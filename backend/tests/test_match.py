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


def test_match_mix_returns_structured_recipe_for_client_phrasing():
    from mini_highlight_advisor.color import lab_of_hex, linear_blend
    paints = [p for p in _client.get("/api/catalog").json()["paints"] if p["finish"] == "matte"]
    # Two far-apart owned paints; target their 1:1 blend so only a mix reaches it.
    a = min(paints, key=lambda p: lab_of_hex(p["hex"])[0])
    b = max(paints, key=lambda p: lab_of_hex(p["hex"])[0])
    rgb = lambda h: tuple(int(h[i:i + 2], 16) for i in (1, 3, 5))
    mid = linear_blend([rgb(a["hex"]), rgb(b["hex"])], [1, 1])
    hexv = "#" + "".join(f"{round(c):02x}" for c in mid)
    body = _client.post("/api/match", json={"hex": hexv, "finish": "matte",
                                            "owned_codes": [a["code"], b["code"]]}).json()
    assert body["tier"] == "mix"
    assert sorted(body["mix"]["names"]) == sorted([a["name"], b["name"]])
    assert len(body["mix"]["parts"]) == 2
    assert body["mix"]["tint"] is False


def test_match_non_mix_has_null_mix():
    paint = _client.get("/api/catalog").json()["paints"][0]
    body = _client.post("/api/match", json={"hex": paint["hex"], "finish": paint["finish"],
                                            "owned_codes": [paint["code"]]}).json()
    assert body["mix"] is None
