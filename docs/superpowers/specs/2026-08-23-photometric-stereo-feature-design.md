# Photometric-Stereo Feature — Design Spec

**Date:** 2026-08-23
**Status:** Design approved in brainstorm; awaiting spec review before planning.
**Classification:** Architectural (new subsystem: capture → PS → relight → existing pipeline).

## Background — why this feature exists

The app reads highlight placement from a photo's **luminance**. That works for
grey/light-primed minis but fails on **dark albedo** (black primer, dark
basecoats), because brightness there conflates form with paint. Every cheap
single-image method was refuted for this: `depth_spike` (silhouette-only), two
intrinsic-image attempts, and the Step-1 per-region luminance normalization
(probe-proven no-op — rank banding is already albedo-independent, so a monotonic
rescale changes nothing).

**Multi-shot photometric stereo (PS) is the only path that separates normals
from albedo**, which is exactly what defeats dark albedo. This was validated end
to end:

- **Feasibility staircase — all three rungs PASSED** (`spikes/phone_ps_spike_protocol.md`):
  Rung 0 (synthetic, SDM-UniPS separates normals from albedo), Rung 1 (grey
  primer, real phone capture), Rung 2 (black primer — the true worst case). PS
  walked through the dark-albedo wall that killed every single-image method.
- **Payoff validated:** feeding PS relief into the *real* engine relocated the
  highlight plan vs the luminance path on a black mini (bands disagree on ~70% of
  pixels; the top highlight band overlaps 0%). PS bands form a coherent 3D
  gradient tracking the sculpt.
- **"Drag the light" UX validated** (`spikes/relight_slider_spike.py`, this
  session): relighting the recovered normals under a chosen virtual light makes
  highlight placement obvious and *travels* correctly as the light moves — on a
  real black mini's normals. Verdict: the **relighting is the killer UX**; true
  mouse-drag is polish, not risk.

**The residual risk is not the method — it is capture/registration/masking
robustness.** Both real rungs needed software drift-correction, and 2/6 and 2/8
frames were lost to inconsistent background removal. The design puts that risk
where it belongs (the external tool), fully gated.

## Goals

1. Let a user turn a multi-shot phone capture of a **dark/primed mini** into a
   recovered normal map, and get a highlight plan driven by that relief.
2. Provide a **global virtual-light control** (sliders + presets) that *drives
   the actual highlight plan* — the validated killer UX.
3. Keep the Streamlit app **lean and torch-free** (torch was deliberately dropped
   in Tier 0a); reuse the existing region/banding/overlay/edge/steps machinery
   unchanged.

## Non-goals (v1)

- **No torch in the app.** PS compute runs entirely outside the app.
- **No persistence / multi-angle integration.** Saving a PS import as a
  mini-project or as a multi-angle angle is a deliberate fast-follow (both
  persistence and multi-angle are now merged to main; wiring PS in is clean once
  the PS data shape is proven). A v1 PS import is session-only.
- **No true mouse-drag** relight (global sliders/presets only) — validated as
  polish, not risk.
- **No per-region light directions** — single global light only.
- **No specular in the plan** — diffuse `n·l` only; specular is preview flourish,
  deferred.
- **No coloured-mini support beyond dark primer** — v1 targets primed minis (the
  PS use case); coloured minis remain a later fork.

## Architecture

Two halves separated by a **file boundary** — the files *are* the interface.

```
┌─ EXTERNAL (owns torch, the hard/slow part) ─┐        ┌─ APP (lean, torch-free) ─────────────┐
│  ps_tool.py                                 │        │  new input mode: "Import normal map" │
│   capture frames → align → mask →           │  ───▶  │   normal.png + mask.png              │
│   SDM-UniPS → normal.png + mask.png         │  files │   → relight.py (n·l, global light)   │
└─────────────────────────────────────────────┘        │   → analyze_regions(light_field=…)   │
                                                        │   → existing overlay/steps/regions  │
                                                        └──────────────────────────────────────┘
```

### New code

- **`tools/ps_tool.py`** — standalone script run in its **own torch env**, never
  imported by the app (kept under `tools/` so it is off the app's import surface). Productized from the throwaway
  `spikes/phone_ps/` harness that passed the staircase. Owns capture registration
  + masking + inference.
- **`src/mini_highlight_advisor/relight.py`** — pure, torch-free, UI-agnostic
  (fits the "core is UI-agnostic" principle). The spike's shading math promoted
  to real code.
- **`ui/relight_panel.py`** — the global virtual-light control.

### One touch to existing core

`pipeline.analyze_regions(...)` gains an optional `light_field=` parameter:
- **absent** → today's luminance path, **byte-identical** (regression-locked);
- **present** → bypasses `lighting.luminance_light`, feeds the injected field
  straight into the source-agnostic per-region rank banding.

Everything downstream — banding, overlay, regions/RegionBook, edges,
palette/matching, paint-along steps — is **reused unchanged**.

## Component 1 — `ps_tool.py` contract

The stance: **the app never sees a bad map.** `ps_tool` either emits a validated
bundle or fails loudly with a reason.

**Input:** a folder of phone frames — fixed pose, one light moved between shots,
~6–8 shots (shoot extra to survive drops) — plus the checkpoint path.

**Pipeline stages** (each productizes a step done by hand in the staircase):

1. **Per-frame foreground mask** — rembg/GrabCut per frame.
2. **Register to frame 0** — correct pure-2D-translation drift (5–17px observed)
   via centroid alignment.
3. **Quality gates (fail-loud):**
   - drop any frame whose aligned IoU vs reference < `IOU_MIN` (default 0.9) —
     catches the base-cutoff masking artifact automatically;
   - require ≥ `MIN_FRAMES` surviving (default 4), else abort "capture too
     inconsistent";
   - require per-pixel intensity std across frames ≥ `STD_MIN` (real lighting
     variation, not a turntable), else abort.
4. **Consensus mask** — majority vote of the aligned per-frame masks.
5. **Prep + infer** — downscale ≤512², rename `L_01…L_NN`, write `mask.png`, run
   SDM-UniPS (`--target normal`, `map_location='cpu'` patch) → `normal.png`.
6. **QA report** — `report.txt`: frames used/dropped, IoUs, lighting std.

**Output contract (what the app depends on):**

| File | Meaning |
|---|---|
| `normal.png` | RGB-encoded **unit normals**, **pinned convention**: `n = rgb/255*2−1`, R=x-right, G=y-**up**, B=z-toward-viewer |
| `mask.png` | foreground mask, **identical WxH** to `normal.png`; authoritative for foreground |
| `report.txt` | capture QA (always emitted; app need not consume it) |

**Pinned normal convention** is load-bearing: it is why the spike needed a "flip
green" toggle (convention uncertainty). `ps_tool` normalizes to the documented
convention **once**, so `relight.py` needs **no per-import flip toggle**. If ever
wrong, it is a one-line fix in `ps_tool`, not user-facing state.

**Env & vendoring:** `ps_tool` ships its own requirements (torch-CPU, opencv,
einops, imageio) and a **vendored, pinned copy of SDM-UniPS inference** with the
`map_location='cpu'` patch committed in (not a fragile clone-at-runtime). The
445MB checkpoint stays **gitignored**; the README documents the one-time Dropbox
fetch. None of this enters the app env.

**Capture guide:** productize `spikes/phone_ps_spike_protocol.md`'s recipe into
`docs/ps-capture-guide.md` (fixed pose/tripod, one light moved to ~6–8 varied
off-axis angles, consistent framing, mask-friendly background, brighter exposure
for black primer, shoot extra to survive drops).

## Component 2 — `relight.py` (pure, torch-free)

```
load_normals(png) -> (H,W,3) unit vectors     # decode + renormalize; pinned convention
light_dir(az_deg, el_deg) -> (3,)             # [cos el cos az, cos el sin az, sin el]
relight(normals, mask, light) -> (light_field, relit_grey)
    light_field = clamp(normals · light, 0, 1)                 # the banding light source
    relit_grey  = albedo*(ambient + (1-ambient)*light_field)   # 3-channel display base
```

Diffuse-only for v1. `light_field` and `relit_grey` derive from the same relight,
so highlight bands and the background they are drawn on align perfectly. Constants
`ALBEDO` and `AMBIENT` are module defaults (values from the validated spike).

## Component 3 — App-side data flow

**Entry — a third input branch.** The upload gate today has two paths
(photo→mask; bg-removed PNG). PS import is a third: two uploaders (`normal.png`,
`mask.png`). Importing puts the app in **"PS mode"**: masking is skipped (mask
provided) and luminance is skipped (light field from normals). The luminance path
and the "coloured / painted mini (experimental)" toggle are **not shown** in PS
mode — PS is the answer that toggle could not deliver.

**Relight control (`ui/relight_panel.py`):** azimuth + elevation sliders + presets
(Upper-left / Top / Raking-L / Raking-R), written to new `ui/keys.py` constants
`LIGHT_AZ`, `LIGHT_EL`. Any change recomputes and re-renders the plan.

**The one engine call — rgb/light-field split:**

```
analyze_regions(
    rgb         = relit_grey,   # NEW: display base for overlays/steps (not the photo)
    alpha       = mask,
    palette     = …,
    light_field = light_field,  # NEW: bypasses luminance_light, feeds rank banding
    … regions, coverage, edges unchanged …
)
```

Today `rgb` *is* the light source. In PS mode they split — `relit_grey` for
display, `light_field` for banding — but both come from one relight, so the guide
is coherent. Everything after this call is reused unchanged: per-region rank
banding, edge highlights, overlay, paint-along steps, palette/coverage editing,
and the region lasso operating on `relit_grey`.

**Session/UI shape:** new keys `NORMALS`, `PS_MASK`, `LIGHT_AZ`, `LIGHT_EL`; new
`ui/relight_panel.py`; regions/palette/coverage/results panels operate on
`relit_grey` + `mask` with zero changes.

## Data flow (end to end)

```
capture frames ──ps_tool──> normal.png + mask.png ──import──> app
   app: load_normals + mask ──(az,el sliders)──> relight
        → light_field (n·l) + relit_grey
        → analyze_regions(rgb=relit_grey, alpha=mask, light_field=light_field, …)
        → regions / banding / edges / overlay / steps  (unchanged)
        → highlight plan + paint-along, rendered on the relit render
```

## Error handling

- **`ps_tool`** owns capture failure: fail-loud aborts (too few frames, low
  lighting variation) with a human-readable reason; per-frame drops logged to
  `report.txt`. The app therefore only ever receives a clean bundle.
- **App import validation:** on import, verify `normal.png` and `mask.png` have
  identical dimensions and that normals decode to plausible unit vectors; show a
  clear error and stay on the upload gate if not. This is the app's only defense
  against a hand-crafted / mismatched bundle.
- **Empty mask / degenerate light:** if the mask is empty or `light_field` is
  uniformly zero (light behind the mini), surface a gentle warning (mirrors the
  existing flat-region warnings) rather than rendering mud — a real-feature
  version of the spike's "back-lit angles go dark" caveat. v1 may simply warn;
  auto-exposure/tonemapping per light angle is a deferred refinement.

## Testing strategy

A committed **synthetic fixture** (`fixtures/…/synth_normal.png` +
`synth_mask.png`, a tiny dome + ridges) makes the whole app side testable offline
— no torch, no captures.

**`relight.py` (pure, TDD):**
- `load_normals`: known RGB → known unit vectors; non-unit input renormalizes;
  +Z pixel decodes to `[0,0,1]` (pinned convention).
- `light_dir`: `az0/el90 → [0,0,1]`, `az0/el0 → [1,0,0]`.
- `relight`: flat surface + light from +Z → uniform field = 1; raking light →
  gradient; off-mask excluded; **"highlight travels"** — two light dirs give
  different argmax locations (locks the validated behavior).

**`analyze_regions(light_field=…)`:**
- **byte-identical regression lock** without the param;
- new path with rgb luminance and `light_field` deliberately **disagreeing**
  (uniform-grey rgb, gradient light_field) → bands track the light_field (proves
  the bypass).

**`ps_tool.py` pure stages (no torch):**
- registration: two frames offset by known translation → residual under threshold;
- IoU gate: a cut-off-base frame dropped + listed in `report.txt`;
- min-frames abort and lighting-variation abort (identical/turntable frames);
- consensus mask: majority of aligned masks → expected;
- **contract round-trip**: normals array → PNG → `relight.load_normals` recovers
  the pinned convention (spans both modules; guarantees "no flip toggle").
- SDM-UniPS inference itself is **not** unit-tested (heavy/external) — covered by
  the manual gate.

**UI (AppTest, matching existing `ui/` tests):** PS import shows `relight_panel`;
moving a slider re-runs analyze and updates the plan; luminance/coloured-toggle
UI suppressed in PS mode; regions/palette/coverage render on the relit render
without error.

**Manual acceptance gate (user-run, not self-run):** end-to-end on a real black
mini — capture → `ps_tool` → import → drag light → plan. A checklist accompanies
the plan.

## Rollout / build order (for the plan)

1. `relight.py` + synthetic fixture (pure, TDD) — smallest, unblocks the app side.
2. `analyze_regions(light_field=…)` injection + regression lock.
3. App PS-mode: import branch, `ui/relight_panel.py`, wire the one engine call,
   suppress luminance UI in PS mode (AppTest smoke).
4. `ps_tool.py`: pure stages first (registration, gates, consensus, convention —
   all TDD without torch), then vendored SDM-UniPS + `map_location` patch + the
   inference orchestration (manual smoke).
5. `docs/ps-capture-guide.md`.

Note: steps 1–3 deliver the *app-side value* against the synthetic fixture and
any normal map already on disk (e.g. the staircase output), independent of the
`ps_tool` productization in step 4.

## Open questions / future work (explicitly deferred)

- Persistence: save a PS import (normal + mask + light dir) as a mini-project;
  PS capture as a multi-angle angle. Fast-follow once the PS data shape is proven.
- Single-zip bundle import (instead of two uploaders).
- True mouse-drag relight; per-region light; specular in the plan.
- Per-light-angle auto-exposure/tonemapping so back-lit views never go to mud.
- Wrapping `ps_tool` into an app-invoked sidecar (promotion from external import).
