# Photo-Quality Guide + Input Check — Design

**Date:** 2026-08-14
**Status:** Approved design (Idea B from the roadmap). Ready for an implementation plan.
**Roadmap ref:** `docs/superpowers/specs/2026-08-09-roadmap-and-idea-assessment.md`, Session 3 "Idea B".

## Purpose

Input quality caps output quality: the engine reads the *caught light* on the sculpt,
so a flat-lit, clipped, soft, or tiny photo starves the exact signal the pipeline
needs. This feature (a) gives the user a short written **shooting guide**, and (b) runs a
live **input-quality check** on the uploaded photo that warns — with concrete, actionable
advice — when the image will produce a poor highlight plan.

Explicitly **advisory / non-blocking**: the plan always renders; warnings sit above a
working result. This matches the tool's offline/free, zero-LLM constraints — every check
is a local numpy/opencv measurement.

## Scope (locked via brainstorm 2026-08-14)

- **Both halves in this build:** the live input-quality check *and* a static shooting guide.
- **Four checks:** lighting flatness, exposure clipping, resolution/framing, focus.
- **Presentation:** an always-on quality panel. Every row gives useful advice ("something to
  improve"), never a bare verdict — passing checks also speak a short confirmation.
- **Thresholds:** sensible hardcoded defaults now (documented, tunable constants), refined
  empirically later. No calibration photo-session is required to ship (the user has no minis
  on hand to shoot); the one real-photo validation anchor is the existing known-good
  `fixtures/skaven-hero/primed.png`.

## Architecture

One new **pure, Streamlit-free** module: `src/mini_highlight_advisor/input_check.py`. It does
all measurement and phrasing; `app.py` only renders what it returns. This keeps it
unit-testable and UI-agnostic, consistent with the rest of the core.

### Public surface

```python
from dataclasses import dataclass

@dataclass
class CheckResult:
    id: str        # "lighting" | "exposure" | "resolution" | "focus"
    label: str     # e.g. "Lighting", "Exposure", "Framing", "Focus"
    ok: bool
    value: float   # the measured number, surfaced to the user
    detail: str    # observation + concrete fix — always actionable, never just "poor"

def check_input(rgb: np.ndarray, mask: np.ndarray) -> list[CheckResult]: ...

SHOOTING_GUIDE: str   # static guide markdown, also written to docs/photo-guide.md
```

### Key design decisions

- **Takes the already-computed mask**, not the raw image, so it reuses the mask the render
  path already builds and never triggers a second (expensive) depth-model run. `app.py`
  computes the mask once via the existing `compute_mask` and passes it to both `check_input`
  and the analysis path.
- **Measures on raw grayscale (0–255), not `lighting.luminance_light`.** `luminance_light`
  applies CLAHE + a 2/98 percentile stretch — exactly the normalization that would *hide* a
  flat or clipped exposure. The check must read the un-normalized signal.
- **Runs on the same 768px-loaded `rgb` the engine sees** (post `load_image` thumbnail), so
  the verdict reflects what the pipeline actually receives. `load_image` only downscales,
  never upscales, so a small original stays small — the resolution check therefore captures
  both "original too small" and "downscaled" without needing the pre-thumbnail dimensions.

## The four checks

All measured on the raw grayscale (`cv2.cvtColor(rgb, COLOR_RGB2GRAY)`), restricted to
`mask` pixels. Order in the panel = lighting, exposure, focus, framing (most- to
least-impactful on the engine).

| id | Metric | Default threshold (named constant) | Advice on failure |
|---|---|---|---|
| **lighting** | Interpercentile spread `p95 − p5` of raw grey inside mask | `< 60` → too flat | "Lighting is flat (spread N/255) — light the mini with a single raking light from one side (~45°) and turn off any on-axis / built-in flash." |
| **exposure** | Fraction of masked px crushed (`grey ≤ 4`) and blown (`grey ≥ 250`) | crushed `> 25%` **or** blown `> 5%` | crushed: "N% of the mini is crushed to black — raise exposure or add a fill light; shadow detail is lost." blown: "N% is blown out — lower exposure and diffuse the light." |
| **resolution** (label "Framing") | Mask pixel count **and** frame coverage fraction | area `< 40_000 px` **or** coverage `< 0.15` | low coverage: "The mini fills only N% of the frame — move closer or crop so it fills most of the frame." low area: "Photo resolution is low — use a larger image." |
| **focus** | Variance of `cv2.Laplacian(grey)` over masked px | `< 100` → soft | "Photo looks soft / out of focus — refocus on the mini and hold steady (use a timer or brace your hands)." |

Behaviour notes:

- **Passing checks still speak.** e.g. lighting-OK → "Good tonal range across the mini";
  focus-OK → "Sharp"; framing-OK → "Mini fills N% of the frame". So the always-on panel is
  informative even on a good photo.
- When both exposure sub-conditions fire, report both in one `detail` (crushed + blown).
- **All thresholds are named module constants** with a short comment on the reasoning
  (`FLAT_SPREAD_MAX = 60`, `CRUSH_FRAC_MAX = 0.25`, `BLOWN_FRAC_MAX = 0.05`,
  `MIN_MASK_AREA = 40_000`, `MIN_COVERAGE = 0.15`, `MIN_FOCUS_VAR = 100.0`). Tuning later is a
  one-line edit.
- `value` carries the raw measured number for each check so the UI can show it and future
  tuning can inspect it.

## UI presentation & shooting guide

In `app.py`, Miniature tab: right after the image loads and the mask is computed, and
**before** the highlight results, render an always-on **"📷 Photo quality"** panel:

```
📷 Photo quality
✅ Lighting — good tonal range across the mini
⚠️ Exposure — 31% of the mini is crushed to black; raise exposure or add a fill light
✅ Focus — sharp
✅ Framing — mini fills 42% of the frame

▸ How to photograph your mini   (expander)
```

- One row per `CheckResult`: status icon + label + `detail`. Use `st.success` / `st.warning`
  per row (or an equivalent compact render — implementation detail).
- The expander holds `SHOOTING_GUIDE`: raking side light ~45° from one direction; **no
  on-axis / built-in flash** (flattens form); fill the frame; plain neutral background; sharp
  focus + steady hands / timer; a zenithal-primed mini reads best. The same text is also
  written to `docs/photo-guide.md` so it is linkable outside the app.
- **Non-blocking:** the panel never gates the plan. The mask is computed once and shared
  between `check_input` and the render path — no double depth run.

## Testing

Pure module → deterministic synthetic numpy fixtures, one per failure mode:

- flat mid-grey masked block → fails **lighting** only.
- high-contrast gradient masked block → passes **lighting**.
- mostly-black masked block → fails **exposure** (crushed); mostly-white → fails **exposure**
  (blown).
- tiny mask (few px / low coverage) → fails **resolution**.
- sharp checkerboard vs Gaussian-blurred block → **focus** pass / fail.
- **Real anchor:** `fixtures/skaven-hero/primed.png` (+ its alpha) passes all four checks.

Each `CheckResult.detail` is asserted to contain both the measured number and a fix verb,
locking in the "actionable, never just 'poor'" requirement.

`app.py` wiring gets a light smoke check only — the Streamlit UI is not unit-tested here,
matching repo convention.

## Out of scope / deferred

- Empirical threshold calibration from a multi-shot photo session (deferred — no minis on
  hand; defaults ship now, tune later).
- Per-region input checks (whole-mini only for v1).
- Auto-fixing the image (e.g. auto-exposure) — the check advises, it does not alter pixels.
- Any blocking / gating behaviour.
