#!/usr/bin/env python3
"""Post-audit development screen for distribution-matched endpoint acquisition."""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import math
import os
import statistics
import time
import warnings
from collections import Counter, defaultdict
from dataclasses import dataclass
from pathlib import Path
from types import SimpleNamespace
from typing import Any, Iterable

from phase1 import endpoint_budget_label_efficiency_smoke as smoke


PROTOCOL = "endpoint-budget-distribution-matched-yield-screen-v1"
SELECTION_PUBLIC = "endpoint-budget-distribution-matched-yield-selection-public-v1"
SELECTION_PRIVATE = "endpoint-budget-distribution-matched-yield-selection-private-v1"
FIT_CELL = "endpoint-budget-distribution-matched-yield-fit-cell-v1"
FIT_RESULT = "endpoint-budget-distribution-matched-yield-fit-result-v1"
FIT_PRIVATE = "endpoint-budget-distribution-matched-yield-private-pair-witness-v1"
OLD_UNIFORM = "exact_b_uniform_edge"
OLD_YIELD = "yield_guarded_breadth"
NEW_ARM = "distribution_matched_yield"


class ScreenError(RuntimeError):
    pass


def require(condition: bool, message: str) -> None:
    if not condition:
        raise ScreenError(message)


def file_sha(path: Path) -> str:
    return smoke.file_sha(path)


def object_file(path: Path) -> dict[str, Any]:
    return smoke.object_file(path)


def private_mode(path: Path) -> bool:
    return os.name == "nt" or path.stat().st_mode & 0o077 == 0


def load_protocol(path: Path, expected_sha: str) -> dict[str, Any]:
    require(file_sha(path) == expected_sha, "screen protocol SHA")
    value = object_file(path)
    require(value.get("protocol") == PROTOCOL, "screen protocol name")
    require(
        value.get("status") == "FROZEN_AFTER_TASK_HETEROGENEITY_AUDIT_BEFORE_NEW_SELECTION_OR_PREDICTION",
        "screen freeze status",
    )
    known = value["known_before_freeze"]
    require(known["new_selection_seen"] is False, "new selection was seen")
    require(known["new_distribution_objective_seen"] is False, "new objective was seen")
    require(known["new_prediction_or_task_metric_seen"] is False, "new metric was seen")
    require(value["resources"] == {
        "gpu": 0,
        "paid_api_calls": 0,
        "critic_model_fits": 2,
        "base_model_updates": 0,
        "expected_cpu_minutes": "less than 30",
    }, "resource contract")
    return value


def validate_file(path: Path, expected: str, label: str, private: bool = False) -> None:
    require(file_sha(path) == expected, f"{label} SHA")
    if private:
        require(private_mode(path), f"{label} private mode")


def old_population(args: argparse.Namespace, protocol: dict[str, Any]) -> tuple[Any, Any, Any, dict[str, Any], dict[str, Any]]:
    bindings = protocol["input_bindings"]
    old_protocol_path = args.old_protocol.resolve()
    validate_file(old_protocol_path, bindings["old_smoke_protocol_sha256"], "old protocol")
    old_protocol, old_sha = smoke.load_protocol(old_protocol_path, bindings["old_smoke_protocol_sha256"])
    validate_file(args.firewall_receipt.resolve(), bindings["firewall_receipt_sha256"], "firewall receipt", True)
    validate_file(args.train_topology.resolve(), bindings["train_only_topology_sha256"], "train topology", True)
    compatible = SimpleNamespace(
        firewall_receipt=args.firewall_receipt,
        train_topology=args.train_topology,
        source_commit=bindings["artifact_source_commit"],
    )
    full, train, evaluation, receipt = smoke.load_firewall_population(compatible, old_sha)
    require((len(full.edges), len(train.edges), len(evaluation.edges)) == (539, 401, 138), "population sizes")
    require(len({edge.task for edge in train.edges}) == 35, "outer-train tasks")
    return full, train, evaluation, receipt, old_protocol


@dataclass(frozen=True)
class Layout:
    index: dict[tuple[Any, ...], int]
    binary: set[int]
    size: int


class Rows:
    def __init__(self) -> None:
        self.row: list[int] = []
        self.col: list[int] = []
        self.data: list[float] = []
        self.lower: list[float] = []
        self.upper: list[float] = []

    def add(self, terms: Iterable[tuple[int, float]], lower: float, upper: float) -> None:
        row_number = len(self.lower)
        combined: dict[int, float] = defaultdict(float)
        for index, coefficient in terms:
            combined[index] += coefficient
        for index, coefficient in combined.items():
            if coefficient:
                self.row.append(row_number)
                self.col.append(index)
                self.data.append(float(coefficient))
        self.lower.append(float(lower))
        self.upper.append(float(upper))


def make_layout(graph: Any, checkpoints: list[int]) -> tuple[Layout, list[str], list[str], list[str]]:
    tasks = sorted({edge.task for edge in graph.edges})
    runs = sorted({edge.run for edge in graph.edges})
    parents = sorted({edge.parent for edge in graph.edges})
    index: dict[tuple[Any, ...], int] = {}
    binary: set[int] = set()

    def allocate(key: tuple[Any, ...], is_binary: bool) -> None:
        require(key not in index, "layout duplicate")
        index[key] = len(index)
        if is_binary:
            binary.add(index[key])

    for step in range(len(checkpoints)):
        for node in graph.nodes:
            allocate(("x", step, node), True)
        for edge_index in range(len(graph.edges)):
            allocate(("z", step, edge_index), True)
        for run in runs:
            allocate(("run", step, run), True)
        for task in tasks:
            allocate(("d", step, task), False)
    terminal = len(checkpoints) - 1
    for parent in parents:
        allocate(("parent", terminal, parent), True)
    return Layout(index, binary, len(index)), tasks, runs, parents


def build_constraints(
    graph: Any,
    checkpoints: list[int],
    exact_pairs: list[int],
    layout: Layout,
    tasks: list[str],
    runs: list[str],
    parents: list[str],
    integrated_run_floor: int,
    terminal_parent_floor: int,
) -> Rows:
    rows = Rows()
    infinity = math.inf
    edges_by_task: dict[str, list[int]] = defaultdict(list)
    edges_by_run: dict[str, list[int]] = defaultdict(list)
    edges_by_parent: dict[str, list[int]] = defaultdict(list)
    for edge_index, edge in enumerate(graph.edges):
        edges_by_task[edge.task].append(edge_index)
        edges_by_run[edge.run].append(edge_index)
        edges_by_parent[edge.parent].append(edge_index)
    available = {task: len(edges_by_task[task]) for task in tasks}
    total_available = len(graph.edges)
    require(sum(available.values()) == total_available and total_available > 0, "availability total")

    for step, (budget, pair_count) in enumerate(zip(checkpoints, exact_pairs)):
        rows.add(((layout.index[("x", step, node)], 1) for node in graph.nodes), budget, budget)
        if step + 1 < len(checkpoints):
            for node in graph.nodes:
                rows.add(
                    (
                        (layout.index[("x", step, node)], 1),
                        (layout.index[("x", step + 1, node)], -1),
                    ),
                    -infinity,
                    0,
                )
        for edge_index, edge in enumerate(graph.edges):
            z = layout.index[("z", step, edge_index)]
            left = layout.index[("x", step, edge.u)]
            right = layout.index[("x", step, edge.v)]
            rows.add(((z, 1), (left, -1)), -infinity, 0)
            rows.add(((z, 1), (right, -1)), -infinity, 0)
            rows.add(((z, 1), (left, -1), (right, -1)), -1, infinity)
        rows.add(
            ((layout.index[("z", step, edge_index)], 1) for edge_index in range(len(graph.edges))),
            pair_count,
            pair_count,
        )
        for task in tasks:
            z_terms = [(layout.index[("z", step, edge_index)], 1) for edge_index in edges_by_task[task]]
            rows.add(((index, 5) for index, _ in z_terms), -infinity, pair_count)
            d = layout.index[("d", step, task)]
            rows.add([(d, 1)] + [(index, -total_available) for index, _ in z_terms], -pair_count * available[task], infinity)
            rows.add([(d, 1)] + [(index, total_available) for index, _ in z_terms], pair_count * available[task], infinity)
        for run in runs:
            z_indices = [layout.index[("z", step, edge_index)] for edge_index in edges_by_run[run]]
            rows.add(((index, 10) for index in z_indices), -infinity, pair_count)
            run_indicator = layout.index[("run", step, run)]
            rows.add([(run_indicator, 1)] + [(index, -1) for index in z_indices], -infinity, 0)

    rows.add(
        (
            (layout.index[("run", step, run)], 1)
            for step in range(len(checkpoints))
            for run in runs
        ),
        integrated_run_floor,
        infinity,
    )
    terminal = len(checkpoints) - 1
    for parent in parents:
        indicator = layout.index[("parent", terminal, parent)]
        z_indices = [layout.index[("z", terminal, edge_index)] for edge_index in edges_by_parent[parent]]
        rows.add([(indicator, 1)] + [(index, -1) for index in z_indices], -infinity, 0)
    rows.add(
        ((layout.index[("parent", terminal, parent)], 1) for parent in parents),
        terminal_parent_floor,
        infinity,
    )
    return rows


def milp_once(layout: Layout, rows: Rows, objective: list[float], time_limit: float) -> Any:
    import numpy as np
    from scipy.optimize import Bounds, LinearConstraint, milp
    from scipy.sparse import coo_matrix

    matrix = coo_matrix((rows.data, (rows.row, rows.col)), shape=(len(rows.lower), layout.size)).tocsr()
    lower = np.zeros(layout.size)
    upper = np.full(layout.size, np.inf)
    for index in layout.binary:
        upper[index] = 1.0
    integrality = np.zeros(layout.size, dtype=int)
    for index in layout.binary:
        integrality[index] = 1
    options = {
        "presolve": True,
        "time_limit": time_limit,
        "mip_rel_gap": 0.0,
        "disp": False,
        "threads": 1,
        "random_seed": 0,
    }
    with warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter("always")
        solved = milp(
            c=np.asarray(objective, dtype=float),
            constraints=LinearConstraint(matrix, np.asarray(rows.lower), np.asarray(rows.upper)),
            integrality=integrality,
            bounds=Bounds(lower, upper),
            options=options,
        )
    unexpected = [
        item for item in caught
        if not (
            issubclass(item.category, RuntimeWarning)
            and "Unrecognized options detected" in str(item.message)
            and ("threads" in str(item.message) or "random_seed" in str(item.message))
        )
    ]
    require(not unexpected, "unexpected scipy warning")
    return solved


def ratio(numerator: int, denominator: int) -> dict[str, Any]:
    return smoke.graph_source.engine.fraction(numerator, denominator)


def trajectory_metrics(graph: Any, selected_by_step: list[set[str]], exact_pairs: list[int]) -> list[dict[str, Any]]:
    available = Counter(edge.task for edge in graph.edges)
    total = len(graph.edges)
    metrics: list[dict[str, Any]] = []
    for selected, expected in zip(selected_by_step, exact_pairs):
        closed = [edge for edge in graph.edges if edge.u in selected and edge.v in selected]
        require(len(closed) == expected, "exact induced pair count")
        by_task = Counter(edge.task for edge in closed)
        by_run = Counter(edge.run for edge in closed)
        l1 = sum(abs(by_task.get(task, 0) / expected - count / total) for task, count in available.items())
        integer_objective = sum(abs(total * by_task.get(task, 0) - expected * count) for task, count in available.items())
        metrics.append({
            "selected_endpoints": len(selected),
            "induced_pairs": len(closed),
            "represented_tasks": len(by_task),
            "represented_runs": len(by_run),
            "parents": len({edge.parent for edge in closed}),
            "maximum_single_task_share": ratio(max(by_task.values()), len(closed)),
            "maximum_single_run_share": ratio(max(by_run.values()), len(closed)),
            "task_distribution_l1": l1,
            "integer_distribution_objective": integer_objective,
        })
    return metrics


def solve_distribution_matched(graph: Any, protocol: dict[str, Any], time_limit: float) -> tuple[dict[str, Any], list[set[str]] | None]:
    selection = protocol["selection"]
    checkpoints = [int(value) for value in selection["checkpoints"]]
    exact_pairs = [int(value) for value in selection["exact_induced_pair_count"]]
    layout, tasks, runs, parents = make_layout(graph, checkpoints)
    rows = build_constraints(
        graph, checkpoints, exact_pairs, layout, tasks, runs, parents,
        int(selection["integrated_closed_run_floor"]), int(selection["terminal_parent_floor"]),
    )
    primary = [0.0] * layout.size
    for step in range(len(checkpoints)):
        for task in tasks:
            primary[layout.index[("d", step, task)]] = 1.0
    first = milp_once(layout, rows, primary, time_limit)
    if first.x is None:
        return {
            "status": "INFEASIBLE_PROVEN" if int(first.status) == 2 else "PRIMARY_OPTIMUM_NOT_RESOLVED",
            "solver_status": int(first.status),
            "solver_message": str(first.message),
        }, None
    first_gap = float(getattr(first, "mip_gap", math.inf))
    if int(first.status) != 0 or not math.isclose(first_gap, 0.0, rel_tol=0.0, abs_tol=0.0):
        return {
            "status": "PRIMARY_OPTIMUM_NOT_RESOLVED",
            "solver_status": int(first.status),
            "solver_message": str(first.message),
            "solver_mip_gap": first_gap,
        }, None
    primary_optimum = int(round(float(first.fun)))
    require(math.isclose(float(first.fun), primary_optimum, rel_tol=0.0, abs_tol=1e-5), "integer primary optimum")
    rows.add(
        ((layout.index[("d", step, task)], 1) for step in range(len(checkpoints)) for task in tasks),
        -math.inf,
        primary_optimum,
    )
    tie = [0.0] * layout.size
    for step in range(len(checkpoints)):
        for node in graph.nodes:
            digest = hashlib.sha256(("distribution-match-tiebreak\0" + str(step) + "\0" + node).encode()).digest()
            tie[layout.index[("x", step, node)]] = (int.from_bytes(digest[:8], "big") + 1) / (2**64)
    second = milp_once(layout, rows, tie, time_limit)
    if second.x is None:
        return {
            "status": "TIE_BREAK_NOT_RESOLVED",
            "primary_integer_objective": primary_optimum,
            "solver_status": int(second.status),
            "solver_message": str(second.message),
        }, None
    second_gap = float(getattr(second, "mip_gap", math.inf))
    if int(second.status) != 0 or not math.isclose(second_gap, 0.0, rel_tol=0.0, abs_tol=0.0):
        return {
            "status": "TIE_BREAK_NOT_RESOLVED",
            "primary_integer_objective": primary_optimum,
            "solver_status": int(second.status),
            "solver_message": str(second.message),
            "solver_mip_gap": second_gap,
        }, None
    selected_by_step = [
        {node for node in graph.nodes if second.x[layout.index[("x", step, node)]] >= 0.5}
        for step in range(len(checkpoints))
    ]
    require(all(len(selected) == budget for selected, budget in zip(selected_by_step, checkpoints)), "exact endpoint budgets")
    require(all(selected_by_step[i] <= selected_by_step[i + 1] for i in range(len(checkpoints) - 1)), "nested selection")
    metrics = trajectory_metrics(graph, selected_by_step, exact_pairs)
    direct_objective = sum(int(row["integer_distribution_objective"]) for row in metrics)
    require(direct_objective == primary_optimum, "direct primary objective")
    require(all(row["maximum_single_task_share"]["numerator"] * 5 <= row["maximum_single_task_share"]["denominator"] for row in metrics), "task anti-dominance")
    require(all(row["maximum_single_run_share"]["numerator"] * 10 <= row["maximum_single_run_share"]["denominator"] for row in metrics), "run anti-dominance")
    require(sum(int(row["represented_runs"]) for row in metrics) >= int(selection["integrated_closed_run_floor"]), "run floor")
    require(metrics[-1]["parents"] >= int(selection["terminal_parent_floor"]), "parent floor")
    fingerprint = hashlib.sha256(
        "\n".join(
            hashlib.sha256((str(step) + "\0" + node).encode()).hexdigest()
            for step, selected in enumerate(selected_by_step)
            for node in sorted(selected)
        ).encode()
    ).hexdigest()
    return {
        "status": "OPTIMAL_WITNESS",
        "primary_integer_objective": primary_optimum,
        "tie_break_objective": float(second.fun),
        "variable_count": layout.size,
        "constraint_count": len(rows.lower),
        "primary_solver_status": int(first.status),
        "primary_solver_message": str(first.message),
        "primary_solver_mip_gap": first_gap,
        "tie_solver_status": int(second.status),
        "tie_solver_message": str(second.message),
        "tie_solver_mip_gap": second_gap,
        "solver_threads_requested": 1,
        "solver_random_seed": 0,
        "metrics": [dict(row, endpoint_budget=budget) for row, budget in zip(metrics, checkpoints)],
        "integrated_closed_runs": sum(int(row["represented_runs"]) for row in metrics),
        "private_selection_fingerprint_sha256": fingerprint,
    }, selected_by_step


def old_structural_metrics(graph: Any, private: dict[str, Any], protocol: dict[str, Any]) -> list[dict[str, Any]]:
    entries = smoke.entries_by_budget(private, OLD_YIELD)
    checkpoints = [int(value) for value in protocol["selection"]["checkpoints"]]
    exact_pairs = [int(value) for value in protocol["selection"]["exact_induced_pair_count"]]
    return [
        dict(row, endpoint_budget=budget)
        for row, budget in zip(trajectory_metrics(graph, [entries[budget] for budget in checkpoints], exact_pairs), checkpoints)
    ]


def build_selection(args: argparse.Namespace) -> tuple[dict[str, Any], dict[str, Any]]:
    protocol = load_protocol(args.protocol.resolve(), args.protocol_sha256)
    bindings = protocol["input_bindings"]
    full, train, _evaluation, _receipt, _old_protocol = old_population(args, protocol)
    validate_file(args.old_selection_public.resolve(), bindings["old_selection_public_sha256"], "old selection public")
    validate_file(args.old_selection_private.resolve(), bindings["old_selection_private_sha256"], "old selection private", True)
    validate_file(args.task_audit_public.resolve(), bindings["task_heterogeneity_public_sha256"], "task audit public")
    old_private = object_file(args.old_selection_private.resolve())
    audit = object_file(args.task_audit_public.resolve())
    require(audit.get("classification") == "EXPLORATORY_TASK_HETEROGENEITY_AUDIT_COMPLETE_NOT_CONFIRMATORY", "audit classification")
    require(audit.get("scope", {}).get("prospective_values_used") is False, "audit prospective scope")
    old_metrics = old_structural_metrics(train, old_private, protocol)
    result, selected = solve_distribution_matched(train, protocol, args.time_limit_seconds)
    require(result["status"] == "OPTIMAL_WITNESS" and selected is not None, "new selection optimum")
    checkpoints = protocol["selection"]["checkpoints"]
    private = {
        "protocol": SELECTION_PRIVATE,
        "protocol_sha256": args.protocol_sha256,
        "analysis_source_commit": args.analysis_source_commit,
        "artifact_source_commit": bindings["artifact_source_commit"],
        "checkpoints": checkpoints,
        "arm": NEW_ARM,
        "selected_endpoint_ids_by_checkpoint": [
            {"endpoint_budget": budget, "endpoint_ids": sorted(values)}
            for budget, values in zip(checkpoints, selected)
        ],
        "selection_fingerprint_sha256": result["private_selection_fingerprint_sha256"],
        "identities_publicly_emitted": False,
    }
    private_sha = hashlib.sha256(smoke.canonical_bytes(private)).hexdigest()
    comparisons = []
    for new, old in zip(result["metrics"], old_metrics):
        comparisons.append({
            "endpoint_budget": new["endpoint_budget"],
            "new_task_distribution_l1": new["task_distribution_l1"],
            "old_yield_task_distribution_l1": old["task_distribution_l1"],
            "new_minus_old_l1": new["task_distribution_l1"] - old["task_distribution_l1"],
            "new_induced_pairs": new["induced_pairs"],
            "old_yield_induced_pairs": old["induced_pairs"],
        })
    public = {
        "protocol": SELECTION_PUBLIC,
        "protocol_sha256": args.protocol_sha256,
        "analysis_source_commit": args.analysis_source_commit,
        "artifact_source_commit": bindings["artifact_source_commit"],
        "classification": "DISTRIBUTION_MATCHED_YIELD_SELECTION_OPTIMAL",
        "population": {
            "outer_train_pairs": len(train.edges),
            "outer_train_endpoints": len(train.nodes),
            "outer_train_tasks": len({edge.task for edge in train.edges}),
            "outer_train_runs": len({edge.run for edge in train.edges}),
        },
        "solver": result,
        "comparison_to_old_yield": comparisons,
        "private_selection_sha256": private_sha,
        "scope": {
            "historical_post_audit_development_only": True,
            "labels_code_predictions_eval_topology_used_for_selection": False,
            "senior_test_rows_used": False,
            "prospective_values_used": False,
            "public_identities_emitted": False,
            "gpu_api_model_fit_base_update": "0/0/0/0",
        },
        "status": "COMPLETE",
    }
    require(smoke.public_has_no_identities(public, full), "selection public identity leak")
    return public, private


def selected_by_budget(private: dict[str, Any]) -> dict[int, set[str]]:
    result: dict[int, set[str]] = {}
    previous: set[str] = set()
    for entry in private["selected_endpoint_ids_by_checkpoint"]:
        budget = int(entry["endpoint_budget"])
        identifiers = entry["endpoint_ids"]
        require(identifiers == sorted(set(identifiers)), "selection IDs")
        selected = set(identifiers)
        require(len(selected) == budget and previous <= selected, "private exact nested")
        result[budget] = selected
        previous = selected
    return result


def witness_cells(value: dict[str, Any]) -> dict[tuple[str, int], dict[str, dict[str, Any]]]:
    cells: dict[tuple[str, int], dict[str, dict[str, Any]]] = defaultdict(dict)
    for row in value["rows"]:
        cell = (row["arm"], int(row["endpoint_budget"]))
        pair = row["pair_identity_sha256"]
        require(pair not in cells[cell], "old witness duplicate")
        cells[cell][pair] = row
    return cells


def arrays(rows: list[dict[str, Any]]) -> dict[str, list[float]]:
    return smoke.arrays_from_pair_witness(rows)


def task_sign_counts(values: list[float], tasks: list[str]) -> dict[str, int]:
    grouped: dict[str, float] = defaultdict(float)
    for value, task in zip(values, tasks):
        grouped[task] += value
    result = {"negative": 0, "zero": 0, "positive": 0}
    for value in grouped.values():
        result["negative" if value < 0 else "positive" if value > 0 else "zero"] += 1
    return result


def paired_comparison(
    left: dict[str, list[float]],
    right: dict[str, list[float]],
    tasks: list[str],
    runs: list[str],
    repetitions: int,
    seed: int,
) -> dict[str, Any]:
    deltas = {
        "accuracy": [a - b for a, b in zip(left["correct"], right["correct"])],
        "log_loss": [a - b for a, b in zip(left["log_loss"], right["log_loss"])],
        "brier": [a - b for a, b in zip(left["brier"], right["brier"])],
    }
    grouped: dict[str, dict[str, list[float]]] = defaultdict(lambda: defaultdict(list))
    for index, task in enumerate(tasks):
        for metric, values in deltas.items():
            grouped[task][metric].append(values[index])
    task_macro = {
        metric: statistics.fmean(statistics.fmean(grouped[task][metric]) for task in sorted(grouped))
        for metric in deltas
    }
    accuracy = deltas["accuracy"]
    return {
        "pooled_metric_delta": {metric: statistics.fmean(values) for metric, values in deltas.items()},
        "task_macro_metric_delta": task_macro,
        "task_net_correct_sign_counts": task_sign_counts(accuracy, tasks),
        "accuracy_task_clustered_bootstrap": smoke.bootstrap_interval(accuracy, tasks, repetitions, seed),
        "accuracy_run_clustered_bootstrap": smoke.bootstrap_interval(accuracy, runs, repetitions, seed + 1),
        "pairwise_accuracy_delta": accuracy,
    }


def build_fit(args: argparse.Namespace) -> tuple[dict[str, Any], list[dict[str, Any]], dict[str, Any]]:
    protocol = load_protocol(args.protocol.resolve(), args.protocol_sha256)
    bindings = protocol["input_bindings"]
    full, train, evaluation, _receipt, old_protocol = old_population(args, protocol)
    validate_file(args.train_labels.resolve(), bindings["train_only_labels_sha256"], "train labels", True)
    validate_file(args.old_selection_public.resolve(), bindings["old_selection_public_sha256"], "old selection public")
    validate_file(args.old_selection_private.resolve(), bindings["old_selection_private_sha256"], "old selection private", True)
    validate_file(args.old_fit_summary.resolve(), bindings["old_fit_summary_sha256"], "old fit summary")
    validate_file(args.old_private_pairs.resolve(), bindings["old_private_pair_witness_sha256"], "old private pair witness", True)
    validate_file(args.task_audit_public.resolve(), bindings["task_heterogeneity_public_sha256"], "task audit public")
    cards_root = args.cards_root.resolve()
    validate_file(cards_root / "cards.safe.json", bindings["safe_cards_sha256"], "safe cards")
    validate_file(cards_root / "security_scan.json", bindings["safe_cards_security_receipt_sha256"], "safe card security receipt")

    selection_public_path = args.selection_public.resolve()
    selection_private_path = args.selection_private.resolve()
    selection_public = object_file(selection_public_path)
    selection_private = object_file(selection_private_path)
    require(selection_public.get("protocol") == SELECTION_PUBLIC and selection_public.get("status") == "COMPLETE", "new selection public")
    require(selection_public.get("protocol_sha256") == args.protocol_sha256, "selection protocol")
    require(file_sha(selection_private_path) == selection_public["private_selection_sha256"], "selection private SHA")
    require(private_mode(selection_private_path), "selection private mode")
    require(selection_private.get("protocol") == SELECTION_PRIVATE, "selection private protocol")
    selections = selected_by_budget(selection_private)
    require(set(selections) == set(protocol["selection"]["checkpoints"]), "selection checkpoints")

    compatible = SimpleNamespace(
        firewall_receipt=args.firewall_receipt,
        train_topology=args.train_topology,
        train_labels=args.train_labels,
        cards_root=args.cards_root,
        source_commit=bindings["artifact_source_commit"],
    )
    needed = set(evaluation.nodes)
    for budget in protocol["fit"]["budgets"]:
        needed.update(selections[int(budget)])
    residual, codes = smoke.load_train_rows_and_codes(compatible, old_protocol, needed)
    train_rows = [row for row in residual if smoke.run_fold(row.first_run) != 0]
    eval_rows = [row for row in residual if smoke.run_fold(row.first_run) == 0]
    require(len(train_rows) == len(train.edges) == 401 and len(eval_rows) == len(evaluation.edges) == 138, "fit split")
    require(all(row.split == "train" for row in train_rows + eval_rows), "train-only rows")
    tasks = [smoke.identity_sha("task", row.task) for row in eval_rows]
    runs = [smoke.identity_sha("physical_run", row.first_run) for row in eval_rows]
    pair_ids = [smoke.pair_identity_sha(row) for row in eval_rows]

    old_private = object_file(args.old_private_pairs.resolve())
    old_cells = witness_cells(old_private)
    checkpoint_root = args.checkpoint_dir.resolve()
    checkpoint_root.mkdir(parents=True, exist_ok=True, mode=0o700)
    require(private_mode(checkpoint_root), "checkpoint private mode")
    output_rows: list[dict[str, Any]] = []
    new_arrays: dict[int, dict[str, list[float]]] = {}
    private_rows: list[dict[str, Any]] = []
    selection_public_sha = file_sha(selection_public_path)
    selection_private_sha = file_sha(selection_private_path)
    for budget in [int(value) for value in protocol["fit"]["budgets"]]:
        checkpoint = checkpoint_root / f"{NEW_ARM}__{budget}.json"
        if checkpoint.exists():
            require(private_mode(checkpoint), "checkpoint mode")
            cell = object_file(checkpoint)
            require(
                cell.get("protocol") == FIT_CELL
                and cell.get("analysis_source_commit") == args.analysis_source_commit
                and cell.get("protocol_sha256") == args.protocol_sha256
                and cell.get("selection_public_sha256") == selection_public_sha
                and cell.get("selection_private_sha256") == selection_private_sha
                and cell.get("endpoint_budget") == budget,
                "checkpoint binding",
            )
            metrics, pair_rows = cell["metrics"], cell["pair_rows"]
            per_pair = arrays(pair_rows)
        else:
            metrics, per_pair = smoke.fit_one(selections[budget], train_rows, eval_rows, codes)
            pair_rows = smoke.pair_witness_rows(NEW_ARM, budget, eval_rows, per_pair["probability"])
            cell = {
                "protocol": FIT_CELL,
                "analysis_source_commit": args.analysis_source_commit,
                "protocol_sha256": args.protocol_sha256,
                "selection_public_sha256": selection_public_sha,
                "selection_private_sha256": selection_private_sha,
                "endpoint_budget": budget,
                "metrics": metrics,
                "pair_rows": pair_rows,
                "raw_identities_emitted": False,
            }
            smoke.write_checkpoint_atomic(checkpoint, cell)
        require([row["pair_identity_sha256"] for row in pair_rows] == pair_ids, "new pair witness order")
        require(all(row["task_sha256"] == task and row["physical_run_sha256"] == run for row, task, run in zip(pair_rows, tasks, runs)), "new witness fingerprints")
        new_arrays[budget] = per_pair
        private_rows.extend(pair_rows)
        output_rows.append({
            "protocol": FIT_RESULT,
            "analysis_source_commit": args.analysis_source_commit,
            "protocol_sha256": args.protocol_sha256,
            "selection_public_sha256": selection_public_sha,
            "selection_private_sha256": selection_private_sha,
            "outer_eval_fold": 0,
            "arm": NEW_ARM,
            "endpoint_budget": budget,
            **metrics,
            "gpu": 0,
            "api_calls": 0,
            "base_model_updates": 0,
        })

    comparisons: dict[str, Any] = {}
    for budget in [int(value) for value in protocol["fit"]["budgets"]]:
        per_arm: dict[str, dict[str, list[float]]] = {}
        for arm in (OLD_UNIFORM, OLD_YIELD):
            rows = [old_cells[(arm, budget)][pair] for pair in pair_ids]
            per_arm[arm] = arrays(rows)
        comparisons[str(budget)] = {
            "new_minus_old_yield": paired_comparison(new_arrays[budget], per_arm[OLD_YIELD], tasks, runs, 2000, 20260830 + budget),
            "new_minus_uniform": paired_comparison(new_arrays[budget], per_arm[OLD_UNIFORM], tasks, runs, 2000, 20261830 + budget),
        }

    task_counts = Counter(tasks)
    dominant = sorted(task_counts, key=lambda key: (-task_counts[key], key))[0]
    terminal = int(protocol["fit"]["budgets"][-1])
    terminal_new_uniform = comparisons[str(terminal)]["new_minus_uniform"]
    retained = [index for index, task in enumerate(tasks) if task != dominant]
    drop_delta = statistics.fmean(terminal_new_uniform["pairwise_accuracy_delta"][index] for index in retained)
    l1_comparisons = {int(row["endpoint_budget"]): row for row in selection_public["comparison_to_old_yield"]}
    gates = {
        "new_task_distribution_l1_strictly_below_old_yield_at_both_budgets": all(
            l1_comparisons[budget]["new_task_distribution_l1"] < l1_comparisons[budget]["old_yield_task_distribution_l1"]
            for budget in protocol["fit"]["budgets"]
        ),
        "new_minus_old_yield_task_macro_accuracy_positive_at_both_budgets": all(
            comparisons[str(budget)]["new_minus_old_yield"]["task_macro_metric_delta"]["accuracy"] > 0
            for budget in protocol["fit"]["budgets"]
        ),
        "terminal_new_minus_uniform_pooled_accuracy_positive": terminal_new_uniform["pooled_metric_delta"]["accuracy"] > 0,
        "terminal_new_minus_uniform_task_macro_accuracy_nonnegative": terminal_new_uniform["task_macro_metric_delta"]["accuracy"] >= 0,
        "terminal_new_minus_uniform_drop_dominant_accuracy_nonnegative": drop_delta >= 0,
        "terminal_new_minus_old_yield_log_loss_and_brier_nonworse": (
            comparisons[str(terminal)]["new_minus_old_yield"]["pooled_metric_delta"]["log_loss"] <= 0
            and comparisons[str(terminal)]["new_minus_old_yield"]["pooled_metric_delta"]["brier"] <= 0
        ),
        "terminal_new_minus_old_yield_positive_task_count_at_least_negative": (
            comparisons[str(terminal)]["new_minus_old_yield"]["task_net_correct_sign_counts"]["positive"]
            >= comparisons[str(terminal)]["new_minus_old_yield"]["task_net_correct_sign_counts"]["negative"]
        ),
    }
    require(set(gates) == set(protocol["frozen_screen_gates"]), "screen gate names")
    private_witness = {
        "protocol": FIT_PRIVATE,
        "protocol_sha256": args.protocol_sha256,
        "analysis_source_commit": args.analysis_source_commit,
        "selection_private_sha256": selection_private_sha,
        "raw_identities_emitted": False,
        "rows": private_rows,
    }
    private_sha = hashlib.sha256(smoke.canonical_bytes(private_witness)).hexdigest()
    for value in comparisons.values():
        for arm_value in value.values():
            arm_value.pop("pairwise_accuracy_delta")
    summary = {
        "protocol": FIT_RESULT,
        "protocol_sha256": args.protocol_sha256,
        "analysis_source_commit": args.analysis_source_commit,
        "artifact_source_commit": bindings["artifact_source_commit"],
        "selection_public_sha256": selection_public_sha,
        "selection_private_sha256": selection_private_sha,
        "model_rows": output_rows,
        "fit_checkpoints": {
            f"{NEW_ARM}__{int(budget)}.json": file_sha(checkpoint_root / f"{NEW_ARM}__{int(budget)}.json")
            for budget in protocol["fit"]["budgets"]
        },
        "comparisons": comparisons,
        "drop_dominant_task_terminal_new_minus_uniform_accuracy_delta": drop_delta,
        "dominant_task": {
            "identity_emitted": False,
            "pair_count": task_counts[dominant],
            "pair_share": ratio(task_counts[dominant], len(tasks)),
        },
        "screen_gates": gates,
        "classification": (
            protocol["interpretation"]["pass_classification"]
            if all(gates.values())
            else protocol["interpretation"]["fail_classification"]
        ),
        "private_pair_witness_sha256": private_sha,
        "scope": {
            "historical_post_audit_development_only": True,
            "senior_test_rows_used": False,
            "prospective_values_used": False,
            "public_identities_or_per_pair_predictions_emitted": False,
            "old_models_refit": False,
            "gpu_api_new_model_fit_base_update": "0/0/2/0",
            "scientific_confirmation": False,
        },
        "status": "COMPLETE",
    }
    require(smoke.public_has_no_identities(summary, full), "fit public identity leak")
    return summary, output_rows, private_witness


def write_csv_exclusive(path: Path, rows: list[dict[str, Any]]) -> None:
    require(rows, "CSV rows")
    path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    descriptor = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    with os.fdopen(descriptor, "w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)


def parser() -> argparse.ArgumentParser:
    value = argparse.ArgumentParser()
    sub = value.add_subparsers(dest="mode", required=True)
    for name in ("select", "fit"):
        item = sub.add_parser(name)
        item.add_argument("--protocol", type=Path, required=True)
        item.add_argument("--protocol-sha256", required=True)
        item.add_argument("--analysis-source-commit", required=True)
        item.add_argument("--old-protocol", type=Path, required=True)
        item.add_argument("--firewall-receipt", type=Path, required=True)
        item.add_argument("--train-topology", type=Path, required=True)
        item.add_argument("--old-selection-public", type=Path, required=True)
        item.add_argument("--old-selection-private", type=Path, required=True)
        item.add_argument("--task-audit-public", type=Path, required=True)
    select = sub.choices["select"]
    select.add_argument("--time-limit-seconds", type=float, default=300)
    select.add_argument("--public-output", type=Path, required=True)
    select.add_argument("--private-output", type=Path, required=True)
    fit = sub.choices["fit"]
    fit.add_argument("--train-labels", type=Path, required=True)
    fit.add_argument("--cards-root", type=Path, required=True)
    fit.add_argument("--old-fit-summary", type=Path, required=True)
    fit.add_argument("--old-private-pairs", type=Path, required=True)
    fit.add_argument("--selection-public", type=Path, required=True)
    fit.add_argument("--selection-private", type=Path, required=True)
    fit.add_argument("--checkpoint-dir", type=Path, required=True)
    fit.add_argument("--summary-output", type=Path, required=True)
    fit.add_argument("--runs-csv", type=Path, required=True)
    fit.add_argument("--private-pairs-output", type=Path, required=True)
    return value


def main() -> None:
    args = parser().parse_args()
    require(len(args.analysis_source_commit) == 40 and all(c in "0123456789abcdef" for c in args.analysis_source_commit), "analysis commit")
    if args.mode == "select":
        public, private = build_selection(args)
        smoke.write_json_exclusive(args.private_output.resolve(), private)
        require(file_sha(args.private_output.resolve()) == public["private_selection_sha256"], "written selection private SHA")
        smoke.write_json_exclusive(args.public_output.resolve(), public)
        print(json.dumps({
            "classification": public["classification"],
            "public_sha256": file_sha(args.public_output.resolve()),
            "private_sha256": file_sha(args.private_output.resolve()),
            "scope": public["scope"],
        }, sort_keys=True))
    else:
        summary, rows, private = build_fit(args)
        smoke.write_json_exclusive(args.private_pairs_output.resolve(), private)
        require(file_sha(args.private_pairs_output.resolve()) == summary["private_pair_witness_sha256"], "written fit private SHA")
        smoke.write_json_exclusive(args.summary_output.resolve(), summary)
        write_csv_exclusive(args.runs_csv.resolve(), rows)
        print(json.dumps({
            "classification": summary["classification"],
            "summary_sha256": file_sha(args.summary_output.resolve()),
            "runs_csv_sha256": file_sha(args.runs_csv.resolve()),
            "private_pairs_sha256": file_sha(args.private_pairs_output.resolve()),
            "scope": summary["scope"],
        }, sort_keys=True))


if __name__ == "__main__":
    main()
