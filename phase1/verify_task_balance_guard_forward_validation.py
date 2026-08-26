#!/usr/bin/env python3
"""Independently verify a task-balance guard forward-validation receipt."""
from __future__ import annotations

import argparse
import hashlib
import json
import math
import os
import sys
from fractions import Fraction
from pathlib import Path
from typing import Any


class ForwardVerificationError(RuntimeError):
    pass


def sha256(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def load(path: Path, expected: str) -> tuple[bytes, dict[str, Any]]:
    if path.is_symlink() or not path.is_file():
        raise ForwardVerificationError("input is absent, non-regular, or symlinked")
    raw = path.read_bytes()
    if sha256(raw) != expected:
        raise ForwardVerificationError("input hash mismatch")
    try:
        value = json.loads(raw)
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ForwardVerificationError("cannot parse input") from exc
    if not isinstance(value, dict):
        raise ForwardVerificationError("input is not an object")
    return raw, value


def integer(value: Any, label: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value < 0:
        raise ForwardVerificationError(f"invalid {label}")
    return value


def counts(value: Any, label: str) -> dict[str, int]:
    if not isinstance(value, dict) or not value:
        raise ForwardVerificationError(f"invalid {label}")
    result: dict[str, int] = {}
    for task, count in value.items():
        if not isinstance(task, str) or not task:
            raise ForwardVerificationError(f"invalid {label} task")
        result[task] = integer(count, label)
    return result


def hhi(value: dict[str, int]) -> float:
    total = sum(value.values())
    return math.fsum((count / total) ** 2 for count in value.values())


def tv(left: dict[str, int], right: dict[str, int]) -> float:
    left_total = sum(left.values())
    right_total = sum(right.values())
    return 0.5 * math.fsum(
        abs(left.get(task, 0) / left_total - right.get(task, 0) / right_total)
        for task in set(left) | set(right)
    )


def verify(
    guard_path: Path,
    guard_sha: str,
    observed_path: Path,
    observed_sha: str,
    result_path: Path,
    result_sha: str,
) -> dict[str, Any]:
    guard_raw, guard = load(guard_path, guard_sha)
    observed_raw, observed = load(observed_path, observed_sha)
    result_raw, result = load(result_path, result_sha)
    if guard.get("protocol") != "prospective_task_balance_accrual_guard_v1":
        raise ForwardVerificationError("guard protocol mismatch")
    if observed.get("protocol") != "task_balance_guard_forward_structural_input_v1":
        raise ForwardVerificationError("observed protocol mismatch")
    if result.get("protocol") != "task_balance_guard_forward_validation_v1":
        raise ForwardVerificationError("result protocol mismatch")
    if result.get("status") != "FORWARD_ACCOUNTING_EXACT":
        raise ForwardVerificationError("result status mismatch")

    if any(observed.get("access_attestation", {}).values()):
        raise ForwardVerificationError("observed access attestation is not zero")
    if any(result.get("access_attestation", {}).values()):
        raise ForwardVerificationError("result access attestation is not zero")
    if observed.get("source_sha256", {}).get("baseline_guard") != sha256(guard_raw):
        raise ForwardVerificationError("guard binding mismatch")
    if result.get("inputs") != {
        "baseline_guard_sha256": sha256(guard_raw),
        "observed_structural_input_sha256": sha256(observed_raw),
        "baseline_snapshot_sha256": guard.get("snapshot_sha256"),
        "current_snapshot_sha256": observed.get("current_snapshot_sha256"),
    }:
        raise ForwardVerificationError("result input binding mismatch")

    chronology = observed.get("chronology", {})
    expected_chronology = {
        "old_run_set_preserved": chronology.get(
            "baseline_run_id_set_subset_of_current"
        )
        is True,
        "old_run_order_preserved_as_subsequence": chronology.get(
            "baseline_run_id_sequence_is_subsequence"
        )
        is True,
        "old_rows_unchanged_by_run_id": chronology.get(
            "common_rows_equal_when_joined_by_run_id"
        )
        is True,
        "byte_prefix_required": False,
        "observed_byte_prefix": chronology.get("baseline_is_byte_prefix_of_current"),
        "new_runs": integer(chronology.get("new_runs"), "new runs"),
        "new_runs_before_old_baseline_tail": integer(
            chronology.get("new_runs_before_old_baseline_tail"), "inserted runs"
        ),
    }
    if not all(
        expected_chronology[key]
        for key in (
            "old_run_set_preserved",
            "old_run_order_preserved_as_subsequence",
            "old_rows_unchanged_by_run_id",
        )
    ):
        raise ForwardVerificationError("chronology invariant failed")
    if result.get("chronology_audit") != expected_chronology:
        raise ForwardVerificationError("chronology receipt mismatch")

    baseline_pairs = {
        row["task"]: integer(row["current_pairs"], "baseline pairs")
        for row in guard.get("single_task_only_headroom", [])
    }
    increments = counts(
        observed.get("pair_inventory", {}).get("pair_increments_by_task"),
        "pair increments",
    )
    tasks = set(baseline_pairs) | set(increments)
    current_pairs = {
        task: baseline_pairs.get(task, 0) + increments.get(task, 0) for task in tasks
    }
    baseline_total = sum(baseline_pairs.values())
    current_total = sum(current_pairs.values())
    dominant, dominant_count = max(
        baseline_pairs.items(), key=lambda item: (item[1], item[0])
    )
    current_dominant, _ = max(current_pairs.items(), key=lambda item: (item[1], item[0]))
    if current_dominant != dominant:
        raise ForwardVerificationError("dominant task changed")
    cap = Fraction(str(guard["current"]["maximum_share"]))
    a, b = cap.numerator, cap.denominator
    baseline_debt = max(0, b * dominant_count - a * baseline_total)
    future_dominant = increments[dominant]
    future_nondominant = sum(increments.values()) - future_dominant
    predicted = max(
        0, baseline_debt + (b - a) * future_dominant - a * future_nondominant
    )
    task_debts = {
        task: max(0, b * count - a * current_total)
        for task, count in current_pairs.items()
    }
    observed_debt = task_debts[dominant]
    violations = sorted(task for task, debt in task_debts.items() if debt)
    if predicted != observed_debt:
        raise ForwardVerificationError("debt accounting mismatch")
    debt_delta = observed_debt - baseline_debt
    debt_direction = (
        "CLEARED"
        if observed_debt == 0 and debt_delta < 0
        else "IMPROVED_BUT_UNCLEARED"
        if debt_delta < 0
        else "WORSENED"
        if debt_delta > 0
        else "UNCHANGED"
    )
    minimum_nondominant = integer(
        guard["exact_integer_envelope"][
            "minimum_future_nondominant_pairs_if_zero_future_dominant"
        ],
        "minimum nondominant",
    )
    adherence = (
        "ADHERED_NO_DOMINANT_INCREMENT"
        if future_dominant == 0
        else "DEFINITELY_NOT_ADHERED_BEFORE_DEBT_CLEARANCE"
        if future_nondominant < minimum_nondominant
        else "ORDER_UNOBSERVED_CANNOT_DETERMINE"
    )
    expected_forward = {
        "dominant_task": dominant,
        "future_dominant_pairs": future_dominant,
        "future_nondominant_pairs": future_nondominant,
        "baseline_debt": baseline_debt,
        "predicted_current_debt": predicted,
        "observed_current_debt": observed_debt,
        "debt_delta": debt_delta,
        "debt_direction": debt_direction,
        "debt_accounting_identity_exact": True,
        "current_cap_pass": not violations,
        "current_cap_violating_tasks": violations,
        "immediate_action_adherence": adherence,
        "strict_guard_adherence_claimed": False,
    }
    if result.get("frozen_guard_forward_result") != expected_forward:
        raise ForwardVerificationError("frozen guard result mismatch")

    run_inventory = observed.get("run_inventory", {})
    baseline_runs = counts(run_inventory.get("baseline_runs_by_task"), "baseline runs")
    current_runs = counts(run_inventory.get("current_runs_by_task"), "current runs")
    secondary = {
        "baseline_run_hhi": hhi(baseline_runs),
        "current_run_hhi": hhi(current_runs),
        "baseline_pair_hhi": hhi(baseline_pairs),
        "current_pair_hhi": hhi(current_pairs),
        "baseline_run_to_pair_tv": tv(baseline_runs, baseline_pairs),
        "current_run_to_pair_tv": tv(current_runs, current_pairs),
    }
    secondary.update(
        {
            "run_hhi_delta": secondary["current_run_hhi"]
            - secondary["baseline_run_hhi"],
            "pair_hhi_delta": secondary["current_pair_hhi"]
            - secondary["baseline_pair_hhi"],
            "run_to_pair_tv_delta": secondary["current_run_to_pair_tv"]
            - secondary["baseline_run_to_pair_tv"],
            "preregistered_for_this_forward_check": False,
        }
    )
    result_secondary = result.get("descriptive_secondary")
    if not isinstance(result_secondary, dict) or set(result_secondary) != set(secondary):
        raise ForwardVerificationError("secondary schema mismatch")
    for key, expected in secondary.items():
        actual = result_secondary[key]
        if isinstance(expected, bool):
            if actual is not expected:
                raise ForwardVerificationError("secondary boolean mismatch")
        elif not math.isclose(actual, expected, rel_tol=0.0, abs_tol=1e-15):
            raise ForwardVerificationError(f"secondary metric mismatch: {key}")

    expected_boundary = {
        "arithmetic_identity_is_statistical_prediction": False,
        "natural_accrual_causal_effect_claimed": False,
        "producer_compliance_claimed": False,
        "predictor_accuracy_effect_or_search_utility_computed": False,
        "descriptive_hhi_or_tv_can_rescue_failed_cap": False,
    }
    if result.get("claim_boundary") != expected_boundary:
        raise ForwardVerificationError("claim boundary mismatch")
    return {
        "protocol": "independent_task_balance_guard_forward_validation_v1",
        "status": "INDEPENDENT_TASK_BALANCE_FORWARD_VALIDATION_PASS",
        "guard_sha256": sha256(guard_raw),
        "observed_structural_input_sha256": sha256(observed_raw),
        "forward_result_sha256": sha256(result_raw),
        "checks": {
            "access_firewall_exact": True,
            "chronology_membership_exact": True,
            "debt_accounting_identity_exact": True,
            "frozen_cap_failure_preserved": not expected_forward["current_cap_pass"],
            "nonadherence_preserved": adherence
            == "DEFINITELY_NOT_ADHERED_BEFORE_DEBT_CLEARANCE",
            "descriptive_metrics_recomputed": True,
            "causal_and_effect_claims_forbidden": True,
        },
        "recomputed": {
            "future_dominant_pairs": future_dominant,
            "future_nondominant_pairs": future_nondominant,
            "baseline_debt": baseline_debt,
            "current_debt": observed_debt,
            "debt_delta": debt_delta,
        },
        "access_attestation": {
            "outcomes_or_prediction_values_read": False,
            "raw_archive_payload_read": False,
            "gpu_or_api_calls": 0,
            "randomness_used": False,
        },
    }


def write_new(path: Path, value: dict[str, Any]) -> None:
    if path.exists():
        raise ForwardVerificationError("output exists")
    if not path.parent.is_dir() or path.parent.is_symlink():
        raise ForwardVerificationError("output parent is absent or unsafe")
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
    parser.add_argument("--guard", required=True, type=Path)
    parser.add_argument("--expect-guard-sha256", required=True)
    parser.add_argument("--observed", required=True, type=Path)
    parser.add_argument("--expect-observed-sha256", required=True)
    parser.add_argument("--result", required=True, type=Path)
    parser.add_argument("--expect-result-sha256", required=True)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    try:
        receipt = verify(
            args.guard,
            args.expect_guard_sha256,
            args.observed,
            args.expect_observed_sha256,
            args.result,
            args.expect_result_sha256,
        )
        write_new(args.output.resolve(), receipt)
        print(json.dumps(receipt["recomputed"], sort_keys=True, separators=(",", ":")))
        return 0
    except (OSError, ForwardVerificationError, ValueError, ZeroDivisionError) as exc:
        print(f"TASK_BALANCE_FORWARD_VERIFY_ERROR: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
