from __future__ import annotations

import cv2
import numpy as np
from PIL import Image


def _largest_blob(binary: np.ndarray) -> np.ndarray:
    n, labels, stats, _ = cv2.connectedComponentsWithStats(binary, connectivity=8)
    if n > 1:
        biggest = 1 + int(np.argmax(stats[1:, cv2.CC_STAT_AREA]))
        binary = np.where(labels == biggest, 255, 0).astype(np.uint8)
    binary = cv2.morphologyEx(binary, cv2.MORPH_CLOSE, np.ones((5, 5), np.uint8))
    return binary > 0


def mask_from_alpha(alpha: np.ndarray, thresh: int = 128) -> np.ndarray:
    return _largest_blob((alpha > thresh).astype(np.uint8) * 255)


def mask_from_grabcut(rgb: np.ndarray, iters: int = 5, border: int = 8) -> np.ndarray:
    """Classical foreground cutout for photos without an alpha channel.

    GrabCut seeded with a border-inset rectangle: everything inside the rect is
    "probable foreground", the thin border is "definite background". Assumes the
    mini is roughly centred and fills most of the frame (what the input-check
    panel nudges users toward). Zero model download — replaces the old depth
    fallback. Bg-removed PNGs remain the fast path via the alpha branch.
    """
    h, w = rgb.shape[:2]
    bgr = cv2.cvtColor(rgb, cv2.COLOR_RGB2BGR)
    gc = np.zeros((h, w), dtype=np.uint8)
    bgd = np.zeros((1, 65), dtype=np.float64)
    fgd = np.zeros((1, 65), dtype=np.float64)
    b = min(border, max(0, min(h, w) // 2 - 1))
    rect = (b, b, max(1, w - 2 * b), max(1, h - 2 * b))
    cv2.grabCut(bgr, gc, rect, bgd, fgd, iters, cv2.GC_INIT_WITH_RECT)
    fg = np.isin(gc, (cv2.GC_FGD, cv2.GC_PR_FGD)).astype(np.uint8) * 255
    return _largest_blob(fg)


def load_image(path: str, max_side: int = 768) -> tuple[np.ndarray, np.ndarray | None]:
    im = Image.open(path)
    has_alpha = im.mode in ("RGBA", "LA") or (im.mode == "P" and "transparency" in im.info)
    if has_alpha:
        rgba = im.convert("RGBA")
        rgba.thumbnail((max_side, max_side))
        arr = np.asarray(rgba)
        alpha = arr[..., 3].copy()
        bg = Image.new("RGBA", rgba.size, (0, 0, 0, 255))
        rgb = np.asarray(Image.alpha_composite(bg, rgba).convert("RGB"))
        return rgb, alpha
    rgb_im = im.convert("RGB")
    rgb_im.thumbnail((max_side, max_side))
    return np.asarray(rgb_im), None


def compute_mask(rgb: np.ndarray, alpha: np.ndarray | None, alpha_thresh: int = 128) -> np.ndarray:
    if alpha is not None:
        return mask_from_alpha(alpha, alpha_thresh)
    return mask_from_grabcut(rgb)
