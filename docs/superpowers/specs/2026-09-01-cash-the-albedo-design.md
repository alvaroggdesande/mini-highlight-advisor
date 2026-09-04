# Cash the Albedo — Design Spec (Fork B, slice 4)

**Date:** 2026-09-01
**Status:** SHIPPED — merged to main via PR #28 (feat/cash-the-albedo). All three tasks complete.
**Classification:** Architectural (new output from `ps_tool`, new consumption path in `relight.py`, UI threading).

## Background — why this exists

Photometric stereo shipped (`5c5eea9`) and has been producing geometry consumers
(edge highlights, cavity/AO shades, NMM — slices 1–3). The roadmap (`2026-08-09-
roadmap-and-idea-assessment.md`, addendum 2026-08-24) explicitly names **"cash the
albedo"** as the next Fork B frontier and the strategic funnel-widener:

> *"v1 discards the one thing PS uniquely recovers — ps_tool exports only
> normal.png + mask.png (no albedo), and relight.py renders on a flat ALBEDO
> constant. So PS on a black mini yields a plan on a grey render — close to what
> Path L already did on a grey-primed mini from one photo. The big payoff (albedo
> → colored minis) is an explicit v1 non-goal."*

**Spike result (2026-09-01):** SDM-UniPS already outputs `baseColor.png` when
`--target normal_and_brdf` is used. The `checkpoint/brdf/` directory exists in the
shipped checkpoint. A spike run on the black-primer frames confirmed:

- Both models load correctly (`nml.pytmodel` + `brdf.pytmodel`)
- `baseColor.png` is exported and readable
- Mean RGB `[0.216, 0.214, 0.212]` on black primer — near-perfect channel balance
  (near-zero spread), confirming the model strips shading and returns flat albedo
- `albedo.png` displayed as flat uniform grey silhouette with no shading gradient ✅

Colour quality on a *painted* mini is the remaining unknown (no painted frames
available at spike time). The architecture is unaffected: if quality is poor the
coloured base is noisy but banding is unaffected (banding is geometry-driven).

## Goals

1. Export `albedo.png` from `ps_tool` as part of the standard PS bundle.
2. Consume it in `relight.py` so the display base is a coloured render of the
   actual paint job, not a flat grey render.
3. Keep Path L byte-identical and three-file bundles backwards-compatible.

## Non-goals (this slice)

- **No palette auto-suggestion from albedo** — sampling albedo per region to match
  paints is a fast-follow (scenario B), not in scope here.
- **No roughness/metallic hint use** — SDM also outputs `roughness.png` and
  `metallic.png`; consuming those (NMM auto-detection, drybrushing hints) is a
  later slice.
- **No new UI controls** — the coloured base is automatic when `albedo.png` is in
  the bundle; no toggle, no mode switch.
- **No persistence change** — PS mode is still session-only; albedo.png is part of
  the session import bundle, not persisted differently.

## Architecture — one seam, four files

```
ps_tool.py  ──(always)──>  albedo.png  ──>  relight.load_albedo()
                                             relight.relight(albedo=…)
                                             → relit_rgb (H,W,3) uint8, coloured
                                             ↓
                                 ui/ (PS import + results threading)
                                             ↓
                                 analyze_regions(rgb=relit_rgb, …)
                                 overlay / steps draw on coloured base
```

`pipeline.py`, `overlay.py`, banding, coverage, edges, shades, NMM — **zero
change**. The coloured `relit_rgb` replaces `relit_grey` as the base; the type is
already `(H,W,3) uint8` so nothing downstream is aware of the change.

## The load-bearing constraint (unchanged)

- **Path L byte-identical** — no `albedo` → `relight()` falls back to flat grey,
  identical to today.
- **Bundle backwards compat** — three-file bundles (no `albedo.png`) load and work
  as before. `albedo.png` is a fourth optional file.

## Detailed design

### `tools/ps_tool.py`

**Remove the `--brdf` spike flag; make BRDF always-on.**

`_build_sdm_cmd` always passes `--target normal_and_brdf` (drop the `brdf`
parameter). `_run_sdm_unips` always reads `baseColor.png` from the SDM temp dir
alongside `normal.png` and returns `(normals, albedo)` — both always present.

`main()`:
- Remove `--brdf` arg.
- Always write `albedo.png` to `args.out`: `albedo_u8 = clip(albedo * 255).astype(uint8)`.
- Update the docstring bundle layout to include `albedo.png`.
- `_check_checkpoint` already checks for `checkpoint/normal/`; add a parallel check
  for `checkpoint/brdf/` with a clear error message pointing at the shipped bundle.

**SDM encoding note:** `baseColor.png` is written by SDM via `cv2.imwrite` (BGR).
Pillow reads it as RGB. No channel flip needed beyond the standard `/ 255` decode —
validated in the spike.

### `src/mini_highlight_advisor/relight.py`

**New: `load_albedo(path: str) -> np.ndarray`**

```python
def load_albedo(path: str) -> np.ndarray:
    """PNG albedo map -> (H,W,3) float32 in [0,1], RGB."""
    return np.asarray(Image.open(path).convert("RGB"), dtype=np.float32) / 255.0
```

**New: `plausible_albedo(albedo: np.ndarray, mask: np.ndarray) -> bool`**

Defence against importing a garbage PNG as albedo. Requirements: shape `(H,W,3)`,
values in `[0,1]`, foreground pixels not all-zero (a fully-black albedo on a
non-black mini is suspicious). Mirrors `plausible_unit_normals`.

**Changed: `relight(normals, mask, light, albedo=None)`**

```python
def relight(normals, mask, light, albedo=None):
    light_field = clip(normals @ light, 0, 1).astype(float32)
    light_field[~mask] = 0.0
    shading = AMBIENT + (1.0 - AMBIENT) * light_field          # (H,W) in [0,1]
    if albedo is not None:
        colour = albedo * shading[..., np.newaxis]             # (H,W,3) float
    else:
        colour = np.full((*mask.shape, 3), ALBEDO) * shading[..., np.newaxis]
    colour8 = clip(colour * 255, 0, 255).astype(uint8)
    colour8[~mask] = 0
    return light_field, colour8
```

`ALBEDO` (the constant) stays for the fallback path. The return type and shape are
unchanged: `(light_field: (H,W) float32, relit_rgb: (H,W,3) uint8)`. The variable
is renamed internally from `relit_grey` to `relit_rgb` — callers already use
positional unpacking so no caller change is needed.

### `ui/` — PS import + session threading

Wherever the app reads `normal.png` + `mask.png` from the uploaded bundle:

1. Also attempt to read `albedo.png` from the same directory / uploaded file set.
2. If present and `plausible_albedo` passes: store in `st.session_state[keys.ALBEDO]`.
3. If absent or fails the plausibility check: store `None` (grey fallback).

**New key:** `keys.ALBEDO = "ps_albedo"`.

In `ui/results.py`, retrieve `albedo = st.session_state.get(keys.ALBEDO)` and pass
it to `relight(normals, mask, light_dir_vec, albedo=albedo)`. No other change to
`results.py`.

### Testing strategy

**`relight.py` (TDD):**
- `albedo=None` → output is byte-identical to current grey path (regression lock).
- `albedo` present → per-pixel: `out[i,j] = clip(albedo[i,j] * shading[i,j] * 255)`;
  verify a red albedo patch in the rendered base is red (not grey).
- `albedo` shape mismatch with `normals` → `ValueError` (fail loud before render).
- `plausible_albedo`: all-zero foreground → `False`; reasonable RGB values → `True`.
- `load_albedo`: round-trip encode/decode within float32 tolerance.

**`ps_tool.py`:**
- `_build_sdm_cmd` always uses `normal_and_brdf` (no more `brdf` param).
- `_check_checkpoint` fails loudly when `checkpoint/brdf/` is missing.
- End-to-end: existing ps_tool integration tests still pass (the output bundle gains
  `albedo.png` but `normal.png` + `mask.png` are unchanged).

**`ui/` (AppTest):**
- PS import with albedo present → `keys.ALBEDO` set; preview renders coloured base.
- PS import without albedo (`albedo.png` absent) → `keys.ALBEDO` is `None`; preview
  renders grey base (no regression).
- Plausibility-fail albedo → treated as absent (grey fallback, no crash).

## Rollout / build order

1. **`relight.py`** — `load_albedo`, `plausible_albedo`, `relight(albedo=)` + tests.
   Pure, no UI dependency. Regression lock on grey path.
2. **`ps_tool.py`** — drop `--brdf` flag, always-on BRDF, always write `albedo.png`,
   update `_check_checkpoint`. Spike code (`# SPIKE` comments) cleaned up.
3. **`ui/`** — `keys.ALBEDO`, PS import reads albedo, `results.py` threads it
   through to `relight()`. AppTest.

Steps 1–2 deliver and prove the value offline (load a real `albedo.png` from the
spike output, feed to `relight()`, inspect). Step 3 wires it into the app.
