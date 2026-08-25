from __future__ import annotations

import hashlib
import json
from pathlib import Path


ROOT = (
    Path(__file__).resolve().parents[2]
    / "phase1"
    / "results"
    / "prospective_0823_batch_postflight_20260825_6299865"
)
FINAL = "7cdaefcf2be7786442e1af1f4d0b4012edee708932f1fad31e174c0dcaf803a1"


def load(name: str) -> dict[str, object]:
    return json.loads((ROOT / name).read_text(encoding="utf-8"))


def sha256(name: str) -> str:
    return hashlib.sha256((ROOT / name).read_bytes()).hexdigest()


def test_formal_json_copies_keep_exact_hashes() -> None:
    expected = {
        "batch_summary.json": "011509acc09daa6856b30121312237deb13a7c928e67f8423cf874841c04f6c5",
        "delta_01_plant.json": "ecadd560aea9274e3dcf8f4c901884948361a6d5f58cddad9879f44056924a99",
        "delta_02_tensorflow.json": "38f48c20495e60a2558b7f9dd00c8a87cdf5e4c6f78c67bd0144fa1e6d6fa7dd",
        "delta_03_ranzcr.json": "1213e5e6bf19f781cdb58214ffe9b13b19427606a20dc9548b9fa157a37fbb68",
        "delta_04_alaska.json": "c60f899f119b0588a7b7acf415844443ba4b614ebd0a68db07b32fbcdb63de33",
        "structural_gate.json": "ca44845bc0f5feaf5de0e77ec658e4b0cca3f5a451b75b33bb4c63acfc1eccca",
    }
    assert {name: sha256(name) for name in expected} == expected


def test_batch_delta_equals_sum_of_accepted_archive_deltas() -> None:
    batch = load("batch_summary.json")
    deltas = [
        load("delta_01_plant.json"),
        load("delta_02_tensorflow.json"),
        load("delta_03_ranzcr.json"),
        load("delta_04_alaska.json"),
    ]
    assert batch["access_attestation"] == {
        "effect_metrics_computed": False,
        "outcomes_or_labels_read": False,
    }
    assert batch["current"]["snapshot_sha256"] == FINAL
    assert batch["current"]["closure_provided"] is False
    expected_current = {
        "endpoints": 10_196,
        "runs": 339,
        "structural_pairs": 2_635,
        "tasks": 30,
        "transactions": 78,
    }
    assert {field: batch["current"][field] for field in expected_current} == expected_current
    for field in ("endpoints", "runs", "structural_pairs", "tasks", "transactions"):
        assert batch["delta"][field] == sum(item["delta"][field] for item in deltas)
    assert batch["delta"] == {
        "endpoints": 204,
        "runs": 11,
        "structural_pairs": 46,
        "tasks": 1,
        "transactions": 4,
    }


def test_independent_gate_preserves_first960_and_security_boundaries() -> None:
    value = load("structural_gate.json")
    assert value["snapshot_sha256"] == FINAL
    assert value["status"] == "CONFIRMATORY_COHORT_COLLECTING"
    assert all(value["cross_checks_against_accumulator"].values())
    expected_inventory = {
        "endpoints": 10_196,
        "finite_decision_runs": 334,
        "runs": 339,
        "structural_pairs": 2_635,
        "tasks": 30,
    }
    inventory = value["independent_inventory"]["provisional_first960"]
    assert {field: inventory[field] for field in expected_inventory} == expected_inventory
    assert value["asset_quality"]["code_redundancy"] == {
        "cross_run_duplicate_code_groups": 0,
        "cross_task_duplicate_code_groups": 0,
        "duplicate_code_groups": 21,
        "duplicate_endpoints_beyond_first": 30,
        "exact_code_unique_fraction": 0.9970576696743821,
    }
    gate = value["gate"]
    assert gate["all_pass"] is False
    assert gate["remaining_confirmatory_runs"] == 621
    assert gate["vault_open_allowed"] is False
    assert gate["checks"] == {
        "accrual_closed_without_outcomes": False,
        "confirmatory_cohort_runs": False,
        "dominant_pair_task_share": False,
        "finite_decision_runs": True,
        "structural_pairs": True,
        "tasks": True,
    }
    assert value["security"]["label_vault_opened"] is False
    assert value["security"]["outcome_files_opened"] == []
    assert value["security"]["scorer_prediction_files_opened"] == []
