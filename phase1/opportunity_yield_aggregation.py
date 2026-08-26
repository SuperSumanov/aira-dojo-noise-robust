#!/usr/bin/env python3
"""Deterministic opportunity-yield aggregation arithmetic.

This module is intentionally file-agnostic.  It operates only on task-level counts
and metrics supplied by a separately gated evaluator.
"""
from __future__ import annotations

import math
from typing import Any, Mapping


class OpportunityYieldAggregationError(ValueError):
    pass


def _positive_integer_counts(name: str, values: Mapping[str, int]) -> dict[str, int]:
    if not isinstance(values, Mapping) or not values:
        raise OpportunityYieldAggregationError(f"{name} must be a non-empty mapping")
    normalized: dict[str, int] = {}
    for task, value in values.items():
        if not isinstance(task, str) or not task:
            raise OpportunityYieldAggregationError(f"{name} has an invalid task")
        if isinstance(value, bool) or not isinstance(value, int) or value <= 0:
            raise OpportunityYieldAggregationError(
                f"{name}[{task!r}] must be a positive integer"
            )
        normalized[task] = value
    return normalized


def _finite_values(values: Mapping[str, float]) -> dict[str, float]:
    if not isinstance(values, Mapping) or not values:
        raise OpportunityYieldAggregationError("task values must be a non-empty mapping")
    normalized: dict[str, float] = {}
    for task, value in values.items():
        if not isinstance(task, str) or not task:
            raise OpportunityYieldAggregationError("task values have an invalid task")
        if isinstance(value, bool) or not isinstance(value, (int, float)):
            raise OpportunityYieldAggregationError(f"task value for {task!r} is not numeric")
        converted = float(value)
        if not math.isfinite(converted):
            raise OpportunityYieldAggregationError(f"task value for {task!r} is not finite")
        normalized[task] = converted
    return normalized


def summarize_task_weights(
    run_counts: Mapping[str, int],
    structural_pair_counts: Mapping[str, int],
    informative_pair_counts: Mapping[str, int],
    *,
    tolerance: float = 1e-12,
) -> dict[str, Any]:
    """Compute two-stage task weights and verify both reweighting identities."""
    runs = _positive_integer_counts("run counts", run_counts)
    structural = _positive_integer_counts("structural pair counts", structural_pair_counts)
    informative = _positive_integer_counts("informative pair counts", informative_pair_counts)
    if set(runs) != set(structural) or set(runs) != set(informative):
        raise OpportunityYieldAggregationError("run, structural, and informative task sets differ")
    if any(informative[task] > structural[task] for task in runs):
        raise OpportunityYieldAggregationError("informative pair count exceeds structural support")
    if not math.isfinite(tolerance) or tolerance < 0:
        raise OpportunityYieldAggregationError("tolerance must be finite and non-negative")

    tasks = sorted(runs)
    total_runs = sum(runs.values())
    total_structural = sum(structural.values())
    total_informative = sum(informative.values())
    rows: list[dict[str, Any]] = []
    weighted_mean_yield = total_structural / total_runs
    structural_weighted_mean_informative_rate = total_informative / total_structural
    structural_residuals = []
    informative_residuals = []
    for task in tasks:
        run_share = runs[task] / total_runs
        structural_share = structural[task] / total_structural
        informative_share = informative[task] / total_informative
        opportunity_yield = structural[task] / runs[task]
        informative_rate = informative[task] / structural[task]
        identity_structural_share = run_share * opportunity_yield / weighted_mean_yield
        identity_informative_share = (
            structural_share
            * informative_rate
            / structural_weighted_mean_informative_rate
        )
        structural_residual = structural_share - identity_structural_share
        informative_residual = informative_share - identity_informative_share
        structural_residuals.append(abs(structural_residual))
        informative_residuals.append(abs(informative_residual))
        rows.append(
            {
                "task": task,
                "runs": runs[task],
                "structural_pairs": structural[task],
                "informative_pairs": informative[task],
                "opportunity_yield": opportunity_yield,
                "informative_rate": informative_rate,
                "run_share": run_share,
                "structural_pair_share": structural_share,
                "informative_pair_share": informative_share,
                "identity_structural_pair_share": identity_structural_share,
                "identity_informative_pair_share": identity_informative_share,
                "structural_identity_residual": structural_residual,
                "informative_identity_residual": informative_residual,
            }
        )
    run_to_structural = 0.5 * math.fsum(
        abs(row["structural_pair_share"] - row["run_share"]) for row in rows
    )
    structural_to_informative = 0.5 * math.fsum(
        abs(row["informative_pair_share"] - row["structural_pair_share"])
        for row in rows
    )
    run_to_informative = 0.5 * math.fsum(
        abs(row["informative_pair_share"] - row["run_share"]) for row in rows
    )
    maximum_structural_residual = max(structural_residuals, default=0.0)
    maximum_informative_residual = max(informative_residuals, default=0.0)
    if max(maximum_structural_residual, maximum_informative_residual) > tolerance:
        raise OpportunityYieldAggregationError("a task-weight identity exceeds tolerance")
    return {
        "tasks": rows,
        "inventory": {
            "tasks": len(tasks),
            "runs": total_runs,
            "structural_pairs": total_structural,
            "informative_pairs": total_informative,
        },
        "weighted_mean_opportunity_yield": weighted_mean_yield,
        "structural_weighted_mean_informative_rate": (
            structural_weighted_mean_informative_rate
        ),
        "total_variations": {
            "run_to_structural": run_to_structural,
            "structural_to_informative": structural_to_informative,
            "run_to_informative": run_to_informative,
        },
        "identity_maximum_absolute_residuals": {
            "run_to_structural": maximum_structural_residual,
            "structural_to_informative": maximum_informative_residual,
        },
        "identity_absolute_tolerance": tolerance,
        "identity_pass": True,
    }


def summarize_task_metric(
    run_counts: Mapping[str, int],
    structural_pair_counts: Mapping[str, int],
    informative_pair_counts: Mapping[str, int],
    task_values: Mapping[str, float],
    *,
    tolerance: float = 1e-12,
) -> dict[str, Any]:
    """Decompose structural-yield and informative-filter task reweighting."""
    weights = summarize_task_weights(
        run_counts,
        structural_pair_counts,
        informative_pair_counts,
        tolerance=tolerance,
    )
    values = _finite_values(task_values)
    tasks = [row["task"] for row in weights["tasks"]]
    if set(values) != set(tasks):
        raise OpportunityYieldAggregationError("weight and metric task sets differ")
    by_task = {row["task"]: row for row in weights["tasks"]}
    pair_weighted = math.fsum(
        by_task[task]["informative_pair_share"] * values[task] for task in tasks
    )
    structural_weighted = math.fsum(
        by_task[task]["structural_pair_share"] * values[task] for task in tasks
    )
    run_weighted = math.fsum(by_task[task]["run_share"] * values[task] for task in tasks)
    uniform_task = math.fsum(values[task] for task in tasks) / len(tasks)
    yield_reweighting = structural_weighted - run_weighted
    informative_reweighting = pair_weighted - structural_weighted
    total_reweighting = pair_weighted - run_weighted
    additivity_residual = total_reweighting - yield_reweighting - informative_reweighting
    task_range = max(values.values()) - min(values.values())
    tvs = weights["total_variations"]
    bounds = {
        "structural_yield": task_range * tvs["run_to_structural"],
        "informative_filter": task_range * tvs["structural_to_informative"],
        "total": task_range * tvs["run_to_informative"],
    }
    observed = {
        "structural_yield": yield_reweighting,
        "informative_filter": informative_reweighting,
        "total": total_reweighting,
    }
    for component in sorted(observed):
        if abs(observed[component]) > bounds[component] + tolerance:
            raise OpportunityYieldAggregationError(
                f"{component} reweighting exceeds its range-times-TV bound"
            )
    realized = {
        component: abs(observed[component]) / bounds[component]
        if bounds[component] > 0
        else None
        for component in sorted(observed)
    }
    if abs(additivity_residual) > tolerance:
        raise OpportunityYieldAggregationError("reweighting decomposition is not additive")
    return {
        "task_values": [
            {"task": task, "value": values[task]} for task in tasks
        ],
        "pair_weighted_metric": pair_weighted,
        "structural_weighted_task_metric": structural_weighted,
        "run_weighted_task_metric": run_weighted,
        "uniform_task_metric": uniform_task,
        "observed_reweighting": observed,
        "additivity_residual": additivity_residual,
        "task_metric_range": task_range,
        "total_variations": tvs,
        "range_times_tv_sharp_bounds": bounds,
        "realized_absolute_fractions_of_bounds": realized,
        "bound_absolute_tolerance": tolerance,
        "bound_pass": True,
        "weight_identity": weights,
    }


def classify_pair_vs_run_sign(pair_value: float, run_value: float) -> str:
    """Classify a contrast without treating an exact zero as a sign flip."""
    for name, value in (("pair value", pair_value), ("run value", run_value)):
        if isinstance(value, bool) or not isinstance(value, (int, float)):
            raise OpportunityYieldAggregationError(f"{name} is not numeric")
        if not math.isfinite(float(value)):
            raise OpportunityYieldAggregationError(f"{name} is not finite")
    pair = float(pair_value)
    run = float(run_value)
    if pair == 0.0 or run == 0.0:
        return "ON_BOUNDARY"
    if pair * run < 0.0:
        return "PAIR_VS_RUN_SIGN_FLIP"
    return "SAME_SIGN"
