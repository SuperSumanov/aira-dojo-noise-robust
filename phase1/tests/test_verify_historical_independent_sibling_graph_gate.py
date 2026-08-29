from __future__ import annotations

from pathlib import Path

from phase1 import verify_historical_independent_sibling_graph_gate as verifier


def edge(
    high: str,
    low: str,
    parent: str,
    run: str,
    *,
    task: str = "task",
) -> verifier.senior.independent.RelationEdge:
    return verifier.senior.independent.RelationEdge(
        high=high,
        low=low,
        declared=parent,
        task=task,
        split="train",
        high_run=run,
        low_run=run,
        declared_run=run,
        category="verified_direct_sibling",
    )


def test_verifier_does_not_import_gate_producer() -> None:
    source = Path(verifier.__file__).read_text(encoding="utf-8")
    forbidden = "import " + "audit_historical_independent_sibling_graph_gate"
    assert forbidden not in source


def test_strict_residual_keeps_only_fully_disjoint_edges() -> None:
    rows = [
        edge("a", "b", "p", "r"),
        edge("x", "c", "q", "s"),
        edge("d", "e", "x", "t"),
        edge("f", "g", "u", "old"),
    ]
    kept, reasons = verifier.strict_residual(rows, {"x"}, {"old"})
    assert kept == [rows[0]]
    assert reasons["rows_retained"] == 1
    assert reasons["rows_dropped"] == 3
    assert reasons["drop_mask_E"] == 1
    assert reasons["drop_mask_P"] == 1
    assert reasons["drop_mask_R"] == 1


def test_strict_residual_records_combined_drop_mask() -> None:
    kept, reasons = verifier.strict_residual(
        [edge("x", "b", "x", "old")], {"x"}, {"old"}
    )
    assert kept == []
    assert reasons["drop_mask_EPR"] == 1


def test_duplicate_profile_distinguishes_reverse_orientation() -> None:
    rows = [edge("a", "b", "p", "r"), edge("b", "a", "p", "r")]
    assert verifier.duplicate_profile(rows) == {
        "duplicate_unordered_pair_rows": 1,
        "conflicting_orientation_unordered_pairs": 1,
    }


def test_identity_fingerprint_ignores_orientation() -> None:
    assert verifier.identity_fingerprint([edge("a", "b", "p", "r")]) == (
        verifier.identity_fingerprint([edge("b", "a", "p", "r")])
    )


def test_row_sets_covers_all_identity_levels() -> None:
    sets = verifier.row_sets(
        [edge("a", "b", "p1", "r1"), edge("b", "c", "p2", "r2", task="other")]
    )
    assert sets["pairs"] == {("a", "b"), ("b", "c")}
    assert sets["endpoints"] == {"a", "b", "c"}
    assert sets["parents"] == {"p1", "p2"}
    assert sets["runs"] == {"r1", "r2"}
    assert sets["tasks"] == {"task", "other"}


def test_classification_is_fail_closed() -> None:
    assert verifier.classify({"integrity": False}, {"support": True}).endswith(
        "INTEGRITY_FAIL"
    )
    assert verifier.classify({"integrity": True}, {"support": False}).endswith(
        "LIMITED_SUPPORT"
    )
    assert verifier.classify({"integrity": True}, {"support": True}).endswith("FEASIBLE")
