from mini_highlight_advisor import scheme_build as sb
from mini_highlight_advisor.scheme_gen import RegionColorSpec
from mini_highlight_advisor.palette import PaintColor
from mini_highlight_advisor.schemes import Scheme


def _owned():
    return [
        PaintColor("Black", "#101010", "V", "MC", code="A1"),
        PaintColor("Grey",  "#808080", "V", "MC", code="A2"),
        PaintColor("White", "#f0f0f0", "V", "MC", code="A3"),
    ]


def _catalog():
    return _owned() + [PaintColor("Deep Red", "#c02030", "V", "MC", code="C9")]


def test_in_collection_target_resolves_to_owned_paint():
    pal = sb.map_ramp_to_palette(["#808080"], _owned(), _catalog(), owned_only=False)
    assert pal[0].code == "A2"


def test_unreachable_falls_back_to_catalogue_when_not_owned_only():
    # red is not in the owned greys, but is in the catalogue
    pal = sb.map_ramp_to_palette(["#c02030"], _owned(), _catalog(), owned_only=False)
    assert pal[0].hex.lower() == "#c02030" or pal[0].code == "C9"


def test_owned_only_never_leaves_collection():
    owned = _owned()
    pal = sb.map_ramp_to_palette(["#c02030"], owned, _catalog(), owned_only=True)
    assert pal[0] in owned


def test_build_scheme_returns_scheme_with_region_keys_and_band_lengths():
    specs = [
        RegionColorSpec("Cloak", "cloak", None, 5),
        RegionColorSpec("Skin", "skin", "tan", 4),
    ]
    scheme = sb.build_scheme("Auto", specs, "Cloak", "#c02030", "neutral",
                             "complementary", _owned(), _catalog(), owned_only=False)
    assert isinstance(scheme, Scheme)
    assert set(scheme.palettes) == {"Cloak", "Skin"}
    assert len(scheme.palettes["Cloak"]) == 5
    assert len(scheme.palettes["Skin"]) == 4
    assert all(isinstance(p, PaintColor) for p in scheme.palettes["Cloak"])
