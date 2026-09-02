# src/mini_highlight_advisor/schemes.py
"""Colour schemes: snapshot the palette-per-region of a RegionBook and swap it
back on demand. Torch-free, Streamlit-free. Region identity is the region NAME
(RegionBook has no stable id); a scheme carries palette only."""
from __future__ import annotations

from dataclasses import dataclass, field

from .palette import PaintColor
from .region_state import RegionBook


@dataclass
class Scheme:
    name: str
    palettes: dict[str, list[PaintColor]]     # region_name -> palette snapshot
    anchor: str | None = None                 # region_name; unused in (a), drives (b)


@dataclass
class ApplyReport:
    updated: list[str] = field(default_factory=list)          # region names written
    skipped_regions: list[str] = field(default_factory=list)  # book regions with no key
    unused_keys: list[str] = field(default_factory=list)      # keys matching no region


def snapshot(book: RegionBook, name: str, anchor: str | None = None) -> Scheme:
    names = book.names()
    # PaintColor is frozen, so a list copy is a complete, isolated snapshot.
    palettes = {names[g]: list(book.palette_at(g)) for g in range(len(names))}
    return Scheme(name=name, palettes=palettes, anchor=anchor)


def apply(scheme: Scheme, book: RegionBook) -> ApplyReport:
    report = ApplyReport()
    names = book.names()
    for g, region_name in enumerate(names):
        pal = scheme.palettes.get(region_name)
        if pal is None:
            report.skipped_regions.append(region_name)
        else:
            book.set_palette_at(g, list(pal))
            report.updated.append(region_name)
    present = set(names)
    report.unused_keys = [k for k in scheme.palettes if k not in present]
    return report
