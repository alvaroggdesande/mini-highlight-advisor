# Edge Highlights — Design

**Date:** 2026-08-12
**Status:** Approved design (spec). Precedes the implementation plan.
**Roadmap link:** realises the edge-highlight slice of idea #9 (techniques), now
unblocked because manual regions shipped (PR #9 lasso, PR #10 region UX v2). See
`2026-08-09-roadmap-and-idea-assessment.md` §"Edge highlighting is often
region-separation, not 'lightest light'".

## Problem

Real minis put a **crisp edge highlight on every raised rim of every plate**, even
on plates angled *away* from the key light (see reference: a blue Space Marine whose
single-colour armour is ~15–20 separate plates, each with its own lit-edge line). Two
consequences that define this feature:

1. **Global luminance ranking is the wrong signal.** The top tonal quantile only
   catches plates facing the light and misses edge highlights on dimmer-facing
   plates. Edge highlights ride **local geometry**, not global brightness.
2. **Broad highlight and edge line coexist.** Each plate has a *broad* lighter zone on
   its upper face (the tonal highlight band the pipeline already produces) **and** a
   separate, thinner, brighter line on its edge. So the edge highlight is an
   **additive** layer, not a re-labeled band.

Today the pipeline only fakes this: the top tonal band is *named* "Edge Highlight"
(`palette.py:35–38`, note "sharpest top edges only" in `overlay.py:14`), but it is
just the brightest broad quantile zone — the label over-promises.

## Premise fit

The engine's core premise is **read the light the sculpt actually catches** — never
invent light. Edge highlights honour this: they are derived from the **luminance
gradient** of the photo, not from an assumed light source. Crucially, because the
input is a **primed / monochrome** mini, there is no paint colour to confuse the
signal — **every luminance edge is a real sculpt edge.** The "primed only" constraint
makes this method reliable here in a way it would not be on a painted mini.

## Approach (chosen)

**Additive, two-tier, reusing the palette's brightest paints. Tonal bands are
untouched.** Append edge-highlight step(s) after the tonal steps, per region:

- **Main edge line** — all strong edges, painted in the region's **second-lightest**
  paint (tonal band `n-2`). Always present when edge highlights are on.
- **Extreme edge** (optional, toggle) — only the *sharpest* subset of edges, painted
  in the region's **lightest** paint (tonal band `n-1`). Mirrors real practice
  ("Edge Highlight" then "Extreme Edge Highlight" — names already in
  `data/recipes_builtin.json`).

**Guard:** two-tier needs two distinct highlight-tier colours. Per the role taxonomy
the top two bands are both highlight-tier only at **n ≥ 5** (`Highlight` +
`Bright Highlight`); at n = 3–4 there is a single highlight, so extreme falls back to
**one-tier** using the single lightest paint, regardless of the extreme-edge toggle.

Rejected alternatives (from brainstorming): *reallocating* the brightest bands out of
broad zones (more faithful but more disruptive — deferred); *region-seam separation
lines* (fragile to imperfect lassos **and** insufficient — misses the internal plate
edges that are the real signal).

## Derivation — `edges.py`

New module, Streamlit-free, operating on the existing light map and a region mask:

```
edge_mask(light: np.ndarray, mask: np.ndarray, sensitivity: float) -> np.ndarray  # bool
```

Algorithm (candidate; exact operator chosen by the spike below):

1. **Gradient.** Sobel magnitude of `light` over the masked area.
2. **Strong edges, adaptively.** Threshold at an *in-region gradient percentile* set by
   `sensitivity` (higher sensitivity → lower percentile → more edges). Adaptive-per-
   region is what lets a shadowed plate and a lit plate both qualify.
3. **Bright side only.** Keep edge pixels whose luminance is above the *local* mean
   (small window). This drops downward-facing edges and needs **no light-direction
   input**.
4. **Silhouette.** Include the region's outer contour (lit side) as an edge.
5. **Thin.** Reduce to a 1–2px line (skeletonise / non-max suppression).

`extreme_edge_mask(...)` = the same map at a stricter threshold (sharpest/narrowest
subset) — reuses the computation, does not recompute from scratch.

### Spike gate (hard, first)

`spikes/edge_highlight_spike.py` on the reference Space-Marine-style photo decides the
operator (Sobel + bright-side vs Laplacian ridge vs morphological top-hat) and whether
clean plate lines are achievable at all. **Clean lines vs. fuzzy scribble is the whole
ballgame; if the spike cannot get clean lines, we stop — cheap to find out.** No engine
code is written before the spike passes.

## Pipeline integration — `pipeline.py`

- `analyze` and `analyze_regions` append edge `BandStep`(s) **after** the tonal steps,
  computed **per region** from that region's mask + palette:
  - main edge step: `exact_rgb` = region paint `n-2` (or `n-1` in one-tier fallback).
  - extreme edge step (if toggled and two colours exist): `exact_rgb` = paint `n-1`.
- No change to `banding.py`. The edge steps are a new *kind* of `BandStep` whose zone
  is an edge mask rather than a quantile band; `BandStep` may gain a small flag (e.g.
  `kind: "band" | "edge"`) so rendering/captions can distinguish them.

## UI — `app.py`

Per-region controls, alongside the region's palette/coverage:

- **"Edge highlights"** toggle — default **on**.
- **"Extreme edge highlight"** toggle — default **off** (opt-in second tier).
- **"Edge sensitivity"** slider — few sharpest ↔ more edges (maps to the gradient
  percentile).

## Rendering — `overlay.py`

- Edge step images render like other paint-along steps: dimmed greyscale background,
  magenta `_ACCENT` marks the edge zone, edge line drawn in the step's paint.
- The thin edge lines also overlay onto the **combined final preview** so the whole
  mini shows its rims (not only the isolated step image).
- **Naming cleanup:** rename the top *tonal* band from "Edge Highlight" to a broad
  name ("Bright Highlight") in `palette.py:35–38`; the appended edge step(s) take the
  "Edge Highlight" / "Extreme Edge Highlight" names. Only the real edge step claims the
  name. Update `_COVERAGE_NOTES` in `overlay.py` accordingly.

## Testing

Unit tests (`tests/test_edges.py`) on synthetic light maps:

- Two-plate luminance step → line lands on the **bright** side, is thin (≤2px).
- **Dim plate** (same step, lower absolute luminance) → still produces a line
  (adaptive threshold works).
- Flat / low-variance region → **no** edges (no scribble on noise-free flat).
- Extreme tier is a **subset** of the main edge mask.
- One-tier fallback when the palette has <2 distinct highlight colours.
- Pipeline: toggle off → no extra step; toggle on → correct number of appended steps
  with correct `exact_rgb` per region.

Plus the spike as visual validation on the real photo.

## Build order

1. **Spike** `spikes/edge_highlight_spike.py` → gate.
2. `edges.py` (`edge_mask`, `extreme_edge_mask`) + `tests/test_edges.py`.
3. Pipeline wiring (`analyze`, `analyze_regions`, `BandStep.kind`).
4. UI toggles + sensitivity slider.
5. Rendering (step images + combined-preview overlay).
6. Naming cleanup (`palette.py`, `overlay.py`) + adjust any affected tests.

## Out of scope

- Reallocating model (brightest bands as edge-only broad-zone replacement).
- Region-seam separation lines.
- Depth/curvature-based edges (luminance gradient only for v1; depth is a possible
  later refinement).
- Coloured / painted minis (unchanged v1 constraint).
