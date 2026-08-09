from __future__ import annotations

from dataclasses import dataclass

import numpy as np


@dataclass(frozen=True)
class PaintColor:
    name: str
    hex: str
    brand: str | None = None
    paint_range: str | None = None

    @property
    def rgb(self) -> np.ndarray:
        h = self.hex.lstrip("#")
        return np.array([int(h[i : i + 2], 16) for i in (0, 2, 4)], dtype=np.float32)


# Vallejo greyscale ramp (dark -> light). Hexes are approximate screen-swatches.
DEFAULT_PALETTE = [
    PaintColor("Black", "#1b1b1b", "Vallejo", "Model Color"),
    PaintColor("German Grey", "#3f4442", "Vallejo", "Model Color"),
    PaintColor("Neutral Grey", "#6d7173", "Vallejo", "Model Color"),
    PaintColor("Light Grey", "#a7a9a6", "Vallejo", "Model Color"),
    PaintColor("Dead White", "#f3f3ee", "Vallejo", "Model Color"),
]

_ROLES = {
    3: ["Shadow", "Base", "Highlight"],
    4: ["Shadow", "Base", "Midtone", "Highlight"],
    5: ["Shadow", "Base", "Midtone", "Highlight", "Edge Highlight"],
}


def role_names(n: int) -> list[str]:
    return _ROLES.get(n, [f"Layer {i + 1}" for i in range(n)])


def default_coverage(n: int) -> list[float]:
    # Linear decreasing weights: shadow widest, edge highlight thinnest.
    weights = list(range(n, 0, -1))
    total = sum(weights)
    return [w / total for w in weights]


def coverage_pct(bands: np.ndarray, mask: np.ndarray, n: int) -> list[float]:
    total = int(mask.sum())
    if total == 0:
        return [0.0] * n
    return [100.0 * int(((bands == b) & mask).sum()) / total for b in range(n)]
