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

**Result: PENDING** — run it on the `skaven-hero` fixture pair. GOOD = big blobs land on real parts
(blade, robe, limb, base, head) with sensible boundaries → regions can be SAM-assisted. BAD = noise
confetti / one blob eats the whole figure / boundaries ignore the sculpt → regions must be fully
manual. Result decides the region-feature design.

Run:
```
.venv/Scripts/python spikes/sam_spike.py fixtures/skaven-hero/primed.png
# denser grid = more/finer masks but slower on CPU:
.venv/Scripts/python spikes/sam_spike.py fixtures/skaven-hero/primed.png --points-per-side 24
```
First run downloads the SAM checkpoint (`facebook/sam-vit-base`, ~375MB) to the HF cache. Output:
`spikes/out/<name>_sam_overlay.png`.

## Environment

CPU-only PyTorch + transformers + opencv + matplotlib, in `.venv` (Python 3.11).
First depth run downloads the model (~100MB for Small) to the HF cache.
