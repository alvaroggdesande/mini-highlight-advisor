from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

_SAMPLES_DIR = Path(__file__).parent / "data" / "samples"
_PHOTOS_DIR = _SAMPLES_DIR / "photos"
_PROJECTS_DIR = _SAMPLES_DIR / "projects"
_PHOTO_EXTS = {".png", ".jpg", ".jpeg"}


@dataclass(frozen=True)
class SamplePhoto:
    name: str
    path: Path


@dataclass(frozen=True)
class SampleProject:
    name: str
    path: Path


def _stem_to_name(stem: str) -> str:
    return stem.replace("-", " ").replace("_", " ").title()


def list_photos() -> list[SamplePhoto]:
    if not _PHOTOS_DIR.exists():
        return []
    return [
        SamplePhoto(name=_stem_to_name(p.stem), path=p)
        for p in sorted(_PHOTOS_DIR.iterdir())
        if p.suffix.lower() in _PHOTO_EXTS
    ]


def list_projects() -> list[SampleProject]:
    if not _PROJECTS_DIR.exists():
        return []
    return [
        SampleProject(name=_stem_to_name(p.stem), path=p)
        for p in sorted(_PROJECTS_DIR.iterdir())
        if p.suffix.lower() == ".json"
    ]
