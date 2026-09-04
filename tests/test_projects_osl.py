# tests/test_projects_osl.py
from mini_highlight_advisor import projects


def test_settings_osl_roundtrip():
    s = projects.ProjectSettings(
        n=5, edge_hl=True, edge_extreme=False,
        edge_sens=0.5, relief_cap=True, per_region_norm=False,
    )
    # OSL params are optional; None when never used.
    assert getattr(s, "osl", None) is None
    d = projects._settings_to_dict(s)
    s2 = projects._settings_from_dict(d)
    assert getattr(s2, "osl", None) is None


def test_settings_osl_values_survive():
    s = projects.ProjectSettings(
        n=5, edge_hl=True, edge_extreme=False,
        edge_sens=0.5, relief_cap=True, per_region_norm=False,
        osl={"x": 12.0, "y": 34.0, "height": 40.0, "reach": 60.0,
             "intensity": 1.0, "layers": 3, "glow": "#28c85a", "hot": "#d2ffe1"},
    )
    d = projects._settings_to_dict(s)
    s2 = projects._settings_from_dict(d)
    assert s2.osl == s.osl
