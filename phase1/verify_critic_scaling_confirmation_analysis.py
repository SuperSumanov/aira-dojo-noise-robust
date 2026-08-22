"""Independent verifier for critic-scaling confirmation artifacts.

This file deliberately does not import the producer.  It independently checks
the frozen contract/lock/bundle identities, reconstructs pair and component
metrics, repeats the task bootstrap, and compares the released CSV/JSON files.
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
import zlib
from pathlib import Path
from typing import Any, Iterable, Mapping, Sequence


EXPECTED_CONTRACT_SHA256 = "579771ac1b90b1022bdded1182ce5c5a17780a741dc95d82a53f5f91d577a568"
HEX64 = re.compile(r"[0-9a-f]{64}")


class VerificationError(RuntimeError):
    """Raised when independent reconstruction disagrees with the release."""


def cli() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--contract", type=Path, required=True)
    parser.add_argument("--lock", type=Path, required=True)
    parser.add_argument("--bundle", type=Path, required=True)
    parser.add_argument("--result-dir", type=Path, required=True)
    parser.add_argument("--receipt", type=Path, required=True)
    return parser.parse_args()


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()


def canonical(value: Any) -> bytes:
    return (json.dumps(value, indent=2, sort_keys=True, ensure_ascii=False) + "\n").encode()


def object_from(path: Path, label: str) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as error:
        raise VerificationError(f"cannot read {label}") from error
    if not isinstance(value, dict):
        raise VerificationError(f"{label} is not an object")
    return value


def jsonl_from(path: Path, label: str) -> list[dict[str, Any]]:
    rows = []
    try:
        with path.open(encoding="utf-8") as handle:
            for number, line in enumerate(handle, 1):
                if not line.strip():
                    raise VerificationError(f"blank line in {label}:{number}")
                value = json.loads(line)
                if not isinstance(value, dict):
                    raise VerificationError(f"non-object row in {label}:{number}")
                rows.append(value)
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as error:
        if isinstance(error, VerificationError):
            raise
        raise VerificationError(f"cannot read {label}") from error
    if not rows:
        raise VerificationError(f"{label} is empty")
    return rows


def safe_file(root: Path, relative: Any, label: str) -> Path:
    if not isinstance(relative, str) or not relative or Path(relative).is_absolute():
        raise VerificationError(f"bad relative path for {label}")
    root = root.resolve()
    cursor = root
    for part in Path(relative).parts:
        cursor = cursor / part
        if cursor.is_symlink():
            raise VerificationError(f"{label} contains a symlink")
    path = (root / relative).resolve()
    try:
        path.relative_to(root)
    except ValueError as error:
        raise VerificationError(f"{label} escapes its root") from error
    if not path.is_file():
        raise VerificationError(f"{label} is missing")
    return path


def artifact(root: Path, spec: Any, label: str) -> tuple[Path, str, int]:
    if not isinstance(spec, dict):
        raise VerificationError(f"{label} spec is invalid")
    path = safe_file(root, spec.get("path"), label)
    digest = spec.get("sha256")
    rows = spec.get("rows")
    if not isinstance(digest, str) or HEX64.fullmatch(digest) is None:
        raise VerificationError(f"{label} digest is invalid")
    if not isinstance(rows, int) or rows <= 0:
        raise VerificationError(f"{label} row count is invalid")
    if sha256(path) != digest:
        raise VerificationError(f"{label} digest mismatch")
    return path, digest, rows


def number(value: Any, label: str) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise VerificationError(f"{label} is not numeric")
    output = float(value)
    if not math.isfinite(output):
        raise VerificationError(f"{label} is non-finite")
    return output


def average(values: Iterable[float]) -> float:
    materialized = [float(value) for value in values]
    if not materialized:
        raise VerificationError("empty average")
    return math.fsum(materialized) / len(materialized)


def means(items: Iterable[tuple[str, float]]) -> dict[str, float]:
    grouped: dict[str, list[float]] = collections.defaultdict(list)
    for key, value in items:
        grouped[key].append(float(value))
    return {key: average(grouped[key]) for key in sorted(grouped)}


def pair_digest(row: Mapping[str, Any]) -> str:
    fields = (
        "task", "pair_semantics", "parent_id", "comparison_component_id",
        "better_id", "worse_id",
    )
    try:
        payload = [row[field] for field in fields]
    except KeyError as error:
        raise VerificationError("truth lacks pair identity field") from error
    encoded = json.dumps(payload, ensure_ascii=False, separators=(",", ":")).encode()
    return hashlib.sha256(encoded).hexdigest()


def credit(margin: float) -> float:
    return 1.0 if margin > 0 else 0.0 if margin < 0 else 0.5


def seeded(base: int, label: str) -> int:
    return int(base) + int(zlib.crc32(label.encode()) & 0x7FFFFFFF)


def interval(values: Mapping[str, float], draws: int, seed: int) -> list[float]:
    keys = sorted(values)
    if len(keys) < 2:
        raise VerificationError("bootstrap has fewer than two clusters")
    generator = random.Random(seed)
    samples = []
    for _ in range(draws):
        samples.append(average(values[generator.choice(keys)] for _ in keys))
    samples.sort()
    return [samples[int(0.025 * (draws - 1))], samples[int(0.975 * (draws - 1))]]


def model_name(size: float, seed: int) -> str:
    return f"qwen3_{size:g}b_seed{seed}"


def verify_contract_and_lock(
    contract_path: Path, lock_path: Path
) -> tuple[dict[str, Any], dict[str, Any], dict[tuple[float, int], dict[str, Any]]]:
    if sha256(contract_path) != EXPECTED_CONTRACT_SHA256:
        raise VerificationError("contract is not the frozen v1 bytes")
    contract = object_from(contract_path, "contract")
    if contract.get("protocol") != "critic-scaling-confirmation-contract-v1":
        raise VerificationError("wrong contract protocol")
    if contract["matrix"]["model_sizes_b"] != [0.6, 1.7, 4.0, 8.0]:
        raise VerificationError("wrong size matrix")
    if contract["matrix"]["seeds"] != [6, 7]:
        raise VerificationError("wrong seed matrix")
    if contract["cohort"] != {
        "split": "test",
        "primary_pair_semantics": "canonical_raw_sibling",
        "same_pair_ids_required_for_every_predictor": True,
        "minimum_primary_tasks": 20,
        "minimum_primary_components": 300,
        "maximum_dominant_task_pair_share": 0.2,
        "pair_truth_locked_before_checkpoint_scoring": True,
        "test_may_be_scored_once_per_checkpoint": True,
    }:
        raise VerificationError("cohort contract differs")
    lock = object_from(lock_path, "pre-test lock")
    if lock.get("protocol") != "critic-scaling-confirmation-lock-v1":
        raise VerificationError("wrong lock protocol")
    if lock.get("status") != "LOCKED_BEFORE_TEST_ACCESS":
        raise VerificationError("lock was not frozen before test")
    if lock.get("contract_sha256") != EXPECTED_CONTRACT_SHA256:
        raise VerificationError("lock references another contract")
    expected = {
        (float(size), int(seed))
        for size in contract["matrix"]["model_sizes_b"]
        for seed in contract["matrix"]["seeds"]
    }
    indexed: dict[tuple[float, int], dict[str, Any]] = {}
    for row in lock.get("runs", []):
        if not isinstance(row, dict):
            raise VerificationError("invalid locked run")
        key = (number(row.get("model_size_b"), "model size"), row.get("seed"))
        if not isinstance(key[1], int) or key in indexed:
            raise VerificationError("invalid or duplicate locked run")
        checkpoint = row.get("checkpoint_manifest_sha256")
        if not isinstance(checkpoint, str) or HEX64.fullmatch(checkpoint) is None:
            raise VerificationError("invalid checkpoint digest")
        if row.get("checkpoint_locked_before_test_access") is not True:
            raise VerificationError("checkpoint was not locked before test")
        if row.get("training_status") != "COMPLETE" or row.get("selected_on_dev_only") is not True:
            raise VerificationError("checkpoint completion/dev-only selection failed")
        if not isinstance(row.get("checkpoint_step"), int) or row["checkpoint_step"] <= 0:
            raise VerificationError("checkpoint step is invalid")
        number(row.get("dev_selection_metric"), "dev metric")
        indexed[(key[0], int(key[1]))] = row
    if set(indexed) != expected:
        raise VerificationError("locked matrix differs")
    return contract, lock, indexed


def verify_ledger(
    root: Path,
    spec: Any,
    label: str,
    lock_hash: str,
    truth_hash: str,
    prediction_hash: str,
    checkpoint_hash: str | None,
) -> str:
    if not isinstance(spec, dict):
        raise VerificationError(f"{label} ledger spec missing")
    path = safe_file(root, spec.get("path"), f"{label} ledger")
    digest = spec.get("sha256")
    if not isinstance(digest, str) or HEX64.fullmatch(digest) is None or sha256(path) != digest:
        raise VerificationError(f"{label} ledger digest mismatch")
    value = object_from(path, f"{label} ledger")
    wanted = {
        "status": "COMPLETE",
        "test_attempts": 1,
        "lock_sha256": lock_hash,
        "truth_sha256": truth_hash,
        "prediction_sha256": prediction_hash,
    }
    if any(value.get(key) != expected for key, expected in wanted.items()):
        raise VerificationError(f"{label} ledger fields differ")
    if checkpoint_hash is not None and value.get("checkpoint_manifest_sha256") != checkpoint_hash:
        raise VerificationError(f"{label} ledger checkpoint differs")
    return digest


def verify_truth(rows: Sequence[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    required = {
        "pair_id", "split", "task", "pair_semantics", "parent_id", "parent_run_id",
        "comparison_component_id", "better_id", "worse_id", "better_run_id",
        "worse_run_id", "better_utility", "worse_utility",
    }
    output: dict[str, dict[str, Any]] = {}
    unordered = set()
    utility_by_endpoint: dict[str, float] = {}
    edges_by_component: dict[str, list[tuple[str, str]]] = collections.defaultdict(list)
    metadata_by_component: dict[str, tuple[str, str, str, str]] = {}
    for index, original in enumerate(rows):
        if not required.issubset(original):
            raise VerificationError(f"truth row {index} lacks fields")
        row = dict(original)
        string_fields = required - {"better_utility", "worse_utility"}
        if any(not isinstance(row[field], str) or not row[field] for field in string_fields):
            raise VerificationError(f"truth row {index} has empty identity")
        if row["split"] != "test" or row["better_id"] == row["worse_id"]:
            raise VerificationError(f"truth row {index} split/self-pair invalid")
        better = number(row["better_utility"], "better utility")
        worse = number(row["worse_utility"], "worse utility")
        if not better > worse:
            raise VerificationError("truth orientation is not strict")
        row["better_utility"], row["worse_utility"] = better, worse
        if row["pair_id"] != pair_digest(row) or row["pair_id"] in output:
            raise VerificationError("truth pair id mismatch or duplicate")
        reverse = (
            row["task"], row["pair_semantics"], row["parent_id"],
            row["comparison_component_id"], frozenset((row["better_id"], row["worse_id"])),
        )
        if reverse in unordered:
            raise VerificationError("truth reversed duplicate")
        unordered.add(reverse)
        if row["pair_semantics"] == "canonical_raw_sibling" and not (
            row["parent_run_id"] == row["better_run_id"] == row["worse_run_id"]
        ):
            raise VerificationError("primary pair crosses runs")
        for endpoint, utility in ((row["better_id"], better), (row["worse_id"], worse)):
            if endpoint in utility_by_endpoint and not math.isclose(
                utility_by_endpoint[endpoint], utility, rel_tol=0, abs_tol=1e-12
            ):
                raise VerificationError("endpoint utility inconsistent")
            utility_by_endpoint[endpoint] = utility
        component = row["comparison_component_id"]
        meta = (row["task"], row["pair_semantics"], row["parent_id"], row["parent_run_id"])
        if component in metadata_by_component and metadata_by_component[component] != meta:
            raise VerificationError("component metadata mixed")
        metadata_by_component[component] = meta
        edges_by_component[component].append((row["better_id"], row["worse_id"]))
        output[row["pair_id"]] = row
    for component, edges in edges_by_component.items():
        graph: dict[str, set[str]] = collections.defaultdict(set)
        for left, right in edges:
            graph[left].add(right)
            graph[right].add(left)
        reached = {min(graph)}
        stack = list(reached)
        while stack:
            node = stack.pop()
            for neighbour in sorted(graph[node]):
                if neighbour not in reached:
                    reached.add(neighbour)
                    stack.append(neighbour)
        if reached != set(graph):
            raise VerificationError(f"component {component} disconnected")
    return output


def verify_prediction_rows(
    rows: Sequence[dict[str, Any]], truth: Mapping[str, dict[str, Any]], label: str
) -> dict[str, dict[str, float]]:
    output: dict[str, dict[str, float]] = {}
    endpoint_scores: dict[str, float] = {}
    for index, row in enumerate(rows):
        if not {"pair_id", "better_score", "worse_score", "margin"}.issubset(row):
            raise VerificationError(f"{label} row {index} lacks fields")
        identity = row["pair_id"]
        if identity not in truth or identity in output:
            raise VerificationError(f"{label} pair coverage/duplicate failure")
        better = number(row["better_score"], "better score")
        worse = number(row["worse_score"], "worse score")
        margin = number(row["margin"], "margin")
        if not math.isclose(margin, better - worse, rel_tol=0, abs_tol=1e-9):
            raise VerificationError(f"{label} margin mismatch")
        truth_row = truth[identity]
        for endpoint, score in ((truth_row["better_id"], better), (truth_row["worse_id"], worse)):
            if endpoint in endpoint_scores and not math.isclose(
                endpoint_scores[endpoint], score, rel_tol=0, abs_tol=1e-9
            ):
                raise VerificationError(f"{label} endpoint score inconsistent")
            endpoint_scores[endpoint] = score
        output[identity] = {"better_score": better, "worse_score": worse, "margin": margin}
    if set(output) != set(truth):
        raise VerificationError(f"{label} does not cover exact truth")
    return output


def load_bundle(
    bundle_path: Path,
    lock_path: Path,
    lock: Mapping[str, Any],
    locked_runs: Mapping[tuple[float, int], dict[str, Any]],
) -> tuple[
    dict[str, dict[str, Any]],
    dict[str, dict[str, dict[str, float]]],
    dict[str, dict[str, Any]],
]:
    bundle = object_from(bundle_path, "bundle")
    lock_hash = sha256(lock_path)
    if bundle.get("protocol") != "critic-scaling-confirmation-bundle-v1":
        raise VerificationError("wrong bundle protocol")
    if bundle.get("status") != "COMPLETE" or bundle.get("lock_sha256") != lock_hash:
        raise VerificationError("bundle is incomplete or bound to another lock")
    root = bundle_path.parent
    truth_path, truth_hash, truth_count = artifact(root, bundle.get("truth"), "truth")
    if truth_hash != lock["dataset"]["truth_sha256"] or truth_count != lock["dataset"]["truth_rows"]:
        raise VerificationError("truth differs from lock")
    truth_rows = jsonl_from(truth_path, "truth")
    if len(truth_rows) != truth_count:
        raise VerificationError("truth count differs")
    truth = verify_truth(truth_rows)
    predictors: dict[str, dict[str, dict[str, float]]] = {}
    receipts: dict[str, dict[str, Any]] = {
        "truth": {"path": bundle["truth"]["path"], "sha256": truth_hash, "rows": truth_count}
    }
    baseline = bundle.get("baseline")
    if not isinstance(baseline, dict) or baseline.get("id") != "char_tfidf_lr":
        raise VerificationError("baseline identity differs")
    if baseline.get("receipt_sha256") != lock["baseline"]["receipt_sha256"]:
        raise VerificationError("baseline receipt differs")
    path, digest, count = artifact(root, baseline.get("predictions"), "baseline predictions")
    if count != truth_count:
        raise VerificationError("baseline count differs")
    predictors["char_tfidf_lr"] = verify_prediction_rows(
        jsonl_from(path, "baseline predictions"), truth, "baseline"
    )
    ledger = verify_ledger(
        root, baseline.get("ledger"), "baseline", lock_hash, truth_hash, digest, None
    )
    receipts["char_tfidf_lr"] = {
        "path": baseline["predictions"]["path"], "sha256": digest, "rows": count,
        "ledger_sha256": ledger
    }
    seen = set()
    for row in bundle.get("runs", []):
        if not isinstance(row, dict):
            raise VerificationError("invalid bundle run")
        key = (number(row.get("model_size_b"), "bundle size"), row.get("seed"))
        if not isinstance(key[1], int) or key in seen or key not in locked_runs:
            raise VerificationError("invalid/extra/duplicate bundle run")
        seen.add(key)
        checkpoint = locked_runs[key]["checkpoint_manifest_sha256"]
        if row.get("checkpoint_manifest_sha256") != checkpoint:
            raise VerificationError("bundle checkpoint differs")
        name = model_name(key[0], int(key[1]))
        path, digest, count = artifact(root, row.get("predictions"), f"{name} predictions")
        if count != truth_count:
            raise VerificationError(f"{name} count differs")
        predictors[name] = verify_prediction_rows(jsonl_from(path, name), truth, name)
        ledger = verify_ledger(
            root, row.get("ledger"), name, lock_hash, truth_hash, digest, checkpoint
        )
        receipts[name] = {
            "path": row["predictions"]["path"], "sha256": digest, "rows": count,
            "ledger_sha256": ledger, "checkpoint_manifest_sha256": checkpoint,
        }
    if seen != set(locked_runs):
        raise VerificationError("bundle matrix incomplete")
    return truth, predictors, receipts


def components_for(
    rows: Sequence[dict[str, Any]], prediction: Mapping[str, Mapping[str, float]]
) -> list[dict[str, Any]]:
    grouped: dict[str, list[dict[str, Any]]] = collections.defaultdict(list)
    for row in rows:
        grouped[row["comparison_component_id"]].append(row)
    output = []
    for component in sorted(grouped):
        entries = grouped[component]
        scores: dict[str, float] = {}
        utilities: dict[str, float] = {}
        for row in entries:
            pred = prediction[row["pair_id"]]
            scores[row["better_id"]] = pred["better_score"]
            scores[row["worse_id"]] = pred["worse_score"]
            utilities[row["better_id"]] = row["better_utility"]
            utilities[row["worse_id"]] = row["worse_utility"]
        best_score = max(scores.values())
        selected = sorted(endpoint for endpoint, score in scores.items() if score == best_score)
        oracle = max(utilities.values())
        oracle_set = {endpoint for endpoint, utility in utilities.items() if utility == oracle}
        selected_utility = average(utilities[endpoint] for endpoint in selected)
        uniform = average(utilities.values())
        headroom = oracle - uniform
        if not headroom > 0:
            raise VerificationError("component has no headroom")
        regret = (oracle - selected_utility) / headroom
        output.append(
            {
                "component_id": component,
                "task": entries[0]["task"],
                "pair_semantics": entries[0]["pair_semantics"],
                "parent_id": entries[0]["parent_id"],
                "parent_run_id": entries[0]["parent_run_id"],
                "endpoints": len(scores),
                "selected_ties": len(selected),
                "top1": len(set(selected) & oracle_set) / len(selected),
                "raw_regret": oracle - selected_utility,
                "normalized_regret": regret,
                "gain_capture": 1.0 - regret,
            }
        )
    return output


def predictor_result(
    name: str,
    truth: Mapping[str, dict[str, Any]],
    prediction: Mapping[str, Mapping[str, float]],
    contract: Mapping[str, Any],
) -> tuple[dict[str, Any], list[dict[str, Any]], dict[str, Any]]:
    primary = [
        truth[identity] for identity in sorted(truth)
        if truth[identity]["pair_semantics"] == "canonical_raw_sibling"
    ]
    if not primary:
        raise VerificationError("no primary rows")
    credits = {row["pair_id"]: credit(prediction[row["pair_id"]]["margin"]) for row in primary}
    task = means((row["task"], credits[row["pair_id"]]) for row in primary)
    run = means((row["parent_run_id"], credits[row["pair_id"]]) for row in primary)
    component_rows = components_for(primary, prediction)
    component_gain = means((row["task"], row["gain_capture"]) for row in component_rows)
    component_top1 = means((row["task"], row["top1"]) for row in component_rows)
    by_semantics: dict[str, list[dict[str, Any]]] = collections.defaultdict(list)
    for row in truth.values():
        by_semantics[row["pair_semantics"]].append(row)
    semantics = {}
    for semantics_name in sorted(by_semantics):
        selected = by_semantics[semantics_name]
        task_values = means(
            (row["task"], credit(prediction[row["pair_id"]]["margin"])) for row in selected
        )
        semantics[semantics_name] = {
            "pairs": len(selected),
            "tasks": len(task_values),
            "micro_accuracy": average(
                credit(prediction[row["pair_id"]]["margin"]) for row in selected
            ),
            "task_macro_accuracy": average(task_values.values()),
        }
    draws = int(contract["inference"]["bootstrap_draws"])
    seed = int(contract["inference"]["bootstrap_seed"])
    result = {
        "predictor_id": name,
        "primary_pairs": len(primary),
        "primary_tasks": len(task),
        "primary_runs": len(run),
        "primary_components": len(component_rows),
        "micro_accuracy": average(credits.values()),
        "task_macro_accuracy": average(task.values()),
        "task_bootstrap_ci": interval(task, draws, seeded(seed, name + ":task")),
        "run_macro_accuracy": average(run.values()),
        "run_bootstrap_ci": interval(run, draws, seeded(seed, name + ":run")),
        "component_task_macro_top1": average(component_top1.values()),
        "component_task_macro_gain_capture": average(component_gain.values()),
        "component_gain_task_bootstrap_ci": interval(
            component_gain, draws, seeded(seed, name + ":component-gain")
        ),
        "semantics": semantics,
    }
    internal = {
        "per_task": {key: {"accuracy": value} for key, value in task.items()},
        "component_task_gain": component_gain,
        "component_task_top1": component_top1,
    }
    return result, component_rows, internal


def decision_result(
    contract: Mapping[str, Any],
    metrics: Mapping[str, dict[str, Any]],
    internals: Mapping[str, dict[str, Any]],
    truth: Mapping[str, dict[str, Any]],
) -> dict[str, Any]:
    sizes = [float(value) for value in contract["matrix"]["model_sizes_b"]]
    seeds = [int(value) for value in contract["matrix"]["seeds"]]
    low, high = 0.6, 8.0
    baseline = "char_tfidf_lr"
    tasks = sorted(internals[baseline]["per_task"])
    size_task = {
        size: {
            task: average(
                internals[model_name(size, seed)]["per_task"][task]["accuracy"]
                for seed in seeds
            )
            for task in tasks
        }
        for size in sizes
    }
    size_means = {str(size): average(size_task[size].values()) for size in sizes}
    size_seed = {
        str(size): {
            str(seed): metrics[model_name(size, seed)]["task_macro_accuracy"] for seed in seeds
        }
        for size in sizes
    }
    low_high = {task: size_task[high][task] - size_task[low][task] for task in tasks}
    baseline_task = {
        task: internals[baseline]["per_task"][task]["accuracy"] for task in tasks
    }
    high_base = {task: size_task[high][task] - baseline_task[task] for task in tasks}
    draws = int(contract["inference"]["bootstrap_draws"])
    seed0 = int(contract["inference"]["bootstrap_seed"])
    low_high_ci = interval(low_high, draws, seeded(seed0, "high-minus-low"))
    high_base_ci = interval(high_base, draws, seeded(seed0, "high-minus-baseline"))
    endpoint_by_seed = {
        str(seed): metrics[model_name(high, seed)]["task_macro_accuracy"]
        - metrics[model_name(low, seed)]["task_macro_accuracy"]
        for seed in seeds
    }
    high_seed = {
        str(seed): metrics[model_name(high, seed)]["task_macro_accuracy"] for seed in seeds
    }
    baseline_macro = metrics[baseline]["task_macro_accuracy"]
    loto = {
        task: average(value for other, value in high_base.items() if other != task)
        for task in tasks
    }
    baseline_gain = internals[baseline]["component_task_gain"]
    utility_delta = {
        task: average(
            internals[model_name(high, seed)]["component_task_gain"][task] for seed in seeds
        ) - baseline_gain[task]
        for task in sorted(baseline_gain)
    }
    utility_ci = interval(
        utility_delta, draws, seeded(seed0, "high-minus-baseline-component-gain")
    )
    primary = [
        row for row in truth.values() if row["pair_semantics"] == "canonical_raw_sibling"
    ]
    task_counts = collections.Counter(row["task"] for row in primary)
    components = len({row["comparison_component_id"] for row in primary})
    dominant = max(task_counts.values()) / len(primary)
    support_gates = {
        "tasks_at_least_20": len(task_counts) >= 20,
        "components_at_least_300": components >= 300,
        "dominant_task_pair_share_at_most_0_2": dominant <= 0.2,
    }
    monotonic = all(
        size_means[str(left)] <= size_means[str(right)]
        for left, right in zip(sizes, sizes[1:])
    )
    scaling_gates = {
        "size_means_monotonic_nondecreasing": monotonic,
        "high_minus_low_point_at_least_0_02": average(low_high.values()) >= 0.02,
        "each_seed_high_minus_low_positive": all(value > 0 for value in endpoint_by_seed.values()),
        "high_minus_low_ci_lower_positive": low_high_ci[0] > 0,
    }
    baseline_gates = {
        "each_high_size_seed_above_baseline": all(value > baseline_macro for value in high_seed.values()),
        "high_minus_baseline_ci_lower_positive": high_base_ci[0] > 0,
        "all_leave_one_task_out_deltas_positive": all(value > 0 for value in loto.values()),
    }
    utility_gates = {"component_gain_ci_lower_positive": utility_ci[0] > 0}
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
            "pairs": len(primary), "tasks": len(task_counts), "components": components,
            "dominant_task_pair_share": dominant, "gates": support_gates, "pass": support_pass,
        },
        "capacity_scaling": {
            "size_mean_task_macro_accuracy": size_means,
            "size_seed_task_macro_accuracy": size_seed,
            "high_minus_low_task_macro_delta": average(low_high.values()),
            "high_minus_low_task_macro_delta_by_seed": endpoint_by_seed,
            "high_minus_low_task_bootstrap_ci": low_high_ci,
            "per_task_delta": low_high,
            "gates": scaling_gates, "pass": scaling_pass,
        },
        "high_size_vs_baseline": {
            "baseline_task_macro_accuracy": baseline_macro,
            "high_size_seed_task_macro_accuracy": high_seed,
            "seed_mean_high_minus_baseline_task_macro_delta": average(high_base.values()),
            "seed_mean_high_minus_baseline_task_bootstrap_ci": high_base_ci,
            "leave_one_task_out_delta": loto,
            "gates": baseline_gates, "pass": baseline_pass,
        },
        "utility_conversion": {
            "seed_mean_high_minus_baseline_component_gain_task_macro_delta": average(
                utility_delta.values()
            ),
            "task_bootstrap_ci": utility_ci,
            "per_task_delta": utility_delta,
            "gates": utility_gates, "pass": utility_pass,
        },
    }


def same(expected: Any, observed: Any, path: str = "root") -> None:
    if isinstance(expected, dict):
        if not isinstance(observed, dict) or set(expected) != set(observed):
            raise VerificationError(f"mapping keys differ at {path}")
        for key in sorted(expected):
            same(expected[key], observed[key], f"{path}.{key}")
    elif isinstance(expected, list):
        if not isinstance(observed, list) or len(expected) != len(observed):
            raise VerificationError(f"list shape differs at {path}")
        for index, (left, right) in enumerate(zip(expected, observed)):
            same(left, right, f"{path}[{index}]")
    elif isinstance(expected, float):
        if not isinstance(observed, (int, float)) or not math.isclose(
            expected, float(observed), rel_tol=0, abs_tol=1e-12
        ):
            raise VerificationError(f"numeric value differs at {path}")
    elif expected != observed:
        raise VerificationError(f"value differs at {path}")


def verify_csvs(
    result_dir: Path,
    internals: Mapping[str, dict[str, Any]],
    component_rows: Mapping[str, Sequence[dict[str, Any]]],
) -> dict[str, int]:
    task_path = result_dir / "per_predictor_task.csv"
    component_path = result_dir / "per_predictor_component.csv"
    with task_path.open(encoding="utf-8", newline="") as handle:
        actual_task = list(csv.DictReader(handle))
    expected_task = [
        {"predictor_id": predictor, "task": task, "accuracy": repr(internals[predictor]["per_task"][task]["accuracy"])}
        for predictor in sorted(internals)
        for task in sorted(internals[predictor]["per_task"])
    ]
    if actual_task != expected_task:
        raise VerificationError("per-task CSV differs")
    with component_path.open(encoding="utf-8", newline="") as handle:
        actual_component = list(csv.DictReader(handle))
    expected_component = []
    for predictor in sorted(component_rows):
        for row in component_rows[predictor]:
            expected_component.append(
                {
                    "predictor_id": predictor,
                    **{key: str(value) for key, value in row.items()},
                }
            )
    if actual_component != expected_component:
        raise VerificationError("per-component CSV differs")
    return {"per_task_rows": len(actual_task), "per_component_rows": len(actual_component)}


def verify_manifest(result_dir: Path) -> dict[str, dict[str, Any]]:
    manifest = object_from(result_dir / "artifact_manifest.json", "artifact manifest")
    expected_names = {"summary.json", "per_predictor_task.csv", "per_predictor_component.csv"}
    if set(manifest) != expected_names:
        raise VerificationError("artifact manifest names differ")
    for name in sorted(expected_names):
        path = result_dir / name
        expected = {"bytes": path.stat().st_size, "sha256": sha256(path)}
        if manifest[name] != expected:
            raise VerificationError(f"artifact manifest differs for {name}")
    return manifest


def verify(
    contract_path: Path,
    lock_path: Path,
    bundle_path: Path,
    result_dir: Path,
) -> dict[str, Any]:
    contract, lock, locked_runs = verify_contract_and_lock(contract_path, lock_path)
    truth, predictions, receipts = load_bundle(bundle_path, lock_path, lock, locked_runs)
    metrics: dict[str, dict[str, Any]] = {}
    components: dict[str, list[dict[str, Any]]] = {}
    internals: dict[str, dict[str, Any]] = {}
    for name in sorted(predictions):
        metric, rows, internal = predictor_result(name, truth, predictions[name], contract)
        metrics[name], components[name], internals[name] = metric, rows, internal
    decision = decision_result(contract, metrics, internals, truth)
    released = object_from(result_dir / "summary.json", "released summary")
    if released.get("protocol") != "critic-scaling-confirmation-analysis-v1":
        raise VerificationError("released summary protocol differs")
    same(metrics, released.get("predictors"), "predictors")
    same(decision, released.get("decision"), "decision")
    if released.get("status") != decision["status"]:
        raise VerificationError("released status differs")
    identity = released.get("input_identity", {})
    wanted_identity = {
        "contract_sha256": sha256(contract_path),
        "lock_sha256": sha256(lock_path),
        "bundle_sha256": sha256(bundle_path),
        "artifacts": receipts,
    }
    same(wanted_identity, identity, "input_identity")
    if released.get("access_attestation") != {
        "gpu_jobs": 0,
        "api_calls": 0,
        "model_fits": 0,
        "base_llm_updates": 0,
        "prospective_score_channel_truth_read": False,
        "historical_test_touched_checkpoint_used": False,
    }:
        raise VerificationError("access attestation differs")
    csv_counts = verify_csvs(result_dir, internals, components)
    manifest = verify_manifest(result_dir)
    return {
        "protocol": "critic-scaling-confirmation-independent-verifier-v1",
        "status": "INDEPENDENT_VERIFICATION_PASS",
        "analysis_status": decision["status"],
        "contract_sha256": sha256(contract_path),
        "lock_sha256": sha256(lock_path),
        "bundle_sha256": sha256(bundle_path),
        "summary_sha256": sha256(result_dir / "summary.json"),
        "artifact_manifest_sha256": sha256(result_dir / "artifact_manifest.json"),
        "predictors": len(predictions),
        **csv_counts,
        "released_artifacts": manifest,
        "producer_imported": False,
    }


def main() -> None:
    args = cli()
    if args.receipt.exists():
        raise FileExistsError(f"refusing to overwrite {args.receipt}")
    receipt = verify(args.contract, args.lock, args.bundle, args.result_dir)
    args.receipt.parent.mkdir(parents=True, exist_ok=True)
    args.receipt.write_bytes(canonical(receipt))
    print(json.dumps({"status": receipt["status"], "receipt": str(args.receipt)}, sort_keys=True))


if __name__ == "__main__":
    main()
