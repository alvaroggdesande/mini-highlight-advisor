# Manual Region Lasso Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Let a painter lasso multiple regions on a mini, give each its own palette + band settings, and render them combined into one plan plus a descriptive swatch board — with zero regions behaving exactly like today.

**Architecture:** A new `regions.py` holds the `Region` dataclass, exclusive last-wins pixel assignment, and lasso-path→mask rasterisation. `pipeline.py` gains `analyze_regions`, which bands each region *within its own sub-mask* (luminance still places the highlights) and composites a combined preview. `overlay.py` gains `paint_regions` (composite) and `swatch_board` (descriptive panel). `app.py` snapshots the current global palette + a drawn lasso into a region. A spike gates the drawing component choice.

**Tech Stack:** Python 3.11, numpy, Pillow, OpenCV, Streamlit, `streamlit-drawable-canvas` (pending spike; `streamlit-image-coordinates` fallback), pytest.

## Global Constraints

- **Primed / monochrome minis only** — luminance is the shading signal (copied from spec/CLAUDE.md).
- **Tool stays OFFLINE / FREE, zero LLM** — no API calls anywhere in this feature.
- **Zero-region output must be byte-identical to today's single-palette path** (region model C).
- **The lasso assigns *which paints* apply; it does NOT place highlights** — each band is the brightest-quantile of luminance *within* a region's sub-mask.
- **Pixel assignment is exclusive and last-wins** — later region in list order owns overlaps; no feathering in v1.
- **Never build on `main`.** Work on `feat/manual-region-lasso`; feature branch + PR.
- **Env:** `.venv` (py 3.11). Tests: `.venv/Scripts/python -m pytest`. App: `streamlit run app.py`.
- Paint colours are `np.ndarray` float32 shape `(3,)`, RGB. `bands`: int array, `-1` off-mask, band `0` = darkest.

---

### Task 1: Spike — drawing-component compatibility gate

Decide whether `streamlit-drawable-canvas` works on the repo's pinned Streamlit. This gates only the **UI** (Task 7); core Tasks 2–6 are identical either way, so they can proceed in parallel.

**Files:**
- Create: `spikes/canvas_spike.py`
- Modify: `requirements.txt`

- [ ] **Step 1: Add the dependency**

Append to `requirements.txt`:

```
streamlit-drawable-canvas
```

- [ ] **Step 2: Install it into the venv**

Run: `.venv/Scripts/python -m pip install streamlit-drawable-canvas`
Expected: installs, or surfaces a hard version conflict with the pinned `streamlit`.

- [ ] **Step 3: Write the spike app**

```python
# spikes/canvas_spike.py
"""Spike: does streamlit-drawable-canvas run on this repo's Streamlit?
Run: streamlit run spikes/canvas_spike.py
PASS if: the canvas renders, freehand drawing works, and json_data returns
objects with a 'path' (freehand) or 'points'/'path' (polygon) we can read.
"""
import numpy as np
import streamlit as st
from PIL import Image

st.title("drawable-canvas spike")
try:
    from streamlit_drawable_canvas import st_canvas
except Exception as e:  # import/version failure = spike FAIL -> use fallback
    st.error(f"import failed: {e!r}")
    st.stop()

bg = Image.fromarray(np.full((300, 300, 3), 120, np.uint8))
res = st_canvas(
    fill_color="rgba(255,0,200,0.3)", stroke_width=2, stroke_color="#ff28c8",
    background_image=bg, height=300, width=300, drawing_mode="freedraw",
    key="spike",
)
if res.json_data is not None:
    objs = res.json_data.get("objects", [])
    st.write(f"objects: {len(objs)}")
    if objs:
        st.json(objs[-1])  # inspect the path/points shape we must parse in Task 7
```

- [ ] **Step 4: Run it and record the verdict**

Run: `streamlit run spikes/canvas_spike.py` and draw a shape.
Record in `spikes/README.md` (one line): PASS (canvas + path readable) or FAIL (+ reason).
- **PASS** → Task 7 uses `st_canvas`; note the exact JSON key holding the point list.
- **FAIL** → remove the dep from `requirements.txt`, add `streamlit-image-coordinates` instead, and Task 7 uses polygon-by-click. Downstream Tasks 2–6 are unaffected.

- [ ] **Step 5: Commit**

```bash
git add spikes/canvas_spike.py spikes/README.md requirements.txt
git commit -m "spike: drawable-canvas compatibility gate for region lasso"
```

---

### Task 2: `Region` dataclass + exclusive last-wins assignment

**Files:**
- Create: `src/mini_highlight_advisor/regions.py`
- Test: `tests/test_regions.py`

**Interfaces:**
- Consumes: `PaintColor` from `palette.py`.
- Produces:
  - `Region(name: str, mask: np.ndarray, palette: list[PaintColor], coverage: list[float])` — `mask` is a source-resolution bool array; `len(coverage) == len(palette)`.
  - `assign_owners(base_mask: np.ndarray, region_masks: list[np.ndarray]) -> np.ndarray` — int32 array: `-2` = off `base_mask`, `-1` = default region (on-mask, unowned), `i` = owned by `region_masks[i]` (last index wins on overlap).

- [ ] **Step 1: Write the failing test**

```python
# tests/test_regions.py
import numpy as np
from mini_highlight_advisor.regions import Region, assign_owners
from mini_highlight_advisor.palette import PaintColor


def test_assign_owners_last_wins_on_overlap():
    base = np.ones((4, 4), bool)
    a = np.zeros((4, 4), bool); a[:, :3] = True   # cols 0,1,2
    b = np.zeros((4, 4), bool); b[:, 1:] = True    # cols 1,2,3 (overlaps 1,2)
    owner = assign_owners(base, [a, b])
    assert owner[0, 0] == 0    # only a
    assert owner[0, 1] == 1    # overlap -> b (last wins)
    assert owner[0, 3] == 1    # only b


def test_assign_owners_offmask_and_default():
    base = np.ones((2, 2), bool); base[0, 0] = False
    owner = assign_owners(base, [])
    assert owner[0, 0] == -2   # off base mask
    assert owner[1, 1] == -1   # on-mask, unowned -> default


def test_region_is_constructible():
    r = Region("Robe", np.ones((2, 2), bool), [PaintColor("A", "#101010")], [1.0])
    assert r.name == "Robe" and len(r.palette) == len(r.coverage)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.venv/Scripts/python -m pytest tests/test_regions.py -v`
Expected: FAIL — `ModuleNotFoundError: mini_highlight_advisor.regions`.

- [ ] **Step 3: Write minimal implementation**

```python
# src/mini_highlight_advisor/regions.py
from __future__ import annotations

from dataclasses import dataclass

import numpy as np

from .palette import PaintColor


@dataclass
class Region:
    name: str
    mask: np.ndarray                 # source-resolution bool
    palette: list[PaintColor]
    coverage: list[float]            # len == len(palette), sums to ~1.0


def assign_owners(base_mask: np.ndarray, region_masks: list[np.ndarray]) -> np.ndarray:
    owner = np.full(base_mask.shape, -1, dtype=np.int32)
    for i, rm in enumerate(region_masks):
        owner[rm & base_mask] = i        # later i overwrites -> last-wins
    owner[~base_mask] = -2
    return owner
```

- [ ] **Step 4: Run test to verify it passes**

Run: `.venv/Scripts/python -m pytest tests/test_regions.py -v`
Expected: PASS (3 tests).

- [ ] **Step 5: Commit**

```bash
git add src/mini_highlight_advisor/regions.py tests/test_regions.py
git commit -m "feat: Region dataclass + exclusive last-wins owner assignment"
```

---

### Task 3: Lasso-path → mask rasterisation + display→source scaling

**Files:**
- Modify: `src/mini_highlight_advisor/regions.py`
- Test: `tests/test_regions.py`

**Interfaces:**
- Produces:
  - `scale_points(points: list[tuple[float, float]], sx: float, sy: float) -> list[tuple[float, float]]`
  - `polygon_to_mask(points: list[tuple[float, float]], shape: tuple[int, int]) -> np.ndarray` — `shape` is `(H, W)`; returns filled-interior bool array.

- [ ] **Step 1: Write the failing test**

```python
# add to tests/test_regions.py
from mini_highlight_advisor.regions import scale_points, polygon_to_mask


def test_scale_points_scales_each_axis_independently():
    assert scale_points([(2.0, 3.0)], 2.0, 0.5) == [(4.0, 1.5)]


def test_polygon_to_mask_fills_interior_not_exterior():
    square = [(1, 1), (1, 4), (4, 4), (4, 1)]
    m = polygon_to_mask(square, (6, 6))
    assert m.dtype == bool
    assert m.shape == (6, 6)
    assert m[2, 2]            # inside
    assert not m[0, 0]       # outside
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.venv/Scripts/python -m pytest tests/test_regions.py -k "scale_points or polygon" -v`
Expected: FAIL — `ImportError: cannot import name 'scale_points'`.

- [ ] **Step 3: Write minimal implementation**

Add to `src/mini_highlight_advisor/regions.py` (add `from PIL import Image, ImageDraw` to the imports):

```python
def scale_points(points, sx: float, sy: float):
    return [(x * sx, y * sy) for x, y in points]


def polygon_to_mask(points, shape) -> np.ndarray:
    h, w = shape
    img = Image.new("L", (w, h), 0)
    if len(points) >= 3:
        ImageDraw.Draw(img).polygon([(float(x), float(y)) for x, y in points], fill=1)
    return np.array(img, dtype=bool)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `.venv/Scripts/python -m pytest tests/test_regions.py -v`
Expected: PASS (5 tests total).

- [ ] **Step 5: Commit**

```bash
git add src/mini_highlight_advisor/regions.py tests/test_regions.py
git commit -m "feat: lasso path -> mask rasterisation + display/source scaling"
```

---

### Task 4: `paint_regions` composite renderer

Built before the pipeline task because `analyze_regions` calls it. Duck-typed on `.sub_mask / .bands / .colors` to avoid importing `pipeline` (which imports `overlay` — circular).

**Files:**
- Modify: `src/mini_highlight_advisor/overlay.py`
- Test: `tests/test_overlay.py`

**Interfaces:**
- Consumes: existing `_DIM` constant in `overlay.py`.
- Produces: `paint_regions(rgb: np.ndarray, plans, alpha: float = 0.78) -> np.ndarray` — `plans` is any sequence of objects with `.sub_mask` (bool), `.bands` (int array), `.colors` (list of float32 `(3,)`). Off-all-region pixels are dimmed by `_DIM`; each region's bands are painted in its sub-mask.

- [ ] **Step 1: Write the failing test**

```python
# add to tests/test_overlay.py
import numpy as np
from types import SimpleNamespace
from mini_highlight_advisor.overlay import paint_regions


def test_paint_regions_composites_each_region_in_its_submask():
    rgb = np.full((4, 4, 3), 100, np.uint8)
    left = np.zeros((4, 4), bool); left[:, :2] = True
    right = np.zeros((4, 4), bool); right[:, 2:] = True
    p_left = SimpleNamespace(sub_mask=left, bands=np.zeros((4, 4), int),
                             colors=[np.array([255, 0, 0], np.float32)])
    p_right = SimpleNamespace(sub_mask=right, bands=np.zeros((4, 4), int),
                              colors=[np.array([0, 0, 255], np.float32)])
    out = paint_regions(rgb, [p_left, p_right])
    assert out.shape == rgb.shape and out.dtype == np.uint8
    assert out[0, 0, 0] > out[0, 0, 2]   # left pixel is reddish
    assert out[0, 3, 2] > out[0, 3, 0]   # right pixel is bluish
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.venv/Scripts/python -m pytest tests/test_overlay.py -k paint_regions -v`
Expected: FAIL — `ImportError: cannot import name 'paint_regions'`.

- [ ] **Step 3: Write minimal implementation**

Add to `src/mini_highlight_advisor/overlay.py`:

```python
def paint_regions(rgb, plans, alpha: float = 0.78) -> np.ndarray:
    base = rgb.astype(np.float32)
    out = base.copy()
    union = np.zeros(rgb.shape[:2], bool)
    for p in plans:
        union |= p.sub_mask
    out[~union] = out[~union] * _DIM
    for p in plans:
        for b, color in enumerate(p.colors):
            m = (p.bands == b) & p.sub_mask
            out[m] = (1 - alpha) * base[m] + alpha * color
    return np.clip(out, 0, 255).astype(np.uint8)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `.venv/Scripts/python -m pytest tests/test_overlay.py -k paint_regions -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add src/mini_highlight_advisor/overlay.py tests/test_overlay.py
git commit -m "feat: paint_regions composite renderer (last-wins per-region)"
```

---

### Task 5: `swatch_board` descriptive panel

**Files:**
- Modify: `src/mini_highlight_advisor/overlay.py`
- Test: `tests/test_overlay.py`

**Interfaces:**
- Consumes: existing `_font` helper in `overlay.py`.
- Produces: `swatch_board(regions: list[tuple[str, list[np.ndarray]]], width: int = 460) -> Image.Image` — one row per region: its name + its palette swatches (dark→light). Pure display; no harmony logic (structured so a readout is an additive pass later).

- [ ] **Step 1: Write the failing test**

```python
# add to tests/test_overlay.py
from PIL import Image
from mini_highlight_advisor.overlay import swatch_board


def test_swatch_board_returns_image_and_grows_with_rows():
    regs = [("Robe", [np.array([200, 0, 0], np.float32)]),
            ("Blade", [np.array([50, 50, 50], np.float32),
                       np.array([210, 210, 210], np.float32)])]
    img = swatch_board(regs)
    assert isinstance(img, Image.Image)
    assert img.width > 0 and img.height > 0
    assert swatch_board(regs).height > swatch_board(regs[:1]).height
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.venv/Scripts/python -m pytest tests/test_overlay.py -k swatch_board -v`
Expected: FAIL — `ImportError: cannot import name 'swatch_board'`.

- [ ] **Step 3: Write minimal implementation**

Add to `src/mini_highlight_advisor/overlay.py`:

```python
def swatch_board(regions, width: int = 460, sw: int = 44, pad: int = 12) -> Image.Image:
    row_h = sw + pad + 24
    height = max(1, pad + len(regions) * row_h)
    img = Image.new("RGB", (width, height), (26, 27, 32))
    d = ImageDraw.Draw(img)
    name_f = _font(20)
    for r, (name, colors) in enumerate(regions):
        y = pad + r * row_h
        d.text((pad, y), name, font=name_f, fill=(235, 236, 240))
        x, yy = pad, y + 26
        for c in colors:
            fill = tuple(int(v) for v in c)
            d.rectangle([x, yy, x + sw, yy + sw], fill=fill, outline=(70, 72, 80), width=2)
            x += sw + 6
    return img
```

- [ ] **Step 4: Run test to verify it passes**

Run: `.venv/Scripts/python -m pytest tests/test_overlay.py -k swatch_board -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add src/mini_highlight_advisor/overlay.py tests/test_overlay.py
git commit -m "feat: swatch_board descriptive per-region palette panel"
```

---

### Task 6: `analyze_regions` pipeline + `RegionPlan` / `MultiRegionResult`

**Files:**
- Modify: `src/mini_highlight_advisor/pipeline.py`
- Test: `tests/test_pipeline.py`

**Interfaces:**
- Consumes: `prepare_shading`, `band_light`, `per_band_images`, `role_names`, `coverage_pct`, `default_coverage` (all already imported in `pipeline.py`); `assign_owners` + `Region` from `regions.py`; `paint_regions` from `overlay.py`.
- Produces:
  - `RegionPlan(name, sub_mask, bands, colors, names, roles, coverage, steps)` — per-region result; `steps` is `list[BandStep]`.
  - `plan_region(rgb, sub_mask, light, name, palette, coverage) -> RegionPlan`.
  - `MultiRegionResult(mask, light, plans, combined_rgb)` — `plans` = default region first (only if it has pixels), then user regions in list order; `combined_rgb` is the composited preview.
  - `analyze_regions(rgb, alpha, default_palette, coverage=None, regions=None) -> MultiRegionResult`.

- [ ] **Step 1: Write the failing test**

```python
# add to tests/test_pipeline.py
from mini_highlight_advisor.pipeline import analyze_regions, MultiRegionResult
from mini_highlight_advisor.regions import Region
from mini_highlight_advisor.palette import default_coverage as _dc

_PAL3 = [PaintColor("A", "#202020"), PaintColor("B", "#808080"), PaintColor("C", "#f0f0f0")]


def test_analyze_regions_zero_regions_matches_single_palette_path():
    rgb = np.random.default_rng(0).integers(0, 255, (32, 32, 3), dtype=np.uint8)
    alpha = np.full((32, 32), 255, dtype=np.uint8)
    baseline = analyze(rgb, alpha, _PAL3)
    result = analyze_regions(rgb, alpha, _PAL3, None, [])
    assert isinstance(result, MultiRegionResult)
    assert len(result.plans) == 1                      # default region only
    assert np.array_equal(result.plans[0].bands, baseline.bands)
    assert result.plans[0].coverage == baseline.coverage


def test_analyze_regions_partitions_pixels_exclusively():
    rgb = np.random.default_rng(2).integers(0, 255, (20, 20, 3), dtype=np.uint8)
    alpha = np.full((20, 20), 255, dtype=np.uint8)
    left = np.zeros((20, 20), bool); left[:, :10] = True
    region = Region("Left", left, _PAL3, _dc(3))
    result = analyze_regions(rgb, alpha, _PAL3, None, [region])
    # Default (right half) + one user region (left half)
    assert len(result.plans) == 2
    subs = [p.sub_mask for p in result.plans]
    assert not (subs[0] & subs[1]).any()               # disjoint
    union = subs[0] | subs[1]
    assert np.array_equal(union, result.mask)          # covers exactly the mini
    assert result.combined_rgb.shape == rgb.shape


def test_analyze_regions_bands_within_submask_only():
    rgb = np.random.default_rng(3).integers(0, 255, (16, 16, 3), dtype=np.uint8)
    alpha = np.full((16, 16), 255, dtype=np.uint8)
    top = np.zeros((16, 16), bool); top[:8, :] = True
    region = Region("Top", top, _PAL3, _dc(3))
    result = analyze_regions(rgb, alpha, _PAL3, None, [region])
    for p in result.plans:
        # Off the region's sub-mask, bands are -1 (never assigned outside it).
        assert (p.bands[~p.sub_mask] == -1).all()
        assert set(np.unique(p.bands[p.sub_mask])) <= set(range(3))
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.venv/Scripts/python -m pytest tests/test_pipeline.py -k analyze_regions -v`
Expected: FAIL — `ImportError: cannot import name 'analyze_regions'`.

- [ ] **Step 3: Write minimal implementation**

Add to `src/mini_highlight_advisor/pipeline.py`. Extend the existing import lines:

```python
from .overlay import (
    BandStep, compose_panel, paint_preview, paint_regions, per_band_images, render_legend,
)
from .palette import PaintColor, coverage_pct, default_coverage, role_names
from .regions import Region, assign_owners
```

Then append:

```python
@dataclass
class RegionPlan:
    name: str
    sub_mask: np.ndarray
    bands: np.ndarray
    colors: list[np.ndarray]
    names: list[str]
    roles: list[str]
    coverage: list[float]
    steps: list[BandStep]


@dataclass
class MultiRegionResult:
    mask: np.ndarray
    light: np.ndarray
    plans: list[RegionPlan]
    combined_rgb: np.ndarray


def plan_region(rgb, sub_mask, light, name, palette, coverage) -> RegionPlan:
    colors = [p.rgb for p in palette]
    names = [p.name for p in palette]
    roles = role_names(len(palette))
    bands = band_light(light, sub_mask, coverage)
    cov = coverage_pct(bands, sub_mask, len(palette))
    steps = per_band_images(rgb, bands, sub_mask, colors)
    return RegionPlan(name, sub_mask, bands, colors, names, roles, cov, steps)


def analyze_regions(rgb, alpha, default_palette, coverage=None, regions=None) -> MultiRegionResult:
    regions = regions or []
    if coverage is None:
        coverage = default_coverage(len(default_palette))
    shading = prepare_shading(rgb, alpha)
    mask, light = shading.mask, shading.light
    owner = assign_owners(mask, [r.mask for r in regions])
    plans: list[RegionPlan] = []
    default_sub = owner == -1
    if default_sub.any():
        plans.append(plan_region(rgb, default_sub, light, "Default", default_palette, coverage))
    for i, r in enumerate(regions):
        sub = owner == i
        if not sub.any():
            continue
        plans.append(plan_region(rgb, sub, light, r.name, r.palette, r.coverage))
    combined = paint_regions(rgb, plans)
    return MultiRegionResult(mask, light, plans, combined)
```

- [ ] **Step 4: Run the full suite**

Run: `.venv/Scripts/python -m pytest tests/test_pipeline.py tests/test_regions.py tests/test_overlay.py -v`
Expected: PASS (all new + existing pipeline/overlay/regions tests green — the zero-region test guards model C).

- [ ] **Step 5: Commit**

```bash
git add src/mini_highlight_advisor/pipeline.py tests/test_pipeline.py
git commit -m "feat: analyze_regions per-region banding + combined composite"
```

---

### Task 7: Wire the region UI into `app.py`

Manual-tested (Streamlit UI). Uses the Task-1 verdict for the drawing widget. The design keeps it simple: the existing global palette editor **is** the default palette; **"Add region"** snapshots the *current* palette + coverage + the drawn lasso into a `Region`. Zero regions → the existing `band_and_render` path runs untouched.

**Files:**
- Modify: `app.py`

**Interfaces:**
- Consumes: `analyze_regions`, `MultiRegionResult` from `pipeline.py`; `Region`, `scale_points`, `polygon_to_mask` from `regions.py`; `swatch_board` from `overlay.py`; existing `prepare_shading`, `band_and_render`, and the already-built `palette` + `coverage` locals in the Miniature tab.

- [ ] **Step 1: Import the new symbols**

In `app.py`, extend the pipeline import and add the regions/overlay imports:

```python
from mini_highlight_advisor.pipeline import prepare_shading, band_and_render, analyze_regions
from mini_highlight_advisor.regions import Region, scale_points, polygon_to_mask
from mini_highlight_advisor.overlay import swatch_board
```

If Task 1 was **PASS**: `from streamlit_drawable_canvas import st_canvas`.
If Task 1 was **FAIL**: `from streamlit_image_coordinates import streamlit_image_coordinates` and collect polygon vertices in `st.session_state` on each click instead of a freehand path.

- [ ] **Step 2: Initialise region state**

Near the top of the `with tab_mini:` block, after the palette/coverage are built:

```python
st.session_state.setdefault("regions", [])   # list[Region]
```

- [ ] **Step 3: Draw the canvas + "Add region" (PASS path)**

Inside the `if uploaded is not None:` block, *after* `_shading(...)` returns `rgb, alpha, shading`, before rendering. Render the mini at a fixed display width and compute the scale back to source pixels:

```python
src_h, src_w = rgb.shape[:2]
disp_w = min(500, src_w)
disp_h = round(src_h * disp_w / src_w)
st.markdown("#### Regions (optional)")
st.caption("Draw a lasso, name it, then 'Add region' to snapshot the current "
           "palette + coverage for that area. Draw nothing to keep the single-palette plan.")
canvas = st_canvas(
    fill_color="rgba(255,40,200,0.25)", stroke_width=2, stroke_color="#ff28c8",
    background_image=Image.fromarray(rgb), height=disp_h, width=disp_w,
    drawing_mode="polygon", key=f"canvas_{len(st.session_state['regions'])}",
)
region_name = st.text_input("Region name", value=f"Region {len(st.session_state['regions']) + 1}")
if st.button("Add region"):
    objs = (canvas.json_data or {}).get("objects", [])
    if objs:
        pts = _points_from_object(objs[-1])          # see Step 4
        sx, sy = src_w / disp_w, src_h / disp_h
        rmask = polygon_to_mask(scale_points(pts, sx, sy), (src_h, src_w)) & shading.mask
        if rmask.any():
            st.session_state["regions"].append(
                Region(region_name.strip() or f"Region {len(st.session_state['regions']) + 1}",
                       rmask, list(palette), list(coverage)))
            st.rerun()
        else:
            st.warning("Lasso didn't overlap the mini — try again.")
    else:
        st.warning("Draw a lasso first.")
```

`Image` is already imported? It is not — add `from PIL import Image` to the top of `app.py`.

- [ ] **Step 4: Add the canvas-object point parser**

Add a module-level helper in `app.py`. The exact key comes from the Task-1 spike's `st.json(objs[-1])` output; polygon objects expose their vertices as a `path`/`points` list. Implement against what the spike showed, e.g.:

```python
def _points_from_object(obj) -> list[tuple[float, float]]:
    # Polygon mode: vertices live in obj["path"] as [["M",x,y],["L",x,y],...] OR
    # obj["points"] as [{"x":..,"y":..}] depending on component version (confirmed in spike).
    if "points" in obj:
        return [(p["x"], p["y"]) for p in obj["points"]]
    return [(seg[1], seg[2]) for seg in obj["path"] if len(seg) >= 3]
```

(FAIL/fallback path: return the list of clicked vertices accumulated in `st.session_state` instead.)

- [ ] **Step 5: Show the region list with remove buttons**

```python
if st.session_state["regions"]:
    st.markdown("**Regions added**")
    for idx, r in enumerate(st.session_state["regions"]):
        cols = st.columns([4, 1])
        cols[0].write(f"{idx + 1}. {r.name} — {len(r.palette)} layers, {int(r.mask.sum())} px")
        if cols[1].button("Remove", key=f"rm_{idx}"):
            st.session_state["regions"].pop(idx)
            st.rerun()
```

- [ ] **Step 6: Branch the render — combined vs single**

Replace the existing single-render block (`result = band_and_render(...)` and everything that displays it) so that when regions exist we render the multi-region result:

```python
regions = st.session_state["regions"]
if regions:
    multi = analyze_regions(rgb, alpha, palette, coverage, regions)
    st.image(multi.combined_rgb, caption="Combined painted preview (all regions)",
             use_container_width=True)
    st.subheader("Colour schemes — all regions")
    st.image(swatch_board([(p.name, p.colors) for p in multi.plans]),
             use_container_width=False)
    st.subheader("Paint-along steps by region")
    for plan in multi.plans:
        st.markdown(f"### {plan.name}")
        for step, role, name, cov in zip(plan.steps, plan.roles, plan.names, plan.coverage):
            st.markdown(f"**Step {step.index + 1} — {role} · {name}**  ·  ~{cov:.0f}%")
            if step.is_last:
                c1, c2 = st.columns(2)
                c1.image(step.zone_rgb, caption="Where to paint", use_container_width=True)
                c2.image(step.cumulative_rgb, caption="Apply across", use_container_width=True)
            else:
                c1, c2, c3 = st.columns(3)
                c1.image(step.zone_rgb, caption="Where to paint", use_container_width=True)
                c2.image(step.cumulative_rgb, caption="Apply across", use_container_width=True)
                c3.image(step.exact_rgb, caption="Stays this colour", use_container_width=True)
else:
    result = band_and_render(rgb, shading.mask, shading.light, palette, coverage)
    # ... existing single-region display block, unchanged ...
```

- [ ] **Step 7: Manual test the full flow**

Run: `streamlit run app.py`. With the `skaven-hero` fixture (or any primed-mini photo):
1. Upload → confirm the single-palette plan still renders when no region is drawn (model C regression).
2. Draw a lasso over one area, name it "Blade", set a dark 3-layer palette, "Add region".
3. Change palette to a light 5-layer scheme, lasso the robe, "Add region".
4. Confirm: combined preview shows both palettes; swatch board lists both regions' schemes; steps are grouped under "Default / Blade / Robe"; overlap resolves last-wins; "Remove" drops a region and re-renders.

- [ ] **Step 8: Commit**

```bash
git add app.py
git commit -m "feat: region lasso UI — draw, snapshot palette, combined render + swatch board"
```

---

## Self-Review

**Spec coverage:**
- Region model C (zero regions == today) → Task 6 regression test + Task 7 branch. ✅
- Per-region palette + band count + coverage (config B) → `Region.palette`/`.coverage`, `plan_region` uses each region's own values (Task 2/6). ✅
- Descriptive swatch board (check A), structured for later readout B → Task 5. ✅
- Lasso via drawable-canvas + spike, polygon-click fallback → Task 1 gate, Task 7 both paths. ✅
- Exclusive last-wins assignment → Task 2 `assign_owners` + test. ✅
- Banding within sub-mask (luminance places highlights) → Task 6 `plan_region` bands per sub-mask + test. ✅
- Display→source mask scaling + intersect base mask → Task 3 + Task 7 Step 3. ✅
- Combined overlay + per-region grouped steps → Task 6 `combined_rgb` + Task 7 Step 6. ✅
- Out of scope (feathering, technique presets, harmony judgement, SAM) → not built; noted. ✅

**Placeholder scan:** No TBD/TODO; every code step has real code. The only spike-dependent detail (exact canvas JSON key) is handled by `_points_from_object` covering both known shapes. ✅

**Type consistency:** `assign_owners` sentinels (`-2/-1/i`) consistent across Tasks 2/6; `RegionPlan.colors` = `list[np.ndarray]` matches `paint_regions`/`swatch_board` consumers; `Region(name, mask, palette, coverage)` constructed identically in tests and Task 7; `analyze_regions(rgb, alpha, default_palette, coverage, regions)` signature consistent between Task 6 def and Task 7 call. ✅
