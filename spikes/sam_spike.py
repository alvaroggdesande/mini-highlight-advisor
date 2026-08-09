"""Spike 5 - SAM automatic region segmentation on a PRIMED mini.

QUESTION: does Segment Anything (a LOCAL CV model - no API, no network) carve a
monochrome primed miniature into usable region blobs (blade / robe / arm / base),
or does the lack of colour starve it?

This is the ONE unknown left in the offline "SAM + manual labelling" region plan
(see docs/superpowers/specs/2026-08-09-roadmap-and-idea-assessment.md): SAM proposes
masks locally, the user names them. No LLM, no internet.

HOW TO READ THE RESULT: open the saved `*_sam_overlay.png`. Each coloured blob is one
SAM mask over a dimmed copy of the mini. GOOD = the big blobs land on real parts
(blade, robe, arm/limb, base, head) with roughly the right boundaries. BAD = noise
confetti, one blob swallowing the whole figure, or boundaries that ignore the sculpt.
The verdict decides: regions can be SAM-assisted (good) vs must be fully manual (bad).

Run (in .venv, CPU is fine but slow - first run downloads the SAM checkpoint):
    .venv/Scripts/python spikes/sam_spike.py fixtures/skaven-hero/primed.png

Options:
    --points-per-side 16      sampling-grid density (higher = more/finer masks, slower)
    --points-per-batch 16     lower if you hit memory pressure on CPU
    --min-area 0.4            drop masks smaller than this %% of the image (noise)
    --max-area 60             drop masks bigger than this %% (kills whole-figure blob)
    --max-show 25             cap masks drawn in the overlay (largest first)
    --model facebook/sam-vit-base
    --max-side 1024           downscale longest side before running (speed)
"""

from __future__ import annotations

import argparse
import os
import sys

import numpy as np
from PIL import Image

# Distinct-ish colours for the overlay (cycled if there are more masks).
_COLORS = np.array(
    [
        [230, 25, 75], [60, 180, 75], [255, 225, 25], [0, 130, 200],
        [245, 130, 48], [145, 30, 180], [70, 240, 240], [240, 50, 230],
        [210, 245, 60], [250, 190, 212], [0, 128, 128], [220, 190, 255],
        [170, 110, 40], [255, 250, 200], [128, 0, 0], [170, 255, 195],
        [128, 128, 0], [255, 215, 180], [0, 0, 128], [128, 128, 128],
    ],
    dtype=np.float32,
)


def _load_rgb(path: str, max_side: int) -> np.ndarray:
    img = Image.open(path).convert("RGB")
    if max_side and max(img.size) > max_side:
        scale = max_side / max(img.size)
        new = (round(img.size[0] * scale), round(img.size[1] * scale))
        img = img.resize(new, Image.LANCZOS)
        print(f"  resized to {new[0]}x{new[1]} (longest side {max_side})")
    return np.asarray(img, dtype=np.uint8)


def _run_sam(generator, image: np.ndarray, pps: int, ppb: int):
    """Call the mask-generation pipeline, coping with kwarg-name drift across
    transformers versions (points_per_side vs points_per_crop)."""
    last_err = None
    for density_key in ("points_per_side", "points_per_crop", None):
        kw = {"points_per_batch": ppb}
        if density_key:
            kw[density_key] = pps
        try:
            out = generator(Image.fromarray(image), **kw)
            if density_key:
                print(f"  (grid controlled via '{density_key}={pps}')")
            else:
                print("  (grid density kwarg not accepted - using pipeline default)")
            return out
        except TypeError as e:  # unknown kwarg for this version - fail fast, retry
            last_err = e
    raise last_err


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("image")
    p.add_argument("--model", default="facebook/sam-vit-base")
    p.add_argument("--points-per-side", type=int, default=16)
    p.add_argument("--points-per-batch", type=int, default=16)
    p.add_argument("--min-area", type=float, default=0.4, help="%% of image")
    p.add_argument("--max-area", type=float, default=60.0, help="%% of image")
    p.add_argument("--max-show", type=int, default=25)
    p.add_argument("--max-side", type=int, default=1024)
    p.add_argument("--out", default="spikes/out")
    args = p.parse_args()

    if not os.path.exists(args.image):
        print(f"ERROR: input not found: {args.image}\n"
              f"Save the CLEAN primed photo there first (see fixtures README).",
              file=sys.stderr)
        return 2

    print(f"Loading image: {args.image}")
    image = _load_rgb(args.image, args.max_side)
    h, w = image.shape[:2]
    total = float(h * w)

    print(f"Loading SAM ({args.model}) on CPU - first run downloads the checkpoint...")
    from transformers import pipeline

    generator = pipeline("mask-generation", model=args.model, device=-1)

    print("Generating masks (this is the slow part on CPU)...")
    outputs = _run_sam(generator, image, args.points_per_side, args.points_per_batch)
    masks = outputs["masks"]
    scores = outputs.get("scores")
    print(f"  raw masks: {len(masks)}")

    # Filter by area; keep as (mask, area_pct, score).
    kept = []
    for i, m in enumerate(masks):
        m = np.asarray(m, dtype=bool)
        area_pct = 100.0 * m.sum() / total
        if args.min_area <= area_pct <= args.max_area:
            sc = float(scores[i]) if scores is not None else float("nan")
            kept.append((m, area_pct, sc))
    kept.sort(key=lambda t: t[1], reverse=True)
    print(f"  kept after area filter [{args.min_area}%%..{args.max_area}%%]: {len(kept)}")

    if not kept:
        print("VERDICT: no masks survived filtering - SAM found nothing region-like. "
              "Loosen --min-area/--max-area or treat this as a FAIL for auto-regions.")
        return 0

    # Build overlay: dimmed greyscale base + coloured masks on top.
    gray = image.astype(np.float32) @ np.array([0.299, 0.587, 0.114], np.float32)
    base = np.repeat(gray[:, :, None], 3, axis=2) * 0.35
    overlay = base.copy()
    alpha = 0.5
    shown = kept[: args.max_show]
    print("\n  #  area%   score   colour")
    for idx, (m, area_pct, sc) in enumerate(shown):
        color = _COLORS[idx % len(_COLORS)]
        overlay[m] = (1 - alpha) * overlay[m] + alpha * color
        print(f"  {idx:>2} {area_pct:6.1f}  {sc:6.3f}   rgb{tuple(int(c) for c in color)}")

    os.makedirs(args.out, exist_ok=True)
    stem = os.path.splitext(os.path.basename(args.image))[0]
    out_path = os.path.join(args.out, f"{stem}_sam_overlay.png")
    Image.fromarray(np.clip(overlay, 0, 255).astype(np.uint8)).save(out_path)
    print(f"\nSaved: {out_path}")
    print(f"Showing {len(shown)} of {len(kept)} kept masks (largest first).")
    print("\nEYEBALL IT: do the big blobs land on blade / robe / arm / base / head "
          "with sensible boundaries? That is the go/no-go for SAM-assisted regions.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
