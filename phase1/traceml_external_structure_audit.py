"""Outcome-free TraceML paired-agent structure eligibility audit.

This audit reads only identity/provenance columns from a fixed TraceML release.
It never reads score columns or source-code content.  MLEvolve branch keys are
mapped to physical runs by the pre-registered ``<run>__branch<N>`` convention;
the resulting path adjacency is accepted as a direct tree edge only when every
edge advances original depth by exactly one and the reconstructed graph is a
tree within each physical run.
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
from collections import Counter, defaultdict, deque
from pathlib import Path
from typing import Any, Iterable


PROTOCOL = "traceml-external-structure-eligibility-v1"
FIXED_REVISION = "61faec615b179f186dbe9c82ee59d17e14817e96"
EXPECTED_MLEVOLVE_PHYSICAL_RUNS = 13
MINIMUM_PHYSICAL_RUNS = 8
MINIMUM_PAIR_TASKS = 4
MINIMUM_FINITE_NON_TIE_PAIRS = 150
MAXIMUM_DOMINANT_PAIR_TASK_SHARE = 0.50
BRANCH_PATTERN = re.compile(r"^(?P<run>mlev__run_.+)__branch(?P<branch>[0-9]+)$")
CREDENTIAL = re.compile(
    rb"(?:^|[^A-Za-z0-9])(?:sk-[A-Za-z0-9._-]{16,}|hf_[A-Za-z0-9]{16,}|"
    rb"gh[pousr]_[A-Za-z0-9]{16,}|AKIA[0-9A-Z]{16}|AIza[0-9A-Za-z_-]{30,}|"
    rb"Bearer[ \t]+[A-Za-z0-9._-]{20,}|-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----)"
)
STATE_COLUMNS = (
    "key_id",
    "version_number",
    "comp",
    "group",
    "depth",
    "orig_version_number",
    "is_agent",
    "raw_code_path",
)
ACTION_COLUMNS = ("key_id", "v_old", "v_new", "comp", "group", "is_agent")


class AuditError(RuntimeError):
    """Raised when a fixed input or structural invariant is malformed."""


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1 << 20), b""):
            digest.update(block)
    return digest.hexdigest()


def canonical_json(value: Any) -> bytes:
    return (json.dumps(value, indent=2, sort_keys=True, ensure_ascii=False) + "\n").encode("utf-8")


def exact_int(value: Any) -> int | None:
    if value is None:
        return None
    if isinstance(value, bool):
        return None
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    if not math.isfinite(number) or not number.is_integer():
        return None
    return int(number)


def parse_branch_key(value: Any) -> tuple[str, int] | None:
    if not isinstance(value, str):
        return None
    match = BRANCH_PATTERN.fullmatch(value)
    if match is None:
        return None
    return match.group("run"), int(match.group("branch"))


def scan_identity_values(rows: Iterable[dict[str, Any]], columns: Iterable[str], label: str) -> None:
    for row_number, row in enumerate(rows, 1):
        for column in columns:
            value = row.get(column)
            if isinstance(value, str) and CREDENTIAL.search(value.encode("utf-8", errors="strict")):
                raise AuditError(f"credential-shaped identity value: {label}:{row_number}:{column}")


def read_identity_rows(path: Path, expected_sha256: str, columns: tuple[str, ...]) -> list[dict[str, Any]]:
    if sha256_file(path) != expected_sha256:
        raise AuditError(f"SHA mismatch: {path.name}")
    try:
        import pyarrow.parquet as pq
    except ImportError as error:  # pragma: no cover - deployment dependency
        raise AuditError("pyarrow is required for TraceML parquet audit") from error
    schema = pq.read_schema(path)
    missing = sorted(set(columns) - set(schema.names))
    if missing:
        raise AuditError(f"missing columns in {path.name}: {missing}")
    rows = pq.read_table(path, columns=list(columns)).to_pylist()
    scan_identity_values(rows, columns, path.name)
    return rows


def is_mlevolve(row: dict[str, Any]) -> bool:
    return row.get("is_agent") is True and str(row.get("group", "")).lower() == "mlevolve"


def acyclic(nodes: set[int], edges: set[tuple[int, int]]) -> bool:
    children: dict[int, set[int]] = defaultdict(set)
    indegree = {node: 0 for node in nodes}
    for parent, child in edges:
        if child in children[parent]:
            continue
        children[parent].add(child)
        indegree.setdefault(parent, 0)
        indegree[child] = indegree.get(child, 0) + 1
    queue = deque(sorted(node for node, degree in indegree.items() if degree == 0))
    visited = 0
    while queue:
        node = queue.popleft()
        visited += 1
        for child in sorted(children.get(node, ())):
            indegree[child] -= 1
            if indegree[child] == 0:
                queue.append(child)
    return visited == len(indegree)


def distribution(values: list[int]) -> dict[str, int | float | None]:
    if not values:
        return {"minimum": None, "median": None, "maximum": None}
    return {
        "minimum": min(values),
        "median": statistics.median(values),
        "maximum": max(values),
    }


def audit_identity_rows(
    state_rows: list[dict[str, Any]], action_rows: list[dict[str, Any]]
) -> dict[str, Any]:
    state = [row for row in state_rows if is_mlevolve(row)]
    actions = [row for row in action_rows if is_mlevolve(row)]
    keys = sorted({str(row.get("key_id")) for row in state})
    parsed = {key: parse_branch_key(key) for key in keys}
    matched = {key: value for key, value in parsed.items() if value is not None}
    physical_runs = sorted({value[0] for value in matched.values()})
    branches_by_run: dict[str, set[int]] = defaultdict(set)
    for run, branch in matched.values():
        branches_by_run[run].add(branch)

    duplicate_state_keys = 0
    lookup: dict[tuple[str, int], tuple[str, int, int, str]] = {}
    node_metadata: dict[tuple[str, int], set[tuple[int, str]]] = defaultdict(set)
    node_code_paths: dict[tuple[str, int], set[str]] = defaultdict(set)
    key_comp_values: dict[str, set[str]] = defaultdict(set)
    missing_orig = 0
    missing_depth = 0
    missing_version = 0
    for row in state:
        key = str(row.get("key_id"))
        parsed_key = parsed.get(key)
        if parsed_key is None:
            continue
        run, _branch = parsed_key
        version = exact_int(row.get("version_number"))
        original = exact_int(row.get("orig_version_number"))
        depth = exact_int(row.get("depth"))
        task = str(row.get("comp"))
        key_comp_values[key].add(task)
        missing_version += version is None
        missing_orig += original is None
        missing_depth += depth is None
        if version is None or original is None or depth is None:
            continue
        lookup_key = (key, version)
        if lookup_key in lookup:
            duplicate_state_keys += 1
            continue
        lookup[lookup_key] = (run, original, depth, task)
        node_key = (run, original)
        node_metadata[node_key].add((depth, task))
        code_path = row.get("raw_code_path")
        if isinstance(code_path, str) and code_path:
            node_code_paths[node_key].add(code_path)

    action_key_set = {str(row.get("key_id")) for row in actions}
    action_keys_matching = sum(parse_branch_key(key) is not None for key in action_key_set)
    edge_rows = 0
    duplicate_action_rows = 0
    seen_action_rows: set[tuple[str, int, int]] = set()
    endpoint_join_failures = 0
    endpoint_identity_mismatches = 0
    edges_by_run: dict[str, set[tuple[int, int]]] = defaultdict(set)
    depth_delta = Counter()
    for row in actions:
        key = str(row.get("key_id"))
        old_version = exact_int(row.get("v_old"))
        new_version = exact_int(row.get("v_new"))
        if old_version is None or new_version is None:
            endpoint_join_failures += 1
            continue
        action_key = (key, old_version, new_version)
        if action_key in seen_action_rows:
            duplicate_action_rows += 1
        seen_action_rows.add(action_key)
        old = lookup.get((key, old_version))
        new = lookup.get((key, new_version))
        if old is None or new is None:
            endpoint_join_failures += 1
            continue
        old_run, old_original, old_depth, old_task = old
        new_run, new_original, new_depth, new_task = new
        if old_run != new_run or old_task != new_task:
            endpoint_identity_mismatches += 1
            continue
        edge_rows += 1
        edges_by_run[old_run].add((old_original, new_original))
        depth_delta[new_depth - old_depth] += 1

    nodes_by_run: dict[str, set[int]] = defaultdict(set)
    task_values_by_run: dict[str, set[str]] = defaultdict(set)
    for (run, node), metadata in node_metadata.items():
        nodes_by_run[run].add(node)
        task_values_by_run[run].update(task for _depth, task in metadata)
    task_by_run = {
        run: next(iter(tasks)) for run, tasks in task_values_by_run.items() if len(tasks) == 1
    }

    children_by_parent: dict[tuple[str, int], set[int]] = defaultdict(set)
    parents_by_child: dict[tuple[str, int], set[int]] = defaultdict(set)
    for run, edges in edges_by_run.items():
        for parent, child in edges:
            children_by_parent[(run, parent)].add(child)
            parents_by_child[(run, child)].add(parent)
    sibling_parents = {
        key: children for key, children in children_by_parent.items() if len(children) >= 2
    }
    provisional_pair_tasks = Counter()
    for (run, _parent), children in sibling_parents.items():
        provisional_pair_tasks[task_by_run.get(run, "<ambiguous>")] += (
            len(children) * (len(children) - 1) // 2
        )
    provisional_pairs = sum(provisional_pair_tasks.values())
    provisional_dominant_share = (
        max(provisional_pair_tasks.values()) / provisional_pairs if provisional_pairs else None
    )

    branch_counts = sorted(len(values) for values in branches_by_run.values())
    deduplicated_edges = sum(len(edges) for edges in edges_by_run.values())
    metadata_conflicts = sum(len(values) != 1 for values in node_metadata.values())
    code_path_conflicts = sum(len(values) > 1 for values in node_code_paths.values())
    children_with_multiple_parents = sum(len(values) > 1 for values in parents_by_child.values())
    all_runs_acyclic = all(
        acyclic(nodes_by_run[run], edges_by_run.get(run, set())) for run in physical_runs
    )
    mapping_checks = {
        "all_state_branch_keys_match": len(matched) == len(keys),
        "all_action_branch_keys_match": action_keys_matching == len(action_key_set),
        "physical_run_count_matches_official_13": len(physical_runs)
        == EXPECTED_MLEVOLVE_PHYSICAL_RUNS,
        "branch_numbers_unique_within_run": sum(len(values) for values in branches_by_run.values())
        == len(keys),
        "state_identity_unique": duplicate_state_keys == 0,
        "action_identity_unique": duplicate_action_rows == 0,
        "state_original_node_complete": missing_version == 0 and missing_orig == 0 and missing_depth == 0,
        "action_endpoint_join_complete": endpoint_join_failures == 0,
        "action_endpoint_identity_consistent": endpoint_identity_mismatches == 0,
        "one_task_per_branch": all(len(values) == 1 for values in key_comp_values.values()),
        "original_node_metadata_consistent_across_branches": metadata_conflicts == 0,
        "direct_depth_increment_exactly_one": set(depth_delta) == {1},
        "each_child_has_at_most_one_parent": children_with_multiple_parents == 0,
        "all_physical_run_graphs_acyclic": all_runs_acyclic,
    }
    mapping_passed = all(mapping_checks.values())

    original_nodes = len(node_metadata)
    nodes_with_code_path = len(node_code_paths)
    code_join_complete = (
        original_nodes > 0 and nodes_with_code_path == original_nodes and code_path_conflicts == 0
    )
    pair_tasks = len(provisional_pair_tasks)
    support_checks = {
        "mapping_passed": mapping_passed,
        "minimum_physical_runs": len(physical_runs) >= MINIMUM_PHYSICAL_RUNS,
        "minimum_pair_tasks": mapping_passed and pair_tasks >= MINIMUM_PAIR_TASKS,
        "minimum_finite_non_tie_pairs": False,
        "maximum_dominant_pair_task_share": mapping_passed
        and provisional_dominant_share is not None
        and provisional_dominant_share <= MAXIMUM_DOMINANT_PAIR_TASK_SHARE,
        "complete_unique_code_join": code_join_complete,
        "zero_overlap_with_local_corpora": False,
    }

    return {
        "protocol": PROTOCOL,
        "revision": FIXED_REVISION,
        "scope": {
            "score_columns_read": False,
            "finite_non_tie_outcomes_counted": False,
            "code_content_read": False,
            "raw_code_values_emitted": False,
            "identity_values_emitted": False,
            "prospective_outcomes_read": False,
            "credential_shaped_identity_values": 0,
        },
        "identity": {
            "mlevolve_state_rows": len(state),
            "mlevolve_action_rows": len(actions),
            "branch_keys": len(keys),
            "branch_keys_matching_fixed_regex": len(matched),
            "action_branch_keys": len(action_key_set),
            "action_branch_keys_matching_fixed_regex": action_keys_matching,
            "physical_runs": len(physical_runs),
            "tasks": len({task for values in key_comp_values.values() for task in values}),
            "branches_per_physical_run": distribution(branch_counts),
            "duplicate_state_keys": duplicate_state_keys,
            "duplicate_action_rows": duplicate_action_rows,
            "missing_version_rows": missing_version,
            "missing_orig_version_rows": missing_orig,
            "missing_depth_rows": missing_depth,
            "key_comp_cardinality_not_one": sum(len(values) != 1 for values in key_comp_values.values()),
            "original_nodes": original_nodes,
            "original_node_metadata_conflicts": metadata_conflicts,
            "original_nodes_with_raw_code_path": nodes_with_code_path,
            "raw_code_path_conflicts": code_path_conflicts,
        },
        "provisional_path_graph": {
            "action_edge_rows_joined": edge_rows,
            "action_endpoint_join_failures": endpoint_join_failures,
            "action_endpoint_identity_mismatches": endpoint_identity_mismatches,
            "deduplicated_path_adjacency_edges": deduplicated_edges,
            "duplicate_branch_edge_rows": edge_rows - deduplicated_edges,
            "edge_depth_delta_counts": {str(key): value for key, value in sorted(depth_delta.items())},
            "children_with_multiple_parents": children_with_multiple_parents,
            "all_physical_run_graphs_acyclic": all_runs_acyclic,
            "provisional_sibling_parents": len(sibling_parents),
            "provisional_sibling_children": sum(len(values) for values in sibling_parents.values()),
            "provisional_path_adjacency_pairs": provisional_pairs,
            "provisional_pair_task_counts": dict(sorted(provisional_pair_tasks.items())),
            "provisional_dominant_pair_task_share": provisional_dominant_share,
            "canonical_direct_sibling_pairs": provisional_pairs if mapping_passed else None,
        },
        "mapping_gate": {
            "checks": mapping_checks,
            "passed": mapping_passed,
            "status": "S0_STRUCTURAL_MAPPING_FIXED" if mapping_passed else "IDENTITY_OR_JOIN_AMBIGUOUS",
        },
        "external_replication_gate": {
            "thresholds": {
                "minimum_physical_runs": MINIMUM_PHYSICAL_RUNS,
                "minimum_pair_tasks": MINIMUM_PAIR_TASKS,
                "minimum_finite_non_tie_pairs": MINIMUM_FINITE_NON_TIE_PAIRS,
                "maximum_dominant_pair_task_share": MAXIMUM_DOMINANT_PAIR_TASK_SHARE,
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


def audit(args: argparse.Namespace) -> dict[str, Any]:
    if args.revision != FIXED_REVISION:
        raise AuditError("TraceML revision is not the pre-registered revision")
    repo = Path(__file__).resolve().parent.parent
    actual_commit = subprocess.check_output(
        ["git", "-C", str(repo), "rev-parse", "HEAD"], text=True
    ).strip()
    if actual_commit != args.source_commit:
        raise AuditError("source commit does not match the executing worktree")
    if subprocess.check_output(
        ["git", "-C", str(repo), "status", "--porcelain", "--untracked-files=all"],
        text=True,
    ).strip():
        raise AuditError("refusing to audit from a dirty worktree")
    state_path = args.state.resolve(strict=True)
    action_path = args.action.resolve(strict=True)
    state_rows = read_identity_rows(state_path, args.expect_state_sha256, STATE_COLUMNS)
    action_rows = read_identity_rows(action_path, args.expect_action_sha256, ACTION_COLUMNS)
    result = audit_identity_rows(state_rows, action_rows)
    result["inputs"] = {
        "state_sha256": args.expect_state_sha256,
        "action_sha256": args.expect_action_sha256,
    }
    try:
        import pyarrow

        pyarrow_version = pyarrow.__version__
    except ImportError:  # pragma: no cover
        pyarrow_version = None
    result["reproducibility"] = {
        "source_commit": actual_commit,
        "python_version": platform.python_version(),
        "pyarrow_version": pyarrow_version,
        "randomness_used": False,
        "source_sha256": sha256_file(Path(__file__).resolve()),
    }
    return result


def arguments() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--state", required=True, type=Path)
    parser.add_argument("--expect-state-sha256", required=True)
    parser.add_argument("--action", required=True, type=Path)
    parser.add_argument("--expect-action-sha256", required=True)
    parser.add_argument("--revision", required=True)
    parser.add_argument("--source-commit", required=True)
    parser.add_argument("--output", required=True, type=Path)
    return parser.parse_args()


def main() -> int:
    args = arguments()
    if args.output.exists():
        print("TRACEML_STRUCTURE_AUDIT_ERROR: output exists")
        return 2
    try:
        result = audit(args)
    except (AuditError, OSError, ValueError) as error:
        print(f"TRACEML_STRUCTURE_AUDIT_ERROR: {error}")
        return 1
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_bytes(canonical_json(result))
    print(
        "TRACEML_STRUCTURE_AUDIT_COMPLETE",
        f"runs={result['identity']['physical_runs']}",
        f"provisional_pairs={result['provisional_path_graph']['provisional_path_adjacency_pairs']}",
        f"mapping_passed={str(result['mapping_gate']['passed']).lower()}",
        "scores_read=false",
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
