# Per-Region Luminance Normalization — Design

**Date:** 2026-08-15
**Status:** Approved design (brainstorm 2026-08-15). Ready for an implementation plan.
**Roadmap ref:** `docs/superpowers/specs/2026-08-09-roadmap-and-idea-assessment.md` — "Revised
colored-mini fork", bet #1 (Tier 3 Step 1). Follows Step 2 (capture guidance, PR #18).

## Purpose

The engine reads **luminance as the shading signal**. Today the luminance stretch is computed
**once over the whole mini**, which is correct only when albedo is constant — i.e. a primed
monochrome mini. On a **colored / part-painted** mini, a single global stretch mixes albedo
across materials: a bright region and a dark region share one scale, so the dark region's own
relief is compressed into a narrow slice and its highlights are crushed.

The fix is cheap and reuses infrastructure the repo already has (manual regions): inside a
single-material region albedo is ~constant, so **luminance variation within that region is
relief**. Compute the stretch **per region** and each region reads its own form independent of
the others' colour. This is the lowest-cost, lowest-risk step of the colored-mini fork — it
does not need a new model or a capture change.

**Explicitly opt-in and experimental.** It ships behind a default-off toggle; the primed path
is unchanged. It has a known, named failure — **dark albedo with no dynamic range** — which we
handle by graceful degradation rather than pretending to solve (that needs multi-shot
photometric stereo, Step 3).

## Scope (locked via brainstorm 2026-08-15)

- **Trigger: user toggle, opt-in.** A "Colored / painted mini (experimental)" checkbox,
  default **off**. Off ⇒ today's behavior, byte-for-byte. On ⇒ per-region normalization.
  No auto-detection of "is this colored" — the toggle is explicit.
- **Dark-albedo guard included.** Per-region normalization without a guard would stretch a
  no-relief dark region's noise into confident-looking fake bands — the "manufactured
  precision" weakness, in exactly the path most prone to it. A dynamic-range floor turns that
  named failure into an honest warning + band cap.
- **Both the "Whole mini" leftover region and lassoed regions** normalize to themselves when
  the toggle is on. (The leftover region is still a single routing bucket; if it spans several
  colours the result is best-effort — see Non-goals.)
- **YAGNI / Non-goals:** no auto colored-vs-primed detection; no multi-colour-*within*-one-region
  handling (roadmap defers it — the user is expected to lasso per material); no change to edge
  or step-image rendering beyond consuming the new per-region light; no new dependencies.

## Architecture

Keep the split of responsibility the repo already follows: measurement/engine in the core
modules, rendering-only in `app.py`.

### `lighting.py` — split the two jobs `luminance_light` does today

`luminance_light` currently (a) CLAHE-enhances the grayscale and (b) percentile-stretches to
[0,1] inside a mask. Split internally, keeping the public function identical:

```python
def _clahe_gray(rgb, clip_limit=3.0) -> np.ndarray:      # enhanced gray, global CLAHE (unchanged)
def _stretch(gray, mask) -> np.ndarray:                  # p2..p98 within mask -> [0,1], off-mask 0
def luminance_light(rgb, mask, clip_limit=3.0):          # = _stretch(_clahe_gray(rgb, clip_limit), mask)
```

Global CLAHE is kept global on purpose — it is tile-local contrast enhancement, not the
albedo-mixing step. The albedo mixing is entirely in the **stretch**, which is what we move
per-region.

New helper for the per-region path, returning the flat-region signal alongside the light:

```python
@dataclass
class LocalLight:
    light: np.ndarray      # region stretched to its own [0,1]; off-(sub)mask = 0
    dyn_range: float       # p98 - p2 of the region's raw CLAHE gray, 0..255 (pre-stretch)
    flat: bool             # dyn_range < FLAT_DYNRANGE_MIN

def local_luminance_light(gray, sub_mask) -> LocalLight
```

`gray` is the shared `_clahe_gray(rgb)` computed once by the caller (no per-region CLAHE recompute).

### `banding.py` — dark-albedo floor constant

Add a tuned constant next to `_MIN_SPREAD_PER_BAND` / `FLAT_SPREAD_MAX`:

```python
# Raw CLAHE-gray p2..p98 range (0-255) a region needs before per-region stretching is
# trustworthy. Below this the region is dark/low-albedo with no relief dynamic range;
# stretching it only amplifies sensor noise into fake bands, so we cap to 1 band and warn.
FLAT_DYNRANGE_MIN = 25   # starting value; tuned against the synthetic fixtures
```

(Exact value tuned empirically against the fixtures in the plan; documented as tunable, like the
existing thresholds.)

### `pipeline.py` — thread the toggle and the guard

- `analyze_regions(..., per_region_norm: bool = False)` — new trailing kwarg, default off.
- When **off**: unchanged — one global `light`, each `plan_region` slices it. (Regression lock.)
- When **on**: compute `gray = _clahe_gray(rgb)` once. For each region, compute
  `ll = local_luminance_light(gray, sub_mask)` and pass `ll.light` as that region's light. If
  `ll.flat`, force the region to a single band and set a new flag on `RegionPlan`.
- `plan_region` gains a `flat_albedo: bool = False` parameter (or receives the `LocalLight`).
  When flat, it behaves like a hard relief cap to 1 band, but flagged distinctly so the UI can
  give the dark-albedo message rather than the generic flat-relief one.
- `RegionPlan` gains `flat_albedo: bool = False` (reuse the existing `capped`/`requested_bands`
  fields for the band-count story; `flat_albedo` only distinguishes *why* for the message).

The global (`per_region_norm=False`) branch does not touch any of the new code paths.

### `app.py` — one checkbox, rendering only

- A `st.checkbox("Colored / painted mini (experimental)", value=False, key=...)` in the mini tab,
  near the region controls.
- Its value is passed as `per_region_norm` into `analyze_regions`.
- When on, per-region plans that come back `flat_albedo=True` render a short inline warning
  ("This region is too dark / low-contrast to read relief — try a paler basecoat or stronger
  raking light"). Reuse the existing per-region cap-notice rendering; only the message text
  differs.
- When on, the primed-only framing of `PAINTED_CAPTURE_NOTE` may be softened (it already tells
  painted-mini users capture discipline is on them — consistent, no contradiction).

## Data flow (toggle ON)

```
rgb ──► _clahe_gray(rgb) ──► gray (computed once)
                               │
        per region sub_mask ──►│──► local_luminance_light(gray, sub_mask)
                               │        ├─ dyn_range ≥ floor ─► _stretch ─► region light ─► band_light ─► bands
                               │        └─ dyn_range < floor  ─► flat=True ─► 1 band + dark-albedo warning
```

## Testing (TDD; synthetic fixtures, the Step-2 probe precedent)

No real colored-mini photo is required to ship (same constraint as Step 2 — the user has no
minis on hand). Deterministic synthetic fixtures give ground truth the global path cannot fake:

1. **Recovery:** a two-region synthetic (bright albedo block + dark albedo block, each carrying
   the *same* shading gradient). Assert the dark region's within-region band split is correct
   under `per_region_norm=True` but crushed/degenerate under the global path — proving per-region
   norm recovers relief the global stretch loses.
2. **Dark-albedo guard fires:** a flat dark region (albedo below floor, negligible gradient)
   ⇒ `flat_albedo=True`, capped to 1 band. And a dark region *with* real gradient but raw range
   above the floor ⇒ NOT flagged (guard doesn't over-trigger).
3. **Regression lock:** `per_region_norm=False` ⇒ `analyze_regions` output identical to current
   `main` on the known-good `fixtures/skaven-hero/primed.png` (bands array equality).
4. **Purity:** `local_luminance_light` and `_stretch`/`_clahe_gray` unit-tested directly (shape,
   off-mask zeros, dyn_range math, flat threshold boundary).

Plus one manual eyeball: wire the toggle, load a real painted photo in the app, confirm the
per-region result is visibly better than global and the dark-albedo warning reads sensibly.

## Risks & limitations (recorded honestly)

- **Dark albedo is not solved, only degraded gracefully.** A dark region with genuine but
  low-dynamic-range relief is indistinguishable from a flat one in a single image — the guard
  will (correctly, conservatively) cap it. Recovering it needs Step 3 (phone photometric stereo).
- **Multi-colour within one region** still mixes albedo — the user must lasso per material. The
  "Whole mini" leftover bucket is the main place this bites; documented as best-effort.
- **Threshold tuning** (`FLAT_DYNRANGE_MIN`) is empirical and set against synthetic fixtures; it
  may need revisiting once real painted photos are tested. Documented as tunable, not load-bearing.

## Out of scope / next in sequence

After this ships, the roadmap gate is whether to fund the **Step 3 phone photometric-stereo
spike** — the only path that actually separates normals from albedo and reopens dark albedo.
