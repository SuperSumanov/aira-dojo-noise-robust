from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
DRAFT = ROOT / "phase1" / "PAPER_DRAFT_DECISION_CORPUS_20260902.md"


def test_all_current_main_tables_are_in_one_packet() -> None:
    text = DRAFT.read_text(encoding="utf-8")
    required_once = (
        "**Table 1(a): direct MLE data and resources.**",
        "**Table 1(b): adjacent methods and benchmark precedents.**",
        "**Table 2(a): historical v11 populations.**",
        "**Table 2(b): sealed prospective structural state at the 2026-09-02 snapshot.**",
        "**Table 3: audit readouts and validity boundaries.**",
        "**Table 4A(a): historical common-support development calibration.**",
        "**Table 4A(b): separately measured deployment cost.**",
        "**[SEALED TABLE 4B.]**",
        "**[CONDITIONAL TABLE 5.]**",
    )
    for marker in required_once:
        assert text.count(marker) == 1


def test_integrated_structural_denominators_remain_separate() -> None:
    text = DRAFT.read_text(encoding="utf-8")
    assert "296 archives / 559 eligible runs" in text
    assert "14,383 structurally eligible" in text
    assert "517 runs | 13,098 scorer-covered" in text
    assert "different denominators and are never merged" in text
    assert "Target-522 frozen selection/rank | 522/522 reached | withheld | withheld" in text


def test_sealed_and_conditional_boundaries_survive_table_merge() -> None:
    text = DRAFT.read_text(encoding="utf-8")
    assert "no accuracy, calibration, utility, candidate\nidentity, or private selection profile" in text
    assert "Model-size scaling enters the paper only if a real producer" in text
    assert "Table 4A does not claim prospective generalization" in text
    assert "graph-basis sensitivity" in text
    assert "not a new graph theorem or independent" in text
