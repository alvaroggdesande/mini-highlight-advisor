# src/mini_highlight_advisor/projects.py
from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path

from .palette import PaintColor

PROJECTS_DIR = Path(__file__).resolve().parents[2] / "user_data" / "projects"

SCHEMA_VERSION = 1


@dataclass(frozen=True)
class ProjectSettings:
    n: int
    edge_hl: bool
    edge_extreme: bool
    edge_sens: float
    relief_cap: bool
    per_region_norm: bool


@dataclass(frozen=True)
class ProjectMeta:
    slug: str
    name: str
    updated_at: str


def slugify(name: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", name.strip().lower()).strip("-")
    if not slug:
        raise ValueError("project name must contain at least one letter or digit")
    return slug


def _palette_to_dicts(palette: list[PaintColor]) -> list[dict]:
    return [
        {"name": p.name, "hex": p.hex, "brand": p.brand,
         "paint_range": p.paint_range, "code": p.code, "finish": p.finish}
        for p in palette
    ]


def _palette_from_dicts(items: list[dict]) -> list[PaintColor]:
    return [
        PaintColor(name=d["name"], hex=d["hex"], brand=d.get("brand"),
                   paint_range=d.get("paint_range"), code=d.get("code", ""),
                   finish=d.get("finish", "matte"))
        for d in items
    ]
