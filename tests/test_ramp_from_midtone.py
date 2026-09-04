"""Tests for ramp_from_midtone — the painterly ramp generator."""
import math
import pytest

from mini_highlight_advisor.color import lab_of_hex, ramp_from_midtone


def _chroma(hexv: str) -> float:
    _, a, b = lab_of_hex(hexv)
    return math.hypot(a, b)


def test_returns_n_hex_strings_for_each_layer_count():
    for n in range(3, 8):
        result = ramp_from_midtone("#6d7173", n)
        assert len(result) == n
        for h in result:
            assert h.startswith("#") and len(h) == 7


def test_midtone_lightness_preserved_at_centre_slot():
    mid = "#7a5c3a"
    for n in range(3, 8):
        result = ramp_from_midtone(mid, n)
        mid_L, _, _ = lab_of_hex(mid)
        out_L, _, _ = lab_of_hex(result[n // 2])
        assert abs(out_L - mid_L) < 2.0, f"n={n}: L mismatch {out_L:.1f} vs {mid_L:.1f}"


def test_lightness_monotonically_increases_dark_to_light():
    result = ramp_from_midtone("#6d7173", 5)
    Ls = [lab_of_hex(h)[0] for h in result]
    for i in range(len(Ls) - 1):
        assert Ls[i] < Ls[i + 1], f"Non-monotonic at slot {i}: {Ls}"


def test_shadows_more_saturated_than_highlights_for_chromatic_input():
    # Mid-L red — enough headroom so gamut clipping doesn't swamp the boost.
    result = ramp_from_midtone("#b04040", 5)
    assert _chroma(result[0]) > _chroma(result[-1])


def test_neutral_grey_midtone_produces_valid_near_neutral_ramp():
    result = ramp_from_midtone("#808080", 5)
    for h in result:
        assert _chroma(h) < 15, f"Grey ramp produced too-chromatic stop: {h}"


def test_works_for_even_layer_count():
    result = ramp_from_midtone("#4488cc", 4)
    assert len(result) == 4
    Ls = [lab_of_hex(h)[0] for h in result]
    for i in range(len(Ls) - 1):
        assert Ls[i] < Ls[i + 1]


def test_shaping_params_accepted_as_keyword_args():
    """The four params exist for future slider wiring — must be accepted now."""
    result = ramp_from_midtone(
        "#6d7173", 5,
        shadow_sat_boost=0.1,
        shadow_cool=8.0,
        hi_desat=0.1,
        hi_warm=5.0,
    )
    assert len(result) == 5
