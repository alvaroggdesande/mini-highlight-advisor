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
    paints = [
        {"code": "70.950", "name": "Black", "hex": "#1b1b1b"},
        {"code": "70.999", "name": "No Hex Here"},
    ]
    with pytest.raises(ValueError) as exc:
        validate_catalog(paints)
    msg = str(exc.value)
    assert "1" in msg and "No Hex Here" in msg and "hex" in msg


def test_missing_code_raises():
    paints = [{"name": "Black", "hex": "#1b1b1b"}]
    with pytest.raises(ValueError) as exc:
        validate_catalog(paints)
    assert "code" in str(exc.value)


def test_bad_hex_raises_quoting_value_and_name():
    paints = [{"code": "70.957", "name": "Bad Red", "hex": "#12"}]
    with pytest.raises(ValueError) as exc:
        validate_catalog(paints)
    msg = str(exc.value)
    assert "Bad Red" in msg and "#12" in msg


def test_duplicate_code_raises():
    paints = [
        {"code": "70.991", "name": "Neutral Grey", "hex": "#6d7173"},
        {"code": "70.991", "name": "Other Grey", "hex": "#6d7174"},
    ]
    with pytest.raises(ValueError) as exc:
        validate_catalog(paints)
    assert "70.991" in str(exc.value)


def test_duplicate_name_is_allowed():
    paints = [
        {"code": "70.951", "name": "Dead White", "hex": "#f3f3ee"},
        {"code": "72.001", "name": "Dead White", "hex": "#ffffff"},
    ]
    assert validate_catalog(paints) is None


def test_valid_paints_pass_validation():
    paints = [
        {"code": "70.950", "name": "Black", "hex": "#1b1b1b", "brand": "Vallejo", "range": "Model Color"},
        {"code": "70.951", "name": "Dead White", "hex": "#F3F3EE"},
    ]
    assert validate_catalog(paints) is None


def test_find_by_code_resolves_known_paint():
    from mini_highlight_advisor.catalog import load_catalog, find_by_code
    p = find_by_code(load_catalog(), "72.045")
    assert p is not None and p.name == "Charred Brown"


def test_find_by_code_missing_returns_none():
    from mini_highlight_advisor.catalog import load_catalog, find_by_code
    assert find_by_code(load_catalog(), "99.999") is None


def test_reverted_names_collide_but_load_by_code():
    from mini_highlight_advisor.catalog import load_catalog, find_by_code
    cat = load_catalog()
    # Two "Dead White" now coexist, distinguished only by code.
    assert find_by_code(cat, "70.951").name == "Dead White"      # Model Color
    assert find_by_code(cat, "72.001").name == "Dead White"      # Game Color
    assert find_by_code(cat, "72.061").name == "Khaki"           # was "Khaki game"
    assert find_by_code(cat, "72.016").name == "Royal Purple"    # was "Royal Purple model"→ Game


def test_load_defaults_finish_matte(tmp_path):
    import json
    from mini_highlight_advisor.catalog import load_catalog
    p = tmp_path / "c.json"
    p.write_text(json.dumps({"paints": [{"code": "70.950", "name": "Black", "hex": "#1b1b1b"}]}))
    assert load_catalog(p)[0].finish == "matte"


def test_load_reads_metallic_finish(tmp_path):
    import json
    from mini_highlight_advisor.catalog import load_catalog
    p = tmp_path / "c.json"
    p.write_text(json.dumps({"paints": [
        {"code": "77.101", "name": "Sterling Silver", "hex": "#d5d7d6", "finish": "metallic"}]}))
    assert load_catalog(p)[0].finish == "metallic"


def test_validate_rejects_bad_finish():
    from mini_highlight_advisor.catalog import validate_catalog
    with pytest.raises(ValueError) as exc:
        validate_catalog([{"code": "1", "name": "Glitterbomb", "hex": "#111111", "finish": "glitter"}])
    assert "finish" in str(exc.value) and "Glitterbomb" in str(exc.value)


def test_known_metallics_tagged_after_curation():
    from mini_highlight_advisor.catalog import load_catalog, find_by_code
    cat = load_catalog()
    # TMM range + real metallics hiding in Model/Game Color
    for code in ["77.101", "70.997", "70.865", "72.052", "72.054", "72.055", "72.059"]:
        p = find_by_code(cat, code)
        assert p is not None and p.finish == "metallic", code


def test_colour_named_paints_stay_matte():
    from mini_highlight_advisor.catalog import load_catalog, find_by_code
    cat = load_catalog()
    # keyword false-positives that are NOT metallic paints — must remain matte
    for code in ["72.007", "72.036", "72.002", "70.897", "72.045"]:
        p = find_by_code(cat, code)
        assert p is not None and p.finish == "matte", code


def test_all_tmm_entries_are_metallic():
    from mini_highlight_advisor.catalog import load_catalog
    cat = load_catalog()
    tmm = [p for p in cat if p.paint_range == "True Metallic Metal"]
    assert tmm and all(p.finish == "metallic" for p in tmm)
