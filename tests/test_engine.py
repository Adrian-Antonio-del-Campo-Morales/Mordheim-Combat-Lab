import queue
import threading
import time

import numpy as np
import pytest

import mordheim_combat_lab.engine as engine
from mordheim_combat_lab.engine import (
    ENEMY_VARIANTS_PER_PROFILE,
    _build_enemy_variants,
    _generate_shared_enemy_selection,
    _random_enemy_config,
    _random_candidate_charges,
    effective_fighter_key,
    run_single_task_optimized,
)
from mordheim_combat_lab.enemies import ENEMY_PROFILES
from mordheim_combat_lab.rules import (
    EQUIPMENT_SELECTOR_OPTIONS, POISONS, TWO_HANDED_WEAPONS, WEAPON_UNARMED,
)
from mordheim_combat_lab.ui import DEFAULT_COMBO_SIMULATIONS, CombatLabApp


FIGHTER = {
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


def test_shared_enemy_selection_is_reproducible_and_valid():
    names = ["Human warrior", "Dwarf warrior", "Orc"]
    first = _generate_shared_enemy_selection(names, 1_000, 1234)
    second = _generate_shared_enemy_selection(names, 1_000, 1234)
    assert np.array_equal(first, second)
    assert first.min() >= 0
    assert first.max() < len(names)


def test_first_turn_charge_is_drawn_per_duel_and_is_balanced():
    first = _random_candidate_charges(np.random.default_rng(2026), 100_000)
    second = _random_candidate_charges(np.random.default_rng(2026), 100_000)
    assert np.array_equal(first, second)
    assert first.dtype == np.bool_
    assert 0.49 < first.mean() < 0.51
    assert first.any() and (~first).any()


def test_worker_runs_a_small_custom_matchup():
    total = 100
    progress = queue.Queue()
    args = (
        "Single",
        "prueba",
        FIGHTER,
        "custom",
        FIGHTER | {
            "WS": 3,
            "I": 3,
            "skills": [],
            "main_weapon": "Sword",
            "off_hand": "None",
            "has_helmet": False,
            "has_luck_amulet": False,
            "armor": "No Armour",
        },
        [],
        np.zeros(total, dtype=np.int64),
        total,
        42,
        True,
        progress,
        0,
    )
    mode, label, win_rate, is_base = run_single_task_optimized(args)
    assert (mode, label, is_base) == ("Single", "prueba", True)
    assert 0.0 <= win_rate <= 100.0
    assert progress.get_nowait() == ("chunk", 0, total)


def test_worker_accepts_multiple_manual_enemies_with_shared_selection():
    total = 200
    enemies = [
        FIGHTER | {"enemy_name": "Swordsman"},
        FIGHTER | {"enemy_name": "Brute", "S": 4, "main_weapon": "Mace"},
    ]
    indices = np.tile(np.array([0, 1], dtype=np.int64), total // 2)
    args = (
        "Single", "multiple", FIGHTER, "custom", enemies, [], indices,
        total, 77, True, None, 0, 0,
    )
    mode, label, win_rate, is_base = run_single_task_optimized(args)
    assert (mode, label, is_base) == ("Single", "multiple", True)
    assert 0.0 <= win_rate <= 100.0


def test_random_enemy_equipment_is_legal_and_levels_are_applied():
    rng = np.random.default_rng(9)
    config = _random_enemy_config("Human warrior", 4, rng)
    legal = ENEMY_PROFILES["Human warrior"]["equipment"]
    assert config["main_weapon"] in {name for name, *_ in legal["main"]}
    assert config["off_hand"] in {name for name, *_ in legal["off"]}
    assert config["armor"] in {name for name, *_ in legal["armor"]}
    assert sum(config[attr] - ENEMY_PROFILES["Human warrior"][attr]
               for attr in ("WS", "S", "T", "W", "I", "A")) + len(config["skills"]) == 4
    if config["main_weapon"] in TWO_HANDED_WEAPONS:
        assert config["off_hand"] in {"None", "Shield", "Dagger", "Mace", "Axe", "Sword"}


def test_enemy_variants_have_expected_shape():
    enemies, owners = _build_enemy_variants(["Zombie", "Vampire"], 2, 123, 5)
    assert enemies.shape == (10, 38)
    assert owners.tolist() == [0] * 5 + [1] * 5


def test_house_rules_are_applied_to_random_enemy_variants():
    enemies, _owners = _build_enemy_variants(
        ["Zombie"], 0, 123, 2,
        house_rule_config={
            "house_rule_offhand_penalty": True,
            "house_rule_hard_armour": True,
        },
    )
    assert np.all(enemies[:, engine.FIGHTER_OFFHAND_HIT_PENALTY] == 1)
    assert np.all(enemies[:, engine.FIGHTER_HARD_ARMOUR] == 1)


def test_vectorized_engine_has_no_compilation_pause():
    total = 10_000
    names = ["Human warrior", "Orc"]
    indices = _generate_shared_enemy_selection(
        names, total, 77, ENEMY_VARIANTS_PER_PROFILE
    )
    args = (
        "Single", "performance", FIGHTER, "sample", None, names, indices,
        total, 77, True, None, 0, 0,
    )
    started = time.perf_counter()
    result = run_single_task_optimized(args)
    elapsed = time.perf_counter() - started
    assert 0.0 <= result[2] <= 100.0
    assert elapsed < 3.0


def test_simulation_batch_is_split_into_small_chunks(monkeypatch):
    candidate = engine._make_fighter(FIGHTER)
    enemies = np.asarray([engine._make_fighter(FIGHTER | {"main_weapon": "Mace"})])
    sizes = []

    def fake_kernel(_candidate, _enemy, amount, _seed):
        sizes.append(amount)
        return amount, amount

    monkeypatch.setattr(engine, "_simulate_simple_native", fake_kernel)
    total = 250_000
    wins, resolved = engine._simulate_batch(
        candidate, enemies, np.zeros(total, dtype=np.int8), total, 42
    )
    assert sizes == [100_000, 100_000, 50_000]
    assert (wins, resolved) == (total, total)


def test_simulation_batch_honours_a_cancellation_request():
    cancel_event = threading.Event()
    cancel_event.set()
    candidate = engine._make_fighter(FIGHTER)
    enemies = np.asarray([engine._make_fighter(FIGHTER)])
    with pytest.raises(engine.SimulationCancelled):
        engine._simulate_batch(
            candidate, enemies, np.zeros(100, dtype=np.int8), 100, 42,
            cancel_event,
        )


def test_numpy_combat_checks_for_cancellation_during_resolution(monkeypatch):
    class CancelAfterChecks:
        def __init__(self):
            self.checks = 0

        def is_set(self):
            self.checks += 1
            return self.checks >= 3

    monkeypatch.setattr(engine, "_simulate_simple_native", None)
    candidate = engine._make_fighter(FIGHTER)
    enemies = np.asarray([engine._make_fighter(FIGHTER)])
    with pytest.raises(engine.SimulationCancelled):
        engine._simulate_batch(
            candidate, enemies, np.zeros(1_000, dtype=np.int8), 1_000, 42,
            CancelAfterChecks(),
        )


def test_task_runner_stops_before_starting_when_cancelled():
    cancel_event = threading.Event()
    cancel_event.set()
    task = (
        "Single", "cancel", FIGHTER, "custom", FIGHTER,
        [], np.zeros(100, dtype=np.int8), 100, 42, True, None, 0, 0,
    )
    with pytest.raises(engine.SimulationCancelled):
        CombatLabApp._run_tasks(
            [task], None, 100, cancel_event=cancel_event
        )


def test_native_route_only_accepts_simple_fighters(monkeypatch):
    monkeypatch.setattr(engine, "_simulate_simple_native", lambda *_args: (0, 0))
    simple = engine._make_fighter(FIGHTER)
    assert engine._can_use_native_kernel(simple, simple)

    skilled = engine._make_fighter(FIGHTER | {"skills": ["Strongman"]})
    poisoned = engine._make_fighter(FIGHTER | {"main_poison": "Black Lotus"})
    special = engine._make_fighter(FIGHTER | {"main_weapon": "Steel whip"})
    assert not engine._can_use_native_kernel(skilled, simple)
    assert not engine._can_use_native_kernel(poisoned, simple)
    assert not engine._can_use_native_kernel(special, simple)


def test_effective_key_ignores_equipment_specific_skills_when_inert():
    base = FIGHTER | {"skills": []}
    inert = FIGHTER | {"skills": ["Axe Master", "Shield Strike"]}
    assert effective_fighter_key(base) == effective_fighter_key(inert)


def test_effective_key_keeps_equipment_specific_skills_when_active():
    axe = FIGHTER | {"main_weapon": "Axe", "skills": []}
    axe_master = axe | {"skills": ["Axe Master"]}
    shield = FIGHTER | {"off_hand": "Shield", "skills": []}
    shield_strike = shield | {"skills": ["Shield Strike"]}
    assert effective_fighter_key(axe) != effective_fighter_key(axe_master)
    assert effective_fighter_key(shield) != effective_fighter_key(shield_strike)


def test_effective_key_never_drops_general_combat_skills():
    for skill in ("Expert Fighter", "Mighty Blow", "Resilient"):
        upgraded = FIGHTER | {"skills": [skill]}
        assert effective_fighter_key(FIGHTER) != effective_fighter_key(upgraded)


def test_every_advertised_combat_skill_has_an_engine_mask():
    for skill in engine.SKILLS:
        assert engine._skill_mask([skill]), skill


def test_new_permanent_skill_bonuses_are_encoded_in_fighter():
    fighter = engine._make_fighter(FIGHTER | {
        "skills": ["Iron Sinews", "Monstrous", "Red Fury", "Very Tough"],
    })
    assert fighter[1] == FIGHTER["S"] + 1
    assert fighter[3] == FIGHTER["W"] + 1
    assert fighter[5] == FIGHTER["A"] + 1
    assert fighter[8] == engine._armor_base_save(FIGHTER["armor"]) - 1


def test_high_elf_melee_skills_are_encoded():
    mask = engine._skill_mask([
        "Elven Agility", "Miniath", "Sure Strike", "Luck",
    ])
    assert mask & engine.SKILL_ELVEN_AGILITY
    assert mask & engine.SKILL_MINIATH
    assert mask & engine.SKILL_REROLL_WOUNDS
    assert mask & engine.SKILL_LUCK


def test_new_permanent_skill_bonuses_are_encoded_in_fighter():
    fighter = engine._make_fighter(FIGHTER | {
        "skills": ["Iron Sinews", "Monstrous", "Red Fury", "Very Tough"],
    })
    assert fighter[1] == FIGHTER["S"] + 1
    assert fighter[3] == FIGHTER["W"] + 1
    assert fighter[5] == FIGHTER["A"] + 1
    assert fighter[8] == engine._armor_base_save(FIGHTER["armor"]) - 1


def test_high_elf_melee_skills_are_encoded():
    mask = engine._skill_mask([
        "Elven Agility", "Miniath", "Sure Strike",
    ])
    assert mask & engine.SKILL_ELVEN_AGILITY
    assert mask & engine.SKILL_MINIATH
    assert mask & engine.SKILL_REROLL_WOUNDS


def test_task_deduplication_preserves_aliases_for_inert_skills():
    base_task = ("Single", "base", FIGHTER, None, None, None, None, 100, 1, True)
    inert_task = (
        "Single", "master without axe", FIGHTER | {"skills": ["Axe Master"]},
        None, None, None, None, 100, 2, False,
    )
    unique, aliases = CombatLabApp._deduplicate_tasks([base_task, inert_task])
    assert len(unique) == 1
    assert aliases[("Single", "base")] == [
        ("base", True),
        ("master without axe", False),
    ]


def test_task_deduplication_keeps_active_skills_separate():
    base_task = ("Single", "base", FIGHTER, None, None, None, None, 100, 1, True)
    active_task = (
        "Single", "esgrima", FIGHTER | {"skills": ["Expert Swordsman"]},
        None, None, None, None, 100, 2, False,
    )
    unique, _aliases = CombatLabApp._deduplicate_tasks([base_task, active_task])
    assert len(unique) == 2


def test_tree_sort_keys_never_mix_incompatible_types():
    values = ["Sword + Shield", "★ 62.40% (+3.20%)", "", "+1 HA", "−2.5%"]
    sorted(values, key=CombatLabApp._tree_sort_key)


def test_analysis_default_is_one_hundred_thousand():
    assert DEFAULT_COMBO_SIMULATIONS == 100_000


def test_luck_amulet_is_not_an_upgrade_anymore():
    upgrades = CombatLabApp._build_upgrade_list(object(), FIGHTER)
    assert all("Amuleto" not in label for label, _upgrade in upgrades)


def test_equipment_catalog_contains_armour_objects_and_consumables():
    options = CombatLabApp._equipment_options()
    labels = {label for label, _kind, _value in options}
    kinds = {label: kind for label, kind, _value in options}
    assert {"Light armour", "Helmet", "Lucky charm"} <= labels
    assert {"Crimson Shade", "Black Lotus", "Spider Spittle"} <= labels
    assert {"Mad Cap Mushrooms", "Head-splitter mushrooms"} <= labels
    assert kinds["Sea Dragon cloak"] == "cloak"


def test_candidate_equipment_menu_keeps_poisons_in_weapon_selectors():
    assert set(EQUIPMENT_SELECTOR_OPTIONS).isdisjoint(
        poison for poison in POISONS if poison != "No Poison"
    )


def test_equipment_loadout_preserves_initial_optional_equipment():
    candidate = FIGHTER | {
        "armor": "Heavy armour",
        "has_helmet": True,
        "has_luck_amulet": True,
    }
    equipped = CombatLabApp._apply_equipment_items(candidate, (
        ("Light armour", "armor", "Light armour"),
        ("Lucky charm", "amulet", True),
    ))
    assert equipped["armor"] == "Light armour"
    assert equipped["has_helmet"]
    assert equipped["has_luck_amulet"]


def test_sea_dragon_cloak_is_applied_as_optional_equipment():
    candidate = FIGHTER | {"armor": "Light armour"}
    equipped = CombatLabApp._apply_equipment_items(candidate, (
        ("Sea Dragon cloak", "cloak", True),
    ))
    assert equipped["armor"] == "Light armour"
    assert equipped["has_sea_dragon_cloak"]
    assert "Sea Dragon cloak" in CombatLabApp._owned_optional_equipment(equipped)


def test_selecting_owned_armour_or_helmet_keeps_the_exact_base_profile():
    candidate = FIGHTER | {
        "armor": "Toughened leathers", "has_helmet": True,
        "main_poison": "No Poison", "offhand_poison": "No Poison",
    }
    helmet = CombatLabApp._apply_equipment_items(candidate, (
        ("Helmet", "helmet", True),
    ))
    leather = CombatLabApp._apply_equipment_items(candidate, (
        ("Toughened leathers", "armor", "Toughened leathers"),
    ))
    assert helmet == candidate
    assert leather == candidate
    assert effective_fighter_key(helmet) == effective_fighter_key(candidate)
    assert effective_fighter_key(leather) == effective_fighter_key(candidate)
    task_tail = ("custom", FIGHTER, [], np.zeros(10, dtype=np.int8), 10, 42)
    tasks = [
        ("Single", "BASELINE", candidate, *task_tail, True),
        ("Single", "Helmet", helmet, *task_tail, False),
        ("Single", "Toughened leathers", leather, *task_tail, False),
    ]
    unique, aliases = CombatLabApp._deduplicate_tasks(tasks)
    assert len(unique) == 1
    assert [label for label, _is_base in aliases[("Single", "BASELINE")]] == [
        "BASELINE", "Helmet", "Toughened leathers",
    ]


def test_equipment_loadout_preserves_and_fills_initial_poison_slots():
    candidate = FIGHTER | {
        "main_poison": "Black Lotus", "offhand_poison": "No Poison",
    }
    equipped = CombatLabApp._apply_equipment_items(candidate, (
        ("Black Lotus", "poison", "Black Lotus"),
        ("Black Venom", "poison", "Black Venom"),
    ))
    assert equipped["main_poison"] == "Black Lotus"
    assert equipped["offhand_poison"] == "Black Venom"


def test_owned_equipment_is_deducted_once_from_combination_cost():
    candidate = FIGHTER | {
        "armor": "Light armour", "has_helmet": True,
        "main_poison": "Black Lotus", "offhand_poison": "No Poison",
    }
    costs = {"Light armour": 20.0, "Helmet": 10.0, "Black Lotus": 13.5}
    assert CombatLabApp._equipment_acquisition_costs(
        ("Helmet", "Light armour", "Black Lotus"), candidate, costs
    ) == (0.0, 0.0, 0.0)
    assert CombatLabApp._equipment_acquisition_costs(
        ("Black Lotus", "Black Lotus"), candidate, costs
    ) == (0.0, 13.5)
    display, total = CombatLabApp._equipment_cost_display((0.0, 13.5))
    assert display == "0 + 13.5 = 13.5 gc"
    assert total == 13.5


def test_only_poison_can_be_selected_twice():
    armor = ("Light armour", "armor", "Light armour")
    amulet = ("Lucky charm", "amulet", True)
    poison = ("Black Lotus", "poison", "Black Lotus")
    legal = CombatLabApp._equipment_combination_is_legal
    assert not legal((armor, armor))
    assert not legal((amulet, amulet))
    assert legal((poison, poison))


def test_distinct_preparations_can_be_combined_but_not_duplicated():
    first = ("Crimson Shade", "preparation", "Crimson Shade")
    second = ("Mandrake Root", "preparation", "Mandrake Root")
    legal = CombatLabApp._equipment_combination_is_legal
    assert legal((first, second))
    assert not legal((first, first))


def test_equipment_loadout_accumulates_preparations():
    equipped = CombatLabApp._apply_equipment_items(FIGHTER, (
        ("Crimson Shade", "preparation", "Crimson Shade"),
        ("Mandrake Root", "preparation", "Mandrake Root"),
    ))
    assert equipped["preparations"] == ["Crimson Shade", "Mandrake Root"]


def test_equipment_loadouts_can_include_legal_triples():
    armor = ("Light armour", "armor", "Light armour")
    helmet = ("Helmet", "helmet", True)
    poison = ("Black Lotus", "poison", "Black Lotus")
    loadouts = CombatLabApp._equipment_loadouts([armor, helmet, poison], 3)
    item_sets = {items for _labels, items in loadouts}
    assert (armor, helmet, poison) in item_sets
    assert (poison, poison, poison) not in item_sets
    assert all(1 <= len(items) <= 3 for _labels, items in loadouts)


def test_equipment_maximum_one_only_generates_individual_items():
    options = CombatLabApp._equipment_options()[:3]
    loadouts = CombatLabApp._equipment_loadouts(options, 1)
    assert len(loadouts) == len(options)
    assert all(len(items) == 1 for _labels, items in loadouts)


def test_weapon_loadouts_cover_the_four_hand_configurations():
    loadouts = CombatLabApp._weapon_loadouts(
        ["Sword", "Mace", "Double-handed weapon", "Bagh Nakh"]
    )
    assert ("Single", "Sword", "None") in loadouts
    assert ("Shield", "Sword", "Shield") in loadouts
    assert ("Dual", "Sword", "Mace") in loadouts
    assert ("Dual", "Mace", "Sword") in loadouts
    assert ("TwoHand", "Double-handed weapon", "None") in loadouts
    assert ("TwoHand", "Bagh Nakh", "None") in loadouts
    assert ("Single", "None", "None") in loadouts


def test_two_handed_weapons_are_not_generated_as_dual_combinations():
    loadouts = CombatLabApp._weapon_loadouts(["Sword", "Double-handed weapon"])
    assert all(
        main != "Double-handed weapon" or mode == "TwoHand"
        for mode, main, _off in loadouts
    )


def test_weapons_that_demand_attention_do_not_get_a_second_weapon():
    loadouts = CombatLabApp._weapon_loadouts(
        ["Spear", "Morning star", "Choppa", "Squig prodder", "Dagger"]
    )
    assert not any(
        mode == "Dual" and main in {"Spear", "Morning star", "Choppa", "Squig prodder"}
        for mode, main, _off in loadouts
    )


def test_spiked_gauntlet_is_the_exception_for_difficult_weapons():
    loadouts = CombatLabApp._weapon_loadouts(
        ["Choppa", "Squig prodder", "Spiked gauntlet"]
    )
    assert ("Dual", "Choppa", "Spiked gauntlet") in loadouts
    assert ("Dual", "Squig prodder", "Spiked gauntlet") in loadouts


def test_sun_gauntlet_is_only_generated_in_the_off_hand():
    loadouts = CombatLabApp._weapon_loadouts(["Sword", "Sun gauntlet"])
    assert not any(main == "Sun gauntlet" for _mode, main, _off in loadouts)
    assert ("Dual", "Sword", "Sun gauntlet") in loadouts


def test_weapon_loadouts_use_selected_defenses_and_respect_exceptions():
    loadouts = CombatLabApp._weapon_loadouts(
        ["Sword", "Spear", "Morning star", "Choppa"],
        ("Shield", "Buckler"),
    )
    assert ("Shield", "Sword", "Shield") in loadouts
    assert ("Shield", "Sword", "Buckler") in loadouts
    assert ("Shield", "Spear", "Buckler") in loadouts
    assert ("Shield", "Choppa", "Shield") in loadouts
    assert ("Shield", "Choppa", "Buckler") not in loadouts
    assert not any(mode == "Shield" and main == "Morning star" for mode, main, _off in loadouts)


def test_materialized_weapon_loadouts_assign_material_to_each_weapon_only():
    loadouts = CombatLabApp._materialized_weapon_loadouts(
        ["Sword", "Dagger"], ("Normal", "Gromril"), ("Buckler",)
    )
    assert ("Shield", "Sword", "Buckler", "Gromril", "Normal") in loadouts
    assert ("Dual", "Sword", "Dagger", "Gromril", "Normal") in loadouts
    assert ("Dual", "Sword", "Dagger", "Normal", "Gromril") in loadouts
    assert all(
        off_material == "Normal"
        for _mode, _main, off, _main_material, off_material in loadouts
        if off in {"None", "Shield", "Buckler"}
    )


def test_weapon_cost_uses_material_multiplier_and_formats_total():
    costs = {"Sword": 10.0, "Buckler": 5.0}
    main = CombatLabApp._weapon_cost("Sword", "Gromril", costs)
    off = CombatLabApp._weapon_cost("Buckler", "Normal", costs)
    display, total = CombatLabApp._weapon_cost_display(main, off)
    assert main == 40.0
    assert total == 45.0
    assert display == "40 + 5 = 45 gc"


def test_owned_weapons_are_deducted_once_regardless_of_hand():
    candidate = {
        "main_weapon": "Sword", "main_weapon_material": "Gromril",
        "off_hand": "Dagger", "offhand_material": "Normal",
    }
    costs = {"Sword": 10.0, "Dagger": 2.0}
    assert CombatLabApp._weapon_acquisition_costs(
        "Dagger", "Sword", "Normal", "Gromril", candidate, costs,
    ) == (0.0, 0.0)
    assert CombatLabApp._weapon_acquisition_costs(
        "Sword", "Sword", "Gromril", "Gromril", candidate, costs,
    ) == (0.0, 40.0)


def test_mirrored_simple_weapons_share_one_effective_profile_with_one_attack():
    sword_dagger = FIGHTER | {
        "A": 1, "main_weapon": "Sword", "off_hand": "Dagger",
        "main_weapon_material": "Gromril", "offhand_material": "Normal",
        "main_poison": "Black Lotus", "offhand_poison": "No Poison",
    }
    dagger_sword = FIGHTER | {
        "A": 1, "main_weapon": "Dagger", "off_hand": "Sword",
        "main_weapon_material": "Normal", "offhand_material": "Gromril",
        "main_poison": "No Poison", "offhand_poison": "Black Lotus",
    }
    first = CombatLabApp._canonical_weapon_candidate(sword_dagger, "Dual")
    second = CombatLabApp._canonical_weapon_candidate(dagger_sword, "Dual")
    assert first == second
    assert effective_fighter_key(first) == effective_fighter_key(second)
    task_tail = ("custom", FIGHTER, [], np.zeros(10, dtype=np.int8), 10, 42)
    tasks = [
        ("Dual", "Sword || Dagger", first, *task_tail, False),
        ("Dual", "Dagger || Sword", second, *task_tail, False),
    ]
    unique, aliases = CombatLabApp._deduplicate_tasks(tasks)
    assert len(unique) == 1
    assert [label for label, _is_base in aliases[("Dual", "Sword || Dagger")]] == [
        "Sword || Dagger", "Dagger || Sword",
    ]


def test_mirrored_weapons_remain_distinct_when_the_main_hand_matters():
    two_attacks = FIGHTER | {
        "A": 2, "main_weapon": "Sword", "off_hand": "Dagger",
    }
    axe_master = FIGHTER | {
        "A": 1, "main_weapon": "Axe", "off_hand": "Dagger",
        "skills": ["Axe Master"],
    }
    assert CombatLabApp._canonical_weapon_candidate(
        two_attacks, "Dual"
    ) == two_attacks
    assert CombatLabApp._canonical_weapon_candidate(
        axe_master, "Dual"
    ) == axe_master


def test_every_warrior_owns_exactly_one_free_normal_dagger():
    costs = {"Dagger": 2.0}
    assert CombatLabApp._weapon_acquisition_costs(
        "Dagger", "None", "Normal", "Normal", {}, costs,
    ) == (0.0, 0.0)
    assert CombatLabApp._weapon_acquisition_costs(
        "Dagger", "Dagger", "Normal", "Normal", {}, costs,
    ) == (0.0, 2.0)
    assert CombatLabApp._weapon_acquisition_costs(
        "Dagger", "None", "Gromril", "Normal", {}, costs,
    ) == (8.0, 0.0)


def test_empty_hands_have_zero_acquisition_cost_and_a_clear_label():
    assert CombatLabApp._weapon_acquisition_costs(
        "None", "None", "Normal", "Normal", {}, {}
    ) == (0.0, 0.0)
    assert CombatLabApp._weapon_loadout_label(
        "None", "None", "Normal", "Normal"
    ) == "Unarmed || None"
    assert engine._make_fighter(FIGHTER | {"main_weapon": "None"})[6] == WEAPON_UNARMED


def test_house_rules_adjust_armour_and_junk_costs_with_ceiling():
    class Flag:
        def __init__(self, value):
            self.value = value

        def get(self):
            return self.value

    app = object.__new__(CombatLabApp)
    app.house_rule_vars = {
        "cheap_armour": Flag(True),
        "expensive_junk": Flag(True),
    }
    adjusted = app._costs_with_house_rules({
        "Light armour": 25.0, "Helmet": 10.0, "Shield": 5.0,
        "Buckler": 5.0, "Mace": 3.0,
    })
    assert adjusted["Light armour"] == 13.0
    assert adjusted["Helmet"] == 5.0
    assert adjusted["Shield"] == adjusted["Buckler"] == 3.0
    assert adjusted["Mace"] == adjusted["Sling"] == 5.0


def test_weapon_export_includes_total_cost_and_motta_index():
    table_data = (
        {
            "Single": [40.0, [["Sword || None", 50.0, 10.0]]],
            "Shield": [40.0, []], "Dual": [40.0, []], "TwoHand": [40.0, []],
        },
        {"Single": "Sword"},
        {"Sword || None": (10.0, 0.0)},
    )
    headers, rows = CombatLabApp._result_export_rows("weapons", table_data)
    row = next(value for value in rows if value[0] == "Sword")
    assert "Cost" in headers
    assert "MOTTA Score" in headers
    assert row[headers.index("Cost")] == 10.0
    assert np.isclose(
        row[headers.index("MOTTA Score")],
        10.0 / np.hypot(10.0, 0.01) * 507.4,
    )


def test_regularized_motta_is_large_at_zero_cost_linear_and_symmetric():
    positive = CombatLabApp._motta_index(2.0, 0.0)
    negative = CombatLabApp._motta_index(-2.0, 0.0)
    assert np.isclose(positive, 101_480.0)
    assert negative == -positive
    assert CombatLabApp._motta_index(0.0, 0.0) == 0.0
    assert np.isclose(
        CombatLabApp._motta_index(2.0, 10.0),
        2.0 / np.hypot(10.0, 0.01) * 507.4,
    )


def test_two_poisons_are_applied_one_to_each_hand():
    equipped = CombatLabApp._apply_equipment_items(FIGHTER, (
        ("Black Lotus", "poison", "Black Lotus"),
        ("Black Venom", "poison", "Black Venom"),
    ))
    assert equipped["main_poison"] == "Black Lotus"
    assert equipped["offhand_poison"] == "Black Venom"


def test_optimal_view_only_uses_visible_equipment_modes():
    values = {
        "Single": (55.0, 1.0),
        "Shield": (70.0, 2.0),
        "Dual": (65.0, 3.0),
        "TwoHand": (60.0, 4.0),
    }
    assert CombatLabApp._best_visible_mode(values, {"Single", "Shield", "Dual"}) == "Shield"
    assert CombatLabApp._best_visible_mode(values, {"Single", "Dual"}) == "Dual"


def test_optimal_view_handles_sparse_weapon_modes():
    values = {"Shield": (61.0, 2.0)}
    assert CombatLabApp._best_visible_mode(values, {"Single", "Shield"}) == "Shield"
    assert CombatLabApp._best_visible_mode(values, {"Single", "Dual"}) is None


def test_combo_parts_keep_one_canonical_order():
    parts = CombatLabApp._combo_parts("+1 A + Strongman")
    assert parts == ("+1 A", "Strongman")


def test_combo_search_ignores_case_accents_and_component_order():
    parts = CombatLabApp._combo_parts("+1 A + Strongman")
    assert CombatLabApp._combo_matches(parts, "STRONGMAN")
    assert CombatLabApp._combo_matches(parts, "+1 a")
    assert not CombatLabApp._combo_matches(parts, "Resilient")
