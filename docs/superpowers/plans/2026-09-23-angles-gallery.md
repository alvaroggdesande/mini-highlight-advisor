# Angles Gallery Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add an "Angles" tab to the React app — a read-only grid showing every angle's combined painted preview, so the user can see the same palette across all faces at once. Faithfully ports `ui/gallery_panel.py`.

**Architecture:**
- **Backend:** No new endpoints — the gallery fetches previews via the existing `POST /api/analyze` route (same as Studio).
- **Frontend:** `AngleGallery` holds per-angle preview state locally. On tab open, it fires `/api/analyze` for each angle that doesn't already have a `preview` in the project store (i.e., non-active angles). The active angle's `preview` is already in the store from the Studio `useAnalyze` hook.
- **Coordinate system:** The gallery renders each preview as `<img src={dataUri} />` — no Konva canvas needed; regions are rasterized server-side just like in Studio.

**Tech Stack:** Zustand, React 18, TypeScript, Vitest

**Spec:** `docs/superpowers/specs/2026-09-22-react-fastapi-migration-design.md` §7 (AnglesTab ← `ui/gallery_panel.py`)

## Global Constraints

- Branch: `feat/angles-gallery` (never commit to `main` directly)
- No npm/pip installs — all dependencies already present
- Run frontend tests from `web/`: `npm test -- --run`
- Gallery is **read-only** — no editing; switching active angle happens in `AngleBar` in Studio
- A failed preview for one angle must not blank the grid (matches the `try/except` in `gallery_panel.py`)

---

### Task 1: `AngleGallery` component + tests

**Files:**
- Create: `web/src/components/AngleGallery.tsx`
- Create: `web/src/components/AngleGallery.test.tsx`

**Interfaces:**
- No props — reads `angles` and `activeAngle` from `useProjectStore`
- Local state: `previews: Record<string, string | null | "error">` — angleId → base64 PNG, null (loading), or "error"
- On mount / when `angles` changes: for each angle, use `preview` from store if present (active angle), otherwise call `analyze(buildRequest(angle))` and store the result locally
- Renders a 3-column grid; each cell shows the preview image + angle label + "(active)" badge

**Helper: `buildRequest(angle: Angle): AnalyzeRequest`**
The analyze request shape is identical to what `useAnalyze` sends:
```typescript
{
  photo_id: angle.photoId,
  whole: angle.book.whole,
  regions: angle.book.drawn
    .filter((r) => !r.blank)
    .map((r) => ({ name: r.name, rings: r.rings, palette: r.palette, coverage: r.coverage, material: r.material })),
  settings: angle.settings,
}
```
Angles without a `photoId` (not yet uploaded) skip the fetch and show a "no photo" placeholder.

- [ ] **Step 1: Write `web/src/components/AngleGallery.test.tsx`**

```typescript
import { render, screen, waitFor } from "@testing-library/react";
import { describe, it, expect, vi, beforeEach } from "vitest";
import { AngleGallery } from "./AngleGallery";
import { useProjectStore } from "../store/projectStore";
import * as client from "../api/client";

vi.mock("react-i18next", () => ({
  useTranslation: () => ({ t: (k: string) => k }),
}));

const DEFAULT_SETTINGS = {
  edge_hl: true, edge_extreme: false, edge_sens: 0.5,
  relief_cap: true, per_region_norm: false,
};

const DEFAULT_BOOK = {
  whole: { palette: [], coverage: [], material: "matte" },
  drawn: [],
  selected: 0,
  schemes: [],
};

function seedAngles(count: number, withPreviews: number[] = []) {
  const angles = Array.from({ length: count }, (_, i) => ({
    id: `a${i}`,
    label: `Angle ${i + 1}`,
    photoId: `ph00${i}`,
    width: 100,
    height: 100,
    qualityChecks: [],
    book: DEFAULT_BOOK,
    settings: DEFAULT_SETTINGS,
    preview: withPreviews.includes(i) ? `data:image/png;base64,FAKE${i}` : undefined,
    resultToken: withPreviews.includes(i) ? `tok${i}` : undefined,
  }));
  useProjectStore.setState({ angles, activeAngle: 0 });
}

beforeEach(() => {
  useProjectStore.setState({ angles: [], activeAngle: 0 });
  vi.restoreAllMocks();
});

it("shows an info message when there are no angles", () => {
  render(<AngleGallery />);
  expect(screen.getByText(/gallery\.no_angles/i)).toBeInTheDocument();
});

it("renders one card per angle", async () => {
  vi.spyOn(client, "analyze").mockResolvedValue({
    preview_png: "data:image/png;base64,ABC",
    result_token: "tok",
  });
  seedAngles(2);
  render(<AngleGallery />);
  await waitFor(() => {
    expect(screen.getByText("Angle 1")).toBeInTheDocument();
    expect(screen.getByText("Angle 2")).toBeInTheDocument();
  });
});

it("uses store preview for active angle (no extra API call)", async () => {
  const spy = vi.spyOn(client, "analyze").mockResolvedValue({
    preview_png: "data:image/png;base64,ABC",
    result_token: "tok",
  });
  seedAngles(2, [0]); // angle 0 already has a preview
  render(<AngleGallery />);
  await waitFor(() => {
    // Only angle 1 should have triggered analyze (angle 0 used store preview)
    expect(spy).toHaveBeenCalledTimes(1);
  });
});

it("marks the active angle with an indicator", async () => {
  vi.spyOn(client, "analyze").mockResolvedValue({
    preview_png: "data:image/png;base64,ABC", result_token: "tok",
  });
  seedAngles(2);
  render(<AngleGallery />);
  await waitFor(() => screen.getAllByAltText(/Angle/));
  expect(screen.getByText(/gallery\.active_badge/i)).toBeInTheDocument();
});

it("shows a loading indicator while preview is fetching", () => {
  // analyze never resolves → stays in loading state
  vi.spyOn(client, "analyze").mockImplementation(() => new Promise(() => {}));
  seedAngles(1);
  render(<AngleGallery />);
  expect(screen.getByText(/gallery\.loading/i)).toBeInTheDocument();
});

it("shows an error state when analyze fails for an angle", async () => {
  vi.spyOn(client, "analyze").mockRejectedValue(new Error("network"));
  seedAngles(1);
  render(<AngleGallery />);
  await waitFor(() => {
    expect(screen.getByText(/gallery\.preview_error/i)).toBeInTheDocument();
  });
});

it("skips fetch for angles without a photoId", async () => {
  const spy = vi.spyOn(client, "analyze").mockResolvedValue({
    preview_png: "data:image/png;base64,ABC", result_token: "tok",
  });
  useProjectStore.setState({
    angles: [{
      id: "a0", label: "No Photo",
      photoId: undefined as any,
      width: undefined, height: undefined,
      qualityChecks: [], book: DEFAULT_BOOK, settings: DEFAULT_SETTINGS,
    }],
    activeAngle: 0,
  });
  render(<AngleGallery />);
  // Brief wait; no fetch should fire
  await new Promise((r) => setTimeout(r, 50));
  expect(spy).not.toHaveBeenCalled();
  expect(screen.getByText(/gallery\.no_photo/i)).toBeInTheDocument();
});
```

- [ ] **Step 2: Run to verify new tests fail**

```
npm test -- --run
```
Expected: all new `AngleGallery` tests fail (component does not exist).

- [ ] **Step 3: Create `web/src/components/AngleGallery.tsx`**

```typescript
import { useEffect, useState } from "react";
import { useTranslation } from "react-i18next";
import { analyze } from "../api/client";
import { useProjectStore, activeAngleOf } from "../store/projectStore";
import type { AnalyzeRequest } from "../api/types";
import type { Angle } from "../store/projectStore";

const COLS = 3;

function buildRequest(angle: Angle): AnalyzeRequest {
  return {
    photo_id: angle.photoId,
    whole: angle.book.whole,
    regions: angle.book.drawn
      .filter((r) => !r.blank)
      .map((r) => ({
        name: r.name,
        rings: r.rings,
        palette: r.palette,
        coverage: r.coverage,
        material: r.material,
      })),
    settings: angle.settings,
  };
}

type PreviewState = string | null | "error";  // data URI | loading | error

export function AngleGallery() {
  const { t } = useTranslation();
  const angles = useProjectStore((s) => s.angles);
  const activeAngle = useProjectStore((s) => s.activeAngle);

  // Seed initial previews from store (active angle already has one from useAnalyze)
  const [previews, setPreviews] = useState<Record<string, PreviewState>>(() => {
    const init: Record<string, PreviewState> = {};
    for (const a of angles) {
      init[a.id] = a.preview ?? null;
    }
    return init;
  });

  useEffect(() => {
    let cancelled = false;

    // Reset local state when angles list changes
    const init: Record<string, PreviewState> = {};
    for (const a of angles) {
      init[a.id] = a.preview ?? null;
    }
    setPreviews(init);

    // Kick off fetches for angles without a preview
    for (const angle of angles) {
      if (angle.preview) continue;       // already rendered by useAnalyze
      if (!angle.photoId) continue;      // no photo uploaded yet

      analyze(buildRequest(angle))
        .then((res) => {
          if (!cancelled) {
            setPreviews((prev) => ({ ...prev, [angle.id]: res.preview_png }));
          }
        })
        .catch(() => {
          if (!cancelled) {
            setPreviews((prev) => ({ ...prev, [angle.id]: "error" }));
          }
        });
    }

    return () => { cancelled = true; };
  }, [angles]);

  if (angles.length === 0) {
    return (
      <p style={{ color: "#888", fontSize: 14 }}>{t("gallery.no_angles")}</p>
    );
  }

  const rows: Angle[][] = [];
  for (let i = 0; i < angles.length; i += COLS) {
    rows.push(angles.slice(i, i + COLS));
  }

  return (
    <div>
      <h3 style={{ color: "#ccc", fontWeight: 500, marginBottom: 4 }}>{t("gallery.heading")}</h3>
      <p style={{ color: "#777", fontSize: 12, marginBottom: 16 }}>{t("gallery.caption")}</p>
      {rows.map((row, ri) => (
        <div
          key={ri}
          style={{ display: "grid", gridTemplateColumns: `repeat(${COLS}, 1fr)`, gap: 16, marginBottom: 16 }}
        >
          {row.map((angle, ci) => {
            const idx = ri * COLS + ci;
            const preview = previews[angle.id];
            const isActive = idx === activeAngle;

            return (
              <div
                key={angle.id}
                style={{
                  background: "#111", borderRadius: 6, overflow: "hidden",
                  border: isActive ? "2px solid #888" : "2px solid #222",
                }}
              >
                <div style={{ position: "relative" }}>
                  {!angle.photoId ? (
                    <div
                      style={{
                        height: 160, display: "flex", alignItems: "center",
                        justifyContent: "center", color: "#555", fontSize: 13,
                      }}
                    >
                      {t("gallery.no_photo")}
                    </div>
                  ) : preview === null ? (
                    <div
                      style={{
                        height: 160, display: "flex", alignItems: "center",
                        justifyContent: "center", color: "#555", fontSize: 13,
                      }}
                    >
                      {t("gallery.loading")}
                    </div>
                  ) : preview === "error" ? (
                    <div
                      style={{
                        height: 160, display: "flex", alignItems: "center",
                        justifyContent: "center", color: "#844", fontSize: 13,
                      }}
                    >
                      {t("gallery.preview_error")}
                    </div>
                  ) : (
                    <img
                      src={preview}
                      alt={angle.label}
                      style={{ width: "100%", display: "block", objectFit: "contain" }}
                    />
                  )}
                </div>
                <div style={{ padding: "6px 8px", display: "flex", alignItems: "center", gap: 6 }}>
                  <span style={{ flex: 1, fontSize: 13, color: "#ccc", overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>
                    {angle.label}
                  </span>
                  {isActive && (
                    <span style={{ fontSize: 11, color: "#888", whiteSpace: "nowrap" }}>
                      {t("gallery.active_badge")}
                    </span>
                  )}
                </div>
              </div>
            );
          })}
        </div>
      ))}
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
git add web/src/components/AngleGallery.tsx web/src/components/AngleGallery.test.tsx
git commit -m "feat: add AngleGallery component — read-only preview grid per angle"
```

---

### Task 2: i18n keys, `AnglesTab` shell, and App wiring

**Files:**
- Modify: `web/src/i18n/locales/en.json` (add `tabs.angles` + `gallery.*` section)
- Modify: `web/src/i18n/locales/es.json` (mirror)
- Create: `web/src/components/AnglesTab.tsx` (thin wrapper — no tests needed)
- Modify: `web/src/App.tsx` (add "angles" to `MainTab`, add tab button + render)

- [ ] **Step 1: Add i18n keys to `web/src/i18n/locales/en.json`**

In the `"tabs"` object, add:
```json
"angles": "Angles"
```

Add a new top-level `"gallery"` section:
```json
"gallery": {
  "heading": "All Angles",
  "caption": "Read-only — edit palette and settings in the Studio tab.",
  "no_angles": "No angles yet. Upload a photo to get started.",
  "active_badge": "● active",
  "loading": "Rendering…",
  "preview_error": "Preview failed",
  "no_photo": "No photo"
}
```

- [ ] **Step 2: Mirror keys in `web/src/i18n/locales/es.json`**

In the `"tabs"` object, add:
```json
"angles": "Ángulos"
```

Add a new top-level `"gallery"` section:
```json
"gallery": {
  "heading": "Todos los ángulos",
  "caption": "Solo lectura — edita en la pestaña Estudio.",
  "no_angles": "Aún no hay ángulos. Sube una foto para empezar.",
  "active_badge": "● activo",
  "loading": "Renderizando…",
  "preview_error": "Error al renderizar",
  "no_photo": "Sin foto"
}
```

- [ ] **Step 3: Create `web/src/components/AnglesTab.tsx`**

```typescript
import { AngleGallery } from "./AngleGallery";

export function AnglesTab() {
  return (
    <div style={{ padding: "0 4px" }}>
      <AngleGallery />
    </div>
  );
}
```

- [ ] **Step 4: Wire `AnglesTab` into `web/src/App.tsx`**

**4a — Add import:**
```typescript
import { AnglesTab } from "./components/AnglesTab";
```

**4b — Expand the `MainTab` type:**
```typescript
type MainTab = "studio" | "paint" | "paints" | "angles";
```
(If the paints-inventory plan has already landed, the type already includes "paints" — just add "angles".)

**4c — Add the Angles tab button** in the nav block, after the Paints button:
```tsx
            <button
              style={tabBtn("angles")}
              onClick={() => setTab("angles")}
            >
              {t("tabs.angles")}
            </button>
```

**4d — Add the AnglesTab render** after the PaintsTab render:
```tsx
          {tab === "angles" && <AnglesTab />}
```

- [ ] **Step 5: Run all frontend tests — expect all pass**

```
npm test -- --run
```
Expected: all green.

- [ ] **Step 6: Smoke-test in the browser**

Start both processes and open `http://localhost:5173`. Upload a photo, analyze it, then add 2–3 angles each with a different photo. Verify:

1. "Angles" tab is visible in the nav
2. Click Angles → grid shows each angle's preview
3. Active angle has the "● active" badge and a highlighted border
4. Angles without a photo show "No photo" placeholder
5. One angle per row for 1–3 angles; two rows for 4+ angles
6. The gallery renders without affecting Studio state (switch back to Studio → active angle, palette, and preview unchanged)
7. Edit a color in Studio → switch to Angles → the active angle's preview cell updates (uses store `preview`); other angles still show their last-computed preview

- [ ] **Step 7: Commit**

```
git add web/src/components/AnglesTab.tsx web/src/App.tsx
git add web/src/i18n/locales/en.json web/src/i18n/locales/es.json
git commit -m "feat: add AnglesTab — read-only all-angles preview grid wired into App"
```

---

## Self-Review

**Spec coverage (§7 AnglesTab ← `ui/gallery_panel.py`):**
- Read-only previews ✓ — no editing in gallery
- Grid layout ✓ — 3 columns matching `_PER_ROW = 3` in Streamlit
- Active angle marked ✓ — border highlight + "● active" badge
- Per-angle rendering via `analyze_regions` ✓ — reuses `/api/analyze`
- Memoization ✓ — local `previews` state; once a preview is fetched it stays until angles change
- One bad angle doesn't blank the grid ✓ — `"error"` state shows per-cell error, rest continue
- Angles without a photo skip the fetch ✓ — `!angle.photoId` guard

**API contract (§5):**
- No new endpoints needed; gallery reuses `POST /api/analyze` ✓
- Result cache on server means re-analyzing the active angle (which just analyzed) is a cache hit ✓

**Streamlit gallery memoization analog:**
- Streamlit used `_cached_preview` keyed by `angle_signature` in session state
- React version keys by `angle.id` in local component state; re-fetches when `angles` array reference changes (e.g., after palette edit). This is slightly less aggressive than Streamlit's content-fingerprint but sufficient for a personal tool — the server result cache handles the hot path.

**Placeholder scan:** None found. All code blocks are complete and runnable.
