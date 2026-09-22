import json
from fastapi.testclient import TestClient
from backend.main import app

_client = TestClient(app)


def test_get_collection_returns_list():
    r = _client.get("/api/collection")
    assert r.status_code == 200
    assert isinstance(r.json()["owned"], list)


def test_put_collection_round_trip():
    r = _client.get("/api/catalog")
    code = r.json()["paints"][0]["code"]
    _client.put("/api/collection", json={"owned": [code]})
    owned = _client.get("/api/collection").json()["owned"]
    assert code in owned


def test_export_import_collection_round_trip():
    r = _client.get("/api/catalog")
    code = r.json()["paints"][0]["code"]
    _client.put("/api/collection", json={"owned": [code]})
    export = _client.get("/api/collection/export")
    assert export.status_code == 200
    data = export.content
    r2 = _client.post("/api/collection/import", files={"file": ("c.json", data, "application/json")})
    assert r2.status_code == 200
    assert code in r2.json()["owned"]
