from __future__ import annotations
import json
from pathlib import Path

_DEFAULT_LOCALES: Path = Path(__file__).parent.parent.parent / "locales"


def load_catalog(lang: str, locales_dir: Path = _DEFAULT_LOCALES) -> dict:
    """Load raw JSON catalog for lang. Returns {} if the file does not exist."""
    path = locales_dir / f"{lang}.json"
    if not path.exists():
        return {}
    with path.open(encoding="utf-8") as f:
        return json.load(f)


def list_langs(locales_dir: Path = _DEFAULT_LOCALES) -> list[str]:
    """Return sorted language codes that have a catalog file on disk."""
    if not locales_dir.exists():
        return []
    return sorted(p.stem for p in locales_dir.glob("*.json"))
