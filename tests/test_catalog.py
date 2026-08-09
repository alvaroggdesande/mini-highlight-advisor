import pytest

from mini_highlight_advisor.catalog import (
    load_catalog,
    find_by_name,
    validate_catalog,
)
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


def test_shipped_seed_passes_validation():
    # The curated seed must load cleanly (no regression).
    cat = load_catalog()
    assert len(cat) > 0
    assert all(p.brand == "Vallejo" for p in cat)


def test_missing_required_key_raises_naming_index():
    paints = [{"name": "Black", "hex": "#1b1b1b"}, {"name": "No Hex Here"}]
    with pytest.raises(ValueError) as exc:
        validate_catalog(paints)
    msg = str(exc.value)
    assert "1" in msg          # names the offending index
    assert "No Hex Here" in msg  # names the entry when name is present
    assert "hex" in msg          # names the missing key


def test_bad_hex_raises_quoting_value_and_name():
    paints = [{"name": "Bad Red", "hex": "#12"}]
    with pytest.raises(ValueError) as exc:
        validate_catalog(paints)
    msg = str(exc.value)
    assert "Bad Red" in msg
    assert "#12" in msg


def test_duplicate_name_raises_naming_duplicate():
    paints = [
        {"name": "Neutral Grey", "hex": "#6d7173"},
        {"name": "Neutral Grey", "hex": "#6d7174"},
    ]
    with pytest.raises(ValueError) as exc:
        validate_catalog(paints)
    assert "Neutral Grey" in str(exc.value)


def test_valid_paints_pass_validation():
    paints = [
        {"name": "Black", "hex": "#1b1b1b", "brand": "Vallejo", "range": "Model Color"},
        {"name": "Dead White", "hex": "#F3F3EE"},  # brand/range optional, hex case-insensitive
    ]
    assert validate_catalog(paints) is None
