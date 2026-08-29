# tests/test_materials_nmm.py
import numpy as np

from mini_highlight_advisor import materials


def _flat(h=21, w=21):
    """All normals face the viewer (+Z)."""
    n = np.zeros((h, w, 3), np.float32)
    n[..., 2] = 1.0
    return n, np.ones((h, w), bool)


def _dome(h=41, w=41):
    """Convex hemisphere: normals tip from up (top rows) to down (bottom rows)."""
    yy, xx = np.mgrid[0:h, 0:w].astype(np.float32)
    cy = cx = (h - 1) / 2.0
    r = (h - 1) / 2.0
    dx = (xx - cx) / r
    dy = (yy - cy) / r
    r2 = dx * dx + dy * dy
    mask = r2 <= 1.0
    nx = dx
    ny = -dy                                    # image row grows down; convention is y-UP
    nz = np.sqrt(np.clip(1.0 - r2, 0.0, None))
    n = np.stack([nx, ny, nz], axis=-1).astype(np.float32)
    n[~mask] = np.array([0.0, 0.0, 1.0], np.float32)
    return n, mask


def test_nmm_light_is_float32_and_bounded():
    n, m = _dome()
    out = materials.nmm_light(n, m)
    assert out.dtype == np.float32
    assert out[m].min() >= 0.0 and out[m].max() <= 1.0


def test_flat_front_facing_has_no_horizon():
    # R_y == 0 everywhere -> uniform mid value, no spurious light/dark split.
    n, m = _flat()
    out = materials.nmm_light(n, m, horizon=0.5)
    assert np.allclose(out[m], out[m].flat[0], atol=1e-5)


def test_dome_is_bright_top_dark_bottom():
    n, m = _dome()
    out = materials.nmm_light(n, m, horizon=0.5)
    col = out.shape[1] // 2
    top = out[2, col]            # reflects up -> sky
    bottom = out[-3, col]       # reflects down -> ground
    assert top > bottom


def test_higher_horizon_is_darker_overall():
    # Raising the horizon puts more surface below it (ground) -> lower mean brightness.
    n, m = _dome()
    low = materials.nmm_light(n, m, horizon=0.2)[m].mean()
    high = materials.nmm_light(n, m, horizon=0.8)[m].mean()
    assert low > high


def test_off_mask_is_zero():
    n, m = _dome()
    m2 = m.copy()
    m2[:5, :] = False
    out = materials.nmm_light(n, m2)
    assert np.all(out[~m2] == 0.0)


def test_degenerate_all_zero_normals_is_flat_not_crash():
    n = np.zeros((10, 10, 3), np.float32)       # all-zero -> renormalized defensively
    m = np.ones((10, 10), bool)
    out = materials.nmm_light(n, m)
    assert out.shape == (10, 10)
    assert np.all(np.isfinite(out))


def _blob_with_detail(h=120, w=120):
    """A smooth convex blob PLUS fine surface detail (bumps) — a stand-in for a
    real mini, whose NMM banding must follow the surface, not raster rows."""
    yy, xx = np.mgrid[0:h, 0:w].astype(np.float32)
    cy = cx = (h - 1) / 2.0
    r = (h - 1) / 2.0
    dx = (xx - cx) / r
    dy = (yy - cy) / r
    mask = (dx * dx + dy * dy) <= 1.0
    # ny carries detail in BOTH axes (cos in row, sin in column) so R_y — and
    # therefore the NMM brightness — genuinely varies within each row, not only
    # top-to-bottom.
    nx = dx * 0.6 + 0.15 * np.sin(xx * 0.9)
    ny = -dy * 0.6 + 0.12 * np.cos(yy * 0.9) + 0.12 * np.sin(xx * 0.7)
    nz = np.sqrt(np.clip(1.0 - nx * nx - ny * ny, 0.01, None))
    n = np.stack([nx, ny, nz], -1).astype(np.float32)
    n[~mask] = np.array([0.0, 0.0, 1.0], np.float32)
    return n, mask


def test_nmm_light_is_not_near_binary():
    # Regression: a hard smoothstep horizon saturated R_y into two big tied
    # clusters (~0 and ~1), discarding geometry. The field must instead carry a
    # smooth gradient — most pixels strictly between the extremes.
    n, m = _blob_with_detail()
    out = materials.nmm_light(n, m)                       # defaults
    vals = out[m]
    intermediate = np.mean((vals > 0.02) & (vals < 0.98))
    assert intermediate > 0.5, f"near-binary field: only {intermediate:.0%} intermediate"


def test_nmm_light_is_strictly_monotonic_in_reflection():
    # The banding degeneracy (raster-order horizontal stripes) came from large
    # tied clusters. Guard it at the source: distinct R_y values must map to
    # distinct brightness (no saturation plateaus), so banding rank == geometry
    # rank. We assert a high fraction of unique output values inside the mask.
    n, m = _blob_with_detail()
    out = materials.nmm_light(n, m)
    vals = out[m]
    unique_frac = len(np.unique(vals)) / vals.size
    assert unique_frac > 0.5, f"too many tied values: unique fraction {unique_frac:.0%}"
