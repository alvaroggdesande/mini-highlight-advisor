from __future__ import annotations

import json
from collections import Counter
from dataclasses import dataclass
from pathlib import Path

import numpy as np

from .palette import PaintColor

COLLECTION_PATH = Path(__file__).resolve().parents[2] / "user_data" / "collection.json"


def _validate_codes(stored: set[str], catalog: list[PaintColor] | None) -> set[str]:
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
    return result


def load(path: Path = COLLECTION_PATH, catalog: list[PaintColor] | None = None) -> set[str]:
    path = Path(path)
    if not path.exists():
        return set()
    stored = set(json.loads(path.read_text(encoding="utf-8")).get("owned", []))
    return _validate_codes(stored, catalog)


def save(owned: set[str], path: Path = COLLECTION_PATH) -> None:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps({"owned": sorted(owned)}, indent=2), encoding="utf-8")


def export_to_json_bytes(owned: set[str]) -> bytes:
    return json.dumps({"owned": sorted(owned)}, indent=2).encode("utf-8")


def import_from_json_bytes(data: bytes, catalog: list[PaintColor] | None = None) -> set[str]:
    stored = set(json.loads(data.decode("utf-8")).get("owned", []))
    return _validate_codes(stored, catalog)


@dataclass(frozen=True)
class SlotStatus:
    paint: PaintColor
    owned: bool
    nearest_owned: PaintColor | None


def nearest_paint(target_rgb: np.ndarray, candidates: list[PaintColor]) -> PaintColor | None:
    if not candidates:
        return None
    return min(candidates, key=lambda c: float(np.linalg.norm(c.rgb - target_rgb)))


def annotate_ownership(palette: list[PaintColor], owned: list[PaintColor]) -> list[SlotStatus]:
    owned_names = {p.name for p in owned}
    slots: list[SlotStatus] = []
    for paint in palette:
        is_owned = paint.name in owned_names
        nearest = None if is_owned else nearest_paint(paint.rgb, owned)
        slots.append(SlotStatus(paint=paint, owned=is_owned, nearest_owned=nearest))
    return slots
