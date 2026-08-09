from __future__ import annotations

from dataclasses import dataclass

import numpy as np
from PIL import Image

from .banding import band_light
from .lighting import luminance_light
from .masking import compute_mask
from .overlay import BandStep, compose_panel, paint_preview, per_band_images, render_legend
from .palette import PaintColor, coverage_pct, default_coverage, role_names


@dataclass
class HighlightResult:
    mask: np.ndarray
    light: np.ndarray
    bands: np.ndarray
    coverage: list[float]
    roles: list[str]
    preview_rgb: np.ndarray
    panel: Image.Image
    steps: list[BandStep]


def analyze(rgb: np.ndarray, alpha: np.ndarray | None, palette: list[PaintColor]) -> HighlightResult:
    n = len(palette)
    colors = [p.rgb for p in palette]
    names = [p.name for p in palette]
    roles = role_names(n)

    mask = compute_mask(rgb, alpha)
    light = luminance_light(rgb, mask)
    bands = band_light(light, mask, default_coverage(n))
    coverage = coverage_pct(bands, mask, n)

    preview_rgb = paint_preview(rgb, bands, mask, colors)
    legend = render_legend(colors, names, roles, coverage, height=preview_rgb.shape[0])
    panel = compose_panel(rgb, preview_rgb, legend)

    steps = per_band_images(rgb, bands, mask, colors)

    return HighlightResult(mask, light, bands, coverage, roles, preview_rgb, panel, steps)
