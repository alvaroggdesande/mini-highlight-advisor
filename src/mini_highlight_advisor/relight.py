"""Pure, torch-free relighting of a recovered normal map.

Pinned convention (load-bearing): n = rgb/255*2-1, R=x-right, G=y-up,
B=z-toward-viewer. ps_tool normalizes to this once, so there is NO per-import
flip toggle here. Diffuse-only for v1.
"""
from __future__ import annotations

import numpy as np
from PIL import Image

ALBEDO = 0.6      # flat display albedo (validated spike value)
AMBIENT = 0.15    # ambient fill (validated spike value)


def load_normals(path: str) -> np.ndarray:
    """PNG-encoded normals -> (H,W,3) float32 unit vectors, pinned convention."""
    rgb = np.asarray(Image.open(path).convert("RGB"), dtype=np.float32) / 255.0
    return _decode(rgb)


def _decode(rgb01: np.ndarray) -> np.ndarray:
    n = rgb01 * 2.0 - 1.0
    norm = np.linalg.norm(n, axis=-1, keepdims=True)
    norm[norm == 0] = 1.0
    return (n / norm).astype(np.float32)


def light_dir(az_deg: float, el_deg: float) -> np.ndarray:
    az, el = np.radians(az_deg), np.radians(el_deg)
    return np.array(
        [np.cos(el) * np.cos(az), np.cos(el) * np.sin(az), np.sin(el)],
        dtype=np.float32,
    )


def relight(normals: np.ndarray, mask: np.ndarray, light: np.ndarray):
    """Diffuse relight. Returns (light_field, relit_grey).

    light_field: (H,W) float32 in [0,1], off-mask 0 — the banding light source.
    relit_grey:  (H,W,3) uint8, off-mask 0 — the display base overlays draw on.
    Both derive from the SAME n.l so bands and their background align.
    """
    light_field = np.clip(normals @ light, 0.0, 1.0).astype(np.float32)
    light_field[~mask] = 0.0
    grey = ALBEDO * (AMBIENT + (1.0 - AMBIENT) * light_field)
    grey8 = np.clip(grey * 255.0, 0, 255).astype(np.uint8)
    relit_grey = np.stack([grey8, grey8, grey8], axis=-1)
    relit_grey[~mask] = 0
    return light_field, relit_grey


def plausible_unit_normals(rgb01: np.ndarray, mask: np.ndarray) -> bool:
    """App-side defense: does this decode like a real normal map over the mini?

    A blank/hand-crafted image decodes to degenerate raw vectors; a real map has
    most foreground pixels with a raw magnitude near 1 and z generally positive.
    """
    if not mask.any():
        return False
    raw = rgb01 * 2.0 - 1.0
    fg = raw[mask]
    mags = np.linalg.norm(fg, axis=-1)
    near_unit = np.mean((mags > 0.3) & (mags < 2.0))
    z_positive = np.mean(fg[:, 2] > 0.0)
    return bool(near_unit > 0.7 and z_positive > 0.6)
