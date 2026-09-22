import hashlib
import json
import os

from fastapi import FastAPI, File, HTTPException, UploadFile
from fastapi.responses import FileResponse, Response, StreamingResponse
from fastapi.staticfiles import StaticFiles

from mini_highlight_advisor.pipeline import analyze_regions, prepare_shading
from mini_highlight_advisor.regions import Region, polygons_to_mask
from mini_highlight_advisor.input_check import check_input
from mini_highlight_advisor import samples
from backend.cache import LRU
from backend.core_adapters import decode_image, default_whole, paint_from_model, paint_to_dict
from backend.schemas import AnalyzeRequest, RegionColorSpec as RegionColorSpecModel, SchemeGenerateRequest, RampGenerateRequest, MatchRequest, RecipeModel
from backend.serialize import png_data_uri, to_png_bytes

from mini_highlight_advisor.catalog import load_catalog as _load_catalog_raw

_catalog_cache: list | None = None


def _catalog():
    global _catalog_cache
    if _catalog_cache is None:
        _catalog_cache = _load_catalog_raw()
    return _catalog_cache

app = FastAPI(title="Mini Highlight Advisor API")

shading_cache = LRU(maxsize=8)
result_cache = LRU(maxsize=16)
mask_cache = LRU(maxsize=64)


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
    h, w = rgb.shape[:2]
    palette = [paint_from_model(p) for p in req.whole.palette]

    regions = []
    for rm in req.regions:
        rings = [[(float(x), float(y)) for x, y in ring] for ring in rm.rings]
        key = (req.photo_id, hashlib.sha256(json.dumps(rings).encode()).hexdigest())
        mask = mask_cache.get(key)
        if mask is None:
            mask = polygons_to_mask(rings, (h, w)) & shading.mask
            mask_cache.set(key, mask)
        regions.append(Region(
            name=rm.name, mask=mask,
            palette=[paint_from_model(p) for p in rm.palette],
            coverage=list(rm.coverage), material=rm.material,
        ))

    result = analyze_regions(
        rgb, alpha, palette, list(req.whole.coverage), regions,
        edges=req.settings.edge_hl,
        extreme_edge=req.settings.edge_extreme,
        edge_sensitivity=req.settings.edge_sens,
        relief_cap=req.settings.relief_cap,
        per_region_norm=req.settings.per_region_norm,
        whole_material=req.whole.material,
        shading=shading,
    )
    token = hashlib.sha256((req.photo_id + req.model_dump_json()).encode("utf-8")).hexdigest()[:16]
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


@app.get("/api/photo/{photo_id}/image")
def photo_image(photo_id: str):
    cached = shading_cache.get(photo_id)
    if cached is None:
        raise HTTPException(status_code=404, detail="unknown photo_id; re-upload the photo")
    rgb, _alpha, _shading = cached
    return Response(content=to_png_bytes(rgb), media_type="image/png")


@app.get("/api/catalog")
def get_catalog():
    return {"paints": [paint_to_dict(p) for p in _catalog()]}


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


# Serve the built React SPA in production (after `npm run build`).
# In dev, web/dist doesn't exist — Vite dev server handles the frontend instead.
_dist = os.path.join(os.path.dirname(__file__), "..", "web", "dist")
if os.path.isdir(_dist):
    app.mount("/", StaticFiles(directory=_dist, html=True), name="static")
