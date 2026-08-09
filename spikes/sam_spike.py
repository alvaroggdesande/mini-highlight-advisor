"""Spike 5 - SAM region segmentation on a PRIMED mini (auto + prompt modes).

QUESTION: does Segment Anything (a LOCAL CV model - no API, no network) give us
usable region masks on a monochrome primed mini so a user can name them?

Two modes:
  * auto   - "segment everything" (blind grid of points). HARD on a low-contrast
             primer; this is what failed first: only the bright blade + base showed.
  * prompt - the REAL "SAM + manual" workflow: click points ON the body and SAM
             grows the region at each click. Much easier for SAM than auto.

Also `--enhance` (ON by default) CLAHE-boosts contrast first, so a dark/underexposed
primer's edges become visible to SAM (same trick lighting.py uses).

HOW TO READ IT: open the saved overlay. In prompt mode each click gets its own colour
+ a white cross marker. GOOD = clicking the robe/arm/head grows a mask that covers
that part with sensible boundaries -> "SAM + manual" is viable. BAD = the mask bleeds
across the whole figure or collapses to nothing -> regions must be brushed by hand.

Run (in .venv; first run downloads facebook/sam-vit-base ~375MB to the HF cache):
    # prompt mode with default body clicks (recommended next test):
    .venv/Scripts/python spikes/sam_spike.py fixtures/skaven-hero/primed.png
    # your own clicks (fractions of width,height; ';'-separated):
    .venv/Scripts/python spikes/sam_spike.py fixtures/skaven-hero/primed.png \
        --click "0.5,0.66;0.72,0.66;0.44,0.48"
    # re-run the original automatic mode:
    .venv/Scripts/python spikes/sam_spike.py fixtures/skaven-hero/primed.png --mode auto
    # turn the contrast boost off to compare:
    .venv/Scripts/python spikes/sam_spike.py fixtures/skaven-hero/primed.png --no-enhance
"""

from __future__ import annotations

import argparse
import os
import sys

import numpy as np
from PIL import Image

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

# (x_frac, y_frac, label) - default clicks on the body parts auto-mode missed.
_DEFAULT_CLICKS = [
    (0.50, 0.66, "torso"),
    (0.72, 0.66, "arm/shield"),
    (0.44, 0.48, "head"),
    (0.45, 0.82, "lower robe"),
]


def _load_rgb(path: str, max_side: int) -> np.ndarray:
    img = Image.open(path).convert("RGB")
    if max_side and max(img.size) > max_side:
        scale = max_side / max(img.size)
        new = (round(img.size[0] * scale), round(img.size[1] * scale))
        img = img.resize(new, Image.LANCZOS)
        print(f"  resized to {new[0]}x{new[1]} (longest side {max_side})")
    return np.asarray(img, dtype=np.uint8)


def _enhance(rgb: np.ndarray) -> np.ndarray:
    """CLAHE on the L channel so a dark/underexposed primer shows edges."""
    import cv2

    lab = cv2.cvtColor(rgb, cv2.COLOR_RGB2LAB)
    l, a, b = cv2.split(lab)
    l = cv2.createCLAHE(clipLimit=3.0, tileGridSize=(8, 8)).apply(l)
    return cv2.cvtColor(cv2.merge([l, a, b]), cv2.COLOR_LAB2RGB)


def _parse_clicks(spec: str | None, w: int, h: int):
    """Return list of (x_px, y_px, label)."""
    src = _DEFAULT_CLICKS
    if spec:
        src = []
        for i, pair in enumerate(p for p in spec.split(";") if p.strip()):
            xf, yf = (float(v) for v in pair.split(","))
            src.append((xf, yf, f"click{i}"))
    return [(int(round(xf * w)), int(round(yf * h)), lbl) for xf, yf, lbl in src]


def _run_prompt(image: np.ndarray, clicks, model_name: str):
    import torch
    from transformers import SamModel, SamProcessor

    print(f"Loading SAM ({model_name}) on CPU...")
    model = SamModel.from_pretrained(model_name)
    proc = SamProcessor.from_pretrained(model_name)
    pil = Image.fromarray(image)

    results = []
    for x, y, label in clicks:
        inputs = proc(pil, input_points=[[[x, y]]], return_tensors="pt")
        with torch.no_grad():
            out = model(**inputs)
        masks = proc.post_process_masks(
            out.pred_masks, inputs["original_sizes"], inputs["reshaped_input_sizes"]
        )[0][0]  # (3, H, W) multimask
        scores = out.iou_scores[0, 0]  # (3,)
        best = int(scores.argmax())
        m = masks[best].numpy().astype(bool)
        area = 100.0 * m.sum() / m.size
        results.append((m, f"{label} @({x},{y})", float(scores[best]), (x, y)))
        print(f"  {label:<12} @({x:>4},{y:>4})  area={area:5.1f}%  iou={float(scores[best]):.3f}")
    return results


def _run_auto(image: np.ndarray, model_name: str, pps: int, ppb: int,
              min_a: float, max_a: float, max_show: int):
    from transformers import pipeline

    print(f"Loading SAM ({model_name}) on CPU...")
    gen = pipeline("mask-generation", model=model_name, device=-1)
    total = float(image.shape[0] * image.shape[1])

    outputs = None
    last = None
    for key in ("points_per_side", "points_per_crop", None):
        kw = {"points_per_batch": ppb}
        if key:
            kw[key] = pps
        try:
            outputs = gen(Image.fromarray(image), **kw)
            break
        except TypeError as e:
            last = e
    if outputs is None:
        raise last

    masks, scores = outputs["masks"], outputs.get("scores")
    kept = []
    for i, m in enumerate(masks):
        m = np.asarray(m, dtype=bool)
        a = 100.0 * m.sum() / total
        if min_a <= a <= max_a:
            sc = float(scores[i]) if scores is not None else float("nan")
            kept.append((m, f"mask{i}", sc, None))
    kept.sort(key=lambda t: t[0].sum(), reverse=True)
    for m, lbl, sc, _ in kept[:max_show]:
        print(f"  {lbl:<8} area={100.0 * m.sum() / total:5.1f}%  iou={sc:.3f}")
    return kept[:max_show]


def _visualize(image, results, out_path):
    gray = image.astype(np.float32) @ np.array([0.299, 0.587, 0.114], np.float32)
    overlay = np.repeat(gray[:, :, None], 3, axis=2) * 0.35
    for idx, (m, _lbl, _sc, click) in enumerate(results):
        color = _COLORS[idx % len(_COLORS)]
        overlay[m] = 0.5 * overlay[m] + 0.5 * color
        if click is not None:  # white cross at the click point
            cx, cy = click
            overlay[max(cy - 6, 0):cy + 6, max(cx - 1, 0):cx + 2] = 255
            overlay[max(cy - 1, 0):cy + 2, max(cx - 6, 0):cx + 6] = 255
    os.makedirs(os.path.dirname(out_path), exist_ok=True)
    Image.fromarray(np.clip(overlay, 0, 255).astype(np.uint8)).save(out_path)


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("image")
    p.add_argument("--mode", choices=["prompt", "auto"], default="prompt")
    p.add_argument("--click", default=None, help='"x,y;x,y" as fractions of w,h')
    p.add_argument("--enhance", action=argparse.BooleanOptionalAction, default=True)
    p.add_argument("--model", default="facebook/sam-vit-base")
    p.add_argument("--points-per-side", type=int, default=16)
    p.add_argument("--points-per-batch", type=int, default=16)
    p.add_argument("--min-area", type=float, default=0.4)
    p.add_argument("--max-area", type=float, default=60.0)
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
    if args.enhance:
        print("  CLAHE contrast-enhance: ON")
        image = _enhance(image)
    h, w = image.shape[:2]

    print(f"Mode: {args.mode}")
    if args.mode == "prompt":
        clicks = _parse_clicks(args.click, w, h)
        results = _run_prompt(image, clicks, args.model)
    else:
        results = _run_auto(image, args.model, args.points_per_side,
                            args.points_per_batch, args.min_area, args.max_area,
                            args.max_show)

    if not results:
        print("VERDICT: no usable masks -> treat as FAIL for SAM-assisted regions.")
        return 0

    stem = os.path.splitext(os.path.basename(args.image))[0]
    suffix = "prompt" if args.mode == "prompt" else "auto"
    out_path = os.path.join(args.out, f"{stem}_sam_{suffix}.png")
    _visualize(image, results, out_path)
    print(f"\nSaved: {out_path}")
    print("EYEBALL IT: in prompt mode, did each click grow a mask that covers that "
          "body part with sensible edges? That is the go/no-go for SAM + manual.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
