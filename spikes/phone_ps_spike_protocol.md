# Phone Photometric-Stereo Spike — Protocol Note

> **Status: THROWAWAY spike design. Not a feature spec, not a plan.**
> Written 2026-08-15. Rung 0 is executable now (no minis). Rungs 1–2 are
> **blocked on capture** — they need multi-light photo sets of real primed minis,
> which we don't have on hand yet. This note exists so the probe can be run cold
> the day minis are available, without re-deriving the design.

This is Tier 3 **Step 3** of the colored-mini fork (roadmap addendum 2026-08-14).
Step 1 (per-region luminance norm) shipped; Step 2 (off-axis capture guidance)
shipped. Both single-image intrinsic-image attempts were refuted — the signal
isn't in a frontal-flash photo. Multi-shot photometric stereo (PS) is the only
remaining path that separates **normals from albedo**, which is what defeats dark
albedo. This spike decides whether to **fund** the PS build, before building it.

---

## The feasibility question (the one thing we're testing)

**Can an off-the-shelf, uncalibrated PS model, fed a handful of ordinary phone
shots of a primed mini under a moving light, recover fine surface relief (helmet
ridges, pauldron tops, chest detail) separately from albedo — well enough to
place highlight bands?**

Single-image methods provably can't do this (`depth_spike` = NO; two intrinsic-
image refutations = NO). PS is the sole claimed unblock. This spike finds out
whether that claim survives contact with *phone capture on black/grey primer*.

---

## Engine: SDM-UniPS (Ikehata, CVPR 2023)

Chosen because it is **uncalibrated** — it needs NO known light directions, only
several images under *arbitrary* varying light. That is the phone-friendly
property. (Near-field LUCES needs measured light positions; DMDPS needs a
display-as-light rig — both are heavier to probe. Revisit only if SDM-UniPS
passes the principle test but fails on capture ergonomics.)

- Repo: https://github.com/satoshi-ikehata/SDM-UniPS-CVPR2023
- Checkpoints (Dropbox `checkpoint.zip`): extract to `.../normal/nml.pytmodel`
  and `.../brdf/brdf.pytmodel`.
- Deps: Python 3.11, PyTorch 2.0, opencv, einops, imageio. Repo assumes
  **CUDA 11.8**.
- **Hardware note (this machine):** AMD Radeon 780M, no NVIDIA/CUDA → we run
  **CPU-only torch**. Fine for a downscaled smoke test; too slow for full 4096².
  Downscale inputs (e.g. ≤512²) and cap image count for any CPU run.
- Input layout — one folder per object:
  ```
  DATA/<object>.data/
    ├── mask.png        (optional; improves accuracy)
    ├── L_img1.png
    ├── L_img2.png
    └── ...             (up to 10 images by default)
  ```
  "Multiple images under various arbitrary lighting with sufficient shading
  variation in all parts." Object mask optional but helpful — we already own
  masking (`masking.py`), so supply one from the mini's alpha.
- Run: `python sdm_unips/main.py --session_name S --test_dir DATA --checkpoint CKPT --target normal`
  (add `--scalable` for memory-limited high-res; not needed downscaled.)
- Output: normal map (+ BRDF) under `S/results/`.

---

## The 3-rung staircase — each rung can return a killing NO cheaply

Isolate the variables. A NO at a lower rung kills the bet before we spend on the
next; a NO at a higher rung (with lower rungs passing) *localises the killer*.

### Rung 0 — engine smoke test (FREE, no minis) — executable now
Run SDM-UniPS on a **known** multi-light object (author's real test object, or a
controlled input with known ground-truth normals) → confirm the pipeline installs
on this machine and recovers known relief.
- **Kills:** "the tooling doesn't even run / recover relief here."
- **Pass:** recovered normal map visibly tracks the known relief (and, if
  ground-truth normals available, mean angular error is sane — say < ~25°).
- **Note:** SDM-UniPS is trained on complex-BRDF real-ish data; prefer a **real**
  photo test object over flat synthetic Lambertian, which may be out-of-
  distribution and *understate* the model. If using synthetic, treat a weak
  result as inconclusive, not a NO.

### Rung 1 — best realistic case (needs one capture)
One **grey-primed** mini (more SNR than black), **careful** off-axis lighting
moved to ~4 positions, fixed framing, background removed.
- **Answers:** "does PS recover mini-*scale* relief on our object class at all?"
- **A NO here kills the whole bet** — PS is dead for miniatures.

### Rung 2 — real worst case (needs one capture) — only if Rung 1 passes
**Black-primed**, **handheld** (no tripod), the true target condition.
- **A NO here with Rung 1 passing does NOT kill PS** — it localises the residual
  killer as *capture / SNR / registration*, and tells us what the eventual
  protocol must add (tripod? more shots? brighter/softer light? alignment step?).

---

## Capture recipe (Rungs 1–2) — the load-bearing half

**A sloppy capture makes a NO meaningless.** Most of the spike's correctness lives
here, not in the code. Get these right:

1. **Fixed viewpoint.** Phone on a stand / braced; the mini and camera do NOT move
   between shots. Only the light moves. (Rung 2 deliberately relaxes this to
   handheld to test robustness — but shoot a fixed-viewpoint version too, as the
   control.)
2. **One dominant moving light.** A single small bright source (desk LED, phone
   torch held in the other hand, a lamp) moved to **~4–6 distinct off-axis
   positions** between shots — e.g. upper-left, upper-right, left, right, top.
   Kill room ambient / other lights as much as possible so each shot has one
   clear light direction. **This is the opposite of on-axis flash** — the whole
   point is directional shading.
3. **Sufficient shading variation everywhere.** No region should be in shadow in
   *all* shots; no region blown out in all shots. Vary the light enough that
   every surface gets lit from several sides across the set.
4. **Consistent exposure, no HDR / no flash.** Lock exposure if possible so pixel
   intensities are comparable across shots. Turn the flash OFF.
5. **Background removed** → provide a `mask.png` from the alpha (reuse our masking
   path). Keeps PS from wasting capacity on background.
6. **Downscale** to ≤512² for CPU runs.

Capture BOTH a grey-primed (Rung 1) and a black-primed (Rung 2) subject if
possible, same protocol, so the only difference between rungs is albedo/SNR.

---

## Verdict decision table (pinned up front — do NOT move the goalposts)

Same eyeball test as `depth_spike` / `shading_spike`: **do the recovered
normals/bands track internal geometry** (helmet top, pauldron tops, chest plate;
recesses → dark bands) **rather than lighting up the silhouette only** — the exact
failure `depth_spike` had.

| Rung 0 | Rung 1 | Rung 2 | Verdict |
|---|---|---|---|
| pass | pass | pass | **FUND the build.** PS survives the real worst case. |
| pass | pass | fail | **FUND, but the protocol is the hard part.** Method works; capture/SNR is the residual killer — scope the build around a stricter capture protocol (tripod / more shots / lighting). |
| pass | fail | — | **DON'T FUND.** PS doesn't recover mini-scale relief on our object class even best-case. Bet is dead; stop. |
| fail | — | — | **Inconclusive on the method** — tooling/engine problem (bad install, wrong input, CPU/precision, or synthetic OOD). Fix the harness or get real test data before judging PS. Not a verdict on the bet. |

---

## Rung 0 result — PASS (2026-08-19)

Ran SDM-UniPS on the synthetic known-relief object (`spikes/phone_ps/`, CPU-only
AMD 780M, torch 2.13+cpu, 10 images @ 512², ~5.4 min). One repo edit required:
`model_utils.loadmodel` needed `map_location='cpu'` (checkpoint saved on CUDA).

- **Recovered normal map reproduces the GT** — dome radial gradient **and** the
  fine ridge/bump checkerboard, recovered across **both albedo halves including
  the dark-primer half**.
- **Albedo/normal separation confirmed** — the central bright/dark boundary and
  the diagonal blue stripe leave **no trace** in the recovered normals. This is
  the core property the mini bet depends on.
- **Honest interior MAE = 4.51°** (median 4.17°, 100% of pixels < 15°), computed
  over the eroded object interior (`eval_mae.py`). The engine's built-in figure
  of 42.6° is an artifact of the synthetic GT (I gave the *background* a valid
  unit normal `[0,0,1]`, so it counts background + grazing rim pixels) — not a
  recovery failure. Interior error map is uniformly dark.

**What Rung 0 proves:** the tooling runs on this machine and SDM-UniPS recovers
fine relief separately from albedo on this object class — in principle. **What it
does NOT prove:** anything about real phone photos, black primer under real light,
or handheld capture. Synthetic Lambertian is the easy case. The mini question is
Rungs 1–2, still blocked on captures.

## Rung 1 result — PASS (2026-08-23)

Ran SDM-UniPS on a **grey-metal-primed** mini (Tyranid-ish: base + carapace +
tendrils), 6 phone shots, fixed pose / moving single light, CPU-only, ~92 s.
Originals at `spikes/phone_ps/data/grey.data` → aligned/masked/downscaled copy at
`data/grey_aligned.data`, isolated run under `run_rung1/`, output
`rung1_grey/results/grey_aligned.data/normal.png`.

- **Capture caveat handled:** the user's *first* grey set was a turntable (mini
  rotated, light fixed) → unusable for PS (breaks pixel correspondence), re-shot.
  The re-shoot had fixed pose but a **5–17 px translation drift** between frames
  (raw silhouette IoU 0.66–0.85). Diagnosed as pure 2D translation
  (centroid-aligned IoU 0.97+, silhouette area constant → no rotation/scale) and
  corrected in software by registering every frame to frame 0. Lighting variation
  healthy (per-pixel intensity std 36/255 across the stack).
- **PASS evidence — relighting, not just the normal map.** Rendered pure Lambertian
  `n·l` from the recovered normals (albedo discarded) under 4 raking directions
  (`rung1_grey/_relit.png`). Shading responds correctly to light direction
  (terminator sweeps as the light moves), raised carapace/tendrils catch light
  while recesses go dark, base disc shows a correct radial dome gradient. The
  `depth_spike` silhouette-only failure mode is **absent**. Relief is
  albedo-independent — the core property the dark-albedo bet needs.

**What Rung 1 proves:** PS recovers mini-scale relief separately from albedo on our
object class, from ordinary phone shots — the load-bearing question. **The kill
condition (Rung 1 fail) did NOT fire; the PS bet is alive.** **What it does NOT
prove:** black primer (this was higher-SNR grey-metal, also mildly specular) and
handheld capture — that's **Rung 2**, still blocked on a black-primed capture. The
drift correction also means the eventual real protocol needs a tripod or a
baked-in alignment step. Per the decision table we are at **pass / pass / —**; the
FUND vs "FUND-but-protocol-is-the-hard-part" verdict awaits Rung 2.

## Rung 2 result — PASS (2026-08-23)

Ran SDM-UniPS on a **black-primed** mini (same object family), CPU ~120 s. Originals
at `data/black.data` → `data/black_aligned.data`, isolated run `run_rung2/`, output
`rung2_black/results/black_aligned.data/normal.png`.

- **Capture caveat — 2 of 6 frames discarded.** The background remover **cut the
  base off L_02 and L_04** (base-less alpha → those two would not co-register:
  centroid-aligned IoU ~0.49 vs 0.94–0.99 for the rest). Not a shooting error — a
  masking artifact. Ran on the **4 clean frames** (L_01/03/05/06), centroid-aligned
  like the grey set. 4 light directions is enough for SDM-UniPS.
- **SNR on dark albedo was workable** — body mean brightness 38 vs base 85, but the
  dark body still carried real shading variation (per-pixel std ~29 across frames).
  The user's "more light + brighter exposure on the black one" did its job.
- **PASS evidence — relighting (`rung2_black/_relit.png`).** Pure Lambertian `n·l`
  from recovered normals, albedo discarded, 4 raking dirs: raised skeletal
  figure / carapace / weapon catch light, recesses go dark, terminator sweeps
  correctly, base dome reads as a dome. The black primer left **no trace** in the
  relief → albedo-independent recovery on the true worst-case albedo.

**Verdict: full staircase pass / pass / pass ⇒ FUND the build.** PS recovers
mini-scale relief separately from albedo even on black primer — the property no
single-image method could deliver. **The residual engineering risk is NOT the
method — it's capture/masking robustness:** 2/6 frames were lost to inconsistent
background removal, and both rungs needed software drift-correction. So the funded
build must own a solid **capture + registration + masking protocol** (tripod or
alignment step; consistent masking; enough shots to survive dropping a couple).
This is the "FUND, but the protocol is the hard part" nuance landing on top of a
clean method pass. Funding cost still includes reintroducing the torch dependency
dropped in Tier 0a (heavy ML dep, CPU speed) — part of the go decision, per hygiene
below.

## Spike hygiene — what NOT to conclude

- Rung 0 pass ≠ feature works. It only says the engine runs and recovers relief
  on a *known* object. The mini question is Rungs 1–2.
- A PASS is NOT permission to keep the spike code. Any code here is throwaway;
  funding the build means a fresh spec → plan → implementation, and re-examining
  the torch dependency (deliberately dropped from the main app — a PS feature
  reintroduces a heavy ML dep and likely can't run in the current lightweight
  Streamlit env / on CPU at usable speed; that cost is part of the fund/no-fund
  decision, not a footnote).
- Everything downstream (how many shots a real user tolerates, in-app capture UX,
  hosting a torch model) is out of scope for the spike and only worth designing
  *after* a GO.
