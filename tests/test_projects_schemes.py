# tests/test_projects_schemes.py
import json
import numpy as np
from mini_highlight_advisor import projects
from mini_highlight_advisor.region_state import new_book
from mini_highlight_advisor.palette import PaintColor, default_ramp, default_coverage
from mini_highlight_advisor.schemes import Scheme


def _angle(tmp_book):
    return projects.AngleData(
        label="a1", photo_bytes=b"\x89PNG\r\n", photo_suffix=".png",
        book=tmp_book,
        settings=projects.ProjectSettings(n=5, edge_hl=True, edge_extreme=False,
                                          edge_sens=0.5, relief_cap=True,
                                          per_region_norm=False))


def test_scheme_roundtrip(tmp_path):
    book = new_book(5)
    m = np.zeros((4, 4), dtype=bool); m[1, 1] = True
    book.add(m, "armour", default_ramp(5), default_coverage(5))
    scheme = Scheme(name="Crimson", anchor="armour",
                    palettes={"Whole mini": default_ramp(5),
                              "armour": [PaintColor("Red", "#ff0000")]})
    projects.save_project("Mini One", [], 0, [_angle(book)],
                          schemes=[scheme], root=tmp_path)
    lp = projects.load_project("mini-one", root=tmp_path)
    assert len(lp.schemes) == 1
    got = lp.schemes[0]
    assert got.name == "Crimson" and got.anchor == "armour"
    assert got.palettes["armour"] == [PaintColor("Red", "#ff0000")]


def test_schema_version_is_4(tmp_path):
    book = new_book(5)
    projects.save_project("Mini Two", [], 0, [_angle(book)],
                          schemes=[], root=tmp_path)
    manifest = json.loads((tmp_path / "mini-two" / "manifest.json").read_text())
    assert manifest["schema_version"] == 4


def test_load_v2_project_without_schemes_key(tmp_path):
    book = new_book(5)
    projects.save_project("Mini Three", [], 0, [_angle(book)], root=tmp_path)
    # Simulate an older manifest: strip schema up to v2 and drop the schemes key.
    mpath = tmp_path / "mini-three" / "manifest.json"
    m = json.loads(mpath.read_text())
    m["schema_version"] = 2
    m.pop("schemes", None)
    mpath.write_text(json.dumps(m))
    lp = projects.load_project("mini-three", root=tmp_path)
    assert lp.schemes == []
