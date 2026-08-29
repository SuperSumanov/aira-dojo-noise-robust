#!/usr/bin/env python3
"""Independent graph-level verifier for Target-522 yield-guarded breadth."""

from __future__ import annotations

import argparse
from collections import Counter, defaultdict
from fractions import Fraction
import hashlib
import itertools
import json
import math
import os
from pathlib import Path
import re
from typing import Any
import warnings

from phase1 import falsify_historical_run_split_breadth_pareto as graph_impl
from phase1 import verify_tree_within_stratum_forward_target522 as target_check


PROTOCOL_NAME = "yield-guarded-breadth-forward-target522-v1"
PUBLIC_PROTOCOL = "yield-guarded-breadth-forward-target522-public-result-v1"
PRIVATE_PROTOCOL = "yield-guarded-breadth-forward-target522-private-witness-v1"
VERIFY_PROTOCOL = "independent-yield-guarded-breadth-forward-target522-verifier-v1"
PAIR_FIELDS = {"task", "run_id", "parent", "left", "right"}
SHA_RE = re.compile(r"[0-9a-f]{64}")


class BreadthVerificationError(RuntimeError):
    pass


def check(condition: bool, message: str) -> None:
    if not condition:
        raise BreadthVerificationError(message)


def canonical_bytes(value: Any) -> bytes:
    return (
        json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
        + "\n"
    ).encode()


def canonical_sha(value: Any) -> str:
    return hashlib.sha256(canonical_bytes(value)).hexdigest()


def object_file(path: Path) -> dict[str, Any]:
    value = target_check.object_file(path)
    check(isinstance(value, dict), "object root")
    return value


def protocol_file(path: Path, expected_sha: str) -> tuple[dict[str, Any], str]:
    check(SHA_RE.fullmatch(expected_sha) is not None, "protocol SHA syntax")
    actual = target_check.file_digest(path)
    check(actual == expected_sha, "protocol SHA")
    protocol = object_file(path)
    check(protocol.get("protocol") == PROTOCOL_NAME, "protocol name")
    check(
        protocol.get("status") == "FROZEN_BEFORE_TARGET522_SELECTION_OR_SIBLING_GRAPH_PROFILE",
        "freeze status",
    )
    freeze = protocol.get("freeze_state") or {}
    check(freeze.get("candidate_identity_counts_or_profile_seen") is False, "candidate pre-read")
    observation = freeze.get("freeze_observation") or {}
    check(observation.get("target522_selection_complete_present") is False, "selection pre-complete")
    check(observation.get("target522_selection_failed_present") is False, "selection pre-failed")
    check(observation.get("prospective_values_read") is False, "value pre-read")
    return protocol, actual


def independent_selection_and_increment(
    state_root: Path,
    selection_root: Path,
    repo_root: Path,
    protocol: dict[str, Any],
) -> tuple[dict[str, Any], target_check.SnapshotView, dict[str, Any], dict[str, Any], dict[str, Any]]:
    binding = protocol["freeze_state"]["target522_selection_protocol"]
    original_path = repo_root / binding["path"]
    original, original_sha = target_check.protocol_file(original_path, binding["sha256"])
    monitor_binding = protocol["freeze_state"]["target522_selection_monitor"]
    monitor_path = repo_root / monitor_binding["path"]
    check(target_check.file_digest(monitor_path) == monitor_binding["sha256"], "monitor SHA")
    selection = target_check.inspect_selection(
        selection_root, original_path, monitor_path, original, original_sha
    )
    check(selection["monitor_source_sha256"] == monitor_binding["sha256"], "selection monitor SHA")
    check(
        str(selection_root.resolve())
        == protocol["freeze_state"]["target522_selection_root"],
        "selection root",
    )
    baseline = target_check.collect_snapshot(state_root, selection["baseline"])
    candidate = target_check.collect_snapshot(state_root, selection["candidate"])
    cards, runs, append_only = target_check.incremental_population(
        baseline, candidate, original
    )
    check(
        len(runs) >= protocol["population"]["physical_run_increment_minimum"],
        "increment minimum",
    )
    return selection, candidate, cards, runs, append_only


def groups(cards: dict[str, dict[str, Any]]) -> dict[tuple[str, str, str], set[str]]:
    answer: dict[tuple[str, str, str], set[str]] = defaultdict(set)
    for identifier, card in cards.items():
        parent = card["parent"]
        check(isinstance(parent, str) and parent, "empty parent")
        answer[(card["task"], card["run"], parent)].add(identifier)
    return answer


def independent_pair_graph(
    state_root: Path,
    candidate: target_check.SnapshotView,
    cards: dict[str, dict[str, Any]],
    runs: dict[str, dict[str, Any]],
) -> tuple[Any, dict[str, Any]]:
    state = state_root.resolve()
    run_ids = set(runs)
    observed_rows: list[dict[str, str]] = []
    hashes: list[str] = []
    contributing = 0
    for raw in candidate.registry_lines:
        entry = json.loads(raw.decode("utf-8"))
        intake = Path(entry["intake_dir"])
        check(
            intake.resolve().parent == state / "intakes"
            and intake.resolve().name == entry["drop_id"],
            "intake location",
        )
        summary = object_file(intake / "summary.json")
        pair_sha = summary.get("outputs", {}).get("eligible_structural_pairs_sha256")
        check(isinstance(pair_sha, str) and SHA_RE.fullmatch(pair_sha), "pair digest")
        pair_path = intake / "eligible_structural_pairs.jsonl"
        check(target_check.file_digest(pair_path) == pair_sha, "pair digest binding")
        raw_file = pair_path.read_bytes()
        check(target_check.SECRET_SHAPE.search(raw_file) is None, "secret-shaped pair data")
        hashes.append(pair_sha)
        local_count = 0
        for row, _line in target_check.line_objects(pair_path):
            check(set(row) == PAIR_FIELDS, "pair fields")
            if row["run_id"] not in run_ids:
                continue
            check(
                all(isinstance(row[key], str) and row[key] for key in PAIR_FIELDS),
                "pair value",
            )
            check(row["left"] < row["right"], "pair canonical order")
            observed_rows.append(row)
            local_count += 1
        contributing += int(local_count > 0)
    expected = {
        (task, run, parent, left, right)
        for (task, run, parent), children in groups(cards).items()
        for left, right in itertools.combinations(sorted(children), 2)
    }
    observed = {
        (row["task"], row["run_id"], row["parent"], row["left"], row["right"])
        for row in observed_rows
    }
    check(len(observed) == len(observed_rows), "duplicate pair")
    check(observed == expected, "pair population not exact clique")
    graph = graph_impl.graph_from_edges(
        [
            graph_impl.engine.Edge(left, right, parent, task, run)
            for task, run, parent, left, right in sorted(observed)
        ]
    )
    fingerprint = hashlib.sha256(
        "\n".join(
            hashlib.sha256("\0".join(item).encode()).hexdigest()
            for item in sorted(observed)
        ).encode()
    ).hexdigest()
    return graph, {
        "all_candidate_intake_pair_files_count": len(hashes),
        "increment_contributing_pair_files_count": contributing,
        "candidate_pair_sha_multiset_sha256": canonical_sha(sorted(hashes)),
        "increment_pair_graph_sha256": fingerprint,
        "structural_pair_files_equal_exact_observed_sibling_cliques": True,
    }


def fraction(numerator: int, denominator: int) -> dict[str, Any]:
    value = Fraction(numerator, denominator) if denominator else Fraction(0, 1)
    return {
        "numerator": value.numerator,
        "denominator": value.denominator,
        "decimal_17g": format(float(value), ".17g"),
    }


def census_and_support(graph: Any, protocol: dict[str, Any]) -> tuple[dict[str, Any], dict[str, bool]]:
    tasks = Counter(edge.task for edge in graph.edges)
    runs = Counter(edge.run for edge in graph.edges)
    pairs = len(graph.edges)
    census = {
        "pairs": pairs,
        "endpoints": len(graph.nodes),
        "parents": len({edge.parent for edge in graph.edges}),
        "physical_runs": len(runs),
        "tasks": len(tasks),
        "maximum_single_task_pair_share": fraction(max(tasks.values(), default=0), max(1, pairs)),
        "maximum_single_run_pair_share": fraction(max(runs.values(), default=0), max(1, pairs)),
    }
    fixed = protocol["support_gates_before_acquisition"]
    support = {
        "minimum_pairs": pairs >= fixed["minimum_pairs"],
        "minimum_endpoints": census["endpoints"] >= fixed["minimum_endpoints"],
        "minimum_parents": census["parents"] >= fixed["minimum_parents"],
        "minimum_physical_runs": census["physical_runs"] >= fixed["minimum_physical_runs"],
        "minimum_tasks": census["tasks"] >= fixed["minimum_tasks"],
        "maximum_single_task_pair_share": census["maximum_single_task_pair_share"]["numerator"] * 3
        <= census["maximum_single_task_pair_share"]["denominator"],
        "maximum_single_run_pair_share": census["maximum_single_run_pair_share"]["numerator"] * 10
        <= census["maximum_single_run_pair_share"]["denominator"],
    }
    return census, support


def budget_values(graph: Any, protocol: dict[str, Any]) -> list[int]:
    acquisition = protocol["acquisition"]
    values = [
        math.floor(len(graph.nodes) * value / acquisition["budget_fraction_denominator"])
        for value in acquisition["budget_fraction_numerators"]
    ]
    check(values == sorted(set(values)) and len(values) == 6 and values[0] >= 2, "budgets")
    return values


def exact_order(graph: Any, seed: int, maximum: int) -> list[str]:
    engine = graph_impl.engine
    selected: set[str] = set()
    order: list[str] = []
    edges = sorted(
        graph.edges, key=lambda edge: engine.hash_key(seed, "EDGE", edge.u, edge.v)
    )
    for edge in edges:
        missing = [node for node in (edge.u, edge.v) if node not in selected]
        if not missing or len(selected) + len(missing) > maximum:
            continue
        missing.sort(
            key=lambda node: engine.hash_key(
                seed, "EDGE-ENDPOINT", edge.u, edge.v, node
            )
        )
        for node in missing:
            check(node not in selected, "duplicate order endpoint")
            selected.add(node)
            order.append(node)
        if len(order) == maximum:
            return order
    remaining = sorted(
        set(graph.nodes) - selected,
        key=lambda node: engine.hash_key(seed, "EDGE-FILL", node),
    )
    order.extend(remaining[: maximum - len(order)])
    check(len(order) == maximum and len(set(order)) == maximum, "order closure")
    return order


def selection_metrics(graph: Any, selected: set[str], budget: int) -> dict[str, Any]:
    closed = [edge for edge in graph.edges if edge.u in selected and edge.v in selected]
    tasks = Counter(edge.task for edge in closed)
    runs = Counter(edge.run for edge in closed)
    return {
        "budget": budget,
        "selected_endpoints": len(selected),
        "closed_edges": len(closed),
        "parents": len({edge.parent for edge in closed}),
        "tasks": len(tasks),
        "physical_runs": len(runs),
        "maximum_single_task_share": fraction(max(tasks.values(), default=0), max(1, len(closed))),
        "maximum_single_run_share": fraction(max(runs.values(), default=0), max(1, len(closed))),
    }


def independent_baseline(graph: Any, budgets: list[int]) -> dict[str, Any]:
    rows: list[dict[str, Any]] = []
    old_underfill = 0
    for seed in range(256):
        order = exact_order(graph, seed, budgets[-1])
        rows.extend(selection_metrics(graph, set(order[:budget]), budget) | {"seed": seed} for budget in budgets)
        old = graph_impl.engine.snapshots_from_actions(
            graph,
            seed,
            budgets,
            graph_impl.engine.uniform_edge_actions(graph, seed, budgets[-1]),
        )
        old_underfill += sum(int(row["selected_endpoints"] != row["budget"]) for row in old)
    check(len(rows) == 256 * len(budgets), "baseline rows")
    by_budget: dict[str, Any] = {}
    for budget in budgets:
        subset = [row for row in rows if row["budget"] == budget]
        by_budget[str(budget)] = {
            field: graph_impl.engine.nearest_rank(
                [int(row[field]) for row in subset], 0.5
            )
            for field in ("closed_edges", "parents", "tasks", "physical_runs")
        }
    integrated: dict[str, int] = {}
    for field in ("closed_edges", "tasks", "physical_runs"):
        sums: dict[int, int] = defaultdict(int)
        for row in rows:
            sums[row["seed"]] += int(row[field])
        integrated[field] = graph_impl.engine.nearest_rank(list(sums.values()), 0.5)
    return {
        "seeds": 256,
        "rows": len(rows),
        "all_rows_exact_endpoint_budget": all(
            row["selected_endpoints"] == row["budget"] for row in rows
        ),
        "by_budget_nearest_rank_median": by_budget,
        "integrated_trajectory_nearest_rank_median": integrated,
        "historical_atomic_underfill_diagnostic_rows": old_underfill,
    }


def floors_from_baseline(baseline: dict[str, Any], budgets: list[int]) -> dict[str, Any]:
    integrated = baseline["integrated_trajectory_nearest_rank_median"]
    terminal = baseline["by_budget_nearest_rank_median"][str(budgets[-1])]
    return {
        "pointwise_closed_edges": [
            baseline["by_budget_nearest_rank_median"][str(value)]["closed_edges"]
            for value in budgets
        ],
        "integrated_closed_edges": integrated["closed_edges"],
        "integrated_tasks": math.ceil(6 * integrated["tasks"] / 5),
        "integrated_physical_runs": math.ceil(11 * integrated["physical_runs"] / 10),
        "terminal_parents": math.ceil(9 * terminal["parents"] / 10),
    }


def witness_gates(metrics: list[dict[str, Any]], floors: dict[str, Any]) -> dict[str, bool]:
    integrated = {
        field: sum(int(row[field]) for row in metrics)
        for field in ("closed_edges", "tasks", "physical_runs")
    }
    terminal = metrics[-1]
    return {
        "exact_endpoint_budget_all_checkpoints": all(
            row["selected_endpoints"] == row["budget"] for row in metrics
        ),
        "all_six_pointwise_closed_edge_counts_at_least_uniform_median": all(
            row["closed_edges"] >= floor
            for row, floor in zip(metrics, floors["pointwise_closed_edges"])
        ),
        "integrated_closed_edges_at_least_uniform_trajectory_median": integrated["closed_edges"]
        >= floors["integrated_closed_edges"],
        "integrated_task_breadth_at_least_6_over_5": integrated["tasks"]
        >= floors["integrated_tasks"],
        "integrated_run_breadth_at_least_11_over_10": integrated["physical_runs"]
        >= floors["integrated_physical_runs"],
        "terminal_parent_breadth_at_least_9_over_10": terminal["parents"]
        >= floors["terminal_parents"],
        "terminal_maximum_single_task_edge_share_at_most_1_over_3": terminal[
            "maximum_single_task_share"
        ]["numerator"]
        * 3
        <= terminal["maximum_single_task_share"]["denominator"],
        "terminal_maximum_single_run_edge_share_at_most_1_over_10": terminal[
            "maximum_single_run_share"
        ]["numerator"]
        * 10
        <= terminal["maximum_single_run_share"]["denominator"],
    }


def independent_solver_status(
    graph: Any, budgets: list[int], floors: dict[str, Any], time_limit: float
) -> str:
    import numpy as np
    from scipy.optimize import Bounds, LinearConstraint, milp
    from scipy.sparse import coo_matrix

    nodes = list(graph.nodes)
    tasks = sorted({edge.task for edge in graph.edges})
    runs = sorted({edge.run for edge in graph.edges})
    parents = sorted({edge.parent for edge in graph.edges})
    index: dict[tuple[Any, ...], int] = {}

    def allocate(key: tuple[Any, ...]) -> None:
        check(key not in index, "duplicate independent MILP variable")
        index[key] = len(index)

    for step in range(len(budgets)):
        for node in nodes:
            allocate(("x", step, node))
        for edge_index in range(len(graph.edges)):
            allocate(("z", step, edge_index))
        for task in tasks:
            allocate(("task", step, task))
        for run in runs:
            allocate(("run", step, run))
    terminal = len(budgets) - 1
    for parent in parents:
        allocate(("parent", terminal, parent))

    row_indices: list[int] = []
    column_indices: list[int] = []
    coefficients: list[float] = []
    lower: list[float] = []
    upper: list[float] = []

    def add_row(
        terms: Any, lower_bound: float, upper_bound: float
    ) -> None:
        combined: dict[int, float] = defaultdict(float)
        for variable, coefficient in terms:
            combined[variable] += coefficient
        row_number = len(lower)
        for variable, coefficient in combined.items():
            if coefficient:
                row_indices.append(row_number)
                column_indices.append(variable)
                coefficients.append(float(coefficient))
        lower.append(float(lower_bound))
        upper.append(float(upper_bound))

    edges_by_task: dict[str, list[int]] = defaultdict(list)
    edges_by_run: dict[str, list[int]] = defaultdict(list)
    edges_by_parent: dict[str, list[int]] = defaultdict(list)
    for edge_index, edge in enumerate(graph.edges):
        edges_by_task[edge.task].append(edge_index)
        edges_by_run[edge.run].append(edge_index)
        edges_by_parent[edge.parent].append(edge_index)

    infinity = math.inf
    pointwise = floors["pointwise_closed_edges"]
    for step, budget in enumerate(budgets):
        add_row(((index[("x", step, node)], 1) for node in nodes), budget, budget)
        if step + 1 < len(budgets):
            for node in nodes:
                add_row(
                    (
                        (index[("x", step, node)], 1),
                        (index[("x", step + 1, node)], -1),
                    ),
                    -infinity,
                    0,
                )
        for edge_index, edge in enumerate(graph.edges):
            closed = index[("z", step, edge_index)]
            left = index[("x", step, edge.u)]
            right = index[("x", step, edge.v)]
            add_row(((closed, 1), (left, -1)), -infinity, 0)
            add_row(((closed, 1), (right, -1)), -infinity, 0)
            add_row(((closed, 1), (left, -1), (right, -1)), -1, infinity)
        add_row(
            (
                (index[("z", step, edge_index)], 1)
                for edge_index in range(len(graph.edges))
            ),
            pointwise[step],
            infinity,
        )
        for task in tasks:
            add_row(
                [(index[("task", step, task)], 1)]
                + [
                    (index[("z", step, edge_index)], -1)
                    for edge_index in edges_by_task[task]
                ],
                -infinity,
                0,
            )
        for run in runs:
            add_row(
                [(index[("run", step, run)], 1)]
                + [
                    (index[("z", step, edge_index)], -1)
                    for edge_index in edges_by_run[run]
                ],
                -infinity,
                0,
            )

    add_row(
        (
            (index[("task", step, task)], 1)
            for step in range(len(budgets))
            for task in tasks
        ),
        floors["integrated_tasks"],
        infinity,
    )
    add_row(
        (
            (index[("run", step, run)], 1)
            for step in range(len(budgets))
            for run in runs
        ),
        floors["integrated_physical_runs"],
        infinity,
    )
    add_row(
        (
            (index[("z", step, edge_index)], 1)
            for step in range(len(budgets))
            for edge_index in range(len(graph.edges))
        ),
        floors["integrated_closed_edges"],
        infinity,
    )
    for parent in parents:
        add_row(
            [(index[("parent", terminal, parent)], 1)]
            + [
                (index[("z", terminal, edge_index)], -1)
                for edge_index in edges_by_parent[parent]
            ],
            -infinity,
            0,
        )
    add_row(
        ((index[("parent", terminal, parent)], 1) for parent in parents),
        floors["terminal_parents"],
        infinity,
    )
    terminal_edges = [
        index[("z", terminal, edge_index)]
        for edge_index in range(len(graph.edges))
    ]
    for task in tasks:
        add_row(
            [
                (index[("z", terminal, edge_index)], 3)
                for edge_index in edges_by_task[task]
            ]
            + [(variable, -1) for variable in terminal_edges],
            -infinity,
            0,
        )
    for run in runs:
        add_row(
            [
                (index[("z", terminal, edge_index)], 10)
                for edge_index in edges_by_run[run]
            ]
            + [(variable, -1) for variable in terminal_edges],
            -infinity,
            0,
        )

    matrix = coo_matrix(
        (coefficients, (row_indices, column_indices)),
        shape=(len(lower), len(index)),
    ).tocsr()
    with warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter("always")
        solved = milp(
            c=np.zeros(len(index)),
            constraints=LinearConstraint(matrix, np.array(lower), np.array(upper)),
            integrality=np.ones(len(index)),
            bounds=Bounds(np.zeros(len(index)), np.ones(len(index))),
            options={
                "presolve": True,
                "time_limit": time_limit,
                "mip_rel_gap": 0.0,
                "disp": False,
                "threads": 1,
                "random_seed": 0,
            },
        )
    unexpected = [
        item
        for item in caught
        if not (
            issubclass(item.category, RuntimeWarning)
            and "Unrecognized options detected" in str(item.message)
            and ("threads" in str(item.message) or "random_seed" in str(item.message))
        )
    ]
    check(not unexpected, "unexpected independent solver warning")
    if solved.x is not None:
        return "FEASIBLE_WITNESS"
    return "INFEASIBLE_PROVEN" if int(solved.status) == 2 else "FEASIBILITY_UNRESOLVED"


def no_public_identities(public: dict[str, Any], graph: Any) -> bool:
    raw = canonical_bytes(public).decode("utf-8")
    identities = set(graph.nodes)
    identities.update(edge.parent for edge in graph.edges)
    identities.update(edge.task for edge in graph.edges)
    identities.update(edge.run for edge in graph.edges)
    return not any(json.dumps(value, ensure_ascii=False) in raw for value in identities)


def verify(args: argparse.Namespace) -> dict[str, Any]:
    protocol, protocol_sha = protocol_file(args.protocol.resolve(), args.protocol_sha256)
    public = object_file(args.public_result.resolve())
    check(public.get("protocol") == PUBLIC_PROTOCOL, "public result protocol")
    check(public.get("protocol_sha256") == protocol_sha, "public protocol binding")
    selection, candidate, cards, runs, append_only = independent_selection_and_increment(
        args.state_root.resolve(),
        args.selection_root.resolve(),
        args.repo_root.resolve(),
        protocol,
    )
    graph, pair_binding = independent_pair_graph(
        args.state_root.resolve(), candidate, cards, runs
    )
    census, support = census_and_support(graph, protocol)
    check(public["graph_census"] == census, "graph census")
    check(public["support_gates"] == support, "support gates")
    check(public["selection_binding"]["append_only"] == append_only, "append-only binding")
    check(public["selection_binding"]["pair_files"] == pair_binding, "pair binding")
    check(
        public["selection_binding"]["baseline_snapshot_sha256"] == selection["baseline"],
        "baseline selection binding",
    )
    check(
        public["selection_binding"]["candidate_snapshot_sha256"] == selection["candidate"],
        "candidate selection binding",
    )
    check(no_public_identities(public, graph), "public result emits graph identity")
    scope = public["scope"]
    check(scope["prospective_label_outcome_prediction_values_read"] is False, "value boundary")
    check(scope["gpu_api_model_fit_base_update"] == "0/0/0/0", "resource boundary")

    classification = public["classification"]
    if not all(support.values()):
        check(
            classification == "FORWARD_TARGET522_YIELD_GUARDED_BREADTH_LIMITED_SUPPORT",
            "limited-support classification",
        )
        check(public["baseline"] is None and public["solver"] is None, "limited support leakage")
        check(not args.private_witness.exists(), "limited support private witness")
        return verification_payload(public, protocol_sha, census, support, None, None)

    budgets = budget_values(graph, protocol)
    baseline = independent_baseline(graph, budgets)
    floors = floors_from_baseline(baseline, budgets)
    check(public["checkpoints"] == budgets, "checkpoints")
    check(public["baseline"] == baseline, "baseline")
    check(public["fixed_floors"] == floors, "floors")
    solver_status = public["solver"]["status"]
    private_metrics = None
    gates = None
    if solver_status == "FEASIBLE_WITNESS":
        check(args.private_witness.is_file() and not args.private_witness.is_symlink(), "private witness")
        check(args.private_witness.stat().st_mode & 0o077 == 0, "private witness mode")
        check(
            target_check.file_digest(args.private_witness)
            == public["private_witness_sha256"],
            "private witness SHA",
        )
        private = object_file(args.private_witness)
        check(private.get("protocol") == PRIVATE_PROTOCOL, "private protocol")
        check(private.get("checkpoints") == budgets, "private checkpoints")
        entries = private.get("selected_endpoint_ids_by_checkpoint")
        check(isinstance(entries, list) and len(entries) == len(budgets), "private entries")
        selected_sets: list[set[str]] = []
        private_metrics = []
        for entry, budget in zip(entries, budgets):
            check(entry.get("budget") == budget, "private budget")
            identifiers = entry.get("endpoint_ids")
            check(
                isinstance(identifiers, list)
                and identifiers == sorted(set(identifiers))
                and len(identifiers) == budget
                and set(identifiers) <= set(graph.nodes),
                "private endpoint set",
            )
            selected_sets.append(set(identifiers))
            private_metrics.append(selection_metrics(graph, set(identifiers), budget))
        check(
            all(selected_sets[index] <= selected_sets[index + 1] for index in range(len(selected_sets) - 1)),
            "private trajectory nesting",
        )
        check(
            private["selection_fingerprint_sha256"]
            == canonical_sha(private["selected_endpoint_ids_by_checkpoint"]),
            "private fingerprint",
        )
        check(public["solver"]["metrics"] == private_metrics, "public/private metrics")
        integrated = {
            field: sum(int(row[field]) for row in private_metrics)
            for field in ("closed_edges", "tasks", "physical_runs")
        }
        check(public["solver"]["integrated"] == integrated, "public/private integrated")
        gates = witness_gates(private_metrics, floors)
        check(public["witness_gates"] == gates and all(gates.values()), "witness gates")
        check(
            classification == "FORWARD_TARGET522_YIELD_GUARDED_BREADTH_JOINTLY_FEASIBLE",
            "feasible classification",
        )
    else:
        check(not args.private_witness.exists(), "unexpected private witness")
        independent_status = independent_solver_status(
            graph,
            budgets,
            floors,
            protocol["acquisition"]["solver_time_limit_seconds"],
        )
        check(independent_status == solver_status, "independent solver status")
        expected = (
            "FORWARD_TARGET522_YIELD_GUARDED_BREADTH_INFEASIBLE_PROVEN"
            if solver_status == "INFEASIBLE_PROVEN"
            else "FORWARD_TARGET522_YIELD_GUARDED_BREADTH_FEASIBILITY_UNRESOLVED"
        )
        check(classification == expected, "nonfeasible classification")
    return verification_payload(public, protocol_sha, census, support, private_metrics, gates)


def verification_payload(
    public: dict[str, Any],
    protocol_sha: str,
    census: dict[str, Any],
    support: dict[str, bool],
    metrics: list[dict[str, Any]] | None,
    gates: dict[str, bool] | None,
) -> dict[str, Any]:
    return {
        "protocol": VERIFY_PROTOCOL,
        "status": "INDEPENDENT_GRAPH_LEVEL_VERIFICATION_COMPLETE",
        "classification": public["classification"],
        "protocol_sha256": protocol_sha,
        "public_result_sha256": None,
        "graph_census": census,
        "support_gates": support,
        "private_witness_recomputed": metrics is not None,
        "private_metrics": metrics,
        "witness_gates": gates,
        "boundary": {
            "forward_producer_imported": False,
            "independent_target522_loader_used": True,
            "pair_graph_reconstructed": True,
            "baseline_reimplemented": True,
            "induced_edges_recomputed_from_private_endpoint_ids": metrics is not None,
            "identities_emitted": False,
            "prospective_label_outcome_prediction_values_read": False,
            "gpu_api_model_fit_base_update": "0/0/0/0",
        },
    }


def write_once(path: Path, value: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    descriptor = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    with os.fdopen(descriptor, "wb") as handle:
        handle.write(canonical_bytes(value))


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--protocol", type=Path, required=True)
    parser.add_argument("--protocol-sha256", required=True)
    parser.add_argument("--state-root", type=Path, required=True)
    parser.add_argument("--selection-root", type=Path, required=True)
    parser.add_argument("--repo-root", type=Path, required=True)
    parser.add_argument("--public-result", type=Path, required=True)
    parser.add_argument("--private-witness", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    result = verify(args)
    result["public_result_sha256"] = target_check.file_digest(args.public_result.resolve())
    write_once(args.output.resolve(), result)
    print(
        json.dumps(
            {
                "status": result["status"],
                "classification": result["classification"],
                "output_sha256": target_check.file_digest(args.output.resolve()),
                "boundary": result["boundary"],
            },
            sort_keys=True,
        )
    )


if __name__ == "__main__":
    main()
