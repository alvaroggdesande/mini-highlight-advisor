import numpy as np
from PIL import Image
from types import SimpleNamespace
from mini_highlight_advisor.overlay import paint_preview, render_legend, compose_panel, per_band_images, BandStep, paint_regions, swatch_board, edge_steps


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
    rgb, bands, mask, colors = _fixture()  # uniform 100 input
    steps = per_band_images(rgb, bands, mask, colors, alpha=1.0)
    # (0,0) is band 0: non-active in the last step (band 2), never painted.
    # Background = greyscale(100) * 0.4 = 40 per channel.
    out = steps[2].cumulative_rgb
    assert tuple(out[0, 0]) == (40, 40, 40)


def test_output_shape_and_dtype_match_input():
    rgb, bands, mask, colors = _fixture()
    steps = per_band_images(rgb, bands, mask, colors, alpha=1.0)
    assert steps[0].cumulative_rgb.shape == rgb.shape
    assert steps[0].cumulative_rgb.dtype == np.uint8


def _non_grey(img):
    return (img[..., 0] != img[..., 1]) | (img[..., 1] != img[..., 2])


def test_every_step_has_zone_rgb_with_matching_shape():
    rgb, bands, mask, colors = _fixture()
    steps = per_band_images(rgb, bands, mask, colors)
    assert all(s.zone_rgb is not None for s in steps)
    assert all(s.zone_rgb.shape == rgb.shape for s in steps)
    assert all(s.zone_rgb.dtype == np.uint8 for s in steps)


def test_zone_accent_region_equals_cumulative_region():
    # uniform-grey input => background stays grey (R==G==B); accent-painted
    # pixels become non-grey, so the non-grey region marks the active zone.
    rgb, bands, mask, colors = _fixture()
    steps = per_band_images(rgb, bands, mask, colors)
    for k, s in enumerate(steps):
        assert np.array_equal(_non_grey(s.zone_rgb), (bands >= k) & mask)


def test_step_background_is_greyscale_and_dimmed():
    # colored uniform input; luma = 0.299*100 + 0.587*40 + 0.114*20 = 55.66
    # background = int(55.66 * 0.4) = 22 per channel.
    bands = np.array(
        [[0, 0, 1, 2],
         [0, 0, 1, 2],
         [-1, -1, -1, -1],
         [0, 1, 1, 2]],
        dtype=np.int32,
    )
    mask = bands >= 0
    rgb = np.empty((4, 4, 3), np.uint8)
    rgb[:] = (100, 40, 20)
    colors = [np.array([255, 0, 0], np.float32),
              np.array([0, 255, 0], np.float32),
              np.array([0, 0, 255], np.float32)]
    steps = per_band_images(rgb, bands, mask, colors, alpha=1.0)
    # row 2 is off-mask => non-active in every step => greyscale-dimmed
    bg_pixel = steps[0].cumulative_rgb[2, 0]
    assert bg_pixel[0] == bg_pixel[1] == bg_pixel[2]  # desaturated
    assert tuple(bg_pixel) == (22, 22, 22)            # exact dim value


def test_no_pure_white_outline_pixels():
    # guards outline removal: with a non-white input and non-white paints,
    # no pixel in any step image should be pure white.
    bands = np.array(
        [[0, 0, 1, 2],
         [0, 0, 1, 2],
         [-1, -1, -1, -1],
         [0, 1, 1, 2]],
        dtype=np.int32,
    )
    mask = bands >= 0
    rgb = np.empty((4, 4, 3), np.uint8)
    rgb[:] = (100, 40, 20)
    colors = [np.array([255, 0, 0], np.float32),
              np.array([0, 255, 0], np.float32),
              np.array([0, 0, 255], np.float32)]
    steps = per_band_images(rgb, bands, mask, colors, alpha=1.0)
    for s in steps:
        for img in (s.zone_rgb, s.cumulative_rgb, s.exact_rgb):
            if img is not None:
                assert not np.any(np.all(img == 255, axis=-1))


def test_paint_regions_composites_each_region_in_its_submask():
    rgb = np.full((4, 4, 3), 100, np.uint8)
    left = np.zeros((4, 4), bool); left[:, :2] = True
    right = np.zeros((4, 4), bool); right[:, 2:] = True
    p_left = SimpleNamespace(sub_mask=left, bands=np.zeros((4, 4), int),
                             colors=[np.array([255, 0, 0], np.float32)])
    p_right = SimpleNamespace(sub_mask=right, bands=np.zeros((4, 4), int),
                              colors=[np.array([0, 0, 255], np.float32)])
    out = paint_regions(rgb, [p_left, p_right])
    assert out.shape == rgb.shape and out.dtype == np.uint8
    assert out[0, 0, 0] > out[0, 0, 2]   # left pixel is reddish
    assert out[0, 3, 2] > out[0, 3, 0]   # right pixel is bluish


def test_swatch_board_returns_image_and_grows_with_rows():
    regs = [("Robe", [np.array([200, 0, 0], np.float32)]),
            ("Blade", [np.array([50, 50, 50], np.float32),
                       np.array([210, 210, 210], np.float32)])]
    img = swatch_board(regs)
    assert isinstance(img, Image.Image)
    assert img.width > 0 and img.height > 0
    assert swatch_board(regs).height > swatch_board(regs[:1]).height


# Edge steps tests

def _two_plate_rgb(size=40):
    light = np.full((size, size), 120.0, np.float32)
    light[:, : size // 2] = 200.0
    rgb = np.stack([light, light, light], -1).astype(np.uint8)
    mask = np.ones((size, size), bool)
    return rgb, light, mask


def test_edge_steps_one_tier_by_default():
    rgb, light, mask = _two_plate_rgb()
    colors = [np.array([c, c, c], np.float32) for c in (10, 80, 150, 220, 255)]
    steps = edge_steps(rgb, light, mask, colors, sensitivity=0.5, extreme=False, start_index=5)
    assert len(steps) == 1
    assert steps[0].kind == "edge"
    assert steps[0].label == "Edge Highlight"
    assert steps[0].index == 5


def test_edge_steps_two_tier_when_extreme():
    rgb, light, mask = _two_plate_rgb()
    colors = [np.array([c, c, c], np.float32) for c in (10, 80, 150, 220, 255)]
    steps = edge_steps(rgb, light, mask, colors, sensitivity=0.5, extreme=True, start_index=5)
    assert [s.label for s in steps] == ["Edge Highlight", "Extreme Edge Highlight"]
    assert steps[-1].is_last is True
    assert steps[0].is_last is False


def test_edge_steps_one_tier_fallback_few_colors():
    rgb, light, mask = _two_plate_rgb()
    colors = [np.array([c, c, c], np.float32) for c in (10, 150, 255)]  # 3 bands
    steps = edge_steps(rgb, light, mask, colors, sensitivity=0.5, extreme=True, start_index=3)
    assert len(steps) == 1  # not enough distinct highlight colours -> one tier


def test_edge_steps_one_tier_fallback_four_bands():
    """4 bands = [Shadow, Base, Midtone, Highlight] -> only ONE highlight-tier
    colour, so extreme still falls back to one tier. Two-tier needs n >= 5."""
    rgb, light, mask = _two_plate_rgb()
    colors = [np.array([c, c, c], np.float32) for c in (10, 90, 170, 255)]  # 4 bands
    steps = edge_steps(rgb, light, mask, colors, sensitivity=0.5, extreme=True, start_index=4)
    assert len(steps) == 1  # n < 5 -> one tier


def test_paint_preview_draws_edge_overlay():
    size = 20
    rgb = np.zeros((size, size, 3), np.uint8)
    mask = np.ones((size, size), bool)
    bands = np.zeros((size, size), np.int32)
    colors = [np.array([0, 0, 0], np.float32)]
    edge = np.zeros((size, size), bool)
    edge[5, :] = True
    red = np.array([255, 0, 0], np.float32)
    out = paint_preview(rgb, bands, mask, colors, edge_overlays=[(edge, red)])
    # row 5 should carry red; a non-edge row should not
    assert out[5, 10, 0] > 150
    assert out[0, 10, 0] < 50
