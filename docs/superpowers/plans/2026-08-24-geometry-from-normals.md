# Geometry-from-Normals (Fork B, slice 1) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Derive a true surface-geometry toolkit from the recovered normal field and ship the first consumer — light-independent geometric edge highlights — without changing Path L (single-photo luminance) behaviour at all.

**Architecture:** A new pure module `surface.py` (numpy in/out, torch-free, UI-agnostic, same discipline as `relight.py`) computes `curvature`, `ambient_occlusion`, and `reflect` from an already-normalized normal field. `edges.py` gains a curvature-sourced `geometric_edge_mask` sibling to the existing light-gradient `edge_mask`. `pipeline.analyze_regions` gains one optional `normal_field=None` parameter threaded exactly like the existing `light_field`; when present the edge overlays come from curvature, when absent every branch takes today's path (byte-identical). The app passes the session `NORMALS` as `normal_field=` in PS mode only.

**Tech Stack:** Python 3.11, numpy, OpenCV (`cv2`), Streamlit (UI only). Tests: pytest + `streamlit.testing.v1.AppTest`.

**Spec:** `docs/superpowers/specs/2026-08-24-geometry-from-normals-design.md`

## Global Constraints

Every task's requirements implicitly include this section.

- **`surface.py` and the `edges.py` additions are pure:** numpy in, numpy out. No Streamlit, no torch, no I/O. Same shape/discipline as `relight.py`.
- **Pinned normal convention (load-bearing):** `R=x-right, G=y-up, B=z-toward-viewer`. The field arriving at `surface.py` is *already normalized* (via `relight._decode`/`load_normals`) — **no per-import flip toggle**, defensive renormalize only.
- **Image rows grow downward but the convention is y-UP**, so `∂/∂y = −∂/∂row`. The in-plane divergence used for curvature is `∂(nx)/∂col − ∂(ny)/∂row`. Convex/outward = positive; concave/crease = negative.
- **Path L must be byte-identical to today.** Geometry is capability-gated on the *presence of a normal field*, never a mode flag. `normal_field=None` ⇒ the geometry code path is never entered.
- **Module is named `surface.py`, NOT `geometry.py`** — `ui/geometry.py` already owns unrelated 2D lasso path math.
- **Reuse the committed synthetic fixture** from the PS work: `tests/fixtures/ps/synth_normal.png` + `synth_mask.png` (a dome + ridges). No torch, no captures needed to test the whole slice.
- **Branch discipline:** work on `feat/geometry-from-normals`. Never build straight on `main`; feature branch + PR/merge.
- **Test/commit commands:** run tests with `.venv/Scripts/python -m pytest`. Commit with `git -C "C:/Users/ag/alvaro/git/mini-highlight-advisor" ...` (absolute path).

**Before Task 1**, create the branch:
```bash
git -C "C:/Users/ag/alvaro/git/mini-highlight-advisor" checkout -b feat/geometry-from-normals
```

---

### Task 1: `surface.curvature`

The foundational, and only *consumed*, primitive: signed mean curvature as the divergence of the in-plane normal field.

**Files:**
- Create: `src/mini_highlight_advisor/surface.py`
- Test: `tests/test_surface_curvature.py`

**Interfaces:**
- Consumes: an already-normalized `normals: (H,W,3) float32` and `mask: (H,W) bool` (pinned convention).
- Produces:
  - `_validate(normals) -> (H,W,3) float32` — shape-checks `(H,W,3)`, defensively renormalizes to unit length (mirrors `relight.load_normals`). Raises `ValueError` on bad shape.
  - `curvature(normals, mask) -> (H,W) float32` — signed mean curvature; `>0` convex ridge, `<0` concave crease, `0` off-mask.

- [ ] **Step 1: Write the failing tests**

Create `tests/test_surface_curvature.py`:

```python
import numpy as np
import pytest
from pathlib import Path
from PIL import Image

from mini_highlight_advisor import surface, relight

FIX = Path(__file__).parent / "fixtures" / "ps"


def _dome():
    """The committed synthetic dome+ridges fixture (normals, mask)."""
    n = relight.load_normals(str(FIX / "synth_normal.png"))
    m = np.asarray(Image.open(FIX / "synth_mask.png").convert("L")) > 127
    return n, m


def _flat(h=20, w=20):
    n = np.zeros((h, w, 3), np.float32)
    n[..., 2] = 1.0                       # all facing the viewer
    return n, np.ones((h, w), bool)


def test_validate_rejects_bad_shape():
    with pytest.raises(ValueError):
        surface._validate(np.zeros((8, 8), np.float32))


def test_validate_renormalizes_to_unit():
    n = np.full((4, 4, 3), 3.0, np.float32)   # non-unit
    out = surface._validate(n)
    assert np.allclose(np.linalg.norm(out, axis=-1), 1.0, atol=1e-4)


def test_flat_region_curvature_is_zero():
    n, m = _flat()
    c = surface.curvature(n, m)
    assert c.shape == (20, 20) and c.dtype == np.float32
    assert np.allclose(c, 0.0, atol=1e-4)


def test_convex_dome_interior_is_positive():
    n, m = _dome()
    c = surface.curvature(n, m)
    # sample a well-inside-the-mask patch (avoid the silhouette boundary)
    interior = np.zeros_like(m)
    interior[50:78, 50:78] = True
    interior &= m
    assert c[interior].mean() > 0.0


def test_off_mask_is_exactly_zero():
    n, m = _dome()
    c = surface.curvature(n, m)
    assert np.all(c[~m] == 0.0)
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `.venv/Scripts/python -m pytest tests/test_surface_curvature.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'mini_highlight_advisor.surface'`

- [ ] **Step 3: Write minimal implementation**

Create `src/mini_highlight_advisor/surface.py`:

```python
"""Pure, torch-free surface geometry derived from a normal field.

Consumes the SAME pinned convention as relight.py (R=x-right, G=y-up,
B=z-toward-viewer) and the SAME already-normalized field — no flip toggle.
numpy in, numpy out; no Streamlit, no torch. Named surface.py (not geometry.py)
because ui/geometry.py already owns unrelated 2D lasso path math.
"""
from __future__ import annotations

import cv2
import numpy as np


def _validate(normals: np.ndarray) -> np.ndarray:
    """Shape-check (H,W,3) and defensively renormalize to unit (mirrors relight)."""
    n = np.asarray(normals, dtype=np.float32)
    if n.ndim != 3 or n.shape[2] != 3:
        raise ValueError(f"normals must be (H,W,3), got {n.shape}")
    norm = np.linalg.norm(n, axis=-1, keepdims=True)
    norm[norm == 0] = 1.0
    return (n / norm).astype(np.float32)


def curvature(normals: np.ndarray, mask: np.ndarray) -> np.ndarray:
    """Signed mean curvature = divergence of the in-plane normal field.

    >0 convex/outward ridge, <0 concave crease, 0 off-mask. Image rows grow
    downward but the convention is y-UP, so d/dy = -d/drow and the divergence is
    d(nx)/dcol - d(ny)/drow. Gaussian pre-blur calms primer grain (same rationale
    as edges._grad_mag). Off-mask components are zeroed so the field contributes
    nothing there.
    """
    n = _validate(normals)
    m = mask.astype(bool)
    nx = np.where(m, n[..., 0], 0.0).astype(np.float32)
    ny = np.where(m, n[..., 1], 0.0).astype(np.float32)
    nx = cv2.GaussianBlur(nx, (3, 3), 0)
    ny = cv2.GaussianBlur(ny, (3, 3), 0)
    dnx_dcol = cv2.Sobel(nx, cv2.CV_32F, 1, 0, ksize=3)
    dny_drow = cv2.Sobel(ny, cv2.CV_32F, 0, 1, ksize=3)
    curv = dnx_dcol - dny_drow            # convex/outward > 0
    curv[~m] = 0.0
    return curv.astype(np.float32)
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `.venv/Scripts/python -m pytest tests/test_surface_curvature.py -v`
Expected: PASS (5 tests)

- [ ] **Step 5: Commit**

```bash
git -C "C:/Users/ag/alvaro/git/mini-highlight-advisor" add src/mini_highlight_advisor/surface.py tests/test_surface_curvature.py
git -C "C:/Users/ag/alvaro/git/mini-highlight-advisor" commit -m "feat(surface): signed mean curvature from the normal field"
```

---

### Task 2: `surface.ambient_occlusion` + `surface.reflect`

The two remaining foundation primitives. Cheap, share the same fixture, and unblock the later cavity/AO and specular/NMM slices without another foundation pass. Built + tested now, **not consumed** this slice.

**Files:**
- Modify: `src/mini_highlight_advisor/surface.py` (append two functions)
- Test: `tests/test_surface_ao_reflect.py`

**Interfaces:**
- Consumes: `curvature` (Task 1), `_validate` (Task 1).
- Produces:
  - `ambient_occlusion(normals, mask) -> (H,W) float32` in `[0,1]`, `1` = exposed (convex/flat), `→0` = deep recess; off-mask `0`. Cavity-style: driven by the concave (negative) part of curvature, self-scaled by its 95th percentile inside the mask.
  - `reflect(view, normals) -> (H,W,3) float32` — `R = 2(N·V)N − V`, per pixel; `view` is a `(3,)` direction (broadcast) or a full `(H,W,3)` field; output unit-length where inputs are.

- [ ] **Step 1: Write the failing tests**

Create `tests/test_surface_ao_reflect.py`:

```python
import numpy as np

from mini_highlight_advisor import surface


def _flat(h=21, w=21):
    n = np.zeros((h, w, 3), np.float32)
    n[..., 2] = 1.0
    return n, np.ones((h, w), bool)


def _two_dips(h=21, w=41):
    """One field, two concave Gaussian valleys of DIFFERENT depth (shared scale).
    Shallow dip centred at col 10 (depth 3), deep dip at col 30 (depth 8)."""
    col = np.arange(w, dtype=np.float32)

    def slope(c0, depth, s=4.0):
        return depth * (col - c0) / (s * s) * np.exp(-((col - c0) ** 2) / (2 * s * s))

    n = np.zeros((h, w, 3), np.float32)
    n[..., 0] = (-(slope(10, 3.0) + slope(30, 8.0)))[None, :]   # outward normal: nx = -dh/dcol
    n[..., 2] = 1.0
    return n, np.ones((h, w), bool)


# --- ambient_occlusion ---

def test_ao_flat_is_fully_exposed():
    n, m = _flat()
    ao = surface.ambient_occlusion(n, m)
    assert ao.dtype == np.float32
    assert np.allclose(ao[m], 1.0, atol=1e-3)


def test_ao_crevice_is_more_occluded_than_flat():
    n, m = _two_dips()
    ao = surface.ambient_occlusion(n, m)
    row = ao.shape[0] // 2
    assert ao[row, 30] < ao[row, 0]        # bottom of the deep dip vs a flat edge


def test_ao_monotone_with_recess_depth():
    n, m = _two_dips()
    ao = surface.ambient_occlusion(n, m)
    deep = ao[:, 26:35].min()              # deep dip window (depth 8)
    shallow = ao[:, 6:15].min()            # shallow dip window (depth 3)
    assert deep < shallow


def test_ao_off_mask_is_zero():
    n, m = _two_dips()
    m2 = m.copy()
    m2[:, :3] = False
    ao = surface.ambient_occlusion(n, m2)
    assert np.all(ao[~m2] == 0.0)


# --- reflect ---

def test_reflect_facing_viewer_is_identity():
    n = np.zeros((5, 5, 3), np.float32); n[..., 2] = 1.0     # N = +Z
    r = surface.reflect(np.array([0, 0, 1], np.float32), n)  # V = +Z
    assert np.allclose(r, np.array([0, 0, 1], np.float32), atol=1e-5)


def test_reflect_orthogonal_view_flips_view():
    n = np.zeros((3, 3, 3), np.float32); n[..., 2] = 1.0     # N = +Z
    r = surface.reflect(np.array([1, 0, 0], np.float32), n)  # V = +X, N.V = 0 => R = -V
    assert np.allclose(r, np.array([-1, 0, 0], np.float32), atol=1e-5)


def test_reflect_output_is_unit_length():
    rng = np.random.default_rng(0)
    raw = rng.normal(size=(6, 6, 3)).astype(np.float32)
    n = surface._validate(raw)
    r = surface.reflect(np.array([0, 0, 1], np.float32), n)
    assert np.allclose(np.linalg.norm(r, axis=-1), 1.0, atol=1e-4)
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `.venv/Scripts/python -m pytest tests/test_surface_ao_reflect.py -v`
Expected: FAIL with `AttributeError: module 'mini_highlight_advisor.surface' has no attribute 'ambient_occlusion'`

- [ ] **Step 3: Write minimal implementation**

Append to `src/mini_highlight_advisor/surface.py`:

```python
def ambient_occlusion(normals: np.ndarray, mask: np.ndarray) -> np.ndarray:
    """Cavity-style AO from concavity: 1 = exposed (convex/flat), ->0 = deep recess.

    Concavity is the negative part of curvature, self-scaled by its 95th percentile
    inside the mask so the map is comparable across minis. Off-mask 0. (Foundation
    primitive — built and tested here, consumed by the later cavity/AO slice.)
    """
    m = mask.astype(bool)
    conc = np.clip(-curvature(normals, m), 0.0, None)
    vals = conc[m]
    scale = float(np.percentile(vals, 95)) if vals.size and vals.max() > 0 else 1.0
    ao = 1.0 - np.clip(conc / (scale + 1e-6), 0.0, 1.0)
    ao[~m] = 0.0
    return ao.astype(np.float32)


def reflect(view: np.ndarray, normals: np.ndarray) -> np.ndarray:
    """Reflection vectors R = 2(N.V)N - V, per pixel.

    `view` is a (3,) direction (broadcast) or a full (H,W,3) field; output is
    unit-length where inputs are. (Foundation primitive for the later specular/NMM
    slice.)
    """
    n = _validate(normals)
    v = np.asarray(view, np.float32)
    v = v / (np.linalg.norm(v, axis=-1, keepdims=True) + 1e-12)
    ndotv = np.sum(n * v, axis=-1, keepdims=True)
    return (2.0 * ndotv * n - v).astype(np.float32)
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `.venv/Scripts/python -m pytest tests/test_surface_ao_reflect.py -v`
Expected: PASS (7 tests)

- [ ] **Step 5: Commit**

```bash
git -C "C:/Users/ag/alvaro/git/mini-highlight-advisor" add src/mini_highlight_advisor/surface.py tests/test_surface_ao_reflect.py
git -C "C:/Users/ag/alvaro/git/mini-highlight-advisor" commit -m "feat(surface): ambient_occlusion + reflect foundation primitives"
```

---

### Task 3: `edges.geometric_edge_mask` (+ extreme sibling)

The first consumer's core: edge highlights sourced from convex curvature instead of the light gradient — the same despeckle/percentile machinery, a different source. **Light-independence is the key test.**

**Files:**
- Modify: `src/mini_highlight_advisor/edges.py`
- Test: `tests/test_edges_geometric.py`

**Interfaces:**
- Consumes: `surface.curvature` (Task 1); module-local `_despeckle`, `_MIN_EDGE_AREA` (existing in `edges.py`).
- Produces:
  - `geometric_edge_mask(normals, mask, sensitivity=0.5) -> (H,W) bool` — thresholds convex curvature (`>0` side only); reuses `_despeckle` and the same `sensitivity→percentile` mapping as `edge_mask`.
  - `geometric_extreme_edge_mask(normals, mask, sensitivity=0.5) -> (H,W) bool` — the sharpest-30% subset of `geometric_edge_mask`, mirroring `extreme_edge_mask`.

- [ ] **Step 1: Write the failing tests**

Create `tests/test_edges_geometric.py`:

```python
import numpy as np

from mini_highlight_advisor import relight
from mini_highlight_advisor.edges import (
    edge_mask, geometric_edge_mask, geometric_extreme_edge_mask,
)


def _vridge(h=40, w=40, c0=20, half=8):
    """A convex vertical crest at column c0: nx sweeps -sin..+sin THROUGH the
    crest so curvature (d nx/dcol) is positive, peaking on the crest column."""
    col = np.arange(w, dtype=np.float32)
    ang = np.clip((col - c0) / half, -1.0, 1.0) * (np.pi / 3.0)
    n = np.zeros((h, w, 3), np.float32)
    n[..., 0] = np.sin(ang)[None, :]
    n[..., 2] = np.cos(ang)[None, :]
    return n, np.ones((h, w), bool), c0


def test_geometric_edge_lands_on_crest():
    n, mask, c0 = _vridge()
    g = geometric_edge_mask(n, mask, 0.5)
    cols = np.where(g.any(axis=0))[0]
    assert cols.size > 0
    assert cols.min() >= c0 - 10 and cols.max() <= c0 + 10


def test_geometric_edge_is_light_independent():
    """The core value claim: the light-gradient edge MOVES with the virtual light;
    the curvature edge does not depend on light at all and stays on the crest."""
    n, mask, c0 = _vridge()
    lf1, _ = relight.relight(n, mask, relight.light_dir(0, 30))     # lit from the right
    lf2, _ = relight.relight(n, mask, relight.light_dir(180, 30))   # lit from the left
    e1 = edge_mask(lf1, mask, 0.5)
    e2 = edge_mask(lf2, mask, 0.5)
    g = geometric_edge_mask(n, mask, 0.5)
    assert not np.array_equal(e1, e2)                  # light-gradient edge moves
    cols = np.where(g.any(axis=0))[0]                  # curvature edge sits on crest
    assert cols.size > 0
    assert abs(int(round(cols.mean())) - c0) <= 3


def test_geometric_flat_normals_empty():
    n = np.zeros((30, 30, 3), np.float32); n[..., 2] = 1.0
    mask = np.ones((30, 30), bool)
    assert geometric_edge_mask(n, mask, 0.5).sum() == 0


def test_geometric_speckle_is_dropped():
    """Isolated single-pixel tilts (primer grain / gravel base) must be removed by
    the connected-component filter — no line-like ridge among them."""
    n = np.zeros((60, 60, 3), np.float32); n[..., 2] = 1.0
    for (r, c) in [(10, 10), (20, 40), (35, 15), (48, 50), (30, 30)]:
        n[r, c, 0] = 0.4
        n[r, c, 2] = np.sqrt(1.0 - 0.4 ** 2)
    mask = np.ones((60, 60), bool)
    assert geometric_edge_mask(n, mask, 0.5).sum() == 0


def test_geometric_extreme_is_subset_of_main():
    n, mask, _ = _vridge()
    main = geometric_edge_mask(n, mask, 0.5)
    ext = geometric_extreme_edge_mask(n, mask, 0.5)
    assert np.all(main[ext])
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `.venv/Scripts/python -m pytest tests/test_edges_geometric.py -v`
Expected: FAIL with `ImportError: cannot import name 'geometric_edge_mask'`

- [ ] **Step 3: Write minimal implementation**

In `src/mini_highlight_advisor/edges.py`, add the import near the top (after `import numpy as np`):

```python
from .surface import curvature
```

Append at the end of `edges.py`:

```python
def geometric_edge_mask(normals: np.ndarray, mask: np.ndarray,
                        sensitivity: float = 0.5) -> np.ndarray:
    """Edge highlights from convex curvature of the normal field — light-independent.

    Same sensitivity->percentile mapping and despeckle as edge_mask; the only
    difference is the source (convex curvature magnitude, not light gradient). The
    convex-side filter (clip to >0) is the geometric analogue of _bright_side.
    """
    mask = mask.astype(bool)
    conv = np.clip(curvature(normals, mask), 0.0, None)   # convex ridges only
    conv[~mask] = 0.0
    vals = conv[mask]
    vals = vals[vals > 0]
    if vals.size == 0:
        return np.zeros(mask.shape, bool)
    pct = float(np.clip(94.0 - 12.0 * sensitivity, 82.0, 97.0))
    thr = np.percentile(vals, pct)
    strong = (conv >= thr) & mask
    return _despeckle(strong)


def geometric_extreme_edge_mask(normals: np.ndarray, mask: np.ndarray,
                                sensitivity: float = 0.5) -> np.ndarray:
    base = geometric_edge_mask(normals, mask, sensitivity)
    if not base.any():
        return np.zeros(mask.astype(bool).shape, bool)
    conv = np.clip(curvature(normals, mask.astype(bool)), 0.0, None)
    thr = np.percentile(conv[base], 70.0)   # sharpest 30% of the main-edge pixels
    return base & (conv >= thr)
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `.venv/Scripts/python -m pytest tests/test_edges_geometric.py -v`
Expected: PASS (5 tests)

- [ ] **Step 5: Commit**

```bash
git -C "C:/Users/ag/alvaro/git/mini-highlight-advisor" add src/mini_highlight_advisor/edges.py tests/test_edges_geometric.py
git -C "C:/Users/ag/alvaro/git/mini-highlight-advisor" commit -m "feat(edges): curvature-sourced geometric edge masks (light-independent)"
```

---

### Task 4: `pipeline` — thread `normal_field` and select the edge overlay source

Add one optional `normal_field=None` param to `analyze_regions`, thread `normals=` into `plan_region` exactly like `light`, and switch the **edge overlay source** to curvature when normals are present. Path L (no normal field) stays byte-identical.

**Scope note (from the spec):** only the *edge overlays* (`main` + `extreme`, the visible highlight on the combined preview) switch source — this is the seam the spec shows and the tests lock. The per-layer edge *step images* (`edge_steps`, the paint-along guide) remain light-sourced this slice; a follow-up can align them if wanted.

**Files:**
- Modify: `src/mini_highlight_advisor/pipeline.py` (`plan_region` ~116-154, `analyze_regions` ~157-201, imports line 11)
- Test: `tests/test_pipeline_normal_field.py`

**Interfaces:**
- Consumes: `edges.geometric_edge_mask`, `edges.geometric_extreme_edge_mask` (Task 3); existing `edge_mask`, `extreme_edge_mask`.
- Produces:
  - `plan_region(rgb, sub_mask, light, name, palette, coverage, edges=True, extreme_edge=False, edge_sensitivity=0.5, relief_cap=False, flat_albedo=False, normals=None)` — new trailing `normals=None`. When `normals is not None`, `edge_overlays` are computed from `geometric_edge_mask`/`geometric_extreme_edge_mask`; otherwise unchanged.
  - `analyze_regions(rgb, alpha, default_palette, coverage=None, regions=None, edges=True, extreme_edge=False, edge_sensitivity=0.5, relief_cap=False, per_region_norm=False, light_field=None, normal_field=None)` — new trailing `normal_field=None`, validated against `rgb` dims, threaded into every `plan_region` call.

- [ ] **Step 1: Write the failing tests**

Create `tests/test_pipeline_normal_field.py`:

```python
import numpy as np
import pytest

from mini_highlight_advisor.pipeline import analyze_regions, WHOLE_MINI
from mini_highlight_advisor.edges import edge_mask
from mini_highlight_advisor.palette import DEFAULT_PALETTE, default_coverage

PAL = DEFAULT_PALETTE[:5]
COV = default_coverage(5)


def _whole(res):
    return next(p for p in res.plans if p.name == WHOLE_MINI)


def _vridge(h=48, w=48, c0=24, half=8):
    col = np.arange(w, dtype=np.float32)
    ang = np.clip((col - c0) / half, -1.0, 1.0) * (np.pi / 3.0)
    n = np.zeros((h, w, 3), np.float32)
    n[..., 0] = np.sin(ang)[None, :]
    n[..., 2] = np.cos(ang)[None, :]
    return n, c0


def test_normal_absent_overlay_is_light_gradient():
    # Regression lock: no normal_field -> overlay is exactly today's edge_mask.
    ramp = np.tile(np.linspace(40, 220, 48, dtype=np.uint8), (48, 1))
    rgb = np.stack([ramp, ramp, ramp], axis=-1)
    alpha = np.full((48, 48), 255, np.uint8)
    res = analyze_regions(rgb, alpha, PAL, COV, [], edges=True)
    whole = _whole(res)
    expected = edge_mask(res.light, whole.sub_mask, 0.5)
    np.testing.assert_array_equal(whole.edge_overlays[0][0], expected)


def test_normal_present_overlay_from_curvature():
    # Uniform relit light (no gradient) but a REAL ridge in the normals: the
    # overlay must come from curvature and land on the crest.
    n, c0 = _vridge()
    rgb = np.full((48, 48, 3), 120, np.uint8)          # flat luminance
    alpha = np.full((48, 48), 255, np.uint8)
    uniform = np.full((48, 48), 0.5, np.float32)       # uniform light -> no edges
    res = analyze_regions(rgb, alpha, PAL, COV, [], edges=True,
                          light_field=uniform, normal_field=n)
    ov = _whole(res).edge_overlays[0][0]
    assert ov.sum() > 0
    cols = np.where(ov.any(axis=0))[0]
    assert abs(int(round(cols.mean())) - c0) <= 4
    # sanity: the light-gradient path finds nothing on this uniform light
    assert edge_mask(uniform, np.ones((48, 48), bool), 0.5).sum() == 0


def test_normal_field_shape_mismatch_raises():
    rgb = np.full((20, 20, 3), 120, np.uint8)
    alpha = np.full((20, 20), 255, np.uint8)
    bad = np.zeros((10, 10, 3), np.float32)
    with pytest.raises(ValueError):
        analyze_regions(rgb, alpha, PAL, COV, [], edges=True,
                        light_field=np.full((20, 20), 0.5, np.float32),
                        normal_field=bad)
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `.venv/Scripts/python -m pytest tests/test_pipeline_normal_field.py -v`
Expected: FAIL — `test_normal_present_overlay_from_curvature` errors on the unknown `normal_field=` kwarg (and the mismatch test does not raise).

- [ ] **Step 3: Write minimal implementation**

In `pipeline.py`, extend the edges import (line 11):

```python
from .edges import (
    edge_mask, extreme_edge_mask, geometric_edge_mask, geometric_extreme_edge_mask,
)
```

Change the `plan_region` signature (line ~116-119) to add `normals`:

```python
def plan_region(rgb, sub_mask, light, name, palette, coverage,
                edges: bool = True, extreme_edge: bool = False,
                edge_sensitivity: float = 0.5,
                relief_cap: bool = False, flat_albedo: bool = False,
                normals: np.ndarray | None = None) -> RegionPlan:
```

Replace the overlay block inside `plan_region` (currently lines ~143-151) with source selection:

```python
    overlays = None
    if edges:
        steps = steps + edge_steps(rgb, light, sub_mask, colors,
                                   sensitivity=edge_sensitivity,
                                   extreme=extreme_edge, start_index=len(palette))
        two_tier = extreme_edge and len(colors) >= 5  # match edge_steps guard
        if normals is not None:
            main = geometric_edge_mask(normals, sub_mask, edge_sensitivity)
        else:
            main = edge_mask(light, sub_mask, edge_sensitivity)
        overlays = [(main, colors[-2] if two_tier else colors[-1])]
        if two_tier:
            if normals is not None:
                ext = geometric_extreme_edge_mask(normals, sub_mask, edge_sensitivity)
            else:
                ext = extreme_edge_mask(light, sub_mask, edge_sensitivity)
            overlays.append((ext, colors[-1]))
```

In `analyze_regions`, add the parameter (line ~162) and validation, and thread `normals` via `ekw`. Change the signature tail:

```python
                    light_field: np.ndarray | None = None,
                    normal_field: np.ndarray | None = None) -> MultiRegionResult:
```

Immediately after `regions = regions or []` (line ~163), validate:

```python
    if normal_field is not None:
        if (normal_field.ndim != 3 or normal_field.shape[2] != 3
                or normal_field.shape[:2] != rgb.shape[:2]):
            raise ValueError(
                f"normal_field {getattr(normal_field, 'shape', None)} must be "
                f"(H,W,3) matching rgb {rgb.shape[:2]}")
```

Add `normals=normal_field` to the shared `ekw` dict (line ~178-179):

```python
    ekw = dict(edges=edges, extreme_edge=extreme_edge, edge_sensitivity=edge_sensitivity,
               relief_cap=relief_cap, normals=normal_field)
```

(Both the whole-mini and per-region `plan_region(... **ekw)` calls now receive `normals`; the global field is localized by each region's `sub_mask`, exactly as `light` is.)

- [ ] **Step 4: Run tests to verify they pass**

Run: `.venv/Scripts/python -m pytest tests/test_pipeline_normal_field.py tests/test_pipeline_light_field.py -v`
Expected: PASS (new file + the existing light-field regression lock still green)

- [ ] **Step 5: Commit**

```bash
git -C "C:/Users/ag/alvaro/git/mini-highlight-advisor" add src/mini_highlight_advisor/pipeline.py tests/test_pipeline_normal_field.py
git -C "C:/Users/ag/alvaro/git/mini-highlight-advisor" commit -m "feat(pipeline): capability-gated normal_field -> curvature edge overlays"
```

---

### Task 5: App wiring — pass session `NORMALS` in PS mode

Thread `normal_field` through the shared editor chain (`ps_mode → editor → results → analyze_regions`). Photo mode and the multi-angle gallery pass nothing → `normal_field=None` → Path L untouched.

**Files:**
- Modify: `ui/ps_mode.py` (the `render_editor` call, ~65-66)
- Modify: `ui/editor.py` (`render_editor` signature + `results.render` call, 12-25)
- Modify: `ui/results.py` (`render` signature line 13 + `analyze_regions` call ~74-79)
- Test: `tests/test_ui_ps_mode.py` (add one wiring smoke test)

**Interfaces:**
- Consumes: `analyze_regions(..., normal_field=)` (Task 4); `st.session_state[keys.NORMALS]` (already loaded in PS mode).
- Produces: `render_editor(..., normal_field=None)` and `results.render(..., normal_field=None)` — new trailing kw threaded straight to `analyze_regions`.

- [ ] **Step 1: Write the failing test**

Add to `tests/test_ui_ps_mode.py` (the `HARNESS` string and `FIX` already exist at the top of that file):

```python
def test_ps_mode_geometry_wiring_runs():
    # PS mode now passes the session normals to analyze_regions as normal_field;
    # the full editor must render end-to-end on the synthetic fixture without error.
    at = AppTest.from_string(HARNESS); at.run()
    assert not at.exception
    assert at.session_state["ps_normals"] is not None
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.venv/Scripts/python -m pytest tests/test_ui_ps_mode.py::test_ps_mode_geometry_wiring_runs -v`
Expected: FAIL — `render_editor()`/`results.render()`/`analyze_regions()` raise `TypeError: unexpected keyword argument 'normal_field'` once the calls below are wired (or, before wiring, the assertion is trivially green — so wire Step 3 first if it passes vacuously, then confirm it still passes). The meaningful gate is Step 4 with all three signatures updated.

- [ ] **Step 3: Write minimal implementation**

`ui/results.py` — add the parameter (line 13) and pass it through:

```python
def render(rgb, alpha, book, palette, picked, owned_paints, shading,
           light_field=None, normal_field=None) -> None:
```

In the `analyze_regions` call (~74-79), add the trailing kwarg:

```python
    multi = analyze_regions(rgb, alpha, wp, wcov, drawn,
                            edges=edges, extreme_edge=extreme_edge,
                            edge_sensitivity=edge_sensitivity,
                            relief_cap=relief_cap,
                            per_region_norm=per_region_norm,
                            light_field=light_field,
                            normal_field=normal_field)
```

`ui/editor.py` — add the parameter (line 12) and forward it (line 24-25):

```python
def render_editor(rgb, alpha, shading, book, picked, owned_paints,
                  light_field=None, normal_field=None) -> None:
```

```python
    results.render(rgb, alpha, book, palette, picked, owned_paints, shading,
                   light_field=light_field, normal_field=normal_field)
```

`ui/ps_mode.py` — pass the session normals in the `render_editor` call (~65-66). `normals` is already bound at line 51:

```python
    editor.render_editor(relit_grey, mask_u8, shading, book, picked, owned_paints,
                         light_field=light_field, normal_field=normals)
```

- [ ] **Step 4: Run the PS UI suite to verify it passes**

Run: `.venv/Scripts/python -m pytest tests/test_ui_ps_mode.py -v`
Expected: PASS (existing tests + the new wiring smoke test — the fixture normals now drive curvature edges through the full editor with no exception)

- [ ] **Step 5: Commit**

```bash
git -C "C:/Users/ag/alvaro/git/mini-highlight-advisor" add ui/ps_mode.py ui/editor.py ui/results.py tests/test_ui_ps_mode.py
git -C "C:/Users/ag/alvaro/git/mini-highlight-advisor" commit -m "feat(ui): pass PS-mode normals as normal_field to the editor pipeline"
```

---

### Final: full regression sweep

- [ ] **Run the whole suite** to confirm nothing regressed (especially the Path L / light-field locks):

Run: `.venv/Scripts/python -m pytest -q`
Expected: PASS. Known pre-existing exception: 2 failures in `tests/test_ui_gallery.py` unrelated to this slice — confirm the count is unchanged, not increased.

---

## Self-Review

**1. Spec coverage:**

| Spec requirement | Task |
|---|---|
| `surface.py` pure/torch-free, pinned convention, no flip, defensive renormalize | Tasks 1-2 (`_validate`) |
| `curvature` = divergence of in-plane normals, Gaussian-smoothed, convex=+, off-mask 0 | Task 1 |
| `ambient_occlusion` [0,1], 1=exposed, 0=recess | Task 2 |
| `reflect` R=2(N·V)N−V, unit output | Task 2 |
| All three primitives built + tested (only curvature consumed) | Tasks 1-2 |
| `geometric_edge_mask` thresholds convex curvature, reuses despeckle + sensitivity mapping | Task 3 |
| Light-independence test (core value claim) | Task 3 (`test_geometric_edge_is_light_independent`) |
| speckle dropped / empty on flat normals (graceful-empty) | Task 3 |
| `extreme_edge` follows the same source selection | Tasks 3 + 4 (`geometric_extreme_edge_mask`) |
| `analyze_regions` gains `normal_field=None`, threaded like `light_field` | Task 4 |
| `plan_region` gains `normals=`; overlay source select | Task 4 |
| Path L byte-identical when `normal_field` omitted | Task 4 (`test_normal_absent_overlay_is_light_gradient`) + light-field regression lock |
| curvature/light-gradient disagreement proves source swap | Task 4 (`test_normal_present_overlay_from_curvature`) |
| Shape-mismatch raises a clear error at the seam | Task 4 (`test_normal_field_shape_mismatch_raises`) |
| App passes `NORMALS` as `normal_field=` in PS mode; Path L UI untouched | Task 5 |
| UI AppTest smoke (PS import still renders) | Task 5 |
| Reuse committed synthetic fixture | Tasks 1, 3 |

Cavity/specular/auto-region *outputs* are explicitly out of scope (foundation primitives only) — no tasks, correctly.

**2. Placeholder scan:** No TBD/TODO/"handle edge cases"/"similar to Task N". Every code and test step carries literal content. ✔

**3. Type consistency:** `curvature`, `ambient_occlusion`, `reflect`, `_validate` used with identical signatures in Tasks 1-3. `geometric_edge_mask`/`geometric_extreme_edge_mask` defined in Task 3 and called with the same signatures in Task 4. `normal_field` (pipeline param) vs `normals` (plan_region param) naming is intentional and consistent across Tasks 4-5 (`analyze_regions` exposes `normal_field`; it maps to `plan_region(normals=...)` via `ekw`). `edge_overlays[0][0]` (bool mask) accessed consistently in Task 4 tests, matching the `(mask, color)` tuples `plan_region` builds. ✔

**One flagged scope boundary** (surfaced, not hidden): `edge_steps` (per-layer paint-along step images) stays light-sourced this slice; only the visible edge *overlays* switch to curvature. This matches the spec's shown seam and testing strategy exactly. If step-image alignment is wanted, it is a small follow-up.
