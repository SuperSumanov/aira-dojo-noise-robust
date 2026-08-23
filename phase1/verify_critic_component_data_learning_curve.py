"""Independent source refit for the component-clean TF-IDF data curve."""

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


PROTOCOL = "critic-component-data-learning-curve-v1"
CONTRACT_SHA256 = "a7c6bca3e430580c4a178d89694e90658a5496b8a1775a967221b7dc32d3c9da"
SOURCE = {
    "cards": ("5fd24c8e545a67e1048f8a67b23bcb64605b9ad584a4fbaa44aa1b1f1b6e1afb", 604190866),
    "train": ("0ec49d76a896accf8e85a2556ca7ed12b9379b1867247d99c6be5e4c83bea98e", 3208089),
    "dev": ("3b3fb53f84277e935c66d3b3d1646d7a7d33624fb916e3f9bcc15f689904cfa4", 376635),
}


class VerificationError(RuntimeError):
    """Raised when source reconstruction and a producer artifact differ."""


def file_hash(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1 << 20), b""):
            digest.update(block)
    return digest.hexdigest()


def canonical(value: Any) -> bytes:
    return (json.dumps(value, indent=2, sort_keys=True, ensure_ascii=False) + "\n").encode()


def compact(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def load_contract(path: Path) -> dict[str, Any]:
    if file_hash(path) != CONTRACT_SHA256:
        raise VerificationError("contract hash mismatch")
    value = json.loads(path.read_text(encoding="utf-8"))
    if value.get("protocol") != PROTOCOL:
        raise VerificationError("contract protocol mismatch")
    return value


def attest(path: Path, role: str) -> None:
    digest, size = SOURCE[role]
    if not path.is_file() or path.stat().st_size != size or file_hash(path) != digest:
        raise VerificationError(f"{role} source mismatch")


def identity(row: dict[str, Any]) -> tuple[str, str, str, str]:
    try:
        endpoints = sorted((row["better"], row["worse"]))
        value = row["task"], row["parent"], endpoints[0], endpoints[1]
    except (KeyError, TypeError, ValueError) as error:
        raise VerificationError("pair identity malformed") from error
    if not all(isinstance(item, str) and item for item in value) or value[2] == value[3]:
        raise VerificationError("pair identity malformed")
    return value


def pair_file(path: Path, split: str) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    seen = set()
    with path.open(encoding="utf-8") as stream:
        for number, text in enumerate(stream, 1):
            if not text.strip():
                raise VerificationError(f"blank pair line {number}")
            row = json.loads(text)
            if not isinstance(row, dict) or row.get("intask_split") != split:
                raise VerificationError("pair split malformed")
            if (
                row.get("outer_intask_split") != "train"
                or row.get("train_dev_protocol") != "pair-graph-component-train-dev-split-v1"
                or row.get("train_dev_seed") != 20260821
                or row.get("train_dev_target_numerator") != 1
                or row.get("train_dev_target_denominator") != 10
            ):
                raise VerificationError("pair split receipt malformed")
            component = row.get("pair_component_id")
            if (
                not isinstance(component, str)
                or len(component) != 64
                or any(character not in "0123456789abcdef" for character in component)
            ):
                raise VerificationError("component identity malformed")
            key = identity(row)
            if key in seen:
                raise VerificationError("duplicate unordered pair")
            seen.add(key)
            rows.append(row)
    if not rows:
        raise VerificationError("pair file empty")
    return rows


def card_projection(
    path: Path, endpoints: set[str]
) -> tuple[dict[str, str], dict[str, str], dict[str, tuple[Any, ...]], dict[str, int]]:
    grouped = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(grouped, dict):
        raise VerificationError("cards root malformed")
    code: dict[str, str] = {}
    run: dict[str, str] = {}
    config: dict[str, tuple[Any, ...]] = {}
    seen = set()
    card_count = 0
    for run_id, records in grouped.items():
        if not isinstance(run_id, str) or not run_id or not isinstance(records, list):
            raise VerificationError("card group malformed")
        for record in records:
            card_count += 1
            if not isinstance(record, dict) or not isinstance(record.get("id"), str) or record["id"] in seen:
                raise VerificationError("card identity malformed")
            card_id = record["id"]
            seen.add(card_id)
            if card_id not in endpoints:
                continue
            task_value = record.get("task")
            task = task_value.get("name") if isinstance(task_value, dict) else None
            values = task, record.get("client"), record.get("hardware"), record.get("time_limit"), record.get("execution_timeout")
            if (
                not isinstance(record.get("code"), str)
                or not all(isinstance(item, str) and item for item in values[:3])
                or not all(isinstance(item, int) for item in values[3:])
            ):
                raise VerificationError("retained card projection malformed")
            code[card_id] = record["code"]
            run[card_id] = run_id
            config[card_id] = values
    if set(code) != endpoints:
        raise VerificationError("card endpoint coverage mismatch")
    return code, run, config, {"cards": card_count, "run_groups": len(grouped), "needed_cards": len(endpoints)}


def integrity_receipt(
    train: list[dict[str, Any]],
    dev: list[dict[str, Any]],
    run: dict[str, str],
    config: dict[str, tuple[Any, ...]],
    contract: dict[str, Any],
) -> dict[str, Any]:
    train_keys = {identity(row) for row in train}
    dev_keys = {identity(row) for row in dev}
    train_endpoints = {endpoint for key in train_keys for endpoint in key[2:]}
    dev_endpoints = {endpoint for key in dev_keys for endpoint in key[2:]}
    train_runs = {run[endpoint] for endpoint in train_endpoints}
    dev_runs = {run[endpoint] for endpoint in dev_endpoints}
    if train_keys & dev_keys or train_endpoints & dev_endpoints or train_runs & dev_runs:
        raise VerificationError("train/dev isolation failure")
    placement: dict[str, tuple[str, str]] = {}
    for split, rows in (("train", train), ("dev", dev)):
        for row in rows:
            component = row["pair_component_id"]
            value = split, row["task"]
            if component in placement and placement[component] != value:
                raise VerificationError("component placement failure")
            placement[component] = value
            if config[row["better"]] != config[row["worse"]] or config[row["better"]][0] != row["task"]:
                raise VerificationError("pair config failure")
    train_tasks = Counter(row["task"] for row in train)
    dev_tasks = Counter(row["task"] for row in dev)
    support = {
        "train_pairs": len(train),
        "dev_pairs": len(dev),
        "train_tasks": len(train_tasks),
        "dev_tasks": len(dev_tasks),
        "train_components": sum(split == "train" for split, _ in placement.values()),
        "dev_components": sum(split == "dev" for split, _ in placement.values()),
        "train_runs": len(train_runs),
        "dev_runs": len(dev_runs),
        "train_dominant_task_share": max(train_tasks.values()) / len(train),
        "dev_dominant_task_share": max(dev_tasks.values()) / len(dev),
        "train_dev_pair_overlap": 0,
        "train_dev_endpoint_overlap": 0,
        "train_dev_physical_run_overlap": 0,
    }
    rules = contract["support_gates"]
    checks = {
        "dev_dominant_task_share": support["dev_dominant_task_share"] <= rules["dev_dominant_task_share_lte"],
        "dev_pairs": support["dev_pairs"] >= rules["dev_pairs_gte"],
        "dev_tasks": support["dev_tasks"] >= rules["dev_tasks_gte"],
        "train_components": support["train_components"] >= rules["train_components_gte"],
        "train_dominant_task_share": support["train_dominant_task_share"] <= rules["train_dominant_task_share_lte"],
        "train_tasks": support["train_tasks"] >= rules["train_tasks_gte"],
        "zero_train_dev_endpoint_overlap": not train_endpoints & dev_endpoints,
        "zero_train_dev_pair_overlap": not train_keys & dev_keys,
        "zero_train_dev_physical_run_overlap": not train_runs & dev_runs,
    }
    if not all(checks.values()):
        raise VerificationError("support gate failure")
    return {"support": support, "support_gates": checks}


def components(rows: list[dict[str, Any]]) -> dict[str, tuple[str, int]]:
    grouped: dict[str, tuple[str, int]] = {}
    counts = Counter(row["pair_component_id"] for row in rows)
    for row in rows:
        component = row["pair_component_id"]
        value = row["task"], counts[component]
        if component in grouped and grouped[component] != value:
            raise VerificationError("component grouping mismatch")
        grouped[component] = value
    return grouped


def choose(grouped: dict[str, tuple[str, int]], total: int, seed: int, fraction: float) -> tuple[str, ...]:
    def rank(component: str) -> str:
        return hashlib.sha256(f"{seed}|{grouped[component][0]}|{component}".encode()).hexdigest()

    ordered = sorted(grouped, key=rank)
    chosen = {
        next(component for component in ordered if grouped[component][0] == task)
        for task in sorted({value[0] for value in grouped.values()})
    }
    count = sum(grouped[component][1] for component in chosen)
    target = math.ceil(total * fraction)
    for component in ordered:
        if count >= target:
            break
        if component not in chosen:
            chosen.add(component)
            count += grouped[component][1]
    return tuple(sorted(chosen))


def component_hash(values: tuple[str, ...]) -> str:
    return hashlib.sha256(("\n".join(values) + "\n").encode()).hexdigest()


def positions(rows: list[dict[str, Any]], index: dict[str, int]) -> tuple[np.ndarray, np.ndarray]:
    left = np.fromiter((index[row["better"]] for row in rows), dtype=np.int64)
    right = np.fromiter((index[row["worse"]] for row in rows), dtype=np.int64)
    return left, right


def refit(
    chosen: tuple[str, ...],
    train: list[dict[str, Any]],
    dev: list[dict[str, Any]],
    code: dict[str, str],
    run: dict[str, str],
) -> dict[str, Any]:
    membership = set(chosen)
    fit_rows = [row for row in train if row["pair_component_id"] in membership]
    fit_cards = sorted({endpoint for row in fit_rows for endpoint in (row["better"], row["worse"])})
    dev_cards = sorted({endpoint for row in dev for endpoint in (row["better"], row["worse"])})
    card_order = sorted(set(fit_cards) | set(dev_cards))
    index = {card_id: offset for offset, card_id in enumerate(card_order)}
    encoder = TfidfVectorizer(
        analyzer="char_wb", ngram_range=(3, 5), max_features=30000,
        min_df=3, sublinear_tf=True, dtype=np.float64,
    )
    encoder.fit([code[card_id][:20000] for card_id in fit_cards])
    vectors = encoder.transform([code[card_id][:20000] for card_id in card_order]).tocsr()
    positive, negative = positions(fit_rows, index)
    differences = vectors[positive] - vectors[negative]
    design = sparse.vstack((differences, -differences), format="csr")
    labels = np.r_[np.ones(len(fit_rows), dtype=np.int8), np.zeros(len(fit_rows), dtype=np.int8)]
    classifier = LogisticRegression(C=0.5, max_iter=1500, solver="lbfgs", random_state=0)
    classifier.fit(design, labels)
    if int(classifier.n_iter_[0]) >= 1500 or not np.isfinite(classifier.coef_).all() or not np.isfinite(classifier.intercept_).all():
        raise VerificationError("independent refit convergence failure")
    weights = np.asarray(classifier.coef_, dtype=np.float64).ravel()
    better, worse = positions(dev, index)
    dev_difference = vectors[better] - vectors[worse]
    margin = np.asarray(dev_difference.dot(weights), dtype=np.float64).ravel()
    reverse = np.asarray((-dev_difference).dot(weights), dtype=np.float64).ravel()
    if not np.isfinite(margin).all() or float(np.max(np.abs(margin + reverse))) != 0.0:
        raise VerificationError("independent margin failure")
    loss = np.logaddexp(0.0, -margin)
    probability = np.exp(-loss)
    credit = np.where(margin > 0, 1.0, np.where(margin < 0, 0.0, 0.5))
    by_task: dict[str, dict[str, float | int]] = {}
    for task in sorted({row["task"] for row in dev}):
        selected = np.asarray([row["task"] == task for row in dev], dtype=bool)
        by_task[task] = {
            "pairs": int(selected.sum()),
            "log_loss": float(np.mean(loss[selected])),
            "accuracy": float(np.mean(credit[selected])),
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
            "selected_components": len(chosen),
            "selected_components_sha256": component_hash(chosen),
            "train_pairs": len(fit_rows),
            "train_endpoints": len(fit_cards),
            "train_runs": len({run[endpoint] for endpoint in fit_cards}),
            "train_tasks": len({row["task"] for row in fit_rows}),
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


def decision(matrix: dict[tuple[int, float], dict[str, Any]], contract: dict[str, Any]) -> dict[str, Any]:
    seeds = contract["selection"]["seeds"]
    fractions = contract["selection"]["fractions"]
    tasks = sorted(matrix[(seeds[0], 1.0)]["task_metrics"])
    means = [
        {
            "fraction": fraction,
            "task_macro_log_loss": float(np.mean([matrix[(seed, fraction)]["metrics"]["task_macro_log_loss"] for seed in seeds])),
            "task_macro_accuracy": float(np.mean([matrix[(seed, fraction)]["metrics"]["task_macro_accuracy"] for seed in seeds])),
        }
        for fraction in fractions
    ]
    full = matrix[(seeds[0], 1.0)]["task_metrics"]
    loss_delta = np.asarray([
        full[task]["log_loss"] - float(np.mean([matrix[(seed, .25)]["task_metrics"][task]["log_loss"] for seed in seeds]))
        for task in tasks
    ])
    accuracy_delta = np.asarray([
        full[task]["accuracy"] - float(np.mean([matrix[(seed, .25)]["task_metrics"][task]["accuracy"] for seed in seeds]))
        for task in tasks
    ])
    loss_loto = [float(np.mean(np.delete(loss_delta, index))) for index in range(len(tasks))]
    accuracy_loto = [float(np.mean(np.delete(accuracy_delta, index))) for index in range(len(tasks))]
    contrasts = [
        {
            "seed": seed,
            "full_minus_quarter_log_loss": matrix[(seed, 1.0)]["metrics"]["task_macro_log_loss"] - matrix[(seed, .25)]["metrics"]["task_macro_log_loss"],
            "full_minus_quarter_accuracy": matrix[(seed, 1.0)]["metrics"]["task_macro_accuracy"] - matrix[(seed, .25)]["metrics"]["task_macro_accuracy"],
        }
        for seed in seeds
    ]
    loss_values = [item["task_macro_log_loss"] for item in means]
    accuracy_values = [item["task_macro_accuracy"] for item in means]
    loss_ci = confidence_interval(loss_delta, contract)
    accuracy_ci = confidence_interval(accuracy_delta, contract)
    loss_rule = contract["decision_rules"]["proper_score_positive"]
    accuracy_rule = contract["decision_rules"]["top1_positive"]
    loss_checks = {
        "mean_curve_nonincreasing": all(left >= right for left, right in zip(loss_values, loss_values[1:])),
        "all_seed_contrasts_negative": all(item["full_minus_quarter_log_loss"] < 0 for item in contrasts),
        "point_effect_floor": float(np.mean(loss_delta)) <= loss_rule["point_full_minus_mean_quarter_log_loss_lte"],
        "bootstrap_ci_high_below_zero": loss_ci[1] < loss_rule["bootstrap_ci95_high_full_minus_mean_quarter_log_loss_lt"],
        "loto_all_negative": max(loss_loto) < loss_rule["leave_one_task_out_full_minus_mean_quarter_log_loss_lt"],
    }
    accuracy_checks = {
        "mean_curve_nondecreasing": all(left <= right for left, right in zip(accuracy_values, accuracy_values[1:])),
        "all_seed_contrasts_positive": all(item["full_minus_quarter_accuracy"] > 0 for item in contrasts),
        "point_effect_floor": float(np.mean(accuracy_delta)) >= accuracy_rule["point_full_minus_mean_quarter_accuracy_gte"],
        "bootstrap_ci_low_above_zero": accuracy_ci[0] > accuracy_rule["bootstrap_ci95_low_full_minus_mean_quarter_accuracy_gt"],
        "loto_all_positive": min(accuracy_loto) > accuracy_rule["leave_one_task_out_full_minus_mean_quarter_accuracy_gt"],
    }
    return {
        "mean_curve": means,
        "seed_contrasts": contrasts,
        "full_minus_mean_quarter": {
            "task_macro_log_loss": {
                "point": float(np.mean(loss_delta)), "ci95": loss_ci,
                "loto_min": min(loss_loto), "loto_max": max(loss_loto),
            },
            "task_macro_accuracy": {
                "point": float(np.mean(accuracy_delta)), "ci95": accuracy_ci,
                "loto_min": min(accuracy_loto), "loto_max": max(accuracy_loto),
            },
        },
        "proper_score_checks": loss_checks,
        "top1_checks": accuracy_checks,
        "proper_score_positive": all(loss_checks.values()),
        "top1_positive": all(accuracy_checks.values()),
        "any_predeclared_positive": all(loss_checks.values()) or all(accuracy_checks.values()),
    }


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
    expected_files = {"summary.json", "curve.csv", "per_task.csv", "per_pair.jsonl", "artifact_manifest.json"}
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
    endpoints = {endpoint for rows in (train, dev) for row in rows for endpoint in (row["better"], row["worse"])}
    code, run, config, card_inventory = card_projection(cards_path, endpoints)
    integrity = integrity_receipt(train, dev, run, config, contract)
    grouped = components(train)
    seeds = contract["selection"]["seeds"]
    fractions = contract["selection"]["fractions"]
    chosen_matrix: dict[tuple[int, float], tuple[str, ...]] = {}
    cache: dict[tuple[str, ...], dict[str, Any]] = {}
    matrix: dict[tuple[int, float], dict[str, Any]] = {}
    expected_curve: list[dict[str, Any]] = []
    expected_tasks: list[dict[str, Any]] = []
    expected_pairs: list[dict[str, Any]] = []
    for seed in seeds:
        prior: set[str] = set()
        for fraction in fractions:
            chosen = choose(grouped, len(train), seed, fraction)
            if not prior <= set(chosen):
                raise VerificationError("independent subset nesting failure")
            prior = set(chosen)
            realized = sum(grouped[component][1] for component in chosen) / len(train)
            if fraction < 1.0 and realized - fraction > contract["selection"]["realized_fraction_max_overshoot"] + 1e-15:
                raise VerificationError("independent subset overshoot")
            if fraction == 1.0 and set(chosen) != set(grouped):
                raise VerificationError("independent full subset failure")
            chosen_matrix[(seed, fraction)] = chosen
            if chosen not in cache:
                cache[chosen] = refit(chosen, train, dev, code, run)
            item = cache[chosen]
            matrix[(seed, fraction)] = item
            expected_curve.append({
                "selection_seed": seed,
                "target_fraction": fraction,
                "realized_pair_fraction": item["fit_receipt"]["train_pairs"] / len(train),
                **item["fit_receipt"],
                **item["metrics"],
            })
            expected_tasks.extend({"selection_seed": seed, "target_fraction": fraction, "task": task, **values} for task, values in item["task_metrics"].items())
            expected_pairs.extend({"selection_seed": seed, "target_fraction": fraction, **row} for row in item["pair_rows"])
    actual_curve = read_csv(artifact_dir / "curve.csv")
    actual_tasks = read_csv(artifact_dir / "per_task.csv")
    actual_pairs = [json.loads(line) for line in (artifact_dir / "per_pair.jsonl").read_text(encoding="utf-8").splitlines()]
    if len(actual_curve) != len(expected_curve) or len(actual_tasks) != len(expected_tasks) or len(actual_pairs) != len(expected_pairs):
        raise VerificationError("artifact row count mismatch")
    maximum_difference = 0.0
    for index, expected in enumerate(expected_curve):
        maximum_difference = max(maximum_difference, close_enough(expected, cast_row(actual_curve[index], expected), f"curve[{index}]"))
    for index, expected in enumerate(expected_tasks):
        maximum_difference = max(maximum_difference, close_enough(expected, cast_row(actual_tasks[index], expected), f"task[{index}]"))
    for index, expected in enumerate(expected_pairs):
        maximum_difference = max(maximum_difference, close_enough(expected, actual_pairs[index], f"pair[{index}]"))
    full = matrix[(seeds[0], 1.0)]["metrics"]
    known = contract["claim_boundary"]["known_before_freeze"]
    tolerance = contract["evaluation"]["full_dev_anchor_tolerance"]
    anchors = {
        "full_dev_micro_accuracy": abs(full["pair_micro_accuracy"] - known["full_dev_micro_accuracy"]) <= tolerance,
        "full_dev_task_macro_accuracy": abs(full["task_macro_accuracy"] - known["full_dev_task_macro_accuracy"]) <= tolerance,
        "full_identical_across_selection_seeds": len({compact(matrix[(seed, 1.0)]["metrics"]) for seed in seeds}) == 1,
    }
    expected_decision = decision(matrix, contract)
    expected_summary = {
        "protocol": PROTOCOL,
        "contract_sha256": CONTRACT_SHA256,
        "status": "RETROSPECTIVE_DEV_DATA_SCALING_POSITIVE" if expected_decision["any_predeclared_positive"] else "RETROSPECTIVE_DEV_DATA_SCALING_NO_UNLOCK",
        "evidence_level": contract["evidence_level"],
        "inputs": {role: {"sha256": SOURCE[role][0], "bytes": SOURCE[role][1]} for role in ("cards", "train", "dev")},
        "access_attestation": {
            "cards_container_full_json_parsed": True,
            "nonretained_card_fields_referenced": False,
            "raw_grade_as_feature_or_selection_signal": False,
            "heldout_test_pairs_opened": False,
            "test_predictions_opened": False,
            "prospective_vault_opened": False,
            "score_channel_truth_opened": False,
            "gpu_jobs": 0,
            "api_calls": 0,
            "base_llm_updates": 0,
            "unique_cpu_critic_fits": len(cache),
        },
        "card_inventory": card_inventory,
        "integrity": integrity,
        "known_anchor_checks": anchors,
        "decision": expected_decision,
    }
    actual_summary = json.loads((artifact_dir / "summary.json").read_text(encoding="utf-8"))
    maximum_difference = max(maximum_difference, close_enough(expected_summary, actual_summary, "summary"))
    return {
        "protocol": f"verify-{PROTOCOL}-v1",
        "status": "INDEPENDENT_SOURCE_REFIT_PASS",
        "contract_sha256": CONTRACT_SHA256,
        "artifact_manifest_sha256": file_hash(artifact_dir / "artifact_manifest.json"),
        "rows": {"curve": len(expected_curve), "per_task": len(expected_tasks), "per_pair": len(expected_pairs)},
        "unique_cpu_critic_refits": len(cache),
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
    parser.add_argument("--contract", type=Path, default=Path(__file__).with_name("critic_component_data_learning_curve_v1.json"))
    return parser.parse_args()


def main() -> None:
    args = arguments()
    if args.verification_output.exists():
        raise VerificationError("verification output already exists")
    receipt = verify(args.cards, args.train, args.dev, args.contract, args.artifact_dir)
    args.verification_output.parent.mkdir(parents=True, exist_ok=True)
    args.verification_output.write_bytes(canonical(receipt))
    print(compact(receipt))


if __name__ == "__main__":
    main()
