from __future__ import annotations

import json
import re
from pathlib import Path

from .palette import PaintColor

CATALOG_PATH = Path(__file__).parent / "data" / "vallejo_paints.json"

_HEX_RE = re.compile(r"^#[0-9a-fA-F]{6}$")


def validate_catalog(paints: list[dict]) -> None:
    """Raise ValueError on the first invalid entry; return None if all valid.

    Per entry: required keys (code, name, hex) present, hex well-formed,
    code unique. Names MAY repeat across ranges. Errors identify the entry.
    """
    seen_codes: set[str] = set()
    for i, p in enumerate(paints):
        for key in ("code", "name", "hex"):
            if key not in p:
                present = p.get("name") or p.get("code")
                label = f" ({present!r})" if present is not None else ""
                raise ValueError(
                    f"Catalogue entry at index {i}{label} is missing required key {key!r}."
                )
        code, name, hexv = p["code"], p["name"], p["hex"]
        if not _HEX_RE.match(hexv):
            raise ValueError(
                f"Catalogue paint {name!r} ({code}) has invalid hex {hexv!r}; expected #rrggbb."
            )
        if code in seen_codes:
            raise ValueError(f"Duplicate catalogue paint code {code!r} (name {name!r}).")
        seen_codes.add(code)


def load_catalog(path: Path = CATALOG_PATH) -> list[PaintColor]:
    data = json.loads(Path(path).read_text(encoding="utf-8"))
    paints = data["paints"]
    validate_catalog(paints)
    return [
        PaintColor(
            name=p["name"],
            hex=p["hex"],
            brand=p.get("brand"),
            paint_range=p.get("range"),
            code=p.get("code", ""),
        )
        for p in paints
    ]


def find_by_name(catalog: list[PaintColor], name: str) -> PaintColor | None:
    for p in catalog:
        if p.name == name:
            return p
    return None


def find_by_code(catalog: list[PaintColor], code: str) -> PaintColor | None:
    for p in catalog:
        if p.code == code:
            return p
    return None
