import numpy as np
from mini_highlight_advisor import overlay


def test_zero_contribution_is_identity():
    base = (np.random.default_rng(0).integers(0, 255, (8, 8, 3))).astype(np.uint8)
    out = overlay.osl_preview(base, np.zeros((8, 8, 3), np.float32))
    assert np.array_equal(out, base)


def test_screen_brightens_and_clips():
    base = np.full((4, 4, 3), 100, np.uint8)
    contrib = np.full((4, 4, 3), 200.0, np.float32)
    out = overlay.osl_preview(base, contrib)
    assert out.dtype == np.uint8
    assert np.all(out >= base)          # screen never darkens
    assert np.all(out <= 255)
