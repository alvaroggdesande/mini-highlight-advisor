import numpy as np
import pytest
from pathlib import Path
from PIL import Image

from mini_highlight_advisor import surface, relight

FIX = Path(__file__).parent / "fixtures" / "ps"


def _dome():
    """The committed synthetic dome+ridges fixture (normals, mask)."""
    n = relight.load_normals(str(FIX / "synth_normal.png"))
    m = np.asarray(Image.open(FIX / "synth_mask.png").convert("L")) > 127
    return n, m


def _flat(h=20, w=20):
    n = np.zeros((h, w, 3), np.float32)
    n[..., 2] = 1.0                       # all facing the viewer
    return n, np.ones((h, w), bool)


def test_validate_rejects_bad_shape():
    with pytest.raises(ValueError):
        surface._validate(np.zeros((8, 8), np.float32))


def test_validate_renormalizes_to_unit():
    n = np.full((4, 4, 3), 3.0, np.float32)   # non-unit
    out = surface._validate(n)
    assert np.allclose(np.linalg.norm(out, axis=-1), 1.0, atol=1e-4)


def test_flat_region_curvature_is_zero():
    n, m = _flat()
    c = surface.curvature(n, m)
    assert c.shape == (20, 20) and c.dtype == np.float32
    assert np.allclose(c, 0.0, atol=1e-4)


def test_convex_dome_interior_is_positive():
    n, m = _dome()
    c = surface.curvature(n, m)
    # sample a well-inside-the-mask patch (avoid the silhouette boundary)
    interior = np.zeros_like(m)
    interior[50:78, 50:78] = True
    interior &= m
    assert c[interior].mean() > 0.0


def test_off_mask_is_exactly_zero():
    n, m = _dome()
    c = surface.curvature(n, m)
    assert np.all(c[~m] == 0.0)
