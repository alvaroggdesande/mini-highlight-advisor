# Cavity / AO Recess Shades Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add normals-derived **recess shades** (the first non-highlight output) that darken concave creases/cavities, capability-gated on a normal field, leaving Path L byte-identical.

**Architecture:** Mirror the shipped edge-highlight slice on the *concave* side of the curvature signal. A new `edges.cavity_mask` (concave twin of `geometric_edge_mask`) feeds a dark auto-derived shade colour into the *existing* `edge_overlays` fixed-alpha compositing path and a new `overlay.shade_steps` paint-along step. One `shades=` flag threads through `analyze_regions` → `plan_region`, gated on `normals is not None`.

**Tech Stack:** Python 3.11, numpy, OpenCV (cv2), Streamlit; pytest + streamlit AppTest. Env: `.venv/Scripts/python`.

**Spec:** `docs/superpowers/specs/2026-08-25-cavity-ao-recess-shades-design.md`

## Global Constraints

- **Path L frozen:** with `shades=False` OR no normal field, output is **byte-identical** to today. Every pipeline change is gated on `shades and normals is not None`.
- **Normals-only:** no luminance approximation of recesses. Shades exist only when a normal field is present.
- **Reuse, don't fork:** reuse `edges._despeckle`, `edges.curvature` (via `surface.curvature`), the `edge_overlays` `list[(mask, color)]` compositing, and the `BandStep`/`_zone_render`/`_render_step` step machinery. No new compositing code.
- **Sensitivity→percentile mapping copied verbatim from `geometric_edge_mask`:** `pct = float(np.clip(94.0 - 12.0 * sensitivity, 82.0, 97.0))`.
- **Shade colour:** `_SHADE_DARKEN = 0.55`; `shade_rgb = (colors[0] * _SHADE_DARKEN).astype(np.float32)`.
- **Run tests with:** `.venv/Scripts/python -m pytest`.
- **Never build on `main`:** work stays on `feat/cavity-ao-recess-shades`; PR at the end.

## File Structure

- `src/mini_highlight_advisor/edges.py` — MODIFY: add `cavity_mask`; broaden module docstring to mention recess masks.
- `src/mini_highlight_advisor/overlay.py` — MODIFY: add `shade_steps`.
- `src/mini_highlight_advisor/pipeline.py` — MODIFY: add `_SHADE_DARKEN`; add `shades=` param to `analyze_regions` + `plan_region`; build shade overlay + step under the capability gate; import `cavity_mask`, `shade_steps`.
- `ui/keys.py` — MODIFY: add `SHADES` key.
- `ui/results.py` — MODIFY: PS-only "Recess shades" checkbox; thread `shades=` into `analyze_regions`.
- `tests/test_edges_cavity.py` — CREATE.
- `tests/test_overlay.py` — MODIFY: add `shade_steps` tests.
- `tests/test_pipeline_shades.py` — CREATE.
- `tests/test_ui_ps_mode.py` — MODIFY: add recess-shades checkbox test.

---

### Task 1: `edges.cavity_mask` — concave-curvature recess mask

**Files:**
- Modify: `src/mini_highlight_advisor/edges.py`
- Test: `tests/test_edges_cavity.py` (create)

**Interfaces:**
- Consumes: `edges.curvature` (already imported as `from .surface import curvature`), `edges._despeckle`, `edges._MIN_EDGE_AREA`.
- Produces: `cavity_mask(normals: np.ndarray, mask: np.ndarray, sensitivity: float = 0.5) -> np.ndarray` (bool `(H,W)`). Concave twin of `geometric_edge_mask`: thresholds `clip(-curvature, 0, None)` at the same percentile, despeckled. Graceful-empty on flat/convex-only input.

- [ ] **Step 1: Write the failing tests**

Create `tests/test_edges_cavity.py`:

```python
import numpy as np

from mini_highlight_advisor import relight
from mini_highlight_advisor.edges import cavity_mask, edge_mask, geometric_edge_mask


def _vcrease(h=40, w=40, c0=20, half=8):
    """A concave vertical crease at column c0: nx sweeps +sin..-sin THROUGH the
    crease, so d(nx)/dcol < 0 there and -curvature peaks on the crease column.
    (Sign-flipped mirror of test_edges_geometric._vridge, which is convex.)"""
    col = np.arange(w, dtype=np.float32)
    ang = np.clip((col - c0) / half, -1.0, 1.0) * (np.pi / 3.0)
    n = np.zeros((h, w, 3), np.float32)
    n[..., 0] = -np.sin(ang)[None, :]
    n[..., 2] = np.cos(ang)[None, :]
    return n, np.ones((h, w), bool), c0


def _vridge(h=40, w=40, c0=20, half=8):
    col = np.arange(w, dtype=np.float32)
    ang = np.clip((col - c0) / half, -1.0, 1.0) * (np.pi / 3.0)
    n = np.zeros((h, w, 3), np.float32)
    n[..., 0] = np.sin(ang)[None, :]
    n[..., 2] = np.cos(ang)[None, :]
    return n, np.ones((h, w), bool), c0


def test_cavity_lands_on_crease():
    n, mask, c0 = _vcrease()
    g = cavity_mask(n, mask, 0.5)
    cols = np.where(g.any(axis=0))[0]
    assert cols.size > 0
    assert cols.min() >= c0 - 3 and cols.max() <= c0 + 3


def test_cavity_is_light_independent():
    """Core value claim: the luminance edge MOVES with the virtual light; the
    curvature-recess mask does not depend on light and stays on the crease."""
    n, mask, c0 = _vcrease()
    lf1, _ = relight.relight(n, mask, relight.light_dir(0, 30))
    lf2, _ = relight.relight(n, mask, relight.light_dir(180, 30))
    e1 = edge_mask(lf1, mask, 0.5)
    e2 = edge_mask(lf2, mask, 0.5)
    g = cavity_mask(n, mask, 0.5)
    assert not np.array_equal(e1, e2)                  # luminance response moves
    cols = np.where(g.any(axis=0))[0]
    assert cols.size > 0
    assert abs(int(round(cols.mean())) - c0) <= 3


def test_cavity_convex_ridge_is_empty():
    """A purely convex ridge has no concavity -> recess mask empty (distinct from
    geometric_edge_mask, which fires on exactly this input)."""
    n, mask, _ = _vridge()
    assert cavity_mask(n, mask, 0.5).sum() == 0
    assert geometric_edge_mask(n, mask, 0.5).sum() > 0   # sanity: convex fires edges


def test_cavity_flat_normals_empty():
    n = np.zeros((30, 30, 3), np.float32); n[..., 2] = 1.0
    mask = np.ones((30, 30), bool)
    assert cavity_mask(n, mask, 0.5).sum() == 0


def test_cavity_speckle_is_dropped():
    """Isolated single-pixel concave tilts (primer grain) are removed by the
    connected-component filter."""
    n = np.zeros((60, 60, 3), np.float32); n[..., 2] = 1.0
    for (r, c) in [(10, 10), (20, 40), (35, 15), (48, 50), (30, 30)]:
        n[r, c, 0] = -0.4
        n[r, c, 2] = np.sqrt(1.0 - 0.4 ** 2)
    mask = np.ones((60, 60), bool)
    assert cavity_mask(n, mask, 0.5).sum() == 0
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `.venv/Scripts/python -m pytest tests/test_edges_cavity.py -v`
Expected: FAIL with `ImportError: cannot import name 'cavity_mask'`.

- [ ] **Step 3: Implement `cavity_mask`**

In `src/mini_highlight_advisor/edges.py`, first broaden the module docstring's first line from `"""Edge-highlight masks.` to `"""Curvature-derived highlight and recess masks.` (keep the rest of the docstring unchanged). Then add, directly after `geometric_extreme_edge_mask`:

```python
def cavity_mask(normals: np.ndarray, mask: np.ndarray,
                sensitivity: float = 0.5) -> np.ndarray:
    """Recess shades from concave curvature of the normal field — light-independent.

    Concave twin of geometric_edge_mask: same sensitivity->percentile mapping and
    despeckle, sourced from the concave clip of curvature (creases/cavities) instead
    of the convex clip. Flat or convex-only normals -> empty mask (graceful, no
    manufactured shade). Thresholding concave curvature is thresholding ambient
    occlusion (AO = 1 - normalised concavity is monotonic), so this consumes the AO
    signal in its raw form.
    """
    mask = mask.astype(bool)
    conc = np.clip(-curvature(normals, mask), 0.0, None)   # concave creases only
    conc[~mask] = 0.0
    vals = conc[mask]
    vals = vals[vals > 0]
    if vals.size == 0:
        return np.zeros(mask.shape, bool)
    pct = float(np.clip(94.0 - 12.0 * sensitivity, 82.0, 97.0))
    thr = np.percentile(vals, pct)
    return _despeckle((conc >= thr) & mask)
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `.venv/Scripts/python -m pytest tests/test_edges_cavity.py -v`
Expected: PASS (5 tests).

- [ ] **Step 5: Commit**

```bash
git add src/mini_highlight_advisor/edges.py tests/test_edges_cavity.py
git commit -m "feat(edges): cavity_mask — concave-curvature recess masks (light-independent)"
```

---

### Task 2: `overlay.shade_steps` — recess paint-along step

**Files:**
- Modify: `src/mini_highlight_advisor/overlay.py`
- Test: `tests/test_overlay.py`

**Interfaces:**
- Consumes: `overlay.BandStep`, `overlay._zone_render`, `overlay._render_step`.
- Produces: `shade_steps(rgb, recess_mask, shade_rgb, alpha=0.78, start_index=0) -> list[BandStep]`. Returns exactly one `BandStep(kind="shade", label="Recess Shade", index=start_index, is_last=True)` rendered with `shade_rgb`.

- [ ] **Step 1: Write the failing tests**

In `tests/test_overlay.py`, add `shade_steps` to the existing import line
(`from mini_highlight_advisor.overlay import ... edge_steps`) so it reads
`... edge_steps, shade_steps`, then append these tests at end of file:

```python
def _plate_and_mask():
    rgb = np.zeros((20, 30, 3), np.uint8)
    rgb[:, 15:] = 200
    mask = np.ones((20, 30), bool)
    return rgb, mask


def test_shade_steps_single_step_shape():
    rgb, mask = _plate_and_mask()
    recess = np.zeros((20, 30), bool); recess[:, 5:9] = True
    shade_rgb = np.array([10, 10, 10], np.float32)
    steps = shade_steps(rgb, recess, shade_rgb, start_index=6)
    assert len(steps) == 1
    s = steps[0]
    assert s.kind == "shade"
    assert s.label == "Recess Shade"
    assert s.index == 6
    assert s.is_last is True


def test_shade_steps_uses_shade_colour():
    rgb, mask = _plate_and_mask()
    recess = np.zeros((20, 30), bool); recess[:, 5:9] = True
    shade_rgb = np.array([10, 10, 10], np.float32)
    s = shade_steps(rgb, recess, shade_rgb, start_index=6)[0]
    # inside the recess the cumulative render is pulled toward the dark shade colour;
    # a bright background pixel (200) must be darkened there.
    assert s.cumulative_rgb[0, 6].mean() < 200


def test_shade_steps_empty_mask_renders():
    rgb, mask = _plate_and_mask()
    recess = np.zeros((20, 30), bool)
    steps = shade_steps(rgb, recess, np.array([10, 10, 10], np.float32), start_index=6)
    assert len(steps) == 1                     # still one step, no crash
    assert steps[0].kind == "shade"
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `.venv/Scripts/python -m pytest tests/test_overlay.py -k shade -v`
Expected: FAIL with `ImportError: cannot import name 'shade_steps'`.

- [ ] **Step 3: Implement `shade_steps`**

In `src/mini_highlight_advisor/overlay.py`, add directly after `edge_steps`:

```python
def shade_steps(rgb, recess_mask, shade_rgb, alpha: float = 0.78,
                start_index: int = 0) -> list[BandStep]:
    """Recess-shade paint-along step (mirror of edge_steps, one tier).

    One BandStep darkening the concave-recess zone with the auto-derived shade
    colour. Empty recess_mask still yields a step (empty active zone), never a crash.
    """
    return [BandStep(
        index=start_index,
        zone_rgb=_zone_render(rgb, recess_mask),
        cumulative_rgb=_render_step(rgb, recess_mask, shade_rgb, alpha),
        exact_rgb=_render_step(rgb, recess_mask, shade_rgb, alpha),
        is_last=True, kind="shade", label="Recess Shade",
    )]
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `.venv/Scripts/python -m pytest tests/test_overlay.py -k shade -v`
Expected: PASS (3 tests).

- [ ] **Step 5: Commit**

```bash
git add src/mini_highlight_advisor/overlay.py tests/test_overlay.py
git commit -m "feat(overlay): shade_steps — recess-shade paint-along step"
```

---

### Task 3: Pipeline threading — `shades=` gated on normals

**Files:**
- Modify: `src/mini_highlight_advisor/pipeline.py`
- Test: `tests/test_pipeline_shades.py` (create)

**Interfaces:**
- Consumes: `edges.cavity_mask` (Task 1), `overlay.shade_steps` (Task 2).
- Produces: `analyze_regions(..., shades: bool = False)` and `plan_region(..., shades: bool = False)`. When `shades and normals is not None`: a `(recess_mask, shade_rgb)` tuple is **prepended** to `RegionPlan.edge_overlays`, and one `BandStep(kind="shade")` is appended to `RegionPlan.steps`. Module constant `_SHADE_DARKEN = 0.55`.

- [ ] **Step 1: Write the failing tests**

Create `tests/test_pipeline_shades.py`:

```python
import numpy as np

from mini_highlight_advisor.pipeline import analyze_regions, WHOLE_MINI
from mini_highlight_advisor.palette import DEFAULT_PALETTE, default_coverage

PAL = DEFAULT_PALETTE[:5]
COV = default_coverage(5)


def _whole(res):
    return next(p for p in res.plans if p.name == WHOLE_MINI)


def _vcrease(h=48, w=48, c0=24, half=8):
    col = np.arange(w, dtype=np.float32)
    ang = np.clip((col - c0) / half, -1.0, 1.0) * (np.pi / 3.0)
    n = np.zeros((h, w, 3), np.float32)
    n[..., 0] = -np.sin(ang)[None, :]
    n[..., 2] = np.cos(ang)[None, :]
    return n, c0


def _flat_inputs():
    rgb = np.full((48, 48, 3), 120, np.uint8)
    alpha = np.full((48, 48), 255, np.uint8)
    light = np.full((48, 48), 0.5, np.float32)
    return rgb, alpha, light


def test_shades_off_is_baseline():
    # Regression lock: shades default off -> no shade overlay, no shade step.
    n, _ = _vcrease()
    rgb, alpha, light = _flat_inputs()
    res = analyze_regions(rgb, alpha, PAL, COV, [], edges=True,
                          light_field=light, normal_field=n)
    whole = _whole(res)
    assert not any(s.kind == "shade" for s in whole.steps)


def test_shades_on_adds_overlay_and_step():
    n, c0 = _vcrease()
    rgb, alpha, light = _flat_inputs()
    res = analyze_regions(rgb, alpha, PAL, COV, [], edges=True, shades=True,
                          light_field=light, normal_field=n)
    whole = _whole(res)
    # shade overlay is present and prepended (index 0 of edge_overlays)
    shade_mask, shade_col = whole.edge_overlays[0]
    assert shade_mask.sum() > 0
    cols = np.where(shade_mask.any(axis=0))[0]
    assert abs(int(round(cols.mean())) - c0) <= 4
    # shade colour is the darkened base (band 0)
    np.testing.assert_allclose(shade_col, whole.colors[0] * 0.55, rtol=1e-5)
    # exactly one shade step appended
    assert sum(s.kind == "shade" for s in whole.steps) == 1


def test_shades_ignored_without_normals():
    # shades=True but no normal field (Path L) -> no shade overlay/step, no crash.
    rgb, alpha, _ = _flat_inputs()
    res = analyze_regions(rgb, alpha, PAL, COV, [], edges=True, shades=True)
    whole = _whole(res)
    assert not any(s.kind == "shade" for s in whole.steps)
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `.venv/Scripts/python -m pytest tests/test_pipeline_shades.py -v`
Expected: FAIL with `TypeError: analyze_regions() got an unexpected keyword argument 'shades'`.

- [ ] **Step 3: Implement the threading**

In `src/mini_highlight_advisor/pipeline.py`:

(a) Extend the overlay import to add `shade_steps`:

```python
from .overlay import (
    BandStep, compose_panel, edge_steps, paint_preview, paint_regions,
    per_band_images, render_legend, shade_steps,
)
```

(b) Extend the edges import to add `cavity_mask`:

```python
from .edges import (
    edge_mask, extreme_edge_mask, geometric_edge_mask, geometric_extreme_edge_mask,
    cavity_mask,
)
```

(c) Add a module constant near the top (after `WHOLE_MINI = "Whole mini"`):

```python
_SHADE_DARKEN = 0.55   # recess shade = darkest palette paint glazed this much darker
```

(d) Add `shades: bool = False` to the `plan_region` signature (append after `normals`):

```python
def plan_region(rgb, sub_mask, light, name, palette, coverage,
                edges: bool = True, extreme_edge: bool = False,
                edge_sensitivity: float = 0.5,
                relief_cap: bool = False, flat_albedo: bool = False,
                normals: np.ndarray | None = None,
                shades: bool = False) -> RegionPlan:
```

(e) In `plan_region`, immediately **after** the `if edges:` block (after `overlays` is fully built) and **before** the `return RegionPlan(...)`, insert:

```python
    if shades and normals is not None:
        recess = cavity_mask(normals, sub_mask, edge_sensitivity)
        shade_rgb = (colors[0] * _SHADE_DARKEN).astype(np.float32)
        overlays = [(recess, shade_rgb)] + (overlays or [])   # shade under any edges
        steps = steps + shade_steps(rgb, recess, shade_rgb, start_index=len(steps))
```

(f) Add `shades: bool = False` to the `analyze_regions` signature (append after `normal_field`):

```python
def analyze_regions(rgb, alpha, default_palette, coverage=None, regions=None,
                    edges: bool = True, extreme_edge: bool = False,
                    edge_sensitivity: float = 0.5,
                    relief_cap: bool = False,
                    per_region_norm: bool = False,
                    light_field: np.ndarray | None = None,
                    normal_field: np.ndarray | None = None,
                    shades: bool = False) -> MultiRegionResult:
```

(g) Add `shades=shades` to the `ekw` dict in `analyze_regions`:

```python
    ekw = dict(edges=edges, extreme_edge=extreme_edge, edge_sensitivity=edge_sensitivity,
               relief_cap=relief_cap, normals=normal_field, shades=shades)
```

- [ ] **Step 4: Run the new tests plus the pipeline regression tests**

Run: `.venv/Scripts/python -m pytest tests/test_pipeline_shades.py tests/test_pipeline_normal_field.py tests/test_pipeline_light_field.py tests/test_relief_cap_pipeline.py -v`
Expected: PASS (new shade tests pass; existing pipeline tests still pass — Path L byte-identical).

- [ ] **Step 5: Commit**

```bash
git add src/mini_highlight_advisor/pipeline.py tests/test_pipeline_shades.py
git commit -m "feat(pipeline): shades= param — recess overlay + step, gated on normals"
```

---

### Task 4: UI — PS-only "Recess shades" checkbox

**Files:**
- Modify: `ui/keys.py`, `ui/results.py`
- Test: `tests/test_ui_ps_mode.py`

**Interfaces:**
- Consumes: `analyze_regions(..., shades=)` (Task 3), `ui.keys.SHADES`.
- Produces: a `st.checkbox("Recess shades", key=keys.SHADES)` rendered only when `normal_field is not None`, its value threaded as `shades=` into the `analyze_regions` call.

- [ ] **Step 1: Write the failing test**

In `tests/test_ui_ps_mode.py`, add at end of file:

```python
def test_ps_mode_recess_shades_toggle_runs():
    at = AppTest.from_string(HARNESS); at.run()
    assert not at.exception
    # the PS-only recess-shades checkbox is present...
    box = at.checkbox(key="shades")
    assert box is not None
    # ...and toggling it on re-runs the full editor without error.
    box.set_value(True).run()
    assert not at.exception
    assert at.session_state["shades"] is True
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.venv/Scripts/python -m pytest tests/test_ui_ps_mode.py::test_ps_mode_recess_shades_toggle_runs -v`
Expected: FAIL (no widget with key `"shades"` — `KeyError`/lookup error).

- [ ] **Step 3: Add the key and the checkbox**

(a) In `ui/keys.py`, add under the edge keys (after the `PER_REGION_NORM` line):

```python
SHADES = "shades"                # recess shades checkbox (PS mode only)
```

(b) In `ui/results.py`, add the checkbox after the `edge_sensitivity` slider block and before the `relief_cap` checkbox:

```python
    shades = False
    if normal_field is not None:
        shades = st.checkbox(
            "Recess shades", value=False, key=keys.SHADES,
            help="Darken concave recesses (creases, cavities) from the surface "
                 "normals — the inverse of edge highlights. PS mode only; reuses "
                 "the edge-sensitivity slider.")
```

(c) In the `analyze_regions(...)` call in `ui/results.py`, add `shades=shades`:

```python
    multi = analyze_regions(rgb, alpha, wp, wcov, drawn,
                            edges=edges, extreme_edge=extreme_edge,
                            edge_sensitivity=edge_sensitivity,
                            relief_cap=relief_cap,
                            per_region_norm=per_region_norm,
                            light_field=light_field,
                            normal_field=normal_field,
                            shades=shades)
```

- [ ] **Step 4: Run the UI test plus the full PS-mode suite**

Run: `.venv/Scripts/python -m pytest tests/test_ui_ps_mode.py -v`
Expected: PASS (new test passes; existing PS-mode tests still pass).

- [ ] **Step 5: Commit**

```bash
git add ui/keys.py ui/results.py tests/test_ui_ps_mode.py
git commit -m "feat(ui): PS-only Recess shades checkbox wired to shades="
```

---

### Task 5: Full-suite verification

**Files:** none (verification only).

- [ ] **Step 1: Run the full test suite**

Run: `.venv/Scripts/python -m pytest -q`
Expected: all pass except the 2 **pre-existing** `tests/test_ui_gallery.py` failures noted in project memory (unrelated to this slice). If any *other* test fails, stop and investigate before proceeding.

- [ ] **Step 2: Confirm Path-L regression lock explicitly**

Run: `.venv/Scripts/python -m pytest tests/test_pipeline.py tests/test_overlay.py tests/test_edges.py tests/test_edges_geometric.py -q`
Expected: PASS (no drift in the photo-mode / edge paths).

- [ ] **Step 3: Final commit if any doc/cleanup remains**

If nothing else changed, skip. Otherwise:

```bash
git add -A
git commit -m "chore: cavity/AO recess-shades slice cleanup"
```

---

## Self-Review

**1. Spec coverage:**
- `cavity_mask` (concave mirror, honest-empty, light-independent) → Task 1. ✓
- Auto-darkened shade colour `colors[0] * 0.55` → Task 3 (built where `colors` is known). ✓
- Reuse `edge_overlays` compositing (shade prepended, under edges) → Task 3 step (e). ✓
- `shade_steps` mirror emitting `BandStep(kind="shade", label="Recess Shade")` → Task 2. ✓
- `shades=` threading through `analyze_regions`→`plan_region`, gated on `normals is not None` → Task 3. ✓
- Path L byte-identical (default off / no normals) → Task 3 tests + Task 5 regression run. ✓
- PS-only checkbox reusing edge sensitivity → Task 4. ✓
- Testing strategy (crease fixture via self-contained `_vcrease`, light-independence, graceful-empty, regression lock, UI smoke) → Tasks 1–4. ✓
- Non-goals (no AO-depth opacity, no wash slot, no banding/palette change) → nothing in the plan touches them. ✓

**2. Placeholder scan:** No TBD/TODO; every code step shows full code. ✓

**3. Type consistency:** `cavity_mask(normals, mask, sensitivity)->bool(H,W)` used identically in Task 3. `shade_steps(rgb, recess_mask, shade_rgb, alpha, start_index)->list[BandStep]` defined in Task 2, called in Task 3 with `start_index=len(steps)`. `shades` bool param name consistent across `analyze_regions`, `plan_region`, `ekw`, `keys.SHADES="shades"`, and the AppTest `key="shades"`. `_SHADE_DARKEN=0.55` matches the `0.55` asserted in Task 3's test. ✓
