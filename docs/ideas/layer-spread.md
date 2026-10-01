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

6. **The cork painting holder is in the mask** (found 2026-10-01 on the rat-ogre
   photos). Background removal keeps the holder (3–24 % of the alpha mask per angle).
   Its bright, textured, saturated surface competes for the top bands like a base does,
   only worse. With CLAHE removed, 70–88 % of top-band pixels landed on cork/base.

Related UI point: the Paint step "Result so far" image paints all bands ≥ k, so it
looks broader than the actual layer.

## Rat-ogre validation run (2026-10-01)

10 black-primed angles in `fixtures/rat-ogre/angle_01..10.png` (local, gitignored;
`angle_03/05/10` are the bundled samples `ratogre_1/2/3`). Holder removed by an
approximate orange-hue mask (probe only, not product code). Top-2 = Highlight + Bright
Highlight. Median over the 10 angles (min–max):

| Variant | Top-2 blobs | Coherent (≥30 px) | Tiles touched % | Nest | Base share % | Rim share % | IoU @0.66× |
|---|---|---|---|---|---|---|---|
| Current (CLAHE 8×8) | 547 (381–1411) | 0.86 | 84 | 0.41 | 22 | 37 (25–57) | 0.68 |
| Plain grey | 563 | 0.87 | 82 | 0.54 | **36** | 41 | 0.73 |
| CLAHE 2×2 | 556 | 0.87 | 83 | 0.55 | 39 | 40 | 0.72 |
| Grey + Gaussian σ=3 | 46 | 0.99 | 57 | 0.89 | 38 | 41 | 0.77 |
| Grey + bilateral ×1 | 340 | 0.91 | 77 | 0.61 | 35 | 41 | 0.76 |
| Grey + bilateral ×3 | 102 (59–171) | 0.98 | 68 | 0.72 | 34 | 44 | 0.78 |

Metric definitions:

- **Top-2 blobs**: 8-connected components of bands ≥ n−2.
- **Coherent**: share of top-2 pixels in blobs ≥ 30 px.
- **Tiles touched**: 32 px tiles containing any top-2 pixel ÷ tiles containing the mask.
- **Nest**: share of the top band inside the top-2 region eroded by 2 px.
- **Base share**: top-2 pixels in the bottom 15 % of mask rows (rough proxy).
- **Rim share**: edge-mask pixels within 2 px of the silhouette (distance transform).
- **IoU @0.66×**: top-2 overlap between full-res and 0.66×-res analysis. A real sculpt
  feature survives a resolution change; pixel noise does not.

Findings:

1. **Smoothing confirmed.** Bilateral ×3 cuts specks ~5× and raises nesting
   0.41 → 0.72 while keeping more detail than a Gaussian blur, which scores best on
   numbers but visibly smears. A single bilateral pass is too weak.
2. **CLAHE was hiding the base/holder problem.** Removing it alone raises the base
   share from 22 % to 36 %, because the glossy base rim and leftover cork win the global
   ranking. So "drop CLAHE" must not ship before base/holder exclusion.
3. **The silhouette rim is unaffected by smoothing** (37–44 % median, up to 64 %). It
   needs its own fix.
4. Painted-fixture numbers (Necron) and primed numbers (rat-ogre) agree in direction.

Caveat: this probe banded the **whole mini as one region**. In the app, banding runs
independently inside each lasso region (skin, armour, weapon, base). A base drawn as its
own region can't take the skin's highlight budget, so holder/base exclusion may come
largely through the region model. Spread must be judged **per region**.

## Next evaluation: per-region blind review (not an answer key)

Rejected: having the user lasso "highlight"/"bright" answer-key regions. That misuses
regions (they are parts, each with its own shadow → highlight layers) and choosing
layers is the app's job, not the user's.

Instead:

1. The user saves 1–2 projects with normal part regions (e.g. `angle_03`, `angle_10`:
   skin / armour / weapon, base as its own region).
2. The probe reads each project's regions (`rings` + width/height in the manifest,
   rasterised via `polygon_to_mask`) and bands each region under each variant
   (current, bilateral ×3, no-CLAHE, …).
3. It renders blind sheets: per region, the variants side by side, labels hidden, order
   shuffled. The user picks the one closest to how they'd paint it.
4. Per-region metrics (blobs, nest, rim, IoU) support the picks; they don't replace them.

Probe script: `spikes/layer_spread_probe.py` (whole-mini version; needs the per-region
extension above).

## Plan (one change at a time, measured before/after) — reordered 2026-10-01

1. **Exclude holder + base from the ranking pool** (promoted from "maybe"). Options:
   auto-detect the base/holder as its own region, or a user "exclude" lasso. Banding
   then ranks only the model.
2. Edge-preserving smoothing of the light field before banding (bilateral ×3 or a
   guided filter; rank-safe, keeps the rank-based design).
3. Drop CLAHE or use much larger tiles. Only after 1, see finding 2.
4. Nested margin + minimum blob area for the top bands. Trade-off: real coverage %
   will differ from the requested % → show the real numbers.
5. Exclude the silhouette rim from the luminance edge mask.

## Validation set

The Necron fixtures are **painted** (albedo confounds luminance). Validate on
**black-primed** minis — the app's design lane:

- `fixtures/rat-ogre/angle_01..10.png` (10 angles, RGBA, local only), the primary set
- `src/mini_highlight_advisor/data/samples/photos/ratogre_1..3.png` (same as angles 03/05/10)
- `src/mini_highlight_advisor/data/samples/projects/rat-ogre_project.json`
- `user_data/projects/rat-ogre1`, `user_data/projects/rat-ogres-4`

Metrics: as defined in the validation run above, computed per region, plus the
blind per-region review.
