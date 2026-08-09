# Per-band Step-by-Step Images Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Turn the shipped single combined preview into a dark→light sequence of per-paint step images so a painter can follow the highlight plan one layer at a time.

**Architecture:** Purely additive on top of v1. A new `per_band_images` function in `overlay.py` re-renders the existing `bands` partition into one `BandStep` per band (a cumulative "apply across" image + a just-this-band "ends up here" image). `pipeline.analyze` attaches the steps to `HighlightResult`; `app.py` displays them in a new "Paint-along steps" section. No new models, dependencies, or tuning parameters.

**Tech Stack:** Python 3.11, numpy, opencv (`cv2`, already used by `masking.py`), Pillow, Streamlit, pytest.

## Global Constraints

- Package lives under `src/mini_highlight_advisor/`; tests under `tests/`.
- `bands` is an `int` array; off-mask pixels are `-1`; `mask == (bands >= 0)`; band `0` = darkest, band `n-1` = lightest. It is a partition (each masked pixel in exactly one band).
- Paint colors are passed as a list of `np.ndarray` dtype `float32`, shape `(3,)`, RGB.
- Reuse the existing dim factor (`0.25`) and default overlay alpha (`0.78`) from `paint_preview` — do not introduce new magic constants for these.
- No new pip dependencies.

---

### Task 1: `per_band_images` + `BandStep` in overlay.py

**Files:**
- Modify: `src/mini_highlight_advisor/overlay.py`
- Test: `tests/test_overlay.py`

**Interfaces:**
- Consumes: `bands: np.ndarray (int)`, `mask: np.ndarray (bool)`, `rgb: np.ndarray uint8 (H,W,3)`, `colors: list[np.ndarray float32 (3,)]`.
- Produces:
  - `@dataclass BandStep` with fields `index: int`, `cumulative_rgb: np.ndarray`, `exact_rgb: np.ndarray | None`, `is_last: bool`.
  - `per_band_images(rgb, bands, mask, colors, alpha: float = 0.78) -> list[BandStep]` — returns exactly `len(colors)` steps, index `0..n-1` in dark→light order. For step `k`: `cumulative_rgb` active region is `(bands >= k) & mask`; `exact_rgb` active region is `(bands == k) & mask`; the last step (`k == n-1`) has `exact_rgb is None` and `is_last True`.

- [ ] **Step 1: Write the failing tests**

Add to `tests/test_overlay.py`:

```python
from mini_highlight_advisor.overlay import per_band_images, BandStep


def _fixture():
    # 4x4 with an off-mask row (-1); bands 0 (dark) .. 2 (light)
    bands = np.array(
        [[0, 0, 1, 2],
         [0, 0, 1, 2],
         [-1, -1, -1, -1],
         [0, 1, 1, 2]],
        dtype=np.int32,
    )
    mask = bands >= 0
    rgb = np.full((4, 4, 3), 100, dtype=np.uint8)
    colors = [
        np.array([255, 0, 0], np.float32),   # band 0
        np.array([0, 255, 0], np.float32),   # band 1
        np.array([0, 0, 255], np.float32),   # band 2
    ]
    return rgb, bands, mask, colors


def _painted_region(out, color):
    # with alpha=1.0 active pixels equal the paint color exactly
    return np.all(out == color.astype(np.uint8), axis=-1)


def test_per_band_images_returns_one_step_per_color_in_order():
    rgb, bands, mask, colors = _fixture()
    steps = per_band_images(rgb, bands, mask, colors, alpha=1.0)
    assert len(steps) == 3
    assert [s.index for s in steps] == [0, 1, 2]
    assert all(isinstance(s, BandStep) for s in steps)


def test_step0_cumulative_covers_full_mask():
    rgb, bands, mask, colors = _fixture()
    steps = per_band_images(rgb, bands, mask, colors, alpha=1.0)
    painted = _painted_region(steps[0].cumulative_rgb, colors[0])
    assert np.array_equal(painted, mask)


def test_exact_region_equals_band_equals_k():
    rgb, bands, mask, colors = _fixture()
    steps = per_band_images(rgb, bands, mask, colors, alpha=1.0)
    for k in (0, 1):  # last step has no exact image
        painted = _painted_region(steps[k].exact_rgb, colors[k])
        assert np.array_equal(painted, (bands == k) & mask)


def test_cumulative_regions_are_nested_and_shrinking():
    rgb, bands, mask, colors = _fixture()
    steps = per_band_images(rgb, bands, mask, colors, alpha=1.0)
    prev = None
    for k, s in enumerate(steps):
        region = _painted_region(s.cumulative_rgb, colors[k])
        assert np.array_equal(region, (bands >= k) & mask)
        if prev is not None:
            # region(k) subset of region(k-1)
            assert np.all(prev[region])
        prev = region


def test_last_step_has_no_exact_image():
    rgb, bands, mask, colors = _fixture()
    steps = per_band_images(rgb, bands, mask, colors, alpha=1.0)
    assert steps[-1].is_last is True
    assert steps[-1].exact_rgb is None
    assert all(s.is_last is False for s in steps[:-1])
    assert all(s.exact_rgb is not None for s in steps[:-1])


def test_nonactive_interior_pixel_is_dimmed():
    rgb, bands, mask, colors = _fixture()
    steps = per_band_images(rgb, bands, mask, colors, alpha=1.0)
    # pixel (0,0) is band 0: non-active in the last step (band 2) and not
    # adjacent to any band-2 pixel, so it is neither painted nor on the outline.
    out = steps[2].cumulative_rgb
    assert out[0, 0].sum() < rgb[0, 0].sum()


def test_output_shape_and_dtype_match_input():
    rgb, bands, mask, colors = _fixture()
    steps = per_band_images(rgb, bands, mask, colors, alpha=1.0)
    assert steps[0].cumulative_rgb.shape == rgb.shape
    assert steps[0].cumulative_rgb.dtype == np.uint8
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `.venv\Scripts\python -m pytest tests/test_overlay.py -k per_band -v`
Expected: FAIL — `ImportError: cannot import name 'per_band_images'`.

- [ ] **Step 3: Write the minimal implementation**

Add to `src/mini_highlight_advisor/overlay.py` (imports `cv2` and `dataclass` at top):

```python
from dataclasses import dataclass

import cv2

_DIM = 0.25
_OUTLINE = np.array([255, 255, 255], np.float32)


@dataclass
class BandStep:
    index: int
    cumulative_rgb: np.ndarray
    exact_rgb: np.ndarray | None
    is_last: bool


def _outline_ring(active_mask: np.ndarray) -> np.ndarray:
    a = active_mask.astype(np.uint8)
    dil = cv2.dilate(a, np.ones((3, 3), np.uint8), iterations=1)
    return (dil > 0) & (~active_mask)


def _render_step(rgb, active_mask, color, alpha) -> np.ndarray:
    base = rgb.astype(np.float32)
    out = base.copy()
    out[~active_mask] = out[~active_mask] * _DIM
    out[active_mask] = (1 - alpha) * base[active_mask] + alpha * color
    out[_outline_ring(active_mask)] = _OUTLINE
    return np.clip(out, 0, 255).astype(np.uint8)


def per_band_images(rgb, bands, mask, colors, alpha: float = 0.78) -> list[BandStep]:
    n = len(colors)
    steps: list[BandStep] = []
    for k, color in enumerate(colors):
        is_last = k == n - 1
        cumulative = _render_step(rgb, (bands >= k) & mask, color, alpha)
        exact = None if is_last else _render_step(rgb, (bands == k) & mask, color, alpha)
        steps.append(BandStep(index=k, cumulative_rgb=cumulative, exact_rgb=exact, is_last=is_last))
    return steps
```

- [ ] **Step 4: Run the tests to verify they pass**

Run: `.venv\Scripts\python -m pytest tests/test_overlay.py -v`
Expected: PASS (new `per_band` tests plus the 3 pre-existing overlay tests).

- [ ] **Step 5: Commit**

```bash
git add src/mini_highlight_advisor/overlay.py tests/test_overlay.py
git commit -m "feat: per-band step images (cumulative + exact) in overlay"
```

---

### Task 2: Attach `steps` to `HighlightResult` in the pipeline

**Files:**
- Modify: `src/mini_highlight_advisor/pipeline.py`
- Test: `tests/test_pipeline.py` (add a test; file already exists from v1)

**Interfaces:**
- Consumes: `per_band_images` and `BandStep` from Task 1.
- Produces: `HighlightResult.steps: list[BandStep]`, length `== len(palette)`, populated by `analyze`.

- [ ] **Step 1: Write the failing test**

Add to `tests/test_pipeline.py`:

```python
def test_analyze_populates_per_band_steps():
    import numpy as np
    from mini_highlight_advisor.palette import PaintColor
    from mini_highlight_advisor.pipeline import analyze

    rgb = np.random.default_rng(0).integers(0, 255, (32, 32, 3), dtype=np.uint8)
    alpha = np.full((32, 32), 255, dtype=np.uint8)  # full-model alpha, fast path
    palette = [PaintColor("A", "#202020"), PaintColor("B", "#808080"), PaintColor("C", "#f0f0f0")]

    result = analyze(rgb, alpha, palette)

    assert len(result.steps) == len(palette)
    assert result.steps[-1].is_last is True
    assert result.steps[-1].exact_rgb is None
    assert result.steps[0].cumulative_rgb.shape == rgb.shape
```

- [ ] **Step 2: Run the test to verify it fails**

Run: `.venv\Scripts\python -m pytest tests/test_pipeline.py::test_analyze_populates_per_band_steps -v`
Expected: FAIL — `AttributeError: 'HighlightResult' object has no attribute 'steps'`.

- [ ] **Step 3: Implement**

In `src/mini_highlight_advisor/pipeline.py`:

1. Extend the import: `from .overlay import BandStep, compose_panel, paint_preview, per_band_images, render_legend`
2. Add the field to the dataclass (after `panel`):

```python
    steps: list[BandStep]
```

3. In `analyze`, after `panel = compose_panel(...)` and before the `return`:

```python
    steps = per_band_images(rgb, bands, mask, colors)
```

4. Add `steps` to the constructor call:

```python
    return HighlightResult(mask, light, bands, coverage, roles, preview_rgb, panel, steps)
```

- [ ] **Step 4: Run the tests to verify they pass**

Run: `.venv\Scripts\python -m pytest tests/test_pipeline.py -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add src/mini_highlight_advisor/pipeline.py tests/test_pipeline.py
git commit -m "feat: expose per-band steps on HighlightResult"
```

---

### Task 3: "Paint-along steps" section in the app

**Files:**
- Modify: `app.py`

**Interfaces:**
- Consumes: `result.steps` (list of `BandStep`), `result.roles`, `result.coverage`, and the sidebar `palette` (each `PaintColor` has `.name`).

No automated test — Streamlit UI. Verified by a manual browser smoke test (deferred to the user, per project convention).

- [ ] **Step 1: Add the section to `app.py`**

After the existing layer-guide loop (the `for role, paint, cov in zip(...)` block), add:

```python
    st.subheader("Paint-along steps")
    st.caption("Work dark to light. 'Apply across' = paint this color over the whole area; "
               "'Ends up here' = the slice that stays this color after you highlight over it.")
    for step, role, paint, cov in zip(result.steps, result.roles, palette, result.coverage):
        st.markdown(f"**Step {step.index + 1} — {role} · {paint.name}**  ·  ~{cov:.0f}% of the model")
        if step.is_last:
            st.image(step.cumulative_rgb, caption="Apply across", use_container_width=True)
        else:
            c1, c2 = st.columns(2)
            c1.image(step.cumulative_rgb, caption="Apply across", use_container_width=True)
            c2.image(step.exact_rgb, caption="Ends up here", use_container_width=True)
```

- [ ] **Step 2: Manual smoke test (user-run)**

Run: `.venv\Scripts\streamlit run app.py`
Expected: after uploading a primed-mini photo, a "Paint-along steps" section appears below the panel with one row per layer, two images per row (single image for the final layer), dimmed background + colored active zone + thin outline.

- [ ] **Step 3: Commit**

```bash
git add app.py
git commit -m "feat: paint-along step images section in Streamlit app"
```

---

## Self-Review Notes

- **Spec coverage:** rendering (paint-color fill + dim `0.25` + outline ring) → Task 1 `_render_step`; cumulative vs exact pair → Task 1 `per_band_images`; last-step single image → Task 1 `is_last`/`exact_rgb None` + Task 3 branch; pipeline `steps` field → Task 2; app section → Task 3; all seven spec tests → Task 1 Step 1. Deferred items (PDF, downloads, brightened-photo toggle, recess sub-threshold) correctly absent.
- **Placeholder scan:** none — all steps carry real code.
- **Type consistency:** `per_band_images`/`BandStep`/field names (`cumulative_rgb`, `exact_rgb`, `is_last`, `index`) are identical across Tasks 1–3; `HighlightResult` constructor arg order matches the v1 field order with `steps` appended last.
