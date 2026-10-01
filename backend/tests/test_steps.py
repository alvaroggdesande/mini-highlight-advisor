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


def test_plans_manifest_unknown_token_returns_409():
    r = client.get("/api/plans", params={"token": "deadbeef"})
    assert r.status_code == 409


def test_plans_manifest_lists_plan_names():
    token = _upload_and_analyze(n_bands=2)
    r = client.get("/api/plans", params={"token": token})
    assert r.status_code == 200
    body = r.json()
    assert "plans" in body
    names = [p["name"] for p in body["plans"]]
    assert names == ["Whole mini"]  # single-region synthetic photo


def test_plans_manifest_carries_no_step_images():
    # The manifest must be cheap: names only, no rendered step payload.
    token = _upload_and_analyze(n_bands=2)
    body = client.get("/api/plans", params={"token": token}).json()
    assert "steps" not in body["plans"][0]


def test_steps_plan_filter_returns_only_that_plan():
    token = _upload_and_analyze(n_bands=2)
    r = client.get("/api/steps", params={"token": token, "plan": "Whole mini"})
    assert r.status_code == 200
    plans = r.json()["plans"]
    assert [p["name"] for p in plans] == ["Whole mini"]
    assert len(plans[0]["steps"]) >= 1


def test_steps_plan_filter_matches_unfiltered_plan():
    token = _upload_and_analyze(n_bands=2)
    full = client.get("/api/steps", params={"token": token}).json()["plans"]
    whole = next(p for p in full if p["name"] == "Whole mini")
    filtered = client.get(
        "/api/steps", params={"token": token, "plan": "Whole mini"}
    ).json()["plans"][0]
    assert filtered["roles"] == whole["roles"]
    assert len(filtered["steps"]) == len(whole["steps"])


def test_steps_plan_filter_unknown_name_returns_404():
    token = _upload_and_analyze(n_bands=2)
    r = client.get("/api/steps", params={"token": token, "plan": "nope"})
    assert r.status_code == 404


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


def _analyze_with(n_bands: int, settings: dict) -> str:
    r = client.post("/api/photo", files={"file": ("m.png", _png_bytes(), "image/png")})
    photo_id = r.json()["photo_id"]
    palette = [{"name": f"p{i}", "hex": f"#{20 + 40 * i:02x}{20 + 40 * i:02x}{20 + 40 * i:02x}",
                "code": f"C{i}"} for i in range(n_bands)]
    req = {"photo_id": photo_id,
           "whole": {"palette": palette, "coverage": [1.0 / n_bands] * n_bands, "material": "matte"},
           "settings": settings}
    r = client.post("/api/analyze", json=req)
    assert r.status_code == 200
    return r.json()["result_token"]


def test_band_steps_carry_their_paint():
    token = _analyze_with(3, {"edge_hl": False, "relief_cap": False})
    steps = client.get("/api/steps", params={"token": token}).json()["plans"][0]["steps"]
    bands = [s for s in steps if s["kind"] == "band"]
    assert [s["paint_name"] for s in bands] == ["p0", "p1", "p2"]
    assert [s["paint_code"] for s in bands] == ["C0", "C1", "C2"]
    assert all(s["paint_hex"].startswith("#") for s in bands)


def test_single_edge_step_uses_lightest_paint():
    token = _analyze_with(3, {"edge_hl": True, "edge_extreme": False, "relief_cap": False})
    steps = client.get("/api/steps", params={"token": token}).json()["plans"][0]["steps"]
    edges = [s for s in steps if s["kind"] == "edge"]
    assert len(edges) == 1
    assert edges[0]["paint_name"] == "p2"


def test_two_tier_edge_steps_use_top_two_paints():
    token = _analyze_with(5, {"edge_hl": True, "edge_extreme": True, "relief_cap": False})
    steps = client.get("/api/steps", params={"token": token}).json()["plans"][0]["steps"]
    edges = [s for s in steps if s["kind"] == "edge"]
    assert [s["paint_name"] for s in edges] == ["p3", "p4"]


def test_step_paint_out_of_range_and_missing_palette_is_none():
    from types import SimpleNamespace
    from backend.main import _step_paint
    from mini_highlight_advisor.palette import PaintColor

    plan = SimpleNamespace(palette=[PaintColor("only", "#101010")])
    band5 = SimpleNamespace(kind="band", index=5, label=None)
    assert _step_paint(plan, band5, edge_pos=None, n_edges=0) is None
    assert _step_paint(SimpleNamespace(palette=None), band5, None, 0) is None
    shade = SimpleNamespace(kind="shade", index=1, label="Recess Shade")
    assert _step_paint(plan, shade, None, 0) is None
