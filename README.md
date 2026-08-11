# Mini Highlight Advisor

Upload a photo of a **primed miniature** and get a paint-by-layer highlight plan:
where to highlight, which of your palette colours per layer, roughly how far each
band goes — as a painted preview on your own photo, a written layer guide, and a
**paint-along step sequence** (one set of images per layer, dark to light).

No existing tool does geometry-driven highlight overlays on your own photo:
text-only guides (PaintGuide.ai), hallucinated renders (AI-MiniPainter), and
finished-job scorers (MyMiniScore) all solve a different problem.

## Scope (v1)

- **Primed / zenithal-primed (monochrome) minis.** A primed model is already a
  shading map, so the tool reads highlight relief from the photo's own
  **luminance** (CLAHE-enhanced grayscale). Painted/coloured minis are future
  work — luminance there conflates dark paint with shadow.
- **Manual regions.** Lasso areas (armour / blade / robe / skin) and give each
  its own editable palette + coverage; "Whole mini" owns whatever you don't
  lasso. Region *outlines* are fixed once drawn (delete + redraw to reshape) —
  growing a region with extra strokes is on the roadmap.

## How it works

```
upload → mask (alpha fast-path, else depth fallback)
       → luminance light map
       → draw regions (optional); "Whole mini" owns the rest
       → per-region editable palette + coverage (recipe/default suggest, you tweak;
         revisit any region to change its colours or coverage)
       → coverage-controlled curved banding (dark→light) per region
       → combined painted preview + per-region paint-along step images
```

## Install & run

```bash
python -m venv .venv
.venv\Scripts\activate            # Windows (use source .venv/bin/activate on *nix)
pip install -r requirements.txt
streamlit run app.py
```

First run downloads the depth model only if your upload has no alpha channel
(a background-removed PNG skips it and is fastest).

## Paint-along steps

For an N-layer plan you get, per layer:

- **Where to paint** — the zone for this layer in a bright marker (always
  visible, even for dark paints).
- **Apply across** — that zone in the actual paint colour.
- **Ends up here** — the slice that stays this colour after you highlight over it.

## Development

- Source: `src/mini_highlight_advisor/` — see `CLAUDE.md` for the module map and
  conventions.
- Tests: `.venv/Scripts/python -m pytest`
- Design specs and implementation plans live in `docs/superpowers/`.

## Roadmap

Grow-a-region (additive lasso) · SAM-based masks · coloured-mini support · PDF export.
