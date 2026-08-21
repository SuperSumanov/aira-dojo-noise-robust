"""Independent full-refit verifier for the parent-closed static-source OOF audit."""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import re
import zlib
from collections import defaultdict
from pathlib import Path
from typing import Any

import numpy as np
from sklearn.ensemble import HistGradientBoostingClassifier

from phase1.verify_critic_component_static_suite import extract_features


PROTOCOL = "critic-static-source-parent-closed-component-oof-v2"
FOLD_SEED = 20260823
TASK_SEED = 20260823
PARENT_SEED = 20260824
FOLDS = 5
REPS = 20_000
EXPECTED = {
    "cards": ("5fd24c8e545a67e1048f8a67b23bcb64605b9ad584a4fbaa44aa1b1f1b6e1afb", 604190866),
    "train": ("0ec49d76a896accf8e85a2556ca7ed12b9379b1867247d99c6be5e4c83bea98e", 3208089),
    "dev": ("3b3fb53f84277e935c66d3b3d1646d7a7d33624fb916e3f9bcc15f689904cfa4", 376635),
}
EXPECTED_COUNTS = {
    "pairs": 5240,
    "tasks": 28,
    "original_components": 168,
    "cross_component_parents": 16,
    "supercomponents": 152,
    "merged_supercomponents": 16,
    "maximum_original_components_per_supercomponent": 2,
}
LINEAGE = ("depth", "n_sibs", "step")
FEATURES = tuple(sorted(extract_features({"code": "", "lineage": {}})))
CODE = tuple(name for name in FEATURES if name not in LINEAGE)
GROUPS = {"gbm_code": CODE, "gbm_lineage": LINEAGE, "gbm_all": FEATURES}
LEARNED = tuple(GROUPS)
MODELS = ("random_hash", *LEARNED, "orientation_oracle")


class VerificationError(RuntimeError):
    """Raised when an artifact differs from an independent refit."""


def demand(condition: bool, message: str) -> None:
    if not condition:
        raise VerificationError(message)


def compact(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def file_hash(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()


def numeric_hash(values: np.ndarray) -> str:
    return hashlib.sha256(np.asarray(values, dtype="<f8").tobytes()).hexdigest()


def identify(path: Path, role: str) -> None:
    expected_hash, expected_bytes = EXPECTED[role]
    demand(path.stat().st_size == expected_bytes, f"{role} byte count mismatch")
    demand(file_hash(path) == expected_hash, f"{role} hash mismatch")


def identity(row: dict[str, Any]) -> tuple[str, str, str, str]:
    try:
        low, high = sorted((row["better"], row["worse"]))
        result = row["task"], row["parent"], low, high
    except (KeyError, TypeError, ValueError) as error:
        raise VerificationError("invalid pair identity") from error
    demand(all(isinstance(value, str) and value for value in result), "empty pair identity")
    demand(low != high, "self pair")
    return result


def load_rows(path: Path, split: str) -> list[dict[str, Any]]:
    result = []
    observed = set()
    with path.open(encoding="utf-8") as handle:
        for line_number, line in enumerate(handle, 1):
            demand(bool(line.strip()), f"blank row at {path.name}:{line_number}")
            row = json.loads(line)
            demand(isinstance(row, dict), "non-object pair row")
            key = identity(row)
            demand(key not in observed, f"duplicate pair in {path.name}")
            observed.add(key)
            demand(row.get("intask_split") == split, f"split mismatch in {path.name}")
            result.append(row)
    return result


def cards_projection(path: Path, endpoints: set[str]):
    grouped = json.loads(path.read_text(encoding="utf-8"))
    demand(isinstance(grouped, dict), "cards root is not grouped")
    vectors: dict[str, np.ndarray] = {}
    run_of: dict[str, str] = {}
    task_of: dict[str, str] = {}
    config_of: dict[str, tuple[Any, ...]] = {}
    seen = set()
    total = 0
    for run_id, cards in grouped.items():
        demand(isinstance(run_id, str) and isinstance(cards, list), "invalid card group")
        for card in cards:
            total += 1
            demand(isinstance(card, dict) and isinstance(card.get("id"), str), "invalid card")
            card_id = card["id"]
            demand(card_id not in seen, "duplicate card id")
            seen.add(card_id)
            if card_id not in endpoints:
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
            demand(
                all(isinstance(value, str) and value for value in config[:3])
                and all(isinstance(value, int) for value in config[3:]),
                "needed card lacks provenance",
            )
            extracted = extract_features(card)
            demand(tuple(sorted(extracted)) == FEATURES and len(FEATURES) == 34, "feature contract mismatch")
            vector = np.asarray([extracted[name] for name in FEATURES], dtype=np.float64)
            demand(np.isfinite(vector).all(), "non-finite feature")
            vectors[card_id] = vector
            run_of[card_id] = run_id
            task_of[card_id] = task
            config_of[card_id] = config
    demand(set(vectors) == endpoints, "endpoint missing from Cards")
    return vectors, run_of, task_of, config_of, {
        "cards": total, "run_groups": len(grouped), "needed_cards": len(endpoints)
    }


def parent_closed_units(rows, run_of, task_of, config_of):
    original = set()
    task_for_component = {}
    split_for_component = {}
    endpoint_membership = defaultdict(set)
    run_membership = defaultdict(set)
    parent_membership = defaultdict(set)
    keys = set()
    for row in rows:
        key = identity(row)
        demand(key not in keys, "duplicate combined pair")
        keys.add(key)
        component = row.get("pair_component_id")
        demand(
            row.get("outer_intask_split") == "train"
            and row.get("train_dev_protocol") == "pair-graph-component-train-dev-split-v1"
            and row.get("train_dev_seed") == 20260821
            and row.get("train_dev_target_numerator") == 1
            and row.get("train_dev_target_denominator") == 10
            and isinstance(component, str)
            and re.fullmatch(r"[0-9a-f]{64}", component) is not None,
            "component receipt mismatch",
        )
        original.add(component)
        demand(task_for_component.setdefault(component, row["task"]) == row["task"], "component task leak")
        demand(
            split_for_component.setdefault(component, row["intask_split"]) == row["intask_split"],
            "component split leak",
        )
        for endpoint in (row["better"], row["worse"]):
            demand(task_of[endpoint] == row["task"], "pair/card task mismatch")
            endpoint_membership[endpoint].add(component)
            run_membership[run_of[endpoint]].add(component)
        demand(config_of[row["better"]] == config_of[row["worse"]], "config mismatch")
        parent_membership[(row["task"], row["parent"])].add(component)
    demand(len(rows) == EXPECTED_COUNTS["pairs"], "pair count mismatch")
    demand(len({row["task"] for row in rows}) == EXPECTED_COUNTS["tasks"], "task count mismatch")
    demand(len(original) == EXPECTED_COUNTS["original_components"], "component count mismatch")
    demand(all(len(value) == 1 for value in endpoint_membership.values()), "endpoint crosses component")
    demand(all(len(value) == 1 for value in run_membership.values()), "run crosses component")
    crossing = {key: value for key, value in parent_membership.items() if len(value) > 1}
    demand(len(crossing) == EXPECTED_COUNTS["cross_component_parents"], "parent crossing count mismatch")

    leader = {component: component for component in original}
    def root(component):
        cursor = component
        while leader[cursor] != cursor:
            cursor = leader[cursor]
        while leader[component] != component:
            following = leader[component]
            leader[component] = cursor
            component = following
        return cursor
    def merge(left, right):
        left_root, right_root = root(left), root(right)
        if left_root != right_root:
            low, high = sorted((left_root, right_root))
            leader[high] = low
    for components in parent_membership.values():
        ordered = sorted(components)
        for component in ordered[1:]:
            merge(ordered[0], component)
    member_sets = defaultdict(list)
    for component in sorted(original):
        member_sets[root(component)].append(component)
    demand(len(member_sets) == EXPECTED_COUNTS["supercomponents"], "supercomponent count mismatch")
    demand(
        sum(len(value) > 1 for value in member_sets.values()) == EXPECTED_COUNTS["merged_supercomponents"],
        "merged supercomponent count mismatch",
    )
    demand(
        max(map(len, member_sets.values()))
        == EXPECTED_COUNTS["maximum_original_components_per_supercomponent"],
        "closure width mismatch",
    )
    super_for_component = {}
    for members in member_sets.values():
        identifier = hashlib.sha256(compact(members).encode()).hexdigest()
        for component in members:
            super_for_component[component] = identifier
    super_for_pair = {compact(identity(row)): super_for_component[row["pair_component_id"]] for row in rows}
    super_tasks = defaultdict(set)
    super_endpoints = defaultdict(set)
    super_runs = defaultdict(set)
    super_parents = defaultdict(set)
    for row in rows:
        super_id = super_for_pair[compact(identity(row))]
        super_tasks[super_id].add(row["task"])
        super_parents[(row["task"], row["parent"])].add(super_id)
        for endpoint in (row["better"], row["worse"]):
            super_endpoints[endpoint].add(super_id)
            super_runs[run_of[endpoint]].add(super_id)
    demand(all(len(value) == 1 for value in super_tasks.values()), "supercomponent task leak")
    demand(all(len(value) == 1 for value in super_endpoints.values()), "endpoint closure failed")
    demand(all(len(value) == 1 for value in super_runs.values()), "run closure failed")
    demand(all(len(value) == 1 for value in super_parents.values()), "parent closure failed")
    receipt = {
        "pairs": len(rows),
        "tasks": len({row["task"] for row in rows}),
        "parents": len(super_parents),
        "endpoints": len(super_endpoints),
        "runs": len(super_runs),
        "original_components": len(original),
        "cross_component_parents_before_closure": len(crossing),
        "supercomponents": len(member_sets),
        "merged_supercomponents": sum(len(value) > 1 for value in member_sets.values()),
        "maximum_original_components_per_supercomponent": max(map(len, member_sets.values())),
        "all_endpoint_run_parent_supercomponent_unique": True,
        "supercomponent_membership_sha256": hashlib.sha256(
            compact(sorted((super_for_component[key], key) for key in super_for_component)).encode()
        ).hexdigest(),
    }
    return super_for_pair, receipt


def independent_fold_assignment(rows, super_for_pair):
    pair_indices = defaultdict(list)
    task_for_super = {}
    for index, row in enumerate(rows):
        super_id = super_for_pair[compact(identity(row))]
        pair_indices[super_id].append(index)
        demand(task_for_super.setdefault(super_id, row["task"]) == row["task"], "super task mismatch")
    ordered = sorted(pair_indices, key=lambda value: (-len(pair_indices[value]), task_for_super[value], value))
    task_counts = defaultdict(lambda: [0, 0, 0, 0, 0])
    total_counts = [0, 0, 0, 0, 0]
    assignment = {}
    for super_id in ordered:
        task = task_for_super[super_id]
        offset = int(hashlib.sha256(f"{FOLD_SEED}|{task}".encode()).hexdigest(), 16) % FOLDS
        candidates = []
        for fold in range(FOLDS):
            candidates.append((task_counts[task][fold], total_counts[fold], (fold - offset) % FOLDS, fold))
        fold = min(candidates)[-1]
        assignment[super_id] = fold
        weight = len(pair_indices[super_id])
        task_counts[task][fold] += weight
        total_counts[fold] += weight
    folds = np.asarray([assignment[super_for_pair[compact(identity(row))]] for row in rows], dtype=np.int8)
    demand(set(folds.tolist()) == set(range(FOLDS)), "empty fold")
    receipt = {
        "algorithm": "parent_closed_greedy_task_then_global_balance_v2",
        "seed": FOLD_SEED,
        "folds": FOLDS,
        "pair_counts": [int(np.sum(folds == fold)) for fold in range(FOLDS)],
        "supercomponent_counts": [
            len({super_for_pair[compact(identity(row))] for row, value in zip(rows, folds) if value == fold})
            for fold in range(FOLDS)
        ],
        "assignment_sha256": hashlib.sha256(compact(sorted(assignment.items())).encode()).hexdigest(),
    }
    return folds, receipt


def isolation_receipts(rows, folds, run_of, super_for_pair):
    result = []
    for fold in range(FOLDS):
        fit = [row for row, value in zip(rows, folds) if value != fold]
        evaluate = [row for row, value in zip(rows, folds) if value == fold]
        demand(fit and evaluate, "empty fold side")
        receipt = {"fold": fold, "fit_pairs": len(fit), "eval_pairs": len(evaluate)}
        extractors = {
            "pair": lambda row: {identity(row)},
            "endpoint": lambda row: {row["better"], row["worse"]},
            "run": lambda row: {run_of[row["better"]], run_of[row["worse"]]},
            "parent": lambda row: {(row["task"], row["parent"])},
            "original_component": lambda row: {row["pair_component_id"]},
            "supercomponent": lambda row: {super_for_pair[compact(identity(row))]},
        }
        for name, extractor in extractors.items():
            fit_values = set().union(*(extractor(row) for row in fit))
            eval_values = set().union(*(extractor(row) for row in evaluate))
            overlap = len(fit_values & eval_values)
            receipt[f"{name}_overlap"] = overlap
            demand(overlap == 0, f"{name} overlap in fold {fold}")
        receipt["fit_tasks"] = len({row["task"] for row in fit})
        receipt["eval_tasks"] = len({row["task"] for row in evaluate})
        result.append(receipt)
    return result


def fitted_oof(differences, folds):
    location = {name: index for index, name in enumerate(FEATURES)}
    predictions = {name: np.full(len(differences), np.nan) for name in LEARNED}
    receipts = {name: [] for name in LEARNED}
    antisymmetry = {name: 0.0 for name in LEARNED}
    for name, feature_names in GROUPS.items():
        columns = [location[feature] for feature in feature_names]
        values = differences[:, columns]
        for fold in range(FOLDS):
            fit_mask = folds != fold
            eval_mask = folds == fold
            fit_values = values[fit_mask]
            augmented = np.concatenate((fit_values, -fit_values), axis=0)
            labels = np.r_[np.ones(len(fit_values), dtype=np.int8), np.zeros(len(fit_values), dtype=np.int8)]
            model = HistGradientBoostingClassifier(
                loss="log_loss", max_iter=300, learning_rate=.08, max_leaf_nodes=31,
                max_depth=None, min_samples_leaf=20, l2_regularization=0.0,
                early_stopping=False, random_state=7,
            ).fit(augmented, labels)
            demand(model.n_iter_ == 300, "GBM iteration mismatch")
            evaluation = values[eval_mask]
            direct = model.decision_function(evaluation)
            reversed_score = model.decision_function(-evaluation)
            forward = (direct - reversed_score) / 2.0
            reverse = (reversed_score - direct) / 2.0
            demand(np.isfinite(forward).all(), "non-finite OOF prediction")
            error = float(np.max(np.abs(forward + reverse)))
            demand(error <= 1e-12, "antisymmetry failure")
            predictions[name][eval_mask] = forward
            antisymmetry[name] = max(antisymmetry[name], error)
            receipts[name].append({
                "fold": fold,
                "fit_pairs": int(np.sum(fit_mask)),
                "eval_pairs": int(np.sum(eval_mask)),
                "features": list(feature_names),
                "feature_count": len(columns),
                "n_iter": int(model.n_iter_),
                "fit_matrix_sha256": numeric_hash(fit_values),
                "eval_margin_sha256": numeric_hash(forward),
                "anti_symmetry_max_abs": error,
            })
        demand(np.isfinite(predictions[name]).all(), "missing OOF prediction")
    return predictions, receipts, antisymmetry


def credit(margins):
    demand(np.isfinite(margins).all(), "non-finite metric input")
    return np.where(margins > 0, 1.0, np.where(margins < 0, 0.0, 0.5))


def distribution(values):
    points = np.quantile(values, [0, .1, .25, .5, .75, .9, 1], method="linear")
    return dict(zip(("q00", "q10", "q25", "q50", "q75", "q90", "q100"), map(float, points)))


def by_task(rows, values):
    tasks = sorted({row["task"] for row in rows})
    means = np.asarray([
        np.mean([value for row, value in zip(rows, values) if row["task"] == task]) for task in tasks
    ])
    generator = np.random.default_rng(TASK_SEED)
    choices = generator.integers(0, len(tasks), size=(REPS, len(tasks)))
    samples = np.mean(means[choices], axis=1)
    interval = np.quantile(samples, [.025, .975], method="linear")
    return {
        "point": float(np.mean(means)), "ci95": list(map(float, interval)),
        "clusters": len(tasks), "replicates": REPS, "seed": TASK_SEED,
    }


def by_parent(rows, values):
    grouped = defaultdict(list)
    for row, value in zip(rows, values):
        grouped[(row["task"], row["parent"])].append(float(value))
    arrays = [np.asarray(grouped[key]) for key in sorted(grouped)]
    generator = np.random.default_rng(PARENT_SEED)
    samples = np.empty(REPS)
    for repetition in range(REPS):
        choices = generator.integers(0, len(arrays), size=len(arrays))
        samples[repetition] = sum(float(np.sum(arrays[item])) for item in choices) / sum(
            len(arrays[item]) for item in choices
        )
    interval = np.quantile(samples, [.025, .975], method="linear")
    return {
        "point": float(np.mean(values)), "ci95": list(map(float, interval)),
        "clusters": len(arrays), "replicates": REPS, "seed": PARENT_SEED,
    }


def metrics(rows, margins):
    values = credit(margins)
    task_result = by_task(rows, values)
    return {
        "pairs": len(rows), "tasks": len({row["task"] for row in rows}),
        "parents": len({(row["task"], row["parent"]) for row in rows}),
        "coverage": float(np.mean(np.isfinite(margins))), "ties": int(np.sum(margins == 0)),
        "micro_accuracy": float(np.mean(values)), "task_macro_accuracy": task_result["point"],
        "task_clustered": task_result, "parent_clustered": by_parent(rows, values),
        "margin_quantiles": distribution(margins),
    }


def paired(rows, values):
    task_result = by_task(rows, values)
    parent_result = by_parent(rows, values)
    task_means = {
        task: float(np.mean([value for row, value in zip(rows, values) if row["task"] == task]))
        for task in sorted({row["task"] for row in rows})
    }
    loto = {
        task: float(np.mean([value for other, value in task_means.items() if other != task]))
        for task in task_means
    }
    return {
        "pair_micro_delta": float(np.mean(values)), "task_macro_delta": task_result["point"],
        "task_clustered": task_result, "parent_clustered": parent_result,
        "per_task_delta": task_means, "leave_one_task_out_task_macro_delta": loto,
        "minimum_leave_one_task_out_task_macro_delta": min(loto.values()),
    }


def recompute(cards_path: Path, train_path: Path, dev_path: Path):
    for role, path in (("cards", cards_path), ("train", train_path), ("dev", dev_path)):
        identify(path, role)
    rows = load_rows(train_path, "train") + load_rows(dev_path, "dev")
    rows.sort(key=identity)
    endpoints = {row[side] for row in rows for side in ("better", "worse")}
    vectors, run_of, task_of, config_of, card_inventory = cards_projection(cards_path, endpoints)
    super_for_pair, integrity = parent_closed_units(rows, run_of, task_of, config_of)
    folds, fold_receipt = independent_fold_assignment(rows, super_for_pair)
    isolation = isolation_receipts(rows, folds, run_of, super_for_pair)
    differences = np.vstack([vectors[row["better"]] - vectors[row["worse"]] for row in rows])
    learned, model_receipts, antisymmetry = fitted_oof(differences, folds)
    random_values = []
    for row in rows:
        left, right = sorted((row["better"], row["worse"]))
        chosen = (left, right)[zlib.crc32((left + "|" + right).encode()) & 1]
        random_values.append(1.0 if chosen == row["better"] else -1.0)
    margins = {
        "random_hash": np.asarray(random_values), **learned,
        "orientation_oracle": np.ones(len(rows)),
    }
    all_metrics = {name: metrics(rows, margins[name]) for name in MODELS}
    code_values = credit(margins["gbm_code"])
    paired_results = {
        "code_minus_lineage": paired(rows, code_values - credit(margins["gbm_lineage"])),
        "code_minus_all": paired(rows, code_values - credit(margins["gbm_all"])),
    }
    random_task = all_metrics["random_hash"]["task_clustered"]["ci95"]
    random_parent = all_metrics["random_hash"]["parent_clustered"]["ci95"]
    gates = {
        "code_task_ci_above_half": all_metrics["gbm_code"]["task_clustered"]["ci95"][0] > .5,
        "code_parent_ci_above_half": all_metrics["gbm_code"]["parent_clustered"]["ci95"][0] > .5,
        "code_lineage_task_ci_above_zero": paired_results["code_minus_lineage"]["task_clustered"]["ci95"][0] > 0,
        "code_lineage_parent_ci_above_zero": paired_results["code_minus_lineage"]["parent_clustered"]["ci95"][0] > 0,
        "code_all_task_noninferior_one_point": paired_results["code_minus_all"]["task_clustered"]["ci95"][0] >= -.01,
        "code_all_parent_noninferior_one_point": paired_results["code_minus_all"]["parent_clustered"]["ci95"][0] >= -.01,
        "code_lineage_all_loto_positive": paired_results["code_minus_lineage"]["minimum_leave_one_task_out_task_macro_delta"] > 0,
        "random_task_ci_contains_half": random_task[0] <= .5 <= random_task[1],
        "random_parent_ci_contains_half": random_parent[0] <= .5 <= random_parent[1],
        "learned_full_coverage": all(all_metrics[name]["coverage"] == 1.0 for name in LEARNED),
        "learned_no_ties": all(all_metrics[name]["ties"] == 0 for name in LEARNED),
        "all_antisymmetric": max(antisymmetry.values()) <= 1e-12,
        "orientation_oracle_exact": all_metrics["orientation_oracle"]["micro_accuracy"] == 1.0,
        "all_fold_isolation_zero": all(
            value == 0 for receipt in isolation for key, value in receipt.items() if key.endswith("_overlap")
        ),
    }
    effect_pass = all(gates.values())
    feature_matrix = np.vstack([vectors[card_id] for card_id in sorted(vectors)])
    summary = {
        "protocol": PROTOCOL,
        "status": (
            "STATIC_CODE_SOURCE_CANDIDATE_PENDING_INDEPENDENT_VERIFICATION"
            if effect_pass else "STATIC_SOURCE_AUDIT_VALID_NO_NARROW_POSITIVE"
        ),
        "evidence_level": "retrospective_outer_train_parent_closed_component_oof_robustness",
        "inputs": {
            role: {"sha256": EXPECTED[role][0], "bytes": EXPECTED[role][1]}
            for role in ("cards", "train", "dev")
        },
        "forbidden_inputs_opened": {
            "test": False, "tfidf": False, "semantic": False, "prospective_outcome": False,
        },
        "card_inventory": card_inventory,
        "integrity": integrity,
        "folds": {**fold_receipt, "isolation": isolation},
        "features": {
            "all_names": list(FEATURES), "groups": {name: list(value) for name, value in GROUPS.items()},
            "matrix_sha256": numeric_hash(feature_matrix),
            "endpoint_order_sha256": hashlib.sha256(compact(sorted(vectors)).encode()).hexdigest(),
            "forbidden_post_execution_fields_used": False,
        },
        "models": {
            "parameters": {
                "loss": "log_loss", "max_iter": 300, "learning_rate": .08,
                "max_leaf_nodes": 31, "max_depth": None, "min_samples_leaf": 20,
                "l2_regularization": 0.0, "early_stopping": False, "random_state": 7,
            },
            "fold_receipts": model_receipts, "anti_symmetry_max_abs": antisymmetry,
        },
        "metrics": all_metrics, "paired_deltas": paired_results, "gates": gates,
        "producer_effect_gates_pass": effect_pass, "pending_independent_verification": True,
        "narrow_positive_claim_allowed": False,
        "bootstrap": {"replicates": REPS, "task_seed": TASK_SEED, "parent_seed": PARENT_SEED},
    }
    pair_rows = []
    task_rows = []
    parent_rows = []
    fold_rows = []
    for name in MODELS:
        values = credit(margins[name])
        for index, (row, margin, value, fold) in enumerate(zip(rows, margins[name], values, folds)):
            pair_rows.append({
                "model": name, "index": index, "source_split": row["intask_split"],
                "task": row["task"], "parent": row["parent"], "better": row["better"],
                "worse": row["worse"], "pair_component_id": row["pair_component_id"],
                "parent_closed_supercomponent_id": super_for_pair[compact(identity(row))],
                "fold": int(fold), "margin": float(margin), "correct_credit": float(value),
                "tie": bool(margin == 0),
            })
        for task in sorted({row["task"] for row in rows}):
            mask = np.asarray([row["task"] == task for row in rows])
            task_rows.append({"model": name, "task": task, "pairs": int(mask.sum()), "accuracy": float(values[mask].mean())})
        for task, parent in sorted({(row["task"], row["parent"]) for row in rows}):
            mask = np.asarray([row["task"] == task and row["parent"] == parent for row in rows])
            parent_rows.append({
                "model": name, "task": task, "parent": parent,
                "pairs": int(mask.sum()), "accuracy": float(values[mask].mean()),
            })
        for fold in range(FOLDS):
            mask = folds == fold
            fold_rows.append({
                "model": name, "fold": fold, "pairs": int(mask.sum()),
                "tasks": len({row["task"] for row, keep in zip(rows, mask) if keep}),
                "accuracy": float(values[mask].mean()),
            })
    return summary, pair_rows, task_rows, parent_rows, fold_rows


def compare_values(expected: Any, observed: Any, location: str = "root") -> float:
    if isinstance(expected, dict):
        demand(isinstance(observed, dict) and set(expected) == set(observed), f"mapping mismatch at {location}")
        return max((compare_values(expected[key], observed[key], f"{location}.{key}") for key in expected), default=0.0)
    if isinstance(expected, list):
        demand(isinstance(observed, list) and len(expected) == len(observed), f"list mismatch at {location}")
        return max((compare_values(left, right, f"{location}[{index}]") for index, (left, right) in enumerate(zip(expected, observed))), default=0.0)
    if isinstance(expected, bool) or expected is None or isinstance(expected, str):
        demand(observed == expected and type(observed) is type(expected), f"value mismatch at {location}")
        return 0.0
    if isinstance(expected, int):
        demand(isinstance(observed, int) and not isinstance(observed, bool) and observed == expected, f"integer mismatch at {location}")
        return 0.0
    if isinstance(expected, float):
        demand(isinstance(observed, (int, float)) and not isinstance(observed, bool), f"numeric type mismatch at {location}")
        difference = abs(float(observed) - expected)
        demand(np.isfinite(difference) and difference <= 1e-12, f"numeric mismatch at {location}")
        return difference
    raise VerificationError(f"unsupported comparison type at {location}")


def read_jsonl_artifact(path: Path):
    with path.open(encoding="utf-8") as handle:
        return [json.loads(line) for line in handle]


def compare_csv(path: Path, expected: list[dict[str, Any]], fields: tuple[str, ...]) -> float:
    with path.open(encoding="utf-8", newline="") as handle:
        observed = list(csv.DictReader(handle))
    demand(len(observed) == len(expected), f"row count mismatch in {path.name}")
    maximum = 0.0
    integer_fields = {"pairs", "tasks", "fold"}
    for index, (left, right) in enumerate(zip(expected, observed)):
        for field in fields:
            if field in integer_fields:
                demand(int(right[field]) == left[field], f"integer mismatch in {path.name}:{index}:{field}")
            elif field == "accuracy":
                difference = abs(float(right[field]) - left[field])
                demand(difference <= 1e-12, f"accuracy mismatch in {path.name}:{index}")
                maximum = max(maximum, difference)
            else:
                demand(right[field] == left[field], f"identity mismatch in {path.name}:{index}:{field}")
    return maximum


def verify(cards_path: Path, train_path: Path, dev_path: Path, artifact_dir: Path) -> dict[str, Any]:
    expected_summary, expected_pairs, expected_tasks, expected_parents, expected_folds = recompute(
        cards_path, train_path, dev_path
    )
    producer_summary = json.loads((artifact_dir / "summary.json").read_text(encoding="utf-8"))
    maximum_summary = compare_values(expected_summary, producer_summary, "summary")
    observed_pairs = read_jsonl_artifact(artifact_dir / "per_pair.jsonl")
    demand(len(observed_pairs) == len(expected_pairs), "per-pair row count mismatch")
    maximum_pair = max(
        (compare_values(left, right, f"per_pair[{index}]") for index, (left, right) in enumerate(zip(expected_pairs, observed_pairs))),
        default=0.0,
    )
    maximum_task = compare_csv(
        artifact_dir / "per_task.csv", expected_tasks, ("model", "task", "pairs", "accuracy")
    )
    maximum_parent = compare_csv(
        artifact_dir / "per_parent.csv", expected_parents,
        ("model", "task", "parent", "pairs", "accuracy"),
    )
    maximum_fold = compare_csv(
        artifact_dir / "per_fold.csv", expected_folds,
        ("model", "fold", "pairs", "tasks", "accuracy"),
    )
    manifest = json.loads((artifact_dir / "artifact_manifest.json").read_text(encoding="utf-8"))
    expected_manifest = {
        name: file_hash(artifact_dir / name)
        for name in ("summary.json", "per_pair.jsonl", "per_task.csv", "per_parent.csv", "per_fold.csv")
    }
    demand(manifest == expected_manifest, "artifact manifest mismatch")
    verification_gates = {
        "full_refit_summary_exact": maximum_summary <= 1e-12,
        "all_pair_rows_exact": maximum_pair <= 1e-12,
        "all_task_rows_exact": maximum_task <= 1e-12,
        "all_parent_rows_exact": maximum_parent <= 1e-12,
        "all_fold_rows_exact": maximum_fold <= 1e-12,
        "artifact_manifest_valid": True,
        "producer_not_imported": True,
    }
    verification_pass = all(verification_gates.values())
    strong = bool(expected_summary["producer_effect_gates_pass"] and verification_pass)
    return {
        "protocol": "independent-critic-static-source-parent-closed-component-oof-verifier-v2",
        "status": (
            "STATIC_CODE_SOURCE_NARROW_POSITIVE_INDEPENDENTLY_VERIFIED"
            if strong else "STATIC_SOURCE_OOF_INDEPENDENTLY_VERIFIED_NO_NARROW_POSITIVE"
        ),
        "full_refit": True,
        "producer_imported": False,
        "pairs": expected_summary["integrity"]["pairs"],
        "producer_effect_gates_pass": expected_summary["producer_effect_gates_pass"],
        "verification_gates": verification_gates,
        "narrow_positive_claim_allowed": strong,
        "max_abs_summary_difference": maximum_summary,
        "max_abs_pair_difference": maximum_pair,
        "max_abs_task_accuracy_difference": maximum_task,
        "max_abs_parent_accuracy_difference": maximum_parent,
        "max_abs_fold_accuracy_difference": maximum_fold,
        "producer_summary_sha256": file_hash(artifact_dir / "summary.json"),
        "producer_artifact_manifest_sha256": file_hash(artifact_dir / "artifact_manifest.json"),
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("cards", type=Path)
    parser.add_argument("train", type=Path)
    parser.add_argument("dev", type=Path)
    parser.add_argument("artifact_dir", type=Path)
    args = parser.parse_args()
    print(json.dumps(verify(args.cards, args.train, args.dev, args.artifact_dir), indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
