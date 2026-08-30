#!/usr/bin/env python3
"""Historical same-pool predictor sensitivity under UST edge weighting."""

from __future__ import annotations

import argparse
from collections import Counter, defaultdict
import hashlib
import json
import math
import os
from pathlib import Path
import random
from typing import Any, Iterable, Mapping

import numpy as np


STATIC_PAIR_SHA256 = "ec5a9afd37e9fbf21a4a1e89c29e9a0c771a75f0f2090b99a163711a59515acd"
TFIDF_PAIR_SHA256 = "021f8b3c74db89c6b770714edb879731799b145744af7b765005eed72f9ecde6"
STATIC_MODELS = (
    "code_len",
    "depth",
    "n_cv",
    "n_ensemble",
    "n_lines",
    "random_hash",
    "static_gbm_pooled",
    "static_gbm_task",
    "static_lr_pooled",
    "static_lr_task",
    "step",
)
PRIMARY_FULL_COVERAGE_MODELS = (
    "tfidf_lr",
    "static_lr_pooled",
    "static_gbm_pooled",
    "static_lr_task",
    "static_gbm_task",
)
FROZEN_CHAMPION = "static_gbm_task"
REFERENCE_MODEL = "tfidf_lr"
BOOTSTRAP_REPETITIONS = 20_000
TASK_BOOTSTRAP_SEED = 20260830
PARENT_BOOTSTRAP_SEED = 20260831
NUMERIC_TOLERANCE = 5e-9


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


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    with path.open(encoding="utf-8") as handle:
        for number, line in enumerate(handle, start=1):
            try:
                row = json.loads(line)
            except json.JSONDecodeError as error:
                raise ValueError(f"invalid JSON row {number}") from error
            require(isinstance(row, dict), f"row {number} object")
            rows.append(row)
    require(rows, "empty JSONL")
    return rows


def pair_key(row: Mapping[str, Any]) -> tuple[Any, ...]:
    return (
        row["index"], row["task"], row["parent"], row["semantics"],
        row["better"], row["worse"], row["better_run"], row["worse_run"],
    )


def validate_common_row(row: Mapping[str, Any], static: bool) -> None:
    expected = {
        "better", "better_run", "correct", "index", "margin", "parent", "semantics",
        "split", "task", "tie", "worse", "worse_run",
    }
    if static:
        expected |= {"abstain", "model"}
    require(set(row) == expected, "pair row schema")
    for key in ("better", "better_run", "parent", "semantics", "split", "task", "worse", "worse_run"):
        require(isinstance(row[key], str) and row[key], f"invalid {key}")
    require(isinstance(row["index"], int) and row["index"] >= 0, "invalid index")
    require(row["better"] != row["worse"], "self pair")
    require(isinstance(row["tie"], bool), "tie type")
    if static:
        require(isinstance(row["abstain"], bool), "abstain type")
        require(row["model"] in STATIC_MODELS, "unexpected static model")
    abstain = bool(row.get("abstain", False))
    if row["tie"] or abstain:
        require(row["correct"] is None, "tie or abstain correctness")
    else:
        require(isinstance(row["correct"], bool), "correctness type")
        require(isinstance(row["margin"], (int, float)) and math.isfinite(row["margin"]),
                "finite margin")


def load_predictions(
    static_path: Path, tfidf_path: Path
) -> tuple[dict[str, dict[tuple[Any, ...], dict[str, Any]]], dict[tuple[Any, ...], dict[str, Any]]]:
    static_by_model: dict[str, dict[tuple[Any, ...], dict[str, Any]]] = {
        model: {} for model in STATIC_MODELS
    }
    for row in read_jsonl(static_path):
        validate_common_row(row, static=True)
        if row["split"] != "test":
            continue
        key = pair_key(row)
        require(key not in static_by_model[row["model"]], "duplicate static model pair")
        static_by_model[row["model"]][key] = row
    supports = [set(rows) for rows in static_by_model.values()]
    require(all(len(rows) == 931 for rows in supports), "static test support size")
    require(all(support == supports[0] for support in supports[1:]), "static support drift")

    tfidf: dict[tuple[Any, ...], dict[str, Any]] = {}
    for row in read_jsonl(tfidf_path):
        validate_common_row(row, static=False)
        if row["split"] != "test":
            continue
        key = pair_key(row)
        require(key not in tfidf, "duplicate TF-IDF pair")
        tfidf[key] = row
    require(set(tfidf) == supports[0], "TF-IDF support mismatch")
    models = {**static_by_model, "tfidf_lr": tfidf}
    for model in PRIMARY_FULL_COVERAGE_MODELS:
        require(all(not row["tie"] and not row.get("abstain", False) for row in models[model].values()),
                f"primary model not full-coverage no-tie: {model}")
    return models, static_by_model[STATIC_MODELS[0]]


def component_weights(
    nodes: list[str], keyed_edges: list[tuple[tuple[Any, ...], str, str]]
) -> dict[tuple[Any, ...], float]:
    require(len(nodes) >= 2 and keyed_edges, "empty component")
    position = {node: index for index, node in enumerate(nodes)}
    laplacian = np.zeros((len(nodes), len(nodes)), dtype=np.float64)
    for _key, left, right in keyed_edges:
        i, j = position[left], position[right]
        laplacian[i, i] += 1.0
        laplacian[j, j] += 1.0
        laplacian[i, j] -= 1.0
        laplacian[j, i] -= 1.0
    eigenvalues, eigenvectors = np.linalg.eigh(laplacian)
    threshold = np.finfo(np.float64).eps * len(nodes) * max(1.0, float(eigenvalues[-1])) * 32.0
    require(abs(float(eigenvalues[0])) <= threshold and np.all(eigenvalues[1:] > threshold),
            "component Laplacian rank")
    positive = eigenvectors[:, 1:]
    pseudoinverse = (positive / eigenvalues[1:]) @ positive.T
    weights: dict[tuple[Any, ...], float] = {}
    for key, left, right in keyed_edges:
        i, j = position[left], position[right]
        value = float(pseudoinverse[i, i] + pseudoinverse[j, j] - 2.0 * pseudoinverse[i, j])
        require(value > 0.0 and value <= 1.0 + NUMERIC_TOLERANCE, "edge weight range")
        weights[key] = min(value, 1.0)
    require(abs(sum(weights.values()) - (len(nodes) - 1)) <= NUMERIC_TOLERANCE * (len(nodes) - 1),
            "component Foster identity")
    return weights


def build_weights(
    base: Mapping[tuple[Any, ...], Mapping[str, Any]]
) -> tuple[dict[tuple[Any, ...], float], dict[str, Any]]:
    contexts: dict[tuple[str, str], list[tuple[tuple[Any, ...], str, str]]] = defaultdict(list)
    for key, row in base.items():
        contexts[(row["task"], row["parent"])].append((key, row["better"], row["worse"]))
    weights: dict[tuple[Any, ...], float] = {}
    component_sizes: list[tuple[int, int]] = []
    task_raw: Counter[str] = Counter()
    task_rank: Counter[str] = Counter()
    parent_components = 0
    complete_components = 0
    for (task, _parent), edges in sorted(contexts.items()):
        adjacency: dict[str, set[str]] = defaultdict(set)
        unordered: set[tuple[str, str]] = set()
        for _key, left, right in edges:
            edge = tuple(sorted((left, right)))
            require(edge not in unordered, "duplicate unordered edge within parent")
            unordered.add(edge)
            adjacency[left].add(right)
            adjacency[right].add(left)
        unseen = set(adjacency)
        node_component: dict[str, int] = {}
        components: list[list[str]] = []
        while unseen:
            start = min(unseen)
            unseen.remove(start)
            stack = [start]
            nodes: list[str] = []
            while stack:
                node = stack.pop()
                nodes.append(node)
                new = adjacency[node] & unseen
                unseen.difference_update(new)
                stack.extend(sorted(new, reverse=True))
            number = len(components)
            nodes = sorted(nodes)
            components.append(nodes)
            for node in nodes:
                node_component[node] = number
        keyed_by_component: dict[int, list[tuple[tuple[Any, ...], str, str]]] = defaultdict(list)
        for keyed_edge in edges:
            number = node_component[keyed_edge[1]]
            require(number == node_component[keyed_edge[2]], "component edge mismatch")
            keyed_by_component[number].append(keyed_edge)
        for number, nodes in enumerate(components):
            local = keyed_by_component[number]
            local_weights = component_weights(nodes, local)
            require(not (set(weights) & set(local_weights)), "weight key duplicate")
            weights.update(local_weights)
            rank = len(nodes) - 1
            task_raw[task] += len(local)
            task_rank[task] += rank
            component_sizes.append((len(nodes), len(local)))
            parent_components += 1
            complete_components += len(local) == len(nodes) * (len(nodes) - 1) // 2
    require(set(weights) == set(base), "weight coverage")
    total_rank = sum(task_rank.values())
    require(abs(sum(weights.values()) - total_rank) <= NUMERIC_TOLERANCE * total_rank,
            "global Foster identity")
    raw_probability = {task: count / len(base) for task, count in task_raw.items()}
    rank_probability = {task: count / total_rank for task, count in task_rank.items()}
    task_tv = 0.5 * sum(abs(raw_probability[task] - rank_probability[task]) for task in task_raw)
    edge_tv = 0.5 * sum(abs(weight / total_rank - 1.0 / len(base)) for weight in weights.values())
    sorted_weights = sorted(weights.values())
    return weights, {
        "tasks": len(task_raw),
        "decision_parents": len(contexts),
        "connected_components": parent_components,
        "complete_components": complete_components,
        "incomplete_components": parent_components - complete_components,
        "endpoint_memberships": sum(nodes for nodes, _edges in component_sizes),
        "pair_rows": len(base),
        "incidence_rank": total_rank,
        "cycle_rows": len(base) - total_rank,
        "weight_sum_decimal_17g": decimal(sum(weights.values())),
        "minimum_weight_decimal_17g": decimal(sorted_weights[0]),
        "median_weight_decimal_17g": decimal(linear_quantile(sorted_weights, 0.5)),
        "maximum_weight_decimal_17g": decimal(sorted_weights[-1]),
        "edge_distribution_total_variation_decimal_17g": decimal(edge_tv),
        "task_weight_total_variation_decimal_17g": decimal(task_tv),
        "raw_max_task_share_decimal_17g": decimal(max(raw_probability.values())),
        "rank_max_task_share_decimal_17g": decimal(max(rank_probability.values())),
        "task_identities_emitted": False,
    }


def linear_quantile(sorted_values: list[float], fraction: float) -> float:
    position = fraction * (len(sorted_values) - 1)
    lower, upper = int(math.floor(position)), int(math.ceil(position))
    if lower == upper:
        return sorted_values[lower]
    weight = position - lower
    return sorted_values[lower] * (1.0 - weight) + sorted_values[upper] * weight


def credit(row: Mapping[str, Any]) -> float:
    if row["tie"] or row.get("abstain", False):
        return 0.5
    return float(row["correct"])


def bootstrap_ci(values: Mapping[Any, float], seed: int) -> tuple[float, float]:
    keys = sorted(values, key=str)
    require(keys, "empty bootstrap")
    require(BOOTSTRAP_REPETITIONS >= 40, "bootstrap repetitions")
    rng = random.Random(seed)
    draws: list[float] = []
    for _ in range(BOOTSTRAP_REPETITIONS):
        draws.append(sum(values[rng.choice(keys)] for _ in keys) / len(keys))
    draws.sort()
    lower_index = int(0.025 * BOOTSTRAP_REPETITIONS)
    upper_index = int(0.975 * BOOTSTRAP_REPETITIONS) - 1
    return draws[lower_index], draws[upper_index]


def model_metrics(
    rows: Mapping[tuple[Any, ...], Mapping[str, Any]],
    weights: Mapping[tuple[Any, ...], float],
) -> tuple[
    dict[str, Any], dict[str, float], dict[str, float], dict[tuple[str, str], float]
]:
    raw_by_task: dict[str, list[float]] = defaultdict(list)
    raw_by_parent: dict[tuple[str, str], list[float]] = defaultdict(list)
    weighted_by_task: dict[str, list[tuple[float, float]]] = defaultdict(list)
    weighted_by_parent: dict[tuple[str, str], list[tuple[float, float]]] = defaultdict(list)
    credits: list[float] = []
    ties = abstentions = 0
    for key, row in rows.items():
        value = credit(row)
        weight = weights[key]
        parent = (row["task"], row["parent"])
        credits.append(value)
        raw_by_task[row["task"]].append(value)
        raw_by_parent[parent].append(value)
        weighted_by_task[row["task"]].append((weight, value))
        weighted_by_parent[parent].append((weight, value))
        ties += bool(row["tie"])
        abstentions += bool(row.get("abstain", False))
    raw_task = {task: sum(values) / len(values) for task, values in raw_by_task.items()}
    raw_parent = {parent: sum(values) / len(values) for parent, values in raw_by_parent.items()}
    ust_task = {
        task: sum(weight * value for weight, value in values) / sum(weight for weight, _ in values)
        for task, values in weighted_by_task.items()
    }
    ust_parent = {
        parent: sum(weight * value for weight, value in values) / sum(weight for weight, _ in values)
        for parent, values in weighted_by_parent.items()
    }
    raw_parent_by_task: dict[str, list[float]] = defaultdict(list)
    ust_parent_by_task: dict[str, list[float]] = defaultdict(list)
    for (task, _parent), value in raw_parent.items():
        raw_parent_by_task[task].append(value)
    for (task, _parent), value in ust_parent.items():
        ust_parent_by_task[task].append(value)
    raw_task_parent = {
        task: sum(values) / len(values) for task, values in raw_parent_by_task.items()
    }
    ust_task_parent = {
        task: sum(values) / len(values) for task, values in ust_parent_by_task.items()
    }
    task_ci = bootstrap_ci(ust_task, TASK_BOOTSTRAP_SEED)
    task_parent_ci = bootstrap_ci(ust_task_parent, TASK_BOOTSTRAP_SEED)
    parent_ci = bootstrap_ci(ust_parent, PARENT_BOOTSTRAP_SEED)
    task_shift = {task: ust_task[task] - raw_task[task] for task in ust_task}
    task_parent_shift = {
        task: ust_task_parent[task] - raw_task_parent[task] for task in ust_task_parent
    }
    parent_shift = {parent: ust_parent[parent] - raw_parent[parent] for parent in ust_parent}
    task_shift_ci = bootstrap_ci(task_shift, TASK_BOOTSTRAP_SEED)
    task_parent_shift_ci = bootstrap_ci(task_parent_shift, TASK_BOOTSTRAP_SEED)
    parent_shift_ci = bootstrap_ci(parent_shift, PARENT_BOOTSTRAP_SEED)
    result = {
        "pairs": len(rows),
        "tasks": len(ust_task),
        "parents": len(ust_parent),
        "ties": ties,
        "abstentions": abstentions,
        "neutral_credit_policy_for_tie_or_abstain": 0.5,
        "raw_pair_micro_accuracy_decimal_17g": decimal(sum(credits) / len(credits)),
        "raw_task_macro_accuracy_decimal_17g": decimal(sum(raw_task.values()) / len(raw_task)),
        "raw_task_parent_macro_accuracy_decimal_17g": decimal(
            sum(raw_task_parent.values()) / len(raw_task_parent)
        ),
        "raw_parent_macro_accuracy_decimal_17g": decimal(sum(raw_parent.values()) / len(raw_parent)),
        "ust_pair_micro_accuracy_decimal_17g": decimal(
            sum(weights[key] * credit(rows[key]) for key in rows) / sum(weights.values())
        ),
        "ust_task_macro_accuracy_decimal_17g": decimal(sum(ust_task.values()) / len(ust_task)),
        "ust_task_clustered_ci95": [decimal(task_ci[0]), decimal(task_ci[1])],
        "ust_task_parent_macro_accuracy_decimal_17g": decimal(
            sum(ust_task_parent.values()) / len(ust_task_parent)
        ),
        "ust_task_parent_clustered_ci95": [
            decimal(task_parent_ci[0]), decimal(task_parent_ci[1])
        ],
        "ust_parent_macro_accuracy_decimal_17g": decimal(sum(ust_parent.values()) / len(ust_parent)),
        "ust_parent_clustered_ci95": [decimal(parent_ci[0]), decimal(parent_ci[1])],
        "ust_minus_raw_task_macro_decimal_17g": decimal(
            sum(ust_task.values()) / len(ust_task) - sum(raw_task.values()) / len(raw_task)
        ),
        "ust_minus_raw_task_macro_clustered_ci95": [
            decimal(task_shift_ci[0]), decimal(task_shift_ci[1])
        ],
        "ust_minus_raw_task_parent_macro_decimal_17g": decimal(
            sum(ust_task_parent.values()) / len(ust_task_parent)
            - sum(raw_task_parent.values()) / len(raw_task_parent)
        ),
        "ust_minus_raw_task_parent_macro_clustered_ci95": [
            decimal(task_parent_shift_ci[0]), decimal(task_parent_shift_ci[1])
        ],
        "ust_minus_raw_parent_macro_decimal_17g": decimal(
            sum(ust_parent.values()) / len(ust_parent) - sum(raw_parent.values()) / len(raw_parent)
        ),
        "ust_minus_raw_parent_macro_clustered_ci95": [
            decimal(parent_shift_ci[0]), decimal(parent_shift_ci[1])
        ],
    }
    return result, ust_task, ust_task_parent, ust_parent


def paired_summary(
    candidate: Mapping[Any, float], reference: Mapping[Any, float], seed: int
) -> dict[str, Any]:
    require(set(candidate) == set(reference), "paired support")
    differences = {key: candidate[key] - reference[key] for key in candidate}
    ci = bootstrap_ci(differences, seed)
    point = sum(differences.values()) / len(differences)
    return {
        "clusters": len(differences),
        "point_decimal_17g": decimal(point),
        "ci95": [decimal(ci[0]), decimal(ci[1])],
    }


def ordering(values: Mapping[str, float], names: Iterable[str]) -> list[str]:
    return sorted(names, key=lambda name: (-values[name], name))


def discordant_pairs(left: list[str], right: list[str]) -> int:
    require(set(left) == set(right), "ordering support")
    left_position = {name: index for index, name in enumerate(left)}
    right_position = {name: index for index, name in enumerate(right)}
    count = 0
    for i, first in enumerate(left):
        for second in left[i + 1:]:
            count += (left_position[first] - left_position[second]) * (
                right_position[first] - right_position[second]
            ) < 0
    return count


def analyze(static_path: Path, tfidf_path: Path) -> dict[str, Any]:
    require(file_sha(static_path) == STATIC_PAIR_SHA256, "static pair SHA")
    require(file_sha(tfidf_path) == TFIDF_PAIR_SHA256, "TF-IDF pair SHA")
    models, base = load_predictions(static_path, tfidf_path)
    weights, graph = build_weights(base)
    metrics: dict[str, dict[str, Any]] = {}
    task_values: dict[str, dict[str, float]] = {}
    task_parent_values: dict[str, dict[str, float]] = {}
    parent_values: dict[str, dict[tuple[str, str], float]] = {}
    for model in sorted(models):
        (
            metrics[model], task_values[model], task_parent_values[model], parent_values[model]
        ) = model_metrics(models[model], weights)
    for model in sorted(models):
        metrics[model]["paired_ust_task_delta_vs_tfidf"] = paired_summary(
            task_values[model], task_values[REFERENCE_MODEL], TASK_BOOTSTRAP_SEED
        )
        metrics[model]["paired_ust_parent_delta_vs_tfidf"] = paired_summary(
            parent_values[model], parent_values[REFERENCE_MODEL], PARENT_BOOTSTRAP_SEED
        )
        metrics[model]["paired_ust_task_parent_delta_vs_tfidf"] = paired_summary(
            task_parent_values[model], task_parent_values[REFERENCE_MODEL], TASK_BOOTSTRAP_SEED
        )

    raw_headline_points = {
        name: float(value["raw_task_parent_macro_accuracy_decimal_17g"])
        for name, value in metrics.items()
    }
    ust_headline_points = {
        name: float(value["ust_task_parent_macro_accuracy_decimal_17g"])
        for name, value in metrics.items()
    }
    raw_task_points = {
        name: float(value["raw_task_macro_accuracy_decimal_17g"]) for name, value in metrics.items()
    }
    ust_task_points = {
        name: float(value["ust_task_macro_accuracy_decimal_17g"]) for name, value in metrics.items()
    }
    all_names = sorted(models)
    raw_all_order = ordering(raw_headline_points, all_names)
    ust_all_order = ordering(ust_headline_points, all_names)
    raw_primary_order = ordering(raw_headline_points, PRIMARY_FULL_COVERAGE_MODELS)
    ust_primary_order = ordering(ust_headline_points, PRIMARY_FULL_COVERAGE_MODELS)
    raw_task_all_order = ordering(raw_task_points, all_names)
    ust_task_all_order = ordering(ust_task_points, all_names)
    raw_task_primary_order = ordering(raw_task_points, PRIMARY_FULL_COVERAGE_MODELS)
    ust_task_primary_order = ordering(ust_task_points, PRIMARY_FULL_COVERAGE_MODELS)
    champion_task_delta = {
        task: task_parent_values[FROZEN_CHAMPION][task] - task_parent_values[REFERENCE_MODEL][task]
        for task in task_parent_values[FROZEN_CHAMPION]
    }
    loto = [
        sum(value for task, value in champion_task_delta.items() if task != dropped)
        / (len(champion_task_delta) - 1)
        for dropped in champion_task_delta
    ]
    primary = metrics[FROZEN_CHAMPION]
    task_delta = primary["paired_ust_task_delta_vs_tfidf"]
    task_parent_delta = primary["paired_ust_task_parent_delta_vs_tfidf"]
    parent_delta = primary["paired_ust_parent_delta_vs_tfidf"]
    return {
        "protocol": "historical-ust-predictor-sensitivity-result-v2",
        "status": "HISTORICAL_SENSITIVITY_COMPLETE",
        "classification": "HISTORICAL_UST_PREDICTOR_SENSITIVITY_AUDIT_COMPLETE",
        "inputs": {
            "static_per_pair_sha256": STATIC_PAIR_SHA256,
            "tfidf_per_pair_sha256": TFIDF_PAIR_SHA256,
        },
        "population": {
            "split": "test",
            "pairs": 931,
            "models": len(models),
            "primary_full_coverage_models": list(PRIMARY_FULL_COVERAGE_MODELS),
            "dev_selected_champion_fixed_before_analysis": FROZEN_CHAMPION,
            "reference_fixed_before_analysis": REFERENCE_MODEL,
            "support_exact_across_all_models": True,
        },
        "pair_graph": graph,
        "models": metrics,
        "ranking_sensitivity": {
            "headline_all_models_raw_task_parent_macro_order": raw_all_order,
            "headline_all_models_ust_task_parent_macro_order": ust_all_order,
            "headline_all_models_discordant_pairs": discordant_pairs(raw_all_order, ust_all_order),
            "headline_primary_models_raw_task_parent_macro_order": raw_primary_order,
            "headline_primary_models_ust_task_parent_macro_order": ust_primary_order,
            "headline_primary_models_discordant_pairs": discordant_pairs(
                raw_primary_order, ust_primary_order
            ),
            "sensitivity_all_models_raw_task_pair_macro_order": raw_task_all_order,
            "sensitivity_all_models_ust_task_pair_macro_order": ust_task_all_order,
            "sensitivity_all_models_discordant_pairs": discordant_pairs(
                raw_task_all_order, ust_task_all_order
            ),
            "sensitivity_primary_models_raw_task_pair_macro_order": raw_task_primary_order,
            "sensitivity_primary_models_ust_task_pair_macro_order": ust_task_primary_order,
            "sensitivity_primary_models_discordant_pairs": discordant_pairs(
                raw_task_primary_order, ust_task_primary_order
            ),
            "frozen_champion_reselection_performed": False,
        },
        "frozen_champion_summary": {
            "model": FROZEN_CHAMPION,
            "reference": REFERENCE_MODEL,
            "headline_ust_task_parent_macro_accuracy_decimal_17g": primary[
                "ust_task_parent_macro_accuracy_decimal_17g"
            ],
            "headline_ust_task_parent_clustered_ci95": primary[
                "ust_task_parent_clustered_ci95"
            ],
            "headline_ust_minus_raw_task_parent_macro_decimal_17g": primary[
                "ust_minus_raw_task_parent_macro_decimal_17g"
            ],
            "headline_ust_minus_raw_task_parent_macro_clustered_ci95": primary[
                "ust_minus_raw_task_parent_macro_clustered_ci95"
            ],
            "headline_paired_ust_task_parent_delta": task_parent_delta,
            "ust_task_macro_accuracy_decimal_17g": primary["ust_task_macro_accuracy_decimal_17g"],
            "ust_task_clustered_ci95": primary["ust_task_clustered_ci95"],
            "ust_minus_raw_task_macro_decimal_17g": primary[
                "ust_minus_raw_task_macro_decimal_17g"
            ],
            "ust_minus_raw_task_macro_clustered_ci95": primary[
                "ust_minus_raw_task_macro_clustered_ci95"
            ],
            "ust_minus_raw_parent_macro_decimal_17g": primary[
                "ust_minus_raw_parent_macro_decimal_17g"
            ],
            "ust_minus_raw_parent_macro_clustered_ci95": primary[
                "ust_minus_raw_parent_macro_clustered_ci95"
            ],
            "paired_ust_task_delta": task_delta,
            "paired_ust_parent_delta": parent_delta,
            "leave_one_task_out_task_delta_min_decimal_17g": decimal(min(loto)),
            "leave_one_task_out_task_delta_max_decimal_17g": decimal(max(loto)),
            "leave_one_task_out_positive_count": sum(value > 0.0 for value in loto),
            "leave_one_task_out_total": len(loto),
            "headline_chance_supported_task_ci_lower_above_half": (
                float(primary["ust_task_parent_clustered_ci95"][0]) > 0.5
            ),
            "headline_advantage_over_tfidf_supported_task_ci_lower_above_zero": (
                float(task_parent_delta["ci95"][0]) > 0.0
            ),
            "sensitivity_advantage_over_tfidf_supported_task_pair_ci_lower_above_zero": (
                float(task_delta["ci95"][0]) > 0.0
            ),
            "advantage_over_tfidf_supported_parent_ci_lower_above_zero": float(parent_delta["ci95"][0]) > 0.0,
            "headline_ust_weighting_changes_task_parent_macro_supported_ci_excludes_zero": (
                float(primary["ust_minus_raw_task_parent_macro_clustered_ci95"][0]) > 0.0
                or float(primary["ust_minus_raw_task_parent_macro_clustered_ci95"][1]) < 0.0
            ),
            "sensitivity_ust_weighting_changes_task_pair_macro_supported_ci_excludes_zero": (
                float(primary["ust_minus_raw_task_macro_clustered_ci95"][0]) > 0.0
                or float(primary["ust_minus_raw_task_macro_clustered_ci95"][1]) < 0.0
            ),
            "ust_weighting_changes_parent_macro_supported_ci_excludes_zero": (
                float(primary["ust_minus_raw_parent_macro_clustered_ci95"][0]) > 0.0
                or float(primary["ust_minus_raw_parent_macro_clustered_ci95"][1]) < 0.0
            ),
        },
        "interpretation_boundary": {
            "historical_postdisclosure_sensitivity_only": True,
            "not_a_new_champion_selection": True,
            "not_prospective_confirmation": True,
            "not_effective_sample_size": True,
            "not_independent_labels": True,
            "no_search_utility_claim": True,
        },
        "scope": {
            "historical_revealed_prediction_outcomes_read": True,
            "prospective_values_read": False,
            "model_fit": False,
            "gpu_paid_api_base_update": "0/0/0",
            "raw_pair_task_parent_endpoint_identities_emitted": False,
        },
    }


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
    parser.add_argument("--static-per-pair", type=Path, required=True)
    parser.add_argument("--tfidf-per-pair", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    result = analyze(args.static_per_pair.resolve(), args.tfidf_per_pair.resolve())
    write_exclusive(args.output.resolve(), result)
    print(canonical_bytes({
        "status": result["status"],
        "classification": result["classification"],
        "output_sha256": file_sha(args.output.resolve()),
        "prospective_values_read": False,
    }).decode(), end="")


if __name__ == "__main__":
    main()
