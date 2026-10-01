# UI pass A — fixes and quick wins Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Fix four UI bugs, name the paint on every paint-along step, explain the step images, replace silent failures with friendly error/loading states, and finish i18n coverage.

**Architecture:** Mostly frontend (React 19 + Mantine 7 + Zustand + react-i18next in `web/src`). One additive backend change: `StepImageDto` gains optional `paint_name/paint_hex/paint_code`, resolved server-side from the plan's final (post-relief-cap) palette. A shared `ErrorNotice` component carries every error state.

**Tech Stack:** Vite + React + TS, Mantine 7, Zustand, vitest + Testing Library; FastAPI + pydantic + pytest.

**Spec:** `docs/superpowers/specs/2026-10-01-ui-pass-a-fixes-design.md`

## Global Constraints

- Every new user-visible string goes in BOTH `web/src/i18n/locales/en.json` and `es.json` (same key set).
- The scheme API identifier stays `"Whole Mini"` (`region_name` / `anchor_name` sent to `/api/scheme/generate`); only its *display* is translated.
- New `StepImageDto` fields are optional with default `None` (backward compatible).
- `analyzing` / `analyzeNonce` are runtime-only angle fields; never added to `toProjectAngleDto` (`web/src/api/client.ts`).
- Band minimum stays 3 (`n <= 3` → remove disabled / no-op).
- Branch: `feat/ui-pass-a-fixes` (already exists, pushed). Commit per task. Never commit to main.
- Commands: frontend tests `cd web && npx vitest run <path>`; full frontend `cd web && npx vitest run && npx tsc -b`; backend `.venv/Scripts/python -m pytest backend/tests/<file> -q` from repo root.
- Component tests mock i18n as `vi.mock("react-i18next", () => ({ useTranslation: () => ({ t: (k: string) => k }) }))` (existing pattern) — assertions use keys.

## Review Focus

1. **Removing a middle band of a drawn region** (selected ≥ 1) must remove that region's slot, not the whole-mini's — test `removeBand` with `selected = 1`.
2. **Relief-capped plan** (palette shorter than requested): step paint fields must come from `plan.palette`, never index out of range — test with a 1-band capped plan (`palette` shorter than step indices must not crash; missing → `None`).
3. **Retry after a step-fetch error keeps the selected region tab** (doesn't jump back to region 0) — PaintTab test.
4. **Analyze validation early-return** (invalid hex mid-typing) must not leave `analyzing` stuck `true` — useAnalyze sets analyzing only after validation; test in Task 8.
5. **"Owned paints only" with zero owned paints** sends `owned_codes: []` and shows the hint — GeneratePanel test.

---

### Task 1: `ErrorNotice` component + `errors` locale section

**Files:**
- Create: `web/src/components/ErrorNotice.tsx`
- Test: `web/src/components/ErrorNotice.test.tsx`
- Modify: `web/src/i18n/locales/en.json`, `web/src/i18n/locales/es.json` (add top-level `errors`)

**Interfaces:**
- Produces: `ErrorNotice({ message: string; detail?: string; onRetry?: () => void })` — Mantine `Alert` (color red), message as body, detail in small dimmed text, a Retry button (label `t("errors.retry")`) only when `onRetry` given.
- Produces locale keys: `errors.retry`, `errors.steps`, `errors.analyze`, `errors.upload`, `errors.generate`, `errors.catalog`, `errors.import`, `errors.project_save`, `errors.project_load`, `errors.project_delete`, `errors.project_download`, `errors.project_upload`.

- [ ] **Step 1: Write the failing test**

```tsx
// web/src/components/ErrorNotice.test.tsx
import { describe, it, expect, vi } from "vitest";
import { render, screen, fireEvent } from "@testing-library/react";
import { MantineProvider } from "@mantine/core";
import { ErrorNotice } from "./ErrorNotice";

vi.mock("react-i18next", () => ({ useTranslation: () => ({ t: (k: string) => k }) }));

const wrap = (ui: React.ReactNode) => render(<MantineProvider>{ui}</MantineProvider>);

describe("ErrorNotice", () => {
  it("shows message and detail", () => {
    wrap(<ErrorNotice message="Could not load" detail="500 boom" />);
    expect(screen.getByText("Could not load")).toBeTruthy();
    expect(screen.getByText("500 boom")).toBeTruthy();
  });
  it("has no retry button without onRetry", () => {
    wrap(<ErrorNotice message="x" />);
    expect(screen.queryByText("errors.retry")).toBeNull();
  });
  it("calls onRetry", () => {
    const onRetry = vi.fn();
    wrap(<ErrorNotice message="x" onRetry={onRetry} />);
    fireEvent.click(screen.getByText("errors.retry"));
    expect(onRetry).toHaveBeenCalledOnce();
  });
});
```

- [ ] **Step 2: Run** `cd web && npx vitest run src/components/ErrorNotice.test.tsx` — Expected: FAIL (module not found).

- [ ] **Step 3: Implement**

```tsx
// web/src/components/ErrorNotice.tsx
import { useTranslation } from "react-i18next";
import { Alert, Button, Stack, Text } from "@mantine/core";

export interface ErrorNoticeProps { message: string; detail?: string; onRetry?: () => void; }

/** Friendly error box: translated message, optional raw detail (for bug reports), optional Retry. */
export function ErrorNotice({ message, detail, onRetry }: ErrorNoticeProps) {
  const { t } = useTranslation();
  return (
    <Alert color="red" variant="light" role="alert">
      <Stack gap={6} align="flex-start">
        <Text size="sm">{message}</Text>
        {detail && <Text size="xs" c="dimmed" style={{ wordBreak: "break-word" }}>{detail}</Text>}
        {onRetry && <Button size="xs" variant="light" color="red" onClick={onRetry}>{t("errors.retry")}</Button>}
      </Stack>
    </Alert>
  );
}
```

Add to `en.json` (top level, after `gallery`):

```json
"errors": {
  "retry": "Try again",
  "steps": "Couldn't load the painting steps.",
  "analyze": "Couldn't update the preview.",
  "upload": "Couldn't upload that photo. Try a PNG or JPEG.",
  "generate": "Couldn't generate a colour scheme.",
  "catalog": "Couldn't load the paint catalogue.",
  "import": "Import failed.",
  "project_save": "Save failed.",
  "project_load": "Load failed.",
  "project_delete": "Delete failed.",
  "project_download": "Download failed.",
  "project_upload": "Import failed."
}
```

Add to `es.json`:

```json
"errors": {
  "retry": "Reintentar",
  "steps": "No se pudieron cargar los pasos de pintura.",
  "analyze": "No se pudo actualizar la vista previa.",
  "upload": "No se pudo subir esa foto. Prueba con PNG o JPEG.",
  "generate": "No se pudo generar un esquema de color.",
  "catalog": "No se pudo cargar el catálogo de pinturas.",
  "import": "Error al importar.",
  "project_save": "Error al guardar.",
  "project_load": "Error al cargar.",
  "project_delete": "Error al eliminar.",
  "project_download": "Error al descargar.",
  "project_upload": "Error al importar."
}
```

- [ ] **Step 4: Run** the test again — Expected: PASS.
- [ ] **Step 5: Commit** `git add web/src/components/ErrorNotice* web/src/i18n/locales && git commit -m "feat(web): ErrorNotice component + errors locale section"`

---

### Task 2: Backend — paint fields on step DTOs

**Files:**
- Modify: `backend/schemas.py:111-118` (`StepImageDto`)
- Modify: `backend/main.py:141-168` (`_plan_to_dto`)
- Modify: `web/src/api/types.ts:59-67` (`StepImageDto`)
- Test: `backend/tests/test_steps.py`

**Interfaces:**
- Produces: `StepImageDto.paint_name: str | None`, `paint_hex: str | None`, `paint_code: str | None` (TS: `paint_name?: string | null` etc.).
- Mapping (from `plan.palette`, the final post-cap palette): band step `k` → `palette[k]`; edge steps: if the plan has 2 edge steps → first `palette[-2]`, second `palette[-1]`; 1 edge step → `palette[-1]`; other kinds, empty palette or out-of-range index → all `None`. Empty `code` string → `None`.

- [ ] **Step 1: Write the failing tests** (append to `backend/tests/test_steps.py`; reuses `_png_bytes`/`client` already in the file)

```python
def _analyze_with(n_bands: int, settings: dict) -> str:
    r = client.post("/api/photo", files={"file": ("m.png", _png_bytes(), "image/png")})
    photo_id = r.json()["photo_id"]
    palette = [{"name": f"p{i}", "hex": f"#{20 + 40 * i:02x}{20 + 40 * i:02x}{20 + 40 * i:02x}",
                "code": f"C{i}"} for i in range(n_bands)]
    req = {"photo_id": photo_id,
           "whole": {"palette": palette, "coverage": [1.0 / n_bands] * n_bands, "material": "matte"},
           "settings": settings}
    r = client.post("/api/analyze", json=req)
    assert r.status_code == 200
    return r.json()["result_token"]


def test_band_steps_carry_their_paint():
    token = _analyze_with(3, {"edge_hl": False, "relief_cap": False})
    steps = client.get("/api/steps", params={"token": token}).json()["plans"][0]["steps"]
    bands = [s for s in steps if s["kind"] == "band"]
    assert [s["paint_name"] for s in bands] == ["p0", "p1", "p2"]
    assert [s["paint_code"] for s in bands] == ["C0", "C1", "C2"]
    assert all(s["paint_hex"].startswith("#") for s in bands)


def test_single_edge_step_uses_lightest_paint():
    token = _analyze_with(3, {"edge_hl": True, "edge_extreme": False, "relief_cap": False})
    steps = client.get("/api/steps", params={"token": token}).json()["plans"][0]["steps"]
    edges = [s for s in steps if s["kind"] == "edge"]
    assert len(edges) == 1
    assert edges[0]["paint_name"] == "p2"


def test_two_tier_edge_steps_use_top_two_paints():
    token = _analyze_with(5, {"edge_hl": True, "edge_extreme": True, "relief_cap": False})
    steps = client.get("/api/steps", params={"token": token}).json()["plans"][0]["steps"]
    edges = [s for s in steps if s["kind"] == "edge"]
    assert [s["paint_name"] for s in edges] == ["p3", "p4"]
```

Add a pure unit test of the mapping helper for the capped / out-of-range case (Review Focus #2):

```python
from types import SimpleNamespace
from backend.main import _step_paint
from mini_highlight_advisor.palette import PaintColor


def test_step_paint_out_of_range_and_missing_palette_is_none():
    plan = SimpleNamespace(palette=[PaintColor("only", "#101010")])
    band5 = SimpleNamespace(kind="band", index=5, label=None)
    assert _step_paint(plan, band5, edge_pos=None, n_edges=0) is None
    assert _step_paint(SimpleNamespace(palette=None), band5, None, 0) is None
    shade = SimpleNamespace(kind="shade", index=1, label="Recess Shade")
    assert _step_paint(plan, shade, None, 0) is None
```

- [ ] **Step 2: Run** `.venv/Scripts/python -m pytest backend/tests/test_steps.py -q` — Expected: FAIL (KeyError `paint_name` / ImportError `_step_paint`).

- [ ] **Step 3: Implement**

`backend/schemas.py` — add to `StepImageDto` after `is_last: bool`:

```python
    paint_name: str | None = None
    paint_hex: str | None = None
    paint_code: str | None = None
```

`backend/main.py` — add above `_plan_to_dto`:

```python
def _step_paint(plan, step, edge_pos: int | None, n_edges: int):
    """The PaintColor a step is painted with, from the plan's FINAL palette
    (after relief capping), or None. Mirrors plan_region/edge_steps: bands use
    palette[k]; a two-tier edge pair uses palette[-2] then palette[-1]; a single
    edge step uses palette[-1]. Shade/other kinds have no catalogue paint."""
    pal = getattr(plan, "palette", None) or []
    if not pal:
        return None
    if step.kind == "band":
        return pal[step.index] if 0 <= step.index < len(pal) else None
    if step.kind == "edge" and edge_pos is not None:
        if n_edges == 2 and len(pal) >= 2:
            return pal[-2] if edge_pos == 0 else pal[-1]
        return pal[-1]
    return None
```

In `_plan_to_dto`, before the loop:

```python
    edge_steps = [s for s in plan.steps if s.kind == "edge"]
    n_edges = len(edge_steps)
```

and inside the loop, before `steps_out.append(...)`:

```python
        edge_pos = next((i for i, s in enumerate(edge_steps) if s is step), None)
        paint = _step_paint(plan, step, edge_pos, n_edges)
```

then pass to `StepImageDto(...)`:

```python
            paint_name=paint.name if paint else None,
            paint_hex=paint.hex if paint else None,
            paint_code=(paint.code or None) if paint else None,
```

`web/src/api/types.ts` — add to `StepImageDto`:

```ts
  paint_name?: string | null;
  paint_hex?: string | null;
  paint_code?: string | null;
```

- [ ] **Step 4: Run** `.venv/Scripts/python -m pytest backend/tests -q` — Expected: all PASS.
- [ ] **Step 5: Commit** `git add backend web/src/api/types.ts && git commit -m "feat(api): step DTOs carry the paint (name/hex/code) from the final palette"`

---

### Task 3: StepList — paint in header, hint line, clearer captions

**Files:**
- Modify: `web/src/components/StepList.tsx`
- Modify: `web/src/i18n/locales/en.json`, `es.json` (`paint` section)
- Test: `web/src/components/StepList.test.tsx`

**Interfaces:**
- Consumes: `StepImageDto.paint_name/paint_hex/paint_code` (Task 2).
- Produces locale keys `paint.steps_hint`; changes values of `paint.step_cumulative`, `paint.step_exact`.

- [ ] **Step 1: Write the failing tests** (add to `StepList.test.tsx`)

```tsx
  it("shows the paint name, code and swatch when the step carries a paint", () => {
    const withPaint: RegionPlanDto = { ...plan, steps: [
      { ...makeStep(0, true), paint_name: "Ivory", paint_hex: "#f0e8d0", paint_code: "70.918" },
    ] };
    render(<MantineProvider><StepList plan={withPaint} /></MantineProvider>);
    expect(screen.getByText(/Ivory/)).toBeTruthy();
    expect(screen.getByText(/70\.918/)).toBeTruthy();
    expect(screen.getByTestId("step-swatch")).toBeTruthy();
  });

  it("keeps the plain header when no paint is present", () => {
    render(<MantineProvider><StepList plan={plan} /></MantineProvider>);
    expect(screen.queryByTestId("step-swatch")).toBeNull();
  });

  it("renders the steps hint once", () => {
    render(<MantineProvider><StepList plan={plan} /></MantineProvider>);
    expect(screen.getAllByText("paint.steps_hint")).toHaveLength(1);
  });
```

- [ ] **Step 2: Run** `cd web && npx vitest run src/components/StepList.test.tsx` — Expected: the 3 new tests FAIL.

- [ ] **Step 3: Implement** — replace the header line in `StepCard` (`StepList.tsx:10`) and add the hint in `StepList`:

```tsx
import { ColorSwatch, Group, Image, Paper, SimpleGrid, Stack, Text } from "@mantine/core";
// ...
function StepHeader({ step }: { step: StepImageDto }) {
  const { t } = useTranslation();
  const role = t(ROLE_KEY[step.label] ?? step.label);
  if (!step.paint_name) return <Text fw={600} mb="xs">{role}</Text>;
  return (
    <Group gap="xs" mb="xs" wrap="nowrap">
      {step.paint_hex && <ColorSwatch data-testid="step-swatch" color={step.paint_hex} size={20} />}
      <Text fw={600}>
        {role} — {step.paint_name}
        {step.paint_code && <Text span c="dimmed" fw={400}> · {step.paint_code}</Text>}
      </Text>
    </Group>
  );
}
```

In `StepCard` replace `<Text fw={600} mb="xs">{t(ROLE_KEY[step.label] ?? step.label)}</Text>` with `<StepHeader step={step} />`.

In `StepList`:

```tsx
export function StepList({ plan }: StepListProps) {
  const { t } = useTranslation();
  return (
    <Stack gap="xs">
      <Text size="sm" c="dimmed">{t("paint.steps_hint")}</Text>
      {plan.steps.map((step) => (
        <StepCard key={`${step.kind}-${step.index}`} step={step} />
      ))}
    </Stack>
  );
}
```

Locale `paint` section — en:

```json
"step_cumulative": "After this layer",
"step_exact": "What stays visible at the end",
"steps_hint": "Paint each layer over the pink area. Later, lighter layers go on top, so only part of each layer stays visible at the end."
```

es:

```json
"step_cumulative": "Tras esta capa",
"step_exact": "Lo que queda visible al final",
"steps_hint": "Pinta cada capa sobre la zona rosa. Las capas siguientes, más claras, van encima, así que al final solo queda visible una parte de cada capa."
```

- [ ] **Step 4: Run** the StepList tests — Expected: all PASS.
- [ ] **Step 5: Commit** `git commit -am "feat(web): step cards name their paint; explain step images"`

---

### Task 4: Delete the clicked band, not the last one

**Files:**
- Modify: `web/src/store/projectStore.ts` (interface ~line 65, impl after `setBandCount` ~line 217)
- Modify: `web/src/components/colour/BandCard.tsx:28,66`
- Test: `web/src/store/projectStore.test.ts`, `web/src/components/colour/BandCard.test.tsx`

**Interfaces:**
- Produces: store action `removeBand(i: number): void` — removes slot `i` of the SELECTED region's palette + coverage, renormalises coverage to sum 1; no-op if `n <= 3` or `i` out of range.

- [ ] **Step 1: Write the failing tests**

`projectStore.test.ts` (inside the existing `describe`, uses the file's `photo()` helper):

```ts
  it("removeBand drops the chosen slot of the selected region and renormalises", () => {
    const st = useProjectStore.getState();
    st.initFromPhoto(photo("p1"));
    st.setPaletteAt(0, ["a", "b", "c", "d"].map((n) => ({ name: n, hex: "#101010" })));
    st.setCoverage([0.4, 0.3, 0.2, 0.1]);
    useProjectStore.getState().removeBand(1);
    const w = activeBookOf(useProjectStore.getState())!.whole;
    expect(w.palette.map((p) => p.name)).toEqual(["a", "c", "d"]);
    expect(w.coverage.reduce((x, y) => x + y, 0)).toBeCloseTo(1);
    expect(w.coverage[0]).toBeCloseTo(0.4 / 0.7);
  });

  it("removeBand targets a drawn region when it is selected", () => {
    const st = useProjectStore.getState();
    st.initFromPhoto(photo("p1"));
    st.addRegion([[[0, 0], [1, 0], [1, 1]]], "cloak");          // selected = 1
    st.setPaletteAt(1, ["w", "x", "y", "z"].map((n) => ({ name: n, hex: "#202020" })));
    st.setCoverage([0.25, 0.25, 0.25, 0.25]);
    useProjectStore.getState().removeBand(2);
    const b = activeBookOf(useProjectStore.getState())!;
    expect(b.drawn[0].palette.map((p) => p.name)).toEqual(["w", "x", "z"]);
    expect(b.whole.palette).toHaveLength(2);                      // whole untouched
  });

  it("removeBand is a no-op at the 3-band floor", () => {
    const st = useProjectStore.getState();
    st.initFromPhoto(photo("p1"));
    st.setPaletteAt(0, ["a", "b", "c"].map((n) => ({ name: n, hex: "#101010" })));
    st.setCoverage([0.5, 0.3, 0.2]);
    useProjectStore.getState().removeBand(0);
    expect(activeBookOf(useProjectStore.getState())!.whole.palette).toHaveLength(3);
  });
```

(Check `setPaletteAt(g, palette)` signature in the store before running; it exists at `projectStore.ts:75`.)

`BandCard.test.tsx` — change the store mock to capture calls via `vi.hoisted`, and add a test:

```tsx
const { removeBand, snapshotUndo } = vi.hoisted(() => ({ removeBand: vi.fn(), snapshotUndo: vi.fn() }));
vi.mock("../../store/projectStore", () => ({
  useProjectStore: (sel: any) => sel({
    setPaletteSlot: () => {}, setHexSlot: () => {}, setBandCount: () => {},
    removeBand, snapshotUndo,
  }),
}));
// ...
  it("✕ removes its own band index (with an undo snapshot)", () => {
    renderCard({ i: 1, n: 4 });
    fireEvent.click(screen.getByLabelText("colour.delete_band"));
    expect(snapshotUndo).toHaveBeenCalled();
    expect(removeBand).toHaveBeenCalledWith(1);
  });
```

(add `fireEvent` to the testing-library import.)

- [ ] **Step 2: Run** `cd web && npx vitest run src/store/projectStore.test.ts src/components/colour/BandCard.test.tsx` — Expected: new tests FAIL.

- [ ] **Step 3: Implement**

Interface (next to `setBandCount(n: number): void;`): `removeBand(i: number): void;`

Impl (after `setBandCount`):

```ts
  removeBand: (i) => set((s) => patchBook(s, (b) => {
    const cur = b.selected === 0 ? b.whole : b.drawn[b.selected - 1];
    const n = cur.palette.length;
    if (n <= 3 || i < 0 || i >= n) return b;
    const palette = cur.palette.filter((_, k) => k !== i);
    const raw = cur.coverage.filter((_, k) => k !== i);
    const sum = raw.reduce((a, c) => a + c, 0);
    const coverage = sum > 0 ? raw.map((v) => v / sum) : raw.map(() => 1 / raw.length);
    if (b.selected === 0) return { ...b, whole: { ...b.whole, palette, coverage } };
    const drawn = b.drawn.slice();
    drawn[b.selected - 1] = { ...drawn[b.selected - 1], palette, coverage };
    return { ...b, drawn };
  })),
```

`BandCard.tsx`: replace `const setBandCount = useProjectStore((s) => s.setBandCount);` with

```tsx
  const removeBand = useProjectStore((s) => s.removeBand);
  const snapshotUndo = useProjectStore((s) => s.snapshotUndo);
```

and the onClick at line 66 with `onClick={() => { if (n > 3) { snapshotUndo(); removeBand(i); } }}`.

- [ ] **Step 4: Run** the two test files — Expected: PASS.
- [ ] **Step 5: Commit** `git commit -am "fix(web): band ✕ removes the clicked band (undoable)"`

---

### Task 5: GeneratePanel — owned codes only, error notice, translated region label

**Files:**
- Modify: `web/src/components/colour/GeneratePanel.tsx`
- Modify: locales (`colour.owned_only_none`)
- Test: `web/src/components/colour/GeneratePanel.test.tsx`

**Interfaces:**
- Consumes: `ErrorNotice` (Task 1), `useCatalogStore(s => s.ownedCodes): Set<string>`.

- [ ] **Step 1: Write the failing tests** — change the catalog mock to hoisted state and add tests:

```tsx
import { fireEvent, waitFor } from "@testing-library/react";
import * as client from "../../api/client";

const cat = vi.hoisted(() => ({ paints: [] as any[], ownedCodes: new Set<string>() }));
vi.mock("../../store/catalogStore", () => ({ useCatalogStore: (sel: any) => sel(cat) }));

// in beforeEach also: cat.paints = [{ code: "V1" }, { code: "V2" }] as any; cat.ownedCodes = new Set(["V1"]); vi.restoreAllMocks();

  it("owned-only sends owned codes, not the whole catalogue", async () => {
    const spy = vi.spyOn(client, "generateScheme").mockResolvedValue({ palettes: {} } as any);
    render(<MantineProvider><GeneratePanel /></MantineProvider>);
    fireEvent.click(screen.getByLabelText("colour.owned_only"));
    fireEvent.click(screen.getByText("colour.generate"));
    await waitFor(() => expect(spy).toHaveBeenCalled());
    expect(spy.mock.calls[0][0].owned_codes).toEqual(["V1"]);
    expect(spy.mock.calls[0][0].anchor_name).toBe("Whole Mini");
  });

  it("owned-only with nothing owned sends [] and shows a hint", async () => {
    cat.ownedCodes = new Set();
    const spy = vi.spyOn(client, "generateScheme").mockResolvedValue({ palettes: {} } as any);
    render(<MantineProvider><GeneratePanel /></MantineProvider>);
    fireEvent.click(screen.getByLabelText("colour.owned_only"));
    expect(screen.getByText("colour.owned_only_none")).toBeTruthy();
    fireEvent.click(screen.getByText("colour.generate"));
    await waitFor(() => expect(spy).toHaveBeenCalled());
    expect(spy.mock.calls[0][0].owned_codes).toEqual([]);
  });

  it("shows an error notice when generation fails", async () => {
    vi.spyOn(client, "generateScheme").mockRejectedValue(new Error("500 boom"));
    render(<MantineProvider><GeneratePanel /></MantineProvider>);
    fireEvent.click(screen.getByText("colour.generate"));
    expect(await screen.findByText("errors.generate")).toBeTruthy();
    expect(screen.getByText("500 boom")).toBeTruthy();
  });

  it("displays the translated whole-mini label in the anchor select", () => {
    render(<MantineProvider><GeneratePanel /></MantineProvider>);
    expect(screen.getByRole("option", { name: "region.whole_mini" })).toBeTruthy();
  });
```

- [ ] **Step 2: Run** `cd web && npx vitest run src/components/colour/GeneratePanel.test.tsx` — Expected: new tests FAIL.

- [ ] **Step 3: Implement** in `GeneratePanel.tsx`:

```tsx
import { ErrorNotice } from "../ErrorNotice";

const WHOLE_MINI_ID = "Whole Mini";   // API identifier — never translate
// in component:
  const owned = useCatalogStore((s) => s.ownedCodes);
  const [error, setError] = useState<string | null>(null);
// replace regionNames / ownedCodes lines:
  const regionNames = [WHOLE_MINI_ID, ...book.drawn.map((r) => r.name)];
  const regionLabels = [t("region.whole_mini"), ...book.drawn.map((r) => r.name)];
  const ownedCodes = ownedOnly ? Array.from(owned) : [];
```

Remove the now-unused `catalogPaints` selector. In `handleGenerate`: `setLoading(true); setError(null);` and add `catch (e) { setError(e instanceof Error ? e.message : String(e)); }` before `finally`; replace `?? "Whole Mini"` with `?? WHOLE_MINI_ID`. Anchor `<option>` text uses `regionLabels[i]`. Toggle `aria-label={t("colour.toggle_generate")}`. After the checkbox/button `Group`:

```tsx
          {ownedOnly && owned.size === 0 && (
            <Text size="xs" c="dimmed">{t("colour.owned_only_none")}</Text>
          )}
          {error && <ErrorNotice message={t("errors.generate")} detail={error} />}
```

Locales `colour`: en `"owned_only_none": "You haven't marked any paints as owned yet — tick them in the Paint Collection tab."`, `"toggle_generate": "Show or hide the scheme generator"`; es `"owned_only_none": "Aún no has marcado pinturas como tuyas — márcalas en la pestaña Colección de pinturas."`, `"toggle_generate": "Mostrar u ocultar el generador de esquemas"`.

Update the existing collapsed-state test if it relied on `aria-label="toggle generate"` (it uses `data-testid`, so no change expected).

- [ ] **Step 4: Run** the GeneratePanel tests — Expected: PASS.
- [ ] **Step 5: Commit** `git commit -am "fix(web): owned-only scheme generation uses owned paints; surface errors"`

---

### Task 6: Studio import syncs the collection; "+ angle" downscales

**Files:**
- Modify: `web/src/components/colour/RecipeManager.tsx`
- Modify: `web/src/components/AngleBar.tsx`
- Create: `web/src/components/colour/RecipeManager.test.tsx`
- Modify: `web/src/components/AngleBar.test.tsx`
- Modify: locales (`recipes.import_success`, `angles.add`)

**Interfaces:**
- Consumes: `useCatalogStore(s => s.setOwnedFromImport)`, `importCollection(file): Promise<{ owned: string[] }>`, `downscaleImage(blob): Promise<Blob>` (`lib/downscale`), `ErrorNotice`.

- [ ] **Step 1: Write the failing tests**

```tsx
// web/src/components/colour/RecipeManager.test.tsx
import { it, expect, vi, beforeEach } from "vitest";
import { render, screen, fireEvent, waitFor } from "@testing-library/react";
import { MantineProvider } from "@mantine/core";
import { RecipeManager } from "./RecipeManager";
import { useCatalogStore } from "../../store/catalogStore";
import * as client from "../../api/client";

vi.mock("react-i18next", () => ({ useTranslation: () => ({ t: (k: string) => k }) }));
beforeEach(() => { vi.restoreAllMocks(); useCatalogStore.setState({ ownedCodes: new Set() }); });

it("collection import from Studio updates the owned set", async () => {
  vi.spyOn(client, "importCollection").mockResolvedValue({ owned: ["V1", "V2"] } as any);
  const { container } = render(<MantineProvider><RecipeManager /></MantineProvider>);
  const input = container.querySelector('input[data-kind="collection"]') as HTMLInputElement;
  fireEvent.change(input, { target: { files: [new File(["{}"], "c.json")] } });
  await waitFor(() => expect(useCatalogStore.getState().ownedCodes.has("V2")).toBe(true));
});

it("shows an error notice when an import fails", async () => {
  vi.spyOn(client, "importRecipes").mockRejectedValue(new Error("400 bad file"));
  const { container } = render(<MantineProvider><RecipeManager /></MantineProvider>);
  const input = container.querySelector('input[data-kind="recipes"]') as HTMLInputElement;
  fireEvent.change(input, { target: { files: [new File(["{}"], "r.json")] } });
  expect(await screen.findByText("errors.import")).toBeTruthy();
});
```

`AngleBar.test.tsx` — add:

```tsx
import { vi, afterEach } from "vitest";
import * as client from "../api/client";
import * as ds from "../lib/downscale";
afterEach(() => vi.restoreAllMocks());

  it("+ angle downscales the photo before uploading", async () => {
    useProjectStore.getState().initFromPhoto(photo("p0"));
    const small = new Blob(["small"]);
    const down = vi.spyOn(ds, "downscaleImage").mockResolvedValue(small);
    const up = vi.spyOn(client, "uploadPhoto").mockResolvedValue(photo("p1") as any);
    const { container } = render(<MantineProvider><AngleBar /></MantineProvider>);
    const input = container.querySelector('input[type="file"]') as HTMLInputElement;
    fireEvent.change(input, { target: { files: [new File(["big"], "b.png")] } });
    await waitFor(() => expect(up).toHaveBeenCalledWith(small, "b.png"));
    expect(down).toHaveBeenCalled();
  });
```

(If `vi.spyOn` on an ES module namespace fails in this setup, use `vi.mock("../lib/downscale", () => ({ downscaleImage: vi.fn() }))` with `vi.hoisted` instead — the existing `PhotoUploader.test.tsx` spies on `client` successfully, so namespace spying works here.)

- [ ] **Step 2: Run** `cd web && npx vitest run src/components/colour/RecipeManager.test.tsx src/components/AngleBar.test.tsx` — Expected: new tests FAIL.

- [ ] **Step 3: Implement**

`RecipeManager.tsx`:

```tsx
import { useRef, useState } from "react";
import { Button, Group, Stack, Text } from "@mantine/core";
import { useCatalogStore } from "../../store/catalogStore";
import { ErrorNotice } from "../ErrorNotice";
// in component:
  const setOwnedFromImport = useCatalogStore((s) => s.setOwnedFromImport);
  const [error, setError] = useState<string | null>(null);
  const [ok, setOk] = useState<string | null>(null);

  async function run(fn: () => Promise<void>) {
    setError(null); setOk(null);
    try { await fn(); } catch (e) { setError(e instanceof Error ? e.message : String(e)); }
  }
  async function onRecipes(f: File) { await run(async () => { await importRecipes(f); setOk(t("recipes.import_success")); }); }
  async function onCollection(f: File) {
    await run(async () => {
      const res = await importCollection(f);
      setOwnedFromImport(res.owned);
      setOk(t("paints.import_success", { count: res.owned.length }));
    });
  }
```

Wrap the existing `Group` in `<Stack gap={4}>`; the two `<input>`s get `data-kind="recipes"` / `data-kind="collection"` and `onChange={(e) => { const f = e.target.files?.[0]; if (f) { onRecipes(f); e.target.value = ""; } }}` (collection: `onCollection`). Export buttons call `run(async () => triggerDownload(...))`. Below the group:

```tsx
      {ok && <Text size="xs" c="green">{ok}</Text>}
      {error && <ErrorNotice message={t("errors.import")} detail={error} />}
```

`AngleBar.tsx`: `import { downscaleImage } from "../lib/downscale";` and `addAngle(await uploadPhoto(await downscaleImage(file), file.name));`. Replace `+ angle` text with `{t("angles.add")}` (add `const { t } = useTranslation();`).

Locales: en `recipes.import_success`: `"Recipes imported"`; new top-level `"angles": { "add": "+ Add angle", "default_label": "Angle {{n}}", "rename": "Rename angle", "remove": "Remove angle" }`. es `recipes.import_success`: `"Recetas importadas"`; `"angles": { "add": "+ Añadir ángulo", "default_label": "Ángulo {{n}}", "rename": "Renombrar ángulo", "remove": "Eliminar ángulo" }`.

(`AngleBar.test.tsx` has no i18n mock; real i18n resolves `angles.add` to "+ Add angle" — fine.)

- [ ] **Step 4: Run** the two files — Expected: PASS.
- [ ] **Step 5: Commit** `git commit -am "fix(web): Studio collection import syncs owned paints; + angle downscales"`

---

### Task 7: PaintTab — loading text, friendly error, retry

**Files:**
- Modify: `web/src/components/PaintTab.tsx:30-125`
- Modify: locales (`paint.loading` value)
- Test: `web/src/components/PaintTab.test.tsx`

**Interfaces:**
- Consumes: `ErrorNotice`.

- [ ] **Step 1: Write the failing tests** (add to `PaintTab.test.tsx`; uses its `MANIFEST`/`planOf`)

```tsx
  it("shows loading text while the manifest loads", async () => {
    vi.spyOn(client, "fetchPlanNames").mockReturnValue(new Promise(() => {}));
    render(<MantineProvider><PaintTab /></MantineProvider>);
    expect(await screen.findByText("paint.loading")).toBeTruthy();
  });

  it("manifest error shows a friendly notice and Retry refetches", async () => {
    const names = vi.spyOn(client, "fetchPlanNames")
      .mockRejectedValueOnce(new Error("500 boom"))
      .mockResolvedValue(MANIFEST);
    vi.spyOn(client, "fetchSteps").mockImplementation(async (_t, n) => planOf(n as string));
    render(<MantineProvider><PaintTab /></MantineProvider>);
    expect(await screen.findByText("errors.steps")).toBeTruthy();
    fireEvent.click(screen.getByText("errors.retry"));
    await waitFor(() => expect(names).toHaveBeenCalledTimes(2));
    expect(await screen.findByTestId("step-list")).toBeTruthy();
  });

  it("retry after a step error keeps the selected region", async () => {
    vi.spyOn(client, "fetchPlanNames").mockResolvedValue(MANIFEST);
    const steps = vi.spyOn(client, "fetchSteps").mockImplementation(async (_t, n) => {
      if (n === "Cloak" && steps.mock.calls.filter((c) => c[1] === "Cloak").length === 1) throw new Error("500 x");
      return planOf(n as string);
    });
    render(<MantineProvider><PaintTab /></MantineProvider>);
    fireEvent.click(await screen.findByRole("tab", { name: "Cloak" }));
    expect(await screen.findByText("errors.steps")).toBeTruthy();
    fireEvent.click(screen.getByText("errors.retry"));
    expect(await screen.findByText("Cloak", { selector: "[data-testid=step-list]" })).toBeTruthy();
  });
```

- [ ] **Step 2: Run** `cd web && npx vitest run src/components/PaintTab.test.tsx` — Expected: new tests FAIL.

- [ ] **Step 3: Implement** in `PaintTab.tsx`:

- `import { ErrorNotice } from "./ErrorNotice";` and `Group` from Mantine.
- New state: `const [retryNonce, setRetryNonce] = useState(0);`
- Manifest effect deps: `[token, retryNonce]`. Step effect deps: `[token, active, cache, setPreview, retryNonce]`.
- Retry:

```tsx
  function retry() {
    setError(null);
    if (!names) loadedNamesToken.current = undefined;   // manifest failed → refetch it
    setRetryNonce((n) => n + 1);                          // step failed → effect re-runs for `active`
  }
  const loading = (
    <Center mt="xl"><Group gap="xs"><Loader size="sm" /><Text size="sm" c="dimmed">{t("paint.loading")}</Text></Group></Center>
  );
```

- Replace `if (namesLoading) return <Center ...>` with `if (namesLoading) return loading;`
- Replace `if (error) return <Text c="red">{error}</Text>;` with
  `if (error) return <ErrorNotice message={t("errors.steps")} detail={error} onRetry={retry} />;`
  — but only when names are absent; when names exist, render the tabs and put the notice inside the active panel so the selection stays visible. Concretely: `if (error && !names) return <ErrorNotice .../>;` and inside each `Tabs.Panel`: `{cache[n] ? <StepList .../> : error && n === active ? <ErrorNotice message={t("errors.steps")} detail={error} onRetry={retry} /> : stepLoading ? loading : null}`.

Locale `paint.loading` — en `"Loading steps… the first time can take up to a minute."`, es `"Cargando pasos… la primera vez puede tardar hasta un minuto."`

- [ ] **Step 4: Run** the PaintTab tests — Expected: all PASS (existing ones too).
- [ ] **Step 5: Commit** `git commit -am "feat(web): Paint tab loading text, friendly errors and retry"`

---

### Task 8: Preview — "updating" badge, first-render loader, error + retry

**Files:**
- Modify: `web/src/store/projectStore.ts` (Angle type line 41-46, State interface, impls)
- Modify: `web/src/hooks/useAnalyze.ts`
- Modify: `web/src/components/PreviewImage.tsx`
- Modify: locales (new `preview` section)
- Test: `web/src/store/projectStore.test.ts`, create `web/src/hooks/useAnalyze.test.tsx`, create `web/src/components/PreviewImage.test.tsx`

**Interfaces:**
- Produces: `Angle.analyzing?: boolean`, `Angle.analyzeNonce?: number`; actions `setAnalyzing(on: boolean): void` (active angle), `retryAnalyze(): void` (clears `error`, increments `analyzeNonce`).
- `useAnalyze` effect deps include `angle?.analyzeNonce`.

- [ ] **Step 1: Write the failing tests**

`projectStore.test.ts`:

```ts
  it("retryAnalyze clears the error and bumps the nonce; setAnalyzing toggles", () => {
    const st = useProjectStore.getState();
    st.initFromPhoto(photo("p1"));
    st.setError("500 boom");
    st.setAnalyzing(true);
    useProjectStore.getState().retryAnalyze();
    const a = useProjectStore.getState().angles[0];
    expect(a.error).toBeUndefined();
    expect(a.analyzeNonce).toBe(1);
    expect(a.analyzing).toBe(true);
  });
```

`web/src/hooks/useAnalyze.test.tsx`:

```tsx
import { it, expect, vi, beforeEach } from "vitest";
import { renderHook, waitFor } from "@testing-library/react";
import { useAnalyze } from "./useAnalyze";
import { useProjectStore } from "../store/projectStore";
import * as client from "../api/client";

const photo = { photo_id: "p1", width: 10, height: 10, quality_checks: [],
  default_whole: { palette: [{ name: "a", hex: "#000000" }], coverage: [1], material: "matte" } };
beforeEach(() => { vi.restoreAllMocks(); useProjectStore.setState(useProjectStore.getInitialState(), true); });

it("sets analyzing during the request and clears it after", async () => {
  let resolve!: (v: any) => void;
  vi.spyOn(client, "analyze").mockReturnValue(new Promise((r) => { resolve = r; }));
  useProjectStore.getState().initFromPhoto(photo as any);
  renderHook(() => useAnalyze(0));
  await waitFor(() => expect(useProjectStore.getState().angles[0].analyzing).toBe(true));
  resolve({ preview_png: "data:x", result_token: "t" });
  await waitFor(() => expect(useProjectStore.getState().angles[0].analyzing).toBe(false));
});

it("invalid hex never sets analyzing", async () => {
  const spy = vi.spyOn(client, "analyze");
  useProjectStore.getState().initFromPhoto(photo as any);
  useProjectStore.getState().setPaletteAt(0, [{ name: "a", hex: "#zz" }]);
  renderHook(() => useAnalyze(0));
  await new Promise((r) => setTimeout(r, 20));
  expect(spy).not.toHaveBeenCalled();
  expect(useProjectStore.getState().angles[0].analyzing).toBeFalsy();
});

it("retryAnalyze re-runs analyze", async () => {
  const spy = vi.spyOn(client, "analyze").mockRejectedValueOnce(new Error("500"))
    .mockResolvedValue({ preview_png: "data:x", result_token: "t" } as any);
  useProjectStore.getState().initFromPhoto(photo as any);
  renderHook(() => useAnalyze(0));
  await waitFor(() => expect(useProjectStore.getState().angles[0].error).toBe("500"));
  useProjectStore.getState().retryAnalyze();
  await waitFor(() => expect(spy).toHaveBeenCalledTimes(2));
});
```

`web/src/components/PreviewImage.test.tsx`:

```tsx
import { it, expect, vi, beforeEach } from "vitest";
import { render, screen, fireEvent } from "@testing-library/react";
import { MantineProvider } from "@mantine/core";
import { PreviewImage } from "./PreviewImage";
import { useProjectStore } from "../store/projectStore";

vi.mock("react-i18next", () => ({ useTranslation: () => ({ t: (k: string) => k }) }));
const photo = { photo_id: "p1", width: 10, height: 10, quality_checks: [],
  default_whole: { palette: [{ name: "a", hex: "#000000" }], coverage: [1], material: "matte" } };
const wrap = () => render(<MantineProvider><PreviewImage /></MantineProvider>);
beforeEach(() => useProjectStore.setState(useProjectStore.getInitialState(), true));

it("no angle → placeholder", () => { wrap(); expect(screen.getByText("preview.placeholder")).toBeTruthy(); });

it("angle without preview yet → rendering loader, not the placeholder", () => {
  useProjectStore.getState().initFromPhoto(photo as any);
  wrap();
  expect(screen.getByText("preview.rendering")).toBeTruthy();
  expect(screen.queryByText("preview.placeholder")).toBeNull();
});

it("analyzing with a preview → updating badge", () => {
  const st = useProjectStore.getState();
  st.initFromPhoto(photo as any); st.setPreview("data:x", "t"); st.setAnalyzing(true);
  wrap();
  expect(screen.getByText("preview.updating")).toBeTruthy();
});

it("error → friendly notice whose Retry bumps the nonce", () => {
  const st = useProjectStore.getState();
  st.initFromPhoto(photo as any); st.setError("500 boom");
  wrap();
  expect(screen.getByText("errors.analyze")).toBeTruthy();
  fireEvent.click(screen.getByText("errors.retry"));
  expect(useProjectStore.getState().angles[0].analyzeNonce).toBe(1);
});
```

- [ ] **Step 2: Run** `cd web && npx vitest run src/store/projectStore.test.ts src/hooks/useAnalyze.test.tsx src/components/PreviewImage.test.tsx` — Expected: new tests FAIL.

- [ ] **Step 3: Implement**

Store — `Angle`: add `analyzing?: boolean; analyzeNonce?: number;`. State interface: `setAnalyzing(on: boolean): void; retryAnalyze(): void;`. Impl next to `setError`:

```ts
  setAnalyzing: (on) => set((s) => patchAngle(s, s.activeAngle, (a) => ({ ...a, analyzing: on }))),
  retryAnalyze: () => set((s) => patchAngle(s, s.activeAngle,
    (a) => ({ ...a, error: undefined, analyzeNonce: (a.analyzeNonce ?? 0) + 1 }))),
```

(Both keep `book`/`settings` references, so they do not re-trigger the `useAnalyze` effect. `toProjectAngleDto` maps fields explicitly, so neither leaks into saves.)

`useAnalyze.ts`:

```ts
  const setAnalyzing = useProjectStore((s) => s.setAnalyzing);
  const nonce = angle?.analyzeNonce ?? 0;
  // inside the timeout, AFTER the paletteHasValidHexes early-return:
        setAnalyzing(true);
        try {
          const res = await analyze({ photo_id: photoId, whole: book.whole, regions, settings });
          setPreview(res.preview_png, res.result_token);
        } finally { setAnalyzing(false); }
  // deps: [photoId, book, settings, nonce, delay, setPreview, setError, setAnalyzing]
```

(keep the outer `catch` that calls `setError`.)

`PreviewImage.tsx`:

```tsx
import { useTranslation } from "react-i18next";
import { Badge, Box, Center, Group, Loader, Text } from "@mantine/core";
import { useProjectStore, activeAngleOf } from "../store/projectStore";
import { ErrorNotice } from "./ErrorNotice";

export function PreviewImage() {
  const { t } = useTranslation();
  const angle = useProjectStore(activeAngleOf);
  const retry = useProjectStore((s) => s.retryAnalyze);
  if (!angle) return <Text c="dimmed">{t("preview.placeholder")}</Text>;
  const err = angle.error && <ErrorNotice message={t("errors.analyze")} detail={angle.error} onRetry={retry} />;
  if (!angle.preview) {
    return err || (
      <Center mih={200}><Group gap="xs"><Loader size="sm" /><Text size="sm" c="dimmed">{t("preview.rendering")}</Text></Group></Center>
    );
  }
  return (
    <>
      {err}
      <Box pos="relative">
        <img src={angle.preview} alt={t("preview.alt")} style={{ maxWidth: "100%", display: "block" }} />
        {angle.analyzing && (
          <Badge pos="absolute" top={8} left={8} variant="filled" color="dark"
            leftSection={<Loader size={10} color="white" />}>{t("preview.updating")}</Badge>
        )}
      </Box>
    </>
  );
}
```

Locales — en `"preview": { "placeholder": "Upload a photo or pick a sample to see the preview.", "rendering": "Rendering the preview…", "updating": "Updating preview…", "alt": "Painted preview" }`; es `"preview": { "placeholder": "Sube una foto o elige un ejemplo para ver la vista previa.", "rendering": "Generando la vista previa…", "updating": "Actualizando vista previa…", "alt": "Vista previa pintada" }`.

- [ ] **Step 4: Run** the three files — Expected: PASS.
- [ ] **Step 5: Commit** `git commit -am "feat(web): preview updating badge, first-render loader, error retry"`

---

### Task 9: Upload busy/error state; catalogue error state

**Files:**
- Modify: `web/src/components/PhotoUploader.tsx`
- Modify: `web/src/components/PaintInventory.tsx:14-20`
- Modify: locales (`upload` section)
- Test: `web/src/components/PhotoUploader.test.tsx`, `web/src/components/PaintInventory.test.tsx`

**Interfaces:**
- Consumes: `ErrorNotice`; `useCatalogStore(s => s.fetch)`, `s.error`.

- [ ] **Step 1: Write the failing tests**

`PhotoUploader.test.tsx`:

```tsx
it("shows a friendly error when the upload fails before any angle exists", async () => {
  vi.spyOn(client, "listSamplePhotos").mockResolvedValue([{ id: "necron", name: "Necron" }]);
  vi.spyOn(client, "samplePhotoBlob").mockResolvedValue(new Blob(["x"]));
  vi.spyOn(client, "uploadPhoto").mockRejectedValue(new Error("413 too big"));
  render(<MantineProvider><PhotoUploader /></MantineProvider>);
  (await screen.findByRole("button", { name: /Necron/ })).click();
  expect(await screen.findByText(/413 too big/)).toBeTruthy();
  expect(useProjectStore.getState().angles).toHaveLength(0);
});
```

(This file uses real i18n, so the message renders as English text; asserting on the detail avoids coupling to copy.)

`PaintInventory.test.tsx`:

```tsx
it("catalogue error shows a notice with retry instead of spinning", () => {
  const fetch = vi.fn();
  useCatalogStore.setState({ paints: [], status: "error", error: "500 x", fetch } as any);
  render(<MantineProvider><PaintInventory /></MantineProvider>);
  expect(screen.getByText("errors.catalog")).toBeTruthy();
  fireEvent.click(screen.getByText("errors.retry"));
  expect(fetch).toHaveBeenCalled();
});
```

- [ ] **Step 2: Run** `cd web && npx vitest run src/components/PhotoUploader.test.tsx src/components/PaintInventory.test.tsx` — Expected: new tests FAIL.

- [ ] **Step 3: Implement**

`PhotoUploader.tsx`:

```tsx
import { useTranslation } from "react-i18next";
import { ErrorNotice } from "./ErrorNotice";
// in component:
  const { t } = useTranslation();
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function handleBlob(blob: Blob, name: string) {
    setBusy(true); setError(null);
    try { initFromPhoto(await uploadPhoto(await downscaleImage(blob), name)); }
    catch (e) { setError(e instanceof Error ? e.message : String(e)); }
    finally { setBusy(false); }
  }
```

Remove the store `setError` selector. Button: `<Button variant="default" loading={busy} onClick=...>{t("upload.button")}</Button>`; sample label `{t("upload.or_sample")}`; sample buttons `disabled={busy}` and their own catch calls the local `setError`. After the samples block: `{error && <ErrorNotice message={t("errors.upload")} detail={error} />}`.

`PaintInventory.tsx` — before the `status !== "ready"` branch:

```tsx
  const fetchCatalog = useCatalogStore((s) => s.fetch);
  const catalogError = useCatalogStore((s) => s.error);
  if (status === "error") {
    return <ErrorNotice message={t("errors.catalog")} detail={catalogError ?? undefined} onRetry={fetchCatalog} />;
  }
```

(hooks must be declared above any early return — put the two selectors with the other selectors at the top.)

Locales — en `"upload": { "button": "Upload photo", "or_sample": "Or start from a sample:" }`; es `"upload": { "button": "Subir foto", "or_sample": "O empieza con un ejemplo:" }`.

- [ ] **Step 4: Run** both files — Expected: PASS.
- [ ] **Step 5: Commit** `git commit -am "feat(web): upload busy/error state; catalogue error with retry"`

---

### Task 10: Remaining i18n leftovers, angle labels, locale parity test

**Files:**
- Modify: `web/src/components/ManagePanel.tsx`, `web/src/components/AngleGallery.tsx:77,80`, `web/src/components/RegionHeader.tsx:27`, `web/src/components/colour/BandCard.tsx:16-21`, `web/src/components/ProjectLibrary.tsx` (5 fallbacks), `web/src/store/projectStore.ts:140,148`
- Modify: locales
- Create: `web/src/i18n/locales.test.ts`
- Modify: `web/src/components/AngleBar.test.tsx:18` ("angle 1" → "Angle 1"), any other test that asserts the old literals (`grep -rn "Draw region\|Add region\|angle 1\|stroke(s)" web/src --include=*.test.*`)

**Interfaces:**
- Consumes: locale keys `angles.default_label|rename|remove` (Task 6).

- [ ] **Step 1: Write the failing tests**

```ts
// web/src/i18n/locales.test.ts
import { it, expect } from "vitest";
import en from "./locales/en.json";
import es from "./locales/es.json";

function keys(o: any, p = ""): string[] {
  return Object.entries(o).flatMap(([k, v]) =>
    v && typeof v === "object" ? keys(v, `${p}${k}.`) : [`${p}${k}`]);
}

it("en and es have identical key sets", () => {
  expect(keys(es).sort()).toEqual(keys(en).sort());
});

it("no locale value contains markdown headings", () => {
  for (const v of [...keys(en).map((k) => k.split(".").reduce((o: any, s) => o[s], en)),
                   ...keys(es).map((k) => k.split(".").reduce((o: any, s) => o[s], es))]) {
    expect(String(v).startsWith("#")).toBe(false);
  }
});
```

Store label test in `projectStore.test.ts`:

```ts
  it("new angles get a translated, capitalised default label", () => {
    const st = useProjectStore.getState();
    st.initFromPhoto(photo("p1"));
    st.addAngle(photo("p2"));
    expect(useProjectStore.getState().angles.map((a) => a.label)).toEqual(["Angle 1", "Angle 2"]);
  });
```

`ManagePanel.test.tsx` mocks i18n (`t` returns the key), so its existing tests that click the literal `"Draw region"` / `"Add region"` must switch to `"region.draw"` / `"region.add"`. Add:

```tsx
  it("draw controls use translation keys", () => {
    useProjectStore.getState().initFromPhoto(photo());
    render(<MantineProvider><ManagePanel /></MantineProvider>);
    fireEvent.click(screen.getByText("region.draw"));
    expect(screen.getByText("region.add")).toBeTruthy();
    expect(screen.getByText("region.cancel")).toBeTruthy();
  });
```

- [ ] **Step 2: Run** `cd web && npx vitest run src/i18n src/store/projectStore.test.ts` — Expected: FAIL (markdown heading in `paints.heading`, label "angle 1").

- [ ] **Step 3: Implement**

Locales — en:
- `paints.heading`: `"Paints"`; es: `"Pinturas"`.
- `region` add: en `"draw": "Draw region", "add": "Add region", "cancel": "Cancel", "strokes_one": "{{count}} stroke", "strokes_other": "{{count}} strokes", "visible": "Visible", "delete": "Delete region", "select": "Region", "default_name": "region {{n}}"`; es `"draw": "Dibujar región", "add": "Añadir región", "cancel": "Cancelar", "strokes_one": "{{count}} trazo", "strokes_other": "{{count}} trazos", "visible": "Visible", "delete": "Eliminar región", "select": "Región", "default_name": "región {{n}}"`.
- `colour` add: en `"buy": "Buy: {{name}}"`; es `"buy": "Comprar: {{name}}"`.

`ManagePanel.tsx`: add `const { t } = useTranslation();`; `defaultName = t("region.default_name", { n: book.drawn.length + 1 })`; button texts `t("region.draw")`, `t("region.add")`, `t("region.cancel")`; strokes `t("region.strokes", { count: draftRings.length })`; checkbox `label={t("region.visible")} aria-label={t("region.visible")}`; delete `aria-label={t("region.delete")}`.

`AngleGallery.tsx:77,80`: `aria-label={t("angles.rename")}`, `aria-label={t("angles.remove")}`.

`RegionHeader.tsx:27`: `aria-label={t("region.select")}`.

`BandCard.tsx:16-21` `matchPhrase` — it is a module-level function; pass `t` in: `function matchPhrase(r: MatchResult, t: TFunction): string` returning `t("colour.buy", { name: r.name ?? "" })` for the buy case (import `type TFunction` from `i18next`), and call sites pass `t`.

`ProjectLibrary.tsx`: replace the fallbacks `"save failed"`, `"load failed"`, `"delete failed"`, `"download failed"`, `"upload failed"` with `t("errors.project_save")`, `t("errors.project_load")`, `t("errors.project_delete")`, `t("errors.project_download")`, `t("errors.project_upload")`.

`projectStore.ts`: `import i18n from "../i18n";` then line 140 `makeAngle(res, i18n.t("angles.default_label", { n: 1 }), DEFAULT_SETTINGS)` and line 148 `` makeAngle(res, i18n.t("angles.default_label", { n: s.angles.length + 1 }), settings) ``.

Update `AngleBar.test.tsx:18` to `"Angle 1"` and any test found by the grep in **Files**.

- [ ] **Step 4: Run the full frontend suite + typecheck** `cd web && npx vitest run && npx tsc -b` — Expected: all PASS, no type errors. Then `.venv/Scripts/python -m pytest backend/tests -q` — Expected: PASS.
- [ ] **Step 5: Commit** `git commit -am "feat(web): finish i18n coverage; translated angle labels; locale parity test"`

---

### Task 11: Branch wrap-up

- [ ] **Step 1:** `cd web && npm run build` — Expected: clean build.
- [ ] **Step 2:** Manual smoke (user): `uvicorn backend.main:app --reload` + `cd web && npm run dev`; upload a sample → preview badge appears while editing; Painting Steps shows paint names + hint; delete a middle band; toggle Spanish and scan for English leftovers.
- [ ] **Step 3:** `git push` and open the PR (user merges).
