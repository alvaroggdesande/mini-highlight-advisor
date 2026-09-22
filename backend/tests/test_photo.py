import io
import numpy as np
from PIL import Image
from fastapi.testclient import TestClient
from backend.main import app

client = TestClient(app)


def _png_bytes():
    arr = (np.random.default_rng(0).integers(0, 255, (32, 24, 3))).astype("uint8")
    buf = io.BytesIO()
    Image.fromarray(arr).save(buf, format="PNG")
    return buf.getvalue()


def test_upload_returns_id_dims_and_defaults():
    r = client.post("/api/photo", files={"file": ("m.png", _png_bytes(), "image/png")})
    assert r.status_code == 200
    body = r.json()
    assert len(body["photo_id"]) == 16
    assert body["width"] == 24 and body["height"] == 32
    assert isinstance(body["quality_checks"], list)
    assert body["default_whole"]["material"] == "matte"


def test_same_bytes_same_id():
    data = _png_bytes()
    a = client.post("/api/photo", files={"file": ("m.png", data, "image/png")}).json()
    b = client.post("/api/photo", files={"file": ("m.png", data, "image/png")}).json()
    assert a["photo_id"] == b["photo_id"]
