import os
import tempfile

import numpy as np

from mini_highlight_advisor.masking import load_image
from mini_highlight_advisor.palette import PaintColor, DEFAULT_PALETTE, default_coverage
from backend.schemas import PaintColorModel


def paint_from_model(m: PaintColorModel) -> PaintColor:
    return PaintColor(
        name=m.name,
        hex=m.hex,
        brand=m.brand,
        paint_range=m.paint_range,
        code=m.code,
        finish=m.finish,
    )


def paint_to_dict(p: PaintColor) -> dict:
    return {
        "name": p.name,
        "hex": p.hex,
        "brand": p.brand,
        "paint_range": p.paint_range,
        "code": p.code,
        "finish": p.finish,
    }


def default_whole() -> dict:
    pal = list(DEFAULT_PALETTE)
    return {
        "palette": [paint_to_dict(p) for p in pal],
        "coverage": list(default_coverage(len(pal))),
        "material": "matte",
    }


def decode_image(data: bytes, filename: str) -> tuple[np.ndarray, np.ndarray | None]:
    suffix = os.path.splitext(filename)[1] or ".png"
    with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as tmp:
        tmp.write(data)
        path = tmp.name
    try:
        return load_image(path)
    finally:
        os.unlink(path)
