import numpy as np
from mini_highlight_advisor.catalog import load_catalog, find_by_name
from mini_highlight_advisor.palette import DEFAULT_PALETTE


def test_load_catalog_returns_vallejo_paints():
    cat = load_catalog()
    assert len(cat) > 0
    assert all(p.brand == "Vallejo" for p in cat)


def test_known_paint_resolves_to_expected_hex():
    cat = load_catalog()
    charred = find_by_name(cat, "Charred Brown")
    assert charred is not None
    assert charred.hex.lower() == "#3d2a25"
    assert charred.paint_range == "Game Color"


def test_find_by_name_missing_returns_none():
    assert find_by_name(load_catalog(), "Nonexistent Paint") is None


def test_default_palette_entries_exist_in_catalog():
    cat = load_catalog()
    for p in DEFAULT_PALETTE:
        assert find_by_name(cat, p.name) is not None
