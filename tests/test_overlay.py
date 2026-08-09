import numpy as np
from PIL import Image
from mini_highlight_advisor.overlay import paint_preview, render_legend, compose_panel


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
