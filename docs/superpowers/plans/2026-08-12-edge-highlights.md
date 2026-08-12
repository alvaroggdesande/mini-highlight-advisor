# Edge Highlights Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add an additive, per-region edge-highlight step that marks the crisp lit rims of every plate — derived from the luminance gradient, painted in the palette's brightest paint(s).

**Architecture:** A new `edges.py` derives a thin edge mask from the existing luminance light map (strong gradient, bright side only). The pipeline appends edge `BandStep`(s) after the tonal steps per region; rendering draws them as paint-along steps and overlays the lines on the combined preview. Tonal bands are untouched.

**Tech Stack:** Python 3.11, NumPy, OpenCV (`cv2`, already a dependency), Streamlit. Tests via pytest.

## Global Constraints

- **Primed / monochrome minis only** — luminance is the shading signal; edges are derived from luminance gradient, never from an assumed light direction.
- **Additive model** — the N tonal bands stay as broad zones; edge steps are appended, never replace a band.
- **Two-tier, reuse brightest paints** — main edge line = second-lightest paint (`colors[-2]`); extreme edge = lightest (`colors[-1]`). One-tier fallback uses the single lightest (`colors[-1]`) when there are fewer than 2 highlight colours.
- **Defaults:** edge highlights **on**; extreme-edge tier **off**.
- **`cv2` only** — no scikit-image (not installed).
- **No direct `main` commits** — this work is on branch `feat/edge-highlights`.
- **Spec:** `docs/superpowers/specs/2026-08-12-edge-highlights-design.md`.

---

## File Structure

- Create: `src/mini_highlight_advisor/edges.py` — edge-mask derivation (`edge_mask`, `extreme_edge_mask`).
- Create: `spikes/edge_highlight_spike.py` — visual operator-choice gate.
- Create: `tests/test_edges.py` — behavioural tests for the edge masks.
- Modify: `src/mini_highlight_advisor/overlay.py` — `BandStep` gains `kind`/`label`; add `edge_steps`; add edge overlay to `paint_preview`/`paint_regions`; update `_COVERAGE_NOTES`.
- Modify: `src/mini_highlight_advisor/pipeline.py` — `band_and_render`, `plan_region`, `analyze`, `analyze_regions` gain edge params and append edge steps; `RegionPlan` gains `edge_overlays`.
- Modify: `src/mini_highlight_advisor/palette.py:33-40` — rename top tonal band off "Edge Highlight".
- Modify: `app.py` — per-region edge toggles + sensitivity slider.
- Modify: `tests/test_pipeline.py` — assert appended edge steps.

---

### Task 1: Spike — choose the edge operator (HARD GATE)

Not TDD. Produces a decision and a chosen operator. **No engine code (Task 2+) begins until a human confirms the spike yields clean plate lines.**

**Files:**
- Create: `spikes/edge_highlight_spike.py`

**Interfaces:**
- Consumes: `mini_highlight_advisor.masking.load_image`, `mini_highlight_advisor.lighting.luminance_light`.
- Produces: nothing importable; writes comparison PNGs to `spikes/output/`.

- [ ] **Step 1: Write the spike script**

```python
"""Edge-highlight operator spike. Run: python spikes/edge_highlight_spike.py
Writes side-by-side candidates to spikes/output/ for human inspection.
GATE: proceed to edges.py only if one operator gives clean, thin plate lines."""
import os
import cv2
import numpy as np
from mini_highlight_advisor.masking import load_image, compute_mask
from mini_highlight_advisor.lighting import luminance_light

FIXTURES = [
    "spikes/input/WhatsApp_Image_2026-08-09_at_14.04.41-removebg-preview.png",
    "spikes/input/WhatsApp_Image_2026-08-09_at_15.53.49__1_-removebg-preview.png",
    "spikes/input/WhatsApp_Image_2026-08-09_at_15.53.48-removebg-preview.png",
]
OUT = "spikes/output"


def grad_mag(light, mask):
    l = light.astype(np.float32)
    gx = cv2.Sobel(l, cv2.CV_32F, 1, 0, ksize=3)
    gy = cv2.Sobel(l, cv2.CV_32F, 0, 1, ksize=3)
    mag = np.hypot(gx, gy)
    mag[~mask] = 0.0
    return mag


def bright_side(light, mask, win=9):
    local = cv2.blur(light.astype(np.float32), (win, win))
    return (light.astype(np.float32) >= local) & mask


def cand_sobel(light, mask, pct=90.0):
    mag = grad_mag(light, mask)
    vals = mag[mask]; vals = vals[vals > 0]
    thr = np.percentile(vals, pct)
    return (mag >= thr) & bright_side(light, mask)


def cand_canny(light, mask, lo=60, hi=150):
    l8 = cv2.normalize(light.astype(np.float32), None, 0, 255, cv2.NORM_MINMAX).astype(np.uint8)
    l8[~mask] = 0
    return (cv2.Canny(l8, lo, hi) > 0) & bright_side(light, mask)


def overlay(rgb, edge, color=(255, 40, 200)):
    out = (rgb.astype(np.float32) * 0.35).astype(np.uint8)
    out[edge] = color
    return out


def main():
    os.makedirs(OUT, exist_ok=True)
    for fx in FIXTURES:
        stem = os.path.splitext(os.path.basename(fx))[0][:24]
        rgb, alpha = load_image(fx)
        mask = compute_mask(rgb, alpha)
        light = luminance_light(rgb, mask)
        cv2.imwrite(f"{OUT}/{stem}__00_light.png", light)
        for name, edge in [
            ("sobel_p90", cand_sobel(light, mask, 90.0)),
            ("sobel_p85", cand_sobel(light, mask, 85.0)),
            ("canny", cand_canny(light, mask)),
        ]:
            img = overlay(rgb, edge)
            cv2.imwrite(f"{OUT}/{stem}__{name}.png", cv2.cvtColor(img, cv2.COLOR_RGB2BGR))
            print(stem, name, "edge px:", int(edge.sum()))


if __name__ == "__main__":
    main()
```

- [ ] **Step 2: Run the spike**

Run: `.venv/Scripts/python spikes/edge_highlight_spike.py`
Expected: writes `spikes/output/*.png`; prints edge-pixel counts per candidate.

- [ ] **Step 3: Human gate (manual)**

Inspect `spikes/output/`. **Confirm** at least one operator draws thin lines that follow plate edges (incl. on dimmer-facing plates) without turning primer grain into scribble. Record which operator + parameters win in a one-line comment at the top of `edges.py` in Task 2. **If none pass, STOP and report back — do not build the engine.**

- [ ] **Step 4: Commit**

```bash
git add spikes/edge_highlight_spike.py
git commit -m "spike: edge-highlight operator candidates (gate)"
```

---

### Task 2: `edges.py` — edge-mask derivation

**Files:**
- Create: `src/mini_highlight_advisor/edges.py`
- Test: `tests/test_edges.py`

**Interfaces:**
- Consumes: nothing from earlier tasks (pure NumPy/cv2 on `light: float32 HxW`, `mask: bool HxW`).
- Produces:
  - `edge_mask(light: np.ndarray, mask: np.ndarray, sensitivity: float = 0.5) -> np.ndarray` (bool HxW)
  - `extreme_edge_mask(light: np.ndarray, mask: np.ndarray, sensitivity: float = 0.5) -> np.ndarray` (bool HxW, always a subset of `edge_mask` with the same args)

- [ ] **Step 1: Write the failing tests**

```python
# tests/test_edges.py
import numpy as np
from mini_highlight_advisor.edges import edge_mask, extreme_edge_mask


def _two_plate(bright=200.0, dark=120.0, size=40):
    """Left half bright plate, right half darker plate: one vertical step edge."""
    light = np.full((size, size), dark, np.float32)
    light[:, : size // 2] = bright
    mask = np.ones((size, size), bool)
    return light, mask


def test_edge_lands_on_bright_side():
    light, mask = _two_plate()
    e = edge_mask(light, mask, 0.5)
    cols = np.where(e.any(axis=0))[0]
    assert cols.size > 0
    # the step is at col 20; kept pixels must sit on the bright (left) side, <= boundary
    assert cols.max() <= light.shape[1] // 2


def test_edge_is_thin():
    light, mask = _two_plate()
    e = edge_mask(light, mask, 0.5)
    per_row = e.sum(axis=1)
    # <=4: the Gaussian pre-blur widens a hard step by ~1px vs a raw Sobel line
    assert per_row[per_row > 0].max() <= 4


def test_dim_plate_still_edges():
    """Same relative step but globally dim: adaptive threshold must still fire."""
    light, mask = _two_plate(bright=90.0, dark=40.0)
    e = edge_mask(light, mask, 0.5)
    assert e.sum() > 0


def test_flat_region_has_no_edges():
    light = np.full((40, 40), 150.0, np.float32)
    mask = np.ones((40, 40), bool)
    assert edge_mask(light, mask, 0.5).sum() == 0


def test_speckle_is_dropped():
    """Isolated high-gradient specks (texture/primer grain, e.g. a gravel base)
    must be removed by the connected-component filter; only line-like edges survive."""
    light = np.full((60, 60), 120.0, np.float32)
    for (r, c) in [(10, 10), (20, 40), (35, 15), (48, 50), (30, 30)]:
        light[r, c] = 240.0  # scattered bright specks, no long edge among them
    mask = np.ones((60, 60), bool)
    assert edge_mask(light, mask, 0.5).sum() == 0


def test_extreme_is_subset_of_main():
    light, mask = _two_plate()
    main = edge_mask(light, mask, 0.5)
    ext = extreme_edge_mask(light, mask, 0.5)
    assert np.all(main[ext])  # every extreme pixel is also a main-edge pixel


def test_higher_sensitivity_more_edges():
    # gentle gradient ramp so percentile choice actually changes the count
    light = np.tile(np.linspace(60, 200, 40, dtype=np.float32), (40, 1))
    mask = np.ones((40, 40), bool)
    assert edge_mask(light, mask, 0.9).sum() >= edge_mask(light, mask, 0.1).sum()
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `.venv/Scripts/python -m pytest tests/test_edges.py -v`
Expected: FAIL with `ModuleNotFoundError: mini_highlight_advisor.edges`.

- [ ] **Step 3: Implement `edges.py`**

Operator confirmed by the spike gate (2026-08-12): **Sobel ≈ p88 + Gaussian pre-blur + connected-component despeckle, bright-side filtered.** Canny was rejected (too noisy on primer grain / textured bases). Implement exactly:

```python
"""Edge-highlight masks. Operator (spike gate 2026-08-12): Sobel gradient at ~p88
with a Gaussian pre-blur and connected-component speckle removal, bright-side
filtered. Canny rejected (too noisy on primer grain and textured bases)."""
from __future__ import annotations

import cv2
import numpy as np

_MIN_EDGE_AREA = 8  # drop connected components smaller than this (texture speckle)


def _grad_mag(light: np.ndarray, mask: np.ndarray) -> np.ndarray:
    l = cv2.GaussianBlur(light.astype(np.float32), (3, 3), 0)  # calm primer grain
    gx = cv2.Sobel(l, cv2.CV_32F, 1, 0, ksize=3)
    gy = cv2.Sobel(l, cv2.CV_32F, 0, 1, ksize=3)
    mag = np.hypot(gx, gy)
    mag[~mask] = 0.0
    return mag


def _bright_side(light: np.ndarray, mask: np.ndarray, win: int = 9) -> np.ndarray:
    local = cv2.blur(light.astype(np.float32), (win, win))
    return (light.astype(np.float32) >= local) & mask


def _despeckle(edges: np.ndarray, min_area: int = _MIN_EDGE_AREA) -> np.ndarray:
    n, labels, stats, _ = cv2.connectedComponentsWithStats(
        edges.astype(np.uint8), connectivity=8)
    out = np.zeros(edges.shape, bool)
    for i in range(1, n):  # 0 is background
        if stats[i, cv2.CC_STAT_AREA] >= min_area:
            out[labels == i] = True
    return out


def edge_mask(light: np.ndarray, mask: np.ndarray, sensitivity: float = 0.5) -> np.ndarray:
    mask = mask.astype(bool)
    mag = _grad_mag(light, mask)
    vals = mag[mask]
    vals = vals[vals > 0]
    if vals.size == 0:
        return np.zeros(mask.shape, bool)
    # sensitivity 0.5 -> ~p88; more sensitive -> lower percentile -> more edges
    pct = float(np.clip(94.0 - 12.0 * sensitivity, 82.0, 97.0))
    thr = np.percentile(vals, pct)
    strong = (mag >= thr) & mask
    return _despeckle(strong & _bright_side(light, mask))


def extreme_edge_mask(light: np.ndarray, mask: np.ndarray, sensitivity: float = 0.5) -> np.ndarray:
    base = edge_mask(light, mask, sensitivity)
    if not base.any():
        return np.zeros(mask.astype(bool).shape, bool)
    mag = _grad_mag(light, mask.astype(bool))
    thr = np.percentile(mag[base], 70.0)  # sharpest 30% of the main-edge pixels
    return base & (mag >= thr)
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `.venv/Scripts/python -m pytest tests/test_edges.py -v`
Expected: PASS (7 tests).

- [ ] **Step 5: Commit**

```bash
git add src/mini_highlight_advisor/edges.py tests/test_edges.py
git commit -m "feat: gradient edge masks (bright-side, adaptive, two-tier subset)"
```

---

### Task 3: `BandStep` fields + `edge_steps` renderer

**Files:**
- Modify: `src/mini_highlight_advisor/overlay.py:23-29` (`BandStep`), add `edge_steps` after `per_band_images`.
- Test: `tests/test_overlay.py` (add cases; keep existing).

**Interfaces:**
- Consumes: `edge_mask`, `extreme_edge_mask` (Task 2); `_zone_render`, `_render_step` (existing in `overlay.py`).
- Produces:
  - `BandStep` gains `kind: str = "band"` and `label: str | None = None` (defaults keep every existing `per_band_images` call valid).
  - `edge_steps(rgb, light, mask, colors, sensitivity: float = 0.5, extreme: bool = False, alpha: float = 0.78, start_index: int = 0) -> list[BandStep]` — 1 step (main) or 2 steps (main + extreme). Each has `kind="edge"` and a `label`.

- [ ] **Step 1: Write the failing tests**

```python
# add to tests/test_overlay.py
import numpy as np
from mini_highlight_advisor.overlay import edge_steps, BandStep


def _two_plate_rgb(size=40):
    light = np.full((size, size), 120.0, np.float32)
    light[:, : size // 2] = 200.0
    rgb = np.stack([light, light, light], -1).astype(np.uint8)
    mask = np.ones((size, size), bool)
    return rgb, light, mask


def test_edge_steps_one_tier_by_default():
    rgb, light, mask = _two_plate_rgb()
    colors = [np.array([c, c, c], np.float32) for c in (10, 80, 150, 220, 255)]
    steps = edge_steps(rgb, light, mask, colors, sensitivity=0.5, extreme=False, start_index=5)
    assert len(steps) == 1
    assert steps[0].kind == "edge"
    assert steps[0].label == "Edge Highlight"
    assert steps[0].index == 5


def test_edge_steps_two_tier_when_extreme():
    rgb, light, mask = _two_plate_rgb()
    colors = [np.array([c, c, c], np.float32) for c in (10, 80, 150, 220, 255)]
    steps = edge_steps(rgb, light, mask, colors, sensitivity=0.5, extreme=True, start_index=5)
    assert [s.label for s in steps] == ["Edge Highlight", "Extreme Edge Highlight"]
    assert steps[-1].is_last is True
    assert steps[0].is_last is False


def test_edge_steps_one_tier_fallback_few_colors():
    rgb, light, mask = _two_plate_rgb()
    colors = [np.array([c, c, c], np.float32) for c in (10, 150, 255)]  # 3 bands
    steps = edge_steps(rgb, light, mask, colors, sensitivity=0.5, extreme=True, start_index=3)
    assert len(steps) == 1  # not enough distinct highlight colours -> one tier


def test_edge_steps_one_tier_fallback_four_bands():
    """4 bands = [Shadow, Base, Midtone, Highlight] -> only ONE highlight-tier
    colour, so extreme still falls back to one tier. Two-tier needs n >= 5."""
    rgb, light, mask = _two_plate_rgb()
    colors = [np.array([c, c, c], np.float32) for c in (10, 90, 170, 255)]  # 4 bands
    steps = edge_steps(rgb, light, mask, colors, sensitivity=0.5, extreme=True, start_index=4)
    assert len(steps) == 1  # n < 5 -> one tier
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `.venv/Scripts/python -m pytest tests/test_overlay.py -k edge -v`
Expected: FAIL with `ImportError: cannot import name 'edge_steps'`.

- [ ] **Step 3: Implement**

Edit `BandStep`:

```python
@dataclass
class BandStep:
    index: int
    zone_rgb: np.ndarray
    cumulative_rgb: np.ndarray
    exact_rgb: np.ndarray | None
    is_last: bool
    kind: str = "band"
    label: str | None = None
```

Add after `per_band_images` (imports at top of file: `from .edges import edge_mask, extreme_edge_mask`):

```python
def edge_steps(rgb, light, mask, colors, sensitivity: float = 0.5,
               extreme: bool = False, alpha: float = 0.78,
               start_index: int = 0) -> list[BandStep]:
    n = len(colors)
    two_tier = extreme and n >= 5  # n>=5 => top two bands are both highlight-tier
    main_color = colors[-2] if two_tier else colors[-1]
    main = edge_mask(light, mask, sensitivity)
    steps = [BandStep(
        index=start_index,
        zone_rgb=_zone_render(rgb, main),
        cumulative_rgb=_render_step(rgb, main, main_color, alpha),
        exact_rgb=_render_step(rgb, main, main_color, alpha),
        is_last=not two_tier, kind="edge", label="Edge Highlight",
    )]
    if two_tier:
        ext = extreme_edge_mask(light, mask, sensitivity)
        steps.append(BandStep(
            index=start_index + 1,
            zone_rgb=_zone_render(rgb, ext),
            cumulative_rgb=_render_step(rgb, ext, colors[-1], alpha),
            exact_rgb=_render_step(rgb, ext, colors[-1], alpha),
            is_last=True, kind="edge", label="Extreme Edge Highlight",
        ))
    return steps
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `.venv/Scripts/python -m pytest tests/test_overlay.py -v`
Expected: PASS (existing + 3 new).

- [ ] **Step 5: Commit**

```bash
git add src/mini_highlight_advisor/overlay.py tests/test_overlay.py
git commit -m "feat: edge_steps renderer + BandStep kind/label"
```

---

### Task 4: Pipeline wiring — append edge steps per region

**Files:**
- Modify: `src/mini_highlight_advisor/pipeline.py` (`band_and_render`, `plan_region`, `analyze`, `analyze_regions`, `RegionPlan`).
- Test: `tests/test_pipeline.py` (add cases).

**Interfaces:**
- Consumes: `edge_steps` (Task 3).
- Produces: all four functions accept `edges: bool = True, extreme_edge: bool = False, edge_sensitivity: float = 0.5`. `HighlightResult.steps` / `RegionPlan.steps` include appended edge `BandStep`(s) when `edges=True`. `RegionPlan` gains `edge_overlays: list = None` — a list of `(bool_mask, color)` used by preview rendering in Task 5.

- [ ] **Step 1: Write the failing tests**

```python
# add to tests/test_pipeline.py
from mini_highlight_advisor.palette import DEFAULT_PALETTE
from mini_highlight_advisor.pipeline import analyze


def test_analyze_appends_edge_step_by_default():
    rgb, alpha = load_image(FIXTURE)
    res = analyze(rgb, alpha, DEFAULT_PALETTE)
    kinds = [s.kind for s in res.steps]
    assert kinds.count("band") == len(DEFAULT_PALETTE)
    assert kinds.count("edge") == 1  # extreme off by default


def test_analyze_no_edge_when_disabled():
    rgb, alpha = load_image(FIXTURE)
    res = analyze(rgb, alpha, DEFAULT_PALETTE, edges=False)
    assert all(s.kind == "band" for s in res.steps)


def test_analyze_two_edge_steps_with_extreme():
    rgb, alpha = load_image(FIXTURE)
    res = analyze(rgb, alpha, DEFAULT_PALETTE, extreme_edge=True)
    assert [s.kind for s in res.steps].count("edge") == 2
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `.venv/Scripts/python -m pytest tests/test_pipeline.py -k edge -v`
Expected: FAIL with `TypeError: analyze() got an unexpected keyword argument 'edges'`.

- [ ] **Step 3: Implement**

Add `from .overlay import ... edge_steps` to the existing overlay import. Update `band_and_render`:

```python
def band_and_render(rgb, mask, light, palette, coverage,
                    edges: bool = True, extreme_edge: bool = False,
                    edge_sensitivity: float = 0.5) -> HighlightResult:
    n = len(palette)
    colors = [p.rgb for p in palette]
    names = [p.name for p in palette]
    roles = role_names(n)
    bands = band_light(light, mask, coverage)
    cov = coverage_pct(bands, mask, n)
    preview_rgb = paint_preview(rgb, bands, mask, colors)
    legend = render_legend(colors, names, roles, cov, height=preview_rgb.shape[0])
    panel = compose_panel(rgb, preview_rgb, legend)
    steps = per_band_images(rgb, bands, mask, colors)
    if edges:
        steps = steps + edge_steps(rgb, light, mask, colors,
                                   sensitivity=edge_sensitivity,
                                   extreme=extreme_edge, start_index=n)
    return HighlightResult(mask, light, bands, cov, roles, preview_rgb, panel, steps)
```

Thread the same three params through `analyze` into `band_and_render`:

```python
def analyze(rgb, alpha, palette, coverage=None,
            edges: bool = True, extreme_edge: bool = False,
            edge_sensitivity: float = 0.5) -> HighlightResult:
    if coverage is None:
        coverage = default_coverage(len(palette))
    shading = prepare_shading(rgb, alpha)
    return band_and_render(rgb, shading.mask, shading.light, palette, coverage,
                           edges=edges, extreme_edge=extreme_edge,
                           edge_sensitivity=edge_sensitivity)
```

Add `edge_overlays` to `RegionPlan` (after `steps`):

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
    edge_overlays: list | None = None
```

Update `plan_region` and `analyze_regions` to accept and thread the three params, and to build `edge_overlays` for the preview (import `edge_mask, extreme_edge_mask` from `.edges`):

```python
def plan_region(rgb, sub_mask, light, name, palette, coverage,
                edges: bool = True, extreme_edge: bool = False,
                edge_sensitivity: float = 0.5) -> RegionPlan:
    colors = [p.rgb for p in palette]
    names = [p.name for p in palette]
    roles = role_names(len(palette))
    bands = band_light(light, sub_mask, coverage)
    cov = coverage_pct(bands, sub_mask, len(palette))
    steps = per_band_images(rgb, bands, sub_mask, colors)
    overlays = None
    if edges:
        steps = steps + edge_steps(rgb, light, sub_mask, colors,
                                   sensitivity=edge_sensitivity,
                                   extreme=extreme_edge, start_index=len(palette))
        two_tier = extreme_edge and len(colors) >= 5  # match edge_steps guard
        overlays = [(edge_mask(light, sub_mask, edge_sensitivity),
                     colors[-2] if two_tier else colors[-1])]
        if two_tier:
            overlays.append((extreme_edge_mask(light, sub_mask, edge_sensitivity), colors[-1]))
    return RegionPlan(name, sub_mask, bands, colors, names, roles, cov, steps, overlays)


def analyze_regions(rgb, alpha, default_palette, coverage=None, regions=None,
                    edges: bool = True, extreme_edge: bool = False,
                    edge_sensitivity: float = 0.5) -> MultiRegionResult:
    regions = regions or []
    if coverage is None:
        coverage = default_coverage(len(default_palette))
    shading = prepare_shading(rgb, alpha)
    mask, light = shading.mask, shading.light
    owner = assign_owners(mask, [r.mask for r in regions])
    plans: list[RegionPlan] = []
    default_sub = owner == -1
    ekw = dict(edges=edges, extreme_edge=extreme_edge, edge_sensitivity=edge_sensitivity)
    if default_sub.any():
        plans.append(plan_region(rgb, default_sub, light, WHOLE_MINI, default_palette, coverage, **ekw))
    for i, r in enumerate(regions):
        sub = owner == i
        if not sub.any():
            continue
        plans.append(plan_region(rgb, sub, light, r.name, r.palette, r.coverage, **ekw))
    combined = paint_regions(rgb, plans)
    return MultiRegionResult(mask, light, plans, combined)
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `.venv/Scripts/python -m pytest tests/test_pipeline.py -v`
Expected: PASS (existing + 3 new).

- [ ] **Step 5: Commit**

```bash
git add src/mini_highlight_advisor/pipeline.py tests/test_pipeline.py
git commit -m "feat: append edge steps in analyze/analyze_regions (per region)"
```

---

### Task 5: Draw edge lines on the combined preview

**Files:**
- Modify: `src/mini_highlight_advisor/overlay.py` (`paint_preview`, `paint_regions`).
- Test: `tests/test_overlay.py` (add cases).

**Interfaces:**
- Consumes: `RegionPlan.edge_overlays` (Task 4).
- Produces:
  - `paint_preview(rgb, bands, mask, colors, alpha=0.78, edge_overlays=None)` — `edge_overlays: list[(bool_mask, color)] | None`; edge pixels drawn last.
  - `paint_regions(rgb, plans, alpha=0.78)` — draws each plan's `edge_overlays` last (after all band fills, so lines sit on top).

- [ ] **Step 1: Write the failing tests**

```python
# add to tests/test_overlay.py
from mini_highlight_advisor.overlay import paint_preview


def test_paint_preview_draws_edge_overlay():
    size = 20
    rgb = np.zeros((size, size, 3), np.uint8)
    mask = np.ones((size, size), bool)
    bands = np.zeros((size, size), np.int32)
    colors = [np.array([0, 0, 0], np.float32)]
    edge = np.zeros((size, size), bool)
    edge[5, :] = True
    red = np.array([255, 0, 0], np.float32)
    out = paint_preview(rgb, bands, mask, colors, edge_overlays=[(edge, red)])
    # row 5 should carry red; a non-edge row should not
    assert out[5, 10, 0] > 150
    assert out[0, 10, 0] < 50
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `.venv/Scripts/python -m pytest tests/test_overlay.py -k edge_overlay -v`
Expected: FAIL with `TypeError: paint_preview() got an unexpected keyword argument 'edge_overlays'`.

- [ ] **Step 3: Implement**

Extend `paint_preview` (add the param and a final overlay pass before the clip):

```python
def paint_preview(rgb, bands, mask, colors, alpha: float = 0.78, edge_overlays=None) -> np.ndarray:
    base = rgb.astype(np.float32)
    out = base.copy()
    out[~mask] = out[~mask] * _DIM
    for b, color in enumerate(colors):
        m = (bands == b) & mask
        out[m] = (1 - alpha) * base[m] + alpha * color
    for emask, color in (edge_overlays or []):
        out[emask] = (1 - alpha) * base[emask] + alpha * color
    return np.clip(out, 0, 255).astype(np.uint8)
```

Extend `paint_regions` to draw overlays last:

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
    for p in plans:
        for emask, color in (p.edge_overlays or []):
            m = emask & p.sub_mask
            out[m] = (1 - alpha) * base[m] + alpha * color
    return np.clip(out, 0, 255).astype(np.uint8)
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `.venv/Scripts/python -m pytest tests/test_overlay.py -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add src/mini_highlight_advisor/overlay.py tests/test_overlay.py
git commit -m "feat: overlay edge lines on combined preview"
```

---

### Task 6: Naming cleanup — top tonal band is no longer "Edge Highlight"

**Files:**
- Modify: `src/mini_highlight_advisor/palette.py:33-40` (`_ROLE_NAMES` lists); also fix the stale `default_coverage` comment ("edge highlight thinnest" → "bright highlight thinnest").
- Modify: `src/mini_highlight_advisor/overlay.py:9-15` (`_COVERAGE_NOTES`).
- Modify: `src/mini_highlight_advisor/consistency.py:7-13` (`ROLE_DILUTION`) — the old `"Edge Highlight"` key was the top *tonal* band's dilution advice; after the rename the tonal band is `"Bright Highlight"`, so add that key. Keep `"Edge Highlight"` (its "thinned, fine controlled tip" advice now correctly describes the real edge step) and add `"Extreme Edge Highlight"`.
- Test: `tests/test_palette.py` (adjust assertions on the old top-band name) and `tests/test_consistency.py` (add a `"Bright Highlight"` role test).

**Interfaces:**
- Consumes: nothing new.
- Produces: `role_names(n)` returns "Bright Highlight" (not "Edge Highlight") as the top tonal band for n≥5; the string "Edge Highlight" now belongs only to the appended edge step's `label`.

- [ ] **Step 1: Update the role lists**

In `palette.py`, replace the top entry of each list that reads `"Edge Highlight"` with `"Bright Highlight"`:

```python
    3: ["Shadow", "Base", "Highlight"],
    4: ["Shadow", "Base", "Midtone", "Highlight"],
    5: ["Shadow", "Base", "Midtone", "Highlight", "Bright Highlight"],
    6: ["Shadow", "Deep Base", "Base", "Midtone", "Highlight", "Bright Highlight"],
    7: ["Shadow", "Deep Base", "Base", "Midtone", "Upper Midtone",
        "Highlight", "Bright Highlight"],
```

- [ ] **Step 2: Update coverage notes**

In `overlay.py` `_COVERAGE_NOTES`, replace the `"Edge Highlight"` key with `"Bright Highlight"` and add the true edge labels:

```python
_COVERAGE_NOTES = {
    "Shadow": "deepest recesses",
    "Base": "the main body of the surface",
    "Midtone": "flat, gently-lit panels",
    "Highlight": "raised areas facing the light",
    "Bright Highlight": "the brightest broad zones",
    "Edge Highlight": "the crisp lit rim of every plate",
    "Extreme Edge Highlight": "sharpest edges only, the final pop",
}
```

- [ ] **Step 3: Run the full suite**

Run: `.venv/Scripts/python -m pytest -q`
Expected: PASS. If `tests/test_palette.py` asserts the old `"Edge Highlight"` top-band name, update it to `"Bright Highlight"`.

- [ ] **Step 4: Commit**

```bash
git add src/mini_highlight_advisor/palette.py src/mini_highlight_advisor/overlay.py tests/test_palette.py
git commit -m "refactor: rename top tonal band to Bright Highlight; edge labels own 'Edge Highlight'"
```

---

### Task 7: UI — per-region edge toggles + sensitivity slider

Streamlit UI; verified by running the app (repo convention: no unit test for `app.py`; the user runs the smoke).

**Files:**
- Modify: `app.py`

**Interfaces:**
- Consumes: `analyze` / `analyze_regions` edge params (Task 4).
- Produces: three widgets whose values are passed as `edges`, `extreme_edge`, `edge_sensitivity`.

- [ ] **Step 1: Add the widgets**

Near the existing per-region palette/coverage controls, add (keys namespaced per region so multiple regions don't collide):

```python
edges = st.checkbox("Edge highlights", value=True, key=f"edges_{region_key}")
extreme_edge = st.checkbox("Extreme edge highlight", value=False,
                           key=f"extreme_{region_key}", disabled=not edges)
edge_sensitivity = st.slider("Edge sensitivity", 0.0, 1.0, 0.5, 0.05,
                             key=f"edgesens_{region_key}", disabled=not edges,
                             help="Few sharpest edges (left) to more edges (right).")
```

- [ ] **Step 2: Thread into the analyze call**

Pass the widget values into the existing `analyze(...)` / `analyze_regions(...)` call:

```python
result = analyze_regions(
    rgb, alpha, default_palette, coverage=coverage, regions=regions,
    edges=edges, extreme_edge=extreme_edge, edge_sensitivity=edge_sensitivity,
)
```

- [ ] **Step 3: Label edge steps in the step display**

Where the app renders each `BandStep` caption, prefer `step.label` when set:

```python
caption = step.label or roles[step.index]
```

- [ ] **Step 4: Manual smoke (user runs)**

Run: `streamlit run app.py`
Verify: upload the fixture; the plan gains a final "Edge Highlight" step tracing plate rims; toggling "Extreme edge highlight" adds an "Extreme Edge Highlight" step; the sensitivity slider changes how many edges appear; turning "Edge highlights" off removes the extra steps and preview lines.

- [ ] **Step 5: Commit**

```bash
git add app.py
git commit -m "feat: edge-highlight UI (toggle, extreme toggle, sensitivity)"
```

---

## Self-Review

**Spec coverage:**
- Additive, tonal bands untouched → Tasks 3–4 (append only). ✓
- Two-tier reuse of last two paints + one-tier fallback → Task 3 (`edge_steps`) + tests. ✓
- Gradient / bright-side / adaptive / silhouette derivation → Task 2 (`edges.py`). *(Silhouette rim: the mask-boundary step edge is captured by the Sobel response at `mask` borders; no extra code — confirmed visually in the Task 1 spike.)* ✓
- Spike hard gate → Task 1. ✓
- Pipeline per-region wiring → Task 4. ✓
- Combined-preview overlay → Task 5. ✓
- UI toggles + sensitivity, defaults (edge on / extreme off) → Task 7 + Task 3/4 defaults. ✓
- Naming cleanup → Task 6. ✓
- Testing matrix (bright side, thin, dim survives, flat empty, extreme⊆main, toggle off) → Tasks 2–4. ✓

**Placeholder scan:** one intentional `<FILL>` in `edges.py`'s docstring — the spike's chosen operator name, resolved in Task 1 Step 3. No other placeholders.

**Type consistency:** `edge_mask`/`extreme_edge_mask(light, mask, sensitivity)` used identically in Tasks 2/4; `edge_steps(..., start_index=n)` matches call sites in Task 4; `BandStep.kind`/`label` defined in Task 3 and consumed in Tasks 4/7; `RegionPlan.edge_overlays` defined in Task 4 and consumed in Task 5.
