from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path

from phase1 import build_decision_corpus_evidence_index_v8 as builder
from phase1 import verify_decision_corpus_evidence_index_v8 as verifier


ROOT = Path(__file__).resolve().parents[2]
PACKAGE = (
    ROOT
    / "phase1"
    / "results"
    / "decision_corpus_evidence_index_v8_887_20260828_3d30826"
)
FORMAL = PACKAGE / "formal"
PROTOCOL = ROOT / "phase1" / "decision_corpus_evidence_index_v8_protocol_v1.json"
PROTOCOL_SHA256 = "a463a6e7ede5bb9b46dbe6081ae46d26d6c2e8410e858acf9d022c642633deda"


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


def test_formal_manifest_is_complete_and_exact() -> None:
    manifest_path = FORMAL / "SHA256SUMS"
    expected = manifest(manifest_path)
    actual = {
        path.relative_to(FORMAL).as_posix()
        for path in FORMAL.rglob("*")
        if path.is_file() and path.name != "SHA256SUMS"
    }
    assert set(expected) == actual
    assert len(expected) == 34
    for name, expected_sha in expected.items():
        assert digest(FORMAL / name) == expected_sha
    assert digest(manifest_path) == (
        "73a5884be6fffaed9d8ca3cb7972226c95bd1db3627cd1e330931dfd8f047b06"
    )


def test_published_index_rebuilds_and_independent_verifier_matches() -> None:
    published_index = load(FORMAL / "index.json")
    rebuilt = builder.build_index(ROOT, PROTOCOL, PROTOCOL_SHA256)
    assert published_index == rebuilt
    receipt = load(FORMAL / "independent_verification.json")
    assert receipt == verifier.verify_candidate(ROOT, PROTOCOL, FORMAL / "index.json")
    assert (FORMAL / "index_a.json").read_bytes() == (FORMAL / "index_b.json").read_bytes()
    assert (FORMAL / "verifier_a.json").read_bytes() == (FORMAL / "verifier_b.json").read_bytes()


def test_source_bindings_and_formal_counts_are_exact() -> None:
    bindings = load(PACKAGE / "source_bindings.json")
    summary = load(FORMAL / "formal_summary.json")
    sources = bindings["source_sha256"]
    assert digest(PROTOCOL) == sources["protocol"] == PROTOCOL_SHA256
    assert digest(ROOT / "phase1" / "build_decision_corpus_evidence_index_v8.py") == sources["builder"]
    assert digest(ROOT / "phase1" / "verify_decision_corpus_evidence_index_v8.py") == sources["verifier"]
    assert digest(ROOT / "phase1" / "tests" / "test_decision_corpus_evidence_index_v8.py") == sources["tests"]
    assert digest(ROOT / "phase1" / "finalize_historical_release_future_identifier_erased_package.py") == sources[
        "complete_release_packager"
    ]
    assert digest(ROOT / "phase1" / "historical_release_future_identifier_erased_package_protocol_v1.json") == sources[
        "complete_release_package_protocol"
    ]
    assert summary["source_commit"] == bindings["formal_source_commit"]
    assert summary["index_sha256"] == bindings["formal_sha256"]["index"]
    assert summary["independent_verification_sha256"] == bindings["formal_sha256"][
        "independent_verification"
    ]
    assert digest(FORMAL / "formal_summary.json") == bindings["formal_sha256"]["formal_summary"]
    assert (summary["entry_count"], summary["inherited_entry_count"], summary["appended_entry_count"]) == (
        16,
        14,
        2,
    )
    assert (summary["artifact_count"], summary["bound_file_count"], summary["json_assertion_count"]) == (
        43,
        3,
        499,
    )


def test_status_claim_boundaries_and_security_are_preserved() -> None:
    summary = load(FORMAL / "formal_summary.json")
    verification = load(FORMAL / "independent_verification.json")
    assert summary["classification"] == verification["classification"] == (
        "ZERO_IDENTIFIER_ERASED_RELEASE_LINKS"
    )
    assert summary["index_status"] == verification["index_status"] == (
        "PROVISIONAL_TEMPORAL_SPLIT_CERTIFIED_EVIDENCE_STACK_AWAITING_FIRST960"
    )
    assert summary["complete_release_primary_near_duplicate_pairs"] == 0
    assert summary["complete_release_strict_near_duplicate_pairs"] == 0
    assert summary["all_pre_registered_gates_passed"] is True
    assert summary["builder_ab_byte_identical"] is True
    assert summary["verifier_ab_byte_identical"] is True
    assert summary["production_trace_forbidden_path_hits"] == 0
    assert summary["prospective_label_grade_outcome_or_prediction_values_read"] is False
    assert summary["accuracy_effect_or_search_utility_computed"] is False
    assert summary["raw_senior_archives_opened"] is False
    assert summary["gpu_api_model_fit_base_update"] == [0, 0, 0, 0]
    assert (FORMAL / "forbidden_open_hits.txt").read_bytes() == b""
    assert (FORMAL / "credential_filename_hits.txt").read_text().strip() == "0"
    assert (FORMAL / "credential_content_file_hits.txt").read_text().strip() == "0"
    boundary = summary["claim_boundary"]
    assert boundary["semantic_clone_absence_proven"] is False
    assert boundary["unknown_pretraining_contamination_absence_proven"] is False
    assert boundary["first960_or_closure_completed"] is False


def test_formal_test_receipts_are_preserved() -> None:
    assert "30 passed" in (FORMAL / "focused_tests.txt").read_text(encoding="utf-8")
    assert "1288 passed, 47 warnings" in (FORMAL / "full_tests.txt").read_text(encoding="utf-8")
