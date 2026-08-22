#!/usr/bin/env python3
"""Measure gap-weighted and parent-level utility of the frozen TF-IDF baseline."""
from __future__ import annotations

import argparse
import csv
import hashlib
import json
import math
import os
import zlib
from collections import Counter, defaultdict, deque
from pathlib import Path
from typing import Any, Iterable

import numpy as np


PROTOCOL = "tfidf-retrospective-utility-audit-v1"
PAIR_FIELDS = {
    "better",
    "better_run",
    "correct",
    "index",
    "margin",
    "parent",
    "semantics",
    "split",
    "task",
    "tie",
    "worse",
    "worse_run",
}
SUBSETS = ("merged", "Draft", "Improve")


class AuditError(RuntimeError):
    """Raised when a frozen input or a utility invariant fails closed."""


def canonical_json(value: Any) -> str:
    return json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
    )


def pretty_json(value: Any) -> bytes:
    return (
        json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True, allow_nan=False)
        + "\n"
    ).encode("utf-8")


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1 << 20), b""):
            digest.update(block)
    return digest.hexdigest()


def checked_file(path_value: str | Path, identity: dict[str, Any], label: str) -> Path:
    path_input = Path(path_value)
    if path_input.is_symlink() or not path_input.is_file():
        raise AuditError(f"{label} is absent, symlinked, or non-regular")
    path = path_input.resolve()
    if (
        not isinstance(identity, dict)
        or not isinstance(identity.get("bytes"), int)
        or not isinstance(identity.get("sha256"), str)
        or path.stat().st_size != identity["bytes"]
        or sha256_file(path) != identity["sha256"]
    ):
        raise AuditError(f"{label} frozen identity mismatch")
    return path


def read_json(path: Path, label: str) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise AuditError(f"invalid {label} JSON") from exc
    if not isinstance(value, dict):
        raise AuditError(f"{label} must be a JSON object")
    return value


def load_protocol(path_value: str | Path) -> tuple[Path, dict[str, Any]]:
    path_input = Path(path_value)
    if path_input.is_symlink() or not path_input.is_file():
        raise AuditError("protocol is absent, symlinked, or non-regular")
    path = path_input.resolve()
    protocol = read_json(path, "protocol")
    if (
        protocol.get("protocol") != PROTOCOL
        or protocol.get("status") != "FROZEN_BEFORE_GRADE_GAP_AND_PARENT_UTILITY_READ"
    ):
        raise AuditError("protocol is not the frozen v1 contract")
    frozen = protocol.get("frozen_inputs")
    if not isinstance(frozen, dict) or set(frozen) != {
        "cards",
        "cost_summary",
        "tfidf_per_pair",
        "tfidf_summary",
    }:
        raise AuditError("protocol frozen-input schema mismatch")
    bootstrap = protocol.get("bootstrap")
    if (
        not isinstance(bootstrap, dict)
        or not isinstance(bootstrap.get("replicates"), int)
        or bootstrap["replicates"] < 1000
        or not isinstance(bootstrap.get("task_seed"), int)
    ):
        raise AuditError("protocol bootstrap contract invalid")
    return path, protocol


def load_pairs(path: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    keys = set()
    indices: dict[str, list[int]] = defaultdict(list)
    with path.open(encoding="utf-8") as handle:
        for line_number, line in enumerate(handle, 1):
            if not line.strip():
                raise AuditError(f"blank pair row at line {line_number}")
            try:
                row = json.loads(line)
            except json.JSONDecodeError as exc:
                raise AuditError(f"invalid pair JSON at line {line_number}") from exc
            if not isinstance(row, dict) or set(row) != PAIR_FIELDS:
                raise AuditError(f"pair schema mismatch at line {line_number}")
            split = row["split"]
            semantics = row["semantics"]
            if split not in {"dev", "test"} or semantics not in {"Draft", "Improve"}:
                raise AuditError("pair split or semantics outside frozen contract")
            string_fields = (
                "task",
                "parent",
                "better",
                "worse",
                "better_run",
                "worse_run",
            )
            if not all(isinstance(row[field], str) and row[field] for field in string_fields):
                raise AuditError("pair string identity invalid")
            if row["better"] == row["worse"]:
                raise AuditError("self-pair")
            margin = row["margin"]
            if (
                isinstance(margin, bool)
                or not isinstance(margin, (int, float))
                or not math.isfinite(float(margin))
                or margin == 0
                or not isinstance(row["correct"], bool)
                or not isinstance(row["tie"], bool)
                or row["tie"] is not False
                or row["correct"] is not (margin > 0)
            ):
                raise AuditError("pair margin/correct/tie contract mismatch")
            if not isinstance(row["index"], int) or isinstance(row["index"], bool):
                raise AuditError("pair index invalid")
            key = (
                split,
                row["task"],
                row["parent"],
                *sorted((row["better"], row["worse"])),
            )
            if key in keys:
                raise AuditError("duplicate unordered pair")
            keys.add(key)
            indices[split].append(row["index"])
            rows.append(row)
    if not rows:
        raise AuditError("empty pair input")
    for split, values in indices.items():
        if values != list(range(len(values))):
            raise AuditError(f"{split} pair indices are not contiguous in file order")
    return rows


def validate_tfidf_summary(summary: dict[str, Any], rows: list[dict[str, Any]]) -> None:
    if summary.get("protocol") != "critic-component-char-tfidf-baseline-v1" or summary.get("status") != "BASELINE_VALID":
        raise AuditError("TF-IDF summary status mismatch")
    if summary.get("model", {}).get("anti_symmetry_max_abs") != 0.0:
        raise AuditError("TF-IDF summary antisymmetry mismatch")
    metrics = summary.get("metrics")
    if not isinstance(metrics, dict):
        raise AuditError("TF-IDF summary metrics missing")
    for split in ("dev", "test"):
        selected = [row for row in rows if row["split"] == split]
        observed = float(np.mean([row["correct"] for row in selected]))
        expected = metrics.get(split, {}).get("merged", {})
        if expected.get("pairs") != len(selected) or abs(expected.get("micro_accuracy", -1.0) - observed) > 1e-15:
            raise AuditError("TF-IDF summary does not match per-pair rows")


def validate_cost_summary(summary: dict[str, Any], protocol: dict[str, Any]) -> dict[str, Any]:
    if summary.get("protocol") != "deployment_cost_attestation_v2" or summary.get("status") != "DEPLOYMENT_COST_ADVANTAGE_SUPPORTED":
        raise AuditError("cost summary status mismatch")
    scope = summary.get("scope")
    model = summary.get("models", {}).get(protocol["cost_contract"]["model"])
    if not isinstance(scope, dict) or not isinstance(model, dict):
        raise AuditError("cost summary schema mismatch")
    if (
        scope.get("accuracy_computed") is not False
        or scope.get("prospective_vault_opened") is not False
        or scope.get("gpu_used") is not False
        or scope.get("api_used") is not False
    ):
        raise AuditError("cost summary scope mismatch")
    query_fraction = model.get("query_p95_fraction_of_execution_parallel_p50")
    break_even = model.get("initialization_break_even_parallel_pairs")
    if (
        not isinstance(query_fraction, (int, float))
        or not isinstance(break_even, int)
        or query_fraction >= protocol["cost_contract"][
            "require_query_p95_fraction_of_execution_parallel_p50_below"
        ]
        or break_even
        > protocol["cost_contract"][
            "require_initialization_break_even_parallel_pairs_at_most"
        ]
    ):
        raise AuditError("cost positive gate mismatch")
    return {
        "initialization_p50_s": model["initialization_s"]["p50"],
        "initialization_break_even_parallel_pairs": break_even,
        "pair_query_p50_ms": model["single_pair_query_ms"]["p50"],
        "pair_query_p95_ms": model["single_pair_query_ms"]["p95"],
        "execution_parallel_p50_over_query_p50": model[
            "execution_parallel_p50_over_query_p50"
        ],
        "query_p95_fraction_of_execution_parallel_p50": query_fraction,
        "execution_parallel_p50_s": summary["runtime_reference"][
            "pair_ideal_parallel_runtime_s"
        ]["p50"],
    }


def load_card_truth(path: Path, needed: set[str]) -> tuple[dict[str, dict[str, Any]], dict[str, int]]:
    try:
        grouped = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise AuditError("invalid Cards JSON") from exc
    if not isinstance(grouped, dict):
        raise AuditError("Cards root is not grouped")
    truth: dict[str, dict[str, Any]] = {}
    seen = set()
    total = 0
    for run_id, cards in grouped.items():
        if not isinstance(run_id, str) or not isinstance(cards, list):
            raise AuditError("invalid Cards run group")
        for card in cards:
            total += 1
            if not isinstance(card, dict) or not isinstance(card.get("id"), str):
                raise AuditError("invalid Card")
            card_id = card["id"]
            if card_id in seen:
                raise AuditError("duplicate Card id")
            seen.add(card_id)
            if card_id not in needed:
                continue
            task = card.get("task")
            label = card.get("label")
            if (
                not isinstance(task, dict)
                or not isinstance(task.get("name"), str)
                or not isinstance(task.get("higher_is_better"), bool)
                or not isinstance(label, dict)
                or isinstance(label.get("graded"), bool)
                or not isinstance(label.get("graded"), (int, float))
                or not math.isfinite(float(label["graded"]))
            ):
                raise AuditError("needed Card lacks finite raw grade or task direction")
            grade = float(label["graded"])
            truth[card_id] = {
                "task": task["name"],
                "higher_is_better": task["higher_is_better"],
                "raw_grade": grade,
                "utility": grade if task["higher_is_better"] else -grade,
            }
    if set(truth) != needed:
        raise AuditError("pair endpoint missing from Cards")
    return truth, {"cards": total, "run_groups": len(grouped), "needed_cards": len(needed)}


def build_pair_utility(
    rows: list[dict[str, Any]], truth: dict[str, dict[str, Any]], grade_tolerance: float
) -> list[dict[str, Any]]:
    output = []
    for row in rows:
        better = truth[row["better"]]
        worse = truth[row["worse"]]
        if better["task"] != row["task"] or worse["task"] != row["task"]:
            raise AuditError("pair/Card task mismatch")
        if better["higher_is_better"] != worse["higher_is_better"]:
            raise AuditError("pair endpoints disagree on task direction")
        gap = better["utility"] - worse["utility"]
        if not math.isfinite(gap) or gap <= grade_tolerance:
            raise AuditError("better/worse raw-grade orientation is not strictly positive")
        correct = row["correct"]
        output.append(
            {
                "split": row["split"],
                "index": row["index"],
                "task": row["task"],
                "parent": row["parent"],
                "semantics": row["semantics"],
                "better": row["better"],
                "worse": row["worse"],
                "margin": float(row["margin"]),
                "correct": correct,
                "oriented_raw_gap": float(gap),
                "selected_regret": 0.0 if correct else float(gap),
            }
        )
    return output


def parent_prediction(
    rows: list[dict[str, Any]],
    truth: dict[str, dict[str, Any]],
    *,
    margin_tolerance: float,
    grade_tolerance: float,
    tie_tolerance: float,
) -> dict[str, Any]:
    adjacency: dict[str, list[tuple[str, float]]] = defaultdict(list)
    endpoints = set()
    for row in rows:
        better, worse, margin = row["better"], row["worse"], float(row["margin"])
        endpoints.update((better, worse))
        adjacency[better].append((worse, -margin))
        adjacency[worse].append((better, margin))
    root = min(endpoints)
    potentials = {root: 0.0}
    queue: deque[str] = deque([root])
    max_residual = 0.0
    while queue:
        current = queue.popleft()
        for neighbor, delta in adjacency[current]:
            proposed = potentials[current] + delta
            if neighbor not in potentials:
                potentials[neighbor] = proposed
                queue.append(neighbor)
            else:
                max_residual = max(max_residual, abs(potentials[neighbor] - proposed))
    if set(potentials) != endpoints:
        raise AuditError("parent margin graph is disconnected")
    if max_residual > margin_tolerance:
        raise AuditError("parent margin graph is inconsistent")
    predicted_max = max(potentials.values())
    predicted = [
        endpoint
        for endpoint, value in potentials.items()
        if abs(value - predicted_max) <= tie_tolerance
    ]
    if len(predicted) != 1:
        raise AuditError("parent prediction winner is not unique")
    utilities = {
        endpoint: truth[endpoint]["utility"] for endpoint in sorted(endpoints)
    }
    oracle_utility = max(utilities.values())
    random_utility = float(np.mean(list(utilities.values())))
    potential = oracle_utility - random_utility
    if potential <= grade_tolerance:
        raise AuditError("parent has zero oracle-over-random potential")
    selected_utility = utilities[predicted[0]]
    regret = oracle_utility - selected_utility
    if regret < -grade_tolerance:
        raise AuditError("negative parent regret")
    return {
        "candidates": len(endpoints),
        "edges": len(rows),
        "max_margin_residual": max_residual,
        "predicted": predicted[0],
        "top1_exact": regret <= grade_tolerance,
        "oracle_minus_random": float(potential),
        "selected_minus_random": float(selected_utility - random_utility),
        "regret": float(max(0.0, regret)),
    }


def build_parent_utility(
    pair_rows: list[dict[str, Any]],
    truth: dict[str, dict[str, Any]],
    tolerances: dict[str, float],
) -> list[dict[str, Any]]:
    grouped: dict[tuple[str, str, str, str], list[dict[str, Any]]] = defaultdict(list)
    for row in pair_rows:
        grouped[(row["split"], row["task"], row["parent"], row["semantics"])].append(row)
    output = []
    for (split, task, parent, semantics), rows in sorted(grouped.items()):
        result = parent_prediction(
            rows,
            truth,
            margin_tolerance=tolerances["margin_consistency"],
            grade_tolerance=tolerances["grade"],
            tie_tolerance=tolerances["prediction_tie"],
        )
        output.append(
            {
                "split": split,
                "task": task,
                "parent": parent,
                "semantics": semantics,
                **result,
            }
        )
    return output


def bootstrap_task_values(
    values: dict[str, float], *, metric: str, base_seed: int, replicates: int
) -> dict[str, Any]:
    tasks = sorted(values)
    array = np.asarray([values[task] for task in tasks], dtype=np.float64)
    if not len(array) or not np.isfinite(array).all():
        raise AuditError(f"invalid task values for {metric}")
    seed = int((base_seed + zlib.crc32(metric.encode("utf-8"))) % (2**32))
    rng = np.random.default_rng(seed)
    sampled = rng.integers(0, len(array), size=(replicates, len(array)))
    estimates = np.mean(array[sampled], axis=1)
    low, high = np.quantile(estimates, [0.025, 0.975], method="linear")
    return {
        "point": float(np.mean(array)),
        "ci95": [float(low), float(high)],
        "tasks": len(array),
        "replicates": replicates,
        "seed": seed,
        "task_values": dict(sorted(values.items())),
    }


def subset_metrics(
    split: str,
    subset: str,
    pair_rows: list[dict[str, Any]],
    parent_rows: list[dict[str, Any]],
    *,
    base_seed: int,
    replicates: int,
) -> dict[str, Any]:
    pairs = [
        row
        for row in pair_rows
        if row["split"] == split and (subset == "merged" or row["semantics"] == subset)
    ]
    parents = [
        row
        for row in parent_rows
        if row["split"] == split and (subset == "merged" or row["semantics"] == subset)
    ]
    if not pairs or not parents:
        raise AuditError("empty requested split/subset")
    tasks = sorted({row["task"] for row in pairs})
    if set(tasks) != {row["task"] for row in parents}:
        raise AuditError("pair and parent task support differ")
    unweighted = {}
    weighted = {}
    parent_capture = {}
    parent_top1 = {}
    parent_regret = {}
    for task in tasks:
        task_pairs = [row for row in pairs if row["task"] == task]
        task_parents = [row for row in parents if row["task"] == task]
        gap_total = sum(row["oriented_raw_gap"] for row in task_pairs)
        correct_gap = sum(
            row["oriented_raw_gap"] for row in task_pairs if row["correct"]
        )
        potential = sum(row["oracle_minus_random"] for row in task_parents)
        selected_gain = sum(row["selected_minus_random"] for row in task_parents)
        if gap_total <= 0 or potential <= 0:
            raise AuditError("task has nonpositive pair or parent utility denominator")
        unweighted[task] = float(np.mean([row["correct"] for row in task_pairs]))
        weighted[task] = float(correct_gap / gap_total)
        parent_capture[task] = float(selected_gain / potential)
        parent_top1[task] = float(np.mean([row["top1_exact"] for row in task_parents]))
        parent_regret[task] = float(
            sum(row["regret"] for row in task_parents) / potential
        )
    difference = {task: weighted[task] - unweighted[task] for task in tasks}
    prefix = f"{split}.{subset}"
    weighted_receipt = bootstrap_task_values(
        weighted,
        metric=prefix + ".pair_gap_weighted_accuracy",
        base_seed=base_seed,
        replicates=replicates,
    )
    return {
        "pairs": len(pairs),
        "parents": len(parents),
        "tasks": len(tasks),
        "dominant_parent_task_share": max(
            Counter(row["task"] for row in parents).values()
        )
        / len(parents),
        "pair_unweighted_accuracy": bootstrap_task_values(
            unweighted,
            metric=prefix + ".pair_unweighted_accuracy",
            base_seed=base_seed,
            replicates=replicates,
        ),
        "pair_gap_weighted_accuracy": weighted_receipt,
        "pair_gap_capture": {
            "point": 2 * weighted_receipt["point"] - 1,
            "ci95": [
                2 * weighted_receipt["ci95"][0] - 1,
                2 * weighted_receipt["ci95"][1] - 1,
            ],
        },
        "pair_gap_weighted_minus_unweighted": bootstrap_task_values(
            difference,
            metric=prefix + ".pair_gap_weighted_minus_unweighted",
            base_seed=base_seed,
            replicates=replicates,
        ),
        "parent_gain_capture": bootstrap_task_values(
            parent_capture,
            metric=prefix + ".parent_gain_capture",
            base_seed=base_seed,
            replicates=replicates,
        ),
        "parent_top1_accuracy": bootstrap_task_values(
            parent_top1,
            metric=prefix + ".parent_top1_accuracy",
            base_seed=base_seed,
            replicates=replicates,
        ),
        "parent_normalized_regret": bootstrap_task_values(
            parent_regret,
            metric=prefix + ".parent_normalized_regret",
            base_seed=base_seed,
            replicates=replicates,
        ),
    }


def analyze(
    protocol_path: str | Path,
    cards_path: str | Path,
    pair_path: str | Path,
    tfidf_summary_path: str | Path,
    cost_summary_path: str | Path,
) -> tuple[dict[str, Any], list[dict[str, Any]], list[dict[str, Any]]]:
    frozen_protocol_path, protocol = load_protocol(protocol_path)
    frozen = protocol["frozen_inputs"]
    cards = checked_file(cards_path, frozen["cards"], "cards")
    pairs_file = checked_file(pair_path, frozen["tfidf_per_pair"], "tfidf per-pair")
    tfidf_summary_file = checked_file(
        tfidf_summary_path, frozen["tfidf_summary"], "TF-IDF summary"
    )
    cost_summary_file = checked_file(
        cost_summary_path, frozen["cost_summary"], "cost summary"
    )
    pair_rows = load_pairs(pairs_file)
    validate_tfidf_summary(read_json(tfidf_summary_file, "TF-IDF summary"), pair_rows)
    cost = validate_cost_summary(read_json(cost_summary_file, "cost summary"), protocol)
    needed = {row[field] for row in pair_rows for field in ("better", "worse")}
    truth, card_inventory = load_card_truth(cards, needed)
    tolerances = protocol["tolerances"]
    utility_pairs = build_pair_utility(pair_rows, truth, tolerances["grade"])
    utility_parents = build_parent_utility(pair_rows, truth, tolerances)
    bootstrap = protocol["bootstrap"]
    metrics = {
        split: {
            subset: subset_metrics(
                split,
                subset,
                utility_pairs,
                utility_parents,
                base_seed=bootstrap["task_seed"],
                replicates=bootstrap["replicates"],
            )
            for subset in SUBSETS
        }
        for split in ("dev", "test")
    }
    test = metrics["test"]["merged"]
    gate_contract = protocol["primary_positive_gates"]
    gates = {
        "integrity_and_cost_gates_pass": True,
        "test_tasks_at_least_20": test["tasks"] >= gate_contract["test_tasks_at_least"],
        "test_parents_at_least_300": test["parents"]
        >= gate_contract["test_parents_at_least"],
        "test_pair_gap_weighted_accuracy_task_ci_lower_gt_0_5": test[
            "pair_gap_weighted_accuracy"
        ]["ci95"][0]
        > gate_contract["test_pair_gap_weighted_accuracy_task_cluster_ci95_lower_gt"],
        "test_parent_gain_capture_task_ci_lower_gt_0": test["parent_gain_capture"][
            "ci95"
        ][0]
        > gate_contract["test_parent_gain_capture_task_cluster_ci95_lower_gt"],
    }
    positive = all(gates.values())
    summary = {
        "protocol": PROTOCOL,
        "status": (
            "RETROSPECTIVE_COST_UTILITY_POSITIVE" if positive else "VALID_NO_STRONG_COST_UTILITY_POSITIVE"
        ),
        "evidence_level": "retrospective_accuracy_touched_component_clean_test",
        "protocol_sha256": sha256_file(frozen_protocol_path),
        "inputs": frozen,
        "card_inventory": card_inventory,
        "pair_inventory": {
            "rows": len(pair_rows),
            "dev": sum(row["split"] == "dev" for row in pair_rows),
            "test": sum(row["split"] == "test" for row in pair_rows),
            "needed_endpoints": len(needed),
        },
        "cost": cost,
        "metrics": metrics,
        "primary_positive_gates": gates,
        "primary_positive_gates_pass": positive,
        "claim_boundary": protocol["claim_boundary"],
        "access_attestation": {
            "future_or_prospective_vault_opened": False,
            "gpu_used": False,
            "api_used": False,
            "model_fit": False,
            "base_llm_updated": False,
        },
    }
    return summary, utility_pairs, utility_parents


def write_outputs(
    output_value: str | Path,
    summary: dict[str, Any],
    pair_rows: list[dict[str, Any]],
    parent_rows: list[dict[str, Any]],
) -> None:
    output_input = Path(output_value)
    if output_input.is_symlink() or output_input.exists():
        raise AuditError("output directory already exists or is symlinked")
    output = output_input.resolve()
    output.mkdir(parents=True)
    (output / "summary.json").write_bytes(pretty_json(summary))
    with (output / "per_pair_utility.jsonl").open("x", encoding="utf-8", newline="\n") as handle:
        for row in pair_rows:
            handle.write(canonical_json(row) + "\n")
    with (output / "per_parent_utility.jsonl").open("x", encoding="utf-8", newline="\n") as handle:
        for row in parent_rows:
            handle.write(canonical_json(row) + "\n")
    with (output / "per_task.csv").open("x", encoding="utf-8", newline="") as handle:
        fields = (
            "split",
            "subset",
            "task",
            "pair_unweighted_accuracy",
            "pair_gap_weighted_accuracy",
            "parent_gain_capture",
            "parent_top1_accuracy",
            "parent_normalized_regret",
        )
        writer = csv.DictWriter(handle, fieldnames=fields, lineterminator="\n")
        writer.writeheader()
        for split in ("dev", "test"):
            for subset in SUBSETS:
                metrics = summary["metrics"][split][subset]
                tasks = sorted(metrics["pair_unweighted_accuracy"]["task_values"])
                for task in tasks:
                    writer.writerow(
                        {
                            "split": split,
                            "subset": subset,
                            "task": task,
                            "pair_unweighted_accuracy": metrics[
                                "pair_unweighted_accuracy"
                            ]["task_values"][task],
                            "pair_gap_weighted_accuracy": metrics[
                                "pair_gap_weighted_accuracy"
                            ]["task_values"][task],
                            "parent_gain_capture": metrics["parent_gain_capture"][
                                "task_values"
                            ][task],
                            "parent_top1_accuracy": metrics["parent_top1_accuracy"][
                                "task_values"
                            ][task],
                            "parent_normalized_regret": metrics[
                                "parent_normalized_regret"
                            ]["task_values"][task],
                        }
                    )
    manifest = {
        name: sha256_file(output / name)
        for name in (
            "summary.json",
            "per_pair_utility.jsonl",
            "per_parent_utility.jsonl",
            "per_task.csv",
        )
    }
    (output / "artifact_manifest.json").write_bytes(pretty_json(manifest))


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("protocol")
    parser.add_argument("cards")
    parser.add_argument("tfidf_per_pair")
    parser.add_argument("tfidf_summary")
    parser.add_argument("cost_summary")
    parser.add_argument("output")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    try:
        summary, pair_rows, parent_rows = analyze(
            args.protocol,
            args.cards,
            args.tfidf_per_pair,
            args.tfidf_summary,
            args.cost_summary,
        )
        write_outputs(args.output, summary, pair_rows, parent_rows)
    except (AuditError, OSError, ValueError) as exc:
        print(f"TFIDF_UTILITY_AUDIT_FAIL type={type(exc).__name__}", file=os.sys.stderr)
        return 2
    print(
        "TFIDF_UTILITY_AUDIT_COMPLETE "
        f"status={summary['status']} "
        f"test_tasks={summary['metrics']['test']['merged']['tasks']} "
        f"test_parents={summary['metrics']['test']['merged']['parents']}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
