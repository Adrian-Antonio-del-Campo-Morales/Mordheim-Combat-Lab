from mordheim_combat_lab.ui.preferences import load_preferences, save_preferences


def test_preferences_round_trip_arbitrary_ui_values(tmp_path, monkeypatch):
    path = tmp_path / "settings.json"
    monkeypatch.setattr("mordheim_combat_lab.ui.preferences.settings_path", lambda: path)

    save_preferences({"simulations": 12_000, "window_geometry": "1200x800"})

    assert load_preferences() == {"simulations": 12_000, "window_geometry": "1200x800"}
