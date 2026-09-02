# Scheme Generator — Design Spec

**Date:** 2026-09-02
**Status:** Draft — awaiting user review
**Classification:** Architectural (two new pure modules, extends Region/RegionBook + persistence + a new UI panel)

## Background

The tool answers three questions for a painter: *where do highlights go?* (solved — banding /
geometry), *how do I apply paint?* (solved — technique system: smooth / drybrush / NMM), and
*what colours do I use?* — which today is **fragmented and abstract.** The pieces exist but none
is aware of the mini in front of the user: `collection.py` (owned paints + `nearest_paint`),
`matching.py` (`match()` → owned-first paint or buildable mix), `schemes.py` (save/apply
per-region palettes), `color.py` (`ramp_from_midtone`, `hue_rotate` — harmony primitives), and
`recipes.py`. See the 2026-09-02 addendum in `2026-08-09-roadmap-and-idea-assessment.md`.

This feature (roadmap **Idea A**) builds the colour-**decision** engine: the user tags each
lassoed region with a **surface** (skin / metal / cloth / …), picks a **hero colour + mood**,
and the tool generates a **complete, coherent scheme for the whole mini — one buildable ramp per
region**, mapped to real paints (owned-first, not owned-only). It targets the actual paralysis:
"I own 40 paints and a bare mini — what do I do?" It also absorbs the old "material presets" idea:
the surface tag *softly* sets the region's technique (fur → drybrush).

## Goals

1. A **surface vocabulary** (`surfaces.py`): each surface carries a display name, a **bucket**
   (`realistic` | `free`), a set of **tone variants** (realistic only), and a **soft default
   technique**. Realism means "pick from a named set", never "must be natural" — skin's tones
   include orc-green / drow-blue / undead-grey alongside natural fleshtones.
2. A **colour-decision layer** (`scheme_gen.py`, paint-agnostic): from surface tags + anchor
   hue + mood + harmony variant, produce a **base hue per region** then expand each to an
   N-band ramp (`ramp_from_midtone`). Knows nothing about paints.
3. A **paint-mapping + assembly layer** (`scheme_build.py`): map each ramp hex to a real paint
   — **owned-first, catalogue fallback, buildable mix** (`matching.match`) — and assemble a
   `schemes.Scheme`. An `owned_only` mode hard-limits to the collection.
4. **Region gains `surface` + `tone`** fields (distinct from the technique field); RegionBook
   gains accessors; both persist in the project manifest (schema v3 → v4, back-compat).
5. A **Streamlit panel** (`ui/scheme_gen_panel.py`): per-region surface/tone pickers, anchor +
   mood + harmony-variant controls, `owned_only` toggle, Generate → preview → Apply. Applying
   writes palettes via `schemes.apply` and (opt-in checkbox) sets techniques from surface
   defaults.
6. **Reuse, don't rebuild:** the output is the existing `schemes.Scheme`; on-mini preview,
   save/swap, and persistence of the applied scheme are already shipped.

## Non-goals (this slice)

- **Auto-region detection** — regions are manual lasso only, as today. Surface tagging is per
  drawn region; auto-tagging is a future combo, not a prerequisite.
- **Learning the user's taste / recommending a mood** — the user drives anchor + mood.
- **Per-band paint-along recipe UI changes** — a band that resolves to a *mix* is stored as a
  synthetic `PaintColor` (hex = target, name = mix phrase); the existing legend/guide renders it
  as-is. No new recipe surface.
- **Gem/glass special ramps, OSL, glow** — gems are treated as a free surface with an ordinary
  ramp for v1.
- **Coverage generation** — like the scheme experimenter, a scheme captures **palette only**;
  coverage and the (now soft-set) technique remain live per-region settings.
- **B — contrast/value coaching** — parked (separate roadmap idea).

## Architecture

```
surfaces.py        ← NEW; pure, torch-free, Streamlit-free. Vocabulary registry.
  SurfaceSpec(name, display, bucket, tones: dict[str,str], default_technique)
  SURFACES: dict[str, SurfaceSpec]
  get_surface(name) -> SurfaceSpec           (falls back to "other")

scheme_gen.py      ← NEW; pure. The colour-decision layer (HEX ONLY, paint-agnostic).
  harmony_hues(anchor_hex, variant, k) -> list[str]
  apply_mood(hex, mood) -> str
  region_base_hue(surface, tone, is_anchor, anchor_hex, harmony_hex) -> str
  generate_ramps(specs, anchor_name, anchor_hex, mood, variant) -> dict[name, list[str]]

scheme_build.py    ← NEW; glue. Colour-decision → paints → Scheme.
  map_ramp_to_palette(ramp_hexes, owned, catalog, owned_only) -> list[PaintColor]
  build_scheme(name, specs, anchor_name, anchor_hex, mood, variant,
               owned, catalog, owned_only) -> schemes.Scheme

regions.py         ← Region gains `surface: str = "other"`, `tone: str | None = None`.
region_state.py    ← RegionBook gains whole_surface/whole_tone + surface_at/tone_at accessors.
projects.py        ← serialize/deserialize surface + tone; manifest schema v3 → v4 (back-compat).
ui/scheme_gen_panel.py ← NEW; the panel. The only Streamlit file.
ui/results.py or app.py ← mount the panel.
```

**No change** to banding math, step-image rendering, `schemes.apply`, or the technique system.
The generator is a front-end that *manufactures* a `schemes.Scheme`; everything downstream of a
Scheme already exists.

## Data model

### `surfaces.py`

```python
from __future__ import annotations
from dataclasses import dataclass

@dataclass(frozen=True)
class SurfaceSpec:
    name: str                       # internal key, e.g. "skin"
    display: str                    # UI label, e.g. "Skin"
    bucket: str                     # "realistic" | "free"
    tones: dict[str, str]           # tone label -> hex; empty for free surfaces
    default_technique: str          # soft default: "smooth" | "drybrush" | "nmm" | ""
    default_tone: str | None = None # key into tones; None -> first tone

    def base_tone_hex(self, tone: str | None) -> str | None:
        """Hex for a realistic surface's chosen tone; None for free surfaces."""
        if not self.tones:
            return None
        key = tone or self.default_tone or next(iter(self.tones))
        return self.tones.get(key) or next(iter(self.tones.values()))
```

**Vocabulary (v1).** Hexes are archetype anchors, mood-adjusted downstream; not final paints.

REALISTIC (base hue from tone, ignores harmony unless overridden):

| surface | default technique | tones (label → hex archetype) |
|---|---|---|
| `skin` | smooth | pale `#e8c0a0`, tan `#d29b73`, dark `#7a4a30`, olive `#b89a6a`, **orc-green `#6f8f4a`**, **drow-blue `#6a6f9a`**, **undead-grey `#9aa39a`**, **pale-blue `#a9c2cf`** |
| `bone` | smooth | ivory `#d8cbaa`, weathered `#b8a980`, dark `#8a7a55` |
| `metal` | smooth¹ | steel `#8a9099`, gold `#c9a83f`, bronze `#9a6f3f`, copper `#b5713f` |
| `wood` | smooth | walnut `#5b3d28`, oak `#8a6a44`, dark `#3f2c1d` |
| `leather` | smooth | dark-brown `#4a3423`, tan `#7a5638`, black `#2a2320` |
| `fur` | **drybrush** | brown `#5a4030`, grey `#7d7a72`, black `#2b2b2b`, white `#d8d4c8`, ginger `#a5673a` |

¹ Metal's *ideal* technique is NMM, but NMM is PS-only; the static default is `smooth` and the
panel suggests NMM when `normal_field` is present (see UI). Drybrush is also a common metal
choice — the default is soft and freely changed.

FREE (base hue from anchor + harmony):

| surface | default technique | tones |
|---|---|---|
| `cloth` | smooth | — |
| `cloak` | smooth | — |
| `robe` | smooth | — |
| `gem` | smooth | — |
| `accent` | smooth | — |
| `other` | `""` (no technique implication) | — |

`"other"` is the escape hatch: free-coloured (follows harmony) but implies no technique and no
realism. **Universal escape for realistic surfaces:** a realistic region can be made to follow
the harmony by setting its `tone` to the reserved key `"__harmony__"` (surfaced in the UI as a
“Follow scheme colour” option in the tone dropdown). This covers a fantasy skin the user wants
tied to the palette rather than a named fleshtone.

### `Region` / `RegionBook`

```python
@dataclass
class Region:
    name: str
    mask: np.ndarray
    palette: list[PaintColor]
    coverage: list[float]
    material: str = "matte"     # UNCHANGED — the TECHNIQUE field (smooth/drybrush/nmm/matte alias)
    surface: str = "other"      # NEW — the surface vocabulary key
    tone: str | None = None     # NEW — chosen tone key for realistic surfaces; None = default
```

`RegionBook` mirrors the existing `whole_material` / `material_at` / `set_material_at` pattern
with `whole_surface`, `whole_tone`, and `surface_at`/`set_surface_at`/`tone_at`/`set_tone_at`.
Index 0 (“Whole mini”) is a valid target like any region.

## The colour-decision layer — `scheme_gen.py`

**Harmony.** Given the anchor hue and how many free regions need a hue, offset via `hue_rotate`:

```python
_VARIANT_OFFSETS = {
    "complementary":      [180.0],
    "analogous":          [-30.0, 30.0, -60.0, 60.0],
    "triadic":            [120.0, 240.0],
    "split-complementary":[150.0, 210.0],
}

def harmony_hues(anchor_hex: str, variant: str, k: int) -> list[str]:
    """k hues for the non-anchor free regions, cycling the variant's offsets."""
    offsets = _VARIANT_OFFSETS.get(variant, _VARIANT_OFFSETS["complementary"])
    return [hue_rotate(anchor_hex, offsets[i % len(offsets)]) for i in range(k)]
```

The anchor region keeps the anchor hue. Non-anchor **free** regions receive `harmony_hues` in
region order. Cycling the `variant` re-rolls the free colours while realistic regions stay put —
this *is* the "give me the complementary" mechanic.

**Mood** = one HSV transform applied to *every* base hue after assignment (both buckets, for
cohesion), in HLS space like `hue_rotate`:

```python
_MOODS = {                # (sat_mul, light_mul, hue_shift_deg)
    "neutral":   (1.00, 1.00,   0.0),
    "grimdark":  (0.70, 0.78, +12.0),   # desaturate, darken, cool
    "heroic":    (1.18, 1.08,  -8.0),   # saturate, lighten, warm  (clamped)
    "natural":   (0.85, 0.98, -18.0),   # desaturate toward ochre/warm
}
```

`apply_mood` multiplies S and L (clamped to [0,1]) and rotates hue. **`generate_ramps`** ties it
together per region: resolve base hue (anchor hue / tone hex / harmony hex per bucket & override)
→ `apply_mood` → `ramp_from_midtone(base, n)` where `n = len(region.palette)` (ramp length
matches the region's existing band count). Returns `dict[region_name, list[hex]]`. **Paint-free.**

## The paint-mapping + assembly layer — `scheme_build.py`

Per ramp hex, reuse `matching.match(Target(hex), owned, catalog)`:

- tier `exact` / `close` → `result.paints[0]` (an owned paint).
- tier `mix` → a **synthetic** `PaintColor(name=result.phrase, hex=hex, ...)` — the intended
  colour with the mix recipe as its name; keeps the palette one-colour-per-band and shows the
  recipe in the legend.
- tier `unreachable` → `result.buy_hint` (nearest catalogue paint) when `owned_only` is False;
  when `owned_only` is True, fall back to the nearest owned single instead (no catalogue leak).

`build_scheme` runs `generate_ramps`, maps every region's ramp to a palette, and returns a
`schemes.Scheme(name, palettes={region_name: [PaintColor,…]})`. Applying it is the existing
`schemes.apply(scheme, book)`.

## UI — `ui/scheme_gen_panel.py`

A panel (expander/section) with:

- **Per region:** a **surface** selectbox; when the chosen surface is realistic, a **tone**
  selectbox (its tones + a “Follow scheme colour” = `__harmony__` option). Writes
  `book.set_surface_at` / `set_tone_at`.
- **Anchor:** a region selectbox (which region is the hero) + a `st.color_picker` (defaults to
  the midtone of that region's current palette).
- **Mood** selectbox and **harmony variant** selectbox (`complementary` default). A
  “Re-roll free colours” affordance = cycling the variant.
- **`Owned only`** checkbox (default off = owned-first with catalogue fallback).
- **Also set techniques from surface** checkbox (default on): on Apply, `set_material_at` per
  region from `SurfaceSpec.default_technique` (skipping `""`), NMM only offered when
  `normal_field is not None`.
- **Generate** → `build_scheme` → per-region swatch preview (reuse existing swatch rendering;
  on-mini preview via the already-shipped scheme-preview path) → **Apply** (`schemes.apply` +
  optional technique set). Post-generate, individual colours remain editable through the normal
  per-region palette editor; changing anchor/variant/mood and regenerating re-derives.

Mount point: alongside the scheme experimenter in `ui/results.py` (or `app.py`), guarded to
appear once regions exist.

## Persistence — `projects.py`

Serialize `surface` + `tone` per region (whole-mini included). Bump manifest schema v3 → v4.
Back-compat: a v3 (or older) project loads with `surface="other"`, `tone=None`; no migration
step required. The applied scheme itself already persists via the scheme-experimenter path.

## Testing strategy

**`tests/test_surfaces.py`** (pure): every SurfaceSpec has a valid bucket; realistic surfaces
have ≥1 tone and free surfaces have none; `base_tone_hex` returns a valid hex for realistic and
None for free; `get_surface("nope")` falls back to `"other"`; `skin` includes the fantasy tones.

**`tests/test_scheme_gen.py`** (pure): `harmony_hues` returns exactly `k` hues and the
complementary offset is ~180° in hue; `apply_mood("#808080", "grimdark")` lowers value & sat;
`generate_ramps` returns one ramp per region of length `len(palette)`; the anchor region's
midtone hue ≈ the anchor hue (mood aside); a realistic region ignores the harmony; a realistic
region with `tone="__harmony__"` follows it.

**`tests/test_scheme_build.py`** (pure, tiny fixed catalogue + collection): an in-collection
target resolves to an owned paint; an unreachable target with `owned_only=False` resolves to a
catalogue `buy_hint`; with `owned_only=True` it stays within the collection; a mix target yields
a synthetic `PaintColor` whose hex equals the target; `build_scheme` returns a `schemes.Scheme`
whose `palettes` keys match the region names and whose palette lengths match band counts.

**`tests/test_projects_surface.py`** (pure): round-trip a book with surfaces/tones through
save/load; a v3 manifest without the keys loads with defaults.

**`tests/test_ui_scheme_gen.py`** (AppTest): the panel renders once a region exists; picking a
realistic surface reveals the tone dropdown; Generate then Apply changes the book's palettes;
“Also set techniques” writes the surface default technique; NMM tone/technique only offered with
`normal_field`.

## Rollout / build order

1. **`surfaces.py`** + tests — pure vocabulary. No other file touched.
2. **`scheme_gen.py`** + tests — harmony, mood, ramps (hex only). Depends on `color.py` +
   `surfaces.py`.
3. **`scheme_build.py`** + tests — paint mapping + `schemes.Scheme` assembly. Depends on
   `matching.py` + `schemes.py`.
4. **`regions.py` / `region_state.py`** — `surface` + `tone` fields + accessors + tests.
5. **`projects.py`** — persistence + schema v4 + back-compat tests.
6. **`ui/scheme_gen_panel.py`** + mount + AppTest — the visible payoff.

Steps 1–3 are the engine and fully testable headless; 4–6 wire it into the app. Each step is
independently committable.

## Self-review

**Placeholder scan:** no TBD; vocabulary table complete for all listed surfaces; every mood and
variant has concrete numbers.

**Consistency:** `Region.surface`/`tone` (new) is kept strictly separate from `Region.material`
(the technique field). Surface → technique is applied only on Apply, only when the user leaves
“Also set techniques” on, and is freely overridden after. The colour-decision layer
(`scheme_gen`) never imports `matching`/`collection`; paint mapping lives only in
`scheme_build`. Output is the existing `schemes.Scheme` — one manufacturing front-end, no new
downstream.

**Scope:** two pure engine modules + one glue module + Region/persistence extension + one panel.
Larger than the technique slice but coherent; each build step is isolated. Right-sized for one
plan.

**Ambiguity check:** "owned-first not owned-only" is pinned to the `match` tier ladder;
`owned_only` behaviour is specified per tier. "Realistic doesn't mean natural" is pinned via
fantasy tones + the `__harmony__` escape. Ramp length = region band count, stated explicitly.

**Back-compat:** old projects load with `surface="other"`, `tone=None`; `get_surface` falls back
to `"other"`; a region left as `"other"` follows the harmony and forces no technique — the inert
default.
