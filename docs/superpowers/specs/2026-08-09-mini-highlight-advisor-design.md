# Mini Highlight Advisor — Design Spec

**Date:** 2026-08-09
**Status:** Approved (design), spike pending

## 1. Problem

Miniature painters struggle to know **where** to place highlights, **which** of their 4-5 paint
colors to use for each layer, and **how far** each color should extend before the next layer
begins. Highlighting is fundamentally about simulating light hitting a 3D surface (the hobby's
"zenithal" mental model: light from directly above, brightest on top-most surfaces).

The goal: upload a photo of a miniature and get back **two outputs**:

1. An **annotated overlay** — the user's actual photo with highlight zones drawn on it, banded
   into paint layers, colored with the user's palette.
2. A **written layer-by-layer guide** — per region: which paints, in what order, with technique
   notes.

## 2. Market gap (why this is worth building)

Existing tools do adjacent things but **not** this:

| Tool | Does | Doesn't |
|------|------|---------|
| PaintGuide.ai | Text step-by-step guide, maps to user's paint collection, PDF | No overlay on the user's actual photo |
| AI-MiniPainter | Generates a hallucinated fully-painted render | Doesn't say where/which/how-far; invents a look |
| MyMiniScore | Scores/critiques a finished paint job | Backward-looking, not a how-to |

The novel piece is the **geometry-driven overlay**: taking the user's real photo, computing where
light falls, banding it into layers, mapping to the user's palette, and drawing it on the photo.
No known tool does this.

## 3. Key architectural decision: region-centric

The unit of work is **not the whole image** — it is the **region**. Different materials need
different treatment:

- NMM (non-metallic metal) blade → long smooth gradient, many bands, hard reflection points
- Robe fold → 3-4 soft layers
- Face → subtle work in specific zones
- Small detail → 2 layers

So the mini is decomposed into regions (armour, blade, cloth, skin, leather, details), and each
region is processed independently with its own technique, band count, and palette.

## 4. Pipeline

```
Photo ─┬─> [Depth + Normal estimation]  (whole image, once)
       └─> [Region detection]  → list of regions, each with a mask + material type
                                        │
        for each region ↓
   ┌───────────────────────────────────────────────────────────┐
   │  • technique      (NMM / edge-highlight / layer-blend / …)  │ ← LLM picks per material
   │  • band count     (blade=6, robe=4, detail=2, …)            │ ← recommended per region
   │  • palette        (suggested colors, user-editable)         │ ← suggest-then-edit
   │  • light intensity from normals → quantize into bands       │ ← the geometry core
   │  • recolor bands + label                                    │
   └───────────────────────────────────────────────────────────┘
                                        │
        ┌───────────────────────────────┴─────────────────┐
   [Composite overlay image]                    [LLM writes step-by-step text guide]
```

## 5. Modules (clean boundaries, UI-agnostic core)

The core is fully independent of the UI so a future web app reuses everything but the presentation
layer.

- `lighting.py` — depth/normals → per-pixel light intensity. Pure CV, unit-testable on synthetic
  inputs. `light_intensity(normals, light_dir) -> intensity_map`.
- `regions.py` — `detect_regions(image) -> [Region]`. Region = mask + material label + suggested
  technique/band-count/palette. **This is the swap point:** v1 = LLM rough regions; v2 = SAM masks
  labeled by LLM. Nothing downstream changes when swapped.
- `banding.py` — `band(intensity, n_bands, curve) -> band_map`. Splits intensity into discrete
  zones; band boundaries follow a per-technique curve (NMM weights more bands near the bright end;
  edge-highlight uses a thin top band). Pure function.
- `palette.py` — suggest / store / edit colors; map palette entries to bands (darkest = shadow,
  brightest = edge highlight).
- `overlay.py` — draw banded zones (semi-transparent) + a legend chip per band onto the photo.
- `guide.py` — LLM prompt → written per-region instructions.
- UI layer (Streamlit) — thin orchestration + display only.

## 6. The lighting core (novel + riskiest) — REVISED after spike

**Spike finding (2026-08-09):** the originally-planned "monocular depth → surface normals →
light" pipeline does **not** work on its own. Depth-Anything V2 (Small) captures figure-ground and
gross form well, but *smooths away the fine relief* (armour edges, pauldron tops, helmet crest)
that painters actually highlight — estimated normals varied only at the silhouette. See
`spikes/depth_spike.py` and the finding in `spikes/README.md`.

**Refined approach that passed the spike:** **depth for the MASK, image luminance for the RELIEF.**
A grey/black-primed mini photographed under normal light is itself a shading map — pixel brightness
≈ how much light each surface catches. So:

1. **Mask.** Run depth estimation, Otsu-threshold + largest-connected-component → clean figure mask.
2. **Light map from luminance.** Convert the photo to grayscale, apply CLAHE (local contrast) so
   fine relief survives, contrast-stretch *within the mask*. This yields a per-pixel 0-1 light map
   with real per-detail structure. (For a zenithal-primed model this map is essentially the answer.)
3. **Band** the light map into N bands (N = region's recommended layer count), boundaries per a
   per-technique curve (not necessarily equal-width). **Confirmed necessary by the preview spike
   (2026-08-09):** equal-width bands over-allocate the top layers (one mini put ~34% of its surface
   in "Highlight" and ~16% in "Edge Highlight" — far too much for sharp top edges). Upper bands must
   be made progressively thinner (gamma/quantile curve), and coverage may need per-region
   normalization.
4. **Map bands → palette.** Darkest = shadow paint, brightest = edge highlight.
5. **Draw.** Recolor each band's pixels semi-transparently onto the photo + legend chip: paint name
   + coverage note ("top ~15% / raised edges only").

Trustworthy because it reads the light the sculpt *actually* catches, rather than guessing geometry
from a single view. Aligns with real workflow: highlights are planned at the primed/undercoat stage.

**Important scope consequence:** luminance-as-relief assumes a roughly **monochrome primed/undercoat
surface**. On an already-multicolour-basecoated mini, luminance conflates dark paint with shadow.
v1 therefore targets the **primed/zenithal-primed stage**. Colored-mini support (depth mask +
high-pass local-contrast, or per-region normalization) is deferred to v2.

## 7. Decisions locked in

- **Palette input:** suggest (LLM) then user-edit.
- **Band count:** recommended per-region by the tool (material-aware), user-editable.
- **Region detection:** LLM rough regions in v1, with a manual-correction fallback in the UI;
  SAM upgrade in v2 behind the `detect_regions` interface.
- **Delivery:** local Streamlit first (user knows it); UI-agnostic core keeps the web-app path open.

## 8. Phasing

- **v1 (MVP, a few evenings):** single photo → global depth/normals → LLM approximate regions →
  per-region banding → overlay + text guide → Streamlit UI with editable palette.
- **v2 (a week-ish):** SAM masks; per-material band curves tuned; manual region correction;
  save/load palettes; PDF export (overlay + guide).
- **v3 (real web app, optional):** hosting, phone-friendly upload, accounts, paint-brand database +
  cross-brand substitution, multi-angle photos.

## 9. Risks & de-risking

- **Depth/normals may be noisy on small, oddly-lit phone photos.** → **RESOLVED by spike
  (2026-08-09).** Confirmed the naive depth→normals→light approach fails (too smooth); pivoted to
  depth-mask + luminance-relief, which passed on a real primed-mini photo. See Section 6.
- **Luminance-relief only valid on monochrome primed surfaces.** → v1 scoped to the primed/undercoat
  stage (Section 6); colored-mini support deferred to v2.
- **Multi-pose check (2026-08-09):** 3 of 4 test minis passed including dynamic/angled poses
  (approach is pose-independent). The failure was input-quality: underexposed black primer + a
  background-removal artifact baked into the alpha. → (a) **own the masking** — treat user
  background removal as a fast path only, with our own segmentation/depth fallback; (b) **guide
  input quality** — reasonably exposed, ideally zenithal-primed photo; (c) scenic bases read as
  their own bright region → reinforces region-centric processing (base ≠ model).
- **LLM region masks are rough in v1.** → Accepted; manual override + SAM upgrade path.
- **Color accuracy under camera lighting.** → v1 guides *placement* only; exact color-matching is
  explicitly out of scope for v1.
- **2D overlay guiding a 3D object.** → Framed as *guidance*, not paint-by-numbers; encourage a
  zenithal-primed reference photo (which also gives the cleanest luminance signal).

## 10. Testing strategy

- `lighting.py` / `banding.py` are pure functions → unit-test on synthetic shapes (a rendered
  sphere has a known light gradient; assert monotonic falloff and correct band boundaries).
- `regions.py` / `guide.py` (LLM) and `overlay.py` → snapshot / eyeball on a small fixture set of
  real mini photos.

## 11. Out of scope (v1)

- Exact paint color matching / cross-brand substitution (v2/v3).
- Multi-angle / 3D reconstruction.
- Accounts, hosting, mobile capture (v3).
- Weathering, OSL, freehand guidance (future).
