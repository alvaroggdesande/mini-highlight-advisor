"""Pure geometry helpers for the drawable canvas and region-outline preview."""
import cv2
import numpy as np

# Colors for drawn regions — order matches book indices 1, 2, 3, … (book index 0 = Whole mini).
# RGB tuples used for the cv2 outline image; emojis for the radio label; hex for HTML swatches.
REGION_COLORS: list[tuple[int, int, int]] = [
    (180, 50, 255),   # purple  → 🟣
    (50, 100, 255),   # blue    → 🔵
    (250, 210, 30),   # yellow  → 🟡
    (50, 200, 50),    # green   → 🟢
    (255, 60, 60),    # red     → 🔴
]
REGION_EMOJIS: list[str] = ["🟣", "🔵", "🟡", "🟢", "🔴"]
WHOLE_MINI_EMOJI = "⬜"


def region_label(g: int, name: str) -> str:
    """Format a region selector label: coloured emoji + name."""
    if g == 0:
        return f"{WHOLE_MINI_EMOJI} {name}"
    return f"{REGION_EMOJIS[(g - 1) % len(REGION_EMOJIS)]} {name}"


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
    colour matching REGION_COLORS. Read-only preview."""
    out = np.ascontiguousarray(rgb[..., :3]).copy()
    kernel = np.ones((3, 3), np.uint8)
    for i, r in enumerate(regions):
        m = r.mask.astype(np.uint8)
        edge = (m - cv2.erode(m, kernel, iterations=2)).astype(bool)
        out[edge] = REGION_COLORS[i % len(REGION_COLORS)]
    return out
