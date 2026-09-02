# Feature #3: Painterly ramp sliders (future)

**Status:** Parked. The foundation is in place; this note records the extension path.

## What exists (feature #2)

`ramp_from_midtone(mid_hex, n, *, shadow_sat_boost, shadow_cool, hi_desat, hi_warm)`
in `src/mini_highlight_advisor/color.py`.

The four keyword args are already wired as named parameters with sensible defaults:

| Param | Default | Effect |
|---|---|---|
| `shadow_sat_boost` | 0.25 | How much more saturated shadows get vs the midtone |
| `shadow_cool` | 15.0 | Hue shift (degrees LCh) toward cool/blue for shadows |
| `hi_desat` | 0.20 | How much less saturated highlights get vs the midtone |
| `hi_warm` | 10.0 | Hue shift (degrees LCh) toward warm/yellow for highlights |

## What feature #3 adds

Expose those four params as sliders in the "Generate from midtone colour"
expander in `ui/palette_editor.py`, just above the "Generate ramp" button.

The implementation is a pure UI wiring — no logic changes, no new keys in
`color.py`. Just:
1. Add four slider widgets in `palette_editor.py` reading/writing session-state keys
   (e.g. `keys.SHADOW_SAT_BOOST`, etc.) with the current defaults as their defaults.
2. Pass those session-state values as kwargs when calling `ramp_from_midtone`.
3. Add the four keys to `ui/keys.py`.

No test changes needed — the behaviour tests already parametrise over these args
(`test_shaping_params_accepted_as_keyword_args`).

## Suggested slider ranges

| Param | Min | Max | Step |
|---|---|---|---|
| Shadow saturation boost | 0.0 | 0.6 | 0.05 |
| Shadow cool (°) | 0 | 40 | 5 |
| Highlight desaturation | 0.0 | 0.5 | 0.05 |
| Highlight warm (°) | 0 | 30 | 5 |
