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
