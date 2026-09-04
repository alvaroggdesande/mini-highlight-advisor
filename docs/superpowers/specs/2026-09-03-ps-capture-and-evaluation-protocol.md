# PS Capture & Evaluation Protocol (dogfooding)

**Date:** 2026-09-03
**Status:** Working protocol. Purpose: settle "is PS worth the friction vs light-only?"
with **evidence from real minis**, not whiteboard ranking. Produces a comparable
capture-quality score + usefulness read per mini.

## Why this exists

The roadmap keeps re-ranking PS vs light-only in the abstract. The only honest arbiter is:
shoot real minis across the three capture regimes, score each capture, and look at whether
PS's geometry actually places the plan better than luminance. This log becomes the evidence
that re-prioritises the roadmap.

## The three capture regimes

| Regime | How to shoot | What it tests |
|--------|--------------|---------------|
| **A. Single, Path L** | one **raking side light** (~30–45° from the side, NOT on-axis flash); avoid crushing to pure black | value placement on primed minis (light-only's lane) |
| **B. Multi-angle, Path L** | front / back / left / right, each a single raking-light shot | cheap whole-mini breadth (`feat/multi-angle-view`) |
| **C. PS multi-shot** | **fix the mini AND the camera** (prop the phone). Take **6–8 frames, moving the LIGHT** to a different position each shot. Lock exposure/focus. Do **not** rotate the mini (a turntable fails the lighting-variation gate). | true normals + albedo → the geometry prizes |

## Running PS (regime C)

See `tools/README-ps.md`. From the repo root, in the PS venv:

```
python tools/ps_tool.py --frames <frames_dir> --checkpoint <checkpoint_dir> --out <out_dir>
```

Output bundle in `<out_dir>/`: `normal.png`, `mask.png`, `albedo.png`, `report.txt`
(the report is written **even on abort**, so a failed capture still tells you why).

## Capture-quality scorecard (all thresholds are the tool's real gates)

Read `report.txt` + glance at `albedo.png` / `normal.png`:

| Metric | Source | ❌ Fail | 🟡 Marginal | ✅ Good |
|--------|--------|--------|------------|--------|
| **Frames kept** | report `frames used` | < 4 (tool aborts) | 4–5 | 6–8+ |
| **Per-frame IoU** | report `ious` | any < 0.90 (dropped: rig moved) | 0.90–0.95 | 0.96–1.0 |
| **Lighting std** | report `lighting std` | < 8.0 (aborts: light barely moved) | 8–20 | 30+ |
| **Albedo channel balance** | `albedo.png` mean RGB | strong colour skew = shading baked in | mild | balanced (no systematic tint) |
| **Albedo brightness** | `albedo.png` mean | very dark (< ~0.12) = thin palette-match signal | dim but usable | bright enough to sample paints |
| **Normal coherence** | `normal.png` (eyeball) | scrambled everywhere | faceting only at overlapping parts (expected at 512px) | clean, readable relief |

Reference "good" run (black-primer staircase): 8/8 frames kept, IoUs 0.967–1.0, lighting std ~42.

## Usefulness read (does PS beat light-only on THIS mini?)

- Run the existing side-by-side: `spikes/phone_ps/compare_ps_vs_luminance.py` (throwaway spike —
  luminance-placed plan vs PS-relief-placed plan on the same mini). Does PS **relocate**
  highlights somewhere luminance got wrong? On a dark/low-contrast mini it should; on a
  well-lit primed mini the gap may be small — that's a *finding*, not a failure.
- For each candidate PS feature, ask: does the normal field give something luminance can't
  here? (edge on a true ridge / cavity in a true recess / a clean part-seam for auto-regions).

## Findings log (one block per mini — append below over time)

```
### <mini name> — <primed | part-painted | painted>  (<date>)
Regime(s) shot: A / B / C
report.txt: frames kept = __ , IoUs = __–__ , lighting std = __
albedo: mean RGB = [_,_,_]  (balanced? bright enough?)
normal: <clean / faceting where / scrambled>
Path L plan quality (subjective): <where it read right / where it lied>
PS plan quality (subjective): <where it read right / where it lied>
PS-vs-luminance (compare script): <PS relocated highlights? where? worth the shots?>
Verdict for the roadmap: <PS earned it here / light-only was enough / inconclusive>
```

### Batch summary — 9 captures scored (2026-09-03)

**Headline for the roadmap:** on **global highlight placement**, PS did **not** earn the
shots on a single mini — the PS-relit plan is visually near-identical to single-frame
luminance on every scorable capture, including the dark **black-primed skaven** (PS's
theoretical best case). Mechanism: our banding is **rank-based**, so PS-shade→stretch→band
and luminance→stretch→band land the same bands wherever the two maps agree on tonal *rank*
(same reason the per-region luminance-norm probe was a no-op). Caveat: the compare uses one
aligned frame (`L_01`) for the luminance side, so this is "single good raking frame vs PS",
not "flash-flattened vs PS".

Where PS *does* still earn it: the recovered **normals are clean and carry true geometry**
(ridges, cavities, part-seams) — that's the Fork-B lane (edge highlights / cavity-AO / auto
regions), which the global-placement compare doesn't exercise. PS also recovered a genuinely
albedo-clean map on the black skaven (mean RGB ~0.65, neutral) — the shading was removed as
intended, it just didn't move the bands.

Capture reliability: **2 of 9 shoots aborted** (skorpeh-grey-front 2/8, skaven-back 2/7) —
too few frames survived the IoU gate (rig/light drift or too few usable frames). Of the 7 that
ran, all cleared the frame-count and lighting-std gates; min per-frame IoU sat in the 0.90–0.95
**marginal** band on the phone shoots (vs 0.96+ on the tripod reference runs).

| Mini (regime C) | Frames kept | Min IoU (kept) | Lighting std | Albedo mean / bright | Normal | Capture verdict |
|---|---|---|---|---|---|---|
| necron_overlord_painted **back** | 10/10 | 0.939 | 36.3 | [.289,.245,.249] / .261 | clean | ✅ PASS |
| necron_overlord_painted **front** | 6/10 | 0.936 | 31.4 | [.323,.304,.300] / .309 | clean | ✅ PASS (4 dropped) |
| necron_reanimator_wip **back** | 7/8 | 0.911 | 40.1 | [.402,.396,.392] / .397 | readable, faint cyan tint | ✅ PASS |
| necron_reanimator_wip **front** | 6/8 | 0.913 | 42.9 | [.392,.396,.387] / .392 | readable, base noisy | ✅ PASS (2 dropped) |
| skaven_clanrat1_black **front** | 8/8 | 0.909 | 35.1 | [.651,.650,.653] / .652 | clean | ✅ PASS (best albedo) |
| painted_mini (Sep-1 test) | 9/9 | 0.967 | 42.4 | [.294,.287,.290] / .290 | clean | ✅ PASS (best IoU) |
| necron_skorpeh_lord_grey front | 2/8 | — | — | — | — | ❌ FAIL (abort) |
| skaven_clanrat1_black **back** | 2/7 | — | — | — | — | ❌ FAIL (abort) |
| black staircase (tripod ref) | 8/8 | 0.967 | 41.9 | (pre-albedo build) | clean | ✅ reference |

Side-by-sides written to each bundle as `_compare.png` (via throwaway `spikes/phone_ps/_score_all.py`).

---

### necron_overlord_painted — painted  (2026-09-03)
Regime(s) shot: C (front + back)
report.txt: frames kept = 10 (back) / 6-of-10 (front) , IoUs = 0.939–1.0 (back) / 0.936–1.0 kept (front) , lighting std = 36.3 / 31.4
albedo: mean RGB = [.289,.245,.249] back, [.323,.304,.300] front — mild skew (real teal/green paint, not baked shading), dim (~0.26–0.31) but usable
normal: clean, readable relief across body/tubes/staff on both faces; base coherent
Path L plan quality (subjective): reads correctly on the raised plates and cabling; single-frame luminance already tracks form well
PS plan quality (subjective): essentially the same zones as Path L; no visible relocation
PS-vs-luminance (compare script): near-identical placement both faces — PS did **not** relocate highlights; front lost 4 frames to drift but the 6 kept were enough for a clean normal
Verdict for the roadmap: **light-only was enough** for placement; PS's clean normal is only worth it for geometry features (edges/cavities), not global bands

### necron_reanimator_wip — part-painted (grey/metal WIP)  (2026-09-03)
Regime(s) shot: C (front + back)
report.txt: frames kept = 7-of-8 (back, dropped L_05@0.672) / 6-of-8 (front, dropped L_05,L_06) , IoUs kept = 0.911–1.0 / 0.913–1.0 , lighting std = 40.1 / 42.9
albedo: mean RGB ~[.40,.40,.39] both faces — well balanced and bright (grey WIP recovers a neutral, bright albedo)
normal: readable relief on the mechanical upper body; faint cyan tint on back, base a bit noisy but coherent
Path L plan quality (subjective): good on the exposed mech detail; base rubble reads
PS plan quality (subjective): matches Path L; marginal extra relief on base rubble at most
PS-vs-luminance (compare script): near-identical; no meaningful relocation
Verdict for the roadmap: **light-only was enough**; strong albedo recovery is the only standout, and placement didn't use it

### skaven_clanrat1_black — primed (black)  (2026-09-03)
Regime(s) shot: C (front PASS; back ABORTED 2/7)
report.txt: frames kept = 8/8 (front) , IoUs = 0.909–1.0 , lighting std = 35.1
albedo: mean RGB = [.651,.650,.653] — **neutral and bright**; PS fully removed the black-primer shading (best albedo of the batch)
normal: clean, very readable (cloak, blade, base spikes all resolve)
Path L plan quality (subjective): single raking frame already places cloak/blade highlights correctly
PS plan quality (subjective): same zones; no relocation despite this being the dark-mini case PS should win
PS-vs-luminance (compare script): near-identical — the key negative result: **even on a black-primed mini, PS did not beat luminance on placement**
Verdict for the roadmap: **light-only was enough** for placement here; PS earns its keep (if anywhere) via albedo recovery + geometry features, not band placement. Back face is a capture-hygiene FAIL (2/7) — reshoot with the rig locked.

### necron_skorpeh_lord_grey / skaven_clanrat1_black-back — ABORTED captures  (2026-09-03)
Regime C attempted; both aborted at the IoU gate (skorpeh-grey-front 2/8 kept, skaven-back 2/7 kept — need 4).
Cause per user: wrong/insufficient frames (rig or light moved between shots; too few usable frames).
No albedo/normal produced. Action: reshoot with mini + phone locked, 6–8 clean light-only-moves, exposure/focus locked.

---

## Roadmap implication (the reframe this dogfood produced)

The compare tested PS on the job it's **structurally worst at**: matching a value ramp that
luminance already nails for free (banding is rank-based; a decent raking frame ties the
geometry-relit shade every time, even on a black-primed mini). So for the **current product —
value highlighting — the verdict is: ship single-photo, trust the light.** The real investment
is capture guidance (make that one photo a raking shot, not on-axis flash), *not* PS. Keep PS in
the value world only as a narrow Fork-B **geometry-feature generator** (edges on true ridges,
cavity/AO in true recesses, part-seams for auto-regions) — things one photo genuinely can't make.

**Where PS actually earns its existence: NMM and OSL** — the techniques where you *impose* a
light that isn't in the photo instead of following the real one.
- **NMM** = a stylized reflection map placed by *surface orientation*: hard bright sky-streak
  where the normal faces the notional light, a hard dark horizon band, ground bounce at the
  bottom. Luminance from one ambient photo can't tell a sky-facing bevel from a ground-facing
  one; the **normal can**. This is the one job geometry provably beats brightness. It's the
  parked `feat/nmm-metal-from-normals` branch, and the parked insight holds: the reflection env
  is a **vertical gradient applied per metal region**, not a per-feature effect (the stripe bug
  was near-binary n_y saturation; fix = monotonic blend).
- **OSL** = a *placed emitter*: `shade = facing(n→emitter) × falloff(2D distance) × colour`,
  added over the base. Photo lighting is irrelevant, even counterproductive.
- Both need real normals (PS multi-shot **or** the imported-normal-map mode) + clean albedo +
  region restriction — and crucially do **not** need "good value lighting", only the lighting
  *variation* the gates already enforce. The black-skaven capture (useless for value placement)
  is the **ideal NMM/OSL substrate**: clean neutral albedo + clean normal.

Open scope question for the next brainstorm (do not pre-decide): does the product's audience
want NMM/OSL at all? If yes, PS flips from "didn't earn it" to "the only engine for the next
tier". If no, PS stays on the shelf as a Fork-B feature generator and value-highlighting stays
single-photo.
