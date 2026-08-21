import copy
import json
from pathlib import Path

import pytest

from phase1 import build_decision_corpus_evidence_index_v3 as builder
from phase1 import decision_corpus_evidence_index_v3_schema as schema
from phase1 import verify_decision_corpus_evidence_index_v3 as verifier


REPO_ROOT = Path(__file__).resolve().parents[2]
SOURCE_INDEX = REPO_ROOT / builder.SOURCE_INDEX_RELATIVE


def test_builder_and_independent_reconstruction_agree():
    assert builder.PROTOCOL == schema.PROTOCOL
    assert builder.OBSERVABILITY_ENTRY == schema.OBSERVABILITY_ENTRY
    assert builder.SOURCE_ENTRY_NAMES == schema.SOURCE_ENTRY_NAMES
    assert builder.SCOPE == schema.SCOPE
    assert builder.REPORTING_CONTRACT == schema.REPORTING_CONTRACT
    built = builder.build_index(REPO_ROOT, SOURCE_INDEX)
    assert built == verifier.expected_index(REPO_ROOT)
    assert [entry["name"] for entry in built["entries"]] == [
        "decision_corpus",
        "source_opportunity",
        "decision_observability",
        "label_repeatability",
        "normalized_clone",
        "deployment_cost",
        "prospective_gate",
    ]


def test_observability_entry_keeps_denominator_and_utility_boundaries():
    payload = builder.build_index(REPO_ROOT, SOURCE_INDEX)
    entry = next(item for item in payload["entries"] if item["name"] == "decision_observability")
    assert "not a log of comparisons" in entry["does_not_prove"]
    assert "all audited parents retain" in entry["does_not_prove"]
    assert payload["scope"]["observability_is_actual_agent_comparison_log"] is False
    assert payload["scope"]["observability_establishes_predictor_or_search_utility"] is False
    assert payload["reporting_contract"]["decision_point_disappearance_language_allowed"] is False
    assert payload["reporting_contract"]["actual_agent_comparison_count_language_allowed"] is False


def test_formal_summary_is_pinned_to_remote_manifest_hash():
    path = REPO_ROOT / builder.OBSERVABILITY_ENTRY["artifacts"][0]["path"]
    assert builder.normalized_sha256(path) == (
        "e2bf11bc557ff147a11040821a6d3aa5a0650023ba585bbbf7f5e730fcf07ceb"
    )


def test_checked_in_index_matches_builder_when_present():
    checked = REPO_ROOT / "phase1/results/decision_corpus_evidence_index_v3_20260821/index.json"
    if not checked.exists():
        pytest.skip("formal v3 output has not been generated yet")
    assert json.loads(checked.read_text(encoding="utf-8")) == builder.build_index(
        REPO_ROOT, SOURCE_INDEX
    )


def test_independent_verifier_rejects_claim_drift():
    payload = copy.deepcopy(builder.build_index(REPO_ROOT, SOURCE_INDEX))
    payload["entries"][2]["does_not_prove"] = "decision points disappeared"
    temporary = REPO_ROOT / "phase1/results/.tmp_v3_claim_drift.json"
    try:
        temporary.write_text(json.dumps(payload) + "\n", encoding="utf-8")
        with pytest.raises(verifier.VerificationError, match="differs"):
            verifier.verify_index(REPO_ROOT, temporary)
    finally:
        temporary.unlink(missing_ok=True)


def test_independent_verifier_rejects_hash_drift():
    payload = copy.deepcopy(builder.build_index(REPO_ROOT, SOURCE_INDEX))
    payload["entries"][2]["artifacts"][0]["sha256_normalized_lf"] = "0" * 64
    temporary = REPO_ROOT / "phase1/results/.tmp_v3_hash_drift.json"
    try:
        temporary.write_text(json.dumps(payload) + "\n", encoding="utf-8")
        with pytest.raises(verifier.VerificationError, match="differs"):
            verifier.verify_index(REPO_ROOT, temporary)
    finally:
        temporary.unlink(missing_ok=True)
