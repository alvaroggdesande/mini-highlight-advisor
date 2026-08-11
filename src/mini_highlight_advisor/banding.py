from __future__ import annotations

import numpy as np


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
