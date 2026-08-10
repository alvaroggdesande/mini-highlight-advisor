# tests/test_consistency.py
from mini_highlight_advisor.palette import PaintColor
from mini_highlight_advisor.matching import MatchResult
from mini_highlight_advisor.consistency import annotate


def _res(tier="close", paints=None):
    paints = paints or [PaintColor("Neutral Grey", "#6d7173")]
    return MatchResult(tier, "#6d7173", paints, None, 2.0, None, "x")


def test_role_dilution_base():
    note = annotate(_res(), role="Base")
    assert "thin coats" in note


def test_edge_highlight_role():
    note = annotate(_res(), role="Edge Highlight")
    assert "fine" in note.lower() or "tip" in note.lower()


def test_mix_adds_water_ratio():
    res = MatchResult("mix", "#8a8a88", [PaintColor("Black", "#1b1b1b"),
                      PaintColor("White", "#f3f3ee")], [1, 1], 3.0, None, "x")
    note = annotate(res, role="Midtone")
    assert "milk" in note.lower() or "consistency" in note.lower()


def test_metallic_caveat():
    res = _res(paints=[PaintColor("Gunmetal", "#5a5f63", paint_range="Metal Color")])
    note = annotate(res, role="Base")
    assert "stir" in note.lower() or "settle" in note.lower()


def test_low_opacity_caveat():
    res = _res(paints=[PaintColor("Dead White", "#f3f3ee")])
    note = annotate(res, role="Highlight")
    assert "coat" in note.lower()


def test_unknown_role_no_dilution_but_still_string():
    note = annotate(_res(), role="")
    assert isinstance(note, str)
