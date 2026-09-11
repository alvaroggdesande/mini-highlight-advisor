# Mini Highlight Advisor — Geometry Acquisition & Usability Direction

**Date:** 2026-09-11
**Status:** Strategic assessment + recommended first bet (not a feature spec). Read this
before scoping the next geometry-side feature. Lineage: continues
`2026-08-09-roadmap-and-idea-assessment.md` (esp. the 2026-08-14 and 2026-08-24 addenda).

## Why this doc exists

A session raised three ideas for using 3D models with the tool:

1. **Synthetic ground-truth** — render minis from known STLs, run our geometry
   pipeline, compare recovered relief to the true surface (a dev/validation harness).
2. **Bring-your-own-STL** — let users who 3D-print their minis import the mesh and get
   *exact* geometry, skipping recovery entirely.
3. **Phone photogrammetry / Gaussian-splat** — capture the real mini's geometry from a
   casual phone orbit as an alternative to photometric stereo (PS).

All three collapse onto **one** question, which is also the tool's central usability
wall: **how do we get *faithful* surface relief with *less friction* — and does newer
(2025-2026) technology change the answer?**

The steer for this doc (2026-09-11):
- **Focus:** the newer-tech opportunity, with an eye on *reliable relief without the PS
  ceremony*. End-to-end UX flow is explicitly out of scope here.
- **Audience:** me now, shareable with other painters later (friction matters for that
  later step, but isn't blocking today).
- **Constraints:** explore what's *useful* first; decide offline-vs-hosted and cost
  *afterwards*. The old "OFFLINE / FREE locked" rule is relaxed for this exploration.
- **Ambition:** rank the geometry-source paths, then recommend **one concrete first
  bet** to prototype next.

## The two axes everything is judged on

Every geometry source is scored on two axes, and our bar is unusual on the first one:

- **Faithfulness** — the relief must be *the real mini's* relief. This tool decides
  *where* highlights, cavity shades and edge highlights go on the physical mini in the
  user's hand. **Hallucinated or smoothed relief is actively harmful** — it places paint
  guidance in the wrong spot. "Looks like a great 3D asset" is *not* the bar; "matches
  the actual object sub-millimetre" is.
- **Friction** — the capture/processing ceremony. This is the named obstacle to the tool
  being usable and shareable. PS is maximal friction ("a lab protocol, not a desk-side
  flow": 6-8 tripod shots, a moved light, an external torch tool, a 445 MB checkpoint,
  re-import two PNGs).

The load-bearing design rule from 2026-08-24 still holds: **two input paths, always both
live.** Path L (single photo → luminance; cheap, default, no torch) and Path P
(multi-shot → PS → normal field; faithful, heavy). Any new geometry source is
**capability-gated** through the existing optional `normal_field=` seam
(`analyze_regions(normal_field=…)`) — present a normal field → richer geometry; absent →
Path L is byte-identical to today. **No rewrite is needed to add a new normal source.**
That seam is why the directions below are cheap to try.

## What "newer technology" actually changes (Sept 2026 investigation)

Three focused research passes (parallel, sourced, adversarially framed). Findings, with
confidence:

### 1. AI image/text → 3D mesh (Hunyuan3D 3.0, TRELLIS, Tripo, Rodin, Meshy) — REJECTED

**Not faithful. Confidence: HIGH.** These are *generative completions* conditioned on the
image, not measurements of the object. They reconstruct the visible silhouette well but
**hallucinate occluded/back regions, force symmetry, and smooth or invent fine relief**,
and they infer relief from *shading cues + learned priors* (so your phone lighting
changes the geometry). Best measured geometric fidelity to input (TRELLIS, CD×1000 ≈ 39.6
on GSO) is achieved *partly by leaning on priors/symmetry*, not by measuring your mini.
More photos help the *seen* surface only; unseen regions stay guesses (dense multi-view +
hallucination-aware methods need ~72 rendered views to enforce continuity). For a painting
guide, "always produces a confident, closed mesh" is precisely the failure mode.

- Cue3D (arXiv 2511.22121, Nov 2025); Dehallu3D (arXiv 2603.01601, 2026); "When Does An
  Extra View Help?" (arXiv 2608.08132, Aug 2026); Hunyuan3D 2.5 (arXiv 2506.16504) / 3.0
  (Tencent, 16 Sep 2025, hosted-only).
- *Gap:* no benchmark measures faithfulness on 28-32 mm minis specifically; the "will
  fail on minis" verdict is a well-supported extrapolation, not a direct measurement.

### 2. Phone-video Gaussian splatting / NeRF (2DGS, GOF, RaDe-GS, PGSR; KIRI/Polycam/Luma) — REJECTED as a relief source

**Lower capture friction, but geometry is systematically over-smoothed. Confidence: HIGH
on the smoothing.** Splats optimize an *appearance* loss, not a geometric one; extracted
normals over-smooth and distort curvature exactly in low-texture / uniformly-shaded
regions — which a **primed mini is** (low-texture + often glossy = near worst case, plus
SfM/COLMAP pose failures and floaters). Best explicit methods land ~0.7 mm Chamfer on
DTU-scale objects; on a 30 mm mini the sculpted relief we place highlights on is *at or
below* that error floor. The field's own framing: **MVS/splat = reliable global shape;
photometric stereo = high-frequency relief.** They are complements — the SOTA hybrids
literally use splat for global shape and *PS for the fine normals* (PS-GS, *Computers &
Graphics* 2026).

- RaDe-GS (arXiv 2406.01467); PGSR (arXiv 2406.06521); 2DGS (Huang 2024); PS-GS (2026).
- Capture friction: a phone orbit beats PS multi-shot. *Total-pipeline* friction is a
  wash (COLMAP + a ~20-30 min GS train + mesh extract + normal bake), and it yields the
  *wrong data type* (a smoothed mesh) vs PS's dense per-pixel normals.
- Consumer apps (KIRI Engine, Scaniverse, Polycam, Luma): none export per-pixel normals;
  you'd bake from a mesh that lacks the detail. KIRI (free, "Featureless Object Scan"
  mode) is the only one worth a *1-hour empirical sanity check* if we ever want to
  confirm the smoothing on our own mini — not a pipeline commitment.

### 3. Classic photogrammetry (RealityScan 2.1, Metashape, KIRI) — REJECTED for minis

**Wrong tool for our subject class. Confidence: HIGH on failure modes.** A mini's profile
— reflective, uniform black/grey primer (no texture to match), thin protruding parts
(weapons/antennae go edge-on), macro depth-of-field — is described in the small-object
photogrammetry literature as "close to as bad as it gets." Mitigations make it worse for
us: cross-polarization destroys the specular/albedo info; dulling spray ruins a *painted*
mini. Community signal: painters **print minis from STLs**, they don't photogrammetry
them. (No credible "I scanned my 28 mm mini" report surfaced — flagged.)

### 4. STL "bring-your-own" bake path — STRONG (the winner when it applies)

**Ground-truth relief, low friction. Confidence: HIGH on the bake; MEDIUM on
prevalence/registration.** If the user has the mesh, curvature / ambient-occlusion /
cavity / edge maps come *directly* from it — no recovery, no smoothing, exact by
construction. This is technically routine: Blender Cycles AO bake + the Geometry
"Pointiness" → colour-ramp trick for curvature/cavity (or a scriptable `trimesh`/`libigl`
pipeline). The painter ↔ 3D-print overlap is real and growing (MyMiniFactory, Patreon
sculptors shipping monthly packs, resin printing) — a meaningful subset of painters has
the *exact* STL of the mini in hand. **Registration can be sidestepped for v1:** let the user
rotate the STL to roughly match their photo (or pick a front/¾ preset) and show guidance
*on the render* — this removes the hardest CV problem and matches how painters already
think ("highlight this edge, shade this recess"). Full photo-overlay (FoundationPose /
MegaPose / manual 3-point drag) is later polish, not a v1 requirement.

- Blender baking docs; StraySpark curvature-in-Blender; FoundationPose (CVPR 2024,
  NVlabs) / MegaPose (2022) for the *later* overlay tier.
- *Bonus:* this path **is** idea #1 (synthetic ground truth). The same STL→relief bake
  gives a dev-side harness to validate PS *and* AI-normal outputs against exact geometry.

### 5. NEW LEVER — single-photo AI normal estimators (Lotus, Marigold-Normals, Metric3D v2)

**This is the genuinely new thing since the 2026-08-14 research** (which had only
StableNormal). A family of 2025-2026 monocular normal estimators now produce a per-pixel
normal field from **one photo**:

- **Lotus** (arXiv 2409.18124, ICLR 2025) — single-step deterministic diffusion,
  depth+normals, fast (good UX fit); **Lotus-2** (HF 2512.01030, late 2025) pushes SOTA.
- **Marigold-Normals v1.1** (prs-eth, checkpoint 2025-05-15) + an LCM fast variant.
- **Metric3D v2** (TPAMI 2024) — the *metric* normal model, 1st across 16+ benchmarks
  (if we later want scaled geometry, not just direction).
- **StableNormal** (SIGGRAPH Asia 2024) — the prior quality reference; **NormalCrafter**
  (arXiv 2504.11427, Apr 2025) — temporally-consistent normals from *video* if the user
  films a slow orbit.

**Why this matters for us:** it's a *single-photo* relief source that drops straight into
the existing `normal_field=` seam — the lowest possible capture friction (one photo, any
mini, no PS rig, no torch), directly attacking the #2 pain. **Caveat: fidelity on a tiny
matte-primer mini is unvalidated** — these are trained on scene-scale data; expect
faithful *directional* normals but soft fine relief, not PS/STL-grade ground truth.
Confidence: MEDIUM. This is exactly what a cheap spike should settle.

## Re-ranked geometry sources (for OUR bar)

| Source | Faithfulness | Friction | Applies when | Verdict |
|---|---|---|---|---|
| **STL bake** (Path S) | Ground truth | Low (Blender/trimesh bake; pose = rotate-to-match render) | User printed / has the STL | **Pursue** — winner when it applies; also = validation harness |
| **Single-photo AI normals** (Path N) | Medium (sharp, not exact — *unvalidated on minis*) | **Lowest** (1 photo) | Any mini, no STL, no PS rig | **Spike, then likely pursue** — the newer-tech usability lever |
| **Phone PS** (Path P, existing) | High | Medium-High (multi-shot + torch) | No STL; hard/dark/colored minis | Keep as the faithful fallback |
| **Single photo → luminance** (Path L, existing) | Low (flat under frontal flash) | Lowest | Everyday, primed | Keep as default/fast path |
| **Gaussian splat** | Low for relief (over-smoothed) | Wash | — | Reject as relief; coarse scaffold only |
| **AI image→3D** | Low (hallucinated) | Low | — | Reject |
| **Photogrammetry** | Low on primed/glossy | High + fragile | textured/matte/chunky only | Reject for minis |

**Key finding:** for our subject class, the two *new* things worth building both avoid the
recovery problem entirely or attack friction head-on — **use the exact mesh (Path S)** or
**collapse PS to one photo (Path N)**. Splat and AI-mesh both fail the faithfulness bar;
photogrammetry fails the subject class.

## The two directions worth pursuing

Both slot into the existing capability-gated `normal_field=` seam. Path L stays default
and byte-identical; neither touches the fast path.

- **Path S — STL import + mesh bake.** User imports the mini's STL → bake
  curvature/AO/cavity/edge maps (Blender headless or `trimesh`/`libigl`) → feed the
  derived normal/relief field through the existing seam. Highest faithfulness, low
  friction, self-contained, low technical risk. Serves the print-and-paint segment now
  and *doubles as the synthetic ground-truth validation harness* for every other
  geometry source (idea #1). Pose starts registration-light (rotate-to-match render).
- **Path N — single-photo AI normal field.** Run a monocular normal estimator
  (Lotus / Metric3D v2 / Marigold-Normals) on one photo → normal field → existing seam.
  Lowest friction of any faithful-ish path; works for any mini. **Fidelity on minis is
  the open risk** — settle it with the spike below before building.

**Explicitly NOT pursuing** (this doc closes the door, matching how the 2026-08-14 pass
closed single-image relief recovery): AI image→3D mesh, Gaussian-splat-as-relief, and
photogrammetry. All three fail our faithfulness bar for a painting guide.

## Recommended first bet — a near-zero-cost evaluation spike (assessment → first bet)

**Do the Path N fidelity spike first, because we already hold the ground truth.** We
don't need to build anything or capture anything new to decide whether the single-photo
normal path is real:

1. **We already have PS ground-truth.** The painted-mini validation run and the
   black-primer staircase left PS normal maps (and albedo) on disk:
   `spikes/phone_ps/data/painted_mini_out/` and the staircase outputs. These are
   *measured* normals of real minis — a ready-made reference.
2. **The spike:** run Lotus / Metric3D v2 / Marigold-Normals on the *single frontal
   frame* of those same minis. Two measurements:
   - **Quantitative:** angular error of the AI normal field vs the PS normal field
     (masked to the mini).
   - **The one that actually matters:** feed the AI normal field through
     `analyze_regions(normal_field=…)` and eyeball whether **edge-highlight and cavity/AO
     placement** matches the PS-based plan. Band *placement* is the product, not the raw
     normals — a normal field can be metrically loose and still place bands correctly (or
     be metrically OK and still misplace them).
3. **Decision gate:**
   - **Passes** → build **Path N**. Huge usability win: one photo, any mini, no PS
     ceremony, and the integration seam already exists. This is the direct answer to the
     #2/#4 steer.
   - **Fails** (soft relief loses the fine edges/cavities) → **Path S** becomes the
     primary new build (faithful for the print segment) and we keep PS as the hard-case
     fallback.

**Regardless of the spike outcome, Path S is worth building** — it is the highest-certainty
geometry source (ground truth, self-contained, low risk), it serves a real segment, and it
gives us the STL→relief validation harness that makes *all* future geometry work
measurable. The spike just decides whether Path N gets built *first* (if single-photo
relief is good enough to be the everyday low-friction path) or *later/never*.

**Why this order:** the spike is hours not days, spends no capture effort, uses data
already on disk, and directly answers the session's core question — *can newer tech give
reliable relief without the PS ceremony?* Everything else waits on that yes/no.

## Open questions — to determine later (deliberately deferred)

- **Cost / offline model.** Lotus / Marigold / Metric3D v2 run locally on a GPU or via
  hosted inference; STL bake is local Blender/`trimesh`. Per the steer, pick the cost
  model *after* the spike proves value. If Path N passes but needs a GPU the user lacks,
  a hosted normal-estimation step is the first place a paid/online dependency might enter
  — evaluate then.
- **STL registration.** Ship registration-light first (user rotates STL to match / preset
  angles, guidance on the render). Defer FoundationPose/MegaPose photo-overlay.
- **Albedo synergy.** PS already recovers albedo; a future combo (AI/STL normals +
  recovered or sampled albedo) could serve colored minis — out of scope here.
- **Empirical splat sanity check (optional, low priority).** One free KIRI Engine scan of
  a primed mini would confirm the over-smoothing verdict on our own object — a 1-hour
  test, not a commitment. Only if we ever doubt finding #2.

## Continuation pointer (start here next session)

1. Run the **Path N evaluation spike** using the existing `spikes/phone_ps/data/...`
   outputs as PS ground truth. Estimator shortlist: **Lotus** (fast, single-step) and
   **Metric3D v2** (metric); Marigold-Normals as a third. Integration point:
   `analyze_regions(normal_field=…)`. Judge on **band placement**, not raw normal error.

   **On-disk ground-truth pairs (verified present 2026-09-11)** — each `<name>.out/`
   (or `<name>_out/`) holds the PS `normal.png` (+ `albedo.png`); the matching source
   frames (single frontal photo = the estimator's input) are in the sibling
   `<name>.data/` dir. Spans the albedo range for free:
   - `painted_mini_out/` — painted (the doc's original example)
   - `necron_overlord_painted_front.out/` + `..._back.out/` — painted
   - `necron_reanimator_wip_front.data.out/` + `..._back.data.out/` — WIP basecoat
   - `skaven_clanrat1_black_front.out/` — **black primer** (the hardest / most valuable case)

   *Env note:* the AI normal estimators need **torch**, which the repo `.venv`
   deliberately lacks (Tier 0a drop). Run them in a **separate throwaway env** — mirror
   the `tools/ps_tool.py` sidecar pattern (own venv), or a scratch `spikes/` venv. Do NOT
   add torch to the app env. This is a spike; keep the estimator code throwaway.
2. On the gate: pass → spec Path N; fail → spec Path S first.
3. Either way, **Path S (STL import + mesh bake)** is on the roadmap as the
   highest-faithfulness source and the validation harness — spec it once the spike sets
   the order.

**One-line summary:** newer tech does *not* rescue AI-mesh, splat, or photogrammetry for
faithful mini relief — but it *does* add a real new lever (single-photo AI normal
estimators) and reaffirms the STL-bake path; the cheap next move is to benchmark
single-photo normals against the PS ground truth we already have, then build whichever of
Path N / Path S the result favours.
