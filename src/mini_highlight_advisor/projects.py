# src/mini_highlight_advisor/projects.py
from __future__ import annotations

import json
import os
import re
import shutil
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
from PIL import Image

from .palette import PaintColor
from .region_state import RegionBook
from .regions import Region
from .schemes import Scheme

PROJECTS_DIR = Path(__file__).resolve().parents[2] / "user_data" / "projects"

SCHEMA_VERSION = 3


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


def _scheme_to_dict(s: Scheme) -> dict:
    return {"name": s.name, "anchor": s.anchor,
            "palettes": {region: _palette_to_dicts(pal)
                         for region, pal in s.palettes.items()}}


def _scheme_from_dict(d: dict) -> Scheme:
    return Scheme(name=d["name"], anchor=d.get("anchor"),
                  palettes={region: _palette_from_dicts(items)
                            for region, items in d["palettes"].items()})


def _write_mask(path: Path, mask: np.ndarray) -> None:
    Image.fromarray(np.asarray(mask, dtype=bool)).save(path)


def _read_mask(path: Path) -> np.ndarray:
    with Image.open(path) as im:
        return np.asarray(im).astype(bool)


@dataclass(frozen=True)
class LoadedProject:
    paints_pool: list[str]
    active_angle: int
    angles: list[AngleData]
    schemes: list[Scheme]


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


@dataclass(frozen=True)
class AngleData:
    label: str
    photo_bytes: bytes
    photo_suffix: str
    book: RegionBook
    settings: ProjectSettings


def _write_angle(project_dir: Path, idx: int, a: AngleData) -> dict:
    angle_dir = Path(project_dir) / f"angle_{idx:02d}"
    angle_dir.mkdir(parents=True, exist_ok=True)
    photo_file = f"photo{a.photo_suffix}"
    (angle_dir / photo_file).write_bytes(a.photo_bytes)
    drawn = []
    for i, r in enumerate(a.book.drawn):
        mask_file = f"region_{i:02d}.png"
        _write_mask(angle_dir / mask_file, r.mask)
        drawn.append({"name": r.name, "palette": _palette_to_dicts(r.palette),
                      "coverage": list(r.coverage), "mask_file": mask_file,
                      "material": r.material})
    return {
        "label": a.label,
        "photo_file": photo_file,
        "settings": _settings_to_dict(a.settings),
        "book": {"whole": {"palette": _palette_to_dicts(a.book.whole_palette),
                           "coverage": list(a.book.whole_coverage),
                           "material": a.book.whole_material},
                 "drawn": drawn, "selected": a.book.selected},
    }


def _read_angle(project_dir: Path, idx: int, entry: dict) -> AngleData:
    angle_dir = Path(project_dir) / f"angle_{idx:02d}"
    photo_bytes = (angle_dir / entry["photo_file"]).read_bytes()
    photo_suffix = Path(entry["photo_file"]).suffix
    b = entry["book"]
    drawn = [
        Region(name=d["name"], mask=_read_mask(angle_dir / d["mask_file"]),
               palette=_palette_from_dicts(d["palette"]), coverage=list(d["coverage"]),
               material=d.get("material", "matte"))
        for d in b["drawn"]
    ]
    book = RegionBook(whole_palette=_palette_from_dicts(b["whole"]["palette"]),
                      whole_coverage=list(b["whole"]["coverage"]),
                      whole_material=b["whole"].get("material", "matte"),
                      drawn=drawn, selected=b["selected"])
    return AngleData(label=entry["label"], photo_bytes=photo_bytes,
                     photo_suffix=photo_suffix, book=book,
                     settings=_settings_from_dict(entry["settings"]))


def save_project(name, paints_pool, active_angle, angles, schemes=None,
                 root: Path = PROJECTS_DIR, _now: str | None = None) -> str:
    slug = slugify(name)
    root = Path(root)
    root.mkdir(parents=True, exist_ok=True)
    dest = root / slug
    tmp = root / f".tmp-{slug}"
    shutil.rmtree(tmp, ignore_errors=True)
    tmp.mkdir(parents=True)

    angle_entries = [_write_angle(tmp, i, a) for i, a in enumerate(angles)]
    now = _now or _now_iso()
    manifest = {
        "schema_version": SCHEMA_VERSION, "name": name, "slug": slug,
        "created_at": now, "updated_at": now,
        "paints_pool": list(paints_pool), "active_angle": active_angle,
        "angles": angle_entries,
        "schemes": [_scheme_to_dict(s) for s in (schemes or [])],
    }
    (tmp / "manifest.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    shutil.rmtree(dest, ignore_errors=True)
    os.replace(tmp, dest)
    return slug


def list_projects(root: Path = PROJECTS_DIR) -> list[ProjectMeta]:
    root = Path(root)
    if not root.exists():
        return []
    metas = []
    for child in root.iterdir():
        if not child.is_dir() or child.name.startswith(".tmp-"):
            continue
        mpath = child / "manifest.json"
        if not mpath.exists():
            continue
        try:
            m = json.loads(mpath.read_text(encoding="utf-8"))
            metas.append(ProjectMeta(slug=m["slug"], name=m["name"],
                                     updated_at=m["updated_at"]))
        except (json.JSONDecodeError, KeyError):
            continue
    return sorted(metas, key=lambda x: x.updated_at, reverse=True)


def delete_project(slug: str, root: Path = PROJECTS_DIR) -> None:
    shutil.rmtree(Path(root) / slug, ignore_errors=True)


def _adapt_v1(m: dict, project_dir: Path) -> LoadedProject:
    photo_bytes = (project_dir / m["photo_file"]).read_bytes()
    photo_suffix = Path(m["photo_file"]).suffix
    b = m["book"]
    drawn = [
        Region(name=d["name"], mask=_read_mask(project_dir / d["mask_file"]),
               palette=_palette_from_dicts(d["palette"]), coverage=list(d["coverage"]),
               material=d.get("material", "matte"))
        for d in b["drawn"]
    ]
    book = RegionBook(whole_palette=_palette_from_dicts(b["whole"]["palette"]),
                      whole_coverage=list(b["whole"]["coverage"]),
                      whole_material=b["whole"].get("material", "matte"),
                      drawn=drawn, selected=b["selected"])
    angle = AngleData(label=m.get("name", "angle 1"), photo_bytes=photo_bytes,
                      photo_suffix=photo_suffix, book=book,
                      settings=_settings_from_dict(m["settings"]))
    return LoadedProject(paints_pool=[], active_angle=0, angles=[angle], schemes=[])


def load_project(slug: str, root: Path = PROJECTS_DIR) -> LoadedProject:
    mpath = _manifest_path(Path(root), slug)
    if not mpath.exists():
        raise FileNotFoundError(f"no project manifest at {mpath}")
    m = json.loads(mpath.read_text(encoding="utf-8"))
    project_dir = mpath.parent
    if m.get("schema_version", 1) < 2:
        return _adapt_v1(m, project_dir)
    angles = [_read_angle(project_dir, i, e) for i, e in enumerate(m["angles"])]
    active = m.get("active_angle", 0)
    if angles:
        active = min(max(0, active), len(angles) - 1)
    else:
        active = 0
    schemes = []
    for d in m.get("schemes", []):
        try:
            schemes.append(_scheme_from_dict(d))
        except (KeyError, TypeError):
            continue
    return LoadedProject(paints_pool=list(m.get("paints_pool", [])),
                         active_angle=active, angles=angles, schemes=schemes)


def next_active_index(active: int, removed: int, count_before: int) -> int:
    """New active index after removing `removed` from a list of size `count_before`."""
    if count_before <= 1:
        return 0
    if active > removed:
        return active - 1
    if active == removed:
        return max(0, removed - 1)
    return active
