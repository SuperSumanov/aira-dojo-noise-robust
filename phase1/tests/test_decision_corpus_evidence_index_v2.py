import copy
import json
from pathlib import Path

import pytest

from phase1 import build_decision_corpus_evidence_index_v2 as builder
from phase1 import decision_corpus_evidence_index_v2_schema as schema
from phase1 import verify_decision_corpus_evidence_index_v2 as verifier


REPO_ROOT = Path(__file__).resolve().parents[2]
SOURCE_INDEX = REPO_ROOT / builder.SOURCE_INDEX_RELATIVE


def test_builder_and_independent_reconstruction_agree():
    assert builder.PROTOCOL == schema.PROTOCOL
    assert builder.SOURCE_ENTRY == schema.SOURCE_ENTRY
    built = builder.build_index(REPO_ROOT, SOURCE_INDEX)
    expected = verifier.expected_index(REPO_ROOT)
    assert built == expected
    assert [entry["name"] for entry in built["entries"]] == [
        "decision_corpus",
        "source_opportunity",
        "label_repeatability",
        "normalized_clone",
        "deployment_cost",
        "prospective_gate",
    ]


def test_source_opportunity_keeps_fragment_and_missingness_boundaries():
    payload = builder.build_index(REPO_ROOT, SOURCE_INDEX)
    entry = next(item for item in payload["entries"] if item["name"] == "source_opportunity")
    assert "does not recover missing numeric outcomes" in entry["does_not_prove"]
    assert payload["scope"]["source_choice_set_complete"] is False
    assert payload["scope"]["missing_at_random_assumed"] is False
    assert payload["reporting_contract"]["complete_choice_set_language_allowed"] is False
    assert payload["reporting_contract"]["missing_at_random_language_allowed"] is False


def test_checked_in_index_matches_builder_when_present():
    checked = (
        REPO_ROOT
        / "phase1/results/decision_corpus_evidence_index_v2_20260821/index.json"
    )
    if not checked.exists():
        pytest.skip("formal v2 output has not been generated yet")
    assert json.loads(checked.read_text(encoding="utf-8")) == builder.build_index(
        REPO_ROOT, SOURCE_INDEX
    )


def test_independent_verifier_rejects_claim_drift(tmp_path: Path):
    payload = builder.build_index(REPO_ROOT, SOURCE_INDEX)
    payload = copy.deepcopy(payload)
    payload["entries"][1]["does_not_prove"] = "we now claim a complete choice set"
    temporary = REPO_ROOT / "phase1" / "results" / ".tmp_v2_claim_drift.json"
    try:
        temporary.write_text(json.dumps(payload) + "\n", encoding="utf-8")
        with pytest.raises(verifier.VerificationError, match="differs"):
            verifier.verify_index(REPO_ROOT, temporary)
    finally:
        temporary.unlink(missing_ok=True)


def test_independent_verifier_rejects_hash_drift():
    payload = builder.build_index(REPO_ROOT, SOURCE_INDEX)
    payload = copy.deepcopy(payload)
    payload["entries"][1]["artifacts"][0]["sha256_normalized_lf"] = "0" * 64
    temporary = REPO_ROOT / "phase1" / "results" / ".tmp_v2_hash_drift.json"
    try:
        temporary.write_text(json.dumps(payload) + "\n", encoding="utf-8")
        with pytest.raises(verifier.VerificationError, match="differs"):
            verifier.verify_index(REPO_ROOT, temporary)
    finally:
        temporary.unlink(missing_ok=True)
