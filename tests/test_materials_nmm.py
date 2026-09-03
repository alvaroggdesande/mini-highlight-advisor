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


# ---------------------------------------------------------------------------
# Task 1: build_nmm_env + NMM_PRESETS
# ---------------------------------------------------------------------------
from mini_highlight_advisor.materials import build_nmm_env, NMM_PRESETS  # noqa: E402


def _disk_col(env):
    """Center column of the disk, top->bottom (sky->ground)."""
    size = env.shape[0]
    return env[:, size // 2]


def test_env_vertical_profile_is_non_monotone():
    # sky (top) bright, horizon row darkest, ground bounce (bottom rim) brighter
    # than the ground band just above it. A monotone v1 curve could not pass this.
    env = build_nmm_env(size=201, horizon=0.5)          # v_h = 0 -> horizon at center row
    col = _disk_col(env)
    size = env.shape[0]
    sky = col[size // 6]                 # high up = sky
    horizon = col[size // 2]             # center row = horizon line
    ground = col[int(size * 0.72)]       # below horizon = ground
    bottom_rim = col[size - 3]           # near bottom rim = ground bounce
    assert sky > horizon
    assert horizon <= ground             # horizon is the darkest zone
    assert bottom_rim > ground           # bounce lifts the rim above the ground band


def test_env_hard_horizon_is_crisp():
    env = build_nmm_env(size=201, horizon=0.5)
    col = _disk_col(env)
    size = env.shape[0]
    just_above = col[size // 2 - int(size * 0.10)]
    horizon = col[size // 2]
    assert just_above - horizon > 0.25   # sharp dark break, not a soft ramp


def _argmax_uv(env):
    size = env.shape[0]
    r, c = np.unravel_index(int(np.argmax(env)), env.shape)
    u = c / (size - 1) * 2 - 1
    v = 1 - r / (size - 1) * 2
    return u, v


def test_env_brightest_pixel_sits_at_light_dir():
    u, v = _argmax_uv(build_nmm_env(size=201, light_dir=135.0))
    assert u < -0.1 and v > 0.1          # upper-left glint


def test_env_rotating_light_180_moves_glint_opposite():
    u0, v0 = _argmax_uv(build_nmm_env(size=201, light_dir=135.0))
    u1, v1 = _argmax_uv(build_nmm_env(size=201, light_dir=315.0))
    assert np.sign(u1) == -np.sign(u0) and np.sign(v1) == -np.sign(v0)


def test_env_raising_horizon_moves_dark_band_down():
    def dark_row(h):
        env = build_nmm_env(size=201, horizon=h)
        col = env[:, 100]
        disk_rows = np.where(col > 0)[0]     # ignore off-disk zeros at the poles
        return disk_rows[np.argmin(col[disk_rows])]
    assert dark_row(0.7) > dark_row(0.3)     # higher horizon -> darkest row lower down


def test_env_raising_hotspot_concentrates_peak():
    def peak_area(hs):
        env = build_nmm_env(size=201, hotspot=hs)
        return int((env > 0.95).sum())
    assert peak_area(0.9) < peak_area(0.2)   # tighter glint = fewer near-white px


def test_env_presets_are_valid_disks():
    for knobs in NMM_PRESETS.values():
        env = build_nmm_env(size=64, **knobs)
        assert env.shape == (64, 64) and env.dtype == np.float32
        assert np.all(np.isfinite(env)) and env.min() >= 0.0 and env.max() <= 1.0


def test_env_clamps_out_of_range_knobs_without_crash():
    env = build_nmm_env(size=32, horizon=5.0, bounce=-2.0, hotspot=9.0)
    assert np.all(np.isfinite(env)) and env.max() <= 1.0
