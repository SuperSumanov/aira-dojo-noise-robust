from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
PACKAGE = (
    ROOT
    / "phase1"
    / "results"
    / "historical_release_future_identifier_erased_overlap_887_20260828_8bf9512_r2"
)


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def load(path: Path) -> dict:
    value = json.loads(path.read_text(encoding="utf-8"))
    assert isinstance(value, dict)
    return value


def manifest(path: Path) -> dict[str, str]:
    rows: dict[str, str] = {}
    for line in path.read_text(encoding="utf-8").splitlines():
        match = re.fullmatch(r"([0-9a-f]{64}) [ *](.+)", line)
        assert match is not None
        name = match.group(2).removeprefix("./")
        assert name not in rows
        rows[name] = match.group(1)
    return rows


def test_compact_package_manifest_is_complete_and_exact() -> None:
    manifest_path = PACKAGE / "SHA256SUMS"
    expected = manifest(manifest_path)
    actual = {
        path.name
        for path in PACKAGE.iterdir()
        if path.is_file() and path.name != "SHA256SUMS"
    }
    assert set(expected) == actual
    assert len(expected) == 5
    for name, expected_sha in expected.items():
        assert digest(PACKAGE / name) == expected_sha
    assert digest(manifest_path) == (
        "152f6f7c2d12f8c47e0fd809a56eb2a3ad8cd3dac826b62115c994201a0da985"
    )


def test_complete_release_zero_link_result_and_population_are_exact() -> None:
    summary = load(PACKAGE / "formal_summary.json")
    assert summary["classification"] == "ZERO_IDENTIFIER_ERASED_RELEASE_LINKS"
    assert summary["evidence_index_status"] == (
        "PROVISIONAL_TEMPORAL_SPLIT_CERTIFIED_EVIDENCE_STACK_AWAITING_FIRST960"
    )
    assert summary["all_pre_registered_gates_passed"] is True
    assert (summary["historical_endpoints"], summary["historical_runs"], summary["historical_tasks"]) == (
        16012,
        667,
        25,
    )
    assert (summary["prospective_endpoints"], summary["prospective_runs"], summary["prospective_tasks"]) == (
        11906,
        435,
        34,
    )
    assert summary["historical_fingerprinted_endpoints"] == 16012
    assert summary["prospective_fingerprinted_endpoints"] == 11894
    assert summary["primary_candidate_pairs"] == 18510294
    assert summary["primary_near_duplicate_pairs"] == 0
    assert summary["strict_near_duplicate_pairs"] == 0
    assert summary["primary_prospective_affected_endpoints"] == 0
    assert summary["primary_components"] == 0
    assert all(summary["gate_checks"].values())


def test_independent_recheck_and_failure_history_are_bound() -> None:
    summary = load(PACKAGE / "formal_summary.json")
    recheck = load(PACKAGE / "independent_recheck.json")
    bindings = load(PACKAGE / "source_bindings.json")
    assert recheck["status"] == "INDEPENDENT_PACKAGE_RECHECK_COMPLETE"
    assert recheck["imports_packager_builder"] is False
    assert recheck["producer_aggregate_matches"] is True
    assert recheck["formal_postflight_verifier_byte_identical"] is True
    assert recheck["subset_bruteforce_matches"] is True
    assert bindings["status"] == "FORMAL_POSTFLIGHT_DEPLOYMENT_AND_FAILURE_HISTORY_BOUND"
    assert bindings["scientific_protocol_changed_in_r2"] is False
    assert summary["prior_failed_formal_rc"] == bindings["prior_failed_formal_rc"] == 124
    assert summary["prior_failed_deployment_rc"] == bindings["prior_failed_deployment_rc"] == 1
    assert summary["prior_failed_result_file_created"] is False
    assert summary["prior_failed_result_values_read"] is False
    assert bindings["formal_sha256sums_file_sha256"] == (
        "4089cef1c7a42886ae6a363d3854e2f4e89e254829549a4681ea6bfaaed80fac"
    )
    assert bindings["postflight_sha256sums_file_sha256"] == (
        "868a11eda261ea78f71f4148eb60bf7b36a4b413ee708b7bbc03da3d1c6f5a98"
    )
    assert bindings["deployment_sha256sums_file_sha256"] == (
        "9a178a93e4f2b074363f120a3e1974c47f003cf874a6b0f13942ffede16af69c"
    )


def test_claim_and_access_boundaries_are_preserved() -> None:
    summary = load(PACKAGE / "formal_summary.json")
    boundary = summary["claim_boundary"]
    assert boundary["fixed_identifier_erased_syntactic_overlap_only"] is True
    assert boundary["semantic_clone_absence_proven"] is False
    assert boundary["unknown_pretraining_contamination_absence_proven"] is False
    assert boundary["all_historical_sources_covered"] is False
    assert boundary["first960_or_closure_completed"] is False
    assert boundary["predictor_accuracy_effect_or_search_utility_computed"] is False
    assert summary["prospective_outcomes_read"] is False
    assert summary["prediction_values_read"] is False
    assert summary["raw_senior_archives_opened"] is False
    assert summary["gpu_api_model_fit_base_update"] == [0, 0, 0, 0]
    attestation = (PACKAGE / "access_attestation.txt").read_text(encoding="utf-8")
    assert "prospective_label_grade_outcome_prediction_values_read=false" in attestation
    assert "raw_senior_archives_opened=false" in attestation
