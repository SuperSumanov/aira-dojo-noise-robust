from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
RELEASE = ROOT / "phase1/results/decision_corpus_evidence_index_v10_20260902_983bdec"
SOURCE_V9 = (
    ROOT
    / "phase1/results/decision_corpus_evidence_index_v9_20260829_f108812/formal/index.json"
)


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def load(name: str) -> dict:
    value = json.loads((RELEASE / name).read_text(encoding="utf-8"))
    assert isinstance(value, dict)
    return value


def test_release_hashes_match_formal_summary_and_independent_receipt() -> None:
    summary = load("formal_summary.json")
    verification = load("independent_verification.json")
    assert sha256(RELEASE / "index.json") == summary["index_sha256"]
    assert sha256(RELEASE / "independent_verification.json") == summary[
        "independent_verification_sha256"
    ]
    assert verification["index_sha256"] == summary["index_sha256"]
    assert verification["status"] == (
        "INDEPENDENT_CLAIM_DEDUPLICATED_EVIDENCE_INDEX_V10_VERIFIED"
    )
    manifest = (RELEASE / "REMOTE_MANIFEST_SHA256").read_text(encoding="ascii").strip()
    assert re.fullmatch(r"[0-9a-f]{64}", manifest)
    assert manifest == "0c98fde448dee549d6660e3482f9cdfb27f5d21e214c5e04c96162bc0ee55d00"


def test_release_manifest_covers_every_public_payload_exactly() -> None:
    rows = {}
    for line in (RELEASE / "SHA256SUMS").read_text(encoding="ascii").splitlines():
        match = re.fullmatch(r"([0-9a-f]{64})  ([^/]+)", line)
        assert match is not None
        digest, name = match.groups()
        assert name not in rows
        rows[name] = digest
    assert set(rows) == {
        "REMOTE_MANIFEST_SHA256",
        "README.md",
        "failed_v1_summary.json",
        "formal_summary.json",
        "independent_verification.json",
        "index.json",
        "postpush_summary.json",
    }
    for name, digest in rows.items():
        assert sha256(RELEASE / name) == digest


def test_release_preserves_all_v9_entries_and_provisional_status() -> None:
    index = load("index.json")
    source = json.loads(SOURCE_V9.read_text(encoding="utf-8"))
    assert index["entries"][:16] == source["entries"]
    assert index["status"] == source["status"]
    assert index["claim_accounting"]["source_distinct_entry_count"] == 16
    assert index["claim_accounting"]["source_v9_status_preserved"] is True


def test_release_adds_exactly_four_distinct_claim_entries() -> None:
    index = load("index.json")
    assert [entry["name"] for entry in index["entries"][16:]] == [
        "archive_disposition_longitudinal",
        "archive_granularity_retention",
        "prospective_wl_snapshot_chain_517",
        "archive_rejection_support_census",
    ]
    assert all(
        entry["counts_as_distinct_claim_evidence"] is True
        for entry in index["entries"][16:]
    )
    assert index["claim_accounting"]["total_distinct_entry_count"] == 20
    assert index["claim_accounting"]["distinct_entries_added"] == 4


def test_support_floor_is_only_a_reconstruction_with_nineteen_exact_fields() -> None:
    index = load("index.json")
    distinct_names = {entry["name"] for entry in index["entries"]}
    assert len(index["reconstructions"]) == 1
    reconstruction = index["reconstructions"][0]
    assert reconstruction["name"] not in distinct_names
    assert reconstruction["counts_as_distinct_claim_evidence"] is False
    assert reconstruction["reproduction_of"] == "archive_granularity_retention"
    assert index["claim_accounting"]["duplicate_claims_counted_as_distinct"] == 0
    assert index["claim_accounting"]["shared_numeric_fields_crosschecked"] == 19
    assert index["claim_deduplication"]["reconstruction_numeric_crosscheck"] == {
        "target_entry": "archive_granularity_retention",
        "reconstruction_record": "archive_rejection_support_floor_reconstruction",
        "shared_numeric_fields_exact": 19,
        "counts_as_distinct_claim_evidence": False,
        "incremental_descriptive_component_is_independent_confirmation": False,
    }


def test_formal_gates_and_failed_preworktree_attempt_are_recorded() -> None:
    summary = load("formal_summary.json")
    failure = load("failed_v1_summary.json")
    postpush = load("postpush_summary.json")
    assert summary["status"] == "FORMAL_CLAIM_DEDUPLICATED_EVIDENCE_INDEX_V10_COMPLETE"
    assert summary["focused_test_tail"] == "105 passed in 3.31s"
    assert summary["full_test_tail"] == "1988 passed, 48 warnings in 115.29s (0:01:55)"
    assert summary["builder_ab_byte_identical"] is True
    assert summary["verifier_ab_byte_identical"] is True
    assert summary["input_hashes_before_after_identical"] is True
    assert summary["forbidden_open_hits"] == 0
    assert summary["network_calls"] == 0
    assert summary["credential_filename_hits"] == 0
    assert summary["credential_content_hits"] == 0
    assert failure["status"] == "INVALID_SOURCE_COMMIT_LAUNCH_FAIL_BEFORE_WORKTREE"
    assert failure["failed_rc"] == 128
    assert failure["worktree_created"] is False
    assert failure["index_files_created"] == 0
    assert failure["verifier_files_created"] == 0
    assert failure["complete_marker_created"] is False
    assert postpush["status"] == "FRESH_PUBLIC_CHECKOUT_POSTPUSH_PASS"
    assert postpush["source_commit"] == (
        "492fad67a43c2e4ddd4aaad3d290d8c2570b41f9"
    )
    assert postpush["root_mode"] == "0500"
    assert postpush["file_count"] == 41
    assert postpush["complete"] is True
    assert postpush["failed_rc_present"] is False
    assert postpush["preflight_lines"] == 13
    assert postpush["input_hash_lines"] == 13
    assert postpush["input_hashes_before_after_identical"] is True
    assert postpush["builder_ab_and_trace_byte_identical"] is True
    assert postpush["verifier_ab_and_trace_byte_identical"] is True
    assert postpush["focused_test_tail"] == "112 passed in 3.17s"
    assert postpush["full_test_tail"] == (
        "1995 passed, 48 warnings in 124.38s (0:02:04)"
    )
    assert postpush["index_sha256"] == summary["index_sha256"]
    assert postpush["independent_verification_sha256"] == summary[
        "independent_verification_sha256"
    ]
    assert postpush["remote_manifest_sha256"] == (
        "303a350b594f67377fb754c523bb172c2c73d1a086f978064cb3b1ce2042e6e8"
    )
    assert postpush["remote_manifest_members"] == 39
    assert postpush["remote_manifest_all_exact"] is True
    assert postpush["forbidden_open_hits"] == 0
    assert postpush["network_calls"] == 0
    assert postpush["credential_filename_hits"] == 0
    assert postpush["credential_content_hits"] == 0
    assert postpush["prospective_values_read"] is False
    assert postpush["raw_senior_archives_opened"] is False
    assert postpush["gpu_api_model_fit_base_update"] == [0, 0, 0, 0]


def test_readme_keeps_claim_and_security_boundaries() -> None:
    readme = (RELEASE / "README.md").read_text(encoding="utf-8")
    assert "does **not** count as a second scientific result" in readme
    assert re.search(r"performs\s+no\s+new\s+scientific\s+readout", readme)
    assert "0/0/0/0" in readme
    assert "Prospective values, raw senior" in readme
