"""Combat simulation engine, independent of the interface."""

import numpy as np

from .enemies import ENEMY_PROFILES
from .rules import *

try:
    from ._combat_fast import simulate_simple as _simulate_simple_native
except ImportError:
    _simulate_simple_native = None


FIGHTER_OFFHAND_HIT_PENALTY = 19
FIGHTER_DUAL_HIT_PENALTY = 20
FIGHTER_UNDEAD_OR_POSSESSED = 21
FIGHTER_BETTER_ARMOUR = 22
FIGHTER_HARD_ARMOUR = 23
FIGHTER_USEFUL_SHIELDS = 24
FIGHTER_FRENZY = 25
FIGHTER_NATURAL_ARMOUR_SAVE = 26
FIGHTER_NATURAL_ARMOUR_UNMODIFIED = 27
FIGHTER_CONCUSSION_IMMUNE = 28
FIGHTER_CLOUD_OF_FLIES = 29
FIGHTER_CHARGE_ATTACK_BONUS = 30
FIGHTER_EXTRA_NATURAL_ATTACKS = 31
FIGHTER_PERFECT_KILLER = 32
FIGHTER_WIGHT_BLADES = 33
FIGHTER_SURVIVOR = 34
FIGHTER_POISONOUS_INJURY = 35
FIGHTER_MADDENED_WITH_PAIN = 36
FIGHTER_INJURY_PROFILE = 37

PRIORITY_FIRST = 0
PRIORITY_NORMAL = 1
PRIORITY_LAST = 2

WHIP_WEAPONS = (
    WEAPON_STEEL_WHIP,
    WEAPON_PIRATE_SCOURGE,
    WEAPON_SERPENT_WHIP,
    WEAPON_BEASTMASTER_WHIP,
)

ENEMY_VARIANTS_PER_PROFILE = 6
SIMULATION_CHUNK_SIZE = 100_000
_ENEMY_VARIANT_CACHE = {}

STATE_STANDING = 0
STATE_KNOCKED_DOWN = 1
STATE_STUNNED = 2
STATE_PARALYZED = 3
STATE_OUT = 4


class SimulationCancelled(RuntimeError):
    """Stop a simulation cleanly when requested by the user."""


def _raise_if_cancelled(cancel_event):
    if cancel_event is not None and cancel_event.is_set():
        raise SimulationCancelled("Simulation cancelled by the user.")


def _skill_mask(skills):
    mask = 0
    for skill in skills:
        if skill == "Strike to Injure":
            mask |= SKILL_STRIKE_TO_INJURE
        elif skill == "Web of Steel":
            mask |= SKILL_CHARGE
        elif skill == "Expert Fighter":
            mask |= SKILL_EXPERT
        elif skill == "Web of Steel":
            mask |= SKILL_CHARGE
        elif skill in ("Step Aside", "Step Aside"):
            mask |= SKILL_SIDESTEP
        elif skill in ("Mighty Blow", "Mighty Blow"):
            mask |= SKILL_POWER
        elif skill in ("Resilient", "Resilient"):
            mask |= SKILL_SEASONED
        elif skill in ("Expert Swordsman", "Expert Swordsman"):
            mask |= SKILL_FENCER
        elif skill in ("Unstoppable Charge", "Unstoppable Charge"):
            mask |= SKILL_UNSTOPPABLE
        elif skill in ("Ferocious Charge", "Ferocious Charge"):
            mask |= SKILL_FEROCIOUS_CHARGE
        elif skill in ("Lightning Reflexes", "Lightning Reflexes"):
            mask |= SKILL_CAT_REFLEXES
        elif skill in ("Jump Up", "Jump Up"):
            mask |= SKILL_SPRING_UP
        elif skill in ("Strongman", "Strongman"):
            mask |= SKILL_STRONGMAN
        elif skill == "Tireless":
            mask |= SKILL_TIRELESS
        elif skill == "Axe Master":
            mask |= SKILL_AXE_MASTER
        elif skill == "Axe Expert":
            mask |= SKILL_AXE_EXPERT
        elif skill == "Shield Strike":
            mask |= SKILL_SHIELD_STRIKE
        elif skill == "Sweep":
            mask |= SKILL_SWEEP
        elif skill in ("Elven Agility", "Elven Agility", "Fey Quickness"):
            mask |= SKILL_ELVEN_AGILITY
        elif skill == "Weapons of the North":
            mask |= SKILL_NORTHERN_WEAPONS
        elif skill == "Mighty Biceps":
            mask |= SKILL_TIRELESS
        elif skill in ("Art of Unarmed Combat", "Art of Unarmed Combat"):
            mask |= SKILL_UNARMED_ART
        elif skill == "art of silent death":
            mask |= SKILL_UNARMED_ART
        elif skill == "Red Fury":
            mask |= SKILL_RED_FURY
        elif skill == "Strength of Steel":
            mask |= SKILL_CHARGE_STRENGTH
        elif skill in ("Crushing Blow", "crushing blow"):
            mask |= SKILL_UNPARRYABLE
        elif skill == "Sure Strike":
            mask |= SKILL_REROLL_WOUNDS
        elif skill == "Infallible":
            mask |= SKILL_CHARGE_REROLL
        elif skill in ("Ignore Pain", "not Pain", "ignore pain"):
            mask |= SKILL_IGNORE_PAIN
        elif skill in ("Always Strikes First", "Always Strikes First"):
            mask |= SKILL_ALWAYS_FIRST
        elif skill in ("Sword Master", "Swordmaster"):
            mask |= SKILL_SWORD_MASTER
        elif skill in ("Master of Blades", "Dwarf Combat Master"):
            mask |= SKILL_UNBEATABLE
        elif skill == "Duellist":
            mask |= SKILL_DUELLIST
        elif skill == "Hatred":
            mask |= SKILL_HATRED
        elif skill == "Crack Shot":
            mask |= SKILL_PISTOL_CRACK_SHOT
        elif skill == "Always Strikes First":
            mask |= SKILL_ALWAYS_FIRST
        elif skill == "Extra Attack":
            mask |= SKILL_RED_FURY
        elif skill == "Blessed Sight":
            mask |= SKILL_REROLL_HITS
        elif skill == "Art of Silent Death":
            mask |= SKILL_ART_OF_SILENT_DEATH
        elif skill == "Unbeatable Warrior":
            mask |= SKILL_UNBEATABLE
        elif skill == "Knife Fighting":
            mask |= SKILL_KNIFE_FIGHT
        elif skill in ("Shield Mastery", "shield master"):
            mask |= SKILL_SHIELD_MASTERY
        elif skill in ("Head Crusher", "’eadbasher"):
            mask |= SKILL_HEAD_CRUSHER
        elif skill in ("Regeneration", "Regeneration"):
            mask |= SKILL_REGENERATION
        elif skill in ("Monster Slayer", "Monster Slayer"):
            mask |= SKILL_MONSTER_SLAYER
        elif skill == "Miniath":
            mask |= SKILL_MINIATH
        elif skill == "Monstrous":
            mask |= SKILL_MONSTROUS
        elif skill == "Very Tough":
            mask |= SKILL_VERY_TOUGH
        elif skill == "Infinite Hatred":
            mask |= SKILL_REROLL_HITS
        elif skill == "Defensive Stance":
            mask |= SKILL_DEFENSIVE_STANCE
        elif skill in ("Hard to Kill", "Tough as Steel"):
            mask |= SKILL_HARDENED_SKIN
        elif skill == "Vampire Reflexes":
            mask |= SKILL_VAMPIRE_REFLEXES
        elif skill in ("Bellowing Battle Roar", "Bellowing Battle Roar"):
            mask |= SKILL_BATTLE_ROAR
        elif skill == "Inspiring Sermon":
            mask |= SKILL_RED_FURY
        elif skill == "Sigmar's Sign":
            mask |= SKILL_SIGMAR_SIGNAL
        elif skill == "Iron Sinews":
            mask |= SKILL_IRON_SINEWS
        elif skill in ("Hardy Constitution", "Hardy Constitution"):
            mask |= SKILL_CRITICAL_RESISTANCE
        elif skill in ("Thick Skull", "Thick Skull", "thick skull", "Thick Skull", "’ard ead"):
            mask |= SKILL_STONE_SKULL
        elif skill in ("Horned One",):
            mask |= SKILL_CHARGE_EXTRA_ATTACK
        elif skill == "Shaggy Hide":
            mask |= SKILL_SHAGGY_HIDE
        elif skill in ("Berserker", "Berserker"):
            mask |= SKILL_BERSERKER_HIT
        elif skill in ("foul odour", "Foul Odour"):
            mask |= SKILL_FOUL_ODOUR
        elif skill in ("True Grit", "true grit"):
            mask |= SKILL_TRUE_GRIT
        elif skill == "berserk charge":
            mask |= SKILL_NORSE_BERSERK_CHARGE
        elif skill == "well ’ard":
            mask |= SKILL_VERY_TOUGH
        elif skill == "Sign of Sigmar":
            mask |= SKILL_SIGMAR_SIGNAL
        elif skill == "savage fury":
            mask |= SKILL_CHARGE_EXTRA_ATTACK
        elif skill == "Berserker":
            mask |= SKILL_UNSTOPPABLE
        elif skill == "Virtue of Valour":
            mask |= SKILL_VALOUR
        elif skill == "Luck":
            mask |= SKILL_LUCK
    return mask


def _armor_base_save(armor):
    code = ARMOR_CODES.get(armor, ARMOR_NONE)
    if code in (ARMOR_LIGHT, ARMOR_HARDENED_LEATHER, ARMOR_WIZARD_ROBE,
                ARMOR_NINJA_GARB, ARMOR_ESHIN_ROBES, ARMOR_CHITIN):
        return 6
    if code in (ARMOR_HEAVY, ARMOR_ITHILMAR):
        return 5
    if code in (ARMOR_GROMRIL, ARMOR_PLATE):
        return 4
    return 7


def _make_fighter(config):
    """Convert a profile into the compact array used by the engine."""
    main_name = config.get("main_weapon", "Sword")
    if main_name in ("None", "None"):
        main = WEAPON_UNARMED
    else:
        try:
            main = WEAPON_CODES[main_name]
        except KeyError as exc:
            raise ValueError(f"Unsupported close-combat weapon: {main_name}") from exc
    off = OFFHAND_CODES.get(config.get("off_hand", "None"), OFF_NONE)
    if config.get("counts_as_buckler", False):
        off = OFF_BUCKLER
    main_material = MATERIAL_CODES.get(
        config.get("main_weapon_material", "Normal"), MATERIAL_NORMAL
    )
    offhand_material = MATERIAL_CODES.get(
        config.get("offhand_material", "Normal"), MATERIAL_NORMAL
    )
    skills = _skill_mask(config.get("skills", []))
    preparation_names = config.get("preparations", ())
    preparation = PREPARATION_NONE
    for preparation_name in preparation_names:
        preparation |= PREPARATION_CODES.get(preparation_name, PREPARATION_NONE)
    if main == WEAPON_BALL_AND_CHAIN:
        preparation |= PREPARATION_HEAD_SPLITTER
    main_poison = POISON_CODES.get(
        config.get("main_poison", "No Poison"), POISON_NONE
    )
    offhand_poison = POISON_CODES.get(
        config.get("offhand_poison", "No Poison"), POISON_NONE
    )
    armor_name = config.get("armor", "No Armour")
    has_sea_dragon_cloak = bool(config.get("has_sea_dragon_cloak", False))
    armor_code = ARMOR_CODES.get(armor_name, ARMOR_NONE)
    has_helmet = bool(config.get("has_helmet", False))
    if main == WEAPON_BALL_AND_CHAIN:
        armor_name = "No Armour"
        armor_code = ARMOR_NONE
        has_helmet = False

    if armor_code in (
        ARMOR_HARDENED_LEATHER, ARMOR_WIZARD_ROBE, ARMOR_NINJA_GARB,
        ARMOR_ESHIN_ROBES,
    ) and off == OFF_SHIELD:
        off = OFF_NONE
    if armor_code in (ARMOR_WIZARD_ROBE, ARMOR_ESHIN_ROBES) and off == OFF_BUCKLER:
        off = OFF_NONE

    if _is_two_handed(main) or _is_paired(main):
        off_weapon = OFF_NONE
    elif main == WEAPON_MORNING_STAR and off != OFF_SHIELD:
        off_weapon = OFF_NONE
    elif main == WEAPON_SPEAR and off not in (OFF_SHIELD, OFF_BUCKLER):
        off_weapon = OFF_NONE
    elif main in (WEAPON_CHOPPA, WEAPON_SQUIG_PROD) and off not in (
        OFF_SHIELD, WEAPON_SPIKED_GAUNTLET,
    ):
        off_weapon = OFF_NONE
    else:
        off_weapon = off

    armor_save = _armor_base_save(armor_name)
    if armor_code != ARMOR_NONE and config.get("house_rule_better_armour", False):
        armor_save -= 1
    if has_sea_dragon_cloak:
        armor_save = min(armor_save, 5)
    if off == OFF_SHIELD and not (_is_two_handed(main) or _is_paired(main)):
        armor_save -= 1
        if config.get("house_rule_useful_shields", False):
            armor_save -= 1
    if skills & SKILL_VERY_TOUGH:
        armor_save -= 1
    if skills & SKILL_SHAGGY_HIDE:
        armor_save -= 1
    natural_armour_save = config.get("natural_armour_save")
    natural_armour_save = int(natural_armour_save) if natural_armour_save else 7
    if config.get("natural_armour_stacks", False) and natural_armour_save <= 6:
        armor_save -= 7 - natural_armour_save
        natural_armour_save = 7

    base_strength = config["S"] + bool(skills & SKILL_IRON_SINEWS)
    base_wounds = config["W"] + bool(skills & SKILL_MONSTROUS)
    base_attacks = config["A"] + bool(skills & SKILL_RED_FURY)
    if skills & SKILL_UNARMED_ART and main in (WEAPON_UNARMED, WEAPON_ESHIN_CLAWS):
        base_attacks += 1

    return np.array(
        [
            config["WS"] + int(main == WEAPON_CATHAYAN_LONGSWORD),
            base_strength + bool(preparation & PREPARATION_CRIMSON_SHADE),
            config["T"] + bool(preparation & PREPARATION_MANDRAKE_ROOT),
            base_wounds,
            config["I"],
            base_attacks,
            main,
            off_weapon,
            armor_save,
            skills,
            int(has_helmet),
            int(bool(config.get("has_luck_amulet", False))),
            main_material,
            offhand_material,
            preparation,
            main_poison,
            offhand_poison,
            armor_code,
            int(bool(config.get("poison_immune", config.get("disease_immune", False)))),
            int(bool(config.get("house_rule_offhand_penalty", False))),
            int(bool(config.get("house_rule_dual_penalty", False))),
            int(bool(config.get("undead_or_possessed", False))),
            int(bool(config.get("house_rule_better_armour", False))),
            int(bool(config.get("house_rule_hard_armour", False))),
            int(bool(config.get("house_rule_useful_shields", False))),
            int(bool(config.get("frenzy", False))),
            natural_armour_save,
            int(bool(config.get("natural_armour_unmodified", False))),
            int(bool(config.get("concussion_immune", False))),
            int(bool(config.get("cloud_of_flies", False))),
            int(bool(config.get("charge_attack_bonus", False))),
            int(config.get("extra_natural_attacks", 0)),
            int(bool(config.get("perfect_killer", False))),
            int(bool(config.get("wight_blades", False))),
            int(bool(config.get("survivor", False))),
            int(bool(config.get("poisonous_injury", False))),
            int(bool(config.get("maddened_with_pain", False))),
            3 if skills & SKILL_TRUE_GRIT else int(config.get("injury_profile", 0)),
        ],
        dtype=np.int64,
    )


def effective_fighter_key(config):
    """Identify profiles equivalent under the current rules and equipment."""
    fighter = _make_fighter(config)
    main = int(fighter[6])
    off = int(fighter[7])
    skills = int(fighter[9])
    attack_weapons = {main}
    if off >= 0:
        attack_weapons.add(off)

    fencing_weapons = {WEAPON_SWORD, WEAPON_SCIMITAR}
    axe_weapons = {WEAPON_AXE, WEAPON_DWARF_AXE}
    tireless_weapons = {WEAPON_FLAIL, WEAPON_MORNING_STAR, WEAPON_CHOPPA}

    if not attack_weapons & fencing_weapons:
        skills &= ~SKILL_FENCER
    if not attack_weapons & axe_weapons:
        skills &= ~SKILL_AXE_EXPERT
    if main != WEAPON_AXE:
        skills &= ~SKILL_AXE_MASTER
    if config.get("off_hand") != "Shield":
        skills &= ~SKILL_SHIELD_STRIKE
    if not _is_two_handed(main):
        skills &= ~SKILL_STRONGMAN
    if not attack_weapons & tireless_weapons:
        skills &= ~SKILL_TIRELESS

    fighter[9] = skills
    return tuple(int(value) for value in fighter)


def _nb_to_hit(ha_att, ha_def):
    if ha_def == 0:
        return 2
    if ha_att > ha_def:
        return 3
    if ha_def > 2 * ha_att:
        return 5
    return 4


def _nb_to_wound(f_att, r_def):
    diff = f_att - r_def
    if diff >= 2:
        return 2
    if diff == 1:
        return 3
    if diff == 0:
        return 4
    if diff == -1:
        return 5
    if diff >= -3:
        return 6
    return 7


def _nb_armour_save(base_save, weapon):
    if weapon in (
        WEAPON_DAGGER, WEAPON_YAMBIYA, WEAPON_PIRATE_SCOURGE,
        WEAPON_PLAGUE_DAGGER, WEAPON_UNARMED, WEAPON_MISERICORDIA,
        WEAPON_STARBLADE,
    ):
        return min(6, base_save - 1)
    return base_save


def _is_two_handed(weapon):
    return weapon in (
        WEAPON_2H, WEAPON_FLAIL, WEAPON_HALBERD, WEAPON_SCYTHE,
        WEAPON_PIKE, WEAPON_ELVEN_2H, WEAPON_GREAT_SCIMITAR,
        WEAPON_BRAZIER_STAFF, WEAPON_WAR_MAUL, WEAPON_DOUBLE_BLADE,
        WEAPON_SERPENT_STAFF,
        WEAPON_KUSARA_KAMA, WEAPON_LONG_HOOK, WEAPON_BO, WEAPON_DRAICH,
        WEAPON_YARI_TWO, WEAPON_CENSER,
        WEAPON_BALL_AND_CHAIN,
        WEAPON_DRAGON_SWORD, WEAPON_CHAIN_STICKS, WEAPON_MAN_CATCHER,
        WEAPON_QUARTER_STAFF,
    )


def _is_paired(weapon):
    return weapon in (
        WEAPON_BAGH_NAKH, WEAPON_BRASS_KNUCKLES, WEAPON_ESHIN_CLAWS,
        WEAPON_WEEPING_BLADES,
        WEAPON_POISONED_DAGGERS,
    )


def _weapon_has_parry(weapon):
    return weapon in (
        WEAPON_SWORD, WEAPON_RAPIER, WEAPON_ELVEN_2H, WEAPON_CUTLASS,
        WEAPON_SCIMITAR, WEAPON_SWORD_BREAKER, WEAPON_DWARF_AXE,
        WEAPON_TRIDENT, WEAPON_SPIKED_GAUNTLET, WEAPON_ESHIN_CLAWS,
        WEAPON_WEEPING_BLADES, WEAPON_SERPENT_STAFF, WEAPON_WITCH_BLADE,
        WEAPON_BO, WEAPON_UNHOLY_SWORD, WEAPON_DRAICH,
        WEAPON_YARI_ONE, WEAPON_YARI_TWO,
        WEAPON_STARBLADE, WEAPON_STARSWORD, WEAPON_DRAGON_SWORD,
        WEAPON_CATHAYAN_LONGSWORD, WEAPON_QUARTER_STAFF,
    )


def _parry_profile(fighter):
    main = int(fighter[6])
    off = int(fighter[7])
    axe_master = bool(int(fighter[9]) & SKILL_AXE_MASTER)
    defensive = bool(int(fighter[9]) & SKILL_DEFENSIVE_STANCE)
    main_parry = _weapon_has_parry(main) or (axe_master and main == WEAPON_AXE) or defensive
    off_parry = _weapon_has_parry(off) or (axe_master and off == WEAPON_AXE)
    sources = int(main_parry) + int(off_parry)
    buckler = off == OFF_BUCKLER
    sources += int(buckler)
    if off == OFF_SHIELD and int(fighter[9]) & SKILL_SHIELD_MASTERY:
        sources += 1
    if main == WEAPON_DOUBLE_BLADE:
        return 2, False
    if main == WEAPON_ESHIN_CLAWS:
        return 1, True
    if main == WEAPON_STARBLADE:
        return 1, False
    paired_parry = main == WEAPON_WEEPING_BLADES
    # The errata explicitly disallow this re-roll when wielding two swords.
    # A buckler grants it only when paired with a normal sword.
    reroll = (buckler and main == WEAPON_SWORD) or bool(
        int(fighter[9]) & (SKILL_MINIATH | SKILL_SWORD_MASTER | SKILL_UNBEATABLE)
    )
    attempts = 1 if sources or paired_parry else 0
    if int(fighter[9]) & SKILL_UNBEATABLE and sources >= 2:
        attempts = 2
    return attempts, reroll


def _weapon_attacks_first(weapon):
    return weapon in (
        WEAPON_SPEAR, WEAPON_PIKE, WEAPON_ANKUS, WEAPON_TRIDENT,
        WEAPON_CHAINED_SQUIG, WEAPON_SQUIG_PROD, WEAPON_LONG_HOOK,
        WEAPON_YARI_TWO, WEAPON_SERPENT_STAFF,
    )


def _has_frenzy_preparation(fighter):
    return bool(
        int(fighter[14]) & (PREPARATION_MAD_CAP | PREPARATION_HEAD_SPLITTER)
    ) or bool(int(fighter[FIGHTER_FRENZY]))


def _random_candidate_charges(rng, total):
    """Choose the charging fighter in each duel; True denotes the candidate."""
    return rng.random(total) < 0.5


def _attack_count(fighter):
    count = int(fighter[5]) + (int(fighter[7]) >= 0)
    if int(fighter[7]) == OFF_SHIELD:
        count = int(fighter[5]) + bool(int(fighter[9]) & SKILL_SHIELD_STRIKE)
    if _is_paired(int(fighter[6])) or int(fighter[6]) == WEAPON_DOUBLE_BLADE:
        count += 1
    if int(fighter[6]) in (WEAPON_BO, WEAPON_STILETTO, WEAPON_QUARTER_STAFF):
        count += 1
    return count


def _whip_weapon_and_source(fighter):
    main = int(fighter[6])
    off = int(fighter[7])
    if main in WHIP_WEAPONS:
        return main, 0
    if off in WHIP_WEAPONS:
        return off, int(fighter[5])
    return OFF_NONE, -1


def _phase_attack_plan(fighter, first_round, frenzy_extra=0, include_whip=False):
    """Return the weapon, hand, and origin of each attack in the phase."""
    core_count = _phase_attack_count(fighter, first_round)
    weapons = []
    sources = []
    kinds = []
    for attack in range(core_count):
        source = _source_attack_index(fighter, attack)
        weapons.append(_phase_weapon_for_attack(fighter, source, first_round))
        sources.append(source)
        kinds.append("core")
    for _ in range(int(fighter[FIGHTER_EXTRA_NATURAL_ATTACKS])):
        weapons.append(WEAPON_NATURAL)
        sources.append(0)
        kinds.append("natural")
    if int(fighter[FIGHTER_CHARGE_ATTACK_BONUS]):
        weapons.append(int(fighter[6]))
        sources.append(0)
        kinds.append("charge_trait")
    if int(fighter[9]) & SKILL_CHARGE_EXTRA_ATTACK:
        weapons.append(int(fighter[6]))
        sources.append(0)
        kinds.append("charge_skill")
    for _ in range(frenzy_extra):
        weapons.append(int(fighter[6]))
        sources.append(0)
        kinds.append("frenzy")
    if int(fighter[FIGHTER_MADDENED_WITH_PAIN]):
        weapons.append(int(fighter[6]))
        sources.append(0)
        kinds.append("maddened")
    if int(fighter[9]) & SKILL_FEROCIOUS_CHARGE:
        for _ in range(int(fighter[5])):
            weapons.append(int(fighter[6]))
            sources.append(0)
            kinds.append("ferocious")
    whip, source = _whip_weapon_and_source(fighter)
    if include_whip and whip >= 0:
        weapons.append(whip)
        sources.append(source)
        kinds.append("whip")
    return weapons, sources, kinds


def _attack_is_last(fighter, weapon, source_index):
    material = _material_for_attack(fighter, source_index)
    if material == MATERIAL_OBSIDIAN:
        return True
    if (
        int(fighter[9]) & SKILL_STRONGMAN
        and weapon == int(fighter[6])
        and (_is_two_handed(weapon) or weapon == WEAPON_BROADSWORD)
    ):
        return False
    return weapon in (
        WEAPON_2H,
        WEAPON_ELVEN_2H,
        WEAPON_GREAT_SCIMITAR,
        WEAPON_WAR_MAUL,
        WEAPON_DRAICH,
        WEAPON_BROADSWORD,
    )


def _attack_priority_rows(
    fighter,
    weapon,
    source_index,
    first_round,
    charging,
    charged,
    whip_extra=False,
    stood=False,
):
    charging = np.asarray(charging, dtype=bool)
    charged = np.asarray(charged, dtype=bool)
    stood = np.asarray(stood, dtype=bool)
    shape = np.broadcast(charging, charged, stood).shape
    priority = np.full(shape, PRIORITY_NORMAL, dtype=np.int8)
    attacks_first = charging | (
        first_round and _weapon_attacks_first(weapon)
    )
    if int(fighter[9]) & SKILL_CAT_REFLEXES:
        attacks_first = attacks_first | charged
    if int(fighter[9]) & SKILL_ALWAYS_FIRST:
        attacks_first = np.ones(shape, dtype=bool)
    if whip_extra:
        attacks_first = attacks_first | charged
    priority[attacks_first] = PRIORITY_FIRST
    if _attack_is_last(fighter, weapon, source_index):
        priority[:] = PRIORITY_LAST
    priority[np.broadcast_to(stood, shape)] = PRIORITY_LAST
    return priority


def _stage_has_attacks(
    fighter, stage, first_round, charging, charged, stood, frenzy_active,
):
    charging = np.asarray(charging, dtype=bool)
    charged = np.asarray(charged, dtype=bool)
    stood = np.asarray(stood, dtype=bool)
    frenzy_active = np.asarray(frenzy_active, dtype=bool)
    shape = np.broadcast(charging, charged, stood, frenzy_active).shape
    has_attack = np.zeros(shape, dtype=bool)
    include_whip = bool(np.any(charging | charged))
    frenzy_extra = int(fighter[5]) if np.any(frenzy_active) else 0
    weapons, sources, kinds = _phase_attack_plan(
        fighter, first_round, frenzy_extra, include_whip
    )
    for weapon, source, kind in zip(weapons, sources, kinds):
        active = np.ones(shape, dtype=bool)
        if kind == "frenzy":
            active &= np.broadcast_to(frenzy_active, shape)
        elif kind == "ferocious":
            active &= np.broadcast_to(charging, shape)
        elif kind == "whip":
            active &= np.broadcast_to(charging | charged, shape)
        priority = _attack_priority_rows(
            fighter, weapon, source, first_round, charging, charged,
            kind == "whip", stood,
        )
        has_attack |= active & (priority == stage)
    return has_attack


def _source_attack_index(fighter, attack_index):
    """Resolve extra Frenzy attacks with the main weapon."""
    return attack_index if attack_index < _attack_count(fighter) else 0


def _weapon_for_attack(fighter, attack_index):
    if attack_index < int(fighter[5]):
        return int(fighter[6])
    if _is_paired(int(fighter[6])) or int(fighter[6]) in (
        WEAPON_DOUBLE_BLADE, WEAPON_BO, WEAPON_STILETTO,
    ):
        return int(fighter[6])
    offhand = int(fighter[7])
    if offhand == OFF_SHIELD and int(fighter[9]) & SKILL_SHIELD_STRIKE:
        return WEAPON_DAGGER
    if offhand >= 0:
        return offhand
    return WEAPON_SWORD


def _phase_attack_count(fighter, first_round, frenzy_extra=0):
    """Ajusta the weapons that only sirven during the primer asalto."""
    main = int(fighter[6])
    off = int(fighter[7])
    attacks = int(fighter[5])
    pistols = (WEAPON_PISTOL, WEAPON_DUELING_PISTOL)
    if main == WEAPON_CHAINED_SQUIG:
        count = attacks + 1 if off >= 0 else 1
    elif main == WEAPON_SERPENT_STAFF:
        count = 1
    elif main == WEAPON_VOMIT_ATTACK:
        count = 1
    elif main in pistols:
        if first_round:
            count = 2 if off in pistols else attacks + int(off >= 0)
            if off == OFF_NONE:
                count = 1
        else:
            count = attacks
    elif off in pistols:
        count = attacks + int(first_round)
    elif main == WEAPON_CHAIN_STICKS:
        count = attacks + (2 if first_round else 0)
    else:
        count = _attack_count(fighter)
    return count + frenzy_extra


def _phase_weapon_for_attack(fighter, attack_index, first_round):
    main = int(fighter[6])
    off = int(fighter[7])
    attacks = int(fighter[5])
    pistols = (WEAPON_PISTOL, WEAPON_DUELING_PISTOL)
    if main == WEAPON_CHAINED_SQUIG:
        return main if attack_index == 0 else (off if off >= 0 else WEAPON_DAGGER)
    if main in pistols:
        if not first_round:
            return off if off >= 0 and off not in pistols else WEAPON_DAGGER
        if off >= 0 and off not in pistols:
            return off if attack_index < attacks else main
        return main if attack_index == 0 else off
    if off in pistols and attack_index >= attacks:
        return off
    return _weapon_for_attack(fighter, attack_index)


def _material_for_attack(attacker, attack_index):
    if attack_index >= int(attacker[5]) and int(attacker[7]) >= 0:
        return int(attacker[13])
    return int(attacker[12])


def _poison_for_attack(attacker, attack_index):
    if _weapon_for_attack(attacker, attack_index) in (
        WEAPON_WEEPING_BLADES, WEAPON_POISONED_DAGGERS, WEAPON_SERPENT_WHIP,
    ):
        return POISON_BLACK_LOTUS
    if attack_index >= int(attacker[5]) and int(attacker[7]) >= 0:
        return int(attacker[16])
    return int(attacker[15])


def _house_rule_hit_penalty(attacker, attack_index):
    """Return the hit modifier from active house rules."""
    main = int(attacker[6])
    off = int(attacker[7])
    uses_offhand = attack_index >= int(attacker[5]) and off >= 0
    dual_wielding = off >= 0 or _is_paired(main)
    return int(bool(attacker[FIGHTER_OFFHAND_HIT_PENALTY]) and uses_offhand) + (
        int(bool(attacker[FIGHTER_DUAL_HIT_PENALTY]) and dual_wielding)
    )


def _strength_armour_penalty(attacker, strength):
    """Return the save penalty caused by the attacker's Strength."""
    threshold = 4 if int(attacker[FIGHTER_HARD_ARMOUR]) else 3
    return max(0, int(strength) - threshold)


def _attack_strength(attacker, weapon, defender_is_seasoned, first_round=True, attack_index=-1):
    strength = int(attacker[1])
    if int(attacker[9]) & SKILL_POWER:
        strength += 1
    tireless = bool(int(attacker[9]) & SKILL_TIRELESS)
    if weapon in (WEAPON_2H, WEAPON_ELVEN_2H, WEAPON_GREAT_SCIMITAR, WEAPON_WAR_MAUL):
        strength += 2
    elif weapon == WEAPON_BALL_AND_CHAIN:
        strength += 2
    elif weapon == WEAPON_FLAIL:
        strength += 2 if first_round or tireless else 0
    elif weapon in (WEAPON_MORNING_STAR, WEAPON_HALBERD, WEAPON_BRAZIER_STAFF, WEAPON_BRASS_KNUCKLES, WEAPON_BAGH_NAKH):
        strength += 1 if first_round or tireless or weapon not in (WEAPON_MORNING_STAR,) else 0
    elif weapon == WEAPON_SIGMARITE_HAMMER:
        strength += 1
    elif weapon == WEAPON_CHOPPA:
        strength += 1 if first_round or tireless else 0
    elif weapon == WEAPON_CHAINED_SQUIG:
        strength = 3
    elif weapon == WEAPON_SERPENT_STAFF:
        strength = 4
    elif weapon in (WEAPON_PISTOL, WEAPON_DUELING_PISTOL, WEAPON_SUN_GAUNTLET):
        strength = 4
    elif weapon == WEAPON_VOMIT_ATTACK:
        strength = 5
    elif weapon in (WEAPON_ANCESTRAL_CLAW,):
        strength += 1
    elif weapon in (WEAPON_STARSWORD, WEAPON_BROADSWORD, WEAPON_DRAGON_SWORD):
        strength += 1
    elif weapon in (WEAPON_DRAICH,):
        strength += 2
    elif weapon in (WEAPON_DEATH_KNIFE, WEAPON_STILETTO, WEAPON_LONG_HOOK):
        strength -= 1
    elif weapon == WEAPON_CENSER:
        strength += 2 if first_round else 0
    elif weapon == WEAPON_WITCH_BLADE:
        strength += 1 if first_round else 0
    elif weapon == WEAPON_RAPIER:
        strength -= 1
    elif weapon == WEAPON_UNARMED:
        strength -= 1
    material = int(attacker[12]) if attack_index < 0 else _material_for_attack(attacker, attack_index)
    if material == MATERIAL_OBSIDIAN:
        strength += 1
    poison = _poison_for_attack(attacker, attack_index)
    if poison in (POISON_BLACK_VENOM, POISON_REPTILE):
        strength += 1
    if defender_is_seasoned:
        strength = max(1, strength - 1)
    return strength


def _armour_strength(attacker, weapon, first_round=True, attack_index=-1):
    strength = _attack_strength(attacker, weapon, False, first_round, attack_index)
    if _poison_for_attack(attacker, attack_index) == POISON_REPTILE:
        strength -= 1
    return strength


def _extra_armour_penalty(attacker, weapon, attack_index=-1):
    penalty = 0
    if weapon in (WEAPON_AXE, WEAPON_KATAR, WEAPON_SCYTHE, WEAPON_SCIMITAR,
                  WEAPON_GREAT_SCIMITAR, WEAPON_BAGH_NAKH, WEAPON_WAR_MAUL,
                  WEAPON_DWARF_AXE, WEAPON_CHOPPA,
                  WEAPON_KUSARA_KAMA, WEAPON_CATHAYAN_LONGSWORD):
        penalty += 1
    if weapon in (WEAPON_PISTOL, WEAPON_DUELING_PISTOL):
        penalty += 2
    material = int(attacker[12]) if attack_index < 0 else _material_for_attack(attacker, attack_index)
    if material == MATERIAL_GROMRIL:
        penalty += 1
    return penalty






def _can_parry(attacker_strength, defender_basic_strength):
    return attacker_strength < 2 * defender_basic_strength


def _melee_special_save_target(fighter):
    skills = int(fighter[9])
    if skills & SKILL_ELVEN_AGILITY:
        return 4 if skills & SKILL_SIDESTEP else 6
    if skills & SKILL_SIDESTEP:
        return 5
    if skills & SKILL_VAMPIRE_REFLEXES:
        return 6
    return 7


def _should_sweep(attacker, defender, attack_count):
    if not (int(attacker[9]) & SKILL_SWEEP) or not _is_two_handed(int(attacker[6])):
        return False
    fail_chance = max(1, 6 - int(defender[4])) / 6.0
    normal_hit_chance = (7 - _nb_to_hit(int(attacker[0]), int(defender[0]))) / 6.0
    return fail_chance > min(1.0, attack_count * normal_hit_chance)




def _combat_initiative(fighter, crimson_bonus=0, first_round=False):
    has_ithilmar = int(fighter[12]) == MATERIAL_ITHILMAR or (
        int(fighter[7]) >= 0 and int(fighter[13]) == MATERIAL_ITHILMAR
    )
    initiative = int(fighter[4]) + has_ithilmar + crimson_bonus
    if int(fighter[6]) in (WEAPON_CATHAYAN_LONGSWORD, WEAPON_QUARTER_STAFF):
        initiative += 1
    if int(fighter[6]) in (WEAPON_BRASS_KNUCKLES, WEAPON_WAR_MAUL):
        initiative -= 2 if int(fighter[6]) == WEAPON_BRASS_KNUCKLES else 1
    if int(fighter[6]) == WEAPON_POISONED_DAGGERS:
        initiative += 1
    if int(fighter[6]) == WEAPON_CHAINED_SQUIG and not first_round:
        initiative = 3
    return initiative




def _simulate_batch(
    candidate, enemies, enemy_indices, total_sims, seed, cancel_event=None,
):
    """Simulate a batch of homogeneous variants with NumPy arrays."""
    rng = np.random.default_rng(seed)
    wins = 0
    resolved = 0
    selected = np.asarray(enemy_indices[:total_sims], dtype=np.int64)
    counts = np.bincount(selected, minlength=len(enemies))
    active = np.flatnonzero(counts)
    unique_enemies, inverse = np.unique(enemies[active], axis=0, return_inverse=True)
    grouped_counts = np.zeros(len(unique_enemies), dtype=np.int64)
    np.add.at(grouped_counts, inverse, counts[active])
    for enemy, amount in zip(unique_enemies, grouped_counts):
        _raise_if_cancelled(cancel_event)
        remaining = int(amount)
        while remaining:
            _raise_if_cancelled(cancel_event)
            chunk = min(remaining, SIMULATION_CHUNK_SIZE)
            if _can_use_native_kernel(candidate, enemy):
                native_seed = int(rng.bit_generator.random_raw())
                batch_wins, batch_resolved = _simulate_simple_native(
                    candidate, enemy, chunk, native_seed
                )
            else:
                batch_wins, batch_resolved = _simulate_homogeneous_batch(
                    candidate, enemy, chunk, rng, cancel_event
                )
            wins += batch_wins
            resolved += batch_resolved
            remaining -= chunk
    return wins, resolved


def _fighter_uses_weapon(fighter, *weapons):
    return int(fighter[6]) in weapons or int(fighter[7]) in weapons


def _can_use_native_kernel(candidate, enemy):
    if _simulate_simple_native is None:
        return False
    simple_main = {
        WEAPON_SWORD, WEAPON_MACE, WEAPON_DAGGER, WEAPON_2H, WEAPON_AXE,
        WEAPON_FLAIL, WEAPON_MORNING_STAR, WEAPON_HALBERD, WEAPON_SPEAR,
    }
    simple_off = {
        OFF_NONE, OFF_SHIELD, OFF_BUCKLER,
        WEAPON_SWORD, WEAPON_MACE, WEAPON_DAGGER, WEAPON_AXE,
    }
    special_armour = {ARMOR_ESHIN_ROBES, ARMOR_CHITIN}
    for fighter in (candidate, enemy):
        if int(fighter[6]) not in simple_main or int(fighter[7]) not in simple_off:
            return False
        if int(fighter[5]) + int(int(fighter[7]) >= 0) > 31:
            return False
        if int(fighter[9]) or int(fighter[10]) or int(fighter[11]):
            return False
        if int(fighter[12]) != MATERIAL_NORMAL or int(fighter[13]) != MATERIAL_NORMAL:
            return False
        if int(fighter[14]) != PREPARATION_NONE:
            return False
        if int(fighter[15]) != POISON_NONE or int(fighter[16]) != POISON_NONE:
            return False
        if int(fighter[17]) in special_armour:
            return False
        if any(int(fighter[index]) for index in (
            FIGHTER_OFFHAND_HIT_PENALTY, FIGHTER_DUAL_HIT_PENALTY,
            FIGHTER_BETTER_ARMOUR, FIGHTER_HARD_ARMOUR, FIGHTER_USEFUL_SHIELDS,
            FIGHTER_FRENZY, FIGHTER_NATURAL_ARMOUR_UNMODIFIED,
            FIGHTER_CONCUSSION_IMMUNE,
            FIGHTER_CLOUD_OF_FLIES, FIGHTER_CHARGE_ATTACK_BONUS,
            FIGHTER_EXTRA_NATURAL_ATTACKS, FIGHTER_PERFECT_KILLER,
            FIGHTER_WIGHT_BLADES, FIGHTER_SURVIVOR,
            FIGHTER_POISONOUS_INJURY,
            FIGHTER_MADDENED_WITH_PAIN, FIGHTER_INJURY_PROFILE,
        )):
            return False
        if int(fighter[FIGHTER_NATURAL_ARMOUR_SAVE]) <= 6:
            return False
    return True


def _vector_injury(
    rng, count, weapon, helmet, spring_up, mandrake, dark_steel, modifier,
    wicked_edge=False, concussion_immune=False, poisonous=False,
    injury_profile=0, no_pain=False,
):
    rolls = np.minimum(6, rng.integers(1, 7, count) + modifier)
    if injury_profile == 2:
        states = np.full(count, STATE_OUT, dtype=np.int8)
    elif injury_profile == 3:
        states = np.where(rolls <= 3, STATE_KNOCKED_DOWN,
                          np.where(rolls <= 5, STATE_STUNNED, STATE_OUT))
    elif injury_profile == 1:
        states = np.where(rolls == 1, STATE_KNOCKED_DOWN,
                          np.where(rolls <= 3, STATE_STUNNED, STATE_OUT))
    elif poisonous:
        states = np.where(rolls == 1, STATE_KNOCKED_DOWN,
                          np.where(rolls <= 4, STATE_STUNNED, STATE_OUT))
    elif not concussion_immune and weapon in (
        WEAPON_MACE, WEAPON_STONE_AXE, WEAPON_ANKUS, WEAPON_SIGMARITE_HAMMER,
        WEAPON_DRAICH,
    ):
        states = np.where(rolls == 1, STATE_KNOCKED_DOWN,
                          np.where(rolls <= 4, STATE_STUNNED, STATE_OUT))
    else:
        states = np.where(rolls <= 2, STATE_KNOCKED_DOWN,
                          np.where(rolls <= 4, STATE_STUNNED, STATE_OUT))
    if dark_steel or wicked_edge:
        states = np.where((rolls >= 2) & (rolls <= 4), STATE_STUNNED, states)
    if mandrake:
        states[states == STATE_STUNNED] = STATE_KNOCKED_DOWN
    helmet_knockdown = np.zeros(count, dtype=bool)
    if helmet:
        helmet_knockdown = (
            (states == STATE_STUNNED) & (rng.integers(1, 7, count) >= 4)
        )
        states[helmet_knockdown] = STATE_KNOCKED_DOWN
    if spring_up:
        states[(states == STATE_KNOCKED_DOWN) & ~helmet_knockdown] = STATE_STANDING
    if no_pain:
        states[states == STATE_STUNNED] = STATE_KNOCKED_DOWN
    return states


def _vector_automatic_hit(rng, rows, defender, wounds, states, strength, weapon):
    """Apply an automatic hit from persistent effects."""
    if rows.size == 0:
        return

    alive = rows[states[rows] != STATE_OUT]
    if alive.size == 0:
        return
    wound_target = _nb_to_wound(strength, int(defender[2]))
    wounded = rng.integers(1, 7, alive.size) >= wound_target
    affected = alive[wounded]
    if affected.size == 0:
        return
    save_target = int(defender[8]) + max(0, strength - 3)
    if save_target <= 6:
        saved = rng.integers(1, 7, affected.size) >= save_target
        affected = affected[~saved]
    special_save = _melee_special_save_target(defender)
    if special_save <= 6 and affected.size:
        affected = affected[rng.integers(1, 7, affected.size) < special_save]
    if affected.size == 0:
        return
    damage = 2 if weapon == WEAPON_BRAZIER_STAFF and int(defender[17]) == ARMOR_CHITIN else 1
    for _ in range(damage):
        active = affected[states[affected] != STATE_OUT]
        if active.size == 0:
            break
        wounds[active] -= 1
        injured = active[wounds[active] <= 0]
        if injured.size:
            states[injured] = np.maximum(
                states[injured],
                _vector_injury(
                    rng, injured.size, weapon, bool(defender[10]),
                    bool(int(defender[9]) & SKILL_SPRING_UP),
                    bool(int(defender[14]) & PREPARATION_MANDRAKE_ROOT), False, 0,
                    no_pain=bool(int(defender[9]) & SKILL_IGNORE_PAIN),
                ),
            )


def _vector_cutlass_counterattack(rng, rows, attacker, defender, wounds, states):
    """Resolve the free punch granted by a successful cutlass parry."""
    if rows.size == 0:
        return
    hit = rng.integers(1, 7, rows.size) >= _nb_to_hit(int(defender[0]), int(attacker[0]))
    targets = rows[hit]
    if targets.size == 0:
        return
    strength = max(1, int(defender[1]) - 1)
    if int(attacker[9]) & SKILL_SEASONED:
        strength = max(1, strength - 1)
    wounded = rng.integers(1, 7, targets.size) >= _nb_to_wound(strength, int(attacker[2]))
    targets = targets[wounded]
    if targets.size == 0:
        return
    save_target = max(2, int(attacker[8]) - 1) + max(0, strength - 3)
    if save_target <= 6:
        targets = targets[rng.integers(1, 7, targets.size) < save_target]
    special_save = _melee_special_save_target(attacker)
    if special_save <= 6 and targets.size:
        targets = targets[rng.integers(1, 7, targets.size) < special_save]
    if targets.size:
        wounds[targets] -= 1
        injured = targets[wounds[targets] <= 0]
        if injured.size:
            states[injured] = np.maximum(
                states[injured],
                _vector_injury(
                    rng, injured.size, WEAPON_DAGGER, bool(attacker[10]),
                    bool(int(attacker[9]) & SKILL_SPRING_UP),
                    bool(int(attacker[14]) & PREPARATION_MANDRAKE_ROOT), False, 0,
                    no_pain=bool(int(attacker[9]) & SKILL_IGNORE_PAIN),
                ),
            )


def _vector_attack_phase(
    attacker, defender, indices, defender_wounds, defender_state,
    defender_amulet_used, rng, first_round, charging=False, charged=False,
    defender_initiative_penalty=None, attacker_frenzy=None,
    attacker_attack_penalty=None, defender_attack_penalty=None,
    defender_burning=None, defender_entangled=None,
    attacker_wounds=None, attacker_state=None, attacker_weapon_broken=None,
    priority_stage=None, attacker_stood=False, defender_parry_used=None,
):
    """Resolve one phase for many duels with identical fighters."""
    if indices.size == 0:
        return
    if attacker_weapon_broken is not None:
        broken = indices[attacker_weapon_broken[indices] >= 0]
        if broken.size:
            for broken_code in np.unique(attacker_weapon_broken[broken]):
                affected = broken[attacker_weapon_broken[broken] == broken_code]
                improvised = attacker.copy()
                if int(improvised[6]) == int(broken_code):
                    improvised[6] = WEAPON_DAGGER
                    if _is_paired(int(attacker[6])):
                        improvised[7] = OFF_NONE
                if int(improvised[7]) == int(broken_code):
                    improvised[7] = OFF_NONE
                _vector_attack_phase(
                    improvised, defender, affected, defender_wounds, defender_state,
                    defender_amulet_used, rng, first_round, charging, charged,
                    defender_initiative_penalty, attacker_frenzy,
                    attacker_attack_penalty, defender_attack_penalty,
                    defender_burning, defender_entangled,
                    attacker_wounds, attacker_state, None,
                    priority_stage, attacker_stood, defender_parry_used,
                )
            indices = indices[attacker_weapon_broken[indices] < 0]
            if indices.size == 0:
                return
    standing = defender_state[indices] == STATE_STANDING
    stunned = defender_state[indices] == STATE_STUNNED
    defender_state[indices[stunned]] = STATE_OUT
    rows = indices[
        standing
        | (defender_state[indices] == STATE_KNOCKED_DOWN)
        | (defender_state[indices] == STATE_PARALYZED)
    ]
    if rows.size == 0:
        return
    if (
        int(attacker[6]) == WEAPON_CENSER
        and attacker_wounds is not None and attacker_state is not None
    ):
        backlash = rng.integers(1, 7, rows.size) == 6
        affected = rows[backlash]
        attacker_wounds[affected] -= 1
        injured = affected[attacker_wounds[affected] <= 0]
        if injured.size:
            attacker_state[injured] = np.maximum(
                attacker_state[injured],
                _vector_injury(
                    rng, injured.size, WEAPON_CENSER, bool(attacker[10]),
                    bool(int(attacker[9]) & SKILL_SPRING_UP),
                    bool(int(attacker[14]) & PREPARATION_MANDRAKE_ROOT), False, 0,
                    no_pain=bool(int(attacker[9]) & SKILL_IGNORE_PAIN),
                ),
            )
        rows = rows[attacker_state[rows] == STATE_STANDING]
        if rows.size == 0:
            return

    charging_rows = (
        np.asarray(charging, dtype=bool)[rows]
        if isinstance(charging, np.ndarray)
        else np.full(rows.size, bool(charging), dtype=bool)
    )
    charged_rows = (
        np.asarray(charged, dtype=bool)[rows]
        if isinstance(charged, np.ndarray)
        else np.full(rows.size, bool(charged), dtype=bool)
    )
    stood_rows = (
        np.asarray(attacker_stood, dtype=bool)[rows]
        if isinstance(attacker_stood, np.ndarray)
        else np.full(rows.size, bool(attacker_stood), dtype=bool)
    )

    automatic = np.isin(defender_state[rows], (STATE_KNOCKED_DOWN, STATE_PARALYZED))
    knocked_down = defender_state[rows] == STATE_KNOCKED_DOWN
    started_vulnerable = automatic.copy()
    frenzy_rows = (
        attacker_frenzy[rows]
        if attacker_frenzy is not None
        else np.zeros(rows.size, dtype=bool)
    )
    frenzy_active = bool(np.any(frenzy_rows))
    frenzy_extra = int(attacker[5]) if frenzy_active else 0
    include_whip = bool(np.any(charging_rows | charged_rows))
    plan_weapons, plan_sources, plan_kinds = _phase_attack_plan(
        attacker, first_round, frenzy_extra, include_whip
    )
    base_attack_count = sum(kind != "frenzy" for kind in plan_kinds)
    attack_count = len(plan_weapons)
    sweep = _should_sweep(attacker, defender, base_attack_count)
    if sweep:
        base_attack_count = 1
        attack_count = 1
        automatic = (
            automatic | (rng.integers(1, 7, rows.size) > int(defender[4]))
        )
    capacity = attack_count + 12
    hit_rolls = np.zeros((rows.size, capacity), dtype=np.int8)
    hit_active = np.zeros((rows.size, capacity), dtype=bool)
    attack_enabled = np.ones((rows.size, capacity), dtype=bool)
    weapons = np.empty(capacity, dtype=np.int64)
    source_indices = np.zeros(capacity, dtype=np.int64)
    penalties = np.zeros(capacity, dtype=np.int8)

    hit_target = _nb_to_hit(int(attacker[0]), int(defender[0]))
    charge_hit_target = (
        _nb_to_hit(int(attacker[0]) + 1, int(defender[0]))
        if int(attacker[9]) & SKILL_UNSTOPPABLE else hit_target
    )
    for attack in range(attack_count):
        source_index = int(plan_sources[attack])
        weapon = int(plan_weapons[attack])
        weapons[attack] = weapon
        source_indices[attack] = source_index
        rolls = rng.integers(1, 7, rows.size)
        rolls[automatic] = 6
        if weapon == WEAPON_VOMIT_ATTACK:
            rolls[:] = 6
        reroll = np.zeros(rows.size, dtype=bool)
        house_penalty = _house_rule_hit_penalty(attacker, source_index)
        penalties[attack] = house_penalty
        adjusted_hit_target = min(6, hit_target + house_penalty)
        adjusted_charge_hit_target = min(6, charge_hit_target + house_penalty)
        if (
            int(attacker[9]) & SKILL_FENCER
            and weapon in (WEAPON_SWORD, WEAPON_SCIMITAR, WEAPON_WEEPING_BLADES)
        ):
            reroll = charging_rows & (
                rolls < np.where(charging_rows, adjusted_charge_hit_target, adjusted_hit_target)
            )
        if int(attacker[9]) & SKILL_AXE_EXPERT and weapon in (
            WEAPON_AXE, WEAPON_DWARF_AXE,
        ):
            reroll = charging_rows & (
                rolls < np.where(charging_rows, adjusted_charge_hit_target, adjusted_hit_target)
            )
        if int(attacker[9]) & SKILL_NORTHERN_WEAPONS and (
            weapon in (WEAPON_AXE, WEAPON_DWARF_AXE) or _is_two_handed(weapon)
        ):
            reroll |= rolls < np.where(
                charging_rows, adjusted_charge_hit_target, adjusted_hit_target
            )
        if int(attacker[9]) & SKILL_NORSE_BERSERK_CHARGE and (
            weapon in (WEAPON_AXE, WEAPON_DWARF_AXE) or _is_two_handed(weapon)
        ):
            reroll |= charging_rows & (
                rolls < np.where(charging_rows, adjusted_charge_hit_target, adjusted_hit_target)
            )
        if int(attacker[9]) & SKILL_REROLL_HITS:
            reroll |= rolls < np.where(
                charging_rows, adjusted_charge_hit_target, adjusted_hit_target
            )
        if first_round and int(attacker[9]) & SKILL_HATRED:
            reroll |= rolls < np.where(
                charging_rows, adjusted_charge_hit_target, adjusted_hit_target
            )
        if (
            first_round and int(attacker[9]) & SKILL_PISTOL_CRACK_SHOT
            and weapon in (WEAPON_PISTOL, WEAPON_DUELING_PISTOL)
        ):
            reroll |= rolls < np.where(
                charging_rows, adjusted_charge_hit_target, adjusted_hit_target
            )
        if int(attacker[9]) & SKILL_CHARGE_REROLL:
            reroll |= charging_rows & (
                rolls < np.where(
                    charging_rows, adjusted_charge_hit_target, adjusted_hit_target
                )
            )
        if first_round and int(attacker[9]) & SKILL_DUELLIST:
            reroll |= rolls < np.where(
                charging_rows, adjusted_charge_hit_target, adjusted_hit_target
            )
        if first_round and attack == 0 and int(attacker[9]) & SKILL_LUCK:
            reroll |= rolls < np.where(
                charging_rows, adjusted_charge_hit_target, adjusted_hit_target
            )
        rolls[reroll] = rng.integers(1, 7, int(reroll.sum()))
        hit_rolls[:, attack] = rolls
        current_hit_target = np.where(charging_rows, charge_hit_target, hit_target)
        if int(attacker[9]) & SKILL_KNIFE_FIGHT and weapon in (
            WEAPON_DAGGER, WEAPON_YAMBIYA,
        ):
            current_hit_target[:] = _nb_to_hit(int(attacker[0]) + 1, int(defender[0]))
        if int(attacker[9]) & SKILL_FEROCIOUS_CHARGE:
            current_hit_target = current_hit_target + charging_rows
        if first_round and int(defender[9]) & SKILL_BATTLE_ROAR:
            current_hit_target = current_hit_target + 1
        if int(attacker[9]) & SKILL_BERSERKER_HIT:
            current_hit_target = current_hit_target - charging_rows
        if (
            int(defender[9]) & SKILL_FOUL_ODOUR
            and not int(attacker[FIGHTER_UNDEAD_OR_POSSESSED])
        ):
            current_hit_target = current_hit_target + 1
        if int(defender[FIGHTER_CLOUD_OF_FLIES]):
            current_hit_target = current_hit_target + 1
        if weapon == WEAPON_SERPENT_STAFF:
            current_hit_target[:] = _nb_to_hit(4, int(defender[0]))
        if weapon == WEAPON_DUELING_PISTOL:
            current_hit_target = np.maximum(2, current_hit_target - 1)
        if int(defender[6]) == WEAPON_BALL_AND_CHAIN:
            current_hit_target = np.minimum(6, current_hit_target + 1)
        current_hit_target = np.minimum(6, current_hit_target + house_penalty)
        hit_active[:, attack] = automatic if sweep else (
            automatic | (rolls >= current_hit_target) | (weapon == WEAPON_VOMIT_ATTACK)
        )
        if (
            first_round and int(defender[9]) & SKILL_SIGMAR_SIGNAL
            and int(attacker[FIGHTER_UNDEAD_OR_POSSESSED])
            and attack == 0 and attack_count > 1
        ):
            hit_active[:, attack] = False
            attack_enabled[:, attack] = False
        if plan_kinds[attack] == "frenzy":
            attack_enabled[~frenzy_rows, attack] = False
            hit_active[~frenzy_rows, attack] = False
        elif plan_kinds[attack] == "ferocious":
            attack_enabled[~charging_rows, attack] = False
            hit_active[~charging_rows, attack] = False
        elif plan_kinds[attack] == "whip":
            attack_enabled[~(charging_rows | charged_rows), attack] = False
            hit_active[~(charging_rows | charged_rows), attack] = False
        elif plan_kinds[attack] == "charge_trait":
            attack_enabled[~charging_rows, attack] = False
            hit_active[~charging_rows, attack] = False
        elif plan_kinds[attack] == "charge_skill":
            attack_enabled[~charging_rows, attack] = False
            hit_active[~charging_rows, attack] = False
        elif plan_kinds[attack] == "maddened":
            active = (
                attacker_wounds[rows] < int(attacker[3])
                if attacker_wounds is not None
                else np.zeros(rows.size, dtype=bool)
            )
            attack_enabled[~active, attack] = False
            hit_active[~active, attack] = False
        if priority_stage is not None:
            priority = _attack_priority_rows(
                attacker, weapon, source_index, first_round,
                charging_rows, charged_rows,
                plan_kinds[attack] == "whip", stood_rows,
            )
            attack_enabled[priority != priority_stage, attack] = False
            hit_active[priority != priority_stage, attack] = False
        if attacker_attack_penalty is not None and attack == attack_count - 1:
            attack_enabled[attacker_attack_penalty[rows] > 0, attack] = False
            hit_active[attacker_attack_penalty[rows] > 0, attack] = False

    parry_attempts, reroll_failed_parry = _parry_profile(defender)
    blocks_parry = int(attacker[6]) in (
        WEAPON_WAR_MAUL, WEAPON_CHAINED_SQUIG,
    )
    if parry_attempts and not blocks_parry and not int(attacker[9]) & SKILL_UNPARRYABLE:
        any_parried = np.zeros(rows.size, dtype=bool)
        parried_weapon = np.full(rows.size, OFF_NONE, dtype=np.int16)
        eligible = hit_active[:, :attack_count].copy()
        for attack in range(attack_count):
            source_index = int(source_indices[attack])
            if int(weapons[attack]) in (
                WEAPON_STEEL_WHIP, WEAPON_PIRATE_SCOURGE,
                WEAPON_SERPENT_WHIP, WEAPON_BEASTMASTER_WHIP,
            ):
                eligible[:, attack] = False
                continue
            strength = _attack_strength(
                attacker, int(weapons[attack]), bool(int(defender[9]) & SKILL_SEASONED),
                first_round, source_index,
            )
            if not _can_parry(strength, int(defender[1])):
                eligible[:, attack] = False
        eligible[automatic] = False
        values = np.where(eligible, hit_rolls[:, :attack_count], 0)
        best = values.argmax(axis=1)
        best_roll = values[np.arange(rows.size), best]
        if defender_parry_used is not None:
            available = ~defender_parry_used[rows]
            best_roll = np.where(available, best_roll, 0)
            defender_parry_used[rows[best_roll > 0]] = True
        parry_rolls = rng.integers(1, 7, rows.size)
        if reroll_failed_parry:
            failed = (best_roll > 0) & (parry_rolls <= best_roll)
            parry_rolls[failed] = rng.integers(1, 7, int(failed.sum()))
        equal_parry = bool(
            int(defender[9]) & (
                SKILL_SWORD_MASTER | SKILL_UNBEATABLE | SKILL_DEFENSIVE_STANCE
            )
        )
        if int(defender[6]) == WEAPON_STARBLADE:
            parried = (best_roll > 0) & (parry_rolls >= 4)
        else:
            parried = (best_roll > 0) & (
                parry_rolls >= best_roll if equal_parry else parry_rolls > best_roll
            )
        any_parried |= parried
        parried_weapon[parried] = weapons[best[parried]]
        hit_active[np.arange(rows.size)[parried], best[parried]] = False
        if parry_attempts == 2:
            eligible[np.arange(rows.size), best] = False
            values = np.where(eligible, hit_rolls[:, :attack_count], 0)
            best = values.argmax(axis=1)
            best_roll = values[np.arange(rows.size), best]
            second_roll = rng.integers(1, 7, rows.size)
            parried = (best_roll > 0) & (
                second_roll >= best_roll if equal_parry else second_roll > best_roll
            )
            any_parried |= parried
            parried_weapon[parried] = weapons[best[parried]]
            hit_active[np.arange(rows.size)[parried], best[parried]] = False
        if any_parried.any():
            parry_rows = rows[any_parried]
            if int(defender[6]) == WEAPON_CUTLASS or int(defender[7]) == WEAPON_CUTLASS:
                if attacker_wounds is not None and attacker_state is not None:
                    _vector_cutlass_counterattack(
                        rng, parry_rows, attacker, defender, attacker_wounds, attacker_state
                    )
            if (
                attacker_weapon_broken is not None
                and (int(defender[6]) == WEAPON_SWORD_BREAKER
                     or int(defender[7]) == WEAPON_SWORD_BREAKER)
            ):
                breaks = rng.integers(1, 7, parry_rows.size) >= 4
                attacker_weapon_broken[parry_rows[breaks]] = parried_weapon[any_parried][breaks]

    if defender_burning is not None:
        brazier_hits = np.zeros(rows.size, dtype=bool)
        for attack in range(attack_count):
            if int(weapons[attack]) == WEAPON_BRAZIER_STAFF:
                brazier_hits |= hit_active[:, attack]
        ignited = brazier_hits & (rng.integers(1, 7, rows.size) >= 4)
        defender_burning[rows[ignited]] = True
    if defender_entangled is not None:
        squig_hits = np.zeros(rows.size, dtype=bool)
        for attack in range(attack_count):
            if int(weapons[attack]) == WEAPON_CHAINED_SQUIG:
                squig_hits |= hit_active[:, attack]
        defender_entangled[rows[squig_hits]] = True
    if defender_attack_penalty is not None:
        hampered = np.zeros(rows.size, dtype=bool)
        for attack in range(attack_count):
            if int(weapons[attack]) == WEAPON_KUSARA_KAMA:
                hampered |= hit_active[:, attack] & (hit_rolls[:, attack] >= 5)
        defender_attack_penalty[rows[hampered]] = 1

    queued = attack_count
    attack = 0
    critical_used = np.zeros(rows.size, dtype=bool)
    while attack < queued:
        current_states = defender_state[rows]
        # A fighter knocked down during this phase cannot be finished off,
        # with the attacks that le quedaban to the same atacante. the that ya estaban
        # Fighters knocked down or paralysed at the start remain valid targets.
        local = hit_active[:, attack] & (
            (current_states == STATE_STANDING)
            | (current_states == STATE_PARALYZED)
            | (
                started_vulnerable
                & (current_states == STATE_KNOCKED_DOWN)
            )
        )
        if not local.any():
            attack += 1
            continue
        targets = np.flatnonzero(local)
        global_rows = rows[targets]
        amulet = bool(int(defender[11])) & ~defender_amulet_used[global_rows]
        if np.any(amulet):
            defender_amulet_used[global_rows[amulet]] = True
            ignored = rng.integers(1, 7, int(np.sum(amulet))) >= 4
            local_targets = targets[amulet][ignored]
            hit_active[local_targets, attack] = False
            targets = np.flatnonzero(hit_active[:, attack] & (defender_state[rows] != STATE_OUT))
            global_rows = rows[targets]
        if targets.size == 0:
            attack += 1
            continue

        weapon = int(weapons[attack])
        source_index = int(source_indices[attack])
        poison = _poison_for_attack(attacker, source_index)
        poison_immune = bool(int(defender[18])) or bool(
            int(defender[14]) & PREPARATION_SHALLAYA_TEARS
        )
        if poison_immune:
            poison = POISON_NONE
        if poison == POISON_SPIDER_SPIT:
            paralyzed = rng.integers(1, 7, targets.size) > int(defender[2])
            defender_state[global_rows[paralyzed]] = STATE_PARALYZED
            if paralyzed.any() and attack + 1 < attack_count:
                local_rows = targets[paralyzed]
                hit_active[local_rows, attack + 1:attack_count] = attack_enabled[
                    local_rows, attack + 1:attack_count
                ]
                hit_rolls[local_rows, attack + 1:attack_count] = 6
        special_wound = np.zeros(targets.size, dtype=bool)
        if weapon == WEAPON_PLAGUE_DAGGER and not int(defender[18]):
            natural_six = hit_rolls[targets, attack] == 6
            special_wound = natural_six & (
                rng.integers(1, 7, targets.size) > int(defender[2])
            )
        elif weapon == WEAPON_CENSER and not int(defender[18]):
            special_wound = rng.integers(1, 7, targets.size) > int(defender[2])
        if special_wound.any():
            affected = global_rows[special_wound]
            defender_wounds[affected] -= 1
            injured = affected[defender_wounds[affected] <= 0]
            if injured.size:
                defender_state[injured] = _vector_injury(
                    rng, injured.size, weapon, bool(defender[10]),
                    bool(int(defender[9]) & SKILL_SPRING_UP),
                    bool(int(defender[14]) & PREPARATION_MANDRAKE_ROOT),
                    False, int(weapon == WEAPON_PLAGUE_DAGGER),
                    no_pain=bool(int(defender[9]) & SKILL_IGNORE_PAIN),
                )
        strength = _attack_strength(
            attacker, weapon, bool(int(defender[9]) & SKILL_SEASONED),
            first_round, source_index
        )
        if (
            poison_immune
            and _poison_for_attack(attacker, source_index) in (POISON_BLACK_VENOM, POISON_REPTILE)
        ):
            strength -= 1
        wound_target = np.full(
            targets.size, _nb_to_wound(strength, int(defender[2])), dtype=np.int8
        )
        if int(attacker[9]) & SKILL_CHARGE_STRENGTH:
            charging_targets = charging_rows[targets]
            wound_target[charging_targets] = _nb_to_wound(
                strength + 1, int(defender[2])
            )
        if weapon == WEAPON_LANCE:
            wound_target[charging_rows[targets]] = _nb_to_wound(
                strength + 2, int(defender[2])
            )
        if int(attacker[9]) & SKILL_MONSTER_SLAYER:
            wound_target = np.minimum(4, wound_target)
        lotus = np.zeros(targets.size, dtype=bool)
        if poison == POISON_BLACK_LOTUS:
            lotus = hit_rolls[targets, attack] == 6
        wight_blade = bool(int(attacker[FIGHTER_WIGHT_BLADES])) & (
            hit_rolls[targets, attack] == 6
        )
        if np.all(wound_target > 6) and not lotus.any():
            attack += 1
            continue
        wound_rolls = rng.integers(1, 7, targets.size)
        effective = wound_rolls + bool(int(attacker[9]) & SKILL_EXPERT)
        if poison == POISON_MANBANE:
            effective += 1
            effective[wound_rolls == 1] = 0
        if weapon == WEAPON_SIGMARITE_HAMMER and int(
            defender[FIGHTER_UNDEAD_OR_POSSESSED]
        ):
            effective += 1
        wounded = (effective >= wound_target) | lotus | wight_blade
        rerolled = np.zeros(targets.size, dtype=bool)
        if poison == POISON_DEVIL_TOXIN:
            failed = ~wounded
            if failed.any():
                wound_rolls[failed] = rng.integers(1, 7, int(failed.sum()))
                effective[failed] = wound_rolls[failed] + bool(int(attacker[9]) & SKILL_EXPERT)
                wounded[failed] = effective[failed] >= wound_target[failed]
                rerolled[failed] = True
        elif int(attacker[9]) & SKILL_REROLL_WOUNDS:
            failed = ~wounded
            if failed.any():
                wound_rolls[failed] = rng.integers(1, 7, int(failed.sum()))
                effective[failed] = wound_rolls[failed] + bool(
                    int(attacker[9]) & SKILL_EXPERT
                )
                wounded[failed] = effective[failed] >= wound_target[failed]
                rerolled[failed] = True
        if weapon == WEAPON_RAPIER and queued < capacity:
            failed = targets[~wounded]
            if failed.size:
                penalty = int(penalties[attack]) + 1
                extra = rng.integers(1, 7, failed.size)
                rapier_target = np.where(
                    charging_rows[failed], charge_hit_target, hit_target
                ) + penalty
                if int(defender[6]) == WEAPON_BALL_AND_CHAIN:
                    rapier_target += 1
                rapier_target = np.minimum(6, rapier_target)
                automatic_extra = (
                    defender_state[rows[failed]] == STATE_PARALYZED
                )
                extra[automatic_extra] = 6
                made = automatic_extra | (extra == 6) | (extra >= rapier_target)
                if made.any():
                    hit_rolls[failed[made], queued] = extra[made]
                    hit_active[failed[made], queued] = True
                    weapons[queued] = WEAPON_RAPIER
                    source_indices[queued] = source_index
                    penalties[queued] = penalty
                    queued += 1
        targets = targets[wounded]
        wound_rolls = wound_rolls[wounded]
        wound_target = wound_target[wounded]
        rerolled = rerolled[wounded]
        lotus = lotus[wounded]
        if targets.size == 0:
            attack += 1
            continue
        global_rows = rows[targets]

        critical_needed = 5 if poison == POISON_WOLFSBANE else 6
        if (
            int(attacker[9]) & SKILL_ART_OF_SILENT_DEATH
            and weapon in (WEAPON_UNARMED, WEAPON_NATURAL)
        ):
            critical_needed = 5
        critical = (
            (wound_rolls >= critical_needed) & (lotus | (wound_target < 6))
            & ~critical_used[targets] & ~rerolled
        )
        if int(defender[9]) & SKILL_CRITICAL_RESISTANCE and critical.any():
            ignored = rng.integers(1, 7, int(critical.sum())) >= 5
            critical[np.flatnonzero(critical)[ignored]] = False
        critical_used[targets[critical]] = True
        damage = np.ones(targets.size, dtype=np.int8)
        ignore_armour = np.full(
            targets.size,
            weapon in (
                WEAPON_SUN_GAUNTLET, WEAPON_ANCESTRAL_CLAW, WEAPON_DEATH_KNIFE,
                WEAPON_STARSWORD,
                WEAPON_VOMIT_ATTACK,
            ),
            dtype=bool,
        )
        injury_modifier = np.full(
            targets.size,
            int(weapon == WEAPON_DEATH_KNIFE)
            + int(bool(int(attacker[9]) & SKILL_STRIKE_TO_INJURE))
            + int(bool(int(attacker[9]) & SKILL_KNIFE_FIGHT)
                  and weapon in (WEAPON_DAGGER, WEAPON_YAMBIYA)),
            dtype=np.int8,
        )
        if critical.any():
            rolls = rng.integers(1, 7, int(critical.sum()))
            if int(attacker[9]) & SKILL_CHARGE:
                rolls = np.minimum(6, rolls + 1)
            if weapon == WEAPON_DRAICH:
                rolls = np.minimum(6, rolls + 1)
            if _material_for_attack(attacker, source_index) == MATERIAL_DARK_STEEL:
                rolls = np.minimum(6, rolls + 1)
            if _material_for_attack(attacker, source_index) == MATERIAL_DARK_ELF_BLADE:
                rolls = np.minimum(6, rolls + 1)
            damage[critical] = 2
            ignore_armour[critical] = rolls >= 3
            injury_modifier[critical] += np.where(rolls >= 5, 2, 0)
        if weapon == WEAPON_BALL_AND_CHAIN:
            damage = np.maximum(damage, rng.integers(1, 4, targets.size))
            ignore_armour[:] = True
        if weapon == WEAPON_BRAZIER_STAFF and int(defender[17]) == ARMOR_CHITIN:
            damage *= 2

        armour_strength = _armour_strength(attacker, weapon, first_round, source_index)
        if (
            poison_immune
            and _poison_for_attack(attacker, source_index) == POISON_BLACK_VENOM
        ):
            armour_strength -= 1
        save_target_value = (
            _nb_armour_save(int(defender[8]), weapon)
            + _strength_armour_penalty(attacker, armour_strength)
            + _extra_armour_penalty(attacker, weapon, source_index)
            + int(bool(attacker[FIGHTER_PERFECT_KILLER]))
        )
        save_target = np.full(targets.size, save_target_value, dtype=np.int8)
        charge_penetration_threshold = (
            4 if int(attacker[FIGHTER_HARD_ARMOUR]) else 3
        )
        if (
            int(attacker[9]) & SKILL_CHARGE_STRENGTH
            and armour_strength >= charge_penetration_threshold
        ):
            save_target[charging_rows[targets]] += 1
        if weapon == WEAPON_LANCE:
            lance_penalty = (
                _strength_armour_penalty(attacker, armour_strength + 2)
                - _strength_armour_penalty(attacker, armour_strength)
            )
            save_target[charging_rows[targets]] += lance_penalty
        natural_save = int(defender[FIGHTER_NATURAL_ARMOUR_SAVE])
        if natural_save <= 6:
            natural_target = np.full(targets.size, natural_save, dtype=np.int8)
            if not int(defender[FIGHTER_NATURAL_ARMOUR_UNMODIFIED]):
                natural_target[:] = (
                    _nb_armour_save(natural_save, weapon)
                    + _strength_armour_penalty(attacker, armour_strength)
                    + _extra_armour_penalty(attacker, weapon, source_index)
                )
                if weapon == WEAPON_LANCE:
                    natural_target[charging_rows[targets]] += lance_penalty
            save_target = np.minimum(save_target, natural_target)
        saved = np.zeros(targets.size, dtype=bool)
        can_save = ~ignore_armour & (save_target <= 6)
        saved[can_save] = (
            rng.integers(1, 7, int(can_save.sum())) >= save_target[can_save]
        )
        if int(defender[17]) == ARMOR_ESHIN_ROBES:
            reroll_save = can_save & ~saved
            saved[reroll_save] = (
                rng.integers(1, 7, int(reroll_save.sum()))
                >= save_target[reroll_save]
            )
        targets = targets[~saved]
        damage = damage[~saved]
        injury_modifier = injury_modifier[~saved]
        global_rows = rows[targets]
        if targets.size == 0:
            attack += 1
            continue
        if poison == POISON_BLOODROOT:
            damage *= 2
        dodge_target = _melee_special_save_target(defender)
        if dodge_target <= 6:
            dodged = rng.integers(1, 7, targets.size) >= dodge_target
            targets = targets[~dodged]
            damage = damage[~dodged]
            injury_modifier = injury_modifier[~dodged]
            global_rows = rows[targets]
        if targets.size == 0:
            attack += 1
            continue

        if int(defender[9]) & SKILL_REGENERATION and weapon != WEAPON_BRAZIER_STAFF:
            regenerated = rng.integers(1, 7, targets.size) >= 4
            targets = targets[~regenerated]
            damage = damage[~regenerated]
            injury_modifier = injury_modifier[~regenerated]
            global_rows = rows[targets]
        if targets.size == 0:
            attack += 1
            continue

        if (
            poison == POISON_NIGHTSHADE
            and defender_initiative_penalty is not None
            and targets.size
        ):
            defender_initiative_penalty[global_rows] += 1
        auto_rows = global_rows[knocked_down[targets]]
        defender_state[auto_rows] = STATE_OUT
        normal = ~knocked_down[targets]
        for amount in (1, 2, 3, 4):
            for modifier in (0, 1, 2, 3, 4):
                group = normal & (damage == amount) & (injury_modifier == modifier)
                affected = global_rows[group]
                for _ in range(amount):
                    alive = affected[defender_state[affected] != STATE_OUT]
                    if alive.size == 0:
                        break
                    defender_wounds[alive] -= 1
                    injured = alive[defender_wounds[alive] <= 0]
                    if injured.size:
                        injury = _vector_injury(
                            rng, injured.size, weapon, bool(defender[10]),
                            bool(int(defender[9]) & SKILL_SPRING_UP),
                            bool(int(defender[14]) & PREPARATION_MANDRAKE_ROOT),
                            _material_for_attack(attacker, source_index) == MATERIAL_DARK_STEEL,
                            modifier,
                            _material_for_attack(attacker, source_index) == MATERIAL_DARK_ELF_BLADE,
                            bool(int(defender[FIGHTER_CONCUSSION_IMMUNE])),
                            bool(int(attacker[FIGHTER_POISONOUS_INJURY])),
                            int(defender[FIGHTER_INJURY_PROFILE]),
                            no_pain=bool(int(defender[9]) & SKILL_IGNORE_PAIN),
                        )
                        if int(attacker[9]) & SKILL_HEAD_CRUSHER:
                            injury[injury == STATE_KNOCKED_DOWN] = STATE_STUNNED
                        if int(defender[9]) & SKILL_HARDENED_SKIN:
                            out = injury == STATE_OUT
                            downgrade = out & (
                                rng.integers(1, 7, injury.size) <= 3
                            )
                            injury[downgrade] = STATE_STUNNED
                        if int(defender[9]) & SKILL_STONE_SKULL:
                            stunned = injury == STATE_STUNNED
                            threshold = 2 if bool(defender[10]) else 3
                            recovered = stunned & (
                                rng.integers(1, 7, injury.size) >= threshold
                            )
                            injury[recovered] = STATE_KNOCKED_DOWN
                        if int(defender[FIGHTER_SURVIVOR]):
                            protected = (
                                defender_state[injured] == STATE_STANDING
                            ) & (injury == STATE_OUT)
                            injury[protected] = STATE_STUNNED
                        defender_state[injured] = np.maximum(
                            defender_state[injured], injury
                        )
        attack += 1


def _simulate_homogeneous_batch(candidate, enemy, total, rng, cancel_event=None):
    wounds1 = np.full(total, int(candidate[3]), dtype=np.int16)
    wounds2 = np.full(total, int(enemy[3]), dtype=np.int16)
    state1 = np.zeros(total, dtype=np.int8)
    state2 = np.zeros(total, dtype=np.int8)
    amulet1 = np.zeros(total, dtype=bool)
    amulet2 = np.zeros(total, dtype=bool)
    crimson1 = (
        rng.integers(1, 4, total)
        if int(candidate[14]) & PREPARATION_CRIMSON_SHADE else np.zeros(total, dtype=np.int8)
    )
    crimson2 = (
        rng.integers(1, 4, total)
        if int(enemy[14]) & PREPARATION_CRIMSON_SHADE else np.zeros(total, dtype=np.int8)
    )
    uses_nightshade = POISON_NIGHTSHADE in (
        int(candidate[15]), int(candidate[16]), int(enemy[15]), int(enemy[16]),
    )
    initiative_penalty1 = np.zeros(total, dtype=np.int8) if uses_nightshade else None
    initiative_penalty2 = np.zeros(total, dtype=np.int8) if uses_nightshade else None
    frenzy1 = np.full(total, _has_frenzy_preparation(candidate), dtype=bool)
    frenzy2 = np.full(total, _has_frenzy_preparation(enemy), dtype=bool)
    uses_kusara = _fighter_uses_weapon(candidate, WEAPON_KUSARA_KAMA) or (
        _fighter_uses_weapon(enemy, WEAPON_KUSARA_KAMA)
    )
    attack_penalty1 = np.zeros(total, dtype=np.int8) if uses_kusara else None
    attack_penalty2 = np.zeros(total, dtype=np.int8) if uses_kusara else None
    uses_brazier = _fighter_uses_weapon(candidate, WEAPON_BRAZIER_STAFF) or (
        _fighter_uses_weapon(enemy, WEAPON_BRAZIER_STAFF)
    )
    burning1 = np.zeros(total, dtype=bool) if uses_brazier else None
    burning2 = np.zeros(total, dtype=bool) if uses_brazier else None
    uses_squig = _fighter_uses_weapon(candidate, WEAPON_CHAINED_SQUIG) or (
        _fighter_uses_weapon(enemy, WEAPON_CHAINED_SQUIG)
    )
    entangled1 = np.zeros(total, dtype=bool) if uses_squig else None
    entangled2 = np.zeros(total, dtype=bool) if uses_squig else None
    uses_breaker = _fighter_uses_weapon(candidate, WEAPON_SWORD_BREAKER) or (
        _fighter_uses_weapon(enemy, WEAPON_SWORD_BREAKER)
    )
    broken1 = np.full(total, -999, dtype=np.int16) if uses_breaker else None
    broken2 = np.full(total, -999, dtype=np.int16) if uses_breaker else None
    candidate_charges = _random_candidate_charges(rng, total)
    enemy_charges = ~candidate_charges

    for phase in range(100):
        _raise_if_cancelled(cancel_event)
        unresolved = (state1 != STATE_OUT) & (state2 != STATE_OUT)
        if not unresolved.any():
            break
        candidate_turn = phase % 2 == 0
        skip1 = np.zeros(total, dtype=bool)
        skip2 = np.zeros(total, dtype=bool)
        if candidate_turn:
            if attack_penalty2 is not None:
                attack_penalty2[:] = 0
            if burning1 is not None:
                active_fire = unresolved & burning1
                extinguished = active_fire & (rng.integers(1, 7, total) >= 4)
                burning1[extinguished] = False
                failed_fire = active_fire & ~extinguished
                skip1[failed_fire] = True
                _vector_automatic_hit(
                    rng, np.flatnonzero(failed_fire), candidate, wounds1, state1,
                    4, WEAPON_BRAZIER_STAFF,
                )
            if entangled2 is not None:
                valid_squig = entangled2 & (state1 == STATE_STANDING)
                entangled2 &= state1 == STATE_STANDING
                _vector_automatic_hit(
                    rng, np.flatnonzero(valid_squig), enemy, wounds2, state2,
                    3, WEAPON_CHAINED_SQUIG,
                )
            paralyzed = unresolved & (state1 == STATE_PARALYZED)
            recovered = paralyzed & (rng.integers(1, 7, total) <= int(candidate[2]))
            state1[recovered] = STATE_STANDING
            stunned = unresolved & (state1 == STATE_STUNNED)
            state1[stunned] = STATE_KNOCKED_DOWN
            knocked = unresolved & (state1 == STATE_KNOCKED_DOWN) & ~stunned
            state1[knocked] = STATE_STANDING
            stood1 = knocked
            stood2 = np.zeros(total, dtype=bool)
        else:
            if attack_penalty1 is not None:
                attack_penalty1[:] = 0
            if burning2 is not None:
                active_fire = unresolved & burning2
                extinguished = active_fire & (rng.integers(1, 7, total) >= 4)
                burning2[extinguished] = False
                failed_fire = active_fire & ~extinguished
                skip2[failed_fire] = True
                _vector_automatic_hit(
                    rng, np.flatnonzero(failed_fire), enemy, wounds2, state2,
                    4, WEAPON_BRAZIER_STAFF,
                )
            if entangled1 is not None:
                valid_squig = entangled1 & (state2 == STATE_STANDING)
                entangled1 &= state2 == STATE_STANDING
                _vector_automatic_hit(
                    rng, np.flatnonzero(valid_squig), candidate, wounds1, state1,
                    3, WEAPON_CHAINED_SQUIG,
                )
            paralyzed = unresolved & (state2 == STATE_PARALYZED)
            recovered = paralyzed & (rng.integers(1, 7, total) <= int(enemy[2]))
            state2[recovered] = STATE_STANDING
            stunned = unresolved & (state2 == STATE_STUNNED)
            state2[stunned] = STATE_KNOCKED_DOWN
            knocked = unresolved & (state2 == STATE_KNOCKED_DOWN) & ~stunned
            state2[knocked] = STATE_STANDING
            stood2 = knocked
            stood1 = np.zeros(total, dtype=bool)

        first_round = phase == 0
        charging1 = candidate_charges if first_round else np.zeros(total, dtype=bool)
        charging2 = enemy_charges if first_round else np.zeros(total, dtype=bool)
        charged1 = charging2
        charged2 = charging1
        parry1_used = np.zeros(total, dtype=bool)
        parry2_used = np.zeros(total, dtype=bool)

        # Priorities belong to each attack, not to the fighter as a whole.
        # Resolve first, normal, and last attacks while retaining one parry per
        # defender throughout the phase.
        for stage in (PRIORITY_FIRST, PRIORITY_NORMAL, PRIORITY_LAST):
            unresolved = (state1 != STATE_OUT) & (state2 != STATE_OUT)
            standing1 = (state1 == STATE_STANDING) & ~skip1
            standing2 = (state2 == STATE_STANDING) & ~skip2
            has1 = _stage_has_attacks(
                candidate, stage, first_round, charging1, charged1,
                stood1, frenzy1,
            )
            has2 = _stage_has_attacks(
                enemy, stage, first_round, charging2, charged2,
                stood2, frenzy2,
            )
            active1 = unresolved & standing1 & has1
            active2 = unresolved & standing2 & has2
            # Most duels contain only normal-priority attacks.
            # Do not build a complete vector phase for an empty priority.
            if not active1.any() and not active2.any():
                continue
            both = active1 & active2
            candidate_first = active1 & ~active2

            if both.any():
                i1 = np.maximum(
                    1,
                    _combat_initiative(candidate, first_round=first_round)
                    + crimson1
                    - (initiative_penalty1 if initiative_penalty1 is not None else 0),
                )
                i2 = np.maximum(
                    1,
                    _combat_initiative(enemy, first_round=first_round)
                    + crimson2
                    - (initiative_penalty2 if initiative_penalty2 is not None else 0),
                )
                candidate_first |= both & (i1 > i2)
                tied = both & (i1 == i2)
                candidate_first[tied] = rng.random(int(tied.sum())) < 0.5

            candidate_rows = np.flatnonzero(active1 & candidate_first)
            enemy_rows = np.flatnonzero(active2 & ~candidate_first)

            _vector_attack_phase(
                candidate, enemy, candidate_rows, wounds2, state2, amulet2, rng,
                first_round, charging1, charged1,
                initiative_penalty2, frenzy1,
                attack_penalty1, attack_penalty2, burning2, entangled2,
                wounds1, state1, broken1,
                priority_stage=stage, attacker_stood=stood1,
                defender_parry_used=parry2_used,
            )
            frenzy2[(state2 == STATE_KNOCKED_DOWN) | (state2 == STATE_STUNNED)] = False

            enemy_reply = candidate_rows[
                active2[candidate_rows]
                & (state2[candidate_rows] == STATE_STANDING)
                & ~skip2[candidate_rows]
            ]
            _vector_attack_phase(
                enemy, candidate, enemy_reply, wounds1, state1, amulet1, rng,
                first_round, charging2, charged2,
                initiative_penalty1, frenzy2,
                attack_penalty2, attack_penalty1, burning1, entangled1,
                wounds2, state2, broken2,
                priority_stage=stage, attacker_stood=stood2,
                defender_parry_used=parry1_used,
            )
            frenzy1[(state1 == STATE_KNOCKED_DOWN) | (state1 == STATE_STUNNED)] = False

            _vector_attack_phase(
                enemy, candidate, enemy_rows, wounds1, state1, amulet1, rng,
                first_round, charging2, charged2,
                initiative_penalty1, frenzy2,
                attack_penalty2, attack_penalty1, burning1, entangled1,
                wounds2, state2, broken2,
                priority_stage=stage, attacker_stood=stood2,
                defender_parry_used=parry1_used,
            )
            frenzy1[(state1 == STATE_KNOCKED_DOWN) | (state1 == STATE_STUNNED)] = False

            candidate_reply = enemy_rows[
                active1[enemy_rows]
                & (state1[enemy_rows] == STATE_STANDING)
                & ~skip1[enemy_rows]
            ]
            _vector_attack_phase(
                candidate, enemy, candidate_reply, wounds2, state2, amulet2, rng,
                first_round, charging1, charged1,
                initiative_penalty2, frenzy1,
                attack_penalty1, attack_penalty2, burning2, entangled2,
                wounds1, state1, broken1,
                priority_stage=stage, attacker_stood=stood1,
                defender_parry_used=parry2_used,
            )
            frenzy2[(state2 == STATE_KNOCKED_DOWN) | (state2 == STATE_STUNNED)] = False

    wins = int(np.count_nonzero((state2 == STATE_OUT) & (state1 != STATE_OUT)))
    resolved = int(np.count_nonzero((state1 == STATE_OUT) | (state2 == STATE_OUT)))
    return wins, resolved


def _choice_weight(cost, rarity):
    return 1.0 / (1.0 + cost / 35.0 + rarity / 5.0)


def _weighted_choice(rng, options):
    weights = np.array([_choice_weight(cost, rarity) for _, cost, rarity in options])
    weights /= weights.sum()
    return options[int(rng.choice(len(options), p=weights))][0]


def _random_enemy_config(name, level, rng):
    profile = ENEMY_PROFILES[name]
    equipment = profile["equipment"]
    config = {key: profile[key] for key in ("WS", "S", "T", "W", "I", "A")}
    config["skills"] = list(profile.get("skills", []))
    config["disease_immune"] = name in {"Zombie", "Skeleton", "Vampire", "Possessed"}
    config["undead_or_possessed"] = name in {
        "Zombie", "Skeleton", "Vampire", "Possessed"
    }
    config["main_weapon"] = _weighted_choice(rng, equipment["main"])
    config["off_hand"] = _weighted_choice(rng, equipment["off"])
    config["armor"] = _weighted_choice(rng, equipment["armor"])
    config["main_weapon_material"] = "Normal"
    config["offhand_material"] = "Normal"
    config["has_luck_amulet"] = False
    config["preparations"] = []
    config["main_poison"] = "No Poison"
    config["offhand_poison"] = "No Poison"
    consumables = equipment.get("consumables", [])
    can_use_consumables = name in {
        "Human veteran", "Swordsman or duelist", "Sister of Sigmar",
        "Human leader", "Orc leader", "Skaven assassin", "Elf hero",
    }
    if consumables and can_use_consumables and rng.random() < 0.18:
        weights = np.array([
            _choice_weight(cost, rarity) for _, _, cost, rarity in consumables
        ])
        weights /= weights.sum()
        kind, item_name, _, _ = consumables[
            int(rng.choice(len(consumables), p=weights))
        ]
        if kind == "preparation":
            config["preparations"].append(item_name)
        elif kind == "poison":
            config["main_poison"] = item_name
    helmet = equipment.get("helmet")
    config["has_helmet"] = bool(
        helmet and rng.random() < min(0.35, 2.5 * _choice_weight(*helmet) / 10.0)
    )

    advance_skills = list(SKILLS)
    for skill in config["skills"]:
        if skill in advance_skills:
            advance_skills.remove(skill)
    for _ in range(max(0, int(level))):
        choices = ["WS", "S", "T", "W", "I", "A", *advance_skills]
        choice = choices[int(rng.integers(len(choices)))]
        if choice in ("WS", "S", "T", "W", "I", "A"):
            config[choice] += 1
        elif choice not in config["skills"]:
            config["skills"].append(choice)
            advance_skills.remove(choice)
    return config


def _build_enemy_variants(
    names, level, seed, variants_per_profile=24, house_rule_config=None,
):
    rng = np.random.default_rng(seed)
    fighters = []
    owners = []
    for owner, name in enumerate(names):
        for _ in range(variants_per_profile):
            config = _random_enemy_config(name, level, rng)
            if house_rule_config:
                config.update(house_rule_config)
            fighters.append(_make_fighter(config))
            owners.append(owner)
    return np.stack(fighters), np.asarray(owners, dtype=np.int64)


def _cached_enemy_variants(names, level, house_rule_config=None):
    house_rule_config = house_rule_config or {}
    rule_key = tuple(sorted(
        (key, bool(value)) for key, value in house_rule_config.items() if value
    ))
    key = (tuple(names), int(level), rule_key)
    variants = _ENEMY_VARIANT_CACHE.get(key)
    if variants is None:
        # The catalogue is shared by all improvements in the same run.
        variants = _build_enemy_variants(
            key[0], key[1], 17_071 + key[1] * 997, ENEMY_VARIANTS_PER_PROFILE,
            dict(rule_key),
        )[0]
        _ENEMY_VARIANT_CACHE[key] = variants
    return variants


def _build_cumulative_weights(names):
    weights = np.array(
        [ENEMY_PROFILES[name]["weight"] for name in names],
        dtype=np.float64,
    )
    cumulative = np.cumsum(weights)
    cumulative /= cumulative[-1]
    cumulative[-1] = 1.0
    return cumulative


def _generate_shared_enemy_selection(names, total_simulations, seed, variants_per_profile=1):
    cumulative = _build_cumulative_weights(names)
    rng = np.random.default_rng(seed)
    profiles = np.searchsorted(
        cumulative,
        rng.random(total_simulations),
        side="right",
    ).astype(np.int64, copy=False)
    if variants_per_profile <= 1:
        return profiles
    variants = rng.integers(0, variants_per_profile, total_simulations)
    return profiles * variants_per_profile + variants


def run_single_task_optimized(args):
    enemy_level = int(args[12]) if len(args) > 12 else 0
    cancel_event = args[13] if len(args) > 13 else None
    (
        mode, label, candidate_dict, enemy_mode, custom_enemy_dict,
        active_pool_names, enemy_indices, total_sims, seed, is_base,
        progress_queue, task_id,
    ) = args[:12]

    house_rule_config = {
        config_key: bool(candidate_dict.get(config_key, False))
        for config_key in HOUSE_RULE_CONFIG_KEYS.values()
    }
    _raise_if_cancelled(cancel_event)
    candidate = _make_fighter(candidate_dict)
    if enemy_mode == "custom":
        custom_enemy_configs = (
            list(custom_enemy_dict) if isinstance(custom_enemy_dict, (list, tuple))
            else [custom_enemy_dict]
        )
        if enemy_level:
            rng = np.random.default_rng(seed + 404)
            configs = []
            for enemy_config in custom_enemy_configs:
                for _ in range(24):
                    config = dict(enemy_config)
                    config.update(house_rule_config)
                    config["skills"] = list(enemy_config.get("skills", []))
                    for _ in range(enemy_level):
                        skill_pool = enemy_config.get("allowed_upgrade_skills", SKILLS)
                        available_skills = [
                            skill for skill in skill_pool if skill not in config["skills"]
                        ]
                        options = ["WS", "S", "T", "W", "I", "A", *available_skills]
                        upgrade = options[int(rng.integers(len(options)))]
                        if upgrade in ("WS", "S", "T", "W", "I", "A"):
                            config[upgrade] += 1
                        elif upgrade not in config["skills"]:
                            config["skills"].append(upgrade)
                    configs.append(_make_fighter(config))
            enemies = np.stack(configs)
        else:
            enemies = np.stack([
                _make_fighter(dict(config, **house_rule_config))
                for config in custom_enemy_configs
            ])
    else:
        enemies = _cached_enemy_variants(
            active_pool_names, enemy_level, house_rule_config
        )

    if enemy_mode == "custom" and len(enemies) > 1 and (
        len(enemy_indices) != total_sims or int(np.max(enemy_indices, initial=0)) >= len(enemies)
    ):
        selection_rng = np.random.default_rng(seed + 808)
        enemy_indices = selection_rng.integers(0, len(enemies), total_sims, dtype=np.int64)

    wins, resolved = _simulate_batch(
        candidate, enemies, enemy_indices, total_sims, seed, cancel_event,
    )
    if progress_queue is not None:
        progress_queue.put(("chunk", task_id, total_sims))

    win_rate = (wins / resolved) * 100.0 if resolved else 0.0
    return mode, label, win_rate, is_base


def run_task_batch(tasks):
    """Run a group of comparisons inside a worker process."""
    return [run_single_task_optimized(task) for task in tasks]
