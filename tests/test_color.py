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
