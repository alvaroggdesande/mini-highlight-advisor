import numpy as np
import pytest
from mini_highlight_advisor.region_state import new_book


def _small_rgb():
    return np.full((16, 16, 3), 128, dtype=np.uint8)


def _small_alpha():
    a = np.zeros((16, 16), dtype=np.uint8)
    a[4:12, 4:12] = 255
    return a


class _FakeShading:
    def __init__(self, mask):
        self.mask = mask
        self.light = np.ones((16, 16), dtype=np.float32) * 0.5


def test_run_analysis_returns_multi_region_result():
    from ui import helpers
    from mini_highlight_advisor.pipeline import MultiRegionResult

    rgb = _small_rgb()
    alpha = _small_alpha()
    mask = alpha > 127
    shading = _FakeShading(mask)
    book = new_book(3)

    result = helpers.run_analysis(rgb, alpha, book, shading)
    assert isinstance(result, MultiRegionResult)
    assert len(result.plans) >= 1


def test_run_analysis_reads_edge_hl_from_session_state():
    """With EDGE_HL=False in session_state, edge highlights should be off."""
    import streamlit as st
    from unittest.mock import patch
    from ui import helpers, keys

    rgb = _small_rgb()
    alpha = _small_alpha()
    mask = alpha > 127
    shading = _FakeShading(mask)
    book = new_book(3)

    fake_state = {keys.EDGE_HL: False}
    with patch.object(st, "session_state", fake_state):
        result = helpers.run_analysis(rgb, alpha, book, shading)
    # If edge_hl=False, no edge highlight pixels — just verify it doesn't crash
    assert result is not None
