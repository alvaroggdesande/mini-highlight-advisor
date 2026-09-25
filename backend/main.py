import hashlib
import json
import math
import os
from pathlib import Path

from fastapi import FastAPI, File, HTTPException, UploadFile
from fastapi.responses import FileResponse, Response, StreamingResponse
from fastapi.staticfiles import StaticFiles

from mini_highlight_advisor.pipeline import analyze_regions, prepare_shading
from mini_highlight_advisor.regions import Region, polygons_to_mask
from mini_highlight_advisor.input_check import check_input
from mini_highlight_advisor import samples
from backend.cache import LRU
from backend.core_adapters import decode_image, default_whole, paint_from_model, paint_to_dict
from backend.schemas import (
    AnalyzeRequest, RegionColorSpec as RegionColorSpecModel,
    SchemeGenerateRequest, RampGenerateRequest, MatchRequest, RecipeModel,
    StepsResponse, RegionPlanDto, StepImageDto, SaveProjectRequest,
)
from backend.serialize import png_data_uri, to_png_bytes
from backend import project_store

from mini_highlight_advisor.catalog import load_catalog as _load_catalog_raw

_catalog_cache: list | None = None


def _catalog():
    global _catalog_cache
    if _catalog_cache is None:
        _catalog_cache = _load_catalog_raw()
    return _catalog_cache

app = FastAPI(title="Mini Highlight Advisor API")

# Memory budget (512 MB free tier): the heavy objects are the decoded photos in
# shading_cache (~4 MB each). result_cache holds only the small AnalyzeRequest
# per token — step images are rendered on demand in /api/steps and freed after
# the response, never cached — so it can be large and cheap.
shading_cache = LRU(maxsize=8)
result_cache = LRU(maxsize=32)
mask_cache = LRU(maxsize=32)


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
    suffix = Path(file.filename or "upload.png").suffix or ".png"
    project_store.save_photo(photo_id, suffix, data)
    checks = [{"label": c.label, "ok": c.ok, "detail": c.detail}
              for c in check_input(rgb, shading.mask)]
    h, w = rgb.shape[:2]
    return {"photo_id": photo_id, "width": w, "height": h,
            "quality_checks": checks, "default_whole": default_whole()}


def _get_shading(photo_id: str):
    """Return (rgb, alpha, shading) for a photo, rebuilding it from the persisted
    bytes on a cache miss. The in-memory cache is volatile — it is lost whenever
    the worker restarts (free-tier OOM auto-restart, idle spin-down, redeploy) —
    so falling back to disk keeps analysis working instead of 404-ing on an old
    photo_id the client still holds. Returns None only if the photo is truly gone."""
    cached = shading_cache.get(photo_id)
    if cached is not None:
        return cached
    loaded = project_store.load_photo_bytes(photo_id)
    if loaded is None:
        return None
    data, suffix = loaded
    rgb, alpha = decode_image(data, f"{photo_id}{suffix}")
    shading = prepare_shading(rgb, alpha)
    entry = (rgb, alpha, shading)
    shading_cache.set(photo_id, entry)
    return entry


def _build_result(req: AnalyzeRequest, *, with_steps: bool):
    """Rebuild the analysis for a request. with_steps=False skips the heavy
    per-band step images (used for the live preview); True renders them (used
    only when the Paint tab requests the paint-along guide)."""
    cached = _get_shading(req.photo_id)
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

    return analyze_regions(
        rgb, alpha, palette, list(req.whole.coverage), regions,
        edges=req.settings.edge_hl,
        extreme_edge=req.settings.edge_extreme,
        edge_sensitivity=req.settings.edge_sens,
        relief_cap=req.settings.relief_cap,
        per_region_norm=req.settings.per_region_norm,
        whole_material=req.whole.material,
        with_steps=with_steps,
        shading=shading,
    )


@app.post("/api/analyze")
def analyze(req: AnalyzeRequest):
    # Preview only — no step images built or cached (keeps peak memory low).
    result = _build_result(req, with_steps=False)
    token = hashlib.sha256((req.photo_id + req.model_dump_json()).encode("utf-8")).hexdigest()[:16]
    result_cache.set(token, req)  # cache the small request; steps rebuilt on demand
    return {"preview_png": png_data_uri(result.combined_rgb), "result_token": token}


@app.get("/api/steps")
def get_steps(token: str) -> StepsResponse:
    req = result_cache.get(token)
    if req is None:
        raise HTTPException(status_code=409, detail="token expired; re-analyze to refresh")
    # Heavy step images built here, on demand, and freed when the response is sent.
    # _build_result rebuilds shading from disk on a cache miss (worker restart).
    result = _build_result(req, with_steps=True)
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
    cached = _get_shading(photo_id)
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
        "delta_e": result.delta_e if math.isfinite(result.delta_e) else 999.0,
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
    from mini_highlight_advisor.recipes import import_from_json_bytes, load_all, save_user
    data = await file.read()
    new_recipes = import_from_json_bytes(data)
    for recipe in new_recipes:
        save_user(recipe)
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


@app.get("/api/projects")
def list_projects():
    return {"projects": project_store.list_projects()}


@app.put("/api/projects")
def save_project(req: SaveProjectRequest):
    for angle in req.angles:
        photo_id = angle.get("photo_id")
        if photo_id and project_store.load_photo_bytes(photo_id) is None:
            raise HTTPException(
                status_code=409,
                detail=f"photo {photo_id!r} not found on disk; re-upload the photo before saving",
            )
    manifest = {
        "schema_version": 6,
        "name": req.name,
        "active_angle": req.active_angle,
        "angles": req.angles,
    }
    slug = project_store.save_project(req.name, manifest)
    saved = project_store.load_project(slug)
    return {"slug": slug, "name": req.name, "updated_at": saved["updated_at"]}


@app.get("/api/projects/{slug}/download")
def download_project(slug: str):
    try:
        blob = project_store.project_to_blob(slug)
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail="project not found")
    return Response(
        content=blob,
        media_type="application/json",
        headers={"Content-Disposition": f"attachment; filename={slug}.json"},
    )


@app.post("/api/projects/upload")
async def upload_project_blob(file: UploadFile = File(...)):
    data = await file.read()
    try:
        manifest, photos = project_store.project_from_blob(data)
        for photo_id, (suffix, photo_bytes) in photos.items():
            project_store.save_photo(photo_id, suffix, photo_bytes)
            if shading_cache.get(photo_id) is None:
                try:
                    rgb, alpha = decode_image(photo_bytes, f"photo{suffix}")
                    shading = prepare_shading(rgb, alpha)
                    shading_cache.set(photo_id, (rgb, alpha, shading))
                except Exception:
                    pass
        slug = project_store.save_project(manifest["name"], manifest)
        return project_store.load_project(slug)
    except (json.JSONDecodeError, KeyError, ValueError) as exc:
        raise HTTPException(status_code=422, detail=f"invalid project blob: {exc}")


@app.get("/api/projects/{slug}")
def get_project(slug: str):
    try:
        manifest = project_store.load_project(slug)
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail="project not found")
    for angle in manifest.get("angles", []):
        photo_id = angle.get("photo_id")
        if photo_id and shading_cache.get(photo_id) is None:
            result = project_store.load_photo_bytes(photo_id)
            if result is None:
                continue
            photo_bytes, suffix = result
            try:
                rgb, alpha = decode_image(photo_bytes, f"photo{suffix}")
                shading = prepare_shading(rgb, alpha)
                shading_cache.set(photo_id, (rgb, alpha, shading))
            except Exception:
                continue
    return manifest


@app.delete("/api/projects/{slug}")
def delete_project(slug: str):
    project_store.delete_project(slug)
    return {"ok": True}


# Serve the built React SPA in production (after `npm run build`).
# In dev, web/dist doesn't exist — Vite dev server handles the frontend instead.
_dist = os.path.join(os.path.dirname(__file__), "..", "web", "dist")
if os.path.isdir(_dist):
    app.mount("/", StaticFiles(directory=_dist, html=True), name="static")
