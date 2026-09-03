from __future__ import annotations

from dataclasses import dataclass

import numpy as np
from PIL import Image, ImageDraw

from .palette import PaintColor


@dataclass
class Region:
    name: str
    mask: np.ndarray                 # source-resolution bool
    palette: list[PaintColor]
    coverage: list[float]            # len == len(palette), sums to ~1.0
    material: str = "matte"          # "matte" (default) | "nmm" | technique key
    surface: str = "other"           # surface vocabulary key (skin/metal/cloth/…)
    tone: str | None = None          # chosen tone key for realistic surfaces
    blank: bool = False              # skip paint overlay in preview (treated as whole-mini)
    ramp_midtone: str | None = None  # hex used to generate the L2 ramp
    ramp_variant: str | None = None  # "standard"|"complementary"|"warm"|"cool"


def assign_owners(base_mask: np.ndarray, region_masks: list[np.ndarray]) -> np.ndarray:
    owner = np.full(base_mask.shape, -1, dtype=np.int32)
    for i, rm in enumerate(region_masks):
        owner[rm & base_mask] = i        # later i overwrites -> last-wins
    owner[~base_mask] = -2
    return owner


def scale_points(points, sx: float, sy: float):
    return [(x * sx, y * sy) for x, y in points]


def polygon_to_mask(points, shape) -> np.ndarray:
    h, w = shape
    img = Image.new("L", (w, h), 0)
    if len(points) >= 3:
        ImageDraw.Draw(img).polygon([(float(x), float(y)) for x, y in points], fill=1)
    return np.array(img, dtype=bool)


def polygons_to_mask(point_lists, shape) -> np.ndarray:
    """Union of several polygon rings into one boolean mask (shape = (h, w))."""
    out = np.zeros(shape, dtype=bool)
    for pts in point_lists:
        out |= polygon_to_mask(pts, shape)
    return out
