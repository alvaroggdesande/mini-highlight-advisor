# Paint Steps Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a Paint tab to the React app that lazily fetches and renders per-band step images (zone / cumulative / exact) for each region, mirroring the Streamlit `ui/results.render_steps` layout.

**Architecture:** A new `GET /api/steps?token=` endpoint serializes the already-cached `MultiRegionResult` step images as base64 PNGs — no re-render. The React client fetches these lazily only when the Paint tab is opened; on a 409 (token expired/evicted from LRU) it transparently re-POSTs `/analyze` to refresh the cache and retries. The UI mirrors the Streamlit 3-column (non-last step) / 2-column (last step) layout.

**Tech Stack:** FastAPI + Pydantic v2 (backend), React 19 + TypeScript + Zustand 5, Vitest + React Testing Library, react-i18next.

**Spec:** `docs/superpowers/specs/2026-09-22-react-fastapi-migration-design.md` (§5 API contract and §7 component map)

## Global Constraints

- Python tests: `.venv/Scripts/python -m pytest backend/tests/ -v`
- Frontend tests: `cd web && npm test -- --run`
- All images returned as base64 `data:image/png;base64,...` strings — no binary endpoints
- `BandStep.label` is `None` for band steps; derive from `plan.roles[step.index]`. Edge/shade steps have `label` set.
- OSL steps (`kind == "osl"`) are excluded from the web app — skip them in the endpoint
- Never push to `main`; always feature branch + PR
- All user-visible strings go through `useTranslation`

---

### Task 1: Backend — schemas + `/api/steps` endpoint + tests

**Files:**
- Modify: `backend/schemas.py` (append 3 new models)
- Modify: `backend/main.py` (add endpoint + update imports)
- Create: `backend/tests/test_steps.py`

**Interfaces:**
- Produces: `GET /api/steps?token=<str>` → `StepsResponse` JSON, or HTTP 409 on cache miss
- Consumed by: Task 2 (TypeScript client)

- [ ] **Step 1: Create feature branch**

```bash
git -C C:\Users\ag\alvaro\git\mini-highlight-advisor checkout -b feat/paint-steps
```

- [ ] **Step 2: Write failing tests**

Create `backend/tests/test_steps.py`:

```python
import io
import numpy as np
from PIL import Image
from fastapi.testclient import TestClient
from backend.main import app

client = TestClient(app)


def _png_bytes(w: int = 30, h: int = 40) -> bytes:
    arr = np.random.default_rng(2).integers(0, 255, (h, w, 3), dtype=np.uint8)
    buf = io.BytesIO()
    Image.fromarray(arr).save(buf, format="PNG")
    return buf.getvalue()


def _upload_and_analyze(n_bands: int = 2) -> str:
    """Upload a synthetic photo, run analyze (edge_hl=False), return result_token."""
    data = _png_bytes()
    r = client.post("/api/photo", files={"file": ("m.png", data, "image/png")})
    assert r.status_code == 200
    photo_id = r.json()["photo_id"]

    palette = [{"name": f"p{i}", "hex": "#202020" if i == 0 else "#e0e0e0"}
               for i in range(n_bands)]
    coverage = [1.0 / n_bands] * n_bands
    req = {
        "photo_id": photo_id,
        "whole": {"palette": palette, "coverage": coverage, "material": "matte"},
        "settings": {"edge_hl": False},
    }
    r = client.post("/api/analyze", json=req)
    assert r.status_code == 200
    return r.json()["result_token"]


def test_steps_unknown_token_returns_409():
    r = client.get("/api/steps", params={"token": "deadbeef"})
    assert r.status_code == 409


def test_steps_returns_plans_with_steps():
    token = _upload_and_analyze(n_bands=2)
    r = client.get("/api/steps", params={"token": token})
    assert r.status_code == 200
    body = r.json()
    assert "plans" in body
    assert len(body["plans"]) >= 1  # at least the WHOLE_MINI plan
    plan = body["plans"][0]
    assert "name" in plan
    assert "roles" in plan
    assert "coverage" in plan
    assert "steps" in plan
    assert len(plan["steps"]) >= 1


def test_steps_images_are_base64_png():
    token = _upload_and_analyze(n_bands=2)
    body = client.get("/api/steps", params={"token": token}).json()
    step = body["plans"][0]["steps"][0]
    assert step["zone_png"].startswith("data:image/png;base64,")
    assert step["cumulative_png"].startswith("data:image/png;base64,")


def test_steps_last_step_has_no_exact_png():
    token = _upload_and_analyze(n_bands=2)
    body = client.get("/api/steps", params={"token": token}).json()
    # edge_hl=False: only 2 band steps. Step index 1 is last.
    band_steps = [s for s in body["plans"][0]["steps"] if s["kind"] == "band"]
    last = band_steps[-1]
    assert last["is_last"] is True
    assert last["exact_png"] is None


def test_steps_non_last_step_has_exact_png():
    token = _upload_and_analyze(n_bands=2)
    body = client.get("/api/steps", params={"token": token}).json()
    band_steps = [s for s in body["plans"][0]["steps"] if s["kind"] == "band"]
    first = band_steps[0]
    assert first["is_last"] is False
    assert first["exact_png"] is not None
    assert first["exact_png"].startswith("data:image/png;base64,")


def test_steps_band_step_label_matches_role():
    token = _upload_and_analyze(n_bands=2)
    body = client.get("/api/steps", params={"token": token}).json()
    plan = body["plans"][0]
    band_steps = [s for s in plan["steps"] if s["kind"] == "band"]
    for step in band_steps:
        assert step["label"] == plan["roles"][step["index"]]


def test_steps_edge_hl_adds_edge_step():
    data = _png_bytes()
    r = client.post("/api/photo", files={"file": ("m.png", data, "image/png")})
    photo_id = r.json()["photo_id"]
    req = {
        "photo_id": photo_id,
        "whole": {"palette": [{"name": "a", "hex": "#202020"}, {"name": "b", "hex": "#e0e0e0"}],
                  "coverage": [0.5, 0.5], "material": "matte"},
        "settings": {"edge_hl": True},
    }
    token = client.post("/api/analyze", json=req).json()["result_token"]
    body = client.get("/api/steps", params={"token": token}).json()
    kinds = [s["kind"] for s in body["plans"][0]["steps"]]
    assert "edge" in kinds
```

- [ ] **Step 3: Run to confirm they fail**

```
.venv\Scripts\python -m pytest backend/tests/test_steps.py -v
```

Expected: all tests fail (404 or similar — `/api/steps` not defined yet).

- [ ] **Step 4: Add Pydantic schemas to `backend/schemas.py`**

Append to the end of `backend/schemas.py`:

```python
class StepImageDto(BaseModel):
    index: int
    label: str
    kind: str  # "band" | "edge" | "shade"
    zone_png: str
    cumulative_png: str
    exact_png: str | None
    is_last: bool


class RegionPlanDto(BaseModel):
    name: str
    roles: list[str]
    coverage: list[float]
    steps: list[StepImageDto]


class StepsResponse(BaseModel):
    plans: list[RegionPlanDto]
```

- [ ] **Step 5: Add the `GET /api/steps` endpoint to `backend/main.py`**

Update the schemas import line near the top of `backend/main.py` to include the new models:

```python
from backend.schemas import (
    AnalyzeRequest, RegionColorSpec as RegionColorSpecModel,
    SchemeGenerateRequest, RampGenerateRequest, MatchRequest, RecipeModel,
    StepsResponse, RegionPlanDto, StepImageDto,
)
```

Then add this endpoint after the `/api/analyze` route (after the `result_cache.set` + return line):

```python
@app.get("/api/steps")
def get_steps(token: str) -> StepsResponse:
    result = result_cache.get(token)
    if result is None:
        raise HTTPException(status_code=409, detail="token expired; re-analyze to refresh")
    plans_out: list[RegionPlanDto] = []
    for plan in result.plans:
        steps_out: list[StepImageDto] = []
        for step in plan.steps:
            if step.kind == "osl":
                continue  # OSL excluded from the web app
            label = step.label
            if label is None:
                # Band steps don't set label; derive from the plan's role names
                label = (plan.roles[step.index]
                         if step.index < len(plan.roles)
                         else f"Band {step.index + 1}")
            steps_out.append(StepImageDto(
                index=step.index,
                label=label,
                kind=step.kind,
                zone_png=png_data_uri(step.zone_rgb),
                cumulative_png=png_data_uri(step.cumulative_rgb),
                exact_png=png_data_uri(step.exact_rgb) if step.exact_rgb is not None else None,
                is_last=step.is_last,
            ))
        plans_out.append(RegionPlanDto(
            name=plan.name,
            roles=plan.roles,
            coverage=plan.coverage,
            steps=steps_out,
        ))
    return StepsResponse(plans=plans_out)
```

- [ ] **Step 6: Run tests to confirm they pass**

```
.venv\Scripts\python -m pytest backend/tests/test_steps.py -v
```

Expected: all 7 tests pass.

- [ ] **Step 7: Run full backend suite to check no regressions**

```
.venv\Scripts\python -m pytest backend/tests/ -v
```

Expected: all tests pass.

- [ ] **Step 8: Commit**

```bash
git -C C:\Users\ag\alvaro\git\mini-highlight-advisor add backend/schemas.py backend/main.py backend/tests/test_steps.py
git -C C:\Users\ag\alvaro\git\mini-highlight-advisor commit -m "feat: add GET /api/steps endpoint with per-band step image serialization"
```

---

### Task 2: TypeScript types + API client

**Files:**
- Modify: `web/src/api/types.ts` (append 3 new interfaces)
- Modify: `web/src/api/client.ts` (append `TokenExpiredError` + `fetchSteps`)

**Interfaces:**
- Produces: `StepImageDto`, `RegionPlanDto`, `StepsResponse` interfaces; `TokenExpiredError` class; `fetchSteps(token: string): Promise<StepsResponse>`
- Consumed by: Task 4 (`StepList`), Task 5 (`PaintTab`)

- [ ] **Step 1: Write failing tests**

Check if `web/src/api/client.test.ts` already exists. It does — append to it. Add at the end:

```ts
import { fetchSteps, TokenExpiredError } from "./client";

describe("fetchSteps", () => {
  afterEach(() => vi.restoreAllMocks());

  it("throws TokenExpiredError on 409", async () => {
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue({ status: 409, ok: false }));
    await expect(fetchSteps("bad-token")).rejects.toBeInstanceOf(TokenExpiredError);
  });

  it("returns parsed JSON on 200", async () => {
    const body = { plans: [] };
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue({
      status: 200, ok: true, json: () => Promise.resolve(body),
    }));
    const result = await fetchSteps("good-token");
    expect(result).toEqual(body);
  });
});
```

- [ ] **Step 2: Run to confirm they fail**

```
cd web && npm test -- --run src/api/client.test.ts
```

Expected: the two new fetchSteps tests fail (`fetchSteps` not defined).

- [ ] **Step 3: Add TypeScript types to `web/src/api/types.ts`**

Append to the end of `web/src/api/types.ts`:

```ts
export interface StepImageDto {
  index: number;
  label: string;
  kind: string;  // "band" | "edge" | "shade"
  zone_png: string;
  cumulative_png: string;
  exact_png: string | null;
  is_last: boolean;
}

export interface RegionPlanDto {
  name: string;
  roles: string[];
  coverage: number[];
  steps: StepImageDto[];
}

export interface StepsResponse {
  plans: RegionPlanDto[];
}
```

- [ ] **Step 4: Add `TokenExpiredError` and `fetchSteps` to `web/src/api/client.ts`**

At the top of `web/src/api/client.ts`, add to the existing imports block:

```ts
import type { StepsResponse } from "./types";
```

After the existing `json<T>()` helper (before `uploadPhoto`), add:

```ts
export class TokenExpiredError extends Error {
  constructor() { super("token expired"); }
}
```

At the end of `web/src/api/client.ts`, append:

```ts
export async function fetchSteps(token: string): Promise<StepsResponse> {
  const res = await fetch(`/api/steps?token=${encodeURIComponent(token)}`);
  if (res.status === 409) throw new TokenExpiredError();
  if (!res.ok) throw new Error(`${res.status} ${await res.text()}`);
  return res.json() as Promise<StepsResponse>;
}
```

- [ ] **Step 5: Run tests to confirm they pass**

```
cd web && npm test -- --run src/api/client.test.ts
```

Expected: all tests in that file pass (existing + 2 new).

- [ ] **Step 6: Commit**

```bash
git -C C:\Users\ag\alvaro\git\mini-highlight-advisor add web/src/api/types.ts web/src/api/client.ts
git -C C:\Users\ag\alvaro\git\mini-highlight-advisor commit -m "feat: add StepsResponse types and fetchSteps client with TokenExpiredError"
```

---

### Task 3: i18n keys

**Files:**
- Modify: `web/src/i18n/locales/en.json`
- Modify: `web/src/i18n/locales/es.json`

**Interfaces:**
- Produces: `t("tabs.studio")`, `t("tabs.paint")`, `t("paint.loading")`, `t("paint.no_preview")`, `t("paint.step_zone")`, `t("paint.step_cumulative")`, `t("paint.step_exact")`
- Consumed by: `App.tsx` (Task 5), `PaintTab` (Task 5), `StepList` (Task 4)

- [ ] **Step 1: Add keys to `en.json`**

In `web/src/i18n/locales/en.json`, add `"studio"` and `"paint"` to the existing `"tabs"` object so it reads:

```json
"tabs": {
  "manage": "Manage",
  "colour": "Colour",
  "technique": "Technique",
  "studio": "Studio",
  "paint": "Paint"
}
```

Add a new top-level `"paint"` object (alongside `"tabs"`, `"colour"`, etc.):

```json
"paint": {
  "loading": "Loading steps…",
  "no_preview": "Analyze the photo first to see painting steps.",
  "step_zone": "Where to paint",
  "step_cumulative": "Result so far",
  "step_exact": "This layer"
}
```

- [ ] **Step 2: Add keys to `es.json`**

Apply the same structure to `web/src/i18n/locales/es.json`. Add to `"tabs"`:

```json
"studio": "Estudio",
"paint": "Pintura"
```

Add a new top-level `"paint"` object:

```json
"paint": {
  "loading": "Cargando pasos…",
  "no_preview": "Analiza la foto primero para ver los pasos de pintura.",
  "step_zone": "Dónde pintar",
  "step_cumulative": "Resultado hasta aquí",
  "step_exact": "Esta capa"
}
```

- [ ] **Step 3: Verify TypeScript compiles**

```
cd web && npx tsc --noEmit
```

Expected: no errors.

- [ ] **Step 4: Commit**

```bash
git -C C:\Users\ag\alvaro\git\mini-highlight-advisor add web/src/i18n/locales/en.json web/src/i18n/locales/es.json
git -C C:\Users\ag\alvaro\git\mini-highlight-advisor commit -m "feat: add i18n keys for Studio/Paint tabs and step image captions"
```

---

### Task 4: `StepList` component

**Files:**
- Create: `web/src/components/StepList.tsx`
- Create: `web/src/components/StepList.test.tsx`

**Interfaces:**
- Consumes: `RegionPlanDto`, `StepImageDto` from Task 2; `t("paint.step_zone")` etc. from Task 3
- Produces: `export function StepList({ plans }: { plans: RegionPlanDto[] })` — consumed by `PaintTab` (Task 5)

- [ ] **Step 1: Write failing tests**

Create `web/src/components/StepList.test.tsx`:

```tsx
import { describe, it, expect, vi } from "vitest";
import { render, screen } from "@testing-library/react";
import { StepList } from "./StepList";
import type { RegionPlanDto } from "../api/types";

vi.mock("react-i18next", () => ({ useTranslation: () => ({ t: (k: string) => k }) }));

const makeStep = (index: number, isLast: boolean) => ({
  index,
  label: index === 0 ? "Shadow" : "Highlight",
  kind: "band",
  zone_png: "data:image/png;base64,abc",
  cumulative_png: "data:image/png;base64,def",
  exact_png: isLast ? null : "data:image/png;base64,ghi",
  is_last: isLast,
});

const plan: RegionPlanDto = {
  name: "Helmet",
  roles: ["Shadow", "Highlight"],
  coverage: [60, 40],
  steps: [makeStep(0, false), makeStep(1, true)],
};

describe("StepList", () => {
  it("renders a heading for each region", () => {
    render(<StepList plans={[plan]} />);
    expect(screen.getByText("Helmet")).toBeTruthy();
  });

  it("renders the step label for each step", () => {
    render(<StepList plans={[plan]} />);
    expect(screen.getByText("Shadow")).toBeTruthy();
    expect(screen.getByText("Highlight")).toBeTruthy();
  });

  it("non-last step renders zone, cumulative, and exact captions", () => {
    render(<StepList plans={[plan]} />);
    // t() returns the key itself (mocked); non-last step (index 0) has all three
    expect(screen.getAllByText("paint.step_zone").length).toBeGreaterThanOrEqual(1);
    expect(screen.getAllByText("paint.step_cumulative").length).toBeGreaterThanOrEqual(1);
    expect(screen.getAllByText("paint.step_exact").length).toBeGreaterThanOrEqual(1);
  });

  it("last-only plan renders zone and cumulative but not exact caption", () => {
    const lastOnlyPlan: RegionPlanDto = { ...plan, steps: [makeStep(0, true)] };
    render(<StepList plans={[lastOnlyPlan]} />);
    expect(screen.queryByText("paint.step_exact")).toBeNull();
  });

  it("renders multiple regions", () => {
    const plan2: RegionPlanDto = { ...plan, name: "Cloak" };
    render(<StepList plans={[plan, plan2]} />);
    expect(screen.getByText("Helmet")).toBeTruthy();
    expect(screen.getByText("Cloak")).toBeTruthy();
  });
});
```

- [ ] **Step 2: Run to confirm they fail**

```
cd web && npm test -- --run src/components/StepList.test.tsx
```

Expected: all 5 tests fail (`StepList` not defined).

- [ ] **Step 3: Implement `StepList.tsx`**

Create `web/src/components/StepList.tsx`:

```tsx
import { useTranslation } from "react-i18next";
import type { RegionPlanDto, StepImageDto } from "../api/types";

function StepCard({ step }: { step: StepImageDto }) {
  const { t } = useTranslation();
  const imgStyle: React.CSSProperties = { width: "100%", display: "block" };
  const captionStyle: React.CSSProperties = {
    fontSize: 12, color: "#aaa", textAlign: "center", marginTop: 4,
  };
  const colStyle: React.CSSProperties = { display: "flex", flexDirection: "column" };

  return (
    <div style={{ marginBottom: 16 }}>
      <div style={{ fontWeight: 600, marginBottom: 8 }}>{step.label}</div>
      {step.is_last ? (
        <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 8 }}>
          <div style={colStyle}>
            <img src={step.zone_png} alt={t("paint.step_zone")} style={imgStyle} />
            <span style={captionStyle}>{t("paint.step_zone")}</span>
          </div>
          <div style={colStyle}>
            <img src={step.cumulative_png} alt={t("paint.step_cumulative")} style={imgStyle} />
            <span style={captionStyle}>{t("paint.step_cumulative")}</span>
          </div>
        </div>
      ) : (
        <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr 1fr", gap: 8 }}>
          <div style={colStyle}>
            <img src={step.zone_png} alt={t("paint.step_zone")} style={imgStyle} />
            <span style={captionStyle}>{t("paint.step_zone")}</span>
          </div>
          <div style={colStyle}>
            <img src={step.cumulative_png} alt={t("paint.step_cumulative")} style={imgStyle} />
            <span style={captionStyle}>{t("paint.step_cumulative")}</span>
          </div>
          <div style={colStyle}>
            <img src={step.exact_png!} alt={t("paint.step_exact")} style={imgStyle} />
            <span style={captionStyle}>{t("paint.step_exact")}</span>
          </div>
        </div>
      )}
    </div>
  );
}

export interface StepListProps { plans: RegionPlanDto[]; }

export function StepList({ plans }: StepListProps) {
  return (
    <div>
      {plans.map((plan) => (
        <section key={plan.name} style={{ marginBottom: 32 }}>
          <h3 style={{ borderBottom: "1px solid #333", paddingBottom: 8, marginBottom: 16 }}>
            {plan.name}
          </h3>
          {plan.steps.map((step) => (
            <StepCard key={`${step.kind}-${step.index}`} step={step} />
          ))}
        </section>
      ))}
    </div>
  );
}
```

- [ ] **Step 4: Run tests to confirm they pass**

```
cd web && npm test -- --run src/components/StepList.test.tsx
```

Expected: all 5 tests pass.

- [ ] **Step 5: Commit**

```bash
git -C C:\Users\ag\alvaro\git\mini-highlight-advisor add web/src/components/StepList.tsx web/src/components/StepList.test.tsx
git -C C:\Users\ag\alvaro\git\mini-highlight-advisor commit -m "feat: add StepList component with 2/3-column step image grid"
```

---

### Task 5: `PaintTab` component + `App.tsx` wiring

**Files:**
- Create: `web/src/components/PaintTab.tsx`
- Create: `web/src/components/PaintTab.test.tsx`
- Modify: `web/src/App.tsx`

**Interfaces:**
- Consumes: `fetchSteps`, `TokenExpiredError`, `analyze` from `../api/client`; `StepList` from Task 4; `useProjectStore`, `activeAngleOf` from store; `t("tabs.studio")`, `t("tabs.paint")`, `t("paint.loading")`, `t("paint.no_preview")` from Task 3
- Produces: `<PaintTab />` + Studio/Paint top-level tab bar wired into `App.tsx`

- [ ] **Step 1: Write failing PaintTab tests**

Create `web/src/components/PaintTab.test.tsx`:

```tsx
import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, waitFor } from "@testing-library/react";
import { PaintTab } from "./PaintTab";
import { useProjectStore } from "../store/projectStore";
import * as client from "../api/client";
import type { StepsResponse, Settings } from "../api/types";

vi.mock("react-i18next", () => ({ useTranslation: () => ({ t: (k: string) => k }) }));
vi.mock("./StepList", () => ({
  StepList: ({ plans }: { plans: unknown[] }) => (
    <div data-testid="step-list">{plans.length} plans</div>
  ),
}));

const SETTINGS: Settings = {
  edge_hl: true, edge_extreme: false, edge_sens: 0.5, relief_cap: true, per_region_norm: false,
};
const EMPTY_RESPONSE: StepsResponse = { plans: [] };

beforeEach(() => {
  vi.restoreAllMocks();
  useProjectStore.setState({
    activeAngle: 0,
    angles: [{
      id: "a1", label: "Front", photoId: "abc123", width: 30, height: 40,
      qualityChecks: [], settings: SETTINGS,
      book: {
        whole: { palette: [], coverage: [], material: "matte" },
        drawn: [], selected: 0, schemes: [],
      },
      preview: "data:image/png;base64,xxx",
      resultToken: "tok123",
    }],
  });
});

describe("PaintTab", () => {
  it("shows no_preview when result token is absent", () => {
    useProjectStore.setState((s) => ({
      ...s,
      angles: [{ ...s.angles[0], resultToken: undefined }],
    }));
    render(<PaintTab />);
    expect(screen.getByText("paint.no_preview")).toBeTruthy();
  });

  it("shows loading while fetching", () => {
    vi.spyOn(client, "fetchSteps").mockReturnValue(new Promise(() => {}));
    render(<PaintTab />);
    expect(screen.getByText("paint.loading")).toBeTruthy();
  });

  it("fetches steps with the current token on mount and renders StepList", async () => {
    vi.spyOn(client, "fetchSteps").mockResolvedValue(EMPTY_RESPONSE);
    render(<PaintTab />);
    await waitFor(() => expect(screen.getByTestId("step-list")).toBeTruthy());
    expect(client.fetchSteps).toHaveBeenCalledWith("tok123");
  });

  it("re-analyzes and retries on TokenExpiredError", async () => {
    vi.spyOn(client, "fetchSteps")
      .mockRejectedValueOnce(new client.TokenExpiredError())
      .mockResolvedValueOnce(EMPTY_RESPONSE);
    vi.spyOn(client, "analyze").mockResolvedValue({
      preview_png: "data:image/png;base64,y",
      result_token: "newTok",
    });
    render(<PaintTab />);
    await waitFor(() => expect(screen.getByTestId("step-list")).toBeTruthy());
    expect(client.analyze).toHaveBeenCalledOnce();
    expect(client.fetchSteps).toHaveBeenCalledTimes(2);
    expect(client.fetchSteps).toHaveBeenLastCalledWith("newTok");
  });
});
```

- [ ] **Step 2: Run to confirm they fail**

```
cd web && npm test -- --run src/components/PaintTab.test.tsx
```

Expected: all 4 tests fail (`PaintTab` not defined).

- [ ] **Step 3: Implement `PaintTab.tsx`**

Create `web/src/components/PaintTab.tsx`:

```tsx
import { useState, useEffect } from "react";
import { useTranslation } from "react-i18next";
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

  useEffect(() => {
    if (!token) return;
    let cancelled = false;

    async function load() {
      setLoading(true);
      setError(null);
      try {
        const data = await fetchSteps(token!);
        if (!cancelled) setPlans(data.plans);
      } catch (e) {
        if (cancelled) return;
        if (e instanceof TokenExpiredError) {
          // Cache evicted: re-analyze with current store state, then retry
          try {
            const { angles, activeAngle } = useProjectStore.getState();
            const a = angles[activeAngle];
            if (!a?.photoId) throw new Error("no photo");
            const regions: RegionPayload[] = a.book.drawn
              .filter((r) => !r.blank && r.rings.length > 0)
              .map((r) => ({
                name: r.name, rings: r.rings, palette: r.palette,
                coverage: r.coverage, material: r.material,
              }));
            const res = await analyze({
              photo_id: a.photoId,
              whole: a.book.whole,
              regions,
              settings: a.settings,
            });
            if (!cancelled) {
              setPreview(res.preview_png, res.result_token);
              const retry = await fetchSteps(res.result_token);
              if (!cancelled) setPlans(retry.plans);
            }
          } catch (retryErr) {
            if (!cancelled) setError(String(retryErr));
          }
        } else {
          setError(String(e));
        }
      } finally {
        if (!cancelled) setLoading(false);
      }
    }

    load();
    return () => { cancelled = true; };
  }, [token]); // eslint-disable-line react-hooks/exhaustive-deps

  if (!token) {
    return <p style={{ color: "#aaa" }}>{t("paint.no_preview")}</p>;
  }
  if (loading) {
    return <p style={{ color: "#aaa" }}>{t("paint.loading")}</p>;
  }
  if (error) {
    return <p style={{ color: "#e55" }}>{error}</p>;
  }
  if (!plans) return null;

  return <StepList plans={plans} />;
}
```

- [ ] **Step 4: Run PaintTab tests to confirm they pass**

```
cd web && npm test -- --run src/components/PaintTab.test.tsx
```

Expected: all 4 tests pass.

- [ ] **Step 5: Update `App.tsx` to add Studio/Paint top-level tabs**

Replace the entire content of `web/src/App.tsx` with:

```tsx
import { useState, useEffect } from "react";
import { useTranslation } from "react-i18next";
import { PhotoUploader } from "./components/PhotoUploader";
import { PreviewImage } from "./components/PreviewImage";
import { RegionSelector } from "./components/RegionSelector";
import { AngleBar } from "./components/AngleBar";
import { RightPanel } from "./components/RightPanel";
import { PaintTab } from "./components/PaintTab";
import { useAnalyze } from "./hooks/useAnalyze";
import { useProjectStore, activeAngleOf } from "./store/projectStore";
import { useCatalogStore } from "./store/catalogStore";

type MainTab = "studio" | "paint";

export default function App() {
  const { t } = useTranslation();
  useAnalyze();
  const hasAngle = useProjectStore((s) => s.angles.length > 0);
  const resultToken = useProjectStore((s) => activeAngleOf(s)?.resultToken);
  const fetchCatalog = useCatalogStore((s) => s.fetch);
  const [tab, setTab] = useState<MainTab>("studio");

  useEffect(() => {
    if (hasAngle) fetchCatalog();
  }, [hasAngle, fetchCatalog]);

  const tabBtn = (id: MainTab, disabled = false): React.CSSProperties => ({
    padding: "6px 18px", marginRight: 4,
    background: "none", border: "none",
    borderBottom: tab === id ? "2px solid #eee" : "2px solid transparent",
    color: disabled ? "#555" : tab === id ? "#eee" : "#888",
    fontSize: 14, fontWeight: tab === id ? 600 : 400,
    cursor: disabled ? "default" : "pointer",
  });

  return (
    <main style={{ maxWidth: 1100, margin: "0 auto", padding: 16 }}>
      <h1>Mini Highlight Advisor</h1>
      {!hasAngle ? (
        <PhotoUploader />
      ) : (
        <>
          <AngleBar />
          <nav style={{ borderBottom: "1px solid #333", marginBottom: 16 }}>
            <button style={tabBtn("studio")} onClick={() => setTab("studio")}>
              {t("tabs.studio")}
            </button>
            <button
              style={tabBtn("paint", !resultToken)}
              onClick={() => { if (resultToken) setTab("paint"); }}
              disabled={!resultToken}
            >
              {t("tabs.paint")}
            </button>
          </nav>
          {tab === "studio" && (
            <div style={{ display: "flex", gap: 24, alignItems: "flex-start" }}>
              <div style={{ flex: "0 0 auto" }}>
                <PreviewImage />
              </div>
              <div style={{ flex: 1 }}>
                <RegionSelector />
                <RightPanel />
              </div>
            </div>
          )}
          {tab === "paint" && <PaintTab />}
        </>
      )}
    </main>
  );
}
```

- [ ] **Step 6: Run the full frontend test suite**

```
cd web && npm test -- --run
```

Expected: all tests pass (no regressions from App.tsx change).

- [ ] **Step 7: Run the full backend test suite**

```
.venv\Scripts\python -m pytest backend/tests/ -v
```

Expected: all tests pass.

- [ ] **Step 8: Commit**

```bash
git -C C:\Users\ag\alvaro\git\mini-highlight-advisor add web/src/components/PaintTab.tsx web/src/components/PaintTab.test.tsx web/src/App.tsx
git -C C:\Users\ag\alvaro\git\mini-highlight-advisor commit -m "feat: add PaintTab with lazy steps fetch and Studio/Paint top-level tabs in App"
```
