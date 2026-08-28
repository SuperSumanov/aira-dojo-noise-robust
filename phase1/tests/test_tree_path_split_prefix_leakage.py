from __future__ import annotations

import ast
import copy
import itertools
import json
from fractions import Fraction
from pathlib import Path

import pytest

from phase1 import audit_tree_path_split_prefix_leakage as producer
from phase1 import verify_tree_path_split_prefix_leakage as verifier


ROOT = Path(__file__).resolve().parents[2]


def cards() -> dict[str, dict[str, object]]:
    return {
        "root": {"task": "task-a", "run": "run-a", "parent": "outside", "depth": 1},
        "a": {"task": "task-a", "run": "run-a", "parent": "root", "depth": 2},
        "b": {"task": "task-a", "run": "run-a", "parent": "root", "depth": 2},
        "c": {"task": "task-a", "run": "run-a", "parent": "a", "depth": 3},
        "d": {"task": "task-a", "run": "run-a", "parent": "a", "depth": 3},
    }


def protocol() -> dict[str, object]:
    value = json.loads((ROOT / "phase1" / "tree_path_split_prefix_leakage_v1.json").read_text(encoding="utf-8"))
    value["split_design"].update(
        {"train_paths": 1, "validation_paths": 1, "test_paths": 1}
    )
    value["strong_positive_gates"].update(
        {
            "global_test_occurrence_contamination_integrity_floor": "0",
            "minimum_task_fraction_at_or_above_group_ratio_reference": "0",
            "minimum_physical_run_fraction_at_or_above_group_ratio_reference": "0",
            "maximum_single_task_expected_contaminated_occurrence_contribution_share": "1",
            "maximum_single_physical_run_expected_contaminated_occurrence_contribution_share": "1",
        }
    )
    return value


def brute_force_terms(total: int, train_size: int, validation_size: int, test_size: int, multiplicity: int) -> dict[str, Fraction]:
    support = set(range(multiplicity))
    assignments = 0
    overlap = Fraction()
    appears_test = Fraction()
    test_occurrences = Fraction()
    contaminated_test_occurrences = Fraction()
    universe = set(range(total))
    for train_tuple in itertools.combinations(range(total), train_size):
        train = set(train_tuple)
        remainder = universe - train
        for validation_tuple in itertools.combinations(sorted(remainder), validation_size):
            validation = set(validation_tuple)
            test = remainder - validation
            assert len(test) == test_size
            assignments += 1
            overlap += bool(support & train and support & test)
            appears_test += bool(support & test)
            test_count = len(support & test)
            test_occurrences += test_count
            contaminated_test_occurrences += test_count if support & train else 0
    return {
        "train_test_overlap": overlap / assignments,
        "appears_in_test": appears_test / assignments,
        "expected_test_occurrences": test_occurrences / assignments,
        "expected_contaminated_test_occurrences": contaminated_test_occurrences / assignments,
    }


def test_reconstructs_paths_edges_and_multiplicities() -> None:
    rows, inventory, checks = producer.reconstruct_tree_rows(cards())
    assert sorted(row[3] for row in rows) == [1, 1, 1, 2]
    assert inventory == {
        "eligible_endpoints": 5,
        "observed_fragments": 1,
        "fragments_with_observed_edges": 1,
        "single_node_fragments": 0,
        "root_to_leaf_path_records": 3,
        "canonical_observed_edges": 4,
        "path_edge_occurrences": 5,
        "tasks": 1,
        "physical_runs": 1,
    }
    assert all(checks.values())


def test_independent_tree_reconstruction_matches_without_importing_producer() -> None:
    left = producer.reconstruct_tree_rows(cards())
    right = verifier.independently_reconstruct(cards())
    assert left == right
    source = (ROOT / "phase1" / "verify_tree_path_split_prefix_leakage.py").read_text(encoding="utf-8")
    tree = ast.parse(source)
    imported = {
        alias.name
        for node in ast.walk(tree)
        if isinstance(node, (ast.Import, ast.ImportFrom))
        for alias in node.names
    }
    assert "audit_tree_path_split_prefix_leakage" not in imported


def test_hand_computed_two_of_three_paths() -> None:
    observed = producer.split_terms(3, 1, 1, 1, 2)
    assert observed == {
        "train_test_overlap": Fraction(1, 3),
        "appears_in_test": Fraction(2, 3),
        "expected_test_occurrences": Fraction(2, 3),
        "expected_contaminated_test_occurrences": Fraction(1, 3),
    }


@pytest.mark.parametrize("multiplicity", [1, 2, 3, 4])
def test_exact_formula_matches_exhaustive_fixed_size_assignments(multiplicity: int) -> None:
    expected = brute_force_terms(4, 2, 1, 1, multiplicity)
    assert producer.split_terms(4, 2, 1, 1, multiplicity) == expected
    assert verifier.independently_compute_terms(4, 2, 1, 1, multiplicity) == expected


def test_all_multiplicity_one_has_zero_cross_split_prefix_mass() -> None:
    p = protocol()
    rows = [
        ("t1", "r1", "f1", 1),
        ("t2", "r2", "f2", 1),
        ("t3", "r3", "f3", 1),
    ]
    summary = producer.summarize_rows(rows, p)
    assert producer.exact(Fraction()) == summary["global"]["expected_train_test_cross_split_canonical_edges"]
    assert producer.exact(Fraction()) == summary["global"]["test_occurrence_contamination_ratio_of_expectations"]


def test_producer_and_verifier_summaries_are_byte_equivalent_on_synthetic_rows() -> None:
    p = protocol()
    rows = [
        ("t1", "r1", "f1", 2),
        ("t1", "r1", "f1", 1),
        ("t2", "r2", "f2", 2),
        ("t2", "r2", "f2", 1),
    ]
    left = producer.summarize_rows(rows, p)
    right = verifier.independently_summarize(rows, p)
    assert json.dumps(left, sort_keys=True, separators=(",", ":")) == json.dumps(
        right, sort_keys=True, separators=(",", ":")
    )


def test_both_axes_pass_only_under_frozen_breadth_and_dominance_limits() -> None:
    p = protocol()
    rows = [
        ("t1", "r1", "f1", 2),
        ("t1", "r1", "f1", 1),
        ("t2", "r2", "f2", 2),
        ("t2", "r2", "f2", 1),
    ]
    summary = producer.summarize_rows(rows, p)
    assert producer.final_classification(summary, {"ok": True}, p) == "BROAD_PATH_SPLIT_PREFIX_LEAKAGE_RISK"
    assert verifier.classify(summary, {"ok": True}, p) == "BROAD_PATH_SPLIT_PREFIX_LEAKAGE_RISK"


def test_global_signal_cannot_rescue_failed_breadth_or_anti_dominance() -> None:
    p = protocol()
    p["strong_positive_gates"].update(
        {
            "minimum_task_fraction_at_or_above_group_ratio_reference": "1",
            "minimum_physical_run_fraction_at_or_above_group_ratio_reference": "1",
            "maximum_single_task_expected_contaminated_occurrence_contribution_share": "0",
            "maximum_single_physical_run_expected_contaminated_occurrence_contribution_share": "0",
        }
    )
    rows = [
        ("t1", "r1", "f1", 2),
        ("t1", "r1", "f1", 1),
        ("t2", "r2", "f2", 2),
        ("t2", "r2", "f2", 1),
    ]
    summary = producer.summarize_rows(rows, p)
    assert producer.final_classification(summary, {"ok": True}, p) == "GLOBAL_EXPECTATION_WITHOUT_BROAD_SUPPORT"
    assert verifier.classify(summary, {"ok": True}, p) == "GLOBAL_EXPECTATION_WITHOUT_BROAD_SUPPORT"


def test_hard_gate_failure_has_precedence() -> None:
    p = protocol()
    rows = [
        ("t1", "r1", "f1", 2),
        ("t1", "r1", "f1", 1),
        ("t2", "r2", "f2", 2),
        ("t2", "r2", "f2", 1),
    ]
    summary = producer.summarize_rows(rows, p)
    assert producer.final_classification(summary, {"ok": False}, p) == "PATH_SPLIT_PREFIX_LEAKAGE_GATE_FAIL"
    assert verifier.classify(summary, {"ok": False}, p) == "PATH_SPLIT_PREFIX_LEAKAGE_GATE_FAIL"


def test_known_global_floor_is_integrity_only_and_cannot_be_relabelled_new() -> None:
    p = protocol()
    assert p["strong_positive_gates"]["global_floor_is_new_evidence"] is False
    assert p["disclosed_post_hoc_global_exploration"]["new_discovery_claim"] is False
    p["strong_positive_gates"]["global_test_occurrence_contamination_integrity_floor"] = "1"
    rows = [
        ("t1", "r1", "f1", 2),
        ("t1", "r1", "f1", 1),
        ("t2", "r2", "f2", 2),
        ("t2", "r2", "f2", 1),
    ]
    summary = producer.summarize_rows(rows, p)
    assert producer.final_classification(summary, {"ok": True}, p) == "PATH_SPLIT_PREFIX_LEAKAGE_GATE_FAIL"
    assert verifier.classify(summary, {"ok": True}, p) == "PATH_SPLIT_PREFIX_LEAKAGE_GATE_FAIL"


@pytest.mark.parametrize(
    "arguments",
    [
        (3, 1, 1, 0, 1),
        (3, -1, 2, 2, 1),
        (3, 1, 1, 1, 0),
        (3, 1, 1, 1, 4),
    ],
)
def test_invalid_split_or_multiplicity_fails_closed(arguments: tuple[int, int, int, int, int]) -> None:
    with pytest.raises(producer.PrefixLeakageError):
        producer.split_terms(*arguments)
    with pytest.raises(verifier.VerificationError):
        verifier.independently_compute_terms(*arguments)


def test_cycle_fails_closed_in_both_reconstructions() -> None:
    bad = cards()
    bad["root"]["parent"] = "c"
    with pytest.raises(producer.PrefixLeakageError):
        producer.reconstruct_tree_rows(bad)
    with pytest.raises(verifier.VerificationError):
        verifier.independently_reconstruct(bad)


def test_cross_run_edge_fails_closed_in_both_reconstructions() -> None:
    bad = cards()
    bad["a"]["run"] = "run-b"
    with pytest.raises(producer.PrefixLeakageError):
        producer.reconstruct_tree_rows(bad)
    with pytest.raises(verifier.VerificationError):
        verifier.independently_reconstruct(bad)


def test_histogram_boundary_and_quantiles_are_exact() -> None:
    values = [Fraction(), Fraction(1, 10), Fraction(1, 4), Fraction(1, 2), Fraction(1)]
    boundaries = [Fraction(), Fraction(1, 10), Fraction(1, 4), Fraction(1, 2), Fraction(3, 4), Fraction(1)]
    assert producer.histogram(values, boundaries) == [1, 1, 1, 1, 1]
    assert verifier.bin_counts(values, boundaries) == [1, 1, 1, 1, 1]
    assert producer.median(values) == verifier.middle(values) == Fraction(1, 4)
    assert producer.nearest_rank(values, Fraction(9, 10)) == verifier.rank_nine_tenths(values) == 1


def test_independent_deep_comparison_rejects_tampering() -> None:
    with pytest.raises(verifier.VerificationError):
        verifier.deep_equal({"value": 1}, {"value": 2}, "root")


def test_frozen_protocol_records_post_hoc_global_and_unseen_breadth_timing() -> None:
    p = protocol()
    timing = p["design_timing"]
    assert timing["global_analytic_split_values_seen_before_freeze"] is True
    assert timing["task_run_or_fragment_breadth_values_seen_before_freeze"] is False
    assert timing["actual_random_partition_drawn"] is False
    assert p["claim_boundary"]["global_values_are_post_hoc_corollaries"] is True
    assert p["claim_boundary"]["actual_model_performance_inflation_measured"] is False
