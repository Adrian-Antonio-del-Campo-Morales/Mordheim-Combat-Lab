from mordheim_combat_lab import Characteristics, FighterBuild, compile_fighter
from mordheim_combat_lab.ui.services import CombatCatalogue


def test_free_selection_build_compiles_with_runtime_equipment():
    catalogue = CombatCatalogue()
    sword = next(item_id for item_id, name in catalogue.weapons(None) if name == "Sword")
    shield = next(item_id for item_id, name in catalogue.off_hand_options(None) if name == "Shield")

    fighter = compile_fighter(
        FighterBuild(
            "mordheim",
            Characteristics(4, 3, 3, 1, 4, 1),
            main_weapon_id=sword,
            off_hand_id=shield,
        )
    )

    assert fighter.fighter_id == "custom:custom"
