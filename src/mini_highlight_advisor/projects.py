# src/mini_highlight_advisor/projects.py
from __future__ import annotations

import json
import re
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

from .palette import PaintColor
from .region_state import RegionBook

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


@dataclass(frozen=True)
class LoadedProject:
    photo_bytes: bytes
    photo_suffix: str
    book: RegionBook
    settings: ProjectSettings


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _manifest_path(root: Path, slug: str) -> Path:
    return Path(root) / slug / "manifest.json"


def _settings_to_dict(s: ProjectSettings) -> dict:
    return {"n": s.n, "edge_hl": s.edge_hl, "edge_extreme": s.edge_extreme,
            "edge_sens": s.edge_sens, "relief_cap": s.relief_cap,
            "per_region_norm": s.per_region_norm}


def _settings_from_dict(d: dict) -> ProjectSettings:
    return ProjectSettings(n=d["n"], edge_hl=d["edge_hl"], edge_extreme=d["edge_extreme"],
                           edge_sens=d["edge_sens"], relief_cap=d["relief_cap"],
                           per_region_norm=d["per_region_norm"])


def save_project(name, photo_bytes, photo_suffix, book, settings,
                 root: Path = PROJECTS_DIR, _now: str | None = None) -> str:
    slug = slugify(name)
    dest = Path(root) / slug
    dest.mkdir(parents=True, exist_ok=True)  # Task 4 replaces this with an atomic write
    photo_file = f"photo{photo_suffix}"
    (dest / photo_file).write_bytes(photo_bytes)
    manifest = {
        "schema_version": SCHEMA_VERSION,
        "name": name,
        "slug": slug,
        "created_at": _now or _now_iso(),
        "updated_at": _now or _now_iso(),
        "photo_file": photo_file,
        "settings": _settings_to_dict(settings),
        "book": {
            "whole": {"palette": _palette_to_dicts(book.whole_palette),
                      "coverage": list(book.whole_coverage)},
            "drawn": [],   # Task 3 fills this
            "selected": book.selected,
        },
    }
    (dest / "manifest.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    return slug


def load_project(slug: str, root: Path = PROJECTS_DIR) -> LoadedProject:
    mpath = _manifest_path(Path(root), slug)
    if not mpath.exists():
        raise FileNotFoundError(f"no project manifest at {mpath}")
    m = json.loads(mpath.read_text(encoding="utf-8"))
    photo_file = m["photo_file"]
    photo_bytes = (mpath.parent / photo_file).read_bytes()
    photo_suffix = Path(photo_file).suffix
    b = m["book"]
    book = RegionBook(
        whole_palette=_palette_from_dicts(b["whole"]["palette"]),
        whole_coverage=list(b["whole"]["coverage"]),
        drawn=[],   # Task 3 fills this
        selected=b["selected"],
    )
    return LoadedProject(photo_bytes, photo_suffix, book, _settings_from_dict(m["settings"]))
