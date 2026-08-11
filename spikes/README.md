# Spikes — de-risking experiments

Throwaway experiments to validate the risky core before building. Not production code.

## 1. `depth_spike.py` — monocular depth → normals → zenithal light

**Question:** can a monocular depth model give a light map that lands on real highlight spots?

**Result: NO on its own.** Depth-Anything V2 (Small) separates figure from background well and gets
the gross form, but *smooths away the fine relief* — estimated normals varied only at the
silhouette, so the light/band tiles lit up the outer edge, not the internal detail (helmet top,
pauldron tops, chest plate). Naive depth→normals→light is not trustworthy for per-detail placement.

Run:
```
python spikes/depth_spike.py spikes/input/<mini>.jpg --bands 5
```

## 2. `shading_spike.py` — depth for mask + image luminance for relief

**Question:** does reading relief from the photo's own brightness recover the fine detail?

**Result: YES (on a primed mini).** Using depth only to build a clean figure mask, then computing
the light map from CLAHE-enhanced luminance inside the mask, recovers all the fine relief. Bands
overlaid on the mini track the actual armour geometry (recesses → dark bands, raised plates →
bright bands). This is the approach v1 will build on.

**Caveat:** luminance-as-relief assumes a roughly monochrome primed/undercoat surface. On a
multicolour-basecoated mini, dark paint reads as shadow. v1 targets the primed/zenithal-primed
stage; colored-mini support is a v2 concern.

Run:
```
python spikes/shading_spike.py spikes/input/<mini>.jpg --bands 5 --model small
# --model base|large for a higher-detail (heavier) depth model
```

## 3. Multi-mini / multi-pose check (background-removed PNGs)

`shading_spike.py` extended to mask from the **alpha channel** when the input is a background-removed
PNG (no depth needed). Tested on 3 extra black/grey-primed minis in varied poses.

**Result: 3 of 4 minis pass, including dynamic/angled poses** → the luminance-relief approach is
pose-independent. The 4th (`...14.04.40__2...`) fails for **input-quality** reasons, not method:
- background removal baked in a large fully-opaque grey smudge that isn't part of the model
  (raising `--alpha-thresh` to 240 did not drop it → alpha ≈ 255 on the smudge);
- the mini is black-primed and underexposed, so luminance has almost no tonal range to read.

**Design consequences:**
- Own the masking; don't trust user background removal (fast path when clean, fallback otherwise).
- Guide input quality: reasonably exposed, ideally zenithal-primed photo.
- Scenic bases read as bright texture and get their own bands → reinforces the region-centric design
  (base vs model should be separate regions).

Run:
```
python spikes/shading_spike.py spikes/input/<mini>.png --bands 5 --alpha-thresh 200
```

## 4. Paint-labelled preview — "what the tool would output"

`preview_spike.py` turns the abstract bands into a painter-facing mockup: mask + luminance light
→ band → paint each band with a **real named paint colour** → render `original | painted preview |
legend`. The legend shows, per layer (dark→light): swatch, role (Shadow/Base/Midtone/Highlight/
Edge Highlight), paint name, coverage %, and a plain-English note.

**Result: the palette + legend concept works and reads convincingly** across all three working
minis (static Infinity figure, crouched creature, leaping creature w/ scenic base). Recesses land
in shadow, raised plates rise through the mids, sharp top edges get the edge-highlight colour.

**Validated learning — banding needs a per-technique curve, not equal width.** With equal-width
intensity bands the Infinity mini put ~34% of its surface in the Highlight band and ~16% in Edge
Highlight — too much for a realistic "sharp edges only" top layer. The grey creatures banded more
naturally (~14% edge). Confirms the spec's plan to make band boundaries follow a per-technique
curve (upper bands thinner), and to consider per-region normalization.

Run:
```
python spikes/preview_spike.py spikes/input/<mini>.jpg --bands 5
python spikes/preview_spike.py spikes/input/<mini>.png --bands 5 --alpha-thresh 200
python spikes/preview_spike.py <img> --palette "Abaddon Black:#14151a,Leadbelcher:#4b4f54,Dawnstone:#71767b,Administratum Grey:#a9adb0,White Scar:#eef0f2"
```

## 5. `sam_spike.py` — SAM automatic region segmentation on a primed mini

**Question:** does Segment Anything (a **local** CV model — no API/no network) carve a
*monochrome primed* mini into usable region blobs (blade / robe / arm / base), or does the lack of
colour starve it? This is the one open unknown in the offline **"SAM + manual labelling"** region
plan (see `docs/superpowers/specs/2026-08-09-roadmap-and-idea-assessment.md`): SAM proposes masks
locally, the user names them.

**Result: NO — SAM cannot carve internal regions on a monochrome mini (2026-08-09).**
- *auto mode*: found only the bright detached blade + the base; the whole body was starved.
- *prompt mode* (grey primer, CLAHE-enhanced, 4 body clicks): **every** body click — torso, arm,
  head, robe — grew the **same single whole-figure mask**. The base separated (detached), the
  blade separated (detached + not clicked); nothing internal did.
- Root cause: **SAM segments whole *objects*, not sub-parts of one object.** A mini is one
  connected object; robe/arm/cloak/skin share no object boundary. On a monochrome primer there are
  no colour/material cues to override that. The grey-primer input was GOOD → this is **fundamental,
  not input quality**. Contrast/exposure/grid-density do not fix it.

**Consequence:** SAM gives us only what depth/alpha already give (whole silhouette) plus detached
objects (blade, base). Internal material regions must come from another route: (a) **manual
brush/lasso** (works on any photo, zero ML), (b) depth-curvature part segmentation (research), or
(c) interactive positive+negative-point refinement (fiddly, uncertain, needs a UI). **Region
auto-detect is off the table.**

Run:
```
.venv/Scripts/python spikes/sam_spike.py fixtures/skaven-hero/primed.png
# denser grid = more/finer masks but slower on CPU:
.venv/Scripts/python spikes/sam_spike.py fixtures/skaven-hero/primed.png --points-per-side 24
```
First run downloads the SAM checkpoint (`facebook/sam-vit-base`, ~375MB) to the HF cache. Output:
`spikes/out/<name>_sam_overlay.png`.

## 6. `canvas_spike.py` — streamlit-drawable-canvas as the manual region lasso

**Question:** does `streamlit-drawable-canvas` run on this repo's pinned Streamlit, and can we
read a drawn lasso's vertices back as a point list? This gates the drawing-widget choice for the
manual-region feature (`docs/superpowers/plans/2026-08-11-manual-region-lasso.md`); the
polygon-by-click `streamlit-image-coordinates` is the fallback.

**Result: PASS *with a shim* (2026-08-11).** The import gate passed (drawable-canvas 0.9.3 installs
with no version conflict and imports cleanly), but at **runtime** `st_canvas` crashed:
`AttributeError: module 'streamlit.elements.image' has no attribute 'image_to_url'`. Newer Streamlit
(1.61.1) moved that private helper to `streamlit.elements.lib.image_utils.image_to_url` and changed
its 2nd arg from `width: int` to a `layout_config` object (only `.width` is read). Fix = an ~8-line
compat shim (`_patch_image_to_url`, in both this spike and `app.py`) that re-exposes an adapter;
`streamlit` is pinned to `1.61.*` in `requirements.txt` so an upgrade can't silently re-break it.
With the shim, freehand (`freedraw`) drawing works and the traced stroke comes back as
`json_data["objects"][-1]["path"]` (SVG segments — segment endpoint = its last two numbers), which
`app.py`'s `_points_from_object` parses. **Fallback if the shim ever breaks:** swap to
`streamlit-image-coordinates` polygon-by-click (no design change downstream).

Run:
```
streamlit run spikes/canvas_spike.py
```

## Environment

CPU-only PyTorch + transformers + opencv + matplotlib, in `.venv` (Python 3.11).
First depth run downloads the model (~100MB for Small) to the HF cache.
