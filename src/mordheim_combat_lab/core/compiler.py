"""Compile stable IDs into numeric fighter specifications."""
from __future__ import annotations
from dataclasses import dataclass, fields
from functools import lru_cache
from pathlib import Path
import re
from ..catalog.loader import load_bands, load_execution_contract, load_mechanics, load_runtime_scope, load_simulation_mappings, load_skills, runtime_bindings
from .models import Characteristics, CompiledFighter, EffectSet, FighterBuild

COLLECTIONS = ("weapons","armours","defences","materials","preparations","poisons","skills")
EFFECT_FIELDS = {field.name for field in fields(EffectSet)}
TRAIT_TYPES = {
    "starting_skills": (list,tuple), "natural_armour_save": int, "injury_profile": int,
    "ward_save": int, "regeneration_save": int,
    "extra_natural_attacks": int, "poison_immune": bool, "undead_or_possessed": bool,
    "frenzy": bool, "cloud_of_flies": bool, "natural_armour_stacks": bool,
    "charge_attack_bonus": bool, "maddened_with_pain": bool,
    "natural_armour_unmodified": bool, "poisonous_injury": bool, "survivor": bool,
    "natural_armour_worst_save": int,
    "concussion_immune": bool, "wight_blades": bool, "perfect_killer": bool,
    "counts_as_buckler": bool, "counts_as_shield": bool, "fragile_halflings": bool,
    "flammable": bool,
    "injury_reroll_out": bool,
    "dagger_master": bool,
    "spiritual_weapons": bool,
    "bear_hug": bool,
}

SPECIAL_RULE_EFFECTS = {
    "band--beastmen-special-skills-mutant": {},
    "band--marauder-special-skills-mutant": {},
    "band--mutations-tentacle": {"effects": {"incoming_attacks_modifier": -1}},
    "band--blessings-of-nurgle-nurgles-rot": {"traits": {"poison_immune": True}},
    "band--blessings-of-nurgle-cloud-of-flies": {"traits": {"cloud_of_flies": True}},
    "band--blessings-of-nurgle-bloated-foulness": {"stats": {"toughness": 1, "wounds": 1}},
    "band--blessings-of-nurgle-mark-of-nurgle": {"stats": {"wounds": 1}, "traits": {"poison_immune": True}},
    "band--blood-dragon-power-red-fury": {"effects": {"attacks_bonus": 1}},
    "band--blood-dragon-power-infallible": {"effects": {"charge_reroll_hits": True}},
    "band--blood-dragon-power-strength-of-steel": {"effects": {"charge_strength_bonus": 1}},
    "band--lahmia-power-lost-innocence": {"effects": {"priority": 10}},
    "band--strigoi-power-curse-of-the-reborn": {"effects": {"regeneration_save": 4}},
    "band--strigoi-power-monstrosity": {"stats": {"wounds": 1}},
    "band--strigoi-power-iron-sinews": {"stats": {"strength": 1}},
    "band--strigoi-power-infinite-hatred": {"effects": {"reroll_hits": True}},
    # Optional profile rules are selected through FighterBuild.special_rule_ids.
    # The effects below are the persistent part of their 1v1 contract; rules
    # which replace a particular attack remain represented by equipment slots.
    "band--orc-special-skills-well-ard": {"effects": {"armour_save_bonus": 1}},
    "trained-bear--bear-hug": {"effects": {"bear_hug": True}},
    "band--mutations-extra-arm": {},
    "band--mutations-great-claw": {},
    "band--beastmen-special-skills-horned-one": {},
    "band--dwarf-special-skills-combat-master": {"effects": {"tags": ("skill.unbeatable-warrior",)}},
    "band--dwarf-special-skills-master-of-blades": {"effects": {"tags": ("skill.unbeatable-warrior", "skill.sword-master")}},
    "band--norse-special-skills-berserk-charge": {"effects": {"charge_reroll_hits": True}},
    "band--skaven-special-skills-art-of-silent-death": {"effects": {"tags": ("skill.art-of-silent-death",), "attacks_bonus": 1}},
    "band--necromantic-modification-multiple-limbs": {"effects": {"attacks_bonus": 1}},
    "band--necromantic-modification-putrid-stench": {"effects": {"incoming_hit_modifier": -1}},
    "band--mutations-tentacle": {"effects": {"incoming_attacks_modifier": -1}},
    "band--slayer-special-skills-berserker": {"effects": {"tags": ("skill.berserker",)}},
    "band--troll-slayer-special-skills-berserker": {"effects": {"tags": ("skill.berserker",)}},
    "swordsmen--expert-swordsmen": {"effects": {"tags": ("skill.expert-swordsman",)}},
    "band--norse-special-skills-crushing-blow": {"effects": {"cannot_be_parried": True}},
    "band--norse-special-skills-shield-master": {"effects": {"tags": ("skill.shield-mastery",)}},
    "band--pit-fighter-skill-bulging-biceps": {"effects": {"tags": ("skill.mighty-biceps",)}},
    "band--shield-bash": {},
    "band--skaven-special-skills-tail-fighting": {},
    "band--sacred-mark-venom-glands": {},
}

# Rules granted by a profile use the same compact EffectSet contract as a
# selected special rule.  This keeps source-specific wording out of the
# vectorized combat loop.
PROFILE_RULE_EFFECTS = {
    "wild-beasts--charge": {"effects": {"charge_attacks_bonus": 1}},
    "fanatics--frantic": {"effects": {"priority": 10}},
    "centigors--trample": {},
    "band--bite-attack": {},
    "saurus-totem-warrior--bite-attack": {},
    "saurus-braves--bite-attack": {},
    "wulfen--hardened-hide": {"traits": {"natural_armour_save": 6}},
}

@dataclass(frozen=True, slots=True)
class ExecutionEffect:
    """A single, data-defined effect and the context in which it is applied."""
    effect: EffectSet
    trigger: str
    application: str
    stacking: str

def merge_effects(left: EffectSet, right: EffectSet) -> EffectSet:
    values = {}
    for field in fields(EffectSet):
        a, b = getattr(left, field.name), getattr(right, field.name)
        if field.name == "tags": values[field.name] = tuple(dict.fromkeys((*a,*b)))
        elif isinstance(a, bool): values[field.name] = a or b
        elif field.name in {"ward_save","regeneration_save","maximum_wound_target"}: values[field.name] = min(a, b)
        elif field.name in {"damage","out_of_action_threshold"}: values[field.name] = max(a, b)
        elif field.name == "priority": values[field.name] = max(a, b)
        else: values[field.name] = a + b
    return EffectSet(**values)

def merge_best_effects(left: EffectSet, right: EffectSet) -> EffectSet:
    """Keep the best independent value for a non-stacking effect."""
    values = {}
    for field in fields(EffectSet):
        a, b = getattr(left, field.name), getattr(right, field.name)
        if field.name == "tags": values[field.name] = tuple(dict.fromkeys((*a, *b)))
        elif isinstance(a, bool): values[field.name] = a or b
        elif field.name in {"ward_save", "regeneration_save", "maximum_wound_target", "incoming_strength_modifier"}:
            values[field.name] = min(a, b)
        else: values[field.name] = max(a, b)
    return EffectSet(**values)

def apply_execution_effects(base: EffectSet, effect_ids, effects: Mapping[str, ExecutionEffect],
                            trigger: str, application: str) -> EffectSet:
    """Apply only effects declared for one executable runtime context."""
    result = base
    applied_once: set[str] = set()
    for effect_id in effect_ids:
        definition = effects[effect_id]
        if definition.trigger != trigger or definition.application != application:
            continue
        if definition.stacking == "once" and effect_id in applied_once:
            continue
        result = merge_best_effects(result, definition.effect) if definition.stacking == "best" else merge_effects(result, definition.effect)
        if definition.stacking == "once":
            applied_once.add(effect_id)
    return result

@lru_cache(maxsize=None)
def mechanic_index(ruleset: str, root: Path | None = None):
    doc = load_mechanics(ruleset, root)
    return {str(row["id"]): row for collection in COLLECTIONS for row in doc.get(collection, ())}

@lru_cache(maxsize=None)
def effect_index(ruleset: str, root: Path | None = None):
    result = {}
    for row in load_execution_contract(ruleset, root).get("mechanics") or ():
        mechanic_id=str(row.get("id", ""))
        if not mechanic_id or mechanic_id in result: raise ValueError(f"missing or duplicate execution ID: {mechanic_id!r}")
        if row.get("handler")!="effect-set": raise ValueError(f"unknown handler for {mechanic_id}: {row.get('handler')!r}")
        trigger = row.get("trigger")
        application = row.get("application")
        if trigger not in {"passive","duel_start","attack"}: raise ValueError(f"unknown trigger for {mechanic_id}")
        if application not in {"fighter","attack"}: raise ValueError(f"unknown application for {mechanic_id}")
        expected_application = "attack" if trigger == "attack" else "fighter"
        if application != expected_application:
            raise ValueError(f"invalid trigger/application for {mechanic_id}: {trigger}/{application}")
        if row.get("stacking") not in {"stack","best","once"}: raise ValueError(f"unknown stacking rule for {mechanic_id}")
        params = dict(row.get("parameters") or {})
        unknown = set(params) - EFFECT_FIELDS
        if unknown: raise ValueError(f"unknown parameters for {row.get('id')}: {sorted(unknown)}")
        if "tags" in params: params["tags"]=tuple(params["tags"])
        result[mechanic_id] = ExecutionEffect(EffectSet(**params), trigger, application, row["stacking"])
    return result

def validate_execution_contract(ruleset="mordheim", root=None):
    try: mechanics, effects = mechanic_index(ruleset, root), effect_index(ruleset, root)
    except (TypeError, ValueError) as exc: return [str(exc)]
    errors = []
    if set(mechanics)-set(effects): errors.append(f"mechanics without execution: {sorted(set(mechanics)-set(effects))}")
    if set(effects)-set(mechanics): errors.append(f"execution without mechanic: {sorted(set(effects)-set(mechanics))}")
    empty=[mid for mid,row in ((str(r.get("id")),r) for r in load_execution_contract(ruleset,root).get("mechanics") or ()) if not (row.get("parameters") or {})]
    if empty:errors.append(f"mechanics with empty contracts: {sorted(empty)}")
    return errors

def _profile(build, root):
    # A free-selection build supplies its whole profile as characteristics.
    # A band/profile build may also supply them: those are player advances
    # over the KB starting profile, while the package still governs legal
    # equipment, skills and special rules.
    if build.characteristics is not None and not build.band_id:
        return build.characteristics, {}, None, None, ()
    for package in load_bands(build.collection, root):
        if package.band.get("id") != build.band_id: continue
        if package.ruleset != build.ruleset:
            raise ValueError(
                f"band {build.collection}/{build.band_id} uses ruleset "
                f"{package.ruleset}, not {build.ruleset}"
            )
        for profile in package.profiles:
            if profile.get("id") != build.profile_id: continue
            exclusions={(row.get("band_id"),row.get("profile_id")):row.get("reason") for row in load_runtime_scope(build.ruleset,root).get("profile_exclusions") or ()}
            reason=exclusions.get((build.band_id,build.profile_id))
            if reason:raise ValueError(f"profile is outside the duel runtime: {build.band_id}/{build.profile_id}: {reason}")
            c = profile["characteristics"]
            values={};random=[]
            for key in ("WS","S","T","W","I","A"):
                value=c.get(key)
                if isinstance(value,int):values[key]=value;continue
                match=re.fullmatch(r"(\d*)D(\d+)(?:\+(\d+))?",str(value),re.IGNORECASE)
                if not match:raise ValueError(f"profile {build.band_id}/{build.profile_id} is not an individual close-combat fighter")
                dice=int(match.group(1) or 1);sides=int(match.group(2));bonus=int(match.group(3) or 0)
                values[key]=dice+bonus;random.append((key,dice,sides,bonus))
            base = Characteristics(values["WS"],values["S"],values["T"],values["W"],values["I"],values["A"])
            return build.characteristics or base, dict(profile.get("combat_traits") or {}), package, profile, tuple(random)
        raise KeyError(f"unknown profile {build.band_id}/{build.profile_id}")
    raise KeyError(f"unknown band {build.collection}/{build.band_id}")

def _profile_allowed_mechanics(package, profile, mechanics, ruleset, root):
    by_option={str(row.get("engine_option")):mid for mid,row in mechanics.items() if row.get("engine_option")}
    mapping={str(row["item_id"]):row for row in load_simulation_mappings(ruleset,root).get("item_mappings") or ()}
    lists={row.get("id"):row for row in package.equipment_lists}
    item_ids=set(profile.get("fixed_equipment") or ())
    for list_id in profile.get("equipment_lists") or ():
        if list_id not in lists: raise ValueError(f"profile references unknown equipment list: {package.band.get('id')}/{profile.get('id')}/{list_id}")
        item_ids.update(str(item.get("item_id")) for item in lists[list_id].get("items") or ())
    allowed=set()
    for item_id in item_ids:
        row=mapping.get(item_id)
        if not row or row.get("status")!="implemented":
            continue
        mechanic_id=row.get("mechanic_id") or by_option.get(str(row.get("engine_option")))
        if mechanic_id in mechanics:
            allowed.add(mechanic_id)
    allowed.update(
        str(binding["id"])
        for rule in _applicable_profile_rules(package, profile)
        for binding in runtime_bindings(rule, "mechanic")
        if binding.get("id") in mechanics
    )
    return allowed

def _applicable_profile_rules(package, profile):
    rule_ids = set(profile.get("rule_ids") or ())
    return tuple(rule for rule in package.special_rules if rule.get("id") in rule_ids)

def _profile_rule_mechanics(package, profile):
    """Return automatic profile rules that have an executable mechanic binding."""
    rules = (
        *_applicable_profile_rules(package, profile),
        *(rule for rule in package.special_rules
          if (rule.get("runtime") or {}).get("grant") == "band"
          and rule.get("applies_to", {}).get("band") is True),
    )
    return tuple(
        str(binding["id"])
        for rule in rules
        if (rule.get("runtime") or {}).get("implemented") == "YES"
        and (rule.get("runtime") or {}).get("grant") in {"profile", "band"}
        for binding in runtime_bindings(rule, "mechanic")
    )

def _profile_rule_traits(package, profile):
    traits = {}
    rules=(*_applicable_profile_rules(package, profile), *(rule for rule in package.special_rules if (rule.get("runtime") or {}).get("grant") == "band" and rule.get("applies_to",{}).get("band") is True))
    for rule in rules:
        runtime = rule.get("runtime") or {}
        if runtime.get("implemented") != "YES" or runtime.get("grant") not in {"profile", "band"}:
            continue
        for binding in runtime_bindings(rule, "trait"):
            key = str(binding["id"]).removeprefix("trait.").replace("-", "_")
            value = (binding.get("parameters") or {}).get("value")
            if key in traits and traits[key] != value:
                raise ValueError(f"conflicting runtime trait {key} for {package.band.get('id')}/{profile.get('id')}")
            traits[key] = value
    return traits

def _validate_profile_selections(build, package, profile, mechanics, root, main_weapon_id):
    allowed=_profile_allowed_mechanics(package,profile,mechanics,build.ruleset,root)
    equipment={main_weapon_id,build.armour_id,*build.defence_ids}
    if build.off_hand_id:equipment.add(build.off_hand_id)
    if build.main_material_id!="material.normal":equipment.add(build.main_material_id)
    if build.off_hand_id and build.off_material_id!="material.normal":equipment.add(build.off_material_id)
    equipment.discard("armour.no-armour")
    if main_weapon_id=="weapon.natural-attacks":equipment.discard(main_weapon_id)
    illegal=sorted(equipment-allowed)
    if illegal:raise ValueError(f"equipment is not available to {build.band_id}/{build.profile_id}: {illegal}")
    skills={str(row["id"]):row for row in load_skills(build.ruleset,root)}
    access=set(profile.get("skill_access") or ())
    def skill_is_available(skill_id):
        skill = skills.get(skill_id)
        if skill is None or skill.get("category") not in access:
            return False
        if skill.get("category") != "special":
            return True
        source_ids = {build.band_id, str(package.band.get("canonical_family") or "")}
        return any(
            any(f"/{band_id}" in str(reference.get("url") or "") for band_id in source_ids if band_id)
            for reference in skill.get("source_refs") or ()
        )
    illegal_skills=sorted(skill for skill in build.skill_ids if not skill_is_available(skill))
    if illegal_skills:raise ValueError(f"skills are not available to {build.band_id}/{build.profile_id}: {illegal_skills}")
    restrictions=" ".join(profile.get("equipment_restrictions") or ()).lower()
    forbids_armour=any(text in restrictions for text in (
        "never wear armour","cannot wear armour","armour is not allowed","does not allow armour",
        "using any armour","non-armour items","do not wear armour","any form of armour",
        "do not use weapons or wear armour","never use weapons or armour","cannot use normal equipment"))
    if forbids_armour and build.armour_id!="armour.no-armour":raise ValueError(f"armour is forbidden for {build.band_id}/{build.profile_id}")
    if ("may not use an off-hand weapon" in restrictions or "must use one hand" in restrictions) and build.off_hand_id:
        raise ValueError(f"off-hand equipment is forbidden for {build.band_id}/{build.profile_id}")
    if "may not take a lance" in restrictions and main_weapon_id=="weapon.lance":raise ValueError(f"lance is forbidden for {build.band_id}/{build.profile_id}")
    if ("may not use double-handed weapons" in restrictions or "double-handed weapons are for" in restrictions) and mechanics[main_weapon_id].get("hands")==2:
        raise ValueError(f"two-handed weapons are forbidden for {build.band_id}/{build.profile_id}")
    if "may never wear heavy armour" in restrictions and build.armour_id in {"armour.heavy-armour","armour.gromril-armour","armour.ithilmar-armour","armour.plate-armour"}:
        raise ValueError(f"heavy armour is forbidden for {build.band_id}/{build.profile_id}")
    if "may not wear a helmet" in restrictions and any(x in build.defence_ids for x in ("defence.helmet","defence.cooking-pot-helmet")):
        raise ValueError(f"helmet is forbidden for {build.band_id}/{build.profile_id}")

def compile_fighter(build: FighterBuild, root: Path | None = None) -> CompiledFighter:
    characteristics, traits, package, profile, random_characteristics = _profile(build, root)
    if package is not None:
        traits = {**traits, **_profile_rule_traits(package, profile)}
    automatic_rule_effects = EffectSet()
    if package is not None:
        for rule in _applicable_profile_rules(package, profile):
            runtime = rule.get("runtime") or {}
            if runtime.get("implemented") != "YES" or runtime.get("grant") not in {"profile", "band"}:
                continue
            if not runtime_bindings(rule, "compiler"):
                continue
            contract = PROFILE_RULE_EFFECTS.get(str(rule.get("id")))
            if contract is None:
                raise ValueError(f"profile rule has no executable compiler contract: {rule.get('id')}")
            automatic_rule_effects = merge_effects(automatic_rule_effects, EffectSet(**contract.get("effects", {})))
            traits.update(contract.get("traits", {}))
    selected_special_effects = EffectSet()
    selected_special_mechanics = []
    stat_bonuses = {}
    if build.special_rule_ids:
        if package is None:
            raise ValueError("special rules require a band/profile build")
        rules = {str(rule.get("id")): rule for rule in package.special_rules}
        mutation_count = sum(rule_id.startswith("band--mutations-") for rule_id in build.special_rule_ids)
        external_mutation_grants = {
            "beastmen-raiders": "band--beastmen-special-skills-mutant",
            "marauders-of-chaos": "band--marauder-special-skills-mutant",
        }
        mutation_grant = external_mutation_grants.get(build.band_id)
        if mutation_count and mutation_grant:
            if build.special_rule_ids.count(mutation_grant) < mutation_count:
                raise ValueError(f"each purchased mutation requires {mutation_grant}")
            for candidate_package in load_bands(build.collection, root):
                for candidate in candidate_package.special_rules:
                    candidate_id = str(candidate.get("id"))
                    if candidate_id.startswith("band--mutations-"):
                        rules.setdefault(candidate_id, {**candidate, "eligibility": []})
        for rule_id in build.special_rule_ids:
            rule = rules.get(rule_id)
            if rule is None:
                raise ValueError(f"special rule is not available to {build.band_id}: {rule_id}")
            eligible = set(rule.get("eligibility") or ())
            if eligible and build.profile_id not in eligible:
                raise ValueError(f"special rule is not available to {build.band_id}/{build.profile_id}: {rule_id}")
            if rule_id.startswith("band--blessings-of-nurgle-") and build.profile_id != "tainted-ones":
                raise ValueError(f"special rule is not available to {build.band_id}/{build.profile_id}: {rule_id}")
            runtime = rule.get("runtime") or {}
            if runtime.get("implemented") != "YES":
                reason = next((str(effect.get("reason")) for effect in runtime.get("effects") or () if effect.get("reason")), "no executable binding")
                raise ValueError(f"special rule is outside the executable duel runtime: {rule_id}: {reason}")
            if runtime.get("grant") != "selectable":
                raise ValueError(f"special rule is not selectable: {rule_id}")
            bindings = runtime_bindings(rule)
            if not bindings:
                raise ValueError(f"special rule has no executable contract: {rule_id}")
            selected_special_mechanics.extend(str(binding["id"]) for binding in bindings if binding.get("kind") == "mechanic")
            for binding in (binding for binding in bindings if binding.get("kind") == "trait"):
                key = str(binding["id"]).removeprefix("trait.").replace("-", "_")
                traits[key] = (binding.get("parameters") or {}).get("value")
            if any(binding.get("kind") == "compiler" for binding in bindings):
                definition = SPECIAL_RULE_EFFECTS.get(rule_id)
                if definition is None:
                    raise ValueError(f"special rule has no executable compiler contract: {rule_id}")
                selected_special_effects = merge_effects(selected_special_effects, EffectSet(**definition.get("effects", {})))
                traits.update(definition.get("traits", {}))
                for stat, bonus in definition.get("stats", {}).items():
                    stat_bonuses[stat] = stat_bonuses.get(stat, 0) + bonus
    if stat_bonuses:
        characteristics = Characteristics(**{
            field.name: getattr(characteristics, field.name) + stat_bonuses.get(field.name, 0)
            for field in fields(Characteristics)
        })
    errors = validate_execution_contract(build.ruleset, root)
    if errors: raise ValueError("; ".join(errors))
    mechanics, effects = mechanic_index(build.ruleset, root), effect_index(build.ruleset, root)
    excluded={row.get("id") for row in load_runtime_scope(build.ruleset,root).get("mechanic_exclusions") or ()}
    requested=set(build.skill_ids)|set(build.preparation_ids)|set(build.defence_ids)
    if build.main_weapon_id:requested.add(build.main_weapon_id)
    if build.off_hand_id:requested.add(build.off_hand_id)
    unavailable=sorted(requested&excluded)
    if unavailable:raise ValueError(f"mechanics are outside the one-against-one runtime: {unavailable}")
    main_weapon_id=build.main_weapon_id
    if profile is not None and build.main_weapon_id=="weapon.dagger":
        allowed=_profile_allowed_mechanics(package,profile,mechanics,build.ruleset,root)
        fixed=set(profile.get("fixed_equipment") or ())
        if fixed:
            weapon_ids=sorted(mid for mid in allowed if mid.startswith("weapon."))
            if weapon_ids:main_weapon_id=weapon_ids[0]
        elif not profile.get("equipment_lists"):
            main_weapon_id="weapon.natural-attacks"
        elif "weapon.dagger" not in allowed:
            main_weapon_id="weapon.natural-attacks"
    selected = [main_weapon_id,build.armour_id,build.main_material_id,*build.defence_ids,*build.skill_ids,*build.preparation_ids]
    selected += [x for x in (build.off_hand_id,build.off_material_id,build.main_poison_id,build.off_poison_id,build.extra_hand_id) if x]
    unknown = [x for x in selected if x not in mechanics]
    if unknown: raise KeyError(f"unknown mechanic IDs: {unknown}")
    main_row = mechanics[main_weapon_id]
    if not main_row.get("main_hand",False): raise ValueError("illegal main-hand selection")
    if build.off_hand_id:
        off_row = mechanics[build.off_hand_id]
        if build.off_hand_id.startswith("weapon.") and not off_row.get("off_hand",False): raise ValueError("illegal off-hand selection")
        if main_row.get("hands") == 2 or main_row.get("paired"): raise ValueError("main weapon occupies both hands")
    handed={"defence.shield","defence.buckler","defence.kite-shield"}
    if handed.intersection(build.defence_ids):raise ValueError("hand-held defences belong in off_hand_id")
    if package is not None:_validate_profile_selections(build,package,profile,mechanics,root,main_weapon_id)
    unknown_traits=set(traits)-set(TRAIT_TYPES)
    unknown_overrides=set(build.trait_overrides)-set(TRAIT_TYPES)
    if unknown_traits or unknown_overrides:raise ValueError(f"unknown combat traits: {sorted(unknown_traits|unknown_overrides)}")
    for key,value in build.trait_overrides.items():
        if not isinstance(value,TRAIT_TYPES[key]):raise TypeError(f"invalid combat trait value for {key}: {value!r}")
    traits.update(build.trait_overrides)
    for key,value in traits.items():
        if not isinstance(value,TRAIT_TYPES[key]):raise TypeError(f"invalid combat trait value for {key}: {value!r}")
    for key in ("natural_armour_save","natural_armour_worst_save","ward_save","regeneration_save"):
        if key in traits and not 2 <= int(traits[key]) <= 7:
            raise ValueError(f"combat trait {key} must be between 2 and 7")
    if "injury_profile" in traits and int(traits["injury_profile"]) not in range(4):
        raise ValueError("combat trait injury_profile must be between 0 and 3")
    global_effects = EffectSet()
    profile_rule_skills = _profile_rule_mechanics(package, profile) if package is not None else ()
    global_ids = [item for item in selected if item not in {
        main_weapon_id, build.off_hand_id, build.armour_id, build.main_material_id,
        build.off_material_id, build.main_poison_id, build.off_poison_id,
    }]
    global_ids += list(profile_rule_skills)
    global_ids += selected_special_mechanics
    global_ids += [build.armour_id, *build.defence_ids]
    if build.off_hand_id and build.off_hand_id.startswith("defence."):
        global_ids.append(build.off_hand_id)
    global_effects = apply_execution_effects(global_effects, global_ids, effects, "passive", "fighter")
    global_effects = apply_execution_effects(global_effects, global_ids, effects, "duel_start", "fighter")
    for skill_id in traits.get("starting_skills") or ():
        if skill_id not in effects: raise ValueError(f"profile references unknown starting skill ID: {skill_id}")
        global_effects = apply_execution_effects(global_effects, (skill_id,), effects, "passive", "fighter")
    trait_tags=tuple(key for key,value in traits.items() if value is True)
    global_effects = merge_effects(global_effects,EffectSet(
        tags=trait_tags,attacks_bonus=int(traits.get("extra_natural_attacks",0)),
        charge_attacks_bonus=int(bool(traits.get("charge_attack_bonus",False))),
        poison_immunity=bool(traits.get("poison_immune",False)), bear_hug=bool(traits.get("bear_hug",False)),
        frenzy=bool(traits.get("frenzy",False)),
        parry=bool(traits.get("counts_as_buckler",False)),
        armour_save_bonus=int(bool(traits.get("counts_as_shield",False))),
        ward_save=int(traits.get("ward_save",7)),
        regeneration_save=int(traits.get("regeneration_save",7)),
        armour_penetration=int(bool(traits.get("perfect_killer",False)))))
    global_effects = merge_effects(merge_effects(global_effects, automatic_rule_effects), selected_special_effects)
    main_ids=[main_weapon_id, build.main_material_id, *profile_rule_skills]
    if build.main_poison_id: main_ids.append(build.main_poison_id)
    main_effect=apply_execution_effects(EffectSet(), main_ids, effects, "attack", "attack")
    off_effect=apply_execution_effects(EffectSet(), (build.off_hand_id,), effects, "attack", "attack") if build.off_hand_id else None
    if off_effect and build.off_hand_id.startswith("weapon."):
        off_ids=[build.off_hand_id, build.off_material_id, *profile_rule_skills]
        if build.off_poison_id: off_ids.append(build.off_poison_id)
        off_effect=apply_execution_effects(EffectSet(), off_ids, effects, "attack", "attack")
    extra_attacks=[]
    automatic_rule_ids = {str(rule.get("id")) for rule in _applicable_profile_rules(package, profile)} if package is not None else set()
    # Natural and profile-granted attacks are resolved independently, so
    # weapon modifiers never leak into horns, hooves, claws, or bites.
    if "centigors--trample" in automatic_rule_ids:
        extra_attacks.append(EffectSet(tags=("rule.trample",)))
    if any(rule_id in automatic_rule_ids for rule_id in {"band--bite-attack", "saurus-totem-warrior--bite-attack", "saurus-braves--bite-attack"}):
        extra_attacks.append(EffectSet(tags=("weapon.natural-attacks", "rule.bite-attack")))
    if "band--beastmen-special-skills-horned-one" in build.special_rule_ids:
        extra_attacks.append(EffectSet(tags=("rule.horned-one",), charge_strength_bonus=0))
    if "band--mutations-great-claw" in build.special_rule_ids:
        extra_attacks.append(EffectSet(tags=("rule.great-claw",), strength_bonus=1))
    if "band--shield-bash" in build.special_rule_ids:
        if not (build.off_hand_id in {"defence.shield", "defence.kite-shield"}): raise ValueError("Shield Bash requires a shield or kite shield")
        extra_attacks.append(merge_effects(effects["weapon.mace"].effect, EffectSet(strength_bonus=-1)))
    if build.extra_hand_id:
        if not any(rule_id in build.special_rule_ids for rule_id in ("band--mutations-extra-arm", "band--skaven-special-skills-tail-fighting")):
            raise ValueError("an extra hand requires Extra Arm or Tail Fighting")
        if build.extra_hand_id == "defence.kite-shield":
            raise ValueError("the extra hand may not carry a kite shield")
        extra=effects[build.extra_hand_id].effect
        if build.extra_hand_id.startswith("weapon."):
            extra_attacks.append(extra)
        elif build.extra_hand_id in {"defence.shield", "defence.buckler", "defence.kite-shield"}:
            global_effects=merge_effects(global_effects, extra)
            if "band--mutations-extra-arm" in build.special_rule_ids: extra_attacks.append(effects["weapon.natural-attacks"].effect)
        else: raise ValueError("the extra hand must hold a one-handed weapon, shield, or buckler")
    if "band--sacred-mark-venom-glands" in build.special_rule_ids:
        main_effect=EffectSet(tags=("weapon.natural-attacks", "rule.venom-glands"), target_armour_bonus=1, injury_modifier=1)
    armour_save = int(mechanics[build.armour_id].get("base_save") or 7)-effects[build.armour_id].effect.armour_save_bonus-global_effects.armour_save_bonus
    if off_effect is not None:armour_save-=off_effect.armour_save_bonus
    if "defence.sea-dragon-cloak" in build.defence_ids:armour_save=min(armour_save,5)
    if build.armour_id=="armour.cathayan-quilted-silk":armour_save-=1
    natural_armour_save=int(traits.get("natural_armour_save") or 7)
    if traits.get("natural_armour_stacks") and natural_armour_save<=6:
        armour_save-=7-natural_armour_save
    return CompiledFighter(f"{build.band_id or 'custom'}:{build.profile_id or 'custom'}",characteristics,main_effect,off_effect,global_effects,max(1,armour_save),4 if "defence.helmet" in build.defence_ids else 5 if "defence.cooking-pot-helmet" in build.defence_ids else 7,natural_armour_save,bool(build.off_hand_id and build.off_hand_id.startswith("weapon.")),bool(traits.get("natural_armour_unmodified",False)),int(traits.get("injury_profile") or 0),random_characteristics,natural_armour_worst_save=int(traits.get("natural_armour_worst_save") or 7),extra_attacks=tuple(extra_attacks))
