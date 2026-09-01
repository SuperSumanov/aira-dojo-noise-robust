from __future__ import annotations

import hashlib
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
RELEASE = ROOT / "phase1/results/archive_rejection_support_census_20260902_7ad0164"


def load(name: str) -> dict[str, object]:
    return json.loads((RELEASE / name).read_text(encoding="utf-8"))


def digest(name: str) -> str:
    return hashlib.sha256((RELEASE / name).read_bytes()).hexdigest()


def test_release_hashes_and_independent_reconstruction_match() -> None:
    result = load("result.json")
    verification = load("independent_verification.json")
    summary = load("formal_summary.json")
    assert digest("result.json") == summary["result_sha256"] == verification["result_sha256"]
    assert digest("independent_verification.json") == summary[
        "independent_verification_sha256"
    ]
    assert verification["all_result_fields_equal"] is True
    assert verification["producer_imported"] is False
    assert verification["event_support_class_counts"] == result[
        "event_support_class_counts"
    ]
    assert verification["competition_support_class_counts"] == result[
        "competition_support_class_counts"
    ]


def test_release_counts_are_complete_and_match_frozen_summary() -> None:
    result = load("result.json")
    summary = load("formal_summary.json")
    events = result["event_support_class_counts"]
    competitions = result["competition_support_class_counts"]
    assert events == {
        "PRIOR_ANCHOR_ELIGIBLE_SUPPORT": 13,
        "CURRENT_WINDOW_ELIGIBLE_SUPPORT": 0,
        "ACCEPTED_ARCHIVE_ONLY_NO_ELIGIBLE_SUPPORT": 0,
        "NO_ACCEPTED_ARCHIVE_SUPPORT": 1,
    }
    assert sum(events.values()) == result["population"]["structural_rejected_archives"] == 14
    assert competitions == {
        "distinct_rejected_competitions": 7,
        "PRIOR_ANCHOR_ELIGIBLE_SUPPORT": 6,
        "CURRENT_WINDOW_ELIGIBLE_SUPPORT": 0,
        "ACCEPTED_ARCHIVE_ONLY_NO_ELIGIBLE_SUPPORT": 0,
        "NO_ACCEPTED_ARCHIVE_SUPPORT": 1,
    }
    assert summary["event_support_class_counts"]["prior_anchor_percent"] == 92.857143
    assert summary["competition_support_class_counts"]["prior_anchor_percent"] == 85.714286


def test_release_integrity_and_claim_boundaries_are_preserved() -> None:
    result = load("result.json")
    summary = load("formal_summary.json")
    assert all(result["integrity"].values())
    assert result["access_attestation"][
        "event_competition_archive_task_run_or_candidate_identity_values_emitted"
    ] is False
    assert result["access_attestation"][
        "labels_grades_outcomes_predictions_accuracy_or_utility_read"
    ] is False
    assert result["claim_boundary"]["partially_predisclosed_not_fully_blind_confirmation"]
    assert result["claim_boundary"]["estimates_causal_effect"] is False
    assert summary["failed_attempt_retained"]["scientific_readout_occurred"] is False
    assert summary["failed_attempt_retained"]["partial_output_reused"] is False


def test_release_contains_no_identity_bearing_schema_keys() -> None:
    forbidden = {
        "task",
        "run_id",
        "archive_relative_path",
        "competition",
        "archive_name",
        "drop_id",
        "intake_dir",
    }

    def visit(value: object) -> None:
        if isinstance(value, dict):
            assert forbidden.isdisjoint(value)
            for child in value.values():
                visit(child)
        elif isinstance(value, list):
            for child in value:
                visit(child)

    visit(load("result.json"))
    visit(load("independent_verification.json"))
