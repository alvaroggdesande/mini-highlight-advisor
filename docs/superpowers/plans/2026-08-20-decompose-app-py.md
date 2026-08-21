# Decompose app.py into a ui/ package — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Split the 547-line root `app.py` into a thin orchestrator plus a focused `ui/` package, with the ~40 magic session-state key strings centralized — with zero change to app behavior.

**Architecture:** Extract cohesive blocks of the Streamlit app into `ui/` modules that expose `render_*` functions taking explicit params and returning explicit values. `app.py` becomes a table-of-contents orchestrator that calls them in the exact original order. All session-state key strings move behind `ui/keys.py`; the two order-sensitive session-state choreography blocks move into `ui/state.py`. The core `src/mini_highlight_advisor/` package is untouched and stays UI-agnostic.

**Tech Stack:** Python 3.11, Streamlit 1.61.*, streamlit-drawable-canvas 0.9.3, numpy, opencv, pytest.

**Spec:** No separate spec doc — the approved design lives in the chat brainstorm that produced this plan (2026-08-20). Design summary is inlined in "Global Constraints" and each task below.

## Global Constraints

- **Behavior-preserving refactor.** No user-visible change: same widgets, same order on screen, same session-state keys (same string values), same reruns. Only *where the code lives* and *how key strings are spelled* changes.
- **On-screen widget order is fixed.** The current top-to-bottom order in the Miniature tab must be preserved exactly: region columns → "Editing" header → rename → recipe loader → palette slots → coverage → save-recipe → write-back → match-to-paints → edge/relief/norm toggles → photo-quality → analyze + steps.
- **Paints tab body must execute before the Miniature tab body** (both `st.tabs` bodies run every rerun; `picked`/`owned_paints` must be finalized before the mini tab renders ownership badges). Preserve by calling `paints_tab.render()` first and threading its return values into the mini flow.
- **Session-state key *string values* are frozen.** `ui/keys.py` must emit byte-identical strings to today (`"n"`, `f"slot_hex_{i}"`, `f"cov_pct_{i}"`, `"_loaded_g"`, etc.). Changing a key string silently resets that widget — treat any diff as a bug.
- **Callbacks stay module-level functions** (Streamlit requires plain funcs for `on_change`/`on_click`).
- **`setdefault` seeding stays before widget instantiation**; `st.rerun()`, `st.stop()`, and `@st.cache_data` on `shading` are preserved exactly.
- **Import order for the compat shim is load-bearing:** the `image_to_url` monkey-patch must run *before* `streamlit_drawable_canvas` is imported. `ui/compat.py` enforces this at its own import time.
- **Verification ownership:** the executor runs cheap `python -c "import ui.<module>"` import checks and the pure-unit pytest after each task. The full-app smoke test (`streamlit run app.py`, click-through) is the USER's, done once at the end.
- **Target layout:**
  ```
  app.py                — orchestrator (~40-60 lines)
  ui/__init__.py
  ui/context.py         — CATALOG, CUSTOM, CODE_LABEL, CATALOG_CODES (shared constants)
  ui/keys.py            — session-key names + builders
  ui/state.py           — load_region_into_widgets, rehydrate_editor_widgets
  ui/compat.py          — image_to_url patch + st_canvas guard + HF env
  ui/helpers.py         — swatch, render_region_steps, current_cov_seed, shading
  ui/geometry.py        — points_from_object, region_outline_image
  ui/paints_tab.py      — render() -> (picked, owned_paints)
  ui/regions_panel.py   — render(book, rgb, shading, src_w, src_h) -> sel
  ui/palette_editor.py  — render(...) -> (palette, n); render_save_recipe(palette, n)
  ui/coverage_editor.py — render(n) -> coverage
  ui/results.py         — render(...) -> None
  ```
- **Extraction is bottom-up:** leaf modules (no intra-ui deps) first, consumers later, `app.py` slims last. The app stays runnable after every task.

---

### Task 1: Scaffold `ui/` package + shared context + keys

**Files:**
- Create: `ui/__init__.py`
- Create: `ui/context.py`
- Create: `ui/keys.py`
- Create: `tests/test_ui_keys.py`

**Interfaces:**
- Consumes: `mini_highlight_advisor.catalog.load_catalog` (existing).
- Produces:
  - `ui.context.CATALOG: list[PaintColor]`, `ui.context.CUSTOM: str = "(custom target)"`, `ui.context.CODE_LABEL: dict[str,str]`, `ui.context.CATALOG_CODES: list[str]`.
  - `ui.keys` names: `N="n"`, `COV_N="cov_n"`, `LOADED_G="_loaded_g"`, `BOOK="book"`, `DRAW_MODE="draw_mode"`, `REGION_RADIO="region_radio"`, `ADHOC_HEX="adhoc_hex"`, `ADHOC_ON="adhoc_on"`, `EDGE_HL="edge_hl"`, `EDGE_EXTREME="edge_extreme"`, `EDGE_SENS="edge_sens"`, `RELIEF_CAP="relief_cap"`, `PER_REGION_NORM="per_region_norm"`, `SAVE_NAME="save_name"`, `OWNED="owned"`, `RENAME_PREFIX="rename_"`.
  - `ui.keys` builders: `slot_code(i)`, `slot_hex(i)`, `slot_hexinput(i)`, `cov_pct(i)`, `blend(i)`, `rename(i)`, `canvas(n)`.

- [ ] **Step 1: Write the failing test**

```python
# tests/test_ui_keys.py
from ui import keys


def test_key_builders_match_legacy_strings():
    assert keys.slot_code(0) == "slot_code_0"
    assert keys.slot_hex(3) == "slot_hex_3"
    assert keys.slot_hexinput(2) == "slot_hexinput_2"
    assert keys.cov_pct(4) == "cov_pct_4"
    assert keys.blend(1) == "blend_1"
    assert keys.rename(2) == "rename_2"
    assert keys.canvas(0) == "canvas_0"


def test_key_constants_match_legacy_strings():
    assert keys.N == "n"
    assert keys.COV_N == "cov_n"
    assert keys.LOADED_G == "_loaded_g"
    assert keys.DRAW_MODE == "draw_mode"
    assert keys.PER_REGION_NORM == "per_region_norm"
    assert keys.RENAME_PREFIX == "rename_"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.venv/Scripts/python -m pytest tests/test_ui_keys.py -q`
Expected: FAIL — `ModuleNotFoundError: No module named 'ui'`.

- [ ] **Step 3: Create the package files**

```python
# ui/__init__.py
"""Streamlit UI layer for Mini Highlight Advisor.

The core package (mini_highlight_advisor) stays UI-agnostic; everything that
touches Streamlit lives here. app.py is a thin orchestrator over these modules.
"""
```

```python
# ui/context.py
"""Shared, load-once catalogue constants used across UI panels."""
from mini_highlight_advisor.catalog import load_catalog

# UI sentinel for "not a catalogue paint" (custom hex). Byte-identical to the
# legacy app.py value — do not change; it is compared by string everywhere.
CUSTOM = "(custom target)"

CATALOG = load_catalog()
CODE_LABEL = {p.code: f"{p.name} · {p.paint_range or ''} · {p.code}" for p in CATALOG}
CATALOG_CODES = [p.code for p in CATALOG]
```

```python
# ui/keys.py
"""Session-state key names and builders.

Centralizes the ~40 magic strings that were scattered through app.py. The
string *values* are frozen: they must match the legacy app.py keys exactly,
or existing widget state silently resets. Tests lock the contract.
"""

# --- fixed keys ---
N = "n"                          # number of palette layers (slider)
COV_N = "cov_n"                  # layer count the coverage sliders were seeded for
LOADED_G = "_loaded_g"           # region index currently loaded into widget keys
BOOK = "book"                    # RegionBook in session
DRAW_MODE = "draw_mode"          # region-lasso draw mode toggle
REGION_RADIO = "region_radio"    # region selector radio
ADHOC_HEX = "adhoc_hex"          # ad-hoc match colour picker
ADHOC_ON = "adhoc_on"            # include ad-hoc colour checkbox
EDGE_HL = "edge_hl"              # edge highlights checkbox
EDGE_EXTREME = "edge_extreme"    # extreme edge highlight checkbox
EDGE_SENS = "edge_sens"          # edge sensitivity slider
RELIEF_CAP = "relief_cap"        # auto-reduce bands on flat regions checkbox
PER_REGION_NORM = "per_region_norm"  # colored/painted mini toggle
SAVE_NAME = "save_name"          # recipe save name text input
OWNED = "owned"                  # owned-paints multiselect
RENAME_PREFIX = "rename_"        # prefix of per-region rename text-input keys


# --- per-index builders ---
def slot_code(i: int) -> str: return f"slot_code_{i}"
def slot_hex(i: int) -> str: return f"slot_hex_{i}"
def slot_hexinput(i: int) -> str: return f"slot_hexinput_{i}"
def cov_pct(i: int) -> str: return f"cov_pct_{i}"
def blend(i: int) -> str: return f"blend_{i}"
def rename(i: int) -> str: return f"rename_{i}"
def canvas(n: int) -> str: return f"canvas_{n}"
```

- [ ] **Step 4: Run test to verify it passes**

Run: `.venv/Scripts/python -m pytest tests/test_ui_keys.py -q`
Expected: PASS. Also run `.venv/Scripts/python -c "import ui.context, ui.keys"` — Expected: no output, exit 0.

- [ ] **Step 5: Commit**

```bash
git add ui/__init__.py ui/context.py ui/keys.py tests/test_ui_keys.py
git commit -m "refactor(ui): scaffold ui/ package with context + keys modules"
```

---

### Task 2: Extract `ui/geometry.py` (canvas geometry)

**Files:**
- Create: `ui/geometry.py`
- Create: `tests/test_ui_geometry.py`
- Modify: `app.py` (remove `_points_from_object` [113-122] and `_region_outline_image` [160-172]; import from `ui.geometry`; update call sites to `geometry.points_from_object` / `geometry.region_outline_image`).

**Interfaces:**
- Consumes: nothing intra-ui.
- Produces: `ui.geometry.points_from_object(obj) -> list[tuple[float, float]]`; `ui.geometry.region_outline_image(rgb, regions) -> np.ndarray`.

- [ ] **Step 1: Write the failing test**

```python
# tests/test_ui_geometry.py
import numpy as np
from ui import geometry
from mini_highlight_advisor.regions import Region
from mini_highlight_advisor.palette import DEFAULT_PALETTE


def test_points_from_object_points_form():
    obj = {"points": [{"x": 1, "y": 2}, {"x": 3, "y": 4}]}
    assert geometry.points_from_object(obj) == [(1, 2), (3, 4)]


def test_points_from_object_path_form_uses_segment_endpoints():
    # SVG-ish path: M/L take (x,y); Q's control point is ignored (endpoint = last two).
    obj = {"path": [["M", 0, 0], ["Q", 5, 5, 2, 3], ["z"]]}
    assert geometry.points_from_object(obj) == [(0, 0), (2, 3)]


def test_region_outline_image_shape_and_draws_edges():
    rgb = np.zeros((20, 20, 3), dtype=np.uint8)
    mask = np.zeros((20, 20), dtype=bool)
    mask[5:15, 5:15] = True
    region = Region(name="r", mask=mask, palette=list(DEFAULT_PALETTE[:3]), coverage=[0.5, 0.3, 0.2])
    out = geometry.region_outline_image(rgb, [region])
    assert out.shape == (20, 20, 3)
    assert out.any()  # at least the boundary pixels were coloured
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.venv/Scripts/python -m pytest tests/test_ui_geometry.py -q`
Expected: FAIL — `ModuleNotFoundError: No module named 'ui.geometry'`.

- [ ] **Step 3: Create `ui/geometry.py`**

Move the two functions verbatim from `app.py` (current lines 113-122 and 160-172), renamed without the leading underscore. Keep the `import cv2` / `import numpy as np` local to `region_outline_image` (or hoist to module top — either is fine; prefer module-top imports):

```python
# ui/geometry.py
"""Pure geometry helpers for the drawable canvas and region-outline preview."""
import cv2
import numpy as np


def points_from_object(obj) -> list[tuple[float, float]]:
    # Extract traced vertices from a drawable-canvas (fabric.js) object.
    # Freedraw/polygon objects expose the stroke as obj["path"], a list of SVG
    # segments: ["M",x,y] / ["L",x,y] / ["Q",cx,cy,x,y] / ["z"]. The segment
    # END point is always its last two numbers (Q's control point is ignored).
    # Some versions use obj["points"] ([{"x":..,"y":..}]) instead.
    if "points" in obj:
        return [(p["x"], p["y"]) for p in obj["points"]]
    return [(seg[-2], seg[-1]) for seg in obj.get("path", []) if len(seg) >= 3]


def region_outline_image(rgb, regions):
    """RGB copy of the photo with each region's boundary drawn in a distinct
    colour. Read-only preview — selection happens in the list."""
    out = np.ascontiguousarray(rgb[..., :3]).copy()
    colors = [(255, 40, 200), (40, 200, 255), (255, 200, 40), (120, 255, 120), (255, 120, 120)]
    kernel = np.ones((3, 3), np.uint8)
    for i, r in enumerate(regions):
        m = r.mask.astype(np.uint8)
        edge = (m - cv2.erode(m, kernel, iterations=2)).astype(bool)
        out[edge] = colors[i % len(colors)]
    return out
```

- [ ] **Step 4: Update `app.py`**

Delete the `_points_from_object` (113-122) and `_region_outline_image` (160-172) definitions. Add `from ui import geometry` to the import block. Replace the two call sites:
- line 242: `outline = _region_outline_image(rgb, book.drawn)` → `outline = geometry.region_outline_image(rgb, book.drawn)`
- line 286: `[scale_points(_points_from_object(o), sx, sy) for o in objs]` → `[scale_points(geometry.points_from_object(o), sx, sy) for o in objs]`

- [ ] **Step 5: Verify**

Run: `.venv/Scripts/python -m pytest tests/test_ui_geometry.py -q` → PASS.
Run: `.venv/Scripts/python -c "import ui.geometry"` → exit 0.
Confirm `_points_from_object` / `_region_outline_image` no longer appear in `app.py` (grep).

- [ ] **Step 6: Commit**

```bash
git add ui/geometry.py tests/test_ui_geometry.py app.py
git commit -m "refactor(ui): extract canvas geometry into ui/geometry.py"
```

---

### Task 3: Extract `ui/helpers.py` (presentational + data helpers)

**Files:**
- Create: `ui/helpers.py`
- Create: `tests/test_ui_helpers.py`
- Modify: `app.py` (remove `_swatch` [105-110], `_render_region_steps` [125-152], `_current_cov_seed` [155-157], `_shading` [60-69]; import from `ui.helpers`; update call sites).

**Interfaces:**
- Consumes: `mini_highlight_advisor.masking.load_image`, `mini_highlight_advisor.pipeline.prepare_shading` (existing).
- Produces:
  - `ui.helpers.swatch(hexv: str, size: str = "1em") -> str`
  - `ui.helpers.render_region_steps(steps, roles, names, coverage) -> None` (Streamlit side effects)
  - `ui.helpers.current_cov_seed(n: int) -> list[float]`
  - `ui.helpers.shading(image_bytes: bytes, suffix: str) -> tuple[rgb, alpha, ShadingResult]` (cached with `@st.cache_data`)

- [ ] **Step 1: Write the failing test**

```python
# tests/test_ui_helpers.py
from ui import helpers


def test_swatch_is_inline_span_with_colour():
    html = helpers.swatch("# abc123".replace(" ", ""), size="2em")
    assert "background-color:#abc123" in html
    assert "width:2em" in html and "height:2em" in html
    assert html.startswith("<span")


def test_current_cov_seed_length_and_sums_to_100():
    seed = helpers.current_cov_seed(5)
    assert len(seed) == 5
    assert abs(sum(seed) - 100.0) < 1.0  # default_coverage fractions * 100
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.venv/Scripts/python -m pytest tests/test_ui_helpers.py -q`
Expected: FAIL — `ModuleNotFoundError: No module named 'ui.helpers'`.

- [ ] **Step 3: Create `ui/helpers.py`**

Move the four functions from `app.py`. `swatch`, `current_cov_seed` are pure; `render_region_steps` and `shading` keep their Streamlit dependencies. `shading` keeps the `@st.cache_data(show_spinner=False)` decorator. Bodies are copied verbatim from the current lines (60-69, 105-110, 125-152, 155-157), dropping the leading underscore and the redundant local `from ... import default_coverage` (import it at module top instead).

```python
# ui/helpers.py
"""Presentational + data helpers for the Streamlit UI."""
import os
import tempfile

import streamlit as st

from mini_highlight_advisor.masking import load_image
from mini_highlight_advisor.pipeline import prepare_shading
from mini_highlight_advisor.palette import default_coverage


@st.cache_data(show_spinner=False)
def shading(image_bytes: bytes, suffix: str):
    with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as tmp:
        tmp.write(image_bytes)
        tmp_path = tmp.name
    try:
        rgb, alpha = load_image(tmp_path)
    finally:
        os.unlink(tmp_path)
    return rgb, alpha, prepare_shading(rgb, alpha)


def swatch(hexv: str, size: str = "1em") -> str:
    return (
        f"<span style='display:inline-block;width:{size};height:{size};"
        f"background-color:{hexv};border:1px solid #888;"
        f"vertical-align:middle;margin-right:0.5em'></span>"
    )


def current_cov_seed(n: int) -> list[float]:
    return [round(f * 100, 1) for f in default_coverage(n)]


def render_region_steps(steps, roles, names, coverage) -> None:
    # (verbatim body of app.py _render_region_steps, lines 125-152)
    ...
```

(Copy the full `_render_region_steps` body into `render_region_steps` — it is unchanged.)

- [ ] **Step 4: Update `app.py`**

Delete the four defs. Add `from ui import helpers`. Update call sites:
- line 219: `rgb, alpha, shading = _shading(...)` → `rgb, alpha, shading = helpers.shading(...)` (note: the local variable `shading` shadows the function name; after this change the call is `helpers.shading(...)`, so no collision).
- all `_swatch(...)` → `helpers.swatch(...)` (lines 201, 397, 479, and inside slots 391-401 as applicable).
- line 293: `_current_cov_seed(...)` → `helpers.current_cov_seed(...)`.
- line 544: `_render_region_steps(...)` → `helpers.render_region_steps(...)`.

- [ ] **Step 5: Verify**

Run: `.venv/Scripts/python -m pytest tests/test_ui_helpers.py -q` → PASS.
Run: `.venv/Scripts/python -c "import ui.helpers"` → exit 0.
Grep `app.py` for `_swatch`, `_shading`, `_render_region_steps`, `_current_cov_seed` → no defs remain (only `helpers.` calls).

- [ ] **Step 6: Commit**

```bash
git add ui/helpers.py tests/test_ui_helpers.py app.py
git commit -m "refactor(ui): extract presentational helpers into ui/helpers.py"
```

---

### Task 4: Extract `ui/compat.py` (image_to_url patch + st_canvas guard + env)

**Files:**
- Create: `ui/compat.py`
- Modify: `app.py` (remove `_patch_image_to_url` [26-50], the `st_canvas` guarded import [52-55], and the `os.environ.setdefault(...HF...)` [57]; import `st_canvas` from `ui.compat`).

**Interfaces:**
- Consumes: nothing intra-ui.
- Produces: `ui.compat.st_canvas` (the component callable, or `None` if unavailable). Import side effects (patch + env) run once at module import, before the drawable-canvas import.

- [ ] **Step 1: Create `ui/compat.py`**

Move `_patch_image_to_url` (rename to `_patch_image_to_url`, keep private), call it, then do the guarded `st_canvas` import, then the HF env setdefault — same order as app.py lines 26-57. This preserves the load-bearing "patch before import" ordering.

```python
# ui/compat.py
"""Version-compat shims, isolated so they are easy to retire later.

Importing this module (a) monkey-patches streamlit.elements.image.image_to_url
for streamlit-drawable-canvas 0.9.3 against streamlit 1.61.*, then (b) imports
st_canvas, then (c) sets the HF symlink-warning env var. Order matters: the
patch must run before the drawable-canvas import.
"""
import os


def _patch_image_to_url() -> None:
    # (verbatim body of app.py _patch_image_to_url, lines 26-47)
    ...


_patch_image_to_url()

try:
    from streamlit_drawable_canvas import st_canvas
except Exception:  # component missing/incompatible -> region drawing off, single-palette still works
    st_canvas = None

os.environ.setdefault("HF_HUB_DISABLE_SYMLINKS_WARNING", "1")
```

(Copy the full `_patch_image_to_url` body verbatim.)

- [ ] **Step 2: Update `app.py`**

Delete lines 26-57 (the def, the `_patch_image_to_url()` call, the `try/except` st_canvas import, the HF env line). Add to the import block: `from ui.compat import st_canvas`. Every existing `st_canvas` reference in app.py (lines 53, 233, 270, and the regions code) now resolves to the imported name.

- [ ] **Step 3: Verify**

Run: `.venv/Scripts/python -c "import ui.compat; print(ui.compat.st_canvas is None)"` → prints `True` or `False`, exit 0 (no traceback).
Run: `.venv/Scripts/python -m pytest -q` → existing tests still PASS.

- [ ] **Step 4: Commit**

```bash
git add ui/compat.py app.py
git commit -m "refactor(ui): isolate streamlit compat shim into ui/compat.py"
```

---

### Task 5: Extract `ui/state.py` (session-state choreography)

**Files:**
- Create: `ui/state.py`
- Modify: `app.py` (replace the on-selection-change block [253-266] with `state.load_region_into_widgets(book, sel)`; replace the `setdefault` rehydrate block [321-337] with `state.rehydrate_editor_widgets(book, sel)`).

**Interfaces:**
- Consumes: `ui.context` (CATALOG, CUSTOM), `ui.keys`, `mini_highlight_advisor.catalog.find_by_code`.
- Produces:
  - `ui.state.load_region_into_widgets(book, sel) -> None` — if `st.session_state[keys.LOADED_G] != sel`, load region `sel`'s palette/coverage into widget keys, set `book.selected = sel`, and `st.rerun()`. Otherwise no-op. (Contains the `st.rerun()`, exactly as today.)
  - `ui.state.rehydrate_editor_widgets(book, sel) -> None` — `setdefault` the missing `n` / `slot_*` / `cov_pct_*` / `cov_n` keys from region `sel` (restores keys Streamlit GC'd after a mid-run rerun; never clobbers live edits).

- [ ] **Step 1: Create `ui/state.py`**

Move the two blocks verbatim into functions, swapping raw key strings for `keys.*` and the raw `CUSTOM`/`CATALOG` for `context.*`. The `load_region_into_widgets` body is app.py lines 253-266 (the `if st.session_state.get("_loaded_g") != sel:` block including the final `st.rerun()`); note app.py sets `book.selected = sel` both inside the block (265) and after it (267) — keep the inside-block assignment; the caller keeps the after assignment (see Step 2).

```python
# ui/state.py
"""The two order-sensitive session-state choreography blocks, centralized.

These are the highest-risk pieces of the editor: getting the load/rehydrate
timing wrong silently corrupts a region's palette. Keep them here, driven by
ui.keys, so the whole 'session-state dance' lives in one place.
"""
import streamlit as st

from mini_highlight_advisor.catalog import find_by_code
from ui import context, keys


def load_region_into_widgets(book, sel) -> None:
    # On selection change, load that region's palette/coverage into widget keys.
    if st.session_state.get(keys.LOADED_G) != sel:
        pal = book.palette_at(sel)
        cov = book.coverage_at(sel)
        st.session_state[keys.N] = len(pal)
        for i, p in enumerate(pal):
            match = find_by_code(context.CATALOG, p.code) if p.code else None
            st.session_state[keys.slot_code(i)] = p.code if match else context.CUSTOM
            st.session_state[keys.slot_hex(i)] = p.hex
        for i in range(len(cov) - 1):
            st.session_state[keys.cov_pct(i)] = round(cov[i] * 100, 1)
        st.session_state[keys.COV_N] = len(cov)
        st.session_state[keys.LOADED_G] = sel
        book.selected = sel
        st.rerun()


def rehydrate_editor_widgets(book, sel) -> None:
    # Restore only the *missing* editor keys from the selected region after a
    # rerun that GC'd them; live user edits (present keys) are untouched.
    _pal = book.palette_at(sel)
    _cov = book.coverage_at(sel)
    st.session_state.setdefault(keys.N, len(_pal))
    for i, p in enumerate(_pal):
        _has_code = bool(p.code) and find_by_code(context.CATALOG, p.code) is not None
        st.session_state.setdefault(keys.slot_code(i), p.code if _has_code else context.CUSTOM)
        st.session_state.setdefault(keys.slot_hex(i), p.hex)
    for i in range(len(_cov) - 1):
        st.session_state.setdefault(keys.cov_pct(i), round(_cov[i] * 100, 1))
    st.session_state.setdefault(keys.COV_N, len(_cov))
```

- [ ] **Step 2: Update `app.py`**

The selection-load block currently lives *inside* the `with right:` column, between the radio (247-251) and `book.selected = sel` (267). Replace lines 253-266 with a single call `state.load_region_into_widgets(book, sel)`; keep line 267 `book.selected = sel` as-is. Replace the rehydrate block (321-337) with `state.rehydrate_editor_widgets(book, sel)`. Add `from ui import state`.

(Note: this block moves into `ui/regions_panel.py` in Task 8; for now it stays inline in app.py so the app runs after this task.)

- [ ] **Step 3: Verify**

Run: `.venv/Scripts/python -c "import ui.state"` → exit 0.
Run: `.venv/Scripts/python -m pytest -q` → existing tests still PASS.
Grep `app.py`: the raw `"_loaded_g"` string and the `setdefault("n", ...)` from the rehydrate block are gone (now via `keys`/`state`). (The slots section still has its own `setdefault(keys.N, 5)` — that is intentional and stays until Task 7.)

- [ ] **Step 4: Commit**

```bash
git add ui/state.py app.py
git commit -m "refactor(ui): centralize session-state choreography in ui/state.py"
```

---

### Task 6: Extract `ui/paints_tab.py`

**Files:**
- Create: `ui/paints_tab.py`
- Modify: `app.py` (replace the `with tab_paints:` body [183-203] with `picked, owned_paints = paints_tab.render()` inside the `with tab_paints:` context).

**Interfaces:**
- Consumes: `ui.context` (CATALOG, CODE_LABEL, CATALOG_CODES), `ui.keys` (OWNED), `ui.helpers.swatch`, `mini_highlight_advisor.collection`, `mini_highlight_advisor.catalog.find_by_code`.
- Produces: `ui.paints_tab.render() -> tuple[list[str], list[PaintColor]]` returning `(picked, owned_paints)`. Assumes it is called inside a `with tab_paints:` context (it does not manage the tab itself).

- [ ] **Step 1: Create `ui/paints_tab.py`**

Move the Paints-tab body (app.py 184-203) verbatim into `render()`, swapping the `"owned"` key for `keys.OWNED`, `_swatch` for `helpers.swatch`, and CATALOG/CODE_LABEL/CATALOG_CODES for `context.*`. Return `(picked, owned_paints)`.

```python
# ui/paints_tab.py
"""The '🎨 Paints' tab: owned-paint inventory."""
import streamlit as st

from mini_highlight_advisor import collection
from mini_highlight_advisor.catalog import find_by_code
from ui import context, helpers, keys


def render() -> tuple[list[str], list]:
    st.markdown("**My paints** (Vallejo)")
    owned_codes = collection.load(catalog=context.CATALOG)
    picked = st.multiselect(
        "Paints you own", context.CATALOG_CODES,
        default=sorted(owned_codes & set(context.CATALOG_CODES)),
        format_func=lambda c: context.CODE_LABEL.get(c, c),
        key=keys.OWNED,
    )
    if set(picked) != owned_codes:
        collection.save(set(picked))
    owned_paints = [p for c in picked if (p := find_by_code(context.CATALOG, c)) is not None]

    st.markdown("**Owned paints**")
    if not owned_paints:
        st.caption("No paints selected yet — tick the paints you own above.")
    for p in owned_paints:
        rng = p.paint_range or ""
        st.markdown(f"{helpers.swatch(p.hex)}{p.name} · {rng} · {p.code}", unsafe_allow_html=True)

    st.caption(f"Catalogue: {len(context.CATALOG)} paints (Vallejo Model Color + Game Color)")
    return picked, owned_paints
```

- [ ] **Step 2: Update `app.py`**

Replace the `with tab_paints:` body with:

```python
with tab_paints:
    picked, owned_paints = paints_tab.render()
```

Add `from ui import paints_tab`. The `picked` / `owned_paints` locals remain available to the mini tab exactly as before (paints tab still executes first).

- [ ] **Step 3: Verify**

Run: `.venv/Scripts/python -c "import ui.paints_tab"` → exit 0.
Run: `.venv/Scripts/python -m pytest -q` → PASS.

- [ ] **Step 4: Commit**

```bash
git add ui/paints_tab.py app.py
git commit -m "refactor(ui): extract Paints tab into ui/paints_tab.py"
```

---

### Task 7: Extract `ui/palette_editor.py` (slots + recipe load/save + callbacks)

**Files:**
- Create: `ui/palette_editor.py`
- Modify: `app.py` (replace recipe-loader [339-352] + palette-slots [354-406] with `palette, n = palette_editor.render(book, sel, picked)`; replace save-recipe expander [452-459] with `palette_editor.render_save_recipe(palette, n)`; move callbacks `_apply_paste_hex` [85-91] and `_blend_neighbours` [94-102] into the module).

**Interfaces:**
- Consumes: `ui.context` (CATALOG, CUSTOM, CODE_LABEL, CATALOG_CODES), `ui.keys`, `ui.helpers.swatch`, `mini_highlight_advisor` palette/recipes/collection/catalog/color APIs.
- Produces:
  - `ui.palette_editor.render(book, sel, picked) -> tuple[list[PaintColor], int]` returning `(palette, n)`. Renders the recipe loader then the palette slots (same on-screen order as today). `picked` is the set of owned codes for the owned/not-owned badges.
  - `ui.palette_editor.render_save_recipe(palette, n) -> None` — the "Save as recipe" expander.

- [ ] **Step 1: Create `ui/palette_editor.py`**

Move, in this order inside `render()`:
1. Recipe loader (app.py 339-352) — uses `load_all`, `to_palette`, `find_by_name`, `Counter(p.name ...)`, sets `keys.N` + `keys.slot_code(i)`/`keys.slot_hex(i)`, `st.rerun()`.
2. Palette slots (app.py 354-406) — the `setdefault(keys.N, 5)`, the `st.slider("Number of layers", 3, 7, key=keys.N)` → `n`, the per-slot selectbox/color_picker/paste with `keys.slot_code(i)`/`keys.slot_hex(i)`/`keys.slot_hexinput(i)`, the owned badge via `picked`, `collection.nearest_paint`, and the "blend neighbours" button with `key=keys.blend(i)` and `on_click=_blend_neighbours, args=(i, n)`.

Move the two callbacks to module level, swapping raw strings for `keys.*` and `CUSTOM` for `context.CUSTOM`:

```python
# ui/palette_editor.py  (callbacks)
def _apply_paste_hex(i: int) -> None:
    norm = valid_hex(st.session_state.get(keys.slot_hexinput(i), ""))
    if norm is not None:
        st.session_state[keys.slot_hex(i)] = norm


def _blend_neighbours(i: int, n: int) -> None:
    lo = st.session_state.get(keys.slot_hex(i - 1), ramp_hex(i - 1, n))
    hi = st.session_state.get(keys.slot_hex(i + 1), ramp_hex(i + 1, n))
    st.session_state[keys.slot_hex(i)] = blend_hex_lab(lo, hi)
    st.session_state[keys.slot_code(i)] = context.CUSTOM
```

`render()` returns `(palette, n)`. `render_save_recipe(palette, n)` is the expander body (app.py 452-459), using `keys.SAVE_NAME` for the name field. Copy the slot/recipe bodies verbatim except for the key-string and context substitutions.

Imports needed: `streamlit as st`; from `mini_highlight_advisor.palette`: `DEFAULT_PALETTE, PaintColor, role_names, ramp_hex, default_ramp, valid_hex`; from `mini_highlight_advisor.color`: `blend_hex_lab`; from `mini_highlight_advisor.recipes`: `load_all, to_palette, save_user, Recipe, RecipeStep`; from `mini_highlight_advisor.catalog`: `find_by_code, find_by_name`; from `mini_highlight_advisor import collection`; from `collections`: `Counter`; and `from ui import context, helpers, keys`.

- [ ] **Step 2: Update `app.py`**

Replace 339-352 + 354-406 with:

```python
        palette, n = palette_editor.render(book, sel, picked)
```

Replace 452-459 with:

```python
        palette_editor.render_save_recipe(palette, n)
```

Delete the `_apply_paste_hex` / `_blend_neighbours` defs (85-102). Add `from ui import palette_editor`. Remove now-unused imports from app.py that only the palette editor used (`DEFAULT_PALETTE`, `PaintColor`, `ramp_hex`, `default_ramp` if unused elsewhere, `blend_hex_lab`, `to_palette`, `Recipe`, `RecipeStep`, `find_by_name`, `Counter`) — verify each is unused before removing.

- [ ] **Step 3: Verify**

Run: `.venv/Scripts/python -c "import ui.palette_editor"` → exit 0.
Run: `.venv/Scripts/python -m pytest -q` → PASS.
Confirm `n` is returned and consumed downstream (coverage + save-recipe still get the right layer count).

- [ ] **Step 4: Commit**

```bash
git add ui/palette_editor.py app.py
git commit -m "refactor(ui): extract palette + recipe editor into ui/palette_editor.py"
```

---

### Task 8: Extract `ui/coverage_editor.py` (coverage sliders + cap)

**Files:**
- Create: `ui/coverage_editor.py`
- Modify: `app.py` (replace coverage block [408-450] with `coverage = coverage_editor.render(n)`).

**Interfaces:**
- Consumes: `ui.keys`, `ui.helpers.current_cov_seed` (not needed — seed is local), `mini_highlight_advisor.palette` (`role_names`, `default_coverage`, `remainder_pct`, `slider_max_pct`).
- Produces: `ui.coverage_editor.render(n: int) -> list[float]` returning `coverage` (fractions summing to 1.0). Renders the per-band sliders, the remainder caption, and the "Reset to default curve" button. Callback `_cap_slider(idx, n_ctrl)` is module-level.

- [ ] **Step 1: Create `ui/coverage_editor.py`**

Move app.py 408-450 into `render(n)`. The current `_cap_slider(idx)` closes over `n_ctrl`; make it a module-level `_cap_slider(idx, n_ctrl)` and pass `args=(i, n_ctrl)` from the slider. Swap `cov_pct_{i}` for `keys.cov_pct(i)` and `cov_n` for `keys.COV_N`.

```python
# ui/coverage_editor.py
"""Per-layer coverage sliders (remainder model)."""
import streamlit as st

from mini_highlight_advisor.palette import (
    role_names, default_coverage, remainder_pct, slider_max_pct,
)
from ui import keys

_COV_FLOOR = 3.0


def _cap_slider(idx: int, n_ctrl: int) -> None:
    key = keys.cov_pct(idx)
    others = [st.session_state[keys.cov_pct(j)] for j in range(n_ctrl) if j != idx]
    smax = slider_max_pct(others, floor=_COV_FLOOR)
    if st.session_state[key] > smax:
        st.session_state[key] = smax


def render(n: int) -> list[float]:
    st.markdown("**Coverage** (% of the model each layer occupies)")
    roles_now = role_names(n)
    n_ctrl = n - 1  # controllable bands; lightest band is the auto remainder
    seed = [round(f * 100, 1) for f in default_coverage(n)]

    if st.session_state.get(keys.COV_N) != n:
        for i in range(n_ctrl):
            st.session_state[keys.cov_pct(i)] = seed[i]
        st.session_state[keys.COV_N] = n

    if st.button("Reset to default curve"):
        for i in range(n_ctrl):
            st.session_state[keys.cov_pct(i)] = seed[i]
        st.rerun()

    cov_pcts: list[float] = []
    for i in range(n_ctrl):
        val = st.slider(
            f"{roles_now[i]}", 0.0, 100.0, step=0.5,
            key=keys.cov_pct(i), on_change=_cap_slider, args=(i, n_ctrl),
        )
        cov_pcts.append(val)

    remainder = remainder_pct(cov_pcts)
    st.caption(f"**{roles_now[-1]} · auto: {remainder:.1f}%**  (remainder — always keeps ≥ {_COV_FLOOR:.0f}%)")
    return [p / 100.0 for p in (cov_pcts + [remainder])]  # fractions, sum == 1.0
```

- [ ] **Step 2: Update `app.py`**

Replace 408-450 with `coverage = coverage_editor.render(n)`. Add `from ui import coverage_editor`. Remove now-unused imports (`remainder_pct`, `slider_max_pct`, `default_coverage` if unused elsewhere in app.py).

- [ ] **Step 3: Verify**

Run: `.venv/Scripts/python -c "import ui.coverage_editor"` → exit 0.
Run: `.venv/Scripts/python -m pytest -q` → PASS.

- [ ] **Step 4: Commit**

```bash
git add ui/coverage_editor.py app.py
git commit -m "refactor(ui): extract coverage editor into ui/coverage_editor.py"
```

---

### Task 9: Extract `ui/regions_panel.py` (canvas + region list/add/delete/rename)

**Files:**
- Create: `ui/regions_panel.py`
- Modify: `app.py` (replace the columns block [228-308], the "### Editing" header [310-311], and the rename block [314-319] with `sel = regions_panel.render(book, rgb, shading, src_w, src_h)`; move the inline `state.load_region_into_widgets` call from Task 5 into this module).

**Interfaces:**
- Consumes: `ui.compat.st_canvas`, `ui.geometry` (points_from_object, region_outline_image), `ui.state.load_region_into_widgets`, `ui.helpers.current_cov_seed`, `ui.keys`, `mini_highlight_advisor.regions` (scale_points, polygons_to_mask), `mini_highlight_advisor.palette.default_ramp`, `PIL.Image`.
- Produces: `ui.regions_panel.render(book, rgb, shading, src_w, src_h) -> int` returning the selected region index `sel`. Handles the draw-mode canvas, region radio + selection-load, add/cancel/delete, the "Editing:" header, and rename. Contains `st.rerun()` calls exactly as today.

- [ ] **Step 1: Create `ui/regions_panel.py`**

Move app.py 226 (`draw_mode = ...`), 228-308 (columns), 310-311 (divider + "### Editing"), 314-319 (rename) into `render()`. Compute `disp_w`/`disp_h` inside (currently 224-225). Use:
- `keys.DRAW_MODE`, `keys.REGION_RADIO`, `keys.canvas(len(book.drawn))`, `keys.rename(sel)`, `keys.LOADED_G` (pop on add/delete), and the `RENAME_PREFIX` cleanup loops.
- `st_canvas` from `ui.compat`; `geometry.region_outline_image` / `geometry.points_from_object`; `helpers.current_cov_seed`; `state.load_region_into_widgets(book, sel)` in place of the inline block.

The rename cleanup loops (`for _k in [k for k in list(st.session_state) if k.startswith("rename_")]`) become `... if k.startswith(keys.RENAME_PREFIX)`.

Return `sel` at the end (after the rename block). The `book.selected = sel` line (267) stays right after the `load_region_into_widgets` call.

Copy the body verbatim except for the substitutions above; the control flow (draw mode, add/cancel/delete, reruns) is unchanged.

Signature note: `render` needs `shading.mask` (for `polygons_to_mask(...) & shading.mask` at line 287), so pass the whole `shading` object.

- [ ] **Step 2: Update `app.py`**

Replace lines 224-319 (from `disp_w = ...` through the rename block) with:

```python
        sel = regions_panel.render(book, rgb, shading, src_w, src_h)
        state.rehydrate_editor_widgets(book, sel)
```

Add `from ui import regions_panel`. Remove now-unused app.py imports that only regions used (`Image`, `scale_points`, `polygons_to_mask`, `default_ramp`, `RegionBook`/`new_book` may still be used for the `book` init — verify; `Region` if unused). Keep `from ui import state` (still used for rehydrate here).

- [ ] **Step 3: Verify**

Run: `.venv/Scripts/python -c "import ui.regions_panel"` → exit 0.
Run: `.venv/Scripts/python -m pytest -q` → PASS.
Grep `app.py`: no `st_canvas(...)` call, no `radio(...)`, no `polygons_to_mask` remain inline.

- [ ] **Step 4: Commit**

```bash
git add ui/regions_panel.py app.py
git commit -m "refactor(ui): extract regions panel into ui/regions_panel.py"
```

---

### Task 10: Extract `ui/results.py` (match + toggles + photo-quality + analyze + steps)

**Files:**
- Create: `ui/results.py`
- Modify: `app.py` (replace match-to-paints [465-481], edge/relief/norm toggles [483-501], photo-quality panel [503-516], and analyze + render [518-544] with `results.render(rgb, alpha, book, palette, picked, owned_paints, shading)`).

**Interfaces:**
- Consumes: `ui.helpers.swatch`, `ui.helpers.render_region_steps`, `ui.keys`, `ui.context.CATALOG`, `mini_highlight_advisor` APIs: `matching` (target_from_paint, target_from_hex), `advisor.advise`, `palette.role_names`, `input_check` (check_input, SHOOTING_GUIDE, PAINTED_CAPTURE_NOTE), `pipeline.analyze_regions`, `overlay.swatch_board`.
- Produces: `ui.results.render(rgb, alpha, book, palette, picked, owned_paints, shading) -> None`. Renders, in order: match-to-paints, edge/relief/per-region-norm controls, photo-quality panel, the combined preview, colour-scheme board, and per-region paint-along steps.

- [ ] **Step 1: Create `ui/results.py`**

Move app.py 465-544 into `render(...)`. Substitutions: `_swatch` → `helpers.swatch`; `_render_region_steps` → `helpers.render_region_steps`; `adhoc_hex`/`adhoc_on`/`edge_hl`/`edge_extreme`/`edge_sens`/`relief_cap`/`per_region_norm` → the corresponding `keys.*`; `CATALOG` → `context.CATALOG`. `analyze_regions(rgb, alpha, wp, wcov, drawn, ...)` where `wp, wcov, drawn = book.analyze_args()` (line 519). The toggles (`edges`, `extreme_edge`, `edge_sensitivity`, `relief_cap`, `per_region_norm`) are read from the checkboxes/slider and passed into `analyze_regions` exactly as today.

Imports: `streamlit as st`; from `mini_highlight_advisor.matching`: `target_from_paint, target_from_hex`; from `mini_highlight_advisor.advisor`: `advise`; from `mini_highlight_advisor.palette`: `role_names`; from `mini_highlight_advisor.input_check`: `check_input, SHOOTING_GUIDE, PAINTED_CAPTURE_NOTE`; from `mini_highlight_advisor.pipeline`: `analyze_regions`; from `mini_highlight_advisor.overlay`: `swatch_board`; `from ui import context, helpers, keys`.

- [ ] **Step 2: Update `app.py`**

Replace 465-544 with:

```python
        results.render(rgb, alpha, book, palette, picked, owned_paints, shading)
```

Add `from ui import results`. Remove now-unused app.py imports (`target_from_paint`, `target_from_hex`, `advise`, `check_input`, `SHOOTING_GUIDE`, `PAINTED_CAPTURE_NOTE`, `analyze_regions`, `swatch_board`, `role_names` if unused elsewhere).

- [ ] **Step 3: Verify**

Run: `.venv/Scripts/python -c "import ui.results"` → exit 0.
Run: `.venv/Scripts/python -m pytest -q` → PASS.

- [ ] **Step 4: Commit**

```bash
git add ui/results.py app.py
git commit -m "refactor(ui): extract results/analyze panel into ui/results.py"
```

---

### Task 11: Final slim `app.py` + full verification

**Files:**
- Modify: `app.py` (final cleanup: import block, orchestration order, remove any dead imports/vars).

**Interfaces:**
- Consumes: all `ui.*` modules.
- Produces: the final orchestrator. Expected shape:

```python
import os

import streamlit as st

from ui import (
    compat, context, state, helpers,
    paints_tab, regions_panel, palette_editor, coverage_editor, results,
)

st.set_page_config(page_title="Mini Highlight Advisor", layout="wide")
st.title("Mini Highlight Advisor")
st.caption(
    "Upload a photo of a primed miniature (background-removed PNG is fastest). "
    "You'll get a painted preview + a paint-by-layer plan. Best with a raking "
    "side light (not on-axis flash) — that gives the sculpt the shadows the tool reads."
)

tab_mini, tab_paints = st.tabs(["🖌️ Miniature", "🎨 Paints"])

# st.tabs runs BOTH bodies every rerun, in code order. Fill Paints FIRST so
# owned_paints is finalised before the Miniature tab renders ownership badges.
with tab_paints:
    picked, owned_paints = paints_tab.render()

with tab_mini:
    if "book" not in st.session_state:
        from mini_highlight_advisor.region_state import new_book
        st.session_state["book"] = new_book(5)
    book = st.session_state["book"]

    uploaded = st.file_uploader("Mini photo", type=["png", "jpg", "jpeg"])
    if uploaded is None:
        st.info("Upload a photo of a primed miniature to begin.")
        st.stop()

    suffix = os.path.splitext(uploaded.name)[1]
    try:
        with st.spinner("Preparing shading (first run downloads the depth model if no alpha channel)..."):
            rgb, alpha, shading = helpers.shading(uploaded.getvalue(), suffix)
        src_h, src_w = rgb.shape[:2]

        sel = regions_panel.render(book, rgb, shading, src_w, src_h)
        state.rehydrate_editor_widgets(book, sel)

        st.divider()
        st.markdown(f"### Editing: **{book.names()[sel]}**")

        palette, n = palette_editor.render(book, sel, picked)
        coverage = coverage_editor.render(n)
        palette_editor.render_save_recipe(palette, n)

        book.set_palette_at(sel, palette)
        book.set_coverage_at(sel, coverage)

        results.render(rgb, alpha, book, palette, picked, owned_paints, shading)
    except Exception as e:
        st.error("Error processing image — see traceback below.")
        st.exception(e)
```

> Ordering note: the "### Editing" header currently renders *inside* the region flow (app.py 310-311). Decide during Task 9 whether it belongs to `regions_panel.render` or stays in `app.py`; keep it in exactly one place and in the same on-screen position (immediately before the palette editor). The shape above assumes it stays in `app.py` — if Task 9 put it in `regions_panel`, remove it here.

- [ ] **Step 1: Reconcile the "### Editing" header** — ensure it appears exactly once, in its original position (after regions, before palette). Remove any duplicate.

- [ ] **Step 2: Remove dead imports/vars** — grep `app.py` for every top-level import and confirm it is still referenced; delete unused ones. Confirm no `_`-prefixed helper defs remain in `app.py`.

- [ ] **Step 3: Import + test sweep**

Run: `.venv/Scripts/python -c "import ui.compat, ui.context, ui.keys, ui.state, ui.helpers, ui.geometry, ui.paints_tab, ui.regions_panel, ui.palette_editor, ui.coverage_editor, ui.results"` → exit 0.
Run: `.venv/Scripts/python -m pytest -q` → all PASS.
Run: `.venv/Scripts/python -m py_compile app.py` → exit 0.
Report: final `app.py` line count (target < ~70).

- [ ] **Step 4: Commit**

```bash
git add app.py
git commit -m "refactor(ui): slim app.py to a thin orchestrator over ui/ package"
```

- [ ] **Step 5: USER smoke test (handoff)**

Ask the user to run `streamlit run app.py` and click through: upload a mini, draw a region, edit palette + coverage, load/save a recipe, toggle edge/relief/colored-mini, and confirm the combined preview + per-region steps render — verifying no behavior changed. Do not claim completion until the user confirms.

---

## Self-Review

**Spec coverage** (against the approved design):
- ✅ `ui/` package at repo root, thin `app.py` — Tasks 1-11.
- ✅ Centralize magic session keys — `ui/keys.py` (Task 1), applied in every subsequent task.
- ✅ Isolate the order-sensitive session choreography — `ui/state.py` (Task 5).
- ✅ 11 approved modules + the flagged `ui/context.py` — all created.
- ✅ Behavior-preserving (order, keys, callbacks, reruns) — Global Constraints + per-task substitution-only edits.
- ✅ Tests for pure helpers + user smoke test — Tasks 1 (keys), 2 (geometry), 3 (helpers); user smoke test Task 11 Step 5.
- ✅ Compat shim isolated for later retirement — Task 4.

**Placeholder scan:** The `...` markers in Tasks 3 and 4 explicitly mean "copy the verbatim body from the named app.py line range" — the source of truth is the existing file, and repasting risks silent transcription drift in a behavior-preserving refactor. Every new-code file (keys, context, state, coverage_editor, paints_tab, callbacks, final app.py) is given in full. No TBD/TODO left.

**Type consistency:** `render()` return contracts are consistent across producers/consumers — `paints_tab.render() -> (picked, owned_paints)`; `regions_panel.render(...) -> sel`; `palette_editor.render(...) -> (palette, n)`; `coverage_editor.render(n) -> coverage`; `results.render(...) -> None`. `n` flows palette_editor → coverage_editor + save_recipe. `keys.*` builder names are used identically everywhere.
