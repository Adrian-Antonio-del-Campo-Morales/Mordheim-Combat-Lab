"""Fallos deliberados limitados a una ejecución y restaurados incluso al fallar."""
from contextlib import contextmanager, ExitStack
from dataclasses import replace

from mordheim_combat_lab.combat.modular import attacks, pools, aftermath, contexts, state, rounds
from mordheim_combat_lab.construction import compiler, selection, restrictions


@contextmanager
def runtime_fault(fault: str):
    from unittest.mock import patch

    if fault not in {"retain-critical-allowance", "retain-parry-capacity", "retain-consumable",
                     "retain-lucky-charm", "suppress-skill-access-grant"}:
        raise ValueError(f"unknown isolated runtime mutation {fault}")
    with ExitStack() as stack:
        if fault == "suppress-skill-access-grant":
            original = compiler.runtime_bindings

            def omit_skill_access(*args, **kwargs):
                return tuple(
                    {**binding, "parameters": {"category": "combat"}}
                    if binding.get("id") == "profile.skill-access" else binding
                    for binding in original(*args, **kwargs)
                )

            for consumer in (compiler, selection, restrictions):
                if hasattr(consumer, "runtime_bindings"):
                    stack.enter_context(patch.object(consumer, "runtime_bindings", omit_skill_access))
        elif fault == "retain-consumable":
            stack.enter_context(patch.object(state.FighterState, "spend", lambda value, resource: value))
        else:
            def faulty_replace(value, **changes):
                if isinstance(value, state.FighterState):
                    if fault == "retain-critical-allowance" and changes.get("critical_available") is False:
                        changes.pop("critical_available")
                    if (fault == "retain-parry-capacity" and "parries_remaining" in changes
                            and changes["parries_remaining"] < value.parries_remaining):
                        changes.pop("parries_remaining")
                    if fault == "retain-lucky-charm" and changes.get("lucky_charm") is False:
                        changes.pop("lucky_charm")
                return replace(value, **changes)

            for consumer in (attacks, pools, aftermath, contexts, state, rounds):
                if hasattr(consumer, "replace"):
                    stack.enter_context(patch.object(consumer, "replace", faulty_replace))
        yield
