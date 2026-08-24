from pathlib import Path
import numpy as np
from PIL import Image

from mini_highlight_advisor import relight

FIX = Path(__file__).parent / "fixtures" / "ps"


def _mask():
    return np.asarray(Image.open(FIX / "synth_mask.png").convert("L")) > 127


def test_load_normals_pins_z_toward_viewer():
    # rgb (128,128,255) decodes ~[0,0,1] under the pinned convention.
    n = relight.load_normals(str(FIX / "synth_normal.png"))
    assert n.shape[2] == 3
    # a background pixel was encoded flat-facing-viewer
    assert np.allclose(n[0, 0], [0, 0, 1], atol=0.02)


def test_load_normals_renormalizes_to_unit():
    n = relight.load_normals(str(FIX / "synth_normal.png"))
    norms = np.linalg.norm(n, axis=-1)
    assert np.allclose(norms, 1.0, atol=1e-3)


def test_light_dir_zenith_and_horizon():
    assert np.allclose(relight.light_dir(0, 90), [0, 0, 1], atol=1e-6)
    assert np.allclose(relight.light_dir(0, 0), [1, 0, 0], atol=1e-6)


def test_relight_flat_surface_from_zenith_is_uniform():
    m = np.ones((8, 8), bool)
    normals = np.zeros((8, 8, 3), np.float32)
    normals[..., 2] = 1.0                      # all facing viewer
    lf, grey = relight.relight(normals, m, relight.light_dir(0, 90))
    assert np.allclose(lf[m], 1.0, atol=1e-5)
    assert lf.dtype == np.float32
    assert grey.dtype == np.uint8 and grey.shape == (8, 8, 3)


def test_relight_excludes_off_mask():
    m = np.zeros((8, 8), bool); m[2:6, 2:6] = True
    normals = np.zeros((8, 8, 3), np.float32); normals[..., 2] = 1.0
    lf, grey = relight.relight(normals, m, relight.light_dir(0, 90))
    assert np.all(lf[~m] == 0)
    assert np.all(grey[~m] == 0)


def test_highlight_travels_with_light():
    # THE validated behavior: two light dirs put the brightest pixel in
    # different places on the dome.
    n = relight.load_normals(str(FIX / "synth_normal.png"))
    m = _mask()
    lf_l, _ = relight.relight(n, m, relight.light_dir(200, 30))   # from the left
    lf_r, _ = relight.relight(n, m, relight.light_dir(340, 30))   # from the right
    argmax_l = np.unravel_index(np.argmax(np.where(m, lf_l, -1)), lf_l.shape)
    argmax_r = np.unravel_index(np.argmax(np.where(m, lf_r, -1)), lf_r.shape)
    assert argmax_l[1] != argmax_r[1]            # brightest column moves


def test_plausible_unit_normals_accepts_fixture_rejects_blank():
    m = _mask()
    good = np.asarray(Image.open(FIX / "synth_normal.png").convert("RGB"), np.float32) / 255.0
    blank = np.zeros_like(good)                   # decodes to all [-1,-1,-1], degenerate
    assert relight.plausible_unit_normals(good, m) is True
    assert relight.plausible_unit_normals(blank, m) is False
