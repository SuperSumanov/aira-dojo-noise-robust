from __future__ import annotations

import csv
import hashlib
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
PACKAGE = ROOT / "phase1/results/endpoint_budget_influence_bounded_task_reweight_20260830_d768cb2"


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def read(name: str) -> dict:
    return json.loads((PACKAGE / name).read_text(encoding="utf-8"))


def test_public_package_has_exact_members() -> None:
    assert {path.name for path in PACKAGE.iterdir()} == {
        "README.md",
        "focused_tests.txt",
        "formal_manifest.txt",
        "formal_receipt.json",
        "full_tests.txt",
        "integrity_receipt.json",
        "postflight_focused_tests.txt",
        "postflight_manifest.txt",
        "preflight_13.txt",
        "runs.csv",
        "summary.json",
        "verifier.json",
    }


def test_public_artifact_hashes_match_formal_receipt() -> None:
    receipt = read("formal_receipt.json")
    for name, expected in receipt["public_artifacts"].items():
        assert sha256(PACKAGE / name) == expected
    assert (PACKAGE / "formal_manifest.txt").read_text().strip() == receipt["formal_manifest_sha256"]
    assert (PACKAGE / "postflight_manifest.txt").read_text().strip() == receipt["postflight_manifest_sha256"]


def test_classification_and_gate_count_are_exact() -> None:
    summary = read("summary.json")
    receipt = read("formal_receipt.json")
    expected = "HISTORICAL_SINGLE_FOLD_INFLUENCE_BOUNDED_TASK_REWEIGHT_DOES_NOT_ADVANCE"
    assert summary["classification"] == receipt["classification"] == expected
    assert sum(summary["advancement_gates"].values()) == receipt["advancement_gates"]["passed"] == 5
    assert len(summary["advancement_gates"]) == receipt["advancement_gates"]["total"] == 7
    assert receipt["advancement_gates"]["failed"] == 2


def test_exact_failed_gates_are_preserved() -> None:
    gates = read("summary.json")["advancement_gates"]
    assert {name for name, passed in gates.items() if not passed} == {
        "terminal_log_loss_and_brier_delta_new_minus_old_yield_nonpositive",
        "terminal_pair_micro_task_macro_and_drop_dominant_accuracy_delta_new_minus_uniform_nonnegative",
    }


def test_model_rows_and_csv_are_exact() -> None:
    summary = read("summary.json")
    with (PACKAGE / "runs.csv").open(encoding="utf-8", newline="") as handle:
        rows = list(csv.DictReader(handle))
    assert len(rows) == len(summary["model_rows"]) == 2
    for csv_row, summary_row in zip(rows, summary["model_rows"]):
        assert set(csv_row) == set(summary_row)
        assert all(csv_row[key] == str(value) for key, value in summary_row.items())


def test_independent_verifier_and_integrity_scope() -> None:
    summary = read("summary.json")
    verifier = read("verifier.json")
    integrity = read("integrity_receipt.json")
    assert verifier["all_aggregate_fields_equal"] is True
    assert verifier["classification"] == summary["classification"]
    assert verifier["summary_sha256"] == sha256(PACKAGE / "summary.json")
    assert verifier["runs_csv_sha256"] == sha256(PACKAGE / "runs.csv")
    assert verifier["model_refits"] == 0
    assert verifier["prospective_values_read"] is False
    assert verifier["senior_test_rows_used"] is False
    assert integrity["formal_manifest_failures"] == 0
    assert integrity["formal_verifier_a_b_byte_exact"] is True
    assert integrity["fresh_postflight_verifier_byte_exact_to_formal"] is True
    assert set(integrity["scanner_bytes"].values()) == {0}
    assert summary["scope"]["prospective_first960_target300_target522_values_used"] is False
    assert summary["population"]["senior_test_rows_used"] is False


def test_all_preflight_lines_and_test_receipts_are_present() -> None:
    preflight = (PACKAGE / "preflight_13.txt").read_text(encoding="utf-8").splitlines()
    assert len(preflight) == 13
    assert all(line.endswith("PASS") for line in preflight)
    assert "37 passed" in (PACKAGE / "focused_tests.txt").read_text(encoding="utf-8")
    assert "1663 passed" in (PACKAGE / "full_tests.txt").read_text(encoding="utf-8")
    assert "11 passed" in (PACKAGE / "postflight_focused_tests.txt").read_text(encoding="utf-8")
