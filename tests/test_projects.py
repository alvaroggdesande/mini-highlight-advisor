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


def _angle(label="front", photo=b"PB", suffix=".png", book=None):
    book = book if book is not None else _whole_book()
    return projects.AngleData(label, photo, suffix, book, _settings())


def test_v2_multi_angle_roundtrip(tmp_path):
    from mini_highlight_advisor.region_state import RegionBook
    from mini_highlight_advisor.regions import Region
    from mini_highlight_advisor.palette import default_ramp, default_coverage
    m = np.zeros((5, 5), dtype=bool); m[1:3, 1:3] = True
    back_book = RegionBook(default_ramp(5), default_coverage(5),
                           drawn=[Region("Cape", m, default_ramp(4), default_coverage(4))],
                           selected=1)
    angles = [_angle("front", b"FRONT"), _angle("back", b"BACK", book=back_book)]
    slug = projects.save_project("Skaven Hero", ["70.950", "72.001"], 1, angles,
                                 root=tmp_path)
    assert slug == "skaven-hero"
    lp = projects.load_project(slug, root=tmp_path)
    assert lp.paints_pool == ["70.950", "72.001"]
    assert lp.active_angle == 1
    assert [a.label for a in lp.angles] == ["front", "back"]
    assert lp.angles[0].photo_bytes == b"FRONT"
    assert lp.angles[1].book.drawn[0].name == "Cape"
    assert np.array_equal(lp.angles[1].book.drawn[0].mask, m)


def test_v2_overwrite_is_atomic(tmp_path):
    projects.save_project("Mini", [], 0, [_angle("a", b"ONE")], root=tmp_path)
    projects.save_project("Mini", [], 0, [_angle("a", b"TWO")], root=tmp_path)
    lp = projects.load_project("mini", root=tmp_path)
    assert len(lp.angles) == 1
    assert lp.angles[0].photo_bytes == b"TWO"
    assert not (tmp_path / ".tmp-mini").exists()


def test_v1_manifest_loads_as_single_angle(tmp_path):
    # Hand-write a legacy v1 project on disk.
    import json
    from mini_highlight_advisor.palette import default_ramp, default_coverage
    d = tmp_path / "legacy"; d.mkdir()
    (d / "photo.png").write_bytes(b"LEGACY")
    manifest = {
        "schema_version": 1, "name": "Legacy Mini", "slug": "legacy",
        "created_at": "t", "updated_at": "t", "photo_file": "photo.png",
        "settings": projects._settings_to_dict(_settings()),
        "book": {"whole": {"palette": projects._palette_to_dicts(default_ramp(5)),
                           "coverage": list(default_coverage(5))},
                 "drawn": [], "selected": 0},
    }
    (d / "manifest.json").write_text(json.dumps(manifest), encoding="utf-8")
    lp = projects.load_project("legacy", root=tmp_path)
    assert lp.paints_pool == []
    assert lp.active_angle == 0
    assert len(lp.angles) == 1
    assert lp.angles[0].label == "Legacy Mini"
    assert lp.angles[0].photo_bytes == b"LEGACY"
    assert lp.angles[0].settings == _settings()


@pytest.mark.parametrize("active,removed,count,expected", [
    (0, 0, 1, 0),   # removing the only angle
    (2, 0, 3, 1),   # active after removed shifts down
    (1, 2, 3, 1),   # active before removed unchanged
    (2, 2, 3, 1),   # removing the active picks the previous
    (0, 1, 3, 0),   # active before removed unchanged (at 0)
])
def test_next_active_index(active, removed, count, expected):
    assert projects.next_active_index(active, removed, count) == expected


def test_list_projects_sorted_by_updated_desc(tmp_path):
    projects.save_project("Alpha", [], 0, [_angle()], root=tmp_path,
                          _now="2026-08-20T10:00:00+00:00")
    projects.save_project("Beta", [], 0, [_angle()], root=tmp_path,
                          _now="2026-08-21T10:00:00+00:00")
    metas = projects.list_projects(root=tmp_path)
    assert [m.name for m in metas] == ["Beta", "Alpha"]
    assert metas[0].slug == "beta"


def test_overwrite_by_name_drops_stale_angle_dirs(tmp_path):
    # Save with two angles, then re-save with one; stale angle_01 must be gone.
    angles_two = [_angle("a", b"A"), _angle("b", b"B")]
    projects.save_project("Same", [], 0, angles_two, root=tmp_path)
    angles_one = [_angle("a", b"A")]
    projects.save_project("Same", [], 0, angles_one, root=tmp_path)
    assert not (tmp_path / "same" / "angle_01").exists()
    lp = projects.load_project("same", root=tmp_path)
    assert len(lp.angles) == 1


def test_delete_project_removes_folder_and_is_idempotent(tmp_path):
    projects.save_project("Gone", [], 0, [_angle()], root=tmp_path)
    projects.delete_project("gone", root=tmp_path)
    assert not (tmp_path / "gone").exists()
    projects.delete_project("gone", root=tmp_path)  # no error second time


def test_list_skips_corrupt_manifest_but_load_raises(tmp_path):
    projects.save_project("Good", [], 0, [_angle()], root=tmp_path)
    bad = tmp_path / "bad"; bad.mkdir()
    (bad / "manifest.json").write_text("{ not json", encoding="utf-8")
    assert [m.slug for m in projects.list_projects(root=tmp_path)] == ["good"]
    with pytest.raises(Exception):
        projects.load_project("bad", root=tmp_path)


def test_load_project_clamps_out_of_range_active_angle(tmp_path):
    """active_angle >= len(angles) in a corrupt/hand-edited manifest must clamp, not IndexError."""
    import json
    angles = [_angle("front", b"F"), _angle("back", b"B")]
    slug = projects.save_project("Clamp Test", [], 1, angles, root=tmp_path)
    # Rewrite manifest.json with an out-of-range active_angle
    mpath = tmp_path / slug / "manifest.json"
    m = json.loads(mpath.read_text(encoding="utf-8"))
    m["active_angle"] = 99
    mpath.write_text(json.dumps(m), encoding="utf-8")
    lp = projects.load_project(slug, root=tmp_path)
    assert lp.active_angle == 1   # clamped to len(angles)-1 = 1


def test_material_round_trips(tmp_path):
    """Material (matte/nmm) survives save/load; old manifests without 'material' default to matte."""
    import numpy as np
    from mini_highlight_advisor.region_state import RegionBook
    from mini_highlight_advisor.palette import default_ramp, default_coverage

    book = _whole_book()
    m = np.zeros((8, 8), bool); m[2:5, 2:5] = True
    book.add(m, "Blade", default_ramp(5), default_coverage(5))
    book.set_material_at(1, "nmm")   # drawn region -> nmm
    book.set_material_at(0, "matte") # whole mini -> matte (explicit)

    angles = [_angle("front", b"PHOTO", book=book)]
    slug = projects.save_project("Material Test", [], 0, angles, root=tmp_path)
    lp = projects.load_project(slug, root=tmp_path)
    reloaded = lp.angles[0].book
    assert reloaded.material_at(1) == "nmm",  "drawn region material must survive round-trip"
    assert reloaded.material_at(0) == "matte", "whole-mini material must survive round-trip"


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
