from fastapi.testclient import TestClient
from backend.main import app

_client = TestClient(app)


def _spec(name: str, surface: str = "skin", n_bands: int = 3, is_anchor: bool = False):
    return {"region_name": name, "surface": surface, "n_bands": n_bands, "is_anchor": is_anchor}


def test_scheme_single_region():
    r = _client.post("/api/scheme/generate", json={
        "specs": [_spec("Whole Mini", is_anchor=True)],
        "anchor_name": "Whole Mini",
        "anchor_hex": "#c0392b",
        "mood": "neutral",
        "variant": "complementary",
        "owned_codes": [],
    })
    assert r.status_code == 200
    palettes = r.json()["palettes"]
    assert "Whole Mini" in palettes
    assert len(palettes["Whole Mini"]) == 3


def test_scheme_multi_region_returns_all_keys():
    r = _client.post("/api/scheme/generate", json={
        "specs": [_spec("Whole Mini", is_anchor=True), _spec("helmet", surface="metal")],
        "anchor_name": "Whole Mini",
        "anchor_hex": "#c0392b",
        "mood": "heroic",
        "variant": "analogous",
        "owned_codes": [],
    })
    assert r.status_code == 200
    palettes = r.json()["palettes"]
    assert "Whole Mini" in palettes
    assert "helmet" in palettes
