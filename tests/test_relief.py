import os

import numpy as np
import pytest

from mini_highlight_advisor.banding import relief_recommended_bands
from mini_highlight_advisor.lighting import luminance_light
from mini_highlight_advisor.masking import compute_mask, load_image

_PRIMED = os.path.join(os.path.dirname(__file__), "..", "fixtures", "skaven-hero", "primed.png")


def _masked(vals: np.ndarray):
    """Lay `vals` into a light field, all inside the mask."""
    light = np.zeros((vals.size,), dtype=np.float32)
    light[:] = vals
    mask = np.ones((vals.size,), dtype=bool)
    return light, mask


def test_full_range_gradient_supports_all_requested_bands():
    light, mask = _masked(np.linspace(0.0, 1.0, 500, dtype=np.float32))
    assert relief_recommended_bands(light, mask, 5) == 5


def test_constant_region_collapses_to_one_band():
    light, mask = _masked(np.full(500, 0.4, dtype=np.float32))
    assert relief_recommended_bands(light, mask, 5) == 1


def test_moderately_flat_region_reduces_below_requested():
    # p5..p95 spread ~0.25 of the normalized range.
    light, mask = _masked(np.linspace(0.40, 0.66, 500, dtype=np.float32))
    k = relief_recommended_bands(light, mask, 5)
    assert 1 <= k < 5


def test_never_exceeds_requested():
    light, mask = _masked(np.linspace(0.0, 1.0, 500, dtype=np.float32))
    assert relief_recommended_bands(light, mask, 3) == 3


def test_empty_mask_returns_one():
    light = np.zeros((10,), dtype=np.float32)
    mask = np.zeros((10,), dtype=bool)
    assert relief_recommended_bands(light, mask, 5) == 1


@pytest.mark.skipif(not os.path.exists(_PRIMED), reason="fixture missing")
def test_known_good_primed_mini_is_not_capped():
    # The anchor: a well-exposed primed mini must keep the default 5 bands.
    rgb, alpha = load_image(_PRIMED)
    mask = compute_mask(rgb, alpha)
    light = luminance_light(rgb, mask)
    assert relief_recommended_bands(light, mask, 5) == 5
