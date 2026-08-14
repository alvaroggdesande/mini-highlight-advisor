from __future__ import annotations

from dataclasses import dataclass

import cv2
import numpy as np

# --- Tuning constants (raw grey 0-255 inside the mask) --------------------
FLAT_SPREAD_MAX = 60  # p95-p5 below this => lighting too flat to read form


@dataclass
class CheckResult:
    id: str        # "lighting" | "exposure" | "focus" | "resolution"
    label: str     # human label shown in the panel
    ok: bool
    value: float   # measured number, surfaced to the user
    detail: str    # observation + concrete fix; never a bare verdict


def _to_gray(rgb: np.ndarray) -> np.ndarray:
    return cv2.cvtColor(rgb, cv2.COLOR_RGB2GRAY)


def _check_lighting(gray: np.ndarray, mask: np.ndarray) -> CheckResult:
    inside = gray[mask]
    p5, p95 = np.percentile(inside, [5, 95])
    spread = float(p95 - p5)
    ok = spread >= FLAT_SPREAD_MAX
    if ok:
        detail = "Good tonal range across the mini."
    else:
        detail = (
            f"Lighting is flat (spread {spread:.0f}/255) — light the mini with a "
            "single raking light from one side (~45°) and turn off any on-axis / "
            "built-in flash."
        )
    return CheckResult("lighting", "Lighting", ok, spread, detail)


def check_input(rgb: np.ndarray, mask: np.ndarray) -> list[CheckResult]:
    if not mask.any():
        return [CheckResult(
            "input", "Photo", False, 0.0,
            "No mini detected in the photo — check the image or background removal.",
        )]
    gray = _to_gray(rgb)
    return [
        _check_lighting(gray, mask),
    ]
