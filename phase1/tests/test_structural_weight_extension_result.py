from __future__ import annotations

import hashlib
import json
from pathlib import Path


ROOT = (
    Path(__file__).parents[1]
    / "results"
    / "structural_weight_extension_ad0b_20260827_2dbd964"
)
SNAPSHOT = "ad0b624d636cb5e89f94d8887a7abe99f7b9ef6ce77bbde7da704b0275dedb0e"
SOURCE_COMMIT = "7b9ddf64efcbf75107e3bdc7846d7467454ddc90"


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def read_json(name: str):
    return json.loads((ROOT / name).read_text(encoding="utf-8"))


def test_formal_bindings_and_independent_receipt() -> None:
    summary = read_json("formal_summary.json")
    receipt = read_json("independent_verification.json")
    assert summary["status"] == "FORMAL_STRUCTURAL_WEIGHT_EXTENSION_PASS"
    assert summary["source_commit"] == SOURCE_COMMIT
    assert summary["snapshot_sha256"] == SNAPSHOT
    assert summary["outputs"] == {
        "headline_metrics_sha256": digest(ROOT / "headline_metrics.json"),
        "independent_verification_sha256": digest(ROOT / "independent_verification.json"),
        "trajectory_sha256": digest(ROOT / "trajectory.json"),
    }
    assert receipt["status"] == "INDEPENDENT_STRUCTURAL_WEIGHT_EXTENSION_PASS"
    assert receipt["snapshot_sha256"] == SNAPSHOT
    assert receipt["recomputed_key_findings"]["runs"] == 404
    assert receipt["recomputed_key_findings"]["pairs"] == 2884


def test_preregistered_gates_are_not_rescued() -> None:
    metrics = read_json("headline_metrics.json")
    assert metrics["claim_gates"] == {
        "E1_extension_temporal_persistence": True,
        "E2_no_single_drop_artifact": False,
        "E3_single_task_robustness": False,
        "E4_yield_is_primary_mechanism": False,
        "E5_reconstructed_version_direction_consistency": True,
    }
    assert metrics["all_gates_passed"] is False
    assert metrics["maximum_positive_single_drop_attribution"] == 1.0617531614480789
    assert metrics["task_deletion"] == {
        "dominant_task": "osic-pulmonary-fibrosis-progression",
        "dominant_task_deletion_retained": False,
        "fraction": 0.967741935483871,
        "retained": 30,
        "total": 31,
    }
    assert metrics["yield_mechanism"] == {
        "pair_hhi_fraction": 0.5991375958702558,
        "run_to_pair_tv_fraction": 0.44105064109821923,
    }
    trajectory = read_json("trajectory.json")
    worst = max(
        trajectory["leave_one_added_drop_out"],
        key=lambda row: row["attribution_fraction_of_positive_pair_hhi_delta"],
    )
    assert worst["drop_id"] == (
        "0820-osic-pulmonary-fibrosis-progression-8seeds-4c1127356fce21d7"
    )
    assert worst["removed_added_runs"] == 5
    assert worst["pair_hhi_delta_vs_first240"] == -0.002578347695087399
    failed_tasks = [
        row for row in trajectory["leave_one_task_out"] if not row["inversion_retained"]
    ]
    assert failed_tasks == [
        {
            "inversion_retained": False,
            "is_current_pair_dominant_task": True,
            "pair_hhi_delta": -0.0018797549643278927,
            "removed_task": "osic-pulmonary-fibrosis-progression",
            "run_hhi_delta": -0.009590476011648245,
        }
    ]


def test_blindness_paths_tests_and_complete_trajectory() -> None:
    trajectory = read_json("trajectory.json")
    audit = read_json("exact_path_audit.json")
    assert len(trajectory["full_prefix_trajectory"]) == 404
    assert trajectory["known_before_protocol_freeze"][
        "current_hhi_trajectory_decomposition_and_deletions_known"
    ] is False
    assert trajectory["interpretation_contract"]["all_gates_passed"] is False
    assert trajectory["interpretation_contract"]["search_utility_claim"] is False
    assert trajectory["security"] == {
        "api_calls": 0,
        "base_llm_updates": 0,
        "eligible_blind_manifest_opened": False,
        "gpu_calls": 0,
        "label_vault_opened": False,
        "model_fits": 0,
        "opened_basenames": [
            "SHA256SUMS",
            "summary.json",
            "provisional_first960_runs.jsonl",
            "intake_registry.jsonl",
            "source_provenance.json",
            "eligible_structural_pairs.jsonl",
        ],
        "outcome_grade_winner_orientation_opened": False,
        "raw_archive_or_journal_bytes_opened": False,
        "score_or_prediction_values_opened": False,
    }
    assert audit["status"] == "EXACT_PATH_AUDIT_PASS"
    assert audit["forbidden_open_hits"] == 0
    assert "12 passed in 2.43s" in (ROOT / "focused_tests.txt").read_text(encoding="utf-8")
    assert "1225 passed, 47 warnings in 80.95s" in (
        ROOT / "full_tests.txt"
    ).read_text(encoding="utf-8")
    credential = (ROOT / "credential_scan.txt").read_text(encoding="utf-8")
    assert "commit_filename_secret_hits=0" in credential
    assert "commit_blob_secret_hits=0" in credential
    assert "result_content_secret_hits=0" in credential


def test_checked_in_manifest() -> None:
    lines = (ROOT / "SHA256SUMS").read_text(encoding="utf-8").splitlines()
    entries = {}
    for line in lines:
        checksum, relative = line.split(maxsplit=1)
        entries[relative.lstrip("* ").replace("\\", "/")] = checksum
    expected_files = {
        path.name for path in ROOT.iterdir() if path.is_file() and path.name != "SHA256SUMS"
    }
    assert set(entries) == expected_files
    for name, expected in entries.items():
        assert digest(ROOT / name) == expected
