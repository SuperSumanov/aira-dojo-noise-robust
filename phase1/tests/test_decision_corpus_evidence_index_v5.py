import copy
import csv
import json
from pathlib import Path

import pytest

from phase1 import build_decision_corpus_evidence_index_v5 as builder
from phase1 import decision_corpus_evidence_index_v5_schema as schema
from phase1 import verify_decision_corpus_evidence_index_v5 as verifier


REPO_ROOT = Path(__file__).resolve().parents[2]
SOURCE_INDEX = REPO_ROOT / builder.SOURCE_INDEX_RELATIVE


def test_builder_and_independent_reconstruction_agree():
    assert builder.PROTOCOL == schema.PROTOCOL
    assert builder.ANSWERABILITY_ENTRY == schema.ANSWERABILITY_ENTRY
    assert builder.SOURCE_ENTRY_NAMES == schema.SOURCE_ENTRY_NAMES
    assert builder.SCOPE == schema.SCOPE
    assert builder.REPORTING_CONTRACT == schema.REPORTING_CONTRACT
    built = builder.build_index(REPO_ROOT, SOURCE_INDEX)
    assert built == verifier.expected_index(REPO_ROOT)
    assert [entry["name"] for entry in built["entries"]] == [
        "decision_corpus",
        "source_opportunity",
        "decision_observability",
        "status_certified_partial_order",
        "source_decision_answerability",
        "label_repeatability",
        "normalized_clone",
        "deployment_cost",
        "prospective_gate",
    ]


def test_answerability_entry_keeps_model_and_total_order_boundaries():
    payload = builder.build_index(REPO_ROOT, SOURCE_INDEX)
    entry = next(
        item for item in payload["entries"] if item["name"] == "source_decision_answerability"
    )
    assert "not predictor accuracy" in entry["does_not_prove"]
    assert "complete numeric total order" in entry["does_not_prove"]
    assert "rather than logged agent comparisons" in entry["does_not_prove"]
    assert payload["scope"]["source_winner_answerability_is_predictor_accuracy"] is False
    assert payload["scope"]["source_winner_answerability_is_search_utility"] is False
    assert payload["scope"]["source_winner_answerability_is_complete_total_order"] is False
    assert payload["scope"]["source_identity_unavailable_imputed"] is False
    assert payload["reporting_contract"]["source_winner_answerability_language_allowed"] is True
    assert (
        payload["reporting_contract"]["source_winner_predictor_performance_language_allowed"]
        is False
    )


def test_parent_and_task_csv_files_and_manifest_are_pinned():
    entry = builder.ANSWERABILITY_ENTRY
    for bound in entry["bound_files"]:
        path = REPO_ROOT / bound["path"]
        assert builder.normalized_sha256(path) == bound["sha256_normalized_lf"]
        rows = list(csv.reader(builder.normalized_utf8_lf(path).decode("utf-8").splitlines()))
        assert rows[0] == bound["header"]
        assert len(rows) - 1 == bound["data_row_count"]
        assert all(len(row) == len(rows[0]) for row in rows[1:])
    manifest_spec = entry["artifacts"][2]
    manifest = json.loads((REPO_ROOT / manifest_spec["path"]).read_text(encoding="utf-8"))
    for assertion_path, expected in manifest_spec["json_assertions"].items():
        assert verifier.asserted_value(manifest, assertion_path) == expected


def test_independent_verifier_checks_all_artifacts_and_bound_files(tmp_path: Path):
    path = tmp_path / "index.json"
    path.write_text(
        json.dumps(builder.build_index(REPO_ROOT, SOURCE_INDEX), indent=2) + "\n",
        encoding="utf-8",
    )
    receipt = verifier.verify_index(REPO_ROOT, path)
    assert receipt["status"] == "INDEPENDENTLY_VERIFIED_SOURCE_ANSWERABILITY_EVIDENCE_INDEX"
    assert receipt["entry_count"] == 9
    assert receipt["artifact_count"] == 26
    assert receipt["bound_file_count"] == 3
    assert receipt["json_assertion_count"] > 280
    assert receipt["prospective_outcomes_read"] is False


def test_checked_in_index_matches_builder_when_present():
    checked = REPO_ROOT / "phase1/results/decision_corpus_evidence_index_v5_20260821/index.json"
    if not checked.exists():
        pytest.skip("formal v5 output has not been generated yet")
    assert json.loads(checked.read_text(encoding="utf-8")) == builder.build_index(
        REPO_ROOT, SOURCE_INDEX
    )


def test_independent_verifier_rejects_claim_drift():
    payload = copy.deepcopy(builder.build_index(REPO_ROOT, SOURCE_INDEX))
    payload["entries"][4]["does_not_prove"] = "predictor accuracy"
    temporary = REPO_ROOT / "phase1/results/.tmp_v5_claim_drift.json"
    try:
        temporary.write_text(json.dumps(payload) + "\n", encoding="utf-8")
        with pytest.raises(verifier.VerificationError, match="differs"):
            verifier.verify_index(REPO_ROOT, temporary)
    finally:
        temporary.unlink(missing_ok=True)


def test_independent_verifier_rejects_csv_binding_drift():
    payload = copy.deepcopy(builder.build_index(REPO_ROOT, SOURCE_INDEX))
    payload["entries"][4]["bound_files"][0]["sha256_normalized_lf"] = "0" * 64
    temporary = REPO_ROOT / "phase1/results/.tmp_v5_csv_drift.json"
    try:
        temporary.write_text(json.dumps(payload) + "\n", encoding="utf-8")
        with pytest.raises(verifier.VerificationError, match="differs"):
            verifier.verify_index(REPO_ROOT, temporary)
    finally:
        temporary.unlink(missing_ok=True)


def test_csv_payload_rejects_header_drift(tmp_path: Path):
    path = tmp_path / "table.csv"
    path.write_text("wrong,b\n1,2\n", encoding="utf-8", newline="\n")
    specification = {
        "path": "table.csv",
        "format": "csv",
        "line_count": 2,
        "data_row_count": 1,
        "header": ["a", "b"],
    }
    with pytest.raises(verifier.VerificationError, match="header mismatch"):
        verifier.verify_bound_payload(path, specification)
