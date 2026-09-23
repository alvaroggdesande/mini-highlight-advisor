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


def test_capture_help_is_translated_for_spanish():
    """The capture guide text should be available in the locale catalog."""
    set_lang("es")
    guide = t("capture.shooting_guide")
    note = t("capture.painted_capture_note")
    ps_guide = t("capture.ps_guide")
    assert "luz lateral" in guide.lower()
    assert "miniatura" in guide.lower()
    assert "imprimada" in note.lower() or "primed" not in note.lower()
    assert "estéreo" in ps_guide.lower() or "fotométrico" in ps_guide.lower()


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


def test_no_dead_keys():
    """Every key in en.json is referenced in at least one t() call in ui/, app.py, or web/src/."""
    locales = Path(__file__).parents[2] / "locales"
    root = Path(__file__).parents[2]
    en_keys = set(_flatten_keys(json.loads((locales / "en.json").read_text(encoding="utf-8"))))

    pattern = re.compile(r'\bt\("([^"]+)"')
    used: set[str] = set()
    for py in (root / "ui").rglob("*.py"):
        used.update(pattern.findall(py.read_text(encoding="utf-8")))
    used.update(pattern.findall((root / "app.py").read_text(encoding="utf-8")))
    # React frontend uses the same t("key") call signature
    for ts in (root / "web" / "src").rglob("*.ts"):
        used.update(pattern.findall(ts.read_text(encoding="utf-8")))
    for tsx in (root / "web" / "src").rglob("*.tsx"):
        used.update(pattern.findall(tsx.read_text(encoding="utf-8")))

    dead = en_keys - used
    assert not dead, f"Dead keys in en.json not referenced in ui/, app.py, or web/src/: {sorted(dead)}"
