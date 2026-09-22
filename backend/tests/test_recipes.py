import json
import pytest
from pathlib import Path
from fastapi.testclient import TestClient
from backend.main import app

_client = TestClient(app)


@pytest.fixture(autouse=True)
def _isolate_recipes(tmp_path, monkeypatch):
    monkeypatch.setattr("mini_highlight_advisor.recipes.USER_PATH", tmp_path / "recipes.json")


def test_list_recipes_returns_list():
    r = _client.get("/api/recipes")
    assert r.status_code == 200
    assert isinstance(r.json()["recipes"], list)


def test_save_and_list_recipe():
    payload = {"name": "__test_recipe__", "steps": [{"label": "base", "hex": "#8b4513", "paint_ref": None}]}
    r = _client.post("/api/recipes", json=payload)
    assert r.status_code == 200
    assert r.json()["ok"] is True
    names = [rec["name"] for rec in _client.get("/api/recipes").json()["recipes"]]
    assert "__test_recipe__" in names


def test_export_recipes_bytes():
    r = _client.get("/api/recipes/export")
    assert r.status_code == 200
    assert r.headers["content-type"].startswith("application/json")
    parsed = json.loads(r.content)
    assert "recipes" in parsed


def test_import_recipes_merges():
    data = json.dumps({"recipes": [{"name": "__imported__", "steps": [{"label": "l", "hex": "#aabbcc"}]}]}).encode()
    r = _client.post("/api/recipes/import", files={"file": ("r.json", data, "application/json")})
    assert r.status_code == 200
    names = [rec["name"] for rec in r.json()["recipes"]]
    assert "__imported__" in names
