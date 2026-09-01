from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pytest

from phase1.audit_archive_rejection_support_census import build_result as build_census
from phase1.audit_archive_rejection_support_floor import (
    METRICS,
    SupportFloorError,
    build_result,
)
from phase1.tests.test_archive_rejection_support_census import (
    file_sha,
    fixture as census_fixture,
    write_json,
)
from phase1.verify_archive_rejection_support_census import verify as verify_census
from phase1.verify_archive_rejection_support_floor import (
    SupportFloorVerificationError,
    verify,
)


ROOT = Path(__file__).resolve().parents[2]
PRIOR = "PRIOR_ANCHOR_ELIGIBLE_SUPPORT"
WINDOW = "CURRENT_WINDOW_ELIGIBLE_SUPPORT"
ARCHIVE_ONLY = "ACCEPTED_ARCHIVE_ONLY_NO_ELIGIBLE_SUPPORT"
NO_SUPPORT = "NO_ACCEPTED_ARCHIVE_SUPPORT"


def make_floor_case(tmp_path: Path) -> dict[str, object]:
    case = census_fixture(tmp_path)
    census_result = build_census(
        case["protocol"], case["observations"], case["state"]
    )
    census_result_path = case["root"] / "census_result.json"
    write_json(census_result_path, census_result)
    census_receipt = verify_census(
        case["protocol"],
        case["observations"],
        census_result_path,
        case["state"],
    )
    census_receipt_path = case["root"] / "census_verification.json"
    write_json(census_receipt_path, census_receipt)

    census_protocol = json.loads(case["protocol"].read_text(encoding="utf-8"))
    census_inputs = census_protocol["inputs"]
    floor_protocol = case["root"] / "floor_protocol.json"
    write_json(
        floor_protocol,
        {
            "protocol": "archive_rejection_support_floor_v1",
            "frozen_before_distinct_competition_floor_readout": True,
            "post_hoc_after_aggregate_census_readout": True,
            "inputs": {
                "prior_snapshot_sha256": census_inputs["prior_snapshot_sha256"],
                "current_snapshot_sha256": census_inputs["current_snapshot_sha256"],
                "current_observations_sha256": census_inputs[
                    "current_observations_sha256"
                ],
                "current_observations_bytes": census_inputs[
                    "current_observations_bytes"
                ],
                "prior_transactions_sha256": census_inputs[
                    "prior_transactions_sha256"
                ],
                "prior_transaction_lines": census_inputs[
                    "prior_transaction_lines"
                ],
                "current_transactions_sha256": census_inputs[
                    "current_transactions_sha256"
                ],
                "current_transaction_lines": census_inputs[
                    "current_transaction_lines"
                ],
                "current_window_transaction_lines": census_inputs[
                    "current_window_transaction_lines"
                ],
                "census_result_path": census_result_path.relative_to(
                    case["root"]
                ).as_posix(),
                "census_result_sha256": file_sha(census_result_path),
                "census_verification_path": census_receipt_path.relative_to(
                    case["root"]
                ).as_posix(),
                "census_verification_sha256": file_sha(census_receipt_path),
            },
            "known_before_floor_readout": {
                "population": {
                    key: census_result["population"][key]
                    for key in (
                        "observed_archives",
                        "baseline_archives",
                        "accepted_archives",
                        "structural_rejected_archives",
                        "alias_quarantined_archives",
                        "physical_runs",
                        "eligible_runs",
                        "eligible_endpoints",
                        "eligible_structural_pairs",
                        "eligible_tasks",
                    )
                },
                "census_event_support_class_counts": census_result[
                    "event_support_class_counts"
                ],
                "census_competition_support_class_counts": census_result[
                    "competition_support_class_counts"
                ],
                "census_event_weighted_support_quantities": census_result[
                    "event_weighted_support_quantity_aggregates"
                ],
            },
            "unknown_at_freeze": {
                "distinct_competition_weighted_support_totals": False,
                "per_class_metric_minimum_median_maximum": False,
                "number_of_prior_supported_competitions_with_exactly_one_archive_or_run": False,
                "minimum_prior_eligible_run_fraction": False,
                "minimum_prior_endpoints_per_eligible_run": False,
                "maximum_prior_support_concentration_share": False,
                "number_of_competitions_receiving_any_current_window_increment": False,
            },
            "estimand": {
                "metrics": list(METRICS),
                "full_census_not_sampling_inference": True,
                "no_binary_success_threshold": True,
            },
            "access_contract": {
                "observation_and_hash_bound_intake_metadata_only": True,
                "rejection_registry_contents_opened": False,
                "archive_payloads_opened": False,
                "labels_grades_outcomes_predictions_accuracy_or_utility_read": False,
                "candidate_identities_or_profiles_read": False,
                "identity_values_emitted": False,
                "gpu_paid_api_model_fit_base_update": "0/0/0/0",
            },
        },
    )
    return {**case, "floor_protocol": floor_protocol}


def test_producer_matches_nonimporting_verifier(tmp_path: Path) -> None:
    case = make_floor_case(tmp_path)
    result = build_result(
        case["floor_protocol"], case["observations"], case["state"]
    )
    result_path = case["root"] / "floor_result.json"
    write_json(result_path, result)
    receipt = verify(
        case["floor_protocol"],
        case["observations"],
        result_path,
        case["state"],
    )
    assert receipt["status"] == (
        "INDEPENDENT_ARCHIVE_REJECTION_SUPPORT_FLOOR_PASS_POST_HOC"
    )
    assert receipt["all_result_fields_equal"] is True
    assert receipt["producer_imported"] is False


def test_exact_synthetic_support_floor(tmp_path: Path) -> None:
    case = make_floor_case(tmp_path)
    result = build_result(
        case["floor_protocol"], case["observations"], case["state"]
    )
    assert result["competition_support_class_counts"] == {
        "distinct_rejected_competitions": 4,
        PRIOR: 1,
        WINDOW: 1,
        ARCHIVE_ONLY: 1,
        NO_SUPPORT: 1,
    }
    assert result["distinct_competition_support_totals"] == {
        "prior_prefix": {
            "accepted_archives": 1,
            "physical_runs": 1,
            "eligible_runs": 1,
            "eligible_endpoints": 2,
        },
        "current_window": {
            "accepted_archives": 2,
            "physical_runs": 2,
            "eligible_runs": 1,
            "eligible_endpoints": 2,
        },
        "current_total": {
            "accepted_archives": 3,
            "physical_runs": 3,
            "eligible_runs": 2,
            "eligible_endpoints": 4,
        },
    }
    floor = result["prior_supported_competition_floor"]
    assert floor["competition_count"] == 1
    assert floor["competitions_with_exactly_one_prior_accepted_archive"] == 1
    assert floor["competitions_with_exactly_one_prior_physical_run"] == 1
    assert floor["competitions_with_exactly_one_prior_eligible_run"] == 1
    assert floor["minimum_prior_eligible_run_fraction"]["numerator"] == 1
    assert floor["minimum_prior_eligible_run_fraction"]["denominator"] == 1
    assert floor["minimum_prior_endpoints_per_eligible_run"]["numerator"] == 2
    assert floor["minimum_prior_endpoints_per_eligible_run"]["denominator"] == 1
    assert result["current_window_competition_counts_with_positive_increment"] == {
        "accepted_archives": 2,
        "physical_runs": 2,
        "eligible_runs": 1,
        "eligible_endpoints": 1,
    }


def test_support_floor_emits_no_identity_values(tmp_path: Path) -> None:
    case = make_floor_case(tmp_path)
    result = build_result(
        case["floor_protocol"], case["observations"], case["state"]
    )
    rendered = json.dumps(result, sort_keys=True)
    assert all(value not in rendered for value in case["identity_values"])
    assert result["access_attestation"][
        "competition_archive_task_run_or_candidate_identity_values_emitted"
    ] is False


def test_bound_census_evidence_tamper_fails_closed(tmp_path: Path) -> None:
    case = make_floor_case(tmp_path)
    protocol = json.loads(case["floor_protocol"].read_text(encoding="utf-8"))
    evidence = case["root"] / protocol["inputs"]["census_result_path"]
    evidence.write_bytes(evidence.read_bytes() + b" ")
    with pytest.raises(SupportFloorError, match="hash mismatch"):
        build_result(case["floor_protocol"], case["observations"], case["state"])


def test_window_size_is_protocol_bound(tmp_path: Path) -> None:
    case = make_floor_case(tmp_path)
    protocol = json.loads(case["floor_protocol"].read_text(encoding="utf-8"))
    protocol["inputs"]["current_window_transaction_lines"] -= 1
    write_json(case["floor_protocol"], protocol)
    with pytest.raises(SupportFloorError, match="transaction count mismatch"):
        build_result(case["floor_protocol"], case["observations"], case["state"])


def test_independent_verifier_rejects_candidate_tamper(tmp_path: Path) -> None:
    case = make_floor_case(tmp_path)
    result = build_result(
        case["floor_protocol"], case["observations"], case["state"]
    )
    result["prior_supported_competition_floor"][
        "competitions_with_exactly_one_prior_eligible_run"
    ] += 1
    result_path = case["root"] / "tampered_floor_result.json"
    write_json(result_path, result)
    with pytest.raises(
        SupportFloorVerificationError,
        match="differs from independent reconstruction",
    ):
        verify(
            case["floor_protocol"],
            case["observations"],
            result_path,
            case["state"],
        )


def test_verifier_source_does_not_import_floor_producer() -> None:
    source = (
        ROOT / "phase1/verify_archive_rejection_support_floor.py"
    ).read_text(encoding="utf-8")
    assert "audit_archive_rejection_support_floor" not in source


def test_frozen_real_protocol_binds_completed_census() -> None:
    protocol_path = ROOT / "phase1/archive_rejection_support_floor_v1.json"
    protocol = json.loads(protocol_path.read_text(encoding="utf-8"))
    inputs = protocol["inputs"]
    known = protocol["known_before_floor_readout"]
    assert inputs["current_transaction_lines"] - inputs["prior_transaction_lines"] == (
        inputs["current_window_transaction_lines"]
    ) == 7
    competition_counts = known["census_competition_support_class_counts"]
    assert competition_counts["distinct_rejected_competitions"] == sum(
        competition_counts[name]
        for name in (PRIOR, WINDOW, ARCHIVE_ONLY, NO_SUPPORT)
    )
    assert set(protocol["unknown_at_freeze"].values()) == {False}
    assert protocol["access_contract"]["identity_values_emitted"] is False
    for path_key, hash_key in (
        ("census_result_path", "census_result_sha256"),
        ("census_verification_path", "census_verification_sha256"),
    ):
        evidence = (protocol_path.parent / inputs[path_key]).resolve()
        evidence.relative_to(protocol_path.parent.resolve())
        assert evidence.is_file() and not evidence.is_symlink()
        assert hashlib.sha256(evidence.read_bytes()).hexdigest() == inputs[hash_key]
