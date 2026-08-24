# Geometry-from-Normals — Design Spec (Fork B, slice 1)

**Date:** 2026-08-24
**Status:** Design approved in brainstorm; awaiting spec review before planning.
**Classification:** Architectural (new pure subsystem: `surface.py`; capability-gated
consumers hang off it) — but the first *slice* is small and regression-locked.

## Background — why this exists

Photometric stereo shipped (`5c5eea9`): the app can now hold a **true surface-normal
field**, not just a 2D luminance proxy. The roadmap re-triage (2026-08-24 addendum to
`2026-08-09-roadmap-and-idea-assessment.md`) chose **Fork B — cash the geometry**: derive
features that were previously "invented knowledge" directly from the normal field, all
offline, with **no new capture burden** (they consume the normals Path P already produces).

This spec covers the **shared foundation (`surface.py`) + the first consumer (geometric
edge highlights)**. Cavity/AO shades, specular/NMM (via reflection vectors), and
normal-discontinuity auto-regions are later slices on the same foundation and are out of
scope here (named in "Future slices").

## The load-bearing constraint — two input paths, always both live

The app must keep **both** input paths working simultaneously, forever:

- **Path L** — single photo → luminance shading. Cheap, no torch, no capture ceremony.
  The default and fast path.
- **Path P** — multi-shot → photometric stereo → normal field. High ceremony, external
  torch sidecar, defeats dark albedo, and is the *only* source of a real normal field.

**B must never degrade Path L.** Geometry features are therefore **capability-gated on the
presence of a normal field**, not on a mode flag: normals present → richer geometry; normals
absent → Path L behaves byte-identically to today.

## Why this is not horrible to design — B rides the existing seam

`analyze_regions` already branches on an optional injected signal (`light_field`):

```python
if light_field is not None:      # Path P: mask from alpha, light = injected normals·l
    ...
else:                            # Path L: shading from luminance
    shading = prepare_shading(rgb, alpha)
```

B adds **one analogous optional parameter — `normal_field=None`** — threaded exactly like
`light_field`. No forked engine, no duplicated pipeline. When it is `None`, the geometry
code path is never entered and Path L is untouched.

### Concrete motivation for the first consumer

Today's edge highlights (`edges.py`) are computed from the **gradient of the light field**
(`_grad_mag(light, mask)`). In Path P that light field is `normals · l`, so the edges are
gradients of the *relit* image — they **move when the virtual light moves**. True sculpt
ridges do not move. Sourcing edge highlights from **curvature of the normal field** makes
them **light-independent** and geometrically correct. That is the upgrade this slice ships,
and it is directly A/B-comparable against the existing behaviour.

## Architecture

### New: `src/mini_highlight_advisor/surface.py` (pure, torch-free, UI-agnostic)

> **Naming:** the module is `surface.py` (surface-geometry-from-normals), **not**
> `geometry.py` — `ui/geometry.py` already exists for unrelated 2D lasso path/point math.
> Distinct name, distinct concern.


Same shape/discipline as `relight.py` (numpy in, numpy out; no Streamlit, no torch). The
normal-field toolkit (referred to below as `surface`). **This slice implements and tests all three primitives** (they are
cheap and share test scaffolding) even though only `curvature` is consumed now — the others
unblock the later slices without another foundation pass:

```
curvature(normals, mask) -> (H,W) float32          # signed mean curvature; >0 convex ridge, <0 concave crease; off-mask 0
ambient_occlusion(normals, mask) -> (H,W) float32  # [0,1], 1 = exposed, 0 = deep recess (screen-space AO from normals)
reflect(view, normals) -> (H,W,3) float32          # reflection vectors R = 2(N·V)N − V; for later specular/NMM
```

- **Convention** is the pinned one from `relight.py` (`R=x-right, G=y-up, B=z-to-viewer`);
  `surface.py` documents that it consumes the *already-normalized* field, so there is no
  flip toggle (same guarantee as relight).
- `curvature` is computed as the divergence of the normal field (finite differences of the
  in-plane normal components inside the mask), Gaussian-smoothed to calm primer grain —
  reusing the pre-blur rationale already in `edges._grad_mag`. Sign convention:
  convex/outward = positive. Off-mask pixels contribute nothing (masked finite differences).

### First consumer: geometric edge highlights (`edges.py` + one `plan_region` seam)

`edges.py` gains a curvature-sourced sibling to the existing light-gradient functions:

```
geometric_edge_mask(normals, mask, sensitivity=0.5) -> bool (H,W)   # thresholds convex curvature; reuses _despeckle + a bright/convex-side filter
```

It **reuses** the existing despeckle and percentile-thresholding machinery so behaviour
(min area, sensitivity→percentile mapping) stays consistent with `edge_mask`. The difference
is the *source*: convex curvature magnitude instead of light gradient.

`plan_region` gains an optional `normals=` sub-field (masked to the region, threaded exactly
as `light` is today). The selection is local and minimal:

```python
# pipeline.plan_region, at the edge-overlay step (today lines ~148/151)
if normals is not None:
    main = geometric_edge_mask(normals, sub_mask, edge_sensitivity)
else:
    main = edge_mask(light, sub_mask, edge_sensitivity)   # Path L unchanged
```

`extreme_edge` (sharpest-30% subset) follows the same source selection.

### Threading (the whole change to the call chain)

```
analyze_regions(..., light_field=…, normal_field=None)   # NEW param, defaults None
   └─ if normal_field is not None: sub-mask it per region (like light)
   └─ plan_region(rgb, sub, light, …, normals=<region normals or None>)
        └─ edges: geometric_edge_mask(normals,…)  if normals else edge_mask(light,…)
```

- **Path L** callers pass nothing new → `normal_field=None` → every branch takes the
  existing path → **byte-identical output** (regression-locked).
- **Path P** (the app's PS import) already has the normal field in session (`NORMALS`); it
  passes it as `normal_field=` alongside the existing `light_field=`. `relight`/`light_field`
  is unchanged — it still drives *banding*; normals now additionally drive *edges*.

### App wiring (minimal)

In PS mode the app already loads `NORMALS`. The only change: pass it to `analyze_regions`
as `normal_field=`. No new UI in this slice (edge toggle/sensitivity already exist). Path L
UI is untouched.

## Data flow

```
Path L:  photo → luminance light ─┐
                                  ├─ analyze_regions(normal_field=None)
                                  │     edges from light gradient  (TODAY, unchanged)
                                  └─ plan / overlay / steps

Path P:  frames → ps_tool → normal.png ─ relight → light_field (banding)
                                       └────────── normal_field  ─┐
                                  ├─ analyze_regions(light_field=…, normal_field=normals)
                                  │     banding from light_field   (unchanged)
                                  │     edges from curvature       (NEW, light-independent)
                                  └─ plan / overlay / steps
```

## Error handling

- `surface.py` validates input shape `(H,W,3)` and renormalizes defensively (mirrors
  `relight.load_normals`); a degenerate all-zero normal field yields an empty curvature map,
  which `geometric_edge_mask` turns into an empty edge mask (same graceful-empty contract as
  `edge_mask` when no gradient exists) — never a crash, never mud.
- Shape mismatch between `normal_field` and `rgb`/`alpha` in `analyze_regions` raises a clear
  error at the seam (the app already validates normal/mask dims on import; this is defense in
  depth).

## Testing strategy

Reuse the committed **synthetic fixture** from the PS work
(`tests/fixtures/ps/synth_normal.png` + `synth_mask.png`, generated by
`tests/fixtures/ps/generate_synth.py` — a dome + ridges) so the whole slice is testable
offline — no torch, no captures. Extend `generate_synth.py` if a sharper isolated ridge is
needed for the edge tests.

**`surface.py` (pure, TDD):**
- `curvature`: flat region (constant normals) → ~0 everywhere; a synthetic convex dome →
  positive interior; a ridge line → positive along the crest; off-mask → 0.
- `ambient_occlusion`: exposed convex point → near 1; a modeled crevice → lower; monotone
  with recess depth on the synthetic fixture.
- `reflect`: known `N`,`V` → known `R` (e.g. `N=V=+Z → R=+Z`); output unit-length.

**`geometric_edge_mask` (TDD):**
- synthetic ridge → edge mask lands **on the crest**, not on flat regions;
- **light-independence**: the mask is identical under two different virtual light dirs
  (locks the core value claim — this is what the light-gradient version fails);
- speckle below `_MIN_EDGE_AREA` removed (reuses `_despeckle`);
- empty/flat normals → empty mask (no crash).

**`analyze_regions(normal_field=…)`:**
- **byte-identical regression lock** when `normal_field` is omitted (Path L untouched);
- with `normal_field` present, region edge overlays come from curvature: construct a case
  where light-gradient edges and curvature edges **disagree** (uniform relit light but a real
  ridge in the normals) → edges track curvature (proves the source swap).

**UI (AppTest, matching existing `ui/` tests):** PS import still renders; the plan still
draws; no new UI required, so this is a smoke-level regression check only.

## Rollout / build order (for the plan)

1. `surface.py` (curvature, AO, reflect) + tests against the synthetic fixture — pure, TDD,
   unblocks everything.
2. `edges.geometric_edge_mask` + tests (light-independence is the key test).
3. `pipeline`: add `normal_field=` to `analyze_regions`, thread `normals=` into `plan_region`,
   select edge source; regression-lock Path L byte-identical.
4. App: pass `NORMALS` as `normal_field=` in PS mode (one line + AppTest smoke).

Steps 1–3 deliver and prove the value against the synthetic fixture and any normal map on
disk (e.g. staircase output), independent of a live capture.

## Future slices (out of scope here, same foundation)

- **Cavity / AO shades** — consume `ambient_occlusion` + concave `curvature`; introduces a
  "shade below the darkest band" concept (recess darkening), the first non-highlight output.
- **Specular / real NMM + OSL** — consume `reflect()`; the highest-value slice (fake horizon
  / reflected-ground become derivable), plus coloured OSL tints. Builds on this foundation.
- **Normal-discontinuity auto-regions** — cluster curvature discontinuities into part
  proposals; re-opens the SAM-killed auto-region idea. Largest; last.

## Non-goals (this slice)

- No cavity/specular/NMM/auto-region output (foundation primitives are built and tested, but
  only curvature is *consumed*).
- No change to banding (still driven by `light_field`), palette, coverage, regions UI, steps,
  or persistence.
- No new capture requirement; no torch in the app; Path L behaviour frozen.
