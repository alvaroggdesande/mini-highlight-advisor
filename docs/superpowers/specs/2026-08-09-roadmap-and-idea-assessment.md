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
(spike #5) on the `skaven-hero` fixture pair. Everything region-related waits on that
result.
