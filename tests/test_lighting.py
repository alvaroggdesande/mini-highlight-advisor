import numpy as np
from mini_highlight_advisor.lighting import luminance_light


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
