# Scheme Experimenter — Design Spec

**Date:** 2026-09-01
**Status:** Approved shape, ready for implementation plan
**Classification:** Architectural (new subsystem: scheme model + persistence + UI panel)

## Context

The photometric-stereo spike (now cashed via Fork B) gives the app the
miniature's true **relief** (`normal.png`) independent of paint state. The
render engine already paints *synthetic* colour onto that relief with correct
highlight placement — that is exactly what the app does today for a single
palette-per-region setup.

The core user goal has always been: **"where do the highlights land when I have
5–6 colours?"** Today you answer that for one colour setup at a time. This
feature lets the user **save the current colour setup as a named scheme, keep
several, and swap the whole mini's colours in one click** to compare where the
highlights fall under each. It is forward-looking and assistive (plan before you
paint), works on **primed minis** (no real albedo required — colour is chosen),
and cashes the relief investment in a visible, immediate way.

This is scope **(a): fast manual swapping**. Scope **(b): scheme suggestion**
("pick one anchor colour → suggest/choose the rest") is a later evolution; the
data model here is shaped so (b) slots in without a rewrite.

## Goals

- Save the current per-region palette setup as a **named scheme**.
- Keep a list of schemes and **apply** any one with a single click, re-rendering
  the mini (preview + written guide + step images) in those colours.
- **Persist** schemes inside the mini-project so they survive save/reload.
- Handle **region mismatch** gracefully (schemes applied after regions changed).
- Shape the model for the future anchor→suggest evolution (b).

## Non-goals (this slice)

- No scheme **suggestion / generation** (that is (b)).
- No **side-by-side / gallery** comparison — quick-swap (single preview) only,
  per the chosen UX.
- No capture of **coverage or material** in a scheme — a scheme is a *colour*
  story (palette only). Coverage/material remain live per-region settings.
- No **cross-project** reusable scheme library (that is Approach B, deferred).
- No albedo / painted-mini palette *extraction* (separate, deferred fast-follow).

## The chosen approach: per-project palette snapshot, keyed by region name

A scheme is a named snapshot of `{region_name → palette}` stored inside the
current mini-project. Applying it writes each region's palette back onto the
matching region in the **active angle's** `RegionBook`, then the existing render
runs. No new rendering math.

Region identity is the region **name** (`WHOLE_MINI` for index 0; the
user-given name for drawn regions), because `Region`/`RegionBook` carry no
stable id. Name-keying also lets one scheme apply across a project's multiple
angles when their region names match — a free bonus, not a requirement.

Rejected alternatives:
- **Global reusable scheme library** (cross-mini): needs a separate store and
  cross-mini region matching — real complexity for a payoff not yet requested.
  Deferred; a per-project scheme can be "promoted" later.
- **Save-as project copies per idea**: bloats storage, gives no real swap concept.

## Data model

New torch-free core module `src/mini_highlight_advisor/schemes.py`:

```python
@dataclass
class Scheme:
    name: str
    palettes: dict[str, list[PaintColor]]   # region_name -> palette snapshot
    anchor: str | None = None               # region_name; unused in (a), drives (b)
```

Pure functions (no Streamlit):

- `snapshot(book: RegionBook, name: str, anchor: str | None = None) -> Scheme`
  — read `book.names()` and `book.palette_at(g)` for every region into a
  `Scheme`. Palette is **deep-copied** so later edits don't mutate the snapshot.
- `apply(scheme: Scheme, book: RegionBook) -> ApplyReport` — for each region
  index `g` in `book`, if `book.names()[g]` is a key in `scheme.palettes`, call
  `book.set_palette_at(g, deepcopy(palette))`. Return a report of which region
  names were updated, which book regions were left untouched (no key), and which
  scheme keys matched no region.

```python
@dataclass
class ApplyReport:
    updated: list[str]          # region names written
    skipped_regions: list[str]  # regions in book with no scheme entry
    unused_keys: list[str]      # scheme keys matching no region
```

`apply` never raises on mismatch — it applies what it can and reports the rest.
Duplicate region names: apply the scheme's palette to **every** region with that
name (RegionBook does not enforce unique names).

Palette-length note: `apply` does not require the snapshot palette length to
equal the region's current band count (`n`). The palette list is replaced
wholesale; the render path already tolerates palette length via existing
coverage/ramp handling. (If this proves wrong in testing, `apply` truncates/pads
against the region's current coverage length — decide during implementation from
a real test, not assumption.)

## Persistence

Schemes live at **project level** in `manifest.json`, alongside `paints_pool`.
Bump `SCHEMA_VERSION` 2 → 3.

- `save_project(...)` gains a `schemes: list[Scheme]` argument, serialized via a
  `_scheme_to_dict` / `_scheme_from_dict` pair that reuses the existing
  `_palette_to_dicts` / `_palette_from_dicts` helpers.
- `LoadedProject` gains `schemes: list[Scheme]`.
- `load_project` reads `m.get("schemes", [])` — **absent = empty list**, so v2
  projects and the v1 adapter load unchanged (schemes default empty).
- No new files on disk; schemes are small JSON inside the existing manifest.

Manifest shape (added key):

```json
{
  "schema_version": 3,
  "schemes": [
    {"name": "Crimson Guard",
     "anchor": "armour",
     "palettes": {"Whole mini": [ ...paint dicts... ],
                  "armour":     [ ...paint dicts... ]}}
  ]
}
```

## UI — quick-swap panel

New module `ui/schemes_panel.py`, placed beside the region editor. Session state
holds the scheme list (new key in `ui/keys.py`, e.g. `SCHEMES`).

Panel contents:
- **Saved schemes** as a single-select list (radio). Selecting one and clicking
  **Apply** writes its palettes onto the active book and reruns → preview + guide
  + steps re-render in those colours.
- **＋ Save current as scheme** — text input for the name + button; snapshots the
  current book. Empty/duplicate name → inline validation (reuse a `slugify`-style
  check for non-empty; duplicate names prompt overwrite-or-rename).
- **Rename** and **Delete** per scheme.
- After Apply, show the `ApplyReport` as a small non-blocking note when anything
  didn't match, e.g. *"2 of 3 regions updated — 'gold trim' had no saved
  colour."* No silent partial application.

The active working palette is always live; schemes are snapshots you flip
between. Applying overwrites the current per-region palettes (the user saves
first if they want to keep the current setup — matching the existing
save-then-experiment flow).

## Data flow

```
edit region palettes (as today)
  └─ "Save current as scheme"  → schemes.snapshot(book, name) → append to session SCHEMES
select a scheme + Apply
  └─ schemes.apply(scheme, book) → book palettes overwritten → st.rerun
       └─ existing analyze_regions render → preview + guide + step images update
save project
  └─ save_project(..., schemes=session.SCHEMES) → manifest.json (schema v3)
load project
  └─ LoadedProject.schemes → session SCHEMES
```

## Error handling

- **Region mismatch** (regions changed after a scheme was saved): `apply`
  matches by name, applies what it can, and the panel surfaces the `ApplyReport`.
- **Empty scheme name**: inline validation, no save.
- **Duplicate scheme name**: prompt overwrite or rename; never two schemes with
  the same name silently.
- **Old projects** (schema < 3): load with `schemes = []`; no migration needed.
- **Corrupt scheme entry** in manifest: skip that entry on load (mirrors
  `list_projects`' tolerant `except (JSONDecodeError, KeyError): continue`), rest
  of project loads.

## Testing

`schemes.py` is pure → real unit tests (no Streamlit):

- `snapshot` then `apply` onto the same book is a no-op on palettes (round-trip).
- `apply` after **renaming** a region → that region reported in
  `skipped_regions`; the renamed-away key in `unused_keys`.
- `apply` after **removing** a region → remaining regions updated; removed
  region's key in `unused_keys`.
- `apply` after **adding** a region → new region in `skipped_regions`.
- `snapshot` deep-copies: editing the book after snapshot does not change the
  scheme; applying a scheme then editing a region does not change the scheme.
- Duplicate region names → palette applied to every matching region.

Persistence round-trip:
- `save_project` with schemes → `load_project` returns equal schemes.
- Load a **v2** manifest (no `schemes` key) → `schemes == []`, project intact.

The panel is thin wiring; covered by the core tests plus a manual browser smoke.

## Future evolution (b): anchor → suggest

The `Scheme.anchor` field (a region name) is stored now and unused in (a). In
(b), the panel gains a **"suggest the rest"** action: the user sets a region as
anchor and picks its colour; a colour-theory generator (complementary /
analogous / triadic, or faction presets) fills the other regions' palettes to
produce a candidate `Scheme` that lands in the same saved-schemes list. The
storage, apply path, and swap UX built here are reused unchanged — (b) only adds
a generator that *produces* `Scheme` objects.

## Files touched

- **New** `src/mini_highlight_advisor/schemes.py` — `Scheme`, `ApplyReport`,
  `snapshot`, `apply`.
- **New** `ui/schemes_panel.py` — quick-swap panel.
- **Edit** `src/mini_highlight_advisor/projects.py` — `SCHEMA_VERSION` → 3;
  scheme (de)serialization; `save_project(schemes=...)`; `LoadedProject.schemes`;
  `load_project` reads `m.get("schemes", [])`.
- **Edit** `ui/keys.py` — `SCHEMES` (and active-selection) session keys.
- **Edit** the app wiring that mounts panels + calls `save_project`/`load_project`
  (pass schemes in/out of session).
- **New** `tests/test_schemes.py` and a persistence round-trip test.
