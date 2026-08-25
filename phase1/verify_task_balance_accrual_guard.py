#!/usr/bin/env python3
"""Independently verify the pair-balance accrual envelope."""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import sys
from fractions import Fraction
from pathlib import Path
from typing import Any


class BalanceGuardVerificationError(RuntimeError):
    pass


def digest(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def read_bound(path: Path, expected_sha256: str) -> tuple[bytes, dict[str, Any]]:
    if path.is_symlink() or not path.is_file():
        raise BalanceGuardVerificationError("input is absent, non-regular, or symlinked")
    raw = path.read_bytes()
    if digest(raw) != expected_sha256:
        raise BalanceGuardVerificationError("input hash mismatch")
    try:
        value = json.loads(raw)
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise BalanceGuardVerificationError("cannot parse input") from exc
    if not isinstance(value, dict):
        raise BalanceGuardVerificationError("input is not an object")
    return raw, value


def verify(
    structural_gate_path: Path,
    structural_gate_sha256: str,
    coverage_matrix_path: Path,
    coverage_matrix_sha256: str,
    guard_path: Path,
    guard_sha256: str,
) -> dict[str, Any]:
    _, gate = read_bound(structural_gate_path, structural_gate_sha256)
    _, coverage = read_bound(coverage_matrix_path, coverage_matrix_sha256)
    guard_raw, guard = read_bound(guard_path, guard_sha256)
    if guard.get("protocol") != "prospective_task_balance_accrual_guard_v1":
        raise BalanceGuardVerificationError("guard protocol mismatch")
    if gate.get("snapshot_sha256") != coverage.get("snapshot_sha256"):
        raise BalanceGuardVerificationError("source snapshot mismatch")
    if guard.get("snapshot_sha256") != gate.get("snapshot_sha256"):
        raise BalanceGuardVerificationError("guard snapshot mismatch")
    if guard.get("inputs") != {
        "structural_gate_sha256": structural_gate_sha256,
        "coverage_matrix_sha256": coverage_matrix_sha256,
    }:
        raise BalanceGuardVerificationError("guard input binding mismatch")

    gate_security = gate.get("security")
    source_access = coverage.get("access_attestation")
    if (
        not isinstance(gate_security, dict)
        or gate_security.get("label_vault_opened") is not False
        or gate_security.get("outcome_files_opened") != []
        or not isinstance(source_access, dict)
        or source_access.get(
            "labels_grades_outcomes_or_winner_orientation_read"
        )
        is not False
        or source_access.get("prediction_values_aggregated") is not False
    ):
        raise BalanceGuardVerificationError("source inputs are not outcome-blind")

    inventory = coverage.get("inventory", {}).get("wl")
    gate_spec = gate.get("gate")
    if not isinstance(inventory, dict) or not isinstance(gate_spec, dict):
        raise BalanceGuardVerificationError("source schema mismatch")
    counts = inventory.get("pairs_per_task")
    total = inventory.get("pairs")
    if (
        not isinstance(counts, dict)
        or not counts
        or isinstance(total, bool)
        or not isinstance(total, int)
        or total <= 0
    ):
        raise BalanceGuardVerificationError("pair inventory missing")
    normalized: dict[str, int] = {}
    for task, value in counts.items():
        if not isinstance(task, str) or not task:
            raise BalanceGuardVerificationError("invalid task name")
        if isinstance(value, bool) or not isinstance(value, int) or value < 0:
            raise BalanceGuardVerificationError("invalid task pair count")
        normalized[task] = value
    if sum(normalized.values()) != total:
        raise BalanceGuardVerificationError("pair inventory does not sum")
    dominant_task, dominant_pairs = max(
        normalized.items(), key=lambda item: (item[1], item[0])
    )
    cap_value = gate_spec.get("maximum_dominant_pair_task_share")
    if isinstance(cap_value, bool) or not isinstance(cap_value, (int, float)):
        raise BalanceGuardVerificationError("invalid dominant-task cap")
    cap = Fraction(str(cap_value))
    if not 0 < cap < 1:
        raise BalanceGuardVerificationError("dominant-task cap is outside (0,1)")
    a, b = cap.numerator, cap.denominator
    debt = max(0, b * dominant_pairs - a * total)
    minimum_nondominant = -(-debt // a) if debt else 0
    expected_current = {
        "pairs": total,
        "tasks": len(normalized),
        "dominant_task": dominant_task,
        "dominant_pairs": dominant_pairs,
        "dominant_share": dominant_pairs / total,
        "maximum_share": float(cap),
        "gate_pass": debt == 0,
    }
    if guard.get("current") != expected_current:
        raise BalanceGuardVerificationError("current balance state mismatch")

    budgets = sorted({minimum_nondominant, 1000, 2000, 3000, 4000})
    allowance_table = []
    for nondominant in budgets:
        numerator = a * nondominant - debt
        allowance_table.append(
            {
                "future_nondominant_pairs": nondominant,
                "maximum_future_dominant_pairs": (
                    numerator // (b - a) if numerator >= 0 else None
                ),
            }
        )
    expected_envelope = {
        "cap_numerator": a,
        "cap_denominator": b,
        "imbalance_debt_numerator": debt,
        "minimum_future_nondominant_pairs_if_zero_future_dominant": (
            minimum_nondominant
        ),
        "minimum_future_nondominant_pairs_formula": (
            f"ceil(({debt}+{b - a}*future_dominant_pairs)/{a})"
        ),
        "allowance_table": allowance_table,
    }
    if guard.get("exact_integer_envelope") != expected_envelope:
        raise BalanceGuardVerificationError("integer envelope mismatch")

    expected_all_task_constraint = {
        "inequality": (
            f"For every task t: {b}*(current_t+future_t) <= "
            f"{a}*(current_total+sum_future_all_tasks)."
        ),
        "must_hold_for_every_task": True,
        "recompute_after_each_stable_snapshot": True,
        "dominant_debt_alone_is_not_sufficient": True,
    }
    if guard.get("all_task_simultaneous_constraint") != expected_all_task_constraint:
        raise BalanceGuardVerificationError("all-task constraint mismatch")

    expected_headroom = []
    for task, count in sorted(normalized.items()):
        numerator = a * total - b * count
        expected_headroom.append(
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
    if guard.get("single_task_only_headroom") != expected_headroom:
        raise BalanceGuardVerificationError("single-task headroom mismatch")

    clearance_total = total + minimum_nondominant
    clearance_per_task_cap = a * clearance_total // b
    expected_clearance = {
        "future_nondominant_pairs": minimum_nondominant,
        "resulting_total_pairs": clearance_total,
        "maximum_pairs_per_task": clearance_per_task_cap,
        "nondominant_task_allocation_capacities": [
            {
                "task": task,
                "current_pairs": count,
                "maximum_future_pairs_at_debt_clearance_endpoint": max(
                    0, clearance_per_task_cap - count
                ),
            }
            for task, count in sorted(normalized.items())
            if task != dominant_task
        ],
    }
    if guard.get("zero_future_dominant_debt_clearance_endpoint") != expected_clearance:
        raise BalanceGuardVerificationError("debt-clearance endpoint mismatch")
    expected_operational_guard = {
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
    }
    if guard.get("operational_guard") != expected_operational_guard:
        raise BalanceGuardVerificationError("operational guard mismatch")
    if guard.get("access_attestation") != {
        "labels_grades_outcomes_or_predictions_read": False,
        "accuracy_effect_or_search_utility_computed": False,
        "gpu_or_api_calls": 0,
        "randomness_used": False,
    }:
        raise BalanceGuardVerificationError("access attestation mismatch")
    return {
        "protocol": "independent_prospective_task_balance_accrual_guard_v1",
        "status": "INDEPENDENT_TASK_BALANCE_ACCRUAL_GUARD_PASS",
        "guard_sha256": digest(guard_raw),
        "recomputed_current": expected_current,
        "recomputed_minimum_nondominant_pairs": minimum_nondominant,
        "recomputed_allowance_table": allowance_table,
        "outcomes_or_predictions_read": False,
        "randomness_used": False,
    }


def write_new(path: Path, value: dict[str, Any]) -> None:
    if path.exists():
        raise BalanceGuardVerificationError("output exists")
    if not path.parent.is_dir() or path.parent.is_symlink():
        raise BalanceGuardVerificationError("output parent is absent or unsafe")
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
    parser.add_argument("--guard", required=True, type=Path)
    parser.add_argument("--expect-guard-sha256", required=True)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    try:
        value = verify(
            args.structural_gate,
            args.expect_structural_gate_sha256,
            args.coverage_matrix,
            args.expect_coverage_matrix_sha256,
            args.guard,
            args.expect_guard_sha256,
        )
        write_new(args.output.resolve(), value)
        print(json.dumps(value["recomputed_current"], sort_keys=True, separators=(",", ":")))
        return 0
    except (OSError, BalanceGuardVerificationError, ValueError, ZeroDivisionError) as exc:
        print(f"TASK_BALANCE_ACCRUAL_GUARD_VERIFY_ERROR: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
