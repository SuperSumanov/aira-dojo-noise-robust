import copy

import pytest

from phase1.source_opportunity_hurdle_baseline import (
    ARMS,
    BaselineError,
    classify_node,
    fit_and_score,
    parent_metrics,
    scan_file,
    static_features,
    tie_mean,
)


def test_classify_node_separates_scoreability_from_execution():
    assert classify_node({"exit_code": 1}) == ("EXECUTION_ERROR", False, False)
    assert classify_node({"exit_code": 0, "metric_info": {}}) == (
        "OFFICIAL_GRADE_ABSENT", True, False
    )
    assert classify_node({"exit_code": 0, "metric_info": {"score": 0.7}}) == (
        "NORMALIZATION_METADATA_ABSENT", True, False
    )
    category, exec_ok, scoreable = classify_node(
        {"exit_code": 0, "metric_info": {"score": 0.7, "bronze_threshold": 0.5}}
    )
    assert (category, exec_ok, scoreable) == ("SCOREABLE", True, True)


def test_static_features_are_pre_execution_only():
    features = static_features(
        "import sklearn\nfor seed in range(3):\n    print(seed)\n", "task", "Debug", 4, 2
    )
    assert features["task"] == "task"
    assert features["operator"] == "Debug"
    assert features["n_seed"] > 0
    forbidden = {"runtime", "stdout", "self_report", "exit_code", "grade", "scoreable"}
    assert forbidden.isdisjoint(features)


def test_tie_mean_is_label_blind_and_analytic():
    assert tie_mean([(1.0, 0.0), (1.0, 1.0), (0.2, 1.0)]) == 0.5


def _train_rows():
    rows = []
    for parent_index in range(4):
        for positive in (False, True):
            token = "valid_pipeline" if positive else "broken_pipeline"
            code = f"import pandas as pd\n# shared shared shared {token} p{parent_index}\n"
            rows.append(
                {
                    "role": "train",
                    "parent": f"p{parent_index}",
                    "task": "task-a" if parent_index < 2 else "task-b",
                    "run_id": f"run-{parent_index}",
                    "child_id": f"c{parent_index}-{int(positive)}",
                    "code": code,
                    "static": {"task": "task-a", "operator": "Draft", "x": float(positive)},
                    "scoreable": positive,
                    "y_norm": 0.6 + 0.05 * parent_index if positive else None,
                }
            )
    return rows


def _score_rows():
    return [
        {
            "role": "frozen",
            "parent": "fp",
            "task": "task-a",
            "run_id": "fr",
            "child_id": f"fc{index}",
            "code": f"import pandas as pd\n# shared shared shared {'valid_pipeline' if index else 'broken_pipeline'}\n",
            "static": {"task": "task-a", "operator": "Draft", "x": float(index)},
        }
        for index in (0, 1)
    ]


def test_frozen_labels_cannot_change_fit_or_scores():
    train = _train_rows()
    score = _score_rows()
    first, diagnostics = fit_and_score(train, score)
    altered = copy.deepcopy(score)
    for index, row in enumerate(altered):
        row["scoreable"] = bool(index == 0)
        row["y_norm"] = 1.0 - index
        row["utility"] = 1.0 - index
    second, _ = fit_and_score(train, altered)
    assert first == second
    assert diagnostics["fit_roles"] == ["train"]


def test_identical_scores_make_permuted_labels_equal_random_expectation():
    rows = []
    scores = {}
    for parent in ("a", "b"):
        for index, label in enumerate((0, 1)):
            child = f"{parent}-{index}"
            rows.append(
                {
                    "role": "frozen", "parent": parent, "task": "task",
                    "run_id": parent, "child_id": child, "scoreable": bool(label),
                    "utility": float(label),
                }
            )
            scores[child] = {arm: 0.0 for arm in ARMS}
    metrics = parent_metrics(rows, scores, "frozen")
    for row in metrics:
        assert row["hurdle_tfidf_scoreability"] == row["random_expected_scoreability"]
        assert row["hurdle_tfidf_utility"] == row["random_expected_utility"]


def test_scan_file_refuses_credential_shape(tmp_path):
    path = tmp_path / "journal.jsonl"
    path.write_bytes(b'{"code":"sk-' + b"a" * 24 + b'"}\n')
    with pytest.raises(BaselineError, match="credential-shaped"):
        scan_file(path)
