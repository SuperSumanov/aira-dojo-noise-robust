from __future__ import annotations

import hashlib
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
RECEIPT = ROOT / "target300_schema_v2_safe_receipt_20260831.json"
VERIFIER = ROOT / "scripts" / "verify_target300_schema_v2_safe_result_20260831.sh"
RECEIPT_SHA = "41c23fa4ed50476969fdd4300b53e43cfcec288cfcdce10f8ddca9f6b8acd314"
VERIFIER_SHA = "b2b7a1a8cf869d3ee4b8c8a963df4281f32a6ac7189ca6d069ee0a1753de9b83"


def _sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def test_formal_result_is_pass_collecting_not_closed() -> None:
    value = json.loads(RECEIPT.read_text(encoding="utf-8"))
    assert value["status"] == "TARGET300_SCHEMA_V2_PASS_COLLECTING_TRUTH_UNREAD"
    assert value["execution"]["formal_rc"] == 0
    assert value["execution"]["v1_failure_retained"] is True
    assert value["execution"]["v1_retried"] is False
    assert value["execution"]["alternate_candidate_used"] is False
    assert value["execution"]["first_closed_anchor_written"] is False
    assert value["formal_validation"]["cohort_status"] == "FUTURE_COHORT_COLLECTING"
    assert value["formal_validation"]["verifier_status"] == "PASS_COLLECTING_TRUTH_UNREAD"
    assert value["claim_boundary"]["target300_identity_closed"] is False


def test_inventory_partition_and_previous_deltas_are_exact() -> None:
    value = json.loads(RECEIPT.read_text(encoding="utf-8"))
    inventory = value["inventory"]
    closure = value["closure"]
    assert inventory["selected_physical_runs"] == 219
    assert closure["remaining_runs_to_target"] == 300 - 219 == 81
    assert inventory["selected_archives"] + inventory["structurally_rejected_in_settled_prefix"] == 83
    assert inventory["settled_archive_prefix"] == inventory["observed_future_archives"] == 83
    assert inventory["pending_head_present"] is False
    assert closure["new_selected_runs_since_previous"] == 219 - 193 == 26
    assert closure["new_selected_archives_since_previous"] == 69 - 60 == 9
    assert closure["new_selected_tasks_since_previous"] == 31 - 30 == 1
    assert closure["previous_exact_prefix_survived"] is True


def test_reproducibility_and_blindness_gates_all_pass() -> None:
    value = json.loads(RECEIPT.read_text(encoding="utf-8"))
    formal = value["formal_validation"]
    assert formal["focused_tests_passed"] == 14
    assert formal["full_tests_passed"] == 1877
    assert formal["producer_replicas_byte_identical"] is True
    assert formal["independent_verifier_replicas_byte_identical"] is True
    assert formal["independent_verifier_imported_producer"] is False
    assert formal["formal_tree_read_only"] is True
    assert formal["formal_manifest_verified"] is True
    security = value["security"]
    assert security["forbidden_open_count"] == 0
    assert security["filename_secret_scan_count"] == 0
    assert security["content_secret_scan_count"] == 0
    assert all(
        security[key] is False
        for key in (
            "label_vault_opened",
            "score_or_outcome_opened",
            "prediction_values_opened",
            "accuracy_or_utility_computed",
            "candidate_identifiers_or_task_profile_read",
            "private_selection_read",
        )
    )


def test_safe_receipt_and_whitelist_verifier_are_hash_bound() -> None:
    value = json.loads(RECEIPT.read_text(encoding="utf-8"))
    assert _sha(RECEIPT) == RECEIPT_SHA
    assert _sha(VERIFIER) == VERIFIER_SHA
    assert value["hashes"]["safe_verifier_sha256"] == VERIFIER_SHA
    script = VERIFIER.read_text(encoding="utf-8")
    assert "per_task_selected_runs" not in script
    assert "cohort_runs.jsonl" not in script
    assert "cohort_archives.jsonl" not in script
    assert "OUTCOMES_READ=false" in script
    assert "IDENTITIES_READ=false" in script
