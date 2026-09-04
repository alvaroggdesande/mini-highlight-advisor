"""Offline probe: does smoothing the normal field rescue NMM v2 from speckle?

Renders the real black-primer normal bundle through the NMM path with several
normal-smoothing sigmas, side by side. No Streamlit, no torch. Throwaway.
"""
import numpy as np
from PIL import Image
import cv2

from mini_highlight_advisor import materials, relight
from mini_highlight_advisor.banding import band_by_value

BUNDLE = "spikes/phone_ps/data/black_output"
N_BANDS = 5
PRESET = materials.NMM_PRESETS["Gold"]

# gold metal ramp, dark -> glint (RGB 0..1), N_BANDS steps
GOLD = np.array([
    [0.12, 0.09, 0.04],
    [0.45, 0.32, 0.10],
    [0.72, 0.55, 0.20],
    [0.90, 0.78, 0.38],
    [1.00, 0.96, 0.75],
], dtype=np.float32)


def smooth_normals(normals, mask, sigma):
    if sigma <= 0:
        return normals
    m = mask.astype(np.float32)[..., None]
    num = cv2.GaussianBlur(normals * m, (0, 0), sigma)
    den = cv2.GaussianBlur(mask.astype(np.float32), (0, 0), sigma)[..., None] + 1e-6
    sm = num / den
    n = np.linalg.norm(sm, axis=-1, keepdims=True)
    n[n == 0] = 1.0
    sm = (sm / n).astype(np.float32)
    sm[~mask] = 0.0
    return sm


def render(normals, mask):
    env = materials.build_nmm_env(horizon=PRESET["horizon"], light_dir=PRESET["light_dir"],
                                  bounce=PRESET["bounce"], hotspot=PRESET["hotspot"])
    light = materials.nmm_light(normals, mask, env=env)
    bands = band_by_value(light, mask, n_bands=N_BANDS)
    out = np.zeros((*mask.shape, 3), np.float32)
    for b in range(N_BANDS):
        out[bands == b] = GOLD[b]
    out[~mask] = 0.0
    return (out * 255).astype(np.uint8), light


def main():
    normals = relight.load_normals(f"{BUNDLE}/normal.png")
    mask = np.asarray(Image.open(f"{BUNDLE}/mask.png").convert("L")) > 127
    if mask.shape != normals.shape[:2]:
        mask = cv2.resize(mask.astype(np.uint8), (normals.shape[1], normals.shape[0]),
                          interpolation=cv2.INTER_NEAREST) > 0

    sigmas = [0.0, 1.5, 3.0, 6.0]
    tiles = []
    for s in sigmas:
        sm = smooth_normals(normals, mask, s)
        img, _ = render(sm, mask)
        # label strip
        lbl = np.zeros((22, img.shape[1], 3), np.uint8)
        cv2.putText(lbl, f"sigma={s}", (6, 16), cv2.FONT_HERSHEY_SIMPLEX,
                    0.5, (255, 255, 255), 1, cv2.LINE_AA)
        tiles.append(np.vstack([lbl, img]))
    strip = np.hstack(tiles)
    Image.fromarray(strip).save("spikes/nmm_smooth_probe_out.png")
    print("wrote spikes/nmm_smooth_probe_out.png", strip.shape)


if __name__ == "__main__":
    main()
