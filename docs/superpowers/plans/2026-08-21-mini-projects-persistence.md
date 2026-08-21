# Mini-Projects Persistence Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a named "mini library" — save the current session (photo, regions, palettes, coverage, render settings) to disk and reload any saved project later.

**Architecture:** A Streamlit-free core module `projects.py` (mirroring `collection.py`/`recipes.py`) owns all serialization: each project is a folder `user_data/projects/<slug>/` holding `manifest.json`, the original photo bytes, and one 1-bit PNG per drawn-region mask. A thin `ui/projects_panel.py` provides save/load/delete widgets, and `app.py`'s upload gate is extended so a loaded project can supply the photo instead of a fresh upload.

**Tech Stack:** Python 3.11, numpy, Pillow (PIL), Streamlit; stdlib `json`, `pathlib`, `shutil`, `datetime`.

**Spec:** `docs/superpowers/specs/2026-08-21-mini-projects-persistence-design.md`

## Global Constraints

- **Core stays Streamlit-free:** `projects.py` must not import `streamlit`. All Streamlit glue lives in `ui/projects_panel.py` and `app.py`. (Same discipline as `collection.py`/`recipes.py`.)
- **Persistence root:** default `user_data/projects/` resolved as `Path(__file__).resolve().parents[2] / "user_data" / "projects"` — identical anchoring to `collection.COLLECTION_PATH`. Every public function takes a `root: Path` argument (default = that constant) so tests use `tmp_path`.
- **Masks are photo-coupled:** drawn-region masks are saved/loaded at source resolution and are only valid against the same photo; never attempt to re-derive them from polygons.
- **Owned paints and recipes stay global** — do NOT copy them into a project.
- **Tests:** `.venv/Scripts/python -m pytest`. New core tests live in `tests/test_projects.py`. No Streamlit UI unit tests (repo convention).
- **Process:** feature branch `feat/mini-projects-persistence`, commit per task, never build on `main`.

---

### Task 1: Core scaffolding — dataclasses, `slugify`, PaintColor (de)serialization

**Files:**
- Create: `src/mini_highlight_advisor/projects.py`
- Test: `tests/test_projects.py`

**Interfaces:**
- Consumes: `PaintColor` from `mini_highlight_advisor.palette`.
- Produces:
  - `PROJECTS_DIR: Path`
  - `@dataclass(frozen=True) ProjectSettings(n:int, edge_hl:bool, edge_extreme:bool, edge_sens:float, relief_cap:bool, per_region_norm:bool)`
  - `@dataclass(frozen=True) ProjectMeta(slug:str, name:str, updated_at:str)`
  - `slugify(name:str) -> str`
  - `_palette_to_dicts(palette:list[PaintColor]) -> list[dict]`
  - `_palette_from_dicts(items:list[dict]) -> list[PaintColor]`

- [ ] **Step 1: Write the failing test**

```python
# tests/test_projects.py
from mini_highlight_advisor import projects
from mini_highlight_advisor.palette import PaintColor


def test_slugify_normalizes_and_is_stable():
    assert projects.slugify("Skaven Hero") == "skaven-hero"
    assert projects.slugify("  My Mini!!  ") == "my-mini"
    # same display name -> same slug (overwrite semantics rely on this)
    assert projects.slugify("Space Marine") == projects.slugify("space   marine")


def test_slugify_rejects_empty():
    import pytest
    with pytest.raises(ValueError):
        projects.slugify("   ")


def test_palette_dict_roundtrip_preserves_all_fields():
    pal = [
        PaintColor("Black", "#1b1b1b", "Vallejo", "Model Color", code="70.950"),
        PaintColor("Custom", "#abcdef"),  # brand/paint_range None, code "", finish default
    ]
    out = projects._palette_from_dicts(projects._palette_to_dicts(pal))
    assert out == pal
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.venv/Scripts/python -m pytest tests/test_projects.py -v`
Expected: FAIL (module `projects` has no attribute `slugify` / import error).

- [ ] **Step 3: Write minimal implementation**

```python
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
```

- [ ] **Step 4: Run test to verify it passes**

Run: `.venv/Scripts/python -m pytest tests/test_projects.py -v`
Expected: PASS (3 tests).

- [ ] **Step 5: Commit**

```bash
git add src/mini_highlight_advisor/projects.py tests/test_projects.py
git commit -m "feat(projects): core scaffolding — slugify + palette (de)serialization"
```

---

### Task 2: Save/load a whole-mini project (no drawn regions)

Round-trips manifest + photo bytes + settings + the whole-mini palette/coverage. Drawn regions come in Task 3.

**Files:**
- Modify: `src/mini_highlight_advisor/projects.py`
- Test: `tests/test_projects.py`

**Interfaces:**
- Consumes: `RegionBook` from `mini_highlight_advisor.region_state`; `ProjectSettings`, `slugify`, `_palette_to_dicts/_from_dicts` from Task 1.
- Produces:
  - `@dataclass(frozen=True) LoadedProject(photo_bytes:bytes, photo_suffix:str, book:RegionBook, settings:ProjectSettings)`
  - `save_project(name:str, photo_bytes:bytes, photo_suffix:str, book:RegionBook, settings:ProjectSettings, root:Path=PROJECTS_DIR, _now:str|None=None) -> str` (returns slug)
  - `load_project(slug:str, root:Path=PROJECTS_DIR) -> LoadedProject`
  - Private: `_manifest_path(root, slug) -> Path`, `_now_iso() -> str`

**Notes for the implementer:**
- `RegionBook` is `RegionBook(whole_palette, whole_coverage, drawn=[], selected=0)` (see `region_state.py`).
- `photo_suffix` is like `".png"`; the photo file is written as `photo{suffix}` and its name recorded in the manifest as `photo_file`.
- `_now` param exists ONLY so tests can pin timestamps; production calls pass nothing and get `_now_iso()`.

- [ ] **Step 1: Write the failing test**

```python
def _settings():
    return projects.ProjectSettings(n=5, edge_hl=True, edge_extreme=False,
                                    edge_sens=0.5, relief_cap=True, per_region_norm=False)


def _whole_book():
    from mini_highlight_advisor.region_state import RegionBook
    from mini_highlight_advisor.palette import default_ramp, default_coverage
    return RegionBook(default_ramp(5), default_coverage(5))


def test_save_then_load_whole_mini_roundtrip(tmp_path):
    book = _whole_book()
    slug = projects.save_project("Skaven Hero", b"PHOTOBYTES", ".png",
                                 book, _settings(), root=tmp_path)
    assert slug == "skaven-hero"

    loaded = projects.load_project(slug, root=tmp_path)
    assert loaded.photo_bytes == b"PHOTOBYTES"
    assert loaded.photo_suffix == ".png"
    assert loaded.settings == _settings()
    assert loaded.book.whole_palette == book.whole_palette
    assert loaded.book.whole_coverage == book.whole_coverage
    assert loaded.book.drawn == []
    assert loaded.book.selected == 0
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.venv/Scripts/python -m pytest tests/test_projects.py::test_save_then_load_whole_mini_roundtrip -v`
Expected: FAIL (`save_project` not defined).

- [ ] **Step 3: Write minimal implementation**

Add to `projects.py`:

```python
import json
from datetime import datetime, timezone

from .region_state import RegionBook


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
```

- [ ] **Step 4: Run test to verify it passes**

Run: `.venv/Scripts/python -m pytest tests/test_projects.py::test_save_then_load_whole_mini_roundtrip -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add src/mini_highlight_advisor/projects.py tests/test_projects.py
git commit -m "feat(projects): save/load whole-mini roundtrip (manifest + photo + settings)"
```

---

### Task 3: Drawn regions with 1-bit PNG masks

Extend save/load so `book.drawn` regions serialize each as `region_NN.png` (bit-identical bool mask) plus name/palette/coverage in the manifest.

**Files:**
- Modify: `src/mini_highlight_advisor/projects.py`
- Test: `tests/test_projects.py`

**Interfaces:**
- Consumes: `Region` from `mini_highlight_advisor.regions`; save/load from Task 2.
- Produces (private): `_write_mask(path:Path, mask:np.ndarray) -> None`, `_read_mask(path:Path) -> np.ndarray`.

**Notes for the implementer:**
- `Region` = `Region(name:str, mask:np.ndarray(bool), palette:list[PaintColor], coverage:list[float])`.
- Mask PNG: `Image.fromarray(mask_bool)` yields a 1-bit ("1") image; read back with `np.asarray(Image.open(path)).astype(bool)`. This round-trips 0/1 bit-identically.
- Mask files are named `region_00.png`, `region_01.png`, … index-aligned to `book.drawn`.

- [ ] **Step 1: Write the failing test**

```python
import numpy as np


def test_drawn_regions_roundtrip_masks_bit_identical(tmp_path):
    from mini_highlight_advisor.region_state import RegionBook
    from mini_highlight_advisor.regions import Region
    from mini_highlight_advisor.palette import default_ramp, default_coverage

    m0 = np.zeros((6, 8), dtype=bool); m0[1:3, 2:5] = True
    m1 = np.zeros((6, 8), dtype=bool); m1[4:6, 0:2] = True
    book = RegionBook(default_ramp(5), default_coverage(5), drawn=[
        Region("Cloak", m0, default_ramp(4), default_coverage(4)),
        Region("Blade", m1, default_ramp(3), default_coverage(3)),
    ], selected=1)

    slug = projects.save_project("Multi", b"PB", ".png", book, _settings(), root=tmp_path)
    loaded = projects.load_project(slug, root=tmp_path)

    assert [r.name for r in loaded.book.drawn] == ["Cloak", "Blade"]
    assert np.array_equal(loaded.book.drawn[0].mask, m0)
    assert np.array_equal(loaded.book.drawn[1].mask, m1)
    assert loaded.book.drawn[0].palette == book.drawn[0].palette
    assert loaded.book.drawn[0].coverage == book.drawn[0].coverage
    assert loaded.book.selected == 1
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.venv/Scripts/python -m pytest tests/test_projects.py::test_drawn_regions_roundtrip_masks_bit_identical -v`
Expected: FAIL (`loaded.book.drawn` is `[]`).

- [ ] **Step 3: Write minimal implementation**

Add mask helpers and wire them into save/load:

```python
import numpy as np
from PIL import Image
from .regions import Region


def _write_mask(path: Path, mask: np.ndarray) -> None:
    Image.fromarray(np.asarray(mask, dtype=bool)).save(path)


def _read_mask(path: Path) -> np.ndarray:
    return np.asarray(Image.open(path)).astype(bool)
```

In `save_project`, replace the `"drawn": []` line with a loop that writes each mask and builds its manifest entry:

```python
    drawn_entries = []
    for i, r in enumerate(book.drawn):
        mask_file = f"region_{i:02d}.png"
        _write_mask(dest / mask_file, r.mask)
        drawn_entries.append({
            "name": r.name,
            "palette": _palette_to_dicts(r.palette),
            "coverage": list(r.coverage),
            "mask_file": mask_file,
        })
    # ...
    "drawn": drawn_entries,
```

In `load_project`, replace `drawn=[]` with:

```python
    drawn = [
        Region(name=d["name"],
               mask=_read_mask(mpath.parent / d["mask_file"]),
               palette=_palette_from_dicts(d["palette"]),
               coverage=list(d["coverage"]))
        for d in b["drawn"]
    ]
    # RegionBook(..., drawn=drawn, ...)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `.venv/Scripts/python -m pytest tests/test_projects.py -v`
Expected: PASS (all tests, including Task 2's, still green).

- [ ] **Step 5: Commit**

```bash
git add src/mini_highlight_advisor/projects.py tests/test_projects.py
git commit -m "feat(projects): serialize drawn regions as 1-bit PNG masks"
```

---

### Task 4: `list_projects`, `delete_project`, atomic overwrite-by-name, corrupt-manifest handling

**Files:**
- Modify: `src/mini_highlight_advisor/projects.py`
- Test: `tests/test_projects.py`

**Interfaces:**
- Produces:
  - `list_projects(root:Path=PROJECTS_DIR) -> list[ProjectMeta]` (sorted by `updated_at` descending)
  - `delete_project(slug:str, root:Path=PROJECTS_DIR) -> None`
  - `save_project` upgraded to write atomically and to leave no orphaned mask files on overwrite.

**Notes for the implementer:**
- **Atomic overwrite:** write the whole project into a temp dir `root / f".tmp-{slug}"`, then `shutil.rmtree(dest, ignore_errors=True)` and `os.replace(tmp, dest)`. Building fresh into a temp dir is what guarantees a smaller re-save leaves no stale `region_NN.png` from a previous larger book.
- `list_projects` skips any subfolder whose `manifest.json` is missing or unparseable (so a half-written or hand-broken folder never crashes the list).
- `delete_project` on a missing slug is a no-op (idempotent).

- [ ] **Step 1: Write the failing test**

```python
import pytest


def test_list_projects_sorted_by_updated_desc(tmp_path):
    book = _whole_book()
    projects.save_project("Alpha", b"A", ".png", book, _settings(), root=tmp_path,
                          _now="2026-08-20T10:00:00+00:00")
    projects.save_project("Beta", b"B", ".png", book, _settings(), root=tmp_path,
                          _now="2026-08-21T10:00:00+00:00")
    metas = projects.list_projects(root=tmp_path)
    assert [m.name for m in metas] == ["Beta", "Alpha"]
    assert metas[0].slug == "beta"


def test_overwrite_by_name_drops_stale_region_masks(tmp_path):
    from mini_highlight_advisor.region_state import RegionBook
    from mini_highlight_advisor.regions import Region
    from mini_highlight_advisor.palette import default_ramp, default_coverage
    m = np.zeros((4, 4), dtype=bool); m[0, 0] = True
    two = RegionBook(default_ramp(5), default_coverage(5),
                     drawn=[Region("R0", m, default_ramp(3), default_coverage(3)),
                            Region("R1", m, default_ramp(3), default_coverage(3))])
    projects.save_project("Same", b"P", ".png", two, _settings(), root=tmp_path)
    # re-save under the same name with only ONE drawn region
    one = RegionBook(default_ramp(5), default_coverage(5),
                     drawn=[Region("R0", m, default_ramp(3), default_coverage(3))])
    projects.save_project("Same", b"P", ".png", one, _settings(), root=tmp_path)
    assert not (tmp_path / "same" / "region_01.png").exists()
    assert len(projects.load_project("same", root=tmp_path).book.drawn) == 1


def test_delete_project_removes_folder_and_is_idempotent(tmp_path):
    projects.save_project("Gone", b"P", ".png", _whole_book(), _settings(), root=tmp_path)
    projects.delete_project("gone", root=tmp_path)
    assert not (tmp_path / "gone").exists()
    projects.delete_project("gone", root=tmp_path)  # no error second time


def test_list_skips_corrupt_manifest_but_load_raises(tmp_path):
    projects.save_project("Good", b"P", ".png", _whole_book(), _settings(), root=tmp_path)
    bad = tmp_path / "bad"; bad.mkdir()
    (bad / "manifest.json").write_text("{ not json", encoding="utf-8")
    assert [m.slug for m in projects.list_projects(root=tmp_path)] == ["good"]
    with pytest.raises(Exception):
        projects.load_project("bad", root=tmp_path)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.venv/Scripts/python -m pytest tests/test_projects.py -k "list_projects or overwrite or delete or corrupt" -v`
Expected: FAIL (`list_projects` / `delete_project` not defined).

- [ ] **Step 3: Write minimal implementation**

Rewrite `save_project` to build into a temp dir then swap, and add the two new functions:

```python
import os
import shutil


def save_project(name, photo_bytes, photo_suffix, book, settings,
                 root: Path = PROJECTS_DIR, _now: str | None = None) -> str:
    slug = slugify(name)
    root = Path(root)
    root.mkdir(parents=True, exist_ok=True)
    dest = root / slug
    tmp = root / f".tmp-{slug}"
    shutil.rmtree(tmp, ignore_errors=True)
    tmp.mkdir(parents=True)

    photo_file = f"photo{photo_suffix}"
    (tmp / photo_file).write_bytes(photo_bytes)

    drawn_entries = []
    for i, r in enumerate(book.drawn):
        mask_file = f"region_{i:02d}.png"
        _write_mask(tmp / mask_file, r.mask)
        drawn_entries.append({"name": r.name, "palette": _palette_to_dicts(r.palette),
                              "coverage": list(r.coverage), "mask_file": mask_file})

    now = _now or _now_iso()
    manifest = {
        "schema_version": SCHEMA_VERSION, "name": name, "slug": slug,
        "created_at": now, "updated_at": now, "photo_file": photo_file,
        "settings": _settings_to_dict(settings),
        "book": {"whole": {"palette": _palette_to_dicts(book.whole_palette),
                           "coverage": list(book.whole_coverage)},
                 "drawn": drawn_entries, "selected": book.selected},
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
```

Also make `load_project` raise on unparseable manifest — the existing `json.loads` already raises `json.JSONDecodeError`, so `test_list_skips_corrupt_manifest_but_load_raises` passes as-is.

- [ ] **Step 4: Run tests to verify they pass**

Run: `.venv/Scripts/python -m pytest tests/test_projects.py -v`
Expected: PASS (all tests).

- [ ] **Step 5: Commit**

```bash
git add src/mini_highlight_advisor/projects.py tests/test_projects.py
git commit -m "feat(projects): list/delete + atomic overwrite + corrupt-manifest handling"
```

---

### Task 5: UI panel + upload-gate integration (manual smoke)

Wire the core into the app: a "📁 Projects" expander for save/load/delete, and an upload gate that accepts a loaded project's photo. No automated test (Streamlit UI, per repo convention) — this task ends with a manual browser smoke test.

**Files:**
- Create: `ui/projects_panel.py`
- Modify: `ui/keys.py` (add project session keys), `app.py` (upload gate + render the panel)

**Interfaces:**
- Consumes: `projects.list_projects/save_project/load_project/delete_project`, `ProjectSettings`; `keys` from `ui`.
- Produces: `ui.projects_panel.render_save(book, photo_bytes, photo_suffix) -> None` and `ui.projects_panel.render_library() -> None` (or a single `render(...)` — implementer's call; keep save vs load/delete visually grouped).

**Notes for the implementer:**
- **New session keys** (add to `ui/keys.py`): `LOADED_PHOTO = "loaded_photo"` (holds `{"bytes": ..., "suffix": ...}` or absent), `LOADED_NAME = "loaded_project_name"`, plus widget keys `SAVE_PROJECT_NAME = "save_project_name"`, `LOAD_SELECT = "load_project_select"`.
- **Gathering settings for save** — read the live widget values from session (they are written by the results/palette panels earlier in the run):
  ```python
  from mini_highlight_advisor.projects import ProjectSettings
  settings = ProjectSettings(
      n=st.session_state.get(keys.N, 5),
      edge_hl=st.session_state.get(keys.EDGE_HL, True),
      edge_extreme=st.session_state.get(keys.EDGE_EXTREME, False),
      edge_sens=st.session_state.get(keys.EDGE_SENS, 0.5),
      relief_cap=st.session_state.get(keys.RELIEF_CAP, True),
      per_region_norm=st.session_state.get(keys.PER_REGION_NORM, False),
  )
  ```
- **On Load**, seed session then rerun so existing choreography rehydrates widgets:
  ```python
  lp = projects.load_project(slug)
  st.session_state[keys.LOADED_PHOTO] = {"bytes": lp.photo_bytes, "suffix": lp.photo_suffix}
  st.session_state[keys.LOADED_NAME] = <selected display name>
  st.session_state[keys.BOOK] = lp.book
  st.session_state[keys.N] = lp.settings.n
  st.session_state[keys.EDGE_HL] = lp.settings.edge_hl
  st.session_state[keys.EDGE_EXTREME] = lp.settings.edge_extreme
  st.session_state[keys.EDGE_SENS] = lp.settings.edge_sens
  st.session_state[keys.RELIEF_CAP] = lp.settings.relief_cap
  st.session_state[keys.PER_REGION_NORM] = lp.settings.per_region_norm
  st.session_state.pop(keys.LOADED_G, None)  # force region rehydrate from restored book
  for k in [k for k in list(st.session_state) if k.startswith(keys.RENAME_PREFIX)]:
      st.session_state.pop(k, None)
  st.rerun()
  ```
- **Overwrite confirm:** if `slugify(name)` matches an existing slug from `list_projects()`, show a warning + require a confirm checkbox before calling `save_project`.
- **Delete confirm:** same pattern — a confirm checkbox next to the Delete button.

- [ ] **Step 1: Add session keys to `ui/keys.py`**

```python
# --- projects (mini library) ---
LOADED_PHOTO = "loaded_photo"          # {"bytes":..., "suffix":...} for a loaded project
LOADED_NAME = "loaded_project_name"    # display name of the loaded project (save default)
SAVE_PROJECT_NAME = "save_project_name"
LOAD_SELECT = "load_project_select"
```

- [ ] **Step 2: Create `ui/projects_panel.py`**

```python
"""📁 Projects panel — save the current mini and reload/delete saved ones.

Streamlit glue only; all persistence lives in mini_highlight_advisor.projects.
"""
import streamlit as st

from mini_highlight_advisor import projects
from mini_highlight_advisor.projects import ProjectSettings
from ui import keys


def _current_settings() -> ProjectSettings:
    return ProjectSettings(
        n=st.session_state.get(keys.N, 5),
        edge_hl=st.session_state.get(keys.EDGE_HL, True),
        edge_extreme=st.session_state.get(keys.EDGE_EXTREME, False),
        edge_sens=st.session_state.get(keys.EDGE_SENS, 0.5),
        relief_cap=st.session_state.get(keys.RELIEF_CAP, True),
        per_region_norm=st.session_state.get(keys.PER_REGION_NORM, False),
    )


def render_library() -> None:
    """Load / delete existing projects. Render this BEFORE the upload gate."""
    with st.expander("📁 Projects — load a saved mini", expanded=False):
        metas = projects.list_projects()
        if not metas:
            st.caption("No saved projects yet. Save one below after setting up a mini.")
            return
        labels = {m.slug: f"{m.name}" for m in metas}
        slug = st.selectbox("Saved projects", [m.slug for m in metas],
                            format_func=lambda s: labels[s], key=keys.LOAD_SELECT)
        c_load, c_del = st.columns(2)
        if c_load.button("Load", type="primary"):
            lp = projects.load_project(slug)
            st.session_state[keys.LOADED_PHOTO] = {"bytes": lp.photo_bytes,
                                                   "suffix": lp.photo_suffix}
            st.session_state[keys.LOADED_NAME] = labels[slug]
            st.session_state[keys.BOOK] = lp.book
            st.session_state[keys.N] = lp.settings.n
            st.session_state[keys.EDGE_HL] = lp.settings.edge_hl
            st.session_state[keys.EDGE_EXTREME] = lp.settings.edge_extreme
            st.session_state[keys.EDGE_SENS] = lp.settings.edge_sens
            st.session_state[keys.RELIEF_CAP] = lp.settings.relief_cap
            st.session_state[keys.PER_REGION_NORM] = lp.settings.per_region_norm
            st.session_state.pop(keys.LOADED_G, None)
            for k in [k for k in list(st.session_state) if k.startswith(keys.RENAME_PREFIX)]:
                st.session_state.pop(k, None)
            st.rerun()
        if c_del.button("Delete") and st.checkbox("Confirm delete", key="confirm_del"):
            projects.delete_project(slug)
            st.rerun()


def render_save(photo_bytes: bytes, photo_suffix: str, book) -> None:
    """Save the current mini. Render this AFTER the book/settings exist this run."""
    with st.expander("💾 Save this mini as a project", expanded=False):
        default = st.session_state.get(keys.LOADED_NAME, "Untitled")
        name = st.text_input("Project name", value=default, key=keys.SAVE_PROJECT_NAME)
        existing = {m.slug for m in projects.list_projects()}
        try:
            will_overwrite = projects.slugify(name) in existing
        except ValueError:
            will_overwrite = False
        if will_overwrite:
            st.warning(f"A project named “{name}” exists — saving overwrites it.")
        ok = (not will_overwrite) or st.checkbox("Confirm overwrite", key="confirm_ow")
        if st.button("Save project", type="primary", disabled=not ok):
            try:
                projects.save_project(name, photo_bytes, photo_suffix, book,
                                      _current_settings())
                st.session_state[keys.LOADED_NAME] = name
                st.toast(f"Saved “{name}”.")
            except ValueError as e:
                st.error(str(e))
```

- [ ] **Step 3: Wire into `app.py`**

Modify the Miniature-tab body. Render the library BEFORE the uploader, make the upload gate fall back to a loaded photo, and render the save panel once `book`/settings exist. Replace the current upload block:

```python
with tab_mini:
    if "book" not in st.session_state:
        st.session_state["book"] = new_book(5)
    book: RegionBook = st.session_state["book"]

    projects_panel.render_library()

    uploaded = st.file_uploader("Mini photo", type=["png", "jpg", "jpeg"])
    if uploaded is not None:
        photo_bytes = uploaded.getvalue()
        photo_suffix = os.path.splitext(uploaded.name)[1]
        st.session_state.pop(keys.LOADED_PHOTO, None)   # new upload detaches loaded project
        st.session_state.pop(keys.LOADED_NAME, None)
    elif st.session_state.get(keys.LOADED_PHOTO):
        lp = st.session_state[keys.LOADED_PHOTO]
        photo_bytes, photo_suffix = lp["bytes"], lp["suffix"]
    else:
        st.info("Upload a photo of a primed miniature to begin, or load a saved project above.")
        st.stop()

    try:
        with st.spinner("Preparing shading (first run downloads the depth model if no alpha channel)..."):
            rgb, alpha, shading = helpers.shading(photo_bytes, photo_suffix)
        src_h, src_w = rgb.shape[:2]

        sel = regions_panel.render(book, rgb, shading, src_w, src_h)
        state.rehydrate_editor_widgets(book, sel)
        palette, n = palette_editor.render(book, sel, picked)
        coverage = coverage_editor.render(n)
        palette_editor.render_save_recipe(palette, n)
        book.set_palette_at(sel, palette)
        book.set_coverage_at(sel, coverage)
        results.render(rgb, alpha, book, palette, picked, owned_paints, shading)

        projects_panel.render_save(photo_bytes, photo_suffix, book)
    except Exception as e:
        st.error("Error processing image — see traceback below.")
        st.exception(e)
```

Add imports at the top of `app.py`: `from ui import (..., projects_panel, keys)` (extend the existing `ui` import tuple; `keys` is needed for `keys.LOADED_PHOTO`/`keys.LOADED_NAME`).

- [ ] **Step 4: Regression — run the full suite**

Run: `.venv/Scripts/python -m pytest -q`
Expected: PASS (no existing tests broken; `test_projects.py` green).

- [ ] **Step 5: Manual browser smoke test (user)**

Run: `streamlit run app.py`
Verify:
1. Upload the `fixtures/skaven-hero` photo, draw 1–2 regions, tweak a palette + band count + an edge toggle.
2. Open "💾 Save this mini as a project", name it, Save → toast appears.
3. Refresh the browser (state is lost from the editor).
4. Open "📁 Projects", select the saved project, Load → photo, regions, palettes, band count, and edge toggles all return as left.
5. Re-save under the same name → overwrite warning + confirm works. Delete → project disappears from the list.

- [ ] **Step 6: Commit**

```bash
git add ui/projects_panel.py ui/keys.py app.py
git commit -m "feat(ui): projects panel + upload-gate integration for mini library"
```

---

## Self-Review

**Spec coverage:**
- On-disk folder format (manifest/photo/PNG masks) → Tasks 2–3. ✅
- Core `projects.py` API (slugify, list/save/load/delete, dataclasses) → Tasks 1–4. ✅
- Atomic save + overwrite-by-name + corrupt-manifest handling → Task 4. ✅
- Global settings persisted (n, edges, relief_cap, per_region_norm) → Tasks 2 & 5. ✅
- UI panel (save/load/delete, overwrite/delete confirms) → Task 5. ✅
- Upload-gate change (loaded photo supplies image; new upload detaches) → Task 5. ✅
- Owned paints / recipes stay global (not touched) → honored (no task copies them). ✅
- Testing: full core unit coverage + manual UI smoke → Tasks 1–4 (unit), Task 5 (smoke). ✅
- Thumbnail stretch explicitly deferred → not planned (correct). ✅

**Placeholder scan:** No TBD/TODO; every code step has runnable code. ✅

**Type consistency:** `ProjectSettings`, `ProjectMeta`, `LoadedProject`, `save_project`/`load_project`/`list_projects`/`delete_project` signatures, `_write_mask`/`_read_mask`, and `_palette_to_dicts`/`_from_dicts` are consistent across tasks; session key names (`LOADED_PHOTO`, `LOADED_NAME`, `SAVE_PROJECT_NAME`, `LOAD_SELECT`) match between `keys.py` and `projects_panel.py`/`app.py`. ✅
