from mordheim_combat_lab.candidate_catalog import bands_for_category, find_profile, load_bands
import numpy as np

from mordheim_combat_lab.engine import (
    _attack_is_last, _attack_strength, _combat_initiative, _extra_armour_penalty, _make_fighter,
    _parry_profile, _phase_attack_count, _skill_mask, _vector_injury,
    STATE_KNOCKED_DOWN, STATE_STUNNED,
    FIGHTER_FRENZY, FIGHTER_NATURAL_ARMOUR_SAVE,
    FIGHTER_NATURAL_ARMOUR_UNMODIFIED,
)
from mordheim_combat_lab.rules import (
    ARMOR_HEAVY,
    SKILL_CHARGE,
    SKILL_EXPERT,
    SKILL_STRIKE_TO_INJURE,
    WEAPON_SWORD, WEAPON_MACE,
    WEAPON_BROADSWORD, WEAPON_CATHAYAN_LONGSWORD, WEAPON_CHAIN_STICKS,
    WEAPON_DRAGON_SWORD, WEAPON_QUARTER_STAFF, WEAPON_STARBLADE,
)


def test_combat_lab_catalog_contains_both_normalized_collections():
    bands = load_bands()
    assert len(bands) == 83
    assert sum(len(band.profiles) for band in bands) == 540
    assert len(bands_for_category("trollheim")) == 34
    assert len(bands_for_category("core")) == 6
    assert all("profane" not in band.band_id for band in bands)


def test_core_mercenary_uses_canonical_english_options_and_skills():
    captain = find_profile("mercenaries", "mercenary-captain")
    assert {"Sword", "Dagger", "Double-handed weapon"} <= set(captain.weapons)
    assert {"Light armour", "Heavy armour"} <= set(captain.armors)
    assert captain.defenses == ("Shield", "Buckler")
    assert captain.skills_by_category["combat"] == (
        "Strike to Injure", "Combat Master", "Weapons Training",
        "Web of Steel", "Expert Swordsman", "Step Aside",
    )


def test_english_equipment_reaches_existing_numeric_engine_codes():
    fighter = _make_fighter({
        "WS": 3, "S": 3, "T": 3, "W": 1, "I": 3, "A": 1,
        "main_weapon": "Sword", "off_hand": "Shield", "armor": "Heavy armour",
    })
    assert fighter[6] == WEAPON_SWORD
    assert fighter[17] == ARMOR_HEAVY
    assert fighter[8] == 4  # 5+ heavy armour, improved by the shield.


def test_freely_translated_mordheim_skill_does_not_replace_mordheim_rule():
    mordheim = _skill_mask(("Strike to Injure", "Web of Steel"))
    legacy = _skill_mask(("Expert Fighter",))
    assert mordheim & SKILL_STRIKE_TO_INJURE
    assert mordheim & SKILL_CHARGE
    assert not mordheim & SKILL_EXPERT
    assert legacy & SKILL_EXPERT


def _fighter(weapon, *, attacks=1, skills=()):
    return _make_fighter({
        "WS": 3, "S": 3, "T": 3, "W": 1, "I": 3, "A": attacks,
        "main_weapon": weapon, "off_hand": "None", "armor": "No Armour",
        "skills": skills,
    })


def test_new_source_weapons_have_distinct_engine_behaviour():
    chain_sticks = _fighter("Chain Sticks", attacks=1)
    assert chain_sticks[6] == WEAPON_CHAIN_STICKS
    assert _phase_attack_count(chain_sticks, True) == 3
    assert _phase_attack_count(chain_sticks, False) == 1

    quarter_staff = _fighter("Quarter Staff")
    assert quarter_staff[6] == WEAPON_QUARTER_STAFF
    assert _phase_attack_count(quarter_staff, True) == 2
    assert _combat_initiative(quarter_staff) == 4
    assert _parry_profile(quarter_staff)[0] == 1

    cathayan = _fighter("Cathayan Longsword")
    assert cathayan[0] == 4
    assert _combat_initiative(cathayan) == 4
    assert _extra_armour_penalty(cathayan, WEAPON_CATHAYAN_LONGSWORD) == 1


def test_broadsword_and_source_parry_weapons_are_not_approximated_as_swords():
    broadsword = _fighter("Broadsword")
    assert broadsword[6] == WEAPON_BROADSWORD
    assert _attack_is_last(broadsword, WEAPON_BROADSWORD, 0)
    strongman = _fighter("Broadsword", skills=("Strongman",))
    assert not _attack_is_last(strongman, WEAPON_BROADSWORD, 0)
    assert _parry_profile(_fighter("Dragon Sword"))[0] == 1
    assert _fighter("Dragon Sword")[6] == WEAPON_DRAGON_SWORD
    assert _parry_profile(_fighter("Starblade"))[0] == 1
    assert _fighter("Starblade")[6] == WEAPON_STARBLADE


def test_dark_elf_blade_is_an_upgrade_with_its_own_wicked_edge_rule():
    corsair = find_profile("dark-elves", "corsairs")
    assert "Dark Elf blade" in corsair.materials

    class FixedRoll:
        @staticmethod
        def integers(_low, _high, count):
            return np.full(count, 2, dtype=np.int8)

    ordinary = _vector_injury(FixedRoll(), 1, WEAPON_SWORD, False, False, False, False, 0)
    wicked = _vector_injury(FixedRoll(), 1, WEAPON_SWORD, False, False, False, False, 0, True)
    assert ordinary[0] == STATE_KNOCKED_DOWN
    assert wicked[0] == STATE_STUNNED


def test_profile_rules_are_converted_to_engine_traits():
    cold_one = find_profile("dark-elves", "cold-one-beasthounds")
    assert cold_one.combat_traits["natural_armour_save"] == 6
    assert cold_one.combat_traits["natural_armour_unmodified"]
    fighter = _make_fighter({
        **cold_one.stats, **cold_one.combat_traits,
        "skills": cold_one.combat_traits["starting_skills"],
        "main_weapon": "Natural attacks", "off_hand": "None", "armor": "No Armour",
    })
    assert fighter[FIGHTER_NATURAL_ARMOUR_SAVE] == 6
    assert fighter[FIGHTER_NATURAL_ARMOUR_UNMODIFIED]

    totem = find_profile("amazons-mordheim", "totem-warriors")
    frenzy = _make_fighter({
        **totem.stats, **totem.combat_traits, "skills": (),
        "main_weapon": "Sword", "off_hand": "None", "armor": "No Armour",
    })
    assert frenzy[FIGHTER_FRENZY]


def test_hard_head_cancels_the_club_concussion_rule():
    class FixedRoll:
        @staticmethod
        def integers(_low, _high, count):
            return np.full(count, 2, dtype=np.int8)

    concussion = _vector_injury(FixedRoll(), 1, WEAPON_MACE, False, False, False, False, 0)
    hard_head = _vector_injury(
        FixedRoll(), 1, WEAPON_MACE, False, False, False, False, 0,
        concussion_immune=True,
    )
    assert concussion[0] == STATE_STUNNED
    assert hard_head[0] == STATE_KNOCKED_DOWN


def test_troll_vomit_is_an_explicit_optional_attack_not_a_translated_weapon():
    troll = find_profile("orc-mob", "troll")
    assert {"Natural attacks", "Vomit attack"} <= set(troll.weapons)


def test_profile_rules_reuse_equivalent_spanish_engine_mechanics():
    pilgrims = find_profile("bretonnian-chapel-guard", "battle-pilgrims")
    spider = find_profile("forest-goblins", "gigantic-spider")
    assert "Hatred" in pilgrims.combat_traits["starting_skills"]
    assert spider.combat_traits["poisonous_injury"] is True
    assert find_profile("black-orcs", "orc-nuttaz").combat_traits["starting_skills"] == ("Extra Attack",)
    assert find_profile("night-goblins-mic", "fanatics").combat_traits["starting_skills"] == ("Always Strikes First",)
    assert find_profile("cursed-cavalcade", "great-bear").combat_traits["maddened_with_pain"] is True
    assert find_profile("battle-monks-of-cathay", "raging-peasants").combat_traits["injury_profile"] == 2
    assert find_profile("night-goblins-web", "snotlings").combat_traits["injury_profile"] == 1
    vomit = _fighter("Vomit attack", attacks=3)
    assert _phase_attack_count(vomit, True) == 1
    assert _attack_strength(vomit, vomit[6], False) == 5


def test_no_pain_is_not_cancelled_by_jump_up():
    class FixedRoll:
        @staticmethod
        def integers(_low, _high, count):
            return np.full(count, 3, dtype=np.int8)

    injury = _vector_injury(
        FixedRoll(), 1, WEAPON_SWORD, False, True, False, False, 0,
        no_pain=True,
    )
    assert injury[0] == STATE_KNOCKED_DOWN


def test_english_special_skill_names_reach_existing_mechanics():
    assert _skill_mask(("Step Aside",)) == _skill_mask(("Step Aside",))
    assert _skill_mask(("Ferocious Charge",)) == _skill_mask(("Ferocious Charge",))
    assert _skill_mask(("crushing blow",)) == _skill_mask(("Crushing Blow",))
    assert _skill_mask(("shield master",)) == _skill_mask(("Shield Mastery",))
