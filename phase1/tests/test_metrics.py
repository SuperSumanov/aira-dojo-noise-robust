"""Unit checks for the pure-numpy metrics (known-answer)."""
import numpy as np

from phase1.eval import metrics as M


def test_spearman_monotone():
    assert abs(M.spearman([1, 2, 3, 4], [1, 2, 3, 4]) - 1.0) < 1e-9
    assert abs(M.spearman([1, 2, 3, 4], [4, 3, 2, 1]) + 1.0) < 1e-9


def test_spearman_handles_ties():
    # rankdata averages ties -> no NaN, finite correlation
    v = M.spearman([1, 1, 2, 2], [1, 2, 1, 2])
    assert np.isfinite(v)


def test_kendall_monotone():
    assert abs(M.kendall_tau([1, 2, 3, 4], [1, 2, 3, 4]) - 1.0) < 1e-9
    assert abs(M.kendall_tau([1, 2, 3, 4], [4, 3, 2, 1]) + 1.0) < 1e-9


def test_top_k_regret():
    y = [0.1, 0.5, 0.9]
    # pred ranks item2 top -> its y is the global best -> regret 0
    assert M.top_k_regret(y, [0.2, 0.4, 0.99], k=1) == 0.0
    # pred ranks item0 top -> y=0.1 vs best 0.9 -> regret 0.8
    assert abs(M.top_k_regret(y, [0.9, 0.4, 0.2], k=1) - 0.8) < 1e-9
    # k=2 window contains the best -> regret 0
    assert M.top_k_regret(y, [0.9, 0.1, 0.5], k=2) == 0.0


def test_ece_perfect_is_zero():
    y = [0.05, 0.25, 0.55, 0.95]
    assert M.ece(y, y, n_bins=10) < 1e-9


def test_bootstrap_ci_brackets_point():
    rng = np.random.default_rng(0)
    y = rng.uniform(0, 1, 40)
    p = y + rng.normal(0, 0.1, 40)
    point, lo, hi = M.bootstrap_ci(y, p, "spearman", n_boot=300, seed=1)
    assert lo <= point <= hi
