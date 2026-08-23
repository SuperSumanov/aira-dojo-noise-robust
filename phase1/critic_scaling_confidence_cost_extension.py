#!/usr/bin/env python3
"""Pre-registered proper-score and confidence-cost extension for clean critic scaling.

The producer deliberately reuses the already frozen primary input validator.  The
independent extension verifier does not import this module and reconstructs every
derived calibration, task metric, interval, and gate from the source bundles.
"""

from __future__ import annotations

import argparse
import collections
import csv
import hashlib
import json
import math
import statistics
from pathlib import Path
from typing import Any, Iterable, Mapping, Sequence

from phase1 import critic_scaling_confirmation_analysis as primary


EXTENSION_PROTOCOL = "critic-scaling-confidence-cost-extension-v1"
CALIBRATION_LOCK_PROTOCOL = "critic-scaling-confidence-cost-lock-v1"
ANALYSIS_PROTOCOL = "critic-scaling-confidence-cost-analysis-v1"


class ConfidenceCostError(RuntimeError):
    """Raised when an input or a pre-registered condition fails closed."""


def arguments() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--primary-contract", type=Path, required=True)
    parser.add_argument("--extension-contract", type=Path, required=True)
    parser.add_argument("--primary-lock", type=Path, required=True)
    parser.add_argument("--calibration-lock", type=Path, required=True)
    parser.add_argument("--primary-bundle", type=Path, required=True)
    parser.add_argument("--out-dir", type=Path, required=True)
    return parser.parse_args()


def canonical_bytes(value: Any) -> bytes:
    return (json.dumps(value, sort_keys=True, separators=(",", ":")) + "\n").encode()


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def read_object(path: Path, label: str) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ConfidenceCostError(f"cannot read {label}: {exc}") from exc
    if not isinstance(value, dict):
        raise ConfidenceCostError(f"{label} is not an object")
    return value


def read_jsonl(path: Path, label: str) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    try:
        with path.open("r", encoding="utf-8") as handle:
            for line_number, line in enumerate(handle, 1):
                if not line.strip():
                    raise ConfidenceCostError(f"{label} has blank line {line_number}")
                value = json.loads(line)
                if not isinstance(value, dict):
                    raise ConfidenceCostError(f"{label} row {line_number} is not an object")
                rows.append(value)
    except (OSError, json.JSONDecodeError) as exc:
        raise ConfidenceCostError(f"cannot read {label}: {exc}") from exc
    if not rows:
        raise ConfidenceCostError(f"{label} is empty")
    return rows


def checked_artifact(root: Path, spec: Any, label: str) -> tuple[Path, str, int]:
    if not isinstance(spec, dict):
        raise ConfidenceCostError(f"{label} artifact spec is absent")
    relative = spec.get("path")
    if not isinstance(relative, str) or not relative or Path(relative).is_absolute():
        raise ConfidenceCostError(f"{label} path is not a safe relative path")
    candidate = root / relative
    try:
        resolved_root = root.resolve(strict=True)
        resolved = candidate.resolve(strict=True)
    except OSError as exc:
        raise ConfidenceCostError(f"cannot resolve {label}: {exc}") from exc
    if resolved == resolved_root or resolved_root not in resolved.parents:
        raise ConfidenceCostError(f"{label} escapes the lock directory")
    if candidate.is_symlink() or not resolved.is_file():
        raise ConfidenceCostError(f"{label} is not a regular non-symlink file")
    digest = spec.get("sha256")
    rows = spec.get("rows")
    if not isinstance(digest, str) or len(digest) != 64:
        raise ConfidenceCostError(f"{label} SHA256 is invalid")
    if not isinstance(rows, int) or rows <= 0:
        raise ConfidenceCostError(f"{label} row count is invalid")
    if sha256_file(resolved) != digest:
        raise ConfidenceCostError(f"{label} SHA256 mismatch")
    return resolved, digest, rows


def finite(value: Any, label: str) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ConfidenceCostError(f"{label} is not numeric")
    output = float(value)
    if not math.isfinite(output):
        raise ConfidenceCostError(f"{label} is not finite")
    return output


def mean(values: Iterable[float]) -> float:
    items = [float(value) for value in values]
    if not items:
        raise ConfidenceCostError("cannot average an empty collection")
    return math.fsum(items) / len(items)


def grouped_mean(items: Iterable[tuple[str, float]]) -> dict[str, float]:
    groups: dict[str, list[float]] = collections.defaultdict(list)
    for key, value in items:
        groups[key].append(float(value))
    return {key: mean(groups[key]) for key in sorted(groups)}


def validate_extension_contract(
    extension: Mapping[str, Any], extension_sha: str, primary_sha: str
) -> None:
    if extension.get("protocol") != EXTENSION_PROTOCOL:
        raise ConfidenceCostError("wrong extension contract protocol")
    if extension.get("status") not in {
        "PRE_REGISTERED_SYNTHETIC_VALIDATION_PENDING",
        "ANALYZER_READY_EFFECT_ASSETS_PENDING",
    }:
        raise ConfidenceCostError("extension contract status is not frozen")
    binding = extension.get("binding")
    if not isinstance(binding, dict):
        raise ConfidenceCostError("extension binding is absent")
    if binding.get("primary_contract_sha256") != primary_sha:
        raise ConfidenceCostError("extension binds a different primary contract")
    for field in (
        "same_primary_lock_required",
        "same_test_bundle_required",
        "same_predictor_matrix_required",
        "primary_decision_may_not_be_changed",
        "secondary_result_may_not_rescue_failed_primary",
    ):
        if binding.get(field) is not True:
            raise ConfidenceCostError(f"extension weakens binding field {field}")
    access = extension.get("access_and_compute")
    expected_access = {
        "gpu_jobs_authorized": 0,
        "api_calls_authorized": 0,
        "model_fits_authorized": 0,
        "base_llm_updates_authorized": 0,
        "future_truth_reads_authorized": False,
        "real_effect_run_authorized": False,
        "synthetic_tests_authorized": True,
    }
    if access != expected_access:
        raise ConfidenceCostError("extension accidentally authorizes compute or truth")
    if len(extension_sha) != 64:
        raise ConfidenceCostError("extension SHA is malformed")


def dev_pair_id(row: Mapping[str, Any]) -> str:
    payload = [
        row.get("task"),
        row.get("pair_semantics"),
        row.get("parent_id"),
        row.get("comparison_component_id"),
        row.get("better_id"),
        row.get("worse_id"),
    ]
    return hashlib.sha256(canonical_bytes(payload)).hexdigest()


def validate_dev_truth(
    rows: Sequence[dict[str, Any]], primary_contract: Mapping[str, Any]
) -> dict[str, dict[str, Any]]:
    required = set(primary_contract["prediction_schema"]["truth_required_fields"])
    output: dict[str, dict[str, Any]] = {}
    unordered: set[tuple[str, str, str, str, frozenset[str]]] = set()
    endpoint_utilities: dict[str, float] = {}
    for index, source in enumerate(rows):
        if not required.issubset(source):
            raise ConfidenceCostError(f"dev truth row {index} lacks required fields")
        row = dict(source)
        if row.get("split") != "dev":
            raise ConfidenceCostError(f"dev truth row {index} is not dev")
        for field in (
            "pair_id", "task", "pair_semantics", "parent_id", "parent_run_id",
            "comparison_component_id", "better_id", "worse_id", "better_run_id",
            "worse_run_id",
        ):
            if not isinstance(row.get(field), str) or not row[field]:
                raise ConfidenceCostError(f"dev truth row {index} has invalid {field}")
        if row["better_id"] == row["worse_id"]:
            raise ConfidenceCostError("dev truth contains a self pair")
        better = finite(row["better_utility"], "dev better utility")
        worse = finite(row["worse_utility"], "dev worse utility")
        if not better > worse:
            raise ConfidenceCostError("dev truth orientation is not strictly positive")
        row["better_utility"] = better
        row["worse_utility"] = worse
        if row["pair_id"] != dev_pair_id(row):
            raise ConfidenceCostError("dev truth pair_id mismatch")
        if row["pair_id"] in output:
            raise ConfidenceCostError("duplicate dev pair_id")
        key = (
            row["task"], row["pair_semantics"], row["parent_id"],
            row["comparison_component_id"], frozenset((row["better_id"], row["worse_id"])),
        )
        if key in unordered:
            raise ConfidenceCostError("duplicate or reversed dev unordered pair")
        unordered.add(key)
        if row["pair_semantics"] == primary_contract["cohort"]["primary_pair_semantics"] and not (
            row["parent_run_id"] == row["better_run_id"] == row["worse_run_id"]
        ):
            raise ConfidenceCostError("dev primary sibling pair crosses physical runs")
        tolerance = float(
            primary_contract["prediction_schema"]["endpoint_utility_consistency_tolerance"]
        )
        for endpoint, utility in ((row["better_id"], better), (row["worse_id"], worse)):
            previous = endpoint_utilities.setdefault(endpoint, utility)
            if not math.isclose(previous, utility, rel_tol=0.0, abs_tol=tolerance):
                raise ConfidenceCostError("dev endpoint utility is inconsistent")
        output[row["pair_id"]] = row
    return output


def validate_dev_predictions(
    rows: Sequence[dict[str, Any]],
    truth: Mapping[str, dict[str, Any]],
    primary_contract: Mapping[str, Any],
    label: str,
) -> dict[str, dict[str, float | str]]:
    try:
        return primary.validate_predictions(rows, truth, primary_contract, label)
    except primary.ConfirmationError as exc:
        raise ConfidenceCostError(str(exc)) from exc


def matrix_key(size: float, seed: int) -> str:
    return f"qwen3_{size:g}b_seed{seed}"


def load_calibration_lock(
    path: Path,
    value: Mapping[str, Any],
    extension: Mapping[str, Any],
    extension_sha: str,
    primary_contract: Mapping[str, Any],
    primary_contract_sha: str,
    primary_lock: Mapping[str, Any],
    primary_lock_sha: str,
    locked_runs: Mapping[tuple[float, int], dict[str, Any]],
) -> tuple[dict[str, dict[str, Any]], dict[str, dict[str, dict[str, float | str]]], dict[str, Any]]:
    if value.get("protocol") != CALIBRATION_LOCK_PROTOCOL:
        raise ConfidenceCostError("wrong calibration lock protocol")
    if value.get("status") != extension["calibration_lock"]["required_status"]:
        raise ConfidenceCostError("calibration lock is not pre-test locked")
    if value.get("extension_contract_sha256") != extension_sha:
        raise ConfidenceCostError("calibration lock binds another extension contract")
    if value.get("primary_contract_sha256") != primary_contract_sha:
        raise ConfidenceCostError("calibration lock binds another primary contract")
    if value.get("primary_lock_sha256") != primary_lock_sha:
        raise ConfidenceCostError("calibration lock binds another primary lock")
    frozen_at = value.get("frozen_at_utc")
    if not isinstance(frozen_at, str) or not frozen_at.endswith("Z"):
        raise ConfidenceCostError("calibration lock lacks UTC freeze time")
    if value.get("locked_before_test_access") is not True:
        raise ConfidenceCostError("calibration lock was not frozen before test")
    root = path.parent
    truth_path, truth_sha, truth_rows = checked_artifact(root, value.get("dev_truth"), "dev truth")
    raw_truth = read_jsonl(truth_path, "dev truth")
    if len(raw_truth) != truth_rows:
        raise ConfidenceCostError("dev truth row count mismatch")
    truth = validate_dev_truth(raw_truth, primary_contract)

    predictions: dict[str, dict[str, dict[str, float | str]]] = {}
    receipts: dict[str, Any] = {
        "dev_truth": {"path": value["dev_truth"]["path"], "sha256": truth_sha, "rows": len(truth)}
    }
    baseline = value.get("baseline")
    if not isinstance(baseline, dict) or baseline.get("id") != primary_contract["baseline"]["id"]:
        raise ConfidenceCostError("calibration baseline identity mismatch")
    if baseline.get("receipt_sha256") != primary_lock["baseline"]["receipt_sha256"]:
        raise ConfidenceCostError("calibration baseline receipt mismatch")
    baseline_path, baseline_sha, baseline_rows = checked_artifact(
        root, baseline.get("predictions"), "dev baseline predictions"
    )
    if baseline_rows != len(truth):
        raise ConfidenceCostError("dev baseline coverage mismatch")
    baseline_id = primary_contract["baseline"]["id"]
    predictions[baseline_id] = validate_dev_predictions(
        read_jsonl(baseline_path, "dev baseline predictions"), truth, primary_contract, baseline_id
    )
    receipts[baseline_id] = {"path": baseline["predictions"]["path"], "sha256": baseline_sha, "rows": baseline_rows}

    run_specs = value.get("runs")
    if not isinstance(run_specs, list):
        raise ConfidenceCostError("calibration runs are absent")
    seen: set[tuple[float, int]] = set()
    for spec in run_specs:
        if not isinstance(spec, dict):
            raise ConfidenceCostError("calibration run is not an object")
        size = finite(spec.get("model_size_b"), "calibration model size")
        seed = spec.get("seed")
        if not isinstance(seed, int):
            raise ConfidenceCostError("calibration model seed is invalid")
        key = (size, seed)
        if key in seen or key not in locked_runs:
            raise ConfidenceCostError("calibration model matrix has duplicate or extra run")
        seen.add(key)
        checkpoint = locked_runs[key]["checkpoint_manifest_sha256"]
        if spec.get("checkpoint_manifest_sha256") != checkpoint:
            raise ConfidenceCostError("dev prediction checkpoint differs from primary lock")
        predictor = matrix_key(size, seed)
        prediction_path, prediction_sha, prediction_rows = checked_artifact(
            root, spec.get("predictions"), f"{predictor} dev predictions"
        )
        if prediction_rows != len(truth):
            raise ConfidenceCostError(f"{predictor} dev coverage mismatch")
        predictions[predictor] = validate_dev_predictions(
            read_jsonl(prediction_path, f"{predictor} dev predictions"),
            truth,
            primary_contract,
            predictor,
        )
        receipts[predictor] = {
            "path": spec["predictions"]["path"],
            "sha256": prediction_sha,
            "rows": prediction_rows,
            "checkpoint_manifest_sha256": checkpoint,
        }
    if seen != set(locked_runs):
        raise ConfidenceCostError("calibration model matrix is incomplete")
    return truth, predictions, receipts


def overlap_receipt(
    dev_truth: Mapping[str, Mapping[str, Any]],
    test_truth: Mapping[str, Mapping[str, Any]],
) -> dict[str, int]:
    def endpoints(rows: Iterable[Mapping[str, Any]]) -> set[str]:
        return {str(row[field]) for row in rows for field in ("better_id", "worse_id")}

    def runs(rows: Iterable[Mapping[str, Any]]) -> set[str]:
        return {
            str(row[field])
            for row in rows
            for field in ("parent_run_id", "better_run_id", "worse_run_id")
        }

    def pairs(rows: Iterable[Mapping[str, Any]]) -> set[tuple[str, frozenset[str]]]:
        return {
            (str(row["task"]), frozenset((str(row["better_id"]), str(row["worse_id"]))))
            for row in rows
        }

    return {
        "endpoint_overlap": len(endpoints(dev_truth.values()) & endpoints(test_truth.values())),
        "physical_run_overlap": len(runs(dev_truth.values()) & runs(test_truth.values())),
        "unordered_pair_overlap": len(pairs(dev_truth.values()) & pairs(test_truth.values())),
    }


def inverse_temperature(margins: Sequence[float], contract: Mapping[str, Any]) -> dict[str, Any]:
    if not margins:
        raise ConfidenceCostError("cannot calibrate on empty margins")
    config = contract["probability_map"]
    nonzero = sorted(abs(value) for value in margins if value != 0.0)
    scale = statistics.median(nonzero) if nonzero else float(config["zero_margin_scale_fallback"])
    if not math.isfinite(scale) or scale <= 0.0:
        raise ConfidenceCostError("invalid dev margin scale")
    normalized = [value / scale for value in margins]
    lower = float(config["inverse_temperature_min"])
    upper = float(config["inverse_temperature_max"])
    iterations = int(config["optimizer_iterations"])

    def derivative(beta: float) -> float:
        terms: list[float] = []
        for value in normalized:
            product = beta * value
            if product >= 0.0:
                weight = math.exp(-product) / (1.0 + math.exp(-product))
            else:
                weight = 1.0 / (1.0 + math.exp(product))
            terms.append(-value * weight)
        return mean(terms)

    lower_derivative = derivative(lower)
    upper_derivative = derivative(upper)
    if lower_derivative >= 0.0:
        beta = lower
        boundary = "lower"
    elif upper_derivative <= 0.0:
        beta = upper
        boundary = "upper"
    else:
        left, right = lower, upper
        for _ in range(iterations):
            middle = (left + right) / 2.0
            if derivative(middle) < 0.0:
                left = middle
            else:
                right = middle
        beta = (left + right) / 2.0
        boundary = "interior"
    return {
        "dev_margin_scale": scale,
        "inverse_temperature": beta,
        "boundary": boundary,
        "dev_rows": len(margins),
        "derivative_at_min": lower_derivative,
        "derivative_at_max": upper_derivative,
    }


def sigmoid(value: float) -> float:
    if value >= 0.0:
        tail = math.exp(-value)
        return 1.0 / (1.0 + tail)
    head = math.exp(value)
    return head / (1.0 + head)


def softplus(value: float) -> float:
    return max(value, 0.0) + math.log1p(math.exp(-abs(value)))


def selection_id(row: Mapping[str, Any]) -> str:
    payload = [
        row["task"], row["parent_id"], row["comparison_component_id"],
        sorted((row["better_id"], row["worse_id"])),
    ]
    return hashlib.sha256(canonical_bytes(payload)).hexdigest()


def predictor_metrics(
    predictor_id: str,
    test_truth: Mapping[str, dict[str, Any]],
    test_predictions: Mapping[str, Mapping[str, float | str]],
    calibration: Mapping[str, Any],
    extension: Mapping[str, Any],
    primary_contract: Mapping[str, Any],
) -> tuple[dict[str, Any], dict[str, dict[str, Any]], list[dict[str, Any]]]:
    semantics = extension["metrics"]["primary_pair_semantics"]
    rows = [test_truth[key] for key in sorted(test_truth) if test_truth[key]["pair_semantics"] == semantics]
    if not rows:
        raise ConfidenceCostError("test primary semantics has no rows")
    beta = float(calibration["inverse_temperature"])
    scale = float(calibration["dev_margin_scale"])
    pair_values: dict[str, dict[str, float]] = {}
    for row in rows:
        margin = float(test_predictions[row["pair_id"]]["margin"])
        logit = beta * margin / scale
        probability = sigmoid(logit)
        credit = primary.tie_credit(margin)
        pair_values[row["pair_id"]] = {
            "logit": logit,
            "confidence": sigmoid(abs(logit)),
            "credit": credit,
            "error": 1.0 - credit,
            "log_loss": softplus(-logit),
            "brier": (1.0 - probability) ** 2,
            "gap": float(row["better_utility"]) - float(row["worse_utility"]),
        }
    per_task: dict[str, dict[str, Any]] = {}
    grouped: dict[str, list[dict[str, Any]]] = collections.defaultdict(list)
    for row in rows:
        grouped[row["task"]].append(row)
    for task in sorted(grouped):
        task_rows = grouped[task]
        per_task[task] = {
            "pairs": len(task_rows),
            "accuracy": mean(pair_values[row["pair_id"]]["credit"] for row in task_rows),
            "log_loss": mean(pair_values[row["pair_id"]]["log_loss"] for row in task_rows),
            "brier": mean(pair_values[row["pair_id"]]["brier"] for row in task_rows),
        }

    bins = int(extension["metrics"]["ece_bins"])
    bin_values: dict[int, list[tuple[float, float]]] = collections.defaultdict(list)
    for value in pair_values.values():
        index = min(bins - 1, int((value["confidence"] - 0.5) * 2.0 * bins))
        bin_values[index].append((value["confidence"], value["credit"]))
    ece = math.fsum(
        (len(values) / len(pair_values))
        * abs(mean(item[0] for item in values) - mean(item[1] for item in values))
        for values in bin_values.values()
    )

    coverage_rows: list[dict[str, Any]] = []
    coverage_internal: dict[str, dict[str, Any]] = {}
    for target_value in extension["selective_execution"]["coverage_targets"]:
        target = float(target_value)
        task_records: dict[str, dict[str, float | int]] = {}
        accepted_total = 0
        for task in sorted(grouped):
            task_rows = grouped[task]
            ordered = sorted(
                task_rows,
                key=lambda row: (
                    -abs(pair_values[row["pair_id"]]["logit"]),
                    selection_id(row),
                ),
            )
            count = max(1, min(len(ordered), int(math.floor(target * len(ordered) + 0.5))))
            accepted = ordered[:count]
            accepted_total += count
            all_gap = math.fsum(pair_values[row["pair_id"]]["gap"] for row in ordered)
            accepted_gap = math.fsum(pair_values[row["pair_id"]]["gap"] for row in accepted)
            regret = math.fsum(
                pair_values[row["pair_id"]]["gap"] * pair_values[row["pair_id"]]["error"]
                for row in accepted
            )
            full_regret = math.fsum(
                pair_values[row["pair_id"]]["gap"] * pair_values[row["pair_id"]]["error"]
                for row in ordered
            ) / all_gap
            realized = count / len(ordered)
            task_records[task] = {
                "pairs": len(ordered),
                "accepted": count,
                "coverage": realized,
                "accepted_error": mean(pair_values[row["pair_id"]]["error"] for row in accepted),
                "accepted_gap_weighted_error": regret / accepted_gap,
                "total_gap_regret": regret / all_gap,
                "excess_gap_regret_vs_random_acceptance": regret / all_gap - realized * full_regret,
            }
        key = f"{target:g}"
        aggregated = {
            "target_coverage": target,
            "realized_coverage": accepted_total / len(rows),
            "execution_saving_fraction": (accepted_total / len(rows)) / 2.0,
            "task_macro_accepted_error": mean(record["accepted_error"] for record in task_records.values()),
            "task_macro_accepted_gap_weighted_error": mean(
                record["accepted_gap_weighted_error"] for record in task_records.values()
            ),
            "task_macro_total_gap_regret": mean(record["total_gap_regret"] for record in task_records.values()),
            "task_macro_excess_gap_regret_vs_random_acceptance": mean(
                record["excess_gap_regret_vs_random_acceptance"] for record in task_records.values()
            ),
        }
        coverage_internal[key] = {"aggregate": aggregated, "per_task": task_records}
        coverage_rows.append({"predictor_id": predictor_id, **aggregated})

    metric = {
        "predictor_id": predictor_id,
        "calibration": dict(calibration),
        "pairs": len(rows),
        "tasks": len(per_task),
        "micro_accuracy": mean(value["credit"] for value in pair_values.values()),
        "micro_log_loss": mean(value["log_loss"] for value in pair_values.values()),
        "micro_brier": mean(value["brier"] for value in pair_values.values()),
        "fixed_bin_ece": ece,
        "task_macro_accuracy": mean(value["accuracy"] for value in per_task.values()),
        "task_macro_log_loss": mean(value["log_loss"] for value in per_task.values()),
        "task_macro_brier": mean(value["brier"] for value in per_task.values()),
        "coverage": {key: value["aggregate"] for key, value in coverage_internal.items()},
    }
    internal = {"per_task": per_task, "coverage": coverage_internal}
    return metric, internal, coverage_rows


def paired_ci(values: Mapping[str, float], extension: Mapping[str, Any], label: str) -> list[float]:
    return primary.bootstrap_ci(
        values,
        draws=int(extension["metrics"]["bootstrap_draws"]),
        seed=primary.deterministic_seed(int(extension["metrics"]["bootstrap_seed"]), label),
    )


def decision(
    extension: Mapping[str, Any],
    primary_summary: Mapping[str, Any],
    metrics: Mapping[str, Mapping[str, Any]],
    internals: Mapping[str, Mapping[str, Any]],
    dev_truth: Mapping[str, Mapping[str, Any]],
    overlap: Mapping[str, int],
) -> dict[str, Any]:
    sizes = [float(value) for value in (0.6, 1.7, 4.0, 8.0)]
    seeds = [6, 7]
    baseline = "char_tfidf_lr"
    dev_primary = [
        row for row in dev_truth.values()
        if row["pair_semantics"] == extension["metrics"]["primary_pair_semantics"]
    ]
    dev_counts = collections.Counter(row["task"] for row in dev_primary)
    dev_dominant = max(dev_counts.values()) / len(dev_primary)
    dev_gate = {
        "pairs_at_least_200": len(dev_primary) >= int(extension["calibration_lock"]["minimum_dev_pairs"]),
        "tasks_at_least_8": len(dev_counts) >= int(extension["calibration_lock"]["minimum_dev_tasks"]),
        "dominant_task_share_at_most_0_35": dev_dominant <= float(
            extension["calibration_lock"]["maximum_dominant_dev_task_pair_share"]
        ),
        "dev_test_endpoint_overlap_zero": overlap["endpoint_overlap"] == 0,
        "dev_test_physical_run_overlap_zero": overlap["physical_run_overlap"] == 0,
        "dev_test_unordered_pair_overlap_zero": overlap["unordered_pair_overlap"] == 0,
    }
    primary_support = bool(primary_summary["decision"]["support"]["pass"])
    support_pass = primary_support and all(dev_gate.values())

    size_scores: dict[str, dict[str, float]] = {}
    for size in sizes:
        size_scores[f"{size:g}"] = {
            name: mean(metrics[matrix_key(size, seed)][name] for seed in seeds)
            for name in ("task_macro_log_loss", "task_macro_brier")
        }
    monotonic_log = all(
        size_scores[f"{left:g}"]["task_macro_log_loss"]
        >= size_scores[f"{right:g}"]["task_macro_log_loss"]
        for left, right in zip(sizes, sizes[1:])
    )
    monotonic_brier = all(
        size_scores[f"{left:g}"]["task_macro_brier"]
        >= size_scores[f"{right:g}"]["task_macro_brier"]
        for left, right in zip(sizes, sizes[1:])
    )
    high_low_by_seed: dict[str, dict[str, float]] = {}
    high_low_task: dict[str, dict[str, float]] = {"log_loss": {}, "brier": {}}
    tasks = sorted(internals[matrix_key(8.0, 6)]["per_task"])
    for seed in seeds:
        high = matrix_key(8.0, seed)
        low = matrix_key(0.6, seed)
        high_low_by_seed[str(seed)] = {
            "log_loss": metrics[high]["task_macro_log_loss"] - metrics[low]["task_macro_log_loss"],
            "brier": metrics[high]["task_macro_brier"] - metrics[low]["task_macro_brier"],
        }
    for task in tasks:
        for field in ("log_loss", "brier"):
            high_low_task[field][task] = mean(
                internals[matrix_key(8.0, seed)]["per_task"][task][field]
                - internals[matrix_key(0.6, seed)]["per_task"][task][field]
                for seed in seeds
            )
    high_low_ci = {
        field: paired_ci(high_low_task[field], extension, f"high-low:{field}")
        for field in ("log_loss", "brier")
    }
    proper_gates = {
        "size_mean_log_loss_monotonic_nonincreasing": monotonic_log,
        "size_mean_brier_monotonic_nonincreasing": monotonic_brier,
        "each_seed_high_minus_low_log_loss_negative": all(
            row["log_loss"] < 0.0 for row in high_low_by_seed.values()
        ),
        "each_seed_high_minus_low_brier_negative": all(
            row["brier"] < 0.0 for row in high_low_by_seed.values()
        ),
        "high_minus_low_log_loss_ci_upper_negative": high_low_ci["log_loss"][1] < 0.0,
        "high_minus_low_brier_ci_upper_negative": high_low_ci["brier"][1] < 0.0,
    }
    proper_pass = all(proper_gates.values())

    high_baseline_by_seed: dict[str, dict[str, float]] = {}
    high_baseline_task: dict[str, dict[str, float]] = {"log_loss": {}, "brier": {}}
    for seed in seeds:
        high = matrix_key(8.0, seed)
        high_baseline_by_seed[str(seed)] = {
            field: metrics[high][f"task_macro_{field}"] - metrics[baseline][f"task_macro_{field}"]
            for field in ("log_loss", "brier")
        }
    for task in tasks:
        for field in ("log_loss", "brier"):
            high_baseline_task[field][task] = mean(
                internals[matrix_key(8.0, seed)]["per_task"][task][field]
                for seed in seeds
            ) - internals[baseline]["per_task"][task][field]
    high_baseline_ci = {
        field: paired_ci(high_baseline_task[field], extension, f"high-baseline:{field}")
        for field in ("log_loss", "brier")
    }
    baseline_gates = {
        "each_high_seed_log_loss_below_baseline": all(
            row["log_loss"] < 0.0 for row in high_baseline_by_seed.values()
        ),
        "each_high_seed_brier_below_baseline": all(
            row["brier"] < 0.0 for row in high_baseline_by_seed.values()
        ),
        "high_minus_baseline_log_loss_ci_upper_negative": high_baseline_ci["log_loss"][1] < 0.0,
        "high_minus_baseline_brier_ci_upper_negative": high_baseline_ci["brier"][1] < 0.0,
    }
    baseline_pass = all(baseline_gates.values())

    coverage_key = f"{float(extension['selective_execution']['primary_coverage_target']):g}"
    full_key = "1"
    selective_by_seed: dict[str, dict[str, float]] = {}
    half_full_task: dict[str, float] = {}
    excess_task: dict[str, float] = {}
    for seed in seeds:
        predictor = matrix_key(8.0, seed)
        half = internals[predictor]["coverage"][coverage_key]
        full = internals[predictor]["coverage"][full_key]
        selective_by_seed[str(seed)] = {
            "realized_coverage": half["aggregate"]["realized_coverage"],
            "accepted_error": half["aggregate"]["task_macro_accepted_error"],
            "full_error": full["aggregate"]["task_macro_accepted_error"],
            "excess_gap_regret_vs_random_acceptance": half["aggregate"][
                "task_macro_excess_gap_regret_vs_random_acceptance"
            ],
        }
    for task in tasks:
        half_full_task[task] = mean(
            internals[matrix_key(8.0, seed)]["coverage"][coverage_key]["per_task"][task]["accepted_error"]
            - internals[matrix_key(8.0, seed)]["coverage"][full_key]["per_task"][task]["accepted_error"]
            for seed in seeds
        )
        excess_task[task] = mean(
            internals[matrix_key(8.0, seed)]["coverage"][coverage_key]["per_task"][task][
                "excess_gap_regret_vs_random_acceptance"
            ]
            for seed in seeds
        )
    half_full_ci = paired_ci(half_full_task, extension, "selective:half-full-error")
    excess_ci = paired_ci(excess_task, extension, "selective:excess-regret")
    minimum = float(extension["hierarchical_gates"]["selective_confidence"]["realized_coverage_min"])
    maximum = float(extension["hierarchical_gates"]["selective_confidence"]["realized_coverage_max"])
    selective_gates = {
        "each_high_seed_realized_coverage_in_range": all(
            minimum <= row["realized_coverage"] <= maximum for row in selective_by_seed.values()
        ),
        "each_high_seed_half_error_below_full_error": all(
            row["accepted_error"] < row["full_error"] for row in selective_by_seed.values()
        ),
        "half_minus_full_error_ci_upper_negative": half_full_ci[1] < 0.0,
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
            "dev_pairs": len(dev_primary),
            "dev_tasks": len(dev_counts),
            "dev_dominant_task_pair_share": dev_dominant,
            "overlap": dict(overlap),
            "gates": dev_gate,
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
            "coverage_target": float(coverage_key),
            "by_seed": selective_by_seed,
            "half_minus_full_error_task_bootstrap_ci": half_full_ci,
            "excess_gap_regret_vs_random_task_bootstrap_ci": excess_ci,
            "gates": selective_gates,
            "pass": selective_pass,
        },
    }


def write_outputs(
    out_dir: Path,
    summary: Mapping[str, Any],
    internals: Mapping[str, Mapping[str, Any]],
    coverage_rows: Sequence[Mapping[str, Any]],
) -> None:
    if out_dir.exists():
        raise FileExistsError(f"refusing to overwrite {out_dir}")
    out_dir.mkdir(parents=True)
    (out_dir / "summary.json").write_bytes(canonical_bytes(summary))
    with (out_dir / "per_predictor_task.csv").open("w", encoding="utf-8", newline="") as handle:
        fields = ["predictor_id", "task", "pairs", "accuracy", "log_loss", "brier"]
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        for predictor in sorted(internals):
            for task in sorted(internals[predictor]["per_task"]):
                row = internals[predictor]["per_task"][task]
                writer.writerow({"predictor_id": predictor, "task": task, **row})
    with (out_dir / "per_predictor_coverage.csv").open("w", encoding="utf-8", newline="") as handle:
        fields = [
            "predictor_id", "target_coverage", "realized_coverage", "execution_saving_fraction",
            "task_macro_accepted_error", "task_macro_accepted_gap_weighted_error",
            "task_macro_total_gap_regret", "task_macro_excess_gap_regret_vs_random_acceptance",
        ]
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        for row in sorted(coverage_rows, key=lambda value: (value["predictor_id"], value["target_coverage"])):
            writer.writerow(row)
    manifest = {
        path.name: {"bytes": path.stat().st_size, "sha256": sha256_file(path)}
        for path in sorted(out_dir.iterdir())
        if path.is_file()
    }
    (out_dir / "artifact_manifest.json").write_bytes(canonical_bytes(manifest))


def analyze(
    primary_contract_path: Path,
    extension_contract_path: Path,
    primary_lock_path: Path,
    calibration_lock_path: Path,
    primary_bundle_path: Path,
) -> tuple[dict[str, Any], dict[str, dict[str, Any]], dict[str, dict[str, Any]], list[dict[str, Any]]]:
    primary_contract = primary.read_object(primary_contract_path, "primary contract")
    primary.validate_contract(primary_contract)
    primary_contract_sha = primary.sha256_file(primary_contract_path)
    extension = read_object(extension_contract_path, "extension contract")
    extension_sha = sha256_file(extension_contract_path)
    validate_extension_contract(extension, extension_sha, primary_contract_sha)
    primary_lock = primary.read_object(primary_lock_path, "primary lock")
    locked_runs = primary.validate_lock(primary_lock, primary_contract, primary_contract_sha)
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
        raise ConfidenceCostError(str(exc)) from exc
    calibration_lock = read_object(calibration_lock_path, "calibration lock")
    dev_truth, dev_predictions, dev_artifacts = load_calibration_lock(
        calibration_lock_path,
        calibration_lock,
        extension,
        extension_sha,
        primary_contract,
        primary_contract_sha,
        primary_lock,
        primary_lock_sha,
        locked_runs,
    )
    overlap = overlap_receipt(dev_truth, test_truth)
    if any(overlap.values()):
        raise ConfidenceCostError("dev/test identity overlap is nonzero")
    if set(dev_predictions) != set(test_predictions):
        raise ConfidenceCostError("dev and test predictor matrices differ")
    metrics: dict[str, dict[str, Any]] = {}
    internals: dict[str, dict[str, Any]] = {}
    coverage_rows: list[dict[str, Any]] = []
    semantics = extension["metrics"]["primary_pair_semantics"]
    dev_primary_ids = sorted(
        pair_id for pair_id, row in dev_truth.items() if row["pair_semantics"] == semantics
    )
    for predictor in sorted(test_predictions):
        calibration = inverse_temperature(
            [float(dev_predictions[predictor][pair_id]["margin"]) for pair_id in dev_primary_ids],
            extension,
        )
        metric, internal, predictor_coverage = predictor_metrics(
            predictor,
            test_truth,
            test_predictions[predictor],
            calibration,
            extension,
            primary_contract,
        )
        metrics[predictor] = metric
        internals[predictor] = internal
        coverage_rows.extend(predictor_coverage)
    conclusion = decision(extension, primary_summary, metrics, internals, dev_truth, overlap)
    summary = {
        "protocol": ANALYSIS_PROTOCOL,
        "status": conclusion["status"],
        "input_identity": {
            "primary_contract_sha256": primary_contract_sha,
            "extension_contract_sha256": extension_sha,
            "primary_lock_sha256": primary_lock_sha,
            "calibration_lock_sha256": sha256_file(calibration_lock_path),
            "primary_bundle_sha256": sha256_file(primary_bundle_path),
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
    return summary, metrics, internals, coverage_rows


def main() -> None:
    args = arguments()
    summary, _, internals, coverage_rows = analyze(
        args.primary_contract,
        args.extension_contract,
        args.primary_lock,
        args.calibration_lock,
        args.primary_bundle,
    )
    write_outputs(args.out_dir, summary, internals, coverage_rows)
    print(json.dumps({"status": summary["status"], "summary": str(args.out_dir / "summary.json")}, sort_keys=True))


if __name__ == "__main__":
    main()
