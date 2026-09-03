# tests/test_pipeline_nmm.py
import numpy as np

from mini_highlight_advisor.pipeline import plan_region, analyze_regions, WHOLE_MINI
from mini_highlight_advisor.palette import DEFAULT_PALETTE, default_coverage
from mini_highlight_advisor.regions import Region
from mini_highlight_advisor.materials import build_nmm_env

PAL = DEFAULT_PALETTE[:5]
COV = default_coverage(5)

# Build the env once at module level (cheap + deterministic).
ENV = build_nmm_env(size=128)


def _dome(h=64, w=64):
    yy, xx = np.mgrid[0:h, 0:w].astype(np.float32)
    cy = cx = (h - 1) / 2.0
    r = (h - 1) / 2.0
    dx = (xx - cx) / r
    dy = (yy - cy) / r
    r2 = dx * dx + dy * dy
    mask = r2 <= 1.0
    n = np.stack([dx, -dy, np.sqrt(np.clip(1.0 - r2, 0.0, None))], -1).astype(np.float32)
    n[~mask] = np.array([0.0, 0.0, 1.0], np.float32)
    return n, mask


def _uniform_light(mask, val=0.5):
    return np.full(mask.shape, val, np.float32)


def _blob_with_detail(h=120, w=120):
    """Smooth blob + fine surface detail — a stand-in for a real mini."""
    yy, xx = np.mgrid[0:h, 0:w].astype(np.float32)
    cy = cx = (h - 1) / 2.0
    r = (h - 1) / 2.0
    dx = (xx - cx) / r
    dy = (yy - cy) / r
    mask = (dx * dx + dy * dy) <= 1.0
    # ny carries detail in BOTH axes so R_y genuinely varies within each row.
    nx = dx * 0.6 + 0.15 * np.sin(xx * 0.9)
    ny = -dy * 0.6 + 0.12 * np.cos(yy * 0.9) + 0.12 * np.sin(xx * 0.7)
    nz = np.sqrt(np.clip(1.0 - nx * nx - ny * ny, 0.01, None))
    n = np.stack([nx, ny, nz], -1).astype(np.float32)
    n[~mask] = np.array([0.0, 0.0, 1.0], np.float32)
    return n, mask


def test_nmm_bands_follow_surface_detail_not_raster_rows():
    n, mask = _blob_with_detail()
    rgb = np.full((*mask.shape, 3), 120, np.uint8)
    plan = plan_region(rgb, mask, _uniform_light(mask), "x", PAL, COV,
                       edges=False, normals=n, material="nmm", env=ENV)
    bands = plan.bands
    occupied = [np.unique(bands[row][mask[row]]) for row in range(bands.shape[0])]
    occupied = [u for u in occupied if u.size]
    multi = sum(u.size >= 2 for u in occupied)
    assert multi / max(len(occupied), 1) > 0.5


def test_matte_region_bands_from_passed_light():
    n, mask = _dome()
    rgb = np.full((*mask.shape, 3), 120, np.uint8)
    light = _uniform_light(mask)
    plan_default = plan_region(rgb, mask, light, "x", PAL, COV, edges=False, normals=n)
    plan_matte = plan_region(rgb, mask, light, "x", PAL, COV,
                             edges=False, normals=n, material="matte", env=ENV)
    np.testing.assert_array_equal(plan_matte.bands, plan_default.bands)


def test_nmm_region_rebands_from_geometry():
    n, mask = _dome()
    rgb = np.full((*mask.shape, 3), 120, np.uint8)
    light = _uniform_light(mask)
    plan = plan_region(rgb, mask, light, "x", PAL, COV,
                       edges=False, normals=n, material="nmm", env=ENV)
    assert len(np.unique(plan.bands[mask])) > 1
    plan_matte = plan_region(rgb, mask, light, "x", PAL, COV,
                             edges=False, normals=n, material="matte", env=ENV)
    assert not np.array_equal(plan.bands[mask], plan_matte.bands[mask])


def test_nmm_is_light_independent():
    n, mask = _dome()
    rgb = np.full((*mask.shape, 3), 120, np.uint8)
    a = plan_region(rgb, mask, _uniform_light(mask, 0.2), "x", PAL, COV,
                    edges=False, normals=n, material="nmm", env=ENV)
    b = plan_region(rgb, mask, _uniform_light(mask, 0.9), "x", PAL, COV,
                    edges=False, normals=n, material="nmm", env=ENV)
    np.testing.assert_array_equal(a.bands, b.bands)


def test_nmm_without_normals_falls_back_to_matte():
    n, mask = _dome()
    rgb = np.full((*mask.shape, 3), 120, np.uint8)
    light = _uniform_light(mask)
    plan_matte = plan_region(rgb, mask, light, "x", PAL, COV,
                             edges=False, normals=None, material="matte", env=ENV)
    plan_nmm = plan_region(rgb, mask, light, "x", PAL, COV,
                           edges=False, normals=None, material="nmm", env=ENV)
    np.testing.assert_array_equal(plan_nmm.bands, plan_matte.bands)


def test_nmm_knobs_thread_through_analyze_regions():
    from mini_highlight_advisor.pipeline import analyze_regions
    n, dome = _dome()
    rgb = np.full((*dome.shape, 3), 120, np.uint8)
    alpha = np.full(dome.shape, 255, np.uint8)
    light = _uniform_light(dome)
    blade = Region("Blade", dome, PAL, COV, material="nmm")
    lo = analyze_regions(rgb, alpha, PAL, COV, [blade], edges=False,
                         light_field=light, normal_field=n, whole_material="matte",
                         nmm_horizon=0.2)
    hi = analyze_regions(rgb, alpha, PAL, COV, [blade], edges=False,
                         light_field=light, normal_field=n, whole_material="matte",
                         nmm_horizon=0.8)
    lo_bands = next(p for p in lo.plans if p.name == "Blade").bands
    hi_bands = next(p for p in hi.plans if p.name == "Blade").bands
    assert not np.array_equal(lo_bands, hi_bands)   # horizon knob changes the plan


def test_analyze_regions_per_region_material_isolation():
    # The whole-mini leftover uses material="matte" while the drawn blade region uses
    # material="nmm". With a dome normal field and uniform injected light, NMM
    # derives banding from geometry. Rank-based banding always emits N bands for any
    # light field, so the meaningful assertion is that NMM bands DIFFER from what the
    # same dome geometry would produce under matte (i.e. the light-swap is not a no-op).
    n, dome = _dome()
    rgb = np.full((*dome.shape, 3), 120, np.uint8)
    alpha = np.full(dome.shape, 255, np.uint8)
    light = _uniform_light(dome)
    blade = Region("Blade", dome, PAL, COV, material="nmm")
    res = analyze_regions(rgb, alpha, PAL, COV, [blade], edges=False,
                          light_field=light, normal_field=n, whole_material="matte")
    blade_plan = next(p for p in res.plans if p.name == "Blade")
    assert len(np.unique(blade_plan.bands[blade_plan.sub_mask])) > 1
    # Discriminating: NMM blade bands must differ from matte blade bands for the same
    # dome geometry, proving per-region material isolation is not a no-op.
    blade_matte = Region("BladeMatte", dome, PAL, COV, material="matte")
    res_matte = analyze_regions(rgb, alpha, PAL, COV, [blade_matte], edges=False,
                                light_field=light, normal_field=n, whole_material="matte")
    blade_matte_plan = next(p for p in res_matte.plans if p.name == "BladeMatte")
    assert not np.array_equal(blade_plan.bands[blade_plan.sub_mask],
                              blade_matte_plan.bands[blade_matte_plan.sub_mask])
