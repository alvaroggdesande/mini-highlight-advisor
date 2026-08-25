"""Curvature-derived highlight and recess masks. Operator (spike gate 2026-08-12): Sobel gradient at ~p88
with a Gaussian pre-blur and connected-component speckle removal, bright-side
filtered. Canny rejected (too noisy on primer grain and textured bases)."""
from __future__ import annotations

import cv2
import numpy as np

from .surface import curvature

_MIN_EDGE_AREA = 8  # drop connected components smaller than this (texture speckle)


def _grad_mag(light: np.ndarray, mask: np.ndarray) -> np.ndarray:
    l = cv2.GaussianBlur(light.astype(np.float32), (3, 3), 0)  # calm primer grain
    gx = cv2.Sobel(l, cv2.CV_32F, 1, 0, ksize=3)
    gy = cv2.Sobel(l, cv2.CV_32F, 0, 1, ksize=3)
    mag = np.hypot(gx, gy)
    mag[~mask] = 0.0
    return mag


def _bright_side(light: np.ndarray, mask: np.ndarray, win: int = 9) -> np.ndarray:
    local = cv2.blur(light.astype(np.float32), (win, win))
    return (light.astype(np.float32) >= local) & mask


def _despeckle(edges: np.ndarray, min_area: int = _MIN_EDGE_AREA) -> np.ndarray:
    n, labels, stats, _ = cv2.connectedComponentsWithStats(
        edges.astype(np.uint8), connectivity=8)
    out = np.zeros(edges.shape, bool)
    for i in range(1, n):  # 0 is background
        if stats[i, cv2.CC_STAT_AREA] >= min_area:
            out[labels == i] = True
    return out


def edge_mask(light: np.ndarray, mask: np.ndarray, sensitivity: float = 0.5) -> np.ndarray:
    mask = mask.astype(bool)
    mag = _grad_mag(light, mask)
    vals = mag[mask]
    vals = vals[vals > 0]
    if vals.size == 0:
        return np.zeros(mask.shape, bool)
    # sensitivity 0.5 -> ~p88; more sensitive -> lower percentile -> more edges
    pct = float(np.clip(94.0 - 12.0 * sensitivity, 82.0, 97.0))
    thr = np.percentile(vals, pct)
    strong = (mag >= thr) & mask
    return _despeckle(strong & _bright_side(light, mask))


def extreme_edge_mask(light: np.ndarray, mask: np.ndarray, sensitivity: float = 0.5) -> np.ndarray:
    base = edge_mask(light, mask, sensitivity)
    if not base.any():
        return np.zeros(mask.astype(bool).shape, bool)
    mag = _grad_mag(light, mask.astype(bool))
    thr = np.percentile(mag[base], 70.0)  # sharpest 30% of the main-edge pixels
    return base & (mag >= thr)


def geometric_edge_mask(normals: np.ndarray, mask: np.ndarray,
                        sensitivity: float = 0.5) -> np.ndarray:
    """Edge highlights from convex curvature of the normal field — light-independent.

    Same sensitivity->percentile mapping and despeckle as edge_mask; the only
    difference is the source (convex curvature magnitude, not light gradient). The
    convex-side filter (clip to >0) is the geometric analogue of _bright_side.
    """
    mask = mask.astype(bool)
    conv = np.clip(curvature(normals, mask), 0.0, None)   # convex ridges only
    conv[~mask] = 0.0
    vals = conv[mask]
    vals = vals[vals > 0]
    if vals.size == 0:
        return np.zeros(mask.shape, bool)
    pct = float(np.clip(94.0 - 12.0 * sensitivity, 82.0, 97.0))
    thr = np.percentile(vals, pct)
    strong = (conv >= thr) & mask
    return _despeckle(strong)


def geometric_extreme_edge_mask(normals: np.ndarray, mask: np.ndarray,
                                sensitivity: float = 0.5) -> np.ndarray:
    base = geometric_edge_mask(normals, mask, sensitivity)
    if not base.any():
        return np.zeros(mask.astype(bool).shape, bool)
    conv = np.clip(curvature(normals, mask.astype(bool)), 0.0, None)
    thr = np.percentile(conv[base], 70.0)   # sharpest 30% of the main-edge pixels
    return base & (conv >= thr)


def cavity_mask(normals: np.ndarray, mask: np.ndarray,
                sensitivity: float = 0.5) -> np.ndarray:
    """Recess shades from concave curvature of the normal field — light-independent.

    Concave twin of geometric_edge_mask: same sensitivity->percentile mapping and
    despeckle, sourced from the concave clip of curvature (creases/cavities) instead
    of the convex clip. Flat or convex-only normals -> empty mask (graceful, no
    manufactured shade). Thresholding concave curvature is thresholding ambient
    occlusion (AO = 1 - normalised concavity is monotonic), so this consumes the AO
    signal in its raw form.
    """
    mask = mask.astype(bool)
    conc = np.clip(-curvature(normals, mask), 0.0, None)   # concave creases only
    conc[~mask] = 0.0
    vals = conc[mask]
    vals = vals[vals > 0]
    if vals.size == 0:
        return np.zeros(mask.shape, bool)
    pct = float(np.clip(94.0 - 12.0 * sensitivity, 82.0, 97.0))
    thr = np.percentile(vals, pct)
    return _despeckle((conc >= thr) & mask)
