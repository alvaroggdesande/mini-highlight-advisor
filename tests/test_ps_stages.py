import numpy as np
import pytest

from tools import ps_stages as ps
from mini_highlight_advisor import relight


def _disc(h, w, cr, cc, r):
    yy, xx = np.mgrid[0:h, 0:w]
    return ((yy - cr) ** 2 + (xx - cc) ** 2) <= r * r


def test_align_recovers_known_translation():
    ref = _disc(64, 64, 32, 32, 12)
    shifted = _disc(64, 64, 32 + 5, 32 - 7, 12)     # +5 rows, -7 cols
    frames = [ref.astype(np.uint8) * 200, shifted.astype(np.uint8) * 200]
    _, _, offs = ps.align_to_reference(frames, [ref, shifted])
    assert abs(offs[1][0] - (-5)) <= 1        # brings it back up 5 rows
    assert abs(offs[1][1] - 7) <= 1           # and right 7 cols


def test_iou_gate_drops_cut_off_base_frame():
    good = _disc(64, 64, 32, 32, 14)
    cut = good.copy(); cut[40:, :] = False      # base sliced off -> low IoU
    frames = [good.astype(np.uint8) * 200] * 3 + [cut.astype(np.uint8) * 200]
    masks = [good, good, good, cut]
    # inject real lighting variation so only the IoU gate fires
    for i, f in enumerate(frames):
        frames[i] = (f.astype(np.float32) * (0.5 + 0.2 * i)).astype(np.uint8)
    # 4 frames − 1 dropped by IoU = 3 kept; min_frames=3 isolates the IoU gate from the min-frames abort
    kept, report = ps.select_frames(frames, masks, min_frames=3)
    assert 3 not in kept
    assert 3 in report["dropped"]


def test_min_frames_abort():
    good = _disc(32, 32, 16, 16, 8)
    frames = [good.astype(np.uint8) * 200, good.astype(np.uint8) * 100]
    with pytest.raises(ps.CaptureError, match="too few|inconsistent"):
        ps.select_frames(frames, [good, good], min_frames=4)


def test_lighting_variation_abort_on_identical_frames():
    good = _disc(48, 48, 24, 24, 12)
    same = (good.astype(np.uint8) * 150)
    frames = [same.copy() for _ in range(5)]     # zero variation = turntable/no relight
    with pytest.raises(ps.CaptureError, match="lighting|variation"):
        ps.select_frames(frames, [good] * 5)


def test_consensus_is_majority_vote():
    a = _disc(32, 32, 16, 16, 10)
    b = _disc(32, 32, 16, 16, 10)
    c = _disc(32, 32, 16, 16, 4)                  # smaller
    out = ps.consensus_mask([a, b, c])
    assert out[16, 16]                            # center: all agree
    assert out[16, 24] == a[16, 24]              # majority (a,b) win the ring


def test_encode_decode_round_trip_pins_convention():
    rng = np.random.default_rng(0)
    n = rng.normal(size=(20, 20, 3)).astype(np.float32)
    n[..., 2] = np.abs(n[..., 2]) + 0.2          # z toward viewer
    n /= np.linalg.norm(n, axis=-1, keepdims=True)
    png8 = ps.encode_normals(n)
    assert png8.dtype == np.uint8 and png8.shape == (20, 20, 3)
    decoded = relight._decode(png8.astype(np.float32) / 255.0)
    assert np.allclose(decoded, n, atol=1.0 / 255 * 3 + 1e-3)
