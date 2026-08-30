#!/usr/bin/env python3
"""Independent grounded-Laplacian verifier for FOREAGENT LOEO denoising."""

from __future__ import annotations

import argparse
from collections import defaultdict
import hashlib
import json
import math
from pathlib import Path
from typing import Any, Mapping

import numpy as np


MODELS = ("deepseek", "gpt")
MANIFEST_SHA256 = "3df2715b2d2e5f3cc6193c07c99eb682e042e8aa6cb724b046b2469b35773a4e"
MASTER_SHA256 = "480616317ddebb249084dbc8b36b4060fac4b77353fce16b436351eab9c235fe"
EXPECTED = {"sources": 156, "records": 110620, "tasks": 26, "pairs": 18381, "vertices": 894, "rank": 868}
SEED = 20260901
SIGN_TOL = 1e-12
BRIDGE_TOL = 1e-10


def ensure(condition: bool, message: str) -> None:
    if not condition:
        raise ValueError(message)


def file_sha(path: Path) -> str:
    value = hashlib.sha256()
    with path.open("rb") as handle:
        while True:
            block = handle.read(1 << 20)
            if not block:
                break
            value.update(block)
    return value.hexdigest()


def index_value(value: Any) -> int | None:
    if type(value) is int and value in (0, 1):
        return value
    if isinstance(value, str) and value in {"0", "1"}:
        return int(value)
    return None


def normalized_score(value: float) -> float | str:
    if math.isnan(value):
        return "nan"
    if value == math.inf:
        return "+inf"
    if value == -math.inf:
        return "-inf"
    if value == 0.0:
        return 0.0
    return value


def canonical_record(raw: Mapping[str, Any], source: Mapping[str, Any]) -> dict[str, Any]:
    ensure(raw.get("source_index") == source["index"], "source mismatch")
    ensure(raw.get("task") == source["task"], "task mismatch")
    ensure(raw.get("model_family") == source["model"], "model mismatch")
    ensure(raw.get("release_run") == source["run"], "run mismatch")
    paths = raw.get("solution_paths")
    scores = raw.get("scores")
    ensure(
        isinstance(paths, list)
        and len(paths) == 2
        and all(isinstance(path, str) and path for path in paths)
        and paths[0] != paths[1],
        "paths",
    )
    ensure(isinstance(scores, list) and len(scores) == 2, "scores")
    first, second = float(scores[0]), float(scores[1])
    lower = raw.get("is_lower_better")
    ensure(isinstance(lower, bool), "direction")
    pair = tuple(sorted((paths[0], paths[1])))
    finite = math.isfinite(first) and math.isfinite(second) and first != second
    winner: str | None = None
    if finite:
        if lower:
            winner = paths[0] if first < second else paths[1]
        else:
            winner = paths[0] if first > second else paths[1]
    truth_index = index_value(raw.get("groundtruth_best_index"))
    ensure(truth_index is not None, "truth index")
    if winner is not None:
        ensure(paths[truth_index] == winner, "truth score disagreement")
    prediction_index = index_value(raw.get("prediction_best_index"))
    predicted = paths[prediction_index] if prediction_index is not None else None

    def sign(path: str | None) -> float:
        if path is None:
            return 0.0
        return 1.0 if path == pair[1] else -1.0

    # This verifier deliberately uses the opposite canonical orientation from producer.
    return {
        "pair": pair,
        "finite": finite,
        "truth": sign(winner),
        "prediction": sign(predicted),
        "score_map": tuple(
            sorted(
                (
                    (paths[0], normalized_score(first)),
                    (paths[1], normalized_score(second)),
                )
            )
        ),
        "lower": lower,
    }


def load_support(manifest_path: Path, master_path: Path) -> tuple[dict[str, list[dict[str, Any]]], dict[str, Any]]:
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    raw_files = manifest.get("files")
    ensure(isinstance(raw_files, list), "manifest files")
    sources: list[dict[str, Any]] = []
    for position, raw in enumerate(raw_files):
        ensure(isinstance(raw, dict), "manifest source")
        model, task, run = raw.get("model_family"), raw.get("task"), raw.get("release_run")
        ensure(model in MODELS and isinstance(task, str) and task and run in (1, 2, 3), "source metadata")
        sources.append({"index": position, "model": model, "task": task, "run": run})

    rows_by_source: dict[int, dict[tuple[str, str], dict[str, Any]]] = defaultdict(dict)
    row_count = 0
    with master_path.open("r", encoding="utf-8") as handle:
        for row_count, line in enumerate(handle, start=1):
            raw = json.loads(line)
            ensure(isinstance(raw, dict), "row object")
            source_index = raw.get("source_index")
            ensure(type(source_index) is int and 0 <= source_index < len(sources), "source index")
            record = canonical_record(raw, sources[source_index])
            ensure(record["pair"] not in rows_by_source[source_index], "duplicate source pair")
            rows_by_source[source_index][record["pair"]] = record
    ensure(set(rows_by_source) == set(range(len(sources))), "source coverage")

    grouped: dict[tuple[str, str], list[int]] = defaultdict(list)
    tasks: set[str] = set()
    for source in sources:
        grouped[(source["model"], source["task"])].append(source["index"])
        tasks.add(source["task"])
    for key in grouped:
        grouped[key].sort(key=lambda idx: sources[idx]["run"])
        ensure(len(grouped[key]) == 3, "triplicate count")

    support: dict[str, list[dict[str, Any]]] = {}
    vertices: set[tuple[str, str]] = set()
    round_correct = {model: 0.0 for model in MODELS}
    pair_count = 0
    for task in sorted(tasks):
        grids: dict[str, set[tuple[str, str]]] = {}
        for model in MODELS:
            index_group = grouped[(model, task)]
            sets = [set(rows_by_source[idx]) for idx in index_group]
            if model == "deepseek":
                ensure(sets[0] == sets[1] == sets[2], "DeepSeek grid")
                grids[model] = sets[0]
            else:
                grids[model] = sets[0] & sets[1] & sets[2]
        task_rows: list[dict[str, Any]] = []
        for pair in sorted(grids["deepseek"] & grids["gpt"]):
            releases = {
                model: [rows_by_source[idx][pair] for idx in grouped[(model, task)]]
                for model in MODELS
            }
            reference = releases["deepseek"][0]
            for record in releases["deepseek"][1:] + releases["gpt"]:
                ensure(record["score_map"] == reference["score_map"], "score drift")
                ensure(record["lower"] == reference["lower"], "direction drift")
                ensure(record["finite"] == reference["finite"], "finite drift")
                ensure(record["truth"] == reference["truth"], "truth drift")
            if not reference["finite"]:
                continue
            item: dict[str, Any] = {"pair": pair, "truth": reference["truth"]}
            for model in MODELS:
                predictions = [record["prediction"] for record in releases[model]]
                item[model] = sum(predictions) / 3.0
                round_correct[model] += sum(value == reference["truth"] for value in predictions) / 3.0
            task_rows.append(item)
            vertices.add((task, pair[0]))
            vertices.add((task, pair[1]))
            pair_count += 1
        ensure(task_rows, "empty task")
        support[task] = task_rows

    ensure(file_sha(manifest_path) == MANIFEST_SHA256, "manifest hash")
    ensure(file_sha(master_path) == MASTER_SHA256, "master hash")
    ensure(len(sources) == EXPECTED["sources"] and row_count == EXPECTED["records"], "input size")
    ensure(len(support) == EXPECTED["tasks"] and pair_count == EXPECTED["pairs"], "support size")
    ensure(len(vertices) == EXPECTED["vertices"], "vertex size")
    return support, {
        "sources": len(sources),
        "records": row_count,
        "tasks": len(support),
        "pairs": pair_count,
        "vertices": len(vertices),
        "round_pair": {model: round_correct[model] / pair_count for model in MODELS},
    }


def grounded_projection(rows: list[Mapping[str, Any]], model: str) -> dict[str, float]:
    nodes = sorted({node for row in rows for node in row["pair"]})
    positions = {node: index for index, node in enumerate(nodes)}
    design = np.zeros((len(rows), len(nodes) - 1), dtype=np.float64)
    for edge, row in enumerate(rows):
        left, right = row["pair"]
        # Opposite orientation: right minus left. Last node is grounded.
        if positions[right] < len(nodes) - 1:
            design[edge, positions[right]] += 1.0
        if positions[left] < len(nodes) - 1:
            design[edge, positions[left]] -= 1.0
    rank = int(np.linalg.matrix_rank(design, tol=1e-9))
    ensure(rank == len(nodes) - 1, "disconnected task")
    gram_inverse = np.linalg.inv(design.T @ design)
    flow = np.asarray([row[model] for row in rows], dtype=np.float64)
    truth = np.asarray([row["truth"] for row in rows], dtype=np.float64)
    ensure(np.all(np.abs(flow) > SIGN_TOL), "raw abstention")
    fitted = design @ (gram_inverse @ (design.T @ flow))
    leverage = np.einsum("ij,jk,ik->i", design, gram_inverse, design)
    denominator = 1.0 - leverage
    candidate = np.full(flow.shape, np.nan)
    structural = denominator > BRIDGE_TOL
    candidate[structural] = (fitted[structural] - leverage[structural] * flow[structural]) / denominator[structural]
    evaluable = structural & (np.abs(candidate) > SIGN_TOL)
    raw_prediction = np.sign(flow)
    loeo_prediction = np.sign(candidate[evaluable])
    raw_correct = raw_prediction == truth
    hybrid_prediction = raw_prediction.copy()
    hybrid_prediction[evaluable] = loeo_prediction
    hybrid_correct = hybrid_prediction == truth
    return {
        "n": float(len(rows)),
        "vertices": float(len(nodes)),
        "rank": float(rank),
        "raw_correct": float(np.sum(raw_correct)),
        "hybrid_correct": float(np.sum(hybrid_correct)),
        "evaluable_n": float(np.sum(evaluable)),
        "raw_evaluable_correct": float(np.sum(raw_correct[evaluable])),
        "loeo_correct": float(np.sum(loeo_prediction == truth[evaluable])),
        "bridge_or_zero_n": float(len(rows) - np.sum(evaluable)),
        "leverage_sum": float(np.sum(leverage)),
        "residual_energy": float(np.sum((flow - fitted) ** 2)),
    }


def metrics(tasks: list[Mapping[str, float]]) -> dict[str, float]:
    raw_task = np.asarray([row["raw_correct"] / row["n"] for row in tasks])
    hybrid_task = np.asarray([row["hybrid_correct"] / row["n"] for row in tasks])
    loeo_task = np.asarray([row["loeo_correct"] / row["evaluable_n"] for row in tasks])
    raw_eval = np.asarray([row["raw_evaluable_correct"] / row["evaluable_n"] for row in tasks])
    total = sum(row["n"] for row in tasks)
    return {
        "raw_majority_pair_micro": sum(row["raw_correct"] for row in tasks) / total,
        "hybrid_pair_micro": sum(row["hybrid_correct"] for row in tasks) / total,
        "hybrid_minus_raw_pair_micro": sum(row["hybrid_correct"] - row["raw_correct"] for row in tasks) / total,
        "raw_majority_task_macro": float(np.mean(raw_task)),
        "hybrid_task_macro": float(np.mean(hybrid_task)),
        "hybrid_minus_raw_task_macro": float(np.mean(hybrid_task - raw_task)),
        "loeo_only_task_macro": float(np.mean(loeo_task)),
        "raw_on_loeo_support_task_macro": float(np.mean(raw_eval)),
        "loeo_minus_raw_on_loeo_support_task_macro": float(np.mean(loeo_task - raw_eval)),
        "loeo_coverage_pair_micro": sum(row["evaluable_n"] for row in tasks) / total,
        "loeo_coverage_task_macro": float(np.mean([row["evaluable_n"] / row["n"] for row in tasks])),
    }


def bootstrap(tasks: list[Mapping[str, float]], repetitions: int, seed: int) -> dict[str, list[float]]:
    names = (
        "hybrid_minus_raw_task_macro",
        "loeo_minus_raw_on_loeo_support_task_macro",
        "hybrid_minus_raw_pair_micro",
    )
    values = {name: np.empty(repetitions) for name in names}
    generator = np.random.default_rng(seed)
    for repetition in range(repetitions):
        sample = [tasks[index] for index in generator.integers(0, len(tasks), len(tasks))]
        point = metrics(sample)
        for name in names:
            values[name][repetition] = point[name]
    low, high = int(0.025 * repetitions), int(0.975 * repetitions) - 1
    return {
        name: [float(np.sort(array)[low]), float(np.sort(array)[high])]
        for name, array in values.items()
    }


def compare_numeric(expected: Any, actual: Any, path: str, differences: list[float]) -> None:
    if isinstance(expected, dict):
        ensure(isinstance(actual, dict), f"type {path}")
        for key, value in expected.items():
            ensure(key in actual, f"missing {path}.{key}")
            compare_numeric(value, actual[key], f"{path}.{key}", differences)
    elif isinstance(expected, list):
        ensure(isinstance(actual, list) and len(expected) == len(actual), f"list {path}")
        for index, value in enumerate(expected):
            compare_numeric(value, actual[index], f"{path}[{index}]", differences)
    elif isinstance(expected, float):
        ensure(isinstance(actual, (int, float)), f"numeric {path}")
        delta = abs(expected - float(actual))
        differences.append(delta)
        ensure(delta <= 2e-9 * max(1.0, abs(expected)), f"numeric drift {path}: {delta}")
    else:
        ensure(expected == actual, f"value drift {path}")


def verify(manifest: Path, master: Path, result_path: Path) -> dict[str, Any]:
    result = json.loads(result_path.read_text(encoding="utf-8"))
    repetitions = int(result["inference"]["bootstrap_repetitions"])
    support, population = load_support(manifest, master)
    ordered_tasks = sorted(support)
    task_stats: dict[str, list[dict[str, float]]] = {model: [] for model in MODELS}
    rank_total = 0
    for task in ordered_tasks:
        for model in MODELS:
            value = grounded_projection(support[task], model)
            ensure(abs(value["leverage_sum"] - value["rank"]) <= 5e-8, "Foster")
            task_stats[model].append(value)
        rank_total += int(task_stats["deepseek"][-1]["rank"])
    ensure(rank_total == EXPECTED["rank"], "rank total")

    expected_metrics: dict[str, Any] = {}
    for offset, model in enumerate(MODELS):
        task_delta = [row["hybrid_correct"] / row["n"] - row["raw_correct"] / row["n"] for row in task_stats[model]]
        expected_metrics[model] = {
            "point": metrics(task_stats[model]),
            "task_bootstrap_ci": bootstrap(task_stats[model], repetitions, SEED + offset),
            "hybrid_minus_raw_loto": {
                "positive": sum(float(np.mean(np.delete(task_delta, i))) > SIGN_TOL for i in range(len(task_delta))),
                "total": len(task_delta),
            },
            "label_free_diagnostics": {
                "residual_energy_sum": sum(row["residual_energy"] for row in task_stats[model]),
                "bridge_or_zero_edges": int(sum(row["bridge_or_zero_n"] for row in task_stats[model])),
            },
        }

    raw_delta = np.asarray(
        [
            left["raw_correct"] / left["n"] - right["raw_correct"] / right["n"]
            for left, right in zip(task_stats["deepseek"], task_stats["gpt"])
        ]
    )
    hybrid_delta = np.asarray(
        [
            left["hybrid_correct"] / left["n"]
            - right["hybrid_correct"] / right["n"]
            for left, right in zip(task_stats["deepseek"], task_stats["gpt"])
        ]
    )
    generator = np.random.default_rng(SEED + 2)
    sampled = generator.integers(
        0, len(ordered_tasks), size=(repetitions, len(ordered_tasks))
    )
    raw_boot = np.mean(raw_delta[sampled], axis=1)
    hybrid_boot = np.mean(hybrid_delta[sampled], axis=1)
    low, high = int(0.025 * repetitions), int(0.975 * repetitions) - 1

    def interval(values: np.ndarray) -> list[float]:
        ordered = np.sort(values)
        return [float(ordered[low]), float(ordered[high])]

    expected_paired = {
        "raw_task_macro_delta": float(np.mean(raw_delta)),
        "raw_task_macro_delta_ci": interval(raw_boot),
        "hybrid_task_macro_delta": float(np.mean(hybrid_delta)),
        "hybrid_task_macro_delta_ci": interval(hybrid_boot),
        "raw_loto_positive": int(
            sum(
                float(np.mean(np.delete(raw_delta, index))) > SIGN_TOL
                for index in range(len(raw_delta))
            )
        ),
        "hybrid_loto_positive": int(
            sum(
                float(np.mean(np.delete(hybrid_delta, index))) > SIGN_TOL
                for index in range(len(hybrid_delta))
            )
        ),
        "loto_total": len(raw_delta),
    }

    differences: list[float] = []
    compare_numeric(expected_metrics, result["metrics"], "metrics", differences)
    compare_numeric(
        expected_paired,
        result["paired_deepseek_minus_gpt"],
        "paired_deepseek_minus_gpt",
        differences,
    )
    compare_numeric(population["round_pair"], result["population"]["raw_round_pair_micro_reproduction"], "raw_round", differences)
    ensure(result["population"]["tasks"] == EXPECTED["tasks"], "result tasks")
    ensure(result["population"]["common_pairs"] == EXPECTED["pairs"], "result pairs")
    ensure(result["population"]["vertices"] == EXPECTED["vertices"], "result vertices")
    ensure(result["population"]["incidence_rank"] == EXPECTED["rank"], "result rank")
    ensure(result["method"]["target_edge_excluded"] is True, "LOEO marker")
    ensure(result["method"]["labels_used_for_projection"] is False, "label-free marker")
    ensure(result["inputs"]["prospective_sources_read"] is False, "prospective marker")
    coverage_pass = min(
        expected_metrics[model]["point"]["loeo_coverage_pair_micro"]
        for model in MODELS
    ) >= 0.90
    significant_gain = any(
        expected_metrics[model]["task_bootstrap_ci"][
            "hybrid_minus_raw_task_macro"
        ][0]
        > 0.0
        for model in MODELS
    )
    no_negative_point = all(
        expected_metrics[model]["point"]["hybrid_minus_raw_task_macro"] >= 0.0
        for model in MODELS
    )
    comparison_stable = expected_paired["hybrid_task_macro_delta_ci"][0] > 0.0
    expected_gates = {
        "minimum_pair_coverage": 0.90,
        "coverage_pass": coverage_pass,
        "at_least_one_task_macro_gain_ci_lower_gt_zero": significant_gain,
        "both_model_task_macro_gain_points_nonnegative": no_negative_point,
        "hybrid_model_comparison_ci_lower_gt_zero": comparison_stable,
    }
    compare_numeric(expected_gates, result["frozen_gates"], "frozen_gates", differences)
    if coverage_pass and significant_gain and no_negative_point:
        expected_classification = "SUPPORTING_GRAPH_CONSISTENCY_BASELINE_IMPROVES"
    elif comparison_stable:
        expected_classification = "NO_DENOISING_GAIN_MODEL_COMPARISON_REMAINS_STABLE"
    else:
        expected_classification = "NO_POSITIVE_GRAPH_CONSISTENCY_RESULT"
    ensure(result["classification"] == expected_classification, "classification")
    return {
        "protocol": "foreagent-loeo-graph-denoising-verification-v1",
        "status": "PASS",
        "producer_result_sha256": file_sha(result_path),
        "manifest_sha256": file_sha(manifest),
        "master_sha256": file_sha(master),
        "independent_method": "opposite orientation plus grounded reduced-Laplacian inverse",
        "checked_numeric_fields": len(differences),
        "maximum_absolute_numeric_difference": max(differences, default=0.0),
        "prospective_sources_read": False,
        "confidence_values_read": False,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument("--master", type=Path, required=True)
    parser.add_argument("--result", type=Path, required=True)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    value = verify(args.manifest, args.master, args.result)
    payload = json.dumps(value, sort_keys=True, indent=2) + "\n"
    if args.output:
        args.output.write_text(payload, encoding="utf-8")
    else:
        print(payload, end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
