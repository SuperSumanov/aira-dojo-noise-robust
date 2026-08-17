#!/usr/bin/env python3
"""Outcome-blind, names-stripped LOTO contract retrieval support audit."""
from __future__ import annotations

import argparse
import collections
import hashlib
import json
import math
import os
import random
import statistics
import sys
from pathlib import Path
from typing import Any


PROTOCOL = "contract-loto-retrieval-support-v1"
TYPE_NAMES = ("bool", "empty", "float", "int", "nonfinite", "no_rows", "string")
AUDIT_SHA = "166eaa6770b4abd6118f0168abc2b6e8afb5633847af48628f3f637ad9b56bdb"
MEMORY_SHA = "769acc3d198dadb5643e3557f57c738967806546e212c258d0de51ad794a53f0"
SEED = 20260817
PERMUTATIONS = 100_000


class RetrievalError(RuntimeError):
    pass


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()


def load_locked(path: Path, expected_sha: str) -> dict[str, Any]:
    if not path.is_file() or sha256_file(path) != expected_sha:
        raise RetrievalError(f"locked input mismatch: {path}")
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise RetrievalError(f"invalid locked JSON: {path}") from exc
    if not isinstance(value, dict):
        raise RetrievalError("locked input must be an object")
    return value


def fingerprint(row: dict[str, Any]) -> tuple[float, ...]:
    """Use structure and placeholder types only; never task/column names or outcomes."""
    column_count = row.get("column_count")
    row_count = row.get("row_count")
    observed = row.get("observed_types")
    empty_counts = row.get("empty_value_counts")
    if (
        not isinstance(column_count, int)
        or isinstance(column_count, bool)
        or column_count < 1
        or not isinstance(row_count, int)
        or isinstance(row_count, bool)
        or row_count < 0
        or not isinstance(observed, list)
        or len(observed) != column_count
        or not isinstance(empty_counts, list)
        or len(empty_counts) != column_count
    ):
        raise RetrievalError("invalid public contract structure")
    type_shares = []
    for type_name in TYPE_NAMES:
        count = 0
        for values in observed:
            if not isinstance(values, list) or any(not isinstance(item, str) for item in values):
                raise RetrievalError("invalid observed type list")
            count += type_name in values
        type_shares.append(count / column_count)
    if any(not isinstance(value, int) or isinstance(value, bool) or value < 0 for value in empty_counts):
        raise RetrievalError("invalid empty-value counts")
    denominator = row_count * column_count
    empty_fraction = sum(empty_counts) / denominator if denominator else 0.0
    return (
        math.log1p(row_count),
        math.log1p(column_count),
        *type_shares,
        empty_fraction,
    )


def scaled_distance(query: tuple[float, ...], candidate: tuple[float, ...], training: list[tuple[float, ...]]) -> float:
    contributions = []
    for index, (left, right) in enumerate(zip(query, candidate, strict=True)):
        values = [item[index] for item in training]
        lower, upper = min(values), max(values)
        if upper == lower:
            contributions.append(0.0 if left == right else 1.0)
            continue
        scaled_left = min(1.0, max(0.0, (left - lower) / (upper - lower)))
        scaled_right = (right - lower) / (upper - lower)
        contributions.append(abs(scaled_left - scaled_right))
    return sum(contributions) / len(contributions)


def nearest_graph(tasks: list[dict[str, Any]]) -> list[list[int]]:
    features = [fingerprint(row) for row in tasks]
    graph: list[list[int]] = []
    for query_index, query in enumerate(features):
        candidates = [index for index in range(len(tasks)) if index != query_index]
        training = [features[index] for index in candidates]
        distances = {
            index: scaled_distance(query, features[index], training)
            for index in candidates
        }
        best = min(distances.values())
        graph.append([index for index in candidates if abs(distances[index] - best) <= 1e-12])
    return graph


def mean_type_credit(graph: list[list[int]], labels: list[str]) -> float:
    credits = []
    for query, neighbors in enumerate(graph):
        credits.append(sum(labels[index] == labels[query] for index in neighbors) / len(neighbors))
    return statistics.fmean(credits)


def permutation_test(graph: list[list[int]], labels: list[str]) -> dict[str, Any]:
    observed = mean_type_credit(graph, labels)
    rng = random.Random(SEED)
    values = []
    working = list(labels)
    exceed = 0
    for _ in range(PERMUTATIONS):
        rng.shuffle(working)
        value = mean_type_credit(graph, working)
        values.append(value)
        exceed += value >= observed - 1e-15
    values.sort()
    return {
        "seed": SEED,
        "permutations": PERMUTATIONS,
        "observed_mean_same_type_credit": observed,
        "null_mean": statistics.fmean(values),
        "null_q95": values[int(0.95 * (len(values) - 1))],
        "one_sided_p": (exceed + 1) / (PERMUTATIONS + 1),
    }


def run(contract_path: Path, memory_path: Path) -> dict[str, Any]:
    contract = load_locked(contract_path, AUDIT_SHA)
    memory = load_locked(memory_path, MEMORY_SHA)
    all_rows = contract.get("tasks")
    if not isinstance(all_rows, list) or len(all_rows) != 25:
        raise RetrievalError("expected the locked 25-task contract universe")
    supported = [row for row in all_rows if row.get("contract_present") is True]
    abstained = [row for row in all_rows if row.get("contract_present") is not True]
    if len(supported) != 20 or len(abstained) != 5:
        raise RetrievalError("locked support/abstention counts changed")
    for row in supported:
        if not isinstance(row.get("task"), str) or row.get("task_type") not in {"image-cls", "nlp", "tabular"}:
            raise RetrievalError("invalid supported task identity metadata")

    graph = nearest_graph(supported)
    labels = [row["task_type"] for row in supported]
    if collections.Counter(labels) != {"image-cls": 7, "nlp": 9, "tabular": 4}:
        raise RetrievalError("locked 7/9/4 task-type distribution changed")
    permutation = permutation_test(graph, labels)
    writer_counts = memory.get("per_task_writer_marked_best_episodes")
    if not isinstance(writer_counts, dict):
        raise RetrievalError("writer-marked memory counts missing")

    per_query = []
    selection_mass: collections.Counter[str] = collections.Counter()
    type_credits: dict[str, list[float]] = collections.defaultdict(list)
    queries_with_five = 0
    for query_index, neighbors in enumerate(graph):
        query = supported[query_index]
        credit = sum(labels[index] == labels[query_index] for index in neighbors) / len(neighbors)
        type_credits[labels[query_index]].append(credit)
        names = [supported[index]["task"] for index in neighbors]
        if any(not isinstance(writer_counts.get(name, 0), int) for name in names):
            raise RetrievalError("invalid writer-marked episode count")
        episode_count = sum(writer_counts.get(name, 0) for name in names)
        queries_with_five += episode_count >= 5
        mass = 1.0 / len(names)
        for name in names:
            selection_mass[name] += mass
        per_query.append(
            {
                "query_task": query["task"],
                "query_task_type": query["task_type"],
                "nearest_tasks": sorted(names),
                "nearest_tie_count": len(names),
                "same_type_credit": credit,
                "writer_marked_best_episodes_available": episode_count,
            }
        )

    per_type = {key: statistics.fmean(value) for key, value in sorted(type_credits.items())}
    max_mass_share = max(selection_mass.values(), default=0.0) / len(supported)
    criteria = {
        "supported_queries_eq_20": len(supported) == 20,
        "unsupported_abstentions_eq_5": len(abstained) == 5,
        "mean_same_type_credit_ge_0_55": permutation["observed_mean_same_type_credit"] >= 0.55,
        "permutation_p_le_0_05": permutation["one_sided_p"] <= 0.05,
        "at_least_two_task_types_credit_ge_0_50": sum(value >= 0.50 for value in per_type.values()) >= 2,
        "distinct_retrieved_tasks_ge_5": len(selection_mass) >= 5,
        "max_retrieved_task_mass_share_le_0_25": max_mass_share <= 0.25,
        "queries_with_at_least_5_episodes_ge_0_90": queries_with_five / len(supported) >= 0.90,
    }
    passed = all(criteria.values())
    return {
        "protocol": PROTOCOL,
        "status": "VERIFIED_TASK_HELDOUT_RETRIEVAL_SUPPORT" if passed else "INSUFFICIENT_TASK_HELDOUT_RETRIEVAL_SUPPORT",
        "input_contract": {
            "contract_audit_sha256": AUDIT_SHA,
            "experience_memory_audit_sha256": MEMORY_SHA,
            "official_or_prospective_outcomes_read": False,
            "score_magnitudes_read": False,
            "code_read": False,
            "task_names_used_as_features": False,
            "column_names_used_as_features": False,
            "descriptions_used_as_features": False,
            "task_type_used_as_feature": False,
            "task_type_used_only_as_evaluation_label": True,
        },
        "fingerprint": {
            "features": ["log1p_row_count", "log1p_column_count", *[f"column_share_{name}" for name in TYPE_NAMES], "empty_cell_fraction"],
            "distance": "leave-one-task-out train-range-scaled mean absolute distance",
            "ties": "all exact nearest ties receive equal credit and retrieval mass",
        },
        "supported_queries": len(supported),
        "unsupported_abstentions": len(abstained),
        "abstained_tasks": sorted(row["task"] for row in abstained),
        "permutation_test": permutation,
        "per_task_type_same_type_credit": per_type,
        "retrieval_diversity": {
            "distinct_retrieved_tasks": len(selection_mass),
            "max_retrieved_task_mass_share": max_mass_share,
            "retrieved_task_mass": dict(sorted(selection_mass.items())),
        },
        "memory_availability": {
            "queries_with_at_least_5_writer_marked_best_episodes": queries_with_five,
            "query_share_with_at_least_5_writer_marked_best_episodes": queries_with_five / len(supported),
        },
        "criteria": criteria,
        "task_heldout_retrieval_support_claim_allowed": passed,
        "method_effect_claim_allowed": False,
        "paid_experiment_authorized": False,
        "per_query": per_query,
    }


def write_atomic(path: Path, value: dict[str, Any]) -> None:
    if path.exists():
        raise RetrievalError("output already exists")
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(path.name + f".tmp-{os.getpid()}")
    temporary.write_text(
        json.dumps(value, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
        newline="\n",
    )
    temporary.replace(path)


def parser() -> argparse.ArgumentParser:
    value = argparse.ArgumentParser()
    value.add_argument("--contract-audit", required=True)
    value.add_argument("--memory-audit", required=True)
    value.add_argument("--output", required=True)
    return value


def main() -> int:
    try:
        args = parser().parse_args()
        result = run(Path(args.contract_audit), Path(args.memory_audit))
        write_atomic(Path(args.output).resolve(), result)
        print(json.dumps({key: result[key] for key in ("protocol", "status", "criteria")}, sort_keys=True))
        return 0
    except (RetrievalError, OSError) as exc:
        print(f"CONTRACT_LOTO_RETRIEVAL_ERROR: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
