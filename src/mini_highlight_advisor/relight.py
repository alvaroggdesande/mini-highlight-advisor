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


def relight(normals: np.ndarray, mask: np.ndarray, light: np.ndarray,
            albedo: np.ndarray | None = None):
    """Diffuse relight. Returns (light_field, relit_rgb).

    light_field: (H,W) float32 in [0,1], off-mask 0 — the banding light source.
    relit_rgb:   (H,W,3) uint8, off-mask 0 — the display base overlays draw on.
                 When albedo is provided: coloured (albedo × shading).
                 When albedo is None:     grey (ALBEDO_constant × shading), byte-
                                          identical to the previous behaviour.
    albedo must have the same (H,W) as normals; raises ValueError on mismatch.
    """
    if albedo is not None and albedo.shape[:2] != normals.shape[:2]:
        raise ValueError(
            f"albedo shape {albedo.shape[:2]} != normals shape {normals.shape[:2]}")
    light_field = np.clip(normals @ light, 0.0, 1.0).astype(np.float32)
    light_field[~mask] = 0.0
    shading = AMBIENT + (1.0 - AMBIENT) * light_field          # (H,W) in [0,1]
    if albedo is not None:
        colour = albedo * shading[..., np.newaxis]             # (H,W,3) float32
    else:
        colour = np.full((*mask.shape, 3), ALBEDO, dtype=np.float32) * shading[..., np.newaxis]
    colour8 = np.clip(colour * 255.0, 0, 255).astype(np.uint8)
    colour8[~mask] = 0
    return light_field, colour8


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


def load_albedo(path: str) -> np.ndarray:
    """PNG albedo map (baseColor.png from ps_tool) -> (H,W,3) float32 in [0,1], RGB."""
    return np.asarray(Image.open(path).convert("RGB"), dtype=np.float32) / 255.0


def plausible_albedo(albedo: np.ndarray, mask: np.ndarray) -> bool:
    """Defence against importing a garbage PNG as an albedo map.

    Returns True only when albedo is (H,W,3) with the same spatial dims as mask
    and at least some non-zero foreground pixels (a fully-black foreground on a
    non-black mini is suspicious — more likely a wrong file than real albedo).
    """
    if albedo.ndim != 3 or albedo.shape[2] != 3:
        return False
    if albedo.shape[:2] != mask.shape:
        return False
    fg = albedo[mask]
    if not fg.size:
        return False
    return bool(fg.max() > 0.02)
