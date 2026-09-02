import re
from mini_highlight_advisor.surfaces import SURFACES, get_surface, REALISTIC, FREE

_HEX = re.compile(r"^#[0-9a-fA-F]{6}$")


def test_every_surface_has_valid_bucket():
    for s in SURFACES.values():
        assert s.bucket in (REALISTIC, FREE), f"{s.name} bucket {s.bucket!r}"


def test_realistic_surfaces_have_tones_free_do_not():
    for s in SURFACES.values():
        if s.bucket == REALISTIC:
            assert s.tones, f"realistic {s.name} must have tones"
            for label, hexv in s.tones.items():
                assert _HEX.match(hexv), f"{s.name}/{label} bad hex {hexv!r}"
        else:
            assert not s.tones, f"free {s.name} must have no tones"


def test_base_tone_hex_realistic_and_free():
    skin = get_surface("skin")
    assert _HEX.match(skin.base_tone_hex(None))          # default tone
    assert _HEX.match(skin.base_tone_hex("orc-green"))   # named tone
    assert get_surface("cloth").base_tone_hex(None) is None


def test_skin_includes_fantasy_tones():
    tones = set(get_surface("skin").tones)
    assert {"orc-green", "drow-blue", "undead-grey"} <= tones


def test_get_surface_unknown_falls_back_to_other():
    assert get_surface("nonsense").name == "other"


def test_other_has_no_technique_and_is_free():
    other = get_surface("other")
    assert other.default_technique == ""
    assert other.bucket == FREE


def test_fur_defaults_to_drybrush_and_is_realistic():
    fur = get_surface("fur")
    assert fur.default_technique == "drybrush"
    assert fur.bucket == REALISTIC
