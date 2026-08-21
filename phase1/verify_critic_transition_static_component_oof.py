"""Independent full-refit verifier for the parent-relative transition OOF audit."""

from __future__ import annotations

import argparse
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

from phase1 import verify_critic_static_source_component_oof as independent_base


PROTOCOL = "critic-parent-relative-transition-independent-verifier-v1"
PRODUCER_PROTOCOL = "critic-parent-relative-transition-component-oof-v1"
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
TRANSITION_NAMES = tuple(
    f"absolute_static_change__{name}" for name in independent_base.CODE
) + EDIT_NAMES


class TransitionVerificationError(RuntimeError):
    """Raised when the producer artifact differs from the independent refit."""


def demand(condition: bool, message: str) -> None:
    if not condition:
        raise TransitionVerificationError(message)


def semantic_file_identity(path: Path, role: str) -> None:
    digest, size = EXPECTED_SEMANTIC[role]
    demand(path.stat().st_size == size, f"{role} semantic size mismatch")
    demand(independent_base.file_hash(path) == digest, f"{role} semantic hash mismatch")


def load_semantics(draft: Path, improve: Path) -> dict[tuple[str, str, str, str], str]:
    output = {}
    for role, label, path in (("draft", "Draft", draft), ("improve", "Improve", improve)):
        semantic_file_identity(path, role)
        with path.open(encoding="utf-8") as handle:
            for number, line in enumerate(handle, 1):
                demand(bool(line.strip()), f"blank semantic line {number}")
                row = json.loads(line)
                demand(isinstance(row, dict), "semantic line is not an object")
                key = independent_base.identity(row)
                demand(key not in output, "semantic identity duplicated")
                output[key] = label
    return output


def cards_with_parent_source(path: Path, required: set[str]):
    grouped = json.loads(path.read_text(encoding="utf-8"))
    demand(isinstance(grouped, dict), "Cards root invalid")
    vectors = {}
    sources = {}
    run_of = {}
    task_of = {}
    config_of = {}
    observed = set()
    total = 0
    locations = {name: index for index, name in enumerate(independent_base.FEATURES)}
    code_locations = [locations[name] for name in independent_base.CODE]
    for run_id, cards in grouped.items():
        demand(isinstance(run_id, str) and isinstance(cards, list), "Cards group invalid")
        for card in cards:
            total += 1
            demand(
                isinstance(card, dict)
                and isinstance(card.get("id"), str)
                and card["id"] not in observed,
                "card identity invalid",
            )
            card_id = card["id"]
            observed.add(card_id)
            if card_id not in required:
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
                "needed provenance invalid",
            )
            extracted = independent_base.extract_features(card)
            demand(tuple(sorted(extracted)) == independent_base.FEATURES, "feature contract differs")
            full = np.asarray(
                [extracted[name] for name in independent_base.FEATURES], dtype=np.float64
            )
            source = card.get("code")
            demand(isinstance(source, str) and np.isfinite(full).all(), "source projection invalid")
            vectors[card_id] = full[code_locations]
            sources[card_id] = source
            run_of[card_id] = run_id
            task_of[card_id] = task
            config_of[card_id] = config
    demand(set(vectors) == required, "required endpoint or parent missing")
    return vectors, sources, run_of, task_of, config_of, {
        "cards": total,
        "run_groups": len(grouped),
        "needed_cards": len(required),
    }


def line_edit_projection(parent: str, child: str) -> np.ndarray:
    before = parent.splitlines()
    after = child.splitlines()
    opcodes = difflib.SequenceMatcher(None, before, after, autojunk=False).get_opcodes()
    additions = deletions = hunks = unchanged = 0
    for tag, before_start, before_end, after_start, after_end in opcodes:
        if tag == "equal":
            unchanged += before_end - before_start
        else:
            hunks += 1
            deletions += before_end - before_start
            additions += after_end - after_start
    values = np.asarray(
        [
            additions,
            deletions,
            hunks,
            unchanged / max(1, len(before)),
            unchanged / max(1, len(after)),
            abs(math.log1p(len(child)) - math.log1p(len(parent))),
        ],
        dtype=np.float64,
    )
    demand(values.shape == (6,) and np.isfinite(values).all(), "edit projection invalid")
    return values


def independent_matrices(rows, vectors, sources):
    transitions = {}
    child_matrix = []
    transition_matrix = []
    for row in rows:
        parent = row["parent"]
        for endpoint in (row["better"], row["worse"]):
            relation = endpoint, parent
            if relation not in transitions:
                static_change = np.abs(vectors[endpoint] - vectors[parent])
                transitions[relation] = np.r_[
                    static_change,
                    line_edit_projection(sources[parent], sources[endpoint]),
                ]
        child_matrix.append(vectors[row["better"]] - vectors[row["worse"]])
        transition_matrix.append(
            transitions[(row["better"], parent)] - transitions[(row["worse"], parent)]
        )
    child = np.asarray(child_matrix, dtype=np.float64)
    transition = np.asarray(transition_matrix, dtype=np.float64)
    combined = np.column_stack((child, transition))
    demand(
        child.shape == (len(rows), len(independent_base.CODE))
        and transition.shape == (len(rows), len(TRANSITION_NAMES))
        and combined.shape == (len(rows), len(independent_base.CODE) + len(TRANSITION_NAMES))
        and all(np.isfinite(item).all() for item in (child, transition, combined)),
        "independent matrix shape invalid",
    )
    matrices = {
        "child_code": child,
        "transition_only": transition,
        "child_plus_transition": combined,
    }
    receipt = {
        "child_names": list(independent_base.CODE),
        "transition_names": list(TRANSITION_NAMES),
        "unique_child_parent_relations": len(transitions),
        "matrix_shapes": {name: list(value.shape) for name, value in matrices.items()},
        "matrix_sha256": {
            name: independent_base.numeric_hash(value) for name, value in matrices.items()
        },
        "signed_parent_delta_excluded_because_pairwise_cancels": True,
        "all_features_pre_execution": True,
    }
    return matrices, receipt


def independent_oof(matrices, folds):
    margins = {name: np.full(len(folds), np.nan) for name in ARMS}
    receipts = {name: [] for name in ARMS}
    antisymmetry = {name: 0.0 for name in ARMS}
    for name in ARMS:
        values = matrices[name]
        for fold in range(independent_base.FOLDS):
            training = folds != fold
            evaluation = folds == fold
            fit_values = values[training]
            symmetric = np.vstack((fit_values, -fit_values))
            targets = np.concatenate(
                (np.ones(len(fit_values), dtype=np.int8), np.zeros(len(fit_values), dtype=np.int8))
            )
            estimator = HistGradientBoostingClassifier(
                loss="log_loss",
                max_iter=300,
                learning_rate=.08,
                max_leaf_nodes=31,
                max_depth=None,
                min_samples_leaf=20,
                l2_regularization=0.0,
                early_stopping=False,
                random_state=7,
            )
            estimator.fit(symmetric, targets)
            demand(estimator.n_iter_ == 300, "independent GBM iteration mismatch")
            direct = estimator.decision_function(values[evaluation])
            reverse_direct = estimator.decision_function(-values[evaluation])
            forward = .5 * (direct - reverse_direct)
            reverse = .5 * (reverse_direct - direct)
            error = float(np.max(np.abs(forward + reverse)))
            demand(np.isfinite(forward).all() and error <= 1e-12, "independent antisymmetry failure")
            margins[name][evaluation] = forward
            antisymmetry[name] = max(antisymmetry[name], error)
            receipts[name].append(
                {
                    "fold": fold,
                    "fit_pairs": int(np.sum(training)),
                    "eval_pairs": int(np.sum(evaluation)),
                    "features": values.shape[1],
                    "n_iter": int(estimator.n_iter_),
                    "fit_matrix_sha256": independent_base.numeric_hash(fit_values),
                    "eval_margin_sha256": independent_base.numeric_hash(forward),
                    "anti_symmetry_max_abs": error,
                }
            )
        demand(np.isfinite(margins[name]).all(), "independent OOF incomplete")
    return margins, receipts, antisymmetry


def credit(values):
    demand(np.isfinite(values).all(), "non-finite independent metric")
    return np.where(values > 0, 1.0, np.where(values < 0, 0.0, 0.5))


def task_bootstrap(rows, values):
    task_names = sorted({row["task"] for row in rows})
    means = np.asarray(
        [np.mean([value for row, value in zip(rows, values) if row["task"] == name]) for name in task_names]
    )
    generator = np.random.default_rng(TASK_SEED)
    sampled = generator.integers(0, len(task_names), size=(REPS, len(task_names)))
    estimates = np.mean(means[sampled], axis=1)
    interval = np.quantile(estimates, [.025, .975], method="linear")
    return {
        "point": float(np.mean(means)),
        "ci95": list(map(float, interval)),
        "clusters": len(task_names),
        "replicates": REPS,
        "seed": TASK_SEED,
    }


def parent_bootstrap(rows, values):
    groups = defaultdict(list)
    for row, value in zip(rows, values):
        groups[(row["task"], row["parent"])].append(float(value))
    arrays = [np.asarray(groups[key]) for key in sorted(groups)]
    sums = np.asarray([np.sum(array) for array in arrays], dtype=np.float64)
    counts = np.asarray([len(array) for array in arrays], dtype=np.float64)
    generator = np.random.default_rng(PARENT_SEED)
    estimates = np.empty(REPS)
    completed = 0
    while completed < REPS:
        batch = min(256, REPS - completed)
        sampled = generator.integers(0, len(arrays), size=(batch, len(arrays)))
        estimates[completed:completed + batch] = np.sum(sums[sampled], axis=1) / np.sum(
            counts[sampled], axis=1
        )
        completed += batch
    interval = np.quantile(estimates, [.025, .975], method="linear")
    return {
        "point": float(np.mean(values)),
        "ci95": list(map(float, interval)),
        "clusters": len(arrays),
        "replicates": REPS,
        "seed": PARENT_SEED,
    }


def model_metric(rows, margins):
    values = credit(margins)
    task_result = task_bootstrap(rows, values)
    quantile_values = np.quantile(margins, [0, .1, .25, .5, .75, .9, 1], method="linear")
    return {
        "pairs": len(rows),
        "tasks": len({row["task"] for row in rows}),
        "parents": len({(row["task"], row["parent"]) for row in rows}),
        "coverage": float(np.mean(np.isfinite(margins))),
        "ties": int(np.sum(margins == 0)),
        "micro_accuracy": float(np.mean(values)),
        "task_macro_accuracy": task_result["point"],
        "task_clustered": task_result,
        "parent_clustered": parent_bootstrap(rows, values),
        "margin_quantiles": dict(
            zip(("q00", "q10", "q25", "q50", "q75", "q90", "q100"), map(float, quantile_values))
        ),
    }


def paired_metric(rows, values):
    task_result = task_bootstrap(rows, values)
    parent_result = parent_bootstrap(rows, values)
    task_means = {
        name: float(np.mean([value for row, value in zip(rows, values) if row["task"] == name]))
        for name in sorted({row["task"] for row in rows})
    }
    leave_one_out = {
        name: float(np.mean([value for other, value in task_means.items() if other != name]))
        for name in task_means
    }
    return {
        "pair_micro_delta": float(np.mean(values)),
        "task_macro_delta": task_result["point"],
        "task_clustered": task_result,
        "parent_clustered": parent_result,
        "per_task_delta": task_means,
        "leave_one_task_out_task_macro_delta": leave_one_out,
        "minimum_leave_one_task_out_task_macro_delta": min(leave_one_out.values()),
    }


def subset_positions(rows, semantics, subset):
    if subset == "merged":
        return np.arange(len(rows), dtype=np.int64)
    return np.asarray(
        [index for index, row in enumerate(rows) if semantics[independent_base.identity(row)] == subset]
    )


def metrics_for_all(rows, semantics, margins):
    result = {}
    for model in MODELS:
        result[model] = {}
        for subset in SUBSETS:
            positions = subset_positions(rows, semantics, subset)
            selected = [rows[index] for index in positions]
            result[model][subset] = model_metric(selected, margins[model][positions])
    return result


def compare_models(rows, semantics, first, second):
    differences = credit(first) - credit(second)
    result = {}
    for subset in SUBSETS:
        positions = subset_positions(rows, semantics, subset)
        selected = [rows[index] for index in positions]
        result[subset] = paired_metric(selected, differences[positions])
    return result


def both_lower_above(receipt, threshold):
    return (
        receipt["task_clustered"]["ci95"][0] > threshold
        and receipt["parent_clustered"]["ci95"][0] > threshold
    )


def independent_analysis(cards, train, dev, draft, improve):
    for role, path in (("cards", cards), ("train", train), ("dev", dev)):
        independent_base.identify(path, role)
    rows = independent_base.load_rows(train, "train") + independent_base.load_rows(dev, "dev")
    rows.sort(key=independent_base.identity)
    semantics = load_semantics(draft, improve)
    row_keys = {independent_base.identity(row) for row in rows}
    demand(row_keys.issubset(semantics), "independent semantic join incomplete")
    semantic_counts = {
        label: sum(semantics[independent_base.identity(row)] == label for row in rows)
        for label in ("Draft", "Improve")
    }
    demand(semantic_counts == EXPECTED_SEMANTIC_COUNTS, "independent semantic support differs")
    required = {
        item
        for row in rows
        for item in (row["better"], row["worse"], row["parent"])
    }
    vectors, sources, run_of, task_of, config_of, inventory = cards_with_parent_source(
        cards, required
    )
    demand(
        all(task_of[row["parent"]] == row["task"] for row in rows),
        "independent parent task differs from decision task",
    )
    super_for_pair, integrity = independent_base.parent_closed_units(
        rows, run_of, task_of, config_of
    )
    folds, fold_receipt = independent_base.independent_fold_assignment(rows, super_for_pair)
    isolation = independent_base.isolation_receipts(rows, folds, run_of, super_for_pair)
    matrices, feature_receipt = independent_matrices(rows, vectors, sources)
    learned, fit_receipts, antisymmetry = independent_oof(matrices, folds)

    random_values = []
    for row in rows:
        low, high = sorted((row["better"], row["worse"]))
        choice = (low, high)[zlib.crc32((low + "|" + high).encode()) & 1]
        random_values.append(1.0 if choice == row["better"] else -1.0)
    margins = {
        "random_hash": np.asarray(random_values),
        **learned,
        "orientation_oracle": np.ones(len(rows)),
    }
    metrics = metrics_for_all(rows, semantics, margins)
    combined_delta = compare_models(
        rows, semantics, margins["child_plus_transition"], margins["child_code"]
    )
    transition_delta = compare_models(
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
    merged, draft_delta, improve_delta = (
        combined_delta["merged"],
        combined_delta["Draft"],
        combined_delta["Improve"],
    )
    effect_gates = {
        "merged_paired_task_parent_ci_above_zero": both_lower_above(merged, 0.0),
        "merged_all_loto_positive": merged["minimum_leave_one_task_out_task_macro_delta"] > 0,
        "merged_combined_task_parent_chance_ci_above_half": both_lower_above(
            metrics["child_plus_transition"]["merged"], .5
        ),
        "improve_paired_task_parent_ci_above_zero": both_lower_above(improve_delta, 0.0),
        "improve_combined_task_parent_chance_ci_above_half": both_lower_above(
            metrics["child_plus_transition"]["Improve"], .5
        ),
        "draft_task_macro_delta_ge_minus_one_point": draft_delta["task_macro_delta"] >= -.01,
        "draft_task_macro_delta_ge_minus_half_point": draft_delta["task_macro_delta"] >= -.005,
        "improve_task_macro_delta_ge_minus_half_point": improve_delta["task_macro_delta"] >= -.005,
        "draft_paired_task_parent_ci_above_zero": both_lower_above(draft_delta, 0.0),
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
        "protocol": PRODUCER_PROTOCOL,
        "status": status,
        "inputs": {
            **{
                role: {
                    "sha256": independent_base.EXPECTED[role][0],
                    "bytes": independent_base.EXPECTED[role][1],
                }
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
            "fold_receipts": fit_receipts,
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
        correctness = credit(margins[model])
        for index, (row, margin, correct, fold) in enumerate(
            zip(rows, margins[model], correctness, folds)
        ):
            pair_rows.append(
                {
                    "model": model,
                    "index": index,
                    "source_split": row["intask_split"],
                    "semantic": semantics[independent_base.identity(row)],
                    "task": row["task"],
                    "parent": row["parent"],
                    "better": row["better"],
                    "worse": row["worse"],
                    "pair_component_id": row["pair_component_id"],
                    "parent_closed_supercomponent_id": super_for_pair[
                        independent_base.compact(independent_base.identity(row))
                    ],
                    "fold": int(fold),
                    "margin": float(margin),
                    "correct_credit": float(correct),
                    "tie": bool(margin == 0),
                }
            )
    return summary, pair_rows


def read_pair_artifact(path: Path):
    rows = []
    with path.open(encoding="utf-8") as handle:
        for line in handle:
            demand(bool(line.strip()), "blank producer pair row")
            row = json.loads(line)
            demand(isinstance(row, dict), "producer pair row invalid")
            rows.append(row)
    return rows


def verify(cards, train, dev, draft, improve, artifact):
    demand(artifact.is_dir(), "producer artifact directory missing")
    manifest_path = artifact / "artifact_manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    demand(
        manifest
        == {
            "summary.json": independent_base.file_hash(artifact / "summary.json"),
            "per_pair.jsonl": independent_base.file_hash(artifact / "per_pair.jsonl"),
        },
        "producer artifact manifest mismatch",
    )
    expected_summary, expected_pairs = independent_analysis(
        cards, train, dev, draft, improve
    )
    observed_summary = json.loads((artifact / "summary.json").read_text(encoding="utf-8"))
    observed_pairs = read_pair_artifact(artifact / "per_pair.jsonl")
    demand(observed_summary == expected_summary, "summary differs from independent refit")
    demand(observed_pairs == expected_pairs, "per-pair rows differ from independent refit")
    producer_status = observed_summary["status"]
    if producer_status.endswith("_PENDING_INDEPENDENT_VERIFICATION"):
        verified_status = producer_status.removesuffix("_PENDING_INDEPENDENT_VERIFICATION") + "_VERIFIED"
        positive_allowed = producer_status.startswith(("CANONICAL_", "POOLED_"))
    else:
        verified_status = "VERIFIED_INVALID"
        positive_allowed = False
    return {
        "protocol": PROTOCOL,
        "status": verified_status,
        "producer_status": producer_status,
        "producer_imported": False,
        "full_refit": True,
        "all_fields_exact": True,
        "summary_sha256": independent_base.file_hash(artifact / "summary.json"),
        "per_pair_sha256": independent_base.file_hash(artifact / "per_pair.jsonl"),
        "artifact_manifest_sha256": independent_base.file_hash(manifest_path),
        "positive_claim_allowed": positive_allowed,
        "verified_effect_gates": observed_summary["effect_gates"],
        "verified_controls": observed_summary["controls"],
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ("cards", "train", "dev", "draft", "improve", "artifact"):
        parser.add_argument(name, type=Path)
    args = parser.parse_args()
    receipt = verify(
        args.cards, args.train, args.dev, args.draft, args.improve, args.artifact
    )
    print(json.dumps(receipt, indent=2, sort_keys=True, ensure_ascii=False))


if __name__ == "__main__":
    main()
