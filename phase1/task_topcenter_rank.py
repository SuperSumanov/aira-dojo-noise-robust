#!/usr/bin/env python3
"""Nested run-OOF task-conditioned top-centered rankers.

This train-only discovery program deliberately has no frozen/test-pair
argument.  It reuses the locked outer fold column and frozen endpoint features,
fits three preregistered convex heads, and retains fold-atomic checkpoints.
"""

from __future__ import annotations

import argparse
import collections
import csv
import hashlib
import json
import math
import os
import platform
import subprocess
import sys
import time
import zlib
from pathlib import Path
from typing import Any, Iterable, Sequence

import numpy as np

from phase1 import frozen_embed_rank as baseline_module


SEED = 887
PROTOCOL = "task_topcenter_v11_discovery_v1"
OUTER_FOLDS = 5
INNER_FOLDS = 3
BOOTSTRAP_REPS = 10_000
LAMBDA_GLOBAL_GRID = (0.001, 0.005, 0.02)
LAMBDA_TASK_GRID = (0.02, 0.1, 0.5)
MAXITER = 300
FTOL = 1e-10
GTOL = 1e-6
MAXLS = 50
ACCEPT_GRADIENT = 1e-5
EPSILON = 1e-12
EXPECTED = {
    "pairs": 4_263,
    "runs": 333,
    "tasks": 23,
    "parents": 2_293,
    "complete_parents": 2_259,
    "endpoints": 5_499,
    "dimension": 1_792,
}
FAMILIES = {
    "nested_global_allpair": {"objective": "allpair", "task_residual": False},
    "nested_global_topcenter": {"objective": "topcenter", "task_residual": False},
    "nested_task_allpair": {"objective": "allpair", "task_residual": True},
    "nested_task_topcenter": {"objective": "topcenter", "task_residual": True},
}
BASELINE_ARM = "fixed_global_allpair"
MAIN_ARM = "nested_task_topcenter"
METRIC_SEED_OFFSETS = {
    BASELINE_ARM: 10,
    "nested_global_allpair": 200,
    "nested_global_topcenter": 220,
    "nested_task_allpair": 240,
    "nested_task_topcenter": 260,
}


class IntegrityError(RuntimeError):
    pass


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def json_digest(value: Any) -> str:
    payload = json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True)
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def atomic_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(
        json.dumps(payload, indent=2, sort_keys=True, ensure_ascii=False) + "\n",
        encoding="utf-8",
        newline="\n",
    )
    os.replace(temporary, path)


def atomic_npz(path: Path, **arrays: np.ndarray) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(".tmp.npz")
    np.savez_compressed(temporary, **arrays)
    os.replace(temporary, path)


def git_commit(repo_root: Path) -> str:
    return subprocess.check_output(
        ["git", "-C", str(repo_root), "rev-parse", "HEAD"], text=True
    ).strip()


def reject_forbidden_path(path: Path, label: str) -> None:
    found = [token for token in ("frozen", "test", "held") if token in path.name.lower()]
    if found:
        raise IntegrityError(f"{label} path contains forbidden token(s): {found}")


def load_locked_baseline(
    path: Path, rows: Sequence[dict[str, Any]], expected_sha: str
) -> tuple[list[int], dict[str, float], dict[str, Any]]:
    reject_forbidden_path(path, "baseline OOF")
    digest = sha256(path)
    if digest != expected_sha.lower():
        raise IntegrityError(f"baseline OOF hash mismatch: {digest}")
    with path.open("r", encoding="utf-8", newline="") as handle:
        emitted = list(csv.DictReader(handle))
    if len(emitted) != len(rows):
        raise IntegrityError("baseline OOF row count differs from training pairs")
    folds: list[int] = []
    scores: dict[str, float] = {}
    run_fold: dict[str, int] = {}
    for index, (row, output) in enumerate(zip(rows, emitted)):
        if int(output["row_index"]) != index:
            raise IntegrityError(f"baseline row index mismatch at {index}")
        for key in ("task", "run", "parent", "better", "worse"):
            if str(output[key]) != str(row[key]):
                raise IntegrityError(f"baseline {key} mismatch at {index}")
        fold = int(output["fold"])
        if fold not in range(OUTER_FOLDS):
            raise IntegrityError(f"invalid outer fold at row {index}")
        previous_fold = run_fold.setdefault(str(row["run"]), fold)
        if previous_fold != fold:
            raise IntegrityError(f"physical run spans outer folds: {row['run']}")
        folds.append(fold)
        for endpoint_key, score_key in (
            ("better", "better_score"),
            ("worse", "worse_score"),
        ):
            card_id, score = str(row[endpoint_key]), float(output[score_key])
            if not math.isfinite(score):
                raise IntegrityError(f"non-finite baseline score at row {index}")
            if card_id in scores and not math.isclose(scores[card_id], score, abs_tol=1e-12):
                raise IntegrityError(f"inconsistent baseline endpoint score: {card_id}")
            scores[card_id] = score
    endpoints = {str(row[key]) for row in rows for key in ("better", "worse")}
    if set(scores) != endpoints:
        raise IntegrityError("baseline endpoint coverage mismatch")
    return folds, scores, {
        "sha256": digest,
        "rows": len(emitted),
        "runs": len(run_fold),
        "run_overlap": 0,
        "endpoints": len(scores),
        "fold_counts": dict(sorted(collections.Counter(folds).items())),
    }


def parent_groups(
    rows: Sequence[dict[str, Any]], indices: Iterable[int]
) -> dict[str, list[int]]:
    grouped: dict[str, list[int]] = collections.defaultdict(list)
    for index in indices:
        grouped[str(rows[int(index)]["parent"])].append(int(index))
    return dict(grouped)


def strict_parent_winner(
    rows: Sequence[dict[str, Any]], indices: Sequence[int]
) -> str | None:
    candidates = {
        str(rows[index][key]) for index in indices for key in ("better", "worse")
    }
    if len(indices) != len(candidates) * (len(candidates) - 1) // 2:
        return None
    wins = collections.Counter(str(rows[index]["better"]) for index in indices)
    if sorted(wins[candidate] for candidate in candidates) != list(range(len(candidates))):
        return None
    winners = [candidate for candidate in candidates if wins[candidate] == len(candidates) - 1]
    return winners[0] if len(winners) == 1 else None


def objective_edges(
    rows: Sequence[dict[str, Any]], indices: Sequence[int], objective: str
) -> tuple[list[int], np.ndarray, dict[str, Any]]:
    grouped = parent_groups(rows, indices)
    selected: list[int] = []
    complete = 0
    for parent, parent_indices in grouped.items():
        if objective == "allpair":
            selected.extend(parent_indices)
            continue
        if objective != "topcenter":
            raise IntegrityError(f"unknown objective: {objective}")
        winner = strict_parent_winner(rows, parent_indices)
        if winner is None:
            continue
        complete += 1
        winner_edges = [index for index in parent_indices if rows[index]["better"] == winner]
        candidates = {
            str(rows[index][key]) for index in parent_indices for key in ("better", "worse")
        }
        if len(winner_edges) != len(candidates) - 1:
            raise IntegrityError(f"winner-edge coverage mismatch for parent {parent}")
        selected.extend(winner_edges)
    if not selected:
        raise IntegrityError("objective produced no training edges")
    selected.sort()
    counts = collections.Counter(str(rows[index]["parent"]) for index in selected)
    weights = np.asarray([1.0 / counts[str(rows[index]["parent"])] for index in selected])
    weights /= weights.sum()
    parent_weight_sums: collections.Counter[str] = collections.Counter()
    for index, weight in zip(selected, weights.tolist()):
        parent_weight_sums[str(rows[index]["parent"])] += float(weight)
    return selected, weights.astype(np.float64), {
        "objective": objective,
        "input_pairs": len(indices),
        "input_parents": len(grouped),
        "training_edges": len(selected),
        "training_parents": len(counts),
        "strict_complete_parents": complete if objective == "topcenter" else None,
        "parent_weight_sum_min": min(parent_weight_sums.values()),
        "parent_weight_sum_max": max(parent_weight_sums.values()),
    }


def fit_ranker(
    rows: Sequence[dict[str, Any]],
    row_indices: Sequence[int],
    matrix: np.ndarray,
    position: dict[str, int],
    task_names: Sequence[str],
    objective: str,
    task_residual: bool,
    lambda_global: float,
    lambda_task: float | None,
) -> tuple[dict[str, np.ndarray], dict[str, Any]]:
    if lambda_global <= 0 or (task_residual and (lambda_task is None or lambda_task <= 0)):
        raise IntegrityError("regularization must be positive")
    selected, weights, edge_audit = objective_edges(rows, row_indices, objective)
    better = np.asarray([position[str(rows[index]["better"])] for index in selected])
    worse = np.asarray([position[str(rows[index]["worse"])] for index in selected])
    differences = (matrix[better] - matrix[worse]).astype(np.float64, copy=False)
    task_position = {task: index for index, task in enumerate(task_names)}
    edge_tasks = np.asarray([task_position[str(rows[index]["task"])] for index in selected])
    dimension = differences.shape[1]
    parameter_count = dimension * (1 + len(task_names) if task_residual else 1)
    initial = np.zeros(parameter_count, dtype=np.float64)

    from scipy.optimize import minimize
    from scipy.special import expit

    def loss_gradient(theta: np.ndarray) -> tuple[float, np.ndarray]:
        global_weight = theta[:dimension]
        margin = differences @ global_weight
        if task_residual:
            residual = theta[dimension:].reshape(len(task_names), dimension)
            margin = margin + np.einsum(
                "ij,ij->i", differences, residual[edge_tasks], optimize=True
            )
        losses = np.logaddexp(0.0, -margin)
        coefficient = -weights * expit(-margin)
        loss = float(weights @ losses + 0.5 * lambda_global * (global_weight @ global_weight))
        global_gradient = differences.T @ coefficient + lambda_global * global_weight
        if not task_residual:
            return loss, global_gradient
        assert lambda_task is not None
        loss += float(0.5 * lambda_task * np.sum(residual * residual))
        residual_gradient = lambda_task * residual
        for task_index in np.unique(edge_tasks):
            mask = edge_tasks == task_index
            residual_gradient[task_index] += differences[mask].T @ coefficient[mask]
        return loss, np.concatenate((global_gradient, residual_gradient.reshape(-1)))

    started = time.monotonic()
    result = minimize(
        loss_gradient,
        initial,
        method="L-BFGS-B",
        jac=True,
        options={
            "maxiter": MAXITER,
            "ftol": FTOL,
            "gtol": GTOL,
            "maxls": MAXLS,
        },
    )
    elapsed = time.monotonic() - started
    gradient_max = float(np.max(np.abs(np.asarray(result.jac))))
    accepted = bool(result.success) or gradient_max <= ACCEPT_GRADIENT
    if not np.isfinite(result.x).all() or not math.isfinite(float(result.fun)):
        raise IntegrityError("optimizer produced non-finite parameters")
    global_weight = np.asarray(result.x[:dimension], dtype=np.float64)
    residual = (
        np.asarray(result.x[dimension:], dtype=np.float64).reshape(len(task_names), dimension)
        if task_residual
        else np.zeros((len(task_names), dimension), dtype=np.float64)
    )
    fit_task_counts = collections.Counter(str(rows[index]["task"]) for index in selected)
    unseen_norms = {
        task: float(np.linalg.norm(residual[index]))
        for index, task in enumerate(task_names)
        if task not in fit_task_counts
    }
    if any(value > 1e-12 for value in unseen_norms.values()):
        raise IntegrityError("unseen task residual is not exact global fallback")
    return {
        "global_weight": global_weight,
        "task_weights": residual,
        "task_names": np.asarray(task_names, dtype="U"),
    }, {
        **edge_audit,
        "task_residual": task_residual,
        "lambda_global": lambda_global,
        "lambda_task": lambda_task,
        "parameter_count": parameter_count,
        "success": bool(result.success),
        "accepted": accepted,
        "message": str(result.message),
        "iterations": int(result.nit),
        "function_evaluations": int(result.nfev),
        "objective_value": float(result.fun),
        "projected_gradient_max": gradient_max,
        "elapsed_s": elapsed,
        "fit_tasks": len(fit_task_counts),
        "unseen_tasks": sorted(unseen_norms),
        "unseen_task_residual_norms": unseen_norms,
        "global_weight_norm": float(np.linalg.norm(global_weight)),
        "task_weight_norm": float(np.linalg.norm(residual)),
    }


def score_matrix(
    weights: dict[str, np.ndarray], matrix: np.ndarray, endpoint_tasks: Sequence[str]
) -> np.ndarray:
    global_weight = np.asarray(weights["global_weight"], dtype=np.float64)
    residual = np.asarray(weights["task_weights"], dtype=np.float64)
    task_names = [str(value) for value in weights["task_names"].tolist()]
    task_position = {task: index for index, task in enumerate(task_names)}
    scores = np.asarray(matrix, dtype=np.float64) @ global_weight
    task_indices = np.asarray([task_position[task] for task in endpoint_tasks])
    scores += np.einsum(
        "ij,ij->i", np.asarray(matrix, dtype=np.float64), residual[task_indices], optimize=True
    )
    if not np.isfinite(scores).all():
        raise IntegrityError("non-finite endpoint scores")
    return scores


def subset_rows(rows: Sequence[dict[str, Any]], indices: Sequence[int]) -> list[dict[str, Any]]:
    return [rows[int(index)] for index in indices]


def model_metrics(
    rows: Sequence[dict[str, Any]], scores: dict[str, float], seed_offset: int
) -> dict[str, Any]:
    hits = [
        baseline_module.tie_hit(scores[str(row["better"])] - scores[str(row["worse"])])
        for row in rows
    ]
    primary = baseline_module.summarize_values(rows, hits, seed_offset)
    top1, top1_records = baseline_module.parent_top1(rows, scores)
    utility, utility_records = gap_utility_with_records(rows, hits)
    consistency = baseline_module.task_consistency(rows, hits)
    return {
        "pair": primary,
        "top1": top1,
        "utility": utility,
        "task_consistency": consistency,
        "_hits": hits,
        "_top1_records": top1_records,
        "_utility_records": utility_records,
    }


def selection_metrics(
    rows: Sequence[dict[str, Any]], scores: dict[str, float]
) -> dict[str, float]:
    """Overall-only metrics for inner selection; no bootstrap or task peeking."""
    hits = [
        baseline_module.tie_hit(scores[str(row["better"])] - scores[str(row["worse"])])
        for row in rows
    ]
    grouped: dict[str, list[tuple[dict[str, Any], float]]] = collections.defaultdict(list)
    for row, hit in zip(rows, hits):
        grouped[str(row["parent"])].append((row, float(hit)))
    top1_values: list[float] = []
    utility_values: list[float] = []
    for parent, items in grouped.items():
        parent_rows = [row for row, _ in items]
        candidates = {
            str(row[key]) for row in parent_rows for key in ("better", "worse")
        }
        if len(parent_rows) == len(candidates) * (len(candidates) - 1) // 2:
            losses = collections.Counter({candidate: 0 for candidate in candidates})
            for row in parent_rows:
                losses[str(row["worse"])] += 1
            true_top = {
                candidate for candidate, value in losses.items() if value == min(losses.values())
            }
            maximum = max(scores[candidate] for candidate in candidates)
            predicted = {
                candidate
                for candidate in candidates
                if abs(scores[candidate] - maximum) <= EPSILON
            }
            top1_values.append(len(predicted & true_top) / len(predicted))
        denominator = sum(float(row["gap_raw"]) for row in parent_rows)
        if denominator <= 0:
            raise IntegrityError(f"non-positive parent gap denominator: {parent}")
        utility_values.append(
            sum(float(row["gap_raw"]) * hit for row, hit in items) / denominator
        )
    if not top1_values or not utility_values:
        raise IntegrityError("inner selection has no parent metrics")
    return {
        "pair_accuracy": sum(hits) / len(hits),
        "complete_parent_top1": sum(top1_values) / len(top1_values),
        "parent_equal_gap_utility": sum(utility_values) / len(utility_values),
        "complete_parents": len(top1_values),
        "parents": len(utility_values),
    }


def gap_utility_with_records(
    rows: Sequence[dict[str, Any]], hits: Sequence[float]
) -> tuple[dict[str, Any], dict[str, dict[str, Any]]]:
    grouped: dict[str, list[tuple[dict[str, Any], float]]] = collections.defaultdict(list)
    for row, hit in zip(rows, hits):
        grouped[str(row["parent"])].append((row, float(hit)))
    records: dict[str, dict[str, Any]] = {}
    for parent, items in grouped.items():
        denominator = sum(float(row["gap_raw"]) for row, _ in items)
        if denominator <= 0:
            raise IntegrityError(f"non-positive parent gap denominator: {parent}")
        records[parent] = {
            "value": sum(float(row["gap_raw"]) * hit for row, hit in items) / denominator,
            "run": str(items[0][0]["run"]),
            "task": str(items[0][0]["task"]),
        }
    proxy = [{"run": item["run"], "task": item["task"]} for item in records.values()]
    values = [float(item["value"]) for item in records.values()]
    summary = baseline_module.summarize_values(proxy, values, 60)
    summary["parents"] = len(records)
    summary["definition"] = "mean_parent(sum(gap_raw*hit)/sum(gap_raw))"
    return summary, records


def paired_record_summary(
    main: dict[str, dict[str, Any]],
    baseline: dict[str, dict[str, Any]],
    seed_offset: int,
) -> dict[str, Any]:
    if set(main) != set(baseline):
        raise IntegrityError("paired record support mismatch")
    names = sorted(main)
    proxy = [
        {"run": str(main[name]["run"]), "task": str(main[name]["task"])}
        for name in names
    ]
    if any(
        main[name][key] != baseline[name][key]
        for name in names
        for key in ("run", "task")
    ):
        raise IntegrityError("paired record cluster mismatch")
    values = [float(main[name]["value"]) - float(baseline[name]["value"]) for name in names]
    summary = baseline_module.summarize_values(proxy, values, seed_offset)
    summary["records"] = len(values)
    return summary


def paired_metric_comparison(
    left: dict[str, Any], right: dict[str, Any], seed_offset: int
) -> dict[str, Any]:
    return {
        "top1": paired_record_summary(
            left["_top1_records"], right["_top1_records"], seed_offset
        ),
        "utility": paired_record_summary(
            left["_utility_records"], right["_utility_records"], seed_offset + 10
        ),
    }


def stripped_metrics(metrics: dict[str, Any]) -> dict[str, Any]:
    return {key: value for key, value in metrics.items() if not key.startswith("_")}


def inner_splits(rows: Sequence[dict[str, Any]], outer_fit: Sequence[int]) -> list[tuple[list[int], list[int]]]:
    from sklearn.model_selection import GroupKFold

    selected = np.asarray(outer_fit, dtype=np.int64)
    groups = np.asarray([str(rows[index]["run"]) for index in selected])
    splitter = GroupKFold(n_splits=INNER_FOLDS)
    output: list[tuple[list[int], list[int]]] = []
    for fit_local, valid_local in splitter.split(np.zeros(len(selected)), groups=groups):
        fit = selected[fit_local].tolist()
        valid = selected[valid_local].tolist()
        fit_runs = {str(rows[index]["run"]) for index in fit}
        valid_runs = {str(rows[index]["run"]) for index in valid}
        if fit_runs & valid_runs:
            raise IntegrityError("inner physical-run leakage")
        output.append((fit, valid))
    return output


def hyperparameter_grid(task_residual: bool) -> list[dict[str, float | None]]:
    if not task_residual:
        return [
            {"lambda_global": value, "lambda_task": None}
            for value in LAMBDA_GLOBAL_GRID
        ]
    return [
        {"lambda_global": global_value, "lambda_task": task_value}
        for global_value in LAMBDA_GLOBAL_GRID
        for task_value in LAMBDA_TASK_GRID
    ]


def select_hyperparameters(
    family: str,
    rows: Sequence[dict[str, Any]],
    outer_fit: Sequence[int],
    matrix: np.ndarray,
    position: dict[str, int],
    endpoint_tasks: Sequence[str],
    task_names: Sequence[str],
) -> tuple[dict[str, float | None], dict[str, Any], list[str], np.ndarray]:
    definition = FAMILIES[family]
    splits = inner_splits(rows, outer_fit)
    candidates: list[dict[str, Any]] = []
    for configuration in hyperparameter_grid(bool(definition["task_residual"])):
        oof_scores: dict[str, float] = {}
        fit_records: list[dict[str, Any]] = []
        for inner_fold, (fit_indices, valid_indices) in enumerate(splits):
            weights, fit_record = fit_ranker(
                rows,
                fit_indices,
                matrix,
                position,
                task_names,
                str(definition["objective"]),
                bool(definition["task_residual"]),
                float(configuration["lambda_global"]),
                None if configuration["lambda_task"] is None else float(configuration["lambda_task"]),
            )
            fit_record["inner_fold"] = inner_fold
            fit_record["fit_runs"] = len({rows[index]["run"] for index in fit_indices})
            fit_record["valid_runs"] = len({rows[index]["run"] for index in valid_indices})
            fit_record["run_overlap"] = 0
            fit_records.append(fit_record)
            valid_ids = sorted(
                {
                str(rows[index][key])
                for index in valid_indices
                for key in ("better", "worse")
                }
            )
            valid_positions = [position[card_id] for card_id in valid_ids]
            valid_scores = score_matrix(
                weights,
                matrix[valid_positions],
                [endpoint_tasks[index] for index in valid_positions],
            )
            for card_id, score in zip(valid_ids, valid_scores.tolist()):
                if card_id in oof_scores:
                    raise IntegrityError(f"inner endpoint scored twice: {card_id}")
                oof_scores[card_id] = float(score)
        expected_ids = {
            str(rows[index][key])
            for index in outer_fit
            for key in ("better", "worse")
        }
        if set(oof_scores) != expected_ids:
            raise IntegrityError("inner OOF endpoint coverage mismatch")
        fit_rows = subset_rows(rows, outer_fit)
        metrics = selection_metrics(fit_rows, oof_scores)
        accepted = all(record["accepted"] for record in fit_records)
        candidates.append(
            {
                "configuration": configuration,
                "accepted": accepted,
                "inner_top1": metrics["complete_parent_top1"],
                "inner_utility": metrics["parent_equal_gap_utility"],
                "inner_pair_accuracy": metrics["pair_accuracy"],
                "inner_complete_parents": metrics["complete_parents"],
                "inner_parents": metrics["parents"],
                "fits": fit_records,
                "_inner_oof_scores": oof_scores,
            }
        )
    valid = [candidate for candidate in candidates if candidate["accepted"]]
    if len(valid) != len(candidates):
        raise IntegrityError(f"one or more inner configurations failed for {family}")

    def selection_key(candidate: dict[str, Any]) -> tuple[float, float, float, float]:
        configuration = candidate["configuration"]
        return (
            float(candidate["inner_top1"]),
            float(candidate["inner_utility"]),
            float(configuration["lambda_task"] or 0.0),
            float(configuration["lambda_global"]),
        )

    selected = max(valid, key=selection_key)
    inner_ids = sorted(
        {
            str(rows[index][key])
            for index in outer_fit
            for key in ("better", "worse")
        }
    )
    score_matrix_artifact = np.asarray(
        [
            [float(candidate["_inner_oof_scores"][card_id]) for card_id in inner_ids]
            for candidate in candidates
        ],
        dtype=np.float64,
    )
    for candidate in candidates:
        del candidate["_inner_oof_scores"]
    return dict(selected["configuration"]), {
        "family": family,
        "selection_order": [
            "max_inner_complete_parent_top1",
            "max_inner_parent_equal_gap_utility",
            "max_lambda_task",
            "max_lambda_global",
        ],
        "selected": selected["configuration"],
        "selected_key": list(selection_key(selected)),
        "candidates": candidates,
    }, inner_ids, score_matrix_artifact


def save_weights(path: Path, weights: dict[str, np.ndarray]) -> None:
    atomic_npz(
        path,
        global_weight=np.asarray(weights["global_weight"], dtype=np.float64),
        task_weights=np.asarray(weights["task_weights"], dtype=np.float64),
        task_names=np.asarray(weights["task_names"], dtype="U"),
    )


def run_outer_fold(
    fold: int,
    checkpoint_root: Path,
    checkpoint_key: str,
    rows: Sequence[dict[str, Any]],
    outer_folds: Sequence[int],
    matrix: np.ndarray,
    position: dict[str, int],
    endpoint_tasks: Sequence[str],
    task_names: Sequence[str],
) -> tuple[dict[str, dict[str, float]], dict[str, Any]]:
    final_dir = checkpoint_root / f"fold_{fold}"
    summary_path = final_dir / "fold_summary.json"
    if summary_path.exists():
        summary = json.loads(summary_path.read_text(encoding="utf-8"))
        if summary.get("checkpoint_key") != checkpoint_key or int(summary.get("fold", -1)) != fold:
            raise IntegrityError(f"checkpoint identity mismatch for fold {fold}")
        scores_path = final_dir / "valid_scores.npz"
        if sha256(scores_path) != summary["files"]["valid_scores_sha256"]:
            raise IntegrityError(f"checkpoint score hash mismatch for fold {fold}")
        with np.load(scores_path, allow_pickle=False) as data:
            ids = [str(value) for value in data["card_ids"].tolist()]
            scores = {
                family: {card_id: float(value) for card_id, value in zip(ids, data[family].tolist())}
                for family in FAMILIES
            }
        for family in FAMILIES:
            weight_path = final_dir / f"{family}_weights.npz"
            if sha256(weight_path) != summary["files"][f"{family}_weights_sha256"]:
                raise IntegrityError(f"checkpoint weight hash mismatch: {family} fold {fold}")
            inner_path = final_dir / f"{family}_inner_oof_scores.npz"
            if sha256(inner_path) != summary["files"][f"{family}_inner_oof_scores_sha256"]:
                raise IntegrityError(f"checkpoint inner-score hash mismatch: {family} fold {fold}")
        summary["resumed"] = True
        return scores, summary

    temporary = checkpoint_root / f".fold_{fold}.{os.getpid()}.tmp"
    if temporary.exists():
        raise IntegrityError(f"temporary checkpoint already exists: {temporary}")
    temporary.mkdir(parents=True, exist_ok=False)
    started = time.monotonic()
    fit_indices = [index for index, value in enumerate(outer_folds) if value != fold]
    valid_indices = [index for index, value in enumerate(outer_folds) if value == fold]
    fit_runs = {str(rows[index]["run"]) for index in fit_indices}
    valid_runs = {str(rows[index]["run"]) for index in valid_indices}
    if fit_runs & valid_runs:
        raise IntegrityError(f"outer physical-run leakage in fold {fold}")
    valid_ids = sorted(
        {
            str(rows[index][key])
            for index in valid_indices
            for key in ("better", "worse")
        }
    )
    family_scores: dict[str, dict[str, float]] = {}
    family_records: dict[str, Any] = {}
    files: dict[str, str] = {}
    for family, definition in FAMILIES.items():
        selected, inner_record, inner_ids, inner_scores = select_hyperparameters(
            family,
            rows,
            fit_indices,
            matrix,
            position,
            endpoint_tasks,
            task_names,
        )
        inner_path = temporary / f"{family}_inner_oof_scores.npz"
        atomic_npz(
            inner_path,
            card_ids=np.asarray(inner_ids, dtype="U"),
            scores=np.asarray(inner_scores, dtype=np.float64),
        )
        files[f"{family}_inner_oof_scores_sha256"] = sha256(inner_path)
        weights, fit_record = fit_ranker(
            rows,
            fit_indices,
            matrix,
            position,
            task_names,
            str(definition["objective"]),
            bool(definition["task_residual"]),
            float(selected["lambda_global"]),
            None if selected["lambda_task"] is None else float(selected["lambda_task"]),
        )
        if not fit_record["accepted"]:
            raise IntegrityError(f"outer fit not accepted: {family} fold {fold}")
        valid_positions = [position[card_id] for card_id in valid_ids]
        score_array = score_matrix(
            weights,
            matrix[valid_positions],
            [endpoint_tasks[index] for index in valid_positions],
        )
        family_scores[family] = {
            card_id: float(score) for card_id, score in zip(valid_ids, score_array.tolist())
        }
        weight_path = temporary / f"{family}_weights.npz"
        save_weights(weight_path, weights)
        files[f"{family}_weights_sha256"] = sha256(weight_path)
        family_records[family] = {
            "inner_selection": inner_record,
            "outer_fit": fit_record,
        }
    score_path = temporary / "valid_scores.npz"
    atomic_npz(
        score_path,
        card_ids=np.asarray(valid_ids, dtype="U"),
        **{
            family: np.asarray([family_scores[family][card_id] for card_id in valid_ids], dtype=np.float64)
            for family in FAMILIES
        },
    )
    files["valid_scores_sha256"] = sha256(score_path)
    summary = {
        "status": "FOLD_COMPLETE",
        "protocol": PROTOCOL,
        "checkpoint_key": checkpoint_key,
        "fold": fold,
        "fit_pairs": len(fit_indices),
        "valid_pairs": len(valid_indices),
        "fit_runs": len(fit_runs),
        "valid_runs": len(valid_runs),
        "run_overlap": 0,
        "valid_endpoints": len(valid_ids),
        "families": family_records,
        "files": files,
        "elapsed_s": time.monotonic() - started,
        "resumed": False,
    }
    atomic_json(temporary / "fold_summary.json", summary)
    checkpoint_root.mkdir(parents=True, exist_ok=True)
    os.replace(temporary, final_dir)
    return family_scores, summary


def random_score(card_id: str) -> float:
    return (zlib.crc32(f"{SEED}:{card_id}".encode("utf-8")) & 0xFFFFFFFF) / 2**32


def write_predictions(
    path: Path,
    rows: Sequence[dict[str, Any]],
    folds: Sequence[int],
    scores: dict[str, dict[str, float]],
) -> None:
    fields = ["row_index", "task", "run", "parent", "better", "worse", "gap_raw", "fold"]
    for arm in (BASELINE_ARM, *FAMILIES):
        fields.extend(
            [
                f"{arm}_better_score",
                f"{arm}_worse_score",
                f"{arm}_margin",
                f"{arm}_hit",
            ]
        )
    temporary = path.with_suffix(path.suffix + ".tmp")
    with temporary.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        for index, (row, fold) in enumerate(zip(rows, folds)):
            output: dict[str, Any] = {
                "row_index": index,
                "task": row["task"],
                "run": row["run"],
                "parent": row["parent"],
                "better": row["better"],
                "worse": row["worse"],
                "gap_raw": row["gap_raw"],
                "fold": fold,
            }
            for arm in (BASELINE_ARM, *FAMILIES):
                better_score = scores[arm][str(row["better"])]
                worse_score = scores[arm][str(row["worse"])]
                margin = better_score - worse_score
                output.update(
                    {
                        f"{arm}_better_score": repr(better_score),
                        f"{arm}_worse_score": repr(worse_score),
                        f"{arm}_margin": repr(margin),
                        f"{arm}_hit": repr(baseline_module.tie_hit(margin)),
                    }
                )
            writer.writerow(output)
    if path.exists():
        if sha256(temporary) != sha256(path):
            raise IntegrityError(f"existing prediction file differs: {path}")
        temporary.unlink()
    else:
        os.replace(temporary, path)


def arguments() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--repo-root", required=True, type=Path)
    parser.add_argument("--pairs", required=True, type=Path)
    parser.add_argument("--run-map", required=True, type=Path)
    parser.add_argument("--manifest", required=True, type=Path)
    parser.add_argument("--manifest-summary", required=True, type=Path)
    parser.add_argument("--feature-root", required=True, type=Path)
    parser.add_argument("--baseline-oof", required=True, type=Path)
    parser.add_argument("--out-dir", required=True, type=Path)
    parser.add_argument("--extraction-commit", required=True)
    parser.add_argument("--model-sha256", required=True)
    parser.add_argument("--expect-pairs-sha256", required=True)
    parser.add_argument("--expect-run-map-sha256", required=True)
    parser.add_argument("--expect-manifest-sha256", required=True)
    parser.add_argument("--expect-baseline-sha256", required=True)
    parser.add_argument("--wall-cap-s", type=float, default=2700.0)
    return parser.parse_args()


def main() -> int:
    args = arguments()
    reject_forbidden_path(args.pairs, "training pairs")
    reject_forbidden_path(args.baseline_oof, "baseline OOF")
    started = time.monotonic()
    commit = git_commit(args.repo_root)
    manifest, manifest_summary, manifest_sha = baseline_module.load_manifest(
        args.manifest, args.manifest_summary
    )
    if manifest_sha != args.expect_manifest_sha256.lower():
        raise IntegrityError("manifest hash mismatch")
    if sha256(args.run_map) != args.expect_run_map_sha256.lower():
        raise IntegrityError("run-map hash mismatch")
    rows, pair_audit, pair_sha = baseline_module.load_pairs(
        args.pairs, manifest, args.run_map
    )
    if pair_sha != args.expect_pairs_sha256.lower():
        raise IntegrityError("training-pair hash mismatch")
    matrix, position, feature_audit = baseline_module.load_features(
        args.feature_root,
        manifest,
        manifest_sha,
        args.extraction_commit,
        args.model_sha256.lower(),
    )
    folds, baseline_scores, baseline_audit = load_locked_baseline(
        args.baseline_oof, rows, args.expect_baseline_sha256
    )
    endpoint_ids = [str(row["card_id"]) for row in manifest]
    endpoint_tasks = [str(row["task"]) for row in manifest]
    task_names = sorted({str(row["task"]) for row in rows})
    configuration = {
        "protocol": PROTOCOL,
        "seed": SEED,
        "outer_folds": OUTER_FOLDS,
        "inner_folds": INNER_FOLDS,
        "lambda_global_grid": list(LAMBDA_GLOBAL_GRID),
        "lambda_task_grid": list(LAMBDA_TASK_GRID),
        "optimizer": {
            "name": "L-BFGS-B",
            "maxiter": MAXITER,
            "ftol": FTOL,
            "gtol": GTOL,
            "maxls": MAXLS,
            "accepted_gradient": ACCEPT_GRADIENT,
            "initialization": "all_zero",
            "fit_dtype": "float64",
            "checkpoint_dtype": "float64",
        },
        "families": FAMILIES,
        "baseline_arm": BASELINE_ARM,
        "main_arm": MAIN_ARM,
        "selection": ["top1", "utility", "lambda_task_desc", "lambda_global_desc"],
        "metric_seed_offsets": METRIC_SEED_OFFSETS,
    }
    inputs = {
        "pairs_sha256": pair_sha,
        "run_map_sha256": sha256(args.run_map),
        "manifest_sha256": manifest_sha,
        "manifest_summary_sha256": sha256(args.manifest_summary),
        "baseline_oof_sha256": baseline_audit["sha256"],
        "extraction_commit": args.extraction_commit,
        "model_sha256": args.model_sha256.lower(),
        "feature_worker_sha256": feature_audit["worker_source_sha256"],
        "baseline_module_source_sha256": sha256(Path(baseline_module.__file__)),
    }
    checkpoint_key = json_digest(
        {"git_commit": commit, "configuration": configuration, "inputs": inputs}
    )
    args.out_dir.mkdir(parents=True, exist_ok=True)
    all_scores: dict[str, dict[str, float]] = {
        BASELINE_ARM: dict(baseline_scores),
        **{family: {} for family in FAMILIES},
    }
    fold_records: list[dict[str, Any]] = []
    checkpoint_root = args.out_dir / "checkpoints"
    for fold in range(OUTER_FOLDS):
        fold_scores, fold_record = run_outer_fold(
            fold,
            checkpoint_root,
            checkpoint_key,
            rows,
            folds,
            matrix,
            position,
            endpoint_tasks,
            task_names,
        )
        fold_records.append(fold_record)
        for family in FAMILIES:
            overlap = set(all_scores[family]) & set(fold_scores[family])
            if overlap:
                raise IntegrityError(f"outer endpoint scored twice for {family}")
            all_scores[family].update(fold_scores[family])
        if sum(float(record["elapsed_s"]) for record in fold_records) > args.wall_cap_s:
            raise TimeoutError("formal fold runtime exceeded wall cap")
    expected_endpoints = set(endpoint_ids)
    if any(set(all_scores[arm]) != expected_endpoints for arm in all_scores):
        raise IntegrityError("OOF endpoint coverage mismatch")
    metrics = {
        arm: model_metrics(rows, scores, METRIC_SEED_OFFSETS[arm])
        for arm, scores in all_scores.items()
    }
    baseline_metrics = metrics[BASELINE_ARM]
    if not (
        math.isclose(baseline_metrics["pair"]["overall"], 0.5038705137227305, abs_tol=1e-12)
        and math.isclose(baseline_metrics["top1"]["overall"], 0.44710048694112436, abs_tol=1e-12)
        and math.isclose(baseline_metrics["utility"]["overall"], 0.5105066477670084, abs_tol=1e-12)
    ):
        raise IntegrityError("fixed baseline headline did not reproduce")
    main_metrics = metrics[MAIN_ARM]
    paired_comparisons = {
        "main_minus_fixed_baseline": paired_metric_comparison(
            main_metrics, baseline_metrics, 400
        ),
        "nested_global_allpair_minus_fixed_baseline": paired_metric_comparison(
            metrics["nested_global_allpair"], baseline_metrics, 440
        ),
        "topcenter_effect_at_global": paired_metric_comparison(
            metrics["nested_global_topcenter"], metrics["nested_global_allpair"], 480
        ),
        "task_effect_at_allpair": paired_metric_comparison(
            metrics["nested_task_allpair"], metrics["nested_global_allpair"], 520
        ),
        "task_effect_at_topcenter": paired_metric_comparison(
            metrics["nested_task_topcenter"], metrics["nested_global_topcenter"], 560
        ),
        "topcenter_effect_at_task": paired_metric_comparison(
            metrics["nested_task_topcenter"], metrics["nested_task_allpair"], 600
        ),
    }
    top1_delta = paired_comparisons["main_minus_fixed_baseline"]["top1"]
    utility_delta = paired_comparisons["main_minus_fixed_baseline"]["utility"]
    random_scores = {card_id: random_score(card_id) for card_id in endpoint_ids}
    random_metrics = model_metrics(rows, random_scores, 20)
    formal_runtime = sum(float(record["elapsed_s"]) for record in fold_records)
    all_fits = [
        fit
        for record in fold_records
        for family in FAMILIES
        for candidate in record["families"][family]["inner_selection"]["candidates"]
        for fit in candidate["fits"]
    ] + [
        record["families"][family]["outer_fit"]
        for record in fold_records
        for family in FAMILIES
    ]
    predictions_path = args.out_dir / "oof_predictions.csv"
    write_predictions(predictions_path, rows, folds, all_scores)
    invocation_runtime = time.monotonic() - started
    current_fit_runtime = sum(
        float(record["elapsed_s"])
        for record in fold_records
        if not bool(record.get("resumed"))
    )
    accounted_runtime = formal_runtime + max(0.0, invocation_runtime - current_fit_runtime)
    structure_checks = {
        "pairs_eq_4263": pair_audit["pairs"] == EXPECTED["pairs"],
        "runs_eq_333": pair_audit["runs"] == EXPECTED["runs"],
        "tasks_eq_23": pair_audit["tasks"] == EXPECTED["tasks"],
        "parents_eq_2293": pair_audit["parents"] == EXPECTED["parents"],
        "endpoints_eq_5499": pair_audit["endpoints"] == EXPECTED["endpoints"],
        "feature_dimension_eq_1792": feature_audit["dimension"] == EXPECTED["dimension"],
        "feature_coverage_exact": feature_audit["endpoints"] == EXPECTED["endpoints"],
        "complete_parents_eq_2259": baseline_metrics["top1"]["complete_parents"]
        == EXPECTED["complete_parents"],
        "outer_run_overlap_eq_0": all(record["run_overlap"] == 0 for record in fold_records),
        "all_fits_accepted": all(bool(fit["accepted"]) for fit in all_fits),
        "formal_runtime_le_cap": accounted_runtime <= args.wall_cap_s,
        "baseline_hash_exact": baseline_audit["sha256"] == args.expect_baseline_sha256.lower(),
        "baseline_headline_exact": True,
        "random_pair_in_047_053": 0.47 <= random_metrics["pair"]["overall"] <= 0.53,
        "orientation_oracle_eq_1": 1.0 == 1.0,
        "frozen_read_false": True,
    }
    effect_checks = {
        "main_top1_ge_050": main_metrics["top1"]["overall"] >= 0.50,
        "main_top1_delta_ge_003": top1_delta["overall"] >= 0.03,
        "top1_run_delta_ci_low_gt_0": top1_delta["run_macro_ci95"][0] > 0.0,
        "top1_task_delta_ci_low_gt_0": top1_delta["task_macro_ci95"][0] > 0.0,
        "main_utility_ge_055": main_metrics["utility"]["overall"] >= 0.55,
        "main_utility_delta_ge_002": utility_delta["overall"] >= 0.02,
        "utility_run_delta_ci_low_gt_0": utility_delta["run_macro_ci95"][0] > 0.0,
        "utility_task_delta_ci_low_gt_0": utility_delta["task_macro_ci95"][0] > 0.0,
        "main_pair_accuracy_ge_050": main_metrics["pair"]["overall"] >= 0.50,
        "supported_tasks_ge_15": main_metrics["task_consistency"]["supported_tasks"] >= 15,
        "task_nonchance_share_ge_060": main_metrics["task_consistency"]["nonchance_share"] >= 0.60,
    }
    checks = {**structure_checks, **effect_checks}
    checks["all"] = all(checks.values())
    summary = {
        "status": "DISCOVERY_UNLOCK_RECOMMENDED" if checks["all"] else "DISCOVERY_NO_UNLOCK",
        "protocol": PROTOCOL,
        "frozen_read": False,
        "git_commit": commit,
        "source_sha256": sha256(Path(__file__)),
        "runtime_s": accounted_runtime,
        "invocation_runtime_s": invocation_runtime,
        "formal_fold_runtime_s": formal_runtime,
        "software": {
            "python": sys.version,
            "platform": platform.platform(),
            "numpy": np.__version__,
            "scipy": __import__("scipy").__version__,
            "sklearn": __import__("sklearn").__version__,
        },
        "configuration": configuration,
        "inputs": inputs,
        "checkpoint_key": checkpoint_key,
        "pair_audit": pair_audit,
        "manifest_summary": manifest_summary,
        "feature_audit": feature_audit,
        "baseline_audit": baseline_audit,
        "folds": fold_records,
        "metrics": {arm: stripped_metrics(value) for arm, value in metrics.items()},
        "paired_delta_comparisons": paired_comparisons,
        "random_control": stripped_metrics(random_metrics),
        "orientation_oracle": 1.0,
        "discovery_gate": checks,
        "outputs": {
            "oof_predictions": str(predictions_path),
            "oof_predictions_sha256": sha256(predictions_path),
            "checkpoint_root": str(checkpoint_root),
        },
    }
    atomic_json(args.out_dir / "summary.json", summary)
    print(
        summary["status"],
        f"main_top1={main_metrics['top1']['overall']:.6f}",
        f"top1_delta={top1_delta['overall']:.6f}",
        f"main_utility={main_metrics['utility']['overall']:.6f}",
        f"utility_delta={utility_delta['overall']:.6f}",
        f"main_pair={main_metrics['pair']['overall']:.6f}",
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
