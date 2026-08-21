# tests/test_projects.py
import numpy as np

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


def test_drawn_regions_roundtrip_masks_bit_identical(tmp_path):
    from mini_highlight_advisor.region_state import RegionBook
    from mini_highlight_advisor.regions import Region
    from mini_highlight_advisor.palette import default_ramp, default_coverage

    m0 = np.zeros((6, 8), dtype=bool); m0[1:3, 2:5] = True
    m1 = np.zeros((6, 8), dtype=bool); m1[4:6, 0:2] = True
    book = RegionBook(default_ramp(5), default_coverage(5), drawn=[
        Region("Cloak", m0, default_ramp(4), default_coverage(4)),
        Region("Blade", m1, default_ramp(3), default_coverage(3)),
    ], selected=1)

    slug = projects.save_project("Multi", b"PB", ".png", book, _settings(), root=tmp_path)
    loaded = projects.load_project(slug, root=tmp_path)

    assert [r.name for r in loaded.book.drawn] == ["Cloak", "Blade"]
    assert np.array_equal(loaded.book.drawn[0].mask, m0)
    assert np.array_equal(loaded.book.drawn[1].mask, m1)
    assert loaded.book.drawn[0].palette == book.drawn[0].palette
    assert loaded.book.drawn[0].coverage == book.drawn[0].coverage
    assert loaded.book.selected == 1
