#!/usr/bin/env python3
"""Leak-free graph-consistency baseline on FOREAGENT pairwise judgments.

The target edge is excluded analytically through the ordinary least-squares
leave-one-out identity.  Truth labels are used only after the label-free graph
projection has produced a prediction.
"""

from __future__ import annotations

import argparse
from collections import defaultdict
import hashlib
import json
import math
from pathlib import Path
from typing import Any, Iterable, Mapping

import numpy as np


MODELS = ("deepseek", "gpt")
MANIFEST_SHA256 = "3df2715b2d2e5f3cc6193c07c99eb682e042e8aa6cb724b046b2469b35773a4e"
MASTER_SHA256 = "480616317ddebb249084dbc8b36b4060fac4b77353fce16b436351eab9c235fe"
EXPECTED_SOURCE_FILES = 156
EXPECTED_SOURCE_RECORDS = 110620
EXPECTED_TASKS = 26
EXPECTED_COMMON_PAIRS = 18381
EXPECTED_VERTICES = 894
EXPECTED_COMPONENTS = 26
EXPECTED_RANK = 868
KNOWN_COMMON_ROUND_PAIR_MICRO = {
    "deepseek": 0.6152186134232811,
    "gpt": 0.5889596140942641,
}
BOOTSTRAP_REPETITIONS = 20000
BOOTSTRAP_SEED = 20260901
SIGN_TOLERANCE = 1e-12
BRIDGE_TOLERANCE = 1e-10


def require(condition: bool, message: str) -> None:
    if not condition:
        raise ValueError(message)


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def parse_index(value: Any) -> int | None:
    if isinstance(value, bool):
        return None
    if isinstance(value, int) and value in (0, 1):
        return value
    if isinstance(value, str) and value in ("0", "1"):
        return int(value)
    return None


def canonical_score(value: float) -> float | str:
    if math.isnan(value):
        return "nan"
    if value == math.inf:
        return "+inf"
    if value == -math.inf:
        return "-inf"
    if value == 0.0:
        return 0.0
    return value


def read_jsonl(path: Path) -> Iterable[dict[str, Any]]:
    with path.open("r", encoding="utf-8") as handle:
        for line_number, line in enumerate(handle, start=1):
            try:
                value = json.loads(line)
            except json.JSONDecodeError as error:
                raise ValueError(f"invalid JSONL line {line_number}") from error
            require(isinstance(value, dict), "master row is not an object")
            yield value


def parse_row(raw: Mapping[str, Any], source: Mapping[str, Any]) -> dict[str, Any]:
    require(raw.get("source_index") == source["source_index"], "source index drift")
    require(raw.get("task") == source["task"], "task drift")
    require(raw.get("model_family") == source["model_family"], "model drift")
    require(raw.get("release_run") == source["release_run"], "release drift")
    paths_raw = raw.get("solution_paths")
    scores_raw = raw.get("scores")
    require(
        isinstance(paths_raw, list)
        and len(paths_raw) == 2
        and all(isinstance(path, str) and path for path in paths_raw)
        and paths_raw[0] != paths_raw[1],
        "invalid paths",
    )
    require(isinstance(scores_raw, list) and len(scores_raw) == 2, "invalid scores")
    paths = (paths_raw[0], paths_raw[1])
    pair = tuple(sorted(paths))
    try:
        scores = (float(scores_raw[0]), float(scores_raw[1]))
    except (TypeError, ValueError) as error:
        raise ValueError("non-numeric scores") from error
    lower = raw.get("is_lower_better")
    require(isinstance(lower, bool), "invalid metric direction")
    finite_nontie = all(math.isfinite(value) for value in scores) and scores[0] != scores[1]
    true_path: str | None = None
    if finite_nontie:
        true_index = int(scores[1] < scores[0]) if lower else int(scores[1] > scores[0])
        true_path = paths[true_index]
    groundtruth_index = parse_index(raw.get("groundtruth_best_index"))
    require(groundtruth_index is not None, "invalid groundtruth index")
    if true_path is not None:
        require(paths[groundtruth_index] == true_path, "groundtruth/score mismatch")
    prediction_index = parse_index(raw.get("prediction_best_index"))
    prediction_path = paths[prediction_index] if prediction_index is not None else None

    def canonical_sign(path: str | None) -> float:
        if path is None:
            return 0.0
        return 1.0 if path == pair[0] else -1.0

    score_by_path = tuple(
        sorted(
            (
                (paths[0], canonical_score(scores[0])),
                (paths[1], canonical_score(scores[1])),
            )
        )
    )
    return {
        "pair": pair,
        "finite_nontie": finite_nontie,
        "true_sign": canonical_sign(true_path),
        "prediction_sign": canonical_sign(prediction_path),
        "score_by_path": score_by_path,
        "lower": lower,
    }


def load_common_support(
    manifest_path: Path,
    master_path: Path,
    *,
    production_checks: bool = True,
) -> tuple[dict[str, list[dict[str, Any]]], dict[str, Any]]:
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    require(isinstance(manifest, dict), "manifest object")
    files = manifest.get("files")
    require(isinstance(files, list) and files, "manifest files")
    sources: list[dict[str, Any]] = []
    for index, raw_source in enumerate(files):
        require(isinstance(raw_source, dict), "manifest source")
        source = dict(raw_source)
        source["source_index"] = index
        require(source.get("model_family") in MODELS, "unknown model")
        require(isinstance(source.get("task"), str) and source["task"], "invalid task")
        require(source.get("release_run") in (1, 2, 3), "invalid release")
        sources.append(source)

    by_source: dict[int, dict[tuple[str, str], dict[str, Any]]] = defaultdict(dict)
    records = 0
    for records, raw in enumerate(read_jsonl(master_path), start=1):
        index = raw.get("source_index")
        require(isinstance(index, int) and 0 <= index < len(sources), "invalid source index")
        parsed = parse_row(raw, sources[index])
        pair = parsed["pair"]
        require(pair not in by_source[index], "duplicate source pair")
        by_source[index][pair] = parsed
    require(set(by_source) == set(range(len(sources))), "missing source")

    indices: dict[tuple[str, str], list[int]] = defaultdict(list)
    tasks: set[str] = set()
    for source in sources:
        key = (source["model_family"], source["task"])
        indices[key].append(source["source_index"])
        tasks.add(source["task"])
    for key, values in indices.items():
        values.sort(key=lambda index: sources[index]["release_run"])
        require(len(values) == 3, f"triplicate source mismatch: {key}")

    output: dict[str, list[dict[str, Any]]] = {}
    raw_round_correct = {model: 0.0 for model in MODELS}
    common_count = 0
    vertices: set[tuple[str, str]] = set()
    for task in sorted(tasks):
        grids: dict[str, set[tuple[str, str]]] = {}
        for model in MODELS:
            source_indices = indices[(model, task)]
            key_sets = [set(by_source[index]) for index in source_indices]
            if model == "deepseek":
                require(key_sets[0] == key_sets[1] == key_sets[2], "DeepSeek grid drift")
                grids[model] = key_sets[0]
            else:
                grids[model] = set.intersection(*key_sets)
        task_rows: list[dict[str, Any]] = []
        for pair in sorted(grids["deepseek"] & grids["gpt"]):
            model_rows: dict[str, list[dict[str, Any]]] = {}
            for model in MODELS:
                model_rows[model] = [by_source[index][pair] for index in indices[(model, task)]]
            reference = model_rows["deepseek"][0]
            all_rows = model_rows["deepseek"] + model_rows["gpt"]
            for row in all_rows[1:]:
                require(row["score_by_path"] == reference["score_by_path"], "score drift")
                require(row["lower"] == reference["lower"], "direction drift")
                require(row["finite_nontie"] == reference["finite_nontie"], "truth status drift")
                require(row["true_sign"] == reference["true_sign"], "truth drift")
            if not reference["finite_nontie"]:
                continue
            record: dict[str, Any] = {
                "task": task,
                "pair": pair,
                "truth_sign": reference["true_sign"],
            }
            for model in MODELS:
                signs = [float(row["prediction_sign"]) for row in model_rows[model]]
                flow = sum(signs) / 3.0
                round_accuracy = sum(sign == reference["true_sign"] for sign in signs) / 3.0
                record[f"{model}_flow"] = flow
                record[f"{model}_round_accuracy"] = round_accuracy
                raw_round_correct[model] += round_accuracy
            task_rows.append(record)
            common_count += 1
            vertices.add((task, pair[0]))
            vertices.add((task, pair[1]))
        require(task_rows, "empty task support")
        output[task] = task_rows

    raw_pair_micro = {
        model: raw_round_correct[model] / common_count for model in MODELS
    }
    if production_checks:
        require(sha256(manifest_path) == MANIFEST_SHA256, "manifest SHA")
        require(sha256(master_path) == MASTER_SHA256, "master SHA")
        require(len(sources) == EXPECTED_SOURCE_FILES, "source file count")
        require(records == EXPECTED_SOURCE_RECORDS, "source record count")
        require(len(output) == EXPECTED_TASKS, "task count")
        require(common_count == EXPECTED_COMMON_PAIRS, "common pair count")
        require(len(vertices) == EXPECTED_VERTICES, "vertex count")
        for model in MODELS:
            require(
                abs(raw_pair_micro[model] - KNOWN_COMMON_ROUND_PAIR_MICRO[model]) <= 2e-15,
                "known raw reproduction",
            )
    return output, {
        "source_files": len(sources),
        "source_records": records,
        "tasks": len(output),
        "pairs": common_count,
        "vertices": len(vertices),
        "raw_round_pair_micro": raw_pair_micro,
    }


def incidence_matrix(rows: list[Mapping[str, Any]]) -> tuple[list[str], np.ndarray]:
    nodes = sorted({node for row in rows for node in row["pair"]})
    index = {node: offset for offset, node in enumerate(nodes)}
    matrix = np.zeros((len(rows), len(nodes)), dtype=np.float64)
    for row_index, row in enumerate(rows):
        left, right = row["pair"]
        matrix[row_index, index[left]] = 1.0
        matrix[row_index, index[right]] = -1.0
    return nodes, matrix


def loeo_projection(matrix: np.ndarray, flow: np.ndarray) -> dict[str, np.ndarray]:
    require(matrix.ndim == 2 and flow.shape == (matrix.shape[0],), "projection shape")
    laplacian = matrix.T @ matrix
    inverse = np.linalg.pinv(laplacian, rcond=1e-12, hermitian=True)
    fitted = matrix @ (inverse @ (matrix.T @ flow))
    leverage = np.einsum("ij,jk,ik->i", matrix, inverse, matrix)
    denominator = 1.0 - leverage
    evaluable = denominator > BRIDGE_TOLERANCE
    loeo = np.full(flow.shape, np.nan, dtype=np.float64)
    loeo[evaluable] = (
        fitted[evaluable] - leverage[evaluable] * flow[evaluable]
    ) / denominator[evaluable]
    evaluable &= np.abs(loeo) > SIGN_TOLERANCE
    return {
        "fitted": fitted,
        "leverage": leverage,
        "loeo": loeo,
        "evaluable": evaluable,
    }


def task_statistics(rows: list[Mapping[str, Any]], model: str) -> dict[str, float]:
    _, matrix = incidence_matrix(rows)
    flow = np.asarray([row[f"{model}_flow"] for row in rows], dtype=np.float64)
    truth = np.asarray([row["truth_sign"] for row in rows], dtype=np.float64)
    require(np.all(np.abs(flow) > SIGN_TOLERANCE), "raw majority abstention")
    projected = loeo_projection(matrix, flow)
    raw_prediction = np.sign(flow)
    evaluable = projected["evaluable"]
    loeo_prediction = np.sign(projected["loeo"][evaluable])
    raw_correct = raw_prediction == truth
    loeo_correct = loeo_prediction == truth[evaluable]
    hybrid_prediction = raw_prediction.copy()
    hybrid_prediction[evaluable] = loeo_prediction
    hybrid_correct = hybrid_prediction == truth
    residual = flow - projected["fitted"]
    return {
        "n": float(len(rows)),
        "vertices": float(matrix.shape[1]),
        "rank": float(np.linalg.matrix_rank(matrix, tol=1e-9)),
        "raw_correct": float(np.sum(raw_correct)),
        "hybrid_correct": float(np.sum(hybrid_correct)),
        "evaluable_n": float(np.sum(evaluable)),
        "raw_evaluable_correct": float(np.sum(raw_correct[evaluable])),
        "loeo_correct": float(np.sum(loeo_correct)),
        "bridge_or_zero_n": float(len(rows) - np.sum(evaluable)),
        "leverage_sum": float(np.sum(projected["leverage"])),
        "residual_energy": float(residual @ residual),
    }


def point_metrics(per_task: list[Mapping[str, float]]) -> dict[str, float]:
    raw_task = np.asarray([row["raw_correct"] / row["n"] for row in per_task])
    hybrid_task = np.asarray([row["hybrid_correct"] / row["n"] for row in per_task])
    loeo_task = np.asarray(
        [row["loeo_correct"] / row["evaluable_n"] for row in per_task]
    )
    raw_eval_task = np.asarray(
        [row["raw_evaluable_correct"] / row["evaluable_n"] for row in per_task]
    )
    return {
        "raw_majority_pair_micro": sum(row["raw_correct"] for row in per_task)
        / sum(row["n"] for row in per_task),
        "hybrid_pair_micro": sum(row["hybrid_correct"] for row in per_task)
        / sum(row["n"] for row in per_task),
        "hybrid_minus_raw_pair_micro": (
            sum(row["hybrid_correct"] for row in per_task)
            - sum(row["raw_correct"] for row in per_task)
        )
        / sum(row["n"] for row in per_task),
        "raw_majority_task_macro": float(np.mean(raw_task)),
        "hybrid_task_macro": float(np.mean(hybrid_task)),
        "hybrid_minus_raw_task_macro": float(np.mean(hybrid_task - raw_task)),
        "loeo_only_task_macro": float(np.mean(loeo_task)),
        "raw_on_loeo_support_task_macro": float(np.mean(raw_eval_task)),
        "loeo_minus_raw_on_loeo_support_task_macro": float(
            np.mean(loeo_task - raw_eval_task)
        ),
        "loeo_coverage_pair_micro": sum(row["evaluable_n"] for row in per_task)
        / sum(row["n"] for row in per_task),
        "loeo_coverage_task_macro": float(
            np.mean([row["evaluable_n"] / row["n"] for row in per_task])
        ),
    }


def bootstrap_metrics(
    per_task: list[Mapping[str, float]],
    *,
    repetitions: int,
    seed: int,
) -> dict[str, list[float]]:
    require(repetitions >= 1000, "bootstrap repetitions")
    rng = np.random.default_rng(seed)
    task_count = len(per_task)
    names = (
        "hybrid_minus_raw_task_macro",
        "loeo_minus_raw_on_loeo_support_task_macro",
        "hybrid_minus_raw_pair_micro",
    )
    values = {name: np.empty(repetitions, dtype=np.float64) for name in names}
    for repetition in range(repetitions):
        sampled = [per_task[index] for index in rng.integers(0, task_count, task_count)]
        metrics = point_metrics(sampled)
        for name in names:
            values[name][repetition] = metrics[name]
    lower_index = int(0.025 * repetitions)
    upper_index = int(0.975 * repetitions) - 1
    output: dict[str, list[float]] = {}
    for name in names:
        ordered = np.sort(values[name])
        output[name] = [float(ordered[lower_index]), float(ordered[upper_index])]
    return output


def paired_model_metrics(
    left: list[Mapping[str, float]], right: list[Mapping[str, float]], *, repetitions: int
) -> dict[str, Any]:
    require(len(left) == len(right), "paired task count")
    raw_delta = np.asarray(
        [l["raw_correct"] / l["n"] - r["raw_correct"] / r["n"] for l, r in zip(left, right)]
    )
    hybrid_delta = np.asarray(
        [
            l["hybrid_correct"] / l["n"] - r["hybrid_correct"] / r["n"]
            for l, r in zip(left, right)
        ]
    )
    rng = np.random.default_rng(BOOTSTRAP_SEED + 2)
    sampled = rng.integers(0, len(left), size=(repetitions, len(left)))
    raw_boot = np.mean(raw_delta[sampled], axis=1)
    hybrid_boot = np.mean(hybrid_delta[sampled], axis=1)
    lower_index = int(0.025 * repetitions)
    upper_index = int(0.975 * repetitions) - 1

    def interval(values: np.ndarray) -> list[float]:
        ordered = np.sort(values)
        return [float(ordered[lower_index]), float(ordered[upper_index])]

    return {
        "raw_task_macro_delta": float(np.mean(raw_delta)),
        "raw_task_macro_delta_ci": interval(raw_boot),
        "hybrid_task_macro_delta": float(np.mean(hybrid_delta)),
        "hybrid_task_macro_delta_ci": interval(hybrid_boot),
        "raw_loto_positive": int(
            sum(float(np.mean(np.delete(raw_delta, i))) > SIGN_TOLERANCE for i in range(len(left)))
        ),
        "hybrid_loto_positive": int(
            sum(
                float(np.mean(np.delete(hybrid_delta, i))) > SIGN_TOLERANCE
                for i in range(len(left))
            )
        ),
        "loto_total": len(left),
    }


def analyze(
    manifest_path: Path,
    master_path: Path,
    *,
    bootstrap_repetitions: int = BOOTSTRAP_REPETITIONS,
    production_checks: bool = True,
) -> dict[str, Any]:
    support, population = load_common_support(
        manifest_path, master_path, production_checks=production_checks
    )
    task_names = sorted(support)
    per_model: dict[str, list[dict[str, float]]] = {model: [] for model in MODELS}
    graph_rows = graph_vertices = graph_rank = 0
    for task in task_names:
        rows = support[task]
        graph_rows += len(rows)
        nodes, matrix = incidence_matrix(rows)
        rank = int(np.linalg.matrix_rank(matrix, tol=1e-9))
        graph_vertices += len(nodes)
        graph_rank += rank
        require(rank == len(nodes) - 1, "task graph disconnected")
        for model in MODELS:
            stats = task_statistics(rows, model)
            require(abs(stats["leverage_sum"] - rank) <= 5e-8, "Foster identity")
            per_model[model].append(stats)
    if production_checks:
        require(graph_rows == EXPECTED_COMMON_PAIRS, "graph rows")
        require(graph_vertices == EXPECTED_VERTICES, "graph vertices")
        require(len(task_names) == EXPECTED_COMPONENTS, "graph components")
        require(graph_rank == EXPECTED_RANK, "graph rank")

    metrics: dict[str, Any] = {}
    for offset, model in enumerate(MODELS):
        point = point_metrics(per_model[model])
        intervals = bootstrap_metrics(
            per_model[model],
            repetitions=bootstrap_repetitions,
            seed=BOOTSTRAP_SEED + offset,
        )
        task_deltas = [
            row["hybrid_correct"] / row["n"] - row["raw_correct"] / row["n"]
            for row in per_model[model]
        ]
        metrics[model] = {
            "point": point,
            "task_bootstrap_ci": intervals,
            "hybrid_minus_raw_loto": {
                "positive": int(
                    sum(
                        float(np.mean(np.delete(task_deltas, i))) > SIGN_TOLERANCE
                        for i in range(len(task_deltas))
                    )
                ),
                "total": len(task_deltas),
            },
            "label_free_diagnostics": {
                "residual_energy_sum": sum(row["residual_energy"] for row in per_model[model]),
                "bridge_or_zero_edges": int(
                    sum(row["bridge_or_zero_n"] for row in per_model[model])
                ),
            },
        }
    paired = paired_model_metrics(
        per_model["deepseek"], per_model["gpt"], repetitions=bootstrap_repetitions
    )

    coverage_pass = min(
        metrics[model]["point"]["loeo_coverage_pair_micro"] for model in MODELS
    ) >= 0.90
    significant_gain = any(
        metrics[model]["task_bootstrap_ci"]["hybrid_minus_raw_task_macro"][0] > 0.0
        for model in MODELS
    )
    no_negative_point = all(
        metrics[model]["point"]["hybrid_minus_raw_task_macro"] >= 0.0 for model in MODELS
    )
    comparison_stable = paired["hybrid_task_macro_delta_ci"][0] > 0.0
    if coverage_pass and significant_gain and no_negative_point:
        classification = "SUPPORTING_GRAPH_CONSISTENCY_BASELINE_IMPROVES"
    elif comparison_stable:
        classification = "NO_DENOISING_GAIN_MODEL_COMPARISON_REMAINS_STABLE"
    else:
        classification = "NO_POSITIVE_GRAPH_CONSISTENCY_RESULT"

    return {
        "protocol": "foreagent-loeo-graph-denoising-result-v1",
        "status": "HISTORICAL_PUBLIC_GRAPH_CONSISTENCY_BASELINE_COMPLETE",
        "classification": classification,
        "inputs": {
            "manifest_sha256": sha256(manifest_path),
            "master_sha256": sha256(master_path),
            "source_files": population["source_files"],
            "source_records": population["source_records"],
            "prospective_sources_read": False,
            "confidence_values_read": False,
        },
        "population": {
            "tasks": population["tasks"],
            "common_pairs": population["pairs"],
            "vertices": population["vertices"],
            "components": len(task_names),
            "incidence_rank": graph_rank,
            "cycle_rows": graph_rows - graph_rank,
            "raw_round_pair_micro_reproduction": population["raw_round_pair_micro"],
        },
        "method": {
            "fit": "unweighted task-local Hodge least squares on mean signed triplicate judgments",
            "target_edge_excluded": True,
            "loeo_formula": "(fitted_e - leverage_e * observed_e) / (1 - leverage_e)",
            "bridge_or_zero_policy": "fall back to raw triplicate majority in full-coverage hybrid",
            "labels_used_for_projection": False,
        },
        "metrics": metrics,
        "paired_deepseek_minus_gpt": paired,
        "frozen_gates": {
            "minimum_pair_coverage": 0.90,
            "coverage_pass": coverage_pass,
            "at_least_one_task_macro_gain_ci_lower_gt_zero": significant_gain,
            "both_model_task_macro_gain_points_nonnegative": no_negative_point,
            "hybrid_model_comparison_ci_lower_gt_zero": comparison_stable,
        },
        "inference": {
            "bootstrap_repetitions": bootstrap_repetitions,
            "seeds": [BOOTSTRAP_SEED, BOOTSTRAP_SEED + 1, BOOTSTRAP_SEED + 2],
            "cluster": "task",
            "pair_iid_inference": False,
        },
        "claim_boundary": {
            "algorithmic_novelty_claimed": False,
            "role": "predictor-benchmark baseline imported from established graph ranking and recent topological judge denoising work",
            "prospective_confirmation": False,
        },
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument("--master", type=Path, required=True)
    parser.add_argument("--output", type=Path)
    parser.add_argument("--bootstrap-repetitions", type=int, default=BOOTSTRAP_REPETITIONS)
    parser.add_argument("--no-production-checks", action="store_true")
    args = parser.parse_args()
    result = analyze(
        args.manifest,
        args.master,
        bootstrap_repetitions=args.bootstrap_repetitions,
        production_checks=not args.no_production_checks,
    )
    payload = json.dumps(result, sort_keys=True, indent=2, ensure_ascii=False) + "\n"
    if args.output:
        args.output.write_text(payload, encoding="utf-8")
    else:
        print(payload, end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
