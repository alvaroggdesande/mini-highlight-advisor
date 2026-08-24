"""Pure, torch-free surface geometry derived from a normal field.

Consumes the SAME pinned convention as relight.py (R=x-right, G=y-up,
B=z-toward-viewer) and the SAME already-normalized field — no flip toggle.
numpy in, numpy out; no Streamlit, no torch. Named surface.py (not geometry.py)
because ui/geometry.py already owns unrelated 2D lasso path math.
"""
from __future__ import annotations

import cv2
import numpy as np


def _validate(normals: np.ndarray) -> np.ndarray:
    """Shape-check (H,W,3) and defensively renormalize to unit (mirrors relight)."""
    n = np.asarray(normals, dtype=np.float32)
    if n.ndim != 3 or n.shape[2] != 3:
        raise ValueError(f"normals must be (H,W,3), got {n.shape}")
    norm = np.linalg.norm(n, axis=-1, keepdims=True)
    norm[norm == 0] = 1.0
    return (n / norm).astype(np.float32)


def curvature(normals: np.ndarray, mask: np.ndarray) -> np.ndarray:
    """Signed mean curvature = divergence of the in-plane normal field.

    >0 convex/outward ridge, <0 concave crease, 0 off-mask. Image rows grow
    downward but the convention is y-UP, so d/dy = -d/drow and the divergence is
    d(nx)/dcol - d(ny)/drow. Gaussian pre-blur calms primer grain (same rationale
    as edges._grad_mag). Off-mask components are zeroed so the field contributes
    nothing there.

    Note: off-mask in-plane components are zeroed before differentiation, so pixels
    on the mask boundary (the silhouette) differentiate against artificial zeros and
    can show inflated curvature there. Interior curvature is reliable; treat a
    rim-following response near the silhouette as a boundary artefact, not a true ridge.
    """
    n = _validate(normals)
    m = mask.astype(bool)
    nx = np.where(m, n[..., 0], 0.0).astype(np.float32)
    ny = np.where(m, n[..., 1], 0.0).astype(np.float32)
    nx = cv2.GaussianBlur(nx, (3, 3), 0)
    ny = cv2.GaussianBlur(ny, (3, 3), 0)
    dnx_dcol = cv2.Sobel(nx, cv2.CV_32F, 1, 0, ksize=3)
    dny_drow = cv2.Sobel(ny, cv2.CV_32F, 0, 1, ksize=3)
    curv = dnx_dcol - dny_drow            # convex/outward > 0
    curv[~m] = 0.0
    return curv.astype(np.float32)


def ambient_occlusion(normals: np.ndarray, mask: np.ndarray) -> np.ndarray:
    """Cavity-style AO from concavity: 1 = exposed (convex/flat), ->0 = deep recess.

    Concavity is the negative part of curvature, self-scaled by its 95th percentile
    inside the mask so the map is comparable across minis. Off-mask 0. (Foundation
    primitive — built and tested here, consumed by the later cavity/AO slice.)
    """
    m = mask.astype(bool)
    conc = np.clip(-curvature(normals, m), 0.0, None)
    vals = conc[m]
    scale = float(np.percentile(vals, 95)) if vals.size and vals.max() > 0 else 1.0
    ao = 1.0 - np.clip(conc / (scale + 1e-6), 0.0, 1.0)
    ao[~m] = 0.0
    return ao.astype(np.float32)


def reflect(view: np.ndarray, normals: np.ndarray) -> np.ndarray:
    """Reflection vectors R = 2(N.V)N - V, per pixel.

    `view` is a (3,) direction (broadcast) or a full (H,W,3) field; output is
    unit-length where inputs are. (Foundation primitive for the later specular/NMM
    slice.)
    """
    n = _validate(normals)
    v = np.asarray(view, np.float32)
    v = v / (np.linalg.norm(v, axis=-1, keepdims=True) + 1e-12)
    ndotv = np.sum(n * v, axis=-1, keepdims=True)
    return (2.0 * ndotv * n - v).astype(np.float32)
