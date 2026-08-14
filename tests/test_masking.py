import numpy as np
from mini_highlight_advisor import masking
from mini_highlight_advisor.masking import mask_from_alpha, mask_from_grabcut, compute_mask


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


def test_mask_from_grabcut_isolates_centered_blob():
    # Bright centered square on a dark background — no alpha channel.
    rgb = np.full((100, 100, 3), 20, dtype=np.uint8)
    rgb[30:70, 30:70] = 230
    m = mask_from_grabcut(rgb)
    assert m[50, 50]        # blob centre is foreground
    assert not m[2, 2]      # a corner is background


def test_compute_mask_uses_alpha_when_present():
    rgb = np.zeros((20, 20, 3), dtype=np.uint8)
    alpha = np.zeros((20, 20), dtype=np.uint8)
    alpha[5:15, 5:15] = 255
    m = compute_mask(rgb, alpha)
    assert m[10, 10]
    assert not m[0, 0]


def test_compute_mask_falls_back_to_grabcut_without_alpha(monkeypatch):
    rgb = np.zeros((8, 8, 3), dtype=np.uint8)
    sentinel = np.ones((8, 8), dtype=bool)
    monkeypatch.setattr(masking, "mask_from_grabcut", lambda img: sentinel)
    out = compute_mask(rgb, None)
    assert out is sentinel
