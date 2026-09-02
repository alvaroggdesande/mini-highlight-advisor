# tests/test_pipeline_technique.py
import numpy as np

from mini_highlight_advisor.pipeline import plan_region, analyze_regions, WHOLE_MINI
from mini_highlight_advisor.palette import DEFAULT_PALETTE, default_coverage, role_names as palette_role_names
from mini_highlight_advisor.regions import Region


def _flat_light(h=32, w=32):
    light = np.linspace(0.1, 0.9, h * w, dtype=np.float32).reshape(h, w)
    mask = np.ones((h, w), dtype=bool)
    return light, mask


def _rgb(h=32, w=32):
    rng = np.random.default_rng(42)
    return rng.integers(100, 200, (h, w, 3), dtype=np.uint8)


PAL = DEFAULT_PALETTE[:5]
COV = default_coverage(5)


def test_plan_region_default_technique_is_smooth():
    light, mask = _flat_light()
    plan = plan_region(_rgb(), mask, light, "test", PAL, COV, edges=False)
    assert plan.technique == "smooth"


def test_plan_region_smooth_roles_match_palette_role_names():
    """Regression lock: smooth technique produces the same role names as before."""
    light, mask = _flat_light()
    plan = plan_region(_rgb(), mask, light, "test", PAL, COV, edges=False, technique="smooth")
    expected = palette_role_names(len(PAL))
    assert plan.roles == expected, f"expected {expected}, got {plan.roles}"


def test_plan_region_drybrush_technique_field():
    light, mask = _flat_light()
    plan = plan_region(_rgb(), mask, light, "test", PAL, COV, edges=False, technique="drybrush")
    assert plan.technique == "drybrush"


def test_plan_region_drybrush_roles_start_with_base_coat():
    light, mask = _flat_light()
    plan = plan_region(_rgb(), mask, light, "test", PAL, COV, edges=False, technique="drybrush")
    assert plan.roles[0] == "Base coat"
    assert len(plan.roles) == len(PAL)


def test_plan_region_drybrush_bands_byte_identical_to_smooth():
    """CRITICAL: drybrush must not change band placement — only text changes."""
    light, mask = _flat_light()
    rgb = _rgb()
    p_smooth = plan_region(rgb, mask, light, "test", PAL, COV, edges=False, technique="smooth")
    p_dry = plan_region(rgb, mask, light, "test", PAL, COV, edges=False, technique="drybrush")
    np.testing.assert_array_equal(
        p_smooth.bands, p_dry.bands,
        err_msg="drybrush must produce byte-identical band placement to smooth")


def test_plan_region_matte_alias_same_as_smooth():
    light, mask = _flat_light()
    rgb = _rgb()
    p_matte = plan_region(rgb, mask, light, "test", PAL, COV, edges=False, technique="matte")
    p_smooth = plan_region(rgb, mask, light, "test", PAL, COV, edges=False, technique="smooth")
    assert p_matte.roles == p_smooth.roles
    assert p_matte.technique == "smooth"


def test_analyze_regions_drybrush_region_carries_technique():
    rng = np.random.default_rng(0)
    rgb = rng.integers(50, 200, (64, 64, 3), dtype=np.uint8)
    alpha = np.full((64, 64), 255, dtype=np.uint8)
    region_mask = np.zeros((64, 64), dtype=bool)
    region_mask[10:30, 10:30] = True
    pal3 = DEFAULT_PALETTE[:3]
    r = Region("fur", region_mask, pal3, default_coverage(3), material="drybrush")
    result = analyze_regions(rgb, alpha, DEFAULT_PALETTE[:5], regions=[r], edges=False)
    fur_plan = next(p for p in result.plans if p.name == "fur")
    assert fur_plan.technique == "drybrush"
    assert fur_plan.roles[0] == "Base coat"


def test_analyze_regions_whole_mini_technique_defaults_to_smooth():
    rng = np.random.default_rng(1)
    rgb = rng.integers(50, 200, (64, 64, 3), dtype=np.uint8)
    alpha = np.full((64, 64), 255, dtype=np.uint8)
    result = analyze_regions(rgb, alpha, DEFAULT_PALETTE[:5], edges=False)
    whole = next(p for p in result.plans if p.name == WHOLE_MINI)
    assert whole.technique == "smooth"
