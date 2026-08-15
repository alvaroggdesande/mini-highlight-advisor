import numpy as np
from mini_highlight_advisor.lighting import (
    luminance_light, _clahe_gray, _stretch,
    local_luminance_light, LocalLight, FLAT_DYNRANGE_MIN,
)


def test_luminance_zero_outside_mask():
    rgb = np.full((8, 8, 3), 128, dtype=np.uint8)
    mask = np.zeros((8, 8), dtype=bool)
    mask[2:6, 2:6] = True
    out = luminance_light(rgb, mask)
    assert out.shape == (8, 8)
    assert np.all(out[~mask] == 0.0)


def test_luminance_brighter_pixels_map_higher():
    # Left half dark, right half bright, all masked.
    rgb = np.zeros((16, 16, 3), dtype=np.uint8)
    rgb[:, 8:] = 200
    mask = np.ones((16, 16), dtype=bool)
    out = luminance_light(rgb, mask)
    assert out[:, 12].mean() > out[:, 3].mean()


def test_luminance_in_unit_range():
    rng = np.random.default_rng(0)
    rgb = rng.integers(0, 256, size=(20, 20, 3), dtype=np.uint8)
    mask = np.ones((20, 20), dtype=bool)
    out = luminance_light(rgb, mask)
    assert out.min() >= 0.0 and out.max() <= 1.0


def test_luminance_light_equals_stretch_of_clahe_gray():
    # The split must preserve the public function exactly.
    rng = np.random.default_rng(1)
    rgb = rng.integers(0, 256, size=(24, 24, 3), dtype=np.uint8)
    mask = np.zeros((24, 24), dtype=bool)
    mask[4:20, 4:20] = True
    expected = _stretch(_clahe_gray(rgb), mask)
    np.testing.assert_array_equal(luminance_light(rgb, mask), expected)


def test_local_luminance_stretches_region_to_unit_and_zeros_outside():
    gray = np.zeros((10, 10), dtype=np.float32)
    sub = np.zeros((10, 10), dtype=bool)
    sub[2:8, 2:8] = True
    gray[sub] = np.linspace(40, 200, sub.sum(), dtype=np.float32)
    ll = local_luminance_light(gray, sub)
    assert isinstance(ll, LocalLight)
    assert np.all(ll.light[~sub] == 0.0)
    assert ll.light[sub].max() >= 0.99 and ll.light[sub].min() <= 0.01


def test_local_luminance_flat_flag_true_for_narrow_dark_region():
    gray = np.full((10, 10), 30.0, dtype=np.float32)  # near-constant
    sub = np.ones((10, 10), dtype=bool)
    ll = local_luminance_light(gray, sub)
    assert ll.dyn_range < FLAT_DYNRANGE_MIN
    assert ll.flat is True


def test_local_luminance_flat_flag_false_for_wide_range_region():
    gray = np.zeros((10, 10), dtype=np.float32)
    sub = np.ones((10, 10), dtype=bool)
    gray[:] = np.linspace(20, 200, 100, dtype=np.float32).reshape(10, 10)
    ll = local_luminance_light(gray, sub)
    assert ll.dyn_range >= FLAT_DYNRANGE_MIN
    assert ll.flat is False


def test_local_luminance_empty_mask_is_flat_and_zero():
    gray = np.full((6, 6), 100.0, dtype=np.float32)
    sub = np.zeros((6, 6), dtype=bool)
    ll = local_luminance_light(gray, sub)
    assert ll.flat is True
    assert ll.dyn_range == 0.0
    assert np.all(ll.light == 0.0)
