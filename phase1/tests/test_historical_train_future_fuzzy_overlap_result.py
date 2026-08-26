from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path


ROOT = (
    Path(__file__).parents[1]
    / "results"
    / "historical_train_future_fuzzy_overlap_8579_20260826_f9c6de2"
)
EMPTY_SHA = hashlib.sha256(b"").hexdigest()


def _sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _json(name: str) -> dict:
    return json.loads((ROOT / name).read_text(encoding="utf-8"))


def test_formal_summary_and_receipts_agree() -> None:
    summary = _json("formal_summary.json")
    producer = _json("producer_receipt.json")
    verifier = _json("independent_verification.json")
    recheck = _json("independent_recheck.json")
    assert summary["source_commit"] == "f9c6de27afd933d9ceee04e67acbd51d25947798"
    assert summary["snapshot_sha256"] == "8579d7cd32091a11089b935217f7189e321b1d623dbaa69233182ba2fedd9248"
    assert summary["historical_endpoints"] == producer["historical_scope"]["union_endpoints"] == 5519
    assert summary["prospective_endpoints"] == producer["prospective_scope"]["observed_endpoints"] == 10683
    assert summary["prospective_fingerprinted_endpoints"] == 10674
    assert summary["primary_candidate_pairs"] == verifier["primary_candidate_pairs"] == 2880
    assert summary["primary_near_duplicate_pairs"] == verifier["primary_near_duplicate_pairs"] == 0
    assert summary["strict_near_duplicate_pairs"] == verifier["strict_near_duplicate_pairs"] == 0
    assert producer["primary_jaccard_0_85"]["edge_digest_sha256"] == EMPTY_SHA
    assert producer["strict_jaccard_0_95"]["edge_digest_sha256"] == EMPTY_SHA
    assert summary["strong_low_historical_train_future_overlap_support"] is True
    assert all(summary["gate_checks"].values())
    assert verifier["imports_new_producer_code"] is False
    assert verifier["producer_aggregate_matches"] is True
    assert recheck["manifest_payload_files"] == 21
    assert recheck["producer_ab_byte_identical"] is True
    assert recheck["verifier_ab_byte_identical"] is True
    assert summary["focused_tests"]["passed"] == recheck["focused_tests_passed"] == 14
    assert summary["full_tests"]["passed"] == recheck["full_tests_passed"] == 1182
    assert summary["forbidden_path_hits"] == recheck["forbidden_path_hits"] == 0
    assert summary["credential_hits"] == recheck["credential_file_hits"] == 0
    assert summary["gpu_api_model_fit_base_update"] == [0, 0, 0, 0]


def test_downloaded_artifacts_match_remote_formal_manifest() -> None:
    rows = {}
    for line in (ROOT / "remote_formal_SHA256SUMS").read_text(encoding="utf-8").splitlines():
        match = re.fullmatch(r"([0-9a-f]{64})  \./(.+)", line)
        assert match is not None
        rows[match.group(2)] = match.group(1)
    mapping = {
        "formal_summary.json": "formal_summary.json",
        "producer_a.json": "producer_receipt.json",
        "verification_a.json": "independent_verification.json",
        "focused_tests.txt": "focused_tests.txt",
        "full_tests.txt": "full_tests.txt",
        "preflight_13.txt": "preflight_13.txt",
        "access_attestation.txt": "access_attestation.txt",
        "producer_a.time.txt": "producer_resource.txt",
        "verifier_a.time.txt": "verifier_resource.txt",
    }
    for remote_name, local_name in mapping.items():
        assert _sha(ROOT / local_name) == rows[remote_name]
    assert _sha(ROOT / "producer_receipt.json") == "fbba6dbe10937b7376b4bb2b052934bcf1b47cf16610ab2be872d0101ae28194"
    assert _sha(ROOT / "independent_verification.json") == "7f3c0c7be582efdf4c747d7fe9a7cd7d47d33564788e62dabea45374180ee188"
    recheck_rows = {}
    for line in (ROOT / "remote_recheck_SHA256SUMS").read_text(
        encoding="utf-8"
    ).splitlines():
        match = re.fullmatch(r"([0-9a-f]{64})  \./(.+)", line)
        assert match is not None
        recheck_rows[match.group(2)] = match.group(1)
    assert _sha(ROOT / "independent_recheck.json") == recheck_rows[
        "independent_recheck.json"
    ]


def test_public_package_manifest_is_complete() -> None:
    expected = {}
    for line in (ROOT / "SHA256SUMS").read_text(encoding="utf-8").splitlines():
        match = re.fullmatch(r"([0-9a-f]{64})  (.+)", line)
        assert match is not None
        expected[match.group(2)] = match.group(1)
    actual = {
        path.name: _sha(path)
        for path in ROOT.iterdir()
        if path.is_file() and path.name != "SHA256SUMS"
    }
    assert expected == actual
