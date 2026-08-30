"""verification.interactions: responsabilidad extraída sin alterar las reglas."""
from __future__ import annotations



INTERACTION_ALIASES = {
    "attacks.base": "fighter.attacks", "attacks.count": "attack.count",
    "strength.base": "fighter.strength", "strength.wound": "attack.strength",
    "hit.rolls": "hit.roll", "wound.rolls": "wound.roll",
    "round.first_round": "round.first", "charge": "round.charging",
    "recovery.stood-up": "state.stood_up", "priority.order": "priority.tier",
    "damage.wound": "damage.unsaved",
}


INTERACTION_CONCEPTS = frozenset({
    "armour.allowed", "armour.strength", "armour.target", "attack.assignment",
    "attack.count", "attack.fire", "attack.penetration", "attack.strength",
    "build.offhand", "build.profile", "build.variant", "construction.skill-access",
    "construction.skill-lists", "damage.unsaved", "defender.poison_immunity",
    "defender.strength", "defender.toughness", "defender.weapon_skill",
    "fighter.attacks", "fighter.initiative", "fighter.strength", "fighter.weapon_skill",
    "fighter.wounds", "hit.reroll", "hit.roll", "hit.success", "hit.target",
    "injury.condition", "injury.origin", "injury.roll", "injury.total",
    "priority.tier", "priority.weapon", "round.charged", "round.charging", "round.first",
    "skill.strongman", "state.critical_available", "state.frenzy", "state.parries", "state.lucky_charm",
    "state.stood_up", "state.wounds", "weapon.kind", "wound.roll", "wound.success", "wound.target",
})


def normalize_interaction_contract(contract: dict) -> dict:
    normalized = {}
    for side in ("reads", "writes"):
        values = contract.get(side)
        if not isinstance(values, list) or any(not isinstance(value, str) for value in values):
            raise ValueError("interaction contract requires explicit lists of concepts")
        concepts = {INTERACTION_ALIASES.get(value, value) for value in values}
        if concepts - INTERACTION_CONCEPTS:
            raise ValueError(f"unknown interaction concepts: {sorted(concepts - INTERACTION_CONCEPTS)}")
        normalized[side] = sorted(concepts)
    return normalized
