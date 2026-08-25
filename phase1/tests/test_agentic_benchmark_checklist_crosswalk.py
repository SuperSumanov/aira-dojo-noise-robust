from __future__ import annotations

import copy
import json
from pathlib import Path

import pytest

from phase1 import verify_agentic_benchmark_checklist_crosswalk as verifier


REPO_ROOT = Path(__file__).resolve().parents[2]
RESULT = REPO_ROOT / "phase1/results/agentic_benchmark_checklist_crosswalk_v1_20260825"
CROSSWALK = RESULT / "crosswalk.json"


def _load() -> dict:
    return json.loads(CROSSWALK.read_text(encoding="utf-8"))


def _write(path: Path, value: dict) -> None:
    path.write_text(
        json.dumps(value, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
        newline="\n",
    )


def test_committed_crosswalk_binds_complete_abc_item_set() -> None:
    receipt = verifier.verify_crosswalk(REPO_ROOT, CROSSWALK)
    assert receipt["status"] == (
        "INDEPENDENTLY_VERIFIED_SCHEMA_AND_LOCAL_EVIDENCE_BINDING"
    )
    assert receipt["items_verified"] == 24
    assert receipt["evidence_files_verified"] == 24
    assert receipt["status_counts"] == {
        "PASS_LOCAL": 9,
        "PARTIAL": 9,
        "INHERITED_UPSTREAM": 5,
        "NOT_APPLICABLE": 1,
    }
    assert receipt["semantic_assessment_certified"] is False
    assert receipt["aggregate_compliance_score_reported"] is False
    assert receipt["prospective_outcomes_read"] is False
    assert receipt["gpu_or_api_calls"] == 0


def test_committed_receipt_matches_independent_verifier_when_present() -> None:
    path = RESULT / "independent_verification.json"
    if not path.exists():
        pytest.skip("independent receipt has not been generated yet")
    assert json.loads(path.read_text(encoding="utf-8")) == verifier.verify_crosswalk(
        REPO_ROOT,
        CROSSWALK,
    )


def test_hash_mutation_is_rejected(tmp_path: Path) -> None:
    payload = _load()
    payload["evidence_catalog"]["decision_corpus_audit"][
        "sha256_normalized_lf"
    ] = "0" * 64
    mutated = tmp_path / "mutated.json"
    _write(mutated, payload)
    with pytest.raises(verifier.VerificationError, match="hash mismatch"):
        verifier.verify_crosswalk(REPO_ROOT, mutated)


def test_missing_item_is_rejected(tmp_path: Path) -> None:
    payload = _load()
    payload["items"].pop()
    mutated = tmp_path / "missing_item.json"
    _write(mutated, payload)
    with pytest.raises(verifier.VerificationError, match="item set or order"):
        verifier.verify_crosswalk(REPO_ROOT, mutated)


def test_partial_cannot_be_silently_promoted(tmp_path: Path) -> None:
    payload = _load()
    item = next(item for item in payload["items"] if item["id"] == "T.1")
    item["status"] = "PASS_LOCAL"
    payload["status_counts"]["PARTIAL"] -= 1
    payload["status_counts"]["PASS_LOCAL"] += 1
    mutated = tmp_path / "promoted.json"
    _write(mutated, payload)
    with pytest.raises(verifier.VerificationError, match="conservative status changed"):
        verifier.verify_crosswalk(REPO_ROOT, mutated)


def test_aggregate_score_switch_is_rejected(tmp_path: Path) -> None:
    payload = _load()
    payload["interpretation_contract"]["aggregate_compliance_score_reported"] = True
    mutated = tmp_path / "scored.json"
    _write(mutated, payload)
    with pytest.raises(verifier.VerificationError, match="interpretation contract"):
        verifier.verify_crosswalk(REPO_ROOT, mutated)


def test_local_evidence_must_stay_inside_phase1(tmp_path: Path) -> None:
    payload = _load()
    payload["evidence_catalog"]["decision_corpus_audit"]["path"] = (
        "phase1/../AGENTS.md"
    )
    mutated = tmp_path / "traversal.json"
    _write(mutated, payload)
    with pytest.raises(verifier.VerificationError, match="parent traversal"):
        verifier.verify_crosswalk(REPO_ROOT, mutated)


def test_r13_remains_not_applicable_with_random_predictor_analogue(
    tmp_path: Path,
) -> None:
    payload = copy.deepcopy(_load())
    item = next(item for item in payload["items"] if item["id"] == "R.13")
    assert item["status"] == "NOT_APPLICABLE"
    assert "analogue" in item["rationale"].lower()
    item["status"] = "PASS_LOCAL"
    payload["status_counts"].pop("NOT_APPLICABLE")
    payload["status_counts"]["PASS_LOCAL"] += 1
    mutated = tmp_path / "r13_promoted.json"
    _write(mutated, payload)
    with pytest.raises(verifier.VerificationError, match="conservative status changed"):
        verifier.verify_crosswalk(REPO_ROOT, mutated)
