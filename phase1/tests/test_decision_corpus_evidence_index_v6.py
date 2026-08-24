import copy
import json
from pathlib import Path

import pytest

from phase1 import build_decision_corpus_evidence_index_v6 as builder
from phase1 import decision_corpus_evidence_index_v6_schema as schema
from phase1 import verify_decision_corpus_evidence_index_v6 as verifier


REPO_ROOT = Path(__file__).resolve().parents[2]
SOURCE_INDEX = REPO_ROOT / builder.SOURCE_INDEX_RELATIVE


def test_builder_and_independent_reconstruction_agree():
    assert builder.PROTOCOL == schema.PROTOCOL
    assert builder.COVERAGE_ENTRY == schema.COVERAGE_ENTRY
    assert builder.SOURCE_ENTRY_NAMES == schema.SOURCE_ENTRY_NAMES
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
        "prediction_escrow_common_support",
        "prospective_gate",
    ]


def test_common_support_keeps_effect_and_activation_boundaries():
    payload = builder.build_index(REPO_ROOT, SOURCE_INDEX)
    entry = payload["entries"][8]
    assert entry["name"] == "prediction_escrow_common_support"
    assert "not a common strict-effect population" in entry["does_not_prove"]
    assert "does not prove predictor accuracy" in entry["does_not_prove"]
    assert payload["scope"]["prediction_pair_universe_identity_verified"] is True
    assert payload["scope"]["prediction_values_aggregated"] is False
    assert payload["scope"]["prediction_accuracy_computed"] is False
    assert payload["scope"]["common_pair_universe_is_common_effect_population"] is False
    assert payload["scope"]["wl_transition_activation_equated"] is False
    assert payload["scope"]["transition_effect_unlocked"] is False
    assert payload["reporting_contract"]["exact_common_pair_universe_language_allowed"]
    assert not payload["reporting_contract"]["seven_arm_effect_or_accuracy_language_allowed"]


def test_aggregate_copies_match_formal_receipt_hashes():
    specs = builder.COVERAGE_ENTRY["artifacts"]
    assert len(specs) == 2
    for specification in specs:
        path = REPO_ROOT / specification["path"]
        assert builder.normalized_sha256(path) == specification["sha256_normalized_lf"]
        artifact = json.loads(builder.normalized_utf8_lf(path).decode("utf-8"))
        for assertion_path, expected in specification["json_assertions"].items():
            assert verifier.asserted_value(artifact, assertion_path) == expected


def test_source_specific_activation_cross_tab_is_frozen():
    matrix_spec = builder.COVERAGE_ENTRY["artifacts"][0]
    matrix = json.loads(
        (REPO_ROOT / matrix_spec["path"]).read_text(encoding="utf-8")
    )
    cross_tab = matrix["overlap"]["joint_temporal_strata"]
    assert cross_tab == {
        "post_wl_activation|post_transition_activation": 417,
        "post_wl_activation|support_only": 507,
        "support_only|support_only": 1665,
    }
    assert sum(cross_tab.values()) == 2589
    assert matrix["overlap"]["transition_effect_eligible_pairs"] == 363
    assert matrix["inventory"]["transition"]["nontie_all_arms_pairs"] == 2244


def test_independent_verifier_checks_complete_stack(tmp_path: Path):
    index = tmp_path / "index.json"
    index.write_text(
        json.dumps(builder.build_index(REPO_ROOT, SOURCE_INDEX), indent=2) + "\n",
        encoding="utf-8",
    )
    receipt = verifier.verify_index(REPO_ROOT, index)
    assert receipt["status"] == "INDEPENDENTLY_VERIFIED_COMMON_SUPPORT_EVIDENCE_INDEX"
    assert receipt["entry_count"] == 10
    assert receipt["artifact_count"] == 28
    assert receipt["bound_file_count"] == 3
    assert receipt["json_assertion_count"] == 362
    assert receipt["prospective_outcomes_read"] is False
    assert receipt["prediction_values_aggregated"] is False


def test_checked_in_index_matches_builder_when_present():
    checked = REPO_ROOT / "phase1/results/decision_corpus_evidence_index_v6_20260825/index.json"
    if not checked.exists():
        pytest.skip("formal v6 output has not been generated yet")
    assert json.loads(checked.read_text(encoding="utf-8")) == builder.build_index(
        REPO_ROOT, SOURCE_INDEX
    )


def test_independent_verifier_rejects_activation_claim_drift(tmp_path: Path):
    payload = copy.deepcopy(builder.build_index(REPO_ROOT, SOURCE_INDEX))
    payload["entries"][8]["supported_claim"] = payload["entries"][8][
        "supported_claim"
    ].replace("507", "506")
    index = tmp_path / "drift.json"
    index.write_text(json.dumps(payload) + "\n", encoding="utf-8")
    with pytest.raises(verifier.VerificationError, match="differs"):
        verifier.verify_index(REPO_ROOT, index)


def test_independent_verifier_rejects_coverage_hash_drift(tmp_path: Path):
    payload = copy.deepcopy(builder.build_index(REPO_ROOT, SOURCE_INDEX))
    payload["entries"][8]["artifacts"][0]["sha256_normalized_lf"] = "0" * 64
    index = tmp_path / "hash_drift.json"
    index.write_text(json.dumps(payload) + "\n", encoding="utf-8")
    with pytest.raises(verifier.VerificationError, match="differs"):
        verifier.verify_index(REPO_ROOT, index)
