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

## Environment

CPU-only PyTorch + transformers + opencv + matplotlib, in `.venv` (Python 3.11).
First depth run downloads the model (~100MB for Small) to the HF cache.
