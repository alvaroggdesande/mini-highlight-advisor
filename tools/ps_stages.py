"""Torch-free pure stages of ps_tool: registration, quality gates, consensus,
and the convention-pinned normal encoder. Unit-tested offline; the torch
inference orchestration lives in ps_tool.py and calls into these.
"""
from __future__ import annotations

import numpy as np

IOU_MIN = 0.9
MIN_FRAMES = 4
STD_MIN = 8.0


class CaptureError(Exception):
    """Raised on a fail-loud capture abort (too few frames / no lighting variation)."""


def centroid(mask: np.ndarray) -> tuple[float, float]:
    ys, xs = np.nonzero(mask)
    if ys.size == 0:
        return 0.0, 0.0
    return float(ys.mean()), float(xs.mean())


def _shift(arr: np.ndarray, dr: int, dc: int) -> np.ndarray:
    out = np.zeros_like(arr)
    h, w = arr.shape[:2]
    sr0, sr1 = max(0, dr), min(h, h + dr)
    sc0, sc1 = max(0, dc), min(w, w + dc)
    dr0, dr1 = max(0, -dr), min(h, h - dr)
    dc0, dc1 = max(0, -dc), min(w, w - dc)
    out[sr0:sr1, sc0:sc1] = arr[dr0:dr1, dc0:dc1]
    return out


def align_to_reference(frames, masks):
    r0, c0 = centroid(masks[0])
    a_frames, a_masks, offs = [], [], []
    for f, m in zip(frames, masks):
        r, c = centroid(m)
        dr, dc = int(round(r0 - r)), int(round(c0 - c))
        offs.append((dr, dc))
        a_frames.append(_shift(f, dr, dc))
        a_masks.append(_shift(m.astype(np.uint8), dr, dc) > 0)
    return a_frames, a_masks, offs


def iou(a: np.ndarray, b: np.ndarray) -> float:
    a, b = a.astype(bool), b.astype(bool)
    inter = np.logical_and(a, b).sum()
    union = np.logical_or(a, b).sum()
    return float(inter / union) if union else 0.0


def consensus_mask(masks) -> np.ndarray:
    stack = np.stack([m.astype(np.uint8) for m in masks], axis=0)
    return stack.sum(axis=0) > (len(masks) / 2.0)


def _gray(frame: np.ndarray) -> np.ndarray:
    if frame.ndim == 3:
        return frame.mean(axis=-1)
    return frame.astype(np.float32)


def select_frames(frames, masks, *, iou_min=IOU_MIN, min_frames=MIN_FRAMES,
                  std_min=STD_MIN):
    a_frames, a_masks, _ = align_to_reference(frames, masks)
    ref = a_masks[0]
    ious = [iou(ref, m) for m in a_masks]
    kept = [i for i, v in enumerate(ious) if v >= iou_min]
    dropped = [i for i in range(len(frames)) if i not in kept]
    if len(kept) < min_frames:
        raise CaptureError(
            f"capture too inconsistent: only {len(kept)} of {len(frames)} frames "
            f"survived the IoU gate (need {min_frames}).")
    fg = consensus_mask([a_masks[i] for i in kept])
    stack = np.stack([_gray(a_frames[i])[fg] for i in kept], axis=0)
    lighting_std = float(stack.std(axis=0).mean()) if fg.any() else 0.0
    if lighting_std < std_min:
        raise CaptureError(
            f"insufficient lighting variation (per-pixel std {lighting_std:.1f} < "
            f"{std_min}); move the light more between shots — a turntable won't work.")
    return kept, {"dropped": dropped, "ious": ious, "lighting_std": lighting_std}


def encode_normals(normals: np.ndarray) -> np.ndarray:
    """Inverse of relight.load_normals: unit normals -> uint8 PNG array, pinned."""
    n = normals / np.clip(np.linalg.norm(normals, axis=-1, keepdims=True), 1e-6, None)
    return np.clip((n + 1.0) * 0.5 * 255.0, 0, 255).astype(np.uint8)
