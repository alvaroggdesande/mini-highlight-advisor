from __future__ import annotations

from dataclasses import dataclass

import numpy as np
from PIL import Image

from .banding import band_light, relief_recommended_bands
from .lighting import luminance_light
from .masking import compute_mask
from .edges import edge_mask, extreme_edge_mask
from .overlay import (
    BandStep, compose_panel, edge_steps, paint_preview, paint_regions, per_band_images, render_legend,
)
from .palette import PaintColor, coverage_pct, default_coverage, role_names
from .regions import Region, assign_owners

WHOLE_MINI = "Whole mini"


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
    edges: bool = True,
    extreme_edge: bool = False,
    edge_sensitivity: float = 0.5,
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
    if edges:
        steps = steps + edge_steps(rgb, light, mask, colors,
                                   sensitivity=edge_sensitivity,
                                   extreme=extreme_edge, start_index=n)

    return HighlightResult(mask, light, bands, cov, roles, preview_rgb, panel, steps)


def analyze(
    rgb: np.ndarray,
    alpha: np.ndarray | None,
    palette: list[PaintColor],
    coverage: list[float] | None = None,
    edges: bool = True,
    extreme_edge: bool = False,
    edge_sensitivity: float = 0.5,
) -> HighlightResult:
    if coverage is None:
        coverage = default_coverage(len(palette))
    shading = prepare_shading(rgb, alpha)
    return band_and_render(rgb, shading.mask, shading.light, palette, coverage,
                           edges=edges, extreme_edge=extreme_edge,
                           edge_sensitivity=edge_sensitivity)


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
    edge_overlays: list | None = None
    capped: bool = False
    requested_bands: int | None = None


@dataclass
class MultiRegionResult:
    mask: np.ndarray
    light: np.ndarray
    plans: list[RegionPlan]
    combined_rgb: np.ndarray


def plan_region(rgb, sub_mask, light, name, palette, coverage,
                edges: bool = True, extreme_edge: bool = False,
                edge_sensitivity: float = 0.5,
                relief_cap: bool = False) -> RegionPlan:
    requested_bands = len(palette)
    capped = False
    if relief_cap:
        k = relief_recommended_bands(light, sub_mask, requested_bands)
        if k < requested_bands:
            # Keep the darkest k paints (base + lower highlights); a flat region
            # can't show the brightest highlights. Render-only — the caller's
            # stored palette/coverage are untouched.
            capped = True
            palette = palette[:k]
            coverage = default_coverage(k)
    colors = [p.rgb for p in palette]
    names = [p.name for p in palette]
    roles = role_names(len(palette))
    bands = band_light(light, sub_mask, coverage)
    cov = coverage_pct(bands, sub_mask, len(palette))
    steps = per_band_images(rgb, bands, sub_mask, colors)
    overlays = None
    if edges:
        steps = steps + edge_steps(rgb, light, sub_mask, colors,
                                   sensitivity=edge_sensitivity,
                                   extreme=extreme_edge, start_index=len(palette))
        two_tier = extreme_edge and len(colors) >= 5  # match edge_steps guard
        overlays = [(edge_mask(light, sub_mask, edge_sensitivity),
                     colors[-2] if two_tier else colors[-1])]
        if two_tier:
            overlays.append((extreme_edge_mask(light, sub_mask, edge_sensitivity), colors[-1]))
    return RegionPlan(name, sub_mask, bands, colors, names, roles, cov, steps, overlays,
                      capped=capped, requested_bands=requested_bands)


def analyze_regions(rgb, alpha, default_palette, coverage=None, regions=None,
                    edges: bool = True, extreme_edge: bool = False,
                    edge_sensitivity: float = 0.5,
                    relief_cap: bool = False) -> MultiRegionResult:
    regions = regions or []
    if coverage is None:
        coverage = default_coverage(len(default_palette))
    shading = prepare_shading(rgb, alpha)
    mask, light = shading.mask, shading.light
    owner = assign_owners(mask, [r.mask for r in regions])
    plans: list[RegionPlan] = []
    default_sub = owner == -1
    ekw = dict(edges=edges, extreme_edge=extreme_edge, edge_sensitivity=edge_sensitivity,
               relief_cap=relief_cap)
    if default_sub.any():
        plans.append(plan_region(rgb, default_sub, light, WHOLE_MINI, default_palette, coverage, **ekw))
    for i, r in enumerate(regions):
        sub = owner == i
        if not sub.any():
            continue
        plans.append(plan_region(rgb, sub, light, r.name, r.palette, r.coverage, **ekw))
    combined = paint_regions(rgb, plans)
    return MultiRegionResult(mask, light, plans, combined)
