import numpy as np

from mini_highlight_advisor.palette import DEFAULT_PALETTE, default_coverage
from mini_highlight_advisor.lighting import luminance_light
from mini_highlight_advisor.pipeline import analyze_regions, plan_region
from mini_highlight_advisor.regions import Region


def _varied_light(h=10, w=50):
    light = np.linspace(0.0, 1.0, h * w, dtype=np.float32).reshape(h, w)
    return light, np.ones((h, w), dtype=bool), np.zeros((h, w, 3), dtype=np.uint8)


def test_plan_region_flat_albedo_caps_to_one_band():
    light, sub, rgb = _varied_light()
    plan = plan_region(rgb, sub, light, "R", list(DEFAULT_PALETTE),
                       default_coverage(5), edges=False, flat_albedo=True)
    assert plan.flat_albedo is True
    assert plan.capped is True
    assert len(plan.colors) == 1
    assert plan.requested_bands == 5


def test_plan_region_flat_albedo_false_keeps_all_bands():
    light, sub, rgb = _varied_light()
    plan = plan_region(rgb, sub, light, "R", list(DEFAULT_PALETTE),
                       default_coverage(5), edges=False,
                       relief_cap=False, flat_albedo=False)
    assert plan.flat_albedo is False
    assert plan.capped is False
    assert len(plan.colors) == 5


def test_per_region_norm_off_uses_global_light_unchanged():
    # Regression lock: off path returns exactly the global luminance stretch.
    rgb = np.zeros((10, 50, 3), dtype=np.uint8)
    rgb[:] = np.linspace(0, 255, 50, dtype=np.uint8)[None, :, None]
    alpha = np.full((10, 50), 255, dtype=np.uint8)
    multi = analyze_regions(rgb, alpha, list(DEFAULT_PALETTE), default_coverage(5),
                            edges=False, per_region_norm=False)
    np.testing.assert_array_equal(multi.light, luminance_light(rgb, multi.mask))


def test_per_region_norm_on_flags_flat_dark_region():
    # Whole mini is a near-constant dark block -> guard fires.
    rgb = np.full((12, 12, 3), 30, dtype=np.uint8)
    alpha = np.full((12, 12), 255, dtype=np.uint8)
    multi = analyze_regions(rgb, alpha, list(DEFAULT_PALETTE), default_coverage(5),
                            edges=False, per_region_norm=True)
    whole = multi.plans[0]
    assert whole.flat_albedo is True
    assert len(whole.colors) == 1


def test_per_region_norm_recovers_dark_relief_region():
    # Left third bright (albedo high), right two-thirds dark but with real relief.
    # A vertical gradient gives each column-region its own shading ramp.
    rgb = np.zeros((20, 60, 3), dtype=np.uint8)
    ramp = np.linspace(0, 1, 20, dtype=np.float32)[:, None, None]  # dark->light top->bottom
    rgb[:, :20, :] = (120 + 100 * ramp).astype(np.uint8)          # bright region A
    rgb[:, 20:, :] = (30 + 40 * ramp).astype(np.uint8)            # dark region B, 30..70
    alpha = np.full((20, 60), 255, dtype=np.uint8)
    bmask = np.zeros((20, 60), dtype=bool)
    bmask[:, 20:] = True
    region_b = Region("B", bmask, list(DEFAULT_PALETTE), default_coverage(5))

    off = analyze_regions(rgb, alpha, list(DEFAULT_PALETTE), default_coverage(5),
                          regions=[region_b], edges=False,
                          relief_cap=True, per_region_norm=False)
    on = analyze_regions(rgb, alpha, list(DEFAULT_PALETTE), default_coverage(5),
                         regions=[region_b], edges=False,
                         relief_cap=True, per_region_norm=True)
    b_off = next(p for p in off.plans if p.name == "B")
    b_on = next(p for p in on.plans if p.name == "B")
    # Global stretch compresses B -> relief cap wrongly fires.
    assert b_off.capped and len(b_off.colors) < 5
    # Per-region stretch recovers B's real relief -> full bands, not flat.
    assert b_on.flat_albedo is False
    assert len(b_on.colors) == 5
