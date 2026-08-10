import numpy as np
from mini_highlight_advisor.masking import load_image
from mini_highlight_advisor.palette import DEFAULT_PALETTE, coverage_pct, PaintColor, default_coverage
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


def test_analyze_populates_per_band_steps():
    from mini_highlight_advisor.palette import PaintColor

    rgb = np.random.default_rng(0).integers(0, 255, (32, 32, 3), dtype=np.uint8)
    alpha = np.full((32, 32), 255, dtype=np.uint8)  # full-model alpha, fast path
    palette = [PaintColor("A", "#202020"), PaintColor("B", "#808080"), PaintColor("C", "#f0f0f0")]

    result = analyze(rgb, alpha, palette)

    assert len(result.steps) == len(palette)
    assert result.steps[-1].is_last is True
    assert result.steps[-1].exact_rgb is None
    assert result.steps[0].cumulative_rgb.shape == rgb.shape


def test_prepare_then_band_matches_analyze_default():
    from mini_highlight_advisor.pipeline import prepare_shading, band_and_render

    rgb = np.random.default_rng(0).integers(0, 255, (32, 32, 3), dtype=np.uint8)
    alpha = np.full((32, 32), 255, dtype=np.uint8)  # full-model alpha, fast path
    palette = [PaintColor("A", "#202020"), PaintColor("B", "#808080"), PaintColor("C", "#f0f0f0")]

    baseline = analyze(rgb, alpha, palette)  # coverage=None -> default

    sh = prepare_shading(rgb, alpha)
    split = band_and_render(rgb, sh.mask, sh.light, palette, default_coverage(len(palette)))

    assert np.array_equal(split.bands, baseline.bands)
    assert split.coverage == baseline.coverage
    assert split.roles == baseline.roles


def test_analyze_accepts_custom_coverage():
    rgb = np.random.default_rng(1).integers(0, 255, (40, 40, 3), dtype=np.uint8)
    alpha = np.full((40, 40), 255, dtype=np.uint8)
    palette = [PaintColor("A", "#202020"), PaintColor("B", "#808080"), PaintColor("C", "#f0f0f0")]

    # Fatten the shadow band; expect its coverage to dominate.
    result = analyze(rgb, alpha, palette, coverage=[0.6, 0.3, 0.1])
    assert result.coverage[0] > result.coverage[-1]
    assert abs(sum(result.coverage) - 100.0) < 0.5
