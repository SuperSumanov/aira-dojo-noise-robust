from __future__ import annotations

import csv
from pathlib import Path

import numpy as np
import pytest

from phase1 import task_topcenter_rank as rank_module
from phase1 import verify_task_topcenter_discovery as verifier_module


def row(
    better: str,
    worse: str,
    parent: str,
    task: str,
    run: str,
    gap: float = 1.0,
) -> dict:
    return {
        "better": better,
        "worse": worse,
        "parent": parent,
        "task": task,
        "run": run,
        "gap_raw": gap,
    }


def test_topcenter_edges_keep_only_winner_vs_rest_and_equalize_parents() -> None:
    rows = [
        row("a", "b", "p1", "t1", "r1"),
        row("a", "c", "p1", "t1", "r1"),
        row("b", "c", "p1", "t1", "r1"),
        row("d", "e", "p2", "t2", "r2"),
    ]
    selected, weights, audit = rank_module.objective_edges(
        rows, list(range(len(rows))), "topcenter"
    )
    assert selected == [0, 1, 3]
    assert audit["training_parents"] == 2
    assert audit["strict_complete_parents"] == 2
    p1_weight = sum(weight for index, weight in zip(selected, weights) if rows[index]["parent"] == "p1")
    p2_weight = sum(weight for index, weight in zip(selected, weights) if rows[index]["parent"] == "p2")
    assert p1_weight == pytest.approx(p2_weight)


def test_task_residual_fits_opposite_task_directions_and_unseen_falls_back() -> None:
    rows = [
        row("a1", "b1", "p1", "left", "r1"),
        row("a2", "b2", "p2", "left", "r2"),
        row("c1", "d1", "p3", "right", "r3"),
        row("c2", "d2", "p4", "right", "r4"),
    ]
    endpoint_ids = ["a1", "b1", "a2", "b2", "c1", "d1", "c2", "d2", "u1", "u2"]
    values = [1.0, -1.0, 2.0, -2.0, -1.0, 1.0, -2.0, 2.0, 0.5, -0.5]
    matrix = np.asarray(values, dtype=np.float64).reshape(-1, 1)
    position = {card_id: index for index, card_id in enumerate(endpoint_ids)}
    tasks = ["left", "right", "unseen"]
    weights, fit = rank_module.fit_ranker(
        rows,
        list(range(len(rows))),
        matrix,
        position,
        tasks,
        "allpair",
        True,
        0.1,
        0.1,
    )
    assert fit["accepted"]
    assert fit["unseen_tasks"] == ["unseen"]
    assert fit["unseen_task_residual_norms"]["unseen"] == 0.0
    endpoint_tasks = ["left", "left", "left", "left", "right", "right", "right", "right", "unseen", "unseen"]
    scores = rank_module.score_matrix(weights, matrix, endpoint_tasks)
    for item in rows:
        assert scores[position[item["better"]]] > scores[position[item["worse"]]]
    unseen_index = tasks.index("unseen")
    assert np.array_equal(weights["task_weights"][unseen_index], np.zeros(1))


def test_locked_baseline_rejects_forbidden_path_and_cross_run_fold(tmp_path: Path) -> None:
    rows = [
        row("a", "b", "p1", "t", "r"),
        row("c", "d", "p2", "t", "r"),
    ]
    forbidden = tmp_path / "decision_frozen_oof.csv"
    forbidden.write_text("", encoding="utf-8")
    with pytest.raises(rank_module.IntegrityError, match="forbidden"):
        rank_module.load_locked_baseline(forbidden, rows, rank_module.sha256(forbidden))

    baseline = tmp_path / "oof_predictions.csv"
    with baseline.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(
            handle,
            fieldnames=[
                "row_index",
                "task",
                "run",
                "parent",
                "better",
                "worse",
                "fold",
                "better_score",
                "worse_score",
            ],
        )
        writer.writeheader()
        for index, (item, fold) in enumerate(zip(rows, [0, 1])):
            writer.writerow(
                {
                    "row_index": index,
                    "task": item["task"],
                    "run": item["run"],
                    "parent": item["parent"],
                    "better": item["better"],
                    "worse": item["worse"],
                    "fold": fold,
                    "better_score": 1.0,
                    "worse_score": 0.0,
                }
            )
    with pytest.raises(rank_module.IntegrityError, match="spans outer folds"):
        rank_module.load_locked_baseline(baseline, rows, rank_module.sha256(baseline))


def test_hyperparameter_grids_are_preregistered_sizes() -> None:
    assert set(rank_module.FAMILIES) == {
        "nested_global_allpair",
        "nested_global_topcenter",
        "nested_task_allpair",
        "nested_task_topcenter",
    }
    assert rank_module.hyperparameter_grid(False) == [
        {"lambda_global": 0.001, "lambda_task": None},
        {"lambda_global": 0.005, "lambda_task": None},
        {"lambda_global": 0.02, "lambda_task": None},
    ]
    assert len(rank_module.hyperparameter_grid(True)) == 9


def test_independent_metrics_match_producer() -> None:
    rows = [
        row("a", "b", "p1", "t1", "r1", 2.0),
        row("a", "c", "p1", "t1", "r1", 1.0),
        row("b", "c", "p1", "t1", "r1", 0.5),
        row("d", "e", "p2", "t2", "r2", 3.0),
    ]
    scores = {"a": 3.0, "b": 2.0, "c": 1.0, "d": 0.0, "e": 1.0}
    producer = rank_module.model_metrics(rows, scores, 200)
    verifier = verifier_module.model_metrics(rows, scores, 200)
    for metric in ("pair", "top1", "utility"):
        for key in ("overall", "run_macro", "task_macro", "run_macro_ci95", "task_macro_ci95"):
            assert producer[metric][key] == verifier[metric][key]
    assert producer["task_consistency"] == verifier["task_consistency"]
    selection = rank_module.selection_metrics(rows, scores)
    assert selection["pair_accuracy"] == producer["pair"]["overall"]
    assert selection["complete_parent_top1"] == producer["top1"]["overall"]
    assert selection["parent_equal_gap_utility"] == producer["utility"]["overall"]


def test_checkpoint_weights_are_exact_float64(tmp_path: Path) -> None:
    path = tmp_path / "weights.npz"
    weights = {
        "global_weight": np.asarray([1.0, 2.0], dtype=np.float64),
        "task_weights": np.asarray([[3.0, 4.0]], dtype=np.float64),
        "task_names": np.asarray(["task"], dtype="U"),
    }
    rank_module.save_weights(path, weights)
    with np.load(path, allow_pickle=False) as data:
        assert data["global_weight"].dtype == np.float64
        assert data["task_weights"].dtype == np.float64


def test_outer_fold_checkpoint_resumes_without_refit(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    rows = [
        row(f"a{fold}", f"b{fold}", f"p{fold}", "task", f"r{fold}")
        for fold in range(5)
    ]
    endpoint_ids = [value for fold in range(5) for value in (f"a{fold}", f"b{fold}")]
    matrix = np.asarray(
        [[1.0] if card_id.startswith("a") else [-1.0] for card_id in endpoint_ids],
        dtype=np.float64,
    )
    position = {card_id: index for index, card_id in enumerate(endpoint_ids)}

    def fixed_selection(family: str, *args, **kwargs):
        task_residual = bool(rank_module.FAMILIES[family]["task_residual"])
        configuration = {
            "lambda_global": 0.1,
            "lambda_task": 0.1 if task_residual else None,
        }
        return configuration, {
            "family": family,
            "selection_order": [],
            "selected": configuration,
            "selected_key": [],
            "candidates": [],
        }

    monkeypatch.setattr(rank_module, "select_hyperparameters", fixed_selection)
    first_scores, first = rank_module.run_outer_fold(
        0,
        tmp_path / "checkpoints",
        "checkpoint-key",
        rows,
        [0, 1, 2, 3, 4],
        matrix,
        position,
        ["task"] * len(endpoint_ids),
        ["task"],
    )
    second_scores, second = rank_module.run_outer_fold(
        0,
        tmp_path / "checkpoints",
        "checkpoint-key",
        rows,
        [0, 1, 2, 3, 4],
        matrix,
        position,
        ["task"] * len(endpoint_ids),
        ["task"],
    )
    assert first["resumed"] is False
    assert second["resumed"] is True
    assert first_scores == second_scores
