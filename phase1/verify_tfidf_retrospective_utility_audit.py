#!/usr/bin/env python3
"""Independently verify the retrospective TF-IDF utility audit artifacts."""
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
from typing import Any

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
OUTPUTS = (
    "summary.json",
    "per_pair_utility.jsonl",
    "per_parent_utility.jsonl",
    "per_task.csv",
)
SUBSETS = ("merged", "Draft", "Improve")


class VerificationError(RuntimeError):
    """Raised when an independently recomputed invariant differs."""


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1 << 20), b""):
            digest.update(block)
    return digest.hexdigest()


def canonical(value: Any) -> str:
    return json.dumps(
        value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False
    )


def read_object(path: Path, label: str) -> dict[str, Any]:
    if path.is_symlink() or not path.is_file():
        raise VerificationError(f"{label} is absent, symlinked, or non-regular")
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise VerificationError(f"invalid {label} JSON") from exc
    if not isinstance(value, dict):
        raise VerificationError(f"{label} must be an object")
    return value


def checked(path_value: str | Path, identity: dict[str, Any], label: str) -> Path:
    path = Path(path_value)
    if (
        path.is_symlink()
        or not path.is_file()
        or path.stat().st_size != identity.get("bytes")
        or sha256_file(path) != identity.get("sha256")
    ):
        raise VerificationError(f"{label} identity mismatch")
    return path.resolve()


def jsonl(path: Path, label: str) -> list[dict[str, Any]]:
    rows = []
    with path.open(encoding="utf-8") as handle:
        for number, line in enumerate(handle, 1):
            if not line.strip():
                raise VerificationError(f"blank {label} row {number}")
            value = json.loads(line)
            if not isinstance(value, dict):
                raise VerificationError(f"invalid {label} row {number}")
            rows.append(value)
    if not rows:
        raise VerificationError(f"empty {label}")
    return rows


def verify_artifact_manifest(output: Path) -> dict[str, Path]:
    if output.is_symlink() or not output.is_dir():
        raise VerificationError("output root is absent, symlinked, or non-directory")
    observed_names = {entry.name for entry in output.iterdir()}
    if observed_names != {*OUTPUTS, "artifact_manifest.json"}:
        raise VerificationError("producer output file set mismatch")
    manifest_path = output / "artifact_manifest.json"
    manifest = read_object(manifest_path, "artifact manifest")
    if set(manifest) != set(OUTPUTS):
        raise VerificationError("artifact manifest schema mismatch")
    paths = {name: output / name for name in OUTPUTS}
    for name, path in paths.items():
        if path.is_symlink() or not path.is_file() or sha256_file(path) != manifest[name]:
            raise VerificationError(f"artifact hash mismatch: {name}")
    return paths


def load_source_pairs(path: Path) -> list[dict[str, Any]]:
    rows = jsonl(path, "source pair")
    keys = set()
    indices: dict[str, list[int]] = defaultdict(list)
    for row in rows:
        if set(row) != PAIR_FIELDS:
            raise VerificationError("source pair schema mismatch")
        if (
            row["split"] not in {"dev", "test"}
            or row["semantics"] not in {"Draft", "Improve"}
            or isinstance(row["margin"], bool)
            or not isinstance(row["margin"], (int, float))
            or not math.isfinite(float(row["margin"]))
            or row["margin"] == 0
            or not isinstance(row["correct"], bool)
            or row["correct"] is not (row["margin"] > 0)
            or row["tie"] is not False
            or isinstance(row["index"], bool)
            or not isinstance(row["index"], int)
        ):
            raise VerificationError("source pair semantic invariant failed")
        string_fields = (
            "task",
            "parent",
            "better",
            "worse",
            "better_run",
            "worse_run",
        )
        if not all(isinstance(row[field], str) and row[field] for field in string_fields):
            raise VerificationError("source pair string identity invalid")
        if row["better"] == row["worse"]:
            raise VerificationError("source self-pair")
        key = (
            row["split"],
            row["task"],
            row["parent"],
            *sorted((row["better"], row["worse"])),
        )
        if key in keys:
            raise VerificationError("duplicate source unordered pair")
        keys.add(key)
        indices[row["split"]].append(row["index"])
    for split, values in indices.items():
        if values != list(range(len(values))):
            raise VerificationError(f"{split} source indices are not contiguous")
    return rows


def validate_tfidf_summary(
    summary: dict[str, Any], source: list[dict[str, Any]]
) -> None:
    if (
        summary.get("protocol") != "critic-component-char-tfidf-baseline-v1"
        or summary.get("status") != "BASELINE_VALID"
        or summary.get("model", {}).get("anti_symmetry_max_abs") != 0.0
    ):
        raise VerificationError("TF-IDF source summary invariant failed")
    metrics = summary.get("metrics")
    if not isinstance(metrics, dict):
        raise VerificationError("TF-IDF source metrics missing")
    for split in ("dev", "test"):
        selected = [row for row in source if row["split"] == split]
        expected = metrics.get(split, {}).get("merged", {})
        observed = float(np.mean([row["correct"] for row in selected]))
        if (
            expected.get("pairs") != len(selected)
            or abs(expected.get("micro_accuracy", -1.0) - observed) > 1e-15
        ):
            raise VerificationError("TF-IDF summary/per-pair mismatch")


def validate_cost_summary(cost: dict[str, Any], protocol: dict[str, Any]) -> None:
    contract = protocol["cost_contract"]
    model = cost.get("models", {}).get(contract["model"])
    scope = cost.get("scope")
    if (
        cost.get("protocol") != "deployment_cost_attestation_v2"
        or cost.get("status") != "DEPLOYMENT_COST_ADVANTAGE_SUPPORTED"
        or not isinstance(model, dict)
        or not isinstance(scope, dict)
        or scope.get("accuracy_computed") is not False
        or scope.get("prospective_vault_opened") is not False
        or scope.get("gpu_used") is not False
        or scope.get("api_used") is not False
    ):
        raise VerificationError("cost source summary invariant failed")
    query_fraction = model.get("query_p95_fraction_of_execution_parallel_p50")
    break_even = model.get("initialization_break_even_parallel_pairs")
    if (
        isinstance(query_fraction, bool)
        or not isinstance(query_fraction, (int, float))
        or not math.isfinite(float(query_fraction))
        or isinstance(break_even, bool)
        or not isinstance(break_even, int)
        or query_fraction
        >= contract["require_query_p95_fraction_of_execution_parallel_p50_below"]
        or break_even
        > contract["require_initialization_break_even_parallel_pairs_at_most"]
    ):
        raise VerificationError("cost source positive gate failed")


def load_truth(path: Path, needed: set[str]) -> tuple[dict[str, dict[str, Any]], dict[str, int]]:
    grouped = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(grouped, dict):
        raise VerificationError("Cards root is not grouped")
    truth = {}
    seen = set()
    total = 0
    for run_id, cards in grouped.items():
        if not isinstance(run_id, str) or not isinstance(cards, list):
            raise VerificationError("invalid Cards run group")
        for card in cards:
            total += 1
            if not isinstance(card, dict) or not isinstance(card.get("id"), str):
                raise VerificationError("invalid Card")
            card_id = card["id"]
            if card_id in seen:
                raise VerificationError("duplicate Card id")
            seen.add(card_id)
            if card_id not in needed:
                continue
            task, label = card.get("task"), card.get("label")
            if (
                not isinstance(task, dict)
                or not isinstance(task.get("name"), str)
                or not isinstance(task.get("higher_is_better"), bool)
                or not isinstance(label, dict)
                or isinstance(label.get("graded"), bool)
                or not isinstance(label.get("graded"), (int, float))
                or not math.isfinite(float(label["graded"]))
            ):
                raise VerificationError("needed Card truth invalid")
            grade = float(label["graded"])
            truth[card_id] = {
                "task": task["name"],
                "utility": grade if task["higher_is_better"] else -grade,
            }
    if set(truth) != needed:
        raise VerificationError("missing Cards endpoint truth")
    return truth, {"cards": total, "run_groups": len(grouped), "needed_cards": len(needed)}


def expected_pair_rows(
    source: list[dict[str, Any]], truth: dict[str, dict[str, Any]], grade_tolerance: float
) -> list[dict[str, Any]]:
    rows = []
    for row in source:
        better, worse = truth[row["better"]], truth[row["worse"]]
        if better["task"] != row["task"] or worse["task"] != row["task"]:
            raise VerificationError("pair/Card task mismatch")
        gap = better["utility"] - worse["utility"]
        if gap <= grade_tolerance:
            raise VerificationError("raw-grade orientation mismatch")
        rows.append(
            {
                "split": row["split"],
                "index": row["index"],
                "task": row["task"],
                "parent": row["parent"],
                "semantics": row["semantics"],
                "better": row["better"],
                "worse": row["worse"],
                "margin": float(row["margin"]),
                "correct": row["correct"],
                "oriented_raw_gap": float(gap),
                "selected_regret": 0.0 if row["correct"] else float(gap),
            }
        )
    return rows


def solve_parent(
    rows: list[dict[str, Any]],
    truth: dict[str, dict[str, Any]],
    tolerance: dict[str, float],
) -> dict[str, Any]:
    adjacency: dict[str, list[tuple[str, float]]] = defaultdict(list)
    endpoints = set()
    for row in rows:
        better, worse, margin = row["better"], row["worse"], row["margin"]
        endpoints.update((better, worse))
        adjacency[better].append((worse, -margin))
        adjacency[worse].append((better, margin))
    root = min(endpoints)
    potential = {root: 0.0}
    queue: deque[str] = deque([root])
    residual = 0.0
    while queue:
        current = queue.popleft()
        for neighbor, delta in adjacency[current]:
            proposed = potential[current] + delta
            if neighbor not in potential:
                potential[neighbor] = proposed
                queue.append(neighbor)
            else:
                residual = max(residual, abs(potential[neighbor] - proposed))
    if set(potential) != endpoints or residual > tolerance["margin_consistency"]:
        raise VerificationError("parent margin graph failed")
    top = max(potential.values())
    predicted = [
        endpoint
        for endpoint, value in potential.items()
        if abs(value - top) <= tolerance["prediction_tie"]
    ]
    if len(predicted) != 1:
        raise VerificationError("parent predicted winner tie")
    utilities = {endpoint: truth[endpoint]["utility"] for endpoint in endpoints}
    oracle = max(utilities.values())
    random_mean = float(np.mean(list(utilities.values())))
    denominator = oracle - random_mean
    if denominator <= tolerance["grade"]:
        raise VerificationError("parent utility denominator invalid")
    selected = utilities[predicted[0]]
    regret = oracle - selected
    return {
        "candidates": len(endpoints),
        "edges": len(rows),
        "max_margin_residual": residual,
        "predicted": predicted[0],
        "top1_exact": regret <= tolerance["grade"],
        "oracle_minus_random": float(denominator),
        "selected_minus_random": float(selected - random_mean),
        "regret": float(max(0.0, regret)),
    }


def expected_parent_rows(
    source: list[dict[str, Any]],
    truth: dict[str, dict[str, Any]],
    tolerance: dict[str, float],
) -> list[dict[str, Any]]:
    grouped: dict[tuple[str, str, str, str], list[dict[str, Any]]] = defaultdict(list)
    for row in source:
        grouped[(row["split"], row["task"], row["parent"], row["semantics"])].append(row)
    return [
        {
            "split": split,
            "task": task,
            "parent": parent,
            "semantics": semantics,
            **solve_parent(rows, truth, tolerance),
        }
        for (split, task, parent, semantics), rows in sorted(grouped.items())
    ]


def boot(
    values: dict[str, float], metric: str, base_seed: int, replicates: int
) -> dict[str, Any]:
    tasks = sorted(values)
    data = np.asarray([values[task] for task in tasks], dtype=np.float64)
    seed = int((base_seed + zlib.crc32(metric.encode("utf-8"))) % (2**32))
    rng = np.random.default_rng(seed)
    sampled = rng.integers(0, len(data), size=(replicates, len(data)))
    estimates = np.mean(data[sampled], axis=1)
    low, high = np.quantile(estimates, [0.025, 0.975], method="linear")
    return {
        "point": float(np.mean(data)),
        "ci95": [float(low), float(high)],
        "tasks": len(data),
        "replicates": replicates,
        "seed": seed,
        "task_values": dict(sorted(values.items())),
    }


def one_metric_block(
    split: str,
    subset: str,
    pairs: list[dict[str, Any]],
    parents: list[dict[str, Any]],
    bootstrap: dict[str, Any],
) -> dict[str, Any]:
    selected_pairs = [
        row
        for row in pairs
        if row["split"] == split and (subset == "merged" or row["semantics"] == subset)
    ]
    selected_parents = [
        row
        for row in parents
        if row["split"] == split and (subset == "merged" or row["semantics"] == subset)
    ]
    tasks = sorted({row["task"] for row in selected_pairs})
    if set(tasks) != {row["task"] for row in selected_parents}:
        raise VerificationError("pair/parent task support mismatch")
    unweighted, weighted, capture, top1, regret = {}, {}, {}, {}, {}
    for task in tasks:
        task_pairs = [row for row in selected_pairs if row["task"] == task]
        task_parents = [row for row in selected_parents if row["task"] == task]
        gap = sum(row["oriented_raw_gap"] for row in task_pairs)
        denominator = sum(row["oracle_minus_random"] for row in task_parents)
        unweighted[task] = float(np.mean([row["correct"] for row in task_pairs]))
        weighted[task] = float(
            sum(row["oriented_raw_gap"] for row in task_pairs if row["correct"]) / gap
        )
        capture[task] = float(
            sum(row["selected_minus_random"] for row in task_parents) / denominator
        )
        top1[task] = float(np.mean([row["top1_exact"] for row in task_parents]))
        regret[task] = float(sum(row["regret"] for row in task_parents) / denominator)
    difference = {task: weighted[task] - unweighted[task] for task in tasks}
    prefix = f"{split}.{subset}"
    weighted_receipt = boot(
        weighted,
        prefix + ".pair_gap_weighted_accuracy",
        bootstrap["task_seed"],
        bootstrap["replicates"],
    )
    return {
        "pairs": len(selected_pairs),
        "parents": len(selected_parents),
        "tasks": len(tasks),
        "dominant_parent_task_share": max(
            Counter(row["task"] for row in selected_parents).values()
        )
        / len(selected_parents),
        "pair_unweighted_accuracy": boot(
            unweighted,
            prefix + ".pair_unweighted_accuracy",
            bootstrap["task_seed"],
            bootstrap["replicates"],
        ),
        "pair_gap_weighted_accuracy": weighted_receipt,
        "pair_gap_capture": {
            "point": 2 * weighted_receipt["point"] - 1,
            "ci95": [
                2 * weighted_receipt["ci95"][0] - 1,
                2 * weighted_receipt["ci95"][1] - 1,
            ],
        },
        "pair_gap_weighted_minus_unweighted": boot(
            difference,
            prefix + ".pair_gap_weighted_minus_unweighted",
            bootstrap["task_seed"],
            bootstrap["replicates"],
        ),
        "parent_gain_capture": boot(
            capture,
            prefix + ".parent_gain_capture",
            bootstrap["task_seed"],
            bootstrap["replicates"],
        ),
        "parent_top1_accuracy": boot(
            top1,
            prefix + ".parent_top1_accuracy",
            bootstrap["task_seed"],
            bootstrap["replicates"],
        ),
        "parent_normalized_regret": boot(
            regret,
            prefix + ".parent_normalized_regret",
            bootstrap["task_seed"],
            bootstrap["replicates"],
        ),
    }


def extract_cost(cost: dict[str, Any], protocol: dict[str, Any]) -> dict[str, Any]:
    model = cost["models"][protocol["cost_contract"]["model"]]
    return {
        "initialization_p50_s": model["initialization_s"]["p50"],
        "initialization_break_even_parallel_pairs": model[
            "initialization_break_even_parallel_pairs"
        ],
        "pair_query_p50_ms": model["single_pair_query_ms"]["p50"],
        "pair_query_p95_ms": model["single_pair_query_ms"]["p95"],
        "execution_parallel_p50_over_query_p50": model[
            "execution_parallel_p50_over_query_p50"
        ],
        "query_p95_fraction_of_execution_parallel_p50": model[
            "query_p95_fraction_of_execution_parallel_p50"
        ],
        "execution_parallel_p50_s": cost["runtime_reference"][
            "pair_ideal_parallel_runtime_s"
        ]["p50"],
    }


def verify_task_csv(path: Path, metrics: dict[str, Any]) -> int:
    expected = []
    for split in ("dev", "test"):
        for subset in SUBSETS:
            block = metrics[split][subset]
            for task in sorted(block["pair_unweighted_accuracy"]["task_values"]):
                expected.append(
                    {
                        "split": split,
                        "subset": subset,
                        "task": task,
                        "pair_unweighted_accuracy": str(
                            block["pair_unweighted_accuracy"]["task_values"][task]
                        ),
                        "pair_gap_weighted_accuracy": str(
                            block["pair_gap_weighted_accuracy"]["task_values"][task]
                        ),
                        "parent_gain_capture": str(
                            block["parent_gain_capture"]["task_values"][task]
                        ),
                        "parent_top1_accuracy": str(
                            block["parent_top1_accuracy"]["task_values"][task]
                        ),
                        "parent_normalized_regret": str(
                            block["parent_normalized_regret"]["task_values"][task]
                        ),
                    }
                )
    with path.open(encoding="utf-8", newline="") as handle:
        observed = list(csv.DictReader(handle))
    if observed != expected:
        raise VerificationError("per-task CSV mismatch")
    return len(observed)


def verify(
    protocol_path_value: str | Path,
    cards_path_value: str | Path,
    source_pairs_value: str | Path,
    tfidf_summary_value: str | Path,
    cost_summary_value: str | Path,
    output_value: str | Path,
) -> dict[str, Any]:
    protocol_path = Path(protocol_path_value)
    protocol = read_object(protocol_path, "protocol")
    if (
        protocol.get("protocol") != PROTOCOL
        or protocol.get("status")
        != "FROZEN_BEFORE_GRADE_GAP_AND_PARENT_UTILITY_READ"
    ):
        raise VerificationError("protocol freeze mismatch")
    frozen = protocol.get("frozen_inputs")
    if not isinstance(frozen, dict) or set(frozen) != {
        "cards",
        "cost_summary",
        "tfidf_per_pair",
        "tfidf_summary",
    }:
        raise VerificationError("protocol frozen-input schema mismatch")
    bootstrap = protocol.get("bootstrap")
    if (
        not isinstance(bootstrap, dict)
        or isinstance(bootstrap.get("replicates"), bool)
        or not isinstance(bootstrap.get("replicates"), int)
        or bootstrap["replicates"] < 1000
        or isinstance(bootstrap.get("task_seed"), bool)
        or not isinstance(bootstrap.get("task_seed"), int)
    ):
        raise VerificationError("protocol bootstrap contract invalid")
    cards_path = checked(cards_path_value, frozen["cards"], "cards")
    source_path = checked(source_pairs_value, frozen["tfidf_per_pair"], "source pairs")
    tfidf_summary_path = checked(
        tfidf_summary_value, frozen["tfidf_summary"], "TF-IDF summary"
    )
    cost_path = checked(cost_summary_value, frozen["cost_summary"], "cost summary")
    output_path = Path(output_value)
    artifacts = verify_artifact_manifest(output_path)
    summary = read_object(artifacts["summary.json"], "summary")
    source = load_source_pairs(source_path)
    tfidf = read_object(tfidf_summary_path, "TF-IDF summary")
    validate_tfidf_summary(tfidf, source)
    cost = read_object(cost_path, "cost summary")
    validate_cost_summary(cost, protocol)
    needed = {row[key] for row in source for key in ("better", "worse")}
    truth, card_inventory = load_truth(cards_path, needed)
    expected_pairs = expected_pair_rows(source, truth, protocol["tolerances"]["grade"])
    observed_pairs = jsonl(artifacts["per_pair_utility.jsonl"], "utility pair")
    if observed_pairs != expected_pairs:
        raise VerificationError("per-pair utility rows differ")
    expected_parents = expected_parent_rows(source, truth, protocol["tolerances"])
    observed_parents = jsonl(artifacts["per_parent_utility.jsonl"], "utility parent")
    if observed_parents != expected_parents:
        raise VerificationError("per-parent utility rows differ")
    metrics = {
        split: {
            subset: one_metric_block(
                split, subset, expected_pairs, expected_parents, protocol["bootstrap"]
            )
            for subset in SUBSETS
        }
        for split in ("dev", "test")
    }
    if summary.get("metrics") != metrics:
        raise VerificationError("summary metrics differ from independent recomputation")
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
    expected_status = (
        "RETROSPECTIVE_COST_UTILITY_POSITIVE"
        if positive
        else "VALID_NO_STRONG_COST_UTILITY_POSITIVE"
    )
    if (
        summary.get("protocol") != PROTOCOL
        or summary.get("status") != expected_status
        or summary.get("evidence_level")
        != "retrospective_accuracy_touched_component_clean_test"
        or summary.get("protocol_sha256") != sha256_file(protocol_path)
        or summary.get("inputs") != frozen
        or summary.get("card_inventory") != card_inventory
        or summary.get("cost") != extract_cost(cost, protocol)
        or summary.get("primary_positive_gates") != gates
        or summary.get("primary_positive_gates_pass") is not positive
        or summary.get("claim_boundary") != protocol.get("claim_boundary")
        or summary.get("access_attestation")
        != {
            "future_or_prospective_vault_opened": False,
            "gpu_used": False,
            "api_used": False,
            "model_fit": False,
            "base_llm_updated": False,
        }
        or summary.get("pair_inventory")
        != {
            "rows": len(source),
            "dev": sum(row["split"] == "dev" for row in source),
            "test": sum(row["split"] == "test" for row in source),
            "needed_endpoints": len(needed),
        }
    ):
        raise VerificationError("summary metadata/gate mismatch")
    task_rows = verify_task_csv(artifacts["per_task.csv"], metrics)
    return {
        "protocol": "independent-tfidf-retrospective-utility-verifier-v1",
        "status": "TFIDF_RETROSPECTIVE_UTILITY_INDEPENDENTLY_VERIFIED",
        "producer_imported": False,
        "source_pairs": len(source),
        "utility_pairs": len(expected_pairs),
        "utility_parents": len(expected_parents),
        "task_csv_rows": task_rows,
        "primary_positive_gates_pass": positive,
        "summary_sha256": sha256_file(artifacts["summary.json"]),
        "artifact_manifest_sha256": sha256_file(
            output_path / "artifact_manifest.json"
        ),
        "future_or_prospective_vault_opened": False,
        "gpu_api_model_fit": [0, 0, 0],
    }


def write_receipt(path_value: str | Path, receipt: dict[str, Any]) -> None:
    path_input = Path(path_value)
    if path_input.is_symlink() or path_input.exists():
        raise VerificationError("verification output already exists or is symlinked")
    path = path_input.resolve()
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(path.name + f".tmp-{os.getpid()}")
    try:
        temporary.write_text(
            json.dumps(receipt, indent=2, sort_keys=True, allow_nan=False) + "\n",
            encoding="utf-8",
            newline="\n",
        )
        os.replace(temporary, path)
    finally:
        if temporary.exists():
            temporary.unlink()


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("protocol")
    parser.add_argument("cards")
    parser.add_argument("tfidf_per_pair")
    parser.add_argument("tfidf_summary")
    parser.add_argument("cost_summary")
    parser.add_argument("producer_output")
    parser.add_argument("verification_output")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    try:
        receipt = verify(
            args.protocol,
            args.cards,
            args.tfidf_per_pair,
            args.tfidf_summary,
            args.cost_summary,
            args.producer_output,
        )
        write_receipt(args.verification_output, receipt)
    except (VerificationError, OSError, ValueError, KeyError) as exc:
        print(f"TFIDF_UTILITY_VERIFY_FAIL type={type(exc).__name__}", file=os.sys.stderr)
        return 2
    print(
        "TFIDF_UTILITY_VERIFY_PASS "
        f"pairs={receipt['utility_pairs']} parents={receipt['utility_parents']} "
        f"positive={str(receipt['primary_positive_gates_pass']).lower()}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
