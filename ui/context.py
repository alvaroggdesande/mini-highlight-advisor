"""Shared, load-once catalogue constants used across UI panels."""
from mini_highlight_advisor.catalog import load_catalog
from mini_highlight_advisor.palette import PaintColor

# UI sentinel for "not a catalogue paint" (custom hex). Byte-identical to the
# legacy app.py value — do not change; it is compared by string everywhere.
CUSTOM = "(custom target)"

CATALOG = load_catalog()


def _code_label(p: PaintColor) -> str:
    brand_range = " ".join(filter(None, [p.brand, p.paint_range]))
    code_part = f" · {p.code}" if p.code and p.code != p.name else ""
    return f"{p.name} · {brand_range}{code_part}"


CODE_LABEL = {p.code: _code_label(p) for p in CATALOG}
CATALOG_CODES = [p.code for p in CATALOG]
