from mordheim_combat_lab.units import format_movement, movement_to_inches


def test_spanish_profile_movement_normalizes_to_inches():
    assert movement_to_inches(8, "es") == 3
    assert movement_to_inches(10, "es") == 4
    assert movement_to_inches(12, "es") == 5
    assert movement_to_inches(15, "es") == 6
    assert movement_to_inches("5D6", "es") == "2D6"


def test_movement_format_follows_the_selected_locale():
    assert format_movement(4, "en") == '4"'
    assert format_movement(4, "es") == "10 cm"
    assert format_movement(5, "es") == "12 cm"
    assert format_movement("2D6", "en") == '2D6"'
    assert format_movement("2D6", "es") == "5D6 cm"
