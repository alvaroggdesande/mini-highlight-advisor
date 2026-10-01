# Layer spread: final highlight layers feel scattered

Status: **idea / investigation notes** (2026-10-01). Expand into a spec before building.

## Problem

When painting from the guide, the last layers (Highlight, Bright Highlight) don't
match how a painter would place them: they are "too spread" — many small specks over
most of the mini instead of a few coherent patches nested inside the previous layer.
Photos were taken with a top light (not phone flash), so this is not the on-axis
lighting issue.

## What was measured

Probe on two painted Necron fixtures (`fixtures/necron-overlord`, `fixtures/necron-reanimator`),
5 bands, default coverage 33/27/20/13/7 %. "Top-2" = Highlight + Bright Highlight.

| Variant | Top-2 blobs (overlord / reanimator) | 32px tiles touched |
|---|---|---|
| Current (CLAHE 8×8, no smoothing) | 332 / 317 | 55/59 · 93/106 |
| Plain grey, no CLAHE | 287 / 289 | 46/59 · 87/106 |
| Grey + Gaussian σ=3 | 33 / 48 | 35/59 · 75/106 |

Edge highlights (luminance path, sensitivity 0.5): ~5.5 % of the mini, and
**30–42 % of edge pixels sit on the outer 2 px silhouette rim**.

## Causes (ranked)

1. **No spatial smoothing before rank banding.** `banding.band_light` ranks raw
   per-pixel luminance, so primer grain, glints and base texture become top-band
   specks. Gaussian blur fixes the specks (~10× fewer blobs) but melts fine detail
   (cables, spines) → use an edge-preserving filter (bilateral / guided).
2. **CLAHE with 8×8 tiles** (`lighting._clahe_gray`) equalises locally, so every
   tile gets "brightest" pixels — a secondary spreader.
3. **No nesting margin.** Layer k+1 is pixel-nested in layer k but never required to
   sit inside an *eroded* layer k, and there is no minimum blob size.
4. **The base eats the budget.** Rank banding fixes the area (~20 % of pixels in the
   top 2 bands); gravel/skull bases take a large share.
5. **Edge highlights trace the silhouette.** Light is 0 off-mask, so the gradient
   spikes at the outline (`edges.edge_mask`). The silhouette is where the surface
   turns away — painting it is the "outlined mini" mistake.

Related UI point: the Paint step "Result so far" image paints all bands ≥ k, so it
looks broader than the actual layer.

## Plan (one change at a time, measured before/after)

1. Edge-preserving smoothing of the light field before banding (rank-safe: keeps the
   rank-based design).
2. Drop CLAHE or use much larger tiles.
3. Nested margin + minimum blob area for the top bands. Trade-off: real coverage %
   will differ from the requested % → show the real numbers.
4. Exclude the silhouette rim from the luminance edge mask.
5. Maybe: base as an automatic separate region / exclude option.

## Validation set

The Necron fixtures are **painted** (albedo confounds luminance). Validate on
**black-primed** minis — the app's design lane:

- `src/mini_highlight_advisor/data/samples/projects/rat-ogre_project.json`
- `user_data/projects/rat-ogre1`, `user_data/projects/rat-ogres-4`

Metrics: top-band blob count, tiles touched, edge-pixel share on the rim, plus
side-by-side visual review.
