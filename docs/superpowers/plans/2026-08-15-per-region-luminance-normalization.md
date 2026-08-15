# Per-Region Luminance Normalization Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add an opt-in "colored / painted mini" mode that normalizes luminance per region (so each material reads its own relief independent of others' albedo), with a dynamic-range guard that gracefully caps dark/no-relief regions instead of inventing bands.

**Architecture:** Split `lighting.py`'s CLAHE and stretch steps so the stretch can run per-region; add `local_luminance_light` returning the region light plus a flat/dyn-range signal; thread a `per_region_norm` toggle through `analyze_regions`/`plan_region` (default off ⇒ today's global path is byte-for-byte unchanged); surface one checkbox + a dark-albedo warning in `app.py`.

**Tech Stack:** Python 3.11, numpy, opencv (cv2), Streamlit. Tests: pytest via `.venv/Scripts/python -m pytest`.

**Spec:** `docs/superpowers/specs/2026-08-15-per-region-luminance-normalization-design.md`

## Global Constraints

- **Primed path untouched:** with `per_region_norm=False` (the default), `analyze_regions` output must be identical to current `main`. This is a regression lock, not a nicety.
- **No new dependencies.** numpy + cv2 only.
- **Pure core / Streamlit-free engine:** all measurement lives in `lighting.py`/`pipeline.py`; `app.py` only renders.
- **Band convention:** `bands` is an int array, off-mask `-1`, band `0` darkest. Paint colours are float32 `(3,)` RGB.
- **Threshold placement (refines spec):** `FLAT_DYNRANGE_MIN` lives in `lighting.py`, not `banding.py` — the guard is computed inside `local_luminance_light` (in `lighting.py`), and putting the constant there avoids a `lighting → banding` import. Documented, tunable.
- **Test runner:** `.venv/Scripts/python -m pytest` (Windows venv).

---

### Task 1: Split `lighting.py` and add the per-region light + guard

**Files:**
- Modify: `src/mini_highlight_advisor/lighting.py`
- Test: `tests/test_lighting.py`

**Interfaces:**
- Consumes: nothing new (cv2, numpy).
- Produces:
  - `_clahe_gray(rgb: np.ndarray, clip_limit: float = 3.0) -> np.ndarray` — CLAHE-enhanced float32 gray, global.
  - `_stretch(gray: np.ndarray, mask: np.ndarray) -> np.ndarray` — p2..p98 within `mask` → [0,1], off-mask `0.0`.
  - `luminance_light(rgb, mask, clip_limit=3.0) -> np.ndarray` — unchanged public behavior; now `= _stretch(_clahe_gray(rgb, clip_limit), mask)`.
  - `FLAT_DYNRANGE_MIN: float = 25.0`
  - `LocalLight` dataclass: `light: np.ndarray`, `dyn_range: float`, `flat: bool`.
  - `local_luminance_light(gray: np.ndarray, sub_mask: np.ndarray) -> LocalLight` — `gray` is the shared `_clahe_gray` output; stretches `gray` within `sub_mask`, reports `dyn_range = p98-p2` of `gray[sub_mask]`, `flat = dyn_range < FLAT_DYNRANGE_MIN`.

- [ ] **Step 1: Write the failing tests**

Add to `tests/test_lighting.py`:

```python
import numpy as np
from mini_highlight_advisor.lighting import (
    luminance_light, _clahe_gray, _stretch,
    local_luminance_light, LocalLight, FLAT_DYNRANGE_MIN,
)


def test_luminance_light_equals_stretch_of_clahe_gray():
    # The split must preserve the public function exactly.
    rng = np.random.default_rng(1)
    rgb = rng.integers(0, 256, size=(24, 24, 3), dtype=np.uint8)
    mask = np.zeros((24, 24), dtype=bool)
    mask[4:20, 4:20] = True
    expected = _stretch(_clahe_gray(rgb), mask)
    np.testing.assert_array_equal(luminance_light(rgb, mask), expected)


def test_local_luminance_stretches_region_to_unit_and_zeros_outside():
    gray = np.zeros((10, 10), dtype=np.float32)
    sub = np.zeros((10, 10), dtype=bool)
    sub[2:8, 2:8] = True
    gray[sub] = np.linspace(40, 200, sub.sum(), dtype=np.float32)
    ll = local_luminance_light(gray, sub)
    assert isinstance(ll, LocalLight)
    assert np.all(ll.light[~sub] == 0.0)
    assert ll.light[sub].max() >= 0.99 and ll.light[sub].min() <= 0.01


def test_local_luminance_flat_flag_true_for_narrow_dark_region():
    gray = np.full((10, 10), 30.0, dtype=np.float32)  # near-constant
    sub = np.ones((10, 10), dtype=bool)
    ll = local_luminance_light(gray, sub)
    assert ll.dyn_range < FLAT_DYNRANGE_MIN
    assert ll.flat is True


def test_local_luminance_flat_flag_false_for_wide_range_region():
    gray = np.zeros((10, 10), dtype=np.float32)
    sub = np.ones((10, 10), dtype=bool)
    gray[:] = np.linspace(20, 200, 100, dtype=np.float32).reshape(10, 10)
    ll = local_luminance_light(gray, sub)
    assert ll.dyn_range >= FLAT_DYNRANGE_MIN
    assert ll.flat is False


def test_local_luminance_empty_mask_is_flat_and_zero():
    gray = np.full((6, 6), 100.0, dtype=np.float32)
    sub = np.zeros((6, 6), dtype=bool)
    ll = local_luminance_light(gray, sub)
    assert ll.flat is True
    assert ll.dyn_range == 0.0
    assert np.all(ll.light == 0.0)
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `.venv/Scripts/python -m pytest tests/test_lighting.py -v`
Expected: FAIL — `ImportError` on `_clahe_gray` / `local_luminance_light` / `LocalLight` / `FLAT_DYNRANGE_MIN`.

- [ ] **Step 3: Implement the split + new helpers**

Replace the body of `src/mini_highlight_advisor/lighting.py` with:

```python
from __future__ import annotations

from dataclasses import dataclass

import cv2
import numpy as np

# Raw CLAHE-gray p2..p98 range (0-255) a region needs before per-region stretching
# is trustworthy. Below this the region is dark/low-albedo with no relief dynamic
# range; stretching only amplifies sensor noise into fake bands, so the caller caps
# it to 1 band and warns. Starting value; tune against the synthetic fixtures.
FLAT_DYNRANGE_MIN = 25.0


def _clahe_gray(rgb: np.ndarray, clip_limit: float = 3.0) -> np.ndarray:
    gray = cv2.cvtColor(rgb, cv2.COLOR_RGB2GRAY)
    clahe = cv2.createCLAHE(clipLimit=clip_limit, tileGridSize=(8, 8))
    return clahe.apply(gray).astype(np.float32)


def _stretch(gray: np.ndarray, mask: np.ndarray) -> np.ndarray:
    inside = gray[mask]
    if inside.size == 0:
        return np.zeros(gray.shape, dtype=np.float32)
    lo, hi = np.percentile(inside, 2), np.percentile(inside, 98)
    light = np.clip((gray - lo) / (hi - lo + 1e-9), 0.0, 1.0).astype(np.float32)
    light[~mask] = 0.0
    return light


def luminance_light(rgb: np.ndarray, mask: np.ndarray, clip_limit: float = 3.0) -> np.ndarray:
    return _stretch(_clahe_gray(rgb, clip_limit), mask)


@dataclass
class LocalLight:
    light: np.ndarray   # region stretched to its own [0,1]; off-(sub)mask = 0
    dyn_range: float    # p98 - p2 of the region's raw CLAHE gray, 0..255 (pre-stretch)
    flat: bool          # dyn_range < FLAT_DYNRANGE_MIN


def local_luminance_light(gray: np.ndarray, sub_mask: np.ndarray) -> LocalLight:
    """Per-region light + relief signal. ``gray`` is a shared ``_clahe_gray`` output."""
    inside = gray[sub_mask]
    if inside.size == 0:
        return LocalLight(np.zeros(gray.shape, dtype=np.float32), 0.0, True)
    lo, hi = np.percentile(inside, [2, 98])
    dyn = float(hi - lo)
    return LocalLight(_stretch(gray, sub_mask), dyn, dyn < FLAT_DYNRANGE_MIN)
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `.venv/Scripts/python -m pytest tests/test_lighting.py -v`
Expected: PASS (all 5 new tests + the 3 pre-existing `luminance_*` tests).

- [ ] **Step 5: Commit**

```bash
git add src/mini_highlight_advisor/lighting.py tests/test_lighting.py
git commit -m "feat(lighting): split clahe/stretch + add local_luminance_light guard"
```

---

### Task 2: Thread `per_region_norm` + `flat_albedo` through the pipeline

**Files:**
- Modify: `src/mini_highlight_advisor/pipeline.py` (`RegionPlan`, `plan_region`, `analyze_regions`)
- Test: Create `tests/test_per_region_norm.py`

**Interfaces:**
- Consumes: `local_luminance_light`, `_clahe_gray`, `luminance_light` from Task 1.
- Produces:
  - `RegionPlan.flat_albedo: bool = False` (new field).
  - `plan_region(..., relief_cap=False, flat_albedo=False)` — when `flat_albedo=True`, cap to 1 band and set `capped=True`, `flat_albedo=True` (takes precedence over `relief_cap`).
  - `analyze_regions(..., relief_cap=False, per_region_norm=False)` — when `per_region_norm=True`, computes one shared `gray = _clahe_gray(rgb)`, and each region's light + flat flag come from `local_luminance_light(gray, sub)`. When `False`, unchanged.

- [ ] **Step 1: Write the failing tests**

Create `tests/test_per_region_norm.py`:

```python
import numpy as np

from mini_highlight_advisor.palette import DEFAULT_PALETTE, default_coverage
from mini_highlight_advisor.lighting import luminance_light
from mini_highlight_advisor.pipeline import analyze_regions, plan_region
from mini_highlight_advisor.regions import Region


def _varied_light(h=10, w=50):
    light = np.linspace(0.0, 1.0, h * w, dtype=np.float32).reshape(h, w)
    return light, np.ones((h, w), dtype=bool), np.zeros((h, w, 3), dtype=np.uint8)


def test_plan_region_flat_albedo_caps_to_one_band():
    light, sub, rgb = _varied_light()
    plan = plan_region(rgb, sub, light, "R", list(DEFAULT_PALETTE),
                       default_coverage(5), edges=False, flat_albedo=True)
    assert plan.flat_albedo is True
    assert plan.capped is True
    assert len(plan.colors) == 1
    assert plan.requested_bands == 5


def test_plan_region_flat_albedo_false_keeps_all_bands():
    light, sub, rgb = _varied_light()
    plan = plan_region(rgb, sub, light, "R", list(DEFAULT_PALETTE),
                       default_coverage(5), edges=False,
                       relief_cap=False, flat_albedo=False)
    assert plan.flat_albedo is False
    assert plan.capped is False
    assert len(plan.colors) == 5


def test_per_region_norm_off_uses_global_light_unchanged():
    # Regression lock: off path returns exactly the global luminance stretch.
    rgb = np.zeros((10, 50, 3), dtype=np.uint8)
    rgb[:] = np.linspace(0, 255, 50, dtype=np.uint8)[None, :, None]
    alpha = np.full((10, 50), 255, dtype=np.uint8)
    multi = analyze_regions(rgb, alpha, list(DEFAULT_PALETTE), default_coverage(5),
                            edges=False, per_region_norm=False)
    np.testing.assert_array_equal(multi.light, luminance_light(rgb, multi.mask))


def test_per_region_norm_on_flags_flat_dark_region():
    # Whole mini is a near-constant dark block -> guard fires.
    rgb = np.full((12, 12, 3), 30, dtype=np.uint8)
    alpha = np.full((12, 12), 255, dtype=np.uint8)
    multi = analyze_regions(rgb, alpha, list(DEFAULT_PALETTE), default_coverage(5),
                            edges=False, per_region_norm=True)
    whole = multi.plans[0]
    assert whole.flat_albedo is True
    assert len(whole.colors) == 1


def test_per_region_norm_recovers_dark_relief_region():
    # Left third bright (albedo high), right two-thirds dark but with real relief.
    # A vertical gradient gives each column-region its own shading ramp.
    rgb = np.zeros((20, 60, 3), dtype=np.uint8)
    ramp = np.linspace(0, 1, 20, dtype=np.float32)[:, None]        # dark->light top->bottom
    rgb[:, :20, :] = (120 + 100 * ramp).astype(np.uint8)          # bright region A
    rgb[:, 20:, :] = (30 + 40 * ramp).astype(np.uint8)            # dark region B, 30..70
    alpha = np.full((20, 60), 255, dtype=np.uint8)
    bmask = np.zeros((20, 60), dtype=bool)
    bmask[:, 20:] = True
    region_b = Region("B", bmask, list(DEFAULT_PALETTE), default_coverage(5))

    off = analyze_regions(rgb, alpha, list(DEFAULT_PALETTE), default_coverage(5),
                          regions=[region_b], edges=False,
                          relief_cap=True, per_region_norm=False)
    on = analyze_regions(rgb, alpha, list(DEFAULT_PALETTE), default_coverage(5),
                         regions=[region_b], edges=False,
                         relief_cap=True, per_region_norm=True)
    b_off = next(p for p in off.plans if p.name == "B")
    b_on = next(p for p in on.plans if p.name == "B")
    # Global stretch compresses B -> relief cap wrongly fires.
    assert b_off.capped and len(b_off.colors) < 5
    # Per-region stretch recovers B's real relief -> full bands, not flat.
    assert b_on.flat_albedo is False
    assert len(b_on.colors) == 5
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `.venv/Scripts/python -m pytest tests/test_per_region_norm.py -v`
Expected: FAIL — `plan_region` / `analyze_regions` reject `flat_albedo` / `per_region_norm` kwargs; `RegionPlan` has no `flat_albedo`.

- [ ] **Step 3: Add the `flat_albedo` field to `RegionPlan`**

In `src/mini_highlight_advisor/pipeline.py`, add to the `RegionPlan` dataclass (after `requested_bands`):

```python
    flat_albedo: bool = False
```

- [ ] **Step 4: Add the `flat_albedo` branch to `plan_region`**

Change the `plan_region` signature to add the kwarg:

```python
def plan_region(rgb, sub_mask, light, name, palette, coverage,
                edges: bool = True, extreme_edge: bool = False,
                edge_sensitivity: float = 0.5,
                relief_cap: bool = False, flat_albedo: bool = False) -> RegionPlan:
```

Replace the `capped = False` / `if relief_cap:` block with a guard-first version:

```python
    requested_bands = len(palette)
    capped = False
    if flat_albedo:
        # Dark/low-dynamic-range region: no relief signal to band. Keep the base only.
        capped = True
        palette = palette[:1]
        coverage = default_coverage(1)
    elif relief_cap:
        k = relief_recommended_bands(light, sub_mask, requested_bands)
        if k < requested_bands:
            # Keep the darkest k paints (base + lower highlights); a flat region
            # can't show the brightest highlights. Render-only — the caller's
            # stored palette/coverage are untouched.
            capped = True
            palette = palette[:k]
            coverage = default_coverage(k)
```

Update the final `return` to pass the flag:

```python
    return RegionPlan(name, sub_mask, bands, colors, names, roles, cov, steps, overlays,
                      capped=capped, requested_bands=requested_bands,
                      flat_albedo=flat_albedo)
```

- [ ] **Step 5: Thread `per_region_norm` through `analyze_regions`**

Add the import at the top of `pipeline.py` (extend the existing lighting import):

```python
from .lighting import luminance_light, _clahe_gray, local_luminance_light
```

Change the `analyze_regions` signature:

```python
def analyze_regions(rgb, alpha, default_palette, coverage=None, regions=None,
                    edges: bool = True, extreme_edge: bool = False,
                    edge_sensitivity: float = 0.5,
                    relief_cap: bool = False,
                    per_region_norm: bool = False) -> MultiRegionResult:
```

After `mask, light = shading.mask, shading.light` and the `owner`/`ekw` setup, add a per-region light resolver and use it for every `plan_region` call:

```python
    gray = _clahe_gray(rgb) if per_region_norm else None

    def _region_light(sub):
        if per_region_norm:
            ll = local_luminance_light(gray, sub)
            return ll.light, ll.flat
        return light, False

    if default_sub.any():
        lgt, flat = _region_light(default_sub)
        plans.append(plan_region(rgb, default_sub, lgt, WHOLE_MINI, default_palette,
                                 coverage, flat_albedo=flat, **ekw))
    for i, r in enumerate(regions):
        sub = owner == i
        if not sub.any():
            continue
        lgt, flat = _region_light(sub)
        plans.append(plan_region(rgb, sub, lgt, r.name, r.palette, r.coverage,
                                 flat_albedo=flat, **ekw))
```

(Remove the two old `plan_region(...)` calls that used the shared global `light`; `ekw` still carries `edges/extreme_edge/edge_sensitivity/relief_cap`. `MultiRegionResult.light` keeps the global `light` — it is only used for display, not per-region banding.)

- [ ] **Step 6: Run tests to verify they pass**

Run: `.venv/Scripts/python -m pytest tests/test_per_region_norm.py tests/test_relief_cap_pipeline.py tests/test_pipeline.py -v`
Expected: PASS. If `test_per_region_norm_recovers_dark_relief_region` is borderline on band count due to CLAHE, widen region A's brightness (e.g. `120 + 120*ramp`) so B is more compressed globally — the assertion intent (off caps B, on keeps 5) is what must hold.

- [ ] **Step 7: Commit**

```bash
git add src/mini_highlight_advisor/pipeline.py tests/test_per_region_norm.py
git commit -m "feat(pipeline): opt-in per-region luminance norm + dark-albedo guard"
```

---

### Task 3: Wire the opt-in checkbox + dark-albedo warning into the app

**Files:**
- Modify: `app.py` (checkbox near `app.py:492`; `analyze_regions` call `app.py:514`; per-plan render `app.py:524-531`)
- Test: manual (Streamlit UI) — `app.py` is the thin render layer; logic is covered by Tasks 1–2.

**Interfaces:**
- Consumes: `analyze_regions(..., per_region_norm=...)` and `RegionPlan.flat_albedo` from Task 2.
- Produces: no new public surface.

- [ ] **Step 1: Add the toggle checkbox**

In `app.py`, directly after the `relief_cap` checkbox block (ends `app.py:495`), add:

```python
        per_region_norm = st.checkbox(
            "Colored / painted mini (experimental)", value=False, key="per_region_norm",
            help="Normalize brightness per region so each painted colour reads its own "
                 "relief. Off = primed-mini mode (default). Needs one lassoed region per "
                 "material; very dark regions may be flagged as too low-contrast to read.")
```

- [ ] **Step 2: Pass it into `analyze_regions`**

Update the call at `app.py:514-517` to add the kwarg:

```python
        multi = analyze_regions(rgb, alpha, wp, wcov, drawn,
                                edges=edges, extreme_edge=extreme_edge,
                                edge_sensitivity=edge_sensitivity,
                                relief_cap=relief_cap,
                                per_region_norm=per_region_norm)
```

- [ ] **Step 3: Add the dark-albedo warning branch (before the generic cap message)**

In the per-plan loop (`app.py:524-531`), the `flat_albedo` case also sets `capped=True`, so it must be checked FIRST to give the specific message:

```python
        for plan in multi.plans:
            st.markdown(f"### {plan.name}")
            if plan.flat_albedo:
                st.warning(
                    f"“{plan.name}” is too dark / low-contrast to read relief — showing "
                    f"1 band. Try a paler basecoat here, or a stronger raking side light. "
                    f"(Single-photo tools can't recover form from a dark, flat colour.)")
            elif plan.capped:
                st.warning(
                    f"“{plan.name}” looks fairly flat — showing {len(plan.names)} "
                    f"band(s) instead of {plan.requested_bands}. Untick "
                    f"“Auto-reduce bands on flat regions” to force all "
                    f"{plan.requested_bands}.")
            _render_region_steps(plan.steps, plan.roles, plan.names, plan.coverage)
```

- [ ] **Step 4: Manual verification**

Run: `.venv/Scripts/streamlit run app.py`
Check:
1. Toggle **off** (default): primed fixture (`fixtures/skaven-hero/primed.png`) renders exactly as before.
2. Toggle **on** with a real painted photo + at least one lassoed region: each region's highlight plan reads its own relief; a very dark region shows the dark-albedo warning and a single band.
Expected: both behave as described; no exceptions.

- [ ] **Step 5: Run the full suite**

Run: `.venv/Scripts/python -m pytest`
Expected: PASS (all green, including the pre-existing suite unchanged).

- [ ] **Step 6: Commit**

```bash
git add app.py
git commit -m "feat(app): colored-mini toggle + dark-albedo region warning"
```

---

## Self-Review

**Spec coverage:**
- Trigger = opt-in toggle → Task 3 checkbox (default off); off-path regression lock → Task 2 `test_per_region_norm_off_uses_global_light_unchanged`. ✓
- `lighting.py` split (`_clahe_gray`/`_stretch`/identical `luminance_light`) → Task 1. ✓
- `local_luminance_light` + `LocalLight` (light/dyn_range/flat) → Task 1. ✓
- Dark-albedo dynamic-range guard (`FLAT_DYNRANGE_MIN`) → Task 1 (constant + flag), Task 2 (`flat_albedo` caps to 1 band). ✓
- `per_region_norm` threaded through `analyze_regions`/`plan_region`; shared single CLAHE → Task 2 Step 5. ✓
- `RegionPlan.flat_albedo` flag → Task 2 Step 3. ✓
- UI: checkbox + dark-albedo message distinct from generic cap → Task 3. ✓
- Recovery demonstrated (global crush vs per-region recovery) → Task 2 `test_per_region_norm_recovers_dark_relief_region`. ✓
- Non-goals (no auto-detection, no multi-colour-within-region, no edge/step changes) → nothing added for them. ✓

**Placeholder scan:** No TBD/TODO; every code + test block is concrete; `FLAT_DYNRANGE_MIN=25.0` is a documented tunable constant, not a gap. ✓

**Type consistency:** `_clahe_gray`, `_stretch`, `local_luminance_light`, `LocalLight(light,dyn_range,flat)`, `flat_albedo`, `per_region_norm` names match across Tasks 1→2→3. `plan_region`/`analyze_regions` signatures consistent with call sites. ✓
