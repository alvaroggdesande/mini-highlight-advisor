import io
import json
import numpy as np
import pytest
from PIL import Image
from backend import project_store as ps


def _png_bytes():
    arr = (np.random.default_rng(42).integers(0, 255, (32, 24, 3))).astype("uint8")
    buf = io.BytesIO()
    Image.fromarray(arr).save(buf, format="PNG")
    return buf.getvalue()


@pytest.fixture(autouse=True)
def tmp_store(tmp_path, monkeypatch):
    monkeypatch.setattr(ps, "PHOTOS_DIR", tmp_path / "photos")
    monkeypatch.setattr(ps, "PROJECTS_DIR", tmp_path / "projects")


def _minimal_manifest(name="Test", photo_id="ph001"):
    return {
        "schema_version": 6,
        "name": name,
        "active_angle": 0,
        "angles": [
            {
                "id": "a1",
                "label": "angle 1",
                "photo_id": photo_id,
                "book": {
                    "whole": {"palette": [], "coverage": [], "material": "matte"},
                    "drawn": [],
                    "selected": 0,
                    "schemes": [],
                },
                "settings": {
                    "edge_hl": True, "edge_extreme": False, "edge_sens": 0.5,
                    "relief_cap": True, "per_region_norm": False,
                },
            }
        ],
    }


# ── photo store ──────────────────────────────────────────────────────────────

def test_save_and_load_photo():
    ps.save_photo("abc123", ".jpg", b"fake-jpeg")
    result = ps.load_photo_bytes("abc123")
    assert result == (b"fake-jpeg", ".jpg")


def test_load_photo_missing():
    assert ps.load_photo_bytes("nonexistent") is None


def test_load_photo_missing_dir():
    # PHOTOS_DIR doesn't exist yet — must not crash
    assert ps.load_photo_bytes("anything") is None


def test_save_photo_twice_overwrites():
    ps.save_photo("x", ".png", b"v1")
    ps.save_photo("x", ".png", b"v2")
    assert ps.load_photo_bytes("x") == (b"v2", ".png")


# ── slugify ───────────────────────────────────────────────────────────────────

def test_slugify_normal():
    assert ps.slugify("My Cool Mini") == "my-cool-mini"


def test_slugify_strips_special():
    assert ps.slugify("  Héros!!  ") == "h-ros"


def test_slugify_empty_raises():
    with pytest.raises(ValueError):
        ps.slugify("!!!")


def test_slugify_empty_string_raises():
    with pytest.raises(ValueError):
        ps.slugify("")


# ── project CRUD ──────────────────────────────────────────────────────────────

def test_save_and_list_project():
    slug = ps.save_project("My Mini", _minimal_manifest("My Mini"))
    assert slug == "my-mini"
    projects = ps.list_projects()
    assert len(projects) == 1
    assert projects[0]["slug"] == "my-mini"
    assert projects[0]["name"] == "My Mini"
    assert "updated_at" in projects[0]


def test_list_projects_empty():
    assert ps.list_projects() == []


def test_list_skips_non_v6():
    import os, json as _json
    ps.PROJECTS_DIR.mkdir(parents=True, exist_ok=True)
    old_dir = ps.PROJECTS_DIR / "old-project"
    old_dir.mkdir()
    (old_dir / "manifest.json").write_text(
        _json.dumps({"schema_version": 5, "name": "old", "slug": "old-project", "updated_at": "2020-01-01T00:00:00Z"}),
        encoding="utf-8",
    )
    assert ps.list_projects() == []


def test_save_overwrites_existing():
    ps.save_project("proj", _minimal_manifest("proj"))
    ps.save_project("proj", _minimal_manifest("proj"))  # second save
    assert len(ps.list_projects()) == 1


def test_load_project():
    ps.save_project("Load Me", _minimal_manifest("Load Me"))
    m = ps.load_project("load-me")
    assert m["name"] == "Load Me"
    assert m["slug"] == "load-me"
    assert m["schema_version"] == 6


def test_load_project_not_found():
    with pytest.raises(FileNotFoundError):
        ps.load_project("nonexistent")


def test_load_project_wrong_version():
    import json as _json
    ps.PROJECTS_DIR.mkdir(parents=True, exist_ok=True)
    d = ps.PROJECTS_DIR / "old"
    d.mkdir()
    (d / "manifest.json").write_text(
        _json.dumps({"schema_version": 5, "name": "old", "slug": "old", "updated_at": ""}),
        encoding="utf-8",
    )
    with pytest.raises(ValueError):
        ps.load_project("old")


def test_delete_project():
    ps.save_project("Del", _minimal_manifest("Del"))
    ps.delete_project("del")
    assert ps.list_projects() == []


def test_delete_nonexistent_is_silent():
    ps.delete_project("ghost")  # must not raise


# ── blob round-trip ───────────────────────────────────────────────────────────

def test_project_to_blob_embeds_photo():
    png = _png_bytes()
    ps.save_photo("ph001", ".png", png)
    ps.save_project("Blob Test", _minimal_manifest("Blob Test", photo_id="ph001"))
    blob = ps.project_to_blob("blob-test")
    data = json.loads(blob)
    assert data["name"] == "Blob Test"
    assert "photos" in data
    assert "ph001" in data["photos"]
    assert data["photos"]["ph001"]["suffix"] == ".png"


def test_project_from_blob_roundtrip():
    png = _png_bytes()
    ps.save_photo("ph001", ".png", png)
    ps.save_project("RT", _minimal_manifest("RT", photo_id="ph001"))
    blob = ps.project_to_blob("rt")

    manifest, photos = ps.project_from_blob(blob)
    assert manifest["name"] == "RT"
    assert "photos" not in manifest          # stripped from manifest
    assert "ph001" in photos
    suffix, photo_bytes = photos["ph001"]
    assert suffix == ".png"
    assert photo_bytes == png


def test_project_to_blob_missing_photo_skips_gracefully():
    # photo_id in manifest but no file on disk → blob produced, photos key absent for that id
    ps.save_project("No Photo", _minimal_manifest("No Photo", photo_id="missing"))
    blob = ps.project_to_blob("no-photo")
    data = json.loads(blob)
    assert "missing" not in data.get("photos", {})
