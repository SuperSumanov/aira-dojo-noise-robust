"""Pre-registered S1 support audit for TraceML canonical human forks.

This stage reads graph identity plus aggregate score availability.  It never
reads notebook content, emits row-level outcomes, or evaluates a predictor.
Raw notebooks remain forbidden until this audit's fixed gates pass.
"""

from __future__ import annotations

import argparse
import hashlib
import itertools
import json
import math
import re
import subprocess
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any, Iterable


PROTOCOL = "traceml-human-fork-future-s1-support-v1"
FIXED_REVISION = "61faec615b179f186dbe9c82ee59d17e14817e96"
MIN_TASKS = 20
MIN_PARENTS = 100
MIN_FINITE_NONTIE_PAIRS = 500
MAX_DOMINANT_SHARE = 0.20
SOURCE_PATHS = (
    "phase1/traceml_human_fork_s1_support.py",
    "phase1/verify_traceml_human_fork_s1_support.py",
    "phase1/scripts/run_traceml_human_fork_s1_20260821.sh",
    "phase1/traceml_human_fork_future_protocol_v1.json",
    "phase1/traceml_human_fork_s0_input_manifest.json",
)
NODE_ID_COLUMNS = (
    "node_id",
    "tree_id",
    "comp",
    "kernel_id",
    "version_id",
    "version_in_kernel",
    "depth",
    "parent_id",
    "edge_kind",
    "score_is_max",
    "raw_code_path",
)
KERNEL_ID_COLUMNS = ("kernel_id", "comp", "score_is_max", "raw_dir")
TREE_ID_COLUMNS = ("tree_id", "comp")
CREDENTIAL = re.compile(
    rb"(?:^|[^A-Za-z0-9])(?:sk-[A-Za-z0-9._-]{16,}|hf_[A-Za-z0-9]{16,}|"
    rb"gh[pousr]_[A-Za-z0-9]{16,}|AKIA[0-9A-Z]{16}|AIza[0-9A-Za-z_-]{30,}|"
    rb"Bearer[ \t]+[A-Za-z0-9._-]{20,}|-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----)"
)


class AuditError(RuntimeError):
    """Raised when a fixed input or contract is malformed."""


def canonical_json(value: Any) -> bytes:
    return (json.dumps(value, indent=2, sort_keys=True, ensure_ascii=False) + "\n").encode("utf-8")


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1 << 20), b""):
            digest.update(block)
    return digest.hexdigest()


def require(condition: bool, message: str) -> None:
    if not condition:
        raise AuditError(message)


def exact_int(value: Any) -> int | None:
    if value is None or isinstance(value, bool):
        return None
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    return int(number) if math.isfinite(number) and number.is_integer() else None


def finite_float(value: Any) -> float | None:
    if value is None or isinstance(value, bool):
        return None
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    return number if math.isfinite(number) else None


def nonempty_text(value: Any) -> str | None:
    return value if isinstance(value, str) and value else None


def scan_values(rows: Iterable[dict[str, Any]], columns: Iterable[str], label: str) -> None:
    for row_number, row in enumerate(rows, 1):
        for column in columns:
            value = row.get(column)
            if isinstance(value, str) and CREDENTIAL.search(value.encode("utf-8", errors="strict")):
                raise AuditError(f"credential-shaped identity value: {label}:{row_number}:{column}")


def read_json_no_duplicates(path: Path) -> Any:
    def checked(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
        output: dict[str, Any] = {}
        for key, value in pairs:
            if key in output:
                raise AuditError(f"duplicate JSON key in {path.name}")
            output[key] = value
        return output

    return json.loads(path.read_text(encoding="utf-8"), object_pairs_hook=checked)


def read_jsonl_tasks(path: Path) -> set[str]:
    tasks: set[str] = set()
    with path.open("r", encoding="utf-8") as handle:
        for line_number, line in enumerate(handle, 1):
            if not line.strip():
                continue
            row = json.loads(line)
            task = nonempty_text(row.get("task"))
            require(task is not None, f"missing training task: {path.name}:{line_number}")
            if CREDENTIAL.search(task.encode("utf-8")):
                raise AuditError(f"credential-shaped training task: {path.name}:{line_number}")
            tasks.add(task)
    require(bool(tasks), f"no tasks in {path.name}")
    return tasks


def git_output(repo_root: Path, *arguments: str) -> str:
    result = subprocess.run(
        ["git", "-C", str(repo_root), *arguments],
        check=True,
        capture_output=True,
        text=True,
    )
    return result.stdout.strip()


def bind_source(repo_root: Path, source_commit: str) -> dict[str, str]:
    require(git_output(repo_root, "rev-parse", "HEAD") == source_commit, "HEAD/source commit mismatch")
    hashes: dict[str, str] = {}
    for relative in SOURCE_PATHS:
        worktree_blob = git_output(repo_root, "hash-object", relative)
        committed_blob = git_output(repo_root, "rev-parse", f"{source_commit}:{relative}")
        require(worktree_blob == committed_blob, f"registered source differs from commit: {relative}")
        hashes[relative] = sha256_file(repo_root / relative)
    return hashes


def load_parquet(path: Path, columns: tuple[str, ...]) -> list[dict[str, Any]]:
    try:
        import pyarrow.parquet as pq
    except ImportError as error:  # pragma: no cover - deployment dependency
        raise AuditError("pyarrow is required") from error
    schema = pq.read_schema(path)
    missing = sorted(set(columns) - set(schema.names))
    require(not missing, f"missing columns in {path.name}: {missing}")
    return pq.read_table(path, columns=list(columns)).to_pylist()


def selected_edge_counts(path: Path, selected: set[tuple[str, str, str]]) -> dict[tuple[str, str, str], int]:
    try:
        import pyarrow.parquet as pq
    except ImportError as error:  # pragma: no cover - deployment dependency
        raise AuditError("pyarrow is required") from error
    schema = pq.read_schema(path)
    required = ("parent_id", "child_id", "edge_kind")
    require(set(required).issubset(schema.names), "edge schema missing identity columns")
    counts: Counter[tuple[str, str, str]] = Counter()
    parquet = pq.ParquetFile(path)
    for batch in parquet.iter_batches(batch_size=65536, columns=list(required)):
        for parent, child, kind in zip(*(batch.column(i).to_pylist() for i in range(3))):
            values = (parent, child, kind)
            for value in values:
                if isinstance(value, str) and CREDENTIAL.search(value.encode("utf-8")):
                    raise AuditError("credential-shaped edge identity value")
            if all(isinstance(value, str) for value in values) and values in selected:
                counts[values] += 1
    return dict(counts)


def normalize_manifest(manifest: Any) -> tuple[dict[str, bool], list[str]]:
    require(isinstance(manifest, dict) and manifest, "competition manifest is not a mapping")
    directions: dict[str, bool] = {}
    malformed: list[str] = []
    for comp, metadata in manifest.items():
        direction = metadata.get("score_direction") if isinstance(metadata, dict) else None
        if not isinstance(comp, str) or not comp or direction not in ("higher", "lower"):
            malformed.append(str(comp))
            continue
        directions[comp] = direction == "higher"
    return directions, sorted(malformed)


def identity_audit(
    nodes: list[dict[str, Any]],
    kernels: list[dict[str, Any]],
    trees: list[dict[str, Any]],
    manifest: Any,
    edge_counts: dict[tuple[str, str, str], int] | None = None,
) -> tuple[dict[str, Any], dict[str, Any]]:
    """Audit graph identity and return private indexes for support aggregation."""

    scan_values(nodes, ("node_id", "tree_id", "comp", "parent_id", "edge_kind", "raw_code_path"), "nodes")
    scan_values(kernels, ("comp", "raw_dir"), "kernels")
    scan_values(trees, ("tree_id", "comp"), "trees")
    directions, malformed_manifest = normalize_manifest(manifest)

    node_ids = [nonempty_text(row.get("node_id")) for row in nodes]
    kernel_ids = [exact_int(row.get("kernel_id")) for row in kernels]
    tree_ids = [nonempty_text(row.get("tree_id")) for row in trees]
    node_counter = Counter(value for value in node_ids if value is not None)
    kernel_counter = Counter(value for value in kernel_ids if value is not None)
    tree_counter = Counter(value for value in tree_ids if value is not None)
    node_index = {
        value: row for value, row in zip(node_ids, nodes) if value is not None and node_counter[value] == 1
    }
    kernel_index = {
        value: row for value, row in zip(kernel_ids, kernels) if value is not None and kernel_counter[value] == 1
    }
    tree_index = {
        value: row for value, row in zip(tree_ids, trees) if value is not None and tree_counter[value] == 1
    }

    graph_comps = {
        comp
        for rows in (nodes, kernels, trees)
        for row in rows
        if (comp := nonempty_text(row.get("comp"))) is not None
    }
    missing_manifest = sorted(graph_comps - set(directions))
    unused_manifest = sorted(set(directions) - graph_comps)

    counts = Counter()
    counts["missing_node_id"] = sum(value is None for value in node_ids)
    counts["duplicate_node_id"] = sum(count - 1 for count in node_counter.values() if count > 1)
    counts["missing_kernel_id"] = sum(value is None for value in kernel_ids)
    counts["duplicate_kernel_id"] = sum(count - 1 for count in kernel_counter.values() if count > 1)
    counts["missing_tree_id"] = sum(value is None for value in tree_ids)
    counts["duplicate_tree_id"] = sum(count - 1 for count in tree_counter.values() if count > 1)

    for row in kernels:
        comp = nonempty_text(row.get("comp"))
        expected = directions.get(comp or "")
        if comp is None:
            counts["kernel_missing_comp"] += 1
        if not isinstance(row.get("score_is_max"), bool) or expected is None or row.get("score_is_max") != expected:
            counts["kernel_direction_mismatch"] += 1
    for row in trees:
        if nonempty_text(row.get("comp")) is None:
            counts["tree_missing_comp"] += 1

    candidates: list[dict[str, Any]] = []
    for row in nodes:
        node_id = nonempty_text(row.get("node_id"))
        tree_id = nonempty_text(row.get("tree_id"))
        comp = nonempty_text(row.get("comp"))
        kernel_id = exact_int(row.get("kernel_id"))
        expected = directions.get(comp or "")
        if comp is None:
            counts["node_missing_comp"] += 1
        if not isinstance(row.get("score_is_max"), bool) or expected is None or row.get("score_is_max") != expected:
            counts["node_direction_mismatch"] += 1
        kernel = kernel_index.get(kernel_id) if kernel_id is not None else None
        if kernel is None or kernel.get("comp") != comp:
            counts["node_kernel_join_mismatch"] += 1
        tree = tree_index.get(tree_id or "")
        if tree is None or tree.get("comp") != comp:
            counts["node_tree_join_mismatch"] += 1
        if row.get("edge_kind") != "fork":
            continue
        counts["canonical_fork_nodes"] += 1
        parent_id = nonempty_text(row.get("parent_id"))
        parent = node_index.get(parent_id or "")
        valid = True
        if node_id is None or node_counter.get(node_id) != 1 or parent is None:
            counts["fork_parent_join_mismatch"] += 1
            valid = False
        if exact_int(row.get("version_in_kernel")) != 1:
            counts["fork_not_first_kernel_version"] += 1
            valid = False
        if parent is not None:
            if parent.get("tree_id") != tree_id or parent.get("comp") != comp:
                counts["fork_parent_tree_comp_mismatch"] += 1
                valid = False
            child_depth = exact_int(row.get("depth"))
            parent_depth = exact_int(parent.get("depth"))
            if child_depth is None or parent_depth is None or child_depth != parent_depth + 1:
                counts["fork_depth_delta_mismatch"] += 1
                valid = False
            if exact_int(parent.get("kernel_id")) == kernel_id:
                counts["fork_same_kernel_as_parent"] += 1
                valid = False
        if valid:
            candidates.append(
                {
                    "node_id": node_id,
                    "parent_id": parent_id,
                    "tree_id": tree_id,
                    "comp": comp,
                    "kernel_id": kernel_id,
                    "raw_code_path": nonempty_text(row.get("raw_code_path")),
                    "parent_raw_code_path": nonempty_text(parent.get("raw_code_path")),
                }
            )

    selected_edges = {(row["parent_id"], row["node_id"], "fork") for row in candidates}
    if edge_counts is not None:
        counts["fork_edge_table_multiplicity_mismatch"] = sum(
            edge_counts.get(edge, 0) != 1 for edge in selected_edges
        )

    by_parent: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for candidate in candidates:
        by_parent[candidate["parent_id"]].append(candidate)
    for children in by_parent.values():
        kernel_count = Counter(child["kernel_id"] for child in children)
        counts["fork_child_kernel_duplicate_within_parent"] += sum(
            count - 1 for count in kernel_count.values() if count > 1
        )
    global_child_kernels = Counter(child["kernel_id"] for child in candidates)
    counts["fork_child_kernel_duplicate_global"] = sum(
        count - 1 for count in global_child_kernels.values() if count > 1
    )

    fatal_count_names = [
        name
        for name in counts
        if name not in ("canonical_fork_nodes",) and counts[name] != 0
    ]
    identity_pass = not malformed_manifest and not missing_manifest and not fatal_count_names
    public = {
        "counts": dict(sorted(counts.items())),
        "graph_competitions": len(graph_comps),
        "identity_pass": identity_pass,
        "malformed_manifest_entries": len(malformed_manifest),
        "manifest_entries": len(directions),
        "missing_manifest_entries": len(missing_manifest),
        "selected_canonical_fork_children": len(candidates),
        "selected_edge_triples": len(selected_edges),
        "unused_manifest_entries": unused_manifest,
    }
    private = {
        "by_parent": by_parent,
        "directions": directions,
        "kernel_index": kernel_index,
        "node_index": node_index,
        "selected_edges": selected_edges,
    }
    return public, private


def support_audit(
    identity: dict[str, Any],
    private: dict[str, Any],
    kernel_outcomes: dict[int, Any],
    public_scores: dict[str, Any],
    train_tasks: set[str],
) -> tuple[dict[str, Any], dict[str, bool], str]:
    if not identity["identity_pass"]:
        return {}, {"identity_and_direction": False}, "IDENTITY_OR_JOIN_AMBIGUOUS"

    task_pairs: Counter[str] = Counter()
    parent_ids: set[str] = set()
    required_code_nodes: set[str] = set()
    declared_code_nodes: set[str] = set()
    totals = Counter()
    for parent_id, children in sorted(private["by_parent"].items()):
        if len(children) < 2:
            continue
        ordered = sorted(children, key=lambda row: row["node_id"])
        for left, right in itertools.combinations(ordered, 2):
            totals["all_structural_pairs"] += 1
            if left["comp"] in train_tasks:
                totals["task_overlap_structural_pairs"] += 1
                continue
            totals["task_unseen_structural_pairs"] += 1
            left_score = finite_float(kernel_outcomes.get(left["kernel_id"]))
            right_score = finite_float(kernel_outcomes.get(right["kernel_id"]))
            if left_score is None or right_score is None:
                totals["eventual_nonfinite_pairs"] += 1
                continue
            if left_score == right_score:
                totals["eventual_tie_pairs"] += 1
                continue
            totals["eventual_finite_nontie_pairs"] += 1
            task_pairs[left["comp"]] += 1
            parent_ids.add(parent_id)
            for node_id, path in (
                (parent_id, left["parent_raw_code_path"]),
                (left["node_id"], left["raw_code_path"]),
                (right["node_id"], right["raw_code_path"]),
            ):
                required_code_nodes.add(node_id)
                if path is not None:
                    declared_code_nodes.add(node_id)
            left_public = finite_float(public_scores.get(left["node_id"]))
            right_public = finite_float(public_scores.get(right["node_id"]))
            if left_public is None or right_public is None:
                totals["immediate_public_nonfinite_pairs"] += 1
            elif left_public == right_public:
                totals["immediate_public_tie_pairs"] += 1
            else:
                totals["immediate_public_finite_nontie_pairs"] += 1

    n_pairs = totals["eventual_finite_nontie_pairs"]
    dominant_share = max(task_pairs.values()) / n_pairs if n_pairs else None
    declared_coverage = len(declared_code_nodes) / len(required_code_nodes) if required_code_nodes else None
    support = {
        "declared_raw_code_node_coverage": declared_coverage,
        "declared_raw_code_nodes": len(declared_code_nodes),
        "dominant_pair_task_share": dominant_share,
        "parent_groups": len(parent_ids),
        "required_raw_code_nodes": len(required_code_nodes),
        "task_unseen_competitions": len(task_pairs),
        "task_unseen_pair_counts": dict(sorted(task_pairs.items())),
        "totals": dict(sorted(totals.items())),
        "training_competitions": len(train_tasks),
    }
    gates = {
        "declared_raw_code_paths_complete": declared_coverage == 1.0,
        "dominant_pair_task_share_at_most_0_20": dominant_share is not None and dominant_share <= MAX_DOMINANT_SHARE,
        "finite_nontie_eventual_pairs_at_least_500": n_pairs >= MIN_FINITE_NONTIE_PAIRS,
        "identity_and_direction": True,
        "parent_groups_at_least_100": len(parent_ids) >= MIN_PARENTS,
        "task_unseen_competitions_at_least_20": len(task_pairs) >= MIN_TASKS,
    }
    status = (
        "TRACEML_HUMAN_FORK_S1_PASS_DOWNLOAD_ALLOWED"
        if all(gates.values())
        else "TRACEML_HUMAN_FORK_S1_SUPPORT_GATE_FAILED"
    )
    return support, gates, status


def summarize(
    nodes: list[dict[str, Any]],
    kernels: list[dict[str, Any]],
    trees: list[dict[str, Any]],
    manifest: Any,
    edge_counts: dict[tuple[str, str, str], int],
    kernel_outcomes: dict[int, Any],
    public_scores: dict[str, Any],
    train_tasks: set[str],
) -> dict[str, Any]:
    identity, private = identity_audit(nodes, kernels, trees, manifest, edge_counts)
    support, gates, status = support_audit(
        identity, private, kernel_outcomes, public_scores, train_tasks
    )
    return {"gates": gates, "identity": identity, "status": status, "support": support}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--repo-root", type=Path, required=True)
    parser.add_argument("--source-commit", required=True)
    parser.add_argument("--protocol", type=Path, required=True)
    parser.add_argument("--expect-protocol-sha256", required=True)
    parser.add_argument("--input-manifest", type=Path, required=True)
    parser.add_argument("--expect-input-manifest-sha256", required=True)
    parser.add_argument("--dataset-root", type=Path, required=True)
    parser.add_argument("--train-pairs", type=Path, required=True)
    parser.add_argument("--expect-train-sha256", required=True)
    parser.add_argument("--dev-pairs", type=Path, required=True)
    parser.add_argument("--expect-dev-sha256", required=True)
    parser.add_argument("--output", type=Path, required=True)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    source_hashes = bind_source(args.repo_root, args.source_commit)
    require(sha256_file(args.protocol) == args.expect_protocol_sha256, "protocol SHA mismatch")
    require(
        sha256_file(args.input_manifest) == args.expect_input_manifest_sha256,
        "input manifest SHA mismatch",
    )
    require(sha256_file(args.train_pairs) == args.expect_train_sha256, "train SHA mismatch")
    require(sha256_file(args.dev_pairs) == args.expect_dev_sha256, "dev SHA mismatch")
    protocol = read_json_no_duplicates(args.protocol)
    require(protocol.get("protocol") == "traceml-human-fork-future-transfer-v1", "wrong protocol")
    input_manifest = read_json_no_duplicates(args.input_manifest)
    require(input_manifest.get("fixed_revision") == FIXED_REVISION, "wrong fixed revision")

    files = input_manifest.get("files")
    require(isinstance(files, dict), "input file manifest missing")
    for relative, metadata in files.items():
        path = args.dataset_root / relative
        require(isinstance(metadata, dict), f"malformed file metadata: {relative}")
        require(path.is_file(), f"missing fixed input: {relative}")
        require(path.stat().st_size == metadata.get("bytes"), f"size mismatch: {relative}")
        require(sha256_file(path) == metadata.get("sha256"), f"SHA mismatch: {relative}")

    nodes_path = args.dataset_root / "extras/nodes.parquet"
    kernels_path = args.dataset_root / "extras/kernels.parquet"
    trees_path = args.dataset_root / "extras/trees.parquet"
    edges_path = args.dataset_root / "extras/edges.parquet"
    manifest_path = args.dataset_root / "manifests/competitions.json"
    nodes = load_parquet(nodes_path, NODE_ID_COLUMNS)
    kernels = load_parquet(kernels_path, KERNEL_ID_COLUMNS)
    trees = load_parquet(trees_path, TREE_ID_COLUMNS)
    manifest = read_json_no_duplicates(manifest_path)
    preliminary_identity, preliminary_private = identity_audit(nodes, kernels, trees, manifest)
    edge_counts = selected_edge_counts(edges_path, preliminary_private["selected_edges"])

    # Score columns are opened only after the full identity/join pass, including edge-table multiplicity.
    identity, private = identity_audit(nodes, kernels, trees, manifest, edge_counts)
    if identity["identity_pass"]:
        outcome_rows = load_parquet(kernels_path, ("kernel_id", "best_private_score"))
        public_rows = load_parquet(nodes_path, ("node_id", "score_public"))
        kernel_outcomes = {
            exact_int(row.get("kernel_id")): row.get("best_private_score") for row in outcome_rows
        }
        public_scores = {
            nonempty_text(row.get("node_id")): row.get("score_public") for row in public_rows
        }
    else:
        kernel_outcomes = {}
        public_scores = {}
    train_tasks = read_jsonl_tasks(args.train_pairs) | read_jsonl_tasks(args.dev_pairs)
    support, gates, status = support_audit(
        identity, private, kernel_outcomes, public_scores, train_tasks
    )

    result = {
        "gates": gates,
        "identity": identity,
        "inputs": {
            "dev_sha256": args.expect_dev_sha256,
            "file_sha256": {key: value["sha256"] for key, value in sorted(files.items())},
            "input_manifest_sha256": args.expect_input_manifest_sha256,
            "protocol_sha256": args.expect_protocol_sha256,
            "train_sha256": args.expect_train_sha256,
        },
        "protocol": PROTOCOL,
        "reproducibility": {"randomness_used": False, "source_file_sha256": source_hashes},
        "revision": FIXED_REVISION,
        "scope": {
            "api_calls": 0,
            "effect_metrics_computed": [],
            "gpu": 0,
            "notebook_content_read": False,
            "predictor_scores_computed": False,
            "row_level_scores_emitted": False,
            "score_columns_read_after_identity_pass": identity["identity_pass"],
        },
        "source_commit": args.source_commit,
        "status": status,
        "support": support,
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_bytes(canonical_json(result))
    print(status)


if __name__ == "__main__":
    main()
