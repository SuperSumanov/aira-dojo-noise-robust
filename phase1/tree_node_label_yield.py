#!/usr/bin/env python3
"""Aggregate-only structural simulation of endpoint execution label yield.

The acquisition rules consume graph topology only.  They never use pair orientation,
gaps, grades, code, predictor outputs, runtime, or prospective data.
"""

from __future__ import annotations

import argparse
from collections import Counter, defaultdict
from dataclasses import dataclass
import hashlib
import json
import math
import os
from pathlib import Path
from typing import Any, Iterable


RESULT_PROTOCOL = "tree-node-to-sibling-label-yield-result-v1"


class YieldError(RuntimeError):
    pass


def require(condition: bool, message: str) -> None:
    if not condition:
        raise YieldError(message)


def canonical(value: Any) -> str:
    return json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
    )


def raw_sha256(path: Path) -> str:
    require(path.is_file() and not path.is_symlink(), f"unsafe input: {path}")
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(8 << 20), b""):
            digest.update(block)
    return digest.hexdigest()


def normalized_lf(path: Path) -> bytes:
    require(path.is_file() and not path.is_symlink(), f"unsafe input: {path}")
    text = path.read_bytes().decode("utf-8")
    return text.replace("\r\n", "\n").replace("\r", "\n").encode("utf-8")


def normalized_sha256(path: Path) -> tuple[str, int]:
    payload = normalized_lf(path)
    return hashlib.sha256(payload).hexdigest(), len(payload)


def hash_key(*parts: Any) -> str:
    return hashlib.sha256("\0".join(map(str, parts)).encode()).hexdigest()


@dataclass(frozen=True)
class Edge:
    u: str
    v: str
    parent: str
    task: str
    run: str

    @property
    def endpoints(self) -> tuple[str, str]:
        return self.u, self.v


@dataclass
class Graph:
    edges: list[Edge]
    nodes: tuple[str, ...]
    incident: dict[str, tuple[int, ...]]
    context: dict[str, tuple[str, str]]


def load_protocol(path: Path, expected_sha: str) -> tuple[dict[str, Any], str]:
    observed = raw_sha256(path)
    require(observed == expected_sha, "protocol SHA mismatch")
    value = json.loads(path.read_text(encoding="utf-8"))
    require(value.get("protocol") == "tree-node-to-sibling-label-yield-v1", "protocol name")
    require(
        value.get("status")
        == "FROZEN_AFTER_AGGREGATE_TOPOLOGY_TOTALS_BEFORE_ACQUISITION_CURVES",
        "protocol status",
    )
    require(value["estimand"]["not_multifidelity"] is True, "estimand drift")
    require(value["analysis"]["result_is_aggregate_only"] is True, "release drift")
    return value, observed


def verify_lineage_certificate(
    protocol: dict[str, Any], bindings_path: Path, formal_path: Path
) -> dict[str, str]:
    binding = protocol["immutable_inputs"]["lineage_audit_bindings"]
    bindings_sha = raw_sha256(bindings_path)
    formal_sha = raw_sha256(formal_path)
    require(bindings_sha == binding["sha256"], "lineage bindings SHA")
    require(formal_sha == binding["formal_result_sha256"], "lineage formal SHA")
    bindings = json.loads(bindings_path.read_text(encoding="utf-8"))
    formal = json.loads(formal_path.read_text(encoding="utf-8"))
    required_class = binding["required_classification"]
    require(bindings["classification"] == required_class, "bindings classification")
    require(formal["classification"] == required_class, "formal classification")
    require(
        bindings["formal"]["producer_a_sha256"] == formal_sha,
        "formal result not bound by package",
    )
    profile = formal["scientific"]["set_profiles"]["train:b0"]
    require(profile["all_rows"]["pairs"] == 4263, "lineage profile rows")
    relations = profile["relation_counts"]
    require(relations["cross_run_declared_context"] == 0, "cross-run row")
    require(relations["same_run_declared_context_non_sibling"] == 0, "non-sibling row")
    require(
        relations["parent_present_verified_direct_sibling"]
        + relations["lineage_verified_orphan_parent_sibling"]
        == 4263,
        "lineage-direct row closure",
    )
    return {"lineage_bindings": bindings_sha, "lineage_formal_result": formal_sha}


def load_graph(path: Path, protocol: dict[str, Any]) -> tuple[Graph, dict[str, str]]:
    binding = protocol["immutable_inputs"]["pair_graph"]
    digest, size = normalized_sha256(path)
    require(digest == binding["sha256"], "pair graph SHA")
    require(size == binding["git_blob_bytes"], "pair graph normalized size")
    edges: list[Edge] = []
    seen_edges: set[tuple[str, str]] = set()
    context: dict[str, tuple[str, str]] = {}
    parents: dict[str, tuple[str, str]] = {}
    for number, line in enumerate(normalized_lf(path).decode("utf-8").splitlines(), 1):
        require(bool(line), f"blank row: {number}")
        row = json.loads(line)
        require(isinstance(row, dict), f"row object: {number}")
        better, worse = row.get("better"), row.get("worse")
        parent, task, run = row.get("parent"), row.get("task"), row.get("run_id")
        require(
            all(isinstance(item, str) and item for item in (better, worse, parent, task, run)),
            f"graph fields: {number}",
        )
        require(row.get("intask_split") == "train", f"partition: {number}")
        require(row.get("budget") == 0, f"budget: {number}")
        u, v = sorted((better, worse))
        require(u != v and (u, v) not in seen_edges, f"duplicate/self edge: {number}")
        seen_edges.add((u, v))
        pair_context = (task, run)
        for endpoint in (u, v):
            previous = context.setdefault(endpoint, pair_context)
            require(previous == pair_context, f"endpoint context conflict: {number}")
        previous_parent = parents.setdefault(parent, pair_context)
        require(previous_parent == pair_context, f"parent context conflict: {number}")
        edges.append(Edge(u, v, parent, task, run))
    require(len(edges) == binding["rows"], "pair row count")
    incident_mutable: dict[str, list[int]] = defaultdict(list)
    for index, edge in enumerate(edges):
        incident_mutable[edge.u].append(index)
        incident_mutable[edge.v].append(index)
    incident = {key: tuple(value) for key, value in incident_mutable.items()}
    graph = Graph(edges, tuple(sorted(context)), incident, context)
    known = protocol["known_before_freeze"]
    require(len(edges) == known["pairs"], "known pair count")
    require(len(graph.nodes) == known["endpoints"], "known endpoint count")
    require(len({edge.parent for edge in edges}) == known["parents"], "known parent count")
    require(len({edge.task for edge in edges}) == known["tasks"], "known task count")
    require(len({edge.run for edge in edges}) == known["physical_runs"], "known run count")
    return graph, {"pair_graph": digest}


def fraction(value: int, denominator: int) -> dict[str, Any]:
    require(denominator > 0, "nonpositive denominator")
    divisor = math.gcd(value, denominator)
    numerator, reduced_denominator = value // divisor, denominator // divisor
    return {
        "numerator": numerator,
        "denominator": reduced_denominator,
        "decimal_17g": format(value / denominator, ".17g"),
    }


class State:
    def __init__(self, graph: Graph) -> None:
        self.graph = graph
        self.selected: set[str] = set()
        self.closed: set[int] = set()
        self.selected_neighbors: Counter[str] = Counter()
        self.closed_task: Counter[str] = Counter()
        self.closed_run: Counter[str] = Counter()
        self.closed_parent: Counter[str] = Counter()

    def gain(self, missing: tuple[str, ...]) -> int:
        if len(missing) == 1:
            return self.selected_neighbors[missing[0]]
        require(len(missing) == 2, "action arity")
        u, v = missing
        return self.selected_neighbors[u] + self.selected_neighbors[v] + 1

    def add(self, missing: tuple[str, ...]) -> None:
        require(all(node not in self.selected for node in missing), "selected action endpoint")
        for node in missing:
            self.selected.add(node)
            for index in self.graph.incident[node]:
                if index in self.closed:
                    continue
                edge = self.graph.edges[index]
                other = edge.v if edge.u == node else edge.u
                if other in self.selected:
                    self.closed.add(index)
                    self.closed_task[edge.task] += 1
                    self.closed_run[edge.run] += 1
                    self.closed_parent[edge.parent] += 1
                else:
                    self.selected_neighbors[other] += 1

    def metrics(self, seed: int, budget: int) -> dict[str, Any]:
        closed = len(self.closed)
        task_square = sum(value * value for value in self.closed_task.values())
        run_square = sum(value * value for value in self.closed_run.values())
        max_task = max(self.closed_task.values(), default=0)
        max_run = max(self.closed_run.values(), default=0)
        return {
            "seed": seed,
            "budget": budget,
            "selected_endpoints": len(self.selected),
            "closed_edges": closed,
            "closed_edges_per_endpoint": fraction(closed, max(1, len(self.selected))),
            "parents": len(self.closed_parent),
            "tasks": len(self.closed_task),
            "physical_runs": len(self.closed_run),
            "maximum_single_task_share": fraction(max_task, max(1, closed)),
            "maximum_single_run_share": fraction(max_run, max(1, closed)),
            "task_effective_count": fraction(closed * closed, max(1, task_square)),
            "run_effective_count": fraction(closed * closed, max(1, run_square)),
        }


def snapshots_from_actions(
    graph: Graph, seed: int, budgets: list[int], actions: Iterable[tuple[str, ...]]
) -> list[dict[str, Any]]:
    state = State(graph)
    output: list[dict[str, Any]] = []
    position = 0
    for missing in actions:
        new_count = len(state.selected) + len(missing)
        while position < len(budgets) and budgets[position] < new_count:
            output.append(state.metrics(seed, budgets[position]))
            position += 1
        state.add(missing)
        if position == len(budgets):
            break
    while position < len(budgets):
        output.append(state.metrics(seed, budgets[position]))
        position += 1
    return output


def uniform_node_actions(graph: Graph, seed: int) -> Iterable[tuple[str, ...]]:
    for node in sorted(graph.nodes, key=lambda item: hash_key(seed, "NODE", item)):
        yield (node,)


def uniform_edge_actions(
    graph: Graph, seed: int, maximum_budget: int
) -> Iterable[tuple[str, ...]]:
    selected: set[str] = set()
    ordered = sorted(
        graph.edges,
        key=lambda edge: hash_key(seed, "EDGE", edge.u, edge.v),
    )
    for edge in ordered:
        missing = tuple(node for node in edge.endpoints if node not in selected)
        if not missing or len(selected) + len(missing) > maximum_budget:
            continue
        selected.update(missing)
        yield missing


def better_action(
    candidate: tuple[int, int, int, int, str, tuple[str, ...]],
    incumbent: tuple[int, int, int, int, str, tuple[str, ...]] | None,
    balanced: bool,
) -> bool:
    if incumbent is None:
        return True
    gain, cost, task_count, run_count, tie, _ = candidate
    other_gain, other_cost, other_task, other_run, other_tie, _ = incumbent
    if balanced:
        denominator = cost * (1 + task_count) * (1 + run_count)
        other_denominator = other_cost * (1 + other_task) * (1 + other_run)
        left, right = gain * other_denominator, other_gain * denominator
        if left != right:
            return left > right
    left, right = gain * other_cost, other_gain * cost
    if left != right:
        return left > right
    if gain != other_gain:
        return gain > other_gain
    if cost != other_cost:
        return cost < other_cost
    return tie < other_tie


def greedy_actions(
    graph: Graph, seed: int, maximum_budget: int, balanced: bool
) -> Iterable[tuple[str, ...]]:
    state = State(graph)
    step = 0
    while len(state.selected) < maximum_budget and len(state.closed) < len(graph.edges):
        remaining = maximum_budget - len(state.selected)
        candidate_actions: set[tuple[str, ...]] = {
            (node,)
            for node, count in state.selected_neighbors.items()
            if count > 0 and node not in state.selected
        }
        if remaining >= 2:
            candidate_actions.update(
                edge.endpoints
                for index, edge in enumerate(graph.edges)
                if index not in state.closed
                and edge.u not in state.selected
                and edge.v not in state.selected
            )
        best = None
        for missing in candidate_actions:
            cost = len(missing)
            if cost > remaining:
                continue
            gain = state.gain(missing)
            require(gain > 0, "nonpositive closure gain")
            task, run = graph.context[missing[0]]
            require(all(graph.context[node] == (task, run) for node in missing), "action context")
            item = (
                gain,
                cost,
                state.closed_task[task],
                state.closed_run[run],
                hash_key(seed, step, *sorted(missing)),
                missing,
            )
            if better_action(item, best, balanced):
                best = item
        if best is None:
            break
        missing = best[-1]
        state.add(missing)
        yield missing
        step += 1


def nearest_rank(values: list[int], fraction_value: float) -> int:
    require(bool(values), "empty summary")
    ordered = sorted(values)
    return ordered[max(0, math.ceil(fraction_value * len(ordered)) - 1)]


def summarize(rows: list[dict[str, Any]], budgets: list[int]) -> dict[str, Any]:
    result = {}
    integer_fields = (
        "selected_endpoints",
        "closed_edges",
        "parents",
        "tasks",
        "physical_runs",
    )
    for budget in budgets:
        subset = [row for row in rows if row["budget"] == budget]
        result[str(budget)] = {}
        for field in integer_fields:
            values = [int(row[field]) for row in subset]
            result[str(budget)][field] = {
                "minimum": min(values),
                "p05_nearest_rank": nearest_rank(values, 0.05),
                "median_nearest_rank": nearest_rank(values, 0.5),
                "p95_nearest_rank": nearest_rank(values, 0.95),
                "maximum": max(values),
            }
    return result


def share_at_most(row: dict[str, Any], field: str, numerator: int, denominator: int) -> bool:
    value = row[field]
    return value["numerator"] * denominator <= numerator * value["denominator"]


def evaluate_gates(
    method_rows: dict[str, list[dict[str, Any]]], protocol: dict[str, Any]
) -> tuple[dict[str, Any], str]:
    budgets = protocol["acquisition"]["report_budgets"]
    headline = set(protocol["primary_comparison"]["headline_budgets"])
    comparisons: dict[str, Any] = {}
    headline_passes = []
    trajectory_wins = 0
    for budget in budgets:
        uniform = [row for row in method_rows["uniform_edge"] if row["budget"] == budget]
        balanced = [
            row for row in method_rows["balanced_closure_greedy"] if row["budget"] == budget
        ]
        uniform_edges = nearest_rank([row["closed_edges"] for row in uniform], 0.5)
        uniform_tasks = nearest_rank([row["tasks"] for row in uniform], 0.5)
        uniform_runs = nearest_rank([row["physical_runs"] for row in uniform], 0.5)
        balanced_edges = [row["closed_edges"] for row in balanced]
        balanced_tasks = [row["tasks"] for row in balanced]
        balanced_runs = [row["physical_runs"] for row in balanced]
        balanced_median = nearest_rank(balanced_edges, 0.5)
        if balanced_median > uniform_edges:
            trajectory_wins += 1
        yield_pass = min(balanced_edges) * 5 >= uniform_edges * 6
        task_breadth_pass = min(balanced_tasks) * 4 >= uniform_tasks * 3
        run_breadth_pass = min(balanced_runs) * 4 >= uniform_runs * 3
        task_dominance_pass = all(
            share_at_most(row, "maximum_single_task_share", 2, 5) for row in balanced
        )
        run_dominance_pass = all(
            share_at_most(row, "maximum_single_run_share", 1, 10) for row in balanced
        )
        item = {
            "uniform_edge_median_closed_edges": uniform_edges,
            "balanced_greedy_minimum_closed_edges": min(balanced_edges),
            "balanced_greedy_median_closed_edges": balanced_median,
            "uniform_edge_median_tasks": uniform_tasks,
            "balanced_greedy_minimum_tasks": min(balanced_tasks),
            "uniform_edge_median_physical_runs": uniform_runs,
            "balanced_greedy_minimum_physical_runs": min(balanced_runs),
            "yield_gate": yield_pass,
            "task_breadth_gate": task_breadth_pass,
            "run_breadth_gate": run_breadth_pass,
            "task_anti_dominance_gate": task_dominance_pass,
            "run_anti_dominance_gate": run_dominance_pass,
        }
        comparisons[str(budget)] = item
        if budget in headline:
            headline_passes.append(all(value for key, value in item.items() if key.endswith("gate")))
    trajectory_pass = trajectory_wins >= 5
    all_pass = all(headline_passes) and trajectory_pass
    gates = {
        "by_budget": comparisons,
        "headline_all_yield_breadth_and_anti_dominance_pass": all(headline_passes),
        "trajectory_budgets_with_balanced_median_yield_advantage": trajectory_wins,
        "trajectory_consistency_gate": trajectory_pass,
        "all_promotion_gates_pass": all_pass,
    }
    classification = protocol["promotion_gates"][
        "classification_if_all_pass" if all_pass else "classification_otherwise"
    ]
    return gates, classification


def build(args: argparse.Namespace) -> dict[str, Any]:
    protocol, protocol_sha = load_protocol(args.protocol.resolve(), args.protocol_sha256)
    bindings = verify_lineage_certificate(
        protocol, args.lineage_bindings.resolve(), args.lineage_formal.resolve()
    )
    graph, graph_binding = load_graph(args.pair_graph.resolve(), protocol)
    input_sha = {**graph_binding, **bindings}
    budgets = [int(value) for value in protocol["acquisition"]["report_budgets"]]
    maximum_budget = int(protocol["acquisition"]["maximum_endpoint_budget"])
    require(budgets == sorted(set(budgets)) and budgets[-1] == maximum_budget, "budgets")
    random_start, random_stop = protocol["acquisition"]["random_baseline_seeds"][
        "first_seed_in_half_open_range"
    ]
    greedy_start, greedy_stop = protocol["acquisition"]["greedy_tie_seeds"][
        "first_seed_in_half_open_range"
    ]
    method_rows: dict[str, list[dict[str, Any]]] = {}
    for method in ("uniform_node", "uniform_edge"):
        rows = []
        for seed in range(int(random_start), int(random_stop)):
            actions = (
                uniform_node_actions(graph, seed)
                if method == "uniform_node"
                else uniform_edge_actions(graph, seed, maximum_budget)
            )
            rows.extend(snapshots_from_actions(graph, seed, budgets, actions))
        method_rows[method] = rows
    for method, balanced in (("closure_greedy", False), ("balanced_closure_greedy", True)):
        rows = []
        for seed in range(int(greedy_start), int(greedy_stop)):
            actions = greedy_actions(graph, seed, maximum_budget, balanced)
            rows.extend(snapshots_from_actions(graph, seed, budgets, actions))
        method_rows[method] = rows
    gates, classification = evaluate_gates(method_rows, protocol)
    return {
        "protocol": RESULT_PROTOCOL,
        "status": "COMPLETE",
        "protocol_sha256": protocol_sha,
        "input_sha256": input_sha,
        "graph_census": {
            "pairs": len(graph.edges),
            "endpoints": len(graph.nodes),
            "parents": len({edge.parent for edge in graph.edges}),
            "tasks": len({edge.task for edge in graph.edges}),
            "physical_runs": len({edge.run for edge in graph.edges}),
        },
        "methods": {
            method: {
                "rows": rows,
                "summary_by_budget": summarize(rows, budgets),
            }
            for method, rows in method_rows.items()
        },
        "primary_gates": gates,
        "classification": classification,
        "scope": {
            "aggregate_only": True,
            "row_endpoint_parent_task_run_identities_emitted": False,
            "pair_orientation_gap_grade_code_prediction_runtime_used": False,
            "prospective_values_read": False,
            "gpu_api_model_fit_base_update": "0/0/0/0",
        },
    }


def secure_write(path: Path, value: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    descriptor = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8", newline="\n") as handle:
            handle.write(canonical(value) + "\n")
            handle.flush()
            os.fsync(handle.fileno())
    except BaseException:
        try:
            path.unlink()
        except FileNotFoundError:
            pass
        raise


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--protocol", type=Path, required=True)
    parser.add_argument("--protocol-sha256", required=True)
    parser.add_argument("--pair-graph", type=Path, required=True)
    parser.add_argument("--lineage-bindings", type=Path, required=True)
    parser.add_argument("--lineage-formal", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    result = build(args)
    secure_write(args.output.resolve(), result)
    print(canonical({
        "status": result["status"],
        "classification": result["classification"],
        "protocol_sha256": result["protocol_sha256"],
        "output_sha256": raw_sha256(args.output.resolve()),
        "scope": result["scope"],
    }))


if __name__ == "__main__":
    main()
