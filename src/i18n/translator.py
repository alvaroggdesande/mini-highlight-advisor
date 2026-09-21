from __future__ import annotations
from pathlib import Path
from .loader import load_catalog, list_langs, _DEFAULT_LOCALES

_flat: dict[str, str] = {}        # active merged catalog (dot-separated keys)
_en_flat: dict[str, str] = {}     # English-only flat catalog (fallback)
_active_lang: str = "en"
_active_locales_dir: Path = _DEFAULT_LOCALES   # set on each set_lang() call


def set_lang(lang: str, *, _locales_dir: Path | None = None) -> None:
    """Load and merge catalogs for lang. Call once per rerun from ui/lang.py.

    _locales_dir is for test isolation only — omit in production.
    """
    global _flat, _en_flat, _active_lang, _active_locales_dir
    _active_locales_dir = _locales_dir or _DEFAULT_LOCALES
    _active_lang = lang
    en_raw = load_catalog("en", _active_locales_dir)
    _en_flat = _flatten(en_raw)
    if lang == "en":
        _flat = _en_flat
    else:
        lang_raw = load_catalog(lang, _active_locales_dir)
        _flat = _flatten(_deep_merge(en_raw, lang_raw))


def t(key: str, **kwargs) -> str:
    """Translate key in active language, fallback to en, then to key itself."""
    val = _flat.get(key) or _en_flat.get(key, key)
    if kwargs:
        try:
            val = val.format(**kwargs)
        except (KeyError, ValueError):
            pass
    return val


def available_langs(locales_dir: Path | None = None) -> list[str]:
    return list_langs(locales_dir or _active_locales_dir)


def _deep_merge(base: dict, override: dict) -> dict:
    result = dict(base)
    for k, v in override.items():
        if isinstance(v, dict) and isinstance(result.get(k), dict):
            result[k] = _deep_merge(result[k], v)
        else:
            result[k] = v
    return result


def _flatten(d: dict, prefix: str = "") -> dict[str, str]:
    out: dict[str, str] = {}
    for k, v in d.items():
        key = f"{prefix}.{k}" if prefix else k
        if isinstance(v, dict):
            out.update(_flatten(v, key))
        else:
            out[key] = str(v)
    return out


def _reset() -> None:
    """Reset all module state. For test isolation only."""
    global _flat, _en_flat, _active_lang, _active_locales_dir
    _flat = {}
    _en_flat = {}
    _active_lang = "en"
    _active_locales_dir = _DEFAULT_LOCALES
