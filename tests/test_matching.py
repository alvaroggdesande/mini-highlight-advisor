from mini_highlight_advisor.palette import PaintColor
from mini_highlight_advisor.matching import (
    Target, target_from_band, target_from_recipe_step, target_from_hex,
    match, MatchResult,
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


def test_unreachable_gives_buy_hint():
    # vivid blue target, owner has only greys -> unreachable + buy hint from catalog
    res = match(Target("#4a90d9", None), owned=[BLACK, GREY, WHITE], catalog=CATALOG)
    assert res.tier == "unreachable"
    assert res.buy_hint is not None
    assert res.buy_hint.code == "72.022"          # the Sky Blue they don't own
    assert res.buy_hint not in [BLACK, GREY, WHITE]
