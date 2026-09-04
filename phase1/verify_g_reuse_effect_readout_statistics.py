"""Independent recomputation for G-reuse effect readout statistics.

Deliberately does not import the producer module. It consumes the anonymous
outcome-aware rows only after a future caller has authenticated and joined them.
"""
from __future__ import annotations

import hashlib
import math
from collections import defaultdict
from typing import Any


class IndependentReadoutError(RuntimeError):
    pass


ARMS = ("L1", "Lbudget", "G-reuse-budget", "G-reuse-to-L-full", "Ghash-reuse-to-L-full")
SEEDS = (6, 7, 8)
FULL = "G-reuse-to-L-full"
ROW_FIELDS = {"pair_sha256", "task_sha256", "parent_sha256", "run_sha256", "truth_sign", "margins"}
MARGIN_FIELDS = {f"{arm}|{seed}" for arm in ARMS for seed in SEEDS} | {"tfidf"}


def check(condition: bool, message: str) -> None:
    if not condition:
        raise IndependentReadoutError(message)


def sha_shape(value: Any) -> bool:
    return isinstance(value, str) and len(value) == 64 and not (set(value) - set("0123456789abcdef"))


def validate(rows: list[dict[str, Any]], protocol: dict[str, Any]) -> None:
    check(protocol.get("protocol") == "g-reuse-effect-readout-v1", "protocol")
    check(protocol.get("parent_effect_protocol_sha256")
          == "2e95b73ca6a21c45502bc64919dd1dc5f447bd5f21f61f939dbbcfd97f080ed5",
          "parent_protocol")
    inp = protocol.get("input_contract", {})
    check(inp.get("required_seeded_arms") == list(ARMS) and inp.get("required_seeds") == list(SEEDS),
          "arm_seed_contract")
    check(inp.get("required_unseeded_arms") == ["tfidf"] and inp.get("prediction_tie_credit") == .5,
          "tfidf_tie_contract")
    interval = protocol.get("primary_estimand", {}).get("task_cluster_interval", {})
    check(interval.get("replicates") == 20000 and interval.get("seed") == 20260905
          and interval.get("quantiles") == [.025, .975]
          and interval.get("quantile_algorithm") == "Hyndman-Fan type 7 linear interpolation",
          "task_interval_contract")
    sensitivity = protocol.get("primary_estimand", {}).get("sensitivity_intervals", {})
    check(sensitivity == {
        "methods": ["parent-within-task nested paired bootstrap",
                    "physical-run-within-task nested paired bootstrap"],
        "estimand": "task-equal pair-micro seed-average difference, with sampled within-task clusters contributing all their observed pairs",
        "replicates": 5000, "parent_seed": 20260906, "physical_run_seed": 20260907,
        "quantiles": [.025, .975], "may_rescue_primary": False,
    }, "sensitivity_contract")
    deployment = protocol.get("hierarchy", {}).get("deployment", {})
    check(deployment == {
        "full_minus_lbudget_point_minimum": .02,
        "full_minus_lbudget_task_ci_lower_strictly_positive": True,
        "full_minus_lbudget_all_seed_signs_positive": True,
        "full_minus_g_reuse_budget_task_ci_lower_strictly_positive": True,
        "full_minus_tfidf_task_ci_lower_strictly_positive": True,
        "full_minus_lbudget_loto_minimum": 0.0,
        "full_minus_lbudget_single_task_positive_gain_share_maximum": .35,
    }, "deployment_contract")
    check(protocol.get("hierarchy", {}).get("quality_label_information") == {
        "evaluated_only_if_deployment_and_repeat_gates_pass": True,
        "full_minus_hash_task_ci_lower_strictly_positive": True,
    }, "quality_contract")
    check(bool(rows), "empty")
    identities = []
    tasks = set()
    for row in rows:
        check(isinstance(row, dict) and set(row) == ROW_FIELDS, "row_fields")
        check(all(sha_shape(row[field]) for field in
                  ("pair_sha256", "task_sha256", "parent_sha256", "run_sha256")), "sha_shape")
        identities.append(row["pair_sha256"])
        tasks.add(row["task_sha256"])
        check(type(row["truth_sign"]) is int and abs(row["truth_sign"]) == 1, "truth_sign")
        check(isinstance(row["margins"], dict) and set(row["margins"]) == MARGIN_FIELDS,
              "margin_fields")
        check(all(type(value) in (int, float) and math.isfinite(float(value))
                  for value in row["margins"].values()), "margin_value")
    check(len(identities) == len(set(identities)), "duplicate")
    check(len(tasks) >= 2, "task_count")


def correctness(row: dict[str, Any], field: str) -> float:
    margin = float(row["margins"][field])
    return .5 if margin == 0 else float((margin > 0) == (row["truth_sign"] > 0))


def difference(row: dict[str, Any], left: str, right: str, seed: int) -> float:
    left_value = correctness(row, f"{left}|{seed}")
    right_field = "tfidf" if right == "tfidf" else f"{right}|{seed}"
    return left_value - correctness(row, right_field)


def q7(samples: list[float], probability: float) -> float:
    ordered = sorted(samples)
    check(bool(ordered), "empty_quantile")
    location = (len(ordered) - 1) * probability
    before = math.floor(location)
    after = math.ceil(location)
    if before == after:
        return ordered[before]
    return ordered[before] * (after - location) + ordered[after] * (location - before)


def task_bootstrap(values: dict[str, float], comparison: str, protocol: dict[str, Any]) -> list[float]:
    spec = protocol["primary_estimand"]["task_cluster_interval"]
    names = sorted(values)
    draws = []
    for repetition in range(spec["replicates"]):
        selected = []
        for position in range(len(names)):
            token = f"{spec['seed']}\0{comparison}\0{repetition}\0{position}".encode()
            selected.append(values[names[int.from_bytes(hashlib.sha256(token).digest()[:8], "big") % len(names)]])
        draws.append(math.fsum(selected) / len(selected))
    return [q7(draws, .025), q7(draws, .975)]


def comparison(rows: list[dict[str, Any]], left: str, right: str, name: str,
               protocol: dict[str, Any]) -> dict[str, Any]:
    tasks: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in rows:
        tasks[row["task_sha256"]].append(row)
    by_seed: dict[str, float] = {}
    by_task_seed: dict[str, dict[int, float]] = {}
    raw_task_gain: dict[str, float] = {}
    for task, items in tasks.items():
        seed_values = {}
        for seed in SEEDS:
            seed_values[seed] = math.fsum(difference(row, left, right, seed) for row in items) / len(items)
        by_task_seed[task] = seed_values
        raw_task_gain[task] = math.fsum(
            difference(row, left, right, seed) for row in items for seed in SEEDS
        )
    task_values = {task: math.fsum(seed_values.values()) / len(SEEDS)
                   for task, seed_values in by_task_seed.items()}
    for seed in SEEDS:
        by_seed[str(seed)] = math.fsum(values[seed] for values in by_task_seed.values()) / len(tasks)
    total = math.fsum(task_values.values())
    loto = [(total - value) / (len(task_values) - 1) for value in task_values.values()]
    positive = [value for value in raw_task_gain.values() if value > 0]
    return {
        "tasks": len(tasks),
        "point": total / len(tasks),
        "task_cluster_bootstrap_ci95": task_bootstrap(task_values, name, protocol),
        "seed_effects": dict(sorted(by_seed.items())),
        "loto_min": min(loto),
        "loto_max": max(loto),
        "positive_task_count": len(positive),
        "single_task_positive_correct_gain_share": max(positive) / math.fsum(positive) if positive else None,
    }


def nested(rows: list[dict[str, Any]], cluster_field: str, comparison_name: str,
           seed: int, replicates: int) -> list[float]:
    grouped: dict[str, dict[str, list[float]]] = defaultdict(lambda: defaultdict(list))
    for row in rows:
        grouped[row["task_sha256"]][row[cluster_field]].append(
            math.fsum(difference(row, FULL, "Lbudget", model_seed) for model_seed in SEEDS) / len(SEEDS)
        )
    tasks = sorted(grouped)
    draws = []
    for repetition in range(replicates):
        task_estimates = []
        for task_position in range(len(tasks)):
            token = f"{seed}\0{comparison_name}\0task\0{repetition}\0{task_position}".encode()
            task = tasks[int.from_bytes(hashlib.sha256(token).digest()[:8], "big") % len(tasks)]
            clusters = sorted(grouped[task])
            numerator = 0.0
            denominator = 0
            for cluster_position in range(len(clusters)):
                token = (
                    f"{seed}\0{comparison_name}\0{cluster_field}\0{repetition}\0{task_position}\0{cluster_position}"
                ).encode()
                cluster = clusters[int.from_bytes(hashlib.sha256(token).digest()[:8], "big") % len(clusters)]
                numerator += math.fsum(grouped[task][cluster])
                denominator += len(grouped[task][cluster])
            task_estimates.append(numerator / denominator)
        draws.append(math.fsum(task_estimates) / len(task_estimates))
    return [q7(draws, .025), q7(draws, .975)]


def accuracy(rows: list[dict[str, Any]], arm: str) -> float:
    grouped: dict[str, list[float]] = defaultdict(list)
    for row in rows:
        if arm == "tfidf":
            value = correctness(row, "tfidf")
        else:
            value = math.fsum(correctness(row, f"{arm}|{seed}") for seed in SEEDS) / len(SEEDS)
        grouped[row["task_sha256"]].append(value)
    return math.fsum(math.fsum(values) / len(values) for values in grouped.values()) / len(grouped)


def recompute(rows: list[dict[str, Any]], protocol: dict[str, Any]) -> dict[str, Any]:
    validate(rows, protocol)
    comparisons = {
        "full_minus_lbudget": comparison(rows, FULL, "Lbudget", "full_minus_lbudget", protocol),
        "full_minus_g_reuse_budget": comparison(rows, FULL, "G-reuse-budget",
                                                  "full_minus_g_reuse_budget", protocol),
        "full_minus_tfidf": comparison(rows, FULL, "tfidf", "full_minus_tfidf", protocol),
        "l1_minus_lbudget": comparison(rows, "L1", "Lbudget", "l1_minus_lbudget", protocol),
        "full_minus_l1": comparison(rows, FULL, "L1", "full_minus_l1", protocol),
    }
    spec = protocol["primary_estimand"]["sensitivity_intervals"]
    main = comparisons["full_minus_lbudget"]
    main["nested_parent_cluster_bootstrap_ci95"] = nested(
        rows, "parent_sha256", "full_minus_lbudget_parent", spec["parent_seed"], spec["replicates"]
    )
    main["nested_physical_run_cluster_bootstrap_ci95"] = nested(
        rows, "run_sha256", "full_minus_lbudget_run", spec["physical_run_seed"], spec["replicates"]
    )
    rule = protocol["hierarchy"]["deployment"]
    deployment = {
        "point": main["point"] >= rule["full_minus_lbudget_point_minimum"],
        "task_ci": main["task_cluster_bootstrap_ci95"][0] > 0,
        "all_seed_signs": min(main["seed_effects"].values()) > 0,
        "beats_g_reuse_budget": comparisons["full_minus_g_reuse_budget"]["task_cluster_bootstrap_ci95"][0] > 0,
        "beats_tfidf": comparisons["full_minus_tfidf"]["task_cluster_bootstrap_ci95"][0] > 0,
        "loto": main["loto_min"] > rule["full_minus_lbudget_loto_minimum"],
        "single_task_share": main["single_task_positive_correct_gain_share"] is not None
            and main["single_task_positive_correct_gain_share"]
            <= rule["full_minus_lbudget_single_task_positive_gain_share_maximum"],
    }
    deployment["all_pass"] = all(deployment.values())
    repeat_triggered = comparisons["l1_minus_lbudget"]["task_cluster_bootstrap_ci95"][0] > 0
    repeat_pass = not repeat_triggered or comparisons["full_minus_l1"]["task_cluster_bootstrap_ci95"][0] > 0
    eligible = deployment["all_pass"] and repeat_pass
    hash_summary = comparison(rows, FULL, "Ghash-reuse-to-L-full", "full_minus_hash", protocol) if eligible else None
    quality_pass = hash_summary["task_cluster_bootstrap_ci95"][0] > 0 if hash_summary is not None else None
    positive = eligible and quality_pass is True
    return {
        "protocol": "g-reuse-effect-readout-statistics-v1",
        "status": "G_REUSE_EFFECT_CORE_POSITIVE" if positive else "G_REUSE_EFFECT_CORE_NOT_POSITIVE",
        "task_count": len({row["task_sha256"] for row in rows}),
        "pair_count": len(rows),
        "task_macro_accuracy": {arm: accuracy(rows, arm) for arm in (*ARMS, "tfidf")},
        "comparisons": comparisons,
        "gates": {
            "deployment": deployment,
            "local_repeat_confound": {"triggered": repeat_triggered, "pass": repeat_pass},
            "quality_label_information": {"eligible": eligible, "pass": quality_pass,
                                          "comparison": hash_summary},
            "core_positive": positive,
        },
        "scope": {"row_level_truth_written": False, "row_level_predictions_written": False,
                  "raw_identifiers_written": False, "statistics_kernel_opens_vault": False,
                  "synthetic_test_counts_as_effect": False},
    }


def compare_trees(observed: Any, expected: Any, path: str = "$") -> float:
    if type(observed) is not type(expected):
        raise IndependentReadoutError(f"type_mismatch:{path}")
    if isinstance(expected, dict):
        check(set(observed) == set(expected), f"keys:{path}")
        return max((compare_trees(observed[key], expected[key], f"{path}.{key}") for key in expected), default=0.0)
    if isinstance(expected, list):
        check(len(observed) == len(expected), f"length:{path}")
        return max((compare_trees(left, right, f"{path}[{index}]")
                    for index, (left, right) in enumerate(zip(observed, expected))), default=0.0)
    if type(expected) is float:
        check(math.isfinite(observed) and abs(observed - expected) <= 1e-12, f"float:{path}")
        return abs(observed - expected)
    check(observed == expected, f"value:{path}")
    return 0.0


def verify(rows: list[dict[str, Any]], observed: dict[str, Any], protocol: dict[str, Any]) -> dict[str, Any]:
    expected = recompute(rows, protocol)
    maximum = compare_trees(observed, expected)
    return {"verification_pass": True, "maximum_numeric_absolute_difference": maximum,
            "core_positive": expected["gates"]["core_positive"],
            "row_level_truth_written": False, "row_level_predictions_written": False}
