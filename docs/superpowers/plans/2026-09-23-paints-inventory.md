# Paints Inventory Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a "Paints" tab to the React app — a searchable catalog browser where users toggle which paints they own, backed by the server-side collection. Faithfully ports `ui/paints_tab.py`.

**Architecture:**
- **Backend:** All four collection routes already exist (`GET/PUT /api/collection`, `GET /api/collection/export`, `POST /api/collection/import`) — no new Python code.
- **Frontend client:** `getCollection`, `putCollection`, `exportCollection`, `importCollection` already exist in `web/src/api/client.ts` — no new client functions.
- **New work:** (1) extend `catalogStore` with owned-collection state, (2) build `PaintInventory` component (catalog list + search + owned toggles), (3) build `PaintsTab` (wraps PaintInventory + import/export) and wire into `App.tsx`.

**Tech Stack:** Python 3.11, FastAPI, Pydantic v2, Zustand, React 18, TypeScript, Vitest

**Spec:** `docs/superpowers/specs/2026-09-22-react-fastapi-migration-design.md` §7 (PaintsTab ← `ui/paints_tab.py`)

## Global Constraints

- Branch: `feat/paints-inventory` (never commit to `main` directly)
- No npm/pip installs — all dependencies already present
- Run backend tests from repo root: `.venv\Scripts\python -m pytest backend/tests/ -v`
- Run frontend tests from `web/`: `npm test -- --run`
- The existing `getCollection` / `putCollection` API client functions must not be modified

---

### Task 1: Extend `catalogStore` with owned-collection state

**Files:**
- Modify: `web/src/store/catalogStore.ts`
- Modify: `web/src/store/catalogStore.test.ts`

**Interfaces to add:**
- `ownedCodes: Set<string>` — the set of owned paint codes (persisted server-side)
- `collectionStatus: "idle" | "loading" | "ready" | "error"` — distinct from catalog status
- `loadCollection(): Promise<void>` — calls `getCollection()`, idempotent (skip if already loading/ready)
- `toggleOwned(code: string): Promise<void>` — toggle in set, persist immediately, revert on error
- `setOwnedFromImport(codes: string[]): void` — bulk replace after import (no server call; caller already saved)

- [ ] **Step 1: Add new tests to `web/src/store/catalogStore.test.ts`**

Add this describe block after the existing one:

```typescript
import * as client from "../api/client";

describe("catalogStore — collection", () => {
  const reset = () =>
    useCatalogStore.setState({
      paints: [],
      status: "idle",
      error: undefined,
      ownedCodes: new Set(),
      collectionStatus: "idle",
    });

  beforeEach(() => {
    reset();
    vi.restoreAllMocks();
  });

  it("loadCollection transitions idle → loading → ready and stores codes", async () => {
    vi.spyOn(client, "getCollection").mockResolvedValue({ owned: ["X1", "X2"] });
    expect(useCatalogStore.getState().collectionStatus).toBe("idle");
    await useCatalogStore.getState().loadCollection();
    const s = useCatalogStore.getState();
    expect(s.collectionStatus).toBe("ready");
    expect(s.ownedCodes).toEqual(new Set(["X1", "X2"]));
  });

  it("loadCollection is idempotent — second call is a no-op", async () => {
    const spy = vi.spyOn(client, "getCollection").mockResolvedValue({ owned: ["X1"] });
    await useCatalogStore.getState().loadCollection();
    await useCatalogStore.getState().loadCollection();
    expect(spy).toHaveBeenCalledTimes(1);
  });

  it("toggleOwned adds a code and persists", async () => {
    vi.spyOn(client, "getCollection").mockResolvedValue({ owned: [] });
    vi.spyOn(client, "putCollection").mockResolvedValue({ ok: true });
    await useCatalogStore.getState().loadCollection();
    await useCatalogStore.getState().toggleOwned("C1");
    const s = useCatalogStore.getState();
    expect(s.ownedCodes.has("C1")).toBe(true);
    expect(client.putCollection).toHaveBeenCalledWith(expect.arrayContaining(["C1"]));
  });

  it("toggleOwned removes an already-owned code and persists", async () => {
    vi.spyOn(client, "getCollection").mockResolvedValue({ owned: ["C1", "C2"] });
    vi.spyOn(client, "putCollection").mockResolvedValue({ ok: true });
    await useCatalogStore.getState().loadCollection();
    await useCatalogStore.getState().toggleOwned("C1");
    const s = useCatalogStore.getState();
    expect(s.ownedCodes.has("C1")).toBe(false);
    expect(s.ownedCodes.has("C2")).toBe(true);
    expect(client.putCollection).toHaveBeenCalledWith(expect.arrayContaining(["C2"]));
    expect(client.putCollection).toHaveBeenCalledWith(expect.not.arrayContaining(["C1"]));
  });

  it("toggleOwned reverts on API error", async () => {
    vi.spyOn(client, "getCollection").mockResolvedValue({ owned: [] });
    vi.spyOn(client, "putCollection").mockRejectedValue(new Error("network"));
    await useCatalogStore.getState().loadCollection();
    await useCatalogStore.getState().toggleOwned("C1");
    // After revert, C1 should be back to not-owned
    expect(useCatalogStore.getState().ownedCodes.has("C1")).toBe(false);
  });

  it("setOwnedFromImport replaces the owned set", async () => {
    vi.spyOn(client, "getCollection").mockResolvedValue({ owned: ["OLD"] });
    await useCatalogStore.getState().loadCollection();
    useCatalogStore.getState().setOwnedFromImport(["NEW1", "NEW2"]);
    const s = useCatalogStore.getState();
    expect(s.ownedCodes).toEqual(new Set(["NEW1", "NEW2"]));
  });

  it("loadCollection sets error on rejection", async () => {
    vi.spyOn(client, "getCollection").mockRejectedValue(new Error("net"));
    await useCatalogStore.getState().loadCollection();
    expect(useCatalogStore.getState().collectionStatus).toBe("error");
  });
});
```

- [ ] **Step 2: Run to verify new tests fail**

```
npm test -- --run
```
Expected: 6 new tests fail (fields missing from store).

- [ ] **Step 3: Update `web/src/store/catalogStore.ts`**

Replace the full file with:

```typescript
import { create } from "zustand";
import { fetchCatalog, getCollection, putCollection } from "../api/client";
import type { PaintColor } from "../api/types";

interface CatalogState {
  paints: PaintColor[];
  status: "idle" | "loading" | "ready" | "error";
  error?: string;
  ownedCodes: Set<string>;
  collectionStatus: "idle" | "loading" | "ready" | "error";
  fetch(): Promise<void>;
  findByCode(code: string): PaintColor | undefined;
  loadCollection(): Promise<void>;
  toggleOwned(code: string): Promise<void>;
  setOwnedFromImport(codes: string[]): void;
}

export const useCatalogStore = create<CatalogState>((set, get) => ({
  paints: [],
  status: "idle",
  ownedCodes: new Set<string>(),
  collectionStatus: "idle",

  fetch: async () => {
    const { status } = get();
    if (status === "ready" || status === "loading") return;
    set({ status: "loading" });
    try {
      const res = await fetchCatalog();
      set({ paints: res.paints, status: "ready" });
    } catch (e) {
      set({ status: "error", error: String(e) });
    }
  },

  findByCode: (code) => get().paints.find((p) => p.code === code),

  loadCollection: async () => {
    const { collectionStatus } = get();
    if (collectionStatus === "ready" || collectionStatus === "loading") return;
    set({ collectionStatus: "loading" });
    try {
      const res = await getCollection();
      set({ ownedCodes: new Set(res.owned), collectionStatus: "ready" });
    } catch (e) {
      set({ collectionStatus: "error" });
    }
  },

  toggleOwned: async (code: string) => {
    const { ownedCodes } = get();
    const next = new Set(ownedCodes);
    if (next.has(code)) next.delete(code);
    else next.add(code);
    set({ ownedCodes: next });
    try {
      await putCollection([...next]);
    } catch {
      set({ ownedCodes }); // revert
    }
  },

  setOwnedFromImport: (codes: string[]) => {
    set({ ownedCodes: new Set(codes), collectionStatus: "ready" });
  },
}));
```

- [ ] **Step 4: Run all frontend tests — expect all pass**

```
npm test -- --run
```
Expected: all green including the 6 new collection tests.

- [ ] **Step 5: Commit**

```
git checkout -b feat/paints-inventory
git add web/src/store/catalogStore.ts web/src/store/catalogStore.test.ts
git commit -m "feat: extend catalogStore with owned-collection state (loadCollection, toggleOwned)"
```

---

### Task 2: `PaintInventory` component — catalog browse + owned toggles

**Files:**
- Create: `web/src/components/PaintInventory.tsx`
- Create: `web/src/components/PaintInventory.test.tsx`

**UX (faithful port of `paints_tab.py`):**
- Search input filters catalog by name, code, or range (case-insensitive)
- Full catalog list: each row shows color swatch + name + range + code + owned checkbox
- Owned count and total count displayed below search
- Toggling a checkbox calls `catalogStore.toggleOwned(code)` — persists immediately

**Interfaces:**
- Reads `paints` and `ownedCodes` from `useCatalogStore`
- Calls `toggleOwned` from `useCatalogStore`
- No props needed (pure store consumer)

- [ ] **Step 1: Write `web/src/components/PaintInventory.test.tsx`**

```typescript
import { render, screen, fireEvent, waitFor } from "@testing-library/react";
import { describe, it, expect, vi, beforeEach } from "vitest";
import { PaintInventory } from "./PaintInventory";
import { useCatalogStore } from "../store/catalogStore";

vi.mock("react-i18next", () => ({
  useTranslation: () => ({ t: (k: string, o?: Record<string, unknown>) => {
    if (o) return `${k}:${JSON.stringify(o)}`;
    return k;
  }}),
}));

const fakePaint = (code: string, name = `Paint ${code}`, range = "Base") => ({
  name, hex: "#aabbcc", code, finish: "matte", paint_range: range, brand: "Citadel",
});

function seedCatalog(codes: string[], ownedCodes: string[] = []) {
  useCatalogStore.setState({
    paints: codes.map((c) => fakePaint(c)),
    status: "ready",
    ownedCodes: new Set(ownedCodes),
    collectionStatus: "ready",
  });
}

beforeEach(() => {
  useCatalogStore.setState({ paints: [], status: "idle", ownedCodes: new Set(), collectionStatus: "idle" });
  vi.restoreAllMocks();
});

it("renders a row for each paint in the catalog", () => {
  seedCatalog(["C1", "C2", "C3"]);
  render(<PaintInventory />);
  expect(screen.getByText("Paint C1")).toBeInTheDocument();
  expect(screen.getByText("Paint C2")).toBeInTheDocument();
  expect(screen.getByText("Paint C3")).toBeInTheDocument();
});

it("owned paints have their checkbox checked", () => {
  seedCatalog(["C1", "C2"], ["C1"]);
  render(<PaintInventory />);
  const checkboxes = screen.getAllByRole("checkbox");
  // C1 owned → checked; C2 not owned → unchecked
  expect(checkboxes[0]).toBeChecked();
  expect(checkboxes[1]).not.toBeChecked();
});

it("clicking an unchecked row calls toggleOwned", async () => {
  seedCatalog(["C1"], []);
  const toggleSpy = vi.fn().mockResolvedValue(undefined);
  useCatalogStore.setState({ toggleOwned: toggleSpy } as any);
  render(<PaintInventory />);
  fireEvent.click(screen.getByRole("checkbox"));
  expect(toggleSpy).toHaveBeenCalledWith("C1");
});

it("clicking an owned row calls toggleOwned to unmark it", async () => {
  seedCatalog(["C1"], ["C1"]);
  const toggleSpy = vi.fn().mockResolvedValue(undefined);
  useCatalogStore.setState({ toggleOwned: toggleSpy } as any);
  render(<PaintInventory />);
  fireEvent.click(screen.getByRole("checkbox"));
  expect(toggleSpy).toHaveBeenCalledWith("C1");
});

it("search filters catalog rows by name", () => {
  seedCatalog(["C1", "C2"], []);
  useCatalogStore.setState({
    paints: [fakePaint("C1", "Abaddon Black"), fakePaint("C2", "White Scar")],
    status: "ready",
  });
  render(<PaintInventory />);
  const search = screen.getByRole("searchbox");
  fireEvent.change(search, { target: { value: "black" } });
  expect(screen.getByText("Abaddon Black")).toBeInTheDocument();
  expect(screen.queryByText("White Scar")).not.toBeInTheDocument();
});

it("search filters by code", () => {
  seedCatalog([], []);
  useCatalogStore.setState({
    paints: [fakePaint("C1", "Paint A"), fakePaint("C2", "Paint B")],
    status: "ready",
  });
  render(<PaintInventory />);
  fireEvent.change(screen.getByRole("searchbox"), { target: { value: "C2" } });
  expect(screen.queryByText("Paint A")).not.toBeInTheDocument();
  expect(screen.getByText("Paint B")).toBeInTheDocument();
});

it("shows owned and total count", () => {
  seedCatalog(["C1", "C2", "C3"], ["C1", "C2"]);
  render(<PaintInventory />);
  expect(screen.getByText(/2.*3|3.*2/)).toBeInTheDocument();
});

it("shows empty catalog message when no paints loaded", () => {
  render(<PaintInventory />);
  expect(screen.getByText(/paints\.loading/i)).toBeInTheDocument();
});
```

- [ ] **Step 2: Run to verify new tests fail**

```
npm test -- --run
```
Expected: all new `PaintInventory` tests fail (component does not exist).

- [ ] **Step 3: Create `web/src/components/PaintInventory.tsx`**

```typescript
import { useState } from "react";
import { useTranslation } from "react-i18next";
import { useCatalogStore } from "../store/catalogStore";

export function PaintInventory() {
  const { t } = useTranslation();
  const paints = useCatalogStore((s) => s.paints);
  const ownedCodes = useCatalogStore((s) => s.ownedCodes);
  const status = useCatalogStore((s) => s.status);
  const toggleOwned = useCatalogStore((s) => s.toggleOwned);
  const [search, setSearch] = useState("");

  if (status !== "ready") {
    return <p style={{ color: "#888", fontSize: 13 }}>{t("paints.loading")}</p>;
  }

  const q = search.trim().toLowerCase();
  const filtered = q
    ? paints.filter(
        (p) =>
          p.name.toLowerCase().includes(q) ||
          (p.code ?? "").toLowerCase().includes(q) ||
          (p.paint_range ?? "").toLowerCase().includes(q),
      )
    : paints;

  const ownedCount = paints.filter((p) => ownedCodes.has(p.code ?? "")).length;

  return (
    <div>
      <input
        role="searchbox"
        type="search"
        placeholder={t("paints.search_placeholder")}
        value={search}
        onChange={(e) => setSearch(e.target.value)}
        style={{
          width: "100%", padding: "6px 10px", marginBottom: 8, boxSizing: "border-box",
          background: "#1a1a1a", color: "#ddd", border: "1px solid #444",
          borderRadius: 4, fontSize: 13,
        }}
      />

      <div style={{ color: "#666", fontSize: 12, marginBottom: 8 }}>
        {t("paints.owned_count", { owned: ownedCount, total: paints.length })}
        {q && ` · ${filtered.length} ${t("paints.filtered_suffix")}`}
      </div>

      <div style={{ maxHeight: 420, overflowY: "auto" }}>
        {filtered.map((p) => {
          const code = p.code ?? "";
          const owned = ownedCodes.has(code);
          return (
            <label
              key={code || p.name}
              style={{
                display: "flex", alignItems: "center", gap: 8, padding: "4px 2px",
                cursor: "pointer", borderBottom: "1px solid #1e1e1e",
                opacity: owned ? 1 : 0.7,
              }}
            >
              <input
                type="checkbox"
                checked={owned}
                onChange={() => toggleOwned(code)}
                style={{ flexShrink: 0, cursor: "pointer" }}
              />
              {/* Color swatch */}
              <span
                style={{
                  display: "inline-block", width: 14, height: 14,
                  borderRadius: 3, background: p.hex, flexShrink: 0,
                  border: "1px solid #555",
                }}
              />
              <span style={{ flex: 1, fontSize: 13, color: owned ? "#ddd" : "#999" }}>
                {p.name}
              </span>
              {p.paint_range && (
                <span style={{ fontSize: 11, color: "#555", whiteSpace: "nowrap" }}>
                  {p.paint_range}
                </span>
              )}
              <span style={{ fontSize: 11, color: "#444", whiteSpace: "nowrap", fontFamily: "monospace" }}>
                {code}
              </span>
            </label>
          );
        })}
        {filtered.length === 0 && q && (
          <p style={{ color: "#555", fontSize: 13, padding: "8px 0" }}>
            {t("paints.no_results")}
          </p>
        )}
      </div>
    </div>
  );
}
```

- [ ] **Step 4: Run all frontend tests — expect all pass**

```
npm test -- --run
```
Expected: all green.

- [ ] **Step 5: Commit**

```
git add web/src/components/PaintInventory.tsx web/src/components/PaintInventory.test.tsx
git commit -m "feat: add PaintInventory component — catalog browse with owned toggles"
```

---

### Task 3: `PaintsTab`, import/export, i18n keys, and App wiring

**Files:**
- Create: `web/src/components/PaintsTab.tsx`
- Modify: `web/src/i18n/locales/en.json` (add `"paints"` section + `tabs.paints`)
- Modify: `web/src/i18n/locales/es.json` (mirror keys)
- Modify: `web/src/App.tsx` (add "paints" tab, load collection on catalog ready)

No tests for `PaintsTab` itself (thin orchestrator; `PaintInventory` is tested; import/export are framework calls).

- [ ] **Step 1: Add i18n keys to `web/src/i18n/locales/en.json`**

In the `"tabs"` object, add:
```json
"paints": "Paints"
```

Add a new top-level `"paints"` section:
```json
"paints": {
  "heading": "## 🎨 Paints",
  "search_placeholder": "Search by name, code or range…",
  "owned_count": "{{owned}} / {{total}} owned",
  "filtered_suffix": "shown",
  "no_results": "No paints match your search.",
  "loading": "Loading catalog…",
  "manage_section": "Manage collection",
  "export_btn": "Export collection",
  "import_btn": "Import collection",
  "importing": "Importing…",
  "import_success": "Imported {{count}} paints",
  "import_error": "Import failed: {{err}}"
}
```

- [ ] **Step 2: Mirror keys in `web/src/i18n/locales/es.json`**

In the `"tabs"` object, add:
```json
"paints": "Pinturas"
```

Add a new top-level `"paints"` section:
```json
"paints": {
  "heading": "## 🎨 Pinturas",
  "search_placeholder": "Buscar por nombre, código o gama…",
  "owned_count": "{{owned}} / {{total}} propias",
  "filtered_suffix": "mostradas",
  "no_results": "Ninguna pintura coincide.",
  "loading": "Cargando catálogo…",
  "manage_section": "Gestionar colección",
  "export_btn": "Exportar colección",
  "import_btn": "Importar colección",
  "importing": "Importando…",
  "import_success": "Importadas {{count}} pinturas",
  "import_error": "Error al importar: {{err}}"
}
```

- [ ] **Step 3: Create `web/src/components/PaintsTab.tsx`**

```typescript
import { useRef, useState } from "react";
import { useTranslation } from "react-i18next";
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
    const a = document.createElement("a");
    a.href = url;
    a.download = "my_paints.json";
    a.click();
    URL.revokeObjectURL(url);
  }

  async function handleImport(e: React.ChangeEvent<HTMLInputElement>) {
    const file = e.target.files?.[0];
    if (!file) return;
    setImporting(true);
    setMessage(null);
    try {
      const res = await importCollection(file);
      setOwnedFromImport(res.owned);
      setMessage({ kind: "ok", text: t("paints.import_success", { count: res.owned.length }) });
    } catch (err) {
      setMessage({ kind: "err", text: t("paints.import_error", { err: String(err) }) });
    } finally {
      setImporting(false);
      if (fileRef.current) fileRef.current.value = "";
    }
  }

  return (
    <div style={{ padding: "0 4px" }}>
      <PaintInventory />

      <div style={{ marginTop: 16, paddingTop: 12, borderTop: "1px solid #2a2a2a" }}>
        <div style={{ color: "#888", fontSize: 12, marginBottom: 6 }}>
          {t("paints.manage_section")}
        </div>
        <div style={{ display: "flex", gap: 8, flexWrap: "wrap" }}>
          {ownedCodes.size > 0 && (
            <button
              onClick={handleExport}
              style={{ padding: "4px 12px", fontSize: 13, cursor: "pointer" }}
            >
              {t("paints.export_btn")}
            </button>
          )}
          <button
            onClick={() => fileRef.current?.click()}
            disabled={importing}
            style={{ padding: "4px 12px", fontSize: 13, cursor: "pointer" }}
          >
            {importing ? t("paints.importing") : t("paints.import_btn")}
          </button>
          <input
            ref={fileRef}
            type="file"
            accept=".json"
            onChange={handleImport}
            style={{ display: "none" }}
          />
        </div>
        {message && (
          <div
            style={{
              marginTop: 8, fontSize: 13,
              color: message.kind === "ok" ? "#6c6" : "#f66",
            }}
          >
            {message.text}
          </div>
        )}
      </div>
    </div>
  );
}
```

- [ ] **Step 4: Wire `PaintsTab` into `web/src/App.tsx`**

**4a — Add import** at the top of `App.tsx`:
```typescript
import { PaintsTab } from "./components/PaintsTab";
```

**4b — Expand the `MainTab` type:**
```typescript
type MainTab = "studio" | "paint" | "paints";
```

**4c — Load collection when catalog becomes ready.** Find the existing `useEffect` that calls `fetchCatalog`:
```typescript
  useEffect(() => {
    if (hasAngle) fetchCatalog();
  }, [hasAngle, fetchCatalog]);
```
Add a second effect below it:
```typescript
  const loadCollection = useCatalogStore((s) => s.loadCollection);
  const catalogStatus = useCatalogStore((s) => s.status);
  useEffect(() => {
    if (catalogStatus === "ready") loadCollection();
  }, [catalogStatus, loadCollection]);
```

**4d — Add the Paints tab button.** Find the nav block with the Studio and Paint buttons and add after the Paint button:
```tsx
            <button
              style={tabBtn("paints")}
              onClick={() => setTab("paints")}
            >
              {t("tabs.paints")}
            </button>
```

**4e — Add the PaintsTab render.** After `{tab === "paint" && <PaintTab />}`, add:
```tsx
          {tab === "paints" && <PaintsTab />}
```

- [ ] **Step 5: Run all frontend tests — expect all pass**

```
npm test -- --run
```
Expected: all green. No new tests for `PaintsTab` (thin orchestrator; functionality covered by `PaintInventory` tests and the store tests).

- [ ] **Step 6: Smoke-test in the browser**

Start both processes:
```
.venv\Scripts\python -m uvicorn backend.main:app --reload --port 8000
```
```
cd web && npm run dev
```

Open `http://localhost:5173`. Upload any photo to unlock the tab bar. Verify:
1. "Paints" tab visible in the nav (alongside Studio, Paint)
2. Click Paints → catalog list loads (should show all Citadel/Vallejo/AK paints)
3. Search "black" → filters to black paints only
4. Check a paint → checkbox turns on; uncheck → turns off
5. Reload page; return to Paints tab → previously owned paints are still checked (persisted to server)
6. Click "Export collection" → `my_paints.json` downloads
7. Delete `user_data/collection.json`, reload, return to Paints → all unchecked
8. Use "Import collection" with the downloaded file → owned paints restore

- [ ] **Step 7: Commit**

```
git add web/src/components/PaintsTab.tsx web/src/App.tsx
git add web/src/i18n/locales/en.json web/src/i18n/locales/es.json
git commit -m "feat: add PaintsTab — catalog browse with owned toggles, import/export, wired into App"
```

---

## Self-Review

**Spec coverage (§7 PaintsTab ← `ui/paints_tab.py`):**
- Catalog browse ✓ `PaintInventory` — all paints with swatch + name + range + code
- Owned toggles ✓ checkbox per row, persisted via `PUT /api/collection`
- Import ✓ `POST /api/collection/import` → `setOwnedFromImport`
- Export ✓ `GET /api/collection/export` → browser download
- `paints_pool` in the manifest — the owned set is server-side (`user_data/collection.json`), not embedded in the project manifest; this matches the Streamlit behavior where the collection is global, not per-project

**API contract (§5):**
- `GET /api/collection` → `{owned:[code]}` ✓ (already exists, `loadCollection` calls it)
- `PUT /api/collection` → `{ok}` ✓ (already exists, `toggleOwned` calls it)
- `GET /api/collection/export` ✓
- `POST /api/collection/import` ✓

**Owned codes availability for other components:**
- `SchemeGenerator` uses `owned_codes` in its API request — it should read from `useCatalogStore.getState().ownedCodes`. After this plan ships, the `SchemeGenerator` can access live ownership data. (This is a follow-up improvement; the generator currently receives `owned_codes: []` which means "no filter". If the SchemeGenerator already wires `owned_only` toggle, update it to spread `[...ownedCodes]` from the store — but that is a separate concern and not required for this plan.)

**Placeholder scan:** None found. All code blocks are complete and runnable.
