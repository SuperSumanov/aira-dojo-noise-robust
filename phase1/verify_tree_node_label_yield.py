#!/usr/bin/env python3
"""Independent reconstruction of the tree-node label-yield result.

This module intentionally does not import ``tree_node_label_yield``.  It rebuilds
the topology, all acquisition trajectories, summaries, and promotion gates.
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


class VerificationError(RuntimeError):
    pass


def check(condition: bool, message: str) -> None:
    if not condition:
        raise VerificationError(message)


def encode_json(value: Any) -> str:
    return json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
    )


def file_hash(path: Path) -> str:
    check(path.is_file() and not path.is_symlink(), f"unsafe path: {path}")
    value = hashlib.sha256()
    with path.open("rb") as stream:
        while block := stream.read(8 << 20):
            value.update(block)
    return value.hexdigest()


def canonical_file(path: Path) -> bytes:
    check(path.is_file() and not path.is_symlink(), f"unsafe path: {path}")
    decoded = path.read_bytes().decode("utf-8")
    return decoded.replace("\r\n", "\n").replace("\r", "\n").encode()


def canonical_file_binding(path: Path) -> tuple[str, int]:
    content = canonical_file(path)
    return hashlib.sha256(content).hexdigest(), len(content)


def digest_parts(*values: Any) -> str:
    joined = "\0".join(str(value) for value in values)
    return hashlib.sha256(joined.encode()).hexdigest()


@dataclass(frozen=True)
class Pair:
    left: str
    right: str
    parent: str
    task: str
    run: str


@dataclass
class Topology:
    pairs: list[Pair]
    vertices: tuple[str, ...]
    adjacency: dict[str, tuple[int, ...]]
    vertex_context: dict[str, tuple[str, str]]


def protocol_from(path: Path, expected_hash: str) -> tuple[dict[str, Any], str]:
    observed = file_hash(path)
    check(observed == expected_hash, "protocol hash")
    protocol = json.loads(path.read_text(encoding="utf-8"))
    check(protocol.get("protocol") == "tree-node-to-sibling-label-yield-v1", "protocol")
    check(
        protocol.get("status")
        == "FROZEN_AFTER_AGGREGATE_TOPOLOGY_TOTALS_BEFORE_ACQUISITION_CURVES",
        "freeze status",
    )
    check(protocol["estimand"]["not_multifidelity"] is True, "multifidelity drift")
    check(protocol["analysis"]["producer_and_independent_verifier_must_match_exactly"] is True, "verification drift")
    return protocol, observed


def certificate_bindings(
    protocol: dict[str, Any], package_path: Path, result_path: Path
) -> dict[str, str]:
    frozen = protocol["immutable_inputs"]["lineage_audit_bindings"]
    package_hash, result_hash = file_hash(package_path), file_hash(result_path)
    check(package_hash == frozen["sha256"], "package binding")
    check(result_hash == frozen["formal_result_sha256"], "certificate result binding")
    package = json.loads(package_path.read_text(encoding="utf-8"))
    result = json.loads(result_path.read_text(encoding="utf-8"))
    required = frozen["required_classification"]
    check(package["classification"] == required == result["classification"], "classification binding")
    check(package["formal"]["producer_a_sha256"] == result_hash, "package result closure")
    train = result["scientific"]["set_profiles"]["train:b0"]
    relation = train["relation_counts"]
    check(train["all_rows"]["pairs"] == 4263, "certificate rows")
    check(relation["cross_run_declared_context"] == 0, "certificate cross-run")
    check(relation["same_run_declared_context_non_sibling"] == 0, "certificate non-sibling")
    check(
        relation["parent_present_verified_direct_sibling"]
        + relation["lineage_verified_orphan_parent_sibling"]
        == 4263,
        "certificate relation closure",
    )
    return {"lineage_bindings": package_hash, "lineage_formal_result": result_hash}


def topology_from(path: Path, protocol: dict[str, Any]) -> tuple[Topology, str]:
    frozen = protocol["immutable_inputs"]["pair_graph"]
    observed, byte_count = canonical_file_binding(path)
    check(observed == frozen["sha256"], "pair graph hash")
    check(byte_count == frozen["git_blob_bytes"], "pair graph bytes")
    pairs: list[Pair] = []
    edge_keys: set[tuple[str, str]] = set()
    contexts: dict[str, tuple[str, str]] = {}
    parent_contexts: dict[str, tuple[str, str]] = {}
    lines = canonical_file(path).decode().splitlines()
    check(len(lines) == frozen["rows"], "pair graph rows")
    for offset, text in enumerate(lines, 1):
        check(bool(text), f"empty row {offset}")
        row = json.loads(text)
        fields = (row.get("better"), row.get("worse"), row.get("parent"), row.get("task"), row.get("run_id"))
        check(all(isinstance(value, str) and value for value in fields), f"row schema {offset}")
        first, second, parent, task, run = fields
        check(row.get("intask_split") == "train", f"row split {offset}")
        check(row.get("budget") == 0, f"row budget {offset}")
        left, right = sorted((first, second))
        check(left != right and (left, right) not in edge_keys, f"edge uniqueness {offset}")
        edge_keys.add((left, right))
        context = (task, run)
        for vertex in (left, right):
            check(contexts.setdefault(vertex, context) == context, f"vertex context {offset}")
        check(parent_contexts.setdefault(parent, context) == context, f"parent context {offset}")
        pairs.append(Pair(left, right, parent, task, run))
    mutable: dict[str, list[int]] = defaultdict(list)
    for index, pair in enumerate(pairs):
        mutable[pair.left].append(index)
        mutable[pair.right].append(index)
    topology = Topology(
        pairs,
        tuple(sorted(contexts)),
        {vertex: tuple(indices) for vertex, indices in mutable.items()},
        contexts,
    )
    known = protocol["known_before_freeze"]
    observed_counts = {
        "pairs": len(pairs),
        "endpoints": len(contexts),
        "parents": len({pair.parent for pair in pairs}),
        "tasks": len({pair.task for pair in pairs}),
        "physical_runs": len({pair.run for pair in pairs}),
    }
    for key, value in observed_counts.items():
        check(value == known[key], f"known topology {key}")
    return topology, observed


def ratio(numerator: int, denominator: int) -> dict[str, Any]:
    check(denominator > 0, "ratio denominator")
    common = math.gcd(numerator, denominator)
    return {
        "numerator": numerator // common,
        "denominator": denominator // common,
        "decimal_17g": format(numerator / denominator, ".17g"),
    }


class Replay:
    def __init__(self, topology: Topology) -> None:
        self.topology = topology
        self.chosen: set[str] = set()
        self.resolved: set[int] = set()
        self.chosen_neighbors: Counter[str] = Counter()
        self.by_task: Counter[str] = Counter()
        self.by_run: Counter[str] = Counter()
        self.by_parent: Counter[str] = Counter()

    def marginal(self, action: tuple[str, ...]) -> int:
        if len(action) == 1:
            return self.chosen_neighbors[action[0]]
        check(len(action) == 2, "action width")
        return self.chosen_neighbors[action[0]] + self.chosen_neighbors[action[1]] + 1

    def reveal(self, action: tuple[str, ...]) -> None:
        check(all(vertex not in self.chosen for vertex in action), "action duplication")
        for vertex in action:
            self.chosen.add(vertex)
            for index in self.topology.adjacency[vertex]:
                if index in self.resolved:
                    continue
                pair = self.topology.pairs[index]
                neighbor = pair.right if pair.left == vertex else pair.left
                if neighbor in self.chosen:
                    self.resolved.add(index)
                    self.by_task[pair.task] += 1
                    self.by_run[pair.run] += 1
                    self.by_parent[pair.parent] += 1
                else:
                    self.chosen_neighbors[neighbor] += 1

    def receipt(self, seed: int, budget: int) -> dict[str, Any]:
        resolved = len(self.resolved)
        task_squares = sum(count * count for count in self.by_task.values())
        run_squares = sum(count * count for count in self.by_run.values())
        return {
            "seed": seed,
            "budget": budget,
            "selected_endpoints": len(self.chosen),
            "closed_edges": resolved,
            "closed_edges_per_endpoint": ratio(resolved, max(1, len(self.chosen))),
            "parents": len(self.by_parent),
            "tasks": len(self.by_task),
            "physical_runs": len(self.by_run),
            "maximum_single_task_share": ratio(max(self.by_task.values(), default=0), max(1, resolved)),
            "maximum_single_run_share": ratio(max(self.by_run.values(), default=0), max(1, resolved)),
            "task_effective_count": ratio(resolved * resolved, max(1, task_squares)),
            "run_effective_count": ratio(resolved * resolved, max(1, run_squares)),
        }


def trajectory(
    topology: Topology,
    seed: int,
    checkpoints: list[int],
    actions: Iterable[tuple[str, ...]],
) -> list[dict[str, Any]]:
    replay = Replay(topology)
    receipts: list[dict[str, Any]] = []
    checkpoint = 0
    for action in actions:
        after = len(replay.chosen) + len(action)
        while checkpoint < len(checkpoints) and checkpoints[checkpoint] < after:
            receipts.append(replay.receipt(seed, checkpoints[checkpoint]))
            checkpoint += 1
        replay.reveal(action)
        if checkpoint == len(checkpoints):
            break
    while checkpoint < len(checkpoints):
        receipts.append(replay.receipt(seed, checkpoints[checkpoint]))
        checkpoint += 1
    return receipts


def node_plan(topology: Topology, seed: int) -> Iterable[tuple[str, ...]]:
    ordered = sorted(topology.vertices, key=lambda vertex: digest_parts(seed, "NODE", vertex))
    return ((vertex,) for vertex in ordered)


def edge_plan(topology: Topology, seed: int, limit: int) -> Iterable[tuple[str, ...]]:
    chosen: set[str] = set()
    ordered = sorted(
        topology.pairs,
        key=lambda pair: digest_parts(seed, "EDGE", pair.left, pair.right),
    )
    for pair in ordered:
        action = tuple(vertex for vertex in (pair.left, pair.right) if vertex not in chosen)
        if not action or len(chosen) + len(action) > limit:
            continue
        chosen.update(action)
        yield action


def outranks(
    challenger: tuple[int, int, int, int, str, tuple[str, ...]],
    current: tuple[int, int, int, int, str, tuple[str, ...]] | None,
    balance: bool,
) -> bool:
    if current is None:
        return True
    gain, cost, task_load, run_load, token, _ = challenger
    old_gain, old_cost, old_task, old_run, old_token, _ = current
    if balance:
        challenger_denominator = cost * (task_load + 1) * (run_load + 1)
        current_denominator = old_cost * (old_task + 1) * (old_run + 1)
        challenger_product = gain * current_denominator
        current_product = old_gain * challenger_denominator
        if challenger_product != current_product:
            return challenger_product > current_product
    challenger_product = gain * old_cost
    current_product = old_gain * cost
    if challenger_product != current_product:
        return challenger_product > current_product
    if gain != old_gain:
        return gain > old_gain
    if cost != old_cost:
        return cost < old_cost
    return token < old_token


def greedy_plan(
    topology: Topology, seed: int, limit: int, balance: bool
) -> Iterable[tuple[str, ...]]:
    replay = Replay(topology)
    step = 0
    while len(replay.chosen) < limit and len(replay.resolved) < len(topology.pairs):
        room = limit - len(replay.chosen)
        available: set[tuple[str, ...]] = set()
        for vertex, count in replay.chosen_neighbors.items():
            if count and vertex not in replay.chosen:
                available.add((vertex,))
        if room > 1:
            for index, pair in enumerate(topology.pairs):
                if (
                    index not in replay.resolved
                    and pair.left not in replay.chosen
                    and pair.right not in replay.chosen
                ):
                    available.add((pair.left, pair.right))
        winner = None
        for action in available:
            if len(action) > room:
                continue
            marginal = replay.marginal(action)
            check(marginal > 0, "zero marginal candidate")
            task, run = topology.vertex_context[action[0]]
            check(all(topology.vertex_context[vertex] == (task, run) for vertex in action), "action context")
            candidate = (
                marginal,
                len(action),
                replay.by_task[task],
                replay.by_run[run],
                digest_parts(seed, step, *sorted(action)),
                action,
            )
            if outranks(candidate, winner, balance):
                winner = candidate
        if winner is None:
            return
        action = winner[-1]
        replay.reveal(action)
        yield action
        step += 1


def rank_statistic(values: list[int], proportion: float) -> int:
    check(bool(values), "empty statistic")
    values = sorted(values)
    return values[max(0, math.ceil(proportion * len(values)) - 1)]


def method_summary(rows: list[dict[str, Any]], budgets: list[int]) -> dict[str, Any]:
    output: dict[str, Any] = {}
    fields = ("selected_endpoints", "closed_edges", "parents", "tasks", "physical_runs")
    for budget in budgets:
        budget_rows = [row for row in rows if row["budget"] == budget]
        output[str(budget)] = {}
        for field in fields:
            values = [int(row[field]) for row in budget_rows]
            output[str(budget)][field] = {
                "minimum": min(values),
                "p05_nearest_rank": rank_statistic(values, 0.05),
                "median_nearest_rank": rank_statistic(values, 0.5),
                "p95_nearest_rank": rank_statistic(values, 0.95),
                "maximum": max(values),
            }
    return output


def no_more_than(row: dict[str, Any], field: str, top: int, bottom: int) -> bool:
    observed = row[field]
    return observed["numerator"] * bottom <= top * observed["denominator"]


def gate_receipt(rows: dict[str, list[dict[str, Any]]], protocol: dict[str, Any]) -> tuple[dict[str, Any], str]:
    budgets = protocol["acquisition"]["report_budgets"]
    headlines = set(protocol["primary_comparison"]["headline_budgets"])
    table: dict[str, Any] = {}
    headline_results = []
    winning_budgets = 0
    for budget in budgets:
        random_rows = [row for row in rows["uniform_edge"] if row["budget"] == budget]
        method_rows = [row for row in rows["balanced_closure_greedy"] if row["budget"] == budget]
        random_edges = rank_statistic([row["closed_edges"] for row in random_rows], 0.5)
        random_tasks = rank_statistic([row["tasks"] for row in random_rows], 0.5)
        random_runs = rank_statistic([row["physical_runs"] for row in random_rows], 0.5)
        method_edges = [row["closed_edges"] for row in method_rows]
        method_tasks = [row["tasks"] for row in method_rows]
        method_runs = [row["physical_runs"] for row in method_rows]
        method_median = rank_statistic(method_edges, 0.5)
        winning_budgets += int(method_median > random_edges)
        entry = {
            "uniform_edge_median_closed_edges": random_edges,
            "balanced_greedy_minimum_closed_edges": min(method_edges),
            "balanced_greedy_median_closed_edges": method_median,
            "uniform_edge_median_tasks": random_tasks,
            "balanced_greedy_minimum_tasks": min(method_tasks),
            "uniform_edge_median_physical_runs": random_runs,
            "balanced_greedy_minimum_physical_runs": min(method_runs),
            "yield_gate": min(method_edges) * 5 >= random_edges * 6,
            "task_breadth_gate": min(method_tasks) * 4 >= random_tasks * 3,
            "run_breadth_gate": min(method_runs) * 4 >= random_runs * 3,
            "task_anti_dominance_gate": all(
                no_more_than(row, "maximum_single_task_share", 2, 5) for row in method_rows
            ),
            "run_anti_dominance_gate": all(
                no_more_than(row, "maximum_single_run_share", 1, 10) for row in method_rows
            ),
        }
        table[str(budget)] = entry
        if budget in headlines:
            headline_results.append(all(value for key, value in entry.items() if key.endswith("gate")))
    trajectory_pass = winning_budgets >= 5
    all_pass = all(headline_results) and trajectory_pass
    receipt = {
        "by_budget": table,
        "headline_all_yield_breadth_and_anti_dominance_pass": all(headline_results),
        "trajectory_budgets_with_balanced_median_yield_advantage": winning_budgets,
        "trajectory_consistency_gate": trajectory_pass,
        "all_promotion_gates_pass": all_pass,
    }
    key = "classification_if_all_pass" if all_pass else "classification_otherwise"
    return receipt, protocol["promotion_gates"][key]


def reconstruct(args: argparse.Namespace) -> tuple[dict[str, Any], str]:
    protocol, protocol_hash = protocol_from(args.protocol.resolve(), args.protocol_sha256)
    certificate = certificate_bindings(
        protocol, args.lineage_bindings.resolve(), args.lineage_formal.resolve()
    )
    topology, pair_hash = topology_from(args.pair_graph.resolve(), protocol)
    budgets = [int(value) for value in protocol["acquisition"]["report_budgets"]]
    maximum = int(protocol["acquisition"]["maximum_endpoint_budget"])
    check(budgets == sorted(set(budgets)) and budgets[-1] == maximum, "budget contract")
    random_first, random_last = protocol["acquisition"]["random_baseline_seeds"]["first_seed_in_half_open_range"]
    greedy_first, greedy_last = protocol["acquisition"]["greedy_tie_seeds"]["first_seed_in_half_open_range"]
    all_rows: dict[str, list[dict[str, Any]]] = {}
    for method in ("uniform_node", "uniform_edge"):
        rows = []
        for seed in range(int(random_first), int(random_last)):
            plan = node_plan(topology, seed) if method == "uniform_node" else edge_plan(topology, seed, maximum)
            rows.extend(trajectory(topology, seed, budgets, plan))
        all_rows[method] = rows
    for method, balance in (("closure_greedy", False), ("balanced_closure_greedy", True)):
        rows = []
        for seed in range(int(greedy_first), int(greedy_last)):
            rows.extend(trajectory(topology, seed, budgets, greedy_plan(topology, seed, maximum, balance)))
        all_rows[method] = rows
    gates, classification = gate_receipt(all_rows, protocol)
    expected = {
        "protocol": "tree-node-to-sibling-label-yield-result-v1",
        "status": "COMPLETE",
        "protocol_sha256": protocol_hash,
        "input_sha256": {"pair_graph": pair_hash, **certificate},
        "graph_census": {
            "pairs": len(topology.pairs),
            "endpoints": len(topology.vertices),
            "parents": len({pair.parent for pair in topology.pairs}),
            "tasks": len({pair.task for pair in topology.pairs}),
            "physical_runs": len({pair.run for pair in topology.pairs}),
        },
        "methods": {
            method: {"rows": rows, "summary_by_budget": method_summary(rows, budgets)}
            for method, rows in all_rows.items()
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
    return expected, protocol_hash


def verify(args: argparse.Namespace) -> dict[str, Any]:
    result_path = args.result.resolve()
    result_hash = file_hash(result_path)
    check(result_hash == args.result_sha256, "result hash")
    observed = json.loads(result_path.read_text(encoding="utf-8"))
    expected, protocol_hash = reconstruct(args)
    check(observed == expected, "producer result differs from independent reconstruction")
    return {
        "protocol": "tree-node-to-sibling-label-yield-independent-verifier-v1",
        "status": "INDEPENDENT_RECONSTRUCTION_EXACT",
        "protocol_sha256": protocol_hash,
        "source_result_sha256": result_hash,
        "classification": expected["classification"],
        "all_aggregate_fields_equal": True,
        "scope": {
            "identities_emitted": False,
            "pair_orientation_gap_grade_code_prediction_runtime_used": False,
            "prospective_values_read": False,
            "gpu_api_model_fit_base_update": "0/0/0/0",
        },
    }


def write_exclusive(path: Path, value: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    descriptor = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8", newline="\n") as stream:
            stream.write(encode_json(value) + "\n")
            stream.flush()
            os.fsync(stream.fileno())
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
    parser.add_argument("--result", type=Path, required=True)
    parser.add_argument("--result-sha256", required=True)
    parser.add_argument("--output", type=Path, required=True)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    receipt = verify(args)
    write_exclusive(args.output.resolve(), receipt)
    print(encode_json(receipt))


if __name__ == "__main__":
    main()
