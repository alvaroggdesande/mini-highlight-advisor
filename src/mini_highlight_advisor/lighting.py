from __future__ import annotations

from dataclasses import dataclass

import cv2
import numpy as np

# Raw CLAHE-gray p2..p98 range (0-255) a region needs before per-region stretching
# is trustworthy. Below this the region is dark/low-albedo with no relief dynamic
# range; stretching only amplifies sensor noise into fake bands, so the caller caps
# it to 1 band and warns. Starting value; tune against the synthetic fixtures.
FLAT_DYNRANGE_MIN = 25.0


def _clahe_gray(rgb: np.ndarray, clip_limit: float = 3.0) -> np.ndarray:
    gray = cv2.cvtColor(rgb, cv2.COLOR_RGB2GRAY)
    clahe = cv2.createCLAHE(clipLimit=clip_limit, tileGridSize=(8, 8))
    return clahe.apply(gray).astype(np.float32)


def _stretch(gray: np.ndarray, mask: np.ndarray) -> np.ndarray:
    inside = gray[mask]
    if inside.size == 0:
        return np.zeros(gray.shape, dtype=np.float32)
    lo, hi = np.percentile(inside, 2), np.percentile(inside, 98)
    light = np.clip((gray - lo) / (hi - lo + 1e-9), 0.0, 1.0).astype(np.float32)
    light[~mask] = 0.0
    return light


def luminance_light(rgb: np.ndarray, mask: np.ndarray, clip_limit: float = 3.0) -> np.ndarray:
    return _stretch(_clahe_gray(rgb, clip_limit), mask)


@dataclass
class LocalLight:
    light: np.ndarray   # region stretched to its own [0,1]; off-(sub)mask = 0
    dyn_range: float    # p98 - p2 of the region's raw CLAHE gray, 0..255 (pre-stretch)
    flat: bool          # dyn_range < FLAT_DYNRANGE_MIN


def local_luminance_light(gray: np.ndarray, sub_mask: np.ndarray) -> LocalLight:
    """Per-region light + relief signal. ``gray`` is a shared ``_clahe_gray`` output."""
    inside = gray[sub_mask]
    if inside.size == 0:
        return LocalLight(np.zeros(gray.shape, dtype=np.float32), 0.0, True)
    lo, hi = np.percentile(inside, [2, 98])
    dyn = float(hi - lo)
    return LocalLight(_stretch(gray, sub_mask), dyn, dyn < FLAT_DYNRANGE_MIN)
