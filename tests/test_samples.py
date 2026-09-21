from pathlib import Path
import pytest
from mini_highlight_advisor.samples import list_photos, list_projects, SamplePhoto, SampleProject


def test_list_photos_empty_when_dir_absent(tmp_path, monkeypatch):
    monkeypatch.setattr("mini_highlight_advisor.samples._PHOTOS_DIR", tmp_path / "nope")
    assert list_photos() == []


def test_list_projects_empty_when_dir_absent(tmp_path, monkeypatch):
    monkeypatch.setattr("mini_highlight_advisor.samples._PROJECTS_DIR", tmp_path / "nope")
    assert list_projects() == []


def test_list_photos_returns_images_only(tmp_path, monkeypatch):
    photos = tmp_path / "photos"
    photos.mkdir()
    (photos / "rat-ogre.jpg").write_bytes(b"fake")
    (photos / "ignored.txt").write_bytes(b"ignored")
    monkeypatch.setattr("mini_highlight_advisor.samples._PHOTOS_DIR", photos)
    result = list_photos()
    assert len(result) == 1
    assert isinstance(result[0], SamplePhoto)
    assert result[0].name == "Rat Ogre"
    assert result[0].path.name == "rat-ogre.jpg"


def test_list_projects_returns_json_only(tmp_path, monkeypatch):
    projs = tmp_path / "projects"
    projs.mkdir()
    (projs / "rat-ogre.json").write_text("{}")
    (projs / "ignored.txt").write_text("ignored")
    monkeypatch.setattr("mini_highlight_advisor.samples._PROJECTS_DIR", projs)
    result = list_projects()
    assert len(result) == 1
    assert isinstance(result[0], SampleProject)
    assert result[0].name == "Rat Ogre"


def test_list_photos_sorted_alphabetically(tmp_path, monkeypatch):
    photos = tmp_path / "photos"
    photos.mkdir()
    (photos / "b-mini.png").write_bytes(b"")
    (photos / "a-mini.png").write_bytes(b"")
    monkeypatch.setattr("mini_highlight_advisor.samples._PHOTOS_DIR", photos)
    result = list_photos()
    assert result[0].name == "A Mini"
    assert result[1].name == "B Mini"


def test_list_photos_skips_gitkeep(tmp_path, monkeypatch):
    photos = tmp_path / "photos"
    photos.mkdir()
    (photos / ".gitkeep").write_bytes(b"")
    monkeypatch.setattr("mini_highlight_advisor.samples._PHOTOS_DIR", photos)
    assert list_photos() == []
