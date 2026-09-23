import io
import numpy as np
from PIL import Image
from fastapi.testclient import TestClient
from backend.main import app

client = TestClient(app)


def _png_bytes(w: int = 30, h: int = 40) -> bytes:
    rng = np.random.default_rng(2)
    rgb = rng.integers(0, 255, (h, w, 3), dtype=np.uint8)
    # Full-opacity alpha so mask_from_alpha is used (GrabCut fails on tiny noise).
    alpha = np.full((h, w, 1), 255, dtype=np.uint8)
    rgba = np.concatenate([rgb, alpha], axis=-1)
    buf = io.BytesIO()
    Image.fromarray(rgba, mode="RGBA").save(buf, format="PNG")
    return buf.getvalue()


def _upload_and_analyze(n_bands: int = 2) -> str:
    """Upload a synthetic photo, run analyze (edge_hl=False), return result_token."""
    data = _png_bytes()
    r = client.post("/api/photo", files={"file": ("m.png", data, "image/png")})
    assert r.status_code == 200
    photo_id = r.json()["photo_id"]

    palette = [{"name": f"p{i}", "hex": "#202020" if i == 0 else "#e0e0e0"}
               for i in range(n_bands)]
    coverage = [1.0 / n_bands] * n_bands
    req = {
        "photo_id": photo_id,
        "whole": {"palette": palette, "coverage": coverage, "material": "matte"},
        "settings": {"edge_hl": False},
    }
    r = client.post("/api/analyze", json=req)
    assert r.status_code == 200
    return r.json()["result_token"]


def test_steps_unknown_token_returns_409():
    r = client.get("/api/steps", params={"token": "deadbeef"})
    assert r.status_code == 409


def test_steps_returns_plans_with_steps():
    token = _upload_and_analyze(n_bands=2)
    r = client.get("/api/steps", params={"token": token})
    assert r.status_code == 200
    body = r.json()
    assert "plans" in body
    assert len(body["plans"]) >= 1  # at least the WHOLE_MINI plan
    plan = body["plans"][0]
    assert "name" in plan
    assert "roles" in plan
    assert "coverage" in plan
    assert "steps" in plan
    assert len(plan["steps"]) >= 1


def test_steps_images_are_base64_png():
    token = _upload_and_analyze(n_bands=2)
    body = client.get("/api/steps", params={"token": token}).json()
    step = body["plans"][0]["steps"][0]
    assert step["zone_png"].startswith("data:image/png;base64,")
    assert step["cumulative_png"].startswith("data:image/png;base64,")


def test_steps_last_step_has_no_exact_png():
    token = _upload_and_analyze(n_bands=2)
    body = client.get("/api/steps", params={"token": token}).json()
    # edge_hl=False: only 2 band steps. Step index 1 is last.
    band_steps = [s for s in body["plans"][0]["steps"] if s["kind"] == "band"]
    last = band_steps[-1]
    assert last["is_last"] is True
    assert last["exact_png"] is None


def test_steps_non_last_step_has_exact_png():
    token = _upload_and_analyze(n_bands=2)
    body = client.get("/api/steps", params={"token": token}).json()
    band_steps = [s for s in body["plans"][0]["steps"] if s["kind"] == "band"]
    first = band_steps[0]
    assert first["is_last"] is False
    assert first["exact_png"] is not None
    assert first["exact_png"].startswith("data:image/png;base64,")


def test_steps_band_step_label_matches_role():
    token = _upload_and_analyze(n_bands=2)
    body = client.get("/api/steps", params={"token": token}).json()
    plan = body["plans"][0]
    band_steps = [s for s in plan["steps"] if s["kind"] == "band"]
    for step in band_steps:
        assert step["label"] == plan["roles"][step["index"]]


def test_steps_edge_hl_adds_edge_step():
    data = _png_bytes()
    r = client.post("/api/photo", files={"file": ("m.png", data, "image/png")})
    photo_id = r.json()["photo_id"]
    req = {
        "photo_id": photo_id,
        "whole": {"palette": [{"name": "a", "hex": "#202020"}, {"name": "b", "hex": "#e0e0e0"}],
                  "coverage": [0.5, 0.5], "material": "matte"},
        "settings": {"edge_hl": True},
    }
    token = client.post("/api/analyze", json=req).json()["result_token"]
    body = client.get("/api/steps", params={"token": token}).json()
    kinds = [s["kind"] for s in body["plans"][0]["steps"]]
    assert "edge" in kinds
