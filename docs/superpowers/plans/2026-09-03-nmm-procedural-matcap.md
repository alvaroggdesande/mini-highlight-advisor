# NMM v2 — Procedural Matcap Reflection Environment — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace the parked NMM v1 monotone-gradient render model with a procedural-matcap reflection environment + value-anchored banding, so a painter sees exactly where each metal colour lands.

**Architecture:** A small "environment disk" (matcap) is built once from four painterly knobs (`horizon`, `light_dir`, `bounce`, `hotspot`); every surface pixel looks up its brightness by sampling that disk along its reflection vector `R`. NMM regions band by **value interval** (not pixel rank) so flat sky collapses to one paint and the thin hard horizon keeps its own band. Matte regions are byte-identical to today.

**Tech Stack:** Python 3.11, numpy, OpenCV (already used by `surface.py`), Streamlit (UI only), pytest + `streamlit.testing.v1.AppTest`. Torch-free.

**Spec:** `docs/superpowers/specs/2026-09-03-nmm-procedural-matcap-design.md`

## Global Constraints

- **Pinned normal convention** (verbatim, from `surface.py` / `relight.py`): `R = x-right, y-up, z-toward-viewer`. The env disk uses `u = x-right`, `v = y-up`; disk **row 0 is the top (v = +1, sky)**, last row is the bottom (v = −1, ground).
- **Torch-free, numpy in / numpy out** for all `materials.py` / `banding.py` / `overlay.py` code. No Streamlit imports in those modules.
- **Paint colours are `np.ndarray` float32 shape `(3,)`, RGB in `0..255`** (`PaintColor.rgb` parses hex to `0..255`). Env-preview tinting casts these straight to `uint8`.
- **`bands`** is an int array, one layer per masked pixel; **off-mask = −1**, band `0` = darkest, `n−1` = lightest. `mask == (bands >= 0)`.
- **Regression lock (non-negotiable):** when every region is `material="matte"` (and in Path L / photo mode), output is **byte-identical** to today. `band_light` math is untouched; the NMM `env` is unused on the matte path.
- **Capability gate:** NMM controls appear only when `normal_field is not None` (PS mode). Photo / Path-L mode renders none of it.
- **Colours are never invented by the env.** The region's own palette supplies the metal ramp; the env only *places* those colours on the reflection curve.
- **Determinism:** every term in `build_nmm_env` is a smooth deterministic function of the knobs — **no randomness** (`Math.random`/`np.random` forbidden), so disks are reproducible and directly assertable.
- **Process:** feature branch `feat/nmm-procedural-matcap` (already checked out). Never build on `main`. Commit after every green step.

---

## File Structure

**Modified (core):**
- `src/mini_highlight_advisor/materials.py` — add `build_nmm_env` + `NMM_PRESETS` + `_bilinear`; **rewrite** `nmm_light` to sample `env`; **delete** `_CONTRAST` and the monotonicity blend. Keep `_smoothstep` (reused by `build_nmm_env`).
- `src/mini_highlight_advisor/banding.py` — add `band_by_value`. `band_light` / `relief_recommended_bands` untouched.
- `src/mini_highlight_advisor/pipeline.py` — `plan_region`: drop `nmm_horizon`, add `env`, route NMM to `band_by_value` and bypass the relief/flat cap. `analyze_regions`: add `nmm_light_dir` / `nmm_bounce` / `nmm_hotspot`, build the env once, thread it.
- `src/mini_highlight_advisor/overlay.py` — add `nmm_env_preview` (pure disk→banded-tinted RGB image).

**Modified (UI, all `normal_field`-gated):**
- `ui/keys.py` — add env-knob + preset + metal-steps key names.
- `ui/coverage_editor.py` — `render(n, is_nmm=False)`: NMM swaps the coverage sliders for a single **"Metal steps"** number input.
- `ui/editor.py` — compute `is_nmm` from the live material widget state; pass to `coverage_editor.render`.
- `ui/results.py` — the **"Metal environment"** panel: preset selectbox, four knobs, and the **env-disk preview**; pass the knobs into `analyze_regions`.

**Rewritten tests:**
- `tests/test_materials_nmm.py` — env + new `nmm_light` model.
- `tests/test_pipeline_nmm.py` — `env=` param, value-banding, regression lock.
- `tests/test_banding.py` — add `band_by_value` anti-stripe proof (appended; existing tests kept).
- `tests/test_ui_nmm.py` — extend for the Metal-environment panel, env preview, Metal-steps swap.

**New test:**
- `tests/test_overlay_nmm_env.py` — `nmm_env_preview` pure test.

---

## Task 1: `materials.build_nmm_env` + presets

**Files:**
- Modify: `src/mini_highlight_advisor/materials.py`
- Test: `tests/test_materials_nmm.py` (new tests appended; the old `nmm_light` tests are replaced in Task 2)

**Interfaces:**
- Produces:
  - `build_nmm_env(size: int = 256, *, horizon: float = 0.5, light_dir: float = 135.0, bounce: float = 0.35, hotspot: float = 0.5) -> np.ndarray` — `(size, size)` float32 in `[0,1]`; off-disk (`u²+v² > 1`) = 0.0.
  - `NMM_PRESETS: dict[str, dict]` — `{"Steel": {...}, "Gold": {...}, "Chrome": {...}}`, each a dict of the four knob values.
- Consumes: existing module-level `_smoothstep(a, b, x)`.

**Disk coordinate convention (encode exactly):** for a `size×size` array, `u = col/(size-1)*2 - 1` (x-right), `v = 1 - row/(size-1)*2` (y-up: **row 0 → v=+1 sky**, last row → v=−1 ground). Horizon line height `v_h = 1.0 - 2.0*horizon` (raising `horizon` **lowers** `v_h`, moving the dark horizon band **down** the disk). Light point `p_L = (r_L*cos(θ), r_L*sin(θ))` in `(u,v)` with `θ = radians(light_dir)`, `r_L = 0.6` (fixed sky elevation): `light_dir=90 → (0, 0.6)` top; `light_dir=135 → (−0.42, 0.42)` upper-left.

- [ ] **Step 1: Write failing tests for the vertical profile (non-monotone) + hard horizon**

Append to `tests/test_materials_nmm.py`:

```python
from mini_highlight_advisor.materials import build_nmm_env, NMM_PRESETS


def _disk_col(env):
    """Center column of the disk, top->bottom (sky->ground)."""
    size = env.shape[0]
    return env[:, size // 2]


def test_env_vertical_profile_is_non_monotone():
    # sky (top) bright, horizon row darkest, ground bounce (bottom rim) brighter
    # than the ground band just above it. A monotone v1 curve could not pass this.
    env = build_nmm_env(size=201, horizon=0.5)          # v_h = 0 -> horizon at center row
    col = _disk_col(env)
    size = env.shape[0]
    sky = col[size // 6]                 # high up = sky
    horizon = col[size // 2]             # center row = horizon line
    ground = col[int(size * 0.72)]       # below horizon = ground
    bottom_rim = col[size - 3]           # near bottom rim = ground bounce
    assert sky > horizon
    assert horizon <= ground             # horizon is the darkest zone
    assert bottom_rim > ground           # bounce lifts the rim above the ground band


def test_env_hard_horizon_is_crisp():
    env = build_nmm_env(size=201, horizon=0.5)
    col = _disk_col(env)
    size = env.shape[0]
    just_above = col[size // 2 - int(size * 0.10)]
    horizon = col[size // 2]
    assert just_above - horizon > 0.25   # sharp dark break, not a soft ramp
```

- [ ] **Step 2: Run to verify they fail**

Run: `.venv/Scripts/python -m pytest tests/test_materials_nmm.py -k "vertical_profile or hard_horizon" -v`
Expected: FAIL — `ImportError: cannot import name 'build_nmm_env'`.

- [ ] **Step 3: Implement `build_nmm_env` (vertical profile + horizon first)**

Add to `materials.py` (below `_smoothstep`, replacing the `_CONTRAST` block — see Task 2 for the deletion; for now add alongside):

```python
def _disk_coords(size: int):
    yy, xx = np.mgrid[0:size, 0:size].astype(np.float32)
    u = xx / (size - 1) * 2.0 - 1.0            # x-right
    v = 1.0 - yy / (size - 1) * 2.0            # y-up: row 0 -> v=+1 (sky)
    return u, v


def _vert_profile(v: np.ndarray, v_h: float, bounce: float) -> np.ndarray:
    """Non-monotone sky->horizon->ground->bounce curve down the disk."""
    sky_level, ground_level = 0.9, 0.20
    above = _smoothstep(v_h, v_h + 0.25, v)                 # 0 below horizon, 1 in sky
    base = ground_level + (sky_level - ground_level) * above
    notch = np.exp(-((v - v_h) / 0.06) ** 2).astype(np.float32)   # dark horizon line
    rim = 1.0 - _smoothstep(-1.0, -0.6, v)                  # 1 at bottom rim, 0 above
    return (base * (1.0 - notch) + bounce * rim * (1.0 - above)).astype(np.float32)


NMM_PRESETS = {
    "Steel":  dict(horizon=0.50, light_dir=135.0, bounce=0.30, hotspot=0.50),
    "Gold":   dict(horizon=0.55, light_dir=120.0, bounce=0.45, hotspot=0.45),
    "Chrome": dict(horizon=0.50, light_dir=135.0, bounce=0.20, hotspot=0.80),
}


def build_nmm_env(size: int = 256, *, horizon: float = 0.5, light_dir: float = 135.0,
                  bounce: float = 0.35, hotspot: float = 0.5) -> np.ndarray:
    """Procedural NMM environment disk, (size, size) float32 in [0,1].

    Disk coords u=x-right, v=y-up over the unit circle (same pinned convention as
    surface.py / relight.py). Off-disk pixels are 0 and never sampled by nmm_light
    (grazing rays clamp to the rim). Four terms: a non-monotone vertical profile
    (hard horizon + ground bounce), a broad directional streak, and a tight glint.
    """
    size = max(16, int(size))
    horizon = float(np.clip(horizon, 0.0, 1.0))
    bounce = float(np.clip(bounce, 0.0, 1.0))
    hotspot = float(np.clip(hotspot, 0.0, 1.0))
    u, v = _disk_coords(size)
    disk = (u * u + v * v) <= 1.0
    v_h = 1.0 - 2.0 * horizon

    E = _vert_profile(v, v_h, bounce)

    theta = np.radians(float(light_dir))
    r_L = 0.6
    pu, pv = r_L * np.cos(theta), r_L * np.sin(theta)
    d2 = (u - pu) ** 2 + (v - pv) ** 2
    streak = 0.35 * np.exp(-d2 / (2.0 * 0.5 ** 2)).astype(np.float32)
    E = np.clip(E + streak, 0.0, 1.0)

    sigma_hot = 0.22 * (1.0 - hotspot) + 0.03           # bigger hotspot -> tighter
    glint = np.exp(-d2 / (2.0 * sigma_hot ** 2)).astype(np.float32)
    E = np.maximum(E, glint)

    E[~disk] = 0.0
    return E.astype(np.float32)
```

- [ ] **Step 4: Run to verify vertical/horizon tests pass**

Run: `.venv/Scripts/python -m pytest tests/test_materials_nmm.py -k "vertical_profile or hard_horizon" -v`
Expected: PASS.

- [ ] **Step 5: Write failing tests for streak/hotspot azimuth + knob monotonicity**

Append to `tests/test_materials_nmm.py`:

```python
def _argmax_uv(env):
    size = env.shape[0]
    r, c = np.unravel_index(int(np.argmax(env)), env.shape)
    u = c / (size - 1) * 2 - 1
    v = 1 - r / (size - 1) * 2
    return u, v


def test_env_brightest_pixel_sits_at_light_dir():
    u, v = _argmax_uv(build_nmm_env(size=201, light_dir=135.0))
    assert u < -0.1 and v > 0.1          # upper-left glint


def test_env_rotating_light_180_moves_glint_opposite():
    u0, v0 = _argmax_uv(build_nmm_env(size=201, light_dir=135.0))
    u1, v1 = _argmax_uv(build_nmm_env(size=201, light_dir=315.0))
    assert np.sign(u1) == -np.sign(u0) and np.sign(v1) == -np.sign(v0)


def test_env_raising_horizon_moves_dark_band_down():
    def dark_row(h):
        env = build_nmm_env(size=201, horizon=h)
        col = env[:, 100]
        disk_rows = np.where(col > 0)[0]     # ignore off-disk zeros at the poles
        return disk_rows[np.argmin(col[disk_rows])]
    assert dark_row(0.7) > dark_row(0.3)     # higher horizon -> darkest row lower down


def test_env_raising_hotspot_concentrates_peak():
    def peak_area(hs):
        env = build_nmm_env(size=201, hotspot=hs)
        return int((env > 0.95).sum())
    assert peak_area(0.9) < peak_area(0.2)   # tighter glint = fewer near-white px


def test_env_presets_are_valid_disks():
    for knobs in NMM_PRESETS.values():
        env = build_nmm_env(size=64, **knobs)
        assert env.shape == (64, 64) and env.dtype == np.float32
        assert np.all(np.isfinite(env)) and env.min() >= 0.0 and env.max() <= 1.0


def test_env_clamps_out_of_range_knobs_without_crash():
    env = build_nmm_env(size=32, horizon=5.0, bounce=-2.0, hotspot=9.0)
    assert np.all(np.isfinite(env)) and env.max() <= 1.0
```

- [ ] **Step 6: Run to verify — implementation already covers these**

Run: `.venv/Scripts/python -m pytest tests/test_materials_nmm.py -k "light_dir or glint or horizon_moves or hotspot or presets or clamps" -v`
Expected: PASS. If `test_env_raising_horizon_moves_dark_band_down` or the glint tests fail, adjust `_vert_profile` constants (`0.06` notch width, `0.25` sky slope) / `sigma_hot` — do **not** touch the test assertions; they encode the spec's structural guarantees.

- [ ] **Step 7: Commit**

```bash
git add src/mini_highlight_advisor/materials.py tests/test_materials_nmm.py
git commit -m "feat(materials): procedural NMM environment disk (build_nmm_env) + presets"
```

---

## Task 2: rewrite `materials.nmm_light` to sample the env

**Files:**
- Modify: `src/mini_highlight_advisor/materials.py` (rewrite `nmm_light`; **delete `_CONTRAST`** and the old blend; add `_bilinear`)
- Test: `tests/test_materials_nmm.py` (replace the old `nmm_light` tests)

**Interfaces:**
- Consumes: `surface.reflect(view, normals)`, `build_nmm_env` (Task 1).
- Produces: `nmm_light(normals: np.ndarray, mask: np.ndarray, *, view=(0.0, 0.0, 1.0), env: np.ndarray) -> np.ndarray` — `(H,W)` float32 in `[0,1]`; off-mask 0. **`env` is a required keyword-only arg.** `horizon` / `softness` are gone.

- [ ] **Step 1: Delete the old model and its now-broken tests**

In `materials.py`, delete the `_CONTRAST = 0.7` constant and its comment block, and the entire old `nmm_light` body (lines that blend `contrast` + `ramp`). In `tests/test_materials_nmm.py`, **delete** the six original tests that call `nmm_light(n, m, horizon=...)` (`test_nmm_light_is_float32_and_bounded`, `test_flat_front_facing_has_no_horizon`, `test_dome_is_bright_top_dark_bottom`, `test_higher_horizon_is_darker_overall`, `test_off_mask_is_zero`, `test_degenerate_all_zero_normals_is_flat_not_crash`, `test_nmm_light_is_not_near_binary`, `test_nmm_light_is_strictly_monotonic_in_reflection`). Keep the `_flat`, `_dome`, `_blob_with_detail` fixtures — they are reused. Keep all Task-1 env tests.

- [ ] **Step 2: Write the new failing `nmm_light` tests**

Append to `tests/test_materials_nmm.py`:

```python
def test_nmm_light_float32_bounded_and_off_mask_zero():
    n, m = _dome()
    m2 = m.copy(); m2[:5, :] = False
    env = build_nmm_env(size=128)
    out = materials.nmm_light(n, m2, env=env)
    assert out.dtype == np.float32
    assert out[m2].min() >= 0.0 and out[m2].max() <= 1.0
    assert np.all(out[~m2] == 0.0)


def test_nmm_light_is_light_independent():
    # nmm_light takes only normals + env; there is no diffuse-light arg to vary.
    # The core value claim: identical output regardless of any relight the caller did.
    n, m = _dome()
    env = build_nmm_env(size=128)
    a = materials.nmm_light(n, m, env=env)
    b = materials.nmm_light(n, m, env=env, view=(0.0, 0.0, 1.0))
    np.testing.assert_array_equal(a, b)


def test_nmm_light_flat_front_facing_is_uniform():
    # All +Z normals -> R=(0,0,1) -> every pixel samples the disk center -> uniform,
    # no spurious horizon on a flat plane.
    n, m = _flat()
    out = materials.nmm_light(n, m, env=build_nmm_env(size=128))
    assert np.allclose(out[m], out[m].flat[0], atol=1e-5)


def test_nmm_light_dome_sweeps_sky_to_ground():
    # Dome tips from up (top) to down (bottom); brightness must follow: top (sky)
    # brighter than bottom (ground).
    n, m = _dome()
    out = materials.nmm_light(n, m, env=build_nmm_env(size=128, horizon=0.5))
    col = out.shape[1] // 2
    assert out[2, col] > out[-3, col]


def test_nmm_light_degenerate_all_zero_normals_is_flat_not_crash():
    n = np.zeros((10, 10, 3), np.float32)
    m = np.ones((10, 10), bool)
    out = materials.nmm_light(n, m, env=build_nmm_env(size=64))
    assert out.shape == (10, 10) and np.all(np.isfinite(out))
    assert np.allclose(out[m], out[m].flat[0], atol=1e-5)


def test_nmm_light_grazing_rays_clamp_to_rim_no_oob():
    # Steeply side-facing normals push |R_xy| toward/над 1; must clamp, not index OOB.
    n = np.zeros((8, 8, 3), np.float32)
    n[..., 0] = 1.0                       # normals point +x -> grazing reflection
    m = np.ones((8, 8), bool)
    out = materials.nmm_light(n, m, env=build_nmm_env(size=64))
    assert np.all(np.isfinite(out))
```

- [ ] **Step 3: Run to verify they fail**

Run: `.venv/Scripts/python -m pytest tests/test_materials_nmm.py -k "nmm_light" -v`
Expected: FAIL — `TypeError` (old signature) or `NameError` after the delete.

- [ ] **Step 4: Implement the new `nmm_light` + `_bilinear`**

Add to `materials.py`:

```python
def _bilinear(img: np.ndarray, row: np.ndarray, col: np.ndarray) -> np.ndarray:
    """Bilinear sample img at fractional (row, col); indices clamped in-bounds."""
    h, w = img.shape
    r = np.clip(row, 0.0, h - 1.0)
    c = np.clip(col, 0.0, w - 1.0)
    r0 = np.floor(r).astype(np.int64); c0 = np.floor(c).astype(np.int64)
    r1 = np.minimum(r0 + 1, h - 1);    c1 = np.minimum(c0 + 1, w - 1)
    fr = (r - r0).astype(np.float32);  fc = (c - c0).astype(np.float32)
    top = img[r0, c0] * (1 - fc) + img[r0, c1] * fc
    bot = img[r1, c0] * (1 - fc) + img[r1, c1] * fc
    return (top * (1 - fr) + bot * fr).astype(np.float32)


def nmm_light(normals: np.ndarray, mask: np.ndarray, *, view=(0.0, 0.0, 1.0),
              env: np.ndarray) -> np.ndarray:
    """Reflection-environment brightness for NMM, (H,W) float32 in [0,1]; off-mask 0.

    A metal surface mirrors the virtual environment `env` (a matcap disk from
    build_nmm_env). Per pixel we take the reflection vector R = reflect(view,
    normals), read (R_x, R_y), and bilinear-sample the disk where that ray points.
    Brightness is a function of the FULL reflected direction, so azimuth (streak +
    glint) and a non-monotone vertical profile (ground bounce) all survive.

    Light-independence: this takes only `normals` + `env`, never a diffuse light
    direction. Grazing rays (R_x^2+R_y^2 > 1) clamp to the unit-circle rim; a
    degenerate all-zero normal field -> R=(0,0,-Z) -> samples the disk center ->
    flat map (never a crash, never mud). Off-mask -> 0.
    """
    m = mask.astype(bool)
    r = reflect(np.asarray(view, np.float32), normals)   # validates + renormalizes
    rx = r[..., 0].astype(np.float32)
    ry = r[..., 1].astype(np.float32)
    rad = np.sqrt(rx * rx + ry * ry)
    scale = np.where(rad > 1.0, 1.0 / np.maximum(rad, 1e-9), 1.0).astype(np.float32)
    u = rx * scale
    v = ry * scale
    size = env.shape[0]
    col = (u * 0.5 + 0.5) * (size - 1)
    row = (0.5 - v * 0.5) * (size - 1)          # v=+1 -> row 0 (sky/top)
    light = _bilinear(env, row, col)
    light[~m] = 0.0
    return light.astype(np.float32)
```

- [ ] **Step 5: Run the new tests + full materials suite**

Run: `.venv/Scripts/python -m pytest tests/test_materials_nmm.py -v`
Expected: PASS (Task-1 env tests + new `nmm_light` tests). No references to the deleted `_CONTRAST`.

- [ ] **Step 6: Commit**

```bash
git add src/mini_highlight_advisor/materials.py tests/test_materials_nmm.py
git commit -m "feat(materials): nmm_light samples env matcap; delete _CONTRAST monotonicity hack"
```

---

## Task 3: `banding.band_by_value`

**Files:**
- Modify: `src/mini_highlight_advisor/banding.py`
- Test: `tests/test_banding.py` (append; existing `band_light` tests untouched)

**Interfaces:**
- Produces: `band_by_value(light: np.ndarray, mask: np.ndarray, n_bands: int) -> np.ndarray` — int32, off-mask −1, `0` dark … `n_bands−1` light. Cuts the in-mask robust value span into equal-width intervals; assigns by `np.digitize` on **value** (no rank, no raster tie-break).

- [ ] **Step 1: Write the failing anti-stripe tests**

Append to `tests/test_banding.py`:

```python
from mini_highlight_advisor.banding import band_by_value


def test_band_by_value_flat_plateau_collapses_to_one_band():
    # Large flat plateau + a thin dark line. Value banding: plateau -> ONE band,
    # thin line keeps its OWN band regardless of its tiny area.
    light = np.full((20, 20), 0.8, np.float32)
    light[10, :] = 0.05                      # one thin dark row
    mask = np.ones((20, 20), bool)
    bands = band_by_value(light, mask, n_bands=5)
    plateau_bands = np.unique(bands[light == 0.8])
    assert plateau_bands.size == 1           # flat sky -> one paint
    assert bands[10, 0] != plateau_bands[0]  # thin line is a different (darker) band
    assert bands[10, 0] < plateau_bands[0]


def test_band_by_value_contrast_with_rank_banding():
    # Documents WHY value banding exists: rank banding splits the same flat plateau
    # across multiple bands; value banding does not.
    light = np.full((20, 20), 0.8, np.float32)
    light[10, :] = 0.05
    mask = np.ones((20, 20), bool)
    from mini_highlight_advisor.banding import band_light
    rank = band_light(light, mask, [0.2, 0.2, 0.2, 0.2, 0.2])
    val = band_by_value(light, mask, 5)
    assert np.unique(rank[light == 0.8]).size > 1    # rank stripes the plateau
    assert np.unique(val[light == 0.8]).size == 1    # value keeps it whole


def test_band_by_value_no_raster_order_dependence():
    # Shuffling equal-valued pixel positions changes no band assignment.
    rng_vals = np.linspace(0.0, 1.0, 400, dtype=np.float32).reshape(20, 20)
    mask = np.ones((20, 20), bool)
    a = band_by_value(rng_vals, mask, 5)
    b = band_by_value(rng_vals[::-1, ::-1], mask, 5)[::-1, ::-1]
    np.testing.assert_array_equal(a, b)


def test_band_by_value_empty_mask_all_minus_one():
    light = np.zeros((5, 5), np.float32)
    bands = band_by_value(light, np.zeros((5, 5), bool), 5)
    assert np.all(bands == -1)


def test_band_by_value_constant_field_single_band():
    light = np.full((5, 5), 0.5, np.float32)
    bands = band_by_value(light, np.ones((5, 5), bool), 5)
    assert set(np.unique(bands).tolist()) == {0}
```

- [ ] **Step 2: Run to verify they fail**

Run: `.venv/Scripts/python -m pytest tests/test_banding.py -k band_by_value -v`
Expected: FAIL — `ImportError: cannot import name 'band_by_value'`.

- [ ] **Step 3: Implement `band_by_value`**

Add to `banding.py`:

```python
def band_by_value(light: np.ndarray, mask: np.ndarray, n_bands: int) -> np.ndarray:
    """Bands by VALUE interval (not rank). -1 off-mask, 0 dark .. n_bands-1 light.

    Cuts the in-mask robust value span [p2, p98] into n_bands equal-width intervals
    and assigns each pixel by np.digitize on its VALUE. Flat zones collapse to one
    band; a thin feature keeps its own band regardless of area; there is no rank
    ordering, so no raster-order tie-break. Empty mask -> all -1; a constant field
    -> a single occupied band (band 0).
    """
    m = mask.astype(bool)
    bands = np.full(light.shape, -1, dtype=np.int32)
    vals = light[m]
    if vals.size == 0:
        return bands
    lo, hi = np.percentile(vals, [2, 98])
    if hi <= lo:
        bands[m] = 0
        return bands
    edges = lo + (hi - lo) * np.arange(1, n_bands, dtype=np.float64) / n_bands
    b = np.clip(np.digitize(vals, edges), 0, n_bands - 1).astype(np.int32)
    bands[m] = b
    return bands
```

- [ ] **Step 4: Run to verify pass + no `band_light` regression**

Run: `.venv/Scripts/python -m pytest tests/test_banding.py -v`
Expected: PASS (new `band_by_value` tests + all existing `band_light` tests).

- [ ] **Step 5: Commit**

```bash
git add src/mini_highlight_advisor/banding.py tests/test_banding.py
git commit -m "feat(banding): band_by_value — value-interval banding for NMM flat zones"
```

---

## Task 4: `pipeline` — env param, NMM banding branch, build-env-once

**Files:**
- Modify: `src/mini_highlight_advisor/pipeline.py`
- Test: `tests/test_pipeline_nmm.py` (rewrite the NMM calls to the new signature; add the regression + value-banding assertions)

**Interfaces:**
- Consumes: `materials.build_nmm_env`, `materials.nmm_light(..., env=)` (Tasks 1–2), `banding.band_by_value` (Task 3).
- Produces (changed signatures):
  - `plan_region(rgb, sub_mask, light, name, palette, coverage, *, edges=True, extreme_edge=False, edge_sensitivity=0.5, relief_cap=False, flat_albedo=False, normals=None, shades=False, material="matte", env=None) -> RegionPlan` — **`nmm_horizon` removed, `env` added.** (Keep the existing positional/keyword arg order; only swap `nmm_horizon` → `env`.)
  - `analyze_regions(..., nmm_horizon=0.5, nmm_light_dir=135.0, nmm_bounce=0.35, nmm_hotspot=0.5, whole_material="matte") -> MultiRegionResult` — builds the env once, threads it.

- [ ] **Step 1: Update imports and `plan_region`**

In `pipeline.py`:

Change the banding import:
```python
from .banding import band_light, band_by_value, relief_recommended_bands
```

Replace the head of `plan_region` (the signature line ending `material: str = "matte", nmm_horizon: float = 0.5)` and the NMM light-swap block) with:

```python
def plan_region(rgb, sub_mask, light, name, palette, coverage,
                edges: bool = True, extreme_edge: bool = False,
                edge_sensitivity: float = 0.5,
                relief_cap: bool = False, flat_albedo: bool = False,
                normals: np.ndarray | None = None,
                shades: bool = False,
                material: str = "matte",
                env: np.ndarray | None = None) -> RegionPlan:
    is_nmm = material == "nmm" and normals is not None and env is not None
    if is_nmm:
        # Metal is a mirror: re-band from the reflection environment, not the
        # caught/relit light. Geometry places the NMM horizon. normals/env absent
        # -> silently stay matte (defense in depth).
        light = materials.nmm_light(normals, sub_mask, env=env)
    requested_bands = len(palette)
    capped = False
    if not is_nmm:
        if flat_albedo:
            # Dark/low-dynamic-range region: no relief signal. Keep the base only.
            capped = True
            palette = palette[:1]
            coverage = default_coverage(1)
        elif relief_cap:
            k = relief_recommended_bands(light, sub_mask, requested_bands)
            if k < requested_bands:
                capped = True
                palette = palette[:k]
                coverage = default_coverage(k)
    colors = [p.rgb for p in palette]
    names = [p.name for p in palette]
    roles = role_names(len(palette))
    if is_nmm:
        # Value-anchored banding: flat sky -> one paint, thin horizon keeps its band.
        # The relief/flat cap is bypassed above — the env injects deliberate contrast.
        bands = band_by_value(light, sub_mask, n_bands=len(coverage))
    else:
        bands = band_light(light, sub_mask, coverage)
    cov = coverage_pct(bands, sub_mask, len(palette))
```

Leave the rest of `plan_region` (steps, edges, shades, `return RegionPlan(...)`) exactly as-is. **Note:** the geometric edge overlays and recess shades below still run for NMM regions unchanged — they are independent of the light source (spec: "the blade's edge ride-along … runs on these bands unchanged").

- [ ] **Step 2: Update `analyze_regions` to build the env once and thread it**

In `analyze_regions`, change the signature to add the three knobs (keep `nmm_horizon`):

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
                    nmm_light_dir: float = 135.0,
                    nmm_bounce: float = 0.35,
                    nmm_hotspot: float = 0.5,
                    whole_material: str = "matte") -> MultiRegionResult:
```

Replace the `ekw = dict(...)` construction (the block that currently passes `nmm_horizon=nmm_horizon`) with a build-env-once + `env=` thread:

```python
    env = materials.build_nmm_env(horizon=nmm_horizon, light_dir=nmm_light_dir,
                                  bounce=nmm_bounce, hotspot=nmm_hotspot)
    ekw = dict(edges=edges, extreme_edge=extreme_edge, edge_sensitivity=edge_sensitivity,
               relief_cap=relief_cap, normals=normal_field, shades=shades, env=env)
```

(The env is built unconditionally — it is cheap and deterministic, and unused on the matte path, which preserves the byte-identical regression lock.)

- [ ] **Step 3: Rewrite the NMM pipeline tests to the new signature**

In `tests/test_pipeline_nmm.py`: add `from mini_highlight_advisor.materials import build_nmm_env` and a module-level `ENV = build_nmm_env(size=128)`. Replace every `plan_region(..., material="nmm", nmm_horizon=...)` / `material="nmm")` call to pass `env=ENV`, and drop `nmm_horizon=`. Concretely, rewrite the bodies:

```python
def test_nmm_bands_follow_surface_detail_not_raster_rows():
    n, mask = _blob_with_detail()
    rgb = np.full((*mask.shape, 3), 120, np.uint8)
    plan = plan_region(rgb, mask, _uniform_light(mask), "x", PAL, COV,
                       edges=False, normals=n, material="nmm", env=ENV)
    bands = plan.bands
    occupied = [np.unique(bands[row][mask[row]]) for row in range(bands.shape[0])]
    occupied = [u for u in occupied if u.size]
    multi = sum(u.size >= 2 for u in occupied)
    assert multi / max(len(occupied), 1) > 0.5


def test_matte_region_bands_from_passed_light():
    n, mask = _dome()
    rgb = np.full((*mask.shape, 3), 120, np.uint8)
    light = _uniform_light(mask)
    plan_default = plan_region(rgb, mask, light, "x", PAL, COV, edges=False, normals=n)
    plan_matte = plan_region(rgb, mask, light, "x", PAL, COV,
                             edges=False, normals=n, material="matte", env=ENV)
    np.testing.assert_array_equal(plan_matte.bands, plan_default.bands)


def test_nmm_region_rebands_from_geometry():
    n, mask = _dome()
    rgb = np.full((*mask.shape, 3), 120, np.uint8)
    light = _uniform_light(mask)
    plan = plan_region(rgb, mask, light, "x", PAL, COV,
                       edges=False, normals=n, material="nmm", env=ENV)
    assert len(np.unique(plan.bands[mask])) > 1
    plan_matte = plan_region(rgb, mask, light, "x", PAL, COV,
                             edges=False, normals=n, material="matte", env=ENV)
    assert not np.array_equal(plan.bands[mask], plan_matte.bands[mask])


def test_nmm_is_light_independent():
    n, mask = _dome()
    rgb = np.full((*mask.shape, 3), 120, np.uint8)
    a = plan_region(rgb, mask, _uniform_light(mask, 0.2), "x", PAL, COV,
                    edges=False, normals=n, material="nmm", env=ENV)
    b = plan_region(rgb, mask, _uniform_light(mask, 0.9), "x", PAL, COV,
                    edges=False, normals=n, material="nmm", env=ENV)
    np.testing.assert_array_equal(a.bands, b.bands)


def test_nmm_without_normals_falls_back_to_matte():
    n, mask = _dome()
    rgb = np.full((*mask.shape, 3), 120, np.uint8)
    light = _uniform_light(mask)
    plan_matte = plan_region(rgb, mask, light, "x", PAL, COV,
                             edges=False, normals=None, material="matte", env=ENV)
    plan_nmm = plan_region(rgb, mask, light, "x", PAL, COV,
                           edges=False, normals=None, material="nmm", env=ENV)
    np.testing.assert_array_equal(plan_nmm.bands, plan_matte.bands)
```

Add a new regression + knob-threading test:

```python
def test_nmm_knobs_thread_through_analyze_regions():
    from mini_highlight_advisor.pipeline import analyze_regions
    n, dome = _dome()
    rgb = np.full((*dome.shape, 3), 120, np.uint8)
    alpha = np.full(dome.shape, 255, np.uint8)
    light = _uniform_light(dome)
    blade = Region("Blade", dome, PAL, COV, material="nmm")
    lo = analyze_regions(rgb, alpha, PAL, COV, [blade], edges=False,
                         light_field=light, normal_field=n, whole_material="matte",
                         nmm_horizon=0.2)
    hi = analyze_regions(rgb, alpha, PAL, COV, [blade], edges=False,
                         light_field=light, normal_field=n, whole_material="matte",
                         nmm_horizon=0.8)
    lo_bands = next(p for p in lo.plans if p.name == "Blade").bands
    hi_bands = next(p for p in hi.plans if p.name == "Blade").bands
    assert not np.array_equal(lo_bands, hi_bands)   # horizon knob changes the plan
```

Keep `test_analyze_regions_per_region_material_isolation` but confirm it still passes (it calls `analyze_regions`, which now builds env internally — no signature change needed at that call site).

- [ ] **Step 4: Run the pipeline NMM suite**

Run: `.venv/Scripts/python -m pytest tests/test_pipeline_nmm.py -v`
Expected: PASS.

- [ ] **Step 5: Run the FULL regression suite (byte-identical lock)**

Run: `.venv/Scripts/python -m pytest tests/ -q`
Expected: PASS. Pay special attention to `test_pipeline.py`, `test_pipeline_light_field.py`, `test_pipeline_normal_field.py`, `test_relief_cap_pipeline.py`, `test_pipeline_shades.py` — none call `nmm_horizon` on `plan_region`, so they must still pass unchanged (matte path untouched). If any test calls `plan_region(..., nmm_horizon=...)` directly, it will now `TypeError` — grep and fix those to drop `nmm_horizon` (they are matte and don't need `env`).

- [ ] **Step 6: Commit**

```bash
git add src/mini_highlight_advisor/pipeline.py tests/test_pipeline_nmm.py
git commit -m "feat(pipeline): thread NMM env + value banding; bypass relief cap for NMM"
```

---

## Task 5: `overlay.nmm_env_preview` — the env-disk legend

**Files:**
- Modify: `src/mini_highlight_advisor/overlay.py` (add one function)
- Test: `tests/test_overlay_nmm_env.py` (new)

**Interfaces:**
- Consumes: `banding.band_by_value` (Task 3).
- Produces: `nmm_env_preview(env: np.ndarray, colors: list[np.ndarray], n_bands: int, *, bg=(30, 30, 30)) -> np.ndarray` — `(size, size, 3)` uint8. Off-disk = `bg`; each in-disk value band `b` tinted with `colors[min(b, len(colors)-1)]` (0..255 RGB). Band 0 (darkest) → `colors[0]` … top band → `colors[-1]`.

- [ ] **Step 1: Write the failing test**

Create `tests/test_overlay_nmm_env.py`:

```python
import numpy as np

from mini_highlight_advisor.materials import build_nmm_env
from mini_highlight_advisor.overlay import nmm_env_preview

COLORS = [np.array(c, np.float32) for c in
          ([20, 20, 20], [80, 80, 80], [140, 140, 140], [200, 200, 200], [245, 245, 245])]


def test_env_preview_shape_and_bg():
    env = build_nmm_env(size=64)
    img = nmm_env_preview(env, COLORS, n_bands=5)
    assert img.shape == (64, 64, 3) and img.dtype == np.uint8
    # corners are outside the unit disk -> background colour
    assert tuple(img[0, 0]) == (30, 30, 30)


def test_env_preview_tints_bands_with_palette():
    env = build_nmm_env(size=64)
    img = nmm_env_preview(env, COLORS, n_bands=5)
    # every in-disk pixel is one of the palette colours (not the bg)
    palette_set = {tuple(c.astype(np.uint8)) for c in COLORS}
    size = 64
    yy, xx = np.mgrid[0:size, 0:size]
    u = xx / (size - 1) * 2 - 1
    v = 1 - yy / (size - 1) * 2
    disk = (u * u + v * v) <= 1.0
    disk_pixels = {tuple(px) for px in img[disk]}
    assert disk_pixels.issubset(palette_set)


def test_env_preview_fewer_colors_than_bands_clamps():
    # n_bands > len(colors): top bands clamp to the lightest paint, no index error.
    env = build_nmm_env(size=48)
    img = nmm_env_preview(env, COLORS[:3], n_bands=5)
    assert img.shape == (48, 48, 3) and np.all(np.isfinite(img))
```

- [ ] **Step 2: Run to verify it fails**

Run: `.venv/Scripts/python -m pytest tests/test_overlay_nmm_env.py -v`
Expected: FAIL — `ImportError: cannot import name 'nmm_env_preview'`.

- [ ] **Step 3: Implement `nmm_env_preview`**

Add to `overlay.py` (import `band_by_value` at the top: `from .banding import band_by_value`, or import locally inside the function to avoid touching the header — match the file's existing import style):

```python
def nmm_env_preview(env, colors, n_bands, *, bg=(30, 30, 30)):
    """RGB uint8 preview of the NMM environment disk, value-banded and tinted with
    the region's paints: a legend for 'where each colour goes'. Off-disk = bg;
    band 0 (darkest) -> colors[0] ... top band -> colors[-1]. Reuses the Pillar-2
    band_by_value thresholds, so the preview matches the actual plan cuts."""
    size = env.shape[0]
    yy, xx = np.mgrid[0:size, 0:size].astype(np.float32)
    u = xx / (size - 1) * 2.0 - 1.0
    v = 1.0 - yy / (size - 1) * 2.0
    disk = (u * u + v * v) <= 1.0
    bands = band_by_value(env, disk, n_bands)
    out = np.empty((size, size, 3), np.uint8)
    out[:] = np.array(bg, np.uint8)
    k = len(colors)
    for b in range(n_bands):
        col = np.clip(colors[min(b, k - 1)], 0, 255).astype(np.uint8)
        out[bands == b] = col
    return out
```

- [ ] **Step 4: Run to verify pass**

Run: `.venv/Scripts/python -m pytest tests/test_overlay_nmm_env.py -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add src/mini_highlight_advisor/overlay.py tests/test_overlay_nmm_env.py
git commit -m "feat(overlay): nmm_env_preview — value-banded, palette-tinted env disk legend"
```

---

## Task 6: UI — Metal-steps input, Metal-environment panel, env-disk preview

**Files:**
- Modify: `ui/keys.py`, `ui/coverage_editor.py`, `ui/editor.py`, `ui/results.py`
- Test: `tests/test_ui_nmm.py` (extend)

**Interfaces:**
- Consumes: `materials.NMM_PRESETS`, `materials.build_nmm_env`, `overlay.nmm_env_preview`, `analyze_regions(..., nmm_light_dir=, nmm_bounce=, nmm_hotspot=)` (Tasks 1–5), `palette.default_coverage`.
- Produces: no new public function signatures outside the UI package; `coverage_editor.render` gains an `is_nmm` flag.

- [ ] **Step 1: Add key names**

In `ui/keys.py`, below `NMM_HORIZON`:

```python
NMM_LIGHT_DIR = "nmm_light_dir"  # global NMM light-direction slider (deg, PS mode)
NMM_BOUNCE = "nmm_bounce"        # global NMM ground-bounce slider (PS mode)
NMM_HOTSPOT = "nmm_hotspot"      # global NMM specular-hotspot slider (PS mode)
NMM_PRESET = "nmm_preset"        # Metal-environment preset selectbox
```

And add a per-index builder next to `def material(i)`:

```python
def metal_steps(i: int) -> str: return f"metal_steps_{i}"
```

- [ ] **Step 2: NMM branch in `coverage_editor.render` (write the failing UI test first)**

Extend `tests/test_ui_nmm.py` — replace the `HARNESS_PS` block's inline `book = new_book(5)` flow is fine; add a test that selecting NMM shows a "Metal steps" input and hides the coverage sliders. Because `results.render` owns the material selectbox but `coverage_editor` runs earlier in `editor.render_editor`, the two must be driven through the real editor. Add a new harness that mounts `editor.render_editor`:

```python
HARNESS_EDITOR_PS = """
import numpy as np
from pathlib import Path
from PIL import Image
import streamlit as st
from mini_highlight_advisor import relight
from mini_highlight_advisor.region_state import new_book
from ui import editor, keys

FIX = Path("tests/fixtures/ps")
normals = relight.load_normals(str(FIX / "synth_normal.png"))
mask = np.asarray(Image.open(FIX / "synth_mask.png").convert("L")) > 127
lf, relit = relight.relight(normals, mask, relight.light_dir(225, 45))
mask_u8 = (mask * 255).astype(np.uint8)
book = new_book(5)
st.session_state[keys.BOOK] = book
sh = type('S', (), {'mask': mask})()
editor.render_editor(relit, mask_u8, sh, book, [], [],
                     light_field=lf, normal_field=normals)
st.write("ok")
"""


def test_selecting_nmm_swaps_coverage_for_metal_steps():
    at = AppTest.from_string(HARNESS_EDITOR_PS); at.run()
    assert not at.exception
    mat = next(s for s in at.selectbox if "material" in (s.label or "").lower())
    mat.set_value("NMM").run()
    assert not at.exception
    number_labels = [(ni.label or "").lower() for ni in at.number_input]
    assert any("metal steps" in l for l in number_labels)
    # coverage role sliders (e.g. "Shadow"/"Base") are gone for the NMM region
    slider_labels = [(s.label or "").lower() for s in at.slider]
    assert not any(l in ("shadow", "base", "midtone", "highlight") for l in slider_labels)
```

Run: `.venv/Scripts/python -m pytest tests/test_ui_nmm.py -k metal_steps -v`
Expected: FAIL (no "Metal steps" input yet).

- [ ] **Step 3: Implement the `is_nmm` swap in `coverage_editor.render`**

Rewrite `ui/coverage_editor.py`'s `render` to accept `is_nmm`:

```python
from mini_highlight_advisor.palette import (
    role_names, default_coverage, remainder_pct, slider_max_pct,
)
from ui import keys

_COV_FLOOR = 3.0


def render(n: int, is_nmm: bool = False, sel: int = 0) -> list[float]:
    if is_nmm:
        st.markdown("**Metal steps** (value bands for this NMM region)")
        steps = st.number_input(
            "Metal steps", min_value=2, max_value=n, value=min(5, n), step=1,
            key=keys.metal_steps(sel),
            help="How many brightness bands the reflected environment is cut into. "
                 "NMM has no per-band coverage — each step owns a fixed value range.")
        return default_coverage(int(steps))
    # ... existing matte slider body unchanged ...
```

Keep the rest of the matte body (the `_cap_slider`, seeding, sliders, remainder) exactly as it is today after the `if is_nmm` early return.

- [ ] **Step 4: Thread `is_nmm` from `editor.render_editor`**

In `ui/editor.py`, compute the live material from widget state and pass it down:

```python
import streamlit as st
from ui import coverage_editor, palette_editor, regions_panel, results, state, keys


def render_editor(rgb, alpha, shading, book, picked, owned_paints,
                  light_field=None, normal_field=None) -> None:
    src_h, src_w = rgb.shape[:2]
    sel = regions_panel.render(book, rgb, shading, src_w, src_h)
    state.rehydrate_editor_widgets(book, sel)

    palette, n = palette_editor.render(book, sel, picked)
    is_nmm = (normal_field is not None
              and st.session_state.get(keys.material(sel), "Matte") == "NMM")
    coverage = coverage_editor.render(n, is_nmm=is_nmm, sel=sel)
    palette_editor.render_save_recipe(palette, n)

    book.set_palette_at(sel, palette)
    book.set_coverage_at(sel, coverage)

    results.render(rgb, alpha, book, palette, picked, owned_paints, shading,
                   light_field=light_field, normal_field=normal_field)
```

Reading `st.session_state[keys.material(sel)]` (the selectbox value, set at the top of the rerun triggered by the widget change) makes the swap immediate — no one-rerun lag. On the first run (before the selectbox exists) it defaults to `"Matte"`.

Run: `.venv/Scripts/python -m pytest tests/test_ui_nmm.py -k metal_steps -v`
Expected: PASS.

- [ ] **Step 5: Metal-environment panel + env-disk preview in `results.py` (failing test first)**

Extend `tests/test_ui_nmm.py`:

```python
def test_ps_mode_shows_metal_environment_panel_and_preview():
    at = AppTest.from_string(HARNESS_PS); at.run()
    assert not at.exception
    select_labels = [(s.label or "").lower() for s in at.selectbox]
    assert any("preset" in l or "metal environment" in l for l in select_labels)
    slider_labels = [(s.label or "").lower() for s in at.slider]
    assert any("light direction" in l for l in slider_labels)


def test_selecting_preset_and_moving_knobs_replans_without_error():
    at = AppTest.from_string(HARNESS_PS); at.run()
    preset = next(s for s in at.selectbox if "preset" in (s.label or "").lower())
    preset.set_value("Gold").run()
    assert not at.exception
    assert len(at.image) > 0
```

Run: `.venv/Scripts/python -m pytest tests/test_ui_nmm.py -k "metal_environment or preset" -v`
Expected: FAIL.

- [ ] **Step 6: Implement the Metal-environment panel in `results.py`**

In `ui/results.py`, add imports at the top:

```python
from mini_highlight_advisor import materials
from mini_highlight_advisor.overlay import nmm_env_preview
```

Replace the current NMM block (the `nmm_horizon = 0.5` + single horizon slider inside `if normal_field is not None:`) with the full panel. Keep the per-region Material selectbox where it is; add the global env panel + preview after it:

```python
    nmm_horizon, nmm_light_dir, nmm_bounce, nmm_hotspot = 0.5, 135.0, 0.35, 0.5
    if normal_field is not None:
        sel = book.selected
        cur = book.material_at(sel)
        choice = st.selectbox(
            f"Material — {book.names()[sel]}", ["Matte", "NMM"],
            index=0 if cur == "matte" else 1, key=keys.material(sel),
            help="NMM re-bands this region as non-metallic metal: it reads the "
                 "reflection of a virtual environment off the surface normals. "
                 "PS mode only.")
        book.set_material_at(sel, "nmm" if choice == "NMM" else "matte")

        st.markdown("**Metal environment** (the world your metal reflects)")
        preset = st.selectbox("Preset", ["Steel", "Gold", "Chrome", "Custom"],
                              key=keys.NMM_PRESET)
        if preset != "Custom":
            knobs = materials.NMM_PRESETS[preset]
        else:
            knobs = dict(horizon=0.5, light_dir=135.0, bounce=0.35, hotspot=0.5)
        nmm_horizon = st.slider("Horizon height", 0.0, 1.0, knobs["horizon"], 0.05,
                                key=keys.NMM_HORIZON,
                                help="Where the sky/ground break sits on the reflection.")
        nmm_light_dir = st.slider("Light direction", 0.0, 360.0, knobs["light_dir"], 5.0,
                                  key=keys.NMM_LIGHT_DIR,
                                  help="Azimuth of the reflected light streak/glint "
                                       "(90=top, 135=upper-left).")
        with st.expander("Custom / advanced"):
            nmm_bounce = st.slider("Ground bounce", 0.0, 1.0, knobs["bounce"], 0.05,
                                   key=keys.NMM_BOUNCE)
            nmm_hotspot = st.slider("Hotspot", 0.0, 1.0, knobs["hotspot"], 0.05,
                                    key=keys.NMM_HOTSPOT)

        # Env-disk preview: the built env, value-banded, tinted with the selected
        # region's paints -> a legend for where each colour goes. Re-renders live.
        env = materials.build_nmm_env(horizon=nmm_horizon, light_dir=nmm_light_dir,
                                      bounce=nmm_bounce, hotspot=nmm_hotspot)
        steps = len(book.coverage_at(sel))
        preview = nmm_env_preview(env, [p.rgb for p in palette], n_bands=steps)
        st.image(preview, caption="Where each colour goes (reflected environment)",
                 width=180)
```

> **Preset→knob seeding note:** because Streamlit widgets own their value via `key=`, the `value=knobs[...]` arg only seeds on first creation. Selecting a preset changes the *displayed default* for freshly-created sliders; if a slider already has session state, its stored value persists (the user's manual tweak wins). This is acceptable v1 behaviour — the AppTest only asserts the panel renders and re-plans without error, and that `Gold` is selectable. Do **not** add a re-seed nonce unless a follow-up asks for it (YAGNI).

Then pass the knobs into the existing `analyze_regions` call — add the three new kwargs alongside `nmm_horizon`:

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
                            nmm_light_dir=nmm_light_dir,
                            nmm_bounce=nmm_bounce,
                            nmm_hotspot=nmm_hotspot,
                            whole_material=book.material_at(0))
```

Run: `.venv/Scripts/python -m pytest tests/test_ui_nmm.py -v`
Expected: PASS (existing `test_ps_mode_shows_material_selector_and_horizon`, `test_ps_mode_selecting_nmm_replans_without_error`, `test_photo_mode_hides_material_and_horizon` still pass; new panel/preset/metal-steps tests pass). If `test_photo_mode_hides_material_and_horizon` now sees a stray widget, confirm every new control is inside `if normal_field is not None:`.

- [ ] **Step 7: Full suite + manual smoke**

Run: `.venv/Scripts/python -m pytest tests/ -q`
Expected: PASS. (Two pre-existing `test_ui_gallery.py` failures are known-unrelated per project memory — confirm they are the *same* two and not new.)

Manual smoke (defer the actual run to the user per repo convention): `streamlit run app.py`, load a PS bundle (imported normal map), pick a region → **NMM**, confirm the Metal-environment panel + disk preview appear and the combined preview re-renders as the horizon/light-direction sliders move.

- [ ] **Step 8: Commit**

```bash
git add ui/keys.py ui/coverage_editor.py ui/editor.py ui/results.py tests/test_ui_nmm.py
git commit -m "feat(ui): NMM Metal-environment panel, presets, env-disk preview, Metal-steps input"
```

---

## Self-Review

**Spec coverage:**
- Pillar 1 `build_nmm_env` (4 terms: horizon, ground bounce, streak, hotspot) → **Task 1**. ✓
- Pillar 1 `nmm_light` env sampling + delete `_CONTRAST` + light-independence/degenerate/grazing → **Task 2**. ✓
- Pillar 2 `band_by_value` (value-interval, anti-stripe, empty/constant) → **Task 3**. ✓
- Pillar 2 routing in `plan_region` + relief-cap bypass + matte byte-identical + knob threading in `analyze_regions` → **Task 4**. ✓
- UI: Metal-steps swap (editor) → **Task 6 Steps 2–4**; Metal-environment panel + presets + knobs → **Task 6 Steps 5–6**; **env-disk preview** (the "piece that answers the painter pain") → `overlay.nmm_env_preview` (**Task 5**) rendered in **Task 6 Step 6**. ✓
- Error handling (knob clamp, grazing rim-clamp, all-zero flat, empty/constant band, NMM-without-normals fallback) → covered by tests in Tasks 1–4. ✓
- Testing strategy (env structural guarantees, light-independence, dome sweep, anti-stripe proof, matte regression, AppTest capability gate) → Tasks 1–6. ✓
- YAGNI non-goals (no OSL, no colored env, no 3D rotation, no per-region env, no ramp synthesis) → nothing in the plan builds them; preset→knob re-seed nonce explicitly deferred. ✓
- Persistence: env knobs are session-state only, `material` persistence unchanged → no `projects.py` change (correct; nothing added). ✓

**Placeholder scan:** No "TBD"/"handle edge cases"/"similar to Task N" — every code step has literal code and every test has literal asserts. ✓

**Type consistency:** `env: np.ndarray` flows `build_nmm_env` (Task 1) → `nmm_light(..., env=)` (Task 2) → `plan_region(env=)` / `analyze_regions` build-once (Task 4) → `nmm_env_preview(env, ...)` (Task 5) → `results.py` (Task 6). `band_by_value(light, mask, n_bands)` signature identical in Tasks 3, 4, 5. `coverage_editor.render(n, is_nmm, sel)` matches the Task-6 `editor.py` call. `keys.metal_steps(i)` / `keys.NMM_LIGHT_DIR` etc. defined in Task 6 Step 1 before use. `plan_region`'s `nmm_horizon` removed in Task 4 — Task 4 Step 5 greps for stray callers. ✓

**One risk flagged for the executor:** Task 1's `_vert_profile` constants (`0.06`, `0.25`, `sky_level=0.9`) are tuned to pass the structural tests; if a subagent tweaks `size` or a constant and a monotonicity test drifts, fix the *constant*, never the assertion.
