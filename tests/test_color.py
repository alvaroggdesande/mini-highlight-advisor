import math
from mini_highlight_advisor.color import hex_to_rgb, rgb_to_lab, lab_of_hex, delta_e00


def test_hex_to_rgb_parses():
    assert hex_to_rgb("#ffffff") == (255.0, 255.0, 255.0)
    assert hex_to_rgb("000000") == (0.0, 0.0, 0.0)


def test_rgb_to_lab_known_anchors():
    L, a, b = rgb_to_lab((255, 255, 255))
    assert abs(L - 100.0) < 0.5 and abs(a) < 1.0 and abs(b) < 1.0
    L0, _, _ = rgb_to_lab((0, 0, 0))
    assert abs(L0) < 0.5


def test_delta_e00_identity_is_zero():
    lab = lab_of_hex("#6d7173")
    assert delta_e00(lab, lab) == 0.0 or delta_e00(lab, lab) < 1e-9


def test_delta_e00_symmetric():
    a = lab_of_hex("#3f4442")
    b = lab_of_hex("#a7a9a6")
    assert abs(delta_e00(a, b) - delta_e00(b, a)) < 1e-9


def test_delta_e00_orders_by_similarity():
    target = lab_of_hex("#6d7173")      # neutral grey
    near = lab_of_hex("#707173")        # a hair off
    far = lab_of_hex("#1b1b1b")         # near black
    assert delta_e00(target, near) < delta_e00(target, far)


def test_delta_e00_black_white_is_large():
    assert delta_e00(lab_of_hex("#000000"), lab_of_hex("#ffffff")) > 90.0


def test_linear_blend_midpoint_lighter_than_srgb_average():
    from mini_highlight_advisor.color import linear_blend
    r, g, b = linear_blend([(0, 0, 0), (255, 255, 255)], [1, 1])
    assert 180 < r < 195          # linear-light mid ≈ 188, not the 127 of an sRGB average
    assert abs(r - g) < 1e-6 and abs(g - b) < 1e-6


def test_linear_blend_respects_parts():
    from mini_highlight_advisor.color import linear_blend
    dark = linear_blend([(0, 0, 0), (255, 255, 255)], [3, 1])
    light = linear_blend([(0, 0, 0), (255, 255, 255)], [1, 3])
    assert dark[0] < light[0]


def test_linear_blend_single_is_identity():
    from mini_highlight_advisor.color import linear_blend
    r, g, b = linear_blend([(120, 60, 30)], [1])
    assert abs(r - 120) < 1.0 and abs(g - 60) < 1.0 and abs(b - 30) < 1.0


def test_rgb_to_hex_clamps_and_formats():
    from mini_highlight_advisor.color import rgb_to_hex
    assert rgb_to_hex((0, 0, 0)) == "#000000"
    assert rgb_to_hex((255, 255, 255)) == "#ffffff"
    assert rgb_to_hex((300, -5, 128)) == "#ff0080"      # clamp out-of-range


def test_lab_roundtrip_is_near_identity():
    from mini_highlight_advisor.color import hex_to_rgb, rgb_to_lab, lab_to_rgb
    for hexv in ("#000000", "#ffffff", "#6d7173", "#7a1f22", "#3f6db0"):
        r0, g0, b0 = hex_to_rgb(hexv)
        r1, g1, b1 = lab_to_rgb(rgb_to_lab((r0, g0, b0)))
        assert abs(r1 - r0) < 2 and abs(g1 - g0) < 2 and abs(b1 - b0) < 2


def test_blend_hex_lab_black_white_is_mid_grey():
    from mini_highlight_advisor.color import blend_hex_lab
    out = blend_hex_lab("#000000", "#ffffff")
    r = int(out[1:3], 16)
    assert out[1:3] == out[3:5] == out[5:7]     # neutral grey
    assert 108 <= r <= 128                       # perceptual mid (L~50), not linear-bright


def test_blend_hex_lab_symmetric_and_endpoints():
    from mini_highlight_advisor.color import blend_hex_lab
    assert blend_hex_lab("#123456", "#abcdef") == blend_hex_lab("#abcdef", "#123456")
    same = blend_hex_lab("#4488cc", "#4488cc")
    r, g, b = int(same[1:3], 16), int(same[3:5], 16), int(same[5:7], 16)
    assert abs(r - 0x44) <= 1 and abs(g - 0x88) <= 1 and abs(b - 0xcc) <= 1
