import types

import numpy as np

from mini_highlight_advisor.pipeline import (
    analyze_regions, iter_region_plans, region_plan_names, WHOLE_MINI,
)
from mini_highlight_advisor.palette import DEFAULT_PALETTE, default_coverage
from mini_highlight_advisor.regions import Region

PAL = list(DEFAULT_PALETTE[:5])
COV = default_coverage(5)


def _vcrease(h=48, w=48, c0=24, half=8):
    col = np.arange(w, dtype=np.float32)
    ang = np.clip((col - c0) / half, -1.0, 1.0) * (np.pi / 3.0)
    n = np.zeros((h, w, 3), np.float32)
    n[..., 0] = -np.sin(ang)[None, :]
    n[..., 2] = np.cos(ang)[None, :]
    return n


def _inputs():
    rgb = np.full((48, 48, 3), 120, np.uint8)
    alpha = np.full((48, 48), 255, np.uint8)
    light = np.tile(np.linspace(0.1, 0.9, 48, dtype=np.float32), (48, 1))
    n = _vcrease()
    bmask = np.zeros((48, 48), dtype=bool)
    bmask[:, 24:] = True
    region_b = Region("B", bmask, PAL, COV)
    return rgb, alpha, light, n, region_b


def _kwargs():
    rgb, alpha, light, n, region_b = _inputs()
    return dict(rgb=rgb, alpha=alpha, default_palette=PAL, coverage=COV,
                regions=[region_b], edges=True, shades=True,
                light_field=light, normal_field=n)


def test_iter_region_plans_is_a_generator():
    # Laziness contract: it must be a generator (yields plans one at a time),
    # not a function that materialises every plan's step images up front.
    kw = _kwargs()
    gen = iter_region_plans(**kw)
    assert isinstance(gen, types.GeneratorType)


def test_iter_region_plans_builds_one_plan_per_step(monkeypatch):
    # Regression lock for the OOM fix: plans must be built lazily (one render per
    # `next`), never all up front. If someone rewrites this as `return list(...)`
    # the peak-memory guarantee is gone and this test fails.
    import mini_highlight_advisor.pipeline as pl
    calls = {"n": 0}
    real = pl._render_spec

    def spy(rgb, spec, ekw):
        calls["n"] += 1
        return real(rgb, spec, ekw)

    monkeypatch.setattr(pl, "_render_spec", spy)
    gen = pl.iter_region_plans(**_kwargs())  # whole-mini + region B == 2 plans
    assert calls["n"] == 0            # nothing rendered before first consume
    next(gen)
    assert calls["n"] == 1            # only the first plan built
    next(gen)
    assert calls["n"] == 2


def test_iter_region_plans_matches_analyze_regions_plans():
    # Single source of truth: streaming the plans must be byte-identical to the
    # eager analyze_regions().plans (same order, roles, coverage, and every step
    # image), so lazy rendering never drifts from the real pipeline.
    eager = analyze_regions(**_kwargs()).plans
    streamed = list(iter_region_plans(**_kwargs()))

    assert [p.name for p in streamed] == [p.name for p in eager]
    assert {p.name for p in eager} == {WHOLE_MINI, "B"}

    for want, got in zip(eager, streamed):
        assert got.roles == want.roles
        assert got.coverage == want.coverage
        assert len(got.steps) == len(want.steps)
        assert len(got.steps) > 0
        for s_want, s_got in zip(want.steps, got.steps):
            assert (s_got.index, s_got.kind, s_got.label, s_got.is_last) == \
                   (s_want.index, s_want.kind, s_want.label, s_want.is_last)
            assert np.array_equal(s_got.zone_rgb, s_want.zone_rgb)
            assert np.array_equal(s_got.cumulative_rgb, s_want.cumulative_rgb)
            if s_want.exact_rgb is None:
                assert s_got.exact_rgb is None
            else:
                assert np.array_equal(s_got.exact_rgb, s_want.exact_rgb)


def test_region_plan_names_matches_plan_order():
    # The Paint-tab region selector needs the authoritative plan names + order
    # WITHOUT paying to render any step images.
    names = region_plan_names(**_kwargs())
    eager = analyze_regions(**_kwargs()).plans
    assert names == [p.name for p in eager]
    assert names == [WHOLE_MINI, "B"]


def test_region_plan_names_renders_no_steps(monkeypatch):
    # It must resolve names from the specs only — never render a plan. This is
    # what makes the selector manifest cheap enough to fetch eagerly.
    import mini_highlight_advisor.pipeline as pl
    calls = {"n": 0}
    real = pl._render_spec

    def spy(rgb, spec, ekw):
        calls["n"] += 1
        return real(rgb, spec, ekw)

    monkeypatch.setattr(pl, "_render_spec", spy)
    region_plan_names(**_kwargs())
    assert calls["n"] == 0


def test_iter_region_plans_only_yields_single_named_plan():
    # On-demand fetch: the selector asks for exactly one region's steps, so
    # `only` must render just that plan (not all-then-discard).
    plans = list(iter_region_plans(only="B", **_kwargs()))
    assert [p.name for p in plans] == ["B"]

    eager_b = next(p for p in analyze_regions(**_kwargs()).plans if p.name == "B")
    (got,) = plans
    assert got.roles == eager_b.roles
    assert len(got.steps) == len(eager_b.steps) > 0
    for s_want, s_got in zip(eager_b.steps, got.steps):
        assert np.array_equal(s_got.zone_rgb, s_want.zone_rgb)


def test_iter_region_plans_only_renders_just_the_requested_plan(monkeypatch):
    # Memory contract: requesting one region renders one plan, not every plan.
    import mini_highlight_advisor.pipeline as pl
    calls = {"n": 0}
    real = pl._render_spec

    def spy(rgb, spec, ekw):
        calls["n"] += 1
        return real(rgb, spec, ekw)

    monkeypatch.setattr(pl, "_render_spec", spy)
    list(pl.iter_region_plans(only="B", **_kwargs()))
    assert calls["n"] == 1


def test_iter_region_plans_only_unknown_name_yields_nothing():
    assert list(iter_region_plans(only="does-not-exist", **_kwargs())) == []
