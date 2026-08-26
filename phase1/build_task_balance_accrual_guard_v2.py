#!/usr/bin/env python3
"""Build the task-balance guard from structural-only accumulator artifacts."""
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


PROTOCOL = "prospective_task_balance_accrual_guard_v2"
LEDGER_KEYS = {
    "drop_id",
    "endpoints",
    "flow_status",
    "generation_started_at_utc",
    "run_id",
    "source_sha256",
    "task",
}


class BalanceGuardV2Error(RuntimeError):
    pass


def sha256(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def read_object(path: Path, expected: str) -> tuple[bytes, dict[str, Any]]:
    if path.is_symlink() or not path.is_file():
        raise BalanceGuardV2Error("input is absent, non-regular, or symlinked")
    raw = path.read_bytes()
    if sha256(raw) != expected:
        raise BalanceGuardV2Error("input hash mismatch")
    try:
        value = json.loads(raw)
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise BalanceGuardV2Error("cannot parse JSON input") from exc
    if not isinstance(value, dict):
        raise BalanceGuardV2Error("JSON input is not an object")
    return raw, value


def integer(value: Any, label: str, minimum: int = 0) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value < minimum:
        raise BalanceGuardV2Error(f"invalid {label}")
    return value


def counts(value: Any, label: str) -> dict[str, int]:
    if not isinstance(value, dict) or not value:
        raise BalanceGuardV2Error(f"invalid {label}")
    result: dict[str, int] = {}
    for task, count in value.items():
        if not isinstance(task, str) or not task:
            raise BalanceGuardV2Error(f"invalid {label} task")
        result[task] = integer(count, f"{label} count")
    return result


def validate_accumulator(
    summary_path: Path,
    summary_sha: str,
    ledger_path: Path,
    ledger_sha: str,
    snapshot: str,
) -> dict[str, Any]:
    summary_dir = summary_path.absolute().parent
    if (
        len(snapshot) != 64
        or any(character not in "0123456789abcdef" for character in snapshot)
        or summary_dir.is_symlink()
        or summary_dir.parent.is_symlink()
        or summary_dir.name != "accumulator"
        or summary_dir.parent.name != snapshot
        or ledger_path.absolute().parent != summary_dir
        or summary_path.name != "summary.json"
        or ledger_path.name != "provisional_first960_runs.jsonl"
    ):
        raise BalanceGuardV2Error("accumulator source path is not snapshot-bound")
    _, summary = read_object(summary_path, summary_sha)
    if summary.get("protocol") != "prospective_accumulator_v1":
        raise BalanceGuardV2Error("accumulator protocol mismatch")
    if summary.get("status") != "PROSPECTIVE_COHORT_COLLECTING":
        raise BalanceGuardV2Error("accumulator status mismatch")
    security = summary.get("security")
    if (
        not isinstance(security, dict)
        or security.get("label_vault_opened") is not False
        or security.get("outcome_files_opened") != []
        or security.get("scorer_prediction_files_opened") != []
    ):
        raise BalanceGuardV2Error("accumulator security boundary failed")
    closure = summary.get("closure")
    if (
        not isinstance(closure, dict)
        or closure.get("provided") is not False
        or closure.get("all_scheduled_runs_uploaded") is not None
        or closure.get("outcomes_read") is not None
    ):
        raise BalanceGuardV2Error("unexpected closure state")
    outputs = summary.get("outputs")
    if (
        not isinstance(outputs, dict)
        or outputs.get("provisional_first960_runs_sha256") != ledger_sha
    ):
        raise BalanceGuardV2Error("summary does not bind the first-960 ledger")

    support = summary.get("task_support", {}).get("provisional_first960")
    if not isinstance(support, dict):
        raise BalanceGuardV2Error("first-960 task support missing")
    run_counts = counts(support.get("run_counts"), "run counts")
    endpoint_counts = counts(support.get("endpoint_counts"), "endpoint counts")
    pair_counts = counts(support.get("structural_pair_counts"), "pair counts")
    if not (set(run_counts) == set(endpoint_counts) == set(pair_counts)):
        raise BalanceGuardV2Error("task universes differ")
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
        raise BalanceGuardV2Error("task support totals do not sum")
    dominant_task, dominant_pairs = max(
        pair_counts.items(), key=lambda item: (item[1], item[0])
    )
    share = support.get("dominant_structural_pair_task_share")
    if (
        isinstance(share, bool)
        or not isinstance(share, (int, float))
        or not math.isclose(share, dominant_pairs / pairs, rel_tol=0.0, abs_tol=1e-15)
    ):
        raise BalanceGuardV2Error("dominant pair share mismatch")

    if ledger_path.is_symlink() or not ledger_path.is_file():
        raise BalanceGuardV2Error("ledger is absent, non-regular, or symlinked")
    ledger_raw = ledger_path.read_bytes()
    if sha256(ledger_raw) != ledger_sha:
        raise BalanceGuardV2Error("ledger hash mismatch")
    try:
        lines = ledger_raw.decode("utf-8").splitlines()
    except UnicodeDecodeError as exc:
        raise BalanceGuardV2Error("ledger is not UTF-8") from exc
    if not lines or any(not line for line in lines):
        raise BalanceGuardV2Error("ledger contains an empty row")
    seen: set[str] = set()
    order_keys: list[tuple[str, str, str]] = []
    ledger_runs: Counter[str] = Counter()
    ledger_endpoints: Counter[str] = Counter()
    for line in lines:
        try:
            row = json.loads(line)
        except json.JSONDecodeError as exc:
            raise BalanceGuardV2Error("cannot parse ledger row") from exc
        if not isinstance(row, dict) or set(row) != LEDGER_KEYS:
            raise BalanceGuardV2Error("ledger row schema mismatch")
        run_id = row.get("run_id")
        task = row.get("task")
        if not isinstance(run_id, str) or not run_id or run_id in seen:
            raise BalanceGuardV2Error("invalid or duplicate run_id")
        if not isinstance(task, str) or task not in run_counts:
            raise BalanceGuardV2Error("invalid ledger task")
        if row.get("flow_status") != "scoreable":
            raise BalanceGuardV2Error("unexpected ledger flow status")
        for key in ("drop_id", "generation_started_at_utc", "source_sha256"):
            if not isinstance(row.get(key), str) or not row[key]:
                raise BalanceGuardV2Error(f"invalid ledger {key}")
        if len(row["source_sha256"]) != 64 or any(
            character not in "0123456789abcdef" for character in row["source_sha256"]
        ):
            raise BalanceGuardV2Error("invalid ledger source_sha256")
        endpoint_count = integer(row.get("endpoints"), "ledger endpoints", 1)
        seen.add(run_id)
        ledger_runs[task] += 1
        ledger_endpoints[task] += endpoint_count
        order_keys.append(
            (row["generation_started_at_utc"], row["source_sha256"], run_id)
        )
    if order_keys != sorted(order_keys):
        raise BalanceGuardV2Error("ledger chronology is not sorted")
    if len(lines) != runs or dict(ledger_runs) != run_counts:
        raise BalanceGuardV2Error("ledger run counts mismatch")
    if dict(ledger_endpoints) != endpoint_counts:
        raise BalanceGuardV2Error("ledger endpoint counts mismatch")
    return {
        "runs": runs,
        "endpoints": endpoints,
        "pairs": pairs,
        "tasks": tasks,
        "run_counts": run_counts,
        "endpoint_counts": endpoint_counts,
        "pair_counts": pair_counts,
        "dominant_task": dominant_task,
        "dominant_pairs": dominant_pairs,
    }


def build_guard(
    structural_gate_path: Path,
    structural_gate_sha: str,
    accumulator_summary_path: Path,
    accumulator_summary_sha: str,
    first960_ledger_path: Path,
    first960_ledger_sha: str,
    snapshot: str,
) -> dict[str, Any]:
    _, gate = read_object(structural_gate_path, structural_gate_sha)
    source = validate_accumulator(
        accumulator_summary_path,
        accumulator_summary_sha,
        first960_ledger_path,
        first960_ledger_sha,
        snapshot,
    )
    if (
        gate.get("protocol") != "prospective_structural_gate_independent_verifier_v5"
        or gate.get("status") != "CONFIRMATORY_COHORT_COLLECTING"
        or gate.get("snapshot_sha256") != snapshot
    ):
        raise BalanceGuardV2Error("structural gate identity mismatch")
    gate_security = gate.get("security")
    if (
        not isinstance(gate_security, dict)
        or gate_security.get("label_vault_opened") is not False
        or gate_security.get("outcome_files_opened") != []
        or gate_security.get("scorer_prediction_files_opened") != []
    ):
        raise BalanceGuardV2Error("structural gate security boundary failed")
    gate_inputs = gate.get("inputs")
    if (
        not isinstance(gate_inputs, dict)
        or gate_inputs.get("accumulator_summary_sha256") != accumulator_summary_sha
        or gate_inputs.get("provisional_runs_sha256") != first960_ledger_sha
    ):
        raise BalanceGuardV2Error("structural gate source binding mismatch")
    cross_checks = gate.get("cross_checks_against_accumulator")
    if not isinstance(cross_checks, dict) or not cross_checks or not all(
        value is True for value in cross_checks.values()
    ):
        raise BalanceGuardV2Error("structural gate cross-check failed")
    inventory = gate.get("independent_inventory", {}).get("provisional_first960")
    if not isinstance(inventory, dict):
        raise BalanceGuardV2Error("structural gate inventory missing")
    expected_inventory = {
        "runs": source["runs"],
        "endpoints": source["endpoints"],
        "structural_pairs": source["pairs"],
        "tasks": source["tasks"],
        "dominant_pair_task_count": source["dominant_pairs"],
    }
    for key, expected in expected_inventory.items():
        if inventory.get(key) != expected:
            raise BalanceGuardV2Error(f"structural gate inventory mismatch: {key}")
    if not math.isclose(
        inventory.get("dominant_pair_task_share"),
        source["dominant_pairs"] / source["pairs"],
        rel_tol=0.0,
        abs_tol=1e-15,
    ):
        raise BalanceGuardV2Error("structural gate dominant share mismatch")
    gate_spec = gate.get("gate")
    cap_value = gate_spec.get("maximum_dominant_pair_task_share") if isinstance(gate_spec, dict) else None
    if isinstance(cap_value, bool) or not isinstance(cap_value, (int, float)):
        raise BalanceGuardV2Error("invalid dominant-task cap")
    cap = Fraction(str(cap_value))
    if not 0 < cap < 1:
        raise BalanceGuardV2Error("dominant-task cap outside (0,1)")
    a, b = cap.numerator, cap.denominator
    pair_counts = source["pair_counts"]
    total = source["pairs"]
    dominant_task = source["dominant_task"]
    dominant_pairs = source["dominant_pairs"]
    debt = max(0, b * dominant_pairs - a * total)
    minimum_nondominant = -(-debt // a) if debt else 0
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
    headroom = []
    for task, count in sorted(pair_counts.items()):
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
    return {
        "protocol": PROTOCOL,
        "status": "STRUCTURAL_ONLY_TASK_BALANCE_ACCRUAL_GUARD_READY",
        "snapshot_sha256": snapshot,
        "inputs": {
            "structural_gate_sha256": structural_gate_sha,
            "accumulator_summary_sha256": accumulator_summary_sha,
            "provisional_first960_runs_sha256": first960_ledger_sha,
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
        "current": {
            "pairs": total,
            "tasks": len(pair_counts),
            "dominant_task": dominant_task,
            "dominant_pairs": dominant_pairs,
            "dominant_share": dominant_pairs / total,
            "maximum_share": float(cap),
            "gate_pass": debt == 0,
        },
        "exact_integer_envelope": {
            "cap_numerator": a,
            "cap_denominator": b,
            "imbalance_debt_numerator": debt,
            "minimum_future_nondominant_pairs_if_zero_future_dominant": minimum_nondominant,
            "minimum_future_nondominant_pairs_formula": (
                f"ceil(({debt}+{b - a}*future_dominant_pairs)/{a})"
            ),
            "allowance_table": allowance_table,
        },
        "all_task_simultaneous_constraint": {
            "inequality": (
                f"For every task t: {b}*(current_t+future_t) <= "
                f"{a}*(current_total+sum_future_all_tasks)."
            ),
            "must_hold_for_every_task": True,
            "recompute_after_each_stable_snapshot": True,
            "dominant_debt_alone_is_not_sufficient": True,
        },
        "single_task_only_headroom": headroom,
        "zero_future_dominant_debt_clearance_endpoint": {
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
                for task, count in sorted(pair_counts.items())
                if task != dominant_task
            ],
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


def write_new(path: Path, value: dict[str, Any]) -> None:
    if path.exists() or not path.parent.is_dir() or path.parent.is_symlink():
        raise BalanceGuardV2Error("output path is present or unsafe")
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
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    try:
        value = build_guard(
            args.structural_gate,
            args.expect_structural_gate_sha256,
            args.accumulator_summary,
            args.expect_accumulator_summary_sha256,
            args.first960_ledger,
            args.expect_first960_ledger_sha256,
            args.snapshot_sha256,
        )
        write_new(args.output.resolve(), value)
        print(json.dumps(value["current"], sort_keys=True, separators=(",", ":")))
        return 0
    except (OSError, BalanceGuardV2Error, ValueError, ZeroDivisionError) as exc:
        print(f"TASK_BALANCE_GUARD_V2_ERROR: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
