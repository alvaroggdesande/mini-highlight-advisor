from __future__ import annotations

from dataclasses import dataclass

import numpy as np


@dataclass(frozen=True)
class PaintColor:
    name: str
    hex: str
    brand: str | None = None
    paint_range: str | None = None
    code: str = ""
    finish: str = "matte"

    @property
    def rgb(self) -> np.ndarray:
        h = self.hex.lstrip("#")
        return np.array([int(h[i : i + 2], 16) for i in (0, 2, 4)], dtype=np.float32)


# Vallejo greyscale ramp (dark -> light). Hexes are approximate screen-swatches.
DEFAULT_PALETTE = [
    PaintColor("Black", "#1b1b1b", "Vallejo", "Model Color", code="70.950"),
    PaintColor("German Grey", "#3f4442", "Vallejo", "Model Color", code="70.995"),
    PaintColor("Neutral Grey", "#6d7173", "Vallejo", "Model Color", code="70.991"),
    PaintColor("Light Grey", "#a7a9a6", "Vallejo", "Model Color", code="70.990"),
    PaintColor("Dead White", "#f3f3ee", "Vallejo", "Model Color", code="70.951"),
]

_ROLES = {
    3: ["Shadow", "Base", "Highlight"],
    4: ["Shadow", "Base", "Midtone", "Highlight"],
    5: ["Shadow", "Base", "Midtone", "Highlight", "Bright Highlight"],
    6: ["Shadow", "Deep Base", "Base", "Midtone", "Highlight", "Bright Highlight"],
    7: ["Shadow", "Deep Base", "Base", "Midtone", "Upper Midtone",
        "Highlight", "Bright Highlight"],
}


def role_names(n: int) -> list[str]:
    return _ROLES.get(n, [f"Layer {i + 1}" for i in range(n)])


def default_coverage(n: int) -> list[float]:
    # Linear decreasing weights: shadow widest, edge highlight thinnest.
    weights = list(range(n, 0, -1))
    total = sum(weights)
    return [w / total for w in weights]


def ramp_hex(i: int, n: int) -> str:
    # Evenly-spaced neutral grey on the black->white ramp for an n-layer palette.
    v = 0 if n <= 1 else round(255 * i / (n - 1))
    return f"#{v:02x}{v:02x}{v:02x}"


def remainder_pct(others: list[float]) -> float:
    # The lightest band absorbs whatever the other sliders leave.
    return max(0.0, 100.0 - sum(others))


def slider_max_pct(others: list[float], floor: float = 3.0) -> float:
    # Live upper bound for one slider so the remainder band keeps at least `floor`.
    return max(0.0, 100.0 - sum(others) - floor)


def default_ramp(n: int) -> list[PaintColor]:
    """Neutral dark->light ramp for a new region: seed from DEFAULT_PALETTE,
    fill any extra slots with a computed grey ramp."""
    out: list[PaintColor] = []
    for i in range(n):
        if i < len(DEFAULT_PALETTE):
            out.append(DEFAULT_PALETTE[i])
        else:
            out.append(PaintColor(f"Grey {i + 1}", ramp_hex(i, n)))
    return out


def coverage_pct(bands: np.ndarray, mask: np.ndarray, n: int) -> list[float]:
    total = int(mask.sum())
    if total == 0:
        return [0.0] * n
    return [100.0 * int(((bands == b) & mask).sum()) / total for b in range(n)]
