from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path

from phase1 import build_decision_corpus_evidence_index_v7 as builder
from phase1 import decision_corpus_evidence_index_v7_schema as schema
from phase1 import verify_decision_corpus_evidence_index_v7 as verifier


REPO_ROOT = Path(__file__).resolve().parents[2]
RESULT = (
    REPO_ROOT
    / "phase1/results/decision_corpus_evidence_index_v7_20260826_a83bebf"
)


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def manifest(path: Path) -> dict[str, str]:
    rows: dict[str, str] = {}
    for line in path.read_text(encoding="utf-8").splitlines():
        match = re.fullmatch(r"([0-9a-f]{64}) [ *](.+)", line)
        assert match is not None
        rows[match.group(2).removeprefix("./")] = match.group(1)
    return rows


def test_published_package_manifest_covers_every_payload() -> None:
    expected = manifest(RESULT / "SHA256SUMS")
    actual_files = {
        path.name for path in RESULT.iterdir() if path.is_file() and path.name != "SHA256SUMS"
    }
    assert set(expected) == actual_files
    assert len(expected) == 9
    for relative, expected_sha in expected.items():
        assert sha256(RESULT / relative) == expected_sha


def test_published_index_and_receipt_match_independent_reconstruction() -> None:
    index = json.loads((RESULT / "index.json").read_text(encoding="utf-8"))
    assert index == builder.build_index(
        REPO_ROOT, REPO_ROOT / schema.SOURCE_INDEX_RELATIVE
    )
    receipt = json.loads(
        (RESULT / "independent_verification.json").read_text(encoding="utf-8")
    )
    assert receipt == verifier.verify_index(REPO_ROOT, RESULT / "index.json")


def test_formal_summary_binds_exact_public_payloads_and_counts() -> None:
    summary = json.loads((RESULT / "formal_summary.json").read_text(encoding="utf-8"))
    assert summary["source_commit"] == "a83bebfdb8dcf59bea21a1b84269b2e87bf7a02e"
    assert summary["index_sha256"] == sha256(RESULT / "index.json")
    assert summary["independent_verification_sha256"] == sha256(
        RESULT / "independent_verification.json"
    )
    assert (
        summary["entry_count"],
        summary["artifact_count"],
        summary["bound_file_count"],
        summary["json_assertion_count"],
    ) == (14, 37, 3, 434)
    assert summary["builder_ab_byte_identical"] is True
    assert summary["verifier_ab_byte_identical"] is True
    assert summary["production_trace_forbidden_path_hits"] == 0
    assert summary["prediction_values_read_or_aggregated"] is False
    assert summary["prospective_outcomes_read"] is False


def test_remote_manifest_binds_all_copied_formal_files() -> None:
    remote = manifest(RESULT / "remote_formal_SHA256SUMS")
    mapping = {
        "index_a.json": "index.json",
        "verification_a.json": "independent_verification.json",
        "formal_summary.json": "formal_summary.json",
        "preflight_13.txt": "preflight_13.txt",
        "focused_tests.txt": "focused_tests.txt",
        "full_tests.txt": "full_tests.txt",
        "access_attestation.txt": "access_attestation.txt",
    }
    for remote_name, local_name in mapping.items():
        assert remote[remote_name] == sha256(RESULT / local_name)


def test_readme_preserves_claim_boundary() -> None:
    readme = (RESULT / "README.md").read_text(encoding="utf-8")
    assert "single-drop robust magnitude" in readme
    assert "predictor accuracy/effect/search utility" in readme
    assert "不是新的 predictor 效果结果" in readme
