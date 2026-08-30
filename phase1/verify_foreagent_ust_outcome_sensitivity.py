#!/usr/bin/env python3
"""Independent grounded-Laplacian verifier for FOREAGENT UST outcome sensitivity."""

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
EXPECTED_COMMON_FINITE_PAIRS = 18381
BOOTSTRAP_REPETITIONS = 20000
BOOTSTRAP_SEED = 20260830
TOLERANCE = 2e-8
SIGN_TOLERANCE = 1e-10
MODELS = ("deepseek", "gpt")


def check(condition: bool, message: str) -> None:
    if not condition:
        raise ValueError(message)


def sha(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1 << 20), b""):
            digest.update(block)
    return digest.hexdigest()


def canonical(value: Any) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True).encode() + b"\n"


def dec(value: float) -> str:
    check(math.isfinite(value), "decimal finite")
    return format(float(value), ".17g")


def index(value: Any) -> int | None:
    return value if isinstance(value, int) and not isinstance(value, bool) and value in (0, 1) else None


def score_token(value: float) -> float | str:
    if math.isnan(value):
        return "nan"
    if value == math.inf:
        return "+inf"
    if value == -math.inf:
        return "-inf"
    return value


def load(
    manifest: Mapping[str, Any], rows: Iterable[Mapping[str, Any]]
) -> tuple[
    list[dict[str, Any]],
    dict[int, dict[tuple[str, str], dict[str, Any]]],
    int,
    set[str],
    set[str],
]:
    files = manifest.get("files")
    check(isinstance(files, list) and files, "manifest files")
    sources: list[dict[str, Any]] = []
    task_identities: set[str] = set()
    for source_index, source_raw in enumerate(files):
        check(isinstance(source_raw, dict), "source row")
        source = dict(source_raw)
        source["source_index"] = source_index
        check(source.get("model_family") in MODELS, "source model")
        check(source.get("release_run") in (1, 2, 3), "source run")
        check(isinstance(source.get("task"), str) and source["task"], "source task")
        task_identities.add(source["task"])
        sources.append(source)

    records: dict[int, dict[tuple[str, str], dict[str, Any]]] = defaultdict(dict)
    endpoint_identities: set[str] = set()
    count = 0
    for count, row in enumerate(rows, start=1):
        check(isinstance(row, dict), "master row")
        source_index = row.get("source_index")
        check(isinstance(source_index, int) and 0 <= source_index < len(sources), "source index")
        source = sources[source_index]
        check(
            (row.get("task"), row.get("model_family"), row.get("release_run"))
            == (source["task"], source["model_family"], source["release_run"]),
            "source metadata",
        )
        paths = row.get("solution_paths")
        check(
            isinstance(paths, list)
            and len(paths) == 2
            and all(isinstance(path, str) and path for path in paths)
            and paths[0] != paths[1],
            "paths",
        )
        endpoint_identities.update(paths)
        scores_raw = row.get("scores")
        check(isinstance(scores_raw, list) and len(scores_raw) == 2, "scores")
        scores = (float(scores_raw[0]), float(scores_raw[1]))
        lower = row.get("is_lower_better")
        check(isinstance(lower, bool), "lower")
        finite = all(math.isfinite(value) for value in scores)
        if not finite:
            true_path = None
            label_status = "nonfinite_score"
        elif scores[0] == scores[1]:
            true_path = None
            label_status = "exact_tie"
        elif lower:
            true_path = paths[0] if scores[0] < scores[1] else paths[1]
            label_status = "finite_nontie"
        else:
            true_path = paths[0] if scores[0] > scores[1] else paths[1]
            label_status = "finite_nontie"
        groundtruth_index = index(row.get("groundtruth_best_index"))
        check(groundtruth_index is not None, "groundtruth index")
        if true_path is not None:
            check(paths[groundtruth_index] == true_path, "groundtruth mismatch")
        prediction_index = index(row.get("prediction_best_index"))
        predicted_path = paths[prediction_index] if prediction_index is not None else None
        key = tuple(sorted((paths[0], paths[1])))
        check(key not in records[source_index], "duplicate source pair")
        records[source_index][key] = {
            "task": source["task"],
            "score_by_path": tuple(
                sorted(
                    (
                        (paths[0], score_token(scores[0])),
                        (paths[1], score_token(scores[1])),
                    )
                )
            ),
            "lower": lower,
            "label_status": label_status,
            "true": true_path,
            "correct": float(predicted_path == true_path) if true_path is not None else None,
        }
    check(count > 0 and set(records) == set(range(len(sources))), "source coverage")
    return sources, records, count, task_identities, endpoint_identities


def support(
    sources: list[Mapping[str, Any]],
    records: Mapping[int, Mapping[tuple[str, str], Mapping[str, Any]]],
) -> tuple[
    dict[str, dict[str, dict[tuple[str, str], dict[str, Any]]]],
    dict[str, Any],
]:
    source_indices: dict[tuple[str, str], list[int]] = defaultdict(list)
    tasks: set[str] = set()
    for source in sources:
        source_indices[(source["model_family"], source["task"])].append(source["source_index"])
        tasks.add(source["task"])
    for key in source_indices:
        source_indices[key].sort(key=lambda number: sources[number]["release_run"])
        check(len(source_indices[key]) == 3, "three releases")

    output: dict[str, dict[str, dict[tuple[str, str], dict[str, Any]]]] = {
        model: {} for model in MODELS
    }
    grid_counts = {model: 0 for model in MODELS}
    finite_counts = {model: 0 for model in MODELS}
    excluded = {model: 0 for model in MODELS}
    grids: dict[tuple[str, str], set[tuple[str, str]]] = {}
    for task in sorted(tasks):
        for model in MODELS:
            indices = source_indices[(model, task)]
            sets = [set(records[number]) for number in indices]
            union = set.union(*sets)
            if model == "deepseek":
                check(sets[0] == sets[1] == sets[2], "deepseek grid")
                grid = set(sets[0])
            else:
                grid = set.intersection(*sets)
            grids[(model, task)] = grid
            grid_counts[model] += len(grid)
            excluded[model] += len(union - grid)
            valid: dict[tuple[str, str], dict[str, Any]] = {}
            for pair in sorted(grid):
                values = [records[number][pair] for number in indices]
                reference = values[0]
                for value in values[1:]:
                    check(value["task"] == reference["task"], "task drift")
                    check(value["score_by_path"] == reference["score_by_path"], "score drift")
                    check(value["lower"] == reference["lower"], "lower drift")
                    check(value["label_status"] == reference["label_status"], "label drift")
                    check(value["true"] == reference["true"], "truth drift")
                if reference["true"] is None:
                    continue
                valid[pair] = {
                    "true": reference["true"],
                    "score_by_path": reference["score_by_path"],
                    "accuracy": sum(float(value["correct"]) for value in values) / 3.0,
                }
            output[model][task] = valid
            finite_counts[model] += len(valid)
    common_grid = sum(
        len(grids[("deepseek", task)] & grids[("gpt", task)]) for task in sorted(tasks)
    )
    return output, {
        "tasks": len(tasks),
        "grid_counts": grid_counts,
        "finite_counts": finite_counts,
        "excluded": excluded,
        "common_grid": common_grid,
    }


def common(
    model_support: Mapping[str, Mapping[str, Mapping[tuple[str, str], Mapping[str, Any]]]]
) -> dict[str, dict[tuple[str, str], dict[str, float]]]:
    tasks = sorted(model_support["deepseek"])
    check(set(tasks) == set(model_support["gpt"]), "model tasks")
    output: dict[str, dict[tuple[str, str], dict[str, float]]] = {}
    for task in tasks:
        deepseek = model_support["deepseek"][task]
        gpt = model_support["gpt"][task]
        pairs: dict[tuple[str, str], dict[str, float]] = {}
        for pair in sorted(set(deepseek) & set(gpt)):
            check(deepseek[pair]["true"] == gpt[pair]["true"], "cross-model truth")
            check(deepseek[pair]["score_by_path"] == gpt[pair]["score_by_path"], "cross-model score")
            pairs[pair] = {
                "deepseek": float(deepseek[pair]["accuracy"]),
                "gpt": float(gpt[pair]["accuracy"]),
            }
        check(pairs, "empty common task")
        output[task] = pairs
    return output


def grounded_weights(nodes: list[str], edges: list[tuple[str, str]]) -> list[float]:
    check(len(nodes) >= 2 and edges, "component")
    position = {node: number for number, node in enumerate(nodes)}
    laplacian = np.zeros((len(nodes), len(nodes)), dtype=np.float64)
    for left, right in edges:
        i, j = position[left], position[right]
        laplacian[i, i] += 1.0
        laplacian[j, j] += 1.0
        laplacian[i, j] -= 1.0
        laplacian[j, i] -= 1.0
    ground = len(nodes) - 1
    inverse = np.linalg.inv(laplacian[:ground, :ground])
    values: list[float] = []
    for left, right in edges:
        i, j = position[left], position[right]
        if i == ground:
            value = float(inverse[j, j])
        elif j == ground:
            value = float(inverse[i, i])
        else:
            value = float(inverse[i, i] + inverse[j, j] - 2.0 * inverse[i, j])
        check(value > 0.0 and value <= 1.0 + TOLERANCE, "weight range")
        values.append(min(value, 1.0))
    check(abs(sum(values) - ground) <= TOLERANCE * max(1, ground), "Foster identity")
    return values


def linear_quantile(sorted_values: list[float], fraction: float) -> float:
    check(sorted_values and 0.0 <= fraction <= 1.0, "quantile arguments")
    position = fraction * (len(sorted_values) - 1)
    lower = int(math.floor(position))
    upper = int(math.ceil(position))
    if lower == upper:
        return sorted_values[lower]
    interpolation = position - lower
    return sorted_values[lower] * (1.0 - interpolation) + sorted_values[upper] * interpolation


def graph(
    pairs_by_task: Mapping[str, Mapping[tuple[str, str], Mapping[str, float]]]
) -> tuple[dict[tuple[str, tuple[str, str]], float], dict[str, Any]]:
    weights: dict[tuple[str, tuple[str, str]], float] = {}
    all_weights: list[float] = []
    rows_by_task: dict[str, int] = {}
    rank_by_task: dict[str, int] = {}
    vertices = component_count = complete = incomplete = 0
    maximum_residual = 0.0
    node_task: dict[str, str] = {}
    for task in sorted(pairs_by_task):
        adjacency: dict[str, set[str]] = defaultdict(set)
        for left, right in sorted(pairs_by_task[task]):
            check(node_task.setdefault(left, task) == task, "node task")
            check(node_task.setdefault(right, task) == task, "node task")
            adjacency[left].add(right)
            adjacency[right].add(left)
        unseen = set(adjacency)
        components: list[list[str]] = []
        while unseen:
            start = min(unseen)
            unseen.remove(start)
            stack = [start]
            nodes: list[str] = []
            while stack:
                node = stack.pop()
                nodes.append(node)
                fresh = adjacency[node] & unseen
                unseen.difference_update(fresh)
                stack.extend(sorted(fresh, reverse=True))
            components.append(sorted(nodes))
        node_component: dict[str, int] = {}
        for number, nodes in enumerate(components):
            for node in nodes:
                node_component[node] = number
        edges_by_component: dict[int, list[tuple[str, str]]] = defaultdict(list)
        for pair in sorted(pairs_by_task[task]):
            number = node_component[pair[0]]
            check(number == node_component[pair[1]], "component edge")
            edges_by_component[number].append(pair)
        local_rank = 0
        for number, nodes in enumerate(components):
            edges = edges_by_component[number]
            values = grounded_weights(nodes, edges)
            expected = len(nodes) - 1
            maximum_residual = max(maximum_residual, abs(sum(values) - expected))
            local_rank += expected
            vertices += len(nodes)
            component_count += 1
            if len(edges) == len(nodes) * (len(nodes) - 1) // 2:
                complete += 1
            else:
                incomplete += 1
            for pair, value in zip(edges, values):
                weights[(task, pair)] = value
                all_weights.append(value)
        rows_by_task[task] = len(pairs_by_task[task])
        rank_by_task[task] = local_rank
    rows = sum(rows_by_task.values())
    rank = sum(rank_by_task.values())
    check(rows == len(weights) == len(all_weights), "graph rows")
    check(vertices - component_count == rank, "graph rank")
    check(abs(sum(all_weights) - rank) <= TOLERANCE * rank, "global Foster")
    raw_task = {task: value / rows for task, value in rows_by_task.items()}
    rank_task = {task: value / rank for task, value in rank_by_task.items()}
    edge_tv = 0.5 * sum(abs(value / rank - 1.0 / rows) for value in all_weights)
    task_tv = 0.5 * sum(abs(raw_task[task] - rank_task[task]) for task in raw_task)
    ordered = sorted(all_weights)
    return weights, {
        "pair_rows": rows,
        "vertices": vertices,
        "tasks": len(rows_by_task),
        "connected_components": component_count,
        "complete_components": complete,
        "incomplete_components": incomplete,
        "endpoint_edge_incidence_rank": rank,
        "cycle_rows": rows - rank,
        "weight_sum_decimal_17g": dec(sum(all_weights)),
        "maximum_component_foster_residual_decimal_17g": dec(maximum_residual),
        "minimum_weight_decimal_17g": dec(ordered[0]),
        "median_weight_decimal_17g": dec(linear_quantile(ordered, 0.5)),
        "maximum_weight_decimal_17g": dec(ordered[-1]),
        "edge_distribution_total_variation_decimal_17g": dec(edge_tv),
        "task_weight_total_variation_decimal_17g": dec(task_tv),
        "raw_max_task_share_decimal_17g": dec(max(raw_task.values())),
        "rank_max_task_share_decimal_17g": dec(max(rank_task.values())),
        "unit_probability_bridge_edges": sum(value >= 1.0 - TOLERANCE for value in all_weights),
        "task_identities_emitted": False,
    }


def task_statistics(
    pairs_by_task: Mapping[str, Mapping[tuple[str, str], Mapping[str, float]]],
    weights: Mapping[tuple[str, tuple[str, str]], float],
    model: str,
) -> dict[str, dict[str, float]]:
    output: dict[str, dict[str, float]] = {}
    for task in sorted(pairs_by_task):
        raw: list[float] = []
        weighted: list[tuple[float, float]] = []
        for pair in sorted(pairs_by_task[task]):
            if model == "deepseek_minus_gpt":
                value = pairs_by_task[task][pair]["deepseek"] - pairs_by_task[task][pair]["gpt"]
            else:
                value = pairs_by_task[task][pair][model]
            weight = weights[(task, pair)]
            raw.append(value)
            weighted.append((weight, value))
        weight_sum = sum(weight for weight, _ in weighted)
        output[task] = {
            "rows": float(len(raw)),
            "rank": weight_sum,
            "raw_sum": sum(raw),
            "weighted_sum": sum(weight * value for weight, value in weighted),
            "raw_task": sum(raw) / len(raw),
            "weighted_task": sum(weight * value for weight, value in weighted) / weight_sum,
        }
    return output


def points(statistics: Mapping[str, Mapping[str, float]], tasks: list[str]) -> dict[str, float]:
    raw_pair = sum(statistics[task]["raw_sum"] for task in tasks) / sum(
        statistics[task]["rows"] for task in tasks
    )
    weighted_pair = sum(statistics[task]["weighted_sum"] for task in tasks) / sum(
        statistics[task]["rank"] for task in tasks
    )
    raw_task = sum(statistics[task]["raw_task"] for task in tasks) / len(tasks)
    weighted_task = sum(statistics[task]["weighted_task"] for task in tasks) / len(tasks)
    return {
        "raw_pair_micro": raw_pair,
        "ust_rank_micro": weighted_pair,
        "raw_task_macro": raw_task,
        "ust_task_macro": weighted_task,
        "ust_minus_raw_rank_micro": weighted_pair - raw_pair,
        "ust_minus_raw_task_macro": weighted_task - raw_task,
    }


def ci(values: list[float]) -> tuple[float, float]:
    check(len(values) >= 40, "draws")
    values.sort()
    return values[int(0.025 * len(values))], values[int(0.975 * len(values)) - 1]


def metric_summary(
    statistics: Mapping[str, Mapping[str, float]], repetitions: int, seed: int
) -> dict[str, Any]:
    tasks = sorted(statistics)
    central = points(statistics, tasks)
    draws = {name: [] for name in central}
    rng = random.Random(seed)
    for _ in range(repetitions):
        sample = [tasks[rng.randrange(len(tasks))] for _ in tasks]
        values = points(statistics, sample)
        for name in values:
            draws[name].append(values[name])
    output: dict[str, Any] = {}
    for name in sorted(central):
        low, high = ci(draws[name])
        output[name] = {
            "point_decimal_17g": dec(central[name]),
            "task_clustered_ci95": [dec(low), dec(high)],
        }
    output["leave_one_task_out"] = {}
    for name in sorted(central):
        values = [
            points(statistics, [task for task in tasks if task != omitted])[name]
            for omitted in tasks
        ]
        output["leave_one_task_out"][name] = {
            "minimum_decimal_17g": dec(min(values)),
            "maximum_decimal_17g": dec(max(values)),
            "positive_count": sum(value > SIGN_TOLERANCE for value in values),
            "total": len(values),
        }
    return output


def reproduction(
    model_support: Mapping[str, Mapping[str, Mapping[tuple[str, str], Mapping[str, Any]]]],
    model: str,
) -> dict[str, Any]:
    per_task: dict[str, list[float]] = {}
    for task in sorted(model_support[model]):
        per_task[task] = [
            float(model_support[model][task][pair]["accuracy"])
            for pair in sorted(model_support[model][task])
        ]
        check(per_task[task], "reproduction task")
    values = [value for task in sorted(per_task) for value in per_task[task]]
    return {
        "finite_directional_pairs": len(values),
        "tasks": len(per_task),
        "raw_pair_micro_decimal_17g": dec(sum(values) / len(values)),
        "raw_task_macro_decimal_17g": dec(
            sum(sum(task_values) / len(task_values) for task_values in per_task.values())
            / len(per_task)
        ),
    }


def reconstruct(
    manifest: Mapping[str, Any],
    rows: Iterable[Mapping[str, Any]],
    repetitions: int,
) -> tuple[dict[str, Any], set[str], set[str]]:
    sources, records, source_records, tasks, endpoints = load(manifest, rows)
    model_support, grid = support(sources, records)
    common_pairs = common(model_support)
    common_count = sum(len(value) for value in common_pairs.values())
    weights, graph_result = graph(common_pairs)
    expected = {
        "inputs": {
            "manifest_sha256": MANIFEST_SHA256,
            "master_sha256": MASTER_SHA256,
            "source_files": len(sources),
            "source_records": source_records,
        },
        "population": {
            "tasks": grid["tasks"],
            "deepseek_grid_pairs": grid["grid_counts"]["deepseek"],
            "gpt_grid_pairs": grid["grid_counts"]["gpt"],
            "cross_model_common_grid_pairs": grid["common_grid"],
            "deepseek_finite_directional_pairs": grid["finite_counts"]["deepseek"],
            "gpt_finite_directional_pairs": grid["finite_counts"]["gpt"],
            "common_finite_directional_pairs": common_count,
            "gpt_excluded_incomplete_triplicate_pairs": grid["excluded"]["gpt"],
            "confidence_values_read": False,
        },
        "source_grid_reproduction": {
            model: reproduction(model_support, model) for model in MODELS
        },
        "common_support_graph": graph_result,
        "common_support_metrics": {
            model: metric_summary(
                task_statistics(common_pairs, weights, model), repetitions, BOOTSTRAP_SEED
            )
            for model in MODELS
        },
        "paired_deepseek_minus_gpt": metric_summary(
            task_statistics(common_pairs, weights, "deepseek_minus_gpt"),
            repetitions,
            BOOTSTRAP_SEED + 1,
        ),
    }
    return expected, tasks, endpoints


def numeric_string(value: str) -> float | None:
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    return number if math.isfinite(number) else None


def compare(claimed: Any, expected: Any, label: str, differences: list[float]) -> None:
    if isinstance(expected, dict):
        check(isinstance(claimed, dict), f"{label} mapping")
        check(set(claimed) == set(expected), f"{label} keys")
        for key in sorted(expected):
            compare(claimed[key], expected[key], f"{label}.{key}", differences)
    elif isinstance(expected, list):
        check(isinstance(claimed, list) and len(claimed) == len(expected), f"{label} list")
        for index_value, (left, right) in enumerate(zip(claimed, expected)):
            compare(left, right, f"{label}[{index_value}]", differences)
    elif isinstance(expected, str) and numeric_string(expected) is not None:
        check(isinstance(claimed, str) and numeric_string(claimed) is not None, f"{label} number")
        left, right = float(claimed), float(expected)
        difference = abs(left - right)
        differences.append(difference)
        check(difference <= TOLERANCE * max(1.0, abs(right)), f"{label} drift")
    else:
        check(claimed == expected, f"{label} mismatch")


def read_rows(path: Path) -> Iterable[dict[str, Any]]:
    with path.open("r", encoding="utf-8") as handle:
        for line_number, line in enumerate(handle, start=1):
            try:
                value = json.loads(line)
            except json.JSONDecodeError as error:
                raise ValueError(f"bad JSONL line {line_number}") from error
            check(isinstance(value, dict), "master object")
            yield value


def write(path: Path, value: Mapping[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    descriptor = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    try:
        with os.fdopen(descriptor, "wb") as handle:
            handle.write(canonical(value))
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
    parser.add_argument("--claimed-result", type=Path, required=True)
    parser.add_argument("--claimed-result-sha256", required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    manifest_path = args.manifest.resolve()
    master_path = args.master.resolve()
    claimed_path = args.claimed_result.resolve()
    check(sha(manifest_path) == MANIFEST_SHA256, "manifest SHA")
    check(sha(master_path) == MASTER_SHA256, "master SHA")
    check(sha(claimed_path) == args.claimed_result_sha256, "claimed SHA")
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    claimed = json.loads(claimed_path.read_text(encoding="utf-8"))
    check(claimed.get("protocol") == "foreagent-ust-outcome-sensitivity-result-v1", "protocol")
    check(claimed.get("status") == "HISTORICAL_PUBLIC_OUTCOME_SENSITIVITY_COMPLETE", "status")
    check(
        claimed.get("classification") == "POSTDISCLOSURE_GRAPH_WEIGHTED_SENSITIVITY_COMPLETE",
        "classification",
    )
    expected, task_identities, endpoint_identities = reconstruct(
        manifest, read_rows(master_path), BOOTSTRAP_REPETITIONS
    )
    check(expected["inputs"]["source_files"] == EXPECTED_SOURCE_FILES, "source files")
    check(expected["inputs"]["source_records"] == EXPECTED_SOURCE_RECORDS, "source records")
    check(expected["population"]["tasks"] == EXPECTED_TASKS, "tasks")
    check(
        expected["population"]["common_finite_directional_pairs"]
        == EXPECTED_COMMON_FINITE_PAIRS,
        "common support",
    )
    differences: list[float] = []
    for key in expected:
        compare(claimed.get(key), expected[key], key, differences)
    serialized = json.dumps(claimed, sort_keys=True, ensure_ascii=False)
    check(not any(identity in serialized for identity in task_identities), "task identity emitted")
    check(not any(identity in serialized for identity in endpoint_identities), "endpoint identity emitted")
    check(claimed["scope"] == {
        "historical_public_scores_and_predictions_read": True,
        "fields_read": [
            "source_index", "task", "model_family", "release_run", "solution_paths",
            "scores", "is_lower_better", "groundtruth_best_index", "prediction_best_index",
        ],
        "confidence_values_read": False,
        "solution_code_read": False,
        "prospective_values_read": False,
        "raw_task_or_endpoint_identities_emitted": False,
        "gpu_paid_api_model_fit_base_update": "0/0/0/0",
    }, "scope")
    receipt = {
        "protocol": "foreagent-ust-outcome-sensitivity-independent-verification-v1",
        "status": "INDEPENDENT_GROUNDED_RECONSTRUCTION_EXACT_WITHIN_TOLERANCE",
        "claimed_result_sha256": args.claimed_result_sha256,
        "pairs": expected["population"]["common_finite_directional_pairs"],
        "tasks": expected["population"]["tasks"],
        "incidence_rank": expected["common_support_graph"]["endpoint_edge_incidence_rank"],
        "maximum_absolute_numeric_difference_decimal_17g": dec(max(differences, default=0.0)),
        "confidence_values_read": False,
        "prospective_values_read": False,
        "raw_identities_emitted": False,
        "gpu_paid_api_model_fit_base_update": "0/0/0/0",
    }
    write(args.output.resolve(), receipt)
    print(canonical({
        "status": receipt["status"],
        "output_sha256": sha(args.output.resolve()),
        "confidence_values_read": False,
        "prospective_values_read": False,
    }).decode(), end="")


if __name__ == "__main__":
    main()
