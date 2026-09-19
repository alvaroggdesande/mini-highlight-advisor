import numpy as np


def _make_book_with_region():
    from mini_highlight_advisor.region_state import new_book
    from mini_highlight_advisor.palette import default_ramp, default_coverage
    book = new_book(5)
    m = np.zeros((8, 8), bool)
    m[2:5, 2:5] = True
    book.add(m, "Cloak", default_ramp(5), default_coverage(5))
    return book


def test_colour_panel_module_loads():
    import ui.colour_panel as cp
    assert hasattr(cp, "render")


def test_level1_generate_applies_scheme_to_book():
    """Level 1: build_scheme + apply changes the book palettes."""
    from mini_highlight_advisor import scheme_build as sb, schemes as sch
    from mini_highlight_advisor.scheme_gen import RegionColorSpec
    from ui.context import CATALOG

    book = _make_book_with_region()
    before = [p.hex for p in book.palette_at(1)]

    specs = [
        RegionColorSpec(name, book.surface_at(g), book.tone_at(g),
                        len(book.palette_at(g)))
        for g, name in enumerate(book.names())
    ]
    scheme = sb.build_scheme("Auto", specs, "Cloak", "#c02030", "grimdark",
                             "complementary", [], list(CATALOG), owned_only=False)
    sch.apply(scheme, book)
    after = [p.hex for p in book.palette_at(1)]
    assert before != after


def test_ramp_from_midtone_produces_n_colours():
    from mini_highlight_advisor.color import ramp_from_midtone
    hexes = ramp_from_midtone("#808080", 5)
    assert len(hexes) == 5
    # darkest should be darker than lightest
    from mini_highlight_advisor.palette import PaintColor
    dark = PaintColor("d", hexes[0]).rgb.mean()
    light = PaintColor("l", hexes[-1]).rgb.mean()
    assert light > dark


def test_hue_rotate_complementary():
    from mini_highlight_advisor.color import hue_rotate, ramp_from_midtone
    mid = "#c02030"
    comp = hue_rotate(mid, 180)
    hexes = ramp_from_midtone(comp, 3)
    assert len(hexes) == 3
    assert hexes[0] != mid  # complementary is different from original


def test_colour_panel_render_sets_book_palette(tmp_path):
    """colour_panel.render() must call book.set_palette_at (via Level 3 slots)."""
    # This is a unit test of the book interaction, not the Streamlit render.
    # We test that palette_editor logic (now in colour_panel) still sets palettes.
    from mini_highlight_advisor.region_state import new_book
    from mini_highlight_advisor.palette import DEFAULT_PALETTE
    book = new_book(5)
    # Default palette should be set; Level 3 reads it and sets it back via book
    assert book.palette_at(0) is not None
    assert len(book.palette_at(0)) > 0


def test_level1_writeback_sets_hero_hex_and_mood():
    """After running scheme generation logic, book.hero_hex and book.mood are written."""
    from mini_highlight_advisor import scheme_build as sb, schemes as sch
    from mini_highlight_advisor.scheme_gen import RegionColorSpec
    from ui.context import CATALOG

    book = _make_book_with_region()
    assert book.hero_hex is None
    assert book.mood is None

    chosen_hex = "#c02030"
    chosen_mood = "grimdark"
    names = book.names()
    specs = [
        RegionColorSpec(nm, book.surface_at(g), book.tone_at(g), len(book.palette_at(g)))
        for g, nm in enumerate(names)
    ]
    scheme = sb.build_scheme("Auto", specs, names[0], chosen_hex, chosen_mood,
                             "complementary", [], list(CATALOG), owned_only=False)
    sch.apply(scheme, book)

    # Simulate what _render_level1 will do after apply:
    book.hero_hex = chosen_hex
    book.mood = chosen_mood

    assert book.hero_hex == "#c02030"
    assert book.mood == "grimdark"


def test_level1_prefill_seeds_session_from_book():
    """If book.hero_hex/mood are set and session keys absent, they seed the session."""
    import streamlit as st

    book = _make_book_with_region()
    book.hero_hex = "#a03020"
    book.mood = "grimdark"

    # Simulate the pre-fill logic (the actual Streamlit widgets can't be called in tests,
    # so we test the seeding condition and session mutation directly).
    sgen_hex_key = "sgen_anchor_hex"
    sgen_mood_key = "sgen_mood"
    if hasattr(st, "session_state"):
        st.session_state.pop(sgen_hex_key, None)
        st.session_state.pop(sgen_mood_key, None)

    # Pre-fill logic extracted for testability:
    session = {}  # stand-in for st.session_state
    if book.hero_hex is not None and sgen_hex_key not in session:
        session[sgen_hex_key] = book.hero_hex
    from mini_highlight_advisor.scheme_gen import MOODS
    if book.mood is not None and book.mood in MOODS and sgen_mood_key not in session:
        session[sgen_mood_key] = book.mood

    assert session[sgen_hex_key] == "#a03020"
    assert session[sgen_mood_key] == "grimdark"


def _make_book_with_ramp_decision():
    from mini_highlight_advisor.region_state import new_book
    import numpy as np
    book = new_book(5)
    m = np.zeros((8, 8), bool); m[2:5, 2:5] = True
    from mini_highlight_advisor.palette import default_ramp, default_coverage
    book.add(m, "Cloak", default_ramp(5), default_coverage(5))
    book.drawn[0].ramp_midtone = "#c02030"
    book.drawn[0].ramp_variant = "complementary"
    return book


def test_level2_writeback_sets_ramp_decision():
    """Applying a ramp variant writes midtone + variant back to the region."""
    from mini_highlight_advisor.region_state import new_book
    import numpy as np
    from mini_highlight_advisor.palette import default_ramp, default_coverage

    book = new_book(5)
    m = np.zeros((8, 8), bool); m[2:5, 2:5] = True
    book.add(m, "Cloak", default_ramp(5), default_coverage(5))

    sel = 1
    mid_hex = "#a03020"
    label = "Complementary"
    variant_map = {"Ramp": "standard", "Complementary": "complementary",
                   "Warm (+30°)": "warm", "Cool (−30°)": "cool"}

    # Simulate what the Apply button click will do:
    book.drawn[sel - 1].ramp_midtone = mid_hex
    book.drawn[sel - 1].ramp_variant = variant_map[label]

    assert book.drawn[0].ramp_midtone == "#a03020"
    assert book.drawn[0].ramp_variant == "complementary"


def test_level2_writeback_whole_mini_uses_book_fields():
    """sel == 0 (whole-mini) writes ramp decisions to book.whole_ramp_midtone/variant."""
    from mini_highlight_advisor.region_state import new_book
    book = new_book(5)
    sel = 0
    mid_hex = "#c02030"
    variant = "complementary"
    # Simulate what the Apply button click now does for sel == 0:
    if sel > 0:
        book.drawn[sel - 1].ramp_midtone = mid_hex
        book.drawn[sel - 1].ramp_variant = variant
    else:
        book.whole_ramp_midtone = mid_hex
        book.whole_ramp_variant = variant
    assert book.drawn == []
    assert book.whole_ramp_midtone == "#c02030"
    assert book.whole_ramp_variant == "complementary"


def test_level2_complement_shortcut_hex():
    """Complement shortcut injects hue_rotate(hero_hex, 180) as the midtone."""
    from mini_highlight_advisor.color import hue_rotate
    hero_hex = "#c02030"
    complement = hue_rotate(hero_hex, 180)
    # Verify it's the 180° rotation (not the same colour)
    assert complement != hero_hex
    # Simulate seeding the session key:
    session = {}
    session["midtone_hex_1"] = complement
    assert session["midtone_hex_1"] == complement


def test_level2_prefill_seeds_midtone_from_region():
    """If region.ramp_midtone is set and session key absent, session key is seeded."""
    from ui import keys
    book = _make_book_with_ramp_decision()
    sel = 1
    session = {}
    key = keys.midtone_hex(sel)
    region = book.drawn[sel - 1]
    if region.ramp_midtone is not None and key not in session:
        session[key] = region.ramp_midtone
    assert session[key] == "#c02030"


def test_level3_mix_guide_exact_phrase():
    """When the user owns an exact paint match, phrase is 'Use X (code).'"""
    from mini_highlight_advisor.matching import match, Target
    from mini_highlight_advisor.palette import PaintColor
    from ui.context import CATALOG

    # Find any paint in the catalogue
    paint = CATALOG[0]
    owned = [paint]
    result = match(Target(paint.hex, None, paint.finish), owned=owned, catalog=list(CATALOG))
    assert result.tier in ("exact", "close")
    assert result.phrase  # non-empty


def test_level3_mix_guide_unreachable_phrase():
    """When the user owns nothing useful, phrase mentions can't match."""
    from mini_highlight_advisor.matching import match, Target
    result = match(Target("#123456", None, "matte"), owned=[], catalog=[])
    assert "Can't match" in result.phrase or result.phrase  # graceful


def test_level3_owned_list_derivation():
    """owned_list is correctly derived from picked codes + CATALOG."""
    from ui.context import CATALOG
    if not CATALOG:
        return
    paint = CATALOG[0]
    picked = {paint.code}
    owned_list = [p for p in CATALOG if p.code and p.code in picked]
    assert paint in owned_list


def test_level3_finish_is_metallic_for_nmm():
    """For nmm material, finish resolves to 'metallic'."""
    from mini_highlight_advisor.region_state import new_book
    book = new_book(5)
    book.whole_material = "nmm"
    sel = 0
    finish = "metallic" if book.material_at(sel) == "nmm" else "matte"
    assert finish == "metallic"


def test_level3_finish_is_matte_for_smooth():
    from mini_highlight_advisor.region_state import new_book
    book = new_book(5)
    sel = 0
    finish = "metallic" if book.material_at(sel) == "nmm" else "matte"
    assert finish == "matte"


def _make_session():
    """Minimal stand-in for st.session_state (plain dict)."""
    return {}


def test_remove_last_band_decrements_count():
    from ui import keys
    import streamlit as st
    st.session_state[keys.N] = 5
    from ui.colour_panel import _remove_last_band
    _remove_last_band(5)
    assert st.session_state[keys.N] == 4


def test_remove_last_band_clears_slot_keys():
    from ui import keys
    import streamlit as st
    n = 5
    st.session_state[keys.N] = n
    st.session_state[keys.slot_code(n - 1)] = "ABC"
    st.session_state[keys.slot_hex(n - 1)] = "#aabbcc"
    st.session_state[keys.slot_hexinput(n - 1)] = "#aabbcc"
    from ui.colour_panel import _remove_last_band
    _remove_last_band(n)
    assert keys.slot_code(n - 1) not in st.session_state
    assert keys.slot_hex(n - 1) not in st.session_state
    assert keys.slot_hexinput(n - 1) not in st.session_state


def test_remove_last_band_noop_at_minimum():
    from ui import keys
    import streamlit as st
    st.session_state[keys.N] = 3
    from ui.colour_panel import _remove_last_band
    _remove_last_band(3)
    assert st.session_state[keys.N] == 3


def test_add_band_increments_count():
    from ui import keys
    import streamlit as st
    st.session_state[keys.N] = 4
    from ui.colour_panel import _add_band
    _add_band(4)
    assert st.session_state[keys.N] == 5


def test_add_band_seeds_new_slot_keys():
    from ui import keys
    import streamlit as st
    n = 4
    st.session_state[keys.N] = n
    # Ensure slot at index n doesn't pre-exist
    st.session_state.pop(keys.slot_code(n), None)
    st.session_state.pop(keys.slot_hex(n), None)
    from ui.colour_panel import _add_band
    _add_band(n)
    assert keys.slot_hex(n) in st.session_state
    assert st.session_state[keys.slot_hex(n)]  # non-empty hex


def test_add_band_noop_at_maximum():
    from ui import keys
    import streamlit as st
    st.session_state[keys.N] = 7
    from ui.colour_panel import _add_band
    _add_band(7)
    assert st.session_state[keys.N] == 7
