# NMM (metal-from-normals) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add NMM (Non-Metallic Metal) as a per-region material that re-bands a metal region from a reflection-environment light derived from the surface normals, gated on the PS normal field.

**Architecture:** A new pure consumer module `materials.py` turns the normal field into a reflection-environment brightness map (`nmm_light`, built on `surface.reflect`). `Region` gains a `material` string ("matte" | "nmm"); when a region's material is "nmm" and a normal field is present, `pipeline.plan_region` swaps the region's `light` for `nmm_light(...)` before banding — every downstream mechanism (banding, coverage, steps, edges, shades) runs unchanged. Capability-gated: no normals ⇒ Path L byte-identical.

**Tech Stack:** Python 3.11, numpy, opencv (cv2), Streamlit; pytest. Pure modules are torch-free.

**Spec:** `docs/superpowers/specs/2026-08-28-nmm-metal-from-normals-design.md`

## Global Constraints

- **Path L byte-identical:** when no `normal_field` is present (or every region is `"matte"`), output must be identical to current behaviour. Every task that touches the pipeline carries a matte/no-normals regression assertion.
- **Capability-gated on the normal field, not a mode flag:** NMM is available only when `normal_field is not None` (PS mode). UI controls are hidden in photo mode; `plan_region` falls back to matte if asked for NMM without normals.
- **Normal convention (pinned, do not flip):** `R = x-right, G = y-up, B = z-toward-viewer`; consumed already-normalized. View direction for reflection is `+Z = (0, 0, 1)`.
- **Colors come from the region's own palette** — this slice invents no colors; it only places existing palette colors on the reflection curve.
- **Pure modules stay pure:** `materials.py` is numpy-in/numpy-out, no Streamlit, no torch (mirrors `surface.py` / `edges.py`).
- **Process:** work on branch `feat/nmm-metal-from-normals`; TDD; commit after each task. Never build on `main`.
- **Non-goals (do not implement):** OSL, procedural metal-ramp synthesis, double-horizon / reflected-floor / environment rotation, NMM in photo mode.
- **Run tests with:** `.venv/Scripts/python -m pytest`

---

### Task 1: `materials.nmm_light` — reflection-environment shading (pure)

**Files:**
- Create: `src/mini_highlight_advisor/materials.py`
- Test: `tests/test_materials_nmm.py`

**Interfaces:**
- Consumes: `surface.reflect(view, normals) -> (H,W,3) float32` (already exists).
- Produces: `nmm_light(normals: np.ndarray, mask: np.ndarray, view=(0.0,0.0,1.0), horizon: float = 0.5, softness: float = 0.15) -> (H,W) float32` in `[0,1]`, off-mask `0.0`. Higher `horizon` ⇒ horizon sits higher ⇒ more "ground" ⇒ darker overall.

- [ ] **Step 1: Write the failing tests**

```python
# tests/test_materials_nmm.py
import numpy as np

from mini_highlight_advisor import materials


def _flat(h=21, w=21):
    """All normals face the viewer (+Z)."""
    n = np.zeros((h, w, 3), np.float32)
    n[..., 2] = 1.0
    return n, np.ones((h, w), bool)


def _dome(h=41, w=41):
    """Convex hemisphere: normals tip from up (top rows) to down (bottom rows)."""
    yy, xx = np.mgrid[0:h, 0:w].astype(np.float32)
    cy = cx = (h - 1) / 2.0
    r = (h - 1) / 2.0
    dx = (xx - cx) / r
    dy = (yy - cy) / r
    r2 = dx * dx + dy * dy
    mask = r2 <= 1.0
    nx = dx
    ny = -dy                                    # image row grows down; convention is y-UP
    nz = np.sqrt(np.clip(1.0 - r2, 0.0, None))
    n = np.stack([nx, ny, nz], axis=-1).astype(np.float32)
    n[~mask] = np.array([0.0, 0.0, 1.0], np.float32)
    return n, mask


def test_nmm_light_is_float32_and_bounded():
    n, m = _dome()
    out = materials.nmm_light(n, m)
    assert out.dtype == np.float32
    assert out[m].min() >= 0.0 and out[m].max() <= 1.0


def test_flat_front_facing_has_no_horizon():
    # R_y == 0 everywhere -> uniform mid value, no spurious light/dark split.
    n, m = _flat()
    out = materials.nmm_light(n, m, horizon=0.5)
    assert np.allclose(out[m], out[m].flat[0], atol=1e-5)


def test_dome_is_bright_top_dark_bottom():
    n, m = _dome()
    out = materials.nmm_light(n, m, horizon=0.5)
    col = out.shape[1] // 2
    top = out[2, col]            # reflects up -> sky
    bottom = out[-3, col]       # reflects down -> ground
    assert top > bottom


def test_higher_horizon_is_darker_overall():
    # Raising the horizon puts more surface below it (ground) -> lower mean brightness.
    n, m = _dome()
    low = materials.nmm_light(n, m, horizon=0.2)[m].mean()
    high = materials.nmm_light(n, m, horizon=0.8)[m].mean()
    assert low > high


def test_off_mask_is_zero():
    n, m = _dome()
    m2 = m.copy()
    m2[:5, :] = False
    out = materials.nmm_light(n, m2)
    assert np.all(out[~m2] == 0.0)


def test_degenerate_all_zero_normals_is_flat_not_crash():
    n = np.zeros((10, 10, 3), np.float32)       # all-zero -> renormalized defensively
    m = np.ones((10, 10), bool)
    out = materials.nmm_light(n, m)
    assert out.shape == (10, 10)
    assert np.all(np.isfinite(out))
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `.venv/Scripts/python -m pytest tests/test_materials_nmm.py -v`
Expected: FAIL with `ModuleNotFoundError: mini_highlight_advisor.materials` (module not created yet).

- [ ] **Step 3: Write minimal implementation**

```python
# src/mini_highlight_advisor/materials.py
"""Pure, torch-free material shading derived from a normal field.

NMM (Non-Metallic Metal): a metal surface is a mirror, so it shows the
environment, not its own colour. We sample a two-zone virtual environment
(bright sky above a horizon, dark ground below) along the per-pixel reflection
vector R = reflect(view, normals). The resulting brightness re-bands the region
so the classic NMM light/dark split + horizon land geometrically.

Consumes the SAME pinned convention as surface.py / relight.py
(R=x-right, G=y-up, B=z-toward-viewer) and the already-normalized field.
numpy in, numpy out; no Streamlit, no torch. A future osl_light() sibling
(coloured object-source glow via N.L) will live here too.
"""
from __future__ import annotations

import numpy as np

from .surface import reflect


def _smoothstep(a: float, b: float, x: np.ndarray) -> np.ndarray:
    t = np.clip((x - a) / (b - a + 1e-12), 0.0, 1.0)
    return t * t * (3.0 - 2.0 * t)


def nmm_light(normals: np.ndarray, mask: np.ndarray,
              view=(0.0, 0.0, 1.0), horizon: float = 0.5,
              softness: float = 0.15) -> np.ndarray:
    """Reflection-environment brightness for NMM, in [0,1]; off-mask 0.

    view: reflection view direction (default +Z, toward viewer). horizon in
    [0,1] slides the sky/ground split in R_y space: 0 = horizon at the bottom
    (all sky, bright), 1 = horizon at the top (all ground, dark), 0.5 = split at
    the equator. softness sets the transition half-width (the hard NMM line).
    """
    m = mask.astype(bool)
    r = reflect(np.asarray(view, np.float32), normals)   # reflect() validates normals
    ry = r[..., 1]                                        # y-up component
    thr = 2.0 * float(horizon) - 1.0                     # horizon height -> R_y threshold
    light = _smoothstep(thr - softness, thr + softness, ry).astype(np.float32)
    light[~m] = 0.0
    return light
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `.venv/Scripts/python -m pytest tests/test_materials_nmm.py -v`
Expected: PASS (6 tests).

- [ ] **Step 5: Commit**

```bash
git add src/mini_highlight_advisor/materials.py tests/test_materials_nmm.py
git commit -m "feat(materials): nmm_light — reflection-environment shading from normals"
```

---

### Task 2: `Region.material` + `RegionBook` material accessors

**Files:**
- Modify: `src/mini_highlight_advisor/regions.py` (the `Region` dataclass, ~lines 11-16)
- Modify: `src/mini_highlight_advisor/region_state.py` (the `RegionBook` dataclass + accessors)
- Test: `tests/test_region_state.py` (append tests)

**Interfaces:**
- Produces: `Region.material: str = "matte"`; `RegionBook.whole_material: str = "matte"`; `RegionBook.material_at(g: int) -> str`; `RegionBook.set_material_at(g: int, material: str) -> None` (index 0 = whole mini; 1..N = drawn; raises `IndexError` out of range, same as `palette_at`).

- [ ] **Step 1: Write the failing tests**

```python
# append to tests/test_region_state.py
def test_material_defaults_to_matte():
    b = new_book(5)
    assert b.material_at(0) == "matte"

def test_set_material_routes_by_index():
    b = new_book(3)
    b.add(_mask(), "Blade", default_ramp(3), default_coverage(3))
    b.set_material_at(1, "nmm")
    assert b.material_at(1) == "nmm"
    assert b.material_at(0) == "matte"        # whole mini untouched

def test_set_material_whole_mini():
    b = new_book(3)
    b.set_material_at(0, "nmm")
    assert b.material_at(0) == "nmm"

def test_material_at_out_of_range_raises():
    b = new_book(3)
    try:
        b.material_at(5)
        assert False, "expected IndexError"
    except IndexError:
        pass

def test_new_region_material_defaults_matte():
    from mini_highlight_advisor.regions import Region
    r = Region("X", _mask(), default_ramp(3), default_coverage(3))
    assert r.material == "matte"
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `.venv/Scripts/python -m pytest tests/test_region_state.py -k material -v`
Expected: FAIL with `AttributeError: 'RegionBook' object has no attribute 'material_at'` (and `Region` has no `material`).

- [ ] **Step 3: Add `material` to `Region`**

In `src/mini_highlight_advisor/regions.py`, add the field to the dataclass (keep it last, with a default so positional construction is unaffected):

```python
@dataclass
class Region:
    name: str
    mask: np.ndarray                 # source-resolution bool
    palette: list[PaintColor]
    coverage: list[float]            # len == len(palette), sums to ~1.0
    material: str = "matte"          # "matte" (default) | "nmm"
```

- [ ] **Step 4: Add `whole_material` + accessors to `RegionBook`**

In `src/mini_highlight_advisor/region_state.py`, add the field after `whole_coverage` (defaults must stay at the end of the dataclass):

```python
@dataclass
class RegionBook:
    whole_palette: list[PaintColor]
    whole_coverage: list[float]
    whole_material: str = "matte"
    drawn: list[Region] = field(default_factory=list)
    selected: int = 0
```

Add the two accessors next to `set_coverage_at` (reuse `_check`):

```python
    def material_at(self, g: int) -> str:
        self._check(g)
        return self.whole_material if g == 0 else self.drawn[g - 1].material

    def set_material_at(self, g: int, material: str) -> None:
        self._check(g)
        if g == 0:
            self.whole_material = material
        else:
            self.drawn[g - 1].material = material
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `.venv/Scripts/python -m pytest tests/test_region_state.py -v`
Expected: PASS (existing tests + 5 new). Note: `new_book(...)` and `projects._read_angle` construct `RegionBook`/`Region` without `material`, so the defaults apply — no change needed there.

- [ ] **Step 6: Commit**

```bash
git add src/mini_highlight_advisor/regions.py src/mini_highlight_advisor/region_state.py tests/test_region_state.py
git commit -m "feat(regions): per-region material property (matte|nmm) + RegionBook accessors"
```

---

### Task 3: Pipeline threading — `plan_region` swap + `analyze_regions` per-region material

**Files:**
- Modify: `src/mini_highlight_advisor/pipeline.py` (`plan_region` ~lines 121-173; `analyze_regions` ~lines 176-228; imports ~line 15)
- Test: `tests/test_pipeline_nmm.py`

**Interfaces:**
- Consumes: `materials.nmm_light` (Task 1); `Region.material` (Task 2).
- Produces:
  - `plan_region(..., material: str = "matte", nmm_horizon: float = 0.5)` — when `material == "nmm"` and `normals is not None`, the region's `light` is replaced by `materials.nmm_light(normals, sub_mask, horizon=nmm_horizon)` before banding; otherwise unchanged.
  - `analyze_regions(..., nmm_horizon: float = 0.5, whole_material: str = "matte")` — passes `whole_material` for the leftover region and each drawn `Region.material` into `plan_region`.

- [ ] **Step 1: Write the failing tests**

```python
# tests/test_pipeline_nmm.py
import numpy as np

from mini_highlight_advisor.pipeline import plan_region, analyze_regions, WHOLE_MINI
from mini_highlight_advisor.palette import DEFAULT_PALETTE, default_coverage
from mini_highlight_advisor.regions import Region

PAL = DEFAULT_PALETTE[:5]
COV = default_coverage(5)


def _dome(h=64, w=64):
    yy, xx = np.mgrid[0:h, 0:w].astype(np.float32)
    cy = cx = (h - 1) / 2.0
    r = (h - 1) / 2.0
    dx = (xx - cx) / r
    dy = (yy - cy) / r
    r2 = dx * dx + dy * dy
    mask = r2 <= 1.0
    n = np.stack([dx, -dy, np.sqrt(np.clip(1.0 - r2, 0.0, None))], -1).astype(np.float32)
    n[~mask] = np.array([0.0, 0.0, 1.0], np.float32)
    return n, mask


def _uniform_light(mask, val=0.5):
    return np.full(mask.shape, val, np.float32)


def test_matte_region_bands_from_passed_light():
    # Uniform light + matte -> a single band (regression: NMM off changes nothing).
    n, mask = _dome()
    rgb = np.full((*mask.shape, 3), 120, np.uint8)
    plan = plan_region(rgb, mask, _uniform_light(mask), "x", PAL, COV,
                       edges=False, normals=n, material="matte")
    assert len(np.unique(plan.bands[mask])) == 1


def test_nmm_region_rebands_from_geometry():
    # Same uniform light, but material="nmm" -> geometry drives banding -> many bands.
    n, mask = _dome()
    rgb = np.full((*mask.shape, 3), 120, np.uint8)
    plan = plan_region(rgb, mask, _uniform_light(mask), "x", PAL, COV,
                       edges=False, normals=n, material="nmm", nmm_horizon=0.5)
    assert len(np.unique(plan.bands[mask])) > 1


def test_nmm_is_light_independent():
    # NMM ignores the passed light: two different light fields -> identical banding.
    n, mask = _dome()
    rgb = np.full((*mask.shape, 3), 120, np.uint8)
    a = plan_region(rgb, mask, _uniform_light(mask, 0.2), "x", PAL, COV,
                    edges=False, normals=n, material="nmm")
    b = plan_region(rgb, mask, _uniform_light(mask, 0.9), "x", PAL, COV,
                    edges=False, normals=n, material="nmm")
    np.testing.assert_array_equal(a.bands, b.bands)


def test_nmm_without_normals_falls_back_to_matte():
    n, mask = _dome()
    rgb = np.full((*mask.shape, 3), 120, np.uint8)
    plan = plan_region(rgb, mask, _uniform_light(mask), "x", PAL, COV,
                       edges=False, normals=None, material="nmm")
    assert len(np.unique(plan.bands[mask])) == 1     # matte fallback, no crash


def test_analyze_regions_per_region_material_isolation():
    # Whole mini matte (flat bg, uniform light -> 1 band); drawn NMM region (dome -> many).
    n, dome = _dome()
    rgb = np.full((*dome.shape, 3), 120, np.uint8)
    alpha = np.full(dome.shape, 255, np.uint8)
    light = _uniform_light(dome)
    blade = Region("Blade", dome, PAL, COV, material="nmm")
    res = analyze_regions(rgb, alpha, PAL, COV, [blade], edges=False,
                          light_field=light, normal_field=n, whole_material="matte")
    blade_plan = next(p for p in res.plans if p.name == "Blade")
    assert len(np.unique(blade_plan.bands[blade_plan.sub_mask])) > 1
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `.venv/Scripts/python -m pytest tests/test_pipeline_nmm.py -v`
Expected: FAIL with `TypeError: plan_region() got an unexpected keyword argument 'material'`.

- [ ] **Step 3: Add the import and the light swap in `plan_region`**

In `src/mini_highlight_advisor/pipeline.py`, extend the overlay import block (~line 15) to bring in `materials`:

```python
from . import materials
```

Change the `plan_region` signature (add the two params at the end) and insert the swap immediately after the signature, **before** the `flat_albedo`/`relief_cap`/banding logic:

```python
def plan_region(rgb, sub_mask, light, name, palette, coverage,
                edges: bool = True, extreme_edge: bool = False,
                edge_sensitivity: float = 0.5,
                relief_cap: bool = False, flat_albedo: bool = False,
                normals: np.ndarray | None = None,
                shades: bool = False,
                material: str = "matte", nmm_horizon: float = 0.5) -> RegionPlan:
    if material == "nmm" and normals is not None:
        # Metal is a mirror: re-band from the reflection environment, not the
        # caught/relit light. Geometry (not the virtual light) places the NMM
        # horizon. normals absent -> silently stay matte (defense in depth).
        light = materials.nmm_light(normals, sub_mask, horizon=nmm_horizon)
    requested_bands = len(palette)
    # ... rest unchanged ...
```

- [ ] **Step 4: Thread material through `analyze_regions`**

Change the `analyze_regions` signature to add `nmm_horizon` and `whole_material` (at the end), add `nmm_horizon` to the shared `ekw` dict, and pass the material per region:

```python
def analyze_regions(rgb, alpha, default_palette, coverage=None, regions=None,
                    edges: bool = True, extreme_edge: bool = False,
                    edge_sensitivity: float = 0.5,
                    relief_cap: bool = False,
                    per_region_norm: bool = False,
                    light_field: np.ndarray | None = None,
                    normal_field: np.ndarray | None = None,
                    shades: bool = False,
                    nmm_horizon: float = 0.5,
                    whole_material: str = "matte") -> MultiRegionResult:
```

Add `nmm_horizon` to `ekw` (leave `material` out of `ekw` — it is per-region):

```python
    ekw = dict(edges=edges, extreme_edge=extreme_edge, edge_sensitivity=edge_sensitivity,
               relief_cap=relief_cap, normals=normal_field, shades=shades,
               nmm_horizon=nmm_horizon)
```

Pass `material=` in the two `plan_region` calls:

```python
    # whole-mini leftover region:
        plans.append(plan_region(rgb, default_sub, lgt, WHOLE_MINI, default_palette,
                                 coverage, flat_albedo=flat,
                                 material=whole_material, **ekw))
    # drawn regions (inside the for loop):
        plans.append(plan_region(rgb, sub, lgt, r.name, r.palette, r.coverage,
                                 flat_albedo=flat, material=r.material, **ekw))
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `.venv/Scripts/python -m pytest tests/test_pipeline_nmm.py -v`
Expected: PASS (5 tests).

- [ ] **Step 6: Run the full pipeline regression suite (Path L byte-identical)**

Run: `.venv/Scripts/python -m pytest tests/test_pipeline.py tests/test_pipeline_light_field.py tests/test_pipeline_normal_field.py tests/test_pipeline_shades.py tests/test_relief_cap_pipeline.py tests/test_per_region_norm.py -v`
Expected: PASS (all existing pipeline tests — `material` defaults to `"matte"`, so nothing changes when NMM is unused).

- [ ] **Step 7: Commit**

```bash
git add src/mini_highlight_advisor/pipeline.py tests/test_pipeline_nmm.py
git commit -m "feat(pipeline): per-region NMM material re-bands from reflection environment"
```

---

### Task 4: UI — per-region Material selector + global Horizon slider (PS mode only)

**Files:**
- Modify: `ui/keys.py` (add two key constants)
- Modify: `ui/results.py` (add controls + thread into `analyze_regions`; controls ~after the `shades` block at lines 43-49, call at lines 82-90)
- Test: `tests/test_ui_nmm.py`

**Interfaces:**
- Consumes: `RegionBook.material_at` / `set_material_at` (Task 2); `analyze_regions(nmm_horizon=…, whole_material=…)` (Task 3).
- Produces: in PS mode (`normal_field is not None`), a `selectbox` labelled `Material — <region name>` and a `slider` labelled `Horizon height`; in photo mode neither renders.

- [ ] **Step 1: Write the failing tests**

```python
# tests/test_ui_nmm.py
from streamlit.testing.v1 import AppTest

# Mounts the real results.render() on the synthetic PS fixture, WITH the normal field
# (so NMM controls are capability-enabled).
HARNESS_PS = """
import numpy as np
from pathlib import Path
from PIL import Image
import streamlit as st
from mini_highlight_advisor import relight
from mini_highlight_advisor.region_state import new_book
from ui import results, keys

FIX = Path("tests/fixtures/ps")
normals = relight.load_normals(str(FIX / "synth_normal.png"))
mask = np.asarray(Image.open(FIX / "synth_mask.png").convert("L")) > 127
lf, relit = relight.relight(normals, mask, relight.light_dir(225, 45))
mask_u8 = (mask * 255).astype(np.uint8)
book = new_book(5)
st.session_state[keys.BOOK] = book
picked, owned = [], []
wp, wcov, drawn = book.analyze_args()
results.render(relit, mask_u8, book, wp, picked, owned, None,
               light_field=lf, normal_field=normals)
st.write("ok")
"""

# Photo mode: no light field, no normal field -> NMM controls must be absent.
HARNESS_PHOTO = """
import numpy as np
from pathlib import Path
from PIL import Image
import streamlit as st
from mini_highlight_advisor import relight
from mini_highlight_advisor.region_state import new_book
from ui import results, keys

FIX = Path("tests/fixtures/ps")
normals = relight.load_normals(str(FIX / "synth_normal.png"))
mask = np.asarray(Image.open(FIX / "synth_mask.png").convert("L")) > 127
_, relit = relight.relight(normals, mask, relight.light_dir(225, 45))
mask_u8 = (mask * 255).astype(np.uint8)
book = new_book(5)
st.session_state[keys.BOOK] = book
wp, wcov, drawn = book.analyze_args()
sh = type('S', (), {'mask': mask})()
results.render(relit, mask_u8, book, wp, [], [], sh)
st.write("ok")
"""


def test_ps_mode_shows_material_selector_and_horizon():
    at = AppTest.from_string(HARNESS_PS); at.run()
    assert not at.exception
    labels = [(s.label or "").lower() for s in at.selectbox]
    assert any("material" in l for l in labels)
    slider_labels = [(s.label or "").lower() for s in at.slider]
    assert any("horizon" in l for l in slider_labels)


def test_ps_mode_selecting_nmm_replans_without_error():
    at = AppTest.from_string(HARNESS_PS); at.run()
    mat = next(s for s in at.selectbox if "material" in (s.label or "").lower())
    mat.set_value("NMM").run()
    assert not at.exception
    assert len(at.image) > 0            # combined preview still renders


def test_photo_mode_hides_material_and_horizon():
    at = AppTest.from_string(HARNESS_PHOTO); at.run()
    assert not at.exception
    labels = [(s.label or "").lower() for s in at.selectbox]
    assert not any("material" in l for l in labels)
    slider_labels = [(s.label or "").lower() for s in at.slider]
    assert not any("horizon" in l for l in slider_labels)
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `.venv/Scripts/python -m pytest tests/test_ui_nmm.py -v`
Expected: FAIL (`test_ps_mode_shows_material_selector_and_horizon` — no selectbox/slider with those labels yet).

- [ ] **Step 3: Add the key constants**

In `ui/keys.py`, add (near the other editor keys):

```python
MATERIAL = "material_select"
NMM_HORIZON = "nmm_horizon"
```

- [ ] **Step 4: Render the controls in `ui/results.py`**

Insert, immediately after the `shades` block (after line ~49, before the `relief_cap` checkbox), a material selector for the currently-selected region plus the global horizon slider — both gated on `normal_field`:

```python
    nmm_horizon = 0.5
    if normal_field is not None:
        sel = book.selected
        cur = book.material_at(sel)
        choice = st.selectbox(
            f"Material — {book.names()[sel]}", ["Matte", "NMM"],
            index=0 if cur == "matte" else 1, key=keys.MATERIAL,
            help="NMM re-bands this region as non-metallic metal: it reads the "
                 "reflection of a virtual sky/ground off the surface normals. "
                 "PS mode only.")
        book.set_material_at(sel, "nmm" if choice == "NMM" else "matte")
        nmm_horizon = st.slider(
            "Horizon height", 0.0, 1.0, 0.5, 0.05, key=keys.NMM_HORIZON,
            help="Slide the virtual NMM horizon up (darker, more reflected ground) "
                 "or down (brighter, more sky). Affects NMM regions only.")
```

Then thread both into the `analyze_regions` call (the existing call ~lines 83-90) by adding two kwargs:

```python
    multi = analyze_regions(rgb, alpha, wp, wcov, drawn,
                            edges=edges, extreme_edge=extreme_edge,
                            edge_sensitivity=edge_sensitivity,
                            relief_cap=relief_cap,
                            per_region_norm=per_region_norm,
                            light_field=light_field,
                            normal_field=normal_field,
                            shades=shades,
                            nmm_horizon=nmm_horizon,
                            whole_material=book.material_at(0))
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `.venv/Scripts/python -m pytest tests/test_ui_nmm.py -v`
Expected: PASS (3 tests).

- [ ] **Step 6: Run the existing PS UI regression tests**

Run: `.venv/Scripts/python -m pytest tests/test_ui_results_ps.py tests/test_ui_ps_mode.py tests/test_ui_keys.py -v`
Expected: PASS (photo/PS toggles unchanged; the new controls don't disturb the existing harness, which passes no `normal_field`).

- [ ] **Step 7: Commit**

```bash
git add ui/keys.py ui/results.py tests/test_ui_nmm.py
git commit -m "feat(ui): PS-mode Material (Matte/NMM) selector + Horizon slider"
```

---

### Task 5 (optional, forward-compat): persist `material` in project files

Only needed if photometric-stereo projects ever become persistable (today PS is session-only, so this is a no-op for correctness — included so a future PS-persistence change doesn't silently drop the field). Skip if trimming scope.

**Files:**
- Modify: `src/mini_highlight_advisor/projects.py` (`_write_angle` ~lines 114-127; `_read_angle` ~lines 136-143; `_adapt_v1` ~lines 201-208)
- Test: `tests/test_projects.py` (append)

**Interfaces:**
- Consumes: `Region.material`, `RegionBook.whole_material` (Task 2).
- Produces: round-trip of `material` through save/load, defaulting to `"matte"` for pre-existing project files.

- [ ] **Step 1: Write the failing test**

```python
# append to tests/test_projects.py
def test_material_round_trips(tmp_path):
    # Build a book with an NMM drawn region, save, reload, assert material survives
    # and that a manifest missing "material" defaults to matte.
    import numpy as np
    from mini_highlight_advisor.region_state import new_book, RegionBook
    from mini_highlight_advisor.palette import default_ramp, default_coverage
    from mini_highlight_advisor import projects

    book = new_book(3)
    m = np.zeros((8, 8), bool); m[2:5, 2:5] = True
    book.add(m, "Blade", default_ramp(3), default_coverage(3))
    book.set_material_at(1, "nmm")
    book.set_material_at(0, "matte")

    reloaded = projects.roundtrip_book_for_test(book, tmp_path)   # see step 3
    assert reloaded.material_at(1) == "nmm"
    assert reloaded.material_at(0) == "matte"
```

> Note: `tests/test_projects.py` already exercises save/load; if it has a helper that saves an `AngleData` and reads it back, use that instead of `roundtrip_book_for_test` and drop the helper in step 3. Match the existing test's fixtures for `paints_pool`/`active_angle`.

- [ ] **Step 2: Run test to verify it fails**

Run: `.venv/Scripts/python -m pytest tests/test_projects.py -k material -v`
Expected: FAIL (material not written, so reload defaults everything to matte and index 1 assertion fails).

- [ ] **Step 3: Write `material` on save, read with default**

In `_write_angle`, add `material` to each drawn dict and the whole block:

```python
        drawn.append({"name": r.name, "palette": _palette_to_dicts(r.palette),
                      "coverage": list(r.coverage), "mask_file": mask_file,
                      "material": r.material})
    # ... in the "book" dict, whole entry:
        "book": {"whole": {"palette": _palette_to_dicts(a.book.whole_palette),
                           "coverage": list(a.book.whole_coverage),
                           "material": a.book.whole_material},
                 "drawn": drawn, "selected": a.book.selected},
```

In `_read_angle` and `_adapt_v1`, read with a default so old files load:

```python
        Region(name=d["name"], mask=_read_mask(angle_dir / d["mask_file"]),
               palette=_palette_from_dicts(d["palette"]), coverage=list(d["coverage"]),
               material=d.get("material", "matte"))
    # ... and RegionBook(...):
    book = RegionBook(whole_palette=_palette_from_dicts(b["whole"]["palette"]),
                      whole_coverage=list(b["whole"]["coverage"]),
                      whole_material=b["whole"].get("material", "matte"),
                      drawn=drawn, selected=b["selected"])
```

(Apply the same `whole_material=b["whole"].get("material", "matte")` in `_adapt_v1`.)

- [ ] **Step 4: Run test to verify it passes**

Run: `.venv/Scripts/python -m pytest tests/test_projects.py -v`
Expected: PASS (new test + existing project tests — old manifests without `material` still load via the `.get` default).

- [ ] **Step 5: Commit**

```bash
git add src/mini_highlight_advisor/projects.py tests/test_projects.py
git commit -m "feat(projects): persist per-region material (forward-compat, defaults matte)"
```

---

## Final verification

- [ ] **Run the whole suite:** `.venv/Scripts/python -m pytest`
  Expected: all green except the two pre-existing `test_ui_gallery.py` failures noted as unrelated in project history. If anything else fails, it is a regression from this work — fix before finishing.
- [ ] **Manual smoke (optional, requires a PS bundle):** `streamlit run app.py` → PS mode → import a normal/mask bundle → select a region → set Material = NMM → confirm the plan re-bands and the Horizon slider changes the light/dark split. Photo mode shows neither control.

## Self-review notes (traceability to spec)

- Spec §"New: materials.py" → Task 1. §"per-region material property" → Task 2. §"plan_region" + §"analyze_regions" → Task 3. §"UI" → Task 4 (consolidated into `results.py` for cohesion/testability, per plan-time decision; same capability gate + UX). §"Persistence" (optional forward-compat) → Task 5. §"Testing strategy" bullets map onto the tests in Tasks 1-4. Global constraints (Path L byte-identical, capability gate, convention, colors-from-palette) enforced by the regression steps in Tasks 3 & 4 and the fallback in Task 3.
