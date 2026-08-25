import numpy as np

from mordheim_combat_lab.engine import (
    STATE_KNOCKED_DOWN,
    STATE_OUT,
    STATE_STANDING,
    STATE_STUNNED,
    _can_parry,
    _make_fighter,
    _simulate_batch,
    _simulate_homogeneous_batch,
    _vector_injury,
)
from mordheim_combat_lab.rules import WEAPON_MACE, WEAPON_SWORD


def fighter(**changes):
    base = {
        "WS": 4,
        "S": 3,
        "T": 3,
        "W": 1,
        "I": 4,
        "A": 1,
        "skills": [],
        "main_weapon": "Sword",
        "off_hand": "None",
        "has_helmet": False,
        "has_luck_amulet": False,
        "armor": "No Armour",
    }
    return _make_fighter(base | changes)


class FixedRolls:
    def __init__(self, *rolls):
        self.rolls = iter(rolls)

    def integers(self, _low, _high, size):
        return np.full(size, next(self.rolls), dtype=np.int8)


def win_rate(attacker, defender, seed=123, simulations=20_000):
    wins, resolved = _simulate_homogeneous_batch(
        attacker, defender, simulations, np.random.default_rng(seed)
    )
    return wins / resolved


def test_attacks_with_double_strength_cannot_be_parried():
    assert _can_parry(5, 3)
    assert not _can_parry(6, 3)
    assert not _can_parry(7, 3)


def test_vector_injury_table_distinguishes_maces_from_swords():
    mace = _vector_injury(
        FixedRolls(2), 1, WEAPON_MACE, False, False, False, False, 0
    )
    sword = _vector_injury(
        FixedRolls(2), 1, WEAPON_SWORD, False, False, False, False, 0
    )
    out = _vector_injury(
        FixedRolls(6), 1, WEAPON_SWORD, False, False, False, False, 0
    )
    assert mace.tolist() == [STATE_STUNNED]
    assert sword.tolist() == [STATE_KNOCKED_DOWN]
    assert out.tolist() == [STATE_OUT]


def test_spring_up_does_not_cancel_a_helmet_knockdown():
    states = _vector_injury(
        FixedRolls(3, 4), 1, WEAPON_SWORD, True, True, False, False, 0
    )
    assert states.tolist() == [STATE_KNOCKED_DOWN]


def test_mandrake_knockdown_can_be_cancelled_by_spring_up():
    states = _vector_injury(
        FixedRolls(3), 1, WEAPON_SWORD, False, True, True, False, 0
    )
    assert states.tolist() == [STATE_STANDING]


def test_luck_amulet_reduces_the_attackers_win_rate():
    attacker = fighter(main_weapon="Mace")
    plain = fighter(WS=3, I=3, main_weapon="Mace")
    protected = fighter(
        WS=3, I=3, main_weapon="Mace", has_luck_amulet=True
    )
    assert win_rate(attacker, protected) < win_rate(attacker, plain)


def test_sigmarite_hammer_is_better_against_unholy_targets():
    attacker = fighter(main_weapon="Sigmarite hammer")
    normal = fighter(T=4, WS=3, I=3, main_weapon="Mace")
    unholy = fighter(
        T=4, WS=3, I=3, main_weapon="Mace", undead_or_possessed=True
    )
    assert win_rate(attacker, unholy) > win_rate(attacker, normal) + 0.04


def test_chitin_armour_is_vulnerable_to_the_brazier_staff():
    attacker = fighter(main_weapon="Brazier iron")
    light = fighter(W=2, WS=3, I=3, main_weapon="Mace", armor="Light armour")
    chitin = fighter(
        W=2, WS=3, I=3, main_weapon="Mace", armor="Spider chitin armour"
    )
    assert win_rate(attacker, chitin) > win_rate(attacker, light) + 0.03


def test_spider_spit_improves_the_poisoned_weapon():
    plain = fighter(A=2, main_weapon="Sword")
    poisoned = fighter(A=2, main_weapon="Sword", main_poison="Spider Spittle")
    defender = fighter(WS=3, I=3, main_weapon="Mace")
    assert win_rate(poisoned, defender) > win_rate(plain, defender) + 0.02


def test_infallible_strike_improves_wound_rerolls():
    plain = fighter(S=2, main_weapon="Sword")
    infallible = fighter(S=2, main_weapon="Sword", skills=["Sure Strike"])
    defender = fighter(T=4, WS=3, I=3, main_weapon="Mace")
    assert win_rate(infallible, defender) > win_rate(plain, defender) + 0.04


def test_elven_agility_reduces_enemy_win_rate():
    attacker = fighter(A=2, main_weapon="Mace")
    plain = fighter(WS=3, I=3, main_weapon="Sword")
    agile = fighter(WS=3, I=3, main_weapon="Sword", skills=["Elven Agility"])
    assert win_rate(attacker, agile) < win_rate(attacker, plain) - 0.02


def test_unwinnable_duel_is_excluded_from_results():
    candidate = fighter(WS=1, S=1, T=10, I=1, main_weapon="Dagger")
    enemies = np.stack([candidate.copy()])
    wins, resolved = _simulate_batch(
        candidate, enemies, np.zeros(20, dtype=np.int64), 20, 123
    )
    assert wins == 0
    assert resolved == 0
