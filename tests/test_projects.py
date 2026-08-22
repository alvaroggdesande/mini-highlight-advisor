# tests/test_projects.py
import numpy as np
import pytest

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


def test_list_projects_sorted_by_updated_desc(tmp_path):
    book = _whole_book()
    projects.save_project("Alpha", b"A", ".png", book, _settings(), root=tmp_path,
                          _now="2026-08-20T10:00:00+00:00")
    projects.save_project("Beta", b"B", ".png", book, _settings(), root=tmp_path,
                          _now="2026-08-21T10:00:00+00:00")
    metas = projects.list_projects(root=tmp_path)
    assert [m.name for m in metas] == ["Beta", "Alpha"]
    assert metas[0].slug == "beta"


def test_overwrite_by_name_drops_stale_region_masks(tmp_path):
    from mini_highlight_advisor.region_state import RegionBook
    from mini_highlight_advisor.regions import Region
    from mini_highlight_advisor.palette import default_ramp, default_coverage
    m = np.zeros((4, 4), dtype=bool); m[0, 0] = True
    two = RegionBook(default_ramp(5), default_coverage(5),
                     drawn=[Region("R0", m, default_ramp(3), default_coverage(3)),
                            Region("R1", m, default_ramp(3), default_coverage(3))])
    projects.save_project("Same", b"P", ".png", two, _settings(), root=tmp_path)
    # re-save under the same name with only ONE drawn region
    one = RegionBook(default_ramp(5), default_coverage(5),
                     drawn=[Region("R0", m, default_ramp(3), default_coverage(3))])
    projects.save_project("Same", b"P", ".png", one, _settings(), root=tmp_path)
    assert not (tmp_path / "same" / "region_01.png").exists()
    assert len(projects.load_project("same", root=tmp_path).book.drawn) == 1


def test_delete_project_removes_folder_and_is_idempotent(tmp_path):
    projects.save_project("Gone", b"P", ".png", _whole_book(), _settings(), root=tmp_path)
    projects.delete_project("gone", root=tmp_path)
    assert not (tmp_path / "gone").exists()
    projects.delete_project("gone", root=tmp_path)  # no error second time


def test_list_skips_corrupt_manifest_but_load_raises(tmp_path):
    projects.save_project("Good", b"P", ".png", _whole_book(), _settings(), root=tmp_path)
    bad = tmp_path / "bad"; bad.mkdir()
    (bad / "manifest.json").write_text("{ not json", encoding="utf-8")
    assert [m.slug for m in projects.list_projects(root=tmp_path)] == ["good"]
    with pytest.raises(Exception):
        projects.load_project("bad", root=tmp_path)


def test_angle_write_read_roundtrip_bit_identical(tmp_path):
    from mini_highlight_advisor.region_state import RegionBook
    from mini_highlight_advisor.regions import Region
    from mini_highlight_advisor.palette import default_ramp, default_coverage
    m0 = np.zeros((6, 8), dtype=bool); m0[1:3, 2:5] = True
    book = RegionBook(default_ramp(5), default_coverage(5),
                      drawn=[Region("Cloak", m0, default_ramp(4), default_coverage(4))],
                      selected=1)
    a = projects.AngleData(label="front", photo_bytes=b"PB", photo_suffix=".png",
                           book=book, settings=_settings())
    entry = projects._write_angle(tmp_path, 0, a)
    assert entry["label"] == "front"
    assert (tmp_path / "angle_00" / "photo.png").read_bytes() == b"PB"
    out = projects._read_angle(tmp_path, 0, entry)
    assert out.label == "front"
    assert out.photo_bytes == b"PB"
    assert out.photo_suffix == ".png"
    assert out.settings == _settings()
    assert out.book.drawn[0].name == "Cloak"
    assert np.array_equal(out.book.drawn[0].mask, m0)
    assert out.book.selected == 1
