# OSL Glow-Layer Reshape Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Turn OSL from a below-the-editor panel into a toggleable "Glow" tab whose glow shows in the main preview, whose placement canvas shows the mini, and whose paint steps teach the glazing technique.

**Architecture:** UI-layer reshape only. The glow math (`osl.py`, `pipeline.apply_osl`) is untouched. A new pure helper `pipeline.osl_step_caption` and a Streamlit-free `ui/helpers.build_osl_result` wrap the existing `apply_osl`. `ui/editor.py` reads OSL params from `session_state` *before* it draws the main preview (the same pre-read pattern the visibility toggles already use), composites the glow, and renders a 4th "Glow" tab (PS-mode only). `ui/ps_mode.py` loses its post-editor OSL block; the glow steps move to the Paint tab in `app.py`.

**Tech Stack:** Python 3.11, numpy, streamlit, streamlit-drawable-canvas, Pillow, pytest. Env: `.venv/Scripts/python`.

**Spec:** `docs/superpowers/specs/2026-09-04-osl-glow-layer-reshape-design.md`

## Global Constraints

- **PS mode only.** The Glow tab and all OSL compositing must be gated on `normal_field is not None` (photo mode shows exactly the original 3 tabs). Copied verbatim from spec: "the Glow tab is PS-mode only."
- **Glow math is byte-identical.** Do NOT edit `src/mini_highlight_advisor/osl.py` or the body/signature of `pipeline.apply_osl`. Only additive code (`osl_step_caption`, `build_osl_result`) and UI wiring.
- **Live apply.** No "Add glow steps" button — the `keys.OSL_ON` checkbox is the only gate; the glow re-derives every rerun.
- **Never build on `main`.** Work stays on `feat/osl-object-source-lighting`; feature branch + PR.
- **Tests:** `.venv/Scripts/python -m pytest`. Paint colours are `np.ndarray` float32 `(3,)` RGB 0–255. Coverage lists are partitions built with `palette.default_coverage(n)`.

---

## File Structure

- **`src/mini_highlight_advisor/pipeline.py`** (modify) — add pure `osl_step_caption(index, n_steps, paint_name) -> str`.
- **`tests/test_pipeline_osl.py`** (modify) — add caption unit tests.
- **`ui/helpers.py`** (modify) — add `build_osl_result(...)` wrapping `apply_osl`, Streamlit-free.
- **`tests/test_ui_helpers.py`** (modify) — add `build_osl_result` unit tests (uses the synthetic hemisphere fixture).
- **`ui/results.py`** (modify) — `render_osl_steps` uses `osl_step_caption` for per-step captions.
- **`ui/osl_panel.py`** (modify) — `render(mask_shape, background_rgb)`: scaled canvas with the mini as background + click rescale to full res.
- **`tests/test_ui_osl_panel.py`** (modify) — add click-rescale unit test + source-gate assertions.
- **`ui/editor.py`** (modify) — pre-preview glow composite + 4th Glow tab (PS only) + store `keys.OSL_RESULT`.
- **`ui/ps_mode.py`** (modify) — delete post-editor OSL block; keep project-seed logic, moved before `editor.render`.
- **`app.py`** (modify) — Paint tab renders `results.render_osl_steps` from `keys.OSL_RESULT`.
- **`tests/test_ui_ps_mode.py`** / **`tests/test_ui_app_tabs.py`** (modify) — smoke: 4 tabs in PS mode, 3 in photo mode; no bottom duplicate image.
- **`CLAUDE.md`** (modify) — one-line note that OSL now lives in the editor's Glow tab.

Task order matches the spec's build order: leaf-first (caption → canvas → helper) so the editor task (which consumes them) comes last among code changes, then the wiring deletions, then docs.

---

## Task 1: Layer-aware glow-step captions (pure function)

**Files:**
- Modify: `src/mini_highlight_advisor/pipeline.py` (add `osl_step_caption` near `_rgb_to_hex`, ~line 44)
- Test: `tests/test_pipeline_osl.py`

**Interfaces:**
- Produces: `osl_step_caption(index: int, n_steps: int, paint_name: str) -> str` — index 0 = broadest/faintest glaze, index `n_steps-1` = hotspot, middle indices = "tighten". `paint_name` is interpolated into the returned text.

- [ ] **Step 1: Write the failing tests**

Add to `tests/test_pipeline_osl.py`:

```python
from mini_highlight_advisor.pipeline import osl_step_caption


def test_osl_caption_first_step_is_broad_glaze():
    cap = osl_step_caption(0, 3, "Moot Green")
    assert "Moot Green" in cap
    assert "broad" in cap.lower()
    assert "glaze" in cap.lower()


def test_osl_caption_last_step_is_hotspot():
    cap = osl_step_caption(2, 3, "Dead White")
    assert "Dead White" in cap
    assert "hotspot" in cap.lower()
    # sells the effect: away-facing surfaces stay dark
    assert "dark" in cap.lower()


def test_osl_caption_middle_step_is_tighten():
    cap = osl_step_caption(1, 3, "Moot Green")
    assert "Moot Green" in cap
    assert "tighten" in cap.lower()


def test_osl_caption_two_steps_has_broad_and_hotspot_only():
    first = osl_step_caption(0, 2, "A")
    last = osl_step_caption(1, 2, "A")
    assert "broad" in first.lower()
    assert "hotspot" in last.lower()


def test_osl_caption_handles_missing_paint_name():
    # label can be None when no catalog match; caption must still be a str
    cap = osl_step_caption(0, 3, None)
    assert isinstance(cap, str) and cap
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `.venv/Scripts/python -m pytest tests/test_pipeline_osl.py -k osl_caption -v`
Expected: FAIL with `ImportError: cannot import name 'osl_step_caption'`.

- [ ] **Step 3: Implement the function**

Add to `src/mini_highlight_advisor/pipeline.py` (after `_rgb_to_hex`, before `apply_osl`):

```python
def osl_step_caption(index: int, n_steps: int, paint_name: str | None) -> str:
    """Glazing guidance for one OSL glow layer.

    Glow bands are strictly nested broad -> tight: index 0 is the broadest,
    faintest glaze; the final index is the hotspot; anything between tightens.
    """
    paint = paint_name or "the glow colour"
    if index == 0:
        return (f"Thin glaze of **{paint}** over every surface facing the light — "
                f"keep it broad and faint, build it up in several watery passes.")
    if index == n_steps - 1:
        return (f"Hotspot — near-pure **{paint}** on the single point nearest the "
                f"source. Leave surfaces turned away from the light dark.")
    return (f"Tighten **{paint}** onto the surfaces closest and most face-on to the "
            f"source; a little less thinned than the broad glaze.")
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `.venv/Scripts/python -m pytest tests/test_pipeline_osl.py -k osl_caption -v`
Expected: PASS (5 tests).

- [ ] **Step 5: Commit**

```bash
git add src/mini_highlight_advisor/pipeline.py tests/test_pipeline_osl.py
git commit -m "feat(osl): layer-aware glow-step captions (broad/tighten/hotspot)"
```

---

## Task 2: Wire enriched captions into the Paint-tab step renderer

**Files:**
- Modify: `ui/results.py:94-109` (`render_osl_steps`)
- Test: `tests/test_ui_results_ps.py`

**Interfaces:**
- Consumes: `pipeline.osl_step_caption` (Task 1); `osl_result.steps` where each `BandStep` has `.label` (paint name or None), `.zone_rgb`, `.cumulative_rgb`.

- [ ] **Step 1: Write the failing test**

Add to `tests/test_ui_results_ps.py` (create the file if it does not exist, with the imports shown):

```python
import numpy as np
from types import SimpleNamespace
import ui.results as results


def _fake_step(label):
    img = np.zeros((4, 4, 3), np.uint8)
    return SimpleNamespace(label=label, zone_rgb=img, cumulative_rgb=img, kind="osl")


def test_render_osl_steps_uses_layer_captions(monkeypatch):
    captured = []
    monkeypatch.setattr(results.st, "subheader", lambda *a, **k: None)
    monkeypatch.setattr(results.st, "caption", lambda *a, **k: None)
    monkeypatch.setattr(results.st, "columns",
                        lambda n: [SimpleNamespace(image=lambda *a, **k: captured.append(k.get("caption")))
                                   for _ in range(n)])
    osl_result = SimpleNamespace(steps=[_fake_step("Moot Green"),
                                        _fake_step("Warpstone"),
                                        _fake_step("Dead White")])
    results.render_osl_steps(osl_result)
    joined = " ".join(c or "" for c in captured).lower()
    assert "broad" in joined
    assert "hotspot" in joined
    assert "moot green" in joined
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.venv/Scripts/python -m pytest tests/test_ui_results_ps.py -k osl_steps_uses_layer -v`
Expected: FAIL — current captions are `s.label or "glow zone"`, so "broad"/"hotspot" are absent.

- [ ] **Step 3: Update `render_osl_steps`**

In `ui/results.py`, replace the loop body (currently lines ~104-109):

```python
    for s in osl_result.steps:
        cols = st.columns(2)
        cols[0].image(s.zone_rgb, caption=(s.label or "glow zone"),
                      use_container_width=True)
        cols[1].image(s.cumulative_rgb, caption="after this layer",
                      use_container_width=True)
```

with:

```python
    n = len(osl_result.steps)
    for i, s in enumerate(osl_result.steps):
        cols = st.columns(2)
        cols[0].image(s.zone_rgb,
                      caption=pipeline.osl_step_caption(i, n, s.label),
                      use_container_width=True)
        cols[1].image(s.cumulative_rgb, caption="after this layer",
                      use_container_width=True)
```

Add the import at the top of `ui/results.py` (alongside the existing `from mini_highlight_advisor import materials`):

```python
from mini_highlight_advisor import pipeline
```

- [ ] **Step 4: Run test to verify it passes**

Run: `.venv/Scripts/python -m pytest tests/test_ui_results_ps.py -k osl_steps_uses_layer -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add ui/results.py tests/test_ui_results_ps.py
git commit -m "feat(osl): render glow steps with glazing guidance captions"
```

---

## Task 3: Placement canvas shows the mini (background + click rescale)

**Files:**
- Modify: `ui/osl_panel.py` (`render` signature + the `st_canvas` block, lines ~26-61)
- Test: `tests/test_ui_osl_panel.py`

**Interfaces:**
- Produces: `osl_panel.render(mask_shape, background_rgb) -> dict | None` — `background_rgb` is the current painted preview `(H,W,3)` uint8 shown under the click point. Returned dict `x`/`y` are in **full mask resolution**, not display-canvas coordinates.
- Produces: `osl_panel._rescale_click(click, disp_w, disp_h, src_w, src_h) -> tuple[float, float]` — pure helper mapping a display-canvas click to full-res coords.

- [ ] **Step 1: Write the failing tests**

Add to `tests/test_ui_osl_panel.py`:

```python
def test_render_signature_takes_background():
    import inspect, ui.osl_panel as op
    params = list(inspect.signature(op.render).parameters)
    assert params[:2] == ["mask_shape", "background_rgb"]


def test_rescale_click_maps_display_to_full_res():
    import ui.osl_panel as op
    # display canvas 300x200 over a 600x400 source: a click at (150,100)
    # is the centre -> full-res (300,200)
    x, y = op._rescale_click((150.0, 100.0), disp_w=300, disp_h=200,
                             src_w=600, src_h=400)
    assert abs(x - 300.0) < 1e-6
    assert abs(y - 200.0) < 1e-6


def test_rescale_click_identity_when_same_size():
    import ui.osl_panel as op
    x, y = op._rescale_click((42.0, 17.0), disp_w=128, disp_h=128,
                             src_w=128, src_h=128)
    assert (x, y) == (42.0, 17.0)
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `.venv/Scripts/python -m pytest tests/test_ui_osl_panel.py -k "rescale or signature" -v`
Expected: FAIL — `_rescale_click` undefined and `render` still takes only `mask_shape`.

- [ ] **Step 3: Add the rescale helper and update the canvas block**

In `ui/osl_panel.py`, add the import for `Image` at the top:

```python
from PIL import Image
```

Add the pure helper (module level):

```python
def _rescale_click(click, disp_w, disp_h, src_w, src_h) -> tuple[float, float]:
    """Map a click on the display-scaled canvas back to full mask resolution."""
    sx, sy = src_w / disp_w, src_h / disp_h
    return float(click[0]) * sx, float(click[1]) * sy
```

Change the signature:

```python
def render(mask_shape, background_rgb) -> dict | None:
```

Replace the canvas block (currently lines ~42-54) — the `st.caption(...)` through `st.session_state[keys.OSL_POINT] = click` — with a scaled canvas that shows the mini and rescales the click:

```python
    st.caption("Click the source point on the mini below.")
    src_h, src_w = mask_shape
    disp_w = min(600, src_w)
    disp_h = round(src_h * disp_w / src_w)
    click = None
    if st_canvas is not None:
        canvas = st_canvas(
            background_image=Image.fromarray(background_rgb),
            height=disp_h, width=disp_w, drawing_mode="point",
            stroke_width=6, stroke_color="#ff28c8", key=keys.OSL_CANVAS,
        )
        raw = geometry.last_point(canvas)
        if raw is not None:
            click = _rescale_click(raw, disp_w, disp_h, src_w, src_h)
    if click is None:
        click = st.session_state.get(keys.OSL_POINT)
    if click is None:
        st.info("No source placed yet — click on the mini.")
        return None
    st.session_state[keys.OSL_POINT] = click
```

Note: `keys.OSL_POINT` now always stores full-res coords, matching what the seed logic in `ps_mode.py` writes from persisted `x`/`y` — no unit mismatch.

- [ ] **Step 4: Run tests to verify they pass**

Run: `.venv/Scripts/python -m pytest tests/test_ui_osl_panel.py -v`
Expected: PASS (existing 2 + new 3).

- [ ] **Step 5: Commit**

```bash
git add ui/osl_panel.py tests/test_ui_osl_panel.py
git commit -m "feat(osl): placement canvas shows the mini + rescales click to full res"
```

---

## Task 4: `build_osl_result` helper (Streamlit-free glow compositor)

**Files:**
- Modify: `ui/helpers.py` (add `build_osl_result`)
- Test: `tests/test_ui_helpers.py`

**Interfaces:**
- Consumes: `pipeline.OslSource`, `pipeline.apply_osl`, `palette.default_coverage`.
- Produces: `build_osl_result(combined_rgb, normals, mask, params, owned, catalog) -> tuple[np.ndarray, OslResult | None]`. When `params is None` returns `(combined_rgb, None)` (the input array, unchanged). Otherwise returns `(osl_result.preview_rgb, osl_result)`. `params` is the dict from `osl_panel.render` (`x, y, height, reach, intensity, coverage, glow_rgb, hot_rgb`).

- [ ] **Step 1: Write the failing tests**

Add to `tests/test_ui_helpers.py`:

```python
import numpy as np
from PIL import Image
from pathlib import Path
from mini_highlight_advisor import palette

_PS_FIX = Path(__file__).parent / "fixtures" / "ps"


def _load_synth():
    rgb = np.asarray(Image.open(_PS_FIX / "synth_normal.png").convert("RGB"), np.float32) / 255.0
    n = rgb * 2.0 - 1.0
    n /= np.clip(np.linalg.norm(n, axis=-1, keepdims=True), 1e-6, None)
    mask = np.asarray(Image.open(_PS_FIX / "synth_mask.png").convert("L")) > 127
    return n.astype(np.float32), mask


def _osl_params(mask):
    h, w = mask.shape
    return {
        "x": w / 2, "y": h / 2, "height": 40.0, "reach": 25.0, "intensity": 1.0,
        "coverage": palette.default_coverage(3),
        "glow_rgb": np.array([40., 200., 90.], np.float32),
        "hot_rgb": np.array([200., 255., 210.], np.float32),
    }


def test_build_osl_result_none_params_returns_input_unchanged():
    from ui.helpers import build_osl_result
    n, mask = _load_synth()
    base = np.full((*mask.shape, 3), 60, np.uint8)
    preview, res = build_osl_result(base, n, mask, None, owned=[], catalog=[])
    assert res is None
    assert preview is base  # exact same array, no copy/composite


def test_build_osl_result_composites_glow_and_leaves_base_untouched():
    from ui.helpers import build_osl_result
    n, mask = _load_synth()
    base = np.full((*mask.shape, 3), 60, np.uint8)
    preview, res = build_osl_result(base, n, mask, _osl_params(mask),
                                    owned=[], catalog=[])
    assert res is not None and len(res.steps) == 3
    assert preview.shape == base.shape
    assert preview.mean() > base.mean()      # glow brightened the preview
    assert base.mean() == 60                 # caller's array not mutated
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `.venv/Scripts/python -m pytest tests/test_ui_helpers.py -k build_osl_result -v`
Expected: FAIL with `ImportError: cannot import name 'build_osl_result'`.

- [ ] **Step 3: Implement `build_osl_result`**

Add to `ui/helpers.py` (import `pipeline` at top if absent: `from mini_highlight_advisor import pipeline`):

```python
def build_osl_result(combined_rgb, normals, mask, params, owned=None, catalog=None):
    """Composite the OSL glow onto combined_rgb and return (preview_rgb, OslResult).

    Streamlit-free so it is unit-testable. `params` is the dict from
    osl_panel.render, or None when the glow is disabled/unplaced — in which case
    the input image is returned unchanged and the result is None.
    """
    if params is None:
        return combined_rgb, None
    src = pipeline.OslSource(
        x=params["x"], y=params["y"], height=params["height"],
        glow_rgb=params["glow_rgb"], hot_rgb=params["hot_rgb"],
    )
    result = pipeline.apply_osl(
        combined_rgb, normals, mask, src,
        reach=params["reach"], intensity=params["intensity"],
        coverage=params["coverage"], owned=owned or [], catalog=catalog,
    )
    return result.preview_rgb, result
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `.venv/Scripts/python -m pytest tests/test_ui_helpers.py -k build_osl_result -v`
Expected: PASS (2 tests).

- [ ] **Step 5: Commit**

```bash
git add ui/helpers.py tests/test_ui_helpers.py
git commit -m "feat(osl): build_osl_result helper — Streamlit-free glow compositor"
```

---

## Task 5: Editor renders the Glow tab and composites glow into the main preview

**Files:**
- Modify: `ui/editor.py` (import; pre-preview composite before `st.image`; 4th tab; store result)
- Test: `tests/test_ui_ps_mode.py`

**Interfaces:**
- Consumes: `helpers.build_osl_result` (Task 4), `osl_panel.render(mask_shape, background_rgb)` (Task 3), `context.CATALOG`, `keys.OSL_ON` / `keys.OSL_RESULT`.
- Produces: after `editor.render`, `st.session_state[keys.OSL_RESULT]` holds the current `OslResult` or `None`; the main preview image shows the glow when enabled.

- [ ] **Step 1: Write the failing test**

Add to `tests/test_ui_ps_mode.py` (source-level guard — matches the lightweight style already used for OSL/PS UI):

```python
def test_editor_composites_osl_and_has_glow_tab():
    import inspect, ui.editor as ed
    src = inspect.getsource(ed)
    # Glow tab wired in
    assert "Glow" in src
    # glow computed via the shared helper, before the preview image
    assert "build_osl_result" in src
    # result stored for the Paint tab
    assert "OSL_RESULT" in src
    # PS-only: the 4th tab is gated on normals
    assert "has_normals" in src
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.venv/Scripts/python -m pytest tests/test_ui_ps_mode.py -k composites_osl -v`
Expected: FAIL — `editor.py` has no OSL wiring yet.

- [ ] **Step 3: Wire the editor**

In `ui/editor.py`, extend the imports:

```python
from ui import colour_panel, context, geometry, helpers, keys, osl_panel, regions_panel, results, state
```

Right after `multi = helpers.run_analysis(...)` and the two `st.session_state` assignments (~line 41), before `col_render, col_controls = st.columns(...)`, compute the glow so the preview can show it:

```python
    # OSL is a PS-mode glow layer. Read its params from session_state BEFORE the
    # preview draws (same one-rerun-ahead pattern as the visibility toggles above)
    # so the glow shows in the MAIN preview, not a duplicate image below.
    osl_preview_rgb = multi.combined_rgb
    osl_result = None
    has_normals = normal_field is not None
    if has_normals and st.session_state.get(keys.OSL_ON):
        _params = osl_panel.params_from_session(mask_shape=shading.mask.shape)
        osl_preview_rgb, osl_result = helpers.build_osl_result(
            multi.combined_rgb, normal_field, shading.mask, _params,
            owned=owned_paints, catalog=context.CATALOG)
    st.session_state[keys.OSL_RESULT] = osl_result
```

Change the preview image (line ~46) to show the composited version:

```python
        st.image(osl_preview_rgb,
                 caption="Painted preview (all regions)",
                 use_container_width=True)
```

Change the tabs line (~85) to add a PS-only Glow tab:

```python
        tab_labels = ["🗺 Manage", "🎨 Colour", "🖌 Technique"]
        if has_normals:
            tab_labels.append("✨ Glow")
        subtabs = st.tabs(tab_labels)
        subtab_m, subtab_c, subtab_t = subtabs[0], subtabs[1], subtabs[2]
```

Keep the existing `with subtab_m: / subtab_c: / subtab_t:` blocks. After the Technique block, add:

```python
        if has_normals:
            with subtabs[3]:
                osl_panel.render(shading.mask.shape, multi.combined_rgb)
```

Note: the Glow tab body writes widget values into `session_state`; the composite at the top reads them next rerun. `osl_panel.render`'s returned dict is not used here — the editor reads params via `params_from_session` so the compute happens before the tab renders. (This mirrors how `render_technique_controls` writes widgets that `run_analysis` consumes on the next pass.)

- [ ] **Step 4: Add `params_from_session` to `osl_panel.py`**

`osl_panel.render` currently both *draws widgets* and *returns params*; the editor needs the params one rerun earlier (before the tab draws). Factor the param assembly out. Add to `ui/osl_panel.py`:

```python
def params_from_session(mask_shape) -> dict | None:
    """Assemble OSL params from session_state without drawing widgets.

    Returns None unless the glow is enabled AND a source point is placed.
    Mirrors the dict render() returns, reading the same keys the widgets write.
    """
    if not st.session_state.get(keys.OSL_ON):
        return None
    click = st.session_state.get(keys.OSL_POINT)
    if click is None:
        return None
    glow_hex = st.session_state.get(keys.OSL_GLOW) or '#%02x%02x%02x' % PRESETS["Torch"][0]
    hot_hex = st.session_state.get(keys.OSL_HOT) or '#%02x%02x%02x' % PRESETS["Torch"][1]
    n_layers = int(st.session_state.get(keys.OSL_LAYERS, 3))
    return {
        "x": float(click[0]), "y": float(click[1]),
        "height": float(st.session_state.get(keys.OSL_HEIGHT, 40.0)),
        "reach": float(st.session_state.get(keys.OSL_REACH, 60.0)),
        "intensity": float(st.session_state.get(keys.OSL_INTENSITY, 1.0)),
        "coverage": palette.default_coverage(n_layers),
        "glow_rgb": _hex_to_rgb(glow_hex), "hot_rgb": _hex_to_rgb(hot_hex),
    }
```

(`render` may now delegate its final dict-building to `params_from_session` to stay DRY, but that refactor is optional — the editor path uses `params_from_session` directly.)

- [ ] **Step 5: Run test + full UI suite to verify**

Run: `.venv/Scripts/python -m pytest tests/test_ui_ps_mode.py tests/test_ui_osl_panel.py -v`
Expected: PASS. (No Streamlit runtime needed — these are source/import guards.)

- [ ] **Step 6: Commit**

```bash
git add ui/editor.py ui/osl_panel.py tests/test_ui_ps_mode.py
git commit -m "feat(osl): Glow tab in editor + glow composited into main preview"
```

---

## Task 6: Remove the below-editor OSL block; move seed logic up; steps to Paint tab

**Files:**
- Modify: `ui/ps_mode.py` (delete lines ~89-133 block; move seed logic above `editor.render`)
- Modify: `app.py:85-88` (Paint tab renders OSL steps)
- Test: `tests/test_ui_app_tabs.py`

**Interfaces:**
- Consumes: `keys.OSL_RESULT` set by `editor.render` (Task 5); `results.render_osl_steps` (Task 2).

- [ ] **Step 1: Write the failing test**

Add to `tests/test_ui_app_tabs.py`:

```python
def test_paint_tab_renders_osl_steps():
    import inspect, app
    src = inspect.getsource(app)
    assert "render_osl_steps" in src


def test_ps_mode_has_no_bottom_osl_image():
    import inspect, ui.ps_mode as ps
    src = inspect.getsource(ps)
    # the duplicate "With object-source glow" preview image is gone
    assert "With object-source glow" not in src
    # step rendering no longer lives in ps_mode
    assert "render_osl_steps" not in src
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `.venv/Scripts/python -m pytest tests/test_ui_app_tabs.py -k "osl" -v`
Expected: FAIL — `app.py` lacks `render_osl_steps`; `ps_mode.py` still has the bottom image + step call.

- [ ] **Step 3: Edit `ui/ps_mode.py`**

Move the project-seed block (currently lines ~96-116, the `_active_idx ... st.session_state.setdefault(keys.OSL_LAYERS, ...)` logic) to run **before** `editor.render(...)` is called (~line 85). Then delete the entire OSL rendering block that follows `editor.render` (the `st.divider()`, `st.subheader("Object-source lighting (OSL)")`, the `osl_panel.render`, the `_pl.OslSource`/`apply_osl` calls, the `st.image(osl_result.preview_rgb, ...)`, `st.session_state[keys.OSL_RESULT] = osl_result`, and `results.render_osl_steps(osl_result)` — lines ~89-133).

After the edit, `render` ends at the `multi = editor.render(...)` call (the editor now owns OSL). Remove the now-unused imports `osl_panel`, `results`, and `pipeline as _pl` / `context` from `ps_mode.py` **only if** nothing else in the file uses them (grep first: `grep -n "osl_panel\|results\.\|_pl\.\|context\." ui/ps_mode.py`).

- [ ] **Step 4: Edit `app.py` Paint tab**

Change the Paint tab (lines ~85-88) from:

```python
with tab_paint:
    multi = st.session_state.get(keys.LAST_MULTI)
    results.render_steps(multi)
```

to:

```python
with tab_paint:
    multi = st.session_state.get(keys.LAST_MULTI)
    results.render_steps(multi)
    results.render_osl_steps(st.session_state.get(keys.OSL_RESULT))
```

(`results` and `keys` are already imported in `app.py`; confirm with `grep -n "import" app.py`.)

- [ ] **Step 5: Run tests to verify they pass**

Run: `.venv/Scripts/python -m pytest tests/test_ui_app_tabs.py tests/test_ui_ps_mode.py -v`
Expected: PASS.

- [ ] **Step 6: Commit**

```bash
git add ui/ps_mode.py app.py tests/test_ui_app_tabs.py
git commit -m "refactor(osl): steps to Paint tab; drop below-editor OSL block; seed before editor"
```

---

## Task 7: Full-suite regression + CLAUDE.md note

**Files:**
- Modify: `CLAUDE.md` (`osl.py` module-map line)

- [ ] **Step 1: Run the whole test suite**

Run: `.venv/Scripts/python -m pytest -q`
Expected: PASS. Two pre-existing `test_ui_gallery.py` failures are known-unrelated (see project memory) — confirm the count is exactly those two and nothing new. If any OSL/editor/results/ps_mode test fails, fix before proceeding (do NOT edit `osl.py` math to make a UI test pass).

- [ ] **Step 2: Update the module-map note**

In `CLAUDE.md`, append to the `osl.py` bullet:

```markdown
  OSL now lives in the editor's PS-mode **Glow tab** (`ui/osl_panel.py`); the glow
  composites into the main preview via `ui/helpers.build_osl_result`, and its glazing
  steps render in the Paint tab through `results.render_osl_steps`.
```

- [ ] **Step 3: Commit**

```bash
git add CLAUDE.md
git commit -m "docs(osl): note the Glow-tab reshape in the module map"
```

- [ ] **Step 4: Manual smoke (user-run, not automated)**

Hand back to the user to run `streamlit run app.py`, import a PS bundle, open the **✨ Glow** tab, enable the glow, click on the mini, and confirm: (a) the click canvas shows the mini; (b) the main preview updates with the glow; (c) no duplicate image at the bottom of Studio; (d) the Paint tab shows glazing-guidance captions. Per project convention, the agent does not self-run the Streamlit app.

---

## Self-Review

**Spec coverage:**
- Blank placement canvas (#1) → Task 3. ✓
- Glow in main preview, bottom duplicate removed (#2) → Tasks 5 + 6. ✓
- Toggleable Glow tab / layer, PS-only, not a RegionBook region (#3) → Task 5 (tab gated on `has_normals`; `keys.OSL_ON` is the toggle; no `Region` created). ✓
- Enriched glazing captions (#4) → Tasks 1 + 2. ✓
- Steps move Studio→Paint tab → Task 6. ✓
- Glow math byte-identical → enforced by Global Constraints + Task 7 Step 1 guard; no task edits `osl.py` or `apply_osl`. ✓
- Persistence/seed preserved → Task 6 Step 3 moves (not deletes) the seed block. ✓
- Live apply, no button → `keys.OSL_ON`-gated composite in Task 5; no button added. ✓
- Testing (build_osl_result unit, caption unit, click rescale, UI smoke 4-vs-3 tabs) → Tasks 1,3,4,5,6. ✓

**Placeholder scan:** No TBD/TODO; every code step has concrete code. ✓

**Type consistency:** `build_osl_result(combined_rgb, normals, mask, params, owned, catalog) -> (ndarray, OslResult|None)` defined in Task 4, consumed identically in Task 5. `osl_step_caption(index, n_steps, paint_name)` defined Task 1, consumed Task 2. `osl_panel.render(mask_shape, background_rgb)` + `params_from_session(mask_shape)` defined Task 3/5, consumed in editor Task 5. `keys.OSL_RESULT` written in Task 5, read in Task 6. ✓
