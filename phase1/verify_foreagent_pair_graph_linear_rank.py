#!/usr/bin/env python3
"""Independent adjacency/DFS verifier for the FOREAGENT public pair-graph rank audit."""

from __future__ import annotations

import argparse
from collections import Counter, defaultdict
import hashlib
import json
import math
import os
from pathlib import Path, PurePosixPath
from typing import Any, Iterable, Mapping


SOURCE_SHA256 = "79363b7ef0b6154061f18e81f6c6fdf380e71ae3f1d7b9a262cc79acb08f0b5f"


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


def fraction(numerator: int, denominator: int) -> dict[str, Any]:
    divisor = math.gcd(numerator, denominator)
    return {
        "numerator": numerator // divisor,
        "denominator": denominator // divisor,
        "decimal_17g": format(numerator / denominator, ".17g"),
    }


def task(path: str) -> str:
    pieces = PurePosixPath(path).parts
    check("solutions_subset_50" in pieces, "path layout")
    index = pieces.index("solutions_subset_50")
    check(index + 1 < len(pieces), "task path")
    return pieces[index + 1]


def reconstruct(rows: Iterable[Mapping[str, Any]], source_sha: str) -> dict[str, Any]:
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
    check(row_count > 0, "empty graph")

    unseen = set(adjacency)
    component_tasks: list[str] = []
    while unseen:
        start = min(unseen)
        unseen.remove(start)
        stack = [start]
        observed_tasks: set[str] = set()
        while stack:
            node = stack.pop()
            observed_tasks.add(node_task[node])
            new = adjacency[node] & unseen
            unseen.difference_update(new)
            stack.extend(sorted(new, reverse=True))
        check(len(observed_tasks) == 1, "component task")
        component_tasks.append(next(iter(observed_tasks)))
    task_components = Counter(component_tasks)
    pairs = len(edges)
    vertices = len(adjacency)
    components = len(component_tasks)
    tasks = len(set(node_task.values()))
    rank = vertices - components
    redundant = pairs - rank
    degrees = [len(adjacency[node]) for node in adjacency]
    tasks_connected = sum(count == 1 for count in task_components.values())
    return {
        "protocol": "foreagent-public-pair-graph-linear-rank-result-v1",
        "status": "DESCRIPTIVE_COMPLETE",
        "classification": "DESCRIPTIVE_PAIR_GRAPH_LINEAR_RANK_AUDIT_COMPLETE",
        "source_sha256": source_sha,
        "source_rows": row_count,
        "pair_rows": pairs,
        "vertices": vertices,
        "tasks": tasks,
        "connected_components": components,
        "tasks_with_exactly_one_connected_component": tasks_connected,
        "endpoint_edge_incidence_rank": rank,
        "cycle_redundant_pair_rows": redundant,
        "pair_rows_per_incidence_rank": fraction(pairs, rank),
        "redundant_pair_row_share": fraction(redundant, pairs),
        "degree": {"minimum": min(degrees), "maximum": max(degrees), "sum": sum(degrees)},
        "arithmetic_crosschecks": {
            "source_rows_equal_unique_edges": row_count == pairs,
            "degree_sum_equals_twice_pair_rows": sum(degrees) == 2 * pairs,
            "components_equal_tasks": components == tasks,
            "every_task_graph_connected": tasks_connected == tasks,
            "rank_equals_vertices_minus_components": rank == vertices - components,
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
    expected = reconstruct(read_rows(source), SOURCE_SHA256)
    claimed = json.loads(claimed_path.read_text(encoding="utf-8"))
    check(claimed == expected, "claimed result differs from independent DFS reconstruction")
    receipt = {
        "protocol": "foreagent-public-pair-graph-linear-rank-independent-verification-v1",
        "status": "INDEPENDENT_DFS_RECONSTRUCTION_EXACT",
        "source_sha256": SOURCE_SHA256,
        "claimed_result_sha256": args.claimed_result_sha256,
        "pair_rows": expected["pair_rows"],
        "vertices": expected["vertices"],
        "connected_components": expected["connected_components"],
        "endpoint_edge_incidence_rank": expected["endpoint_edge_incidence_rank"],
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
