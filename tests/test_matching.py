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


SILVER = PaintColor("Sterling Silver", "#d5d7d6", finish="metallic")
DARKMETAL = PaintColor("Obsidian Black", "#292b2c", finish="metallic")


def test_target_from_paint_inherits_finish():
    from mini_highlight_advisor.matching import target_from_paint
    assert target_from_paint(SILVER).finish == "metallic"
    assert target_from_paint(GREY).finish == "matte"


def test_matte_target_never_returns_metallic():
    # SILVER (metallic) must be excluded from a MATTE target's pools
    t = Target("#d3d5d4", None, "matte")   # sits right on the silver hex, but matte
    res = match(t, owned=[SILVER, WHITE], catalog=[SILVER, WHITE])
    assert all(p.finish != "metallic" for p in res.paints)
    if res.buy_hint is not None:
        assert res.buy_hint.finish != "metallic"


def test_metallic_target_matches_metallic_only():
    t = Target("#d5d7d6", None, "metallic")
    res = match(t, owned=[SILVER, GREY, WHITE], catalog=[SILVER])
    assert res.tier == "exact" and res.paints == [SILVER]


def test_metallic_shadow_is_all_metallic_mix():
    t = Target("#7f8182", None, "metallic")     # between silver and dark metal
    res = match(t, owned=[SILVER, DARKMETAL], catalog=[SILVER, DARKMETAL])
    assert res.tier == "mix"
    assert all(p.finish == "metallic" for p in res.paints)


def test_metallic_plus_minority_tint():
    blue = PaintColor("Blue", "#2b5fa8")         # matte tint
    t = Target("#95a3b5", None, "metallic")      # silver pushed toward blue (nudged from #93a1b4: 2:1 mix dE=8.005 just above threshold)
    res = match(t, owned=[SILVER, blue], catalog=[SILVER, blue])
    # only legal mix is metallic + tint; tint must be the minority part
    assert res.tier == "mix"
    assert res.paints[0].finish == "metallic" and res.paints[1].finish != "metallic"
    assert res.parts[-1] == min(res.parts)
    assert "tint" in res.phrase.lower()


def test_three_paint_mix_when_pair_cannot_reach():
    R = PaintColor("R", "#ff0000"); G = PaintColor("G", "#00ff00"); B = PaintColor("B", "#0000ff")
    t = Target("#9a9a9a", None, "matte")          # neutral grey needs all three
    res = match(t, owned=[R, G, B], catalog=[R, G, B])
    assert res.tier == "mix" and len(res.paints) == 3


def test_two_paint_kept_when_third_barely_helps():
    NEARW = PaintColor("Near White", "#eeeeee")
    t = Target("#8a8a88", None, "matte")          # black+white already nails it
    res = match(t, owned=[BLACK, WHITE, NEARW], catalog=[BLACK, WHITE, NEARW])
    assert res.tier == "mix" and len(res.paints) == 2


def test_buy_hint_excludes_codeless_owned_paint():
    """I1: a code-less paint the user already owns must NOT appear as a buy-hint.

    Setup:
    - Target: vivid yellow (matte, specific shade) — placed so the code-less
      custom yellow is in owned but NOT close enough to be a tier-1/2 match
      (ΔE > CLOSE_THRESHOLD from target) and no mix is possible (only one
      matte paint owned), forcing tier 4 unreachable.
    - Catalog: only that same code-less paint (the nearest match for the finish).
    - Expected: buy_hint is None (the sole catalog candidate is already owned).

    With the old code-only filter (`"" not in owned_codes`), the code-less paint
    passes the filter and IS returned as buy_hint — making the assertion FAIL
    against the buggy code. After the fix (set-based identity check), it is
    excluded and buy_hint is None.
    """
    # A code-less custom orange — deliberately placed far from the target blue.
    # ΔE between #e07010 (orange) and #4a7ad9 (blue) is >> CLOSE_THRESHOLD.
    CUSTOM_ORANGE = PaintColor("Custom Orange", "#e07010", finish="matte")

    # Target: a vivid blue that CUSTOM_ORANGE cannot match (too far for exact/close)
    # and no mix is possible (only one matte paint owned).
    res = match(
        Target("#4a7ad9", None, "matte"),
        owned=[CUSTOM_ORANGE],
        catalog=[CUSTOM_ORANGE],
    )
    assert res.tier == "unreachable", (
        f"Expected unreachable (orange cannot match blue), got {res.tier}"
    )
    # The critical assertion: the owned code-less paint must NOT be the buy hint.
    assert res.buy_hint is not CUSTOM_ORANGE, (
        "buy_hint must not be a paint the user already owns (code-less identity bug)"
    )
    assert res.buy_hint is None, (
        "with only the owned code-less paint in catalog, buy_hint must be None"
    )
