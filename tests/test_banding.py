import numpy as np
from mini_highlight_advisor.banding import band_light, band_by_value


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


def test_band_by_value_flat_plateau_collapses_to_one_band():
    # Large flat plateau + a thin dark line. Value banding: plateau -> ONE band,
    # thin line keeps its OWN band regardless of its tiny area.
    light = np.full((20, 20), 0.8, np.float32)
    light[10, :] = 0.05                      # one thin dark row
    mask = np.ones((20, 20), bool)
    bands = band_by_value(light, mask, n_bands=5)
    plateau_bands = np.unique(bands[light == 0.8])
    assert plateau_bands.size == 1           # flat sky -> one paint
    assert bands[10, 0] != plateau_bands[0]  # thin line is a different (darker) band
    assert bands[10, 0] < plateau_bands[0]


def test_band_by_value_contrast_with_rank_banding():
    # Documents WHY value banding exists: rank banding splits the same flat plateau
    # across multiple bands; value banding does not.
    light = np.full((20, 20), 0.8, np.float32)
    light[10, :] = 0.05
    mask = np.ones((20, 20), bool)
    rank = band_light(light, mask, [0.2, 0.2, 0.2, 0.2, 0.2])
    val = band_by_value(light, mask, 5)
    assert np.unique(rank[light == 0.8]).size > 1    # rank stripes the plateau
    assert np.unique(val[light == 0.8]).size == 1    # value keeps it whole


def test_band_by_value_no_raster_order_dependence():
    # Shuffling equal-valued pixel positions changes no band assignment.
    rng_vals = np.linspace(0.0, 1.0, 400, dtype=np.float32).reshape(20, 20)
    mask = np.ones((20, 20), bool)
    a = band_by_value(rng_vals, mask, 5)
    b = band_by_value(rng_vals[::-1, ::-1], mask, 5)[::-1, ::-1]
    np.testing.assert_array_equal(a, b)


def test_band_by_value_empty_mask_all_minus_one():
    light = np.zeros((5, 5), np.float32)
    bands = band_by_value(light, np.zeros((5, 5), bool), 5)
    assert np.all(bands == -1)


def test_band_by_value_constant_field_single_band():
    light = np.full((5, 5), 0.5, np.float32)
    bands = band_by_value(light, np.ones((5, 5), bool), 5)
    assert set(np.unique(bands).tolist()) == {0}
