from __future__ import annotations

import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
NOTE = ROOT / "phase1" / "GRAPH_BASIS_EVALUATION_METHOD_20260902.md"
DRAFT = ROOT / "phase1" / "PAPER_DRAFT_DECISION_CORPUS_20260902.md"
RECEIPT = ROOT / "phase1" / "historical_ust_predictor_sensitivity_formal_receipt_20260830.json"
POSTPUSH = ROOT / "phase1" / "graph_basis_method_postpush_receipt_20260902.json"


def test_note_binds_frozen_graph_counts() -> None:
    note = NOTE.read_text(encoding="utf-8")
    receipt = json.loads(RECEIPT.read_text(encoding="utf-8"))
    graph = receipt["pair_graph"]
    assert f"{graph['pair_rows']}-row" in note
    assert f"incidence rank {graph['incidence_rank']}" in note
    assert f"{graph['cycle_rows']}\ncycle rows" in note
    assert receipt["status"] == "HISTORICAL_UST_PREDICTOR_SENSITIVITY_FORMAL_COMPLETE"


def test_note_keeps_method_scope_narrow() -> None:
    note = NOTE.read_text(encoding="utf-8")
    required = (
        "not a predictor gain",
        "does not create another experimental observation",
        "turn dependent edge outcomes into independent samples",
        "estimate an effective sample size",
        "new effective-resistance, Foster, Kirchhoff, or spanning-tree theory",
        "counts_as_distinct_claim_evidence=false",
    )
    for phrase in required:
        assert phrase in note


def test_manuscript_reports_both_estimands_and_clustered_uncertainty() -> None:
    draft = DRAFT.read_text(encoding="utf-8")
    assert "### 4.4 Graph-basis sensitivity for redundant comparisons" in draft
    assert "show row and UST views together" in draft
    assert "retain\ntask-clustered uncertainty" in draft
    assert "not a new graph theorem or independent\n  predictor-performance result" in draft


def test_postpush_receipt_keeps_verification_and_claim_boundaries() -> None:
    receipt = json.loads(POSTPUSH.read_text(encoding="utf-8"))
    assert receipt["exact_public_commit"] == "b757fcc1bceec7687cf6dc45612d9531d70298f7"
    assert receipt["focused_tests"]["passed"] == 18
    assert receipt["full_tests"]["passed"] == 2082
    assert receipt["full_tests"]["failed"] == 0
    assert not any(receipt["claim_boundary"].values())
    assert sum(receipt["security"].values()) == 0
