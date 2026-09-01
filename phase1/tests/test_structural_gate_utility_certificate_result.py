from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
RESULT = ROOT / "phase1/results/structural_gate_utility_certificate_20260902_a0e04d2"


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def load(name: str) -> dict:
    value = json.loads((RESULT / name).read_text(encoding="utf-8"))
    assert isinstance(value, dict)
    return value


def manifest(path: Path) -> dict[str, str]:
    rows: dict[str, str] = {}
    for line in path.read_text(encoding="ascii").splitlines():
        match = re.fullmatch(r"([0-9a-f]{64})  (?:\./)?([^/]+)", line)
        assert match is not None
        digest, name = match.groups()
        assert name not in rows
        rows[name] = digest
    return rows


def test_release_binds_exact_formal_certificate_and_verifier() -> None:
    summary = load("formal_summary.json")
    verifier = load("independent_verification.json")
    assert summary["source_commit"] == "a0e04d27bcf900c2a1293f8ffad38d5104f6d3a3"
    assert sha256(RESULT / "certificate.json") == (
        "b50e99e23ac2202b29c2a710922133bd972768e7dcf30d48a83825c7972b1f55"
    )
    assert sha256(RESULT / "certificate.json") == summary["certificate_sha256"]
    assert sha256(RESULT / "independent_verification.json") == (
        "9ec64e099c5a90f9da0128fa07cfe00e254f31f6c4291d43367ec5c69581d055"
    )
    assert sha256(RESULT / "independent_verification.json") == summary[
        "independent_verification_sha256"
    ]
    assert verifier["candidate_sha256"] == summary["certificate_sha256"]


def test_remote_manifest_is_exact_and_contains_formal_payloads() -> None:
    remote = manifest(RESULT / "remote_formal_SHA256SUMS")
    assert len(remote) == 37
    assert remote["certificate_a.json"] == sha256(RESULT / "certificate.json")
    assert remote["verifier_a.json"] == sha256(RESULT / "independent_verification.json")
    assert remote["formal_summary.json"] == sha256(RESULT / "formal_summary.json")
    expected = (RESULT / "REMOTE_MANIFEST_SHA256").read_text(encoding="ascii").strip()
    assert expected == "1078227f2b9591ae39041da26b9c2cea4930c4775c15799f1b19d36c15d45d82"
    assert sha256(RESULT / "remote_formal_SHA256SUMS") == expected


def test_public_manifest_covers_every_release_file() -> None:
    rows = manifest(RESULT / "SHA256SUMS")
    expected = {
        path.name for path in RESULT.iterdir() if path.is_file() and path.name != "SHA256SUMS"
    }
    assert set(rows) == expected
    for name, digest in rows.items():
        assert sha256(RESULT / name) == digest


def test_partition_and_positive_claim_are_exact_but_derived() -> None:
    certificate = load("certificate.json")
    summary = load("formal_summary.json")
    verifier = load("independent_verification.json")
    assert certificate["population"] == {
        "accepted_archives": 133,
        "distinct_rejected_competitions": 7,
        "eligible_endpoints": 13581,
        "eligible_runs": 517,
        "observed_archives": 283,
        "structural_rejected_archives": 14,
    }
    assert certificate["derived_partition"] == {
        "accounted_affected_competitions": 7,
        "accounting_complete": True,
        "invalid_only_trigger_competitions": 1,
        "observed_last_usable_support_elimination_competitions": 0,
        "retained_usable_support_competitions": 6,
    }
    assert certificate["retained_support"]["minimum_eligible_runs_per_retained_competition"] == 4
    assert certificate["retained_support"]["minimum_eligible_endpoints_per_retained_competition"] == 50
    assert certificate["unique_no_support_trigger"]["checkpoint_runs"] == 0
    assert certificate["decision"]["counts_as_distinct_claim_evidence"] is False
    assert summary["counts_as_distinct_claim_evidence"] is False
    assert verifier["counts_as_distinct_claim_evidence"] is False


def test_formal_security_reproducibility_and_failed_attempt_boundaries() -> None:
    summary = load("formal_summary.json")
    history = load("failure_history.json")
    assert summary["focused_test_tail"] == "12 passed in 1.91s"
    assert summary["full_test_tail"] == "2013 passed, 48 warnings in 140.68s (0:02:20)"
    assert summary["builder_ab_byte_identical"] is True
    assert summary["verifier_ab_byte_identical"] is True
    assert summary["input_hashes_before_after_identical"] is True
    assert summary["forbidden_open_hits"] == 0
    assert summary["network_calls"] == 0
    assert summary["credential_filename_hits"] == 0
    assert summary["credential_content_hits"] == 0
    assert summary["prospective_values_read"] is False
    assert summary["raw_senior_archives_opened"] is False
    assert summary["gpu_api_model_fit_base_update"] == [0, 0, 0, 0]
    assert len(history["failed_attempts"]) == 3
    assert history["failed_attempt_scientific_outputs_created"] == 0
    assert history["failed_attempts_count_as_claim_evidence"] is False
    assert history["successful_attempt"]["complete_marker_created"] is True
    assert history["successful_attempt"]["independent_postflight"] == "PASS"


def test_readme_keeps_the_paper_safe_boundary() -> None:
    readme = (RESULT / "README.md").read_text(encoding="utf-8")
    assert "support-preserving quality gate" in readme
    assert "不是新的独立实验" in readme
    assert "不能宣称" in readme
    assert "counts_as_distinct_claim_evidence=false" in readme
    assert "0/0/0/0" in readme
