from __future__ import annotations

import json
from collections import Counter
from dataclasses import dataclass
from pathlib import Path

import numpy as np

from .palette import PaintColor

COLLECTION_PATH = Path(__file__).resolve().parents[2] / "user_data" / "collection.json"


def load(path: Path = COLLECTION_PATH, catalog: list[PaintColor] | None = None) -> set[str]:
    path = Path(path)
    if not path.exists():
        return set()
    stored = set(json.loads(path.read_text(encoding="utf-8")).get("owned", []))
    if catalog is None:
        return stored
    codes = {p.code for p in catalog}
    name_counts = Counter(p.name for p in catalog)
    by_name = {p.name: p.code for p in catalog}
    result: set[str] = set()
    for entry in stored:
        if entry in codes:
            result.add(entry)
        elif name_counts.get(entry) == 1:
            result.add(by_name[entry])
        # otherwise: unknown or ambiguous legacy name -> drop
    return result


def save(owned: set[str], path: Path = COLLECTION_PATH) -> None:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps({"owned": sorted(owned)}, indent=2), encoding="utf-8")


@dataclass(frozen=True)
class SlotStatus:
    paint: PaintColor
    owned: bool
    nearest_owned: PaintColor | None


def annotate_ownership(palette: list[PaintColor], owned: list[PaintColor]) -> list[SlotStatus]:
    owned_names = {p.name for p in owned}
    slots: list[SlotStatus] = []
    for paint in palette:
        is_owned = paint.name in owned_names
        nearest = None
        # nearest_owned: closest owned paint by Euclidean RGB distance.
        # COMPUTED FOR THE #3 (mixing) SEAM — do not surface in the UI.
        if not is_owned and owned:
            nearest = min(owned, key=lambda o: float(np.linalg.norm(o.rgb - paint.rgb)))
        slots.append(SlotStatus(paint=paint, owned=is_owned, nearest_owned=nearest))
    return slots
