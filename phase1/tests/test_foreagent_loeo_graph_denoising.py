from __future__ import annotations

import json

import numpy as np

from phase1.analyze_foreagent_loeo_graph_denoising import (
    bootstrap_metrics,
    incidence_matrix,
    load_common_support,
    loeo_projection,
    point_metrics,
    task_statistics,
)
from phase1.verify_foreagent_loeo_graph_denoising import grounded_projection


def test_closed_form_loeo_matches_brute_force() -> None:
    rows = [
        {"pair": ("a", "b")},
        {"pair": ("a", "c")},
        {"pair": ("a", "d")},
        {"pair": ("b", "c")},
        {"pair": ("b", "d")},
        {"pair": ("c", "d")},
    ]
    _, matrix = incidence_matrix(rows)
    flow = np.asarray([1.0, 1.0, -1.0, 1.0, 1.0, 1.0])
    result = loeo_projection(matrix, flow)
    assert np.all(result["leverage"] < 1.0 - 1e-10)
    assert np.all(np.isfinite(result["loeo"]))
    for edge in range(matrix.shape[0]):
        keep = np.arange(matrix.shape[0]) != edge
        potential, *_ = np.linalg.lstsq(matrix[keep], flow[keep], rcond=None)
        expected = float(matrix[edge] @ potential)
        assert abs(float(result["loeo"][edge]) - expected) < 1e-10


def test_tree_edges_are_not_loeo_evaluable() -> None:
    rows = [
        {"pair": ("a", "b")},
        {"pair": ("b", "c")},
        {"pair": ("c", "d")},
    ]
    _, matrix = incidence_matrix(rows)
    result = loeo_projection(matrix, np.asarray([1.0, -1.0, 1.0]))
    assert np.allclose(result["leverage"], 1.0, atol=1e-10)
    assert not np.any(result["evaluable"])


def test_orientation_reversal_preserves_loeo_prediction() -> None:
    rows = [
        {"pair": ("a", "b")},
        {"pair": ("a", "c")},
        {"pair": ("b", "c")},
    ]
    _, matrix = incidence_matrix(rows)
    flow = np.asarray([1.0, 1.0, 1.0])
    forward = loeo_projection(matrix, flow)
    reversed_result = loeo_projection(-matrix, -flow)
    assert np.allclose(forward["loeo"], -reversed_result["loeo"], atol=1e-12)
    assert np.array_equal(forward["evaluable"], reversed_result["evaluable"])


def test_loader_canonicalizes_reversed_pair_order(tmp_path) -> None:
    files = []
    rows = []
    for model in ("deepseek", "gpt"):
        for release in (1, 2, 3):
            source_index = len(files)
            files.append(
                {
                    "model_family": model,
                    "task": "task-a",
                    "release_run": release,
                }
            )
            reversed_order = release == 2
            paths = ["b", "a"] if reversed_order else ["a", "b"]
            scores = [0.0, 1.0] if reversed_order else [1.0, 0.0]
            rows.append(
                {
                    "source_index": source_index,
                    "task": "task-a",
                    "model_family": model,
                    "release_run": release,
                    "solution_paths": paths,
                    "scores": scores,
                    "is_lower_better": False,
                    "groundtruth_best_index": 1 if reversed_order else 0,
                    "prediction_best_index": 1 if reversed_order else 0,
                }
            )
            rows.append(
                {
                    "source_index": source_index,
                    "task": "task-a",
                    "model_family": model,
                    "release_run": release,
                    "solution_paths": ["c", "d"],
                    "scores": [float("nan"), 0.0],
                    "is_lower_better": False,
                    "groundtruth_best_index": 0,
                    "prediction_best_index": 0,
                }
            )
    manifest = tmp_path / "manifest.json"
    master = tmp_path / "master.jsonl"
    manifest.write_text(json.dumps({"files": files}), encoding="utf-8")
    master.write_text("".join(json.dumps(row) + "\n" for row in rows), encoding="utf-8")
    support, population = load_common_support(
        manifest, master, production_checks=False
    )
    assert population["pairs"] == 1
    assert support["task-a"][0]["pair"] == ("a", "b")
    assert support["task-a"][0]["truth_sign"] == 1.0
    assert support["task-a"][0]["deepseek_flow"] == 1.0
    assert support["task-a"][0]["gpt_flow"] == 1.0


def test_task_statistics_falls_back_on_bridges() -> None:
    rows = [
        {
            "pair": ("a", "b"),
            "truth_sign": 1.0,
            "deepseek_flow": 1.0,
        },
        {
            "pair": ("b", "c"),
            "truth_sign": -1.0,
            "deepseek_flow": 1.0,
        },
    ]
    stats = task_statistics(rows, "deepseek")
    assert stats["evaluable_n"] == 0.0
    assert stats["raw_correct"] == stats["hybrid_correct"] == 1.0


def test_bootstrap_is_deterministic_and_task_clustered() -> None:
    per_task = [
        {
            "n": 10.0,
            "raw_correct": 5.0,
            "hybrid_correct": 6.0,
            "evaluable_n": 8.0,
            "raw_evaluable_correct": 4.0,
            "loeo_correct": 5.0,
        },
        {
            "n": 20.0,
            "raw_correct": 10.0,
            "hybrid_correct": 10.0,
            "evaluable_n": 10.0,
            "raw_evaluable_correct": 5.0,
            "loeo_correct": 5.0,
        },
    ]
    first = bootstrap_metrics(per_task, repetitions=1000, seed=7)
    second = bootstrap_metrics(per_task, repetitions=1000, seed=7)
    assert first == second
    assert abs(point_metrics(per_task)["hybrid_minus_raw_task_macro"] - 0.05) < 1e-12


def test_independent_grounded_verifier_matches_pseudoinverse() -> None:
    producer_rows = [
        {"pair": ("a", "b"), "truth_sign": 1.0, "deepseek_flow": 1.0},
        {"pair": ("a", "c"), "truth_sign": 1.0, "deepseek_flow": 1.0},
        {"pair": ("a", "d"), "truth_sign": 1.0, "deepseek_flow": -1.0},
        {"pair": ("b", "c"), "truth_sign": 1.0, "deepseek_flow": 1.0},
        {"pair": ("b", "d"), "truth_sign": 1.0, "deepseek_flow": 1.0},
        {"pair": ("c", "d"), "truth_sign": 1.0, "deepseek_flow": 1.0},
    ]
    verifier_rows = [
        {"pair": row["pair"], "truth": -row["truth_sign"], "deepseek": -row["deepseek_flow"]}
        for row in producer_rows
    ]
    producer = task_statistics(producer_rows, "deepseek")
    verifier = grounded_projection(verifier_rows, "deepseek")
    for key in (
        "n",
        "rank",
        "raw_correct",
        "hybrid_correct",
        "evaluable_n",
        "raw_evaluable_correct",
        "loeo_correct",
        "bridge_or_zero_n",
        "leverage_sum",
        "residual_energy",
    ):
        assert abs(producer[key] - verifier[key]) < 1e-10
