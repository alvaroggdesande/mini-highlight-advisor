# Scheme Experimenter Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Let the user save the current per-region colour setup as a named scheme, keep several, and swap the whole mini's colours in one click to compare highlight placement.

**Architecture:** A new torch-free core module `schemes.py` snapshots `{region_name → palette}` from a `RegionBook` and applies a snapshot back onto a book (name-matched, mismatch-tolerant). Schemes persist inside the mini-project `manifest.json` (schema v2 → v3). A thin Streamlit panel (`ui/schemes_panel.py`) provides quick-swap: save-current, a radio list of saved schemes, Apply, Rename, Delete.

**Tech Stack:** Python 3.11, numpy, Streamlit; pytest via `.venv/Scripts/python -m pytest`.

**Spec:** `docs/superpowers/specs/2026-09-01-scheme-experimenter-design.md`

## Global Constraints

- **Core is torch-free / Streamlit-free.** `schemes.py` imports only stdlib + `mini_highlight_advisor` types. No `streamlit` import in the core module.
- **Region identity is the region *name*** (`WHOLE_MINI` for index 0; user-given name for drawn regions). `Region`/`RegionBook` carry no stable id.
- **A scheme captures palette only** — not coverage, not material. Coverage/material stay live per-region settings.
- **`PaintColor` is a frozen dataclass** — immutable. A `list(palette)` copy is a complete, safe snapshot; do NOT deepcopy elements.
- **`apply` never raises on mismatch** — it applies what matches and returns a report.
- **Back-compat:** projects without a `schemes` key load with `schemes == []`; no migration.
- **Never build on `main`.** Work on branch `feat/scheme-experimenter`; feature branch → PR.
- Run tests with `.venv/Scripts/python -m pytest`.

---

### Task 1: Core `schemes.py` — snapshot & apply

**Files:**
- Create: `src/mini_highlight_advisor/schemes.py`
- Test: `tests/test_schemes.py`

**Interfaces:**
- Consumes: `RegionBook` (`.names() -> list[str]`, `.palette_at(g) -> list[PaintColor]`, `.set_palette_at(g, palette)`), `PaintColor` (frozen), `new_book`/`RegionBook.add` for tests.
- Produces:
  - `Scheme(name: str, palettes: dict[str, list[PaintColor]], anchor: str | None = None)` — mutable dataclass.
  - `ApplyReport(updated: list[str], skipped_regions: list[str], unused_keys: list[str])`.
  - `snapshot(book: RegionBook, name: str, anchor: str | None = None) -> Scheme`.
  - `apply(scheme: Scheme, book: RegionBook) -> ApplyReport`.

- [ ] **Step 1: Write the failing tests**

```python
# tests/test_schemes.py
from mini_highlight_advisor.region_state import RegionBook, new_book
from mini_highlight_advisor.palette import PaintColor, default_ramp, default_coverage
from mini_highlight_advisor import schemes as sch
import numpy as np


def _book_with_region(name="armour", n=5):
    book = new_book(n)
    mask = np.zeros((4, 4), dtype=bool)
    mask[1:3, 1:3] = True
    book.add(mask, name, default_ramp(n), default_coverage(n))
    return book


def _red(): return PaintColor("Red", "#ff0000")


def test_snapshot_captures_every_region_by_name():
    book = _book_with_region("armour")
    s = sch.snapshot(book, "Crimson")
    assert s.name == "Crimson"
    assert set(s.palettes) == set(book.names())          # Whole mini + armour
    assert s.anchor is None


def test_snapshot_then_apply_is_palette_noop():
    book = _book_with_region("armour")
    s = sch.snapshot(book, "X")
    before = [list(book.palette_at(g)) for g in range(len(book.names()))]
    report = sch.apply(s, book)
    after = [list(book.palette_at(g)) for g in range(len(book.names()))]
    assert before == after
    assert report.skipped_regions == [] and report.unused_keys == []


def test_apply_changes_palette():
    book = _book_with_region("armour")
    s = sch.snapshot(book, "X")
    s.palettes["armour"] = [_red()]
    sch.apply(s, book)
    assert book.palette_at(1) == [_red()]                # index 1 == "armour"


def test_snapshot_is_isolated_from_later_book_edits():
    book = _book_with_region("armour")
    s = sch.snapshot(book, "X")
    book.set_palette_at(1, [_red()])                     # edit book after snapshot
    assert s.palettes["armour"] != [_red()]              # snapshot unchanged


def test_apply_after_rename_reports_skip_and_unused():
    book = _book_with_region("armour")
    s = sch.snapshot(book, "X")
    book.set_name_at(1, "plating")                       # rename the region
    report = sch.apply(s, book)
    assert "plating" in report.skipped_regions           # book region with no key
    assert "armour" in report.unused_keys                # key matching no region


def test_apply_after_add_reports_new_region_skipped():
    book = _book_with_region("armour")
    s = sch.snapshot(book, "X")
    mask = np.zeros((4, 4), dtype=bool); mask[0, 0] = True
    book.add(mask, "cloak", default_ramp(5), default_coverage(5))
    report = sch.apply(s, book)
    assert "cloak" in report.skipped_regions


def test_apply_to_duplicate_names_hits_every_match():
    book = new_book(5)
    for _ in range(2):
        m = np.zeros((4, 4), dtype=bool); m[0, 0] = True
        book.add(m, "trim", default_ramp(5), default_coverage(5))
    s = sch.snapshot(book, "X")
    s.palettes["trim"] = [_red()]
    sch.apply(s, book)
    assert book.palette_at(1) == [_red()] and book.palette_at(2) == [_red()]
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `.venv/Scripts/python -m pytest tests/test_schemes.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'mini_highlight_advisor.schemes'`

- [ ] **Step 3: Write minimal implementation**

```python
# src/mini_highlight_advisor/schemes.py
"""Colour schemes: snapshot the palette-per-region of a RegionBook and swap it
back on demand. Torch-free, Streamlit-free. Region identity is the region NAME
(RegionBook has no stable id); a scheme carries palette only."""
from __future__ import annotations

from dataclasses import dataclass, field

from .palette import PaintColor
from .region_state import RegionBook


@dataclass
class Scheme:
    name: str
    palettes: dict[str, list[PaintColor]]     # region_name -> palette snapshot
    anchor: str | None = None                 # region_name; unused in (a), drives (b)


@dataclass
class ApplyReport:
    updated: list[str] = field(default_factory=list)          # region names written
    skipped_regions: list[str] = field(default_factory=list)  # book regions with no key
    unused_keys: list[str] = field(default_factory=list)      # keys matching no region


def snapshot(book: RegionBook, name: str, anchor: str | None = None) -> Scheme:
    names = book.names()
    # PaintColor is frozen, so a list copy is a complete, isolated snapshot.
    palettes = {names[g]: list(book.palette_at(g)) for g in range(len(names))}
    return Scheme(name=name, palettes=palettes, anchor=anchor)


def apply(scheme: Scheme, book: RegionBook) -> ApplyReport:
    report = ApplyReport()
    names = book.names()
    for g, region_name in enumerate(names):
        pal = scheme.palettes.get(region_name)
        if pal is None:
            report.skipped_regions.append(region_name)
        else:
            book.set_palette_at(g, list(pal))
            report.updated.append(region_name)
    present = set(names)
    report.unused_keys = [k for k in scheme.palettes if k not in present]
    return report
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `.venv/Scripts/python -m pytest tests/test_schemes.py -v`
Expected: PASS (7 passed)

- [ ] **Step 5: Commit**

```bash
git add src/mini_highlight_advisor/schemes.py tests/test_schemes.py
git commit -m "feat: scheme snapshot/apply core (name-keyed, palette-only, mismatch-tolerant)"
```

---

### Task 2: Persist schemes in the project manifest (schema v3)

**Files:**
- Modify: `src/mini_highlight_advisor/projects.py`
- Test: `tests/test_projects_schemes.py`

**Interfaces:**
- Consumes: `Scheme` from Task 1; existing `_palette_to_dicts` / `_palette_from_dicts`.
- Produces:
  - `_scheme_to_dict(s: Scheme) -> dict` and `_scheme_from_dict(d: dict) -> Scheme`.
  - `save_project(name, paints_pool, active_angle, angles, schemes=None, root=PROJECTS_DIR, _now=None)` — new `schemes` param (default `None` → `[]`).
  - `LoadedProject` gains `schemes: list[Scheme]`.
  - `load_project` returns `.schemes` read from `manifest["schemes"]` (absent → `[]`).

- [ ] **Step 1: Write the failing tests**

```python
# tests/test_projects_schemes.py
import json
import numpy as np
from mini_highlight_advisor import projects
from mini_highlight_advisor.region_state import new_book
from mini_highlight_advisor.palette import PaintColor, default_ramp, default_coverage
from mini_highlight_advisor.schemes import Scheme


def _angle(tmp_book):
    return projects.AngleData(
        label="a1", photo_bytes=b"\x89PNG\r\n", photo_suffix=".png",
        book=tmp_book,
        settings=projects.ProjectSettings(n=5, edge_hl=True, edge_extreme=False,
                                          edge_sens=0.5, relief_cap=True,
                                          per_region_norm=False))


def test_scheme_roundtrip(tmp_path):
    book = new_book(5)
    m = np.zeros((4, 4), dtype=bool); m[1, 1] = True
    book.add(m, "armour", default_ramp(5), default_coverage(5))
    scheme = Scheme(name="Crimson", anchor="armour",
                    palettes={"Whole mini": default_ramp(5),
                              "armour": [PaintColor("Red", "#ff0000")]})
    projects.save_project("Mini One", [], 0, [_angle(book)],
                          schemes=[scheme], root=tmp_path)
    lp = projects.load_project("mini-one", root=tmp_path)
    assert len(lp.schemes) == 1
    got = lp.schemes[0]
    assert got.name == "Crimson" and got.anchor == "armour"
    assert got.palettes["armour"] == [PaintColor("Red", "#ff0000")]


def test_schema_version_is_3(tmp_path):
    book = new_book(5)
    projects.save_project("Mini Two", [], 0, [_angle(book)],
                          schemes=[], root=tmp_path)
    manifest = json.loads((tmp_path / "mini-two" / "manifest.json").read_text())
    assert manifest["schema_version"] == 3


def test_load_v2_project_without_schemes_key(tmp_path):
    book = new_book(5)
    projects.save_project("Mini Three", [], 0, [_angle(book)], root=tmp_path)
    # Simulate an older manifest: strip schema up to v2 and drop the schemes key.
    mpath = tmp_path / "mini-three" / "manifest.json"
    m = json.loads(mpath.read_text())
    m["schema_version"] = 2
    m.pop("schemes", None)
    mpath.write_text(json.dumps(m))
    lp = projects.load_project("mini-three", root=tmp_path)
    assert lp.schemes == []
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `.venv/Scripts/python -m pytest tests/test_projects_schemes.py -v`
Expected: FAIL — `save_project() got an unexpected keyword argument 'schemes'` (and `LoadedProject` has no `schemes`).

- [ ] **Step 3: Implement the persistence changes**

In `src/mini_highlight_advisor/projects.py`:

3a. Bump the version constant:
```python
SCHEMA_VERSION = 3
```

3b. Add the import near the other package imports at the top:
```python
from .schemes import Scheme
```

3c. Add scheme (de)serialization helpers after `_palette_from_dicts`:
```python
def _scheme_to_dict(s: Scheme) -> dict:
    return {"name": s.name, "anchor": s.anchor,
            "palettes": {region: _palette_to_dicts(pal)
                         for region, pal in s.palettes.items()}}


def _scheme_from_dict(d: dict) -> Scheme:
    return Scheme(name=d["name"], anchor=d.get("anchor"),
                  palettes={region: _palette_from_dicts(items)
                            for region, items in d["palettes"].items()})
```

3d. Add the field to `LoadedProject`:
```python
@dataclass(frozen=True)
class LoadedProject:
    paints_pool: list[str]
    active_angle: int
    angles: list[AngleData]
    schemes: list[Scheme]
```

3e. Change the `save_project` signature and manifest to accept and write schemes:
```python
def save_project(name, paints_pool, active_angle, angles, schemes=None,
                 root: Path = PROJECTS_DIR, _now: str | None = None) -> str:
```
and inside the `manifest = {...}` dict add the key:
```python
        "schemes": [_scheme_to_dict(s) for s in (schemes or [])],
```

3f. In `load_project`, read schemes tolerantly and pass them through. Replace the final `return LoadedProject(...)` with:
```python
    schemes = []
    for d in m.get("schemes", []):
        try:
            schemes.append(_scheme_from_dict(d))
        except (KeyError, TypeError):
            continue
    return LoadedProject(paints_pool=list(m.get("paints_pool", [])),
                         active_angle=active, angles=angles, schemes=schemes)
```

3g. In `_adapt_v1`, add `schemes=[]` to its `LoadedProject(...)` return:
```python
    return LoadedProject(paints_pool=[], active_angle=0, angles=[angle], schemes=[])
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `.venv/Scripts/python -m pytest tests/test_projects_schemes.py -v`
Expected: PASS (3 passed)

- [ ] **Step 5: Run the existing projects tests to confirm no regression**

Run: `.venv/Scripts/python -m pytest tests/ -k projects -v`
Expected: PASS — existing project tests still green (the new `schemes` field defaults cleanly; any existing test that constructs `LoadedProject` positionally would fail here — if so, add `schemes=[]` to that construction and re-run).

- [ ] **Step 6: Commit**

```bash
git add src/mini_highlight_advisor/projects.py tests/test_projects_schemes.py
git commit -m "feat: persist colour schemes in project manifest (schema v3, back-compat)"
```

---

### Task 3: Scheme session key + quick-swap panel + app wiring

**Files:**
- Modify: `ui/keys.py`
- Create: `ui/schemes_panel.py`
- Modify: `ui/projects_panel.py` (thread schemes through load/save)
- Modify: `app.py` (mount the panel)

**Interfaces:**
- Consumes: `schemes.snapshot`, `schemes.apply`, `keys.BOOK` / `keys.PS_BOOK`, `keys.SCHEMES`, `LoadedProject.schemes` from Task 2.
- Produces: `keys.SCHEMES` constant; `schemes_panel.render()`.

- [ ] **Step 1: Add the session key**

In `ui/keys.py`, under the `# --- projects (mini library) ---` block, add:
```python
SCHEMES = "schemes"                    # list[Scheme] in session
```

- [ ] **Step 2: Create the panel**

```python
# ui/schemes_panel.py
"""🎨 Schemes panel — save the current colours as a named scheme and swap
between saved schemes to compare highlight placement. Streamlit glue only;
all scheme logic lives in mini_highlight_advisor.schemes."""
import streamlit as st

from mini_highlight_advisor import schemes as sch
from ui import keys


def _active_book():
    # PS mode keeps its own book; prefer it when present, else the photo book.
    # VERIFY against app.py's mode gate before trusting in PS mode (Step 4).
    return st.session_state.get(keys.PS_BOOK) or st.session_state.get(keys.BOOK)


def _reseed_editor_widgets() -> None:
    # After a swap the book palettes changed; drop the selected region's widget
    # keys so the editor re-seeds from the book on the next run.
    st.session_state.pop(keys.LOADED_G, None)
    st.session_state.pop(keys.COV_N, None)
    for k in [k for k in list(st.session_state)
              if k.startswith("slot_code_") or k.startswith("slot_hex_")
              or k.startswith("cov_pct_")]:
        st.session_state.pop(k, None)


def render() -> None:
    book = _active_book()
    if book is None:
        return
    stored = st.session_state.setdefault(keys.SCHEMES, [])
    with st.expander("🎨 Schemes — save & swap colour setups", expanded=False):
        name = st.text_input("Scheme name", key="scheme_save_name")
        if st.button("＋ Save current as scheme", type="primary"):
            clean = name.strip()
            if not clean:
                st.warning("Give the scheme a name.")
            else:
                snap = sch.snapshot(book, clean)
                existing = next((s for s in stored if s.name == clean), None)
                if existing:
                    stored[stored.index(existing)] = snap
                    st.toast(f'Updated scheme "{clean}".')
                else:
                    stored.append(snap)
                    st.toast(f'Saved scheme "{clean}".')
                st.rerun()

        if not stored:
            st.caption("No schemes yet. Set your colours, then save one above.")
            return

        names = [s.name for s in stored]
        pick = st.radio("Saved schemes", names, key="scheme_pick")
        chosen = stored[names.index(pick)]

        c_apply, c_del = st.columns(2)
        if c_apply.button("Apply", type="primary"):
            report = sch.apply(chosen, book)
            _reseed_editor_widgets()
            if report.skipped_regions:
                st.session_state["_scheme_note"] = (
                    f"{len(report.updated)} region(s) updated — no saved colour "
                    f"for: {', '.join(report.skipped_regions)}")
            st.rerun()
        if c_del.button("Delete"):
            stored.remove(chosen)
            st.session_state.pop("scheme_pick", None)
            st.rerun()

        new_name = st.text_input("Rename selected", value=pick, key="scheme_rename")
        if st.button("Rename") and new_name.strip() and new_name.strip() != pick:
            chosen.name = new_name.strip()
            st.session_state.pop("scheme_pick", None)
            st.rerun()

        note = st.session_state.pop("_scheme_note", None)
        if note:
            st.info(note)
```

- [ ] **Step 3: Thread schemes through load/save in `ui/projects_panel.py`**

In `render_library()`, inside the `if c_load.button("Load", ...)` block, after the `OWNED` line, add:
```python
            st.session_state[keys.SCHEMES] = list(lp.schemes)
```

In `render_save()`, inside the `if st.button("Save project", ...)` block, change the `save_project` call to pass schemes:
```python
                projects.save_project(name, pool, active, angles,
                                      schemes=st.session_state.get(keys.SCHEMES, []))
```

- [ ] **Step 4: Mount the panel in `app.py`**

Find where `projects_panel.render_save()` is called in `app.py`. Add the import alongside the other `ui` panel imports:
```python
from ui import schemes_panel
```
and call `schemes_panel.render()` immediately before `projects_panel.render_save()` (both belong in the post-editor controls area).

While there, confirm how `app.py` chooses between photo mode (`keys.BOOK`) and PS mode (`keys.PS_BOOK`) — if there is an explicit `is_ps_mode` flag, make `_active_book()` in `schemes_panel.py` use that same gate instead of the `PS_BOOK or BOOK` fallback. Adjust `_active_book()` to match, if needed.

- [ ] **Step 5: Import sanity check**

Run: `.venv/Scripts/python -c "import ui.schemes_panel; import ui.projects_panel; import ui.keys; print('ok')"`
Expected: prints `ok` with no ImportError.

- [ ] **Step 6: Manual browser smoke**

Run: `.venv/Scripts/streamlit run app.py`
Verify:
1. Set up a mini with at least one drawn region and distinct palettes.
2. Open **🎨 Schemes**, save "Scheme A".
3. Change a region's colours, save "Scheme B".
4. Radio-select "Scheme A", click **Apply** → preview + step images revert to A's colours.
5. Select "Scheme B", **Apply** → colours switch to B. (Quick-swap works.)
6. Rename "Scheme B" → "Forest"; Delete "Scheme A".
7. Save the project, reload it → the saved scheme(s) reappear in the panel.
8. Rename a region, Apply a scheme → the "N region(s) updated — no saved colour for: …" note shows; no crash.

- [ ] **Step 7: Commit**

```bash
git add ui/keys.py ui/schemes_panel.py ui/projects_panel.py app.py
git commit -m "feat: scheme experimenter quick-swap panel + project load/save wiring"
```

---

## Self-Review

**Spec coverage:**
- Save current as named scheme → Task 1 `snapshot` + Task 3 panel save. ✓
- Keep a list + apply/swap in one click → Task 3 radio + Apply. ✓
- Persist inside mini-project → Task 2 (schema v3). ✓
- Region-mismatch graceful handling + surfaced report → Task 1 `ApplyReport`, Task 3 note. ✓
- Palette-only snapshot → Task 1 (`palette_at` only; no coverage/material). ✓
- `anchor` field carried for future (b) → Task 1 `Scheme.anchor`, persisted Task 2. ✓
- Back-compat (absent `schemes` → `[]`) → Task 2 `test_load_v2_project_without_schemes_key`. ✓
- Duplicate region names apply to every match → Task 1 `test_apply_to_duplicate_names_hits_every_match`. ✓
- Corrupt scheme entry skipped on load → Task 2 Step 3f tolerant loop. ✓
- Empty/duplicate scheme name handling → Task 3 panel (warn on empty; overwrite on duplicate). ✓

**Placeholder scan:** No TBD/TODO; every code step has concrete content. The one judgement call (PS-vs-photo book gate) is an explicit verify step with a working fallback, not a placeholder. ✓

**Type consistency:** `Scheme(name, palettes, anchor)`, `ApplyReport(updated, skipped_regions, unused_keys)`, `snapshot(book, name, anchor=None)`, `apply(scheme, book)`, `save_project(..., schemes=None)`, `LoadedProject.schemes` — names match across Tasks 1–3. ✓
