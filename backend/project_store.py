from __future__ import annotations

import base64
import json
import os
import re
import shutil
from datetime import datetime, timezone
from pathlib import Path

PHOTOS_DIR = Path(__file__).resolve().parents[1] / "user_data" / "photos"
PROJECTS_DIR = Path(__file__).resolve().parents[1] / "user_data" / "projects"
SCHEMA_VERSION = 6


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def slugify(name: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", name.strip().lower()).strip("-")
    if not slug:
        raise ValueError("project name must contain at least one letter or digit")
    return slug


# ---------------------------------------------------------------------------
# Photo store
# ---------------------------------------------------------------------------

def save_photo(photo_id: str, suffix: str, data: bytes) -> None:
    PHOTOS_DIR.mkdir(parents=True, exist_ok=True)
    (PHOTOS_DIR / f"{photo_id}{suffix}").write_bytes(data)


def load_photo_bytes(photo_id: str) -> tuple[bytes, str] | None:
    if not PHOTOS_DIR.exists():
        return None
    for path in PHOTOS_DIR.iterdir():
        if path.stem == photo_id:
            return path.read_bytes(), path.suffix
    return None


# ---------------------------------------------------------------------------
# Project CRUD
# ---------------------------------------------------------------------------

def list_projects() -> list[dict]:
    if not PROJECTS_DIR.exists():
        return []
    results = []
    for child in PROJECTS_DIR.iterdir():
        if not child.is_dir() or child.name.startswith(".tmp-"):
            continue
        mpath = child / "manifest.json"
        if not mpath.exists():
            continue
        try:
            m = json.loads(mpath.read_text(encoding="utf-8"))
            if m.get("schema_version") == SCHEMA_VERSION:
                results.append({
                    "slug": m["slug"],
                    "name": m["name"],
                    "updated_at": m["updated_at"],
                })
        except (json.JSONDecodeError, KeyError):
            continue
    return sorted(results, key=lambda x: x["updated_at"], reverse=True)


def save_project(name: str, manifest: dict) -> str:
    slug = slugify(name)
    PROJECTS_DIR.mkdir(parents=True, exist_ok=True)
    dest = PROJECTS_DIR / slug
    tmp = PROJECTS_DIR / f".tmp-{slug}"
    shutil.rmtree(tmp, ignore_errors=True)
    tmp.mkdir(parents=True)
    full = {**manifest, "slug": slug, "updated_at": _now_iso()}
    (tmp / "manifest.json").write_text(json.dumps(full, indent=2), encoding="utf-8")
    shutil.rmtree(dest, ignore_errors=True)
    os.replace(tmp, dest)
    return slug


def load_project(slug: str) -> dict:
    mpath = PROJECTS_DIR / slug / "manifest.json"
    if not mpath.exists():
        raise FileNotFoundError(f"no project manifest at {mpath}")
    m = json.loads(mpath.read_text(encoding="utf-8"))
    if m.get("schema_version") != SCHEMA_VERSION:
        raise ValueError(f"unsupported schema version {m.get('schema_version')!r}")
    return m


def delete_project(slug: str) -> None:
    shutil.rmtree(PROJECTS_DIR / slug, ignore_errors=True)


# ---------------------------------------------------------------------------
# JSON blob (self-contained download/upload)
# ---------------------------------------------------------------------------

def project_to_blob(slug: str) -> bytes:
    manifest = load_project(slug)
    photos: dict[str, dict] = {}
    for angle in manifest.get("angles", []):
        photo_id = angle.get("photo_id")
        if photo_id and photo_id not in photos:
            result = load_photo_bytes(photo_id)
            if result:
                data, suffix = result
                photos[photo_id] = {
                    "suffix": suffix,
                    "data_b64": base64.b64encode(data).decode("ascii"),
                }
    blob = {**manifest, "photos": photos}
    return json.dumps(blob, indent=2).encode("utf-8")


def project_from_blob(data: bytes) -> tuple[dict, dict[str, tuple[str, bytes]]]:
    """Parse a blob.  Returns (manifest_without_photos, {photo_id: (suffix, bytes)})."""
    blob = json.loads(data.decode("utf-8"))
    photos_raw = blob.pop("photos", {})
    photos = {
        pid: (info["suffix"], base64.b64decode(info["data_b64"]))
        for pid, info in photos_raw.items()
    }
    return blob, photos
