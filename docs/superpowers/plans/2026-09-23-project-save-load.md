# Project Save/Load Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add project save/load to the React app — server-side list/save/load/delete plus JSON blob export/import — so users can persist named projects across sessions.

**Architecture:** Photos are written to `user_data/photos/{photo_id}{suffix}` on every upload (approach A); the v6 manifest is the Zustand store shape stored verbatim as JSON under `user_data/projects/{slug}/manifest.json`. A collapsible `ProjectLibrary` panel sits above the uploader/studio. Load warms the shading cache so `useAnalyze` fires immediately on hydration.

**Tech Stack:** Python 3.11, FastAPI, Pydantic v2, Zustand, React 18, TypeScript, Vitest, pytest

**Spec:** `docs/superpowers/specs/2026-09-22-react-fastapi-migration-design.md` §5–§6

## Global Constraints

- Branch: `feat/project-save-load` (never commit to `main` directly)
- Schema version for React manifests: `6` (distinct from Streamlit's v5 in `src/mini_highlight_advisor/projects.py` — do not modify that file)
- `user_data/photos/` and `user_data/projects/` are the persistence roots; create them on first write
- All API routes under `/api/projects`; keep consistency with snake_case JSON (Python side) ↔ camelCase store (TypeScript side)
- No npm/pip installs — all dependencies already present
- Run backend tests from repo root: `.venv/Scripts/python -m pytest backend/tests/ -v`
- Run frontend tests from `web/`: `npm test -- --run`

---

### Task 1: `backend/project_store.py` — photo + project persistence

**Files:**
- Create: `backend/project_store.py`
- Create: `backend/tests/test_project_store.py`

**Interfaces:**
- Produces:
  - `save_photo(photo_id: str, suffix: str, data: bytes) -> None`
  - `load_photo_bytes(photo_id: str) -> tuple[bytes, str] | None`  ← `(bytes, suffix)` or None
  - `slugify(name: str) -> str`  ← raises `ValueError` on empty result
  - `list_projects() -> list[dict]`  ← `[{slug, name, updated_at}]` sorted newest-first
  - `save_project(name: str, manifest: dict) -> str`  ← returns slug; atomic write via tmp dir
  - `load_project(slug: str) -> dict`  ← raises `FileNotFoundError` if missing; raises `ValueError` if schema_version != 6
  - `delete_project(slug: str) -> None`
  - `project_to_blob(slug: str) -> bytes`  ← self-contained JSON with base64-embedded photos
  - `project_from_blob(data: bytes) -> tuple[dict, dict[str, tuple[str, bytes]]]`  ← `(manifest_dict, {photo_id: (suffix, bytes)})`

- [ ] **Step 1: Write `backend/tests/test_project_store.py`**

```python
import io
import json
import numpy as np
import pytest
from PIL import Image
from backend import project_store as ps


def _png_bytes():
    arr = (np.random.default_rng(42).integers(0, 255, (32, 24, 3))).astype("uint8")
    buf = io.BytesIO()
    Image.fromarray(arr).save(buf, format="PNG")
    return buf.getvalue()


@pytest.fixture(autouse=True)
def tmp_store(tmp_path, monkeypatch):
    monkeypatch.setattr(ps, "PHOTOS_DIR", tmp_path / "photos")
    monkeypatch.setattr(ps, "PROJECTS_DIR", tmp_path / "projects")


def _minimal_manifest(name="Test", photo_id="ph001"):
    return {
        "schema_version": 6,
        "name": name,
        "active_angle": 0,
        "angles": [
            {
                "id": "a1",
                "label": "angle 1",
                "photo_id": photo_id,
                "book": {
                    "whole": {"palette": [], "coverage": [], "material": "matte"},
                    "drawn": [],
                    "selected": 0,
                    "schemes": [],
                },
                "settings": {
                    "edge_hl": True, "edge_extreme": False, "edge_sens": 0.5,
                    "relief_cap": True, "per_region_norm": False,
                },
            }
        ],
    }


# ── photo store ──────────────────────────────────────────────────────────────

def test_save_and_load_photo():
    ps.save_photo("abc123", ".jpg", b"fake-jpeg")
    result = ps.load_photo_bytes("abc123")
    assert result == (b"fake-jpeg", ".jpg")


def test_load_photo_missing():
    assert ps.load_photo_bytes("nonexistent") is None


def test_load_photo_missing_dir():
    # PHOTOS_DIR doesn't exist yet — must not crash
    assert ps.load_photo_bytes("anything") is None


def test_save_photo_twice_overwrites():
    ps.save_photo("x", ".png", b"v1")
    ps.save_photo("x", ".png", b"v2")
    assert ps.load_photo_bytes("x") == (b"v2", ".png")


# ── slugify ───────────────────────────────────────────────────────────────────

def test_slugify_normal():
    assert ps.slugify("My Cool Mini") == "my-cool-mini"


def test_slugify_strips_special():
    assert ps.slugify("  Héros!!  ") == "h-ros"


def test_slugify_empty_raises():
    with pytest.raises(ValueError):
        ps.slugify("!!!")


def test_slugify_empty_string_raises():
    with pytest.raises(ValueError):
        ps.slugify("")


# ── project CRUD ──────────────────────────────────────────────────────────────

def test_save_and_list_project():
    slug = ps.save_project("My Mini", _minimal_manifest("My Mini"))
    assert slug == "my-mini"
    projects = ps.list_projects()
    assert len(projects) == 1
    assert projects[0]["slug"] == "my-mini"
    assert projects[0]["name"] == "My Mini"
    assert "updated_at" in projects[0]


def test_list_projects_empty():
    assert ps.list_projects() == []


def test_list_skips_non_v6():
    import os, json as _json
    ps.PROJECTS_DIR.mkdir(parents=True, exist_ok=True)
    old_dir = ps.PROJECTS_DIR / "old-project"
    old_dir.mkdir()
    (old_dir / "manifest.json").write_text(
        _json.dumps({"schema_version": 5, "name": "old", "slug": "old-project", "updated_at": "2020-01-01T00:00:00Z"}),
        encoding="utf-8",
    )
    assert ps.list_projects() == []


def test_save_overwrites_existing():
    ps.save_project("proj", _minimal_manifest("proj"))
    ps.save_project("proj", _minimal_manifest("proj"))  # second save
    assert len(ps.list_projects()) == 1


def test_load_project():
    ps.save_project("Load Me", _minimal_manifest("Load Me"))
    m = ps.load_project("load-me")
    assert m["name"] == "Load Me"
    assert m["slug"] == "load-me"
    assert m["schema_version"] == 6


def test_load_project_not_found():
    with pytest.raises(FileNotFoundError):
        ps.load_project("nonexistent")


def test_load_project_wrong_version():
    import json as _json
    ps.PROJECTS_DIR.mkdir(parents=True, exist_ok=True)
    d = ps.PROJECTS_DIR / "old"
    d.mkdir()
    (d / "manifest.json").write_text(
        _json.dumps({"schema_version": 5, "name": "old", "slug": "old", "updated_at": ""}),
        encoding="utf-8",
    )
    with pytest.raises(ValueError):
        ps.load_project("old")


def test_delete_project():
    ps.save_project("Del", _minimal_manifest("Del"))
    ps.delete_project("del")
    assert ps.list_projects() == []


def test_delete_nonexistent_is_silent():
    ps.delete_project("ghost")  # must not raise


# ── blob round-trip ───────────────────────────────────────────────────────────

def test_project_to_blob_embeds_photo():
    png = _png_bytes()
    ps.save_photo("ph001", ".png", png)
    ps.save_project("Blob Test", _minimal_manifest("Blob Test", photo_id="ph001"))
    blob = ps.project_to_blob("blob-test")
    data = json.loads(blob)
    assert data["name"] == "Blob Test"
    assert "photos" in data
    assert "ph001" in data["photos"]
    assert data["photos"]["ph001"]["suffix"] == ".png"


def test_project_from_blob_roundtrip():
    png = _png_bytes()
    ps.save_photo("ph001", ".png", png)
    ps.save_project("RT", _minimal_manifest("RT", photo_id="ph001"))
    blob = ps.project_to_blob("rt")

    manifest, photos = ps.project_from_blob(blob)
    assert manifest["name"] == "RT"
    assert "photos" not in manifest          # stripped from manifest
    assert "ph001" in photos
    suffix, photo_bytes = photos["ph001"]
    assert suffix == ".png"
    assert photo_bytes == png


def test_project_to_blob_missing_photo_skips_gracefully():
    # photo_id in manifest but no file on disk → blob produced, photos key absent for that id
    ps.save_project("No Photo", _minimal_manifest("No Photo", photo_id="missing"))
    blob = ps.project_to_blob("no-photo")
    data = json.loads(blob)
    assert "missing" not in data.get("photos", {})
```

- [ ] **Step 2: Run tests to verify they fail**

```
.venv\Scripts\python -m pytest backend/tests/test_project_store.py -v
```
Expected: `ModuleNotFoundError: No module named 'backend.project_store'`

- [ ] **Step 3: Create `backend/project_store.py`**

```python
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
```

- [ ] **Step 4: Run tests — expect all pass**

```
.venv\Scripts\python -m pytest backend/tests/test_project_store.py -v
```
Expected: all green.

- [ ] **Step 5: Commit**

```
git checkout -b feat/project-save-load
git add backend/project_store.py backend/tests/test_project_store.py
git commit -m "feat: add backend/project_store.py — v6 photo + project persistence"
```

---

### Task 2: Backend routes — photo persistence on upload + 6 project endpoints

**Files:**
- Modify: `backend/schemas.py` (add `SaveProjectRequest`)
- Modify: `backend/main.py` (persist photo on upload; add project routes)
- Create: `backend/tests/test_projects_api.py`

**Interfaces:**
- Consumes: all functions from `backend/project_store` (Task 1)
- Produces HTTP routes:
  - `POST /api/photo` now persists photo bytes to disk (side effect added)
  - `GET /api/projects` → `{"projects": [{slug, name, updated_at}]}`
  - `PUT /api/projects` body `{name, active_angle, angles}` → `{slug, name, updated_at}`
  - `GET /api/projects/{slug}` → full manifest dict (cache warmed)
  - `DELETE /api/projects/{slug}` → `{"ok": true}`
  - `GET /api/projects/{slug}/download` → JSON blob attachment
  - `POST /api/projects/upload` multipart `file` → full manifest dict

- [ ] **Step 1: Write `backend/tests/test_projects_api.py`**

```python
import io
import json

import numpy as np
import pytest
from fastapi.testclient import TestClient
from PIL import Image

from backend import project_store
from backend.main import app

_client = TestClient(app)


def _png_bytes():
    arr = (np.random.default_rng(99).integers(0, 255, (32, 24, 3))).astype("uint8")
    buf = io.BytesIO()
    Image.fromarray(arr).save(buf, format="PNG")
    return buf.getvalue()


@pytest.fixture(autouse=True)
def patch_store(tmp_path, monkeypatch):
    monkeypatch.setattr(project_store, "PHOTOS_DIR", tmp_path / "photos")
    monkeypatch.setattr(project_store, "PROJECTS_DIR", tmp_path / "projects")


def _upload() -> str:
    r = _client.post("/api/photo", files={"file": ("m.png", _png_bytes(), "image/png")})
    assert r.status_code == 200
    return r.json()["photo_id"]


def _angle(photo_id: str) -> dict:
    return {
        "id": "a1",
        "label": "angle 1",
        "photo_id": photo_id,
        "book": {
            "whole": {"palette": [], "coverage": [], "material": "matte"},
            "drawn": [],
            "selected": 0,
            "schemes": [],
        },
        "settings": {
            "edge_hl": True, "edge_extreme": False, "edge_sens": 0.5,
            "relief_cap": True, "per_region_norm": False,
        },
    }


# ── photo upload persists to disk ─────────────────────────────────────────────

def test_upload_persists_photo_to_disk():
    pid = _upload()
    result = project_store.load_photo_bytes(pid)
    assert result is not None
    data_bytes, suffix = result
    assert suffix == ".png"
    assert len(data_bytes) > 0


# ── list ──────────────────────────────────────────────────────────────────────

def test_list_projects_empty():
    r = _client.get("/api/projects")
    assert r.status_code == 200
    assert r.json() == {"projects": []}


# ── save ──────────────────────────────────────────────────────────────────────

def test_save_project_returns_slug():
    pid = _upload()
    r = _client.put("/api/projects", json={"name": "My Mini", "active_angle": 0, "angles": [_angle(pid)]})
    assert r.status_code == 200
    body = r.json()
    assert body["slug"] == "my-mini"
    assert body["name"] == "My Mini"
    assert "updated_at" in body


def test_save_project_appears_in_list():
    pid = _upload()
    _client.put("/api/projects", json={"name": "Listed", "active_angle": 0, "angles": [_angle(pid)]})
    r = _client.get("/api/projects")
    projects = r.json()["projects"]
    assert len(projects) == 1
    assert projects[0]["slug"] == "listed"


def test_save_project_missing_photo_id_returns_409():
    r = _client.put("/api/projects", json={
        "name": "Bad", "active_angle": 0,
        "angles": [{"id": "a1", "label": "angle 1", "photo_id": "deadbeef0000dead",
                    "book": {}, "settings": {}}],
    })
    assert r.status_code == 409


def test_save_project_angle_without_photo_id_is_ok():
    # angle with no photo yet (e.g. not uploaded) — server skips validation
    r = _client.put("/api/projects", json={
        "name": "NoPhoto", "active_angle": 0,
        "angles": [{"id": "a1", "label": "angle 1",
                    "book": {}, "settings": {}}],
    })
    assert r.status_code == 200


# ── load ──────────────────────────────────────────────────────────────────────

def test_load_project_returns_manifest():
    pid = _upload()
    _client.put("/api/projects", json={"name": "Load Me", "active_angle": 0, "angles": [_angle(pid)]})
    r = _client.get("/api/projects/load-me")
    assert r.status_code == 200
    body = r.json()
    assert body["name"] == "Load Me"
    assert body["slug"] == "load-me"
    assert len(body["angles"]) == 1
    assert body["angles"][0]["photo_id"] == pid


def test_load_project_not_found():
    r = _client.get("/api/projects/no-such-project")
    assert r.status_code == 404


# ── delete ────────────────────────────────────────────────────────────────────

def test_delete_project():
    pid = _upload()
    _client.put("/api/projects", json={"name": "Delete Me", "active_angle": 0, "angles": [_angle(pid)]})
    r = _client.delete("/api/projects/delete-me")
    assert r.status_code == 200
    assert _client.get("/api/projects/delete-me").status_code == 404


# ── download / upload blob ────────────────────────────────────────────────────

def test_download_project_blob():
    pid = _upload()
    _client.put("/api/projects", json={"name": "Download Me", "active_angle": 0, "angles": [_angle(pid)]})
    r = _client.get("/api/projects/download-me/download")
    assert r.status_code == 200
    assert r.headers["content-type"].startswith("application/json")
    data = json.loads(r.content)
    assert data["name"] == "Download Me"
    assert pid in data.get("photos", {})


def test_download_missing_project_404():
    r = _client.get("/api/projects/ghost/download")
    assert r.status_code == 404


def test_upload_blob_restores_project():
    pid = _upload()
    _client.put("/api/projects", json={"name": "Round Trip", "active_angle": 0, "angles": [_angle(pid)]})
    blob = _client.get("/api/projects/round-trip/download").content

    # delete and re-upload
    _client.delete("/api/projects/round-trip")
    r = _client.post("/api/projects/upload",
                     files={"file": ("round-trip.json", blob, "application/json")})
    assert r.status_code == 200
    body = r.json()
    assert body["name"] == "Round Trip"
    assert body["slug"] == "round-trip"
    assert len(body["angles"]) == 1


def test_upload_invalid_blob_422():
    r = _client.post("/api/projects/upload",
                     files={"file": ("bad.json", b"not json", "application/json")})
    assert r.status_code == 422
```

- [ ] **Step 2: Run to verify they fail**

```
.venv\Scripts\python -m pytest backend/tests/test_projects_api.py -v
```
Expected: most fail (routes missing; `test_upload_persists_photo_to_disk` fails because the side effect isn't in `upload_photo` yet).

- [ ] **Step 3: Add `SaveProjectRequest` to `backend/schemas.py`**

Append to the end of `backend/schemas.py`:

```python
class SaveProjectRequest(BaseModel):
    name: str
    active_angle: int = 0
    angles: list[dict] = Field(default_factory=list)
```

- [ ] **Step 4: Add photo persistence + project routes to `backend/main.py`**

**4a — Add import** at the top of `backend/main.py` (after existing imports):

```python
from backend import project_store
from backend.schemas import SaveProjectRequest
```

**4b — In `upload_photo`, add disk persistence after `shading_cache.set`.**
Find this block (around line 53-54):
```python
    shading_cache.set(photo_id, (rgb, alpha, shading))
```
Add immediately after:
```python
    suffix = Path(file.filename or "upload.png").suffix or ".png"
    project_store.save_photo(photo_id, suffix, data)
```

**4c — Append these 6 routes before the `StaticFiles` mount at the bottom of `backend/main.py`:**

```python
@app.get("/api/projects")
def list_projects():
    return {"projects": project_store.list_projects()}


@app.put("/api/projects")
def save_project(req: SaveProjectRequest):
    for angle in req.angles:
        photo_id = angle.get("photo_id")
        if photo_id and project_store.load_photo_bytes(photo_id) is None:
            raise HTTPException(
                status_code=409,
                detail=f"photo {photo_id!r} not found on disk; re-upload the photo before saving",
            )
    manifest = {
        "schema_version": 6,
        "name": req.name,
        "active_angle": req.active_angle,
        "angles": req.angles,
    }
    slug = project_store.save_project(req.name, manifest)
    saved = project_store.load_project(slug)
    return {"slug": slug, "name": req.name, "updated_at": saved["updated_at"]}


@app.get("/api/projects/{slug}/download")
def download_project(slug: str):
    try:
        blob = project_store.project_to_blob(slug)
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail="project not found")
    return Response(
        content=blob,
        media_type="application/json",
        headers={"Content-Disposition": f"attachment; filename={slug}.json"},
    )


@app.post("/api/projects/upload")
async def upload_project_blob(file: UploadFile = File(...)):
    data = await file.read()
    try:
        manifest, photos = project_store.project_from_blob(data)
    except (json.JSONDecodeError, KeyError) as exc:
        raise HTTPException(status_code=422, detail=f"invalid project blob: {exc}")
    for photo_id, (suffix, photo_bytes) in photos.items():
        project_store.save_photo(photo_id, suffix, photo_bytes)
        if shading_cache.get(photo_id) is None:
            try:
                rgb, alpha = decode_image(photo_bytes, f"photo{suffix}")
                shading = prepare_shading(rgb, alpha)
                shading_cache.set(photo_id, (rgb, alpha, shading))
            except Exception:
                pass
    slug = project_store.save_project(manifest["name"], manifest)
    return project_store.load_project(slug)


@app.get("/api/projects/{slug}")
def get_project(slug: str):
    try:
        manifest = project_store.load_project(slug)
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail="project not found")
    for angle in manifest.get("angles", []):
        photo_id = angle.get("photo_id")
        if photo_id and shading_cache.get(photo_id) is None:
            result = project_store.load_photo_bytes(photo_id)
            if result is None:
                continue
            photo_bytes, suffix = result
            try:
                rgb, alpha = decode_image(photo_bytes, f"photo{suffix}")
                shading = prepare_shading(rgb, alpha)
                shading_cache.set(photo_id, (rgb, alpha, shading))
            except Exception:
                continue
    return manifest


@app.delete("/api/projects/{slug}")
def delete_project(slug: str):
    project_store.delete_project(slug)
    return {"ok": True}
```

> **Route order matters:** `GET /api/projects/{slug}/download` and `POST /api/projects/upload` must be defined **before** `GET /api/projects/{slug}` so FastAPI matches the more-specific paths first. The order above is correct.

- [ ] **Step 5: Run tests — expect all pass**

```
.venv\Scripts\python -m pytest backend/tests/test_projects_api.py backend/tests/test_project_store.py -v
```
Expected: all green. Also run existing tests to confirm no regressions:
```
.venv\Scripts\python -m pytest backend/tests/ -v
```

- [ ] **Step 6: Commit**

```
git add backend/schemas.py backend/main.py backend/tests/test_projects_api.py
git commit -m "feat: add project save/load routes + photo disk persistence on upload"
```

---

### Task 3: Frontend types, API client functions, and store hydration

**Files:**
- Modify: `web/src/api/types.ts` (add `ProjectMeta`, `ProjectAngleDto`, `ProjectManifestDto`)
- Modify: `web/src/api/client.ts` (add 5 project functions)
- Modify: `web/src/store/projectStore.ts` (add `projectName`, `slug`, `setProjectMeta`, `initFromProject`; reset them in `initFromPhoto`)
- Modify: `web/src/store/projectStore.test.ts` (add tests for the two new actions)

**Interfaces:**
- Consumes: backend routes from Task 2
- Produces (TypeScript):
  - `ProjectMeta`, `ProjectAngleDto`, `ProjectManifestDto` in `types.ts`
  - `listProjects(): Promise<ProjectMeta[]>`
  - `saveProjectApi(name, activeAngle, angles): Promise<{slug,name,updated_at}>`
  - `loadProjectApi(slug): Promise<ProjectManifestDto>`
  - `deleteProjectApi(slug): Promise<void>`
  - `downloadProjectBlob(slug): Promise<void>` (triggers browser file download)
  - `uploadProjectBlob(file): Promise<ProjectManifestDto>`
  - Store: `projectName: string | null`, `slug: string | null`
  - Store actions: `setProjectMeta(name, slug|null)`, `initFromProject(manifest)`

- [ ] **Step 1: Add tests to `web/src/store/projectStore.test.ts`**

Add this `describe` block at the end of the file (before the closing `}`):

```typescript
describe("projectStore project persistence", () => {
  beforeEach(reset);

  it("initFromProject hydrates angles and sets project meta", () => {
    const manifest: import("../api/types").ProjectManifestDto = {
      name: "Iron Warrior",
      slug: "iron-warrior",
      active_angle: 0,
      updated_at: "2026-01-01T00:00:00Z",
      angles: [
        {
          id: "a1",
          label: "front",
          photo_id: "ph001",
          width: 640,
          height: 480,
          book: {
            whole: { palette: [{ name: "base", hex: "#333" }], coverage: [1], material: "matte" },
            drawn: [],
            selected: 0,
            schemes: [],
          },
          settings: {
            edge_hl: true, edge_extreme: false, edge_sens: 0.5,
            relief_cap: true, per_region_norm: false,
          },
        },
      ],
    };
    useProjectStore.getState().initFromProject(manifest);
    const s = useProjectStore.getState();
    expect(s.projectName).toBe("Iron Warrior");
    expect(s.slug).toBe("iron-warrior");
    expect(s.activeAngle).toBe(0);
    expect(s.angles).toHaveLength(1);
    expect(s.angles[0].id).toBe("a1");
    expect(s.angles[0].photoId).toBe("ph001");
    expect(s.angles[0].width).toBe(640);
    expect(s.angles[0].height).toBe(480);
    expect(s.angles[0].qualityChecks).toEqual([]);
    expect(s.angles[0].preview).toBeUndefined();
    expect(s.angles[0].resultToken).toBeUndefined();
  });

  it("initFromPhoto clears projectName and slug", () => {
    useProjectStore.getState().setProjectMeta("old name", "old-slug");
    useProjectStore.getState().initFromPhoto({
      photo_id: "p2", width: 100, height: 100, quality_checks: [],
      default_whole: { palette: [], coverage: [], material: "matte" },
    });
    const s = useProjectStore.getState();
    expect(s.projectName).toBeNull();
    expect(s.slug).toBeNull();
  });

  it("setProjectMeta stores name and slug", () => {
    useProjectStore.getState().setProjectMeta("My Mini", "my-mini");
    expect(useProjectStore.getState().projectName).toBe("My Mini");
    expect(useProjectStore.getState().slug).toBe("my-mini");
  });

  it("initFromProject preserves drawn region blank flag default", () => {
    const manifest: import("../api/types").ProjectManifestDto = {
      name: "Test", slug: "test", active_angle: 0, updated_at: "",
      angles: [{
        id: "a1", label: "angle 1", photo_id: "ph1",
        book: {
          whole: { palette: [], coverage: [], material: "matte" },
          drawn: [{ id: "r1", name: "helm", rings: [], palette: [], coverage: [], material: "matte" }],
          selected: 0, schemes: [],
        },
        settings: { edge_hl: true, edge_extreme: false, edge_sens: 0.5, relief_cap: true, per_region_norm: false },
      }],
    };
    useProjectStore.getState().initFromProject(manifest);
    const drawn = useProjectStore.getState().angles[0].book.drawn;
    expect(drawn[0].blank).toBe(false);
  });
});
```

- [ ] **Step 2: Run tests to verify new ones fail**

From `web/` directory:
```
npm test -- --run
```
Expected: 3 new tests fail (`initFromProject`, `initFromPhoto clears`, `setProjectMeta`).

- [ ] **Step 3: Add types to `web/src/api/types.ts`**

Append to the end of `web/src/api/types.ts`:

```typescript
export interface ProjectMeta {
  slug: string;
  name: string;
  updated_at: string;
}

export interface ProjectAngleDto {
  id: string;
  label: string;
  photo_id: string;
  width?: number;
  height?: number;
  book: {
    whole: Whole;
    drawn: {
      id: string; name: string; rings: number[][][];
      palette: PaintColor[]; coverage: number[]; material: string;
      blank?: boolean;
      surface?: string; tone?: string; ramp_midtone?: string; ramp_variant?: string;
    }[];
    selected: number;
    hero_hex?: string;
    mood?: string;
    variant?: string;
    schemes: { id: string; name: string; palettes: { [regionId: string]: PaintColor[] }; anchor_hex?: string }[];
  };
  settings: Settings;
}

export interface ProjectManifestDto {
  name: string;
  slug: string;
  active_angle: number;
  updated_at: string;
  angles: ProjectAngleDto[];
}
```

- [ ] **Step 4: Update `web/src/store/projectStore.ts`**

**4a — Add the import** at the top (extend the existing import from `../api/types`):
```typescript
import type { PhotoResponse, Settings, Whole, PaintColor, QualityCheck, ProjectManifestDto } from "../api/types";
```

**4b — Add two new fields to `interface State`** after `angles: Angle[]`:
```typescript
  projectName: string | null;
  slug: string | null;
  setProjectMeta(name: string, slug: string | null): void;
  initFromProject(manifest: ProjectManifestDto): void;
```

**4c — Update `INITIAL_STATE`:**
```typescript
const INITIAL_STATE = { activeAngle: 0, angles: [] as Angle[], projectName: null as string | null, slug: null as string | null };
```

**4d — Update `initFromPhoto` inside `create<State>` to also clear project meta:**
```typescript
  initFromPhoto: (res) => set({
    activeAngle: 0,
    angles: [makeAngle(res, "angle 1", DEFAULT_SETTINGS)],
    projectName: null,
    slug: null,
  }),
```

**4e — Add two new actions inside `create<State>` (before the closing `})`)**:
```typescript
  setProjectMeta: (name, slug) => set({ projectName: name, slug }),

  initFromProject: (manifest) => set({
    activeAngle: manifest.active_angle,
    angles: manifest.angles.map((a) => ({
      id: a.id,
      label: a.label,
      photoId: a.photo_id,
      width: a.width,
      height: a.height,
      qualityChecks: [] as QualityCheck[],
      book: {
        ...a.book,
        drawn: a.book.drawn.map((d) => ({ ...d, blank: d.blank ?? false })),
      },
      settings: a.settings,
    })),
    projectName: manifest.name,
    slug: manifest.slug,
  }),
```

- [ ] **Step 5: Add project API functions to `web/src/api/client.ts`**

Append to the end of `web/src/api/client.ts`:

```typescript
import type { ProjectMeta, ProjectManifestDto } from "./types";
import type { Angle } from "../store/projectStore";

function toProjectAngleDto(a: Angle): object {
  return {
    id: a.id,
    label: a.label,
    photo_id: a.photoId,
    width: a.width,
    height: a.height,
    book: a.book,
    settings: a.settings,
  };
}

export async function listProjects(): Promise<ProjectMeta[]> {
  const data = await json<{ projects: ProjectMeta[] }>(await fetch("/api/projects"));
  return data.projects;
}

export async function saveProjectApi(
  name: string,
  activeAngle: number,
  angles: Angle[],
): Promise<{ slug: string; name: string; updated_at: string }> {
  return json(await fetch("/api/projects", {
    method: "PUT",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ name, active_angle: activeAngle, angles: angles.map(toProjectAngleDto) }),
  }));
}

export async function loadProjectApi(slug: string): Promise<ProjectManifestDto> {
  return json<ProjectManifestDto>(await fetch(`/api/projects/${encodeURIComponent(slug)}`));
}

export async function deleteProjectApi(slug: string): Promise<void> {
  await json(await fetch(`/api/projects/${encodeURIComponent(slug)}`, { method: "DELETE" }));
}

export async function downloadProjectBlob(slug: string): Promise<void> {
  const res = await fetch(`/api/projects/${encodeURIComponent(slug)}/download`);
  if (!res.ok) throw new Error(`${res.status} ${await res.text()}`);
  const blob = await res.blob();
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = `${slug}.json`;
  a.click();
  URL.revokeObjectURL(url);
}

export async function uploadProjectBlob(file: File): Promise<ProjectManifestDto> {
  const fd = new FormData();
  fd.append("file", file, file.name);
  return json<ProjectManifestDto>(await fetch("/api/projects/upload", { method: "POST", body: fd }));
}
```

- [ ] **Step 6: Run all frontend tests — expect all pass**

```
npm test -- --run
```
Expected: all green including the 4 new store tests.

- [ ] **Step 7: Commit**

```
git add web/src/api/types.ts web/src/api/client.ts web/src/store/projectStore.ts web/src/store/projectStore.test.ts
git commit -m "feat: add project types, API client functions, and store hydration"
```

---

### Task 4: `ProjectLibrary` component, i18n keys, and App wiring

**Files:**
- Create: `web/src/components/ProjectLibrary.tsx`
- Create: `web/src/components/ProjectLibrary.test.tsx`
- Modify: `locales/en.json` (add react project keys under `"projects"`)
- Modify: `locales/es.json` (add same keys, untranslated for now)
- Modify: `web/src/App.tsx` (import + render `<ProjectLibrary />`)

**Interfaces:**
- Consumes: `listProjects`, `saveProjectApi`, `loadProjectApi`, `deleteProjectApi`, `downloadProjectBlob`, `uploadProjectBlob` from `client.ts` (Task 3)
- Consumes: `projectName`, `slug`, `activeAngle`, `angles`, `initFromProject`, `setProjectMeta` from `useProjectStore` (Task 3)

- [ ] **Step 1: Add i18n keys to `locales/en.json`**

Inside the `"projects"` object, add these keys alongside the existing Streamlit keys:

```json
"react_toggle": "Projects",
"react_name_placeholder": "Project name",
"react_save": "Save",
"react_saving": "Saving…",
"react_import": "Import JSON",
"react_importing": "Uploading…",
"react_empty": "No saved projects",
"react_load": "Load",
"react_export": "↓",
"react_delete": "×",
"react_confirm_delete": "Delete \"{{name}}\"?"
```

- [ ] **Step 2: Add same keys to `locales/es.json`**

Inside the `"projects"` object in `es.json`, add (same English values as placeholder — translate later):

```json
"react_toggle": "Proyectos",
"react_name_placeholder": "Nombre del proyecto",
"react_save": "Guardar",
"react_saving": "Guardando…",
"react_import": "Importar JSON",
"react_importing": "Subiendo…",
"react_empty": "No hay proyectos guardados",
"react_load": "Cargar",
"react_export": "↓",
"react_delete": "×",
"react_confirm_delete": "¿Eliminar \"{{name}}\"?"
```

- [ ] **Step 3: Write `web/src/components/ProjectLibrary.test.tsx`**

```typescript
import { render, screen, fireEvent, waitFor } from "@testing-library/react";
import { describe, it, expect, vi, beforeEach } from "vitest";
import { ProjectLibrary } from "./ProjectLibrary";
import * as client from "../api/client";
import { useProjectStore } from "../store/projectStore";

vi.mock("../api/client");
vi.mock("react-i18next", () => ({
  useTranslation: () => ({
    t: (key: string, opts?: Record<string, string>) => {
      if (opts?.name) return key.replace("{{name}}", opts.name);
      return key;
    },
  }),
}));

const mockProjects = [
  { slug: "my-mini", name: "My Mini", updated_at: "2026-01-15T00:00:00Z" },
];

beforeEach(() => {
  vi.mocked(client.listProjects).mockResolvedValue(mockProjects);
  vi.mocked(client.saveProjectApi).mockResolvedValue({
    slug: "my-mini", name: "My Mini", updated_at: "2026-01-15T00:00:00Z",
  });
  vi.mocked(client.loadProjectApi).mockResolvedValue({
    name: "My Mini", slug: "my-mini", active_angle: 0, updated_at: "2026-01-15T00:00:00Z",
    angles: [],
  });
  vi.mocked(client.deleteProjectApi).mockResolvedValue(undefined);
  // Reset store
  useProjectStore.setState(useProjectStore.getInitialState(), true);
});

it("renders collapsed by default", () => {
  render(<ProjectLibrary />);
  expect(screen.getByText(/projects\.react_toggle/i)).toBeInTheDocument();
  expect(screen.queryByPlaceholderText(/react_name_placeholder/i)).not.toBeInTheDocument();
});

it("expands on click and loads project list", async () => {
  render(<ProjectLibrary />);
  fireEvent.click(screen.getByRole("button", { name: /projects\.react_toggle/i }));
  await waitFor(() => {
    expect(screen.getByPlaceholderText(/react_name_placeholder/i)).toBeInTheDocument();
    expect(screen.getByText("My Mini")).toBeInTheDocument();
  });
});

it("collapses when toggle clicked again", async () => {
  render(<ProjectLibrary />);
  const btn = screen.getByRole("button", { name: /projects\.react_toggle/i });
  fireEvent.click(btn);
  await waitFor(() => screen.getByText("My Mini"));
  fireEvent.click(btn);
  expect(screen.queryByText("My Mini")).not.toBeInTheDocument();
});

it("calls loadProjectApi and initFromProject when Load is clicked", async () => {
  const initSpy = vi.spyOn(useProjectStore.getState(), "initFromProject");
  render(<ProjectLibrary />);
  fireEvent.click(screen.getByRole("button", { name: /projects\.react_toggle/i }));
  await waitFor(() => screen.getByText("My Mini"));
  fireEvent.click(screen.getByText(/projects\.react_load/));
  await waitFor(() => expect(client.loadProjectApi).toHaveBeenCalledWith("my-mini"));
});

it("calls deleteProjectApi after confirmation", async () => {
  vi.spyOn(window, "confirm").mockReturnValue(true);
  render(<ProjectLibrary />);
  fireEvent.click(screen.getByRole("button", { name: /projects\.react_toggle/i }));
  await waitFor(() => screen.getByText("My Mini"));
  fireEvent.click(screen.getByText(/projects\.react_delete/));
  await waitFor(() => expect(client.deleteProjectApi).toHaveBeenCalledWith("my-mini"));
});

it("does NOT call deleteProjectApi if user cancels confirmation", async () => {
  vi.spyOn(window, "confirm").mockReturnValue(false);
  render(<ProjectLibrary />);
  fireEvent.click(screen.getByRole("button", { name: /projects\.react_toggle/i }));
  await waitFor(() => screen.getByText("My Mini"));
  fireEvent.click(screen.getByText(/projects\.react_delete/));
  expect(client.deleteProjectApi).not.toHaveBeenCalled();
});

it("shows 'No saved projects' when list is empty", async () => {
  vi.mocked(client.listProjects).mockResolvedValue([]);
  render(<ProjectLibrary />);
  fireEvent.click(screen.getByRole("button", { name: /projects\.react_toggle/i }));
  await waitFor(() => screen.getByText(/projects\.react_empty/));
});
```

- [ ] **Step 4: Run tests to verify new ones fail**

```
npm test -- --run
```
Expected: 6 new `ProjectLibrary` tests fail (`ProjectLibrary` does not exist yet).

- [ ] **Step 5: Create `web/src/components/ProjectLibrary.tsx`**

```typescript
import { useEffect, useRef, useState } from "react";
import { useTranslation } from "react-i18next";
import {
  deleteProjectApi,
  downloadProjectBlob,
  listProjects,
  loadProjectApi,
  saveProjectApi,
  uploadProjectBlob,
} from "../api/client";
import { useProjectStore } from "../store/projectStore";
import type { ProjectMeta } from "../api/types";

export function ProjectLibrary() {
  const { t } = useTranslation();
  const [open, setOpen] = useState(false);
  const [projects, setProjects] = useState<ProjectMeta[]>([]);
  const [inputName, setInputName] = useState("");
  const [busy, setBusy] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const fileRef = useRef<HTMLInputElement>(null);

  const projectName = useProjectStore((s) => s.projectName);
  const slug = useProjectStore((s) => s.slug);
  const activeAngle = useProjectStore((s) => s.activeAngle);
  const angles = useProjectStore((s) => s.angles);
  const initFromProject = useProjectStore((s) => s.initFromProject);
  const setProjectMeta = useProjectStore((s) => s.setProjectMeta);
  const hasAngles = angles.length > 0;

  useEffect(() => {
    if (projectName && !inputName) setInputName(projectName);
  }, [projectName]);

  useEffect(() => {
    if (!open) return;
    listProjects().then(setProjects).catch(() => setProjects([]));
  }, [open]);

  async function handleSave() {
    const name = inputName.trim();
    if (!name || !hasAngles) return;
    setBusy("save");
    setError(null);
    try {
      const res = await saveProjectApi(name, activeAngle, angles);
      setProjectMeta(res.name, res.slug);
      setProjects(await listProjects());
    } catch (e) {
      setError(e instanceof Error ? e.message : "save failed");
    } finally {
      setBusy(null);
    }
  }

  async function handleLoad(projectSlug: string) {
    setBusy(`load:${projectSlug}`);
    setError(null);
    try {
      const manifest = await loadProjectApi(projectSlug);
      initFromProject(manifest);
    } catch (e) {
      setError(e instanceof Error ? e.message : "load failed");
    } finally {
      setBusy(null);
    }
  }

  async function handleDelete(projectSlug: string, name: string) {
    if (!window.confirm(t("projects.react_confirm_delete", { name }))) return;
    setBusy(`delete:${projectSlug}`);
    setError(null);
    try {
      await deleteProjectApi(projectSlug);
      setProjects((prev) => prev.filter((p) => p.slug !== projectSlug));
    } catch (e) {
      setError(e instanceof Error ? e.message : "delete failed");
    } finally {
      setBusy(null);
    }
  }

  async function handleDownload(projectSlug: string) {
    setBusy(`download:${projectSlug}`);
    setError(null);
    try {
      await downloadProjectBlob(projectSlug);
    } catch (e) {
      setError(e instanceof Error ? e.message : "download failed");
    } finally {
      setBusy(null);
    }
  }

  async function handleUpload(e: React.ChangeEvent<HTMLInputElement>) {
    const file = e.target.files?.[0];
    if (!file) return;
    setBusy("upload");
    setError(null);
    try {
      const manifest = await uploadProjectBlob(file);
      initFromProject(manifest);
      setProjects(await listProjects());
    } catch (e) {
      setError(e instanceof Error ? e.message : "upload failed");
    } finally {
      setBusy(null);
      if (fileRef.current) fileRef.current.value = "";
    }
  }

  const label = `${open ? "▼" : "▶"} ${t("projects.react_toggle")}${projectName ? ` — ${projectName}` : ""}`;

  return (
    <div style={{ marginBottom: 16, paddingBottom: open ? 12 : 0, borderBottom: "1px solid #2a2a2a" }}>
      <button
        onClick={() => setOpen((v) => !v)}
        style={{ background: "none", border: "none", color: "#888", cursor: "pointer", padding: "4px 0", fontSize: 13 }}
      >
        {label}
      </button>

      {open && (
        <div style={{ marginTop: 10 }}>
          {error && (
            <div style={{ color: "#f66", marginBottom: 8, fontSize: 13 }}>{error}</div>
          )}

          <div style={{ display: "flex", gap: 8, alignItems: "center", marginBottom: 10, flexWrap: "wrap" }}>
            <input
              value={inputName}
              onChange={(e) => setInputName(e.target.value)}
              onKeyDown={(e) => { if (e.key === "Enter") handleSave(); }}
              placeholder={t("projects.react_name_placeholder")}
              style={{
                flex: "1 1 160px", padding: "4px 8px",
                background: "#1a1a1a", color: "#ddd",
                border: "1px solid #444", borderRadius: 4, fontSize: 13,
              }}
            />
            <button
              onClick={handleSave}
              disabled={!inputName.trim() || !hasAngles || busy === "save"}
              style={{ padding: "4px 12px", fontSize: 13, cursor: "pointer" }}
            >
              {busy === "save" ? t("projects.react_saving") : t("projects.react_save")}
            </button>
            <button
              onClick={() => fileRef.current?.click()}
              disabled={busy === "upload"}
              style={{ padding: "4px 12px", fontSize: 13, cursor: "pointer" }}
            >
              {busy === "upload" ? t("projects.react_importing") : t("projects.react_import")}
            </button>
            <input
              ref={fileRef}
              type="file"
              accept=".json"
              onChange={handleUpload}
              style={{ display: "none" }}
            />
          </div>

          {projects.length === 0 ? (
            <div style={{ color: "#555", fontSize: 13 }}>{t("projects.react_empty")}</div>
          ) : (
            <div style={{ display: "flex", flexDirection: "column", gap: 2 }}>
              {projects.map((p) => (
                <div
                  key={p.slug}
                  style={{ display: "flex", alignItems: "center", gap: 8, padding: "3px 0" }}
                >
                  <span style={{ flex: 1, fontSize: 13, color: p.slug === slug ? "#eee" : "#999" }}>
                    {p.name}
                  </span>
                  <span style={{ color: "#444", fontSize: 11, whiteSpace: "nowrap" }}>
                    {new Date(p.updated_at).toLocaleDateString()}
                  </span>
                  <button
                    onClick={() => handleLoad(p.slug)}
                    disabled={busy === `load:${p.slug}`}
                    style={{ padding: "2px 8px", fontSize: 12, cursor: "pointer" }}
                  >
                    {busy === `load:${p.slug}` ? "…" : t("projects.react_load")}
                  </button>
                  <button
                    onClick={() => handleDownload(p.slug)}
                    disabled={busy === `download:${p.slug}`}
                    title="Export JSON"
                    style={{ padding: "2px 6px", fontSize: 12, cursor: "pointer" }}
                  >
                    {t("projects.react_export")}
                  </button>
                  <button
                    onClick={() => handleDelete(p.slug, p.name)}
                    disabled={busy?.startsWith("delete:") ?? false}
                    title="Delete"
                    style={{ padding: "2px 6px", fontSize: 12, cursor: "pointer", color: "#c44" }}
                  >
                    {t("projects.react_delete")}
                  </button>
                </div>
              ))}
            </div>
          )}
        </div>
      )}
    </div>
  );
}
```

- [ ] **Step 6: Wire `ProjectLibrary` into `web/src/App.tsx`**

**6a — Add import** at the top of `App.tsx` (after existing imports):
```typescript
import { ProjectLibrary } from "./components/ProjectLibrary";
```

**6b — Add `<ProjectLibrary />` as the first child of `<main>`, before `{!hasAngle ? ...}`**:

Find:
```tsx
    <main style={{ maxWidth: 1100, margin: "0 auto", padding: 16 }}>
      <h1>Mini Highlight Advisor</h1>
      {!hasAngle ? (
```

Replace with:
```tsx
    <main style={{ maxWidth: 1100, margin: "0 auto", padding: 16 }}>
      <h1>Mini Highlight Advisor</h1>
      <ProjectLibrary />
      {!hasAngle ? (
```

- [ ] **Step 7: Run all frontend tests — expect all pass**

```
npm test -- --run
```
Expected: all green.

- [ ] **Step 8: Smoke-test in the browser**

Start both processes (repo root):
```
.venv\Scripts\python -m uvicorn backend.main:app --reload --port 8000
```
```
cd web && npm run dev
```

Open `http://localhost:5173`. Verify:
1. "▶ Projects" toggle is visible above the uploader on a fresh load
2. Click toggle → panel expands, "No saved projects" shown
3. Upload a photo → Studio view
4. Type a project name → click Save → project appears in list, toggle shows "▼ Projects — My Mini"
5. Reload page → click "▶ Projects" → project in list
6. Click Load → Studio reloads with same photo and settings (preview regenerates in ~1s)
7. Click ↓ on the project → browser downloads a `.json` file
8. Delete the project → list becomes empty
9. Upload the downloaded `.json` via "Import JSON" → project reappears and loads

- [ ] **Step 9: Commit**

```
git add web/src/components/ProjectLibrary.tsx web/src/components/ProjectLibrary.test.tsx
git add web/src/App.tsx locales/en.json locales/es.json
git commit -m "feat: add ProjectLibrary component and wire into App"
```

---

## Self-Review

**Spec coverage check (§5):**
- `GET /api/projects` ✓ Task 2
- `GET /api/projects/{slug}` ✓ Task 2 (warms shading cache)
- `PUT /api/projects/{slug}` → implemented as `PUT /api/projects` (no slug in URL — client sends name, server slugifies) ✓ Task 2
- `DELETE /api/projects/{slug}` ✓ Task 2
- `GET /api/projects/{slug}/download` ✓ Task 2
- `POST /api/projects/upload` ✓ Task 2
- Photo disk persistence (approach A) ✓ Task 2

**Spec coverage check (§6):**
- v6 schema (rings, not numpy masks) ✓ manifest stored verbatim
- `save = serialize store → manifest` ✓ `saveProjectApi` + `toProjectAngleDto`
- `load = hydrate store from manifest` ✓ `initFromProject`
- `qualityChecks: []` on load ✓ Task 3
- `preview/resultToken` cleared on load (absent = undefined) ✓ Task 3

**Type consistency check:**
- `photo_id` (snake_case) used in all Python code and JSON manifests ✓
- `photoId` (camelCase) used in store's `Angle` type ✓
- `toProjectAngleDto` converts `photoId → photo_id` on save ✓
- `initFromProject` converts `photo_id → photoId` on load ✓
- `ProjectManifestDto.active_angle` (snake_case from API) → `manifest.active_angle` in `initFromProject` ✓

**Placeholder scan:** None found. All code blocks are complete and runnable.
