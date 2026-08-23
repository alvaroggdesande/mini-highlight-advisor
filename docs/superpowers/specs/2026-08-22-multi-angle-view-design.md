# Multi-Angle View (#8) — Design

**Date:** 2026-08-22
**Status:** Design spec (approved approach; ready for implementation plan).
**Roadmap:** Implements idea **#8** (multiple independent 2D photos → per-angle plans)
from `2026-08-09-roadmap-and-idea-assessment.md`. Explicitly leaves the door open for
idea **#12** (combined multi-angle view) as a later read-only presentation layer — #12
is **out of scope** here.

## 1. Purpose

Let one project hold a miniature photographed from several angles (front / back / side /
anything). Each angle gets the **existing single-photo pipeline** run independently — its
own regions, its own luminance banding, its own settings — producing a per-angle paint
plan. A single **shared paint pool** ("the paints I'm using on this mini") is common to
all angles, matching how a painter actually works: same paints, different faces.

This is **breadth, not depth**: it orchestrates and persists the proven engine over N
photos. No new CV, no cross-photo alignment, no 3D.

## 2. Why now

- The single-photo path is rich (palette input, mix advisor, Vallejo catalogue, coverage
  / 7 bands, edge highlights, manual regions, relief gate, capture guidance) — the
  roadmap gated multi-photo behind exactly this maturity.
- Persistence (PR #21) shipped yesterday at `SCHEMA_VERSION = 1`, one `photo_file` per
  project. Multi-angle is the natural evolution of that model. Doing it now bumps the
  schema to v2 **while the persistence code is fresh and before real saved projects
  accumulate that would need migrating.**

## 3. Current-state constraints (what we build against)

- The editor operates on a single **implicit "current photo"**: one `RegionBook`
  (`keys.BOOK`), one settings set (`keys.N`, `EDGE_*`, `RELIEF_CAP`, `PER_REGION_NORM`),
  one loaded/uploaded photo. `app.py` wires: upload/load → `helpers.shading` → regions →
  palette → coverage → results → save.
- Per-region editing already uses a **save/restore swap** (`ui/state.py`
  `load_region_into_widgets` / `rehydrate_editor_widgets`) keyed on the selected region
  index. This is the proven pattern we lift one level up for angles.
- The **owned-paints list** already exists as a session-global multiselect
  (`keys.OWNED`, produced by `paints_tab.render()` → `owned_paints`), driving the matcher
  and buy-hints. It is **not persisted** today. This is the pre-existing seed of the
  shared paint pool.
- Persistence v1 (`projects.py`): manifest `{schema_version:1, name, slug, timestamps,
  photo_file, settings, book}`; region masks as `region_NN.png` at project root; atomic
  save via `.tmp-<slug>` + `os.replace`; corrupt/keyless manifests skipped in
  `list_projects`.

## 4. Chosen approach — Active-angle swap (Approach A)

The existing editor is **untouched** and keeps operating on "the current photo." We add
one level above it:

- Session holds an **`angles` list** (source of truth) + an **active-angle index**. The
  live editor keys (`BOOK`, settings, loaded photo) **mirror the active angle**.
- Switching angle flushes live editor state back into the active angle record, then loads
  the selected angle's state into the live keys — the same dance as the per-region swap,
  one level up.
- The **paint pool is shared** (one list across all angles) — realized by keeping the
  existing global `OWNED` key and making it persistent + project-scoped.
- **Settings are per-angle** (front may want a different band count / edge behaviour than
  back). Only the paint pool is shared.
- One angle is the **degenerate case** — today's single-photo experience is "a project
  with one angle."

Rejected alternatives (recorded): **B — separate projects grouped** (fights the shared
pool; must sync a pool across N projects; #12 must load N projects). **C — all angles
live at once** (the region-editor session keys are global strings; N live editors collide;
N canvases per rerun is heavy).

## 5. Data model

### 5.1 Session state (source of truth while editing)

New keys in `ui/keys.py`:

| Key | Value | Notes |
|-----|-------|-------|
| `ANGLES = "angles"` | `list[AngleState]` | one record per angle; source of truth |
| `ACTIVE_ANGLE = "active_angle"` | `int` | index into `ANGLES` |
| `angle_label(i)` builder | text-input key per angle | free-form label editing |
| `ANGLE_SELECT = "angle_select"` | active-angle radio/selectbox key | |

`AngleState` (new dataclass, lives with the persistence/state types):
`{label: str, photo_bytes: bytes, photo_suffix: str, book: RegionBook, settings: ProjectSettings}`.

The **active** angle's `book` object is the *same object* referenced by
`st.session_state[keys.BOOK]` (shared by reference — region edits reflect automatically).
The active angle's `settings` are flushed from the widget keys on switch/save. The paint
pool stays in `keys.OWNED` (global, shared) — **not** stored per angle.

### 5.2 On-disk layout (v2)

```
user_data/projects/<slug>/
  manifest.json
  angle_00/  photo.<ext>  region_00.png  region_01.png ...
  angle_01/  photo.<ext>  region_00.png ...
```

Angle subdirectories keep per-angle mask filenames from colliding.

### 5.3 Manifest v2

```json
{
  "schema_version": 2,
  "name": "Skaven Hero",
  "slug": "skaven-hero",
  "created_at": "...", "updated_at": "...",
  "paints_pool": ["RANGE:CODE", "..."],
  "active_angle": 0,
  "angles": [
    {
      "label": "front",
      "photo_file": "angle_00/photo.png",
      "settings": { "n": 5, "edge_hl": true, "edge_extreme": false,
                    "edge_sens": 0.5, "relief_cap": true, "per_region_norm": false },
      "book": {
        "whole": { "palette": [ ...PaintColor dicts... ], "coverage": [ ... ] },
        "drawn": [ { "name": "...", "palette": [...], "coverage": [...],
                    "mask_file": "angle_00/region_00.png" } ],
        "selected": 0
      }
    }
  ]
}
```

Notes:
- `settings` moves **inside each angle** (was project-level in v1).
- `paints_pool` stores the owned-paints selection as **catalogue codes** (what the
  multiselect needs to restore). Code-less custom paints in the pool are not restorable
  via the catalogue multiselect — see Open Questions §10.
- The v1 per-region palette / coverage serialization (`_palette_to_dicts`, mask PNGs) is
  reused verbatim, just nested under each angle.

### 5.4 Migration (v1 → v2)

Handled **entirely in `load_project`** — a v1 manifest is adapted to the v2 in-memory
shape on read; the on-disk v1 directory is left as-is until the project is next saved
(the next save rewrites it in v2 layout). Adaptation:

- `paints_pool` → `[]` (v1 never persisted owned paints).
- `active_angle` → `0`.
- `angles` → single entry: `label` = the project `name` (or `"angle 1"`), `photo_file` =
  the v1 root `photo_file`, `settings` = the v1 project-level `settings`, `book` = the v1
  `book` (masks read from project root, not an `angle_00/` subdir).

`save_project` **always writes v2.**

## 6. Component changes (file-by-file)

- **`src/mini_highlight_advisor/projects.py`**
  - `SCHEMA_VERSION = 2`.
  - New `AngleData` dataclass (persistence-facing twin of the session `AngleState`).
  - `LoadedProject` becomes `{paints_pool: list[str], active_angle: int, angles: list[AngleData]}`.
  - `save_project(name, paints_pool, active_angle, angles, root=..., _now=None)` — writes
    the angle-subdir layout + v2 manifest; same `.tmp-<slug>` + `os.replace` atomicity.
  - `load_project` — reads v2; adapts v1 (§5.4). Missing angle photo → clear error.
  - `list_projects` / `delete_project` / `slugify` / mask helpers unchanged (still skip
    corrupt/keyless manifests).
- **`ui/keys.py`** — add `ANGLES`, `ACTIVE_ANGLE`, `ANGLE_SELECT`, `angle_label(i)`
  builder. (Reuse `OWNED` as the pool — no new pool key.)
- **`ui/state.py`** — new `load_angle_into_editor(idx)` mirroring
  `load_region_into_widgets`: (1) flush live settings into `angles[active]`; (2) copy
  `angles[idx].book / settings / photo` into the live keys (`BOOK`, settings keys,
  `LOADED_PHOTO`); (3) reset `LOADED_G`, `REGION_RADIO`, `RENAME_*` (as project-load
  already does); (4) `st.rerun()`. Factor the pure pieces (build `AngleState` from editor
  state; choose new active on removal) into testable functions.
- **`ui/angles_panel.py`** (new) — the angle bar: active-angle selector, "➕ Add angle"
  (reveals the uploader; append fresh `AngleState`, make active), rename active
  (free-form), "🗑️ Remove angle" (disabled when only one). Streamlit glue only.
- **`ui/projects_panel.py`** — `render_save` serializes **all** angles + the pool (from
  `OWNED`) + active index. `render_library` Load restores the `angles` list, the pool
  (→ `OWNED`), the active index, and seeds the live editor from the active angle.
- **`app.py`** — bootstrap the `angles` list; first-ever upload creates angle 0. The
  uploader routes to "add / replace the active angle's photo." After the angle bar picks
  the active angle, the rest of the editor runs **unchanged** on that angle's
  photo/book/settings.
- **`ui/results.py`** — unchanged for #8 (renders the active angle's plan). #12 will later
  add a read-only combined gallery over the persisted `angles` list.

## 7. UX flow

1. **Angle bar** at the top of the Miniature tab (below the Projects panel): chips /
   selectbox of angle labels, active one highlighted; add / rename / remove controls.
2. **First upload** creates angle 0 (default label `"angle 1"`); identical to today's
   single-photo start.
3. **Add angle** → upload another photo → new angle appended and made active.
4. **Switch angle** → live editor state is flushed to the current angle, the selected
   angle loads into the editor; regions/palette/coverage/results all reflect it.
5. **Paint pool** (Paints tab, `OWNED`) is shared across every angle and persists with the
   project.
6. **Save / Load** round-trips the whole mini (all angles + pool + active index).

## 8. Error handling / edge cases

- **Remove active angle** → choose a neighbour as new active. Never zero angles; removing
  the last angle returns to the empty-upload state.
- **Missing angle photo on load** → raise a clear error (consistent with v1's explicit
  load failure).
- **Corrupt / keyless manifest** → skipped in `list_projects`, as today.
- **Atomic overwrite** → unchanged (`.tmp-<slug>` + `os.replace`), now with angle subdirs.
- **Unsaved multi-angle sessions** work fully — angles live in session independent of
  saving; persistence just serializes the list.
- **v1 projects** load unchanged via §5.4 and upgrade to v2 on next save.

## 9. Testing

- **`tests/test_projects.py`** — extend: v2 multi-angle round-trip; v1→v2 load adaptation
  (single angle, empty pool, masks from root); pool persistence; angle-subdir layout;
  atomic overwrite; corrupt-manifest skip still holds. Update existing v1 tests for the
  new `save_project` signature.
- **`tests/test_angle_state.py`** (new, pure — no Streamlit) — the flush/build and
  active-on-removal helpers factored out of `ui/state.py`.
- **`tests/test_ui_keys.py`** — lock the new key strings.
- All existing tests stay green.

## 10. Open questions (minor; resolve during implementation)

- **Code-less custom paints in the shared pool** — the `OWNED` multiselect is
  catalogue-code-based, so a pool member without a code can't be restored through it.
  Options: store full `PaintColor` dicts for code-less pool entries and surface them
  separately, or accept the limitation for v2 and document it. Lean: document the
  limitation; pool is catalogue-code paints in v2.
- **Angle bar widget** — selectbox vs. a row of buttons/chips. Selectbox is the lowest-risk
  first cut; chips are a polish follow-up.

## 11. Out of scope (YAGNI)

- **#12 combined multi-angle view** — deferred; this design keeps it a pure read-only
  render over the persisted `angles` list (no new data model needed).
- Cross-photo pixel alignment, photogrammetry, 3D — killed in the roadmap.
- Shared **regions** across angles (regions are per-angle).
- Per-angle distinct paint pools (the pool is mini-level).
