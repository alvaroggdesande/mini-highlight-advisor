from __future__ import annotations

from dataclasses import dataclass

import numpy as np
from PIL import Image

from .banding import band_light, relief_recommended_bands
from .lighting import luminance_light, _clahe_gray, local_luminance_light
from .masking import compute_mask
from .edges import (
    edge_mask, extreme_edge_mask, geometric_edge_mask, geometric_extreme_edge_mask,
    cavity_mask,
)
from .overlay import (
    BandStep, compose_panel, edge_steps, paint_preview, paint_regions,
    per_band_images, render_legend, shade_steps,
)
from .palette import PaintColor, coverage_pct, default_coverage, role_names
from .regions import Region, assign_owners
from .techniques import get_technique
from . import materials

WHOLE_MINI = "Whole mini"
_SHADE_DARKEN = 0.55   # recess shade = darkest palette paint glazed this much darker


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
    flat_albedo: bool = False
    technique: str = "smooth"          # technique name (resolved via alias)


@dataclass
class MultiRegionResult:
    mask: np.ndarray
    light: np.ndarray
    plans: list[RegionPlan]
    combined_rgb: np.ndarray


def plan_region(rgb, sub_mask, light, name, palette, coverage,
                edges: bool = True, extreme_edge: bool = False,
                edge_sensitivity: float = 0.5,
                relief_cap: bool = False, flat_albedo: bool = False,
                normals: np.ndarray | None = None,
                shades: bool = False,
                material: str = "matte", nmm_horizon: float = 0.5,
                technique: str = "smooth") -> RegionPlan:
    if material == "nmm" and normals is not None:
        # Metal is a mirror: re-band from the reflection environment, not the
        # caught/relit light. Geometry (not the virtual light) places the NMM
        # horizon. normals absent -> silently stay matte (defense in depth).
        light = materials.nmm_light(normals, sub_mask, horizon=nmm_horizon)
    requested_bands = len(palette)
    capped = False
    if flat_albedo:
        # Dark/low-dynamic-range region: no relief signal to band. Keep the base only.
        capped = True
        palette = palette[:1]
        coverage = default_coverage(1)
    elif relief_cap:
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
    spec = get_technique(technique)
    roles = spec.role_names(len(palette))
    bands = band_light(light, sub_mask, coverage)
    cov = coverage_pct(bands, sub_mask, len(palette))
    steps = per_band_images(rgb, bands, sub_mask, colors)
    overlays = None
    if edges:
        steps = steps + edge_steps(rgb, light, sub_mask, colors,
                                   sensitivity=edge_sensitivity,
                                   extreme=extreme_edge, start_index=len(palette))
        two_tier = extreme_edge and len(colors) >= 5  # match edge_steps guard
        if normals is not None:
            main = geometric_edge_mask(normals, sub_mask, edge_sensitivity)
        else:
            main = edge_mask(light, sub_mask, edge_sensitivity)
        overlays = [(main, colors[-2] if two_tier else colors[-1])]
        if two_tier:
            if normals is not None:
                ext = geometric_extreme_edge_mask(normals, sub_mask, edge_sensitivity)
            else:
                ext = extreme_edge_mask(light, sub_mask, edge_sensitivity)
            overlays.append((ext, colors[-1]))
    if shades and normals is not None:
        recess = cavity_mask(normals, sub_mask, edge_sensitivity)
        shade_rgb = (colors[0] * _SHADE_DARKEN).astype(np.float32)
        overlays = [(recess, shade_rgb)] + (overlays or [])   # shade under any edges
        steps = steps + shade_steps(rgb, recess, shade_rgb, start_index=len(steps))
    return RegionPlan(name, sub_mask, bands, colors, names, roles, cov, steps, overlays,
                      capped=capped, requested_bands=requested_bands,
                      flat_albedo=flat_albedo, technique=spec.name)


def analyze_regions(rgb, alpha, default_palette, coverage=None, regions=None,
                    edges: bool = True, extreme_edge: bool = False,
                    edge_sensitivity: float = 0.5,
                    relief_cap: bool = False,
                    per_region_norm: bool = False,
                    light_field: np.ndarray | None = None,
                    normal_field: np.ndarray | None = None,
                    shades: bool = False,
                    nmm_horizon: float = 0.5,
                    whole_material: str = "matte",
                    whole_blank: bool = False) -> MultiRegionResult:
    regions = regions or []
    if normal_field is not None:
        if (normal_field.ndim != 3 or normal_field.shape[2] != 3
                or normal_field.shape[:2] != rgb.shape[:2]):
            raise ValueError(
                f"normal_field {getattr(normal_field, 'shape', None)} must be "
                f"(H,W,3) matching rgb {rgb.shape[:2]}")
    if coverage is None:
        coverage = default_coverage(len(default_palette))
    if light_field is not None:
        # PS mode: mask from the provided (authoritative) alpha; light = injected
        # field. The field is global, so per-region luminance norm is bypassed.
        mask = compute_mask(rgb, alpha)
        light = light_field
        per_region_norm = False
    else:
        shading = prepare_shading(rgb, alpha)
        mask, light = shading.mask, shading.light
    owner = assign_owners(mask, [r.mask for r in regions])
    plans: list[RegionPlan] = []
    default_sub = owner == -1
    ekw = dict(edges=edges, extreme_edge=extreme_edge, edge_sensitivity=edge_sensitivity,
               relief_cap=relief_cap, normals=normal_field, shades=shades,
               nmm_horizon=nmm_horizon)

    gray = _clahe_gray(rgb) if per_region_norm else None

    def _region_light(sub):
        if per_region_norm:
            ll = local_luminance_light(gray, sub)
            return ll.light, ll.flat
        return light, False

    if default_sub.any() and not whole_blank:
        lgt, flat = _region_light(default_sub)
        plans.append(plan_region(rgb, default_sub, lgt, WHOLE_MINI, default_palette,
                                 coverage, flat_albedo=flat,
                                 material=whole_material, technique=whole_material, **ekw))
    for i, r in enumerate(regions):
        sub = owner == i
        if not sub.any():
            continue
        lgt, flat = _region_light(sub)
        plans.append(plan_region(rgb, sub, lgt, r.name, r.palette, r.coverage,
                                 flat_albedo=flat, material=r.material,
                                 technique=r.material, **ekw))
    combined = paint_regions(rgb, plans)
    return MultiRegionResult(mask, light, plans, combined)
