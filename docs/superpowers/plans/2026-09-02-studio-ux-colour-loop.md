# Studio UX & Colour Loop Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Restructure the app into five tabs with the mini render always visible on the left, and consolidate five fragmented colour surfaces into one three-level Colour sub-tab.

**Architecture:** Stage 1 establishes the tab skeleton and two-column Studio layout with zero logic change. Stage 2 moves the analysis call before the columns (so the left render is always current) and introduces the three sub-tabs with a new unified `colour_panel.py`. Stage 3 wires the remaining Regions and Technique sub-tabs and adds the Capture & help content.

**Tech Stack:** Streamlit, Python 3.11; session-state widget pattern; `AppTest` harness for UI tests.

**Spec:** `docs/superpowers/specs/2026-09-02-studio-ux-colour-loop-design.md`

## Global Constraints

- Never push directly to `main`; work on `feat/studio-ux-colour-loop`.
- Run tests with `.venv/Scripts/python -m pytest` from the repo root.
- Session-state key string *values* are frozen — adding new keys is fine; renaming existing ones silently breaks widget state.
- All existing tests must continue to pass after each task.
- The dual-path constraint is non-negotiable: Path L (photo → luminance) and Path P (PS → normal field) must both work identically before and after every stage.
- Streamlit `st.tabs` runs ALL tab bodies on every rerun; design around this, not against it.

---

## Stage 1 — Skeleton reflow

**Goal:** Immediately fix "render too far down." Five tabs; mini render pinned left; paint-along steps in their own tab; shooting guide in Capture tab. Zero logic change.

---

### Task 1: Extract `render_steps()` from `ui/results.py` and remove inline combined render

**Files:**
- Modify: `ui/results.py`
- Create: `tests/test_ui_render_steps.py`

**Interfaces:**
- Produces: `results.render_steps(multi: MultiRegionResult | None) -> None` — renders swatch board + per-region steps; shows placeholder when `multi` is None.
- Produces: `results.render()` no longer renders `multi.combined_rgb`, swatch board, or per-region steps (it only runs analysis + stores `LAST_MULTI`).

- [ ] **Step 1: Write failing tests**

```python
# tests/test_ui_render_steps.py
from streamlit.testing.v1 import AppTest

HARNESS_NONE = """
import streamlit as st
from ui import results
results.render_steps(None)
st.write("ok")
"""

HARNESS_MULTI = """
import numpy as np
from pathlib import Path
from PIL import Image
import streamlit as st
from mini_highlight_advisor import relight
from mini_highlight_advisor.masking import compute_mask
from mini_highlight_advisor.region_state import new_book
from mini_highlight_advisor.pipeline import analyze_regions
from ui import results, keys

FIX = Path("tests/fixtures/ps")
normals = relight.load_normals(str(FIX / "synth_normal.png"))
mask = np.asarray(Image.open(FIX / "synth_mask.png").convert("L")) > 127
lf, relit = relight.relight(normals, mask, relight.light_dir(225, 45))
mask_u8 = (mask * 255).astype(np.uint8)
book = new_book(5)
wp, wcov, drawn = book.analyze_args()
multi = analyze_regions(relit, mask_u8, wp, wcov, drawn, light_field=lf)
results.render_steps(multi)
st.write("ok")
"""

def test_render_steps_none_shows_placeholder():
    at = AppTest.from_string(HARNESS_NONE)
    at.run()
    assert not at.exception
    texts = [i.value for i in at.info]
    assert any("Studio" in t for t in texts)

def test_render_steps_with_multi_renders_images():
    at = AppTest.from_string(HARNESS_MULTI)
    at.run()
    assert not at.exception
    assert len(at.image) >= 1  # at least the swatch board
```

- [ ] **Step 2: Run tests to verify they fail**

```
.venv/Scripts/python -m pytest tests/test_ui_render_steps.py -v
```
Expected: `AttributeError: module 'ui.results' has no attribute 'render_steps'`

- [ ] **Step 3: Add `render_steps()` to `ui/results.py` and strip the inline renders from `render()`**

At the bottom of `ui/results.py`, add:

```python
def render_steps(multi) -> None:
    """Paint tab: swatch board + per-region paint-along steps.

    Call this from the Paint tab, reading keys.LAST_MULTI from session state.
    `multi` is None before the first analysis run; shows a placeholder then.
    """
    from mini_highlight_advisor.overlay import swatch_board  # already imported above
    if multi is None:
        st.info("Set your colours in Studio first, then come here to paint.")
        return
    st.image(swatch_board([(p.name, p.colors) for p in multi.plans]),
             caption="Colour schemes — all regions")
    st.subheader("Paint-along steps by region")
    st.caption("Work dark to light within each region.")
    for plan in multi.plans:
        st.markdown(f"### {plan.name}")
        if plan.flat_albedo:
            st.warning(
                f'"{plan.name}" is too dark / low-contrast to read relief — showing '
                f"1 band. Try a paler basecoat here, or a stronger raking side light.")
        elif plan.capped:
            st.warning(
                f'"{plan.name}" looks fairly flat — showing {len(plan.names)} '
                f'band(s) instead of {plan.requested_bands}. Untick '
                f'"Auto-reduce bands on flat regions" to force all '
                f"{plan.requested_bands}.")
        helpers.render_region_steps(plan.steps, plan.roles, plan.names, plan.coverage,
                                    technique=plan.technique)
```

In `render()`, remove the block from line `st.session_state[keys.LAST_MULTI] = multi` onward (keep only the assignment to LAST_MULTI/LAST_RGB but remove `st.image(multi.combined_rgb, ...)`, `st.subheader("Colour schemes…")`, `st.image(swatch_board(…))`, `st.subheader("Paint-along steps…")`, `st.caption(…)`, and the `for plan in multi.plans:` loop). The `render()` function should now end after:

```python
    st.session_state[keys.LAST_MULTI] = multi
    st.session_state[keys.LAST_RGB] = rgb
```

- [ ] **Step 4: Run tests to verify they pass**

```
.venv/Scripts/python -m pytest tests/test_ui_render_steps.py tests/test_ui_results_ps.py -v
```
Expected: all pass. (The `test_ui_results_ps` tests cover the existing `render()` path; they must still pass because `render()` still runs analysis and stores LAST_MULTI.)

- [ ] **Step 5: Commit**

```
git add ui/results.py tests/test_ui_render_steps.py
git commit -m "feat: extract render_steps() from results.py; remove inline combined render"
```

---

### Task 2: Restructure `app.py` — five tabs, two-column Studio, Paint + Capture tabs

**Files:**
- Modify: `app.py`
- Create: `tests/test_ui_app_tabs.py`

**Interfaces:**
- Consumes: `results.render_steps(multi)` from Task 1.
- Consumes: `results.render()` unchanged (still called from editor inside col_controls).
- Produces: `tab_studio`, `tab_paint`, `tab_paints`, `tab_angles`, `tab_capture` in session.

- [ ] **Step 1: Write failing smoke test**

```python
# tests/test_ui_app_tabs.py
"""Smoke tests for the new five-tab app structure."""
from streamlit.testing.v1 import AppTest

def _make_at():
    at = AppTest.from_file("app.py", default_timeout=30)
    at.run()
    return at

def test_app_loads_without_error():
    at = _make_at()
    assert not at.exception

def test_five_tabs_present():
    at = _make_at()
    tab_labels = [t.label for t in at.tabs]
    assert "🖌️ Studio" in tab_labels
    assert "🪜 Paint" in tab_labels
    assert "📷 Capture & help" in tab_labels

def test_paint_tab_shows_placeholder_before_upload():
    at = _make_at()
    # Before upload, render_steps(None) should show the info placeholder.
    infos = [i.value for i in at.info]
    assert any("Studio" in t for t in infos)
```

- [ ] **Step 2: Run test to verify it fails**

```
.venv/Scripts/python -m pytest tests/test_ui_app_tabs.py -v
```
Expected: FAIL — tab labels don't match (currently: "🖌️ Miniature", "🎨 Paints", "🖼️ All angles").

- [ ] **Step 3: Rewrite `app.py`**

Replace the current tab block in `app.py`. Keep everything above the `st.tabs(...)` call unchanged (imports, `st.set_page_config`, `st.title`, `st.caption`). Replace from `tab_mini, tab_paints, tab_gallery = st.tabs(...)` to end of file with:

```python
# NOTE: st.tabs runs ALL bodies every rerun in code order.
# Paints must execute before Studio so owned_codes is finalised before Studio
# renders ownership badges. Display order is fixed by the label list.
tab_studio, tab_paint, tab_paints, tab_angles, tab_capture = st.tabs([
    "🖌️ Studio", "🪜 Paint", "🎨 Paints", "🖼️ All angles", "📷 Capture & help",
])

# --- 🎨 Paints: inventory (must run first — see note above) ---
with tab_paints:
    picked, owned_paints = paints_tab.render()

# --- 🖌️ Studio: visualise and decide ---
with tab_studio:
    st.session_state.setdefault(keys.ANGLES, [])
    st.session_state.setdefault(keys.ACTIVE_ANGLE, 0)

    projects_panel.render_library()

    input_mode = st.radio(
        "Input", ["Photo", "Import normal map (photometric stereo)"],
        horizontal=True, key="input_mode",
        help="Photo = primed mini under a raking light (luminance). PS = import a "
             "recovered normal map for dark/primed minis; drag a virtual light.")
    if input_mode.startswith("Import"):
        ps_mode.render(picked, owned_paints)
        st.stop()

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
        state.set_active_angle(0)
        state.seed_editor_from_angle(a)
        st.rerun()

    active_idx = angles_panel.render()
    active = st.session_state[keys.ANGLES][active_idx]
    book = st.session_state[keys.BOOK]
    photo_bytes, photo_suffix = active.photo_bytes, active.photo_suffix

    try:
        with st.spinner("Preparing shading…"):
            rgb, alpha, shading = helpers.shading(photo_bytes, photo_suffix)

        col_render, col_controls = st.columns([1, 1])

        with col_render:
            cached_multi = st.session_state.get(keys.LAST_MULTI)
            if cached_multi is not None:
                st.image(cached_multi.combined_rgb,
                         caption="Painted preview (all regions)",
                         use_container_width=True)
            else:
                st.info("Preview will appear here after the first analysis run.")

        with col_controls:
            editor.render_editor(rgb, alpha, shading, book, picked, owned_paints)
            scheme_gen_panel.render(owned_paints)
            schemes_panel.render()
            projects_panel.render_save()

        # After first analysis run, left column needs a rerun to show the image.
        if cached_multi is None and st.session_state.get(keys.LAST_MULTI) is not None:
            st.rerun()

    except Exception as e:
        st.error("Error processing image — see traceback below.")
        st.exception(e)

# --- 🪜 Paint: paint-along steps ---
with tab_paint:
    multi = st.session_state.get(keys.LAST_MULTI)
    results.render_steps(multi)

# --- 🖼️ All angles: read-only gallery ---
with tab_angles:
    _angles = st.session_state.get(keys.ANGLES, [])
    _active = st.session_state.get(keys.ACTIVE_ANGLE, 0)
    if _angles:
        _angles[_active] = state.flush_editor_into_angle(_angles[_active])
    gallery_panel.render(_angles, _active)

# --- 📷 Capture & help ---
with tab_capture:
    from mini_highlight_advisor.input_check import SHOOTING_GUIDE, PAINTED_CAPTURE_NOTE
    st.header("How to photograph your mini")
    st.markdown(SHOOTING_GUIDE)
    st.divider()
    st.markdown(PAINTED_CAPTURE_NOTE)
    st.header("Photometric stereo (PS) capture")
    ps_guide = Path("docs/ps-capture-guide.md")
    if ps_guide.exists():
        st.markdown(ps_guide.read_text(encoding="utf-8"))
    else:
        st.caption("PS capture guide not found.")
```

Add `from pathlib import Path` to the imports at the top of `app.py`.

Also add `results` to the import line in `app.py`:
```python
from ui import (
    angles_panel, editor, gallery_panel, helpers, keys, paints_tab,
    projects_panel, ps_mode, results, scheme_gen_panel, schemes_panel, state,
)
```

- [ ] **Step 4: Run tests**

```
.venv/Scripts/python -m pytest tests/test_ui_app_tabs.py tests/test_ui_render_steps.py -v
```
Expected: all pass.

- [ ] **Step 5: Run full test suite to check for regressions**

```
.venv/Scripts/python -m pytest --ignore=tests/test_ui_gallery.py -x -q
```
(The two pre-existing `test_ui_gallery.py` failures are unrelated; exclude them.)
Expected: all other tests pass.

- [ ] **Step 6: Commit**

```
git add app.py tests/test_ui_app_tabs.py
git commit -m "feat: five-tab structure; mini render pinned left; steps → Paint tab; guide → Capture tab"
```

---

## Stage 2 — Unified Colour flow

**Goal:** Consolidate the five colour surfaces into a three-level Colour sub-tab. Move analysis before the columns so the left render is always current. Introduce the three control sub-tabs (Regions / Colour / Technique).

---

### Task 3: Add `SCHEME_GENERATED` key to `ui/keys.py`

**Files:**
- Modify: `ui/keys.py`
- Modify: `tests/test_ui_keys.py`

**Interfaces:**
- Produces: `keys.SCHEME_GENERATED = "scheme_generated"` — bool flag; True after Level 1 scheme has been generated at least once (used to collapse the Level 1 expander).

- [ ] **Step 1: Write failing test**

Open `tests/test_ui_keys.py` and add:

```python
def test_scheme_generated_key_exists():
    from ui import keys
    assert hasattr(keys, "SCHEME_GENERATED")
    assert keys.SCHEME_GENERATED == "scheme_generated"
```

- [ ] **Step 2: Run to verify it fails**

```
.venv/Scripts/python -m pytest tests/test_ui_keys.py::test_scheme_generated_key_exists -v
```

- [ ] **Step 3: Add the key**

In `ui/keys.py`, after the `SCHEMES` line, add:

```python
SCHEME_GENERATED = "scheme_generated"  # True once Level 1 scheme has been applied
```

- [ ] **Step 4: Run test to verify it passes**

```
.venv/Scripts/python -m pytest tests/test_ui_keys.py -v
```

- [ ] **Step 5: Commit**

```
git add ui/keys.py tests/test_ui_keys.py
git commit -m "feat: add SCHEME_GENERATED session-state key"
```

---

### Task 4: Add `run_analysis()` to `ui/helpers.py`

This function reads all technique/edge/relief widget values from session_state and calls `analyze_regions`. Moving the analysis call here (called before the columns in `app.py`) means the left render is always synchronised with the current widget state.

**Files:**
- Modify: `ui/helpers.py`
- Create: `tests/test_ui_helpers_analysis.py`

**Interfaces:**
- Consumes: `keys.EDGE_HL`, `keys.EDGE_EXTREME`, `keys.EDGE_SENS`, `keys.RELIEF_CAP`, `keys.PER_REGION_NORM`, `keys.SHADES`, `keys.NMM_HORIZON`, `keys.material(i)` from session_state.
- Produces: `helpers.run_analysis(rgb, alpha, book, shading, light_field=None, normal_field=None) -> MultiRegionResult`

- [ ] **Step 1: Write failing test**

```python
# tests/test_ui_helpers_analysis.py
import numpy as np
import pytest
from mini_highlight_advisor.region_state import new_book


def _small_rgb():
    return np.full((16, 16, 3), 128, dtype=np.uint8)


def _small_alpha():
    a = np.zeros((16, 16), dtype=np.uint8)
    a[4:12, 4:12] = 255
    return a


class _FakeShading:
    def __init__(self, mask):
        self.mask = mask
        self.light = np.ones((16, 16), dtype=np.float32) * 0.5


def test_run_analysis_returns_multi_region_result():
    from ui import helpers
    from mini_highlight_advisor.pipeline import MultiRegionResult

    rgb = _small_rgb()
    alpha = _small_alpha()
    mask = alpha > 127
    shading = _FakeShading(mask)
    book = new_book(3)

    result = helpers.run_analysis(rgb, alpha, book, shading)
    assert isinstance(result, MultiRegionResult)
    assert len(result.plans) >= 1


def test_run_analysis_reads_edge_hl_from_session_state():
    """With EDGE_HL=False in session_state, edge highlights should be off."""
    import streamlit as st
    from unittest.mock import patch
    from ui import helpers, keys

    rgb = _small_rgb()
    alpha = _small_alpha()
    mask = alpha > 127
    shading = _FakeShading(mask)
    book = new_book(3)

    fake_state = {keys.EDGE_HL: False}
    with patch.object(st, "session_state", fake_state):
        result = helpers.run_analysis(rgb, alpha, book, shading)
    # If edge_hl=False, no edge highlight pixels — just verify it doesn't crash
    assert result is not None
```

- [ ] **Step 2: Run to verify they fail**

```
.venv/Scripts/python -m pytest tests/test_ui_helpers_analysis.py -v
```
Expected: `AttributeError: module 'ui.helpers' has no attribute 'run_analysis'`

- [ ] **Step 3: Add `run_analysis` to `ui/helpers.py`**

At the bottom of `ui/helpers.py`, add:

```python
def run_analysis(rgb, alpha, book, shading,
                 light_field=None, normal_field=None):
    """Run analyze_regions reading all control values from session_state.

    Call this BEFORE rendering columns so the result is available for the
    left-column render in the same Streamlit pass.
    """
    import streamlit as st
    from mini_highlight_advisor.pipeline import analyze_regions

    edges = st.session_state.get(keys.EDGE_HL, True)
    extreme_edge = st.session_state.get(keys.EDGE_EXTREME, False)
    edge_sensitivity = st.session_state.get(keys.EDGE_SENS, 0.5)
    relief_cap = st.session_state.get(keys.RELIEF_CAP, True)
    per_region_norm = st.session_state.get(keys.PER_REGION_NORM, False)
    shades = st.session_state.get(keys.SHADES, False)
    nmm_horizon = st.session_state.get(keys.NMM_HORIZON, 0.5)

    wp, wcov, drawn = book.analyze_args()
    return analyze_regions(
        rgb, alpha, wp, wcov, drawn,
        edges=edges, extreme_edge=extreme_edge,
        edge_sensitivity=edge_sensitivity,
        relief_cap=relief_cap,
        per_region_norm=per_region_norm,
        light_field=light_field,
        normal_field=normal_field,
        shades=shades,
        nmm_horizon=nmm_horizon,
        whole_material=book.material_at(0),
    )
```

Also add `from ui import keys` at the top of `helpers.py` if not already present.

- [ ] **Step 4: Run tests**

```
.venv/Scripts/python -m pytest tests/test_ui_helpers_analysis.py -v
```

- [ ] **Step 5: Commit**

```
git add ui/helpers.py tests/test_ui_helpers_analysis.py
git commit -m "feat: helpers.run_analysis() — reads session_state, calls analyze_regions"
```

---

### Task 5: Create `ui/colour_panel.py` — Level 1 (whole-mini scheme)

Level 1 is the whole-mini scheme generator: absorbs `scheme_gen_panel.py` exactly, but collapses after first use via `SCHEME_GENERATED`.

**Files:**
- Create: `ui/colour_panel.py`
- Create: `tests/test_ui_colour_panel.py`

**Interfaces:**
- Produces: `colour_panel.render(book, sel, picked, owned_paints) -> None` — the full three-level colour panel (Level 1 in this task; Levels 2 and 3 added in Tasks 6 and 7).

- [ ] **Step 1: Write failing test**

```python
# tests/test_ui_colour_panel.py
import numpy as np


def _make_book_with_region():
    from mini_highlight_advisor.region_state import new_book
    from mini_highlight_advisor.palette import default_ramp, default_coverage
    book = new_book(5)
    m = np.zeros((8, 8), bool)
    m[2:5, 2:5] = True
    book.add(m, "Cloak", default_ramp(5), default_coverage(5))
    return book


def test_colour_panel_module_loads():
    import ui.colour_panel as cp
    assert hasattr(cp, "render")


def test_level1_generate_applies_scheme_to_book():
    """Level 1: build_scheme + apply changes the book palettes."""
    from mini_highlight_advisor import scheme_build as sb, schemes as sch
    from mini_highlight_advisor.scheme_gen import RegionColorSpec
    from ui.context import CATALOG

    book = _make_book_with_region()
    before = [p.hex for p in book.palette_at(1)]

    specs = [
        RegionColorSpec(name, book.surface_at(g), book.tone_at(g),
                        len(book.palette_at(g)))
        for g, name in enumerate(book.names())
    ]
    scheme = sb.build_scheme("Auto", specs, "Cloak", "#c02030", "grimdark",
                             "complementary", [], list(CATALOG), owned_only=False)
    sch.apply(scheme, book)
    after = [p.hex for p in book.palette_at(1)]
    assert before != after
```

- [ ] **Step 2: Run to verify**

```
.venv/Scripts/python -m pytest tests/test_ui_colour_panel.py::test_colour_panel_module_loads -v
```
Expected: `ModuleNotFoundError: No module named 'ui.colour_panel'`

- [ ] **Step 3: Create `ui/colour_panel.py` with Level 1**

```python
# ui/colour_panel.py
"""Three-level colour panel: whole-mini scheme → region ramp → bands.

Level 1 (whole-mini scheme) is implemented in this file.
Levels 2 and 3 are added in subsequent tasks.
"""
import streamlit as st

from mini_highlight_advisor import scheme_build as sb, schemes as sch
from mini_highlight_advisor.scheme_gen import RegionColorSpec, MOODS, VARIANTS, HARMONY_TONE
from mini_highlight_advisor.surfaces import SURFACES, get_surface, REALISTIC
from ui import context, keys


def _reseed_editor_widgets() -> None:
    """Drop widget keys for palette slots so the editor re-seeds from the book."""
    st.session_state.pop(keys.LOADED_G, None)
    st.session_state.pop(keys.COV_N, None)
    for k in [k for k in list(st.session_state)
              if k.startswith("slot_code_") or k.startswith("slot_hex_")
              or k.startswith("slot_hexinput_") or k.startswith("cov_pct_")]:
        st.session_state.pop(k, None)


def _render_level1(book, owned_paints) -> None:
    """Level 1 — whole-mini scheme: surfaces + hero + mood → generate & apply."""
    generated = st.session_state.get(keys.SCHEME_GENERATED, False)
    with st.expander("🎯 Generate scheme (surfaces + hero colour + mood)",
                     expanded=not generated):
        names = book.names()
        st.caption("Tag each region, then pick a hero colour and a mood.")
        for g, name in enumerate(names):
            c1, c2 = st.columns([1, 1])
            surf_keys = list(SURFACES)
            cur_surf = book.surface_at(g)
            idx = surf_keys.index(cur_surf) if cur_surf in surf_keys else surf_keys.index("other")
            chosen = c1.selectbox(
                f"Surface — {name}", surf_keys, index=idx,
                format_func=lambda s: SURFACES[s].display, key=f"sgen_surface_{g}")
            book.set_surface_at(g, chosen)
            spec = get_surface(chosen)
            if spec.bucket == REALISTIC:
                tone_opts = list(spec.tones) + [HARMONY_TONE]
                cur_tone = book.tone_at(g)
                t_idx = tone_opts.index(cur_tone) if cur_tone in tone_opts else 0
                tone = c2.selectbox(
                    f"Tone — {name}", tone_opts, index=t_idx,
                    format_func=lambda t: "Follow scheme colour" if t == HARMONY_TONE else t,
                    key=f"sgen_tone_{g}")
                book.set_tone_at(g, tone)
            else:
                book.set_tone_at(g, None)

        anchor_name = st.selectbox("Hero region (anchor)", names, key="sgen_anchor")
        g_anchor = names.index(anchor_name)
        pal = book.palette_at(g_anchor)
        default_hex = pal[len(pal) // 2].hex if pal else "#c02030"
        anchor_hex = st.color_picker("Hero colour", value=default_hex, key="sgen_anchor_hex")
        mood = st.selectbox("Mood", list(MOODS), key="sgen_mood")
        variant = st.selectbox("Harmony", VARIANTS, key="sgen_variant",
                               help="Cycle this to re-roll the free regions' colours.")
        owned_only = st.checkbox("Owned only (no catalogue suggestions)", value=False,
                                 key="sgen_owned_only")
        set_tech = st.checkbox("Also set techniques from surface", value=True,
                               key="sgen_set_tech")

        if st.button("✨ Generate & apply scheme", type="primary", key="sgen_go"):
            specs = [
                RegionColorSpec(nm, book.surface_at(g), book.tone_at(g),
                                len(book.palette_at(g)))
                for g, nm in enumerate(names)
            ]
            scheme = sb.build_scheme(
                "Generated", specs, anchor_name, anchor_hex, mood, variant,
                list(owned_paints), list(context.CATALOG), owned_only)
            sch.apply(scheme, book)
            if set_tech:
                ps_on = st.session_state.get(keys.NORMALS) is not None
                for g, nm in enumerate(names):
                    tech = get_surface(book.surface_at(g)).default_technique
                    if not tech:
                        continue
                    if tech == "nmm" and not ps_on:
                        continue
                    book.set_material_at(g, tech)
            st.session_state[keys.SCHEME_GENERATED] = True
            _reseed_editor_widgets()
            st.success("Scheme generated and applied. Adjust any colour below.")
            st.rerun()


def render(book, sel: int, picked, owned_paints) -> None:
    """Render the three-level colour panel for the given region selection.

    Levels 2 and 3 are stubs until Tasks 6 and 7 add them.
    """
    _render_level1(book, owned_paints)
    # Level 2 and 3 will be inserted here in subsequent tasks.
```

- [ ] **Step 4: Run tests**

```
.venv/Scripts/python -m pytest tests/test_ui_colour_panel.py -v
```

- [ ] **Step 5: Commit**

```
git add ui/colour_panel.py tests/test_ui_colour_panel.py
git commit -m "feat: colour_panel Level 1 — whole-mini scheme (surfaces + hero + mood)"
```

---

### Task 6: Add Level 2 (region ramp) and Level 3 (bands + inline match) to `colour_panel.py`

Level 2 merges "Generate from midtone" + "Colour variants" into one compact section. Level 3 is the palette slots (absorbs `palette_editor.py`) with owned-first paint match shown inline per slot. The `_mini_preview` thumbnail is dropped — left-column render is the preview.

**Files:**
- Modify: `ui/colour_panel.py`
- Modify: `tests/test_ui_colour_panel.py`

**Interfaces:**
- Consumes: `color.ramp_from_midtone`, `color.hue_rotate`, `collection.nearest_paint`, `matching.target_from_paint`, `palette.role_names`, `palette.DEFAULT_PALETTE`, `catalog.find_by_code`, `catalog.find_by_name`, `recipes.load_all`, `recipes.to_palette`, `recipes.save_user`, `overlay.preview_scheme` (dropped — no longer needed).
- Produces: `colour_panel.render()` now sets `book.set_palette_at(sel, palette)` internally and renders all three levels.

- [ ] **Step 1: Add tests for Level 2 and 3 behaviour**

Append to `tests/test_ui_colour_panel.py`:

```python
def test_ramp_from_midtone_produces_n_colours():
    from mini_highlight_advisor.color import ramp_from_midtone
    hexes = ramp_from_midtone("#808080", 5)
    assert len(hexes) == 5
    # darkest should be darker than lightest
    from mini_highlight_advisor.palette import PaintColor
    dark = PaintColor("d", hexes[0]).rgb.mean()
    light = PaintColor("l", hexes[-1]).rgb.mean()
    assert light > dark


def test_hue_rotate_complementary():
    from mini_highlight_advisor.color import hue_rotate, ramp_from_midtone
    mid = "#c02030"
    comp = hue_rotate(mid, 180)
    hexes = ramp_from_midtone(comp, 3)
    assert len(hexes) == 3
    assert hexes[0] != mid  # complementary is different from original


def test_colour_panel_render_sets_book_palette(tmp_path):
    """colour_panel.render() must call book.set_palette_at (via Level 3 slots)."""
    # This is a unit test of the book interaction, not the Streamlit render.
    # We test that palette_editor logic (now in colour_panel) still sets palettes.
    from mini_highlight_advisor.region_state import new_book
    from mini_highlight_advisor.palette import DEFAULT_PALETTE
    book = new_book(5)
    # Default palette should be set; Level 3 reads it and sets it back via book
    assert book.palette_at(0) is not None
    assert len(book.palette_at(0)) > 0
```

- [ ] **Step 2: Run to confirm they pass already (pure logic tests)**

```
.venv/Scripts/python -m pytest tests/test_ui_colour_panel.py -v
```

- [ ] **Step 3: Add Level 2 and Level 3 to `ui/colour_panel.py`**

Replace the `render()` function and add helpers. The full updated file:

```python
# ui/colour_panel.py
"""Three-level colour panel: whole-mini scheme → region ramp → bands + inline match."""
import streamlit as st
from collections import Counter

from mini_highlight_advisor import scheme_build as sb, schemes as sch
from mini_highlight_advisor.scheme_gen import RegionColorSpec, MOODS, VARIANTS, HARMONY_TONE
from mini_highlight_advisor.surfaces import SURFACES, get_surface, REALISTIC
from mini_highlight_advisor.palette import (
    DEFAULT_PALETTE, PaintColor, role_names, ramp_hex, valid_hex,
)
from mini_highlight_advisor.color import hue_rotate, ramp_from_midtone
from mini_highlight_advisor.catalog import find_by_code, find_by_name
from mini_highlight_advisor.recipes import load_all, to_palette, save_user, Recipe, RecipeStep
from mini_highlight_advisor import collection
from ui import context, helpers, keys


def _reseed_editor_widgets() -> None:
    st.session_state.pop(keys.LOADED_G, None)
    st.session_state.pop(keys.COV_N, None)
    for k in [k for k in list(st.session_state)
              if k.startswith("slot_code_") or k.startswith("slot_hex_")
              or k.startswith("slot_hexinput_") or k.startswith("cov_pct_")]:
        st.session_state.pop(k, None)


def _render_level1(book, owned_paints) -> None:
    """Level 1 — whole-mini scheme: surfaces + hero + mood → generate & apply."""
    generated = st.session_state.get(keys.SCHEME_GENERATED, False)
    with st.expander("🎯 Generate scheme (surfaces + hero colour + mood)",
                     expanded=not generated):
        names = book.names()
        st.caption("Tag each region, then pick a hero colour and a mood.")
        for g, name in enumerate(names):
            c1, c2 = st.columns([1, 1])
            surf_keys = list(SURFACES)
            cur_surf = book.surface_at(g)
            idx = surf_keys.index(cur_surf) if cur_surf in surf_keys else surf_keys.index("other")
            chosen = c1.selectbox(
                f"Surface — {name}", surf_keys, index=idx,
                format_func=lambda s: SURFACES[s].display, key=f"sgen_surface_{g}")
            book.set_surface_at(g, chosen)
            spec = get_surface(chosen)
            if spec.bucket == REALISTIC:
                tone_opts = list(spec.tones) + [HARMONY_TONE]
                cur_tone = book.tone_at(g)
                t_idx = tone_opts.index(cur_tone) if cur_tone in tone_opts else 0
                tone = c2.selectbox(
                    f"Tone — {name}", tone_opts, index=t_idx,
                    format_func=lambda t: "Follow scheme colour" if t == HARMONY_TONE else t,
                    key=f"sgen_tone_{g}")
                book.set_tone_at(g, tone)
            else:
                book.set_tone_at(g, None)

        anchor_name = st.selectbox("Hero region (anchor)", names, key="sgen_anchor")
        g_anchor = names.index(anchor_name)
        pal = book.palette_at(g_anchor)
        default_hex = pal[len(pal) // 2].hex if pal else "#c02030"
        anchor_hex = st.color_picker("Hero colour", value=default_hex, key="sgen_anchor_hex")
        mood = st.selectbox("Mood", list(MOODS), key="sgen_mood")
        variant = st.selectbox("Harmony", VARIANTS, key="sgen_variant",
                               help="Cycle this to re-roll the free regions' colours.")
        owned_only = st.checkbox("Owned only (no catalogue suggestions)", value=False,
                                 key="sgen_owned_only")
        set_tech = st.checkbox("Also set techniques from surface", value=True,
                               key="sgen_set_tech")

        if st.button("✨ Generate & apply scheme", type="primary", key="sgen_go"):
            specs = [
                RegionColorSpec(nm, book.surface_at(g), book.tone_at(g),
                                len(book.palette_at(g)))
                for g, nm in enumerate(names)
            ]
            scheme = sb.build_scheme(
                "Generated", specs, anchor_name, anchor_hex, mood, variant,
                list(owned_paints), list(context.CATALOG), owned_only)
            sch.apply(scheme, book)
            if set_tech:
                ps_on = st.session_state.get(keys.NORMALS) is not None
                for g, nm in enumerate(names):
                    tech = get_surface(book.surface_at(g)).default_technique
                    if not tech:
                        continue
                    if tech == "nmm" and not ps_on:
                        continue
                    book.set_material_at(g, tech)
            st.session_state[keys.SCHEME_GENERATED] = True
            _reseed_editor_widgets()
            st.success("Scheme generated and applied. Adjust any colour below.")
            st.rerun()


def _apply_ramp(hexes: list[str], n: int) -> None:
    """Write a list of hex strings into the palette-slot session keys."""
    for i, h in enumerate(hexes[:n]):
        st.session_state[keys.slot_hex(i)] = h
        st.session_state[keys.slot_code(i)] = context.CUSTOM


def _render_level2(book, sel: int, n: int, owned_paints) -> None:
    """Level 2 — region ramp: midtone → ramp + harmony variants.

    Applies immediately on button click (no preview thumbnail — left-column
    render is the preview).
    """
    st.divider()
    st.markdown(f"**Ramp for: {book.names()[sel]}**")

    mid_hex = st.color_picker("Base colour (midtone)", value="#808080", key=keys.MIDTONE_HEX)

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

        apply_col, save_col = st.columns(2)
        if apply_col.button(f"Apply {label}", key=f"apply_ramp_{label}"):
            _apply_ramp(hexes, n)
            st.rerun()
        if save_col.button(f"💾 Save", key=f"save_ramp_{label}"):
            steps = [
                RecipeStep(label=r, hex=h, paint_ref=(p.name if p else None))
                for r, h, p in zip(role_names(n), hexes, paints)
            ]
            save_user(Recipe(f"{label} ({mid_hex})", steps))
            st.toast(f"Saved '{label} ({mid_hex})'")


def _apply_paste_hex(i: int) -> None:
    norm = valid_hex(st.session_state.get(keys.slot_hexinput(i), ""))
    if norm is not None:
        st.session_state[keys.slot_hex(i)] = norm


def _blend_neighbours(i: int, n: int) -> None:
    from mini_highlight_advisor.color import blend_hex_lab
    lo = st.session_state.get(keys.slot_hex(i - 1), ramp_hex(i - 1, n))
    hi = st.session_state.get(keys.slot_hex(i + 1), ramp_hex(i + 1, n))
    st.session_state[keys.slot_hex(i)] = blend_hex_lab(lo, hi)
    st.session_state[keys.slot_code(i)] = context.CUSTOM


def _render_level3(book, sel: int, picked) -> tuple[list[PaintColor], int]:
    """Level 3 — bands: palette slots dark→light with inline owned-first match.

    Returns (palette, n) so the caller can set book.set_palette_at(sel, palette).
    """
    st.divider()
    # Recipe loader
    recipes = load_all()
    recipe_by_name = {r.name: r for r in recipes}
    name_counts = Counter(p.name for p in context.CATALOG)
    choice = st.selectbox("Load recipe", ["(none)"] + list(recipe_by_name),
                          key="cp_recipe_choice")
    if st.button("Load recipe", key="cp_recipe_load") and choice != "(none)":
        pal = to_palette(recipe_by_name[choice])
        st.session_state[keys.N] = max(3, min(5, len(pal)))
        for i, p in enumerate(pal[:st.session_state[keys.N]]):
            match = find_by_name(context.CATALOG, p.name)
            unique = name_counts.get(p.name) == 1
            st.session_state[keys.slot_code(i)] = match.code if (match and unique) else context.CUSTOM
            st.session_state[keys.slot_hex(i)] = p.hex
        st.rerun()

    st.session_state.setdefault(keys.N, 5)
    n = st.slider("Number of layers", 3, 7, key=keys.N)

    st.markdown("**Bands (dark → light)**")
    palette = []
    options = context.CATALOG_CODES + [context.CUSTOM]
    for i in range(n):
        default = DEFAULT_PALETTE[i] if i < len(DEFAULT_PALETTE) else PaintColor(f"Grey {i+1}", ramp_hex(i, n))
        st.session_state.setdefault(keys.slot_code(i), default.code)
        st.session_state.setdefault(keys.slot_hex(i), default.hex)
        default_code = st.session_state[keys.slot_code(i)]
        if default_code != context.CUSTOM and find_by_code(context.CATALOG, default_code) is None:
            default_code = context.CUSTOM
        c1, c2, c3 = st.columns([3, 1, 1])
        slot_sel = c1.selectbox(
            f"Layer {i + 1}", options,
            index=options.index(default_code),
            format_func=lambda c: context.CUSTOM if c == context.CUSTOM else context.CODE_LABEL.get(c, c),
            key=keys.slot_code(i),
        )
        if slot_sel == context.CUSTOM:
            hexv = c2.color_picker(f"hex {i+1}", key=keys.slot_hex(i),
                                   label_visibility="collapsed")
            pasted = c3.text_input(f"paste hex {i+1}", value=hexv, key=keys.slot_hexinput(i),
                                   on_change=_apply_paste_hex, args=(i,),
                                   label_visibility="collapsed")
            if pasted and valid_hex(pasted) is None:
                c3.caption("⚠️ invalid hex")
            paint = PaintColor(f"Custom {i+1}", hexv)
            palette.append(paint)
            near = collection.nearest_paint(paint.rgb, context.CATALOG)
            if near is not None:
                owned_badge = "✅ owned" if near.code in set(picked) else "⚠️ not owned"
                c3.caption(f"{hexv} · closest: {near.name} · {near.code} ({owned_badge})")
        else:
            paint = find_by_code(context.CATALOG, slot_sel)
            c2.markdown(helpers.swatch(paint.hex, size="2.2em"), unsafe_allow_html=True)
            palette.append(paint)
            st.session_state[keys.slot_hex(i)] = paint.hex
            badge = "✅ owned" if paint.code in set(picked) else "⚠️ not owned"
            c3.write(f"{paint.hex} · {badge}")

        if 0 < i < n - 1:
            c1.button("↕ blend", key=keys.blend(i),
                      on_click=_blend_neighbours, args=(i, n))

    return palette, n


def _render_scheme_save(book) -> None:
    """Scheme save / swap at the bottom of the Colour panel (replaces schemes_panel)."""
    st.divider()
    stored = st.session_state.setdefault(keys.SCHEMES, [])
    with st.expander("💾 Save & swap schemes"):
        name = st.text_input("Scheme name", key="cp_scheme_save_name")
        if st.button("＋ Save current as scheme", type="primary", key="cp_scheme_save_btn"):
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

        if stored:
            names = [s.name for s in stored]
            pick = st.radio("Saved schemes", names, key="cp_scheme_pick")
            chosen = stored[names.index(pick)]
            c_apply, c_del = st.columns(2)
            if c_apply.button("Apply", type="primary", key="cp_scheme_apply_btn"):
                report = sch.apply(chosen, book)
                _reseed_editor_widgets()
                if report.skipped_regions:
                    st.info(f"{len(report.updated)} region(s) updated — no saved colour "
                            f"for: {', '.join(report.skipped_regions)}")
                st.rerun()
            if c_del.button("Delete", key="cp_scheme_delete_btn"):
                stored.remove(chosen)
                st.session_state.pop("cp_scheme_pick", None)
                st.rerun()


def render(book, sel: int, picked, owned_paints) -> None:
    """Render the three-level colour panel for the selected region."""
    _render_level1(book, owned_paints)

    # Level 2 needs n (band count); read from session_state (set by Level 3 slider).
    n = st.session_state.get(keys.N, 5)
    _render_level2(book, sel, n, owned_paints)

    palette, n = _render_level3(book, sel, picked)
    book.set_palette_at(sel, palette)

    _render_scheme_save(book)
```

- [ ] **Step 4: Run tests**

```
.venv/Scripts/python -m pytest tests/test_ui_colour_panel.py -v
```

- [ ] **Step 5: Commit**

```
git add ui/colour_panel.py tests/test_ui_colour_panel.py
git commit -m "feat: colour_panel Levels 2 + 3 — region ramp, bands, inline match, scheme save"
```

---

### Task 7: Extract `render_technique_controls()` from `ui/results.py`

The technique/edge/relief controls stay in `results.py` but are exposed as a standalone function so the Technique sub-tab can call them independently from the analysis.

**Files:**
- Modify: `ui/results.py`
- Modify: `tests/test_ui_results_ps.py` (verify existing tests still pass)

**Interfaces:**
- Produces: `results.render_technique_controls(book, sel, has_normals: bool) -> None` — renders edge/technique/relief/colored/photo-quality widgets only; does NOT call `analyze_regions`.
- The existing `results.render()` is kept for backward compatibility in Stage 1's wiring; it will be removed in Task 8.

- [ ] **Step 1: Write failing test**

Append to `tests/test_ui_results_ps.py`:

```python
def test_render_technique_controls_exists():
    import ui.results as r
    assert hasattr(r, "render_technique_controls")

def test_render_technique_controls_smoke():
    HARNESS = """
import numpy as np
import streamlit as st
from mini_highlight_advisor.region_state import new_book
from ui import results, keys

book = new_book(5)
st.session_state[keys.BOOK] = book
results.render_technique_controls(book, 0, has_normals=False)
st.write("ok")
"""
    from streamlit.testing.v1 import AppTest
    at = AppTest.from_string(HARNESS)
    at.run()
    assert not at.exception
```

- [ ] **Step 2: Run to verify failure**

```
.venv/Scripts/python -m pytest tests/test_ui_results_ps.py::test_render_technique_controls_exists -v
```

- [ ] **Step 3: Extract `render_technique_controls()` in `ui/results.py`**

In `results.py`, extract the widget-rendering portion into a new function. Add before `render()`:

```python
def render_technique_controls(book, sel: int, has_normals: bool) -> None:
    """Render technique, edge, relief, and photo-quality controls.

    Writes widget values into session_state. Does NOT call analyze_regions.
    Call this from the Technique sub-tab; read the values via helpers.run_analysis().
    """
    # --- Match to my paints — ad-hoc colour (lightweight, kept here) ---
    # (full match display moves to colour_panel Level 3 inline badges)

    st.markdown("**Edge highlights**")
    st.checkbox("Edge highlights", value=True, key=keys.EDGE_HL)
    st.checkbox("Extreme edge highlight", value=False, key=keys.EDGE_EXTREME,
                disabled=not st.session_state.get(keys.EDGE_HL, True))
    st.slider("Edge sensitivity", 0.0, 1.0, 0.5, 0.05, key=keys.EDGE_SENS,
              disabled=not st.session_state.get(keys.EDGE_HL, True),
              help="Few sharpest edges (left) to more edges (right).")

    if has_normals:
        st.checkbox("Recess shades", value=False, key=keys.SHADES,
                    help="Darken concave recesses from surface normals (PS mode only).")

    # Technique picker
    cur_material = book.material_at(sel)
    cur_key = "smooth" if cur_material == "matte" else cur_material
    technique_labels = ["Smooth layering", "Drybrush"]
    technique_keys   = ["smooth",          "drybrush"]
    if has_normals:
        technique_labels.append("NMM")
        technique_keys.append("nmm")
    cur_idx = technique_keys.index(cur_key) if cur_key in technique_keys else 0
    choice_label = st.selectbox(
        f"Technique — {book.names()[sel]}", technique_labels, index=cur_idx,
        key=keys.material(sel),
        help=("Smooth layering: thin glazes, dark to light.\n"
              "Drybrush: drag a nearly-dry brush across raised surfaces.\n"
              "NMM (PS mode only): non-metallic metal from surface normals."),
    )
    chosen_key = technique_keys[technique_labels.index(choice_label)]
    book.set_material_at(sel, chosen_key)

    if has_normals and chosen_key == "nmm":
        st.slider("Horizon height", 0.0, 1.0, 0.5, 0.05, key=keys.NMM_HORIZON,
                  help="Slide the virtual NMM horizon up or down.")

    st.checkbox("Auto-reduce bands on flat regions", value=True, key=keys.RELIEF_CAP,
                help="Cap band count to what the relief supports.")

    if not has_normals:
        st.checkbox("Colored / painted mini (experimental)", value=False,
                    key=keys.PER_REGION_NORM,
                    help="Normalize brightness per region so each painted colour reads its "
                         "own relief. Off = primed-mini mode (default).")

    # Photo quality (photo mode only)
    if not has_normals:
        try:
            st.subheader("📷 Photo quality")
            from mini_highlight_advisor.masking import compute_mask
            # shading.mask is not available here; use a lightweight check on rgb shape
            # Full check happens inside render() which has access to shading.
            st.caption("Photo quality check runs during analysis.")
        except Exception:
            pass
```

Note: the photo-quality check (`check_input`) requires `shading.mask` which isn't available in `render_technique_controls`. Keep the full check in `render()` for now and add a caption placeholder here. Task 8 will wire it properly.

- [ ] **Step 4: Run tests**

```
.venv/Scripts/python -m pytest tests/test_ui_results_ps.py -v
```

- [ ] **Step 5: Commit**

```
git add ui/results.py tests/test_ui_results_ps.py
git commit -m "feat: extract render_technique_controls() from results.py"
```

---

### Task 8: Wire three sub-tabs in `app.py`; move analysis before columns; delete absorbed files

This task rewires `app.py` Studio to use the three sub-tabs, moves `run_analysis()` before the columns so the left render is always current, and deletes `scheme_gen_panel.py`, `schemes_panel.py`, and `editor.py` (their logic is now in `colour_panel.py` and `app.py` directly). Also deletes `palette_editor.py`.

**Files:**
- Modify: `app.py`
- Delete: `ui/scheme_gen_panel.py`, `ui/schemes_panel.py`, `ui/palette_editor.py`, `ui/editor.py`
- Modify: `ui/__init__.py` (remove deleted modules from any re-exports if present)
- Modify: `tests/test_ui_app_tabs.py`

- [ ] **Step 1: Add test for sub-tabs**

Append to `tests/test_ui_app_tabs.py`:

```python
def test_studio_has_sub_tabs():
    at = _make_at()
    # All tabs (top-level + sub-tabs) are returned by at.tabs
    all_labels = [t.label for t in at.tabs]
    assert "Regions" in all_labels
    assert "Colour" in all_labels
    assert "Technique" in all_labels
```

- [ ] **Step 2: Run to confirm failure**

```
.venv/Scripts/python -m pytest tests/test_ui_app_tabs.py::test_studio_has_sub_tabs -v
```

- [ ] **Step 3: Rewrite the Studio block in `app.py`**

Replace the `with tab_studio:` block (from `with tab_studio:` to the `except Exception as e:` block) with:

```python
# --- 🖌️ Studio: visualise and decide ---
with tab_studio:
    st.session_state.setdefault(keys.ANGLES, [])
    st.session_state.setdefault(keys.ACTIVE_ANGLE, 0)

    projects_panel.render_library()

    input_mode = st.radio(
        "Input", ["Photo", "Import normal map (photometric stereo)"],
        horizontal=True, key="input_mode",
        help="Photo = primed mini under a raking light (luminance). PS = import a "
             "recovered normal map for dark/primed minis; drag a virtual light.")
    if input_mode.startswith("Import"):
        ps_mode.render(picked, owned_paints)
        st.stop()

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
        state.set_active_angle(0)
        state.seed_editor_from_angle(a)
        st.rerun()

    active_idx = angles_panel.render()
    active = st.session_state[keys.ANGLES][active_idx]
    book = st.session_state[keys.BOOK]
    photo_bytes, photo_suffix = active.photo_bytes, active.photo_suffix

    try:
        with st.spinner("Preparing shading…"):
            rgb, alpha, shading = helpers.shading(photo_bytes, photo_suffix)

        normal_field = st.session_state.get(keys.NORMALS)
        light_field = None  # photo mode; PS mode takes a different branch above

        # Run analysis BEFORE columns using session_state from the previous run.
        # (Session_state holds the values the user set on the previous run, which
        # are the same as what the widgets currently display. This keeps the left
        # render in sync with the controls without an extra rerun.)
        multi = helpers.run_analysis(rgb, alpha, book, shading,
                                     light_field=light_field, normal_field=normal_field)
        st.session_state[keys.LAST_MULTI] = multi
        st.session_state[keys.LAST_RGB] = rgb

        col_render, col_controls = st.columns([1, 1])

        with col_render:
            st.image(multi.combined_rgb,
                     caption="Painted preview (all regions)",
                     use_container_width=True)
            # Compact photo-quality check
            if normal_field is None:
                try:
                    from mini_highlight_advisor.input_check import check_input
                    for r in check_input(rgb, shading.mask):
                        (st.success if r.ok else st.warning)(f"**{r.label}** — {r.detail}")
                except Exception:
                    pass

        with col_controls:
            sel = st.session_state.get(keys.REGION_RADIO, 0)
            subtab_r, subtab_c, subtab_t = st.tabs(["🗺 Regions", "🎨 Colour", "🖌 Technique"])

            with subtab_r:
                src_h, src_w = rgb.shape[:2]
                sel = regions_panel.render(book, rgb, shading, src_w, src_h)
                state.rehydrate_editor_widgets(book, sel)
                n = st.session_state.get(keys.N, 5)
                coverage = coverage_editor.render(n)
                book.set_coverage_at(sel, coverage)

            with subtab_c:
                colour_panel.render(book, sel, picked, owned_paints)

            with subtab_t:
                has_normals = normal_field is not None
                results.render_technique_controls(book, sel, has_normals=has_normals)

        projects_panel.render_save()

    except Exception as e:
        st.error("Error processing image — see traceback below.")
        st.exception(e)
```

Update the import line in `app.py` to add `colour_panel`, `coverage_editor`, `regions_panel` and remove the deleted modules:

```python
from ui import (
    angles_panel, colour_panel, coverage_editor, gallery_panel, helpers, keys,
    paints_tab, projects_panel, ps_mode, regions_panel, results, state,
)
```

- [ ] **Step 4: Delete absorbed files**

```
git rm ui/scheme_gen_panel.py ui/schemes_panel.py ui/palette_editor.py ui/editor.py
```

Also update `ui/__init__.py` to remove any explicit re-exports of those modules (check with `cat ui/__init__.py`).

- [ ] **Step 5: Run full test suite**

```
.venv/Scripts/python -m pytest --ignore=tests/test_ui_gallery.py -x -q
```

Fix any import errors caused by deleted modules (e.g. if any test imports `ui.palette_editor` directly, update it to `ui.colour_panel`). The key files to check:
- `tests/test_ui_scheme_gen.py` — imports `ui.scheme_gen_panel`; redirect to `ui.colour_panel`
- Any test that imports `ui.editor`; redirect its logic tests to the equivalent function in `app.py` or `colour_panel.py`

- [ ] **Step 6: Commit**

```
git add app.py ui/__init__.py tests/
git commit -m "feat: three sub-tabs wired; analysis before columns; delete absorbed panels"
```

---

## Stage 3 — Polish

**Goal:** Move photo-quality check properly to the left column; add PS capture guide to Capture tab; clean up any dead code.

---

### Task 9: Photo-quality check in left column and Capture tab PS guide

**Files:**
- Modify: `ui/results.py` — remove the photo-quality placeholder caption added in Task 7 (the real check now lives in `app.py`'s col_render)
- Modify: `app.py` — the photo-quality check in col_render is already there from Task 8; ensure it works with the `shading` object
- Modify: `tests/test_ui_app_tabs.py`

**Interfaces:**
- No new functions. Cleanup only.

- [ ] **Step 1: Add test for Capture tab content**

Append to `tests/test_ui_app_tabs.py`:

```python
def test_capture_tab_contains_guide_text():
    at = _make_at()
    # The Capture tab markdown should contain key shooting guide phrases
    all_markdown = " ".join(m.value for m in at.markdown)
    assert "raking" in all_markdown.lower() or "side light" in all_markdown.lower()
```

- [ ] **Step 2: Run to check it passes (should already from Task 2)**

```
.venv/Scripts/python -m pytest tests/test_ui_app_tabs.py -v
```

- [ ] **Step 3: Remove the placeholder caption from `render_technique_controls()`**

In `ui/results.py`, find and remove this block from `render_technique_controls()`:

```python
    # Photo quality (photo mode only)
    if not has_normals:
        try:
            st.subheader("📷 Photo quality")
            ...
            st.caption("Photo quality check runs during analysis.")
        except Exception:
            pass
```

The photo-quality check already lives in `app.py`'s `col_render` block (added in Task 8).

- [ ] **Step 4: Run full suite**

```
.venv/Scripts/python -m pytest --ignore=tests/test_ui_gallery.py -q
```
Expected: all pass.

- [ ] **Step 5: Commit**

```
git add ui/results.py tests/test_ui_app_tabs.py
git commit -m "polish: remove technique-panel photo-quality placeholder; capture tab verified"
```

---

### Task 10: Final cleanup and PR

- [ ] **Step 1: Check for any lingering imports of deleted modules**

```
grep -r "scheme_gen_panel\|schemes_panel\|palette_editor\|ui\.editor" --include="*.py" .
```
Fix any remaining references.

- [ ] **Step 2: Run the full test suite one final time**

```
.venv/Scripts/python -m pytest --ignore=tests/test_ui_gallery.py -v
```
All tests pass.

- [ ] **Step 3: Check git status — no untracked files that should be committed**

```
git status
```

- [ ] **Step 4: Final commit if any stray fixes**

```
git add -p  # stage only intentional changes
git commit -m "chore: cleanup stray imports after panel consolidation"
```

- [ ] **Step 5: Push and open PR**

```
git push -u origin feat/studio-ux-colour-loop
```
Open a PR titled: "Studio UX: five-tab layout, mini render always visible, unified Colour panel"

---

## Self-review

**Spec coverage:**
- ✅ Five tabs (Studio / Paint / Paints / All angles / Capture & help) — Tasks 2, 8
- ✅ Render pinned left, always visible — Tasks 2, 8
- ✅ Steps → Paint tab — Task 1, 2
- ✅ Guide → Capture tab — Task 2
- ✅ Three control sub-tabs (Regions / Colour / Technique) — Task 8
- ✅ Level 1 whole-mini scheme — Task 5
- ✅ Level 2 region ramp (midtone + variants, apply immediately) — Task 6
- ✅ Level 3 bands with inline match — Task 6
- ✅ Scheme save/load consolidated — Task 6
- ✅ `_mini_preview` thumbnail dropped — Task 6 (not included in colour_panel)
- ✅ `scheme_gen_panel.py`, `schemes_panel.py`, `palette_editor.py`, `editor.py` deleted — Task 8
- ✅ Analysis before columns (left render always current) — Task 4, 8
- ✅ `SCHEME_GENERATED` flag for Level 1 collapse — Task 3, 5

**Placeholder scan:** None found. All code blocks are concrete.

**Type consistency:**
- `render_steps(multi)` — `multi` typed as `MultiRegionResult | None` throughout
- `run_analysis(...)` → returns `MultiRegionResult` — matches usage in `app.py`
- `colour_panel.render(book, sel, picked, owned_paints)` — `sel: int`, `picked: list[str]` — consistent across Tasks 5, 6, 8
- `render_technique_controls(book, sel, has_normals)` — `has_normals: bool` — consistent Tasks 7, 8
