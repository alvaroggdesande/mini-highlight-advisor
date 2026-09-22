from fastapi.testclient import TestClient
from backend.main import app

_client = TestClient(app)


def test_catalog_returns_nonempty_list():
    r = _client.get("/api/catalog")
    assert r.status_code == 200
    paints = r.json()["paints"]
    assert len(paints) > 0


def test_catalog_entries_have_required_fields():
    r = _client.get("/api/catalog")
    p = r.json()["paints"][0]
    for field in ("name", "hex", "code", "finish"):
        assert field in p, f"missing {field}"
