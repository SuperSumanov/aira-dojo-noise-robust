#!/usr/bin/env python3
"""Independently audit metric-field availability for the historical API panel.

This verifier does not import the panel builder.  It emits aggregate schema counts
only and never reads code, labels, observations, predictions, or prospective data.
"""

from __future__ import annotations

import argparse
from collections import Counter, defaultdict
import hashlib
import json
from pathlib import Path
from typing import Any

from phase1.audit_senior_0819_pair_benchmark_integrity import JsonObjectStream


class MetricAuditError(RuntimeError):
    pass


def require(condition: bool, message: str) -> None:
    if not condition:
        raise MetricAuditError(message)


def sha256(path: Path) -> str:
    require(path.is_file() and not path.is_symlink(), f"unsafe file: {path}")
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(8 << 20), b""):
            digest.update(block)
    return digest.hexdigest()


def read_test_pairs(
    path: Path, expected_rows: int, expected_test_rows: int
) -> tuple[list[tuple[str, str]], dict[str, int]]:
    rows = 0
    splits: Counter[str] = Counter()
    test_pairs: list[tuple[str, str]] = []
    with path.open(encoding="utf-8") as handle:
        for number, line in enumerate(handle, 1):
            require(bool(line.strip()), f"blank pair row: {number}")
            value = json.loads(line)
            require(isinstance(value, dict), f"pair object: {number}")
            split = value.get("intask_split")
            require(split in {"train", "test"}, f"pair split: {number}")
            better, worse = value.get("better"), value.get("worse")
            require(
                isinstance(better, str)
                and better
                and isinstance(worse, str)
                and worse
                and better != worse,
                f"pair endpoints: {number}",
            )
            rows += 1
            splits[split] += 1
            if split == "test":
                test_pairs.append((better, worse))
    require(rows == expected_rows, "pair row count")
    require(len(test_pairs) == expected_test_rows, "test row count")
    return test_pairs, dict(splits)


def consensus_status(values: set[str]) -> str:
    if not values:
        return "missing"
    if len(values) == 1:
        return "unique"
    return "ambiguous"


def audit(args: argparse.Namespace) -> dict[str, Any]:
    protocol_path = args.protocol.resolve()
    require(sha256(protocol_path) == args.protocol_sha256, "protocol SHA mismatch")
    protocol = json.loads(protocol_path.read_text(encoding="utf-8"))
    require(protocol.get("protocol") == "openrouter-full-context-judge-v1", "protocol")
    paths = {
        "cards": args.cards.resolve(),
        "run_split": args.run_split.resolve(),
        "decision": args.decision.resolve(),
        "value_hardware_time": args.value_hardware_time.resolve(),
    }
    observed = {}
    for role, path in paths.items():
        binding = protocol["immutable_inputs"][role]
        observed[role] = sha256(path)
        require(observed[role] == binding["sha256"], f"input SHA: {role}")
        require(path.stat().st_size == binding["bytes"], f"input size: {role}")

    run_split = json.loads(paths["run_split"].read_text(encoding="utf-8"))
    require(isinstance(run_split, dict) and set(run_split) == {"all", "hold"}, "run split")
    all_runs = set(run_split["all"])
    held_runs = set(run_split["hold"])
    require(len(all_runs) == protocol["immutable_inputs"]["run_split"]["all_runs"], "all runs")
    require(len(held_runs) == protocol["immutable_inputs"]["run_split"]["held_runs"], "held runs")
    require(held_runs <= all_runs, "held run subset")

    pair_rows = {}
    split_counts = {}
    for role in ("decision", "value_hardware_time"):
        binding = protocol["immutable_inputs"][role]
        pair_rows[role], split_counts[role] = read_test_pairs(
            paths[role], binding["rows"], binding["test_rows"]
        )
    endpoint_ids = {
        identity
        for pairs in pair_rows.values()
        for pair in pairs
        for identity in pair
    }

    seen_cards: set[str] = set()
    endpoint_meta: dict[str, tuple[str, str, bool]] = {}
    run_task_metrics: dict[tuple[str, str], set[str]] = defaultdict(set)
    cards_with_metric = 0
    run_count = 0
    stream = JsonObjectStream(paths["cards"])
    try:
        for run, rows in stream:
            require(run in all_runs, "Cards run outside split")
            require(isinstance(rows, list) and rows, "Cards run rows")
            run_count += 1
            for value in rows:
                require(isinstance(value, dict), "Card object")
                identity = value.get("id")
                task = value.get("task")
                require(
                    isinstance(identity, str) and identity and identity not in seen_cards,
                    "Card identity",
                )
                require(isinstance(task, dict), "Card task")
                task_name = task.get("name")
                metric = task.get("metric")
                require(isinstance(task_name, str) and task_name, "Card task name")
                seen_cards.add(identity)
                has_metric = isinstance(metric, str) and bool(metric)
                cards_with_metric += int(has_metric)
                if has_metric:
                    run_task_metrics[(run, task_name)].add(metric)
                if identity in endpoint_ids:
                    endpoint_meta[identity] = (run, task_name, has_metric)
    finally:
        stream.close()
    require(run_count == len(all_runs), "Cards run coverage")
    require(set(endpoint_meta) == endpoint_ids, "endpoint Card coverage")

    endpoint_keys = {(run, task) for run, task, _ in endpoint_meta.values()}
    key_status = Counter(consensus_status(run_task_metrics.get(key, set())) for key in endpoint_keys)
    endpoint_status = Counter(
        consensus_status(run_task_metrics.get((run, task), set()))
        for run, task, _ in endpoint_meta.values()
    )
    pair_status: dict[str, Counter[str]] = {}
    for role, pairs in pair_rows.items():
        values: Counter[str] = Counter()
        for first, second in pairs:
            first_meta, second_meta = endpoint_meta[first], endpoint_meta[second]
            require(first_meta[:2] == second_meta[:2], f"pair run-task mismatch: {role}")
            values[consensus_status(run_task_metrics.get(first_meta[:2], set()))] += 1
        pair_status[role] = values

    return {
        "protocol": "openrouter-full-context-metric-availability-audit-v1",
        "status": "HISTORICAL_METRIC_AVAILABILITY_AUDIT_COMPLETE",
        "protocol_sha256": args.protocol_sha256,
        "input_sha256": observed,
        "input_split_counts": split_counts,
        "inventory": {
            "physical_runs": run_count,
            "cards": len(seen_cards),
            "cards_with_nonempty_metric": cards_with_metric,
            "all_run_task_keys_with_nonempty_metric": len(run_task_metrics),
            "historical_test_endpoint_cards": len(endpoint_ids),
            "endpoint_cards_with_nonempty_metric": sum(value[2] for value in endpoint_meta.values()),
            "referenced_run_task_keys": len(endpoint_keys),
        },
        "referenced_run_task_consensus_status": dict(sorted(key_status.items())),
        "endpoint_consensus_status": dict(sorted(endpoint_status.items())),
        "pair_consensus_status": {
            role: dict(sorted(values.items())) for role, values in sorted(pair_status.items())
        },
        "security": {
            "identities_emitted": False,
            "code_labels_observations_predictions_read": False,
            "prospective_values_read": False,
            "api_calls": 0,
        },
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--protocol", type=Path, required=True)
    parser.add_argument("--protocol-sha256", required=True)
    parser.add_argument("--cards", type=Path, required=True)
    parser.add_argument("--run-split", type=Path, required=True)
    parser.add_argument("--decision", type=Path, required=True)
    parser.add_argument("--value-hardware-time", type=Path, required=True)
    return parser.parse_args()


def main() -> None:
    print(json.dumps(audit(parse_args()), ensure_ascii=True, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
