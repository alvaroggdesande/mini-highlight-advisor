"""Shared, load-once catalogue constants used across UI panels."""
from mini_highlight_advisor.catalog import load_catalog

# UI sentinel for "not a catalogue paint" (custom hex). Byte-identical to the
# legacy app.py value — do not change; it is compared by string everywhere.
CUSTOM = "(custom target)"

CATALOG = load_catalog()
CODE_LABEL = {p.code: f"{p.name} · {p.paint_range or ''} · {p.code}" for p in CATALOG}
CATALOG_CODES = [p.code for p in CATALOG]
