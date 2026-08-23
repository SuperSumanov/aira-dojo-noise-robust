#!/usr/bin/env python3
"""Independent verifier for the clean scaling confidence-cost extension.

This module intentionally does not import the extension producer.  It reuses only
the frozen primary bundle validator, then independently rebuilds every extension-
specific calibration, proper score, selective policy, interval, gate, CSV, and
release hash from the source artifacts.
"""

from __future__ import annotations

import argparse
import collections
import csv
import hashlib
import json
import math
import random
import statistics
import zlib
from pathlib import Path
from typing import Any, Iterable, Mapping, Sequence

from phase1 import critic_scaling_confirmation_analysis as primary


EXPECTED_EXTENSION_CONTRACT_SHA256 = (
    "00ba64a222ae793c3f5d196ee754f0af9e2f01986ad85ed78c11b6f570da665b"
)
EXTENSION_PROTOCOL = "critic-scaling-confidence-cost-extension-v1"
LOCK_PROTOCOL = "critic-scaling-confidence-cost-lock-v1"
ANALYSIS_PROTOCOL = "critic-scaling-confidence-cost-analysis-v1"


class VerificationError(RuntimeError):
    """Raised when source reconstruction disagrees with the released result."""


def cli() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--primary-contract", type=Path, required=True)
    parser.add_argument("--extension-contract", type=Path, required=True)
    parser.add_argument("--primary-lock", type=Path, required=True)
    parser.add_argument("--calibration-lock", type=Path, required=True)
    parser.add_argument("--primary-bundle", type=Path, required=True)
    parser.add_argument("--result-dir", type=Path, required=True)
    parser.add_argument("--receipt", type=Path, required=True)
    return parser.parse_args()


def digest(path: Path) -> str:
    value = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            value.update(block)
    return value.hexdigest()


def canonical(value: Any) -> bytes:
    return (json.dumps(value, sort_keys=True, separators=(",", ":")) + "\n").encode()


def object_from(path: Path, label: str) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise VerificationError(f"cannot read {label}: {exc}") from exc
    if not isinstance(value, dict):
        raise VerificationError(f"{label} is not an object")
    return value


def jsonl_from(path: Path, label: str) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    try:
        for number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
            if not line:
                raise VerificationError(f"{label} has blank row {number}")
            value = json.loads(line)
            if not isinstance(value, dict):
                raise VerificationError(f"{label} row {number} is not an object")
            rows.append(value)
    except (OSError, json.JSONDecodeError) as exc:
        raise VerificationError(f"cannot read {label}: {exc}") from exc
    if not rows:
        raise VerificationError(f"{label} is empty")
    return rows


def number(value: Any, label: str) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise VerificationError(f"{label} is not numeric")
    result = float(value)
    if not math.isfinite(result):
        raise VerificationError(f"{label} is not finite")
    return result


def average(values: Iterable[float]) -> float:
    rows = [float(value) for value in values]
    if not rows:
        raise VerificationError("cannot average empty values")
    return math.fsum(rows) / len(rows)


def extension_contract(path: Path, primary_sha: str) -> dict[str, Any]:
    if digest(path) != EXPECTED_EXTENSION_CONTRACT_SHA256:
        raise VerificationError("extension contract SHA256 differs from frozen verifier")
    value = object_from(path, "extension contract")
    if value.get("protocol") != EXTENSION_PROTOCOL:
        raise VerificationError("extension protocol differs")
    if value.get("status") not in {
        "PRE_REGISTERED_SYNTHETIC_VALIDATION_PENDING",
        "ANALYZER_READY_EFFECT_ASSETS_PENDING",
    }:
        raise VerificationError("extension status differs")
    binding = value.get("binding")
    if not isinstance(binding, dict) or binding.get("primary_contract_sha256") != primary_sha:
        raise VerificationError("extension primary binding differs")
    if binding.get("secondary_result_may_not_rescue_failed_primary") is not True:
        raise VerificationError("extension permits primary rescue")
    if value.get("access_and_compute") != {
        "gpu_jobs_authorized": 0,
        "api_calls_authorized": 0,
        "model_fits_authorized": 0,
        "base_llm_updates_authorized": 0,
        "future_truth_reads_authorized": False,
        "real_effect_run_authorized": False,
        "synthetic_tests_authorized": True,
    }:
        raise VerificationError("extension compute permission differs")
    return value


def pair_digest(row: Mapping[str, Any]) -> str:
    payload = [
        row.get("task"), row.get("pair_semantics"), row.get("parent_id"),
        row.get("comparison_component_id"), row.get("better_id"), row.get("worse_id"),
    ]
    return hashlib.sha256(canonical(payload)).hexdigest()


def validate_dev_truth(
    rows: Sequence[dict[str, Any]], contract: Mapping[str, Any]
) -> dict[str, dict[str, Any]]:
    required = set(contract["prediction_schema"]["truth_required_fields"])
    output: dict[str, dict[str, Any]] = {}
    unordered: set[tuple[str, str, str, str, frozenset[str]]] = set()
    utility: dict[str, float] = {}
    for index, source in enumerate(rows):
        if not required.issubset(source) or source.get("split") != "dev":
            raise VerificationError(f"dev truth row {index} schema or split differs")
        row = dict(source)
        for field in (
            "pair_id", "task", "pair_semantics", "parent_id", "parent_run_id",
            "comparison_component_id", "better_id", "worse_id", "better_run_id",
            "worse_run_id",
        ):
            if not isinstance(row.get(field), str) or not row[field]:
                raise VerificationError(f"dev truth row {index} has invalid {field}")
        better = number(row.get("better_utility"), "dev better utility")
        worse = number(row.get("worse_utility"), "dev worse utility")
        if row["better_id"] == row["worse_id"] or not better > worse:
            raise VerificationError("dev truth orientation differs")
        row["better_utility"] = better
        row["worse_utility"] = worse
        if row["pair_id"] != pair_digest(row) or row["pair_id"] in output:
            raise VerificationError("dev truth pair identity differs")
        key = (
            row["task"], row["pair_semantics"], row["parent_id"],
            row["comparison_component_id"], frozenset((row["better_id"], row["worse_id"])),
        )
        if key in unordered:
            raise VerificationError("dev truth unordered pair repeats")
        unordered.add(key)
        if row["pair_semantics"] == contract["cohort"]["primary_pair_semantics"] and not (
            row["parent_run_id"] == row["better_run_id"] == row["worse_run_id"]
        ):
            raise VerificationError("dev sibling crosses runs")
        tolerance = float(contract["prediction_schema"]["endpoint_utility_consistency_tolerance"])
        for endpoint, score in ((row["better_id"], better), (row["worse_id"], worse)):
            previous = utility.setdefault(endpoint, score)
            if not math.isclose(previous, score, rel_tol=0.0, abs_tol=tolerance):
                raise VerificationError("dev endpoint utility differs")
        output[row["pair_id"]] = row
    return output


def model_name(size: float, seed: int) -> str:
    return f"qwen3_{size:g}b_seed{seed}"


def load_dev(
    lock_path: Path,
    extension: Mapping[str, Any],
    extension_sha: str,
    primary_contract: Mapping[str, Any],
    primary_sha: str,
    primary_lock: Mapping[str, Any],
    primary_lock_sha: str,
    locked_runs: Mapping[tuple[float, int], dict[str, Any]],
) -> tuple[dict[str, dict[str, Any]], dict[str, dict[str, dict[str, float | str]]], dict[str, Any]]:
    value = object_from(lock_path, "calibration lock")
    if value.get("protocol") != LOCK_PROTOCOL or value.get("status") != "LOCKED_BEFORE_TEST_ACCESS":
        raise VerificationError("calibration lock status differs")
    if value.get("extension_contract_sha256") != extension_sha:
        raise VerificationError("calibration lock extension SHA differs")
    if value.get("primary_contract_sha256") != primary_sha:
        raise VerificationError("calibration lock primary contract SHA differs")
    if value.get("primary_lock_sha256") != primary_lock_sha:
        raise VerificationError("calibration lock primary lock SHA differs")
    if value.get("locked_before_test_access") is not True:
        raise VerificationError("calibration lock is late")
    timestamp = value.get("frozen_at_utc")
    if not isinstance(timestamp, str) or not timestamp.endswith("Z"):
        raise VerificationError("calibration lock timestamp differs")
    root = lock_path.parent
    try:
        truth_path, truth_sha, truth_count = primary.checked_artifact(
            root, value.get("dev_truth"), "dev truth"
        )
    except primary.ConfirmationError as exc:
        raise VerificationError(str(exc)) from exc
    truth_rows = jsonl_from(truth_path, "dev truth")
    if len(truth_rows) != truth_count:
        raise VerificationError("dev truth rows differ")
    truth = validate_dev_truth(truth_rows, primary_contract)
    receipts: dict[str, Any] = {
        "dev_truth": {"path": value["dev_truth"]["path"], "sha256": truth_sha, "rows": len(truth)}
    }
    predictions: dict[str, dict[str, dict[str, float | str]]] = {}

    def load_predictions(spec: Mapping[str, Any], label: str) -> tuple[dict[str, dict[str, float | str]], str, int]:
        try:
            path, sha, rows = primary.checked_artifact(root, spec.get("predictions"), label)
            values = primary.validate_predictions(
                primary.read_jsonl(path, label), truth, primary_contract, label
            )
        except primary.ConfirmationError as exc:
            raise VerificationError(str(exc)) from exc
        if rows != len(truth):
            raise VerificationError(f"{label} rows differ")
        return values, sha, rows

    baseline = value.get("baseline")
    baseline_id = primary_contract["baseline"]["id"]
    if not isinstance(baseline, dict) or baseline.get("id") != baseline_id:
        raise VerificationError("dev baseline identity differs")
    if baseline.get("receipt_sha256") != primary_lock["baseline"]["receipt_sha256"]:
        raise VerificationError("dev baseline receipt differs")
    predictions[baseline_id], sha, rows = load_predictions(baseline, baseline_id)
    receipts[baseline_id] = {"path": baseline["predictions"]["path"], "sha256": sha, "rows": rows}
    runs = value.get("runs")
    if not isinstance(runs, list):
        raise VerificationError("dev run matrix is absent")
    seen: set[tuple[float, int]] = set()
    for spec in runs:
        if not isinstance(spec, dict):
            raise VerificationError("dev run is not an object")
        size = number(spec.get("model_size_b"), "dev model size")
        seed = spec.get("seed")
        if not isinstance(seed, int):
            raise VerificationError("dev model seed differs")
        key = (size, seed)
        if key in seen or key not in locked_runs:
            raise VerificationError("dev model matrix differs")
        seen.add(key)
        checkpoint = locked_runs[key]["checkpoint_manifest_sha256"]
        if spec.get("checkpoint_manifest_sha256") != checkpoint:
            raise VerificationError("dev checkpoint differs")
        name = model_name(size, seed)
        predictions[name], sha, rows = load_predictions(spec, name)
        receipts[name] = {
            "path": spec["predictions"]["path"], "sha256": sha, "rows": rows,
            "checkpoint_manifest_sha256": checkpoint,
        }
    if seen != set(locked_runs):
        raise VerificationError("dev model matrix is incomplete")
    return truth, predictions, receipts


def overlaps(
    dev: Mapping[str, Mapping[str, Any]], test: Mapping[str, Mapping[str, Any]]
) -> dict[str, int]:
    def endpoint_set(rows: Iterable[Mapping[str, Any]]) -> set[str]:
        return {str(row[field]) for row in rows for field in ("better_id", "worse_id")}

    def run_set(rows: Iterable[Mapping[str, Any]]) -> set[str]:
        return {
            str(row[field]) for row in rows
            for field in ("parent_run_id", "better_run_id", "worse_run_id")
        }

    def pair_set(rows: Iterable[Mapping[str, Any]]) -> set[tuple[str, frozenset[str]]]:
        return {
            (str(row["task"]), frozenset((str(row["better_id"]), str(row["worse_id"]))))
            for row in rows
        }

    return {
        "endpoint_overlap": len(endpoint_set(dev.values()) & endpoint_set(test.values())),
        "physical_run_overlap": len(run_set(dev.values()) & run_set(test.values())),
        "unordered_pair_overlap": len(pair_set(dev.values()) & pair_set(test.values())),
    }


def calibrate(margins: Sequence[float], extension: Mapping[str, Any]) -> dict[str, Any]:
    config = extension["probability_map"]
    nonzero = sorted(abs(value) for value in margins if value != 0.0)
    scale = statistics.median(nonzero) if nonzero else float(config["zero_margin_scale_fallback"])
    values = [value / scale for value in margins]
    low = float(config["inverse_temperature_min"])
    high = float(config["inverse_temperature_max"])

    def slope(beta: float) -> float:
        result = []
        for value in values:
            product = beta * value
            logistic_negative = (
                math.exp(-product) / (1.0 + math.exp(-product))
                if product >= 0.0
                else 1.0 / (1.0 + math.exp(product))
            )
            result.append(-value * logistic_negative)
        return average(result)

    low_slope, high_slope = slope(low), slope(high)
    if low_slope >= 0.0:
        beta, boundary = low, "lower"
    elif high_slope <= 0.0:
        beta, boundary = high, "upper"
    else:
        left, right = low, high
        for _ in range(int(config["optimizer_iterations"])):
            middle = (left + right) / 2.0
            if slope(middle) < 0.0:
                left = middle
            else:
                right = middle
        beta, boundary = (left + right) / 2.0, "interior"
    return {
        "dev_margin_scale": scale,
        "inverse_temperature": beta,
        "boundary": boundary,
        "dev_rows": len(margins),
        "derivative_at_min": low_slope,
        "derivative_at_max": high_slope,
    }


def logistic(value: float) -> float:
    if value >= 0.0:
        tail = math.exp(-value)
        return 1.0 / (1.0 + tail)
    head = math.exp(value)
    return head / (1.0 + head)


def tie_credit(margin: float) -> float:
    return 1.0 if margin > 0.0 else 0.0 if margin < 0.0 else 0.5


def choice_hash(row: Mapping[str, Any]) -> str:
    payload = [
        row["task"], row["parent_id"], row["comparison_component_id"],
        sorted((row["better_id"], row["worse_id"])),
    ]
    return hashlib.sha256(canonical(payload)).hexdigest()


def rebuild_predictor(
    predictor: str,
    truth: Mapping[str, Mapping[str, Any]],
    predictions: Mapping[str, Mapping[str, float | str]],
    calibration: Mapping[str, Any],
    extension: Mapping[str, Any],
) -> tuple[dict[str, Any], dict[str, Any], list[dict[str, Any]]]:
    semantics = extension["metrics"]["primary_pair_semantics"]
    rows = [truth[key] for key in sorted(truth) if truth[key]["pair_semantics"] == semantics]
    beta = float(calibration["inverse_temperature"])
    scale = float(calibration["dev_margin_scale"])
    pair: dict[str, dict[str, float]] = {}
    for row in rows:
        margin = float(predictions[row["pair_id"]]["margin"])
        logit = beta * margin / scale
        probability = logistic(logit)
        credit = tie_credit(margin)
        pair[row["pair_id"]] = {
            "logit": logit,
            "confidence": logistic(abs(logit)),
            "credit": credit,
            "error": 1.0 - credit,
            "log_loss": max(-logit, 0.0) + math.log1p(math.exp(-abs(logit))),
            "brier": (1.0 - probability) ** 2,
            "gap": float(row["better_utility"]) - float(row["worse_utility"]),
        }
    grouped: dict[str, list[Mapping[str, Any]]] = collections.defaultdict(list)
    for row in rows:
        grouped[str(row["task"])].append(row)
    per_task: dict[str, dict[str, Any]] = {}
    for task in sorted(grouped):
        task_rows = grouped[task]
        per_task[task] = {
            "pairs": len(task_rows),
            "accuracy": average(pair[row["pair_id"]]["credit"] for row in task_rows),
            "log_loss": average(pair[row["pair_id"]]["log_loss"] for row in task_rows),
            "brier": average(pair[row["pair_id"]]["brier"] for row in task_rows),
        }
    bins = int(extension["metrics"]["ece_bins"])
    binned: dict[int, list[tuple[float, float]]] = collections.defaultdict(list)
    for value in pair.values():
        index = min(bins - 1, int((value["confidence"] - 0.5) * 2.0 * bins))
        binned[index].append((value["confidence"], value["credit"]))
    ece = math.fsum(
        len(values) / len(pair)
        * abs(average(value[0] for value in values) - average(value[1] for value in values))
        for values in binned.values()
    )
    coverage: dict[str, dict[str, Any]] = {}
    coverage_rows: list[dict[str, Any]] = []
    for target_raw in extension["selective_execution"]["coverage_targets"]:
        target = float(target_raw)
        task_values: dict[str, dict[str, Any]] = {}
        accepted_total = 0
        for task in sorted(grouped):
            ordered = sorted(
                grouped[task],
                key=lambda row: (-abs(pair[row["pair_id"]]["logit"]), choice_hash(row)),
            )
            selected_count = max(
                1, min(len(ordered), int(math.floor(target * len(ordered) + 0.5)))
            )
            selected = ordered[:selected_count]
            accepted_total += selected_count
            all_gap = math.fsum(pair[row["pair_id"]]["gap"] for row in ordered)
            accepted_gap = math.fsum(pair[row["pair_id"]]["gap"] for row in selected)
            regret = math.fsum(
                pair[row["pair_id"]]["gap"] * pair[row["pair_id"]]["error"]
                for row in selected
            )
            full_regret = math.fsum(
                pair[row["pair_id"]]["gap"] * pair[row["pair_id"]]["error"]
                for row in ordered
            ) / all_gap
            realized = selected_count / len(ordered)
            task_values[task] = {
                "pairs": len(ordered),
                "accepted": selected_count,
                "coverage": realized,
                "accepted_error": average(pair[row["pair_id"]]["error"] for row in selected),
                "accepted_gap_weighted_error": regret / accepted_gap,
                "total_gap_regret": regret / all_gap,
                "excess_gap_regret_vs_random_acceptance": regret / all_gap - realized * full_regret,
            }
        aggregate = {
            "target_coverage": target,
            "realized_coverage": accepted_total / len(rows),
            "execution_saving_fraction": accepted_total / len(rows) / 2.0,
            "task_macro_accepted_error": average(value["accepted_error"] for value in task_values.values()),
            "task_macro_accepted_gap_weighted_error": average(
                value["accepted_gap_weighted_error"] for value in task_values.values()
            ),
            "task_macro_total_gap_regret": average(value["total_gap_regret"] for value in task_values.values()),
            "task_macro_excess_gap_regret_vs_random_acceptance": average(
                value["excess_gap_regret_vs_random_acceptance"] for value in task_values.values()
            ),
        }
        key = f"{target:g}"
        coverage[key] = {"aggregate": aggregate, "per_task": task_values}
        coverage_rows.append({"predictor_id": predictor, **aggregate})
    metric = {
        "predictor_id": predictor,
        "calibration": dict(calibration),
        "pairs": len(rows),
        "tasks": len(per_task),
        "micro_accuracy": average(value["credit"] for value in pair.values()),
        "micro_log_loss": average(value["log_loss"] for value in pair.values()),
        "micro_brier": average(value["brier"] for value in pair.values()),
        "fixed_bin_ece": ece,
        "task_macro_accuracy": average(value["accuracy"] for value in per_task.values()),
        "task_macro_log_loss": average(value["log_loss"] for value in per_task.values()),
        "task_macro_brier": average(value["brier"] for value in per_task.values()),
        "coverage": {key: value["aggregate"] for key, value in coverage.items()},
    }
    return metric, {"per_task": per_task, "coverage": coverage}, coverage_rows


def seeded(base: int, label: str) -> int:
    return int(base) + int(zlib.crc32(label.encode()) & 0x7FFFFFFF)


def interval(values: Mapping[str, float], extension: Mapping[str, Any], label: str) -> list[float]:
    keys = sorted(values)
    draws = int(extension["metrics"]["bootstrap_draws"])
    rng = random.Random(seeded(int(extension["metrics"]["bootstrap_seed"]), label))
    samples = []
    for _ in range(draws):
        samples.append(average(values[rng.choice(keys)] for _ in keys))
    samples.sort()
    return [samples[int(0.025 * (draws - 1))], samples[int(0.975 * (draws - 1))]]


def rebuild_decision(
    extension: Mapping[str, Any],
    primary_summary: Mapping[str, Any],
    metrics: Mapping[str, Mapping[str, Any]],
    internals: Mapping[str, Mapping[str, Any]],
    dev_truth: Mapping[str, Mapping[str, Any]],
    overlap: Mapping[str, int],
) -> dict[str, Any]:
    sizes, seeds = [0.6, 1.7, 4.0, 8.0], [6, 7]
    dev_rows = [
        row for row in dev_truth.values()
        if row["pair_semantics"] == extension["metrics"]["primary_pair_semantics"]
    ]
    dev_counts = collections.Counter(str(row["task"]) for row in dev_rows)
    dominant = max(dev_counts.values()) / len(dev_rows)
    support_gates = {
        "pairs_at_least_200": len(dev_rows) >= int(extension["calibration_lock"]["minimum_dev_pairs"]),
        "tasks_at_least_8": len(dev_counts) >= int(extension["calibration_lock"]["minimum_dev_tasks"]),
        "dominant_task_share_at_most_0_35": dominant <= float(
            extension["calibration_lock"]["maximum_dominant_dev_task_pair_share"]
        ),
        "dev_test_endpoint_overlap_zero": overlap["endpoint_overlap"] == 0,
        "dev_test_physical_run_overlap_zero": overlap["physical_run_overlap"] == 0,
        "dev_test_unordered_pair_overlap_zero": overlap["unordered_pair_overlap"] == 0,
    }
    primary_support = bool(primary_summary["decision"]["support"]["pass"])
    support_pass = primary_support and all(support_gates.values())
    size_scores = {
        f"{size:g}": {
            field: average(metrics[model_name(size, seed)][field] for seed in seeds)
            for field in ("task_macro_log_loss", "task_macro_brier")
        }
        for size in sizes
    }
    high_low_by_seed = {
        str(seed): {
            field: metrics[model_name(8.0, seed)][f"task_macro_{field}"]
            - metrics[model_name(0.6, seed)][f"task_macro_{field}"]
            for field in ("log_loss", "brier")
        }
        for seed in seeds
    }
    tasks = sorted(internals[model_name(8.0, 6)]["per_task"])
    high_low_task = {
        field: {
            task: average(
                internals[model_name(8.0, seed)]["per_task"][task][field]
                - internals[model_name(0.6, seed)]["per_task"][task][field]
                for seed in seeds
            )
            for task in tasks
        }
        for field in ("log_loss", "brier")
    }
    high_low_ci = {
        field: interval(high_low_task[field], extension, f"high-low:{field}")
        for field in ("log_loss", "brier")
    }
    proper_gates = {
        "size_mean_log_loss_monotonic_nonincreasing": all(
            size_scores[f"{left:g}"]["task_macro_log_loss"]
            >= size_scores[f"{right:g}"]["task_macro_log_loss"]
            for left, right in zip(sizes, sizes[1:])
        ),
        "size_mean_brier_monotonic_nonincreasing": all(
            size_scores[f"{left:g}"]["task_macro_brier"]
            >= size_scores[f"{right:g}"]["task_macro_brier"]
            for left, right in zip(sizes, sizes[1:])
        ),
        "each_seed_high_minus_low_log_loss_negative": all(
            value["log_loss"] < 0.0 for value in high_low_by_seed.values()
        ),
        "each_seed_high_minus_low_brier_negative": all(
            value["brier"] < 0.0 for value in high_low_by_seed.values()
        ),
        "high_minus_low_log_loss_ci_upper_negative": high_low_ci["log_loss"][1] < 0.0,
        "high_minus_low_brier_ci_upper_negative": high_low_ci["brier"][1] < 0.0,
    }
    proper_pass = all(proper_gates.values())
    baseline = "char_tfidf_lr"
    high_baseline_by_seed = {
        str(seed): {
            field: metrics[model_name(8.0, seed)][f"task_macro_{field}"]
            - metrics[baseline][f"task_macro_{field}"]
            for field in ("log_loss", "brier")
        }
        for seed in seeds
    }
    high_baseline_task = {
        field: {
            task: average(
                internals[model_name(8.0, seed)]["per_task"][task][field]
                for seed in seeds
            ) - internals[baseline]["per_task"][task][field]
            for task in tasks
        }
        for field in ("log_loss", "brier")
    }
    high_baseline_ci = {
        field: interval(high_baseline_task[field], extension, f"high-baseline:{field}")
        for field in ("log_loss", "brier")
    }
    baseline_gates = {
        "each_high_seed_log_loss_below_baseline": all(
            value["log_loss"] < 0.0 for value in high_baseline_by_seed.values()
        ),
        "each_high_seed_brier_below_baseline": all(
            value["brier"] < 0.0 for value in high_baseline_by_seed.values()
        ),
        "high_minus_baseline_log_loss_ci_upper_negative": high_baseline_ci["log_loss"][1] < 0.0,
        "high_minus_baseline_brier_ci_upper_negative": high_baseline_ci["brier"][1] < 0.0,
    }
    baseline_pass = all(baseline_gates.values())
    half_key = f"{float(extension['selective_execution']['primary_coverage_target']):g}"
    selective_by_seed: dict[str, dict[str, float]] = {}
    for seed in seeds:
        predictor = model_name(8.0, seed)
        half = internals[predictor]["coverage"][half_key]["aggregate"]
        full = internals[predictor]["coverage"]["1"]["aggregate"]
        selective_by_seed[str(seed)] = {
            "realized_coverage": half["realized_coverage"],
            "accepted_error": half["task_macro_accepted_error"],
            "full_error": full["task_macro_accepted_error"],
            "excess_gap_regret_vs_random_acceptance": half[
                "task_macro_excess_gap_regret_vs_random_acceptance"
            ],
        }
    half_full_task = {
        task: average(
            internals[model_name(8.0, seed)]["coverage"][half_key]["per_task"][task]["accepted_error"]
            - internals[model_name(8.0, seed)]["coverage"]["1"]["per_task"][task]["accepted_error"]
            for seed in seeds
        )
        for task in tasks
    }
    excess_task = {
        task: average(
            internals[model_name(8.0, seed)]["coverage"][half_key]["per_task"][task][
                "excess_gap_regret_vs_random_acceptance"
            ]
            for seed in seeds
        )
        for task in tasks
    }
    half_ci = interval(half_full_task, extension, "selective:half-full-error")
    excess_ci = interval(excess_task, extension, "selective:excess-regret")
    minimum = float(extension["hierarchical_gates"]["selective_confidence"]["realized_coverage_min"])
    maximum = float(extension["hierarchical_gates"]["selective_confidence"]["realized_coverage_max"])
    selective_gates = {
        "each_high_seed_realized_coverage_in_range": all(
            minimum <= value["realized_coverage"] <= maximum
            for value in selective_by_seed.values()
        ),
        "each_high_seed_half_error_below_full_error": all(
            value["accepted_error"] < value["full_error"]
            for value in selective_by_seed.values()
        ),
        "half_minus_full_error_ci_upper_negative": half_ci[1] < 0.0,
        "excess_gap_regret_vs_random_ci_upper_negative": excess_ci[1] < 0.0,
    }
    selective_pass = all(selective_gates.values())
    primary_confirmed = primary_summary["status"] in {
        "STRONG_CLEAN_SCALING_BASELINE_AND_UTILITY_PASS",
        "CLEAN_SCALING_AND_BASELINE_PASS_UTILITY_NOT_CONFIRMED",
        "CLEAN_SCALING_PASS_BASELINE_NOT_CONFIRMED",
    }
    secondary_pass = support_pass and proper_pass and selective_pass
    if secondary_pass and baseline_pass and primary_confirmed:
        status = "PRIMARY_CONFIRMED_SECONDARY_CONFIDENCE_COST_AND_BASELINE_PASS"
    elif secondary_pass and primary_confirmed:
        status = "PRIMARY_CONFIRMED_SECONDARY_CONFIDENCE_COST_PASS_BASELINE_NOT_CONFIRMED"
    elif secondary_pass:
        status = "SECONDARY_SIGNAL_PRESENT_PRIMARY_NOT_RESCUED"
    else:
        status = "VALID_NO_SECONDARY_CONFIDENCE_COST_CONFIRMATION"
    return {
        "status": status,
        "primary_status": primary_summary["status"],
        "primary_clean_scaling_confirmed": primary_confirmed,
        "secondary_can_rescue_primary": False,
        "support": {
            "primary_support_pass": primary_support,
            "dev_pairs": len(dev_rows),
            "dev_tasks": len(dev_counts),
            "dev_dominant_task_pair_share": dominant,
            "overlap": dict(overlap),
            "gates": support_gates,
            "pass": support_pass,
        },
        "proper_score_scaling": {
            "size_mean_scores": size_scores,
            "high_minus_low_by_seed": high_low_by_seed,
            "high_minus_low_task_bootstrap_ci": high_low_ci,
            "gates": proper_gates,
            "pass": proper_pass,
        },
        "high_size_vs_baseline": {
            "high_minus_baseline_by_seed": high_baseline_by_seed,
            "high_minus_baseline_task_bootstrap_ci": high_baseline_ci,
            "gates": baseline_gates,
            "pass": baseline_pass,
        },
        "selective_confidence": {
            "coverage_target": float(half_key),
            "by_seed": selective_by_seed,
            "half_minus_full_error_task_bootstrap_ci": half_ci,
            "excess_gap_regret_vs_random_task_bootstrap_ci": excess_ci,
            "gates": selective_gates,
            "pass": selective_pass,
        },
    }


def compare(expected: Any, observed: Any, path: str = "root") -> None:
    if isinstance(expected, dict):
        if not isinstance(observed, dict) or set(expected) != set(observed):
            raise VerificationError(f"{path} object keys differ")
        for key in sorted(expected):
            compare(expected[key], observed[key], f"{path}.{key}")
    elif isinstance(expected, list):
        if not isinstance(observed, list) or len(expected) != len(observed):
            raise VerificationError(f"{path} list shape differs")
        for index, (left, right) in enumerate(zip(expected, observed)):
            compare(left, right, f"{path}[{index}]")
    elif isinstance(expected, (int, float)) and not isinstance(expected, bool):
        if isinstance(observed, bool) or not isinstance(observed, (int, float)):
            raise VerificationError(f"{path} numeric type differs")
        if not math.isclose(float(expected), float(observed), rel_tol=0.0, abs_tol=1e-12):
            raise VerificationError(f"{path} numeric value differs")
    elif expected != observed:
        raise VerificationError(f"{path} value differs")


def verify_csvs(
    result_dir: Path,
    internals: Mapping[str, Mapping[str, Any]],
    coverage_rows: Sequence[Mapping[str, Any]],
) -> None:
    task_path = result_dir / "per_predictor_task.csv"
    with task_path.open("r", encoding="utf-8", newline="") as handle:
        observed = list(csv.DictReader(handle))
    expected = []
    for predictor in sorted(internals):
        for task in sorted(internals[predictor]["per_task"]):
            row = internals[predictor]["per_task"][task]
            expected.append(
                {
                    "predictor_id": predictor,
                    "task": task,
                    "pairs": str(row["pairs"]),
                    "accuracy": str(row["accuracy"]),
                    "log_loss": str(row["log_loss"]),
                    "brier": str(row["brier"]),
                }
            )
    if observed != expected:
        raise VerificationError("per_predictor_task.csv differs from source reconstruction")
    coverage_path = result_dir / "per_predictor_coverage.csv"
    with coverage_path.open("r", encoding="utf-8", newline="") as handle:
        observed_coverage = list(csv.DictReader(handle))
    expected_coverage = []
    fields = [
        "predictor_id", "target_coverage", "realized_coverage", "execution_saving_fraction",
        "task_macro_accepted_error", "task_macro_accepted_gap_weighted_error",
        "task_macro_total_gap_regret", "task_macro_excess_gap_regret_vs_random_acceptance",
    ]
    for row in sorted(coverage_rows, key=lambda value: (value["predictor_id"], value["target_coverage"])):
        expected_coverage.append({field: str(row[field]) for field in fields})
    if observed_coverage != expected_coverage:
        raise VerificationError("per_predictor_coverage.csv differs from source reconstruction")


def verify_manifest(result_dir: Path) -> dict[str, dict[str, Any]]:
    manifest = object_from(result_dir / "artifact_manifest.json", "artifact manifest")
    expected_names = {"summary.json", "per_predictor_task.csv", "per_predictor_coverage.csv"}
    if set(manifest) != expected_names:
        raise VerificationError("artifact manifest file set differs")
    for name in sorted(expected_names):
        path = result_dir / name
        if manifest[name] != {"bytes": path.stat().st_size, "sha256": digest(path)}:
            raise VerificationError(f"artifact manifest differs for {name}")
    return manifest


def verify(
    primary_contract_path: Path,
    extension_contract_path: Path,
    primary_lock_path: Path,
    calibration_lock_path: Path,
    primary_bundle_path: Path,
    result_dir: Path,
) -> dict[str, Any]:
    primary_contract = primary.read_object(primary_contract_path, "primary contract")
    primary.validate_contract(primary_contract)
    primary_sha = primary.sha256_file(primary_contract_path)
    extension = extension_contract(extension_contract_path, primary_sha)
    extension_sha = digest(extension_contract_path)
    primary_lock = primary.read_object(primary_lock_path, "primary lock")
    locked_runs = primary.validate_lock(primary_lock, primary_contract, primary_sha)
    primary_lock_sha = primary.sha256_file(primary_lock_path)
    primary_bundle = primary.read_object(primary_bundle_path, "primary bundle")
    try:
        test_truth, test_predictions, primary_artifacts = primary.validate_bundle(
            primary_bundle_path,
            primary_bundle,
            primary_lock,
            primary_lock_sha,
            locked_runs,
            primary_contract,
        )
        primary_summary, _, _, _ = primary.analyze(
            primary_contract_path, primary_lock_path, primary_bundle_path
        )
    except primary.ConfirmationError as exc:
        raise VerificationError(str(exc)) from exc
    dev_truth, dev_predictions, dev_artifacts = load_dev(
        calibration_lock_path,
        extension,
        extension_sha,
        primary_contract,
        primary_sha,
        primary_lock,
        primary_lock_sha,
        locked_runs,
    )
    overlap = overlaps(dev_truth, test_truth)
    if any(overlap.values()):
        raise VerificationError("dev/test overlap is nonzero")
    if set(dev_predictions) != set(test_predictions):
        raise VerificationError("dev/test predictor matrices differ")
    semantics = extension["metrics"]["primary_pair_semantics"]
    dev_ids = sorted(pair_id for pair_id, row in dev_truth.items() if row["pair_semantics"] == semantics)
    metrics: dict[str, dict[str, Any]] = {}
    internals: dict[str, dict[str, Any]] = {}
    coverage_rows: list[dict[str, Any]] = []
    for predictor in sorted(test_predictions):
        calibration = calibrate(
            [float(dev_predictions[predictor][pair_id]["margin"]) for pair_id in dev_ids],
            extension,
        )
        metric, internal, rows = rebuild_predictor(
            predictor, test_truth, test_predictions[predictor], calibration, extension
        )
        metrics[predictor] = metric
        internals[predictor] = internal
        coverage_rows.extend(rows)
    conclusion = rebuild_decision(
        extension, primary_summary, metrics, internals, dev_truth, overlap
    )
    expected_summary = {
        "protocol": ANALYSIS_PROTOCOL,
        "status": conclusion["status"],
        "input_identity": {
            "primary_contract_sha256": primary_sha,
            "extension_contract_sha256": extension_sha,
            "primary_lock_sha256": primary_lock_sha,
            "calibration_lock_sha256": digest(calibration_lock_path),
            "primary_bundle_sha256": digest(primary_bundle_path),
            "primary_artifacts": primary_artifacts,
            "dev_artifacts": dev_artifacts,
        },
        "access_attestation": {
            "gpu_jobs": 0,
            "api_calls": 0,
            "model_fits": 0,
            "base_llm_updates": 0,
            "real_future_truth_read": False,
            "historical_test_touched_assets_used": False,
        },
        "predictors": metrics,
        "decision": conclusion,
    }
    released = object_from(result_dir / "summary.json", "released summary")
    compare(expected_summary, released)
    verify_csvs(result_dir, internals, coverage_rows)
    manifest = verify_manifest(result_dir)
    return {
        "protocol": "critic-scaling-confidence-cost-independent-verification-v1",
        "status": "INDEPENDENT_VERIFICATION_PASS",
        "analysis_status": conclusion["status"],
        "extension_contract_sha256": extension_sha,
        "primary_contract_sha256": primary_sha,
        "primary_lock_sha256": primary_lock_sha,
        "calibration_lock_sha256": digest(calibration_lock_path),
        "primary_bundle_sha256": digest(primary_bundle_path),
        "result_manifest_sha256": digest(result_dir / "artifact_manifest.json"),
        "verified_artifacts": manifest,
        "predictors": len(metrics),
        "gpu_jobs": 0,
        "api_calls": 0,
        "model_fits": 0,
        "real_future_truth_read": False,
    }


def main() -> None:
    args = cli()
    receipt = verify(
        args.primary_contract,
        args.extension_contract,
        args.primary_lock,
        args.calibration_lock,
        args.primary_bundle,
        args.result_dir,
    )
    if args.receipt.exists():
        raise FileExistsError(f"refusing to overwrite {args.receipt}")
    args.receipt.parent.mkdir(parents=True, exist_ok=True)
    args.receipt.write_bytes(canonical(receipt))
    print(json.dumps({"status": receipt["status"], "receipt": str(args.receipt)}, sort_keys=True))


if __name__ == "__main__":
    main()
