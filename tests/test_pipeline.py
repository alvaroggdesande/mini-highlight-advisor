import numpy as np
from mini_highlight_advisor.masking import load_image
from mini_highlight_advisor.palette import DEFAULT_PALETTE, coverage_pct
from mini_highlight_advisor.pipeline import analyze, HighlightResult

FIXTURE = "spikes/input/WhatsApp_Image_2026-08-09_at_14.04.40-removebg-preview.png"


def test_analyze_end_to_end_on_alpha_png():
    rgb, alpha = load_image(FIXTURE)
    result = analyze(rgb, alpha, DEFAULT_PALETTE)
    assert isinstance(result, HighlightResult)
    # Every band index present within the mask is valid.
    assert set(np.unique(result.bands[result.mask])) <= set(range(len(DEFAULT_PALETTE)))
    # Coverage sums to ~100% and is reported per band.
    assert len(result.coverage) == len(DEFAULT_PALETTE)
    assert abs(sum(result.coverage) - 100.0) < 0.5
    # Preview matches image dims; panel is wider (has legend).
    assert result.preview_rgb.shape == rgb.shape
    assert result.panel.width > rgb.shape[1]


def test_analyze_edge_band_covers_less_than_shadow():
    rgb, alpha = load_image(FIXTURE)
    result = analyze(rgb, alpha, DEFAULT_PALETTE)
    assert result.coverage[-1] < result.coverage[0]  # curved banding: edge < shadow
