from __future__ import annotations

import hashlib
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
RESULT = ROOT / "phase1/results/task_balance_structural_only_v2_8579_20260826_1b9b836"
EXPECTED = {
    "guard.json": "2ffa91a5e10f17f31c1a79f51a69d2f4e2331353e9ac9cfab14c6c40352cd177",
    "guard_independent_verification.json": "62f5fa00ad4535c0e6e8706daf62f5408ac4fa407506f761b42840d1c115310c",
    "forward_validation.json": "fca979bb912c61bb14385638069a64aefcb8a7b9bc41cb77c260d07075ea0fb1",
    "forward_independent_verification.json": "00f8fec272705d0d5dfe072f2e0e59efa170913900249a506c829b693f102146",
    "remote_formal_SHA256SUMS": "b1405cd4a7ae844a1150119137349672d41963296f0899778a476d923b005135",
    "remote_postformal_SHA256SUMS": "8b90eab94987a01f981463ea3f821d5afa4e8b11271c4913c1b673f80ecb0166",
}


def _sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def test_result_payloads_are_the_exact_formal_bytes() -> None:
    for name, expected in EXPECTED.items():
        assert _sha(RESULT / name) == expected
    manifest = (RESULT / "SHA256SUMS").read_text(encoding="utf-8").splitlines()
    assert len(manifest) == 12
    for row in manifest:
        expected, relative = row.split("  ./", maxsplit=1)
        assert _sha(RESULT / relative) == expected


def test_structural_only_guard_reconstructs_the_frozen_baseline() -> None:
    guard = json.loads((RESULT / "guard.json").read_text(encoding="utf-8"))
    receipt = json.loads(
        (RESULT / "guard_independent_verification.json").read_text(encoding="utf-8")
    )
    assert guard["status"] == "STRUCTURAL_ONLY_TASK_BALANCE_ACCRUAL_GUARD_READY"
    assert guard["inputs"] == {
        "structural_gate_sha256": "ca44845bc0f5feaf5de0e77ec658e4b0cca3f5a451b75b33bb4c63acfc1eccca",
        "accumulator_summary_sha256": "ad3e8fe4180fd6c6f7fcea121ef0c51c0f292445d77368e2b3ab4dc9a56d4585",
        "provisional_first960_runs_sha256": "43b1f16d5326fad5de490a5b63bd8a6f3c454ad303c031cd1fb54e607919cf83",
    }
    assert "coverage_matrix" not in json.dumps(guard)
    assert guard["current"] == {
        "dominant_pairs": 823,
        "dominant_share": 0.31233396584440226,
        "dominant_task": "osic-pulmonary-fibrosis-progression",
        "gate_pass": False,
        "maximum_share": 0.25,
        "pairs": 2635,
        "tasks": 30,
    }
    assert guard["exact_integer_envelope"]["imbalance_debt_numerator"] == 657
    assert receipt["status"] == "INDEPENDENT_STRUCTURAL_ONLY_TASK_BALANCE_GUARD_PASS"
    assert receipt["guard_sha256"] == EXPECTED["guard.json"]


def test_forward_accounting_is_exact_but_cap_and_compliance_fail() -> None:
    result = json.loads((RESULT / "forward_validation.json").read_text(encoding="utf-8"))
    receipt = json.loads(
        (RESULT / "forward_independent_verification.json").read_text(encoding="utf-8")
    )
    assert result["status"] == "STRUCTURAL_ONLY_FORWARD_ACCOUNTING_EXACT"
    assert result["source_validation"]["prediction_matrix_input_used"] is False
    forward = result["frozen_guard_forward_result"]
    assert forward["future_dominant_pairs"] == 27
    assert forward["future_nondominant_pairs"] == 93
    assert forward["baseline_debt"] == 657
    assert forward["predicted_current_debt"] == 645
    assert forward["observed_current_debt"] == 645
    assert forward["debt_delta"] == -12
    assert forward["current_dominant_share"] == 0.308529945553539
    assert forward["current_cap_pass"] is False
    assert forward["immediate_action_adherence"] == (
        "DEFINITELY_NOT_ADHERED_BEFORE_DEBT_CLEARANCE"
    )
    assert receipt["status"] == "INDEPENDENT_STRUCTURAL_ONLY_TASK_BALANCE_FORWARD_PASS"
    assert receipt["forward_result_sha256"] == EXPECTED["forward_validation.json"]
    assert receipt["recomputed"]["current_pairs"] == 2755


def test_access_boundary_and_taint_propagation_are_explicit() -> None:
    result = json.loads((RESULT / "forward_validation.json").read_text(encoding="utf-8"))
    assert result["access_attestation"] == {
        "api_calls": 0,
        "base_llm_updates": 0,
        "gpu_jobs": 0,
        "labels_grades_outcomes_or_winner_orientation_read": False,
        "model_fits": 0,
        "prediction_pair_files_opened": [],
        "prediction_values_read_or_aggregated": False,
        "randomness_used": False,
        "raw_archive_payload_read": False,
    }
    registry = json.loads(
        (ROOT / "phase1/prediction_matrix_downstream_taint_registry_v1.json").read_text(
            encoding="utf-8"
        )
    )
    assert registry["replacement"]["formal_status"] == (
        "INDEPENDENT_STRUCTURAL_ONLY_TASK_BALANCE_FORWARD_PASS"
    )
    assert registry["replacement"]["v1_provenance_retroactively_repaired"] is False
    statuses = {row["path"]: row["status"] for row in registry["artifacts"]}
    assert statuses[
        "phase1/results/task_balance_accrual_guard_7cda_20260825/guard.json"
    ] == "HISTORICAL_WITHDRAWN_AS_STRICT_ZERO_PREDICTION_ACCESS_EVIDENCE"
    assert "1113 passed, 47 warnings" in (RESULT / "full_tests.txt").read_text(
        encoding="utf-8"
    )
