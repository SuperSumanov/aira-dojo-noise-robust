"""Independent verifier for the outcome-free TraceML structure audit.

This module intentionally does not import the producer.  It parses the fixed
branch identity with ``rsplit`` (rather than the producer's regular expression),
reconstructs the original graph, and checks every aggregate in the producer
receipt without reading score columns or source-code content.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import platform
import re
import statistics
import subprocess
import sys
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any, Iterable


PROTOCOL = "traceml-external-structure-eligibility-v1"
VERIFY_PROTOCOL = "independent-traceml-external-structure-eligibility-v1"
VERIFY_STATUS = "INDEPENDENT_TRACEML_EXTERNAL_STRUCTURE_AUDIT_VERIFIED"
REVISION = "61faec615b179f186dbe9c82ee59d17e14817e96"
OFFICIAL_RUNS = 13
MIN_RUNS = 8
MIN_TASKS = 4
MIN_PAIRS = 150
MAX_TASK_SHARE = 0.50
STATE_FIELDS = (
    "key_id",
    "version_number",
    "comp",
    "group",
    "depth",
    "orig_version_number",
    "is_agent",
    "raw_code_path",
)
ACTION_FIELDS = ("key_id", "v_old", "v_new", "comp", "group", "is_agent")
SECRET_SHAPE = re.compile(
    rb"(?:^|[^A-Za-z0-9])(?:sk-[A-Za-z0-9._-]{16,}|hf_[A-Za-z0-9]{16,}|"
    rb"gh[pousr]_[A-Za-z0-9]{16,}|AKIA[0-9A-Z]{16}|AIza[0-9A-Za-z_-]{30,}|"
    rb"Bearer[ \t]+[A-Za-z0-9._-]{20,}|-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----)"
)


class VerificationError(RuntimeError):
    """Fail-closed error in the independent implementation."""


def digest(path: Path) -> str:
    value = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            value.update(block)
    return value.hexdigest()


def canonical_json(value: Any) -> bytes:
    return (json.dumps(value, indent=2, sort_keys=True, ensure_ascii=False) + "\n").encode("utf-8")


def integer(value: Any) -> int | None:
    if value is None or isinstance(value, bool):
        return None
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    return int(number) if math.isfinite(number) and number == int(number) else None


def split_key(value: Any) -> tuple[str, int] | None:
    if not isinstance(value, str) or "__branch" not in value:
        return None
    prefix, suffix = value.rsplit("__branch", 1)
    if not prefix.startswith("mlev__run_") or not suffix or not suffix.isascii() or not suffix.isdigit():
        return None
    return prefix, int(suffix)


def mlevolve(row: dict[str, Any]) -> bool:
    return row.get("is_agent") is True and str(row.get("group", "")).casefold() == "mlevolve"


def scan_values(rows: Iterable[dict[str, Any]], fields: Iterable[str], label: str) -> None:
    for number, row in enumerate(rows, 1):
        for field in fields:
            value = row.get(field)
            if isinstance(value, str) and SECRET_SHAPE.search(value.encode("utf-8", errors="strict")):
                raise VerificationError(f"credential-shaped identity value: {label}:{number}:{field}")


def parquet_rows(path: Path, expected: str, fields: tuple[str, ...]) -> list[dict[str, Any]]:
    if digest(path) != expected:
        raise VerificationError(f"input SHA mismatch: {path.name}")
    try:
        import pyarrow.parquet as pq
    except ImportError as error:  # pragma: no cover - deployment dependency
        raise VerificationError("pyarrow is required") from error
    names = set(pq.read_schema(path).names)
    if not set(fields).issubset(names):
        raise VerificationError(f"identity schema mismatch: {path.name}")
    rows = pq.read_table(path, columns=list(fields)).to_pylist()
    scan_values(rows, fields, path.name)
    return rows


def no_cycle(nodes: set[int], edges: set[tuple[int, int]]) -> bool:
    adjacent: dict[int, set[int]] = defaultdict(set)
    for parent, child in edges:
        adjacent[parent].add(child)
    color = {node: 0 for node in nodes}

    def visit(node: int) -> bool:
        if color.get(node, 0) == 1:
            return False
        if color.get(node, 0) == 2:
            return True
        color[node] = 1
        if any(not visit(child) for child in sorted(adjacent.get(node, set()))):
            return False
        color[node] = 2
        return True

    return all(visit(node) for node in sorted(nodes) if color[node] == 0)


def spread(values: list[int]) -> dict[str, int | float | None]:
    if not values:
        return {"minimum": None, "median": None, "maximum": None}
    return {"minimum": min(values), "median": statistics.median(values), "maximum": max(values)}


def independently_aggregate(
    state_input: list[dict[str, Any]], action_input: list[dict[str, Any]]
) -> dict[str, Any]:
    states = [row for row in state_input if mlevolve(row)]
    actions = [row for row in action_input if mlevolve(row)]
    branch_keys = sorted({str(row.get("key_id")) for row in states})
    parsed = {key: split_key(key) for key in branch_keys}
    valid = {key: item for key, item in parsed.items() if item is not None}
    runs = sorted({item[0] for item in valid.values()})
    branch_numbers: dict[str, set[int]] = defaultdict(set)
    for run, number in valid.values():
        branch_numbers[run].add(number)

    state_index: dict[tuple[str, int], tuple[str, int, int, str]] = {}
    original_metadata: dict[tuple[str, int], list[tuple[int, str]]] = defaultdict(list)
    code_paths: dict[tuple[str, int], set[str]] = defaultdict(set)
    tasks_by_key: dict[str, set[str]] = defaultdict(set)
    duplicate_states = missing_version = missing_original = missing_depth = 0
    for row in states:
        key = str(row.get("key_id"))
        parsed_key = parsed.get(key)
        if parsed_key is None:
            continue
        run, _ = parsed_key
        version = integer(row.get("version_number"))
        original = integer(row.get("orig_version_number"))
        depth = integer(row.get("depth"))
        task = str(row.get("comp"))
        tasks_by_key[key].add(task)
        missing_version += version is None
        missing_original += original is None
        missing_depth += depth is None
        if version is None or original is None or depth is None:
            continue
        identity = (key, version)
        if identity in state_index:
            duplicate_states += 1
            continue
        state_index[identity] = (run, original, depth, task)
        original_metadata[(run, original)].append((depth, task))
        path = row.get("raw_code_path")
        if isinstance(path, str) and path:
            code_paths[(run, original)].add(path)

    action_keys = {str(row.get("key_id")) for row in actions}
    matching_action_keys = sum(split_key(key) is not None for key in action_keys)
    seen_actions: set[tuple[str, int, int]] = set()
    duplicate_actions = join_failures = identity_mismatches = joined_rows = 0
    unique_edges: dict[str, set[tuple[int, int]]] = defaultdict(set)
    depth_steps: Counter[int] = Counter()
    for row in actions:
        key = str(row.get("key_id"))
        old_number = integer(row.get("v_old"))
        new_number = integer(row.get("v_new"))
        if old_number is None or new_number is None:
            join_failures += 1
            continue
        action_identity = (key, old_number, new_number)
        duplicate_actions += action_identity in seen_actions
        seen_actions.add(action_identity)
        old = state_index.get((key, old_number))
        new = state_index.get((key, new_number))
        if old is None or new is None:
            join_failures += 1
            continue
        old_run, old_node, old_depth, old_task = old
        new_run, new_node, new_depth, new_task = new
        if old_run != new_run or old_task != new_task:
            identity_mismatches += 1
            continue
        joined_rows += 1
        unique_edges[old_run].add((old_node, new_node))
        depth_steps[new_depth - old_depth] += 1

    nodes: dict[str, set[int]] = defaultdict(set)
    task_sets_by_run: dict[str, set[str]] = defaultdict(set)
    for (run, node), values in original_metadata.items():
        nodes[run].add(node)
        task_sets_by_run[run].update(task for _depth, task in values)
    task_by_run = {
        run: next(iter(values)) for run, values in task_sets_by_run.items() if len(values) == 1
    }
    children: dict[tuple[str, int], set[int]] = defaultdict(set)
    parent_sets: dict[tuple[str, int], set[int]] = defaultdict(set)
    for run, edges in unique_edges.items():
        for parent, child in edges:
            children[(run, parent)].add(child)
            parent_sets[(run, child)].add(parent)
    sibling_sets = {key: value for key, value in children.items() if len(value) >= 2}
    pairs_by_task: Counter[str] = Counter()
    for (run, _), child_set in sibling_sets.items():
        pairs_by_task[task_by_run.get(run, "<ambiguous>")] += math.comb(len(child_set), 2)
    pair_count = sum(pairs_by_task.values())
    dominant_share = max(pairs_by_task.values()) / pair_count if pair_count else None

    metadata_conflicts = sum(len(set(values)) != 1 for values in original_metadata.values())
    code_conflicts = sum(len(values) > 1 for values in code_paths.values())
    multiple_parents = sum(len(values) > 1 for values in parent_sets.values())
    acyclic = all(no_cycle(nodes[run], unique_edges.get(run, set())) for run in runs)
    dedup_edges = sum(len(values) for values in unique_edges.values())
    mapping_checks = {
        "all_state_branch_keys_match": len(valid) == len(branch_keys),
        "all_action_branch_keys_match": matching_action_keys == len(action_keys),
        "physical_run_count_matches_official_13": len(runs) == OFFICIAL_RUNS,
        "branch_numbers_unique_within_run": sum(len(values) for values in branch_numbers.values())
        == len(branch_keys),
        "state_identity_unique": duplicate_states == 0,
        "action_identity_unique": duplicate_actions == 0,
        "state_original_node_complete": missing_version == 0
        and missing_original == 0
        and missing_depth == 0,
        "action_endpoint_join_complete": join_failures == 0,
        "action_endpoint_identity_consistent": identity_mismatches == 0,
        "one_task_per_branch": all(len(values) == 1 for values in tasks_by_key.values()),
        "original_node_metadata_consistent_across_branches": metadata_conflicts == 0,
        "direct_depth_increment_exactly_one": set(depth_steps) == {1},
        "each_child_has_at_most_one_parent": multiple_parents == 0,
        "all_physical_run_graphs_acyclic": acyclic,
    }
    mapping_passed = all(mapping_checks.values())
    originals = len(original_metadata)
    complete_code = originals > 0 and len(code_paths) == originals and code_conflicts == 0
    support_checks = {
        "mapping_passed": mapping_passed,
        "minimum_physical_runs": len(runs) >= MIN_RUNS,
        "minimum_pair_tasks": mapping_passed and len(pairs_by_task) >= MIN_TASKS,
        "minimum_finite_non_tie_pairs": False,
        "maximum_dominant_pair_task_share": mapping_passed
        and dominant_share is not None
        and dominant_share <= MAX_TASK_SHARE,
        "complete_unique_code_join": complete_code,
        "zero_overlap_with_local_corpora": False,
    }
    return {
        "identity": {
            "mlevolve_state_rows": len(states),
            "mlevolve_action_rows": len(actions),
            "branch_keys": len(branch_keys),
            "branch_keys_matching_fixed_regex": len(valid),
            "action_branch_keys": len(action_keys),
            "action_branch_keys_matching_fixed_regex": matching_action_keys,
            "physical_runs": len(runs),
            "tasks": len({task for values in tasks_by_key.values() for task in values}),
            "branches_per_physical_run": spread(sorted(len(values) for values in branch_numbers.values())),
            "duplicate_state_keys": duplicate_states,
            "duplicate_action_rows": duplicate_actions,
            "missing_version_rows": missing_version,
            "missing_orig_version_rows": missing_original,
            "missing_depth_rows": missing_depth,
            "key_comp_cardinality_not_one": sum(len(values) != 1 for values in tasks_by_key.values()),
            "original_nodes": originals,
            "original_node_metadata_conflicts": metadata_conflicts,
            "original_nodes_with_raw_code_path": len(code_paths),
            "raw_code_path_conflicts": code_conflicts,
        },
        "provisional_path_graph": {
            "action_edge_rows_joined": joined_rows,
            "action_endpoint_join_failures": join_failures,
            "action_endpoint_identity_mismatches": identity_mismatches,
            "deduplicated_path_adjacency_edges": dedup_edges,
            "duplicate_branch_edge_rows": joined_rows - dedup_edges,
            "edge_depth_delta_counts": {str(key): value for key, value in sorted(depth_steps.items())},
            "children_with_multiple_parents": multiple_parents,
            "all_physical_run_graphs_acyclic": acyclic,
            "provisional_sibling_parents": len(sibling_sets),
            "provisional_sibling_children": sum(len(values) for values in sibling_sets.values()),
            "provisional_path_adjacency_pairs": pair_count,
            "provisional_pair_task_counts": dict(sorted(pairs_by_task.items())),
            "provisional_dominant_pair_task_share": dominant_share,
            "canonical_direct_sibling_pairs": pair_count if mapping_passed else None,
        },
        "mapping_gate": {
            "checks": mapping_checks,
            "passed": mapping_passed,
            "status": "S0_STRUCTURAL_MAPPING_FIXED" if mapping_passed else "IDENTITY_OR_JOIN_AMBIGUOUS",
        },
        "external_replication_gate": {
            "thresholds": {
                "minimum_physical_runs": MIN_RUNS,
                "minimum_pair_tasks": MIN_TASKS,
                "minimum_finite_non_tie_pairs": MIN_PAIRS,
                "maximum_dominant_pair_task_share": MAX_TASK_SHARE,
                "complete_unique_code_join_required": True,
                "zero_overlap_required": True,
            },
            "checks": support_checks,
            "passed": all(support_checks.values()),
            "s1_score_support_not_run": True,
            "overlap_audit_not_run": True,
            "frozen_scorer_allowed": False,
            "status": "NOT_ELIGIBLE_S0_FAIL_CLOSED",
        },
    }


def object_file(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise VerificationError("producer result is not a JSON object")
    return value


def verify(args: argparse.Namespace) -> dict[str, Any]:
    repo = Path(__file__).resolve().parent.parent
    actual_commit = subprocess.check_output(
        ["git", "-C", str(repo), "rev-parse", "HEAD"], text=True
    ).strip()
    if actual_commit != args.source_commit:
        raise VerificationError("source commit mismatch")
    if subprocess.check_output(
        ["git", "-C", str(repo), "status", "--porcelain", "--untracked-files=all"], text=True
    ).strip():
        raise VerificationError("dirty verifier worktree")
    if args.revision != REVISION:
        raise VerificationError("revision mismatch")

    state_path = args.state.resolve(strict=True)
    action_path = args.action.resolve(strict=True)
    producer_source = args.producer_source.resolve(strict=True)
    producer_result_path = args.producer_result.resolve(strict=True)
    if digest(producer_result_path) != args.expect_producer_result_sha256:
        raise VerificationError("producer result SHA mismatch")
    result = object_file(producer_result_path)
    states = parquet_rows(state_path, args.expect_state_sha256, STATE_FIELDS)
    actions = parquet_rows(action_path, args.expect_action_sha256, ACTION_FIELDS)
    rebuilt = independently_aggregate(states, actions)
    expected_scope = {
        "score_columns_read": False,
        "finite_non_tie_outcomes_counted": False,
        "code_content_read": False,
        "raw_code_values_emitted": False,
        "identity_values_emitted": False,
        "prospective_outcomes_read": False,
        "credential_shaped_identity_values": 0,
    }
    checks = {
        "protocol": result.get("protocol") == PROTOCOL,
        "revision": result.get("revision") == REVISION,
        "inputs": result.get("inputs")
        == {"state_sha256": args.expect_state_sha256, "action_sha256": args.expect_action_sha256},
        "scope": result.get("scope") == expected_scope,
        "identity": result.get("identity") == rebuilt["identity"],
        "provisional_path_graph": result.get("provisional_path_graph")
        == rebuilt["provisional_path_graph"],
        "mapping_gate": result.get("mapping_gate") == rebuilt["mapping_gate"],
        "external_replication_gate": result.get("external_replication_gate")
        == rebuilt["external_replication_gate"],
        "source_commit": result.get("reproducibility", {}).get("source_commit") == actual_commit,
        "producer_source_sha256": result.get("reproducibility", {}).get("source_sha256")
        == digest(producer_source),
        "randomness_unused": result.get("reproducibility", {}).get("randomness_used") is False,
    }
    if not all(checks.values()):
        raise VerificationError(
            "independent aggregate mismatch: "
            + ",".join(name for name, passed in checks.items() if not passed)
        )
    return {
        "protocol": VERIFY_PROTOCOL,
        "status": VERIFY_STATUS,
        "revision": REVISION,
        "source_commit": actual_commit,
        "inputs": {
            "state_sha256": args.expect_state_sha256,
            "action_sha256": args.expect_action_sha256,
            "producer_result_sha256": args.expect_producer_result_sha256,
            "producer_source_sha256": digest(producer_source),
        },
        "verification": checks,
        "observed": {
            "physical_runs": rebuilt["identity"]["physical_runs"],
            "branch_keys": rebuilt["identity"]["branch_keys"],
            "deduplicated_path_adjacency_edges": rebuilt["provisional_path_graph"][
                "deduplicated_path_adjacency_edges"
            ],
            "skipped_depth_adjacencies": sum(
                value
                for key, value in rebuilt["provisional_path_graph"]["edge_depth_delta_counts"].items()
                if key != "1"
            ),
            "provisional_path_adjacency_pairs": rebuilt["provisional_path_graph"][
                "provisional_path_adjacency_pairs"
            ],
            "mapping_passed": rebuilt["mapping_gate"]["passed"],
            "external_replication_gate_passed": rebuilt["external_replication_gate"]["passed"],
        },
        "scope": {
            "score_columns_read": False,
            "code_content_read": False,
            "identity_values_emitted": False,
            "prospective_outcomes_read": False,
            "producer_imported": False,
        },
        "reproducibility": {
            "python_version": platform.python_version(),
            "randomness_used": False,
            "verifier_source_sha256": digest(Path(__file__).resolve()),
        },
    }


def arguments() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--state", required=True, type=Path)
    parser.add_argument("--expect-state-sha256", required=True)
    parser.add_argument("--action", required=True, type=Path)
    parser.add_argument("--expect-action-sha256", required=True)
    parser.add_argument("--revision", required=True)
    parser.add_argument("--source-commit", required=True)
    parser.add_argument("--producer-source", required=True, type=Path)
    parser.add_argument("--producer-result", required=True, type=Path)
    parser.add_argument("--expect-producer-result-sha256", required=True)
    parser.add_argument("--output", required=True, type=Path)
    return parser.parse_args()


def main() -> int:
    args = arguments()
    if args.output.exists():
        print("TRACEML_STRUCTURE_VERIFY_ERROR: output exists", file=sys.stderr)
        return 2
    try:
        receipt = verify(args)
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_bytes(canonical_json(receipt))
    except (
        VerificationError,
        OSError,
        ValueError,
        json.JSONDecodeError,
        subprocess.CalledProcessError,
    ) as error:
        print(f"TRACEML_STRUCTURE_VERIFY_ERROR: {error}", file=sys.stderr)
        return 1
    print(
        VERIFY_STATUS,
        f"runs={receipt['observed']['physical_runs']}",
        f"skipped_depth={receipt['observed']['skipped_depth_adjacencies']}",
        "outcomes_read=false",
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
