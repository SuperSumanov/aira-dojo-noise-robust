#!/usr/bin/env python3
"""Independent grounded-Laplacian verifier for the FOREAGENT UST weight audit."""

from __future__ import annotations

import argparse
from collections import Counter, defaultdict
import hashlib
import json
import math
import os
from pathlib import Path, PurePosixPath
from typing import Any, Iterable, Mapping

import numpy as np


SOURCE_SHA256 = "79363b7ef0b6154061f18e81f6c6fdf380e71ae3f1d7b9a262cc79acb08f0b5f"
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


def task(path: str) -> str:
    check(isinstance(path, str) and path, "path")
    pieces = PurePosixPath(path).parts
    check("solutions_subset_50" in pieces, "path layout")
    index = pieces.index("solutions_subset_50")
    check(index + 1 < len(pieces) and pieces[index + 1], "task path")
    return pieces[index + 1]


def linear_quantile(sorted_values: list[float], fraction: float) -> float:
    position = fraction * (len(sorted_values) - 1)
    lower, upper = int(math.floor(position)), int(math.ceil(position))
    if lower == upper:
        return sorted_values[lower]
    weight = position - lower
    return sorted_values[lower] * (1.0 - weight) + sorted_values[upper] * weight


def grounded_component_resistances(
    nodes: list[str], edges: list[tuple[str, str]]
) -> list[float]:
    check(len(nodes) >= 2 and edges, "component")
    index = {node: position for position, node in enumerate(nodes)}
    laplacian = np.zeros((len(nodes), len(nodes)), dtype=np.float64)
    for left, right in edges:
        i, j = index[left], index[right]
        laplacian[i, i] += 1.0
        laplacian[j, j] += 1.0
        laplacian[i, j] -= 1.0
        laplacian[j, i] -= 1.0
    grounded = len(nodes) - 1
    inverse = np.linalg.inv(laplacian[:grounded, :grounded])
    result: list[float] = []
    for left, right in edges:
        i, j = index[left], index[right]
        if i == grounded:
            value = float(inverse[j, j])
        elif j == grounded:
            value = float(inverse[i, i])
        else:
            value = float(inverse[i, i] + inverse[j, j] - 2.0 * inverse[i, j])
        check(value > 0.0 and value <= 1.0 + TOLERANCE, "resistance range")
        result.append(min(value, 1.0))
    check(abs(sum(result) - (len(nodes) - 1)) <= TOLERANCE * (len(nodes) - 1),
          "component Foster identity")
    return result


def reconstruct(rows: Iterable[Mapping[str, Any]]) -> dict[str, Any]:
    adjacency: dict[str, set[str]] = defaultdict(set)
    node_task: dict[str, str] = {}
    edges: set[tuple[str, str]] = set()
    row_count = 0
    for row_count, row in enumerate(rows, start=1):
        check(set(row) == {"paths"}, "row schema")
        paths = row["paths"]
        check(isinstance(paths, list) and len(paths) == 2, "paths")
        left, right = paths
        check(isinstance(left, str) and isinstance(right, str) and left != right, "endpoints")
        left_task, right_task = task(left), task(right)
        check(left_task == right_task, "cross-task")
        check(node_task.setdefault(left, left_task) == left_task, "task drift")
        check(node_task.setdefault(right, right_task) == right_task, "task drift")
        edge = tuple(sorted((left, right)))
        check(edge not in edges, "duplicate edge")
        edges.add(edge)
        adjacency[left].add(right)
        adjacency[right].add(left)
    check(row_count and edges, "empty")

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
            new = adjacency[node] & unseen
            unseen.difference_update(new)
            stack.extend(sorted(new, reverse=True))
        components.append(sorted(nodes))

    node_component: dict[str, int] = {}
    component_tasks: list[str] = []
    for number, nodes in enumerate(components):
        tasks = {node_task[node] for node in nodes}
        check(len(tasks) == 1, "component task")
        component_tasks.append(next(iter(tasks)))
        for node in nodes:
            node_component[node] = number
    edges_by_component: dict[int, list[tuple[str, str]]] = defaultdict(list)
    for edge in sorted(edges):
        number = node_component[edge[0]]
        check(number == node_component[edge[1]], "edge component")
        edges_by_component[number].append(edge)

    all_weights: list[float] = []
    residuals: list[float] = []
    task_edges: Counter[str] = Counter()
    task_rank: Counter[str] = Counter()
    for number, nodes in enumerate(components):
        weights = grounded_component_resistances(nodes, edges_by_component[number])
        all_weights.extend(weights)
        residuals.append(abs(sum(weights) - (len(nodes) - 1)))
        task_name = component_tasks[number]
        task_edges[task_name] += len(edges_by_component[number])
        task_rank[task_name] += len(nodes) - 1

    pair_rows = len(edges)
    vertices = len(adjacency)
    component_count = len(components)
    rank = vertices - component_count
    tasks = len(set(node_task.values()))
    check(row_count == pair_rows and len(all_weights) == pair_rows, "row accounting")
    check(abs(sum(all_weights) - rank) <= TOLERANCE * rank, "global Foster identity")
    sorted_weights = sorted(all_weights)
    edge_tv = 0.5 * sum(abs(value / rank - 1.0 / pair_rows) for value in all_weights)
    raw_task = {name: count / pair_rows for name, count in task_edges.items()}
    rank_task = {name: count / rank for name, count in task_rank.items()}
    task_tv = 0.5 * sum(abs(raw_task[name] - rank_task[name]) for name in task_edges)
    raw_hhi = sum(value * value for value in raw_task.values())
    rank_hhi = sum(value * value for value in rank_task.values())
    return {
        "source_rows": row_count,
        "pair_rows": pair_rows,
        "vertices": vertices,
        "tasks": tasks,
        "connected_components": component_count,
        "endpoint_edge_incidence_rank": rank,
        "sum": sum(all_weights),
        "maximum_component_residual": max(residuals),
        "global_residual": abs(sum(all_weights) - rank),
        "minimum": sorted_weights[0],
        "q25": linear_quantile(sorted_weights, 0.25),
        "median": linear_quantile(sorted_weights, 0.50),
        "q75": linear_quantile(sorted_weights, 0.75),
        "maximum": sorted_weights[-1],
        "edge_tv": edge_tv,
        "bridge_edges": sum(value >= 1.0 - 5e-9 for value in all_weights),
        "raw_max_task": max(raw_task.values()),
        "rank_max_task": max(rank_task.values()),
        "task_tv": task_tv,
        "raw_hhi": raw_hhi,
        "rank_hhi": rank_hhi,
        "tasks_up": sum(rank_task[name] > raw_task[name] for name in task_edges),
        "tasks_down": sum(rank_task[name] < raw_task[name] for name in task_edges),
    }


def close_decimal(claimed: str, expected: float, label: str) -> None:
    check(isinstance(claimed, str), f"{label} type")
    value = float(claimed)
    check(math.isfinite(value), f"{label} finite")
    check(abs(value - expected) <= TOLERANCE * max(1.0, abs(expected)), f"{label} drift")


def verify_claimed(claimed: Mapping[str, Any], expected: Mapping[str, Any]) -> None:
    for key in (
        "source_rows", "pair_rows", "vertices", "tasks", "connected_components",
        "endpoint_edge_incidence_rank",
    ):
        check(claimed.get(key) == expected[key], f"{key} drift")
    check(claimed.get("protocol") == "foreagent-public-ust-pair-weighting-result-v1", "protocol")
    check(claimed.get("status") == "DESCRIPTIVE_COMPLETE", "status")
    check(claimed.get("classification") == "DESCRIPTIVE_UST_PAIR_WEIGHTING_AUDIT_COMPLETE",
          "classification")
    ust = claimed["ust_edge_weight"]
    for field, key in (
        ("sum_decimal_17g", "sum"),
        ("maximum_component_foster_residual_decimal_17g", "maximum_component_residual"),
        ("global_foster_residual_decimal_17g", "global_residual"),
        ("minimum_decimal_17g", "minimum"),
        ("q25_decimal_17g", "q25"),
        ("median_decimal_17g", "median"),
        ("q75_decimal_17g", "q75"),
        ("maximum_decimal_17g", "maximum"),
        ("edge_distribution_total_variation_from_uniform_rows_decimal_17g", "edge_tv"),
    ):
        close_decimal(ust[field], expected[key], field)
    check(ust["expected_sum_rank"] == expected["endpoint_edge_incidence_rank"], "rank sum")
    check(ust["unit_probability_bridge_edges"] == expected["bridge_edges"], "bridge count")
    mean = expected["endpoint_edge_incidence_rank"] / expected["pair_rows"]
    close_decimal(ust["mean_exact"]["decimal_17g"], mean, "mean")
    close_decimal(ust["minimum_to_uniform_mean_decimal_17g"], expected["minimum"] / mean,
                  "minimum ratio")
    close_decimal(ust["maximum_to_uniform_mean_decimal_17g"], expected["maximum"] / mean,
                  "maximum ratio")
    task_weighting = claimed["task_weighting"]
    for field, key in (
        ("raw_pair_row_max_task_share_decimal_17g", "raw_max_task"),
        ("incidence_rank_max_task_share_decimal_17g", "rank_max_task"),
        ("total_variation_decimal_17g", "task_tv"),
        ("raw_pair_row_herfindahl_decimal_17g", "raw_hhi"),
        ("incidence_rank_herfindahl_decimal_17g", "rank_hhi"),
    ):
        close_decimal(task_weighting[field], expected[key], field)
    close_decimal(task_weighting["raw_pair_row_effective_task_count_decimal_17g"],
                  1.0 / expected["raw_hhi"], "raw effective tasks")
    close_decimal(task_weighting["incidence_rank_effective_task_count_decimal_17g"],
                  1.0 / expected["rank_hhi"], "rank effective tasks")
    check(task_weighting["tasks_upweighted_by_rank_normalization"] == expected["tasks_up"],
          "tasks up")
    check(task_weighting["tasks_downweighted_by_rank_normalization"] == expected["tasks_down"],
          "tasks down")
    check(task_weighting["task_identities_emitted"] is False, "task identities")
    check(claimed["scope"] == {
        "columns_read": ["paths"],
        "scores_or_predictions_read": False,
        "solution_code_read": False,
        "raw_identities_emitted": False,
        "gpu_paid_api_model_fit_base_update": "0/0/0/0",
    }, "scope")


def read_rows(path: Path) -> list[dict[str, Any]]:
    import pyarrow.parquet as pq

    return pq.read_table(path, columns=["paths"]).to_pylist()


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
    parser.add_argument("--input", type=Path, required=True)
    parser.add_argument("--input-sha256", required=True)
    parser.add_argument("--claimed-result", type=Path, required=True)
    parser.add_argument("--claimed-result-sha256", required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    source = args.input.resolve()
    claimed_path = args.claimed_result.resolve()
    check(args.input_sha256 == SOURCE_SHA256 and sha(source) == SOURCE_SHA256, "source SHA")
    check(sha(claimed_path) == args.claimed_result_sha256, "claimed SHA")
    expected = reconstruct(read_rows(source))
    claimed = json.loads(claimed_path.read_text(encoding="utf-8"))
    verify_claimed(claimed, expected)
    receipt = {
        "protocol": "foreagent-public-ust-pair-weighting-independent-verification-v1",
        "status": "INDEPENDENT_GROUNDED_LAPLACIAN_RECONSTRUCTION_WITHIN_TOLERANCE",
        "source_sha256": SOURCE_SHA256,
        "claimed_result_sha256": args.claimed_result_sha256,
        "pair_rows": expected["pair_rows"],
        "vertices": expected["vertices"],
        "connected_components": expected["connected_components"],
        "endpoint_edge_incidence_rank": expected["endpoint_edge_incidence_rank"],
        "global_foster_residual_decimal_17g": format(expected["global_residual"], ".17g"),
        "scores_or_predictions_read": False,
        "raw_identities_emitted": False,
        "gpu_paid_api_model_fit_base_update": "0/0/0/0",
    }
    write(args.output.resolve(), receipt)
    print(canonical({
        "status": receipt["status"],
        "output_sha256": sha(args.output.resolve()),
        "scores_or_predictions_read": False,
    }).decode(), end="")


if __name__ == "__main__":
    main()
