import numpy as np
from mini_highlight_advisor.banding import band_light


def test_band_light_respects_target_coverage():
    # Uniform gradient over a full mask -> coverage should match targets closely.
    light = np.tile(np.linspace(0, 1, 1000, dtype=np.float32), (10, 1))
    mask = np.ones_like(light, dtype=bool)
    coverage = [0.4, 0.3, 0.2, 0.1]
    bands = band_light(light, mask, coverage)
    total = mask.sum()
    for b, target in enumerate(coverage):
        frac = (bands == b).sum() / total
        assert abs(frac - target) < 0.02


def test_band_light_darkest_is_zero_brightest_is_last():
    light = np.tile(np.linspace(0, 1, 100, dtype=np.float32), (5, 1))
    mask = np.ones_like(light, dtype=bool)
    bands = band_light(light, mask, [0.5, 0.5])
    assert bands[0, 0] == 0        # darkest pixel -> band 0
    assert bands[0, -1] == 1       # brightest pixel -> last band


def test_band_light_flat_region_still_splits_by_coverage():
    # A (near-)uniform region must not collapse all pixels into one band — it
    # should still split into the requested proportions (rank-based banding).
    light = np.full((100, 100), 0.3, dtype=np.float32)
    mask = np.ones_like(light, dtype=bool)
    coverage = [0.4, 0.3, 0.2, 0.1]
    bands = band_light(light, mask, coverage)
    total = mask.sum()
    realized = [(bands == b).sum() / total for b in range(len(coverage))]
    assert all(r > 0 for r in realized), f"a band collapsed to empty: {realized}"
    for r, target in zip(realized, coverage):
        assert abs(r - target) < 0.02


def test_band_light_marks_outside_mask_as_minus_one():
    light = np.zeros((2, 2), dtype=np.float32)
    mask = np.array([[True, False], [True, True]])
    bands = band_light(light, mask, [1.0])
    assert bands[0, 1] == -1
    assert set(np.unique(bands[mask])) <= {0}
