#!/usr/bin/env python3
"""Independently verify the V2 TF-IDF comparison-component utility audit."""
from __future__ import annotations

import argparse
import csv
import hashlib
import json
import os
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any

import numpy as np

from phase1 import verify_tfidf_retrospective_utility_audit as base


PROTOCOL = "tfidf-retrospective-component-utility-audit-v2"
STATUS = "FROZEN_AFTER_V1_STRUCTURAL_FAILURE_BEFORE_AGGREGATE_UTILITY_OBSERVATION"
SUBSETS = ("merged", "Draft", "Improve")
OUTPUTS = (
    "summary.json",
    "per_pair_utility.jsonl",
    "per_component_utility.jsonl",
    "per_task.csv",
)


class ComponentVerificationError(base.VerificationError):
    """Raised when V2 artifacts differ from an independent recomputation."""


def artifact_paths(output_value: str | Path) -> tuple[Path, dict[str, Path]]:
    output = Path(output_value)
    if output.is_symlink() or not output.is_dir():
        raise ComponentVerificationError("V2 output root invalid")
    observed = {entry.name for entry in output.iterdir()}
    if observed != {*OUTPUTS, "artifact_manifest.json"}:
        raise ComponentVerificationError("V2 output file set mismatch")
    manifest = base.read_object(output / "artifact_manifest.json", "V2 manifest")
    if set(manifest) != set(OUTPUTS):
        raise ComponentVerificationError("V2 manifest schema mismatch")
    paths = {name: output / name for name in OUTPUTS}
    for name, path in paths.items():
        if path.is_symlink() or not path.is_file() or base.sha256_file(path) != manifest[name]:
            raise ComponentVerificationError(f"V2 artifact hash mismatch: {name}")
    return output, paths


def graph_components(rows: list[dict[str, Any]]) -> list[tuple[str, ...]]:
    adjacency: dict[str, set[str]] = defaultdict(set)
    for row in rows:
        left, right = row["better"], row["worse"]
        adjacency[left].add(right)
        adjacency[right].add(left)
    components = []
    remaining = set(adjacency)
    while remaining:
        frontier = [min(remaining)]
        reached = set()
        while frontier:
            current = frontier.pop()
            if current in reached:
                continue
            reached.add(current)
            frontier.extend(sorted(adjacency[current] - reached, reverse=True))
        remaining -= reached
        components.append(tuple(sorted(reached)))
    return sorted(components, key=lambda values: values[0])


def component_id(
    split: str,
    task: str,
    parent: str,
    semantics: str,
    endpoints: tuple[str, ...],
) -> str:
    value = {
        "split": split,
        "task": task,
        "parent": parent,
        "semantics": semantics,
        "endpoints_sorted": list(endpoints),
    }
    return hashlib.sha256(base.canonical(value).encode("utf-8")).hexdigest()


def independently_build_components(
    source: list[dict[str, Any]],
    truth: dict[str, dict[str, Any]],
    tolerance: dict[str, float],
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    grouped: dict[tuple[str, str, str, str], list[dict[str, Any]]] = defaultdict(list)
    parent_semantics: dict[tuple[str, str, str], set[str]] = defaultdict(set)
    for row in source:
        key = (row["split"], row["task"], row["parent"], row["semantics"])
        grouped[key].append(row)
        parent_semantics[key[:3]].add(row["semantics"])

    output = []
    group_records = []
    assigned: set[tuple[str, int]] = set()
    for (split, task, parent, semantics), rows in sorted(grouped.items()):
        endpoint_sets = graph_components(rows)
        for ordinal, endpoints in enumerate(endpoint_sets):
            endpoint_set = set(endpoints)
            selected = [
                row
                for row in rows
                if row["better"] in endpoint_set and row["worse"] in endpoint_set
            ]
            if not selected:
                raise ComponentVerificationError("independent empty component")
            for row in selected:
                key = (row["split"], row["index"])
                if key in assigned:
                    raise ComponentVerificationError("independent duplicate assignment")
                assigned.add(key)
            solved = base.solve_parent(selected, truth, tolerance)
            output.append(
                {
                    "split": split,
                    "task": task,
                    "parent": parent,
                    "semantics": semantics,
                    "component_ordinal": ordinal,
                    "component_id": component_id(
                        split, task, parent, semantics, endpoints
                    ),
                    **solved,
                }
            )
        group_records.append(
            {"split": split, "components": len(endpoint_sets), "pairs": len(rows)}
        )
    if len(assigned) != len(source):
        raise ComponentVerificationError("independent incomplete pair assignment")

    structure: dict[str, Any] = {
        "parent_groups": len(group_records),
        "disconnected_parent_groups": sum(
            record["components"] > 1 for record in group_records
        ),
        "decision_components": len(output),
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
            "decision_components": sum(record["components"] for record in selected),
        }
    return output, structure


def metric_block(
    split: str,
    subset: str,
    pairs: list[dict[str, Any]],
    components: list[dict[str, Any]],
    bootstrap: dict[str, Any],
) -> dict[str, Any]:
    selected_pairs = [
        row
        for row in pairs
        if row["split"] == split and (subset == "merged" or row["semantics"] == subset)
    ]
    selected_components = [
        row
        for row in components
        if row["split"] == split and (subset == "merged" or row["semantics"] == subset)
    ]
    tasks = sorted({row["task"] for row in selected_pairs})
    if not selected_pairs or not selected_components or set(tasks) != {
        row["task"] for row in selected_components
    }:
        raise ComponentVerificationError("V2 task support mismatch")
    unweighted: dict[str, float] = {}
    weighted: dict[str, float] = {}
    capture: dict[str, float] = {}
    top1: dict[str, float] = {}
    regret: dict[str, float] = {}
    for task in tasks:
        task_pairs = [row for row in selected_pairs if row["task"] == task]
        task_components = [
            row for row in selected_components if row["task"] == task
        ]
        total_gap = sum(row["oriented_raw_gap"] for row in task_pairs)
        denominator = sum(
            row["oracle_minus_random"] for row in task_components
        )
        if total_gap <= 0 or denominator <= 0:
            raise ComponentVerificationError("V2 independent denominator invalid")
        unweighted[task] = float(np.mean([row["correct"] for row in task_pairs]))
        weighted[task] = float(
            sum(row["oriented_raw_gap"] for row in task_pairs if row["correct"])
            / total_gap
        )
        capture[task] = float(
            sum(row["selected_minus_random"] for row in task_components)
            / denominator
        )
        top1[task] = float(
            np.mean([row["top1_exact"] for row in task_components])
        )
        regret[task] = float(
            sum(row["regret"] for row in task_components) / denominator
        )
    difference = {task: weighted[task] - unweighted[task] for task in tasks}
    prefix = f"v2.{split}.{subset}"
    weighted_receipt = base.boot(
        weighted,
        prefix + ".pair_gap_weighted_accuracy",
        bootstrap["task_seed"],
        bootstrap["replicates"],
    )
    return {
        "pairs": len(selected_pairs),
        "decision_components": len(selected_components),
        "parent_groups": len(
            {(row["task"], row["parent"]) for row in selected_components}
        ),
        "tasks": len(tasks),
        "dominant_component_task_share": max(
            Counter(row["task"] for row in selected_components).values()
        )
        / len(selected_components),
        "pair_unweighted_accuracy": base.boot(
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
        "pair_gap_weighted_minus_unweighted": base.boot(
            difference,
            prefix + ".pair_gap_weighted_minus_unweighted",
            bootstrap["task_seed"],
            bootstrap["replicates"],
        ),
        "component_gain_capture": base.boot(
            capture,
            prefix + ".component_gain_capture",
            bootstrap["task_seed"],
            bootstrap["replicates"],
        ),
        "component_top1_accuracy": base.boot(
            top1,
            prefix + ".component_top1_accuracy",
            bootstrap["task_seed"],
            bootstrap["replicates"],
        ),
        "component_normalized_regret": base.boot(
            regret,
            prefix + ".component_normalized_regret",
            bootstrap["task_seed"],
            bootstrap["replicates"],
        ),
    }


def verify_task_csv(path: Path, metrics: dict[str, Any]) -> int:
    expected = []
    for split in ("dev", "test"):
        for subset in SUBSETS:
            block = metrics[split][subset]
            tasks = sorted(block["pair_unweighted_accuracy"]["task_values"])
            for task in tasks:
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
                        "component_gain_capture": str(
                            block["component_gain_capture"]["task_values"][task]
                        ),
                        "component_top1_accuracy": str(
                            block["component_top1_accuracy"]["task_values"][task]
                        ),
                        "component_normalized_regret": str(
                            block["component_normalized_regret"]["task_values"][task]
                        ),
                    }
                )
    with path.open(encoding="utf-8", newline="") as handle:
        observed = list(csv.DictReader(handle))
    if observed != expected:
        raise ComponentVerificationError("V2 per-task CSV mismatch")
    return len(observed)


def verify(
    protocol_path_value: str | Path,
    cards_path_value: str | Path,
    pair_path_value: str | Path,
    tfidf_summary_value: str | Path,
    cost_summary_value: str | Path,
    output_value: str | Path,
) -> dict[str, Any]:
    protocol_path = Path(protocol_path_value)
    protocol = base.read_object(protocol_path, "V2 protocol")
    if protocol.get("protocol") != PROTOCOL or protocol.get("status") != STATUS:
        raise ComponentVerificationError("V2 protocol freeze mismatch")
    frozen = protocol.get("frozen_inputs")
    if not isinstance(frozen, dict) or set(frozen) != {
        "cards",
        "cost_summary",
        "tfidf_per_pair",
        "tfidf_summary",
    }:
        raise ComponentVerificationError("V2 frozen inputs invalid")
    bootstrap = protocol.get("bootstrap")
    if (
        not isinstance(bootstrap, dict)
        or isinstance(bootstrap.get("replicates"), bool)
        or not isinstance(bootstrap.get("replicates"), int)
        or bootstrap["replicates"] < 1000
        or isinstance(bootstrap.get("task_seed"), bool)
        or not isinstance(bootstrap.get("task_seed"), int)
        or protocol.get("predecessor", {}).get("aggregate_utility_output_emitted")
        is not False
    ):
        raise ComponentVerificationError("V2 bootstrap/predecessor contract invalid")
    cards_path = base.checked(cards_path_value, frozen["cards"], "cards")
    pair_path = base.checked(pair_path_value, frozen["tfidf_per_pair"], "pairs")
    tfidf_path = base.checked(
        tfidf_summary_value, frozen["tfidf_summary"], "TF-IDF summary"
    )
    cost_path = base.checked(cost_summary_value, frozen["cost_summary"], "cost")
    output, artifacts = artifact_paths(output_value)
    source = base.load_source_pairs(pair_path)
    tfidf = base.read_object(tfidf_path, "TF-IDF summary")
    base.validate_tfidf_summary(tfidf, source)
    cost = base.read_object(cost_path, "cost summary")
    base.validate_cost_summary(cost, protocol)
    needed = {row[field] for row in source for field in ("better", "worse")}
    truth, card_inventory = base.load_truth(cards_path, needed)
    expected_pairs = base.expected_pair_rows(
        source, truth, protocol["tolerances"]["grade"]
    )
    observed_pairs = base.jsonl(artifacts["per_pair_utility.jsonl"], "V2 pair")
    if observed_pairs != expected_pairs:
        raise ComponentVerificationError("V2 pair rows differ")
    expected_components, structure = independently_build_components(
        source, truth, protocol["tolerances"]
    )
    if structure != protocol.get("expected_structure"):
        raise ComponentVerificationError("V2 structure differs from freeze")
    observed_components = base.jsonl(
        artifacts["per_component_utility.jsonl"], "V2 component"
    )
    if observed_components != expected_components:
        raise ComponentVerificationError("V2 component rows differ")
    metrics = {
        split: {
            subset: metric_block(
                split,
                subset,
                expected_pairs,
                expected_components,
                protocol["bootstrap"],
            )
            for subset in SUBSETS
        }
        for split in ("dev", "test")
    }
    summary = base.read_object(artifacts["summary.json"], "V2 summary")
    if summary.get("metrics") != metrics:
        raise ComponentVerificationError("V2 metrics differ")
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
    expected_status = (
        "RETROSPECTIVE_COMPONENT_COST_UTILITY_POSITIVE"
        if positive
        else "VALID_NO_STRONG_COMPONENT_COST_UTILITY_POSITIVE"
    )
    if (
        summary.get("protocol") != PROTOCOL
        or summary.get("status") != expected_status
        or summary.get("evidence_level")
        != "retrospective_accuracy_touched_component_clean_test_after_structural_v1_invalid"
        or summary.get("protocol_sha256") != base.sha256_file(protocol_path)
        or summary.get("inputs") != frozen
        or summary.get("predecessor") != protocol.get("predecessor")
        or summary.get("structure") != structure
        or summary.get("card_inventory") != card_inventory
        or summary.get("pair_inventory")
        != {
            "rows": len(source),
            "dev": sum(row["split"] == "dev" for row in source),
            "test": sum(row["split"] == "test" for row in source),
            "needed_endpoints": len(needed),
        }
        or summary.get("cost") != base.extract_cost(cost, protocol)
        or summary.get("primary_positive_gates") != gates
        or summary.get("primary_positive_gates_pass") is not positive
        or summary.get("claim_boundary") != protocol.get("claim_boundary")
        or summary.get("access_attestation")
        != {
            "future_or_prospective_vault_opened": False,
            "historical_released_cards_opened": True,
            "gpu_used": False,
            "api_used": False,
            "model_fit": False,
            "base_llm_updated": False,
        }
    ):
        raise ComponentVerificationError("V2 summary metadata/gates differ")
    task_rows = verify_task_csv(artifacts["per_task.csv"], metrics)
    return {
        "protocol": "independent-tfidf-retrospective-component-utility-verifier-v2",
        "status": "TFIDF_RETROSPECTIVE_COMPONENT_UTILITY_INDEPENDENTLY_VERIFIED",
        "producer_imported": False,
        "source_pairs": len(source),
        "utility_pairs": len(expected_pairs),
        "utility_components": len(expected_components),
        "task_csv_rows": task_rows,
        "primary_positive_gates_pass": positive,
        "summary_sha256": base.sha256_file(artifacts["summary.json"]),
        "artifact_manifest_sha256": base.sha256_file(
            output / "artifact_manifest.json"
        ),
        "future_or_prospective_vault_opened": False,
        "gpu_api_model_fit": [0, 0, 0],
    }


def write_receipt(path_value: str | Path, receipt: dict[str, Any]) -> None:
    path = Path(path_value)
    if path.is_symlink() or path.exists():
        raise ComponentVerificationError("V2 verification output exists")
    resolved = path.resolve()
    resolved.parent.mkdir(parents=True, exist_ok=True)
    temporary = resolved.with_name(resolved.name + f".tmp-{os.getpid()}")
    try:
        temporary.write_text(
            json.dumps(receipt, indent=2, sort_keys=True, allow_nan=False) + "\n",
            encoding="utf-8",
            newline="\n",
        )
        os.replace(temporary, resolved)
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
    except (base.VerificationError, OSError, ValueError, KeyError) as exc:
        print(f"TFIDF_COMPONENT_VERIFY_FAIL type={type(exc).__name__}", file=os.sys.stderr)
        return 2
    print(
        "TFIDF_COMPONENT_VERIFY_PASS "
        f"pairs={receipt['utility_pairs']} "
        f"components={receipt['utility_components']} "
        f"positive={str(receipt['primary_positive_gates_pass']).lower()}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
