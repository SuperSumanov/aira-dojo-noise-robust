from __future__ import annotations

import math

import pytest

sklearn_metrics = pytest.importorskip("sklearn.metrics")
scipy_stats = pytest.importorskip("scipy.stats")

from phase1.balanced_continuation_e2a_scoring import compute_score


def test_all_six_metrics_match_independent_libraries() -> None:
    assert compute_score(
        "spaceship-titanic", [True, False, True, False], [True, True, True, False]
    ) == sklearn_metrics.accuracy_score([True, False, True, False], [True, True, True, False])

    binary = [0, 0, 1, 1]
    probabilities = [0.1, 0.4, 0.35, 0.8]
    assert compute_score(
        "tabular-playground-series-may-2022", binary, probabilities
    ) == pytest.approx(sklearn_metrics.roc_auc_score(binary, probabilities), abs=1e-15)

    authors = ["EAP", "HPL", "MWS", "EAP"]
    author_probabilities = [
        (0.8, 0.1, 0.1), (0.2, 0.7, 0.1), (0.1, 0.2, 0.7), (0.6, 0.2, 0.2)
    ]
    assert compute_score(
        "spooky-author-identification", authors, author_probabilities
    ) == pytest.approx(
        sklearn_metrics.log_loss(authors, author_probabilities, labels=["EAP", "HPL", "MWS"]),
        abs=1e-15,
    )

    similarity = [0.0, 0.25, 0.5, 0.75, 1.0]
    predicted_similarity = [0.1, 0.3, 0.45, 0.8, 0.9]
    assert compute_score(
        "us-patent-phrase-to-phrase-matching", similarity, predicted_similarity
    ) == pytest.approx(scipy_stats.pearsonr(similarity, predicted_similarity).statistic, abs=1e-15)

    material = [(0.0, 1.0), (0.5, 2.0), (3.0, 8.0), (1.5, 4.0)]
    predicted_material = [(0.1, 1.1), (0.4, 2.2), (2.8, 7.5), (1.6, 4.2)]
    independent_columns = []
    for column in range(2):
        independent_columns.append(math.sqrt(sklearn_metrics.mean_squared_log_error(
            [row[column] for row in material],
            [row[column] for row in predicted_material],
        )))
    assert compute_score(
        "nomad2018-predict-transparent-conductors", material, predicted_material
    ) == pytest.approx(sum(independent_columns) / 2, abs=1e-15)

    essay = [1, 2, 3, 4, 5, 6, 2, 5]
    predicted_essay = [1, 2, 4, 4, 5, 6, 3, 4]
    assert compute_score(
        "learning-agency-lab-automated-essay-scoring-2", essay, predicted_essay
    ) == pytest.approx(
        sklearn_metrics.cohen_kappa_score(essay, predicted_essay, weights="quadratic"),
        abs=1e-15,
    )
