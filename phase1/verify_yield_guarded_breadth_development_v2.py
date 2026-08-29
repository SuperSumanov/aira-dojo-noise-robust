#!/usr/bin/env python3
"""Non-importing aggregate verifier for yield-guarded breadth development v2."""

from __future__ import annotations

import argparse
from fractions import Fraction
import hashlib
import json
import math
import os
from pathlib import Path
from typing import Any


EXPECTED_PRIOR_SHA = "f1d8054ccc3e0d50f77a3ff4be29480f99ab0dbc51a6e1e510853da63c06e042"
EXPECTED_RESULT_SHA = "e43831946643d60654bb10b834278fd480c97292fcf91ea6dfa95962c77c191d"


def raw_sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def require(condition: bool, message: str) -> None:
    if not condition:
        raise RuntimeError(message)


def check_ratio(value: dict[str, Any]) -> Fraction:
    numerator = int(value["numerator"])
    denominator = int(value["denominator"])
    require(denominator > 0, "ratio denominator")
    exact = Fraction(numerator, denominator)
    require(value["decimal_17g"] == format(float(exact), ".17g"), "ratio decimal")
    return exact


def verify_fold(name: str, observed: dict[str, Any], prior: dict[str, Any]) -> dict[str, Any]:
    published = prior["gates_by_fold"][name]
    budgets = [int(value) for value in published["budgets"]]
    require(observed["status"] == "FEASIBLE_WITNESS", f"{name} witness")
    require(observed["solver_status"] == 0, f"{name} solver status")
    require(observed["solver_constant_objective_optimal"] is True, f"{name} constant optimum")
    require(observed["solver_mip_gap"] == 0.0, f"{name} gap")
    require(observed["solver_threads_requested"] == 1, f"{name} threads")
    require(observed["solver_random_seed"] == 0, f"{name} seed")
    require(observed["identities_emitted"] is False, f"{name} identities")
    require(len(observed["private_selection_fingerprint_sha256"]) == 64, f"{name} fingerprint")

    baseline_by_budget = observed["baseline_by_budget"]
    for budget in budgets:
        expected = published["by_budget"][str(budget)]
        actual = baseline_by_budget[str(budget)]
        for field in ("closed_edges", "parents", "tasks", "physical_runs"):
            require(actual[field] == expected[field]["uniform_median"], f"{name} baseline {budget} {field}")

    baseline_integrated = observed["baseline_integrated"]
    for field in ("closed_edges", "tasks", "physical_runs"):
        require(
            baseline_integrated[field] == published["integrated"][field]["uniform_median"],
            f"{name} baseline integral {field}",
        )
    require(observed["integrated_task_floor"] == math.ceil(6 * baseline_integrated["tasks"] / 5), f"{name} task floor")
    require(observed["integrated_run_floor"] == math.ceil(11 * baseline_integrated["physical_runs"] / 10), f"{name} run floor")

    rows = observed["metrics"]
    require([row["budget"] for row in rows] == budgets, f"{name} budgets")
    for row, budget in zip(rows, budgets):
        require(row["selected_endpoints"] == budget, f"{name} selected endpoints")
        require(row["closed_edges"] >= baseline_by_budget[str(budget)]["closed_edges"], f"{name} yield floor")
        task_share = check_ratio(row["maximum_single_task_share"])
        run_share = check_ratio(row["maximum_single_run_share"])
        require(Fraction(0, 1) <= task_share <= 1, f"{name} task share range")
        require(Fraction(0, 1) <= run_share <= 1, f"{name} run share range")

    integrated = {
        field: sum(int(row[field]) for row in rows)
        for field in ("closed_edges", "tasks", "physical_runs")
    }
    require(integrated == observed["integrated"], f"{name} integral exact")
    terminal = rows[-1]
    gates = {
        "all_pointwise_yield_floors_met": all(
            row["closed_edges"] >= baseline_by_budget[str(row["budget"])]["closed_edges"] for row in rows
        ),
        "integrated_yield_noninferiority": integrated["closed_edges"] >= baseline_integrated["closed_edges"],
        "integrated_task_breadth_at_least_6_over_5": integrated["tasks"] * 5 >= baseline_integrated["tasks"] * 6,
        "integrated_run_breadth_at_least_11_over_10": integrated["physical_runs"] * 10 >= baseline_integrated["physical_runs"] * 11,
        "terminal_parent_breadth_at_least_9_over_10": terminal["parents"] * 10 >= baseline_by_budget[str(budgets[-1])]["parents"] * 9,
        "terminal_task_anti_dominance_at_most_1_over_3": check_ratio(terminal["maximum_single_task_share"]) <= Fraction(1, 3),
        "terminal_run_anti_dominance_at_most_1_over_10": check_ratio(terminal["maximum_single_run_share"]) <= Fraction(1, 10),
    }
    require(gates == observed["gates"], f"{name} gates exact")
    require(all(gates.values()), f"{name} all gates")
    require(observed["all_development_gates_pass"] is True, f"{name} aggregate pass")
    return {
        "status": "AGGREGATE_EXACT",
        "budgets": budgets,
        "integrated": integrated,
        "baseline_integrated": baseline_integrated,
        "gates_recomputed": gates,
        "private_witness_recomputed": False,
    }


def write_exclusive(path: Path, value: dict[str, Any]) -> None:
    descriptor = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    with os.fdopen(descriptor, "w", encoding="utf-8", newline="\n") as handle:
        handle.write(json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False) + "\n")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--result", required=True)
    parser.add_argument("--ab-result", required=True)
    parser.add_argument("--prior", required=True)
    parser.add_argument("--output", required=True)
    args = parser.parse_args()
    result_path = Path(args.result).resolve()
    ab_path = Path(args.ab_result).resolve()
    prior_path = Path(args.prior).resolve()
    require(raw_sha(result_path) == EXPECTED_RESULT_SHA, "result sha")
    require(raw_sha(ab_path) == EXPECTED_RESULT_SHA, "AB result sha")
    require(result_path.read_bytes() == ab_path.read_bytes(), "AB bytes")
    require(raw_sha(prior_path) == EXPECTED_PRIOR_SHA, "prior sha")
    result = json.loads(result_path.read_text(encoding="utf-8"))
    prior = json.loads(prior_path.read_text(encoding="utf-8"))
    require(result["protocol"] == "yield-guarded-breadth-milp-development-v2", "protocol")
    require(result["status"] == "DEVELOPMENT_AFTER_BOTH_RUN_SPLIT_FOLDS_READOUT", "status")
    require(result["all_folds_feasible_and_all_development_gates_pass"] is True, "headline")
    require(result["scope"] == {
        "post_readout_development_only": True,
        "external_confirmation": False,
        "labels_outcomes_predictions_code_runtime_used": False,
        "prospective_values_used": False,
        "identities_emitted": False,
        "gpu_api_model_fit_base_update": "0/0/0/0",
    }, "scope")
    folds = {name: verify_fold(name, result["folds"][name], prior) for name in ("fold0", "fold1")}
    verification = {
        "classification": "DEVELOPMENT_AGGREGATE_INDEPENDENT_VERIFICATION_PASS",
        "result_sha256": EXPECTED_RESULT_SHA,
        "ab_byte_exact": True,
        "prior_sha256": EXPECTED_PRIOR_SHA,
        "folds": folds,
        "boundary": {
            "non_importing": True,
            "aggregate_gates_recomputed": True,
            "private_witness_recomputed": False,
            "external_confirmation": False,
        },
    }
    write_exclusive(Path(args.output).resolve(), verification)
    print(json.dumps({"classification": verification["classification"], "output_sha256": raw_sha(Path(args.output).resolve())}, sort_keys=True))


if __name__ == "__main__":
    main()
