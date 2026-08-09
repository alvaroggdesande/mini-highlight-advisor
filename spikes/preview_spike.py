"""
Spike v3 — the "what the tool would actually output" preview.

Takes a primed-mini photo, computes the highlight light-map (depth/alpha mask + luminance
relief, per the earlier spikes), bands it, and paints each band with a REAL named paint colour.
Renders a final panel: original | painted preview | legend (role, paint name, coverage %).

This turns the abstract bands into something a painter can judge before we build the app.

Usage:
    python spikes/preview_spike.py spikes/input/<mini>.jpg
    python spikes/preview_spike.py spikes/input/<mini>.png --bands 5 --alpha-thresh 200
    # custom palette (dark -> light), name:hex comma-separated:
    python spikes/preview_spike.py <img> --palette "Abaddon Black:#14151a,Leadbelcher:#4b4f54,..."
"""

from __future__ import annotations

import argparse
import os
import sys

import numpy as np
from PIL import Image, ImageDraw, ImageFont

# Reuse the validated mask + light-map logic from the shading spike.
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from shading_spike import (  # noqa: E402
    OUT_DIR,
    alpha_mask,
    band,
    figure_mask,
    load_depth,
    load_rgba,
    luminance_light,
)

# Default palette: a cool grey/metal scheme (dark -> light), fitting sci-fi primed minis.
DEFAULT_PALETTE = [
    ("Abaddon Black", "#14151a"),
    ("Leadbelcher", "#4b4f54"),
    ("Dawnstone", "#71767b"),
    ("Administratum Grey", "#a9adb0"),
    ("White Scar", "#eef0f2"),
]

# Role labels dark -> light, by band count.
ROLES = {
    3: ["Shadow", "Base", "Highlight"],
    4: ["Shadow", "Base", "Midtone", "Highlight"],
    5: ["Shadow", "Base", "Midtone", "Highlight", "Edge Highlight"],
}

COVERAGE_NOTES = {
    "Shadow": "deepest recesses",
    "Base": "the main body of the surface",
    "Midtone": "flat, gently-lit panels",
    "Highlight": "raised areas facing the light",
    "Edge Highlight": "sharpest top edges only",
}


def hex_to_rgb(h: str) -> np.ndarray:
    h = h.lstrip("#")
    return np.array([int(h[i : i + 2], 16) for i in (0, 2, 4)], dtype=np.float32)


def parse_palette(spec: str | None, n: int):
    if spec:
        entries = []
        for part in spec.split(","):
            name, hx = part.rsplit(":", 1)
            entries.append((name.strip(), hx.strip()))
    else:
        entries = DEFAULT_PALETTE
    if len(entries) < n:
        raise SystemExit(f"Palette has {len(entries)} colours but --bands is {n}.")
    return entries[:n]


def role_names(n: int):
    return ROLES.get(n, [f"Layer {i + 1}" for i in range(n)])


def paint_preview(image: Image.Image, bands: np.ndarray, mask: np.ndarray, colors, alpha=0.78):
    """Alpha-blend each band's real paint colour onto the mini, keeping a little of the
    underlying texture so relief stays readable."""
    base = np.asarray(image.convert("RGB")).astype(np.float32)
    out = base.copy()
    # Darken the background slightly so the painted model pops.
    out[~mask] = out[~mask] * 0.25
    for b, rgb in enumerate(colors):
        m = (bands == b) & mask
        out[m] = (1 - alpha) * base[m] + alpha * rgb
    return Image.fromarray(np.clip(out, 0, 255).astype(np.uint8))


def coverage_pct(bands: np.ndarray, mask: np.ndarray, n: int):
    total = int(mask.sum())
    if total == 0:
        return [0.0] * n
    return [100.0 * int(((bands == b) & mask).sum()) / total for b in range(n)]


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
    d.text((20, 52), "dark → light  (paint in this order)", font=small_f, fill=(150, 152, 160))

    n = len(colors)
    top = 92
    row_h = min(96, (height - top - 16) // max(n, 1))
    sw = 54
    for i in range(n):
        y = top + i * row_h
        rgb = tuple(int(v) for v in colors[i])
        d.rectangle([20, y, 20 + sw, y + sw], fill=rgb, outline=(70, 72, 80), width=2)
        d.text((20, y + sw + 2), f"{i + 1}", font=small_f, fill=(150, 152, 160))
        tx = 20 + sw + 18
        d.text((tx, y), roles[i], font=role_f, fill=(235, 236, 240))
        d.text((tx, y + 26), names[i], font=body_f, fill=(190, 192, 200))
        note = COVERAGE_NOTES.get(roles[i], "")
        d.text((tx, y + 50), f"~{coverage[i]:.0f}% · {note}", font=small_f, fill=(150, 152, 160))
    return img


def hstack(imgs, gap=10, bg=(26, 27, 32)):
    h = max(i.height for i in imgs)
    w = sum(i.width for i in imgs) + gap * (len(imgs) - 1)
    canvas = Image.new("RGB", (w, h), bg)
    x = 0
    for im in imgs:
        canvas.paste(im, (x, (h - im.height) // 2))
        x += im.width + gap
    return canvas


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("image")
    ap.add_argument("--bands", type=int, default=5)
    ap.add_argument("--model", default="small")
    ap.add_argument("--alpha-thresh", type=int, default=128)
    ap.add_argument("--palette", default=None, help='name:hex,name:hex,... dark->light')
    args = ap.parse_args()
    if not os.path.exists(args.image):
        print(f"Image not found: {args.image}")
        return 1

    palette = parse_palette(args.palette, args.bands)
    names = [p[0] for p in palette]
    colors = [hex_to_rgb(p[1]) for p in palette]
    roles = role_names(args.bands)

    print("Loading image...")
    image, alpha = load_rgba(args.image)
    if alpha is not None:
        alpha_im = Image.fromarray(alpha)
        image.thumbnail((768, 768))
        alpha_im.thumbnail((768, 768))
        alpha = np.asarray(alpha_im)
        print("Masking from alpha channel.")
        mask = alpha_mask(alpha, args.alpha_thresh)
    else:
        image.thumbnail((768, 768))
        print(f"Estimating depth ({args.model}) for mask...")
        mask = figure_mask(load_depth(image, args.model))

    print("Computing light map + bands...")
    light = luminance_light(image, mask)
    bands = band(light, args.bands, mask)
    coverage = coverage_pct(bands, mask, args.bands)

    preview = paint_preview(image, bands, mask, colors)
    original = image.convert("RGB")
    legend = render_legend(colors, names, roles, coverage, height=preview.height)

    panel = hstack([original, preview, legend])
    os.makedirs(OUT_DIR, exist_ok=True)
    name = os.path.splitext(os.path.basename(args.image))[0]
    out = os.path.join(OUT_DIR, f"{name}_preview.png")
    panel.save(out)
    print(f"\nSaved preview -> {out}")
    for i in range(args.bands):
        print(f"  {roles[i]:16s} {names[i]:22s} ~{coverage[i]:.0f}%")
    return 0


if __name__ == "__main__":
    sys.exit(main())
