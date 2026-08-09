# Own-Palette Input (#4) — Design

**Date:** 2026-08-09
**Status:** Approved design — ready for implementation plan.
**Feature ID:** #4 in `2026-08-09-roadmap-and-idea-assessment.md`.

## Purpose

Replace the raw hex-per-slot palette editor with **fast, accurate palette
assembly from real paints**, and capture **which paints the user owns**. This is
the cheapest enabler in the roadmap: it establishes the two things paint-mixing
(#3) needs — the *want* (a target palette) and the *have* (owned paints) — and
its bundled paint catalogue is the seed for the multi-brand paint DB (#5).

The dependency this unblocks, verbatim from the roadmap:

```
own-palette input (#4) ──┬──> paint-mixing suggestions (#3)
                         └──> multi-brand paint DB (#5)
```

Mental model: *"I want these 5 colours; I own 3 of them; later, tell me how to
mix the other 2."* This feature builds everything up to (and including flagging)
"I own 3 of them." The "how to mix" step is #3 and is **out of scope here** — but
the seam it plugs into is built.

## Constraints (inherited, non-negotiable)

- **Offline / free at runtime.** No live API lookups. The paint catalogue ships
  as a static JSON in the package.
- **Primed / monochrome minis only; whole mini = one region.** Unchanged by this
  feature — this is purely about how the palette is assembled *before* `analyze`
  runs. The `analyze` pipeline is untouched.
- **Vallejo** is the first (and, for v1, only) catalogue brand — it is the user's
  actual paint range. Citadel becomes the later proof that #5's "add a brand"
  path works.

## Core concepts (data model)

Three distinct colour concepts:

- **`Paint`** — a catalogue entry: `name`, `brand` (`"Vallejo"`), `range` (e.g.
  `"Model Color"` / `"Game Color"`), `hex`. Extends today's `PaintColor` (name +
  hex) with `brand` / `range` as optional fields so existing call-sites keep
  working.
- **`Recipe`** — a *named, value-ordered* scheme: a `name` plus an ordered list of
  **steps**, each `{label, hex, paint_ref?}`. A step is a *target colour* that may
  reference a catalogue paint (`paint_ref`) or be a free target (mix toward it
  later). A recipe **carries its own length**.
- **Owned collection** — the set of catalogue paints the user marks "I own this."
  This is the *have*.

### Recipe ↔ band count

A recipe carries its own length. **Loading a recipe sets the band count to match
and drops its steps into the slots 1:1.** No resampling of recipes to arbitrary
band counts (rejected: you can't half-own a paint, and "resampling paints" is
fuzzy). For v1, recipe length must fall within the supported band range (**3–5**,
matching `role_names`); built-in starters are authored within that range.

## Files

| File | Location | Committed? | Purpose |
|------|----------|-----------|---------|
| `data/vallejo_paints.json` | in package (`src/mini_highlight_advisor/data/`) | ✅ yes | bundled catalogue — the picker source; seed for #5 |
| `data/recipes_builtin.json` | in package | ✅ yes | shipped starter recipes (e.g. NMM Copper) — read-only |
| `user_data/collection.json` | repo-local | no (personal, local) | the user's owned paints |
| `user_data/recipes.json` | repo-local | no (personal, local) | recipes the user saves |

**Builtin-vs-user recipe split (chosen):** keep **both** files. The app shows
builtin + user recipes **merged** in the load list; "Save as recipe" **always**
writes to `user_data/recipes.json`. Rationale (single-user): starter recipes stay
safe from accidental edits/deletion, and new starters can ship in app updates
without clobbering the user's saved recipes. Cost is ~identical either way.

**Future upgrade (noted, not built):** the catalogue could be fetched online
instead of bundled. Out of scope now.

## Sourcing the catalogue (dev-time, one-time)

The app is offline *at runtime*; **building** `vallejo_paints.json` is a one-time
dev-time task during implementation: fetch a community Vallejo name→hex list,
clean it, commit the JSON.

- **Hex accuracy caveat (bake into the data + a code comment):** these are
  screen-swatch approximations, not spectrophotometer-accurate. Good enough for
  value-ordering and picking; do not present them as exact.
- **Catalogue size is a data decision, not an architecture decision.** The code
  just loads a JSON. Start with a **small curated set** (the user's actual paints
  + all colours referenced by the built-in recipes) and grow the JSON anytime
  with **zero code change**. Do not block the build on a complete Vallejo dump.

## Modules (`src/mini_highlight_advisor/`)

UI-agnostic core preserved — all logic is plain data + pure functions, no
Streamlit.

- **`palette.py`** (extend) — `PaintColor` gains optional `brand` / `range`
  (defaults preserve existing call-sites). Swap `DEFAULT_PALETTE` from Citadel
  greys to **Vallejo** greys/metals (so defaults are pickable/ownable within the
  Vallejo catalogue).
- **`catalog.py`** (new) — loads `data/vallejo_paints.json` → `list[Paint]`;
  lookup/search helpers (`by_name`, substring search). Pure data access.
- **`recipes.py`** (new) — `Recipe` dataclass + `load_builtin()`, `load_user()`,
  `save_user(recipe)`, and `to_palette(recipe) -> list[PaintColor]` (for dropping
  a recipe into the band slots).
- **`collection.py`** (new) — the owned set: `load()`, `save(owned)`, membership
  test, against `user_data/collection.json`.
- **`annotate_ownership(palette, owned) -> list[SlotStatus]`** (pure function;
  home it in `collection.py` or `palette.py`). Each `SlotStatus` =
  `{paint, owned: bool, nearest_owned: PaintColor | None}`.
  - `owned` — surfaced now as the badge.
  - `nearest_owned` — **computed but NOT surfaced.** Pure nearest-hex (Euclidean
    RGB) among owned paints. This is the one field pre-wired ahead of need: it is
    the entire seam #3/mixing consumes, and costs nothing.

`pipeline.analyze(rgb, alpha, palette)` is **unchanged**.

## UI (`app.py`)

Two surfaces.

### Sidebar — "My paints" (owned collection)

Searchable multiselect over the catalogue; selections persist to
`user_data/collection.json` on change. This is the *have*, set once and rarely
touched.

```
┌── My paints ────────────────┐
│ Search: [ burnt____ ]        │
│ ☑ Burnt Umber      #4A3527   │
│ ☑ Beige Red        #EAA88C   │
│ ☐ Orange Brown     #A75A38   │
│ (12 owned) — saved automatically │
└──────────────────────────────┘
```

### Main — Palette section (the *want*, assembled before `analyze`)

```
Bands: [ 5 ▾ ]     Load recipe: [ NMM Copper ▾ ]   ← sets bands + fills slots

  Role            Paint (Vallejo)              Hex        Owned
  ─────────────────────────────────────────────────────────────
  Shadow          [ Charred Brown        ▾ ]   ■ #3D2A25   ✓
  Base            [ Orange Brown         ▾ ]   ■ #A75A38   ⚠ not owned
  Midtone         [ Bright Orange        ▾ ]   ■ #E15E32   ✓
  Highlight       [ Beige Red            ▾ ]   ■ #EAA88C   ✓
  Edge Highlight  [ (custom target)      ▾ ]   ■ #F5F5F3   ⚠ not owned

  Recipe name: [ My NMM Copper____ ]  [ Save as recipe ]
```

Interactions:

- **Paint dropdown** per slot — searchable catalogue list; picking fills the hex
  (no typing). A `(custom target…)` option retains manual hex entry for targets
  not in the catalogue (e.g. recipe steps to mix toward). This preserves today's
  hex editor as the fallback path, no longer the primary one.
- **Load recipe** — merged builtin + user list; loading sets band count to the
  recipe's length and fills the slots 1:1.
- **Owned column** — `✓` if the slot's chosen paint is in the collection;
  `⚠ not owned` otherwise (including `(custom target)` slots, which can't be
  owned). Flag only — **no mixing suggestion**.
- **Save as recipe** — names the current slots and writes to
  `user_data/recipes.json`.

## Out of scope (deferred — flagged, not silently cut)

- **Paint-mixing suggestions (#3)** — the "mix these 3 to approximate the one you
  don't own." This feature only *flags* the gap and pre-computes `nearest_owned`.
- **Surfacing `nearest_owned`** — computed, not shown.
- **Multi-brand catalogue (#5)** — Vallejo only; the bundled JSON is #5's seed.
- **Coverage sliders (#6)** and **raising the band cap past 5 (#7)** — separate
  features; band range stays as today (3–5, default 5).
- **Online catalogue fetch** — future upgrade; catalogue is bundled JSON now.

## Testing

Pure-core modules are fully unit-testable without Streamlit (repo convention):

- `catalog.load()` — parses the bundled JSON; known paint resolves to expected
  hex; search matches by substring.
- `recipes` — `load_builtin()` returns the shipped starters; `save_user()` then
  `load_user()` round-trips a recipe; `to_palette()` yields the right ordered
  `PaintColor`s; merged list contains both sources.
- `collection` — `save()`/`load()` round-trips the owned set; membership test.
- `annotate_ownership()` — owned paint → `owned=True`; unowned → `owned=False`
  with `nearest_owned` = the correct closest owned paint by RGB distance;
  `(custom target)` slot → `owned=False`, `nearest_owned` handled gracefully
  (may be None if collection empty).
- `palette.PaintColor` — new `brand`/`range` optional fields default cleanly;
  existing construction (name + hex only) still works; `DEFAULT_PALETTE` is
  Vallejo and every entry resolves in the catalogue.

App wiring (Streamlit) is verified manually (`streamlit run app.py`) per repo
practice — not unit-tested.

## Acceptance criteria

1. A paint can be chosen from a Vallejo dropdown and its hex auto-fills; no manual
   hex entry required for catalogued paints.
2. `(custom target)` still allows manual hex entry for non-catalogue colours.
3. Owned paints persist across app restarts (`user_data/collection.json`).
4. Loading a built-in recipe (e.g. NMM Copper) sets the band count and fills all
   slots with the recipe's colours in value order.
5. Saving the current palette as a named recipe persists it
   (`user_data/recipes.json`) and it appears in the load list on restart,
   alongside the built-in starters.
6. Each slot shows an owned/not-owned badge driven by the collection.
7. `nearest_owned` is computed by `annotate_ownership` but not shown anywhere in
   the UI.
8. `analyze` and existing tests are unaffected.
