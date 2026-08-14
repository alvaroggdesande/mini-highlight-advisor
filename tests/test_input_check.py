import numpy as np
from mini_highlight_advisor.input_check import check_input, CheckResult


def _full_mask(h, w):
    return np.ones((h, w), dtype=bool)


def test_flat_image_fails_lighting_with_advice():
    # Uniform mid-grey -> no tonal spread -> lighting must fail.
    rgb = np.full((200, 200, 3), 128, dtype=np.uint8)
    results = check_input(rgb, _full_mask(200, 200))
    lighting = next(r for r in results if r.id == "lighting")
    assert lighting.ok is False
    assert "flat" in lighting.detail.lower()
    assert "raking" in lighting.detail.lower()  # actionable fix present


def test_high_contrast_gradient_passes_lighting():
    grad = np.tile(np.linspace(0, 255, 200, dtype=np.uint8), (200, 1))
    rgb = np.stack([grad, grad, grad], axis=-1)
    results = check_input(rgb, _full_mask(200, 200))
    lighting = next(r for r in results if r.id == "lighting")
    assert lighting.ok is True
    assert isinstance(lighting, CheckResult)


def test_check_input_returns_lighting_first():
    rgb = np.full((50, 50, 3), 128, dtype=np.uint8)
    results = check_input(rgb, _full_mask(50, 50))
    assert results[0].id == "lighting"


def test_empty_mask_returns_non_crashing_advice():
    rgb = np.full((50, 50, 3), 128, dtype=np.uint8)
    mask = np.zeros((50, 50), dtype=bool)
    results = check_input(rgb, mask)  # must not raise
    assert len(results) >= 1
    assert results[0].ok is False
    assert "no mini detected" in results[0].detail.lower()
