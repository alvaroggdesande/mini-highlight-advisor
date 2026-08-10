from mini_highlight_advisor.palette import PaintColor
from mini_highlight_advisor.matching import (
    Target, target_from_band, target_from_recipe_step, target_from_hex,
    target_from_paint, match, MatchResult,
)
from mini_highlight_advisor.recipes import RecipeStep

BLACK = PaintColor("Black", "#1b1b1b", code="70.950")
GREY = PaintColor("Neutral Grey", "#6d7173", code="70.991")
WHITE = PaintColor("Dead White", "#f3f3ee", code="70.951")
CATALOG = [BLACK, GREY, WHITE, PaintColor("Sky Blue", "#4a90d9", code="72.022")]


def test_normalizers():
    assert target_from_band("#123456") == Target("#123456", None)
    assert target_from_hex("#abcdef") == Target("#abcdef", None)
    step = RecipeStep(label="Base", hex="#6d7173", paint_ref="70.991")
    assert target_from_recipe_step(step) == Target("#6d7173", "70.991")


def test_exact_by_preferred_code():
    res = match(Target("#6d7173", "70.991"), owned=[GREY, WHITE], catalog=CATALOG)
    assert res.tier == "exact"
    assert res.paints == [GREY]


def test_exact_by_near_zero_distance():
    res = match(Target("#6e7274", None), owned=[GREY, WHITE], catalog=CATALOG)
    assert res.tier == "exact"
    assert res.paints == [GREY]


def test_close_single_within_threshold():
    # a grey clearly off from #6d7173 but still within CLOSE_THRESHOLD
    res = match(Target("#787b7d", None), owned=[GREY, WHITE], catalog=CATALOG)
    assert res.tier == "close"
    assert res.paints == [GREY]
    assert res.delta_e > 1.0


def test_mix_when_between_two_owned():
    # midway grey reachable only by mixing black + white; no single owned grey
    res = match(Target("#8a8a88", None), owned=[BLACK, WHITE], catalog=CATALOG)
    assert res.tier == "mix"
    assert len(res.paints) == 2
    assert res.parts is not None and len(res.parts) == 2
    assert "approx" in res.phrase.lower()


def test_mix_rejected_when_single_is_closer():
    # Fixture designed to isolate the Tier 3 guard: mix[3] < nearest_single_d.
    #
    # Target: #686868
    # Grey A (#767676, code 70.001): ΔE = 5.48 to target — above CLOSE_THRESHOLD (5.0),
    #   so Tier 2 is NOT triggered; Grey A is the nearest single.
    # Grey B (#8a8a8a, code 70.002): ΔE = 13.45 to target.
    # Best 2-paint mix (3:1 Grey A:Grey B): ΔE = 7.50 — within MIX_ACCEPT_THRESHOLD (8.0),
    #   so WITHOUT the guard this would return tier "mix".
    # But 7.50 > 5.48, so mix[3] < nearest_single_d is False; the guard rejects the mix.
    # Result falls through to Tier 4 "unreachable".
    # Removing the guard clause at matching.py:96 would cause this test to fail.
    GREY_A = PaintColor("Grey A", "#767676", code="70.001")
    GREY_B = PaintColor("Grey B", "#8a8a8a", code="70.002")
    SKY_BLUE = PaintColor("Sky Blue", "#4a90d9", code="72.022")
    res = match(Target("#686868", None), owned=[GREY_A, GREY_B], catalog=[GREY_A, GREY_B, SKY_BLUE])
    assert res.tier == "unreachable"
    assert res.tier != "mix"


def test_unreachable_gives_buy_hint():
    # vivid blue target, owner has only greys -> unreachable + buy hint from catalog
    res = match(Target("#4a90d9", None), owned=[BLACK, GREY, WHITE], catalog=CATALOG)
    assert res.tier == "unreachable"
    assert res.buy_hint is not None
    assert res.buy_hint.code == "72.022"          # the Sky Blue they don't own
    assert res.buy_hint not in [BLACK, GREY, WHITE]


def test_target_from_paint():
    # PaintColor with a real code → preferred_code is populated
    coded = PaintColor("Neutral Grey", "#6d7173", code="70.991")
    assert target_from_paint(coded) == Target("#6d7173", "70.991")
    # PaintColor with default empty-string code → preferred_code is None (not "")
    custom = PaintColor("Custom 1", "#aabbcc")
    assert target_from_paint(custom) == Target("#aabbcc", None)
