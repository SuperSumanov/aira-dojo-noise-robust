import hashlib
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
RESULT = ROOT / "phase1" / "results" / "opportunity_yield_aggregation_audit_v1_20260826"
POSTPUSH = (
    ROOT
    / "phase1"
    / "results"
    / "opportunity_yield_aggregation_audit_postpush_bad6ec5_20260826"
)


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def test_formal_summary_binds_independent_receipt_and_scope() -> None:
    summary = json.loads((RESULT / "formal_summary.json").read_text(encoding="utf-8"))
    receipt = json.loads((RESULT / "independent_verification.json").read_text(encoding="utf-8"))

    assert summary["status"] == "FORMAL_OPPORTUNITY_YIELD_AGGREGATION_AUDIT_PASS"
    assert summary["source_commit"] == receipt["source_commit"]
    assert summary["contract_sha256"] == receipt["contract_sha256"]
    assert summary["independent_verification_sha256"] == _sha256(
        RESULT / "independent_verification.json"
    )
    assert summary["claim_boundary"]["effect_result"] is False
    assert summary["claim_boundary"]["existing_primary_or_inference_superseded"] is False
    assert summary["claim_boundary"]["informative_cluster_size_theory_claimed_novel"] is False
    assert all(receipt["checks"].values())
    assert not any(receipt["access_and_compute"].values())


def test_readme_and_preflight_lock_two_stage_non_rescue_boundary() -> None:
    readme = (RESULT / "README.md").read_text(encoding="utf-8")
    preflight = (RESULT / "preflight_13.txt").read_text(encoding="utf-8")

    for token in (
        "structural opportunity yield",
        "informative retention",
        "NOT_IDENTIFIABLE_FULL_TASK_UNIVERSE",
        "不能挽救失败 primary",
        "informative cluster size",
    ):
        assert token in readme
    assert len([line for line in preflight.splitlines() if line.startswith("PREFLIGHT_")]) == 13
    assert "no prospective state path" in preflight
    assert "not predictor accuracy" in preflight


def test_inner_sha256_manifest_is_complete_and_exact() -> None:
    rows = {}
    for line in (RESULT / "SHA256SUMS").read_text(encoding="utf-8").splitlines():
        digest, relative = line.split("  ./", maxsplit=1)
        rows[relative] = digest

    assert set(rows) == {
        "README.md",
        "formal_summary.json",
        "independent_verification.json",
        "preflight_13.txt",
    }
    for relative, digest in rows.items():
        assert _sha256(RESULT / relative) == digest


def test_postpush_receipt_binds_public_commit_remote_manifest_and_access() -> None:
    summary = json.loads((POSTPUSH / "formal_summary.json").read_text(encoding="utf-8"))
    assert summary["status"] == "OPPORTUNITY_YIELD_AGGREGATION_AUDIT_POSTPUSH_PASS"
    assert summary["validated_public_commit"] == "bad6ec5428c62b6a213b0d75fa0d1e58d858b5d4"
    assert summary["formal_execution"]["sha256sums_file_sha256"] == _sha256(
        POSTPUSH / "remote_SHA256SUMS"
    )
    assert summary["formal_execution"]["verifier_equals_committed_receipt"] is True
    assert summary["claim_boundary"]["effect_result"] is False
    assert not any(summary["access_and_compute"].values())

    remote_rows = (POSTPUSH / "remote_SHA256SUMS").read_text(encoding="utf-8")
    assert remote_rows.count("0054e5fceaf326b67f773d44109841ce576db59c9efd959671e97b6b3357e973") == 2
    assert "./status_before.txt" in remote_rows
    assert "./status_after.txt" in remote_rows
    assert _sha256(POSTPUSH / "preflight_13.txt") == (
        "393410eab536f12927e276ebf088a2e4f926c6e8f4c44123c921e352e67072e3"
    )
    assert _sha256(POSTPUSH / "access_attestation.txt") == (
        "1fcdb58246e7f3d87da39ff1ed1cc973fa5214a1be694bbb4a807fdbd9af5e25"
    )


def test_postpush_local_manifest_is_complete_and_exact() -> None:
    rows = {}
    for line in (POSTPUSH / "SHA256SUMS").read_text(encoding="utf-8").splitlines():
        digest, relative = line.split("  ./", maxsplit=1)
        rows[relative] = digest

    assert set(rows) == {
        "README.md",
        "access_attestation.txt",
        "formal_summary.json",
        "preflight_13.txt",
        "remote_SHA256SUMS",
    }
    for relative, digest in rows.items():
        assert _sha256(POSTPUSH / relative) == digest
