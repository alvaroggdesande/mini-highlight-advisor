import colorsys
from mini_highlight_advisor import scheme_gen as sg
from mini_highlight_advisor.color import hex_to_rgb


def _hue(hexv):
    r, g, b = hex_to_rgb(hexv)
    return colorsys.rgb_to_hls(r / 255, g / 255, b / 255)[0] * 360.0


def _sat_light(hexv):
    r, g, b = hex_to_rgb(hexv)
    h, l, s = colorsys.rgb_to_hls(r / 255, g / 255, b / 255)
    return s, l


def test_harmony_hues_returns_k_and_complementary_is_180():
    out = sg.harmony_hues("#c02030", "complementary", 3)
    assert len(out) == 3
    d = abs(_hue(out[0]) - _hue("#c02030")) % 360
    assert min(d, 360 - d) == pytest.approx(180, abs=2)


def test_apply_mood_grimdark_darkens_and_desaturates():
    s0, l0 = _sat_light("#808080".replace("80", "a0"))  # a mid colour with some sat
    base = "#b05040"
    s_before, l_before = _sat_light(base)
    out = sg.apply_mood(base, "grimdark")
    s_after, l_after = _sat_light(out)
    assert s_after < s_before
    assert l_after < l_before


def test_apply_mood_neutral_is_identity_hue():
    base = "#3366cc"
    assert _hue(sg.apply_mood(base, "neutral")) == pytest.approx(_hue(base), abs=1)


def test_generate_ramps_one_ramp_per_region_correct_length():
    specs = [
        sg.RegionColorSpec("Cloak", "cloak", None, 5),
        sg.RegionColorSpec("Skin", "skin", "tan", 4),
    ]
    out = sg.generate_ramps(specs, "Cloak", "#c02030", "neutral", "complementary")
    assert set(out) == {"Cloak", "Skin"}
    assert len(out["Cloak"]) == 5
    assert len(out["Skin"]) == 4


def test_anchor_region_midtone_tracks_anchor_hue():
    specs = [sg.RegionColorSpec("Cloak", "cloak", None, 5)]
    out = sg.generate_ramps(specs, "Cloak", "#c02030", "neutral", "complementary")
    mid = out["Cloak"][5 // 2]
    d = abs(_hue(mid) - _hue("#c02030")) % 360
    assert min(d, 360 - d) < 20


def test_realistic_region_ignores_harmony_but_harmony_tone_follows():
    anchor = "#c02030"  # red
    locked = sg.generate_ramps(
        [sg.RegionColorSpec("Skin", "skin", "orc-green", 5)],
        "Cloak", anchor, "neutral", "complementary")["Skin"][2]
    followed = sg.generate_ramps(
        [sg.RegionColorSpec("Skin", "skin", sg.HARMONY_TONE, 5)],
        "Cloak", anchor, "neutral", "complementary")["Skin"][2]
    # locked skin is green-ish, harmony-following skin is NOT the same hue
    assert abs(_hue(locked) - _hue(followed)) > 20


import pytest  # noqa: E402  (kept at bottom so the file reads top-down)
