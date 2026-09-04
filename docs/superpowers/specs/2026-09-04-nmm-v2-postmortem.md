# NMM v2 (procedural-matcap) — Post-mortem & redesign brief

**Date:** 2026-09-04
**Branch:** `feat/nmm-procedural-matcap` (parked, pushed, **not merged** — do not merge)
**Status:** approach abandoned. This doc is the durable record so the redesign
doesn't re-walk the same dead end.

---

## 1. What was built

NMM v2 modelled metal as a **mirror sampling a procedural reflection
environment** (a "matcap" disk). Per pixel:

1. `reflect(view, N)` → reflection vector `R` from the surface normal field.
2. Read `(R_x, R_y)`, bilinear-sample a procedural env disk (`build_nmm_env`:
   hard horizon + ground bounce + directional streak + tight specular glint).
3. `band_by_value` the sampled brightness into paint steps.

Code (all on the branch, as reference):
- `src/mini_highlight_advisor/materials.py` — `build_nmm_env`, `NMM_PRESETS`,
  `nmm_light`, `smooth_normals`.
- `src/mini_highlight_advisor/banding.py` — `band_by_value`.
- `src/mini_highlight_advisor/pipeline.py` — NMM branch in `plan_region`.
- `ui/results.py` — Metal-environment panel (presets, knobs, env-disk preview).
- Spec: `docs/superpowers/specs/2026-09-01-...` era; branch commits `82df350`
  (spec) → `5bc0af0` (bilateral smoothing).

## 2. Symptom

On real minis the render was unusable:
- **Raw normals →** gold/glint **speckle** scattered through recesses and flats,
  following noise, not form.
- **Gaussian-smoothed normals →** speckle gone but form smeared into **mud**
  (reads as plastic).
- **Bilateral-smoothed normals →** best of the three (denoises flats, keeps form
  edges) but a greebled surface **still doesn't read as metal**.

Screenshots from the session: a Necron warrior — raw gold speckle; then a
bilateral chrome weapon that read as smeared plastic.

## 3. Root cause (two independent failure modes)

**(a) The reflection lookup amplifies normal noise.** `R = reflect(view, N)`:
a small wobble in `N` throws `R` a proportionally *larger* distance across the
env disk. Because the glint is a tight blob, only pixels whose (noisy) reflection
lands on it get the top band → isolated speckles instead of a coherent highlight
line. There was **no smoothing anywhere** in `normals → reflect → nmm_light →
band_by_value`.

**(b) The input normals are noise-dominated.** Phone photometric-stereo
(SDM-UniPS, `tools/ps_tool.py`) normals carry heavy pixel-scale noise. Measured
across four real bundles (`spikes/nmm_normal_diag.py`), high-frequency energy vs
total spatial variation of the normal field, in-mask:

| bundle | noise ratio |
|---|---|
| necron_overlord_painted_front | 222% |
| necron_reanimator_wip_front | 220% |
| black_output (black primer) | 230% |
| skaven_clanrat1_black_front | 226% |

>200% everywhere — the pixel-scale noise **exceeds** the smooth form signal. The
high-pass view lights up across whole surfaces, not just at edges.

**Why smoothing can't win:** the noise and the genuine form live at *overlapping
spatial scales*. Any blur strong enough to kill the noise also destroys the form
→ the speckle↔mud trap. Bilateral (edge-preserving) is the best compromise but
only shifts the trade-off; it can't separate signals that overlap in scale.

**(c) The deeper problem — matcap value maps are low-contrast.** Even where the
normals *are* clean, a reflection environment produces soft, gradual value maps.
But NMM reads as metal precisely because it has **hard, high-contrast value
zones**: near-black shadow, a crisp near-white highlight line, sharp transitions.
The matcap can't produce that structure. So even a perfect denoise would still
read as matte plastic, not metal. This is the decisive point: the approach is
wrong *independent of* the noise.

## 4. Verdict

Reflection-matcap NMM is the wrong tool for phone-PS normals. Two strikes:
noise-fragile **and** structurally low-contrast. Smoothing (Gaussian → bilateral)
was a fair cheap test; it proved the approach can't be rescued, only softened.
Bilateral (`smooth_normals`, commit `5bc0af0`) is left in as the best stopgap.

## 5. Redesign direction (for next time)

Metal NMM on a mini is a **painting convention**, not a physical mirror sim:
hard-edged value zones, a placed near-white highlight, a near-black shadow,
positioned *by form*. Build it in the repo's proven, noise-tolerant, *robust
geometry* style — the same style that already works on these exact normals:

- `geometric_edge_mask` / `geometric_extreme_edge_mask` (edge highlights)
- `cavity_mask` (cavity/AO shades)

These survive the noise because they use **thresholded, robust** geometry
signals, not the raw reflection vector. Sketch:

1. Derive a robust **facing/height** signal from the normals (e.g. `N·up`, or a
   smoothed curvature/AO), denoised at a scale that keeps form.
2. Band it into a small number of **hard** value zones (not a smooth ramp).
3. Place **one** crisp highlight line geometrically (reuse the edge machinery)
   and one shadow in the cavities (reuse cavity machinery).
4. Keep it stylised and high-contrast — legibility over physical accuracy.

**Build on `main`, not this branch.** While this branch was parked, `main` grew
its own NMM lineage — a **technique system** (`get_technique`, `spec.role_names`,
technique-aware `plan_region`/banding). The redesign should extend *that*, fresh
off current `main`. This branch's matcap code is reference only.

## 6. Why this branch was not merged

`main` is ~78 commits ahead; the merge conflicts (`pipeline.py`, `ui/results.py`,
`tests/test_ui_nmm.py`, `ui/editor.py`) are an **architecture collision** between
this branch's matcap and main's technique system — not mechanical. Resolving
them would either regress main's live technique code or delete the matcap this
branch exists for. Since the matcap approach is abandoned, the branch is kept
as a pushed reference and the PR should be **closed/drafted**, not merged.

## 7. Artifacts

- Branch: `feat/nmm-procedural-matcap` (pushed).
- Diagnostics (untracked, under `spikes/`): `nmm_normal_diag.py` (+ `_out.png`),
  `nmm_smooth_probe.py` (+ `_out.png`), `nmm_bilateral_probe.py` (+ `_out.png`).
- Real PS bundles used: `spikes/phone_ps/data/{necron_overlord_painted_front,
  necron_reanimator_wip_front,black_output,skaven_clanrat1_black_front}.*`.
