from __future__ import annotations

from dataclasses import dataclass

import numpy as np

from .palette import PaintColor


@dataclass
class Region:
    name: str
    mask: np.ndarray                 # source-resolution bool
    palette: list[PaintColor]
    coverage: list[float]            # len == len(palette), sums to ~1.0


def assign_owners(base_mask: np.ndarray, region_masks: list[np.ndarray]) -> np.ndarray:
    owner = np.full(base_mask.shape, -1, dtype=np.int32)
    for i, rm in enumerate(region_masks):
        owner[rm & base_mask] = i        # later i overwrites -> last-wins
    owner[~base_mask] = -2
    return owner
