from ui import keys


def test_key_builders_match_legacy_strings():
    assert keys.slot_code(0) == "slot_code_0"
    assert keys.slot_hex(3) == "slot_hex_3"
    assert keys.slot_hexinput(2) == "slot_hexinput_2"
    assert keys.cov_pct(4) == "cov_pct_4"
    assert keys.blend(1) == "blend_1"
    assert keys.rename(2) == "rename_2"
    assert keys.canvas(0) == "canvas_0"


def test_key_constants_match_legacy_strings():
    assert keys.N == "n"
    assert keys.COV_N == "cov_n"
    assert keys.LOADED_G == "_loaded_g"
    assert keys.DRAW_MODE == "draw_mode"
    assert keys.PER_REGION_NORM == "per_region_norm"
    assert keys.RENAME_PREFIX == "rename_"
