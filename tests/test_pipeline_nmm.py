# tests/test_pipeline_nmm.py
import numpy as np

from mini_highlight_advisor.pipeline import plan_region, analyze_regions, WHOLE_MINI
from mini_highlight_advisor.palette import DEFAULT_PALETTE, default_coverage
from mini_highlight_advisor.regions import Region

PAL = DEFAULT_PALETTE[:5]
COV = default_coverage(5)


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


def test_matte_region_bands_from_passed_light():
    # material="matte" is a no-op: bands must equal those from the default call (no
    # material kwarg). NMM code path is NOT taken regardless of normals being present.
    n, mask = _dome()
    rgb = np.full((*mask.shape, 3), 120, np.uint8)
    light = _uniform_light(mask)
    plan_default = plan_region(rgb, mask, light, "x", PAL, COV,
                               edges=False, normals=n)
    plan_matte = plan_region(rgb, mask, light, "x", PAL, COV,
                             edges=False, normals=n, material="matte")
    np.testing.assert_array_equal(plan_matte.bands, plan_default.bands)


def test_nmm_region_rebands_from_geometry():
    # Same uniform light, but material="nmm" -> geometry drives banding -> many bands.
    n, mask = _dome()
    rgb = np.full((*mask.shape, 3), 120, np.uint8)
    light = _uniform_light(mask)
    plan = plan_region(rgb, mask, light, "x", PAL, COV,
                       edges=False, normals=n, material="nmm", nmm_horizon=0.5)
    assert len(np.unique(plan.bands[mask])) > 1
    # Discriminating: NMM bands must differ from matte bands for the same geometry
    # and same uniform light, proving the NMM light-swap is not a no-op.
    plan_matte = plan_region(rgb, mask, light, "x", PAL, COV,
                             edges=False, normals=n, material="matte")
    assert not np.array_equal(plan.bands[mask], plan_matte.bands[mask])


def test_nmm_is_light_independent():
    # NMM ignores the passed light: two different light fields -> identical banding.
    n, mask = _dome()
    rgb = np.full((*mask.shape, 3), 120, np.uint8)
    a = plan_region(rgb, mask, _uniform_light(mask, 0.2), "x", PAL, COV,
                    edges=False, normals=n, material="nmm")
    b = plan_region(rgb, mask, _uniform_light(mask, 0.9), "x", PAL, COV,
                    edges=False, normals=n, material="nmm")
    np.testing.assert_array_equal(a.bands, b.bands)


def test_nmm_without_normals_falls_back_to_matte():
    # normals=None with material="nmm" -> silently falls back to matte (no crash).
    # Bands must be identical to material="matte" (same light, no NMM override).
    n, mask = _dome()
    rgb = np.full((*mask.shape, 3), 120, np.uint8)
    light = _uniform_light(mask)
    plan_matte = plan_region(rgb, mask, light, "x", PAL, COV,
                             edges=False, normals=None, material="matte")
    plan_nmm_no_normals = plan_region(rgb, mask, light, "x", PAL, COV,
                                      edges=False, normals=None, material="nmm")
    np.testing.assert_array_equal(plan_nmm_no_normals.bands, plan_matte.bands)


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
