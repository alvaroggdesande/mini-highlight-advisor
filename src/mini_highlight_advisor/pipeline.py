from __future__ import annotations

from dataclasses import dataclass

import numpy as np
from PIL import Image

from .banding import band_light
from .lighting import luminance_light
from .masking import compute_mask
from .overlay import (
    BandStep, compose_panel, paint_preview, paint_regions, per_band_images, render_legend,
)
from .palette import PaintColor, coverage_pct, default_coverage, role_names
from .regions import Region, assign_owners


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


@dataclass
class ShadingResult:
    mask: np.ndarray
    light: np.ndarray


def prepare_shading(rgb: np.ndarray, alpha: np.ndarray | None) -> ShadingResult:
    mask = compute_mask(rgb, alpha)
    light = luminance_light(rgb, mask)
    return ShadingResult(mask, light)


def band_and_render(
    rgb: np.ndarray,
    mask: np.ndarray,
    light: np.ndarray,
    palette: list[PaintColor],
    coverage: list[float],
) -> HighlightResult:
    n = len(palette)
    colors = [p.rgb for p in palette]
    names = [p.name for p in palette]
    roles = role_names(n)

    bands = band_light(light, mask, coverage)
    cov = coverage_pct(bands, mask, n)

    preview_rgb = paint_preview(rgb, bands, mask, colors)
    legend = render_legend(colors, names, roles, cov, height=preview_rgb.shape[0])
    panel = compose_panel(rgb, preview_rgb, legend)
    steps = per_band_images(rgb, bands, mask, colors)

    return HighlightResult(mask, light, bands, cov, roles, preview_rgb, panel, steps)


def analyze(
    rgb: np.ndarray,
    alpha: np.ndarray | None,
    palette: list[PaintColor],
    coverage: list[float] | None = None,
) -> HighlightResult:
    if coverage is None:
        coverage = default_coverage(len(palette))
    shading = prepare_shading(rgb, alpha)
    return band_and_render(rgb, shading.mask, shading.light, palette, coverage)


@dataclass
class RegionPlan:
    name: str
    sub_mask: np.ndarray
    bands: np.ndarray
    colors: list[np.ndarray]
    names: list[str]
    roles: list[str]
    coverage: list[float]
    steps: list[BandStep]


@dataclass
class MultiRegionResult:
    mask: np.ndarray
    light: np.ndarray
    plans: list[RegionPlan]
    combined_rgb: np.ndarray


def plan_region(rgb, sub_mask, light, name, palette, coverage) -> RegionPlan:
    colors = [p.rgb for p in palette]
    names = [p.name for p in palette]
    roles = role_names(len(palette))
    bands = band_light(light, sub_mask, coverage)
    cov = coverage_pct(bands, sub_mask, len(palette))
    steps = per_band_images(rgb, bands, sub_mask, colors)
    return RegionPlan(name, sub_mask, bands, colors, names, roles, cov, steps)


def analyze_regions(rgb, alpha, default_palette, coverage=None, regions=None) -> MultiRegionResult:
    regions = regions or []
    if coverage is None:
        coverage = default_coverage(len(default_palette))
    shading = prepare_shading(rgb, alpha)
    mask, light = shading.mask, shading.light
    owner = assign_owners(mask, [r.mask for r in regions])
    plans: list[RegionPlan] = []
    default_sub = owner == -1
    if default_sub.any():
        plans.append(plan_region(rgb, default_sub, light, "Default", default_palette, coverage))
    for i, r in enumerate(regions):
        sub = owner == i
        if not sub.any():
            continue
        plans.append(plan_region(rgb, sub, light, r.name, r.palette, r.coverage))
    combined = paint_regions(rgb, plans)
    return MultiRegionResult(mask, light, plans, combined)
