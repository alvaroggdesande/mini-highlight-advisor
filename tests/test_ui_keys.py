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


def test_angle_keys_are_frozen():
    from ui import keys
    assert keys.ANGLES == "angles"
    assert keys.ACTIVE_ANGLE == "active_angle"
    assert keys.ANGLE_SELECT == "angle_select"
    assert keys.ANGLE_LABEL_PREFIX == "angle_label_"
    assert keys.angle_label(0) == "angle_label_0"
    assert keys.angle_label(3) == "angle_label_3"


def test_ps_keys_present_and_frozen():
    from ui import keys
    assert keys.LIGHT_AZ == "light_az"
    assert keys.LIGHT_EL == "light_el"
    assert keys.NORMALS == "ps_normals"
    assert keys.PS_MASK == "ps_mask"


def test_ps_albedo_key_is_frozen():
    assert keys.PS_ALBEDO == "ps_albedo"


def test_scheme_generated_key_exists():
    from ui import keys
    assert hasattr(keys, "SCHEME_GENERATED")
    assert keys.SCHEME_GENERATED == "scheme_generated"
