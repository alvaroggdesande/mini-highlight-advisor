import numpy as np
from mini_highlight_advisor.regions import Region, assign_owners, scale_points, polygon_to_mask
from mini_highlight_advisor.palette import PaintColor


def test_assign_owners_last_wins_on_overlap():
    base = np.ones((4, 4), bool)
    a = np.zeros((4, 4), bool); a[:, :3] = True   # cols 0,1,2
    b = np.zeros((4, 4), bool); b[:, 1:] = True    # cols 1,2,3 (overlaps 1,2)
    owner = assign_owners(base, [a, b])
    assert owner[0, 0] == 0    # only a
    assert owner[0, 1] == 1    # overlap -> b (last wins)
    assert owner[0, 3] == 1    # only b


def test_assign_owners_offmask_and_default():
    base = np.ones((2, 2), bool); base[0, 0] = False
    owner = assign_owners(base, [])
    assert owner[0, 0] == -2   # off base mask
    assert owner[1, 1] == -1   # on-mask, unowned -> default


def test_region_is_constructible():
    r = Region("Robe", np.ones((2, 2), bool), [PaintColor("A", "#101010")], [1.0])
    assert r.name == "Robe" and len(r.palette) == len(r.coverage)


def test_scale_points_scales_each_axis_independently():
    assert scale_points([(2.0, 3.0)], 2.0, 0.5) == [(4.0, 1.5)]


def test_polygon_to_mask_fills_interior_not_exterior():
    square = [(1, 1), (1, 4), (4, 4), (4, 1)]
    m = polygon_to_mask(square, (6, 6))
    assert m.dtype == bool
    assert m.shape == (6, 6)
    assert m[2, 2]            # inside
    assert not m[0, 0]       # outside


def test_polygons_to_mask_unions_disjoint_shapes():
    from mini_highlight_advisor.regions import polygons_to_mask
    a = [(0, 0), (0, 2), (2, 2), (2, 0)]      # top-left block
    b = [(5, 5), (5, 7), (7, 7), (7, 5)]      # bottom-right block
    m = polygons_to_mask([a, b], (8, 8))
    assert m.dtype == bool and m.shape == (8, 8)
    assert m[1, 1] and m[6, 6]                # both filled
    assert not m[1, 6]                        # gap between them stays empty


def test_polygons_to_mask_single_matches_polygon_to_mask():
    from mini_highlight_advisor.regions import polygons_to_mask, polygon_to_mask
    sq = [(1, 1), (1, 4), (4, 4), (4, 1)]
    assert np.array_equal(polygons_to_mask([sq], (6, 6)), polygon_to_mask(sq, (6, 6)))


def test_polygons_to_mask_empty_is_all_false():
    from mini_highlight_advisor.regions import polygons_to_mask
    m = polygons_to_mask([], (4, 4))
    assert m.shape == (4, 4) and not m.any()
