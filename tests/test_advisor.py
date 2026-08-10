# tests/test_advisor.py
from mini_highlight_advisor.palette import PaintColor
from mini_highlight_advisor.matching import Target
from mini_highlight_advisor.advisor import advise, AdviceRow

BLACK = PaintColor("Black", "#1b1b1b", code="70.950")
GREY = PaintColor("Neutral Grey", "#6d7173", code="70.991")
WHITE = PaintColor("Dead White", "#f3f3ee", code="70.951")
CATALOG = [BLACK, GREY, WHITE]


def test_advise_zips_targets_and_roles():
    targets = [Target("#6d7173", "70.991"), Target("#f3f3ee", None)]
    rows = advise(targets, ["Base", "Edge Highlight"], owned=[GREY, WHITE], catalog=CATALOG)
    assert len(rows) == 2
    assert all(isinstance(r, AdviceRow) for r in rows)
    assert rows[0].role == "Base"
    assert rows[0].result.tier == "exact"
    assert "thin coats" in rows[0].note          # consistency was applied


def test_advise_tolerates_missing_roles():
    rows = advise([Target("#6d7173", None)], roles=[], owned=[GREY], catalog=CATALOG)
    assert len(rows) == 1
    assert rows[0].role == ""
