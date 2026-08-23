"""Independent source-refit verifier for the gap-aware train/dev qualification.

The command line accepts only the frozen Cards source, component-clean train/dev
pair sources, the producer bundle, and a verification receipt destination.  It has
no argument for an outer test set, a prospective cohort, or a truth vault.
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
from typing import Any, Mapping

import numpy as np
from scipy import sparse
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.linear_model import LogisticRegression, Ridge


PROTOCOL = "critic-gap-aware-train-dev-qualification-v1"
CONTRACT_SHA256 = "f411c0f732df12158e8c683ddbb94cea107d7673b40b8305ee5b83c8219ef4f8"
ARM_ORDER = ("binary_bt", "gap_permuted_bt", "gap_weighted_bt", "gap_ridge")
PERMUTATION_SEED = 20260902
SOURCE: dict[str, dict[str, Any]] = {
    "cards": {
        "sha256": "5fd24c8e545a67e1048f8a67b23bcb64605b9ad584a4fbaa44aa1b1f1b6e1afb",
        "bytes": 604190866,
    },
    "train": {
        "sha256": "0ec49d76a896accf8e85a2556ca7ed12b9379b1867247d99c6be5e4c83bea98e",
        "bytes": 3208089,
        "rows": 4689,
    },
    "dev": {
        "sha256": "3b3fb53f84277e935c66d3b3d1646d7a7d33624fb916e3f9bcc15f689904cfa4",
        "bytes": 376635,
        "rows": 551,
    },
}
OUTPUT_FILES = {
    "summary.json",
    "arm_metrics.csv",
    "task_metrics.csv",
    "task_scales.csv",
    "per_pair.jsonl",
    "artifact_manifest.json",
}
MANIFESTED_FILES = OUTPUT_FILES - {"artifact_manifest.json"}
ARM_FIELDS = [
    "arm",
    "pairs",
    "parents",
    "tasks",
    "pair_micro_accuracy",
    "task_macro_parent_macro_accuracy",
    "task_macro_parent_macro_relative_gap_weighted_accuracy",
    "prediction_ties",
]
TASK_FIELDS = [
    "arm",
    "task",
    "pairs",
    "parents",
    "parent_macro_accuracy",
    "parent_macro_relative_gap_weighted_accuracy",
]
SCALE_FIELDS = ["task", "train_gap_q75"]

EXPECTED_RESOURCES = {
    "api_calls": 0,
    "base_llm_updates": 0,
    "gpu_jobs": 0,
    "maximum_unique_cpu_fits_per_implementation": 4,
    "threads_per_fit": 1,
}
EXPECTED_SHARED_MODEL = {
    "code_prefix_chars": 20000,
    "lr_C": 0.5,
    "lr_max_iter": 1500,
    "lr_random_state": 0,
    "lr_solver": "lbfgs",
    "margin_excludes_intercept": True,
    "tfidf_analyzer": "char_wb",
    "tfidf_dtype": "float64",
    "tfidf_fit_population": "unique train endpoints only",
    "tfidf_max_features": 30000,
    "tfidf_min_df": 3,
    "tfidf_ngram_range": [3, 5],
    "tfidf_sublinear_tf": True,
}
EXPECTED_BOOTSTRAP = {
    "cluster": "task",
    "quantile_method": "linear_type7",
    "replicates": 20000,
    "seed": 20260901,
}
EXPECTED_CREDIT = {"negative_margin": 0.0, "positive_margin": 1.0, "zero_margin": 0.5}
EXPECTED_SUPPORT_GATE = {
    "dev_parents_minimum": 200,
    "dev_tasks_minimum": 20,
    "dominant_task_parent_share_maximum": 0.2,
    "train_dev_endpoint_overlap": 0,
    "train_dev_pair_overlap": 0,
}
EXPECTED_POSITIVE_GATE = {
    "bootstrap_ci95_low_gt": 0.0,
    "leave_one_task_out_min_gt": 0.0,
    "point_delta_gte": 0.015,
    "tasks_with_positive_delta_fraction_gte": 0.6,
}
EXPECTED_CONTROL_GATE = {
    "bootstrap_ci95_low_gt": 0.0,
    "leave_one_task_out_min_gt": 0.0,
    "point_delta_gt": 0.0,
    "tasks_with_positive_delta_fraction_gte": 0.6,
}


class VerificationError(RuntimeError):
    """Raised when independent reconstruction disagrees with an input or bundle."""


def canonical_bytes(value: Any) -> bytes:
    return (json.dumps(value, indent=2, sort_keys=True, ensure_ascii=False) + "\n").encode("utf-8")


def compact(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _source_receipt(source: Mapping[str, Mapping[str, Any]], role: str) -> dict[str, Any]:
    try:
        receipt = dict(source[role])
    except (KeyError, TypeError) as error:
        raise VerificationError(f"missing frozen {role} identity") from error
    required = {"sha256", "bytes"} | ({"rows"} if role in {"train", "dev"} else set())
    if set(receipt) != required:
        raise VerificationError(f"invalid frozen {role} identity schema")
    if (
        not isinstance(receipt["sha256"], str)
        or re.fullmatch(r"[0-9a-f]{64}", receipt["sha256"]) is None
        or not isinstance(receipt["bytes"], int)
        or isinstance(receipt["bytes"], bool)
        or receipt["bytes"] <= 0
        or ("rows" in receipt and (not isinstance(receipt["rows"], int) or receipt["rows"] <= 0))
    ):
        raise VerificationError(f"invalid frozen {role} identity value")
    return receipt


def _assert_contract_semantics(contract: dict[str, Any], source: Mapping[str, Mapping[str, Any]]) -> None:
    if contract.get("protocol") != PROTOCOL:
        raise VerificationError("contract protocol mismatch")
    if contract.get("status") != "PREREGISTERED_BEFORE_ANY_GAP_AWARE_MODEL_FIT":
        raise VerificationError("contract status mismatch")
    if contract.get("resources") != EXPECTED_RESOURCES:
        raise VerificationError("contract resource boundary mismatch")
    models = contract.get("models")
    if not isinstance(models, dict) or models.get("shared") != EXPECTED_SHARED_MODEL:
        raise VerificationError("contract shared-model definition mismatch")
    if models.get("binary_bt") != {"fit": "mirrored logistic regression with hard labels", "role": "fixed baseline"}:
        raise VerificationError("contract binary arm mismatch")
    if models.get("gap_weighted_bt") != {
        "fit": "mirrored logistic regression with hard labels and task-mass-preserving sample weights",
        "role": "sole primary candidate",
        "sample_weight": "clip(gap_raw / train-task-q75, 0.25, 4.0), then divide by the mean clipped weight within each train task",
    }:
        raise VerificationError("contract weighted arm mismatch")
    if models.get("gap_permuted_bt") != {
        "fit": "mirrored logistic regression using the exact gap_weighted_bt weight multiset within each task after an orientation-independent hash-ordered cyclic shift by one row",
        "permutation_seed": PERMUTATION_SEED,
        "role": "mandatory gap-information negative control; cannot be omitted or used as a rescue",
    }:
        raise VerificationError("contract permuted-control arm mismatch")
    if models.get("gap_ridge") != {
        "alpha": 1.0,
        "fit": "mirrored sparse ridge without intercept",
        "role": "non-rescuing mechanistic diagnostic",
        "solver": "lsqr",
        "target": "signed log1p(gap_raw / train-task-q75)",
    }:
        raise VerificationError("contract ridge arm mismatch")
    task_scale = contract.get("task_scale")
    if task_scale != {
        "definition": "numpy linear/type-7 0.75 quantile of positive gap_raw within each train task",
        "dev_only_task_policy": "fail closed",
        "minimum": 0.0,
        "source": "train rows only",
    }:
        raise VerificationError("contract task-scale definition mismatch")
    evaluation = contract.get("evaluation")
    if not isinstance(evaluation, dict):
        raise VerificationError("contract evaluation schema mismatch")
    if evaluation.get("bootstrap") != EXPECTED_BOOTSTRAP or evaluation.get("credit") != EXPECTED_CREDIT:
        raise VerificationError("contract inference primitive mismatch")
    if evaluation.get("support_gate") != EXPECTED_SUPPORT_GATE:
        raise VerificationError("contract support gate mismatch")
    if evaluation.get("primary_positive_gate") != EXPECTED_POSITIVE_GATE:
        raise VerificationError("contract positive gate mismatch")
    if evaluation.get("primary_gap_information_control_gate") != EXPECTED_CONTROL_GATE:
        raise VerificationError("contract control gate mismatch")
    if evaluation.get("primary_contrasts") != [
        "gap_weighted_bt_minus_binary_bt",
        "gap_weighted_bt_minus_gap_permuted_bt",
    ]:
        raise VerificationError("contract primary contrasts mismatch")
    claim = contract.get("claim_boundary")
    if not isinstance(claim, dict) or claim.get("gap_ridge_may_rescue_primary") is not False:
        raise VerificationError("contract rescue boundary mismatch")
    inputs = contract.get("inputs")
    if not isinstance(inputs, dict) or set(inputs) != {"cards", "train", "dev"}:
        raise VerificationError("contract input schema mismatch")
    for role in ("cards", "train", "dev"):
        frozen = _source_receipt(source, role)
        declared = inputs.get(role)
        if not isinstance(declared, dict):
            raise VerificationError(f"contract {role} input schema mismatch")
        for field in ("sha256", "bytes"):
            if declared.get(field) != frozen[field]:
                raise VerificationError(f"contract {role} identity mismatch")
        if role != "cards" and declared.get("rows") != frozen["rows"]:
            raise VerificationError(f"contract {role} row count mismatch")


def load_contract(
    path: Path,
    expected_sha256: str = CONTRACT_SHA256,
    source: Mapping[str, Mapping[str, Any]] = SOURCE,
) -> dict[str, Any]:
    if not path.is_file() or sha256_file(path) != expected_sha256:
        raise VerificationError("contract identity mismatch")
    try:
        contract = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as error:
        raise VerificationError("contract parse failure") from error
    if not isinstance(contract, dict):
        raise VerificationError("contract root schema mismatch")
    _assert_contract_semantics(contract, source)
    return contract


def attest_source(path: Path, role: str, source: Mapping[str, Mapping[str, Any]]) -> None:
    receipt = _source_receipt(source, role)
    if (
        not path.is_file()
        or path.stat().st_size != receipt["bytes"]
        or sha256_file(path) != receipt["sha256"]
    ):
        raise VerificationError(f"{role} input identity mismatch")


def unordered_key(row: Mapping[str, Any]) -> tuple[str, str, str, str]:
    try:
        better = row["better"]
        worse = row["worse"]
        left, right = sorted((better, worse))
        values = row["task"], row["parent"], left, right
    except (KeyError, TypeError, ValueError) as error:
        raise VerificationError("invalid pair identity schema") from error
    if not all(isinstance(value, str) and value for value in values) or left == right:
        raise VerificationError("invalid pair identity value")
    return values


def pair_identifier(row: Mapping[str, Any]) -> str:
    return hashlib.sha256(compact(unordered_key(row)).encode("utf-8")).hexdigest()


def read_pair_source(
    path: Path,
    role: str,
    source: Mapping[str, Mapping[str, Any]],
) -> list[dict[str, Any]]:
    attest_source(path, role, source)
    expected_rows = _source_receipt(source, role)["rows"]
    try:
        lines = path.read_text(encoding="utf-8").splitlines()
    except (OSError, UnicodeDecodeError) as error:
        raise VerificationError(f"{role} input decode failure") from error
    rows: list[dict[str, Any]] = []
    identities: set[tuple[str, str, str, str]] = set()
    for line_number, line in enumerate(lines, 1):
        if not line:
            raise VerificationError(f"blank {role} row")
        try:
            row = json.loads(line)
        except json.JSONDecodeError as error:
            raise VerificationError(f"invalid {role} JSON at row {line_number}") from error
        if not isinstance(row, dict):
            raise VerificationError(f"non-object {role} row")
        key = unordered_key(row)
        if key in identities:
            raise VerificationError(f"duplicate unordered pair in {role}")
        identities.add(key)
        gap = row.get("gap_raw")
        component = row.get("pair_component_id")
        if (
            row.get("intask_split") != "train"
            or row.get("outer_intask_split") != "train"
            or row.get("train_dev_protocol") != "pair-graph-component-train-dev-split-v1"
            or row.get("train_dev_seed") != 20260821
            or row.get("train_dev_target_numerator") != 1
            or row.get("train_dev_target_denominator") != 10
            or row.get("src") != "decision"
            or not isinstance(gap, (int, float))
            or isinstance(gap, bool)
            or not math.isfinite(float(gap))
            or float(gap) <= 0.0
            or not isinstance(component, str)
            or re.fullmatch(r"[0-9a-f]{64}", component) is None
        ):
            raise VerificationError(f"invalid component-clean schema in {role}")
        rows.append(row)
    if len(rows) != expected_rows:
        raise VerificationError(f"{role} row-count mismatch")
    return rows


def read_card_projection(
    path: Path,
    needed: set[str],
    source: Mapping[str, Mapping[str, Any]],
) -> tuple[dict[str, str], dict[str, str], dict[str, tuple[Any, ...]], dict[str, int]]:
    attest_source(path, "cards", source)
    try:
        grouped = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as error:
        raise VerificationError("cards input parse failure") from error
    if not isinstance(grouped, dict):
        raise VerificationError("cards root is not grouped by physical run")
    codes: dict[str, str] = {}
    runs: dict[str, str] = {}
    configs: dict[str, tuple[Any, ...]] = {}
    seen: set[str] = set()
    total_cards = 0
    for run_id in sorted(grouped):
        cards = grouped[run_id]
        if not isinstance(run_id, str) or not run_id or not isinstance(cards, list):
            raise VerificationError("invalid cards run group")
        for card in cards:
            total_cards += 1
            if not isinstance(card, dict) or not isinstance(card.get("id"), str) or card["id"] in seen:
                raise VerificationError("invalid or duplicate card")
            card_id = card["id"]
            seen.add(card_id)
            if card_id not in needed:
                continue
            task_object = card.get("task")
            task = task_object.get("name") if isinstance(task_object, dict) else None
            config = (
                task,
                card.get("client"),
                card.get("hardware"),
                card.get("time_limit"),
                card.get("execution_timeout"),
            )
            if (
                not isinstance(card.get("code"), str)
                or not all(isinstance(value, str) and value for value in config[:3])
                or not all(isinstance(value, int) and not isinstance(value, bool) for value in config[3:])
            ):
                raise VerificationError("needed card projection schema mismatch")
            codes[card_id] = card["code"]
            runs[card_id] = run_id
            configs[card_id] = config
    if set(codes) != needed:
        raise VerificationError("pair endpoint missing from cards")
    inventory = {"cards": total_cards, "run_groups": len(grouped), "needed_cards": len(needed)}
    return codes, runs, configs, inventory


def validate_train_dev_integrity(
    train: list[dict[str, Any]],
    dev: list[dict[str, Any]],
    runs: Mapping[str, str],
    configs: Mapping[str, tuple[Any, ...]],
) -> dict[str, Any]:
    pools = {"train": train, "dev": dev}
    keys = {split: {unordered_key(row) for row in rows} for split, rows in pools.items()}
    endpoints = {
        split: {endpoint for row in rows for endpoint in (row["better"], row["worse"])}
        for split, rows in pools.items()
    }
    run_sets = {split: {runs[endpoint] for endpoint in values} for split, values in endpoints.items()}
    components = {split: {row["pair_component_id"] for row in rows} for split, rows in pools.items()}
    overlap = {
        "pairs": len(keys["train"] & keys["dev"]),
        "endpoints": len(endpoints["train"] & endpoints["dev"]),
        "physical_runs": len(run_sets["train"] & run_sets["dev"]),
        "components": len(components["train"] & components["dev"]),
    }
    if any(overlap.values()):
        raise VerificationError("train/dev leakage")
    component_owner: dict[str, tuple[str, str]] = {}
    for split, rows in pools.items():
        for row in rows:
            if configs[row["better"]] != configs[row["worse"]] or configs[row["better"]][0] != row["task"]:
                raise VerificationError("pair violates exact task/config matching")
            owner = (split, row["task"])
            component = row["pair_component_id"]
            if component in component_owner and component_owner[component] != owner:
                raise VerificationError("comparison component crosses split or task")
            component_owner[component] = owner
    return {
        "overlap": overlap,
        "pairs": {split: len(rows) for split, rows in pools.items()},
        "endpoints": {split: len(values) for split, values in endpoints.items()},
        "physical_runs": {split: len(values) for split, values in run_sets.items()},
        "components": {split: len(values) for split, values in components.items()},
    }


def recompute_task_scales(rows: list[dict[str, Any]]) -> dict[str, float]:
    grouped: dict[str, list[float]] = defaultdict(list)
    for row in rows:
        grouped[row["task"]].append(float(row["gap_raw"]))
    scales = {
        task: float(np.quantile(np.asarray(values, dtype=np.float64), 0.75, method="linear"))
        for task, values in sorted(grouped.items())
    }
    if not scales or any(not math.isfinite(value) or value <= 0.0 for value in scales.values()):
        raise VerificationError("invalid train-only task q75")
    return scales


def relative_gap_vector(rows: list[dict[str, Any]], scales: Mapping[str, float]) -> np.ndarray:
    try:
        values = np.fromiter(
            (float(row["gap_raw"]) / scales[row["task"]] for row in rows),
            dtype=np.float64,
            count=len(rows),
        )
    except KeyError as error:
        raise VerificationError("dev-only task lacks train q75") from error
    if values.shape != (len(rows),) or not np.isfinite(values).all() or np.any(values <= 0.0):
        raise VerificationError("invalid task-relative gap")
    return values


def recompute_task_mass_weights(rows: list[dict[str, Any]], relative: np.ndarray) -> np.ndarray:
    if relative.shape != (len(rows),):
        raise VerificationError("relative-gap shape mismatch")
    weights = np.clip(relative, 0.25, 4.0).astype(np.float64, copy=True)
    task_indices: dict[str, list[int]] = defaultdict(list)
    for index, row in enumerate(rows):
        task_indices[row["task"]].append(index)
    for task in sorted(task_indices):
        indices = np.asarray(task_indices[task], dtype=np.int64)
        mean = float(np.mean(weights[indices]))
        if not math.isfinite(mean) or mean <= 0.0:
            raise VerificationError("invalid clipped task weight mean")
        weights[indices] /= mean
    if not np.isfinite(weights).all() or np.any(weights <= 0.0):
        raise VerificationError("invalid task-mass-preserving weight")
    for task in sorted(task_indices):
        indices = np.asarray(task_indices[task], dtype=np.int64)
        if abs(float(np.mean(weights[indices])) - 1.0) > 1e-12:
            raise VerificationError("task training mass was not preserved")
    return weights


def independently_permute_task_weights(
    rows: list[dict[str, Any]], weights: np.ndarray
) -> np.ndarray:
    """Apply the frozen orientation-blind, task-local one-step cyclic shift."""
    if weights.shape != (len(rows),) or not np.isfinite(weights).all():
        raise VerificationError("permuted-control weight shape mismatch")
    output = np.empty_like(weights)
    task_indices: dict[str, list[int]] = defaultdict(list)
    for index, row in enumerate(rows):
        task_indices[row["task"]].append(index)
    for task in sorted(task_indices):
        ordered = sorted(
            task_indices[task],
            key=lambda index: hashlib.sha256(
                f"{PERMUTATION_SEED}|{compact(unordered_key(rows[index]))}".encode("utf-8")
            ).hexdigest(),
        )
        if len(ordered) < 2:
            raise VerificationError("task cannot support cyclic weight control")
        for position, destination in enumerate(ordered):
            output[destination] = weights[ordered[(position + 1) % len(ordered)]]
        task_original = weights[np.asarray(ordered, dtype=np.int64)]
        task_permuted = output[np.asarray(ordered, dtype=np.int64)]
        if not np.array_equal(np.sort(task_original), np.sort(task_permuted)):
            raise VerificationError("permuted control changed task weight multiset")
    if not np.isfinite(output).all():
        raise VerificationError("invalid permuted-control weights")
    return output


def _endpoint_indices(
    rows: list[dict[str, Any]], positions: Mapping[str, int]
) -> tuple[np.ndarray, np.ndarray]:
    return (
        np.fromiter((positions[row["better"]] for row in rows), dtype=np.int64, count=len(rows)),
        np.fromiter((positions[row["worse"]] for row in rows), dtype=np.int64, count=len(rows)),
    )


def independently_refit_four_arms(
    codes: Mapping[str, str],
    train: list[dict[str, Any]],
    dev: list[dict[str, Any]],
    scales: Mapping[str, float],
) -> tuple[dict[str, np.ndarray], dict[str, Any]]:
    train_endpoints = sorted({endpoint for row in train for endpoint in (row["better"], row["worse"])})
    all_endpoints = sorted(
        set(train_endpoints) | {endpoint for row in dev for endpoint in (row["better"], row["worse"])}
    )
    positions = {card_id: index for index, card_id in enumerate(all_endpoints)}
    encoder = TfidfVectorizer(
        analyzer="char_wb",
        ngram_range=(3, 5),
        min_df=3,
        max_features=30000,
        sublinear_tf=True,
        dtype=np.float64,
    )
    encoder.fit([codes[card_id][:20000] for card_id in train_endpoints])
    matrix = encoder.transform([codes[card_id][:20000] for card_id in all_endpoints])
    train_better, train_worse = _endpoint_indices(train, positions)
    dev_better, dev_worse = _endpoint_indices(dev, positions)
    train_difference = sparse.csr_matrix(matrix[train_better] - matrix[train_worse])
    dev_difference = sparse.csr_matrix(matrix[dev_better] - matrix[dev_worse])
    mirrored = sparse.vstack((train_difference, -train_difference), format="csr")
    labels = np.concatenate((np.ones(len(train), dtype=np.int8), np.zeros(len(train), dtype=np.int8)))

    binary = LogisticRegression(C=0.5, max_iter=1500, solver="lbfgs", random_state=0).fit(mirrored, labels)
    train_relative = relative_gap_vector(train, scales)
    train_weights = recompute_task_mass_weights(train, train_relative)
    permuted_weights = independently_permute_task_weights(train, train_weights)
    weighted = LogisticRegression(C=0.5, max_iter=1500, solver="lbfgs", random_state=0).fit(
        mirrored,
        labels,
        sample_weight=np.concatenate((train_weights, train_weights)),
    )
    permuted = LogisticRegression(C=0.5, max_iter=1500, solver="lbfgs", random_state=0).fit(
        mirrored,
        labels,
        sample_weight=np.concatenate((permuted_weights, permuted_weights)),
    )
    signed_strength = np.log1p(train_relative)
    ridge = Ridge(alpha=1.0, fit_intercept=False, solver="lsqr", tol=1e-6).fit(
        mirrored,
        np.concatenate((signed_strength, -signed_strength)),
    )
    fitted = {
        "binary_bt": binary,
        "gap_permuted_bt": permuted,
        "gap_weighted_bt": weighted,
        "gap_ridge": ridge,
    }
    coefficients: dict[str, np.ndarray] = {}
    for arm, model in fitted.items():
        coefficient = np.asarray(model.coef_, dtype=np.float64).reshape(-1)
        if coefficient.shape != (matrix.shape[1],) or not np.isfinite(coefficient).all():
            raise VerificationError(f"invalid independent {arm} coefficient")
        coefficients[arm] = coefficient
    for arm in ("binary_bt", "gap_permuted_bt", "gap_weighted_bt"):
        iterations = np.asarray(fitted[arm].n_iter_)
        if iterations.size != 1 or int(iterations[0]) >= 1500:
            raise VerificationError(f"independent {arm} refit did not converge")

    margins: dict[str, np.ndarray] = {}
    anti_symmetry: dict[str, float] = {}
    for arm in ARM_ORDER:
        forward = np.asarray(dev_difference.dot(coefficients[arm]), dtype=np.float64).reshape(-1)
        reverse = np.asarray((-dev_difference).dot(coefficients[arm]), dtype=np.float64).reshape(-1)
        if forward.shape != (len(dev),) or not np.isfinite(forward).all():
            raise VerificationError(f"invalid independent {arm} dev margins")
        anti_symmetry[arm] = float(np.max(np.abs(forward + reverse))) if len(forward) else 0.0
        if anti_symmetry[arm] > 1e-12:
            raise VerificationError(f"independent {arm} margin is not antisymmetric")
        margins[arm] = forward
    diagnostics = {
        "tfidf_features": int(matrix.shape[1]),
        "tfidf_train_fit_endpoints": len(train_endpoints),
        "transformed_endpoints": len(all_endpoints),
        "train_weight_min": float(np.min(train_weights)),
        "train_weight_max": float(np.max(train_weights)),
        "train_weight_mean": float(np.mean(train_weights)),
        "permuted_weight_equal_value_fraction": float(np.mean(permuted_weights == train_weights)),
        "permuted_weight_multiset_exact": bool(
            np.array_equal(np.sort(permuted_weights), np.sort(train_weights))
        ),
        "anti_symmetry_max_abs": anti_symmetry,
        "fits": len(ARM_ORDER),
    }
    return margins, diagnostics


def margin_credit(values: np.ndarray) -> np.ndarray:
    return np.where(values > 0.0, 1.0, np.where(values < 0.0, 0.0, 0.5)).astype(np.float64)


def recompute_arm_statistics(
    rows: list[dict[str, Any]],
    margins: Mapping[str, np.ndarray],
    dev_relative: np.ndarray,
) -> tuple[dict[str, dict[str, Any]], list[dict[str, Any]], dict[str, dict[str, float]]]:
    parent_indices: dict[tuple[str, str], list[int]] = defaultdict(list)
    for index, row in enumerate(rows):
        parent_indices[(row["task"], row["parent"])].append(index)
    tasks = sorted({row["task"] for row in rows})
    clipped_relative = np.clip(dev_relative, 0.25, 4.0)
    metrics: dict[str, dict[str, Any]] = {}
    task_rows: list[dict[str, Any]] = []
    primary_task_values: dict[str, dict[str, float]] = {arm: {} for arm in ARM_ORDER}
    for arm in ARM_ORDER:
        values = np.asarray(margins[arm], dtype=np.float64)
        if values.shape != (len(rows),):
            raise VerificationError(f"{arm} margin row-count mismatch")
        credits = margin_credit(values)
        parent_primary: dict[str, list[float]] = defaultdict(list)
        parent_weighted: dict[str, list[float]] = defaultdict(list)
        pair_counts: dict[str, int] = defaultdict(int)
        for (task, _parent), indices_list in sorted(parent_indices.items()):
            indices = np.asarray(indices_list, dtype=np.int64)
            parent_primary[task].append(float(np.mean(credits[indices])))
            parent_weighted[task].append(
                float(np.average(credits[indices], weights=clipped_relative[indices]))
            )
            pair_counts[task] += len(indices_list)
        task_primary = {task: float(np.mean(parent_primary[task])) for task in tasks}
        task_weighted = {task: float(np.mean(parent_weighted[task])) for task in tasks}
        primary_task_values[arm] = task_primary
        metrics[arm] = {
            "pairs": len(rows),
            "parents": len(parent_indices),
            "tasks": len(tasks),
            "pair_micro_accuracy": float(np.mean(credits)),
            "task_macro_parent_macro_accuracy": float(np.mean(list(task_primary.values()))),
            "task_macro_parent_macro_relative_gap_weighted_accuracy": float(
                np.mean(list(task_weighted.values()))
            ),
            "prediction_ties": int(np.sum(values == 0.0)),
        }
        for task in tasks:
            task_rows.append(
                {
                    "arm": arm,
                    "task": task,
                    "pairs": pair_counts[task],
                    "parents": len(parent_primary[task]),
                    "parent_macro_accuracy": task_primary[task],
                    "parent_macro_relative_gap_weighted_accuracy": task_weighted[task],
                }
            )
    return metrics, task_rows, primary_task_values


def recompute_primary(
    task_values: Mapping[str, Mapping[str, float]],
    parent_counts: Mapping[str, int],
) -> dict[str, Any]:
    tasks = sorted(task_values["binary_bt"])
    if (
        not tasks
        or tasks != sorted(task_values["gap_weighted_bt"])
        or tasks != sorted(task_values["gap_permuted_bt"])
    ):
        raise VerificationError("primary arm task pools differ")
    total_parents = sum(parent_counts.values())
    if total_parents <= 0 or set(parent_counts) != set(tasks):
        raise VerificationError("invalid dev parent support")
    dominant_share = max(parent_counts.values()) / total_parents
    support = {
        "dev_tasks": len(tasks),
        "dev_parents": total_parents,
        "dominant_task_parent_share": dominant_share,
        "dev_tasks_pass": len(tasks) >= EXPECTED_SUPPORT_GATE["dev_tasks_minimum"],
        "dev_parents_pass": total_parents >= EXPECTED_SUPPORT_GATE["dev_parents_minimum"],
        "dominant_task_parent_share_pass": (
            dominant_share <= EXPECTED_SUPPORT_GATE["dominant_task_parent_share_maximum"]
        ),
        "train_dev_pair_overlap_pass": True,
        "train_dev_endpoint_overlap_pass": True,
    }
    support["all_pass"] = all(value for key, value in support.items() if key.endswith("_pass"))

    def contrast(comparator: str, gate: Mapping[str, float], *, strict_point: bool) -> dict[str, Any]:
        deltas = np.asarray(
            [task_values["gap_weighted_bt"][task] - task_values[comparator][task] for task in tasks],
            dtype=np.float64,
        )
        generator = np.random.default_rng(EXPECTED_BOOTSTRAP["seed"])
        sampled = generator.integers(
            0,
            len(tasks),
            size=(EXPECTED_BOOTSTRAP["replicates"], len(tasks)),
        )
        estimates = np.mean(deltas[sampled], axis=1)
        low, high = np.quantile(estimates, [0.025, 0.975], method="linear")
        leave_one_out = {
            task: float(np.mean(np.delete(deltas, index)))
            for index, task in enumerate(tasks)
        }
        point = float(np.mean(deltas))
        positive_fraction = float(np.mean(deltas > 0.0))
        point_pass = (
            point > gate["point_delta_gt"]
            if strict_point
            else point >= gate["point_delta_gte"]
        )
        effect = {
            "candidate": "gap_weighted_bt",
            "comparator": comparator,
            "point_delta": point,
            "task_bootstrap_ci95": [float(low), float(high)],
            "leave_one_task_out_min": min(leave_one_out.values()),
            "leave_one_task_out": leave_one_out,
            "tasks_with_positive_delta": int(np.sum(deltas > 0.0)),
            "tasks_with_zero_delta": int(np.sum(deltas == 0.0)),
            "tasks_with_negative_delta": int(np.sum(deltas < 0.0)),
            "tasks_with_positive_delta_fraction": positive_fraction,
            "point_gate_pass": point_pass,
            "ci_gate_pass": float(low) > gate["bootstrap_ci95_low_gt"],
            "loto_gate_pass": min(leave_one_out.values()) > gate["leave_one_task_out_min_gt"],
            "positive_task_fraction_gate_pass": (
                positive_fraction >= gate["tasks_with_positive_delta_fraction_gte"]
            ),
        }
        effect["all_pass"] = all(value for key, value in effect.items() if key.endswith("_pass"))
        return effect

    binary_effect = contrast("binary_bt", EXPECTED_POSITIVE_GATE, strict_point=False)
    control_effect = contrast("gap_permuted_bt", EXPECTED_CONTROL_GATE, strict_point=True)
    return {
        "support": support,
        "gap_weighted_minus_binary": binary_effect,
        "gap_weighted_minus_gap_permuted": control_effect,
        "all_pass": support["all_pass"] and binary_effect["all_pass"] and control_effect["all_pass"],
    }


def reconstruct_expected_bundle(
    cards_path: Path,
    train_path: Path,
    dev_path: Path,
    contract_path: Path,
    *,
    expected_contract_sha256: str = CONTRACT_SHA256,
    source: Mapping[str, Mapping[str, Any]] = SOURCE,
) -> dict[str, Any]:
    contract = load_contract(contract_path, expected_contract_sha256, source)
    train = read_pair_source(train_path, "train", source)
    dev = read_pair_source(dev_path, "dev", source)
    needed = {endpoint for row in train + dev for endpoint in (row["better"], row["worse"])}
    codes, runs, configs, card_inventory = read_card_projection(cards_path, needed, source)
    integrity = validate_train_dev_integrity(train, dev, runs, configs)
    scales = recompute_task_scales(train)
    dev_relative = relative_gap_vector(dev, scales)
    margins, fit_diagnostics = independently_refit_four_arms(codes, train, dev, scales)
    arm_metrics, task_rows, task_values = recompute_arm_statistics(dev, margins, dev_relative)
    parent_counts: dict[str, int] = defaultdict(int)
    for task, _parent in {(row["task"], row["parent"]) for row in dev}:
        parent_counts[task] += 1
    primary = recompute_primary(task_values, parent_counts)
    status = (
        "RETROSPECTIVE_DEV_GAP_AWARE_QUALIFIED_FOR_FUTURE"
        if primary["all_pass"]
        else "RETROSPECTIVE_DEV_GAP_AWARE_NO_UNLOCK"
    )
    summary = {
        "protocol": PROTOCOL,
        "contract_sha256": expected_contract_sha256,
        "status": status,
        "claim_boundary": contract["claim_boundary"],
        "inputs": {
            "cards_sha256": _source_receipt(source, "cards")["sha256"],
            "train_sha256": _source_receipt(source, "train")["sha256"],
            "dev_sha256": _source_receipt(source, "dev")["sha256"],
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
        "arm_metrics": arm_metrics,
        "primary": primary,
        "gap_ridge_may_rescue_primary": False,
    }
    arm_rows = [{"arm": arm, **arm_metrics[arm]} for arm in ARM_ORDER]
    scale_rows = [{"task": task, "train_gap_q75": scales[task]} for task in sorted(scales)]
    pair_rows = []
    for index, row in enumerate(dev):
        pair_rows.append(
            {
                "pair_id": pair_identifier(row),
                "task": row["task"],
                "parent": row["parent"],
                "better": row["better"],
                "worse": row["worse"],
                "left": min(row["better"], row["worse"]),
                "right": max(row["better"], row["worse"]),
                "gap_raw": float(row["gap_raw"]),
                "train_task_gap_q75": scales[row["task"]],
                "task_relative_gap": float(dev_relative[index]),
                "better_minus_worse_margins": {
                    arm: float(margins[arm][index]) for arm in ARM_ORDER
                },
                "credits": {arm: float(margin_credit(margins[arm])[index]) for arm in ARM_ORDER},
            }
        )
    return {
        "summary": summary,
        "arm_rows": arm_rows,
        "task_rows": sorted(task_rows, key=lambda row: (ARM_ORDER.index(row["arm"]), row["task"])),
        "scale_rows": scale_rows,
        "pair_rows": pair_rows,
    }


def _json_object(path: Path, role: str) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as error:
        raise VerificationError(f"invalid {role} JSON") from error
    if not isinstance(value, dict):
        raise VerificationError(f"invalid {role} root schema")
    return value


def _jsonl_rows(path: Path, role: str) -> list[dict[str, Any]]:
    try:
        lines = path.read_text(encoding="utf-8").splitlines()
    except (OSError, UnicodeDecodeError) as error:
        raise VerificationError(f"invalid {role} encoding") from error
    rows: list[dict[str, Any]] = []
    for index, line in enumerate(lines, 1):
        if not line:
            raise VerificationError(f"blank {role} row")
        try:
            value = json.loads(line)
        except json.JSONDecodeError as error:
            raise VerificationError(f"invalid {role} JSON at row {index}") from error
        if not isinstance(value, dict):
            raise VerificationError(f"non-object {role} row")
        rows.append(value)
    return rows


def _csv_rows(path: Path, fields: list[str], role: str) -> list[dict[str, str]]:
    try:
        with path.open(encoding="utf-8", newline="") as handle:
            reader = csv.DictReader(handle)
            if reader.fieldnames != fields:
                raise VerificationError(f"{role} CSV schema mismatch")
            rows = list(reader)
    except (OSError, UnicodeDecodeError, csv.Error) as error:
        raise VerificationError(f"invalid {role} CSV") from error
    if any(None in row or any(value is None for value in row.values()) for row in rows):
        raise VerificationError(f"{role} CSV row schema mismatch")
    return rows


def _cast_csv_row(actual: dict[str, str], expected: Mapping[str, Any], role: str) -> dict[str, Any]:
    if set(actual) != set(expected):
        raise VerificationError(f"{role} CSV field mismatch")
    converted: dict[str, Any] = {}
    for key, expected_value in expected.items():
        try:
            if isinstance(expected_value, bool):
                if actual[key] not in {"True", "False"}:
                    raise ValueError("invalid boolean")
                converted[key] = actual[key] == "True"
            elif isinstance(expected_value, int):
                converted[key] = int(actual[key])
            elif isinstance(expected_value, float):
                converted[key] = float(actual[key])
            else:
                converted[key] = actual[key]
        except (TypeError, ValueError) as error:
            raise VerificationError(f"{role} CSV value type mismatch at {key}") from error
    return converted


def compare_values(expected: Any, observed: Any, location: str = "root") -> float:
    if isinstance(expected, dict):
        if not isinstance(observed, dict) or set(expected) != set(observed):
            raise VerificationError(f"mapping schema mismatch at {location}")
        return max(
            (compare_values(expected[key], observed[key], f"{location}.{key}") for key in expected),
            default=0.0,
        )
    if isinstance(expected, list):
        if not isinstance(observed, list) or len(expected) != len(observed):
            raise VerificationError(f"list schema mismatch at {location}")
        return max(
            (
                compare_values(left, right, f"{location}[{index}]")
                for index, (left, right) in enumerate(zip(expected, observed))
            ),
            default=0.0,
        )
    if isinstance(expected, bool):
        if observed is not expected:
            raise VerificationError(f"value mismatch at {location}")
        return 0.0
    if isinstance(expected, float):
        if not isinstance(observed, (int, float)) or isinstance(observed, bool):
            raise VerificationError(f"numeric type mismatch at {location}")
        observed_float = float(observed)
        if not math.isfinite(expected) or not math.isfinite(observed_float):
            raise VerificationError(f"non-finite numeric value at {location}")
        difference = abs(expected - observed_float)
        if not math.isclose(expected, observed_float, rel_tol=1e-10, abs_tol=1e-12):
            raise VerificationError(f"numeric mismatch at {location}: {difference}")
        return difference
    if isinstance(expected, int):
        if not isinstance(observed, int) or isinstance(observed, bool) or observed != expected:
            raise VerificationError(f"integer mismatch at {location}")
        return 0.0
    if observed != expected:
        raise VerificationError(f"value mismatch at {location}")
    return 0.0


def validate_output_bundle(artifact_dir: Path, expected: Mapping[str, Any]) -> dict[str, Any]:
    if artifact_dir.is_symlink() or not artifact_dir.is_dir():
        raise VerificationError("artifact directory is not an ordinary directory")
    members = list(artifact_dir.iterdir())
    if (
        {path.name for path in members} != OUTPUT_FILES
        or any(path.is_symlink() or not path.is_file() for path in members)
    ):
        raise VerificationError("artifact file set mismatch")
    manifest_path = artifact_dir / "artifact_manifest.json"
    manifest = _json_object(manifest_path, "artifact manifest")
    if set(manifest) != {"protocol", "files"} or manifest.get("protocol") != PROTOCOL:
        raise VerificationError("artifact manifest header mismatch")
    files = manifest.get("files")
    if not isinstance(files, dict) or set(files) != MANIFESTED_FILES:
        raise VerificationError("artifact manifest membership mismatch")
    for name in sorted(MANIFESTED_FILES):
        path = artifact_dir / name
        receipt = files[name]
        if not isinstance(receipt, dict) or set(receipt) != {"bytes", "sha256"}:
            raise VerificationError(f"artifact manifest schema mismatch for {name}")
        actual_receipt = {"bytes": path.stat().st_size, "sha256": sha256_file(path)}
        if receipt != actual_receipt:
            raise VerificationError(f"artifact manifest hash mismatch for {name}")

    observed_summary = _json_object(artifact_dir / "summary.json", "summary")
    observed_arm_strings = _csv_rows(artifact_dir / "arm_metrics.csv", ARM_FIELDS, "arm metrics")
    observed_task_strings = _csv_rows(artifact_dir / "task_metrics.csv", TASK_FIELDS, "task metrics")
    observed_scale_strings = _csv_rows(artifact_dir / "task_scales.csv", SCALE_FIELDS, "task scales")
    observed_pairs = _jsonl_rows(artifact_dir / "per_pair.jsonl", "per-pair")
    expected_sets = (
        (expected["arm_rows"], observed_arm_strings, "arm"),
        (expected["task_rows"], observed_task_strings, "task"),
        (expected["scale_rows"], observed_scale_strings, "scale"),
    )
    maximum_difference = compare_values(expected["summary"], observed_summary, "summary")
    for expected_rows, observed_rows, role in expected_sets:
        if len(expected_rows) != len(observed_rows):
            raise VerificationError(f"{role} artifact row-count mismatch")
        for index, expected_row in enumerate(expected_rows):
            observed_row = _cast_csv_row(observed_rows[index], expected_row, f"{role}[{index}]")
            maximum_difference = max(
                maximum_difference,
                compare_values(expected_row, observed_row, f"{role}[{index}]"),
            )
    if len(expected["pair_rows"]) != len(observed_pairs):
        raise VerificationError("per-pair artifact row-count mismatch")
    for index, (expected_row, observed_row) in enumerate(zip(expected["pair_rows"], observed_pairs)):
        maximum_difference = max(
            maximum_difference,
            compare_values(expected_row, observed_row, f"pair[{index}]"),
        )
    return {
        "artifact_manifest_sha256": sha256_file(manifest_path),
        "maximum_numeric_difference": maximum_difference,
        "rows": {
            "arm_metrics": len(expected["arm_rows"]),
            "task_metrics": len(expected["task_rows"]),
            "task_scales": len(expected["scale_rows"]),
            "per_pair": len(expected["pair_rows"]),
        },
    }


def verify(
    cards_path: Path,
    train_path: Path,
    dev_path: Path,
    contract_path: Path,
    artifact_dir: Path,
    *,
    expected_contract_sha256: str = CONTRACT_SHA256,
    source: Mapping[str, Mapping[str, Any]] = SOURCE,
) -> dict[str, Any]:
    expected = reconstruct_expected_bundle(
        cards_path,
        train_path,
        dev_path,
        contract_path,
        expected_contract_sha256=expected_contract_sha256,
        source=source,
    )
    output = validate_output_bundle(artifact_dir, expected)
    return {
        "protocol": f"verify-{PROTOCOL}-v1",
        "status": "INDEPENDENT_SOURCE_REFIT_PASS",
        "contract_sha256": expected_contract_sha256,
        "inputs": {
            role: {key: value for key, value in _source_receipt(source, role).items() if key in {"sha256", "bytes"}}
            for role in ("cards", "train", "dev")
        },
        **output,
        "unique_cpu_critic_refits": 4,
        "summary_status": expected["summary"]["status"],
        "primary_point_deltas": {
            "gap_weighted_minus_binary": expected["summary"]["primary"][
                "gap_weighted_minus_binary"
            ]["point_delta"],
            "gap_weighted_minus_gap_permuted": expected["summary"]["primary"][
                "gap_weighted_minus_gap_permuted"
            ]["point_delta"],
        },
        "primary_contrast_all_pass": {
            "gap_weighted_minus_binary": expected["summary"]["primary"][
                "gap_weighted_minus_binary"
            ]["all_pass"],
            "gap_weighted_minus_gap_permuted": expected["summary"]["primary"][
                "gap_weighted_minus_gap_permuted"
            ]["all_pass"],
        },
        "primary_all_pass": expected["summary"]["primary"]["all_pass"],
        "source_open_attestation": {
            "heldout_test_pairs": False,
            "test_predictions": False,
            "prospective_vault": False,
            "score_channel_truth": False,
        },
    }


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("cards", type=Path)
    parser.add_argument("train", type=Path)
    parser.add_argument("dev", type=Path)
    parser.add_argument("artifact_dir", type=Path)
    parser.add_argument("verification_output", type=Path)
    parser.add_argument(
        "--contract",
        type=Path,
        required=True,
    )
    return parser


def main() -> None:
    args = build_parser().parse_args()
    if args.verification_output.exists():
        raise VerificationError("verification output already exists")
    receipt = verify(args.cards, args.train, args.dev, args.contract, args.artifact_dir)
    args.verification_output.parent.mkdir(parents=True, exist_ok=True)
    args.verification_output.write_bytes(canonical_bytes(receipt))
    print(compact(receipt))


if __name__ == "__main__":
    main()
