#!/usr/bin/env python3
"""Independently verify the structural-only task-balance guard v2."""
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


ROW_KEYS = {
    "drop_id",
    "endpoints",
    "flow_status",
    "generation_started_at_utc",
    "run_id",
    "source_sha256",
    "task",
}


class GuardV2VerificationError(RuntimeError):
    pass


def digest(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def load_json(path: Path, expected: str) -> tuple[bytes, dict[str, Any]]:
    if path.is_symlink() or not path.is_file():
        raise GuardV2VerificationError("input is absent, non-regular, or symlinked")
    raw = path.read_bytes()
    if digest(raw) != expected:
        raise GuardV2VerificationError("input hash mismatch")
    try:
        obj = json.loads(raw)
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise GuardV2VerificationError("cannot parse JSON") from exc
    if not isinstance(obj, dict):
        raise GuardV2VerificationError("JSON is not an object")
    return raw, obj


def as_int(value: Any, label: str, minimum: int = 0) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value < minimum:
        raise GuardV2VerificationError(f"invalid {label}")
    return value


def as_counts(value: Any, label: str) -> dict[str, int]:
    if not isinstance(value, dict) or not value:
        raise GuardV2VerificationError(f"invalid {label}")
    result: dict[str, int] = {}
    for task, count in value.items():
        if not isinstance(task, str) or not task:
            raise GuardV2VerificationError(f"invalid {label} task")
        result[task] = as_int(count, label)
    return result


def structural_source(
    summary_path: Path,
    summary_sha: str,
    ledger_path: Path,
    ledger_sha: str,
    snapshot: str,
) -> dict[str, Any]:
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
        raise GuardV2VerificationError("snapshot path binding mismatch")
    _, summary = load_json(summary_path, summary_sha)
    if (
        summary.get("protocol") != "prospective_accumulator_v1"
        or summary.get("status") != "PROSPECTIVE_COHORT_COLLECTING"
    ):
        raise GuardV2VerificationError("accumulator identity mismatch")
    sec = summary.get("security", {})
    if (
        sec.get("label_vault_opened") is not False
        or sec.get("outcome_files_opened") != []
        or sec.get("scorer_prediction_files_opened") != []
    ):
        raise GuardV2VerificationError("accumulator security mismatch")
    closure = summary.get("closure", {})
    if closure != {
        "all_scheduled_runs_uploaded": None,
        "outcomes_read": None,
        "provided": False,
    }:
        raise GuardV2VerificationError("accumulator closure mismatch")
    if summary.get("outputs", {}).get("provisional_first960_runs_sha256") != ledger_sha:
        raise GuardV2VerificationError("summary-ledger binding mismatch")
    support = summary.get("task_support", {}).get("provisional_first960", {})
    run_counts = as_counts(support.get("run_counts"), "run counts")
    endpoint_counts = as_counts(support.get("endpoint_counts"), "endpoint counts")
    pair_counts = as_counts(support.get("structural_pair_counts"), "pair counts")
    if set(run_counts) != set(endpoint_counts) or set(run_counts) != set(pair_counts):
        raise GuardV2VerificationError("task universe mismatch")
    runs = as_int(support.get("runs"), "runs", 1)
    endpoints = as_int(support.get("endpoints"), "endpoints", 1)
    pairs = as_int(support.get("structural_pairs"), "pairs", 1)
    tasks = as_int(support.get("tasks"), "tasks", 1)
    if (
        sum(run_counts.values()) != runs
        or sum(endpoint_counts.values()) != endpoints
        or sum(pair_counts.values()) != pairs
        or len(pair_counts) != tasks
    ):
        raise GuardV2VerificationError("task support totals mismatch")
    dominant_task, dominant_pairs = max(
        pair_counts.items(), key=lambda item: (item[1], item[0])
    )
    if not math.isclose(
        support.get("dominant_structural_pair_task_share"),
        dominant_pairs / pairs,
        rel_tol=0.0,
        abs_tol=1e-15,
    ):
        raise GuardV2VerificationError("dominant share mismatch")

    if ledger_path.is_symlink() or not ledger_path.is_file():
        raise GuardV2VerificationError("invalid ledger path")
    raw = ledger_path.read_bytes()
    if digest(raw) != ledger_sha:
        raise GuardV2VerificationError("ledger hash mismatch")
    try:
        lines = raw.decode("utf-8").splitlines()
    except UnicodeDecodeError as exc:
        raise GuardV2VerificationError("ledger is not UTF-8") from exc
    if not lines or any(not line for line in lines):
        raise GuardV2VerificationError("empty ledger row")
    ids: set[str] = set()
    order_keys: list[tuple[str, str, str]] = []
    ledger_runs: Counter[str] = Counter()
    ledger_endpoints: Counter[str] = Counter()
    for line in lines:
        try:
            row = json.loads(line)
        except json.JSONDecodeError as exc:
            raise GuardV2VerificationError("invalid ledger row") from exc
        if not isinstance(row, dict) or set(row) != ROW_KEYS:
            raise GuardV2VerificationError("ledger schema mismatch")
        run_id = row.get("run_id")
        task = row.get("task")
        if not isinstance(run_id, str) or not run_id or run_id in ids:
            raise GuardV2VerificationError("invalid or duplicate run_id")
        if not isinstance(task, str) or task not in run_counts:
            raise GuardV2VerificationError("invalid ledger task")
        if row.get("flow_status") != "scoreable":
            raise GuardV2VerificationError("ledger row is not scoreable")
        for key in ("drop_id", "generation_started_at_utc", "source_sha256"):
            if not isinstance(row.get(key), str) or not row[key]:
                raise GuardV2VerificationError(f"invalid ledger {key}")
        if len(row["source_sha256"]) != 64 or any(
            character not in "0123456789abcdef" for character in row["source_sha256"]
        ):
            raise GuardV2VerificationError("invalid ledger source_sha256")
        endpoint_count = as_int(row.get("endpoints"), "ledger endpoints", 1)
        ids.add(run_id)
        ledger_runs[task] += 1
        ledger_endpoints[task] += endpoint_count
        order_keys.append(
            (row["generation_started_at_utc"], row["source_sha256"], run_id)
        )
    if order_keys != sorted(order_keys):
        raise GuardV2VerificationError("ledger chronology is not sorted")
    if len(lines) != runs or dict(ledger_runs) != run_counts:
        raise GuardV2VerificationError("ledger run totals mismatch")
    if dict(ledger_endpoints) != endpoint_counts:
        raise GuardV2VerificationError("ledger endpoint totals mismatch")
    return {
        "runs": runs,
        "endpoints": endpoints,
        "pairs": pairs,
        "tasks": tasks,
        "pair_counts": pair_counts,
        "dominant_task": dominant_task,
        "dominant_pairs": dominant_pairs,
    }


def verify(
    gate_path: Path,
    gate_sha: str,
    summary_path: Path,
    summary_sha: str,
    ledger_path: Path,
    ledger_sha: str,
    snapshot: str,
    guard_path: Path,
    guard_sha: str,
) -> dict[str, Any]:
    _, gate = load_json(gate_path, gate_sha)
    guard_raw, guard = load_json(guard_path, guard_sha)
    source = structural_source(summary_path, summary_sha, ledger_path, ledger_sha, snapshot)
    if (
        gate.get("protocol") != "prospective_structural_gate_independent_verifier_v5"
        or gate.get("status") != "CONFIRMATORY_COHORT_COLLECTING"
        or gate.get("snapshot_sha256") != snapshot
    ):
        raise GuardV2VerificationError("structural gate identity mismatch")
    gate_sec = gate.get("security", {})
    if (
        gate_sec.get("label_vault_opened") is not False
        or gate_sec.get("outcome_files_opened") != []
        or gate_sec.get("scorer_prediction_files_opened") != []
    ):
        raise GuardV2VerificationError("structural gate security mismatch")
    if gate.get("inputs", {}).get("accumulator_summary_sha256") != summary_sha:
        raise GuardV2VerificationError("gate-summary binding mismatch")
    if gate.get("inputs", {}).get("provisional_runs_sha256") != ledger_sha:
        raise GuardV2VerificationError("gate-ledger binding mismatch")
    cross = gate.get("cross_checks_against_accumulator")
    if not isinstance(cross, dict) or not cross or not all(value is True for value in cross.values()):
        raise GuardV2VerificationError("gate cross-check mismatch")
    inv = gate.get("independent_inventory", {}).get("provisional_first960", {})
    for key, expected in {
        "runs": source["runs"],
        "endpoints": source["endpoints"],
        "structural_pairs": source["pairs"],
        "tasks": source["tasks"],
        "dominant_pair_task_count": source["dominant_pairs"],
    }.items():
        if inv.get(key) != expected:
            raise GuardV2VerificationError(f"gate inventory mismatch: {key}")
    if not math.isclose(
        inv.get("dominant_pair_task_share"),
        source["dominant_pairs"] / source["pairs"],
        rel_tol=0.0,
        abs_tol=1e-15,
    ):
        raise GuardV2VerificationError("gate dominant share mismatch")

    cap_value = gate.get("gate", {}).get("maximum_dominant_pair_task_share")
    if isinstance(cap_value, bool) or not isinstance(cap_value, (int, float)):
        raise GuardV2VerificationError("invalid cap")
    cap = Fraction(str(cap_value))
    if not 0 < cap < 1:
        raise GuardV2VerificationError("cap outside (0,1)")
    a, b = cap.numerator, cap.denominator
    counts_by_task = source["pair_counts"]
    total = source["pairs"]
    dominant = source["dominant_task"]
    dominant_count = source["dominant_pairs"]
    debt = max(0, b * dominant_count - a * total)
    minimum = -(-debt // a) if debt else 0
    budgets = sorted({minimum, 1000, 2000, 3000, 4000})
    allowance = []
    for nondominant in budgets:
        numerator = a * nondominant - debt
        allowance.append(
            {
                "future_nondominant_pairs": nondominant,
                "maximum_future_dominant_pairs": (
                    numerator // (b - a) if numerator >= 0 else None
                ),
            }
        )
    expected_current = {
        "pairs": total,
        "tasks": len(counts_by_task),
        "dominant_task": dominant,
        "dominant_pairs": dominant_count,
        "dominant_share": dominant_count / total,
        "maximum_share": float(cap),
        "gate_pass": debt == 0,
    }
    expected_envelope = {
        "cap_numerator": a,
        "cap_denominator": b,
        "imbalance_debt_numerator": debt,
        "minimum_future_nondominant_pairs_if_zero_future_dominant": minimum,
        "minimum_future_nondominant_pairs_formula": (
            f"ceil(({debt}+{b - a}*future_dominant_pairs)/{a})"
        ),
        "allowance_table": allowance,
    }
    expected_headroom = []
    for task, count in sorted(counts_by_task.items()):
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
    clearance_total = total + minimum
    per_task_cap = a * clearance_total // b
    expected_clearance = {
        "future_nondominant_pairs": minimum,
        "resulting_total_pairs": clearance_total,
        "maximum_pairs_per_task": per_task_cap,
        "nondominant_task_allocation_capacities": [
            {
                "task": task,
                "current_pairs": count,
                "maximum_future_pairs_at_debt_clearance_endpoint": max(
                    0, per_task_cap - count
                ),
            }
            for task, count in sorted(counts_by_task.items())
            if task != dominant
        ],
    }
    expected = {
        "protocol": "prospective_task_balance_accrual_guard_v2",
        "status": "STRUCTURAL_ONLY_TASK_BALANCE_ACCRUAL_GUARD_READY",
        "snapshot_sha256": snapshot,
        "inputs": {
            "structural_gate_sha256": gate_sha,
            "accumulator_summary_sha256": summary_sha,
            "provisional_first960_runs_sha256": ledger_sha,
        },
        "source_validation": {
            "snapshot_path_binding_exact": True,
            "summary_binds_ledger_sha256": True,
            "ledger_rows": source["runs"],
            "ledger_run_and_endpoint_counts_match_summary": True,
            "summary_task_counts_sum_exactly": True,
            "independent_structural_gate_totals_match": True,
            "independent_structural_gate_cross_checks_all_true": True,
        },
        "current": expected_current,
        "exact_integer_envelope": expected_envelope,
        "all_task_simultaneous_constraint": {
            "inequality": (
                f"For every task t: {b}*(current_t+future_t) <= "
                f"{a}*(current_total+sum_future_all_tasks)."
            ),
            "must_hold_for_every_task": True,
            "recompute_after_each_stable_snapshot": True,
            "dominant_debt_alone_is_not_sufficient": True,
        },
        "single_task_only_headroom": expected_headroom,
        "zero_future_dominant_debt_clearance_endpoint": expected_clearance,
        "operational_guard": {
            "immediate_action": (
                f"Temporarily route acquisition away from {dominant} until at least "
                f"{minimum} observed non-{dominant} sibling pairs accrue, "
                "while enforcing the all-task simultaneous constraint."
            ),
            "after_debt_is_cleared": (
                f"Each additional {dominant} pair requires at least "
                f"({b - a}/{a}) additional non-dominant pairs, with integer rounding "
                "applied to the cumulative envelope."
            ),
            "allocation_unit": "observed_canonical_sibling_pairs_not_raw_runs",
            "chronological_first_960_membership_rule_unchanged": True,
            "recompute_from_observed_pairs_not_expected_yield": True,
            "not_a_stopping_rule": True,
        },
        "access_attestation": {
            "labels_grades_outcomes_or_winner_orientation_read": False,
            "prediction_pair_files_opened": [],
            "prediction_values_read_or_aggregated": False,
            "raw_archive_payload_read": False,
            "accuracy_effect_or_search_utility_computed": False,
            "gpu_jobs": 0,
            "api_calls": 0,
            "model_fits": 0,
            "base_llm_updates": 0,
            "randomness_used": False,
        },
    }
    if guard != expected:
        raise GuardV2VerificationError("guard differs from independent reconstruction")
    return {
        "protocol": "independent_prospective_task_balance_accrual_guard_v2",
        "status": "INDEPENDENT_STRUCTURAL_ONLY_TASK_BALANCE_GUARD_PASS",
        "guard_sha256": digest(guard_raw),
        "snapshot_sha256": snapshot,
        "recomputed_current": expected_current,
        "recomputed_minimum_nondominant_pairs": minimum,
        "source_checks": {
            "snapshot_path_binding_exact": True,
            "summary_ledger_binding_exact": True,
            "ledger_counts_recomputed": True,
            "independent_structural_gate_cross_checked": True,
        },
        "access_attestation": {
            "outcomes_or_prediction_values_read": False,
            "raw_archive_payload_read": False,
            "gpu_or_api_calls": 0,
            "randomness_used": False,
        },
    }


def write_new(path: Path, value: dict[str, Any]) -> None:
    if path.exists() or not path.parent.is_dir() or path.parent.is_symlink():
        raise GuardV2VerificationError("output path is present or unsafe")
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
    parser.add_argument("--accumulator-summary", required=True, type=Path)
    parser.add_argument("--expect-accumulator-summary-sha256", required=True)
    parser.add_argument("--first960-ledger", required=True, type=Path)
    parser.add_argument("--expect-first960-ledger-sha256", required=True)
    parser.add_argument("--snapshot-sha256", required=True)
    parser.add_argument("--guard", required=True, type=Path)
    parser.add_argument("--expect-guard-sha256", required=True)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    try:
        receipt = verify(
            args.structural_gate,
            args.expect_structural_gate_sha256,
            args.accumulator_summary,
            args.expect_accumulator_summary_sha256,
            args.first960_ledger,
            args.expect_first960_ledger_sha256,
            args.snapshot_sha256,
            args.guard,
            args.expect_guard_sha256,
        )
        write_new(args.output.resolve(), receipt)
        print(json.dumps(receipt["recomputed_current"], sort_keys=True, separators=(",", ":")))
        return 0
    except (OSError, GuardV2VerificationError, ValueError, ZeroDivisionError, TypeError) as exc:
        print(f"TASK_BALANCE_GUARD_V2_VERIFY_ERROR: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
