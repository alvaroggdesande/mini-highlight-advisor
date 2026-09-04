import numpy as np
from PIL import Image
from pathlib import Path
from mini_highlight_advisor import pipeline

_FIX = Path(__file__).parent / "fixtures" / "ps"

def _load():
    rgb = np.asarray(Image.open(_FIX / "synth_normal.png").convert("RGB"), np.float32) / 255.0
    n = rgb * 2.0 - 1.0
    n /= np.clip(np.linalg.norm(n, axis=-1, keepdims=True), 1e-6, None)
    mask = np.asarray(Image.open(_FIX / "synth_mask.png").convert("L")) > 127
    return n.astype(np.float32), mask

def test_apply_osl_makes_glow_steps_and_preview():
    n, mask = _load()
    base = np.full((*mask.shape, 3), 60, np.uint8)
    src = pipeline.OslSource(x=63.5, y=63.5, height=40.0,
                             glow_rgb=np.array([40., 200., 90.], np.float32),
                             hot_rgb=np.array([200., 255., 210.], np.float32))
    res = pipeline.apply_osl(base, n, mask, src, reach=25.0, intensity=1.0,
                             coverage=[1.0, 0.5, 0.2], owned=[], catalog=[])
    assert len(res.steps) == 3
    assert all(s.kind == "osl" for s in res.steps)
    assert res.preview_rgb.shape == base.shape
    # preview brightened somewhere inside the lit zone
    assert res.preview_rgb.mean() > base.mean()
    # base is untouched (caller's array not mutated)
    assert base.mean() == 60

def test_apply_osl_dark_when_source_behind():
    n, mask = _load()
    base = np.full((*mask.shape, 3), 60, np.uint8)
    # height 0 and far off to the side with tiny reach -> almost no glow
    src = pipeline.OslSource(x=-200.0, y=63.5, height=0.0,
                             glow_rgb=np.array([40., 200., 90.], np.float32),
                             hot_rgb=np.array([200., 255., 210.], np.float32))
    res = pipeline.apply_osl(base, n, mask, src, reach=5.0, intensity=1.0,
                             coverage=[1.0, 0.5, 0.2], owned=[], catalog=[])
    assert res.glow[mask].max() < 0.2
