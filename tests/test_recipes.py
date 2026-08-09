from pathlib import Path

from mini_highlight_advisor.recipes import (
    Recipe, RecipeStep, load_builtin, load_user, save_user, load_all, to_palette,
)


def test_load_builtin_has_nmm_copper_dark_to_light():
    recipes = load_builtin()
    copper = next(r for r in recipes if r.name == "NMM Copper")
    assert len(copper.steps) == 5
    assert 3 <= len(copper.steps) <= 5
    lums = [sum(int(s.hex.lstrip("#")[i:i+2], 16) for i in (0, 2, 4)) for s in copper.steps]
    assert lums == sorted(lums)  # dark to light


def test_to_palette_uses_paint_ref_name_and_hex():
    recipe = Recipe("t", [RecipeStep("Base", "#A75A38", "Orange Brown"),
                          RecipeStep("Top", "#ffffff", None)])
    pal = to_palette(recipe)
    assert pal[0].name == "Orange Brown" and pal[0].hex == "#A75A38"
    assert pal[1].name == "Top" and pal[1].hex == "#ffffff"


def test_save_user_then_load_user_round_trips(tmp_path):
    p = tmp_path / "recipes.json"
    r = Recipe("My Scheme", [RecipeStep("Base", "#123456", None)])
    save_user(r, path=p)
    loaded = load_user(path=p)
    assert [x.name for x in loaded] == ["My Scheme"]
    assert loaded[0].steps[0].hex == "#123456"


def test_save_user_upserts_by_name(tmp_path):
    p = tmp_path / "recipes.json"
    save_user(Recipe("A", [RecipeStep("s", "#111111", None)]), path=p)
    save_user(Recipe("A", [RecipeStep("s", "#222222", None)]), path=p)
    loaded = load_user(path=p)
    assert len(loaded) == 1 and loaded[0].steps[0].hex == "#222222"


def test_load_user_missing_file_returns_empty(tmp_path):
    assert load_user(path=tmp_path / "nope.json") == []


def test_load_all_merges_builtin_and_user(tmp_path):
    p = tmp_path / "recipes.json"
    save_user(Recipe("Custom", [RecipeStep("s", "#333333", None)]), path=p)
    names = [r.name for r in load_all(user_path=p)]
    assert "NMM Copper" in names and "Custom" in names
