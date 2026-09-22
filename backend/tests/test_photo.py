import io
import pytest
import numpy as np
from PIL import Image
from fastapi.testclient import TestClient
from backend.main import app
from mini_highlight_advisor import samples

_client = TestClient(app)


@pytest.fixture
def client():
    return TestClient(app)


def _png_bytes():
    arr = (np.random.default_rng(0).integers(0, 255, (32, 24, 3))).astype("uint8")
    buf = io.BytesIO()
    Image.fromarray(arr).save(buf, format="PNG")
    return buf.getvalue()


def test_upload_returns_id_dims_and_defaults():
    r = _client.post("/api/photo", files={"file": ("m.png", _png_bytes(), "image/png")})
    assert r.status_code == 200
    body = r.json()
    assert len(body["photo_id"]) == 16
    assert body["width"] == 24 and body["height"] == 32
    assert isinstance(body["quality_checks"], list)
    assert body["default_whole"]["material"] == "matte"


def test_same_bytes_same_id():
    data = _png_bytes()
    a = _client.post("/api/photo", files={"file": ("m.png", data, "image/png")}).json()
    b = _client.post("/api/photo", files={"file": ("m.png", data, "image/png")}).json()
    assert a["photo_id"] == b["photo_id"]


def test_photo_image_returns_png_for_known_id(client):
    photo = samples.list_photos()[0]
    with open(photo.path, "rb") as fh:
        pid = client.post("/api/photo", files={"file": (photo.path.name, fh.read(), "image/png")}).json()["photo_id"]
    r = client.get(f"/api/photo/{pid}/image")
    assert r.status_code == 200
    assert r.headers["content-type"] == "image/png"
    assert r.content[:8] == b"\x89PNG\r\n\x1a\n"


def test_photo_image_404_for_unknown_id(client):
    r = client.get("/api/photo/deadbeef/image")
    assert r.status_code == 404
