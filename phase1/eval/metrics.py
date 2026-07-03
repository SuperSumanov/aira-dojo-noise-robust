"""Pure-numpy evaluation metrics for value critics. No scipy/sklearn dependency (keeps the mock
smoke lightweight and the remote install trivial).

A critic outputs a scalar score per held-out card; the label is y_norm in [0,1]. What we care about
under FEW + EXPENSIVE labels:
  * ranking quality      -> spearman, kendall_tau  (do higher-scored candidates really grade higher)
  * decision quality     -> top_k_regret           (if I keep the top-k by the critic, how far below
                                                     the true best do I land — the thing a search loop
                                                     actually pays for)
  * calibration          -> ece                    (does a predicted 0.8 mean ~0.8 graded — matters if
                                                     a threshold/あきらめ rule reads the value)
Uncertainty via nonparametric bootstrap over the test items (bootstrap_ci).
"""
from __future__ import annotations

from typing import Callable, Dict, List, Sequence, Tuple

import numpy as np


def _rankdata(a: np.ndarray) -> np.ndarray:
    """Average ranks (ties -> mean rank), 1-based. scipy.stats.rankdata equivalent."""
    a = np.asarray(a, dtype=float)
    order = np.argsort(a, kind="mergesort")
    ranks = np.empty(len(a), dtype=float)
    sa = a[order]
    i = 0
    n = len(a)
    while i < n:
        j = i
        while j + 1 < n and sa[j + 1] == sa[i]:
            j += 1
        ranks[order[i:j + 1]] = 0.5 * (i + j) + 1.0  # mean of 1-based positions i+1..j+1
        i = j + 1
    return ranks


def _pearson(x: np.ndarray, y: np.ndarray) -> float:
    x = np.asarray(x, float); y = np.asarray(y, float)
    if len(x) < 2:
        return float("nan")
    xc, yc = x - x.mean(), y - y.mean()
    d = np.sqrt((xc * xc).sum() * (yc * yc).sum())
    return float(xc.dot(yc) / d) if d > 0 else 0.0


def spearman(y_true: Sequence[float], y_pred: Sequence[float]) -> float:
    if len(y_true) < 2:
        return float("nan")
    return _pearson(_rankdata(np.asarray(y_true)), _rankdata(np.asarray(y_pred)))


def kendall_tau(y_true: Sequence[float], y_pred: Sequence[float]) -> float:
    """Tau-b (ties-corrected). O(n^2) — fine for the per-task test sizes here."""
    a = np.asarray(y_true, float); b = np.asarray(y_pred, float)
    n = len(a)
    if n < 2:
        return float("nan")
    conc = disc = 0
    tie_a = tie_b = 0
    for i in range(n - 1):
        da = a[i + 1:] - a[i]
        db = b[i + 1:] - b[i]
        prod = np.sign(da) * np.sign(db)
        conc += int((prod > 0).sum())
        disc += int((prod < 0).sum())
        tie_a += int((da == 0).sum())
        tie_b += int((db == 0).sum())
    n0 = n * (n - 1) / 2.0
    denom = np.sqrt(max(1e-12, (n0 - tie_a)) * max(1e-12, (n0 - tie_b)))
    return float((conc - disc) / denom) if denom > 0 else 0.0


def top_k_regret(y_true: Sequence[float], y_pred: Sequence[float], k: int = 1) -> float:
    """best achievable y_true  -  best y_true among the k highest-y_pred items. 0 = critic's top-k
    contains the true best; larger = worse decision. Normalized already (y in [0,1])."""
    a = np.asarray(y_true, float); b = np.asarray(y_pred, float)
    if len(a) == 0:
        return float("nan")
    k = min(k, len(a))
    topk = np.argsort(-b, kind="mergesort")[:k]
    return float(a.max() - a[topk].max())


def ece(y_true: Sequence[float], y_pred: Sequence[float], n_bins: int = 10) -> float:
    """Expected calibration error for a [0,1] regression target: |mean_pred - mean_true| per equal-width
    prediction bin, weighted by bin population. Predictions are clipped to [0,1] first."""
    a = np.asarray(y_true, float)
    b = np.clip(np.asarray(y_pred, float), 0.0, 1.0)
    if len(a) == 0:
        return float("nan")
    edges = np.linspace(0.0, 1.0, n_bins + 1)
    idx = np.clip(np.digitize(b, edges[1:-1]), 0, n_bins - 1)
    e = 0.0
    for k in range(n_bins):
        m = idx == k
        if m.any():
            e += (m.sum() / len(a)) * abs(b[m].mean() - a[m].mean())
    return float(e)


METRICS: Dict[str, Callable[[Sequence[float], Sequence[float]], float]] = {
    "spearman": spearman,
    "kendall": kendall_tau,
    "regret@1": lambda t, p: top_k_regret(t, p, 1),
    "regret@3": lambda t, p: top_k_regret(t, p, 3),
    "regret@5": lambda t, p: top_k_regret(t, p, 5),
    "ece": ece,
}
# For sample-efficiency plots: True = higher is better.
METRIC_HIGHER_BETTER = {"spearman": True, "kendall": True,
                        "regret@1": False, "regret@3": False, "regret@5": False, "ece": False}


def compute_all(y_true: Sequence[float], y_pred: Sequence[float]) -> Dict[str, float]:
    return {name: fn(y_true, y_pred) for name, fn in METRICS.items()}


def bootstrap_ci(y_true: Sequence[float], y_pred: Sequence[float], metric: str,
                 n_boot: int = 1000, seed: int = 0, alpha: float = 0.05) -> Tuple[float, float, float]:
    """(point, lo, hi) with a percentile bootstrap over test items."""
    fn = METRICS[metric]
    a = np.asarray(y_true, float); b = np.asarray(y_pred, float)
    point = fn(a, b)
    n = len(a)
    if n < 3:
        return point, float("nan"), float("nan")
    rng = np.random.default_rng(seed)
    vals = np.empty(n_boot)
    for i in range(n_boot):
        idx = rng.integers(0, n, n)
        vals[i] = fn(a[idx], b[idx])
    vals = vals[np.isfinite(vals)]
    if len(vals) == 0:
        return point, float("nan"), float("nan")
    lo, hi = np.quantile(vals, [alpha / 2, 1 - alpha / 2])
    return float(point), float(lo), float(hi)
