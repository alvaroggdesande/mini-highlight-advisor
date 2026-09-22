# React ColourPanel Slice — Design Spec

- **Date:** 2026-09-22
- **Status:** Approved — pending implementation plan
- **Owner:** Alvaro
- **Branch:** `feat/react-colour-panel`
- **Supersedes UI of:** `ui/colour_panel.py` (Streamlit)
- **Depends on:** `feat/react-studio-regions` (merged to main)

---

## 1. Goals

Deliver the ColourPanel as a React slice on top of the existing React+FastAPI scaffold. After this slice, a user can:

- Pick real paints for every band slot in every region (catalog select or custom hex)
- Generate a full colour scheme across all regions from a hero colour, mood, and harmony variant (L1)
- Generate a per-region dark→light ramp from a midtone hex in one click (L2)
- Load and save palette recipes; import/export recipe JSON files
- Snapshot and restore named colour schemes within a session
- See inline paint-match recommendations for every custom hex slot
- Adjust material (matte / metallic) per region

The port is **faithful** — interaction model matches Streamlit exactly. UX simplification (merging L1/L2/L3 into a less layered flow) is deferred to a future design pass.

### Out of scope

- ES translation strings — i18n slice fills `es.json`
- Project save/load serialising new store fields — project slice
- Server-side scheme persistence — planned after project slice (see memory note)
- `AnglesTab`, `PaintTab` step images, `PaintsTab` inventory — separate slices
- NMM, Glow, OSL, PS mode — excluded from the React app entirely
- Any UX redesign of L1/L2/L3 interactions

---

## 2. Architecture overview

The slice has three layers:

1. **Backend** — five new FastAPI endpoints in `backend/main.py` (ramp generation, recipes CRUD + import/export, collection import/export). Seven already-specced endpoints now implemented.
2. **Store** — `projectStore` extended with colour-editor fields; new `catalogStore` for the paint catalog.
3. **Frontend** — `RightPanel` tab strip (Manage | Colour | Technique) replaces the current flat layout; `ColourPanel` and its sub-components handle all colour editing.

The existing `useAnalyze` hook is unchanged — it already watches `book.whole` and `book.drawn` and re-fires on any palette/coverage/material change.

---

## 3. Store extension

### 3.1 Type changes (`web/src/store/projectStore.ts` + `web/src/api/types.ts`)

**Wire types** in `api/types.ts` are **unchanged**. `Whole` stays `{ palette, coverage, material }` — the API never sees colour-editor state.

New store-side types added to `projectStore.ts`:

```ts
// Store-side extension of Whole — never serialised to wire
export interface WholeState extends Whole {
  surface?: string          // "skin" | "cloth" | "metal" | "bone" | "leather" | "fur" | "wood" | "gem" | "accent" | "other"
  tone?: string             // tone archetype key or "__harmony__"
  ramp_midtone?: string     // last midtone hex applied via L2
  ramp_variant?: string     // "ramp" | "complementary" | "warm" | "cool"
}

// Per-region colour state fields added to DrawnRegion
// (DrawnRegion already has palette/coverage/material)
export interface DrawnRegion {
  // ...existing fields...
  surface?: string
  tone?: string
  ramp_midtone?: string
  ramp_variant?: string
}

export interface Scheme {
  id: string
  name: string
  // keyed by drawn[i].id for drawn regions; "__whole__" for the whole-mini
  palettes: { [regionId: string]: PaintColor[] }
  anchor_hex?: string       // hero colour at time of snapshot
}
```

**Book** gains:

```ts
export interface Book {
  whole: WholeState          // replaces Whole
  drawn: DrawnRegion[]
  selected: number
  hero_hex?: string          // L1 anchor colour
  mood?: string              // "neutral" | "grimdark" | "heroic" | "natural"
  variant?: string           // "complementary" | "analogous" | "triadic" | "split-complementary"
  schemes: Scheme[]          // saved scheme snapshots (session-only)
}
```

`makeAngle` initialises `book.schemes = []` and all optional fields as `undefined`.

### 3.2 New actions

| Action | Signature | Effect |
|---|---|---|
| `setSurface` | `(g, surface)` | Sets surface on whole (g=0) or drawn[g-1] |
| `setTone` | `(g, tone)` | Sets tone on whole or drawn[g-1] |
| `setMaterial` | `(g, material)` | Sets material on whole or drawn[g-1] |
| `setHeroHex` | `(hex)` | Sets book.hero_hex on active angle |
| `setMood` | `(mood)` | Sets book.mood on active angle |
| `setVariant` | `(variant)` | Sets book.variant on active angle |
| `setRampState` | `(g, midtone, variant)` | Sets ramp_midtone + ramp_variant on region g |
| `setPaletteAt` | `(g, palette[])` | Replaces the full palette for region g (used by recipe load and scheme apply) |
| `setPaletteSlot` | `(g, i, paint)` | Replaces palette[i] on region g with a catalog PaintColor |
| `setHexSlot` | `(g, i, hex)` | Replaces palette[i].hex on region g (CUSTOM mode — name="custom", code="") |
| `saveScheme` | `(name)` | Snapshots current palettes for all regions into book.schemes[] |
| `applyScheme` | `(id)` | Writes each palette from the snapshot to matching region by ID; silently skips missing IDs |
| `deleteScheme` | `(id)` | Removes scheme from book.schemes[] |

Existing `setCoverage(cov[])`, `setBandCount(n)` remain unchanged — they route via `b.selected` implicitly.

### 3.3 catalogStore (`web/src/store/catalogStore.ts`)

Standalone Zustand store, never serialised to the project manifest:

```ts
interface CatalogState {
  paints: PaintColor[]
  status: "idle" | "loading" | "ready" | "error"
  error?: string
  fetch(): Promise<void>    // idempotent — no-op if status is "ready" or "loading"
  findByCode(code: string): PaintColor | undefined
}
```

`fetch()` calls `GET /api/catalog`. Called once from `App.tsx` after the first photo upload (catalog is only needed when ColourPanel is visible). Result is cached for the session lifetime.

---

## 4. Backend API contract

### 4.1 Existing endpoints — implemented this slice

These are already in the migration spec (`2026-09-22-react-fastapi-migration-design.md §5`); this slice provides the implementation:

| Method + path | Request | Response | Core |
|---|---|---|---|
| `GET /api/catalog` | — | `{ paints: PaintColor[] }` | `catalog.load_catalog()` |
| `POST /api/match` | `{ hex, finish, owned_codes: str[] }` | `{ tier, phrase, name?, hex?, delta_e }` | `matching.match()` |
| `POST /api/scheme/generate` | `{ specs: RegionColorSpec[], anchor_name, anchor_hex, mood, variant, owned_codes }` | `{ palettes: { region_name: PaintColor[] } }` | `scheme_gen` + `scheme_build` |
| `GET /api/recipes` | — | `{ recipes: Recipe[] }` | `recipes.load_all()` |
| `POST /api/recipes` | `{ name, steps: RecipeStep[] }` | `{ ok }` | `recipes.save_user()` |
| `GET /api/collection` | — | `{ owned: str[] }` | `collection.load()` |
| `PUT /api/collection` | `{ owned: str[] }` | `{ ok }` | `collection.save()` |

### 4.2 New endpoints — added this slice

**`POST /api/ramp/generate`**

```
Request:  { midtone_hex: str, n: int, variant: "ramp"|"complementary"|"warm"|"cool",
            blend_hexes?: [str, str] }
Response: { hexes: str[] }   # length == n, dark → light
```

If `blend_hexes` is provided, the server calls `color.blend_hex_lab(hex_a, hex_b)` first and uses the result as `midtone_hex` (ignoring the `midtone_hex` field). This supports the BandSlot **Blend** button in one round-trip — all colour math stays server-side. Server then applies `hue_rotate(midtone, degrees)` (0° / 180° / +30° / −30°) and calls `color.ramp_from_midtone(rotated, n)`. Returns hex strings only — no paint matching. The client fires `POST /api/match` per slot separately.

**`GET /api/recipes/export`**

Returns `application/json` blob — `recipes.export_to_json_bytes(user_recipes)`. Only user recipes are exported (not builtins).

**`POST /api/recipes/import`**

Multipart `file` field. Calls `recipes.import_from_json_bytes(data)`, merges with existing user recipes (upsert by name), saves. Returns `{ recipes: Recipe[] }` (full updated list).

**`GET /api/collection/export`**

Returns `application/json` blob — `collection.export_to_json_bytes(owned)`.

**`POST /api/collection/import`**

Multipart `file` field. Calls `collection.import_from_json_bytes(data, catalog)`, merges with current owned set, saves. Returns `{ owned: str[] }`.

### 4.3 Schemas (`backend/schemas.py` additions)

```python
class RegionColorSpec(BaseModel):
    region_name: str
    surface: str
    tone: str | None = None
    n_bands: int
    is_anchor: bool = False

class SchemeGenerateRequest(BaseModel):
    specs: list[RegionColorSpec]
    anchor_name: str
    anchor_hex: str
    mood: str = "neutral"
    variant: str = "complementary"
    owned_codes: list[str] = Field(default_factory=list)

class RampGenerateRequest(BaseModel):
    midtone_hex: str = ""
    n: int
    variant: str = "ramp"   # "ramp"|"complementary"|"warm"|"cool"
    blend_hexes: list[str] | None = None  # if set, server blends [hex_a, hex_b] → midtone

class MatchRequest(BaseModel):
    hex: str
    finish: str = "matte"
    owned_codes: list[str] = Field(default_factory=list)

class RecipeStepModel(BaseModel):
    label: str
    hex: str
    paint_ref: str | None = None

class RecipeModel(BaseModel):
    name: str
    steps: list[RecipeStepModel]
```

---

## 5. API client additions (`web/src/api/`)

### 5.1 New types (`types.ts`)

```ts
export interface RegionColorSpec {
  region_name: string; surface: string; tone?: string;
  n_bands: number; is_anchor: boolean;
}
export interface SchemeGenerateRequest {
  specs: RegionColorSpec[]; anchor_name: string; anchor_hex: string;
  mood: string; variant: string; owned_codes: string[];
}
export interface SchemeGenerateResponse {
  palettes: { [region_name: string]: PaintColor[] };
}
export interface RampGenerateRequest {
  midtone_hex?: string; n: number; variant: string;
  blend_hexes?: [string, string];  // if set, server blends these → midtone
}
export interface RampGenerateResponse { hexes: string[]; }
export interface MatchRequest { hex: string; finish: string; owned_codes: string[]; }
export interface MatchResult { tier: string; phrase: string; name?: string; hex?: string; delta_e: number; }
export interface RecipeStep { label: string; hex: string; paint_ref?: string | null; }
export interface Recipe { name: string; steps: RecipeStep[]; }
export interface CatalogResponse { paints: PaintColor[]; }

// Harmony variant and mood constants (mirrors Python)
export const MOODS = ["neutral", "grimdark", "heroic", "natural"] as const;
export const VARIANTS = ["complementary", "analogous", "triadic", "split-complementary"] as const;
export const RAMP_VARIANTS = ["ramp", "complementary", "warm", "cool"] as const;
export const SURFACES = ["skin","bone","metal","wood","leather","fur","cloth","cloak","robe","gem","accent","other"] as const;
```

### 5.2 New client functions (`client.ts`)

```ts
fetchCatalog(): Promise<CatalogResponse>
matchPaint(req: MatchRequest): Promise<MatchResult>
generateScheme(req: SchemeGenerateRequest): Promise<SchemeGenerateResponse>
generateRamp(req: RampGenerateRequest): Promise<RampGenerateResponse>
listRecipes(): Promise<{ recipes: Recipe[] }>
saveRecipe(recipe: Recipe): Promise<{ ok: boolean }>
exportRecipes(): Promise<Blob>
importRecipes(file: File): Promise<{ recipes: Recipe[] }>
getCollection(): Promise<{ owned: string[] }>
putCollection(owned: string[]): Promise<{ ok: boolean }>
exportCollection(): Promise<Blob>
importCollection(file: File): Promise<{ owned: string[] }>
```

---

## 6. Component map

### 6.1 Studio layout change (`App.tsx`)

`BandControl` is removed. The right-hand column becomes:

```tsx
<RegionSelector />
<RightPanel />    // NEW — tab strip
```

`RightPanel` renders the active tab:

```tsx
<Tabs labels={["Manage", "Colour", "Technique"]}>
  <ManagePanel />           // existing, unchanged
  <ColourPanel />           // NEW
  <TechniquePanel />        // NEW
</Tabs>
```

Tab labels go through `useTranslation()`.

### 6.2 `TechniquePanel`

Single `<select>` for material: `"matte" | "metallic"`. Reads `book.whole.material` or `book.drawn[selected-1].material` depending on `book.selected`. On change: `setMaterial(selected, value)`. No other controls (NMM/Glow excluded).

### 6.3 `ColourPanel`

Orchestrator component. Reads `activeBookOf`, `activeAngleOf` from store. Passes `selected` (active region index) down to sub-components. Owns no local state — each sub-component (`RecipeSaver`, `SchemeManager`) manages its own text input state.

Renders in order: `SchemeGenerator` → `RampEditor` → `BandEditor` → `SchemeManager`.

### 6.4 `SchemeGenerator` (L1)

Local state (resets on unmount — generative controls, not project state):
- `anchorIndex: number` — which region is the hero
- `heroHex: string` — colour picker value
- `mood: string`
- `variant: string`
- `perRegion: { surface: string; tone: string }[]` — one entry per region slot (whole + drawn)
- `ownedOnly: boolean`

On **Generate**:
1. Build `RegionColorSpec[]` from local state + `book.drawn` names
2. Call `generateScheme(req)` → response palettes
3. Dispatch `setPaletteAt(g, palette)` for each region
4. Dispatch `setHeroHex`, `setMood`, `setVariant`, `setSurface(g)`, `setTone(g)` to persist to store

Seeding: on mount, pre-populate local state from `book.hero_hex`, `book.mood`, `book.variant`, `book.whole.surface`, `book.drawn[i].surface` if present — so switching back to L1 shows the last-used values.

### 6.5 `RampEditor` (L2)

Local state:
- `midtoneHex: string` — colour picker

Seed midtone from active region's `ramp_midtone` if set; otherwise from `palette[Math.floor(n/2)].hex`.

**Use scheme colour** button: sets `midtoneHex` to `book.hero_hex` (if set) — mirrors Streamlit's "use scheme colour" shortcut.

Four buttons: **Ramp** / **Complementary** / **Warm** / **Cool**. On click:
1. Call `generateRamp({ midtone_hex, n, variant })`
2. Dispatch `setHexSlot(g, i, hex)` for each returned hex
3. Dispatch `setRampState(g, midtoneHex, variant)`

### 6.6 `BandEditor` (L3)

Orchestrates `RecipeLoader` + `BandSlot[]` + `CoverageEditor` + `RecipeSaver`.

Derives `n` from `activeRegionPalette.length`. Band count change (insert/delete) via `setBandCount(g, n ± 1)` — existing action.

### 6.7 `RecipeLoader`

Fetches `GET /api/recipes` on mount. Selectbox with all recipes. **Load** button resolves the selected recipe to a `PaintColor[]` client-side (`toPalette(recipe, catalogStore.paints)`: for each step, look up `paint_ref` by name in the catalog — if found use that `PaintColor`, otherwise create a CUSTOM entry with `step.hex`) then dispatches `setPaletteAt(book.selected, palette)`.

### 6.8 `BandSlot`

Props: `g, i, paint: PaintColor, finish: string`.

Two modes:
- **Catalog mode** (paint.code !== ""): shows paint code selectbox (all catalog codes + `"(custom)"`), colour swatch, ownership badge.
- **Custom mode** (paint.code === ""): shows hex colour picker + hex text input, match phrase below.

Switching mode: selecting `"(custom)"` from the catalog selectbox sets `setHexSlot(g, i, paint.hex)`.

Match phrase: fires `POST /api/match` debounced 400 ms on hex change. Result stored in `BandSlot` local state (`matchResult: MatchResult | null`). Displayed as: `"✓ Paint Name"` (exact), `"≈ Paint Name"` (close), `"Mix A + B"` (mix), `"Buy: Paint Name"` (unreachable).

Actions per slot:
- **Delete** (✕): `setBandCount(n - 1)` if n > 3
- **Blend** (↕): fires `generateRamp({ blend_hexes: [palette[i-1].hex, palette[i+1].hex], n: 1, variant: "ramp" })` → `setHexSlot(g, i, hexes[0])`. Server blends the two neighbours in Lab space and returns the midpoint.
- **Insert after** (＋): `setBandCount(n + 1)` if n < 7, then `setHexSlot(g, n, palette[n-1].hex)` to seed the new slot

### 6.9 `CoverageEditor`

Props: `g, n, coverage: number[]`.

Renders N−1 sliders (role names from `role_names(n)` as labels). Slider `i` controls `coverage[i]`; last slot auto-computed as remainder. Upper-bound cap: each slider's max = `1.0 - sum(others) - 0.03` (3% floor for the remainder).

**Reset** button: `setCoverage(g, default_coverage(n))` — evenly distributed.

Dispatches `setCoverage(g, coverage[])` on slider `mouseUp` (not on every drag tick).

### 6.10 `RecipeSaver`

Text input (recipe name) + **Save** button. On save: `POST /api/recipes { name, steps }` where steps are built from current palette. Shows success toast. Invalidates `RecipeLoader`'s recipe list (passed via callback or React state lift).

### 6.11 `SchemeManager`

Reads `book.schemes`. Name input + **Save** button → `saveScheme(name)`. Lists saved schemes with **Apply** + **Delete** per entry.

Apply: `applyScheme(id)`. The action matches snapshot region IDs to current region IDs; silently skips any that no longer exist (regions may have been deleted since the snapshot).

### 6.12 `RecipeManager`

**Export recipes**: `GET /api/recipes/export` → trigger browser download.

**Import recipes**: file input → `POST /api/recipes/import` → refresh recipe list + toast.

---

## 7. Data flows

### 7.1 L1 — Scheme generation

1. User configures surface/tone per region, hero colour, mood, variant in `SchemeGenerator`.
2. Clicks **Generate** → `POST /api/scheme/generate`.
3. Response palettes dispatched per region via `setPaletteAt(g, palette)`.
4. `setHeroHex`, `setMood`, `setVariant`, `setSurface(g)`, `setTone(g)` persist controls to store.
5. `useAnalyze` debounce fires → preview re-renders.

### 7.2 L2 — Ramp generation

1. User picks midtone hex in `RampEditor`, clicks a variant button.
2. `POST /api/ramp/generate { midtone_hex, n, variant }`.
3. Each returned hex dispatched via `setHexSlot(g, i, hex)` → each slot enters CUSTOM mode.
4. `setRampState(g, midtone, variant)` persists to store.
5. `useAnalyze` debounce fires.

### 7.3 L3 — Slot editing

- **Catalog select**: `setPaletteSlot(g, i, paint)` → `useAnalyze` fires.
- **Custom hex**: `setHexSlot(g, i, hex)` → `useAnalyze` fires independently from match debounce.
- **Coverage**: `setCoverage(cov[])` on `mouseUp` → `useAnalyze` fires (routes via `b.selected`).
- **Blend**: `generateRamp({ blend_hexes: [left.hex, right.hex], n: 1 })` → `setHexSlot(g, i, hex)`.
- **Insert/delete**: `setBandCount(n ± 1)` → store redistributes coverage.

### 7.4 Recipe flow

Load: `GET /api/recipes` → `setPaletteAt(g, toPalette(recipe))` → analyze.
Save: `POST /api/recipes` → toast.
Import: `POST /api/recipes/import` → refresh list.
Export: `GET /api/recipes/export` → download.

### 7.5 Scheme flow

Save: `saveScheme(name)` snapshots all current region palettes keyed by region ID.
Apply: `applyScheme(id)` writes each palette to matching region; silently skips removed regions.
Delete: `deleteScheme(id)`.

---

## 8. i18n

`react-i18next` initialised in `web/src/i18n/index.ts`, imported in `main.tsx` before `<App />`. All user-visible strings in the five new components go through `useTranslation()`. `en.json` is ported from `src/mini_highlight_advisor/locales/en.json` — only keys referenced in React components are included (no dead keys). `es.json` is a valid but empty namespace; the i18n slice provides ES strings.

Key namespaces used by this slice: `colour`, `surfaces`, `moods`, `variants`, `recipes`, `schemes`, `technique`, `common`.

---

## 9. Testing

### Backend (`backend/tests/`)

New test files:

- `test_catalog.py` — `GET /api/catalog` returns non-empty list with required fields.
- `test_match.py` — exact/close/unreachable tiers; owned filter.
- `test_ramp.py` — all four variants; output length == n; hexes are valid CSS hex strings.
- `test_scheme_generate.py` — single-region + multi-region; anchor propagates correctly; owned_codes filter.
- `test_recipes.py` — list (builtin + user); save upserts; export bytes; import merges.
- `test_collection.py` — get/put round-trip; export/import round-trip.

### Frontend (`web/src/`)

- `store/projectStore.test.ts` — all 13 new actions; `applyScheme` skips missing region IDs; `saveScheme` keyed correctly.
- `store/catalogStore.test.ts` — fetch lifecycle; `findByCode` lookup; idempotent on re-call.
- `components/colour/CoverageEditor.test.tsx` — remainder arithmetic; floor cap; Reset.
- `components/colour/BandEditor.test.tsx` — recipe load seeds palette; insert/delete bounds.
- `components/colour/SchemeManager.test.tsx` — save/apply/delete.
- `components/colour/BandSlot.test.tsx` — catalog/custom mode toggle; match phrase renders.
- `components/RightPanel.test.tsx` — tab switching renders correct child.

API calls in frontend tests are mocked via `vi.spyOn(client, ...)` — no live backend required.

---

## 10. File index

**New files:**

```
backend/tests/test_catalog.py
backend/tests/test_match.py
backend/tests/test_ramp.py
backend/tests/test_scheme_generate.py
backend/tests/test_recipes.py
backend/tests/test_collection.py

web/src/store/catalogStore.ts
web/src/store/catalogStore.test.ts
web/src/i18n/index.ts
web/src/i18n/locales/en.json
web/src/i18n/locales/es.json
web/src/components/RightPanel.tsx
web/src/components/RightPanel.test.tsx
web/src/components/TechniquePanel.tsx
web/src/components/colour/ColourPanel.tsx
web/src/components/colour/SchemeGenerator.tsx
web/src/components/colour/RampEditor.tsx
web/src/components/colour/BandEditor.tsx
web/src/components/colour/BandEditor.test.tsx
web/src/components/colour/RecipeLoader.tsx
web/src/components/colour/BandSlot.tsx
web/src/components/colour/BandSlot.test.tsx
web/src/components/colour/CoverageEditor.tsx
web/src/components/colour/CoverageEditor.test.tsx
web/src/components/colour/RecipeSaver.tsx
web/src/components/colour/SchemeManager.tsx
web/src/components/colour/SchemeManager.test.tsx
web/src/components/colour/RecipeManager.tsx
```

**Modified files:**

```
backend/main.py              — 12 new/implemented endpoints
backend/schemas.py           — RegionColorSpec, SchemeGenerateRequest, RampGenerateRequest, MatchRequest, RecipeStepModel, RecipeModel
web/src/api/types.ts         — new request/response types + constants
web/src/api/client.ts        — 12 new typed fetch functions
web/src/store/projectStore.ts — WholeState, Scheme types; Book extension; 13 new actions
web/src/App.tsx              — catalog fetch on first photo; RightPanel replaces flat stack; BandControl removed
web/src/main.tsx             — i18n import
```

---

## 11. Deferred

| Topic | Where handled |
|---|---|
| ES translation strings | i18n slice |
| New store fields in project save/load manifest | project slice |
| Server-side scheme persistence (`GET/PUT /api/schemes`) | after project slice — see memory note |
| `AnglesTab` gallery | AnglesTab slice |
| `PaintTab` step images (`GET /api/steps`) | PaintTab slice |
| `PaintsTab` paint inventory | PaintsTab slice |
| ColourPanel UX redesign (merge L1/L2/L3) | post-migration design pass — see memory note |
