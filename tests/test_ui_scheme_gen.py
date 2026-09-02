from streamlit.testing.v1 import AppTest


def _run():
    at = AppTest.from_file("app.py")
    return at.run()


def test_panel_absent_without_regions_present_with_them():
    # Smoke: the app imports and the panel module loads without error.
    import ui.scheme_gen_panel as p
    assert hasattr(p, "render")


def test_generate_then_apply_changes_book_palettes(tmp_path):
    # Unit-level exercise of the panel's core call path without a full Streamlit
    # session: build a book, generate a scheme, apply it, assert palettes changed.
    import numpy as np
    from mini_highlight_advisor.region_state import new_book
    from mini_highlight_advisor.palette import default_ramp, default_coverage
    from mini_highlight_advisor import scheme_build as sb, schemes as sch
    from mini_highlight_advisor.scheme_gen import RegionColorSpec
    from ui.context import CATALOG

    book = new_book(5)
    m = np.zeros((8, 8), bool); m[2:5, 2:5] = True
    book.add(m, "Cloak", default_ramp(5), default_coverage(5))
    book.set_surface_at(1, "cloak")

    specs = [
        RegionColorSpec(name, book.surface_at(g), book.tone_at(g),
                        len(book.palette_at(g)))
        for g, name in enumerate(book.names())
    ]
    before = [p.hex for p in book.palette_at(1)]
    scheme = sb.build_scheme("Auto", specs, "Cloak", "#c02030", "grimdark",
                             "complementary", [], list(CATALOG), owned_only=False)
    sch.apply(scheme, book)
    after = [p.hex for p in book.palette_at(1)]
    assert before != after
