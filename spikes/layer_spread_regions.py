"""Per-region layer-spread blind review (2026-10-01). See docs/ideas/layer-spread.md.

Reads a saved project JSON (photos embedded), rebuilds each angle's region masks the
same way the backend does (rings in the 768px analysis space, last-wins ownership,
leftover = "Whole mini"), computes the light field under several variants, and bands
EACH region on its own with the project's coverage -- the app's real path.

Per region it writes one blind sheet: the photo crop, then the variants side by side
labelled A..E in a shuffled order. Top row = all layers, bottom row = top-2 only
(Highlight + Bright Highlight). The answer key and metrics go to key.json / metrics.csv
-- don't open them before picking.

Run from the repo root:
  .venv/Scripts/python.exe spikes/layer_spread_regions.py fixtures/rat-ogre/rat-ogre-5_project.json
"""
import sys, os, io, json, base64, csv, random
import numpy as np, cv2
from PIL import Image
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "src"))
from mini_highlight_advisor.masking import load_image, compute_mask
from mini_highlight_advisor.lighting import _stretch
from mini_highlight_advisor.banding import band_light
from mini_highlight_advisor.edges import edge_mask
from mini_highlight_advisor.regions import polygons_to_mask, assign_owners

SEED = 20261001
TILE_H = 340
PAD = 12
# Shadow -> bright: blue-greys, then orange (Highlight), pale yellow (Bright Highlight).
PAL = np.array([[30, 30, 90], [60, 90, 160], [110, 160, 170], [235, 140, 30], [255, 250, 160]], np.uint8)


def gray(rgb): return cv2.cvtColor(rgb, cv2.COLOR_RGB2GRAY)
def clahe8(rgb): return cv2.createCLAHE(3.0, (8, 8)).apply(gray(rgb)).astype(np.float32)
def bilat3(g):
    for _ in range(3):
        g = cv2.bilateralFilter(g, 9, 25, 5)
    return g


VARIANTS = {
    "current(CLAHE8)":  clahe8,
    "CLAHE8+bilat x3":  lambda rgb: bilat3(clahe8(rgb)),
    "gray+bilat x3":    lambda rgb: bilat3(gray(rgb).astype(np.float32)),
    "plain gray":       lambda rgb: gray(rgb).astype(np.float32),
    "gray+gauss s3":    lambda rgb: cv2.GaussianBlur(gray(rgb).astype(np.float32), (0, 0), 3),
}


def decode(photo):
    data = base64.b64decode(photo["data_b64"])
    path = os.path.join(OUT, "_tmp" + photo["suffix"])
    with open(path, "wb") as f:
        f.write(data)
    try:
        return load_image(path)
    finally:
        os.unlink(path)


def region_metrics(light, sub, bands, n):
    top2 = bands >= n - 2
    _, _, st, _ = cv2.connectedComponentsWithStats(top2.astype(np.uint8), connectivity=8)
    a = st[1:, cv2.CC_STAT_AREA]
    coh = a[a >= 30].sum() / max(a.sum(), 1)
    top1 = bands == n - 1
    er = cv2.erode(top2.astype(np.uint8), np.ones((5, 5), np.uint8)).astype(bool)
    nest = (top1 & er).sum() / max(top1.sum(), 1)
    e = edge_mask(light, sub, 0.5)
    dist = cv2.distanceTransform(sub.astype(np.uint8), cv2.DIST_L2, 3)
    rim = (e & (dist <= 2)).sum() / max(e.sum(), 1)
    return dict(blobs=len(a), coh=round(float(coh), 3), nest=round(float(nest), 3),
                rim=round(float(rim), 3))


def stability(fn, rgb, full, sub, cov):
    """Top-2 IoU inside the region between full-res and a 0.66x-res analysis."""
    n = len(cov)
    b1 = band_light(_stretch(fn(rgb), full), sub, cov) >= n - 2
    s = 0.66
    rgb2 = cv2.resize(rgb, None, fx=s, fy=s, interpolation=cv2.INTER_AREA)
    size = (rgb2.shape[1], rgb2.shape[0])
    f2 = cv2.resize(full.astype(np.uint8), size, interpolation=cv2.INTER_NEAREST).astype(bool)
    s2 = cv2.resize(sub.astype(np.uint8), size, interpolation=cv2.INTER_NEAREST).astype(bool) & f2
    b2 = band_light(_stretch(fn(rgb2), f2), s2, cov) >= n - 2
    b2 = cv2.resize(b2.astype(np.uint8), (sub.shape[1], sub.shape[0]),
                    interpolation=cv2.INTER_NEAREST).astype(bool) & sub
    return round(float((b1 & b2).sum() / max((b1 | b2).sum(), 1)), 3)


def render(rgb, sub, bands, n, box, top2_only):
    y0, y1, x0, x1 = box
    vis = (rgb.astype(np.float32) * 0.4).astype(np.uint8)
    if top2_only:
        vis[sub] = (rgb[sub] * 0.7).astype(np.uint8)
        hi = bands >= n - 2
        vis[hi] = (0.15 * rgb[hi] + 0.85 * PAL[bands[hi] - (n - 2) + 3]).astype(np.uint8)
    else:
        idx = np.round(bands[sub] * (4 / max(n - 1, 1))).astype(int)
        vis[sub] = (0.35 * rgb[sub] + 0.65 * PAL[idx]).astype(np.uint8)
    crop = vis[y0:y1, x0:x1]
    s = TILE_H / crop.shape[0]
    return cv2.resize(crop, (max(1, int(crop.shape[1] * s)), TILE_H), interpolation=cv2.INTER_NEAREST)


def label(img, text):
    img = img.copy()
    cv2.putText(img, text, (8, 30), cv2.FONT_HERSHEY_SIMPLEX, 0.9, (0, 0, 0), 4)
    cv2.putText(img, text, (8, 30), cv2.FONT_HERSHEY_SIMPLEX, 0.9, (255, 80, 255), 2)
    return img


project_path = sys.argv[1]
proj = json.load(open(project_path, encoding="utf-8"))
OUT = os.path.join(ROOT, "spikes", "out", "layer_spread", "regions", proj["slug"])
os.makedirs(OUT, exist_ok=True)
rng = random.Random(SEED)
key, rows = {}, []

for ai, ang in enumerate(proj["angles"], 1):
    rgb, alpha = decode(proj["photos"][ang["photo_id"]])
    h, w = rgb.shape[:2]
    assert (w, h) == (ang["width"], ang["height"]), ((w, h), ang["width"], ang["height"])
    full = compute_mask(rgb, alpha)
    book = ang["book"]
    drawn = book["drawn"]
    rmasks = [polygons_to_mask([[(float(x), float(y)) for x, y in ring] for ring in r["rings"]], (h, w)) & full
              for r in drawn]
    owner = assign_owners(full, rmasks)
    regions = [("Whole mini", owner == -1, book["whole"]["coverage"])]
    regions += [(r["name"], owner == i, r["coverage"]) for i, r in enumerate(drawn)]
    lights = {name: _stretch(fn(rgb), full) for name, fn in VARIANTS.items()}

    for ri, (rname, sub, cov) in enumerate(regions):
        if sub.sum() < 200:
            continue
        n = len(cov)
        ys, xs = np.where(sub)
        box = (max(ys.min() - PAD, 0), min(ys.max() + PAD + 1, h),
               max(xs.min() - PAD, 0), min(xs.max() + PAD + 1, w))
        order = list(VARIANTS)
        rng.shuffle(order)
        sid = f"a{ai}_r{ri}"
        key[sid] = {"angle": ang["label"], "region": rname, "coverage": cov,
                    "letters": {chr(65 + k): v for k, v in enumerate(order)}}
        photo = rgb.copy()
        photo[~sub] = (photo[~sub] * 0.4).astype(np.uint8)
        y0, y1, x0, x1 = box
        pc = photo[y0:y1, x0:x1]
        pc = cv2.resize(pc, (max(1, int(pc.shape[1] * TILE_H / pc.shape[0])), TILE_H))
        raw = rgb[y0:y1, x0:x1]
        raw = cv2.resize(raw, (pc.shape[1], TILE_H))
        top, bot = [label(pc, "region")], [label(raw, "photo")]
        for k, vname in enumerate(order):
            bands = band_light(lights[vname], sub, cov)
            top.append(label(render(rgb, sub, bands, n, box, False), chr(65 + k)))
            bot.append(label(render(rgb, sub, bands, n, box, True), chr(65 + k) + " top-2"))
            m = region_metrics(lights[vname], sub, bands, n)
            m["iou66"] = stability(VARIANTS[vname], rgb, full, sub, cov)
            rows.append({"sheet": sid, "angle": ang["label"], "region": rname,
                         "px": int(sub.sum()), "variant": vname, **m})
        sep = lambda t: np.hstack([np.pad(x, ((0, 0), (0, 6), (0, 0)), constant_values=255) for x in t])
        sheet = np.vstack([sep(top), np.full((6, sep(top).shape[1], 3), 255, np.uint8), sep(bot)])
        cv2.imwrite(os.path.join(OUT, f"{sid}.jpg"), cv2.cvtColor(sheet, cv2.COLOR_RGB2BGR),
                    [cv2.IMWRITE_JPEG_QUALITY, 90])
        print(f"{sid}: {ang['label']} / {rname}  {int(sub.sum())}px")

json.dump(key, open(os.path.join(OUT, "key.json"), "w"), indent=2)
with open(os.path.join(OUT, "metrics.csv"), "w", newline="") as f:
    wr = csv.DictWriter(f, fieldnames=list(rows[0]))
    wr.writeheader(); wr.writerows(rows)
print("wrote", len(key), "sheets to", OUT)
