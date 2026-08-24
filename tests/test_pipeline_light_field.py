import numpy as np

from mini_highlight_advisor.pipeline import analyze_regions, prepare_shading, WHOLE_MINI
from mini_highlight_advisor.banding import band_light
from mini_highlight_advisor.palette import DEFAULT_PALETTE, default_coverage

PAL = DEFAULT_PALETTE[:5]
COV = default_coverage(5)


def _whole(res):
    return next(p for p in res.plans if p.name == WHOLE_MINI)


def test_light_field_absent_matches_luminance_path():
    # Regression lock: omitting light_field == today's luminance banding.
    rgb = (np.random.default_rng(0).integers(0, 255, (48, 48, 3))).astype(np.uint8)
    alpha = np.full((48, 48), 255, np.uint8)
    res = analyze_regions(rgb, alpha, PAL, COV, [], edges=False, relief_cap=False)
    sh = prepare_shading(rgb, alpha)
    expected = band_light(sh.light, sh.mask, COV)
    np.testing.assert_array_equal(_whole(res).bands, expected)


def test_light_field_present_bypasses_luminance():
    # Uniform-grey rgb (flat luminance) vs a gradient light_field that DISAGREES.
    # Bands must track the light_field, proving the bypass.
    rgb = np.full((40, 40, 3), 100, np.uint8)          # flat -> luminance carries no relief
    alpha = np.full((40, 40), 255, np.uint8)
    grad = np.tile(np.linspace(0, 1, 40, dtype=np.float32), (40, 1))  # left->right ramp
    res = analyze_regions(rgb, alpha, PAL, COV, [], edges=False,
                          relief_cap=False, light_field=grad)
    bands = _whole(res).bands
    mask = bands >= 0
    # darkest band on the left, brightest on the right => mean column index rises with band
    cols = np.array([bands[mask & (bands == k)].size and
                     np.mean(np.argwhere(bands == k)[:, 1]) for k in range(5)])
    assert np.all(np.diff(cols) > 0)


def test_light_field_uses_provided_mask_shape():
    rgb = np.full((24, 24, 3), 100, np.uint8)
    alpha = np.full((24, 24), 255, np.uint8)
    lf = np.tile(np.linspace(0, 1, 24, dtype=np.float32), (24, 1))
    res = analyze_regions(rgb, alpha, PAL, COV, [], edges=False, light_field=lf)
    assert res.mask.shape == (24, 24)
    assert (res.plans[0].bands >= 0).any()
