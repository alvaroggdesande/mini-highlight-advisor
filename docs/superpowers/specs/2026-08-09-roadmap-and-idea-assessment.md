# Mini Highlight Advisor — Roadmap & Idea Assessment

**Date:** 2026-08-09
**Status:** Strategic assessment (not a feature spec). Read this before scoping the next feature.

## Purpose

Capture an honest triage of a batch of feature ideas: how hard each is, where the
value is, which ones are wrong or traps, and — most importantly — **which ideas
unstick others**. The user's steer: deprioritise external polish, focus on the
*enablers*.

## Current v1 state (the constraints everything is judged against)

- Whole mini = **one region**.
- **Primed / monochrome minis only** — luminance *is* the shading signal.
- Pipeline: luminance → CLAHE light map → quantile bands (3–5, default 5) →
  palette mapping → overlay + per-band paint-along step images.
- Streamlit UI, editable 5-slot palette (Citadel greys by default).
- The engine's core premise: **read the light the sculpt actually catches.**
  Any idea that requires *inventing* light the photo doesn't contain fights this
  premise and is therefore expensive.

## The 11 ideas — effort / value / verdict

| # | Idea | Effort | Value | Verdict |
|---|------|--------|-------|---------|
| 11 | PDF export | Low | High | ✅ but **deferred** — easy anytime, unsticks nothing. Do it in a slow month. |
| 6 | Adjustable coverage % per band | Low | High | ✅ `band_light` already takes a coverage list; expose it. Fixes a known flaw (top bands over-allocated). |
| 4 | "Enumerate my colors" / own-palette input | Low–Med | High | ✅ **Enabler.** Unsticks #3 and #5. |
| 3 | Paint-mixing + water suggestions | Med | High | ✅ "own 3 paints, want 5 bands → mix X+Y." Depends on #4. |
| 2 | Paint consistency / thin-with-water notes | Low | Med | 🟡 Generic advice; only meaningful bundled with techniques. |
| 9 | Techniques (layering / OSL / NMM / edge) | Split | Mixed | 🟡 See detailed notes — parts cheap, parts a different engine. |
| 7 | More than 5 bands | Low | Low–Med | ⚠️ Raise cap to ~7, **default stays 5**. 10 = false precision. |
| 5 | Multi-brand paint DB (Citadel/Vallejo/…) | Med–High | High | 🟡 Data/ops burden. After #4; seed from an existing dataset. |
| 1 | Per-material regions (detect / choose / split) | High | High | 🟡 **Hub enabler**, but hard on primed minis. Painted reference helps (below). |
| 10 | Colored-mini support | High | Highest | 🟡 Biggest market unlock, hardest core change. Needs a spike. |
| 8 | 3–4 photos → 3D model | Very High | Low–Med | ❌ Reframed → **multiple independent 2D photos** (agreed). |

## Challenges & reframes (the honest pushback)

- **#8 — full 3D photogrammetry killed.** Research-grade from casual phone photos,
  and the painter is already holding the real 3D model. **Reframed and agreed:**
  accept a few photos (front / back / side), run the existing 2D pipeline on each
  independently → per-angle plans. Low–Med effort, delivers the real need.
- **#7 — 10 bands is false precision.** Luminance on a phone photo can't resolve 10
  *meaningful* bands; smooth 10-step blends are an airbrush/glaze skill. Cap ~7,
  **default 5**.
- **#3 — pigment mixing isn't linear RGB.** Physical mixing ≠ additive colour. Fine
  for *guidance* ("roughly equal parts X and Y"); don't render a naive RGB average
  as accurate.

## Key insights from the discussion (the parts that changed the picture)

### Painted reference image → the region enabler
Official product pages (and the user's own references) almost always show a
**painted** version. Priming removes exactly the colour/texture cues needed to tell
armour from cloth, which is why region detection on a primed mini is hard. A painted
reference restores them. Two very different uses:

- **Region *labeling* (cheap — do this first):** feed the LLM *both* the primed photo
  and the painted reference. The reference disambiguates what the primer hides
  ("that bump is a red pauldron; that's a metal blade"), improving region
  identification and palette suggestion. **No pixel alignment required.**
- **Region *mask transfer* (hard — defer):** warping the reference's masks onto the
  user's photo needs image registration across different pose/lighting/instance.
  Expensive; not the starting point.

### OSL fits the engine via lighting, not invention
OSL (object-source lighting) would normally require *inventing* a light source the
photo lacks — which fights the core premise. **But** if the user photographs the
primed mini lit **from the OSL direction** (e.g. from below), the real light *is* the
OSL light and the luminance engine reads placement **for free**. So OSL =
**photography instruction + a colour tint** on the affected bands (the glow is
coloured). Cheap and premise-consistent.

### NMM is ~70% layering; the rest is invented
NMM approximates as an **extreme-contrast band curve** with strong darkest/lightest
points — the engine can do that part. What it *cannot* read is NMM's fake
horizon / reflected-ground — that is placed knowledge, not caught light. First
approximation is feasible; true NMM is not fully derivable.

### Edge highlighting is often region-separation, not "lightest light"
In practice edge highlights frequently exist to **separate adjacent regions**, and
aren't always the brightest value. Consequence: **edge-highlight quality is
downstream of regions (#1)** — it only becomes meaningful once regions exist.

## Dependency graph — what unsticks what

```
own-palette input (#4) ──┬──> paint-mixing suggestions (#3)
                         └──> multi-brand paint DB (#5)

painted-reference labeling ──┬──> per-material regions (#1)
                             └──> colored-mini understanding (#10)

per-material regions (#1) ──┬──> per-region techniques / band counts (#9)
                            ├──> edge-highlight-as-separation (#9)
                            └──> NMM / OSL placement (#9)
```

**The two true foundations are `own-palette input` and `region support` (bootstrapped
by the painted reference). Almost everything interesting hangs off those.**

## Prioritisation (enablers first, polish last)

1. **Own-palette input (#4)** — foundational; unsticks #3 and #5. Cheapest big lever.
2. **Painted-reference *labeling* + first-pass regions (#1)** — the hub. Start with
   LLM labeling from primed+painted images; manual region chooser before auto-detect.
3. **Coverage sliders (#6) + raise band cap to ~7 (#7)** — small, fixes a known flaw.
4. **Paint-mixing (#3) + consistency notes (#2) + technique band-curve presets +
   OSL-as-lighting** — the "your paints & techniques" arc, all downstream of 1–2.
5. **Colored-mini spike (#10)** — the big fork; decides the product's ceiling and
   whether deeper region investment pays off.
6. **Multi-photo (reframed #8)** — cheap breadth once the single-photo path is rich.

**Explicitly deferred / parked:**
- **PDF export (#11)** — easy anytime, unsticks nothing. Later.
- **3D photogrammetry (#8 original)** — killed; replaced by multi-2D-photo.
- **Region mask-transfer** and **true NMM horizon** — not derivable cheaply; revisit
  only if the labeling/approximation paths prove insufficient.

## Meta-decision on the table

Two strategic directions, can't do both at once:

- **Deepen the niche** — palette, mixing, coverage, techniques. Low risk, compounding,
  serves existing primed-mini painters.
- **Widen the funnel** — colored-mini (#10) + regions (#1). Higher risk, needs spikes,
  reaches the majority who photograph painted-in-progress minis.

Recommendation: do the **enabler arc (palette + reference-labeled regions)** first —
it serves the niche *and* de-risks the widen-the-funnel bet, because reference-labeling
and region support are prerequisites for colored-mini anyway.

## Decision addendum (2026-08-09, session 2)

**Locked: the tool stays OFFLINE / FREE. Region support = "SAM + manual".**

Clarified the SAM-vs-Claude confusion. The two halves of region support are solved by
different models:

- **Geometry ("where are the regions") → SAM** — a *local* CV model (same category as
  the depth model the app already runs). Offline, free per image, no API. Produces
  *unlabeled* blobs; it does not know what a "robe" is.
- **Semantics ("what is each blob") → a vision LLM (Claude)** — an *API* call: online,
  costs money per upload. The current app has **zero LLM in it** and we're keeping it
  that way for now.

**Chosen approach = B (SAM + manual):** SAM proposes region blobs locally; the *user*
names each blob and picks its palette (the painted reference helps the user decide,
but no automatic labeling). Auto-labeling with Claude (approach A) is deferred to a
future opt-in toggle — a small swap on top, not a rewrite.

**Remaining unknown → one spike.** SAM proposing blobs is the shared foundation under
both the offline and future-API versions, so it must be validated either way. The
only open question: **does SAM produce usable region blobs on a *monochrome primed*
mini, or does the lack of colour starve it?** De-risked by `spikes/sam_spike.py`
(spike #5) on the `skaven-hero` fixture pair.

**SPIKE RESULT (2026-08-09): NO — SAM regions are off the table.** SAM is an *object*
segmenter, not a *part* segmenter: every click on the body (torso/arm/head/robe) grew
the same whole-figure mask; only detached objects (blade, base) separated. The input
was a good grey-primer photo, so this is fundamental, not input quality. SAM gives us
only what depth/alpha already give (whole silhouette) + detached objects.

**Revised region plan:** internal regions require **manual brush/lasso** (works on any
photo, zero ML risk); SAM auto/assist is dropped. Because manual regions are now a
non-trivial UI project, the recommended next move is to **pivot to the other
foundation first — own-palette input (#4)** — which has zero region risk, delivers
value immediately, and unsticks mixing (#3) + brand DB (#5). Manual-region support
becomes its own later design.

**Design note for the future manual-region feature — lasso precision vs edge-highlight
correctness.** A concern: a hand-drawn lasso won't be pixel-perfect. It doesn't need to
be. **The lasso only assigns *which paints/technique* apply to an area; it does NOT
place the highlights — luminance does.** Each band (including the edge highlight) is the
brightest-quantile of luminance *within* the region, i.e. it reads the light the sculpt
actually catches. So edge highlights *inside* a region are robust to a loose lasso. The
only sensitivity is at **region seams**: a lasso that bleeds into a neighbour can put one
region's edge-highlight colour on the other's bright rim. Mitigations: (a) add/subtract
refine brush; (b) edge-snap the lasso to the sculpt's own luminance/depth edge; (c)
exclusive pixel assignment + feathered boundaries. Note the seam is *semantically* where
a separating edge highlight belongs (edge-highlight-as-region-separation), so it is a
feature to exploit, not only a defect to fix.

## Addendum (2026-08-14): capture-reality correction, relief-recovery research, refactoring merge

Three updates fold in here: (1) a correction to the assumed capture conditions, (2) a
deep-research pass on whether the "blocked" colored-mini / relief-recovery problem is
now solvable with newer tech, and (3) refactoring priorities merged into the roadmap.

### Correction to "current v1 state" — the lighting premise is weaker than written

The original doc assumed a zenithal-primed mini (a baked-in top-down shading gradient
the luminance engine reads). **Reality: minis are black or grey primed — NOT zenithal —
and photographed with ON-AXIS / FRONTAL FLASH** (light co-located with the lens). This is
the flat-lighting *worst case*: co-axial light suppresses form and cast shadows, so a
single photo carries very little directional shading to read. Consequence: the engine is
not merely "limited to primed minis" — on frontal flash it is fighting physics even on a
grey primer. This reframes the whole colored-mini fork: the block is **partly physical
(missing shadow signal), not only algorithmic (albedo/shadow confusion).**

### Relief-recovery research verdict — no single-image model unblocks this

Deep-research pass (2026-08-14, 22 sources, adversarially verified). Headline: **no
single-image method, however new, defeats the bottleneck, because the information isn't
in the frontal-flash photo.** Remove albedo perfectly and the shading layer is still
near-flat. The two real unblocks both change the *input*, not the model.

- **Single-image AI (baseline only, low confidence).** StableNormal (SIGGRAPH Asia 2024,
  arXiv:2406.16864) is SOTA and estimates normals *directly* (YOSO + SG-DRN refinement),
  avoiding the depth→differentiate smoothing that killed `depth_spike`. But it is trained
  on scene-scale data, unvalidated on 28-32mm objects, and cannot invent shadow signal
  frontal flash removed. Intrinsic decomposition (Colorful Diffuse Intrinsic, ACM TOG
  2024) separates albedo from shading but outputs NO geometry, and the shading it returns
  is the near-flat one. Neither solves the core physics.
- **Cheapest real win — change the capture, not the code.** Move the light OFF-axis / add
  a second light so form shadows return. Nearly free (a photography instruction), and it
  restores signal for both the existing luminance engine and any normal estimator. Fits
  the existing OSL insight ("photograph under the light you want").
- **The genuine colored-mini unblock — phone photometric stereo (multi-shot).** PS
  recovers normals AND albedo *separately* by construction, so shape stops depending on
  paint colour — the real defeat of dark albedo. Phone-feasible variants: SDM-UniPS
  (uncalibrated, no known light directions, CVPR 2023), near-field point-light PS
  (LUCES-MV, validated at 30-40cm phone distance, 2024), DMDPS (phone display as
  programmable light, 2025). Caveats from verification: none tested on black primer under
  true frontal flash; lab "0.2mm" figures don't transfer to handheld; single-shot
  colour-multiplexed PS was REFUTED. Needs a 3-4 shot protocol; black primer stays
  low-SNR.
- **STL path (unchanged).** Where the mesh exists, render curvature / ambient-occlusion /
  cavity maps directly — sidesteps recovery. Pose tools (MegaPose, FoundationPose) exist
  for photo-overlay; registration-free "guidance on a render" is the cheap path.
- **Polarization (not a bet).** Albedo-independent orientation cue (Poppy, 2026 preprint;
  cross-polar) but weakest exactly on dark/low-polarization surfaces — i.e. black primer —
  and needs a polarization sensor.
- **Prior art:** BrushForge (brushforgeapp.com) — active hobby-painting app, do a
  competitive look.

### Revised colored-mini fork — three de-risked bets, not one monolith

The old doc listed colored-mini (#10) as a single "highest value / highest risk /
needs a spike" fork. Replace with, in order:

1. **Per-region luminance normalization** — cheapest; reuses existing manual regions.
   Inside a single-material region albedo is ~constant, so luminance variation there *is*
   relief. Extends the engine to colored minis region-by-region for near-free. Fails on
   dark albedo (no dynamic range) and multi-colour-within-one-region.
2. **Off-axis capture guidance** — free; the highest-ROI change overall. Fixes the
   frontal-flash physics problem for both primed and colored minis.
3. **Phone photometric-stereo spike** — the real widen-the-funnel bet; multi-shot,
   separates normals from albedo. This, not a bigger depth/normal model, is the path.
4. *(optional, low confidence)* StableNormal direct-normal baseline; STL-render path for
   the print segment.

The prior "widen the funnel needs a colored-mini spike" framing is corrected: the fork is
reopened by **changing capture**, not by a new model. The depth-refuted spike closed the
single-image door for good.

### Refactoring priorities (merged in — these are engineering, not features)

- **Tier 0a — Drop torch + transformers.** The DPT depth model (~200MB download, drags in
  torch) exists in `masking.py` ONLY as a mask fallback when the upload lacks alpha. That
  is a depth transformer used to get a silhouette. Replace with: require
  background-removed PNGs (already the README "fast path"), or `rembg`, or OpenCV GrabCut
  (zero new deps). Deletes the biggest dependency, the silent first-run download, and an
  untested path. Highest leverage, lowest risk.
- **Tier 0b — Relief-confidence gate.** Per-region luminance variance / gradient energy;
  warn + auto-cap band count when a region is too flat to justify N bands. Turns the
  core "manufactured precision" weakness (rank banding always emits N crisp bands even on
  flat relief) into a feature. Note this weakness is *worse* under frontal flash.
- **Tier 2 (do only if still building on the UI / hosting):** cross-platform fonts
  (`overlay.py` Windows-hardcoded paths); unpin Streamlit + retire the `image_to_url`
  monkey-patch; decompose the 506-line `app.py` (extract palette/region render fns, tame
  the 40+ session keys); name the magic mask constants (-1 off-mask, -2 unmask owner).

### Consolidated prioritisation (features + refactors, tiers not a strict queue)

- **Tier 0 (foundational refactors, before new features):** drop torch/transformers;
  relief-confidence gate.
- **Tier 1 (enablers, already shipped):** own-palette input (#4); manual regions (#1)
  — note regions double as the cheap colored-mini unblock.
- **Tier 2 (cheap polish / known flaws):** coverage sliders + band cap (#6/#7, shipped);
  cross-platform fonts; Streamlit unpin; app.py decomposition — UI-conditional.
- **Tier 3 (colored-mini fork):** per-region luminance norm → off-axis capture guidance →
  phone-PS spike → (optional) StableNormal baseline / STL-render path.
- **Deferred (unchanged):** PDF export (#11); multi-photo breadth (#8 reframe — note
  phone-PS is the higher-value version of "multiple photos"); region mask-transfer; true
  NMM horizon.

**Strategic note:** the research does not reopen the "widen the funnel" bet cheaply. Every
path past the primed-monochrome niche needs either a capture-behaviour change (off-axis
light, multi-shot PS) or an STL. If the goal is a low-friction phone tool for the mass of
painters, that friction is real and unavoidable — weigh it against extracting the strongest
albedo-independent asset the repo already has (the palette matcher + mix advisor) as a
standalone tool.

### Implementation note (2026-08-15) — Tier 3 Step 2 shipped as guidance; auto-detector refuted

Executed **Tier 3 Step 2 (off-axis capture guidance)** on `feat/capture-relief-check`.
Scope landed *smaller* than first proposed, for an evidence-backed reason.

**What was proposed and dropped:** an "albedo-blind relief-energy" addition to
`input_check._check_lighting` — high-pass residual std inside the mask — so the lighting
check would catch flat frontal-flash on *colored* minis (where raw tonal spread is
inflated by paint albedo and gives a false pass). A quick synthetic probe refuted it. On
matched cases (200×200, single-image):

| case | should | grey spread | hp_std | blur-spread |
|---|---|---|---|---|
| flat-flash **colored** (albedo blocks, no shading) | warn | 180 | 33.7 | 179.5 |
| raking **colored** (albedo blocks × shading gradient) | pass | 192 | 22.5 | 179.3 |

The bad case and the good case are indistinguishable on spread and blur-spread, and rank
**backwards** on high-pass energy (a hard albedo edge emits more high-pass than smooth
form shading). This is the intrinsic-image ambiguity again: **no cheap single-image
statistic separates flat-flash from good raking light once paint is on.** Same wall the
depth spike hit — confirms single-image is closed and only multi-shot PS (Step 3) reopens it.

**What shipped instead (zero-regression):**
- Sharpened the frontal-flash line in `SHOOTING_GUIDE` + `docs/photo-guide.md` to name the
  mechanism (fills recesses / erases shadows) and call it the #1 cause of a flat result.
- New `PAINTED_CAPTURE_NOTE` surfaced in the app photo-quality panel: scopes the automatic
  lighting check to **primed** minis and puts capture discipline on the user for painted ones.
- **Left `_check_lighting` logic untouched** — it already works correctly on primed minis
  (probe: uniform grey spread 0 → warn; gradient spread 230 → pass); the false-pass only
  exists in colored mode, which isn't a supported path yet, and can't be fixed cheaply.

Next in the sequence: **Step 1 (per-region luminance normalization)**, then gate on whether
to fund the **Step 3 phone-PS spike**.
