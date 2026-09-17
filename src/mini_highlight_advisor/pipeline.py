from __future__ import annotations

from dataclasses import dataclass

import numpy as np
from PIL import Image

from .banding import band_light, band_by_value, relief_recommended_bands
from .lighting import luminance_light, _clahe_gray, local_luminance_light
from .masking import compute_mask
from .edges import (
    edge_mask, extreme_edge_mask, geometric_edge_mask, geometric_extreme_edge_mask,
    cavity_mask,
)
from .overlay import (
    BandStep, compose_panel, edge_steps, osl_preview, paint_preview, paint_regions,
    per_band_images, render_legend, shade_steps,
)
from .palette import PaintColor, coverage_pct, default_coverage, role_names
from .regions import Region, assign_owners
from .techniques import get_technique
from . import materials, osl, matching

WHOLE_MINI = "Whole mini"
_SHADE_DARKEN = 0.55   # recess shade = darkest palette paint glazed this much darker


@dataclass
class OslSource:
    x: float
    y: float
    height: float
    glow_rgb: np.ndarray   # float32 (3,) 0-255
    hot_rgb: np.ndarray    # float32 (3,) 0-255


@dataclass
class OslResult:
    glow: np.ndarray            # (H,W) float32
    preview_rgb: np.ndarray     # (H,W,3) uint8
    steps: list[BandStep]


def _rgb_to_hex(rgb: np.ndarray) -> str:
    r, g, b = (int(np.clip(v, 0, 255)) for v in rgb)
    return f"#{r:02x}{g:02x}{b:02x}"


def osl_step_caption(index: int, n_steps: int, paint_name: str | None) -> str:
    """Glazing guidance for one OSL glow layer.

    Glow bands are strictly nested broad -> tight: index 0 is the broadest,
    faintest glaze; the final index is the hotspot; anything between tightens.
    """
    paint = paint_name or "the glow colour"
    if index == 0:
        return (f"Thin glaze of **{paint}** over every surface facing the light — "
                f"keep it broad and faint, build it up in several watery passes.")
    if index == n_steps - 1:
        return (f"Hotspot — near-pure **{paint}** on the single point nearest the "
                f"source. Leave surfaces turned away from the light dark.")
    return (f"Tighten **{paint}** onto the surfaces closest and most face-on to the "
            f"source; a little less thinned than the broad glaze.")


def apply_osl(base_preview_rgb: np.ndarray, normals: np.ndarray, mask: np.ndarray,
              source: OslSource, reach: float, intensity: float,
              coverage: list[float], owned=None, catalog=None) -> OslResult:
    """Compute the OSL glow, a screen-composited preview, and nested glow steps.
    Leaves base_preview_rgb unmodified; returns steps with kind='osl' and, when a
    catalog is provided, label = the nearest named paint."""
    glow = osl.osl_field(normals, mask, source.x, source.y, source.height, reach, intensity)
    contribution = osl.osl_ramp(glow, source.glow_rgb, source.hot_rgb)
    preview = osl_preview(base_preview_rgb, contribution)
    bands = osl.osl_bands(glow, mask, coverage)
    colors = osl.osl_colors(source.glow_rgb, source.hot_rgb, len(coverage))
    steps = per_band_images(base_preview_rgb, bands, mask, colors)
    for s, color in zip(steps, colors):
        s.kind = "osl"
        if catalog:
            m = matching.match(matching.target_from_hex(_rgb_to_hex(color)),
                               owned or [], catalog)
            s.label = getattr(m, "name", None) or getattr(m, "phrase", None)
    return OslResult(glow=glow, preview_rgb=preview, steps=steps)


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
                material: str = "matte",
                env: np.ndarray | None = None,
                nmm_smooth: float = 0.0,
                technique: str = "smooth") -> RegionPlan:
    is_nmm = material == "nmm" and normals is not None and env is not None
    if is_nmm:
        # Metal is a mirror: re-band from the reflection environment, not the
        # caught/relit light. Geometry places the NMM horizon. normals/env absent
        # -> silently stay matte (defense in depth).
        # Denoise the normals first: the reflection lookup amplifies normal noise
        # into gold speckle, so smooth before sampling (nmm_smooth in pixels).
        nrm = materials.smooth_normals(normals, sub_mask, nmm_smooth)
        light = materials.nmm_light(nrm, sub_mask, env=env)
        # Resample palette to the requested band count (Metal steps UI knob).
        # Keep BOTH endpoints (darkest shadow + lightest glint) so the full
        # dark→light ramp is represented. No-op when k == len(palette).
        k = len(coverage)
        if k < len(palette):
            idx = np.linspace(0, len(palette) - 1, k).round().astype(int)
            palette = [palette[i] for i in idx]
    requested_bands = len(palette)
    capped = False
    if not is_nmm:
        if flat_albedo:
            # Dark/low-dynamic-range region: no relief signal. Keep the base only.
            capped = True
            palette = palette[:1]
            coverage = default_coverage(1)
        elif relief_cap:
            k = relief_recommended_bands(light, sub_mask, requested_bands)
            if k < requested_bands:
                capped = True
                palette = palette[:k]
                coverage = default_coverage(k)
    colors = [p.rgb for p in palette]
    names = [p.name for p in palette]
    spec = get_technique(technique)
    roles = spec.role_names(len(palette))
    if is_nmm:
        # Value-anchored banding: flat sky -> one paint, thin horizon keeps its band.
        # The relief/flat cap is bypassed above — the env injects deliberate contrast.
        bands = band_by_value(light, sub_mask, n_bands=len(coverage))
    else:
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
                    nmm_light_dir: float = 135.0,
                    nmm_bounce: float = 0.35,
                    nmm_hotspot: float = 0.5,
                    nmm_smooth: float = 2.0,
                    whole_material: str = "matte",
                    whole_blank: bool = False,
                    shading: "ShadingResult | None" = None) -> MultiRegionResult:
    # `shading` lets callers pass an already-computed mask+light so the (often
    # expensive, e.g. GrabCut) mask computation runs once per photo instead of on
    # every call. When None we compute it here as before.
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
        mask = shading.mask if shading is not None else compute_mask(rgb, alpha)
        light = light_field
        per_region_norm = False
    else:
        if shading is None:
            shading = prepare_shading(rgb, alpha)
        mask, light = shading.mask, shading.light
    owner = assign_owners(mask, [r.mask for r in regions])
    plans: list[RegionPlan] = []
    default_sub = owner == -1
    env = materials.build_nmm_env(horizon=nmm_horizon, light_dir=nmm_light_dir,
                                  bounce=nmm_bounce, hotspot=nmm_hotspot)
    ekw = dict(edges=edges, extreme_edge=extreme_edge, edge_sensitivity=edge_sensitivity,
               relief_cap=relief_cap, normals=normal_field, shades=shades, env=env,
               nmm_smooth=nmm_smooth)

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
