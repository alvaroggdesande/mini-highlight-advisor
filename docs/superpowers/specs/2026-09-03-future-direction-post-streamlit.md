# Future Direction & Life After Streamlit

**Date:** 2026-09-03
**Status:** Vision / discussion doc — NOT a spec, NOT a commitment. Read before scoping any
"where next" work. Captures a founder-honest steer from the 2026-09-03 session.

## The honest framing (user's own words)

- **No grand plan.** "A bit of everything, no plan." The goal is not a product roadmap or a
  monetized launch. It is a good tool that a few people enjoy.
- **The real near-term need is *sharing for feedback*.** "It would be great to have some
  feedback from some friends first, and I cannot share the Streamlit one." Everything about
  "more users" and "post-Streamlit" is downstream of this one concrete blocker.
- **Skeptical of fuzzy advice.** LLM-style coaching that says "sales down 20%, fix it" is
  useless. Any feedback feature must be *specific, numeric, prescriptive* — or it is noise.
- **Unconvinced by the coloured-mini hype** — correctly (see below).

## Decision 1 — Coloured-mini is DE-PRIORITISED (correcting the roadmap's hype)

The prior roadmap tagged coloured-mini as "highest value." That label is a **market/funnel
argument only**: the tool works on primed/monochrome minis (luminance *is* the shading
signal), but most people photograph *painted / in-progress* minis, so "primed only" turns
most first-time users away. Removing that wall widens the funnel.

**But it does not serve this project's actual goals:**

- Not chasing a mass market ("no plan").
- Welded to the **heavy PS path** — tripod, 6–8 shots, torch sidecar, 445 MB checkpoint.
  Maximum friction; the opposite of "share with a friend."
- The user's own use is primed minis, where the light path already works.

**Verdict:** coloured-mini stays parked. It only earns "highest value" under a
widen-to-mass-market goal we do not have. Revisit only if friend feedback specifically
demands painted-mini input *and* the PS friction has been reduced.

## Decision 2 — The user-benefit frontier is a MEASURED coaching loop (not an LLM)

Chosen direction: **close the loop** — turn the one-shot planner into something that follows
the painter through the job. Two slices, in order:

### Slice 1 — Value/contrast coaching (cheap, no new capture, no LLM)

The tool already computes every region's banded value structure. It can therefore *critique
by measurement*, and — crucially — **name the exact next paint from the user's palette**:

> ❌ Fuzz: "Increase contrast on the cloak."
> ✅ Measured: "Cloak runs value **22% → 51%** (29% spread). Reads flat below ~40% at arm's
> length. Take the top highlight to ~70% — that's **Ulthuan Grey**, not the **Fenrisian
> Grey** you're on. One more layer."

Substance is arithmetic on data the tool already has (band values + `matching.py` to name the
paint). An LLM, if used at all, only smooths phrasing — never invents the numbers. **This is
the feature's whole reason to exist and the answer to the "LLM advice isn't actionable"
objection: it is a ruler, not a pundit.**

Likely inputs already present: per-region band values (`banding.py`), palette + nearest-paint
(`palette.py` / `collection.py` / `matching.py`). New work: a "does this plan read?" analyzer
(value spread, adjacent-band gaps, edge-vs-body separation) + prescriptive copy that cites a
target value and the paint that reaches it.

### Slice 2 — WIP comparison (the sticky version)

Photograph the half-painted mini; sample actual per-region values; compare to plan targets:

> "Your cloak's brightest paint is sitting at **48%**. The plan wanted **70%**. Go two layers
> lighter."

Actionable because it is *the user's own pixels vs. a numeric target, with the next paint
named*. This is what makes a painter return mid-project instead of using the tool once — the
one thing the tool cannot do today (it is one-shot). Non-PS, reuses the existing capture +
region + value machinery.

**Design rule for both slices:** every piece of advice must carry (a) a measured current
value, (b) a target value with a reason, (c) a concrete next action naming a real paint.
No advice that fails all three ships.

## Decision 3 — "Post-Streamlit" is an OPTION unlocked by feedback, not a rewrite we owe

The strategic asset is already in place: the **engine is UI-agnostic**
(`src/mini_highlight_advisor/`); Streamlit is only `app.py` + `ui/`. So the arc is staged and
each stage is only funded by the previous one paying off:

1. **Now (days) — make it shareable.** The real blocker behind "I can't share the Streamlit
   one." Cheapest path: **Streamlit Community Cloud** (free public deploy, optionally
   password-gated) or a small hosted container. Zero architecture change. This is the only
   step with a committed rationale today (friend feedback).
   - Caveat to check: the PS path needs a 445 MB torch sidecar + checkpoint — it will **not**
     run on Community Cloud. The shareable build is the **Path L (luminance) app only**; PS
     stays a local/desktop capability. Good — Path L is the low-friction path anyway.
2. **Later (only if friends validate it) — API seam.** Put a thin FastAPI layer in front of
   the existing engine; Streamlit demotes to the internal dev/preview harness.
3. **Eventually (only if it takes off) — mobile-first front-end.** Capture *and* painting both
   happen phone-in-hand at the desk, so mobile is the product, not an afterthought. React/PWA.

Streamlit's real ceilings (recorded so the trigger to leave is legible): single-user sessions,
weak on mobile, full-rerun model, no real auth/persistence/multi-user, torch is desktop-only.
None of these bite until there are actual users — so none justify work before step 1 proves
demand.

## What this means for the immediate queue

- **Ship now:** the UX legibility cluster (shrink-on-draw bug, existing-region borders while
  drawing, selected-region on the colour tab, export-as-image). Small, both paths, high daily
  usability — and export-as-image is a prerequisite for sharing results.
- **Then:** make the Path-L app public (Decision 3, step 1) so friends can try it.
- **Then:** Slice 1 value/contrast coaching (Decision 2) — the measured, paint-naming critic.
- **Parked:** coloured-mini funnel; API/mobile rewrite; PS relight polish.

## Open questions (for the user, not blockers)

- Public vs. password-gated for the friends build? (Password-gated keeps it private-ish while
  still shareable by URL.)
- Is WIP comparison (Slice 2) worth the extra capture step, or is the pre-paint critic
  (Slice 1) enough to feel like a coach?

## Addendum (2026-09-03, same session) — painted-mini is ONE axis, PS value ranking, capture regimes

### Decisions 1 & 2 are two ends of one axis, not separate topics

"Painted mini" spans a cheap end and an expensive end. Splitting them is what reconciles
"de-prioritise coloured-mini" with "the WIP loop is worth it":

- **Cheap end — WIP progress check (PROMOTED).** You already lassoed the region; you measure a
  *relative* value inside it against the plan's target. Albedo is ~constant within one material
  region, so this is largely **Path-L-doable — no PS.** This is the cheap cousin of coloured-mini
  and it is worth building.
- **Expensive end — coloured-mini planning from scratch (STILL PARKED).** Arbitrary paint, no
  plan, must separate albedo from shading → PS → high friction.
- **Open feasibility risk:** *absolute* checks ("you're at 48%, target 70%") under arbitrary
  albedo may not survive; *relative* checks (did the highlight get enough lighter than the
  midtone) are safer. Resolve empirically, not on the whiteboard (see the capture protocol).

### PS value ranking — what heavy PS is actually for

Relight is the *weak* reason to run PS (the painter holds the real 3D mini and can tilt it under
a lamp better than any recovered normal map). PS earns its friction only through **geometry a
painter cannot eyeball**, ranked by prize:

1. **Auto-regions from normal discontinuities** — part seams *are* normal discontinuities; kills
   the manual-lasso chore. Biggest prize if it holds up.
2. **Correct cavity / AO recess shades** — true occlusion, not "darkest luminance quantile".
3. **Geometric edge highlights** — true ridges, not "brightest quantile" (often not the edge).
4. **NMM / OSL reflection placement** — reflection vectors need normals.
5. **Coloured-mini via albedo** — parked.

Light-only's legitimate lane is **value placement on well-lit primed minis** — real and useful.
Its ceiling is geometry (1–4) and colour. Only PS lifts that ceiling.

### Three capture regimes (do NOT conflate "multi-angle" with PS)

- **Single photo, Path L** — cheapest; value placement on primed minis; guesses geometry, fails
  on colour.
- **Multi-angle, Path L each** — cheap breadth (front/back/side; `feat/multi-angle-view` already
  merged); still guesses geometry, does not lift the ceiling.
- **PS multi-shot** — same pose, *moved light*, 6–8 frames → true normals + albedo. The only path
  to prizes 1–5. (A turntable does NOT work: rotating the subject keeps lighting constant relative
  to it and fails the lighting-variation gate. Fix the mini and camera; move the light.)

### NMM / OSL status (the user is right — both unfinished)

- **NMM** is a rough v1: stripe bug fixed, but the reflection environment is a single **vertical
  gradient** — correct for one lassoed metal region, wrong whole-mini. Reworking toward
  per-feature reflection is open and needs normals (PS).
- **OSL** is not started — but has a **cheap Path-L slice**: photograph the mini lit from the glow
  direction and tint the affected bands (no PS). The PS reflection-vector version is the
  "correct placement" upgrade, not a prerequisite.

### The move that settles this: empirical dogfooding

All of the above is theory until real minis are shot and scored. See
`2026-09-03-ps-capture-and-evaluation-protocol.md`. Shoot minis across the three regimes, score
capture quality against the `ps_tool` gates, run the PS-vs-luminance comparison, and let the
evidence re-prioritise — instead of ranking features on a whiteboard.
