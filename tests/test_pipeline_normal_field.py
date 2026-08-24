import numpy as np
import pytest

from mini_highlight_advisor.pipeline import analyze_regions, WHOLE_MINI
from mini_highlight_advisor.edges import edge_mask
from mini_highlight_advisor.palette import DEFAULT_PALETTE, default_coverage

PAL = DEFAULT_PALETTE[:5]
COV = default_coverage(5)


def _whole(res):
    return next(p for p in res.plans if p.name == WHOLE_MINI)


def _vridge(h=48, w=48, c0=24, half=8):
    col = np.arange(w, dtype=np.float32)
    ang = np.clip((col - c0) / half, -1.0, 1.0) * (np.pi / 3.0)
    n = np.zeros((h, w, 3), np.float32)
    n[..., 0] = np.sin(ang)[None, :]
    n[..., 2] = np.cos(ang)[None, :]
    return n, c0


def test_normal_absent_overlay_is_light_gradient():
    # Regression lock: no normal_field -> overlay is exactly today's edge_mask.
    ramp = np.tile(np.linspace(40, 220, 48, dtype=np.uint8), (48, 1))
    rgb = np.stack([ramp, ramp, ramp], axis=-1)
    alpha = np.full((48, 48), 255, np.uint8)
    res = analyze_regions(rgb, alpha, PAL, COV, [], edges=True)
    whole = _whole(res)
    expected = edge_mask(res.light, whole.sub_mask, 0.5)
    np.testing.assert_array_equal(whole.edge_overlays[0][0], expected)


def test_normal_present_overlay_from_curvature():
    # Uniform relit light (no gradient) but a REAL ridge in the normals: the
    # overlay must come from curvature and land on the crest.
    n, c0 = _vridge()
    rgb = np.full((48, 48, 3), 120, np.uint8)          # flat luminance
    alpha = np.full((48, 48), 255, np.uint8)
    uniform = np.full((48, 48), 0.5, np.float32)       # uniform light -> no edges
    res = analyze_regions(rgb, alpha, PAL, COV, [], edges=True,
                          light_field=uniform, normal_field=n)
    ov = _whole(res).edge_overlays[0][0]
    assert ov.sum() > 0
    cols = np.where(ov.any(axis=0))[0]
    assert abs(int(round(cols.mean())) - c0) <= 4
    # sanity: the light-gradient path finds nothing on this uniform light
    assert edge_mask(uniform, np.ones((48, 48), bool), 0.5).sum() == 0


def test_normal_field_shape_mismatch_raises():
    rgb = np.full((20, 20, 3), 120, np.uint8)
    alpha = np.full((20, 20), 255, np.uint8)
    bad = np.zeros((10, 10, 3), np.float32)
    with pytest.raises(ValueError):
        analyze_regions(rgb, alpha, PAL, COV, [], edges=True,
                        light_field=np.full((20, 20), 0.5, np.float32),
                        normal_field=bad)
