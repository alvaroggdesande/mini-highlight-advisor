from mini_highlight_advisor.collection import load, save, annotate_ownership
from mini_highlight_advisor.palette import PaintColor


def test_save_then_load_round_trips_codes(tmp_path):
    p = tmp_path / "collection.json"
    save({"70.804", "72.010"}, path=p)
    assert load(path=p) == {"70.804", "72.010"}


def test_load_missing_returns_empty_set(tmp_path):
    assert load(path=tmp_path / "nope.json") == set()


def test_load_maps_unique_legacy_name_and_drops_unknown(tmp_path):
    p = tmp_path / "collection.json"
    p.write_text('{"owned": ["Beige Red", "72.010", "Ghost Paint"]}', encoding="utf-8")
    catalog = [
        PaintColor("Beige Red", "#EAA88C", "Vallejo", "Model Color", code="70.804"),
        PaintColor("Bloody Red", "#C72323", "Vallejo", "Game Color", code="72.010"),
    ]
    # "Beige Red"->70.804 (unique name), "72.010" kept (known code), "Ghost Paint" dropped.
    assert load(path=p, catalog=catalog) == {"70.804", "72.010"}


def test_load_drops_ambiguous_legacy_name(tmp_path):
    p = tmp_path / "collection.json"
    p.write_text('{"owned": ["Dead White"]}', encoding="utf-8")
    catalog = [
        PaintColor("Dead White", "#f3f3ee", "Vallejo", "Model Color", code="70.951"),
        PaintColor("Dead White", "#ffffff", "Vallejo", "Game Color", code="72.001"),
    ]
    assert load(path=p, catalog=catalog) == set()  # ambiguous -> dropped


def test_annotate_marks_owned_and_unowned():
    palette = [PaintColor("Orange Brown", "#A75A38"), PaintColor("Bright Orange", "#E15E32")]
    owned = [PaintColor("Orange Brown", "#A75A38")]
    slots = annotate_ownership(palette, owned)
    assert slots[0].owned is True
    assert slots[1].owned is False


def test_nearest_owned_is_closest_by_rgb():
    # unowned target #E15E32; owned has a near-orange and a far-black
    palette = [PaintColor("Bright Orange", "#E15E32")]
    owned = [PaintColor("Orange Brown", "#A75A38"), PaintColor("Black", "#000000")]
    slots = annotate_ownership(palette, owned)
    assert slots[0].owned is False
    assert slots[0].nearest_owned.name == "Orange Brown"


def test_nearest_owned_none_when_no_owned():
    slots = annotate_ownership([PaintColor("X", "#123456")], [])
    assert slots[0].owned is False
    assert slots[0].nearest_owned is None


def test_nearest_paint_returns_rgb_closest():
    from mini_highlight_advisor.collection import nearest_paint
    cands = [PaintColor("Orange Brown", "#A75A38"), PaintColor("Black", "#000000")]
    got = nearest_paint(PaintColor("t", "#E15E32").rgb, cands)
    assert got.name == "Orange Brown"


def test_nearest_paint_empty_returns_none():
    from mini_highlight_advisor.collection import nearest_paint
    import numpy as np
    assert nearest_paint(np.zeros(3, dtype="float32"), []) is None
