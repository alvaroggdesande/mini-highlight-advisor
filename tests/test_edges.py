# tests/test_edges.py
import numpy as np
from mini_highlight_advisor.edges import edge_mask, extreme_edge_mask


def _two_plate(bright=200.0, dark=120.0, size=40):
    """Left half bright plate, right half darker plate: one vertical step edge."""
    light = np.full((size, size), dark, np.float32)
    light[:, : size // 2] = bright
    mask = np.ones((size, size), bool)
    return light, mask


def test_edge_lands_on_bright_side():
    light, mask = _two_plate()
    e = edge_mask(light, mask, 0.5)
    cols = np.where(e.any(axis=0))[0]
    assert cols.size > 0
    # the step is at col 20; kept pixels must sit on the bright (left) side, <= boundary
    assert cols.max() <= light.shape[1] // 2


def test_edge_is_thin():
    light, mask = _two_plate()
    e = edge_mask(light, mask, 0.5)
    per_row = e.sum(axis=1)
    # <=4: the Gaussian pre-blur widens a hard step by ~1px vs a raw Sobel line
    assert per_row[per_row > 0].max() <= 4


def test_dim_plate_still_edges():
    """Same relative step but globally dim: adaptive threshold must still fire."""
    light, mask = _two_plate(bright=90.0, dark=40.0)
    e = edge_mask(light, mask, 0.5)
    assert e.sum() > 0


def test_flat_region_has_no_edges():
    light = np.full((40, 40), 150.0, np.float32)
    mask = np.ones((40, 40), bool)
    assert edge_mask(light, mask, 0.5).sum() == 0


def test_speckle_is_dropped():
    """Isolated high-gradient specks (texture/primer grain, e.g. a gravel base)
    must be removed by the connected-component filter; only line-like edges survive."""
    light = np.full((60, 60), 120.0, np.float32)
    for (r, c) in [(10, 10), (20, 40), (35, 15), (48, 50), (30, 30)]:
        light[r, c] = 240.0  # scattered bright specks, no long edge among them
    mask = np.ones((60, 60), bool)
    assert edge_mask(light, mask, 0.5).sum() == 0


def test_extreme_is_subset_of_main():
    light, mask = _two_plate()
    main = edge_mask(light, mask, 0.5)
    ext = extreme_edge_mask(light, mask, 0.5)
    assert np.all(main[ext])  # every extreme pixel is also a main-edge pixel


def test_higher_sensitivity_more_edges():
    # gentle gradient ramp so percentile choice actually changes the count
    light = np.tile(np.linspace(60, 200, 40, dtype=np.float32), (40, 1))
    mask = np.ones((40, 40), bool)
    assert edge_mask(light, mask, 0.9).sum() >= edge_mask(light, mask, 0.1).sum()
