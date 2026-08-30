#!/usr/bin/env python3
"""Aggregate-only UST edge-weight audit of FOREAGENT's public pair graph."""

from __future__ import annotations

import argparse
from collections import Counter, defaultdict
import hashlib
import json
import math
import os
from pathlib import Path, PurePosixPath
import re
from typing import Any, Iterable, Mapping

import numpy as np


SOURCE_SHA256 = "79363b7ef0b6154061f18e81f6c6fdf380e71ae3f1d7b9a262cc79acb08f0b5f"
SHA_RE = re.compile(r"[0-9a-f]{64}")
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


def ratio(numerator: int, denominator: int) -> dict[str, Any]:
    require(denominator > 0, "zero denominator")
    divisor = math.gcd(numerator, denominator)
    return {
        "numerator": numerator // divisor,
        "denominator": denominator // divisor,
        "decimal_17g": decimal(numerator / denominator),
    }


def task_from_path(path: str) -> str:
    require(isinstance(path, str) and path, "invalid solution path")
    pieces = PurePosixPath(path).parts
    require("solutions_subset_50" in pieces, "unexpected solution path")
    index = pieces.index("solutions_subset_50")
    require(index + 1 < len(pieces) and pieces[index + 1], "missing task in path")
    return pieces[index + 1]


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


def graph_from_rows(
    rows: Iterable[Mapping[str, Any]],
) -> tuple[int, list[tuple[str, str]], dict[str, str], UnionFind]:
    edges: set[tuple[str, str]] = set()
    node_task: dict[str, str] = {}
    union = UnionFind()
    source_rows = 0
    for source_rows, row in enumerate(rows, start=1):
        require(set(row) == {"paths"}, f"row {source_rows} schema")
        paths = row["paths"]
        require(isinstance(paths, list) and len(paths) == 2, f"row {source_rows} paths")
        left, right = paths
        require(
            isinstance(left, str) and isinstance(right, str) and left != right,
            f"row {source_rows} endpoints",
        )
        left_task, right_task = task_from_path(left), task_from_path(right)
        require(left_task == right_task, f"row {source_rows} cross-task edge")
        require(node_task.setdefault(left, left_task) == left_task, "endpoint task drift")
        require(node_task.setdefault(right, right_task) == right_task, "endpoint task drift")
        edge = tuple(sorted((left, right)))
        require(edge not in edges, f"row {source_rows} duplicate unordered edge")
        edges.add(edge)
        union.union(*edge)
    require(source_rows > 0 and edges, "empty graph")
    return source_rows, sorted(edges), node_task, union


def linear_quantile(sorted_values: list[float], fraction: float) -> float:
    require(sorted_values and 0.0 <= fraction <= 1.0, "quantile arguments")
    position = fraction * (len(sorted_values) - 1)
    lower = int(math.floor(position))
    upper = int(math.ceil(position))
    if lower == upper:
        return sorted_values[lower]
    weight = position - lower
    return sorted_values[lower] * (1.0 - weight) + sorted_values[upper] * weight


def component_leverages(
    nodes: list[str], edges: list[tuple[str, str]]
) -> list[float]:
    require(len(nodes) >= 2 and edges, "empty component")
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
    require(abs(float(eigenvalues[0])) <= threshold, "missing Laplacian nullspace")
    require(np.all(eigenvalues[1:] > threshold), "component is not connected")
    positive_vectors = eigenvectors[:, 1:]
    pseudoinverse = (positive_vectors / eigenvalues[1:]) @ positive_vectors.T
    leverages: list[float] = []
    for left, right in edges:
        i, j = index[left], index[right]
        value = float(pseudoinverse[i, i] + pseudoinverse[j, j] - 2.0 * pseudoinverse[i, j])
        require(value > 0.0 and value <= 1.0 + NUMERIC_TOLERANCE, "invalid edge leverage")
        leverages.append(min(value, 1.0))
    expected = len(nodes) - 1
    require(abs(sum(leverages) - expected) <= NUMERIC_TOLERANCE * max(1, expected),
            "Foster identity drift")
    return leverages


def summarize(rows: Iterable[Mapping[str, Any]], source_sha256: str) -> dict[str, Any]:
    require(SHA_RE.fullmatch(source_sha256) is not None, "source SHA")
    source_rows, edges, node_task, union = graph_from_rows(rows)
    component_nodes: dict[str, list[str]] = defaultdict(list)
    for node in sorted(node_task):
        component_nodes[union.find(node)].append(node)
    component_edges: dict[str, list[tuple[str, str]]] = defaultdict(list)
    for edge in edges:
        root = union.find(edge[0])
        require(root == union.find(edge[1]), "edge component drift")
        component_edges[root].append(edge)

    task_edges: Counter[str] = Counter()
    task_rank: Counter[str] = Counter()
    component_task: dict[str, str] = {}
    all_leverages: list[float] = []
    component_residuals: list[float] = []
    for root in sorted(component_nodes):
        nodes = component_nodes[root]
        tasks = {node_task[node] for node in nodes}
        require(len(tasks) == 1, "component crosses tasks")
        task = next(iter(tasks))
        component_task[root] = task
        local_edges = component_edges[root]
        leverages = component_leverages(nodes, local_edges)
        all_leverages.extend(leverages)
        component_residuals.append(abs(sum(leverages) - (len(nodes) - 1)))
        task_edges[task] += len(local_edges)
        task_rank[task] += len(nodes) - 1

    pair_rows = len(edges)
    vertices = len(node_task)
    components = len(component_nodes)
    tasks = len(set(node_task.values()))
    rank = vertices - components
    require(source_rows == pair_rows and len(all_leverages) == pair_rows, "row accounting")
    require(sum(task_edges.values()) == pair_rows, "task edge accounting")
    require(sum(task_rank.values()) == rank, "task rank accounting")
    require(abs(sum(all_leverages) - rank) <= NUMERIC_TOLERANCE * rank, "global Foster identity")

    sorted_leverages = sorted(all_leverages)
    uniform_edge_probability = 1.0 / pair_rows
    leverage_probabilities = [value / rank for value in all_leverages]
    edge_total_variation = 0.5 * sum(
        abs(value - uniform_edge_probability) for value in leverage_probabilities
    )
    raw_task_probabilities = {task: count / pair_rows for task, count in task_edges.items()}
    rank_task_probabilities = {task: count / rank for task, count in task_rank.items()}
    task_total_variation = 0.5 * sum(
        abs(raw_task_probabilities[task] - rank_task_probabilities[task])
        for task in task_edges
    )
    raw_hhi = sum(value * value for value in raw_task_probabilities.values())
    rank_hhi = sum(value * value for value in rank_task_probabilities.values())
    mean_leverage = rank / pair_rows

    return {
        "protocol": "foreagent-public-ust-pair-weighting-result-v1",
        "status": "DESCRIPTIVE_COMPLETE",
        "classification": "DESCRIPTIVE_UST_PAIR_WEIGHTING_AUDIT_COMPLETE",
        "source_sha256": source_sha256,
        "source_rows": source_rows,
        "pair_rows": pair_rows,
        "vertices": vertices,
        "tasks": tasks,
        "connected_components": components,
        "endpoint_edge_incidence_rank": rank,
        "components_with_one_task": sum(
            len({node_task[node] for node in component_nodes[root]}) == 1
            for root in component_nodes
        ),
        "ust_edge_weight": {
            "definition": "unweighted edge effective resistance, equal to its uniform-spanning-tree inclusion probability within its connected component",
            "sum_decimal_17g": decimal(sum(all_leverages)),
            "expected_sum_rank": rank,
            "maximum_component_foster_residual_decimal_17g": decimal(max(component_residuals)),
            "global_foster_residual_decimal_17g": decimal(abs(sum(all_leverages) - rank)),
            "mean_exact": ratio(rank, pair_rows),
            "minimum_decimal_17g": decimal(sorted_leverages[0]),
            "q25_decimal_17g": decimal(linear_quantile(sorted_leverages, 0.25)),
            "median_decimal_17g": decimal(linear_quantile(sorted_leverages, 0.50)),
            "q75_decimal_17g": decimal(linear_quantile(sorted_leverages, 0.75)),
            "maximum_decimal_17g": decimal(sorted_leverages[-1]),
            "minimum_to_uniform_mean_decimal_17g": decimal(sorted_leverages[0] / mean_leverage),
            "maximum_to_uniform_mean_decimal_17g": decimal(sorted_leverages[-1] / mean_leverage),
            "edge_distribution_total_variation_from_uniform_rows_decimal_17g": decimal(edge_total_variation),
            "unit_probability_bridge_edges": sum(
                value >= 1.0 - NUMERIC_TOLERANCE for value in all_leverages
            ),
        },
        "task_weighting": {
            "raw_pair_row_max_task_share_decimal_17g": decimal(max(raw_task_probabilities.values())),
            "incidence_rank_max_task_share_decimal_17g": decimal(max(rank_task_probabilities.values())),
            "total_variation_decimal_17g": decimal(task_total_variation),
            "raw_pair_row_herfindahl_decimal_17g": decimal(raw_hhi),
            "incidence_rank_herfindahl_decimal_17g": decimal(rank_hhi),
            "raw_pair_row_effective_task_count_decimal_17g": decimal(1.0 / raw_hhi),
            "incidence_rank_effective_task_count_decimal_17g": decimal(1.0 / rank_hhi),
            "tasks_upweighted_by_rank_normalization": sum(
                rank_task_probabilities[task] > raw_task_probabilities[task]
                for task in task_edges
            ),
            "tasks_downweighted_by_rank_normalization": sum(
                rank_task_probabilities[task] < raw_task_probabilities[task]
                for task in task_edges
            ),
            "task_identities_emitted": False,
        },
        "metric_interpretation": {
            "ust_averaged_pair_accuracy": "sum_e R_e * correct_e / (V-C), with an outer task-macro aggregation when tasks are the scientific population",
            "expectation_identity": "equals expected edge accuracy on one independent uniform spanning tree per connected component",
            "complete_clique_special_case": "for K_k, every edge has R_e=2/k and the total weight is k-1",
            "tree_special_case": "for a tree, every edge has R_e=1 and the metric equals raw edge accuracy",
        },
        "interpretation_boundary": {
            "not_claimed": [
                "new effective-resistance or spanning-tree mathematics",
                "effective sample size",
                "statistical independence of weighted labels",
                "Shannon information",
                "superiority over task-macro or cluster-robust inference",
                "invalidity of FOREAGENT model accuracy",
                "predictor efficacy without an outcome-bearing sensitivity analysis",
            ],
        },
        "scope": {
            "columns_read": ["paths"],
            "scores_or_predictions_read": False,
            "solution_code_read": False,
            "raw_identities_emitted": False,
            "gpu_paid_api_model_fit_base_update": "0/0/0/0",
        },
    }


def read_parquet(path: Path) -> list[dict[str, Any]]:
    import pyarrow.parquet as pq

    return pq.read_table(path, columns=["paths"]).to_pylist()


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
    parser.add_argument("--input", type=Path, required=True)
    parser.add_argument("--input-sha256", required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    source = args.input.resolve()
    require(args.input_sha256 == SOURCE_SHA256, "unfrozen source SHA")
    require(file_sha(source) == args.input_sha256, "input SHA mismatch")
    result = summarize(read_parquet(source), args.input_sha256)
    write_exclusive(args.output.resolve(), result)
    print(canonical_bytes({
        "status": result["status"],
        "classification": result["classification"],
        "output_sha256": file_sha(args.output.resolve()),
        "scores_or_predictions_read": False,
    }).decode(), end="")


if __name__ == "__main__":
    main()
