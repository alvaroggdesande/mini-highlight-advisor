"""External photometric-stereo tool: capture frames -> validated bundle.

Runs in its OWN torch env (tools/requirements-ps.txt). NEVER imported by the app
(the app is torch-free). Emits normal.png + mask.png + report.txt; either a valid
bundle or a loud abort with a reason.

Usage:
  python tools/ps_tool.py --frames path/to/frames_dir \\
      --checkpoint path/to/checkpoint_dir --out path/to/out_dir

The --checkpoint argument must be the DIRECTORY containing the 'normal/' subdir
(i.e. the unzipped checkpoint/, not a .pytmodel file directly).

Output layout (out_dir/):
  normal.png   -- RGB-encoded unit normals in the PINNED convention:
                  R=x-right, G=y-up, B=z-toward-viewer; n = rgb/255*2-1
  mask.png     -- foreground mask (bool, same WxH as normal.png)
  report.txt   -- frames used/dropped, per-frame IoUs, lighting std; always
                  written even on abort so the gate can inspect failures.
"""
from __future__ import annotations

import argparse
import subprocess
import sys
import tempfile
from pathlib import Path

import cv2
import numpy as np
from PIL import Image

# ps_stages lives beside ps_tool (tools/ps_stages.py).  When run as
# `python tools/ps_tool.py` from the repo root, tools/ is NOT on sys.path.
# Insert it so the relative import works in both `python tools/ps_tool.py`
# and `python -m tools.ps_tool` invocations.
_TOOLS_DIR = Path(__file__).parent
if str(_TOOLS_DIR) not in sys.path:
    sys.path.insert(0, str(_TOOLS_DIR))

from ps_stages import (  # noqa: E402  (after sys.path fixup)
    CaptureError,
    align_to_reference,
    consensus_mask,
    encode_normals,
    select_frames,
)

MAX_SIDE = 512


# ---------------------------------------------------------------------------
# Frame loading
# ---------------------------------------------------------------------------

def _load_frames(frames_dir: Path):
    """Return (paths, frames) for all image files in frames_dir (sorted).

    All frames must share one HxW: the capture is a fixed camera with only the
    light moving, so a differing size means a stray non-frame file (contact sheet,
    thumbnail) landed in the folder. Fail loud naming it rather than crashing with
    an opaque broadcast error deep in frame selection.
    """
    paths = sorted(
        p for p in frames_dir.iterdir()
        if p.suffix.lower() in (".png", ".jpg", ".jpeg")
    )
    if not paths:
        raise CaptureError(f"No image files found in {frames_dir}")
    frames = [np.asarray(Image.open(p).convert("RGB")) for p in paths]
    ref_hw = frames[0].shape[:2]
    odd = [(p.name, f.shape[:2]) for p, f in zip(paths, frames)
           if f.shape[:2] != ref_hw]
    if odd:
        listing = ", ".join(f"{name} {hw[1]}x{hw[0]}" for name, hw in odd)
        raise CaptureError(
            f"frames are not all the same size: {paths[0].name} is "
            f"{ref_hw[1]}x{ref_hw[0]} but these differ: {listing}. The capture is "
            "a fixed camera (only the light moves), so every frame must match. "
            "Remove any non-capture files (contact sheets, thumbnails) from "
            f"{frames_dir} and re-run.")
    return paths, frames


# ---------------------------------------------------------------------------
# Per-frame masking (torch-env copy of masking.mask_from_grabcut + _largest_blob)
# ---------------------------------------------------------------------------
# Duplicated from src/mini_highlight_advisor/masking.py to avoid importing the
# app package into the torch env.  Keep in sync if masking.py changes.

def _largest_blob(binary: np.ndarray) -> np.ndarray:
    """Keep only the largest connected foreground region; close small holes."""
    n, labels, stats, _ = cv2.connectedComponentsWithStats(binary, connectivity=8)
    if n > 1:
        biggest = 1 + int(np.argmax(stats[1:, cv2.CC_STAT_AREA]))
        binary = np.where(labels == biggest, 255, 0).astype(np.uint8)
    binary = cv2.morphologyEx(binary, cv2.MORPH_CLOSE, np.ones((5, 5), np.uint8))
    return binary > 0


def _mask_one(rgb: np.ndarray, iters: int = 5, border: int = 8) -> np.ndarray:
    """GrabCut foreground mask for a single frame (returns bool array).

    Mirrors masking.mask_from_grabcut: border-inset rectangle seeds GrabCut;
    result is the largest connected component.  Assumes the mini is roughly
    centred and fills most of the frame.
    """
    h, w = rgb.shape[:2]
    bgr = cv2.cvtColor(rgb, cv2.COLOR_RGB2BGR)
    gc = np.zeros((h, w), dtype=np.uint8)
    bgd = np.zeros((1, 65), dtype=np.float64)
    fgd = np.zeros((1, 65), dtype=np.float64)
    b = min(border, max(0, min(h, w) // 2 - 1))
    rect = (b, b, max(1, w - 2 * b), max(1, h - 2 * b))
    cv2.grabCut(bgr, gc, rect, bgd, fgd, iters, cv2.GC_INIT_WITH_RECT)
    fg = np.isin(gc, (cv2.GC_FGD, cv2.GC_PR_FGD)).astype(np.uint8) * 255
    return _largest_blob(fg)


def _mask_each(frames) -> list[np.ndarray]:
    """Return a bool mask array for every frame."""
    return [_mask_one(f) for f in frames]


# ---------------------------------------------------------------------------
# Prepared-dir writer  (SDM-UniPS input layout)
# ---------------------------------------------------------------------------

def _write_prepared_dir(prepared: Path, a_frames: list[np.ndarray],
                        mask: np.ndarray) -> None:
    """Write frames + consensus mask into the SDM-UniPS input layout.

    Layout expected by SDM-UniPS:
        <prepared>/        (this IS the <object>.data dir)
            mask.png       -- foreground mask (uint8 0/255)
            L_01.png       -- first frame, downscaled to <= MAX_SIDE px on a side
            L_02.png
            ...

    Frames are downscaled to fit within MAX_SIDE x MAX_SIDE (aspect preserved)
    and written as uint8 PNG.  The mask is resized to match.
    """
    prepared.mkdir(parents=True, exist_ok=True)

    # Determine target size from first frame
    h0, w0 = a_frames[0].shape[:2]
    scale = min(1.0, MAX_SIDE / max(h0, w0))
    th, tw = max(1, int(round(h0 * scale))), max(1, int(round(w0 * scale)))

    # Write consensus mask (resized to match frame size)
    mask_u8 = (mask * 255).astype(np.uint8)
    if scale < 1.0:
        mask_u8 = cv2.resize(mask_u8, (tw, th), interpolation=cv2.INTER_NEAREST)
    Image.fromarray(mask_u8).save(prepared / "mask.png")

    # Write frames as L_01.png, L_02.png, ...
    for idx, frame in enumerate(a_frames, start=1):
        if scale < 1.0:
            frame_small = cv2.resize(
                cv2.cvtColor(frame, cv2.COLOR_RGB2BGR),
                (tw, th),
                interpolation=cv2.INTER_CUBIC,
            )
            frame_small = cv2.cvtColor(frame_small, cv2.COLOR_BGR2RGB)
        else:
            frame_small = frame
        fname = f"L_{idx:02d}.png"
        Image.fromarray(frame_small).save(prepared / fname)


# ---------------------------------------------------------------------------
# Convention flip
# ---------------------------------------------------------------------------

def _to_pinned_convention(normals: np.ndarray) -> np.ndarray:
    """Flip SDM-UniPS native convention -> pinned app convention.

    SDM-UniPS writes normals.png as BGR with the mapping
        R_sdm = x-right, G_sdm = y-DOWN, B_sdm = z-toward-viewer
    (evident from the spike's compare_ps_vs_luminance.py which uses
    L=[-0.35, -1.0, 0.65] — a NEGATIVE Y component — for a top light on
    raw SDM output, implying raw SDM has G=y-DOWN).

    The pinned app convention (relight.py) is:
        R=x-right, G=y-UP, B=z-toward-viewer.

    Therefore: flip the Y (green) component.

    # CONFIRM AT MANUAL GATE: round-trip
    #   spikes/phone_ps/run_black/results/black_aligned.data/normal.png
    # through relight.relight with a top light (L=[0,1,0]) and check that
    # highlights land on top-facing geometry.  If they appear on BOTTOM-facing
    # geometry instead, the flip is wrong — remove the negation below
    # (one-line fix, encode_normals will re-normalise).

    Input normals: (H, W, 3) float, any scale (encode_normals re-normalises).
    Returns: same shape float array with Y negated.
    """
    result = normals.copy()
    result[..., 1] = -result[..., 1]   # negate Y: y-DOWN -> y-UP
    return result


# ---------------------------------------------------------------------------
# SDM-UniPS inference via subprocess
# ---------------------------------------------------------------------------

def _build_sdm_cmd(prepared_dir, checkpoint, session_name, vendor_main) -> list:
    """Build the SDM-UniPS argv.

    The subprocess runs with cwd=vendor/sdm_unips (for SDM's relative imports), so
    any relative --checkpoint / --test_dir would resolve against the vendor dir,
    not the user's cwd -> 'Pretrained model not Found' / 'Found 0 objects!'.
    Absolutize both. SDM scans test_dir for *<test_ext> dirs; prepared_dir IS the
    .data dir, so its PARENT is test_dir.
    """
    test_dir = str(Path(prepared_dir).parent.resolve())
    return [
        sys.executable, str(vendor_main),
        "--session_name", str(session_name),
        "--target", "normal",
        "--checkpoint", str(Path(checkpoint).resolve()),
        "--test_dir", test_dir,
        "--test_ext", ".data",
        "--test_prefix", "L*",
        "--max_image_res", str(MAX_SIDE),
        "--canonical_resolution", "256",
    ]


def _run_sdm_unips(prepared_dir: Path, checkpoint: Path) -> np.ndarray:
    """Invoke vendored SDM-UniPS inference; return (H, W, 3) float normals.

    Returns: unit-normal array in SDM-UniPS native convention (pre-flip).
             Values in [-1, +1]; off-mask pixels are zero.

    Implementation choice — subprocess over direct import:
        SDM-UniPS's main.py uses `sys.path.append('..')` relative to its own
        location and wires everything through a module-level argparse.  Importing
        it as a library would require patching sys.path, monkeypatching argparse,
        and running __main__ code at import time — fragile.  Running it as a
        subprocess with cwd=vendor/sdm_unips faithfully reproduces the spike run
        (same sys.path semantics, same argparse flow) and is the safest bridge.

        SDM-UniPS writes its output to <session_name>/results/<objname>/normal.png.
        We use a temp session dir, read that file back, and decode it.

    Args:
        prepared_dir: path to the <object>.data dir (contains L_*.png + mask.png).
                      Its PARENT is used as `--test_dir` (SDM-UniPS scans for
                      *.data dirs inside test_dir).
        checkpoint:   path to the checkpoint DIRECTORY (contains normal/ subdir
                      with the .pytmodel file).
    """
    objname = prepared_dir.name  # e.g. "prepared.data"

    with tempfile.TemporaryDirectory() as session_tmp:
        session_name = str(Path(session_tmp) / "sdm_session")
        vendor_main = str(_TOOLS_DIR / "vendor" / "sdm_unips" / "main.py")

        cmd = _build_sdm_cmd(prepared_dir, checkpoint, session_name, vendor_main)

        print(f"[ps_tool] Running SDM-UniPS inference …")
        result = subprocess.run(
            cmd,
            cwd=str(_TOOLS_DIR / "vendor" / "sdm_unips"),
            capture_output=False,
            check=False,
        )
        if result.returncode != 0:
            raise RuntimeError(
                f"SDM-UniPS inference exited with code {result.returncode}. "
                "Check stdout above for details."
            )

        # SDM-UniPS writes: <session_name>/results/<objname>/normal.png
        normal_path = Path(session_name) / "results" / objname / "normal.png"
        if not normal_path.exists():
            raise RuntimeError(
                f"SDM-UniPS finished but normal.png not found at {normal_path}. "
                "Check SDM-UniPS stdout for errors."
            )

        # Decode SDM-UniPS's normal.png (written via cv2.imwrite as BGR):
        #   cv2.imwrite writes BGR, so channel 0 is B, 1 is G, 2 is R in file;
        #   Pillow reads it as RGB (R=0,G=1,B=2 in array).
        # SDM-UniPS writes: 255*(0.5*(1+nout[:,:,::-1])) where nout is (H,W,3)
        # with nout[...,0]=x, nout[...,1]=y, nout[...,2]=z (OpenGL-style xyz).
        # The [::-1] reverses the last dim before imwrite, turning XYZ→ZYX for
        # BGR storage.  cv2.imwrite(BGR) stores: B_ch=Z, G_ch=Y, R_ch=X.
        # Pillow loads as RGB: R=X, G=Y, B=Z — exactly the expected layout.
        #
        # Decode: n = rgb/255*2 - 1  (same formula as relight._decode)
        img = np.asarray(Image.open(normal_path).convert("RGB"), dtype=np.float32)
        normals = img / 255.0 * 2.0 - 1.0  # (H, W, 3) in [-1, 1]
        return normals


# ---------------------------------------------------------------------------
# Pre-flight checks (fail loud before any capture work)
# ---------------------------------------------------------------------------

class PreflightError(Exception):
    """Raised for a setup mistake (wrong env / bad checkpoint) before work starts."""


def _check_runtime_env() -> None:
    """The SDM-UniPS subprocess runs under sys.executable, so torch + einops +
    imageio must be importable from THIS interpreter. Running from the app's
    torch-free .venv is the #1 mistake; catch it here with a fix, not an
    einops ModuleNotFoundError deep in the vendored code."""
    import importlib.util

    missing = [m for m in ("torch", "einops", "imageio")
               if importlib.util.find_spec(m) is None]
    if missing:
        raise PreflightError(
            f"missing required module(s): {', '.join(missing)}. ps_tool must run "
            "from its OWN torch env, not the app's torch-free .venv.\n"
            f"  interpreter in use: {sys.executable}\n"
            "  fix (one-time):\n"
            "    python -m venv tools/.ps-venv\n"
            "    tools/.ps-venv/Scripts/pip install -r tools/requirements-ps.txt\n"
            "  then run with:  tools/.ps-venv/Scripts/python tools/ps_tool.py ...")


def _check_checkpoint(checkpoint: Path) -> None:
    """The --checkpoint arg must be the unzipped checkpoint DIRECTORY containing a
    normal/ subdir. Guards against the README placeholder path and pointing at a
    .pytmodel file or the wrong level."""
    if not checkpoint.is_dir():
        raise PreflightError(
            f"--checkpoint is not a directory: {checkpoint}\n"
            "  It must be the unzipped checkpoint/ directory (with a normal/ "
            "subdir), not a placeholder path or a .pytmodel file. "
            "See tools/README-ps.md for the download.")
    if not (checkpoint / "normal").is_dir():
        raise PreflightError(
            f"--checkpoint has no 'normal/' subdir: {checkpoint}\n"
            "  Point it at the unzipped checkpoint/ directory itself (which "
            "contains normal/), not a parent or child of it.")


def _preflight(checkpoint: Path) -> None:
    _check_runtime_env()
    _check_checkpoint(checkpoint)


# ---------------------------------------------------------------------------
# Main orchestration
# ---------------------------------------------------------------------------

def main() -> int:
    ap = argparse.ArgumentParser(
        description="Phone photometric stereo: frames dir -> normal.png/mask.png/report.txt"
    )
    ap.add_argument("--frames", required=True, type=Path,
                    help="Directory of capture frames (L_01.png … or any *.png/*.jpg).")
    ap.add_argument("--checkpoint", required=True, type=Path,
                    help="SDM-UniPS checkpoint DIRECTORY (contains normal/ subdir).")
    ap.add_argument("--out", required=True, type=Path,
                    help="Output directory; will be created if needed.")
    args = ap.parse_args()
    args.out.mkdir(parents=True, exist_ok=True)

    # Always write report.txt so the gate can inspect failures.
    report_path = args.out / "report.txt"

    try:
        # 0. Pre-flight: env + checkpoint sanity, before touching any frames.
        _preflight(args.checkpoint)

        # 1. Load raw frames
        paths, frames = _load_frames(args.frames)
        print(f"[ps_tool] Loaded {len(frames)} frames from {args.frames}")

        # 2. Per-frame GrabCut masks
        print("[ps_tool] Computing per-frame masks …")
        masks = _mask_each(frames)

        # 3. Quality gate: select frames by IoU + lighting-std (fail-loud)
        print("[ps_tool] Running frame selection …")
        kept, report = select_frames(frames, masks)

        # 4. Align kept frames to reference centroid
        a_frames, a_masks, _ = align_to_reference(
            [frames[i] for i in kept],
            [masks[i] for i in kept],
        )

        # 5. Consensus mask
        mask = consensus_mask(a_masks)

        # 6. Write prepared dir (SDM-UniPS input layout)
        prepared = args.out / "prepared.data"
        print(f"[ps_tool] Writing prepared dir: {prepared}")
        _write_prepared_dir(prepared, a_frames, mask)

        # 7. Run SDM-UniPS inference (subprocess into vendor/sdm_unips/)
        normals_sdm = _run_sdm_unips(prepared, args.checkpoint)   # (H,W,3), SDM convention

        # 8. Convention flip: SDM y-DOWN -> pinned y-UP
        normals = _to_pinned_convention(normals_sdm)               # still (H,W,3)

        # 9. Encode and write outputs
        # SDM-UniPS forces a square crop (canonical_resolution x canonical_resolution),
        # so normals may be (H, W) != prepared-frame dims.  Resize the consensus mask to
        # match so that normal.png and mask.png are guaranteed identical WxH (required by
        # the app's import validation).
        sdm_h, sdm_w = normals.shape[:2]
        mask_u8 = (mask * 255).astype(np.uint8)
        mask_u8 = cv2.resize(mask_u8, (sdm_w, sdm_h), interpolation=cv2.INTER_NEAREST)

        Image.fromarray(encode_normals(normals)).save(args.out / "normal.png")
        Image.fromarray(mask_u8).save(args.out / "mask.png")

        report_path.write_text(
            f"frames used: {[paths[i].name for i in kept]}\n"
            f"dropped: {[paths[i].name for i in report['dropped']]}\n"
            f"ious: {[round(v, 3) for v in report['ious']]}\n"
            f"lighting std: {report['lighting_std']:.1f}\n"
        )
        print(f"[ps_tool] Bundle written to {args.out}")
        return 0

    except PreflightError as e:
        report_path.write_text(f"PREFLIGHT: {e}\n")
        print(f"[ps_tool] PREFLIGHT FAILED: {e}", file=sys.stderr)
        return 3

    except CaptureError as e:
        report_path.write_text(f"ABORT: {e}\n")
        print(f"[ps_tool] ABORT: {e}", file=sys.stderr)
        return 2

    except Exception as e:
        report_path.write_text(f"ERROR: {e}\n")
        print(f"[ps_tool] ERROR: {e}", file=sys.stderr)
        raise


if __name__ == "__main__":
    raise SystemExit(main())
