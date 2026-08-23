"""Retrospective train/dev qualification for a task-relative gap-aware critic.

The command line deliberately has no outer-test or prospective-truth argument.
Only the fixed component-clean train/dev pair files are valid outcome inputs.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import math
import re
from collections import defaultdict
from pathlib import Path
from typing import Any

import numpy as np
from scipy import sparse
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.linear_model import LogisticRegression, Ridge


PROTOCOL = "critic-gap-aware-train-dev-qualification-v1"
CONTRACT_SHA256 = "f411c0f732df12158e8c683ddbb94cea107d7673b40b8305ee5b83c8219ef4f8"
ARM_ORDER = ("binary_bt", "gap_permuted_bt", "gap_weighted_bt", "gap_ridge")


class QualificationError(RuntimeError):
    """Raised when a frozen identity or scientific invariant is violated."""


def canonical(value: Any) -> bytes:
    return (json.dumps(value, indent=2, sort_keys=True, ensure_ascii=False) + "\n").encode("utf-8")


def compact(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()


def verify_file(path: Path, expected: dict[str, Any], role: str) -> None:
    if not path.is_file():
        raise QualificationError(f"missing {role} input")
    if path.stat().st_size != expected["bytes"] or sha256_file(path) != expected["sha256"]:
        raise QualificationError(f"{role} input identity mismatch")


def load_contract(path: Path) -> dict[str, Any]:
    if sha256_file(path) != CONTRACT_SHA256:
        raise QualificationError("contract identity mismatch")
    contract = json.loads(path.read_text(encoding="utf-8"))
    if (
        contract.get("protocol") != PROTOCOL
        or contract.get("status") != "PREREGISTERED_BEFORE_ANY_GAP_AWARE_MODEL_FIT"
        or contract.get("resources", {}).get("gpu_jobs") != 0
        or contract.get("resources", {}).get("api_calls") != 0
        or contract.get("resources", {}).get("maximum_unique_cpu_fits_per_implementation") != 4
    ):
        raise QualificationError("contract semantic mismatch")
    return contract


def pair_key(row: dict[str, Any]) -> tuple[str, str, str, str]:
    try:
        left, right = sorted((row["better"], row["worse"]))
        values = row["task"], row["parent"], left, right
    except (KeyError, TypeError, ValueError) as error:
        raise QualificationError("invalid pair identity") from error
    if not all(isinstance(value, str) and value for value in values) or left == right:
        raise QualificationError("invalid pair identity")
    return values


def pair_id(row: dict[str, Any]) -> str:
    return hashlib.sha256(compact(pair_key(row)).encode("utf-8")).hexdigest()


def read_pairs(path: Path, expected: dict[str, Any], role: str) -> list[dict[str, Any]]:
    verify_file(path, expected, role)
    if role not in {"train", "dev"}:
        raise QualificationError("unknown pair-source role")
    rows: list[dict[str, Any]] = []
    keys: set[tuple[str, str, str, str]] = set()
    for line_number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
        if not line:
            raise QualificationError(f"blank {role} row")
        try:
            row = json.loads(line)
        except json.JSONDecodeError as error:
            raise QualificationError(f"invalid {role} JSON at row {line_number}") from error
        if not isinstance(row, dict):
            raise QualificationError(f"non-object {role} row")
        key = pair_key(row)
        if key in keys:
            raise QualificationError(f"duplicate unordered pair in {role}")
        keys.add(key)
        gap = row.get("gap_raw")
        component = row.get("pair_component_id")
        if (
            row.get("intask_split") != role
            or row.get("outer_intask_split") != "train"
            or row.get("train_dev_protocol") != "pair-graph-component-train-dev-split-v1"
            or row.get("train_dev_seed") != 20260821
            or row.get("train_dev_target_numerator") != 1
            or row.get("train_dev_target_denominator") != 10
            or row.get("src") != "decision"
            or not isinstance(gap, (int, float))
            or not math.isfinite(gap)
            or gap <= 0
            or not isinstance(component, str)
            or re.fullmatch(r"[0-9a-f]{64}", component) is None
        ):
            raise QualificationError(f"invalid component-clean receipt in {role}")
        rows.append(row)
    if len(rows) != expected["rows"]:
        raise QualificationError(f"{role} row-count mismatch")
    return rows


def load_codes(
    path: Path, expected: dict[str, Any], needed: set[str]
) -> tuple[dict[str, str], dict[str, str], dict[str, tuple[Any, ...]], dict[str, int]]:
    verify_file(path, expected, "cards")
    grouped = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(grouped, dict):
        raise QualificationError("cards root is not grouped by physical run")
    codes: dict[str, str] = {}
    tasks: dict[str, str] = {}
    runs: dict[str, str] = {}
    configs: dict[str, tuple[Any, ...]] = {}
    seen: set[str] = set()
    total = 0
    for run_id in sorted(grouped):
        cards = grouped[run_id]
        if not isinstance(run_id, str) or not run_id or not isinstance(cards, list):
            raise QualificationError("invalid cards run group")
        for card in cards:
            total += 1
            if not isinstance(card, dict) or not isinstance(card.get("id"), str) or card["id"] in seen:
                raise QualificationError("invalid or duplicate card")
            card_id = card["id"]
            seen.add(card_id)
            if card_id not in needed:
                continue
            task_object = card.get("task")
            task = task_object.get("name") if isinstance(task_object, dict) else None
            config = (task, card.get("client"), card.get("hardware"), card.get("time_limit"), card.get("execution_timeout"))
            if (
                not isinstance(card.get("code"), str)
                or not all(isinstance(value, str) and value for value in config[:3])
                or not all(isinstance(value, int) for value in config[3:])
            ):
                raise QualificationError("needed card lacks permitted code/provenance fields")
            codes[card_id] = card["code"]
            tasks[card_id] = task
            runs[card_id] = run_id
            configs[card_id] = config
    if set(codes) != needed:
        raise QualificationError("pair endpoint missing from cards")
    return codes, runs, configs, {"cards": total, "run_groups": len(grouped), "needed_cards": len(needed)}


def validate_integrity(
    train: list[dict[str, Any]],
    dev: list[dict[str, Any]],
    runs: dict[str, str],
    configs: dict[str, tuple[Any, ...]],
) -> dict[str, Any]:
    pools = {"train": train, "dev": dev}
    keys = {name: {pair_key(row) for row in rows} for name, rows in pools.items()}
    endpoints = {name: {endpoint for row in rows for endpoint in (row["better"], row["worse"])} for name, rows in pools.items()}
    run_sets = {name: {runs[endpoint] for endpoint in values} for name, values in endpoints.items()}
    components = {name: {row["pair_component_id"] for row in rows} for name, rows in pools.items()}
    overlap = {
        "pairs": len(keys["train"] & keys["dev"]),
        "endpoints": len(endpoints["train"] & endpoints["dev"]),
        "physical_runs": len(run_sets["train"] & run_sets["dev"]),
        "components": len(components["train"] & components["dev"]),
    }
    if any(overlap.values()):
        raise QualificationError("train/dev leakage")
    for rows in pools.values():
        for row in rows:
            if configs[row["better"]] != configs[row["worse"]] or configs[row["better"]][0] != row["task"]:
                raise QualificationError("pair violates exact task/config matching")
    return {
        "overlap": overlap,
        "pairs": {name: len(rows) for name, rows in pools.items()},
        "endpoints": {name: len(values) for name, values in endpoints.items()},
        "physical_runs": {name: len(values) for name, values in run_sets.items()},
        "components": {name: len(values) for name, values in components.items()},
    }


def task_scales(rows: list[dict[str, Any]]) -> dict[str, float]:
    grouped: dict[str, list[float]] = defaultdict(list)
    for row in rows:
        grouped[row["task"]].append(float(row["gap_raw"]))
    scales = {
        task: float(np.quantile(np.asarray(values, dtype=np.float64), 0.75, method="linear"))
        for task, values in sorted(grouped.items())
    }
    if not scales or any(not math.isfinite(value) or value <= 0 for value in scales.values()):
        raise QualificationError("invalid train-only task scale")
    return scales


def relative_gaps(rows: list[dict[str, Any]], scales: dict[str, float]) -> np.ndarray:
    try:
        values = np.fromiter((float(row["gap_raw"]) / scales[row["task"]] for row in rows), dtype=np.float64)
    except KeyError as error:
        raise QualificationError("dev-only task lacks train scale") from error
    if values.shape != (len(rows),) or not np.isfinite(values).all() or np.any(values <= 0):
        raise QualificationError("invalid task-relative gaps")
    return values


def task_mass_preserving_weights(rows: list[dict[str, Any]], relative: np.ndarray) -> np.ndarray:
    clipped = np.clip(relative, 0.25, 4.0)
    output = clipped.copy()
    by_task: dict[str, list[int]] = defaultdict(list)
    for index, row in enumerate(rows):
        by_task[row["task"]].append(index)
    for task in sorted(by_task):
        indices = np.asarray(by_task[task], dtype=np.int64)
        output[indices] /= float(np.mean(output[indices]))
    for task in sorted(by_task):
        indices = np.asarray(by_task[task], dtype=np.int64)
        if abs(float(np.mean(output[indices])) - 1.0) > 1e-12:
            raise QualificationError("task mass was not preserved")
    return output


def hash_cyclic_permuted_weights(rows: list[dict[str, Any]], weights: np.ndarray) -> np.ndarray:
    """Permute each task's exact weight multiset without using pair orientation."""
    if weights.shape != (len(rows),):
        raise QualificationError("weight shape mismatch")
    output = np.empty_like(weights)
    by_task: dict[str, list[int]] = defaultdict(list)
    for index, row in enumerate(rows):
        by_task[row["task"]].append(index)
    for task in sorted(by_task):
        indices = sorted(
            by_task[task],
            key=lambda index: hashlib.sha256(
                f"20260902|{compact(pair_key(rows[index]))}".encode("utf-8")
            ).hexdigest(),
        )
        if len(indices) < 2:
            raise QualificationError("task cannot support cyclic weight control")
        for position, destination in enumerate(indices):
            output[destination] = weights[indices[(position + 1) % len(indices)]]
        if not np.array_equal(np.sort(output[indices]), np.sort(weights[indices])):
            raise QualificationError("permuted control changed task weight multiset")
    return output


def matrix_indices(rows: list[dict[str, Any]], positions: dict[str, int]) -> tuple[np.ndarray, np.ndarray]:
    better = np.fromiter((positions[row["better"]] for row in rows), dtype=np.int64)
    worse = np.fromiter((positions[row["worse"]] for row in rows), dtype=np.int64)
    return better, worse


def fit_models(
    codes: dict[str, str], train: list[dict[str, Any]], dev: list[dict[str, Any]], scales: dict[str, float]
) -> tuple[dict[str, np.ndarray], dict[str, Any]]:
    train_ids = sorted({endpoint for row in train for endpoint in (row["better"], row["worse"])})
    all_ids = sorted(set(train_ids) | {endpoint for row in dev for endpoint in (row["better"], row["worse"])})
    positions = {card_id: index for index, card_id in enumerate(all_ids)}
    vectorizer = TfidfVectorizer(
        analyzer="char_wb", ngram_range=(3, 5), min_df=3, max_features=30000, sublinear_tf=True, dtype=np.float64
    )
    vectorizer.fit([codes[card_id][:20000] for card_id in train_ids])
    matrix = vectorizer.transform([codes[card_id][:20000] for card_id in all_ids])
    train_better, train_worse = matrix_indices(train, positions)
    dev_better, dev_worse = matrix_indices(dev, positions)
    train_difference = sparse.csr_matrix(matrix[train_better] - matrix[train_worse])
    dev_difference = sparse.csr_matrix(matrix[dev_better] - matrix[dev_worse])
    mirrored_x = sparse.vstack((train_difference, -train_difference), format="csr")
    hard_y = np.concatenate((np.ones(len(train), dtype=np.int8), np.zeros(len(train), dtype=np.int8)))

    binary = LogisticRegression(C=0.5, max_iter=1500, solver="lbfgs", random_state=0).fit(mirrored_x, hard_y)
    train_relative = relative_gaps(train, scales)
    train_weights = task_mass_preserving_weights(train, train_relative)
    permuted_weights = hash_cyclic_permuted_weights(train, train_weights)
    weighted = LogisticRegression(C=0.5, max_iter=1500, solver="lbfgs", random_state=0).fit(
        mirrored_x, hard_y, sample_weight=np.concatenate((train_weights, train_weights))
    )
    permuted = LogisticRegression(C=0.5, max_iter=1500, solver="lbfgs", random_state=0).fit(
        mirrored_x, hard_y, sample_weight=np.concatenate((permuted_weights, permuted_weights))
    )
    ridge_target = np.log1p(train_relative)
    ridge = Ridge(alpha=1.0, fit_intercept=False, solver="lsqr", tol=1e-6).fit(
        mirrored_x, np.concatenate((ridge_target, -ridge_target))
    )
    for arm, fitted in (
        ("binary_bt", binary),
        ("gap_permuted_bt", permuted),
        ("gap_weighted_bt", weighted),
    ):
        iterations = np.asarray(fitted.n_iter_)
        if iterations.size != 1 or int(iterations[0]) >= 1500:
            raise QualificationError(f"{arm} did not converge")
    coefficients = {
        "binary_bt": np.asarray(binary.coef_, dtype=np.float64).reshape(-1),
        "gap_permuted_bt": np.asarray(permuted.coef_, dtype=np.float64).reshape(-1),
        "gap_weighted_bt": np.asarray(weighted.coef_, dtype=np.float64).reshape(-1),
        "gap_ridge": np.asarray(ridge.coef_, dtype=np.float64).reshape(-1),
    }
    margins: dict[str, np.ndarray] = {}
    anti_symmetry = {}
    for arm in ARM_ORDER:
        values = np.asarray(dev_difference.dot(coefficients[arm]), dtype=np.float64).reshape(-1)
        reverse = np.asarray((-dev_difference).dot(coefficients[arm]), dtype=np.float64).reshape(-1)
        if values.shape != (len(dev),) or not np.isfinite(values).all():
            raise QualificationError(f"invalid {arm} dev margins")
        anti_symmetry[arm] = float(np.max(np.abs(values + reverse))) if len(values) else 0.0
        if anti_symmetry[arm] > 1e-12:
            raise QualificationError(f"{arm} margin is not antisymmetric")
        margins[arm] = values
    diagnostics = {
        "tfidf_features": int(matrix.shape[1]),
        "tfidf_train_fit_endpoints": len(train_ids),
        "transformed_endpoints": len(all_ids),
        "train_weight_min": float(np.min(train_weights)),
        "train_weight_max": float(np.max(train_weights)),
        "train_weight_mean": float(np.mean(train_weights)),
        "permuted_weight_equal_value_fraction": float(np.mean(permuted_weights == train_weights)),
        "permuted_weight_multiset_exact": bool(np.array_equal(np.sort(permuted_weights), np.sort(train_weights))),
        "anti_symmetry_max_abs": anti_symmetry,
        "fits": len(ARM_ORDER),
    }
    return margins, diagnostics


def credits(margins: np.ndarray) -> np.ndarray:
    return np.where(margins > 0, 1.0, np.where(margins < 0, 0.0, 0.5)).astype(np.float64)


def arm_metrics(
    rows: list[dict[str, Any]], arm_margins: dict[str, np.ndarray], dev_relative: np.ndarray
) -> tuple[dict[str, dict[str, Any]], list[dict[str, Any]], dict[str, dict[str, float]]]:
    by_parent: dict[tuple[str, str], list[int]] = defaultdict(list)
    for index, row in enumerate(rows):
        by_parent[(row["task"], row["parent"])].append(index)
    tasks = sorted({row["task"] for row in rows})
    output: dict[str, dict[str, Any]] = {}
    task_rows: list[dict[str, Any]] = []
    task_values: dict[str, dict[str, float]] = {arm: {} for arm in ARM_ORDER}
    clipped_gap = np.clip(dev_relative, 0.25, 4.0)
    for arm in ARM_ORDER:
        arm_credit = credits(arm_margins[arm])
        per_task_primary: dict[str, list[float]] = defaultdict(list)
        per_task_weighted: dict[str, list[float]] = defaultdict(list)
        per_task_pairs: dict[str, int] = defaultdict(int)
        for (task, _parent), indices_list in sorted(by_parent.items()):
            indices = np.asarray(indices_list, dtype=np.int64)
            per_task_primary[task].append(float(np.mean(arm_credit[indices])))
            per_task_weighted[task].append(float(np.average(arm_credit[indices], weights=clipped_gap[indices])))
            per_task_pairs[task] += len(indices_list)
        task_primary = {task: float(np.mean(per_task_primary[task])) for task in tasks}
        task_weighted = {task: float(np.mean(per_task_weighted[task])) for task in tasks}
        task_values[arm] = task_primary
        output[arm] = {
            "pairs": len(rows),
            "parents": len(by_parent),
            "tasks": len(tasks),
            "pair_micro_accuracy": float(np.mean(arm_credit)),
            "task_macro_parent_macro_accuracy": float(np.mean(list(task_primary.values()))),
            "task_macro_parent_macro_relative_gap_weighted_accuracy": float(np.mean(list(task_weighted.values()))),
            "prediction_ties": int(np.sum(arm_margins[arm] == 0)),
        }
        for task in tasks:
            task_rows.append(
                {
                    "arm": arm,
                    "task": task,
                    "pairs": per_task_pairs[task],
                    "parents": len(per_task_primary[task]),
                    "parent_macro_accuracy": task_primary[task],
                    "parent_macro_relative_gap_weighted_accuracy": task_weighted[task],
                }
            )
    return output, task_rows, task_values


def primary_contrast(
    task_values: dict[str, dict[str, float]], contract: dict[str, Any], parent_counts: dict[str, int]
) -> dict[str, Any]:
    tasks = sorted(task_values["binary_bt"])
    if tasks != sorted(task_values["gap_weighted_bt"]) or tasks != sorted(task_values["gap_permuted_bt"]):
        raise QualificationError("primary arm task pools differ")
    bootstrap = contract["evaluation"]["bootstrap"]
    support_contract = contract["evaluation"]["support_gate"]
    total_parents = sum(parent_counts.values())
    dominant_share = max(parent_counts.values()) / total_parents
    support = {
        "dev_tasks": len(tasks),
        "dev_parents": total_parents,
        "dominant_task_parent_share": dominant_share,
        "dev_tasks_pass": len(tasks) >= support_contract["dev_tasks_minimum"],
        "dev_parents_pass": total_parents >= support_contract["dev_parents_minimum"],
        "dominant_task_parent_share_pass": dominant_share <= support_contract["dominant_task_parent_share_maximum"],
        "train_dev_pair_overlap_pass": True,
        "train_dev_endpoint_overlap_pass": True,
    }
    support["all_pass"] = all(value for key, value in support.items() if key.endswith("_pass"))

    def effect_against(comparator: str, gate: dict[str, Any], strict_point: bool) -> dict[str, Any]:
        deltas = np.asarray(
            [task_values["gap_weighted_bt"][task] - task_values[comparator][task] for task in tasks],
            dtype=np.float64,
        )
        point = float(np.mean(deltas))
        rng = np.random.default_rng(bootstrap["seed"])
        sampled = rng.integers(0, len(tasks), size=(bootstrap["replicates"], len(tasks)))
        estimates = np.mean(deltas[sampled], axis=1)
        low, high = np.quantile(estimates, [0.025, 0.975], method="linear")
        loto = {task: float(np.mean(np.delete(deltas, index))) for index, task in enumerate(tasks)}
        positive_fraction = float(np.mean(deltas > 0))
        point_pass = point > gate["point_delta_gt"] if strict_point else point >= gate["point_delta_gte"]
        effect = {
            "candidate": "gap_weighted_bt",
            "comparator": comparator,
            "point_delta": point,
            "task_bootstrap_ci95": [float(low), float(high)],
            "leave_one_task_out_min": min(loto.values()),
            "leave_one_task_out": loto,
            "tasks_with_positive_delta": int(np.sum(deltas > 0)),
            "tasks_with_zero_delta": int(np.sum(deltas == 0)),
            "tasks_with_negative_delta": int(np.sum(deltas < 0)),
            "tasks_with_positive_delta_fraction": positive_fraction,
            "point_gate_pass": point_pass,
            "ci_gate_pass": float(low) > gate["bootstrap_ci95_low_gt"],
            "loto_gate_pass": min(loto.values()) > gate["leave_one_task_out_min_gt"],
            "positive_task_fraction_gate_pass": positive_fraction >= gate["tasks_with_positive_delta_fraction_gte"],
        }
        effect["all_pass"] = all(value for key, value in effect.items() if key.endswith("_pass"))
        return effect

    binary_effect = effect_against("binary_bt", contract["evaluation"]["primary_positive_gate"], False)
    control_effect = effect_against(
        "gap_permuted_bt", contract["evaluation"]["primary_gap_information_control_gate"], True
    )
    return {
        "support": support,
        "gap_weighted_minus_binary": binary_effect,
        "gap_weighted_minus_gap_permuted": control_effect,
        "all_pass": support["all_pass"] and binary_effect["all_pass"] and control_effect["all_pass"],
    }


def write_csv(path: Path, fieldnames: list[str], rows: list[dict[str, Any]]) -> None:
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames, lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)


def analyze(cards_path: Path, train_path: Path, dev_path: Path, output: Path, contract_path: Path) -> dict[str, Any]:
    contract = load_contract(contract_path)
    if output.exists() or output.is_symlink():
        raise QualificationError("output path already exists")
    train = read_pairs(train_path, contract["inputs"]["train"], "train")
    dev = read_pairs(dev_path, contract["inputs"]["dev"], "dev")
    needed = {endpoint for row in train + dev for endpoint in (row["better"], row["worse"])}
    codes, runs, configs, card_inventory = load_codes(cards_path, contract["inputs"]["cards"], needed)
    integrity = validate_integrity(train, dev, runs, configs)
    scales = task_scales(train)
    dev_relative = relative_gaps(dev, scales)
    margins, fit_diagnostics = fit_models(codes, train, dev, scales)
    metrics, task_rows, task_values = arm_metrics(dev, margins, dev_relative)
    parent_counts: dict[str, int] = defaultdict(int)
    for task, parent in {(row["task"], row["parent"]) for row in dev}:
        parent_counts[task] += 1
    contrast = primary_contrast(task_values, contract, dict(parent_counts))
    if integrity["overlap"]["pairs"] != 0 or integrity["overlap"]["endpoints"] != 0:
        raise QualificationError("support overlap invariant changed")
    status = (
        "RETROSPECTIVE_DEV_GAP_AWARE_QUALIFIED_FOR_FUTURE"
        if contrast["all_pass"]
        else "RETROSPECTIVE_DEV_GAP_AWARE_NO_UNLOCK"
    )
    summary = {
        "protocol": PROTOCOL,
        "contract_sha256": CONTRACT_SHA256,
        "status": status,
        "claim_boundary": contract["claim_boundary"],
        "inputs": {
            "cards_sha256": sha256_file(cards_path),
            "train_sha256": sha256_file(train_path),
            "dev_sha256": sha256_file(dev_path),
        },
        "resources": {
            "gpu_jobs": 0,
            "api_calls": 0,
            "base_llm_updates": 0,
            "cpu_fits": fit_diagnostics["fits"],
            "outer_test_pair_path_accepted_by_cli": False,
            "future_truth_path_accepted_by_cli": False,
        },
        "card_inventory": card_inventory,
        "integrity": integrity,
        "train_task_scale": {
            "tasks": len(scales),
            "minimum": min(scales.values()),
            "median": float(np.median(np.asarray(list(scales.values()), dtype=np.float64))),
            "maximum": max(scales.values()),
        },
        "fit_diagnostics": fit_diagnostics,
        "arm_metrics": metrics,
        "primary": contrast,
        "gap_ridge_may_rescue_primary": False,
    }
    output.mkdir(parents=True)
    (output / "summary.json").write_bytes(canonical(summary))
    arm_rows = [{"arm": arm, **metrics[arm]} for arm in ARM_ORDER]
    write_csv(
        output / "arm_metrics.csv",
        [
            "arm", "pairs", "parents", "tasks", "pair_micro_accuracy",
            "task_macro_parent_macro_accuracy", "task_macro_parent_macro_relative_gap_weighted_accuracy", "prediction_ties",
        ],
        arm_rows,
    )
    write_csv(
        output / "task_metrics.csv",
        ["arm", "task", "pairs", "parents", "parent_macro_accuracy", "parent_macro_relative_gap_weighted_accuracy"],
        sorted(task_rows, key=lambda row: (ARM_ORDER.index(row["arm"]), row["task"])),
    )
    with (output / "task_scales.csv").open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=["task", "train_gap_q75"], lineterminator="\n")
        writer.writeheader()
        for task in sorted(scales):
            writer.writerow({"task": task, "train_gap_q75": scales[task]})
    with (output / "per_pair.jsonl").open("w", encoding="utf-8", newline="") as handle:
        for index, row in enumerate(dev):
            record = {
                "pair_id": pair_id(row),
                "task": row["task"],
                "parent": row["parent"],
                "better": row["better"],
                "worse": row["worse"],
                "left": min(row["better"], row["worse"]),
                "right": max(row["better"], row["worse"]),
                "gap_raw": float(row["gap_raw"]),
                "train_task_gap_q75": scales[row["task"]],
                "task_relative_gap": float(dev_relative[index]),
                "better_minus_worse_margins": {arm: float(margins[arm][index]) for arm in ARM_ORDER},
                "credits": {arm: float(credits(margins[arm])[index]) for arm in ARM_ORDER},
            }
            handle.write(compact(record) + "\n")
    files = ["summary.json", "arm_metrics.csv", "task_metrics.csv", "task_scales.csv", "per_pair.jsonl"]
    manifest = {
        "protocol": PROTOCOL,
        "files": {name: {"bytes": (output / name).stat().st_size, "sha256": sha256_file(output / name)} for name in files},
    }
    (output / "artifact_manifest.json").write_bytes(canonical(manifest))
    return summary


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("cards", type=Path)
    parser.add_argument("train", type=Path)
    parser.add_argument("dev", type=Path)
    parser.add_argument("output", type=Path)
    parser.add_argument("--contract", type=Path, required=True)
    args = parser.parse_args()
    summary = analyze(args.cards, args.train, args.dev, args.output, args.contract)
    print(summary["status"])


if __name__ == "__main__":
    main()
