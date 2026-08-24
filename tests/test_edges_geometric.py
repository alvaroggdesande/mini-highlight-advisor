import numpy as np

from mini_highlight_advisor import relight
from mini_highlight_advisor.edges import (
    edge_mask, geometric_edge_mask, geometric_extreme_edge_mask,
)


def _vridge(h=40, w=40, c0=20, half=8):
    """A convex vertical crest at column c0: nx sweeps -sin..+sin THROUGH the
    crest so curvature (d nx/dcol) is positive, peaking on the crest column."""
    col = np.arange(w, dtype=np.float32)
    ang = np.clip((col - c0) / half, -1.0, 1.0) * (np.pi / 3.0)
    n = np.zeros((h, w, 3), np.float32)
    n[..., 0] = np.sin(ang)[None, :]
    n[..., 2] = np.cos(ang)[None, :]
    return n, np.ones((h, w), bool), c0


def test_geometric_edge_lands_on_crest():
    n, mask, c0 = _vridge()
    g = geometric_edge_mask(n, mask, 0.5)
    cols = np.where(g.any(axis=0))[0]
    assert cols.size > 0
    assert cols.min() >= c0 - 3 and cols.max() <= c0 + 3


def test_geometric_edge_is_light_independent():
    """The core value claim: the light-gradient edge MOVES with the virtual light;
    the curvature edge does not depend on light at all and stays on the crest."""
    n, mask, c0 = _vridge()
    lf1, _ = relight.relight(n, mask, relight.light_dir(0, 30))     # lit from the right
    lf2, _ = relight.relight(n, mask, relight.light_dir(180, 30))   # lit from the left
    e1 = edge_mask(lf1, mask, 0.5)
    e2 = edge_mask(lf2, mask, 0.5)
    g = geometric_edge_mask(n, mask, 0.5)
    assert not np.array_equal(e1, e2)                  # light-gradient edge moves
    cols = np.where(g.any(axis=0))[0]                  # curvature edge sits on crest
    assert cols.size > 0
    assert abs(int(round(cols.mean())) - c0) <= 3


def test_geometric_flat_normals_empty():
    n = np.zeros((30, 30, 3), np.float32); n[..., 2] = 1.0
    mask = np.ones((30, 30), bool)
    assert geometric_edge_mask(n, mask, 0.5).sum() == 0


def test_geometric_speckle_is_dropped():
    """Isolated single-pixel tilts (primer grain / gravel base) must be removed by
    the connected-component filter — no line-like ridge among them."""
    n = np.zeros((60, 60, 3), np.float32); n[..., 2] = 1.0
    for (r, c) in [(10, 10), (20, 40), (35, 15), (48, 50), (30, 30)]:
        n[r, c, 0] = 0.4
        n[r, c, 2] = np.sqrt(1.0 - 0.4 ** 2)
    mask = np.ones((60, 60), bool)
    assert geometric_edge_mask(n, mask, 0.5).sum() == 0


def test_geometric_extreme_is_subset_of_main():
    n, mask, _ = _vridge()
    main = geometric_edge_mask(n, mask, 0.5)
    ext = geometric_extreme_edge_mask(n, mask, 0.5)
    assert np.all(main[ext])
