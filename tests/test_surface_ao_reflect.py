import numpy as np

from mini_highlight_advisor import surface


def _flat(h=21, w=21):
    n = np.zeros((h, w, 3), np.float32)
    n[..., 2] = 1.0
    return n, np.ones((h, w), bool)


def _two_dips(h=21, w=41):
    """One field, two concave Gaussian valleys of DIFFERENT depth (shared scale).
    Shallow dip centred at col 10 (depth 3), deep dip at col 30 (depth 8)."""
    col = np.arange(w, dtype=np.float32)

    def slope(c0, depth, s=4.0):
        return depth * (col - c0) / (s * s) * np.exp(-((col - c0) ** 2) / (2 * s * s))

    n = np.zeros((h, w, 3), np.float32)
    n[..., 0] = (-(slope(10, 3.0) + slope(30, 8.0)))[None, :]   # outward normal: nx = -dh/dcol
    n[..., 2] = 1.0
    return n, np.ones((h, w), bool)


# --- ambient_occlusion ---

def test_ao_flat_is_fully_exposed():
    n, m = _flat()
    ao = surface.ambient_occlusion(n, m)
    assert ao.dtype == np.float32
    assert np.allclose(ao[m], 1.0, atol=1e-3)


def test_ao_crevice_is_more_occluded_than_flat():
    n, m = _two_dips()
    ao = surface.ambient_occlusion(n, m)
    row = ao.shape[0] // 2
    assert ao[row, 30] < ao[row, 0]        # bottom of the deep dip vs a flat edge


def test_ao_monotone_with_recess_depth():
    n, m = _two_dips()
    ao = surface.ambient_occlusion(n, m)
    deep = ao[:, 26:35].min()              # deep dip window (depth 8)
    shallow = ao[:, 6:15].min()            # shallow dip window (depth 3)
    assert deep < shallow


def test_ao_off_mask_is_zero():
    n, m = _two_dips()
    m2 = m.copy()
    m2[:, :3] = False
    ao = surface.ambient_occlusion(n, m2)
    assert np.all(ao[~m2] == 0.0)


# --- reflect ---

def test_reflect_facing_viewer_is_identity():
    n = np.zeros((5, 5, 3), np.float32); n[..., 2] = 1.0     # N = +Z
    r = surface.reflect(np.array([0, 0, 1], np.float32), n)  # V = +Z
    assert np.allclose(r, np.array([0, 0, 1], np.float32), atol=1e-5)


def test_reflect_orthogonal_view_flips_view():
    n = np.zeros((3, 3, 3), np.float32); n[..., 2] = 1.0     # N = +Z
    r = surface.reflect(np.array([1, 0, 0], np.float32), n)  # V = +X, N.V = 0 => R = -V
    assert np.allclose(r, np.array([-1, 0, 0], np.float32), atol=1e-5)


def test_reflect_output_is_unit_length():
    rng = np.random.default_rng(0)
    raw = rng.normal(size=(6, 6, 3)).astype(np.float32)
    n = surface._validate(raw)
    r = surface.reflect(np.array([0, 0, 1], np.float32), n)
    assert np.allclose(np.linalg.norm(r, axis=-1), 1.0, atol=1e-4)
