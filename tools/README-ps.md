# Phone Photometric Stereo Tool

Turns a set of phone-captured frames (mini lit from different angles) into a
validated normal-map bundle (`normal.png` + `mask.png` + `report.txt`) that the
app's `relight.py` consumes.

**This tool runs in a separate torch environment.**
Torch is deliberately excluded from the app's `.venv` (keeping the Streamlit app
light and torch-free).  Everything under `tools/` is the heavy offline pipeline.

---

## Attribution

Vendored inference: **SDM-UniPS** (Scalable, Detailed and Mask-free Universal
Photometric Stereo Network), Satoshi Ikehata, CVPR 2023.
License: see `tools/vendor/sdm_unips/LICENSE`.

> Ikehata, S. (2023). SDM-UniPS: Scalable, Detailed and Mask-free Universal
> Photometric Stereo. *Proceedings of the IEEE/CVF Conference on Computer Vision
> and Pattern Recognition (CVPR)*.

The vendored copy in `tools/vendor/sdm_unips/` is a verbatim copy of the
original source with **one committed patch**: in
`modules/model/model_utils.py:loadmodel`, `torch.load` is called with
`map_location=torch.device('cpu')` so a CUDA-saved checkpoint loads on CPU-only
machines.  No other source modifications have been made.

---

## One-time setup

### 1. Create the ps-venv (separate from the app's `.venv`)

```bash
python -m venv tools/.ps-venv
tools/.ps-venv/Scripts/pip install -r tools/requirements-ps.txt
```

The venv is gitignored (`tools/.ps-venv/`).  Torch (~2 GB) installs here only.

### 2. Download the checkpoint (445 MB, one-time)

```bash
# Download checkpoint.zip from the SDM-UniPS Dropbox link:
curl -L "https://www.dropbox.com/s/yu8h6g0zp07mumd/checkpoint.zip?dl=1" \
     -o checkpoint.zip
unzip checkpoint.zip          # produces a checkpoint/ dir with normal/ subdir
rm checkpoint.zip
```

Store the unzipped `checkpoint/` directory anywhere convenient — it is
gitignored (`tools/**/checkpoint*`, `*.pytmodel`).

---

## Usage

```bash
tools/.ps-venv/Scripts/python tools/ps_tool.py \
    --frames  path/to/frames_dir \
    --checkpoint path/to/checkpoint \
    --out     path/to/out_dir
```

| Argument | Description |
|---|---|
| `--frames` | Directory containing capture frames (`*.png` / `*.jpg`). Name them `L_01.png … L_NN.png` or any sorted order. |
| `--checkpoint` | The unzipped checkpoint **directory** (contains a `normal/` subdir with the `.pytmodel` file). |
| `--out` | Output directory (created if absent). Receives `normal.png`, `mask.png`, `report.txt`. |

### Example (black-primer test data from the spike)

```bash
tools/.ps-venv/Scripts/python tools/ps_tool.py \
    --frames spikes/phone_ps/data/black.data \
    --checkpoint /path/to/checkpoint \
    --out /tmp/ps_out
```

Exit codes: `0` = success, `2` = capture quality abort (see `report.txt`),
non-zero = inference error.

---

## Output contract

| File | Description |
|---|---|
| `normal.png` | RGB-encoded unit normals. Pinned convention: R=x-right, G=y-**up**, B=z-toward-viewer. Decode: `n = rgb/255 * 2 − 1`. |
| `mask.png` | Foreground mask (uint8, 0/255). Same width × height as `normal.png`. |
| `report.txt` | Frames used/dropped, per-frame IoUs, lighting std. Always written even on abort. |

---

## Pipeline overview

1. Load frames from `--frames`.
2. Per-frame GrabCut foreground mask (border-inset rect + largest blob).
3. Quality gate (`ps_stages.select_frames`): IoU ≥ 0.9, lighting std ≥ 8.0, min 4 frames.
4. Align kept frames to reference centroid (`ps_stages.align_to_reference`).
5. Consensus mask (`ps_stages.consensus_mask`).
6. Downscale frames to ≤ 512 px; write `prepared.data/` (SDM-UniPS input layout).
7. Run vendored SDM-UniPS inference (subprocess into `tools/vendor/sdm_unips/main.py`).
8. Convention flip: SDM native y-DOWN → pinned y-UP (negate green channel).
9. Encode normals (`ps_stages.encode_normals`) and write outputs.

### Convention flip note

SDM-UniPS saves normals with G=y-**down** (confirmed by the spike's
`compare_ps_vs_luminance.py` using `L=[−0.35, −1.0, 0.65]` — a negative-Y
vector — for a top light on raw SDM output).  `ps_tool.py::_to_pinned_convention`
negates the Y channel to reach G=y-up.  **Confirm at manual gate** by
round-tripping the staircase output through `relight.relight` under a top light
`L=[0, 1, 0]` and checking highlights land on top-facing geometry.

---

## What is gitignored

```
tools/.ps-venv/       # the separate torch venv
tools/**/checkpoint*  # the 445 MB model checkpoint
*.pytmodel            # model weight files
```
