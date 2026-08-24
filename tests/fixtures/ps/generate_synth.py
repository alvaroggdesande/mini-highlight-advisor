"""Deterministic generator for the PS synthetic fixture (dome + 2 ridges).
Run once; the two PNGs it writes are committed. No randomness, no torch.
Run: .venv/Scripts/python tests/fixtures/ps/generate_synth.py
"""
from pathlib import Path
import numpy as np
from PIL import Image

H = W = 128
cy = cx = 63.5
R = 50.0
here = Path(__file__).parent

yy, xx = np.mgrid[0:H, 0:W].astype(np.float32)
dx = (xx - cx) / R
dy = (yy - cy) / R
r2 = dx * dx + dy * dy
mask = r2 <= 1.0

# Dome normals: x-right, y-UP (image row grows downward, so up = -dy), z-toward-viewer.
nx = dx
ny = -dy
nz = np.sqrt(np.clip(1.0 - r2, 0.0, 1.0))

# Two ridges: tilt the surface locally so banding has crisp travel to lock onto.
ridge = ((np.abs(xx - 40) < 3) | (np.abs(xx - 88) < 3)) & mask
nx = np.where(ridge, 0.6, nx)
nz = np.where(ridge, np.sqrt(np.clip(1.0 - nx**2 - ny**2, 0.0, 1.0)), nz)

n = np.stack([nx, ny, nz], axis=-1).astype(np.float32)
n[~mask] = np.array([0.0, 0.0, 1.0], np.float32)      # background = flat facing viewer
norm = np.linalg.norm(n, axis=-1, keepdims=True)
n = n / np.clip(norm, 1e-6, None)

rgb = np.clip((n + 1.0) * 0.5 * 255.0, 0, 255).astype(np.uint8)
Image.fromarray(rgb).save(here / "synth_normal.png")
Image.fromarray((mask * 255).astype(np.uint8)).save(here / "synth_mask.png")
print("wrote synth_normal.png + synth_mask.png")
