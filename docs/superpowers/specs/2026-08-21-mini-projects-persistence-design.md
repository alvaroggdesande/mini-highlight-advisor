# Mini-Projects Persistence — Design

**Date:** 2026-08-21
**Status:** Approved design (ready for implementation plan).
**Branch:** `feat/mini-projects-persistence`

## Purpose

Give the tool a **named mini library**: save the current mini as a named project
and reload any saved project later, restoring the photo, all regions, palettes,
coverage, and render settings exactly as they were left. Today every careful lasso
and palette tweak is lost on a browser refresh and cannot span bench sessions; this
makes the tool usable over time and turns one-off sessions into a growing collection.

Chosen framing (from brainstorming): **named library** (not just crash-recovery),
stored **server-side** on local disk. This fits the tool's offline/free premise and
matches the existing `user_data/` persistence convention.

## Scope

**In scope**
- Save the current session as a named project to `user_data/projects/<slug>/`.
- List saved projects and load any of them (full restore).
- Delete a saved project.
- Overwrite-by-name on save (with a confirm step in the UI).

**Out of scope (deferred / YAGNI)**
- Autosave / restore-last-session (crash recovery) — explicitly not this feature.
- Version history per project.
- Export/import portable project files (download/upload) — server-side only for now.
- Cross-project paint reconciliation — owned paints and custom recipes stay **global**
  (`collection.json` / `recipes.json`), not per-project.
- Thumbnail previews in the load list — optional stretch, see "Optional stretch" below.

## Dependency note

This feature builds on the `ui/` decomposition (`refactor/decompose-app-py`): it adds a
new `ui/projects_panel.py` and touches the thin `app.py` orchestrator. Implementation
assumes that refactor is merged to `main` first (or this branch is rebased onto it).

## Current-state facts the design relies on

- **Photo entry:** `app.py` reads `uploaded.getvalue()` (raw bytes) + suffix and calls
  `helpers.shading(bytes, suffix) -> (rgb, alpha, shading)`. If no upload, `st.stop()`.
- **Region state:** `st.session_state["book"]` holds a `RegionBook` — `whole_palette`,
  `whole_coverage`, `drawn: list[Region]`, `selected`. Each `Region` = `name`,
  `mask` (source-res bool ndarray), `palette: list[PaintColor]`, `coverage: list[float]`.
- **Masks are not re-derivable:** drawn-region polygon points are discarded after
  `polygons_to_mask(...) & shading.mask`; only the final bool mask is kept. Masks are
  therefore serialized directly and are tied to the photo's source resolution.
- **Global render settings** live in widget session keys (`ui/keys.py`): `n` (band count),
  `edge_hl`, `edge_extreme`, `edge_sens`, `relief_cap`, `per_region_norm`.
- **Existing persistence pattern:** `collection.py` / `recipes.py` — Streamlit-free module,
  module-level `load`/`save` with a default `Path`, JSON under `user_data/`, unit-tested.
- **PaintColor** (`palette.py`) is a frozen dataclass: `name, hex, brand, paint_range,
  code, finish`.

## On-disk format — one folder per project

`user_data/projects/<slug>/`:

- **`manifest.json`**
  - `schema_version: int` (start at `1`).
  - `name: str` (display name, verbatim), `slug: str`.
  - `created_at`, `updated_at` (ISO-8601 strings).
  - `photo_file: str` (e.g. `"photo.png"`).
  - `settings`: `{ n, edge_hl, edge_extreme, edge_sens, relief_cap, per_region_norm }`.
  - `book`:
    - `whole`: `{ palette: [PaintColorDict], coverage: [float] }`
    - `drawn`: `[ { name, palette: [PaintColorDict], coverage: [float], mask_file: str } ]`
    - `selected: int`
  - `PaintColorDict` = `{ name, hex, brand, paint_range, code, finish }`.
- **`photo.<ext>`** — original uploaded bytes verbatim (preserves alpha channel; reloaded
  through the same `helpers.shading` path so analysis is identical).
- **`region_00.png`, `region_01.png`, …** — 1-bit PNG masks for each **drawn** region at
  source resolution, index-aligned to `book.drawn`. The "Whole mini" region (index 0) has
  **no** mask (computed at render time), so it stores palette + coverage only.

**Rationale for PNG masks over RLE-in-JSON:** human-inspectable, PIL/numpy already in use,
keeps the manifest small, and folder-per-project makes extra files free. Masks always match
on reload because the same photo is reloaded at the same resolution.

## Core module — `src/mini_highlight_advisor/projects.py`

Streamlit-free, unit-tested, mirroring `collection.py` / `recipes.py`:

```
PROJECTS_DIR = <repo>/user_data/projects            # default, overridable in tests

@dataclass(frozen=True)
class ProjectSettings:
    n: int              # band count
    edge_hl: bool       # edge-highlights on
    edge_extreme: bool  # extreme edge highlight
    edge_sens: float    # edge sensitivity slider, 0.0-1.0
    relief_cap: bool    # auto-reduce bands on flat regions
    per_region_norm: bool  # colored/painted mini toggle

@dataclass(frozen=True)
class ProjectMeta:
    slug: str
    name: str
    updated_at: str

@dataclass(frozen=True)
class LoadedProject:
    photo_bytes: bytes
    photo_suffix: str
    book: RegionBook
    settings: ProjectSettings

def slugify(name: str) -> str: ...
def list_projects(root: Path = PROJECTS_DIR) -> list[ProjectMeta]: ...   # sorted by updated_at desc
def save_project(name, photo_bytes, photo_suffix, book, settings, root=PROJECTS_DIR) -> str: ...  # returns slug
def load_project(slug, root=PROJECTS_DIR) -> LoadedProject: ...
def delete_project(slug, root=PROJECTS_DIR) -> None: ...
```

- **Atomic save:** write to a temp dir under `root`, then replace the target folder (so a
  crash mid-save never corrupts an existing project). Same name → same slug → overwrite.
- **Serialization helpers** (private): `_palette_to_dicts` / `_palette_from_dicts`,
  `_book_to_manifest` / `_book_from_manifest` (masks passed alongside as ndarrays), mask
  PNG read/write (1-bit).
- **Errors:** missing/corrupt `manifest.json` → skipped by `list_projects`, raises a clear
  error on explicit `load_project`. Mask-shape mismatch vs photo (only reachable by hand-
  editing the folder) → explicit error. `save_project` rejects an empty/whitespace name.

## UI — `ui/projects_panel.py`

A "📁 Projects" expander rendered in the Miniature tab (near the top, above/around the
uploader). Streamlit-side glue only; all persistence logic lives in `projects.py`.

- **Save:** name text input (default = loaded project's name, else `"Untitled"`) + Save
  button. Gathers current photo bytes + `book` + a `ProjectSettings` built from the live
  session keys, calls `save_project`, toasts success. If the name already exists, require a
  confirm (checkbox/second click) before overwriting.
- **Load:** selectbox of `list_projects()` (display name) + Load button → `load_project`,
  then write into `session_state`:
  - `loaded_photo` = `{bytes, suffix}` (see upload-gate change),
  - `book` = restored `RegionBook`,
  - the widget keys `n / edge_hl / edge_extreme / edge_sens / relief_cap / per_region_norm`,
  - pop `_loaded_g` (and `rename_*` keys) so regions rehydrate from the restored book,
  - `st.rerun()`.
- **Delete:** button on the selected project with a confirm step → `delete_project`, rerun.

## Integration — the upload gate (`app.py`, the only orchestrator change)

Today: `uploaded is None → st.stop()`. Change so a loaded project supplies the photo:

- Session holds optional `loaded_photo = {"bytes": ..., "suffix": ...}`.
- Photo source resolution: if the user uploads a file, use it **and clear** `loaded_photo`
  (uploading a new photo detaches from the loaded project). Else if `loaded_photo` is
  present, use its bytes+suffix. Else `st.stop()` with the existing "upload to begin" info.
- Everything downstream (`helpers.shading`, `regions_panel`, editors, `results`) is
  unchanged — it only ever sees `rgb, alpha, shading` + `book`.

Restore timing: because Load calls `st.rerun()` after seeding the widget keys, on the next
run the palette/edge/coverage widgets adopt the restored values, and popping `_loaded_g`
makes `state.load_region_into_widgets` reload the selected region from the restored book —
reusing the existing session-state choreography rather than inventing new timing.

## Testing

- **Core `projects.py` — full unit coverage via `tmp_path`:**
  - round-trip `save_project` → `load_project` reconstructs palettes, coverage, region
    names, `selected`, and **bit-identical** masks; settings preserved.
  - `slugify` (spaces/case/unsafe chars/collision-to-same-slug behavior).
  - overwrite-by-name replaces cleanly (no orphaned mask files from a larger previous book).
  - `delete_project` removes the folder; `list_projects` ordering by `updated_at`.
  - corrupt/missing manifest handling (skipped in list; raises on load).
  - Fixtures: a tiny synthetic RGB photo + small bool masks (no dependency on real captures).
- **No Streamlit UI test** — consistent with the repo (`ui/` panels are not unit-tested;
  the session-key contract is covered by `keys`/`state` tests). Manual browser smoke by the
  user: save a multi-region mini, refresh, load it back, confirm regions/palettes/settings.

## Optional stretch (not in MVP)

Thumbnail next to each project in the load list — cheap (the photo is on disk) and nice,
but left out to keep the MVP tight. Revisit if the library grows enough that names alone
are hard to scan.
