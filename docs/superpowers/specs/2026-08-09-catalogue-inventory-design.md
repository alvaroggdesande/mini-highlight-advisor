# Catalogue Growth + Paints/Inventory Tab — Design

**Goal:** Make the paint catalogue easy to grow toward the full Vallejo Model Color + Game Color ranges by hand, safely, and move paint management into its own "Paints" tab separated from the miniature-analysis workflow.

**Status:** Design approved 2026-08-09. Awaiting implementation plan.

## Background

The `own-palette-input` feature (#4) shipped a Vallejo catalogue-backed picker, recipes, and an owned-paints collection. The bundled catalogue (`src/mini_highlight_advisor/data/vallejo_paints.json`) is a deliberately small **13-paint curated seed** — enough for the vertical slice, explicitly designed to grow with zero loader change. This feature makes that growth practical and safe, and reorganises the UI so paint inventory is distinct from building a paint plan.

**This feature depends on `own-palette-input`** — it modifies `catalog.py` and the palette section of `app.py`, both introduced by that feature. It is branched from `feat/own-palette-input` and should merge after it.

## Decisions (from brainstorm)

- **Core goal:** a bigger *built-in* catalogue (not per-user bring-your-own). Target coverage: Vallejo **Model Color + Game Color** (~320 paints eventually). Other lines (Air, specialty) are out of scope.
- **Data sourcing:** *scaffold now, grow later.* The shipped file stays the current curated, verified seed. The user grows it over time by hand-editing the JSON. **We do not bulk-invent hex codes** — inventing ~320 approximate hexes from memory would produce unreliable data, worse than an honest small seed.
- **Format:** keep **JSON** (current schema). Add a format doc + load-time validation so hand-edits are safe.
- **UI:** split into Streamlit tabs — a **Miniature** tab (make the plan) and a **Paints** tab (manage inventory).
- **Inventory UI:** keep the simple `multiselect` (moved from the sidebar into the Paints tab), plus a more *readable* owned-paints display (colour swatch + name + range). A richer/more-visual inventory is a future idea, out of scope here.

## Architecture

The pure-data core stays Streamlit-free and unit-tested; `app.py` is the only Streamlit file. `pipeline.analyze` is untouched — this feature only changes (a) how robustly the catalogue is loaded, and (b) how the palette/inventory UI is arranged.

## Components

### 1. Catalogue data & format

- Keep `src/mini_highlight_advisor/data/vallejo_paints.json`, unchanged schema:
  ```json
  {"name": "Neutral Grey", "brand": "Vallejo", "range": "Model Color", "hex": "#6d7173"}
  ```
  Top-level object: `{"_note": "...", "paints": [ … ]}`.
- The shipped file remains the current curated seed. Growth happens by the user appending entries.
- **`brand` and `range` remain optional** on load (the `PaintColor` dataclass and `find_by_name` are unchanged). `name` and `hex` are required.
- New doc `docs/adding-paints.md`: the schema, a copy-paste example row, the `#rrggbb` hex rule, and the "names must be unique" rule, plus a note that load-time validation will name any bad entry.

### 2. Load-time validation (new core code)

`load_catalog` gains validation so a hand-edit typo produces a clear, actionable error instead of a crash deep in the stack or a silently wrong colour. A dedicated `validate_catalog(paints: list[dict]) -> None` (or inline helper) checks, in order:

- **Missing required key** — an entry lacking `name` or `hex` → `ValueError` naming the entry's index (and `name` if present).
- **Bad hex** — `hex` not matching `^#[0-9a-fA-F]{6}$` → `ValueError` quoting the offending value and the paint name.
- **Duplicate name** — two entries with the same `name` → `ValueError` naming the duplicate. Duplicates break the picker, which resolves paints by name via `find_by_name` (returns the first match).

Validation runs inside `load_catalog` after JSON parse, before constructing `PaintColor`s. The error messages are the feature's usability payoff — they must identify *which* entry is wrong.

`find_by_name` and `PaintColor` are unchanged.

### 3. UI: two tabs (`app.py` — verified manually, per repo practice)

Wrap the app body in `tab_mini, tab_paints = st.tabs(["🖌️ Miniature", "🎨 Paints"])`.

- **🖌️ Miniature tab** — the existing flow, unchanged in behaviour, just relocated onto the tab:
  recipe loader → layer-count slider → per-layer paint picker (catalogue paint or `(custom target)`) → owned ✅/⚠️ badge per slot → save-as-recipe → file upload → painted preview + layer guide + paint-along steps. The per-layer picker stays here; it is part of building a plan.
- **🎨 Paints tab** — the inventory:
  - the **"My paints"** `multiselect` (moved out of the sidebar), same persistence to `user_data/collection.json` as today;
  - a **readable owned list**: for each owned paint, a small colour swatch (inline HTML `<span>` with `background-color`, rendered via `st.markdown(unsafe_allow_html=True)`) next to its name and range;
  - a **catalogue-size line**, e.g. *"Catalogue: 13 paints (Vallejo Model Color + Game Color)"*, so the user can confirm the file grew after editing it.
- The **sidebar** previously held only "My paints"; after the move it is empty and is removed. (The layer-count slider already lives in the main body from the own-palette work.)

### 4. Data flow & the tab-ordering gotcha

Core data flow is unchanged: the Miniature tab assembles `palette: list[PaintColor]` and calls `analyze` exactly as today; the collection is read for badges and written from the multiselect.

**Streamlit gotcha (must be handled):** `st.tabs` executes *both* tab bodies on every rerun, in code order. The Miniature badges read the owned set that the Paints multiselect produces. To avoid one-rerun-stale badges, **fill the Paints tab body before the Miniature tab body in code** (the display order is fixed by the label list, so Miniature still appears first), so `session_state["owned"]` and the resolved `owned_paints` are finalised before the Miniature badges render. This must be called out in the implementation plan.

## Acceptance Criteria

1. Editing `vallejo_paints.json` to add a valid paint makes it appear in the Miniature layer picker and the Paints multiselect with no code change. *(catalogue growth)*
2. A malformed hex in the JSON produces a clear error naming the offending paint, not a raw traceback or a wrong colour. *(validation)*
3. A missing `name`/`hex` and a duplicate `name` each produce a clear, entry-identifying error. *(validation)*
4. The existing curated seed loads cleanly (passes validation). *(no regression)*
5. The app shows two tabs; the Miniature tab reproduces the current workflow (upload → preview → steps) unchanged. *(UI reorg)*
6. "My paints" lives in the Paints tab (not the sidebar) and selections persist across restart. *(UI move)*
7. The Paints tab shows the owned paints as a readable swatch + name + range list, and a catalogue-count line. *(readable inventory)*
8. Ticking/unticking a paint in the Paints tab drives the ✅/⚠️ badges in the Miniature tab within the same session (no stale-by-one-rerun badge). *(tab-ordering)*
9. `nearest_owned` still appears nowhere in the UI. *(carried constraint from #4)*

## Testing Strategy

- **Unit tests** (`tests/test_catalog.py`): valid load still returns `list[PaintColor]`; the shipped seed passes validation; malformed hex, missing required key, and duplicate name each raise a clear `ValueError`; `find_by_name` behaviour unchanged.
- **Manual verification** (`app.py`, per repo practice): the AC5–AC8 items above walked in `streamlit run app.py`.

## Files

- `src/mini_highlight_advisor/catalog.py` — **modify**: add validation to `load_catalog`.
- `src/mini_highlight_advisor/data/vallejo_paints.json` — **unchanged content** (seed stays); grown by the user over time.
- `app.py` — **modify**: wrap body in two tabs; move "My paints" to the Paints tab; add readable owned list + catalogue-count line; remove the empty sidebar.
- `tests/test_catalog.py` — **modify**: add validation tests.
- `docs/adding-paints.md` — **create**: how to add a paint by hand.

## Out of Scope (YAGNI)

In-app paint adding; a `user_data/` catalogue overlay; multi-brand support; Model Air / Game Air / specialty lines; auto-fetching an external dataset; a richer/more-visual inventory UI (noted as a future idea).

## Global Constraints (carried from #4)

- Offline / free at runtime — static bundled catalogue, no live lookups.
- Vallejo is the only catalogue brand for now (`brand == "Vallejo"`); catalogue hexes are approximate screen-swatches.
- Band range 3–5, default 5; `pipeline.analyze` untouched.
- `nearest_owned` is computed but never surfaced in the UI.
- Never build on `main`; feature branch + PR. This work is on `feat/catalogue-inventory` (forked from `feat/own-palette-input`).
- Test runner: `.venv/Scripts/python -m pytest`; the Streamlit app is verified manually.
