"""Fail-closed analysis for a future clean critic-scaling confirmation bundle.

The result-bearing files are intentionally separate from the pre-test lock.  The
lock fixes the cohort, checkpoints, matrix, and baseline before any test scoring;
the bundle then binds one-shot ledgers and prediction files to that lock.  This
module never trains or scores a model.
"""

from __future__ import annotations

import argparse
import collections
import csv
import hashlib
import json
import math
import random
import re
import statistics
import zlib
from pathlib import Path
from typing import Any, Iterable, Mapping, Sequence


CONTRACT_PROTOCOL = "critic-scaling-confirmation-contract-v1"
LOCK_PROTOCOL = "critic-scaling-confirmation-lock-v1"
BUNDLE_PROTOCOL = "critic-scaling-confirmation-bundle-v1"
ANALYSIS_PROTOCOL = "critic-scaling-confirmation-analysis-v1"
HEX64 = re.compile(r"[0-9a-f]{64}")
HEX40_OR_64 = re.compile(r"(?:[0-9a-f]{40}|[0-9a-f]{64})")


class ConfirmationError(RuntimeError):
    """Raised whenever a frozen identity or analysis invariant fails."""


def arguments() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--contract", type=Path, required=True)
    parser.add_argument("--lock", type=Path, required=True)
    parser.add_argument("--bundle", type=Path, required=True)
    parser.add_argument("--out-dir", type=Path, required=True)
    return parser.parse_args()


def canonical_bytes(value: Any) -> bytes:
    return (json.dumps(value, indent=2, sort_keys=True, ensure_ascii=False) + "\n").encode()


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()


def require_hex(value: Any, label: str, *, allow_git40: bool = False) -> str:
    pattern = HEX40_OR_64 if allow_git40 else HEX64
    if not isinstance(value, str) or pattern.fullmatch(value) is None:
        raise ConfirmationError(f"{label} is not a lowercase digest")
    return value


def read_object(path: Path, label: str) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as error:
        raise ConfirmationError(f"cannot read {label}") from error
    if not isinstance(value, dict):
        raise ConfirmationError(f"{label} root must be an object")
    return value


def read_jsonl(path: Path, label: str) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    try:
        with path.open(encoding="utf-8") as handle:
            for line_number, line in enumerate(handle, 1):
                if not line.strip():
                    raise ConfirmationError(f"blank row in {label}:{line_number}")
                row = json.loads(line)
                if not isinstance(row, dict):
                    raise ConfirmationError(f"non-object row in {label}:{line_number}")
                rows.append(row)
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as error:
        if isinstance(error, ConfirmationError):
            raise
        raise ConfirmationError(f"cannot read {label}") from error
    if not rows:
        raise ConfirmationError(f"{label} is empty")
    return rows


def safe_relative_file(root: Path, relative: Any, label: str) -> Path:
    if not isinstance(relative, str) or not relative or Path(relative).is_absolute():
        raise ConfirmationError(f"{label} path must be non-empty and relative")
    root_resolved = root.resolve()
    candidate = root / relative
    cursor = root
    for part in Path(relative).parts:
        cursor = cursor / part
        if cursor.is_symlink():
            raise ConfirmationError(f"{label} contains a symlink")
    path = candidate.resolve()
    try:
        path.relative_to(root_resolved)
    except ValueError as error:
        raise ConfirmationError(f"{label} escapes bundle root") from error
    if not path.is_file():
        raise ConfirmationError(f"{label} is absent")
    return path


def checked_artifact(root: Path, spec: Any, label: str) -> tuple[Path, str, int]:
    if not isinstance(spec, dict):
        raise ConfirmationError(f"{label} spec must be an object")
    path = safe_relative_file(root, spec.get("path"), label)
    expected_hash = require_hex(spec.get("sha256"), f"{label} SHA256")
    expected_rows = spec.get("rows")
    if not isinstance(expected_rows, int) or expected_rows <= 0:
        raise ConfirmationError(f"{label} row count must be positive")
    if sha256_file(path) != expected_hash:
        raise ConfirmationError(f"{label} SHA256 mismatch")
    return path, expected_hash, expected_rows


def finite_number(value: Any, label: str) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ConfirmationError(f"{label} must be numeric")
    result = float(value)
    if not math.isfinite(result):
        raise ConfirmationError(f"{label} is non-finite")
    return result


def pair_id(row: Mapping[str, Any]) -> str:
    payload = [
        row["task"],
        row["pair_semantics"],
        row["parent_id"],
        row["comparison_component_id"],
        row["better_id"],
        row["worse_id"],
    ]
    encoded = json.dumps(payload, ensure_ascii=False, separators=(",", ":")).encode()
    return hashlib.sha256(encoded).hexdigest()


def require_nonempty_string(row: Mapping[str, Any], field: str, label: str) -> str:
    value = row.get(field)
    if not isinstance(value, str) or not value:
        raise ConfirmationError(f"{label} has invalid {field}")
    return value


def validate_truth(
    rows: Sequence[dict[str, Any]], contract: Mapping[str, Any]
) -> tuple[dict[str, dict[str, Any]], dict[str, dict[str, Any]]]:
    required = set(contract["prediction_schema"]["truth_required_fields"])
    primary_semantics = contract["cohort"]["primary_pair_semantics"]
    truth: dict[str, dict[str, Any]] = {}
    reverse_keys: set[tuple[str, str, str, str, frozenset[str]]] = set()
    endpoint_utilities: dict[str, float] = {}
    components: dict[str, dict[str, Any]] = {}

    for index, source in enumerate(rows):
        if not required.issubset(source):
            raise ConfirmationError(f"truth row {index} lacks required fields")
        row = dict(source)
        for field in (
            "pair_id", "task", "pair_semantics", "parent_id", "parent_run_id",
            "comparison_component_id", "better_id", "worse_id", "better_run_id",
            "worse_run_id",
        ):
            require_nonempty_string(row, field, f"truth row {index}")
        if row.get("split") != "test":
            raise ConfirmationError(f"truth row {index} is not test")
        if row["better_id"] == row["worse_id"]:
            raise ConfirmationError(f"truth row {index} is a self pair")
        better_utility = finite_number(row["better_utility"], "better utility")
        worse_utility = finite_number(row["worse_utility"], "worse utility")
        if not better_utility > worse_utility:
            raise ConfirmationError(f"truth row {index} orientation is not strictly positive")
        row["better_utility"] = better_utility
        row["worse_utility"] = worse_utility
        expected_id = pair_id(row)
        if row["pair_id"] != expected_id or HEX64.fullmatch(row["pair_id"]) is None:
            raise ConfirmationError(f"truth row {index} pair_id mismatch")
        if row["pair_id"] in truth:
            raise ConfirmationError("duplicate pair_id in truth")
        reverse_key = (
            row["task"], row["pair_semantics"], row["parent_id"],
            row["comparison_component_id"], frozenset((row["better_id"], row["worse_id"])),
        )
        if reverse_key in reverse_keys:
            raise ConfirmationError("duplicate or reversed unordered pair in truth")
        reverse_keys.add(reverse_key)

        if row["pair_semantics"] == primary_semantics and not (
            row["parent_run_id"] == row["better_run_id"] == row["worse_run_id"]
        ):
            raise ConfirmationError("primary sibling pair crosses physical runs")
        for endpoint, utility in (
            (row["better_id"], better_utility), (row["worse_id"], worse_utility)
        ):
            previous = endpoint_utilities.setdefault(endpoint, utility)
            tolerance = contract["prediction_schema"]["endpoint_utility_consistency_tolerance"]
            if not math.isclose(previous, utility, rel_tol=0.0, abs_tol=tolerance):
                raise ConfirmationError("endpoint utility is inconsistent across truth rows")

        component_id = row["comparison_component_id"]
        meta = components.setdefault(
            component_id,
            {
                "task": row["task"],
                "pair_semantics": row["pair_semantics"],
                "parent_id": row["parent_id"],
                "parent_run_id": row["parent_run_id"],
                "edges": [],
            },
        )
        expected_meta = (
            meta["task"], meta["pair_semantics"], meta["parent_id"], meta["parent_run_id"]
        )
        observed_meta = (
            row["task"], row["pair_semantics"], row["parent_id"], row["parent_run_id"]
        )
        if expected_meta != observed_meta:
            raise ConfirmationError("comparison component mixes metadata")
        meta["edges"].append((row["better_id"], row["worse_id"]))
        truth[row["pair_id"]] = row

    for component_id in sorted(components):
        edges = components[component_id]["edges"]
        adjacency: dict[str, set[str]] = collections.defaultdict(set)
        for left, right in edges:
            adjacency[left].add(right)
            adjacency[right].add(left)
        start = min(adjacency)
        reached = {start}
        stack = [start]
        while stack:
            node = stack.pop()
            for neighbour in sorted(adjacency[node]):
                if neighbour not in reached:
                    reached.add(neighbour)
                    stack.append(neighbour)
        if reached != set(adjacency):
            raise ConfirmationError(f"comparison component {component_id} is disconnected")
        components[component_id]["endpoints"] = sorted(adjacency)
    return truth, components


def validate_predictions(
    rows: Sequence[dict[str, Any]],
    truth: Mapping[str, dict[str, Any]],
    contract: Mapping[str, Any],
    label: str,
) -> dict[str, dict[str, float | str]]:
    required = set(contract["prediction_schema"]["prediction_required_fields"])
    output: dict[str, dict[str, float | str]] = {}
    endpoint_scores: dict[str, float] = {}
    margin_tolerance = float(contract["prediction_schema"]["margin_tolerance"])
    score_tolerance = float(
        contract["prediction_schema"]["endpoint_score_consistency_tolerance"]
    )
    for index, source in enumerate(rows):
        if not required.issubset(source):
            raise ConfirmationError(f"{label} row {index} lacks required fields")
        current_pair_id = source.get("pair_id")
        if not isinstance(current_pair_id, str) or current_pair_id not in truth:
            raise ConfirmationError(f"{label} row {index} has unknown pair_id")
        if current_pair_id in output:
            raise ConfirmationError(f"{label} has duplicate pair_id")
        better_score = finite_number(source["better_score"], f"{label} better_score")
        worse_score = finite_number(source["worse_score"], f"{label} worse_score")
        margin = finite_number(source["margin"], f"{label} margin")
        if not math.isclose(
            margin, better_score - worse_score, rel_tol=0.0, abs_tol=margin_tolerance
        ):
            raise ConfirmationError(f"{label} margin disagrees with endpoint scores")
        truth_row = truth[current_pair_id]
        for endpoint, score in (
            (truth_row["better_id"], better_score),
            (truth_row["worse_id"], worse_score),
        ):
            previous = endpoint_scores.setdefault(endpoint, score)
            if not math.isclose(previous, score, rel_tol=0.0, abs_tol=score_tolerance):
                raise ConfirmationError(f"{label} endpoint score is inconsistent")
        output[current_pair_id] = {
            "pair_id": current_pair_id,
            "better_score": better_score,
            "worse_score": worse_score,
            "margin": margin,
        }
    if set(output) != set(truth):
        raise ConfirmationError(f"{label} prediction coverage differs from truth")
    return output


def tie_credit(margin: float) -> float:
    if margin > 0.0:
        return 1.0
    if margin < 0.0:
        return 0.0
    return 0.5


def grouped_means(rows: Iterable[tuple[str, float]]) -> dict[str, float]:
    grouped: dict[str, list[float]] = collections.defaultdict(list)
    for key, value in rows:
        grouped[key].append(float(value))
    return {
        key: math.fsum(grouped[key]) / len(grouped[key])
        for key in sorted(grouped)
    }


def mean(values: Iterable[float]) -> float:
    materialized = [float(value) for value in values]
    if not materialized:
        raise ConfirmationError("cannot average an empty collection")
    return math.fsum(materialized) / len(materialized)


def bootstrap_ci(
    cluster_values: Mapping[str, float], *, draws: int, seed: int
) -> list[float]:
    keys = sorted(cluster_values)
    if len(keys) < 2:
        raise ConfirmationError("cluster bootstrap needs at least two clusters")
    rng = random.Random(seed)
    samples: list[float] = []
    for _ in range(draws):
        selected = [rng.choice(keys) for _ in keys]
        samples.append(mean(cluster_values[key] for key in selected))
    samples.sort()
    lower = samples[int(0.025 * (draws - 1))]
    upper = samples[int(0.975 * (draws - 1))]
    return [lower, upper]


def deterministic_seed(base: int, label: str) -> int:
    return int(base) + int(zlib.crc32(label.encode()) & 0x7FFFFFFF)


def component_records(
    truth_rows: Sequence[dict[str, Any]],
    predictions: Mapping[str, Mapping[str, float | str]],
) -> list[dict[str, Any]]:
    grouped: dict[str, list[dict[str, Any]]] = collections.defaultdict(list)
    for row in truth_rows:
        grouped[row["comparison_component_id"]].append(row)
    records: list[dict[str, Any]] = []
    for component_id in sorted(grouped):
        rows = grouped[component_id]
        score_by_endpoint: dict[str, float] = {}
        utility_by_endpoint: dict[str, float] = {}
        for row in rows:
            prediction = predictions[row["pair_id"]]
            score_by_endpoint[row["better_id"]] = float(prediction["better_score"])
            score_by_endpoint[row["worse_id"]] = float(prediction["worse_score"])
            utility_by_endpoint[row["better_id"]] = float(row["better_utility"])
            utility_by_endpoint[row["worse_id"]] = float(row["worse_utility"])
        maximum_score = max(score_by_endpoint.values())
        selected = sorted(
            endpoint for endpoint, score in score_by_endpoint.items() if score == maximum_score
        )
        oracle_utility = max(utility_by_endpoint.values())
        oracle_endpoints = {
            endpoint for endpoint, utility in utility_by_endpoint.items()
            if utility == oracle_utility
        }
        selected_utility = mean(utility_by_endpoint[endpoint] for endpoint in selected)
        uniform_utility = mean(utility_by_endpoint.values())
        headroom = oracle_utility - uniform_utility
        if not headroom > 0.0:
            raise ConfirmationError("component lacks strictly positive oracle headroom")
        top1 = len(set(selected) & oracle_endpoints) / len(selected)
        normalized_regret = (oracle_utility - selected_utility) / headroom
        records.append(
            {
                "component_id": component_id,
                "task": rows[0]["task"],
                "pair_semantics": rows[0]["pair_semantics"],
                "parent_id": rows[0]["parent_id"],
                "parent_run_id": rows[0]["parent_run_id"],
                "endpoints": len(score_by_endpoint),
                "selected_ties": len(selected),
                "top1": top1,
                "raw_regret": oracle_utility - selected_utility,
                "normalized_regret": normalized_regret,
                "gain_capture": 1.0 - normalized_regret,
            }
        )
    return records


def predictor_metrics(
    predictor_id: str,
    truth: Mapping[str, dict[str, Any]],
    predictions: Mapping[str, Mapping[str, float | str]],
    contract: Mapping[str, Any],
) -> tuple[dict[str, Any], list[dict[str, Any]], dict[str, dict[str, Any]]]:
    primary_semantics = contract["cohort"]["primary_pair_semantics"]
    primary = [truth[pair] for pair in sorted(truth) if truth[pair]["pair_semantics"] == primary_semantics]
    if not primary:
        raise ConfirmationError("primary semantics has no rows")
    credits = {
        row["pair_id"]: tie_credit(float(predictions[row["pair_id"]]["margin"]))
        for row in primary
    }
    per_task = grouped_means((row["task"], credits[row["pair_id"]]) for row in primary)
    per_run = grouped_means((row["parent_run_id"], credits[row["pair_id"]]) for row in primary)
    draws = int(contract["inference"]["bootstrap_draws"])
    seed = int(contract["inference"]["bootstrap_seed"])
    components = component_records(primary, predictions)
    component_task_gain = grouped_means((row["task"], row["gain_capture"]) for row in components)
    component_task_top1 = grouped_means((row["task"], row["top1"]) for row in components)
    semantics: dict[str, dict[str, Any]] = {}
    by_semantics: dict[str, list[dict[str, Any]]] = collections.defaultdict(list)
    for row in truth.values():
        by_semantics[row["pair_semantics"]].append(row)
    for name in sorted(by_semantics):
        rows = by_semantics[name]
        task_values = grouped_means(
            (row["task"], tie_credit(float(predictions[row["pair_id"]]["margin"])))
            for row in rows
        )
        semantics[name] = {
            "pairs": len(rows),
            "tasks": len(task_values),
            "micro_accuracy": mean(
                tie_credit(float(predictions[row["pair_id"]]["margin"])) for row in rows
            ),
            "task_macro_accuracy": mean(task_values.values()),
        }
    result = {
        "predictor_id": predictor_id,
        "primary_pairs": len(primary),
        "primary_tasks": len(per_task),
        "primary_runs": len(per_run),
        "primary_components": len(components),
        "micro_accuracy": mean(credits.values()),
        "task_macro_accuracy": mean(per_task.values()),
        "task_bootstrap_ci": bootstrap_ci(
            per_task, draws=draws, seed=deterministic_seed(seed, predictor_id + ":task")
        ),
        "run_macro_accuracy": mean(per_run.values()),
        "run_bootstrap_ci": bootstrap_ci(
            per_run, draws=draws, seed=deterministic_seed(seed, predictor_id + ":run")
        ),
        "component_task_macro_top1": mean(component_task_top1.values()),
        "component_task_macro_gain_capture": mean(component_task_gain.values()),
        "component_gain_task_bootstrap_ci": bootstrap_ci(
            component_task_gain,
            draws=draws,
            seed=deterministic_seed(seed, predictor_id + ":component-gain"),
        ),
        "semantics": semantics,
    }
    internals = {
        "per_task": {task: {"accuracy": value} for task, value in per_task.items()},
        "component_task_gain": component_task_gain,
        "component_task_top1": component_task_top1,
    }
    return result, components, internals


def model_key(size_b: float, seed: int) -> str:
    return f"qwen3_{size_b:g}b_seed{seed}"


def expected_matrix(contract: Mapping[str, Any]) -> list[tuple[float, int]]:
    return [
        (float(size), int(seed))
        for size in contract["matrix"]["model_sizes_b"]
        for seed in contract["matrix"]["seeds"]
    ]


def validate_contract(contract: Mapping[str, Any]) -> None:
    if contract.get("protocol") != CONTRACT_PROTOCOL:
        raise ConfirmationError("wrong contract protocol")
    if contract.get("status") != "CONTRACT_READY_ASSETS_PENDING":
        raise ConfirmationError("contract status changed")
    sizes = [float(value) for value in contract["matrix"]["model_sizes_b"]]
    seeds = [int(value) for value in contract["matrix"]["seeds"]]
    if sizes != [0.6, 1.7, 4.0, 8.0] or seeds != [6, 7]:
        raise ConfirmationError("contract matrix differs from frozen v1")
    if contract["access_and_compute"] != {
        "gpu_jobs_authorized": 0,
        "api_calls_authorized": 0,
        "model_fits_authorized": 0,
        "base_llm_updates_authorized": 0,
        "future_truth_reads_authorized": False,
        "long_experiment_requires_new_budget_approval": True,
    }:
        raise ConfirmationError("contract accidentally authorizes compute or truth access")


def validate_lock(
    lock: Mapping[str, Any], contract: Mapping[str, Any], contract_sha: str
) -> dict[tuple[float, int], dict[str, Any]]:
    if lock.get("protocol") != LOCK_PROTOCOL or lock.get("status") != "LOCKED_BEFORE_TEST_ACCESS":
        raise ConfirmationError("invalid pre-test lock status")
    if lock.get("contract_sha256") != contract_sha:
        raise ConfirmationError("lock references a different contract")
    require_hex(lock.get("source_commit"), "lock source commit", allow_git40=True)
    frozen_at = lock.get("frozen_at_utc")
    if not isinstance(frozen_at, str) or not frozen_at.endswith("Z"):
        raise ConfirmationError("lock lacks a UTC freeze timestamp")
    dataset = lock.get("dataset")
    if not isinstance(dataset, dict):
        raise ConfirmationError("lock dataset is absent")
    require_hex(dataset.get("truth_sha256"), "locked truth SHA256")
    if not isinstance(dataset.get("truth_rows"), int) or dataset["truth_rows"] <= 0:
        raise ConfirmationError("locked truth row count is invalid")
    if dataset.get("split") != "test":
        raise ConfirmationError("locked cohort is not test")
    baseline = lock.get("baseline")
    if not isinstance(baseline, dict) or baseline.get("id") != contract["baseline"]["id"]:
        raise ConfirmationError("locked baseline identity differs")
    if baseline.get("fit_scope") != "train_only":
        raise ConfirmationError("baseline was not fit train-only")
    require_hex(baseline.get("receipt_sha256"), "baseline receipt SHA256")
    runs = lock.get("runs")
    if not isinstance(runs, list):
        raise ConfirmationError("lock runs must be a list")
    indexed: dict[tuple[float, int], dict[str, Any]] = {}
    for row in runs:
        if not isinstance(row, dict):
            raise ConfirmationError("lock run is not an object")
        size_seed = (finite_number(row.get("model_size_b"), "model size"), row.get("seed"))
        if not isinstance(size_seed[1], int):
            raise ConfirmationError("model seed must be an integer")
        key = (size_seed[0], int(size_seed[1]))
        if key in indexed:
            raise ConfirmationError("duplicate model run in lock")
        if not isinstance(row.get("base_model"), str) or not row["base_model"]:
            raise ConfirmationError("model run lacks base_model")
        require_hex(row.get("model_revision"), "model revision", allow_git40=True)
        require_hex(row.get("checkpoint_manifest_sha256"), "checkpoint manifest SHA256")
        if row.get("checkpoint_locked_before_test_access") is not True:
            raise ConfirmationError("checkpoint was not locked before test access")
        if row.get("training_status") != "COMPLETE":
            raise ConfirmationError("model training did not complete")
        if row.get("selected_on_dev_only") is not True:
            raise ConfirmationError("checkpoint was not selected on dev only")
        if not isinstance(row.get("checkpoint_step"), int) or row["checkpoint_step"] <= 0:
            raise ConfirmationError("checkpoint step is invalid")
        finite_number(row.get("dev_selection_metric"), "dev selection metric")
        indexed[key] = row
    if sorted(indexed) != sorted(expected_matrix(contract)):
        raise ConfirmationError("lock model matrix is missing or has extras")
    return indexed


def validate_ledger(
    root: Path,
    spec: Any,
    *,
    label: str,
    lock_sha: str,
    truth_sha: str,
    prediction_sha: str,
    checkpoint_sha: str | None,
) -> str:
    if not isinstance(spec, dict):
        raise ConfirmationError(f"{label} ledger spec is absent")
    path = safe_relative_file(root, spec.get("path"), f"{label} ledger")
    digest = require_hex(spec.get("sha256"), f"{label} ledger SHA256")
    if sha256_file(path) != digest:
        raise ConfirmationError(f"{label} ledger SHA256 mismatch")
    ledger = read_object(path, f"{label} ledger")
    expected = {
        "status": "COMPLETE",
        "test_attempts": 1,
        "lock_sha256": lock_sha,
        "truth_sha256": truth_sha,
        "prediction_sha256": prediction_sha,
    }
    for key, value in expected.items():
        if ledger.get(key) != value:
            raise ConfirmationError(f"{label} ledger disagrees on {key}")
    if checkpoint_sha is not None and ledger.get("checkpoint_manifest_sha256") != checkpoint_sha:
        raise ConfirmationError(f"{label} ledger checkpoint mismatch")
    return digest


def validate_bundle(
    bundle_path: Path,
    bundle: Mapping[str, Any],
    lock: Mapping[str, Any],
    lock_sha: str,
    locked_runs: Mapping[tuple[float, int], dict[str, Any]],
    contract: Mapping[str, Any],
) -> tuple[
    dict[str, dict[str, Any]],
    dict[str, dict[str, dict[str, float | str]]],
    dict[str, dict[str, Any]],
]:
    if bundle.get("protocol") != BUNDLE_PROTOCOL or bundle.get("status") != "COMPLETE":
        raise ConfirmationError("invalid result bundle status")
    if bundle.get("lock_sha256") != lock_sha:
        raise ConfirmationError("bundle references a different pre-test lock")
    root = bundle_path.parent
    truth_path, truth_sha, truth_rows_expected = checked_artifact(root, bundle.get("truth"), "truth")
    if truth_sha != lock["dataset"]["truth_sha256"] or truth_rows_expected != lock["dataset"]["truth_rows"]:
        raise ConfirmationError("bundle truth differs from pre-test lock")
    truth_rows = read_jsonl(truth_path, "truth")
    if len(truth_rows) != truth_rows_expected:
        raise ConfirmationError("truth row count mismatch")
    truth, _ = validate_truth(truth_rows, contract)

    predictions: dict[str, dict[str, dict[str, float | str]]] = {}
    artifact_receipts: dict[str, dict[str, Any]] = {
        "truth": {"path": bundle["truth"]["path"], "sha256": truth_sha, "rows": len(truth)}
    }
    baseline_spec = bundle.get("baseline")
    if not isinstance(baseline_spec, dict) or baseline_spec.get("id") != contract["baseline"]["id"]:
        raise ConfirmationError("bundle baseline identity differs")
    if baseline_spec.get("receipt_sha256") != lock["baseline"]["receipt_sha256"]:
        raise ConfirmationError("bundle baseline training receipt differs")
    baseline_path, baseline_sha, baseline_rows = checked_artifact(
        root, baseline_spec.get("predictions"), "baseline predictions"
    )
    if baseline_rows != len(truth):
        raise ConfirmationError("baseline prediction row count differs")
    baseline_values = validate_predictions(
        read_jsonl(baseline_path, "baseline predictions"), truth, contract, "baseline"
    )
    baseline_ledger_sha = validate_ledger(
        root,
        baseline_spec.get("ledger"),
        label="baseline",
        lock_sha=lock_sha,
        truth_sha=truth_sha,
        prediction_sha=baseline_sha,
        checkpoint_sha=None,
    )
    predictions[contract["baseline"]["id"]] = baseline_values
    artifact_receipts[contract["baseline"]["id"]] = {
        "path": baseline_spec["predictions"]["path"], "sha256": baseline_sha, "rows": baseline_rows,
        "ledger_sha256": baseline_ledger_sha,
    }

    run_specs = bundle.get("runs")
    if not isinstance(run_specs, list):
        raise ConfirmationError("bundle runs must be a list")
    seen: set[tuple[float, int]] = set()
    for row in run_specs:
        if not isinstance(row, dict):
            raise ConfirmationError("bundle run is not an object")
        size = finite_number(row.get("model_size_b"), "bundle model size")
        seed = row.get("seed")
        if not isinstance(seed, int):
            raise ConfirmationError("bundle model seed must be integer")
        key = (size, seed)
        if key in seen or key not in locked_runs:
            raise ConfirmationError("bundle model run is duplicate or not locked")
        seen.add(key)
        locked = locked_runs[key]
        checkpoint_sha = locked["checkpoint_manifest_sha256"]
        if row.get("checkpoint_manifest_sha256") != checkpoint_sha:
            raise ConfirmationError("bundle checkpoint differs from lock")
        predictor_id = model_key(size, seed)
        prediction_path, prediction_sha, prediction_rows = checked_artifact(
            root, row.get("predictions"), f"{predictor_id} predictions"
        )
        if prediction_rows != len(truth):
            raise ConfirmationError(f"{predictor_id} prediction row count differs")
        values = validate_predictions(
            read_jsonl(prediction_path, f"{predictor_id} predictions"),
            truth,
            contract,
            predictor_id,
        )
        ledger_sha = validate_ledger(
            root,
            row.get("ledger"),
            label=predictor_id,
            lock_sha=lock_sha,
            truth_sha=truth_sha,
            prediction_sha=prediction_sha,
            checkpoint_sha=checkpoint_sha,
        )
        predictions[predictor_id] = values
        artifact_receipts[predictor_id] = {
            "path": row["predictions"]["path"], "sha256": prediction_sha, "rows": prediction_rows,
            "ledger_sha256": ledger_sha, "checkpoint_manifest_sha256": checkpoint_sha,
        }
    if seen != set(locked_runs):
        raise ConfirmationError("bundle model matrix is incomplete")
    return truth, predictions, artifact_receipts


def comparison_summary(
    contract: Mapping[str, Any],
    metrics: Mapping[str, dict[str, Any]],
    internals: Mapping[str, dict[str, Any]],
    truth: Mapping[str, dict[str, Any]],
) -> dict[str, Any]:
    sizes = [float(value) for value in contract["matrix"]["model_sizes_b"]]
    seeds = [int(value) for value in contract["matrix"]["seeds"]]
    low = float(contract["matrix"]["reference_low_size_b"])
    high = float(contract["matrix"]["reference_high_size_b"])
    baseline_id = contract["baseline"]["id"]
    draws = int(contract["inference"]["bootstrap_draws"])
    bootstrap_seed = int(contract["inference"]["bootstrap_seed"])

    tasks = sorted(internals[baseline_id]["per_task"])
    size_task_values: dict[float, dict[str, float]] = {}
    for size in sizes:
        size_task_values[size] = {
            task: mean(
                internals[model_key(size, seed)]["per_task"][task]["accuracy"] for seed in seeds
            )
            for task in tasks
        }
    size_means = {str(size): mean(size_task_values[size].values()) for size in sizes}
    size_seed_task_macros = {
        str(size): {
            str(seed): metrics[model_key(size, seed)]["task_macro_accuracy"] for seed in seeds
        }
        for size in sizes
    }
    low_high_delta = {
        task: size_task_values[high][task] - size_task_values[low][task] for task in tasks
    }
    baseline_task = {
        task: internals[baseline_id]["per_task"][task]["accuracy"] for task in tasks
    }
    high_baseline_delta = {
        task: size_task_values[high][task] - baseline_task[task] for task in tasks
    }
    low_high_ci = bootstrap_ci(
        low_high_delta,
        draws=draws,
        seed=deterministic_seed(bootstrap_seed, "high-minus-low"),
    )
    high_baseline_ci = bootstrap_ci(
        high_baseline_delta,
        draws=draws,
        seed=deterministic_seed(bootstrap_seed, "high-minus-baseline"),
    )
    monotonic = all(
        size_means[str(left)] <= size_means[str(right)]
        for left, right in zip(sizes, sizes[1:])
    )
    endpoint_delta = mean(low_high_delta.values())
    endpoint_delta_by_seed = {
        str(seed): (
            metrics[model_key(high, seed)]["task_macro_accuracy"]
            - metrics[model_key(low, seed)]["task_macro_accuracy"]
        )
        for seed in seeds
    }
    high_seed_task_macros = {
        str(seed): metrics[model_key(high, seed)]["task_macro_accuracy"] for seed in seeds
    }
    baseline_task_macro = metrics[baseline_id]["task_macro_accuracy"]
    each_high_seed_beats = all(value > baseline_task_macro for value in high_seed_task_macros.values())
    loto = {
        task: mean(value for other, value in high_baseline_delta.items() if other != task)
        for task in tasks
    }

    baseline_component = internals[baseline_id]["component_task_gain"]
    high_component_delta = {
        task: mean(
            internals[model_key(high, seed)]["component_task_gain"][task] for seed in seeds
        ) - baseline_component[task]
        for task in sorted(baseline_component)
    }
    utility_ci = bootstrap_ci(
        high_component_delta,
        draws=draws,
        seed=deterministic_seed(bootstrap_seed, "high-minus-baseline-component-gain"),
    )

    primary_semantics = contract["cohort"]["primary_pair_semantics"]
    primary_rows = [row for row in truth.values() if row["pair_semantics"] == primary_semantics]
    task_counts = collections.Counter(row["task"] for row in primary_rows)
    component_count = len({row["comparison_component_id"] for row in primary_rows})
    dominant_share = max(task_counts.values()) / len(primary_rows)
    support_gates = {
        "tasks_at_least_20": len(task_counts) >= contract["cohort"]["minimum_primary_tasks"],
        "components_at_least_300": component_count >= contract["cohort"]["minimum_primary_components"],
        "dominant_task_pair_share_at_most_0_2": (
            dominant_share <= contract["cohort"]["maximum_dominant_task_pair_share"]
        ),
    }
    scaling_gates = {
        "size_means_monotonic_nondecreasing": monotonic,
        "high_minus_low_point_at_least_0_02": endpoint_delta >= 0.02,
        "each_seed_high_minus_low_positive": all(
            value > 0.0 for value in endpoint_delta_by_seed.values()
        ),
        "high_minus_low_ci_lower_positive": low_high_ci[0] > 0.0,
    }
    baseline_gates = {
        "each_high_size_seed_above_baseline": each_high_seed_beats,
        "high_minus_baseline_ci_lower_positive": high_baseline_ci[0] > 0.0,
        "all_leave_one_task_out_deltas_positive": all(value > 0.0 for value in loto.values()),
    }
    utility_gates = {"component_gain_ci_lower_positive": utility_ci[0] > 0.0}
    support_pass = all(support_gates.values())
    scaling_pass = all(scaling_gates.values())
    baseline_pass = all(baseline_gates.values())
    utility_pass = all(utility_gates.values())
    if support_pass and scaling_pass and baseline_pass and utility_pass:
        status = "STRONG_CLEAN_SCALING_BASELINE_AND_UTILITY_PASS"
    elif support_pass and scaling_pass and baseline_pass:
        status = "CLEAN_SCALING_AND_BASELINE_PASS_UTILITY_NOT_CONFIRMED"
    elif support_pass and scaling_pass:
        status = "CLEAN_SCALING_PASS_BASELINE_NOT_CONFIRMED"
    else:
        status = "VALID_NO_CLEAN_SCALING_CONFIRMATION"

    return {
        "status": status,
        "support": {
            "pairs": len(primary_rows),
            "tasks": len(task_counts),
            "components": component_count,
            "dominant_task_pair_share": dominant_share,
            "gates": support_gates,
            "pass": support_pass,
        },
        "capacity_scaling": {
            "size_mean_task_macro_accuracy": size_means,
            "size_seed_task_macro_accuracy": size_seed_task_macros,
            "high_minus_low_task_macro_delta": endpoint_delta,
            "high_minus_low_task_macro_delta_by_seed": endpoint_delta_by_seed,
            "high_minus_low_task_bootstrap_ci": low_high_ci,
            "per_task_delta": low_high_delta,
            "gates": scaling_gates,
            "pass": scaling_pass,
        },
        "high_size_vs_baseline": {
            "baseline_task_macro_accuracy": baseline_task_macro,
            "high_size_seed_task_macro_accuracy": high_seed_task_macros,
            "seed_mean_high_minus_baseline_task_macro_delta": mean(high_baseline_delta.values()),
            "seed_mean_high_minus_baseline_task_bootstrap_ci": high_baseline_ci,
            "leave_one_task_out_delta": loto,
            "gates": baseline_gates,
            "pass": baseline_pass,
        },
        "utility_conversion": {
            "seed_mean_high_minus_baseline_component_gain_task_macro_delta": mean(
                high_component_delta.values()
            ),
            "task_bootstrap_ci": utility_ci,
            "per_task_delta": high_component_delta,
            "gates": utility_gates,
            "pass": utility_pass,
        },
    }


def write_outputs(
    out_dir: Path,
    summary: Mapping[str, Any],
    metrics: Mapping[str, dict[str, Any]],
    components: Mapping[str, Sequence[dict[str, Any]]],
    internals: Mapping[str, dict[str, Any]],
) -> None:
    if out_dir.exists():
        raise FileExistsError(f"refusing to overwrite {out_dir}")
    out_dir.mkdir(parents=True)
    (out_dir / "summary.json").write_bytes(canonical_bytes(summary))
    with (out_dir / "per_predictor_task.csv").open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=["predictor_id", "task", "accuracy"])
        writer.writeheader()
        for predictor_id in sorted(internals):
            for task in sorted(internals[predictor_id]["per_task"]):
                writer.writerow(
                    {
                        "predictor_id": predictor_id,
                        "task": task,
                        "accuracy": repr(internals[predictor_id]["per_task"][task]["accuracy"]),
                    }
                )
    fields = [
        "predictor_id", "component_id", "task", "pair_semantics", "parent_id",
        "parent_run_id", "endpoints", "selected_ties", "top1", "raw_regret",
        "normalized_regret", "gain_capture",
    ]
    with (out_dir / "per_predictor_component.csv").open(
        "w", encoding="utf-8", newline=""
    ) as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        for predictor_id in sorted(components):
            for row in components[predictor_id]:
                writer.writerow({"predictor_id": predictor_id, **row})
    manifest = {
        path.name: {"bytes": path.stat().st_size, "sha256": sha256_file(path)}
        for path in sorted(out_dir.iterdir())
        if path.is_file()
    }
    (out_dir / "artifact_manifest.json").write_bytes(canonical_bytes(manifest))


def analyze(contract_path: Path, lock_path: Path, bundle_path: Path) -> tuple[
    dict[str, Any],
    dict[str, dict[str, Any]],
    dict[str, list[dict[str, Any]]],
    dict[str, dict[str, Any]],
]:
    contract = read_object(contract_path, "contract")
    validate_contract(contract)
    contract_sha = sha256_file(contract_path)
    lock = read_object(lock_path, "pre-test lock")
    locked_runs = validate_lock(lock, contract, contract_sha)
    lock_sha = sha256_file(lock_path)
    bundle = read_object(bundle_path, "result bundle")
    truth, predictions, artifacts = validate_bundle(
        bundle_path, bundle, lock, lock_sha, locked_runs, contract
    )

    metrics: dict[str, dict[str, Any]] = {}
    components: dict[str, list[dict[str, Any]]] = {}
    internals: dict[str, dict[str, Any]] = {}
    for predictor_id in sorted(predictions):
        metric, component_rows, internal = predictor_metrics(
            predictor_id, truth, predictions[predictor_id], contract
        )
        metrics[predictor_id] = metric
        components[predictor_id] = component_rows
        internals[predictor_id] = internal
    comparison = comparison_summary(contract, metrics, internals, truth)
    summary = {
        "protocol": ANALYSIS_PROTOCOL,
        "status": comparison["status"],
        "input_identity": {
            "contract_sha256": contract_sha,
            "lock_sha256": lock_sha,
            "bundle_sha256": sha256_file(bundle_path),
            "artifacts": artifacts,
        },
        "access_attestation": {
            "gpu_jobs": 0,
            "api_calls": 0,
            "model_fits": 0,
            "base_llm_updates": 0,
            "prospective_score_channel_truth_read": False,
            "historical_test_touched_checkpoint_used": False,
        },
        "predictors": metrics,
        "decision": comparison,
    }
    return summary, metrics, components, internals


def main() -> None:
    args = arguments()
    summary, metrics, components, internals = analyze(
        args.contract, args.lock, args.bundle
    )
    write_outputs(args.out_dir, summary, metrics, components, internals)
    print(json.dumps({"status": summary["status"], "summary": str(args.out_dir / "summary.json")}, sort_keys=True))


if __name__ == "__main__":
    main()
