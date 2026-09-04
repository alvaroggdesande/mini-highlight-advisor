import numpy as np
from PIL import Image
from pathlib import Path

from ui import helpers
from mini_highlight_advisor import palette


def test_swatch_is_inline_span_with_colour():
    html = helpers.swatch("# abc123".replace(" ", ""), size="2em")
    assert "background-color:#abc123" in html
    assert "width:2em" in html and "height:2em" in html
    assert html.startswith("<span")


def test_current_cov_seed_length_and_sums_to_100():
    seed = helpers.current_cov_seed(5)
    assert len(seed) == 5
    assert abs(sum(seed) - 100.0) < 1.0  # default_coverage fractions * 100


_PS_FIX = Path(__file__).parent / "fixtures" / "ps"


def _load_synth():
    rgb = np.asarray(Image.open(_PS_FIX / "synth_normal.png").convert("RGB"), np.float32) / 255.0
    n = rgb * 2.0 - 1.0
    n /= np.clip(np.linalg.norm(n, axis=-1, keepdims=True), 1e-6, None)
    mask = np.asarray(Image.open(_PS_FIX / "synth_mask.png").convert("L")) > 127
    return n.astype(np.float32), mask


def _osl_params(mask):
    h, w = mask.shape
    return {
        "x": w / 2, "y": h / 2, "height": 40.0, "reach": 25.0, "intensity": 1.0,
        "coverage": palette.default_coverage(3),
        "glow_rgb": np.array([40., 200., 90.], np.float32),
        "hot_rgb": np.array([200., 255., 210.], np.float32),
    }


def test_build_osl_result_none_params_returns_input_unchanged():
    from ui.helpers import build_osl_result
    n, mask = _load_synth()
    base = np.full((*mask.shape, 3), 60, np.uint8)
    preview, res = build_osl_result(base, n, mask, None, owned=[], catalog=[])
    assert res is None
    assert preview is base  # exact same array, no copy/composite


def test_build_osl_result_composites_glow_and_leaves_base_untouched():
    from ui.helpers import build_osl_result
    n, mask = _load_synth()
    base = np.full((*mask.shape, 3), 60, np.uint8)
    preview, res = build_osl_result(base, n, mask, _osl_params(mask),
                                    owned=[], catalog=[])
    assert res is not None and len(res.steps) == 3
    assert preview.shape == base.shape
    assert preview.mean() > base.mean()      # glow brightened the preview
    assert base.mean() == 60                 # caller's array not mutated
