import numpy as np
import pytest
from ui import geometry
from mini_highlight_advisor.regions import Region
from mini_highlight_advisor.region_state import RegionBook
from mini_highlight_advisor.palette import DEFAULT_PALETTE


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_mask(h=20, w=20, inner=slice(5, 15)):
    m = np.zeros((h, w), dtype=bool)
    m[inner, inner] = True
    return m


def _make_book(drawn=None):
    pal = list(DEFAULT_PALETTE[:3])
    cov = [0.5, 0.3, 0.2]
    return RegionBook(whole_palette=pal, whole_coverage=cov, drawn=drawn or [])


# ---------------------------------------------------------------------------
# highlight_region_image
# ---------------------------------------------------------------------------

def test_highlight_region_image_preserves_shape():
    rgb = np.full((20, 20, 3), 180, dtype=np.uint8)
    mask = _make_mask()
    region = Region(name="r", mask=mask, palette=list(DEFAULT_PALETTE[:3]), coverage=[0.5, 0.3, 0.2])
    book = _make_book([region])
    out = geometry.highlight_region_image(rgb, book, sel=1)
    assert out.shape == (20, 20, 3)
    assert out.dtype == np.uint8


def test_highlight_region_image_selected_region_brighter_than_outside():
    # Non-selected pixels are dimmed; selected region pixels keep full brightness.
    rgb = np.full((20, 20, 3), 200, dtype=np.uint8)
    mask = _make_mask()
    region = Region(name="r", mask=mask, palette=list(DEFAULT_PALETTE[:3]), coverage=[0.5, 0.3, 0.2])
    book = _make_book([region])
    out = geometry.highlight_region_image(rgb, book, sel=1)
    # Sample interior of selected region (away from drawn boundary)
    region_mean = float(out[7:13, 7:13].mean())
    # Sample clearly outside the region
    outside_mean = float(out[0:3, 0:3].mean())
    assert region_mean > outside_mean, (
        f"Selected region ({region_mean:.1f}) should be brighter than outside ({outside_mean:.1f})"
    )


def test_highlight_region_image_no_drawn_regions_returns_unchanged():
    # When there are no drawn regions (or sel=0), the image is returned as-is.
    rgb = np.full((10, 10, 3), 100, dtype=np.uint8)
    book = _make_book()
    out = geometry.highlight_region_image(rgb, book, sel=0)
    assert np.array_equal(out, rgb[..., :3])


def test_points_from_object_points_form():
    obj = {"points": [{"x": 1, "y": 2}, {"x": 3, "y": 4}]}
    assert geometry.points_from_object(obj) == [(1, 2), (3, 4)]


def test_points_from_object_path_form_uses_segment_endpoints():
    # SVG-ish path: M/L take (x,y); Q's control point is ignored (endpoint = last two).
    obj = {"path": [["M", 0, 0], ["Q", 5, 5, 2, 3], ["z"]]}
    assert geometry.points_from_object(obj) == [(0, 0), (2, 3)]


def test_region_outline_image_shape_and_draws_edges():
    rgb = np.zeros((20, 20, 3), dtype=np.uint8)
    mask = np.zeros((20, 20), dtype=bool)
    mask[5:15, 5:15] = True
    region = Region(name="r", mask=mask, palette=list(DEFAULT_PALETTE[:3]), coverage=[0.5, 0.3, 0.2])
    out = geometry.region_outline_image(rgb, [region])
    assert out.shape == (20, 20, 3)
    assert out.any()  # at least the boundary pixels were coloured
