import numpy as np
from PIL import Image
from mini_highlight_advisor.overlay import paint_preview, render_legend, compose_panel, per_band_images, BandStep


def test_paint_preview_colors_bands_and_darkens_background():
    rgb = np.full((4, 4, 3), 100, dtype=np.uint8)
    bands = np.array([[0, 1, 1, 1], [-1, -1, -1, -1], [0, 0, 1, 1], [0, 0, 1, 1]], dtype=np.int32)
    mask = bands >= 0
    colors = [np.array([255, 0, 0], np.float32), np.array([0, 0, 255], np.float32)]
    out = paint_preview(rgb, bands, mask, colors, alpha=1.0)
    assert out.dtype == np.uint8
    assert tuple(out[0, 0]) == (255, 0, 0)      # band 0 -> red
    assert tuple(out[0, 1]) == (0, 0, 255)      # band 1 -> blue
    assert out[1, 0].sum() < rgb[1, 0].sum()    # background darkened


def test_render_legend_dimensions():
    img = render_legend(
        colors=[np.array([20, 20, 20], np.float32), np.array([230, 230, 230], np.float32)],
        names=["Abaddon Black", "White Scar"],
        roles=["Shadow", "Highlight"],
        coverage=[70.0, 30.0],
        height=400,
    )
    assert isinstance(img, Image.Image)
    assert img.size == (430, 400)


def test_compose_panel_width_is_sum():
    a = np.zeros((100, 50, 3), np.uint8)
    b = np.zeros((100, 60, 3), np.uint8)
    legend = Image.new("RGB", (430, 100))
    panel = compose_panel(a, b, legend)
    assert panel.width == 50 + 60 + 430 + 20  # two 10px gaps
    assert panel.height == 100


def _fixture():
    # 4x4 with an off-mask row (-1); bands 0 (dark) .. 2 (light)
    bands = np.array(
        [[0, 0, 1, 2],
         [0, 0, 1, 2],
         [-1, -1, -1, -1],
         [0, 1, 1, 2]],
        dtype=np.int32,
    )
    mask = bands >= 0
    rgb = np.full((4, 4, 3), 100, dtype=np.uint8)
    colors = [
        np.array([255, 0, 0], np.float32),   # band 0
        np.array([0, 255, 0], np.float32),   # band 1
        np.array([0, 0, 255], np.float32),   # band 2
    ]
    return rgb, bands, mask, colors


def _painted_region(out, color):
    # with alpha=1.0 active pixels equal the paint color exactly
    return np.all(out == color.astype(np.uint8), axis=-1)


def test_per_band_images_returns_one_step_per_color_in_order():
    rgb, bands, mask, colors = _fixture()
    steps = per_band_images(rgb, bands, mask, colors, alpha=1.0)
    assert len(steps) == 3
    assert [s.index for s in steps] == [0, 1, 2]
    assert all(isinstance(s, BandStep) for s in steps)


def test_step0_cumulative_covers_full_mask():
    rgb, bands, mask, colors = _fixture()
    steps = per_band_images(rgb, bands, mask, colors, alpha=1.0)
    painted = _painted_region(steps[0].cumulative_rgb, colors[0])
    assert np.array_equal(painted, mask)


def test_exact_region_equals_band_equals_k():
    rgb, bands, mask, colors = _fixture()
    steps = per_band_images(rgb, bands, mask, colors, alpha=1.0)
    for k in (0, 1):  # last step has no exact image
        painted = _painted_region(steps[k].exact_rgb, colors[k])
        assert np.array_equal(painted, (bands == k) & mask)


def test_cumulative_regions_are_nested_and_shrinking():
    rgb, bands, mask, colors = _fixture()
    steps = per_band_images(rgb, bands, mask, colors, alpha=1.0)
    prev = None
    for k, s in enumerate(steps):
        region = _painted_region(s.cumulative_rgb, colors[k])
        assert np.array_equal(region, (bands >= k) & mask)
        if prev is not None:
            # region(k) subset of region(k-1)
            assert np.all(prev[region])
        prev = region


def test_last_step_has_no_exact_image():
    rgb, bands, mask, colors = _fixture()
    steps = per_band_images(rgb, bands, mask, colors, alpha=1.0)
    assert steps[-1].is_last is True
    assert steps[-1].exact_rgb is None
    assert all(s.is_last is False for s in steps[:-1])
    assert all(s.exact_rgb is not None for s in steps[:-1])


def test_nonactive_interior_pixel_is_dimmed():
    rgb, bands, mask, colors = _fixture()
    steps = per_band_images(rgb, bands, mask, colors, alpha=1.0)
    # pixel (0,0) is band 0: non-active in the last step (band 2) and not
    # adjacent to any band-2 pixel, so it is neither painted nor on the outline.
    out = steps[2].cumulative_rgb
    assert out[0, 0].sum() < rgb[0, 0].sum()


def test_output_shape_and_dtype_match_input():
    rgb, bands, mask, colors = _fixture()
    steps = per_band_images(rgb, bands, mask, colors, alpha=1.0)
    assert steps[0].cumulative_rgb.shape == rgb.shape
    assert steps[0].cumulative_rgb.dtype == np.uint8
