import numpy as np
from PIL import Image
from pathlib import Path
from mini_highlight_advisor import pipeline, osl, palette
from mini_highlight_advisor.pipeline import osl_step_caption

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
    cov = palette.default_coverage(3)  # valid partition summing to 1.0
    res = pipeline.apply_osl(base, n, mask, src, reach=25.0, intensity=1.0,
                             coverage=cov, owned=[], catalog=[])
    assert len(res.steps) == 3
    assert all(s.kind == "osl" for s in res.steps)
    assert res.preview_rgb.shape == base.shape
    # preview brightened somewhere inside the lit zone
    assert res.preview_rgb.mean() > base.mean()
    # base is untouched (caller's array not mutated)
    assert base.mean() == 60
    # Multiple non-empty bands must exist (would fail under [1.0]*n collapse)
    bands = osl.osl_bands(res.glow, mask, palette.default_coverage(3))
    assert (bands == 0).sum() > 0
    assert (bands == 1).sum() > 0
    assert (bands == 2).sum() > 0

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


def test_osl_caption_first_step_is_broad_glaze():
    cap = osl_step_caption(0, 3, "Moot Green")
    assert "Moot Green" in cap
    assert "broad" in cap.lower()
    assert "glaze" in cap.lower()


def test_osl_caption_last_step_is_hotspot():
    cap = osl_step_caption(2, 3, "Dead White")
    assert "Dead White" in cap
    assert "hotspot" in cap.lower()
    # sells the effect: away-facing surfaces stay dark
    assert "dark" in cap.lower()


def test_osl_caption_middle_step_is_tighten():
    cap = osl_step_caption(1, 3, "Moot Green")
    assert "Moot Green" in cap
    assert "tighten" in cap.lower()


def test_osl_caption_two_steps_has_broad_and_hotspot_only():
    first = osl_step_caption(0, 2, "A")
    last = osl_step_caption(1, 2, "A")
    assert "broad" in first.lower()
    assert "hotspot" in last.lower()


def test_osl_caption_handles_missing_paint_name():
    # label can be None when no catalog match; caption must still be a str
    cap = osl_step_caption(0, 3, None)
    assert isinstance(cap, str) and cap
