#!/usr/bin/env python3
"""Independent aggregate verifier for influence-bounded task reweighting."""

from __future__ import annotations

import argparse
from collections import Counter, defaultdict
import csv
from fractions import Fraction
import hashlib
import json
import math
import os
from pathlib import Path
from typing import Any


PROTOCOL = "endpoint-budget-influence-bounded-task-reweight-v1"
STATUS = "FROZEN_AFTER_STRUCTURAL_WEIGHT_DIAGNOSTICS_BEFORE_ANY_REWEIGHTED_MODEL_FIT_OR_PREDICTION"
RESULT = "endpoint-budget-influence-bounded-task-reweight-result-v1"
PRIVATE = "endpoint-budget-influence-bounded-task-reweight-private-pairs-v1"
CELL = "endpoint-budget-influence-bounded-task-reweight-cell-v1"
NEW_ARM = "influence_bounded_task_reweight"
OLD_YIELD = "yield_guarded_breadth"
OLD_UNIFORM = "exact_b_uniform_edge"
FOLD_SALT = "endpoint-label-efficiency-v1"


class VerificationError(RuntimeError):
    pass


def require(condition: bool, message: str) -> None:
    if not condition:
        raise VerificationError(message)


def canonical_bytes(value: Any) -> bytes:
    return (
        json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False)
        + "\n"
    ).encode("utf-8")


def sha_bytes(value: Any) -> str:
    return hashlib.sha256(canonical_bytes(value)).hexdigest()


def file_sha(path: Path) -> str:
    require(path.is_file() and not path.is_symlink(), f"unsafe file: {path}")
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(8 << 20), b""):
            digest.update(block)
    return digest.hexdigest()


def read_object(path: Path) -> dict[str, Any]:
    require(path.is_file() and not path.is_symlink(), f"unsafe JSON: {path}")
    value = json.loads(path.read_text(encoding="utf-8"))
    require(isinstance(value, dict), "object required")
    return value


def private_mode(path: Path) -> bool:
    return os.name == "nt" or path.stat().st_mode & 0o077 == 0


def run_fold(run: str) -> int:
    digest = hashlib.sha256((FOLD_SALT + "\0" + run).encode("utf-8")).digest()
    return int.from_bytes(digest[:8], "big") % 5


def identity_sha(kind: str, value: str) -> str:
    return hashlib.sha256((kind + "\0" + value).encode("utf-8")).hexdigest()


def pair_sha(row: dict[str, str]) -> str:
    return sha_bytes(
        {
            "endpoints": sorted((row["better"], row["worse"])),
            "parent": row["parent"],
            "task": row["task"],
            "physical_run": row["physical_run"],
        }
    )


def close(left: Any, right: Any, context: str) -> None:
    if isinstance(left, dict) and isinstance(right, dict):
        require(set(left) == set(right), context + " keys")
        for key in left:
            close(left[key], right[key], context + "." + key)
        return
    if isinstance(left, list) and isinstance(right, list):
        require(len(left) == len(right), context + " length")
        for index, (a, b) in enumerate(zip(left, right)):
            close(a, b, f"{context}[{index}]")
        return
    if isinstance(left, (int, float)) and isinstance(right, (int, float)) and not isinstance(left, bool) and not isinstance(right, bool):
        require(math.isclose(float(left), float(right), rel_tol=1e-11, abs_tol=1e-12), context)
        return
    require(left == right, context)


def weight_receipt(
    all_train: list[dict[str, str]], induced: list[dict[str, str]], ess_minimum: float, influence_cap: float
) -> dict[str, Any]:
    available = Counter(row["task"] for row in all_train)
    selected = Counter(row["task"] for row in induced)
    raw_by_task = {task: available[task] / count for task, count in selected.items()}
    raw_mean = sum(selected[task] * raw_by_task[task] for task in selected) / len(induced)
    direct = [raw_by_task[row["task"]] / raw_mean for row in induced]
    centered = sum((value - 1.0) ** 2 for value in direct)
    lambda_ess = 1.0 if centered == 0 else math.sqrt(
        max(0.0, (len(induced) / ess_minimum - len(induced)) / centered)
    )
    maximum_direct = max(direct)
    lambda_influence = (
        1.0
        if maximum_direct <= 1.0
        else (influence_cap * len(induced) - 1.0) / (maximum_direct - 1.0)
    )
    selected_lambda = max(0.0, min(1.0, lambda_ess, lambda_influence))
    weights = [1.0 + selected_lambda * (value - 1.0) for value in direct]
    total = sum(weights)
    ess = total * total / sum(value * value for value in weights)
    supported_total = sum(available[task] for task in selected)
    observed_share = {task: selected[task] / len(induced) for task in selected}
    target_share = {task: available[task] / supported_total for task in selected}
    weighted_mass: Counter[str] = Counter()
    for row, weight in zip(induced, weights):
        weighted_mass[row["task"]] += weight
    weighted_share = {task: weighted_mass[task] / total for task in selected}
    return {
        "induced_pairs": len(induced),
        "selected_tasks": len(selected),
        "outer_train_tasks": len(available),
        "selected_task_support_availability_fraction": supported_total / sum(available.values()),
        "direct_density_ratio": {
            "minimum": min(direct),
            "maximum": max(direct),
            "effective_sample_size_fraction": (
                len(induced) * len(induced) / sum(value * value for value in direct) / len(induced)
            ),
            "maximum_single_pair_weight_share": max(direct) / sum(direct),
        },
        "lambda_bounds": {
            "effective_sample_size": lambda_ess,
            "maximum_single_pair_influence": lambda_influence,
            "one": 1.0,
        },
        "selected_lambda": selected_lambda,
        "final_weight": {
            "minimum": min(weights),
            "maximum": max(weights),
            "mean": total / len(weights),
            "effective_sample_size": ess,
            "effective_sample_size_fraction": ess / len(weights),
            "maximum_single_pair_weight_share": max(weights) / total,
        },
        "task_distribution_l1": {
            "unweighted_to_availability": sum(
                abs(observed_share[task] - target_share[task]) for task in selected
            ),
            "weighted_to_availability": sum(
                abs(weighted_share[task] - target_share[task]) for task in selected
            ),
        },
        "raw_task_identities_emitted": False,
    }


def arrays(probabilities: list[float]) -> dict[str, list[float]]:
    result = {"correct": [], "log_loss": [], "brier": [], "probability": probabilities}
    for probability in probabilities:
        require(math.isfinite(probability) and 0 <= probability <= 1, "probability")
        clipped = min(max(probability, 1e-15), 1 - 1e-15)
        result["correct"].append(float(probability > 0.5))
        result["log_loss"].append(-math.log(clipped))
        result["brier"].append((1.0 - probability) ** 2)
    return result


def task_macro(values: list[float], tasks: list[str]) -> float:
    grouped: dict[str, list[float]] = defaultdict(list)
    for value, task in zip(values, tasks):
        grouped[task].append(value)
    return sum(sum(group) / len(group) for group in grouped.values()) / len(grouped)


def bootstrap_cluster(values: list[float], clusters: list[str], repetitions: int, seed: int) -> dict[str, Any]:
    import numpy as np

    grouped: dict[str, list[float]] = defaultdict(list)
    for value, cluster in zip(values, clusters):
        grouped[cluster].append(float(value))
    keys = sorted(grouped)
    rng = np.random.default_rng(seed)
    draws = []
    for _ in range(repetitions):
        sampled = rng.choice(len(keys), size=len(keys), replace=True)
        combined = [value for index in sampled for value in grouped[keys[int(index)]]]
        draws.append(float(np.mean(combined)))
    return {
        "point": float(np.mean(values)),
        "lo": float(np.quantile(draws, 0.025)),
        "hi": float(np.quantile(draws, 0.975)),
        "clusters": len(keys),
        "repetitions": repetitions,
    }


def bootstrap_task_macro(values: list[float], tasks: list[str], repetitions: int, seed: int) -> dict[str, Any]:
    import numpy as np

    grouped: dict[str, list[float]] = defaultdict(list)
    for value, task in zip(values, tasks):
        grouped[task].append(float(value))
    keys = sorted(grouped)
    means = [float(np.mean(grouped[key])) for key in keys]
    rng = np.random.default_rng(seed)
    draws = []
    for _ in range(repetitions):
        sampled = rng.choice(len(means), size=len(means), replace=True)
        draws.append(float(np.mean([means[int(index)] for index in sampled])))
    return {
        "point": float(np.mean(means)),
        "lo": float(np.quantile(draws, 0.025)),
        "hi": float(np.quantile(draws, 0.975)),
        "tasks": len(keys),
        "repetitions": repetitions,
    }


def compare(
    new: dict[str, list[float]], old: dict[str, list[float]], tasks: list[str], runs: list[str], repetitions: int, seed: int
) -> dict[str, Any]:
    deltas = {
        key: [a - b for a, b in zip(new[key], old[key])]
        for key in ("correct", "log_loss", "brier")
    }
    grouped: dict[str, list[float]] = defaultdict(list)
    for value, task in zip(deltas["correct"], tasks):
        grouped[task].append(value)
    means = {task: sum(values) / len(values) for task, values in grouped.items()}
    counts = Counter(tasks)
    dominant_count = max(counts.values())
    dominant = min(task for task, count in counts.items() if count == dominant_count)
    keep = [index for index, task in enumerate(tasks) if task != dominant]
    return {
        "pair_micro": {
            "pairwise_accuracy": sum(deltas["correct"]) / len(tasks),
            "log_loss": sum(deltas["log_loss"]) / len(tasks),
            "brier_score": sum(deltas["brier"]) / len(tasks),
        },
        "task_macro_accuracy": task_macro(deltas["correct"], tasks),
        "task_signs": {
            "positive": sum(value > 0 for value in means.values()),
            "negative": sum(value < 0 for value in means.values()),
            "equal": sum(value == 0 for value in means.values()),
        },
        "drop_dominant_task_pair_micro_accuracy": sum(deltas["correct"][index] for index in keep) / len(keep),
        "task_clustered_pair_micro_accuracy_bootstrap": bootstrap_cluster(
            deltas["correct"], tasks, repetitions, seed
        ),
        "run_clustered_pair_micro_accuracy_bootstrap": bootstrap_cluster(
            deltas["correct"], runs, repetitions, seed + 1000
        ),
        "task_macro_accuracy_bootstrap": bootstrap_task_macro(
            deltas["correct"], tasks, repetitions, seed + 2000
        ),
    }


def verify(args: argparse.Namespace) -> dict[str, Any]:
    protocol_path = args.protocol.resolve()
    require(file_sha(protocol_path) == args.protocol_sha256, "protocol SHA")
    protocol = read_object(protocol_path)
    require(protocol.get("protocol") == PROTOCOL and protocol.get("status") == STATUS, "protocol")
    require(protocol["known_before_freeze"]["reweighted_model_fit_prediction_or_metric_seen"] is False, "prior result")
    immutable = protocol["immutable_inputs"]
    source_root = args.source_root.resolve()
    require(str(source_root) == immutable["historical_formal_root"], "source root")
    for relative, digest in immutable["historical_artifacts"].items():
        require(file_sha(source_root / relative) == digest, "source SHA " + relative)

    topology_object = read_object(source_root / "firewall_a/topology.json")
    labels_object = read_object(source_root / "firewall_a/labels.json")
    selection_object = read_object(source_root / "selection_a.private.json")
    old_pairs_object = read_object(source_root / "fit/private_pairs.json")
    require(topology_object.get("all_source_rows_train") is True, "topology train-only")
    require(labels_object.get("all_source_rows_train") is True, "labels train-only")
    require(labels_object.get("senior_test_rows_emitted") == 0, "senior test")
    topology = []
    for row in topology_object["rows"]:
        require(row["source_split"] == "train" and row["u"] < row["v"], "topology row")
        topology.append(
            {
                "u": row["u"],
                "v": row["v"],
                "parent": row["parent"],
                "task": row["task"],
                "physical_run": row["physical_run"],
            }
        )
    labels = []
    for row in labels_object["rows"]:
        require(row["source_split"] == "train" and row["relation"] == "verified_direct_sibling", "label row")
        labels.append(
            {
                "better": row["better"],
                "worse": row["worse"],
                "parent": row["parent"],
                "task": row["task"],
                "physical_run": row["physical_run"],
            }
        )
    topology_keys = {
        (tuple(sorted((row["u"], row["v"]))), row["parent"], row["task"], row["physical_run"])
        for row in topology
    }
    label_keys = {
        (tuple(sorted((row["better"], row["worse"]))), row["parent"], row["task"], row["physical_run"])
        for row in labels
    }
    require(topology_keys == label_keys and len(topology) == len(labels) == 539, "source closure")
    train_topology = [row for row in topology if run_fold(row["physical_run"]) != 0]
    eval_labels = [row for row in labels if run_fold(row["physical_run"]) == 0]
    require(len(train_topology) == 401 and len(eval_labels) == 138, "fold sizes")

    selections = {}
    for entry in selection_object["arms"][OLD_YIELD]:
        selections[int(entry["budget"])] = set(entry["endpoint_ids"])
    ess_minimum = float(Fraction(protocol["model"]["sample_weight"]["effective_sample_size_fraction_minimum"]))
    influence_cap = float(Fraction(protocol["model"]["sample_weight"]["maximum_single_pair_weight_share"]))
    expected_receipts = {}
    for budget in (96, 192):
        selected = selections[budget]
        induced = [row for row in train_topology if row["u"] in selected and row["v"] in selected]
        expected_receipts[str(budget)] = weight_receipt(
            train_topology, induced, ess_minimum, influence_cap
        )

    summary_path = args.summary.resolve()
    private_path = args.private_pairs.resolve()
    runs_path = args.runs_csv.resolve()
    checkpoint_root = args.checkpoint_dir.resolve()
    for path in (summary_path, private_path, runs_path, checkpoint_root):
        require(private_mode(path), "private output mode")
    summary = read_object(summary_path)
    witness = read_object(private_path)
    require(summary.get("protocol") == RESULT and summary.get("status") == "COMPLETE", "summary")
    require(witness.get("protocol") == PRIVATE, "private witness")
    require(
        summary.get("protocol_sha256")
        == witness.get("protocol_sha256")
        == args.protocol_sha256,
        "result protocol binding",
    )
    require(summary.get("source_commit") == witness.get("source_commit") == args.source_commit, "source commit")
    require(file_sha(private_path) == summary["private_pair_witness_sha256"], "private witness SHA")
    close(summary["structural_weight_receipts"], expected_receipts, "weight receipts")

    expected_pairs = [
        {
            "pair_identity_sha256": pair_sha(row),
            "task_sha256": identity_sha("task", row["task"]),
            "physical_run_sha256": identity_sha("physical_run", row["physical_run"]),
        }
        for row in eval_labels
    ]
    tasks = [row["task_sha256"] for row in expected_pairs]
    runs = [row["physical_run_sha256"] for row in expected_pairs]
    new_rows: dict[int, list[dict[str, Any]]] = defaultdict(list)
    for row in witness["rows"]:
        require(row["arm"] == NEW_ARM, "new arm")
        new_rows[int(row["endpoint_budget"])].append(row)
    require(set(new_rows) == {96, 192}, "new budgets")
    new_arrays = {}
    for budget, rows_for_budget in new_rows.items():
        rows_for_budget.sort(key=lambda row: int(row["pair_index"]))
        require([row["pair_index"] for row in rows_for_budget] == list(range(len(eval_labels))), "new pair order")
        for witness_row, expected in zip(rows_for_budget, expected_pairs):
            require(witness_row["pair_identity_sha256"] == expected["pair_identity_sha256"], "new pair fingerprint")
            require(witness_row["task_sha256"] == expected["task_sha256"], "new task fingerprint")
            require(witness_row["physical_run_sha256"] == expected["physical_run_sha256"], "new run fingerprint")
        new_arrays[budget] = arrays([float(row["probability_first_better"]) for row in rows_for_budget])

    wanted = {(arm, budget) for arm in (OLD_UNIFORM, OLD_YIELD) for budget in (96, 192)}
    old_rows: dict[tuple[str, int], list[dict[str, Any]]] = defaultdict(list)
    for row in old_pairs_object["rows"]:
        key = (row["arm"], int(row["endpoint_budget"]))
        if key in wanted:
            old_rows[key].append(row)
    require(set(old_rows) == wanted, "old cells")
    old_arrays = {}
    for key, rows_for_cell in old_rows.items():
        rows_for_cell.sort(key=lambda row: int(row["pair_index"]))
        require([row["pair_index"] for row in rows_for_cell] == list(range(len(eval_labels))), "old order")
        for witness_row, expected in zip(rows_for_cell, expected_pairs):
            require(witness_row["pair_identity_sha256"] == expected["pair_identity_sha256"], "old pair fingerprint")
        old_arrays[key] = arrays([float(row["probability_first_better"]) for row in rows_for_cell])

    model_rows = {int(row["endpoint_budget"]): row for row in summary["model_rows"]}
    require(set(model_rows) == {96, 192}, "model rows")
    expected_checkpoint_names = {f"{NEW_ARM}__{budget}.json" for budget in (96, 192)}
    require(set(summary["fit_checkpoints"]) == expected_checkpoint_names, "checkpoint names")
    for budget in (96, 192):
        checkpoint_path = checkpoint_root / f"{NEW_ARM}__{budget}.json"
        require(file_sha(checkpoint_path) == summary["fit_checkpoints"][checkpoint_path.name], "checkpoint SHA")
        checkpoint = read_object(checkpoint_path)
        require(
            checkpoint.get("protocol") == CELL
            and checkpoint.get("source_commit") == args.source_commit
            and checkpoint.get("protocol_sha256") == args.protocol_sha256
            and checkpoint.get("endpoint_budget") == budget,
            "checkpoint binding",
        )
        checkpoint_rows = sorted(checkpoint["pair_rows"], key=lambda row: row["pair_index"])
        require(checkpoint_rows == new_rows[budget], "checkpoint pair rows")
        current = new_arrays[budget]
        metrics = checkpoint["metrics"]
        close(metrics["weight_receipt"], expected_receipts[str(budget)], "checkpoint weight receipt")
        require(math.isclose(metrics["pairwise_accuracy"], sum(current["correct"]) / len(eval_labels), abs_tol=1e-12), "accuracy")
        require(math.isclose(metrics["log_loss"], sum(current["log_loss"]) / len(eval_labels), abs_tol=1e-12), "logloss")
        require(math.isclose(metrics["brier_score"], sum(current["brier"]) / len(eval_labels), abs_tol=1e-12), "brier")
        row = model_rows[budget]
        require(row["arm"] == NEW_ARM and row["selected_endpoints"] == budget, "model row identity")
        close(row["pairwise_accuracy"], metrics["pairwise_accuracy"], "model accuracy")
        close(row["task_macro_accuracy"], task_macro(current["correct"], tasks), "model task macro")
        close(row["log_loss"], metrics["log_loss"], "model logloss")
        close(row["brier_score"], metrics["brier_score"], "model brier")
        close(row["weight_lambda"], expected_receipts[str(budget)]["selected_lambda"], "model lambda")

    with runs_path.open(encoding="utf-8", newline="") as handle:
        csv_rows = list(csv.DictReader(handle))
    require(len(csv_rows) == len(summary["model_rows"]), "CSV row count")
    for csv_row, summary_row in zip(csv_rows, summary["model_rows"]):
        require(set(csv_row) == set(summary_row), "CSV columns")
        require(all(csv_row[key] == str(value) for key, value in summary_row.items()), "CSV equality")

    repetitions = int(protocol["metrics"]["bootstrap_repetitions"])
    base_seed = int(protocol["metrics"]["bootstrap_seed"])
    comparisons = {}
    for budget in (96, 192):
        comparisons[str(budget)] = {
            "new_minus_old_yield": compare(
                new_arrays[budget], old_arrays[(OLD_YIELD, budget)], tasks, runs, repetitions, base_seed + budget
            ),
            "new_minus_uniform": compare(
                new_arrays[budget], old_arrays[(OLD_UNIFORM, budget)], tasks, runs, repetitions, base_seed + 10000 + budget
            ),
        }
    close(summary["paired_comparisons"], comparisons, "comparisons")
    support_minimum = float(
        Fraction(protocol["structural_gates_before_model_fit"]["minimum_selected_task_support_availability_fraction"])
    )
    terminal_old = comparisons["192"]["new_minus_old_yield"]
    terminal_uniform = comparisons["192"]["new_minus_uniform"]
    gates = {
        "structural_influence_gates_all_pass": all(
            receipt["selected_task_support_availability_fraction"] + 1e-12 >= support_minimum
            and receipt["final_weight"]["effective_sample_size_fraction"] + 1e-12 >= ess_minimum
            and receipt["final_weight"]["maximum_single_pair_weight_share"] <= influence_cap + 1e-12
            for receipt in expected_receipts.values()
        ),
        "task_distribution_l1_strictly_lower_at_both_budgets": all(
            receipt["task_distribution_l1"]["weighted_to_availability"]
            < receipt["task_distribution_l1"]["unweighted_to_availability"]
            for receipt in expected_receipts.values()
        ),
        "task_macro_accuracy_delta_new_minus_old_yield_strictly_positive_at_both_budgets": all(
            comparisons[str(budget)]["new_minus_old_yield"]["task_macro_accuracy"] > 0
            for budget in (96, 192)
        ),
        "terminal_pair_micro_accuracy_delta_new_minus_old_yield_nonnegative": terminal_old["pair_micro"][
            "pairwise_accuracy"
        ]
        >= 0,
        "terminal_log_loss_and_brier_delta_new_minus_old_yield_nonpositive": terminal_old["pair_micro"][
            "log_loss"
        ]
        <= 0
        and terminal_old["pair_micro"]["brier_score"] <= 0,
        "terminal_pair_micro_task_macro_and_drop_dominant_accuracy_delta_new_minus_uniform_nonnegative": (
            terminal_uniform["pair_micro"]["pairwise_accuracy"] >= 0
            and terminal_uniform["task_macro_accuracy"] >= 0
            and terminal_uniform["drop_dominant_task_pair_micro_accuracy"] >= 0
        ),
        "positive_task_count_at_least_negative_task_count_at_both_budgets": all(
            comparisons[str(budget)]["new_minus_old_yield"]["task_signs"]["positive"]
            >= comparisons[str(budget)]["new_minus_old_yield"]["task_signs"]["negative"]
            for budget in (96, 192)
        ),
    }
    require(summary["advancement_gates"] == gates, "advancement gates")
    classes = protocol["advancement_gates_historical_development_only"]
    expected_class = classes["if_all_gates_pass"] if all(gates.values()) else classes["if_any_gate_fails"]
    require(summary["classification"] == expected_class, "classification")
    require(summary["scope"]["prospective_first960_target300_target522_values_used"] is False, "prospective scope")
    require(summary["population"]["senior_test_rows_used"] is False, "senior test scope")

    identities = {
        value
        for row in topology
        for value in (row["u"], row["v"], row["parent"], row["task"], row["physical_run"])
    }
    public_text = canonical_bytes(summary).decode("utf-8")
    private_text = canonical_bytes(witness).decode("utf-8")
    require(not any(json.dumps(value, ensure_ascii=False) in public_text for value in identities), "public identity leak")
    require(not any(json.dumps(value, ensure_ascii=False) in private_text for value in identities), "private identity leak")
    return {
        "protocol": "endpoint-budget-influence-bounded-task-reweight-independent-verifier-v1",
        "protocol_sha256": args.protocol_sha256,
        "source_commit": args.source_commit,
        "summary_sha256": file_sha(summary_path),
        "runs_csv_sha256": file_sha(runs_path),
        "private_pair_witness_sha256": file_sha(private_path),
        "classification": summary["classification"],
        "all_aggregate_fields_equal": True,
        "model_refits": 0,
        "prospective_values_read": False,
        "senior_test_rows_used": False,
        "raw_identities_emitted": False,
    }


def write_exclusive(path: Path, value: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    require(not path.exists(), "output exists")
    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    with os.fdopen(fd, "wb") as handle:
        handle.write(canonical_bytes(value))


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--protocol", type=Path, required=True)
    parser.add_argument("--protocol-sha256", required=True)
    parser.add_argument("--source-commit", required=True)
    parser.add_argument("--source-root", type=Path, required=True)
    parser.add_argument("--summary", type=Path, required=True)
    parser.add_argument("--runs-csv", type=Path, required=True)
    parser.add_argument("--private-pairs", type=Path, required=True)
    parser.add_argument("--checkpoint-dir", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    result = verify(args)
    write_exclusive(args.output.resolve(), result)
    print(canonical_bytes(result).decode("utf-8"), end="")


if __name__ == "__main__":
    main()
