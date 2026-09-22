import base64
import numpy as np
from PIL import Image
from backend.serialize import to_png_bytes, png_data_uri


def test_png_data_uri_from_ndarray():
    arr = np.zeros((4, 4, 3), dtype=np.uint8)
    uri = png_data_uri(arr)
    assert uri.startswith("data:image/png;base64,")
    raw = base64.b64decode(uri.split(",", 1)[1])
    assert Image.open(__import__("io").BytesIO(raw)).size == (4, 4)


def test_to_png_bytes_from_pil():
    img = Image.new("RGB", (2, 3))
    assert to_png_bytes(img)[:8] == b"\x89PNG\r\n\x1a\n"
