# src/mini_highlight_advisor/materials.py
"""Pure, torch-free material shading derived from a normal field.

NMM (Non-Metallic Metal): a metal surface is a mirror, so it shows the
environment, not its own colour. We sample a two-zone virtual environment
(bright sky above a horizon, dark ground below) along the per-pixel reflection
vector R = reflect(view, normals). The resulting brightness re-bands the region
so the classic NMM light/dark split + horizon land geometrically.

Consumes the SAME pinned convention as surface.py / relight.py
(R=x-right, G=y-up, B=z-toward-viewer) and the already-normalized field.
numpy in, numpy out; no Streamlit, no torch. A future osl_light() sibling
(coloured object-source glow via N.L) will live here too.
"""
from __future__ import annotations

import numpy as np

from .surface import reflect


def _smoothstep(a: float, b: float, x: np.ndarray) -> np.ndarray:
    t = np.clip((x - a) / (b - a + 1e-12), 0.0, 1.0)
    return t * t * (3.0 - 2.0 * t)


# ---------------------------------------------------------------------------
# Procedural NMM environment disk (build_nmm_env) — Task 1
# ---------------------------------------------------------------------------

def _disk_coords(size: int):
    yy, xx = np.mgrid[0:size, 0:size].astype(np.float32)
    u = xx / (size - 1) * 2.0 - 1.0            # x-right
    v = 1.0 - yy / (size - 1) * 2.0            # y-up: row 0 -> v=+1 (sky)
    return u, v


def _vert_profile(v: np.ndarray, v_h: float, bounce: float) -> np.ndarray:
    """Non-monotone sky->horizon->ground->bounce curve down the disk."""
    sky_level, ground_level = 0.7, 0.20
    above = _smoothstep(v_h, v_h + 0.25, v)                 # 0 below horizon, 1 in sky
    base = ground_level + (sky_level - ground_level) * above
    notch = np.exp(-((v - v_h) / 0.06) ** 2).astype(np.float32)   # dark horizon line
    rim = 1.0 - _smoothstep(-1.0, -0.6, v)                  # 1 at bottom rim, 0 above
    return (base * (1.0 - notch) + bounce * rim * (1.0 - above)).astype(np.float32)


NMM_PRESETS = {
    "Steel":  dict(horizon=0.50, light_dir=135.0, bounce=0.30, hotspot=0.50),
    "Gold":   dict(horizon=0.55, light_dir=120.0, bounce=0.45, hotspot=0.45),
    "Chrome": dict(horizon=0.50, light_dir=135.0, bounce=0.20, hotspot=0.80),
}


def build_nmm_env(size: int = 256, *, horizon: float = 0.5, light_dir: float = 135.0,
                  bounce: float = 0.35, hotspot: float = 0.5) -> np.ndarray:
    """Procedural NMM environment disk, (size, size) float32 in [0,1].

    Disk coords u=x-right, v=y-up over the unit circle (same pinned convention as
    surface.py / relight.py). Off-disk pixels are 0 and never sampled by nmm_light
    (grazing rays clamp to the rim). Four terms: a non-monotone vertical profile
    (hard horizon + ground bounce), a broad directional streak, and a tight glint.
    """
    size = max(16, int(size))
    horizon = float(np.clip(horizon, 0.0, 1.0))
    bounce = float(np.clip(bounce, 0.0, 1.0))
    hotspot = float(np.clip(hotspot, 0.0, 1.0))
    u, v = _disk_coords(size)
    disk = (u * u + v * v) <= 1.0
    v_h = 1.0 - 2.0 * horizon

    E = _vert_profile(v, v_h, bounce)

    theta = np.radians(float(light_dir))
    r_L = 0.6
    pu, pv = r_L * np.cos(theta), r_L * np.sin(theta)
    d2 = (u - pu) ** 2 + (v - pv) ** 2
    streak = 0.20 * np.exp(-d2 / (2.0 * 0.20 ** 2)).astype(np.float32)
    E = np.clip(E + streak, 0.0, 1.0)

    sigma_hot = 0.22 * (1.0 - hotspot) + 0.03           # bigger hotspot -> tighter
    glint = np.exp(-d2 / (2.0 * sigma_hot ** 2)).astype(np.float32)
    E = np.maximum(E, glint)

    E[~disk] = 0.0
    return E.astype(np.float32)


# ---------------------------------------------------------------------------
# Weight of the horizon smoothstep vs. the raw reflection ramp. The ramp term
# (1 - _CONTRAST) keeps the mapping STRICTLY monotonic in R_y so no two distinct
# reflection values collapse to the same brightness — see the long comment in
# nmm_light for why that matters for banding.
_CONTRAST = 0.7


def nmm_light(normals: np.ndarray, mask: np.ndarray,
              view=(0.0, 0.0, 1.0), horizon: float = 0.5,
              softness: float = 0.15) -> np.ndarray:
    """Reflection-environment brightness for NMM, in [0,1]; off-mask 0.

    A metal surface mirrors a two-zone virtual environment (bright sky above a
    horizon, dark ground below), sampled along the per-pixel reflection vector's
    y-up component ``R_y`` (in ``[-1, 1]``). ``horizon`` in ``[0, 1]`` slides the
    sky/ground split (0 = all sky/bright, 1 = all ground/dark); ``softness`` sets
    the contrast of that split.

    Critically, the result is a **strictly monotonic** function of ``R_y``: the
    horizon smoothstep supplies the NMM sky/ground contrast, but it is blended
    with the raw reflection ramp so the brightness never saturates into large
    tied clusters. A pure smoothstep with a narrow ``softness`` clips most of the
    surface to exactly 0 or 1 (a near-binary field); rank-based banding then
    breaks those ties by pixel raster order and paints flat horizontal image
    stripes instead of following the geometry. Keeping the mapping monotonic
    makes banding rank track the surface everywhere.
    """
    m = mask.astype(bool)
    r = reflect(np.asarray(view, np.float32), normals)   # reflect() validates normals
    ry = r[..., 1]                                        # y-up component, in [-1, 1]
    ramp = (0.5 * (ry + 1.0)).astype(np.float32)         # [0,1], strictly increasing in R_y
    thr = 2.0 * float(horizon) - 1.0                     # horizon height -> R_y threshold
    contrast = _smoothstep(thr - softness, thr + softness, ry).astype(np.float32)
    # Blend keeps strict monotonicity (ramp term never plateaus) while contrast
    # gives the characteristic NMM sky/ground split around the horizon.
    light = (_CONTRAST * contrast + (1.0 - _CONTRAST) * ramp).astype(np.float32)
    light[~m] = 0.0
    return light
