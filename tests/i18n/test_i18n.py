import json
import re
from pathlib import Path

import pytest

from i18n import t, set_lang, available_langs
from i18n import translator as _tr


@pytest.fixture(autouse=True)
def reset_state():
    _tr._reset()
    yield
    _tr._reset()


@pytest.fixture
def tmp_locales(tmp_path):
    en = {
        "app": {"title": "Hello", "msg": "Count: {n}"},
        "only_english": {"value": "EN only"},
    }
    es = {
        "app": {"title": "Hola"},
        # "app.msg" absent → fallback to en
        # "only_english" absent → fallback to en
    }
    (tmp_path / "en.json").write_text(json.dumps(en), encoding="utf-8")
    (tmp_path / "es.json").write_text(json.dumps(es), encoding="utf-8")
    return tmp_path


def test_fallback_to_english(tmp_locales):
    set_lang("es", _locales_dir=tmp_locales)
    assert t("only_english.value") == "EN only"


def test_missing_key_returns_key(tmp_locales):
    set_lang("en", _locales_dir=tmp_locales)
    assert t("nonexistent.key") == "nonexistent.key"


def test_interpolation(tmp_locales):
    set_lang("en", _locales_dir=tmp_locales)
    assert t("app.msg", n=3) == "Count: 3"


def test_es_all_keys_accessible():
    """Every en.json key returns a non-key value when lang=es (fallback works)."""
    set_lang("es")
    locales = Path(__file__).parents[2] / "locales"
    en_keys = _flatten_keys(json.loads((locales / "en.json").read_text(encoding="utf-8")))
    for key in en_keys:
        result = t(key)
        assert result != key, f"t({key!r}) returned itself — fallback broken"


def _flatten_keys(d: dict, prefix: str = "") -> list[str]:
    keys = []
    for k, v in d.items():
        full = f"{prefix}.{k}" if prefix else k
        if isinstance(v, dict):
            keys.extend(_flatten_keys(v, full))
        else:
            keys.append(full)
    return keys
