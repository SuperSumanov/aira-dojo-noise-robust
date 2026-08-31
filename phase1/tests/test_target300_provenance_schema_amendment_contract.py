from __future__ import annotations

import hashlib
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
FAILURE_PATH = ROOT / "target300_v1_schema_failure_safe_receipt_20260831.json"
AMENDMENT_PATH = ROOT / "target300_provenance_schema_amendment_v2.json"
FAILURE_SHA = "aef8d5a8a013610f0276b0fc96480e238133e15f28d14f256f47aabb00f5da42"
AMENDMENT_SHA = "ef6de30a9ba3cf9b2f893523765baa08b4fcf1c6f87ee4539e4ef594eb2d6df1"


def _sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def test_v1_failure_is_retained_before_any_scientific_readout() -> None:
    value = json.loads(FAILURE_PATH.read_text(encoding="utf-8"))
    assert value["status"] == "TARGET300_V1_SCHEMA_DRIFT_FAIL_CLOSED"
    execution = value["v1_execution"]
    assert execution["formal_rc"] == 2
    assert execution["focused_tests"]["passed"] == 12
    assert execution["full_tests"]["passed"] == 965
    assert execution["producer_b_started"] is False
    assert execution["independent_verifier_started"] is False
    assert execution["first_closed_anchor_written"] is False
    assert execution["v1_retry_permitted"] is False
    assert all(flag is False for flag in value["blindness"].values())
    assert _sha(FAILURE_PATH) == FAILURE_SHA


def test_key_only_audit_supports_exactly_one_forward_compatible_field() -> None:
    value = json.loads(FAILURE_PATH.read_text(encoding="utf-8"))
    audit = value["key_only_schema_audit"]
    assert audit["provenance_rows"] == 520
    assert audit["legacy_exact_rows"] == 495
    assert audit["optional_source_rows"] == 25
    assert audit["legacy_exact_rows"] + audit["optional_source_rows"] == audit["provenance_rows"]
    assert audit["optional_keys"] == ["competition_id_source"]
    assert audit["rows_with_missing_required_keys"] == 0
    assert audit["rows_with_other_extra_keys"] == 0
    assert audit["values_printed"] is False


def test_v2_changes_only_the_provenance_input_schema_contract() -> None:
    value = json.loads(AMENDMENT_PATH.read_text(encoding="utf-8"))
    assert value["protocol"] == "target300_provenance_schema_amendment_v2"
    assert value["status"] == "FROZEN_AFTER_V1_STRUCTURAL_FAILURE_BEFORE_SCIENTIFIC_READOUT"
    schema = value["schema_amendment"]
    assert schema["sole_optional_key"] == "competition_id_source"
    assert schema["allowed_optional_values"] == [
        "archive_consensus_fallback",
        "explicit_journal",
    ]
    assert schema["arbitrary_extra_keys_rejected"] is True
    assert schema["missing_required_keys_rejected"] is True
    assert schema["invalid_optional_values_rejected"] is True
    assert schema["optional_key_dropped_from_cohort_identity_rows"] is True
    for unchanged in (
        "archive_order_changed",
        "run_deduplication_changed",
        "eligibility_logic_changed",
        "target_or_boundary_rule_changed",
        "label_score_outcome_or_prediction_access_added",
    ):
        assert schema[unchanged] is False
    assert _sha(AMENDMENT_PATH) == AMENDMENT_SHA


def test_v2_is_bound_to_the_failed_v1_candidate_and_cannot_reselect() -> None:
    value = json.loads(AMENDMENT_PATH.read_text(encoding="utf-8"))
    assert value["failure_binding"]["v1_must_not_be_retried"] is True
    candidate = value["fixed_candidate"]
    assert candidate["latest_snapshot_sha256"].startswith("30945550")
    assert candidate["selected_by_v1_first_stable_successor_rule"] is True
    assert candidate["alternate_snapshot_selection_allowed"] is False
    assert value["previous_prefix"]["selected_runs"] == 193
    assert value["previous_prefix"]["selected_archives"] == 60
    assert value["previous_prefix"]["must_survive_as_exact_prefix"] is True
    assert value["required_validation"]["v2_failure_retained_without_retry"] is True
    assert value["scope"]["gpu_jobs_authorized"] == 0
    assert value["scope"]["paid_api_calls_authorized"] == 0
    assert value["scope"]["model_fits_authorized"] == 0
    assert value["scope"]["truth_support_replay_or_effect_authorized"] is False
