# Studio UX Reshape — Approach A — Design Spec

- **Date:** 2026-09-23
- **Status:** Approved — pending implementation plan
- **Owner:** Alvaro
- **Branch:** `feat/studio-ux-approach-a`
- **Reshapes:** `web/src/App.tsx` Studio panel, `web/src/components/RightPanel.tsx`,
  `web/src/components/colour/*`, `web/src/components/AngleBar.tsx` / `AngleGallery.tsx`
- **Data model:** unchanged. This is a **presentation + scope-separation** reshape.
  No new store fields, no wire-type changes, no engine changes.

---

## 1. Motivation

The React Studio shipped and is in real use. Using it surfaced one root defect and a
set of follow-on UX issues. The root defect is **scope mixing**: the Colour tab stacks
a *book-level* operation (Scheme/Hero generation, which writes palettes to **every**
region at once) directly on top of *region-local* editors (Ramp, Bands, Coverage) with
identical visual weight and no scope signal. This is why editing "one region" appears to
change others — `SchemeGenerator` iterates `regionNames.map(...)` and `hero_hex` is stored
at book level (`setHeroHex → b.hero_hex`), so it is behaving exactly as built; the layout
just hides that it is a whole-mini action.

Everything else the reshape addresses follows from making scope explicit and from promoting
**bands** to the primary colour object.

### What we are NOT changing (settled during brainstorming)

- **Angles stay independent.** Each `Angle` owns its own `Book` (regions + palettes +
  schemes). There is no cross-angle recipe sharing and no attempt to enforce one — a mask
  drawn on one photo has no correspondence on another. The sharing primitive is
  **save a recipe on one angle, lasso + apply it on the next**. This is correct; leave it.
- **One paint per band.** The engine (`band_light`) partitions pixels into N bands, one
  paint each. "Multiple paints per band / wet blend" is a *painting instruction*, not a
  recipe/render concept — it belongs in the Paint guide, never the recipe editor. The
  existing **Blend** (`↕`) action stays as-is: it sets a band's colour to the interpolated
  midpoint of its two neighbours. It is not reorder and not paint-mixing.
- **Meaning of Scheme / Hero.** Not redefined. Hero = the anchor seed for cross-region
  harmony generation; Scheme = "generate coordinated palettes for the whole mini from one
  anchor + harmony rule." We make their *scope* visible; we do not touch their semantics.
- **Coverage semantics.** Coverage is the fraction of a region's tonal range each band
  occupies (Shadow→Highlight), summing to 1, last band auto-derived. Unchanged.

---

## 2. Goals

After this reshape, in the Studio tab a user can:

- See at a glance that Studio reads top-to-bottom as **WHOLE MINI → REGION → BANDS** —
  scope is spatial, not guessed.
- Keep the miniature preview **always visible** while editing, including when the band list
  is long (sticky preview; only the editor column scrolls).
- Edit a **band as the primary object**: role, colour control, live paint-match, and its
  coverage all live in one card.
- Run whole-mini palette **Generate** from a demoted, collapsible surface that is clearly
  separated from region-local editing.
- **Undo** any destructive colour action (Generate, Load, Reset coverage), and additionally
  get an explicit **Load → preview → Apply** step so loading a recipe never silently
  overwrites the current region's palette.
- Paint the region-selection lasso as a **continuous** drag rather than a
  draw-then-release gesture.
- Manage angles from **one** home (the Angles gallery) with only lightweight switch + quick-add
  in the persistent top bar.

### Out of scope (deferred, not rejected)

- **Click-a-region-on-the-mini** selection (Approach B increment). Region selection stays via
  the lasso + a compact switcher for now.
- **Preview layout variants** (large-centre / interactive overlay). Preview stays left, sticky.
- **Metallic-aware paint matching.** `finish` is region-local and earns its place in the region
  editor now; steering matching toward metallic-flagged catalog paints is a later hook.
- **Rename of the "Whole mini" collision** (see §10). Filed, not fixed here.
- Any change to the Paint, Paints, or Angles *processing*; this reshape is Studio-surface only.

---

## 3. Layout — Approach A

Studio remains a two-column layout: **preview left, editor column right.** The editor column
is a single scrolling stack (no more `Manage | Colour | Technique` sub-tabs inside it for the
colour flow — see §3.5 for what happens to those). Vertical order encodes scope.

```
┌─────────────┐  ┌───────────────────────────────────────┐
│  MINIATURE  │  │ ▸ Generate palette (whole mini)  [▾]   │  WHOLE-MINI scope
│  (preview)  │  │   hero · mood · harmony   [Generate]   │  (collapsible)
│             │  ├───────────────────────────────────────┤
│  STICKY —   │  │ EDITING: [ Cloak ▾ ]                    │  REGION scope
│  stays in   │  │ surface · tone · finish                │
│  view while │  │ ┌───────────────────────────────────┐  │
│  the right  │  │ │ Shadow                            │  │  BAND scope
│  column     │  │ │ [swatch] Dark Green / AK11147     │  │  (primary object)
│  scrolls    │  │ │ Coverage 33%  ───────●──────────  │  │
│             │  │ ├───────────────────────────────────┤  │
│             │  │ │ Base                              │  │
│             │  │ │ [swatch] Bright Green / AK11146   │  │
│             │  │ │ Coverage 27%  ─────●────────────  │  │
│             │  │ ├───────────────────────────────────┤  │
│             │  │ │ Highlight            13% (auto)   │  │  auto band = chip
│             │  │ └───────────────────────────────────┘  │
│             │  │ + Add band                             │  recipe-level
│             │  │ Ramp   Load…   Save     ↺ Undo         │
└─────────────┘  └───────────────────────────────────────┘
```

### 3.1 Sticky preview, scrolling editor

The preview (`PreviewImage`) is pinned so it stays in view as the editor column overflows.
Implementation: the Studio `Group` keeps `align="flex-start"`; the preview column gets
`position: sticky; top: <offset>` (or an equivalent sticky wrapper), and the editor column
is the only scroll region. This is the load-bearing detail — with up to 7 band cards plus the
Generate and region blocks, the column *will* overflow a laptop viewport, and the "change band
→ see result" loop must survive that.

### 3.2 Whole-mini Generate surface (scope-lifted)

`SchemeGenerator` is lifted to the **top** of the editor column, inside a collapsible block
titled "Generate palette (whole mini)". It keeps its current behaviour and inputs (anchor
region, hero hex, mood, harmony, per-region surface/tone table, owned-only, Generate).

**Collapse default is state-driven:**
- **Expanded** when the active region is still greyscale defaults (palette entries are the
  `#808080` neutral placeholder from `neutralRegion` / `default_whole`) — i.e. nothing has been
  generated yet.
- **Collapsed** to a one-line summary once a real palette exists, so it is out of the way during
  band work but one click from a re-roll.

**Scope-leak fix — surface/tone move out.** `surface` and `tone` are region-local
(`setSurface(g,…)`, `setTone(g,…)`) but are currently edited inside this book-level panel's
per-region table. They move to the **region header** (§3.3). The Generate panel keeps only the
whole-mini inputs (anchor, hero, mood, harmony). (If the harmony generator still needs
per-region surface/tone as *inputs*, it reads them from region state rather than owning their
editing UI.)

### 3.3 Region header + switcher

Directly below Generate, a region header block:

- **`EDITING: [ region ▾ ]`** — a compact switcher (segmented control or select) listing
  `Whole mini` + every drawn region; changing it calls `setSelected(g)`. This is the "compact
  selector, no permanent rail" decision. Add-region and lasso stay on the preview side, not here.
- **surface · tone · finish** for the selected region (`setSurface`, `setTone`, `setMaterial`),
  moved here from the Generate table. `finish` (matte/metallic) stays region-local and is the
  future hook for metallic-aware matching.

The header makes region context unmissable: once Generate (the only whole-mini surface) is
above it, *everything below the header edits the selected region only*.

### 3.4 Band cards (primary colour object)

`BandEditor` renders one **card** per band (replacing the flat `BandSlot` rows). Each card:

- **Role name as the band's identity** — `Shadow · Base · Midtone · Highlight …` from the
  existing `roleNames(n)`. No bare numbers. The role tells a painter what the band is *for*;
  a number does not.
- **Live colour control**, not a static label: swatch + the existing catalog-select / custom-hex
  toggle (`setPaletteSlot` / `setHexSlot`). When the slot is a custom hex, the computed
  paint-match hint (`✓ / ≈ / mix / Buy…`, already produced in `BandSlot`) renders under the
  control. This is where the target-colour → matched-paint relationship finally becomes visible
  instead of hidden behind an either/or toggle.
- **Coverage in-card** — the coverage slider for this band lives inside the card, immediately
  below the colour control, instead of in a separate `CoverageEditor` section. Model is unchanged:
  `palette[i]` and `coverage[i]` are parallel arrays indexed by the same `i`, so this is a pure
  relocation.
- **Auto band = chip, not slider.** The top (highlight) band is the auto-derived remainder;
  render it as a static `Highlight · 13% (auto)` chip, never a dead slider, so nobody grabs it and
  wonders why it will not move.
- **Blend (`↕`)** stays available between interior bands (unchanged meaning: interpolate the
  midpoint hex of the two neighbours).
- **No drag-to-reorder.** Band order is tonal (dark→light) and fixed by definition; reordering is
  meaningless to the renderer. "Obvious ordering" is achieved by showing the tonal progression
  (top = shadow, swatches darkening→lightening down the stack), not by making it draggable.

**Add / remove band become clear, single actions.** Today every `BandSlot` carries its own
`＋`/`✕` (adding a band is a recipe action rendered N times). Pull them out: a single **`+ Add band`**
button in the recipe footer for adding, and **remove-band as a per-card `✕`** — the card owns its own
removal, consistent with the card being the primary object. The `✕` is disabled at the 3-band floor;
`+ Add band` is disabled at the 7-band ceiling. Clamp stays 3–7 (`setBandCount`).

### 3.5 Recipe footer + what happens to Manage / Technique

Below the band cards, a recipe-level footer: **`+ Add band` · `Ramp` · `Load…` · `Save` · `↺ Undo`.**

- **Ramp** (`RampEditor`) is a secondary tool here — region-local, seeds the whole band ramp from a
  midtone. It moves into the footer / a small popover rather than being a co-equal top-level section.
- **Load… → preview → Apply** (see §4).
- **Save** (`RecipeSaver`) unchanged.
- **Undo** (see §4).

**Decision (was open):** the `RightPanel` `Manage | Colour | Technique` sub-tab strip is removed. The
colour/region editor described in §3.2–§3.5 becomes the **default Studio surface** — it is no longer
behind a `Colour` tab. The other two panels are handled as follows:

- **Technique** (`TechniquePanel`) is **removed as a separate surface.** Its only current control is
  `material` (matte / metallic), which is precisely the region-local **finish** that moves into the
  region header (§3.3). Keeping a slim Technique tab would duplicate that one control, and advanced
  technique (NMM etc.) is excluded from the web app entirely. So material/finish lives in the region
  header, and `TechniquePanel` is retired. (If a future technique surface is needed, it returns as its
  own region-scoped block — but YAGNI for now.)
- **Manage regions** (`ManagePanel`: draw / add / rename / remove, plus the `blank`/visible toggle
  relocated from the retired `RegionSelector`) is kept as a **compact control near the region header**.
  The header owns *switch* (`EDITING: [region ▾]`); Manage owns *draw / add / rename / remove / visible*.
  This resolves the duplication (two surfaces — `RegionSelector` radio + `ManagePanel` — that both
  touched regions) into one clear split, mirroring the angles switch-vs-CRUD split in §5. `RegionSelector`
  (the radio list) is retired; its selection role moves to the header switcher and its `visible` toggle
  moves into `ManagePanel`.

Net: colour editing is the default surface; the region header owns switch + surface/tone/finish; region
CRUD (incl. visible) is one compact Manage control by the header; Technique and the old RegionSelector
radio are retired.

---

## 4. Undo + Load safety

Two complementary mechanisms:

1. **Global colour Undo (`↺`).** A single-level (or short-stack) undo that reverts the last
   destructive colour mutation on the active book: **Generate palette**, **Load recipe**, and
   **Reset coverage**. These are the actions that replace state wholesale and do not otherwise warn.
   Implementation: snapshot the relevant book slice before the mutation; `↺` restores it. This is
   what makes a live preview safe to *experiment* with, which is the whole point of live preview.

2. **Explicit Load → preview → Apply.** `RecipeLoader` currently calls
   `setPaletteAt(book.selected, …)` immediately on Load — it replaces **only the current region's
   palette** (not coverage, not other regions), but it is still a silent whole-palette swap. New flow:
   select recipe → **preview** the incoming palette (show its swatches, and state that it replaces the
   current region's palette only) → **Apply**. Cancel leaves the region untouched.

Undo and Apply are not redundant: Apply guards the one loud action a dialog fits; Undo covers Generate
and Reset coverage, which will not wear dialogs.

---

## 5. Angles — one management home

Resolve the "two homes for one job" duplication between `AngleBar` (persistent, above the tabs) and
the Angles tab (`AngleGallery`).

- **Top bar (`AngleBar`)** = lightweight **switch + quick-add** only. Keep the angle chips and a
  `+ angle`. Remove the rename field and delete control from the bar.
- **Angles gallery (`AngleGallery`)** = the **CRUD home**: add, rename, delete, reorder, select. Heavy
  angle management lives here and only here.

No store changes — both already call the same `projectStore` actions (`switchAngle`, `addAngle`,
`renameAngle`, `removeAngle`); this is purely which surface exposes which action.

---

## 6. Continuous lasso

The region-selection lasso in `RegionCanvas` should paint continuously **during** the pointer drag
rather than only committing on release. As the pointer moves while pressed, the in-progress selection
updates live. Selection *semantics* (what the closed region means, how it becomes a `Region`) are
unchanged — this is an input-handling improvement only, isolated to `RegionCanvas`.

---

## 7. Component-level change map

| Area | File(s) | Change | Cost |
|---|---|---|---|
| Studio layout | `App.tsx` | Sticky preview column; editor column becomes the scroll region | Small |
| Scope lift | `App.tsx`, `RightPanel.tsx` (retired), `ColourPanel.tsx` | Colour flow becomes default Studio surface; sub-tab strip removed; Generate lifted to top, collapsible; region editor below | Medium |
| Generate panel | `SchemeGenerator.tsx` | Drop per-region surface/tone editing (moves to header; still read as generate inputs from region state); add collapse state | Small–Med |
| Region header | new (e.g. `RegionHeader.tsx`) | `EDITING: [region ▾]` switcher + surface/tone/finish(material) | Small |
| Technique retired | `TechniquePanel.tsx` | Removed; its only control (material/finish) moves to region header | Small |
| Region select | `RegionSelector.tsx` (retired), `ManagePanel.tsx` | Radio retired; selection → header switcher; `visible`/blank toggle → `ManagePanel` | Small |
| Band cards | `BandEditor.tsx`, `BandSlot.tsx` → card | Role name, live colour control + match hint, in-card coverage, auto chip, single Add-band footer, no reorder | Medium |
| Coverage | `CoverageEditor.tsx` | Dissolved into band cards (last band → auto chip) | Small |
| Ramp | `RampEditor.tsx` | Demote to footer tool / popover | Small |
| Load safety | `RecipeLoader.tsx` | Load → preview → Apply | Small–Med |
| Undo | `projectStore.ts` + footer control | Snapshot/restore last destructive colour mutation | Medium |
| Angles | `AngleBar.tsx`, `AngleGallery.tsx` | Bar = switch/quick-add; gallery = CRUD home | Small |
| Lasso | `RegionCanvas.tsx` | Continuous-drag selection | Small |

No changes to: `projectStore` data shape (only an undo snapshot buffer), `api/types.ts`, backend,
`useAnalyze`, or the Python engine.

---

## 8. Data flow (unchanged)

`useAnalyze` already watches `book.whole` and `book.drawn` and re-fires on any palette/coverage/
material change, so the live-preview loop needs no new wiring — relocating coverage into band cards
still mutates the same `coverage[]` array via the same `setCoverage`, and the preview updates as it
does today. The only new store surface is the undo snapshot buffer (§4).

---

## 9. Testing

- **Component tests** (Vitest, matching existing `*.test.tsx`): band card renders role name +
  colour control + coverage + match hint; auto band renders a chip, not a slider; add-band is a
  single footer control clamped 3–7; region switcher calls `setSelected`; Generate collapse state
  follows greyscale-default vs generated.
- **Undo**: after Generate / Load / Reset coverage, `↺` restores the prior book slice (store test).
- **Load → Apply**: preview does not mutate state; Apply replaces only the current region's palette;
  Cancel is a no-op (component + store test).
- **Angles**: `AngleBar` no longer exposes rename/delete; `AngleGallery` does (component tests).
- **Lasso**: continuous-drag updates selection before release (`RegionCanvas` test).
- Manual smoke: long recipe (7 bands) keeps the preview pinned while the editor scrolls.

---

## 10. Open naming flag (file, do not fix here)

"Whole mini" names **two** things: the leftover **region** (region 0) and the scope of the
**Generate palette** action. Same words, two scopes — a latent confusion once users internalise the
WHOLE→REGION→BANDS hierarchy. Candidate future rename: call the leftover region something like
"Base coat / Everything else" and reserve "whole mini" for the Generate scope. Out of scope for this
reshape.

---

## 11. Sequencing note for the plan

Rough dependency order (the writing-plans step will formalise): (1) sticky preview + editor scroll,
(2) scope lift — Generate to top + region header + surface/tone relocation, (3) band cards + coverage
merge, (4) undo + Load/Apply, (5) angles home split, (6) continuous lasso. Each is independently
shippable and testable; none blocks the next except (3) depends on (2)'s region header existing.
