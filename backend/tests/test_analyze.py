import io
import numpy as np
from PIL import Image
from fastapi.testclient import TestClient
from mini_highlight_advisor import samples
from backend.main import app, mask_cache

client = TestClient(app)


def _upload():
    arr = (np.random.default_rng(1).integers(0, 255, (40, 30, 3))).astype("uint8")
    buf = io.BytesIO(); Image.fromarray(arr).save(buf, format="PNG")
    return client.post("/api/photo", files={"file": ("m.png", buf.getvalue(), "image/png")}).json()


def _upload_sample() -> tuple[str, int, int]:
    photo = samples.list_photos()[0]
    with open(photo.path, "rb") as fh:
        r = client.post("/api/photo", files={"file": (photo.path.name, fh.read(), "image/png")})
    assert r.status_code == 200
    j = r.json()
    return j["photo_id"], j["width"], j["height"]


def _whole():
    return {"palette": [{"name": "a", "hex": "#202020"}, {"name": "b", "hex": "#e0e0e0"}],
            "coverage": [0.5, 0.5], "material": "matte"}


def test_analyze_returns_preview_and_token():
    up = _upload()
    req = {"photo_id": up["photo_id"], "whole": up["default_whole"]}
    r = client.post("/api/analyze", json=req)
    assert r.status_code == 200
    body = r.json()
    assert body["preview_png"].startswith("data:image/png;base64,")
    assert len(body["result_token"]) == 16


def test_analyze_unknown_photo_404():
    req = {"photo_id": "deadbeefdeadbeef",
           "whole": {"palette": [{"name": "a", "hex": "#101010"}], "coverage": [1.0]}}
    assert client.post("/api/analyze", json=req).status_code == 404


def test_analyze_with_region_returns_preview_and_token():
    pid, w, h = _upload_sample()
    ring = [[w * 0.3, h * 0.3], [w * 0.7, h * 0.3], [w * 0.7, h * 0.7], [w * 0.3, h * 0.7]]
    req = {"photo_id": pid, "whole": _whole(),
           "regions": [{"name": "helmet", "rings": [ring],
                        "palette": _whole()["palette"], "coverage": [0.5, 0.5], "material": "matte"}],
           "settings": {}}
    r = client.post("/api/analyze", json=req)
    assert r.status_code == 200
    body = r.json()
    assert body["preview_png"].startswith("data:image/png;base64,")
    assert len(body["result_token"]) == 16


def test_analyze_mask_cache_hits_on_identical_rings():
    pid, w, h = _upload_sample()
    ring = [[w * 0.3, h * 0.3], [w * 0.7, h * 0.3], [w * 0.7, h * 0.7], [w * 0.3, h * 0.7]]
    region = {"name": "r", "rings": [ring], "palette": _whole()["palette"],
              "coverage": [0.5, 0.5], "material": "matte"}
    req = {"photo_id": pid, "whole": _whole(), "regions": [region], "settings": {}}
    mask_cache._d.clear()
    client.post("/api/analyze", json=req)
    n_after_first = len(mask_cache._d)
    client.post("/api/analyze", json=req)  # identical rings -> no new cache entry
    assert len(mask_cache._d) == n_after_first == 1
