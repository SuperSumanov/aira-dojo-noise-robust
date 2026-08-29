from __future__ import annotations

from phase1 import audit_historical_independent_sibling_graph_gate as gate
from phase1.audit_senior_0819_decision_relation_taxonomy import DecisionRow


def row(
    first: str,
    second: str,
    parent: str,
    run: str,
    *,
    task: str = "task",
) -> DecisionRow:
    return DecisionRow(
        first=first,
        second=second,
        parent=parent,
        task=task,
        split="train",
        first_run=run,
        second_run=run,
        parent_run=run,
        relation="verified_direct_sibling",
    )


def test_strict_residual_keeps_fully_disjoint_row() -> None:
    candidate = row("a", "b", "p", "r")
    kept, reasons = gate.strict_residual([candidate], {"x"}, {"old"})
    assert kept == [candidate]
    assert reasons["rows_retained"] == 1
    assert reasons["rows_dropped"] == 0


def test_strict_residual_drops_endpoint_overlap() -> None:
    kept, reasons = gate.strict_residual([row("a", "b", "p", "r")], {"a"}, set())
    assert kept == []
    assert reasons["drop_mask_E"] == 1
    assert reasons["endpoint_overlap_rows"] == 1


def test_strict_residual_drops_parent_overlap() -> None:
    kept, reasons = gate.strict_residual([row("a", "b", "p", "r")], {"p"}, set())
    assert kept == []
    assert reasons["drop_mask_P"] == 1


def test_strict_residual_drops_run_overlap_and_records_combination() -> None:
    kept, reasons = gate.strict_residual(
        [row("a", "b", "p", "r")], {"a", "p"}, {"r"}
    )
    assert kept == []
    assert reasons["drop_mask_EPR"] == 1
    assert reasons["run_overlap_rows"] == 1


def test_duplicate_profile_distinguishes_duplicate_and_reverse_conflict() -> None:
    rows = [row("a", "b", "p", "r"), row("b", "a", "p", "r")]
    assert gate.duplicate_profile(rows) == {
        "duplicate_unordered_pair_rows": 1,
        "conflicting_orientation_unordered_pairs": 1,
    }


def test_fingerprint_is_orientation_invariant() -> None:
    assert gate.fingerprint([row("a", "b", "p", "r")]) == gate.fingerprint(
        [row("b", "a", "p", "r")]
    )


def test_classification_order_is_fail_closed() -> None:
    assert gate.classify({"a": False}, {"b": True}).endswith("INTEGRITY_FAIL")
    assert gate.classify({"a": True}, {"b": False}).endswith("LIMITED_SUPPORT")
    assert gate.classify({"a": True}, {"b": True}).endswith("FEASIBLE")


def test_row_sets_counts_all_identity_levels() -> None:
    sets = gate.row_sets(
        [row("a", "b", "p1", "r1"), row("b", "c", "p2", "r2", task="other")]
    )
    assert len(sets["pairs"]) == 2
    assert sets["endpoints"] == {"a", "b", "c"}
    assert sets["parents"] == {"p1", "p2"}
    assert sets["runs"] == {"r1", "r2"}
    assert sets["tasks"] == {"task", "other"}
