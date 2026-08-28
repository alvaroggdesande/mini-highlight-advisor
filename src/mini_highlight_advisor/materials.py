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


def nmm_light(normals: np.ndarray, mask: np.ndarray,
              view=(0.0, 0.0, 1.0), horizon: float = 0.5,
              softness: float = 0.15) -> np.ndarray:
    """Reflection-environment brightness for NMM, in [0,1]; off-mask 0.

    view: reflection view direction (default +Z, toward viewer). horizon in
    [0,1] slides the sky/ground split in R_y space: 0 = horizon at the bottom
    (all sky, bright), 1 = horizon at the top (all ground, dark), 0.5 = split at
    the equator. softness sets the transition half-width (the hard NMM line).
    """
    m = mask.astype(bool)
    r = reflect(np.asarray(view, np.float32), normals)   # reflect() validates normals
    ry = r[..., 1]                                        # y-up component
    thr = 2.0 * float(horizon) - 1.0                     # horizon height -> R_y threshold
    light = _smoothstep(thr - softness, thr + softness, ry).astype(np.float32)
    light[~m] = 0.0
    return light
