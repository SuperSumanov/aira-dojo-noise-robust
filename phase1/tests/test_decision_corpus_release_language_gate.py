from __future__ import annotations

from pathlib import Path
import json


ROOT = Path(__file__).resolve().parents[2]
DRAFT = ROOT / "phase1" / "PAPER_DRAFT_DECISION_CORPUS_20260902.md"
BLUEPRINT = ROOT / "phase1" / "PAPER_BLUEPRINT_DECISION_CORPUS_20260902.md"
TABLES = ROOT / "phase1" / "PAPER_TABLES_1_3_DRAFT_20260902.md"
DATACARD = ROOT / "phase1" / "DATACARD_DECISION_CORPUS_DRAFT_20260902.md"
RECEIPT = ROOT / "phase1" / "release_language_gate_postpush_receipt_20260902.json"
CURRENT = ROOT / "phase1" / "CURRENT_DIRECTION.md"


def test_main_manuscript_does_not_claim_uncleared_payload_release() -> None:
    draft = DRAFT.read_text(encoding="utf-8")
    forbidden = (
        "historical v11 release contains",
        "and releases reconstruction manifests",
        "Its released unit is",
        "We release versioned cards",
        "### 3.3 Historical releases and split isolation",
        "The v11 card release is reconstructed",
        "| v11 card release |",
        "Its historical release shows",
    )
    for phrase in forbidden:
        assert phrase not in draft
    assert "Internal manuscript draft v0.7" in draft
    assert "publication of\ncontent-bearing corpus payloads remains conditional" in draft
    assert "data release is not yet legally or\ncontent-cleared" in draft


def test_build_and_release_clearance_vocabulary_is_consistent_across_packet() -> None:
    blueprint = BLUEPRINT.read_text(encoding="utf-8")
    tables = TABLES.read_text(encoding="utf-8")
    datacard = DATACARD.read_text(encoding="utf-8")
    assert "historical v11 build" in blueprint
    assert "public\n> content-bearing payloads remain conditional" in blueprint
    assert "### Panel A. Historical v11 build" in tables
    assert "| v11 card build |" in tables
    assert "immutable internal corpus\n> build versions" in datacard
    assert "**PARTIAL / NOT RELEASE CLEARED**" in datacard


def test_release_gate_language_remains_explicit_not_silently_deleted() -> None:
    draft = DRAFT.read_text(encoding="utf-8").lower()
    required = (
        "content safety, licensing, or release clearance",
        "provider-output terms",
        "final licenses/notices",
        "privacy/path",
        "croissant 1.1",
        "responsible ai 1.0",
    )
    for phrase in required:
        assert phrase in draft


def test_postpush_receipt_binds_language_gate_without_granting_clearance() -> None:
    receipt = json.loads(RECEIPT.read_text(encoding="utf-8"))
    current = CURRENT.read_text(encoding="utf-8")
    assert receipt["exact_public_commit"] == (
        "0f1604e658ac045f9cde9392c5c7981b248c1a7d"
    )
    assert receipt["scope"]["manuscript_version"] == "v0.7"
    assert receipt["scope"]["public_payload_status"] == (
        "PARTIAL / NOT RELEASE CLEARED"
    )
    assert receipt["scope"]["counts_as_distinct_claim_evidence"] is False
    assert receipt["scope"]["release_clearance_changed"] is False
    verified = receipt["successful_verification"]
    assert verified["focused_tests"]["passed"] == 22
    assert verified["full_phase1_tests"]["passed"] == 2161
    assert verified["full_phase1_tests"]["failed"] == 0
    assert sum(
        value
        for key, value in receipt["security"].items()
        if key.endswith("_hits") or key in {
            "gpu_jobs", "paid_api_calls", "model_fits", "base_llm_updates"
        }
    ) == 0
    assert "## 0L0k." in current
    assert "PARTIAL / NOT RELEASE CLEARED" in current
