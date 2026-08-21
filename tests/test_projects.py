# tests/test_projects.py
from mini_highlight_advisor import projects
from mini_highlight_advisor.palette import PaintColor


def test_slugify_normalizes_and_is_stable():
    assert projects.slugify("Skaven Hero") == "skaven-hero"
    assert projects.slugify("  My Mini!!  ") == "my-mini"
    # same display name -> same slug (overwrite semantics rely on this)
    assert projects.slugify("Space Marine") == projects.slugify("space   marine")


def test_slugify_rejects_empty():
    import pytest
    with pytest.raises(ValueError):
        projects.slugify("   ")


def test_palette_dict_roundtrip_preserves_all_fields():
    pal = [
        PaintColor("Black", "#1b1b1b", "Vallejo", "Model Color", code="70.950"),
        PaintColor("Custom", "#abcdef"),  # brand/paint_range None, code "", finish default
    ]
    out = projects._palette_from_dicts(projects._palette_to_dicts(pal))
    assert out == pal


def _settings():
    return projects.ProjectSettings(n=5, edge_hl=True, edge_extreme=False,
                                    edge_sens=0.5, relief_cap=True, per_region_norm=False)


def _whole_book():
    from mini_highlight_advisor.region_state import RegionBook
    from mini_highlight_advisor.palette import default_ramp, default_coverage
    return RegionBook(default_ramp(5), default_coverage(5))


def test_save_then_load_whole_mini_roundtrip(tmp_path):
    book = _whole_book()
    slug = projects.save_project("Skaven Hero", b"PHOTOBYTES", ".png",
                                 book, _settings(), root=tmp_path)
    assert slug == "skaven-hero"

    loaded = projects.load_project(slug, root=tmp_path)
    assert loaded.photo_bytes == b"PHOTOBYTES"
    assert loaded.photo_suffix == ".png"
    assert loaded.settings == _settings()
    assert loaded.book.whole_palette == book.whole_palette
    assert loaded.book.whole_coverage == book.whole_coverage
    assert loaded.book.drawn == []
    assert loaded.book.selected == 0
