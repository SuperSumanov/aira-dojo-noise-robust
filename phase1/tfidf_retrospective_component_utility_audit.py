#!/usr/bin/env python3
"""Audit TF-IDF utility on structurally identifiable comparison components."""
from __future__ import annotations

import argparse
import csv
import hashlib
import json
import os
from collections import Counter, defaultdict, deque
from pathlib import Path
from typing import Any

import numpy as np

from phase1 import tfidf_retrospective_utility_audit as base


PROTOCOL = "tfidf-retrospective-component-utility-audit-v2"
STATUS = "FROZEN_AFTER_V1_STRUCTURAL_FAILURE_BEFORE_AGGREGATE_UTILITY_OBSERVATION"
SUBSETS = ("merged", "Draft", "Improve")


class ComponentAuditError(base.AuditError):
    """Raised when the V2 structural or utility contract fails closed."""


def load_protocol(path_value: str | Path) -> tuple[Path, dict[str, Any]]:
    path = Path(path_value)
    if path.is_symlink() or not path.is_file():
        raise ComponentAuditError("protocol is absent, symlinked, or non-regular")
    resolved = path.resolve()
    protocol = base.read_json(resolved, "V2 protocol")
    if protocol.get("protocol") != PROTOCOL or protocol.get("status") != STATUS:
        raise ComponentAuditError("V2 protocol freeze mismatch")
    frozen = protocol.get("frozen_inputs")
    if not isinstance(frozen, dict) or set(frozen) != {
        "cards",
        "cost_summary",
        "tfidf_per_pair",
        "tfidf_summary",
    }:
        raise ComponentAuditError("V2 frozen-input schema mismatch")
    bootstrap = protocol.get("bootstrap")
    if (
        not isinstance(bootstrap, dict)
        or isinstance(bootstrap.get("replicates"), bool)
        or not isinstance(bootstrap.get("replicates"), int)
        or bootstrap["replicates"] < 1000
        or isinstance(bootstrap.get("task_seed"), bool)
        or not isinstance(bootstrap.get("task_seed"), int)
    ):
        raise ComponentAuditError("V2 bootstrap contract invalid")
    if protocol.get("predecessor", {}).get("aggregate_utility_output_emitted") is not False:
        raise ComponentAuditError("V1 failure boundary is not frozen")
    return resolved, protocol


def connected_endpoint_sets(rows: list[dict[str, Any]]) -> list[tuple[str, ...]]:
    adjacency: dict[str, set[str]] = defaultdict(set)
    for row in rows:
        better, worse = row["better"], row["worse"]
        adjacency[better].add(worse)
        adjacency[worse].add(better)
    pending = set(adjacency)
    components = []
    while pending:
        root = min(pending)
        reached = {root}
        queue: deque[str] = deque([root])
        while queue:
            current = queue.popleft()
            for neighbor in sorted(adjacency[current]):
                if neighbor not in reached:
                    reached.add(neighbor)
                    queue.append(neighbor)
        pending -= reached
        components.append(tuple(sorted(reached)))
    return sorted(components, key=lambda values: values[0])


def component_identifier(
    split: str,
    task: str,
    parent: str,
    semantics: str,
    endpoints: tuple[str, ...],
) -> str:
    payload = {
        "split": split,
        "task": task,
        "parent": parent,
        "semantics": semantics,
        "endpoints_sorted": list(endpoints),
    }
    return hashlib.sha256(base.canonical_json(payload).encode("utf-8")).hexdigest()


def partition_components(
    pair_rows: list[dict[str, Any]],
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    grouped: dict[tuple[str, str, str, str], list[dict[str, Any]]] = defaultdict(list)
    parent_semantics: dict[tuple[str, str, str], set[str]] = defaultdict(set)
    for row in pair_rows:
        key = (row["split"], row["task"], row["parent"], row["semantics"])
        grouped[key].append(row)
        parent_semantics[key[:3]].add(row["semantics"])

    assignments: list[dict[str, Any]] = []
    group_records = []
    seen_pair_keys = set()
    for (split, task, parent, semantics), rows in sorted(grouped.items()):
        endpoint_sets = connected_endpoint_sets(rows)
        endpoint_to_ordinal = {
            endpoint: ordinal
            for ordinal, endpoints in enumerate(endpoint_sets)
            for endpoint in endpoints
        }
        component_rows: dict[int, list[dict[str, Any]]] = defaultdict(list)
        for row in rows:
            left = endpoint_to_ordinal[row["better"]]
            right = endpoint_to_ordinal[row["worse"]]
            if left != right:
                raise ComponentAuditError("edge crosses computed components")
            pair_key = (row["split"], row["index"])
            if pair_key in seen_pair_keys:
                raise ComponentAuditError("pair assigned more than once")
            seen_pair_keys.add(pair_key)
            component_rows[left].append(row)
        for ordinal, endpoints in enumerate(endpoint_sets):
            rows_for_component = component_rows[ordinal]
            if not rows_for_component:
                raise ComponentAuditError("empty computed component")
            assignments.append(
                {
                    "split": split,
                    "task": task,
                    "parent": parent,
                    "semantics": semantics,
                    "component_ordinal": ordinal,
                    "component_id": component_identifier(
                        split, task, parent, semantics, endpoints
                    ),
                    "endpoints": endpoints,
                    "rows": rows_for_component,
                }
            )
        group_records.append(
            {
                "split": split,
                "components": len(endpoint_sets),
                "pairs": len(rows),
            }
        )
    if len(seen_pair_keys) != len(pair_rows):
        raise ComponentAuditError("not every pair was assigned exactly once")

    structure: dict[str, Any] = {
        "parent_groups": len(group_records),
        "disconnected_parent_groups": sum(
            record["components"] > 1 for record in group_records
        ),
        "decision_components": len(assignments),
        "mixed_semantics_parent_groups": sum(
            len(values) > 1 for values in parent_semantics.values()
        ),
        "all_pairs_assigned_exactly_once": True,
    }
    for split in ("dev", "test"):
        selected = [record for record in group_records if record["split"] == split]
        structure[split] = {
            "pairs": sum(record["pairs"] for record in selected),
            "parent_groups": len(selected),
            "connected_parent_groups": sum(
                record["components"] == 1 for record in selected
            ),
            "disconnected_parent_groups": sum(
                record["components"] > 1 for record in selected
            ),
            "decision_components": sum(
                record["components"] for record in selected
            ),
        }
    return assignments, structure


def build_component_utility(
    assignments: list[dict[str, Any]],
    truth: dict[str, dict[str, Any]],
    tolerances: dict[str, float],
) -> list[dict[str, Any]]:
    output = []
    for assignment in assignments:
        result = base.parent_prediction(
            assignment["rows"],
            truth,
            margin_tolerance=tolerances["margin_consistency"],
            grade_tolerance=tolerances["grade"],
            tie_tolerance=tolerances["prediction_tie"],
        )
        if result["candidates"] != len(assignment["endpoints"]):
            raise ComponentAuditError("component candidate inventory mismatch")
        output.append(
            {
                "split": assignment["split"],
                "task": assignment["task"],
                "parent": assignment["parent"],
                "semantics": assignment["semantics"],
                "component_ordinal": assignment["component_ordinal"],
                "component_id": assignment["component_id"],
                **result,
            }
        )
    return output


def subset_metrics(
    split: str,
    subset: str,
    pair_rows: list[dict[str, Any]],
    component_rows: list[dict[str, Any]],
    *,
    base_seed: int,
    replicates: int,
) -> dict[str, Any]:
    pairs = [
        row
        for row in pair_rows
        if row["split"] == split and (subset == "merged" or row["semantics"] == subset)
    ]
    components = [
        row
        for row in component_rows
        if row["split"] == split and (subset == "merged" or row["semantics"] == subset)
    ]
    if not pairs or not components:
        raise ComponentAuditError("empty V2 split/subset")
    tasks = sorted({row["task"] for row in pairs})
    if set(tasks) != {row["task"] for row in components}:
        raise ComponentAuditError("pair/component task support differs")

    unweighted: dict[str, float] = {}
    weighted: dict[str, float] = {}
    capture: dict[str, float] = {}
    top1: dict[str, float] = {}
    regret: dict[str, float] = {}
    for task in tasks:
        task_pairs = [row for row in pairs if row["task"] == task]
        task_components = [row for row in components if row["task"] == task]
        gap_total = sum(row["oriented_raw_gap"] for row in task_pairs)
        correct_gap = sum(
            row["oriented_raw_gap"] for row in task_pairs if row["correct"]
        )
        denominator = sum(
            row["oracle_minus_random"] for row in task_components
        )
        selected_gain = sum(
            row["selected_minus_random"] for row in task_components
        )
        if gap_total <= 0 or denominator <= 0:
            raise ComponentAuditError("nonpositive V2 task denominator")
        unweighted[task] = float(np.mean([row["correct"] for row in task_pairs]))
        weighted[task] = float(correct_gap / gap_total)
        capture[task] = float(selected_gain / denominator)
        top1[task] = float(
            np.mean([row["top1_exact"] for row in task_components])
        )
        regret[task] = float(
            sum(row["regret"] for row in task_components) / denominator
        )
    difference = {task: weighted[task] - unweighted[task] for task in tasks}
    prefix = f"v2.{split}.{subset}"
    weighted_receipt = base.bootstrap_task_values(
        weighted,
        metric=prefix + ".pair_gap_weighted_accuracy",
        base_seed=base_seed,
        replicates=replicates,
    )
    return {
        "pairs": len(pairs),
        "decision_components": len(components),
        "parent_groups": len({(row["task"], row["parent"]) for row in components}),
        "tasks": len(tasks),
        "dominant_component_task_share": max(
            Counter(row["task"] for row in components).values()
        )
        / len(components),
        "pair_unweighted_accuracy": base.bootstrap_task_values(
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
        "pair_gap_weighted_minus_unweighted": base.bootstrap_task_values(
            difference,
            metric=prefix + ".pair_gap_weighted_minus_unweighted",
            base_seed=base_seed,
            replicates=replicates,
        ),
        "component_gain_capture": base.bootstrap_task_values(
            capture,
            metric=prefix + ".component_gain_capture",
            base_seed=base_seed,
            replicates=replicates,
        ),
        "component_top1_accuracy": base.bootstrap_task_values(
            top1,
            metric=prefix + ".component_top1_accuracy",
            base_seed=base_seed,
            replicates=replicates,
        ),
        "component_normalized_regret": base.bootstrap_task_values(
            regret,
            metric=prefix + ".component_normalized_regret",
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
    cards = base.checked_file(cards_path, frozen["cards"], "cards")
    pair_file = base.checked_file(pair_path, frozen["tfidf_per_pair"], "TF-IDF pairs")
    tfidf_summary_file = base.checked_file(
        tfidf_summary_path, frozen["tfidf_summary"], "TF-IDF summary"
    )
    cost_summary_file = base.checked_file(
        cost_summary_path, frozen["cost_summary"], "cost summary"
    )
    source_rows = base.load_pairs(pair_file)
    base.validate_tfidf_summary(
        base.read_json(tfidf_summary_file, "TF-IDF summary"), source_rows
    )
    cost = base.validate_cost_summary(
        base.read_json(cost_summary_file, "cost summary"), protocol
    )
    assignments, structure = partition_components(source_rows)
    if structure != protocol.get("expected_structure"):
        raise ComponentAuditError("V2 frozen structural receipt mismatch")
    needed = {row[field] for row in source_rows for field in ("better", "worse")}
    truth, card_inventory = base.load_card_truth(cards, needed)
    utility_pairs = base.build_pair_utility(
        source_rows, truth, protocol["tolerances"]["grade"]
    )
    utility_components = build_component_utility(
        assignments, truth, protocol["tolerances"]
    )
    bootstrap = protocol["bootstrap"]
    metrics = {
        split: {
            subset: subset_metrics(
                split,
                subset,
                utility_pairs,
                utility_components,
                base_seed=bootstrap["task_seed"],
                replicates=bootstrap["replicates"],
            )
            for subset in SUBSETS
        }
        for split in ("dev", "test")
    }
    test = metrics["test"]["merged"]
    contract = protocol["primary_positive_gates"]
    gates = {
        "integrity_and_cost_gates_pass": True,
        "test_tasks_at_least_20": test["tasks"] >= contract["test_tasks_at_least"],
        "test_decision_components_at_least_300": test["decision_components"]
        >= contract["test_decision_components_at_least"],
        "test_pair_gap_weighted_accuracy_task_ci_lower_gt_0_5": test[
            "pair_gap_weighted_accuracy"
        ]["ci95"][0]
        > contract["test_pair_gap_weighted_accuracy_task_cluster_ci95_lower_gt"],
        "test_component_gain_capture_task_ci_lower_gt_0": test[
            "component_gain_capture"
        ]["ci95"][0]
        > contract["test_component_gain_capture_task_cluster_ci95_lower_gt"],
    }
    positive = all(gates.values())
    summary = {
        "protocol": PROTOCOL,
        "status": (
            "RETROSPECTIVE_COMPONENT_COST_UTILITY_POSITIVE"
            if positive
            else "VALID_NO_STRONG_COMPONENT_COST_UTILITY_POSITIVE"
        ),
        "evidence_level": "retrospective_accuracy_touched_component_clean_test_after_structural_v1_invalid",
        "protocol_sha256": base.sha256_file(frozen_protocol_path),
        "inputs": frozen,
        "predecessor": protocol["predecessor"],
        "structure": structure,
        "card_inventory": card_inventory,
        "pair_inventory": {
            "rows": len(source_rows),
            "dev": sum(row["split"] == "dev" for row in source_rows),
            "test": sum(row["split"] == "test" for row in source_rows),
            "needed_endpoints": len(needed),
        },
        "cost": cost,
        "metrics": metrics,
        "primary_positive_gates": gates,
        "primary_positive_gates_pass": positive,
        "claim_boundary": protocol["claim_boundary"],
        "access_attestation": {
            "future_or_prospective_vault_opened": False,
            "historical_released_cards_opened": True,
            "gpu_used": False,
            "api_used": False,
            "model_fit": False,
            "base_llm_updated": False,
        },
    }
    return summary, utility_pairs, utility_components


def write_outputs(
    output_value: str | Path,
    summary: dict[str, Any],
    pair_rows: list[dict[str, Any]],
    component_rows: list[dict[str, Any]],
) -> None:
    output_input = Path(output_value)
    if output_input.is_symlink() or output_input.exists():
        raise ComponentAuditError("V2 output already exists or is symlinked")
    output = output_input.resolve()
    output.mkdir(parents=True)
    (output / "summary.json").write_bytes(base.pretty_json(summary))
    with (output / "per_pair_utility.jsonl").open(
        "x", encoding="utf-8", newline="\n"
    ) as handle:
        for row in pair_rows:
            handle.write(base.canonical_json(row) + "\n")
    with (output / "per_component_utility.jsonl").open(
        "x", encoding="utf-8", newline="\n"
    ) as handle:
        for row in component_rows:
            handle.write(base.canonical_json(row) + "\n")
    with (output / "per_task.csv").open("x", encoding="utf-8", newline="") as handle:
        fields = (
            "split",
            "subset",
            "task",
            "pair_unweighted_accuracy",
            "pair_gap_weighted_accuracy",
            "component_gain_capture",
            "component_top1_accuracy",
            "component_normalized_regret",
        )
        writer = csv.DictWriter(handle, fieldnames=fields, lineterminator="\n")
        writer.writeheader()
        for split in ("dev", "test"):
            for subset in SUBSETS:
                metrics = summary["metrics"][split][subset]
                for task in sorted(metrics["pair_unweighted_accuracy"]["task_values"]):
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
                            "component_gain_capture": metrics[
                                "component_gain_capture"
                            ]["task_values"][task],
                            "component_top1_accuracy": metrics[
                                "component_top1_accuracy"
                            ]["task_values"][task],
                            "component_normalized_regret": metrics[
                                "component_normalized_regret"
                            ]["task_values"][task],
                        }
                    )
    names = (
        "summary.json",
        "per_pair_utility.jsonl",
        "per_component_utility.jsonl",
        "per_task.csv",
    )
    manifest = {name: base.sha256_file(output / name) for name in names}
    (output / "artifact_manifest.json").write_bytes(base.pretty_json(manifest))


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
        summary, pair_rows, component_rows = analyze(
            args.protocol,
            args.cards,
            args.tfidf_per_pair,
            args.tfidf_summary,
            args.cost_summary,
        )
        write_outputs(args.output, summary, pair_rows, component_rows)
    except (base.AuditError, OSError, ValueError, KeyError) as exc:
        print(f"TFIDF_COMPONENT_UTILITY_FAIL type={type(exc).__name__}", file=os.sys.stderr)
        return 2
    print(
        "TFIDF_COMPONENT_UTILITY_COMPLETE "
        f"status={summary['status']} "
        f"test_tasks={summary['metrics']['test']['merged']['tasks']} "
        f"test_components={summary['metrics']['test']['merged']['decision_components']}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
