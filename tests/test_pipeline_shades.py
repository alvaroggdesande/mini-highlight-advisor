import numpy as np

from mini_highlight_advisor.pipeline import analyze_regions, WHOLE_MINI
from mini_highlight_advisor.palette import DEFAULT_PALETTE, default_coverage

PAL = DEFAULT_PALETTE[:5]
COV = default_coverage(5)


def _whole(res):
    return next(p for p in res.plans if p.name == WHOLE_MINI)


def _vcrease(h=48, w=48, c0=24, half=8):
    col = np.arange(w, dtype=np.float32)
    ang = np.clip((col - c0) / half, -1.0, 1.0) * (np.pi / 3.0)
    n = np.zeros((h, w, 3), np.float32)
    n[..., 0] = -np.sin(ang)[None, :]
    n[..., 2] = np.cos(ang)[None, :]
    return n, c0


def _flat_inputs():
    rgb = np.full((48, 48, 3), 120, np.uint8)
    alpha = np.full((48, 48), 255, np.uint8)
    light = np.full((48, 48), 0.5, np.float32)
    return rgb, alpha, light


def test_shades_off_is_baseline():
    # Regression lock: shades default off -> no shade overlay, no shade step.
    n, _ = _vcrease()
    rgb, alpha, light = _flat_inputs()
    res = analyze_regions(rgb, alpha, PAL, COV, [], edges=True,
                          light_field=light, normal_field=n)
    whole = _whole(res)
    assert not any(s.kind == "shade" for s in whole.steps)


def test_shades_on_adds_overlay_and_step():
    n, c0 = _vcrease()
    rgb, alpha, light = _flat_inputs()
    res = analyze_regions(rgb, alpha, PAL, COV, [], edges=True, shades=True,
                          light_field=light, normal_field=n)
    whole = _whole(res)
    # shade overlay is present and prepended (index 0 of edge_overlays)
    shade_mask, shade_col = whole.edge_overlays[0]
    assert shade_mask.sum() > 0
    cols = np.where(shade_mask.any(axis=0))[0]
    assert abs(int(round(cols.mean())) - c0) <= 4
    # shade colour is the darkened base (band 0)
    np.testing.assert_allclose(shade_col, whole.colors[0] * 0.55, rtol=1e-5)
    # exactly one shade step appended
    assert sum(s.kind == "shade" for s in whole.steps) == 1


def test_shades_ignored_without_normals():
    # shades=True but no normal field (Path L) -> no shade overlay/step, no crash.
    rgb, alpha, _ = _flat_inputs()
    res = analyze_regions(rgb, alpha, PAL, COV, [], edges=True, shades=True)
    whole = _whole(res)
    assert not any(s.kind == "shade" for s in whole.steps)
