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

import cv2
import numpy as np

from .surface import reflect


def smooth_normals(normals: np.ndarray, mask: np.ndarray, sigma: float) -> np.ndarray:
    """Masked Gaussian-smooth a normal field, then renormalize to unit length.

    The NMM reflection lookup amplifies normal noise (a small wobble in N throws
    the reflection vector a larger distance across the env disk), so pixel-scale
    noise in a photo/PS-derived normal map turns the tight glint into scattered
    speckle. Blurring the normals BEFORE reflect() collapses that speckle into
    coherent value zones. sigma is in pixels; sigma<=0 is identity.

    Masked blur (blur N*mask and mask, then divide) so background zeros never
    bleed across the silhouette edge. Off-mask pixels are returned unchanged.
    """
    if sigma <= 0:
        return normals
    m = mask.astype(bool)
    mf = m.astype(np.float32)
    num = cv2.GaussianBlur(normals * mf[..., None], (0, 0), sigma)
    den = cv2.GaussianBlur(mf, (0, 0), sigma)[..., None] + 1e-6
    sm = num / den
    mag = np.linalg.norm(sm, axis=-1, keepdims=True)
    mag[mag == 0] = 1.0
    sm = (sm / mag).astype(np.float32)
    out = normals.copy()
    out[m] = sm[m]
    return out


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
# nmm_light — env-matcap sampler (Task 2)
# ---------------------------------------------------------------------------

def _bilinear(img: np.ndarray, row: np.ndarray, col: np.ndarray) -> np.ndarray:
    """Bilinear sample img at fractional (row, col); indices clamped in-bounds."""
    h, w = img.shape
    r = np.clip(row, 0.0, h - 1.0)
    c = np.clip(col, 0.0, w - 1.0)
    r0 = np.floor(r).astype(np.int64); c0 = np.floor(c).astype(np.int64)
    r1 = np.minimum(r0 + 1, h - 1);    c1 = np.minimum(c0 + 1, w - 1)
    fr = (r - r0).astype(np.float32);  fc = (c - c0).astype(np.float32)
    top = img[r0, c0] * (1 - fc) + img[r0, c1] * fc
    bot = img[r1, c0] * (1 - fc) + img[r1, c1] * fc
    return (top * (1 - fr) + bot * fr).astype(np.float32)


def nmm_light(normals: np.ndarray, mask: np.ndarray, *, view=(0.0, 0.0, 1.0),
              env: np.ndarray) -> np.ndarray:
    """Reflection-environment brightness for NMM, (H,W) float32 in [0,1]; off-mask 0.

    A metal surface mirrors the virtual environment `env` (a matcap disk from
    build_nmm_env). Per pixel we take the reflection vector R = reflect(view,
    normals), read (R_x, R_y), and bilinear-sample the disk where that ray points.
    Brightness is a function of the FULL reflected direction, so azimuth (streak +
    glint) and a non-monotone vertical profile (ground bounce) all survive.

    Light-independence: this takes only `normals` + `env`, never a diffuse light
    direction. Grazing rays (R_x^2+R_y^2 > 1) clamp to the unit-circle rim; a
    degenerate all-zero normal field -> R=(0,0,-Z) -> samples the disk center ->
    flat map (never a crash, never mud). Off-mask -> 0.
    """
    m = mask.astype(bool)
    r = reflect(np.asarray(view, np.float32), normals)   # validates + renormalizes
    rx = r[..., 0].astype(np.float32)
    ry = r[..., 1].astype(np.float32)
    rad = np.sqrt(rx * rx + ry * ry)
    scale = np.where(rad > 1.0, 1.0 / np.maximum(rad, 1e-9), 1.0).astype(np.float32)
    u = rx * scale
    v = ry * scale
    size = env.shape[0]
    col = (u * 0.5 + 0.5) * (size - 1)
    row = (0.5 - v * 0.5) * (size - 1)          # v=+1 -> row 0 (sky/top)
    light = _bilinear(env, row, col)
    light[~m] = 0.0
    return light.astype(np.float32)

