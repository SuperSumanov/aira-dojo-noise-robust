from __future__ import annotations

import json
import re
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
CONTRACT = ROOT / "phase1/recent_mle_integrity_competitor_delta_v1.json"
NOTE = ROOT / "phase1/RECENT_MLE_INTEGRITY_COMPETITOR_DELTA_20260902.md"
DRAFT = ROOT / "phase1/PAPER_DRAFT_DECISION_CORPUS_20260902.md"
TABLES = ROOT / "phase1/PAPER_TABLES_1_3_DRAFT_20260902.md"
MAP = ROOT / "phase1/RELATED_WORK_CITATION_MAP_20260902.md"
HANDOFF = ROOT / "phase1/SENIOR_HANDOFF_20_DAY_SPRINT_20260902.md"
BIB = ROOT / "phase1/DECISION_CORPUS_REFERENCES_20260902.bib"
RECEIPT = ROOT / "phase1/recent_mle_integrity_competitor_postpush_receipt_20260902.json"
CURRENT = ROOT / "phase1/CURRENT_DIRECTION.md"


def test_primary_source_delta_is_version_and_date_bound() -> None:
    data = json.loads(CONTRACT.read_text(encoding="utf-8"))
    assert data["status"] == "PRIMARY_SOURCE_SCOPE_DELTA_NOT_SCIENTIFIC_EVIDENCE"
    assert data["scope"]["window_start"] == "2026-08-20"
    assert data["scope"]["window_end"] == "2026-09-02"
    assert [(item["arxiv_id"], item["version"]) for item in data["sources"]] == [
        ("2608.19653", "v1"),
        ("2608.30724", "v1"),
    ]
    assert data["positioning"]["absolute_priority_claim_allowed"] is False
    assert data["positioning"]["counts_as_distinct_claim_evidence"] is False
    assert sum(data["security"].values()) == 0


def test_both_competitors_are_routed_through_manuscript_packet() -> None:
    for path in (NOTE, DRAFT, TABLES, MAP, HANDOFF):
        text = path.read_text(encoding="utf-8")
        assert "DeltaML-Bench" in text
        assert "BAITBENCH" in text
    draft = DRAFT.read_text(encoding="utf-8")
    assert "@moukpe2026deltamlbench" in draft
    assert "@prasad2026baitbench" in draft


def test_bibliography_binds_exact_v1_records() -> None:
    text = BIB.read_text(encoding="utf-8")
    for key, arxiv_id in (
        ("moukpe2026deltamlbench", "2608.19653"),
        ("prasad2026baitbench", "2608.30724"),
    ):
        assert len(re.findall(rf"^@\w+\{{{key},", text, flags=re.MULTILINE)) == 1
        assert text.count(arxiv_id) >= 2
    assert "Version 1; submitted 2026-08-20" in text
    assert "Version 1; submitted 2026-08-31" in text


def test_claim_boundary_does_not_overreach_or_change_experiment_authority() -> None:
    note = NOTE.read_text(encoding="utf-8")
    handoff = HANDOFF.read_text(encoding="utf-8")
    assert "not an exhaustive literature" in note
    assert "not new scientific evidence" in note
    assert "config-v2" in note
    assert "不改变 clean-scaling 的 sidecar/closure 门" in handoff
    assert "first trustworthy MLE-agent benchmark" in note


def test_postpush_receipt_preserves_failures_and_final_pass() -> None:
    receipt = json.loads(RECEIPT.read_text(encoding="utf-8"))
    current = CURRENT.read_text(encoding="utf-8")
    assert receipt["exact_public_commit"] == (
        "9989b562888bfdcd7931568b91de8e82bd8c8567"
    )
    assert [item["attempt"] for item in receipt["failure_chain"]] == [
        "r1",
        "r2",
        "r3",
        "r4",
    ]
    assert all(
        item["scientific_result_written"] is False
        for item in receipt["failure_chain"]
    )
    successful = receipt["successful_verification"]
    assert successful["focused_tests"]["passed"] == 46
    assert successful["full_tests"]["passed"] == 2152
    assert successful["full_tests"]["failed"] == 0
    assert successful["credential_filename_hits"] == 0
    assert successful["credential_shape_hits"] == 0
    assert receipt["positioning"]["counts_as_distinct_claim_evidence"] is False
    assert sum(receipt["security"].values()) == 0
    assert "## 0L0i." in current
    assert "不改变\nconfig-v2/closure/GPU 批准门" in current
