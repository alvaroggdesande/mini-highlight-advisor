# tests/test_techniques.py
import pytest
from mini_highlight_advisor.palette import role_names as palette_role_names


def test_smooth_role_names_match_palette_for_n_3_to_7():
    from mini_highlight_advisor.techniques import get_technique
    spec = get_technique("smooth")
    for n in range(3, 8):
        assert spec.role_names(n) == palette_role_names(n), \
            f"smooth.role_names({n}) must equal palette.role_names({n})"


def test_smooth_unknown_n_returns_generic_labels():
    from mini_highlight_advisor.techniques import get_technique
    spec = get_technique("smooth")
    assert spec.role_names(1) == ["Layer 1"]
    assert spec.role_names(2) == ["Layer 1", "Layer 2"]


def test_drybrush_role_names_correct_length_for_all_n():
    from mini_highlight_advisor.techniques import get_technique
    spec = get_technique("drybrush")
    for n in range(1, 8):
        roles = spec.role_names(n)
        assert len(roles) == n, f"drybrush.role_names({n}) returned {len(roles)} items"


def test_drybrush_base_coat_always_first():
    from mini_highlight_advisor.techniques import get_technique
    spec = get_technique("drybrush")
    for n in range(1, 8):
        assert spec.role_names(n)[0] == "Base coat"


def test_drybrush_fine_highlight_at_n5():
    from mini_highlight_advisor.techniques import get_technique
    spec = get_technique("drybrush")
    assert spec.role_names(5)[-1] == "Fine highlight"


def test_matte_alias_returns_same_object_as_smooth():
    from mini_highlight_advisor.techniques import get_technique
    assert get_technique("matte") is get_technique("smooth")


def test_unknown_technique_falls_back_to_smooth():
    from mini_highlight_advisor.techniques import get_technique
    assert get_technique("totally_unknown") is get_technique("smooth")


def test_smooth_coverage_note_shadow():
    from mini_highlight_advisor.techniques import get_technique
    spec = get_technique("smooth")
    assert spec.coverage_note("Shadow") == "deepest recesses"


def test_drybrush_coverage_note_base_coat_mentions_recess():
    from mini_highlight_advisor.techniques import get_technique
    spec = get_technique("drybrush")
    assert "recess" in spec.coverage_note("Base coat")


def test_smooth_captions_contain_pct_placeholder():
    from mini_highlight_advisor.techniques import get_technique
    spec = get_technique("smooth")
    assert "{pct" in spec.captions.across
    assert "{pct" in spec.captions.stays


def test_drybrush_captions_mention_drybrush():
    from mini_highlight_advisor.techniques import get_technique
    spec = get_technique("drybrush")
    assert "rybrush" in spec.captions.across.lower()


def test_smooth_captions_format_with_pct():
    from mini_highlight_advisor.techniques import get_technique
    spec = get_technique("smooth")
    result = spec.captions.across.format(pct=42.5)
    assert "42" in result


def test_drybrush_captions_format_with_pct():
    from mini_highlight_advisor.techniques import get_technique
    spec = get_technique("drybrush")
    result = spec.captions.stays.format(pct=15.0)
    assert "15" in result
