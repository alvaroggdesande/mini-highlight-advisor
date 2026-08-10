# Palette Matcher & Mix Advisor — Design

**Date:** 2026-08-10
**Status:** Approved design (ready for implementation plan).
**Roadmap lineage:** Implements ideas **#3 (paint-mixing + water)** and **#2 (consistency
notes)** from `2026-08-09-roadmap-and-idea-assessment.md`. Both were parked *downstream
of own-palette input (#4)*, which is now shipped (`collection.py`, `catalog.py`,
`recipes.py`). This is the next step in the "your paints & techniques" arc.

## Problem

You have a set of colours you *want* to paint — the band colours the engine derives
from your photo, the steps of a recipe, or a colour you point at. You then have to
work out, by eye, how to reproduce each one from the paints you actually own: use it
directly, substitute the closest thing, or mix. Today the tool suggests a palette but
never reconciles it against your real inventory, and gives no thinning/consistency
guidance.

Two distinct usage patterns fall out of this (captured now, acted on later — see UI):

- The **mix/inventory answer** is consulted *once*, while you prep your paints.
- The **highlight map** is stared at *for days* while you paint, checked constantly
  against the physical model.

## Goal

A pure matching engine that, given a target colour, tells the painter how to hit it
with the paints they own — plus honest consistency guidance — exposed through a
minimal UI that can be re-homed into a proper two-mode layout later.

## Non-goals / out of scope

- Physically-accurate pigment mixing (Kubelka-Munk / spectral). Explicitly rejected:
  mixing is guidance-only and honest, never a rendered "accurate" mixed swatch.
- Techniques (layering/OSL/NMM/edge) — idea #9, separate future design.
- Per-material regions — idea #1, separate future design.
- The full "Prep view vs Paint view" UI split — noted below as future work; this
  design ships the simplest possible surface.

## Concepts

### Target normalisation

Every source reduces to a single normalised target:

```
Target = (hex: str, preferred_code: str | None)
```

- **Plan band colours** → `(band_hex, None)`.
- **Recipe steps** → `(step.hex, step.paint_ref)` — `paint_ref` is the preferred code
  when the recipe names a specific paint.
- **Ad-hoc picked colour** → `(picked_hex, None)`.

### Inventory

Matching is against **owned paints only** — the intersection of `collection.load(...)`
(owned codes) with `catalog.load_catalog(...)` (resolved to `PaintColor`s). This is the
"what do I have" answer, so owned-only is correct. The full catalogue is used only for
the buy-hint (below).

### Colour distance

All proximity is measured as **CIEDE2000 (ΔE00) in CIELab**, converting from the sRGB
hex via `PaintColor.rgb`. Rationale: perceptually uniform, and single-paint matching
has no mixing nonlinearity, so this tier is genuinely accurate. A single tunable module
constant `CLOSE_THRESHOLD` (default **ΔE00 ≈ 5**) separates tier 2 from tier 3.

> Implementation note: prefer a small, well-tested colour-conversion routine (sRGB→Lab
> + CIEDE2000). If a dependency is added it must be lightweight and offline (the tool
> stays offline/free). A vendored ~40-line implementation is acceptable and avoids a
> dependency.

## The matching engine — `matching.py` (pure)

`match(target, owned, catalog) -> MatchResult`. Resolves each target into exactly one
of four **honesty tiers**:

1. **Exact** — `preferred_code` is owned, OR an owned paint is within a hair
   (ΔE00 ≤ ~1). Phrase: "Use *Ironbreaker* (72.054)."
2. **Close single** — nearest owned paint with ΔE00 ≤ `CLOSE_THRESHOLD`. Phrase names
   the paint and the direction of the small deviation ("slightly warmer / darker").
3. **Mix** — no single owned paint is close enough. Pick **two owned paints that
   bracket the target** (one darker, one lighter; nearest in hue), expressed as **rough
   integer parts** ("~2 parts X + 1 part Y"). Where useful, express as
   lighten/darken with an owned white/black ("X + a touch of white"). **Labelled
   approximate. No mixed swatch is rendered as if accurate.**
4. **Unreachable** — no acceptable single or bracketing mix exists in the inventory.
   State it plainly and name the nearest owned paint with its ΔE00, **plus a buy-hint:
   the closest paint in the full catalogue you don't own** ("...or buy *Z*").

### `MatchResult` (shape)

```
MatchResult:
  tier: "exact" | "close" | "mix" | "unreachable"
  target_hex: str
  paints: list[PaintColor]        # 1 for exact/close, 2 for mix, nearest-owned for unreachable
  parts: list[int] | None         # e.g. [2, 1] for mix, else None
  delta_e: float                  # ΔE00 of the recommendation vs target
  buy_hint: PaintColor | None     # populated only for unreachable
  phrase: str                     # short human sentence
```

Pure: no Streamlit, no file I/O. Deterministic. `delta_e` for a mix is a rough
indicator only (of the linear estimate) and is presented as approximate.

## Consistency notes — `consistency.py` (pure)

`annotate(result, role) -> str` produces one short working-consistency line by
composing up to three independent, static rule sets (dict/keyword lookups, no ML):

1. **Per-role dilution** — keyed off the plan's role name:
   - Shadow / Base → "2 thin coats, milk-like."
   - Midtone / Highlight → "thinned more, build up gradually."
   - Edge Highlight → "thinned, fine controlled tip / near-dry."
2. **Water ratio for mixes** — only when `tier == "mix"`: append working dilution so the
   mix and its thinning read as one instruction.
3. **Paint-type caveats** — matched on catalogue `paint_range` / `name` substrings:
   metallic → "settles, stir often"; white / yellow / low-opacity → "expect extra
   coats"; ink / wash / contrast → "flows, one pass."

A band can trigger 0–3 rules; matches concatenate into one line. Purely additive — no
match, no note. Rule tables live as module constants, easy to extend.

## Data flow

```
                         owned paints (collection.py + catalog.py)
                                        │
   ┌─ plan band colours ──┐            ▼
   ├─ recipe steps ───────┼──► normalize to Target ──► matching.py ──► MatchResult (per target)
   └─ ad-hoc picked hex ──┘                                  │
                                                             ▼
                                       consistency.py annotates (role + tier + paint-type)
                                                             │
                                                             ▼
                                      minimal Streamlit section (one row/expander per band)
```

Adapters are thin: no new persisted data model; the plan, recipes, and a hex input all
already exist or are trivial.

## UI (minimal now, re-homed later)

- One results section: **one row / expander per target (band)** showing tier phrase,
  the paint chip(s), mix parts if any, and the consistency line.
- Deliberately dumb and self-contained so it can later be split into the **Prep view**
  (dense, consulted once) vs **Paint view** (clean, large highlight map, live for days)
  without touching the engine. That split is **future work**, explicitly not in this
  design.

## Testing

Pure modules make this straightforward; all tests offline and deterministic.

- **`matching.py`**: each tier hit deliberately with hand-built owned sets — exact via
  `preferred_code`; exact via near-zero ΔE; close within threshold; mix bracketing
  (verify two paints, plausible parts, approximate flag); unreachable (verify buy-hint
  names a catalogue paint not owned). Threshold boundary tests around `CLOSE_THRESHOLD`.
- **Colour distance**: known sRGB→Lab / ΔE00 reference pairs to pin the conversion.
- **`consistency.py`**: each rule set in isolation (role dilution, mix water ratio,
  paint-type caveats) and composition (0, 1, and 3 rules firing).
- **Adapters**: recipe step with/without `paint_ref` normalises correctly; plan band
  hex and ad-hoc hex normalise to `(hex, None)`.

## Files

- **New:** `src/mini_highlight_advisor/matching.py`, `consistency.py`, and a colour
  conversion helper (vendored in `matching.py` or a small `color.py`).
- **New tests:** `tests/test_matching.py`, `tests/test_consistency.py`.
- **Touched:** `app.py` (minimal results section + ad-hoc hex input); possibly small
  helpers where the plan exposes band hexes and recipes expose steps.
- **Unchanged data models:** `palette.py`, `catalog.py`, `collection.py`, `recipes.py`.

## Open tunables (sane defaults, easy to change)

- `CLOSE_THRESHOLD` — ΔE00 boundary between close-single and mix. Default ≈ 5.
- Exact near-hair threshold — ΔE00 ≈ 1.
- Mix parts granularity — small integer parts (cap denominator low, e.g. ≤ 4) to keep
  guidance practical.
