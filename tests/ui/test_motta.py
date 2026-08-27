from mordheim_combat_lab.ui.services import motta_score


def test_motta_uses_the_legacy_cost_regularisation():
    assert motta_score(1.0, 10.0) == 50.73997463001903


def test_motta_requires_a_known_cost():
    assert motta_score(2.0, None) is None
