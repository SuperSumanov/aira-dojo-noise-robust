#!/usr/bin/env python3
"""One-time outcome-blind Target-522 confirmation of exact-B yield-guarded breadth."""

from __future__ import annotations

import argparse
from collections import Counter, defaultdict
import hashlib
import itertools
import json
import math
import os
from pathlib import Path
import re
from typing import Any
import warnings

from phase1 import audit_tree_within_stratum_forward_target522 as target
from phase1 import audit_yield_guarded_breadth_exact_budget_development_v1 as exact_dev
from phase1 import develop_yield_guarded_breadth_feasibility_v2 as milp_dev
from phase1 import falsify_historical_run_split_breadth_pareto as graph_impl


PROTOCOL_NAME = "yield-guarded-breadth-forward-target522-v1"
PUBLIC_PROTOCOL = "yield-guarded-breadth-forward-target522-public-result-v1"
PRIVATE_PROTOCOL = "yield-guarded-breadth-forward-target522-private-witness-v1"
SHA_RE = re.compile(r"[0-9a-f]{64}")
COMMIT_RE = re.compile(r"[0-9a-f]{40}")
PAIR_KEYS = {"task", "run_id", "parent", "left", "right"}


class ForwardBreadthError(RuntimeError):
    pass


def require(condition: bool, message: str) -> None:
    if not condition:
        raise ForwardBreadthError(message)


def canonical_bytes(value: Any) -> bytes:
    return (
        json.dumps(
            value,
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
            allow_nan=False,
        )
        + "\n"
    ).encode()


def canonical_sha(value: Any) -> str:
    return hashlib.sha256(canonical_bytes(value)).hexdigest()


def file_sha(path: Path) -> str:
    return target.sha256_file(path)


def load_protocol(path: Path, expected_sha: str) -> tuple[dict[str, Any], str]:
    require(SHA_RE.fullmatch(expected_sha) is not None, "invalid protocol SHA")
    actual = file_sha(path)
    require(actual == expected_sha, "protocol SHA mismatch")
    protocol = target.read_object(path)
    require(protocol.get("protocol") == PROTOCOL_NAME, "protocol name mismatch")
    require(
        protocol.get("status") == "FROZEN_BEFORE_TARGET522_SELECTION_OR_SIBLING_GRAPH_PROFILE",
        "protocol freeze status mismatch",
    )
    freeze = protocol.get("freeze_state") or {}
    require(freeze.get("candidate_identity_counts_or_profile_seen") is False, "candidate seen before freeze")
    observation = freeze.get("freeze_observation") or {}
    require(observation.get("target522_selection_complete_present") is False, "selection completed before freeze")
    require(observation.get("target522_selection_failed_present") is False, "selection failed before freeze")
    require(observation.get("prospective_values_read") is False, "prospective values seen before freeze")
    contract = protocol["acquisition"]["uniform_edge_exact_budget_contract"]
    require("selected_endpoints equals" in contract["required_invariant"], "exact-B invariant missing")
    return protocol, actual


def original_target_protocol(
    repo_root: Path, protocol: dict[str, Any]
) -> tuple[dict[str, Any], str]:
    binding = protocol["freeze_state"]["target522_selection_protocol"]
    path = repo_root / binding["path"]
    return target.load_protocol(path, binding["sha256"])


def selection_and_increment(
    state_root: Path,
    selection_root: Path,
    repo_root: Path,
    protocol: dict[str, Any],
) -> tuple[
    dict[str, Any],
    target.BlindSnapshot,
    dict[str, Any],
    dict[str, Any],
    dict[str, Any],
]:
    target_protocol, target_protocol_sha = original_target_protocol(repo_root, protocol)
    selection = target.verify_selection(
        selection_root, repo_root, target_protocol, target_protocol_sha
    )
    monitor_binding = protocol["freeze_state"]["target522_selection_monitor"]
    monitor_path = repo_root / monitor_binding["path"]
    require(file_sha(monitor_path) == monitor_binding["sha256"], "selection monitor SHA mismatch")
    require(
        selection["selection_monitor_source_sha256"] == monitor_binding["sha256"],
        "selection package monitor SHA mismatch",
    )
    expected_selection_root = protocol["freeze_state"]["target522_selection_root"]
    require(str(selection_root.resolve()) == expected_selection_root, "selection root mismatch")
    baseline = target.load_blind_snapshot(
        state_root, selection["baseline_snapshot_sha256"]
    )
    candidate = target.load_blind_snapshot(
        state_root, selection["candidate_snapshot_sha256"]
    )
    increment_cards, increment_runs, append_only = target.disjoint_increment(
        baseline, candidate, target_protocol
    )
    require(
        len(increment_runs) >= protocol["population"]["physical_run_increment_minimum"],
        "increment below frozen minimum",
    )
    return selection, candidate, increment_cards, increment_runs, append_only


def structural_pair_graph(
    state_root: Path,
    candidate: target.BlindSnapshot,
    increment_cards: dict[str, dict[str, Any]],
    increment_runs: dict[str, dict[str, Any]],
) -> tuple[Any, dict[str, Any]]:
    state = state_root.resolve()
    run_ids = set(increment_runs)
    rows: list[dict[str, str]] = []
    bound_pair_hashes: list[str] = []
    selected_pair_file_count = 0
    for raw in candidate.registry_raw_rows:
        registry = json.loads(raw.decode("utf-8"))
        intake = Path(registry["intake_dir"])
        require(
            intake.resolve().parent == state / "intakes"
            and intake.resolve().name == registry["drop_id"],
            "unsafe intake path",
        )
        summary = target.read_object(intake / "summary.json")
        pair_sha = summary.get("outputs", {}).get("eligible_structural_pairs_sha256")
        require(isinstance(pair_sha, str) and SHA_RE.fullmatch(pair_sha), "pair SHA")
        pair_path = intake / "eligible_structural_pairs.jsonl"
        require(file_sha(pair_path) == pair_sha, "pair file SHA mismatch")
        raw_pairs = pair_path.read_bytes()
        require(target.CREDENTIAL_RE.search(raw_pairs) is None, "credential-shaped pair bytes")
        bound_pair_hashes.append(pair_sha)
        selected_here = 0
        for row, _raw_row in target.read_rows_raw(pair_path):
            require(set(row) == PAIR_KEYS, "pair schema mismatch")
            if row["run_id"] not in run_ids:
                continue
            require(
                all(isinstance(row[key], str) and row[key] for key in PAIR_KEYS),
                "invalid pair field",
            )
            require(row["left"] < row["right"], "noncanonical pair order")
            rows.append(row)
            selected_here += 1
        selected_pair_file_count += int(selected_here > 0)

    expected = {
        (task, run, parent, left, right)
        for (task, run, parent), children in sibling_groups(increment_cards).items()
        for left, right in itertools.combinations(sorted(children), 2)
    }
    observed = {
        (row["task"], row["run_id"], row["parent"], row["left"], row["right"])
        for row in rows
    }
    require(len(observed) == len(rows), "duplicate structural pair")
    require(observed == expected, "pair files are not the exact sibling clique")
    edges = [
        graph_impl.engine.Edge(left, right, parent, task_name, run)
        for task_name, run, parent, left, right in sorted(observed)
    ]
    graph = graph_impl.graph_from_edges(edges)
    require(set(graph.nodes) <= set(increment_cards), "pair endpoint outside increment")
    fingerprint = hashlib.sha256(
        "\n".join(
            hashlib.sha256("\0".join(item).encode()).hexdigest()
            for item in sorted(observed)
        ).encode()
    ).hexdigest()
    bindings = {
        "all_candidate_intake_pair_files_count": len(bound_pair_hashes),
        "increment_contributing_pair_files_count": selected_pair_file_count,
        "candidate_pair_sha_multiset_sha256": canonical_sha(sorted(bound_pair_hashes)),
        "increment_pair_graph_sha256": fingerprint,
        "structural_pair_files_equal_exact_observed_sibling_cliques": True,
    }
    return graph, bindings


def sibling_groups(cards: dict[str, dict[str, Any]]) -> dict[tuple[str, str, str], set[str]]:
    groups: dict[tuple[str, str, str], set[str]] = defaultdict(set)
    for identifier, card in cards.items():
        parent = card["parent"]
        require(isinstance(parent, str) and parent, "empty parent in eligible card")
        groups[(card["task"], card["run"], parent)].add(identifier)
    return groups


def ratio(numerator: int, denominator: int) -> dict[str, Any]:
    return milp_dev.ratio(numerator, denominator)


def graph_support(graph: Any, protocol: dict[str, Any]) -> tuple[dict[str, Any], dict[str, bool]]:
    task_counts = Counter(edge.task for edge in graph.edges)
    run_counts = Counter(edge.run for edge in graph.edges)
    pairs = len(graph.edges)
    census = {
        "pairs": pairs,
        "endpoints": len(graph.nodes),
        "parents": len({edge.parent for edge in graph.edges}),
        "physical_runs": len(run_counts),
        "tasks": len(task_counts),
        "maximum_single_task_pair_share": ratio(max(task_counts.values(), default=0), max(1, pairs)),
        "maximum_single_run_pair_share": ratio(max(run_counts.values(), default=0), max(1, pairs)),
    }
    fixed = protocol["support_gates_before_acquisition"]
    gates = {
        "minimum_pairs": census["pairs"] >= fixed["minimum_pairs"],
        "minimum_endpoints": census["endpoints"] >= fixed["minimum_endpoints"],
        "minimum_parents": census["parents"] >= fixed["minimum_parents"],
        "minimum_physical_runs": census["physical_runs"] >= fixed["minimum_physical_runs"],
        "minimum_tasks": census["tasks"] >= fixed["minimum_tasks"],
        "maximum_single_task_pair_share": census["maximum_single_task_pair_share"]["numerator"] * 3
        <= census["maximum_single_task_pair_share"]["denominator"],
        "maximum_single_run_pair_share": census["maximum_single_run_pair_share"]["numerator"] * 10
        <= census["maximum_single_run_pair_share"]["denominator"],
    }
    return census, gates


def checkpoints(graph: Any, protocol: dict[str, Any]) -> list[int]:
    acquisition = protocol["acquisition"]
    denominator = acquisition["budget_fraction_denominator"]
    values = [
        math.floor(len(graph.nodes) * numerator / denominator)
        for numerator in acquisition["budget_fraction_numerators"]
    ]
    require(values == sorted(set(values)) and len(values) == 6 and values[0] >= 2, "checkpoint closure")
    return values


def exact_baseline(graph: Any, budgets: list[int]) -> tuple[dict[str, Any], list[int], dict[str, int]]:
    rows, old_underfilled = exact_dev.baseline_rows(graph, budgets)
    require(old_underfilled >= 0, "underfill diagnostic")
    by_budget, integrated = exact_dev.summarize_baseline(rows, budgets)
    require(all(row["selected_endpoints"] == row["budget"] for row in rows), "exact-B baseline")
    floors = [by_budget[budget]["closed_edges"] for budget in budgets]
    return {
        "seeds": 256,
        "rows": len(rows),
        "all_rows_exact_endpoint_budget": True,
        "by_budget_nearest_rank_median": {str(key): value for key, value in by_budget.items()},
        "integrated_trajectory_nearest_rank_median": integrated,
        "historical_atomic_underfill_diagnostic_rows": old_underfilled,
    }, floors, integrated


def solve_private(
    graph: Any,
    budgets: list[int],
    yield_floors: list[int],
    integrated_yield_floor: int,
    task_floor: int,
    run_floor: int,
    parent_floor: int,
    time_limit: float,
) -> tuple[dict[str, Any], dict[str, Any] | None]:
    import numpy as np
    from scipy.optimize import Bounds, LinearConstraint, milp
    from scipy.sparse import coo_matrix

    layout, tasks, runs, parents = milp_dev.make_layout(graph, budgets)
    rows = milp_dev.build_constraints(
        graph,
        budgets,
        yield_floors,
        parent_floor,
        layout,
        tasks,
        runs,
        parents,
        3,
        10,
        task_floor,
        run_floor,
    )
    rows.add(
        (
            (layout.index[("z", step, edge_index)], 1)
            for step in range(len(budgets))
            for edge_index in range(len(graph.edges))
        ),
        integrated_yield_floor,
        math.inf,
    )
    matrix = coo_matrix(
        (rows.data, (rows.row, rows.col)), shape=(len(rows.lower), layout.size)
    ).tocsr()
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
            c=np.zeros(layout.size),
            constraints=LinearConstraint(matrix, np.array(rows.lower), np.array(rows.upper)),
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
    require(not unexpected, "unexpected solver warning")
    common = {
        "solver_status": int(solved.status),
        "solver_message": str(solved.message),
        "variable_count": layout.size,
        "constraint_count": len(rows.lower),
        "solver_threads_requested": 1,
        "solver_random_seed": 0,
        "solver_mip_gap": float(getattr(solved, "mip_gap", 0.0) or 0.0),
        "solver_mip_node_count": int(getattr(solved, "mip_node_count", 0) or 0),
    }
    if solved.x is None:
        common["status"] = (
            "INFEASIBLE_PROVEN" if int(solved.status) == 2 else "FEASIBILITY_UNRESOLVED"
        )
        return common, None

    selected_by_step = [
        sorted(
            vertex
            for vertex in graph.nodes
            if solved.x[layout.index[("x", step, vertex)]] >= 0.5
        )
        for step in range(len(budgets))
    ]
    require(
        all(len(selected) == budget for selected, budget in zip(selected_by_step, budgets)),
        "solver exact budget",
    )
    require(
        all(set(selected_by_step[index]) <= set(selected_by_step[index + 1]) for index in range(len(budgets) - 1)),
        "solver trajectory not nested",
    )
    metrics = [metrics_for_selection(graph, set(selected), budget) for selected, budget in zip(selected_by_step, budgets)]
    common.update(
        {
            "status": "FEASIBLE_WITNESS",
            "metrics": metrics,
            "integrated": {
                field: sum(int(row[field]) for row in metrics)
                for field in ("closed_edges", "tasks", "physical_runs")
            },
        }
    )
    private = {
        "protocol": PRIVATE_PROTOCOL,
        "checkpoints": budgets,
        "selected_endpoint_ids_by_checkpoint": [
            {"budget": budget, "endpoint_ids": selected}
            for budget, selected in zip(budgets, selected_by_step)
        ],
        "identities_publicly_emitted": False,
    }
    private["selection_fingerprint_sha256"] = canonical_sha(
        private["selected_endpoint_ids_by_checkpoint"]
    )
    return common, private


def metrics_for_selection(graph: Any, selected: set[str], budget: int) -> dict[str, Any]:
    closed = [edge for edge in graph.edges if edge.u in selected and edge.v in selected]
    by_task = Counter(edge.task for edge in closed)
    by_run = Counter(edge.run for edge in closed)
    return {
        "budget": budget,
        "selected_endpoints": len(selected),
        "closed_edges": len(closed),
        "parents": len({edge.parent for edge in closed}),
        "tasks": len(by_task),
        "physical_runs": len(by_run),
        "maximum_single_task_share": ratio(max(by_task.values(), default=0), max(1, len(closed))),
        "maximum_single_run_share": ratio(max(by_run.values(), default=0), max(1, len(closed))),
    }


def fixed_floors(
    baseline: dict[str, Any], budgets: list[int]
) -> dict[str, int | list[int]]:
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


def gates_for_witness(
    solver: dict[str, Any], baseline: dict[str, Any], floors: dict[str, Any]
) -> dict[str, bool]:
    metrics = solver["metrics"]
    integrated = solver["integrated"]
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


def build(args: argparse.Namespace) -> tuple[dict[str, Any], dict[str, Any] | None]:
    protocol, protocol_sha = load_protocol(args.protocol.resolve(), args.protocol_sha256)
    require(COMMIT_RE.fullmatch(args.source_commit) is not None, "source commit")
    selection, candidate, increment_cards, increment_runs, append_only = selection_and_increment(
        args.state_root.resolve(),
        args.selection_root.resolve(),
        args.repo_root.resolve(),
        protocol,
    )
    graph, pair_bindings = structural_pair_graph(
        args.state_root.resolve(), candidate, increment_cards, increment_runs
    )
    census, support = graph_support(graph, protocol)
    base = {
        "protocol": PUBLIC_PROTOCOL,
        "status": "COMPLETE",
        "protocol_sha256": protocol_sha,
        "analysis_source_commit": args.source_commit,
        "selection_binding": {
            "baseline_snapshot_sha256": selection["baseline_snapshot_sha256"],
            "candidate_snapshot_sha256": selection["candidate_snapshot_sha256"],
            "selection_support_sha256sums_sha256": selection[
                "selection_support_sha256sums_sha256"
            ],
            "append_only": append_only,
            "pair_files": pair_bindings,
        },
        "graph_census": census,
        "support_gates": support,
        "scope": {
            "outcome_blind_topology_only": True,
            "aggregate_public_output": True,
            "endpoint_parent_task_run_identities_publicly_emitted": False,
            "pair_orientation_gap_grade_prediction_runtime_used": False,
            "code_used_by_acquisition_or_metrics": False,
            "prospective_label_outcome_prediction_values_read": False,
            "gpu_api_model_fit_base_update": "0/0/0/0",
        },
    }
    if not all(support.values()):
        base.update(
            {
                "classification": "FORWARD_TARGET522_YIELD_GUARDED_BREADTH_LIMITED_SUPPORT",
                "baseline": None,
                "fixed_floors": None,
                "solver": None,
                "witness_gates": None,
                "private_witness_sha256": None,
            }
        )
        return base, None

    budgets = checkpoints(graph, protocol)
    baseline, yield_floors, integrated = exact_baseline(graph, budgets)
    floors = fixed_floors(baseline, budgets)
    require(floors["pointwise_closed_edges"] == yield_floors, "floor mismatch")
    solver, private = solve_private(
        graph,
        budgets,
        yield_floors,
        int(floors["integrated_closed_edges"]),
        int(floors["integrated_tasks"]),
        int(floors["integrated_physical_runs"]),
        int(floors["terminal_parents"]),
        protocol["acquisition"]["solver_time_limit_seconds"],
    )
    if solver["status"] == "FEASIBLE_WITNESS":
        require(private is not None, "missing private witness")
        witness_gates = gates_for_witness(solver, baseline, floors)
        require(all(witness_gates.values()), "solver witness failed fixed gate")
        classification = "FORWARD_TARGET522_YIELD_GUARDED_BREADTH_JOINTLY_FEASIBLE"
        private_sha = hashlib.sha256(canonical_bytes(private)).hexdigest()
    elif solver["status"] == "INFEASIBLE_PROVEN":
        witness_gates = None
        classification = "FORWARD_TARGET522_YIELD_GUARDED_BREADTH_INFEASIBLE_PROVEN"
        private_sha = None
    else:
        witness_gates = None
        classification = "FORWARD_TARGET522_YIELD_GUARDED_BREADTH_FEASIBILITY_UNRESOLVED"
        private_sha = None
    require(classification in protocol["ordered_classification"], "classification outside protocol")
    base.update(
        {
            "classification": classification,
            "checkpoints": budgets,
            "baseline": baseline,
            "fixed_floors": floors,
            "solver": solver,
            "witness_gates": witness_gates,
            "private_witness_sha256": private_sha,
        }
    )
    return base, private


def write_exclusive(path: Path, value: dict[str, Any]) -> None:
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


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--protocol", type=Path, required=True)
    parser.add_argument("--protocol-sha256", required=True)
    parser.add_argument("--source-commit", required=True)
    parser.add_argument("--state-root", type=Path, required=True)
    parser.add_argument("--selection-root", type=Path, required=True)
    parser.add_argument("--repo-root", type=Path, required=True)
    parser.add_argument("--public-output", type=Path, required=True)
    parser.add_argument("--private-output", type=Path, required=True)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    public, private = build(args)
    if private is not None:
        write_exclusive(args.private_output.resolve(), private)
        require(
            file_sha(args.private_output.resolve()) == public["private_witness_sha256"],
            "private witness write hash",
        )
    else:
        require(not args.private_output.exists(), "unexpected private output")
    write_exclusive(args.public_output.resolve(), public)
    print(
        json.dumps(
            {
                "status": public["status"],
                "classification": public["classification"],
                "protocol_sha256": public["protocol_sha256"],
                "public_output_sha256": file_sha(args.public_output.resolve()),
                "private_witness_present": private is not None,
                "scope": public["scope"],
            },
            sort_keys=True,
        )
    )


if __name__ == "__main__":
    main()
