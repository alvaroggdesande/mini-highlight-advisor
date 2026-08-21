"""Pure geometry helpers for the drawable canvas and region-outline preview."""
import cv2
import numpy as np


def points_from_object(obj) -> list[tuple[float, float]]:
    # Extract traced vertices from a drawable-canvas (fabric.js) object.
    # Freedraw/polygon objects expose the stroke as obj["path"], a list of SVG
    # segments: ["M",x,y] / ["L",x,y] / ["Q",cx,cy,x,y] / ["z"]. The segment
    # END point is always its last two numbers (Q's control point is ignored).
    # Some versions use obj["points"] ([{"x":..,"y":..}]) instead.
    if "points" in obj:
        return [(p["x"], p["y"]) for p in obj["points"]]
    return [(seg[-2], seg[-1]) for seg in obj.get("path", []) if len(seg) >= 3]


def region_outline_image(rgb, regions):
    """RGB copy of the photo with each region's boundary drawn in a distinct
    colour. Read-only preview — selection happens in the list."""
    out = np.ascontiguousarray(rgb[..., :3]).copy()
    colors = [(255, 40, 200), (40, 200, 255), (255, 200, 40), (120, 255, 120), (255, 120, 120)]
    kernel = np.ones((3, 3), np.uint8)
    for i, r in enumerate(regions):
        m = r.mask.astype(np.uint8)
        edge = (m - cv2.erode(m, kernel, iterations=2)).astype(bool)
        out[edge] = colors[i % len(colors)]
    return out
