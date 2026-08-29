#!/usr/bin/env python3
# Independent public verifier; it intentionally never imports the producer.
"""Independent aggregate verifier for the exact-B historical development audit.

This module intentionally does not import the audited producer.  It rebuilds
the exact-B endpoint order and all baseline aggregates from the historical
topology.  The private MILP endpoint witness is not present in the aggregate
result, so this verifier explicitly does not claim to recompute that witness.
"""

from __future__ import annotations

import argparse
from collections import defaultdict
import hashlib
import json
import math
import os
from pathlib import Path
from typing import Any

from phase1 import develop_yield_guarded_breadth_feasibility_v2 as dev
from phase1 import falsify_historical_run_split_breadth_pareto as source


EXPECTED_RESULT_SHA = "86bdcee7005914d6fcdaf2f39be517cf725fed785f7e590f7916c97f11051314"


def require(condition: bool, message: str) -> None:
    if not condition:
        raise RuntimeError(message)


def digest(path: Path) -> str:
    answer = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1 << 20), b""):
            answer.update(block)
    return answer.hexdigest()


def exact_order(graph: Any, seed: int, maximum: int) -> list[str]:
    engine = source.engine
    chosen: set[str] = set()
    order: list[str] = []
    edges = list(graph.edges)
    edges.sort(key=lambda edge: engine.hash_key(seed, "EDGE", edge.u, edge.v))
    for edge in edges:
        pending = [value for value in (edge.u, edge.v) if value not in chosen]
        if len(chosen) + len(pending) > maximum or not pending:
            continue
        pending.sort(
            key=lambda value: engine.hash_key(
                seed, "EDGE-ENDPOINT", edge.u, edge.v, value
            )
        )
        for value in pending:
            require(value not in chosen, "duplicate exact-order endpoint")
            chosen.add(value)
            order.append(value)
        if len(order) == maximum:
            return order
    fill = list(set(graph.nodes) - chosen)
    fill.sort(key=lambda value: engine.hash_key(seed, "EDGE-FILL", value))
    order.extend(fill[: maximum - len(order)])
    require(len(order) == maximum and len(set(order)) == maximum, "exact order closure")
    return order


def metrics(graph: Any, selected: set[str], seed: int, budget: int) -> dict[str, int]:
    closed = [edge for edge in graph.edges if edge.u in selected and edge.v in selected]
    return {
        "seed": seed,
        "budget": budget,
        "selected_endpoints": len(selected),
        "closed_edges": len(closed),
        "parents": len({edge.parent for edge in closed}),
        "tasks": len({edge.task for edge in closed}),
        "physical_runs": len({edge.run for edge in closed}),
    }


def rebuild_baseline(
    graph: Any, checkpoints: list[int]
) -> tuple[dict[str, dict[str, int]], dict[str, int], int]:
    rows: list[dict[str, int]] = []
    old_underfilled = 0
    for seed in range(256):
        order = exact_order(graph, seed, checkpoints[-1])
        rows.extend(metrics(graph, set(order[:budget]), seed, budget) for budget in checkpoints)
        old = source.engine.snapshots_from_actions(
            graph,
            seed,
            checkpoints,
            source.engine.uniform_edge_actions(graph, seed, checkpoints[-1]),
        )
        old_underfilled += sum(
            int(row["selected_endpoints"] != row["budget"]) for row in old
        )
    require(
        len(rows) == 256 * len(checkpoints)
        and all(row["selected_endpoints"] == row["budget"] for row in rows),
        "exact-B row closure",
    )
    by_budget: dict[str, dict[str, int]] = {}
    fields = ("closed_edges", "parents", "tasks", "physical_runs")
    for budget in checkpoints:
        subset = [row for row in rows if row["budget"] == budget]
        by_budget[str(budget)] = {
            field: source.engine.nearest_rank(
                [int(row[field]) for row in subset], 0.5
            )
            for field in fields
        }
    integrated: dict[str, int] = {}
    for field in ("closed_edges", "tasks", "physical_runs"):
        sums: dict[int, int] = defaultdict(int)
        for row in rows:
            sums[row["seed"]] += row[field]
        require(sorted(sums) == list(range(256)), "integrated seed closure")
        integrated[field] = source.engine.nearest_rank(list(sums.values()), 0.5)
    return by_budget, integrated, old_underfilled


def verify(args: argparse.Namespace) -> dict[str, Any]:
    result_path = args.result.resolve()
    require(digest(result_path) == EXPECTED_RESULT_SHA, "result SHA mismatch")
    result = json.loads(result_path.read_text(encoding="utf-8"))
    require(
        result["protocol"] == "yield-guarded-breadth-exact-budget-audit-v1",
        "result protocol",
    )
    require(
        result["status"] == "DEVELOPMENT_AFTER_HISTORICAL_GRAPH_READOUT",
        "result status",
    )
    require(result["scope"]["prospective_values_read"] is False, "prospective boundary")
    require(
        result["scope"]["endpoint_parent_task_run_identities_emitted"] is False,
        "identity boundary",
    )
    graphs, protocol = dev.reconstruct(
        args.worktree.resolve(), args.data_root.resolve(), args.cards_root.resolve()
    )
    verified: dict[str, Any] = {}
    all_pass = True
    for fold in (0, 1):
        name = f"fold{fold}"
        graph = graphs[fold]
        checkpoints = source.budgets(graph, protocol)
        baseline, integrated_baseline, old_underfilled = rebuild_baseline(
            graph, checkpoints
        )
        observed = result["folds"][name]
        require(observed["checkpoints"] == checkpoints, f"{name} checkpoints")
        require(observed["baseline_by_budget"] == baseline, f"{name} baseline")
        require(
            observed["baseline_integrated"] == integrated_baseline,
            f"{name} integrated baseline",
        )
        require(
            observed["old_baseline_underfilled_checkpoint_rows"] == old_underfilled,
            f"{name} old underfill count",
        )
        require(observed["baseline_exact_endpoint_budget"] is True, f"{name} exact flag")
        if observed["status"] != "FEASIBLE_WITNESS":
            all_pass = False
            verified[name] = {
                "status": observed["status"],
                "baseline_recomputed": True,
                "private_witness_recomputed": False,
            }
            continue
        rows = observed["metrics"]
        require([row["budget"] for row in rows] == checkpoints, f"{name} metric budgets")
        integrated = {
            field: sum(int(row[field]) for row in rows)
            for field in ("closed_edges", "tasks", "physical_runs")
        }
        require(observed["integrated"] == integrated, f"{name} witness integrated")
        terminal = rows[-1]
        pointwise = [baseline[str(value)]["closed_edges"] for value in checkpoints]
        recomputed_gates = {
            "exact_endpoint_budget_all_checkpoints": all(
                row["selected_endpoints"] == row["budget"] for row in rows
            ),
            "all_pointwise_yield_floors_met": all(
                row["closed_edges"] >= floor for row, floor in zip(rows, pointwise)
            ),
            "integrated_yield_noninferiority": integrated["closed_edges"]
            >= integrated_baseline["closed_edges"],
            "integrated_task_breadth_at_least_6_over_5": integrated["tasks"] * 5
            >= integrated_baseline["tasks"] * 6,
            "integrated_run_breadth_at_least_11_over_10": integrated["physical_runs"] * 10
            >= integrated_baseline["physical_runs"] * 11,
            "terminal_parent_breadth_at_least_9_over_10": terminal["parents"] * 10
            >= baseline[str(checkpoints[-1])]["parents"] * 9,
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
        require(observed["gates"] == recomputed_gates, f"{name} gates")
        require(
            observed["all_exact_budget_development_gates_pass"]
            == all(recomputed_gates.values()),
            f"{name} aggregate verdict",
        )
        all_pass &= all(recomputed_gates.values())
        verified[name] = {
            "status": "AGGREGATE_EXACT",
            "checkpoints": checkpoints,
            "baseline_recomputed": True,
            "old_underfill_recomputed": old_underfilled,
            "gates_recomputed": recomputed_gates,
            "private_witness_recomputed": False,
        }
    require(
        result["all_folds_feasible_and_all_exact_budget_development_gates_pass"]
        is all_pass,
        "all-fold verdict",
    )
    expected_class = (
        "HISTORICAL_RUN_SPLIT_EXACT_BUDGET_YIELD_GUARDED_BREADTH_JOINTLY_FEASIBLE_DEVELOPMENT_ONLY"
        if all_pass
        else "HISTORICAL_RUN_SPLIT_EXACT_BUDGET_YIELD_GUARDED_BREADTH_NOT_ESTABLISHED"
    )
    require(result["classification"] == expected_class, "classification")
    return {
        "protocol": "independent-yield-guarded-breadth-exact-budget-audit-verifier-v1",
        "status": "INDEPENDENT_AGGREGATE_VERIFICATION_COMPLETE",
        "classification": "DEVELOPMENT_AGGREGATE_INDEPENDENT_VERIFICATION_PASS",
        "result_sha256": EXPECTED_RESULT_SHA,
        "folds": verified,
        "all_folds_pass": all_pass,
        "boundary": {
            "producer_imported": False,
            "baseline_algorithm_reimplemented": True,
            "aggregate_gates_recomputed": True,
            "private_witness_recomputed": False,
            "prospective_values_read": False,
            "identities_emitted": False,
        },
    }


def write_exclusive(path: Path, value: dict[str, Any]) -> None:
    descriptor = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    with os.fdopen(descriptor, "w", encoding="utf-8", newline="\n") as handle:
        handle.write(json.dumps(value, sort_keys=True, separators=(",", ":")) + "\n")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--worktree", type=Path, required=True)
    parser.add_argument("--data-root", type=Path, required=True)
    parser.add_argument("--cards-root", type=Path, required=True)
    parser.add_argument("--result", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    value = verify(args)
    write_exclusive(args.output.resolve(), value)
    print(
        json.dumps(
            {
                "status": value["status"],
                "classification": value["classification"],
                "all_folds_pass": value["all_folds_pass"],
                "output_sha256": digest(args.output.resolve()),
                "boundary": value["boundary"],
            },
            sort_keys=True,
        )
    )


if __name__ == "__main__":
    main()
