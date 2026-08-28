#!/usr/bin/env python3
"""Forward-check the v2 balance guard using structural-only snapshots."""
from __future__ import annotations

import argparse
import json
import math
import os
import sys
from fractions import Fraction
from pathlib import Path
from typing import Any

from phase1.build_task_balance_accrual_guard_v2 import (
    BalanceGuardV2Error,
    read_object,
    sha256,
    validate_accumulator,
)


PROTOCOL = "task_balance_guard_forward_validation_v2"


class ForwardV2Error(RuntimeError):
    pass


def ledger_rows(path: Path, expected_sha: str) -> tuple[bytes, list[dict[str, Any]]]:
    if path.is_symlink() or not path.is_file():
        raise ForwardV2Error("invalid ledger path")
    raw = path.read_bytes()
    if sha256(raw) != expected_sha:
        raise ForwardV2Error("ledger hash mismatch")
    try:
        rows = [json.loads(line) for line in raw.decode("utf-8").splitlines()]
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ForwardV2Error("cannot parse ledger") from exc
    if not rows or any(not isinstance(row, dict) for row in rows):
        raise ForwardV2Error("invalid ledger rows")
    return raw, rows


def hhi(counts: dict[str, int]) -> float:
    total = sum(counts.values())
    if total <= 0:
        raise ForwardV2Error("empty HHI distribution")
    return math.fsum((count / total) ** 2 for count in counts.values())


def tv(left: dict[str, int], right: dict[str, int]) -> float:
    left_total = sum(left.values())
    right_total = sum(right.values())
    if left_total <= 0 or right_total <= 0:
        raise ForwardV2Error("empty TV distribution")
    return 0.5 * math.fsum(
        abs(left.get(task, 0) / left_total - right.get(task, 0) / right_total)
        for task in set(left) | set(right)
    )


def is_subsequence(left: list[str], right: list[str]) -> bool:
    cursor = iter(right)
    return all(any(candidate == value for candidate in cursor) for value in left)


def build_forward(
    guard_path: Path,
    guard_sha: str,
    guard_verification_path: Path,
    guard_verification_sha: str,
    baseline_summary_path: Path,
    baseline_summary_sha: str,
    baseline_ledger_path: Path,
    baseline_ledger_sha: str,
    baseline_snapshot: str,
    current_summary_path: Path,
    current_summary_sha: str,
    current_ledger_path: Path,
    current_ledger_sha: str,
    current_snapshot: str,
    current_common_support_path: Path,
    current_common_support_sha: str,
    *,
    allow_task_expansion: bool = False,
) -> dict[str, Any]:
    _, guard = read_object(guard_path, guard_sha)
    _, guard_verification = read_object(guard_verification_path, guard_verification_sha)
    _, common_support = read_object(current_common_support_path, current_common_support_sha)
    if (
        guard.get("protocol") != "prospective_task_balance_accrual_guard_v2"
        or guard.get("status") != "STRUCTURAL_ONLY_TASK_BALANCE_ACCRUAL_GUARD_READY"
        or guard.get("snapshot_sha256") != baseline_snapshot
    ):
        raise ForwardV2Error("baseline guard identity mismatch")
    if (
        guard_verification.get("protocol")
        != "independent_prospective_task_balance_accrual_guard_v2"
        or guard_verification.get("status")
        != "INDEPENDENT_STRUCTURAL_ONLY_TASK_BALANCE_GUARD_PASS"
        or guard_verification.get("guard_sha256") != guard_sha
        or guard_verification.get("snapshot_sha256") != baseline_snapshot
        or guard_verification.get("access_attestation")
        != {
            "outcomes_or_prediction_values_read": False,
            "raw_archive_payload_read": False,
            "gpu_or_api_calls": 0,
            "randomness_used": False,
        }
    ):
        raise ForwardV2Error("baseline guard independent verification mismatch")
    if guard.get("inputs", {}).get("accumulator_summary_sha256") != baseline_summary_sha:
        raise ForwardV2Error("guard-summary binding mismatch")
    if guard.get("inputs", {}).get("provisional_first960_runs_sha256") != baseline_ledger_sha:
        raise ForwardV2Error("guard-ledger binding mismatch")
    guard_access = guard.get("access_attestation", {})
    if (
        guard_access.get("labels_grades_outcomes_or_winner_orientation_read") is not False
        or guard_access.get("prediction_pair_files_opened") != []
        or guard_access.get("prediction_values_read_or_aggregated") is not False
        or guard_access.get("raw_archive_payload_read") is not False
        or guard_access.get("accuracy_effect_or_search_utility_computed") is not False
    ):
        raise ForwardV2Error("baseline guard access boundary mismatch")

    baseline = validate_accumulator(
        baseline_summary_path,
        baseline_summary_sha,
        baseline_ledger_path,
        baseline_ledger_sha,
        baseline_snapshot,
    )
    current = validate_accumulator(
        current_summary_path,
        current_summary_sha,
        current_ledger_path,
        current_ledger_sha,
        current_snapshot,
    )
    expected_common_support = {
        "protocol": "prediction-receipt-common-support-v1",
        "status": "INDEPENDENT_PREDICTION_RECEIPT_COMMON_SUPPORT_VERIFIED",
        "snapshot_sha256": current_snapshot,
        "pairs": current["pairs"],
        "same_canonical_pair_population_certified": True,
        "candidate_exact": True,
        "prediction_pair_files_opened": False,
        "prediction_values_accessed": False,
        "producer_imported": False,
        "prospective_outcomes_read": False,
        "effect_metrics_computed": [],
    }
    for key, expected in expected_common_support.items():
        if common_support.get(key) != expected:
            raise ForwardV2Error(f"current common-support receipt mismatch: {key}")

    baseline_raw, baseline_rows = ledger_rows(baseline_ledger_path, baseline_ledger_sha)
    current_raw, current_rows = ledger_rows(current_ledger_path, current_ledger_sha)
    baseline_ids = [row["run_id"] for row in baseline_rows]
    current_ids = [row["run_id"] for row in current_rows]
    current_map = {row["run_id"]: row for row in current_rows}
    baseline_set = set(baseline_ids)
    current_set = set(current_ids)
    subset = baseline_set <= current_set
    subsequence = is_subsequence(baseline_ids, current_ids)
    rows_equal = subset and all(current_map[run_id] == row for run_id, row in zip(baseline_ids, baseline_rows))
    if not subset or not subsequence or not rows_equal:
        raise ForwardV2Error("first-960 chronology invariant failed")
    new_ids = current_set - baseline_set
    tail_index = current_ids.index(baseline_ids[-1])
    inserted_before_tail = sum(
        1 for index, run_id in enumerate(current_ids) if run_id in new_ids and index < tail_index
    )

    baseline_pairs = baseline["pair_counts"]
    current_pairs = current["pair_counts"]
    baseline_runs = baseline["run_counts"]
    current_runs = current["run_counts"]
    baseline_tasks = set(baseline_pairs)
    current_tasks = set(current_pairs)
    if set(baseline_runs) != baseline_tasks or set(current_runs) != current_tasks:
        raise ForwardV2Error("pair/run task universes differ")
    if allow_task_expansion:
        if not baseline_tasks <= current_tasks:
            raise ForwardV2Error("task universe is not a monotone expansion")
    elif baseline_tasks != current_tasks:
        raise ForwardV2Error("task universe changed")
    increments = {
        task: current_pairs[task] - baseline_pairs.get(task, 0)
        for task in sorted(current_pairs)
    }
    run_increments = {
        task: current_runs[task] - baseline_runs.get(task, 0)
        for task in sorted(current_runs)
    }
    if any(value < 0 for value in increments.values()) or any(
        value < 0 for value in run_increments.values()
    ):
        raise ForwardV2Error("this forward protocol does not admit negative accrual")
    if sum(increments.values()) != current["pairs"] - baseline["pairs"]:
        raise ForwardV2Error("pair increment total mismatch")
    if sum(run_increments.values()) != len(new_ids):
        raise ForwardV2Error("run increment total mismatch")

    state = guard.get("current", {})
    envelope = guard.get("exact_integer_envelope", {})
    if (
        state.get("pairs") != baseline["pairs"]
        or state.get("dominant_task") != baseline["dominant_task"]
        or state.get("dominant_pairs") != baseline["dominant_pairs"]
    ):
        raise ForwardV2Error("guard baseline state mismatch")
    cap = Fraction(str(state.get("maximum_share")))
    if not 0 < cap < 1:
        raise ForwardV2Error("guard cap outside (0,1)")
    a, b = cap.numerator, cap.denominator
    dominant = baseline["dominant_task"]
    if current["dominant_task"] != dominant:
        raise ForwardV2Error("dominant task changed")
    baseline_debt = max(0, b * baseline["dominant_pairs"] - a * baseline["pairs"])
    if envelope.get("imbalance_debt_numerator") != baseline_debt:
        raise ForwardV2Error("guard debt mismatch")
    future_dominant = increments[dominant]
    future_nondominant = sum(increments.values()) - future_dominant
    predicted_debt = max(
        0,
        baseline_debt + (b - a) * future_dominant - a * future_nondominant,
    )
    task_debts = {
        task: max(0, b * count - a * current["pairs"])
        for task, count in current_pairs.items()
    }
    observed_debt = task_debts[dominant]
    if predicted_debt != observed_debt:
        raise ForwardV2Error("debt accounting identity failed")
    violating = sorted(task for task, debt in task_debts.items() if debt)
    minimum_without_dominant = envelope.get(
        "minimum_future_nondominant_pairs_if_zero_future_dominant"
    )
    if isinstance(minimum_without_dominant, bool) or not isinstance(
        minimum_without_dominant, int
    ):
        raise ForwardV2Error("invalid guard minimum")
    adherence = (
        "ADHERED_NO_DOMINANT_INCREMENT"
        if future_dominant == 0
        else "DEFINITELY_NOT_ADHERED_BEFORE_DEBT_CLEARANCE"
        if future_nondominant < minimum_without_dominant
        else "ORDER_UNOBSERVED_CANNOT_DETERMINE"
    )
    debt_delta = observed_debt - baseline_debt
    direction = (
        "CLEARED"
        if observed_debt == 0 and debt_delta < 0
        else "IMPROVED_BUT_UNCLEARED"
        if debt_delta < 0
        else "WORSENED"
        if debt_delta > 0
        else "UNCHANGED"
    )
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
            "run_hhi_delta": secondary["current_run_hhi"] - secondary["baseline_run_hhi"],
            "pair_hhi_delta": secondary["current_pair_hhi"] - secondary["baseline_pair_hhi"],
            "run_to_pair_tv_delta": secondary["current_run_to_pair_tv"]
            - secondary["baseline_run_to_pair_tv"],
            "preregistered_for_this_forward_check": False,
        }
    )
    protocol_name = (
        "task_balance_guard_forward_validation_v3"
        if allow_task_expansion
        else PROTOCOL
    )
    status_name = (
        "STRUCTURAL_ONLY_FORWARD_ACCOUNTING_EXACT_WITH_TASK_EXPANSION"
        if allow_task_expansion
        else "STRUCTURAL_ONLY_FORWARD_ACCOUNTING_EXACT"
    )
    source_validation = {
        "baseline_summary_and_ledger_revalidated": True,
        "current_summary_and_ledger_revalidated": True,
        "current_total_cross_checked_by_receipt_only_independent_verifier": True,
        "prediction_matrix_input_used": False,
    }
    chronology = {
        "old_run_set_preserved": True,
        "old_run_order_preserved_as_subsequence": True,
        "old_rows_unchanged_by_run_id": True,
        "byte_prefix_required": False,
        "observed_byte_prefix": current_raw.startswith(baseline_raw),
        "baseline_runs": len(baseline_rows),
        "current_runs": len(current_rows),
        "new_runs": len(new_ids),
        "new_runs_before_old_baseline_tail": inserted_before_tail,
    }
    forward_result = {
        "dominant_task": dominant,
        "future_dominant_pairs": future_dominant,
        "future_nondominant_pairs": future_nondominant,
        "baseline_debt": baseline_debt,
        "predicted_current_debt": predicted_debt,
        "observed_current_debt": observed_debt,
        "debt_delta": debt_delta,
        "debt_direction": direction,
        "debt_accounting_identity_exact": True,
        "current_dominant_pairs": current["dominant_pairs"],
        "current_dominant_share": current["dominant_pairs"] / current["pairs"],
        "current_cap_pass": not violating,
        "current_cap_violating_tasks": violating,
        "immediate_action_adherence": adherence,
        "strict_guard_adherence_claimed": False,
        "pair_increments_by_task": increments,
    }
    claim_boundary = {
        "arithmetic_identity_is_statistical_prediction": False,
        "natural_accrual_causal_effect_claimed": False,
        "producer_compliance_claimed": False,
        "predictor_accuracy_effect_or_search_utility_computed": False,
        "descriptive_hhi_or_tv_can_rescue_failed_cap": False,
    }
    if allow_task_expansion:
        source_validation.update(
            {
                "task_universe_contract": "monotone_expansion_with_explicit_zero_extension",
                "baseline_task_set_subset_of_current": True,
            }
        )
        chronology.update(
            {
                "baseline_tasks": len(baseline_tasks),
                "current_tasks": len(current_tasks),
                "added_tasks": len(current_tasks - baseline_tasks),
                "removed_tasks": 0,
                "task_identities_emitted": True,
            }
        )
        forward_result.update(
            {
                "new_task_zero_extension_explicit": True,
                "added_task_count": len(current_tasks - baseline_tasks),
            }
        )
        claim_boundary["same_snapshot_v2_kill_rescued"] = False
    return {
        "protocol": protocol_name,
        "status": status_name,
        "inputs": {
            "baseline_guard_sha256": guard_sha,
            "baseline_guard_independent_verification_sha256": guard_verification_sha,
            "baseline_accumulator_summary_sha256": baseline_summary_sha,
            "baseline_first960_runs_sha256": baseline_ledger_sha,
            "baseline_snapshot_sha256": baseline_snapshot,
            "current_accumulator_summary_sha256": current_summary_sha,
            "current_first960_runs_sha256": current_ledger_sha,
            "current_snapshot_sha256": current_snapshot,
            "current_receipt_common_support_verification_sha256": current_common_support_sha,
        },
        "source_validation": source_validation,
        "chronology_audit": chronology,
        "frozen_guard_forward_result": forward_result,
        "descriptive_secondary": secondary,
        "claim_boundary": claim_boundary,
        "access_attestation": {
            "labels_grades_outcomes_or_winner_orientation_read": False,
            "prediction_pair_files_opened": [],
            "prediction_values_read_or_aggregated": False,
            "raw_archive_payload_read": False,
            "gpu_jobs": 0,
            "api_calls": 0,
            "model_fits": 0,
            "base_llm_updates": 0,
            "randomness_used": False,
        },
    }


def write_new(path: Path, value: dict[str, Any]) -> None:
    if path.exists() or not path.parent.is_dir() or path.parent.is_symlink():
        raise ForwardV2Error("output path is present or unsafe")
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
    parser.add_argument("--guard-verification", required=True, type=Path)
    parser.add_argument("--expect-guard-verification-sha256", required=True)
    parser.add_argument("--baseline-summary", required=True, type=Path)
    parser.add_argument("--expect-baseline-summary-sha256", required=True)
    parser.add_argument("--baseline-ledger", required=True, type=Path)
    parser.add_argument("--expect-baseline-ledger-sha256", required=True)
    parser.add_argument("--baseline-snapshot-sha256", required=True)
    parser.add_argument("--current-summary", required=True, type=Path)
    parser.add_argument("--expect-current-summary-sha256", required=True)
    parser.add_argument("--current-ledger", required=True, type=Path)
    parser.add_argument("--expect-current-ledger-sha256", required=True)
    parser.add_argument("--current-snapshot-sha256", required=True)
    parser.add_argument("--current-common-support-verification", required=True, type=Path)
    parser.add_argument("--expect-current-common-support-verification-sha256", required=True)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    try:
        value = build_forward(
            args.guard,
            args.expect_guard_sha256,
            args.guard_verification,
            args.expect_guard_verification_sha256,
            args.baseline_summary,
            args.expect_baseline_summary_sha256,
            args.baseline_ledger,
            args.expect_baseline_ledger_sha256,
            args.baseline_snapshot_sha256,
            args.current_summary,
            args.expect_current_summary_sha256,
            args.current_ledger,
            args.expect_current_ledger_sha256,
            args.current_snapshot_sha256,
            args.current_common_support_verification,
            args.expect_current_common_support_verification_sha256,
        )
        write_new(args.output.resolve(), value)
        print(json.dumps(value["frozen_guard_forward_result"], sort_keys=True, separators=(",", ":")))
        return 0
    except (OSError, BalanceGuardV2Error, ForwardV2Error, ValueError, TypeError, ZeroDivisionError) as exc:
        print(f"TASK_BALANCE_FORWARD_V2_ERROR: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
