from __future__ import annotations

import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
MAP = ROOT / "phase1" / "RELATED_WORK_CITATION_MAP_20260902.md"
DRAFT = ROOT / "phase1" / "PAPER_DRAFT_DECISION_CORPUS_20260902.md"
BLUEPRINT = ROOT / "phase1" / "PAPER_BLUEPRINT_DECISION_CORPUS_20260902.md"
HANDOFF = ROOT / "phase1" / "SENIOR_HANDOFF_20_DAY_SPRINT_20260902.md"
RECEIPT = ROOT / "phase1" / "direct_competitor_map_postpush_receipt_20260902.json"


def test_primary_direct_competitors_are_not_omitted() -> None:
    for path in (MAP, DRAFT, BLUEPRINT, HANDOFF):
        text = path.read_text(encoding="utf-8")
        assert "FOREAGENT" in text
        assert "AI Research Preference Models" in text
        assert "2601.05930" in text
        assert "2608.13940" in text


def test_claim_withdrawals_cover_preference_and_system_priority() -> None:
    map_text = MAP.read_text(encoding="utf-8")
    draft = DRAFT.read_text(encoding="utf-8")
    assert "first pre-execution comparison of two ML-agent solutions" in map_text
    assert "first preference-guided child selection in AIRA-dojo" in map_text
    assert "first pre-execution MLE preference mechanism" in draft
    assert "first preference-guided AIRA-dojo speedup" in draft


def test_competitor_units_and_biases_remain_distinct() -> None:
    map_text = MAP.read_text(encoding="utf-8")
    draft = DRAFT.read_text(encoding="utf-8")
    for text in (map_text, draft):
        assert "18,438" in text
        assert "1,000" in text
        assert "0.01" in text
        assert "off-policy" in text
        assert "subtree" in text
    assert "does not supersede RPM's system result" in draft


def test_table4b_requires_named_rpm_transfer_boundary() -> None:
    map_text = MAP.read_text(encoding="utf-8")
    draft = DRAFT.read_text(encoding="utf-8")
    blueprint = BLUEPRINT.read_text(encoding="utf-8")
    assert "RPM-style inference-only transfer baseline" in map_text
    assert "not be labeled “RPM reproduction.”" in map_text
    assert "RPM-style inference-only prompt-transfer row" in draft
    assert "RPM exact reproduction/transfer 必须分名" in blueprint
    assert "predictions remain\nescrowed" in draft


def test_citation_consolidation_is_not_new_scientific_evidence() -> None:
    map_text = MAP.read_text(encoding="utf-8")
    handoff = HANDOFF.read_text(encoding="utf-8")
    assert "not a newly discovered scientific result" in map_text
    assert "不是新科学结果" in handoff


def test_postpush_receipt_binds_exact_commit_and_no_result_read() -> None:
    receipt = json.loads(RECEIPT.read_text(encoding="utf-8"))
    assert receipt["exact_public_commit"] == "397ac77dcfd289361ecdc36dbf8846a2134c9dee"
    assert receipt["focused_tests"]["passed"] == 13
    assert receipt["focused_tests"]["failed"] == 0
    assert receipt["full_tests"]["passed"] == 2092
    assert receipt["full_tests"]["failed"] == 0
    assert receipt["full_tests"]["warnings"] == 48
    assert receipt["pretest_false_positive"]["tests_started"] is False
    assert receipt["positioning_state"]["counts_as_distinct_claim_evidence"] is False
    assert sum(receipt["security"].values()) == 0
