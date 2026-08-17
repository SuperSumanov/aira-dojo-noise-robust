from __future__ import annotations

from phase1.failure_mechanism_length_heterogeneity import (
    heterogeneity_stat,
    stratified_permutation_p,
)

import numpy as np


def test_weighted_heterogeneity_statistic_is_zero_for_equal_means() -> None:
    categories = np.array([0, 0, 1, 1], dtype=np.int16)
    values = np.array([0.0, 1.0, 0.0, 1.0])
    assert heterogeneity_stat(categories, values, 2) == 0.0


def test_task_stratified_permutation_detects_repeated_category_difference(monkeypatch) -> None:
    import phase1.failure_mechanism_length_heterogeneity as module

    monkeypatch.setattr(module, "PERMUTATIONS", 2_000)
    rows = []
    for task_index in range(5):
        for pair_index in range(20):
            rows.append(
                {
                    "category": "high" if pair_index < 10 else "low",
                    "task": f"task-{task_index}",
                    "length_credit": 1.0 if pair_index < 10 else 0.0,
                }
            )
    observed, p_value = stratified_permutation_p(rows, "length_credit")
    assert observed > 0.2
    assert p_value < 0.01
