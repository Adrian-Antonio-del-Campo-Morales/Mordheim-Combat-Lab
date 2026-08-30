"""verification.scenarios: responsabilidad extraída sin alterar las reglas."""
from __future__ import annotations
import mordheim_combat_lab.combat.modular.pools as pools

from dataclasses import fields
from dataclasses import is_dataclass
from dataclasses import replace
from enum import Enum
from fractions import Fraction
from mordheim_combat_lab.verification.mutations import runtime_fault
import mordheim_combat_lab.combat.modular.aftermath as aftermath
import mordheim_combat_lab.combat.modular.attacks as attack_resolution
import mordheim_combat_lab.combat.modular.contexts as contexts
import mordheim_combat_lab.combat.modular.rounds as rounds
import mordheim_combat_lab.combat.modular.state as combat_state
import mordheim_combat_lab.combat.phases as phases
from mordheim_combat_lab.construction.compiler import compile_fighter
from mordheim_combat_lab.construction.selection import _applicable_rules
from mordheim_combat_lab.domain.dice import DiceSource
from mordheim_combat_lab.domain.models import Characteristics
from mordheim_combat_lab.domain.models import FighterBuild
from mordheim_combat_lab.knowledge.loader import load_bands
from mordheim_combat_lab.knowledge.loader import load_runtime_scope
from mordheim_combat_lab.knowledge.loader import load_skills
from mordheim_combat_lab.verification.dice import StrictDecisions
from mordheim_combat_lab.verification.dice import StrictDice
from mordheim_combat_lab.verification.dice import enumerate_exact
from mordheim_combat_lab.verification.reports import EvidenceMismatch
from pathlib import Path
from unittest.mock import patch


def _plain(value):
    if isinstance(value, Enum):
        return value.name
    if is_dataclass(value):
        return {f.name: _plain(getattr(value, f.name)) for f in fields(value)}
    if isinstance(value, dict):
        return {k: _plain(v) for k, v in value.items()}
    if isinstance(value, (tuple, list)):
        return [_plain(v) for v in value]
    if isinstance(value, (set, frozenset)):
        return sorted(_plain(v) for v in value)
    return value


def _lookup(value, path: str):
    for part in path.split("."):
        value = value[int(part)] if isinstance(value, list) else value[part]
    return value


def _build(values: dict, root: Path):
    values = dict(values)
    if "characteristics" in values:
        values["characteristics"] = Characteristics(**values["characteristics"])
    elif not values.get("profile_id"):
        values["characteristics"] = Characteristics(3, 3, 3, 3, 3, 1)
    for name in ("defence_ids", "skill_ids", "preparation_ids", "special_rule_ids", "variant_ids"):
        if name in values:
            values[name] = tuple(values[name])
    return compile_fighter(FighterBuild("mordheim", **values), root)


def _state(fighter, values: dict, dice: DiceSource, key: str):
    current = combat_state.initialize_fighter(fighter, dice, key)
    values = dict(values)
    if "condition" in values:
        values["condition"] = phases.Condition[values["condition"]]
    if "resources_spent" in values:
        values["resources_spent"] = frozenset(values["resources_spent"])
    return replace(current, **values)


def _mutate(value, path: list[str], replacement):
    if not path:
        if isinstance(value, tuple):
            return tuple(replacement)
        return replacement
    return replace(value, **{path[0]: _mutate(getattr(value, path[0]), path[1:], replacement)})


def execute_case(case: dict, root: Path, dice: DiceSource,
                 mutation: dict | None = None) -> dict:
    """Fixed adapters only: no alternate combat implementation or eval."""
    attacker = _build(case.get("attacker", {}), root)
    defender = _build(case.get("defender", {}), root)
    if mutation:
        for change in mutation.get("changes", [mutation]):
            actor, *path = change["path"].split(".")
            if actor not in {"attacker", "defender"}:
                raise ValueError("mutations must target a compiled fighter")
            if actor == "attacker":
                attacker = _mutate(attacker, path, change["value"])
            else:
                defender = _mutate(defender, path, change["value"])
    output = {"attacker": attacker, "defender": defender}
    operation = case["operation"]
    if operation in {"compile", "grant", "selectable_grant", "general_skill_access"} and case.get("decisions"):
        raise ValueError("construction cases cannot request combat decisions")
    if operation == "general_skill_access":
        excluded = {row["id"] for row in load_runtime_scope("mordheim", root).get("mechanic_exclusions", [])}
        candidates = [row["id"] for row in load_skills("mordheim", root)
                      if row.get("kind") == "general" and row["id"] not in excluded]
        accepted = []
        for skill in candidates:
            build = dict(case.get("attacker", {}), skill_ids=[skill])
            try:
                _build(build, root)
            except ValueError as error:
                if "skills are not available" not in str(error) and "skills are forbidden" not in str(error):
                    raise
            else:
                accepted.append(skill)
        output["result"] = {"skills": sorted(accepted)}
        return _plain(output)
    if operation == "selectable_grant":
        build = case.get("defender", {})
        package = next(band for band in load_bands(build.get("collection", "mordheim"), root)
                       if band.band["id"] == build["band_id"])
        rule_id = case["context"]["rule_id"]
        recipients = []
        for profile in package.profiles:
            try:
                _build({**build, "profile_id": profile["id"], "special_rule_ids": [rule_id]}, root)
            except ValueError as error:
                if "special rule is not available" not in str(error):
                    raise
            else:
                recipients.append(profile["id"])
        output["result"] = {"recipients": sorted(recipients)}
        return _plain(output)
    if operation == "grant":
        build = case.get("defender", {})
        package = next(band for band in load_bands(build.get("collection", "mordheim"), root)
                       if band.band["id"] == build["band_id"])
        rule_id = case["context"]["rule_id"]
        output["result"] = {"recipients": sorted(
            profile["id"] for profile in package.profiles
            if any(rule["id"] == rule_id for rule in _applicable_rules(package, profile))
        )}
        return _plain(output)
    if operation == "compile":
        if case.get("decisions"):
            raise ValueError("construction cases cannot request combat decisions")
        return _plain(output)
    a = _state(attacker, case.get("attacker_state", {}), dice, "a")
    d = _state(defender, case.get("defender_state", {}), dice, "d")
    context = case.get("context", {})
    weapon = contexts.weapon_against_opponent(attacker, defender, attacker.main_weapon)
    effect = contexts._combined_effect(attacker, weapon)
    first, charging = context.get("first_round", False), context.get("charging", False)
    choices = StrictDecisions(case.get("decisions", []))
    if operation == "strength":
        strength, armour = contexts._attack_strength(attacker, defender, a, weapon, effect, first, charging)
        output["result"] = {"wound": strength, "armour": armour}
    elif operation == "hit":
        ctx = contexts.prepare_hit_context(attacker, defender, a, d, weapon, effect,
                                            first_round=first, charging=charging, key="hit")
        output.update(context=ctx, result=phases.resolve_hit(ctx, dice))
    elif operation == "special_save":
        ctx = contexts.prepare_special_save_context(defender, effect, key="special")
        output.update(context=ctx, result=phases.resolve_special_save(ctx, dice))
    elif operation == "wound":
        ctx = contexts.prepare_wound_context(attacker, defender, a, d, weapon, effect,
            first_round=first, charging=charging, hit_roll=context.get("hit_roll", 4), key="wound")
        output.update(context=ctx, result=phases.resolve_wound(ctx, dice))
    elif operation == "armour":
        ctx = contexts.prepare_armour_context(attacker, defender, a, d, weapon, effect,
            first_round=first, charging=charging, key="armour")
        output.update(context=ctx, result=phases.resolve_armour(ctx, dice))
    elif operation == "parry":
        strength, _ = contexts._attack_strength(attacker, defender, a, weapon, effect, first, charging)
        ctx = contexts._parry_context(defender, d, effect, strength, context.get("hit_roll", 4), "test")
        output.update(context=ctx, result=phases.resolve_parry(ctx, dice) if ctx else phases.ParryResult(False, False))
    elif operation == "priority":
        ctx = phases.PriorityContext(attacker, defender, **context)
        output.update(context=ctx, result=phases.resolve_priority(ctx))
    elif operation == "acting_order":
        left = phases.resolve_priority(phases.PriorityContext(attacker, defender, **context))
        right = phases.resolve_priority(phases.PriorityContext(defender, attacker,
            **case.get("opponent_context", {})))
        output.update(context={"first": left, "second": right},
                      result={"first_acts": phases.first_acts_before(left, right, dice)})
    elif operation == "attacks":
        ctx = phases.AttackPoolContext(attacker, **context)
        output.update(context=ctx, result=phases.build_attacks(ctx))
    elif operation == "allocate":
        count = phases.build_attacks(phases.AttackPoolContext(attacker, **context)).attacks
        output["result"] = {"count": count, "weapons": pools.allocate_attack_weapons(
            attacker, count, first, choices, key="test")}
    elif operation == "injury":
        ctx = contexts._injury_context(defender, effect, "test")
        output.update(context=ctx, result=phases.resolve_injury(ctx, dice))
    elif operation == "attack":
        output["result"] = attack_resolution.resolve_reference_attack(
            attacker, defender, a, d, weapon, dice, key="test", **context)
    elif operation in {"pool", "pool_recovery"}:
        a, d, attack_outcomes = pools._resolve_attack_pool(
            attacker, defender, a, d, context.get("count", a.attacks), dice,
            key="test", first_round=first, charging=charging, decisions=choices)
        output["result"] = {"attacker": a, "defender": d, "attacks": attack_outcomes}
        if operation == "pool_recovery":
            after_a, _ = aftermath._start_round_state(attacker, a)
            after_d, _ = aftermath._start_round_state(defender, d)
            output["result"]["after_recovery"] = {"attacker": after_a, "defender": after_d}
    elif operation == "bear_hug":
        ctx = phases.BearHugContext(context.get("successful_hits", 2), a.strength,
                                    d.strength, key="hug")
        output.update(context=ctx, result=phases.resolve_bear_hug(ctx, dice, choices))
    elif operation == "round":
        duel_state = combat_state.DuelState(a, d, **context)
        output["result"] = rounds.resolve_round(attacker, defender, duel_state, dice, choices)
    elif operation == "initialize":
        output["result"] = {"attacker": a, "defender": d}
    elif operation == "recovery":
        states = []
        for _ in range(context.get("rounds", 1)):
            a, stood = aftermath._start_round_state(attacker, a)
            states.append({"state": a, "stood_up": stood})
        output["result"] = {"rounds": states}
    else:
        raise ValueError(f"unsupported semantic operation {operation}")
    choices.finish()
    return _plain(output)


def check_case(case: dict, root: Path, mutation: dict | None = None):
    unknown = set(case) - {
        "id", "roles", "operation", "attacker", "defender", "attacker_state",
        "defender_state", "context", "opponent_context", "decisions", "rolls",
        "expect", "expect_contains", "distribution", "reject",
    }
    if unknown:
        raise ValueError(f"unknown scenario fields: {sorted(unknown)}")
    phase_fields = {
        "priority": {field.name for field in fields(phases.PriorityContext)} - {"fighter", "opponent"},
        "attacks": {field.name for field in fields(phases.AttackPoolContext)} - {"fighter"},
    }
    context_fields = {
        "compile": set(), "grant": {"rule_id"}, "selectable_grant": {"rule_id"},
        "general_skill_access": set(), "initialize": set(), "injury": set(), "special_save": set(),
        "strength": {"first_round", "charging"}, "hit": {"first_round", "charging"},
        "wound": {"first_round", "charging", "hit_roll"},
        "armour": {"first_round", "charging"}, "parry": {"first_round", "charging", "hit_roll"},
        "pool": {"first_round", "charging", "count"},
        "pool_recovery": {"first_round", "charging", "count"},
        "bear_hug": {"successful_hits"}, "recovery": {"rounds"},
        "round": {"round_index", "first_charged"},
        "attack": {"first_round", "charging", "helpless_at_start", "hit_only", "defences_resolved",
                   "defences_only", "parry_allowed"},
        "acting_order": phase_fields["priority"], "allocate": phase_fields["attacks"], **phase_fields,
    }
    operation = case["operation"]
    if operation not in context_fields:
        raise ValueError(f"unsupported semantic operation {operation}")
    if set(case.get("context", {})) - context_fields[operation]:
        raise ValueError(f"unknown context fields for {operation}")
    if case.get("opponent_context") and (operation != "acting_order" or
            set(case["opponent_context"]) - phase_fields["priority"]):
        raise ValueError("opponent_context is only accepted by acting_order with priority fields")
    if "distribution" in case and any(key in case for key in ("rolls", "expect", "expect_contains", "reject")):
        raise ValueError("distribution cases cannot silently ignore fixed expectations or dice")
    if mutation and mutation.get("runtime_fault"):
        with runtime_fault(mutation["runtime_fault"]):
            return check_case(case, root)
    if "distribution" in case:
        spec = case["distribution"]
        def run(dice):
            output = execute_case(case, root, dice, mutation)
            return _lookup(output, spec["observable"])
        observed = enumerate_exact(run, max_rolls=spec.get("max_rolls", 6))
        literals = {"true": True, "false": False, "null": None}
        expected = {literals.get(key, key): Fraction(str(value))
                    for key, value in spec["expected"].items()}
        if observed != expected:
            raise EvidenceMismatch(f"distribution: {observed!r} != {expected!r}")
        return
    dice = StrictDice(case.get("rolls", []))
    try:
        output = execute_case(case, root, dice, mutation)
    except ValueError as error:
        if case.get("reject") and case["reject"] in str(error):
            dice.finish()
            return
        raise
    if case.get("reject"):
        raise EvidenceMismatch("illegal build was accepted")
    if not case.get("expect"):
        raise ValueError("a semantic case must assert an observable or a distribution")
    for path, expected in case["expect"].items():
        if mutation and not path.startswith(("result.", "context.")):
            continue
        actual = _lookup(output, path)
        if actual != expected:
            raise EvidenceMismatch(f"{path}: got {actual!r}, expected {expected!r}")
    if not mutation:
        for path, expected in case.get("expect_contains", {}).items():
            actual = _lookup(output, path)
            if any(value not in actual for value in expected):
                raise EvidenceMismatch(f"{path}: missing required compiled bindings {expected!r}")
    dice.finish()
