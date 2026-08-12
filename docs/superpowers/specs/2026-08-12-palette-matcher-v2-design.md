# Palette-Matcher v2 — Design

**Date:** 2026-08-12
**Status:** Approved design (ready for implementation plan).
**Scope:** Ideas #1 (finish/metallic flag) + #2 (multi-paint mixes) from the
roadmap's "palette-matcher v2" note. Idea #3 (geometry-driven edge highlight) is
**explicitly out of scope** — it is a `banding.py`/mask-geometry change and gets its
own spec.

## Purpose

The matcher today (`matching.py`) maps each desired palette colour to *what you own*:
exact → close single → 2-paint mix → unreachable+buy-hint. Two gaps limit it:

1. **It is finish-blind.** It will happily propose mixing a matte paint into a
   metallic target (or vice-versa), and it sniffs "metallic" from the paint *name*
   (`consistency.py`), which is fragile.
2. **Mixes are pairs only**, with a naive sRGB average the roadmap already flags as
   inaccurate.

v2 adds a real **finish** property to the catalogue and teaches the mixer the physics
of finishes, and extends mixing from 2 to (capped, ΔE-gated) 3 paints with a more
honest blend model.

## Non-goals

- **No band-curve / technique presets.** "NMM/TMM/layering rules" here means *mixer
  guardrails + notes*, not reshaping banding. Band-curve techniques belong with the
  parked geometry/banding work.
- **No geometry-driven edge highlight** (idea #3 — separate spec).
- **No new region UI.** Finish rides on the paint the user already picks per slot.
- **No spectrophotometric colour accuracy.** Hexes remain approximate screen-swatches;
  the mixer output is guidance, always labelled "approx".

## The finish model

### `PaintColor.finish`
Add `finish: str = "matte"` to the frozen `PaintColor` dataclass. Allowed values:

| finish | meaning | mixer role |
|--------|---------|------------|
| `matte` | opaque flat paint (default) | full base-mix ingredient |
| `metallic` | metal-flake paint | base-mix ingredient (metallic-only pool) + tint target |
| `wash` | transparent flow/shade | **never a mix ingredient**; single-match / notes only |
| `contrast` | transparent one-coat | **never a mix ingredient**; single-match / notes only |

### Catalogue (`catalog.py`)
- `load_catalog` reads `p.get("finish", "matte")`.
- `validate_catalog` gains a check: `finish`, if present, must be in the allowed set;
  else `ValueError` naming the entry (same style as existing checks).
- **Default-on-load = matte**, so the ~160 genuinely matte entries need no JSON edit.

### `Target.finish` (`matching.py`)
`Target` gains `finish: str = "matte"`.
- `target_from_paint(paint)` → inherits `paint.finish`.
- `target_from_hex` / `target_from_recipe_step` → `matte` (ad-hoc hex and recipe steps
  carry no finish, so they never pull metallics into a match).

## Matching rules

### Single / close / nearest — same-finish only
The candidate pool for the single-match tiers is filtered to paints whose `finish`
equals the target's finish. Rationale: you cannot match a metallic target with a flat
paint, nor a flat target with a metal. Concretely:

- metallic target → ranked only against metallic owned paints;
- matte target → matte only;
- wash target → wash only; contrast target → contrast only.

If the same-finish owned pool is empty, the target falls straight through to the mix
tier (if legal) or unreachable.

### Buy hint (unreachable tier)
Drawn from the catalogue **within the target's finish family** (a metallic target that
can't be matched suggests buying a metallic, never a matte).

## Mixing rules (the finish asymmetry)

Mixing is only attempted for `matte` and `metallic` targets. `wash`/`contrast` targets
never mix.

### Matte target
Ingredients are **matte only**. Metallic is forbidden; wash/contrast are excluded (they
can't build an opaque base). This is the existing behaviour, now enforced by flag
instead of accident.

### Metallic target (asymmetric — the user's rule)
> "for a matte ending, never add metallic. for some metallic, a tint of other colour
> can help slightly."

A metallic mix is one of:
- **all-metallic**: 2–3 metallic paints (e.g. `Sterling Silver + Obsidian Black` for a
  metallic shadow); or
- **metallic + one minority tint**: metallic base(s) plus a *single* non-metallic
  coloured paint, where the **metallic parts strictly exceed the tint part** (the tint
  is always the ratio minimum — e.g. `3:1`, `2:1`, `2:1:1`). Models "a drop of ink to
  shift the metal's hue."

At most one tint ingredient; the tint may be any non-metallic paint.

## Mix engine (2 → 3 paints, bounded, ΔE-gated)

### Bounded candidate search
To keep cost independent of collection size:
- Build the **base pool** = the top-`K` (=8) nearest legal singles by ΔE within the
  target's finish family.
- For metallic targets additionally build a **tint pool** = the top-`T` (=4) nearest
  *non-metallic* owned paints.
- Enumerate 2- and 3-paint blends only among these pools.

### Ratios
One generator produces integer part-tuples `(a, b[, c])`, each part ≥ 1, **sum ≤ 4**
(reproducible at the bench: "2:1", "2:1:1"). This subsumes today's pair ratios
`[(1,1),(2,1),(1,2),(3,1),(1,3)]` and yields the triples `(1,1,1),(2,1,1),(1,2,1),
(1,1,2)`. For metallic+tint blends, only tuples whose minimum part is the tint slot are
legal (enforces tint-minority).

### Blend model — linear-light
Replace the naive sRGB average with: sRGB → linear RGB, average channels weighted by
parts, → sRGB, then ΔE00 against the target. Cheap, strictly more physically honest.
Output is still labelled "approx" (pigment mixing ≠ additive light).

### Acceptance & tiers
- A **2-paint** mix is accepted only if it beats the nearest legal single (unchanged
  rule) and is ≤ `MIX_ACCEPT_THRESHOLD` (8.0).
- A **3-paint** mix is accepted only if it beats the *best 2-paint* mix by
  **ΔE ≥ 1.0** *and* is ≤ `MIX_ACCEPT_THRESHOLD`. Complexity must earn its keep; a
  3-paint blend is materially harder to reproduce than a 2-paint one.
- Tier order is unchanged: `exact → close → mix → unreachable`. The `mix` tier now
  spans 2–3 paints and metallic tints. `MatchResult.paints`/`parts` already carry
  arbitrary-length lists, so no shape change beyond populating 3 entries.

### Phrasing (`matching.py` + `consistency.py`)
- `"Mix 2:1 Sterling Silver + Imperial Gold (approx)."`
- `"Mix 3:1 Sterling Silver + a touch of Blue (tint, approx)."`
- `"Mix 2:1:1 …"` for a genuine triple.
- `consistency.py._paint_type_caveat` switches from keyword-sniffing to the real
  `finish` flag, keeping the keyword fallback only for finish-less custom paints.

## UI (`app.py`)

No new selectors. Finish is read from the catalogue paint chosen per slot; ad-hoc hex
slots are matte. Advice rows already render the consistency note, which now becomes
finish-accurate. A small finish badge next to a slot is a **nice-to-have, not
required** for this spec.

## Catalogue data work (`vallejo_paints.json`)

This is a **curation pass across all 244 entries**, not a single-range tag:

1. **Tag every metallic**, wherever it lives. Real metallics already sit in the "matte"
   ranges (`Silver 70.997`, `Oily Steel`, `Gunmetal Grey/Blue`, any Gold/Bronze). An
   automated first pass proposes tags from name+range heuristics; the ambiguous ones
   are surfaced for the user to confirm. Tag the `True Metallic Metal` range as
   `metallic`.
2. **Leave matte entries untouched** (default-on-load handles them).
3. Wash/contrast families stay valid-but-empty (no such entries yet).

### Data caveats (non-blocking, recommend a later data pass)
- The hand-built TMM range uses **invented codes** (real Vallejo Metal Color is
  77.7xx) and **repeats each colour name across ~4 fabricated lightness levels**. The
  matcher tolerates this (codes are unique; `validate_catalog` allows repeated names),
  but **buy-hints will cite invented codes**.
- With the metallic mixer in place, most fabricated lightness levels become
  **redundant** — a metallic shadow/highlight is now `metallic + Obsidian Black`/lighter
  metallic, and a hue shift is `+ coloured tint`. Recommend collapsing each metallic to
  its **real single SKU** in a follow-up data pass. Not required for the engine to work.

## Modules touched

- `palette.py` — add `finish` field to `PaintColor`.
- `catalog.py` — load + validate `finish`.
- `matching.py` — `Target.finish`; finish-filtered candidate pools; metallic tint rule;
  top-K/top-T bounding; linear-light blend; 3-paint search + ΔE gate; phrasing.
- `consistency.py` — flag-based caveat with keyword fallback.
- `color.py` — add `linear_blend(rgbs, parts)` helper (sRGB↔linear round-trip).
- `data/vallejo_paints.json` — finish curation pass.
- `app.py` — no functional change required (finish flows through `target_from_paint`);
  optional finish badge deferred.

## Testing

- **Catalogue:** `finish` defaults to matte when absent; `validate_catalog` rejects an
  out-of-set finish; a known metallic (e.g. `Silver 70.997`) is tagged after curation.
- **Same-finish matching:** a matte target never returns a metallic single/close; a
  metallic target ranks only against metallics.
- **Mixer guardrails:** matte target mix never contains a metallic; metallic mix keeps
  metallic-majority; tint is always the minority part; at most one tint ingredient;
  wash/contrast never appear as ingredients.
- **Bounding:** search is independent of owned-collection size (top-K/top-T honoured).
- **Blend:** `linear_blend` round-trips and differs from the old sRGB average on a
  known case; ΔE of a linear blend is computed on the linear result.
- **3-paint gate:** a triple that beats the best pair by ≥1.0 is chosen; one that beats
  it by <1.0 is rejected in favour of the pair.
- **Phrasing snapshots:** 2-paint, 3-paint, metallic-tint, all-metallic.
