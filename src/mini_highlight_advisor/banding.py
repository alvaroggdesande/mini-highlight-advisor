from __future__ import annotations

import numpy as np

# Minimum normalized-light spread (0..1) each band needs to be honest. The light
# field is stretched so the whole mini spans ~[0,1]; a flat sub-region occupies a
# narrow slice, so its p5..p95 spread measures how much relief it actually holds.
# 0.12 keeps the whole-mini (spread ~1.0) at ~8 supportable bands — never capping
# the default 5 on the known-good primed fixture — while a spread of ~0.25 drops
# to 2 bands and a near-constant region collapses to 1.
_MIN_SPREAD_PER_BAND = 0.12


def relief_recommended_bands(light: np.ndarray, mask: np.ndarray, requested_n: int) -> int:
    """Max band count the region's relief honestly supports, in ``[1, requested_n]``.

    Rank banding always emits ``requested_n`` crisp bands even where the light is
    flat — manufactured precision. This measures the region's own tonal spread and
    caps the count so flat regions don't get highlight bands the sculpt can't show.
    """
    vals = light[mask]
    if vals.size == 0:
        return 1
    p5, p95 = np.percentile(vals, [5, 95])
    spread = float(p95 - p5)
    supported = int(spread / _MIN_SPREAD_PER_BAND)
    return max(1, min(requested_n, supported))


def band_light(light: np.ndarray, mask: np.ndarray, coverage: list[float]) -> np.ndarray:
    n = len(coverage)
    bands = np.full(light.shape, -1, dtype=np.int32)
    vals = light[mask]
    m = vals.size
    if m == 0:
        return bands
    # Assign bands by pixel RANK in luminance order (darkest -> lightest), cutting
    # at cumulative coverage. Rank-based (not value-threshold) banding so a flat or
    # low-variance region still splits into the requested proportions instead of
    # collapsing every tied pixel into one band. On well-varied luminance this is
    # identical to value quantiles, since rank order matches value order.
    order = np.argsort(vals, kind="stable")          # ascending: darkest first
    ranks = np.empty(m, dtype=np.int64)
    ranks[order] = np.arange(m, dtype=np.int64)
    edges = np.cumsum(coverage)[:-1] * m             # interior cut points, in ranks
    bands[mask] = np.digitize(ranks, edges).astype(np.int32)  # 0..n-1
    return bands
