#!/usr/bin/env python3
"""Build an outcome-blind pair-balance accrual envelope."""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import sys
from fractions import Fraction
from pathlib import Path
from typing import Any


PROTOCOL = "prospective_task_balance_accrual_guard_v1"


class BalanceGuardError(RuntimeError):
    pass


def digest(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def read_bound(path: Path, expected_sha256: str) -> dict[str, Any]:
    if path.is_symlink() or not path.is_file():
        raise BalanceGuardError("input is absent, non-regular, or symlinked")
    raw = path.read_bytes()
    if digest(raw) != expected_sha256:
        raise BalanceGuardError("input hash mismatch")
    try:
        value = json.loads(raw)
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise BalanceGuardError("cannot parse input") from exc
    if not isinstance(value, dict):
        raise BalanceGuardError("input is not an object")
    return value


def ceil_div(numerator: int, denominator: int) -> int:
    return -(-numerator // denominator)


def build_guard(
    structural_gate_path: Path,
    structural_gate_sha256: str,
    coverage_matrix_path: Path,
    coverage_matrix_sha256: str,
) -> dict[str, Any]:
    gate = read_bound(structural_gate_path, structural_gate_sha256)
    coverage = read_bound(coverage_matrix_path, coverage_matrix_sha256)
    if gate.get("snapshot_sha256") != coverage.get("snapshot_sha256"):
        raise BalanceGuardError("input snapshots differ")
    gate_security = gate.get("security")
    access = coverage.get("access_attestation")
    if (
        not isinstance(gate_security, dict)
        or gate_security.get("label_vault_opened") is not False
        or gate_security.get("outcome_files_opened") != []
        or not isinstance(access, dict)
        or access.get("labels_grades_outcomes_or_winner_orientation_read") is not False
        or access.get("prediction_values_aggregated") is not False
    ):
        raise BalanceGuardError("inputs are not outcome-blind")
    gate_spec = gate.get("gate")
    wl_inventory = coverage.get("inventory", {}).get("wl")
    if not isinstance(gate_spec, dict) or not isinstance(wl_inventory, dict):
        raise BalanceGuardError("input schema mismatch")
    total = wl_inventory.get("pairs")
    task_counts = wl_inventory.get("pairs_per_task")
    cap_value = gate_spec.get("maximum_dominant_pair_task_share")
    if (
        isinstance(total, bool)
        or not isinstance(total, int)
        or total <= 0
        or not isinstance(task_counts, dict)
        or not task_counts
        or isinstance(cap_value, bool)
        or not isinstance(cap_value, (int, float))
    ):
        raise BalanceGuardError("invalid pair inventory or cap")
    cap = Fraction(str(cap_value))
    if not 0 < cap < 1:
        raise BalanceGuardError("cap is outside (0,1)")
    a, b = cap.numerator, cap.denominator
    normalized_counts: dict[str, int] = {}
    for task, count in task_counts.items():
        if not isinstance(task, str) or not task:
            raise BalanceGuardError("invalid task name")
        if isinstance(count, bool) or not isinstance(count, int) or count < 0:
            raise BalanceGuardError("invalid task pair count")
        normalized_counts[task] = count
    if sum(normalized_counts.values()) != total:
        raise BalanceGuardError("pair inventory does not sum")
    dominant_task, dominant_pairs = max(
        normalized_counts.items(), key=lambda item: (item[1], item[0])
    )
    if dominant_task != wl_inventory.get("dominant_task"):
        raise BalanceGuardError("dominant task mismatch")
    if dominant_pairs != wl_inventory.get("dominant_task_pairs"):
        raise BalanceGuardError("dominant pair count mismatch")

    debt_numerator = max(0, b * dominant_pairs - a * total)
    minimum_nondominant = ceil_div(debt_numerator, a) if debt_numerator else 0
    budgets = sorted({minimum_nondominant, 1000, 2000, 3000, 4000})
    allowance_table = []
    for nondominant_pairs in budgets:
        allowance_numerator = a * nondominant_pairs - debt_numerator
        maximum_dominant = (
            allowance_numerator // (b - a) if allowance_numerator >= 0 else None
        )
        allowance_table.append(
            {
                "future_nondominant_pairs": nondominant_pairs,
                "maximum_future_dominant_pairs": maximum_dominant,
            }
        )

    headroom = []
    for task, count in sorted(normalized_counts.items()):
        numerator = a * total - b * count
        headroom.append(
            {
                "task": task,
                "current_pairs": count,
                "current_share": count / total,
                "additional_same_task_pairs_before_cap_if_no_other_pairs": (
                    numerator // (b - a) if numerator >= 0 else None
                ),
                "currently_above_cap": numerator < 0,
            }
        )

    clearance_total = total + minimum_nondominant
    clearance_per_task_cap = a * clearance_total // b
    clearance_capacities = [
        {
            "task": task,
            "current_pairs": count,
            "maximum_future_pairs_at_debt_clearance_endpoint": max(
                0, clearance_per_task_cap - count
            ),
        }
        for task, count in sorted(normalized_counts.items())
        if task != dominant_task
    ]

    all_task_constraint = (
        f"For every task t: {b}*(current_t+future_t) <= "
        f"{a}*(current_total+sum_future_all_tasks)."
    )

    return {
        "protocol": PROTOCOL,
        "status": "OUTCOME_BLIND_TASK_BALANCE_ACCRUAL_GUARD_READY",
        "snapshot_sha256": gate.get("snapshot_sha256"),
        "inputs": {
            "structural_gate_sha256": structural_gate_sha256,
            "coverage_matrix_sha256": coverage_matrix_sha256,
        },
        "current": {
            "pairs": total,
            "tasks": len(normalized_counts),
            "dominant_task": dominant_task,
            "dominant_pairs": dominant_pairs,
            "dominant_share": dominant_pairs / total,
            "maximum_share": float(cap),
            "gate_pass": debt_numerator == 0,
        },
        "exact_integer_envelope": {
            "cap_numerator": a,
            "cap_denominator": b,
            "imbalance_debt_numerator": debt_numerator,
            "minimum_future_nondominant_pairs_if_zero_future_dominant": minimum_nondominant,
            "minimum_future_nondominant_pairs_formula": (
                f"ceil(({debt_numerator}+{b - a}*future_dominant_pairs)/{a})"
            ),
            "allowance_table": allowance_table,
        },
        "all_task_simultaneous_constraint": {
            "inequality": all_task_constraint,
            "must_hold_for_every_task": True,
            "recompute_after_each_stable_snapshot": True,
            "dominant_debt_alone_is_not_sufficient": True,
        },
        "single_task_only_headroom": headroom,
        "zero_future_dominant_debt_clearance_endpoint": {
            "future_nondominant_pairs": minimum_nondominant,
            "resulting_total_pairs": clearance_total,
            "maximum_pairs_per_task": clearance_per_task_cap,
            "nondominant_task_allocation_capacities": clearance_capacities,
        },
        "operational_guard": {
            "immediate_action": (
                f"Temporarily route acquisition away from {dominant_task} until at least "
                f"{minimum_nondominant} observed non-{dominant_task} sibling pairs accrue, "
                "while enforcing the all-task simultaneous constraint."
            ),
            "after_debt_is_cleared": (
                f"Each additional {dominant_task} pair requires at least "
                f"({b - a}/{a}) additional non-dominant pairs, with integer rounding "
                "applied to the cumulative envelope."
            ),
            "allocation_unit": "observed_canonical_sibling_pairs_not_raw_runs",
            "chronological_first_960_membership_rule_unchanged": True,
            "recompute_from_observed_pairs_not_expected_yield": True,
            "not_a_stopping_rule": True,
        },
        "access_attestation": {
            "labels_grades_outcomes_or_predictions_read": False,
            "accuracy_effect_or_search_utility_computed": False,
            "gpu_or_api_calls": 0,
            "randomness_used": False,
        },
    }


def write_new(path: Path, value: dict[str, Any]) -> None:
    if path.exists():
        raise BalanceGuardError("output exists")
    if not path.parent.is_dir() or path.parent.is_symlink():
        raise BalanceGuardError("output parent is absent or unsafe")
    temporary = path.with_name(path.name + f".tmp-{os.getpid()}")
    temporary.write_text(
        json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True, allow_nan=False)
        + "\n",
        encoding="utf-8",
        newline="\n",
    )
    temporary.replace(path)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--structural-gate", required=True, type=Path)
    parser.add_argument("--expect-structural-gate-sha256", required=True)
    parser.add_argument("--coverage-matrix", required=True, type=Path)
    parser.add_argument("--expect-coverage-matrix-sha256", required=True)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    try:
        value = build_guard(
            args.structural_gate,
            args.expect_structural_gate_sha256,
            args.coverage_matrix,
            args.expect_coverage_matrix_sha256,
        )
        write_new(args.output.resolve(), value)
        print(json.dumps(value["current"], sort_keys=True, separators=(",", ":")))
        return 0
    except (OSError, BalanceGuardError, ValueError, ZeroDivisionError) as exc:
        print(f"TASK_BALANCE_ACCRUAL_GUARD_ERROR: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
