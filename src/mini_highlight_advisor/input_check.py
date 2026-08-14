from __future__ import annotations

from dataclasses import dataclass

import cv2
import numpy as np

# --- Shooting guide -------------------------------------------------------
SHOOTING_GUIDE = """\
### How to photograph your mini

- **Raking side light.** Light the mini from one side at roughly 45° so the sculpt
  casts soft shadows — that shading is exactly what the tool reads.
- **No on-axis / built-in flash.** A flash pointing straight at the mini flattens the
  form and erases the shading signal.
- **Fill the frame.** Get close (or crop) so the mini occupies most of the photo.
- **Plain, neutral background.** A clean backdrop helps isolate the mini.
- **Sharp focus, steady hands.** Focus on the mini and use a timer or brace your hands
  to avoid blur.
- **A zenithal-primed (grey/white) mini reads best** — it is already a shading map.
"""

# --- Tuning constants (raw grey 0-255 inside the mask) --------------------
FLAT_SPREAD_MAX = 60     # p95-p5 below this => lighting too flat to read form
CRUSH_VALUE = 4          # grey <= this counts as crushed-to-black
CRUSH_FRAC_MAX = 0.25    # >25% crushed => shadow detail lost
BLOWN_VALUE = 250        # grey >= this counts as blown-out
BLOWN_FRAC_MAX = 0.05    # >5% blown => highlight detail lost
MIN_FOCUS_VAR = 100.0    # variance of Laplacian below this => soft / out of focus
MIN_MASK_AREA = 40_000   # fewer masked px than this => too low-res for clean bands
MIN_COVERAGE = 0.15      # mini fills <15% of the frame => move closer / crop


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


def _check_exposure(gray: np.ndarray, mask: np.ndarray) -> CheckResult:
    inside = gray[mask]
    crushed = float(np.mean(inside <= CRUSH_VALUE))
    blown = float(np.mean(inside >= BLOWN_VALUE))
    crushed_bad = crushed > CRUSH_FRAC_MAX
    blown_bad = blown > BLOWN_FRAC_MAX
    ok = not (crushed_bad or blown_bad)
    parts = []
    if crushed_bad:
        parts.append(
            f"{crushed * 100:.0f}% of the mini is crushed to black — raise exposure "
            "or add a fill light; shadow detail is lost."
        )
    if blown_bad:
        parts.append(
            f"{blown * 100:.0f}% is blown out — lower exposure and diffuse the light."
        )
    detail = " ".join(parts) if parts else (
        "Exposure looks balanced — shadows and highlights both hold detail."
    )
    return CheckResult("exposure", "Exposure", ok, max(crushed, blown), detail)


def _check_focus(gray: np.ndarray, mask: np.ndarray) -> CheckResult:
    lap = cv2.Laplacian(gray, cv2.CV_64F)
    var = float(lap[mask].var())
    ok = var >= MIN_FOCUS_VAR
    if ok:
        detail = "Sharp."
    else:
        detail = (
            "Photo looks soft / out of focus — refocus on the mini and hold steady "
            "(use a timer or brace your hands)."
        )
    return CheckResult("focus", "Focus", ok, var, detail)


def _check_framing(mask: np.ndarray) -> CheckResult:
    area = int(mask.sum())
    coverage = float(mask.mean())
    ok = area >= MIN_MASK_AREA and coverage >= MIN_COVERAGE
    if ok:
        detail = f"Mini fills {coverage * 100:.0f}% of the frame."
    elif coverage < MIN_COVERAGE:
        detail = (
            f"The mini fills only {coverage * 100:.0f}% of the frame — move closer "
            "or crop so it fills most of the frame."
        )
    else:
        detail = "Photo resolution is low — use a larger image."
    return CheckResult("resolution", "Framing", ok, float(area), detail)


def check_input(rgb: np.ndarray, mask: np.ndarray) -> list[CheckResult]:
    if not mask.any():
        return [CheckResult(
            "input", "Photo", False, 0.0,
            "No mini detected in the photo — check the image or background removal.",
        )]
    gray = _to_gray(rgb)
    return [
        _check_lighting(gray, mask),
        _check_exposure(gray, mask),
        _check_focus(gray, mask),
        _check_framing(mask),
    ]
