"""
Spike v2 — test the "read relief from the photo's own luminance" hypothesis.

Finding from depth_spike.py: monocular depth (Depth-Anything V2 Small) captures figure-ground
and gross form well, but SMOOTHS AWAY the fine relief (armour edges, pauldron tops, helmet
crest) that painters actually highlight. Normals varied only at the silhouette.

Hypothesis: a grey/black-PRIMED mini photographed under normal light is already a shading map —
pixel brightness ~ how much light the surface catches. So:
    - use DEPTH only to build a clean figure MASK (its strength)
    - compute the light map from image LUMINANCE inside that mask (fine detail)
    - band it and overlay the bands ON the actual mini so placement is judgeable

Outputs spikes/out/<name>_shading.png : original | figure mask | luminance-light |
bands-overlay(depth) | bands-overlay(luminance)

Usage:
    python spikes/shading_spike.py path/to/mini.jpg --bands 5 --model small
"""

from __future__ import annotations

import argparse
import os
import sys

import numpy as np
from PIL import Image

HERE = os.path.dirname(os.path.abspath(__file__))
OUT_DIR = os.path.join(HERE, "out")

MODELS = {
    "small": "depth-anything/Depth-Anything-V2-Small-hf",
    "base": "depth-anything/Depth-Anything-V2-Base-hf",
    "large": "depth-anything/Depth-Anything-V2-Large-hf",
}


def load_depth(image: Image.Image, model_key: str) -> np.ndarray:
    from transformers import pipeline

    pipe = pipeline(task="depth-estimation", model=MODELS[model_key])
    depth = np.asarray(pipe(image)["depth"], dtype=np.float32)
    d_min, d_max = float(depth.min()), float(depth.max())
    return np.zeros_like(depth) if d_max - d_min < 1e-6 else (depth - d_min) / (d_max - d_min)


def figure_mask(depth: np.ndarray) -> np.ndarray:
    """Otsu threshold on depth to separate the (nearer) figure from the background."""
    import cv2

    d8 = (depth * 255).astype(np.uint8)
    _, mask = cv2.threshold(d8, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
    # Largest connected component = the mini; drop specks.
    n, labels, stats, _ = cv2.connectedComponentsWithStats(mask, connectivity=8)
    if n > 1:
        biggest = 1 + int(np.argmax(stats[1:, cv2.CC_STAT_AREA]))
        mask = np.where(labels == biggest, 255, 0).astype(np.uint8)
    mask = cv2.morphologyEx(mask, cv2.MORPH_CLOSE, np.ones((5, 5), np.uint8))
    return mask > 0


def luminance_light(image: Image.Image, mask: np.ndarray) -> np.ndarray:
    """Light map from the photo's own brightness, contrast-stretched WITHIN the mask."""
    import cv2

    gray = cv2.cvtColor(np.asarray(image.convert("RGB")), cv2.COLOR_RGB2GRAY).astype(np.float32)
    # CLAHE brings out local relief that global stretch would flatten.
    clahe = cv2.createCLAHE(clipLimit=3.0, tileGridSize=(8, 8))
    gray = clahe.apply(gray.astype(np.uint8)).astype(np.float32)
    inside = gray[mask]
    if inside.size == 0:
        return np.zeros_like(gray)
    lo, hi = np.percentile(inside, 2), np.percentile(inside, 98)
    light = np.clip((gray - lo) / (hi - lo + 1e-9), 0.0, 1.0)
    light[~mask] = 0.0
    return light


def depth_light(depth: np.ndarray, mask: np.ndarray) -> np.ndarray:
    """Zenithal light from depth-derived normals, for side-by-side comparison."""
    import cv2

    d = cv2.GaussianBlur(depth, (0, 0), sigmaX=2.0)
    gy, gx = np.gradient(d)
    nx, ny, nz = -gx, -gy, np.full_like(d, 1.0 / 40.0)
    n = np.stack([nx, ny, nz], -1)
    n /= np.linalg.norm(n, axis=-1, keepdims=True) + 1e-9
    L = np.array([0, -1, 0.6], np.float32)
    L /= np.linalg.norm(L)
    light = np.clip(np.tensordot(n, L, ([2], [0])), 0, 1)
    inside = light[mask]
    if inside.size:
        lo, hi = np.percentile(inside, 2), np.percentile(inside, 98)
        light = np.clip((light - lo) / (hi - lo + 1e-9), 0, 1)
    light[~mask] = 0.0
    return light


def band(light: np.ndarray, n_bands: int, mask: np.ndarray) -> np.ndarray:
    edges = np.linspace(0.0, 1.0, n_bands + 1)
    idx = np.digitize(light, edges[1:-1]).astype(np.int32)
    idx[~mask] = -1
    return idx


def overlay_bands(image: Image.Image, bands: np.ndarray, n_bands: int, alpha=0.55) -> np.ndarray:
    import matplotlib

    base = np.asarray(image.convert("RGB")).astype(np.float32)
    ramp = matplotlib.colormaps["magma"](np.linspace(0.12, 0.95, n_bands))[:, :3] * 255
    out = base.copy()
    for b in range(n_bands):
        m = bands == b
        out[m] = (1 - alpha) * base[m] + alpha * ramp[b]
    return out.astype(np.uint8)


def gray_rgb(light: np.ndarray) -> np.ndarray:
    return np.stack([(light * 255).astype(np.uint8)] * 3, -1)


def mask_rgb(mask: np.ndarray) -> np.ndarray:
    return np.stack([(mask * 255).astype(np.uint8)] * 3, -1)


def make_panel(tiles) -> Image.Image:
    import cv2

    h = min(t[1].shape[0] for t in tiles)

    def fit(a):
        s = h / a.shape[0]
        return cv2.resize(a, (int(a.shape[1] * s), h))

    imgs = [fit(t[1]) for t in tiles]
    gap = 8
    W = sum(i.shape[1] for i in imgs) + gap * (len(imgs) - 1)
    canvas = np.full((h, W, 3), 255, np.uint8)
    x = 0
    for img in imgs:
        canvas[:, x : x + img.shape[1]] = img
        x += img.shape[1] + gap
    return Image.fromarray(canvas)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("image")
    ap.add_argument("--bands", type=int, default=5)
    ap.add_argument("--model", choices=list(MODELS), default="small")
    args = ap.parse_args()
    if not os.path.exists(args.image):
        print(f"Image not found: {args.image}")
        return 1

    print("Loading image...")
    image = Image.open(args.image).convert("RGB")
    image.thumbnail((768, 768))

    print(f"Estimating depth ({args.model})...")
    depth = load_depth(image, args.model)

    print("Building mask + light maps...")
    mask = figure_mask(depth)
    lum = luminance_light(image, mask)
    dl = depth_light(depth, mask)

    b_lum = band(lum, args.bands, mask)
    b_depth = band(dl, args.bands, mask)

    tiles = [
        ("original", np.asarray(image)),
        ("figure mask", mask_rgb(mask)),
        ("luminance light", gray_rgb(lum)),
        ("bands (depth)", overlay_bands(image, b_depth, args.bands)),
        ("bands (luminance)", overlay_bands(image, b_lum, args.bands)),
    ]
    os.makedirs(OUT_DIR, exist_ok=True)
    name = os.path.splitext(os.path.basename(args.image))[0]
    out = os.path.join(OUT_DIR, f"{name}_shading.png")
    make_panel(tiles).save(out)
    print(f"\nSaved -> {out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
