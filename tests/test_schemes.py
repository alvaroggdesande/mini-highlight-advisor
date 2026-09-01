# tests/test_schemes.py
from mini_highlight_advisor.region_state import RegionBook, new_book
from mini_highlight_advisor.palette import PaintColor, default_ramp, default_coverage
from mini_highlight_advisor import schemes as sch
import numpy as np


def _book_with_region(name="armour", n=5):
    book = new_book(n)
    mask = np.zeros((4, 4), dtype=bool)
    mask[1:3, 1:3] = True
    book.add(mask, name, default_ramp(n), default_coverage(n))
    return book


def _red(): return PaintColor("Red", "#ff0000")


def test_snapshot_captures_every_region_by_name():
    book = _book_with_region("armour")
    s = sch.snapshot(book, "Crimson")
    assert s.name == "Crimson"
    assert set(s.palettes) == set(book.names())          # Whole mini + armour
    assert s.anchor is None


def test_snapshot_then_apply_is_palette_noop():
    book = _book_with_region("armour")
    s = sch.snapshot(book, "X")
    before = [list(book.palette_at(g)) for g in range(len(book.names()))]
    report = sch.apply(s, book)
    after = [list(book.palette_at(g)) for g in range(len(book.names()))]
    assert before == after
    assert report.skipped_regions == [] and report.unused_keys == []


def test_apply_changes_palette():
    book = _book_with_region("armour")
    s = sch.snapshot(book, "X")
    s.palettes["armour"] = [_red()]
    sch.apply(s, book)
    assert book.palette_at(1) == [_red()]                # index 1 == "armour"


def test_snapshot_is_isolated_from_later_book_edits():
    book = _book_with_region("armour")
    s = sch.snapshot(book, "X")
    book.set_palette_at(1, [_red()])                     # edit book after snapshot
    assert s.palettes["armour"] != [_red()]              # snapshot unchanged


def test_apply_after_rename_reports_skip_and_unused():
    book = _book_with_region("armour")
    s = sch.snapshot(book, "X")
    book.set_name_at(1, "plating")                       # rename the region
    report = sch.apply(s, book)
    assert "plating" in report.skipped_regions           # book region with no key
    assert "armour" in report.unused_keys                # key matching no region


def test_apply_after_add_reports_new_region_skipped():
    book = _book_with_region("armour")
    s = sch.snapshot(book, "X")
    mask = np.zeros((4, 4), dtype=bool); mask[0, 0] = True
    book.add(mask, "cloak", default_ramp(5), default_coverage(5))
    report = sch.apply(s, book)
    assert "cloak" in report.skipped_regions


def test_apply_to_duplicate_names_hits_every_match():
    book = new_book(5)
    for _ in range(2):
        m = np.zeros((4, 4), dtype=bool); m[0, 0] = True
        book.add(m, "trim", default_ramp(5), default_coverage(5))
    s = sch.snapshot(book, "X")
    s.palettes["trim"] = [_red()]
    sch.apply(s, book)
    assert book.palette_at(1) == [_red()] and book.palette_at(2) == [_red()]
