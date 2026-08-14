import numpy as np

from mini_highlight_advisor.palette import DEFAULT_PALETTE, default_coverage
from mini_highlight_advisor.pipeline import analyze_regions, plan_region


def _scene(varied: bool):
    rgb = np.zeros((10, 50, 3), dtype=np.uint8)
    light = np.zeros((10, 50), dtype=np.float32)
    sub = np.ones((10, 50), dtype=bool)
    if varied:
        light[:] = np.linspace(0.0, 1.0, 500, dtype=np.float32).reshape(10, 50)
    else:
        light[sub] = 0.4
    return rgb, sub, light


def _plan(varied, relief_cap):
    rgb, sub, light = _scene(varied)
    return plan_region(rgb, sub, light, "R", list(DEFAULT_PALETTE),
                       default_coverage(5), edges=False, relief_cap=relief_cap)


def test_flat_region_capped_reduces_bands():
    plan = _plan(varied=False, relief_cap=True)
    assert plan.capped
    assert plan.requested_bands == 5
    assert len(plan.colors) == 1
    assert len(plan.coverage) == 1


def test_varied_region_not_capped():
    plan = _plan(varied=True, relief_cap=True)
    assert not plan.capped
    assert len(plan.colors) == 5


def test_relief_cap_off_keeps_all_bands_on_flat_region():
    plan = _plan(varied=False, relief_cap=False)
    assert not plan.capped
    assert len(plan.colors) == 5


def test_analyze_regions_accepts_relief_cap():
    rgb = np.zeros((10, 50, 3), dtype=np.uint8)
    rgb[:] = np.linspace(0, 255, 50, dtype=np.uint8)[None, :, None]
    alpha = np.full((10, 50), 255, dtype=np.uint8)
    multi = analyze_regions(rgb, alpha, list(DEFAULT_PALETTE), default_coverage(5),
                            edges=False, relief_cap=True)
    assert multi.plans  # whole-mini plan present, no crash
