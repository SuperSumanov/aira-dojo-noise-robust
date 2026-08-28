#!/usr/bin/env python3
"""Outcome-blind audit of edge weights induced by root-to-leaf linearization."""

from __future__ import annotations

import argparse
import collections
import hashlib
import json
import math
import os
import platform
import re
import statistics
import sys
from pathlib import Path
from typing import Any, Iterable


PROTOCOL_NAME = "prospective-tree-linearization-weight-audit-v1"
RECEIPT_PROTOCOL = "prospective-tree-linearization-weight-audit-receipt-v1"
BLIND_KEYS = {
    "card_id", "task", "run_id", "code", "code_sha256", "lineage",
    "generation_started_at_utc", "source_sha256",
}
LINEAGE_KEYS = {"depth", "step", "n_siblings", "op", "parent"}
RUN_KEYS = {
    "run_id", "task", "drop_id", "flow_status", "endpoints",
    "generation_started_at_utc", "source_sha256",
}
SHA_RE = re.compile(r"[0-9a-f]{64}")
CREDENTIAL_RE = re.compile(
    rb"(?:^|[^A-Za-z0-9])(?:sk-[A-Za-z0-9._-]{16,}|hf_[A-Za-z0-9]{16,}|"
    rb"gh[pousr]_[A-Za-z0-9]{16,}|AKIA[0-9A-Z]{16}|"
    rb"AIza[0-9A-Za-z_-]{20,}|Bearer[ \t]+[A-Za-z0-9._~-]{16,}|"
    rb"-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----)"
)


class AuditError(RuntimeError):
    pass


def require(condition: bool, message: str) -> None:
    if not condition:
        raise AuditError(message)


def sha256_bytes(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def sha256_file(path: Path) -> str:
    require(path.is_file() and not path.is_symlink(), f"unsafe hash input: {path.name}")
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1 << 20), b""):
            digest.update(block)
    return digest.hexdigest()


def read_object(path: Path) -> dict[str, Any]:
    require(path.is_file() and not path.is_symlink(), f"unsafe JSON input: {path.name}")
    value = json.loads(path.read_text(encoding="utf-8"))
    require(isinstance(value, dict), f"JSON root is not an object: {path.name}")
    return value


def read_rows(path: Path) -> Iterable[dict[str, Any]]:
    require(path.is_file() and not path.is_symlink(), f"unsafe JSONL input: {path.name}")
    with path.open(encoding="utf-8") as handle:
        for line_number, line in enumerate(handle, 1):
            require(bool(line.strip()), f"blank JSONL row: {path.name}:{line_number}")
            value = json.loads(line)
            require(isinstance(value, dict), f"non-object JSONL row: {path.name}:{line_number}")
            yield value


def canonical_sha(value: Any) -> str:
    raw = json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode()
    return sha256_bytes(raw)


def valid_sha(value: Any, label: str) -> str:
    require(isinstance(value, str) and SHA_RE.fullmatch(value) is not None, f"invalid {label}")
    return value


def protocol_value(path: Path, expected_sha: str) -> tuple[dict[str, Any], str]:
    actual = sha256_file(path)
    require(actual == expected_sha, "protocol SHA mismatch")
    value = read_object(path)
    require(value.get("protocol") == PROTOCOL_NAME, "protocol name mismatch")
    require(
        value.get("status") == "OUTCOME_BLIND_PROTOCOL_FROZEN_BEFORE_LINEARIZATION_AGGREGATES",
        "protocol status mismatch",
    )
    return value, actual


def verify_manifest_bytes(path: Path, expected_sha: str) -> bytes:
    require(path.is_file() and not path.is_symlink(), "unsafe blind manifest")
    raw = path.read_bytes()
    require(sha256_bytes(raw) == expected_sha, "blind manifest SHA mismatch")
    require(CREDENTIAL_RE.search(raw) is None, "credential-shaped bytes in blind manifest")
    return raw


def load_population(
    state_root: Path, snapshot_root: Path, protocol: dict[str, Any]
) -> tuple[dict[str, dict[str, Any]], dict[str, dict[str, Any]], dict[str, Any]]:
    state = state_root.resolve()
    snapshot = snapshot_root.resolve()
    fixed = protocol["fixed_snapshot"]
    snapshot_sha = valid_sha(fixed["sha256"], "fixed snapshot SHA")
    require(snapshot.parent == state / "snapshots" and snapshot.name == snapshot_sha, "snapshot path mismatch")
    latest = state / "LATEST"
    require(latest.is_file() and not latest.is_symlink(), "LATEST is unsafe")
    require(latest.read_text(encoding="utf-8").strip() == snapshot_sha, "LATEST mismatch")

    registry_path = snapshot / "intake_registry.jsonl"
    accumulator_dir = snapshot / "accumulator"
    accumulator_summary_path = accumulator_dir / "summary.json"
    runs_path = accumulator_dir / "provisional_runs.jsonl"
    accumulator = read_object(accumulator_summary_path)
    require(accumulator.get("protocol") == "prospective_accumulator_v1", "accumulator protocol mismatch")
    security = accumulator.get("security")
    require(
        isinstance(security, dict)
        and security.get("label_vault_opened") is False
        and security.get("outcome_files_opened") == []
        and security.get("scorer_prediction_files_opened") == [],
        "accumulator is not outcome blind",
    )
    require(accumulator.get("closure", {}).get("provided") is False, "unexpected closure state")
    require(
        accumulator.get("inputs", {}).get("registry_sha256") == sha256_file(registry_path),
        "registry binding mismatch",
    )
    require(
        accumulator.get("outputs", {}).get("provisional_runs_sha256") == sha256_file(runs_path),
        "provisional run binding mismatch",
    )

    registry = list(read_rows(registry_path))
    cards: dict[str, dict[str, Any]] = {}
    run_drop: dict[str, str] = {}
    binding_rows: list[tuple[str, str]] = []
    seen_drops: set[str] = set()
    expected_intake_summaries = accumulator.get("inputs", {}).get("intake_summaries")
    require(isinstance(expected_intake_summaries, dict), "accumulator intake bindings missing")

    for entry in registry:
        require(set(entry) == {"drop_id", "intake_dir", "summary_sha256"}, "registry schema mismatch")
        drop_id = entry["drop_id"]
        require(isinstance(drop_id, str) and drop_id and drop_id not in seen_drops, "invalid drop identity")
        seen_drops.add(drop_id)
        intake = Path(entry["intake_dir"]).resolve()
        require(intake.parent == state / "intakes" and intake.name == drop_id, "intake path mismatch")
        summary_sha = valid_sha(entry["summary_sha256"], "intake summary SHA")
        summary_path = intake / "summary.json"
        require(sha256_file(summary_path) == summary_sha, "intake summary hash mismatch")
        require(expected_intake_summaries.get(drop_id) == summary_sha, "accumulator intake mismatch")
        summary = read_object(summary_path)
        outputs = summary.get("outputs")
        intake_security = summary.get("security")
        blindness = summary.get("blindness")
        require(all(isinstance(value, dict) for value in (outputs, intake_security, blindness)), "intake contract missing")
        require(
            intake_security.get("env_members_read") is False
            and intake_security.get("live_event_journal_members_read") is False
            and blindness.get("labels_used_for_run_selection") is False
            and blindness.get("labels_used_for_endpoint_selection") is False
            and blindness.get("metrics_computed") == [],
            "intake blindness contract failed",
        )
        manifest_sha = valid_sha(outputs.get("eligible_blind_manifest_sha256"), "blind manifest SHA")
        manifest_path = intake / "eligible_blind_manifest.jsonl"
        verify_manifest_bytes(manifest_path, manifest_sha)
        binding_rows.append((summary_sha, manifest_sha))
        for row in read_rows(manifest_path):
            require(set(row) == BLIND_KEYS, "blind manifest schema mismatch")
            lineage = row.get("lineage")
            require(isinstance(lineage, dict) and set(lineage) == LINEAGE_KEYS, "blind lineage schema mismatch")
            card_id, task, run_id = row["card_id"], row["task"], row["run_id"]
            code, parent = row["code"], lineage["parent"]
            require(
                all(isinstance(value, str) and value for value in (card_id, task, run_id, code, parent))
                and card_id not in cards,
                "invalid or duplicate blind endpoint",
            )
            require(hashlib.sha256(code.encode()).hexdigest() == row["code_sha256"], "code SHA mismatch")
            valid_sha(row["source_sha256"], "source SHA")
            for key in ("depth", "step", "n_siblings"):
                value = lineage[key]
                require(isinstance(value, int) and not isinstance(value, bool) and value >= 0, "invalid lineage integer")
            require(isinstance(lineage["op"], str) and lineage["op"], "invalid lineage operator")
            owner = run_drop.setdefault(run_id, drop_id)
            require(owner == drop_id, "physical run spans intake drops")
            cards[card_id] = {
                "task": task,
                "run": run_id,
                "parent": parent,
                "depth": lineage["depth"],
            }

    runs: dict[str, dict[str, Any]] = {}
    for row in read_rows(runs_path):
        require(set(row) == RUN_KEYS, "provisional run schema mismatch")
        run_id = row.get("run_id")
        require(isinstance(run_id, str) and run_id and run_id not in runs, "invalid provisional run")
        require(row.get("flow_status") == "scoreable", "non-scoreable provisional run")
        require(row.get("drop_id") == run_drop.get(run_id), "run/drop mismatch")
        require(isinstance(row.get("task"), str) and row["task"], "invalid run task")
        require(isinstance(row.get("endpoints"), int) and row["endpoints"] > 0, "invalid endpoint count")
        runs[run_id] = row

    by_run = collections.Counter(card["run"] for card in cards.values())
    require(set(by_run) == set(runs), "card/run population mismatch")
    for run_id, row in runs.items():
        require(by_run[run_id] == row["endpoints"], "run endpoint count mismatch")
    for card in cards.values():
        require(runs[card["run"]]["task"] == card["task"], "card/run task mismatch")

    expected = {
        "runs": fixed["provisional_first960_runs"],
        "endpoints": fixed["eligible_endpoints"],
        "tasks": fixed["tasks"],
    }
    observed = {"runs": len(runs), "endpoints": len(cards), "tasks": len({c["task"] for c in cards.values()})}
    require(observed == expected, "fixed population count mismatch")
    inventory = accumulator.get("inventory", {})
    require(
        inventory.get("provisional_first960_runs") == expected["runs"]
        and inventory.get("provisional_first960_endpoints") == expected["endpoints"],
        "accumulator fixed population mismatch",
    )
    task_support = accumulator.get("task_support", {}).get("provisional_first960", {})
    require(task_support.get("tasks") == expected["tasks"], "accumulator task count mismatch")

    bindings = {
        "registry_sha256": sha256_file(registry_path),
        "accumulator_summary_sha256": sha256_file(accumulator_summary_path),
        "provisional_runs_sha256": sha256_file(runs_path),
        "intake_summary_manifest_multiset_sha256": canonical_sha(sorted(binding_rows)),
        "intake_count": len(registry),
    }
    return cards, runs, bindings


def concentration(counts: dict[str, int]) -> dict[str, Any]:
    values = [value for value in counts.values() if value > 0]
    require(bool(values), "concentration has no positive weight")
    total = sum(values)
    shares = [value / total for value in values]
    hhi = math.fsum(value * value for value in shares)
    return {
        "positive_clusters": len(values),
        "total_weight": total,
        "maximum_share": max(shares),
        "hhi": hhi,
        "inverse_hhi_descriptive_diversity": 1.0 / hhi,
    }


def total_variation(left: dict[str, int], right: dict[str, int]) -> float:
    keys = set(left) | set(right)
    left_total, right_total = sum(left.values()), sum(right.values())
    require(left_total > 0 and right_total > 0, "TV has zero total")
    return 0.5 * math.fsum(
        abs(left.get(key, 0) / left_total - right.get(key, 0) / right_total)
        for key in keys
    )


def nearest_rank(values: list[int], probability: float) -> int:
    require(bool(values) and 0 < probability <= 1, "invalid quantile input")
    ordered = sorted(values)
    rank = max(1, math.ceil(probability * len(ordered)))
    return ordered[rank - 1]


def graph_metrics(
    cards: dict[str, dict[str, Any]], protocol: dict[str, Any]
) -> dict[str, Any]:
    children: dict[str, list[str]] = {card_id: [] for card_id in cards}
    observed_parent: dict[str, str] = {}
    fragment_roots: list[str] = []
    for child_id, child in cards.items():
        parent_id = child["parent"]
        if parent_id not in cards:
            fragment_roots.append(child_id)
            continue
        parent = cards[parent_id]
        require(parent_id != child_id, "self-parent edge")
        require(parent["run"] == child["run"], "observed edge crosses physical runs")
        require(parent["task"] == child["task"], "observed edge crosses tasks")
        observed_parent[child_id] = parent_id
        children[parent_id].append(child_id)

    state: dict[str, int] = {}
    for start in cards:
        trail: list[str] = []
        cursor = start
        while cursor in observed_parent and state.get(cursor, 0) == 0:
            state[cursor] = 1
            trail.append(cursor)
            cursor = observed_parent[cursor]
        require(state.get(cursor, 0) != 1, "observed graph contains a cycle")
        for node in trail:
            state[node] = 2
    require(len(fragment_roots) > 0, "observed graph has no fragment roots")

    leaf_counts: dict[str, int] = {}
    stack: list[tuple[str, bool]] = [(root, False) for root in sorted(fragment_roots)]
    while stack:
        node, expanded = stack.pop()
        if expanded:
            child_rows = children[node]
            leaf_counts[node] = 1 if not child_rows else sum(leaf_counts[child] for child in child_rows)
        else:
            stack.append((node, True))
            stack.extend((child, False) for child in children[node])
    require(len(leaf_counts) == len(cards), "not all endpoints are rooted in observed fragments")

    multiplicities: list[int] = []
    unique_task: collections.Counter[str] = collections.Counter()
    linear_task: collections.Counter[str] = collections.Counter()
    unique_run: collections.Counter[str] = collections.Counter()
    linear_run: collections.Counter[str] = collections.Counter()
    unique_depth: collections.Counter[str] = collections.Counter()
    linear_depth: collections.Counter[str] = collections.Counter()
    multiplicity_histogram: collections.Counter[str] = collections.Counter()
    for child_id in sorted(observed_parent):
        card = cards[child_id]
        multiplicity = leaf_counts[child_id]
        require(multiplicity >= 1, "invalid edge multiplicity")
        multiplicities.append(multiplicity)
        multiplicity_histogram[str(multiplicity)] += 1
        task, run, depth = card["task"], card["run"], str(card["depth"])
        unique_task[task] += 1
        linear_task[task] += multiplicity
        unique_run[run] += 1
        linear_run[run] += multiplicity
        unique_depth[depth] += 1
        linear_depth[depth] += multiplicity

    unique_edges = len(multiplicities)
    branch_occurrences = sum(multiplicities)
    duplicate_occurrences = branch_occurrences - unique_edges
    require(unique_edges > 0 and duplicate_occurrences >= 0, "invalid edge totals")
    task_tv = total_variation(dict(unique_task), dict(linear_task))
    run_tv = total_variation(dict(unique_run), dict(linear_run))
    run_task = {card["run"]: card["task"] for card in cards.values()}
    per_task_run_tv = []
    for task in sorted(unique_task):
        task_unique = {
            run: count for run, count in unique_run.items() if run_task[run] == task
        }
        task_linear = {run: linear_run[run] for run in task_unique}
        per_task_run_tv.append(total_variation(task_unique, task_linear))

    thresholds = protocol["materiality_thresholds"]
    support = protocol["hard_integrity_gates"]
    edge_runs, edge_tasks = len(unique_run), len(unique_task)
    parent_present_fraction = unique_edges / len(cards)
    gates = {
        "latest_equals_fixed_snapshot": True,
        "intake_and_accumulator_hashes_rechecked": True,
        "blind_manifest_schema_exact": True,
        "all_cards_unique": True,
        "all_provisional_runs_unique_and_scoreable": True,
        "card_run_task_matches_provisional_run": True,
        "observed_edges_same_task_and_physical_run": True,
        "observed_graph_acyclic": True,
        "parent_present_endpoint_fraction_at_least_minimum": parent_present_fraction
        >= support["minimum_parent_present_endpoint_fraction"],
        "observed_unique_edges_at_least_minimum": unique_edges
        >= support["minimum_observed_unique_edges"],
        "physical_runs_with_observed_edges_at_least_minimum": edge_runs
        >= support["minimum_physical_runs_with_observed_edges"],
        "tasks_with_observed_edges_at_least_minimum": edge_tasks
        >= support["minimum_tasks_with_observed_edges"],
    }
    all_gates = all(gates.values())
    duplicate_fraction = duplicate_occurrences / branch_occurrences
    duplicate_material = duplicate_fraction >= thresholds["minimum_duplicate_branch_occurrence_fraction"]
    task_material = task_tv >= thresholds["minimum_unique_to_linearized_task_total_variation"]
    run_material = run_tv >= thresholds["minimum_unique_to_linearized_run_total_variation"]
    if not all_gates:
        classification = "LINEARIZATION_AUDIT_GATE_FAIL"
    elif duplicate_material and task_material and run_material:
        classification = "MULTI_AXIS_MATERIAL_LINEARIZATION_REWEIGHTING"
    elif duplicate_material and run_material:
        classification = "RUN_LEVEL_MATERIAL_LINEARIZATION_REWEIGHTING"
    elif duplicate_occurrences > 0:
        classification = "LINEARIZATION_DUPLICATION_WITHOUT_MATERIAL_WEIGHT_SHIFT"
    else:
        classification = "NO_OBSERVED_LINEARIZATION_DUPLICATION"
    require(classification in protocol["ordered_classification"], "classification outside protocol")

    reference = thresholds["per_task_run_total_variation_reference"]
    return {
        "classification": classification,
        "inventory": {
            "eligible_endpoints": len(cards),
            "observed_unique_edges": unique_edges,
            "fragment_roots": len(fragment_roots),
            "fragment_leaves": sum(not children[node] for node in cards),
            "observed_fragments": len(fragment_roots),
            "single_node_fragments": sum(not children[root] for root in fragment_roots),
            "physical_runs": len({card["run"] for card in cards.values()}),
            "tasks": len({card["task"] for card in cards.values()}),
            "physical_runs_with_observed_edges": edge_runs,
            "tasks_with_observed_edges": edge_tasks,
            "parent_present_endpoint_fraction": parent_present_fraction,
        },
        "linearization": {
            "root_to_leaf_trajectory_count": sum(leaf_counts[root] for root in fragment_roots),
            "unique_edge_rows": unique_edges,
            "branch_linearized_edge_occurrences": branch_occurrences,
            "duplicate_edge_occurrences": duplicate_occurrences,
            "duplicate_branch_occurrence_fraction": duplicate_fraction,
            "mean_edge_multiplicity": branch_occurrences / unique_edges,
            "fraction_unique_edges_repeated": sum(value > 1 for value in multiplicities) / unique_edges,
            "edge_multiplicity": {
                "minimum": min(multiplicities),
                "median": statistics.median(multiplicities),
                "p90_nearest_rank": nearest_rank(multiplicities, 0.90),
                "p95_nearest_rank": nearest_rank(multiplicities, 0.95),
                "maximum": max(multiplicities),
                "histogram": dict(sorted(multiplicity_histogram.items(), key=lambda item: int(item[0]))),
            },
        },
        "weighting": {
            "task": {
                "unique_edges": concentration(dict(unique_task)),
                "branch_linearized": concentration(dict(linear_task)),
                "total_variation": task_tv,
            },
            "physical_run": {
                "unique_edges": concentration(dict(unique_run)),
                "branch_linearized": concentration(dict(linear_run)),
                "total_variation": run_tv,
            },
            "anonymous_per_task_run_total_variation": {
                "task_count": len(per_task_run_tv),
                "values_sorted": sorted(per_task_run_tv),
                "median": statistics.median(per_task_run_tv),
                "maximum": max(per_task_run_tv),
                "tasks_at_or_above_reference": sum(value >= reference for value in per_task_run_tv),
                "reference": reference,
            },
            "depth_diagnostic": {
                "unique_edge_counts": dict(sorted(unique_depth.items(), key=lambda item: int(item[0]))),
                "branch_linearized_counts": dict(sorted(linear_depth.items(), key=lambda item: int(item[0]))),
                "total_variation": total_variation(dict(unique_depth), dict(linear_depth)),
                "non_rescuing": True,
            },
        },
        "pre_registered_gate": {
            "hard_integrity_and_support": gates,
            "all_hard_gates_passed": all_gates,
            "materiality": {
                "duplicate_fraction_at_least_threshold": duplicate_material,
                "task_total_variation_at_least_threshold": task_material,
                "run_total_variation_at_least_threshold": run_material,
            },
            "thresholds": {**support, **thresholds},
        },
    }


def build_receipt(
    state_root: Path,
    snapshot_root: Path,
    protocol_path: Path,
    protocol_sha: str,
    source_commit: str,
) -> dict[str, Any]:
    require(re.fullmatch(r"[0-9a-f]{40}", source_commit) is not None, "invalid source commit")
    protocol, actual_protocol_sha = protocol_value(protocol_path, protocol_sha)
    cards, runs, bindings = load_population(state_root, snapshot_root, protocol)
    result = graph_metrics(cards, protocol)
    return {
        "protocol": RECEIPT_PROTOCOL,
        "status": "OUTCOME_BLIND_TREE_LINEARIZATION_WEIGHT_AUDIT_COMPLETE",
        "snapshot_sha256": protocol["fixed_snapshot"]["sha256"],
        "protocol_sha256": actual_protocol_sha,
        "source_commit": source_commit,
        "producer_source_sha256": sha256_file(Path(__file__)),
        "input_bindings": bindings,
        **result,
        "claim_boundary": protocol["claim_boundary"],
        "security": {
            "allowed_input_basenames": protocol["security"]["allowed_input_basenames"],
            "raw_senior_archives_opened": False,
            "prospective_label_grade_outcome_prediction_values_read": False,
            "task_run_card_parent_or_code_values_emitted": False,
            "accuracy_effect_or_search_utility_computed": False,
            "gpu_api_model_fit_base_update": [0, 0, 0, 0],
        },
        "reproducibility": {
            "python_version": platform.python_version(),
            "randomness_used": False,
        },
    }


def write_new(path: Path, value: dict[str, Any]) -> None:
    require(not path.exists(), "refusing to overwrite output")
    require(path.parent.is_dir() and not path.parent.is_symlink(), "unsafe output parent")
    temporary = path.with_name(path.name + f".tmp-{os.getpid()}")
    temporary.write_text(
        json.dumps(value, indent=2, sort_keys=True, ensure_ascii=False, allow_nan=False) + "\n",
        encoding="utf-8",
        newline="\n",
    )
    temporary.replace(path)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--state-root", required=True, type=Path)
    parser.add_argument("--snapshot-root", required=True, type=Path)
    parser.add_argument("--protocol", required=True, type=Path)
    parser.add_argument("--expect-protocol-sha256", required=True)
    parser.add_argument("--source-commit", required=True)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    try:
        receipt = build_receipt(
            args.state_root,
            args.snapshot_root,
            args.protocol,
            args.expect_protocol_sha256,
            args.source_commit,
        )
        write_new(args.output.resolve(), receipt)
        print(json.dumps({
            "status": receipt["status"],
            "classification": receipt["classification"],
            "snapshot_sha256": receipt["snapshot_sha256"],
        }, sort_keys=True, separators=(",", ":")))
        return 0
    except (AuditError, OSError, ValueError, KeyError, ZeroDivisionError) as error:
        print(f"TREE_LINEARIZATION_WEIGHT_AUDIT_ERROR: {error}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
