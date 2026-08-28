#!/usr/bin/env python3
"""Non-importing verifier for the prospective tree-linearization weight audit."""

from __future__ import annotations

import argparse
import collections
import hashlib
import json
import math
import os
import re
import statistics
import sys
from pathlib import Path
from typing import Any, Iterable


PROTOCOL_NAME = "prospective-tree-linearization-weight-audit-v1"
RECEIPT_PROTOCOL = "prospective-tree-linearization-weight-audit-receipt-v1"
VERIFY_PROTOCOL = "independent-prospective-tree-linearization-weight-audit-v1"
BLIND_FIELDS = {
    "card_id", "task", "run_id", "code", "code_sha256", "lineage",
    "generation_started_at_utc", "source_sha256",
}
LINEAGE_FIELDS = {"depth", "step", "n_siblings", "op", "parent"}
RUN_FIELDS = {
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


class VerificationError(RuntimeError):
    pass


def check(condition: bool, message: str) -> None:
    if not condition:
        raise VerificationError(message)


def digest_bytes(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def digest_file(path: Path) -> str:
    check(path.is_file() and not path.is_symlink(), f"unsafe hash input: {path.name}")
    hasher = hashlib.sha256()
    with path.open("rb") as stream:
        while True:
            block = stream.read(1 << 20)
            if not block:
                break
            hasher.update(block)
    return hasher.hexdigest()


def object_at(path: Path) -> dict[str, Any]:
    check(path.is_file() and not path.is_symlink(), f"unsafe object input: {path.name}")
    parsed = json.loads(path.read_text(encoding="utf-8"))
    check(isinstance(parsed, dict), f"object expected: {path.name}")
    return parsed


def rows_at(path: Path) -> Iterable[dict[str, Any]]:
    check(path.is_file() and not path.is_symlink(), f"unsafe row input: {path.name}")
    with path.open(encoding="utf-8") as stream:
        for number, line in enumerate(stream, 1):
            check(bool(line.strip()), f"blank row: {path.name}:{number}")
            parsed = json.loads(line)
            check(isinstance(parsed, dict), f"object row expected: {path.name}:{number}")
            yield parsed


def canonical_digest(value: Any) -> str:
    return digest_bytes(
        json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode()
    )


def sha_text(value: Any, label: str) -> str:
    check(isinstance(value, str) and SHA_RE.fullmatch(value) is not None, f"invalid {label}")
    return value


def collect_inputs(
    state_root: Path, snapshot_root: Path, protocol: dict[str, Any]
) -> tuple[dict[str, dict[str, Any]], dict[str, dict[str, Any]], dict[str, Any]]:
    state = state_root.resolve()
    snapshot = snapshot_root.resolve()
    fixed = protocol["fixed_snapshot"]
    snapshot_sha = sha_text(fixed["sha256"], "snapshot SHA")
    check(snapshot.parent == state / "snapshots" and snapshot.name == snapshot_sha, "snapshot binding mismatch")
    latest = state / "LATEST"
    check(latest.is_file() and not latest.is_symlink(), "unsafe LATEST")
    check(latest.read_text(encoding="utf-8").strip() == snapshot_sha, "LATEST mismatch")

    registry_path = snapshot / "intake_registry.jsonl"
    accumulator_root = snapshot / "accumulator"
    summary_path = accumulator_root / "summary.json"
    runs_path = accumulator_root / "provisional_runs.jsonl"
    summary = object_at(summary_path)
    check(summary.get("protocol") == "prospective_accumulator_v1", "accumulator protocol mismatch")
    sec = summary.get("security")
    check(
        isinstance(sec, dict)
        and sec.get("label_vault_opened") is False
        and sec.get("outcome_files_opened") == []
        and sec.get("scorer_prediction_files_opened") == [],
        "accumulator blindness mismatch",
    )
    check(summary.get("closure", {}).get("provided") is False, "closure state mismatch")
    check(summary.get("inputs", {}).get("registry_sha256") == digest_file(registry_path), "registry hash mismatch")
    check(summary.get("outputs", {}).get("provisional_runs_sha256") == digest_file(runs_path), "run ledger hash mismatch")
    expected_summaries = summary.get("inputs", {}).get("intake_summaries")
    check(isinstance(expected_summaries, dict), "intake summary bindings missing")

    cards: dict[str, dict[str, Any]] = {}
    owner_by_run: dict[str, str] = {}
    seen_drops: set[str] = set()
    binding_pairs: list[tuple[str, str]] = []
    registry = list(rows_at(registry_path))
    for registry_row in registry:
        check(set(registry_row) == {"drop_id", "intake_dir", "summary_sha256"}, "registry schema mismatch")
        drop = registry_row["drop_id"]
        check(isinstance(drop, str) and drop and drop not in seen_drops, "duplicate drop")
        seen_drops.add(drop)
        intake = Path(registry_row["intake_dir"]).resolve()
        check(intake.parent == state / "intakes" and intake.name == drop, "intake path mismatch")
        summary_sha = sha_text(registry_row["summary_sha256"], "intake summary SHA")
        intake_summary_path = intake / "summary.json"
        check(digest_file(intake_summary_path) == summary_sha, "intake summary digest mismatch")
        check(expected_summaries.get(drop) == summary_sha, "intake summary not bound by accumulator")
        intake_summary = object_at(intake_summary_path)
        outputs = intake_summary.get("outputs")
        security = intake_summary.get("security")
        blindness = intake_summary.get("blindness")
        check(all(isinstance(item, dict) for item in (outputs, security, blindness)), "intake contract absent")
        check(
            security.get("env_members_read") is False
            and security.get("live_event_journal_members_read") is False
            and blindness.get("labels_used_for_run_selection") is False
            and blindness.get("labels_used_for_endpoint_selection") is False
            and blindness.get("metrics_computed") == [],
            "intake blindness mismatch",
        )
        manifest_sha = sha_text(outputs.get("eligible_blind_manifest_sha256"), "manifest SHA")
        manifest_path = intake / "eligible_blind_manifest.jsonl"
        check(manifest_path.is_file() and not manifest_path.is_symlink(), "unsafe blind manifest")
        manifest_raw = manifest_path.read_bytes()
        check(digest_bytes(manifest_raw) == manifest_sha, "manifest digest mismatch")
        check(CREDENTIAL_RE.search(manifest_raw) is None, "credential-shaped manifest bytes")
        binding_pairs.append((summary_sha, manifest_sha))
        for row in rows_at(manifest_path):
            check(set(row) == BLIND_FIELDS, "blind row schema mismatch")
            lineage = row.get("lineage")
            check(isinstance(lineage, dict) and set(lineage) == LINEAGE_FIELDS, "lineage schema mismatch")
            identifier, run, task = row["card_id"], row["run_id"], row["task"]
            code, parent = row["code"], lineage["parent"]
            check(
                all(isinstance(item, str) and item for item in (identifier, run, task, code, parent))
                and identifier not in cards,
                "invalid or duplicate endpoint",
            )
            check(hashlib.sha256(code.encode()).hexdigest() == row["code_sha256"], "endpoint code digest mismatch")
            sha_text(row["source_sha256"], "endpoint source SHA")
            for field in ("depth", "step", "n_siblings"):
                number = lineage[field]
                check(isinstance(number, int) and not isinstance(number, bool) and number >= 0, "invalid lineage number")
            check(isinstance(lineage["op"], str) and lineage["op"], "invalid lineage operation")
            prior_owner = owner_by_run.setdefault(run, drop)
            check(prior_owner == drop, "run split across drops")
            cards[identifier] = {"run": run, "task": task, "parent": parent, "depth": lineage["depth"]}

    runs: dict[str, dict[str, Any]] = {}
    for row in rows_at(runs_path):
        check(set(row) == RUN_FIELDS, "run ledger schema mismatch")
        run = row.get("run_id")
        check(isinstance(run, str) and run and run not in runs, "duplicate run")
        check(row.get("flow_status") == "scoreable", "non-scoreable run")
        check(row.get("drop_id") == owner_by_run.get(run), "run owner mismatch")
        check(isinstance(row.get("task"), str) and row["task"], "invalid run task")
        check(isinstance(row.get("endpoints"), int) and row["endpoints"] > 0, "invalid run endpoints")
        runs[run] = row

    card_counts = collections.Counter(card["run"] for card in cards.values())
    check(set(card_counts) == set(runs), "run/card set mismatch")
    for run, row in runs.items():
        check(card_counts[run] == row["endpoints"], "run/card count mismatch")
    for card in cards.values():
        check(runs[card["run"]]["task"] == card["task"], "run/card task mismatch")

    observed_counts = {
        "runs": len(runs),
        "endpoints": len(cards),
        "tasks": len({card["task"] for card in cards.values()}),
    }
    expected_counts = {
        "runs": fixed["provisional_first960_runs"],
        "endpoints": fixed["eligible_endpoints"],
        "tasks": fixed["tasks"],
    }
    check(observed_counts == expected_counts, "fixed count mismatch")
    inventory = summary.get("inventory", {})
    check(
        inventory.get("provisional_first960_runs") == expected_counts["runs"]
        and inventory.get("provisional_first960_endpoints") == expected_counts["endpoints"],
        "accumulator inventory mismatch",
    )
    check(
        summary.get("task_support", {}).get("provisional_first960", {}).get("tasks")
        == expected_counts["tasks"],
        "accumulator task support mismatch",
    )
    return cards, runs, {
        "registry_sha256": digest_file(registry_path),
        "accumulator_summary_sha256": digest_file(summary_path),
        "provisional_runs_sha256": digest_file(runs_path),
        "intake_summary_manifest_multiset_sha256": canonical_digest(sorted(binding_pairs)),
        "intake_count": len(registry),
    }


def cluster_summary(weights: dict[str, int]) -> dict[str, Any]:
    positive = [weight for weight in weights.values() if weight > 0]
    check(bool(positive), "empty cluster weighting")
    total = sum(positive)
    probabilities = [weight / total for weight in positive]
    hhi = math.fsum(probability * probability for probability in probabilities)
    return {
        "positive_clusters": len(positive),
        "total_weight": total,
        "maximum_share": max(probabilities),
        "hhi": hhi,
        "inverse_hhi_descriptive_diversity": 1.0 / hhi,
    }


def tv_distance(first: dict[str, int], second: dict[str, int]) -> float:
    keys = set(first) | set(second)
    first_total, second_total = sum(first.values()), sum(second.values())
    check(first_total > 0 and second_total > 0, "zero weighting total")
    return math.fsum(
        abs(first.get(key, 0) / first_total - second.get(key, 0) / second_total)
        for key in keys
    ) / 2


def percentile(values: list[int], probability: float) -> int:
    ordered = sorted(values)
    check(bool(ordered), "empty percentile")
    return ordered[max(1, math.ceil(probability * len(ordered))) - 1]


def independently_reconstruct(cards: dict[str, dict[str, Any]], protocol: dict[str, Any]) -> dict[str, Any]:
    child_lists: dict[str, list[str]] = {identifier: [] for identifier in cards}
    parent_map: dict[str, str] = {}
    roots: list[str] = []
    for child, row in cards.items():
        parent = row["parent"]
        if parent not in cards:
            roots.append(child)
        else:
            check(parent != child, "self loop")
            check(cards[parent]["run"] == row["run"], "cross-run edge")
            check(cards[parent]["task"] == row["task"], "cross-task edge")
            parent_map[child] = parent
            child_lists[parent].append(child)

    queue = collections.deque(sorted(roots))
    topological: list[str] = []
    while queue:
        node = queue.popleft()
        topological.append(node)
        queue.extend(sorted(child_lists[node]))
    check(len(topological) == len(cards), "cycle or unrooted component")

    descendant_leaves: dict[str, int] = {}
    for node in reversed(topological):
        descendant_leaves[node] = (
            1 if not child_lists[node] else sum(descendant_leaves[child] for child in child_lists[node])
        )

    unique_task: collections.Counter[str] = collections.Counter()
    linear_task: collections.Counter[str] = collections.Counter()
    unique_run: collections.Counter[str] = collections.Counter()
    linear_run: collections.Counter[str] = collections.Counter()
    unique_depth: collections.Counter[str] = collections.Counter()
    linear_depth: collections.Counter[str] = collections.Counter()
    histogram: collections.Counter[str] = collections.Counter()
    multiplicities: list[int] = []
    for child in sorted(parent_map):
        row = cards[child]
        multiplicity = descendant_leaves[child]
        check(multiplicity >= 1, "nonpositive multiplicity")
        multiplicities.append(multiplicity)
        histogram[str(multiplicity)] += 1
        unique_task[row["task"]] += 1
        linear_task[row["task"]] += multiplicity
        unique_run[row["run"]] += 1
        linear_run[row["run"]] += multiplicity
        depth = str(row["depth"])
        unique_depth[depth] += 1
        linear_depth[depth] += multiplicity

    unique_edges = len(multiplicities)
    branch_rows = sum(multiplicities)
    duplicates = branch_rows - unique_edges
    check(unique_edges > 0 and duplicates >= 0, "edge accounting failed")
    task_tv = tv_distance(dict(unique_task), dict(linear_task))
    run_tv = tv_distance(dict(unique_run), dict(linear_run))
    task_for_run = {card["run"]: card["task"] for card in cards.values()}
    within_task_tvs: list[float] = []
    for task in sorted(unique_task):
        first = {run: weight for run, weight in unique_run.items() if task_for_run[run] == task}
        second = {run: linear_run[run] for run in first}
        within_task_tvs.append(tv_distance(first, second))

    gates_spec = protocol["hard_integrity_gates"]
    material_spec = protocol["materiality_thresholds"]
    parent_fraction = unique_edges / len(cards)
    gates = {
        "latest_equals_fixed_snapshot": True,
        "intake_and_accumulator_hashes_rechecked": True,
        "blind_manifest_schema_exact": True,
        "all_cards_unique": True,
        "all_provisional_runs_unique_and_scoreable": True,
        "card_run_task_matches_provisional_run": True,
        "observed_edges_same_task_and_physical_run": True,
        "observed_graph_acyclic": True,
        "parent_present_endpoint_fraction_at_least_minimum": parent_fraction
        >= gates_spec["minimum_parent_present_endpoint_fraction"],
        "observed_unique_edges_at_least_minimum": unique_edges
        >= gates_spec["minimum_observed_unique_edges"],
        "physical_runs_with_observed_edges_at_least_minimum": len(unique_run)
        >= gates_spec["minimum_physical_runs_with_observed_edges"],
        "tasks_with_observed_edges_at_least_minimum": len(unique_task)
        >= gates_spec["minimum_tasks_with_observed_edges"],
    }
    all_gates = all(gates.values())
    duplicate_fraction = duplicates / branch_rows
    duplicate_material = duplicate_fraction >= material_spec["minimum_duplicate_branch_occurrence_fraction"]
    task_material = task_tv >= material_spec["minimum_unique_to_linearized_task_total_variation"]
    run_material = run_tv >= material_spec["minimum_unique_to_linearized_run_total_variation"]
    if not all_gates:
        classification = "LINEARIZATION_AUDIT_GATE_FAIL"
    elif duplicate_material and task_material and run_material:
        classification = "MULTI_AXIS_MATERIAL_LINEARIZATION_REWEIGHTING"
    elif duplicate_material and run_material:
        classification = "RUN_LEVEL_MATERIAL_LINEARIZATION_REWEIGHTING"
    elif duplicates > 0:
        classification = "LINEARIZATION_DUPLICATION_WITHOUT_MATERIAL_WEIGHT_SHIFT"
    else:
        classification = "NO_OBSERVED_LINEARIZATION_DUPLICATION"
    check(classification in protocol["ordered_classification"], "classification not allowed")
    reference = material_spec["per_task_run_total_variation_reference"]
    return {
        "classification": classification,
        "inventory": {
            "eligible_endpoints": len(cards),
            "observed_unique_edges": unique_edges,
            "fragment_roots": len(roots),
            "fragment_leaves": sum(not child_lists[node] for node in cards),
            "observed_fragments": len(roots),
            "single_node_fragments": sum(not child_lists[root] for root in roots),
            "physical_runs": len({card["run"] for card in cards.values()}),
            "tasks": len({card["task"] for card in cards.values()}),
            "physical_runs_with_observed_edges": len(unique_run),
            "tasks_with_observed_edges": len(unique_task),
            "parent_present_endpoint_fraction": parent_fraction,
        },
        "linearization": {
            "root_to_leaf_trajectory_count": sum(descendant_leaves[root] for root in roots),
            "unique_edge_rows": unique_edges,
            "branch_linearized_edge_occurrences": branch_rows,
            "duplicate_edge_occurrences": duplicates,
            "duplicate_branch_occurrence_fraction": duplicate_fraction,
            "mean_edge_multiplicity": branch_rows / unique_edges,
            "fraction_unique_edges_repeated": sum(value > 1 for value in multiplicities) / unique_edges,
            "edge_multiplicity": {
                "minimum": min(multiplicities),
                "median": statistics.median(multiplicities),
                "p90_nearest_rank": percentile(multiplicities, 0.90),
                "p95_nearest_rank": percentile(multiplicities, 0.95),
                "maximum": max(multiplicities),
                "histogram": dict(sorted(histogram.items(), key=lambda item: int(item[0]))),
            },
        },
        "weighting": {
            "task": {
                "unique_edges": cluster_summary(dict(unique_task)),
                "branch_linearized": cluster_summary(dict(linear_task)),
                "total_variation": task_tv,
            },
            "physical_run": {
                "unique_edges": cluster_summary(dict(unique_run)),
                "branch_linearized": cluster_summary(dict(linear_run)),
                "total_variation": run_tv,
            },
            "anonymous_per_task_run_total_variation": {
                "task_count": len(within_task_tvs),
                "values_sorted": sorted(within_task_tvs),
                "median": statistics.median(within_task_tvs),
                "maximum": max(within_task_tvs),
                "tasks_at_or_above_reference": sum(value >= reference for value in within_task_tvs),
                "reference": reference,
            },
            "depth_diagnostic": {
                "unique_edge_counts": dict(sorted(unique_depth.items(), key=lambda item: int(item[0]))),
                "branch_linearized_counts": dict(sorted(linear_depth.items(), key=lambda item: int(item[0]))),
                "total_variation": tv_distance(dict(unique_depth), dict(linear_depth)),
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
            "thresholds": {**gates_spec, **material_spec},
        },
    }


def compare(expected: Any, actual: Any, path: str) -> None:
    if isinstance(expected, float):
        check(
            isinstance(actual, (int, float))
            and not isinstance(actual, bool)
            and math.isclose(expected, float(actual), rel_tol=1e-12, abs_tol=1e-12),
            f"numeric mismatch: {path}",
        )
    elif isinstance(expected, dict):
        check(isinstance(actual, dict) and set(actual) == set(expected), f"mapping mismatch: {path}")
        for key in expected:
            compare(expected[key], actual[key], f"{path}.{key}")
    elif isinstance(expected, list):
        check(isinstance(actual, list) and len(actual) == len(expected), f"list mismatch: {path}")
        for index, item in enumerate(expected):
            compare(item, actual[index], f"{path}[{index}]")
    else:
        check(expected == actual, f"value mismatch: {path}")


def verify(
    state_root: Path,
    snapshot_root: Path,
    protocol_path: Path,
    protocol_sha: str,
    receipt_path: Path,
    receipt_sha: str,
    producer_source: Path,
    producer_source_sha: str,
    source_commit: str,
) -> dict[str, Any]:
    check(digest_file(protocol_path) == protocol_sha, "protocol SHA mismatch")
    protocol = object_at(protocol_path)
    check(protocol.get("protocol") == PROTOCOL_NAME, "protocol name mismatch")
    check(digest_file(receipt_path) == receipt_sha, "receipt SHA mismatch")
    receipt = object_at(receipt_path)
    check(receipt.get("protocol") == RECEIPT_PROTOCOL, "receipt protocol mismatch")
    check(receipt.get("status") == "OUTCOME_BLIND_TREE_LINEARIZATION_WEIGHT_AUDIT_COMPLETE", "receipt status mismatch")
    check(digest_file(producer_source) == producer_source_sha, "producer source SHA mismatch")
    check(re.fullmatch(r"[0-9a-f]{40}", source_commit) is not None, "invalid source commit")
    check(receipt.get("source_commit") == source_commit, "receipt source commit mismatch")
    check(receipt.get("producer_source_sha256") == producer_source_sha, "receipt producer source mismatch")
    check(receipt.get("protocol_sha256") == protocol_sha, "receipt protocol binding mismatch")
    check(receipt.get("snapshot_sha256") == protocol["fixed_snapshot"]["sha256"], "receipt snapshot mismatch")

    cards, _runs, bindings = collect_inputs(state_root, snapshot_root, protocol)
    expected = independently_reconstruct(cards, protocol)
    compare(bindings, receipt.get("input_bindings"), "input_bindings")
    for section in ("classification", "inventory", "linearization", "weighting", "pre_registered_gate"):
        compare(expected[section], receipt.get(section), section)
    compare(protocol["claim_boundary"], receipt.get("claim_boundary"), "claim_boundary")
    expected_security = {
        "allowed_input_basenames": protocol["security"]["allowed_input_basenames"],
        "raw_senior_archives_opened": False,
        "prospective_label_grade_outcome_prediction_values_read": False,
        "task_run_card_parent_or_code_values_emitted": False,
        "accuracy_effect_or_search_utility_computed": False,
        "gpu_api_model_fit_base_update": [0, 0, 0, 0],
    }
    compare(expected_security, receipt.get("security"), "security")
    return {
        "protocol": VERIFY_PROTOCOL,
        "status": "INDEPENDENT_TREE_LINEARIZATION_WEIGHT_AUDIT_PASS",
        "snapshot_sha256": protocol["fixed_snapshot"]["sha256"],
        "receipt_sha256": receipt_sha,
        "producer_source_sha256": producer_source_sha,
        "classification": expected["classification"],
        "observed_unique_edges": expected["inventory"]["observed_unique_edges"],
        "branch_linearized_edge_occurrences": expected["linearization"]["branch_linearized_edge_occurrences"],
        "all_hard_gates_passed": expected["pre_registered_gate"]["all_hard_gates_passed"],
        "checks": {
            "input_hashes_rechecked": True,
            "population_reconstructed": True,
            "graph_reconstructed_without_importing_producer": True,
            "edge_multiplicity_recomputed": True,
            "task_run_depth_weights_recomputed": True,
            "classification_recomputed": True,
            "identity_free_security_contract_exact": True,
        },
        "security": {
            "imports_producer": False,
            "prospective_label_grade_outcome_prediction_values_read": False,
            "task_run_card_parent_or_code_values_emitted": False,
            "gpu_api_model_fit_base_update": [0, 0, 0, 0],
        },
    }


def write_once(path: Path, value: dict[str, Any]) -> None:
    check(not path.exists(), "refusing to overwrite verifier output")
    check(path.parent.is_dir() and not path.parent.is_symlink(), "unsafe verifier output parent")
    temporary = path.with_name(path.name + f".tmp-{os.getpid()}")
    temporary.write_text(
        json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True, allow_nan=False) + "\n",
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
    parser.add_argument("--receipt", required=True, type=Path)
    parser.add_argument("--expect-receipt-sha256", required=True)
    parser.add_argument("--producer-source", required=True, type=Path)
    parser.add_argument("--expect-producer-source-sha256", required=True)
    parser.add_argument("--source-commit", required=True)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    try:
        result = verify(
            args.state_root,
            args.snapshot_root,
            args.protocol,
            args.expect_protocol_sha256,
            args.receipt,
            args.expect_receipt_sha256,
            args.producer_source,
            args.expect_producer_source_sha256,
            args.source_commit,
        )
        write_once(args.output.resolve(), result)
        print(json.dumps({
            "status": result["status"],
            "classification": result["classification"],
            "snapshot_sha256": result["snapshot_sha256"],
        }, sort_keys=True, separators=(",", ":")))
        return 0
    except (VerificationError, OSError, ValueError, KeyError, ZeroDivisionError) as error:
        print(f"TREE_LINEARIZATION_WEIGHT_VERIFY_ERROR: {error}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
