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


def mask_from_depthmap(depth: np.ndarray) -> np.ndarray:
    d = depth.astype(np.float32)
    d = (d - d.min()) / (np.ptp(d) + 1e-9) if np.ptp(d) > 1e-9 else np.zeros_like(d)
    d8 = (d * 255).astype(np.uint8)
    _, binary = cv2.threshold(d8, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
    return _largest_blob(binary)


def mask_from_depth(rgb: np.ndarray, model: str = "depth-anything/Depth-Anything-V2-Small-hf") -> np.ndarray:
    from transformers import pipeline

    pipe = pipeline(task="depth-estimation", model=model)
    depth = np.asarray(pipe(Image.fromarray(rgb))["depth"], dtype=np.float32)
    return mask_from_depthmap(depth)


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
    return mask_from_depth(rgb)
