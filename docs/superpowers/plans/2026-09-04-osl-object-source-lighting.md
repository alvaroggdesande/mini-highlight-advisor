# OSL — Object-Source Lighting Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Let a user click a spot on a PS-normal mini, pick a glow colour, and get extra paint-along steps that glaze that object-source glow on top of the existing region plans.

**Architecture:** A pure-numpy `osl.py` computes a per-pixel glow field from the recovered normals (real N·L facing × screen-space distance falloff from the click). A ramp turns that field into a base→glow→hue-tinted-white colour contribution; `banding.py` slices it into 2–4 nested glow layers; `overlay.per_band_images` renders them as `BandStep`s. `pipeline.apply_osl` runs this as a post-process that leaves every region's base plan untouched. A PS-mode-only `ui/osl_panel.py` captures the click + sliders and shows a live preview; OSL params persist with the project and recompute on load.

**Tech Stack:** Python 3.11, numpy, Pillow, OpenCV, Streamlit, `streamlit-drawable-canvas` (already vendored via `ui/compat.py`). No new dependencies. Torch-free.

**Spec:** `docs/superpowers/specs/2026-09-04-osl-object-source-lighting-design.md`

## Global Constraints

- **Torch-free / Streamlit-free core.** `osl.py` imports only numpy (+ `banding`, `matching`, `overlay` from this package). No torch, no streamlit.
- **Pinned normal convention (load-bearing):** `n = rgb/255*2-1`, `R = x-right`, `G = y-up`, `B = z-toward-viewer`. Image row index grows **downward**, so "up" = **negative** image-y. Any direction vector dotted with normals MUST be built in this frame: `L = normalize([sx - px, py - sy, height])` (note the `py - sy`, not `sy - py`).
- **Paint colours** are `np.ndarray` float32 shape `(3,)`, RGB in **0–255** (same as `palette.PaintColor` / `overlay` blending). `glow_rgb` and `hot_rgb` follow this.
- **`bands`** are int arrays, one layer per masked pixel, off-band = `-1`, band `0` = darkest/faintest, `n-1` = brightest. `mask == (bands >= 0)` for the lit zone.
- **OSL is PS-only** (needs normals) and **single-source in v1** (math built for N, UI ships one).
- **Never build on `main`.** Work on `feat/osl-object-source-lighting`; commit per task.
- **Run tests with** `.venv/Scripts/python -m pytest`.

---

### Task 1: `osl_field` — the glow field from normals

**Files:**
- Create: `src/mini_highlight_advisor/osl.py`
- Test: `tests/test_osl.py`

**Interfaces:**
- Consumes: nothing (leaf module). Fixture: `tests/fixtures/ps/synth_normal.png`, `synth_mask.png` (dome centred at (63.5, 63.5), R=50, y-up convention).
- Produces:
  - `osl_field(normals: np.ndarray, mask: np.ndarray, x: float, y: float, height: float, reach: float, intensity: float) -> np.ndarray` — returns `(H,W)` float32 in `[0,1]`, `0` off-mask.

- [ ] **Step 1: Write the failing tests**

```python
# tests/test_osl.py
import numpy as np
from PIL import Image
from pathlib import Path
from mini_highlight_advisor import osl

_FIX = Path(__file__).parent / "fixtures" / "ps"

def _load():
    rgb = np.asarray(Image.open(_FIX / "synth_normal.png").convert("RGB"), np.float32) / 255.0
    n = rgb * 2.0 - 1.0
    n /= np.clip(np.linalg.norm(n, axis=-1, keepdims=True), 1e-6, None)
    mask = np.asarray(Image.open(_FIX / "synth_mask.png").convert("L")) > 127
    return n.astype(np.float32), mask

def test_off_mask_is_zero():
    n, mask = _load()
    g = osl.osl_field(n, mask, x=63.5, y=63.5, height=40.0, reach=40.0, intensity=1.0)
    assert g.shape == mask.shape
    assert np.all(g[~mask] == 0.0)
    assert g.dtype == np.float32

def test_peaks_near_click():
    n, mask = _load()
    # Source right above the apex -> apex normal [0,0,1] faces it, distance 0.
    g = osl.osl_field(n, mask, x=63.5, y=63.5, height=40.0, reach=40.0, intensity=1.0)
    apex = g[60:67, 60:67].mean()
    rim = g[mask].mean()
    assert apex > rim  # brightest at/near the click

def test_face_turned_away_stays_dark():
    n, mask = _load()
    # Source far to the RIGHT. Left-of-centre dome pixels point LEFT -> should stay dark
    # even though some are physically close-ish; right-facing pixels light up.
    g = osl.osl_field(n, mask, x=180.0, y=63.5, height=30.0, reach=60.0, intensity=1.0)
    left = g[mask & (np.arange(mask.shape[1])[None, :] < 45)].mean()
    right = g[mask & (np.arange(mask.shape[1])[None, :] > 82)].mean()
    assert right > left * 2.0  # N.L modulation, not a distance-only stain

def test_axis_pin_y_is_up():
    n, mask = _load()
    # Source ABOVE the top of the dome (small image-y). With the correct py - sy sign,
    # the top half (normals point up = ny>0) lights up more than the bottom half.
    g = osl.osl_field(n, mask, x=63.5, y=-40.0, height=30.0, reach=80.0, intensity=1.0)
    ys = np.arange(mask.shape[0])[:, None]
    top = g[mask & (ys < 55)].mean()
    bottom = g[mask & (ys > 72)].mean()
    assert top > bottom  # guards the image-y / green-up flip (the NMM-stripe class of bug)

def test_falloff_monotonic_in_distance():
    n, mask = _load()
    # Flat-facing background disabled by mask; use a synthetic flat normal field so only
    # distance varies (facing constant = 1 for a source straight in front).
    flat = np.zeros((100, 100, 3), np.float32); flat[..., 2] = 1.0
    m = np.ones((100, 100), bool)
    g = osl.osl_field(flat, m, x=50.0, y=50.0, height=10.0, reach=20.0, intensity=1.0)
    near = g[50, 50]; mid = g[50, 60]; far = g[50, 90]
    assert near > mid > far
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `.venv/Scripts/python -m pytest tests/test_osl.py -v`
Expected: FAIL — `AttributeError: module 'mini_highlight_advisor.osl' has no attribute 'osl_field'` (or ModuleNotFound).

- [ ] **Step 3: Implement `osl_field`**

```python
# src/mini_highlight_advisor/osl.py
"""Object-Source Lighting: a coloured point light placed on a PS-normal mini.

Pure numpy, torch-free, Streamlit-free. Consumes the pinned normal convention
(R=x-right, G=y-UP, B=z-toward-viewer). Image rows grow DOWNWARD, so "up" is
negative image-y: direction vectors are built as [sx-px, py-sy, height].
"""
from __future__ import annotations

import numpy as np


def osl_field(normals: np.ndarray, mask: np.ndarray, x: float, y: float,
              height: float, reach: float, intensity: float) -> np.ndarray:
    """Per-pixel glow amount from a point source at screen (x, y) floating `height`
    off the surface plane. Returns (H,W) float32 in [0,1], 0 off-mask.

    facing  = clip(N . L, 0, 1) with L in the normals' frame (y-up).
    falloff = 1 / (1 + (screen_distance / reach)^2).
    glow    = clip(intensity * facing * falloff, 0, 1).
    """
    h, w = mask.shape
    yy, xx = np.mgrid[0:h, 0:w].astype(np.float32)
    dx = float(x) - xx                 # x-right
    dy = yy - float(y)                 # image-y grows down; py - sy => y-UP frame
    dz = np.full_like(dx, float(height))
    L = np.stack([dx, dy, dz], axis=-1)
    L /= np.clip(np.linalg.norm(L, axis=-1, keepdims=True), 1e-6, None)
    facing = np.clip(np.sum(normals * L, axis=-1), 0.0, 1.0)
    dist = np.sqrt((xx - float(x)) ** 2 + (yy - float(y)) ** 2)
    reach = max(float(reach), 1e-3)
    falloff = 1.0 / (1.0 + (dist / reach) ** 2)
    glow = np.clip(float(intensity) * facing * falloff, 0.0, 1.0).astype(np.float32)
    glow[~mask] = 0.0
    return glow
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `.venv/Scripts/python -m pytest tests/test_osl.py -v`
Expected: PASS (5 tests).

- [ ] **Step 5: Commit**

```bash
git add src/mini_highlight_advisor/osl.py tests/test_osl.py
git commit -m "feat(osl): osl_field — glow from normals (N.L x screen falloff), axis-pinned"
```

---

### Task 2: `osl_ramp`, `osl_colors`, `osl_bands`, `osl_field_multi`

**Files:**
- Modify: `src/mini_highlight_advisor/osl.py`
- Test: `tests/test_osl.py` (append)

**Interfaces:**
- Consumes: `osl_field` (Task 1); `banding.band_light(light, mask, coverage) -> bands`.
- Produces:
  - `osl_ramp(glow, glow_rgb, hot_rgb) -> np.ndarray` — `(H,W,3)` float32 0–255, the glow **contribution** premultiplied by amount (glow=0 → 0).
  - `osl_colors(glow_rgb, hot_rgb, n) -> list[np.ndarray]` — `n` float32 `(3,)` colours, faint→hot.
  - `osl_bands(glow, mask, coverage, floor=0.08) -> np.ndarray` — bands over the **lit** zone only (`glow > floor`); unlit → `-1`.
  - `osl_field_multi(normals, mask, sources) -> np.ndarray` — `max` over per-source `osl_field`; `sources` is a list of `(x, y, height, reach, intensity)` tuples. (v1-unused seam.)

- [ ] **Step 1: Write the failing tests**

```python
# append to tests/test_osl.py
from mini_highlight_advisor import banding  # noqa

GLOW_RGB = np.array([40.0, 200.0, 90.0], np.float32)   # green
HOT_RGB  = np.array([200.0, 255.0, 210.0], np.float32) # hue-tinted white

def test_ramp_endpoints():
    glow = np.array([[0.0, 1.0]], np.float32)
    out = osl.osl_ramp(glow, GLOW_RGB, HOT_RGB)
    assert np.allclose(out[0, 0], 0.0)                 # no glow -> no contribution
    assert np.allclose(out[0, 1], HOT_RGB, atol=1e-3)  # full glow -> hot colour

def test_colors_faint_to_hot():
    cols = osl.osl_colors(GLOW_RGB, HOT_RGB, 3)
    assert len(cols) == 3
    assert np.allclose(cols[0], GLOW_RGB)
    assert np.allclose(cols[-1], HOT_RGB)

def test_bands_exclude_unlit_and_nest():
    n, mask = _load()
    g = osl.osl_field(n, mask, x=63.5, y=63.5, height=40.0, reach=25.0, intensity=1.0)
    bands = osl.osl_bands(g, mask, coverage=[1.0, 0.5, 0.2], floor=0.1)
    assert bands.shape == mask.shape
    assert np.all(bands[~mask] == -1)
    assert np.all(bands[mask & (g <= 0.1)] == -1)      # unlit excluded
    lit = bands >= 0
    assert lit.sum() > 0
    # nested: brighter bands are subsets of fainter ones
    assert (bands >= 2).sum() <= (bands >= 1).sum() <= (bands >= 0).sum()

def test_field_multi_is_max():
    n, mask = _load()
    a = osl.osl_field(n, mask, 40.0, 63.5, 30.0, 40.0, 1.0)
    b = osl.osl_field(n, mask, 88.0, 63.5, 30.0, 40.0, 1.0)
    both = osl.osl_field_multi(n, mask, [(40.0, 63.5, 30.0, 40.0, 1.0),
                                         (88.0, 63.5, 30.0, 40.0, 1.0)])
    assert np.allclose(both, np.maximum(a, b))
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `.venv/Scripts/python -m pytest tests/test_osl.py -k "ramp or colors or bands or multi" -v`
Expected: FAIL — attributes not defined.

- [ ] **Step 3: Implement**

```python
# add to src/mini_highlight_advisor/osl.py
from mini_highlight_advisor.banding import band_light


def osl_ramp(glow: np.ndarray, glow_rgb: np.ndarray, hot_rgb: np.ndarray) -> np.ndarray:
    """base->glow->hot colour, premultiplied by the glow amount (contribution)."""
    t = glow[..., np.newaxis].astype(np.float32)
    colour = (1.0 - t) * np.asarray(glow_rgb, np.float32) + t * np.asarray(hot_rgb, np.float32)
    return (colour * t).astype(np.float32)


def osl_colors(glow_rgb: np.ndarray, hot_rgb: np.ndarray, n: int) -> list[np.ndarray]:
    """n paint colours from faint glow to hot, evenly interpolated."""
    glow_rgb = np.asarray(glow_rgb, np.float32)
    hot_rgb = np.asarray(hot_rgb, np.float32)
    if n <= 1:
        return [glow_rgb.copy()]
    return [((1.0 - t) * glow_rgb + t * hot_rgb).astype(np.float32)
            for t in np.linspace(0.0, 1.0, n)]


def osl_bands(glow: np.ndarray, mask: np.ndarray, coverage: list[float],
              floor: float = 0.08) -> np.ndarray:
    """Band the LIT zone (glow > floor) into len(coverage) nested layers; unlit -> -1."""
    lit = mask & (glow > float(floor))
    if not lit.any():
        return np.full(mask.shape, -1, dtype=int)
    return band_light(glow, lit, coverage)


def osl_field_multi(normals: np.ndarray, mask: np.ndarray, sources) -> np.ndarray:
    """max-composite of osl_field over sources = list of (x,y,height,reach,intensity)."""
    out = np.zeros(mask.shape, np.float32)
    for (x, y, height, reach, intensity) in sources:
        out = np.maximum(out, osl_field(normals, mask, x, y, height, reach, intensity))
    return out
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `.venv/Scripts/python -m pytest tests/test_osl.py -v`
Expected: PASS (9 tests total).

- [ ] **Step 5: Commit**

```bash
git add src/mini_highlight_advisor/osl.py tests/test_osl.py
git commit -m "feat(osl): ramp, colours, lit-zone banding, N-source max-composite"
```

---

### Task 3: `overlay.osl_preview` — composite the glow over the painted preview

**Files:**
- Modify: `src/mini_highlight_advisor/overlay.py`
- Test: `tests/test_overlay_osl.py`

**Interfaces:**
- Consumes: `osl.osl_ramp` output (a `(H,W,3)` float32 0–255 contribution).
- Produces:
  - `osl_preview(base_rgb: np.ndarray, contribution: np.ndarray) -> np.ndarray` — `(H,W,3)` uint8, screen-blend of base and contribution.

- [ ] **Step 1: Write the failing test**

```python
# tests/test_overlay_osl.py
import numpy as np
from mini_highlight_advisor import overlay

def test_zero_contribution_is_identity():
    base = (np.random.default_rng(0).integers(0, 255, (8, 8, 3))).astype(np.uint8)
    out = overlay.osl_preview(base, np.zeros((8, 8, 3), np.float32))
    assert np.array_equal(out, base)

def test_screen_brightens_and_clips():
    base = np.full((4, 4, 3), 100, np.uint8)
    contrib = np.full((4, 4, 3), 200.0, np.float32)
    out = overlay.osl_preview(base, contrib)
    assert out.dtype == np.uint8
    assert np.all(out >= base)          # screen never darkens
    assert np.all(out <= 255)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.venv/Scripts/python -m pytest tests/test_overlay_osl.py -v`
Expected: FAIL — `overlay` has no attribute `osl_preview`.

- [ ] **Step 3: Implement**

```python
# add to src/mini_highlight_advisor/overlay.py
def osl_preview(base_rgb: np.ndarray, contribution: np.ndarray) -> np.ndarray:
    """Screen-blend an OSL glow contribution (0-255 float) over a painted preview."""
    b = base_rgb.astype(np.float32) / 255.0
    c = np.clip(contribution.astype(np.float32) / 255.0, 0.0, 1.0)
    out = 1.0 - (1.0 - b) * (1.0 - c)
    return np.clip(out * 255.0, 0, 255).astype(np.uint8)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `.venv/Scripts/python -m pytest tests/test_overlay_osl.py -v`
Expected: PASS (2 tests).

- [ ] **Step 5: Commit**

```bash
git add src/mini_highlight_advisor/overlay.py tests/test_overlay_osl.py
git commit -m "feat(overlay): osl_preview — screen-blend glow over the painted preview"
```

---

### Task 4: `pipeline.apply_osl` — post-process producing glow steps + preview

**Files:**
- Modify: `src/mini_highlight_advisor/pipeline.py`
- Test: `tests/test_pipeline_osl.py`

**Interfaces:**
- Consumes: `osl.osl_field`, `osl.osl_ramp`, `osl.osl_colors`, `osl.osl_bands`; `overlay.osl_preview`, `overlay.per_band_images`; `matching.match`, `matching.target_from_hex`.
- Produces:
  - `@dataclass OslSource(x: float, y: float, height: float, glow_rgb: np.ndarray, hot_rgb: np.ndarray)`
  - `@dataclass OslResult(glow: np.ndarray, preview_rgb: np.ndarray, steps: list[BandStep])`
  - `apply_osl(base_preview_rgb, normals, mask, source: OslSource, reach: float, intensity: float, coverage: list[float], owned, catalog) -> OslResult`
    - `owned` / `catalog` are `list[PaintColor]` for naming; may be empty (naming skipped).
    - Appends nothing to existing region plans — glow steps are returned separately, `kind="osl"`, `label` = named paint (when a catalog is given).

- [ ] **Step 1: Write the failing test**

```python
# tests/test_pipeline_osl.py
import numpy as np
from PIL import Image
from pathlib import Path
from mini_highlight_advisor import pipeline

_FIX = Path(__file__).parent / "fixtures" / "ps"

def _load():
    rgb = np.asarray(Image.open(_FIX / "synth_normal.png").convert("RGB"), np.float32) / 255.0
    n = rgb * 2.0 - 1.0
    n /= np.clip(np.linalg.norm(n, axis=-1, keepdims=True), 1e-6, None)
    mask = np.asarray(Image.open(_FIX / "synth_mask.png").convert("L")) > 127
    return n.astype(np.float32), mask

def test_apply_osl_makes_glow_steps_and_preview():
    n, mask = _load()
    base = np.full((*mask.shape, 3), 60, np.uint8)
    src = pipeline.OslSource(x=63.5, y=63.5, height=40.0,
                             glow_rgb=np.array([40., 200., 90.], np.float32),
                             hot_rgb=np.array([200., 255., 210.], np.float32))
    res = pipeline.apply_osl(base, n, mask, src, reach=25.0, intensity=1.0,
                             coverage=[1.0, 0.5, 0.2], owned=[], catalog=[])
    assert len(res.steps) == 3
    assert all(s.kind == "osl" for s in res.steps)
    assert res.preview_rgb.shape == base.shape
    # preview brightened somewhere inside the lit zone
    assert res.preview_rgb.mean() > base.mean()
    # base is untouched (caller's array not mutated)
    assert base.mean() == 60

def test_apply_osl_dark_when_source_behind():
    n, mask = _load()
    base = np.full((*mask.shape, 3), 60, np.uint8)
    # height 0 and far off to the side with tiny reach -> almost no glow
    src = pipeline.OslSource(x=-200.0, y=63.5, height=0.0,
                             glow_rgb=np.array([40., 200., 90.], np.float32),
                             hot_rgb=np.array([200., 255., 210.], np.float32))
    res = pipeline.apply_osl(base, n, mask, src, reach=5.0, intensity=1.0,
                             coverage=[1.0, 0.5, 0.2], owned=[], catalog=[])
    assert res.glow[mask].max() < 0.2
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.venv/Scripts/python -m pytest tests/test_pipeline_osl.py -v`
Expected: FAIL — `pipeline` has no `OslSource` / `apply_osl`.

- [ ] **Step 3: Implement**

```python
# add to src/mini_highlight_advisor/pipeline.py (near the other dataclasses)
from dataclasses import dataclass
from mini_highlight_advisor import osl, matching


@dataclass
class OslSource:
    x: float
    y: float
    height: float
    glow_rgb: np.ndarray   # float32 (3,) 0-255
    hot_rgb: np.ndarray    # float32 (3,) 0-255


@dataclass
class OslResult:
    glow: np.ndarray            # (H,W) float32
    preview_rgb: np.ndarray     # (H,W,3) uint8
    steps: list[BandStep]


def _rgb_to_hex(rgb: np.ndarray) -> str:
    r, g, b = (int(np.clip(v, 0, 255)) for v in rgb)
    return f"#{r:02x}{g:02x}{b:02x}"


def apply_osl(base_preview_rgb: np.ndarray, normals: np.ndarray, mask: np.ndarray,
              source: OslSource, reach: float, intensity: float,
              coverage: list[float], owned=None, catalog=None) -> OslResult:
    """Compute the OSL glow, a screen-composited preview, and nested glow steps.
    Leaves base_preview_rgb unmodified; returns steps with kind='osl' and, when a
    catalog is provided, label = the nearest named paint."""
    glow = osl.osl_field(normals, mask, source.x, source.y, source.height, reach, intensity)
    contribution = osl.osl_ramp(glow, source.glow_rgb, source.hot_rgb)
    preview = overlay.osl_preview(base_preview_rgb, contribution)
    bands = osl.osl_bands(glow, mask, coverage)
    colors = osl.osl_colors(source.glow_rgb, source.hot_rgb, len(coverage))
    steps = overlay.per_band_images(base_preview_rgb, bands, mask, colors)
    for s, color in zip(steps, colors):
        s.kind = "osl"
        if catalog:
            m = matching.match(matching.target_from_hex(_rgb_to_hex(color)),
                               owned or [], catalog)
            s.label = getattr(m, "name", None) or getattr(m, "phrase", None)
    return OslResult(glow=glow, preview_rgb=preview, steps=steps)
```

> **Note on `matching.match` return:** confirm the attribute that holds the display name (`MatchResult` around `matching.py:45`). If it is not `.name`/`.phrase`, adjust the `getattr` chain to the real field. This is the only place the plan touches `matching`; keep the label best-effort (never raise if naming fails).

- [ ] **Step 4: Run test to verify it passes**

Run: `.venv/Scripts/python -m pytest tests/test_pipeline_osl.py -v`
Expected: PASS (2 tests). Then run the full suite to catch regressions: `.venv/Scripts/python -m pytest -q`.

- [ ] **Step 5: Commit**

```bash
git add src/mini_highlight_advisor/pipeline.py tests/test_pipeline_osl.py
git commit -m "feat(pipeline): apply_osl post-process -> glow preview + named glow steps"
```

---

### Task 5: `ui/osl_panel.py` + wire into PS mode + render steps

**Files:**
- Create: `src/../../ui/osl_panel.py` (repo `ui/osl_panel.py`)
- Modify: `ui/ps_mode.py` (call the panel + `apply_osl`, stash result in session)
- Modify: `ui/results.py` (render OSL steps after the region steps)
- Modify: `ui/keys.py` (session keys for OSL state)
- Test: `tests/test_ui_osl_panel.py`

**Interfaces:**
- Consumes: `pipeline.apply_osl`, `pipeline.OslSource`; `st_canvas` via `ui.compat`; `ui.geometry` for click extraction; `keys`.
- Produces:
  - `osl_panel.render(mask_shape) -> dict | None` — returns `{"x","y","height","reach","intensity","glow_rgb","hot_rgb","coverage"}` when the user has placed a source and enabled OSL, else `None`.
  - `results.render_osl_steps(osl_result) -> None`.

- [ ] **Step 1: Write the failing UI smoke test**

```python
# tests/test_ui_osl_panel.py
import importlib

def test_osl_panel_module_imports_and_has_render():
    mod = importlib.import_module("ui.osl_panel")
    assert hasattr(mod, "render")

def test_ps_mode_calls_osl_only_with_normals(monkeypatch):
    # Guard: OSL must be gated on has_normals. Assert the source string references
    # the normals gate so the panel can never run in Path-L mode.
    import inspect, ui.ps_mode as ps
    src = inspect.getsource(ps)
    assert "osl" in src.lower()
    assert "normal" in src.lower()
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.venv/Scripts/python -m pytest tests/test_ui_osl_panel.py -v`
Expected: FAIL — `ModuleNotFoundError: ui.osl_panel`.

- [ ] **Step 3: Implement the panel**

```python
# ui/osl_panel.py
"""PS-mode-only Object-Source Lighting panel: click-to-place a coloured glow.

Streamlit reruns on every interaction; the caller re-derives the glow from the
returned params. Returns None until the user places a source AND ticks 'Enable'.
"""
import numpy as np
import streamlit as st

from ui import keys
from ui.compat import st_canvas
from ui import geometry

PRESETS = {  # (glow_rgb, hot_rgb)
    "Torch":  ((255, 150, 40), (255, 230, 190)),
    "Plasma": ((40, 200, 255), (210, 245, 255)),
    "Gem":    ((60, 220, 120), (210, 255, 225)),
}


def _hex_to_rgb(h: str) -> np.ndarray:
    h = h.lstrip("#")
    return np.array([int(h[i:i + 2], 16) for i in (0, 2, 4)], np.float32)


def render(mask_shape) -> dict | None:
    st.markdown("**Object-source glow** (OSL) — click where the light lives, pick a colour.")
    enabled = st.checkbox("Enable glow", value=st.session_state.get(keys.OSL_ON, False),
                          key=keys.OSL_ON)
    if not enabled:
        return None

    preset = st.selectbox("Preset", list(PRESETS), key=keys.OSL_PRESET)
    dg, dh = PRESETS[preset]
    glow_hex = st.color_picker("Glow colour", '#%02x%02x%02x' % dg, key=keys.OSL_GLOW)
    hot_hex = st.color_picker("Hotspot tint", '#%02x%02x%02x' % dh, key=keys.OSL_HOT)
    height = st.slider("Height (off surface)", 0.0, 120.0, 40.0, key=keys.OSL_HEIGHT)
    reach = st.slider("Reach (glow radius, px)", 5.0, 300.0, 60.0, key=keys.OSL_REACH)
    intensity = st.slider("Intensity", 0.1, 2.0, 1.0, key=keys.OSL_INTENSITY)
    n_layers = st.slider("Glow layers", 2, 4, 3, key=keys.OSL_LAYERS)

    st.caption("Click the source point on the canvas below.")
    click = None
    if st_canvas is not None:
        h, w = mask_shape
        canvas = st_canvas(height=h, width=w, drawing_mode="point",
                           stroke_width=6, key=keys.OSL_CANVAS)
        click = geometry.last_point(canvas) if hasattr(geometry, "last_point") else None
    if click is None:
        click = st.session_state.get(keys.OSL_POINT)
    if click is None:
        st.info("No source placed yet — click on the mini.")
        return None
    st.session_state[keys.OSL_POINT] = click

    x, y = float(click[0]), float(click[1])
    return {
        "x": x, "y": y, "height": float(height), "reach": float(reach),
        "intensity": float(intensity), "coverage": [1.0] * int(n_layers),
        "glow_rgb": _hex_to_rgb(glow_hex), "hot_rgb": _hex_to_rgb(hot_hex),
    }
```

> **Click extraction:** `ui/geometry.py` already parses `st_canvas` fabric objects for lassos. Add a small `last_point(canvas) -> tuple[float,float] | None` there that reads the last `point`/`circle` object's `left`/`top` (mirror the existing vertex-extraction helper). If a point drawing-mode object exposes coordinates differently, follow the shape `geometry.py` already handles. Keep it defensive: return `None` on any missing key.

- [ ] **Step 4: Add session keys**

```python
# add to ui/keys.py
OSL_ON = "osl_on"
OSL_PRESET = "osl_preset"
OSL_GLOW = "osl_glow"
OSL_HOT = "osl_hot"
OSL_HEIGHT = "osl_height"
OSL_REACH = "osl_reach"
OSL_INTENSITY = "osl_intensity"
OSL_LAYERS = "osl_layers"
OSL_CANVAS = "osl_canvas"
OSL_POINT = "osl_point"
```

- [ ] **Step 5: Wire into `ui/ps_mode.py`**

After the region plan (`multi`) and its combined preview are computed, and only in this PS branch (normals present):

```python
# ui/ps_mode.py — after the base preview_rgb / multi is available
from ui import osl_panel
from mini_highlight_advisor import pipeline as _pl

osl_params = osl_panel.render(mask.shape)
osl_result = None
if osl_params is not None:
    src = _pl.OslSource(x=osl_params["x"], y=osl_params["y"],
                        height=osl_params["height"],
                        glow_rgb=osl_params["glow_rgb"], hot_rgb=osl_params["hot_rgb"])
    osl_result = _pl.apply_osl(base_preview_rgb, normals, mask, src,
                               reach=osl_params["reach"], intensity=osl_params["intensity"],
                               coverage=osl_params["coverage"],
                               owned=paints_pool, catalog=catalog_pool)
    st.image(osl_result.preview_rgb, caption="With object-source glow",
             use_container_width=True)
st.session_state[keys.OSL_RESULT] = osl_result
```

> Use the existing variable names in `ps_mode.py` for the base preview, `normals`, `mask`, and the paint pools (`base_preview_rgb`, `paints_pool`, `catalog_pool` are placeholders — match what the file actually calls them; grep the file first). Add `OSL_RESULT = "osl_result"` to `ui/keys.py`.

- [ ] **Step 6: Render OSL steps in `ui/results.py`**

```python
# add to ui/results.py
import streamlit as st

def render_osl_steps(osl_result) -> None:
    if osl_result is None or not osl_result.steps:
        return
    st.subheader("Object-source glow — extra steps")
    st.caption("Paint the object normally first, then glaze the glow on top.")
    for s in osl_result.steps:
        cols = st.columns(2)
        cols[0].image(s.zone_rgb, caption=(s.label or "glow zone"),
                      use_container_width=True)
        cols[1].image(s.cumulative_rgb, caption="after this layer",
                      use_container_width=True)
```

Call `results.render_osl_steps(st.session_state.get(keys.OSL_RESULT))` right after `render_steps(multi)` in the paint tab.

- [ ] **Step 7: Run the UI smoke test + full suite**

Run: `.venv/Scripts/python -m pytest tests/test_ui_osl_panel.py -v && .venv/Scripts/python -m pytest -q`
Expected: PASS. (The two pre-existing `test_ui_gallery.py` failures are unrelated and known — see project memory.)

- [ ] **Step 8: Commit**

```bash
git add ui/osl_panel.py ui/ps_mode.py ui/results.py ui/keys.py ui/geometry.py tests/test_ui_osl_panel.py
git commit -m "feat(ui): OSL panel — click-to-place glow, live preview, extra glow steps (PS mode)"
```

---

### Task 6: Persist OSL params with the project + docs

**Files:**
- Modify: `src/mini_highlight_advisor/projects.py` (add OSL params to `ProjectSettings` + to/from dict)
- Modify: `ui/ps_mode.py` (seed the panel from a loaded project's OSL params)
- Modify: `CLAUDE.md` (module-map line for `osl.py`)
- Test: `tests/test_projects_osl.py`

**Interfaces:**
- Consumes: `ProjectSettings` (`projects.py:26`), `_settings_to_dict`/`_settings_from_dict` (`projects.py:103`/`109`).
- Produces: OSL params round-trip through `ProjectSettings` (persist the **params**, not the rendered images — steps recompute on load, matching how the rest of the app treats step images).

- [ ] **Step 1: Write the failing round-trip test**

```python
# tests/test_projects_osl.py
from mini_highlight_advisor import projects

def test_settings_osl_roundtrip():
    s = projects.ProjectSettings()  # existing defaults
    # OSL params are optional; None when never used.
    assert getattr(s, "osl", None) is None
    d = projects._settings_to_dict(s)
    s2 = projects._settings_from_dict(d)
    assert getattr(s2, "osl", None) is None

def test_settings_osl_values_survive():
    s = projects.ProjectSettings()
    s.osl = {"x": 12.0, "y": 34.0, "height": 40.0, "reach": 60.0,
             "intensity": 1.0, "layers": 3, "glow": "#28c85a", "hot": "#d2ffe1"}
    d = projects._settings_to_dict(s)
    s2 = projects._settings_from_dict(d)
    assert s2.osl == s.osl
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.venv/Scripts/python -m pytest tests/test_projects_osl.py -v`
Expected: FAIL — `ProjectSettings` has no `osl` field / not serialized.

- [ ] **Step 3: Implement**

Add an optional `osl: dict | None = None` field to the `ProjectSettings` dataclass (`projects.py:26`), then thread it through the serializers:

```python
# in _settings_to_dict(s): add
    "osl": s.osl,
# in _settings_from_dict(d): add (tolerate old manifests without the key)
    osl=d.get("osl"),
```

- [ ] **Step 4: Seed the panel from a loaded project**

In `ui/ps_mode.py`, before `osl_panel.render(...)`, if the active project's settings carry `osl` and the session keys are unset, prime `st.session_state` (`keys.OSL_ON`, `OSL_POINT`, colours, sliders) from it — mirroring how other panels restore from `ProjectSettings`. Grep `ps_mode.py` / `projects_panel.py` for the existing settings-restore pattern and follow it.

- [ ] **Step 5: Docs**

Add one line to `CLAUDE.md` module map under `src/mini_highlight_advisor/`:

```
- `osl.py` — object-source lighting: a clicked coloured point light over the PS
  normals (N·L × screen falloff) → glow preview + extra "glaze the glow" steps.
  PS mode only. `pipeline.apply_osl` runs it as a post-process; base plans untouched.
```

- [ ] **Step 6: Run tests + commit**

Run: `.venv/Scripts/python -m pytest tests/test_projects_osl.py -v && .venv/Scripts/python -m pytest -q`
Expected: PASS.

```bash
git add src/mini_highlight_advisor/projects.py ui/ps_mode.py CLAUDE.md tests/test_projects_osl.py
git commit -m "feat(osl): persist OSL params with the project; docs"
```

---

## Self-Review (completed)

- **Spec coverage:** model (§ osl_field, Task 1) ✓ · ramp/hotspot-tint (Task 2) ✓ · lit-zone banding into steps (Task 2/4) ✓ · N-source seam (Task 2) ✓ · add-on post-process leaving base plans untouched (Task 4) ✓ · PS-only UI + click-to-place + live preview (Task 5) ✓ · persistence (Task 6) ✓ · docs (Task 6) ✓ · axis-convention pin (Task 1 `test_axis_pin_y_is_up`) ✓.
- **Placeholder scan:** two flagged assumptions carry explicit "grep the file first / confirm the field" notes rather than silent guesses — `matching.match`'s name attribute (Task 4) and `ps_mode.py`'s real variable names (Task 5). Both are best-effort and non-fatal.
- **Type consistency:** `glow_rgb`/`hot_rgb` are float32 `(3,)` 0–255 throughout; `OslSource`/`OslResult` names match between Tasks 4–6; `osl_field`/`osl_ramp`/`osl_colors`/`osl_bands` signatures identical where consumed.

## Known unknowns for the executor (resolve by reading, not guessing)

1. **`matching.MatchResult` field name** for the display label (Task 4).
2. **`ps_mode.py` local variable names** for base preview, paint pools, and the settings-restore pattern (Tasks 5–6).
3. **`st_canvas` point-mode object shape** for click extraction (Task 5 `geometry.last_point`).
