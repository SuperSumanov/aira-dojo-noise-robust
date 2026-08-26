#!/usr/bin/env python3
"""Independent verifier for structural-only task-balance forward validation v2."""
from __future__ import annotations

import argparse
import hashlib
import json
import math
import os
import sys
from collections import Counter
from fractions import Fraction
from pathlib import Path
from typing import Any


LEDGER_KEYS = {
    "drop_id",
    "endpoints",
    "flow_status",
    "generation_started_at_utc",
    "run_id",
    "source_sha256",
    "task",
}


class ForwardV2VerificationError(RuntimeError):
    pass


def digest(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def load_object(path: Path, expected: str) -> tuple[bytes, dict[str, Any]]:
    if path.is_symlink() or not path.is_file():
        raise ForwardV2VerificationError("input is absent, non-regular, or symlinked")
    raw = path.read_bytes()
    if digest(raw) != expected:
        raise ForwardV2VerificationError("input hash mismatch")
    try:
        value = json.loads(raw)
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ForwardV2VerificationError("cannot parse JSON input") from exc
    if not isinstance(value, dict):
        raise ForwardV2VerificationError("JSON input is not an object")
    return raw, value


def integer(value: Any, label: str, minimum: int = 0) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value < minimum:
        raise ForwardV2VerificationError(f"invalid {label}")
    return value


def count_map(value: Any, label: str) -> dict[str, int]:
    if not isinstance(value, dict) or not value:
        raise ForwardV2VerificationError(f"invalid {label}")
    result: dict[str, int] = {}
    for task, count in value.items():
        if not isinstance(task, str) or not task:
            raise ForwardV2VerificationError(f"invalid {label} task")
        result[task] = integer(count, label)
    return result


def source(
    summary_path: Path,
    summary_sha: str,
    ledger_path: Path,
    ledger_sha: str,
    snapshot: str,
) -> tuple[bytes, list[dict[str, Any]], dict[str, Any]]:
    parent = summary_path.absolute().parent
    if (
        len(snapshot) != 64
        or any(character not in "0123456789abcdef" for character in snapshot)
        or parent.is_symlink()
        or parent.parent.is_symlink()
        or summary_path.name != "summary.json"
        or ledger_path.name != "provisional_first960_runs.jsonl"
        or parent.name != "accumulator"
        or parent.parent.name != snapshot
        or ledger_path.absolute().parent != parent
    ):
        raise ForwardV2VerificationError("snapshot path binding mismatch")
    _, summary = load_object(summary_path, summary_sha)
    if (
        summary.get("protocol") != "prospective_accumulator_v1"
        or summary.get("status") != "PROSPECTIVE_COHORT_COLLECTING"
    ):
        raise ForwardV2VerificationError("accumulator identity mismatch")
    sec = summary.get("security", {})
    if (
        sec.get("label_vault_opened") is not False
        or sec.get("outcome_files_opened") != []
        or sec.get("scorer_prediction_files_opened") != []
    ):
        raise ForwardV2VerificationError("accumulator security mismatch")
    if summary.get("closure") != {
        "all_scheduled_runs_uploaded": None,
        "outcomes_read": None,
        "provided": False,
    }:
        raise ForwardV2VerificationError("closure state mismatch")
    if summary.get("outputs", {}).get("provisional_first960_runs_sha256") != ledger_sha:
        raise ForwardV2VerificationError("summary-ledger binding mismatch")
    support = summary.get("task_support", {}).get("provisional_first960", {})
    run_counts = count_map(support.get("run_counts"), "run counts")
    endpoint_counts = count_map(support.get("endpoint_counts"), "endpoint counts")
    pair_counts = count_map(support.get("structural_pair_counts"), "pair counts")
    if set(run_counts) != set(endpoint_counts) or set(run_counts) != set(pair_counts):
        raise ForwardV2VerificationError("task universe mismatch")
    runs = integer(support.get("runs"), "runs", 1)
    endpoints = integer(support.get("endpoints"), "endpoints", 1)
    pairs = integer(support.get("structural_pairs"), "pairs", 1)
    tasks = integer(support.get("tasks"), "tasks", 1)
    if (
        sum(run_counts.values()) != runs
        or sum(endpoint_counts.values()) != endpoints
        or sum(pair_counts.values()) != pairs
        or len(pair_counts) != tasks
    ):
        raise ForwardV2VerificationError("summary totals mismatch")
    dominant_task, dominant_pairs = max(
        pair_counts.items(), key=lambda item: (item[1], item[0])
    )
    if not math.isclose(
        support.get("dominant_structural_pair_task_share"),
        dominant_pairs / pairs,
        rel_tol=0.0,
        abs_tol=1e-15,
    ):
        raise ForwardV2VerificationError("dominant share mismatch")

    if ledger_path.is_symlink() or not ledger_path.is_file():
        raise ForwardV2VerificationError("invalid ledger path")
    raw = ledger_path.read_bytes()
    if digest(raw) != ledger_sha:
        raise ForwardV2VerificationError("ledger hash mismatch")
    try:
        rows = [json.loads(line) for line in raw.decode("utf-8").splitlines()]
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ForwardV2VerificationError("cannot parse ledger") from exc
    if not rows or any(not isinstance(row, dict) or set(row) != LEDGER_KEYS for row in rows):
        raise ForwardV2VerificationError("ledger schema mismatch")
    seen: set[str] = set()
    order_keys: list[tuple[str, str, str]] = []
    ledger_runs: Counter[str] = Counter()
    ledger_endpoints: Counter[str] = Counter()
    for row in rows:
        run_id = row.get("run_id")
        task = row.get("task")
        if not isinstance(run_id, str) or not run_id or run_id in seen:
            raise ForwardV2VerificationError("invalid or duplicate run_id")
        if not isinstance(task, str) or task not in run_counts:
            raise ForwardV2VerificationError("invalid ledger task")
        if row.get("flow_status") != "scoreable":
            raise ForwardV2VerificationError("unscoreable ledger row")
        for key in ("drop_id", "generation_started_at_utc", "source_sha256"):
            if not isinstance(row.get(key), str) or not row[key]:
                raise ForwardV2VerificationError(f"invalid ledger {key}")
        if len(row["source_sha256"]) != 64 or any(
            character not in "0123456789abcdef" for character in row["source_sha256"]
        ):
            raise ForwardV2VerificationError("invalid ledger source_sha256")
        count = integer(row.get("endpoints"), "ledger endpoints", 1)
        seen.add(run_id)
        ledger_runs[task] += 1
        ledger_endpoints[task] += count
        order_keys.append(
            (row["generation_started_at_utc"], row["source_sha256"], run_id)
        )
    if order_keys != sorted(order_keys):
        raise ForwardV2VerificationError("ledger chronology is not sorted")
    if len(rows) != runs or dict(ledger_runs) != run_counts:
        raise ForwardV2VerificationError("ledger run totals mismatch")
    if dict(ledger_endpoints) != endpoint_counts:
        raise ForwardV2VerificationError("ledger endpoint totals mismatch")
    return raw, rows, {
        "runs": runs,
        "endpoints": endpoints,
        "pairs": pairs,
        "tasks": tasks,
        "run_counts": run_counts,
        "pair_counts": pair_counts,
        "dominant_task": dominant_task,
        "dominant_pairs": dominant_pairs,
    }


def hhi(counts: dict[str, int]) -> float:
    total = sum(counts.values())
    return math.fsum((count / total) ** 2 for count in counts.values())


def tv(left: dict[str, int], right: dict[str, int]) -> float:
    left_total = sum(left.values())
    right_total = sum(right.values())
    return 0.5 * math.fsum(
        abs(left.get(task, 0) / left_total - right.get(task, 0) / right_total)
        for task in set(left) | set(right)
    )


def subsequence(left: list[str], right: list[str]) -> bool:
    cursor = iter(right)
    return all(any(candidate == value for candidate in cursor) for value in left)


def verify(
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
    common_support_path: Path,
    common_support_sha: str,
    result_path: Path,
    result_sha: str,
) -> dict[str, Any]:
    _, guard = load_object(guard_path, guard_sha)
    _, guard_verification = load_object(guard_verification_path, guard_verification_sha)
    _, common_support = load_object(common_support_path, common_support_sha)
    result_raw, result = load_object(result_path, result_sha)
    if (
        guard.get("protocol") != "prospective_task_balance_accrual_guard_v2"
        or guard.get("status") != "STRUCTURAL_ONLY_TASK_BALANCE_ACCRUAL_GUARD_READY"
        or guard.get("snapshot_sha256") != baseline_snapshot
        or guard.get("inputs", {}).get("accumulator_summary_sha256") != baseline_summary_sha
        or guard.get("inputs", {}).get("provisional_first960_runs_sha256")
        != baseline_ledger_sha
    ):
        raise ForwardV2VerificationError("guard identity or binding mismatch")
    if (
        guard_verification.get("protocol")
        != "independent_prospective_task_balance_accrual_guard_v2"
        or guard_verification.get("status")
        != "INDEPENDENT_STRUCTURAL_ONLY_TASK_BALANCE_GUARD_PASS"
        or guard_verification.get("guard_sha256") != guard_sha
        or guard_verification.get("snapshot_sha256") != baseline_snapshot
    ):
        raise ForwardV2VerificationError("guard verification mismatch")
    expected_zero = {
        "outcomes_or_prediction_values_read": False,
        "raw_archive_payload_read": False,
        "gpu_or_api_calls": 0,
        "randomness_used": False,
    }
    if guard_verification.get("access_attestation") != expected_zero:
        raise ForwardV2VerificationError("guard verification access mismatch")

    baseline_raw, baseline_rows, baseline = source(
        baseline_summary_path,
        baseline_summary_sha,
        baseline_ledger_path,
        baseline_ledger_sha,
        baseline_snapshot,
    )
    current_raw, current_rows, current = source(
        current_summary_path,
        current_summary_sha,
        current_ledger_path,
        current_ledger_sha,
        current_snapshot,
    )
    for key, expected in {
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
    }.items():
        if common_support.get(key) != expected:
            raise ForwardV2VerificationError(f"common support mismatch: {key}")

    baseline_ids = [row["run_id"] for row in baseline_rows]
    current_ids = [row["run_id"] for row in current_rows]
    baseline_set = set(baseline_ids)
    current_set = set(current_ids)
    current_map = {row["run_id"]: row for row in current_rows}
    if not baseline_set <= current_set or not subsequence(baseline_ids, current_ids):
        raise ForwardV2VerificationError("chronology containment mismatch")
    if not all(current_map[run_id] == row for run_id, row in zip(baseline_ids, baseline_rows)):
        raise ForwardV2VerificationError("common ledger row changed")
    new_ids = current_set - baseline_set
    tail_index = current_ids.index(baseline_ids[-1])
    inserted = sum(
        1 for index, run_id in enumerate(current_ids) if run_id in new_ids and index < tail_index
    )
    expected_chronology = {
        "old_run_set_preserved": True,
        "old_run_order_preserved_as_subsequence": True,
        "old_rows_unchanged_by_run_id": True,
        "byte_prefix_required": False,
        "observed_byte_prefix": current_raw.startswith(baseline_raw),
        "baseline_runs": len(baseline_rows),
        "current_runs": len(current_rows),
        "new_runs": len(new_ids),
        "new_runs_before_old_baseline_tail": inserted,
    }

    baseline_pairs = baseline["pair_counts"]
    current_pairs = current["pair_counts"]
    baseline_runs = baseline["run_counts"]
    current_runs = current["run_counts"]
    if set(baseline_pairs) != set(current_pairs) or set(baseline_runs) != set(current_runs):
        raise ForwardV2VerificationError("task universe changed")
    increments = {
        task: current_pairs[task] - baseline_pairs[task] for task in sorted(baseline_pairs)
    }
    run_increments = {
        task: current_runs[task] - baseline_runs[task] for task in sorted(baseline_runs)
    }
    if any(value < 0 for value in increments.values()) or any(
        value < 0 for value in run_increments.values()
    ):
        raise ForwardV2VerificationError("negative accrual encountered")
    if sum(increments.values()) != current["pairs"] - baseline["pairs"]:
        raise ForwardV2VerificationError("pair increment mismatch")
    if sum(run_increments.values()) != len(new_ids):
        raise ForwardV2VerificationError("run increment mismatch")
    state = guard.get("current", {})
    envelope = guard.get("exact_integer_envelope", {})
    if (
        state.get("pairs") != baseline["pairs"]
        or state.get("dominant_task") != baseline["dominant_task"]
        or state.get("dominant_pairs") != baseline["dominant_pairs"]
        or current["dominant_task"] != baseline["dominant_task"]
    ):
        raise ForwardV2VerificationError("guard state mismatch")
    cap = Fraction(str(state.get("maximum_share")))
    a, b = cap.numerator, cap.denominator
    dominant = baseline["dominant_task"]
    baseline_debt = max(0, b * baseline["dominant_pairs"] - a * baseline["pairs"])
    if envelope.get("imbalance_debt_numerator") != baseline_debt:
        raise ForwardV2VerificationError("baseline debt mismatch")
    future_dominant = increments[dominant]
    future_nondominant = sum(increments.values()) - future_dominant
    predicted = max(
        0, baseline_debt + (b - a) * future_dominant - a * future_nondominant
    )
    task_debts = {
        task: max(0, b * count - a * current["pairs"])
        for task, count in current_pairs.items()
    }
    observed = task_debts[dominant]
    if predicted != observed:
        raise ForwardV2VerificationError("debt identity mismatch")
    violations = sorted(task for task, debt in task_debts.items() if debt)
    minimum = integer(
        envelope.get("minimum_future_nondominant_pairs_if_zero_future_dominant"),
        "minimum nondominant",
    )
    adherence = (
        "ADHERED_NO_DOMINANT_INCREMENT"
        if future_dominant == 0
        else "DEFINITELY_NOT_ADHERED_BEFORE_DEBT_CLEARANCE"
        if future_nondominant < minimum
        else "ORDER_UNOBSERVED_CANNOT_DETERMINE"
    )
    delta = observed - baseline_debt
    direction = (
        "CLEARED"
        if observed == 0 and delta < 0
        else "IMPROVED_BUT_UNCLEARED"
        if delta < 0
        else "WORSENED"
        if delta > 0
        else "UNCHANGED"
    )
    expected_forward = {
        "dominant_task": dominant,
        "future_dominant_pairs": future_dominant,
        "future_nondominant_pairs": future_nondominant,
        "baseline_debt": baseline_debt,
        "predicted_current_debt": predicted,
        "observed_current_debt": observed,
        "debt_delta": delta,
        "debt_direction": direction,
        "debt_accounting_identity_exact": True,
        "current_dominant_pairs": current["dominant_pairs"],
        "current_dominant_share": current["dominant_pairs"] / current["pairs"],
        "current_cap_pass": not violations,
        "current_cap_violating_tasks": violations,
        "immediate_action_adherence": adherence,
        "strict_guard_adherence_claimed": False,
        "pair_increments_by_task": increments,
    }
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
    expected_inputs = {
        "baseline_guard_sha256": guard_sha,
        "baseline_guard_independent_verification_sha256": guard_verification_sha,
        "baseline_accumulator_summary_sha256": baseline_summary_sha,
        "baseline_first960_runs_sha256": baseline_ledger_sha,
        "baseline_snapshot_sha256": baseline_snapshot,
        "current_accumulator_summary_sha256": current_summary_sha,
        "current_first960_runs_sha256": current_ledger_sha,
        "current_snapshot_sha256": current_snapshot,
        "current_receipt_common_support_verification_sha256": common_support_sha,
    }
    expected_source = {
        "baseline_summary_and_ledger_revalidated": True,
        "current_summary_and_ledger_revalidated": True,
        "current_total_cross_checked_by_receipt_only_independent_verifier": True,
        "prediction_matrix_input_used": False,
    }
    expected_boundary = {
        "arithmetic_identity_is_statistical_prediction": False,
        "natural_accrual_causal_effect_claimed": False,
        "producer_compliance_claimed": False,
        "predictor_accuracy_effect_or_search_utility_computed": False,
        "descriptive_hhi_or_tv_can_rescue_failed_cap": False,
    }
    expected_access = {
        "labels_grades_outcomes_or_winner_orientation_read": False,
        "prediction_pair_files_opened": [],
        "prediction_values_read_or_aggregated": False,
        "raw_archive_payload_read": False,
        "gpu_jobs": 0,
        "api_calls": 0,
        "model_fits": 0,
        "base_llm_updates": 0,
        "randomness_used": False,
    }
    if set(result) != {
        "protocol",
        "status",
        "inputs",
        "source_validation",
        "chronology_audit",
        "frozen_guard_forward_result",
        "descriptive_secondary",
        "claim_boundary",
        "access_attestation",
    }:
        raise ForwardV2VerificationError("result top-level schema mismatch")
    if result.get("protocol") != "task_balance_guard_forward_validation_v2":
        raise ForwardV2VerificationError("result protocol mismatch")
    if result.get("status") != "STRUCTURAL_ONLY_FORWARD_ACCOUNTING_EXACT":
        raise ForwardV2VerificationError("result status mismatch")
    exact_sections = {
        "inputs": expected_inputs,
        "source_validation": expected_source,
        "chronology_audit": expected_chronology,
        "frozen_guard_forward_result": expected_forward,
        "claim_boundary": expected_boundary,
        "access_attestation": expected_access,
    }
    for key, expected in exact_sections.items():
        if result.get(key) != expected:
            raise ForwardV2VerificationError(f"result section mismatch: {key}")
    actual_secondary = result.get("descriptive_secondary")
    if not isinstance(actual_secondary, dict) or set(actual_secondary) != set(secondary):
        raise ForwardV2VerificationError("secondary schema mismatch")
    for key, expected in secondary.items():
        actual = actual_secondary[key]
        if isinstance(expected, bool):
            if actual is not expected:
                raise ForwardV2VerificationError(f"secondary mismatch: {key}")
        elif not math.isclose(actual, expected, rel_tol=0.0, abs_tol=1e-15):
            raise ForwardV2VerificationError(f"secondary mismatch: {key}")
    return {
        "protocol": "independent_task_balance_guard_forward_validation_v2",
        "status": "INDEPENDENT_STRUCTURAL_ONLY_TASK_BALANCE_FORWARD_PASS",
        "forward_result_sha256": digest(result_raw),
        "inputs": expected_inputs,
        "checks": {
            "no_prediction_matrix_input": True,
            "baseline_guard_independently_verified": True,
            "both_accumulator_sources_recomputed": True,
            "current_total_receipt_cross_check_exact": True,
            "chronology_membership_exact": True,
            "debt_accounting_identity_exact": True,
            "cap_failure_preserved": not expected_forward["current_cap_pass"],
            "causal_and_effect_claims_forbidden": True,
        },
        "recomputed": {
            "baseline_pairs": baseline["pairs"],
            "current_pairs": current["pairs"],
            "new_runs": len(new_ids),
            "future_dominant_pairs": future_dominant,
            "future_nondominant_pairs": future_nondominant,
            "baseline_debt": baseline_debt,
            "current_debt": observed,
            "debt_delta": delta,
            "current_dominant_share": current["dominant_pairs"] / current["pairs"],
        },
        "access_attestation": expected_zero,
    }


def write_new(path: Path, value: dict[str, Any]) -> None:
    if path.exists() or not path.parent.is_dir() or path.parent.is_symlink():
        raise ForwardV2VerificationError("output path is present or unsafe")
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
    parser.add_argument("--result", required=True, type=Path)
    parser.add_argument("--expect-result-sha256", required=True)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    try:
        receipt = verify(
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
            args.result,
            args.expect_result_sha256,
        )
        write_new(args.output.resolve(), receipt)
        print(json.dumps(receipt["recomputed"], sort_keys=True, separators=(",", ":")))
        return 0
    except (OSError, ForwardV2VerificationError, ValueError, TypeError, ZeroDivisionError) as exc:
        print(f"TASK_BALANCE_FORWARD_V2_VERIFY_ERROR: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
