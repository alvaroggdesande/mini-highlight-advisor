from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np

from .palette import PaintColor, default_coverage, default_ramp
from .pipeline import WHOLE_MINI
from .regions import Region


@dataclass
class RegionBook:
    """Ordered regions for the editor. Global index 0 is the 'Whole mini'
    leftover region (its mask is computed at render time, so it is stored as
    palette + coverage only); indices 1..N are drawn Regions. Pure state — no
    Streamlit."""

    whole_palette: list[PaintColor]
    whole_coverage: list[float]
    whole_material: str = "matte"
    whole_surface: str = "other"
    whole_tone: str | None = None
    drawn: list[Region] = field(default_factory=list)
    selected: int = 0

    def names(self) -> list[str]:
        return [WHOLE_MINI] + [r.name for r in self.drawn]

    def _check(self, g: int) -> None:
        if not (0 <= g <= len(self.drawn)):
            raise IndexError(f"region index {g} out of range")

    def palette_at(self, g: int) -> list[PaintColor]:
        self._check(g)
        return self.whole_palette if g == 0 else self.drawn[g - 1].palette

    def coverage_at(self, g: int) -> list[float]:
        self._check(g)
        return self.whole_coverage if g == 0 else self.drawn[g - 1].coverage

    def set_palette_at(self, g: int, palette: list[PaintColor]) -> None:
        self._check(g)
        if g == 0:
            self.whole_palette = palette
        else:
            self.drawn[g - 1].palette = palette

    def set_coverage_at(self, g: int, coverage: list[float]) -> None:
        self._check(g)
        if g == 0:
            self.whole_coverage = coverage
        else:
            self.drawn[g - 1].coverage = coverage

    def material_at(self, g: int) -> str:
        self._check(g)
        return self.whole_material if g == 0 else self.drawn[g - 1].material

    def set_material_at(self, g: int, material: str) -> None:
        self._check(g)
        if g == 0:
            self.whole_material = material
        else:
            self.drawn[g - 1].material = material

    def surface_at(self, g: int) -> str:
        self._check(g)
        return self.whole_surface if g == 0 else self.drawn[g - 1].surface

    def set_surface_at(self, g: int, surface: str) -> None:
        self._check(g)
        if g == 0:
            self.whole_surface = surface
        else:
            self.drawn[g - 1].surface = surface

    def tone_at(self, g: int) -> str | None:
        self._check(g)
        return self.whole_tone if g == 0 else self.drawn[g - 1].tone

    def set_tone_at(self, g: int, tone: str | None) -> None:
        self._check(g)
        if g == 0:
            self.whole_tone = tone
        else:
            self.drawn[g - 1].tone = tone

    def set_name_at(self, g: int, name: str) -> None:
        if g == 0:
            raise ValueError("cannot rename the 'Whole mini' region")
        self._check(g)
        clean = name.strip()
        if clean:
            self.drawn[g - 1].name = clean

    def add(self, mask: np.ndarray, name: str,
            palette: list[PaintColor], coverage: list[float]) -> int:
        self.drawn.append(Region(name, mask, palette, coverage))
        self.selected = len(self.drawn)
        return self.selected

    def remove(self, g: int) -> None:
        if g == 0:
            raise ValueError("cannot remove the 'Whole mini' region")
        self._check(g)
        del self.drawn[g - 1]
        if self.selected == g:
            self.selected = g - 1
        elif self.selected > g:
            self.selected -= 1

    def analyze_args(self) -> tuple[list[PaintColor], list[float], list[Region]]:
        return self.whole_palette, self.whole_coverage, list(self.drawn)


def new_book(n: int = 5) -> RegionBook:
    return RegionBook(default_ramp(n), default_coverage(n))
