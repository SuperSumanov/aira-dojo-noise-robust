"""Parent-closed OOF audit of child-only versus parent-relative transition features."""

from __future__ import annotations

import argparse
import csv
import difflib
import hashlib
import json
import math
import zlib
from collections import defaultdict
from pathlib import Path
from typing import Any

import numpy as np
from sklearn.ensemble import HistGradientBoostingClassifier

from phase1 import critic_static_source_component_oof as base


PROTOCOL = "critic-parent-relative-transition-component-oof-v1"
TASK_SEED = 20260825
PARENT_SEED = 20260826
REPS = 20_000
ARMS = ("child_code", "transition_only", "child_plus_transition")
MODELS = ("random_hash", *ARMS, "orientation_oracle")
SUBSETS = ("merged", "Draft", "Improve")
EXPECTED_SEMANTIC = {
    "draft": ("3ca77a18e224cacbb7f52121d6e8c2b66f17298c68dd06fbc42a14a238ad05b9", 1465008),
    "improve": ("7aca481afda5317fe78a0ad52fc7488fceff7fde6531c74ebb718df9e3b6926e", 1087821),
}
EXPECTED_SEMANTIC_COUNTS = {"Draft": 3196, "Improve": 2044}
EDIT_NAMES = (
    "added_lines",
    "deleted_lines",
    "changed_hunks",
    "equal_fraction_parent",
    "equal_fraction_child",
    "absolute_log_character_ratio",
)
TRANSITION_NAMES = tuple(f"absolute_static_change__{name}" for name in base.CODE_FEATURES) + EDIT_NAMES


def semantic_identity(path: Path, role: str) -> None:
    expected_sha, expected_bytes = EXPECTED_SEMANTIC[role]
    base.require(path.stat().st_size == expected_bytes, f"{role} semantic byte count mismatch")
    base.require(base.sha256_file(path) == expected_sha, f"{role} semantic digest mismatch")


def semantic_map(draft_path: Path, improve_path: Path) -> dict[tuple[str, str, str, str], str]:
    result: dict[tuple[str, str, str, str], str] = {}
    for role, label, path in (
        ("draft", "Draft", draft_path),
        ("improve", "Improve", improve_path),
    ):
        semantic_identity(path, role)
        with path.open(encoding="utf-8") as handle:
            for line_number, line in enumerate(handle, 1):
                base.require(bool(line.strip()), f"blank semantic row {line_number}")
                raw = json.loads(line)
                base.require(isinstance(raw, dict), "semantic row is not an object")
                key = base.pair_key(raw)
                base.require(key not in result, "semantic identities overlap or repeat")
                result[key] = label
    return result


def load_card_projection(cards_path: Path, needed: set[str]):
    grouped = json.loads(cards_path.read_text(encoding="utf-8"))
    base.require(isinstance(grouped, dict), "Cards root is not grouped")
    vectors: dict[str, np.ndarray] = {}
    sources: dict[str, str] = {}
    runs: dict[str, str] = {}
    tasks: dict[str, str] = {}
    configs: dict[str, tuple[Any, ...]] = {}
    seen = set()
    total = 0
    for run_id, cards in grouped.items():
        base.require(isinstance(run_id, str) and isinstance(cards, list), "invalid card group")
        for card in cards:
            total += 1
            base.require(
                isinstance(card, dict)
                and isinstance(card.get("id"), str)
                and card["id"] not in seen,
                "invalid or duplicate card",
            )
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
            base.require(
                all(isinstance(value, str) and value for value in config[:3])
                and all(isinstance(value, int) for value in config[3:]),
                "needed card lacks provenance",
            )
            features = base.feature_dict(card)
            vector = np.asarray([features[name] for name in base.CODE_FEATURES], dtype=np.float64)
            source = card.get("code")
            base.require(isinstance(source, str) and np.isfinite(vector).all(), "invalid source projection")
            vectors[card_id] = vector
            sources[card_id] = source
            runs[card_id] = run_id
            tasks[card_id] = task
            configs[card_id] = config
    base.require(set(vectors) == needed, "needed endpoint or parent missing")
    return vectors, sources, runs, tasks, configs, {
        "cards": total,
        "run_groups": len(grouped),
        "needed_cards": len(needed),
    }


def edit_shape(parent: str, child: str) -> np.ndarray:
    parent_lines = parent.splitlines()
    child_lines = child.splitlines()
    matcher = difflib.SequenceMatcher(None, parent_lines, child_lines, autojunk=False)
    added = deleted = changed_hunks = equal = 0
    for tag, parent_start, parent_end, child_start, child_end in matcher.get_opcodes():
        if tag == "equal":
            equal += parent_end - parent_start
        else:
            changed_hunks += 1
            deleted += parent_end - parent_start
            added += child_end - child_start
    output = np.asarray(
        (
            added,
            deleted,
            changed_hunks,
            equal / max(1, len(parent_lines)),
            equal / max(1, len(child_lines)),
            abs(math.log1p(len(child)) - math.log1p(len(parent))),
        ),
        dtype=np.float64,
    )
    base.require(output.shape == (6,) and np.isfinite(output).all(), "invalid edit shape")
    return output


def feature_matrices(rows, vectors, sources):
    relation_cache: dict[tuple[str, str], np.ndarray] = {}
    child_rows = []
    transition_rows = []
    for row in rows:
        parent = row["parent"]
        for side in ("better", "worse"):
            child = row[side]
            relation = (child, parent)
            if relation not in relation_cache:
                absolute_change = np.abs(vectors[child] - vectors[parent])
                relation_cache[relation] = np.concatenate(
                    (absolute_change, edit_shape(sources[parent], sources[child]))
                )
        child_difference = vectors[row["better"]] - vectors[row["worse"]]
        transition_difference = (
            relation_cache[(row["better"], parent)]
            - relation_cache[(row["worse"], parent)]
        )
        child_rows.append(child_difference)
        transition_rows.append(transition_difference)
    child = np.asarray(child_rows, dtype=np.float64)
    transition = np.asarray(transition_rows, dtype=np.float64)
    combined = np.concatenate((child, transition), axis=1)
    base.require(
        child.shape == (len(rows), len(base.CODE_FEATURES))
        and transition.shape == (len(rows), len(TRANSITION_NAMES))
        and combined.shape == (len(rows), len(base.CODE_FEATURES) + len(TRANSITION_NAMES))
        and all(np.isfinite(matrix).all() for matrix in (child, transition, combined)),
        "transition feature matrix contract failed",
    )
    matrices = {
        "child_code": child,
        "transition_only": transition,
        "child_plus_transition": combined,
    }
    receipt = {
        "child_names": list(base.CODE_FEATURES),
        "transition_names": list(TRANSITION_NAMES),
        "unique_child_parent_relations": len(relation_cache),
        "matrix_shapes": {name: list(value.shape) for name, value in matrices.items()},
        "matrix_sha256": {name: base.array_sha(value) for name, value in matrices.items()},
        "signed_parent_delta_excluded_because_pairwise_cancels": True,
        "all_features_pre_execution": True,
    }
    return matrices, receipt


def oof_margins(matrices: dict[str, np.ndarray], folds: np.ndarray):
    predictions = {name: np.full(len(folds), np.nan, dtype=np.float64) for name in ARMS}
    receipts = {name: [] for name in ARMS}
    antisymmetry = {name: 0.0 for name in ARMS}
    for name, values in matrices.items():
        for fold in range(base.FOLDS):
            fit_mask = folds != fold
            eval_mask = folds == fold
            fit_values = values[fit_mask]
            augmented = np.concatenate((fit_values, -fit_values), axis=0)
            labels = np.r_[
                np.ones(len(fit_values), dtype=np.int8),
                np.zeros(len(fit_values), dtype=np.int8),
            ]
            model = HistGradientBoostingClassifier(
                loss="log_loss",
                max_iter=300,
                learning_rate=.08,
                max_leaf_nodes=31,
                max_depth=None,
                min_samples_leaf=20,
                l2_regularization=0.0,
                early_stopping=False,
                random_state=7,
            ).fit(augmented, labels)
            base.require(model.n_iter_ == 300, "GBM iteration count changed")
            evaluation = values[eval_mask]
            direct = model.decision_function(evaluation)
            reversed_score = model.decision_function(-evaluation)
            forward = (direct - reversed_score) / 2.0
            reverse = (reversed_score - direct) / 2.0
            error = float(np.max(np.abs(forward + reverse)))
            base.require(np.isfinite(forward).all() and error <= 1e-12, "antisymmetry failure")
            predictions[name][eval_mask] = forward
            antisymmetry[name] = max(antisymmetry[name], error)
            receipts[name].append(
                {
                    "fold": fold,
                    "fit_pairs": int(np.sum(fit_mask)),
                    "eval_pairs": int(np.sum(eval_mask)),
                    "features": values.shape[1],
                    "n_iter": int(model.n_iter_),
                    "fit_matrix_sha256": base.array_sha(fit_values),
                    "eval_margin_sha256": base.array_sha(forward),
                    "anti_symmetry_max_abs": error,
                }
            )
        base.require(np.isfinite(predictions[name]).all(), "missing OOF margin")
    return predictions, receipts, antisymmetry


def correctness(margins: np.ndarray) -> np.ndarray:
    base.require(np.isfinite(margins).all(), "non-finite metric input")
    return np.where(margins > 0, 1.0, np.where(margins < 0, 0.0, 0.5))


def task_interval(rows, values):
    tasks = sorted({row["task"] for row in rows})
    means = np.asarray(
        [np.mean([value for row, value in zip(rows, values) if row["task"] == task]) for task in tasks],
        dtype=np.float64,
    )
    rng = np.random.default_rng(TASK_SEED)
    indices = rng.integers(0, len(tasks), size=(REPS, len(tasks)))
    samples = np.mean(means[indices], axis=1)
    interval = np.quantile(samples, [.025, .975], method="linear")
    return {
        "point": float(np.mean(means)),
        "ci95": list(map(float, interval)),
        "clusters": len(tasks),
        "replicates": REPS,
        "seed": TASK_SEED,
    }


def parent_interval(rows, values):
    grouped: dict[tuple[str, str], list[float]] = defaultdict(list)
    for row, value in zip(rows, values):
        grouped[(row["task"], row["parent"])].append(float(value))
    arrays = [np.asarray(grouped[key], dtype=np.float64) for key in sorted(grouped)]
    sums = np.asarray([np.sum(array) for array in arrays], dtype=np.float64)
    counts = np.asarray([len(array) for array in arrays], dtype=np.float64)
    rng = np.random.default_rng(PARENT_SEED)
    estimates = np.empty(REPS, dtype=np.float64)
    offset = 0
    while offset < REPS:
        width = min(256, REPS - offset)
        indices = rng.integers(0, len(arrays), size=(width, len(arrays)))
        estimates[offset:offset + width] = np.sum(sums[indices], axis=1) / np.sum(
            counts[indices], axis=1
        )
        offset += width
    interval = np.quantile(estimates, [.025, .975], method="linear")
    return {
        "point": float(np.mean(values)),
        "ci95": list(map(float, interval)),
        "clusters": len(arrays),
        "replicates": REPS,
        "seed": PARENT_SEED,
    }


def metric(rows, margins):
    credit = correctness(margins)
    task = task_interval(rows, credit)
    quantiles = np.quantile(margins, [0, .1, .25, .5, .75, .9, 1], method="linear")
    return {
        "pairs": len(rows),
        "tasks": len({row["task"] for row in rows}),
        "parents": len({(row["task"], row["parent"]) for row in rows}),
        "coverage": float(np.mean(np.isfinite(margins))),
        "ties": int(np.sum(margins == 0)),
        "micro_accuracy": float(np.mean(credit)),
        "task_macro_accuracy": task["point"],
        "task_clustered": task,
        "parent_clustered": parent_interval(rows, credit),
        "margin_quantiles": dict(
            zip(("q00", "q10", "q25", "q50", "q75", "q90", "q100"), map(float, quantiles))
        ),
    }


def paired(rows, delta):
    task = task_interval(rows, delta)
    parent = parent_interval(rows, delta)
    task_means = {
        task_name: float(
            np.mean([value for row, value in zip(rows, delta) if row["task"] == task_name])
        )
        for task_name in sorted({row["task"] for row in rows})
    }
    loto = {
        task_name: float(np.mean([value for other, value in task_means.items() if other != task_name]))
        for task_name in task_means
    }
    return {
        "pair_micro_delta": float(np.mean(delta)),
        "task_macro_delta": task["point"],
        "task_clustered": task,
        "parent_clustered": parent,
        "per_task_delta": task_means,
        "leave_one_task_out_task_macro_delta": loto,
        "minimum_leave_one_task_out_task_macro_delta": min(loto.values()),
    }


def subset_indices(rows, semantics, name):
    if name == "merged":
        return np.arange(len(rows), dtype=np.int64)
    return np.asarray([index for index, row in enumerate(rows) if semantics[base.pair_key(row)] == name])


def all_metrics(rows, semantics, margins):
    output = {}
    for model, values in margins.items():
        output[model] = {}
        for subset in SUBSETS:
            indices = subset_indices(rows, semantics, subset)
            selected_rows = [rows[index] for index in indices]
            output[model][subset] = metric(selected_rows, values[indices])
    return output


def delta_metrics(rows, semantics, left, right):
    delta = correctness(left) - correctness(right)
    output = {}
    for subset in SUBSETS:
        indices = subset_indices(rows, semantics, subset)
        selected_rows = [rows[index] for index in indices]
        output[subset] = paired(selected_rows, delta[indices])
    return output


def lower_above(receipt, value):
    return receipt["task_clustered"]["ci95"][0] > value and receipt["parent_clustered"]["ci95"][0] > value


def analyze(cards_path, train_path, dev_path, draft_path, improve_path):
    for role, path in (("cards", cards_path), ("train", train_path), ("dev", dev_path)):
        base.verify_identity(path, role)
    rows = base.read_rows(train_path, "train") + base.read_rows(dev_path, "dev")
    rows.sort(key=base.pair_key)
    semantics = semantic_map(draft_path, improve_path)
    row_keys = {base.pair_key(row) for row in rows}
    base.require(row_keys.issubset(semantics), "semantic identity missing")
    semantic_counts = {
        label: sum(semantics[base.pair_key(row)] == label for row in rows)
        for label in ("Draft", "Improve")
    }
    base.require(semantic_counts == EXPECTED_SEMANTIC_COUNTS, "semantic support changed")
    needed = {
        item
        for row in rows
        for item in (row["better"], row["worse"], row["parent"])
    }
    vectors, sources, runs, tasks, configs, inventory = load_card_projection(cards_path, needed)
    base.require(
        all(tasks[row["parent"]] == row["task"] for row in rows),
        "pair parent task differs from decision task",
    )
    super_by_row, integrity = base.validate_and_close_components(rows, runs, tasks, configs)
    folds, fold_receipt = base.assign_folds(rows, super_by_row)
    isolation = base.fold_isolation(rows, folds, runs, super_by_row)
    matrices, feature_receipt = feature_matrices(rows, vectors, sources)
    learned, model_receipts, antisymmetry = oof_margins(matrices, folds)

    random_margin = []
    for row in rows:
        left, right = sorted((row["better"], row["worse"]))
        selected = (left, right)[zlib.crc32((left + "|" + right).encode()) & 1]
        random_margin.append(1.0 if selected == row["better"] else -1.0)
    margins = {
        "random_hash": np.asarray(random_margin, dtype=np.float64),
        **learned,
        "orientation_oracle": np.ones(len(rows), dtype=np.float64),
    }
    metrics = all_metrics(rows, semantics, margins)
    combined_delta = delta_metrics(
        rows, semantics, margins["child_plus_transition"], margins["child_code"]
    )
    transition_delta = delta_metrics(
        rows, semantics, margins["transition_only"], margins["child_code"]
    )

    controls = {
        "random_all_subset_task_parent_cis_contain_half": all(
            receipt["task_clustered"]["ci95"][0] <= .5 <= receipt["task_clustered"]["ci95"][1]
            and receipt["parent_clustered"]["ci95"][0] <= .5 <= receipt["parent_clustered"]["ci95"][1]
            for receipt in metrics["random_hash"].values()
        ),
        "orientation_all_subsets_exact": all(
            receipt["micro_accuracy"] == 1.0 for receipt in metrics["orientation_oracle"].values()
        ),
        "learned_full_coverage": all(
            metrics[arm][subset]["coverage"] == 1.0 for arm in ARMS for subset in SUBSETS
        ),
        "learned_no_ties": all(
            metrics[arm][subset]["ties"] == 0 for arm in ARMS for subset in SUBSETS
        ),
        "all_antisymmetric": max(antisymmetry.values()) <= 1e-12,
        "all_fold_isolation_zero": all(
            value == 0
            for receipt in isolation
            for key, value in receipt.items()
            if key.endswith("_overlap")
        ),
    }
    merged = combined_delta["merged"]
    draft = combined_delta["Draft"]
    improve = combined_delta["Improve"]
    combined_improve = metrics["child_plus_transition"]["Improve"]
    combined_merged = metrics["child_plus_transition"]["merged"]
    effect_gates = {
        "merged_paired_task_parent_ci_above_zero": lower_above(merged, 0.0),
        "merged_all_loto_positive": merged["minimum_leave_one_task_out_task_macro_delta"] > 0,
        "merged_combined_task_parent_chance_ci_above_half": lower_above(combined_merged, .5),
        "improve_paired_task_parent_ci_above_zero": lower_above(improve, 0.0),
        "improve_combined_task_parent_chance_ci_above_half": lower_above(combined_improve, .5),
        "draft_task_macro_delta_ge_minus_one_point": draft["task_macro_delta"] >= -.01,
        "draft_task_macro_delta_ge_minus_half_point": draft["task_macro_delta"] >= -.005,
        "improve_task_macro_delta_ge_minus_half_point": improve["task_macro_delta"] >= -.005,
        "draft_paired_task_parent_ci_above_zero": lower_above(draft, 0.0),
    }
    valid = all(controls.values())
    canonical = valid and all(
        effect_gates[name]
        for name in (
            "merged_paired_task_parent_ci_above_zero",
            "merged_all_loto_positive",
            "improve_paired_task_parent_ci_above_zero",
            "improve_combined_task_parent_chance_ci_above_half",
            "draft_task_macro_delta_ge_minus_one_point",
        )
    )
    pooled = valid and all(
        effect_gates[name]
        for name in (
            "merged_paired_task_parent_ci_above_zero",
            "merged_all_loto_positive",
            "merged_combined_task_parent_chance_ci_above_half",
            "draft_task_macro_delta_ge_minus_half_point",
            "improve_task_macro_delta_ge_minus_half_point",
        )
    )
    draft_only = (
        valid
        and effect_gates["draft_paired_task_parent_ci_above_zero"]
        and not effect_gates["improve_paired_task_parent_ci_above_zero"]
    )
    if not valid:
        status = "INVALID"
    elif canonical:
        status = "CANONICAL_TRANSITION_POSITIVE_PENDING_INDEPENDENT_VERIFICATION"
    elif pooled:
        status = "POOLED_TRANSITION_POSITIVE_PENDING_INDEPENDENT_VERIFICATION"
    elif draft_only:
        status = "DRAFT_ONLY_CONSTRUCTION_SIGNAL_PENDING_INDEPENDENT_VERIFICATION"
    else:
        status = "NO_ROBUST_TRANSITION_GAIN_PENDING_INDEPENDENT_VERIFICATION"

    summary = {
        "protocol": PROTOCOL,
        "status": status,
        "inputs": {
            **{
                role: {"sha256": base.EXPECTED[role][0], "bytes": base.EXPECTED[role][1]}
                for role in ("cards", "train", "dev")
            },
            **{
                role: {"sha256": EXPECTED_SEMANTIC[role][0], "bytes": EXPECTED_SEMANTIC[role][1]}
                for role in ("draft", "improve")
            },
        },
        "forbidden_inputs_opened": {
            "heldout_test": False,
            "tfidf": False,
            "prospective": False,
            "execution_outcome": False,
        },
        "card_inventory": inventory,
        "all_parent_tasks_match": True,
        "semantic_counts": semantic_counts,
        "integrity": integrity,
        "folds": {**fold_receipt, "isolation": isolation},
        "features": feature_receipt,
        "models": {
            "parameters": {
                "loss": "log_loss",
                "max_iter": 300,
                "learning_rate": .08,
                "max_leaf_nodes": 31,
                "max_depth": None,
                "min_samples_leaf": 20,
                "l2_regularization": 0.0,
                "early_stopping": False,
                "random_state": 7,
            },
            "fold_receipts": model_receipts,
            "anti_symmetry_max_abs": antisymmetry,
        },
        "metrics": metrics,
        "paired_deltas": {
            "child_plus_transition_minus_child_code": combined_delta,
            "transition_only_minus_child_code": transition_delta,
        },
        "controls": controls,
        "effect_gates": effect_gates,
        "producer_valid": valid,
        "pending_independent_verification": valid,
        "positive_claim_allowed": False,
        "bootstrap": {"replicates": REPS, "task_seed": TASK_SEED, "parent_seed": PARENT_SEED},
    }
    pair_rows = []
    for model in MODELS:
        credits = correctness(margins[model])
        for index, (row, margin, credit, fold) in enumerate(
            zip(rows, margins[model], credits, folds)
        ):
            pair_rows.append(
                {
                    "model": model,
                    "index": index,
                    "source_split": row["intask_split"],
                    "semantic": semantics[base.pair_key(row)],
                    "task": row["task"],
                    "parent": row["parent"],
                    "better": row["better"],
                    "worse": row["worse"],
                    "pair_component_id": row["pair_component_id"],
                    "parent_closed_supercomponent_id": super_by_row[base.compact(base.pair_key(row))],
                    "fold": int(fold),
                    "margin": float(margin),
                    "correct_credit": float(credit),
                    "tie": bool(margin == 0),
                }
            )
    return summary, pair_rows


def write_outputs(output: Path, summary: dict[str, Any], pair_rows: list[dict[str, Any]]) -> None:
    base.require(not output.exists(), "output directory already exists")
    json.dumps(summary, allow_nan=False)
    for row in pair_rows:
        json.dumps(row, allow_nan=False)
    output.mkdir(parents=True)
    (output / "summary.json").write_bytes(base.canonical(summary))
    with (output / "per_pair.jsonl").open("x", encoding="utf-8", newline="\n") as handle:
        for row in pair_rows:
            handle.write(base.compact(row) + "\n")
    manifest = {
        name: base.sha256_file(output / name)
        for name in ("summary.json", "per_pair.jsonl")
    }
    (output / "artifact_manifest.json").write_bytes(base.canonical(manifest))


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ("cards", "train", "dev", "draft", "improve", "output"):
        parser.add_argument(name, type=Path)
    args = parser.parse_args()
    result = analyze(args.cards, args.train, args.dev, args.draft, args.improve)
    write_outputs(args.output, *result)
    print(json.dumps(result[0], indent=2, sort_keys=True, ensure_ascii=False, allow_nan=False))


if __name__ == "__main__":
    main()
