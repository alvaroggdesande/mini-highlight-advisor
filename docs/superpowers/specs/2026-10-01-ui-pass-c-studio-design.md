# UI pass C — Studio restructure

Date: 2026-10-01 · Branch: `feat/ui-pass-c-studio` · Status: draft for review

## Context

Third and last piece of the 2026-10-01 UX review (first-time hobbyist lens):
A fixes + quick wins (merged, PR #83), B guidance (merged, PR #84), **C (this spec)
Studio restructure**.

Today the Studio editor column is, top to bottom: scheme generator ("Generate palette
(whole mini)", with Anchor region / Hero colour / Mood / Harmony variant) → region
header ("Editing: [region]", Manage regions, Surface / Tone / Material) → "Band Editor
(L3)" whose footer crams Add band, the whole "Ramp Generator (L2)", recipe load, recipe
save, Reset coverage and Undo → Colour Schemes snapshots → recipe **and collection**
import/export (the collection half duplicates the Paints tab).

Problems: the order is backwards (colour every region before defining them), the
labels are developer jargon (L1/L2/L3, Coverage, auto, Hero colour, Anchor region), one
"Editing:" picker silently scopes some sections but not others (the scheme always
colours *all* regions), power tools crowd the main path, and edge-highlight settings
have no UI at all (`DEFAULT_SETTINGS` only; no setter exists).

**Goal:** a hobbyist reads the Studio as three numbered steps — Regions → Colour scheme
→ Layers — with plain wording, one obvious region selection, and save/share tools out of
the way. Layers are the primary activity; the scheme generator is an optional helper.

**Out of scope:** persisting the ★ main-colour region and the colour harmony in saved
projects (needs `projects.py` / `RegionBook` changes — `variant` isn't persisted today
either; small backend follow-up), UI for `relief_cap` / `per_region_norm`, banding/layer
logic (`docs/ideas/layer-spread.md`), Paints-tab brand filter. No backend changes.

## 1. Layout

`StudioPanel` keeps the sticky left column (QualityAlert, PreviewImage, "see painting
steps" CTA from B). The editor column becomes:

```
1  Regions
   ┌ ★ Whole mini  [skin ▾] [pale…] [matte ▾] ┐   click a row = select it
   │ ☆ Cloak       [cloth▾] [dark…] [matte ▾] │   selected row highlighted
   └──────────────────────────────────────────┘
   + Draw a region      (toggles the existing ManagePanel)
2  Colour scheme · all regions · optional
   Main colour ■  Mood ▾  Colour harmony ▾  ☐ Owned paints only  [Suggest colours]
   caption: ★ marks the region that gets the main colour
3  Layers for [Cloak ▾]
   [Shadow card] [Base card] … [Highlight card · 42% · fills the rest]
   + Add layer · Reset areas · ↺ Undo
   Fill layers from:  [one colour]  [a saved recipe]
   ── Edge highlights · whole mini ──
   ☑ Edge highlights   ☐ Extra-sharp edge highlight   How many edges ─●─
▸ Save & share    (collapsed by default)
   Save as recipe · Saved schemes · Export / import recipes
```

### 1.1 Step 1 — Regions (`RegionTable`, new)

- One row per region: Whole mini first, then `book.drawn` in order. Columns: ★ toggle,
  name, Surface (NativeSelect, `SURFACES`), Tone (TextInput with placeholder), Finish
  (matte / metallic). Edits call the existing `setSurface(g, …)`, `setTone(g, …)`,
  `setMaterial(g, …)` with the row's index — every row is editable in place, not only
  the selected one.
- Clicking a row (anywhere outside its inputs) calls `setSelected(g)`. The row whose
  index equals `book.selected` is visually highlighted and has `aria-selected="true"`.
- ★ toggle: an ActionIcon per row (filled ★ when `isAnchor`, outline ☆ otherwise,
  `aria-label` "Main colour goes on {name}"). Clicking the outline star sets the anchor
  to that row; there is always exactly one anchor (clicking the filled star is a no-op).
  Whole mini row → `setAnchor(undefined)`, drawn row → `setAnchor(region.id)`.
- "+ Draw a region" button toggles a Collapse containing the existing `ManagePanel`
  (canvas, draw, rename/visible/delete of the selected drawn region) — moved from
  `RegionHeader`, behaviour unchanged.

### 1.2 Step 2 — Colour scheme (`GeneratePanel`, slimmed)

- Header via `StepSection` with title "Colour scheme" and badges/caption "all regions ·
  optional". Keeps today's collapse rule (expanded until `book.hero_hex` is set; toggle
  overrides).
- **Removed:** the Anchor region dropdown and its local `anchorIndex` state. The anchor
  comes from `book.anchor_id`: index 0 when undefined, else `1 + drawn.findIndex(id)`;
  if the id is not found, fall back to 0. That index drives `is_anchor` per spec and
  `anchor_name` in the request (API identifiers unchanged, `WHOLE_MINI_ID` stays).
- Caption under the controls: "★ marks the region that gets the main colour".
- Fields renamed per §3; behaviour otherwise unchanged (owned-only hint from A stays).

### 1.3 Step 3 — Layers (`BandEditor` + new `LayerTools`, `EdgeSettings`)

- Header: "Layers for [region ▾]" — a NativeSelect bound to `book.selected` /
  `setSelected`, so it is the same selection as the highlighted table row.
- Band cards unchanged in function; wording per §3 (role, "Area" slider with hint,
  last layer shows `{pct}% · fills the rest`).
- `LayerTools` (replaces `RecipeFooter`):
  - Row 1: "+ Add layer" (disabled at 7), "Reset areas", "↺ Undo" — same logic as
    `RecipeFooter` today (add copies last hex; reset snapshots then `defaultCoverage`).
  - Row 2: "Fill layers from:" with two toggle buttons, **one colour** and **a saved
    recipe**. At most one is open; clicking the open one closes it. "one colour"
    expands `RampEditor` inline, "a saved recipe" expands `RecipeLoader` inline. Both
    components are reused unchanged apart from wording; `RecipeLoader`'s
    `onRecipeLoaded` keeps re-keying the band list as today.
- `EdgeSettings` (new), below the tools, under a small divider label "Edge highlights ·
  whole mini" (settings are per photo/angle, not per region):
  - Checkbox "Edge highlights" → `edge_hl`.
  - Checkbox "Extra-sharp edge highlight" → `edge_extreme`, disabled when `edge_hl` is
    off.
  - Slider "How many edges" 0–1 step 0.05 → `edge_sens`, disabled when `edge_hl` is
    off; left/right hint text "fewer, sharpest" / "more". Commit on change end
    (`onChangeEnd`) so dragging doesn't spam analyses (useAnalyze also debounces 150 ms).
  - All call `setSettings({...})`. No new analyze wiring needed: `useAnalyze` already
    sends `angle.settings` and lists it as an effect dependency; painting steps come
    from that result token, and `PaintTab.reanalyze` also sends `a.settings`.

### 1.4 Save & share (`SaveSharePanel`, new)

- A Collapse, closed by default, header "Save & share ▸".
- Contains, in order: `RecipeSaver` ("Save as recipe"), `SchemeManager` ("Saved
  schemes"), `RecipeManager` reduced to **recipes only** (export / import recipes).
- The collection export/import buttons, `collectionRef`, `onCollection` and the
  `setOwnedFromImport` dependency are removed from `RecipeManager` — the Paints tab is
  the single home for the collection.
- `RecipeSaver.onSaved` previously re-keyed `BandEditor` (to refresh `RecipeLoader`'s
  list). Since the loader now only mounts when "a saved recipe" is opened, and it fetches
  `listRecipes()` on mount, the re-key is no longer needed for saving; drop the prop
  wiring from the saver.

### 1.5 Shared pieces

- `StepSection` (new): `{ n?: number; title: string; caption?: string; right?: ReactNode;
  children }` — renders a numbered circle + title (+ optional caption, optional right
  slot for toggles/pickers) above its children. Used by steps 1–3.
- **Deleted:** `RegionHeader.tsx` (+ test; coverage moves to RegionTable / BandEditor
  tests), `colour/RecipeFooter.tsx` (+ test; coverage moves to LayerTools tests),
  `BandControl.tsx` (dead code, nothing imports it; its 1–8 range contradicted the real
  3–7 limit).

## 2. Store (`web/src/store/projectStore.ts`)

- `setSettings(patch: Partial<Settings>)`: shallow-merge into the active angle's
  `settings`. New angles already inherit the active angle's settings (`makeAngle`).
- `Book.anchor_id?: string` — runtime-only ★ (undefined = Whole mini). Not sent to the
  backend and not persisted: `initFromProject` / `initFromPhoto` leave it undefined, so
  loading a project resets the ★ to Whole mini (today the anchor is component-local and
  resets even on tab switch, so this is strictly better).
- `setAnchor(id: string | undefined)`.
- `removeRegion`: if the removed region's id equals `anchor_id`, clear `anchor_id`.
- `book.selected` remains the single selection; table rows and the step 3 picker both
  use `setSelected`.
- Undo snapshots (`structuredClone(book)`) naturally include `anchor_id`; fine.

## 3. Wording (EN + ES)

| Now (EN) | New EN | New ES |
|---|---|---|
| Band Editor (L3) | Layers for | Capas de |
| band (add / delete) | Add layer / Delete layer | Añadir capa / Eliminar capa |
| Ramp Generator (L2) | one colour (Fill layers from) | un color |
| Load recipe (in footer) | a saved recipe (Fill layers from) | una receta guardada |
| — | Fill layers from: | Rellenar capas desde: |
| Midtone | Middle colour | Color medio |
| Generate palette (whole mini) | Colour scheme | Esquema de color |
| — | all regions · optional | todas las regiones · opcional |
| Generate | Suggest colours | Sugerir colores |
| Hero colour | Main colour | Color principal |
| Anchor region | ★ marks the region that gets the main colour | ★ marca la región que lleva el color principal |
| Harmony variant | Colour harmony | Armonía de color |
| Coverage | Area (hint: how much of the region this layer covers) | Área (cuánto de la región cubre esta capa) |
| `42% (auto)` | `42% · fills the rest` | `42% · rellena el resto` |
| Reset coverage | Reset areas | Restablecer áreas |
| Material | Finish | Acabado |
| Tone (no placeholder) | Tone, placeholder "pale, dark…" | Tono, "claro, oscuro…" |
| Editing: / Manage regions | Regions / + Draw a region | Regiones / + Dibujar una región |
| Colour Schemes / Save snapshot | Saved schemes / Save current colours | Esquemas guardados / Guardar colores actuales |
| Save recipe | Save as recipe | Guardar como receta |
| — | Save & share | Guardar y compartir |
| — | Edge highlights · whole mini | Luces de borde · toda la mini |
| — | Edge highlights / Extra-sharp edge highlight / How many edges (fewer, sharpest … more) | Luces de borde / Luz de borde extra nítida / Cuántos bordes (menos, más nítidos … más) |
| — | Main colour goes on {{name}} (★ aria-label) | El color principal va en {{name}} |

ES wording may be aligned with existing ES glossary terms during implementation (e.g.
the existing `region.whole_mini` translation). Keys no longer used are deleted
(`colour.ramp_editor`, `colour.band_editor`, `colour.anchor_region`,
`recipes.collection_export`, `recipes.collection_import`, plus any orphaned by the
renames); `locales.test.ts` keeps EN/ES parity.

## 4. Behaviour preserved

Band limits 3–7 (BandCard ✕ disabled at 3, Add layer disabled at 7); undo semantics;
scheme generator collapse rule; owned-only hint; `WHOLE_MINI_ID` API identifier; region
drawing flow and B's lasso hints; the left preview column.

## 5. Testing (vitest, TDD per component)

- `RegionTable`: renders one row per region; row click calls `setSelected(g)`; selected
  row has `aria-selected`; editing a non-selected row's surface/tone/finish updates that
  row; ★ click sets anchor; deleting the starred region falls back to Whole mini;
  "+ Draw a region" reveals ManagePanel.
- Store: `setSettings` merges into the active angle only; `setAnchor`; `removeRegion`
  clears a matching `anchor_id`.
- `BandEditor`: step 3 picker reflects and changes `book.selected` (sync with table).
- `LayerTools`: add/reset/undo as before (migrated from `RecipeFooter.test`); fill
  toggles open one panel at a time and close on second click.
- `EdgeSettings`: checkboxes/slider call `setSettings`; extra-sharp + slider disabled
  when edge highlights off.
- `GeneratePanel`: request marks `is_anchor` from `anchor_id` (whole mini default,
  drawn id, unknown id → whole mini); no anchor dropdown rendered.
- `SaveSharePanel`: collapsed by default; when opened shows save-recipe, schemes,
  recipe export/import and **no** collection buttons.
- `StudioPanel`: steps render in order Regions → Colour scheme → Layers → Save & share.
- Existing tests touching removed/renamed strings updated; `locales.test.ts` green;
  `tsc` clean.
- User runs pytest (unchanged backend) and a browser smoke in EN + ES.
