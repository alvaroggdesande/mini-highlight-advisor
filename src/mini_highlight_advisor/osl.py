"""Object-Source Lighting: a coloured point light placed on a PS-normal mini.

Pure numpy, torch-free, Streamlit-free. Consumes the pinned normal convention
(R=x-right, G=y-UP, B=z-toward-viewer). Image rows grow DOWNWARD, so "up" is
negative image-y: direction vectors are built as [sx-px, py-sy, height].
"""
from __future__ import annotations

import numpy as np


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
