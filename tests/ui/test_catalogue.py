from mordheim_combat_lab import Characteristics, FighterBuild, compile_fighter
from mordheim_combat_lab.ui.services import CombatCatalogue


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


def test_profile_build_can_apply_user_edited_characteristics():
    fighter = compile_fighter(FighterBuild(
        "mordheim", Characteristics(5, 4, 4, 2, 5, 2),
        band_id="mercenaries", profile_id="mercenary-captain",
    ))

    assert fighter.fighter_id == "mercenaries:mercenary-captain"
    assert fighter.characteristics == Characteristics(5, 4, 4, 2, 5, 2)
