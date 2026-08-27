"""Typed public API for the close-combat runtime."""
from __future__ import annotations
from dataclasses import dataclass, field
from threading import Event
from typing import Mapping

@dataclass(frozen=True, slots=True)
class Characteristics:
    weapon_skill: int; strength: int; toughness: int; wounds: int; initiative: int; attacks: int
    def __post_init__(self):
        for name in self.__slots__:
            value = getattr(self, name)
            if not isinstance(value, int) or value < 0: raise ValueError(f"{name} must be a non-negative integer")
        if self.wounds < 1 or self.attacks < 1: raise ValueError("wounds and attacks must be at least one")

@dataclass(frozen=True, slots=True)
class FighterBuild:
    ruleset: str
    characteristics: Characteristics | None = None
    band_id: str | None = None; profile_id: str | None = None
    main_weapon_id: str = "weapon.dagger"; off_hand_id: str | None = None
    armour_id: str = "armour.no-armour"; defence_ids: tuple[str, ...] = ()
    main_material_id: str = "material.normal"; off_material_id: str = "material.normal"
    skill_ids: tuple[str, ...] = (); preparation_ids: tuple[str, ...] = ()
    special_rule_ids: tuple[str, ...] = ()
    extra_hand_id: str | None = None
    main_poison_id: str | None = None; off_poison_id: str | None = None
    trait_overrides: Mapping[str, object] = field(default_factory=dict)
    collection: str = "mordheim"
    def __post_init__(self):
        if self.characteristics is None and not (self.band_id and self.profile_id): raise ValueError("provide characteristics or a band/profile pair")
        if bool(self.band_id) != bool(self.profile_id): raise ValueError("band_id and profile_id must be provided together")
        if not self.collection or any(character not in "abcdefghijklmnopqrstuvwxyz0123456789-" for character in self.collection):
            raise ValueError("collection must be a stable lowercase ID")

@dataclass(frozen=True, slots=True)
class EffectSet:
    tags: tuple[str, ...] = ()
    strength_bonus: int = 0; first_round_strength_bonus: int = 0
    charge_strength_bonus: int = 0; toughness_bonus: int = 0; initiative_bonus: int = 0
    fixed_strength: int = 0
    armour_penetration: int = 0; target_armour_bonus: int = 0
    hit_modifier: int = 0; wound_modifier: int = 0; injury_modifier: int = 0
    attacks_bonus: int = 0; charge_attacks_bonus: int = 0; charge_ws_bonus: int = 0
    first_round_attacks_bonus: int = 0; incoming_strength_modifier: int = 0
    incoming_attacks_modifier: int = 0
    incoming_hit_modifier: int = 0
    armour_save_bonus: int = 0; ward_save: int = 7; priority: int = 0
    parry: bool = False; concussion: bool = False; two_handed: bool = False; paired: bool = False
    reroll_hits: bool = False; reroll_wounds: bool = False; strongman: bool = False
    charge_reroll_hits: bool = False
    step_aside: bool = False; thick_skull: bool = False
    ignore_armour: bool = False; automatic_hit: bool = False; cannot_be_parried: bool = False
    bear_hug: bool = False
    poison_immunity: bool = False; frenzy: bool = False
    damage: int = 1; regeneration_save: int = 7; out_of_action_threshold: int = 5
    maximum_wound_target: int = 7

@dataclass(frozen=True, slots=True)
class CompiledFighter:
    fighter_id: str; characteristics: Characteristics
    main_weapon: EffectSet; off_hand: EffectSet | None; global_effects: EffectSet
    armour_save: int; helmet_save: int; natural_armour_save: int
    off_hand_attacks: bool = False
    natural_armour_unmodified: bool = False
    injury_profile: int = 0
    random_characteristics: tuple[tuple[str,int,int,int], ...] = ()
    natural_armour_worst_save: int = 7
    extra_attacks: tuple[EffectSet, ...] = ()

@dataclass(frozen=True, slots=True)
class DuelRequest:
    first: CompiledFighter; second: CompiledFighter; simulations: int
    seed: int = 0; batch_size: int = 100_000; maximum_rounds: int = 50
    cancel_event: Event | None = field(default=None, compare=False, repr=False)
    def __post_init__(self):
        if min(self.simulations, self.batch_size, self.maximum_rounds) < 1: raise ValueError("simulation limits must be positive")

@dataclass(frozen=True, slots=True)
class DuelResult:
    first_wins: int; second_wins: int; unresolved: int; simulations: int
    def __post_init__(self):
        if self.first_wins + self.second_wins + self.unresolved != self.simulations: raise ValueError("result counts must add up")
    @property
    def first_win_rate(self): return 100.0 * self.first_wins / self.simulations
    @property
    def second_win_rate(self): return 100.0 * self.second_wins / self.simulations
    @property
    def unresolved_rate(self): return 100.0 * self.unresolved / self.simulations

class SimulationCancelled(RuntimeError): pass
