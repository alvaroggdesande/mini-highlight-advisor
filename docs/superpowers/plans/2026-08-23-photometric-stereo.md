# Photometric-Stereo Feature Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Turn a multi-shot phone capture of a dark/primed mini into a recovered normal map and a highlight plan driven by that relief, with a global virtual-light control that drives the actual plan.

**Architecture:** Two halves split by a *file boundary*. An external, torch-owning `tools/ps_tool.py` turns capture frames into a validated `normal.png` + `mask.png` bundle. The lean, torch-free app gains a third input mode that imports that bundle, relights the normals under a user-chosen global light (`src/mini_highlight_advisor/relight.py`), and feeds the resulting light field into the existing engine via one new optional `analyze_regions(light_field=…)` parameter. Everything downstream — banding, overlay, regions, edges, palette/matching, paint-along steps — is reused unchanged.

**Tech Stack:** Python 3.11, numpy, opencv, pillow, streamlit (app env `.venv`). `ps_tool` runs in its **own** env: torch-CPU, opencv, einops, imageio + a vendored copy of SDM-UniPS inference.

**Spec:** `docs/superpowers/specs/2026-08-23-photometric-stereo-feature-design.md`

## Global Constraints

- **App stays torch-free.** No task under `src/` or `ui/` may import torch, transformers, or anything from `tools/ps_tool` / SDM-UniPS. PS compute lives entirely in `tools/`, off the app's import surface.
- **Pinned normal convention (load-bearing):** `n = rgb/255*2 − 1`; **R = x-right, G = y-up, B = z-toward-viewer**; vectors renormalized to unit length on decode. `ps_tool` normalizes to this convention **once** so `relight.py` needs **no per-import flip toggle**.
- **Dtypes at the seams:** a *light field* is `float32` in `[0,1]`, shape `(H,W)`, off-mask = `0` (matches `lighting.luminance_light`). A *display rgb* is `uint8` in `[0,255]`, shape `(H,W,3)` (matches `masking.load_image` output that `overlay.paint_preview`/`paint_regions` consume via `.astype(float32)`).
- **v1 scope:** primed minis (dark-primer target); **session-only** (no persistence, no multi-angle integration); **diffuse-only** (`n·l`, no specular in the plan); **single global light** (no per-region light directions); global sliders/presets only (no true mouse-drag).
- **Process:** work on the existing `feat/photometric-stereo` branch; never build on `main`; feature branch + PR/merge (CLAUDE.md). No git worktrees. Tests run with `.venv/Scripts/python -m pytest`.
- **The app never sees a bad map.** `ps_tool` either emits a validated bundle or fails loud with a reason. The app additionally validates dimensions + plausible unit normals on import as its only defense against a hand-crafted bundle.

---

## File Structure

**New files**

- `src/mini_highlight_advisor/relight.py` — pure, torch-free normal-map math: decode, light direction, relight, plausibility check. The spike's shading math promoted to real code.
- `ui/relight_panel.py` — the global virtual-light control (azimuth + elevation sliders + presets).
- `ui/editor.py` — the shared region→results editor body, extracted from `app.py` so photo mode and PS mode reuse it verbatim (this is the spec's "reused unchanged").
- `ui/ps_mode.py` — the PS input branch: two uploaders, import validation, relight, and the one engine call, wiring the shared editor with a `light_field`.
- `tools/ps_tool.py` — standalone capture → align → mask → SDM-UniPS → bundle script, run in its own torch env; never imported by the app.
- `tools/ps_stages.py` — the torch-free pure stages of `ps_tool` (registration, gates, consensus, convention encode) so they are unit-testable without torch.
- `tools/requirements-ps.txt`, `tools/README-ps.md`, vendored `tools/vendor/sdm_unips/…` — env + vendored inference (Task 7).
- `docs/ps-capture-guide.md` — productized capture recipe.
- `tests/fixtures/ps/synth_normal.png`, `tests/fixtures/ps/synth_mask.png` — committed synthetic fixture (tiny dome + ridges) making the whole app side testable offline.
- `tests/fixtures/ps/generate_synth.py` — deterministic one-off generator for the two fixtures above (committed for reproducibility).
- Tests: `tests/test_relight.py`, `tests/test_pipeline_light_field.py`, `tests/test_ui_relight_panel.py`, `tests/test_ui_results_ps.py`, `tests/test_ui_ps_mode.py`, `tests/test_ps_stages.py`.

**Modified files**

- `src/mini_highlight_advisor/pipeline.py` — `analyze_regions(...)` gains an optional `light_field=` parameter (one touch).
- `ui/keys.py` — add `NORMALS`, `PS_MASK`, `LIGHT_AZ`, `LIGHT_EL` (+ preset key).
- `ui/results.py` — `render(...)` gains `light_field=None`; suppresses luminance/coloured/photo-quality UI in PS mode; passes `light_field` to `analyze_regions`.
- `app.py` — editor body extracted into `ui/editor.py`; a top-of-tab input-mode selector routes to photo mode (unchanged behavior) or `ps_mode.render()`.
- `.gitignore` — ignore the 445 MB checkpoint + `ps_tool` env artifacts (Task 7).

---

### Task 1: `relight.py` + synthetic fixture (pure, TDD)

Smallest unit; unblocks the whole app side. Pure numpy, no streamlit, no torch.

**Files:**
- Create: `src/mini_highlight_advisor/relight.py`
- Create: `tests/fixtures/ps/generate_synth.py`
- Create (generated, committed): `tests/fixtures/ps/synth_normal.png`, `tests/fixtures/ps/synth_mask.png`
- Test: `tests/test_relight.py`

**Interfaces:**
- Consumes: nothing (leaf module).
- Produces:
  - `load_normals(path: str) -> np.ndarray` — `(H,W,3)` `float32` unit vectors, pinned convention.
  - `light_dir(az_deg: float, el_deg: float) -> np.ndarray` — `(3,)` `float32` unit vector `[cos el cos az, cos el sin az, sin el]`.
  - `relight(normals: np.ndarray, mask: np.ndarray, light: np.ndarray) -> tuple[np.ndarray, np.ndarray]` — returns `(light_field, relit_grey)` where `light_field` is `(H,W)` `float32` in `[0,1]` (off-mask 0) and `relit_grey` is `(H,W,3)` `uint8` (off-mask 0).
  - `plausible_unit_normals(rgb01: np.ndarray, mask: np.ndarray) -> bool` — True if the raw decoded field looks like a real normal map over the foreground.
  - Module constants `ALBEDO = 0.6`, `AMBIENT = 0.15` (values validated in the spike).

- [ ] **Step 1: Write the fixture generator**

`tests/fixtures/ps/generate_synth.py` — deterministic; run once, output committed. A 128×128 hemispherical dome (radius 50, centered) plus two raised ridges, encoded to the pinned convention, with a circular mask.

```python
"""Deterministic generator for the PS synthetic fixture (dome + 2 ridges).
Run once; the two PNGs it writes are committed. No randomness, no torch.
Run: .venv/Scripts/python tests/fixtures/ps/generate_synth.py
"""
from pathlib import Path
import numpy as np
from PIL import Image

H = W = 128
cy = cx = 63.5
R = 50.0
here = Path(__file__).parent

yy, xx = np.mgrid[0:H, 0:W].astype(np.float32)
dx = (xx - cx) / R
dy = (yy - cy) / R
r2 = dx * dx + dy * dy
mask = r2 <= 1.0

# Dome normals: x-right, y-UP (image row grows downward, so up = -dy), z-toward-viewer.
nx = dx
ny = -dy
nz = np.sqrt(np.clip(1.0 - r2, 0.0, 1.0))

# Two ridges: tilt the surface locally so banding has crisp travel to lock onto.
ridge = ((np.abs(xx - 40) < 3) | (np.abs(xx - 88) < 3)) & mask
nx = np.where(ridge, 0.6, nx)
nz = np.where(ridge, np.sqrt(np.clip(1.0 - nx**2 - ny**2, 0.0, 1.0)), nz)

n = np.stack([nx, ny, nz], axis=-1).astype(np.float32)
n[~mask] = np.array([0.0, 0.0, 1.0], np.float32)      # background = flat facing viewer
norm = np.linalg.norm(n, axis=-1, keepdims=True)
n = n / np.clip(norm, 1e-6, None)

rgb = np.clip((n + 1.0) * 0.5 * 255.0, 0, 255).astype(np.uint8)
Image.fromarray(rgb).save(here / "synth_normal.png")
Image.fromarray((mask * 255).astype(np.uint8)).save(here / "synth_mask.png")
print("wrote synth_normal.png + synth_mask.png")
```

- [ ] **Step 2: Generate and commit the fixtures**

Run: `.venv/Scripts/python tests/fixtures/ps/generate_synth.py`
Expected: writes `synth_normal.png` + `synth_mask.png` under `tests/fixtures/ps/`.

- [ ] **Step 3: Write the failing tests**

`tests/test_relight.py`:

```python
from pathlib import Path
import numpy as np
from PIL import Image

from mini_highlight_advisor import relight

FIX = Path(__file__).parent / "fixtures" / "ps"


def _mask():
    return np.asarray(Image.open(FIX / "synth_mask.png").convert("L")) > 127


def test_load_normals_pins_z_toward_viewer():
    # rgb (128,128,255) decodes ~[0,0,1] under the pinned convention.
    n = relight.load_normals(str(FIX / "synth_normal.png"))
    assert n.shape[2] == 3
    # a background pixel was encoded flat-facing-viewer
    assert np.allclose(n[0, 0], [0, 0, 1], atol=0.02)


def test_load_normals_renormalizes_to_unit():
    n = relight.load_normals(str(FIX / "synth_normal.png"))
    norms = np.linalg.norm(n, axis=-1)
    assert np.allclose(norms, 1.0, atol=1e-3)


def test_light_dir_zenith_and_horizon():
    assert np.allclose(relight.light_dir(0, 90), [0, 0, 1], atol=1e-6)
    assert np.allclose(relight.light_dir(0, 0), [1, 0, 0], atol=1e-6)


def test_relight_flat_surface_from_zenith_is_uniform():
    m = np.ones((8, 8), bool)
    normals = np.zeros((8, 8, 3), np.float32)
    normals[..., 2] = 1.0                      # all facing viewer
    lf, grey = relight.relight(normals, m, relight.light_dir(0, 90))
    assert np.allclose(lf[m], 1.0, atol=1e-5)
    assert lf.dtype == np.float32
    assert grey.dtype == np.uint8 and grey.shape == (8, 8, 3)


def test_relight_excludes_off_mask():
    m = np.zeros((8, 8), bool); m[2:6, 2:6] = True
    normals = np.zeros((8, 8, 3), np.float32); normals[..., 2] = 1.0
    lf, grey = relight.relight(normals, m, relight.light_dir(0, 90))
    assert np.all(lf[~m] == 0)
    assert np.all(grey[~m] == 0)


def test_highlight_travels_with_light():
    # THE validated behavior: two light dirs put the brightest pixel in
    # different places on the dome.
    n = relight.load_normals(str(FIX / "synth_normal.png"))
    m = _mask()
    lf_l, _ = relight.relight(n, m, relight.light_dir(200, 30))   # from the left
    lf_r, _ = relight.relight(n, m, relight.light_dir(340, 30))   # from the right
    argmax_l = np.unravel_index(np.argmax(np.where(m, lf_l, -1)), lf_l.shape)
    argmax_r = np.unravel_index(np.argmax(np.where(m, lf_r, -1)), lf_r.shape)
    assert argmax_l[1] != argmax_r[1]            # brightest column moves


def test_plausible_unit_normals_accepts_fixture_rejects_blank():
    m = _mask()
    good = np.asarray(Image.open(FIX / "synth_normal.png").convert("RGB"), np.float32) / 255.0
    blank = np.zeros_like(good)                   # decodes to all [-1,-1,-1], degenerate
    assert relight.plausible_unit_normals(good, m) is True
    assert relight.plausible_unit_normals(blank, m) is False
```

- [ ] **Step 4: Run tests to verify they fail**

Run: `.venv/Scripts/python -m pytest tests/test_relight.py -v`
Expected: FAIL — `ModuleNotFoundError: mini_highlight_advisor.relight`.

- [ ] **Step 5: Write the implementation**

`src/mini_highlight_advisor/relight.py`:

```python
"""Pure, torch-free relighting of a recovered normal map.

Pinned convention (load-bearing): n = rgb/255*2-1, R=x-right, G=y-up,
B=z-toward-viewer. ps_tool normalizes to this once, so there is NO per-import
flip toggle here. Diffuse-only for v1.
"""
from __future__ import annotations

import numpy as np
from PIL import Image

ALBEDO = 0.6      # flat display albedo (validated spike value)
AMBIENT = 0.15    # ambient fill (validated spike value)


def load_normals(path: str) -> np.ndarray:
    """PNG-encoded normals -> (H,W,3) float32 unit vectors, pinned convention."""
    rgb = np.asarray(Image.open(path).convert("RGB"), dtype=np.float32) / 255.0
    return _decode(rgb)


def _decode(rgb01: np.ndarray) -> np.ndarray:
    n = rgb01 * 2.0 - 1.0
    norm = np.linalg.norm(n, axis=-1, keepdims=True)
    norm[norm == 0] = 1.0
    return (n / norm).astype(np.float32)


def light_dir(az_deg: float, el_deg: float) -> np.ndarray:
    az, el = np.radians(az_deg), np.radians(el_deg)
    return np.array(
        [np.cos(el) * np.cos(az), np.cos(el) * np.sin(az), np.sin(el)],
        dtype=np.float32,
    )


def relight(normals: np.ndarray, mask: np.ndarray, light: np.ndarray):
    """Diffuse relight. Returns (light_field, relit_grey).

    light_field: (H,W) float32 in [0,1], off-mask 0 — the banding light source.
    relit_grey:  (H,W,3) uint8, off-mask 0 — the display base overlays draw on.
    Both derive from the SAME n.l so bands and their background align.
    """
    light_field = np.clip(normals @ light, 0.0, 1.0).astype(np.float32)
    light_field[~mask] = 0.0
    grey = ALBEDO * (AMBIENT + (1.0 - AMBIENT) * light_field)
    grey8 = np.clip(grey * 255.0, 0, 255).astype(np.uint8)
    relit_grey = np.stack([grey8, grey8, grey8], axis=-1)
    relit_grey[~mask] = 0
    return light_field, relit_grey


def plausible_unit_normals(rgb01: np.ndarray, mask: np.ndarray) -> bool:
    """App-side defense: does this decode like a real normal map over the mini?

    A blank/hand-crafted image decodes to degenerate raw vectors; a real map has
    most foreground pixels with a raw magnitude near 1 and z generally positive.
    """
    if not mask.any():
        return False
    raw = rgb01 * 2.0 - 1.0
    fg = raw[mask]
    mags = np.linalg.norm(fg, axis=-1)
    near_unit = np.mean((mags > 0.3) & (mags < 2.0))
    z_positive = np.mean(fg[:, 2] > 0.0)
    return bool(near_unit > 0.7 and z_positive > 0.6)
```

- [ ] **Step 6: Run tests to verify they pass**

Run: `.venv/Scripts/python -m pytest tests/test_relight.py -v`
Expected: PASS (all tests).

- [ ] **Step 7: Commit**

```bash
git add src/mini_highlight_advisor/relight.py tests/test_relight.py tests/fixtures/ps/
git commit -m "feat(relight): pure normal-map relight + synthetic fixture"
```

---

### Task 2: `analyze_regions(light_field=…)` injection + regression lock

One touch to the engine. Absent → today's luminance path byte-identical; present → bypass `luminance_light`, feed the injected field into rank banding.

**Files:**
- Modify: `src/mini_highlight_advisor/pipeline.py:157-193` (`analyze_regions`)
- Test: `tests/test_pipeline_light_field.py`

**Interfaces:**
- Consumes: `relight.relight`'s `light_field` contract (`(H,W)` float32 `[0,1]`, off-mask 0) — for the bypass-proof test.
- Produces: `analyze_regions(rgb, alpha, default_palette, coverage=None, regions=None, edges=True, extreme_edge=False, edge_sensitivity=0.5, relief_cap=False, per_region_norm=False, light_field=None) -> MultiRegionResult`. When `light_field` is not None: `mask = compute_mask(rgb, alpha)`, `light = light_field`, and `per_region_norm` is forced off.

- [ ] **Step 1: Write the failing tests**

`tests/test_pipeline_light_field.py`:

```python
import numpy as np

from mini_highlight_advisor.pipeline import analyze_regions, prepare_shading, WHOLE_MINI
from mini_highlight_advisor.banding import band_light
from mini_highlight_advisor.palette import DEFAULT_PALETTE, default_coverage

PAL = DEFAULT_PALETTE[:5]
COV = default_coverage(5)


def _whole(res):
    return next(p for p in res.plans if p.name == WHOLE_MINI)


def test_light_field_absent_matches_luminance_path():
    # Regression lock: omitting light_field == today's luminance banding.
    rgb = (np.random.default_rng(0).integers(0, 255, (48, 48, 3))).astype(np.uint8)
    alpha = np.full((48, 48), 255, np.uint8)
    res = analyze_regions(rgb, alpha, PAL, COV, [], edges=False, relief_cap=False)
    sh = prepare_shading(rgb, alpha)
    expected = band_light(sh.light, sh.mask, COV)
    np.testing.assert_array_equal(_whole(res).bands, expected)


def test_light_field_present_bypasses_luminance():
    # Uniform-grey rgb (flat luminance) vs a gradient light_field that DISAGREES.
    # Bands must track the light_field, proving the bypass.
    rgb = np.full((40, 40, 3), 100, np.uint8)          # flat -> luminance carries no relief
    alpha = np.full((40, 40), 255, np.uint8)
    grad = np.tile(np.linspace(0, 1, 40, dtype=np.float32), (40, 1))  # left->right ramp
    res = analyze_regions(rgb, alpha, PAL, COV, [], edges=False,
                          relief_cap=False, light_field=grad)
    bands = _whole(res).bands
    mask = bands >= 0
    # darkest band on the left, brightest on the right => mean column index rises with band
    cols = np.array([bands[mask & (bands == k)].size and
                     np.mean(np.argwhere(bands == k)[:, 1]) for k in range(5)])
    assert np.all(np.diff(cols) > 0)


def test_light_field_uses_provided_mask_shape():
    rgb = np.full((24, 24, 3), 100, np.uint8)
    alpha = np.full((24, 24), 255, np.uint8)
    lf = np.tile(np.linspace(0, 1, 24, dtype=np.float32), (24, 1))
    res = analyze_regions(rgb, alpha, PAL, COV, [], edges=False, light_field=lf)
    assert res.mask.shape == (24, 24)
    assert (res.plans[0].bands >= 0).any()
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `.venv/Scripts/python -m pytest tests/test_pipeline_light_field.py -v`
Expected: FAIL — `analyze_regions() got an unexpected keyword argument 'light_field'`.

- [ ] **Step 3: Modify `analyze_regions`**

In `src/mini_highlight_advisor/pipeline.py`, change the signature and the shading setup. Replace the current head of `analyze_regions` (the `def` line through `gray = _clahe_gray(rgb) if per_region_norm else None`) with:

```python
def analyze_regions(rgb, alpha, default_palette, coverage=None, regions=None,
                    edges: bool = True, extreme_edge: bool = False,
                    edge_sensitivity: float = 0.5,
                    relief_cap: bool = False,
                    per_region_norm: bool = False,
                    light_field: np.ndarray | None = None) -> MultiRegionResult:
    regions = regions or []
    if coverage is None:
        coverage = default_coverage(len(default_palette))
    if light_field is not None:
        # PS mode: mask from the provided (authoritative) alpha; light = injected
        # field. The field is global, so per-region luminance norm is bypassed.
        mask = compute_mask(rgb, alpha)
        light = light_field
        per_region_norm = False
    else:
        shading = prepare_shading(rgb, alpha)
        mask, light = shading.mask, shading.light
    owner = assign_owners(mask, [r.mask for r in regions])
    plans: list[RegionPlan] = []
    default_sub = owner == -1
    ekw = dict(edges=edges, extreme_edge=extreme_edge, edge_sensitivity=edge_sensitivity,
               relief_cap=relief_cap)

    gray = _clahe_gray(rgb) if per_region_norm else None
```

Add the import at the top of the file (it is not yet imported here):

```python
from .masking import compute_mask
```

The rest of `analyze_regions` (the `_region_light` closure, the region loop, `paint_regions`, and the `return MultiRegionResult(mask, light, plans, combined)`) is unchanged.

- [ ] **Step 4: Run tests to verify they pass**

Run: `.venv/Scripts/python -m pytest tests/test_pipeline_light_field.py tests/test_pipeline.py -v`
Expected: PASS (new tests pass; existing pipeline tests still green = regression lock holds).

- [ ] **Step 5: Commit**

```bash
git add src/mini_highlight_advisor/pipeline.py tests/test_pipeline_light_field.py
git commit -m "feat(pipeline): optional light_field bypass in analyze_regions"
```

---

### Task 3: `ui/relight_panel.py` + light keys

The global virtual-light control. Azimuth + elevation sliders + preset buttons, writing `keys.LIGHT_AZ` / `keys.LIGHT_EL`.

**Files:**
- Modify: `ui/keys.py` (add `NORMALS`, `PS_MASK`, `LIGHT_AZ`, `LIGHT_EL`, `LIGHT_PRESET`)
- Create: `ui/relight_panel.py`
- Test: `tests/test_ui_keys.py` (extend), `tests/test_ui_relight_panel.py`

**Interfaces:**
- Consumes: nothing (streamlit-only).
- Produces: `relight_panel.render() -> tuple[float, float]` returning `(az_deg, el_deg)`; reads/writes `st.session_state[keys.LIGHT_AZ]` and `[keys.LIGHT_EL]`. `PRESETS: dict[str, tuple[float, float]]` = `{"Upper-left": (225,45), "Top": (90,80), "Raking-L": (200,20), "Raking-R": (340,20)}`.

- [ ] **Step 1: Add the keys**

In `ui/keys.py`, after the `EDGE_*` / `PER_REGION_NORM` block (near line 21), add:

```python
# --- photometric-stereo (PS) mode ---
NORMALS = "ps_normals"           # decoded (H,W,3) unit normals in session
PS_MASK = "ps_mask"              # (H,W) bool foreground mask from the imported bundle
LIGHT_AZ = "light_az"            # virtual-light azimuth slider (deg)
LIGHT_EL = "light_el"            # virtual-light elevation slider (deg)
LIGHT_PRESET = "light_preset"    # nonce to force slider re-seed after a preset click
```

- [ ] **Step 2: Write the failing tests**

Extend `tests/test_ui_keys.py` with:

```python
def test_ps_keys_present_and_frozen():
    from ui import keys
    assert keys.LIGHT_AZ == "light_az"
    assert keys.LIGHT_EL == "light_el"
    assert keys.NORMALS == "ps_normals"
    assert keys.PS_MASK == "ps_mask"
```

`tests/test_ui_relight_panel.py`:

```python
from streamlit.testing.v1 import AppTest

HARNESS = """
import streamlit as st
from ui import relight_panel
az, el = relight_panel.render()
st.write("az", az)
st.write("el", el)
"""


def _run():
    at = AppTest.from_string(HARNESS)
    at.run()
    return at


def test_renders_two_sliders_with_defaults():
    at = _run()
    assert len(at.slider) == 2
    az = next(v.value for v in at.markdown if False)  # placeholder; use write below
    assert at.session_state["light_az"] is not None
    assert at.session_state["light_el"] is not None


def test_preset_button_sets_light():
    at = _run()
    # click the "Raking-L" preset; azimuth/elevation should jump to its values
    at.button(key="preset_Raking-L").click()
    at.run()
    assert at.session_state["light_az"] == 200
    assert at.session_state["light_el"] == 20
```

- [ ] **Step 3: Run tests to verify they fail**

Run: `.venv/Scripts/python -m pytest tests/test_ui_relight_panel.py tests/test_ui_keys.py -v`
Expected: FAIL — `ModuleNotFoundError: ui.relight_panel`.

- [ ] **Step 4: Write the implementation**

`ui/relight_panel.py`:

```python
"""Global virtual-light control for PS mode: az/el sliders + presets.

Any change re-runs Streamlit; the caller re-derives the plan from (az, el).
"""
import streamlit as st

from ui import keys

PRESETS = {
    "Upper-left": (225, 45),
    "Top": (90, 80),
    "Raking-L": (200, 20),
    "Raking-R": (340, 20),
}


def render() -> tuple[float, float]:
    st.markdown("**Virtual light** — drag to move where the highlights fall.")
    cols = st.columns(len(PRESETS))
    for col, (name, (az, el)) in zip(cols, PRESETS.items()):
        if col.button(name, key=f"preset_{name}"):
            st.session_state[keys.LIGHT_AZ] = az
            st.session_state[keys.LIGHT_EL] = el
            st.rerun()
    az = st.slider("Azimuth °", 0, 360, st.session_state.get(keys.LIGHT_AZ, 225),
                   key=keys.LIGHT_AZ)
    el = st.slider("Elevation °", 0, 90, st.session_state.get(keys.LIGHT_EL, 45),
                   key=keys.LIGHT_EL)
    return float(az), float(el)
```

Note: `st.slider(..., value=..., key=k)` — when `key` already exists in session state, Streamlit uses the stored value and ignores `value`; the preset write above therefore takes effect on the next run. Remove the placeholder line in the first test (`az = next(...)`) — the assertion on session_state is the real check; keep only the session_state assertions.

- [ ] **Step 5: Run tests to verify they pass**

Run: `.venv/Scripts/python -m pytest tests/test_ui_relight_panel.py tests/test_ui_keys.py -v`
Expected: PASS.

- [ ] **Step 6: Commit**

```bash
git add ui/keys.py ui/relight_panel.py tests/test_ui_relight_panel.py tests/test_ui_keys.py
git commit -m "feat(ui): relight panel (az/el sliders + presets) + PS keys"
```

---

### Task 4: `results.render` light_field param + PS-mode UI suppression

Teach the results panel to run the PS path: accept `light_field`, hide the luminance-only controls (coloured/painted toggle + photo-quality panel), and pass the field into `analyze_regions`. Photo mode (`light_field=None`) stays byte-identical.

**Files:**
- Modify: `ui/results.py:13` (signature) and `ui/results.py:46-73` (suppress + pass-through)
- Test: `tests/test_ui_results_ps.py`

**Interfaces:**
- Consumes: `analyze_regions(..., light_field=…)` (Task 2); `keys.PER_REGION_NORM`, `keys.EDGE_*`, `keys.RELIEF_CAP`.
- Produces: `results.render(rgb, alpha, book, palette, picked, owned_paints, shading, light_field=None) -> None`. When `light_field is not None`: the "Colored / painted mini" checkbox and the "Photo quality" panel are **not rendered**; `per_region_norm` is treated as `False`; `analyze_regions` is called with `light_field=light_field`.

- [ ] **Step 1: Write the failing tests**

`tests/test_ui_results_ps.py`:

```python
from streamlit.testing.v1 import AppTest

# Mounts the real results.render() on the synthetic PS fixture, in PS mode.
HARNESS_PS = """
import numpy as np
from pathlib import Path
from PIL import Image
import streamlit as st
from mini_highlight_advisor import relight
from mini_highlight_advisor.pipeline import compute_mask if False else None
from mini_highlight_advisor.masking import compute_mask
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
palette = wp
results.render(relit, mask_u8, book, palette, picked, owned, None, light_field=lf)
st.write("ok")
"""

HARNESS_PHOTO = HARNESS_PS.replace(
    "results.render(relit, mask_u8, book, palette, picked, owned, None, light_field=lf)",
    "sh = type('S', (), {'mask': mask})()\n"
    "results.render(relit, mask_u8, book, palette, picked, owned, sh)",
)


def test_ps_mode_hides_coloured_toggle():
    at = AppTest.from_string(HARNESS_PS); at.run()
    assert not at.exception
    labels = [c.label for c in at.checkbox]
    assert not any("painted mini" in (l or "").lower() for l in labels)


def test_ps_mode_renders_plan_without_error():
    at = AppTest.from_string(HARNESS_PS); at.run()
    assert not at.exception
    assert any("ok" == (m.value if hasattr(m, "value") else "") for m in at.markdown) or True


def test_photo_mode_still_shows_coloured_toggle():
    at = AppTest.from_string(HARNESS_PHOTO); at.run()
    assert not at.exception
    labels = [c.label for c in at.checkbox]
    assert any("painted mini" in (l or "").lower() for l in labels)
```

(Clean the harness header — drop the `compute_mask if False else None` placeholder line; it is only there to show the real import is `from mini_highlight_advisor.masking import compute_mask`. Keep the single real import.)

- [ ] **Step 2: Run tests to verify they fail**

Run: `.venv/Scripts/python -m pytest tests/test_ui_results_ps.py -v`
Expected: FAIL — `render() got an unexpected keyword argument 'light_field'`.

- [ ] **Step 3: Modify `results.render`**

Change the signature (`ui/results.py:13`):

```python
def render(rgb, alpha, book, palette, picked, owned_paints, shading, light_field=None) -> None:
    ps_mode = light_field is not None
```

Wrap the coloured-mini checkbox (`ui/results.py:46-50`) so it is hidden in PS mode:

```python
    if ps_mode:
        per_region_norm = False
    else:
        per_region_norm = st.checkbox(
            "Colored / painted mini (experimental)", value=False, key=keys.PER_REGION_NORM,
            help="Normalize brightness per region so each painted colour reads its own "
                 "relief. Off = primed-mini mode (default). Needs one lassoed region per "
                 "material; very dark regions may be flagged as too low-contrast to read.")
```

Wrap the Photo-quality panel (`ui/results.py:52-65`, the whole `try:` block) so it is skipped in PS mode:

```python
    if not ps_mode:
        try:
            st.subheader("\U0001F4F7 Photo quality")
            for r in check_input(rgb, shading.mask):
                line = f"**{r.label}** — {r.detail}"
                (st.success if r.ok else st.warning)(line)
            st.caption(PAINTED_CAPTURE_NOTE)
            with st.expander("How to photograph your mini"):
                st.markdown(SHOOTING_GUIDE)
        except Exception:
            st.caption("Photo-quality check unavailable for this image.")
```

Pass the field into the engine call (`ui/results.py:69-73`):

```python
    multi = analyze_regions(rgb, alpha, wp, wcov, drawn,
                            edges=edges, extreme_edge=extreme_edge,
                            edge_sensitivity=edge_sensitivity,
                            relief_cap=relief_cap,
                            per_region_norm=per_region_norm,
                            light_field=light_field)
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `.venv/Scripts/python -m pytest tests/test_ui_results_ps.py -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add ui/results.py tests/test_ui_results_ps.py
git commit -m "feat(ui): results supports PS light_field + suppresses luminance UI"
```

---

### Task 5: Extract `ui/editor.py`, add `ui/ps_mode.py`, wire the app entry

Split the shared editor body out of `app.py` so photo mode and PS mode reuse it verbatim, then add the third input branch. Session-only: no persistence, no multi-angle for PS.

**Files:**
- Create: `ui/editor.py`
- Create: `ui/ps_mode.py`
- Modify: `app.py`
- Test: `tests/test_ui_ps_mode.py`

**Interfaces:**
- Consumes: `regions_panel.render`, `palette_editor.render`/`render_save_recipe`, `coverage_editor.render`, `results.render(..., light_field=)`, `state.rehydrate_editor_widgets`, `relight.load_normals`/`relight`/`light_dir`/`plausible_unit_normals`, `masking.compute_mask`, `pipeline.ShadingResult`, `relight_panel.render`, `region_state.new_book`.
- Produces:
  - `editor.render_editor(rgb, alpha, shading, book, picked, owned_paints, light_field=None) -> None` — the shared region→palette→coverage→results body.
  - `ps_mode.render(picked, owned_paints) -> None` — the full PS branch (uploaders → validate → relight → editor). Uses `keys.NORMALS`, `keys.PS_MASK`.

- [ ] **Step 1: Create `ui/editor.py` by extracting the shared body**

`ui/editor.py`:

```python
"""The shared region -> palette -> coverage -> results editor body.

Extracted verbatim from app.py so photo mode and PS mode drive the SAME editor.
`light_field` is None for photo mode (luminance path) and a (H,W) float32 field
for PS mode (relit path).
"""
import streamlit as st

from ui import coverage_editor, palette_editor, regions_panel, results, state


def render_editor(rgb, alpha, shading, book, picked, owned_paints, light_field=None) -> None:
    src_h, src_w = rgb.shape[:2]
    sel = regions_panel.render(book, rgb, shading, src_w, src_h)
    state.rehydrate_editor_widgets(book, sel)

    palette, n = palette_editor.render(book, sel, picked)
    coverage = coverage_editor.render(n)
    palette_editor.render_save_recipe(palette, n)

    book.set_palette_at(sel, palette)
    book.set_coverage_at(sel, coverage)

    results.render(rgb, alpha, book, palette, picked, owned_paints, shading,
                   light_field=light_field)
```

- [ ] **Step 2: Rewire photo mode in `app.py` to call `render_editor`**

In `app.py`, replace the body of the `try:` block (the lines from `src_h, src_w = rgb.shape[:2]` through `results.render(...)`, i.e. `app.py:60-77`) with a single call, keeping `helpers.shading(...)` above it and `projects_panel.render_save()` below it:

```python
        with st.spinner("Preparing shading (first run downloads the depth model if no alpha channel)..."):
            rgb, alpha, shading = helpers.shading(photo_bytes, photo_suffix)

        editor.render_editor(rgb, alpha, shading, book, picked, owned_paints)

        projects_panel.render_save()
```

Add `editor` to the `from ui import (...)` import list at the top of `app.py`.

- [ ] **Step 3: Run the full suite to confirm the extraction is behavior-preserving**

Run: `.venv/Scripts/python -m pytest -q`
Expected: PASS — existing UI/smoke tests (e.g. `test_smoke.py`, `test_ui_*`) still green; the extraction changed no behavior.

- [ ] **Step 4: Commit the refactor**

```bash
git add ui/editor.py app.py
git commit -m "refactor(ui): extract shared render_editor from app.py"
```

- [ ] **Step 5: Write the failing PS-mode test**

`tests/test_ui_ps_mode.py`:

```python
import io
import numpy as np
from pathlib import Path
from PIL import Image
from streamlit.testing.v1 import AppTest

FIX = Path("tests/fixtures/ps")

# Pre-seeds an imported bundle in session (skips the uploader interaction), then
# drives ps_mode.render() end to end on the synthetic fixture.
HARNESS = """
import numpy as np
from pathlib import Path
from PIL import Image
import streamlit as st
from mini_highlight_advisor import relight
from ui import ps_mode, keys

FIX = Path("tests/fixtures/ps")
if keys.NORMALS not in st.session_state:
    st.session_state[keys.NORMALS] = relight.load_normals(str(FIX / "synth_normal.png"))
    st.session_state[keys.PS_MASK] = (
        np.asarray(Image.open(FIX / "synth_mask.png").convert("L")) > 127)

ps_mode.render(picked=[], owned_paints=[])
st.write("done")
"""


def test_ps_mode_shows_relight_panel_and_runs():
    at = AppTest.from_string(HARNESS); at.run()
    assert not at.exception
    # relight panel contributed the az/el sliders
    assert at.session_state["light_az"] is not None
    assert at.session_state["light_el"] is not None
    assert len(at.slider) >= 2


def test_moving_the_light_reruns_without_error():
    at = AppTest.from_string(HARNESS); at.run()
    at.slider(key="light_az").set_value(90).run()
    assert not at.exception
    assert at.session_state["light_az"] == 90
```

- [ ] **Step 6: Run the test to verify it fails**

Run: `.venv/Scripts/python -m pytest tests/test_ui_ps_mode.py -v`
Expected: FAIL — `ModuleNotFoundError: ui.ps_mode`.

- [ ] **Step 7: Write `ui/ps_mode.py`**

```python
"""PS input branch: import a normal.png + mask.png bundle, relight under a global
virtual light, and drive the shared editor with the resulting light field.

Session-only (v1): no persistence, no multi-angle. Torch-free — ps_tool produced
the bundle out of process.
"""
import numpy as np
import streamlit as st
from PIL import Image

from mini_highlight_advisor import relight
from mini_highlight_advisor.masking import compute_mask
from mini_highlight_advisor.pipeline import ShadingResult
from mini_highlight_advisor.region_state import new_book
from ui import editor, keys, relight_panel


def _import_gate() -> bool:
    """Two uploaders + validation. Returns True once a valid bundle is in session."""
    if keys.NORMALS in st.session_state and keys.PS_MASK in st.session_state:
        return True
    st.info("Import a photometric-stereo bundle produced by `tools/ps_tool.py`: "
            "a normal map and its mask. See docs/ps-capture-guide.md.")
    c1, c2 = st.columns(2)
    nrm = c1.file_uploader("normal.png", type=["png"], key="ps_upload_normal")
    msk = c2.file_uploader("mask.png", type=["png"], key="ps_upload_mask")
    if nrm is None or msk is None:
        return False

    rgb01 = np.asarray(Image.open(nrm).convert("RGB"), np.float32) / 255.0
    mask = np.asarray(Image.open(msk).convert("L")) > 127
    if rgb01.shape[:2] != mask.shape:
        st.error(f"Dimension mismatch: normal {rgb01.shape[:2]} vs mask {mask.shape}. "
                 "The two files must be the same size.")
        return False
    if not relight.plausible_unit_normals(rgb01, mask):
        st.error("That doesn't look like a normal map (values don't decode to unit "
                 "normals over the mask). Re-export the bundle from ps_tool.")
        return False

    st.session_state[keys.NORMALS] = relight._decode(rgb01)
    st.session_state[keys.PS_MASK] = mask
    st.rerun()
    return True


def render(picked, owned_paints) -> None:
    if not _import_gate():
        st.stop()

    normals = st.session_state[keys.NORMALS]
    mask = st.session_state[keys.PS_MASK]

    az, el = relight_panel.render()
    light_field, relit_grey = relight.relight(normals, mask, relight.light_dir(az, el))
    mask_u8 = (mask * 255).astype(np.uint8)
    shading = ShadingResult(mask=compute_mask(relit_grey, mask_u8), light=light_field)

    st.session_state.setdefault(keys.BOOK, new_book(5))
    book = st.session_state[keys.BOOK]

    editor.render_editor(relit_grey, mask_u8, shading, book, picked, owned_paints,
                         light_field=light_field)
```

- [ ] **Step 8: Add the input-mode selector to `app.py`**

In `app.py`, inside `with tab_mini:` and before the angles gate (before `if not angles:`), add a mode selector; route to PS mode when chosen. Import `ps_mode` in the `from ui import (...)` list.

```python
    input_mode = st.radio(
        "Input", ["Photo", "Import normal map (photometric stereo)"],
        horizontal=True, key="input_mode",
        help="Photo = primed mini under a raking light (luminance). PS = import a "
             "recovered normal map for dark/primed minis; drag a virtual light.")
    if input_mode.startswith("Import"):
        ps_mode.render(picked, owned_paints)
        st.stop()
```

Place this after `projects_panel.render_library()` so the mini library still renders in photo mode; the `st.stop()` keeps PS mode from falling through into the angles/photo flow. The `tab_gallery` block reads `keys.ANGLES` (unset in PS mode) and safely renders empty.

- [ ] **Step 9: Run the PS-mode test + full suite**

Run: `.venv/Scripts/python -m pytest tests/test_ui_ps_mode.py -q && .venv/Scripts/python -m pytest -q`
Expected: PASS (PS-mode tests green; nothing else regressed).

- [ ] **Step 10: Commit**

```bash
git add ui/ps_mode.py app.py tests/test_ui_ps_mode.py
git commit -m "feat(ui): PS input mode — import bundle, relight, drive editor"
```

---

### Task 6: `tools/ps_stages.py` — pure capture stages (TDD, no torch)

Productize the by-hand staircase steps that don't need torch: masking-agnostic registration, quality gates, consensus mask, and the convention-pinned normal encoder. All unit-tested offline.

**Files:**
- Create: `tools/__init__.py` (empty, so tests can import `tools.ps_stages`)
- Create: `tools/ps_stages.py`
- Test: `tests/test_ps_stages.py`

**Interfaces:**
- Consumes: `relight.load_normals` (for the round-trip test); numpy, cv2.
- Produces:
  - `centroid(mask: np.ndarray) -> tuple[float,float]` — (row, col) center of mass.
  - `align_to_reference(frames: list[np.ndarray], masks: list[np.ndarray]) -> tuple[list[np.ndarray], list[np.ndarray], list[tuple[int,int]]]` — integer-shift each frame+mask so its centroid matches frame 0; returns shifted frames, shifted masks, and the (dr,dc) offsets.
  - `iou(a: np.ndarray, b: np.ndarray) -> float`.
  - `consensus_mask(masks: list[np.ndarray]) -> np.ndarray` — majority vote.
  - `select_frames(frames, masks, *, iou_min=0.9, min_frames=4, std_min=8.0) -> tuple[list[int], dict]` — returns kept indices + a report dict `{"dropped": [...], "ious": [...], "lighting_std": float}`; raises `CaptureError(reason)` on min-frames / lighting-variation aborts.
  - `encode_normals(normals: np.ndarray) -> np.ndarray` — `(H,W,3)` uint8, inverse of `relight.load_normals` (pinned convention).
  - `class CaptureError(Exception)`.
  - Module constants `IOU_MIN=0.9`, `MIN_FRAMES=4`, `STD_MIN=8.0`.

- [ ] **Step 1: Write the failing tests**

`tests/test_ps_stages.py`:

```python
import numpy as np
import pytest

from tools import ps_stages as ps
from mini_highlight_advisor import relight


def _disc(h, w, cr, cc, r):
    yy, xx = np.mgrid[0:h, 0:w]
    return ((yy - cr) ** 2 + (xx - cc) ** 2) <= r * r


def test_align_recovers_known_translation():
    ref = _disc(64, 64, 32, 32, 12)
    shifted = _disc(64, 64, 32 + 5, 32 - 7, 12)     # +5 rows, -7 cols
    frames = [ref.astype(np.uint8) * 200, shifted.astype(np.uint8) * 200]
    _, _, offs = ps.align_to_reference(frames, [ref, shifted])
    assert abs(offs[1][0] - (-5)) <= 1        # brings it back up 5 rows
    assert abs(offs[1][1] - 7) <= 1           # and right 7 cols


def test_iou_gate_drops_cut_off_base_frame():
    good = _disc(64, 64, 32, 32, 14)
    cut = good.copy(); cut[46:, :] = False      # base sliced off -> low IoU
    frames = [good.astype(np.uint8) * 200] * 3 + [cut.astype(np.uint8) * 200]
    masks = [good, good, good, cut]
    # inject real lighting variation so only the IoU gate fires
    for i, f in enumerate(frames):
        frames[i] = (f.astype(np.float32) * (0.5 + 0.2 * i)).astype(np.uint8)
    kept, report = ps.select_frames(frames, masks)
    assert 3 not in kept
    assert 3 in report["dropped"]


def test_min_frames_abort():
    good = _disc(32, 32, 16, 16, 8)
    frames = [good.astype(np.uint8) * 200, good.astype(np.uint8) * 100]
    with pytest.raises(ps.CaptureError, match="too few|inconsistent"):
        ps.select_frames(frames, [good, good], min_frames=4)


def test_lighting_variation_abort_on_identical_frames():
    good = _disc(48, 48, 24, 24, 12)
    same = (good.astype(np.uint8) * 150)
    frames = [same.copy() for _ in range(5)]     # zero variation = turntable/no relight
    with pytest.raises(ps.CaptureError, match="lighting|variation"):
        ps.select_frames(frames, [good] * 5)


def test_consensus_is_majority_vote():
    a = _disc(32, 32, 16, 16, 10)
    b = _disc(32, 32, 16, 16, 10)
    c = _disc(32, 32, 16, 16, 4)                  # smaller
    out = ps.consensus_mask([a, b, c])
    assert out[16, 16]                            # center: all agree
    assert out[16, 24] == a[16, 24]              # majority (a,b) win the ring


def test_encode_decode_round_trip_pins_convention():
    rng = np.random.default_rng(0)
    n = rng.normal(size=(20, 20, 3)).astype(np.float32)
    n[..., 2] = np.abs(n[..., 2]) + 0.2          # z toward viewer
    n /= np.linalg.norm(n, axis=-1, keepdims=True)
    png8 = ps.encode_normals(n)
    assert png8.dtype == np.uint8 and png8.shape == (20, 20, 3)
    decoded = relight._decode(png8.astype(np.float32) / 255.0)
    assert np.allclose(decoded, n, atol=1.0 / 255 * 2 + 1e-3)
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `.venv/Scripts/python -m pytest tests/test_ps_stages.py -v`
Expected: FAIL — `ModuleNotFoundError: tools.ps_stages`.

- [ ] **Step 3: Write the implementation**

`tools/__init__.py`: empty file.

`tools/ps_stages.py`:

```python
"""Torch-free pure stages of ps_tool: registration, quality gates, consensus,
and the convention-pinned normal encoder. Unit-tested offline; the torch
inference orchestration lives in ps_tool.py and calls into these.
"""
from __future__ import annotations

import numpy as np

IOU_MIN = 0.9
MIN_FRAMES = 4
STD_MIN = 8.0


class CaptureError(Exception):
    """Raised on a fail-loud capture abort (too few frames / no lighting variation)."""


def centroid(mask: np.ndarray) -> tuple[float, float]:
    ys, xs = np.nonzero(mask)
    if ys.size == 0:
        return 0.0, 0.0
    return float(ys.mean()), float(xs.mean())


def _shift(arr: np.ndarray, dr: int, dc: int) -> np.ndarray:
    out = np.zeros_like(arr)
    h, w = arr.shape[:2]
    sr0, sr1 = max(0, dr), min(h, h + dr)
    sc0, sc1 = max(0, dc), min(w, w + dc)
    dr0, dr1 = max(0, -dr), min(h, h - dr)
    dc0, dc1 = max(0, -dc), min(w, w - dc)
    out[sr0:sr1, sc0:sc1] = arr[dr0:dr1, dc0:dc1]
    return out


def align_to_reference(frames, masks):
    r0, c0 = centroid(masks[0])
    a_frames, a_masks, offs = [], [], []
    for f, m in zip(frames, masks):
        r, c = centroid(m)
        dr, dc = int(round(r0 - r)), int(round(c0 - c))
        offs.append((dr, dc))
        a_frames.append(_shift(f, dr, dc))
        a_masks.append(_shift(m.astype(np.uint8), dr, dc) > 0)
    return a_frames, a_masks, offs


def iou(a: np.ndarray, b: np.ndarray) -> float:
    a, b = a.astype(bool), b.astype(bool)
    inter = np.logical_and(a, b).sum()
    union = np.logical_or(a, b).sum()
    return float(inter / union) if union else 0.0


def consensus_mask(masks) -> np.ndarray:
    stack = np.stack([m.astype(np.uint8) for m in masks], axis=0)
    return stack.sum(axis=0) > (len(masks) / 2.0)


def _gray(frame: np.ndarray) -> np.ndarray:
    if frame.ndim == 3:
        return frame.mean(axis=-1)
    return frame.astype(np.float32)


def select_frames(frames, masks, *, iou_min=IOU_MIN, min_frames=MIN_FRAMES,
                  std_min=STD_MIN):
    a_frames, a_masks, _ = align_to_reference(frames, masks)
    ref = a_masks[0]
    ious = [iou(ref, m) for m in a_masks]
    kept = [i for i, v in enumerate(ious) if v >= iou_min]
    dropped = [i for i in range(len(frames)) if i not in kept]
    if len(kept) < min_frames:
        raise CaptureError(
            f"capture too inconsistent: only {len(kept)} of {len(frames)} frames "
            f"survived the IoU gate (need {min_frames}).")
    fg = consensus_mask([a_masks[i] for i in kept])
    stack = np.stack([_gray(a_frames[i])[fg] for i in kept], axis=0)
    lighting_std = float(stack.std(axis=0).mean()) if fg.any() else 0.0
    if lighting_std < std_min:
        raise CaptureError(
            f"insufficient lighting variation (per-pixel std {lighting_std:.1f} < "
            f"{std_min}); move the light more between shots — a turntable won't work.")
    return kept, {"dropped": dropped, "ious": ious, "lighting_std": lighting_std}


def encode_normals(normals: np.ndarray) -> np.ndarray:
    """Inverse of relight.load_normals: unit normals -> uint8 PNG array, pinned."""
    n = normals / np.clip(np.linalg.norm(normals, axis=-1, keepdims=True), 1e-6, None)
    return np.clip((n + 1.0) * 0.5 * 255.0, 0, 255).astype(np.uint8)
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `.venv/Scripts/python -m pytest tests/test_ps_stages.py -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add tools/__init__.py tools/ps_stages.py tests/test_ps_stages.py
git commit -m "feat(ps_tool): torch-free capture stages (align, gates, consensus, encode)"
```

---

### Task 7: `tools/ps_tool.py` — vendored SDM-UniPS inference + orchestration (manual smoke)

Wire the pure stages into the full external pipeline, add the torch env and vendored inference, and emit the validated bundle. **Verification is a manual gate** (heavy/external; not self-run) per the spec — the torch inference itself is deliberately not unit-tested.

**Files:**
- Create: `tools/ps_tool.py`
- Create: `tools/requirements-ps.txt`
- Create: `tools/README-ps.md`
- Create: `tools/vendor/sdm_unips/…` (vendored, pinned inference with the `map_location='cpu'` patch committed in)
- Modify: `.gitignore`

**Interfaces:**
- Consumes: `tools.ps_stages` (all of Task 6); vendored `sdm_unips` inference.
- Produces: a CLI `python tools/ps_tool.py --frames DIR --checkpoint CKPT --out OUTDIR` that writes `normal.png`, `mask.png`, `report.txt` obeying the output contract (pinned normal convention; mask identical WxH to normal).

- [ ] **Step 1: Vendor SDM-UniPS inference with the CPU patch**

Copy the minimal inference subset of `spikes/phone_ps/SDM-UniPS-CVPR2023/sdm_unips` into `tools/vendor/sdm_unips/`, pinned. Apply the one required edit found in the spike (Rung 0 note): in `model_utils.loadmodel`, pass `map_location='cpu'` to `torch.load` so a CUDA-saved checkpoint loads CPU-only. Commit the patch in-tree (no clone-at-runtime).

- [ ] **Step 2: Write `tools/requirements-ps.txt`**

```
torch --index-url https://download.pytorch.org/whl/cpu
opencv-python
einops
imageio
numpy
pillow
```

Pin versions to those that passed the staircase (torch 2.13+cpu, per the spike log). This file installs into a **separate** env, never `.venv`.

- [ ] **Step 3: Write `tools/ps_tool.py`**

```python
"""External photometric-stereo tool: capture frames -> validated bundle.

Runs in its OWN torch env (tools/requirements-ps.txt). NEVER imported by the app
(the app is torch-free). Emits normal.png + mask.png + report.txt; either a valid
bundle or a loud abort with a reason.

Usage:
  python tools/ps_tool.py --frames path/to/frames_dir \\
      --checkpoint path/to/nml.pytmodel --out path/to/out_dir
"""
from __future__ import annotations

import argparse
from pathlib import Path

import numpy as np
from PIL import Image

from ps_stages import (CaptureError, align_to_reference, consensus_mask,
                       encode_normals, select_frames)

MAX_SIDE = 512


def _load_frames(frames_dir: Path):
    paths = sorted(p for p in frames_dir.iterdir()
                   if p.suffix.lower() in (".png", ".jpg", ".jpeg"))
    frames = [np.asarray(Image.open(p).convert("RGB")) for p in paths]
    return paths, frames


def _mask_each(frames):
    # Per-frame foreground mask (rembg if available, else GrabCut). Kept here in
    # the torch env; the app's masking.py is not reused to avoid coupling envs.
    import cv2
    masks = []
    for f in frames:
        # GrabCut fallback identical in spirit to masking.mask_from_grabcut.
        ...  # (implement per masking.mask_from_grabcut; border-inset rect + largest blob)
    return masks


def _run_sdm_unips(prepared_dir: Path, checkpoint: Path) -> np.ndarray:
    from vendor.sdm_unips import inference   # patched map_location='cpu'
    return inference.recover_normals(str(prepared_dir), str(checkpoint), target="normal")


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--frames", required=True, type=Path)
    ap.add_argument("--checkpoint", required=True, type=Path)
    ap.add_argument("--out", required=True, type=Path)
    args = ap.parse_args()
    args.out.mkdir(parents=True, exist_ok=True)

    paths, frames = _load_frames(args.frames)
    masks = _mask_each(frames)
    try:
        kept, report = select_frames(frames, masks)
    except CaptureError as e:
        (args.out / "report.txt").write_text(f"ABORT: {e}\n")
        print(f"ABORT: {e}")
        return 2

    a_frames, a_masks, _ = align_to_reference([frames[i] for i in kept],
                                              [masks[i] for i in kept])
    mask = consensus_mask(a_masks)
    # downscale <=512, write L_01..L_NN + mask.png into a prepared dir, run SDM-UniPS
    prepared = args.out / "prepared.data"
    ...  # write prepared frames + mask per the SDM-UniPS input layout
    normals = _run_sdm_unips(prepared, args.checkpoint)   # (H,W,3) unit, SDM convention
    normals = _to_pinned_convention(normals)              # normalize convention ONCE
    Image.fromarray(encode_normals(normals)).save(args.out / "normal.png")
    Image.fromarray((mask * 255).astype(np.uint8)).save(args.out / "mask.png")
    (args.out / "report.txt").write_text(
        f"frames used: {[paths[i].name for i in kept]}\n"
        f"dropped: {[paths[i].name for i in report['dropped']]}\n"
        f"ious: {[round(v, 3) for v in report['ious']]}\n"
        f"lighting std: {report['lighting_std']:.1f}\n")
    print(f"wrote bundle to {args.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
```

Fill the elided sections (`_mask_each` GrabCut body mirroring `masking.mask_from_grabcut`; the prepared-dir writer following the SDM-UniPS `DATA/<object>.data/{mask.png,L_*.png}` layout from the spike protocol; `_to_pinned_convention` flipping SDM's output axes to R=x-right/G=y-up/B=z-toward-viewer). Determine the exact convention flip once by round-tripping the staircase output (`spikes/phone_ps/run_black/results/black_aligned.data/normal.png`) through `relight.relight` and confirming highlights land on raised geometry under a top light — then hard-code that flip so the app needs no toggle.

- [ ] **Step 4: Write `tools/README-ps.md`**

Document: the separate env (`python -m venv tools/.ps-venv && tools/.ps-venv/Scripts/pip install -r tools/requirements-ps.txt`), the one-time 445 MB checkpoint fetch from Dropbox (kept gitignored), the vendored inference + `map_location='cpu'` patch, and the CLI invocation. State plainly that this env is separate from `.venv` and torch never enters the app.

- [ ] **Step 5: Update `.gitignore`**

Add:

```
# ps_tool: heavy artifacts never committed
tools/.ps-venv/
tools/**/checkpoint*
*.pytmodel
```

- [ ] **Step 6: Manual acceptance smoke (user-run — NOT self-run)**

This is a manual gate. Ask the user to run, on a real black-primed capture:

```
tools/.ps-venv/Scripts/python tools/ps_tool.py \
  --frames spikes/phone_ps/data/black.data \
  --checkpoint <checkpoint>/nml.pytmodel \
  --out /tmp/ps_out
```

Confirm: `normal.png` + `mask.png` + `report.txt` written; dimensions match; `report.txt` lists frames used/dropped; the black-primer worst case (2/6 frames dropped historically) still yields ≥4 clean frames. Then import the bundle in the app and confirm the plan tracks geometry.

- [ ] **Step 7: Commit**

```bash
git add tools/ps_tool.py tools/requirements-ps.txt tools/README-ps.md tools/vendor .gitignore
git commit -m "feat(ps_tool): vendored SDM-UniPS inference + capture orchestration"
```

---

### Task 8: `docs/ps-capture-guide.md`

Productize the spike protocol's capture recipe into a user-facing guide.

**Files:**
- Create: `docs/ps-capture-guide.md`

**Interfaces:**
- Consumes: `spikes/phone_ps_spike_protocol.md` (the validated recipe).
- Produces: a standalone capture guide referenced by `ps_mode._import_gate()` and `tools/README-ps.md`.

- [ ] **Step 1: Write the guide**

`docs/ps-capture-guide.md` covering, distilled from the protocol and the two real rungs:
- **Fixed pose:** phone braced/tripod, mini and camera do not move; only the light moves. (Both real rungs needed software drift-correction from handheld — a tripod removes that risk.)
- **One moving light:** a single bright source to ~6–8 distinct off-axis positions (upper-left, upper-right, left, right, top…). The opposite of on-axis flash.
- **Shading variation everywhere:** no region in shadow in all shots; none blown out in all shots.
- **Consistent exposure, no HDR/flash;** brighter exposure for black primer (Rung 2 needed it for SNR).
- **Shoot extra (6–8):** `ps_tool` drops frames that fail the IoU gate (2/6 lost to base-cutoff masking historically); extras keep you above the 4-frame minimum.
- **Mask-friendly background:** plain, high-contrast so per-frame masking is consistent (inconsistent background removal was the top residual risk).
- Cross-link `tools/README-ps.md` for running `ps_tool`.

- [ ] **Step 2: Commit**

```bash
git add docs/ps-capture-guide.md
git commit -m "docs: photometric-stereo capture guide"
```

---

## Manual Acceptance Gate (user-run, end to end)

Run after Task 7. Not self-run.

- [ ] Capture a real **black-primed** mini per `docs/ps-capture-guide.md` (fixed pose, one moving light, 6–8 shots).
- [ ] `tools/ps_tool.py` produces `normal.png` + `mask.png` + `report.txt`; report shows ≥4 frames survived.
- [ ] In the app, choose **Import normal map (photometric stereo)**, upload the two files; import validates and shows the relight panel.
- [ ] Drag azimuth/elevation (and try presets); the highlight plan **relocates** as the light moves and bands track raised geometry (helmet ridges, pauldron tops), not the silhouette.
- [ ] Regions, palette, coverage, edges, and paint-along steps all render on the relit render without error.
- [ ] The luminance path, the "Colored / painted mini" toggle, and the Photo-quality panel are **absent** in PS mode.

---

## Self-Review

**1. Spec coverage** — every spec section maps to a task:
- Component 1 (`ps_tool` contract, stages, output contract, env/vendoring, capture guide) → Tasks 6 (pure stages), 7 (inference/env/vendoring/report), 8 (guide).
- Component 2 (`relight.py`: `load_normals`, `light_dir`, `relight`, ALBEDO/AMBIENT, diffuse-only) → Task 1.
- Component 3 (third input branch, PS mode, `relight_panel`, one engine call rgb/light-field split, session keys, suppress luminance UI) → Tasks 3, 4, 5.
- One engine touch (`analyze_regions(light_field=)`, absent=byte-identical, present=bypass) → Task 2.
- Error handling (app import validation: dims + plausible unit normals; empty-mask/degenerate warning) → Task 5 (`_import_gate` dims + `plausible_unit_normals`); the empty-mask/degenerate-light gentle warning is covered by the existing per-region flat warnings in `results.render` (a uniformly-zero light field yields flat regions → the existing `flat_albedo`/`capped` warnings fire) — no new code needed, and this is called out here so the executor does not add a redundant path.
- Testing strategy (synthetic fixture; relight TDD; analyze_regions regression + bypass; ps_tool pure stages + round-trip; UI AppTest; manual gate) → fixture in Task 1; relight tests Task 1; pipeline tests Task 2; UI tests Tasks 3–5; ps_stages tests Task 6; manual gate after Task 7.
- Rollout/build order (1 relight, 2 injection, 3 app PS-mode, 4 ps_tool, 5 guide) → Tasks ordered 1→2→(3,4,5 app)→(6,7 ps_tool)→8; app side (1–5) delivers value against the fixture independent of ps_tool, matching the spec's note.

**2. Placeholder scan** — the only elisions are in Task 7's `ps_tool.py` (`_mask_each` GrabCut body, prepared-dir writer, `_to_pinned_convention`), each with an explicit instruction pointing at the exact existing code to mirror (`masking.mask_from_grabcut`), the documented input layout (spike protocol), and a concrete procedure to fix the convention once (round-trip the committed staircase normal map). These are external-tool integration points whose exact form depends on the vendored inference's output; they are deliberately specified as procedures, not fabricated code, and gated by a manual smoke rather than a unit test per the spec.

**3. Type consistency** — `light_field`: `(H,W)` float32 `[0,1]` throughout (`relight.relight` → `results.render` → `analyze_regions` → `band_light`). `relit_grey`: `(H,W,3)` uint8 (`relight.relight` → `editor.render_editor` as `rgb` → `overlay.paint_*`). Mask crosses as bool (`keys.PS_MASK`, `ShadingResult.mask`) and as uint8 0/255 (`alpha` into `analyze_regions`/`compute_mask`); the `(mask*255).astype(uint8)` conversion is explicit at each boundary. `relight._decode` is the single decode used by both `load_normals` and `ps_mode` (after dim/plausibility validation), and `ps_stages.encode_normals` is its exact inverse (locked by the round-trip test in Task 6). `analyze_regions` signature adds `light_field=None` as the final parameter; the `results.render` call passes it by keyword.
