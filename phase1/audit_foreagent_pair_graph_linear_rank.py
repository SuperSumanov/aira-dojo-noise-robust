#!/usr/bin/env python3
"""Aggregate-only linear-rank audit of FOREAGENT's public pair graph."""

from __future__ import annotations

import argparse
from collections import Counter
import hashlib
import json
import math
import os
from pathlib import Path, PurePosixPath
import re
from typing import Any, Iterable, Mapping


SOURCE_SHA256 = "79363b7ef0b6154061f18e81f6c6fdf380e71ae3f1d7b9a262cc79acb08f0b5f"
SHA_RE = re.compile(r"[0-9a-f]{64}")


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


def ratio(numerator: int, denominator: int) -> dict[str, Any]:
    require(denominator > 0, "zero denominator")
    divisor = math.gcd(numerator, denominator)
    return {
        "numerator": numerator // divisor,
        "denominator": denominator // divisor,
        "decimal_17g": format(numerator / denominator, ".17g"),
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


def summarize(rows: Iterable[Mapping[str, Any]], source_sha256: str) -> dict[str, Any]:
    require(SHA_RE.fullmatch(source_sha256) is not None, "source SHA")
    edges: set[tuple[str, str]] = set()
    node_task: dict[str, str] = {}
    degrees: Counter[str] = Counter()
    union = UnionFind()
    source_rows = 0
    for source_rows, row in enumerate(rows, start=1):
        require(set(row) == {"paths"}, f"row {source_rows} schema")
        paths = row["paths"]
        require(isinstance(paths, list) and len(paths) == 2, f"row {source_rows} paths")
        left, right = paths
        require(isinstance(left, str) and isinstance(right, str) and left != right,
                f"row {source_rows} endpoints")
        left_task, right_task = task_from_path(left), task_from_path(right)
        require(left_task == right_task, f"row {source_rows} cross-task edge")
        require(node_task.setdefault(left, left_task) == left_task, "endpoint task drift")
        require(node_task.setdefault(right, right_task) == right_task, "endpoint task drift")
        edge = tuple(sorted((left, right)))
        require(edge not in edges, f"row {source_rows} duplicate unordered edge")
        edges.add(edge)
        union.union(*edge)
        degrees.update(edge)
    require(source_rows > 0 and edges, "empty graph")

    roots = {union.find(node) for node in union.parent}
    component_tasks: dict[str, str] = {}
    components_per_task: Counter[str] = Counter()
    for node, task in node_task.items():
        root = union.find(node)
        require(component_tasks.setdefault(root, task) == task, "component crosses tasks")
    components_per_task.update(component_tasks.values())
    vertices = len(union.parent)
    pairs = len(edges)
    components = len(roots)
    tasks = len(set(node_task.values()))
    incidence_rank = vertices - components
    require(incidence_rank > 0 and pairs >= incidence_rank, "incidence arithmetic")
    redundant = pairs - incidence_rank
    tasks_connected = sum(count == 1 for count in components_per_task.values())
    return {
        "protocol": "foreagent-public-pair-graph-linear-rank-result-v1",
        "status": "DESCRIPTIVE_COMPLETE",
        "classification": "DESCRIPTIVE_PAIR_GRAPH_LINEAR_RANK_AUDIT_COMPLETE",
        "source_sha256": source_sha256,
        "source_rows": source_rows,
        "pair_rows": pairs,
        "vertices": vertices,
        "tasks": tasks,
        "connected_components": components,
        "tasks_with_exactly_one_connected_component": tasks_connected,
        "endpoint_edge_incidence_rank": incidence_rank,
        "cycle_redundant_pair_rows": redundant,
        "pair_rows_per_incidence_rank": ratio(pairs, incidence_rank),
        "redundant_pair_row_share": ratio(redundant, pairs),
        "degree": {
            "minimum": min(degrees.values()),
            "maximum": max(degrees.values()),
            "sum": sum(degrees.values()),
        },
        "arithmetic_crosschecks": {
            "source_rows_equal_unique_edges": source_rows == pairs,
            "degree_sum_equals_twice_pair_rows": sum(degrees.values()) == 2 * pairs,
            "components_equal_tasks": components == tasks,
            "every_task_graph_connected": tasks_connected == tasks,
            "rank_equals_vertices_minus_components": incidence_rank == vertices - components,
        },
        "interpretation_boundary": {
            "quantity": "rank of the endpoint-edge incidence design in the released comparison graph",
            "not_claimed": [
                "statistically independent labels",
                "effective sample size",
                "Shannon information",
                "invalidity of published model accuracy",
                "causal explanation of prediction difficulty",
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

    table = pq.read_table(path, columns=["paths"])
    return table.to_pylist()


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
