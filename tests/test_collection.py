from mini_highlight_advisor.collection import load, save, annotate_ownership
from mini_highlight_advisor.palette import PaintColor


def test_save_then_load_round_trips(tmp_path):
    p = tmp_path / "collection.json"
    save({"Orange Brown", "Beige Red"}, path=p)
    assert load(path=p) == {"Orange Brown", "Beige Red"}


def test_load_missing_returns_empty_set(tmp_path):
    assert load(path=tmp_path / "nope.json") == set()


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
