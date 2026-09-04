# NMM v2 — Procedural Matcap Reflection Environment — Design Spec

**Date:** 2026-09-03
**Status:** Design approved in brainstorm; awaiting spec review before planning.
**Branch:** `feat/nmm-procedural-matcap` (off `feat/nmm-metal-from-normals`).
**Classification:** Architectural. Reworks the render *model* of the parked NMM v1;
keeps its region/plan plumbing; adds a value-threshold banding path and an
environment-preview UI. Regression-locks Path L / matte byte-identical.

## Why this exists

The 9-mini PS dogfood (`2026-09-03-ps-capture-and-evaluation-protocol.md`) settled
that photometric stereo does **not** earn its friction for *value placement* —
banding is rank-based, so a single good raking frame ties the PS-relit plan every
time, even on a black-primed mini. The one job where a normal field provably beats
brightness is **imposing a light the photo does not contain**: NMM (and later OSL).
Luminance cannot tell a sky-facing bevel from a ground-facing one; the reflection
vector can. That is the sole province where PS lifts the ceiling.

The painter need driving this (user's own words): *"I don't know where to place each
of the colors to make a real NMM."* NMM is hard precisely because the painter must
mentally construct a reflected environment and decide where each value lands. A real
normal field can **derive** that placement instead of leaving it to the imagination.

### What the parked v1 got wrong

The parked `feat/nmm-metal-from-normals` v1 models the reflection environment as a
**monotone vertical gradient**: `nmm_light` maps the reflection vector's vertical
component `R_y` through a smoothstep around a `horizon`, blended
`0.7·smoothstep + 0.3·raw_ramp`. That `0.3` ramp (`_CONTRAST = 0.7`) exists **only**
to force strict monotonicity in `R_y`, because the earlier stripe bug was rank-based
banding tie-breaking a near-binary field by raster order.

That monotonicity workaround is the ceiling:

- It **softens the hard horizon** — the signature thin dark→light break is diluted by
  the ramp term.
- It makes **ground bounce impossible** — a monotone function of `R_y` cannot produce
  the sky-bright / mid-dark / base-lighter-again value curve that reads as metal.
- It carries **no azimuth** — brightness depends only on reflected *height* `R_y`, so a
  directional light streak and specular glints (which depend on reflected *direction*)
  cannot exist.

The four elements the painter wants — **hard horizon, ground bounce, directional
streak, specular hotspot** — do not fit a 1D vertical function. Two of them are
non-monotone in elevation (ground bounce) or depend on azimuth (streak, hotspot). The
model must sample the **full reflection direction**, not just its height.

### The coupled constraint: banding

The render model and the banding method are coupled. The stripes came from feeding a
near-binary field into **equal-area** banding (`band_light` cuts on pixel *rank*, so it
must split tied pixels across bands and breaks ties by raster order). But **every**
convincing NMM environment has large flat zones (a broad flat sky, a flat ground), so
equal-area banding will stripe on *any* good NMM env, and will also swallow the thin
horizon into a fixed-population band. The honest fix is **value-anchored banding** for
NMM regions — which also removes the reason the `_CONTRAST` hack existed, so it is
deleted. Fixing the render model without fixing the banding is not possible.

## Scope — reuse vs. change

Built **on the parked branch**, which already ships (built + tested): `Region.material`,
`RegionBook.whole_material` / `material_at` / `set_material_at`, the `material=` /
`nmm_horizon=` threading through `plan_region` and `analyze_regions`, and the
`normal_field`-gated NMM UI. **All of that plumbing is kept.** The rework is:

1. **Rewrite `materials.nmm_light`** into a procedural-matcap sampler; add
   `materials.build_nmm_env`. **Delete `_CONTRAST` / the monotonicity blend.**
2. **Add `banding.band_by_value`**, used only for NMM regions. Matte regions keep
   `band_light` byte-identically.
3. **Extend the UI**: four env knobs + presets, and the **environment-disk preview**.

**Out of scope (unchanged):** Path L behaviour, matte banding math, palette / collection
/ matching, region drawing, geometric edges, recess shades, persistence semantics.

**Strategic caveat (recorded, not relitigated):** this stays a **local/desktop PS-path**
feature — it will not run on the Streamlit-Cloud "share with friends" build (torch
sidecar). It targets the imported-normal-map or multi-shot path; the clean black-primed
skaven capture (neutral albedo + clean normal) is an ideal substrate.

## Pillar 1 — the procedural matcap environment

A metal surface is a mirror, so its brightness at a pixel is whatever the virtual
environment shows along the reflection ray `R`. Rather than compute a formula per pixel,
build a small **environment disk** (a "matcap" — the sphere of the reflected world) once,
then every pixel *looks up* its brightness by where its `R` points.

### `materials.py` API

```python
def build_nmm_env(size: int = 256, *, horizon: float = 0.5, light_dir: float = 135.0,
                  bounce: float = 0.35, hotspot: float = 0.5) -> np.ndarray:
    """Procedural NMM environment disk, (size, size) float32 in [0,1].

    Disk coords u=x-right, v=y-up over the unit circle (same pinned convention as
    surface.py / relight.py: R = x-right, y-up, z-toward-viewer). Pixels outside the
    unit circle are 0 and never sampled (grazing rays clamp to the rim, see nmm_light).
    """

def nmm_light(normals: np.ndarray, mask: np.ndarray, *, view=(0.0, 0.0, 1.0),
              env: np.ndarray) -> np.ndarray:
    """Reflection-environment brightness for NMM, (H,W) float32 in [0,1]; off-mask 0."""
```

### `build_nmm_env` — four terms, one per requested element

The disk value at `(u, v)` sums four contributions:

1. **Vertical profile `vert(v)`** — a **non-monotone** curve down the disk:
   bright **sky** plateau above the horizon → sharp dip to near-black at the **hard
   horizon** line (centered at `v_h = 2·horizon − 1`) → dark **ground** plateau → a rise
   back toward mid near the bottom rim = **ground bounce** (its height set by `bounce`).
   This single curve delivers *horizon* + *ground bounce*.
2. **Streak** — a broad, soft radial falloff centered on the light point `p_L`, placed on
   the disk from the `light_dir` azimuth (degrees; 90 = top, 135 = upper-left) at a fixed
   sky elevation radius. The diffuse sky-glow the metal catches. Delivers the
   *directional streak*.
3. **Hotspot** — a tight Gaussian at `p_L`; `hotspot` sets its size/intensity. The
   pinpoint glint. Delivers *specular hotspots*.
4. **Combine** — `E = clip(vert(v) + streak, 0, 1)`, then `E = max(E, hotspot)` so the
   glint always punches to white. Off-disk (`u²+v² > 1`) → 0.

Term shapes are smooth, deterministic functions of the knobs (no randomness), so the disk
is fully reproducible and directly assertable in tests. Exact curve forms (plateau widths,
falloff sigmas) are implementation detail for the plan; the spec fixes their **structural
guarantees** (the test list in this doc), not their constants.

### `nmm_light` — sample the env along R

Per pixel: `R = surface.reflect(view, normals)` (validates + renormalizes normals); take
`(R_x, R_y)`; map from `[-1, 1]` into disk pixel coordinates; **bilinear-sample** `env`.
Rays with `R_x² + R_y² > 1` (grazing) **clamp to the unit-circle rim** (no out-of-bounds).
Off-mask pixels → 0. A degenerate all-zero normal field yields `R = view = +Z` →
`(R_x, R_y) = (0,0)` → samples the disk center → a flat map (never a crash, never mud).

**Why this nails all four elements** where v1 could not: brightness is now a function of
the **full reflected direction** `(R_x, R_y)`, so azimuth returns (streak + hotspot) and
`vert(v)` is free to be non-monotone (ground bounce). The horizon is a genuine geometric
derivation — it lands on the mini wherever the surface tips so `R` crosses the horizon
line, following the sculpt. **Light-independence is preserved**: `nmm_light` takes only
`normals` + `env`, never a diffuse light direction — the core NMM value claim and a locked
test.

### Knobs and presets

Four knobs: `horizon`, `light_dir`, `bounce`, `hotspot`. Three built-in presets
(`Steel`, `Gold`, `Chrome`) are saved knob-tuples. **Colors are never invented here** —
the region's own assigned palette (or a loaded `NMM Gold` / `NMM Copper` recipe) supplies
the metal ramp; the env only *places* those colors on the reflection curve.

**YAGNI (explicit non-goals):** no 3D environment rotation, no double-horizon /
reflected-floor-plane geometry beyond the `bounce` bump, no per-region environment (one
env per render, shared by all NMM regions — matching v1's global-horizon decision), no
colored environment (brightness only; the palette carries hue).

## Pillar 2 — NMM value-anchored banding

`band_light` cuts on pixel **rank** (`np.digitize(ranks, edges)`), forcing each band to
hold a fixed fraction of pixels. That is incompatible with NMM's flat zones + thin
horizon. Add a value-threshold sibling:

```python
def band_by_value(light: np.ndarray, mask: np.ndarray, n_bands: int) -> np.ndarray:
    """Bands by VALUE interval (not rank). −1 off-mask, 0 dark … n_bands−1 light.

    Cuts the value axis over the in-mask [min, max] range into n_bands equal-width
    intervals and assigns each pixel by np.digitize on its VALUE. Flat zones collapse
    to one band; a thin feature keeps its own band regardless of area; no tie-break by
    raster order (there is no rank ordering).
    """
```

Cut range: the in-mask value span (`p_lo..p_hi`, robust percentiles to shrug off a few
outliers — exact percentiles are a plan detail), divided into `n_bands` equal-width
intervals. Consequences, all desired for NMM:

- Flat sky → identical values → **one clean band → one paint.** No ties to mis-break, no
  stripes.
- The thin hard horizon occupies its own dark value interval **regardless of area** — it
  survives as a crisp line.
- Bands map to **fixed brightness ranges**, so "band 0 = horizon shadow, top band =
  glint/sky" is stable and learnable — directly serving the where-do-colors-go goal.

### Routing in `pipeline.plan_region`

Mirrors the existing material swap; one branch:

```python
if material == "nmm" and normals is not None:
    light = materials.nmm_light(normals, sub_mask, env=env)
    bands = banding.band_by_value(light, sub_mask, n_bands=len(coverage))
else:
    bands = banding.band_light(light, sub_mask, coverage)   # unchanged, byte-identical
```

- `material == "nmm"` with `normals is None` → **matte fallback** (uses passed `light` +
  `band_light`), never a crash. Cannot arise from the UI (NMM is only offered with
  normals); the fallback keeps the pure API total.
- `material == "matte"` → the branch is skipped; **byte-identical to today**.

### Two honest consequences (named, by design)

1. **Coverage sliders do not apply to NMM regions.** Value banding has no area quota, so
   an NMM region's editor shows an **integer "Metal steps"** input (default 5) in place of
   per-band coverage sliders. `len(coverage)` still carries the step count through the
   existing signature (so plumbing is unchanged); the *UI control* differs.
2. **The relief cap is skipped for NMM.** `relief_recommended_bands` exists to avoid
   manufacturing highlights a flat sculpt cannot show, but the NMM env deliberately injects
   extreme contrast, so the cap would fight it. NMM regions bypass it (the parked spec
   already anticipated this). `flat_albedo` comes only from `per_region_norm`, always off
   in PS mode, so NMM regions are never flagged flat — no special-casing needed.

Everything downstream — per-band step images (`per_band_images`), geometric edge
highlights (the blade's edge ride-along, independent of the light source), recess shades,
combined preview (`paint_regions`), swatch board — runs on these bands unchanged.

## Integration & UI

### Threading

`analyze_regions` gains three env-knob globals alongside the existing `nmm_horizon`
(`nmm_light_dir`, `nmm_bounce`, `nmm_hotspot`), **builds the env once** up front, and
passes it into each NMM `plan_region` call:

```python
env = materials.build_nmm_env(horizon=nmm_horizon, light_dir=nmm_light_dir,
                              bounce=nmm_bounce, hotspot=nmm_hotspot)
ekw = dict(..., normals=normal_field, shades=shades, env=env)
```

`plan_region` gains `env=None` and applies Pillar 2's branch. One env per render, shared
by all NMM regions. Regression lock: when every material is `"matte"`, `env` is unused and
output is byte-identical to today.

### UI (all `normal_field`-gated; invisible in Path L / photo mode)

1. **Per-region Material selector** (`Matte | NMM`) — already on the branch
   (`ui/editor.py`). When a region is NMM, its coverage-sliders block is replaced by a
   single **"Metal steps"** integer input.
2. **Global "Metal environment" panel** (`ui/results.py`, beside the recess-shades
   toggle):
   - **Preset** selectbox: `Steel · Gold · Chrome · Custom`.
   - **Horizon height** slider and **Light direction** control (v1: an 8-way
     NW/N/NE/… selectbox mapped to degrees, or a 0–360 slider — plan picks the
     lower-churn Streamlit control). **Bounce** + **Hotspot** sliders behind a
     "Custom / advanced" expander.
3. **Environment-disk preview — the piece that answers the painter pain.** Render the
   built `env` as a small image in that panel (*"the world your metal reflects"*), then
   overlay the **value-band cuts** (the same `band_by_value` thresholds) tinted with the
   selected region's assigned paints: sky zone = the region's lightest paint, horizon line
   = its darkest, ground = mid, glint = white. The disk becomes a **legend for where each
   color goes**, and it re-renders live as the horizon / light-direction controls move.
   Cheap: it reuses the `env` array and the Pillar-2 thresholds — no new engine.

**Persistence:** NMM is session-only (v1), unchanged from the parked spec. `material`
defaults `"matte"`, so old projects load unchanged; the env knobs are session state, not
persisted.

## Error handling

- `build_nmm_env` clamps knobs to valid ranges; any knob tuple yields a valid disk
  (off-disk pixels 0). No knob combination crashes.
- `nmm_light` renormalizes normals defensively (via `surface.reflect` → `_validate`);
  grazing rays clamp to the rim; all-zero normals → flat map; off-mask → 0.
- `band_by_value` with an empty mask → all `−1` (mirrors `band_light`); a constant field →
  a single occupied band (no divide-by-zero on the value range).
- `plan_region` NMM-without-normals → matte fallback (above).

## Testing strategy

Offline, torch-free; reuse the committed synthetic fixture
(`tests/fixtures/ps/synth_normal.png` + `synth_mask.png`, dome + ridges). The parked
`test_materials_nmm.py` / `test_pipeline_nmm.py` / `test_ui_nmm.py` are **rewritten** to
the new model.

**`build_nmm_env` (pure, TDD):**
- Vertical profile is **non-monotone**: sky row brighter than horizon row; horizon row is
  the **darkest**; bottom-rim (ground bounce) brighter than the ground band above it —
  the test v1 could not pass.
- **Hard horizon**: value drop across the horizon row exceeds a crispness threshold.
- **Directional streak/hotspot**: the brightest disk pixel sits at the `light_dir`
  azimuth; rotating `light_dir` by 180° moves it to the opposite side (locks
  azimuth-awareness).
- **Knob monotonicity**: raising `horizon` moves the dark band down; raising `bounce`
  lifts the bottom rim; raising `hotspot` concentrates the peak.

**`nmm_light` (pure, TDD):**
- **Light-independence**: identical output under two different diffuse-light setups (takes
  only `normals` + `env`) — the core value claim.
- Flat front-facing normals (all `+Z`) → all sample the disk center → uniform map (no
  spurious horizon on a flat plane).
- Synthetic dome → sampled brightness sweeps sky→horizon→ground→bounce as the surface
  tips (reflection follows geometry).
- Off-mask → 0; degenerate all-zero normals → flat, no crash; grazing `|R_xy|>1` clamps to
  rim, no out-of-bounds.

**`band_by_value` (pure, TDD) — the anti-stripe proof:**
- A field with a **large flat plateau + a thin dark line** → plateau collapses to **one
  band**, thin line keeps **its own band** (area-independent). Contrast against
  `band_light` on the same field producing multiple plateau bands — documents *why* value
  banding exists.
- **No raster-order dependence**: shuffling equal-valued pixel positions changes no band
  assignment.
- Empty mask → all `−1`; constant field → single occupied band.

**`plan_region` / `analyze_regions` (TDD):**
- `material="matte"` → **byte-identical** to current output (regression lock, Path L and
  no-NMM Path P).
- `material="nmm"` with uniform input `light` but varying normals → matte gives one flat
  band, NMM gives a structured plan (proves source swap + value banding together).
- `material="nmm", normals=None` → matte fallback, no crash.
- Per-region isolation: one NMM region differs from its matte twin while sibling matte
  regions are unchanged; the four env knobs thread through and change the NMM plan.

**UI (AppTest, matching existing `ui/` tests):**
- PS mode renders the Material selector, the Metal-environment panel, and the env-disk
  preview without error; selecting NMM swaps a region's coverage sliders for the "Metal
  steps" input.
- Photo / Path-L mode renders **none** of it (capability gate).
- Smoke: a PS plan still draws with matte defaults (no regression to the existing PS flow).

## Rollout / build order (for the plan)

1. `materials.build_nmm_env` + tests (structural guarantees above) — pure, TDD, no deps.
2. Rewrite `materials.nmm_light` to sample `env`; **delete `_CONTRAST`**; retarget its
   tests (light-independence, dome sweep, degenerate/ grazing).
3. `banding.band_by_value` + tests (anti-stripe proof).
4. `pipeline`: `env=` param + the NMM banding branch in `plan_region`; build-env-once +
   knob globals in `analyze_regions`; **regression-lock matte byte-identical**.
5. UI: Metal-steps input (`editor.py`), Metal-environment panel + presets + knobs, and the
   env-disk preview (`results.py`), all `normal_field`-gated + AppTest.

Steps 1–4 deliver and prove the value against the synthetic fixture and any normal map on
disk (e.g. staircase / black-skaven captures), independent of a live capture.

## Non-goals (this slice)

- **No OSL** (colored object-source glow via `N·L` + tint) — the later sibling on the same
  foundation. NMM samples the environment via `R`; OSL casts a placed emitter via `N·L`.
- **No procedural metal-ramp synthesis** — the painter supplies the ramp or loads an NMM
  recipe; this slice only *places* colors.
- **No colored environment, no 3D env rotation, no double-horizon, no per-region env** —
  one brightness-only env per render, four knobs, shared by all NMM regions.
- **No NMM in Path L / photo mode** — capability-gated off (no normals).
- **No change** to Path L behaviour, matte banding, palette / regions-drawing UI, steps,
  or persistence semantics.
