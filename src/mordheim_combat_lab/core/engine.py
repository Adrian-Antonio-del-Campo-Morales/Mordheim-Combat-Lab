"""Single NumPy-vectorized executor for close-combat effects."""
from __future__ import annotations
from dataclasses import dataclass, replace
import numpy as np
from .compiler import merge_effects
from .models import CompiledFighter, DuelRequest, DuelResult, EffectSet, SimulationCancelled

STANDING, KNOCKED_DOWN, STUNNED, PARALYZED, OUT = range(5)

@dataclass(slots=True)
class CombatState:
    wounds: np.ndarray
    condition: np.ndarray
    initiative_penalty: np.ndarray
    frenzy: np.ndarray
    lucky_charm: np.ndarray
    crimson_initiative: np.ndarray
    attack_penalty: np.ndarray
    entangled: np.ndarray
    parry_used: np.ndarray
    parry_remaining: np.ndarray
    critical_used: np.ndarray
    force_of_will_used: np.ndarray
    force_of_will_active: np.ndarray
    force_of_will_penalty: np.ndarray
    disability: np.ndarray
    mark_of_old_ones_used: np.ndarray
    on_fire: np.ndarray
    weapon_skill: np.ndarray
    strength: np.ndarray
    toughness: np.ndarray
    initiative: np.ndarray
    attacks: np.ndarray

@dataclass(slots=True)
class PreparedAttack:
    weapon: EffectSet
    effect: EffectSet
    active: np.ndarray
    strength: np.ndarray
    hit_target: np.ndarray
    rolls: np.ndarray
    hit_rows: np.ndarray

def has(effect: EffectSet, mechanic_id: str) -> bool:
    return mechanic_id in effect.tags

def _parry_capacity(fighter: CompiledFighter) -> int:
    """Return the number of parries available in a close-combat phase."""
    if not has(fighter.global_effects, "skill.unbeatable-warrior"):
        return 1
    return 2 if fighter.main_weapon.parry and fighter.off_hand is not None and fighter.off_hand.parry else 1

def _claim_criticals(candidate: np.ndarray, rows: np.ndarray, state: CombatState) -> np.ndarray:
    """Allow at most one critical per attacker and close-combat phase."""
    accepted = candidate & ~state.critical_used[rows]
    state.critical_used[rows[accepted]] = True
    return accepted

def _critical_wound_threshold(effect: EffectSet, weapon: EffectSet, poison_blocked: bool) -> int:
    """Return the natural To Wound roll that produces a critical hit."""
    if (has(effect, "poison.wolfsbane") and not poison_blocked) or has(effect, "mechanic.body-slam"):
        return 5
    if has(effect, "skill.art-of-silent-death"):
        return 5
    if has(effect, "skill.unarmed-critical-strikes") and has(weapon, "weapon.natural-attacks"):
        return 5
    return 6

def to_hit(attacker_ws: int, defender_ws: int) -> int:
    return 2 if defender_ws == 0 else 3 if attacker_ws > defender_ws else 5 if defender_ws > 2 * attacker_ws else 4

def wound_targets(strength: np.ndarray, toughness: int, maximum: int = 7) -> np.ndarray:
    difference = strength - toughness
    targets = np.select((difference >= 2, difference == 1, difference == 0, difference == -1, difference >= -3), (2, 3, 4, 5, 6), default=7)
    return np.minimum(targets, maximum).astype(np.int8)

def effective_initiative(fighter: CompiledFighter, state: CombatState) -> np.ndarray:
    return np.maximum(1, state.initiative + fighter.global_effects.initiative_bonus + fighter.main_weapon.initiative_bonus + state.crimson_initiative - state.initiative_penalty)

def _characteristic_test(fighter: CompiledFighter, target: np.ndarray,
                         rng: np.random.Generator, *, six_always_fails: bool = False) -> np.ndarray:
    """Resolve a D6 characteristic test, including Blessed Sight's one reroll."""
    rolls = rng.integers(1, 7, target.size)
    passed = rolls <= target
    if six_always_fails:
        passed &= rolls != 6
    failed = ~passed
    if failed.any() and has(fighter.global_effects, "skill.blessed-sight"):
        rerolls = rng.integers(1, 7, int(failed.sum()))
        rerolled = rerolls <= target[failed]
        if six_always_fails:
            rerolled &= rerolls != 6
        passed[failed] = rerolled
    return passed

def attack_count(fighter: CompiledFighter, charging: np.ndarray, first_round: bool = False,
                 frenzy: np.ndarray | None = None, charged: np.ndarray | None = None,
                 attack_penalty: np.ndarray | None = None,
                 wounded: np.ndarray | None = None,
                 base_attacks: np.ndarray | None = None) -> np.ndarray:
    effect = fighter.global_effects
    base = fighter.characteristics.attacks + effect.attacks_bonus + int(fighter.off_hand_attacks or fighter.main_weapon.paired)
    if has(fighter.main_weapon, "weapon.double-bladed-sword") or has(fighter.main_weapon, "weapon.bo"):
        base += 1
    result = (base_attacks.astype(np.int16,copy=True)+base-fighter.characteristics.attacks
              if base_attacks is not None else np.full(charging.size,base,dtype=np.int16))
    if wounded is not None and has(effect,"maddened_with_pain"):
        result += wounded.astype(np.int16)
    result += charging.astype(np.int16) * effect.charge_attacks_bonus
    if has(effect,"skill.shield-strike") and fighter.off_hand is not None and has(fighter.off_hand,"defence.shield"):
        result += 1
    if has(effect,"skill.unarmed-fighting") and has(fighter.main_weapon,"weapon.natural-attacks"):
        result += 1
    if has(effect,"skill.art-of-silent-death") and (has(fighter.main_weapon,"weapon.natural-attacks") or has(fighter.main_weapon,"weapon.fighting-claws")):
        result += 1
    if has(effect,"skill.inspiring-sermon"):
        result += 1
    if first_round:
        result += fighter.main_weapon.first_round_attacks_bonus
        if frenzy is not None:
            result[frenzy] *= 2
        elif effect.frenzy: result *= 2
        if has(effect, "skill.ferocious-charge"):
            result[charging] *= 2
    if has(fighter.main_weapon, "weapon.vomit-attack"):
        result[:] = 1
    if has(effect, "skill.sweep") and fighter.main_weapon.two_handed:
        # Sweep replaces the warrior's normal attacks with a single Initiative
        # test attack; it is not one test for each attack characteristic.
        result[:] = 1
    if has(fighter.main_weapon, "weapon.pistol") or has(fighter.main_weapon, "weapon.duelling-pistol"):
        if not first_round:
            result[:] = 0
        else:
            result[:] = 1
    if first_round and (has(effect,"mechanic.body-slam") or has(effect,"mechanic.bull-charge")):
        result[charging] = 1
    if first_round and has(effect,"mechanic.anvil-head"):
        result[charging] = 1
    if has(effect,"mechanic.death-blow") and fighter.characteristics.attacks >= 2:
        result[:] = 1
    if has(effect,"mechanic.energy-focus") and has(fighter.main_weapon,"weapon.natural-attacks"):
        result[:] = 1
    if attack_penalty is not None:result=np.maximum(0,result-attack_penalty)
    return result

def priority(fighter: CompiledFighter, opponent: CompiledFighter, first_round: bool,
             charging: np.ndarray, charged: np.ndarray, stood: np.ndarray) -> np.ndarray:
    weapon_priority = fighter.main_weapon.priority
    if fighter.global_effects.strongman and weapon_priority < 0:
        weapon_priority = 0
    value = np.full(charging.size, weapon_priority + fighter.global_effects.priority, dtype=np.int8)
    if has(fighter.global_effects,"mechanic.strike-first-vs-skinks-always") and has(opponent.global_effects,"species.skink"):
        value[:] = 20
    if first_round:
        value = np.maximum(value, charging.astype(np.int8))
        if has(fighter.global_effects,"mechanic.strike-first-vs-skinks-first-round") and has(opponent.global_effects,"species.skink"):
            value[:] = 20
        if has(fighter.global_effects, "skill.lightning-reflexes"):
            value[charged] = np.maximum(value[charged], 1)
    value[stood] = -1
    return value

def _parry_hits(defender: CompiledFighter, effect: EffectSet, hit_rows: np.ndarray,
                hit_values: np.ndarray, hit_strength: np.ndarray,
                defender_state: CombatState,
                rng: np.random.Generator,
                selected_rows: np.ndarray | None = None) -> tuple[np.ndarray,np.ndarray]:
    if effect.cannot_be_parried:
        return hit_rows,np.empty(0,dtype=np.int64)
    parry = (defender.main_weapon.parry or bool(defender.off_hand and defender.off_hand.parry)
             or defender.global_effects.parry or has(defender.global_effects,"skill.miniath"))
    parry |= has(defender.global_effects,"skill.axe-master") and has(defender.main_weapon,"weapon.axe")
    parry |= has(defender.global_effects,"skill.shield-mastery") and bool(defender.off_hand and has(defender.off_hand,"defence.shield"))
    if not parry or hit_rows.size == 0:
        return hit_rows,np.empty(0,dtype=np.int64)
    eligible = ((defender_state.condition[hit_rows] == STANDING)
                & (defender_state.parry_remaining[hit_rows] > 0)
                & (hit_strength < 2 * defender_state.strength[hit_rows]))
    if selected_rows is not None:
        eligible &= np.isin(hit_rows, selected_rows)
    highest = np.zeros(hit_rows.size, dtype=bool)
    for row in np.unique(hit_rows[eligible]):
        positions = np.flatnonzero((hit_rows == row) & eligible)
        limit = int(defender_state.parry_remaining[row])
        highest[positions[np.argsort(hit_values[positions])[-limit:]]] = True
    eligible &= highest
    if not eligible.any():
        return hit_rows,np.empty(0,dtype=np.int64)
    parry_roll = rng.integers(1, 7, hit_rows.size)
    match_allowed = any(has(defender.global_effects,x) for x in ("skill.sword-master","skill.swordmaster","skill.defensive-stance","skill.unbeatable-warrior"))
    blocked = eligible & (hit_values != 6) & ((parry_roll >= hit_values) if match_allowed else (parry_roll > hit_values))
    dwarf_axes = has(defender.main_weapon,"weapon.dwarf-axe") and bool(defender.off_hand and has(defender.off_hand,"weapon.dwarf-axe"))
    miniath_reroll = (has(defender.global_effects,"skill.miniath")
                      and (defender.main_weapon.parry or bool(defender.off_hand and defender.off_hand.parry)))
    reroll = (miniath_reroll or has(defender.global_effects,"skill.swordmaster")
              or (has(defender.global_effects,"skill.sword-master") and dwarf_axes)
              or has(defender.main_weapon,"weapon.double-bladed-sword"))
    if reroll and (~blocked).any():
        second = rng.integers(1, 7, hit_rows.size)
        blocked |= eligible & (hit_values != 6) & ((second >= hit_values) if match_allowed else (second > hit_values))
    defender_state.parry_used[hit_rows[eligible]] = True
    defender_state.parry_remaining[hit_rows[eligible]] -= 1
    return hit_rows[~blocked],hit_rows[blocked]

def _prepare_weapon_attack(attacker: CompiledFighter, defender: CompiledFighter, weapon: EffectSet,
                           active: np.ndarray, charging: np.ndarray,
                           attacker_state: CombatState, defender_state: CombatState,
                           rng: np.random.Generator,
                           first_round: bool) -> PreparedAttack | None:
    if active.size == 0:
        return None
    stunned = active[defender_state.condition[active] == STUNNED]
    defender_state.condition[stunned] = OUT
    active = active[defender_state.condition[active] != OUT]
    if active.size == 0:
        return None
    effect = weapon if has(weapon,"mechanic.body-slam") else merge_effects(weapon, attacker.global_effects)
    charge_rows = charging[active]
    strength = (np.full(active.size,effect.fixed_strength,dtype=np.int16) if effect.fixed_strength
                else attacker_state.strength[active]+effect.strength_bonus)
    if has(effect,"mechanic.energy-focus") and has(weapon,"weapon.natural-attacks"):
        strength += np.maximum(0,attacker_state.attacks[active]-1)
    if has(weapon, "rule.scorpion-tail") and (
        defender.global_effects.poison_immunity or has(defender.global_effects, "poison_immune")
    ):
        strength[:] = 2
    retain_named_weapon_bonus = (
        has(effect,"mechanic.retain-flail-morning-star-strength-bonus")
        and any(has(weapon,tag) for tag in ("weapon.flail","weapon.morning-star"))
    )
    if first_round or has(effect,"skill.tireless") or has(effect,"skill.mighty-biceps") or retain_named_weapon_bonus:
        strength += weapon.first_round_strength_bonus
    if first_round:
        strength += charge_rows.astype(np.int16) * effect.charge_strength_bonus
    if defender.global_effects.incoming_strength_modifier:
        strength = np.maximum(1, strength + defender.global_effects.incoming_strength_modifier)
    attacker_ws = attacker_state.weapon_skill[active]
    if first_round:
        attacker_ws_values = attacker_ws + charge_rows.astype(np.int8) * effect.charge_ws_bonus
    else:
        attacker_ws_values = attacker_ws
    hit_target = np.array([to_hit(int(ws),int(dws)) for ws,dws in zip(attacker_ws_values,defender_state.weapon_skill[active])],dtype=np.int8)
    modifier = np.full(active.size, effect.hit_modifier, dtype=np.int8)
    modifier += defender.global_effects.incoming_hit_modifier
    knife_fighting=has(effect,"skill.knife-fighting") and (has(weapon,"weapon.dagger") or has(weapon,"weapon.yambiya"))
    modifier += int(knife_fighting)
    if has(effect, "skill.berserker"):
        modifier += charge_rows.astype(np.int8)
    if first_round and has(attacker.global_effects, "skill.ferocious-charge"):
        modifier[charge_rows] -= 1
    if first_round and has(defender.global_effects, "skill.bellowing-battle-roar"):
        modifier -= 1
    if has(defender.global_effects,"cloud_of_flies"):
        modifier -= 1
    hit_target = np.clip(hit_target - modifier, 2, 6)
    if has(effect,"skill.sweep") and weapon.two_handed:
        failed_tests = ~_characteristic_test(defender, defender_state.initiative[active], rng)
        rolls=np.where(failed_tests,6,1).astype(np.int8);successful=failed_tests
    else:
        rolls = np.full(active.size, 6, dtype=np.int8) if effect.automatic_hit else rng.integers(1, 7, active.size, dtype=np.int8)
        successful = rolls >= hit_target
    helpless = np.isin(defender_state.condition[active], (KNOCKED_DOWN, PARALYZED))
    successful |= helpless
    rolls[helpless] = 1
    reroll = np.full(active.size, effect.reroll_hits, dtype=bool)
    reroll |= charge_rows & effect.charge_reroll_hits
    reroll |= first_round and has(effect, "skill.hatred")
    amazon_enemy=any(tag.startswith("band.lizardmen") or "norse" in tag for tag in defender.global_effects.tags)
    reroll |= first_round and has(attacker.global_effects,"mechanic.amazon-isolationists") and amazon_enemy
    reroll |= charge_rows & has(effect, "skill.infallible")
    reroll |= charge_rows & first_round & has(effect,"skill.axe-expert") & (has(weapon,"weapon.axe") or has(weapon,"weapon.dwarf-axe"))
    reroll |= charge_rows & first_round & has(effect,"skill.expert-swordsman") & any(has(weapon,x) for x in ("weapon.sword","weapon.scimitar","weapon.weeping-blades"))
    reroll |= first_round & has(effect,"skill.crack-shot") & any(has(weapon,x) for x in ("weapon.pistol","weapon.duelling-pistol"))
    reroll |= charge_rows & has(attacker.global_effects,"dagger_master") & (has(weapon,"weapon.dagger") or has(weapon,"weapon.yambiya"))
    reroll |= has(effect,"skill.weapons-of-the-north") and (has(weapon,"weapon.axe") or has(weapon,"weapon.dwarf-axe") or weapon.two_handed)
    reroll |= first_round and has(effect,"skill.duellist")
    reroll |= has(effect,"skill.luck")
    if has(effect, "skill.virtue-of-valour"):
        reroll |= defender_state.strength[active]>attacker_state.strength[active]
    failed = np.flatnonzero(reroll & ~successful)
    if failed.size:
        rerolls = rng.integers(1, 7, failed.size)
        successful[failed] = rerolls >= hit_target[failed]
        rolls[failed] = rerolls
    if has(attacker.global_effects,"mechanic.mark-of-the-old-ones"):
        available=(~successful)&(~attacker_state.mark_of_old_ones_used[active])
        chosen=np.flatnonzero(available)
        if chosen.size:
            # Each duel row represents one independent warrior, so each may
            # convert its first failed roll once per battle.
            successful[chosen]=True
            rolls[chosen]=hit_target[chosen]
            attacker_state.mark_of_old_ones_used[active[chosen]]=True
    hit_rows = active[successful]
    if has(defender.global_effects,"mechanic.spider-infested"):
        missed=active[~successful]
        np.add.at(attacker_state.initiative_penalty,missed,1)
    return PreparedAttack(weapon,effect,active,strength,hit_target,rolls,hit_rows)

def _resolve_weapon(attacker: CompiledFighter, defender: CompiledFighter, weapon: EffectSet,
                    active: np.ndarray, charging: np.ndarray, attacker_state: CombatState,
                    defender_state: CombatState, rng: np.random.Generator, first_round: bool,
                    prepared: PreparedAttack | None = None,
                    parry_rows: np.ndarray | None = None) -> None:
    prepared = prepared or _prepare_weapon_attack(attacker,defender,weapon,active,charging,attacker_state,defender_state,rng,first_round)
    if prepared is None:
        return
    weapon,effect,active,strength,hit_target,rolls,hit_rows = (
        prepared.weapon,prepared.effect,prepared.active,prepared.strength,
        prepared.hit_target,prepared.rolls,prepared.hit_rows)
    knife_fighting=has(effect,"skill.knife-fighting") and (has(weapon,"weapon.dagger") or has(weapon,"weapon.yambiya"))
    hit_rows = hit_rows[defender_state.condition[hit_rows] != OUT]
    hit_values = rolls[np.searchsorted(active, hit_rows)]
    hit_positions = np.searchsorted(active, hit_rows)
    hit_rows,parried_rows = _parry_hits(defender,effect,hit_rows,hit_values,strength[hit_positions],defender_state,rng,parry_rows)
    if parried_rows.size and has(defender.global_effects,"mechanic.spider-infested"):
        np.add.at(attacker_state.initiative_penalty,parried_rows,1)
    if parried_rows.size and (has(defender.main_weapon,"weapon.cutlass") or bool(defender.off_hand and has(defender.off_hand,"weapon.cutlass"))) and not has(weapon,"effect.cutlass-counter"):
        counter=EffectSet(tags=("effect.cutlass-counter",))
        _resolve_weapon(defender,attacker,counter,parried_rows,np.zeros(charging.size,dtype=bool),defender_state,attacker_state,rng,False)
    if hit_rows.size == 0:
        return
    hit_positions = np.searchsorted(active, hit_rows)
    hit_values = rolls[hit_positions]
    if has(weapon,"weapon.kusara-kama"):
        penalized=hit_rows[hit_values>=5];np.add.at(defender_state.attack_penalty,penalized,1)
    if has(weapon,"weapon.chained-squig"):
        defender_state.entangled[hit_rows]=True
    if defender_state.lucky_charm[hit_rows].any():
        eligible = defender_state.lucky_charm[hit_rows]
        charm_rolls = rng.integers(1, 7, hit_rows.size)
        defender_state.lucky_charm[hit_rows[eligible]] = False
        hit_rows = hit_rows[~(eligible & (charm_rolls >= 4))]
        if hit_rows.size == 0:
            return
        hit_positions = np.searchsorted(active, hit_rows)
        hit_values = rolls[hit_positions]
    if has(effect,"mechanic.anvil-head"):
        repeats=rng.integers(1,4,hit_rows.size)
        hit_rows=np.repeat(hit_rows,repeats)
        hit_positions=np.repeat(hit_positions,repeats)
        hit_values=np.repeat(hit_values,repeats)
    ignition_target=min(effect.ignition_threshold,defender.global_effects.caught_fire_threshold)
    if ignition_target<=6 and hit_rows.size:
        ignited=rng.integers(1,7,hit_rows.size)>=ignition_target
        defender_state.on_fire[hit_rows[ignited]]=True
    poison_blocked = defender.global_effects.poison_immunity or has(defender.global_effects, "poison_immune")
    automatic_wound = (hit_values == 6) if ((has(effect, "poison.black-lotus") and not poison_blocked) or has(effect,"wight_blades")) else np.zeros(hit_rows.size,dtype=bool)
    strength_hits = strength[hit_positions]
    toughness = defender_state.toughness[hit_rows] + defender.global_effects.toughness_bonus
    raw_targets = wound_targets(strength_hits, toughness, effect.maximum_wound_target)
    targets = np.minimum(raw_targets,4) if has(effect,"skill.monster-slayer") else raw_targets
    # A positive modifier improves the wound roll (for example, Manbane and
    # Expert Fighter), while a natural 1 remains a failed wound roll.
    targets = np.maximum(2, targets - effect.wound_modifier)
    wound_rolls = rng.integers(1, 7, hit_rows.size)
    critical_rolls = wound_rolls.copy()
    wounded = automatic_wound | (wound_rolls >= targets)
    bear_hug_rows = np.zeros(hit_rows.size, dtype=bool)
    # The Bear may replace two successful hits against one opponent with one
    # crushing contest.  It is resolved here, after parries and charms but
    # before armour, so its successful wound correctly permits no armour save.
    bear_hug = attacker.global_effects.bear_hug
    if bear_hug and hit_rows.size:
        unique, counts = np.unique(hit_rows, return_counts=True)
        hug_rows = unique[counts >= 2]
        if hug_rows.size:
            hug_positions = np.array([np.flatnonzero(hit_rows == row)[0] for row in hug_rows])
            attacker_rolls = rng.integers(1, 7, hug_rows.size)
            defender_rolls = rng.integers(1, 7, hug_rows.size)
            won = attacker_rolls + strength_hits[hug_positions] >= defender_rolls + defender_state.strength[hug_rows]
            keep = ~np.isin(hit_rows, hug_rows)
            hit_rows = np.concatenate((hit_rows[keep], hug_rows))
            hit_positions = np.concatenate((hit_positions[keep], hit_positions[hug_positions]))
            strength_hits = np.concatenate((strength_hits[keep], strength_hits[hug_positions]))
            wound_rolls = np.concatenate((wound_rolls[keep], wound_rolls[hug_positions]))
            critical_rolls = np.concatenate((critical_rolls[keep], critical_rolls[hug_positions]))
            targets = np.concatenate((targets[keep], targets[hug_positions]))
            automatic_wound = np.concatenate((automatic_wound[keep], won))
            wounded = np.concatenate((wounded[keep], won))
            bear_hug_rows = np.concatenate((np.zeros(int(keep.sum()), dtype=bool), np.ones(hug_rows.size, dtype=bool)))
    if has(weapon,"weapon.rapier") and (~wounded).any():
        failed=np.flatnonzero(~wounded);extra_hits=rng.integers(1,7,failed.size)>=np.minimum(6,hit_target[hit_positions[failed]]+1)
        extra_wounds=rng.integers(1,7,failed.size)>=targets[failed]
        wounded[failed]=extra_hits&extra_wounds
    if has(effect, "poison.manbane") and not poison_blocked:
        wounded &= wound_rolls != 1
    if effect.reroll_wounds and (~wounded).any():
        failed = np.flatnonzero(~wounded)
        rerolls = rng.integers(1, 7, failed.size)
        wounded[failed] = rerolls >= targets[failed]
        wound_rolls[failed] = rerolls
    if has(attacker.global_effects,"mechanic.mark-of-the-old-ones"):
        available=(~wounded)&(~attacker_state.mark_of_old_ones_used[hit_rows])
        chosen=np.flatnonzero(available)
        if chosen.size:
            wounded[chosen]=True
            wound_rolls[chosen]=targets[chosen]
            attacker_state.mark_of_old_ones_used[hit_rows[chosen]]=True
    wound_rows = hit_rows[wounded]
    if wound_rows.size == 0:
        return
    wound_positions = np.searchsorted(hit_rows, wound_rows)
    wound_strength = strength_hits[wounded].copy()
    if has(effect,"skill.monster-slayer-effective-strength-armour"):
        boosted = raw_targets[wounded] > 4
        wound_strength[boosted] = np.maximum(wound_strength[boosted], toughness[wounded][boosted])
    critical_threshold = _critical_wound_threshold(effect, weapon, poison_blocked)
    if has(attacker.global_effects,"spiritual_weapons"):critical_threshold=5
    critical = _claim_criticals((critical_rolls[wounded] >= critical_threshold) & (targets[wounded] < 6), wound_rows, attacker_state)
    if has(effect, "effect.no-critical"):
        critical[:] = False
    if has(defender.global_effects,"skill.hardy-constitution") and critical.any():
        critical &= rng.integers(1,7,critical.size)<5
    save_modifier=np.maximum(0,wound_strength-3)+effect.armour_penetration-effect.target_armour_bonus
    save_target=np.full(wound_rows.size,defender.armour_save,dtype=np.int16)+save_modifier
    natural=np.full(wound_rows.size,defender.natural_armour_save,dtype=np.int16)
    if not defender.natural_armour_unmodified:natural+=save_modifier
    natural=np.minimum(natural,defender.natural_armour_worst_save)
    if defender.global_effects.natural_armour_negated_by_magic and has(effect,"attack.magical"):
        natural[:]=7
    save_target=np.minimum(save_target,natural)
    save_floor=defender.global_effects.armour_save_floor
    if effect.ignore_armour:
        save_target[:]=save_floor if defender.global_effects.armour_cannot_be_ignored else 7
    elif bear_hug_rows.any():
        save_target[bear_hug_rows[wounded]] = 7
    if save_floor<=6:
        save_target=np.minimum(save_target,save_floor)
    saved = np.zeros(wound_rows.size, dtype=bool)
    eligible = save_target <= 6
    saved[eligible] = rng.integers(1, 7, int(eligible.sum())) >= np.maximum(2, save_target[eligible])
    wound_rows = wound_rows[~saved]
    critical = critical[~saved]
    if wound_rows.size == 0:
        return
    ward=defender.global_effects.ward_save
    if defender.global_effects.step_aside:
        ward=min(ward,4 if has(defender.global_effects,"skill.vampire-reflexes") else 5)
    if has(defender.global_effects,"skill.elven-agility") and defender.global_effects.step_aside:ward=min(ward,4)
    if ward <= 6 and not (defender.global_effects.ward_save_mundane_only and has(effect,"attack.magical")):
        protected = rng.integers(1, 7, wound_rows.size) >= ward
        wound_rows = wound_rows[~protected]
        critical = critical[~protected]
    regeneration=defender.global_effects.regeneration_save
    regeneration_blocked = (
        (defender.global_effects.regeneration_blocked_by_fire and has(effect,"attack.fire"))
        or (defender.global_effects.regeneration_blocked_by_blessed and has(effect,"attack.blessed"))
    )
    if regeneration<=6 and wound_rows.size and not regeneration_blocked:
        regenerated=rng.integers(1,7,wound_rows.size)>=regeneration
        wound_rows=wound_rows[~regenerated];critical=critical[~regenerated]
    if wound_rows.size == 0:
        return
    if defender.injury_profile==2:
        defender_state.condition[wound_rows]=OUT
        return
    helpless_wounds = np.isin(defender_state.condition[wound_rows], (KNOCKED_DOWN, PARALYZED))
    defender_state.condition[wound_rows[helpless_wounds]] = OUT
    damage = max(1, effect.damage)
    if has(defender.global_effects,"flammable") and has(effect,"attack.fire"):
        damage *= 2
    np.subtract.at(defender_state.wounds, np.repeat(wound_rows, damage), 1)
    if has(defender.global_effects, "acid_blood"):
        reactive = EffectSet(
            tags=("rule.acid-blood", "effect.no-critical"),
            fixed_strength=3,
            automatic_hit=True,
            cannot_be_parried=True,
        )
        counts = np.bincount(wound_rows, minlength=defender_state.wounds.size)
        for index in range(int(counts.max(initial=0)) * damage):
            reactive_rows = np.flatnonzero(counts * damage > index)
            _resolve_weapon(
                defender, attacker, reactive, reactive_rows,
                np.zeros(attacker_state.wounds.size, dtype=bool),
                defender_state, attacker_state, rng, False,
            )
    if has(effect, "poison.nightshade") and not poison_blocked:
        np.add.at(defender_state.initiative_penalty, wound_rows, 1)
    if has(effect, "poison.spider-spittle") and not poison_blocked:
        failed_tests = ~_characteristic_test(defender, defender_state.toughness[wound_rows], rng)
        paralyzed = wound_rows[failed_tests & (defender_state.condition[wound_rows] == STANDING)]
        defender_state.condition[paralyzed] = PARALYZED
    injured = np.unique(wound_rows[defender_state.wounds[wound_rows] <= 0])
    if injured.size == 0:
        return
    critical_by_row = {int(row): bool(value) for row, value in zip(wound_rows, critical)}
    injury_rolls = rng.integers(1, 7, injured.size) + effect.injury_modifier + int(knife_fighting)
    critical_bonus=2+int(has(effect,"skill.web-of-steel"))
    injury_rolls += np.array([critical_bonus if critical_by_row.get(int(row), False) else 0 for row in injured])
    threshold = defender.global_effects.out_of_action_threshold
    if has(defender.global_effects,"injury_reroll_out") and not has(effect,"attack.fire"):
        out_threshold = 6 if has(defender.global_effects,"skill.hard-to-kill") or has(defender.global_effects,"skill.tough-as-steel") else threshold
        reroll = injury_rolls >= out_threshold
        injury_rolls[reroll] = rng.integers(1, 7, int(reroll.sum()))
    injury = np.where(injury_rolls >= threshold, OUT, np.where(injury_rolls >= 3, STUNNED, KNOCKED_DOWN)).astype(np.int8)
    if has(defender.global_effects,"skill.tough-as-steel"):
        injury=np.where(injury_rolls>=6,OUT,np.where(injury_rolls>=4,STUNNED,KNOCKED_DOWN)).astype(np.int8)
    if effect.concussion and not has(defender.global_effects,"concussion_immune"):
        injury[(injury_rolls >= 2) & (injury_rolls <= 4)] = STUNNED
    if defender.injury_profile==1:
        injury=np.where(injury_rolls>=4,OUT,np.where(injury_rolls>=2,STUNNED,KNOCKED_DOWN)).astype(np.int8)
    elif defender.injury_profile==3:
        injury=np.where(injury_rolls>=4,OUT,KNOCKED_DOWN).astype(np.int8)
    if has(defender.global_effects,"fragile_halflings"):
        injury[injury_rolls == 2] = STUNNED
    if has(defender.global_effects,"poisonous_injury"):
        injury=np.where(injury_rolls>=5,OUT,np.where(injury_rolls>=2,STUNNED,KNOCKED_DOWN)).astype(np.int8)
    if has(defender.global_effects,"survivor"):
        injury[injury==OUT]=STUNNED
    if has(effect, "skill.head-crusher"):
        injury[injury == KNOCKED_DOWN] = STUNNED
    if has(defender.global_effects, "skill.ignore-pain"):
        injury[injury == STUNNED] = KNOCKED_DOWN
    if has(defender.global_effects,"skill.jump-up"):
        injury[injury==KNOCKED_DOWN]=STANDING
    if has(defender.global_effects,"preparation.mandrake-root"):
        injury[injury==STUNNED]=KNOCKED_DOWN
    if defender.global_effects.thick_skull:
        stunned = injury == STUNNED
        threshold_roll = 2 if defender.helmet_save <= 4 else 3
        recovery = rng.integers(1, 7, injured.size) >= threshold_roll
        injury[stunned & recovery] = KNOCKED_DOWN
    if defender.helmet_save <= 6:
        stunned = injury == STUNNED
        recovery = rng.integers(1, 7, injured.size) >= defender.helmet_save
        injury[stunned & recovery] = KNOCKED_DOWN
    defender_state.condition[injured] = np.maximum(defender_state.condition[injured], injury)
    defender_state.frenzy[injured] &= injury == STANDING
    contagious_rows=injured[(injury==OUT)]
    if (contagious_rows.size and has(defender.global_effects,"contagious")
            and not has(attacker.global_effects,"undead_or_possessed")):
        passed = _characteristic_test(attacker, attacker_state.toughness[contagious_rows], rng,
                                      six_always_fails=True)
        infected=contagious_rows[~passed]
        attacker_state.wounds[infected]-=1
        defeated=infected[attacker_state.wounds[infected]<=0]
        if defeated.size:
            attacker_state.condition[defeated]=OUT

def resolve_attacks(attacker: CompiledFighter, defender: CompiledFighter, rows: np.ndarray,
                    attacks: np.ndarray, charging: np.ndarray, attacker_state: CombatState,
                    defender_state: CombatState, rng: np.random.Generator, first_round: bool) -> None:
    if rows.size == 0:
        return
    bull_rows=rows[first_round & charging[rows] & has(attacker.global_effects,"mechanic.bull-charge")]
    if bull_rows.size:
        bull=EffectSet(tags=("mechanic.bull-charge",),hit_modifier=1)
        prepared=_prepare_weapon_attack(attacker,defender,bull,bull_rows,charging,attacker_state,defender_state,rng,first_round)
        if prepared is not None:
            hit_rows=prepared.hit_rows[defender_state.condition[prepared.hit_rows]!=OUT]
            hit_values=prepared.rolls[np.searchsorted(prepared.active,hit_rows)]
            hit_strength=prepared.strength[np.searchsorted(prepared.active,hit_rows)]
            hit_rows,_=_parry_hits(defender,prepared.effect,hit_rows,hit_values,hit_strength,defender_state,rng)
            if hit_rows.size:
                charm=defender_state.lucky_charm[hit_rows]
                if charm.any():
                    rolls=rng.integers(1,7,hit_rows.size)
                    defender_state.lucky_charm[hit_rows[charm]]=False
                    hit_rows=hit_rows[~(charm&(rolls>=4))]
                standing=hit_rows[defender_state.condition[hit_rows]==STANDING]
                defender_state.condition[standing]=KNOCKED_DOWN
        rows=rows[~np.isin(rows,bull_rows)]
        if rows.size==0:return
    maximum = int(attacks[rows].max(initial=0))
    prepared_attacks: list[PreparedAttack] = []
    body_rows=rows[first_round & charging[rows] & has(attacker.global_effects,"mechanic.body-slam")]
    if body_rows.size:
        body=EffectSet(tags=("mechanic.body-slam",),strength_bonus=1,hit_modifier=1)
        prepared=_prepare_weapon_attack(attacker,defender,body,body_rows,charging,attacker_state,defender_state,rng,first_round)
        if prepared is not None:prepared_attacks.append(prepared)
        rows=rows[~np.isin(rows,body_rows)]
    for index in range(maximum):
        active = rows[(attacks[rows] > index) & (defender_state.condition[rows] != OUT)]
        if active.size == 0:
            continue
        offhand = attacker.off_hand_attacks and attacker.off_hand is not None
        use_off = offhand & (index == attacks[active] - 1)
        main_weapon=attacker.main_weapon
        if index==0 and has(attacker.global_effects,"mechanic.unpredictable-attack"):
            main_weapon=merge_effects(main_weapon,EffectSet(cannot_be_parried=True,tags=("mechanic.unpredictable-attack",)))
        main = _prepare_weapon_attack(attacker,defender,main_weapon,active[~use_off],charging,attacker_state,defender_state,rng,first_round)
        if main is not None:
            prepared_attacks.append(main)
        if offhand:
            off = _prepare_weapon_attack(attacker,defender,attacker.off_hand,active[use_off],charging,attacker_state,defender_state,rng,first_round)
            if off is not None:
                prepared_attacks.append(off)
    for weapon in attacker.extra_attacks:
        extra = _prepare_weapon_attack(attacker, defender, weapon, rows, charging, attacker_state, defender_state, rng, first_round)
        if extra is not None: prepared_attacks.append(extra)
    best_roll = np.full(charging.size,-1,dtype=np.int8)
    second_roll = np.full(charging.size,-1,dtype=np.int8)
    selected = [np.zeros(0,dtype=np.int64) for _ in prepared_attacks]
    owner = np.full(charging.size,-1,dtype=np.int32)
    second_owner = np.full(charging.size,-1,dtype=np.int32)
    two_parries = _parry_capacity(defender) == 2
    for attack_index,prepared in enumerate(prepared_attacks):
        positions=np.searchsorted(prepared.active,prepared.hit_rows)
        values=prepared.rolls[positions]
        better=values>best_roll[prepared.hit_rows]
        if two_parries:
            replaced_rows=prepared.hit_rows[better]
            second_roll[replaced_rows]=best_roll[replaced_rows]
            second_owner[replaced_rows]=owner[replaced_rows]
            between=(~better) & (values>second_roll[prepared.hit_rows])
            second_rows=prepared.hit_rows[between]
            second_roll[second_rows]=values[between]
            second_owner[second_rows]=attack_index
        chosen=prepared.hit_rows[better]
        best_roll[chosen]=values[better]
        owner[chosen]=attack_index
    for attack_index in range(len(prepared_attacks)):
        selected[attack_index]=np.flatnonzero((owner==attack_index) | (second_owner==attack_index))
    for prepared,parry_rows in zip(prepared_attacks,selected):
        _resolve_weapon(attacker,defender,prepared.weapon,prepared.active,charging,
                        attacker_state,defender_state,rng,first_round,
                        prepared=prepared,parry_rows=parry_rows)

def _new_state(fighter: CompiledFighter, count: int, rng: np.random.Generator) -> CombatState:
    wounds = fighter.characteristics.wounds + int(has(fighter.global_effects, "skill.monstrous"))
    crimson = rng.integers(1,4,count,dtype=np.int8) if has(fighter.global_effects,"preparation.crimson-shade") else np.zeros(count,dtype=np.int8)
    characteristic_values={
        "WS":np.full(count,fighter.characteristics.weapon_skill,dtype=np.int16),
        "S":np.full(count,fighter.characteristics.strength,dtype=np.int16),
        "T":np.full(count,fighter.characteristics.toughness,dtype=np.int16),
        "I":np.full(count,fighter.characteristics.initiative,dtype=np.int16),
        "A":np.full(count,fighter.characteristics.attacks,dtype=np.int16),
    }
    for key,dice,sides,bonus in fighter.random_characteristics:
        rolls=np.zeros(count,dtype=np.int16)
        for _ in range(dice):rolls+=rng.integers(1,sides+1,count,dtype=np.int16)
        characteristic_values[key]=rolls+bonus
    state=CombatState(np.full(count, wounds, dtype=np.int16), np.zeros(count, dtype=np.int8),
                       np.zeros(count, dtype=np.int8), np.full(count, fighter.global_effects.frenzy),
                       np.full(count, has(fighter.global_effects, "defence.lucky-charm")),crimson,
                       np.zeros(count,dtype=np.int8),np.zeros(count,dtype=bool),
                       np.zeros(count,dtype=bool),np.full(count,_parry_capacity(fighter),dtype=np.int8),np.zeros(count,dtype=bool),
                       np.zeros(count,dtype=bool),np.zeros(count,dtype=bool),np.zeros(count,dtype=np.int8),
                       np.zeros(count,dtype=np.int8),np.zeros(count,dtype=bool),np.zeros(count,dtype=bool),
                       characteristic_values["WS"],characteristic_values["S"],
                       characteristic_values["T"],characteristic_values["I"],
                       characteristic_values["A"])
    if has(fighter.global_effects,"mechanic.disability"):
        state.disability[:]=rng.integers(1,7,count,dtype=np.int8)
        state.initiative[state.disability==1]=np.maximum(1,state.initiative[state.disability==1]-1)
        state.weapon_skill[state.disability==2]=np.maximum(1,state.weapon_skill[state.disability==2]-1)
        state.toughness[state.disability==4]=np.maximum(1,state.toughness[state.disability==4]-1)
        state.strength[state.disability==5]=np.maximum(1,state.strength[state.disability==5]-1)
    return state

def _resolve_spines(first: CompiledFighter, second: CompiledFighter,
                    rows: np.ndarray, charge1: np.ndarray, charge2: np.ndarray,
                    state1: CombatState, state2: CombatState,
                    rng: np.random.Generator) -> None:
    """Resolve simultaneous, non-critical Spines hits at phase start."""
    spines=EffectSet(
        tags=("rule.spines", "effect.no-critical"), fixed_strength=1,
        automatic_hit=True, cannot_be_parried=True)
    prepared1=(
        _prepare_weapon_attack(first,second,spines,rows,charge1,state1,state2,rng,False)
        if has(first.global_effects,"spines") else None)
    prepared2=(
        _prepare_weapon_attack(second,first,spines,rows,charge2,state2,state1,rng,False)
        if has(second.global_effects,"spines") else None)
    if prepared1 is not None:
        _resolve_weapon(first,second,spines,rows,charge1,state1,state2,rng,False,prepared=prepared1)
    if prepared2 is not None:
        _resolve_weapon(second,first,spines,rows,charge2,state2,state1,rng,False,prepared=prepared2)

def _rescue_force_of_will(fighter: CompiledFighter, state: CombatState,
                          rows: np.ndarray, rng: np.random.Generator) -> None:
    if not has(fighter.global_effects,"mechanic.force-of-will") or rows.size==0:return
    eligible=rows[(state.condition[rows]==OUT)&~state.force_of_will_used[rows]]
    if eligible.size==0:return
    state.force_of_will_used[eligible]=True
    success=_characteristic_test(fighter,state.toughness[eligible],rng)
    rescued=eligible[success]
    state.condition[rescued]=STANDING
    state.wounds[rescued]=1
    state.force_of_will_active[rescued]=True

def _sustain_force_of_will(fighter: CompiledFighter, state: CombatState,
                           rng: np.random.Generator) -> None:
    if not has(fighter.global_effects,"mechanic.force-of-will"):return
    active=np.flatnonzero(state.force_of_will_active&(state.condition!=OUT))
    if active.size==0:return
    state.force_of_will_penalty[active]+=1
    target=np.maximum(0,state.toughness[active]-state.force_of_will_penalty[active])
    failed=rng.integers(1,7,active.size)>target
    removed=active[failed]
    state.condition[removed]=OUT
    state.force_of_will_active[removed]=False

def _black_hunger_backlash(fighter: CompiledFighter, state: CombatState,
                           rows: np.ndarray, rng: np.random.Generator) -> None:
    if not has(fighter.global_effects,"mechanic.black-hunger") or rows.size==0:return
    active=rows[state.condition[rows]!=OUT]
    if active.size==0:return
    hits=rng.integers(1,4,active.size)
    backlash=EffectSet(tags=("mechanic.black-hunger-backlash","effect.no-critical"),fixed_strength=3,
                       automatic_hit=True,cannot_be_parried=True,ignore_armour=True)
    for index in range(3):
        hit_rows=active[hits>index]
        _resolve_weapon(fighter,fighter,backlash,hit_rows,np.zeros(state.wounds.size,dtype=bool),state,state,rng,False)
        _rescue_force_of_will(fighter,state,hit_rows,rng)

def _resolve_fire(victim: CompiledFighter, opponent: CompiledFighter,
                  victim_state: CombatState, opponent_state: CombatState,
                  rng: np.random.Generator) -> None:
    """Resolve the Recovery-phase test and S4 hit for warriors on fire."""
    burning=np.flatnonzero(victim_state.on_fire&(victim_state.condition!=OUT))
    if burning.size==0:return
    extinguished=rng.integers(1,7,burning.size)>=4
    victim_state.on_fire[burning[extinguished]]=False
    still_burning=burning[~extinguished]
    if still_burning.size==0:return
    fire=EffectSet(tags=("attack.fire","effect.no-critical"),fixed_strength=4,
                   automatic_hit=True,cannot_be_parried=True)
    source=replace(opponent,main_weapon=fire,off_hand=None,global_effects=EffectSet(),extra_attacks=())
    _resolve_weapon(source,victim,fire,still_burning,np.zeros(victim_state.wounds.size,dtype=bool),
                    opponent_state,victim_state,rng,False)

def simulate_batch(first: CompiledFighter, second: CompiledFighter, count: int,
                   rng: np.random.Generator, maximum_rounds: int) -> tuple[int, int, int]:
    state1, state2 = _new_state(first,count,rng), _new_state(second,count,rng)
    first_charges = rng.random(count) < .5
    for round_index in range(maximum_rounds):
        if round_index:
            _sustain_force_of_will(first,state1,rng);_sustain_force_of_will(second,state2,rng)
            _resolve_fire(first,second,state1,state2,rng);_resolve_fire(second,first,state2,state1,rng)
        unresolved = (state1.condition != OUT) & (state2.condition != OUT)
        if not unresolved.any():
            break
        state1.parry_used[:] = False; state2.parry_used[:] = False
        state1.parry_remaining[:] = _parry_capacity(first)
        state2.parry_remaining[:] = _parry_capacity(second)
        state1.critical_used[:] = False; state2.critical_used[:] = False
        if has(first.global_effects,"mechanic.spawn-special-attacks"):
            state1.attacks[:]=rng.integers(1,7,count,dtype=np.int16)+1
        if has(second.global_effects,"mechanic.spawn-special-attacks"):
            state2.attacks[:]=rng.integers(1,7,count,dtype=np.int16)+1
        stunned1, stunned2 = state1.condition == STUNNED, state2.condition == STUNNED
        stood1, stood2 = state1.condition == KNOCKED_DOWN, state2.condition == KNOCKED_DOWN
        state1.condition[stunned1] = KNOCKED_DOWN; state2.condition[stunned2] = KNOCKED_DOWN
        state1.condition[stood1 & ~stunned1] = STANDING; state2.condition[stood2 & ~stunned2] = STANDING
        paralyzed1, paralyzed2 = state1.condition == PARALYZED, state2.condition == PARALYZED
        paralyzed_rows1=np.flatnonzero(paralyzed1)
        paralyzed_rows2=np.flatnonzero(paralyzed2)
        if paralyzed_rows1.size:
            recover1=_characteristic_test(first,state1.toughness[paralyzed_rows1],rng)
            state1.condition[paralyzed_rows1[recover1]] = STANDING
        if paralyzed_rows2.size:
            recover2=_characteristic_test(second,state2.toughness[paralyzed_rows2],rng)
            state2.condition[paralyzed_rows2[recover2]] = STANDING
        first_round = round_index == 0
        charge1 = first_charges if first_round else np.zeros(count,dtype=bool)
        charge2 = ~first_charges if first_round else np.zeros(count,dtype=bool)
        if first_round:
            for netter,target,netter_state,target_state,charging in (
                (first,second,state1,state2,charge1),(second,first,state2,state1,charge2)):
                rows=np.flatnonzero(unresolved&charging&has(netter.global_effects,"mechanic.netter"))
                if rows.size:
                    hits=rng.integers(1,7,rows.size)>=max(2,7-netter.ballistic_skill)
                    escape=_characteristic_test(target,target_state.strength[rows],rng)
                    caught=rows[hits&~escape]
                    target_state.condition[caught]=KNOCKED_DOWN
        _resolve_spines(first,second,np.flatnonzero(unresolved),charge1,charge2,state1,state2,rng)
        active=np.flatnonzero(unresolved)
        _rescue_force_of_will(first,state1,active,rng);_rescue_force_of_will(second,state2,active,rng)
        entangled1=np.flatnonzero(state1.entangled&(state2.condition==STANDING)&unresolved)
        entangled2=np.flatnonzero(state2.entangled&(state1.condition==STANDING)&unresolved)
        entangle_effect=EffectSet(tags=("effect.chained-squig-entangle",),fixed_strength=3,automatic_hit=True)
        _resolve_weapon(second,first,entangle_effect,entangled1,charge2,state2,state1,rng,False)
        _resolve_weapon(first,second,entangle_effect,entangled2,charge1,state1,state2,rng,False)
        charged1, charged2 = charge2, charge1
        attacks1=attack_count(first,charge1,first_round,state1.frenzy,charged1,state1.attack_penalty,state1.wounds<first.characteristics.wounds,state1.attacks)
        attacks2=attack_count(second,charge2,first_round,state2.frenzy,charged2,state2.attack_penalty,state2.wounds<second.characteristics.wounds,state2.attacks)
        attacks1=np.maximum(1,attacks1+second.global_effects.incoming_attacks_modifier)
        attacks2=np.maximum(1,attacks2+first.global_effects.incoming_attacks_modifier)
        attacks1[state1.on_fire]=0;attacks2[state2.on_fire]=0
        if has(first.global_effects,"animal_friendship") and has(second.global_effects,"species.animal"):
            attacks2[:]=0
        if has(second.global_effects,"animal_friendship") and has(first.global_effects,"species.animal"):
            attacks1[:]=0
        state1.attack_penalty[:]=0;state2.attack_penalty[:]=0
        if first_round and has(first.main_weapon,"weapon.serpent-whip"):attacks1+=charge1|charged1
        if first_round and has(second.main_weapon,"weapon.serpent-whip"):attacks2+=charge2|charged2
        if first_round and has(first.main_weapon,"weapon.boar-spear"):attacks2[charge2]=np.maximum(1,attacks2[charge2]-1)
        if first_round and has(second.main_weapon,"weapon.boar-spear"):attacks1[charge1]=np.maximum(1,attacks1[charge1]-1)
        if first_round and has(first.global_effects,"skill.sigmar-s-sign") and has(second.global_effects,"undead_or_possessed"):
            attacks2=np.maximum(1,attacks2-1)
        if first_round and has(second.global_effects,"skill.sigmar-s-sign") and has(first.global_effects,"undead_or_possessed"):
            attacks1=np.maximum(1,attacks1-1)
        p1,p2=priority(first,second,first_round,charge1,charged1,stood1),priority(second,first,first_round,charge2,charged2,stood2)
        i1,i2=effective_initiative(first,state1),effective_initiative(second,state2)
        first_acts=(p1>p2)|((p1==p2)&(i1>i2));ties=(p1==p2)&(i1==i2)
        first_acts[ties]=rng.random(int(ties.sum()))<.5
        rows=np.flatnonzero(unresolved&(state1.condition==STANDING)&first_acts)
        resolve_attacks(first,second,rows,attacks1,charge1,state1,state2,rng,first_round)
        _rescue_force_of_will(first,state1,rows,rng);_rescue_force_of_will(second,state2,rows,rng)
        reply=rows[state2.condition[rows]==STANDING]
        resolve_attacks(second,first,reply,attacks2,charge2,state2,state1,rng,first_round)
        _rescue_force_of_will(first,state1,reply,rng);_rescue_force_of_will(second,state2,reply,rng)
        rows=np.flatnonzero(unresolved&(state2.condition==STANDING)&~first_acts)
        resolve_attacks(second,first,rows,attacks2,charge2,state2,state1,rng,first_round)
        _rescue_force_of_will(first,state1,rows,rng);_rescue_force_of_will(second,state2,rows,rng)
        reply=rows[state1.condition[rows]==STANDING]
        resolve_attacks(first,second,reply,attacks1,charge1,state1,state2,rng,first_round)
        _rescue_force_of_will(first,state1,reply,rng);_rescue_force_of_will(second,state2,reply,rng)
        active=np.flatnonzero(unresolved)
        _black_hunger_backlash(first,state1,active,rng)
        _black_hunger_backlash(second,state2,active,rng)
    a=int(np.count_nonzero((state2.condition==OUT)&(state1.condition!=OUT)))
    b=int(np.count_nonzero((state1.condition==OUT)&(state2.condition!=OUT)))
    return a,b,count-a-b

def simulate_duel(request: DuelRequest) -> DuelResult:
    rng=np.random.default_rng(request.seed);a=b=u=0;remaining=request.simulations
    while remaining:
        if request.cancel_event is not None and request.cancel_event.is_set():
            raise SimulationCancelled("simulation cancelled")
        count=min(remaining,request.batch_size)
        x,y,z=simulate_batch(request.first,request.second,count,rng,request.maximum_rounds)
        a+=x;b+=y;u+=z;remaining-=count
    return DuelResult(a,b,u,request.simulations)
