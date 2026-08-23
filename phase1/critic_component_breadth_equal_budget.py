"""Equal-pair-budget comparison of broad versus concentrated component supervision."""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import math
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any

import numpy as np
from scipy import sparse
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.linear_model import LogisticRegression


PROTOCOL = "critic-component-breadth-equal-pair-budget-v1"
CONTRACT_SHA256 = "1dc28d105922741d0c6a8263d9b2ebd2566d1a28de3dec1eb8f490116f7e6316"
EXPECTED = {
    "cards": ("5fd24c8e545a67e1048f8a67b23bcb64605b9ad584a4fbaa44aa1b1f1b6e1afb", 604190866),
    "train": ("0ec49d76a896accf8e85a2556ca7ed12b9379b1867247d99c6be5e4c83bea98e", 3208089),
    "dev": ("3b3fb53f84277e935c66d3b3d1646d7a7d33624fb916e3f9bcc15f689904cfa4", 376635),
}


class BreadthError(RuntimeError):
    """Raised when a frozen protocol invariant fails."""


def canonical(value: Any) -> bytes:
    return (json.dumps(value, indent=2, sort_keys=True, ensure_ascii=False) + "\n").encode()


def compact(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()


def verify_contract(path: Path) -> dict[str, Any]:
    if sha256_file(path) != CONTRACT_SHA256:
        raise BreadthError("contract identity mismatch")
    contract = json.loads(path.read_text(encoding="utf-8"))
    if contract.get("protocol") != PROTOCOL:
        raise BreadthError("contract protocol mismatch")
    return contract


def verify_input(path: Path, role: str) -> None:
    expected_hash, expected_bytes = EXPECTED[role]
    if not path.is_file() or path.stat().st_size != expected_bytes or sha256_file(path) != expected_hash:
        raise BreadthError(f"{role} input identity mismatch")


def pair_identity(row: dict[str, Any]) -> str:
    try:
        left, right = sorted((row["better"], row["worse"]))
        values = row["task"], row["parent"], left, right
    except (KeyError, TypeError, ValueError) as error:
        raise BreadthError("invalid pair identity") from error
    if not all(isinstance(value, str) and value for value in values) or left == right:
        raise BreadthError("invalid pair identity")
    return "|".join(values)


def pair_key(row: dict[str, Any]) -> tuple[str, str, str, str]:
    left, right = sorted((row["better"], row["worse"]))
    return row["task"], row["parent"], left, right


def read_pairs(path: Path, split: str) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    identities: set[str] = set()
    with path.open(encoding="utf-8") as handle:
        for line_number, line in enumerate(handle, 1):
            if not line.strip():
                raise BreadthError(f"blank row at {path.name}:{line_number}")
            row = json.loads(line)
            if not isinstance(row, dict) or row.get("intask_split") != split:
                raise BreadthError(f"invalid {split} row")
            if (
                row.get("outer_intask_split") != "train"
                or row.get("train_dev_protocol") != "pair-graph-component-train-dev-split-v1"
                or row.get("train_dev_seed") != 20260821
                or row.get("train_dev_target_numerator") != 1
                or row.get("train_dev_target_denominator") != 10
                or not isinstance(row.get("pair_component_id"), str)
                or len(row["pair_component_id"]) != 64
            ):
                raise BreadthError("component split receipt mismatch")
            identity = pair_identity(row)
            if identity in identities:
                raise BreadthError("duplicate unordered pair")
            identities.add(identity)
            rows.append(row)
    if not rows:
        raise BreadthError(f"empty {split} pool")
    return rows


def load_cards(
    path: Path, needed: set[str]
) -> tuple[dict[str, str], dict[str, str], dict[str, tuple[Any, ...]], dict[str, int]]:
    grouped = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(grouped, dict):
        raise BreadthError("cards root is not grouped")
    codes: dict[str, str] = {}
    runs: dict[str, str] = {}
    configs: dict[str, tuple[Any, ...]] = {}
    seen: set[str] = set()
    total = 0
    for run_id, cards in grouped.items():
        if not isinstance(run_id, str) or not run_id or not isinstance(cards, list):
            raise BreadthError("invalid card group")
        for card in cards:
            total += 1
            if not isinstance(card, dict) or not isinstance(card.get("id"), str) or card["id"] in seen:
                raise BreadthError("invalid or duplicate card")
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
                raise BreadthError("needed card lacks code or provenance")
            codes[card_id] = card["code"]
            runs[card_id] = run_id
            configs[card_id] = config
    if set(codes) != needed:
        raise BreadthError("pair endpoint missing from cards")
    return codes, runs, configs, {"cards": total, "run_groups": len(grouped), "needed_cards": len(needed)}


def validate_inputs(
    train: list[dict[str, Any]],
    dev: list[dict[str, Any]],
    runs: dict[str, str],
    configs: dict[str, tuple[Any, ...]],
) -> dict[str, Any]:
    keys = {"train": {pair_key(row) for row in train}, "dev": {pair_key(row) for row in dev}}
    endpoints = {
        split: {endpoint for key in split_keys for endpoint in key[2:]}
        for split, split_keys in keys.items()
    }
    run_sets = {split: {runs[endpoint] for endpoint in values} for split, values in endpoints.items()}
    if keys["train"] & keys["dev"] or endpoints["train"] & endpoints["dev"] or run_sets["train"] & run_sets["dev"]:
        raise BreadthError("train/dev pair, endpoint, or physical-run overlap")
    component_split: dict[str, str] = {}
    component_task: dict[str, str] = {}
    for split, rows in (("train", train), ("dev", dev)):
        for row in rows:
            component = row["pair_component_id"]
            if component in component_split and component_split[component] != split:
                raise BreadthError("component crosses train/dev")
            if component in component_task and component_task[component] != row["task"]:
                raise BreadthError("component crosses tasks")
            component_split[component] = split
            component_task[component] = row["task"]
            if configs[row["better"]] != configs[row["worse"]] or configs[row["better"]][0] != row["task"]:
                raise BreadthError("pair violates exact configuration")
    return {
        "train_pairs": len(train),
        "dev_pairs": len(dev),
        "train_tasks": len({row["task"] for row in train}),
        "dev_tasks": len({row["task"] for row in dev}),
        "train_components": sum(split == "train" for split in component_split.values()),
        "dev_components": sum(split == "dev" for split in component_split.values()),
        "train_runs": len(run_sets["train"]),
        "dev_runs": len(run_sets["dev"]),
        "train_dev_pair_overlap": 0,
        "train_dev_endpoint_overlap": 0,
        "train_dev_physical_run_overlap": 0,
    }


def selection_rank(seed: int, arm: str, value: str) -> str:
    return hashlib.sha256(f"{seed}|{arm}|{value}".encode()).hexdigest()


def group_by_task_component(rows: list[dict[str, Any]]) -> dict[str, dict[str, list[dict[str, Any]]]]:
    grouped: dict[str, dict[str, list[dict[str, Any]]]] = defaultdict(lambda: defaultdict(list))
    for row in rows:
        grouped[row["task"]][row["pair_component_id"]].append(row)
    return grouped


def choose_broad(groups: dict[str, list[dict[str, Any]]], target: int, seed: int) -> list[dict[str, Any]]:
    components = sorted(groups, key=lambda item: selection_rank(seed, "broad-component", item))
    selected = [
        min(groups[component], key=lambda row: selection_rank(seed, "broad-floor", pair_identity(row)))
        for component in components[: min(target, len(components))]
    ]
    selected_ids = {pair_identity(row) for row in selected}
    remaining = [
        row
        for component in sorted(groups)
        for row in groups[component]
        if pair_identity(row) not in selected_ids
    ]
    remaining.sort(key=lambda row: selection_rank(seed, "broad-fill", pair_identity(row)))
    selected.extend(remaining[: target - len(selected)])
    return selected


def choose_concentrated(groups: dict[str, list[dict[str, Any]]], target: int, seed: int) -> list[dict[str, Any]]:
    components = sorted(
        groups,
        key=lambda item: (-len(groups[item]), selection_rank(seed, "concentrated-component", item)),
    )
    selected: list[dict[str, Any]] = []
    for component in components:
        needed = target - len(selected)
        if needed <= 0:
            break
        rows = sorted(
            groups[component],
            key=lambda row: selection_rank(seed, "concentrated-pair", pair_identity(row)),
        )
        selected.extend(rows[:needed])
    return selected


def choose_random(groups: dict[str, list[dict[str, Any]]], target: int, seed: int) -> list[dict[str, Any]]:
    rows = [row for component in sorted(groups) for row in groups[component]]
    rows.sort(key=lambda row: selection_rank(seed, "random-pair", pair_identity(row)))
    return rows[:target]


def build_selections(
    train: list[dict[str, Any]], dev: list[dict[str, Any]], contract: dict[str, Any]
) -> tuple[dict[tuple[int, str], list[dict[str, Any]]], list[dict[str, Any]], list[str]]:
    grouped = group_by_task_component(train)
    dev_tasks = {row["task"] for row in dev}
    fraction = contract["selection"]["fraction_per_task"]
    selections: dict[tuple[int, str], list[dict[str, Any]]] = {}
    task_receipts: list[dict[str, Any]] = []
    for seed in contract["selection"]["seeds"]:
        for task in sorted(grouped):
            groups = grouped[task]
            total = sum(len(rows) for rows in groups.values())
            target = math.ceil(fraction * total)
            arms = {
                "broad": choose_broad(groups, target, seed),
                "concentrated": choose_concentrated(groups, target, seed),
                "random": choose_random(groups, target, seed),
            }
            budget_hashes = set()
            component_counts = {}
            for arm, rows in arms.items():
                identities = [pair_identity(row) for row in rows]
                if len(rows) != target or len(set(identities)) != target:
                    raise BreadthError("pair budget or uniqueness mismatch")
                selections.setdefault((seed, arm), []).extend(rows)
                budget_hashes.add(len(rows))
                component_counts[arm] = len({row["pair_component_id"] for row in rows})
            if budget_hashes != {target}:
                raise BreadthError("per-task arm budget mismatch")
            task_receipts.append(
                {
                    "seed": seed,
                    "task": task,
                    "dev_supported": task in dev_tasks,
                    "total_pairs": total,
                    "target_pairs": target,
                    "available_components": len(groups),
                    "broad_components": component_counts["broad"],
                    "concentrated_components": component_counts["concentrated"],
                    "random_components": component_counts["random"],
                    "breadth_informative": component_counts["broad"] > component_counts["concentrated"],
                }
            )
    receipts_by_task: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for receipt in task_receipts:
        receipts_by_task[receipt["task"]].append(receipt)
    informative = sorted(
        task
        for task, receipts in receipts_by_task.items()
        if len(receipts) == len(contract["selection"]["seeds"])
        and all(row["dev_supported"] and row["breadth_informative"] for row in receipts)
    )
    return selections, task_receipts, informative


def selection_receipt(
    seed: int, arm: str, rows: list[dict[str, Any]], runs: dict[str, str]
) -> dict[str, Any]:
    task_counts = Counter(row["task"] for row in rows)
    identities = sorted(pair_identity(row) for row in rows)
    return {
        "selection_seed": seed,
        "arm": arm,
        "pairs": len(rows),
        "tasks": len(task_counts),
        "task_pair_budget_sha256": hashlib.sha256(
            ("\n".join(f"{task}|{task_counts[task]}" for task in sorted(task_counts)) + "\n").encode()
        ).hexdigest(),
        "components": len({row["pair_component_id"] for row in rows}),
        "endpoints": len({endpoint for row in rows for endpoint in (row["better"], row["worse"])}),
        "runs": len({runs[endpoint] for row in rows for endpoint in (row["better"], row["worse"])}),
        "unordered_pairs_sha256": hashlib.sha256(("\n".join(identities) + "\n").encode()).hexdigest(),
    }


def matrix_indices(rows: list[dict[str, Any]], positions: dict[str, int]) -> tuple[np.ndarray, np.ndarray]:
    return (
        np.fromiter((positions[row["better"]] for row in rows), dtype=np.int64),
        np.fromiter((positions[row["worse"]] for row in rows), dtype=np.int64),
    )


def fit_arm(
    train_rows: list[dict[str, Any]],
    dev: list[dict[str, Any]],
    codes: dict[str, str],
    runs: dict[str, str],
) -> dict[str, Any]:
    train_ids = sorted({endpoint for row in train_rows for endpoint in (row["better"], row["worse"])})
    dev_ids = sorted({endpoint for row in dev for endpoint in (row["better"], row["worse"])})
    card_ids = sorted(set(train_ids) | set(dev_ids))
    positions = {card_id: index for index, card_id in enumerate(card_ids)}
    vectorizer = TfidfVectorizer(
        analyzer="char_wb",
        ngram_range=(3, 5),
        max_features=30000,
        min_df=3,
        sublinear_tf=True,
        dtype=np.float64,
    )
    vectorizer.fit([codes[card_id][:20000] for card_id in train_ids])
    matrix = vectorizer.transform([codes[card_id][:20000] for card_id in card_ids]).tocsr()
    train_better, train_worse = matrix_indices(train_rows, positions)
    difference = matrix[train_better] - matrix[train_worse]
    design = sparse.vstack((difference, -difference), format="csr")
    labels = np.concatenate((np.ones(len(train_rows), dtype=np.int8), np.zeros(len(train_rows), dtype=np.int8)))
    model = LogisticRegression(C=0.5, max_iter=1500, solver="lbfgs", random_state=0).fit(design, labels)
    if int(model.n_iter_[0]) >= 1500 or not np.isfinite(model.coef_).all() or not np.isfinite(model.intercept_).all():
        raise BreadthError("logistic regression convergence/finite gate failed")
    weights = np.asarray(model.coef_, dtype=np.float64).reshape(-1)
    dev_better, dev_worse = matrix_indices(dev, positions)
    dev_difference = matrix[dev_better] - matrix[dev_worse]
    margins = np.asarray(dev_difference.dot(weights), dtype=np.float64).reshape(-1)
    reverse = np.asarray((-dev_difference).dot(weights), dtype=np.float64).reshape(-1)
    if margins.shape != (len(dev),) or not np.isfinite(margins).all():
        raise BreadthError("invalid dev margins")
    anti_symmetry = float(np.max(np.abs(margins + reverse)))
    if anti_symmetry != 0.0:
        raise BreadthError("pair margin is not exactly antisymmetric")
    losses = np.logaddexp(0.0, -margins)
    probabilities = np.exp(-losses)
    credits = np.where(margins > 0, 1.0, np.where(margins < 0, 0.0, 0.5))
    task_metrics: dict[str, dict[str, float | int]] = {}
    for task in sorted({row["task"] for row in dev}):
        mask = np.asarray([row["task"] == task for row in dev], dtype=bool)
        task_metrics[task] = {
            "pairs": int(mask.sum()),
            "log_loss": float(np.mean(losses[mask])),
            "accuracy": float(np.mean(credits[mask])),
        }
    pair_rows = [
        {
            "index": index,
            "task": row["task"],
            "parent": row["parent"],
            "better": row["better"],
            "worse": row["worse"],
            "margin": float(margin),
            "probability_better": float(probability),
            "log_loss": float(loss),
            "accuracy_credit": float(credit),
        }
        for index, (row, margin, probability, loss, credit) in enumerate(
            zip(dev, margins, probabilities, losses, credits)
        )
    ]
    return {
        "metrics": {
            "task_macro_log_loss": float(np.mean([item["log_loss"] for item in task_metrics.values()])),
            "task_macro_accuracy": float(np.mean([item["accuracy"] for item in task_metrics.values()])),
            "pair_micro_log_loss": float(np.mean(losses)),
            "pair_micro_accuracy": float(np.mean(credits)),
            "ties": int(np.sum(margins == 0)),
        },
        "task_metrics": task_metrics,
        "pair_rows": pair_rows,
        "fit_receipt": {
            "train_pairs": len(train_rows),
            "train_endpoints": len(train_ids),
            "train_runs": len({runs[endpoint] for endpoint in train_ids}),
            "train_components": len({row["pair_component_id"] for row in train_rows}),
            "train_tasks": len({row["task"] for row in train_rows}),
            "vocabulary_size": len(vectorizer.vocabulary_),
            "lr_iterations": int(model.n_iter_[0]),
            "lr_intercept": float(model.intercept_[0]),
            "coef_l2": float(np.linalg.norm(weights)),
            "anti_symmetry_max_abs": anti_symmetry,
        },
    }


def task_bootstrap(values: np.ndarray, contract: dict[str, Any]) -> list[float]:
    config = contract["bootstrap"]
    rng = np.random.default_rng(config["seed"])
    draws = rng.integers(0, len(values), size=(config["replicates"], len(values)))
    estimates = np.mean(values[draws], axis=1)
    interval = np.quantile(estimates, [0.025, 0.975], method="linear")
    return [float(interval[0]), float(interval[1])]


def evaluate(matrix: dict[tuple[int, str], dict[str, Any]], contract: dict[str, Any]) -> dict[str, Any]:
    seeds = contract["selection"]["seeds"]
    arms = ("broad", "concentrated", "random")
    tasks = sorted(matrix[(seeds[0], "broad")]["task_metrics"])
    mean_arms = [
        {
            "arm": arm,
            "task_macro_log_loss": float(np.mean([matrix[(seed, arm)]["metrics"]["task_macro_log_loss"] for seed in seeds])),
            "task_macro_accuracy": float(np.mean([matrix[(seed, arm)]["metrics"]["task_macro_accuracy"] for seed in seeds])),
        }
        for arm in arms
    ]
    loss_delta = np.asarray(
        [
            float(np.mean([matrix[(seed, "broad")]["task_metrics"][task]["log_loss"] for seed in seeds]))
            - float(np.mean([matrix[(seed, "concentrated")]["task_metrics"][task]["log_loss"] for seed in seeds]))
            for task in tasks
        ],
        dtype=np.float64,
    )
    accuracy_delta = np.asarray(
        [
            float(np.mean([matrix[(seed, "broad")]["task_metrics"][task]["accuracy"] for seed in seeds]))
            - float(np.mean([matrix[(seed, "concentrated")]["task_metrics"][task]["accuracy"] for seed in seeds]))
            for task in tasks
        ],
        dtype=np.float64,
    )
    loss_ci = task_bootstrap(loss_delta, contract)
    accuracy_ci = task_bootstrap(accuracy_delta, contract)
    loss_loto = [float(np.mean(np.delete(loss_delta, index))) for index in range(len(tasks))]
    accuracy_loto = [float(np.mean(np.delete(accuracy_delta, index))) for index in range(len(tasks))]
    seed_contrasts = [
        {
            "seed": seed,
            "broad_minus_concentrated_log_loss": matrix[(seed, "broad")]["metrics"]["task_macro_log_loss"]
            - matrix[(seed, "concentrated")]["metrics"]["task_macro_log_loss"],
            "broad_minus_concentrated_accuracy": matrix[(seed, "broad")]["metrics"]["task_macro_accuracy"]
            - matrix[(seed, "concentrated")]["metrics"]["task_macro_accuracy"],
        }
        for seed in seeds
    ]
    proper_rule = contract["decision_rules"]["proper_score_positive"]
    top1_rule = contract["decision_rules"]["top1_positive"]
    proper_checks = {
        "all_seed_contrasts_negative": all(row["broad_minus_concentrated_log_loss"] < 0 for row in seed_contrasts),
        "point_effect_floor": float(np.mean(loss_delta)) <= proper_rule["point_broad_minus_concentrated_log_loss_lte"],
        "bootstrap_ci_high_below_zero": loss_ci[1] < proper_rule["bootstrap_ci95_high_broad_minus_concentrated_log_loss_lt"],
        "loto_all_negative": max(loss_loto) < proper_rule["leave_one_task_out_broad_minus_concentrated_log_loss_lt"],
    }
    top1_checks = {
        "all_seed_contrasts_positive": all(row["broad_minus_concentrated_accuracy"] > 0 for row in seed_contrasts),
        "point_effect_floor": float(np.mean(accuracy_delta)) >= top1_rule["point_broad_minus_concentrated_accuracy_gte"],
        "bootstrap_ci_low_above_zero": accuracy_ci[0] > top1_rule["bootstrap_ci95_low_broad_minus_concentrated_accuracy_gt"],
        "loto_all_positive": min(accuracy_loto) > top1_rule["leave_one_task_out_broad_minus_concentrated_accuracy_gt"],
    }
    descriptive = {}
    for metric in ("task_macro_log_loss", "task_macro_accuracy"):
        descriptive[f"broad_minus_random_{metric}"] = float(
            np.mean([matrix[(seed, "broad")]["metrics"][metric] - matrix[(seed, "random")]["metrics"][metric] for seed in seeds])
        )
        descriptive[f"random_minus_concentrated_{metric}"] = float(
            np.mean([matrix[(seed, "random")]["metrics"][metric] - matrix[(seed, "concentrated")]["metrics"][metric] for seed in seeds])
        )
    return {
        "mean_arms": mean_arms,
        "seed_contrasts": seed_contrasts,
        "broad_minus_concentrated": {
            "task_macro_log_loss": {
                "point": float(np.mean(loss_delta)),
                "ci95": loss_ci,
                "loto_min": min(loss_loto),
                "loto_max": max(loss_loto),
            },
            "task_macro_accuracy": {
                "point": float(np.mean(accuracy_delta)),
                "ci95": accuracy_ci,
                "loto_min": min(accuracy_loto),
                "loto_max": max(accuracy_loto),
            },
        },
        "random_arm_descriptive": descriptive,
        "proper_score_checks": proper_checks,
        "top1_checks": top1_checks,
        "proper_score_positive": all(proper_checks.values()),
        "top1_positive": all(top1_checks.values()),
        "any_predeclared_positive": all(proper_checks.values()) or all(top1_checks.values()),
    }


def structural_checks(
    integrity: dict[str, Any],
    receipts: list[dict[str, Any]],
    informative: list[str],
    contract: dict[str, Any],
) -> dict[str, bool]:
    gates = contract["structural_gates"]
    by_seed = {
        seed: {row["arm"]: row for row in receipts if row["selection_seed"] == seed}
        for seed in contract["selection"]["seeds"]
    }
    checks = {
        "train_pairs": integrity["train_pairs"] == gates["train_pairs_eq"],
        "dev_pairs": integrity["dev_pairs"] == gates["dev_pairs_eq"],
        "train_tasks": integrity["train_tasks"] == gates["train_tasks_eq"],
        "dev_tasks": integrity["dev_tasks"] == gates["dev_tasks_eq"],
        "train_components": integrity["train_components"] == gates["train_components_eq"],
        "zero_pair_overlap": integrity["train_dev_pair_overlap"] == gates["train_dev_pair_overlap_eq"],
        "zero_endpoint_overlap": integrity["train_dev_endpoint_overlap"] == gates["train_dev_endpoint_overlap_eq"],
        "zero_run_overlap": integrity["train_dev_physical_run_overlap"] == gates["train_dev_physical_run_overlap_eq"],
        "informative_dev_tasks": len(informative) >= gates["informative_dev_tasks_gte"],
        "per_arm_pair_budget": all(
            row["pairs"] == gates["per_arm_pairs_per_seed_eq"] for row in receipts
        ),
        "per_task_pair_budget_hash_equal": all(
            len({row["task_pair_budget_sha256"] for row in arm_map.values()}) == 1
            for arm_map in by_seed.values()
        ),
        "broad_components": all(
            arm_map["broad"]["components"] == gates["broad_components_per_seed_eq"]
            for arm_map in by_seed.values()
        ),
        "concentrated_components": all(
            arm_map["concentrated"]["components"] == gates["concentrated_components_per_seed_eq"]
            for arm_map in by_seed.values()
        ),
        "component_breadth_contrast": all(
            arm_map["broad"]["components"] - arm_map["concentrated"]["components"]
            >= gates["broad_minus_concentrated_components_per_seed_gte"]
            for arm_map in by_seed.values()
        ),
        "run_breadth_contrast": all(
            arm_map["broad"]["runs"] - arm_map["concentrated"]["runs"]
            >= gates["broad_minus_concentrated_runs_per_seed_gte"]
            for arm_map in by_seed.values()
        ),
    }
    if not all(checks.values()):
        raise BreadthError("structural gate failed before fit")
    return checks


def analyze(
    cards_path: Path, train_path: Path, dev_path: Path, contract_path: Path
) -> tuple[dict[str, Any], list[dict[str, Any]], list[dict[str, Any]], list[dict[str, Any]], list[dict[str, Any]]]:
    contract = verify_contract(contract_path)
    for role, path in (("cards", cards_path), ("train", train_path), ("dev", dev_path)):
        verify_input(path, role)
    train = read_pairs(train_path, "train")
    dev = read_pairs(dev_path, "dev")
    needed = {endpoint for rows in (train, dev) for row in rows for endpoint in (row["better"], row["worse"])}
    codes, runs, configs, card_inventory = load_cards(cards_path, needed)
    integrity = validate_inputs(train, dev, runs, configs)
    selections, task_receipts, informative = build_selections(train, dev, contract)
    receipts = [
        selection_receipt(seed, arm, selections[(seed, arm)], runs)
        for seed in contract["selection"]["seeds"]
        for arm in ("broad", "concentrated", "random")
    ]
    checks = structural_checks(integrity, receipts, informative, contract)
    matrix: dict[tuple[int, str], dict[str, Any]] = {}
    arm_rows: list[dict[str, Any]] = []
    task_rows: list[dict[str, Any]] = []
    pair_rows: list[dict[str, Any]] = []
    for seed in contract["selection"]["seeds"]:
        for arm in ("broad", "concentrated", "random"):
            fit = fit_arm(selections[(seed, arm)], dev, codes, runs)
            matrix[(seed, arm)] = fit
            receipt = next(row for row in receipts if row["selection_seed"] == seed and row["arm"] == arm)
            arm_rows.append({**receipt, **fit["fit_receipt"], **fit["metrics"]})
            task_rows.extend(
                {"selection_seed": seed, "arm": arm, "task": task, **values}
                for task, values in fit["task_metrics"].items()
            )
            pair_rows.extend(
                {"selection_seed": seed, "arm": arm, **row} for row in fit["pair_rows"]
            )
    decision = evaluate(matrix, contract)
    summary = {
        "protocol": PROTOCOL,
        "contract_sha256": CONTRACT_SHA256,
        "status": (
            "RETROSPECTIVE_DEV_COMPONENT_BREADTH_POSITIVE"
            if decision["any_predeclared_positive"]
            else "RETROSPECTIVE_DEV_COMPONENT_BREADTH_NO_UNLOCK"
        ),
        "evidence_level": contract["evidence_level"],
        "inputs": {role: {"sha256": EXPECTED[role][0], "bytes": EXPECTED[role][1]} for role in EXPECTED},
        "access_attestation": {
            "cards_container_full_json_parsed": True,
            "nonretained_card_fields_referenced": False,
            "raw_grade_as_feature_or_selection_signal": False,
            "pair_orientation_used_for_selection": False,
            "heldout_test_pairs_opened": False,
            "test_predictions_opened": False,
            "prospective_vault_opened": False,
            "score_channel_truth_opened": False,
            "gpu_jobs": 0,
            "api_calls": 0,
            "base_llm_updates": 0,
            "unique_cpu_critic_fits": len(matrix),
        },
        "card_inventory": card_inventory,
        "integrity": integrity,
        "informative_dev_tasks": informative,
        "structural_checks": checks,
        "selection_receipts": receipts,
        "decision": decision,
    }
    return summary, arm_rows, task_rows, pair_rows, task_receipts


def write_csv(path: Path, rows: list[dict[str, Any]]) -> None:
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)


def write_artifacts(
    output: Path,
    summary: dict[str, Any],
    arm_rows: list[dict[str, Any]],
    task_rows: list[dict[str, Any]],
    pair_rows: list[dict[str, Any]],
    selection_task_rows: list[dict[str, Any]],
) -> None:
    if output.exists():
        raise BreadthError("output already exists")
    output.mkdir(parents=True)
    (output / "summary.json").write_bytes(canonical(summary))
    write_csv(output / "arm_metrics.csv", arm_rows)
    write_csv(output / "per_task.csv", task_rows)
    write_csv(output / "selection_by_task.csv", selection_task_rows)
    with (output / "per_pair.jsonl").open("w", encoding="utf-8") as handle:
        for row in pair_rows:
            handle.write(compact(row) + "\n")
    artifact_names = ("summary.json", "arm_metrics.csv", "per_task.csv", "selection_by_task.csv", "per_pair.jsonl")
    artifacts = {
        name: {"sha256": sha256_file(output / name), "bytes": (output / name).stat().st_size}
        for name in artifact_names
    }
    manifest = {"protocol": f"{PROTOCOL}-artifact-manifest-v1", "contract_sha256": CONTRACT_SHA256, "artifacts": artifacts}
    (output / "artifact_manifest.json").write_bytes(canonical(manifest))


def arguments() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("cards", type=Path)
    parser.add_argument("train", type=Path)
    parser.add_argument("dev", type=Path)
    parser.add_argument("output", type=Path)
    parser.add_argument("--contract", type=Path, default=Path(__file__).with_name("critic_component_breadth_equal_budget_v1.json"))
    return parser.parse_args()


def main() -> None:
    args = arguments()
    result = analyze(args.cards, args.train, args.dev, args.contract)
    write_artifacts(args.output, *result)
    print(compact({"status": result[0]["status"], "decision": result[0]["decision"]}))


if __name__ == "__main__":
    main()
