import copy
import json
from pathlib import Path

import pytest

from phase1 import build_decision_corpus_evidence_index_v4 as builder
from phase1 import decision_corpus_evidence_index_v4_schema as schema
from phase1 import verify_decision_corpus_evidence_index_v4 as verifier


REPO_ROOT = Path(__file__).resolve().parents[2]
SOURCE_INDEX = REPO_ROOT / builder.SOURCE_INDEX_RELATIVE


def test_builder_and_independent_reconstruction_agree():
    assert builder.PROTOCOL == schema.PROTOCOL
    assert builder.PARTIAL_ORDER_ENTRY == schema.PARTIAL_ORDER_ENTRY
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
        "label_repeatability",
        "normalized_clone",
        "deployment_cost",
        "prospective_gate",
    ]


def test_partial_order_entry_keeps_validity_and_utility_boundaries():
    payload = builder.build_index(REPO_ROOT, SOURCE_INDEX)
    entry = next(
        item for item in payload["entries"] if item["name"] == "status_certified_partial_order"
    )
    assert "not a numeric-quality total order" in entry["does_not_prove"]
    assert "unresolved relations remain unknown" in entry["does_not_prove"]
    assert payload["scope"]["status_partial_order_is_numeric_quality_order"] is False
    assert payload["scope"]["status_partial_order_establishes_predictor_or_search_utility"] is False
    assert payload["scope"]["grade_absent_required_for_materiality"] is False
    assert payload["reporting_contract"]["numeric_quality_total_order_language_allowed"] is False
    assert payload["reporting_contract"]["explicit_validity_edge_count_language_allowed"] is True


def test_edge_file_and_manifest_are_both_pinned():
    entry = builder.PARTIAL_ORDER_ENTRY
    bound = entry["bound_files"][0]
    edge_path = REPO_ROOT / bound["path"]
    assert builder.normalized_sha256(edge_path) == (
        "dda9f121dc32a1ef309992b0bec61934864e35ec337385bb2f5c0c548b258a3d"
    )
    assert len(builder.normalized_utf8_lf(edge_path).decode("utf-8").splitlines()) == 2079
    manifest_spec = entry["artifacts"][2]
    manifest_path = REPO_ROOT / manifest_spec["path"]
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    for assertion_path, expected in manifest_spec["json_assertions"].items():
        assert verifier.asserted_value(manifest, assertion_path) == expected


def test_independent_verifier_checks_all_artifacts_and_bound_file(tmp_path: Path):
    path = tmp_path / "index.json"
    path.write_text(
        json.dumps(builder.build_index(REPO_ROOT, SOURCE_INDEX), indent=2) + "\n",
        encoding="utf-8",
    )
    receipt = verifier.verify_index(REPO_ROOT, path)
    assert receipt["status"] == "INDEPENDENTLY_VERIFIED_FAILURE_AWARE_EVIDENCE_INDEX"
    assert receipt["entry_count"] == 8
    assert receipt["artifact_count"] == 23
    assert receipt["bound_file_count"] == 1
    assert receipt["json_assertion_count"] > 181
    assert receipt["prospective_outcomes_read"] is False


def test_checked_in_index_matches_builder_when_present():
    checked = REPO_ROOT / "phase1/results/decision_corpus_evidence_index_v4_20260821/index.json"
    if not checked.exists():
        pytest.skip("formal v4 output has not been generated yet")
    assert json.loads(checked.read_text(encoding="utf-8")) == builder.build_index(
        REPO_ROOT, SOURCE_INDEX
    )


def test_independent_verifier_rejects_claim_drift():
    payload = copy.deepcopy(builder.build_index(REPO_ROOT, SOURCE_INDEX))
    payload["entries"][3]["does_not_prove"] = "numeric total order"
    temporary = REPO_ROOT / "phase1/results/.tmp_v4_claim_drift.json"
    try:
        temporary.write_text(json.dumps(payload) + "\n", encoding="utf-8")
        with pytest.raises(verifier.VerificationError, match="differs"):
            verifier.verify_index(REPO_ROOT, temporary)
    finally:
        temporary.unlink(missing_ok=True)


def test_independent_verifier_rejects_edge_binding_drift():
    payload = copy.deepcopy(builder.build_index(REPO_ROOT, SOURCE_INDEX))
    payload["entries"][3]["bound_files"][0]["sha256_normalized_lf"] = "0" * 64
    temporary = REPO_ROOT / "phase1/results/.tmp_v4_edge_drift.json"
    try:
        temporary.write_text(json.dumps(payload) + "\n", encoding="utf-8")
        with pytest.raises(verifier.VerificationError, match="differs"):
            verifier.verify_index(REPO_ROOT, temporary)
    finally:
        temporary.unlink(missing_ok=True)
