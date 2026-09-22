import hashlib

from fastapi import FastAPI, File, UploadFile

from mini_highlight_advisor.pipeline import prepare_shading
from mini_highlight_advisor.input_check import check_input
from backend.cache import LRU
from backend.core_adapters import decode_image, default_whole

app = FastAPI(title="Mini Highlight Advisor API")

shading_cache = LRU(maxsize=8)


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
