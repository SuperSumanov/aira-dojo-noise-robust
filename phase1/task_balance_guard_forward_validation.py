#!/usr/bin/env python3
"""Validate a frozen task-balance guard on a later outcome-blind snapshot."""
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


PROTOCOL = "task_balance_guard_forward_validation_v1"


class ForwardValidationError(RuntimeError):
    pass


def digest(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def read_bound(path: Path, expected_sha256: str) -> tuple[bytes, dict[str, Any]]:
    if path.is_symlink() or not path.is_file():
        raise ForwardValidationError("input is absent, non-regular, or symlinked")
    raw = path.read_bytes()
    if digest(raw) != expected_sha256:
        raise ForwardValidationError("input hash mismatch")
    try:
        value = json.loads(raw)
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ForwardValidationError("cannot parse input") from exc
    if not isinstance(value, dict):
        raise ForwardValidationError("input is not an object")
    return raw, value


def require_int(value: Any, label: str, *, minimum: int = 0) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value < minimum:
        raise ForwardValidationError(f"invalid {label}")
    return value


def normalize_counts(value: Any, label: str) -> dict[str, int]:
    if not isinstance(value, dict) or not value:
        raise ForwardValidationError(f"invalid {label}")
    counts: dict[str, int] = {}
    for task, count in value.items():
        if not isinstance(task, str) or not task:
            raise ForwardValidationError(f"invalid {label} task")
        counts[task] = require_int(count, f"{label} count")
    return counts


def hhi(counts: dict[str, int]) -> float:
    total = sum(counts.values())
    if total <= 0:
        raise ForwardValidationError("empty distribution")
    return sum((count / total) ** 2 for count in counts.values())


def tv(left: dict[str, int], right: dict[str, int]) -> float:
    left_total = sum(left.values())
    right_total = sum(right.values())
    if left_total <= 0 or right_total <= 0:
        raise ForwardValidationError("empty distribution")
    tasks = set(left) | set(right)
    return 0.5 * sum(
        abs(left.get(task, 0) / left_total - right.get(task, 0) / right_total)
        for task in tasks
    )


def build_forward_validation(
    guard: dict[str, Any],
    guard_sha256: str,
    observed: dict[str, Any],
    observed_sha256: str,
) -> dict[str, Any]:
    if guard.get("protocol") != "prospective_task_balance_accrual_guard_v1":
        raise ForwardValidationError("guard protocol mismatch")
    if guard.get("status") != "OUTCOME_BLIND_TASK_BALANCE_ACCRUAL_GUARD_READY":
        raise ForwardValidationError("guard status mismatch")
    if guard.get("access_attestation") != {
        "labels_grades_outcomes_or_predictions_read": False,
        "accuracy_effect_or_search_utility_computed": False,
        "gpu_or_api_calls": 0,
        "randomness_used": False,
    }:
        raise ForwardValidationError("guard access attestation mismatch")
    if observed.get("protocol") != "task_balance_guard_forward_structural_input_v1":
        raise ForwardValidationError("observed protocol mismatch")
    if observed.get("status") != "OUTCOME_BLIND_FORWARD_INPUT_EXTRACTED":
        raise ForwardValidationError("observed status mismatch")
    if observed.get("access_attestation") != {
        "labels_grades_outcomes_or_winner_orientation_read": False,
        "prediction_values_read_or_aggregated": False,
        "raw_archive_payload_read": False,
        "gpu_jobs": 0,
        "api_calls": 0,
        "model_fits": 0,
        "base_llm_updates": 0,
    }:
        raise ForwardValidationError("observed access attestation mismatch")
    source_sha = observed.get("source_sha256")
    if not isinstance(source_sha, dict) or source_sha.get("baseline_guard") != guard_sha256:
        raise ForwardValidationError("baseline guard binding mismatch")
    if observed.get("baseline_snapshot_sha256") != guard.get("snapshot_sha256"):
        raise ForwardValidationError("baseline snapshot mismatch")

    chronology = observed.get("chronology")
    if not isinstance(chronology, dict):
        raise ForwardValidationError("chronology missing")
    baseline_runs = require_int(chronology.get("baseline_runs"), "baseline runs", minimum=1)
    current_runs = require_int(chronology.get("current_runs"), "current runs", minimum=1)
    new_runs = require_int(chronology.get("new_runs"), "new runs")
    if current_runs - baseline_runs != new_runs:
        raise ForwardValidationError("run delta mismatch")
    for key in (
        "baseline_run_id_set_subset_of_current",
        "baseline_run_id_sequence_is_subsequence",
        "common_rows_equal_when_joined_by_run_id",
    ):
        if chronology.get(key) is not True:
            raise ForwardValidationError(f"chronology invariant failed: {key}")
    if not isinstance(chronology.get("baseline_is_byte_prefix_of_current"), bool):
        raise ForwardValidationError("byte-prefix diagnostic is not boolean")
    inserted_before_tail = require_int(
        chronology.get("new_runs_before_old_baseline_tail"), "inserted runs"
    )
    if inserted_before_tail > new_runs:
        raise ForwardValidationError("inserted-run count exceeds new runs")

    headroom = guard.get("single_task_only_headroom")
    if not isinstance(headroom, list) or not headroom:
        raise ForwardValidationError("baseline task counts missing")
    baseline_pairs: dict[str, int] = {}
    for row in headroom:
        if not isinstance(row, dict):
            raise ForwardValidationError("invalid baseline task row")
        task = row.get("task")
        if not isinstance(task, str) or not task or task in baseline_pairs:
            raise ForwardValidationError("invalid or duplicate baseline task")
        baseline_pairs[task] = require_int(row.get("current_pairs"), "baseline pairs")

    current_state = guard.get("current")
    envelope = guard.get("exact_integer_envelope")
    if not isinstance(current_state, dict) or not isinstance(envelope, dict):
        raise ForwardValidationError("guard balance state missing")
    baseline_total = sum(baseline_pairs.values())
    if baseline_total != require_int(current_state.get("pairs"), "guard pairs", minimum=1):
        raise ForwardValidationError("guard pair total mismatch")
    dominant_task, dominant_pairs = max(
        baseline_pairs.items(), key=lambda item: (item[1], item[0])
    )
    if dominant_task != current_state.get("dominant_task"):
        raise ForwardValidationError("baseline dominant task mismatch")
    if dominant_pairs != current_state.get("dominant_pairs"):
        raise ForwardValidationError("baseline dominant count mismatch")
    cap_value = current_state.get("maximum_share")
    if isinstance(cap_value, bool) or not isinstance(cap_value, (int, float)):
        raise ForwardValidationError("invalid cap")
    cap = Fraction(str(cap_value))
    if not 0 < cap < 1:
        raise ForwardValidationError("cap outside (0,1)")
    a, b = cap.numerator, cap.denominator
    baseline_debt = max(0, b * dominant_pairs - a * baseline_total)
    if baseline_debt != envelope.get("imbalance_debt_numerator"):
        raise ForwardValidationError("baseline debt mismatch")

    pair_inventory = observed.get("pair_inventory")
    if not isinstance(pair_inventory, dict):
        raise ForwardValidationError("pair inventory missing")
    increments = normalize_counts(
        pair_inventory.get("pair_increments_by_task"), "pair increments"
    )
    all_tasks = set(baseline_pairs) | set(increments)
    if set(increments) != all_tasks:
        raise ForwardValidationError("increment task universe is incomplete")
    current_pairs = {
        task: baseline_pairs.get(task, 0) + increments.get(task, 0)
        for task in sorted(all_tasks)
    }
    future_dominant = increments[dominant_task]
    future_nondominant = sum(increments.values()) - future_dominant
    current_total = sum(current_pairs.values())
    new_pairs = sum(increments.values())
    predicted_debt = max(
        0,
        baseline_debt + (b - a) * future_dominant - a * future_nondominant,
    )
    current_task_debts = {
        task: max(0, b * count - a * current_total)
        for task, count in current_pairs.items()
    }
    violating_tasks = sorted(task for task, debt in current_task_debts.items() if debt > 0)
    observed_debt = current_task_debts[dominant_task]
    current_dominant_task, current_dominant_pairs = max(
        current_pairs.items(), key=lambda item: (item[1], item[0])
    )
    expected_inventory = {
        "baseline_pairs": baseline_total,
        "current_pairs": current_total,
        "new_pairs": new_pairs,
        "tasks": len(all_tasks),
        "dominant_task": dominant_task,
        "baseline_dominant_pairs": dominant_pairs,
        "current_dominant_pairs": current_pairs[dominant_task],
        "future_dominant_pairs": future_dominant,
        "future_nondominant_pairs": future_nondominant,
        "baseline_debt": baseline_debt,
        "predicted_current_debt": predicted_debt,
        "observed_current_debt": observed_debt,
        "current_dominant_share": current_pairs[dominant_task] / current_total,
        "current_cap_pass": not violating_tasks,
        "current_cap_violating_tasks": violating_tasks,
        "strict_zero_dominant_immediate_action_adhered": future_dominant == 0,
        "pair_increments_by_task": dict(sorted(increments.items())),
    }
    if pair_inventory != expected_inventory:
        raise ForwardValidationError("observed pair inventory is internally inconsistent")
    if current_dominant_task != dominant_task:
        raise ForwardValidationError("dominant task changed; frozen envelope is insufficient")
    if predicted_debt != observed_debt:
        raise ForwardValidationError("frozen-envelope prediction does not match current debt")

    run_inventory = observed.get("run_inventory")
    if not isinstance(run_inventory, dict):
        raise ForwardValidationError("run inventory missing")
    baseline_run_counts = normalize_counts(
        run_inventory.get("baseline_runs_by_task"), "baseline run counts"
    )
    current_run_counts = normalize_counts(
        run_inventory.get("current_runs_by_task"), "current run counts"
    )
    if sum(baseline_run_counts.values()) != baseline_runs:
        raise ForwardValidationError("baseline run inventory does not sum")
    if sum(current_run_counts.values()) != current_runs:
        raise ForwardValidationError("current run inventory does not sum")
    if any(current_run_counts.get(task, 0) < count for task, count in baseline_run_counts.items()):
        raise ForwardValidationError("run inventory is not append-only")

    recomputed_secondary = {
        "baseline_run_hhi": hhi(baseline_run_counts),
        "current_run_hhi": hhi(current_run_counts),
        "baseline_pair_hhi": hhi(baseline_pairs),
        "current_pair_hhi": hhi(current_pairs),
        "baseline_run_to_pair_tv": tv(baseline_run_counts, baseline_pairs),
        "current_run_to_pair_tv": tv(current_run_counts, current_pairs),
    }
    observed_secondary = observed.get("descriptive_secondary")
    if not isinstance(observed_secondary, dict) or set(observed_secondary) != set(
        recomputed_secondary
    ):
        raise ForwardValidationError("descriptive secondary schema mismatch")
    for key, expected in recomputed_secondary.items():
        value = observed_secondary.get(key)
        if isinstance(value, bool) or not isinstance(value, (int, float)):
            raise ForwardValidationError("invalid descriptive secondary value")
        if not math.isclose(value, expected, rel_tol=0.0, abs_tol=1e-15):
            raise ForwardValidationError(f"descriptive secondary mismatch: {key}")

    minimum_without_dominant = require_int(
        envelope.get("minimum_future_nondominant_pairs_if_zero_future_dominant"),
        "minimum future nondominant",
    )
    if future_dominant == 0:
        adherence_status = "ADHERED_NO_DOMINANT_INCREMENT"
    elif future_nondominant < minimum_without_dominant:
        adherence_status = "DEFINITELY_NOT_ADHERED_BEFORE_DEBT_CLEARANCE"
    else:
        adherence_status = "ORDER_UNOBSERVED_CANNOT_DETERMINE"

    debt_delta = observed_debt - baseline_debt
    if debt_delta < 0:
        debt_direction = "IMPROVED_BUT_UNCLEARED" if observed_debt else "CLEARED"
    elif debt_delta > 0:
        debt_direction = "WORSENED"
    else:
        debt_direction = "UNCHANGED"
    return {
        "protocol": PROTOCOL,
        "status": "FORWARD_ACCOUNTING_EXACT",
        "inputs": {
            "baseline_guard_sha256": guard_sha256,
            "observed_structural_input_sha256": observed_sha256,
            "baseline_snapshot_sha256": guard.get("snapshot_sha256"),
            "current_snapshot_sha256": observed.get("current_snapshot_sha256"),
        },
        "chronology_audit": {
            "old_run_set_preserved": True,
            "old_run_order_preserved_as_subsequence": True,
            "old_rows_unchanged_by_run_id": True,
            "byte_prefix_required": False,
            "observed_byte_prefix": chronology["baseline_is_byte_prefix_of_current"],
            "new_runs": new_runs,
            "new_runs_before_old_baseline_tail": inserted_before_tail,
        },
        "frozen_guard_forward_result": {
            "dominant_task": dominant_task,
            "future_dominant_pairs": future_dominant,
            "future_nondominant_pairs": future_nondominant,
            "baseline_debt": baseline_debt,
            "predicted_current_debt": predicted_debt,
            "observed_current_debt": observed_debt,
            "debt_delta": debt_delta,
            "debt_direction": debt_direction,
            "debt_accounting_identity_exact": True,
            "current_cap_pass": not violating_tasks,
            "current_cap_violating_tasks": violating_tasks,
            "immediate_action_adherence": adherence_status,
            "strict_guard_adherence_claimed": False,
        },
        "descriptive_secondary": {
            **recomputed_secondary,
            "run_hhi_delta": recomputed_secondary["current_run_hhi"]
            - recomputed_secondary["baseline_run_hhi"],
            "pair_hhi_delta": recomputed_secondary["current_pair_hhi"]
            - recomputed_secondary["baseline_pair_hhi"],
            "run_to_pair_tv_delta": recomputed_secondary["current_run_to_pair_tv"]
            - recomputed_secondary["baseline_run_to_pair_tv"],
            "preregistered_for_this_forward_check": False,
        },
        "claim_boundary": {
            "arithmetic_identity_is_statistical_prediction": False,
            "natural_accrual_causal_effect_claimed": False,
            "producer_compliance_claimed": False,
            "predictor_accuracy_effect_or_search_utility_computed": False,
            "descriptive_hhi_or_tv_can_rescue_failed_cap": False,
        },
        "access_attestation": {
            "labels_grades_outcomes_or_winner_orientation_read": False,
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
    if path.exists():
        raise ForwardValidationError("output exists")
    if not path.parent.is_dir() or path.parent.is_symlink():
        raise ForwardValidationError("output parent is absent or unsafe")
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
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    try:
        guard_raw, guard = read_bound(args.guard, args.expect_guard_sha256)
        observed_raw, observed = read_bound(args.observed, args.expect_observed_sha256)
        result = build_forward_validation(
            guard,
            digest(guard_raw),
            observed,
            digest(observed_raw),
        )
        write_new(args.output.resolve(), result)
        print(json.dumps(result["frozen_guard_forward_result"], sort_keys=True, separators=(",", ":")))
        return 0
    except (OSError, ForwardValidationError, ValueError, ZeroDivisionError) as exc:
        print(f"TASK_BALANCE_FORWARD_VALIDATION_ERROR: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
