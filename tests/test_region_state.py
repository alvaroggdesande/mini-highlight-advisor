import numpy as np
from mini_highlight_advisor.region_state import RegionBook, new_book
from mini_highlight_advisor.palette import default_ramp, default_coverage

def _mask(h=8, w=8):
    m = np.zeros((h, w), dtype=bool); m[2:5, 2:5] = True; return m

def test_new_book_is_whole_mini_only():
    b = new_book(5)
    assert b.names() == ["Whole mini"]
    assert b.selected == 0
    assert len(b.palette_at(0)) == 5

def test_add_appends_and_selects():
    b = new_book(4)
    g = b.add(_mask(), "Cloak", default_ramp(3), default_coverage(3))
    assert g == 1
    assert b.selected == 1
    assert b.names() == ["Whole mini", "Cloak"]
    assert len(b.palette_at(1)) == 3

def test_set_palette_routes_by_index():
    b = new_book(3)
    b.add(_mask(), "Cloak", default_ramp(3), default_coverage(3))
    new_pal = default_ramp(3)
    b.set_palette_at(1, new_pal)
    assert b.palette_at(1) is new_pal
    assert b.palette_at(0) is not new_pal

def test_remove_fixes_selection():
    b = new_book(3)
    b.add(_mask(), "A", default_ramp(3), default_coverage(3))
    b.add(_mask(), "B", default_ramp(3), default_coverage(3))
    b.remove(2)
    assert b.names() == ["Whole mini", "A"]
    assert b.selected == 1

def test_cannot_remove_whole_mini():
    b = new_book(3)
    try:
        b.remove(0)
        assert False, "expected ValueError"
    except ValueError:
        pass

def test_analyze_args_shape():
    b = new_book(3)
    b.add(_mask(), "Cloak", default_ramp(3), default_coverage(3))
    wp, cov, drawn = b.analyze_args()
    assert len(wp) == 3 and len(cov) == 3
    assert len(drawn) == 1 and drawn[0].name == "Cloak"

def test_set_name_at_renames_drawn_region():
    b = new_book(3)
    b.add(_mask(), "Cloak", default_ramp(3), default_coverage(3))
    b.set_name_at(1, "Robe")
    assert b.names() == ["Whole mini", "Robe"]

def test_set_name_at_rejects_blank_keeps_old():
    b = new_book(3)
    b.add(_mask(), "Cloak", default_ramp(3), default_coverage(3))
    b.set_name_at(1, "   ")
    assert b.names() == ["Whole mini", "Cloak"]

def test_set_name_at_cannot_rename_whole_mini():
    b = new_book(3)
    try:
        b.set_name_at(0, "Nope")
        assert False, "expected ValueError"
    except ValueError:
        pass
