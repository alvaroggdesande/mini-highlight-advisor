"""
Depth-map spike — the make-or-break de-risking test for Mini Highlight Advisor.

Question this answers: given ONE ordinary photo of a miniature, can a monocular depth
model produce a surface estimate good enough to compute a believable zenithal light map
(light from above) that a painter would recognise as "yes, those are the spots that catch
the light"?

Pipeline (all on the whole image, no regions yet — regions come later):
    photo -> relative depth (Depth-Anything V2) -> surface normals -> zenithal light
    intensity -> quantised bands -> side-by-side visualisation panel

Usage:
    python spikes/depth_spike.py path/to/mini.jpg
    python spikes/depth_spike.py path/to/mini.jpg --bands 5 --flip-depth --light 0,-1,0.6

Outputs a single PNG panel to spikes/out/<name>_panel.png so we can eyeball it.
"""

from __future__ import annotations

import argparse
import os
import sys

import numpy as np
from PIL import Image


def load_depth(image: Image.Image) -> np.ndarray:
    """Run Depth-Anything V2 (small) and return a float depth map in [0, 1].

    The model returns a *relative* depth (disparity-like): larger values are typically
    nearer. We normalise to [0, 1]; the --flip-depth flag lets us invert if the geometry
    looks inside-out.
    """
    from transformers import pipeline

    pipe = pipeline(
        task="depth-estimation",
        model="depth-anything/Depth-Anything-V2-Small-hf",
    )
    result = pipe(image)
    depth = np.asarray(result["depth"], dtype=np.float32)
    d_min, d_max = float(depth.min()), float(depth.max())
    if d_max - d_min < 1e-6:
        return np.zeros_like(depth)
    return (depth - d_min) / (d_max - d_min)


def depth_to_normals(depth: np.ndarray, z_scale: float = 40.0) -> np.ndarray:
    """Estimate per-pixel surface normals from a depth map.

    normal ~ normalize( (-dz/dx, -dz/dy, 1/z_scale) ). z_scale controls how "bumpy" the
    surface is treated as: smaller -> more pronounced normals. Returns HxWx3 in [-1, 1].
    """
    # Light smoothing first so pixel noise doesn't dominate the gradient.
    import cv2

    d = cv2.GaussianBlur(depth, (0, 0), sigmaX=2.0)
    gy, gx = np.gradient(d)
    nx = -gx
    ny = -gy
    nz = np.full_like(d, 1.0 / z_scale)
    normals = np.stack([nx, ny, nz], axis=-1)
    norm = np.linalg.norm(normals, axis=-1, keepdims=True)
    norm = np.where(norm < 1e-6, 1.0, norm)
    return normals / norm


def zenithal_intensity(normals: np.ndarray, light_dir: np.ndarray) -> np.ndarray:
    """Lambertian light response for a single directional light.

    Image coords: +x right, +y DOWN, +z toward viewer. Zenithal light comes from above
    the model, i.e. light_dir points up-and-slightly-toward-viewer, e.g. (0, -1, 0.6).
    """
    L = light_dir / (np.linalg.norm(light_dir) + 1e-9)
    intensity = np.tensordot(normals, L, axes=([2], [0]))
    return np.clip(intensity, 0.0, 1.0)


def band(intensity: np.ndarray, n_bands: int) -> np.ndarray:
    """Quantise a [0,1] intensity map into n discrete bands (0..n-1)."""
    edges = np.linspace(0.0, 1.0, n_bands + 1)
    idx = np.digitize(intensity, edges[1:-1])
    return idx.astype(np.int32)


def colorize(arr: np.ndarray, cmap: str = "viridis") -> np.ndarray:
    import matplotlib

    normed = (arr - arr.min()) / (np.ptp(arr) + 1e-9)
    rgba = matplotlib.colormaps[cmap](normed)
    return (rgba[..., :3] * 255).astype(np.uint8)


def band_colors(bands: np.ndarray, n_bands: int) -> np.ndarray:
    """Map band indices to a dark->bright ramp (shadow -> edge highlight)."""
    import matplotlib

    ramp = matplotlib.colormaps["magma"](np.linspace(0.1, 0.95, n_bands))[:, :3]
    out = ramp[np.clip(bands, 0, n_bands - 1)]
    return (out * 255).astype(np.uint8)


def make_panel(original, depth, normals, intensity, bands, n_bands) -> Image.Image:
    normals_vis = ((normals * 0.5 + 0.5) * 255).astype(np.uint8)
    tiles = [
        ("original", np.asarray(original.convert("RGB"))),
        ("depth", colorize(depth, "inferno")),
        ("normals", normals_vis),
        ("zenithal light", colorize(intensity, "gray")),
        (f"{n_bands} bands", band_colors(bands, n_bands)),
    ]
    h = min(t[1].shape[0] for t in tiles)

    def fit(a):
        scale = h / a.shape[0]
        import cv2

        return cv2.resize(a, (int(a.shape[1] * scale), h))

    imgs = [fit(t[1]) for t in tiles]
    gap = 8
    total_w = sum(i.shape[1] for i in imgs) + gap * (len(imgs) - 1)
    canvas = np.full((h, total_w, 3), 255, dtype=np.uint8)
    x = 0
    for img in imgs:
        canvas[:, x : x + img.shape[1]] = img
        x += img.shape[1] + gap
    return Image.fromarray(canvas)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("image", help="path to a mini photo")
    ap.add_argument("--bands", type=int, default=5)
    ap.add_argument("--flip-depth", action="store_true", help="invert depth if geometry looks inside-out")
    ap.add_argument("--z-scale", type=float, default=40.0)
    ap.add_argument("--light", default="0,-1,0.6", help="light direction x,y,z (y is DOWN)")
    args = ap.parse_args()

    if not os.path.exists(args.image):
        print(f"Image not found: {args.image}")
        return 1

    light_dir = np.array([float(v) for v in args.light.split(",")], dtype=np.float32)

    print("Loading image...")
    image = Image.open(args.image).convert("RGB")
    # Cap size for a fast spike.
    image.thumbnail((768, 768))

    print("Estimating depth (first run downloads the model ~100MB)...")
    depth = load_depth(image)
    if args.flip_depth:
        depth = 1.0 - depth

    print("Computing normals + zenithal light...")
    normals = depth_to_normals(depth, z_scale=args.z_scale)
    intensity = zenithal_intensity(normals, light_dir)
    bands = band(intensity, args.bands)

    os.makedirs("spikes/out", exist_ok=True)
    name = os.path.splitext(os.path.basename(args.image))[0]
    out_path = os.path.join("spikes", "out", f"{name}_panel.png")
    panel = make_panel(image, depth, normals, intensity, bands, args.bands)
    panel.save(out_path)
    print(f"\nSaved panel -> {out_path}")
    print("Eyeball test: in the 'zenithal light' + 'bands' tiles, do the BRIGHT areas land")
    print("on the spots you'd actually highlight (helmet top, shoulder tops, raised edges)?")
    return 0


if __name__ == "__main__":
    sys.exit(main())
