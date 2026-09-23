# Studio UX Reshape — Approach A — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Reshape the React Studio so scope reads top-to-bottom (whole-mini → region → bands), the preview stays pinned while editing, bands become the primary colour object with in-card coverage, and destructive colour actions are reversible.

**Architecture:** Pure frontend reshape of `web/src`. No backend, no wire-type, and no Python-engine changes. The Studio right column becomes a single scrolling stack of new/refactored components (`GeneratePanel`, `RegionHeader`, `ManagePanel`, `BandEditor`+`BandCard`) inside a new `StudioPanel` with a sticky preview. One new store field (an undo snapshot) is the only state-shape addition.

**Tech Stack:** React 18 + TypeScript, Vite, Mantine v7, Zustand, react-konva (lasso), Vitest + Testing Library, react-i18next.

**Spec:** `docs/superpowers/specs/2026-09-23-studio-ux-approach-a-design.md`

## Global Constraints

- **No data-model / wire-type changes.** `api/types.ts` wire types and the `Book`/`Angle`/region shapes are unchanged except for adding an undo snapshot field to the store (never serialised). Copied from spec §1/§7/§8.
- **One paint per band.** Do not add multi-paint-per-band or reorder. `Blend (↕)` keeps its meaning (interpolated midpoint of neighbours). Spec §1.
- **Band count clamps 3–7** (`setBandCount`). Spec §3.4.
- **Coverage invariant:** sums to 1, last band auto-derived. Spec §1/§3.4.
- **i18n:** user-facing strings go through `t(...)`. Tests mock `react-i18next` so `t(k) => k` (assert on keys). Existing pattern — see `CoverageEditor.test.tsx`.
- **Test runner:** from `web/`, run `npx vitest run <file>`. Full suite: `npm test`.
- **Store test reset idiom:** `useProjectStore.setState(useProjectStore.getInitialState(), true)` then `initFromPhoto(photo())`. Copied from `CoverageEditor.test.tsx`.
- **Branch:** `feat/studio-ux-approach-a` (already checked out). Feature branch + PR; never commit to `main`.

---

## File Structure

**New files:**
- `web/src/lib/roles.ts` — `roleNames(n)` + `defaultCoverage(n)` (moved out of `CoverageEditor`, shared by band cards).
- `web/src/components/StudioPanel.tsx` — the Studio surface: sticky preview column + scrolling editor column.
- `web/src/components/colour/GeneratePanel.tsx` — whole-mini palette generation (refactor of `SchemeGenerator`, collapsible, no per-region surface/tone table).
- `web/src/components/RegionHeader.tsx` — `EDITING: [region ▾]` switcher + surface/tone/finish for the selected region + a toggle to reveal Manage-regions.
- `web/src/components/colour/BandCard.tsx` — one band as a card (refactor of `BandSlot`): role name, colour control + match hint, in-card coverage (or auto chip), per-card `✕`.
- `web/src/components/colour/RecipeFooter.tsx` — `+ Add band`, `Ramp`, `Load…`, `Save`, `Reset coverage`, `↺ Undo`.

**Modified files:**
- `web/src/App.tsx` — Studio tab renders `<StudioPanel/>` instead of the inline `PreviewImage`+`RegionSelector`+`RightPanel`.
- `web/src/store/projectStore.ts` — add `undoSnapshot`, `snapshotUndo()`, `undo()`.
- `web/src/components/colour/BandEditor.tsx` — render `BandCard`s + `RecipeFooter`; own the coverage-change handler; drop the embedded `RecipeLoader`/`CoverageEditor`/`RecipeSaver` stack.
- `web/src/components/colour/RecipeLoader.tsx` — Load → preview → Apply.
- `web/src/components/ManagePanel.tsx` — absorb the `visible`/blank toggle from the retired `RegionSelector`.
- `web/src/components/AngleBar.tsx` — switch + quick-add only (remove rename/delete).
- `web/src/components/AngleGallery.tsx` — add select/rename/delete (CRUD home).

**Retired files (delete + remove imports):**
- `web/src/components/RegionSelector.tsx` (+ `.test.tsx`) — selection → header switcher; visible toggle → `ManagePanel`.
- `web/src/components/RightPanel.tsx` (+ `.test.tsx`) — sub-tab strip removed; children re-homed in `StudioPanel`.
- `web/src/components/colour/ColourPanel.tsx` — its stacking role is replaced by `StudioPanel`.
- `web/src/components/TechniquePanel.tsx` — material/finish moves to `RegionHeader`.
- `web/src/components/colour/CoverageEditor.tsx` (+ `.test.tsx`) — dissolved into band cards.

---

## Task 1: `StudioPanel` with sticky preview

Extract the Studio two-column layout into its own component and pin the preview. Editor content is unchanged this task (still the existing `RegionSelector` + `RightPanel`) — this task only proves the layout + sticky behaviour, so it ships working software before the deeper refactor.

**Files:**
- Create: `web/src/components/StudioPanel.tsx`
- Create: `web/src/components/StudioPanel.test.tsx`
- Modify: `web/src/App.tsx:55-63` (studio `Tabs.Panel`)

**Interfaces:**
- Produces: `StudioPanel()` — default Studio surface. Renders a sticky preview column (test id `studio-preview`) and a scrolling editor column (test id `studio-editor`).

- [ ] **Step 1: Write the failing test**

```tsx
// web/src/components/StudioPanel.test.tsx
import { describe, it, expect, beforeEach, vi } from "vitest";
import { render, screen } from "@testing-library/react";
import { MantineProvider } from "@mantine/core";
import { StudioPanel } from "./StudioPanel";
import { useProjectStore } from "../store/projectStore";
import type { PhotoResponse } from "../api/types";

vi.mock("react-i18next", () => ({ useTranslation: () => ({ t: (k: string) => k }) }));
// RegionCanvas uses react-konva (canvas) which jsdom cannot render — stub it.
vi.mock("./RegionCanvas", () => ({ RegionCanvas: () => null }));

const photo = (): PhotoResponse => ({
  photo_id: "p1", width: 10, height: 10, quality_checks: [],
  default_whole: { palette: [{ name: "a", hex: "#111" }, { name: "b", hex: "#aaa" }, { name: "c", hex: "#eee" }],
                   coverage: [0.5, 0.3, 0.2], material: "matte" },
});
const reset = () => useProjectStore.setState(useProjectStore.getInitialState(), true);

describe("StudioPanel", () => {
  beforeEach(() => { reset(); useProjectStore.getState().initFromPhoto(photo()); });

  it("renders a sticky preview column and an editor column", () => {
    render(<MantineProvider><StudioPanel /></MantineProvider>);
    const preview = screen.getByTestId("studio-preview");
    expect(preview).toBeTruthy();
    expect(preview.style.position).toBe("sticky");
    expect(screen.getByTestId("studio-editor")).toBeTruthy();
  });
});
```

Add `import { vi } from "vitest";` to the import line if the runner needs it explicit (other tests in this repo call `vi.mock` with `vi` from the top `import`; match `CoverageEditor.test.tsx` which imports `vi` in the first line).

- [ ] **Step 2: Run test to verify it fails**

Run: `cd web && npx vitest run src/components/StudioPanel.test.tsx`
Expected: FAIL — cannot find `./StudioPanel`.

- [ ] **Step 3: Create `StudioPanel`**

```tsx
// web/src/components/StudioPanel.tsx
import { Box, Group, Stack } from "@mantine/core";
import { PreviewImage } from "./PreviewImage";
import { RegionSelector } from "./RegionSelector";
import { RightPanel } from "./RightPanel";

export function StudioPanel() {
  return (
    <Group align="flex-start" gap="xl" wrap="nowrap">
      <Box data-testid="studio-preview"
        style={{ position: "sticky", top: 16, alignSelf: "flex-start", maxWidth: 360, flexShrink: 0 }}>
        <PreviewImage />
      </Box>
      <Stack data-testid="studio-editor" style={{ flex: 1 }}>
        <RegionSelector />
        <RightPanel />
      </Stack>
    </Group>
  );
}
```

- [ ] **Step 4: Wire into `App.tsx`**

Replace the studio panel body (`App.tsx:55-63`) with:

```tsx
<Tabs.Panel value="studio">
  <StudioPanel />
</Tabs.Panel>
```

Add `import { StudioPanel } from "./components/StudioPanel";` and remove now-unused `PreviewImage`, `RegionSelector`, `RightPanel`, `Group`, `Stack` imports from `App.tsx` **only if** they are unused after the change (keep `Group`/`Stack` if still referenced elsewhere in the file — they are not, so remove).

- [ ] **Step 5: Run tests + typecheck**

Run: `cd web && npx vitest run src/components/StudioPanel.test.tsx && npx tsc -b --noEmit`
Expected: PASS, no type errors.

- [ ] **Step 6: Commit**

```bash
git add web/src/components/StudioPanel.tsx web/src/components/StudioPanel.test.tsx web/src/App.tsx
git commit -m "feat(studio): extract StudioPanel with sticky preview"
```

---

## Task 2: `roles.ts` shared helper

Move `roleNames`/`defaultCoverage` out of `CoverageEditor` so band cards and coverage math share one source. (Pure move + test; `CoverageEditor` keeps working by importing from here until it is retired in Task 6.)

**Files:**
- Create: `web/src/lib/roles.ts`
- Create: `web/src/lib/roles.test.ts`
- Modify: `web/src/components/colour/CoverageEditor.tsx:5-19` (import instead of define)

**Interfaces:**
- Produces:
  - `roleNames(n: number): string[]` — e.g. `roleNames(4) === ["Shadow","Base","Midtone","Highlight"]`; `n` outside 3–7 → `["Layer 1", …]`.
  - `defaultCoverage(n: number): number[]` — descending weights normalised to sum 1.

- [ ] **Step 1: Write the failing test**

```ts
// web/src/lib/roles.test.ts
import { describe, it, expect } from "vitest";
import { roleNames, defaultCoverage } from "./roles";

describe("roles", () => {
  it("names the 4-band roles", () => {
    expect(roleNames(4)).toEqual(["Shadow", "Base", "Midtone", "Highlight"]);
  });
  it("falls back to Layer N outside 3-7", () => {
    expect(roleNames(2)).toEqual(["Layer 1", "Layer 2"]);
  });
  it("defaultCoverage sums to 1 and descends", () => {
    const cov = defaultCoverage(4);
    expect(cov[0]).toBeGreaterThan(cov[3]);
    expect(cov.reduce((a, b) => a + b, 0)).toBeCloseTo(1, 6);
  });
});
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd web && npx vitest run src/lib/roles.test.ts`
Expected: FAIL — cannot find `./roles`.

- [ ] **Step 3: Create `roles.ts`**

```ts
// web/src/lib/roles.ts
const _ROLES: Record<number, string[]> = {
  3: ["Shadow", "Base", "Highlight"],
  4: ["Shadow", "Base", "Midtone", "Highlight"],
  5: ["Shadow", "Base", "Midtone", "Highlight", "Bright Highlight"],
  6: ["Shadow", "Deep Base", "Base", "Midtone", "Highlight", "Bright Highlight"],
  7: ["Shadow", "Deep Base", "Base", "Midtone", "Upper Midtone", "Highlight", "Bright Highlight"],
};

export function roleNames(n: number): string[] {
  return _ROLES[n] ?? Array.from({ length: n }, (_, i) => `Layer ${i + 1}`);
}

export function defaultCoverage(n: number): number[] {
  const weights = Array.from({ length: n }, (_, i) => n - i);
  const total = weights.reduce((a, b) => a + b, 0);
  return weights.map((w) => w / total);
}
```

- [ ] **Step 4: Point `CoverageEditor` at the shared helper**

In `CoverageEditor.tsx`, delete the local `_ROLES`, `roleNames`, `defaultCoverage` (lines ~5–19) and add:

```tsx
import { roleNames, defaultCoverage } from "../../lib/roles";
```

- [ ] **Step 5: Run tests**

Run: `cd web && npx vitest run src/lib/roles.test.ts src/components/colour/CoverageEditor.test.tsx`
Expected: PASS (both).

- [ ] **Step 6: Commit**

```bash
git add web/src/lib/roles.ts web/src/lib/roles.test.ts web/src/components/colour/CoverageEditor.tsx
git commit -m "refactor(colour): extract shared roleNames/defaultCoverage into lib/roles"
```

---

## Task 3: Undo snapshot in the store

Single-level undo covering the destructive colour actions (Generate, Load-apply, Reset coverage). Callers snapshot before mutating; `undo()` restores.

**Files:**
- Modify: `web/src/store/projectStore.ts` (State interface + implementation)
- Create: `web/src/store/projectStore.undo.test.ts`

**Interfaces:**
- Consumes: `Book`, `activeBookOf` (existing).
- Produces (added to the store):
  - `undoSnapshot: { angle: number; book: Book } | null`
  - `snapshotUndo(): void` — deep-copies the active book into `undoSnapshot`.
  - `undo(): void` — restores `undoSnapshot` to its angle's book and clears it; no-op when null.

- [ ] **Step 1: Write the failing test**

```ts
// web/src/store/projectStore.undo.test.ts
import { describe, it, expect, beforeEach } from "vitest";
import { useProjectStore, activeBookOf } from "./projectStore";
import type { PhotoResponse } from "../api/types";

const photo = (): PhotoResponse => ({
  photo_id: "p1", width: 10, height: 10, quality_checks: [],
  default_whole: { palette: [{ name: "a", hex: "#111" }, { name: "b", hex: "#aaa" }, { name: "c", hex: "#eee" }],
                   coverage: [0.5, 0.3, 0.2], material: "matte" },
});
const reset = () => useProjectStore.setState(useProjectStore.getInitialState(), true);

describe("undo", () => {
  beforeEach(() => { reset(); useProjectStore.getState().initFromPhoto(photo()); });

  it("restores the palette captured by snapshotUndo", () => {
    const s = useProjectStore.getState();
    s.snapshotUndo();
    s.setHexSlot(0, 0, "#00ff00");
    expect(activeBookOf(useProjectStore.getState())!.whole.palette[0].hex).toBe("#00ff00");
    useProjectStore.getState().undo();
    expect(activeBookOf(useProjectStore.getState())!.whole.palette[0].hex).toBe("#111");
    expect(useProjectStore.getState().undoSnapshot).toBeNull();
  });

  it("undo is a no-op when there is no snapshot", () => {
    const s = useProjectStore.getState();
    s.setHexSlot(0, 0, "#00ff00");
    s.undo();
    expect(activeBookOf(useProjectStore.getState())!.whole.palette[0].hex).toBe("#00ff00");
  });
});
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd web && npx vitest run src/store/projectStore.undo.test.ts`
Expected: FAIL — `snapshotUndo`/`undo`/`undoSnapshot` undefined.

- [ ] **Step 3: Implement in the store**

Add to the `State` interface (near the other action signatures):

```ts
undoSnapshot: { angle: number; book: Book } | null;
snapshotUndo(): void;
undo(): void;
```

Add `undoSnapshot: null,` to `INITIAL_STATE`:

```ts
const INITIAL_STATE = { activeAngle: 0, angles: [] as Angle[], projectName: null as string | null, slug: null as string | null, undoSnapshot: null as { angle: number; book: Book } | null };
```

Add the actions in the `create<State>((set) => ({ ... }))` body:

```ts
snapshotUndo: () => set((s) => {
  const b = activeBookOf(s);
  return b ? { undoSnapshot: { angle: s.activeAngle, book: structuredClone(b) } } : {};
}),

undo: () => set((s) => {
  const snap = s.undoSnapshot;
  if (!snap) return {};
  const angle = s.angles[snap.angle];
  if (!angle) return { undoSnapshot: null };
  const angles = s.angles.slice();
  angles[snap.angle] = { ...angle, book: snap.book };
  return { angles, undoSnapshot: null };
}),
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd web && npx vitest run src/store/projectStore.undo.test.ts`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add web/src/store/projectStore.ts web/src/store/projectStore.undo.test.ts
git commit -m "feat(store): single-level undo snapshot for destructive colour actions"
```

---

## Task 4: `GeneratePanel` — whole-mini generation, collapsible

Refactor `SchemeGenerator` into `GeneratePanel`: keep whole-mini inputs (anchor region, hero, mood, harmony, owned-only, Generate), **drop** the per-region surface/tone editing table (those become generate *inputs read from region state*, edited later in `RegionHeader`), collapse when a scheme already exists, and snapshot undo before generating.

**Files:**
- Create: `web/src/components/colour/GeneratePanel.tsx`
- Create: `web/src/components/colour/GeneratePanel.test.tsx`
- Delete (end of task): `web/src/components/colour/SchemeGenerator.tsx`

**Interfaces:**
- Consumes: `snapshotUndo` (Task 3), `generateScheme` (`api/client`), store setters `setPaletteAt/setHeroHex/setMood/setVariant`, region `surface`/`tone` from `book.whole`/`book.drawn`.
- Produces: `GeneratePanel()` — collapsible whole-mini generate block. Collapsed by default when `book.hero_hex` is set; expanded when it is not. Exposes a toggle (test id `generate-toggle`). Renders the Generate button (`colour.generate`).

- [ ] **Step 1: Write the failing test**

```tsx
// web/src/components/colour/GeneratePanel.test.tsx
import { describe, it, expect, beforeEach, vi } from "vitest";
import { render, screen } from "@testing-library/react";
import { MantineProvider } from "@mantine/core";
import { GeneratePanel } from "./GeneratePanel";
import { useProjectStore } from "../../store/projectStore";
import type { PhotoResponse } from "../../api/types";

vi.mock("react-i18next", () => ({ useTranslation: () => ({ t: (k: string) => k }) }));
vi.mock("../../store/catalogStore", () => ({ useCatalogStore: (sel: any) => sel({ paints: [] }) }));

const photo = (): PhotoResponse => ({
  photo_id: "p1", width: 10, height: 10, quality_checks: [],
  default_whole: { palette: [{ name: "a", hex: "#111" }, { name: "b", hex: "#aaa" }, { name: "c", hex: "#eee" }],
                   coverage: [0.5, 0.3, 0.2], material: "matte" },
});
const reset = () => useProjectStore.setState(useProjectStore.getInitialState(), true);

describe("GeneratePanel", () => {
  beforeEach(() => { reset(); useProjectStore.getState().initFromPhoto(photo()); });

  it("is expanded (Generate button visible) when no scheme has been generated", () => {
    render(<MantineProvider><GeneratePanel /></MantineProvider>);
    expect(screen.queryByText("colour.generate")).toBeTruthy();
  });

  it("is collapsed (Generate button hidden) once hero_hex is set", () => {
    useProjectStore.getState().setHeroHex("#c0392b");
    render(<MantineProvider><GeneratePanel /></MantineProvider>);
    expect(screen.queryByText("colour.generate")).toBeNull();
    expect(screen.getByTestId("generate-toggle")).toBeTruthy();
  });

  it("does not render a per-region surface/tone table", () => {
    render(<MantineProvider><GeneratePanel /></MantineProvider>);
    expect(screen.queryByText("colour.tone")).toBeNull();
  });
});
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd web && npx vitest run src/components/colour/GeneratePanel.test.tsx`
Expected: FAIL — cannot find `./GeneratePanel`.

- [ ] **Step 3: Create `GeneratePanel`**

Adapt `SchemeGenerator` (start from its source). Remove the `perRegion` state and the `<Table>` of surface/tone. Read surface/tone for the generate request from region state. Add collapse state. Snapshot before generate.

```tsx
// web/src/components/colour/GeneratePanel.tsx
import { useState } from "react";
import { useTranslation } from "react-i18next";
import { ActionIcon, Button, Checkbox, ColorInput, Group, NativeSelect, Stack, Text } from "@mantine/core";
import { useProjectStore, activeBookOf } from "../../store/projectStore";
import { useCatalogStore } from "../../store/catalogStore";
import { generateScheme } from "../../api/client";
import { MOODS, VARIANTS } from "../../api/types";
import type { RegionColorSpec } from "../../api/types";

export function GeneratePanel() {
  const { t } = useTranslation();
  const book = useProjectStore((s) => activeBookOf(s));
  const catalogPaints = useCatalogStore((s) => s.paints);
  const setPaletteAt = useProjectStore((s) => s.setPaletteAt);
  const setHeroHex = useProjectStore((s) => s.setHeroHex);
  const setMood = useProjectStore((s) => s.setMood);
  const setVariant = useProjectStore((s) => s.setVariant);
  const snapshotUndo = useProjectStore((s) => s.snapshotUndo);

  const [anchorIndex, setAnchorIndex] = useState(0);
  const [heroHex, setHeroHexLocal] = useState(() => book?.hero_hex ?? "#c0392b");
  const [mood, setMoodLocal] = useState(() => book?.mood ?? "neutral");
  const [variant, setVariantLocal] = useState(() => book?.variant ?? "complementary");
  const [ownedOnly, setOwnedOnly] = useState(false);
  const [loading, setLoading] = useState(false);
  // Collapsed once a scheme exists (hero_hex set); user can override.
  const [open, setOpen] = useState<boolean | null>(null);

  if (!book) return null;
  const expanded = open ?? !book.hero_hex;
  const regionNames = ["Whole Mini", ...book.drawn.map((r) => r.name)];
  const ownedCodes = ownedOnly ? catalogPaints.map((p) => p.code ?? "").filter(Boolean) : [];
  const surfaceOf = (i: number) => (i === 0 ? book.whole.surface : book.drawn[i - 1]?.surface) ?? "skin";
  const toneOf = (i: number) => (i === 0 ? book.whole.tone : book.drawn[i - 1]?.tone) || undefined;

  const handleGenerate = async () => {
    setLoading(true);
    try {
      snapshotUndo();
      const anchorName = regionNames[anchorIndex] ?? "Whole Mini";
      const specs: RegionColorSpec[] = regionNames.map((name, i) => ({
        region_name: name, surface: surfaceOf(i), tone: toneOf(i),
        n_bands: i === 0 ? book.whole.palette.length : book.drawn[i - 1].palette.length,
        is_anchor: i === anchorIndex,
      }));
      const res = await generateScheme({ specs, anchor_name: anchorName, anchor_hex: heroHex, mood, variant, owned_codes: ownedCodes });
      regionNames.forEach((name, i) => { const pal = res.palettes[name]; if (pal) setPaletteAt(i, pal); });
      setHeroHex(heroHex); setMood(mood); setVariant(variant);
    } finally { setLoading(false); }
  };

  return (
    <Stack gap="xs">
      <Group justify="space-between">
        <Text size="sm" fw={500}>{t("colour.generate_whole_mini")}</Text>
        <ActionIcon size="sm" variant="subtle" data-testid="generate-toggle"
          onClick={() => setOpen(!expanded)} aria-label="toggle generate">
          {expanded ? "▾" : "▸"}
        </ActionIcon>
      </Group>
      {expanded && (
        <>
          <Group gap="xs" align="flex-end" wrap="wrap">
            <NativeSelect label={t("colour.anchor_region")} size="xs"
              value={anchorIndex} onChange={(e) => setAnchorIndex(Number(e.target.value))}>
              {regionNames.map((name, i) => <option key={i} value={i}>{name}</option>)}
            </NativeSelect>
            <ColorInput label={t("colour.hero_colour")} value={heroHex} onChange={setHeroHexLocal}
              format="hex" size="xs" withEyeDropper={false} />
            <NativeSelect label={t("colour.mood")} size="xs" value={mood}
              onChange={(e) => setMoodLocal(e.target.value)}
              data={MOODS.map((m) => ({ value: m, label: t(`moods.${m}`) }))} />
            <NativeSelect label={t("colour.harmony")} size="xs" value={variant}
              onChange={(e) => setVariantLocal(e.target.value)}
              data={VARIANTS.map((v) => ({ value: v, label: t(`variants.${v}`) }))} />
          </Group>
          <Group gap="sm">
            <Checkbox size="xs" label={t("colour.owned_only")} checked={ownedOnly}
              onChange={(e) => setOwnedOnly(e.currentTarget.checked)} />
            <Button size="xs" onClick={handleGenerate} loading={loading}>{t("colour.generate")}</Button>
          </Group>
        </>
      )}
    </Stack>
  );
}
```

Add i18n key `colour.generate_whole_mini` (e.g. "Generate palette (whole mini)") to `web/src/i18n/en.json` (and a placeholder in `es.json` — copy the English string if no translation is ready). Tests use `t(k) => k`, so they assert on keys, not values.

- [ ] **Step 4: Run test to verify it passes**

Run: `cd web && npx vitest run src/components/colour/GeneratePanel.test.tsx`
Expected: PASS.

- [ ] **Step 5: Delete `SchemeGenerator`**

Delete `web/src/components/colour/SchemeGenerator.tsx`. Grep for imports and repoint/remove them:

Run: `cd web && grep -rl "SchemeGenerator" src` — the only importer is `ColourPanel.tsx`, which is retired in Task 7; if it still imports `SchemeGenerator` at this point, swap that import to `GeneratePanel` to keep the app compiling. Run `npx tsc -b --noEmit` to confirm no dangling references.

- [ ] **Step 6: Commit**

```bash
git add web/src/components/colour/GeneratePanel.tsx web/src/components/colour/GeneratePanel.test.tsx web/src/components/colour/ColourPanel.tsx web/src/i18n/en.json web/src/i18n/es.json
git rm web/src/components/colour/SchemeGenerator.tsx
git commit -m "feat(colour): GeneratePanel — collapsible whole-mini generation, undo-aware"
```

---

## Task 5: `RegionHeader` — switcher + surface/tone/finish

The region-scope header: a compact region switcher plus the region-local surface, tone, and finish (material) controls moved out of the generate table and the retired `TechniquePanel`. Also a toggle to reveal `ManagePanel` (region CRUD), consolidating region management next to the header.

**Files:**
- Create: `web/src/components/RegionHeader.tsx`
- Create: `web/src/components/RegionHeader.test.tsx`

**Interfaces:**
- Consumes: store `activeBookOf`, `setSelected`, `setSurface`, `setTone`, `setMaterial`; `SURFACES` from `api/types`; `ManagePanel` (existing).
- Produces: `RegionHeader()` — renders `EDITING:` + a region `<select>` (accessible name `region`) bound to `book.selected`; surface `<select>`, tone `<input>`, finish `<select>` for the selected region; a `Manage regions` toggle revealing `ManagePanel`.

- [ ] **Step 1: Write the failing test**

```tsx
// web/src/components/RegionHeader.test.tsx
import { describe, it, expect, beforeEach, vi } from "vitest";
import { render, screen, fireEvent } from "@testing-library/react";
import { MantineProvider } from "@mantine/core";
import { RegionHeader } from "./RegionHeader";
import { useProjectStore } from "../store/projectStore";
import type { PhotoResponse } from "../api/types";

vi.mock("react-i18next", () => ({ useTranslation: () => ({ t: (k: string) => k }) }));
vi.mock("./RegionCanvas", () => ({ RegionCanvas: () => null }));

const photo = (): PhotoResponse => ({
  photo_id: "p1", width: 10, height: 10, quality_checks: [],
  default_whole: { palette: [{ name: "a", hex: "#111" }, { name: "b", hex: "#aaa" }, { name: "c", hex: "#eee" }],
                   coverage: [0.5, 0.3, 0.2], material: "matte" },
});
const reset = () => useProjectStore.setState(useProjectStore.getInitialState(), true);

describe("RegionHeader", () => {
  beforeEach(() => {
    reset();
    useProjectStore.getState().initFromPhoto(photo());
    useProjectStore.getState().addRegion([[[1, 1], [2, 2], [3, 1]]], "Cloak");
    useProjectStore.getState().setSelected(0);
  });

  it("switching the region select calls setSelected", () => {
    render(<MantineProvider><RegionHeader /></MantineProvider>);
    const sel = screen.getByLabelText("region") as HTMLSelectElement;
    fireEvent.change(sel, { target: { value: "1" } });
    expect(useProjectStore.getState().angles[0].book.selected).toBe(1);
  });

  it("finish select updates material on the selected region", () => {
    render(<MantineProvider><RegionHeader /></MantineProvider>);
    const finish = screen.getByLabelText("technique.material") as HTMLSelectElement;
    fireEvent.change(finish, { target: { value: "metallic" } });
    expect(useProjectStore.getState().angles[0].book.whole.material).toBe("metallic");
  });
});
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd web && npx vitest run src/components/RegionHeader.test.tsx`
Expected: FAIL — cannot find `./RegionHeader`.

- [ ] **Step 3: Create `RegionHeader`**

```tsx
// web/src/components/RegionHeader.tsx
import { useState } from "react";
import { useTranslation } from "react-i18next";
import { Button, Collapse, Group, NativeSelect, Paper, Stack, Text, TextInput } from "@mantine/core";
import { useProjectStore, activeBookOf } from "../store/projectStore";
import { SURFACES } from "../api/types";
import { ManagePanel } from "./ManagePanel";

export function RegionHeader() {
  const { t } = useTranslation();
  const book = useProjectStore((s) => activeBookOf(s));
  const setSelected = useProjectStore((s) => s.setSelected);
  const setSurface = useProjectStore((s) => s.setSurface);
  const setTone = useProjectStore((s) => s.setTone);
  const setMaterial = useProjectStore((s) => s.setMaterial);
  const [manageOpen, setManageOpen] = useState(false);

  if (!book) return null;
  const g = book.selected;
  const region = g === 0 ? book.whole : book.drawn[g - 1];
  const names = ["Whole mini", ...book.drawn.map((r) => r.name)];

  return (
    <Paper withBorder p="xs">
      <Stack gap="xs">
        <Group gap="xs" align="flex-end">
          <Text size="sm" fw={600}>{t("region.editing")}</Text>
          <NativeSelect aria-label="region" size="xs" value={g}
            onChange={(e) => setSelected(Number(e.target.value))}>
            {names.map((name, i) => <option key={i} value={i}>{name}</option>)}
          </NativeSelect>
          <Button size="xs" variant="subtle" onClick={() => setManageOpen((o) => !o)}>
            {t("region.manage")}
          </Button>
        </Group>
        <Group gap="xs" align="flex-end" wrap="wrap">
          <NativeSelect label={t("colour.surface")} size="xs" value={region.surface ?? "skin"}
            onChange={(e) => setSurface(g, e.target.value)}
            data={SURFACES.map((s) => ({ value: s, label: t(`surfaces.${s}`) }))} />
          <TextInput label={t("colour.tone")} size="xs" value={region.tone ?? ""}
            onChange={(e) => setTone(g, e.target.value)} style={{ maxWidth: 120 }} />
          <NativeSelect label={t("technique.material")} size="xs" value={region.material}
            onChange={(e) => setMaterial(g, e.target.value)}
            data={[{ value: "matte", label: t("technique.matte") },
                   { value: "metallic", label: t("technique.metallic") }]} />
        </Group>
        <Collapse in={manageOpen}><ManagePanel /></Collapse>
      </Stack>
    </Paper>
  );
}
```

Add i18n keys `region.editing` ("Editing:"), `region.manage` ("Manage regions"), and `colour.surface` ("Surface") to `en.json`/`es.json` if absent (`colour.tone` already exists).

- [ ] **Step 4: Run test to verify it passes**

Run: `cd web && npx vitest run src/components/RegionHeader.test.tsx`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add web/src/components/RegionHeader.tsx web/src/components/RegionHeader.test.tsx web/src/i18n/en.json web/src/i18n/es.json
git commit -m "feat(studio): RegionHeader — region switcher + surface/tone/finish + manage toggle"
```

---

## Task 6: `BandCard` + `BandEditor` rebuild + `RecipeFooter`

The centrepiece. Each band becomes a card (role name, live colour control + match hint, in-card coverage or auto chip, per-card `✕`). `BandEditor` renders the cards and owns the coverage handler. A single `RecipeFooter` holds `+ Add band`, `Ramp`, `Load…`, `Save`, `Reset coverage`, `↺ Undo`. `CoverageEditor` is retired.

**Files:**
- Create: `web/src/components/colour/BandCard.tsx`
- Create: `web/src/components/colour/BandCard.test.tsx`
- Create: `web/src/components/colour/RecipeFooter.tsx`
- Modify: `web/src/components/colour/BandEditor.tsx` (render cards + footer, own coverage handler)
- Delete: `web/src/components/colour/CoverageEditor.tsx` + `.test.tsx`

**Interfaces:**
- Consumes: store `setPaletteSlot/setHexSlot/setBandCount/setCoverage/snapshotUndo`; `matchPaint/generateRamp` (`api/client`); `roleNames` (Task 2).
- Produces:
  - `BandCard({ g, i, paint, finish, n, palette, role, coverageValue, isAuto, onCoverage })` — one band card. Interior bands render a coverage `slider`; the `isAuto` (top) band renders a static `… (auto)` chip and no slider. `✕` disabled when `n <= 3`.
  - `RecipeFooter({ g, n })` — `+ Add band` (disabled `n >= 7`), `Ramp`, `Load…`, `Save`, `Reset coverage`, `↺ Undo` (disabled when `undoSnapshot` null).
  - `onCoverage(i: number, val: number): void` — provided by `BandEditor`, applies the sum-to-1 / last-auto math (same as the old `CoverageEditor.handleSlider`).

- [ ] **Step 1: Write the failing test**

```tsx
// web/src/components/colour/BandCard.test.tsx
import { describe, it, expect, vi } from "vitest";
import { render, screen } from "@testing-library/react";
import { MantineProvider } from "@mantine/core";
import { BandCard } from "./BandCard";
import type { PaintColor } from "../../api/types";

vi.mock("react-i18next", () => ({ useTranslation: () => ({ t: (k: string) => k }) }));
vi.mock("../../store/catalogStore", () => ({ useCatalogStore: (sel: any) => sel({ paints: [] }) }));
vi.mock("../../store/projectStore", () => ({
  useProjectStore: (sel: any) => sel({
    setPaletteSlot: () => {}, setHexSlot: () => {}, setBandCount: () => {},
  }),
}));

const paint = (): PaintColor => ({ name: "band", hex: "#808080", code: "AK1" });

function renderCard(over: Partial<React.ComponentProps<typeof BandCard>> = {}) {
  const props = {
    g: 0, i: 1, paint: paint(), finish: "matte", n: 4,
    palette: [paint(), paint(), paint(), paint()], role: "Base",
    coverageValue: 0.27, isAuto: false, onCoverage: () => {},
    ...over,
  } as React.ComponentProps<typeof BandCard>;
  return render(<MantineProvider><BandCard {...props} /></MantineProvider>);
}

describe("BandCard", () => {
  it("shows the role name", () => {
    renderCard({ role: "Midtone" });
    expect(screen.getByText("Midtone")).toBeTruthy();
  });

  it("interior band renders a coverage slider", () => {
    renderCard({ isAuto: false });
    expect(screen.getAllByRole("slider").length).toBe(1);
  });

  it("auto (top) band renders a chip, not a slider", () => {
    renderCard({ isAuto: true, role: "Highlight", coverageValue: 0.13 });
    expect(screen.queryByRole("slider")).toBeNull();
    expect(screen.getByText(/auto/i)).toBeTruthy();
  });

  it("remove is disabled at the 3-band floor", () => {
    renderCard({ n: 3 });
    expect((screen.getByLabelText("colour.delete_band") as HTMLButtonElement).disabled).toBe(true);
  });
});
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd web && npx vitest run src/components/colour/BandCard.test.tsx`
Expected: FAIL — cannot find `./BandCard`.

- [ ] **Step 3: Create `BandCard`**

Adapt `BandSlot`: keep the swatch, catalog-select/custom-hex control, and match-hint; add a role-name header, an in-card coverage slider (or auto chip), and a per-card `✕`. Remove the per-row `＋` (moves to `RecipeFooter`).

```tsx
// web/src/components/colour/BandCard.tsx
import { useState, useEffect, useRef } from "react";
import { useTranslation } from "react-i18next";
import { ActionIcon, Box, ColorInput, ColorSwatch, Group, NativeSelect, Slider, Text } from "@mantine/core";
import { useProjectStore } from "../../store/projectStore";
import { useCatalogStore } from "../../store/catalogStore";
import { matchPaint, generateRamp } from "../../api/client";
import type { PaintColor, MatchResult } from "../../api/types";

interface Props {
  g: number; i: number; paint: PaintColor; finish: string; n: number; palette: PaintColor[];
  role: string; coverageValue: number; isAuto: boolean;
  onCoverage: (i: number, val: number) => void;
}

function matchPhrase(r: MatchResult): string {
  if (r.tier === "exact") return `✓ ${r.name ?? ""}`;
  if (r.tier === "close") return `≈ ${r.name ?? ""}`;
  if (r.tier === "mix") return r.phrase;
  return `Buy: ${r.name ?? ""}`;
}

export function BandCard({ g, i, paint, finish, n, palette, role, coverageValue, isAuto, onCoverage }: Props) {
  const { t } = useTranslation();
  const catalogPaints = useCatalogStore((s) => s.paints);
  const setPaletteSlot = useProjectStore((s) => s.setPaletteSlot);
  const setHexSlot = useProjectStore((s) => s.setHexSlot);
  const setBandCount = useProjectStore((s) => s.setBandCount);
  const isCustom = !paint.code;
  const [matchResult, setMatchResult] = useState<MatchResult | null>(null);
  const debounceRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const pct = Math.round(coverageValue * 100);

  useEffect(() => {
    if (!isCustom) { setMatchResult(null); return; }
    if (debounceRef.current) clearTimeout(debounceRef.current);
    debounceRef.current = setTimeout(async () => {
      try { setMatchResult(await matchPaint({ hex: paint.hex, finish, owned_codes: [] })); } catch { /* ignore */ }
    }, 400);
    return () => { if (debounceRef.current) clearTimeout(debounceRef.current); };
  }, [paint.hex, isCustom, finish]);

  const handleCatalogChange = (code: string) => {
    if (code === "__custom__") setHexSlot(g, i, paint.hex);
    else { const found = catalogPaints.find((p) => p.code === code); if (found) setPaletteSlot(g, i, found); }
  };

  const handleBlend = async () => {
    const left = palette[i - 1]; const right = palette[i + 1];
    if (!left || !right) return;
    try {
      const res = await generateRamp({ n: 1, variant: "ramp", blend_hexes: [left.hex, right.hex] });
      if (res.hexes[0]) setHexSlot(g, i, res.hexes[0]);
    } catch { /* ignore */ }
  };

  return (
    <Box p="xs" style={{ border: "1px solid var(--mantine-color-dark-4)", borderRadius: 6 }}>
      <Group justify="space-between" mb={4}>
        <Text size="xs" fw={600}>{role}</Text>
        {isAuto
          ? <Text size="xs" c="dimmed">{pct}% ({t("colour.auto")})</Text>
          : <ActionIcon size="sm" variant="subtle" color="red" disabled={n <= 3}
              onClick={() => { if (n > 3) setBandCount(n - 1); }} aria-label={t("colour.delete_band")}>✕</ActionIcon>}
      </Group>
      <Group gap={4} align="center" wrap="nowrap">
        <ColorSwatch color={paint.hex} size={22} style={{ flexShrink: 0 }} />
        {isCustom ? (
          <ColorInput value={paint.hex} onChange={(hex) => setHexSlot(g, i, hex)}
            format="hex" size="xs" style={{ flex: 1 }} withEyeDropper={false} />
        ) : (
          <NativeSelect value={paint.code} onChange={(e) => handleCatalogChange(e.target.value)}
            size="xs" style={{ flex: 1 }}>
            {catalogPaints.map((p) => <option key={p.code} value={p.code}>{p.code} — {p.name}</option>)}
            <option value="__custom__">{t("colour.custom")}</option>
          </NativeSelect>
        )}
        {i > 0 && i < n - 1 && (
          <ActionIcon size="sm" variant="subtle" onClick={handleBlend} title={t("colour.blend")}>↕</ActionIcon>
        )}
      </Group>
      {isCustom && matchResult && <Text size="xs" c="dimmed" ml={28}>{matchPhrase(matchResult)}</Text>}
      {!isAuto && (
        <Group gap="xs" align="center" wrap="nowrap" mt={6}>
          <Text size="xs" miw={70}>{t("colour.coverage")}</Text>
          <Slider value={pct} onChange={(v) => onCoverage(i, v)} min={0} max={100} step={1} size="sm" style={{ flex: 1 }} />
          <Text size="xs" miw={32} ta="right">{pct}%</Text>
        </Group>
      )}
    </Box>
  );
}
```

Add i18n keys `colour.auto` ("auto") and `colour.coverage` ("Coverage") to `en.json`/`es.json` if absent.

- [ ] **Step 4: Run test to verify it passes**

Run: `cd web && npx vitest run src/components/colour/BandCard.test.tsx`
Expected: PASS.

- [ ] **Step 5: Create `RecipeFooter`**

```tsx
// web/src/components/colour/RecipeFooter.tsx
import { useTranslation } from "react-i18next";
import { Button, Group } from "@mantine/core";
import { useProjectStore } from "../../store/projectStore";
import { defaultCoverage } from "../../lib/roles";
import { RampEditor } from "./RampEditor";
import { RecipeLoader } from "./RecipeLoader";
import { RecipeSaver } from "./RecipeSaver";

interface Props { g: number; n: number; onRecipeChanged: () => void; }

export function RecipeFooter({ g, n, onRecipeChanged }: Props) {
  const { t } = useTranslation();
  const setBandCount = useProjectStore((s) => s.setBandCount);
  const setHexSlot = useProjectStore((s) => s.setHexSlot);
  const setCoverage = useProjectStore((s) => s.setCoverage);
  const snapshotUndo = useProjectStore((s) => s.snapshotUndo);
  const undo = useProjectStore((s) => s.undo);
  const canUndo = useProjectStore((s) => s.undoSnapshot !== null);
  const palette = useProjectStore((s) => {
    const b = s.angles[s.activeAngle]?.book; if (!b) return [];
    return g === 0 ? b.whole.palette : b.drawn[g - 1]?.palette ?? [];
  });

  const addBand = () => { if (n < 7) { setBandCount(n + 1); setHexSlot(g, n, palette[n - 1]?.hex ?? "#808080"); } };
  const resetCoverage = () => { snapshotUndo(); setCoverage(defaultCoverage(n)); };

  return (
    <Group gap="xs" wrap="wrap">
      <Button size="xs" variant="light" onClick={addBand} disabled={n >= 7}>{t("colour.add_band")}</Button>
      <RampEditor />
      <RecipeLoader onRecipeLoaded={onRecipeChanged} />
      <RecipeSaver onSaved={onRecipeChanged} />
      <Button size="xs" variant="subtle" onClick={resetCoverage}>{t("colour.reset_coverage")}</Button>
      <Button size="xs" variant="subtle" onClick={undo} disabled={!canUndo}
        aria-label="undo">↺ {t("colour.undo")}</Button>
    </Group>
  );
}
```

Add i18n key `colour.undo` ("Undo") to `en.json`/`es.json`.

- [ ] **Step 6: Rebuild `BandEditor`**

```tsx
// web/src/components/colour/BandEditor.tsx
import { useState } from "react";
import { useTranslation } from "react-i18next";
import { Stack, Text } from "@mantine/core";
import { useProjectStore, activeBookOf } from "../../store/projectStore";
import { roleNames } from "../../lib/roles";
import { BandCard } from "./BandCard";
import { RecipeFooter } from "./RecipeFooter";

export function BandEditor() {
  const { t } = useTranslation();
  const book = useProjectStore((s) => activeBookOf(s));
  const setCoverage = useProjectStore((s) => s.setCoverage);
  const [recipeKey, setRecipeKey] = useState(0);

  if (!book) return null;
  const g = book.selected;
  const region = g === 0 ? book.whole : book.drawn[g - 1];
  if (!region) return null;
  const { palette, coverage, material } = region;
  const n = palette.length;
  const roles = roleNames(n);

  // Same math as the retired CoverageEditor.handleSlider: adjust band i, keep last band auto.
  const handleCoverage = (i: number, val: number) => {
    const valFraction = val / 100;
    const others = coverage.reduce((sum, v, j) => (j !== i && j !== n - 1 ? sum + v : sum), 0);
    const clamped = Math.min(valFraction, Math.max(0, 1 - others - 0.03));
    const newCov = coverage.slice();
    newCov[i] = clamped;
    const remainder = 1 - newCov.slice(0, n - 1).reduce((a, b) => a + b, 0);
    newCov[n - 1] = Math.max(0, remainder);
    setCoverage(newCov);
  };

  return (
    <Stack gap="xs" key={recipeKey}>
      <Text size="sm" fw={500}>{t("colour.band_editor")}</Text>
      {palette.map((paint, i) => (
        <BandCard key={i} g={g} i={i} paint={paint} finish={material} n={n} palette={palette}
          role={roles[i]} coverageValue={coverage[i] ?? 0} isAuto={i === n - 1} onCoverage={handleCoverage} />
      ))}
      <RecipeFooter g={g} n={n} onRecipeChanged={() => setRecipeKey((k) => k + 1)} />
    </Stack>
  );
}
```

- [ ] **Step 7: Delete `CoverageEditor`**

```bash
git rm web/src/components/colour/CoverageEditor.tsx web/src/components/colour/CoverageEditor.test.tsx
```

Grep for stragglers: `cd web && grep -rl "CoverageEditor" src` — expect none (BandEditor no longer imports it). Fix any remaining reference.

- [ ] **Step 8: Run tests + typecheck**

Run: `cd web && npx vitest run src/components/colour/BandCard.test.tsx && npx tsc -b --noEmit`
Expected: PASS, no type errors.

- [ ] **Step 9: Commit**

```bash
git add web/src/components/colour/BandCard.tsx web/src/components/colour/BandCard.test.tsx web/src/components/colour/RecipeFooter.tsx web/src/components/colour/BandEditor.tsx web/src/i18n/en.json web/src/i18n/es.json
git rm web/src/components/colour/CoverageEditor.tsx web/src/components/colour/CoverageEditor.test.tsx
git commit -m "feat(colour): band cards with in-card coverage + recipe footer; retire CoverageEditor"
```

---

## Task 7: `RecipeLoader` — Load → preview → Apply

Loading a recipe must not silently overwrite the current region's palette. Show the incoming swatches and require an explicit Apply; snapshot undo before applying.

**Files:**
- Modify: `web/src/components/colour/RecipeLoader.tsx`
- Create: `web/src/components/colour/RecipeLoader.test.tsx`

**Interfaces:**
- Consumes: `listRecipes` (`api/client`), store `setPaletteAt`/`snapshotUndo`, catalog paints.
- Produces: `RecipeLoader({ onRecipeLoaded })` — select a recipe → **Preview** (renders incoming swatches; no state mutation) → **Apply** (snapshot + `setPaletteAt(book.selected, …)`) / **Cancel** (no-op).

- [ ] **Step 1: Write the failing test**

```tsx
// web/src/components/colour/RecipeLoader.test.tsx
import { describe, it, expect, beforeEach, vi } from "vitest";
import { render, screen, fireEvent, waitFor } from "@testing-library/react";
import { MantineProvider } from "@mantine/core";
import { RecipeLoader } from "./RecipeLoader";
import { useProjectStore } from "../../store/projectStore";
import type { PhotoResponse } from "../../api/types";

vi.mock("react-i18next", () => ({ useTranslation: () => ({ t: (k: string) => k }) }));
vi.mock("../../store/catalogStore", () => ({ useCatalogStore: (sel: any) => sel({ paints: [] }) }));
vi.mock("../../api/client", () => ({
  listRecipes: () => Promise.resolve({ recipes: [
    { name: "R1", steps: [{ hex: "#010101", paint_ref: null }, { hex: "#020202", paint_ref: null }, { hex: "#030303", paint_ref: null }] },
  ] }),
}));

const photo = (): PhotoResponse => ({
  photo_id: "p1", width: 10, height: 10, quality_checks: [],
  default_whole: { palette: [{ name: "a", hex: "#111" }, { name: "b", hex: "#aaa" }, { name: "c", hex: "#eee" }],
                   coverage: [0.5, 0.3, 0.2], material: "matte" },
});
const reset = () => useProjectStore.setState(useProjectStore.getInitialState(), true);
const wholeHex0 = () => useProjectStore.getState().angles[0].book.whole.palette[0].hex;

describe("RecipeLoader Load→preview→Apply", () => {
  beforeEach(() => { reset(); useProjectStore.getState().initFromPhoto(photo()); });

  it("Preview does not mutate; Apply replaces the region palette", async () => {
    render(<MantineProvider><RecipeLoader onRecipeLoaded={() => {}} /></MantineProvider>);
    await waitFor(() => screen.getByText("colour.preview_recipe"));
    fireEvent.click(screen.getByText("colour.preview_recipe"));
    expect(wholeHex0()).toBe("#111");                       // preview: no mutation
    fireEvent.click(screen.getByText("colour.apply_recipe"));
    await waitFor(() => expect(wholeHex0()).toBe("#010101")); // apply: replaced
    expect(useProjectStore.getState().undoSnapshot).not.toBeNull();
  });

  it("Cancel after preview leaves the palette untouched", async () => {
    render(<MantineProvider><RecipeLoader onRecipeLoaded={() => {}} /></MantineProvider>);
    await waitFor(() => screen.getByText("colour.preview_recipe"));
    fireEvent.click(screen.getByText("colour.preview_recipe"));
    fireEvent.click(screen.getByText("colour.cancel"));
    expect(wholeHex0()).toBe("#111");
  });
});
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd web && npx vitest run src/components/colour/RecipeLoader.test.tsx`
Expected: FAIL — no `colour.preview_recipe`/`apply_recipe` controls (current component applies immediately).

- [ ] **Step 3: Rewrite `RecipeLoader`**

```tsx
// web/src/components/colour/RecipeLoader.tsx
import { useState, useEffect } from "react";
import { useTranslation } from "react-i18next";
import { Button, ColorSwatch, Group, NativeSelect, Stack } from "@mantine/core";
import { useProjectStore, activeBookOf } from "../../store/projectStore";
import { useCatalogStore } from "../../store/catalogStore";
import { listRecipes } from "../../api/client";
import type { Recipe, PaintColor } from "../../api/types";

function toPalette(recipe: Recipe, catalog: PaintColor[]): PaintColor[] {
  return recipe.steps.map((step) => {
    const found = step.paint_ref ? catalog.find((p) => p.name === step.paint_ref) : undefined;
    return found ?? { name: "custom", hex: step.hex, code: "", finish: "matte" };
  });
}

interface Props { onRecipeLoaded(): void; }

export function RecipeLoader({ onRecipeLoaded }: Props) {
  const { t } = useTranslation();
  const book = useProjectStore((s) => activeBookOf(s));
  const catalogPaints = useCatalogStore((s) => s.paints);
  const setPaletteAt = useProjectStore((s) => s.setPaletteAt);
  const snapshotUndo = useProjectStore((s) => s.snapshotUndo);
  const [recipes, setRecipes] = useState<Recipe[]>([]);
  const [selected, setSelected] = useState<string>("");
  const [preview, setPreview] = useState<PaintColor[] | null>(null);

  useEffect(() => {
    listRecipes().then((res) => { setRecipes(res.recipes); if (res.recipes.length > 0) setSelected(res.recipes[0].name); });
  }, []);

  if (!book) return null;

  const doPreview = () => {
    const recipe = recipes.find((r) => r.name === selected);
    if (recipe) setPreview(toPalette(recipe, catalogPaints));
  };
  const doApply = () => {
    if (!preview) return;
    snapshotUndo();
    setPaletteAt(book.selected, preview);
    setPreview(null);
    onRecipeLoaded();
  };

  return (
    <Stack gap="xs">
      <Group gap="xs">
        <NativeSelect size="xs" value={selected} onChange={(e) => setSelected(e.target.value)} style={{ flex: 1 }}>
          {recipes.length === 0 && <option value="">{t("colour.select_recipe")}</option>}
          {recipes.map((r) => <option key={r.name} value={r.name}>{r.name}</option>)}
        </NativeSelect>
        <Button size="xs" variant="default" onClick={doPreview} disabled={!selected}>{t("colour.preview_recipe")}</Button>
      </Group>
      {preview && (
        <Group gap="xs" align="center">
          <Group gap={2}>{preview.map((p, i) => <ColorSwatch key={i} color={p.hex} size={18} />)}</Group>
          <Button size="xs" onClick={doApply}>{t("colour.apply_recipe")}</Button>
          <Button size="xs" variant="subtle" onClick={() => setPreview(null)}>{t("colour.cancel")}</Button>
        </Group>
      )}
    </Stack>
  );
}
```

Add i18n keys `colour.preview_recipe` ("Load…"), `colour.apply_recipe` ("Apply"), `colour.cancel` ("Cancel") to `en.json`/`es.json` (`colour.select_recipe` already exists).

- [ ] **Step 4: Run test to verify it passes**

Run: `cd web && npx vitest run src/components/colour/RecipeLoader.test.tsx`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add web/src/components/colour/RecipeLoader.tsx web/src/components/colour/RecipeLoader.test.tsx web/src/i18n/en.json web/src/i18n/es.json
git commit -m "feat(colour): RecipeLoader Load→preview→Apply, undo-aware"
```

---

## Task 8: Assemble `StudioPanel`; retire `RightPanel` / `ColourPanel` / `TechniquePanel`

Swap the Studio editor column from the old `RegionSelector`+`RightPanel` to the new stack: `GeneratePanel` → `RegionHeader` → `BandEditor`. Move `SchemeManager`/`RecipeManager` (session scheme snapshots / recipe import-export) below the bands. Retire the dead components.

**Files:**
- Modify: `web/src/components/StudioPanel.tsx`
- Modify: `web/src/components/ManagePanel.tsx` (absorb the `visible`/blank toggle)
- Create: `web/src/components/ManagePanel.test.tsx` (visible toggle)
- Delete: `web/src/components/RegionSelector.tsx` + `.test.tsx`, `web/src/components/RightPanel.tsx` + `.test.tsx`, `web/src/components/colour/ColourPanel.tsx`, `web/src/components/TechniquePanel.tsx`

**Interfaces:**
- Consumes: `GeneratePanel`, `RegionHeader`, `BandEditor`, `SchemeManager`, `RecipeManager` (existing), `PreviewImage`.
- Produces: `StudioPanel()` — sticky preview + editor stack `[GeneratePanel, RegionHeader, BandEditor, SchemeManager, RecipeManager]`.

- [ ] **Step 1: Write the failing test (ManagePanel visible toggle)**

```tsx
// web/src/components/ManagePanel.test.tsx
import { describe, it, expect, beforeEach, vi } from "vitest";
import { render, screen, fireEvent } from "@testing-library/react";
import { MantineProvider } from "@mantine/core";
import { ManagePanel } from "./ManagePanel";
import { useProjectStore } from "../store/projectStore";
import type { PhotoResponse } from "../api/types";

vi.mock("react-i18next", () => ({ useTranslation: () => ({ t: (k: string) => k }) }));
vi.mock("./RegionCanvas", () => ({ RegionCanvas: () => null }));

const photo = (): PhotoResponse => ({
  photo_id: "p1", width: 10, height: 10, quality_checks: [],
  default_whole: { palette: [{ name: "a", hex: "#111" }, { name: "b", hex: "#aaa" }, { name: "c", hex: "#eee" }],
                   coverage: [0.5, 0.3, 0.2], material: "matte" },
});
const reset = () => useProjectStore.setState(useProjectStore.getInitialState(), true);

describe("ManagePanel visible toggle", () => {
  beforeEach(() => {
    reset();
    useProjectStore.getState().initFromPhoto(photo());
    useProjectStore.getState().addRegion([[[1, 1], [2, 2], [3, 1]]], "Cloak"); // selects region 1
  });

  it("toggles blank on the selected drawn region", () => {
    render(<MantineProvider><ManagePanel /></MantineProvider>);
    const before = useProjectStore.getState().angles[0].book.drawn[0].blank;
    fireEvent.click(screen.getByLabelText("visible"));
    expect(useProjectStore.getState().angles[0].book.drawn[0].blank).toBe(!before);
  });
});
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd web && npx vitest run src/components/ManagePanel.test.tsx`
Expected: FAIL — no `visible` control in `ManagePanel` yet.

- [ ] **Step 3: Add the visible toggle to `ManagePanel`**

In `ManagePanel.tsx`, add `toggleBlank` from the store and, in the `!drawing && sel >= 1` block, add a visible checkbox next to the rename/delete row:

```tsx
// add to the store hooks:
const toggleBlank = useProjectStore((s) => s.toggleBlank);
// import Checkbox from "@mantine/core"
```

Replace the `{!drawing && sel >= 1 && ( … )}` group with:

```tsx
{!drawing && sel >= 1 && (
  <Group gap="xs" align="center">
    <TextInput size="xs" value={book.drawn[sel - 1].name}
      onChange={(e) => renameRegion(sel, e.target.value)} style={{ flex: 1 }} />
    <Checkbox size="xs" aria-label="visible" label="visible"
      checked={!book.drawn[sel - 1].blank} onChange={() => toggleBlank(sel)} />
    <ActionIcon size="sm" variant="subtle" color="red"
      onClick={() => removeRegion(sel)} aria-label="Delete region">✕</ActionIcon>
  </Group>
)}
```

- [ ] **Step 4: Run the ManagePanel test**

Run: `cd web && npx vitest run src/components/ManagePanel.test.tsx`
Expected: PASS.

- [ ] **Step 5: Rebuild `StudioPanel` with the new stack**

```tsx
// web/src/components/StudioPanel.tsx
import { Box, Group, Stack } from "@mantine/core";
import { PreviewImage } from "./PreviewImage";
import { RegionHeader } from "./RegionHeader";
import { GeneratePanel } from "./colour/GeneratePanel";
import { BandEditor } from "./colour/BandEditor";
import { SchemeManager } from "./colour/SchemeManager";
import { RecipeManager } from "./colour/RecipeManager";

export function StudioPanel() {
  return (
    <Group align="flex-start" gap="xl" wrap="nowrap">
      <Box data-testid="studio-preview"
        style={{ position: "sticky", top: 16, alignSelf: "flex-start", maxWidth: 360, flexShrink: 0 }}>
        <PreviewImage />
      </Box>
      <Stack data-testid="studio-editor" style={{ flex: 1 }} gap="md">
        <GeneratePanel />
        <RegionHeader />
        <BandEditor />
        <SchemeManager />
        <RecipeManager />
      </Stack>
    </Group>
  );
}
```

The `StudioPanel.test.tsx` from Task 1 still passes (both test ids remain; `RegionCanvas` is reached through `RegionHeader`→`ManagePanel`, so add `vi.mock("./RegionCanvas", () => ({ RegionCanvas: () => null }))` to `StudioPanel.test.tsx` to avoid the konva canvas in jsdom).

- [ ] **Step 6: Retire the dead components**

```bash
cd web && grep -rl "RightPanel\|ColourPanel\|TechniquePanel\|RegionSelector" src
```

Remove each import you find (there should be none left in live code after Step 5), then delete:

```bash
git rm web/src/components/RightPanel.tsx web/src/components/RightPanel.test.tsx \
       web/src/components/RegionSelector.tsx web/src/components/RegionSelector.test.tsx \
       web/src/components/colour/ColourPanel.tsx \
       web/src/components/TechniquePanel.tsx
```

- [ ] **Step 7: Full suite + typecheck**

Run: `cd web && npm test && npx tsc -b --noEmit`
Expected: PASS, no type errors, no references to deleted files.

- [ ] **Step 8: Commit**

```bash
git add web/src/components/StudioPanel.tsx web/src/components/StudioPanel.test.tsx web/src/components/ManagePanel.tsx web/src/components/ManagePanel.test.tsx
git rm web/src/components/RightPanel.tsx web/src/components/RightPanel.test.tsx web/src/components/RegionSelector.tsx web/src/components/RegionSelector.test.tsx web/src/components/colour/ColourPanel.tsx web/src/components/TechniquePanel.tsx
git commit -m "feat(studio): assemble StudioPanel stack; retire RightPanel/ColourPanel/Technique/RegionSelector"
```

---

## Task 9: Angles — one management home

Top bar switches + quick-adds only; the gallery becomes the CRUD home (select, rename, delete).

**Files:**
- Modify: `web/src/components/AngleBar.tsx` (remove rename field + delete control)
- Modify: `web/src/components/AngleGallery.tsx` (add select/rename/delete)
- Modify: `web/src/components/AngleBar.test.tsx`, `web/src/components/AngleGallery.test.tsx`

**Interfaces:**
- Consumes: store `switchAngle`/`addAngle`/`renameAngle`/`removeAngle`.
- Produces: `AngleBar` renders angle chips + `+ angle` only (no rename input, no delete). `AngleGallery` cards are clickable (select), each with a rename input and a delete control (delete disabled when one angle remains).

- [ ] **Step 1: Write the failing tests**

```tsx
// append to web/src/components/AngleBar.test.tsx
it("does not expose rename or delete in the bar", () => {
  // (set up two angles as the existing tests do, then:)
  render(<MantineProvider><AngleBar /></MantineProvider>);
  expect(screen.queryByLabelText("Rename angle")).toBeNull();
  expect(screen.queryByLabelText("Remove angle")).toBeNull();
});
```

```tsx
// append to web/src/components/AngleGallery.test.tsx
it("clicking a gallery card selects that angle", () => {
  // (set up two angles; active = 0, then:)
  render(<MantineProvider><AngleGallery /></MantineProvider>);
  fireEvent.click(screen.getByTestId("angle-card-1"));
  expect(useProjectStore.getState().activeAngle).toBe(1);
});

it("gallery exposes rename and delete", () => {
  render(<MantineProvider><AngleGallery /></MantineProvider>);
  expect(screen.getAllByLabelText("Rename angle").length).toBeGreaterThan(0);
  expect(screen.getAllByLabelText("Remove angle").length).toBeGreaterThan(0);
});
```

Match the existing test files' setup helpers (photo + `addAngle`) — read the current `AngleBar.test.tsx`/`AngleGallery.test.tsx` and reuse their `beforeEach` scaffolding rather than duplicating a new one.

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd web && npx vitest run src/components/AngleBar.test.tsx src/components/AngleGallery.test.tsx`
Expected: FAIL — bar still has rename/delete; gallery has no select/rename/delete.

- [ ] **Step 3: Slim down `AngleBar`**

In `AngleBar.tsx` remove the second `<Group>` (the rename `TextInput` + remove `ActionIcon`) and the now-unused `renameAngle`, `removeAngle`, and `TextInput`/`ActionIcon` imports. Keep the chips + `+ angle` + hidden file input.

- [ ] **Step 4: Add select/rename/delete to `AngleGallery`**

Add store actions and per-card controls. Make the card clickable to select, add a rename `TextInput` and a delete `ActionIcon` in each card's footer:

```tsx
// add hooks:
const switchAngle = useProjectStore((s) => s.switchAngle);
const renameAngle = useProjectStore((s) => s.renameAngle);
const removeAngle = useProjectStore((s) => s.removeAngle);
// import { ActionIcon, TextInput } from "@mantine/core";
```

On the `<Card>` add `data-testid={`angle-card-${idx}`}` and `onClick={() => switchAngle(idx)}` (stop propagation on the inner input/delete so they don't also switch). Replace the label `<Text>` footer with:

```tsx
<Group gap="xs" mt="xs" onClick={(e) => e.stopPropagation()}>
  <TextInput size="xs" aria-label="Rename angle" value={angle.label}
    onChange={(e) => renameAngle(idx, e.target.value)} style={{ flex: 1 }} />
  {isActive && <Badge size="xs" variant="light">{t("gallery.active_badge")}</Badge>}
  <ActionIcon size="sm" variant="subtle" color="red" aria-label="Remove angle"
    disabled={angles.length === 1} onClick={() => removeAngle(idx)}>✕</ActionIcon>
</Group>
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `cd web && npx vitest run src/components/AngleBar.test.tsx src/components/AngleGallery.test.tsx`
Expected: PASS.

- [ ] **Step 6: Commit**

```bash
git add web/src/components/AngleBar.tsx web/src/components/AngleBar.test.tsx web/src/components/AngleGallery.tsx web/src/components/AngleGallery.test.tsx
git commit -m "feat(angles): bar switches/quick-adds; gallery is the CRUD home"
```

---

## Task 10: Continuous lasso

Make the region-selection stroke render live during the drag instead of appearing only on release.

**Files:**
- Modify: `web/src/components/RegionCanvas.tsx`
- Create: `web/src/components/RegionCanvas.liveStroke.test.tsx`

**Interfaces:**
- Consumes: existing `RegionCanvas` props (`drawing`, `draftRings`, `onDraftChange`).
- Produces: while pressed, an in-progress stroke is held in React state and drawn as a live dashed line; on release it is decimated → image-space and appended to `draftRings` (unchanged commit semantics).

- [ ] **Step 1: Write the failing test**

react-konva renders to a canvas that jsdom cannot exercise for pointer geometry, so test the **pure stroke-reducer** that this task extracts, not the Konva event plumbing.

```tsx
// web/src/components/RegionCanvas.liveStroke.test.tsx
import { describe, it, expect } from "vitest";
import { appendPoint } from "./RegionCanvas";

describe("live stroke reducer", () => {
  it("appendPoint accumulates points during a drag", () => {
    let s: number[][] = [];
    s = appendPoint(s, [0, 0]);
    s = appendPoint(s, [1, 1]);
    s = appendPoint(s, [2, 2]);
    expect(s).toEqual([[0, 0], [1, 1], [2, 2]]);
  });
});
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd web && npx vitest run src/components/RegionCanvas.liveStroke.test.tsx`
Expected: FAIL — `appendPoint` not exported.

- [ ] **Step 3: Refactor `RegionCanvas` to a live stroke**

Export the reducer and hold the in-progress stroke in state so it re-renders each move:

```tsx
// at module top, add:
export function appendPoint(stroke: number[][], p: number[]): number[][] {
  return stroke.concat([p]);
}
```

Replace the `stroke` ref with React state and draw it live:

```tsx
// inside the component, replace `const stroke = useRef<Pt[]>([]);` with:
const [live, setLive] = useState<Pt[]>([]);

function onDown(e: any) {
  if (!drawing) return;
  const p = pointerPt(e); if (p) setLive([p]);
}
function onMove(e: any) {
  if (!drawing || live.length === 0) return;
  const p = pointerPt(e); if (p) setLive((s) => appendPoint(s, p) as Pt[]);
}
function onUp() {
  if (!drawing || live.length < 3) { setLive([]); return; }
  const ring = decimate(live, DECIMATE_EPS).map((p) => toImageSpace(p, srcW, srcH, dispW, dispH));
  onDraftChange(draftRings.concat([ring]));
  setLive([]);
}
```

Add `useState` to the React import. In the draft `<Layer>`, draw the live stroke as an open dashed line while it has points:

```tsx
{live.length > 1 && (
  <Line points={live.flatMap((p) => p)} stroke="#ff28c8" strokeWidth={2} dash={[6, 4]} />
)}
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd web && npx vitest run src/components/RegionCanvas.liveStroke.test.tsx`
Expected: PASS.

- [ ] **Step 5: Full suite + typecheck**

Run: `cd web && npm test && npx tsc -b --noEmit`
Expected: PASS, no type errors.

- [ ] **Step 6: Commit**

```bash
git add web/src/components/RegionCanvas.tsx web/src/components/RegionCanvas.liveStroke.test.tsx
git commit -m "feat(regions): continuous live lasso stroke during drag"
```

---

## Final verification

- [ ] Run the full suite: `cd web && npm test` — all green.
- [ ] Typecheck: `cd web && npx tsc -b --noEmit` — clean.
- [ ] Lint: `cd web && npm run lint` — no new errors.
- [ ] Manual smoke (`npm run dev` + backend): upload a photo → Generate collapses after generating → switch region in header → surface/tone/finish edit the right region → band cards show role + coverage, top band is an auto chip, `✕` disabled at 3 bands, `+ Add band` disabled at 7 → change a band and watch the pinned preview update while the editor scrolls → Load… previews then Apply, then `↺ Undo` reverts → angle gallery renames/deletes, top bar only switches/adds → lasso paints continuously during drag.
- [ ] Open a PR against `main`; do not merge to `main` directly.

---

## Notes carried from the spec

- **Deferred, not built:** click-a-region-on-the-mini selection, preview layout variants, metallic-aware matching, the "Whole mini" naming-collision rename (spec §2, §10).
- **Do not add:** multi-paint-per-band, band reorder (spec §1). `Blend (↕)` keeps its interpolate-midpoint meaning.
- **No engine / wire changes.** `useAnalyze` already re-fires on palette/coverage/material change, so the live preview needs no new wiring (spec §8).
