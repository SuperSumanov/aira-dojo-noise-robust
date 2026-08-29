#!/usr/bin/env python3
# Public source for the post-readout exact-budget robustness audit.
"""Development audit for an exact-endpoint-budget uniform-edge baseline.

This script only reads the already disclosed historical topology.  It emits
aggregate metrics and never emits endpoint, parent, task, or run identities.
"""

from __future__ import annotations

import argparse
from collections import defaultdict
import json
import math
import os
from pathlib import Path
from typing import Any, Iterable

from phase1 import develop_yield_guarded_breadth_feasibility_v2 as dev
from phase1 import falsify_historical_run_split_breadth_pareto as source


def require(condition: bool, message: str) -> None:
    if not condition:
        raise RuntimeError(message)


def exact_uniform_edge_actions(
    graph: Any, seed: int, maximum_budget: int
) -> Iterable[tuple[str, ...]]:
    """Preserve edge priority while making every endpoint prefix observable.

    The old implementation yielded both unseen endpoints of an edge as one
    atomic action.  An odd checkpoint between those endpoints therefore saw
    B-1 selected endpoints.  Here the same edge order is retained, but the two
    endpoints are deterministically linearized.  If the final budget has only
    one slot and an edge needs two endpoints, that edge is skipped exactly as
    before; a separately salted singleton fill then uses every remaining slot.
    """

    engine = source.engine
    selected: set[str] = set()
    ordered_edges = sorted(
        graph.edges,
        key=lambda edge: engine.hash_key(seed, "EDGE", edge.u, edge.v),
    )
    for edge in ordered_edges:
        missing = [node for node in edge.endpoints if node not in selected]
        if not missing or len(selected) + len(missing) > maximum_budget:
            continue
        missing.sort(
            key=lambda node: engine.hash_key(
                seed, "EDGE-ENDPOINT", edge.u, edge.v, node
            )
        )
        for node in missing:
            selected.add(node)
            yield (node,)
        if len(selected) == maximum_budget:
            return

    remaining = sorted(
        (node for node in graph.nodes if node not in selected),
        key=lambda node: engine.hash_key(seed, "EDGE-FILL", node),
    )
    for node in remaining:
        if len(selected) == maximum_budget:
            break
        selected.add(node)
        yield (node,)
    require(len(selected) == maximum_budget, "exact baseline did not fill maximum budget")


def direct_metrics(graph: Any, selected: set[str], seed: int, budget: int) -> dict[str, Any]:
    engine = source.engine
    closed = [edge for edge in graph.edges if edge.u in selected and edge.v in selected]
    by_task: dict[str, int] = defaultdict(int)
    by_run: dict[str, int] = defaultdict(int)
    for edge in closed:
        by_task[edge.task] += 1
        by_run[edge.run] += 1
    return {
        "seed": seed,
        "budget": budget,
        "selected_endpoints": len(selected),
        "closed_edges": len(closed),
        "parents": len({edge.parent for edge in closed}),
        "tasks": len(by_task),
        "physical_runs": len(by_run),
        "maximum_single_task_share": engine.fraction(
            max(by_task.values(), default=0), max(1, len(closed))
        ),
        "maximum_single_run_share": engine.fraction(
            max(by_run.values(), default=0), max(1, len(closed))
        ),
    }


def independent_prefix_rows(graph: Any, seed: int, budgets: list[int]) -> list[dict[str, Any]]:
    maximum = budgets[-1]
    order = [action[0] for action in exact_uniform_edge_actions(graph, seed, maximum)]
    require(len(order) == maximum and len(set(order)) == maximum, "prefix order closure")
    return [direct_metrics(graph, set(order[:budget]), seed, budget) for budget in budgets]


def baseline_rows(graph: Any, checkpoints: list[int]) -> tuple[list[dict[str, Any]], int]:
    engine = source.engine
    exact: list[dict[str, Any]] = []
    old_underfilled = 0
    for seed in range(256):
        old = engine.snapshots_from_actions(
            graph,
            seed,
            checkpoints,
            engine.uniform_edge_actions(graph, seed, checkpoints[-1]),
        )
        old_underfilled += sum(
            int(row["selected_endpoints"] != row["budget"]) for row in old
        )
        rows = engine.snapshots_from_actions(
            graph,
            seed,
            checkpoints,
            exact_uniform_edge_actions(graph, seed, checkpoints[-1]),
        )
        independent = independent_prefix_rows(graph, seed, checkpoints)
        fields = (
            "seed",
            "budget",
            "selected_endpoints",
            "closed_edges",
            "parents",
            "tasks",
            "physical_runs",
            "maximum_single_task_share",
            "maximum_single_run_share",
        )
        require(
            [{field: row[field] for field in fields} for row in rows]
            == [{field: row[field] for field in fields} for row in independent],
            f"independent exact baseline mismatch seed={seed}",
        )
        exact.extend(rows)
    require(len(exact) == 256 * len(checkpoints), "exact row count")
    require(
        all(row["selected_endpoints"] == row["budget"] for row in exact),
        "exact endpoint-budget invariant",
    )
    return exact, old_underfilled


def nearest(values: list[int]) -> int:
    return source.engine.nearest_rank(values, 0.5)


def summarize_baseline(
    rows: list[dict[str, Any]], checkpoints: list[int]
) -> tuple[dict[int, dict[str, int]], dict[str, int]]:
    by_budget: dict[int, dict[str, int]] = {}
    fields = ("closed_edges", "parents", "tasks", "physical_runs")
    for budget in checkpoints:
        subset = [row for row in rows if row["budget"] == budget]
        require(len(subset) == 256, f"seed rows budget={budget}")
        by_budget[budget] = {
            field: nearest([int(row[field]) for row in subset]) for field in fields
        }
    integrated: dict[str, int] = {}
    for field in ("closed_edges", "tasks", "physical_runs"):
        by_seed: dict[int, int] = defaultdict(int)
        for row in rows:
            by_seed[int(row["seed"])] += int(row[field])
        require(sorted(by_seed) == list(range(256)), f"integrated seed closure {field}")
        integrated[field] = nearest(list(by_seed.values()))
    return by_budget, integrated


def evaluate(args: argparse.Namespace) -> dict[str, Any]:
    worktree = args.worktree.resolve()
    formal_result = args.falsification_result.resolve()
    require(
        source.engine.raw_sha256(formal_result)
        == "f1d8054ccc3e0d50f77a3ff4be29480f99ab0dbc51a6e1e510853da63c06e042",
        "falsification result SHA",
    )
    observation = json.loads(formal_result.read_text(encoding="utf-8"))
    require(
        observation["classification"]
        == "POSTREADOUT_RUN_SPLIT_BREADTH_PARETO_DOES_NOT_SURVIVE",
        "falsification classification",
    )
    graphs, protocol = dev.reconstruct(worktree, args.data_root.resolve(), args.cards_root.resolve())
    folds: dict[str, Any] = {}
    for fold in (0, 1):
        graph = graphs[fold]
        name = f"fold{fold}"
        checkpoints = source.budgets(graph, protocol)
        rows, old_underfilled = baseline_rows(graph, checkpoints)
        baseline, integrated_baseline = summarize_baseline(rows, checkpoints)
        yield_floors = [baseline[budget]["closed_edges"] for budget in checkpoints]
        require(
            sum(yield_floors) >= integrated_baseline["closed_edges"],
            f"pointwise floors do not imply integrated yield floor {name}",
        )
        task_floor = math.ceil(6 * integrated_baseline["tasks"] / 5)
        run_floor = math.ceil(11 * integrated_baseline["physical_runs"] / 10)
        parent_floor = math.ceil(9 * baseline[checkpoints[-1]]["parents"] / 10)
        solved = dev.solve_guarded(
            graph,
            checkpoints,
            yield_floors,
            parent_floor,
            args.time_limit_seconds,
            integrated_task_floor=task_floor,
            integrated_run_floor=run_floor,
        )
        solved["checkpoints"] = checkpoints
        solved["baseline_exact_endpoint_budget"] = True
        solved["baseline_rows"] = len(rows)
        solved["old_baseline_underfilled_checkpoint_rows"] = old_underfilled
        solved["baseline_by_budget"] = {str(key): value for key, value in baseline.items()}
        solved["baseline_integrated"] = integrated_baseline
        solved["pointwise_floors_imply_integrated_yield_floor"] = True
        if solved["status"] == "FEASIBLE_WITNESS":
            integrated = {
                field: sum(int(row[field]) for row in solved["metrics"])
                for field in ("closed_edges", "tasks", "physical_runs")
            }
            terminal = solved["metrics"][-1]
            gates = {
                "exact_endpoint_budget_all_checkpoints": all(
                    row["selected_endpoints"] == row["budget"]
                    for row in solved["metrics"]
                ),
                "all_pointwise_yield_floors_met": all(
                    row["closed_edges"] >= floor
                    for row, floor in zip(solved["metrics"], yield_floors)
                ),
                "integrated_yield_noninferiority": integrated["closed_edges"]
                >= integrated_baseline["closed_edges"],
                "integrated_task_breadth_at_least_6_over_5": integrated["tasks"] * 5
                >= integrated_baseline["tasks"] * 6,
                "integrated_run_breadth_at_least_11_over_10": integrated["physical_runs"] * 10
                >= integrated_baseline["physical_runs"] * 11,
                "terminal_parent_breadth_at_least_9_over_10": terminal["parents"] * 10
                >= baseline[checkpoints[-1]]["parents"] * 9,
                "terminal_task_anti_dominance_at_most_1_over_3": terminal[
                    "maximum_single_task_share"
                ]["numerator"]
                * 3
                <= terminal["maximum_single_task_share"]["denominator"],
                "terminal_run_anti_dominance_at_most_1_over_10": terminal[
                    "maximum_single_run_share"
                ]["numerator"]
                * 10
                <= terminal["maximum_single_run_share"]["denominator"],
            }
            solved["integrated"] = integrated
            solved["gates"] = gates
            solved["all_exact_budget_development_gates_pass"] = all(gates.values())
        folds[name] = solved

    all_pass = all(
        value.get("status") == "FEASIBLE_WITNESS"
        and value.get("all_exact_budget_development_gates_pass") is True
        for value in folds.values()
    )
    return {
        "protocol": "yield-guarded-breadth-exact-budget-audit-v1",
        "status": "DEVELOPMENT_AFTER_HISTORICAL_GRAPH_READOUT",
        "classification": (
            "HISTORICAL_RUN_SPLIT_EXACT_BUDGET_YIELD_GUARDED_BREADTH_JOINTLY_FEASIBLE_DEVELOPMENT_ONLY"
            if all_pass
            else "HISTORICAL_RUN_SPLIT_EXACT_BUDGET_YIELD_GUARDED_BREADTH_NOT_ESTABLISHED"
        ),
        "folds": folds,
        "all_folds_feasible_and_all_exact_budget_development_gates_pass": all_pass,
        "scope": {
            "historical_post_readout_development_only": True,
            "external_confirmation": False,
            "aggregate_only": True,
            "endpoint_parent_task_run_identities_emitted": False,
            "prospective_values_read": False,
            "labels_outcomes_predictions_code_runtime_used": False,
            "gpu_api_model_fit_base_update": "0/0/0/0",
        },
    }


def write_exclusive(path: Path, value: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    descriptor = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    with os.fdopen(descriptor, "w", encoding="utf-8", newline="\n") as handle:
        handle.write(
            json.dumps(
                value,
                ensure_ascii=False,
                sort_keys=True,
                separators=(",", ":"),
                allow_nan=False,
            )
            + "\n"
        )


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--worktree", type=Path, required=True)
    parser.add_argument("--data-root", type=Path, required=True)
    parser.add_argument("--cards-root", type=Path, required=True)
    parser.add_argument("--falsification-result", type=Path, required=True)
    parser.add_argument("--time-limit-seconds", type=float, default=300)
    parser.add_argument("--output", type=Path, required=True)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    result = evaluate(args)
    write_exclusive(args.output.resolve(), result)
    print(
        json.dumps(
            {
                "status": result["status"],
                "classification": result["classification"],
                "all_folds_pass": result[
                    "all_folds_feasible_and_all_exact_budget_development_gates_pass"
                ],
                "output_sha256": source.engine.raw_sha256(args.output.resolve()),
                "scope": result["scope"],
            },
            sort_keys=True,
        )
    )


if __name__ == "__main__":
    main()
