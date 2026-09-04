"""Object-Source Lighting: a coloured point light placed on a PS-normal mini.

Pure numpy, torch-free, Streamlit-free. Consumes the pinned normal convention
(R=x-right, G=y-UP, B=z-toward-viewer). Image rows grow DOWNWARD, so "up" is
negative image-y: direction vectors are built as [sx-px, py-sy, height].
"""
from __future__ import annotations

import numpy as np
from mini_highlight_advisor.banding import band_light


def osl_field(normals: np.ndarray, mask: np.ndarray, x: float, y: float,
              height: float, reach: float, intensity: float) -> np.ndarray:
    """Per-pixel glow amount from a point source at screen (x, y) floating `height`
    off the surface plane. Returns (H,W) float32 in [0,1], 0 off-mask.

    facing  = clip(N . L, 0, 1) with L in the normals' frame (y-up).
    falloff = 1 / (1 + (screen_distance / reach)^2).
    glow    = clip(intensity * facing * falloff, 0, 1).
    """
    h, w = mask.shape
    yy, xx = np.mgrid[0:h, 0:w].astype(np.float32)
    dx = float(x) - xx                 # x-right
    dy = yy - float(y)                 # image-y grows down; py - sy => y-UP frame
    dz = np.full_like(dx, float(height))
    L = np.stack([dx, dy, dz], axis=-1)
    L /= np.clip(np.linalg.norm(L, axis=-1, keepdims=True), 1e-6, None)
    facing = np.clip(np.sum(normals * L, axis=-1), 0.0, 1.0)
    dist = np.sqrt((xx - float(x)) ** 2 + (yy - float(y)) ** 2)
    reach = max(float(reach), 1e-3)
    falloff = 1.0 / (1.0 + (dist / reach) ** 2)
    glow = np.clip(float(intensity) * facing * falloff, 0.0, 1.0).astype(np.float32)
    glow[~mask] = 0.0
    return glow


def osl_ramp(glow: np.ndarray, glow_rgb: np.ndarray, hot_rgb: np.ndarray) -> np.ndarray:
    """base->glow->hot colour, premultiplied by the glow amount (contribution)."""
    t = glow[..., np.newaxis].astype(np.float32)
    colour = (1.0 - t) * np.asarray(glow_rgb, np.float32) + t * np.asarray(hot_rgb, np.float32)
    return (colour * t).astype(np.float32)


def osl_colors(glow_rgb: np.ndarray, hot_rgb: np.ndarray, n: int) -> list[np.ndarray]:
    """n paint colours from faint glow to hot, evenly interpolated."""
    glow_rgb = np.asarray(glow_rgb, np.float32)
    hot_rgb = np.asarray(hot_rgb, np.float32)
    if n <= 1:
        return [glow_rgb.copy()]
    return [((1.0 - t) * glow_rgb + t * hot_rgb).astype(np.float32)
            for t in np.linspace(0.0, 1.0, n)]


def osl_bands(glow: np.ndarray, mask: np.ndarray, coverage: list[float],
              floor: float = 0.08) -> np.ndarray:
    """Band the LIT zone (glow > floor) into len(coverage) nested layers; unlit -> -1."""
    lit = mask & (glow > float(floor))
    if not lit.any():
        return np.full(mask.shape, -1, dtype=int)
    return band_light(glow, lit, coverage)


def osl_field_multi(normals: np.ndarray, mask: np.ndarray, sources) -> np.ndarray:
    """max-composite of osl_field over sources = list of (x,y,height,reach,intensity)."""
    out = np.zeros(mask.shape, np.float32)
    for (x, y, height, reach, intensity) in sources:
        out = np.maximum(out, osl_field(normals, mask, x, y, height, reach, intensity))
    return out
