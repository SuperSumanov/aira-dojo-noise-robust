from __future__ import annotations

import copy
import hashlib
import json
from fractions import Fraction
from pathlib import Path

import pytest

from phase1 import decompose_tree_linearization_within_strata as producer
from phase1 import verify_tree_linearization_within_stratum_decomposition as verifier


ROOT = Path(__file__).resolve().parents[2]
PROTOCOL_PATH = ROOT / "phase1" / "tree_linearization_within_stratum_decomposition_v1.json"
PRODUCER_PATH = ROOT / "phase1" / "decompose_tree_linearization_within_strata.py"
VERIFIER_PATH = ROOT / "phase1" / "verify_tree_linearization_within_stratum_decomposition.py"
PROTOCOL_SHA = "9f4f27c56e6dcec7b6302b095225afb307c0be3900b528dd5f56225639fb79a7"


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def protocol() -> dict:
    value = json.loads(PROTOCOL_PATH.read_text(encoding="utf-8"))
    assert isinstance(value, dict)
    return value


def decoded(value: dict) -> Fraction:
    return Fraction(value["numerator"], value["denominator"])


def relaxed_protocol() -> dict:
    value = copy.deepcopy(protocol())
    value["hard_integrity_and_support_gates"]["minimum_conditionable_tasks"] = 1
    value["hard_integrity_and_support_gates"]["minimum_conditionable_physical_runs"] = 1
    gates = value["strong_positive_gates"]
    gates["minimum_task_canonical_standardized_within_tv_integrity_floor"] = "1/10"
    gates["minimum_physical_run_canonical_standardized_within_tv_integrity_floor"] = "1/10"
    gates["minimum_task_fraction_at_or_above_conditional_tv_reference"] = "0"
    gates["minimum_physical_run_fraction_at_or_above_conditional_tv_reference"] = "0"
    gates["maximum_single_task_canonical_contribution_share"] = "1"
    gates["maximum_single_physical_run_canonical_contribution_share"] = "1"
    return value


def test_protocol_is_exactly_the_pre_result_amendment() -> None:
    value, actual = producer.load_protocol(PROTOCOL_PATH, PROTOCOL_SHA)
    assert actual == sha(PROTOCOL_PATH) == PROTOCOL_SHA
    amendment = value["pre_result_amendment"]
    assert amendment["new_within_task_or_within_run_values_seen_before_amendment"] is False
    assert amendment["synthetic_within_stratum_values_computed_before_amendment"] is False
    assert "Triangle slack measures looseness" in amendment["reason"]


def test_protocol_hash_drift_fails_closed() -> None:
    with pytest.raises(producer.DecompositionError, match="protocol SHA"):
        producer.load_protocol(PROTOCOL_PATH, "0" * 64)


def test_equal_multiplicity_has_zero_everywhere() -> None:
    edges = [
        ("task-a", "run-a", 1),
        ("task-a", "run-a", 1),
        ("task-b", "run-b", 1),
        ("task-b", "run-b", 1),
    ]
    result = producer.summarize_edges(edges, relaxed_protocol())
    assert decoded(result["overall_edge_total_variation"]) == 0
    for axis in ("task", "physical_run"):
        profile = result["partitions"][axis]
        assert decoded(profile["group_marginal_total_variation"]) == 0
        assert decoded(profile["canonical_marginal_standardized_within_total_variation"]) == 0
        assert decoded(profile["exact_slack_above_triangle_lower_bound"]) == 0


def test_composition_only_shift_has_zero_conditional_distortion() -> None:
    edges = [
        ("task-a", "run-a", 2),
        ("task-a", "run-a", 2),
        ("task-b", "run-b", 1),
        ("task-b", "run-b", 1),
    ]
    result = producer.summarize_edges(edges, relaxed_protocol())
    overall = decoded(result["overall_edge_total_variation"])
    assert overall > 0
    for axis in ("task", "physical_run"):
        profile = result["partitions"][axis]
        assert decoded(profile["group_marginal_total_variation"]) == overall
        assert decoded(profile["canonical_marginal_standardized_within_total_variation"]) == 0
        assert decoded(profile["triangle_lower_bound"]) == 0


def test_pure_within_shift_can_have_zero_triangle_slack() -> None:
    edges = [
        ("task-a", "run-a", 4),
        ("task-a", "run-a", 1),
        ("task-b", "run-b", 4),
        ("task-b", "run-b", 1),
    ]
    result = producer.summarize_edges(edges, relaxed_protocol())
    overall = decoded(result["overall_edge_total_variation"])
    assert overall == Fraction(3, 10)
    for axis in ("task", "physical_run"):
        profile = result["partitions"][axis]
        assert decoded(profile["group_marginal_total_variation"]) == 0
        assert decoded(profile["canonical_marginal_standardized_within_total_variation"]) == overall
        assert decoded(profile["triangle_lower_bound"]) == overall
        assert decoded(profile["exact_slack_above_triangle_lower_bound"]) == 0
        assert profile["strong_positive_gate"]["all_passed"] is True


def test_histogram_is_left_closed_at_reference() -> None:
    edges = [
        ("task-a", "run-a", 3),
        ("task-a", "run-a", 2),
        ("task-b", "run-b", 3),
        ("task-b", "run-b", 2),
    ]
    result = producer.summarize_edges(edges, relaxed_protocol())
    for axis in ("task", "physical_run"):
        distribution = result["partitions"][axis]["anonymous_conditionable_group_distribution"]
        assert decoded(distribution["reference"]) == Fraction(1, 10)
        assert distribution["groups_at_or_above_reference"] == 2
        assert distribution["histogram"]["counts"] == [0, 0, 2, 0, 0, 0]


def test_producer_and_independent_math_match_on_synthetic_groups() -> None:
    edges = [
        ("task-a", "run-a", 5),
        ("task-a", "run-a", 2),
        ("task-a", "run-b", 1),
        ("task-b", "run-c", 3),
        ("task-b", "run-c", 1),
        ("task-b", "run-d", 1),
        ("task-c", "run-e", 2),
        ("task-c", "run-e", 1),
    ]
    spec = relaxed_protocol()
    first = producer.summarize_edges(edges, spec)
    second = verifier.independently_summarize(edges, spec)
    assert first["inventory"] == second["inventory"]
    assert first["overall_edge_total_variation"] == second["overall_edge_total_variation"]
    assert first["partitions"] == second["partitions"]
    assert first["support_checks"] == second["support_checks"]
    assert first["provisional_axis_strength"] == second["axis_strength"]


def test_both_axis_classification_and_gate_failure_precedence() -> None:
    edges = [
        ("task-a", "run-a", 4),
        ("task-a", "run-a", 1),
        ("task-b", "run-b", 4),
        ("task-b", "run-b", 1),
    ]
    spec = relaxed_protocol()
    summary = producer.summarize_edges(edges, spec)
    hard = {"synthetic": True}
    assert producer.final_classification(summary, spec, hard) == (
        "BROAD_NONCOMPOSITIONAL_LINEARIZATION_DISTORTION"
    )
    hard["synthetic"] = False
    assert producer.final_classification(summary, spec, hard) == (
        "WITHIN_STRATUM_DECOMPOSITION_GATE_FAIL"
    )


def test_graph_reconstruction_agrees_and_emits_no_identifiers() -> None:
    cards = {
        "root": {"task": "task-secret", "run": "run-secret", "parent": "missing", "depth": 1},
        "fork": {"task": "task-secret", "run": "run-secret", "parent": "root", "depth": 2},
        "left": {"task": "task-secret", "run": "run-secret", "parent": "fork", "depth": 3},
        "right": {"task": "task-secret", "run": "run-secret", "parent": "fork", "depth": 3},
    }
    first, inventory_a = producer.observed_edges(cards)
    second, inventory_b = verifier.reconstruct_edges(cards)
    assert first == second == [
        ("task-secret", "run-secret", 2),
        ("task-secret", "run-secret", 1),
        ("task-secret", "run-secret", 1),
    ]
    assert inventory_a == inventory_b
    spec = relaxed_protocol()
    spec["hard_integrity_and_support_gates"]["minimum_conditionable_tasks"] = 1
    spec["hard_integrity_and_support_gates"]["minimum_conditionable_physical_runs"] = 1
    rendered = json.dumps(producer.summarize_edges(first, spec), sort_keys=True)
    assert "task-secret" not in rendered
    assert "run-secret" not in rendered


def test_cross_run_edge_and_cycle_fail_closed() -> None:
    cross_run = {
        "a": {"task": "task", "run": "run-a", "parent": "missing", "depth": 1},
        "b": {"task": "task", "run": "run-b", "parent": "a", "depth": 2},
    }
    with pytest.raises(producer.DecompositionError, match="crosses physical runs"):
        producer.observed_edges(cross_run)
    with pytest.raises(verifier.VerificationError, match="cross-run"):
        verifier.reconstruct_edges(cross_run)
    cycle = {
        "a": {"task": "task", "run": "run", "parent": "b", "depth": 1},
        "b": {"task": "task", "run": "run", "parent": "a", "depth": 2},
    }
    with pytest.raises(producer.DecompositionError, match="cycle"):
        producer.observed_edges(cycle)
    with pytest.raises(verifier.VerificationError, match="no fragment roots|cycle"):
        verifier.reconstruct_edges(cycle)


def test_fixed_upstream_receipts_and_claim_boundaries_remain_bound() -> None:
    spec = protocol()
    population, linear, sensitivity, hashes = producer.fixed_inputs(ROOT, spec)
    assert population["fixed_snapshot"]["sha256"] == spec["fixed_population"]["snapshot_sha256"]
    assert linear["classification"] == "MULTI_AXIS_MATERIAL_LINEARIZATION_REWEIGHTING"
    assert sensitivity["classification"] == "VERIFIED_EXACT_EDGE_MEASURE_SENSITIVITY_COROLLARY"
    assert hashes == {name: value["sha256"] for name, value in spec["fixed_inputs"].items()}
    assert spec["claim_boundary"]["positive_within_stratum_tv_existence_is_new"] is False


def test_independent_verifier_does_not_import_new_producer() -> None:
    source = VERIFIER_PATH.read_text(encoding="utf-8")
    assert "import decompose_tree_linearization_within_strata" not in source
    assert "from phase1 import decompose_tree_linearization_within_strata" not in source
    assert sha(PRODUCER_PATH) != sha(VERIFIER_PATH)
