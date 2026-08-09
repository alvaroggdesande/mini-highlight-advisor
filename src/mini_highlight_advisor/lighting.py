from __future__ import annotations

import cv2
import numpy as np


def luminance_light(rgb: np.ndarray, mask: np.ndarray, clip_limit: float = 3.0) -> np.ndarray:
    gray = cv2.cvtColor(rgb, cv2.COLOR_RGB2GRAY)
    clahe = cv2.createCLAHE(clipLimit=clip_limit, tileGridSize=(8, 8))
    gray = clahe.apply(gray).astype(np.float32)
    inside = gray[mask]
    if inside.size == 0:
        return np.zeros(gray.shape, dtype=np.float32)
    lo, hi = np.percentile(inside, 2), np.percentile(inside, 98)
    light = np.clip((gray - lo) / (hi - lo + 1e-9), 0.0, 1.0).astype(np.float32)
    light[~mask] = 0.0
    return light
