import numpy as np

from mini_highlight_advisor import relight
from mini_highlight_advisor.edges import cavity_mask, edge_mask, geometric_edge_mask


def _vcrease(h=40, w=40, c0=20, half=8):
    """A concave vertical crease at column c0: nx sweeps +sin..-sin THROUGH the
    crease, so d(nx)/dcol < 0 there and -curvature peaks on the crease column.
    (Sign-flipped mirror of test_edges_geometric._vridge, which is convex.)"""
    col = np.arange(w, dtype=np.float32)
    ang = np.clip((col - c0) / half, -1.0, 1.0) * (np.pi / 3.0)
    n = np.zeros((h, w, 3), np.float32)
    n[..., 0] = -np.sin(ang)[None, :]
    n[..., 2] = np.cos(ang)[None, :]
    return n, np.ones((h, w), bool), c0


def _vridge(h=40, w=40, c0=20, half=8):
    col = np.arange(w, dtype=np.float32)
    ang = np.clip((col - c0) / half, -1.0, 1.0) * (np.pi / 3.0)
    n = np.zeros((h, w, 3), np.float32)
    n[..., 0] = np.sin(ang)[None, :]
    n[..., 2] = np.cos(ang)[None, :]
    return n, np.ones((h, w), bool), c0


def test_cavity_lands_on_crease():
    n, mask, c0 = _vcrease()
    g = cavity_mask(n, mask, 0.5)
    cols = np.where(g.any(axis=0))[0]
    assert cols.size > 0
    assert cols.min() >= c0 - 3 and cols.max() <= c0 + 3


def test_cavity_is_light_independent():
    """Core value claim: the luminance edge MOVES with the virtual light; the
    curvature-recess mask does not depend on light and stays on the crease."""
    n, mask, c0 = _vcrease()
    lf1, _ = relight.relight(n, mask, relight.light_dir(0, 30))
    lf2, _ = relight.relight(n, mask, relight.light_dir(180, 30))
    e1 = edge_mask(lf1, mask, 0.5)
    e2 = edge_mask(lf2, mask, 0.5)
    g = cavity_mask(n, mask, 0.5)
    assert not np.array_equal(e1, e2)                  # luminance response moves
    cols = np.where(g.any(axis=0))[0]
    assert cols.size > 0
    assert abs(int(round(cols.mean())) - c0) <= 3


def test_cavity_convex_ridge_is_empty():
    """A purely convex ridge has no concavity -> recess mask empty (distinct from
    geometric_edge_mask, which fires on exactly this input)."""
    n, mask, _ = _vridge()
    assert cavity_mask(n, mask, 0.5).sum() == 0
    assert geometric_edge_mask(n, mask, 0.5).sum() > 0   # sanity: convex fires edges


def test_cavity_flat_normals_empty():
    n = np.zeros((30, 30, 3), np.float32); n[..., 2] = 1.0
    mask = np.ones((30, 30), bool)
    assert cavity_mask(n, mask, 0.5).sum() == 0


def test_cavity_speckle_is_dropped():
    """Isolated single-pixel concave tilts (primer grain) are removed by the
    connected-component filter."""
    n = np.zeros((60, 60, 3), np.float32); n[..., 2] = 1.0
    for (r, c) in [(10, 10), (20, 40), (35, 15), (48, 50), (30, 30)]:
        n[r, c, 0] = -0.4
        n[r, c, 2] = np.sqrt(1.0 - 0.4 ** 2)
    mask = np.ones((60, 60), bool)
    assert cavity_mask(n, mask, 0.5).sum() == 0
