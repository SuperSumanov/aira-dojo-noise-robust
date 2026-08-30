#!/usr/bin/env python3
"""Graph-rank/UST sensitivity of released FOREAGENT prediction outcomes."""

from __future__ import annotations

import argparse
from collections import defaultdict
import hashlib
import json
import math
import os
from pathlib import Path
import random
from typing import Any, Iterable, Mapping

import numpy as np


MANIFEST_SHA256 = "3df2715b2d2e5f3cc6193c07c99eb682e042e8aa6cb724b046b2469b35773a4e"
MASTER_SHA256 = "480616317ddebb249084dbc8b36b4060fac4b77353fce16b436351eab9c235fe"
EXPECTED_SOURCE_RECORDS = 110620
EXPECTED_SOURCE_FILES = 156
EXPECTED_TASKS = 26
EXPECTED_DEEPSEEK_GRID_PAIRS = 18438
EXPECTED_GPT_GRID_PAIRS = 18430
EXPECTED_COMMON_GRID_PAIRS = 18430
EXPECTED_DEEPSEEK_FINITE_PAIRS = 18389
EXPECTED_GPT_FINITE_PAIRS = 18381
EXPECTED_COMMON_FINITE_PAIRS = 18381
BOOTSTRAP_REPETITIONS = 20000
BOOTSTRAP_SEED = 20260830
NUMERIC_TOLERANCE = 5e-9
SIGN_TOLERANCE = 1e-10
MODELS = ("deepseek", "gpt")

KNOWN_REPRODUCTION = {
    "deepseek": {
        "raw_pair_micro": 0.6151503616292348,
        "raw_task_macro": 0.6066975560136538,
    },
    "gpt": {
        "raw_pair_micro": 0.588959614094264,
        "raw_task_macro": 0.5800668567178495,
    },
}


def require(condition: bool, message: str) -> None:
    if not condition:
        raise ValueError(message)


def file_sha(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1 << 20), b""):
            digest.update(block)
    return digest.hexdigest()


def canonical_bytes(value: Any) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True).encode() + b"\n"


def decimal(value: float) -> str:
    require(math.isfinite(value), "nonfinite decimal")
    return format(float(value), ".17g")


def parse_index(value: Any) -> int | None:
    if isinstance(value, bool):
        return None
    if isinstance(value, int) and value in (0, 1):
        return value
    return None


def canonical_score(value: float) -> float | str:
    if math.isnan(value):
        return "nan"
    if value == math.inf:
        return "+inf"
    if value == -math.inf:
        return "-inf"
    return value


def parse_record(raw: Mapping[str, Any], source: Mapping[str, Any]) -> dict[str, Any]:
    source_index = raw.get("source_index")
    require(source_index == source["source_index"], "source index mismatch")
    task = raw.get("task")
    model = raw.get("model_family")
    release_run = raw.get("release_run")
    require(
        (task, model, release_run)
        == (source["task"], source["model_family"], source["release_run"]),
        "source metadata mismatch",
    )
    require(model in MODELS, "unexpected model")

    paths_raw = raw.get("solution_paths")
    scores_raw = raw.get("scores")
    require(
        isinstance(paths_raw, list)
        and len(paths_raw) == 2
        and all(isinstance(path, str) and path for path in paths_raw)
        and paths_raw[0] != paths_raw[1],
        "invalid solution paths",
    )
    require(isinstance(scores_raw, list) and len(scores_raw) == 2, "invalid scores")
    try:
        scores = (float(scores_raw[0]), float(scores_raw[1]))
    except (TypeError, ValueError) as error:
        raise ValueError("non-numeric scores") from error
    lower = raw.get("is_lower_better")
    require(isinstance(lower, bool), "invalid direction")
    paths = (paths_raw[0], paths_raw[1])

    if not all(math.isfinite(value) for value in scores):
        label_status = "nonfinite_score"
        true_path = None
    elif scores[0] == scores[1]:
        label_status = "exact_tie"
        true_path = None
    else:
        label_status = "finite_nontie"
        if lower:
            true_path = paths[0] if scores[0] < scores[1] else paths[1]
        else:
            true_path = paths[0] if scores[0] > scores[1] else paths[1]

    groundtruth_index = parse_index(raw.get("groundtruth_best_index"))
    require(groundtruth_index is not None, "invalid groundtruth index")
    groundtruth_path = paths[groundtruth_index]
    if true_path is not None:
        require(groundtruth_path == true_path, "groundtruth/score disagreement")
    prediction_index = parse_index(raw.get("prediction_best_index"))
    prediction_path = paths[prediction_index] if prediction_index is not None else None
    correctness = float(prediction_path == true_path) if true_path is not None else None
    pair_key = tuple(sorted(paths))
    return {
        "task": task,
        "model": model,
        "release_run": release_run,
        "pair_key": pair_key,
        "score_by_path": tuple(
            sorted(
                (
                    (paths[0], canonical_score(scores[0])),
                    (paths[1], canonical_score(scores[1])),
                )
            )
        ),
        "lower": lower,
        "label_status": label_status,
        "true_path": true_path,
        "correct": correctness,
    }


def load_records(
    manifest: Mapping[str, Any], rows: Iterable[Mapping[str, Any]]
) -> tuple[list[dict[str, Any]], dict[int, dict[tuple[str, str], dict[str, Any]]], int]:
    files = manifest.get("files")
    require(isinstance(files, list) and files, "manifest files")
    sources: list[dict[str, Any]] = []
    for source_index, source_raw in enumerate(files):
        require(isinstance(source_raw, dict), "manifest source")
        source = dict(source_raw)
        source["source_index"] = source_index
        require(source.get("model_family") in MODELS, "manifest model")
        require(isinstance(source.get("task"), str) and source["task"], "manifest task")
        require(source.get("release_run") in (1, 2, 3), "manifest release run")
        sources.append(source)

    by_source: dict[int, dict[tuple[str, str], dict[str, Any]]] = defaultdict(dict)
    count = 0
    for count, raw in enumerate(rows, start=1):
        require(isinstance(raw, dict), "master row")
        source_index = raw.get("source_index")
        require(
            isinstance(source_index, int) and 0 <= source_index < len(sources),
            "master source index",
        )
        parsed = parse_record(raw, sources[source_index])
        key = parsed["pair_key"]
        require(key not in by_source[source_index], "duplicate pair within source")
        by_source[source_index][key] = parsed
    require(count > 0, "empty master")
    require(set(by_source) == set(range(len(sources))), "missing source records")
    return sources, by_source, count


def consistent_truth(records: list[Mapping[str, Any]]) -> None:
    require(records, "empty truth records")
    reference = records[0]
    for row in records[1:]:
        require(row["task"] == reference["task"], "task drift across releases")
        require(row["score_by_path"] == reference["score_by_path"], "score drift across releases")
        require(row["lower"] == reference["lower"], "direction drift across releases")
        require(row["label_status"] == reference["label_status"], "label status drift")
        require(row["true_path"] == reference["true_path"], "truth drift across releases")


def build_model_support(
    sources: list[Mapping[str, Any]],
    by_source: Mapping[int, Mapping[tuple[str, str], Mapping[str, Any]]],
) -> tuple[
    dict[str, dict[str, dict[tuple[str, str], dict[str, Any]]]],
    dict[str, Any],
]:
    indices: dict[tuple[str, str], list[int]] = defaultdict(list)
    tasks: set[str] = set()
    for source in sources:
        key = (source["model_family"], source["task"])
        indices[key].append(source["source_index"])
        tasks.add(source["task"])
    for key in indices:
        indices[key].sort(key=lambda index: sources[index]["release_run"])
        require(len(indices[key]) == 3, "expected three releases")

    support: dict[str, dict[str, dict[tuple[str, str], dict[str, Any]]]] = {
        model: {} for model in MODELS
    }
    grid_counts = {model: 0 for model in MODELS}
    finite_counts = {model: 0 for model in MODELS}
    excluded_incomplete = {model: 0 for model in MODELS}
    grid_by_model_task: dict[tuple[str, str], set[tuple[str, str]]] = {}
    for task in sorted(tasks):
        for model in MODELS:
            source_indices = indices[(model, task)]
            key_sets = [set(by_source[index]) for index in source_indices]
            union = set.union(*key_sets)
            if model == "deepseek":
                require(key_sets[0] == key_sets[1] == key_sets[2], "deepseek grid drift")
                grid = set(key_sets[0])
            else:
                grid = set.intersection(*key_sets)
            excluded_incomplete[model] += len(union - grid)
            grid_counts[model] += len(grid)
            grid_by_model_task[(model, task)] = grid
            valid: dict[tuple[str, str], dict[str, Any]] = {}
            for pair_key in sorted(grid):
                records = [by_source[index][pair_key] for index in source_indices]
                consistent_truth(records)
                reference = records[0]
                if reference["true_path"] is None:
                    continue
                values = [float(record["correct"]) for record in records]
                valid[pair_key] = {
                    "task": task,
                    "pair_key": pair_key,
                    "true_path": reference["true_path"],
                    "score_by_path": reference["score_by_path"],
                    "accuracy": sum(values) / len(values),
                }
            support[model][task] = valid
            finite_counts[model] += len(valid)

    common_grid_pairs = 0
    for task in sorted(tasks):
        common_grid_pairs += len(
            grid_by_model_task[("deepseek", task)] & grid_by_model_task[("gpt", task)]
        )
    return support, {
        "tasks": len(tasks),
        "grid_counts": grid_counts,
        "finite_counts": finite_counts,
        "excluded_incomplete_triplicate_pairs": excluded_incomplete,
        "cross_model_common_grid_pairs": common_grid_pairs,
    }


def common_finite_support(
    support: Mapping[str, Mapping[str, Mapping[tuple[str, str], Mapping[str, Any]]]]
) -> dict[str, dict[tuple[str, str], dict[str, Any]]]:
    tasks = sorted(set(support["deepseek"]) & set(support["gpt"]))
    require(tasks and set(tasks) == set(support["deepseek"]) == set(support["gpt"]), "task support")
    common: dict[str, dict[tuple[str, str], dict[str, Any]]] = {}
    for task in tasks:
        deepseek = support["deepseek"][task]
        gpt = support["gpt"][task]
        pairs: dict[tuple[str, str], dict[str, Any]] = {}
        for pair_key in sorted(set(deepseek) & set(gpt)):
            left, right = deepseek[pair_key], gpt[pair_key]
            require(left["true_path"] == right["true_path"], "cross-model truth drift")
            require(left["score_by_path"] == right["score_by_path"], "cross-model score drift")
            pairs[pair_key] = {
                "deepseek": left["accuracy"],
                "gpt": right["accuracy"],
            }
        require(pairs, "empty common task support")
        common[task] = pairs
    return common


class UnionFind:
    def __init__(self) -> None:
        self.parent: dict[str, str] = {}

    def add(self, node: str) -> None:
        self.parent.setdefault(node, node)

    def find(self, node: str) -> str:
        while self.parent[node] != node:
            self.parent[node] = self.parent[self.parent[node]]
            node = self.parent[node]
        return node

    def union(self, left: str, right: str) -> None:
        self.add(left)
        self.add(right)
        left_root, right_root = self.find(left), self.find(right)
        if left_root != right_root:
            self.parent[right_root] = left_root


def component_weights(nodes: list[str], edges: list[tuple[str, str]]) -> list[float]:
    require(len(nodes) >= 2 and edges, "empty graph component")
    index = {node: position for position, node in enumerate(nodes)}
    laplacian = np.zeros((len(nodes), len(nodes)), dtype=np.float64)
    for left, right in edges:
        i, j = index[left], index[right]
        laplacian[i, i] += 1.0
        laplacian[j, j] += 1.0
        laplacian[i, j] -= 1.0
        laplacian[j, i] -= 1.0
    eigenvalues, eigenvectors = np.linalg.eigh(laplacian)
    scale = max(1.0, float(eigenvalues[-1]))
    threshold = np.finfo(np.float64).eps * len(nodes) * scale * 32.0
    require(abs(float(eigenvalues[0])) <= threshold, "missing nullspace")
    require(np.all(eigenvalues[1:] > threshold), "component not connected")
    vectors = eigenvectors[:, 1:]
    pseudoinverse = (vectors / eigenvalues[1:]) @ vectors.T
    weights: list[float] = []
    for left, right in edges:
        i, j = index[left], index[right]
        value = float(pseudoinverse[i, i] + pseudoinverse[j, j] - 2.0 * pseudoinverse[i, j])
        require(value > 0.0 and value <= 1.0 + NUMERIC_TOLERANCE, "invalid leverage")
        weights.append(min(value, 1.0))
    expected = len(nodes) - 1
    require(
        abs(sum(weights) - expected) <= NUMERIC_TOLERANCE * max(1, expected),
        "component Foster identity",
    )
    return weights


def linear_quantile(sorted_values: list[float], fraction: float) -> float:
    require(sorted_values and 0.0 <= fraction <= 1.0, "quantile arguments")
    position = fraction * (len(sorted_values) - 1)
    lower = int(math.floor(position))
    upper = int(math.ceil(position))
    if lower == upper:
        return sorted_values[lower]
    interpolation = position - lower
    return sorted_values[lower] * (1.0 - interpolation) + sorted_values[upper] * interpolation


def build_weights(
    common: Mapping[str, Mapping[tuple[str, str], Mapping[str, float]]]
) -> tuple[dict[tuple[str, tuple[str, str]], float], dict[str, Any]]:
    weights: dict[tuple[str, tuple[str, str]], float] = {}
    all_weights: list[float] = []
    task_rows: dict[str, int] = {}
    task_rank: dict[str, int] = {}
    vertices = components = complete_components = incomplete_components = 0
    maximum_residual = 0.0
    for task in sorted(common):
        pairs = common[task]
        union = UnionFind()
        for pair_key in sorted(pairs):
            left, right = pair_key
            # Official solution paths are relative to a task. Every graph in this
            # routine is task-local, so endpoint identity is (task, path).
            union.union(left, right)
        component_nodes: dict[str, list[str]] = defaultdict(list)
        for node in sorted(union.parent):
            component_nodes[union.find(node)].append(node)
        component_edges: dict[str, list[tuple[str, str]]] = defaultdict(list)
        for pair_key in sorted(pairs):
            root = union.find(pair_key[0])
            require(root == union.find(pair_key[1]), "edge component drift")
            component_edges[root].append(pair_key)
        local_rank = 0
        for root in sorted(component_nodes):
            nodes = component_nodes[root]
            edges = component_edges[root]
            values = component_weights(nodes, edges)
            expected = len(nodes) - 1
            maximum_residual = max(maximum_residual, abs(sum(values) - expected))
            local_rank += expected
            vertices += len(nodes)
            components += 1
            if len(edges) == len(nodes) * (len(nodes) - 1) // 2:
                complete_components += 1
            else:
                incomplete_components += 1
            for edge, value in zip(edges, values):
                weights[(task, edge)] = value
                all_weights.append(value)
        task_rows[task] = len(pairs)
        task_rank[task] = local_rank

    pair_rows = sum(task_rows.values())
    rank = sum(task_rank.values())
    require(pair_rows == len(weights) == len(all_weights), "weight row accounting")
    require(vertices - components == rank, "incidence rank accounting")
    require(abs(sum(all_weights) - rank) <= NUMERIC_TOLERANCE * rank, "global Foster identity")
    raw_task_probability = {task: count / pair_rows for task, count in task_rows.items()}
    rank_task_probability = {task: count / rank for task, count in task_rank.items()}
    edge_tv = 0.5 * sum(abs(value / rank - 1.0 / pair_rows) for value in all_weights)
    task_tv = 0.5 * sum(
        abs(raw_task_probability[task] - rank_task_probability[task]) for task in task_rows
    )
    sorted_weights = sorted(all_weights)
    return weights, {
        "pair_rows": pair_rows,
        "vertices": vertices,
        "tasks": len(task_rows),
        "connected_components": components,
        "complete_components": complete_components,
        "incomplete_components": incomplete_components,
        "endpoint_edge_incidence_rank": rank,
        "cycle_rows": pair_rows - rank,
        "weight_sum_decimal_17g": decimal(sum(all_weights)),
        "maximum_component_foster_residual_decimal_17g": decimal(maximum_residual),
        "minimum_weight_decimal_17g": decimal(sorted_weights[0]),
        "median_weight_decimal_17g": decimal(linear_quantile(sorted_weights, 0.5)),
        "maximum_weight_decimal_17g": decimal(sorted_weights[-1]),
        "edge_distribution_total_variation_decimal_17g": decimal(edge_tv),
        "task_weight_total_variation_decimal_17g": decimal(task_tv),
        "raw_max_task_share_decimal_17g": decimal(max(raw_task_probability.values())),
        "rank_max_task_share_decimal_17g": decimal(max(rank_task_probability.values())),
        "unit_probability_bridge_edges": sum(
            value >= 1.0 - NUMERIC_TOLERANCE for value in all_weights
        ),
        "task_identities_emitted": False,
    }


def cluster_statistics(
    common: Mapping[str, Mapping[tuple[str, str], Mapping[str, float]]],
    weights: Mapping[tuple[str, tuple[str, str]], float],
    model: str,
) -> dict[str, dict[str, float]]:
    require(model in ("deepseek", "gpt", "deepseek_minus_gpt"), "metric model")
    statistics: dict[str, dict[str, float]] = {}
    for task in sorted(common):
        raw_values: list[float] = []
        weighted_values: list[tuple[float, float]] = []
        for pair_key in sorted(common[task]):
            if model == "deepseek_minus_gpt":
                value = common[task][pair_key]["deepseek"] - common[task][pair_key]["gpt"]
            else:
                value = common[task][pair_key][model]
            weight = weights[(task, pair_key)]
            raw_values.append(value)
            weighted_values.append((weight, value))
        weight_sum = sum(weight for weight, _ in weighted_values)
        statistics[task] = {
            "rows": float(len(raw_values)),
            "rank": weight_sum,
            "raw_sum": sum(raw_values),
            "weighted_sum": sum(weight * value for weight, value in weighted_values),
            "raw_task": sum(raw_values) / len(raw_values),
            "weighted_task": sum(weight * value for weight, value in weighted_values) / weight_sum,
        }
    return statistics


def point_metrics(statistics: Mapping[str, Mapping[str, float]], tasks: list[str]) -> dict[str, float]:
    require(tasks, "empty metric tasks")
    raw_pair = sum(statistics[task]["raw_sum"] for task in tasks) / sum(
        statistics[task]["rows"] for task in tasks
    )
    ust_rank = sum(statistics[task]["weighted_sum"] for task in tasks) / sum(
        statistics[task]["rank"] for task in tasks
    )
    raw_task = sum(statistics[task]["raw_task"] for task in tasks) / len(tasks)
    ust_task = sum(statistics[task]["weighted_task"] for task in tasks) / len(tasks)
    return {
        "raw_pair_micro": raw_pair,
        "ust_rank_micro": ust_rank,
        "raw_task_macro": raw_task,
        "ust_task_macro": ust_task,
        "ust_minus_raw_rank_micro": ust_rank - raw_pair,
        "ust_minus_raw_task_macro": ust_task - raw_task,
    }


def interval(values: list[float]) -> tuple[float, float]:
    require(len(values) >= 40, "insufficient bootstrap draws")
    values.sort()
    lower = int(0.025 * len(values))
    upper = int(0.975 * len(values)) - 1
    return values[lower], values[upper]


def summarize_statistics(
    statistics: Mapping[str, Mapping[str, float]],
    *,
    bootstrap_repetitions: int,
    seed: int,
) -> dict[str, Any]:
    tasks = sorted(statistics)
    points = point_metrics(statistics, tasks)
    rng = random.Random(seed)
    draws = {name: [] for name in points}
    for _ in range(bootstrap_repetitions):
        sampled = [rng.choice(tasks) for _ in tasks]
        current = point_metrics(statistics, sampled)
        for name, value in current.items():
            draws[name].append(value)
    result: dict[str, Any] = {}
    for name in sorted(points):
        ci = interval(draws[name])
        result[name] = {
            "point_decimal_17g": decimal(points[name]),
            "task_clustered_ci95": [decimal(ci[0]), decimal(ci[1])],
        }
    loto = {
        name: [
            point_metrics(statistics, [task for task in tasks if task != omitted])[name]
            for omitted in tasks
        ]
        for name in points
    }
    result["leave_one_task_out"] = {
        name: {
            "minimum_decimal_17g": decimal(min(values)),
            "maximum_decimal_17g": decimal(max(values)),
            "positive_count": sum(value > SIGN_TOLERANCE for value in values),
            "total": len(values),
        }
        for name, values in sorted(loto.items())
    }
    return result


def source_grid_reproduction(
    support: Mapping[str, Mapping[str, Mapping[tuple[str, str], Mapping[str, Any]]]],
    model: str,
) -> dict[str, Any]:
    task_values: dict[str, list[float]] = {}
    for task in sorted(support[model]):
        values = [support[model][task][key]["accuracy"] for key in sorted(support[model][task])]
        require(values, "empty source-grid task")
        task_values[task] = values
    pair_values = [value for task in sorted(task_values) for value in task_values[task]]
    pair_micro = sum(pair_values) / len(pair_values)
    task_macro = sum(sum(values) / len(values) for values in task_values.values()) / len(task_values)
    return {
        "finite_directional_pairs": len(pair_values),
        "tasks": len(task_values),
        "raw_pair_micro_decimal_17g": decimal(pair_micro),
        "raw_task_macro_decimal_17g": decimal(task_macro),
    }


def analyze_data(
    manifest: Mapping[str, Any],
    rows: Iterable[Mapping[str, Any]],
    *,
    manifest_sha256: str,
    master_sha256: str,
    bootstrap_repetitions: int = BOOTSTRAP_REPETITIONS,
    production_checks: bool = False,
) -> dict[str, Any]:
    require(bootstrap_repetitions >= 40, "bootstrap repetitions")
    sources, by_source, source_records = load_records(manifest, rows)
    support, grid = build_model_support(sources, by_source)
    common = common_finite_support(support)
    common_pairs = sum(len(pairs) for pairs in common.values())
    weights, graph = build_weights(common)
    reproduction = {
        model: source_grid_reproduction(support, model) for model in MODELS
    }
    if production_checks:
        require(manifest_sha256 == MANIFEST_SHA256, "manifest SHA")
        require(master_sha256 == MASTER_SHA256, "master SHA")
        require(source_records == EXPECTED_SOURCE_RECORDS, "source record count")
        require(len(sources) == EXPECTED_SOURCE_FILES, "source file count")
        require(grid["tasks"] == EXPECTED_TASKS, "task count")
        require(grid["grid_counts"]["deepseek"] == EXPECTED_DEEPSEEK_GRID_PAIRS, "deepseek grid")
        require(grid["grid_counts"]["gpt"] == EXPECTED_GPT_GRID_PAIRS, "gpt grid")
        require(grid["cross_model_common_grid_pairs"] == EXPECTED_COMMON_GRID_PAIRS, "common grid")
        require(grid["finite_counts"]["deepseek"] == EXPECTED_DEEPSEEK_FINITE_PAIRS, "deepseek finite")
        require(grid["finite_counts"]["gpt"] == EXPECTED_GPT_FINITE_PAIRS, "gpt finite")
        require(common_pairs == EXPECTED_COMMON_FINITE_PAIRS, "common finite")
        for model in MODELS:
            for field in ("raw_pair_micro", "raw_task_macro"):
                actual = float(reproduction[model][f"{field}_decimal_17g"])
                require(abs(actual - KNOWN_REPRODUCTION[model][field]) <= 1e-15, "raw reproduction")

    metrics = {
        model: summarize_statistics(
            cluster_statistics(common, weights, model),
            bootstrap_repetitions=bootstrap_repetitions,
            seed=BOOTSTRAP_SEED,
        )
        for model in MODELS
    }
    paired = summarize_statistics(
        cluster_statistics(common, weights, "deepseek_minus_gpt"),
        bootstrap_repetitions=bootstrap_repetitions,
        seed=BOOTSTRAP_SEED + 1,
    )
    return {
        "protocol": "foreagent-ust-outcome-sensitivity-result-v1",
        "status": "HISTORICAL_PUBLIC_OUTCOME_SENSITIVITY_COMPLETE",
        "classification": "POSTDISCLOSURE_GRAPH_WEIGHTED_SENSITIVITY_COMPLETE",
        "inputs": {
            "manifest_sha256": manifest_sha256,
            "master_sha256": master_sha256,
            "source_files": len(sources),
            "source_records": source_records,
        },
        "population": {
            "tasks": grid["tasks"],
            "deepseek_grid_pairs": grid["grid_counts"]["deepseek"],
            "gpt_grid_pairs": grid["grid_counts"]["gpt"],
            "cross_model_common_grid_pairs": grid["cross_model_common_grid_pairs"],
            "deepseek_finite_directional_pairs": grid["finite_counts"]["deepseek"],
            "gpt_finite_directional_pairs": grid["finite_counts"]["gpt"],
            "common_finite_directional_pairs": common_pairs,
            "gpt_excluded_incomplete_triplicate_pairs": grid[
                "excluded_incomplete_triplicate_pairs"
            ]["gpt"],
            "confidence_values_read": False,
        },
        "source_grid_reproduction": reproduction,
        "common_support_graph": graph,
        "common_support_metrics": metrics,
        "paired_deepseek_minus_gpt": paired,
        "inference": {
            "bootstrap_repetitions": bootstrap_repetitions,
            "model_metric_seed": BOOTSTRAP_SEED,
            "paired_metric_seed": BOOTSTRAP_SEED + 1,
            "primary_cluster": "task",
            "release_runs_averaged_within_pair": True,
        },
        "interpretation": {
            "raw_pair_micro": "Each released pair row has equal weight.",
            "ust_rank_micro": "Each edge is weighted by its uniform-spanning-tree inclusion probability; tasks receive total weight equal to their endpoint-incidence rank.",
            "raw_task_macro": "Uniform pair rows within task, then equal tasks.",
            "ust_task_macro": "UST-weighted edges within task, then equal tasks.",
            "no_success_threshold": True,
            "does_not_reclassify_prior_insufficient_support_audit": True,
        },
        "scope": {
            "historical_public_scores_and_predictions_read": True,
            "fields_read": [
                "source_index",
                "task",
                "model_family",
                "release_run",
                "solution_paths",
                "scores",
                "is_lower_better",
                "groundtruth_best_index",
                "prediction_best_index",
            ],
            "confidence_values_read": False,
            "solution_code_read": False,
            "prospective_values_read": False,
            "raw_task_or_endpoint_identities_emitted": False,
            "gpu_paid_api_model_fit_base_update": "0/0/0/0",
        },
    }


def read_jsonl(path: Path) -> Iterable[dict[str, Any]]:
    with path.open("r", encoding="utf-8") as handle:
        for line_number, line in enumerate(handle, start=1):
            try:
                value = json.loads(line)
            except json.JSONDecodeError as error:
                raise ValueError(f"invalid JSONL line {line_number}") from error
            require(isinstance(value, dict), "JSONL row object")
            yield value


def write_exclusive(path: Path, value: Mapping[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    descriptor = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    try:
        with os.fdopen(descriptor, "wb") as handle:
            handle.write(canonical_bytes(value))
            handle.flush()
            os.fsync(handle.fileno())
    except BaseException:
        try:
            path.unlink()
        except FileNotFoundError:
            pass
        raise


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument("--master", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    manifest_path = args.manifest.resolve()
    master_path = args.master.resolve()
    manifest_sha = file_sha(manifest_path)
    master_sha = file_sha(master_path)
    require(manifest_sha == MANIFEST_SHA256, "unfrozen manifest")
    require(master_sha == MASTER_SHA256, "unfrozen master")
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    result = analyze_data(
        manifest,
        read_jsonl(master_path),
        manifest_sha256=manifest_sha,
        master_sha256=master_sha,
        production_checks=True,
    )
    write_exclusive(args.output.resolve(), result)
    print(
        canonical_bytes(
            {
                "status": result["status"],
                "classification": result["classification"],
                "output_sha256": file_sha(args.output.resolve()),
                "confidence_values_read": False,
                "prospective_values_read": False,
            }
        ).decode(),
        end="",
    )


if __name__ == "__main__":
    main()
