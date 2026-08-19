#!/usr/bin/env python3
"""Independent verifier for deployment_cost_attestation_v1 artifacts.

The verifier deliberately does not import the producer.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import math
import subprocess
from pathlib import Path
from typing import Any, Sequence


PROTOCOL = "deployment_cost_attestation_v1"
MODELS = ("static_lr", "static_gbm", "tfidf_lr")


class VerificationError(RuntimeError):
    pass


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def normalized_lf_sha256(path: Path) -> str:
    raw = path.read_bytes()
    raw.decode("utf-8")
    return hashlib.sha256(raw.replace(b"\r\n", b"\n").replace(b"\r", b"\n")).hexdigest()


def quantile(values: Sequence[float], probability: float) -> float:
    if not values:
        raise VerificationError("empty measurement")
    ordered = sorted(float(value) for value in values)
    if any(not math.isfinite(value) or value < 0 for value in ordered):
        raise VerificationError("invalid measurement")
    position = (len(ordered) - 1) * probability
    lower, upper = math.floor(position), math.ceil(position)
    if lower == upper:
        return ordered[lower]
    weight = position - lower
    return ordered[lower] * (1.0 - weight) + ordered[upper] * weight


def distribution(values: Sequence[float]) -> dict[str, float | int]:
    return {
        "n": len(values),
        "p25": quantile(values, 0.25),
        "p50": quantile(values, 0.50),
        "p75": quantile(values, 0.75),
        "p95": quantile(values, 0.95),
        "min": min(values),
        "max": max(values),
    }


def load_csv(path: Path) -> list[dict[str, str]]:
    with path.open(encoding="utf-8", newline="") as handle:
        return list(csv.DictReader(handle))


def load_jsonl(path: Path) -> list[dict[str, Any]]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line]


def atomic_json(path: Path, payload: Any) -> None:
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(
        json.dumps(payload, indent=2, sort_keys=True, ensure_ascii=False, allow_nan=False) + "\n",
        encoding="utf-8",
        newline="\n",
    )
    temporary.replace(path)


def compare(expected: Any, actual: Any, label: str = "root") -> None:
    if isinstance(expected, dict) and isinstance(actual, dict):
        if set(expected) != set(actual):
            raise VerificationError(f"{label} keys differ")
        for key in expected:
            compare(expected[key], actual[key], f"{label}.{key}")
        return
    if isinstance(expected, list) and isinstance(actual, list):
        if len(expected) != len(actual):
            raise VerificationError(f"{label} lengths differ")
        for index, (left, right) in enumerate(zip(expected, actual)):
            compare(left, right, f"{label}[{index}]")
        return
    if isinstance(expected, (int, float)) and isinstance(actual, (int, float)):
        if not math.isclose(float(expected), float(actual), rel_tol=1e-12, abs_tol=1e-12):
            raise VerificationError(f"{label} differs: {expected} != {actual}")
        return
    if expected != actual:
        raise VerificationError(f"{label} differs: {expected!r} != {actual!r}")


def runtime_summary(rows: Sequence[dict[str, str]]) -> dict[str, Any]:
    identifiers: set[str] = set()
    endpoint_runtime: dict[str, float] = {}
    serial: list[float] = []
    parallel: list[float] = []
    seen_pairs: set[tuple[str, str]] = set()
    for expected_index, row in enumerate(rows):
        if int(row["pair_index"]) != expected_index:
            raise VerificationError("runtime pair indices are not contiguous")
        left, right = row["left_id"], row["right_id"]
        if not left < right:
            raise VerificationError("query pair manifest is not canonical")
        pair = (left, right)
        if pair in seen_pairs:
            raise VerificationError("duplicate runtime pair")
        seen_pairs.add(pair)
        identifiers.update(pair)
        complete = int(row["complete"]) == 1
        left_value = float(row["left_runtime_s"]) if row["left_runtime_s"] else None
        right_value = float(row["right_runtime_s"]) if row["right_runtime_s"] else None
        for identifier, value in ((left, left_value), (right, right_value)):
            if value is not None:
                if identifier in endpoint_runtime and endpoint_runtime[identifier] != value:
                    raise VerificationError("endpoint runtime changed across pair rows")
                endpoint_runtime[identifier] = value
        if complete:
            if left_value is None or right_value is None:
                raise VerificationError("complete runtime row has a missing endpoint")
            serial_value = float(row["serial_runtime_s"])
            parallel_value = float(row["ideal_parallel_runtime_s"])
            if not math.isclose(serial_value, left_value + right_value, rel_tol=0, abs_tol=1e-12):
                raise VerificationError("serial runtime formula mismatch")
            if not math.isclose(parallel_value, max(left_value, right_value), rel_tol=0, abs_tol=1e-12):
                raise VerificationError("parallel runtime formula mismatch")
            serial.append(serial_value)
            parallel.append(parallel_value)
        elif row["serial_runtime_s"] or row["ideal_parallel_runtime_s"]:
            raise VerificationError("incomplete runtime row has aggregate values")
    finite_endpoints = list(endpoint_runtime.values())
    return {
        "unique_endpoints": len(identifiers),
        "finite_unique_endpoints": len(finite_endpoints),
        "endpoint_coverage": len(finite_endpoints) / len(identifiers),
        "pairs": len(rows),
        "complete_pairs": len(parallel),
        "pair_coverage": len(parallel) / len(rows),
        "unique_endpoint_runtime_s": distribution(finite_endpoints),
        "pair_serial_runtime_s": distribution(serial),
        "pair_ideal_parallel_runtime_s": distribution(parallel),
    }


def reconstruct_summary(
    config: dict[str, Any],
    measurements: Sequence[dict[str, str]],
    receipts: Sequence[dict[str, Any]],
    runtime: dict[str, Any],
) -> dict[str, Any]:
    models: dict[str, Any] = {}
    for model in MODELS:
        rows = [row for row in measurements if row["model"] == model]
        init_values = [float(row["elapsed_s"]) for row in rows if row["phase"] == "init"]
        batch_values = [float(row["per_pair_ms"]) for row in rows if row["phase"] == "batch_query"]
        single_values = [float(row["per_pair_ms"]) for row in rows if row["phase"] == "single_query"]
        model_receipts = [row for row in receipts if row["model"] == model]
        expected = config["init_trials"]
        if len(init_values) != expected:
            raise VerificationError(f"{model} init row count mismatch")
        if len(batch_values) != expected * config["query_repeats"]:
            raise VerificationError(f"{model} batch row count mismatch")
        if len(single_values) != expected * config["single_pair_sample"]:
            raise VerificationError(f"{model} single row count mismatch")
        if len(model_receipts) != expected:
            raise VerificationError(f"{model} receipt count mismatch")
        trial_single_p50 = []
        for trial in range(expected):
            trial_rows = [
                row for row in rows if row["phase"] == "single_query" and int(row["trial"]) == trial
            ]
            trial_single_p50.append(quantile([float(row["per_pair_ms"]) for row in trial_rows], 0.5))
            batch_digests = {
                row["decision_sha256"]
                for row in rows
                if row["phase"] == "batch_query" and int(row["trial"]) == trial
            }
            receipt = next(row for row in model_receipts if int(row["trial"]) == trial)
            if batch_digests != {receipt["full_decision_sha256"]}:
                raise VerificationError(f"{model} trial {trial} decision digest mismatch")
        query_stability = max(trial_single_p50) / max(min(trial_single_p50), 1e-15)
        init_stability = max(init_values) / max(min(init_values), 1e-15)
        full_digests = sorted({str(row["full_decision_sha256"]) for row in model_receipts})
        warning_count = sum(len(row["fit_warnings"]) for row in model_receipts)
        init_stats = distribution(init_values)
        batch_stats = distribution(batch_values)
        single_stats = distribution(single_values)
        parallel_p50 = runtime["pair_ideal_parallel_runtime_s"]["p50"]
        serial_p50 = runtime["pair_serial_runtime_s"]["p50"]
        single_p50_s = single_stats["p50"] / 1000.0
        single_p95_s = single_stats["p95"] / 1000.0
        denominator = max(parallel_p50 - single_p50_s, 1e-15)
        models[model] = {
            "initialization_s": init_stats,
            "batch_query_per_pair_ms": batch_stats,
            "single_pair_query_ms": single_stats,
            "trial_single_query_p50_ms": trial_single_p50,
            "query_trial_max_min_ratio": query_stability,
            "init_trial_max_min_ratio": init_stability,
            "full_decision_sha256_values": full_digests,
            "fit_warning_count": warning_count,
            "tie_counts": sorted({int(row["tie_count"]) for row in model_receipts}),
            "antisymmetry_min": min(float(row["antisymmetry_fraction"]) for row in model_receipts),
            "execution_parallel_p50_over_query_p50": parallel_p50 / single_p50_s,
            "execution_serial_p50_over_query_p50": serial_p50 / single_p50_s,
            "query_p95_fraction_of_execution_parallel_p50": single_p95_s / parallel_p50,
            "initialization_break_even_parallel_pairs": math.ceil(init_stats["p50"] / denominator),
        }
    integrity = {
        "all_models_complete": len(receipts) == len(MODELS) * config["init_trials"],
        "runtime_pair_coverage_at_least_0_95": runtime["pair_coverage"] >= 0.95,
        "all_decision_digests_stable": all(
            len(models[model]["full_decision_sha256_values"]) == 1 for model in MODELS
        ),
        "all_antisymmetry_exact": all(models[model]["antisymmetry_min"] == 1.0 for model in MODELS),
        "no_fit_warnings": all(models[model]["fit_warning_count"] == 0 for model in MODELS),
        "within_run_query_stability_at_most_2": all(
            models[model]["query_trial_max_min_ratio"] <= 2.0 for model in MODELS
        ),
        "within_run_init_stability_at_most_3": all(
            models[model]["init_trial_max_min_ratio"] <= 3.0 for model in MODELS
        ),
    }
    positive = {
        "all_query_p95_below_1pct_parallel_execution_p50": all(
            models[model]["query_p95_fraction_of_execution_parallel_p50"] <= 0.01 for model in MODELS
        ),
        "all_init_p50_below_10_parallel_execution_p50": all(
            models[model]["initialization_s"]["p50"] <= 10.0 * runtime["pair_ideal_parallel_runtime_s"]["p50"]
            for model in MODELS
        ),
    }
    integrity_pass = all(integrity.values())
    positive_pass = integrity_pass and all(positive.values())
    return {
        "protocol": PROTOCOL,
        "status": (
            "DEPLOYMENT_COST_ADVANTAGE_SUPPORTED"
            if positive_pass
            else "VERIFIED_DEPLOYMENT_COST_ATTESTATION"
            if integrity_pass
            else "FAILED_DEPLOYMENT_COST_INTEGRITY"
        ),
        "scope": {
            "accuracy_computed": False,
            "query_manifest_orientation_free": True,
            "prospective_vault_opened": False,
            "gpu_used": False,
            "api_used": False,
        },
        "runtime_reference": runtime,
        "models": models,
        "integrity_checks": integrity,
        "positive_checks": positive,
    }


def git_head(source_root: Path) -> str:
    result = subprocess.run(
        ["git", "-C", str(source_root), "rev-parse", "HEAD"],
        check=True,
        capture_output=True,
        text=True,
    )
    return result.stdout.strip()


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--result-dir", required=True)
    parser.add_argument("--source-root", required=True)
    parser.add_argument("--out", required=True)
    arguments = parser.parse_args()
    result_dir = Path(arguments.result_dir).resolve()
    source_root = Path(arguments.source_root).resolve()
    output = Path(arguments.out).resolve()
    if output.exists():
        raise VerificationError(f"verification output already exists: {output}")
    config = json.loads((result_dir / "config.json").read_text(encoding="utf-8"))
    published = json.loads((result_dir / "summary.json").read_text(encoding="utf-8"))
    measurements = load_csv(result_dir / "measurements.csv")
    receipts = load_jsonl(result_dir / "trial_receipts.jsonl")
    runtime_rows = load_csv(result_dir / "execution_reference.csv")
    if config["protocol"] != PROTOCOL or published["protocol"] != PROTOCOL:
        raise VerificationError("protocol mismatch")
    if git_head(source_root) != config["expected_git_commit"]:
        raise VerificationError("source-root commit mismatch")
    source_script = source_root / "phase1" / "deployment_cost_attestation.py"
    if sha256(source_script) != config["source_script_sha256"]:
        raise VerificationError("producer script hash mismatch")
    input_checks: dict[str, Any] = {}
    for name, item in config["input_manifest"].items():
        path = Path(item["path"])
        actual_raw = sha256(path)
        actual_normalized = normalized_lf_sha256(path)
        passed = (
            actual_raw == item["sha256"]
            and actual_normalized == item["sha256_normalized_lf"]
            and actual_normalized == item["expected_sha256_normalized_lf"]
        )
        input_checks[name] = {
            "sha256": actual_raw,
            "sha256_normalized_lf": actual_normalized,
            "passed": passed,
        }
        if not passed:
            raise VerificationError(f"input hash mismatch: {name}")
    runtime = runtime_summary(runtime_rows)
    published_runtime = json.loads(
        (result_dir / "runtime_reference_summary.json").read_text(encoding="utf-8")
    )
    compare(runtime, published_runtime, "runtime_reference_summary")
    reconstructed = reconstruct_summary(config, measurements, receipts, runtime)
    compare(reconstructed, published, "summary")
    receipt = {
        "protocol": PROTOCOL,
        "status": "INDEPENDENTLY_VERIFIED_DEPLOYMENT_COST_ATTESTATION",
        "result_status": published["status"],
        "run_label": config["run_label"],
        "source_commit": config["expected_git_commit"],
        "input_checks": input_checks,
        "measurement_rows": len(measurements),
        "trial_receipts": len(receipts),
        "runtime_rows": len(runtime_rows),
        "summary_sha256": sha256(result_dir / "summary.json"),
        "measurements_sha256": sha256(result_dir / "measurements.csv"),
        "trial_receipts_sha256": sha256(result_dir / "trial_receipts.jsonl"),
        "execution_reference_sha256": sha256(result_dir / "execution_reference.csv"),
        "producer_imported": False,
    }
    atomic_json(output, receipt)
    print(receipt["status"])


if __name__ == "__main__":
    main()
