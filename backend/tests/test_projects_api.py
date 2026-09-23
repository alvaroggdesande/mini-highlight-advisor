import io
import json

import numpy as np
import pytest
from fastapi.testclient import TestClient
from PIL import Image

from backend import project_store
from backend.main import app

_client = TestClient(app)


def _png_bytes():
    arr = (np.random.default_rng(99).integers(0, 255, (32, 24, 3))).astype("uint8")
    buf = io.BytesIO()
    Image.fromarray(arr).save(buf, format="PNG")
    return buf.getvalue()


@pytest.fixture(autouse=True)
def patch_store(tmp_path, monkeypatch):
    monkeypatch.setattr(project_store, "PHOTOS_DIR", tmp_path / "photos")
    monkeypatch.setattr(project_store, "PROJECTS_DIR", tmp_path / "projects")


def _upload() -> str:
    r = _client.post("/api/photo", files={"file": ("m.png", _png_bytes(), "image/png")})
    assert r.status_code == 200
    return r.json()["photo_id"]


def _angle(photo_id: str) -> dict:
    return {
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


# ── photo upload persists to disk ─────────────────────────────────────────────

def test_upload_persists_photo_to_disk():
    pid = _upload()
    result = project_store.load_photo_bytes(pid)
    assert result is not None
    data_bytes, suffix = result
    assert suffix == ".png"
    assert len(data_bytes) > 0


# ── list ──────────────────────────────────────────────────────────────────────

def test_list_projects_empty():
    r = _client.get("/api/projects")
    assert r.status_code == 200
    assert r.json() == {"projects": []}


# ── save ──────────────────────────────────────────────────────────────────────

def test_save_project_returns_slug():
    pid = _upload()
    r = _client.put("/api/projects", json={"name": "My Mini", "active_angle": 0, "angles": [_angle(pid)]})
    assert r.status_code == 200
    body = r.json()
    assert body["slug"] == "my-mini"
    assert body["name"] == "My Mini"
    assert "updated_at" in body


def test_save_project_appears_in_list():
    pid = _upload()
    _client.put("/api/projects", json={"name": "Listed", "active_angle": 0, "angles": [_angle(pid)]})
    r = _client.get("/api/projects")
    projects = r.json()["projects"]
    assert len(projects) == 1
    assert projects[0]["slug"] == "listed"


def test_save_project_missing_photo_id_returns_409():
    r = _client.put("/api/projects", json={
        "name": "Bad", "active_angle": 0,
        "angles": [{"id": "a1", "label": "angle 1", "photo_id": "deadbeef0000dead",
                    "book": {}, "settings": {}}],
    })
    assert r.status_code == 409


def test_save_project_angle_without_photo_id_is_ok():
    # angle with no photo yet (e.g. not uploaded) — server skips validation
    r = _client.put("/api/projects", json={
        "name": "NoPhoto", "active_angle": 0,
        "angles": [{"id": "a1", "label": "angle 1",
                    "book": {}, "settings": {}}],
    })
    assert r.status_code == 200


# ── load ──────────────────────────────────────────────────────────────────────

def test_load_project_returns_manifest():
    pid = _upload()
    _client.put("/api/projects", json={"name": "Load Me", "active_angle": 0, "angles": [_angle(pid)]})
    r = _client.get("/api/projects/load-me")
    assert r.status_code == 200
    body = r.json()
    assert body["name"] == "Load Me"
    assert body["slug"] == "load-me"
    assert len(body["angles"]) == 1
    assert body["angles"][0]["photo_id"] == pid


def test_load_project_not_found():
    r = _client.get("/api/projects/no-such-project")
    assert r.status_code == 404


# ── delete ────────────────────────────────────────────────────────────────────

def test_delete_project():
    pid = _upload()
    _client.put("/api/projects", json={"name": "Delete Me", "active_angle": 0, "angles": [_angle(pid)]})
    r = _client.delete("/api/projects/delete-me")
    assert r.status_code == 200
    assert _client.get("/api/projects/delete-me").status_code == 404


# ── download / upload blob ────────────────────────────────────────────────────

def test_download_project_blob():
    pid = _upload()
    _client.put("/api/projects", json={"name": "Download Me", "active_angle": 0, "angles": [_angle(pid)]})
    r = _client.get("/api/projects/download-me/download")
    assert r.status_code == 200
    assert r.headers["content-type"].startswith("application/json")
    data = json.loads(r.content)
    assert data["name"] == "Download Me"
    assert pid in data.get("photos", {})


def test_download_missing_project_404():
    r = _client.get("/api/projects/ghost/download")
    assert r.status_code == 404


def test_upload_blob_restores_project():
    pid = _upload()
    _client.put("/api/projects", json={"name": "Round Trip", "active_angle": 0, "angles": [_angle(pid)]})
    blob = _client.get("/api/projects/round-trip/download").content

    # delete and re-upload
    _client.delete("/api/projects/round-trip")
    r = _client.post("/api/projects/upload",
                     files={"file": ("round-trip.json", blob, "application/json")})
    assert r.status_code == 200
    body = r.json()
    assert body["name"] == "Round Trip"
    assert body["slug"] == "round-trip"
    assert len(body["angles"]) == 1


def test_upload_invalid_blob_422():
    r = _client.post("/api/projects/upload",
                     files={"file": ("bad.json", b"not json", "application/json")})
    assert r.status_code == 422


def test_upload_blob_missing_name_422():
    import json as _json
    bad_blob = _json.dumps({"schema_version": 6, "active_angle": 0, "angles": []}).encode()
    r = _client.post("/api/projects/upload",
                     files={"file": ("bad.json", bad_blob, "application/json")})
    assert r.status_code == 422
