# UI pass C — Studio restructure Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Turn the Studio editor column into three numbered steps (Regions → Colour scheme → Layers) plus a collapsed "Save & share", with plain wording, one region selection, a ★ main-colour marker and edge-highlight controls.

**Architecture:** Front-end only (`web/src`). Two small store additions (`setSettings`, runtime-only `Book.anchor_id` + `setAnchor`), a shared `StepSection` header, three new components (`RegionTable`, `LayerTools`, `EdgeSettings`, plus `SaveSharePanel`), slimmed `GeneratePanel`/`BandEditor`/`RecipeManager`, and deletion of `RegionHeader`, `RecipeFooter`, `BandControl`. Wording changes are mostly locale *value* edits — keys stay put where meaning is unchanged, so tests (which mock `t` as identity) keep working.

**Tech Stack:** React 19 + TypeScript, Mantine 7.17, Zustand, react-i18next, Vitest + Testing Library.

**Spec:** `docs/superpowers/specs/2026-10-01-ui-pass-c-studio-design.md`

## Global Constraints

- No backend changes. `WHOLE_MINI_ID = "Whole Mini"` stays the API identifier (never translated).
- `anchor_id` is runtime-only: never sent to the backend, never persisted; undefined = Whole mini.
- Band (layer) limits stay 3–7: delete disabled at 3, Add layer disabled at 7.
- Every user-visible string goes through `t()`; EN and ES key sets must stay identical (`src/i18n/locales.test.ts`).
- Edge settings are per angle (`angle.settings`), not per region; only `edge_hl`, `edge_extreme`, `edge_sens` get UI.
- Tests mock i18n as `vi.mock("react-i18next", () => ({ useTranslation: () => ({ t: (k: string) => k }) }))` — assert on keys, not English.
- All commands run from `web/` (`C:\Users\ag\alvaro\git\mini-highlight-advisor\web`). Branch: `feat/ui-pass-c-studio` (already exists, pushed).

## Review Focus

- Deleting the region that holds the ★ → ★ falls back to Whole mini, no crash, scheme request uses Whole Mini (Task 1 store test, Task 3 table test).
- Adding a new angle → its ★ is on Whole mini while edge settings are inherited from the current angle (Task 1).
- Renaming the starred region → ★ stays on it (anchor is by id, not name) (Task 1).
- Changing surface/tone/finish in a row that is *not* selected → updates that row and does not change the selection (Task 3).
- Turning "Edge highlights" off → "Extra-sharp edge highlight" and the edge slider are disabled (Task 6).

---

### Task 1: Store — `setSettings`, `anchor_id`, `setAnchor`, `anchorIndexOf`

**Files:**
- Modify: `web/src/store/projectStore.ts` (Book interface ~line 37, State interface ~line 55, `removeRegion` ~line 170, add actions near `setVariant`)
- Test: `web/src/store/projectStore.test.ts` (append a new `describe`)

**Interfaces:**
- Produces:
  - `Book.anchor_id?: string`
  - `setSettings(patch: Partial<Settings>): void` — merges into the **active angle's** settings
  - `setAnchor(id: string | undefined): void`
  - `export function anchorIndexOf(book: Book): number` — 0 for Whole mini, `1 + drawn index` otherwise; unknown/undefined id → 0

- [ ] **Step 1: Write the failing tests** — append to `web/src/store/projectStore.test.ts` (it already defines `reset` and `photo(id)` at the top; add `anchorIndexOf` to the existing import from `./projectStore`):

```ts
describe("projectStore settings + anchor", () => {
  beforeEach(reset);
  const tri = [[[10, 10], [20, 10], [20, 20]]];

  it("setSettings merges into the active angle only", () => {
    useProjectStore.getState().initFromPhoto(photo("p1"));
    useProjectStore.getState().addAngle(photo("p2"));          // active = 1
    useProjectStore.getState().setSettings({ edge_sens: 0.8 });
    const s = useProjectStore.getState();
    expect(s.angles[1].settings.edge_sens).toBe(0.8);
    expect(s.angles[1].settings.edge_hl).toBe(true);
    expect(s.angles[0].settings.edge_sens).toBe(0.5);
  });

  it("anchor defaults to whole mini and follows setAnchor", () => {
    const st = useProjectStore.getState();
    st.initFromPhoto(photo("p1"));
    st.addRegion(tri, "Cloak");
    expect(anchorIndexOf(activeBookOf(useProjectStore.getState())!)).toBe(0);
    const id = activeBookOf(useProjectStore.getState())!.drawn[0].id;
    useProjectStore.getState().setAnchor(id);
    expect(anchorIndexOf(activeBookOf(useProjectStore.getState())!)).toBe(1);
    useProjectStore.getState().setAnchor(undefined);
    expect(anchorIndexOf(activeBookOf(useProjectStore.getState())!)).toBe(0);
  });

  it("removing the starred region falls back to whole mini", () => {
    const st = useProjectStore.getState();
    st.initFromPhoto(photo("p1"));
    st.addRegion(tri, "Cloak");
    const id = activeBookOf(useProjectStore.getState())!.drawn[0].id;
    useProjectStore.getState().setAnchor(id);
    useProjectStore.getState().removeRegion(1);
    const b = activeBookOf(useProjectStore.getState())!;
    expect(b.anchor_id).toBeUndefined();
    expect(anchorIndexOf(b)).toBe(0);
  });

  it("removing a different region keeps the anchor and shifts its index", () => {
    const st = useProjectStore.getState();
    st.initFromPhoto(photo("p1"));
    st.addRegion(tri, "Cloak");
    st.addRegion(tri, "Armour");
    const armourId = activeBookOf(useProjectStore.getState())!.drawn[1].id;
    useProjectStore.getState().setAnchor(armourId);
    useProjectStore.getState().removeRegion(1);                 // remove Cloak
    const b = activeBookOf(useProjectStore.getState())!;
    expect(b.anchor_id).toBe(armourId);
    expect(anchorIndexOf(b)).toBe(1);
  });

  it("renaming the starred region keeps the anchor", () => {
    const st = useProjectStore.getState();
    st.initFromPhoto(photo("p1"));
    st.addRegion(tri, "Cloak");
    const id = activeBookOf(useProjectStore.getState())!.drawn[0].id;
    useProjectStore.getState().setAnchor(id);
    useProjectStore.getState().renameRegion(1, "Cape");
    expect(anchorIndexOf(activeBookOf(useProjectStore.getState())!)).toBe(1);
  });

  it("a new angle starts with the anchor on whole mini but inherits settings", () => {
    const st = useProjectStore.getState();
    st.initFromPhoto(photo("p1"));
    st.addRegion(tri, "Cloak");
    useProjectStore.getState().setAnchor(activeBookOf(useProjectStore.getState())!.drawn[0].id);
    useProjectStore.getState().setSettings({ edge_extreme: true });
    useProjectStore.getState().addAngle(photo("p2"));
    const s = useProjectStore.getState();
    expect(anchorIndexOf(activeBookOf(s)!)).toBe(0);
    expect(s.angles[1].settings.edge_extreme).toBe(true);
  });
});
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `npx vitest run src/store/projectStore.test.ts`
Expected: FAIL — `anchorIndexOf` is not exported / `setSettings is not a function`.

- [ ] **Step 3: Implement**

In `Book` add (after `variant?: string;`):

```ts
  anchor_id?: string;   // runtime-only ★ "main colour goes here" region id; undefined = whole mini
```

In `interface State` add (after `setVariant(variant: string): void;`):

```ts
  setAnchor(id: string | undefined): void;
  setSettings(patch: Partial<Settings>): void;
```

After the `activeBookOf` export add:

```ts
/** Index (0 = whole mini, g = drawn[g-1]) of the ★ main-colour region; unknown id → 0. */
export const anchorIndexOf = (book: Book): number =>
  book.drawn.findIndex((r) => r.id === book.anchor_id) + 1;
```

Replace `removeRegion` with:

```ts
  removeRegion: (g) => set((s) => patchBook(s, (b) => {
    if (g < 1 || g > b.drawn.length) return b;
    const removedId = b.drawn[g - 1].id;
    const drawn = b.drawn.slice();
    drawn.splice(g - 1, 1);
    const selected = b.selected === g ? g - 1 : b.selected > g ? b.selected - 1 : b.selected;
    const anchor_id = b.anchor_id === removedId ? undefined : b.anchor_id;
    return { ...b, drawn, selected, anchor_id };
  })),
```

After `setVariant: ...,` add:

```ts
  setAnchor: (id) => set((s) => patchBook(s, (b) => ({ ...b, anchor_id: id }))),

  setSettings: (patch) => set((s) => patchAngle(s, s.activeAngle,
    (a) => ({ ...a, settings: { ...a.settings, ...patch } }))),
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `npx vitest run src/store`
Expected: PASS (all store tests, including the existing undo tests).

- [ ] **Step 5: Commit**

```bash
git add web/src/store/projectStore.ts web/src/store/projectStore.test.ts
git commit -m "feat(web): store setSettings + runtime-only anchor_id (★ main-colour region)"
```

---

### Task 2: Wording — new keys and renamed values (EN + ES)

**Files:**
- Modify: `web/src/i18n/locales/en.json`, `web/src/i18n/locales/es.json`
- Test: `web/src/i18n/locales.test.ts`

**Interfaces:**
- Produces (keys used by Tasks 3–8): `studio.step_regions`, `studio.draw_region`, `studio.anchor_aria`, `studio.step_scheme`, `studio.scheme_caption`, `studio.anchor_caption`, `studio.step_layers`, `studio.fill_from`, `studio.fill_one_colour`, `studio.fill_recipe`, `studio.save_share`, `edges.title`, `edges.enabled`, `edges.extreme`, `edges.sens`, `edges.fewer`, `edges.more`, `colour.coverage_hint`, `colour.tone_placeholder`.
- Old keys are **not deleted here** (components still reference them until Task 8).

- [ ] **Step 1: Write the failing test** — append to `web/src/i18n/locales.test.ts`:

```ts
it("no developer jargon (L2/L3, N2/N3, 'auto') in locale values", () => {
  for (const loc of [en, es]) {
    for (const k of keys(loc)) {
      const v = String(k.split(".").reduce((o: any, s) => o[s], loc));
      expect(v, k).not.toMatch(/\((L|N)[123]\)/);
      expect(v, k).not.toMatch(/^auto$/);
    }
  }
});

it("has the Studio step keys", () => {
  for (const k of ["studio.step_regions", "studio.step_scheme", "studio.step_layers",
                   "studio.save_share", "edges.enabled", "studio.fill_from"]) {
    expect(keys(en)).toContain(k);
  }
});
```

- [ ] **Step 2: Run test to verify it fails**

Run: `npx vitest run src/i18n/locales.test.ts`
Expected: FAIL — `colour.ramp_editor` value contains "(L2)", `colour.auto` is "auto", and the studio keys are missing.

- [ ] **Step 3: Edit both locale files**

**Changed values** (key → EN / ES):

| key | EN | ES |
|---|---|---|
| `colour.hero_colour` | Main colour | Color principal |
| `colour.harmony` | Colour harmony | Armonía de color |
| `colour.generate` | Suggest colours | Sugerir colores |
| `colour.generating` | Suggesting… | Sugiriendo… |
| `colour.midtone` | Middle colour | Color medio |
| `colour.reset_coverage` | Reset areas | Restablecer áreas |
| `colour.save_recipe` | Save as recipe | Guardar como receta |
| `colour.add_band` | + Add layer | + Añadir capa |
| `colour.delete_band` | Delete layer | Eliminar capa |
| `colour.auto` | fills the rest | rellena el resto |
| `colour.coverage` | Area | Área |
| `colour.toggle_generate` | Show or hide the colour scheme | Mostrar u ocultar el esquema de color |
| `colour.ramp_editor` | Quick ramp from one colour | Rampa rápida desde un color |
| `colour.band_editor` | Layers | Capas |
| `colour.generate_whole_mini` | Colour scheme | Esquema de color |
| `technique.material` | Finish | Acabado |
| `schemes.title` | Saved schemes | Esquemas guardados |
| `schemes.save` | Save current colours | Guardar colores actuales |
| `region.intro` (ES only) | — | Las regiones permiten dar a una parte de la mini (manto, armadura, piel) sus propios colores. |

(The ES `region.intro` change avoids "capa" meaning both *cloak* and *layer*. `ramp_editor`/`band_editor`/`generate_whole_mini` get jargon-free values now only so the test passes; Task 8 deletes them.)

**New keys** — add to the existing `colour` object, the existing `studio` object, and a new top-level `edges` object:

| key | EN | ES |
|---|---|---|
| `colour.coverage_hint` | How much of the region this layer covers | Cuánto de la región cubre esta capa |
| `colour.tone_placeholder` | pale, dark… | claro, oscuro… |
| `studio.step_regions` | Regions | Regiones |
| `studio.draw_region` | + Draw a region | + Dibujar una región |
| `studio.anchor_aria` | Main colour goes on {{name}} | El color principal va en {{name}} |
| `studio.step_scheme` | Colour scheme | Esquema de color |
| `studio.scheme_caption` | all regions · optional | todas las regiones · opcional |
| `studio.anchor_caption` | ★ marks the region that gets the main colour | ★ marca la región que lleva el color principal |
| `studio.step_layers` | Layers for | Capas de |
| `studio.fill_from` | Fill layers from: | Rellenar capas desde: |
| `studio.fill_one_colour` | one colour | un color |
| `studio.fill_recipe` | a saved recipe | una receta guardada |
| `studio.save_share` | Save & share | Guardar y compartir |
| `edges.title` | Edge highlights · whole mini | Luces de borde · toda la mini |
| `edges.enabled` | Edge highlights | Luces de borde |
| `edges.extreme` | Extra-sharp edge highlight | Luz de borde extra nítida |
| `edges.sens` | How many edges | Cuántos bordes |
| `edges.fewer` | fewer, sharpest | menos, más nítidos |
| `edges.more` | more | más |

- [ ] **Step 4: Run tests to verify they pass**

Run: `npx vitest run src/i18n src/components/colour/BandCard.test.tsx`
Expected: PASS (BandCard's `/auto/i` assertion matches the mocked key `colour.auto`).

- [ ] **Step 5: Commit**

```bash
git add web/src/i18n
git commit -m "feat(web): Studio wording — layers/area/main colour/finish, step + edge keys (EN+ES)"
```

---

### Task 3: `StepSection` + `RegionTable` (step 1)

**Files:**
- Create: `web/src/components/StepSection.tsx`, `web/src/components/RegionTable.tsx`
- Test: `web/src/components/RegionTable.test.tsx`

**Interfaces:**
- Consumes: `setAnchor`, `anchorIndexOf` (Task 1); `studio.*` keys (Task 2); existing `setSelected(g)`, `setSurface(g, v)`, `setTone(g, v)`, `setMaterial(g, v)`, `ManagePanel`, `SURFACES`.
- Produces:
  - `StepSection({ n?: number; title: ReactNode; caption?: string; right?: ReactNode; testId?: string; children: ReactNode })`
  - `RegionTable()` — no props; root has `data-testid="step-regions"`; rows have `data-testid="region-row-{g}"`.

- [ ] **Step 1: Write the failing test** — `web/src/components/RegionTable.test.tsx`:

```tsx
import { describe, it, expect, beforeEach, vi } from "vitest";
import { render, screen, fireEvent } from "@testing-library/react";
import { MantineProvider } from "@mantine/core";
import { RegionTable } from "./RegionTable";
import { useProjectStore, activeBookOf } from "../store/projectStore";
import type { PhotoResponse } from "../api/types";

vi.mock("react-i18next", () => ({ useTranslation: () => ({ t: (k: string) => k }) }));
vi.mock("./ManagePanel", () => ({ ManagePanel: () => <div>manage-panel</div> }));

const photo = (): PhotoResponse => ({
  photo_id: "p1", width: 10, height: 10, quality_checks: [],
  default_whole: { palette: [{ name: "a", hex: "#111" }, { name: "b", hex: "#aaa" }, { name: "c", hex: "#eee" }],
                   coverage: [0.5, 0.3, 0.2], material: "matte" },
});
const reset = () => useProjectStore.setState(useProjectStore.getInitialState(), true);
const book = () => activeBookOf(useProjectStore.getState())!;
const ui = () => render(<MantineProvider><RegionTable /></MantineProvider>);

describe("RegionTable", () => {
  beforeEach(() => {
    reset();
    useProjectStore.getState().initFromPhoto(photo());
    useProjectStore.getState().addRegion([[[1, 1], [2, 2], [3, 1]]], "Cloak");
    useProjectStore.getState().setSelected(0);
  });

  it("renders one row per region, whole mini first", () => {
    ui();
    expect(screen.getByTestId("region-row-0").textContent).toContain("region.whole_mini");
    expect(screen.getByTestId("region-row-1").textContent).toContain("Cloak");
  });

  it("clicking a row selects it and marks it aria-selected", () => {
    const { rerender } = ui();
    fireEvent.click(screen.getByText("Cloak"));
    expect(book().selected).toBe(1);
    rerender(<MantineProvider><RegionTable /></MantineProvider>);
    expect(screen.getByTestId("region-row-1").getAttribute("aria-selected")).toBe("true");
    expect(screen.getByTestId("region-row-0").getAttribute("aria-selected")).toBe("false");
  });

  it("editing a non-selected row updates that row without changing the selection", () => {
    ui();
    fireEvent.change(screen.getByLabelText("technique.material Cloak"), { target: { value: "metallic" } });
    fireEvent.change(screen.getByLabelText("colour.tone Cloak"), { target: { value: "dark" } });
    expect(book().drawn[0].material).toBe("metallic");
    expect(book().drawn[0].tone).toBe("dark");
    expect(book().whole.material).toBe("matte");
    expect(book().selected).toBe(0);
  });

  it("★ starts on whole mini and moves to the clicked row without selecting it", () => {
    const { rerender } = ui();
    const stars = () => screen.getAllByLabelText("studio.anchor_aria");
    expect(stars()[0].textContent).toBe("★");
    expect(stars()[1].textContent).toBe("☆");
    fireEvent.click(stars()[1]);
    expect(book().anchor_id).toBe(book().drawn[0].id);
    expect(book().selected).toBe(0);
    rerender(<MantineProvider><RegionTable /></MantineProvider>);
    expect(stars()[1].textContent).toBe("★");
  });

  it("deleting the starred region puts the ★ back on whole mini", () => {
    useProjectStore.getState().setAnchor(book().drawn[0].id);
    useProjectStore.getState().removeRegion(1);
    ui();
    expect(screen.getAllByLabelText("studio.anchor_aria")[0].textContent).toBe("★");
  });

  it("'Draw a region' toggles the region manager", () => {
    ui();
    const btn = screen.getByRole("button", { name: "studio.draw_region" });
    expect(btn.getAttribute("aria-expanded")).toBe("false");
    fireEvent.click(btn);
    expect(btn.getAttribute("aria-expanded")).toBe("true");
    expect(screen.getByText("manage-panel")).toBeTruthy();
  });
});
```

- [ ] **Step 2: Run test to verify it fails**

Run: `npx vitest run src/components/RegionTable.test.tsx`
Expected: FAIL — cannot resolve `./RegionTable`.

- [ ] **Step 3: Implement**

`web/src/components/StepSection.tsx`:

```tsx
import type { ReactNode } from "react";
import { Badge, Group, Stack, Text } from "@mantine/core";

interface Props {
  n?: number; title: ReactNode; caption?: string; right?: ReactNode; testId?: string; children: ReactNode;
}

/** Numbered step header (circle + title + optional right slot + caption) above its content. */
export function StepSection({ n, title, caption, right, testId, children }: Props) {
  return (
    <Stack gap="xs" data-testid={testId}>
      <Group gap="xs" align="center" wrap="wrap">
        {n !== undefined && <Badge circle size="lg" variant="filled">{n}</Badge>}
        <Text fw={600}>{title}</Text>
        {right}
        {caption && <Text size="xs" c="dimmed">{caption}</Text>}
      </Group>
      {children}
    </Stack>
  );
}
```

`web/src/components/RegionTable.tsx`:

```tsx
import { useState } from "react";
import type { MouseEvent } from "react";
import { useTranslation } from "react-i18next";
import { ActionIcon, Button, Collapse, NativeSelect, Table, TextInput } from "@mantine/core";
import { useProjectStore, activeBookOf, anchorIndexOf } from "../store/projectStore";
import { SURFACES } from "../api/types";
import { ManagePanel } from "./ManagePanel";
import { StepSection } from "./StepSection";

// Inputs inside a row must not also select the row.
const stop = (e: MouseEvent) => e.stopPropagation();

export function RegionTable() {
  const { t } = useTranslation();
  const book = useProjectStore(activeBookOf);
  const setSelected = useProjectStore((s) => s.setSelected);
  const setSurface = useProjectStore((s) => s.setSurface);
  const setTone = useProjectStore((s) => s.setTone);
  const setMaterial = useProjectStore((s) => s.setMaterial);
  const setAnchor = useProjectStore((s) => s.setAnchor);
  const [drawOpen, setDrawOpen] = useState(false);

  if (!book) return null;
  const anchor = anchorIndexOf(book);
  const rows = [
    { id: undefined as string | undefined, name: t("region.whole_mini"), r: book.whole },
    ...book.drawn.map((d) => ({ id: d.id as string | undefined, name: d.name, r: d })),
  ];

  return (
    <StepSection n={1} title={t("studio.step_regions")} testId="step-regions">
      <Table verticalSpacing={4} highlightOnHover>
        <Table.Thead>
          <Table.Tr>
            <Table.Th />
            <Table.Th>{t("region.select")}</Table.Th>
            <Table.Th>{t("colour.surface")}</Table.Th>
            <Table.Th>{t("colour.tone")}</Table.Th>
            <Table.Th>{t("technique.material")}</Table.Th>
          </Table.Tr>
        </Table.Thead>
        <Table.Tbody>
          {rows.map(({ id, name, r }, g) => {
            const selected = g === book.selected;
            return (
              <Table.Tr key={id ?? "__whole__"} data-testid={`region-row-${g}`}
                aria-selected={selected} onClick={() => setSelected(g)} style={{ cursor: "pointer" }}
                bg={selected ? "var(--mantine-primary-color-light)" : undefined}>
                <Table.Td onClick={stop}>
                  <ActionIcon size="sm" variant="subtle" aria-pressed={g === anchor}
                    aria-label={t("studio.anchor_aria", { name })} onClick={() => setAnchor(id)}>
                    {g === anchor ? "★" : "☆"}
                  </ActionIcon>
                </Table.Td>
                <Table.Td>{name}</Table.Td>
                <Table.Td onClick={stop}>
                  <NativeSelect size="xs" aria-label={`${t("colour.surface")} ${name}`}
                    value={r.surface ?? "skin"} onChange={(e) => setSurface(g, e.target.value)}
                    data={SURFACES.map((s) => ({ value: s, label: t(`surfaces.${s}`) }))} />
                </Table.Td>
                <Table.Td onClick={stop}>
                  <TextInput size="xs" aria-label={`${t("colour.tone")} ${name}`} style={{ maxWidth: 120 }}
                    placeholder={t("colour.tone_placeholder")} value={r.tone ?? ""}
                    onChange={(e) => setTone(g, e.target.value)} />
                </Table.Td>
                <Table.Td onClick={stop}>
                  <NativeSelect size="xs" aria-label={`${t("technique.material")} ${name}`}
                    value={r.material} onChange={(e) => setMaterial(g, e.target.value)}
                    data={[{ value: "matte", label: t("technique.matte") },
                           { value: "metallic", label: t("technique.metallic") }]} />
                </Table.Td>
              </Table.Tr>
            );
          })}
        </Table.Tbody>
      </Table>
      <Button size="xs" variant="subtle" style={{ alignSelf: "flex-start" }}
        aria-expanded={drawOpen} onClick={() => setDrawOpen((o) => !o)}>
        {t("studio.draw_region")}
      </Button>
      <Collapse in={drawOpen}><ManagePanel /></Collapse>
    </StepSection>
  );
}
```

- [ ] **Step 4: Run test to verify it passes**

Run: `npx vitest run src/components/RegionTable.test.tsx`
Expected: PASS (6 tests).

- [ ] **Step 5: Commit**

```bash
git add web/src/components/StepSection.tsx web/src/components/RegionTable.tsx web/src/components/RegionTable.test.tsx
git commit -m "feat(web): step 1 region table — row click selects, ★ marks main-colour region"
```

---

### Task 4: Slim `GeneratePanel` (step 2)

**Files:**
- Modify: `web/src/components/colour/GeneratePanel.tsx`
- Test: `web/src/components/colour/GeneratePanel.test.tsx`

**Interfaces:**
- Consumes: `anchorIndexOf`, `setAnchor` (Task 1), `StepSection` (Task 3), `studio.step_scheme`, `studio.scheme_caption`, `studio.anchor_caption` (Task 2).
- Produces: `GeneratePanel()` root has `data-testid="step-scheme"`; no anchor dropdown.

- [ ] **Step 1: Update the tests** — in `GeneratePanel.test.tsx`, add `activeBookOf` to the store import, **delete** the test `"displays the translated whole-mini label in the anchor select"`, and append inside the `describe`:

```tsx
  it("has no anchor dropdown and shows the ★ caption", () => {
    render(<MantineProvider><GeneratePanel /></MantineProvider>);
    expect(screen.queryByLabelText("colour.anchor_region")).toBeNull();
    expect(screen.getByText("studio.anchor_caption")).toBeTruthy();
  });

  it("anchors the request on the ★ region from the store", async () => {
    useProjectStore.getState().addRegion([[[1, 1], [2, 2], [3, 1]]], "Cloak");
    const id = activeBookOf(useProjectStore.getState())!.drawn[0].id;
    useProjectStore.getState().setAnchor(id);
    const spy = vi.spyOn(client, "generateScheme").mockResolvedValue({ palettes: {} } as any);
    render(<MantineProvider><GeneratePanel /></MantineProvider>);
    fireEvent.click(screen.getByText("colour.generate"));
    await waitFor(() => expect(spy).toHaveBeenCalled());
    const req = spy.mock.calls[0][0];
    expect(req.anchor_name).toBe("Cloak");
    expect(req.specs.map((s) => s.is_anchor)).toEqual([false, true]);
  });

  it("an unknown anchor id falls back to Whole Mini", async () => {
    useProjectStore.getState().setAnchor("gone");
    const spy = vi.spyOn(client, "generateScheme").mockResolvedValue({ palettes: {} } as any);
    render(<MantineProvider><GeneratePanel /></MantineProvider>);
    fireEvent.click(screen.getByText("colour.generate"));
    await waitFor(() => expect(spy).toHaveBeenCalled());
    expect(spy.mock.calls[0][0].anchor_name).toBe("Whole Mini");
    expect(spy.mock.calls[0][0].specs[0].is_anchor).toBe(true);
  });
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `npx vitest run src/components/colour/GeneratePanel.test.tsx`
Expected: FAIL — caption not found; the anchor request test gets `anchor_name` "Whole Mini".

- [ ] **Step 3: Implement** — in `GeneratePanel.tsx`:

1. Imports: change the store import to `import { useProjectStore, activeBookOf, anchorIndexOf } from "../../store/projectStore";` and add `import { StepSection } from "../StepSection";`.
2. Delete `const [anchorIndex, setAnchorIndex] = useState(0);` and the `regionLabels` line.
3. After `const expanded = ...;` add `const anchorIndex = anchorIndexOf(book);` (the existing `handleGenerate` already uses `anchorIndex` for `is_anchor` and `anchorName`, so it needs no change).
4. Replace the whole `return (...)` with:

```tsx
  return (
    <StepSection n={2} title={t("studio.step_scheme")} caption={t("studio.scheme_caption")} testId="step-scheme"
      right={
        <ActionIcon size="sm" variant="subtle" data-testid="generate-toggle"
          onClick={() => setOpen(!expanded)} aria-label={t("colour.toggle_generate")}>
          {expanded ? "▾" : "▸"}
        </ActionIcon>
      }>
      {expanded && (
        <>
          <Group gap="xs" align="flex-end" wrap="wrap">
            <ColorInput label={t("colour.hero_colour")} value={heroHex} onChange={setHeroHexLocal}
              format="hex" size="xs" withEyeDropper={false} />
            <NativeSelect label={t("colour.mood")} size="xs" value={mood}
              onChange={(e) => setMoodLocal(e.target.value)}
              data={MOODS.map((m) => ({ value: m, label: t(`moods.${m}`) }))} />
            <NativeSelect label={t("colour.harmony")} size="xs" value={variant}
              onChange={(e) => setVariantLocal(e.target.value)}
              data={VARIANTS.map((v) => ({ value: v, label: t(`variants.${v}`) }))} />
          </Group>
          <Text size="xs" c="dimmed">{t("studio.anchor_caption")}</Text>
          <Group gap="sm">
            <Checkbox size="xs" label={t("colour.owned_only")} checked={ownedOnly}
              onChange={(e) => setOwnedOnly(e.currentTarget.checked)} />
            <Button size="xs" onClick={handleGenerate} loading={loading}>{t("colour.generate")}</Button>
          </Group>
          {ownedOnly && owned.size === 0 && (
            <Text size="xs" c="dimmed">{t("colour.owned_only_none")}</Text>
          )}
          {error && <ErrorNotice message={t("errors.generate")} detail={error} />}
        </>
      )}
    </StepSection>
  );
```

5. Remove now-unused imports (`Stack` if unused) so `tsc` stays clean.

- [ ] **Step 4: Run tests to verify they pass**

Run: `npx vitest run src/components/colour/GeneratePanel.test.tsx`
Expected: PASS (existing collapse/owned-only/error tests + 3 new).

- [ ] **Step 5: Commit**

```bash
git add web/src/components/colour/GeneratePanel.tsx web/src/components/colour/GeneratePanel.test.tsx
git commit -m "feat(web): step 2 colour scheme reads ★ from store, anchor dropdown removed"
```

---

### Task 5: Step 3 — `BandEditor` header picker, `LayerTools`, BandCard wording

**Files:**
- Create: `web/src/components/colour/LayerTools.tsx`, `web/src/components/colour/LayerTools.test.tsx`
- Modify: `web/src/components/colour/BandEditor.tsx`, `web/src/components/colour/BandEditor.test.tsx`, `web/src/components/colour/BandCard.tsx`, `web/src/components/colour/BandCard.test.tsx`, `web/src/components/colour/RampEditor.tsx`
- (`RecipeFooter.tsx` stays on disk until Task 8 but is no longer imported.)

**Interfaces:**
- Consumes: `StepSection` (Task 3); keys `studio.step_layers`, `studio.fill_from`, `studio.fill_one_colour`, `studio.fill_recipe`, `colour.coverage_hint` (Task 2); existing `RampEditor()`, `RecipeLoader({ onRecipeLoaded })`.
- Produces: `LayerTools({ g: number; n: number; onRecipeChanged: () => void })`; `BandEditor()` root has `data-testid="step-layers"` and a `NativeSelect` with `aria-label="region.select"` (key) bound to `book.selected`.

- [ ] **Step 1: Write the failing tests**

`web/src/components/colour/LayerTools.test.tsx`:

```tsx
import { describe, it, expect, beforeEach, vi } from "vitest";
import { render, screen, fireEvent } from "@testing-library/react";
import { MantineProvider } from "@mantine/core";
import { LayerTools } from "./LayerTools";
import { useProjectStore, activeBookOf } from "../../store/projectStore";
import type { PhotoResponse } from "../../api/types";

vi.mock("react-i18next", () => ({ useTranslation: () => ({ t: (k: string) => k }) }));
vi.mock("./RampEditor", () => ({ RampEditor: () => <div>ramp-editor</div> }));
vi.mock("./RecipeLoader", () => ({ RecipeLoader: () => <div>recipe-loader</div> }));

const photo = (): PhotoResponse => ({
  photo_id: "p1", width: 10, height: 10, quality_checks: [],
  default_whole: { palette: [{ name: "a", hex: "#111" }, { name: "b", hex: "#aaa" }, { name: "c", hex: "#eee" }],
                   coverage: [0.5, 0.3, 0.2], material: "matte" },
});
const reset = () => useProjectStore.setState(useProjectStore.getInitialState(), true);
const ui = (n = 3) => render(<MantineProvider><LayerTools g={0} n={n} onRecipeChanged={() => {}} /></MantineProvider>);

describe("LayerTools", () => {
  beforeEach(() => { reset(); useProjectStore.getState().initFromPhoto(photo()); });

  it("undo button's accessible name is translated", () => {
    ui();
    expect(screen.getByLabelText("colour.undo")).toBeTruthy();
  });

  it("Add layer appends a layer, and is disabled at 7", () => {
    const { unmount } = ui(3);
    fireEvent.click(screen.getByText("colour.add_band"));
    expect(activeBookOf(useProjectStore.getState())!.whole.palette).toHaveLength(4);
    unmount();
    ui(7);
    expect(screen.getByText("colour.add_band").closest("button")).toBeDisabled();
  });

  it("fill tools open one panel at a time and close on second click", () => {
    ui();
    expect(screen.queryByText("ramp-editor")).toBeNull();
    expect(screen.queryByText("recipe-loader")).toBeNull();
    fireEvent.click(screen.getByText("studio.fill_one_colour"));
    expect(screen.getByText("ramp-editor")).toBeTruthy();
    fireEvent.click(screen.getByText("studio.fill_recipe"));
    expect(screen.queryByText("ramp-editor")).toBeNull();
    expect(screen.getByText("recipe-loader")).toBeTruthy();
    fireEvent.click(screen.getByText("studio.fill_recipe"));
    expect(screen.queryByText("recipe-loader")).toBeNull();
  });
});
```

Replace `web/src/components/colour/BandEditor.test.tsx` mocks and the footer test: change `vi.mock("./RecipeFooter", ...)` to

```tsx
vi.mock("./LayerTools", () => ({ LayerTools: () => <div>layer-tools</div> }));
```

add `fireEvent` to the testing-library import and `activeBookOf` to the store import, replace the `"renders the RecipeFooter"` test with:

```tsx
  it("renders the layer tools", () => {
    render(<MantineProvider><BandEditor /></MantineProvider>);
    expect(screen.getByText("layer-tools")).toBeTruthy();
  });

  it("the 'Layers for' picker reflects and changes the selected region", () => {
    useProjectStore.getState().addRegion([[[1, 1], [2, 2], [3, 1]]], "Cloak");   // selects 1
    render(<MantineProvider><BandEditor /></MantineProvider>);
    const sel = screen.getByLabelText("region.select") as HTMLSelectElement;
    expect(sel.value).toBe("1");
    fireEvent.change(sel, { target: { value: "0" } });
    expect(activeBookOf(useProjectStore.getState())!.selected).toBe(0);
  });
```

In `BandCard.test.tsx`, append inside the `describe`:

```tsx
  it("the last layer shows its share as '· fills the rest'", () => {
    renderCard({ isAuto: true, role: "Highlight", coverageValue: 0.13 });
    expect(screen.getByText("13% · colour.auto")).toBeTruthy();
  });
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `npx vitest run src/components/colour`
Expected: FAIL — `./LayerTools` missing; BandEditor has no `region.select`; BandCard text is `13% (colour.auto)`.

- [ ] **Step 3: Implement**

`web/src/components/colour/LayerTools.tsx`:

```tsx
import { useState } from "react";
import { useTranslation } from "react-i18next";
import { Button, Group, Stack, Text } from "@mantine/core";
import { useProjectStore, activeBookOf } from "../../store/projectStore";
import { defaultCoverage } from "../../lib/roles";
import type { PaintColor } from "../../api/types";
import { RampEditor } from "./RampEditor";
import { RecipeLoader } from "./RecipeLoader";

interface Props { g: number; n: number; onRecipeChanged: () => void; }
type Fill = "ramp" | "recipe";

export function LayerTools({ g, n, onRecipeChanged }: Props) {
  const { t } = useTranslation();
  const setBandCount = useProjectStore((s) => s.setBandCount);
  const setHexSlot = useProjectStore((s) => s.setHexSlot);
  const setCoverage = useProjectStore((s) => s.setCoverage);
  const snapshotUndo = useProjectStore((s) => s.snapshotUndo);
  const undo = useProjectStore((s) => s.undo);
  const canUndo = useProjectStore((s) => s.undoSnapshot !== null);
  const palette = useProjectStore((s) => {
    const book = activeBookOf(s);
    if (!book) return [] as PaintColor[];
    return g === 0 ? book.whole.palette : book.drawn[g - 1]?.palette ?? [];
  });
  const [fill, setFill] = useState<Fill | null>(null);
  const toggle = (f: Fill) => setFill((cur) => (cur === f ? null : f));

  const addBand = () => {
    if (n < 7) {
      setBandCount(n + 1);
      setHexSlot(g, n, palette[n - 1]?.hex ?? "#808080");
    }
  };
  const resetCoverage = () => { snapshotUndo(); setCoverage(defaultCoverage(n)); };

  return (
    <Stack gap="xs">
      <Group gap="xs" wrap="wrap">
        <Button size="xs" variant="light" onClick={addBand} disabled={n >= 7}>{t("colour.add_band")}</Button>
        <Button size="xs" variant="subtle" onClick={resetCoverage}>{t("colour.reset_coverage")}</Button>
        <Button size="xs" variant="subtle" onClick={undo} disabled={!canUndo}
          aria-label={t("colour.undo")}>↺ {t("colour.undo")}</Button>
      </Group>
      <Group gap="xs" align="center" wrap="wrap">
        <Text size="xs">{t("studio.fill_from")}</Text>
        <Button size="xs" variant={fill === "ramp" ? "filled" : "default"} aria-pressed={fill === "ramp"}
          onClick={() => toggle("ramp")}>{t("studio.fill_one_colour")}</Button>
        <Button size="xs" variant={fill === "recipe" ? "filled" : "default"} aria-pressed={fill === "recipe"}
          onClick={() => toggle("recipe")}>{t("studio.fill_recipe")}</Button>
      </Group>
      {fill === "ramp" && <RampEditor />}
      {fill === "recipe" && <RecipeLoader onRecipeLoaded={onRecipeChanged} />}
    </Stack>
  );
}
```

`web/src/components/colour/BandEditor.tsx` — replace imports and return:

```tsx
import { useState } from "react";
import { useTranslation } from "react-i18next";
import { NativeSelect, Stack } from "@mantine/core";
import { useProjectStore, activeBookOf } from "../../store/projectStore";
import { roleNames, ROLE_KEY } from "../../lib/roles";
import { StepSection } from "../StepSection";
import { BandCard } from "./BandCard";
import { LayerTools } from "./LayerTools";
```

add `const setSelected = useProjectStore((s) => s.setSelected);` next to `setCoverage`, add `const names = [t("region.whole_mini"), ...book.drawn.map((r) => r.name)];` after the `region` guard, keep `handleCoverage` unchanged, and replace the `return (...)` with:

```tsx
  return (
    <StepSection n={3} title={t("studio.step_layers")} testId="step-layers"
      right={
        <NativeSelect aria-label={t("region.select")} size="xs" value={g}
          onChange={(e) => setSelected(Number(e.target.value))}>
          {names.map((name, i) => <option key={i} value={i}>{name}</option>)}
        </NativeSelect>
      }>
      {/* Re-keyed after a recipe is applied: remounts cards and closes the fill panel. */}
      <Stack gap="xs" key={recipeKey}>
        {palette.map((paint, i) => (
          <BandCard key={i} g={g} i={i} paint={paint} finish={material} n={n} palette={palette}
            role={roles[i]} coverageValue={coverage[i] ?? 0} isAuto={i === n - 1} onCoverage={handleCoverage} />
        ))}
        <LayerTools g={g} n={n} onRecipeChanged={() => setRecipeKey((k) => k + 1)} />
      </Stack>
    </StepSection>
  );
```

`web/src/components/colour/BandCard.tsx`:
- Add `Tooltip` to the `@mantine/core` import.
- Change the auto chip to: `<Text size="xs" c="dimmed">{pct}% · {t("colour.auto")}</Text>`
- Replace `<Text size="xs" miw={70}>{t("colour.coverage")}</Text>` with:

```tsx
          <Tooltip label={t("colour.coverage_hint")} withArrow>
            <Text size="xs" miw={70} style={{ cursor: "help" }}>{t("colour.coverage")} ⓘ</Text>
          </Tooltip>
```

- Add `thumbLabel={t("colour.coverage")}` to the `<Slider ...>`.

`web/src/components/colour/RampEditor.tsx`: delete the line `<Text size="sm" fw={500}>{t("colour.ramp_editor")}</Text>` (the "one colour" toggle now labels it) and drop `Text` from the import if unused.

- [ ] **Step 4: Run tests to verify they pass**

Run: `npx vitest run src/components/colour`
Expected: PASS (`RecipeFooter.test.tsx` still passes — the file is untouched until Task 8).

- [ ] **Step 5: Commit**

```bash
git add web/src/components/colour
git commit -m "feat(web): step 3 'Layers for' picker + LayerTools with 'Fill layers from' toggles"
```

---

### Task 6: `EdgeSettings`

**Files:**
- Create: `web/src/components/EdgeSettings.tsx`, `web/src/components/EdgeSettings.test.tsx`
- Modify: `web/src/components/colour/BandEditor.tsx` (mount after the keyed Stack), `web/src/components/colour/BandEditor.test.tsx` (add the `../EdgeSettings` mock)

**Interfaces:**
- Consumes: `setSettings` (Task 1); `edges.*` keys (Task 2); `activeAngleOf`.
- Produces: `EdgeSettings()` — no props.

- [ ] **Step 1: Write the failing test** — `web/src/components/EdgeSettings.test.tsx`:

```tsx
import { describe, it, expect, beforeEach, vi } from "vitest";
import { render, screen, fireEvent } from "@testing-library/react";
import { MantineProvider } from "@mantine/core";
import { EdgeSettings } from "./EdgeSettings";
import { useProjectStore, activeAngleOf } from "../store/projectStore";
import type { PhotoResponse } from "../api/types";

vi.mock("react-i18next", () => ({ useTranslation: () => ({ t: (k: string) => k }) }));

const photo = (): PhotoResponse => ({
  photo_id: "p1", width: 10, height: 10, quality_checks: [],
  default_whole: { palette: [{ name: "a", hex: "#111" }, { name: "b", hex: "#aaa" }, { name: "c", hex: "#eee" }],
                   coverage: [0.5, 0.3, 0.2], material: "matte" },
});
const reset = () => useProjectStore.setState(useProjectStore.getInitialState(), true);
const settings = () => activeAngleOf(useProjectStore.getState())!.settings;
const ui = () => render(<MantineProvider><EdgeSettings /></MantineProvider>);

describe("EdgeSettings", () => {
  beforeEach(() => { reset(); useProjectStore.getState().initFromPhoto(photo()); });

  it("checkboxes write edge_hl and edge_extreme", () => {
    ui();
    fireEvent.click(screen.getByLabelText("edges.extreme"));
    expect(settings().edge_extreme).toBe(true);
    fireEvent.click(screen.getByLabelText("edges.enabled"));
    expect(settings().edge_hl).toBe(false);
  });

  it("turning edge highlights off disables extra-sharp and the slider", () => {
    useProjectStore.getState().setSettings({ edge_hl: false });
    ui();
    expect(screen.getByLabelText("edges.extreme")).toBeDisabled();
    expect(screen.getByRole("slider", { name: "edges.sens" }).getAttribute("aria-disabled")).toBe("true");
  });

  it("the edge slider commits edge_sens", () => {
    ui();
    const thumb = screen.getByRole("slider", { name: "edges.sens" });
    fireEvent.keyDown(thumb, { key: "ArrowRight" });
    expect(settings().edge_sens).toBeCloseTo(0.55);
  });
});
```

- [ ] **Step 2: Run test to verify it fails**

Run: `npx vitest run src/components/EdgeSettings.test.tsx`
Expected: FAIL — cannot resolve `./EdgeSettings`.

- [ ] **Step 3: Implement** — `web/src/components/EdgeSettings.tsx`:

```tsx
import { useState } from "react";
import { useTranslation } from "react-i18next";
import { Checkbox, Divider, Group, Slider, Stack, Text } from "@mantine/core";
import { useProjectStore, activeAngleOf } from "../store/projectStore";

/** Per-angle edge-highlight settings; changes re-run the preview via useAnalyze. */
export function EdgeSettings() {
  const { t } = useTranslation();
  const settings = useProjectStore((s) => activeAngleOf(s)?.settings);
  const setSettings = useProjectStore((s) => s.setSettings);
  // Local value while dragging; committed on release so a drag is one analysis, not dozens.
  const [dragSens, setDragSens] = useState<number | null>(null);

  if (!settings) return null;
  const off = !settings.edge_hl;

  return (
    <Stack gap={4}>
      <Divider label={t("edges.title")} labelPosition="left" />
      <Group gap="md" wrap="wrap">
        <Checkbox size="xs" label={t("edges.enabled")} checked={settings.edge_hl}
          onChange={(e) => setSettings({ edge_hl: e.currentTarget.checked })} />
        <Checkbox size="xs" label={t("edges.extreme")} checked={settings.edge_extreme} disabled={off}
          onChange={(e) => setSettings({ edge_extreme: e.currentTarget.checked })} />
      </Group>
      <Group gap="xs" align="center" wrap="nowrap">
        <Text size="xs" miw={90}>{t("edges.sens")}</Text>
        <Text size="xs" c="dimmed">{t("edges.fewer")}</Text>
        <Slider thumbLabel={t("edges.sens")} min={0} max={1} step={0.05} size="sm" style={{ flex: 1 }}
          label={null} disabled={off} value={dragSens ?? settings.edge_sens} onChange={setDragSens}
          onChangeEnd={(v) => { setDragSens(null); setSettings({ edge_sens: v }); }} />
        <Text size="xs" c="dimmed">{t("edges.more")}</Text>
      </Group>
    </Stack>
  );
}
```

In `BandEditor.tsx` add `import { EdgeSettings } from "../EdgeSettings";` and render `<EdgeSettings />` right after the keyed `<Stack>` (inside `StepSection`, outside the keyed Stack). Add to `BandEditor.test.tsx`, next to the other mocks: `vi.mock("../EdgeSettings", () => ({ EdgeSettings: () => <div>edge-settings</div> }));`.

If the slider test fails because the thumb exposes no `aria-disabled`/keyboard `onChangeEnd` in this Mantine version, check `node_modules/@mantine/core/esm/components/Slider/Slider.mjs` for the keydown handler and thumb attributes and adapt the *assertion* (e.g. `data-disabled` on the root via `container.querySelector(".mantine-Slider-root")`) — not the component behaviour.

- [ ] **Step 4: Run tests to verify they pass**

Run: `npx vitest run src/components/EdgeSettings.test.tsx src/components/colour/BandEditor.test.tsx`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add web/src/components/EdgeSettings.tsx web/src/components/EdgeSettings.test.tsx web/src/components/colour/BandEditor.tsx web/src/components/colour/BandEditor.test.tsx
git commit -m "feat(web): edge highlight controls (on/off, extra-sharp, how many) in step 3"
```

---

### Task 7: `SaveSharePanel`; recipes-only `RecipeManager`; `RecipeSaver` without `onSaved`

**Files:**
- Create: `web/src/components/colour/SaveSharePanel.tsx`, `web/src/components/colour/SaveSharePanel.test.tsx`
- Modify: `web/src/components/colour/RecipeManager.tsx`, `web/src/components/colour/RecipeManager.test.tsx`, `web/src/components/colour/RecipeSaver.tsx`

**Interfaces:**
- Consumes: `studio.save_share` (Task 2); existing `SchemeManager()`.
- Produces: `SaveSharePanel()` — root `data-testid="save-share"`, closed by default; `RecipeSaver()` takes no props.

- [ ] **Step 1: Write the failing tests**

`web/src/components/colour/SaveSharePanel.test.tsx`:

```tsx
import { it, expect, vi } from "vitest";
import { render, screen, fireEvent } from "@testing-library/react";
import { MantineProvider } from "@mantine/core";
import { SaveSharePanel } from "./SaveSharePanel";

vi.mock("react-i18next", () => ({ useTranslation: () => ({ t: (k: string) => k }) }));
vi.mock("./RecipeSaver", () => ({ RecipeSaver: () => <div>recipe-saver</div> }));
vi.mock("./SchemeManager", () => ({ SchemeManager: () => <div>scheme-manager</div> }));
vi.mock("./RecipeManager", () => ({ RecipeManager: () => <div>recipe-manager</div> }));

it("is collapsed by default and opens to show save, schemes and recipe import/export", () => {
  render(<MantineProvider><SaveSharePanel /></MantineProvider>);
  expect(screen.queryByText("recipe-saver")).toBeNull();
  const btn = screen.getByRole("button", { name: /studio.save_share/ });
  expect(btn.getAttribute("aria-expanded")).toBe("false");
  fireEvent.click(btn);
  expect(screen.getByText("recipe-saver")).toBeTruthy();
  expect(screen.getByText("scheme-manager")).toBeTruthy();
  expect(screen.getByText("recipe-manager")).toBeTruthy();
});
```

In `RecipeManager.test.tsx`, replace the test `"collection import from Studio updates the owned set"` with:

```tsx
it("offers recipe import/export only — no collection buttons", () => {
  const { container } = render(<MantineProvider><RecipeManager /></MantineProvider>);
  expect(screen.getByText("recipes.export")).toBeTruthy();
  expect(screen.getByText("recipes.import")).toBeTruthy();
  expect(screen.queryByText("recipes.collection_export")).toBeNull();
  expect(screen.queryByText("recipes.collection_import")).toBeNull();
  expect(container.querySelector('input[data-kind="collection"]')).toBeNull();
});
```

and remove the now-unused `useCatalogStore` import and its `setState` in `beforeEach` (keep `vi.restoreAllMocks()`).

- [ ] **Step 2: Run tests to verify they fail**

Run: `npx vitest run src/components/colour/SaveSharePanel.test.tsx src/components/colour/RecipeManager.test.tsx`
Expected: FAIL — `./SaveSharePanel` missing; collection buttons still rendered.

- [ ] **Step 3: Implement**

`web/src/components/colour/SaveSharePanel.tsx`:

```tsx
import { useState } from "react";
import { useTranslation } from "react-i18next";
import { Button, Stack } from "@mantine/core";
import { RecipeSaver } from "./RecipeSaver";
import { SchemeManager } from "./SchemeManager";
import { RecipeManager } from "./RecipeManager";

export function SaveSharePanel() {
  const { t } = useTranslation();
  const [open, setOpen] = useState(false);
  return (
    <Stack gap="xs" data-testid="save-share">
      <Button size="xs" variant="subtle" justify="flex-start" style={{ alignSelf: "flex-start" }}
        aria-expanded={open} onClick={() => setOpen((o) => !o)}>
        {open ? "▾" : "▸"} {t("studio.save_share")}
      </Button>
      {open && (
        <Stack gap="sm" pl="sm">
          <RecipeSaver />
          <SchemeManager />
          <RecipeManager />
        </Stack>
      )}
    </Stack>
  );
}
```

`RecipeManager.tsx` — remove `exportCollection`, `importCollection` from the client import, the `useCatalogStore` import, `collectionRef`, `setOwnedFromImport`, `onCollection`, and the two collection `<Button>`s plus the `data-kind="collection"` `<input>`. What remains: the `run` helper, `onRecipes`, the recipes export/import buttons + hidden recipes input, and the ok/error messages.

`RecipeSaver.tsx` — remove `interface Props`, change the signature to `export function RecipeSaver() {`, and in `handleSave` delete the `onSaved();` call. (`RecipeLoader` now only mounts when "a saved recipe" is opened and fetches the list on mount, so no refresh hook is needed.)

- [ ] **Step 4: Run tests to verify they pass**

Run: `npx vitest run src/components/colour`
Expected: PASS except possibly `RecipeFooter.test.tsx`, which mocks `./RecipeSaver` and still type-checks at runtime; if it fails because `RecipeFooter` passes `onSaved`, leave it — Task 8 deletes it. Note the failure in the commit message if so.

- [ ] **Step 5: Commit**

```bash
git add web/src/components/colour
git commit -m "feat(web): collapsed Save & share panel; Studio no longer imports/exports the collection"
```

---

### Task 8: Assemble `StudioPanel`, delete old components and keys, full verification

**Files:**
- Modify: `web/src/components/StudioPanel.tsx`, `web/src/components/StudioPanel.test.tsx`, `web/src/i18n/locales/en.json`, `web/src/i18n/locales/es.json`
- Delete: `web/src/components/RegionHeader.tsx`, `web/src/components/RegionHeader.test.tsx`, `web/src/components/colour/RecipeFooter.tsx`, `web/src/components/colour/RecipeFooter.test.tsx`, `web/src/components/BandControl.tsx`

**Interfaces:**
- Consumes: `RegionTable` (Task 3, `step-regions`), `GeneratePanel` (Task 4, `step-scheme`), `BandEditor` (Tasks 5–6, `step-layers`), `SaveSharePanel` (Task 7, `save-share`).

- [ ] **Step 1: Write the failing test** — append inside the `describe` in `StudioPanel.test.tsx`:

```tsx
  it("shows the steps in order: regions → colour scheme → layers → save & share", () => {
    render(<MantineProvider><StudioPanel onGoToPaint={() => {}} /></MantineProvider>);
    const order = ["step-regions", "step-scheme", "step-layers", "save-share"].map((id) => screen.getByTestId(id));
    for (let i = 1; i < order.length; i++) {
      expect(order[i - 1].compareDocumentPosition(order[i]) & Node.DOCUMENT_POSITION_FOLLOWING).toBeTruthy();
    }
  });
```

- [ ] **Step 2: Run test to verify it fails**

Run: `npx vitest run src/components/StudioPanel.test.tsx`
Expected: FAIL — `step-regions` / `save-share` not found.

- [ ] **Step 3: Implement**

In `StudioPanel.tsx` replace the imports of `RegionHeader`, `SchemeManager`, `RecipeManager` with:

```tsx
import { RegionTable } from "./RegionTable";
import { SaveSharePanel } from "./colour/SaveSharePanel";
```

and the editor stack with:

```tsx
      <Stack data-testid="studio-editor" style={{ flex: 1 }} gap="xl">
        <RegionTable />
        <GeneratePanel />
        <BandEditor />
        <SaveSharePanel />
      </Stack>
```

Delete the files:

```bash
git rm web/src/components/RegionHeader.tsx web/src/components/RegionHeader.test.tsx \
       web/src/components/colour/RecipeFooter.tsx web/src/components/colour/RecipeFooter.test.tsx \
       web/src/components/BandControl.tsx
```

Remove these now-unused keys from **both** `en.json` and `es.json`: `colour.generate_whole_mini`, `colour.anchor_region`, `colour.ramp_editor`, `colour.band_editor`, `colour.band_count`, `colour.load_recipe`, `recipes.collection_export`, `recipes.collection_import`, `region.editing`, `region.manage`. Before deleting each, confirm it has no remaining use:

Run (from repo root): `git grep -n -E "colour\.(generate_whole_mini|anchor_region|ramp_editor|band_editor|band_count|load_recipe)|recipes\.collection_|region\.(editing|manage)\b" -- web/src ':!web/src/i18n/locales'`
Expected: only test files asserting their *absence* (`RecipeManager.test.tsx`, `GeneratePanel.test.tsx`); no component uses. Keep `region.select` (used by RegionTable header and the step 3 picker).

- [ ] **Step 4: Full verification**

Run: `npx vitest run`
Expected: all test files PASS (previous count was 170 before this branch; it should now be higher — note the new number).

Run: `npx tsc -b`
Expected: no errors (catches leftover imports of deleted components and unused-symbol errors).

Run: `npm run lint`
Expected: no new errors.

- [ ] **Step 5: Commit and push**

```bash
git add -A web/src
git commit -m "feat(web): Studio as numbered steps; remove RegionHeader, RecipeFooter, BandControl and dead keys"
git push
```

Hand over to the user for: `pytest` (backend unchanged, sanity only) and a browser smoke in EN and ES — check (1) row click and the step 3 picker stay in sync, (2) ★ moves and Suggest colours anchors on it, (3) edge toggles/slider change the preview, (4) Save & share opens and has no collection buttons, (5) no English left in the ES Studio.
