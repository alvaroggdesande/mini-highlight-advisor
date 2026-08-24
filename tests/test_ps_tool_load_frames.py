"""_load_frames must fail loud (not crash deep in selection) when a stray
non-frame file of a different size lands in the frames dir. Regression for the
real black.data run where a _contact_black2.png (800x532) broke IoU broadcast."""
import numpy as np
import pytest
from PIL import Image

from tools import ps_tool

# ps_tool imports ps_stages via a bare name (its sys.path hack), so the
# CaptureError it raises is ps_tool.CaptureError — catch that exact symbol,
# not tools.ps_stages.CaptureError (a distinct class object, same source).
CaptureError = ps_tool.CaptureError


def _write_png(path, h, w):
    Image.fromarray(np.zeros((h, w, 3), np.uint8)).save(path)


def test_load_frames_accepts_uniform_size(tmp_path):
    for i in range(3):
        _write_png(tmp_path / f"L_0{i}.png", 576, 433)
    paths, frames = ps_tool._load_frames(tmp_path)
    assert len(frames) == 3
    assert all(f.shape[:2] == (576, 433) for f in frames)


def test_load_frames_rejects_odd_sized_stray_file(tmp_path):
    for i in range(3):
        _write_png(tmp_path / f"L_0{i}.png", 576, 433)
    _write_png(tmp_path / "_contact_black2.png", 532, 800)   # stray non-frame
    with pytest.raises(CaptureError, match="same size"):
        ps_tool._load_frames(tmp_path)


def test_load_frames_error_names_the_offender(tmp_path):
    for i in range(3):
        _write_png(tmp_path / f"L_0{i}.png", 576, 433)
    _write_png(tmp_path / "_contact_black2.png", 532, 800)
    with pytest.raises(CaptureError, match="_contact_black2.png"):
        ps_tool._load_frames(tmp_path)
