from __future__ import annotations

import hashlib
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
PROTOCOL_PATH = ROOT / "archive_granularity_retention_audit_v1.json"


def test_retention_protocol_is_result_before_and_hash_bound() -> None:
    protocol = json.loads(PROTOCOL_PATH.read_text())
    assert protocol["protocol"] == "archive_granularity_retention_audit_v1"
    assert protocol["frozen_before_retention_count_readout"] is True
    disclosure = protocol["disclosure_at_freeze"]
    assert disclosure["structural_rejected_competition_count_known"] == 6
    assert disclosure["structural_mixed_disposition_competition_count_known"] == 6
    for key in (
        "affected_competition_identities_read_or_emitted",
        "retained_accepted_archive_count_read",
        "retained_physical_run_count_read",
        "retained_eligible_run_count_read",
        "retained_eligible_endpoint_count_read",
        "affected_task_dominance_read",
    ):
        assert disclosure[key] is False

    inputs = protocol["inputs"]
    for path_key, hash_key in (
        ("archive_disposition_v2_result_path", "archive_disposition_v2_result_sha256"),
        (
            "archive_disposition_v2_verification_path",
            "archive_disposition_v2_verification_sha256",
        ),
    ):
        path = ROOT / inputs[path_key]
        assert hashlib.sha256(path.read_bytes()).hexdigest() == inputs[hash_key]


def test_retention_protocol_decision_and_access_boundaries() -> None:
    protocol = json.loads(PROTOCOL_PATH.read_text())
    strong = protocol["decision_rule"]["strong"]
    partial = protocol["decision_rule"]["partial"]
    assert strong == {
        "minimum_affected_competitions_with_eligible_support": 6,
        "minimum_retained_eligible_run_share": 0.1,
        "minimum_retained_eligible_endpoint_share": 0.1,
        "maximum_dominant_affected_task_eligible_run_share": 0.7,
        "maximum_dominant_affected_task_eligible_endpoint_share": 0.7,
        "status": "ARCHIVE_GRANULARITY_RETENTION_STRONG",
    }
    assert partial == {
        "minimum_affected_competitions_with_eligible_support": 4,
        "minimum_retained_eligible_run_share": 0.05,
        "minimum_retained_eligible_endpoint_share": 0.05,
        "maximum_dominant_affected_task_eligible_run_share": 0.85,
        "maximum_dominant_affected_task_eligible_endpoint_share": 0.85,
        "status": "ARCHIVE_GRANULARITY_RETENTION_PARTIAL",
    }
    assert protocol["rejection_taxonomy"]["aliases_enter_retention_estimand"] is False
    assert protocol["access_contract"] == {
        "observation_and_hash_bound_intake_metadata_only": True,
        "archive_payloads_opened": False,
        "labels_grades_outcomes_predictions_accuracy_or_utility_read": False,
        "candidate_identities_or_profiles_read": False,
        "archive_task_run_or_candidate_identity_values_emitted": False,
        "gpu_paid_api_model_fit_base_update": "0/0/0/0",
    }
