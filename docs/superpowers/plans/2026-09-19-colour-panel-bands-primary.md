# Colour Panel — Bands-Primary Restructure Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Restructure `ui/colour_panel.py` so bands are the primary interaction (shown first), replace the layer-count slider with `[– band] [+ band]` buttons, and compress Level 2 ramp variants into a single quick-apply row.

**Architecture:** All changes are isolated to `ui/colour_panel.py`. No new modules, no data-model changes. Three independent edits: (1) add/remove helpers + button UI inside `_render_level3`; (2) compact the Level 2 variant buttons into a one-row quick-apply; (3) reorder the `render()` call sequence so L3 → coverage → L2 → L1 → scheme-save. Each task is self-contained and testable independently.

**Tech Stack:** Python 3.11, Streamlit, existing `ui/keys.py` key builders, `mini_highlight_advisor/palette.py` (DEFAULT_PALETTE, ramp_hex).

**Spec:** `docs/superpowers/specs/2026-09-02-studio-ux-colour-loop-design.md` — Level 3 bands section + Level 2 quick-apply paragraphs.

## Global Constraints

- Never commit directly to main — feature branch + PR.
- Branch from main (or from `fix/recipe-name-and-whole-mini-ramp` if that PR isn't merged yet — ask before branching).
- Band count bounds: min 3, max 7. These are existing invariants; do not change them.
- Session key names in `ui/keys.py` are frozen — must not be renamed (widget state resets on key rename). Add new keys only when strictly necessary.
- Tests call no Streamlit widgets directly; they test pure logic extracted from the render functions, consistent with the existing test pattern in `tests/test_ui_colour_panel.py`.
- Run `.venv\Scripts\python -m pytest -x -q` after every task to confirm no regressions.

---

### Task 1: Add/remove band buttons (replace layer-count slider)

**Files:**
- Modify: `ui/colour_panel.py` — `_render_level3` function (currently lines 196–286)
- Test: `tests/test_ui_colour_panel.py`

**Context — what changes:** The current code has:
```python
st.session_state.setdefault(keys.N, 5)
n = st.slider("Number of layers", 3, 7, key=keys.N)
```
Replace with two helper functions (`_remove_last_band`, `_add_band`) and a compact `[– band] [5 bands] [+ band]` button row. The slider is deleted.

**Interfaces:**
- Produces:
  - `_remove_last_band(n: int) -> None` — decrements `session[keys.N]`, clears slot session keys for the removed band index. No-op if `n <= 3`.
  - `_add_band(n: int) -> None` — increments `session[keys.N]`, seeds new slot's session keys with default values. No-op if `n >= 7`.
  - `n: int` — the band count used throughout `_render_level3` is now read from session state rather than from a slider widget return value.

- [ ] **Step 1: Write failing tests**

Add to `tests/test_ui_colour_panel.py`:

```python
def _make_session():
    """Minimal stand-in for st.session_state (plain dict)."""
    return {}


def test_remove_last_band_decrements_count():
    from ui import keys
    import streamlit as st
    st.session_state[keys.N] = 5
    from ui.colour_panel import _remove_last_band
    _remove_last_band(5)
    assert st.session_state[keys.N] == 4


def test_remove_last_band_clears_slot_keys():
    from ui import keys
    import streamlit as st
    n = 5
    st.session_state[keys.N] = n
    st.session_state[keys.slot_code(n - 1)] = "ABC"
    st.session_state[keys.slot_hex(n - 1)] = "#aabbcc"
    st.session_state[keys.slot_hexinput(n - 1)] = "#aabbcc"
    from ui.colour_panel import _remove_last_band
    _remove_last_band(n)
    assert keys.slot_code(n - 1) not in st.session_state
    assert keys.slot_hex(n - 1) not in st.session_state
    assert keys.slot_hexinput(n - 1) not in st.session_state


def test_remove_last_band_noop_at_minimum():
    from ui import keys
    import streamlit as st
    st.session_state[keys.N] = 3
    from ui.colour_panel import _remove_last_band
    _remove_last_band(3)
    assert st.session_state[keys.N] == 3


def test_add_band_increments_count():
    from ui import keys
    import streamlit as st
    st.session_state[keys.N] = 4
    from ui.colour_panel import _add_band
    _add_band(4)
    assert st.session_state[keys.N] == 5


def test_add_band_seeds_new_slot_keys():
    from ui import keys
    import streamlit as st
    n = 4
    st.session_state[keys.N] = n
    # Ensure slot at index n doesn't pre-exist
    st.session_state.pop(keys.slot_code(n), None)
    st.session_state.pop(keys.slot_hex(n), None)
    from ui.colour_panel import _add_band
    _add_band(n)
    assert keys.slot_hex(n) in st.session_state
    assert st.session_state[keys.slot_hex(n)]  # non-empty hex


def test_add_band_noop_at_maximum():
    from ui import keys
    import streamlit as st
    st.session_state[keys.N] = 7
    from ui.colour_panel import _add_band
    _add_band(7)
    assert st.session_state[keys.N] == 7
```

- [ ] **Step 2: Run tests — expect FAIL**

```
cd C:\Users\ag\alvaro\git\mini-highlight-advisor
.venv\Scripts\python -m pytest tests/test_ui_colour_panel.py::test_remove_last_band_decrements_count tests/test_ui_colour_panel.py::test_remove_last_band_clears_slot_keys tests/test_ui_colour_panel.py::test_remove_last_band_noop_at_minimum tests/test_ui_colour_panel.py::test_add_band_increments_count tests/test_ui_colour_panel.py::test_add_band_seeds_new_slot_keys tests/test_ui_colour_panel.py::test_add_band_noop_at_maximum -v
```

Expected: `ImportError` — `_remove_last_band` and `_add_band` don't exist yet.

- [ ] **Step 3: Add `_remove_last_band` and `_add_band` to `colour_panel.py`**

Add these two functions after `_blend_neighbours` (currently around line 195) and before `_render_level3`:

```python
def _remove_last_band(n: int) -> None:
    """Shrink band count by 1 and clear the removed slot's session keys. No-op if n <= 3."""
    if n <= 3:
        return
    i = n - 1
    st.session_state.pop(keys.slot_code(i), None)
    st.session_state.pop(keys.slot_hex(i), None)
    st.session_state.pop(keys.slot_hexinput(i), None)
    st.session_state[keys.N] = n - 1


def _add_band(n: int) -> None:
    """Grow band count by 1 and seed the new slot with a default colour. No-op if n >= 7."""
    if n >= 7:
        return
    new_idx = n  # new band's 0-based index (becomes the new lightest)
    if keys.slot_code(new_idx) not in st.session_state:
        default = (DEFAULT_PALETTE[new_idx]
                   if new_idx < len(DEFAULT_PALETTE)
                   else PaintColor(f"Grey {new_idx + 1}", ramp_hex(new_idx, n + 1)))
        st.session_state[keys.slot_code(new_idx)] = default.code
        st.session_state[keys.slot_hex(new_idx)] = default.hex
    st.session_state[keys.N] = n + 1
```

- [ ] **Step 4: Replace the slider with the button row inside `_render_level3`**

In `_render_level3`, find and replace:

```python
    st.session_state.setdefault(keys.N, 5)
    n = st.slider("Number of layers", 3, 7, key=keys.N)
```

with:

```python
    st.session_state.setdefault(keys.N, 5)
    n = st.session_state[keys.N]
    c_minus, c_label, c_plus = st.columns([1, 2, 1])
    if c_minus.button("– band", disabled=n <= 3, key="band_remove"):
        _remove_last_band(n)
        st.rerun()
    c_label.markdown(f"**{n} bands**")
    if c_plus.button("+ band", disabled=n >= 7, key="band_add"):
        _add_band(n)
        st.rerun()
```

- [ ] **Step 5: Run tests — expect PASS**

```
.venv\Scripts\python -m pytest tests/test_ui_colour_panel.py::test_remove_last_band_decrements_count tests/test_ui_colour_panel.py::test_remove_last_band_clears_slot_keys tests/test_ui_colour_panel.py::test_remove_last_band_noop_at_minimum tests/test_ui_colour_panel.py::test_add_band_increments_count tests/test_ui_colour_panel.py::test_add_band_seeds_new_slot_keys tests/test_ui_colour_panel.py::test_add_band_noop_at_maximum -v
```

- [ ] **Step 6: Run full suite to confirm no regressions**

```
.venv\Scripts\python -m pytest -x -q
```

- [ ] **Step 7: Commit**

```
git add ui/colour_panel.py tests/test_ui_colour_panel.py
git commit -m "feat: replace band-count slider with + / – band buttons"
```

---

### Task 2: Level 2 — compact single-row quick-apply variants

**Files:**
- Modify: `ui/colour_panel.py` — `_render_level2` function (currently lines 111–180)
- Test: `tests/test_ui_colour_panel.py`

**Context — what changes:** The current code renders 4 full rows (one per variant), each with a swatch grid + a full-width Apply button. The spec calls for a single compact row: `[Ramp] [Complementary] [Warm] [Cool]` buttons that apply immediately with no extra step. The per-variant swatch previews are dropped — the left-column mini render is the preview.

The write-back logic (updating `book.drawn[sel-1].ramp_midtone / ramp_variant` or `book.whole_ramp_midtone / whole_ramp_variant`) is unchanged — it just moves into the compact button handler.

**Interfaces:**
- Consumes: `ramps: dict[str, list[str]]` built from `mid_hex` (unchanged)
- Produces: clicking any of the 4 buttons calls `_apply_ramp(hexes, n)` and writes back the ramp decision to the region, exactly as before.

- [ ] **Step 1: Write failing tests**

The write-back logic is already covered by existing tests (`test_level2_writeback_sets_ramp_decision`, `test_level2_writeback_whole_mini_uses_book_fields`). Add one test that verifies the extracted helper function signature:

Add to `tests/test_ui_colour_panel.py`:

```python
def test_write_ramp_decision_drawn_region():
    """_write_ramp_decision writes midtone + variant back to the correct drawn region."""
    from mini_highlight_advisor.region_state import new_book
    from mini_highlight_advisor.palette import default_ramp, default_coverage
    import numpy as np
    book = new_book(5)
    m = np.zeros((8, 8), bool); m[2:5, 2:5] = True
    book.add(m, "Cloak", default_ramp(5), default_coverage(5))

    from ui.colour_panel import _write_ramp_decision
    _write_ramp_decision(book, sel=1, mid_hex="#a03020", variant="complementary")

    assert book.drawn[0].ramp_midtone == "#a03020"
    assert book.drawn[0].ramp_variant == "complementary"


def test_write_ramp_decision_whole_mini():
    """_write_ramp_decision at sel==0 writes to book.whole_ramp_midtone/variant."""
    from mini_highlight_advisor.region_state import new_book
    book = new_book(5)

    from ui.colour_panel import _write_ramp_decision
    _write_ramp_decision(book, sel=0, mid_hex="#c02030", variant="standard")

    assert book.whole_ramp_midtone == "#c02030"
    assert book.whole_ramp_variant == "standard"
```

- [ ] **Step 2: Run tests — expect FAIL**

```
.venv\Scripts\python -m pytest tests/test_ui_colour_panel.py::test_write_ramp_decision_drawn_region tests/test_ui_colour_panel.py::test_write_ramp_decision_whole_mini -v
```

Expected: `ImportError` — `_write_ramp_decision` doesn't exist yet.

- [ ] **Step 3: Extract `_write_ramp_decision` helper and compact the button row**

**Step 3a — Extract helper.** Add after `_apply_ramp` (around line 109):

```python
def _write_ramp_decision(book, sel: int, mid_hex: str, variant: str) -> None:
    """Persist the ramp decision (midtone hex + variant key) on the book."""
    if sel > 0:
        book.drawn[sel - 1].ramp_midtone = mid_hex
        book.drawn[sel - 1].ramp_variant = variant
    else:
        book.whole_ramp_midtone = mid_hex
        book.whole_ramp_variant = variant
```

**Step 3b — Replace the four Apply-button rows with one compact row.**

In `_render_level3`, the current body (after the complement-shortcut block and `mid_hex = st.color_picker(...)`) is:

```python
    ramps = {
        "Ramp": ramp_from_midtone(mid_hex, n),
        "Complementary": ramp_from_midtone(hue_rotate(mid_hex, 180), n),
        "Warm (+30°)":   ramp_from_midtone(hue_rotate(mid_hex, 30), n),
        "Cool (−30°)":   ramp_from_midtone(hue_rotate(mid_hex, -30), n),
    }

    for label, hexes in ramps.items():
        paints = [
            collection.nearest_paint(PaintColor(f"r{i}", h).rgb, context.CATALOG)
            for i, h in enumerate(hexes)
        ]
        row_cols = st.columns([2] + [1] * n)
        row_cols[0].markdown(f"**{label}**")
        for i, (h, p) in enumerate(zip(hexes, paints)):
            row_cols[i + 1].markdown(helpers.swatch(h, size="1.8em"), unsafe_allow_html=True)
            if p:
                row_cols[i + 1].caption(p.name[:10])

        if st.button(f"Apply {label}", key=f"apply_ramp_{label}"):
            _apply_ramp(hexes, n)
            if sel > 0:
                book.drawn[sel - 1].ramp_midtone = mid_hex
                book.drawn[sel - 1].ramp_variant = _VARIANT_MAP[label]
            else:
                book.whole_ramp_midtone = mid_hex
                book.whole_ramp_variant = _VARIANT_MAP[label]
```

Replace the entire block above with:

```python
    ramps = {
        "Ramp": ("standard", ramp_from_midtone(mid_hex, n)),
        "Complementary": ("complementary", ramp_from_midtone(hue_rotate(mid_hex, 180), n)),
        "Warm (+30°)":   ("warm",          ramp_from_midtone(hue_rotate(mid_hex, 30), n)),
        "Cool (−30°)":   ("cool",          ramp_from_midtone(hue_rotate(mid_hex, -30), n)),
    }

    btn_cols = st.columns(len(ramps))
    for col, (label, (variant_key, hexes)) in zip(btn_cols, ramps.items()):
        if col.button(label, key=f"apply_ramp_{label}", use_container_width=True):
            _apply_ramp(hexes, n)
            _write_ramp_decision(book, sel, mid_hex, variant_key)
```

Also remove the now-unused `_VARIANT_MAP` dict that was defined at the top of `_render_level2` (it was `{"Ramp": "standard", ...}`). The variant key is now embedded directly in the `ramps` dict.

Also remove the `collection` import from the top of the file if it's no longer used by `_render_level2` (check if anything else in the file still calls `collection.nearest_paint` first — if Level 3 is the only call site, it's already imported via `from mini_highlight_advisor import collection` and still needed there).

- [ ] **Step 4: Run tests — expect PASS**

```
.venv\Scripts\python -m pytest tests/test_ui_colour_panel.py::test_write_ramp_decision_drawn_region tests/test_ui_colour_panel.py::test_write_ramp_decision_whole_mini -v
```

- [ ] **Step 5: Run full suite**

```
.venv\Scripts\python -m pytest -x -q
```

- [ ] **Step 6: Commit**

```
git add ui/colour_panel.py tests/test_ui_colour_panel.py
git commit -m "feat: Level 2 compact quick-apply row; extract _write_ramp_decision helper"
```

---

### Task 3: Bands-primary reorder in `render()`

**Files:**
- Modify: `ui/colour_panel.py` — `render()` function (currently lines 328–356)
- Test: `tests/test_ui_colour_panel.py`

**Context — what changes:** The current `render()` call order is:
```
L1 scheme → L2 ramp → L3 bands → coverage → scheme-save
```
After this task:
```
L3 bands → coverage → L2 ramp → L1 scheme → scheme-save
```

This puts the most concrete, immediate work (bands) at the top of the colour panel and the more abstract whole-mini scheme generation at the bottom. The dependency that L2 needs `n` (band count) is satisfied because `_render_level3` still runs first and `n` is read from it.

Also removed in this task: the per-region thumbnail (`st.image(thumb, width=220)` in the render function header). The spec drops it — the left-column mini render in `editor.py` is the preview.

**Interfaces:**
- Consumes: `palette, n` returned from `_render_level3(book, sel, picked)` — unchanged
- Produces: `render()` still calls `book.set_palette_at(sel, palette)` and `book.set_coverage_at(sel, cov)` and fires deferred reruns — unchanged

- [ ] **Step 1: Write failing tests**

Add to `tests/test_ui_colour_panel.py`:

```python
def test_render_function_still_exposes_expected_signature():
    """render() must accept (book, sel, picked, owned_paints, rgb=None)."""
    import inspect
    from ui import colour_panel
    sig = inspect.signature(colour_panel.render)
    params = list(sig.parameters)
    assert params == ["book", "sel", "picked", "owned_paints", "rgb"]


def test_level3_runs_before_level2_dependency():
    """n (band count) flows from _render_level3 return value — verify n is returned."""
    import inspect, ui.colour_panel as cp
    # _render_level3 must return (palette, n)
    # Inspect the source to verify return signature — integration test without Streamlit.
    src = inspect.getsource(cp._render_level3)
    assert "return palette, n" in src


def test_thumbnail_removed_from_render():
    """The per-region thumbnail (highlight_region_image) is no longer called from render()."""
    import inspect, ui.colour_panel as cp
    src = inspect.getsource(cp.render)
    assert "highlight_region_image" not in src
```

- [ ] **Step 2: Run tests — expect FAIL**

```
.venv\Scripts\python -m pytest tests/test_ui_colour_panel.py::test_render_function_still_exposes_expected_signature tests/test_ui_colour_panel.py::test_level3_runs_before_level2_dependency tests/test_ui_colour_panel.py::test_thumbnail_removed_from_render -v
```

Expected: `test_thumbnail_removed_from_render` fails (thumbnail still present); others may pass.

- [ ] **Step 3: Rewrite `render()` with new call order**

Replace the entire `render()` function (currently lines 328–356) with:

```python
def render(book, sel: int, picked, owned_paints, rgb=None) -> None:
    """Render the three-level colour panel for the selected region.

    Order: Bands (primary) → Coverage → Ramp → Scheme → Save.
    """
    st.markdown(f"**Editing:** {book.names()[sel]}")

    # Level 3 first: bands are the primary interaction.
    palette, n = _render_level3(book, sel, picked)
    book.set_palette_at(sel, palette)

    # Coverage lives next to bands (both are about 'how many layers and how wide').
    st.divider()
    cov = coverage_editor.render(n)
    book.set_coverage_at(sel, cov)

    # Level 2: ramp quick-apply to seed the bands.
    _render_level2(book, sel, n, owned_paints)

    # Level 1: whole-mini scheme — collapsed once generated.
    _render_level1(book, owned_paints)

    # Scheme save / swap at the bottom.
    _render_scheme_save(book)

    # Deferred rerun after Apply Ramp / Load recipe so Level 3 has already updated
    # the book palette before the analysis re-runs — one click = one visible update.
    _deferred = st.session_state.pop("_ramp_applied", False)
    _deferred = st.session_state.pop("_recipe_loaded", False) or _deferred
    if _deferred:
        st.rerun()
```

Note: also remove the old thumbnail block from the function (the two lines starting `if rgb is not None and book.drawn and sel >= 1:`).

- [ ] **Step 4: Run tests — expect PASS**

```
.venv\Scripts\python -m pytest tests/test_ui_colour_panel.py::test_render_function_still_exposes_expected_signature tests/test_ui_colour_panel.py::test_level3_runs_before_level2_dependency tests/test_ui_colour_panel.py::test_thumbnail_removed_from_render -v
```

- [ ] **Step 5: Run full suite**

```
.venv\Scripts\python -m pytest -x -q
```

- [ ] **Step 6: Commit**

```
git add ui/colour_panel.py tests/test_ui_colour_panel.py
git commit -m "feat: bands-primary layout — L3 first, coverage, L2 ramp, L1 scheme; drop thumbnail"
```

---

## Self-Review

**Spec coverage:**

| Spec requirement | Task |
|---|---|
| `[+ band] [– band]` replace slider | Task 1 |
| Band count bounds 3–7 preserved | Task 1 (`_remove_last_band`/`_add_band` guards) |
| Removed slot session keys cleared on shrink | Task 1 `_remove_last_band` |
| New slot seeded with default on grow | Task 1 `_add_band` |
| Level 2 quick-apply — no extra Apply step | Task 2 |
| Ramp variants in one compact row | Task 2 |
| Write-back (midtone/variant) still fires | Task 2 `_write_ramp_decision` |
| Bands are first thing in Colour sub-tab | Task 3 |
| Coverage lives near bands | Task 3 |
| Per-region thumbnail dropped | Task 3 |

**Placeholder scan:** No TBDs, no "similar to above". All code is concrete.

**Type consistency:**
- `_remove_last_band(n: int) -> None` — defined Task 1, tested Task 1
- `_add_band(n: int) -> None` — defined Task 1, tested Task 1
- `_write_ramp_decision(book, sel: int, mid_hex: str, variant: str) -> None` — defined Task 2, tested Task 2
- `palette, n = _render_level3(book, sel, picked)` — return signature unchanged; Task 3 `render()` consumes it correctly
- `coverage_editor.render(n)` — called with `n` from `_render_level3` return; works before or after reorder because n is read from session state inside coverage_editor via `keys.COV_N`
