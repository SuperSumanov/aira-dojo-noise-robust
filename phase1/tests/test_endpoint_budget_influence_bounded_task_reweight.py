from __future__ import annotations

import hashlib
import inspect
import json
import math
from pathlib import Path

from phase1 import evaluate_endpoint_budget_influence_bounded_task_reweight as producer
from phase1 import verify_endpoint_budget_influence_bounded_task_reweight as verifier


ROOT = Path(__file__).resolve().parents[2]
PROTOCOL_PATH = ROOT / "phase1/endpoint_budget_influence_bounded_task_reweight_v1.json"


def edge(index: int, task: str) -> producer.TopologyRow:
    return producer.TopologyRow((f"a{index:03d}", f"b{index:03d}"), f"p{index:03d}", task, f"r{index:03d}")


def test_protocol_is_frozen_before_reweighted_readout() -> None:
    value = json.loads(PROTOCOL_PATH.read_text(encoding="utf-8"))
    assert value["protocol"] == producer.PROTOCOL
    assert value["status"] == producer.STATUS
    assert value["known_before_freeze"]["reweighted_model_fit_prediction_or_metric_seen"] is False
    assert value["known_before_freeze"]["prospective_first960_target300_target522_values_seen"] is False
    assert value["resources"] == {
        "gpu": 0,
        "paid_api_calls": 0,
        "base_model_updates": 0,
        "critic_model_fits": 2,
        "cpu_wall_time_expected_minutes": "20-45",
        "checkpoint_resume": "one mode-0600 atomic checkpoint per endpoint budget",
    }


def test_protocol_binds_historical_source_files() -> None:
    value = json.loads(PROTOCOL_PATH.read_text(encoding="utf-8"))
    artifacts = value["immutable_inputs"]["historical_artifacts"]
    assert set(artifacts) == {
        "selection_a.public.json",
        "selection_a.private.json",
        "firewall_a/receipt.json",
        "firewall_a/topology.json",
        "firewall_a/labels.json",
        "fit/summary.json",
        "fit/private_pairs.json",
        "fit/runs.csv",
    }
    assert all(len(value) == 64 and set(value) <= set("0123456789abcdef") for value in artifacts.values())


def test_direct_uniform_ratio_preserves_unit_weights() -> None:
    full = [edge(index, "t0") for index in range(4)] + [edge(index + 4, "t1") for index in range(4)]
    induced = [full[0], full[1], full[4], full[5]]
    weights, receipt = producer.influence_bounded_weights(full, induced, 0.7, 0.2)
    assert weights == [1.0] * 4
    assert receipt["selected_lambda"] == 1.0
    assert receipt["final_weight"]["effective_sample_size_fraction"] == 1.0


def test_influence_cap_is_satisfied_by_closed_form_shrinkage() -> None:
    full = [edge(index, "large") for index in range(50)]
    full += [edge(index + 50, "small") for index in range(2)]
    induced = [full[0]] + full[50:]
    weights, receipt = producer.influence_bounded_weights(full, induced, 0.7, 0.35)
    assert len(weights) == 3
    assert receipt["selected_lambda"] < 1.0
    assert receipt["final_weight"]["maximum_single_pair_weight_share"] <= 0.35 + 1e-12
    assert receipt["final_weight"]["effective_sample_size_fraction"] >= 0.7 - 1e-12


def test_ess_constraint_can_be_the_active_bound() -> None:
    full = [edge(index, "large") for index in range(30)]
    full += [edge(index + 30, "small") for index in range(3)]
    induced = [full[0]] + full[30:]
    _, receipt = producer.influence_bounded_weights(full, induced, 0.95, 0.8)
    assert math.isclose(
        receipt["selected_lambda"],
        receipt["lambda_bounds"]["effective_sample_size"],
        rel_tol=1e-12,
        abs_tol=1e-12,
    )
    assert receipt["final_weight"]["effective_sample_size_fraction"] >= 0.95 - 1e-12


def test_weighting_reduces_task_distribution_l1_when_shift_exists() -> None:
    full = [edge(index, "large") for index in range(20)]
    full += [edge(index + 20, "small") for index in range(4)]
    induced = [full[0], full[20], full[21], full[22]]
    _, receipt = producer.influence_bounded_weights(full, induced, 0.7, 0.4)
    assert receipt["task_distribution_l1"]["weighted_to_availability"] < receipt["task_distribution_l1"][
        "unweighted_to_availability"
    ]


def test_pair_arrays_use_first_better_orientation() -> None:
    result = producer.pair_arrays([0.75, 0.25, 0.5])
    assert result["correct"] == [1.0, 0.0, 0.0]
    assert math.isclose(result["brier"][0], 0.0625)
    assert math.isclose(result["brier"][1], 0.5625)


def test_pair_identity_is_orientation_invariant() -> None:
    first = producer.LabelRow("a", "b", "p", "t", "r")
    second = producer.LabelRow("b", "a", "p", "t", "r")
    assert producer.pair_identity_sha(first) == producer.pair_identity_sha(second)


def test_fold_assignment_matches_frozen_hash_definition() -> None:
    run = "example-run"
    digest = hashlib.sha256((producer.FOLD_SALT + "\0" + run).encode()).digest()
    assert producer.run_fold(run) == int.from_bytes(digest[:8], "big") % 5


def test_independent_verifier_does_not_import_producer() -> None:
    source = inspect.getsource(verifier)
    assert "evaluate_endpoint_budget_influence_bounded_task_reweight" not in source
    assert "from phase1 import" not in source


def test_producer_and_verifier_weight_receipts_match_synthetic_case() -> None:
    full = [edge(index, "a") for index in range(12)] + [edge(index + 12, "b") for index in range(4)]
    induced = [full[0], full[1], full[12], full[13], full[14]]
    _, expected = producer.influence_bounded_weights(full, induced, 0.7, 0.3)
    full_dict = [
        {"u": row.endpoints[0], "v": row.endpoints[1], "parent": row.parent, "task": row.task, "physical_run": row.run}
        for row in full
    ]
    induced_dict = [
        {"u": row.endpoints[0], "v": row.endpoints[1], "parent": row.parent, "task": row.task, "physical_run": row.run}
        for row in induced
    ]
    observed = verifier.weight_receipt(full_dict, induced_dict, 0.7, 0.3)
    verifier.close(expected, observed, "synthetic receipt")
