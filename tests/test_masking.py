import numpy as np
from mini_highlight_advisor.masking import mask_from_alpha, mask_from_depthmap


def test_mask_from_alpha_keeps_opaque_largest_blob():
    alpha = np.zeros((20, 20), dtype=np.uint8)
    alpha[5:15, 5:15] = 255           # big opaque square
    alpha[0:2, 0:2] = 255             # tiny speck (should be dropped)
    m = mask_from_alpha(alpha)
    assert m[10, 10]
    assert not m[0, 0]


def test_mask_from_alpha_drops_semi_transparent_halo():
    alpha = np.full((10, 10), 100, dtype=np.uint8)  # below default thresh 128
    alpha[3:7, 3:7] = 255
    m = mask_from_alpha(alpha)
    assert m[5, 5]
    assert not m[0, 0]


def test_mask_from_depthmap_separates_near_foreground():
    depth = np.zeros((20, 20), dtype=np.float32)   # far background
    depth[5:15, 5:15] = 1.0                         # near figure
    m = mask_from_depthmap(depth)
    assert m[10, 10]
    assert not m[0, 0]
