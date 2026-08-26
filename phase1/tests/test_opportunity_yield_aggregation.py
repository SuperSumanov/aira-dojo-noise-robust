from __future__ import annotations

import json
import random
from pathlib import Path

import pytest

from phase1.opportunity_yield_aggregation import (
    OpportunityYieldAggregationError,
    classify_pair_vs_run_sign,
    summarize_task_metric,
    summarize_task_weights,
)


ROOT = Path(__file__).resolve().parents[2]
CONTRACT = ROOT / "phase1" / "opportunity_yield_aggregation_audit_v1.json"


def test_contract_is_outcome_blind_and_non_rescuing() -> None:
    value = json.loads(CONTRACT.read_text(encoding="utf-8"))
    assert value["status"] == "FROZEN_OUTCOME_BLIND_BEFORE_FIRST960_CLOSURE"
    assert value["authority"]["may_rescue_failed_primary"] is False
    assert value["entry_gate"]["independent_accrual_closure_required"] is True
    assert value["entry_gate"]["exact_common_pair_support_required_for_every_compared_arm"] is True
    assert value["contrast_audit"]["unregistered_post_truth_contrasts_allowed"] is False
    assert value["access_and_compute"] == {
        "prospective_label_grade_outcome_or_winner_orientation_read": False,
        "prediction_values_read_or_aggregated": False,
        "accuracy_effect_or_search_utility_computed": False,
        "raw_archive_payload_read": False,
        "gpu_jobs": 0,
        "api_calls": 0,
        "new_model_fits": 0,
        "base_llm_updates": 0,
    }


def test_yield_identity_and_sharp_bound_can_be_attained() -> None:
    runs = {"a": 1, "b": 3}
    structural = {"a": 3, "b": 1}
    informative = dict(structural)
    weights = summarize_task_weights(runs, structural, informative)
    assert weights["total_variations"]["run_to_structural"] == pytest.approx(0.5)
    assert weights["total_variations"]["structural_to_informative"] == pytest.approx(0.0)
    assert max(weights["identity_maximum_absolute_residuals"].values()) <= 1e-12

    result = summarize_task_metric(
        runs, structural, informative, {"a": 1.0, "b": 0.0}
    )
    assert result["pair_weighted_metric"] == pytest.approx(0.75)
    assert result["structural_weighted_task_metric"] == pytest.approx(0.75)
    assert result["run_weighted_task_metric"] == pytest.approx(0.25)
    assert result["uniform_task_metric"] == pytest.approx(0.5)
    assert result["observed_reweighting"]["structural_yield"] == pytest.approx(0.5)
    assert result["observed_reweighting"]["informative_filter"] == pytest.approx(0.0)
    assert result["observed_reweighting"]["total"] == pytest.approx(0.5)
    assert result["range_times_tv_sharp_bounds"]["structural_yield"] == pytest.approx(0.5)
    assert result["realized_absolute_fractions_of_bounds"]["structural_yield"] == pytest.approx(1.0)


def test_informative_filter_is_separate_from_structural_yield() -> None:
    runs = {"a": 1, "b": 1}
    structural = {"a": 2, "b": 2}
    informative = {"a": 2, "b": 1}
    result = summarize_task_metric(
        runs, structural, informative, {"a": 1.0, "b": 0.0}
    )
    assert result["observed_reweighting"]["structural_yield"] == pytest.approx(0.0)
    assert result["observed_reweighting"]["informative_filter"] == pytest.approx(1 / 6)
    assert result["observed_reweighting"]["total"] == pytest.approx(1 / 6)
    assert result["additivity_residual"] == pytest.approx(0.0)
    assert result["total_variations"]["run_to_structural"] == pytest.approx(0.0)
    assert result["total_variations"]["structural_to_informative"] == pytest.approx(1 / 6)


def test_constant_task_metric_has_zero_bound_and_null_fraction() -> None:
    result = summarize_task_metric(
        {"a": 2, "b": 1},
        {"a": 1, "b": 4},
        {"a": 1, "b": 4},
        {"a": 0.4, "b": 0.4},
    )
    assert result["observed_reweighting"]["total"] == pytest.approx(0.0)
    assert all(value == pytest.approx(0.0) for value in result["range_times_tv_sharp_bounds"].values())
    assert all(value is None for value in result["realized_absolute_fractions_of_bounds"].values())


def test_contrast_sign_flip_and_boundary_are_distinct() -> None:
    result = summarize_task_metric(
        {"a": 1, "b": 3},
        {"a": 3, "b": 1},
        {"a": 3, "b": 1},
        {"a": 0.2, "b": -0.2},
    )
    assert result["pair_weighted_metric"] == pytest.approx(0.1)
    assert result["run_weighted_task_metric"] == pytest.approx(-0.1)
    assert (
        classify_pair_vs_run_sign(
            result["pair_weighted_metric"], result["run_weighted_task_metric"]
        )
        == "PAIR_VS_RUN_SIGN_FLIP"
    )
    assert classify_pair_vs_run_sign(0.0, -0.1) == "ON_BOUNDARY"
    assert classify_pair_vs_run_sign(0.1, 0.2) == "SAME_SIGN"


def test_deterministic_random_stress_preserves_identities_additivity_and_bounds() -> None:
    generator = random.Random(20260826)
    for _ in range(200):
        tasks = [f"task-{index}" for index in range(generator.randint(2, 12))]
        runs = {task: generator.randint(1, 20) for task in tasks}
        structural = {task: generator.randint(1, 80) for task in tasks}
        informative = {
            task: generator.randint(1, structural[task]) for task in tasks
        }
        values = {task: generator.uniform(-1.0, 1.0) for task in tasks}
        result = summarize_task_metric(runs, structural, informative, values)
        assert result["weight_identity"]["identity_pass"] is True
        assert abs(result["additivity_residual"]) <= 1e-12
        for component, observed in result["observed_reweighting"].items():
            assert abs(observed) <= (
                result["range_times_tv_sharp_bounds"][component] + 1e-12
            )


@pytest.mark.parametrize(
    ("runs", "structural", "informative", "values"),
    [
        ({"a": 1}, {"a": 0}, {"a": 1}, {"a": 0.5}),
        ({"a": 1}, {"b": 1}, {"b": 1}, {"a": 0.5}),
        ({"a": 1}, {"a": 1}, {"b": 1}, {"a": 0.5}),
        ({"a": 1}, {"a": 1}, {"a": 2}, {"a": 0.5}),
        ({"a": 1}, {"a": 1}, {"a": 1}, {"b": 0.5}),
        ({"a": True}, {"a": 1}, {"a": 1}, {"a": 0.5}),
        ({"a": 1}, {"a": 1}, {"a": 1}, {"a": float("nan")}),
    ],
)
def test_invalid_or_incomplete_task_universe_fails_closed(
    runs: dict[str, int],
    structural: dict[str, int],
    informative: dict[str, int],
    values: dict[str, float],
) -> None:
    with pytest.raises(OpportunityYieldAggregationError):
        summarize_task_metric(runs, structural, informative, values)
