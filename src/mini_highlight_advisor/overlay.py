from __future__ import annotations

import os
from dataclasses import dataclass

import numpy as np
from PIL import Image, ImageDraw, ImageFont

from .edges import edge_mask, extreme_edge_mask

_COVERAGE_NOTES = {
    "Shadow": "deepest recesses",
    "Base": "the main body of the surface",
    "Midtone": "flat, gently-lit panels",
    "Highlight": "raised areas facing the light",
    "Bright Highlight": "the brightest broad zones",
    "Edge Highlight": "the crisp lit rim of every plate",
    "Extreme Edge Highlight": "sharpest edges only, the final pop",
}

_DIM = 0.25
_STEP_DIM = 0.4
_ACCENT = np.array([255, 40, 200], np.float32)
_LUMA = np.array([0.299, 0.587, 0.114], np.float32)


@dataclass
class BandStep:
    index: int
    zone_rgb: np.ndarray
    cumulative_rgb: np.ndarray
    exact_rgb: np.ndarray | None
    is_last: bool
    kind: str = "band"
    label: str | None = None


def _desat_dim(rgb) -> np.ndarray:
    lum = rgb.astype(np.float32) @ _LUMA
    grey = np.stack([lum, lum, lum], axis=-1)
    return grey * _STEP_DIM


def _render_step(rgb, active_mask, color, alpha) -> np.ndarray:
    base = rgb.astype(np.float32)
    out = _desat_dim(rgb)
    out[active_mask] = (1 - alpha) * base[active_mask] + alpha * color
    return np.clip(out, 0, 255).astype(np.uint8)


def _zone_render(rgb, active_mask, accent=_ACCENT, alpha: float = 0.85) -> np.ndarray:
    base = rgb.astype(np.float32)
    out = _desat_dim(rgb)
    out[active_mask] = (1 - alpha) * base[active_mask] + alpha * accent
    return np.clip(out, 0, 255).astype(np.uint8)


def per_band_images(rgb, bands, mask, colors, alpha: float = 0.78) -> list[BandStep]:
    n = len(colors)
    steps: list[BandStep] = []
    for k, color in enumerate(colors):
        is_last = k == n - 1
        active = (bands >= k) & mask
        zone = _zone_render(rgb, active)
        cumulative = _render_step(rgb, active, color, alpha)
        exact = None if is_last else _render_step(rgb, (bands == k) & mask, color, alpha)
        steps.append(BandStep(index=k, zone_rgb=zone, cumulative_rgb=cumulative,
                              exact_rgb=exact, is_last=is_last))
    return steps


def edge_steps(rgb, light, mask, colors, sensitivity: float = 0.5,
               extreme: bool = False, alpha: float = 0.78,
               start_index: int = 0) -> list[BandStep]:
    n = len(colors)
    two_tier = extreme and n >= 5  # n>=5 => top two bands are both highlight-tier
    main_color = colors[-2] if two_tier else colors[-1]
    main = edge_mask(light, mask, sensitivity)
    steps = [BandStep(
        index=start_index,
        zone_rgb=_zone_render(rgb, main),
        cumulative_rgb=_render_step(rgb, main, main_color, alpha),
        exact_rgb=_render_step(rgb, main, main_color, alpha),
        is_last=not two_tier, kind="edge", label="Edge Highlight",
    )]
    if two_tier:
        ext = extreme_edge_mask(light, mask, sensitivity)
        steps.append(BandStep(
            index=start_index + 1,
            zone_rgb=_zone_render(rgb, ext),
            cumulative_rgb=_render_step(rgb, ext, colors[-1], alpha),
            exact_rgb=_render_step(rgb, ext, colors[-1], alpha),
            is_last=True, kind="edge", label="Extreme Edge Highlight",
        ))
    return steps


def paint_preview(rgb, bands, mask, colors, alpha: float = 0.78, edge_overlays=None) -> np.ndarray:
    base = rgb.astype(np.float32)
    out = base.copy()
    out[~mask] = out[~mask] * _DIM
    for b, color in enumerate(colors):
        m = (bands == b) & mask
        out[m] = (1 - alpha) * base[m] + alpha * color
    for emask, color in (edge_overlays or []):
        out[emask] = (1 - alpha) * base[emask] + alpha * color
    return np.clip(out, 0, 255).astype(np.uint8)


def paint_regions(rgb, plans, alpha: float = 0.78) -> np.ndarray:
    base = rgb.astype(np.float32)
    out = base.copy()
    union = np.zeros(rgb.shape[:2], bool)
    for p in plans:
        union |= p.sub_mask
    out[~union] = out[~union] * _DIM
    for p in plans:
        for b, color in enumerate(p.colors):
            m = (p.bands == b) & p.sub_mask
            out[m] = (1 - alpha) * base[m] + alpha * color
    for p in plans:
        for emask, color in (getattr(p, 'edge_overlays', None) or []):
            m = emask & p.sub_mask
            out[m] = (1 - alpha) * base[m] + alpha * color
    return np.clip(out, 0, 255).astype(np.uint8)


def _font(size: int):
    for path in (r"C:\Windows\Fonts\segoeui.ttf", r"C:\Windows\Fonts\arial.ttf"):
        if os.path.exists(path):
            return ImageFont.truetype(path, size)
    return ImageFont.load_default()


def render_legend(colors, names, roles, coverage, height: int, width: int = 430) -> Image.Image:
    img = Image.new("RGB", (width, height), (26, 27, 32))
    d = ImageDraw.Draw(img)
    title_f, role_f, body_f, small_f = _font(26), _font(21), _font(18), _font(15)
    d.text((20, 18), "Highlight plan", font=title_f, fill=(240, 240, 245))
    d.text((20, 52), "dark to light  (paint in this order)", font=small_f, fill=(150, 152, 160))
    n = len(colors)
    top, sw = 92, 54
    row_h = min(96, (height - top - 16) // max(n, 1))
    for i in range(n):
        y = top + i * row_h
        rgb = tuple(int(v) for v in colors[i])
        d.rectangle([20, y, 20 + sw, y + sw], fill=rgb, outline=(70, 72, 80), width=2)
        d.text((20, y + sw + 2), str(i + 1), font=small_f, fill=(150, 152, 160))
        tx = 20 + sw + 18
        d.text((tx, y), roles[i], font=role_f, fill=(235, 236, 240))
        d.text((tx, y + 26), names[i], font=body_f, fill=(190, 192, 200))
        note = _COVERAGE_NOTES.get(roles[i], "")
        d.text((tx, y + 50), f"~{coverage[i]:.0f}% - {note}", font=small_f, fill=(150, 152, 160))
    return img


def compose_panel(original_rgb, preview_rgb, legend: Image.Image, gap: int = 10) -> Image.Image:
    imgs = [Image.fromarray(original_rgb), Image.fromarray(preview_rgb), legend]
    h = max(i.height for i in imgs)
    w = sum(i.width for i in imgs) + gap * (len(imgs) - 1)
    canvas = Image.new("RGB", (w, h), (26, 27, 32))
    x = 0
    for im in imgs:
        canvas.paste(im, (x, (h - im.height) // 2))
        x += im.width + gap
    return canvas


def swatch_board(regions, width: int = 460, sw: int = 44, pad: int = 12) -> Image.Image:
    row_h = sw + pad + 24
    height = max(1, pad + len(regions) * row_h)
    img = Image.new("RGB", (width, height), (26, 27, 32))
    d = ImageDraw.Draw(img)
    name_f = _font(20)
    for r, (name, colors) in enumerate(regions):
        y = pad + r * row_h
        d.text((pad, y), name, font=name_f, fill=(235, 236, 240))
        x, yy = pad, y + 26
        for c in colors:
            fill = tuple(int(v) for v in c)
            d.rectangle([x, yy, x + sw, yy + sw], fill=fill, outline=(70, 72, 80), width=2)
            x += sw + 6
    return img
