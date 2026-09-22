import hashlib
import os

from fastapi import FastAPI, File, HTTPException, UploadFile
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from mini_highlight_advisor.pipeline import analyze_regions, prepare_shading
from mini_highlight_advisor.input_check import check_input
from mini_highlight_advisor import samples
from backend.cache import LRU
from backend.core_adapters import decode_image, default_whole, paint_from_model
from backend.schemas import AnalyzeRequest
from backend.serialize import png_data_uri

app = FastAPI(title="Mini Highlight Advisor API")

shading_cache = LRU(maxsize=8)
result_cache = LRU(maxsize=16)


@app.get("/api/health")
def health():
    return {"status": "ok"}


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


@app.get("/api/samples/photos")
def sample_photos():
    return [{"id": p.path.stem, "name": p.name} for p in samples.list_photos()]


@app.get("/api/samples/photos/{sid}")
def sample_photo(sid: str):
    for p in samples.list_photos():
        if p.path.stem == sid:
            return FileResponse(p.path)
    raise HTTPException(status_code=404, detail="unknown sample id")


# Serve the built React SPA in production (after `npm run build`).
# In dev, web/dist doesn't exist — Vite dev server handles the frontend instead.
_dist = os.path.join(os.path.dirname(__file__), "..", "web", "dist")
if os.path.isdir(_dist):
    app.mount("/", StaticFiles(directory=_dist, html=True), name="static")
