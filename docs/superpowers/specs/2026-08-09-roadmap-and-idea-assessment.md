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

## Session 3 addendum (2026-08-13) — three new ideas + colored-mini reframe

Context: the whole "enabler arc" is shipped (own-palette, manual regions, Region UX
v2/v3, coverage sliders, band-cap 7, mix advisor, palette-matcher v2, edge highlights).
What remains is the big fork (colored-mini) plus polish. Three ideas raised this
session, captured here for later refinement — **none committed yet**.

### Idea A — Save/load "mini projects" (persistence layer)

**What:** load a few photos of a specific miniature, save the whole working state, and
reload it in a later session. Today everything is in-session only; the plan is lost on
refresh. Directly serves the documented prep-vs-paint workflow (the highlight map is
*"stared at for days while painting"*) — persistence is what makes the tool usable
across the days you actually paint.

**How to store it (offline/free lock, line 138, decides this):**
- **V1 = filesystem, no DB.** A `minis/` folder; each mini = a subfolder with source
  photo(s) + a `manifest.json` (palette, coverage, band count, regions as **polygon
  coordinates**, not baked masks — compact, resolution-independent).
- SQLite only if hundreds of minis + search is ever needed. Cloud "mini DB" only when
  this becomes a hosted multi-user web app — then it's just *where* the manifest lives,
  not *what* it is. The core is already "UI-agnostic" (CLAUDE.md), so the manifest is
  the portable unit; the cloud port is a later swap.

**Key design point:** define the container as **"a mini = N photos, each with its own
plan,"** even if V1 fills only one photo. That schema is *also* the natural home for
multi-angle (#8 reframed) and colored-mini. Building a one-photo-only save format now
would force a rewrite when multi-angle lands.

**Ordering / blockers:** no ML risk, no premise fight; independent of the spike.
Highest *immediate personal* value, but it is product *maturity*, not product *ceiling*.
Soft dependency: its container schema should be fixed *before* multi-angle is built so
the two share one format.

### Idea B — Photo-quality guide + live input check

**What:** (1) a short written shooting guide (3/4 raking light from one direction; avoid
on-axis flash which flattens form; fill the frame; neutral background; sharp focus), and
(2) a small in-app **input-quality check** that warns when luminance variance is too low
(no form to read), when the image is clipped over/under-exposed, or resolution is too
small. Input quality caps output quality because the engine reads *caught light* — a
flat-lit photo starves the exact signal it needs.

**Cheap empirical path:** shoot the *same* mini ~5 ways, run each through the pipeline,
eyeball which bands come out cleanest — this *produces* the guide instead of guessing it,
and doubles as fixtures for the input-check thresholds.

**Ordering / blockers:** cheapest, compounding, protects every future plan (including
colored-mini). No blockers. Good "slow moment" work or a warm-up before the spike.

### Idea C — Colored-mini spike, reframed (supersedes the #10 framing above)

**Vision confirmed:** upload a WIP mini (basecoated / washed) → the app advises how to
*continue* (next highlight placement + colours). This is the **market** bet (WIP photos
are the common case) vs. the **niche** (primer-stage photos, today's tool).

**Not a new output format:** it's the *same* overlay + step-images + palette, with the
darkest band anchored to the *existing basecoat* instead of primer grey, advising upward.

**De-risking insight — we already own a form sensor.** The app already runs a **depth
model** (`masking.py` fallback). Depth = pure geometry = form, blind to paint colour.
Luminance is used today only because it's a sharper read of catchable light *on primer*;
on a colored mini where luminance is corrupted by paint, **depth becomes the clean form
signal.** So the spike's first, nearly-free test is: swap the shading map from luminance
to depth on a colored fixture and see if the bands still read.

**Full outcome decision tree (what the throwaway spike buys — days, not weeks):**

| Outcome | Meaning | Cost to act |
|---|---|---|
| 1. Depth / lightness-high-pass cleanly recovers form on painted surfaces | Full colored-mini engine viable — big unlock | Medium (reuses depth + band engine) |
| 2. Works only on *flat-basecoated* regions, not already-shaded ones | Ship "basecoat support" — manual regions already deliver ~80%; market widens primed→basecoated without solving decomposition | **Low** |
| 3. Depth rescues it where luminance fails | Depth-driven banding path, on infra already shipped | Medium, low novelty risk |
| 4. Signal gone on genuinely shaded minis; nothing cheap recovers it | Stay in niche, ceiling known | Zero (bought certainty) |

Outcomes 2 and 3 are both likely and both cheap; even 4 is a win (stops a multi-week
wall). No version of the spike loses more than a couple of days. **This is why the spike
comes before any engine commitment.**

### First-pass ordering (to refine)

1. **Idea B (photo guide + input check)** — cheapest, unblocks nothing but protects
   everything; good warm-up.
2. **Idea C spike** — highest information, decides the ceiling, throwaway cost. Do before
   any colored-mini engine work.
3. **Idea A (persistence)** — high personal value; fix its container schema to be
   multi-photo so multi-angle and colored-mini reuse it. Sequence after the spike verdict
   only because the verdict may add fields to the manifest (e.g. per-photo base-paint
   state); the *skeleton* schema can be designed independently.
4. **Multi-angle (#8 reframed)** — cheap breadth once A's container exists.

### Session 3b — colored-mini vision refined (research)

**Core-value reframe (the unifying thesis).** The product is *one* thing: **upload a
photo → get layer-by-layer highlight PLACEMENT; stop guessing.** Primed / WIP / finished
are just different **inputs** to that; techniques are different **output styles** of it.
This reframes the whole roadmap around placement, not around "colored support" per se.
Differentiator: generic painting guides are everywhere but non-spatial ("highlight the
edges", someone else's mini). Nobody delivers *per-photo, layer-by-layer placement on the
model in your hand.* That's the moat; the target user is the beginner who has neither
technique nor good guessing (advanced painters guess well already).

**Code finding that de-risks the spike.** `masking.py` already runs
`Depth-Anything-V2-Small` on every no-alpha image, but only thresholds it to a silhouette
— the raw **depth values (pure form, blind to paint) are discarded.** `banding.py` is
**source-agnostic** (bands whatever light field it's given, per region). So "use depth
instead of luminance as the shading map on a colored mini" = feed an array already in
memory into a function that already exists. The spike tests *result quality*, not
buildability.

**Per-question verdicts:**
- **Two modes?** UI yes (pick primed vs painted → selects the form-extractor); engine no
  — one pipeline, swappable form source (luminance for primer, depth for painted).
- **Basecoats → regions?** Plausibly **yes**, and it's the inverse of the SAM-on-primer
  failure: basecoated minis *have* hue boundaries, so cheap classical clustering
  (Lab k-means / SLIC superpixels, both in the shipped opencv, no LLM) can propose
  regions. WIP input is *better* for auto-regions than primer. Worth a spike sub-test.
- **More than basecoats → critique placement ("your highlight is wrong")?** Hardest,
  speculative. Possible in principle via depth-form-peaks vs luminance-bright-peaks
  disagreement, but fragile. **Phase-3, high-risk; do not promise.** Spike tells us if the
  signal is even clean enough to attempt.
- **Finished mini ('eavy metal) input?** Two real uses: (a) reference to label *your*
  mini's regions (already the roadmap's painted-reference labeling); (b) extract the
  *pros'* highlight map from the finished mini itself — works well per-region because
  finished highlights are deliberately high-contrast, so reading bright quantiles recovers
  expert placement. A legit teaching feature, possibly easier than WIP.
- **Techniques?** Regions are the unlock. Each technique = placement curve + tint + paint
  choice: drybrush = top bands on high-pass texture within region ✅; TMM = metallic paint
  + edge highlight ✅; NMM = extreme-contrast curve ✅ but fake reflections not derivable
  ⚠️; OSL = photograph-from-glow-direction + band tint ✅. "Free" for what the engine can
  *read*; not derivable for what a human *invents*.
