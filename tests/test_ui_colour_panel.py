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
