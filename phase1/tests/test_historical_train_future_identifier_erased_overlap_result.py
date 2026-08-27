from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path


ROOT = (
    Path(__file__).parents[1]
    / "results"
    / "historical_train_future_identifier_erased_overlap_ad0b_20260827_065d0b5"
)
EMPTY_SHA = hashlib.sha256(b"").hexdigest()


def _sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _json(name: str) -> dict:
    return json.loads((ROOT / name).read_text(encoding="utf-8"))


def _manifest(name: str, *, remote: bool) -> dict[str, str]:
    rows: dict[str, str] = {}
    prefix = r"\./" if remote else ""
    for line in (ROOT / name).read_text(encoding="utf-8").splitlines():
        match = re.fullmatch(rf"([0-9a-f]{{64}})  {prefix}(.+)", line)
        assert match is not None
        rows[match.group(2)] = match.group(1)
    return rows


def test_formal_summary_and_receipts_agree() -> None:
    summary = _json("formal_summary.json")
    producer = _json("producer_receipt.json")
    verifier = _json("independent_verification.json")
    recheck = _json("independent_recheck.json")

    assert summary["source_commit"] == "065d0b56fdc366d05faf723ef03938e7f7a913f2"
    assert summary["snapshot_sha256"] == (
        "ad0b624d636cb5e89f94d8887a7abe99f7b9ef6ce77bbde7da704b0275dedb0e"
    )
    assert summary["historical_endpoints"] == producer["historical_scope"]["union_endpoints"] == 5519
    assert summary["historical_runs"] == producer["historical_scope"]["union_runs"] == 333
    assert summary["prospective_runs"] == producer["prospective_scope"]["observed_runs"] == 404
    assert (
        summary["prospective_endpoints"]
        == producer["prospective_scope"]["observed_endpoints"]
        == 11310
    )
    assert summary["prospective_fingerprinted_endpoints"] == 11299
    assert summary["prospective_fingerprint_coverage"] == 0.999027409372237
    assert summary["primary_candidate_pairs"] == verifier["primary_candidate_pairs"] == 5923921
    assert summary["primary_near_duplicate_pairs"] == verifier["primary_near_duplicate_pairs"] == 0
    assert summary["strict_near_duplicate_pairs"] == verifier["strict_near_duplicate_pairs"] == 0
    assert producer["primary_jaccard_0_85"]["edge_digest_sha256"] == EMPTY_SHA
    assert producer["strict_jaccard_0_95"]["edge_digest_sha256"] == EMPTY_SHA
    assert summary["strong_low_identifier_erased_overlap_support"] is True
    assert all(summary["gate_checks"].values())
    assert summary["closure_rerun_required"] is True
    assert summary["semantic_equivalence_proven"] is False
    assert summary["pretraining_contamination_absence_proven"] is False
    assert summary["prospective_outcomes_read"] is False
    assert summary["prediction_values_read"] is False
    assert verifier["imports_new_producer_code"] is False
    assert verifier["producer_aggregate_matches"] is True
    assert recheck["manifest_payload_files"] == 24
    assert recheck["producer_ab_byte_identical"] is True
    assert recheck["verifier_ab_byte_identical"] is True
    assert summary["focused_tests"]["passed"] == recheck["focused_tests_passed"] == 29
    assert summary["full_tests"]["passed"] == recheck["full_tests_passed"] == 1212
    assert summary["forbidden_path_hits"] == recheck["forbidden_path_hits"] == 0
    assert summary["credential_hits"] == recheck["credential_file_hits"] == 0
    assert summary["gpu_api_model_fit_base_update"] == [0, 0, 0, 0]


def test_downloaded_artifacts_match_remote_manifests() -> None:
    rows = _manifest("remote_formal_SHA256SUMS", remote=True)
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
    assert _sha(ROOT / "producer_receipt.json") == (
        "409c9f046917a98f6bf26b6cac87fa1e688bccff68daf41fd9930f268d7182b6"
    )
    assert _sha(ROOT / "independent_verification.json") == (
        "866536e98138e0ad60929afe8324e8f64a98c05784e351eb6de13a3cc8fa44e0"
    )
    recheck_rows = _manifest("remote_recheck_SHA256SUMS", remote=True)
    assert _sha(ROOT / "independent_recheck.json") == recheck_rows["independent_recheck.json"]


def test_public_package_manifest_is_complete() -> None:
    expected = _manifest("SHA256SUMS", remote=False)
    actual = {
        path.name: _sha(path)
        for path in ROOT.iterdir()
        if path.is_file() and path.name != "SHA256SUMS"
    }
    assert expected == actual
