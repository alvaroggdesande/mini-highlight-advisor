import numpy as np
from ui import geometry
from mini_highlight_advisor.regions import Region
from mini_highlight_advisor.palette import DEFAULT_PALETTE


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
