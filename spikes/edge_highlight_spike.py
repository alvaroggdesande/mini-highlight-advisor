"""Edge-highlight operator spike. Run: python spikes/edge_highlight_spike.py
Writes side-by-side candidates to spikes/output/ for human inspection.
GATE: proceed to edges.py only if one operator gives clean, thin plate lines."""
import os
import cv2
import numpy as np
from mini_highlight_advisor.masking import load_image, compute_mask
from mini_highlight_advisor.lighting import luminance_light

FIXTURES = [
    "spikes/input/WhatsApp_Image_2026-08-09_at_14.04.41-removebg-preview.png",
    "spikes/input/WhatsApp_Image_2026-08-09_at_15.53.49__1_-removebg-preview.png",
    "spikes/input/WhatsApp_Image_2026-08-09_at_15.53.48-removebg-preview.png",
]
OUT = "spikes/output"


def grad_mag(light, mask):
    l = light.astype(np.float32)
    gx = cv2.Sobel(l, cv2.CV_32F, 1, 0, ksize=3)
    gy = cv2.Sobel(l, cv2.CV_32F, 0, 1, ksize=3)
    mag = np.hypot(gx, gy)
    mag[~mask] = 0.0
    return mag


def bright_side(light, mask, win=9):
    local = cv2.blur(light.astype(np.float32), (win, win))
    return (light.astype(np.float32) >= local) & mask


def cand_sobel(light, mask, pct=90.0):
    mag = grad_mag(light, mask)
    vals = mag[mask]; vals = vals[vals > 0]
    thr = np.percentile(vals, pct)
    return (mag >= thr) & bright_side(light, mask)


def cand_canny(light, mask, lo=60, hi=150):
    l8 = cv2.normalize(light.astype(np.float32), None, 0, 255, cv2.NORM_MINMAX).astype(np.uint8)
    l8[~mask] = 0
    return (cv2.Canny(l8, lo, hi) > 0) & bright_side(light, mask)


def overlay(rgb, edge, color=(255, 40, 200)):
    out = (rgb.astype(np.float32) * 0.35).astype(np.uint8)
    out[edge] = color
    return out


def main():
    os.makedirs(OUT, exist_ok=True)
    for i, fx in enumerate(FIXTURES):
        stem = f"fx{i}_" + os.path.splitext(os.path.basename(fx))[0][-18:]
        rgb, alpha = load_image(fx)
        mask = compute_mask(rgb, alpha)
        light = luminance_light(rgb, mask)
        cv2.imwrite(f"{OUT}/{stem}__00_light.png", light)
        for name, edge in [
            ("sobel_p90", cand_sobel(light, mask, 90.0)),
            ("sobel_p85", cand_sobel(light, mask, 85.0)),
            ("canny", cand_canny(light, mask)),
        ]:
            img = overlay(rgb, edge)
            cv2.imwrite(f"{OUT}/{stem}__{name}.png", cv2.cvtColor(img, cv2.COLOR_RGB2BGR))
            print(stem, name, "edge px:", int(edge.sum()))


if __name__ == "__main__":
    main()
