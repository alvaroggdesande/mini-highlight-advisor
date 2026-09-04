"""Tweak 3: edge-preserving (bilateral) smoothing vs Gaussian for NMM.

Does bilateral denoise the flats while keeping form edges — escaping the
speckle<->mud trap? Renders raw / gaussian / bilateral side by side on a real
necron bundle, Chrome preset (matches the screenshot).
"""
import numpy as np
from PIL import Image
import cv2

from mini_highlight_advisor import materials, relight
from mini_highlight_advisor.banding import band_by_value

BUNDLE = "spikes/phone_ps/data/necron_overlord_painted_front.out"
N_BANDS = 5
PRESET = materials.NMM_PRESETS["Chrome"]

STEEL = np.array([
    [0.10, 0.10, 0.12], [0.32, 0.34, 0.38], [0.55, 0.58, 0.62],
    [0.78, 0.81, 0.85], [0.97, 0.98, 1.00],
], dtype=np.float32)


def renorm(n, mask):
    mag = np.linalg.norm(n, axis=-1, keepdims=True)
    mag[mag == 0] = 1.0
    out = (n / mag).astype(np.float32)
    out[~mask] = n[~mask]
    return out


def gaussian(n, mask, sigma):
    mf = mask.astype(np.float32)
    num = cv2.GaussianBlur(n * mf[..., None], (0, 0), sigma)
    den = cv2.GaussianBlur(mf, (0, 0), sigma)[..., None] + 1e-6
    return renorm(num / den, mask)


def bilateral(n, mask, d, sc, ss):
    # bilateralFilter on the 3-channel float normal field; edges (big normal
    # jumps) are preserved, flats are averaged.
    f = cv2.bilateralFilter(n.astype(np.float32), d, sc, ss)
    f[~mask] = n[~mask]
    return renorm(f, mask)


def render(n, mask):
    env = materials.build_nmm_env(**PRESET)
    light = materials.nmm_light(n, mask, env=env)
    bands = band_by_value(light, mask, n_bands=N_BANDS)
    out = np.zeros((*mask.shape, 3), np.float32)
    for b in range(N_BANDS):
        out[bands == b] = STEEL[b]
    out[~mask] = 0.0
    return (out * 255).astype(np.uint8)


def main():
    n = relight.load_normals(f"{BUNDLE}/normal.png")
    mask = np.asarray(Image.open(f"{BUNDLE}/mask.png").convert("L")) > 127
    if mask.shape != n.shape[:2]:
        mask = cv2.resize(mask.astype(np.uint8), (n.shape[1], n.shape[0]),
                          interpolation=cv2.INTER_NEAREST) > 0

    variants = [
        ("raw", n),
        ("gaussian s2", gaussian(n, mask, 2.0)),
        ("bilateral d9 sc0.15", bilateral(n, mask, 9, 0.15, 9)),
        ("bilateral d13 sc0.30", bilateral(n, mask, 13, 0.30, 13)),
    ]
    tiles = []
    for name, nn in variants:
        img = render(nn, mask)
        lbl = np.zeros((22, img.shape[1], 3), np.uint8)
        cv2.putText(lbl, name, (6, 16), cv2.FONT_HERSHEY_SIMPLEX, 0.5,
                    (255, 255, 255), 1, cv2.LINE_AA)
        tiles.append(np.vstack([lbl, img]))
    Image.fromarray(np.hstack(tiles)).save("spikes/nmm_bilateral_probe_out.png")
    print("wrote spikes/nmm_bilateral_probe_out.png")


if __name__ == "__main__":
    main()
