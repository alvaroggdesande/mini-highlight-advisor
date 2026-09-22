# React + FastAPI Migration — Design Spec

- **Date:** 2026-09-22
- **Status:** Approved (design) — pending implementation plan(s)
- **Owner:** Alvaro
- **Supersedes UI of:** `app.py` + `ui/` (Streamlit), eventually and optionally

## 1. Context & motivation

The tool works, but the Streamlit front end has hit structural (not skill)
limits that a proper front end eliminates:

- **All tab bodies execute every rerun** in code order (`st.tabs`), forcing
  fragile ordering hacks (e.g. Paints must run before Studio; `st.stop()` is
  banned because it would kill later tab bodies). The Gallery "Activate" button
  was removed outright because of tab-execution-order bugs.
- **Widgets cannot be updated after they mount**, producing the
  `set_active_angle` / `_angle_select_target` choreography in `ui/state.py`
  just to switch the active angle without Streamlit replaying a stale value.
- **`streamlit-drawable-canvas` pins us to `streamlit==1.61.*`** via the
  `ui/compat.py` shim.

These are structural limits of Streamlit's execution model, not gaps in how we
use it. A React front end with an explicit state model removes all three.

## 2. Goals & non-goals

### In scope (this migration)
- **Photo-mode Studio**: upload → shading → live painted preview.
- **Palette + coverage editing** (the `colour_panel` "levels": scheme
  generation, ramp editing, per-slot paint picking, recipe manager, scheme save).
- **Lasso regions** (draw → immutable region with its own palette/coverage).
- **Paint-along steps** (zone / cumulative / exact images + captions + ownership).
- **Multi-angle** (add / switch / rename / gallery).
- **Colour schemes** (generate, snapshot, apply, save).
- **Paints inventory** (catalog browse, owned toggles, import/export).
- **Project save / load** (filesystem + JSON blob up/download).
- **i18n** — stays multilingual (EN + ES today), ported to react-i18next.

### Out of scope (explicitly cut from the React app)
- **PS mode** (photoscanner normal-map import; `tools/ps_tool.py`, torch).
- **OSL** (object-source lighting / Glow tab).
- **NMM** (non-metallic-metal material) and the normals-dependent techniques.

These remain in the Python core (`src/`) untouched; the React UI simply does not
expose them. Photo mode never passes `light_field` / `normal_field`, so
`analyze_regions` runs its matte path. Revisiting them is a future, separate
effort.

### Non-goals
- No hosting / deployment. This is a personal, localhost tool (two dev servers).
- No UX redesign *during* the port — see §11 (faithful port first).

## 3. Locked decisions

| Decision | Choice | Rationale |
|---|---|---|
| Front-end framework | **Vite + React + TypeScript** (SPA) | Next.js's SSR / file-routing / API-routes are dead weight for a localhost single-page image editor. TS types on the manifest catch shape bugs and make AI assistance reliable. |
| Render loop | **Server renders PNGs each edit** | Python core is the single source of truth; no render logic duplicated in JS. Localhost round-trip is fast. |
| i18n | **Keep multilingual** | Just shipped; port `locales/*.json` to react-i18next (files are near-compatible). |
| State management | **Zustand** | Simpler than Redux; fits an image-editor store; store shape == project manifest. |
| Lasso canvas | **react-konva** | No version pin; polygon points → server rasterizes via existing `polygon_to_mask`. |
| Streamlit removal | **Optional, deferrable, final step** | Both apps coexist indefinitely; retire `app.py` only when React has earned trust (see §10). |

## 4. Architecture — two localhost processes

```
repo root
├── src/mini_highlight_advisor/   # UNCHANGED core (numpy/PIL/opencv)
├── app.py + ui/                  # Streamlit — stays runnable until retired
├── backend/                      # NEW: FastAPI, thin adapter over src/
│   ├── main.py                   # app + routes
│   ├── cache.py                  # LRU: shading-by-photo-hash, result-by-token
│   ├── schemas.py                # pydantic request/response models
│   └── serialize.py              # numpy arrays / PIL → base64 PNG
└── web/                          # NEW: Vite + React + TS SPA
    ├── src/store/                # Zustand: projectStore, uiStore
    ├── src/api/                  # typed fetch client
    ├── src/components/           # tabs + panels (see §7)
    └── src/i18n/                 # react-i18next, locale JSON
```

- **Backend** imports `mini_highlight_advisor` directly (same venv). It rewrites
  no core logic; every endpoint is an adapter that (de)serializes and calls an
  existing function.
- **Frontend** talks to the backend over HTTP on localhost (Vite dev server
  proxies `/api` to FastAPI to avoid CORS in dev).
- Dev run: `uvicorn backend.main:app --reload` (:8000) + `npm run dev` in
  `web/` (:5173). Streamlit `streamlit run app.py` (:8501) remains available.

## 5. Backend API contract

All images are returned as base64 `data:image/png;base64,...` strings in JSON
(simplest for the render-each-edit model on localhost; swappable to blob URL
endpoints later if payload size ever hurts).

| Method + path | Request | Response | Core reuse |
|---|---|---|---|
| `POST /api/photo` | multipart file | `{photo_id, width, height, quality_checks:[{label,ok,detail}]}` | `load_image`, `prepare_shading`, `input_check.check_input` |
| `POST /api/analyze` | `{photo_id, regions:[{name,points,palette,coverage,material}], whole:{palette,coverage,material}, settings}` | `{preview_png, result_token, plans_meta:[{name,roles,coverage,capped,...}]}` | `polygon_to_mask`, `analyze_regions` |
| `GET /api/steps?token=` | — | `{plans:[{name,roles,coverage,steps:[{index,label,kind,zone_png,cumulative_png,exact_png,is_last}]}]}` | memoized `MultiRegionResult` |
| `GET /api/catalog` | — | `{paints:[{name,hex,brand,paint_range,code,finish}]}` | `load_catalog` |
| `POST /api/match` | `{hex, finish, owned:[code]}` | `{phrase, name?, hex?, deviation?}` | `matching.match` |
| `POST /api/scheme/generate` | `{anchor_hex, variant, mood, specs:[RegionColorSpec]}` | `{palettes:{region:[PaintColor]}}` | `scheme_gen`, `scheme_build` |
| `GET /api/collection` | — | `{owned:[code]}` | `collection.load` |
| `PUT /api/collection` | `{owned:[code]}` | `{ok}` | `collection.save` |
| `POST /api/collection/import` · `GET /api/collection/export` | JSON blob | owned set | `collection.import/export_*_json_bytes` |
| `GET /api/projects` | — | `[{slug,name,updated_at}]` | `projects.list_projects` |
| `GET /api/projects/{slug}` | — | project manifest JSON (client-shaped) | `projects.load_project` |
| `PUT /api/projects/{slug}` | manifest JSON | `{slug}` | `projects.save_project` |
| `DELETE /api/projects/{slug}` | — | `{ok}` | `projects.delete_project` |
| `GET /api/projects/{slug}/download` · `POST /api/projects/upload` | JSON blob | manifest | `project_to/from_json_bytes` |

### The `/analyze` ↔ `/steps` split
`analyze_regions` computes the combined preview *and* the per-band step images
in one pass. The server **memoizes the whole `MultiRegionResult`** keyed by an
analyze signature (mirroring `ui/helpers._analysis_signature`) and returns a
`result_token` (the signature hash). `/analyze` serializes only the combined
preview → **one PNG per edit** (fast; this is what Studio shows live). `/steps`
is a cache hit on the token that serializes the ~3×N step images, fetched
lazily only when the Paint tab is open. Scrubbing a slider therefore ships one
image, not fifteen.

### Caching
- `shading_cache`: `photo_id → (rgb, alpha, ShadingResult)`, bounded LRU. The
  expensive GrabCut runs once per uploaded photo.
- `mask_cache`: `(photo_id, hash(points)) → mask`, so immutable region outlines
  rasterize once.
- `result_cache`: `result_token → MultiRegionResult`, bounded LRU.
Single-user, small; simple in-process LRUs are sufficient (no Redis).

## 6. State model — the manifest *is* the client state

The existing JSON-blob manifest shape (`LoadedProject`:
`paints_pool, active_angle, angles[], schemes[]`, each angle carrying
`{label, photo_*, book:{whole, drawn[]}, settings}`) becomes the **Zustand
store shape verbatim**. Save = serialize the store to the manifest; load =
hydrate the store from it. One shape, one source of truth.

### Schema bump v5 → v6: store lasso `points`
Today a drawn region persists only its rasterized mask PNG. The React client
holds the region as its **polygon point-list** (the immutable outline) and
sends points to `/analyze`; the server rasterizes. Therefore:

- **v6 adds a `points` field per drawn region** (list of `[x,y]` in image
  coords), alongside the existing `mask_file` / `mask_b64`.
- Point-lists are the client's source of truth and what travels over HTTP;
  **mask PNGs never travel to the browser** (payloads stay tiny).
- **Backward compat:** a v5→v6 loader keeps old projects working. A legacy
  region that has a mask but no points renders as a static overlay and is
  treated as immutable (which it already is per the "outlines immutable once
  drawn" rule in `CLAUDE.md`) — it simply can't be re-traced, which is fine.
- The server continues to write mask PNGs into the manifest on save (derived
  from points via `polygon_to_mask`), so the on-disk artifact remains
  self-contained and Streamlit-loadable during coexistence.

### How this kills the three Streamlit walls
- **All-tabs-execute** → only the mounted React tab renders; `/analyze` fires on
  explicit state change (debounced), not on every rerun.
- **Widget-key locking** → switching angle is `setActiveAngle(i)`, plain state.
  The entire `set_active_angle` / `_angle_select_target` / `load_region_into_widgets`
  / `rehydrate_editor_widgets` dance in `ui/state.py` disappears.
- **Canvas pin** → react-konva; no Streamlit version lock.

## 7. Component map (React ← Streamlit)

- **App**: layout, `LanguageSelector`, lightweight tab state (no router needed
  for 5 tabs), global loading/error surface.
- **StudioTab** ← `app.py` studio block + `ui/editor.py`
  - `PhotoUploader` ← the `st.file_uploader` + sample-photo picker
  - `AngleBar` ← `ui/angles_panel.py` (add/switch/rename)
  - `RegionCanvas` ← `ui/regions_panel.py` + `ui/geometry.py` (konva bg image,
    freedraw lasso, region outlines, selection highlight)
  - `PreviewImage` ← the left-column `st.image` (+ quality-checks expander)
  - `RegionSelector` ← the persistent region radio + visibility toggles
  - Right-hand `Manage | Colour | Technique`:
    - `ManagePanel` ← `ui/regions_panel.render_management`
    - **`ColourPanel`** ← `ui/colour_panel.py` (the largest piece: `_render_level1`
      scheme/harmony gen, `_render_level2` ramp editor, `_render_level3` per-slot
      paint picker + catalog match, recipe manager, scheme save)
    - `TechniquePanel` ← `ui/results.render_technique_controls` (matte-only;
      NMM/Glow controls omitted)
- **PaintTab** ← `ui/results.render_steps` → `StepList` (zone/cumulative/exact
  + captions + ownership badges; OSL steps omitted)
- **PaintsTab** ← `ui/paints_tab.py` → `PaintInventory` (catalog browse, owned
  toggles, import/export)
- **AnglesTab** ← `ui/gallery_panel.py` → `AngleGallery` (read-only previews)
- **CaptureTab** ← `app.py` capture block → `CaptureGuide` (static markdown;
  the PS-capture section is dropped)
- **Cross-cutting**: `api.ts` typed client; `useAnalyze` hook (debounced
  ~150ms, fires on active-angle book/settings change); `projectStore` +
  `uiStore` (selected region, active tab/sub-tab, language, loading/error).

## 8. Data flow (one edit cycle)

1. User scrubs a coverage slider → updates
   `projectStore.angles[active].book.whole.coverage`.
2. `useAnalyze` (debounced) POSTs `/api/analyze` with
   `{photo_id, regions(points), whole, settings}`.
3. Server: rehydrate shading (cache hit) → rasterize masks (cache hit) →
   `analyze_regions` → memoize by token → serialize **combined preview** →
   return `{preview_png, result_token, plans_meta}`.
4. Client swaps the preview image. If the Paint tab is open, it lazily GETs
   `/api/steps?token=…` and renders the step images.

## 9. Error handling

- **Upload**: type/size validated client-side and server-side; the server runs
  `input_check.check_input` and returns `quality_checks` so the "photo quality"
  panel is preserved.
- **Analyze / scheme / match failures**: server returns 4xx/5xx with a message;
  the client shows an inline error banner (replacing `st.error` /
  `st.exception`). A failed analyze leaves the previous preview in place.
- **Cache misses / expired token**: `/steps` with an unknown token returns 409;
  the client transparently re-POSTs `/analyze` to refresh the token.
- **Persistence**: save uses the existing atomic tmp-dir-then-`os.replace`
  pattern in `projects.save_project`; corrupt/legacy manifests are handled by
  the v1/v5→v6 adapters.

## 10. Rollout — thin slice first, tab by tab

- **Phase 0 — scaffold + vertical slice.** Stand up `backend/` (health +
  `/api/photo` + `/api/analyze`) and `web/` (Vite/React/TS/Zustand). Prove
  **upload → live preview** end to end. This validates the entire pipe (image
  transport, caching, render loop) before any feature breadth.
- **Then, feature by feature:** Studio regions → ColourPanel → Paint steps →
  Paints inventory → Angles gallery → Schemes → project save/load → i18n port →
  Capture guide.
- **Coexistence is permanent until you decide otherwise.** Streamlit
  (`streamlit run app.py`, :8501) stays fully runnable throughout. The two apps
  share `src/` and the on-disk project format, so a project saved in one opens
  in the other.
- **Streamlit removal is a separate, optional, final step.** Retiring `app.py`
  + `ui/` + the `streamlit*` deps happens only when *you* judge React has
  reached parity and earned trust — it is explicitly **not** part of "migration
  done." Deferring it indefinitely is a supported outcome.

## 11. Post-migration follow-ups (captured, not in this port)

- **Colour-selection UX reordering.** All colour functionality is correct, but
  the *order of operations* in the picker feels awkward. This is deliberately
  **not** addressed during the port (a faithful port keeps a clear oracle:
  "does it match Streamlit?"). Once on React, UX iteration is cheap, and some of
  the awkwardness may be a Streamlit rerun-order artifact (`level1→2→3` forced
  execution) that dissolves under real components. Specific reordering asks to
  be gathered and specced separately after parity.
- Possible later re-introduction of PS / OSL / NMM in React (own effort).
- Optional switch from base64 image payloads to blob-URL endpoints if payload
  size becomes noticeable.

## 12. Testing strategy

- **Core (`src/`)**: existing pytest suite untouched — it already covers the
  logic the backend calls.
- **Backend**: FastAPI `TestClient` contract tests — upload→analyze→steps happy
  path, `/scheme/generate`, project save/load round-trip, `/match`, and the
  token-expiry re-analyze path.
- **Frontend**: Vitest + React Testing Library, kept light (personal tool) and
  focused on the seams that carry risk: the Zustand store transitions, the
  `api.ts` client, `RegionCanvas` point capture + coordinate scaling, and the
  `useAnalyze` debounce / tab-isolation behavior.
- **Manual parity checklist** vs. Streamlit per feature slice (screenshot the
  same project in both; previews and steps should match).

## 13. Effort estimate

These are **Claude token budgets** across the build (model I/O), **not** hours
of the owner's time. Owner involvement is steering + review + eyeballing the
running app — roughly an hour or two of attention per slice, spread over as many
sittings as desired.

| Slice | Rough tokens | Model |
|---|---|---|
| This spec + implementation plan(s) | 25–40k | Opus |
| FastAPI backend (all endpoints) | 30–50k | Sonnet |
| Frontend scaffold + store + api + Studio vertical slice | 40–60k | mixed |
| ColourPanel (scheme-gen + ramp editor + paint picker) | 40–60k | Opus/Sonnet |
| RegionCanvas (konva lasso + outlines + selection) | 20–35k | Sonnet |
| Paint / Angles / Paints / Capture + i18n port + save/load | 40–60k | Sonnet |
| Integration, parity smoke, (optional) Streamlit removal | 15–25k | mixed |

**Total ≈ 180–280k tokens.** The spec will be decomposed by the writing-plans
step into **several implementation plans** (one per coherent slice), each on its
own feature branch + PR, rather than one monolithic plan.

## 14. Risks & open questions

- **Payload size** of base64 step images on very large photos — mitigated by the
  analyze/steps split, client debounce, and server memoization; escalation path
  is blob-URL endpoints.
- **ColourPanel is the complexity hotspot** — its three "levels" and the recipe
  manager carry the most state; it should get the most careful decomposition in
  its plan (and is the natural place UX-reordering later lands).
- **Legacy (v5) projects** with mask-only regions render as immutable overlays;
  acceptable given outlines are already immutable, but worth a parity check.
- **react-konva coordinate scaling** (canvas display size vs. image pixels) must
  reuse the same convention as `regions.scale_points` so masks land correctly.
```
