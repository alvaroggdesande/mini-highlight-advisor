import base64
import io

import numpy as np
from PIL import Image


def to_png_bytes(arr) -> bytes:
    img = Image.fromarray(np.asarray(arr).astype("uint8")) if isinstance(arr, np.ndarray) else arr
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return buf.getvalue()


def png_data_uri(arr) -> str:
    return "data:image/png;base64," + base64.b64encode(to_png_bytes(arr)).decode("ascii")
