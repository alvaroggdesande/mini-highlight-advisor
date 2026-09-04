import numpy as np

from mini_highlight_advisor.materials import build_nmm_env
from mini_highlight_advisor.overlay import nmm_env_preview

COLORS = [np.array(c, np.float32) for c in
          ([20, 20, 20], [80, 80, 80], [140, 140, 140], [200, 200, 200], [245, 245, 245])]


def test_env_preview_shape_and_bg():
    env = build_nmm_env(size=64)
    img = nmm_env_preview(env, COLORS, n_bands=5)
    assert img.shape == (64, 64, 3) and img.dtype == np.uint8
    # corners are outside the unit disk -> background colour
    assert tuple(img[0, 0]) == (30, 30, 30)


def test_env_preview_tints_bands_with_palette():
    env = build_nmm_env(size=64)
    img = nmm_env_preview(env, COLORS, n_bands=5)
    # every in-disk pixel is one of the palette colours (not the bg)
    palette_set = {tuple(c.astype(np.uint8)) for c in COLORS}
    size = 64
    yy, xx = np.mgrid[0:size, 0:size]
    u = xx / (size - 1) * 2 - 1
    v = 1 - yy / (size - 1) * 2
    disk = (u * u + v * v) <= 1.0
    disk_pixels = {tuple(px) for px in img[disk]}
    assert disk_pixels.issubset(palette_set)


def test_env_preview_fewer_colors_than_bands_clamps():
    # n_bands > len(colors): top bands clamp to the lightest paint, no index error.
    env = build_nmm_env(size=48)
    img = nmm_env_preview(env, COLORS[:3], n_bands=5)
    assert img.shape == (48, 48, 3) and np.all(np.isfinite(img))
