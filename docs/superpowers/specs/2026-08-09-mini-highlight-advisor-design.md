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

## 6. The lighting core (novel + riskiest)

Per region:

1. **Normals → intensity.** `intensity = max(0, dot(normal, light_dir))`, `light_dir` pointing
   down-from-above (zenithal). Optionally blend a weaker fill light so shapes don't go pure-black.
   Yields a smooth 0-1 map.
2. **Band the intensity** into N bands (N = region's recommended layer count), boundaries per a
   per-technique curve (not necessarily equal-width).
3. **Map bands → palette.** Darkest = shadow paint, brightest = edge highlight.
4. **Draw.** Recolor each band's pixels semi-transparently + legend chip: paint name + coverage
   note ("top ~15% / raised edges only").

Trustworthy because it is the same physics as zenithal priming — a technique painters already
trust their eyes on; we compute it instead of spray-can-guessing.

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

- **Depth/normals may be noisy on small, oddly-lit phone photos.** → **De-risk FIRST** with a
  throwaway spike: feed one real mini photo through a monocular depth model (Depth-Anything),
  derive normals, eyeball the intensity map. If it is garbage on minis, rethink before building
  anything else. This is the make-or-break test — hence it is task #1.
- **LLM region masks are rough in v1.** → Accepted; manual override + SAM upgrade path.
- **Color accuracy under camera lighting.** → v1 guides *placement* only; exact color-matching is
  explicitly out of scope for v1.
- **2D overlay guiding a 3D object.** → Framed as *guidance*, not paint-by-numbers; encourage a
  zenithal-primed reference photo.

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
