#!/usr/bin/env python3
"""Development-only yield-guarded breadth MILP for a known sibling topology."""

from __future__ import annotations

import argparse
from collections import defaultdict
from dataclasses import dataclass
from fractions import Fraction
import hashlib
from itertools import combinations
import json
import math
import os
from pathlib import Path
from types import SimpleNamespace
from typing import Any, Iterable
import warnings

from phase1 import falsify_historical_run_split_breadth_pareto as source


@dataclass(frozen=True)
class Layout:
    index: dict[tuple[Any, ...], int]
    size: int


class Rows:
    def __init__(self) -> None:
        self.row: list[int] = []
        self.col: list[int] = []
        self.data: list[float] = []
        self.lower: list[float] = []
        self.upper: list[float] = []

    def add(self, terms: Iterable[tuple[int, float]], lower: float, upper: float) -> None:
        number = len(self.lower)
        combined: dict[int, float] = defaultdict(float)
        for index, coefficient in terms:
            combined[index] += coefficient
        for index, coefficient in combined.items():
            if coefficient:
                self.row.append(number)
                self.col.append(index)
                self.data.append(float(coefficient))
        self.lower.append(float(lower))
        self.upper.append(float(upper))


def ratio(numerator: int, denominator: int) -> dict[str, Any]:
    value = Fraction(numerator, denominator) if denominator else Fraction(0, 1)
    return {
        "numerator": value.numerator,
        "denominator": value.denominator,
        "decimal_17g": format(float(value), ".17g"),
    }


def make_layout(graph: Any, checkpoints: list[int]) -> tuple[Layout, list[str], list[str], list[str]]:
    tasks = sorted({edge.task for edge in graph.edges})
    runs = sorted({edge.run for edge in graph.edges})
    parents = sorted({edge.parent for edge in graph.edges})
    index: dict[tuple[Any, ...], int] = {}

    def allocate(key: tuple[Any, ...]) -> None:
        if key in index:
            raise AssertionError(key)
        index[key] = len(index)

    for step in range(len(checkpoints)):
        for vertex in graph.nodes:
            allocate(("x", step, vertex))
        for edge_index in range(len(graph.edges)):
            allocate(("z", step, edge_index))
        for task in tasks:
            allocate(("task", step, task))
        for run in runs:
            allocate(("run", step, run))
    terminal = len(checkpoints) - 1
    for parent in parents:
        allocate(("parent", terminal, parent))
    return Layout(index=index, size=len(index)), tasks, runs, parents


def build_constraints(
    graph: Any,
    checkpoints: list[int],
    yield_floors: list[int],
    terminal_parent_floor: int,
    layout: Layout,
    tasks: list[str],
    runs: list[str],
    parents: list[str],
    anti_task_denominator: int | None,
    anti_run_denominator: int | None,
    integrated_task_floor: int | None,
    integrated_run_floor: int | None,
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

    for step, budget in enumerate(checkpoints):
        rows.add(((layout.index[("x", step, vertex)], 1) for vertex in graph.nodes), budget, budget)
        if step + 1 < len(checkpoints):
            for vertex in graph.nodes:
                rows.add(
                    (
                        (layout.index[("x", step, vertex)], 1),
                        (layout.index[("x", step + 1, vertex)], -1),
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
            yield_floors[step],
            infinity,
        )
        for task in tasks:
            rows.add(
                [(layout.index[("task", step, task)], 1)]
                + [(layout.index[("z", step, edge_index)], -1) for edge_index in edges_by_task[task]],
                -infinity,
                0,
            )
        for run in runs:
            rows.add(
                [(layout.index[("run", step, run)], 1)]
                + [(layout.index[("z", step, edge_index)], -1) for edge_index in edges_by_run[run]],
                -infinity,
                0,
            )

    if integrated_task_floor is not None:
        rows.add(
            (
                (layout.index[("task", step, task)], 1)
                for step in range(len(checkpoints))
                for task in tasks
            ),
            integrated_task_floor,
            infinity,
        )
    if integrated_run_floor is not None:
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
        rows.add(
            [(layout.index[("parent", terminal, parent)], 1)]
            + [(layout.index[("z", terminal, edge_index)], -1) for edge_index in edges_by_parent[parent]],
            -infinity,
            0,
        )
    rows.add(
        ((layout.index[("parent", terminal, parent)], 1) for parent in parents),
        terminal_parent_floor,
        infinity,
    )

    all_terminal_edges = [layout.index[("z", terminal, edge_index)] for edge_index in range(len(graph.edges))]
    if anti_task_denominator is not None:
        for task in tasks:
            rows.add(
                [(layout.index[("z", terminal, edge_index)], anti_task_denominator) for edge_index in edges_by_task[task]]
                + [(index, -1) for index in all_terminal_edges],
                -infinity,
                0,
            )
    if anti_run_denominator is not None:
        for run in runs:
            rows.add(
                [(layout.index[("z", terminal, edge_index)], anti_run_denominator) for edge_index in edges_by_run[run]]
                + [(index, -1) for index in all_terminal_edges],
                -infinity,
                0,
            )
    return rows


def solve_guarded(
    graph: Any,
    checkpoints: list[int],
    yield_floors: list[int],
    terminal_parent_floor: int,
    time_limit_seconds: float,
    anti_task_denominator: int | None = 3,
    anti_run_denominator: int | None = 10,
    integrated_task_floor: int | None = None,
    integrated_run_floor: int | None = None,
) -> dict[str, Any]:
    import numpy as np
    from scipy.optimize import Bounds, LinearConstraint, milp
    from scipy.sparse import coo_matrix

    layout, tasks, runs, parents = make_layout(graph, checkpoints)
    rows = build_constraints(
        graph,
        checkpoints,
        yield_floors,
        terminal_parent_floor,
        layout,
        tasks,
        runs,
        parents,
        anti_task_denominator,
        anti_run_denominator,
        integrated_task_floor,
        integrated_run_floor,
    )
    matrix = coo_matrix((rows.data, (rows.row, rows.col)), shape=(len(rows.lower), layout.size)).tocsr()
    base_constraint = LinearConstraint(matrix, np.array(rows.lower), np.array(rows.upper))
    options = {
        "presolve": True,
        "time_limit": time_limit_seconds,
        "mip_rel_gap": 0.0,
        "disp": False,
        "threads": 1,
        "random_seed": 0,
    }
    with warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter("always")
        solved = milp(
            c=np.zeros(layout.size),
            constraints=base_constraint,
            integrality=np.ones(layout.size),
            bounds=Bounds(np.zeros(layout.size), np.ones(layout.size)),
            options=options,
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
    if unexpected:
        raise RuntimeError("unexpected scipy milp warning: " + " | ".join(str(item.message) for item in unexpected))
    if solved.x is None:
        return {
            "status": "INFEASIBLE_PROVEN" if int(solved.status) == 2 else "FEASIBILITY_NOT_RESOLVED",
            "solver_status": int(solved.status),
            "solver_message": str(solved.message),
            "variable_count": layout.size,
            "constraint_count": len(rows.lower),
            "solver_threads_requested": 1,
            "solver_random_seed": 0,
            "scipy_passthrough_warning_count": len(caught),
        }

    selected_by_step: list[set[str]] = []
    metrics: list[dict[str, Any]] = []
    for step, budget in enumerate(checkpoints):
        selected = {
            vertex for vertex in graph.nodes if solved.x[layout.index[("x", step, vertex)]] >= 0.5
        }
        selected_by_step.append(selected)
        closed = [
            edge for edge in graph.edges if edge.u in selected and edge.v in selected
        ]
        z_closed = {
            edge_index
            for edge_index in range(len(graph.edges))
            if solved.x[layout.index[("z", step, edge_index)]] >= 0.5
        }
        induced = {
            edge_index
            for edge_index, edge in enumerate(graph.edges)
            if edge.u in selected and edge.v in selected
        }
        assert z_closed == induced
        by_task: dict[str, int] = defaultdict(int)
        by_run: dict[str, int] = defaultdict(int)
        for edge in closed:
            by_task[edge.task] += 1
            by_run[edge.run] += 1
        metrics.append(
            {
                "budget": budget,
                "selected_endpoints": len(selected),
                "closed_edges": len(closed),
                "parents": len({edge.parent for edge in closed}),
                "tasks": len(by_task),
                "physical_runs": len(by_run),
                "maximum_single_task_share": ratio(max(by_task.values(), default=0), max(1, len(closed))),
                "maximum_single_run_share": ratio(max(by_run.values(), default=0), max(1, len(closed))),
            }
        )
    assert all(len(selected) == budget for selected, budget in zip(selected_by_step, checkpoints))
    assert all(selected_by_step[index] <= selected_by_step[index + 1] for index in range(len(checkpoints) - 1))
    assert all(metric["closed_edges"] >= floor for metric, floor in zip(metrics, yield_floors))
    assert metrics[-1]["parents"] >= terminal_parent_floor
    if anti_task_denominator is not None:
        assert metrics[-1]["maximum_single_task_share"]["numerator"] * anti_task_denominator <= metrics[-1]["maximum_single_task_share"]["denominator"]
    if anti_run_denominator is not None:
        assert metrics[-1]["maximum_single_run_share"]["numerator"] * anti_run_denominator <= metrics[-1]["maximum_single_run_share"]["denominator"]
    integrated_tasks = sum(int(metric["tasks"]) for metric in metrics)
    integrated_runs = sum(int(metric["physical_runs"]) for metric in metrics)
    if integrated_task_floor is not None:
        assert integrated_tasks >= integrated_task_floor
    if integrated_run_floor is not None:
        assert integrated_runs >= integrated_run_floor

    selected_fingerprint = hashlib.sha256(
        "\n".join(
            hashlib.sha256((str(step) + "\0" + vertex).encode()).hexdigest()
            for step, selected in enumerate(selected_by_step)
            for vertex in sorted(selected)
        ).encode()
    ).hexdigest()
    return {
        "status": "FEASIBLE_WITNESS",
        "variable_count": layout.size,
        "constraint_count": len(rows.lower),
        "integrated_task_floor": integrated_task_floor,
        "integrated_run_floor": integrated_run_floor,
        "solver_status": int(solved.status),
        "solver_message": str(solved.message),
        "solver_constant_objective_optimal": bool(solved.success),
        "solver_mip_gap": float(getattr(solved, "mip_gap", None) or 0.0),
        "solver_mip_node_count": int(getattr(solved, "mip_node_count", None) or 0),
        "solver_threads_requested": 1,
        "solver_random_seed": 0,
        "scipy_passthrough_warning_count": len(caught),
        "metrics": metrics,
        "private_selection_fingerprint_sha256": selected_fingerprint,
        "identities_emitted": False,
    }


def baseline_from_topology(graph: Any, checkpoints: list[int]) -> dict[int, dict[str, int]]:
    engine = source.engine
    rows: list[dict[str, Any]] = []
    maximum = checkpoints[-1]
    for seed in range(256):
        rows.extend(
            engine.snapshots_from_actions(
                graph,
                seed,
                checkpoints,
                engine.uniform_edge_actions(graph, seed, maximum),
            )
        )
    answer: dict[int, dict[str, int]] = {}
    for budget in checkpoints:
        selected = [row for row in rows if row["budget"] == budget]
        answer[budget] = {
            field: engine.nearest_rank([int(row[field]) for row in selected], 0.5)
            for field in ("closed_edges", "parents", "tasks", "physical_runs")
        }
    return answer


def paths(worktree: Path, data_root: Path, cards_root: Path) -> SimpleNamespace:
    return SimpleNamespace(
        prior_protocol=str(worktree / "phase1/historical_independent_label_scarce_yield_confirmation_v1.json"),
        prior_result=str(worktree / "phase1/results/historical_independent_label_scarce_yield_20260829_c7148fb/aggregate_result.json"),
        prior_verification=str(worktree / "phase1/results/historical_independent_label_scarce_yield_20260829_c7148fb/independent_verification.json"),
        prior_package_manifest=str(worktree / "phase1/results/historical_independent_label_scarce_yield_20260829_c7148fb/SHA256SUMS"),
        prior_independent_source=str(worktree / "phase1/verify_historical_independent_label_scarce_yield.py"),
        qualification_protocol=str(worktree / "phase1/historical_independent_sibling_graph_gate_v1.json"),
        qualification_result=str(worktree / "phase1/results/historical_independent_sibling_graph_gate_20260829_7ad83d2/formal_summary.json"),
        qualification_verification=str(worktree / "phase1/results/historical_independent_sibling_graph_gate_20260829_7ad83d2/verification.json"),
        qualification_package_manifest=str(worktree / "phase1/results/historical_independent_sibling_graph_gate_20260829_7ad83d2/SHA256SUMS"),
        independent_graph_qualification_source=str(worktree / "phase1/verify_historical_independent_sibling_graph_gate.py"),
        independent_acquisition_engine=str(worktree / "phase1/verify_tree_node_label_yield.py"),
        v11_pairs=str(worktree / "phase1/v11_decision/decision_train_v11_b0.jsonl"),
        v11_lineage=str(worktree / "phase1/results/decision_corpus_lineage_audit_v2_20260829_2514842/formal/producer_a.json"),
        senior_quarantine_protocol=str(worktree / "phase1/senior_0819_verified_sibling_quarantine_v1.json"),
        senior_quarantine_result=str(worktree / "phase1/results/senior_0819_verified_sibling_quarantine_20260829_254fc80/formal_summary.json"),
        senior_quarantine_verification=str(worktree / "phase1/results/senior_0819_verified_sibling_quarantine_20260829_254fc80/verification.json"),
        senior_quarantine_manifest=str(worktree / "phase1/results/senior_0819_verified_sibling_quarantine_20260829_254fc80/MANIFEST.sha256"),
        senior_security_receipt=str(cards_root / "security_scan.json"),
        senior_cards=str(cards_root / "cards.safe.json"),
        senior_run_split=str(data_root / "runsplit_holdruns.json"),
        senior_decision=str(data_root / "decision.jsonl"),
    )


def reconstruct(worktree: Path, data_root: Path, cards_root: Path) -> tuple[dict[int, Any], dict[str, Any]]:
    args = paths(worktree, data_root, cards_root)
    protocol_path = worktree / "phase1/historical_run_split_breadth_pareto_falsification_v1.json"
    protocol, _ = source.load_protocol(protocol_path, "76a6ad30188c53c4f93b1132d45f16608d025057a5624eae7c5b9f13d4544396")
    prior_result, _ = source.verify_prior_artifacts(args, protocol)
    prior_protocol, _ = source.prior.load_protocol(
        Path(args.prior_protocol), protocol["immutable_inputs"]["prior_protocol"]["sha256"]
    )
    qualification_result, _ = source.prior.verify_qualification(args, prior_protocol)
    graph, _ = source.prior.reconstruct_graph(args, prior_protocol, qualification_result)
    source.verify_full_graph_fingerprints(source.graph_fingerprint(graph), prior_result, qualification_result)
    split_edges = {0: [], 1: []}
    for edge in graph.edges:
        split_edges[source.fold_for_run(edge.run)].append(edge)
    return {fold: source.graph_from_edges(edges) for fold, edges in split_edges.items()}, protocol


def evaluate_real(args: argparse.Namespace) -> dict[str, Any]:
    worktree = Path(args.worktree).resolve()
    formal_result_path = Path(args.falsification_result).resolve()
    if source.engine.raw_sha256(formal_result_path) != "f1d8054ccc3e0d50f77a3ff4be29480f99ab0dbc51a6e1e510853da63c06e042":
        raise RuntimeError("falsification result SHA")
    prior_observation = json.loads(formal_result_path.read_text(encoding="utf-8"))
    if prior_observation["classification"] != "POSTREADOUT_RUN_SPLIT_BREADTH_PARETO_DOES_NOT_SURVIVE":
        raise RuntimeError("falsification classification")
    graphs, _ = reconstruct(worktree, Path(args.data_root).resolve(), Path(args.cards_root).resolve())
    folds: dict[str, Any] = {}
    for fold, graph in graphs.items():
        name = f"fold{fold}"
        checkpoints = source.budgets(graph, json.loads((worktree / "phase1/historical_run_split_breadth_pareto_falsification_v1.json").read_text()))
        baseline = baseline_from_topology(graph, checkpoints)
        published_by_budget = prior_observation["gates_by_fold"][name]["by_budget"]
        for budget in checkpoints:
            for field in ("closed_edges", "parents", "tasks", "physical_runs"):
                if baseline[budget][field] != published_by_budget[str(budget)][field]["uniform_median"]:
                    raise RuntimeError(f"baseline mismatch {name} {budget} {field}")
        yield_floors = [baseline[budget]["closed_edges"] for budget in checkpoints]
        terminal_parent_floor = math.ceil(9 * baseline[checkpoints[-1]]["parents"] / 10)
        published_integrated = prior_observation["gates_by_fold"][name]["integrated"]
        integrated_task_floor = math.ceil(6 * published_integrated["tasks"]["uniform_median"] / 5)
        integrated_run_floor = math.ceil(11 * published_integrated["physical_runs"]["uniform_median"] / 10)
        solved = solve_guarded(
            graph,
            checkpoints,
            yield_floors,
            terminal_parent_floor,
            args.time_limit_seconds,
            integrated_task_floor=integrated_task_floor,
            integrated_run_floor=integrated_run_floor,
        )
        if solved["status"] == "FEASIBLE_WITNESS":
            integrated = {
                field: sum(int(row[field]) for row in solved["metrics"])
                for field in ("closed_edges", "tasks", "physical_runs")
            }
            terminal = solved["metrics"][-1]
            gates = {
                "all_pointwise_yield_floors_met": all(
                    row["closed_edges"] >= floor for row, floor in zip(solved["metrics"], yield_floors)
                ),
                "integrated_yield_noninferiority": integrated["closed_edges"] >= published_integrated["closed_edges"]["uniform_median"],
                "integrated_task_breadth_at_least_6_over_5": integrated["tasks"] * 5 >= published_integrated["tasks"]["uniform_median"] * 6,
                "integrated_run_breadth_at_least_11_over_10": integrated["physical_runs"] * 10 >= published_integrated["physical_runs"]["uniform_median"] * 11,
                "terminal_parent_breadth_at_least_9_over_10": terminal["parents"] * 10 >= baseline[checkpoints[-1]]["parents"] * 9,
                "terminal_task_anti_dominance_at_most_1_over_3": terminal["maximum_single_task_share"]["numerator"] * 3 <= terminal["maximum_single_task_share"]["denominator"],
                "terminal_run_anti_dominance_at_most_1_over_10": terminal["maximum_single_run_share"]["numerator"] * 10 <= terminal["maximum_single_run_share"]["denominator"],
            }
            solved["integrated"] = integrated
            solved["baseline_integrated"] = {
                field: published_integrated[field]["uniform_median"]
                for field in ("closed_edges", "tasks", "physical_runs")
            }
            solved["baseline_by_budget"] = {str(budget): baseline[budget] for budget in checkpoints}
            solved["gates"] = gates
            solved["all_development_gates_pass"] = all(gates.values())
        folds[name] = solved
    return {
        "protocol": "yield-guarded-breadth-milp-development-v2",
        "status": "DEVELOPMENT_AFTER_BOTH_RUN_SPLIT_FOLDS_READOUT",
        "objective": "find a nested feasibility witness under fixed yield, breadth, parent, and anti-dominance gates",
        "yield_floor": "uniform-edge nearest-rank median at every checkpoint",
        "folds": folds,
        "all_folds_feasible_and_all_development_gates_pass": all(
            value.get("status") == "FEASIBLE_WITNESS" and value.get("all_development_gates_pass") is True
            for value in folds.values()
        ),
        "scope": {
            "post_readout_development_only": True,
            "external_confirmation": False,
            "labels_outcomes_predictions_code_runtime_used": False,
            "prospective_values_used": False,
            "identities_emitted": False,
            "gpu_api_model_fit_base_update": "0/0/0/0",
        },
    }


def self_test() -> None:
    engine = source.engine
    edges = [
        engine.Edge(f"u{i}", f"v{i}", f"p{i}", f"t{i % 4}", f"r{i % 5}")
        for i in range(8)
    ]
    graph = source.graph_from_edges(edges)
    result = solve_guarded(
        graph,
        checkpoints=[4, 6, 8],
        yield_floors=[2, 3, 4],
        terminal_parent_floor=4,
        time_limit_seconds=30,
        anti_task_denominator=None,
        anti_run_denominator=None,
    )
    assert result["status"] == "FEASIBLE_WITNESS", result
    assert [row["closed_edges"] for row in result["metrics"]] == [2, 3, 4]
    assert [row["selected_endpoints"] for row in result["metrics"]] == [4, 6, 8]
    assert result["identities_emitted"] is False

    # Independent exhaustive oracle for a small, overlapping graph.  This checks
    # both MILP stages instead of merely checking that a feasible solution exists.
    oracle_edges = [
        engine.Edge("a", "b", "p0", "t0", "r0"),
        engine.Edge("a", "c", "p1", "t0", "r0"),
        engine.Edge("b", "c", "p2", "t0", "r0"),
        engine.Edge("d", "e", "p3", "t1", "r1"),
        engine.Edge("e", "f", "p4", "t1", "r1"),
        engine.Edge("g", "h", "p5", "t2", "r2"),
        engine.Edge("i", "j", "p6", "t0", "r3"),
    ]
    oracle_graph = source.graph_from_edges(oracle_edges)
    oracle_checkpoints = [4, 7]
    oracle_floors = [1, 3]
    oracle = solve_guarded(
        oracle_graph,
        checkpoints=oracle_checkpoints,
        yield_floors=oracle_floors,
        terminal_parent_floor=3,
        time_limit_seconds=30,
        anti_task_denominator=2,
        anti_run_denominator=2,
        integrated_task_floor=4,
        integrated_run_floor=5,
    )
    assert oracle["status"] == "FEASIBLE_WITNESS", oracle
    feasible_trajectories = 0
    nodes = sorted(oracle_graph.nodes)
    for first_tuple in combinations(nodes, oracle_checkpoints[0]):
        first_selected = set(first_tuple)
        remaining = [node for node in nodes if node not in first_selected]
        for additions in combinations(remaining, oracle_checkpoints[1] - oracle_checkpoints[0]):
            trajectory = [first_selected, first_selected | set(additions)]
            rows = []
            for selected in trajectory:
                closed = [edge for edge in oracle_edges if edge.u in selected and edge.v in selected]
                rows.append(
                    {
                        "closed_edges": len(closed),
                        "parents": len({edge.parent for edge in closed}),
                        "tasks": len({edge.task for edge in closed}),
                        "runs": len({edge.run for edge in closed}),
                        "task_counts": {
                            task: sum(edge.task == task for edge in closed)
                            for task in {edge.task for edge in closed}
                        },
                        "run_counts": {
                            run: sum(edge.run == run for edge in closed)
                            for run in {edge.run for edge in closed}
                        },
                    }
                )
            if any(row["closed_edges"] < floor for row, floor in zip(rows, oracle_floors)):
                continue
            terminal = rows[-1]
            if terminal["parents"] < 3:
                continue
            if max(terminal["task_counts"].values(), default=0) * 2 > terminal["closed_edges"]:
                continue
            if max(terminal["run_counts"].values(), default=0) * 2 > terminal["closed_edges"]:
                continue
            if sum(row["tasks"] for row in rows) < 4:
                continue
            if sum(row["runs"] for row in rows) < 5:
                continue
            feasible_trajectories += 1
    assert feasible_trajectories > 0
    impossible = solve_guarded(
        oracle_graph,
        checkpoints=oracle_checkpoints,
        yield_floors=oracle_floors,
        terminal_parent_floor=3,
        time_limit_seconds=30,
        anti_task_denominator=2,
        anti_run_denominator=2,
        integrated_task_floor=7,
        integrated_run_floor=5,
    )
    assert impossible["status"] == "INFEASIBLE_PROVEN", impossible
    print(
        json.dumps(
            {
                "status": "SELF_TEST_PASS",
                "disjoint_metrics": result["metrics"],
                "exhaustive_reference_feasible_trajectories": feasible_trajectories,
                "exhaustive_reference_agrees_with_milp": True,
                "known_infeasible_rejected": True,
            },
            sort_keys=True,
        )
    )


def write_exclusive(path: Path, value: dict[str, Any]) -> None:
    descriptor = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    with os.fdopen(descriptor, "w", encoding="utf-8", newline="\n") as handle:
        handle.write(json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False) + "\n")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--self-test", action="store_true")
    parser.add_argument("--worktree")
    parser.add_argument("--data-root")
    parser.add_argument("--cards-root")
    parser.add_argument("--falsification-result")
    parser.add_argument("--time-limit-seconds", type=float, default=300)
    parser.add_argument("--output")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    if args.self_test:
        self_test()
        return
    required = (args.worktree, args.data_root, args.cards_root, args.falsification_result, args.output)
    if not all(required):
        raise SystemExit("real run requires --worktree --data-root --cards-root --falsification-result --output")
    result = evaluate_real(args)
    write_exclusive(Path(args.output).resolve(), result)
    print(json.dumps({
        "status": result["status"],
        "all_folds_pass": result["all_folds_feasible_and_all_development_gates_pass"],
        "output_sha256": source.engine.raw_sha256(Path(args.output).resolve()),
        "scope": result["scope"],
    }, sort_keys=True))


if __name__ == "__main__":
    main()
