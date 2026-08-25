# Cavity / AO Recess Shades — Design Spec (Fork B, slice 2)

**Date:** 2026-08-25
**Status:** Design approved in brainstorm; awaiting spec review before planning.
**Classification:** Architectural — first *non-highlight* output (recess darkening),
a new consumer on the `surface.py` normal-field foundation. The slice itself is small
and regression-locked, riding the seams the edge-highlight slice already cut.

## Background — why this exists

Photometric stereo shipped (`5c5eea9`) and slice 1 of Fork B — geometric edge highlights —
merged (PR #24, `496fb8a`): the app now derives **light-independent** edge highlights from
the *convex* curvature of the normal field, capability-gated on a normal field being present
(`normal_field=`), leaving Path L (single-photo luminance) byte-identical.

This is **slice 2 on the same foundation**: consume the *concave* side of the surface signal
to place **recess shades** — the first output that is not a highlight. Same discipline: no new
capture burden (consumes the normal field Path P already produces), pure/offline, and Path L
frozen.

The roadmap re-triage (`2026-08-09-roadmap-and-idea-assessment.md`, 2026-08-24 addendum, Fork
B) named this explicitly: *"Cavity / AO shades — consume `ambient_occlusion` + concave
`curvature`; introduces a 'shade below the darkest band' concept (recess darkening), the first
non-highlight output."*

## The load-bearing constraint — Path L stays frozen

As with slice 1, recess shades are **capability-gated on the presence of a normal field**, not
on a mode flag. No normal field → the shade code path is never entered → Path L behaves
byte-identically to today. There is **no luminance approximation of AO** — a recess shade from
luminance would be exactly the "invented knowledge" Fork B exists to stop producing. Shades are
a normals-only feature.

## Why this is not horrible to design — it mirrors the edge slice

Slice 1 established every seam this slice needs:

- `surface.curvature(normals, mask)` — signed mean curvature (>0 convex ridge, <0 concave
  crease). Slice 1 consumes the **convex** clip; this slice consumes the **concave** clip.
- `edges.geometric_edge_mask` — thresholds convex curvature with a sensitivity→percentile map
  and `_despeckle`. The recess mask is its exact mirror on the concave side.
- `plan_region`'s `edge_overlays` list — `list[(mask, color)]` composited at fixed alpha in
  `paint_preview` / `paint_regions`. A recess shade is *just another* `(mask, color)` tuple
  (a dark colour on a concave mask), so it reuses that path with **zero new compositing code**.
- `overlay.edge_steps` — emits extra `BandStep`s for the paint-along guide. `shade_steps` is
  its mirror.

## Architecture

### `edges.py` — new `cavity_mask` (mirror of `geometric_edge_mask`)

```
cavity_mask(normals, mask, sensitivity=0.5) -> bool (H,W)   # concave curvature; reuses _despeckle
```

Implementation is the concave twin of `geometric_edge_mask`:

```python
conc = np.clip(-curvature(normals, mask), 0.0, None)   # creases only (edges use +clip)
conc[~mask] = 0.0
vals = conc[mask]; vals = vals[vals > 0]
if vals.size == 0:
    return np.zeros(mask.shape, bool)                  # flat/convex-only -> empty, graceful
pct = float(np.clip(94.0 - 12.0 * sensitivity, 82.0, 97.0))   # SAME mapping as edges
thr = np.percentile(vals, pct)
return _despeckle((conc >= thr) & mask)
```

- **Honest-by-construction:** a flat region has ~zero curvature → the `vals > 0` filter plus
  `_despeckle` yield an **empty mask** — no crash, no manufactured shade on flat surfaces. This
  matches the project's existing relief-honesty discipline (`relief_recommended_bands`,
  `flat_albedo`), which exists precisely to stop manufacturing precision the sculpt can't show.
- **Light-independent:** curvature is a property of the normal field, not of any virtual light,
  so the mask is identical under different relight directions (the same core value claim slice 1
  locks for edges).
- **Signal note:** thresholding concave curvature *is* thresholding ambient occlusion — AO
  (`surface.ambient_occlusion`) is `1 − normalised concavity`, a monotonic transform, so a
  concave-curvature percentile threshold and an AO cutoff select the same pixels. This slice
  therefore consumes the AO signal in its raw (concave-curvature) form. AO's *continuous* value
  (for depth-graded shade opacity) is an explicit non-goal here (see Future refinement).
- The `edges.py` module docstring is broadened from "Edge-highlight masks" to note it now also
  produces curvature-derived **recess** masks.

### Shade colour — auto-darkened base

The shade paint is derived, not user-supplied (symmetric with edges reusing the lightest
palette colour):

```python
_SHADE_DARKEN = 0.55
shade_rgb = (colors[0] * _SHADE_DARKEN).astype(np.float32)   # darkest palette paint, glazed darker
```

`colors[0]` is always present (even a `flat_albedo`- or `relief_cap`-capped region keeps its
base paint), so there is no empty-palette edge case. No new palette slot, no new picker.

### Rendering — reuse the overlay list + a mirror step builder

**Preview overlay (no new compositing code):** the recess tuple is prepended to the existing
`edge_overlays` list in `plan_region`, so `paint_preview` and `paint_regions` composite it via
their current fixed-alpha `(mask, color)` loop. Prepending puts the shade *under* any edge
tuples, so a ridge wins the rare pixel that is both (concave and convex masks are near-disjoint,
so this is an ordering guarantee, not a common case).

**Step image (`overlay.shade_steps`, mirror of `edge_steps`):**

```
shade_steps(rgb, recess_mask, shade_rgb, alpha=0.78, start_index=…) -> list[BandStep]
```

Emits a single `BandStep(kind="shade", label="Recess Shade")` — a paint-along step rendered
with the same `_zone_render` / `_render_step` machinery as bands and edges. Appended after the
band steps and edge steps.

### Threading (the whole change to the call chain)

```
analyze_regions(..., normal_field=…, shades=False)      # NEW param, defaults False
   └─ plan_region(..., normals=…, shades=False)          # NEW param, defaults False
        └─ if shades and normals is not None:
               recess = cavity_mask(normals, sub_mask, edge_sensitivity)
               shade_rgb = colors[0] * _SHADE_DARKEN
               overlays  = [(recess, shade_rgb)] + (overlays or [])   # shade under edges
               steps     = steps + shade_steps(rgb, recess, shade_rgb, start_index=len(steps))
```

- **Path L** and any caller that omits `shades` → `shades=False` → branch never entered →
  **byte-identical output** (regression-locked, same guarantee as slice 1).
- **Shades on but no normals** (`shades=True, normal_field=None`, e.g. a stray toggle in Path L)
  → the `normals is not None` half of the gate is false → no shade, no crash. The UI only shows
  the toggle in PS mode, but the engine is defensively correct regardless.

### App wiring (minimal)

In PS mode the app already holds `NORMALS` and passes it as `normal_field=`. This slice adds:

- one `st.checkbox("Recess shades")`, rendered **only when a normal field is in session**
  (PS mode); default off.
- pass its value as `shades=` to `analyze_regions`.

It reuses the existing edge-sensitivity slider (no new slider). Path-L UI is untouched — the
checkbox does not appear without a normal field.

## Data flow

```
Path L:  photo → luminance → analyze_regions(normal_field=None, shades=False)
                                   edges from light gradient      (unchanged)
                                   NO shades                      (gate off)

Path P:  frames → ps_tool → normal.png → relight → light_field (banding)
                                       └─────────── normal_field ─┐
                             analyze_regions(light_field=…, normal_field=normals, shades=<toggle>)
                                   banding from light_field       (unchanged)
                                   edges  from convex curvature   (slice 1)
                                   shades from concave curvature  (NEW) — recess overlay + step
```

## Error handling

- `cavity_mask` inherits `curvature`'s `(H,W,3)` validation and the graceful-empty contract:
  degenerate / all-zero / flat / convex-only normal fields yield an **empty mask** (mirrors
  `geometric_edge_mask` and `edge_mask`) — never a crash, never a full-mini smear of shade.
- `analyze_regions` already validates `normal_field` shape against `rgb` at the seam (added in
  slice 1); no new validation needed.
- Silhouette-boundary curvature inflation is a known `curvature` artefact (documented in
  `surface.py`): interior recesses are reliable; a rim-following shade near the silhouette is a
  boundary artefact. `_despeckle` and the percentile threshold suppress most of it; this slice
  does not add special boundary handling (same posture as slice 1's edges).

## Testing strategy

Reuse the committed synthetic fixture from the PS/geometry work
(`tests/fixtures/ps/synth_normal.png` + `synth_mask.png`, a dome + ridges from
`generate_synth.py`). Extend `generate_synth.py` with an isolated **concave crease** if the
existing fixture lacks a clean recess for the shade tests.

**`cavity_mask` (TDD, mirrors the `geometric_edge_mask` tests):**
- synthetic concave crease → mask lands **in the recess**, not on flat or convex/ridge regions;
- **light-independence**: mask identical under two different virtual light directions (locks the
  core value claim — a luminance-shade would fail this);
- speckle below `_MIN_EDGE_AREA` removed (reuses `_despeckle`);
- flat or convex-only normals → **empty mask** (no crash, no manufactured shade).

**`shade_steps` (TDD):**
- returns one `BandStep(kind="shade", label="Recess Shade")` at the requested `start_index`;
- zone / cumulative renders use the darkened `shade_rgb`;
- empty recess mask → the step still renders without error (empty active zone).

**`plan_region(shades=True, normals=…)`:**
- recess shade tuple present in `edge_overlays`, ordered **before** any edge tuples;
- a shade `BandStep` is appended to `steps` with the correct darkened colour;
- **byte-identical regression lock** when `shades=False` *or* `normals=None` (Path L / default
  untouched);
- construct a case with a real concave crease → the shade overlay covers the recess pixels.

**UI (AppTest, matching existing `ui/` tests):**
- the "Recess shades" checkbox appears when a normal field is in session and is **absent** in
  Path L;
- toggling it on still renders the plan (smoke-level regression check); no new UI beyond the
  checkbox.

## Rollout / build order (for the plan)

1. `edges.cavity_mask` + tests against the synthetic fixture (light-independence + graceful-empty
   are the key tests). Extend `generate_synth.py` with a crease if needed. Pure, TDD.
2. `overlay.shade_steps` + tests (mirror of `edge_steps`).
3. `pipeline`: add `shades=` to `analyze_regions` and `plan_region`; build the shade colour,
   prepend the overlay tuple, append the shade step; regression-lock `shades=False`/`normals=None`
   byte-identical.
4. App: add the PS-only "Recess shades" checkbox, thread `shades=` (one widget + one arg) +
   AppTest smoke.

Steps 1–3 deliver and prove the value against the synthetic fixture and any normal map on disk,
independent of a live capture.

## Future refinement (out of scope here)

- **AO-depth-graded opacity** — render deeper recesses darker (opacity ∝ `1 − ambient_occlusion`)
  instead of a flat fill. Genuinely richer, and *calls* `surface.ambient_occlusion`'s continuous
  value directly, but requires a per-pixel-alpha overlay path (the current `(mask, color)` list
  is fixed-alpha). Deferred to keep this slice minimal and its render path unchanged.
- **Dedicated wash/shade paint slot** — let the user pick a wash (e.g. a real shade paint) per
  region instead of auto-darkening the base. Adds a palette slot + picker to the region editor;
  deferred (auto-darken is the YAGNI default).

## Non-goals (this slice)

- No luminance/Path-L shades (normals-only, capability-gated; Path L frozen byte-identical).
- No AO-depth-graded opacity; no dedicated wash slot (both above).
- No change to banding, palette, coverage, regions UI, steps ordering beyond appending the shade
  step, or persistence.
- No specular/NMM (that is the `reflect()` slice) and no normal-discontinuity auto-regions.
- No new capture requirement; no torch in the app.
