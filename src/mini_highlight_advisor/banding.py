from __future__ import annotations

import numpy as np


def band_light(light: np.ndarray, mask: np.ndarray, coverage: list[float]) -> np.ndarray:
    n = len(coverage)
    bands = np.full(light.shape, -1, dtype=np.int32)
    vals = light[mask]
    if vals.size == 0:
        return bands
    # Cumulative target fractions give the quantile cut points (interior boundaries only).
    cum = np.cumsum(coverage)[:-1]
    edges = np.quantile(vals, cum)
    idx = np.digitize(light, edges)  # 0..n-1
    bands[mask] = idx[mask].astype(np.int32)
    return bands
