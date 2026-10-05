import pytest
from fastapi.testclient import TestClient
from backend.main import app

_client = TestClient(app)


def _catalog_code():
    r = _client.get("/api/catalog")
    return r.json()["paints"][0]["code"]


def test_match_exact_or_close_when_owned():
    code = _catalog_code()
    r = _client.get("/api/catalog")
    paint = r.json()["paints"][0]
    res = _client.post("/api/match", json={"hex": paint["hex"], "finish": "matte", "owned_codes": [code]})
    assert res.status_code == 200
    body = res.json()
    assert body["tier"] in ("exact", "close")
    assert body["delta_e"] >= 0


def test_match_unreachable_when_no_owned():
    res = _client.post("/api/match", json={"hex": "#ff0000", "finish": "matte", "owned_codes": []})
    assert res.status_code == 200
    assert res.json()["tier"] in ("exact", "close", "mix", "unreachable")


def test_match_rejects_blank_hex():
    res = _client.post("/api/match", json={"hex": "", "finish": "matte", "owned_codes": []})
    assert res.status_code == 422


def test_match_response_has_required_fields():
    res = _client.post("/api/match", json={"hex": "#aabbcc", "finish": "matte", "owned_codes": []})
    body = res.json()
    for field in ("tier", "phrase", "delta_e"):
        assert field in body


def test_match_returns_nearest_catalogue_paints_with_owned_flag():
    paint = _client.get("/api/catalog").json()["paints"][0]
    res = _client.post("/api/match", json={"hex": paint["hex"], "finish": paint["finish"],
                                           "owned_codes": [paint["code"]]})
    nearest = res.json()["nearest"]
    assert len(nearest) == 3
    assert nearest[0]["delta_e"] <= nearest[1]["delta_e"] <= nearest[2]["delta_e"]
    assert nearest[0]["delta_e"] == 0.0
    assert any(n["code"] == paint["code"] and n["owned"] for n in nearest)
    assert all({"name", "hex", "code", "brand"} <= n.keys() for n in nearest)
