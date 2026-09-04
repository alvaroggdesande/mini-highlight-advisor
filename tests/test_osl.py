import numpy as np
from PIL import Image
from pathlib import Path
from mini_highlight_advisor import osl

_FIX = Path(__file__).parent / "fixtures" / "ps"

def _load():
    rgb = np.asarray(Image.open(_FIX / "synth_normal.png").convert("RGB"), np.float32) / 255.0
    n = rgb * 2.0 - 1.0
    n /= np.clip(np.linalg.norm(n, axis=-1, keepdims=True), 1e-6, None)
    mask = np.asarray(Image.open(_FIX / "synth_mask.png").convert("L")) > 127
    return n.astype(np.float32), mask

def test_off_mask_is_zero():
    n, mask = _load()
    g = osl.osl_field(n, mask, x=63.5, y=63.5, height=40.0, reach=40.0, intensity=1.0)
    assert g.shape == mask.shape
    assert np.all(g[~mask] == 0.0)
    assert g.dtype == np.float32

def test_peaks_near_click():
    n, mask = _load()
    # Source right above the apex -> apex normal [0,0,1] faces it, distance 0.
    g = osl.osl_field(n, mask, x=63.5, y=63.5, height=40.0, reach=40.0, intensity=1.0)
    apex = g[60:67, 60:67].mean()
    rim = g[mask].mean()
    assert apex > rim  # brightest at/near the click

def test_face_turned_away_stays_dark():
    n, mask = _load()
    # Source far to the RIGHT. Left-of-centre dome pixels point LEFT -> should stay dark
    # even though some are physically close-ish; right-facing pixels light up.
    g = osl.osl_field(n, mask, x=180.0, y=63.5, height=30.0, reach=60.0, intensity=1.0)
    left = g[mask & (np.arange(mask.shape[1])[None, :] < 45)].mean()
    right = g[mask & (np.arange(mask.shape[1])[None, :] > 82)].mean()
    assert right > left * 2.0  # N.L modulation, not a distance-only stain

def test_axis_pin_y_is_up():
    n, mask = _load()
    # Source ABOVE the top of the dome (small image-y). With the correct py - sy sign,
    # the top half (normals point up = ny>0) lights up more than the bottom half.
    g = osl.osl_field(n, mask, x=63.5, y=-40.0, height=30.0, reach=80.0, intensity=1.0)
    ys = np.arange(mask.shape[0])[:, None]
    top = g[mask & (ys < 55)].mean()
    bottom = g[mask & (ys > 72)].mean()
    assert top > bottom  # guards the image-y / green-up flip (the NMM-stripe class of bug)

def test_falloff_monotonic_in_distance():
    n, mask = _load()
    # Flat-facing background disabled by mask; use a synthetic flat normal field so only
    # distance varies (facing constant = 1 for a source straight in front).
    flat = np.zeros((100, 100, 3), np.float32); flat[..., 2] = 1.0
    m = np.ones((100, 100), bool)
    g = osl.osl_field(flat, m, x=50.0, y=50.0, height=10.0, reach=20.0, intensity=1.0)
    near = g[50, 50]; mid = g[50, 60]; far = g[50, 90]
    assert near > mid > far
