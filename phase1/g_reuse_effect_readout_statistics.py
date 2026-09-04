"""Outcome-aware statistics kernel for the frozen G-reuse effect hierarchy.

This module does not open a label vault or authenticate checkpoints. A future
caller must do both before constructing anonymous rows for this kernel.
"""
from __future__ import annotations

import hashlib
import json
import math
from collections import defaultdict
from pathlib import Path
from typing import Any


class ReadoutError(RuntimeError):
    pass


SEEDED_ARMS = (
    "L1", "Lbudget", "G-reuse-budget", "G-reuse-to-L-full", "Ghash-reuse-to-L-full"
)
SEEDS = (6, 7, 8)
FULL = "G-reuse-to-L-full"
ROW_KEYS = {"pair_sha256", "task_sha256", "parent_sha256", "run_sha256", "truth_sign", "margins"}


def require(ok: bool, reason: str) -> None:
    if not ok:
        raise ReadoutError(reason)


def is_sha(value: Any) -> bool:
    return isinstance(value, str) and len(value) == 64 and all(c in "0123456789abcdef" for c in value)


def margin_keys() -> set[str]:
    return {f"{arm}|{seed}" for arm in SEEDED_ARMS for seed in SEEDS} | {"tfidf"}


def validate_protocol(value: dict[str, Any]) -> None:
    inp = value.get("input_contract", {})
    estimand = value.get("primary_estimand", {})
    interval = value.get("primary_estimand", {}).get("task_cluster_interval", {})
    hierarchy = value.get("hierarchy", {})
    deployment = hierarchy.get("deployment", {})
    repeat = hierarchy.get("local_repeat_confound", {})
    quality = hierarchy.get("quality_label_information", {})
    require(value.get("protocol") == "g-reuse-effect-readout-v1", "protocol")
    require(value.get("status") == "FROZEN_BEFORE_EFFECT_OUTCOME_NOT_AN_UNSEAL_IMPLEMENTATION", "status")
    require(value.get("parent_effect_protocol_sha256")
            == "2e95b73ca6a21c45502bc64919dd1dc5f447bd5f21f61f939dbbcfd97f080ed5",
            "parent_protocol")
    require(inp.get("required_seeded_arms") == list(SEEDED_ARMS), "arms")
    require(inp.get("required_seeds") == list(SEEDS), "seeds")
    require(inp.get("required_unseeded_arms") == ["tfidf"], "tfidf")
    require(inp.get("same_pair_support_required") is True, "same_support")
    require(inp.get("prediction_tie_credit") == 0.5, "tie_credit")
    require(interval.get("replicates") == 20000 and interval.get("seed") == 20260905, "bootstrap")
    require(interval.get("index")
            == "uint64_big_endian_first8_sha256(seed\\0comparison\\0replicate\\0position)_mod_n_tasks",
            "bootstrap_index")
    require(interval.get("quantiles") == [0.025, 0.975], "bootstrap_quantiles")
    require(interval.get("quantile_algorithm") == "Hyndman-Fan type 7 linear interpolation", "quantile")
    require(estimand.get("single_task_correct_difference_share")
            == "maximum positive unnormalised pair-by-seed correct-credit gain from one task divided by the sum of positive task gains",
            "task_share_definition")
    require(deployment == {
        "full_minus_lbudget_point_minimum": 0.02,
        "full_minus_lbudget_task_ci_lower_strictly_positive": True,
        "full_minus_lbudget_all_seed_signs_positive": True,
        "full_minus_g_reuse_budget_task_ci_lower_strictly_positive": True,
        "full_minus_tfidf_task_ci_lower_strictly_positive": True,
        "full_minus_lbudget_loto_minimum": 0.0,
        "full_minus_lbudget_single_task_positive_gain_share_maximum": 0.35,
    }, "deployment_rules")
    require(repeat == {
        "trigger": "L1-minus-Lbudget task-ci lower strictly positive",
        "if_triggered_require": "full-minus-L1 task-ci lower strictly positive",
        "failure_interpretation": "full may avoid repeated-local overtraining but global-to-local transfer is not established",
    }, "repeat_rules")
    require(quality == {
        "evaluated_only_if_deployment_and_repeat_gates_pass": True,
        "full_minus_hash_task_ci_lower_strictly_positive": True,
    }, "quality_rules")
    require(hierarchy.get("core_positive_requires_all_hierarchy_levels") is True, "hierarchy")
    require(value.get("output_contract") == {
        "row_level_truth_written": False,
        "row_level_predictions_written": False,
        "raw_identifiers_written": False,
        "hash_comparison_omitted_when_hierarchy_blocks_it": True,
        "structural_readiness_or_synthetic_test_counts_as_effect": False,
    }, "output_contract")
    require(value.get("resources") == {"gpu_jobs": 0, "paid_api_calls": 0, "model_fits": 0,
                                       "base_llm_updates": 0}, "resources")


def load_protocol(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    validate_protocol(value)
    return value


def validate_rows(rows: list[dict[str, Any]]) -> None:
    require(len(rows) > 0, "empty_rows")
    expected_margins = margin_keys()
    seen: set[str] = set()
    tasks: set[str] = set()
    for row in rows:
        require(isinstance(row, dict) and set(row) == ROW_KEYS, "row_schema")
        for name in ("pair_sha256", "task_sha256", "parent_sha256", "run_sha256"):
            require(is_sha(row[name]), f"{name}_shape")
        require(row["pair_sha256"] not in seen, "duplicate_pair")
        seen.add(row["pair_sha256"])
        tasks.add(row["task_sha256"])
        require(type(row["truth_sign"]) is int and row["truth_sign"] in (-1, 1), "truth_sign")
        require(isinstance(row["margins"], dict) and set(row["margins"]) == expected_margins,
                "margin_schema")
        for margin in row["margins"].values():
            require(type(margin) in (int, float) and math.isfinite(float(margin)), "finite_margin")
    require(len(tasks) >= 2, "task_support")


def credit(margin: float, sign: int) -> float:
    if margin == 0:
        return 0.5
    return 1.0 if margin * sign > 0 else 0.0


def type7(values: list[float], probability: float) -> float:
    ordered = sorted(values)
    require(ordered and 0 <= probability <= 1, "quantile_input")
    if len(ordered) == 1:
        return ordered[0]
    position = (len(ordered) - 1) * probability
    lower = int(math.floor(position))
    fraction = position - lower
    if lower + 1 == len(ordered):
        return ordered[lower]
    return ordered[lower] + fraction * (ordered[lower + 1] - ordered[lower])


def bootstrap(task_effects: dict[str, float], *, comparison: str, seed: int, replicates: int) -> list[float]:
    tasks = sorted(task_effects)
    require(len(tasks) >= 2 and replicates > 0, "bootstrap_input")
    estimates: list[float] = []
    for replicate in range(replicates):
        total = 0.0
        for position in range(len(tasks)):
            payload = f"{seed}\0{comparison}\0{replicate}\0{position}".encode()
            index = int.from_bytes(hashlib.sha256(payload).digest()[:8], "big") % len(tasks)
            total += task_effects[tasks[index]]
        estimates.append(total / len(tasks))
    return [type7(estimates, 0.025), type7(estimates, 0.975)]


def key(arm: str, seed: int) -> str:
    return f"{arm}|{seed}"


def compare(rows: list[dict[str, Any]], left: str, right: str, protocol: dict[str, Any], name: str) -> dict[str, Any]:
    grouped: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in rows:
        grouped[row["task_sha256"]].append(row)
    task_effects: dict[str, float] = {}
    task_positive_numerators: dict[str, float] = {}
    seed_effects_by_task: dict[int, dict[str, float]] = {seed: {} for seed in SEEDS}
    for task, task_rows in grouped.items():
        per_seed = []
        positive_numerator = 0.0
        for seed in SEEDS:
            differences = []
            for row in task_rows:
                left_credit = credit(float(row["margins"][key(left, seed)]), row["truth_sign"])
                right_margin = row["margins"]["tfidf"] if right == "tfidf" else row["margins"][key(right, seed)]
                difference = left_credit - credit(float(right_margin), row["truth_sign"])
                differences.append(difference)
                positive_numerator += difference
            seed_effects_by_task[seed][task] = sum(differences) / len(differences)
            per_seed.append(seed_effects_by_task[seed][task])
        task_effects[task] = sum(per_seed) / len(per_seed)
        task_positive_numerators[task] = positive_numerator
    point = sum(task_effects.values()) / len(task_effects)
    seed_effects = {
        str(seed): sum(values.values()) / len(values) for seed, values in seed_effects_by_task.items()
    }
    interval = protocol["primary_estimand"]["task_cluster_interval"]
    ci = bootstrap(task_effects, comparison=name, seed=interval["seed"], replicates=interval["replicates"])
    loto = {
        task: (sum(task_effects.values()) - value) / (len(task_effects) - 1)
        for task, value in task_effects.items()
    }
    positives = [value for value in task_positive_numerators.values() if value > 0]
    share = max(positives) / sum(positives) if positives else None
    return {
        "tasks": len(task_effects), "point": point, "task_cluster_bootstrap_ci95": ci,
        "seed_effects": dict(sorted(seed_effects.items())), "loto_min": min(loto.values()),
        "loto_max": max(loto.values()), "positive_task_count": len(positives),
        "single_task_positive_correct_gain_share": share,
    }


def arm_accuracy(rows: list[dict[str, Any]], arm: str) -> float:
    by_task: dict[str, list[float]] = defaultdict(list)
    for row in rows:
        if arm == "tfidf":
            by_task[row["task_sha256"]].append(credit(float(row["margins"]["tfidf"]), row["truth_sign"]))
        else:
            by_task[row["task_sha256"]].append(sum(
                credit(float(row["margins"][key(arm, seed)]), row["truth_sign"]) for seed in SEEDS
            ) / len(SEEDS))
    return sum(sum(values) / len(values) for values in by_task.values()) / len(by_task)


def evaluate(rows: list[dict[str, Any]], protocol: dict[str, Any]) -> dict[str, Any]:
    validate_protocol(protocol)
    validate_rows(rows)
    comparisons = {
        "full_minus_lbudget": compare(rows, FULL, "Lbudget", protocol, "full_minus_lbudget"),
        "full_minus_g_reuse_budget": compare(rows, FULL, "G-reuse-budget", protocol,
                                               "full_minus_g_reuse_budget"),
        "full_minus_tfidf": compare(rows, FULL, "tfidf", protocol, "full_minus_tfidf"),
        "l1_minus_lbudget": compare(rows, "L1", "Lbudget", protocol, "l1_minus_lbudget"),
        "full_minus_l1": compare(rows, FULL, "L1", protocol, "full_minus_l1"),
    }
    main = comparisons["full_minus_lbudget"]
    deploy_rule = protocol["hierarchy"]["deployment"]
    deployment = {
        "point": main["point"] >= deploy_rule["full_minus_lbudget_point_minimum"],
        "task_ci": main["task_cluster_bootstrap_ci95"][0] > 0,
        "all_seed_signs": all(value > 0 for value in main["seed_effects"].values()),
        "beats_g_reuse_budget": comparisons["full_minus_g_reuse_budget"]["task_cluster_bootstrap_ci95"][0] > 0,
        "beats_tfidf": comparisons["full_minus_tfidf"]["task_cluster_bootstrap_ci95"][0] > 0,
        "loto": main["loto_min"] > deploy_rule["full_minus_lbudget_loto_minimum"],
        "single_task_share": main["single_task_positive_correct_gain_share"] is not None
            and main["single_task_positive_correct_gain_share"]
            <= deploy_rule["full_minus_lbudget_single_task_positive_gain_share_maximum"],
    }
    deployment["all_pass"] = all(deployment.values())
    repeat_triggered = comparisons["l1_minus_lbudget"]["task_cluster_bootstrap_ci95"][0] > 0
    repeat_gate = (not repeat_triggered) or comparisons["full_minus_l1"]["task_cluster_bootstrap_ci95"][0] > 0
    hierarchy_open = deployment["all_pass"] and repeat_gate
    if hierarchy_open:
        hash_comparison = compare(rows, FULL, "Ghash-reuse-to-L-full", protocol, "full_minus_hash")
        quality_pass: bool | None = hash_comparison["task_cluster_bootstrap_ci95"][0] > 0
    else:
        hash_comparison = None
        quality_pass = None
    core_positive = hierarchy_open and quality_pass is True
    return {
        "protocol": "g-reuse-effect-readout-statistics-v1",
        "status": "G_REUSE_EFFECT_CORE_POSITIVE" if core_positive else "G_REUSE_EFFECT_CORE_NOT_POSITIVE",
        "task_count": len({row["task_sha256"] for row in rows}),
        "pair_count": len(rows),
        "task_macro_accuracy": {arm: arm_accuracy(rows, arm) for arm in (*SEEDED_ARMS, "tfidf")},
        "comparisons": comparisons,
        "gates": {
            "deployment": deployment,
            "local_repeat_confound": {"triggered": repeat_triggered, "pass": repeat_gate},
            "quality_label_information": {"eligible": hierarchy_open, "pass": quality_pass,
                                          "comparison": hash_comparison},
            "core_positive": core_positive,
        },
        "scope": {"row_level_truth_written": False, "row_level_predictions_written": False,
                  "raw_identifiers_written": False, "statistics_kernel_opens_vault": False,
                  "synthetic_test_counts_as_effect": False},
    }
