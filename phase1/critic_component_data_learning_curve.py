"""Outer-train-only component-clean TF-IDF data learning curve."""

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
EXPECTED = {
    "cards": ("5fd24c8e545a67e1048f8a67b23bcb64605b9ad584a4fbaa44aa1b1f1b6e1afb", 604190866),
    "train": ("0ec49d76a896accf8e85a2556ca7ed12b9379b1867247d99c6be5e4c83bea98e", 3208089),
    "dev": ("3b3fb53f84277e935c66d3b3d1646d7a7d33624fb916e3f9bcc15f689904cfa4", 376635),
}


class CurveError(RuntimeError):
    """Raised when a protocol, input, fit, or output invariant fails."""


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
        raise CurveError("contract identity mismatch")
    contract = json.loads(path.read_text(encoding="utf-8"))
    if contract.get("protocol") != PROTOCOL:
        raise CurveError("contract protocol mismatch")
    return contract


def verify_input(path: Path, role: str) -> None:
    expected_hash, expected_bytes = EXPECTED[role]
    if not path.is_file() or path.stat().st_size != expected_bytes or sha256_file(path) != expected_hash:
        raise CurveError(f"{role} input identity mismatch")


def pair_key(row: dict[str, Any]) -> tuple[str, str, str, str]:
    try:
        left, right = sorted((row["better"], row["worse"]))
        key = row["task"], row["parent"], left, right
    except (KeyError, TypeError, ValueError) as error:
        raise CurveError("invalid pair identity") from error
    if not all(isinstance(value, str) and value for value in key) or left == right:
        raise CurveError("invalid pair identity")
    return key


def read_pairs(path: Path, split: str) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    keys: set[tuple[str, str, str, str]] = set()
    with path.open(encoding="utf-8") as handle:
        for line_number, line in enumerate(handle, 1):
            if not line.strip():
                raise CurveError(f"blank row at {path.name}:{line_number}")
            row = json.loads(line)
            if not isinstance(row, dict) or row.get("intask_split") != split:
                raise CurveError(f"invalid {split} row")
            if (
                row.get("outer_intask_split") != "train"
                or row.get("train_dev_protocol") != "pair-graph-component-train-dev-split-v1"
                or row.get("train_dev_seed") != 20260821
                or row.get("train_dev_target_numerator") != 1
                or row.get("train_dev_target_denominator") != 10
                or not isinstance(row.get("pair_component_id"), str)
                or len(row["pair_component_id"]) != 64
                or any(character not in "0123456789abcdef" for character in row["pair_component_id"])
            ):
                raise CurveError("component split receipt mismatch")
            key = pair_key(row)
            if key in keys:
                raise CurveError(f"duplicate unordered pair in {path.name}")
            keys.add(key)
            rows.append(row)
    if not rows:
        raise CurveError(f"empty {split} pool")
    return rows


def load_cards(
    path: Path, needed: set[str]
) -> tuple[dict[str, str], dict[str, str], dict[str, tuple[Any, ...]], dict[str, int]]:
    grouped = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(grouped, dict):
        raise CurveError("cards root is not grouped")
    codes: dict[str, str] = {}
    runs: dict[str, str] = {}
    configs: dict[str, tuple[Any, ...]] = {}
    seen: set[str] = set()
    total = 0
    for run_id, cards in grouped.items():
        if not isinstance(run_id, str) or not run_id or not isinstance(cards, list):
            raise CurveError("invalid card group")
        for card in cards:
            total += 1
            if not isinstance(card, dict) or not isinstance(card.get("id"), str) or card["id"] in seen:
                raise CurveError("invalid or duplicate card")
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
                raise CurveError("needed card lacks code or provenance")
            codes[card_id] = card["code"]
            runs[card_id] = run_id
            configs[card_id] = config
    if set(codes) != needed:
        raise CurveError("pair endpoint missing from cards")
    return codes, runs, configs, {"cards": total, "run_groups": len(grouped), "needed_cards": len(needed)}


def validate_inputs(
    train: list[dict[str, Any]],
    dev: list[dict[str, Any]],
    runs: dict[str, str],
    configs: dict[str, tuple[Any, ...]],
    contract: dict[str, Any],
) -> dict[str, Any]:
    pools = {"train": train, "dev": dev}
    keys = {name: {pair_key(row) for row in rows} for name, rows in pools.items()}
    endpoints = {name: {endpoint for key in values for endpoint in key[2:]} for name, values in keys.items()}
    run_sets = {name: {runs[endpoint] for endpoint in values} for name, values in endpoints.items()}
    if keys["train"] & keys["dev"] or endpoints["train"] & endpoints["dev"] or run_sets["train"] & run_sets["dev"]:
        raise CurveError("train/dev pair, endpoint, or physical-run overlap")
    component_splits: dict[str, str] = {}
    component_tasks: dict[str, str] = {}
    for split, rows in pools.items():
        for row in rows:
            component = row["pair_component_id"]
            task = row["task"]
            if component in component_splits and component_splits[component] != split:
                raise CurveError("component crosses train/dev")
            if component in component_tasks and component_tasks[component] != task:
                raise CurveError("component crosses tasks")
            component_splits[component] = split
            component_tasks[component] = task
            if configs[row["better"]] != configs[row["worse"]] or configs[row["better"]][0] != task:
                raise CurveError("pair violates exact configuration")
    task_counts = {name: Counter(row["task"] for row in rows) for name, rows in pools.items()}
    component_counts = Counter(component_splits.values())
    support = {
        "train_pairs": len(train),
        "dev_pairs": len(dev),
        "train_tasks": len(task_counts["train"]),
        "dev_tasks": len(task_counts["dev"]),
        "train_components": component_counts["train"],
        "dev_components": component_counts["dev"],
        "train_runs": len(run_sets["train"]),
        "dev_runs": len(run_sets["dev"]),
        "train_dominant_task_share": max(task_counts["train"].values()) / len(train),
        "dev_dominant_task_share": max(task_counts["dev"].values()) / len(dev),
        "train_dev_pair_overlap": 0,
        "train_dev_endpoint_overlap": 0,
        "train_dev_physical_run_overlap": 0,
    }
    gates = contract["support_gates"]
    checks = {
        "dev_dominant_task_share": support["dev_dominant_task_share"] <= gates["dev_dominant_task_share_lte"],
        "dev_pairs": support["dev_pairs"] >= gates["dev_pairs_gte"],
        "dev_tasks": support["dev_tasks"] >= gates["dev_tasks_gte"],
        "train_components": support["train_components"] >= gates["train_components_gte"],
        "train_dominant_task_share": support["train_dominant_task_share"] <= gates["train_dominant_task_share_lte"],
        "train_tasks": support["train_tasks"] >= gates["train_tasks_gte"],
        "zero_train_dev_endpoint_overlap": support["train_dev_endpoint_overlap"] == 0,
        "zero_train_dev_pair_overlap": support["train_dev_pair_overlap"] == 0,
        "zero_train_dev_physical_run_overlap": support["train_dev_physical_run_overlap"] == 0,
    }
    if not all(checks.values()):
        raise CurveError("support gate failed")
    return {"support": support, "support_gates": checks}


def component_inventory(rows: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    inventory: dict[str, dict[str, Any]] = {}
    for row in rows:
        component = row["pair_component_id"]
        item = inventory.setdefault(component, {"task": row["task"], "pairs": 0})
        if item["task"] != row["task"]:
            raise CurveError("component task mismatch")
        item["pairs"] += 1
    return inventory


def component_digest(seed: int, task: str, component: str) -> str:
    return hashlib.sha256(f"{seed}|{task}|{component}".encode()).hexdigest()


def selected_components(
    inventory: dict[str, dict[str, Any]], total_pairs: int, seed: int, fraction: float
) -> tuple[str, ...]:
    ordering = sorted(
        inventory,
        key=lambda component: component_digest(seed, inventory[component]["task"], component),
    )
    tasks = sorted({item["task"] for item in inventory.values()})
    selected = {
        next(component for component in ordering if inventory[component]["task"] == task)
        for task in tasks
    }
    target = math.ceil(fraction * total_pairs)
    count = sum(inventory[component]["pairs"] for component in selected)
    for component in ordering:
        if count >= target:
            break
        if component not in selected:
            selected.add(component)
            count += inventory[component]["pairs"]
    return tuple(sorted(selected))


def matrix_indices(rows: list[dict[str, Any]], positions: dict[str, int]) -> tuple[np.ndarray, np.ndarray]:
    return (
        np.fromiter((positions[row["better"]] for row in rows), dtype=np.int64),
        np.fromiter((positions[row["worse"]] for row in rows), dtype=np.int64),
    )


def subset_sha(components: tuple[str, ...]) -> str:
    return hashlib.sha256(("\n".join(components) + "\n").encode()).hexdigest()


def fit_subset(
    selected: tuple[str, ...],
    train: list[dict[str, Any]],
    dev: list[dict[str, Any]],
    codes: dict[str, str],
    runs: dict[str, str],
) -> dict[str, Any]:
    selected_set = set(selected)
    train_rows = [row for row in train if row["pair_component_id"] in selected_set]
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
    train_difference = matrix[train_better] - matrix[train_worse]
    fit_x = sparse.vstack((train_difference, -train_difference), format="csr")
    fit_y = np.concatenate(
        (np.ones(len(train_rows), dtype=np.int8), np.zeros(len(train_rows), dtype=np.int8))
    )
    model = LogisticRegression(C=0.5, max_iter=1500, solver="lbfgs", random_state=0).fit(fit_x, fit_y)
    if int(model.n_iter_[0]) >= 1500 or not np.isfinite(model.coef_).all() or not np.isfinite(model.intercept_).all():
        raise CurveError("logistic regression convergence/finite gate failed")
    weights = np.asarray(model.coef_, dtype=np.float64).reshape(-1)
    dev_better, dev_worse = matrix_indices(dev, positions)
    difference = matrix[dev_better] - matrix[dev_worse]
    margins = np.asarray(difference.dot(weights), dtype=np.float64).reshape(-1)
    reverse = np.asarray((-difference).dot(weights), dtype=np.float64).reshape(-1)
    if margins.shape != (len(dev),) or not np.isfinite(margins).all():
        raise CurveError("invalid dev margins")
    anti_symmetry = float(np.max(np.abs(margins + reverse)))
    if anti_symmetry != 0.0:
        raise CurveError("pair margin is not exactly antisymmetric")
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
    pair_rows = []
    for index, (row, margin, probability, loss, credit) in enumerate(
        zip(dev, margins, probabilities, losses, credits)
    ):
        pair_rows.append(
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
        )
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
            "selected_components": len(selected),
            "selected_components_sha256": subset_sha(selected),
            "train_pairs": len(train_rows),
            "train_endpoints": len(train_ids),
            "train_runs": len({runs[endpoint] for endpoint in train_ids}),
            "train_tasks": len({row["task"] for row in train_rows}),
            "vocabulary_size": len(vectorizer.vocabulary_),
            "lr_iterations": int(model.n_iter_[0]),
            "lr_intercept": float(model.intercept_[0]),
            "coef_l2": float(np.linalg.norm(weights)),
            "anti_symmetry_max_abs": anti_symmetry,
        },
    }


def task_bootstrap(values: np.ndarray, seed: int, replicates: int) -> list[float]:
    rng = np.random.default_rng(seed)
    draws = rng.integers(0, len(values), size=(replicates, len(values)))
    estimates = np.mean(values[draws], axis=1)
    interval = np.quantile(estimates, [0.025, 0.975], method="linear")
    return [float(interval[0]), float(interval[1])]


def evaluate_curve(
    matrix: dict[tuple[int, float], dict[str, Any]], contract: dict[str, Any]
) -> dict[str, Any]:
    seeds = contract["selection"]["seeds"]
    fractions = contract["selection"]["fractions"]
    tasks = sorted(matrix[(seeds[0], 1.0)]["task_metrics"])
    mean_curve = []
    for fraction in fractions:
        mean_curve.append(
            {
                "fraction": fraction,
                "task_macro_log_loss": float(
                    np.mean([matrix[(seed, fraction)]["metrics"]["task_macro_log_loss"] for seed in seeds])
                ),
                "task_macro_accuracy": float(
                    np.mean([matrix[(seed, fraction)]["metrics"]["task_macro_accuracy"] for seed in seeds])
                ),
            }
        )
    full_tasks = matrix[(seeds[0], 1.0)]["task_metrics"]
    loss_deltas = np.asarray(
        [
            full_tasks[task]["log_loss"]
            - float(np.mean([matrix[(seed, 0.25)]["task_metrics"][task]["log_loss"] for seed in seeds]))
            for task in tasks
        ],
        dtype=np.float64,
    )
    accuracy_deltas = np.asarray(
        [
            full_tasks[task]["accuracy"]
            - float(np.mean([matrix[(seed, 0.25)]["task_metrics"][task]["accuracy"] for seed in seeds]))
            for task in tasks
        ],
        dtype=np.float64,
    )
    bootstrap = contract["bootstrap"]
    loss_ci = task_bootstrap(loss_deltas, bootstrap["seed"], bootstrap["replicates"])
    accuracy_ci = task_bootstrap(accuracy_deltas, bootstrap["seed"], bootstrap["replicates"])
    loss_loto = [float(np.mean(np.delete(loss_deltas, index))) for index in range(len(tasks))]
    accuracy_loto = [float(np.mean(np.delete(accuracy_deltas, index))) for index in range(len(tasks))]
    seed_contrasts = []
    for seed in seeds:
        seed_contrasts.append(
            {
                "seed": seed,
                "full_minus_quarter_log_loss": matrix[(seed, 1.0)]["metrics"]["task_macro_log_loss"]
                - matrix[(seed, 0.25)]["metrics"]["task_macro_log_loss"],
                "full_minus_quarter_accuracy": matrix[(seed, 1.0)]["metrics"]["task_macro_accuracy"]
                - matrix[(seed, 0.25)]["metrics"]["task_macro_accuracy"],
            }
        )
    loss_points = [row["task_macro_log_loss"] for row in mean_curve]
    accuracy_points = [row["task_macro_accuracy"] for row in mean_curve]
    proper_rule = contract["decision_rules"]["proper_score_positive"]
    top1_rule = contract["decision_rules"]["top1_positive"]
    proper_checks = {
        "mean_curve_nonincreasing": all(left >= right for left, right in zip(loss_points, loss_points[1:])),
        "all_seed_contrasts_negative": all(row["full_minus_quarter_log_loss"] < 0 for row in seed_contrasts),
        "point_effect_floor": float(np.mean(loss_deltas)) <= proper_rule["point_full_minus_mean_quarter_log_loss_lte"],
        "bootstrap_ci_high_below_zero": loss_ci[1]
        < proper_rule["bootstrap_ci95_high_full_minus_mean_quarter_log_loss_lt"],
        "loto_all_negative": max(loss_loto)
        < proper_rule["leave_one_task_out_full_minus_mean_quarter_log_loss_lt"],
    }
    top1_checks = {
        "mean_curve_nondecreasing": all(left <= right for left, right in zip(accuracy_points, accuracy_points[1:])),
        "all_seed_contrasts_positive": all(row["full_minus_quarter_accuracy"] > 0 for row in seed_contrasts),
        "point_effect_floor": float(np.mean(accuracy_deltas)) >= top1_rule["point_full_minus_mean_quarter_accuracy_gte"],
        "bootstrap_ci_low_above_zero": accuracy_ci[0]
        > top1_rule["bootstrap_ci95_low_full_minus_mean_quarter_accuracy_gt"],
        "loto_all_positive": min(accuracy_loto)
        > top1_rule["leave_one_task_out_full_minus_mean_quarter_accuracy_gt"],
    }
    return {
        "mean_curve": mean_curve,
        "seed_contrasts": seed_contrasts,
        "full_minus_mean_quarter": {
            "task_macro_log_loss": {
                "point": float(np.mean(loss_deltas)),
                "ci95": loss_ci,
                "loto_min": min(loss_loto),
                "loto_max": max(loss_loto),
            },
            "task_macro_accuracy": {
                "point": float(np.mean(accuracy_deltas)),
                "ci95": accuracy_ci,
                "loto_min": min(accuracy_loto),
                "loto_max": max(accuracy_loto),
            },
        },
        "proper_score_checks": proper_checks,
        "top1_checks": top1_checks,
        "proper_score_positive": all(proper_checks.values()),
        "top1_positive": all(top1_checks.values()),
        "any_predeclared_positive": all(proper_checks.values()) or all(top1_checks.values()),
    }


def analyze(cards_path: Path, train_path: Path, dev_path: Path, contract_path: Path) -> tuple[dict[str, Any], list[dict[str, Any]], list[dict[str, Any]], list[dict[str, Any]]]:
    contract = verify_contract(contract_path)
    for role, path in (("cards", cards_path), ("train", train_path), ("dev", dev_path)):
        verify_input(path, role)
    train = read_pairs(train_path, "train")
    dev = read_pairs(dev_path, "dev")
    needed = {endpoint for rows in (train, dev) for row in rows for endpoint in (row["better"], row["worse"])}
    codes, runs, configs, card_inventory = load_cards(cards_path, needed)
    integrity = validate_inputs(train, dev, runs, configs, contract)
    inventory = component_inventory(train)
    seeds = contract["selection"]["seeds"]
    fractions = contract["selection"]["fractions"]
    selected_matrix: dict[tuple[int, float], tuple[str, ...]] = {}
    for seed in seeds:
        previous: set[str] = set()
        for fraction in fractions:
            selected = selected_components(inventory, len(train), seed, fraction)
            if not previous <= set(selected):
                raise CurveError("component subsets are not nested")
            previous = set(selected)
            selected_pairs = sum(inventory[component]["pairs"] for component in selected)
            realized = selected_pairs / len(train)
            if fraction < 1.0 and realized - fraction > contract["selection"]["realized_fraction_max_overshoot"] + 1e-15:
                raise CurveError("realized fraction overshoot")
            if fraction == 1.0 and set(selected) != set(inventory):
                raise CurveError("full fraction does not include every component")
            selected_matrix[(seed, fraction)] = selected
    cache: dict[tuple[str, ...], dict[str, Any]] = {}
    matrix: dict[tuple[int, float], dict[str, Any]] = {}
    curve_rows: list[dict[str, Any]] = []
    task_rows: list[dict[str, Any]] = []
    pair_rows: list[dict[str, Any]] = []
    for seed in seeds:
        for fraction in fractions:
            selected = selected_matrix[(seed, fraction)]
            if selected not in cache:
                cache[selected] = fit_subset(selected, train, dev, codes, runs)
            fit = cache[selected]
            matrix[(seed, fraction)] = fit
            receipt = fit["fit_receipt"]
            curve_rows.append(
                {
                    "selection_seed": seed,
                    "target_fraction": fraction,
                    "realized_pair_fraction": receipt["train_pairs"] / len(train),
                    **receipt,
                    **fit["metrics"],
                }
            )
            task_rows.extend(
                {
                    "selection_seed": seed,
                    "target_fraction": fraction,
                    "task": task,
                    **values,
                }
                for task, values in fit["task_metrics"].items()
            )
            pair_rows.extend(
                {"selection_seed": seed, "target_fraction": fraction, **row}
                for row in fit["pair_rows"]
            )
    full = matrix[(seeds[0], 1.0)]["metrics"]
    known = contract["claim_boundary"]["known_before_freeze"]
    tolerance = contract["evaluation"]["full_dev_anchor_tolerance"]
    anchors = {
        "full_dev_micro_accuracy": abs(full["pair_micro_accuracy"] - known["full_dev_micro_accuracy"]) <= tolerance,
        "full_dev_task_macro_accuracy": abs(full["task_macro_accuracy"] - known["full_dev_task_macro_accuracy"]) <= tolerance,
        "full_identical_across_selection_seeds": len(
            {compact(matrix[(seed, 1.0)]["metrics"]) for seed in seeds}
        )
        == 1,
    }
    if not all(anchors.values()):
        raise CurveError("known full-dev anchor mismatch")
    decision = evaluate_curve(matrix, contract)
    summary = {
        "protocol": PROTOCOL,
        "contract_sha256": CONTRACT_SHA256,
        "status": (
            "RETROSPECTIVE_DEV_DATA_SCALING_POSITIVE"
            if decision["any_predeclared_positive"]
            else "RETROSPECTIVE_DEV_DATA_SCALING_NO_UNLOCK"
        ),
        "evidence_level": contract["evidence_level"],
        "inputs": {
            role: {"sha256": EXPECTED[role][0], "bytes": EXPECTED[role][1]}
            for role in ("cards", "train", "dev")
        },
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
        "decision": decision,
    }
    return summary, curve_rows, task_rows, pair_rows


def write_csv(path: Path, rows: list[dict[str, Any]]) -> None:
    if not rows:
        raise CurveError(f"refusing empty CSV {path.name}")
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)


def write_artifacts(
    output: Path,
    summary: dict[str, Any],
    curve_rows: list[dict[str, Any]],
    task_rows: list[dict[str, Any]],
    pair_rows: list[dict[str, Any]],
) -> None:
    if output.exists():
        raise CurveError("output directory already exists")
    output.mkdir(parents=True)
    (output / "summary.json").write_bytes(canonical(summary))
    write_csv(output / "curve.csv", curve_rows)
    write_csv(output / "per_task.csv", task_rows)
    with (output / "per_pair.jsonl").open("w", encoding="utf-8") as handle:
        for row in pair_rows:
            handle.write(compact(row) + "\n")
    artifacts = {}
    for path in sorted(output.iterdir(), key=lambda item: item.name):
        artifacts[path.name] = {"sha256": sha256_file(path), "bytes": path.stat().st_size}
    manifest = {
        "protocol": f"{PROTOCOL}-artifact-manifest-v1",
        "contract_sha256": CONTRACT_SHA256,
        "artifacts": artifacts,
    }
    (output / "artifact_manifest.json").write_bytes(canonical(manifest))


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("cards", type=Path)
    parser.add_argument("train", type=Path)
    parser.add_argument("dev", type=Path)
    parser.add_argument("output", type=Path)
    parser.add_argument(
        "--contract",
        type=Path,
        default=Path(__file__).with_name("critic_component_data_learning_curve_v1.json"),
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    summary, curve_rows, task_rows, pair_rows = analyze(args.cards, args.train, args.dev, args.contract)
    write_artifacts(args.output, summary, curve_rows, task_rows, pair_rows)
    print(compact({
        "status": summary["status"],
        "proper_score_positive": summary["decision"]["proper_score_positive"],
        "top1_positive": summary["decision"]["top1_positive"],
        "unique_cpu_critic_fits": summary["access_attestation"]["unique_cpu_critic_fits"],
    }))


if __name__ == "__main__":
    main()
