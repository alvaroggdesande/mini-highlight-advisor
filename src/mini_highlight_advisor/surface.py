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
