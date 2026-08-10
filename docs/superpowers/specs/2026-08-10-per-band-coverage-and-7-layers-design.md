# Per-band coverage sliders + 7-layer cap — design

Date: 2026-08-10
Status: approved (brainstorming)

## Problem

The banding step splits the miniature's luminance into `n` layers using a
coverage curve — the fraction of the model each layer should occupy. Today that
curve is a fixed linear ramp (`palette.default_coverage`) and the layer count is
capped at 5. Two consequences:

- The fixed curve over-allocates the lightest bands (the ~34% "Highlight"
  over-allocation seen in previews); the user cannot rebalance it.
- Fine painters want finer transitions than 5 layers allow.

The engine already supports both: `banding.band_light` accepts any coverage
list, and `palette.default_coverage(n)` works for any `n`. The work is almost
entirely UI exposure plus small cosmetic gaps.

## Goals

1. Let the user set the coverage percentage of each layer directly, with the
   painted image redrawing live as they adjust.
2. Raise the layer cap from 5 to 7.

## Non-goals

- Coupled/redistribute sliders (every slider always summing to 100 by stealing
  from the others). Rejected as jumpy and fiddly in Streamlit.
- Saving the coverage curve into recipes. Recipes continue to store palette +
  roles only; coverage is a live, per-session tweak that resets each session.
- Per-region coverage. Whole-mini remains the only region (v1 constraint).

## Coverage UI — the "remainder band" model

The coverage numbers handed to `band_light` **must** sum to 1.0: they are used
as cumulative quantile cut-points (`np.cumsum(coverage)[:-1]`), so a total other
than 100% places the cuts wrong and corrupts the top band. The UI therefore
guarantees a 100% total by construction rather than by validation.

- Layers `0 … n-2` each get a `%` slider showing that band's **exact**
  percentage.
- The lightest layer (`n-1`) is **not** a slider. It is displayed as
  `<role> · auto: Y%` where `Y = 100 - sum(other sliders)`. It absorbs whatever
  is left — which also means fattening the darker bands naturally shrinks the
  lightest band, directly addressing the over-allocation complaint.
- **Never-exceeds invariant (proven, not patched):** each slider's `max_value`
  is computed live as
  `100 - (sum of the OTHER sliders) - floor`, with `floor` = 3% reserved for the
  remainder band. Streamlit rebuilds every widget on each rerun and only one
  slider changes per interaction, so if every slider respected its max when it
  was last set, the total of the `n-1` sliders can never exceed `100 - floor`.
  Therefore the remainder is always `>= floor` and the full total is always
  exactly 100. No clamping, no error banners, no sliders moving on their own.
- Slider values are seeded from `default_coverage(n)` (percent form) so a fresh
  session reproduces today's output. A **"Reset to default curve"** button
  restores that seed. When `n` changes, the seed is recomputed for the new `n`.

### Session-state keying

- Coverage sliders use keys `cov_pct_{i}` (i in `0 … n-2`).
- When `n` changes, existing `cov_pct_*` keys are cleared and reseeded from
  `default_coverage(n)` so a stale curve from a different layer count is never
  reused.

## Live redraw — split the core

The expensive work (mask via depth model, CLAHE luminance) depends only on the
image, not on palette or coverage. Split so it runs once per image while
coverage tweaks re-run only the cheap tail.

- `pipeline.prepare_shading(rgb, alpha) -> ShadingResult(mask, light)` — masking
  + luminance. Cached in the app (`st.cache_data`) keyed on the uploaded image
  bytes.
- `pipeline.band_and_render(rgb, mask, light, palette, coverage) ->
  HighlightResult` — banding + preview + legend + panel + per-band steps. Runs
  on every slider move.
- `pipeline.analyze(rgb, alpha, palette, coverage=None) -> HighlightResult`
  becomes a thin wrapper: `prepare_shading` then `band_and_render`. `coverage`
  is optional and defaults to `default_coverage(len(palette))`, so every current
  caller and test keeps working unchanged.

`ShadingResult` is a small dataclass `(mask: np.ndarray, light: np.ndarray)`.

## #7 — cap raised to 7 layers

- App layer slider max: 5 -> 7. Default layer count stays 5 (`setdefault("n", 5)`
  unchanged); 7 is the new ceiling, not the new default.
- `palette._ROLES` gains two entries:
  - `6`: `Shadow, Deep Base, Base, Midtone, Highlight, Edge Highlight`
  - `7`: `Shadow, Deep Base, Base, Midtone, Upper Midtone, Highlight, Edge Highlight`
- Palette-slot defaults: for slot index `i >= len(DEFAULT_PALETTE)` (i.e. slots
  6 and 7), seed an **interpolated neutral grey** — a custom hex evenly spaced on
  the black->white ramp for the current `n` — instead of duplicating Dead White.
  Curated 3/4/5 defaults are unchanged. A small helper
  `palette.ramp_hex(i, n) -> str` produces the interpolated grey.

## Data flow

```
upload ─► prepare_shading (cached) ─► (mask, light)
                                        │
coverage sliders ──────────────────────┼─► band_and_render ─► HighlightResult ─► image + guide
palette slots ──────────────────────────┘
```

## Testing

- `banding`: a custom coverage list (non-linear) yields per-band actual coverage
  approximately equal to the targets (within a tolerance for quantile
  discretisation).
- `palette`: `role_names(6)` and `role_names(7)` return the new names;
  `ramp_hex` endpoints are near-black / near-white and monotonic in between.
- `pipeline`: regression — `prepare_shading` + `band_and_render` with default
  coverage produces bands/coverage identical to the pre-split `analyze`; and
  `analyze(..., coverage=None)` still matches.
- Remainder math (pure function, extracted for testability): given the `n-1`
  slider values, `remainder = 100 - sum`, and the per-slider max invariant keeps
  the total <= 100.

## Files touched

- `src/mini_highlight_advisor/pipeline.py` — split into `prepare_shading` /
  `band_and_render`; add `ShadingResult`; `analyze` wrapper + optional coverage.
- `src/mini_highlight_advisor/palette.py` — `_ROLES` 6/7; `ramp_hex` helper.
- `app.py` — layer slider max 7; coverage sliders + remainder display + reset
  button + session-state keying; cache `prepare_shading`; call `band_and_render`
  on rerun; interpolated-grey slot defaults.
- `tests/` — coverage/banding, role names + ramp, pipeline regression, remainder
  math.
