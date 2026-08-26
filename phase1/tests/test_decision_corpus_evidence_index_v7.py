from __future__ import annotations

import copy
import inspect
import json
from pathlib import Path

import pytest

from phase1 import build_decision_corpus_evidence_index_v7 as builder
from phase1 import decision_corpus_evidence_index_v7_schema as schema
from phase1 import verify_decision_corpus_evidence_index_v7 as verifier


REPO_ROOT = Path(__file__).resolve().parents[2]
SOURCE_INDEX = REPO_ROOT / schema.SOURCE_INDEX_RELATIVE


def entry(payload: dict, name: str) -> dict:
    return next(value for value in payload["entries"] if value["name"] == name)


def test_builder_and_non_importing_verifier_reconstruct_same_v7() -> None:
    built = builder.build_index(REPO_ROOT, SOURCE_INDEX)
    assert built == verifier.expected_index(REPO_ROOT)
    assert [value["name"] for value in built["entries"]] == [
        "decision_corpus",
        "source_opportunity",
        "decision_observability",
        "status_certified_partial_order",
        "source_decision_answerability",
        "label_repeatability",
        "normalized_clone",
        "deployment_cost",
        "evidence_provenance_repair",
        "prediction_receipt_common_support",
        "structural_weighting_shift",
        "opportunity_yield_aggregation_audit",
        "task_balance_structural_only_v2",
        "prospective_gate",
    ]
    assert "build_decision_corpus_evidence_index_v7" not in inspect.getsource(verifier)


def test_v7_restarts_from_v5_and_excludes_withdrawn_evidence_paths() -> None:
    payload = builder.build_index(REPO_ROOT, SOURCE_INDEX)
    assert payload["source_v5_index"]["path"] == schema.SOURCE_INDEX_RELATIVE
    assert payload["provenance_repair"]["source_v6_read_or_inherited"] is False
    assert payload["provenance_repair"]["v1_provenance_retroactively_repaired"] is False
    for value in payload["entries"]:
        for evidence in value.get("artifacts", []) + value.get("bound_files", []):
            assert not any(
                fragment in evidence["path"]
                for fragment in schema.FORBIDDEN_EVIDENCE_PATH_FRAGMENTS
            )


def test_receipt_only_common_support_keeps_value_and_orientation_boundary() -> None:
    payload = builder.build_index(REPO_ROOT, SOURCE_INDEX)
    value = entry(payload, "prediction_receipt_common_support")
    assert "2,755-pair" in value["supported_claim"]
    assert "does not reopen pair identity or orientation" in value["does_not_prove"]
    assert payload["scope"]["prediction_pair_files_opened_by_replacement_common_support"] is False
    assert payload["scope"]["prediction_values_read_or_aggregated_by_replacement_entries"] is False
    assert payload["reporting_contract"]["receipt_certified_common_support_language_allowed"] is True
    assert payload["reporting_contract"]["pair_orientation_tie_or_margin_language_allowed"] is False


def test_structural_positive_claim_preserves_single_drop_failure() -> None:
    payload = builder.build_index(REPO_ROOT, SOURCE_INDEX)
    value = entry(payload, "structural_weighting_shift")
    assert "0.337082500713674" in value["supported_claim"]
    assert "0.9641733656841007" in value["does_not_prove"]
    assert payload["reporting_contract"]["structural_weighting_shift_language_allowed"] is True
    assert payload["reporting_contract"]["single_drop_robust_magnitude_language_allowed"] is False


def test_opportunity_audit_and_task_balance_cannot_be_promoted_to_effects() -> None:
    payload = builder.build_index(REPO_ROOT, SOURCE_INDEX)
    opportunity = entry(payload, "opportunity_yield_aggregation_audit")
    balance = entry(payload, "task_balance_structural_only_v2")
    assert "not a measured predictor effect" in opportunity["does_not_prove"]
    assert "657 to 645" in balance["supported_claim"]
    assert "still fails the 25% cap" in balance["does_not_prove"]
    assert payload["scope"]["task_balance_cap_pass"] is False
    assert payload["reporting_contract"]["opportunity_yield_effect_language_allowed"] is False
    assert payload["reporting_contract"]["task_balance_cap_or_producer_compliance_language_allowed"] is False


def test_independent_verifier_checks_complete_clean_stack(tmp_path: Path) -> None:
    index_path = tmp_path / "index.json"
    index_path.write_text(
        json.dumps(builder.build_index(REPO_ROOT, SOURCE_INDEX), indent=2) + "\n",
        encoding="utf-8",
    )
    receipt = verifier.verify_index(REPO_ROOT, index_path)
    assert receipt["status"] == (
        "INDEPENDENTLY_VERIFIED_CLEAN_PROVENANCE_EVIDENCE_INDEX"
    )
    assert receipt["entry_count"] == 14
    assert receipt["artifact_count"] == 37
    assert receipt["bound_file_count"] == 3
    assert receipt["json_assertion_count"] == 434
    assert receipt["source_v6_read_or_inherited"] is False
    assert receipt["withdrawn_evidence_paths_used"] is False
    assert receipt["prediction_pair_files_opened"] is False
    assert receipt["prediction_values_read_or_aggregated"] is False
    assert receipt["prospective_outcomes_read"] is False


def test_checked_in_index_matches_builder_when_present() -> None:
    checked = (
        REPO_ROOT
        / "phase1/results/decision_corpus_evidence_index_v7_20260826_a83bebf/index.json"
    )
    if not checked.exists():
        pytest.skip("formal v7 output has not been generated yet")
    assert json.loads(checked.read_text(encoding="utf-8")) == builder.build_index(
        REPO_ROOT, SOURCE_INDEX
    )


def test_builder_rejects_v6_as_source() -> None:
    with pytest.raises(builder.BuildError, match="unaffected v5"):
        builder.build_index(
            REPO_ROOT,
            REPO_ROOT
            / "phase1/results/decision_corpus_evidence_index_v6_20260825/index.json",
        )


def test_independent_verifier_rejects_claim_drift(tmp_path: Path) -> None:
    payload = copy.deepcopy(builder.build_index(REPO_ROOT, SOURCE_INDEX))
    entry(payload, "task_balance_structural_only_v2")["supported_claim"] = (
        "The cap passed."
    )
    index_path = tmp_path / "drift.json"
    index_path.write_text(json.dumps(payload) + "\n", encoding="utf-8")
    with pytest.raises(verifier.VerificationError, match="differs"):
        verifier.verify_index(REPO_ROOT, index_path)


def test_independent_verifier_rejects_replacement_hash_drift(tmp_path: Path) -> None:
    payload = copy.deepcopy(builder.build_index(REPO_ROOT, SOURCE_INDEX))
    entry(payload, "prediction_receipt_common_support")["artifacts"][0][
        "sha256_normalized_lf"
    ] = "0" * 64
    index_path = tmp_path / "hash-drift.json"
    index_path.write_text(json.dumps(payload) + "\n", encoding="utf-8")
    with pytest.raises(verifier.VerificationError, match="differs"):
        verifier.verify_index(REPO_ROOT, index_path)


def test_list_index_assertions_are_fail_closed() -> None:
    payload = {"rows": [{"status": "withdrawn"}]}
    assert verifier.asserted_value(payload, "rows.0.status") == "withdrawn"
    with pytest.raises(verifier.VerificationError, match="outside"):
        verifier.asserted_value(payload, "rows.1.status")
