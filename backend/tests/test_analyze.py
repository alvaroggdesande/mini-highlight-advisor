import io
import numpy as np
from PIL import Image
from fastapi.testclient import TestClient
from backend.main import app

client = TestClient(app)


def _upload():
    arr = (np.random.default_rng(1).integers(0, 255, (40, 30, 3))).astype("uint8")
    buf = io.BytesIO(); Image.fromarray(arr).save(buf, format="PNG")
    return client.post("/api/photo", files={"file": ("m.png", buf.getvalue(), "image/png")}).json()


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
