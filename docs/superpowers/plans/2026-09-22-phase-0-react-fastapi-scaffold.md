# Phase 0 — React + FastAPI Scaffold & Vertical Slice — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Stand up a FastAPI backend over the existing `src/` core and a Vite+React+TS SPA, and prove the whole pipe end to end: upload a photo (or pick a bundled sample) → see the live painted preview, with a minimal band-count control that re-renders through the server.

**Architecture:** Two localhost processes. FastAPI (`backend/`) is a thin adapter that imports `mini_highlight_advisor` directly and calls existing functions (`load_image`, `prepare_shading`, `analyze_regions`, `samples`), returning PNGs as base64 data URIs. React (`web/`) holds state in Zustand, calls the backend via a typed fetch client, and re-analyzes (debounced) whenever the whole-mini palette/coverage/settings change. Regions, steps, colour panel, angles, schemes, paints, i18n are **later phases** — Phase 0 is whole-mini only.

**Tech Stack:** FastAPI, uvicorn, python-multipart, pydantic **v2**, Pillow/NumPy (already present); Vite, React 18, TypeScript, Zustand, Vitest + @testing-library/react.

**Spec:** `docs/superpowers/specs/2026-09-22-react-fastapi-migration-design.md`

## Global Constraints

- **Python core in `src/` is NOT modified.** The backend only imports and adapts it.
- **Streamlit stays runnable.** Do not touch `app.py` or `ui/`. Backend Python deps are added to a **separate** `backend/requirements.txt`, not the root `requirements.txt` (which pins `streamlit==1.61.*`).
- **pydantic is v2** (repo runs 2.13.x). Use `model_dump_json()` / `model_dump()`, not `.json()` / `.dict()`.
- **Feature branch + PR; never commit to `main`.** All Phase 0 work lands on `feat/react-fastapi-migration` (already checked out).
- **All images cross the wire as** `data:image/png;base64,...` strings.
- **Backend runs on :8000, Vite dev server on :5173**, Vite proxies `/api` → `http://localhost:8000`.
- **Phase 0 UI strings may be hardcoded English.** The react-i18next port is a later phase.
- **Node ≥ 18** (Vite 5 requirement).

---

## File Structure

**Backend (new, `backend/`):**
- `backend/__init__.py` — marks package.
- `backend/requirements.txt` — `fastapi`, `uvicorn[standard]`, `python-multipart`, `httpx` (for TestClient).
- `backend/serialize.py` — numpy/PIL → PNG bytes / data URI.
- `backend/cache.py` — small in-process LRU.
- `backend/schemas.py` — pydantic v2 request/response models.
- `backend/core_adapters.py` — PaintColor ↔ dict/model, default-whole seed, image decode.
- `backend/main.py` — FastAPI app + routes (`/api/health`, `/api/photo`, `/api/analyze`, `/api/samples/photos`, `/api/samples/photos/{sid}`).
- `backend/tests/test_health.py`, `test_serialize.py`, `test_cache.py`, `test_photo.py`, `test_analyze.py`, `test_samples.py`.

**Frontend (new, `web/`):**
- `web/package.json`, `web/tsconfig.json`, `web/vite.config.ts`, `web/index.html`.
- `web/src/main.tsx`, `web/src/App.tsx`.
- `web/src/api/client.ts` — typed fetch wrapper.
- `web/src/api/types.ts` — shared TS types (mirror the pydantic models).
- `web/src/store/projectStore.ts` — Zustand store (photo, whole, settings, preview).
- `web/src/hooks/useAnalyze.ts` — debounced re-analyze effect.
- `web/src/components/PhotoUploader.tsx`, `PreviewImage.tsx`, `BandControl.tsx`.
- `web/src/test/setup.ts`; `web/src/**/*.test.ts(x)` colocated tests.

**Docs:**
- `web/README.md` / `backend/README.md` run instructions; a note appended to root `CLAUDE.md`.

---

## Task 1: Backend package + health endpoint

**Files:**
- Create: `backend/__init__.py`, `backend/requirements.txt`, `backend/main.py`
- Test: `backend/tests/__init__.py`, `backend/tests/test_health.py`

**Interfaces:**
- Produces: FastAPI `app` in `backend/main.py`; `GET /api/health → {"status":"ok"}`.

- [ ] **Step 1: Write the failing test**

```python
# backend/tests/test_health.py
from fastapi.testclient import TestClient
from backend.main import app

client = TestClient(app)

def test_health_ok():
    r = client.get("/api/health")
    assert r.status_code == 200
    assert r.json() == {"status": "ok"}
```

- [ ] **Step 2: Create deps file and empty package markers**

```
# backend/requirements.txt
fastapi
uvicorn[standard]
python-multipart
httpx
```

Create empty `backend/__init__.py` and `backend/tests/__init__.py`. Install into the existing venv:
Run: `.venv/Scripts/python -m pip install -r backend/requirements.txt`

- [ ] **Step 3: Run test to verify it fails**

Run: `.venv/Scripts/python -m pytest backend/tests/test_health.py -v`
Expected: FAIL — `ModuleNotFoundError: backend.main` (app not defined yet).

- [ ] **Step 4: Write minimal implementation**

```python
# backend/main.py
from fastapi import FastAPI

app = FastAPI(title="Mini Highlight Advisor API")

@app.get("/api/health")
def health():
    return {"status": "ok"}
```

- [ ] **Step 5: Run test to verify it passes**

Run: `.venv/Scripts/python -m pytest backend/tests/test_health.py -v`
Expected: PASS.

- [ ] **Step 6: Commit**

```bash
git add backend/
git commit -m "feat(backend): FastAPI app skeleton with health endpoint"
```

---

## Task 2: PNG serialization helper

**Files:**
- Create: `backend/serialize.py`
- Test: `backend/tests/test_serialize.py`

**Interfaces:**
- Produces: `to_png_bytes(arr) -> bytes` and `png_data_uri(arr) -> str`, where `arr` is an `np.ndarray` (H,W,3) uint8 **or** a `PIL.Image.Image`. `png_data_uri` returns a string starting `"data:image/png;base64,"`.

- [ ] **Step 1: Write the failing test**

```python
# backend/tests/test_serialize.py
import base64
import numpy as np
from PIL import Image
from backend.serialize import to_png_bytes, png_data_uri

def test_png_data_uri_from_ndarray():
    arr = np.zeros((4, 4, 3), dtype=np.uint8)
    uri = png_data_uri(arr)
    assert uri.startswith("data:image/png;base64,")
    raw = base64.b64decode(uri.split(",", 1)[1])
    assert Image.open(__import__("io").BytesIO(raw)).size == (4, 4)

def test_to_png_bytes_from_pil():
    img = Image.new("RGB", (2, 3))
    assert to_png_bytes(img)[:8] == b"\x89PNG\r\n\x1a\n"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.venv/Scripts/python -m pytest backend/tests/test_serialize.py -v`
Expected: FAIL — `ModuleNotFoundError: backend.serialize`.

- [ ] **Step 3: Write minimal implementation**

```python
# backend/serialize.py
import base64
import io

import numpy as np
from PIL import Image


def to_png_bytes(arr) -> bytes:
    img = Image.fromarray(np.asarray(arr).astype("uint8")) if isinstance(arr, np.ndarray) else arr
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return buf.getvalue()


def png_data_uri(arr) -> str:
    return "data:image/png;base64," + base64.b64encode(to_png_bytes(arr)).decode("ascii")
```

- [ ] **Step 4: Run test to verify it passes**

Run: `.venv/Scripts/python -m pytest backend/tests/test_serialize.py -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add backend/serialize.py backend/tests/test_serialize.py
git commit -m "feat(backend): PNG data-URI serialization helper"
```

---

## Task 3: In-process LRU cache

**Files:**
- Create: `backend/cache.py`
- Test: `backend/tests/test_cache.py`

**Interfaces:**
- Produces: `class LRU` with `__init__(self, maxsize: int = 8)`, `get(key) -> value | None`, `set(key, value) -> None`. Evicts least-recently-used past `maxsize`.

- [ ] **Step 1: Write the failing test**

```python
# backend/tests/test_cache.py
from backend.cache import LRU

def test_get_miss_returns_none():
    assert LRU().get("nope") is None

def test_set_get_roundtrip():
    c = LRU(); c.set("a", 1)
    assert c.get("a") == 1

def test_evicts_least_recently_used():
    c = LRU(maxsize=2)
    c.set("a", 1); c.set("b", 2)
    c.get("a")            # 'a' now most-recent; 'b' is LRU
    c.set("c", 3)         # evicts 'b'
    assert c.get("b") is None
    assert c.get("a") == 1 and c.get("c") == 3
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.venv/Scripts/python -m pytest backend/tests/test_cache.py -v`
Expected: FAIL — `ModuleNotFoundError: backend.cache`.

- [ ] **Step 3: Write minimal implementation**

```python
# backend/cache.py
from collections import OrderedDict


class LRU:
    def __init__(self, maxsize: int = 8):
        self._d: OrderedDict = OrderedDict()
        self.maxsize = maxsize

    def get(self, key):
        if key in self._d:
            self._d.move_to_end(key)
            return self._d[key]
        return None

    def set(self, key, value) -> None:
        self._d[key] = value
        self._d.move_to_end(key)
        while len(self._d) > self.maxsize:
            self._d.popitem(last=False)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `.venv/Scripts/python -m pytest backend/tests/test_cache.py -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add backend/cache.py backend/tests/test_cache.py
git commit -m "feat(backend): bounded in-process LRU cache"
```

---

## Task 4: Schemas + core adapters

**Files:**
- Create: `backend/schemas.py`, `backend/core_adapters.py`
- Test: `backend/tests/test_adapters.py`

**Interfaces:**
- Produces (schemas.py, pydantic v2 `BaseModel`s):
  - `PaintColorModel(name:str, hex:str, brand:str|None=None, paint_range:str|None=None, code:str="", finish:str="matte")`
  - `WholeModel(palette:list[PaintColorModel], coverage:list[float], material:str="matte")`
  - `SettingsModel(edge_hl:bool=True, edge_extreme:bool=False, edge_sens:float=0.5, relief_cap:bool=True, per_region_norm:bool=False)`
  - `AnalyzeRequest(photo_id:str, whole:WholeModel, settings:SettingsModel=SettingsModel())`
- Produces (core_adapters.py):
  - `paint_from_model(m: PaintColorModel) -> PaintColor`
  - `paint_to_dict(p: PaintColor) -> dict` (keys: name,hex,brand,paint_range,code,finish)
  - `default_whole() -> dict` → `{"palette":[...dicts], "coverage":[float], "material":"matte"}` from `DEFAULT_PALETTE` + `default_coverage`
  - `decode_image(data: bytes, filename: str) -> tuple[np.ndarray, np.ndarray|None]` via a temp file + `load_image`

- [ ] **Step 1: Write the failing test**

```python
# backend/tests/test_adapters.py
from backend.schemas import PaintColorModel, WholeModel, AnalyzeRequest
from backend.core_adapters import paint_from_model, paint_to_dict, default_whole
from mini_highlight_advisor.palette import PaintColor

def test_paint_roundtrip():
    m = PaintColorModel(name="Test", hex="#804020", code="ABC")
    p = paint_from_model(m)
    assert isinstance(p, PaintColor) and p.hex == "#804020"
    d = paint_to_dict(p)
    assert d["name"] == "Test" and d["code"] == "ABC" and d["finish"] == "matte"

def test_default_whole_shape():
    dw = default_whole()
    assert dw["material"] == "matte"
    assert len(dw["palette"]) == len(dw["coverage"]) >= 1
    assert dw["palette"][0].keys() >= {"name", "hex", "code", "finish"}

def test_analyze_request_defaults():
    req = AnalyzeRequest(photo_id="x",
                         whole=WholeModel(palette=[PaintColorModel(name="a", hex="#000000")],
                                          coverage=[1.0]))
    assert req.settings.relief_cap is True
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.venv/Scripts/python -m pytest backend/tests/test_adapters.py -v`
Expected: FAIL — modules not found.

- [ ] **Step 3: Write minimal implementation**

```python
# backend/schemas.py
from pydantic import BaseModel, Field


class PaintColorModel(BaseModel):
    name: str
    hex: str
    brand: str | None = None
    paint_range: str | None = None
    code: str = ""
    finish: str = "matte"


class WholeModel(BaseModel):
    palette: list[PaintColorModel]
    coverage: list[float]
    material: str = "matte"


class SettingsModel(BaseModel):
    edge_hl: bool = True
    edge_extreme: bool = False
    edge_sens: float = 0.5
    relief_cap: bool = True
    per_region_norm: bool = False


class AnalyzeRequest(BaseModel):
    photo_id: str
    whole: WholeModel
    settings: SettingsModel = Field(default_factory=SettingsModel)
```

```python
# backend/core_adapters.py
import os
import tempfile

import numpy as np

from mini_highlight_advisor.masking import load_image
from mini_highlight_advisor.palette import PaintColor, DEFAULT_PALETTE, default_coverage
from backend.schemas import PaintColorModel


def paint_from_model(m: PaintColorModel) -> PaintColor:
    return PaintColor(name=m.name, hex=m.hex, brand=m.brand,
                      paint_range=m.paint_range, code=m.code, finish=m.finish)


def paint_to_dict(p: PaintColor) -> dict:
    return {"name": p.name, "hex": p.hex, "brand": p.brand,
            "paint_range": p.paint_range, "code": p.code, "finish": p.finish}


def default_whole() -> dict:
    pal = list(DEFAULT_PALETTE)
    return {"palette": [paint_to_dict(p) for p in pal],
            "coverage": list(default_coverage(len(pal))),
            "material": "matte"}


def decode_image(data: bytes, filename: str) -> tuple[np.ndarray, np.ndarray | None]:
    suffix = os.path.splitext(filename)[1] or ".png"
    with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as tmp:
        tmp.write(data)
        path = tmp.name
    try:
        return load_image(path)
    finally:
        os.unlink(path)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `.venv/Scripts/python -m pytest backend/tests/test_adapters.py -v`
Expected: PASS.

> If `DEFAULT_PALETTE` or `default_coverage` import fails, open `src/mini_highlight_advisor/palette.py` and correct the imported names — do not change `palette.py`.

- [ ] **Step 5: Commit**

```bash
git add backend/schemas.py backend/core_adapters.py backend/tests/test_adapters.py
git commit -m "feat(backend): pydantic schemas and core adapters"
```

---

## Task 5: `POST /api/photo`

**Files:**
- Modify: `backend/main.py`
- Test: `backend/tests/test_photo.py`

**Interfaces:**
- Consumes: `decode_image`, `default_whole` (Task 4); `prepare_shading`, `check_input` (core); `LRU` (Task 3).
- Produces: module-level `shading_cache = LRU(maxsize=8)` in `main.py`; `POST /api/photo` (multipart field `file`) → `{photo_id:str, width:int, height:int, quality_checks:[{label,ok,detail}], default_whole:{...}}`. `photo_id = sha256(bytes)[:16]`. Caches `photo_id → (rgb, alpha, ShadingResult)`.

- [ ] **Step 1: Write the failing test**

```python
# backend/tests/test_photo.py
import io
import numpy as np
from PIL import Image
from fastapi.testclient import TestClient
from backend.main import app

client = TestClient(app)

def _png_bytes():
    arr = (np.random.default_rng(0).integers(0, 255, (32, 24, 3))).astype("uint8")
    buf = io.BytesIO(); Image.fromarray(arr).save(buf, format="PNG"); return buf.getvalue()

def test_upload_returns_id_dims_and_defaults():
    r = client.post("/api/photo", files={"file": ("m.png", _png_bytes(), "image/png")})
    assert r.status_code == 200
    body = r.json()
    assert len(body["photo_id"]) == 16
    assert body["width"] == 24 and body["height"] == 32
    assert isinstance(body["quality_checks"], list)
    assert body["default_whole"]["material"] == "matte"

def test_same_bytes_same_id():
    data = _png_bytes()
    a = client.post("/api/photo", files={"file": ("m.png", data, "image/png")}).json()
    b = client.post("/api/photo", files={"file": ("m.png", data, "image/png")}).json()
    assert a["photo_id"] == b["photo_id"]
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.venv/Scripts/python -m pytest backend/tests/test_photo.py -v`
Expected: FAIL — 404/route missing.

- [ ] **Step 3: Write minimal implementation** (add to `backend/main.py`)

```python
import hashlib

from fastapi import File, UploadFile

from mini_highlight_advisor.pipeline import prepare_shading
from mini_highlight_advisor.input_check import check_input
from backend.cache import LRU
from backend.core_adapters import decode_image, default_whole

shading_cache = LRU(maxsize=8)


@app.post("/api/photo")
async def upload_photo(file: UploadFile = File(...)):
    data = await file.read()
    photo_id = hashlib.sha256(data).hexdigest()[:16]
    cached = shading_cache.get(photo_id)
    if cached is None:
        rgb, alpha = decode_image(data, file.filename or "upload.png")
        shading = prepare_shading(rgb, alpha)
        shading_cache.set(photo_id, (rgb, alpha, shading))
    else:
        rgb, alpha, shading = cached
    checks = [{"label": c.label, "ok": c.ok, "detail": c.detail}
              for c in check_input(rgb, shading.mask)]
    h, w = rgb.shape[:2]
    return {"photo_id": photo_id, "width": w, "height": h,
            "quality_checks": checks, "default_whole": default_whole()}
```

- [ ] **Step 4: Run test to verify it passes**

Run: `.venv/Scripts/python -m pytest backend/tests/test_photo.py -v`
Expected: PASS.

> If `check_input`'s result objects use different attribute names than `label/ok/detail`, open `src/mini_highlight_advisor/input_check.py` and match them; adjust the dict keys and the test accordingly.

- [ ] **Step 5: Commit**

```bash
git add backend/main.py backend/tests/test_photo.py
git commit -m "feat(backend): POST /api/photo — decode, shade, cache, seed defaults"
```

---

## Task 6: `POST /api/analyze` (whole-mini)

**Files:**
- Modify: `backend/main.py`
- Test: `backend/tests/test_analyze.py`

**Interfaces:**
- Consumes: `shading_cache` (Task 5); `AnalyzeRequest` (Task 4); `paint_from_model` (Task 4); `png_data_uri` (Task 2); `analyze_regions` (core).
- Produces: module-level `result_cache = LRU(maxsize=16)`; `POST /api/analyze` (JSON `AnalyzeRequest`) → `{preview_png:str, result_token:str}`. Unknown `photo_id` → HTTP 404. Stores `result_token → MultiRegionResult`.

- [ ] **Step 1: Write the failing test**

```python
# backend/tests/test_analyze.py
import io
import numpy as np
from PIL import Image
from fastapi.testclient import TestClient
from backend.main import app

client = TestClient(app)

def _upload():
    arr = (np.random.default_rng(1).integers(0, 255, (40, 30, 3))).astype("uint8")
    buf = io.BytesIO(); Image.fromarray(arr).save(buf, format="PNG")
    return client.post("/api/photo", files={"file": ("m.png", buf.getvalue(), "image/png")}).json()

def test_analyze_returns_preview_and_token():
    up = _upload()
    req = {"photo_id": up["photo_id"], "whole": up["default_whole"]}
    r = client.post("/api/analyze", json=req)
    assert r.status_code == 200
    body = r.json()
    assert body["preview_png"].startswith("data:image/png;base64,")
    assert len(body["result_token"]) == 16

def test_analyze_unknown_photo_404():
    req = {"photo_id": "deadbeefdeadbeef",
           "whole": {"palette": [{"name": "a", "hex": "#101010"}], "coverage": [1.0]}}
    assert client.post("/api/analyze", json=req).status_code == 404
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.venv/Scripts/python -m pytest backend/tests/test_analyze.py -v`
Expected: FAIL — route missing.

- [ ] **Step 3: Write minimal implementation** (add to `backend/main.py`)

```python
from fastapi import HTTPException

from mini_highlight_advisor.pipeline import analyze_regions
from backend.schemas import AnalyzeRequest
from backend.core_adapters import paint_from_model
from backend.serialize import png_data_uri

result_cache = LRU(maxsize=16)


@app.post("/api/analyze")
def analyze(req: AnalyzeRequest):
    cached = shading_cache.get(req.photo_id)
    if cached is None:
        raise HTTPException(status_code=404, detail="unknown photo_id; re-upload the photo")
    rgb, alpha, shading = cached
    palette = [paint_from_model(p) for p in req.whole.palette]
    result = analyze_regions(
        rgb, alpha, palette, list(req.whole.coverage), [],
        edges=req.settings.edge_hl,
        extreme_edge=req.settings.edge_extreme,
        edge_sensitivity=req.settings.edge_sens,
        relief_cap=req.settings.relief_cap,
        per_region_norm=req.settings.per_region_norm,
        whole_material=req.whole.material,
        shading=shading,
    )
    token = hashlib.sha256(
        (req.photo_id + req.model_dump_json()).encode("utf-8")
    ).hexdigest()[:16]
    result_cache.set(token, result)
    return {"preview_png": png_data_uri(result.combined_rgb), "result_token": token}
```

- [ ] **Step 4: Run test to verify it passes**

Run: `.venv/Scripts/python -m pytest backend/tests/test_analyze.py -v`
Expected: PASS.

- [ ] **Step 5: Run the whole backend suite**

Run: `.venv/Scripts/python -m pytest backend/tests -v`
Expected: all PASS.

- [ ] **Step 6: Commit**

```bash
git add backend/main.py backend/tests/test_analyze.py
git commit -m "feat(backend): POST /api/analyze — whole-mini preview + result token"
```

---

## Task 7: Sample-photo endpoints

**Files:**
- Modify: `backend/main.py`
- Test: `backend/tests/test_samples.py`

**Interfaces:**
- Consumes: `samples.list_photos()` (core) → `SamplePhoto(name, path)`.
- Produces: `GET /api/samples/photos` → `[{id:str, name:str}]` (`id = path.stem`); `GET /api/samples/photos/{sid}` → the image file bytes (`FileResponse`), 404 if no match.

- [ ] **Step 1: Write the failing test**

```python
# backend/tests/test_samples.py
from fastapi.testclient import TestClient
from mini_highlight_advisor import samples
from backend.main import app

client = TestClient(app)

def test_list_samples_matches_core():
    r = client.get("/api/samples/photos")
    assert r.status_code == 200
    assert len(r.json()) == len(samples.list_photos())

def test_fetch_first_sample_bytes():
    photos = samples.list_photos()
    if not photos:
        import pytest; pytest.skip("no bundled sample photos")
    sid = photos[0].path.stem
    r = client.get(f"/api/samples/photos/{sid}")
    assert r.status_code == 200 and r.content[:4] in (b"\x89PNG", b"\xff\xd8\xff\xe0")

def test_unknown_sample_404():
    assert client.get("/api/samples/photos/nope-not-real").status_code == 404
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.venv/Scripts/python -m pytest backend/tests/test_samples.py -v`
Expected: FAIL — routes missing.

- [ ] **Step 3: Write minimal implementation** (add to `backend/main.py`)

```python
from fastapi.responses import FileResponse

from mini_highlight_advisor import samples


@app.get("/api/samples/photos")
def sample_photos():
    return [{"id": p.path.stem, "name": p.name} for p in samples.list_photos()]


@app.get("/api/samples/photos/{sid}")
def sample_photo(sid: str):
    for p in samples.list_photos():
        if p.path.stem == sid:
            return FileResponse(p.path)
    raise HTTPException(status_code=404, detail="unknown sample id")
```

- [ ] **Step 4: Run test to verify it passes**

Run: `.venv/Scripts/python -m pytest backend/tests/test_samples.py -v`
Expected: PASS (or SKIP on the fetch test if no samples are bundled).

- [ ] **Step 5: Commit**

```bash
git add backend/main.py backend/tests/test_samples.py
git commit -m "feat(backend): sample-photo listing and download endpoints"
```

---

## Task 8: Frontend scaffold + typed API client

**Files:**
- Create: `web/package.json`, `web/tsconfig.json`, `web/tsconfig.node.json`, `web/vite.config.ts`, `web/index.html`, `web/src/main.tsx`, `web/src/App.tsx`, `web/src/api/types.ts`, `web/src/api/client.ts`, `web/src/test/setup.ts`
- Test: `web/src/api/client.test.ts`

**Interfaces:**
- Produces (`web/src/api/types.ts`): `PaintColor`, `Whole`, `Settings`, `Analyze­Request`, `PhotoResponse`, `AnalyzeResponse`, `SamplePhoto` — TS mirrors of the pydantic models.
- Produces (`web/src/api/client.ts`): `uploadPhoto(file: Blob, name?: string): Promise<PhotoResponse>`, `analyze(req: AnalyzeRequest): Promise<AnalyzeResponse>`, `listSamplePhotos(): Promise<SamplePhoto[]>`, `samplePhotoBlob(id: string): Promise<Blob>`. Base URL is `/api` (Vite proxy).

- [ ] **Step 1: Scaffold the Vite React-TS app**

Run (from repo root):
```bash
npm create vite@latest web -- --template react-ts
cd web && npm install && npm install zustand
npm install -D vitest @testing-library/react @testing-library/jest-dom jsdom
```

- [ ] **Step 2: Configure Vite proxy + Vitest**

```ts
// web/vite.config.ts
import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

export default defineConfig({
  plugins: [react()],
  server: { proxy: { "/api": "http://localhost:8000" } },
  test: { environment: "jsdom", setupFiles: ["./src/test/setup.ts"], globals: true },
});
```

```ts
// web/src/test/setup.ts
import "@testing-library/jest-dom";
```

Add to `web/package.json` `"scripts"`: `"test": "vitest run"`, `"test:watch": "vitest"`.

- [ ] **Step 3: Write the failing test**

```ts
// web/src/api/client.test.ts
import { describe, it, expect, vi, afterEach } from "vitest";
import { uploadPhoto, listSamplePhotos } from "./client";

afterEach(() => vi.restoreAllMocks());

describe("api client", () => {
  it("POSTs multipart to /api/photo and returns parsed body", async () => {
    const body = { photo_id: "abc", width: 10, height: 20, quality_checks: [], default_whole: { palette: [], coverage: [], material: "matte" } };
    const fetchMock = vi.fn().mockResolvedValue({ ok: true, json: async () => body });
    vi.stubGlobal("fetch", fetchMock);
    const res = await uploadPhoto(new Blob(["x"]), "m.png");
    expect(res.photo_id).toBe("abc");
    const [url, opts] = fetchMock.mock.calls[0];
    expect(url).toBe("/api/photo");
    expect(opts.method).toBe("POST");
    expect(opts.body).toBeInstanceOf(FormData);
  });

  it("throws on non-ok response", async () => {
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue({ ok: false, status: 404, text: async () => "nope" }));
    await expect(listSamplePhotos()).rejects.toThrow(/404/);
  });
});
```

- [ ] **Step 4: Run test to verify it fails**

Run: `cd web && npm test`
Expected: FAIL — `./client` has no exports yet.

- [ ] **Step 5: Write the types and client**

```ts
// web/src/api/types.ts
export interface PaintColor {
  name: string; hex: string; brand?: string | null;
  paint_range?: string | null; code?: string; finish?: string;
}
export interface Whole { palette: PaintColor[]; coverage: number[]; material: string; }
export interface Settings {
  edge_hl: boolean; edge_extreme: boolean; edge_sens: number;
  relief_cap: boolean; per_region_norm: boolean;
}
export interface AnalyzeRequest { photo_id: string; whole: Whole; settings?: Partial<Settings>; }
export interface QualityCheck { label: string; ok: boolean; detail: string; }
export interface PhotoResponse {
  photo_id: string; width: number; height: number;
  quality_checks: QualityCheck[]; default_whole: Whole;
}
export interface AnalyzeResponse { preview_png: string; result_token: string; }
export interface SamplePhoto { id: string; name: string; }
```

```ts
// web/src/api/client.ts
import type { AnalyzeRequest, AnalyzeResponse, PhotoResponse, SamplePhoto } from "./types";

async function json<T>(res: Response): Promise<T> {
  if (!res.ok) throw new Error(`${res.status} ${await res.text()}`);
  return res.json() as Promise<T>;
}

export async function uploadPhoto(file: Blob, name = "upload.png"): Promise<PhotoResponse> {
  const fd = new FormData();
  fd.append("file", file, name);
  return json<PhotoResponse>(await fetch("/api/photo", { method: "POST", body: fd }));
}

export async function analyze(req: AnalyzeRequest): Promise<AnalyzeResponse> {
  return json<AnalyzeResponse>(await fetch("/api/analyze", {
    method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(req),
  }));
}

export async function listSamplePhotos(): Promise<SamplePhoto[]> {
  return json<SamplePhoto[]>(await fetch("/api/samples/photos"));
}

export async function samplePhotoBlob(id: string): Promise<Blob> {
  const res = await fetch(`/api/samples/photos/${id}`);
  if (!res.ok) throw new Error(`${res.status}`);
  return res.blob();
}
```

- [ ] **Step 6: Run test to verify it passes**

Run: `cd web && npm test`
Expected: PASS.

- [ ] **Step 7: Commit**

```bash
git add web/
git commit -m "feat(web): Vite+React+TS scaffold, Vitest, typed API client"
```

---

## Task 9: Zustand store + debounced analyze hook

**Files:**
- Create: `web/src/store/projectStore.ts`, `web/src/hooks/useAnalyze.ts`
- Test: `web/src/store/projectStore.test.ts`

**Interfaces:**
- Consumes: `analyze` (Task 8 client); `Whole`, `Settings`, `PhotoResponse` (Task 8 types).
- Produces (`projectStore.ts`): a Zustand hook `useProjectStore` with state `{ photoId?:string; width?:number; height?:number; whole?:Whole; settings:Settings; preview?:string; resultToken?:string; error?:string }` and actions `setPhoto(res:PhotoResponse)`, `setCoverage(cov:number[])`, `setBandCount(n:number)`, `setPreview(png:string, token:string)`, `setError(msg?:string)`. `DEFAULT_SETTINGS` exported. `setBandCount` truncates/extends `whole.palette` and `whole.coverage` to `n` (re-normalizing coverage to sum 1).
- Produces (`useAnalyze.ts`): `useAnalyze()` — a hook that watches `photoId`, `whole`, `settings`, debounces 150ms, calls `analyze`, and dispatches `setPreview` / `setError`.

- [ ] **Step 1: Write the failing test**

```ts
// web/src/store/projectStore.test.ts
import { describe, it, expect, beforeEach } from "vitest";
import { useProjectStore } from "./projectStore";

const reset = () => useProjectStore.setState(useProjectStore.getInitialState());

describe("projectStore", () => {
  beforeEach(reset);

  it("setPhoto seeds whole + dims from response", () => {
    useProjectStore.getState().setPhoto({
      photo_id: "p1", width: 30, height: 40, quality_checks: [],
      default_whole: { palette: [{ name: "a", hex: "#000000" }], coverage: [1.0], material: "matte" },
    });
    const s = useProjectStore.getState();
    expect(s.photoId).toBe("p1");
    expect(s.width).toBe(30);
    expect(s.whole?.coverage).toEqual([1.0]);
  });

  it("setBandCount resizes palette+coverage and coverage sums to ~1", () => {
    const st = useProjectStore.getState();
    st.setPhoto({ photo_id: "p", width: 1, height: 1, quality_checks: [],
      default_whole: { palette: [{ name: "a", hex: "#000000" }], coverage: [1.0], material: "matte" } });
    st.setBandCount(4);
    const w = useProjectStore.getState().whole!;
    expect(w.palette).toHaveLength(4);
    expect(w.coverage).toHaveLength(4);
    expect(Math.abs(w.coverage.reduce((a, b) => a + b, 0) - 1)).toBeLessThan(1e-6);
  });
});
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd web && npm test`
Expected: FAIL — `./projectStore` has no exports.

- [ ] **Step 3: Write minimal implementation**

```ts
// web/src/store/projectStore.ts
import { create } from "zustand";
import type { PhotoResponse, Settings, Whole } from "../api/types";

export const DEFAULT_SETTINGS: Settings = {
  edge_hl: true, edge_extreme: false, edge_sens: 0.5,
  relief_cap: true, per_region_norm: false,
};

interface State {
  photoId?: string; width?: number; height?: number;
  whole?: Whole; settings: Settings;
  preview?: string; resultToken?: string; error?: string;
  setPhoto(res: PhotoResponse): void;
  setCoverage(cov: number[]): void;
  setBandCount(n: number): void;
  setPreview(png: string, token: string): void;
  setError(msg?: string): void;
}

function resize<T>(arr: T[], n: number, fill: (i: number) => T): T[] {
  const out = arr.slice(0, n);
  for (let i = out.length; i < n; i++) out.push(fill(i));
  return out;
}

export const useProjectStore = create<State>((set) => ({
  settings: DEFAULT_SETTINGS,
  setPhoto: (res) => set({
    photoId: res.photo_id, width: res.width, height: res.height,
    whole: res.default_whole, preview: undefined, error: undefined,
  }),
  setCoverage: (cov) => set((s) => (s.whole ? { whole: { ...s.whole, coverage: cov } } : {})),
  setBandCount: (n) => set((s) => {
    if (!s.whole) return {};
    const palette = resize(s.whole.palette, n, () => ({ name: "band", hex: "#808080" }));
    const coverage = resize(s.whole.coverage, n, () => 1 / n).map(() => 1 / n);
    return { whole: { ...s.whole, palette, coverage } };
  }),
  setPreview: (png, token) => set({ preview: png, resultToken: token, error: undefined }),
  setError: (msg) => set({ error: msg }),
}));
```

```ts
// web/src/hooks/useAnalyze.ts
import { useEffect, useRef } from "react";
import { analyze } from "../api/client";
import { useProjectStore } from "../store/projectStore";

export function useAnalyze(delay = 150) {
  const { photoId, whole, settings, setPreview, setError } = useProjectStore();
  const timer = useRef<ReturnType<typeof setTimeout>>();
  useEffect(() => {
    if (!photoId || !whole) return;
    clearTimeout(timer.current);
    timer.current = setTimeout(async () => {
      try {
        const res = await analyze({ photo_id: photoId, whole, settings });
        setPreview(res.preview_png, res.result_token);
      } catch (e) {
        setError(e instanceof Error ? e.message : String(e));
      }
    }, delay);
    return () => clearTimeout(timer.current);
  }, [photoId, whole, settings, delay, setPreview, setError]);
}
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd web && npm test`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add web/src/store web/src/hooks
git commit -m "feat(web): Zustand project store + debounced analyze hook"
```

---

## Task 10: Uploader + preview components, wired into App

**Files:**
- Create: `web/src/components/PhotoUploader.tsx`, `web/src/components/PreviewImage.tsx`, `web/src/components/BandControl.tsx`
- Modify: `web/src/App.tsx`
- Test: `web/src/components/PhotoUploader.test.tsx`

**Interfaces:**
- Consumes: store actions/state (Task 9); `uploadPhoto`, `listSamplePhotos`, `samplePhotoBlob` (Task 8).
- Produces: `<PhotoUploader/>` (file input + sample buttons; on select, uploads and calls `setPhoto`), `<PreviewImage/>` (renders `preview` data URI or a placeholder; shows `error`), `<BandControl/>` (range input 1–8 → `setBandCount`). `<App/>` mounts them and calls `useAnalyze()`.

- [ ] **Step 1: Write the failing test**

```tsx
// web/src/components/PhotoUploader.test.tsx
import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
import { render, screen, waitFor } from "@testing-library/react";
import { PhotoUploader } from "./PhotoUploader";
import { useProjectStore } from "../store/projectStore";
import * as client from "../api/client";

beforeEach(() => useProjectStore.setState(useProjectStore.getInitialState()));
afterEach(() => vi.restoreAllMocks());

it("lists sample photos and seeds the store when one is picked", async () => {
  vi.spyOn(client, "listSamplePhotos").mockResolvedValue([{ id: "necron", name: "Necron" }]);
  vi.spyOn(client, "samplePhotoBlob").mockResolvedValue(new Blob(["x"]));
  vi.spyOn(client, "uploadPhoto").mockResolvedValue({
    photo_id: "s1", width: 10, height: 10, quality_checks: [],
    default_whole: { palette: [{ name: "a", hex: "#000000" }], coverage: [1.0], material: "matte" },
  });
  render(<PhotoUploader />);
  const btn = await screen.findByRole("button", { name: /Necron/ });
  btn.click();
  await waitFor(() => expect(useProjectStore.getState().photoId).toBe("s1"));
});
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd web && npm test`
Expected: FAIL — component missing.

- [ ] **Step 3: Write the components**

```tsx
// web/src/components/PhotoUploader.tsx
import { useEffect, useState } from "react";
import { listSamplePhotos, samplePhotoBlob, uploadPhoto } from "../api/client";
import type { SamplePhoto } from "../api/types";
import { useProjectStore } from "../store/projectStore";

export function PhotoUploader() {
  const setPhoto = useProjectStore((s) => s.setPhoto);
  const setError = useProjectStore((s) => s.setError);
  const [samples, setSamples] = useState<SamplePhoto[]>([]);

  useEffect(() => { listSamplePhotos().then(setSamples).catch(() => setSamples([])); }, []);

  async function handleBlob(blob: Blob, name: string) {
    try { setPhoto(await uploadPhoto(blob, name)); }
    catch (e) { setError(e instanceof Error ? e.message : String(e)); }
  }

  return (
    <div>
      <input type="file" accept="image/png,image/jpeg" onChange={(e) => {
        const f = e.target.files?.[0]; if (f) handleBlob(f, f.name);
      }} />
      {samples.length > 0 && (
        <div>
          <p>Or start from a sample:</p>
          {samples.map((s) => (
            <button key={s.id} onClick={async () => handleBlob(await samplePhotoBlob(s.id), `${s.id}.png`)}>
              {s.name}
            </button>
          ))}
        </div>
      )}
    </div>
  );
}
```

```tsx
// web/src/components/PreviewImage.tsx
import { useProjectStore } from "../store/projectStore";

export function PreviewImage() {
  const preview = useProjectStore((s) => s.preview);
  const error = useProjectStore((s) => s.error);
  if (error) return <p role="alert" style={{ color: "crimson" }}>Analyze failed: {error}</p>;
  if (!preview) return <p>Upload a photo or pick a sample to see the preview.</p>;
  return <img src={preview} alt="painted preview" style={{ maxWidth: "100%" }} />;
}
```

```tsx
// web/src/components/BandControl.tsx
import { useProjectStore } from "../store/projectStore";

export function BandControl() {
  const whole = useProjectStore((s) => s.whole);
  const setBandCount = useProjectStore((s) => s.setBandCount);
  if (!whole) return null;
  return (
    <label>
      Bands: {whole.palette.length}
      <input type="range" min={1} max={8} value={whole.palette.length}
        onChange={(e) => setBandCount(Number(e.target.value))} />
    </label>
  );
}
```

```tsx
// web/src/App.tsx
import { PhotoUploader } from "./components/PhotoUploader";
import { PreviewImage } from "./components/PreviewImage";
import { BandControl } from "./components/BandControl";
import { useAnalyze } from "./hooks/useAnalyze";

export default function App() {
  useAnalyze();
  return (
    <main style={{ maxWidth: 900, margin: "0 auto", padding: 16 }}>
      <h1>Mini Highlight Advisor</h1>
      <PhotoUploader />
      <BandControl />
      <PreviewImage />
    </main>
  );
}
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd web && npm test`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add web/src
git commit -m "feat(web): uploader, band control, preview — wired via useAnalyze"
```

---

## Task 11: Run docs + manual end-to-end verification

**Files:**
- Create: `backend/README.md`, `web/README.md`
- Modify: `CLAUDE.md` (append a "Web app (React + FastAPI)" section)

**Interfaces:** none (docs + manual verification).

- [ ] **Step 1: Write `backend/README.md`**

```markdown
# Backend (FastAPI)

Install: `.venv/Scripts/python -m pip install -r backend/requirements.txt`
Run:     `.venv/Scripts/python -m uvicorn backend.main:app --reload --port 8000`
Test:    `.venv/Scripts/python -m pytest backend/tests -v`

The backend imports the `mini_highlight_advisor` core directly and adapts it to
HTTP. It does not modify `src/`. Streamlit (`streamlit run app.py`) still runs
independently on :8501.
```

- [ ] **Step 2: Write `web/README.md`**

```markdown
# Web (Vite + React + TS)

Install: `cd web && npm install`
Dev:     `npm run dev`   # http://localhost:5173, proxies /api → :8000
Test:    `npm test`

Start the backend first (`uvicorn backend.main:app --port 8000`), then `npm run dev`.
```

- [ ] **Step 3: Append to `CLAUDE.md`**

Add a section documenting: the two-process layout, that `src/` is the shared core, that Streamlit and the React app coexist, and the three commands above.

- [ ] **Step 4: Manual end-to-end verification**

Start both servers, open http://localhost:5173, and confirm:
- The file picker uploads a photo and the preview appears.
- Each bundled sample button loads and previews.
- Dragging the Bands slider re-renders the preview (proves the debounced analyze loop).
- Stopping the backend surfaces the inline "Analyze failed" banner (proves error handling).

Record the result (paste of the observed behavior / screenshot) in the PR description. Per repo policy, the human runs this step — do not self-certify.

- [ ] **Step 5: Commit**

```bash
git add backend/README.md web/README.md CLAUDE.md
git commit -m "docs: run instructions for backend + web; CLAUDE.md web section"
```

---

## Self-Review

**Spec coverage (Phase 0 scope only):**
- Two-process architecture (spec §4) → Tasks 1, 8.
- `/api/photo` with shading cache + quality checks + default seed (spec §5) → Task 5.
- `/api/analyze` whole-mini preview + result token + memo cache (spec §5, §8) → Task 6.
- Render-each-edit loop, base64 PNG transport (spec §3, §5) → Tasks 6, 9, 10.
- Sample/demo data served (spec §2, §5) → Task 7, consumed in Task 10.
- Zustand store = manifest-shaped subset (spec §6) → Task 9 (`whole`/`settings`; full manifest is a later phase).
- Error banner replacing `st.error` (spec §9) → Tasks 9, 10.
- Streamlit coexistence, `src/` untouched, separate deps (spec §4, §10) → Global Constraints, Tasks 1, 11.
- **Deferred to later phases (correctly out of Phase 0):** regions/points + schema v6 (§6), `/steps` (§5), colour panel/scheme/match/collection/projects endpoints (§5), i18n (§2), angles/paints/capture (§7). These are named in the spec and will get their own plans.

**Placeholder scan:** No "TBD"/"handle edge cases" steps; every code step has literal code.

**Type consistency:** `photo_id`/`result_token` are `sha256(...)[:16]` (16 chars) — asserted consistently in Tasks 5, 6 and TS type in Task 8. `default_whole` shape (`palette`/`coverage`/`material`) is identical across `core_adapters.default_whole` (Task 4), the `/api/photo` response (Task 5), and the TS `Whole` type (Task 8). Store actions `setPhoto/setCoverage/setBandCount/setPreview/setError` match between `projectStore` (Task 9) and consumers (Tasks 9 hook, 10 components).
```
