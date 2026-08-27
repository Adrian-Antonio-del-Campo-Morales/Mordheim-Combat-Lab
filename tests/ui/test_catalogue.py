from mordheim_combat_lab import Characteristics, FighterBuild, compile_fighter
from mordheim_combat_lab.ui.services import CombatCatalogue
from mordheim_combat_lab.catalog.loader import load_skills


def test_catalogue_exposes_kb_profiles_and_profile_equipment():
    catalogue = CombatCatalogue()
    choices = catalogue.profiles("mordheim", "mercenaries")
    captain = next(choice for choice in choices if choice.profile_id == "mercenary-captain")

    assert captain.name == "Mercenary captain"
    assert ("weapon.sword", "Sword") in catalogue.weapons(captain)
    assert catalogue.profile(captain)["characteristics"]["WS"] == 4
    assert (None, "Free hand") in catalogue.off_hand_options(captain)
    assert ("armour.no-armour", "No armour") in catalogue.armours(captain)
    assert catalogue.mechanic("weapon.sword")["hands"] == 1
    assert (None, "No helmet") in catalogue.helmets(captain)
    assert ("material.normal", "Normal") in catalogue.materials(captain)
    assert (None, "No preparation") in catalogue.preparations(captain)
    assert (None, "No poison") in catalogue.poisons(captain)
    assert ("defence.helmet", "Helmet") in catalogue.helmets(captain)
    assert {skill.id for skill in catalogue.skills(captain)} >= {"skill.mighty-blow", "skill.step-aside"}
    assert "skill.combat-master" not in {skill.id for skill in catalogue.skills(captain)}
    assert catalogue.profile_rules(captain)[0].name == "Leader"


def test_catalogue_exposes_runtime_options_for_free_selection():
    catalogue = CombatCatalogue()

    assert ("weapon.sword", "Sword") in catalogue.weapons(None)
    assert ("armour.no-armour", "No armour") in catalogue.armours(None)
    assert {skill.id for skill in catalogue.skills(None)} >= {"skill.mighty-blow", "skill.step-aside"}


def test_catalogue_filters_bands_by_the_legacy_collection_grades():
    catalogue = CombatCatalogue()

    core = catalogue.bands_for_categories({"core"})
    trollheim = catalogue.bands_for_categories({"trollheim"})

    assert core
    assert trollheim
    assert all("core" in package.band.get("categories", ()) for package in core)
    assert all("trollheim" in package.band.get("categories", ()) for package in trollheim)


def test_catalogue_limits_special_skills_to_the_selected_warband():
    catalogue = CombatCatalogue()
    amazon = catalogue.profiles("mordheim", "amazons-lustria")[0]
    arabian = catalogue.profiles("mordheim", "arabian-tomb-raiders")[0]
    lizardman = catalogue.profiles("mordheim", "lizardmen")[0]

    amazon_special = {skill.id for skill in catalogue.skills(amazon) if skill.category == "special"}
    arabian_special = {skill.id for skill in catalogue.skills(arabian) if skill.category == "special"}
    lizardman_special = {skill.id for skill in catalogue.skills(lizardman) if skill.category == "special"}

    assert amazon_special == set()
    assert arabian_special == set()
    assert lizardman_special == {"skill.bellowing-battle-roar"}


def test_catalogue_uses_a_trollheim_band_canonical_family_for_special_skills():
    catalogue = CombatCatalogue()
    lizardman = catalogue.profiles("trollheim", "lustria-lizardmen")[0]

    assert {skill.id for skill in catalogue.skills(lizardman) if skill.category == "special"} == {
        "skill.bellowing-battle-roar"
    }


def test_no_profile_receives_a_special_skill_from_another_band():
    catalogue = CombatCatalogue()
    skills = {str(skill["id"]): skill for skill in load_skills("mordheim")}

    for package in catalogue.bands_for_categories(set()):
        source_ids = {str(package.band["id"]), str(package.band.get("canonical_family") or "")}
        for choice in catalogue.profiles(package.collection, str(package.band["id"])):
            for skill in catalogue.skills(choice):
                if skill.category != "special":
                    continue
                assert any(
                    any(f"/{band_id}" in str(reference.get("url") or "") for band_id in source_ids if band_id)
                    for reference in skills[skill.id].get("source_refs") or ()
                )


def test_profile_build_can_apply_user_edited_characteristics():
    fighter = compile_fighter(FighterBuild(
        "mordheim", Characteristics(5, 4, 4, 2, 5, 2),
        band_id="mercenaries", profile_id="mercenary-captain",
    ))

    assert fighter.fighter_id == "mercenaries:mercenary-captain"
    assert fighter.characteristics == Characteristics(5, 4, 4, 2, 5, 2)
