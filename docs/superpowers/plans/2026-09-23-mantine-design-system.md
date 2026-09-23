# Mantine Design System Integration

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace all raw HTML/inline-style UI with Mantine v7 components, establishing a durable dark-theme design system that makes the app presentable.

**Architecture:** Install `@mantine/core` and wrap the root with `MantineProvider` (dark, violet primary). Then replace, component by component, every raw `<button>`, `<input>`, `<select>`, and `style={{...}}` with Mantine equivalents. Behavior, Zustand wiring, API calls, and all i18n keys are unchanged — this is a pure visual layer change.

**Tech Stack:** Mantine v7 (`@mantine/core`, `@mantine/hooks`), React 19, TypeScript, Vite — Zustand, react-konva, react-i18next unchanged.

**Spec:** `docs/superpowers/specs/2026-09-22-react-fastapi-migration-design.md` §11 (post-migration follow-ups)

## Global Constraints

- **Never change logic** — state wiring, API calls, store selectors, event handlers: unchanged.
- **Dark mode only** — `defaultColorScheme="dark"` on MantineProvider; no toggle.
- **Primary color is violet** — matches existing `--accent: #aa3bff`; use Mantine's built-in `"violet"`.
- **No icons library** — use text/emoji for button labels; icons are a future UX pass.
- **No Tailwind** — Mantine CSS variables and `style` props handle all remaining one-off overrides.
- **Keep all i18n keys intact** — only the surrounding JSX changes, never the `t("key")` calls.
- **Mantine version** — `@mantine/core@7 @mantine/hooks@7` (add `--legacy-peer-deps` if peer dep errors appear with React 19).
- **Run `npm test` after every task** and fix any test queries broken by DOM changes (Mantine restructures some inputs).

---

### Task 1: Install Mantine + configure provider

**Files:**
- Modify: `web/package.json` (via npm install)
- Create: `web/src/theme.ts`
- Modify: `web/src/main.tsx`
- Modify: `web/src/index.css`

**Interfaces:**
- Produces: `theme` export from `web/src/theme.ts` — imported by `main.tsx`; available to all later tasks.

- [ ] **Step 1: Install**

```bash
cd web
npm install @mantine/core@7 @mantine/hooks@7 --legacy-peer-deps
```

If no `ERESOLVE` errors appear, omit `--legacy-peer-deps`.

- [ ] **Step 2: Create `web/src/theme.ts`**

```ts
import { createTheme } from "@mantine/core";

export const theme = createTheme({
  primaryColor: "violet",
  fontFamily: "system-ui, 'Segoe UI', Roboto, sans-serif",
  headings: { fontFamily: "system-ui, 'Segoe UI', Roboto, sans-serif" },
});
```

- [ ] **Step 3: Rewrite `web/src/main.tsx`**

```tsx
import "./i18n/index";
import { StrictMode } from "react";
import { createRoot } from "react-dom/client";
import { MantineProvider, ColorSchemeScript } from "@mantine/core";
import "@mantine/core/styles.css";
import "./index.css";
import App from "./App.tsx";
import { theme } from "./theme.ts";

createRoot(document.getElementById("root")!).render(
  <StrictMode>
    <ColorSchemeScript defaultColorScheme="dark" />
    <MantineProvider theme={theme} defaultColorScheme="dark">
      <App />
    </MantineProvider>
  </StrictMode>
);
```

- [ ] **Step 4: Simplify `web/src/index.css`**

Replace the entire file — Mantine's CSS variables supersede the custom ones:

```css
body {
  margin: 0;
}

#root {
  min-height: 100svh;
  box-sizing: border-box;
}
```

- [ ] **Step 5: Verify**

```bash
npm run build && npm test
```

Expected: build clean, all existing tests pass. MantineProvider adds DOM wrappers that are transparent to @testing-library role queries.

- [ ] **Step 6: Commit**

```bash
git add web/package.json web/package-lock.json web/src/main.tsx web/src/index.css web/src/theme.ts
git commit -m "feat: install Mantine v7 and configure dark-theme provider"
```

---

### Task 2: App shell — header + main tabs

**Files:**
- Modify: `web/src/App.tsx`
- Modify: `web/src/components/LanguageSelector.tsx`

**Interfaces:**
- Consumes: MantineProvider from Task 1.
- Produces: Mantine `Tabs` as the main navigation; `Container` as the page root.

- [ ] **Step 1: Rewrite `App.tsx`**

Logic (hooks, state, effects) is unchanged. Replace only the return value and add Mantine imports:

```tsx
import { useState, useEffect } from "react";
import { useTranslation } from "react-i18next";
import { Container, Group, Stack, Tabs, Title } from "@mantine/core";
import { PhotoUploader } from "./components/PhotoUploader";
import { PreviewImage } from "./components/PreviewImage";
import { RegionSelector } from "./components/RegionSelector";
import { AngleBar } from "./components/AngleBar";
import { RightPanel } from "./components/RightPanel";
import { PaintTab } from "./components/PaintTab";
import { PaintsTab } from "./components/PaintsTab";
import { AnglesTab } from "./components/AnglesTab";
import { useAnalyze } from "./hooks/useAnalyze";
import { useProjectStore, activeAngleOf } from "./store/projectStore";
import { useCatalogStore } from "./store/catalogStore";
import { ProjectLibrary } from "./components/ProjectLibrary";
import { LanguageSelector } from "./components/LanguageSelector";

type MainTab = "studio" | "paint" | "paints" | "angles";

export default function App() {
  const { t } = useTranslation();
  useAnalyze();
  const hasAngle = useProjectStore((s) => s.angles.length > 0);
  const resultToken = useProjectStore((s) => activeAngleOf(s)?.resultToken);
  const fetchCatalog = useCatalogStore((s) => s.fetch);
  const [tab, setTab] = useState<MainTab>("studio");

  useEffect(() => { if (hasAngle) fetchCatalog(); }, [hasAngle, fetchCatalog]);

  const loadCollection = useCatalogStore((s) => s.loadCollection);
  const catalogStatus = useCatalogStore((s) => s.status);
  useEffect(() => { if (catalogStatus === "ready") loadCollection(); }, [catalogStatus, loadCollection]);

  return (
    <Container size="xl" p="md">
      <Group justify="space-between" mb="xs">
        <Title order={3}>Mini Highlight Advisor</Title>
        <LanguageSelector />
      </Group>

      <ProjectLibrary />

      {!hasAngle ? (
        <PhotoUploader />
      ) : (
        <Tabs value={tab} onChange={(v) => setTab((v as MainTab) ?? "studio")}>
          <AngleBar />
          <Tabs.List mb="md">
            <Tabs.Tab value="studio">{t("tabs.studio")}</Tabs.Tab>
            <Tabs.Tab value="paint" disabled={!resultToken}>{t("tabs.paint")}</Tabs.Tab>
            <Tabs.Tab value="paints">{t("tabs.paints")}</Tabs.Tab>
            <Tabs.Tab value="angles">{t("tabs.angles")}</Tabs.Tab>
          </Tabs.List>

          <Tabs.Panel value="studio">
            <Group align="flex-start" gap="xl" wrap="nowrap">
              <PreviewImage />
              <Stack style={{ flex: 1 }}>
                <RegionSelector />
                <RightPanel />
              </Stack>
            </Group>
          </Tabs.Panel>
          <Tabs.Panel value="paint"><PaintTab /></Tabs.Panel>
          <Tabs.Panel value="paints"><PaintsTab /></Tabs.Panel>
          <Tabs.Panel value="angles"><AnglesTab /></Tabs.Panel>
        </Tabs>
      )}
    </Container>
  );
}
```

- [ ] **Step 2: Rewrite `LanguageSelector.tsx`**

```tsx
import { useTranslation } from "react-i18next";
import { SegmentedControl } from "@mantine/core";

export function LanguageSelector() {
  const { i18n } = useTranslation();
  return (
    <SegmentedControl
      size="xs"
      data={[{ value: "en", label: "EN" }, { value: "es", label: "ES" }]}
      value={i18n.language}
      onChange={(v) => i18n.changeLanguage(v)}
    />
  );
}
```

- [ ] **Step 3: Run tests**

```bash
npm test
```

No dedicated test file for `App.tsx` or `LanguageSelector`. Verify build: `npm run build`.

- [ ] **Step 4: Commit**

```bash
git add web/src/App.tsx web/src/components/LanguageSelector.tsx
git commit -m "feat(mantine): App shell — Container, Tabs nav, SegmentedControl language selector"
```

---

### Task 3: PhotoUploader + ProjectLibrary

**Files:**
- Modify: `web/src/components/PhotoUploader.tsx`
- Modify: `web/src/components/ProjectLibrary.tsx`

- [ ] **Step 1: Rewrite `PhotoUploader.tsx`**

```tsx
import { useEffect, useRef, useState } from "react";
import { Button, Group, Stack, Text } from "@mantine/core";
import { listSamplePhotos, samplePhotoBlob, uploadPhoto } from "../api/client";
import type { SamplePhoto } from "../api/types";
import { useProjectStore } from "../store/projectStore";

export function PhotoUploader() {
  const initFromPhoto = useProjectStore((s) => s.initFromPhoto);
  const setError = useProjectStore((s) => s.setError);
  const [samples, setSamples] = useState<SamplePhoto[]>([]);
  const fileRef = useRef<HTMLInputElement>(null);

  useEffect(() => { listSamplePhotos().then(setSamples).catch(() => setSamples([])); }, []);

  async function handleBlob(blob: Blob, name: string) {
    try { initFromPhoto(await uploadPhoto(blob, name)); }
    catch (e) { setError(e instanceof Error ? e.message : String(e)); }
  }

  return (
    <Stack gap="sm" mt="md">
      <Button variant="default" onClick={() => fileRef.current?.click()}>
        Upload photo
      </Button>
      <input
        ref={fileRef}
        type="file"
        accept="image/png,image/jpeg"
        style={{ display: "none" }}
        onChange={(e) => { const f = e.target.files?.[0]; if (f) handleBlob(f, f.name); }}
      />
      {samples.length > 0 && (
        <>
          <Text size="sm" c="dimmed">Or start from a sample:</Text>
          <Group gap="xs">
            {samples.map((s) => (
              <Button key={s.id} variant="subtle" size="xs"
                onClick={async () => {
                  try { handleBlob(await samplePhotoBlob(s.id), `${s.id}.png`); }
                  catch (e) { setError(e instanceof Error ? e.message : String(e)); }
                }}>
                {s.name}
              </Button>
            ))}
          </Group>
        </>
      )}
    </Stack>
  );
}
```

- [ ] **Step 2: Run PhotoUploader tests**

```bash
npm test -- --reporter=verbose PhotoUploader
```

The existing test triggers file upload via an `<input type="file">`. The hidden input is still present with the same accept attribute — the test should pass unchanged. Verify.

- [ ] **Step 3: Rewrite `ProjectLibrary.tsx`**

All handlers unchanged. Only JSX:

```tsx
import { useEffect, useRef, useState } from "react";
import { useTranslation } from "react-i18next";
import { Box, Button, Collapse, Group, Stack, Text, TextInput, UnstyledButton } from "@mantine/core";
import {
  deleteProjectApi, downloadProjectBlob, listProjects,
  loadProjectApi, saveProjectApi, uploadProjectBlob,
} from "../api/client";
import { useProjectStore } from "../store/projectStore";
import type { ProjectMeta } from "../api/types";

export function ProjectLibrary() {
  const { t } = useTranslation();
  const [open, setOpen] = useState(false);
  const [projects, setProjects] = useState<ProjectMeta[]>([]);
  const [inputName, setInputName] = useState("");
  const [busy, setBusy] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const fileRef = useRef<HTMLInputElement>(null);

  const projectName = useProjectStore((s) => s.projectName);
  const slug = useProjectStore((s) => s.slug);
  const activeAngle = useProjectStore((s) => s.activeAngle);
  const angles = useProjectStore((s) => s.angles);
  const initFromProject = useProjectStore((s) => s.initFromProject);
  const setProjectMeta = useProjectStore((s) => s.setProjectMeta);
  const hasAngles = angles.length > 0;

  useEffect(() => { if (projectName && !inputName) setInputName(projectName); }, [projectName]);
  useEffect(() => { if (!open) return; listProjects().then(setProjects).catch(() => setProjects([])); }, [open]);

  async function handleSave() {
    const name = inputName.trim();
    if (!name || !hasAngles) return;
    setBusy("save"); setError(null);
    try {
      const res = await saveProjectApi(name, activeAngle, angles);
      setProjectMeta(res.name, res.slug);
      setProjects(await listProjects());
    } catch (e) { setError(e instanceof Error ? e.message : "save failed"); }
    finally { setBusy(null); }
  }

  async function handleLoad(projectSlug: string) {
    setBusy(`load:${projectSlug}`); setError(null);
    try { initFromProject(await loadProjectApi(projectSlug)); }
    catch (e) { setError(e instanceof Error ? e.message : "load failed"); }
    finally { setBusy(null); }
  }

  async function handleDelete(projectSlug: string, name: string) {
    if (!window.confirm(t("projects.react_confirm_delete", { name }))) return;
    setBusy(`delete:${projectSlug}`); setError(null);
    try { await deleteProjectApi(projectSlug); setProjects((prev) => prev.filter((p) => p.slug !== projectSlug)); }
    catch (e) { setError(e instanceof Error ? e.message : "delete failed"); }
    finally { setBusy(null); }
  }

  async function handleDownload(projectSlug: string) {
    setBusy(`download:${projectSlug}`); setError(null);
    try { await downloadProjectBlob(projectSlug); }
    catch (e) { setError(e instanceof Error ? e.message : "download failed"); }
    finally { setBusy(null); }
  }

  async function handleUpload(e: React.ChangeEvent<HTMLInputElement>) {
    const file = e.target.files?.[0]; if (!file) return;
    setBusy("upload"); setError(null);
    try { initFromProject(await uploadProjectBlob(file)); setProjects(await listProjects()); }
    catch (e) { setError(e instanceof Error ? e.message : "upload failed"); }
    finally { setBusy(null); if (fileRef.current) fileRef.current.value = ""; }
  }

  const toggleLabel = `${open ? "▼" : "▶"} ${t("projects.react_toggle")}${projectName ? ` — ${projectName}` : ""}`;

  return (
    <Box mb="md" pb={open ? "sm" : 0} style={{ borderBottom: "1px solid var(--mantine-color-dark-4)" }}>
      <UnstyledButton onClick={() => setOpen((v) => !v)} c="dimmed" fz="sm">
        {toggleLabel}
      </UnstyledButton>

      <Collapse in={open}>
        <Stack gap="xs" mt="sm">
          {error && <Text c="red" size="sm">{error}</Text>}
          <Group gap="xs" wrap="wrap">
            <TextInput
              value={inputName}
              onChange={(e) => setInputName(e.target.value)}
              onKeyDown={(e) => { if (e.key === "Enter") handleSave(); }}
              placeholder={t("projects.react_name_placeholder")}
              size="xs"
              style={{ flex: "1 1 160px" }}
            />
            <Button size="xs" onClick={handleSave}
              disabled={!inputName.trim() || !hasAngles} loading={busy === "save"}>
              {t("projects.react_save")}
            </Button>
            <Button size="xs" variant="default" onClick={() => fileRef.current?.click()}
              loading={busy === "upload"}>
              {t("projects.react_import")}
            </Button>
            <input ref={fileRef} type="file" accept=".json" style={{ display: "none" }} onChange={handleUpload} />
          </Group>
          {projects.length === 0 ? (
            <Text c="dimmed" size="sm">{t("projects.react_empty")}</Text>
          ) : (
            <Stack gap={4}>
              {projects.map((p) => (
                <Group key={p.slug} gap="xs" wrap="nowrap">
                  <Text size="sm" c={p.slug === slug ? undefined : "dimmed"} style={{ flex: 1 }}>{p.name}</Text>
                  <Text size="xs" c="dimmed">{new Date(p.updated_at).toLocaleDateString()}</Text>
                  <Button size="xs" variant="subtle" loading={busy === `load:${p.slug}`} onClick={() => handleLoad(p.slug)}>
                    {t("projects.react_load")}
                  </Button>
                  <Button size="xs" variant="subtle" loading={busy === `download:${p.slug}`} onClick={() => handleDownload(p.slug)}>
                    {t("projects.react_export")}
                  </Button>
                  <Button size="xs" variant="subtle" color="red"
                    disabled={busy?.startsWith("delete:") ?? false}
                    onClick={() => handleDelete(p.slug, p.name)}>
                    {t("projects.react_delete")}
                  </Button>
                </Group>
              ))}
            </Stack>
          )}
        </Stack>
      </Collapse>
    </Box>
  );
}
```

- [ ] **Step 4: Run ProjectLibrary tests**

```bash
npm test -- --reporter=verbose ProjectLibrary
```

Mantine's `Button` and `UnstyledButton` both render `<button>` — `getByRole("button")` queries still work. Verify.

- [ ] **Step 5: Commit**

```bash
git add web/src/components/PhotoUploader.tsx web/src/components/ProjectLibrary.tsx
git commit -m "feat(mantine): migrate PhotoUploader and ProjectLibrary"
```

---

### Task 4: AngleBar + RegionSelector

**Files:**
- Modify: `web/src/components/AngleBar.tsx`
- Modify: `web/src/components/RegionSelector.tsx`

- [ ] **Step 1: Rewrite `AngleBar.tsx`**

```tsx
import { useRef } from "react";
import { ActionIcon, Button, Group, Stack, TextInput } from "@mantine/core";
import { useProjectStore } from "../store/projectStore";
import { uploadPhoto } from "../api/client";

export function AngleBar() {
  const angles = useProjectStore((s) => s.angles);
  const active = useProjectStore((s) => s.activeAngle);
  const addAngle = useProjectStore((s) => s.addAngle);
  const switchAngle = useProjectStore((s) => s.switchAngle);
  const renameAngle = useProjectStore((s) => s.renameAngle);
  const removeAngle = useProjectStore((s) => s.removeAngle);
  const setError = useProjectStore((s) => s.setError);
  const fileRef = useRef<HTMLInputElement>(null);

  if (angles.length === 0) return null;

  async function onAdd(file: File) {
    try { addAngle(await uploadPhoto(file, file.name)); }
    catch (e) { setError(e instanceof Error ? e.message : String(e)); }
  }

  return (
    <Stack gap="xs" mb="sm">
      <Group gap="xs" wrap="wrap">
        {angles.map((a, i) => (
          <Button key={a.id} size="xs"
            variant={i === active ? "filled" : "default"}
            onClick={() => switchAngle(i)}>
            {a.label}
          </Button>
        ))}
        <Button size="xs" variant="subtle" onClick={() => fileRef.current?.click()}>+ angle</Button>
        <input ref={fileRef} type="file" accept="image/png,image/jpeg" style={{ display: "none" }}
          onChange={(e) => { const f = e.target.files?.[0]; if (f) onAdd(f); }} />
      </Group>
      <Group gap="xs">
        <TextInput
          size="xs"
          value={angles[active].label}
          onChange={(e) => renameAngle(active, e.target.value)}
          aria-label="Rename angle"
          style={{ maxWidth: 200 }}
        />
        <ActionIcon size="sm" variant="subtle" color="red"
          disabled={angles.length === 1}
          onClick={() => removeAngle(active)}
          aria-label="Remove angle">
          ✕
        </ActionIcon>
      </Group>
    </Stack>
  );
}
```

- [ ] **Step 2: Run AngleBar tests**

```bash
npm test -- --reporter=verbose AngleBar
```

The test queries buttons by text label. Check that "Remove angle" is now found via `aria-label` — update the test query to `getByRole("button", { name: "Remove angle" })` if needed (the `aria-label` is picked up by Testing Library's accessible name computation).

- [ ] **Step 3: Rewrite `RegionSelector.tsx`**

```tsx
import { Checkbox, Paper, Radio, Stack, Text } from "@mantine/core";
import { useProjectStore, activeBookOf } from "../store/projectStore";
import { regionLabel } from "../lib/geometry";

export function RegionSelector() {
  const book = useProjectStore(activeBookOf);
  const setSelected = useProjectStore((s) => s.setSelected);
  const toggleBlank = useProjectStore((s) => s.toggleBlank);
  if (!book) return null;
  const names = ["Whole mini", ...book.drawn.map((r) => r.name)];

  return (
    <Paper withBorder p="xs" mb="xs">
      <Text size="xs" fw={500} mb={4}>Region</Text>
      <Radio.Group value={String(book.selected)} onChange={(v) => setSelected(Number(v))}>
        <Stack gap={4}>
          {names.map((name, g) => (
            <Stack key={g} gap={2}>
              <Radio value={String(g)} label={regionLabel(g, name)} size="xs" />
              {g >= 1 && (
                <Checkbox size="xs" label="visible" ml="md"
                  checked={!book.drawn[g - 1].blank}
                  onChange={() => toggleBlank(g)} />
              )}
            </Stack>
          ))}
        </Stack>
      </Radio.Group>
    </Paper>
  );
}
```

- [ ] **Step 4: Run RegionSelector tests**

```bash
npm test -- --reporter=verbose RegionSelector
```

Mantine's `Radio` renders `<input type="radio">` — `getByRole("radio")` queries work unchanged. `Checkbox` renders `<input type="checkbox">` — same. Verify.

- [ ] **Step 5: Commit**

```bash
git add web/src/components/AngleBar.tsx web/src/components/RegionSelector.tsx
git commit -m "feat(mantine): migrate AngleBar and RegionSelector"
```

---

### Task 5: RightPanel + ManagePanel + TechniquePanel

**Files:**
- Modify: `web/src/components/RightPanel.tsx`
- Modify: `web/src/components/ManagePanel.tsx`
- Modify: `web/src/components/TechniquePanel.tsx`

- [ ] **Step 1: Rewrite `RightPanel.tsx`**

```tsx
import { useState } from "react";
import { useTranslation } from "react-i18next";
import { Tabs } from "@mantine/core";
import { ManagePanel } from "./ManagePanel";
import { ColourPanel } from "./colour/ColourPanel";
import { TechniquePanel } from "./TechniquePanel";

type Tab = "manage" | "colour" | "technique";

export function RightPanel() {
  const { t } = useTranslation();
  const [active, setActive] = useState<Tab>("manage");

  return (
    <Tabs value={active} onChange={(v) => setActive((v as Tab) ?? "manage")}>
      <Tabs.List mb="sm">
        <Tabs.Tab value="manage">{t("tabs.manage")}</Tabs.Tab>
        <Tabs.Tab value="colour">{t("tabs.colour")}</Tabs.Tab>
        <Tabs.Tab value="technique">{t("tabs.technique")}</Tabs.Tab>
      </Tabs.List>
      <Tabs.Panel value="manage"><ManagePanel /></Tabs.Panel>
      <Tabs.Panel value="colour"><ColourPanel /></Tabs.Panel>
      <Tabs.Panel value="technique"><TechniquePanel /></Tabs.Panel>
    </Tabs>
  );
}
```

- [ ] **Step 2: Rewrite `ManagePanel.tsx`**

```tsx
import { useState } from "react";
import { ActionIcon, Button, Group, Stack, Text, TextInput } from "@mantine/core";
import { useProjectStore, activeBookOf } from "../store/projectStore";
import { RegionCanvas } from "./RegionCanvas";

export function ManagePanel() {
  const book = useProjectStore(activeBookOf);
  const addRegion = useProjectStore((s) => s.addRegion);
  const removeRegion = useProjectStore((s) => s.removeRegion);
  const renameRegion = useProjectStore((s) => s.renameRegion);
  const [drawing, setDrawing] = useState(false);
  const [draftRings, setDraftRings] = useState<number[][][]>([]);
  const [name, setName] = useState("");

  if (!book) return null;
  const sel = book.selected;
  const defaultName = `region ${book.drawn.length + 1}`;

  function commit() {
    if (draftRings.length === 0) return;
    addRegion(draftRings, name.trim() || defaultName);
    setDrawing(false); setDraftRings([]); setName("");
  }
  function cancel() { setDrawing(false); setDraftRings([]); setName(""); }

  return (
    <Stack gap="xs">
      <RegionCanvas drawing={drawing} draftRings={draftRings} onDraftChange={setDraftRings} />
      {!drawing ? (
        <Button size="xs" variant="default" onClick={() => setDrawing(true)}>Draw region</Button>
      ) : (
        <Group gap="xs" align="center">
          <TextInput size="xs" placeholder={defaultName} value={name}
            onChange={(e) => setName(e.target.value)} style={{ flex: 1 }} />
          <Button size="xs" onClick={commit}>Add region</Button>
          <Button size="xs" variant="subtle" onClick={cancel}>Cancel</Button>
          {draftRings.length > 0 && (
            <Text size="xs" c="dimmed">{draftRings.length} stroke(s)</Text>
          )}
        </Group>
      )}
      {!drawing && sel >= 1 && (
        <Group gap="xs">
          <TextInput size="xs" value={book.drawn[sel - 1].name}
            onChange={(e) => renameRegion(sel, e.target.value)} style={{ flex: 1 }} />
          <ActionIcon size="sm" variant="subtle" color="red"
            onClick={() => removeRegion(sel)} aria-label="Delete region">✕</ActionIcon>
        </Group>
      )}
    </Stack>
  );
}
```

- [ ] **Step 3: Rewrite `TechniquePanel.tsx`**

```tsx
import { useTranslation } from "react-i18next";
import { NativeSelect, Stack } from "@mantine/core";
import { useProjectStore, activeBookOf } from "../store/projectStore";

export function TechniquePanel() {
  const { t } = useTranslation();
  const selected = useProjectStore((s) => activeBookOf(s)?.selected ?? 0);
  const material = useProjectStore((s) => {
    const b = activeBookOf(s);
    if (!b) return "matte";
    return selected === 0 ? b.whole.material : (b.drawn[selected - 1]?.material ?? "matte");
  });
  const setMaterial = useProjectStore((s) => s.setMaterial);

  return (
    <Stack p="xs" gap="sm">
      <NativeSelect
        label={t("technique.material")}
        size="xs"
        value={material}
        onChange={(e) => setMaterial(selected, e.target.value)}
        data={[
          { value: "matte", label: t("technique.matte") },
          { value: "metallic", label: t("technique.metallic") },
        ]}
      />
    </Stack>
  );
}
```

- [ ] **Step 4: Run RightPanel + ManagePanel tests**

```bash
npm test -- --reporter=verbose RightPanel ManagePanel
```

RightPanel test uses `getByRole("tab")` and `getByRole("tabpanel")` — Mantine Tabs renders both correctly. ManagePanel test queries buttons by text — new JSX preserves the same text content. Verify.

- [ ] **Step 5: Commit**

```bash
git add web/src/components/RightPanel.tsx web/src/components/ManagePanel.tsx web/src/components/TechniquePanel.tsx
git commit -m "feat(mantine): migrate RightPanel, ManagePanel, TechniquePanel"
```

---

### Task 6: BandSlot + CoverageEditor

**Files:**
- Modify: `web/src/components/colour/BandSlot.tsx`
- Modify: `web/src/components/colour/CoverageEditor.tsx`

**Key API differences:**
- `ColorInput.onChange(hex: string)` — receives the hex string directly, not an event.
- `Slider.onChange(val: number)` — receives a number (0–100), not `e.target.value`. Adapt `handleSlider` accordingly.
- Mantine `Slider` has no `<input type="range">` in the DOM — tests that fire `change` on a range input will break. Use `fireEvent` on the thumb div or mock the `onChange` prop directly in tests.

- [ ] **Step 1: Rewrite `BandSlot.tsx`**

```tsx
import { useState, useEffect, useRef } from "react";
import { useTranslation } from "react-i18next";
import { ActionIcon, Box, ColorInput, ColorSwatch, Group, NativeSelect, Text } from "@mantine/core";
import { useProjectStore } from "../../store/projectStore";
import { useCatalogStore } from "../../store/catalogStore";
import { matchPaint, generateRamp } from "../../api/client";
import type { PaintColor, MatchResult } from "../../api/types";

interface BandSlotProps { g: number; i: number; paint: PaintColor; finish: string; n: number; palette: PaintColor[]; }

function matchPhrase(result: MatchResult): string {
  if (result.tier === "exact") return `✓ ${result.name ?? ""}`;
  if (result.tier === "close") return `≈ ${result.name ?? ""}`;
  if (result.tier === "mix") return result.phrase;
  return `Buy: ${result.name ?? ""}`;
}

export function BandSlot({ g, i, paint, finish, n, palette }: BandSlotProps) {
  const { t } = useTranslation();
  const catalogPaints = useCatalogStore((s) => s.paints);
  const setPaletteSlot = useProjectStore((s) => s.setPaletteSlot);
  const setHexSlot = useProjectStore((s) => s.setHexSlot);
  const setBandCount = useProjectStore((s) => s.setBandCount);
  const isCustom = !paint.code;
  const [matchResult, setMatchResult] = useState<MatchResult | null>(null);
  const debounceRef = useRef<ReturnType<typeof setTimeout> | null>(null);

  useEffect(() => {
    if (!isCustom) { setMatchResult(null); return; }
    if (debounceRef.current) clearTimeout(debounceRef.current);
    debounceRef.current = setTimeout(async () => {
      try { setMatchResult(await matchPaint({ hex: paint.hex, finish, owned_codes: [] })); }
      catch { /* ignore */ }
    }, 400);
    return () => { if (debounceRef.current) clearTimeout(debounceRef.current); };
  }, [paint.hex, isCustom, finish]);

  const handleCatalogChange = (code: string) => {
    if (code === "__custom__") { setHexSlot(g, i, paint.hex); }
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
    <Box py={4} style={{ borderBottom: "1px solid var(--mantine-color-dark-4)" }}>
      <Group gap={4} align="center" wrap="nowrap">
        <ColorSwatch color={paint.hex} size={22} style={{ flexShrink: 0 }} />
        {isCustom ? (
          <ColorInput value={paint.hex} onChange={(hex) => setHexSlot(g, i, hex)}
            format="hex" size="xs" style={{ flex: 1 }} withEyeDropper={false} />
        ) : (
          <NativeSelect value={paint.code} onChange={(e) => handleCatalogChange(e.target.value)}
            size="xs" style={{ flex: 1 }}>
            {catalogPaints.map((p) => (
              <option key={p.code} value={p.code}>{p.code} — {p.name}</option>
            ))}
            <option value="__custom__">{t("colour.custom")}</option>
          </NativeSelect>
        )}
        {i > 0 && i < n - 1 && (
          <ActionIcon size="sm" variant="subtle" onClick={handleBlend} title={t("colour.blend")}>↕</ActionIcon>
        )}
        <ActionIcon size="sm" variant="subtle" color="red" disabled={n <= 3}
          onClick={() => { if (n > 3) setBandCount(n - 1); }} title={t("colour.delete_band")}>✕</ActionIcon>
        <ActionIcon size="sm" variant="subtle" disabled={n >= 7}
          onClick={() => { if (n < 7) { setBandCount(n + 1); setHexSlot(g, n, palette[n - 1]?.hex ?? "#808080"); } }}
          title={t("colour.add_band")}>＋</ActionIcon>
      </Group>
      {isCustom && matchResult && (
        <Text size="xs" c="dimmed" ml={28}>{matchPhrase(matchResult)}</Text>
      )}
    </Box>
  );
}
```

- [ ] **Step 2: Run BandSlot tests**

```bash
npm test -- --reporter=verbose BandSlot
```

`ColorInput` renders an `<input type="text">` (role `textbox`) — if the test used `getByRole("textbox")` it may now match multiple inputs (the ColorInput itself has an internal text field plus the hex field). Adapt using `getByDisplayValue(paint.hex)`. `NativeSelect` renders a `<select>` (role `combobox`). Verify and fix.

- [ ] **Step 3: Rewrite `CoverageEditor.tsx`**

Note: `Slider.onChange` receives a `number`, not an event. The `handleSlider` signature changes from `(i, raw: string)` to `(i, val: number)`:

```tsx
import { useTranslation } from "react-i18next";
import { Button, Group, Slider, Stack, Text } from "@mantine/core";
import { useProjectStore } from "../../store/projectStore";

const _ROLES: Record<number, string[]> = {
  3: ["Shadow", "Base", "Highlight"],
  4: ["Shadow", "Base", "Midtone", "Highlight"],
  5: ["Shadow", "Base", "Midtone", "Highlight", "Bright Highlight"],
  6: ["Shadow", "Deep Base", "Base", "Midtone", "Highlight", "Bright Highlight"],
  7: ["Shadow", "Deep Base", "Base", "Midtone", "Upper Midtone", "Highlight", "Bright Highlight"],
};
function roleNames(n: number): string[] {
  return _ROLES[n] ?? Array.from({ length: n }, (_, i) => `Layer ${i + 1}`);
}
function defaultCoverage(n: number): number[] {
  const weights = Array.from({ length: n }, (_, i) => n - i);
  const total = weights.reduce((a, b) => a + b, 0);
  return weights.map((w) => w / total);
}

interface Props { g: number; n: number; coverage: number[]; }

export function CoverageEditor({ g: _g, n, coverage }: Props) {
  const { t } = useTranslation();
  const setCoverage = useProjectStore((s) => s.setCoverage);
  const names = roleNames(n);

  const handleSlider = (i: number, val: number) => {
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
    <Stack gap="xs" mt="xs">
      {Array.from({ length: n - 1 }, (_, i) => (
        <Group key={i} gap="xs" align="center" wrap="nowrap">
          <Text size="xs" miw={110}>{names[i]}</Text>
          <Slider value={Math.round((coverage[i] ?? 0) * 100)}
            onChange={(val) => handleSlider(i, val)}
            min={0} max={100} step={1} size="sm" style={{ flex: 1 }} />
          <Text size="xs" miw={32} ta="right">{Math.round((coverage[i] ?? 0) * 100)}%</Text>
        </Group>
      ))}
      <Text size="xs" c="dimmed">{names[n - 1]}: {Math.round((coverage[n - 1] ?? 0) * 100)}% (auto)</Text>
      <Button variant="subtle" size="xs" onClick={() => setCoverage(defaultCoverage(n))}>
        {t("colour.reset_coverage")}
      </Button>
    </Stack>
  );
}
```

- [ ] **Step 4: Run CoverageEditor tests**

```bash
npm test -- --reporter=verbose CoverageEditor
```

Mantine `Slider` renders a `div[role="slider"]` thumb — `getByRole("slider")` still matches. However, if any test fires `fireEvent.change` on the slider (as if it were `<input type="range">`), it will no longer trigger the handler. Fix by calling the component's `onChange` prop directly via `fireEvent` on the slider thumb using pointer events, or by mocking the prop in the test render. Verify and fix as needed.

- [ ] **Step 5: Commit**

```bash
git add web/src/components/colour/BandSlot.tsx web/src/components/colour/CoverageEditor.tsx
git commit -m "feat(mantine): migrate BandSlot (ColorInput, ActionIcon) and CoverageEditor (Slider)"
```

---

### Task 7: RampEditor + SchemeGenerator

**Files:**
- Modify: `web/src/components/colour/RampEditor.tsx`
- Modify: `web/src/components/colour/SchemeGenerator.tsx`

- [ ] **Step 1: Rewrite `RampEditor.tsx`**

```tsx
import { useState } from "react";
import { useTranslation } from "react-i18next";
import { Button, ColorInput, Group, Stack, Text } from "@mantine/core";
import { useProjectStore, activeBookOf } from "../../store/projectStore";
import { generateRamp } from "../../api/client";
import { RAMP_VARIANTS } from "../../api/types";

export function RampEditor() {
  const { t } = useTranslation();
  const book = useProjectStore((s) => activeBookOf(s));
  const setHexSlot = useProjectStore((s) => s.setHexSlot);
  const setRampState = useProjectStore((s) => s.setRampState);

  const activeRegion = book
    ? book.selected === 0 ? book.whole : book.drawn[book.selected - 1]
    : null;

  const seedHex = activeRegion?.ramp_midtone
    ?? activeRegion?.palette[Math.floor((activeRegion.palette.length) / 2)]?.hex
    ?? "#808080";

  const [midtoneHex, setMidtoneHex] = useState(seedHex);
  const [loading, setLoading] = useState<string | null>(null);

  if (!book || !activeRegion) return null;

  const g = book.selected;
  const n = activeRegion.palette.length;

  const handleVariant = async (variant: string) => {
    setLoading(variant);
    try {
      const res = await generateRamp({ midtone_hex: midtoneHex, n, variant });
      res.hexes.forEach((hex, i) => setHexSlot(g, i, hex));
      setRampState(g, midtoneHex, variant);
    } finally { setLoading(null); }
  };

  return (
    <Stack gap="xs">
      <Text size="sm" fw={500}>{t("colour.ramp_editor")}</Text>
      <Group gap="xs" align="flex-end">
        <ColorInput label={t("colour.midtone")} value={midtoneHex} onChange={setMidtoneHex}
          format="hex" size="xs" withEyeDropper={false} style={{ flex: 1 }} />
        {book.hero_hex && (
          <Button size="xs" variant="subtle" onClick={() => setMidtoneHex(book.hero_hex!)}>
            {t("colour.use_scheme_colour")}
          </Button>
        )}
      </Group>
      <Button.Group>
        {RAMP_VARIANTS.map((variant) => (
          <Button key={variant} size="xs" variant="default"
            onClick={() => handleVariant(variant)}
            loading={loading === variant} disabled={loading !== null}>
            {t(`colour.${variant}`)}
          </Button>
        ))}
      </Button.Group>
    </Stack>
  );
}
```

- [ ] **Step 2: Rewrite `SchemeGenerator.tsx`**

```tsx
import { useState, useEffect } from "react";
import { useTranslation } from "react-i18next";
import { Button, Checkbox, ColorInput, Group, NativeSelect, Stack, Table, Text } from "@mantine/core";
import { useProjectStore, activeBookOf } from "../../store/projectStore";
import { useCatalogStore } from "../../store/catalogStore";
import { generateScheme } from "../../api/client";
import { MOODS, VARIANTS, SURFACES } from "../../api/types";
import type { RegionColorSpec } from "../../api/types";

export function SchemeGenerator() {
  const { t } = useTranslation();
  const book = useProjectStore((s) => activeBookOf(s));
  const catalogPaints = useCatalogStore((s) => s.paints);
  const setPaletteAt = useProjectStore((s) => s.setPaletteAt);
  const setHeroHex = useProjectStore((s) => s.setHeroHex);
  const setMood = useProjectStore((s) => s.setMood);
  const setVariant = useProjectStore((s) => s.setVariant);
  const setSurface = useProjectStore((s) => s.setSurface);
  const setTone = useProjectStore((s) => s.setTone);

  const regionCount = book ? 1 + book.drawn.length : 1;
  const [anchorIndex, setAnchorIndex] = useState(0);
  const [heroHex, setHeroHexLocal] = useState(() => book?.hero_hex ?? "#c0392b");
  const [mood, setMoodLocal] = useState(() => book?.mood ?? "neutral");
  const [variant, setVariantLocal] = useState(() => book?.variant ?? "complementary");
  const [perRegion, setPerRegion] = useState<{ surface: string; tone: string }[]>(() =>
    Array.from({ length: regionCount }, (_, i) => ({
      surface: i === 0 ? (book?.whole.surface ?? "skin") : (book?.drawn[i - 1]?.surface ?? "skin"),
      tone: i === 0 ? (book?.whole.tone ?? "") : (book?.drawn[i - 1]?.tone ?? ""),
    }))
  );
  const [ownedOnly, setOwnedOnly] = useState(false);
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    if (!book) return;
    const needed = 1 + book.drawn.length;
    if (perRegion.length < needed) {
      setPerRegion((prev) => [...prev, ...Array.from({ length: needed - prev.length }, (_, i) => {
        const di = prev.length - 1 + i;
        return { surface: book.drawn[di]?.surface ?? "skin", tone: book.drawn[di]?.tone ?? "" };
      })]);
    }
  }, [book?.drawn.length]);

  if (!book) return null;

  const regionNames = ["Whole Mini", ...book.drawn.map((r) => r.name)];
  const ownedCodes = ownedOnly ? catalogPaints.map((p) => p.code ?? "").filter(Boolean) : [];

  const handleGenerate = async () => {
    setLoading(true);
    try {
      const anchorName = regionNames[anchorIndex] ?? "Whole Mini";
      const specs: RegionColorSpec[] = regionNames.map((name, i) => ({
        region_name: name,
        surface: perRegion[i]?.surface ?? "skin",
        tone: perRegion[i]?.tone || undefined,
        n_bands: i === 0 ? book.whole.palette.length : book.drawn[i - 1].palette.length,
        is_anchor: i === anchorIndex,
      }));
      const res = await generateScheme({ specs, anchor_name: anchorName, anchor_hex: heroHex, mood, variant, owned_codes: ownedCodes });
      regionNames.forEach((name, i) => { const pal = res.palettes[name]; if (pal) setPaletteAt(i, pal); });
      setHeroHex(heroHex); setMood(mood); setVariant(variant);
      regionNames.forEach((_, i) => { setSurface(i, perRegion[i]?.surface ?? "skin"); if (perRegion[i]?.tone) setTone(i, perRegion[i].tone); });
    } finally { setLoading(false); }
  };

  const updatePerRegion = (i: number, field: "surface" | "tone", value: string) =>
    setPerRegion((prev) => prev.map((r, j) => j === i ? { ...r, [field]: value } : r));

  return (
    <Stack gap="xs">
      <Text size="sm" fw={500}>{t("colour.scheme_generator")}</Text>
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
      <Table size="xs">
        <Table.Thead>
          <Table.Tr><Table.Th>Region</Table.Th><Table.Th>Surface</Table.Th><Table.Th>Tone</Table.Th></Table.Tr>
        </Table.Thead>
        <Table.Tbody>
          {regionNames.map((name, i) => (
            <Table.Tr key={i}>
              <Table.Td><Text size="xs">{name}</Text></Table.Td>
              <Table.Td>
                <NativeSelect size="xs" value={perRegion[i]?.surface ?? "skin"}
                  onChange={(e) => updatePerRegion(i, "surface", e.target.value)}
                  data={SURFACES.map((s) => ({ value: s, label: t(`surfaces.${s}`) }))} />
              </Table.Td>
              <Table.Td>
                <input type="text" placeholder={t("colour.tone")} value={perRegion[i]?.tone ?? ""}
                  onChange={(e) => updatePerRegion(i, "tone", e.target.value)}
                  style={{ width: 80, fontSize: 12, background: "transparent",
                    border: "1px solid var(--mantine-color-dark-4)", color: "inherit",
                    borderRadius: 4, padding: "2px 4px" }} />
              </Table.Td>
            </Table.Tr>
          ))}
        </Table.Tbody>
      </Table>
      <Group gap="sm">
        <Checkbox size="xs" label={t("colour.owned_only")} checked={ownedOnly}
          onChange={(e) => setOwnedOnly(e.currentTarget.checked)} />
        <Button size="xs" onClick={handleGenerate} loading={loading}>
          {t("colour.generate")}
        </Button>
      </Group>
    </Stack>
  );
}
```

- [ ] **Step 3: Run tests**

```bash
npm test
```

No dedicated test files for RampEditor or SchemeGenerator — verify no import errors and `npm run build` is clean.

- [ ] **Step 4: Commit**

```bash
git add web/src/components/colour/RampEditor.tsx web/src/components/colour/SchemeGenerator.tsx
git commit -m "feat(mantine): migrate RampEditor (Button.Group, ColorInput) and SchemeGenerator (Table, NativeSelect)"
```

---

### Task 8: SchemeManager + BandEditor + Recipe components

**Files:**
- Modify: `web/src/components/colour/SchemeManager.tsx`
- Modify: `web/src/components/colour/BandEditor.tsx`
- Modify: `web/src/components/colour/RecipeLoader.tsx`
- Modify: `web/src/components/colour/RecipeSaver.tsx`
- Modify: `web/src/components/colour/RecipeManager.tsx`

- [ ] **Step 1: Rewrite `SchemeManager.tsx`**

```tsx
import { useState } from "react";
import { useTranslation } from "react-i18next";
import { Button, Group, Stack, Text, TextInput } from "@mantine/core";
import { useProjectStore, activeBookOf } from "../../store/projectStore";

export function SchemeManager() {
  const { t } = useTranslation();
  const schemes = useProjectStore((s) => activeBookOf(s)?.schemes ?? []);
  const saveScheme = useProjectStore((s) => s.saveScheme);
  const applyScheme = useProjectStore((s) => s.applyScheme);
  const deleteScheme = useProjectStore((s) => s.deleteScheme);
  const [name, setName] = useState("");

  return (
    <Stack gap="xs">
      <Text size="sm" fw={500}>{t("schemes.title")}</Text>
      <Group gap="xs">
        <TextInput size="xs" value={name} placeholder={t("schemes.name_placeholder")}
          onChange={(e) => setName(e.target.value)} style={{ flex: 1 }} />
        <Button size="xs" disabled={!name.trim()}
          onClick={() => { if (name.trim()) { saveScheme(name.trim()); setName(""); } }}>
          {t("schemes.save")}
        </Button>
      </Group>
      <Stack gap={4}>
        {schemes.map((sc) => (
          <Group key={sc.id} gap="xs">
            <Text size="xs" style={{ flex: 1 }}>{sc.name}</Text>
            <Button size="xs" variant="subtle" onClick={() => applyScheme(sc.id)}>{t("schemes.apply")}</Button>
            <Button size="xs" variant="subtle" color="red" onClick={() => deleteScheme(sc.id)}>{t("schemes.delete")}</Button>
          </Group>
        ))}
      </Stack>
    </Stack>
  );
}
```

- [ ] **Step 2: Rewrite `RecipeLoader.tsx`**

```tsx
import { useState, useEffect } from "react";
import { useTranslation } from "react-i18next";
import { Button, Group, NativeSelect } from "@mantine/core";
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
  const [recipes, setRecipes] = useState<Recipe[]>([]);
  const [selected, setSelected] = useState<string>("");

  useEffect(() => {
    listRecipes().then((res) => { setRecipes(res.recipes); if (res.recipes.length > 0) setSelected(res.recipes[0].name); });
  }, []);

  if (!book) return null;

  const handleLoad = () => {
    const recipe = recipes.find((r) => r.name === selected);
    if (!recipe) return;
    setPaletteAt(book.selected, toPalette(recipe, catalogPaints));
    onRecipeLoaded();
  };

  return (
    <Group gap="xs">
      <NativeSelect size="xs" value={selected} onChange={(e) => setSelected(e.target.value)} style={{ flex: 1 }}>
        {recipes.length === 0 && <option value="">{t("colour.select_recipe")}</option>}
        {recipes.map((r) => <option key={r.name} value={r.name}>{r.name}</option>)}
      </NativeSelect>
      <Button size="xs" variant="default" onClick={handleLoad} disabled={!selected}>
        {t("colour.load_recipe")}
      </Button>
    </Group>
  );
}
```

- [ ] **Step 3: Rewrite `RecipeSaver.tsx`**

```tsx
import { useState } from "react";
import { useTranslation } from "react-i18next";
import { Button, Group, Text, TextInput } from "@mantine/core";
import { useProjectStore, activeBookOf } from "../../store/projectStore";
import { saveRecipe } from "../../api/client";

interface Props { onSaved(): void; }

export function RecipeSaver({ onSaved }: Props) {
  const { t } = useTranslation();
  const book = useProjectStore((s) => activeBookOf(s));
  const [name, setName] = useState("");
  const [toast, setToast] = useState(false);

  if (!book) return null;
  const activeRegion = book.selected === 0 ? book.whole : book.drawn[book.selected - 1];
  const palette = activeRegion?.palette ?? [];

  const handleSave = async () => {
    if (!name.trim()) return;
    const steps = palette.map((p, i) => ({ label: `step ${i + 1}`, hex: p.hex, paint_ref: p.name !== "custom" ? p.name : null }));
    await saveRecipe({ name: name.trim(), steps });
    setToast(true); setName(""); onSaved();
    setTimeout(() => setToast(false), 2000);
  };

  return (
    <Group gap="xs" mt="xs">
      <TextInput size="xs" value={name} placeholder={t("colour.recipe_name")}
        onChange={(e) => setName(e.target.value)} style={{ flex: 1 }} />
      <Button size="xs" onClick={handleSave} disabled={!name.trim()}>{t("colour.save_recipe")}</Button>
      {toast && <Text size="xs" c="green">{t("colour.recipe_saved")}</Text>}
    </Group>
  );
}
```

- [ ] **Step 4: Rewrite `RecipeManager.tsx`**

```tsx
import { useRef } from "react";
import { useTranslation } from "react-i18next";
import { Button, Group } from "@mantine/core";
import { exportRecipes, importRecipes, exportCollection, importCollection } from "../../api/client";

function triggerDownload(blob: Blob, filename: string) {
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a"); a.href = url; a.download = filename; a.click();
  URL.revokeObjectURL(url);
}

export function RecipeManager() {
  const { t } = useTranslation();
  const recipeRef = useRef<HTMLInputElement>(null);
  const collectionRef = useRef<HTMLInputElement>(null);

  return (
    <Group gap="xs" wrap="wrap">
      <Button size="xs" variant="subtle" onClick={async () => triggerDownload(await exportRecipes(), "recipes.json")}>
        {t("recipes.export")}
      </Button>
      <Button size="xs" variant="subtle" onClick={() => recipeRef.current?.click()}>
        {t("recipes.import")}
      </Button>
      <input ref={recipeRef} type="file" accept=".json" style={{ display: "none" }}
        onChange={async (e) => { const f = e.target.files?.[0]; if (f) { await importRecipes(f); e.target.value = ""; } }} />
      <Button size="xs" variant="subtle" onClick={async () => triggerDownload(await exportCollection(), "collection.json")}>
        {t("recipes.collection_export")}
      </Button>
      <Button size="xs" variant="subtle" onClick={() => collectionRef.current?.click()}>
        {t("recipes.collection_import")}
      </Button>
      <input ref={collectionRef} type="file" accept=".json" style={{ display: "none" }}
        onChange={async (e) => { const f = e.target.files?.[0]; if (f) { await importCollection(f); e.target.value = ""; } }} />
    </Group>
  );
}
```

- [ ] **Step 5: Rewrite `BandEditor.tsx`**

```tsx
import { useState } from "react";
import { useTranslation } from "react-i18next";
import { Divider, Stack, Text } from "@mantine/core";
import { useProjectStore, activeBookOf } from "../../store/projectStore";
import { BandSlot } from "./BandSlot";
import { CoverageEditor } from "./CoverageEditor";
import { RecipeLoader } from "./RecipeLoader";
import { RecipeSaver } from "./RecipeSaver";

export function BandEditor() {
  const { t } = useTranslation();
  const book = useProjectStore((s) => activeBookOf(s));
  const [recipeKey, setRecipeKey] = useState(0);

  if (!book) return null;
  const g = book.selected;
  const region = g === 0 ? book.whole : book.drawn[g - 1];
  if (!region) return null;
  const { palette, coverage, material } = region;
  const n = palette.length;

  return (
    <Stack gap="xs">
      <Text size="sm" fw={500}>{t("colour.band_editor")}</Text>
      <RecipeLoader key={recipeKey} onRecipeLoaded={() => setRecipeKey((k) => k + 1)} />
      <Divider />
      {palette.map((paint, i) => (
        <BandSlot key={i} g={g} i={i} paint={paint} finish={material} n={n} palette={palette} />
      ))}
      <Divider />
      <CoverageEditor g={g} n={n} coverage={coverage} />
      <RecipeSaver onSaved={() => setRecipeKey((k) => k + 1)} />
    </Stack>
  );
}
```

- [ ] **Step 6: Run SchemeManager tests + full suite**

```bash
npm test -- --reporter=verbose SchemeManager
npm test
```

All tests should pass. Fix any text-selector mismatches in SchemeManager (button labels are the same).

- [ ] **Step 7: Commit**

```bash
git add web/src/components/colour/SchemeManager.tsx web/src/components/colour/BandEditor.tsx web/src/components/colour/RecipeLoader.tsx web/src/components/colour/RecipeSaver.tsx web/src/components/colour/RecipeManager.tsx
git commit -m "feat(mantine): migrate SchemeManager, BandEditor, Recipe components"
```

---

### Task 9: PaintInventory + PaintsTab

**Files:**
- Modify: `web/src/components/PaintInventory.tsx`
- Modify: `web/src/components/PaintsTab.tsx`

- [ ] **Step 1: Rewrite `PaintInventory.tsx`**

Note: use `type="search"` on the underlying input so the existing `getByRole("searchbox")` test query continues to work (Mantine's `TextInput` passes `type` through to the `<input>` element, which gives it the implicit ARIA role "searchbox").

```tsx
import { useState } from "react";
import { useTranslation } from "react-i18next";
import { Checkbox, ColorSwatch, Group, Loader, ScrollArea, Stack, Text, TextInput } from "@mantine/core";
import { useCatalogStore } from "../store/catalogStore";

export function PaintInventory() {
  const { t } = useTranslation();
  const paints = useCatalogStore((s) => s.paints);
  const ownedCodes = useCatalogStore((s) => s.ownedCodes);
  const status = useCatalogStore((s) => s.status);
  const toggleOwned = useCatalogStore((s) => s.toggleOwned);
  const [search, setSearch] = useState("");

  if (status !== "ready") {
    return (
      <Group gap="sm">
        <Loader size="xs" />
        <Text size="sm" c="dimmed">{t("paints.loading")}</Text>
      </Group>
    );
  }

  const q = search.trim().toLowerCase();
  const filtered = q
    ? paints.filter((p) =>
        p.name.toLowerCase().includes(q) ||
        (p.code ?? "").toLowerCase().includes(q) ||
        (p.paint_range ?? "").toLowerCase().includes(q))
    : paints;

  const ownedCount = paints.filter((p) => ownedCodes.has(p.code ?? "")).length;

  return (
    <Stack gap="xs">
      <TextInput
        type="search"
        placeholder={t("paints.search_placeholder")}
        value={search}
        onChange={(e) => setSearch(e.target.value)}
        size="xs"
      />
      <Text size="xs" c="dimmed">
        {t("paints.owned_count", { owned: ownedCount, total: paints.length })}
        {q && ` · ${filtered.length} ${t("paints.filtered_suffix")}`}
      </Text>
      <ScrollArea h={420}>
        <Stack gap={0}>
          {filtered.map((p) => {
            const code = p.code ?? "";
            const owned = ownedCodes.has(code);
            return (
              <Group key={code || p.name} gap="xs" py={4}
                style={{ borderBottom: "1px solid var(--mantine-color-dark-5)", opacity: owned ? 1 : 0.7, cursor: "pointer" }}
                onClick={() => toggleOwned(code)}>
                <Checkbox size="xs" checked={owned}
                  onChange={() => toggleOwned(code)}
                  onClick={(e) => e.stopPropagation()}
                  style={{ flexShrink: 0 }} />
                <ColorSwatch color={p.hex} size={14} style={{ flexShrink: 0 }} />
                <Text size="xs" c={owned ? undefined : "dimmed"} style={{ flex: 1 }}>{p.name}</Text>
                {p.paint_range && <Text size="xs" c="dimmed">{p.paint_range}</Text>}
                <Text size="xs" c="dimmed" ff="monospace">{code}</Text>
              </Group>
            );
          })}
          {filtered.length === 0 && q && (
            <Text size="sm" c="dimmed" p="xs">{t("paints.no_results")}</Text>
          )}
        </Stack>
      </ScrollArea>
    </Stack>
  );
}
```

- [ ] **Step 2: Run PaintInventory tests**

```bash
npm test -- --reporter=verbose PaintInventory
```

The test uses `getByRole("searchbox")` — `type="search"` on the Mantine TextInput's underlying `<input>` gives the implicit role. Checkbox interactions use `getByRole("checkbox")` — Mantine Checkbox renders `<input type="checkbox">`, so this still works. Verify.

- [ ] **Step 3: Rewrite `PaintsTab.tsx`**

```tsx
import { useRef, useState } from "react";
import { useTranslation } from "react-i18next";
import { Button, Divider, Group, Stack, Text } from "@mantine/core";
import { exportCollection, importCollection } from "../api/client";
import { useCatalogStore } from "../store/catalogStore";
import { PaintInventory } from "./PaintInventory";

export function PaintsTab() {
  const { t } = useTranslation();
  const setOwnedFromImport = useCatalogStore((s) => s.setOwnedFromImport);
  const ownedCodes = useCatalogStore((s) => s.ownedCodes);
  const [importing, setImporting] = useState(false);
  const [message, setMessage] = useState<{ kind: "ok" | "err"; text: string } | null>(null);
  const fileRef = useRef<HTMLInputElement>(null);

  async function handleExport() {
    const blob = await exportCollection();
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a"); a.href = url; a.download = "my_paints.json"; a.click();
    URL.revokeObjectURL(url);
  }

  async function handleImport(e: React.ChangeEvent<HTMLInputElement>) {
    const file = e.target.files?.[0]; if (!file) return;
    setImporting(true); setMessage(null);
    try {
      const res = await importCollection(file);
      setOwnedFromImport(res.owned);
      setMessage({ kind: "ok", text: t("paints.import_success", { count: res.owned.length }) });
    } catch (err) {
      setMessage({ kind: "err", text: t("paints.import_error", { err: String(err) }) });
    } finally { setImporting(false); if (fileRef.current) fileRef.current.value = ""; }
  }

  return (
    <Stack gap="sm" p="xs">
      <PaintInventory />
      <Divider />
      <Stack gap="xs">
        <Text size="xs" c="dimmed">{t("paints.manage_section")}</Text>
        <Group gap="xs" wrap="wrap">
          {ownedCodes.size > 0 && (
            <Button size="xs" variant="default" onClick={handleExport}>{t("paints.export_btn")}</Button>
          )}
          <Button size="xs" variant="default" loading={importing} onClick={() => fileRef.current?.click()}>
            {t("paints.import_btn")}
          </Button>
          <input ref={fileRef} type="file" accept=".json" style={{ display: "none" }} onChange={handleImport} />
        </Group>
        {message && <Text size="sm" c={message.kind === "ok" ? "green" : "red"}>{message.text}</Text>}
      </Stack>
    </Stack>
  );
}
```

- [ ] **Step 4: Commit**

```bash
git add web/src/components/PaintInventory.tsx web/src/components/PaintsTab.tsx
git commit -m "feat(mantine): migrate PaintInventory (ScrollArea, Checkbox, ColorSwatch) and PaintsTab"
```

---

### Task 10: StepList + PaintTab + AngleGallery + AnglesTab

**Files:**
- Modify: `web/src/components/StepList.tsx`
- Modify: `web/src/components/PaintTab.tsx`
- Modify: `web/src/components/AngleGallery.tsx`
- Modify: `web/src/components/AnglesTab.tsx`

- [ ] **Step 1: Rewrite `StepList.tsx`**

```tsx
import { useTranslation } from "react-i18next";
import { Image, Paper, SimpleGrid, Stack, Text, Title } from "@mantine/core";
import type { RegionPlanDto, StepImageDto } from "../api/types";

function StepCard({ step }: { step: StepImageDto }) {
  const { t } = useTranslation();
  return (
    <Paper p="sm" withBorder mb="sm">
      <Text fw={600} mb="xs">{step.label}</Text>
      <SimpleGrid cols={step.is_last ? 2 : 3} spacing="xs">
        <Stack gap={4}>
          <Image src={step.zone_png} alt={t("paint.step_zone")} />
          <Text size="xs" c="dimmed" ta="center">{t("paint.step_zone")}</Text>
        </Stack>
        <Stack gap={4}>
          <Image src={step.cumulative_png} alt={t("paint.step_cumulative")} />
          <Text size="xs" c="dimmed" ta="center">{t("paint.step_cumulative")}</Text>
        </Stack>
        {!step.is_last && step.exact_png && (
          <Stack gap={4}>
            <Image src={step.exact_png} alt={t("paint.step_exact")} />
            <Text size="xs" c="dimmed" ta="center">{t("paint.step_exact")}</Text>
          </Stack>
        )}
      </SimpleGrid>
    </Paper>
  );
}

export interface StepListProps { plans: RegionPlanDto[]; }

export function StepList({ plans }: StepListProps) {
  return (
    <Stack gap="xl">
      {plans.map((plan, idx) => (
        <div key={plan.name}>
          <Title order={4} mb="sm">{plan.name}</Title>
          {plan.steps.map((step) => (
            <StepCard key={`${step.kind}-${step.index}`} step={step} />
          ))}
        </div>
      ))}
    </Stack>
  );
}
```

- [ ] **Step 2: Rewrite `PaintTab.tsx`**

```tsx
import { useState, useEffect, useRef } from "react";
import { useTranslation } from "react-i18next";
import { Center, Loader, Text } from "@mantine/core";
import { fetchSteps, analyze, TokenExpiredError } from "../api/client";
import { useProjectStore, activeAngleOf } from "../store/projectStore";
import { StepList } from "./StepList";
import type { RegionPlanDto, RegionPayload } from "../api/types";

export function PaintTab() {
  const { t } = useTranslation();
  const token = useProjectStore((s) => activeAngleOf(s)?.resultToken);
  const setPreview = useProjectStore((s) => s.setPreview);
  const [plans, setPlans] = useState<RegionPlanDto[] | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const lastLoadedToken = useRef<string | undefined>(undefined);

  useEffect(() => {
    if (!token) return;
    if (lastLoadedToken.current === token) return;
    let cancelled = false;

    async function load() {
      setLoading(true); setError(null);
      try {
        const data = await fetchSteps(token!);
        if (!cancelled) { lastLoadedToken.current = token; setPlans(data.plans); }
      } catch (e) {
        if (cancelled) return;
        if (e instanceof TokenExpiredError) {
          try {
            const { angles, activeAngle } = useProjectStore.getState();
            const a = angles[activeAngle];
            if (!a?.photoId) throw new Error("no photo");
            const regions: RegionPayload[] = a.book.drawn
              .filter((r) => !r.blank && r.rings.length > 0)
              .map((r) => ({ name: r.name, rings: r.rings, palette: r.palette, coverage: r.coverage, material: r.material }));
            const res = await analyze({ photo_id: a.photoId, whole: a.book.whole, regions, settings: a.settings });
            if (!cancelled) {
              const retry = await fetchSteps(res.result_token);
              if (!cancelled) { lastLoadedToken.current = res.result_token; setPlans(retry.plans); setPreview(res.preview_png, res.result_token); }
            }
          } catch (retryErr) { if (!cancelled) setError(String(retryErr)); }
        } else { setError(String(e)); }
      } finally { if (!cancelled) setLoading(false); }
    }
    load();
    return () => { cancelled = true; };
  }, [token]); // eslint-disable-line react-hooks/exhaustive-deps

  if (!token) return <Text c="dimmed">{t("paint.no_preview")}</Text>;
  if (loading) return <Center mt="xl"><Loader size="sm" /></Center>;
  if (error) return <Text c="red">{error}</Text>;
  if (!plans) return null;
  return <StepList plans={plans} />;
}
```

- [ ] **Step 3: Rewrite `AngleGallery.tsx`**

```tsx
import { useEffect, useState } from "react";
import { useTranslation } from "react-i18next";
import { Badge, Card, Center, Group, Image, SimpleGrid, Text } from "@mantine/core";
import { analyze } from "../api/client";
import { useProjectStore } from "../store/projectStore";
import type { AnalyzeRequest } from "../api/types";
import type { Angle } from "../store/projectStore";

function buildRequest(angle: Angle): AnalyzeRequest {
  return {
    photo_id: angle.photoId!,
    whole: angle.book.whole,
    regions: angle.book.drawn
      .filter((r) => !r.blank)
      .map((r) => ({ name: r.name, rings: r.rings, palette: r.palette, coverage: r.coverage, material: r.material })),
    settings: angle.settings,
  };
}

type PreviewState = string | null | "error";

export function AngleGallery() {
  const { t } = useTranslation();
  const angles = useProjectStore((s) => s.angles);
  const activeAngle = useProjectStore((s) => s.activeAngle);

  const [previews, setPreviews] = useState<Record<string, PreviewState>>(() => {
    const init: Record<string, PreviewState> = {};
    for (const a of angles) { init[a.id] = a.preview ?? null; }
    return init;
  });

  useEffect(() => {
    let cancelled = false;
    setPreviews((prev) => {
      const next: Record<string, PreviewState> = {};
      for (const a of angles) { next[a.id] = a.preview ?? prev[a.id] ?? null; }
      return next;
    });
    for (const angle of angles) {
      if (angle.preview || !angle.photoId) continue;
      analyze(buildRequest(angle))
        .then((res) => { if (!cancelled) setPreviews((prev) => { const e = prev[angle.id]; if (e && e !== "error") return prev; return { ...prev, [angle.id]: res.preview_png }; }); })
        .catch(() => { if (!cancelled) setPreviews((p) => ({ ...p, [angle.id]: "error" })); });
    }
    return () => { cancelled = true; };
  }, [angles]);

  if (angles.length === 0) return <Text c="dimmed" size="sm">{t("gallery.no_angles")}</Text>;

  return (
    <Stack gap="xs">
      <Text fw={500}>{t("gallery.heading")}</Text>
      <Text size="xs" c="dimmed" mb="xs">{t("gallery.caption")}</Text>
      <SimpleGrid cols={3} spacing="md">
        {angles.map((angle, idx) => {
          const preview = previews[angle.id];
          const isActive = idx === activeAngle;
          return (
            <Card key={angle.id} withBorder padding="xs"
              style={{ borderColor: isActive ? "var(--mantine-color-violet-5)" : undefined }}>
              {!angle.photoId ? (
                <Center h={160}><Text size="sm" c="dimmed">{t("gallery.no_photo")}</Text></Center>
              ) : preview === null ? (
                <Center h={160}><Text size="sm" c="dimmed">{t("gallery.loading")}</Text></Center>
              ) : preview === "error" ? (
                <Center h={160}><Text size="sm" c="red">{t("gallery.preview_error")}</Text></Center>
              ) : (
                <Image src={preview} alt={angle.label} fit="contain" h={160} />
              )}
              <Group gap="xs" mt="xs">
                <Text size="xs" style={{ flex: 1, overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>
                  {angle.label}
                </Text>
                {isActive && <Badge size="xs" variant="light">{t("gallery.active_badge")}</Badge>}
              </Group>
            </Card>
          );
        })}
      </SimpleGrid>
    </Stack>
  );
}
```

Add `Stack` to the Mantine import.

- [ ] **Step 4: Migrate `AnglesTab.tsx`**

Read the current file — if it's a thin wrapper around `AngleGallery`, add a `<Box p="sm">` or `<Stack>` wrapper with Mantine. The content is `<AngleGallery />`.

- [ ] **Step 5: Run full test suite + build**

```bash
npm test && npm run build
```

All tests pass, build is clean. Migration is complete.

- [ ] **Step 6: Commit**

```bash
git add web/src/components/StepList.tsx web/src/components/PaintTab.tsx web/src/components/AngleGallery.tsx web/src/components/AnglesTab.tsx
git commit -m "feat(mantine): migrate StepList, PaintTab, AngleGallery, AnglesTab — Mantine migration complete"
```

---

## Self-Review

### Spec coverage
§11 calls for a post-migration visual upgrade with a durable design system. This plan:
- ✅ Covers all 23 component files under `web/src/`
- ✅ Consistent dark theme via `MantineProvider defaultColorScheme="dark"`
- ✅ All form controls replaced: Slider, ColorInput, NativeSelect, Checkbox, Radio, TextInput
- ✅ All layout replaced: Group, Stack, Paper, Card, SimpleGrid, ScrollArea, Container
- ✅ All navigation replaced: Tabs (main + RightPanel), SegmentedControl (language)
- ✅ Test breaks called out per task with specific fix instructions

### Placeholder scan
No TBDs. The tone `<input>` in SchemeGenerator uses a raw styled `<input type="text">` inside a Table.Td — this is intentional (nested Mantine TextInput inside a Table.Td has sizing conflicts); note this for the UX pass.

### Type consistency
- `ColorInput.onChange` → `(hex: string)` — used as `onChange={setMidtoneHex}` (string setter) ✅
- `Slider.onChange` → `(val: number)` — adapted in `handleSlider(i, val: number)` ✅
- `NativeSelect.onChange` → `(e: React.ChangeEvent<HTMLSelectElement>)` — `e.target.value` throughout ✅
- `Radio.Group.onChange` → `(v: string)` — wrapped `Number(v)` for `setSelected` ✅
- `Checkbox.onChange` → `(e: React.ChangeEvent<HTMLInputElement>)` — `e.currentTarget.checked` in SchemeGenerator ✅
