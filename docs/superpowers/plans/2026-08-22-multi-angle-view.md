# Multi-Angle View (#8) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Let one project hold a miniature photographed from several angles, each running the existing single-photo pipeline independently, with a shared paint pool across angles.

**Architecture:** "Active-angle swap" — the existing editor is untouched and always operates on the *active* angle. Session holds an `angles` list (source of truth) + an active index; switching angle flushes the live editor state into the active record and loads the selected one, mirroring the proven per-region swap in `ui/state.py`. Persistence bumps to schema v2 (one subdir per angle); the paint pool is shared (the existing `owned` list, now persisted). Settings are per-angle. The combined multi-angle view (#12) is out of scope but the persisted `angles` list makes it a pure read-only add later.

**Tech Stack:** Python, NumPy, Pillow, Streamlit 1.61.x, pytest.

**Spec:** `docs/superpowers/specs/2026-08-22-multi-angle-view-design.md`

## Global Constraints

- Streamlit pinned `streamlit==1.61.*`; no new runtime dependencies (numpy, opencv-python, pillow, streamlit, streamlit-drawable-canvas only).
- Persistence types stay **pure** (no Streamlit import in `src/mini_highlight_advisor/`).
- Atomic save contract preserved: write to `.tmp-<slug>`, then `os.replace` onto `<slug>`.
- Session-state key *string values* are frozen once shipped (tests lock them) — see `ui/keys.py` docstring.
- One dataclass `AngleData` serves both session and persistence — do not introduce a second "AngleState" twin.
- `SCHEMA_VERSION = 2`; v1 projects load via in-memory adaptation and upgrade to v2 on next save.
- TDD: pure logic (Tasks 1–3) is unit-tested; Streamlit glue (Tasks 4–6) is verified by keeping the full `pytest` suite green plus the manual smoke checklist in each task.

---

### Task 1: AngleData + angle (de)serialization helpers (pure)

Add the angle dataclass and pure serialize/deserialize helpers to `projects.py` **without** touching `save_project`/`load_project` yet — additive, nothing breaks.

**Files:**
- Modify: `src/mini_highlight_advisor/projects.py`
- Test: `tests/test_projects.py`

**Interfaces:**
- Consumes: existing `_palette_to_dicts`, `_palette_from_dicts`, `_write_mask`, `_read_mask`, `_settings_to_dict`, `_settings_from_dict`, `ProjectSettings`, `RegionBook`, `Region`.
- Produces:
  - `@dataclass class AngleData: label: str; photo_bytes: bytes; photo_suffix: str; book: RegionBook; settings: ProjectSettings`
  - `_write_angle(project_dir: Path, idx: int, a: AngleData) -> dict` — writes `project_dir/angle_<idx:02d>/` (photo + masks) and returns the manifest entry.
  - `_read_angle(project_dir: Path, idx: int, entry: dict) -> AngleData` — inverse.

- [ ] **Step 1: Write the failing test**

```python
def test_angle_write_read_roundtrip_bit_identical(tmp_path):
    from mini_highlight_advisor.region_state import RegionBook
    from mini_highlight_advisor.regions import Region
    from mini_highlight_advisor.palette import default_ramp, default_coverage
    m0 = np.zeros((6, 8), dtype=bool); m0[1:3, 2:5] = True
    book = RegionBook(default_ramp(5), default_coverage(5),
                      drawn=[Region("Cloak", m0, default_ramp(4), default_coverage(4))],
                      selected=1)
    a = projects.AngleData(label="front", photo_bytes=b"PB", photo_suffix=".png",
                           book=book, settings=_settings())
    entry = projects._write_angle(tmp_path, 0, a)
    assert entry["label"] == "front"
    assert (tmp_path / "angle_00" / "photo.png").read_bytes() == b"PB"
    out = projects._read_angle(tmp_path, 0, entry)
    assert out.label == "front"
    assert out.photo_bytes == b"PB"
    assert out.photo_suffix == ".png"
    assert out.settings == _settings()
    assert out.book.drawn[0].name == "Cloak"
    assert np.array_equal(out.book.drawn[0].mask, m0)
    assert out.book.selected == 1
```

(`_settings()` already exists at the top of `tests/test_projects.py`.)

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_projects.py::test_angle_write_read_roundtrip_bit_identical -v`
Expected: FAIL — `AttributeError: module ... has no attribute 'AngleData'`.

- [ ] **Step 3: Write minimal implementation**

Add near the other dataclasses in `projects.py`:

```python
@dataclass(frozen=True)
class AngleData:
    label: str
    photo_bytes: bytes
    photo_suffix: str
    book: RegionBook
    settings: ProjectSettings
```

Add the helpers (place after `_settings_from_dict`):

```python
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
                      "coverage": list(r.coverage), "mask_file": mask_file})
    return {
        "label": a.label,
        "photo_file": photo_file,
        "settings": _settings_to_dict(a.settings),
        "book": {"whole": {"palette": _palette_to_dicts(a.book.whole_palette),
                           "coverage": list(a.book.whole_coverage)},
                 "drawn": drawn, "selected": a.book.selected},
    }


def _read_angle(project_dir: Path, idx: int, entry: dict) -> AngleData:
    angle_dir = Path(project_dir) / f"angle_{idx:02d}"
    photo_bytes = (angle_dir / entry["photo_file"]).read_bytes()
    photo_suffix = Path(entry["photo_file"]).suffix
    b = entry["book"]
    drawn = [
        Region(name=d["name"], mask=_read_mask(angle_dir / d["mask_file"]),
               palette=_palette_from_dicts(d["palette"]), coverage=list(d["coverage"]))
        for d in b["drawn"]
    ]
    book = RegionBook(whole_palette=_palette_from_dicts(b["whole"]["palette"]),
                      whole_coverage=list(b["whole"]["coverage"]),
                      drawn=drawn, selected=b["selected"])
    return AngleData(label=entry["label"], photo_bytes=photo_bytes,
                     photo_suffix=photo_suffix, book=book,
                     settings=_settings_from_dict(entry["settings"]))
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_projects.py::test_angle_write_read_roundtrip_bit_identical -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add src/mini_highlight_advisor/projects.py tests/test_projects.py
git commit -m "feat(projects): AngleData + per-angle (de)serialization helpers"
```

---

### Task 2: Schema v2 save/load + v1 migration + active-index helper

Rewrite `save_project`/`load_project` to the multi-angle v2 format, adapt v1 manifests on read, and add the pure `next_active_index` helper. This changes the `save_project` signature and the `LoadedProject` shape; existing tests and callers are updated here (the UI callers are re-wired in Task 6 — the app's save/load path is expected to be broken between this task and Task 6, but the test suite stays green).

**Files:**
- Modify: `src/mini_highlight_advisor/projects.py`
- Test: `tests/test_projects.py`

**Interfaces:**
- Consumes: Task 1's `AngleData`, `_write_angle`, `_read_angle`.
- Produces:
  - `SCHEMA_VERSION = 2`
  - `@dataclass class LoadedProject: paints_pool: list[str]; active_angle: int; angles: list[AngleData]`
  - `save_project(name: str, paints_pool: list[str], active_angle: int, angles: list[AngleData], root=PROJECTS_DIR, _now: str | None = None) -> str`
  - `load_project(slug: str, root=PROJECTS_DIR) -> LoadedProject`
  - `next_active_index(active: int, removed: int, count_before: int) -> int`

- [ ] **Step 1: Write the failing tests**

Replace the existing `LoadedProject`-shaped round-trip tests and add the new ones. New/updated tests:

```python
def _angle(label="front", photo=b"PB", suffix=".png", book=None):
    book = book if book is not None else _whole_book()
    return projects.AngleData(label, photo, suffix, book, _settings())


def test_v2_multi_angle_roundtrip(tmp_path):
    from mini_highlight_advisor.region_state import RegionBook
    from mini_highlight_advisor.regions import Region
    from mini_highlight_advisor.palette import default_ramp, default_coverage
    m = np.zeros((5, 5), dtype=bool); m[1:3, 1:3] = True
    back_book = RegionBook(default_ramp(5), default_coverage(5),
                           drawn=[Region("Cape", m, default_ramp(4), default_coverage(4))],
                           selected=1)
    angles = [_angle("front", b"FRONT"), _angle("back", b"BACK", book=back_book)]
    slug = projects.save_project("Skaven Hero", ["70.950", "72.001"], 1, angles,
                                 root=tmp_path)
    assert slug == "skaven-hero"
    lp = projects.load_project(slug, root=tmp_path)
    assert lp.paints_pool == ["70.950", "72.001"]
    assert lp.active_angle == 1
    assert [a.label for a in lp.angles] == ["front", "back"]
    assert lp.angles[0].photo_bytes == b"FRONT"
    assert lp.angles[1].book.drawn[0].name == "Cape"
    assert np.array_equal(lp.angles[1].book.drawn[0].mask, m)


def test_v2_overwrite_is_atomic(tmp_path):
    projects.save_project("Mini", [], 0, [_angle("a", b"ONE")], root=tmp_path)
    projects.save_project("Mini", [], 0, [_angle("a", b"TWO")], root=tmp_path)
    lp = projects.load_project("mini", root=tmp_path)
    assert len(lp.angles) == 1
    assert lp.angles[0].photo_bytes == b"TWO"
    assert not (tmp_path / ".tmp-mini").exists()


def test_v1_manifest_loads_as_single_angle(tmp_path):
    # Hand-write a legacy v1 project on disk.
    import json
    from mini_highlight_advisor.palette import default_ramp, default_coverage
    d = tmp_path / "legacy"; d.mkdir()
    (d / "photo.png").write_bytes(b"LEGACY")
    manifest = {
        "schema_version": 1, "name": "Legacy Mini", "slug": "legacy",
        "created_at": "t", "updated_at": "t", "photo_file": "photo.png",
        "settings": projects._settings_to_dict(_settings()),
        "book": {"whole": {"palette": projects._palette_to_dicts(default_ramp(5)),
                           "coverage": list(default_coverage(5))},
                 "drawn": [], "selected": 0},
    }
    (d / "manifest.json").write_text(json.dumps(manifest), encoding="utf-8")
    lp = projects.load_project("legacy", root=tmp_path)
    assert lp.paints_pool == []
    assert lp.active_angle == 0
    assert len(lp.angles) == 1
    assert lp.angles[0].label == "Legacy Mini"
    assert lp.angles[0].photo_bytes == b"LEGACY"
    assert lp.angles[0].settings == _settings()


@pytest.mark.parametrize("active,removed,count,expected", [
    (0, 0, 1, 0),   # removing the only angle
    (2, 0, 3, 1),   # active after removed shifts down
    (1, 2, 3, 1),   # active before removed unchanged
    (2, 2, 3, 1),   # removing the active picks the previous
    (0, 1, 3, 0),   # active before removed unchanged (at 0)
])
def test_next_active_index(active, removed, count, expected):
    assert projects.next_active_index(active, removed, count) == expected
```

Delete/replace the old v1-signature tests that call `save_project(name, bytes, suffix, book, settings, ...)` and assert on `loaded.photo_bytes` / `loaded.book` directly (`test_save_then_load_whole_mini_roundtrip`, `test_drawn_regions_roundtrip_masks_bit_identical`, and any other caller of the old signature) — the new `test_v2_multi_angle_roundtrip` covers the same ground through the new API.

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/test_projects.py -v`
Expected: the new tests FAIL (`save_project` old signature / no `next_active_index` / `LoadedProject` has no `angles`).

- [ ] **Step 3: Write the implementation**

In `projects.py`: bump `SCHEMA_VERSION = 2`; replace the `LoadedProject` dataclass; replace `save_project` and `load_project`; add `_adapt_v1` and `next_active_index`:

```python
SCHEMA_VERSION = 2


@dataclass(frozen=True)
class LoadedProject:
    paints_pool: list[str]
    active_angle: int
    angles: list[AngleData]


def save_project(name, paints_pool, active_angle, angles,
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
    }
    (tmp / "manifest.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    shutil.rmtree(dest, ignore_errors=True)
    os.replace(tmp, dest)
    return slug


def _adapt_v1(m: dict, project_dir: Path) -> LoadedProject:
    photo_bytes = (project_dir / m["photo_file"]).read_bytes()
    photo_suffix = Path(m["photo_file"]).suffix
    b = m["book"]
    drawn = [
        Region(name=d["name"], mask=_read_mask(project_dir / d["mask_file"]),
               palette=_palette_from_dicts(d["palette"]), coverage=list(d["coverage"]))
        for d in b["drawn"]
    ]
    book = RegionBook(whole_palette=_palette_from_dicts(b["whole"]["palette"]),
                      whole_coverage=list(b["whole"]["coverage"]),
                      drawn=drawn, selected=b["selected"])
    angle = AngleData(label=m.get("name", "angle 1"), photo_bytes=photo_bytes,
                      photo_suffix=photo_suffix, book=book,
                      settings=_settings_from_dict(m["settings"]))
    return LoadedProject(paints_pool=[], active_angle=0, angles=[angle])


def load_project(slug: str, root: Path = PROJECTS_DIR) -> LoadedProject:
    mpath = _manifest_path(Path(root), slug)
    if not mpath.exists():
        raise FileNotFoundError(f"no project manifest at {mpath}")
    m = json.loads(mpath.read_text(encoding="utf-8"))
    project_dir = mpath.parent
    if m.get("schema_version", 1) < 2:
        return _adapt_v1(m, project_dir)
    angles = [_read_angle(project_dir, i, e) for i, e in enumerate(m["angles"])]
    return LoadedProject(paints_pool=list(m.get("paints_pool", [])),
                         active_angle=m.get("active_angle", 0), angles=angles)


def next_active_index(active: int, removed: int, count_before: int) -> int:
    """New active index after removing `removed` from a list of size `count_before`."""
    if count_before <= 1:
        return 0
    if active > removed:
        return active - 1
    if active == removed:
        return max(0, removed - 1)
    return active
```

- [ ] **Step 4: Run the full project-tests file**

Run: `pytest tests/test_projects.py -v`
Expected: PASS (all, including the parametrized `next_active_index`).

- [ ] **Step 5: Commit**

```bash
git add src/mini_highlight_advisor/projects.py tests/test_projects.py
git commit -m "feat(projects): schema v2 multi-angle save/load + v1 migration"
```

---

### Task 3: Session keys for angles

Add the new session-state keys and lock them with a test.

**Files:**
- Modify: `ui/keys.py`
- Test: `tests/test_ui_keys.py`

**Interfaces:**
- Produces: `keys.ANGLES = "angles"`, `keys.ACTIVE_ANGLE = "active_angle"`, `keys.ANGLE_SELECT = "angle_select"`, `keys.angle_label(i) -> str`.

- [ ] **Step 1: Write the failing test**

Add to `tests/test_ui_keys.py`:

```python
def test_angle_keys_are_frozen():
    from ui import keys
    assert keys.ANGLES == "angles"
    assert keys.ACTIVE_ANGLE == "active_angle"
    assert keys.ANGLE_SELECT == "angle_select"
    assert keys.angle_label(0) == "angle_label_0"
    assert keys.angle_label(3) == "angle_label_3"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_ui_keys.py::test_angle_keys_are_frozen -v`
Expected: FAIL — `AttributeError: ... has no attribute 'ANGLES'`.

- [ ] **Step 3: Write the implementation**

In `ui/keys.py`, under the projects section add:

```python
# --- angles (multi-angle view) ---
ANGLES = "angles"                # list[AngleData] in session: the angle records
ACTIVE_ANGLE = "active_angle"    # int index into ANGLES of the active angle
ANGLE_SELECT = "angle_select"    # active-angle selector widget key
```

And with the other per-index builders:

```python
def angle_label(i: int) -> str: return f"angle_label_{i}"
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_ui_keys.py -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add ui/keys.py tests/test_ui_keys.py
git commit -m "feat(ui): session keys for multi-angle view"
```

---

### Task 4: Angle swap in ui/state.py + app.py bootstrap

Introduce the active-angle concept into the app: session holds an `ANGLES` list of `AngleData`; the active angle's `book`/`settings`/photo mirror into the live editor keys; a swap helper flushes and reloads on switch. First upload creates angle 0, so single-photo behaviour is unchanged.

**Files:**
- Modify: `ui/state.py`, `app.py`
- Test: manual smoke (Streamlit glue) + full `pytest` suite stays green.

**Interfaces:**
- Consumes: `projects.AngleData`, `projects.ProjectSettings`, `keys.ANGLES`, `keys.ACTIVE_ANGLE`, `keys.BOOK`, `keys.LOADED_PHOTO`, the settings keys (`N`, `EDGE_HL`, `EDGE_EXTREME`, `EDGE_SENS`, `RELIEF_CAP`, `PER_REGION_NORM`), `region_state.new_book`.
- Produces:
  - `state.seed_editor_from_angle(a: AngleData) -> None` — copies an `AngleData`'s book/settings/photo into the live session keys and resets `LOADED_G`/`REGION_RADIO`/`RENAME_*`.
  - `state.flush_editor_into_angle(a: AngleData) -> AngleData` — returns a new `AngleData` with `settings` rebuilt from the current widget keys (label/photo/book carried over; `book` is shared by reference).
  - `state.load_angle_into_editor(idx: int) -> None` — flush active, seed `idx`, set `ACTIVE_ANGLE`, `st.rerun()`.

- [ ] **Step 1: Write the swap helpers in `ui/state.py`**

Add (importing `projects` and `region_state` at the top of the file alongside the existing imports):

```python
from mini_highlight_advisor import projects
from mini_highlight_advisor.region_state import RegionBook


def _current_settings() -> projects.ProjectSettings:
    return projects.ProjectSettings(
        n=st.session_state.get(keys.N, 5),
        edge_hl=st.session_state.get(keys.EDGE_HL, True),
        edge_extreme=st.session_state.get(keys.EDGE_EXTREME, False),
        edge_sens=st.session_state.get(keys.EDGE_SENS, 0.5),
        relief_cap=st.session_state.get(keys.RELIEF_CAP, True),
        per_region_norm=st.session_state.get(keys.PER_REGION_NORM, False),
    )


def seed_editor_from_angle(a) -> None:
    st.session_state[keys.BOOK] = a.book
    st.session_state[keys.LOADED_PHOTO] = {"bytes": a.photo_bytes, "suffix": a.photo_suffix}
    st.session_state[keys.N] = a.settings.n
    st.session_state[keys.EDGE_HL] = a.settings.edge_hl
    st.session_state[keys.EDGE_EXTREME] = a.settings.edge_extreme
    st.session_state[keys.EDGE_SENS] = a.settings.edge_sens
    st.session_state[keys.RELIEF_CAP] = a.settings.relief_cap
    st.session_state[keys.PER_REGION_NORM] = a.settings.per_region_norm
    st.session_state.pop(keys.LOADED_G, None)
    st.session_state.pop(keys.REGION_RADIO, None)
    for k in [k for k in list(st.session_state) if k.startswith(keys.RENAME_PREFIX)]:
        st.session_state.pop(k, None)


def flush_editor_into_angle(a):
    return projects.AngleData(label=a.label, photo_bytes=a.photo_bytes,
                              photo_suffix=a.photo_suffix, book=st.session_state[keys.BOOK],
                              settings=_current_settings())


def load_angle_into_editor(idx: int) -> None:
    angles = st.session_state[keys.ANGLES]
    active = st.session_state.get(keys.ACTIVE_ANGLE, 0)
    if idx == active:
        return
    angles[active] = flush_editor_into_angle(angles[active])
    seed_editor_from_angle(angles[idx])
    st.session_state[keys.ACTIVE_ANGLE] = idx
    st.rerun()
```

(`keys.N`, `EDGE_*`, `RELIEF_CAP`, `PER_REGION_NORM`, `LOADED_G`, `REGION_RADIO`, `RENAME_PREFIX` already exist in `ui/keys.py`.)

- [ ] **Step 2: Rewire the top of `app.py` to bootstrap angles**

Replace the current book-init + uploader block in the `with tab_mini:` body. New flow:

```python
with tab_mini:
    st.session_state.setdefault(keys.ANGLES, [])
    st.session_state.setdefault(keys.ACTIVE_ANGLE, 0)

    projects_panel.render_library()

    angles = st.session_state[keys.ANGLES]

    if not angles:
        uploaded = st.file_uploader("Mini photo", type=["png", "jpg", "jpeg"])
        if uploaded is None:
            st.info("Upload a photo of a primed miniature to begin, or load a saved project above.")
            st.stop()
        a = projects.AngleData(label="angle 1", photo_bytes=uploaded.getvalue(),
                               photo_suffix=os.path.splitext(uploaded.name)[1],
                               book=new_book(5), settings=state._current_settings())
        st.session_state[keys.ANGLES] = [a]
        st.session_state[keys.ACTIVE_ANGLE] = 0
        state.seed_editor_from_angle(a)
        st.rerun()

    active_idx = angles_panel.render()          # Task 5 provides this; see note
    active = st.session_state[keys.ANGLES][active_idx]
    book = st.session_state[keys.BOOK]
    photo_bytes, photo_suffix = active.photo_bytes, active.photo_suffix
```

Add `from mini_highlight_advisor import projects` and `from mini_highlight_advisor.region_state import new_book` (already imported) and `angles_panel` to the `ui` import list. **Until Task 5 lands**, temporarily stub the active selector inline so the app runs:

```python
    # TEMP until Task 5: no angle bar yet, just use the active index as-is.
    active_idx = st.session_state[keys.ACTIVE_ANGLE]
```

Keep the rest of the body (`helpers.shading(...)` onward through `results.render(...)`) unchanged — it now reads `book`/`photo_bytes` from the active angle. The `render_save` call is updated in Task 6.

- [ ] **Step 3: Verify the suite stays green**

Run: `pytest -q`
Expected: PASS (no test imports `app.py`; `ui/state.py` new code is import-safe).

- [ ] **Step 4: Manual smoke**

Run: `streamlit run app.py`
Checklist:
- Upload one photo → editor appears, regions/palette/coverage/results work exactly as before.
- Draw a region, edit its palette → results reflect it (single-angle parity).

- [ ] **Step 5: Commit**

```bash
git add ui/state.py app.py
git commit -m "feat(ui): active-angle swap helpers + app bootstrap (single-angle parity)"
```

---

### Task 5: Angle bar panel (add / switch / rename / remove)

Add the UI that lists angles, switches the active one, adds a new angle (upload), renames, and removes.

**Files:**
- Create: `ui/angles_panel.py`
- Modify: `app.py` (replace the Task 4 temp stub with `angles_panel.render()`)
- Test: manual smoke + full `pytest` suite stays green.

**Interfaces:**
- Consumes: `keys.ANGLES`, `keys.ACTIVE_ANGLE`, `keys.ANGLE_SELECT`, `keys.angle_label`, `state.load_angle_into_editor`, `state.flush_editor_into_angle`, `state.seed_editor_from_angle`, `projects.AngleData`, `projects.next_active_index`, `region_state.new_book`.
- Produces: `angles_panel.render() -> int` — returns the active angle index; renders the angle bar and handles add/switch/rename/remove (each mutating action ends in `st.rerun()`).

- [ ] **Step 1: Implement `ui/angles_panel.py`**

```python
"""🧭 Angle bar — switch/add/rename/remove the angles of the current mini.

Streamlit glue only; angle state lives in st.session_state[keys.ANGLES] as a
list of projects.AngleData, with keys.ACTIVE_ANGLE the active index.
"""
import os

import streamlit as st

from mini_highlight_advisor import projects
from mini_highlight_advisor.region_state import new_book
from ui import keys, state


def render() -> int:
    angles = st.session_state[keys.ANGLES]
    active = st.session_state.get(keys.ACTIVE_ANGLE, 0)

    st.markdown("**Angles**")
    labels = [a.label for a in angles]
    picked = st.radio("Active angle", list(range(len(angles))),
                      index=active, format_func=lambda i: labels[i],
                      horizontal=True, key=keys.ANGLE_SELECT)
    if picked != active:
        state.load_angle_into_editor(picked)   # flush + seed + rerun

    c_rename, c_remove = st.columns([3, 1])
    new_label = c_rename.text_input("Rename angle", value=labels[active],
                                    key=keys.angle_label(active))
    if new_label.strip() and new_label != labels[active]:
        angles[active] = projects.AngleData(
            label=new_label.strip(), photo_bytes=angles[active].photo_bytes,
            photo_suffix=angles[active].photo_suffix, book=angles[active].book,
            settings=angles[active].settings)
        st.rerun()

    if c_remove.button("🗑️ Remove", disabled=len(angles) == 1):
        new_active = projects.next_active_index(active, active, len(angles))
        angles.pop(active)
        st.session_state[keys.ACTIVE_ANGLE] = new_active
        state.seed_editor_from_angle(angles[new_active])
        st.rerun()

    with st.expander("➕ Add another angle", expanded=False):
        up = st.file_uploader("New angle photo", type=["png", "jpg", "jpeg"],
                              key="add_angle_uploader")
        if up is not None:
            # persist edits to the current angle before switching to the new one
            angles[active] = state.flush_editor_into_angle(angles[active])
            a = projects.AngleData(label=f"angle {len(angles) + 1}",
                                   photo_bytes=up.getvalue(),
                                   photo_suffix=os.path.splitext(up.name)[1],
                                   book=new_book(5), settings=angles[active].settings)
            angles.append(a)
            st.session_state[keys.ACTIVE_ANGLE] = len(angles) - 1
            state.seed_editor_from_angle(a)
            st.rerun()

    return st.session_state[keys.ACTIVE_ANGLE]
```

- [ ] **Step 2: Wire it into `app.py`**

Remove the Task 4 temp stub and its comment; ensure `angles_panel` is in the `ui` import list so `active_idx = angles_panel.render()` runs. `render()` returns the (possibly changed) active index for the rest of the body.

- [ ] **Step 3: Verify the suite stays green**

Run: `pytest -q`
Expected: PASS.

- [ ] **Step 4: Manual smoke**

Run: `streamlit run app.py`
Checklist:
- Upload front photo → "angle 1" appears in the bar.
- Add angle → upload back photo → "angle 2" becomes active; its regions/palette are fresh; results reflect the back photo.
- Switch back to angle 1 → its regions/palette/settings are exactly as left (swap works, no bleed).
- Rename an angle → label updates in the radio.
- Remove an angle → a neighbour becomes active; the "Remove" button is disabled when only one angle remains.

- [ ] **Step 5: Commit**

```bash
git add ui/angles_panel.py app.py
git commit -m "feat(ui): angle bar — add/switch/rename/remove angles"
```

---

### Task 6: Persist all angles + shared paint pool (save/load wiring)

Make Save serialize every angle + the shared paint pool + active index, and make Load restore them into session and seed the editor from the active angle.

**Files:**
- Modify: `ui/projects_panel.py`, `app.py`
- Test: manual smoke + full `pytest` suite stays green.

**Interfaces:**
- Consumes: `projects.save_project(name, paints_pool, active_angle, angles, ...)`, `projects.load_project(slug) -> LoadedProject`, `keys.ANGLES`, `keys.ACTIVE_ANGLE`, `keys.OWNED`, `state.flush_editor_into_angle`, `state.seed_editor_from_angle`.
- Produces: `render_save()` (new signature — no photo/book args) and an updated `render_library()` Load branch.

- [ ] **Step 1: Rewrite `render_save` in `ui/projects_panel.py`**

Replace `_current_settings` usage and the body of `render_save`. The paint pool is the owned-paints selection in `st.session_state[keys.OWNED]` (list of catalogue codes; default `[]`).

```python
from ui import state  # add to imports


def render_save() -> None:
    """Save the whole mini (all angles + shared paint pool). Render AFTER the editor."""
    with st.expander("💾 Save this mini as a project", expanded=False):
        default = st.session_state.get(keys.LOADED_NAME, "Untitled")
        name = st.text_input("Project name", value=default, key=keys.SAVE_PROJECT_NAME)
        existing = {m.slug for m in projects.list_projects()}
        try:
            will_overwrite = projects.slugify(name) in existing
        except ValueError:
            will_overwrite = False
        if will_overwrite:
            st.warning(f"A project named \"{name}\" exists — saving overwrites it.")
        ok = (not will_overwrite) or st.checkbox("Confirm overwrite", key=f"confirm_ow_{name}")
        if st.button("Save project", type="primary", disabled=not ok):
            angles = st.session_state[keys.ANGLES]
            active = st.session_state.get(keys.ACTIVE_ANGLE, 0)
            # flush live edits of the active angle before serializing
            angles[active] = state.flush_editor_into_angle(angles[active])
            pool = list(st.session_state.get(keys.OWNED, []))
            try:
                projects.save_project(name, pool, active, angles)
                st.session_state[keys.LOADED_NAME] = name
                st.toast(f"Saved \"{name}\".")
            except ValueError as e:
                st.error(str(e))
```

Delete the now-unused `_current_settings` helper in `projects_panel.py` (settings are captured via `state.flush_editor_into_angle`).

- [ ] **Step 2: Rewrite the Load branch in `render_library`**

Replace the `if c_load.button("Load", ...)` body:

```python
        if c_load.button("Load", type="primary"):
            lp = projects.load_project(slug)
            st.session_state[keys.ANGLES] = list(lp.angles)
            st.session_state[keys.ACTIVE_ANGLE] = lp.active_angle
            st.session_state[keys.OWNED] = list(lp.paints_pool)
            st.session_state[keys.LOADED_NAME] = labels[slug]
            state.seed_editor_from_angle(lp.angles[lp.active_angle])
            st.rerun()
```

- [ ] **Step 3: Update the `render_save()` call site in `app.py`**

Change `projects_panel.render_save(photo_bytes, photo_suffix, book)` to `projects_panel.render_save()`. Remove any now-dead `photo_bytes`/`photo_suffix`/`book` locals only if unused elsewhere (they are still read by `helpers.shading` and `results.render`, so keep them).

- [ ] **Step 4: Verify the suite stays green**

Run: `pytest -q`
Expected: PASS.

- [ ] **Step 5: Manual smoke**

Run: `streamlit run app.py`
Checklist:
- Build a 2-angle mini, set owned paints in the Paints tab, draw a region on each angle.
- Save as "Test Mini".
- Reload the page, Load "Test Mini" → both angles present with their regions/palettes; owned-paints pool restored; active angle is the one that was active at save.
- Load a **pre-existing v1 project** (saved before this branch) → opens as a single angle labelled with its old name; re-save → reopens identically (now v2 on disk).

- [ ] **Step 6: Commit**

```bash
git add ui/projects_panel.py app.py
git commit -m "feat(ui): persist all angles + shared paint pool"
```

---

## Self-Review

**Spec coverage:**
- §4 active-angle swap → Tasks 4, 5. §5.1 session keys → Task 3. §5.2 on-disk layout → Task 1 (`_write_angle` subdirs). §5.3 manifest v2 → Task 2. §5.4 v1 migration → Task 2 (`_adapt_v1`, `test_v1_manifest_loads_as_single_angle`). §5 shared pool via `OWNED` → Task 6. §6 file-by-file → Tasks 1–6. §7 UX flow → Tasks 4–6. §8 edge cases: remove-active → Task 2 `next_active_index` + Task 5; missing photo → covered by `_read_angle` raising; atomic overwrite → Task 2 `test_v2_overwrite_is_atomic`; v1 load → Task 2. §9 testing → Tasks 1–3 unit, 4–6 smoke. §10 open questions: code-less custom pool paints → documented limitation (pool stores catalogue codes only, `keys.OWNED`); angle-bar widget → radio chosen (Task 5). §11 out-of-scope (#12) → not built; persisted `angles` list leaves it a read-only add.
- **Gap noted & accepted:** app save/load path is broken between Task 2 (signature change) and Task 6 (re-wiring). Tasks 4–5 keep the app runnable for *editing*; save/load is smoke-tested only at Task 6. This is an intentional, sequenced window, not a missing task.

**Placeholder scan:** No TBD/TODO/"handle edge cases". The one `# TEMP until Task 5` stub in Task 4 is explicit, has real code, and is removed in Task 5 Step 2.

**Type consistency:** `AngleData(label, photo_bytes, photo_suffix, book, settings)` used identically in Tasks 1, 2, 4, 5. `save_project(name, paints_pool, active_angle, angles)` and `LoadedProject(paints_pool, active_angle, angles)` consistent across Tasks 2 and 6. `next_active_index(active, removed, count_before)` defined in Task 2, consumed in Task 5. `seed_editor_from_angle` / `flush_editor_into_angle` / `load_angle_into_editor` names consistent across Tasks 4–6.
