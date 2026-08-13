from __future__ import annotations

import math


def hex_to_rgb(hexv: str) -> tuple[float, float, float]:
    h = hexv.lstrip("#")
    return tuple(float(int(h[i : i + 2], 16)) for i in (0, 2, 4))  # type: ignore[return-value]


def _srgb_to_linear(c: float) -> float:
    c = c / 255.0
    return c / 12.92 if c <= 0.04045 else ((c + 0.055) / 1.055) ** 2.4


def rgb_to_lab(rgb) -> tuple[float, float, float]:
    r, g, b = (_srgb_to_linear(float(v)) for v in rgb)
    x = r * 0.4124 + g * 0.3576 + b * 0.1805
    y = r * 0.2126 + g * 0.7152 + b * 0.0722
    z = r * 0.0193 + g * 0.1192 + b * 0.9505
    xn, yn, zn = 0.95047, 1.0, 1.08883

    def f(t: float) -> float:
        return t ** (1 / 3) if t > 0.008856 else (7.787 * t + 16 / 116)

    fx, fy, fz = f(x / xn), f(y / yn), f(z / zn)
    return (116 * fy - 16, 500 * (fx - fy), 200 * (fy - fz))


def lab_of_hex(hexv: str) -> tuple[float, float, float]:
    return rgb_to_lab(hex_to_rgb(hexv))


def delta_e00(lab1, lab2) -> float:
    L1, a1, b1 = lab1
    L2, a2, b2 = lab2
    avg_Lp = (L1 + L2) / 2.0
    C1 = math.hypot(a1, b1)
    C2 = math.hypot(a2, b2)
    avg_C = (C1 + C2) / 2.0
    G = 0.5 * (1 - math.sqrt((avg_C ** 7) / (avg_C ** 7 + 25 ** 7))) if avg_C > 0 else 0.0
    a1p, a2p = a1 * (1 + G), a2 * (1 + G)
    C1p, C2p = math.hypot(a1p, b1), math.hypot(a2p, b2)
    avg_Cp = (C1p + C2p) / 2.0
    h1p = math.degrees(math.atan2(b1, a1p)) % 360
    h2p = math.degrees(math.atan2(b2, a2p)) % 360
    if abs(h1p - h2p) > 180:
        avg_Hp = (h1p + h2p + 360) / 2.0
    else:
        avg_Hp = (h1p + h2p) / 2.0
    T = (
        1
        - 0.17 * math.cos(math.radians(avg_Hp - 30))
        + 0.24 * math.cos(math.radians(2 * avg_Hp))
        + 0.32 * math.cos(math.radians(3 * avg_Hp + 6))
        - 0.20 * math.cos(math.radians(4 * avg_Hp - 63))
    )
    delta_hp = h2p - h1p
    if abs(delta_hp) > 180:
        delta_hp += 360 if h2p <= h1p else -360
    delta_Lp = L2 - L1
    delta_Cp = C2p - C1p
    delta_Hp = 2 * math.sqrt(C1p * C2p) * math.sin(math.radians(delta_hp) / 2.0)
    S_L = 1 + (0.015 * (avg_Lp - 50) ** 2) / math.sqrt(20 + (avg_Lp - 50) ** 2)
    S_C = 1 + 0.045 * avg_Cp
    S_H = 1 + 0.015 * avg_Cp * T
    delta_ro = 30 * math.exp(-(((avg_Hp - 275) / 25) ** 2))
    R_C = 2 * math.sqrt((avg_Cp ** 7) / (avg_Cp ** 7 + 25 ** 7)) if avg_Cp > 0 else 0.0
    R_T = -R_C * math.sin(math.radians(2 * delta_ro))
    return math.sqrt(
        (delta_Lp / S_L) ** 2
        + (delta_Cp / S_C) ** 2
        + (delta_Hp / S_H) ** 2
        + R_T * (delta_Cp / S_C) * (delta_Hp / S_H)
    )


def _linear_to_srgb255(v: float) -> float:
    v = max(0.0, min(1.0, v))
    s = 12.92 * v if v <= 0.0031308 else 1.055 * (v ** (1 / 2.4)) - 0.055
    return s * 255.0


def linear_blend(rgbs, parts) -> tuple[float, float, float]:
    """Blend sRGB colours (0-255 seqs) by integer `parts` in linear-light space.

    Physically more honest than averaging sRGB directly. Still an approximation of
    real pigment mixing — callers label the result 'approx'.
    """
    total = float(sum(parts))
    acc = [0.0, 0.0, 0.0]
    for rgb, w in zip(rgbs, parts):
        for k in range(3):
            acc[k] += w * _srgb_to_linear(float(rgb[k]))
    return tuple(_linear_to_srgb255(acc[k] / total) for k in range(3))  # type: ignore[return-value]


def lab_to_rgb(lab) -> tuple[float, float, float]:
    """Inverse of rgb_to_lab: CIE-Lab (D65) -> sRGB 0-255 floats."""
    L, a, b = lab
    fy = (L + 16) / 116.0
    fx = fy + a / 500.0
    fz = fy - b / 200.0

    def finv(t: float) -> float:
        return t ** 3 if t ** 3 > 0.008856 else (t - 16 / 116) / 7.787

    xn, yn, zn = 0.95047, 1.0, 1.08883
    x, y, z = xn * finv(fx), yn * finv(fy), zn * finv(fz)
    r = x * 3.2406 + y * -1.5372 + z * -0.4986
    g = x * -0.9689 + y * 1.8758 + z * 0.0415
    bl = x * 0.0557 + y * -0.2040 + z * 1.0570
    return (_linear_to_srgb255(r), _linear_to_srgb255(g), _linear_to_srgb255(bl))


def rgb_to_hex(rgb) -> str:
    """Clamp/round an sRGB 0-255 triple to '#rrggbb'."""
    r, g, b = (max(0, min(255, int(round(v)))) for v in rgb)
    return f"#{r:02x}{g:02x}{b:02x}"


def blend_hex_lab(h1: str, h2: str) -> str:
    """Perceptual midpoint of two hex colours, blended in CIE-Lab."""
    l1 = lab_of_hex(h1)
    l2 = lab_of_hex(h2)
    mid = tuple((a + b) / 2.0 for a, b in zip(l1, l2))
    return rgb_to_hex(lab_to_rgb(mid))
