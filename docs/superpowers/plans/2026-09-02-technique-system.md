# Technique System Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a technique registry (`smooth` + `drybrush`) that gives each region technique-specific role names, coverage notes, and step captions — with fur/drybrush as the first worked material.

**Architecture:** New pure module `techniques.py` holds `TechniqueSpec` (role names, coverage notes, step captions) and a registry `TECHNIQUES`. `RegionPlan` gains a `technique` field. `plan_region` uses `get_technique(technique).role_names(n)` instead of `palette.role_names(n)`. `render_region_steps` in `ui/helpers.py` adjusts the step captions per technique. `render_legend` in `overlay.py` gains an optional `coverage_notes` param. The technique picker in `results.py` is shown in all modes (not just PS mode). Zero new rendering math — `drybrush` uses the same luminance shading as `smooth`; only guide text changes.

**Tech Stack:** Python 3.11, numpy, Streamlit; pytest via `.venv/Scripts/python -m pytest`.

**Spec:** `docs/superpowers/specs/2026-09-02-technique-system-design.md`

## Global Constraints

- **Path L byte-identical:** `technique="drybrush"` must produce the same `bands` array as `technique="smooth"` on identical inputs. Every task that touches `plan_region` carries a regression assertion.
- **Back-compat:** `"matte"` in saved projects must continue to work. `get_technique("matte")` returns the smooth spec via alias. No persistence migration needed.
- **Torch-free / Streamlit-free:** `techniques.py` imports only stdlib. No `streamlit` import.
- **Branch:** `feat/technique-system` (already created; spec committed on it).
- **Run tests with:** `.venv/Scripts/python -m pytest`

---

### Task 1: `techniques.py` — TechniqueSpec + smooth + drybrush + tests

**Files:**
- Create: `src/mini_highlight_advisor/techniques.py`
- Create: `tests/test_techniques.py`

**Interfaces:**
- Produces:
  - `StepCaptions(across: str, stays: str)` — format strings containing `{pct:.0f}`
  - `TechniqueSpec(name, display, description, _roles, _coverage_notes, captions)` with methods `role_names(n: int) -> list[str]` and `coverage_note(role: str) -> str`
  - `TECHNIQUES: dict[str, TechniqueSpec]` — keys `"smooth"`, `"matte"` (alias), `"drybrush"`
  - `get_technique(name: str) -> TechniqueSpec` — falls back to smooth for unknown values

---

- [ ] **Step 1: Write the failing tests**

Create `tests/test_techniques.py`:

```python
# tests/test_techniques.py
import pytest
from mini_highlight_advisor.palette import role_names as palette_role_names


def test_smooth_role_names_match_palette_for_n_3_to_7():
    from mini_highlight_advisor.techniques import get_technique
    spec = get_technique("smooth")
    for n in range(3, 8):
        assert spec.role_names(n) == palette_role_names(n), \
            f"smooth.role_names({n}) must equal palette.role_names({n})"


def test_smooth_unknown_n_returns_generic_labels():
    from mini_highlight_advisor.techniques import get_technique
    spec = get_technique("smooth")
    assert spec.role_names(1) == ["Layer 1"]
    assert spec.role_names(2) == ["Layer 1", "Layer 2"]


def test_drybrush_role_names_correct_length_for_all_n():
    from mini_highlight_advisor.techniques import get_technique
    spec = get_technique("drybrush")
    for n in range(1, 8):
        roles = spec.role_names(n)
        assert len(roles) == n, f"drybrush.role_names({n}) returned {len(roles)} items"


def test_drybrush_base_coat_always_first():
    from mini_highlight_advisor.techniques import get_technique
    spec = get_technique("drybrush")
    for n in range(1, 8):
        assert spec.role_names(n)[0] == "Base coat"


def test_drybrush_fine_highlight_at_n5():
    from mini_highlight_advisor.techniques import get_technique
    spec = get_technique("drybrush")
    assert spec.role_names(5)[-1] == "Fine highlight"


def test_matte_alias_returns_same_object_as_smooth():
    from mini_highlight_advisor.techniques import get_technique
    assert get_technique("matte") is get_technique("smooth")


def test_unknown_technique_falls_back_to_smooth():
    from mini_highlight_advisor.techniques import get_technique
    assert get_technique("totally_unknown") is get_technique("smooth")


def test_smooth_coverage_note_shadow():
    from mini_highlight_advisor.techniques import get_technique
    spec = get_technique("smooth")
    assert spec.coverage_note("Shadow") == "deepest recesses"


def test_drybrush_coverage_note_base_coat_mentions_recess():
    from mini_highlight_advisor.techniques import get_technique
    spec = get_technique("drybrush")
    assert "recess" in spec.coverage_note("Base coat")


def test_smooth_captions_contain_pct_placeholder():
    from mini_highlight_advisor.techniques import get_technique
    spec = get_technique("smooth")
    assert "{pct" in spec.captions.across
    assert "{pct" in spec.captions.stays


def test_drybrush_captions_mention_drybrush():
    from mini_highlight_advisor.techniques import get_technique
    spec = get_technique("drybrush")
    assert "rybrush" in spec.captions.across.lower()


def test_smooth_captions_format_with_pct():
    from mini_highlight_advisor.techniques import get_technique
    spec = get_technique("smooth")
    result = spec.captions.across.format(pct=42.5)
    assert "42" in result


def test_drybrush_captions_format_with_pct():
    from mini_highlight_advisor.techniques import get_technique
    spec = get_technique("drybrush")
    result = spec.captions.stays.format(pct=15.0)
    assert "15" in result
```

- [ ] **Step 2: Run tests to confirm they fail**

```
.venv/Scripts/python -m pytest tests/test_techniques.py -v
```
Expected: FAIL with `ModuleNotFoundError: No module named 'mini_highlight_advisor.techniques'`.

- [ ] **Step 3: Write `techniques.py`**

Create `src/mini_highlight_advisor/techniques.py`:

```python
# src/mini_highlight_advisor/techniques.py
"""Technique registry: maps technique names to role names, coverage notes, and
step captions. Torch-free, Streamlit-free.

Each technique describes HOW paint is applied in a region:
  smooth   — classic glazed layers, dark-to-light (the original behaviour)
  drybrush — nearly-dry brush dragged across raised surfaces (fur, chainmail, cloth)

NMM and OSL are future entries; the registry shape accommodates them without
restructuring. Add an entry to TECHNIQUES and a get_technique() call picks it up.
"""
from __future__ import annotations

from dataclasses import dataclass


@dataclass
class StepCaptions:
    """Per-technique caption strings for the two step-image columns.

    Both strings are Python format strings containing ``{pct:.0f}``
    (the band's percentage coverage) and nothing else.
    """
    across: str   # caption for the "apply across" column
    stays: str    # caption for the "stays this colour" column


@dataclass
class TechniqueSpec:
    """A technique: how paint is applied, and what to call each layer."""
    name: str
    display: str          # shown in the UI picker
    description: str      # tooltip text
    _roles: dict[int, list[str]]      # n -> role names, dark to light
    _coverage_notes: dict[str, str]   # role name -> application note
    captions: StepCaptions

    def role_names(self, n: int) -> list[str]:
        """Return n role names for this technique.

        Uses the per-n table when available; falls back to generic
        "Layer 1 … Layer n" for n values not in the table.
        """
        if n in self._roles:
            return list(self._roles[n])
        return [f"Layer {i + 1}" for i in range(n)]

    def coverage_note(self, role: str) -> str:
        """Short application note for a role name; empty string if unknown."""
        return self._coverage_notes.get(role, "")


_SMOOTH = TechniqueSpec(
    name="smooth",
    display="Smooth layering",
    description="Classic glazed layers, working dark to light.",
    _roles={
        3: ["Shadow", "Base", "Highlight"],
        4: ["Shadow", "Base", "Midtone", "Highlight"],
        5: ["Shadow", "Base", "Midtone", "Highlight", "Bright Highlight"],
        6: ["Shadow", "Deep Base", "Base", "Midtone", "Highlight", "Bright Highlight"],
        7: ["Shadow", "Deep Base", "Base", "Midtone", "Upper Midtone",
            "Highlight", "Bright Highlight"],
    },
    _coverage_notes={
        "Shadow":                  "deepest recesses",
        "Base":                    "the main body of the surface",
        "Deep Base":               "deep base tone, below midtone",
        "Midtone":                 "flat, gently-lit panels",
        "Upper Midtone":           "upper midtone transitional zone",
        "Highlight":               "raised areas facing the light",
        "Bright Highlight":        "the brightest broad zones",
        "Edge Highlight":          "the crisp lit rim of every plate",
        "Extreme Edge Highlight":  "sharpest edges only, the final pop",
    },
    captions=StepCaptions(
        across="Apply across — whole area (~{pct:.0f}%)",
        stays="Stays this colour — final (~{pct:.0f}%)",
    ),
)

_DRYBRUSH = TechniqueSpec(
    name="drybrush",
    display="Drybrush",
    description=(
        "Drag a nearly-dry brush across raised surfaces — "
        "fur, chainmail, cloth, textured bases."
    ),
    _roles={
        1: ["Base coat"],
        2: ["Base coat", "Drybrush"],
        3: ["Base coat", "Drybrush", "Highlight drybrush"],
        4: ["Base coat", "First drybrush", "Second drybrush", "Highlight drybrush"],
        5: ["Base coat", "First drybrush", "Second drybrush",
            "Highlight drybrush", "Fine highlight"],
        6: ["Base coat", "First drybrush", "Second drybrush",
            "Highlight drybrush", "Fine highlight", "Tip highlight"],
        7: ["Base coat", "First drybrush", "Second drybrush",
            "Highlight drybrush", "Fine highlight", "Tip highlight", "Specular tip"],
    },
    _coverage_notes={
        "Base coat":          "basecoat or wash into every recess — your darkest colour",
        "Drybrush":           "drybrush across the whole textured surface",
        "First drybrush":     "heavy drybrush across the whole textured surface",
        "Second drybrush":    "medium drybrush, slightly less pressure",
        "Highlight drybrush": "light drybrush, raised peaks and strands only",
        "Fine highlight":     "barely-dry brush on the sharpest raised tips",
        "Tip highlight":      "almost no paint — crisp topmost fibres only",
        "Specular tip":       "near-white on the very sharpest peaks",
    },
    captions=StepCaptions(
        across="Drybrush across raised areas (~{pct:.0f}%)",
        stays="Peak colour — this zone only (~{pct:.0f}%)",
    ),
)

TECHNIQUES: dict[str, TechniqueSpec] = {
    "smooth":   _SMOOTH,
    "matte":    _SMOOTH,    # back-compat alias for projects saved before this feature
    "drybrush": _DRYBRUSH,
}


def get_technique(name: str) -> TechniqueSpec:
    """Return the TechniqueSpec for name; falls back to smooth for unknown values."""
    return TECHNIQUES.get(name, _SMOOTH)
```

- [ ] **Step 4: Run tests to confirm they pass**

```
.venv/Scripts/python -m pytest tests/test_techniques.py -v
```
Expected: all 13 tests PASS.

- [ ] **Step 5: Run the full suite to check no regressions**

```
.venv/Scripts/python -m pytest
```
Expected: same results as before (pre-existing `test_ui_gallery.py` failures are the only failures).

- [ ] **Step 6: Commit**

```
git add src/mini_highlight_advisor/techniques.py tests/test_techniques.py
git commit -m "feat: technique registry — TechniqueSpec + smooth + drybrush"
```

---

### Task 2: `pipeline.py` — RegionPlan.technique + plan_region uses spec role names

**Files:**
- Modify: `src/mini_highlight_advisor/pipeline.py`
- Create: `tests/test_pipeline_technique.py`

**Interfaces:**
- Consumes: `get_technique` from Task 1
- Produces:
  - `RegionPlan.technique: str` — the technique name carried through to the UI
  - `plan_region(..., technique: str = "smooth") -> RegionPlan` — extended signature
  - `analyze_regions` passes each region's `material` value as `technique` to `plan_region`

---

- [ ] **Step 1: Write the failing tests**

Create `tests/test_pipeline_technique.py`:

```python
# tests/test_pipeline_technique.py
import numpy as np
import pytest

from mini_highlight_advisor.pipeline import plan_region, analyze_regions, WHOLE_MINI
from mini_highlight_advisor.palette import DEFAULT_PALETTE, default_coverage, role_names as palette_role_names
from mini_highlight_advisor.regions import Region


def _flat_light(h=32, w=32):
    light = np.linspace(0.1, 0.9, h * w, dtype=np.float32).reshape(h, w)
    mask = np.ones((h, w), dtype=bool)
    return light, mask


def _rgb(h=32, w=32):
    rng = np.random.default_rng(42)
    return rng.integers(100, 200, (h, w, 3), dtype=np.uint8)


PAL = DEFAULT_PALETTE[:5]
COV = default_coverage(5)


def test_plan_region_default_technique_is_smooth():
    light, mask = _flat_light()
    plan = plan_region(_rgb(), mask, light, "test", PAL, COV, edges=False)
    assert plan.technique == "smooth"


def test_plan_region_smooth_roles_match_palette_role_names():
    """Regression lock: smooth technique produces the same role names as before."""
    light, mask = _flat_light()
    plan = plan_region(_rgb(), mask, light, "test", PAL, COV, edges=False, technique="smooth")
    expected = palette_role_names(len(PAL))
    assert plan.roles == expected, f"expected {expected}, got {plan.roles}"


def test_plan_region_drybrush_technique_field():
    light, mask = _flat_light()
    plan = plan_region(_rgb(), mask, light, "test", PAL, COV, edges=False, technique="drybrush")
    assert plan.technique == "drybrush"


def test_plan_region_drybrush_roles_start_with_base_coat():
    light, mask = _flat_light()
    plan = plan_region(_rgb(), mask, light, "test", PAL, COV, edges=False, technique="drybrush")
    assert plan.roles[0] == "Base coat"
    assert len(plan.roles) == len(PAL)


def test_plan_region_drybrush_bands_byte_identical_to_smooth():
    """CRITICAL: drybrush must not change band placement — only text changes."""
    light, mask = _flat_light()
    rgb = _rgb()
    p_smooth = plan_region(rgb, mask, light, "test", PAL, COV, edges=False, technique="smooth")
    p_dry = plan_region(rgb, mask, light, "test", PAL, COV, edges=False, technique="drybrush")
    np.testing.assert_array_equal(
        p_smooth.bands, p_dry.bands,
        err_msg="drybrush must produce byte-identical band placement to smooth")


def test_plan_region_matte_alias_same_as_smooth():
    light, mask = _flat_light()
    rgb = _rgb()
    p_matte = plan_region(rgb, mask, light, "test", PAL, COV, edges=False, technique="matte")
    p_smooth = plan_region(rgb, mask, light, "test", PAL, COV, edges=False, technique="smooth")
    assert p_matte.roles == p_smooth.roles
    assert p_matte.technique == "smooth"


def test_analyze_regions_drybrush_region_carries_technique():
    rng = np.random.default_rng(0)
    rgb = rng.integers(50, 200, (64, 64, 3), dtype=np.uint8)
    alpha = np.full((64, 64), 255, dtype=np.uint8)
    region_mask = np.zeros((64, 64), dtype=bool)
    region_mask[10:30, 10:30] = True
    pal3 = DEFAULT_PALETTE[:3]
    r = Region("fur", region_mask, pal3, default_coverage(3), material="drybrush")
    result = analyze_regions(rgb, alpha, DEFAULT_PALETTE[:5], regions=[r], edges=False)
    fur_plan = next(p for p in result.plans if p.name == "fur")
    assert fur_plan.technique == "drybrush"
    assert fur_plan.roles[0] == "Base coat"


def test_analyze_regions_whole_mini_technique_defaults_to_smooth():
    rng = np.random.default_rng(1)
    rgb = rng.integers(50, 200, (64, 64, 3), dtype=np.uint8)
    alpha = np.full((64, 64), 255, dtype=np.uint8)
    result = analyze_regions(rgb, alpha, DEFAULT_PALETTE[:5], edges=False)
    whole = next(p for p in result.plans if p.name == WHOLE_MINI)
    assert whole.technique == "smooth"
```

- [ ] **Step 2: Run tests to confirm they fail**

```
.venv/Scripts/python -m pytest tests/test_pipeline_technique.py -v
```
Expected: FAIL — `RegionPlan` has no `technique` attribute; `plan_region` doesn't accept `technique=`.

- [ ] **Step 3: Add `technique` to `RegionPlan`**

In `src/mini_highlight_advisor/pipeline.py`, add `technique: str = "smooth"` to `RegionPlan`:

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
    capped: bool = False
    requested_bands: int | None = None
    flat_albedo: bool = False
    technique: str = "smooth"          # ← add this
```

- [ ] **Step 4: Add `technique` param to `plan_region` and use spec role names**

At the top of `pipeline.py`, add to the imports (after the existing imports from `.palette`):

```python
from .techniques import get_technique
```

In `plan_region`'s signature, add `technique: str = "smooth"` after `nmm_horizon`:

```python
def plan_region(rgb, sub_mask, light, name, palette, coverage,
                edges: bool = True, extreme_edge: bool = False,
                edge_sensitivity: float = 0.5,
                relief_cap: bool = False, flat_albedo: bool = False,
                normals: np.ndarray | None = None,
                shades: bool = False,
                material: str = "matte", nmm_horizon: float = 0.5,
                technique: str = "smooth") -> RegionPlan:
```

Inside `plan_region`, replace the line:

```python
    roles = role_names(len(palette))
```

with:

```python
    spec = get_technique(technique)
    roles = spec.role_names(len(palette))
```

At the closing `return RegionPlan(...)` line, add `technique=spec.name`:

```python
    return RegionPlan(name, sub_mask, bands, colors, names, roles, cov, steps, overlays,
                      capped=capped, requested_bands=requested_bands,
                      flat_albedo=flat_albedo, technique=spec.name)
```

- [ ] **Step 5: Pass `technique` through `analyze_regions`**

In `analyze_regions`, the `ekw` dict is passed to each `plan_region` call. Add `technique` to each call site directly (not via `ekw`, since the whole-mini and drawn regions have different techniques):

Find the two `plan_region` calls inside `analyze_regions`:

```python
    if default_sub.any():
        lgt, flat = _region_light(default_sub)
        plans.append(plan_region(rgb, default_sub, lgt, WHOLE_MINI, default_palette,
                                 coverage, flat_albedo=flat,
                                 material=whole_material, **ekw))
    for i, r in enumerate(regions):
        sub = owner == i
        if not sub.any():
            continue
        lgt, flat = _region_light(sub)
        plans.append(plan_region(rgb, sub, lgt, r.name, r.palette, r.coverage,
                                 flat_albedo=flat, material=r.material, **ekw))
```

Change to pass `technique=` alongside `material=`:

```python
    if default_sub.any():
        lgt, flat = _region_light(default_sub)
        plans.append(plan_region(rgb, default_sub, lgt, WHOLE_MINI, default_palette,
                                 coverage, flat_albedo=flat,
                                 material=whole_material, technique=whole_material, **ekw))
    for i, r in enumerate(regions):
        sub = owner == i
        if not sub.any():
            continue
        lgt, flat = _region_light(sub)
        plans.append(plan_region(rgb, sub, lgt, r.name, r.palette, r.coverage,
                                 flat_albedo=flat, material=r.material,
                                 technique=r.material, **ekw))
```

Note: `technique=r.material` passes the same string as `material`; `get_technique("matte")` returns the smooth spec via alias, so old projects are unaffected.

- [ ] **Step 6: Run the new tests**

```
.venv/Scripts/python -m pytest tests/test_pipeline_technique.py -v
```
Expected: all 8 tests PASS.

- [ ] **Step 7: Run the full suite**

```
.venv/Scripts/python -m pytest
```
Expected: all pass (same pre-existing failures only). In particular `test_pipeline.py` and `test_pipeline_nmm.py` must still pass — they exercise the byte-identical regression path.

- [ ] **Step 8: Commit**

```
git add src/mini_highlight_advisor/pipeline.py tests/test_pipeline_technique.py
git commit -m "feat(pipeline): RegionPlan.technique + plan_region uses technique spec role names"
```

---

### Task 3: `overlay.py` — `render_legend` accepts `coverage_notes` param

**Files:**
- Modify: `src/mini_highlight_advisor/overlay.py`
- Modify: `tests/test_overlay.py` (add one test)

**Interfaces:**
- Consumes: nothing new
- Produces: `render_legend(colors, names, roles, coverage, height, width=430, coverage_notes=None)` — `coverage_notes` is `dict[str, str] | None`; `None` keeps the existing `_COVERAGE_NOTES` lookup

---

- [ ] **Step 1: Write the failing test**

Append to `tests/test_overlay.py`:

```python
def test_render_legend_accepts_custom_coverage_notes():
    from mini_highlight_advisor.overlay import render_legend
    import numpy as np
    colors = [np.array([100, 50, 200], np.float32) for _ in range(3)]
    names = ["Base coat", "First drybrush", "Highlight drybrush"]
    roles = ["Base coat", "First drybrush", "Highlight drybrush"]
    coverage = [50.0, 30.0, 20.0]
    custom_notes = {
        "Base coat": "wash into recesses",
        "First drybrush": "heavy drybrush",
        "Highlight drybrush": "light drybrush on peaks",
    }
    # Must not raise; returns an Image
    img = render_legend(colors, names, roles, coverage, height=300,
                        coverage_notes=custom_notes)
    assert img is not None
```

- [ ] **Step 2: Run test to confirm it fails**

```
.venv/Scripts/python -m pytest tests/test_overlay.py::test_render_legend_accepts_custom_coverage_notes -v
```
Expected: FAIL — `render_legend()` got an unexpected keyword argument `coverage_notes`.

- [ ] **Step 3: Add `coverage_notes` param to `render_legend`**

In `src/mini_highlight_advisor/overlay.py`, update the `render_legend` signature:

```python
def render_legend(colors, names, roles, coverage, height: int, width: int = 430,
                  coverage_notes: dict | None = None) -> Image.Image:
```

Inside the function, replace the line:

```python
        note = _COVERAGE_NOTES.get(roles[i], "")
```

with:

```python
        notes = coverage_notes if coverage_notes is not None else _COVERAGE_NOTES
        note = notes.get(roles[i], "")
```

(Place the `notes = ...` line once, before the loop that iterates `range(n)`.)

- [ ] **Step 4: Run all overlay tests**

```
.venv/Scripts/python -m pytest tests/test_overlay.py -v
```
Expected: all PASS including the new test.

- [ ] **Step 5: Commit**

```
git add src/mini_highlight_advisor/overlay.py tests/test_overlay.py
git commit -m "feat(overlay): render_legend accepts optional coverage_notes dict"
```

---

### Task 4: `ui/helpers.py` — technique-aware step captions

**Files:**
- Modify: `ui/helpers.py`
- Create: `tests/test_ui_technique_captions.py`

**Interfaces:**
- Consumes: `get_technique` from Task 1; `RegionPlan.technique` from Task 2
- Produces: `render_region_steps(steps, roles, names, coverage, technique="smooth")` — new `technique` param; callers must pass `plan.technique`

---

- [ ] **Step 1: Write the failing AppTest**

Create `tests/test_ui_technique_captions.py`:

```python
# tests/test_ui_technique_captions.py
"""Verify that render_region_steps shows technique-specific captions."""
import numpy as np
from pathlib import Path
from PIL import Image
from streamlit.testing.v1 import AppTest

FIX = Path("tests/fixtures/ps")

# Harness: seeds PS state + a 3-band drybrush plan, then calls render_region_steps.
# We check that the output contains a drybrush-specific caption substring.
HARNESS_DRYBRUSH_CAPTIONS = """
import numpy as np
import streamlit as st
from mini_highlight_advisor.overlay import BandStep
from ui.helpers import render_region_steps

# Synthetic 3-step plan (no real images needed — just small arrays)
h, w = 8, 8
zone  = np.zeros((h, w, 3), dtype=np.uint8)
cum   = np.zeros((h, w, 3), dtype=np.uint8)
exact = np.zeros((h, w, 3), dtype=np.uint8)

steps = [
    BandStep(index=0, zone_rgb=zone, cumulative_rgb=cum, exact_rgb=exact,
             is_last=False, kind="band"),
    BandStep(index=1, zone_rgb=zone, cumulative_rgb=cum, exact_rgb=exact,
             is_last=False, kind="band"),
    BandStep(index=2, zone_rgb=zone, cumulative_rgb=cum, exact_rgb=cum,
             is_last=True, kind="band"),
]
roles    = ["Base coat", "Drybrush", "Highlight drybrush"]
names    = ["Wash Black", "Brown", "Bone"]
coverage = [40.0, 35.0, 25.0]

render_region_steps(steps, roles, names, coverage, technique="drybrush")
st.write("done")
"""

HARNESS_SMOOTH_CAPTIONS = """
import numpy as np
import streamlit as st
from mini_highlight_advisor.overlay import BandStep
from ui.helpers import render_region_steps

h, w = 8, 8
zone  = np.zeros((h, w, 3), dtype=np.uint8)
cum   = np.zeros((h, w, 3), dtype=np.uint8)
exact = np.zeros((h, w, 3), dtype=np.uint8)

steps = [
    BandStep(index=0, zone_rgb=zone, cumulative_rgb=cum, exact_rgb=exact,
             is_last=False, kind="band"),
    BandStep(index=1, zone_rgb=zone, cumulative_rgb=cum, exact_rgb=exact,
             is_last=True, kind="band"),
]
roles    = ["Shadow", "Highlight"]
names    = ["Black", "White"]
coverage = [60.0, 40.0]

render_region_steps(steps, roles, names, coverage, technique="smooth")
st.write("done")
"""


def test_drybrush_captions_render_without_error():
    at = AppTest.from_string(HARNESS_DRYBRUSH_CAPTIONS)
    at.run()
    assert not at.exception


def test_smooth_captions_render_without_error():
    at = AppTest.from_string(HARNESS_SMOOTH_CAPTIONS)
    at.run()
    assert not at.exception


def test_drybrush_captions_default_smooth_no_error():
    # Calling render_region_steps without technique= must still work (back-compat).
    harness = HARNESS_SMOOTH_CAPTIONS.replace(
        "render_region_steps(steps, roles, names, coverage, technique=\"smooth\")",
        "render_region_steps(steps, roles, names, coverage)",
    )
    at = AppTest.from_string(harness)
    at.run()
    assert not at.exception
```

- [ ] **Step 2: Run tests to confirm they fail**

```
.venv/Scripts/python -m pytest tests/test_ui_technique_captions.py -v
```
Expected: FAIL — `render_region_steps()` doesn't accept `technique=`.

- [ ] **Step 3: Update `render_region_steps` in `ui/helpers.py`**

Add the import at the top of `ui/helpers.py` (after existing imports):

```python
from mini_highlight_advisor.techniques import get_technique
```

Change the function signature:

```python
def render_region_steps(steps, roles, names, coverage, technique: str = "smooth") -> None:
```

Inside the function body, add one line before the `for step in steps:` loop:

```python
    _spec = get_technique(technique)
```

Then replace the two hardcoded caption strings:

Old:
```python
            c2.image(step.cumulative_rgb, caption=f"Apply across — whole area (~{cum_cov:.0f}%)", use_container_width=True)
```
New:
```python
            c2.image(step.cumulative_rgb,
                     caption=_spec.captions.across.format(pct=cum_cov),
                     use_container_width=True)
```

Old:
```python
            c3.image(step.exact_rgb, caption=f"Stays this colour — final (~{cov:.0f}%)", use_container_width=True)
```
New:
```python
            c3.image(step.exact_rgb,
                     caption=_spec.captions.stays.format(pct=cov),
                     use_container_width=True)
```

(There are two `c2.image` / `c3.image` blocks — one inside `if step.is_last` (only `c2`) and one in the `else` branch (both `c2` and `c3`). Update the `c2` caption in the `is_last` branch too, and both captions in the `else` branch.)

- [ ] **Step 4: Update the caller in `results.py`**

In `ui/results.py`, find the line:

```python
        helpers.render_region_steps(plan.steps, plan.roles, plan.names, plan.coverage)
```

Change to:

```python
        helpers.render_region_steps(plan.steps, plan.roles, plan.names, plan.coverage,
                                    technique=plan.technique)
```

- [ ] **Step 5: Run the new tests**

```
.venv/Scripts/python -m pytest tests/test_ui_technique_captions.py -v
```
Expected: all 3 tests PASS.

- [ ] **Step 6: Run the full suite**

```
.venv/Scripts/python -m pytest
```
Expected: all pass (pre-existing failures only).

- [ ] **Step 7: Commit**

```
git add ui/helpers.py ui/results.py tests/test_ui_technique_captions.py
git commit -m "feat(ui): technique-aware step captions in render_region_steps"
```

---

### Task 5: `ui/results.py` — always-visible technique picker

**Files:**
- Modify: `ui/results.py`
- Create: `tests/test_ui_technique_picker.py`

**Interfaces:**
- Consumes: `RegionBook.material_at(g)`, `RegionBook.set_material_at(g, value)`, `keys.material(i)`
- Produces: technique selectbox always visible (not PS-only); "Smooth layering" and "Drybrush" in all modes; "NMM" added only when `normal_field is not None`; NMM horizon slider stays PS-only

---

- [ ] **Step 1: Write the failing AppTest**

Create `tests/test_ui_technique_picker.py`:

```python
# tests/test_ui_technique_picker.py
"""Technique picker is visible in simple-image mode and PS mode."""
import numpy as np
from pathlib import Path
from PIL import Image
from streamlit.testing.v1 import AppTest
from mini_highlight_advisor import relight
from ui import keys

FIX = Path("tests/fixtures/ps")

# --- Simple-image mode harness (no normal_field) ---
HARNESS_PHOTO = """
import streamlit as st
import numpy as np
from mini_highlight_advisor.region_state import new_book
from ui import results, keys

# Minimal shading stub
class _Shading:
    mask = np.ones((8, 8), dtype=bool)
    light = np.full((8, 8), 0.5, dtype=np.float32)

rgb   = np.zeros((8, 8, 3), dtype=np.uint8)
alpha = np.full((8, 8), 255, dtype=np.uint8)
book  = new_book(3)

st.session_state.setdefault(keys.BOOK, book)
results.render(rgb, alpha, book, book.palette_at(0), [], [], _Shading())
"""

# --- PS mode harness (normal_field seeded) ---
HARNESS_PS = """
import streamlit as st
import numpy as np
from pathlib import Path
from PIL import Image
from mini_highlight_advisor import relight
from mini_highlight_advisor.region_state import new_book
from ui import results, keys

FIX = Path("tests/fixtures/ps")
book = new_book(3)

if keys.NORMALS not in st.session_state:
    normals = relight.load_normals(str(FIX / "synth_normal.png"))
    mask    = np.asarray(Image.open(FIX / "synth_mask.png").convert("L")) > 127
    st.session_state[keys.NORMALS] = normals
    st.session_state[keys.PS_MASK] = mask
    st.session_state[keys.PS_ALBEDO] = None

class _Shading:
    mask = np.ones((8, 8), dtype=bool)
    light = np.full((8, 8), 0.5, dtype=np.float32)

rgb   = np.zeros((8, 8, 3), dtype=np.uint8)
alpha = np.full((8, 8), 255, dtype=np.uint8)
normals = st.session_state[keys.NORMALS]

results.render(rgb, alpha, book, book.palette_at(0), [], [], _Shading(),
               normal_field=normals)
"""


def test_technique_picker_renders_in_photo_mode():
    at = AppTest.from_string(HARNESS_PHOTO)
    at.run()
    assert not at.exception


def test_technique_picker_renders_in_ps_mode():
    at = AppTest.from_string(HARNESS_PS)
    at.run()
    assert not at.exception


def test_matte_normalises_to_smooth_in_picker():
    # A book with "matte" material must not raise a ValueError in the picker.
    at = AppTest.from_string(HARNESS_PHOTO)
    at.run()
    assert not at.exception


def test_set_drybrush_via_picker_updates_book():
    """Selecting Drybrush in photo mode writes 'drybrush' to the book."""
    at = AppTest.from_string(HARNESS_PHOTO)
    at.run()
    assert not at.exception
    # Select Drybrush option
    sel = at.selectbox[0]   # first (and only) technique selectbox
    sel.select("Drybrush")
    at.run()
    assert not at.exception
    # After applying, the book material must be "drybrush"
    book = at.session_state[keys.BOOK]
    assert book.material_at(0) == "drybrush"
```

- [ ] **Step 2: Run tests to confirm they fail**

```
.venv/Scripts/python -m pytest tests/test_ui_technique_picker.py -v
```
Expected: FAIL — various errors as the picker doesn't exist yet.

- [ ] **Step 3: Replace the PS-only material selector with the always-visible technique picker**

In `ui/results.py`, find and replace the entire PS-only material block:

```python
    nmm_horizon = 0.5
    if normal_field is not None:
        sel = book.selected
        cur = book.material_at(sel)
        choice = st.selectbox(
            f"Material — {book.names()[sel]}", ["Matte", "NMM"],
            index=0 if cur == "matte" else 1, key=keys.material(sel),
            help="NMM re-bands this region as non-metallic metal: it reads the "
                 "reflection of a virtual sky/ground off the surface normals. "
                 "PS mode only.")
        book.set_material_at(sel, "nmm" if choice == "NMM" else "matte")
        nmm_horizon = st.slider(
            "Horizon height", 0.0, 1.0, 0.5, 0.05, key=keys.NMM_HORIZON,
            help="Slide the virtual NMM horizon up (darker, more reflected ground) "
                 "or down (brighter, more sky). Affects NMM regions only.")
```

Replace with:

```python
    nmm_horizon = 0.5
    sel = book.selected
    cur_material = book.material_at(sel)
    # Normalise "matte" (legacy) to "smooth" for the picker index lookup.
    cur_key = "smooth" if cur_material == "matte" else cur_material

    technique_labels = ["Smooth layering", "Drybrush"]
    technique_keys   = ["smooth",          "drybrush"]
    if normal_field is not None:
        technique_labels.append("NMM")
        technique_keys.append("nmm")

    cur_idx = technique_keys.index(cur_key) if cur_key in technique_keys else 0
    choice_label = st.selectbox(
        f"Technique — {book.names()[sel]}",
        technique_labels,
        index=cur_idx,
        key=keys.material(sel),
        help=(
            "How paint is applied in this region.\n"
            "Smooth layering: thin glazes, dark to light.\n"
            "Drybrush: drag a nearly-dry brush across raised surfaces "
            "(fur, chainmail, cloth, textured bases).\n"
            "NMM (PS mode only): non-metallic metal — re-bands from the "
            "reflection of a virtual sky/ground off the surface normals."
        ),
    )
    chosen_key = technique_keys[technique_labels.index(choice_label)]
    book.set_material_at(sel, chosen_key)

    if normal_field is not None and chosen_key == "nmm":
        nmm_horizon = st.slider(
            "Horizon height", 0.0, 1.0, 0.5, 0.05, key=keys.NMM_HORIZON,
            help="Slide the virtual NMM horizon up (darker, more reflected ground) "
                 "or down (brighter, more sky). Affects NMM regions only.")
```

- [ ] **Step 4: Run the new tests**

```
.venv/Scripts/python -m pytest tests/test_ui_technique_picker.py -v
```
Expected: all 4 tests PASS.

- [ ] **Step 5: Run the full suite**

```
.venv/Scripts/python -m pytest
```
Expected: all pass (pre-existing failures only).

- [ ] **Step 6: Manual browser smoke**

Run: `.venv/Scripts/streamlit run app.py`

Check:
1. Upload any photo — the **Technique** selectbox appears (not hidden behind PS mode).
2. Select **Drybrush** — step headers read "Base coat", "First drybrush", "Second drybrush", etc. instead of "Shadow", "Base", "Midtone".
3. Step captions read "Drybrush across raised areas (~N%)" and "Peak colour — this zone only (~N%)".
4. Switch back to **Smooth layering** — step headers revert to "Shadow / Base / Midtone / Highlight / Bright Highlight"; captions revert to "Apply across — whole area" and "Stays this colour — final".
5. In PS mode (import a PS bundle): all three options appear — Smooth, Drybrush, NMM. NMM horizon slider only shows when NMM is selected.
6. Save a project with Drybrush selected; reload — the technique is preserved.

- [ ] **Step 7: Commit**

```
git add ui/results.py tests/test_ui_technique_picker.py
git commit -m "feat(ui): always-visible technique picker — Smooth/Drybrush in all modes, NMM PS-only"
```

---

## Self-Review

**Spec coverage:**
- `TechniqueSpec` + `TECHNIQUES` registry → Task 1 ✓
- `role_names(n)` + `coverage_note(role)` on TechniqueSpec → Task 1 ✓
- `"matte"` alias for back-compat → Task 1 `TECHNIQUES["matte"] = _SMOOTH` ✓
- `RegionPlan.technique` → Task 2 ✓
- `plan_region(technique=)` uses spec role names → Task 2 ✓
- Path L byte-identical (drybrush bands = smooth bands) → Task 2 regression assertion ✓
- `analyze_regions` passes technique through → Task 2 ✓
- `render_legend(coverage_notes=)` → Task 3 ✓
- `render_region_steps(technique=)` adjusts captions → Task 4 ✓
- `results.py` caller passes `plan.technique` → Task 4 ✓
- Technique picker always visible, NMM guarded → Task 5 ✓
- "matte" in picker normalised to "smooth" without ValueError → Task 5 ✓

**Placeholder scan:** No TBD or TODO. All code blocks contain complete implementations. All test assertions contain concrete expected values.

**Type consistency:**
- `get_technique(name: str) -> TechniqueSpec` — defined Task 1, consumed Task 2, 4, 5 ✓
- `TechniqueSpec.role_names(n: int) -> list[str]` — defined Task 1, called in Task 2 ✓
- `TechniqueSpec.captions.across` / `.stays` — format strings with `{pct:.0f}` — defined Task 1, formatted Task 4 ✓
- `RegionPlan.technique: str` — added Task 2, read in Task 4 caller (`plan.technique`) ✓
- `render_region_steps(steps, roles, names, coverage, technique="smooth")` — defined Task 4, caller Task 4 (results.py) ✓
- `render_legend(..., coverage_notes=None)` — defined Task 3; no caller passes it yet (extension point) ✓
