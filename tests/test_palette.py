import numpy as np
from mini_highlight_advisor.palette import (
    PaintColor, DEFAULT_PALETTE, role_names, default_coverage, coverage_pct,
    default_ramp,
)


def test_paintcolor_hex_to_rgb():
    assert np.allclose(PaintColor("White", "#ffffff").rgb, [255, 255, 255])
    assert np.allclose(PaintColor("Black", "#000000").rgb, [0, 0, 0])


def test_default_palette_is_five_dark_to_light():
    assert len(DEFAULT_PALETTE) == 5
    lums = [c.rgb.mean() for c in DEFAULT_PALETTE]
    assert lums == sorted(lums)  # ascending brightness


def test_role_names_known_and_generic():
    assert role_names(5) == ["Shadow", "Base", "Midtone", "Highlight", "Bright Highlight"]
    assert role_names(2) == ["Layer 1", "Layer 2"]


def test_default_coverage_decreasing_and_normalized():
    cov = default_coverage(5)
    assert abs(sum(cov) - 1.0) < 1e-6
    assert cov == sorted(cov, reverse=True)  # shadow largest, edge smallest


def test_coverage_pct_counts_within_mask():
    bands = np.array([[0, 1], [1, -1]])
    mask = np.array([[True, True], [True, False]])
    pct = coverage_pct(bands, mask, 2)
    assert abs(pct[0] - 100 / 3) < 1e-6
    assert abs(pct[1] - 200 / 3) < 1e-6


def test_paintcolor_optional_brand_range():
    p = PaintColor("Neutral Grey", "#6d7173", brand="Vallejo", paint_range="Model Color")
    assert p.brand == "Vallejo"
    assert p.paint_range == "Model Color"


def test_paintcolor_still_constructs_with_name_hex_only():
    p = PaintColor("White", "#ffffff")
    assert p.brand is None and p.paint_range is None
    assert np.allclose(p.rgb, [255, 255, 255])


def test_default_palette_is_vallejo():
    assert len(DEFAULT_PALETTE) == 5
    assert all(c.brand == "Vallejo" for c in DEFAULT_PALETTE)
    lums = [c.rgb.mean() for c in DEFAULT_PALETTE]
    assert lums == sorted(lums)  # dark to light


def test_paintcolor_has_code_default_empty():
    from mini_highlight_advisor.palette import PaintColor
    p = PaintColor("Custom 1", "#123456")
    assert p.code == ""


def test_default_palette_entries_have_codes():
    from mini_highlight_advisor.palette import DEFAULT_PALETTE
    assert all(p.code for p in DEFAULT_PALETTE)


def test_role_names_six_and_seven():
    from mini_highlight_advisor.palette import role_names
    assert role_names(6) == [
        "Shadow", "Deep Base", "Base", "Midtone", "Highlight", "Bright Highlight"
    ]
    assert role_names(7) == [
        "Shadow", "Deep Base", "Base", "Midtone", "Upper Midtone",
        "Highlight", "Bright Highlight",
    ]


def test_ramp_hex_endpoints_and_monotonic():
    from mini_highlight_advisor.palette import PaintColor, ramp_hex
    n = 7
    lums = [PaintColor("x", ramp_hex(i, n)).rgb.mean() for i in range(n)]
    assert lums[0] < 40          # near-black low end
    assert ramp_hex(n - 1, n) == "#ffffff"
    assert lums == sorted(lums)  # strictly non-decreasing, dark to light
    assert lums[-1] > lums[0]


def test_remainder_pct_fills_to_100():
    from mini_highlight_advisor.palette import remainder_pct
    assert remainder_pct([40.0, 30.0, 20.0]) == 10.0
    assert remainder_pct([]) == 100.0
    assert remainder_pct([60.0, 60.0]) == 0.0  # clamped, never negative


def test_slider_max_pct_reserves_floor():
    from mini_highlight_advisor.palette import slider_max_pct
    # Two other sliders at 30 each -> 100-60-3 = 37 headroom for this slider.
    assert slider_max_pct([30.0, 30.0], floor=3.0) == 37.0
    # Never negative even when others already over budget.
    assert slider_max_pct([98.0, 10.0], floor=3.0) == 0.0


def test_slider_max_invariant_keeps_total_under_100():
    # If each slider stays within its live max, the n-1 sliders + floor <= 100.
    from mini_highlight_advisor.palette import slider_max_pct, remainder_pct
    sliders = [0.0, 0.0, 0.0]  # n-1 = 3 controllable bands
    # Simulate pushing slider 0 to its max, then slider 1, then slider 2.
    for i in range(len(sliders)):
        others = [v for j, v in enumerate(sliders) if j != i]
        sliders[i] = slider_max_pct(others, floor=3.0)
    assert sum(sliders) <= 97.0 + 1e-9
    assert remainder_pct(sliders) >= 3.0 - 1e-9


def test_default_ramp_length_and_seed():
    ramp = default_ramp(6)
    assert len(ramp) == 6
    assert ramp[0].hex == DEFAULT_PALETTE[0].hex
    assert all(hasattr(p, "hex") for p in ramp)


def test_paintcolor_finish_defaults_matte():
    from mini_highlight_advisor.palette import PaintColor
    assert PaintColor("X", "#111111").finish == "matte"


def test_paintcolor_finish_explicit():
    from mini_highlight_advisor.palette import PaintColor
    assert PaintColor("Silver", "#c9cccd", finish="metallic").finish == "metallic"


def test_valid_hex_accepts_and_normalises():
    from mini_highlight_advisor.palette import valid_hex
    assert valid_hex("#AABBCC") == "#aabbcc"
    assert valid_hex("aabbcc") == "#aabbcc"      # leading # optional
    assert valid_hex("#abc") == "#aabbcc"        # short form expands


def test_valid_hex_rejects_bad_input():
    from mini_highlight_advisor.palette import valid_hex
    assert valid_hex("xyz") is None
    assert valid_hex("#12") is None
    assert valid_hex("#12345") is None
    assert valid_hex("") is None
