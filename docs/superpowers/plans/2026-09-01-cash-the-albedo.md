# Cash the Albedo Implementation Plan

> **STATUS: SHIPPED** — merged to main PR #28 (feat/cash-the-albedo). Commits: `4b9a813` (relight), `bbda416` (ps_tool), `39708af` (ui).

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Export `albedo.png` from `ps_tool` always, and consume it in `relight.py` so the PS display base shows actual paint colours instead of flat grey.

**Architecture:** SDM-UniPS already recovers a diffuse colour map (`baseColor.png`) when `--target normal_and_brdf` is used — both checkpoints ship in `checkpoint/`. `ps_tool` is changed to always request BRDF and always export `albedo.png`. `relight.relight()` gains an optional `albedo` param; when present the relit base is `albedo × shading` (coloured); when absent it falls back to `ALBEDO_constant × shading` (grey, byte-identical to today). `ps_mode.py` gains a third optional uploader for `albedo.png` and passes it through to `relight()`. Banding, pipeline, and overlay are untouched — only the display base changes.

**Tech Stack:** Python 3.11, numpy, Pillow, Streamlit; pytest. All app code is torch-free.

**Spec:** `docs/superpowers/specs/2026-09-01-cash-the-albedo-design.md`

## Global Constraints

- **Path L byte-identical:** `relight(albedo=None)` must produce output identical to the current grey path. Every task that touches `relight` carries a regression assertion.
- **Bundle backwards compat:** three-file bundles (no `albedo.png`) load and work as before; `albedo.png` is an optional fourth file.
- **Torch-free app:** albedo consumed in the app is a plain numpy array loaded with Pillow; no torch anywhere in `src/` or `ui/`.
- **No banding/pipeline change:** `light_field` (n·l) is geometry-driven; albedo affects only the display base passed as `rgb` to `analyze_regions`.
- **Branch:** work on `feat/cash-the-albedo`; never commit straight to `main`.
- **Run tests with:** `.venv/Scripts/python -m pytest`

---

### Task 1: `relight.py` — `load_albedo`, `plausible_albedo`, `relight(albedo=)`

**Files:**
- Modify: `src/mini_highlight_advisor/relight.py`
- Test: `tests/test_relight.py` (append new tests)

**Interfaces:**
- Produces:
  - `load_albedo(path: str) -> np.ndarray` — `(H,W,3) float32` in `[0,1]`, RGB
  - `plausible_albedo(albedo: np.ndarray, mask: np.ndarray) -> bool` — defence against garbage imports
  - `relight(normals, mask, light, albedo=None) -> tuple[np.ndarray, np.ndarray]` — unchanged signature except new kwarg; second return is `(H,W,3) uint8` (was grey, now coloured when albedo present)

- [ ] **Step 1: Write the failing tests**

Append to `tests/test_relight.py`:

```python
def test_relight_no_albedo_is_grey_byte_identical():
    # Regression lock: albedo=None must match the current ALBEDO-constant path.
    m = np.ones((8, 8), bool)
    normals = np.zeros((8, 8, 3), np.float32); normals[..., 2] = 1.0
    light = relight.light_dir(0, 90)
    lf1, base1 = relight.relight(normals, m, light)
    lf2, base2 = relight.relight(normals, m, light, albedo=None)
    np.testing.assert_array_equal(base1, base2)


def test_relight_with_albedo_colours_the_base():
    # A red albedo must produce a red-tinted base, not grey.
    m = np.ones((8, 8), bool)
    normals = np.zeros((8, 8, 3), np.float32); normals[..., 2] = 1.0
    albedo = np.zeros((8, 8, 3), np.float32); albedo[..., 0] = 1.0   # pure red
    lf, base = relight.relight(normals, m, relight.light_dir(0, 90), albedo=albedo)
    # Red channel should be non-zero; green and blue must be zero on-mask
    assert base[m, 0].mean() > 0
    assert np.all(base[m, 1] == 0)
    assert np.all(base[m, 2] == 0)


def test_relight_with_albedo_off_mask_is_zero():
    m = np.zeros((8, 8), bool); m[2:6, 2:6] = True
    normals = np.zeros((8, 8, 3), np.float32); normals[..., 2] = 1.0
    albedo = np.ones((8, 8, 3), np.float32) * 0.5
    lf, base = relight.relight(normals, m, relight.light_dir(0, 90), albedo=albedo)
    assert np.all(base[~m] == 0)


def test_relight_albedo_shape_mismatch_raises():
    normals = np.zeros((8, 8, 3), np.float32); normals[..., 2] = 1.0
    m = np.ones((8, 8), bool)
    wrong_albedo = np.ones((4, 4, 3), np.float32)
    try:
        relight.relight(normals, m, relight.light_dir(0, 90), albedo=wrong_albedo)
        assert False, "expected ValueError"
    except ValueError:
        pass


def test_load_albedo_returns_float32_in_0_1(tmp_path):
    # Write a synthetic RGB PNG, load it back, check dtype and range.
    arr = np.array([[[200, 100, 50]]], dtype=np.uint8)
    from PIL import Image as PILImage
    PILImage.fromarray(arr).save(tmp_path / "albedo.png")
    out = relight.load_albedo(str(tmp_path / "albedo.png"))
    assert out.dtype == np.float32
    assert out.shape == (1, 1, 3)
    assert np.allclose(out[0, 0], [200/255, 100/255, 50/255], atol=1/255)


def test_plausible_albedo_accepts_reasonable():
    m = np.ones((8, 8), bool)
    albedo = np.ones((8, 8, 3), np.float32) * 0.5
    assert relight.plausible_albedo(albedo, m) is True


def test_plausible_albedo_rejects_all_zero_foreground():
    m = np.ones((8, 8), bool)
    albedo = np.zeros((8, 8, 3), np.float32)   # all black
    assert relight.plausible_albedo(albedo, m) is False


def test_plausible_albedo_rejects_wrong_shape():
    m = np.ones((8, 8), bool)
    albedo = np.ones((8, 8), np.float32)        # missing channel dim
    assert relight.plausible_albedo(albedo, m) is False
```

- [ ] **Step 2: Run tests to verify they fail**

```
.venv/Scripts/python -m pytest tests/test_relight.py -k "albedo or plausible_albedo or load_albedo" -v
```
Expected: FAIL with `AttributeError` (`load_albedo`, `plausible_albedo` not yet defined) and `TypeError` (`relight()` doesn't accept `albedo` kwarg).

- [ ] **Step 3: Implement in `relight.py`**

Add `load_albedo` and `plausible_albedo` after `plausible_unit_normals`. Change `relight()` to accept `albedo=None`:

```python
def load_albedo(path: str) -> np.ndarray:
    """PNG albedo map (baseColor.png from ps_tool) -> (H,W,3) float32 in [0,1], RGB."""
    return np.asarray(Image.open(path).convert("RGB"), dtype=np.float32) / 255.0


def plausible_albedo(albedo: np.ndarray, mask: np.ndarray) -> bool:
    """Defence against importing a garbage PNG as an albedo map.

    Returns True only when albedo is (H,W,3) with the same spatial dims as mask
    and at least some non-zero foreground pixels (a fully-black foreground on a
    non-black mini is suspicious — more likely a wrong file than real albedo).
    """
    if albedo.ndim != 3 or albedo.shape[2] != 3:
        return False
    if albedo.shape[:2] != mask.shape:
        return False
    fg = albedo[mask]
    if not fg.size:
        return False
    return bool(fg.max() > 0.02)


def relight(normals: np.ndarray, mask: np.ndarray, light: np.ndarray,
            albedo: np.ndarray | None = None):
    """Diffuse relight. Returns (light_field, relit_rgb).

    light_field: (H,W) float32 in [0,1], off-mask 0 — the banding light source.
    relit_rgb:   (H,W,3) uint8, off-mask 0 — the display base overlays draw on.
                 When albedo is provided: coloured (albedo × shading).
                 When albedo is None:     grey (ALBEDO_constant × shading), byte-
                                          identical to the previous behaviour.
    albedo must have the same (H,W) as normals; raises ValueError on mismatch.
    """
    if albedo is not None and albedo.shape[:2] != normals.shape[:2]:
        raise ValueError(
            f"albedo shape {albedo.shape[:2]} != normals shape {normals.shape[:2]}")
    light_field = np.clip(normals @ light, 0.0, 1.0).astype(np.float32)
    light_field[~mask] = 0.0
    shading = AMBIENT + (1.0 - AMBIENT) * light_field          # (H,W) in [0,1]
    if albedo is not None:
        colour = albedo * shading[..., np.newaxis]             # (H,W,3) float32
    else:
        colour = np.full((*mask.shape, 3), ALBEDO, dtype=np.float32) * shading[..., np.newaxis]
    colour8 = np.clip(colour * 255.0, 0, 255).astype(np.uint8)
    colour8[~mask] = 0
    return light_field, colour8
```

- [ ] **Step 4: Run the new tests**

```
.venv/Scripts/python -m pytest tests/test_relight.py -v
```
Expected: all tests PASS (new + existing — `relight(albedo=None)` is byte-identical to before).

- [ ] **Step 5: Commit**

```
git add src/mini_highlight_advisor/relight.py tests/test_relight.py
git commit -m "feat(relight): load_albedo + plausible_albedo + relight(albedo=) coloured base"
```

---

### Task 2: `ps_tool.py` — drop spike flag, always-on BRDF, `albedo.png` in bundle

**Files:**
- Modify: `tools/ps_tool.py`
- Modify: `tests/test_ps_tool_sdm_cmd.py` (update target assertion)
- Modify: `tests/test_ps_tool_preflight.py` (add `brdf/` checkpoint check)

**Interfaces:**
- Consumes: nothing new (internal cleanup)
- Produces: `args.out / "albedo.png"` always written alongside `normal.png` + `mask.png`; `_check_checkpoint` also validates `checkpoint/brdf/`

- [ ] **Step 1: Update the existing sdm_cmd test for the new target**

In `tests/test_ps_tool_sdm_cmd.py`, add an assertion that the target is now `normal_and_brdf`. The existing tests don't check `--target` explicitly — add one:

```python
def test_sdm_cmd_target_is_normal_and_brdf():
    cmd = ps_tool._build_sdm_cmd(
        Path("out/prepared.data"), Path("ckpt"), "/abs/session", "/abs/main.py")
    assert _arg(cmd, "--target") == "normal_and_brdf"
```

Run to verify it **fails** (current target is `"normal"`):
```
.venv/Scripts/python -m pytest tests/test_ps_tool_sdm_cmd.py::test_sdm_cmd_target_is_normal_and_brdf -v
```

- [ ] **Step 2: Write the new checkpoint test**

Append to `tests/test_ps_tool_preflight.py`:

```python
def test_checkpoint_check_rejects_dir_without_brdf_subdir(tmp_path):
    ckpt = tmp_path / "checkpoint"
    (ckpt / "normal").mkdir(parents=True)   # normal/ present, brdf/ absent
    with pytest.raises(PreflightError, match="brdf"):
        ps_tool._check_checkpoint(ckpt)


def test_checkpoint_check_accepts_dir_with_both_subdirs(tmp_path):
    ckpt = tmp_path / "checkpoint"
    (ckpt / "normal").mkdir(parents=True)
    (ckpt / "brdf").mkdir(parents=True)
    ps_tool._check_checkpoint(ckpt)   # no raise
```

Run to verify the first new test **fails** (current `_check_checkpoint` only checks `normal/`):
```
.venv/Scripts/python -m pytest tests/test_ps_tool_preflight.py -v
```
Expected: `test_checkpoint_check_rejects_dir_without_brdf_subdir` FAILS (no raise currently).

- [ ] **Step 3: Clean up spike code in `ps_tool.py`**

Make the following changes:

**`_build_sdm_cmd`** — remove `brdf` parameter, hardcode `normal_and_brdf`:
```python
def _build_sdm_cmd(prepared_dir, checkpoint, session_name, vendor_main) -> list:
    test_dir = str(Path(prepared_dir).parent.resolve())
    return [
        sys.executable, str(vendor_main),
        "--session_name", str(session_name),
        "--target", "normal_and_brdf",
        "--checkpoint", str(Path(checkpoint).resolve()),
        "--test_dir", test_dir,
        "--test_ext", ".data",
        "--test_prefix", "L*",
        "--max_image_res", str(MAX_SIDE),
        "--canonical_resolution", "256",
    ]
```

**`_run_sdm_unips`** — remove `brdf` parameter, always read `baseColor.png`, always return `(normals, albedo)`:
```python
def _run_sdm_unips(prepared_dir: Path, checkpoint: Path):
    """Invoke vendored SDM-UniPS inference; return (normals, albedo).

    normals: (H,W,3) float32 unit normals in SDM-UniPS native convention (pre-flip).
    albedo:  (H,W,3) float32 diffuse colour in [0,1] RGB, or None if baseColor.png
             was not produced (defensive — should not happen with normal_and_brdf).
    """
    objname = prepared_dir.name

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

        results_dir = Path(session_name) / "results" / objname
        normal_path = results_dir / "normal.png"
        if not normal_path.exists():
            raise RuntimeError(
                f"SDM-UniPS finished but normal.png not found at {normal_path}. "
                "Check SDM-UniPS stdout for errors."
            )

        # Decode normals (see existing encoding comment for full details)
        img = np.asarray(Image.open(normal_path).convert("RGB"), dtype=np.float32)
        normals = img / 255.0 * 2.0 - 1.0

        # Decode albedo: baseColor.png is written by SDM via cv2.imwrite (BGR);
        # Pillow reads it as RGB — no channel flip needed, just / 255 decode.
        albedo = None
        bc_path = results_dir / "baseColor.png"
        if bc_path.exists():
            albedo = np.asarray(Image.open(bc_path).convert("RGB"),
                                dtype=np.float32) / 255.0
            print(f"[ps_tool] albedo recovered — mean RGB {albedo.mean(axis=(0,1)).round(3)}")
        else:
            print("[ps_tool] WARNING: baseColor.png not produced — albedo will be absent")

        return normals, albedo
```

**`_check_checkpoint`** — add `brdf/` check:
```python
def _check_checkpoint(checkpoint: Path) -> None:
    if not checkpoint.exists() or not checkpoint.is_dir():
        raise PreflightError(
            f"--checkpoint does not exist or is not a directory: {checkpoint}\n"
            "  Point it at the unzipped checkpoint/ directory itself (which "
            "contains normal/ and brdf/), not a parent or child of it.")
    if not (checkpoint / "normal").is_dir():
        raise PreflightError(
            f"--checkpoint has no 'normal/' subdir: {checkpoint}\n"
            "  It must be the unzipped checkpoint/ directory (which "
            "contains normal/), not a parent or child of it.")
    if not (checkpoint / "brdf").is_dir():
        raise PreflightError(
            f"--checkpoint has no 'brdf/' subdir: {checkpoint}\n"
            "  The BRDF checkpoint is required (ps_tool always runs normal_and_brdf). "
            "  It must be the unzipped checkpoint/ directory (which contains both "
            "  normal/ and brdf/).")
```

**`main()`** — remove `--brdf` arg, always write `albedo.png`, update unpacking:
```python
def main() -> int:
    ap = argparse.ArgumentParser(
        description="Phone photometric stereo: frames dir -> normal.png/mask.png/albedo.png/report.txt"
    )
    ap.add_argument("--frames", required=True, type=Path, ...)
    ap.add_argument("--checkpoint", required=True, type=Path, ...)
    ap.add_argument("--out", required=True, type=Path, ...)
    args = ap.parse_args()
    args.out.mkdir(parents=True, exist_ok=True)
    report_path = args.out / "report.txt"

    try:
        _preflight(args.checkpoint)

        paths, frames = _load_frames(args.frames)
        print(f"[ps_tool] Loaded {len(frames)} frames from {args.frames}")

        masks = _mask_each(frames)
        kept, report = select_frames(frames, masks)
        a_frames, a_masks, _ = align_to_reference(
            [frames[i] for i in kept], [masks[i] for i in kept])
        mask = consensus_mask(a_masks)

        prepared = args.out / "prepared.data"
        print(f"[ps_tool] Writing prepared dir: {prepared}")
        _write_prepared_dir(prepared, a_frames, mask)

        normals_sdm, albedo = _run_sdm_unips(prepared, args.checkpoint)
        normals = _to_pinned_convention(normals_sdm)

        sdm_h, sdm_w = normals.shape[:2]
        mask_u8 = (mask * 255).astype(np.uint8)
        mask_u8 = cv2.resize(mask_u8, (sdm_w, sdm_h), interpolation=cv2.INTER_NEAREST)

        Image.fromarray(encode_normals(normals)).save(args.out / "normal.png")
        Image.fromarray(mask_u8).save(args.out / "mask.png")
        if albedo is not None:
            albedo_u8 = np.clip(albedo * 255, 0, 255).astype(np.uint8)
            Image.fromarray(albedo_u8).save(args.out / "albedo.png")

        report_path.write_text(
            f"frames used: {[paths[i].name for i in kept]}\n"
            f"dropped: {[paths[i].name for i in report['dropped']]}\n"
            f"ious: {[round(v, 3) for v in report['ious']]}\n"
            f"lighting std: {report['lighting_std']:.1f}\n"
        )
        print(f"[ps_tool] Bundle written to {args.out}")
        return 0
    # ... existing except blocks unchanged
```

Also update the module docstring's "Output layout" section to include `albedo.png`.

- [ ] **Step 4: Run all ps_tool tests**

```
.venv/Scripts/python -m pytest tests/test_ps_tool_sdm_cmd.py tests/test_ps_tool_preflight.py tests/test_ps_stages.py tests/test_ps_tool_load_frames.py -v
```
Expected: all PASS (new target + brdf checkpoint assertions now pass; existing tests unaffected since `_build_sdm_cmd` signature lost the `brdf` param but existing callers in tests only use 4 positional args and the new function still takes 4).

- [ ] **Step 5: Commit**

```
git add tools/ps_tool.py tests/test_ps_tool_sdm_cmd.py tests/test_ps_tool_preflight.py
git commit -m "feat(ps_tool): always-on BRDF — export albedo.png; harden _check_checkpoint for brdf/"
```

---

### Task 3: `ui/` — `keys.ALBEDO`, PS import reads albedo, threads to `relight()`

**Files:**
- Modify: `ui/keys.py` (add `ALBEDO`)
- Modify: `ui/ps_mode.py` (`_import_gate` reads optional albedo; `render` passes it to `relight`)
- Modify: `tests/test_ui_keys.py` (freeze `ALBEDO`)
- Create: `tests/test_ui_ps_albedo.py` (AppTest for with/without albedo)

**Interfaces:**
- Consumes: `relight.load_albedo` + `relight.plausible_albedo` (Task 1); `keys.ALBEDO` (this task)
- Produces: `st.session_state[keys.ALBEDO]` = `(H,W,3) float32` or `None`; `relight.relight(albedo=...)` receives it; display base is coloured when present

- [ ] **Step 1: Add `ALBEDO` key and freeze it in the test**

In `ui/keys.py`, add inside the `# --- photometric-stereo (PS) mode ---` block:
```python
PS_ALBEDO = "ps_albedo"              # (H,W,3) float32 albedo from imported bundle, or None
```

Append to `tests/test_ui_keys.py`:
```python
def test_ps_albedo_key_is_frozen():
    assert keys.PS_ALBEDO == "ps_albedo"
```

Run:
```
.venv/Scripts/python -m pytest tests/test_ui_keys.py -v
```
Expected: new test PASSES immediately (it's a string constant).

- [ ] **Step 2: Write the failing AppTests**

Create `tests/test_ui_ps_albedo.py`:

```python
"""AppTest coverage for PS mode with and without albedo.png in the imported bundle."""
import numpy as np
from pathlib import Path
from PIL import Image
from streamlit.testing.v1 import AppTest

FIX = Path("tests/fixtures/ps")

# Harness with albedo: pre-seeds NORMALS + PS_MASK + PS_ALBEDO (solid mid-grey),
# then drives ps_mode.render(). The albedo being non-None means relight() will
# return a coloured base — the preview must still render without error.
HARNESS_WITH_ALBEDO = """
import numpy as np
from pathlib import Path
from PIL import Image
import streamlit as st
from mini_highlight_advisor import relight
from ui import ps_mode, keys

FIX = Path("tests/fixtures/ps")
if keys.NORMALS not in st.session_state:
    normals = relight.load_normals(str(FIX / "synth_normal.png"))
    mask = np.asarray(Image.open(FIX / "synth_mask.png").convert("L")) > 127
    h, w = mask.shape
    st.session_state[keys.NORMALS] = normals
    st.session_state[keys.PS_MASK] = mask
    st.session_state[keys.PS_ALBEDO] = np.ones((h, w, 3), np.float32) * 0.5

ps_mode.render(picked=[], owned_paints=[])
st.write("done")
"""

# Harness without albedo: pre-seeds NORMALS + PS_MASK only (PS_ALBEDO absent).
# Must fall back to grey display — same behaviour as before this feature.
HARNESS_NO_ALBEDO = """
import numpy as np
from pathlib import Path
from PIL import Image
import streamlit as st
from mini_highlight_advisor import relight
from ui import ps_mode, keys

FIX = Path("tests/fixtures/ps")
if keys.NORMALS not in st.session_state:
    st.session_state[keys.NORMALS] = relight.load_normals(str(FIX / "synth_normal.png"))
    st.session_state[keys.PS_MASK] = (
        np.asarray(Image.open(FIX / "synth_mask.png").convert("L")) > 127)

ps_mode.render(picked=[], owned_paints=[])
st.write("done")
"""


def test_ps_mode_with_albedo_renders_without_error():
    at = AppTest.from_string(HARNESS_WITH_ALBEDO); at.run()
    assert not at.exception
    assert at.session_state.get(keys.PS_ALBEDO) is not None


def test_ps_mode_without_albedo_renders_without_error():
    # Regression: existing grey-base path must still work when PS_ALBEDO is absent.
    at = AppTest.from_string(HARNESS_NO_ALBEDO); at.run()
    assert not at.exception


def test_ps_mode_without_albedo_leaves_albedo_key_none():
    at = AppTest.from_string(HARNESS_NO_ALBEDO); at.run()
    assert not at.exception
    # PS_ALBEDO must default to None, not raise KeyError
    assert at.session_state.get(keys.PS_ALBEDO) is None
```

Run to verify they **fail**:
```
.venv/Scripts/python -m pytest tests/test_ui_ps_albedo.py -v
```
Expected: FAIL — `keys.PS_ALBEDO` may not exist yet in `ps_mode.render`, and `relight()` isn't receiving `albedo`.

- [ ] **Step 3: Wire albedo into `ui/ps_mode.py`**

**`_import_gate`** — add optional third uploader and store albedo in session:

Replace the existing two-column uploader block:
```python
def _import_gate() -> bool:
    """Three uploaders (normal + mask required; albedo optional). Returns True
    once a valid bundle is in session."""
    if keys.NORMALS in st.session_state and keys.PS_MASK in st.session_state:
        return True
    st.info("Import a photometric-stereo bundle produced by `tools/ps_tool.py`: "
            "a normal map and its mask. See docs/ps-capture-guide.md.")
    c1, c2, c3 = st.columns(3)
    nrm = c1.file_uploader("normal.png", type=["png"], key="ps_upload_normal")
    msk = c2.file_uploader("mask.png", type=["png"], key="ps_upload_mask")
    alb = c3.file_uploader("albedo.png (optional)", type=["png"],
                           key="ps_upload_albedo")
    if nrm is None or msk is None:
        return False

    rgb01 = np.asarray(Image.open(nrm).convert("RGB"), np.float32) / 255.0
    mask = np.asarray(Image.open(msk).convert("L")) > 127
    if rgb01.shape[:2] != mask.shape:
        st.error(f"Dimension mismatch: normal {rgb01.shape[:2]} vs mask {mask.shape}. "
                 "The two files must be the same size.")
        return False
    if not relight.plausible_unit_normals(rgb01, mask):
        st.error("That doesn't look like a normal map (values don't decode to unit "
                 "normals over the mask). Re-export the bundle from ps_tool.")
        return False

    st.session_state[keys.NORMALS] = relight._decode(rgb01)
    st.session_state[keys.PS_MASK] = mask

    # Albedo is optional — absent or implausible → None (grey fallback)
    albedo = None
    if alb is not None:
        albedo_arr = relight.load_albedo(alb)
        if relight.plausible_albedo(albedo_arr, mask):
            albedo = albedo_arr
        else:
            st.warning("albedo.png didn't pass the plausibility check — "
                       "falling back to grey display base.")
    st.session_state[keys.PS_ALBEDO] = albedo

    st.rerun()
    return True
```

**`render`** — read albedo from session, pass to `relight()`, rename local variable:

```python
def render(picked, owned_paints) -> None:
    if not _import_gate():
        st.stop()

    normals = st.session_state[keys.NORMALS]
    mask = st.session_state[keys.PS_MASK]
    albedo = st.session_state.get(keys.PS_ALBEDO)   # None for old bundles

    az, el = relight_panel.render()
    light_field, relit_rgb = relight.relight(
        normals, mask, relight.light_dir(az, el), albedo=albedo)
    mask_u8 = (mask * 255).astype(np.uint8)
    shading = ShadingResult(mask=compute_mask(relit_rgb, mask_u8), light=light_field)

    st.session_state.setdefault(keys.PS_BOOK, new_book(5))
    book = st.session_state[keys.PS_BOOK]

    editor.render_editor(relit_rgb, mask_u8, shading, book, picked, owned_paints,
                         light_field=light_field, normal_field=normals)
```

Also add the `keys` import for `PS_ALBEDO` — `keys` is already imported; just ensure `keys.PS_ALBEDO` is referenced (it will be once you added it to `keys.py` in Step 1).

- [ ] **Step 4: Run the new AppTests**

```
.venv/Scripts/python -m pytest tests/test_ui_ps_albedo.py -v
```
Expected: all 3 tests PASS.

- [ ] **Step 5: Run the existing PS UI regression tests**

```
.venv/Scripts/python -m pytest tests/test_ui_ps_mode.py tests/test_ui_results_ps.py tests/test_ui_nmm.py tests/test_ui_keys.py -v
```
Expected: all PASS — the existing harnesses don't seed `PS_ALBEDO`, so `session_state.get(keys.PS_ALBEDO)` returns `None` and `relight(albedo=None)` produces the same grey base as before.

- [ ] **Step 6: Full suite**

```
.venv/Scripts/python -m pytest
```
Expected: all PASS except the two pre-existing `test_ui_gallery.py` failures (unrelated, noted in project history).

- [ ] **Step 7: Commit**

```
git add ui/keys.py ui/ps_mode.py tests/test_ui_keys.py tests/test_ui_ps_albedo.py
git commit -m "feat(ui): PS import reads albedo.png; thread to relight() for coloured display base"
```

---

## Final verification

- [ ] Run `.venv/Scripts/python -m pytest` — all green except the two known `test_ui_gallery.py` failures.
- [ ] **Manual smoke (optional, requires a PS bundle with albedo.png):** run `ps_tool` on a painted mini with the updated tool, import the bundle in the app (normal + mask + albedo), confirm the display base is coloured rather than grey. The highlight overlay bands should still appear on top correctly.
