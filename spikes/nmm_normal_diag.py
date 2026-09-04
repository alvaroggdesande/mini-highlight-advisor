"""Diagnose PS normal quality: how noisy are the normals, really?

For each bundle: show the normal map as RGB, and a high-pass (Laplacian) view
that isolates pixel-scale noise. Print a noise ratio = high-freq energy / total.
High ratio => reflection-based NMM will always be speckle-or-mud.
"""
import numpy as np
from PIL import Image
import cv2

from mini_highlight_advisor import relight

BUNDLES = [
    "spikes/phone_ps/data/necron_overlord_painted_front.out",
    "spikes/phone_ps/data/necron_reanimator_wip_front.data.out",
    "spikes/phone_ps/data/black_output",
    "spikes/phone_ps/data/skaven_clanrat1_black_front.out",
]


def load(bundle):
    n = relight.load_normals(f"{bundle}/normal.png")
    try:
        m = np.asarray(Image.open(f"{bundle}/mask.png").convert("L")) > 127
        if m.shape != n.shape[:2]:
            m = cv2.resize(m.astype(np.uint8), (n.shape[1], n.shape[0]),
                           interpolation=cv2.INTER_NEAREST) > 0
    except FileNotFoundError:
        # magnitude-based foreground fallback
        m = np.abs(n[..., 2]) > 0.05
    return n, m


def noise_ratio(n, m):
    """High-freq energy vs total spatial variation of the normal field, in-mask."""
    lap = np.zeros_like(n)
    for c in range(3):
        lap[..., c] = cv2.Laplacian(n[..., c], cv2.CV_32F, ksize=3)
    hi = np.linalg.norm(lap, axis=-1)[m].mean()
    # total variation as a scale reference
    gx = np.abs(np.diff(n, axis=1)).sum(-1)[m[:, 1:]].mean()
    gy = np.abs(np.diff(n, axis=0)).sum(-1)[m[1:, :]].mean()
    return hi, (gx + gy)


def viz(n, m):
    rgb = ((n * 0.5 + 0.5) * 255).clip(0, 255).astype(np.uint8)
    rgb[~m] = 0
    lap = np.zeros(n.shape[:2], np.float32)
    for c in range(3):
        lap += np.abs(cv2.Laplacian(n[..., c], cv2.CV_32F, ksize=3))
    lap[~m] = 0
    lap = (lap / (lap.max() + 1e-6) * 255).astype(np.uint8)
    lap = cv2.applyColorMap(lap, cv2.COLORMAP_INFERNO)[..., ::-1]  # BGR->RGB
    lap[~m] = 0
    return rgb, lap


def main():
    rows = []
    print(f"{'bundle':52s} {'hi-freq':>8s} {'noise%':>7s}")
    for b in BUNDLES:
        try:
            n, m = load(b)
        except Exception as e:
            print(f"skip {b}: {e}")
            continue
        hi, tv = noise_ratio(n, m)
        pct = 100 * hi / (tv + 1e-6)
        print(f"{b.split('/')[-1]:52s} {hi:8.4f} {pct:6.1f}%")
        rgb, lap = viz(n, m)
        h = 260
        scale = h / rgb.shape[0]
        w = int(rgb.shape[1] * scale)
        rgb = cv2.resize(rgb, (w, h)); lap = cv2.resize(lap, (w, h))
        lbl = np.zeros((20, w, 3), np.uint8)
        cv2.putText(lbl, f"{b.split('/')[-1][:28]} noise={pct:.0f}%", (4, 15),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.42, (255, 255, 255), 1, cv2.LINE_AA)
        rows.append(np.vstack([lbl, rgb, lap]))
    W = max(r.shape[1] for r in rows)
    rows = [np.pad(r, ((0, 0), (0, W - r.shape[1]), (0, 0))) for r in rows]
    Image.fromarray(np.hstack(rows)).save("spikes/nmm_normal_diag_out.png")
    print("wrote spikes/nmm_normal_diag_out.png")


if __name__ == "__main__":
    main()
