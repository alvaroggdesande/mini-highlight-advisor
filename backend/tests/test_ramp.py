import re
from fastapi.testclient import TestClient
from backend.main import app

_client = TestClient(app)
_HEX = re.compile(r"^#[0-9a-fA-F]{6}$")


def _ramp(variant: str, n: int = 5, midtone: str = "#808080"):
    return _client.post("/api/ramp/generate", json={"midtone_hex": midtone, "n": n, "variant": variant})


def test_ramp_returns_correct_length():
    for variant in ("ramp", "complementary", "warm", "cool"):
        r = _ramp(variant, n=5)
        assert r.status_code == 200, variant
        hexes = r.json()["hexes"]
        assert len(hexes) == 5, variant


def test_ramp_hexes_are_valid_css():
    hexes = _ramp("ramp", n=3).json()["hexes"]
    for h in hexes:
        assert _HEX.match(h), f"invalid hex: {h}"


def test_ramp_blend_hexes_overrides_midtone():
    r = _client.post("/api/ramp/generate", json={
        "midtone_hex": "#000000",  # ignored when blend_hexes set
        "n": 3,
        "variant": "ramp",
        "blend_hexes": ["#200000", "#ff8080"],
    })
    assert r.status_code == 200
    assert len(r.json()["hexes"]) == 3
