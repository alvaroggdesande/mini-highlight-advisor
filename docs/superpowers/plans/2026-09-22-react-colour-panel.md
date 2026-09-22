# React ColourPanel Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Port the Streamlit ColourPanel to a React slice, delivering L1 scheme generation, L2 ramp editing, L3 slot editing, recipe CRUD, and session-only scheme snapshots on top of the existing React+FastAPI scaffold.

**Architecture:** Three layers — FastAPI endpoints calling existing Python colour-engine modules (`catalog`, `matching`, `scheme_build`, `recipes`, `collection`, `color`); a Zustand `projectStore` extension plus a new `catalogStore`; and a `ColourPanel` component tree replacing the flat `BandControl`.

**Tech Stack:** React 19 + TypeScript + Zustand 5 + Vitest + react-i18next + FastAPI + Pydantic + existing Python colour-engine

**Spec:** `docs/superpowers/specs/2026-09-22-react-colour-panel-design.md`

## Global Constraints

- Branch: `feat/react-colour-panel` — create from `main` before starting
- Never commit directly to `main`; feature branch + PR
- Wire types in `api/types.ts` are unchanged: `Whole` stays `{ palette, coverage, material }`
- `useAnalyze` hook is unchanged — it already watches `book.whole` and `book.drawn`
- NMM / Glow / OSL / PS modes are excluded from the React app entirely
- The existing Streamlit app (`app.py`) is not modified
- Python tests: run with `.venv/Scripts/python -m pytest backend/tests/` from repo root
- Frontend tests: run with `cd web && npm test`
- No `react-i18next` installed yet — Task 7 installs it via `cd web && npm install react-i18next i18next`

---

### Task 1: Backend schemas

**Files:**
- Modify: `backend/schemas.py` — add 6 new Pydantic models

**Interfaces:**
- Produces: `RegionColorSpec`, `SchemeGenerateRequest`, `RampGenerateRequest`, `MatchRequest`, `RecipeStepModel`, `RecipeModel` — imported by `backend/main.py` in Tasks 2 and 3

- [ ] **Step 1: Add 6 Pydantic models to `backend/schemas.py`**

Append to the end of `backend/schemas.py`:

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
    variant: str = "ramp"
    blend_hexes: list[str] | None = None


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

- [ ] **Step 2: Verify import doesn't break existing app**

Run: `.venv/Scripts/python -c "from backend.schemas import RegionColorSpec, SchemeGenerateRequest, RampGenerateRequest, MatchRequest, RecipeStepModel, RecipeModel; print('ok')"`
Expected: `ok`

- [ ] **Step 3: Commit**

```bash
git add backend/schemas.py
git commit -m "feat: add colour-panel Pydantic schemas"
```

---

### Task 2: Backend — 7 implemented endpoints

**Files:**
- Modify: `backend/main.py` — add `GET /api/catalog`, `POST /api/match`, `POST /api/scheme/generate`, `GET /api/recipes`, `POST /api/recipes`, `GET /api/collection`, `PUT /api/collection`

**Interfaces:**
- Consumes: `RegionColorSpec`, `SchemeGenerateRequest`, `MatchRequest`, `RecipeStepModel`, `RecipeModel` from Task 1; Python modules `mini_highlight_advisor.{catalog,matching,scheme_build,scheme_gen,recipes,collection}`
- Produces: The 7 endpoints consumed by the frontend API client (Task 6)

- [ ] **Step 1: Add module-level catalog cache and imports to `backend/main.py`**

After the existing imports block (after `from backend.serialize import ...`), add:

```python
from mini_highlight_advisor.catalog import load_catalog as _load_catalog_raw
from backend.schemas import (
    RegionColorSpec as RegionColorSpecModel,
    SchemeGenerateRequest, MatchRequest, RecipeModel,
)

_catalog_cache: list | None = None

def _catalog():
    global _catalog_cache
    if _catalog_cache is None:
        _catalog_cache = _load_catalog_raw()
    return _catalog_cache
```

- [ ] **Step 2: Add `GET /api/catalog`**

```python
@app.get("/api/catalog")
def get_catalog():
    return {"paints": [paint_to_dict(p) for p in _catalog()]}
```

- [ ] **Step 3: Add `POST /api/match`**

```python
@app.post("/api/match")
def match_paint(req: MatchRequest):
    from mini_highlight_advisor.matching import Target, match
    catalog = _catalog()
    owned = [p for p in catalog if p.code in set(req.owned_codes)]
    target = Target(hex=req.hex, finish=req.finish)
    result = match(target, owned, catalog)
    return {
        "tier": result.tier,
        "phrase": result.phrase,
        "name": result.paints[0].name if result.paints else None,
        "hex": result.paints[0].hex if result.paints else None,
        "delta_e": result.delta_e,
    }
```

- [ ] **Step 4: Add `POST /api/scheme/generate`**

```python
@app.post("/api/scheme/generate")
def scheme_generate(req: SchemeGenerateRequest):
    from mini_highlight_advisor.scheme_gen import RegionColorSpec as PySpec
    from mini_highlight_advisor.scheme_build import build_scheme
    catalog = _catalog()
    owned_set = set(req.owned_codes)
    owned = [p for p in catalog if p.code in owned_set]
    owned_only = len(req.owned_codes) > 0
    py_specs = [
        PySpec(name=s.region_name, surface=s.surface, tone=s.tone, n_bands=s.n_bands)
        for s in req.specs
    ]
    scheme = build_scheme(
        name="generated",
        specs=py_specs,
        anchor_name=req.anchor_name,
        anchor_hex=req.anchor_hex,
        mood=req.mood,
        variant=req.variant,
        owned=owned,
        catalog=catalog,
        owned_only=owned_only,
    )
    return {"palettes": {name: [paint_to_dict(p) for p in pal]
                         for name, pal in scheme.palettes.items()}}
```

- [ ] **Step 5: Add recipe endpoints**

```python
@app.get("/api/recipes")
def list_recipes():
    from mini_highlight_advisor.recipes import load_all
    recipes = load_all()
    return {"recipes": [{"name": r.name,
                         "steps": [{"label": s.label, "hex": s.hex, "paint_ref": s.paint_ref}
                                   for s in r.steps]}
                        for r in recipes]}


@app.post("/api/recipes")
def save_recipe(req: RecipeModel):
    from mini_highlight_advisor.recipes import Recipe, RecipeStep, save_user
    recipe = Recipe(
        name=req.name,
        steps=[RecipeStep(label=s.label, hex=s.hex, paint_ref=s.paint_ref) for s in req.steps],
    )
    save_user(recipe)
    return {"ok": True}
```

- [ ] **Step 6: Add collection endpoints**

```python
@app.get("/api/collection")
def get_collection():
    from mini_highlight_advisor.collection import load
    return {"owned": sorted(load())}


@app.put("/api/collection")
def put_collection(body: dict):
    from mini_highlight_advisor.collection import save
    owned = set(body.get("owned", []))
    save(owned)
    return {"ok": True}
```

- [ ] **Step 7: Smoke-test the server starts**

Run: `.venv/Scripts/python -m uvicorn backend.main:app --port 8001 &`
Then: `.venv/Scripts/python -c "import httpx; r = httpx.get('http://localhost:8001/api/catalog'); print(r.status_code, len(r.json()['paints']))"` (expect `200 <N>`)
Kill the background server after.

- [ ] **Step 8: Commit**

```bash
git add backend/main.py
git commit -m "feat: implement catalog, match, scheme/generate, recipes, collection endpoints"
```

---

### Task 3: Backend — 5 new endpoints

**Files:**
- Modify: `backend/main.py` — add `POST /api/ramp/generate`, `GET /api/recipes/export`, `POST /api/recipes/import`, `GET /api/collection/export`, `POST /api/collection/import`

**Interfaces:**
- Consumes: `RampGenerateRequest` from Task 1; Python `color.{blend_hex_lab,hue_rotate,ramp_from_midtone}`, `recipes.{export_to_json_bytes,import_from_json_bytes,load_all}`, `collection.{export_to_json_bytes,import_from_json_bytes,load,save}`
- Produces: The 5 endpoints consumed by the frontend API client (Task 6)

- [ ] **Step 1: Add import for `RampGenerateRequest` in `backend/main.py`**

Update the existing import from Task 1:
```python
from backend.schemas import (
    RegionColorSpec as RegionColorSpecModel,
    SchemeGenerateRequest, RampGenerateRequest, MatchRequest, RecipeModel,
)
```

Also add at the top:
```python
from fastapi import FastAPI, File, HTTPException, UploadFile
from fastapi.responses import FileResponse, Response, StreamingResponse
```
(add `StreamingResponse` to the existing `fastapi.responses` import line)

- [ ] **Step 2: Add ramp variant degree mapping and `POST /api/ramp/generate`**

```python
_RAMP_DEGREES: dict[str, float] = {
    "ramp": 0.0, "complementary": 180.0, "warm": 30.0, "cool": -30.0,
}


@app.post("/api/ramp/generate")
def ramp_generate(req: RampGenerateRequest):
    from mini_highlight_advisor.color import blend_hex_lab, hue_rotate, ramp_from_midtone
    midtone = req.midtone_hex
    if req.blend_hexes and len(req.blend_hexes) == 2:
        midtone = blend_hex_lab(req.blend_hexes[0], req.blend_hexes[1])
    degrees = _RAMP_DEGREES.get(req.variant, 0.0)
    rotated = hue_rotate(midtone, degrees)
    hexes = ramp_from_midtone(rotated, req.n)
    return {"hexes": hexes}
```

- [ ] **Step 3: Add recipe export/import endpoints**

```python
@app.get("/api/recipes/export")
def export_recipes():
    from mini_highlight_advisor.recipes import export_to_json_bytes, load_all, load_builtin
    all_recipes = load_all()
    builtin = {r.name for r in load_builtin()}
    user_recipes = [r for r in all_recipes if r.name not in builtin]
    data = export_to_json_bytes(user_recipes)
    return Response(content=data, media_type="application/json",
                    headers={"Content-Disposition": "attachment; filename=recipes.json"})


@app.post("/api/recipes/import")
async def import_recipes(file: UploadFile = File(...)):
    from mini_highlight_advisor.recipes import import_from_json_bytes, load_all
    data = await file.read()
    import_from_json_bytes(data)
    recipes = load_all()
    return {"recipes": [{"name": r.name,
                         "steps": [{"label": s.label, "hex": s.hex, "paint_ref": s.paint_ref}
                                   for s in r.steps]}
                        for r in recipes]}
```

- [ ] **Step 4: Add collection export/import endpoints**

```python
@app.get("/api/collection/export")
def export_collection():
    from mini_highlight_advisor.collection import export_to_json_bytes, load
    data = export_to_json_bytes(load())
    return Response(content=data, media_type="application/json",
                    headers={"Content-Disposition": "attachment; filename=collection.json"})


@app.post("/api/collection/import")
async def import_collection(file: UploadFile = File(...)):
    from mini_highlight_advisor.collection import import_from_json_bytes, load, save
    data = await file.read()
    new_owned = import_from_json_bytes(data, _catalog())
    existing = load()
    merged = existing | new_owned
    save(merged)
    return {"owned": sorted(merged)}
```

- [ ] **Step 5: Commit**

```bash
git add backend/main.py
git commit -m "feat: add ramp/generate, recipe export/import, collection export/import endpoints"
```

---

### Task 4: Backend test suite

**Files:**
- Create: `backend/tests/test_catalog.py`
- Create: `backend/tests/test_match.py`
- Create: `backend/tests/test_ramp.py`
- Create: `backend/tests/test_scheme_generate.py`
- Create: `backend/tests/test_recipes.py`
- Create: `backend/tests/test_collection.py`

**Interfaces:**
- Consumes: All endpoints from Tasks 2 and 3

- [ ] **Step 1: Write `backend/tests/test_catalog.py`**

```python
from fastapi.testclient import TestClient
from backend.main import app

_client = TestClient(app)


def test_catalog_returns_nonempty_list():
    r = _client.get("/api/catalog")
    assert r.status_code == 200
    paints = r.json()["paints"]
    assert len(paints) > 0


def test_catalog_entries_have_required_fields():
    r = _client.get("/api/catalog")
    p = r.json()["paints"][0]
    for field in ("name", "hex", "code", "finish"):
        assert field in p, f"missing {field}"
```

- [ ] **Step 2: Write `backend/tests/test_match.py`**

```python
import pytest
from fastapi.testclient import TestClient
from backend.main import app

_client = TestClient(app)


def _catalog_code():
    r = _client.get("/api/catalog")
    return r.json()["paints"][0]["code"]


def test_match_exact_or_close_when_owned():
    code = _catalog_code()
    r = _client.get("/api/catalog")
    paint = r.json()["paints"][0]
    res = _client.post("/api/match", json={"hex": paint["hex"], "finish": "matte", "owned_codes": [code]})
    assert res.status_code == 200
    body = res.json()
    assert body["tier"] in ("exact", "close")
    assert body["delta_e"] >= 0


def test_match_unreachable_when_no_owned():
    res = _client.post("/api/match", json={"hex": "#ff0000", "finish": "matte", "owned_codes": []})
    assert res.status_code == 200
    assert res.json()["tier"] in ("exact", "close", "mix", "unreachable")


def test_match_response_has_required_fields():
    res = _client.post("/api/match", json={"hex": "#aabbcc", "finish": "matte", "owned_codes": []})
    body = res.json()
    for field in ("tier", "phrase", "delta_e"):
        assert field in body
```

- [ ] **Step 3: Write `backend/tests/test_ramp.py`**

```python
import re
from fastapi.testclient import TestClient
from backend.main import app

_client = TestClient(app)
_HEX = re.compile(r"^#[0-9a-fA-F]{6}$")


def _ramp(variant: str, n: int = 5, midtone: str = "#808080"):
    return _client.post("/api/ramp/generate", json={"midtone_hex": midtone, "n": n, "variant": variant})


def test_ramp_returns_correct_length():
    for variant in ("ramp", "complementary", "warm", "cool"):
        r = _ramp(variant, n=5)
        assert r.status_code == 200, variant
        hexes = r.json()["hexes"]
        assert len(hexes) == 5, variant


def test_ramp_hexes_are_valid_css():
    hexes = _ramp("ramp", n=3).json()["hexes"]
    for h in hexes:
        assert _HEX.match(h), f"invalid hex: {h}"


def test_ramp_blend_hexes_overrides_midtone():
    r = _client.post("/api/ramp/generate", json={
        "midtone_hex": "#000000",  # ignored when blend_hexes set
        "n": 3,
        "variant": "ramp",
        "blend_hexes": ["#200000", "#ff8080"],
    })
    assert r.status_code == 200
    assert len(r.json()["hexes"]) == 3
```

- [ ] **Step 4: Write `backend/tests/test_scheme_generate.py`**

```python
from fastapi.testclient import TestClient
from backend.main import app

_client = TestClient(app)


def _spec(name: str, surface: str = "skin", n_bands: int = 3, is_anchor: bool = False):
    return {"region_name": name, "surface": surface, "n_bands": n_bands, "is_anchor": is_anchor}


def test_scheme_single_region():
    r = _client.post("/api/scheme/generate", json={
        "specs": [_spec("Whole Mini", is_anchor=True)],
        "anchor_name": "Whole Mini",
        "anchor_hex": "#c0392b",
        "mood": "neutral",
        "variant": "complementary",
        "owned_codes": [],
    })
    assert r.status_code == 200
    palettes = r.json()["palettes"]
    assert "Whole Mini" in palettes
    assert len(palettes["Whole Mini"]) == 3


def test_scheme_multi_region_returns_all_keys():
    r = _client.post("/api/scheme/generate", json={
        "specs": [_spec("Whole Mini", is_anchor=True), _spec("helmet", surface="metal")],
        "anchor_name": "Whole Mini",
        "anchor_hex": "#c0392b",
        "mood": "heroic",
        "variant": "analogous",
        "owned_codes": [],
    })
    assert r.status_code == 200
    palettes = r.json()["palettes"]
    assert "Whole Mini" in palettes
    assert "helmet" in palettes
```

- [ ] **Step 5: Write `backend/tests/test_recipes.py`**

```python
import json
from fastapi.testclient import TestClient
from backend.main import app

_client = TestClient(app)


def test_list_recipes_returns_list():
    r = _client.get("/api/recipes")
    assert r.status_code == 200
    assert isinstance(r.json()["recipes"], list)


def test_save_and_list_recipe():
    payload = {"name": "__test_recipe__", "steps": [{"label": "base", "hex": "#8b4513", "paint_ref": None}]}
    r = _client.post("/api/recipes", json=payload)
    assert r.status_code == 200
    assert r.json()["ok"] is True
    names = [rec["name"] for rec in _client.get("/api/recipes").json()["recipes"]]
    assert "__test_recipe__" in names


def test_export_recipes_bytes():
    r = _client.get("/api/recipes/export")
    assert r.status_code == 200
    assert r.headers["content-type"].startswith("application/json")
    parsed = json.loads(r.content)
    assert "recipes" in parsed


def test_import_recipes_merges():
    data = json.dumps({"recipes": [{"name": "__imported__", "steps": [{"label": "l", "hex": "#aabbcc"}]}]}).encode()
    r = _client.post("/api/recipes/import", files={"file": ("r.json", data, "application/json")})
    assert r.status_code == 200
    names = [rec["name"] for rec in r.json()["recipes"]]
    assert "__imported__" in names
```

- [ ] **Step 6: Write `backend/tests/test_collection.py`**

```python
import json
from fastapi.testclient import TestClient
from backend.main import app

_client = TestClient(app)


def test_get_collection_returns_list():
    r = _client.get("/api/collection")
    assert r.status_code == 200
    assert isinstance(r.json()["owned"], list)


def test_put_collection_round_trip():
    r = _client.get("/api/catalog")
    code = r.json()["paints"][0]["code"]
    _client.put("/api/collection", json={"owned": [code]})
    owned = _client.get("/api/collection").json()["owned"]
    assert code in owned


def test_export_import_collection_round_trip():
    r = _client.get("/api/catalog")
    code = r.json()["paints"][0]["code"]
    _client.put("/api/collection", json={"owned": [code]})
    export = _client.get("/api/collection/export")
    assert export.status_code == 200
    data = export.content
    r2 = _client.post("/api/collection/import", files={"file": ("c.json", data, "application/json")})
    assert r2.status_code == 200
    assert code in r2.json()["owned"]
```

- [ ] **Step 7: Run all backend tests**

Run: `.venv/Scripts/python -m pytest backend/tests/ -v`
Expected: all tests pass (green)

- [ ] **Step 8: Commit**

```bash
git add backend/tests/
git commit -m "test: add backend tests for catalog, match, ramp, scheme, recipes, collection"
```

---

### Task 5: projectStore extension — types and 13 new actions

**Files:**
- Modify: `web/src/store/projectStore.ts` — extend types + add 13 new actions + update `makeAngle`
- Modify: `web/src/store/projectStore.test.ts` — add tests for all 13 new actions

**Interfaces:**
- Produces: `WholeState`, `Scheme`, extended `DrawnRegion`, extended `Book`; actions: `setSurface`, `setTone`, `setMaterial`, `setHeroHex`, `setMood`, `setVariant`, `setRampState`, `setPaletteAt`, `setPaletteSlot`, `setHexSlot`, `saveScheme`, `applyScheme`, `deleteScheme`

- [ ] **Step 1: Update type definitions in `web/src/store/projectStore.ts`**

Replace the existing `DrawnRegion` and `Book` interfaces and add new types. Find the block:

```ts
export interface DrawnRegion {
  id: string; name: string; rings: number[][][];
  palette: PaintColor[]; coverage: number[]; material: string; blank: boolean;
}
export interface Book { whole: Whole; drawn: DrawnRegion[]; selected: number; }
```

Replace with:

```ts
export interface WholeState extends Whole {
  surface?: string;
  tone?: string;
  ramp_midtone?: string;
  ramp_variant?: string;
}

export interface DrawnRegion {
  id: string; name: string; rings: number[][][];
  palette: PaintColor[]; coverage: number[]; material: string; blank: boolean;
  surface?: string;
  tone?: string;
  ramp_midtone?: string;
  ramp_variant?: string;
}

export interface Scheme {
  id: string;
  name: string;
  palettes: { [regionId: string]: PaintColor[] };
  anchor_hex?: string;
}

export interface Book {
  whole: WholeState;
  drawn: DrawnRegion[];
  selected: number;
  hero_hex?: string;
  mood?: string;
  variant?: string;
  schemes: Scheme[];
}
```

Also update the `Angle` type — `book: Book` already references `Book`, so `whole` now satisfies `WholeState` automatically since it's structurally compatible (all new fields are optional).

- [ ] **Step 2: Add 13 new actions to the `State` interface**

Append these to the `State` interface (after `setError`):

```ts
  setSurface(g: number, surface: string): void;
  setTone(g: number, tone: string): void;
  setMaterial(g: number, material: string): void;
  setHeroHex(hex: string): void;
  setMood(mood: string): void;
  setVariant(variant: string): void;
  setRampState(g: number, midtone: string, variant: string): void;
  setPaletteAt(g: number, palette: PaintColor[]): void;
  setPaletteSlot(g: number, i: number, paint: PaintColor): void;
  setHexSlot(g: number, i: number, hex: string): void;
  saveScheme(name: string): void;
  applyScheme(id: string): void;
  deleteScheme(id: string): void;
```

- [ ] **Step 3: Update `makeAngle` to initialise `book.schemes`**

Find `book: { whole: res.default_whole, drawn: [], selected: 0 }` and change to:

```ts
book: { whole: res.default_whole, drawn: [], selected: 0, schemes: [] },
```

- [ ] **Step 4: Implement the 13 new actions in the `useProjectStore` body**

Append after `setError`:

```ts
  setSurface: (g, surface) => set((s) => patchBook(s, (b) => {
    if (g === 0) return { ...b, whole: { ...b.whole, surface } };
    const drawn = b.drawn.slice();
    drawn[g - 1] = { ...drawn[g - 1], surface };
    return { ...b, drawn };
  })),

  setTone: (g, tone) => set((s) => patchBook(s, (b) => {
    if (g === 0) return { ...b, whole: { ...b.whole, tone } };
    const drawn = b.drawn.slice();
    drawn[g - 1] = { ...drawn[g - 1], tone };
    return { ...b, drawn };
  })),

  setMaterial: (g, material) => set((s) => patchBook(s, (b) => {
    if (g === 0) return { ...b, whole: { ...b.whole, material } };
    const drawn = b.drawn.slice();
    drawn[g - 1] = { ...drawn[g - 1], material };
    return { ...b, drawn };
  })),

  setHeroHex: (hex) => set((s) => patchBook(s, (b) => ({ ...b, hero_hex: hex }))),

  setMood: (mood) => set((s) => patchBook(s, (b) => ({ ...b, mood }))),

  setVariant: (variant) => set((s) => patchBook(s, (b) => ({ ...b, variant }))),

  setRampState: (g, midtone, variant) => set((s) => patchBook(s, (b) => {
    if (g === 0) return { ...b, whole: { ...b.whole, ramp_midtone: midtone, ramp_variant: variant } };
    const drawn = b.drawn.slice();
    drawn[g - 1] = { ...drawn[g - 1], ramp_midtone: midtone, ramp_variant: variant };
    return { ...b, drawn };
  })),

  setPaletteAt: (g, palette) => set((s) => patchBook(s, (b) => {
    if (g === 0) return { ...b, whole: { ...b.whole, palette } };
    const drawn = b.drawn.slice();
    drawn[g - 1] = { ...drawn[g - 1], palette };
    return { ...b, drawn };
  })),

  setPaletteSlot: (g, i, paint) => set((s) => patchBook(s, (b) => {
    const region = g === 0 ? b.whole : b.drawn[g - 1];
    if (!region) return b;
    const palette = region.palette.slice();
    palette[i] = paint;
    if (g === 0) return { ...b, whole: { ...b.whole, palette } };
    const drawn = b.drawn.slice();
    drawn[g - 1] = { ...drawn[g - 1], palette };
    return { ...b, drawn };
  })),

  setHexSlot: (g, i, hex) => set((s) => patchBook(s, (b) => {
    const region = g === 0 ? b.whole : b.drawn[g - 1];
    if (!region) return b;
    const palette = region.palette.slice();
    palette[i] = { name: "custom", hex, code: "", finish: palette[i]?.finish ?? "matte" };
    if (g === 0) return { ...b, whole: { ...b.whole, palette } };
    const drawn = b.drawn.slice();
    drawn[g - 1] = { ...drawn[g - 1], palette };
    return { ...b, drawn };
  })),

  saveScheme: (name) => set((s) => patchBook(s, (b) => {
    const palettes: { [id: string]: PaintColor[] } = {};
    palettes["__whole__"] = b.whole.palette.slice();
    for (const r of b.drawn) palettes[r.id] = r.palette.slice();
    const scheme: Scheme = { id: newId(), name, palettes, anchor_hex: b.hero_hex };
    return { ...b, schemes: [...b.schemes, scheme] };
  })),

  applyScheme: (id) => set((s) => patchBook(s, (b) => {
    const scheme = b.schemes.find((sc) => sc.id === id);
    if (!scheme) return b;
    const wholePal = scheme.palettes["__whole__"];
    const whole = wholePal ? { ...b.whole, palette: wholePal.slice() } : b.whole;
    const drawn = b.drawn.map((r) => {
      const pal = scheme.palettes[r.id];
      return pal ? { ...r, palette: pal.slice() } : r;
    });
    return { ...b, whole, drawn };
  })),

  deleteScheme: (id) => set((s) => patchBook(s, (b) => ({
    ...b, schemes: b.schemes.filter((sc) => sc.id !== id),
  }))),
```

- [ ] **Step 5: Write failing tests in `web/src/store/projectStore.test.ts`**

Append to the end of the existing test file:

```ts
describe("projectStore colour extensions", () => {
  beforeEach(reset);

  it("setSurface updates whole when g=0", () => {
    useProjectStore.getState().initFromPhoto(photo("p1"));
    useProjectStore.getState().setSurface(0, "metal");
    expect(activeBookOf(useProjectStore.getState())!.whole.surface).toBe("metal");
  });

  it("setSurface updates drawn region when g=1", () => {
    const st = useProjectStore.getState();
    st.initFromPhoto(photo("p1"));
    st.addRegion([[[0, 0], [1, 0], [1, 1]]], "helm");
    st.setSurface(1, "bone");
    expect(activeBookOf(useProjectStore.getState())!.drawn[0].surface).toBe("bone");
  });

  it("setMaterial updates whole material", () => {
    useProjectStore.getState().initFromPhoto(photo("p1"));
    useProjectStore.getState().setMaterial(0, "metallic");
    expect(activeBookOf(useProjectStore.getState())!.whole.material).toBe("metallic");
  });

  it("setHeroHex persists to book", () => {
    useProjectStore.getState().initFromPhoto(photo("p1"));
    useProjectStore.getState().setHeroHex("#c0392b");
    expect(activeBookOf(useProjectStore.getState())!.hero_hex).toBe("#c0392b");
  });

  it("setMood and setVariant persist", () => {
    useProjectStore.getState().initFromPhoto(photo("p1"));
    useProjectStore.getState().setMood("grimdark");
    useProjectStore.getState().setVariant("triadic");
    const b = activeBookOf(useProjectStore.getState())!;
    expect(b.mood).toBe("grimdark");
    expect(b.variant).toBe("triadic");
  });

  it("setRampState stores midtone and variant on drawn region", () => {
    const st = useProjectStore.getState();
    st.initFromPhoto(photo("p1"));
    st.addRegion([[[0, 0], [1, 0], [1, 1]]]);
    st.setRampState(1, "#8b4513", "complementary");
    const r = activeBookOf(useProjectStore.getState())!.drawn[0];
    expect(r.ramp_midtone).toBe("#8b4513");
    expect(r.ramp_variant).toBe("complementary");
  });

  it("setPaletteAt replaces whole palette when g=0", () => {
    useProjectStore.getState().initFromPhoto(photo("p1"));
    const pal = [{ name: "x", hex: "#ff0000", code: "X1", finish: "matte" }];
    useProjectStore.getState().setPaletteAt(0, pal);
    expect(activeBookOf(useProjectStore.getState())!.whole.palette).toEqual(pal);
  });

  it("setPaletteSlot replaces one slot", () => {
    const st = useProjectStore.getState();
    st.initFromPhoto(photo("p1"));
    const paint = { name: "Red", hex: "#ff0000", code: "R1", finish: "matte" };
    st.setPaletteSlot(0, 0, paint);
    expect(activeBookOf(useProjectStore.getState())!.whole.palette[0]).toEqual(paint);
  });

  it("setHexSlot creates custom entry with empty code", () => {
    useProjectStore.getState().initFromPhoto(photo("p1"));
    useProjectStore.getState().setHexSlot(0, 1, "#00ff00");
    const slot = activeBookOf(useProjectStore.getState())!.whole.palette[1];
    expect(slot.code).toBe("");
    expect(slot.hex).toBe("#00ff00");
    expect(slot.name).toBe("custom");
  });

  it("saveScheme snapshots current palettes keyed by region id", () => {
    const st = useProjectStore.getState();
    st.initFromPhoto(photo("p1"));
    st.addRegion([[[0, 0], [1, 0], [1, 1]]], "helm");
    st.saveScheme("my scheme");
    const b = activeBookOf(useProjectStore.getState())!;
    expect(b.schemes).toHaveLength(1);
    expect(b.schemes[0].name).toBe("my scheme");
    expect("__whole__" in b.schemes[0].palettes).toBe(true);
    expect(b.drawn[0].id in b.schemes[0].palettes).toBe(true);
  });

  it("applyScheme restores palettes; silently skips missing region ids", () => {
    const st = useProjectStore.getState();
    st.initFromPhoto(photo("p1"));
    st.addRegion([[[0, 0], [1, 0], [1, 1]]], "helm");
    st.setHexSlot(0, 0, "#ff0000");
    st.saveScheme("snap");
    st.setHexSlot(0, 0, "#0000ff");   // mutate after snapshot
    const schemeId = activeBookOf(useProjectStore.getState())!.schemes[0].id;
    st.applyScheme(schemeId);
    expect(activeBookOf(useProjectStore.getState())!.whole.palette[0].hex).toBe("#ff0000");
  });

  it("applyScheme silently skips region ids not in current book", () => {
    const st = useProjectStore.getState();
    st.initFromPhoto(photo("p1"));
    // Inject a scheme with a stale region id
    const staleScheme: import("./projectStore").Scheme = {
      id: "sch1", name: "old",
      palettes: { "__whole__": [{ name: "a", hex: "#aaaaaa" }], "stale-id": [] },
    };
    st.initFromPhoto(photo("p1"));
    const b = activeBookOf(useProjectStore.getState())!;
    useProjectStore.setState({
      angles: [{ ...useProjectStore.getState().angles[0], book: { ...b, schemes: [staleScheme] } }]
    });
    expect(() => st.applyScheme("sch1")).not.toThrow();
  });

  it("deleteScheme removes scheme by id", () => {
    const st = useProjectStore.getState();
    st.initFromPhoto(photo("p1"));
    st.saveScheme("A");
    st.saveScheme("B");
    const b = activeBookOf(useProjectStore.getState())!;
    st.deleteScheme(b.schemes[0].id);
    expect(activeBookOf(useProjectStore.getState())!.schemes).toHaveLength(1);
    expect(activeBookOf(useProjectStore.getState())!.schemes[0].name).toBe("B");
  });
});
```

- [ ] **Step 6: Run tests**

Run: `cd web && npm test -- --reporter=verbose`
Expected: all existing tests pass + 13 new tests pass

- [ ] **Step 7: Commit**

```bash
git add web/src/store/projectStore.ts web/src/store/projectStore.test.ts
git commit -m "feat: extend projectStore with colour-editor types and 13 new actions"
```

---

### Task 6: catalogStore

**Files:**
- Create: `web/src/store/catalogStore.ts`
- Create: `web/src/store/catalogStore.test.ts`

**Interfaces:**
- Produces: `useCatalogStore` — `{ paints, status, error, fetch, findByCode }` — consumed by `SchemeGenerator`, `BandSlot`, `RecipeLoader`, `App.tsx`

- [ ] **Step 1: Write `web/src/store/catalogStore.ts`**

```ts
import { create } from "zustand";
import { fetchCatalog } from "../api/client";
import type { PaintColor } from "../api/types";

interface CatalogState {
  paints: PaintColor[];
  status: "idle" | "loading" | "ready" | "error";
  error?: string;
  fetch(): Promise<void>;
  findByCode(code: string): PaintColor | undefined;
}

export const useCatalogStore = create<CatalogState>((set, get) => ({
  paints: [],
  status: "idle",

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
}));
```

- [ ] **Step 2: Write failing `web/src/store/catalogStore.test.ts`**

```ts
import { describe, it, expect, beforeEach, vi } from "vitest";
import { useCatalogStore } from "./catalogStore";
import * as client from "../api/client";
import type { PaintColor } from "../api/types";

const reset = () => useCatalogStore.setState({ paints: [], status: "idle", error: undefined });
const fakePaint = (code: string): PaintColor => ({ name: "P", hex: "#aabbcc", code, finish: "matte" });

describe("catalogStore", () => {
  beforeEach(() => {
    reset();
    vi.restoreAllMocks();
  });

  it("fetch transitions idle → loading → ready", async () => {
    vi.spyOn(client, "fetchCatalog").mockResolvedValue({ paints: [fakePaint("X1")] });
    expect(useCatalogStore.getState().status).toBe("idle");
    await useCatalogStore.getState().fetch();
    const s = useCatalogStore.getState();
    expect(s.status).toBe("ready");
    expect(s.paints).toHaveLength(1);
  });

  it("fetch is idempotent — second call is a no-op", async () => {
    const spy = vi.spyOn(client, "fetchCatalog").mockResolvedValue({ paints: [fakePaint("X1")] });
    await useCatalogStore.getState().fetch();
    await useCatalogStore.getState().fetch();
    expect(spy).toHaveBeenCalledTimes(1);
  });

  it("findByCode returns matching paint", async () => {
    vi.spyOn(client, "fetchCatalog").mockResolvedValue({ paints: [fakePaint("X1"), fakePaint("X2")] });
    await useCatalogStore.getState().fetch();
    expect(useCatalogStore.getState().findByCode("X2")).toMatchObject({ code: "X2" });
    expect(useCatalogStore.getState().findByCode("NOPE")).toBeUndefined();
  });

  it("fetch sets error status on rejection", async () => {
    vi.spyOn(client, "fetchCatalog").mockRejectedValue(new Error("network"));
    await useCatalogStore.getState().fetch();
    expect(useCatalogStore.getState().status).toBe("error");
  });
});
```

- [ ] **Step 3: Run tests**

Run: `cd web && npm test -- --reporter=verbose`
Expected: 4 new catalogStore tests pass

- [ ] **Step 4: Commit**

```bash
git add web/src/store/catalogStore.ts web/src/store/catalogStore.test.ts
git commit -m "feat: add catalogStore with idempotent fetch and findByCode"
```

---

### Task 7: API types and client extensions

**Files:**
- Modify: `web/src/api/types.ts` — add new request/response interfaces + constants
- Modify: `web/src/api/client.ts` — add 12 new typed fetch functions

**Interfaces:**
- Produces: all functions consumed by frontend components in Tasks 9–14

- [ ] **Step 1: Append new types to `web/src/api/types.ts`**

Append to `web/src/api/types.ts`:

```ts
// Colour-panel request/response types
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
  blend_hexes?: [string, string];
}
export interface RampGenerateResponse { hexes: string[]; }
export interface MatchRequest { hex: string; finish: string; owned_codes: string[]; }
export interface MatchResult {
  tier: string; phrase: string; name?: string; hex?: string; delta_e: number;
}
export interface RecipeStep { label: string; hex: string; paint_ref?: string | null; }
export interface Recipe { name: string; steps: RecipeStep[]; }
export interface CatalogResponse { paints: PaintColor[]; }

// Constants (mirrors Python)
export const MOODS = ["neutral", "grimdark", "heroic", "natural"] as const;
export const VARIANTS = ["complementary", "analogous", "triadic", "split-complementary"] as const;
export const RAMP_VARIANTS = ["ramp", "complementary", "warm", "cool"] as const;
export const SURFACES = [
  "skin", "bone", "metal", "wood", "leather", "fur", "cloth",
  "cloak", "robe", "gem", "accent", "other",
] as const;
```

- [ ] **Step 2: Add 12 functions to `web/src/api/client.ts`**

Append to `web/src/api/client.ts`:

```ts
import type {
  CatalogResponse, MatchRequest, MatchResult,
  SchemeGenerateRequest, SchemeGenerateResponse,
  RampGenerateRequest, RampGenerateResponse,
  Recipe,
} from "./types";

export async function fetchCatalog(): Promise<CatalogResponse> {
  return json<CatalogResponse>(await fetch("/api/catalog"));
}

export async function matchPaint(req: MatchRequest): Promise<MatchResult> {
  return json<MatchResult>(await fetch("/api/match", {
    method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(req),
  }));
}

export async function generateScheme(req: SchemeGenerateRequest): Promise<SchemeGenerateResponse> {
  return json<SchemeGenerateResponse>(await fetch("/api/scheme/generate", {
    method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(req),
  }));
}

export async function generateRamp(req: RampGenerateRequest): Promise<RampGenerateResponse> {
  return json<RampGenerateResponse>(await fetch("/api/ramp/generate", {
    method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(req),
  }));
}

export async function listRecipes(): Promise<{ recipes: Recipe[] }> {
  return json<{ recipes: Recipe[] }>(await fetch("/api/recipes"));
}

export async function saveRecipe(recipe: Recipe): Promise<{ ok: boolean }> {
  return json<{ ok: boolean }>(await fetch("/api/recipes", {
    method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(recipe),
  }));
}

export async function exportRecipes(): Promise<Blob> {
  const res = await fetch("/api/recipes/export");
  if (!res.ok) throw new Error(`${res.status}`);
  return res.blob();
}

export async function importRecipes(file: File): Promise<{ recipes: Recipe[] }> {
  const fd = new FormData();
  fd.append("file", file, file.name);
  return json<{ recipes: Recipe[] }>(await fetch("/api/recipes/import", { method: "POST", body: fd }));
}

export async function getCollection(): Promise<{ owned: string[] }> {
  return json<{ owned: string[] }>(await fetch("/api/collection"));
}

export async function putCollection(owned: string[]): Promise<{ ok: boolean }> {
  return json<{ ok: boolean }>(await fetch("/api/collection", {
    method: "PUT", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ owned }),
  }));
}

export async function exportCollection(): Promise<Blob> {
  const res = await fetch("/api/collection/export");
  if (!res.ok) throw new Error(`${res.status}`);
  return res.blob();
}

export async function importCollection(file: File): Promise<{ owned: string[] }> {
  const fd = new FormData();
  fd.append("file", file, file.name);
  return json<{ owned: string[] }>(await fetch("/api/collection/import", { method: "POST", body: fd }));
}
```

Note: `json<T>` is already defined in `client.ts` at line 3 — no re-declaration needed.

- [ ] **Step 3: Check TypeScript compiles**

Run: `cd web && npx tsc --noEmit`
Expected: no errors

- [ ] **Step 4: Commit**

```bash
git add web/src/api/types.ts web/src/api/client.ts
git commit -m "feat: extend API types and client with 12 colour-panel functions"
```

---

### Task 8: i18n setup

**Files:**
- Create: `web/src/i18n/index.ts`
- Create: `web/src/i18n/locales/en.json`
- Create: `web/src/i18n/locales/es.json`
- Modify: `web/src/main.tsx`
- Shell: install react-i18next

**Interfaces:**
- Produces: `useTranslation` hook available across all new components

- [ ] **Step 1: Install react-i18next**

Run: `cd web && npm install react-i18next i18next`
Expected: package.json updated, node_modules populated

- [ ] **Step 2: Create `web/src/i18n/index.ts`**

```ts
import i18n from "i18next";
import { initReactI18next } from "react-i18next";
import en from "./locales/en.json";
import es from "./locales/es.json";

i18n.use(initReactI18next).init({
  lng: "en",
  fallbackLng: "en",
  resources: { en: { translation: en }, es: { translation: es } },
  interpolation: { escapeValue: false },
});

export default i18n;
```

- [ ] **Step 3: Create `web/src/i18n/locales/en.json`**

```json
{
  "tabs": {
    "manage": "Manage",
    "colour": "Colour",
    "technique": "Technique"
  },
  "technique": {
    "material": "Material",
    "matte": "Matte",
    "metallic": "Metallic"
  },
  "colour": {
    "scheme_generator": "Scheme Generator (L1)",
    "anchor_region": "Anchor region",
    "hero_colour": "Hero colour",
    "mood": "Mood",
    "harmony": "Harmony variant",
    "surface": "Surface",
    "tone": "Tone",
    "owned_only": "Owned paints only",
    "generate": "Generate",
    "generating": "Generating…",
    "ramp_editor": "Ramp Generator (L2)",
    "midtone": "Midtone",
    "use_scheme_colour": "Use scheme colour",
    "ramp": "Ramp",
    "complementary": "Complementary",
    "warm": "Warm",
    "cool": "Cool",
    "band_editor": "Band Editor (L3)",
    "band_count": "Bands",
    "reset_coverage": "Reset coverage",
    "recipe_name": "Recipe name",
    "save_recipe": "Save recipe",
    "recipe_saved": "Recipe saved",
    "load_recipe": "Load",
    "select_recipe": "Select recipe…",
    "custom": "(custom)",
    "blend": "Blend",
    "add_band": "Add band",
    "delete_band": "Delete band"
  },
  "schemes": {
    "title": "Colour Schemes",
    "name_placeholder": "Scheme name",
    "save": "Save snapshot",
    "apply": "Apply",
    "delete": "Delete"
  },
  "recipes": {
    "export": "Export recipes",
    "import": "Import recipes"
  },
  "surfaces": {
    "skin": "Skin",
    "bone": "Bone",
    "metal": "Metal",
    "wood": "Wood",
    "leather": "Leather",
    "fur": "Fur",
    "cloth": "Cloth",
    "cloak": "Cloak",
    "robe": "Robe",
    "gem": "Gem",
    "accent": "Accent",
    "other": "Other"
  },
  "moods": {
    "neutral": "Neutral",
    "grimdark": "Grimdark",
    "heroic": "Heroic",
    "natural": "Natural"
  },
  "variants": {
    "complementary": "Complementary",
    "analogous": "Analogous",
    "triadic": "Triadic",
    "split-complementary": "Split-Complementary"
  }
}
```

- [ ] **Step 4: Create `web/src/i18n/locales/es.json`**

```json
{}
```

- [ ] **Step 5: Import i18n in `web/src/main.tsx`**

Add `import "./i18n/index";` as the first import in `main.tsx`, before the React imports:

```ts
import "./i18n/index";
import { StrictMode } from 'react'
import { createRoot } from 'react-dom/client'
import './index.css'
import App from './App.tsx'

createRoot(document.getElementById('root')!).render(
  <StrictMode>
    <App />
  </StrictMode>,
)
```

- [ ] **Step 6: Verify TypeScript compiles**

Run: `cd web && npx tsc --noEmit`
Expected: no errors

- [ ] **Step 7: Commit**

```bash
git add web/src/i18n/ web/src/main.tsx web/package.json web/package-lock.json
git commit -m "feat: add react-i18next with en/es locale stubs"
```

---

### Task 9: RightPanel + TechniquePanel

**Files:**
- Create: `web/src/components/RightPanel.tsx`
- Create: `web/src/components/RightPanel.test.tsx`
- Create: `web/src/components/TechniquePanel.tsx`

**Interfaces:**
- Consumes: `useTranslation`, `setMaterial` from store
- Produces: `<RightPanel />` — consumed by `App.tsx` in Task 14

- [ ] **Step 1: Create `web/src/components/TechniquePanel.tsx`**

```tsx
import { useTranslation } from "react-i18next";
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
    <div style={{ padding: 8 }}>
      <label>
        {t("technique.material")}
        {" "}
        <select value={material} onChange={(e) => setMaterial(selected, e.target.value)}>
          <option value="matte">{t("technique.matte")}</option>
          <option value="metallic">{t("technique.metallic")}</option>
        </select>
      </label>
    </div>
  );
}
```

- [ ] **Step 2: Create `web/src/components/RightPanel.tsx`**

```tsx
import { useState } from "react";
import { useTranslation } from "react-i18next";
import { ManagePanel } from "./ManagePanel";
import { ColourPanel } from "./colour/ColourPanel";
import { TechniquePanel } from "./TechniquePanel";

type Tab = "manage" | "colour" | "technique";
const TABS: Tab[] = ["manage", "colour", "technique"];

export function RightPanel() {
  const { t } = useTranslation();
  const [active, setActive] = useState<Tab>("manage");

  return (
    <div>
      <div role="tablist" style={{ display: "flex", gap: 4, marginBottom: 8 }}>
        {TABS.map((tab) => (
          <button
            key={tab}
            role="tab"
            aria-selected={active === tab}
            onClick={() => setActive(tab)}
            style={{ fontWeight: active === tab ? "bold" : "normal" }}
          >
            {t(`tabs.${tab}`)}
          </button>
        ))}
      </div>
      <div role="tabpanel">
        {active === "manage" && <ManagePanel />}
        {active === "colour" && <ColourPanel />}
        {active === "technique" && <TechniquePanel />}
      </div>
    </div>
  );
}
```

- [ ] **Step 3: Write `web/src/components/RightPanel.test.tsx`**

```tsx
import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, fireEvent } from "@testing-library/react";
import { RightPanel } from "./RightPanel";

vi.mock("./ManagePanel", () => ({ ManagePanel: () => <div>ManagePanel</div> }));
vi.mock("./colour/ColourPanel", () => ({ ColourPanel: () => <div>ColourPanel</div> }));
vi.mock("./TechniquePanel", () => ({ TechniquePanel: () => <div>TechniquePanel</div> }));
vi.mock("react-i18next", () => ({
  useTranslation: () => ({ t: (k: string) => k }),
}));

describe("RightPanel", () => {
  it("renders ManagePanel by default", () => {
    render(<RightPanel />);
    expect(screen.getByText("ManagePanel")).toBeTruthy();
  });

  it("clicking Colour tab renders ColourPanel", () => {
    render(<RightPanel />);
    fireEvent.click(screen.getByText("tabs.colour"));
    expect(screen.getByText("ColourPanel")).toBeTruthy();
    expect(screen.queryByText("ManagePanel")).toBeNull();
  });

  it("clicking Technique tab renders TechniquePanel", () => {
    render(<RightPanel />);
    fireEvent.click(screen.getByText("tabs.technique"));
    expect(screen.getByText("TechniquePanel")).toBeTruthy();
  });
});
```

- [ ] **Step 4: Run tests**

Run: `cd web && npm test -- --reporter=verbose`
Expected: 3 new RightPanel tests pass

- [ ] **Step 5: Commit**

```bash
git add web/src/components/RightPanel.tsx web/src/components/RightPanel.test.tsx web/src/components/TechniquePanel.tsx
git commit -m "feat: add RightPanel tab strip and TechniquePanel"
```

---

### Task 10: ColourPanel shell + SchemeGenerator (L1)

**Files:**
- Create: `web/src/components/colour/ColourPanel.tsx`
- Create: `web/src/components/colour/SchemeGenerator.tsx`

**Interfaces:**
- Consumes: `generateScheme`, store actions `setPaletteAt`, `setHeroHex`, `setMood`, `setVariant`, `setSurface`, `setTone`; `useCatalogStore`
- Produces: `<ColourPanel />`, `<SchemeGenerator />`

- [ ] **Step 1: Create `web/src/components/colour/ColourPanel.tsx`**

```tsx
import { SchemeGenerator } from "./SchemeGenerator";
import { RampEditor } from "./RampEditor";
import { BandEditor } from "./BandEditor";
import { SchemeManager } from "./SchemeManager";

export function ColourPanel() {
  return (
    <div style={{ display: "flex", flexDirection: "column", gap: 16 }}>
      <SchemeGenerator />
      <RampEditor />
      <BandEditor />
      <SchemeManager />
    </div>
  );
}
```

- [ ] **Step 2: Create `web/src/components/colour/SchemeGenerator.tsx`**

```tsx
import { useState, useEffect } from "react";
import { useTranslation } from "react-i18next";
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

  // Grow perRegion if drawn regions were added after mount
  useEffect(() => {
    if (!book) return;
    const needed = 1 + book.drawn.length;
    if (perRegion.length < needed) {
      setPerRegion((prev) => [
        ...prev,
        ...Array.from({ length: needed - prev.length }, (_, i) => {
          const di = prev.length - 1 + i;
          return { surface: book.drawn[di]?.surface ?? "skin", tone: book.drawn[di]?.tone ?? "" };
        }),
      ]);
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
      const res = await generateScheme({
        specs,
        anchor_name: anchorName,
        anchor_hex: heroHex,
        mood,
        variant,
        owned_codes: ownedCodes,
      });
      regionNames.forEach((name, i) => {
        const pal = res.palettes[name];
        if (pal) setPaletteAt(i, pal);
      });
      setHeroHex(heroHex);
      setMood(mood);
      setVariant(variant);
      regionNames.forEach((_, i) => {
        setSurface(i, perRegion[i]?.surface ?? "skin");
        if (perRegion[i]?.tone) setTone(i, perRegion[i].tone);
      });
    } finally {
      setLoading(false);
    }
  };

  const updatePerRegion = (i: number, field: "surface" | "tone", value: string) =>
    setPerRegion((prev) => prev.map((r, j) => j === i ? { ...r, [field]: value } : r));

  return (
    <section>
      <h4 style={{ margin: "0 0 8px" }}>{t("colour.scheme_generator")}</h4>

      <label>
        {t("colour.anchor_region")}:{" "}
        <select value={anchorIndex} onChange={(e) => setAnchorIndex(Number(e.target.value))}>
          {regionNames.map((name, i) => <option key={i} value={i}>{name}</option>)}
        </select>
      </label>

      <br />
      <label>
        {t("colour.hero_colour")}:{" "}
        <input type="color" value={heroHex} onChange={(e) => setHeroHexLocal(e.target.value)} />
        <input type="text" value={heroHex} style={{ width: 80, marginLeft: 4 }}
          onChange={(e) => setHeroHexLocal(e.target.value)} />
      </label>

      <br />
      <label>
        {t("colour.mood")}:{" "}
        <select value={mood} onChange={(e) => setMoodLocal(e.target.value)}>
          {MOODS.map((m) => <option key={m} value={m}>{t(`moods.${m}`)}</option>)}
        </select>
      </label>

      <br />
      <label>
        {t("colour.harmony")}:{" "}
        <select value={variant} onChange={(e) => setVariantLocal(e.target.value)}>
          {VARIANTS.map((v) => <option key={v} value={v}>{t(`variants.${v}`)}</option>)}
        </select>
      </label>

      <div style={{ marginTop: 8 }}>
        {regionNames.map((name, i) => (
          <div key={i} style={{ display: "flex", gap: 8, alignItems: "center", marginBottom: 4 }}>
            <span style={{ minWidth: 80 }}>{name}</span>
            <select value={perRegion[i]?.surface ?? "skin"}
              onChange={(e) => updatePerRegion(i, "surface", e.target.value)}>
              {SURFACES.map((s) => <option key={s} value={s}>{t(`surfaces.${s}`)}</option>)}
            </select>
            <input type="text" placeholder={t("colour.tone")} value={perRegion[i]?.tone ?? ""}
              style={{ width: 100 }}
              onChange={(e) => updatePerRegion(i, "tone", e.target.value)} />
          </div>
        ))}
      </div>

      <label>
        <input type="checkbox" checked={ownedOnly} onChange={(e) => setOwnedOnly(e.target.checked)} />
        {" "}{t("colour.owned_only")}
      </label>

      <br />
      <button onClick={handleGenerate} disabled={loading} style={{ marginTop: 8 }}>
        {loading ? t("colour.generating") : t("colour.generate")}
      </button>
    </section>
  );
}
```

- [ ] **Step 3: Verify TypeScript compiles**

Run: `cd web && npx tsc --noEmit`
Expected: no errors

- [ ] **Step 4: Commit**

```bash
git add web/src/components/colour/
git commit -m "feat: add ColourPanel shell and SchemeGenerator (L1)"
```

---

### Task 11: RampEditor (L2)

**Files:**
- Create: `web/src/components/colour/RampEditor.tsx`

**Interfaces:**
- Consumes: `generateRamp`, store actions `setHexSlot`, `setRampState`; `activeBookOf`
- Produces: `<RampEditor />`

- [ ] **Step 1: Create `web/src/components/colour/RampEditor.tsx`**

```tsx
import { useState } from "react";
import { useTranslation } from "react-i18next";
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
    } finally {
      setLoading(null);
    }
  };

  return (
    <section>
      <h4 style={{ margin: "0 0 8px" }}>{t("colour.ramp_editor")}</h4>
      <label>
        {t("colour.midtone")}:{" "}
        <input type="color" value={midtoneHex} onChange={(e) => setMidtoneHex(e.target.value)} />
        <input type="text" value={midtoneHex} style={{ width: 80, marginLeft: 4 }}
          onChange={(e) => setMidtoneHex(e.target.value)} />
      </label>

      {book.hero_hex && (
        <>
          {" "}
          <button onClick={() => setMidtoneHex(book.hero_hex!)}
            style={{ marginLeft: 8 }}>
            {t("colour.use_scheme_colour")}
          </button>
        </>
      )}

      <div style={{ display: "flex", gap: 4, marginTop: 8 }}>
        {RAMP_VARIANTS.map((variant) => (
          <button
            key={variant}
            onClick={() => handleVariant(variant)}
            disabled={loading !== null}
          >
            {loading === variant ? "…" : t(`colour.${variant}`)}
          </button>
        ))}
      </div>
    </section>
  );
}
```

- [ ] **Step 2: Commit**

```bash
git add web/src/components/colour/RampEditor.tsx
git commit -m "feat: add RampEditor (L2)"
```

---

### Task 12: BandSlot

**Files:**
- Create: `web/src/components/colour/BandSlot.tsx`
- Create: `web/src/components/colour/BandSlot.test.tsx`

**Interfaces:**
- Consumes: `matchPaint`, `generateRamp`, `setPaletteSlot`, `setHexSlot`, `setBandCount`; `useCatalogStore`
- Props: `g: number, i: number, paint: PaintColor, finish: string, n: number`
- Produces: `<BandSlot />`

The role names for n bands: `["Shadow","Base","Highlight"]` (n=3), `["Shadow","Base","Midtone","Highlight"]` (n=4), etc — computed via the same logic as Python's `role_names()`.

- [ ] **Step 1: Create `web/src/components/colour/BandSlot.tsx`**

```tsx
import { useState, useEffect, useRef } from "react";
import { useTranslation } from "react-i18next";
import { useProjectStore } from "../../store/projectStore";
import { useCatalogStore } from "../../store/catalogStore";
import { matchPaint, generateRamp } from "../../api/client";
import type { PaintColor, MatchResult } from "../../api/types";

interface BandSlotProps {
  g: number;
  i: number;
  paint: PaintColor;
  finish: string;
  n: number;
  palette: PaintColor[];
}

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

  // Debounced match on hex change (custom mode only)
  useEffect(() => {
    if (!isCustom) { setMatchResult(null); return; }
    if (debounceRef.current) clearTimeout(debounceRef.current);
    debounceRef.current = setTimeout(async () => {
      try {
        const res = await matchPaint({ hex: paint.hex, finish, owned_codes: [] });
        setMatchResult(res);
      } catch { /* ignore */ }
    }, 400);
    return () => { if (debounceRef.current) clearTimeout(debounceRef.current); };
  }, [paint.hex, isCustom, finish]);

  const handleCatalogChange = (code: string) => {
    if (code === "__custom__") {
      setHexSlot(g, i, paint.hex);
    } else {
      const found = catalogPaints.find((p) => p.code === code);
      if (found) setPaletteSlot(g, i, found);
    }
  };

  const handleBlend = async () => {
    const left = palette[i - 1];
    const right = palette[i + 1];
    if (!left || !right) return;
    try {
      const res = await generateRamp({
        n: 1, variant: "ramp",
        blend_hexes: [left.hex, right.hex],
      });
      if (res.hexes[0]) setHexSlot(g, i, res.hexes[0]);
    } catch { /* ignore */ }
  };

  return (
    <div style={{ display: "flex", flexDirection: "column", gap: 4, padding: "4px 0", borderBottom: "1px solid #ccc" }}>
      <div style={{ display: "flex", gap: 4, alignItems: "center" }}>
        <div style={{ width: 24, height: 24, background: paint.hex, border: "1px solid #888", flexShrink: 0 }} />

        {isCustom ? (
          <>
            <input type="color" value={paint.hex} onChange={(e) => setHexSlot(g, i, e.target.value)} />
            <input type="text" value={paint.hex} style={{ width: 72 }}
              onChange={(e) => setHexSlot(g, i, e.target.value)} />
          </>
        ) : (
          <select value={paint.code} onChange={(e) => handleCatalogChange(e.target.value)} style={{ flex: 1 }}>
            {catalogPaints.map((p) => (
              <option key={p.code} value={p.code}>{p.code} — {p.name}</option>
            ))}
            <option value="__custom__">{t("colour.custom")}</option>
          </select>
        )}

        {i > 0 && i < n - 1 && (
          <button onClick={handleBlend} title={t("colour.blend")}>↕</button>
        )}
        <button
          onClick={() => { if (n > 3) setBandCount(n - 1); }}
          disabled={n <= 3}
          title={t("colour.delete_band")}
        >
          ✕
        </button>
        <button
          onClick={() => {
            if (n < 7) {
              setBandCount(n + 1);
              setHexSlot(g, n, palette[n - 1]?.hex ?? "#808080");
            }
          }}
          disabled={n >= 7}
          title={t("colour.add_band")}
        >
          ＋
        </button>
      </div>

      {isCustom && matchResult && (
        <div style={{ fontSize: 12, color: "#888", paddingLeft: 28 }}>
          {matchPhrase(matchResult)}
        </div>
      )}
    </div>
  );
}
```

- [ ] **Step 2: Write `web/src/components/colour/BandSlot.test.tsx`**

```tsx
import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, fireEvent, act } from "@testing-library/react";
import { BandSlot } from "./BandSlot";
import { useProjectStore } from "../../store/projectStore";
import { useCatalogStore } from "../../store/catalogStore";
import * as client from "../../api/client";
import type { PaintColor } from "../../api/types";

vi.mock("react-i18next", () => ({ useTranslation: () => ({ t: (k: string) => k }) }));

const catalogPaint: PaintColor = { name: "Red", hex: "#ff0000", code: "R1", finish: "matte" };
const customPaint: PaintColor = { name: "custom", hex: "#aabbcc", code: "", finish: "matte" };

beforeEach(() => {
  useCatalogStore.setState({ paints: [catalogPaint], status: "ready" });
  vi.restoreAllMocks();
});

describe("BandSlot", () => {
  it("shows catalog selectbox when paint has code", () => {
    render(<BandSlot g={0} i={0} paint={catalogPaint} finish="matte" n={3} palette={[catalogPaint, catalogPaint, catalogPaint]} />);
    expect(screen.getByRole("combobox")).toBeTruthy();
  });

  it("shows colour picker when paint has no code (custom mode)", () => {
    render(<BandSlot g={0} i={0} paint={customPaint} finish="matte" n={3} palette={[customPaint, customPaint, customPaint]} />);
    const inputs = screen.getAllByRole("textbox");
    expect(inputs.length).toBeGreaterThan(0);
  });

  it("fires matchPaint debounced when in custom mode", async () => {
    const spy = vi.spyOn(client, "matchPaint").mockResolvedValue({
      tier: "close", phrase: "Closest: Red", name: "Red", hex: "#ff0000", delta_e: 3,
    });
    vi.useFakeTimers();
    render(<BandSlot g={0} i={0} paint={customPaint} finish="matte" n={3} palette={[customPaint, customPaint, customPaint]} />);
    await act(async () => { vi.advanceTimersByTime(500); });
    expect(spy).toHaveBeenCalled();
    vi.useRealTimers();
  });

  it("delete button is disabled when n=3", () => {
    render(<BandSlot g={0} i={0} paint={catalogPaint} finish="matte" n={3} palette={[catalogPaint, catalogPaint, catalogPaint]} />);
    const del = screen.getByTitle("colour.delete_band");
    expect((del as HTMLButtonElement).disabled).toBe(true);
  });
});
```

- [ ] **Step 3: Run tests**

Run: `cd web && npm test -- --reporter=verbose`
Expected: BandSlot tests pass

- [ ] **Step 4: Commit**

```bash
git add web/src/components/colour/BandSlot.tsx web/src/components/colour/BandSlot.test.tsx
git commit -m "feat: add BandSlot with catalog/custom toggle and debounced paint match"
```

---

### Task 13: CoverageEditor, RecipeLoader, RecipeSaver, BandEditor

**Files:**
- Create: `web/src/components/colour/CoverageEditor.tsx`
- Create: `web/src/components/colour/CoverageEditor.test.tsx`
- Create: `web/src/components/colour/RecipeLoader.tsx`
- Create: `web/src/components/colour/RecipeSaver.tsx`
- Create: `web/src/components/colour/BandEditor.tsx`
- Create: `web/src/components/colour/BandEditor.test.tsx`

**Interfaces:**
- Consumes: `listRecipes`, `saveRecipe`, store actions `setCoverage`, `setPaletteAt`, `setBandCount`; `useCatalogStore`
- Produces: `<BandEditor />`

Frontend `role_names(n)` helper (mirrors Python):

```ts
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
```

`default_coverage(n)` (mirrors Python):
```ts
function defaultCoverage(n: number): number[] {
  const weights = Array.from({ length: n }, (_, i) => n - i);
  const total = weights.reduce((a, b) => a + b, 0);
  return weights.map((w) => w / total);
}
```

- [ ] **Step 1: Create `web/src/components/colour/CoverageEditor.tsx`**

```tsx
import { useTranslation } from "react-i18next";
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

export function CoverageEditor({ g, n, coverage }: Props) {
  const { t } = useTranslation();
  const setCoverage = useProjectStore((s) => s.setCoverage);
  const names = roleNames(n);

  const handleSlider = (i: number, raw: string) => {
    const val = Number(raw) / 100;
    const others = coverage.reduce((sum, v, j) => (j !== i && j !== n - 1 ? sum + v : sum), 0);
    const max = Math.max(0, 1 - others - 0.03);
    const clamped = Math.min(val, max);
    const newCov = coverage.slice();
    newCov[i] = clamped;
    const remainder = 1 - newCov.slice(0, n - 1).reduce((a, b) => a + b, 0);
    newCov[n - 1] = Math.max(0, remainder);
    setCoverage(newCov);
  };

  return (
    <div>
      {Array.from({ length: n - 1 }, (_, i) => (
        <div key={i} style={{ display: "flex", alignItems: "center", gap: 8 }}>
          <span style={{ minWidth: 120, fontSize: 12 }}>{names[i]}</span>
          <input
            type="range" min={0} max={100}
            value={Math.round((coverage[i] ?? 0) * 100)}
            onChange={(e) => handleSlider(i, e.target.value)}
            onMouseUp={() => { /* setCoverage is called on every change; mouseUp is a no-op */ }}
          />
          <span style={{ fontSize: 12, minWidth: 32 }}>
            {Math.round((coverage[i] ?? 0) * 100)}%
          </span>
        </div>
      ))}
      <div style={{ fontSize: 12, color: "#888" }}>
        {names[n - 1]}: {Math.round((coverage[n - 1] ?? 0) * 100)}% (auto)
      </div>
      <button onClick={() => setCoverage(defaultCoverage(n))} style={{ marginTop: 4 }}>
        {t("colour.reset_coverage")}
      </button>
    </div>
  );
}
```

- [ ] **Step 2: Write `web/src/components/colour/CoverageEditor.test.tsx`**

```tsx
import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, fireEvent } from "@testing-library/react";
import { CoverageEditor } from "./CoverageEditor";
import { useProjectStore } from "../../store/projectStore";
import type { PhotoResponse } from "../../api/types";

vi.mock("react-i18next", () => ({ useTranslation: () => ({ t: (k: string) => k }) }));

const photo = (): PhotoResponse => ({
  photo_id: "p1", width: 10, height: 10, quality_checks: [],
  default_whole: { palette: [{ name: "a", hex: "#111" }, { name: "b", hex: "#aaa" }, { name: "c", hex: "#eee" }],
                   coverage: [0.5, 0.3, 0.2], material: "matte" },
});
const reset = () => useProjectStore.setState(useProjectStore.getInitialState(), true);

describe("CoverageEditor", () => {
  beforeEach(() => {
    reset();
    useProjectStore.getState().initFromPhoto(photo());
  });

  it("renders n-1 sliders for n bands", () => {
    render(<CoverageEditor g={0} n={3} coverage={[0.5, 0.3, 0.2]} />);
    const sliders = screen.getAllByRole("slider");
    expect(sliders).toHaveLength(2);
  });

  it("Reset button dispatches default coverage", () => {
    const spy = vi.spyOn(useProjectStore.getState(), "setCoverage");
    render(<CoverageEditor g={0} n={3} coverage={[0.5, 0.3, 0.2]} />);
    fireEvent.click(screen.getByText("colour.reset_coverage"));
    expect(spy).toHaveBeenCalled();
  });
});
```

- [ ] **Step 3: Create `web/src/components/colour/RecipeLoader.tsx`**

```tsx
import { useState, useEffect } from "react";
import { useTranslation } from "react-i18next";
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
    listRecipes().then((res) => {
      setRecipes(res.recipes);
      if (res.recipes.length > 0) setSelected(res.recipes[0].name);
    });
  }, []);

  if (!book) return null;

  const handleLoad = () => {
    const recipe = recipes.find((r) => r.name === selected);
    if (!recipe) return;
    const palette = toPalette(recipe, catalogPaints);
    setPaletteAt(book.selected, palette);
    onRecipeLoaded();
  };

  return (
    <div style={{ display: "flex", gap: 4, alignItems: "center" }}>
      <select value={selected} onChange={(e) => setSelected(e.target.value)}
        style={{ flex: 1 }}>
        {recipes.length === 0 && <option value="">{t("colour.select_recipe")}</option>}
        {recipes.map((r) => <option key={r.name} value={r.name}>{r.name}</option>)}
      </select>
      <button onClick={handleLoad} disabled={!selected}>{t("colour.load_recipe")}</button>
    </div>
  );
}
```

- [ ] **Step 4: Create `web/src/components/colour/RecipeSaver.tsx`**

```tsx
import { useState } from "react";
import { useTranslation } from "react-i18next";
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
    setToast(true);
    setName("");
    onSaved();
    setTimeout(() => setToast(false), 2000);
  };

  return (
    <div style={{ display: "flex", gap: 4, alignItems: "center", marginTop: 8 }}>
      <input type="text" value={name} placeholder={t("colour.recipe_name")}
        onChange={(e) => setName(e.target.value)} style={{ flex: 1 }} />
      <button onClick={handleSave} disabled={!name.trim()}>{t("colour.save_recipe")}</button>
      {toast && <span style={{ color: "green", fontSize: 12 }}>{t("colour.recipe_saved")}</span>}
    </div>
  );
}
```

- [ ] **Step 5: Create `web/src/components/colour/BandEditor.tsx`**

```tsx
import { useState } from "react";
import { useTranslation } from "react-i18next";
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
    <section>
      <h4 style={{ margin: "0 0 8px" }}>{t("colour.band_editor")}</h4>
      <RecipeLoader key={recipeKey} onRecipeLoaded={() => setRecipeKey((k) => k + 1)} />

      {palette.map((paint, i) => (
        <BandSlot key={i} g={g} i={i} paint={paint} finish={material} n={n} palette={palette} />
      ))}

      <CoverageEditor g={g} n={n} coverage={coverage} />
      <RecipeSaver onSaved={() => setRecipeKey((k) => k + 1)} />
    </section>
  );
}
```

- [ ] **Step 6: Write `web/src/components/colour/BandEditor.test.tsx`**

```tsx
import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen } from "@testing-library/react";
import { BandEditor } from "./BandEditor";
import { useProjectStore } from "../../store/projectStore";
import { useCatalogStore } from "../../store/catalogStore";
import * as client from "../../api/client";
import type { PhotoResponse } from "../../api/types";

vi.mock("react-i18next", () => ({ useTranslation: () => ({ t: (k: string) => k }) }));
vi.mock("./BandSlot", () => ({ BandSlot: ({ i }: { i: number }) => <div>slot-{i}</div> }));
vi.mock("./CoverageEditor", () => ({ CoverageEditor: () => <div>coverage</div> }));

const photo = (): PhotoResponse => ({
  photo_id: "p1", width: 10, height: 10, quality_checks: [],
  default_whole: {
    palette: [{ name: "a", hex: "#111" }, { name: "b", hex: "#aaa" }],
    coverage: [0.6, 0.4], material: "matte",
  },
});
const reset = () => useProjectStore.setState(useProjectStore.getInitialState(), true);

describe("BandEditor", () => {
  beforeEach(() => {
    reset();
    useProjectStore.getState().initFromPhoto(photo());
    useCatalogStore.setState({ paints: [], status: "ready" });
    vi.spyOn(client, "listRecipes").mockResolvedValue({ recipes: [] });
  });

  it("renders one BandSlot per palette entry", () => {
    render(<BandEditor />);
    expect(screen.getByText("slot-0")).toBeTruthy();
    expect(screen.getByText("slot-1")).toBeTruthy();
  });
});
```

- [ ] **Step 7: Run tests**

Run: `cd web && npm test -- --reporter=verbose`
Expected: CoverageEditor + BandEditor tests pass

- [ ] **Step 8: Commit**

```bash
git add web/src/components/colour/CoverageEditor.tsx web/src/components/colour/CoverageEditor.test.tsx \
        web/src/components/colour/RecipeLoader.tsx web/src/components/colour/RecipeSaver.tsx \
        web/src/components/colour/BandEditor.tsx web/src/components/colour/BandEditor.test.tsx
git commit -m "feat: add CoverageEditor, RecipeLoader, RecipeSaver, BandEditor"
```

---

### Task 14: SchemeManager + RecipeManager

**Files:**
- Create: `web/src/components/colour/SchemeManager.tsx`
- Create: `web/src/components/colour/SchemeManager.test.tsx`
- Create: `web/src/components/colour/RecipeManager.tsx`

**Interfaces:**
- Consumes: `exportRecipes`, `importRecipes`, `exportCollection`, `importCollection`; store actions `saveScheme`, `applyScheme`, `deleteScheme`
- Produces: `<SchemeManager />`, `<RecipeManager />`

- [ ] **Step 1: Create `web/src/components/colour/SchemeManager.tsx`**

```tsx
import { useState } from "react";
import { useTranslation } from "react-i18next";
import { useProjectStore, activeBookOf } from "../../store/projectStore";

export function SchemeManager() {
  const { t } = useTranslation();
  const schemes = useProjectStore((s) => activeBookOf(s)?.schemes ?? []);
  const saveScheme = useProjectStore((s) => s.saveScheme);
  const applyScheme = useProjectStore((s) => s.applyScheme);
  const deleteScheme = useProjectStore((s) => s.deleteScheme);
  const [name, setName] = useState("");

  return (
    <section>
      <h4 style={{ margin: "0 0 8px" }}>{t("schemes.title")}</h4>
      <div style={{ display: "flex", gap: 4 }}>
        <input type="text" value={name} placeholder={t("schemes.name_placeholder")}
          onChange={(e) => setName(e.target.value)} style={{ flex: 1 }} />
        <button onClick={() => { if (name.trim()) { saveScheme(name.trim()); setName(""); } }}
          disabled={!name.trim()}>
          {t("schemes.save")}
        </button>
      </div>
      <ul style={{ listStyle: "none", padding: 0, margin: "8px 0 0" }}>
        {schemes.map((sc) => (
          <li key={sc.id} style={{ display: "flex", gap: 4, alignItems: "center", marginBottom: 4 }}>
            <span style={{ flex: 1 }}>{sc.name}</span>
            <button onClick={() => applyScheme(sc.id)}>{t("schemes.apply")}</button>
            <button onClick={() => deleteScheme(sc.id)}>{t("schemes.delete")}</button>
          </li>
        ))}
      </ul>
    </section>
  );
}
```

- [ ] **Step 2: Write `web/src/components/colour/SchemeManager.test.tsx`**

```tsx
import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, fireEvent } from "@testing-library/react";
import { SchemeManager } from "./SchemeManager";
import { useProjectStore } from "../../store/projectStore";
import type { PhotoResponse } from "../../api/types";

vi.mock("react-i18next", () => ({ useTranslation: () => ({ t: (k: string) => k }) }));

const photo = (): PhotoResponse => ({
  photo_id: "p1", width: 10, height: 10, quality_checks: [],
  default_whole: { palette: [{ name: "a", hex: "#111" }], coverage: [1], material: "matte" },
});
const reset = () => useProjectStore.setState(useProjectStore.getInitialState(), true);

describe("SchemeManager", () => {
  beforeEach(() => { reset(); useProjectStore.getState().initFromPhoto(photo()); });

  it("saves a scheme when name entered and Save clicked", () => {
    render(<SchemeManager />);
    fireEvent.change(screen.getByRole("textbox"), { target: { value: "My Scheme" } });
    fireEvent.click(screen.getByText("schemes.save"));
    expect(screen.getByText("My Scheme")).toBeTruthy();
  });

  it("deletes a scheme", () => {
    useProjectStore.getState().saveScheme("ToDelete");
    render(<SchemeManager />);
    fireEvent.click(screen.getByText("schemes.delete"));
    expect(screen.queryByText("ToDelete")).toBeNull();
  });

  it("applies a scheme by clicking Apply", () => {
    useProjectStore.getState().saveScheme("snap");
    const spy = vi.spyOn(useProjectStore.getState(), "applyScheme");
    render(<SchemeManager />);
    fireEvent.click(screen.getByText("schemes.apply"));
    expect(spy).toHaveBeenCalled();
  });
});
```

- [ ] **Step 3: Create `web/src/components/colour/RecipeManager.tsx`**

```tsx
import { useRef } from "react";
import { useTranslation } from "react-i18next";
import { exportRecipes, importRecipes, exportCollection, importCollection } from "../../api/client";

function triggerDownload(blob: Blob, filename: string) {
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url; a.download = filename; a.click();
  URL.revokeObjectURL(url);
}

export function RecipeManager() {
  const { t } = useTranslation();
  const recipeImportRef = useRef<HTMLInputElement>(null);
  const collectionImportRef = useRef<HTMLInputElement>(null);

  const handleExportRecipes = async () => {
    const blob = await exportRecipes();
    triggerDownload(blob, "recipes.json");
  };

  const handleImportRecipes = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (!file) return;
    await importRecipes(file);
    e.target.value = "";
  };

  const handleExportCollection = async () => {
    const blob = await exportCollection();
    triggerDownload(blob, "collection.json");
  };

  const handleImportCollection = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (!file) return;
    await importCollection(file);
    e.target.value = "";
  };

  return (
    <section>
      <div style={{ display: "flex", gap: 4, flexWrap: "wrap" }}>
        <button onClick={handleExportRecipes}>{t("recipes.export")}</button>
        <button onClick={() => recipeImportRef.current?.click()}>{t("recipes.import")}</button>
        <input ref={recipeImportRef} type="file" accept=".json" style={{ display: "none" }}
          onChange={handleImportRecipes} />
        <button onClick={handleExportCollection}>{t("colour.owned_only")} export</button>
        <button onClick={() => collectionImportRef.current?.click()}>collection import</button>
        <input ref={collectionImportRef} type="file" accept=".json" style={{ display: "none" }}
          onChange={handleImportCollection} />
      </div>
    </section>
  );
}
```

- [ ] **Step 4: Add `<RecipeManager />` to `ColourPanel`**

Update `web/src/components/colour/ColourPanel.tsx` to import and render `RecipeManager` after `SchemeManager`:

```tsx
import { SchemeGenerator } from "./SchemeGenerator";
import { RampEditor } from "./RampEditor";
import { BandEditor } from "./BandEditor";
import { SchemeManager } from "./SchemeManager";
import { RecipeManager } from "./RecipeManager";

export function ColourPanel() {
  return (
    <div style={{ display: "flex", flexDirection: "column", gap: 16 }}>
      <SchemeGenerator />
      <RampEditor />
      <BandEditor />
      <SchemeManager />
      <RecipeManager />
    </div>
  );
}
```

- [ ] **Step 5: Run tests**

Run: `cd web && npm test -- --reporter=verbose`
Expected: SchemeManager tests pass; all prior tests still green

- [ ] **Step 6: Commit**

```bash
git add web/src/components/colour/SchemeManager.tsx web/src/components/colour/SchemeManager.test.tsx \
        web/src/components/colour/RecipeManager.tsx web/src/components/colour/ColourPanel.tsx
git commit -m "feat: add SchemeManager, RecipeManager, complete ColourPanel"
```

---

### Task 15: App.tsx wiring

**Files:**
- Modify: `web/src/App.tsx` — trigger catalog fetch on first photo, swap `BandControl` → `RightPanel`

**Interfaces:**
- Consumes: `useCatalogStore`, `RightPanel`; removes `BandControl` from render

- [ ] **Step 1: Update `web/src/App.tsx`**

Replace the entire file with:

```tsx
import { useEffect } from "react";
import { PhotoUploader } from "./components/PhotoUploader";
import { PreviewImage } from "./components/PreviewImage";
import { RegionSelector } from "./components/RegionSelector";
import { AngleBar } from "./components/AngleBar";
import { RightPanel } from "./components/RightPanel";
import { useAnalyze } from "./hooks/useAnalyze";
import { useProjectStore } from "./store/projectStore";
import { useCatalogStore } from "./store/catalogStore";

export default function App() {
  useAnalyze();
  const hasAngle = useProjectStore((s) => s.angles.length > 0);
  const fetchCatalog = useCatalogStore((s) => s.fetch);

  useEffect(() => {
    if (hasAngle) fetchCatalog();
  }, [hasAngle, fetchCatalog]);

  return (
    <main style={{ maxWidth: 1100, margin: "0 auto", padding: 16 }}>
      <h1>Mini Highlight Advisor</h1>
      {!hasAngle ? (
        <PhotoUploader />
      ) : (
        <>
          <AngleBar />
          <div style={{ display: "flex", gap: 24, alignItems: "flex-start" }}>
            <div style={{ flex: "0 0 auto" }}>
              <PreviewImage />
            </div>
            <div style={{ flex: 1 }}>
              <RegionSelector />
              <RightPanel />
            </div>
          </div>
        </>
      )}
    </main>
  );
}
```

- [ ] **Step 2: Run full test suite**

Run: `cd web && npm test -- --reporter=verbose`
Expected: all tests pass

- [ ] **Step 3: Run TypeScript check**

Run: `cd web && npx tsc --noEmit`
Expected: no errors

- [ ] **Step 4: Commit**

```bash
git add web/src/App.tsx
git commit -m "feat: wire App.tsx — catalog fetch on photo load, RightPanel replaces BandControl"
```

---

## Self-Review

**Spec coverage check:**

| Spec section | Covered by |
|---|---|
| §3.1 WholeState, DrawnRegion, Scheme, Book types | Task 5 |
| §3.2 All 13 new store actions | Task 5 |
| §3.3 catalogStore | Task 6 |
| §4.1 7 implemented endpoints | Task 2 |
| §4.2 5 new endpoints (ramp, export/import) | Task 3 |
| §4.3 Backend schemas | Task 1 |
| §5.1 New API types + constants | Task 7 |
| §5.2 12 client functions | Task 7 |
| §6.1 App.tsx layout + catalog fetch | Task 15 |
| §6.2 TechniquePanel | Task 9 |
| §6.3 ColourPanel orchestrator | Task 10 |
| §6.4 SchemeGenerator (L1) | Task 10 |
| §6.5 RampEditor (L2) | Task 11 |
| §6.6 BandEditor (L3) | Task 13 |
| §6.7 RecipeLoader | Task 13 |
| §6.8 BandSlot (catalog/custom/match/blend) | Task 12 |
| §6.9 CoverageEditor | Task 13 |
| §6.10 RecipeSaver | Task 13 |
| §6.11 SchemeManager | Task 14 |
| §6.12 RecipeManager | Task 14 |
| §8 i18n setup | Task 8 |
| §9 Backend tests | Task 4 |
| §9 Frontend tests | Tasks 5, 6, 9, 12, 13, 14 |

**Placeholder scan:** None — all steps contain actual code.

**Type consistency check:**
- `setPaletteAt(g, palette)` — defined in Task 5 State interface, implemented in Task 5 store body, consumed in SchemeGenerator (Task 10), RecipeLoader (Task 13) ✓
- `setHexSlot(g, i, hex)` — defined Task 5, consumed RampEditor (Task 11), BandSlot (Task 12) ✓
- `saveScheme(name)`, `applyScheme(id)`, `deleteScheme(id)` — defined Task 5, consumed SchemeManager (Task 14) ✓
- `fetchCatalog()` in `client.ts` — defined Task 7, consumed `catalogStore.ts` (Task 6) ✓
- `generateRamp(req)` — defined Task 7, consumed RampEditor (Task 11), BandSlot (Task 12) ✓
- `useCatalogStore` — defined Task 6, consumed SchemeGenerator (Task 10), BandSlot (Task 12), RecipeLoader (Task 13), App.tsx (Task 15) ✓
- `Book.schemes` — added to type in Task 5, initialised in `makeAngle` (Task 5) ✓
- `CoverageEditor` props `(g, n, coverage)` — declared in Task 13, passed correctly from BandEditor (Task 13) ✓

**Gap found:** The `Scheme` type import in `projectStore.test.ts` (Task 5 applyScheme stale-id test) references `import("./projectStore").Scheme` — this is a dynamic import for type-only use and is valid in TypeScript tests. No fix needed.

**Gap found:** `BandControl.tsx` is imported in the existing codebase. After Task 15 removes it from `App.tsx`, the file itself still exists but is unreferenced. Leave it in place — removing unused files is out of scope for this slice.

---

Plan complete and saved to `docs/superpowers/plans/2026-09-22-react-colour-panel.md`.

**Two execution options:**

**1. Subagent-Driven (recommended)** — fresh subagent per task, review between tasks, fast iteration

**2. Inline Execution** — execute tasks in this session using executing-plans, batch execution with checkpoints

**Which approach?**
