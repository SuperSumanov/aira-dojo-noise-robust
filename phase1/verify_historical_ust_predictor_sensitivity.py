#!/usr/bin/env python3
"""Independent grounded-Laplacian verification of historical UST sensitivity."""

from __future__ import annotations

import argparse
from collections import Counter, defaultdict
import hashlib
import json
import math
import os
from pathlib import Path
import random
from typing import Any, Mapping

import numpy as np


STATIC_SHA = "ec5a9afd37e9fbf21a4a1e89c29e9a0c771a75f0f2090b99a163711a59515acd"
TFIDF_SHA = "021f8b3c74db89c6b770714edb879731799b145744af7b765005eed72f9ecde6"
STATIC_MODELS = {
    "code_len", "depth", "n_cv", "n_ensemble", "n_lines", "random_hash",
    "static_gbm_pooled", "static_gbm_task", "static_lr_pooled", "static_lr_task", "step",
}
PRIMARY = (
    "tfidf_lr", "static_lr_pooled", "static_gbm_pooled", "static_lr_task", "static_gbm_task",
)
CHAMPION = "static_gbm_task"
REFERENCE = "tfidf_lr"
REPETITIONS = 20_000
TASK_SEED = 20260830
PARENT_SEED = 20260831
TOLERANCE = 2e-8


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


def rows(path: Path) -> list[dict[str, Any]]:
    result = []
    with path.open(encoding="utf-8") as handle:
        for line in handle:
            value = json.loads(line)
            check(isinstance(value, dict), "row object")
            result.append(value)
    check(result, "empty input")
    return result


def exact_keys(value: Mapping[str, Any], expected: set[str], label: str) -> None:
    check(set(value) == expected, f"{label} schema")


def validate_input_row(row: Mapping[str, Any], static: bool) -> None:
    expected = {
        "better", "better_run", "correct", "index", "margin", "parent", "semantics",
        "split", "task", "tie", "worse", "worse_run",
    }
    if static:
        expected |= {"abstain", "model"}
    exact_keys(row, expected, "input row")
    for name in ("better", "better_run", "parent", "semantics", "split", "task", "worse", "worse_run"):
        check(isinstance(row[name], str) and bool(row[name]), f"input {name}")
    check(isinstance(row["index"], int) and row["index"] >= 0, "input index")
    check(row["better"] != row["worse"], "input self pair")
    check(isinstance(row["tie"], bool), "input tie")
    if static:
        check(isinstance(row["abstain"], bool), "input abstain")
        check(row["model"] in STATIC_MODELS, "input model")
    neutral = row["tie"] or bool(row.get("abstain", False))
    if neutral:
        check(row["correct"] is None, "neutral correctness")
    else:
        check(isinstance(row["correct"], bool), "input correctness")
        check(isinstance(row["margin"], (int, float)) and math.isfinite(row["margin"]),
              "input margin")


def key(row: Mapping[str, Any]) -> tuple[Any, ...]:
    return (
        row["index"], row["task"], row["parent"], row["semantics"], row["better"],
        row["worse"], row["better_run"], row["worse_run"],
    )


def load(static_path: Path, tfidf_path: Path) -> tuple[dict[str, dict[tuple[Any, ...], dict]], dict]:
    static: dict[str, dict[tuple[Any, ...], dict]] = {name: {} for name in STATIC_MODELS}
    for row in rows(static_path):
        validate_input_row(row, static=True)
        check(row.get("model") in STATIC_MODELS, "static model")
        if row.get("split") != "test":
            continue
        item_key = key(row)
        check(item_key not in static[row["model"]], "duplicate static")
        static[row["model"]][item_key] = row
    support = set(next(iter(static.values())))
    check(len(support) == 931, "support size")
    check(all(set(value) == support for value in static.values()), "static support")
    tfidf: dict[tuple[Any, ...], dict] = {}
    for row in rows(tfidf_path):
        validate_input_row(row, static=False)
        if row.get("split") != "test":
            continue
        item_key = key(row)
        check(item_key not in tfidf, "duplicate tfidf")
        tfidf[item_key] = row
    check(set(tfidf) == support, "tfidf support")
    models = {**static, "tfidf_lr": tfidf}
    for name in PRIMARY:
        check(all(not row["tie"] and not row.get("abstain", False) for row in models[name].values()),
              "primary coverage")
    return models, next(iter(static.values()))


def grounded_weights(nodes: list[str], edges: list[tuple[tuple[Any, ...], str, str]]) -> dict:
    position = {node: index for index, node in enumerate(nodes)}
    laplacian = np.zeros((len(nodes), len(nodes)), dtype=np.float64)
    for _item_key, left, right in edges:
        i, j = position[left], position[right]
        laplacian[i, i] += 1.0
        laplacian[j, j] += 1.0
        laplacian[i, j] -= 1.0
        laplacian[j, i] -= 1.0
    ground = len(nodes) - 1
    inverse = np.linalg.inv(laplacian[:ground, :ground])
    result = {}
    for item_key, left, right in edges:
        i, j = position[left], position[right]
        if i == ground:
            value = float(inverse[j, j])
        elif j == ground:
            value = float(inverse[i, i])
        else:
            value = float(inverse[i, i] + inverse[j, j] - 2.0 * inverse[i, j])
        check(value > 0.0 and value <= 1.0 + TOLERANCE, "weight range")
        result[item_key] = min(value, 1.0)
    check(abs(sum(result.values()) - (len(nodes) - 1)) <= TOLERANCE * (len(nodes) - 1),
          "Foster component")
    return result


def graph_weights(base: Mapping[tuple[Any, ...], Mapping[str, Any]]) -> tuple[dict, dict]:
    contexts: dict[tuple[str, str], list[tuple[tuple[Any, ...], str, str]]] = defaultdict(list)
    for item_key, row in base.items():
        contexts[(row["task"], row["parent"])].append((item_key, row["better"], row["worse"]))
    result = {}
    raw_task: Counter[str] = Counter()
    rank_task: Counter[str] = Counter()
    components_count = complete = endpoint_memberships = 0
    for (task, _parent), context_edges in sorted(contexts.items()):
        adjacency: dict[str, set[str]] = defaultdict(set)
        observed = set()
        for _item_key, left, right in context_edges:
            edge = tuple(sorted((left, right)))
            check(edge not in observed, "duplicate edge")
            observed.add(edge)
            adjacency[left].add(right)
            adjacency[right].add(left)
        unseen = set(adjacency)
        components = []
        node_number = {}
        while unseen:
            start = min(unseen)
            unseen.remove(start)
            stack = [start]
            members = []
            while stack:
                node = stack.pop()
                members.append(node)
                new = adjacency[node] & unseen
                unseen.difference_update(new)
                stack.extend(sorted(new, reverse=True))
            number = len(components)
            members = sorted(members)
            components.append(members)
            for node in members:
                node_number[node] = number
        grouped: dict[int, list] = defaultdict(list)
        for edge in context_edges:
            number = node_number[edge[1]]
            check(number == node_number[edge[2]], "component")
            grouped[number].append(edge)
        for number, members in enumerate(components):
            local = grounded_weights(members, grouped[number])
            check(not (set(result) & set(local)), "duplicate weight")
            result.update(local)
            rank = len(members) - 1
            raw_task[task] += len(grouped[number])
            rank_task[task] += rank
            components_count += 1
            endpoint_memberships += len(members)
            complete += len(grouped[number]) == len(members) * (len(members) - 1) // 2
    check(set(result) == set(base), "weight coverage")
    total_rank = sum(rank_task.values())
    check(abs(sum(result.values()) - total_rank) <= TOLERANCE * total_rank, "Foster global")
    sorted_weights = sorted(result.values())
    middle = len(sorted_weights) // 2
    median = sorted_weights[middle] if len(sorted_weights) % 2 else (
        sorted_weights[middle - 1] + sorted_weights[middle]
    ) / 2.0
    raw_distribution = {name: count / len(base) for name, count in raw_task.items()}
    rank_distribution = {name: count / total_rank for name, count in rank_task.items()}
    return result, {
        "tasks": len(raw_task),
        "decision_parents": len(contexts),
        "connected_components": components_count,
        "complete_components": complete,
        "incomplete_components": components_count - complete,
        "endpoint_memberships": endpoint_memberships,
        "pair_rows": len(base),
        "incidence_rank": total_rank,
        "cycle_rows": len(base) - total_rank,
        "weight_sum": sum(result.values()),
        "minimum_weight": sorted_weights[0],
        "median_weight": median,
        "maximum_weight": sorted_weights[-1],
        "edge_tv": 0.5 * sum(abs(value / total_rank - 1.0 / len(base)) for value in result.values()),
        "task_tv": 0.5 * sum(
            abs(raw_distribution[name] - rank_distribution[name]) for name in raw_distribution
        ),
        "raw_max_task": max(raw_distribution.values()),
        "rank_max_task": max(rank_distribution.values()),
    }


def neutral_credit(row: Mapping[str, Any]) -> float:
    return 0.5 if row["tie"] or row.get("abstain", False) else float(row["correct"])


def ci(values: Mapping[Any, float], seed: int) -> tuple[float, float]:
    keys = sorted(values, key=str)
    check(keys and REPETITIONS >= 40, "bootstrap input")
    generator = random.Random(seed)
    draws = [
        sum(values[generator.choice(keys)] for _ in keys) / len(keys)
        for _ in range(REPETITIONS)
    ]
    draws.sort()
    return draws[int(0.025 * REPETITIONS)], draws[int(0.975 * REPETITIONS) - 1]


def aggregate(model_rows: Mapping, weights: Mapping) -> tuple[dict, dict, dict]:
    raw_task = defaultdict(list)
    raw_parent = defaultdict(list)
    weighted_task = defaultdict(list)
    weighted_parent = defaultdict(list)
    all_credits = []
    for item_key, row in model_rows.items():
        value = neutral_credit(row)
        weight = weights[item_key]
        parent = (row["task"], row["parent"])
        all_credits.append(value)
        raw_task[row["task"]].append(value)
        raw_parent[parent].append(value)
        weighted_task[row["task"]].append((weight, value))
        weighted_parent[parent].append((weight, value))
    raw_task_points = {name: sum(values) / len(values) for name, values in raw_task.items()}
    raw_parent_points = {name: sum(values) / len(values) for name, values in raw_parent.items()}
    task_points = {
        name: sum(w * value for w, value in values) / sum(w for w, _value in values)
        for name, values in weighted_task.items()
    }
    parent_points = {
        name: sum(w * value for w, value in values) / sum(w for w, _value in values)
        for name, values in weighted_parent.items()
    }
    task_ci = ci(task_points, TASK_SEED)
    parent_ci = ci(parent_points, PARENT_SEED)
    task_shift = {name: task_points[name] - raw_task_points[name] for name in task_points}
    parent_shift = {name: parent_points[name] - raw_parent_points[name] for name in parent_points}
    return {
        "pairs": len(model_rows),
        "tasks": len(task_points),
        "parents": len(parent_points),
        "ties": sum(row["tie"] for row in model_rows.values()),
        "abstentions": sum(row.get("abstain", False) for row in model_rows.values()),
        "raw_micro": sum(all_credits) / len(all_credits),
        "raw_task": sum(raw_task_points.values()) / len(raw_task_points),
        "raw_parent": sum(raw_parent_points.values()) / len(raw_parent_points),
        "ust_micro": sum(weights[item_key] * neutral_credit(row) for item_key, row in model_rows.items())
        / sum(weights.values()),
        "ust_task": sum(task_points.values()) / len(task_points),
        "ust_task_ci": task_ci,
        "ust_parent": sum(parent_points.values()) / len(parent_points),
        "ust_parent_ci": parent_ci,
        "task_shift": sum(task_shift.values()) / len(task_shift),
        "task_shift_ci": ci(task_shift, TASK_SEED),
        "parent_shift": sum(parent_shift.values()) / len(parent_shift),
        "parent_shift_ci": ci(parent_shift, PARENT_SEED),
    }, task_points, parent_points


def paired(candidate: Mapping, reference: Mapping, seed: int) -> tuple[float, tuple[float, float]]:
    check(set(candidate) == set(reference), "paired support")
    differences = {name: candidate[name] - reference[name] for name in candidate}
    return sum(differences.values()) / len(differences), ci(differences, seed)


def close(value: Any, expected: float, label: str, differences: list[float]) -> None:
    check(isinstance(value, str), f"{label} type")
    observed = float(value)
    difference = abs(observed - expected)
    differences.append(difference)
    check(difference <= TOLERANCE * max(1.0, abs(expected)), f"{label} drift")


def discordance(left: list[str], right: list[str]) -> int:
    check(set(left) == set(right), "ranking support")
    right_position = {name: index for index, name in enumerate(right)}
    return sum(
        right_position[first] > right_position[second]
        for index, first in enumerate(left)
        for second in left[index + 1:]
    )


def all_strings(value: Any) -> list[str]:
    if isinstance(value, str):
        return [value]
    if isinstance(value, Mapping):
        return [item for key, child in value.items() for item in [str(key), *all_strings(child)]]
    if isinstance(value, list):
        return [item for child in value for item in all_strings(child)]
    return []


def verify(claimed: Mapping[str, Any], static_path: Path, tfidf_path: Path) -> dict[str, Any]:
    exact_keys(claimed, {
        "protocol", "status", "classification", "inputs", "population", "pair_graph",
        "models", "ranking_sensitivity", "frozen_champion_summary",
        "interpretation_boundary", "scope",
    }, "claimed result")
    check(claimed["protocol"] == "historical-ust-predictor-sensitivity-result-v1", "protocol")
    check(claimed["status"] == "HISTORICAL_SENSITIVITY_COMPLETE", "status")
    check(claimed["classification"] == "HISTORICAL_UST_PREDICTOR_SENSITIVITY_AUDIT_COMPLETE",
          "classification")
    check(sha(static_path) == STATIC_SHA and sha(tfidf_path) == TFIDF_SHA, "input SHA")
    models, base = load(static_path, tfidf_path)
    check(claimed["inputs"] == {
        "static_per_pair_sha256": STATIC_SHA,
        "tfidf_per_pair_sha256": TFIDF_SHA,
    }, "claimed inputs")
    check(claimed["population"] == {
        "split": "test",
        "pairs": 931,
        "models": 12,
        "primary_full_coverage_models": list(PRIMARY),
        "dev_selected_champion_fixed_before_analysis": CHAMPION,
        "reference_fixed_before_analysis": REFERENCE,
        "support_exact_across_all_models": True,
    }, "population")
    weights, graph = graph_weights(base)
    differences: list[float] = []
    claimed_graph = claimed["pair_graph"]
    exact_keys(claimed_graph, {
        "tasks", "decision_parents", "connected_components", "complete_components",
        "incomplete_components", "endpoint_memberships", "pair_rows", "incidence_rank",
        "cycle_rows", "weight_sum_decimal_17g", "minimum_weight_decimal_17g",
        "median_weight_decimal_17g", "maximum_weight_decimal_17g",
        "edge_distribution_total_variation_decimal_17g",
        "task_weight_total_variation_decimal_17g", "raw_max_task_share_decimal_17g",
        "rank_max_task_share_decimal_17g", "task_identities_emitted",
    }, "pair graph")
    for field in (
        "tasks", "decision_parents", "connected_components", "complete_components", "incomplete_components",
        "endpoint_memberships", "pair_rows", "incidence_rank", "cycle_rows",
    ):
        check(claimed_graph[field] == graph[field], f"graph {field}")
    for field, expected in (
        ("weight_sum_decimal_17g", graph["weight_sum"]),
        ("minimum_weight_decimal_17g", graph["minimum_weight"]),
        ("median_weight_decimal_17g", graph["median_weight"]),
        ("maximum_weight_decimal_17g", graph["maximum_weight"]),
        ("edge_distribution_total_variation_decimal_17g", graph["edge_tv"]),
        ("task_weight_total_variation_decimal_17g", graph["task_tv"]),
        ("raw_max_task_share_decimal_17g", graph["raw_max_task"]),
        ("rank_max_task_share_decimal_17g", graph["rank_max_task"]),
    ):
        close(claimed_graph[field], expected, field, differences)

    aggregates = {}
    task_points = {}
    parent_points = {}
    check(set(claimed["models"]) == set(models), "claimed model set")
    for name in sorted(models):
        aggregates[name], task_points[name], parent_points[name] = aggregate(models[name], weights)
        observed = claimed["models"][name]
        exact_keys(observed, {
            "pairs", "tasks", "parents", "ties", "abstentions",
            "neutral_credit_policy_for_tie_or_abstain",
            "raw_pair_micro_accuracy_decimal_17g", "raw_task_macro_accuracy_decimal_17g",
            "raw_parent_macro_accuracy_decimal_17g", "ust_pair_micro_accuracy_decimal_17g",
            "ust_task_macro_accuracy_decimal_17g", "ust_task_clustered_ci95",
            "ust_parent_macro_accuracy_decimal_17g", "ust_parent_clustered_ci95",
            "ust_minus_raw_task_macro_decimal_17g",
            "ust_minus_raw_task_macro_clustered_ci95",
            "ust_minus_raw_parent_macro_decimal_17g",
            "ust_minus_raw_parent_macro_clustered_ci95",
            "paired_ust_task_delta_vs_tfidf", "paired_ust_parent_delta_vs_tfidf",
        }, f"{name} metrics")
        check(observed["neutral_credit_policy_for_tie_or_abstain"] == 0.5,
              f"{name} neutral policy")
        for field in ("pairs", "tasks", "parents", "ties", "abstentions"):
            check(observed[field] == aggregates[name][field], f"{name} {field}")
        for field, expected in (
            ("raw_pair_micro_accuracy_decimal_17g", aggregates[name]["raw_micro"]),
            ("raw_task_macro_accuracy_decimal_17g", aggregates[name]["raw_task"]),
            ("raw_parent_macro_accuracy_decimal_17g", aggregates[name]["raw_parent"]),
            ("ust_pair_micro_accuracy_decimal_17g", aggregates[name]["ust_micro"]),
            ("ust_task_macro_accuracy_decimal_17g", aggregates[name]["ust_task"]),
            ("ust_parent_macro_accuracy_decimal_17g", aggregates[name]["ust_parent"]),
            ("ust_minus_raw_task_macro_decimal_17g", aggregates[name]["task_shift"]),
            ("ust_minus_raw_parent_macro_decimal_17g", aggregates[name]["parent_shift"]),
        ):
            close(observed[field], expected, f"{name} {field}", differences)
        for index, expected in enumerate(aggregates[name]["ust_task_ci"]):
            close(observed["ust_task_clustered_ci95"][index], expected, f"{name} task ci", differences)
        for index, expected in enumerate(aggregates[name]["ust_parent_ci"]):
            close(observed["ust_parent_clustered_ci95"][index], expected, f"{name} parent ci", differences)
        for index, expected in enumerate(aggregates[name]["task_shift_ci"]):
            close(observed["ust_minus_raw_task_macro_clustered_ci95"][index], expected,
                  f"{name} task shift ci", differences)
        for index, expected in enumerate(aggregates[name]["parent_shift_ci"]):
            close(observed["ust_minus_raw_parent_macro_clustered_ci95"][index], expected,
                  f"{name} parent shift ci", differences)
        for level, points, seed in (
            ("task", task_points, TASK_SEED), ("parent", parent_points, PARENT_SEED)
        ):
            point, interval = paired(points[name], points[REFERENCE], seed)
            paired_claim = observed[f"paired_ust_{level}_delta_vs_tfidf"]
            exact_keys(paired_claim, {"clusters", "point_decimal_17g", "ci95"},
                       f"{name} {level} paired")
            check(paired_claim["clusters"] == len(points[name]), f"{name} {level} clusters")
            close(paired_claim["point_decimal_17g"], point, f"{name} {level} delta", differences)
            for index, expected in enumerate(interval):
                close(paired_claim["ci95"][index], expected, f"{name} {level} delta ci", differences)

    raw = {name: aggregates[name]["raw_task"] for name in models}
    ust = {name: aggregates[name]["ust_task"] for name in models}
    raw_all = sorted(models, key=lambda name: (-raw[name], name))
    ust_all = sorted(models, key=lambda name: (-ust[name], name))
    raw_primary = sorted(PRIMARY, key=lambda name: (-raw[name], name))
    ust_primary = sorted(PRIMARY, key=lambda name: (-ust[name], name))
    ranking = claimed["ranking_sensitivity"]
    exact_keys(ranking, {
        "all_models_raw_task_macro_order", "all_models_ust_task_macro_order",
        "all_models_discordant_pairs", "primary_models_raw_task_macro_order",
        "primary_models_ust_task_macro_order", "primary_models_discordant_pairs",
        "frozen_champion_reselection_performed",
    }, "ranking")
    check(ranking["all_models_raw_task_macro_order"] == raw_all, "raw all order")
    check(ranking["all_models_ust_task_macro_order"] == ust_all, "ust all order")
    check(ranking["primary_models_raw_task_macro_order"] == raw_primary, "raw primary order")
    check(ranking["primary_models_ust_task_macro_order"] == ust_primary, "ust primary order")
    check(ranking["all_models_discordant_pairs"] == discordance(raw_all, ust_all),
          "all ranking discordance")
    check(ranking["primary_models_discordant_pairs"] == discordance(raw_primary, ust_primary),
          "primary ranking discordance")
    check(ranking["frozen_champion_reselection_performed"] is False, "champion reselection")

    champion_delta = {
        name: task_points[CHAMPION][name] - task_points[REFERENCE][name]
        for name in task_points[CHAMPION]
    }
    loto = [
        sum(value for name, value in champion_delta.items() if name != dropped) / (len(champion_delta) - 1)
        for dropped in champion_delta
    ]
    summary = claimed["frozen_champion_summary"]
    exact_keys(summary, {
        "model", "reference", "ust_task_macro_accuracy_decimal_17g",
        "ust_task_clustered_ci95", "ust_minus_raw_task_macro_decimal_17g",
        "ust_minus_raw_task_macro_clustered_ci95",
        "ust_minus_raw_parent_macro_decimal_17g",
        "ust_minus_raw_parent_macro_clustered_ci95", "paired_ust_task_delta",
        "paired_ust_parent_delta", "leave_one_task_out_task_delta_min_decimal_17g",
        "leave_one_task_out_task_delta_max_decimal_17g", "leave_one_task_out_positive_count",
        "leave_one_task_out_total", "chance_supported_task_ci_lower_above_half",
        "advantage_over_tfidf_supported_task_ci_lower_above_zero",
        "advantage_over_tfidf_supported_parent_ci_lower_above_zero",
        "ust_weighting_changes_task_macro_supported_ci_excludes_zero",
        "ust_weighting_changes_parent_macro_supported_ci_excludes_zero",
    }, "champion summary")
    check(summary["model"] == CHAMPION and summary["reference"] == REFERENCE, "summary model")
    for field in (
        "ust_task_macro_accuracy_decimal_17g", "ust_task_clustered_ci95",
        "ust_minus_raw_task_macro_decimal_17g", "ust_minus_raw_task_macro_clustered_ci95",
        "ust_minus_raw_parent_macro_decimal_17g", "ust_minus_raw_parent_macro_clustered_ci95",
    ):
        check(summary[field] == claimed["models"][CHAMPION][field], f"summary mirror {field}")
    check(summary["paired_ust_task_delta"] == claimed["models"][CHAMPION]["paired_ust_task_delta_vs_tfidf"],
          "summary task delta")
    check(summary["paired_ust_parent_delta"] == claimed["models"][CHAMPION]["paired_ust_parent_delta_vs_tfidf"],
          "summary parent delta")
    close(summary["leave_one_task_out_task_delta_min_decimal_17g"], min(loto), "loto min", differences)
    close(summary["leave_one_task_out_task_delta_max_decimal_17g"], max(loto), "loto max", differences)
    check(summary["leave_one_task_out_positive_count"] == sum(value > 0.0 for value in loto), "loto count")
    check(summary["leave_one_task_out_total"] == len(loto), "loto total")
    task_delta_ci = claimed["models"][CHAMPION]["paired_ust_task_delta_vs_tfidf"]["ci95"]
    parent_delta_ci = claimed["models"][CHAMPION]["paired_ust_parent_delta_vs_tfidf"]["ci95"]
    task_shift_ci = claimed["models"][CHAMPION]["ust_minus_raw_task_macro_clustered_ci95"]
    parent_shift_ci = claimed["models"][CHAMPION]["ust_minus_raw_parent_macro_clustered_ci95"]
    check(summary["chance_supported_task_ci_lower_above_half"] ==
          (float(summary["ust_task_clustered_ci95"][0]) > 0.5), "summary chance flag")
    check(summary["advantage_over_tfidf_supported_task_ci_lower_above_zero"] ==
          (float(task_delta_ci[0]) > 0.0), "summary task advantage flag")
    check(summary["advantage_over_tfidf_supported_parent_ci_lower_above_zero"] ==
          (float(parent_delta_ci[0]) > 0.0), "summary parent advantage flag")
    check(summary["ust_weighting_changes_task_macro_supported_ci_excludes_zero"] ==
          (float(task_shift_ci[0]) > 0.0 or float(task_shift_ci[1]) < 0.0), "summary task shift flag")
    check(summary["ust_weighting_changes_parent_macro_supported_ci_excludes_zero"] ==
          (float(parent_shift_ci[0]) > 0.0 or float(parent_shift_ci[1]) < 0.0), "summary parent shift flag")
    check(claimed["interpretation_boundary"] == {
        "historical_postdisclosure_sensitivity_only": True,
        "not_a_new_champion_selection": True,
        "not_prospective_confirmation": True,
        "not_effective_sample_size": True,
        "not_independent_labels": True,
        "no_search_utility_claim": True,
    }, "interpretation boundary")
    exact_keys(claimed["scope"], {
        "historical_revealed_prediction_outcomes_read", "prospective_values_read", "model_fit",
        "gpu_paid_api_base_update", "raw_pair_task_parent_endpoint_identities_emitted",
    }, "scope")
    check(claimed["pair_graph"]["task_identities_emitted"] is False, "graph identities")
    check(claimed["scope"]["historical_revealed_prediction_outcomes_read"] is True,
          "historical scope")
    check(claimed["scope"]["prospective_values_read"] is False, "prospective scope")
    check(claimed["scope"]["model_fit"] is False, "fit scope")
    check(claimed["scope"]["gpu_paid_api_base_update"] == "0/0/0", "resource scope")
    check(claimed["scope"]["raw_pair_task_parent_endpoint_identities_emitted"] is False,
          "identity scope")
    sensitive = {
        str(row[field])
        for row in base.values()
        for field in ("task", "parent", "better", "worse", "better_run", "worse_run")
    }
    check(not (set(all_strings(claimed)) & sensitive), "raw identity emitted")
    return {
        "protocol": "historical-ust-predictor-sensitivity-independent-verification-v1",
        "status": "INDEPENDENT_GROUNDED_RECONSTRUCTION_EXACT_WITHIN_TOLERANCE",
        "static_per_pair_sha256": STATIC_SHA,
        "tfidf_per_pair_sha256": TFIDF_SHA,
        "claimed_result_sha256": None,
        "pairs": 931,
        "models": len(models),
        "incidence_rank": graph["incidence_rank"],
        "maximum_absolute_numeric_difference_decimal_17g": format(max(differences), ".17g"),
        "prospective_values_read": False,
        "raw_pair_task_parent_endpoint_identities_emitted": False,
        "gpu_paid_api_model_fit_base_update": "0/0/0/0",
    }


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
    parser.add_argument("--static-per-pair", type=Path, required=True)
    parser.add_argument("--tfidf-per-pair", type=Path, required=True)
    parser.add_argument("--claimed-result", type=Path, required=True)
    parser.add_argument("--claimed-result-sha256", required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    claimed_path = args.claimed_result.resolve()
    check(sha(claimed_path) == args.claimed_result_sha256, "claimed result SHA")
    claimed = json.loads(claimed_path.read_text(encoding="utf-8"))
    receipt = verify(claimed, args.static_per_pair.resolve(), args.tfidf_per_pair.resolve())
    receipt["claimed_result_sha256"] = args.claimed_result_sha256
    write(args.output.resolve(), receipt)
    print(canonical({
        "status": receipt["status"],
        "output_sha256": sha(args.output.resolve()),
        "prospective_values_read": False,
    }).decode(), end="")


if __name__ == "__main__":
    main()
