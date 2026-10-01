"""Layer-spread probe (2026-10-01). See docs/ideas/layer-spread.md.

Bands the WHOLE mini (holder removed by an approximate orange-hue mask) under several
light-field variants and prints top-2-band metrics per angle plus a median summary.
Writes side-by-side sheets to spikes/out/layer_spread/.

Run from the repo root:  .venv/Scripts/python.exe spikes/layer_spread_probe.py
TODO: per-region mode (read project manifest rings) + blind shuffled review sheets.
"""
import sys, glob, os
import numpy as np, cv2
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "src"))
from mini_highlight_advisor.masking import load_image, compute_mask
from mini_highlight_advisor.lighting import _stretch
from mini_highlight_advisor.banding import band_light
from mini_highlight_advisor.edges import edge_mask

OUT = os.path.join(ROOT, "spikes", "out", "layer_spread")
os.makedirs(OUT, exist_ok=True)
COV = [.33, .27, .20, .13, .07]
N = len(COV)

def gray(rgb): return cv2.cvtColor(rgb, cv2.COLOR_RGB2GRAY)
def clahe(g, t=8): return cv2.createCLAHE(3.0, (t, t)).apply(g)

VARIANTS = {
    "current(CLAHE8)":   lambda rgb, m: clahe(gray(rgb)).astype(np.float32),
    "plain gray":        lambda rgb, m: gray(rgb).astype(np.float32),
    "CLAHE2 (big tiles)":lambda rgb, m: clahe(gray(rgb), 2).astype(np.float32),
    "gray+gauss s3":     lambda rgb, m: cv2.GaussianBlur(gray(rgb).astype(np.float32), (0, 0), 3),
    "gray+bilateral":    lambda rgb, m: cv2.bilateralFilter(gray(rgb).astype(np.float32), 9, 25, 5),
    "gray+bilat x3":     lambda rgb, m: (lambda g: [g := cv2.bilateralFilter(g, 9, 25, 5) for _ in range(3)][-1])(gray(rgb).astype(np.float32)),
}

def blobs(b, min_area=1):
    n, lab, st, _ = cv2.connectedComponentsWithStats(b.astype(np.uint8), connectivity=8)
    areas = st[1:, cv2.CC_STAT_AREA]
    return areas

def metrics(light, mask, rgb):
    bands = band_light(light, mask, COV)
    top2 = bands >= N - 2
    a = blobs(top2)
    big = a[a >= 30]
    # coherence: share of top-2 px living in blobs >= 30px
    coh = big.sum() / max(a.sum(), 1)
    # tiles touched (32px) over tiles that contain mask
    H, W = mask.shape; t = 32
    tm = tt = 0
    for y in range(0, H, t):
        for x in range(0, W, t):
            if mask[y:y+t, x:x+t].any():
                tm += 1; tt += top2[y:y+t, x:x+t].any()
    # nesting: top band inside eroded band>=N-2 (r=2px)
    top1 = bands == N - 1
    er = cv2.erode(top2.astype(np.uint8), np.ones((5, 5), np.uint8)).astype(bool)
    nest = (top1 & er).sum() / max(top1.sum(), 1)
    # base share: bottom 15% of mask bbox rows
    ys = np.where(mask.any(1))[0]; ycut = ys[-1] - 0.15 * (ys[-1] - ys[0])
    base = np.zeros_like(mask); base[int(ycut):] = True; base &= mask
    base_share = (top2 & base).sum() / max(top2.sum(), 1)
    # edges: share on 2px silhouette rim
    e = edge_mask(light, mask, 0.5)
    dist = cv2.distanceTransform(mask.astype(np.uint8), cv2.DIST_L2, 3)
    rim = (e & (dist <= 2)).sum() / max(e.sum(), 1)
    return bands, dict(blobs=len(a), coh=coh, tiles=f"{tt}/{tm}", nest=nest, base=base_share, rim=rim)

def stability(fn, rgb, mask):
    """Top-2 IoU between full-res and a 0.66x-res analysis (upsampled back)."""
    l1 = _stretch(fn(rgb, mask), mask); b1 = band_light(l1, mask, COV) >= N - 2
    s = 0.66
    rgb2 = cv2.resize(rgb, None, fx=s, fy=s, interpolation=cv2.INTER_AREA)
    m2 = cv2.resize(mask.astype(np.uint8), (rgb2.shape[1], rgb2.shape[0]), interpolation=cv2.INTER_NEAREST).astype(bool)
    l2 = _stretch(fn(rgb2, m2), m2); b2 = band_light(l2, m2, COV) >= N - 2
    b2 = cv2.resize(b2.astype(np.uint8), (mask.shape[1], mask.shape[0]), interpolation=cv2.INTER_NEAREST).astype(bool)
    return (b1 & b2).sum() / max((b1 | b2).sum(), 1)

AGG = {}
PAL = np.array([[40,40,40],[90,90,90],[140,140,140],[200,200,120],[255,240,60]], np.uint8)
photos = sorted(glob.glob(os.path.join(ROOT, "fixtures", "rat-ogre", "angle_*.png")))
for p in photos:
    rgb, alpha = load_image(p); full = compute_mask(rgb, alpha)
    hsv = cv2.cvtColor(rgb, cv2.COLOR_RGB2HSV)
    cork = (full & (hsv[...,0] >= 8) & (hsv[...,0] <= 32) & (hsv[...,1] > 70) & (hsv[...,2] > 70)).astype(np.uint8)
    cork = cv2.morphologyEx(cork, cv2.MORPH_CLOSE, np.ones((9,9),np.uint8))
    cork = cv2.morphologyEx(cork, cv2.MORPH_OPEN, np.ones((5,5),np.uint8))
    cork = cv2.dilate(cork, np.ones((5,5),np.uint8)).astype(bool)
    rest = (full & ~cork).astype(np.uint8)
    n, lab, st, _ = cv2.connectedComponentsWithStats(rest, connectivity=8)
    mask = lab == (1 + np.argmax(st[1:, cv2.CC_STAT_AREA]))
    print(f"holder removed: {(full.sum()-mask.sum())/full.sum():.0%} of alpha mask")
    cv2.imwrite(os.path.join(OUT, os.path.basename(p).replace('.png','_mask.png')), (mask*255).astype(np.uint8))
    print(f"\n== {os.path.basename(p)}  {rgb.shape[1]}x{rgb.shape[0]}  mask={mask.sum()}px")
    print(f"{'variant':20s} {'blobs':>6s} {'coh>=30':>8s} {'tiles':>8s} {'nest':>6s} {'base%':>6s} {'rim%':>6s} {'IoU@.66':>8s}")
    tiles = []
    for name, fn in VARIANTS.items():
        light = _stretch(fn(rgb, mask), mask)
        bands, m = metrics(light, mask, rgb)
        iou = stability(fn, rgb, mask)
        AGG.setdefault(name, []).append((m['blobs'], m['coh'], eval(m['tiles']), m['nest'], m['base'], m['rim'], iou))
        print(f"{name:20s} {m['blobs']:6d} {m['coh']:8.2f} {m['tiles']:>8s} {m['nest']:6.2f} {m['base']*100:6.1f} {m['rim']*100:6.1f} {iou:8.2f}")
        vis = rgb.copy(); sel = bands >= 0
        vis[sel] = (0.35 * rgb[sel] + 0.65 * PAL[bands[sel]]).astype(np.uint8)
        cv2.putText(vis, name, (8, 24), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (255, 0, 0), 2)
        tiles.append(vis)
    sheet = np.hstack(tiles)
    cv2.imwrite(os.path.join(OUT, os.path.basename(p).replace(".png", "_noholder.jpg")),
                cv2.cvtColor(sheet, cv2.COLOR_RGB2BGR), [cv2.IMWRITE_JPEG_QUALITY, 85])

print("== MEDIAN over", len(photos), "angles (min-max)")
print(f"{'variant':20s} {'blobs':>12s} {'coh':>11s} {'tiles%':>11s} {'nest':>11s} {'base%':>11s} {'rim%':>11s} {'IoU':>11s}")
for name, rows in AGG.items():
    a = np.array(rows, float); a[:, 4:6] *= 100; a[:, 2] *= 100
    cells = [f"{np.median(a[:,i]):.2f}({a[:,i].min():.2f}-{a[:,i].max():.2f})" if i in (1,3,6) else f"{np.median(a[:,i]):.0f}({a[:,i].min():.0f}-{a[:,i].max():.0f})" for i in range(7)]
    print(f"{name:20s} " + " ".join(f"{c:>11s}" for c in cells))
