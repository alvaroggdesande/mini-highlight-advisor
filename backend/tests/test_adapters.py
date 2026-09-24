from backend.schemas import PaintColorModel, WholeModel, AnalyzeRequest
from backend.core_adapters import paint_from_model, paint_to_dict, default_whole
from mini_highlight_advisor.palette import PaintColor
import pytest


def test_paint_roundtrip():
    m = PaintColorModel(name="Test", hex="#804020", code="ABC")
    p = paint_from_model(m)
    assert isinstance(p, PaintColor) and p.hex == "#804020"
    d = paint_to_dict(p)
    assert d["name"] == "Test" and d["code"] == "ABC" and d["finish"] == "matte"


def test_paint_hex_normalized_and_rejects_blank():
    assert PaintColorModel(name="Test", hex="#abc").hex == "#aabbcc"
    with pytest.raises(ValueError):
        PaintColorModel(name="Test", hex="")


def test_default_whole_shape():
    dw = default_whole()
    assert dw["material"] == "matte"
    assert len(dw["palette"]) == len(dw["coverage"]) >= 1
    assert dw["palette"][0].keys() >= {"name", "hex", "code", "finish"}


def test_analyze_request_defaults():
    req = AnalyzeRequest(photo_id="x",
                         whole=WholeModel(palette=[PaintColorModel(name="a", hex="#000000")],
                                          coverage=[1.0]))
    assert req.settings.relief_cap is True
