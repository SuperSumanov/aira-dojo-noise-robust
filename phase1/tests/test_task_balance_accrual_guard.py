from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pytest

from phase1.build_task_balance_accrual_guard import build_guard
from phase1.verify_task_balance_accrual_guard import (
    BalanceGuardVerificationError,
    verify,
)


ROOT = Path(__file__).resolve().parents[2]
RESULT = ROOT / "phase1/results/task_balance_accrual_guard_7cda_20260825"
GATE = ROOT / (
    "phase1/results/prospective_0823_batch_postflight_20260825_6299865/"
    "structural_gate.json"
)
COVERAGE = ROOT / "phase1/results/prediction_escrow_coverage_7cda_20260825_6299865/matrix.json"
GATE_SHA = "ca44845bc0f5feaf5de0e77ec658e4b0cca3f5a451b75b33bb4c63acfc1eccca"
COVERAGE_SHA = "be63fbe02c63c306bb488aa30416de7260e83e4701bdce3ed3f1d8843fd6f6b7"
GUARD_SHA = "fd87246bb3656befba27de5a98c88f808ca39e178e7322d27ae9536fe4a751b0"


def _sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def test_committed_guard_binds_the_exact_final_snapshot() -> None:
    assert _sha(GATE) == GATE_SHA
    assert _sha(COVERAGE) == COVERAGE_SHA
    assert _sha(RESULT / "guard.json") == GUARD_SHA
    receipt = verify(
        GATE,
        GATE_SHA,
        COVERAGE,
        COVERAGE_SHA,
        RESULT / "guard.json",
        GUARD_SHA,
    )
    assert receipt["status"] == "INDEPENDENT_TASK_BALANCE_ACCRUAL_GUARD_PASS"
    assert receipt["recomputed_minimum_nondominant_pairs"] == 657
    assert receipt["recomputed_current"]["dominant_pairs"] == 823
    assert receipt["recomputed_current"]["pairs"] == 2635


def test_guard_encodes_the_exact_one_to_three_future_ratio() -> None:
    guard = json.loads((RESULT / "guard.json").read_text(encoding="utf-8"))
    envelope = guard["exact_integer_envelope"]
    assert envelope["imbalance_debt_numerator"] == 657
    assert envelope["minimum_future_nondominant_pairs_formula"] == (
        "ceil((657+3*future_dominant_pairs)/1)"
    )
    assert envelope["allowance_table"][1] == {
        "future_nondominant_pairs": 1000,
        "maximum_future_dominant_pairs": 114,
    }
    assert guard["operational_guard"]["allocation_unit"] == (
        "observed_canonical_sibling_pairs_not_raw_runs"
    )
    assert guard["all_task_simultaneous_constraint"] == {
        "inequality": (
            "For every task t: 4*(current_t+future_t) <= "
            "1*(current_total+sum_future_all_tasks)."
        ),
        "must_hold_for_every_task": True,
        "recompute_after_each_stable_snapshot": True,
        "dominant_debt_alone_is_not_sufficient": True,
    }
    clearance = guard["zero_future_dominant_debt_clearance_endpoint"]
    assert clearance["resulting_total_pairs"] == 3292
    assert clearance["maximum_pairs_per_task"] == 823
    capacities = {
        row["task"]: row["maximum_future_pairs_at_debt_clearance_endpoint"]
        for row in clearance["nondominant_task_allocation_capacities"]
    }
    assert capacities["tensorflow-speech-recognition-challenge"] == 545
    assert capacities["tensorflow-speech-recognition-challenge"] < 657
    assert guard["operational_guard"]["not_a_stopping_rule"] is True


def test_builder_and_verifier_reject_a_mutated_balance_state(tmp_path: Path) -> None:
    snapshot = "a" * 64
    gate_path = tmp_path / "gate.json"
    coverage_path = tmp_path / "coverage.json"
    gate_path.write_text(
        json.dumps(
            {
                "snapshot_sha256": snapshot,
                "security": {"label_vault_opened": False, "outcome_files_opened": []},
                "gate": {"maximum_dominant_pair_task_share": 0.25},
            }
        )
        + "\n",
        encoding="utf-8",
    )
    coverage_path.write_text(
        json.dumps(
            {
                "snapshot_sha256": snapshot,
                "access_attestation": {
                    "labels_grades_outcomes_or_winner_orientation_read": False,
                    "prediction_values_aggregated": False,
                },
                "inventory": {
                    "wl": {
                        "pairs": 100,
                        "pairs_per_task": {"task-a": 30, "task-b": 70},
                        "dominant_task": "task-b",
                        "dominant_task_pairs": 70,
                    }
                },
            }
        )
        + "\n",
        encoding="utf-8",
    )
    gate_sha = _sha(gate_path)
    coverage_sha = _sha(coverage_path)
    guard = build_guard(gate_path, gate_sha, coverage_path, coverage_sha)
    assert guard["exact_integer_envelope"][
        "minimum_future_nondominant_pairs_if_zero_future_dominant"
    ] == 180
    guard_path = tmp_path / "guard.json"
    guard_path.write_text(json.dumps(guard) + "\n", encoding="utf-8")
    guard_sha = _sha(guard_path)
    verify(gate_path, gate_sha, coverage_path, coverage_sha, guard_path, guard_sha)

    guard["current"]["dominant_pairs"] = 69
    bad_path = tmp_path / "bad_guard.json"
    bad_path.write_text(json.dumps(guard) + "\n", encoding="utf-8")
    with pytest.raises(BalanceGuardVerificationError, match="current balance state"):
        verify(
            gate_path,
            gate_sha,
            coverage_path,
            coverage_sha,
            bad_path,
            _sha(bad_path),
        )


def test_independent_verifier_rejects_nonblind_source_attestation(
    tmp_path: Path,
) -> None:
    gate = json.loads(GATE.read_text(encoding="utf-8"))
    coverage = json.loads(COVERAGE.read_text(encoding="utf-8"))
    gate_path = tmp_path / "gate.json"
    coverage_path = tmp_path / "coverage.json"
    gate_path.write_text(json.dumps(gate) + "\n", encoding="utf-8")
    coverage["access_attestation"][
        "labels_grades_outcomes_or_winner_orientation_read"
    ] = True
    coverage_path.write_text(json.dumps(coverage) + "\n", encoding="utf-8")
    gate_sha = _sha(gate_path)
    coverage_sha = _sha(coverage_path)

    guard = json.loads((RESULT / "guard.json").read_text(encoding="utf-8"))
    guard["inputs"] = {
        "structural_gate_sha256": gate_sha,
        "coverage_matrix_sha256": coverage_sha,
    }
    guard_path = tmp_path / "guard.json"
    guard_path.write_text(json.dumps(guard) + "\n", encoding="utf-8")
    with pytest.raises(BalanceGuardVerificationError, match="not outcome-blind"):
        verify(
            gate_path,
            gate_sha,
            coverage_path,
            coverage_sha,
            guard_path,
            _sha(guard_path),
        )
