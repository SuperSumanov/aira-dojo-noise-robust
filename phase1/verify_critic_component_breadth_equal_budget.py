"""Independent source-refit verifier for the equal-pair-budget component breadth experiment."""

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
SOURCE = {
    "cards": ("5fd24c8e545a67e1048f8a67b23bcb64605b9ad584a4fbaa44aa1b1f1b6e1afb", 604190866),
    "train": ("0ec49d76a896accf8e85a2556ca7ed12b9379b1867247d99c6be5e4c83bea98e", 3208089),
    "dev": ("3b3fb53f84277e935c66d3b3d1646d7a7d33624fb916e3f9bcc15f689904cfa4", 376635),
}


class VerificationError(RuntimeError):
    """Raised when independent reconstruction disagrees with the artifact."""


def canonical(value: Any) -> bytes:
    return (json.dumps(value, indent=2, sort_keys=True, ensure_ascii=False) + "\n").encode()


def file_hash(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()


def load_contract(path: Path) -> dict[str, Any]:
    if file_hash(path) != CONTRACT_SHA256:
        raise VerificationError("contract identity mismatch")
    contract = json.loads(path.read_text(encoding="utf-8"))
    if contract.get("protocol") != PROTOCOL:
        raise VerificationError("contract protocol mismatch")
    return contract


def attest(path: Path, role: str) -> None:
    expected_hash, expected_bytes = SOURCE[role]
    if not path.is_file() or path.stat().st_size != expected_bytes or file_hash(path) != expected_hash:
        raise VerificationError(f"{role} source mismatch")


def unordered_identity(row: dict[str, Any]) -> str:
    try:
        left, right = sorted((row["better"], row["worse"]))
        values = row["task"], row["parent"], left, right
    except (KeyError, TypeError, ValueError) as error:
        raise VerificationError("invalid pair identity") from error
    if not all(isinstance(value, str) and value for value in values) or left == right:
        raise VerificationError("invalid pair identity")
    return "|".join(values)


def unordered_key(row: dict[str, Any]) -> tuple[str, str, str, str]:
    left, right = sorted((row["better"], row["worse"]))
    return row["task"], row["parent"], left, right


def pair_file(path: Path, split: str) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    identities: set[str] = set()
    with path.open(encoding="utf-8") as handle:
        for line in handle:
            if not line.strip():
                raise VerificationError("blank pair row")
            row = json.loads(line)
            if (
                not isinstance(row, dict)
                or row.get("intask_split") != split
                or row.get("outer_intask_split") != "train"
                or row.get("train_dev_protocol") != "pair-graph-component-train-dev-split-v1"
                or row.get("train_dev_seed") != 20260821
                or row.get("train_dev_target_numerator") != 1
                or row.get("train_dev_target_denominator") != 10
                or not isinstance(row.get("pair_component_id"), str)
                or len(row["pair_component_id"]) != 64
            ):
                raise VerificationError("pair split receipt mismatch")
            identity = unordered_identity(row)
            if identity in identities:
                raise VerificationError("duplicate unordered pair")
            identities.add(identity)
            rows.append(row)
    if not rows:
        raise VerificationError("empty pair source")
    return rows


def card_projection(
    path: Path, needed: set[str]
) -> tuple[dict[str, str], dict[str, str], dict[str, tuple[Any, ...]], dict[str, int]]:
    grouped = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(grouped, dict):
        raise VerificationError("invalid Cards root")
    code: dict[str, str] = {}
    run: dict[str, str] = {}
    config: dict[str, tuple[Any, ...]] = {}
    seen: set[str] = set()
    total = 0
    for run_id, cards in grouped.items():
        if not isinstance(run_id, str) or not run_id or not isinstance(cards, list):
            raise VerificationError("invalid Cards group")
        for card in cards:
            total += 1
            if not isinstance(card, dict) or not isinstance(card.get("id"), str) or card["id"] in seen:
                raise VerificationError("invalid or duplicate Card")
            card_id = card["id"]
            seen.add(card_id)
            if card_id not in needed:
                continue
            task_object = card.get("task")
            task = task_object.get("name") if isinstance(task_object, dict) else None
            values = (task, card.get("client"), card.get("hardware"), card.get("time_limit"), card.get("execution_timeout"))
            if (
                not isinstance(card.get("code"), str)
                or not all(isinstance(value, str) and value for value in values[:3])
                or not all(isinstance(value, int) for value in values[3:])
            ):
                raise VerificationError("needed Card projection invalid")
            code[card_id] = card["code"]
            run[card_id] = run_id
            config[card_id] = values
    if set(code) != needed:
        raise VerificationError("Card endpoint coverage mismatch")
    return code, run, config, {"cards": total, "run_groups": len(grouped), "needed_cards": len(needed)}


def integrity_receipt(
    train: list[dict[str, Any]],
    dev: list[dict[str, Any]],
    run: dict[str, str],
    config: dict[str, tuple[Any, ...]],
) -> dict[str, Any]:
    keys = {"train": {unordered_key(row) for row in train}, "dev": {unordered_key(row) for row in dev}}
    endpoints = {split: {item for key in keys[split] for item in key[2:]} for split in keys}
    runs = {split: {run[item] for item in endpoints[split]} for split in endpoints}
    if keys["train"] & keys["dev"] or endpoints["train"] & endpoints["dev"] or runs["train"] & runs["dev"]:
        raise VerificationError("train/dev isolation mismatch")
    placement: dict[str, tuple[str, str]] = {}
    for split, rows in (("train", train), ("dev", dev)):
        for row in rows:
            component = row["pair_component_id"]
            value = split, row["task"]
            if component in placement and placement[component] != value:
                raise VerificationError("component placement mismatch")
            placement[component] = value
            if config[row["better"]] != config[row["worse"]] or config[row["better"]][0] != row["task"]:
                raise VerificationError("exact configuration mismatch")
    return {
        "train_pairs": len(train),
        "dev_pairs": len(dev),
        "train_tasks": len({row["task"] for row in train}),
        "dev_tasks": len({row["task"] for row in dev}),
        "train_components": sum(split == "train" for split, _ in placement.values()),
        "dev_components": sum(split == "dev" for split, _ in placement.values()),
        "train_runs": len(runs["train"]),
        "dev_runs": len(runs["dev"]),
        "train_dev_pair_overlap": 0,
        "train_dev_endpoint_overlap": 0,
        "train_dev_physical_run_overlap": 0,
    }


def hashed(seed: int, arm: str, value: str) -> str:
    return hashlib.sha256(f"{seed}|{arm}|{value}".encode()).hexdigest()


def task_components(rows: list[dict[str, Any]]) -> dict[str, dict[str, list[dict[str, Any]]]]:
    result: dict[str, dict[str, list[dict[str, Any]]]] = defaultdict(lambda: defaultdict(list))
    for row in rows:
        result[row["task"]][row["pair_component_id"]].append(row)
    return result


def broad(groups: dict[str, list[dict[str, Any]]], target: int, seed: int) -> list[dict[str, Any]]:
    ordered = sorted(groups, key=lambda component: hashed(seed, "broad-component", component))
    rows = [
        min(groups[component], key=lambda row: hashed(seed, "broad-floor", unordered_identity(row)))
        for component in ordered[: min(target, len(ordered))]
    ]
    present = {unordered_identity(row) for row in rows}
    remainder = [
        row
        for component in sorted(groups)
        for row in groups[component]
        if unordered_identity(row) not in present
    ]
    remainder.sort(key=lambda row: hashed(seed, "broad-fill", unordered_identity(row)))
    return rows + remainder[: target - len(rows)]


def concentrated(groups: dict[str, list[dict[str, Any]]], target: int, seed: int) -> list[dict[str, Any]]:
    ordered = sorted(groups, key=lambda component: (-len(groups[component]), hashed(seed, "concentrated-component", component)))
    result: list[dict[str, Any]] = []
    for component in ordered:
        needed = target - len(result)
        if needed <= 0:
            break
        rows = sorted(groups[component], key=lambda row: hashed(seed, "concentrated-pair", unordered_identity(row)))
        result.extend(rows[:needed])
    return result


def random_rows(groups: dict[str, list[dict[str, Any]]], target: int, seed: int) -> list[dict[str, Any]]:
    rows = [row for component in sorted(groups) for row in groups[component]]
    rows.sort(key=lambda row: hashed(seed, "random-pair", unordered_identity(row)))
    return rows[:target]


def selections(
    train: list[dict[str, Any]], dev: list[dict[str, Any]], contract: dict[str, Any]
) -> tuple[dict[tuple[int, str], list[dict[str, Any]]], list[dict[str, Any]], list[str]]:
    grouped = task_components(train)
    dev_tasks = {row["task"] for row in dev}
    matrix: dict[tuple[int, str], list[dict[str, Any]]] = {}
    task_receipts: list[dict[str, Any]] = []
    for seed in contract["selection"]["seeds"]:
        for task in sorted(grouped):
            groups = grouped[task]
            total = sum(len(rows) for rows in groups.values())
            target = math.ceil(contract["selection"]["fraction_per_task"] * total)
            arms = {
                "broad": broad(groups, target, seed),
                "concentrated": concentrated(groups, target, seed),
                "random": random_rows(groups, target, seed),
            }
            counts = {}
            for arm, rows in arms.items():
                if len(rows) != target or len({unordered_identity(row) for row in rows}) != target:
                    raise VerificationError("selection budget mismatch")
                matrix.setdefault((seed, arm), []).extend(rows)
                counts[arm] = len({row["pair_component_id"] for row in rows})
            task_receipts.append(
                {
                    "seed": seed,
                    "task": task,
                    "dev_supported": task in dev_tasks,
                    "total_pairs": total,
                    "target_pairs": target,
                    "available_components": len(groups),
                    "broad_components": counts["broad"],
                    "concentrated_components": counts["concentrated"],
                    "random_components": counts["random"],
                    "breadth_informative": counts["broad"] > counts["concentrated"],
                }
            )
    by_task: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in task_receipts:
        by_task[row["task"]].append(row)
    informative = sorted(
        task
        for task, rows in by_task.items()
        if len(rows) == len(contract["selection"]["seeds"])
        and all(row["dev_supported"] and row["breadth_informative"] for row in rows)
    )
    return matrix, task_receipts, informative


def selection_receipt(seed: int, arm: str, rows: list[dict[str, Any]], run: dict[str, str]) -> dict[str, Any]:
    counts = Counter(row["task"] for row in rows)
    identities = sorted(unordered_identity(row) for row in rows)
    return {
        "selection_seed": seed,
        "arm": arm,
        "pairs": len(rows),
        "tasks": len(counts),
        "task_pair_budget_sha256": hashlib.sha256(
            ("\n".join(f"{task}|{counts[task]}" for task in sorted(counts)) + "\n").encode()
        ).hexdigest(),
        "components": len({row["pair_component_id"] for row in rows}),
        "endpoints": len({item for row in rows for item in (row["better"], row["worse"])}),
        "runs": len({run[item] for row in rows for item in (row["better"], row["worse"])}),
        "unordered_pairs_sha256": hashlib.sha256(("\n".join(identities) + "\n").encode()).hexdigest(),
    }


def positions(rows: list[dict[str, Any]], index: dict[str, int]) -> tuple[np.ndarray, np.ndarray]:
    return (
        np.fromiter((index[row["better"]] for row in rows), dtype=np.int64),
        np.fromiter((index[row["worse"]] for row in rows), dtype=np.int64),
    )


def refit(
    train_rows: list[dict[str, Any]],
    dev: list[dict[str, Any]],
    code: dict[str, str],
    run: dict[str, str],
) -> dict[str, Any]:
    train_cards = sorted({item for row in train_rows for item in (row["better"], row["worse"])})
    dev_cards = sorted({item for row in dev for item in (row["better"], row["worse"])})
    card_order = sorted(set(train_cards) | set(dev_cards))
    index = {card_id: offset for offset, card_id in enumerate(card_order)}
    encoder = TfidfVectorizer(
        analyzer="char_wb", ngram_range=(3, 5), max_features=30000,
        min_df=3, sublinear_tf=True, dtype=np.float64,
    )
    encoder.fit([code[card_id][:20000] for card_id in train_cards])
    vectors = encoder.transform([code[card_id][:20000] for card_id in card_order]).tocsr()
    positive, negative = positions(train_rows, index)
    differences = vectors[positive] - vectors[negative]
    design = sparse.vstack((differences, -differences), format="csr")
    labels = np.r_[np.ones(len(train_rows), dtype=np.int8), np.zeros(len(train_rows), dtype=np.int8)]
    classifier = LogisticRegression(C=0.5, max_iter=1500, solver="lbfgs", random_state=0).fit(design, labels)
    if int(classifier.n_iter_[0]) >= 1500 or not np.isfinite(classifier.coef_).all() or not np.isfinite(classifier.intercept_).all():
        raise VerificationError("independent refit convergence failure")
    weights = np.asarray(classifier.coef_, dtype=np.float64).ravel()
    better, worse = positions(dev, index)
    difference = vectors[better] - vectors[worse]
    margin = np.asarray(difference.dot(weights), dtype=np.float64).ravel()
    reverse = np.asarray((-difference).dot(weights), dtype=np.float64).ravel()
    if not np.isfinite(margin).all() or float(np.max(np.abs(margin + reverse))) != 0.0:
        raise VerificationError("independent margin failure")
    loss = np.logaddexp(0.0, -margin)
    probability = np.exp(-loss)
    credit = np.where(margin > 0, 1.0, np.where(margin < 0, 0.0, 0.5))
    by_task: dict[str, dict[str, float | int]] = {}
    for task in sorted({row["task"] for row in dev}):
        mask = np.asarray([row["task"] == task for row in dev], dtype=bool)
        by_task[task] = {
            "pairs": int(mask.sum()),
            "log_loss": float(np.mean(loss[mask])),
            "accuracy": float(np.mean(credit[mask])),
        }
    pairs = [
        {
            "index": offset,
            "task": row["task"],
            "parent": row["parent"],
            "better": row["better"],
            "worse": row["worse"],
            "margin": float(item_margin),
            "probability_better": float(item_probability),
            "log_loss": float(item_loss),
            "accuracy_credit": float(item_credit),
        }
        for offset, (row, item_margin, item_probability, item_loss, item_credit) in enumerate(
            zip(dev, margin, probability, loss, credit)
        )
    ]
    return {
        "metrics": {
            "task_macro_log_loss": float(np.mean([item["log_loss"] for item in by_task.values()])),
            "task_macro_accuracy": float(np.mean([item["accuracy"] for item in by_task.values()])),
            "pair_micro_log_loss": float(np.mean(loss)),
            "pair_micro_accuracy": float(np.mean(credit)),
            "ties": int(np.sum(margin == 0)),
        },
        "task_metrics": by_task,
        "pair_rows": pairs,
        "fit_receipt": {
            "train_pairs": len(train_rows),
            "train_endpoints": len(train_cards),
            "train_runs": len({run[item] for item in train_cards}),
            "train_components": len({row["pair_component_id"] for row in train_rows}),
            "train_tasks": len({row["task"] for row in train_rows}),
            "vocabulary_size": len(encoder.vocabulary_),
            "lr_iterations": int(classifier.n_iter_[0]),
            "lr_intercept": float(classifier.intercept_[0]),
            "coef_l2": float(np.linalg.norm(weights)),
            "anti_symmetry_max_abs": 0.0,
        },
    }


def confidence_interval(values: np.ndarray, contract: dict[str, Any]) -> list[float]:
    config = contract["bootstrap"]
    generator = np.random.default_rng(config["seed"])
    samples = generator.integers(0, len(values), size=(config["replicates"], len(values)))
    estimates = np.mean(values[samples], axis=1)
    limits = np.quantile(estimates, [0.025, 0.975], method="linear")
    return [float(limits[0]), float(limits[1])]


def decision(matrix: dict[tuple[int, str], dict[str, Any]], contract: dict[str, Any]) -> dict[str, Any]:
    seeds = contract["selection"]["seeds"]
    arms = ("broad", "concentrated", "random")
    tasks = sorted(matrix[(seeds[0], "broad")]["task_metrics"])
    means = [
        {
            "arm": arm,
            "task_macro_log_loss": float(np.mean([matrix[(seed, arm)]["metrics"]["task_macro_log_loss"] for seed in seeds])),
            "task_macro_accuracy": float(np.mean([matrix[(seed, arm)]["metrics"]["task_macro_accuracy"] for seed in seeds])),
        }
        for arm in arms
    ]
    loss_delta = np.asarray([
        float(np.mean([matrix[(seed, "broad")]["task_metrics"][task]["log_loss"] for seed in seeds]))
        - float(np.mean([matrix[(seed, "concentrated")]["task_metrics"][task]["log_loss"] for seed in seeds]))
        for task in tasks
    ])
    accuracy_delta = np.asarray([
        float(np.mean([matrix[(seed, "broad")]["task_metrics"][task]["accuracy"] for seed in seeds]))
        - float(np.mean([matrix[(seed, "concentrated")]["task_metrics"][task]["accuracy"] for seed in seeds]))
        for task in tasks
    ])
    loss_loto = [float(np.mean(np.delete(loss_delta, index))) for index in range(len(tasks))]
    accuracy_loto = [float(np.mean(np.delete(accuracy_delta, index))) for index in range(len(tasks))]
    contrasts = [
        {
            "seed": seed,
            "broad_minus_concentrated_log_loss": matrix[(seed, "broad")]["metrics"]["task_macro_log_loss"]
            - matrix[(seed, "concentrated")]["metrics"]["task_macro_log_loss"],
            "broad_minus_concentrated_accuracy": matrix[(seed, "broad")]["metrics"]["task_macro_accuracy"]
            - matrix[(seed, "concentrated")]["metrics"]["task_macro_accuracy"],
        }
        for seed in seeds
    ]
    loss_ci = confidence_interval(loss_delta, contract)
    accuracy_ci = confidence_interval(accuracy_delta, contract)
    proper_rule = contract["decision_rules"]["proper_score_positive"]
    top1_rule = contract["decision_rules"]["top1_positive"]
    proper_checks = {
        "all_seed_contrasts_negative": all(item["broad_minus_concentrated_log_loss"] < 0 for item in contrasts),
        "point_effect_floor": float(np.mean(loss_delta)) <= proper_rule["point_broad_minus_concentrated_log_loss_lte"],
        "bootstrap_ci_high_below_zero": loss_ci[1] < proper_rule["bootstrap_ci95_high_broad_minus_concentrated_log_loss_lt"],
        "loto_all_negative": max(loss_loto) < proper_rule["leave_one_task_out_broad_minus_concentrated_log_loss_lt"],
    }
    top1_checks = {
        "all_seed_contrasts_positive": all(item["broad_minus_concentrated_accuracy"] > 0 for item in contrasts),
        "point_effect_floor": float(np.mean(accuracy_delta)) >= top1_rule["point_broad_minus_concentrated_accuracy_gte"],
        "bootstrap_ci_low_above_zero": accuracy_ci[0] > top1_rule["bootstrap_ci95_low_broad_minus_concentrated_accuracy_gt"],
        "loto_all_positive": min(accuracy_loto) > top1_rule["leave_one_task_out_broad_minus_concentrated_accuracy_gt"],
    }
    descriptive = {}
    for metric in ("task_macro_log_loss", "task_macro_accuracy"):
        descriptive[f"broad_minus_random_{metric}"] = float(np.mean([
            matrix[(seed, "broad")]["metrics"][metric] - matrix[(seed, "random")]["metrics"][metric]
            for seed in seeds
        ]))
        descriptive[f"random_minus_concentrated_{metric}"] = float(np.mean([
            matrix[(seed, "random")]["metrics"][metric] - matrix[(seed, "concentrated")]["metrics"][metric]
            for seed in seeds
        ]))
    return {
        "mean_arms": means,
        "seed_contrasts": contrasts,
        "broad_minus_concentrated": {
            "task_macro_log_loss": {"point": float(np.mean(loss_delta)), "ci95": loss_ci, "loto_min": min(loss_loto), "loto_max": max(loss_loto)},
            "task_macro_accuracy": {"point": float(np.mean(accuracy_delta)), "ci95": accuracy_ci, "loto_min": min(accuracy_loto), "loto_max": max(accuracy_loto)},
        },
        "random_arm_descriptive": descriptive,
        "proper_score_checks": proper_checks,
        "top1_checks": top1_checks,
        "proper_score_positive": all(proper_checks.values()),
        "top1_positive": all(top1_checks.values()),
        "any_predeclared_positive": all(proper_checks.values()) or all(top1_checks.values()),
    }


def structure(
    integrity: dict[str, Any], receipts: list[dict[str, Any]], informative: list[str], contract: dict[str, Any]
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
        "per_arm_pair_budget": all(row["pairs"] == gates["per_arm_pairs_per_seed_eq"] for row in receipts),
        "per_task_pair_budget_hash_equal": all(len({row["task_pair_budget_sha256"] for row in arms.values()}) == 1 for arms in by_seed.values()),
        "broad_components": all(arms["broad"]["components"] == gates["broad_components_per_seed_eq"] for arms in by_seed.values()),
        "concentrated_components": all(arms["concentrated"]["components"] == gates["concentrated_components_per_seed_eq"] for arms in by_seed.values()),
        "component_breadth_contrast": all(
            arms["broad"]["components"] - arms["concentrated"]["components"] >= gates["broad_minus_concentrated_components_per_seed_gte"]
            for arms in by_seed.values()
        ),
        "run_breadth_contrast": all(
            arms["broad"]["runs"] - arms["concentrated"]["runs"] >= gates["broad_minus_concentrated_runs_per_seed_gte"]
            for arms in by_seed.values()
        ),
    }
    if not all(checks.values()):
        raise VerificationError("independent structural gate failure")
    return checks


def close_enough(expected: Any, observed: Any, location: str = "root") -> float:
    if isinstance(expected, dict):
        if not isinstance(observed, dict) or set(expected) != set(observed):
            raise VerificationError(f"mapping mismatch at {location}")
        return max((close_enough(value, observed[key], f"{location}.{key}") for key, value in expected.items()), default=0.0)
    if isinstance(expected, list):
        if not isinstance(observed, list) or len(expected) != len(observed):
            raise VerificationError(f"list mismatch at {location}")
        return max((close_enough(left, right, f"{location}[{index}]") for index, (left, right) in enumerate(zip(expected, observed))), default=0.0)
    if isinstance(expected, float):
        try:
            difference = abs(expected - float(observed))
        except (TypeError, ValueError) as error:
            raise VerificationError(f"numeric mismatch at {location}") from error
        if not np.isfinite(difference) or difference > 1e-12:
            raise VerificationError(f"numeric mismatch at {location}: {difference}")
        return difference
    if expected != observed:
        raise VerificationError(f"value mismatch at {location}")
    return 0.0


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open(encoding="utf-8", newline="") as handle:
        return list(csv.DictReader(handle))


def cast_row(actual: dict[str, str], expected: dict[str, Any]) -> dict[str, Any]:
    if set(actual) != set(expected):
        raise VerificationError("CSV field mismatch")
    result: dict[str, Any] = {}
    for key, value in expected.items():
        if isinstance(value, bool):
            result[key] = actual[key].lower() == "true"
        elif isinstance(value, int):
            result[key] = int(actual[key])
        elif isinstance(value, float):
            result[key] = float(actual[key])
        else:
            result[key] = actual[key]
    return result


def verify(
    cards_path: Path,
    train_path: Path,
    dev_path: Path,
    contract_path: Path,
    artifact_dir: Path,
) -> dict[str, Any]:
    contract = load_contract(contract_path)
    for role, path in (("cards", cards_path), ("train", train_path), ("dev", dev_path)):
        attest(path, role)
    expected_files = {
        "summary.json", "arm_metrics.csv", "per_task.csv", "selection_by_task.csv",
        "per_pair.jsonl", "artifact_manifest.json",
    }
    if not artifact_dir.is_dir() or {path.name for path in artifact_dir.iterdir()} != expected_files:
        raise VerificationError("artifact file set mismatch")
    manifest = json.loads((artifact_dir / "artifact_manifest.json").read_text(encoding="utf-8"))
    if manifest.get("protocol") != f"{PROTOCOL}-artifact-manifest-v1" or manifest.get("contract_sha256") != CONTRACT_SHA256:
        raise VerificationError("artifact manifest header mismatch")
    if set(manifest.get("artifacts", {})) != expected_files - {"artifact_manifest.json"}:
        raise VerificationError("artifact manifest membership mismatch")
    for name, receipt in manifest["artifacts"].items():
        path = artifact_dir / name
        if receipt != {"sha256": file_hash(path), "bytes": path.stat().st_size}:
            raise VerificationError(f"artifact manifest hash mismatch for {name}")
    train = pair_file(train_path, "train")
    dev = pair_file(dev_path, "dev")
    endpoints = {item for rows in (train, dev) for row in rows for item in (row["better"], row["worse"])}
    code, run, config, card_inventory = card_projection(cards_path, endpoints)
    integrity = integrity_receipt(train, dev, run, config)
    chosen, selection_tasks, informative = selections(train, dev, contract)
    receipts = [
        selection_receipt(seed, arm, chosen[(seed, arm)], run)
        for seed in contract["selection"]["seeds"]
        for arm in ("broad", "concentrated", "random")
    ]
    checks = structure(integrity, receipts, informative, contract)
    matrix: dict[tuple[int, str], dict[str, Any]] = {}
    expected_arms: list[dict[str, Any]] = []
    expected_tasks: list[dict[str, Any]] = []
    expected_pairs: list[dict[str, Any]] = []
    for seed in contract["selection"]["seeds"]:
        for arm in ("broad", "concentrated", "random"):
            item = refit(chosen[(seed, arm)], dev, code, run)
            matrix[(seed, arm)] = item
            receipt = next(row for row in receipts if row["selection_seed"] == seed and row["arm"] == arm)
            expected_arms.append({**receipt, **item["fit_receipt"], **item["metrics"]})
            expected_tasks.extend({"selection_seed": seed, "arm": arm, "task": task, **values} for task, values in item["task_metrics"].items())
            expected_pairs.extend({"selection_seed": seed, "arm": arm, **row} for row in item["pair_rows"])
    actual_arms = read_csv(artifact_dir / "arm_metrics.csv")
    actual_tasks = read_csv(artifact_dir / "per_task.csv")
    actual_selection_tasks = read_csv(artifact_dir / "selection_by_task.csv")
    actual_pairs = [json.loads(line) for line in (artifact_dir / "per_pair.jsonl").read_text(encoding="utf-8").splitlines()]
    expected_sets = (expected_arms, expected_tasks, selection_tasks, expected_pairs)
    actual_sets = (actual_arms, actual_tasks, actual_selection_tasks, actual_pairs)
    if any(len(expected) != len(actual) for expected, actual in zip(expected_sets, actual_sets)):
        raise VerificationError("artifact row count mismatch")
    maximum_difference = 0.0
    for label, expected_rows, actual_rows in zip(("arm", "task", "selection", "pair"), expected_sets, actual_sets):
        for index, expected in enumerate(expected_rows):
            actual = cast_row(actual_rows[index], expected) if label != "pair" else actual_rows[index]
            maximum_difference = max(maximum_difference, close_enough(expected, actual, f"{label}[{index}]"))
    expected_decision = decision(matrix, contract)
    expected_summary = {
        "protocol": PROTOCOL,
        "contract_sha256": CONTRACT_SHA256,
        "status": "RETROSPECTIVE_DEV_COMPONENT_BREADTH_POSITIVE" if expected_decision["any_predeclared_positive"] else "RETROSPECTIVE_DEV_COMPONENT_BREADTH_NO_UNLOCK",
        "evidence_level": contract["evidence_level"],
        "inputs": {role: {"sha256": SOURCE[role][0], "bytes": SOURCE[role][1]} for role in SOURCE},
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
        "decision": expected_decision,
    }
    actual_summary = json.loads((artifact_dir / "summary.json").read_text(encoding="utf-8"))
    maximum_difference = max(maximum_difference, close_enough(expected_summary, actual_summary, "summary"))
    return {
        "protocol": f"verify-{PROTOCOL}-v1",
        "status": "INDEPENDENT_SOURCE_REFIT_PASS",
        "contract_sha256": CONTRACT_SHA256,
        "artifact_manifest_sha256": file_hash(artifact_dir / "artifact_manifest.json"),
        "rows": {
            "arm_metrics": len(expected_arms),
            "per_task": len(expected_tasks),
            "selection_by_task": len(selection_tasks),
            "per_pair": len(expected_pairs),
        },
        "unique_cpu_critic_refits": len(matrix),
        "maximum_numeric_difference": maximum_difference,
        "summary_status": expected_summary["status"],
        "proper_score_positive": expected_decision["proper_score_positive"],
        "top1_positive": expected_decision["top1_positive"],
        "source_open_attestation": {
            "heldout_test_pairs": False,
            "test_predictions": False,
            "prospective_vault": False,
            "score_channel_truth": False,
        },
    }


def arguments() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("cards", type=Path)
    parser.add_argument("train", type=Path)
    parser.add_argument("dev", type=Path)
    parser.add_argument("artifact_dir", type=Path)
    parser.add_argument("verification_output", type=Path)
    parser.add_argument("--contract", type=Path, default=Path(__file__).with_name("critic_component_breadth_equal_budget_v1.json"))
    return parser.parse_args()


def main() -> None:
    args = arguments()
    if args.verification_output.exists():
        raise VerificationError("verification output already exists")
    receipt = verify(args.cards, args.train, args.dev, args.contract, args.artifact_dir)
    args.verification_output.parent.mkdir(parents=True, exist_ok=True)
    args.verification_output.write_bytes(canonical(receipt))
    print(json.dumps(receipt, sort_keys=True, separators=(",", ":")))


if __name__ == "__main__":
    main()
