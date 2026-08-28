# NMM (metal-from-normals) — Design Spec (Fork B, slice 3a)

**Date:** 2026-08-28
**Status:** Design approved in brainstorm; awaiting spec review before planning.
**Classification:** Architectural (new pure consumer module `materials.py`; a new
per-region *material* property threaded through the region/plan chain) — but the
first slice is small, capability-gated on the normal field, and regression-locks
Path L byte-identical.

## Background — why this exists

Photometric stereo shipped (`5c5eea9`) and the Fork B foundation `surface.py`
(`curvature`, `ambient_occlusion`, `reflect`) is built and tested. Two Fork B
consumers already ship: geometric edge highlights (slice 1, curvature) and
cavity/AO recess shades (slice 2, concavity). This spec is **slice 3a: NMM (Non-
Metallic Metal) placement from the normal field** — the "highest-value slice" the
roadmap flagged (real fake-horizon placement becomes *derivable* instead of
invented). `surface.reflect()` was built in slice 1 and is consumed **nowhere yet**;
this slice is its first consumer.

OSL (object-source lighting) is grouped with NMM in the roadmap but is a
mechanically distinct technique (a colored virtual light casting a glow via `N·L`,
not a mirror sampling an environment via `R`). It is an explicit **non-goal here**
and becomes a later sibling slice on the same `reflect()` foundation.

## What NMM is, and why the normal field unblocks it

NMM paints metal with matte paint by hand-placing the reflections a mirror surface
would show: a bright virtual sky above, dark ground below, and a hard **horizon**
line where they meet, usually across the surface's brightest curve. The roadmap has
always called NMM "≈70% layering (extreme contrast, the engine can do) + ~30%
invented (the horizon/reflected-ground placement, which luminance cannot read)."

A **normal field is per-pixel surface orientation**, so the reflection vector
`R = 2(N·V)N − V` is computable per pixel (`surface.reflect`). Sampling a virtual
environment along `R` turns the "invented 30%" — where the horizon and reflections
land — into a **geometric derivation**. That is the unlock this slice cashes.

## The load-bearing constraint — two input paths, always both live

Unchanged from the Fork B foundation spec (2026-08-24):

- **Path L** — single photo → luminance shading. Cheap, no torch, no capture
  ceremony. Default and fast path.
- **Path P** — multi-shot → photometric stereo → normal field. The only source of a
  real normal field.

NMM is **capability-gated on the presence of a normal field**, not on a mode flag.
Normals present (Path P) → NMM is available; normals absent (Path L) → the feature is
invisible and Path L behaves **byte-identically** to today. This is enforced at two
layers: the UI only renders NMM controls when `normal_field is not None`, and
`plan_region` falls back to matte if asked for NMM without normals (defense in depth).

## Core idea — NMM as a per-region *material* that re-bands from a reflection environment

The brainstorm settled two architectural choices:

1. **Re-band from the reflection environment** (not an overlay mask). An NMM region's
   `light` field is *replaced* by a reflection-environment brightness, then banded by
   the existing machinery. The dark/light gradient and horizon emerge geometrically;
   the metal ramp (the region's palette) maps onto them. This is the honest NMM, and
   it rides the existing `light` seam in `plan_region` — no forked engine.
2. **Per-region material, global horizon.** NMM applies to specific parts (the blade,
   the gold trim) — exactly the manual regions. So "this region is metal" is a
   **per-region property** on `Region`. The horizon *height* (the one parameter that
   most changes the NMM look) is a **global styling knob**, consistent with how
   `edge_sensitivity` is global today.

Colors come from the **region's own assigned palette** (consistent with the tool's
"your paints" ethos and slices 1–2); the painter assigns an NMM ramp or loads the
built-in `NMM Gold` / `NMM Copper` recipe (already in `recipes_builtin.json`). This
slice only *places* those colors on the reflection curve — it invents no colors.

## Architecture

### New: `src/mini_highlight_advisor/materials.py` (pure, torch-free, UI-agnostic)

Mirrors `edges.py`'s relationship to `surface.py`: a normal-field *consumer* that
imports `surface.reflect`, numpy in / numpy out, no Streamlit, no torch. Named
`materials.py` (not `nmm.py`) so the future `osl_light()` sibling has a home.

```
nmm_light(normals, mask, view=(0,0,1), horizon=0.5, softness=0.15) -> (H,W) float32 in [0,1]
```

- Computes `R = reflect(view, normals)` per pixel (`view` defaults to `+Z`, straight
  toward the viewer, the same convention pinned in `relight.py` / `surface.py`:
  `R=x-right, G=y-up, B=z-toward-viewer`).
- Brightness is a **smoothstep on `R`'s vertical component** `R_y` (y-up) around
  `horizon`: reflections pointing up (`R_y` above the horizon) catch the bright sky
  (→1); pointing down (below) catch dark ground (→0); `softness` sets the transition
  half-width. The transition band is the classic hard NMM horizon.
- `horizon` is expressed in normalized `R_y` space: `0.5` ≈ mid; lower slides the
  horizon down (more sky, higher-key metal), higher slides it up (more ground).
  Mapped so a single UI slider `0..1` moves it across the useful range.
- Off-mask pixels → 0. Consumes the already-normalized normal field (defensive
  renormalize via the same `_validate` guarantee `surface` uses); a degenerate
  all-zero field yields a flat (uniform) map, never a crash.
- **Inherently light-independent**: depends only on `view` + `normals`, never on any
  diffuse light direction — the same virtue as curvature edges, and the property the
  tests lock.

### Changed: per-region material property

`regions.Region` gains one field:

```python
@dataclass
class Region:
    name: str
    mask: np.ndarray
    palette: list[PaintColor]
    coverage: list[float]
    material: str = "matte"      # "matte" (default) | "nmm"
```

`region_state.RegionBook` gains a `whole_material: str = "matte"` field (for the
"Whole mini" leftover region) and accessors mirroring the palette/coverage ones:

```python
material_at(g) -> str
set_material_at(g, material) -> None
```

`"matte"` is the default everywhere, so any region that is never touched — every
photo-mode region — behaves exactly as today.

### Changed: `pipeline.plan_region`

Two new params, threaded exactly like the existing region inputs:

```python
def plan_region(rgb, sub_mask, light, name, palette, coverage,
                ..., normals=None, shades=False,
                material="matte", nmm_horizon=0.5) -> RegionPlan:
    if material == "nmm" and normals is not None:
        light = materials.nmm_light(normals, sub_mask, horizon=nmm_horizon)
    # ... everything below (banding, coverage, steps, edges, shades) unchanged
```

- The swap happens **before** banding, so `band_light`, `coverage_pct`,
  `per_band_images`, geometric edges, and recess shades all run on the NMM light
  unchanged.
- `material == "nmm"` with `normals is None` → **matte fallback** (uses the passed
  `light`), never a crash. This can only arise defensively; the UI won't offer NMM
  without normals.
- `material == "matte"` → the `if` is skipped and the function is **byte-identical to
  today** (regression lock).
- Interaction with the existing relief/flat-albedo caps: for an NMM region the relief
  cap (if on) measures `relief_recommended_bands` on the NMM light, whose strong
  built-in contrast will not trip the flat cap; `flat_albedo` comes only from
  `per_region_norm`, which is always off in PS mode — so NMM regions are never flagged
  flat. No special-casing needed.

### Changed: `pipeline.analyze_regions`

One new global param `nmm_horizon: float = 0.5`, added to the shared `ekw` dict, plus
passing each region's material through:

```python
ekw = dict(..., normals=normal_field, shades=shades, nmm_horizon=nmm_horizon)
# whole-mini leftover region:
plan_region(rgb, default_sub, lgt, WHOLE_MINI, default_palette, coverage,
            flat_albedo=flat, material=book_whole_material, **ekw)
# drawn regions:
plan_region(rgb, sub, lgt, r.name, r.palette, r.coverage,
            flat_albedo=flat, material=r.material, **ekw)
```

The whole-mini material is passed by the caller (`results.render`) from
`book.material_at(0)` alongside the existing `book.analyze_args()` outputs (either
extend `analyze_args` to include materials, or pass `whole_material` explicitly — the
plan will pick the lower-churn option). Regression lock: when every material is
`"matte"` (all Path L calls, and any PS session with no NMM region), output is
byte-identical to today.

### Changed: UI (PS mode only, gated on `normal_field is not None`)

- **Per-region material selector** — in `ui/editor.py`, after the palette editor, a
  `st.selectbox("Material", ["Matte", "NMM"])` for the currently selected region,
  written via `book.set_material_at(sel, …)`. Rendered **only when
  `normal_field is not None`**; absent entirely in photo mode. A small helper (inline
  or a tiny `ui/material_panel.py`, plan's call) keyed per `keys` entry.
- **Global horizon slider** — in `ui/results.py`, beside the existing "Recess shades"
  toggle (which is already `normal_field`-gated), a `st.slider("Horizon height",
  0.0, 1.0, 0.5, 0.05)`, passed to `analyze_regions(nmm_horizon=…)`. Shown only when
  normals present; a short help string explains it slides the virtual horizon
  high/low.
- No new capture burden; no torch in the app; Path L UI untouched.

## Data flow

```
Path L:  photo → luminance light ─┐
                                  ├─ analyze_regions(normal_field=None, nmm_horizon=…)
                                  │     every region material defaults "matte"
                                  │     → plan_region skips the NMM swap  (BYTE-IDENTICAL)
                                  └─ plan / overlay / steps

Path P:  frames → ps_tool → normal.png ─ relight → light_field (banding for matte regions)
                                       └────────── normal_field ─┐
              per-region material (Matte | NMM), global horizon ─┤
                                  ├─ analyze_regions(light_field=…, normal_field=normals, nmm_horizon=h)
                                  │     matte region → light = light_field         (unchanged)
                                  │     nmm  region → light = materials.nmm_light(normals, sub, h)   (NEW)
                                  │     banding / steps / edges / shades run on that light
                                  └─ plan / overlay / steps
```

## What rides existing machinery unchanged

Banding (`band_light`), coverage sliders and `coverage_pct`, per-band step images
(`per_band_images`), **geometric edge highlights** (the blade's edge highlight is a
genuine NMM element and keeps working, because edges come from curvature — independent
of the light source), recess shades, combined preview (`paint_regions`), swatch board.
NMM composes with all of them for free.

## Persistence

The mini-projects persistence (`projects.py`) serializes **photo-mode** regions only;
PS mode is session-only (v1). Because `material` defaults to `"matte"` and photo-mode
regions never set it, **no persistence change is required for correctness** — old
projects load with `Region(..., material defaults "matte")`. The plan will
*optionally* serialize `material` (write it; read with `.get("material", "matte")`)
purely for forward-compatibility if PS persistence ever lands; this is a one-line,
backward-compatible addition, not a blocker.

## Error handling

- `materials.nmm_light` validates input shape `(H,W,3)` and renormalizes defensively
  (mirrors `surface._validate` / `relight.load_normals`); an all-zero degenerate field
  yields a flat map (uniform brightness), which bands into a single flat plan — the
  same graceful-empty contract the other consumers honor, never a crash, never mud.
- `plan_region` with `material="nmm"` and `normals=None` falls back to matte (uses the
  passed `light`). This cannot happen from the UI (NMM is only offered with normals),
  but the fallback keeps the pure API total.
- Shape mismatch between `normal_field` and `rgb` is already validated at the
  `analyze_regions` seam (added in the Fork B slice-1 spec); unchanged here.

## Testing strategy

Reuse the committed synthetic PS fixture (`tests/fixtures/ps/synth_normal.png` +
`synth_mask.png`, a dome + ridges) so the whole slice is testable offline — no torch,
no captures.

**`materials.nmm_light` (pure, TDD):**
- flat front-facing normals (all `+Z`) → `R = +Z`, `R_y ≈ 0` → uniform map (no
  spurious horizon);
- synthetic convex dome → monotone bright-top → dark-bottom (the reflection sweeps sky
  → ground as the surface tips over);
- `horizon` shifts the light/dark split location monotonically (raise horizon → more
  dark/ground area);
- **light-independence**: the map is identical when computed under two different
  diffuse-light setups (it never takes a light dir as input — this is the core value
  claim and the property the light-gradient approaches fail);
- off-mask pixels → 0; degenerate all-zero normals → flat, no crash.

**`plan_region` (TDD):**
- `material="matte"` → **byte-identical regression lock** vs current output;
- `material="nmm"` re-bands from the NMM light: construct a case where the passed
  `light` is **uniform** but the normals vary → matte would give one flat band, NMM
  gives a varied plan (proves the source swap);
- `material="nmm"`, `normals=None` → matte fallback (identical to the matte case, no
  crash).

**`analyze_regions` (TDD):**
- all-matte (with and without `normal_field`) → byte-identical to today (Path L and
  no-NMM Path P regression lock);
- a drawn region with `material="nmm"` → that region's plan differs from its matte
  counterpart while sibling matte regions are unchanged (per-region isolation);
- `nmm_horizon` threads through and changes the NMM region's banding.

**`RegionBook` (TDD):**
- `material_at`/`set_material_at` default `"matte"`, route by index (whole vs drawn),
  raise on out-of-range like the palette/coverage accessors; `whole_material` round-trips.

**UI (AppTest, matching existing `ui/` tests):**
- PS mode renders the Material selectbox + Horizon slider; selecting NMM for a region
  re-renders the plan without error;
- photo mode renders **neither** control (capability gate);
- smoke-level: the PS plan still draws with a matte default (no regression to the
  existing PS flow).

## Rollout / build order (for the plan)

1. `materials.nmm_light` + tests against the synthetic fixture — pure, TDD, unblocks
   everything (light-independence + monotone-dome are the key tests).
2. `Region.material` + `RegionBook.whole_material` / `material_at` / `set_material_at`
   + tests.
3. `pipeline`: `material=` + `nmm_horizon=` in `plan_region` (env-light swap) and
   `analyze_regions` (per-region material threading); **regression-lock matte
   byte-identical**.
4. UI: per-region Material selectbox (`editor.py`) + global Horizon slider
   (`results.py`), both `normal_field`-gated + AppTest.
5. *(optional, forward-compat)* serialize `material` in `projects.py` with a
   `.get("material", "matte")` default.

Steps 1–3 deliver and prove the value against the synthetic fixture and any normal map
on disk (e.g. staircase output), independent of a live capture.

## Non-goals (this slice)

- **No OSL** (colored-light glow via `N·L` + tint) — the next sibling slice on the
  same `reflect()` foundation.
- **No procedural metal-ramp synthesis** — the user supplies the ramp or loads an NMM
  recipe; this slice only places colors, invents none.
- **No double-horizon / reflected-floor / environment rotation / azimuth** — a single
  global horizon-height control only. Reflection direction stays fully geometric.
- **No NMM in photo mode** (no normals) — capability-gated off.
- **No change** to banding math, coverage, palette, regions-drawing UI, steps,
  Path L behaviour, or persistence semantics.
