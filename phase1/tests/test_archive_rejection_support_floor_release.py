from __future__ import annotations

import hashlib
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
RELEASE = ROOT / "phase1/results/archive_rejection_support_floor_20260902_5609a8e"
PRIOR = ROOT / "phase1/results/archive_granularity_retention_v1_20260831_bc88298/a/result.json"


def load(name: str) -> dict[str, object]:
    return json.loads((RELEASE / name).read_text(encoding="utf-8"))


def digest(name: str) -> str:
    return hashlib.sha256((RELEASE / name).read_bytes()).hexdigest()


def test_byte_exact_formal_receipts_are_preserved() -> None:
    expected = {
        "result.json": "ce8b30101a26fdba178c6046c24e55a219eacd1e307dc8c033cae754898f4248",
        "independent_verification.json": "3ab7085a8eb7219b03575a5bc85a8d5395c986c3608eedd81fa1af564cb4796c",
        "preflight13.txt": "e9f09074e09ea53feb96df0903e550cd5e756b1391b0440bd962a14e6681a71e",
        "focused_tests.txt": "6cd89cf2ae29b7732893cfe49a25afef641b7007a4726af823053bbda0e72ba7",
        "postflight_summary.txt": "aeaa2f3aa558b2342042cd2522b8b5d1d2678968fc0eadfe7380e6bb73ac9e41",
        "readonly_receipt.json": "2a6c1095c225a09b7acc9f8edd68aff5253815c410a89e2b06af76f08b2fc4e9",
        "REMOTE_MANIFEST_SHA256": "233163325f538542ca19b2b1d208e748c29162ef25849b8ba8d2a854c5f3517e",
    }
    assert {name: digest(name) for name in expected} == expected
    assert (RELEASE / "REMOTE_MANIFEST_SHA256").read_text(
        encoding="ascii"
    ).strip() == "86973b2260f99676513c8f3e7a951accafcf0cdfaf4bf5a35e9bf74bc9ed06a1"


def test_release_matches_independent_reconstruction() -> None:
    result = load("result.json")
    verification = load("independent_verification.json")
    summary = load("formal_summary.json")
    assert digest("result.json") == verification["result_sha256"] == summary[
        "release_files"
    ]["result_sha256"]
    assert digest("independent_verification.json") == summary["release_files"][
        "independent_verification_sha256"
    ]
    assert verification["all_result_fields_equal"] is True
    assert verification["producer_imported"] is False
    assert verification["competition_support_class_counts"] == result[
        "competition_support_class_counts"
    ]
    assert verification["prior_supported_competition_floor"] == result[
        "prior_supported_competition_floor"
    ]


def test_positive_support_floor_is_exact_and_not_single_run_driven() -> None:
    result = load("result.json")
    floor = result["prior_supported_competition_floor"]
    summaries = floor["prior_metric_summaries"]
    assert floor["competition_count"] == 6
    assert floor["competitions_with_exactly_one_prior_accepted_archive"] == 1
    assert floor["competitions_with_exactly_one_prior_physical_run"] == 0
    assert floor["competitions_with_exactly_one_prior_eligible_run"] == 0
    assert {
        metric: (
            summaries[metric]["sum"],
            summaries[metric]["minimum"],
            summaries[metric]["median"]["numerator"],
            summaries[metric]["median"]["denominator"],
            summaries[metric]["maximum"],
        )
        for metric in (
            "accepted_archives",
            "physical_runs",
            "eligible_runs",
            "eligible_endpoints",
        )
    } == {
        "accepted_archives": (20, 1, 4, 1, 5),
        "physical_runs": (94, 4, 17, 1, 29),
        "eligible_runs": (92, 4, 17, 1, 29),
        "eligible_endpoints": (2558, 50, 917, 2, 944),
    }
    assert floor["minimum_prior_eligible_run_fraction"] == {
        "decimal_17g": "0.7142857142857143",
        "denominator": 7,
        "numerator": 5,
    }
    assert floor["minimum_prior_endpoints_per_eligible_run"] == {
        "decimal_17g": "12.5",
        "denominator": 2,
        "numerator": 25,
    }


def test_release_integrity_and_claim_boundaries_are_preserved() -> None:
    result = load("result.json")
    summary = load("formal_summary.json")
    assert all(result["integrity"].values())
    assert result["access_attestation"][
        "competition_archive_task_run_or_candidate_identity_values_emitted"
    ] is False
    assert result["access_attestation"][
        "labels_grades_outcomes_predictions_accuracy_or_utility_read"
    ] is False
    assert result["claim_boundary"]["post_hoc_after_aggregate_census_readout"]
    assert result["claim_boundary"]["full_census_descriptive_not_sampling_inference"]
    assert result["claim_boundary"][
        "estimates_future_rejection_frequency_or_causal_effect"
    ] is False
    assert summary["tests"] == {
        "focused_passed": 12,
        "full_passed": 1963,
        "full_seconds": 147.02,
        "warnings": 48,
    }
    assert summary["formal"]["complete"] is True
    assert summary["formal"]["failed_rc_present"] is False


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
    readme = (RELEASE / "README.md").read_text(encoding="utf-8")
    assert "post-hoc" in readme
    assert "不是新的 fully blind confirmation" in readme


def test_erratum_proves_core_floor_was_already_published() -> None:
    current = load("result.json")
    prior = json.loads(PRIOR.read_text(encoding="utf-8"))
    crosswalk = load("prior_evidence_crosswalk.json")
    summary = load("formal_summary.json")
    old = prior["retained_by_archive_granular_validation"]
    new = current["prior_supported_competition_floor"]["prior_metric_summaries"]
    assert current["prior_supported_competition_floor"]["competition_count"] == old[
        "affected_competitions"
    ] == 6
    for metric in (
        "accepted_archives",
        "physical_runs",
        "eligible_runs",
        "eligible_endpoints",
    ):
        assert new[metric]["sum"] == old[metric]
        old_range = old["anonymous_affected_task_distribution"][metric]
        assert new[metric]["minimum"] == old_range["minimum"]
        assert new[metric]["maximum"] == old_range["maximum"]
        assert float(new[metric]["median"]["decimal_17g"]) == old_range["median"]
    assert new["eligible_runs"]["maximum_share"]["decimal_17g"] == format(
        old["dominant_affected_task_eligible_run_share"], ".17g"
    )
    assert new["eligible_endpoints"]["maximum_share"]["decimal_17g"] == format(
        old["dominant_affected_task_eligible_endpoint_share"], ".17g"
    )
    expected_class = "PRIOR_EVIDENCE_OMISSION_CORRECTED_INDEPENDENT_RECONSTRUCTION"
    assert crosswalk["classification"] == expected_class
    assert summary["evidence_index_erratum"]["classification"] == expected_class
    assert summary["evidence_index_erratum"][
        "counts_as_independent_new_scientific_result"
    ] is False
    erratum = (RELEASE / "ERRATUM.md").read_text(encoding="utf-8")
    assert "不构成新突破" in erratum
    assert "bc88298" in erratum
