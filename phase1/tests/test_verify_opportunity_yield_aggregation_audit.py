from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pytest

from phase1.verify_opportunity_yield_aggregation_audit import (
    OpportunityYieldAuditVerificationError,
    verify,
)


ROOT = Path(__file__).resolve().parents[2]
CONTRACT = ROOT / "phase1" / "opportunity_yield_aggregation_audit_v1.json"
SOURCE_COMMIT = "9" * 40


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def test_verifier_accepts_exact_contract_and_bound_evidence() -> None:
    receipt = verify(CONTRACT, sha256(CONTRACT), ROOT, SOURCE_COMMIT)
    assert receipt["status"] == "INDEPENDENT_OPPORTUNITY_YIELD_AUDIT_CONTRACT_PASS"
    assert receipt["checks"]["authority_firewall_exact"] is True
    assert receipt["checks"]["arm_range_tv_bound_exact"] is True
    assert receipt["checks"]["contrast_range_tv_bound_exact"] is True
    assert receipt["checks"]["prior_work_boundary_explicit"] is True
    assert receipt["access_and_compute"]["prediction_values_read_or_aggregated"] is False


def test_verifier_rejects_rescue_authority(tmp_path: Path) -> None:
    value = json.loads(CONTRACT.read_text(encoding="utf-8"))
    value["authority"]["may_rescue_failed_primary"] = True
    tampered = tmp_path / "tampered.json"
    tampered.write_text(json.dumps(value), encoding="utf-8")
    with pytest.raises(OpportunityYieldAuditVerificationError, match="authority"):
        verify(tampered, sha256(tampered), ROOT, SOURCE_COMMIT)


def test_verifier_rejects_post_truth_contrasts(tmp_path: Path) -> None:
    value = json.loads(CONTRACT.read_text(encoding="utf-8"))
    value["contrast_audit"]["unregistered_post_truth_contrasts_allowed"] = True
    tampered = tmp_path / "tampered.json"
    tampered.write_text(json.dumps(value), encoding="utf-8")
    with pytest.raises(OpportunityYieldAuditVerificationError, match="contrast"):
        verify(tampered, sha256(tampered), ROOT, SOURCE_COMMIT)


def test_verifier_rejects_evidence_path_drift(tmp_path: Path) -> None:
    value = json.loads(CONTRACT.read_text(encoding="utf-8"))
    value["evidence_bindings"]["structural_dependency_atlas"]["path"] = (
        "phase1/results/structural_dependency_atlas_7cda_20260825/headline_metrics.json"
    )
    tampered = tmp_path / "tampered.json"
    tampered.write_text(json.dumps(value), encoding="utf-8")
    with pytest.raises(OpportunityYieldAuditVerificationError, match="binding"):
        verify(tampered, sha256(tampered), ROOT, SOURCE_COMMIT)
