from __future__ import annotations

import json
from pathlib import Path

from .palette import PaintColor

CATALOG_PATH = Path(__file__).parent / "data" / "vallejo_paints.json"


def load_catalog(path: Path = CATALOG_PATH) -> list[PaintColor]:
    data = json.loads(Path(path).read_text(encoding="utf-8"))
    return [
        PaintColor(
            name=p["name"],
            hex=p["hex"],
            brand=p.get("brand"),
            paint_range=p.get("range"),
        )
        for p in data["paints"]
    ]


def find_by_name(catalog: list[PaintColor], name: str) -> PaintColor | None:
    for p in catalog:
        if p.name == name:
            return p
    return None
