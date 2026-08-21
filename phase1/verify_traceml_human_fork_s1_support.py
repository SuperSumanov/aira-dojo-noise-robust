"""Independent verifier for the TraceML human-fork S1 support audit.

This module intentionally does not import the producer.  It reconstructs the
canonical-fork population and all support gates directly from fixed inputs.
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
from typing import Any


PRODUCER_PROTOCOL = "traceml-human-fork-future-s1-support-v1"
VERIFIER_PROTOCOL = "independent-traceml-human-fork-future-s1-support-v1"
REVISION = "61faec615b179f186dbe9c82ee59d17e14817e96"
REGISTERED = (
    "phase1/traceml_human_fork_s1_support.py",
    "phase1/verify_traceml_human_fork_s1_support.py",
    "phase1/scripts/run_traceml_human_fork_s1_20260821.sh",
    "phase1/traceml_human_fork_future_protocol_v1.json",
    "phase1/traceml_human_fork_s0_input_manifest.json",
)
SECRET_SHAPE = re.compile(
    rb"(?:^|[^A-Za-z0-9])(?:sk-[A-Za-z0-9._-]{16,}|hf_[A-Za-z0-9]{16,}|"
    rb"gh[pousr]_[A-Za-z0-9]{16,}|AKIA[0-9A-Z]{16}|AIza[0-9A-Za-z_-]{30,}|"
    rb"Bearer[ \t]+[A-Za-z0-9._-]{20,}|-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----)"
)


class VerificationError(RuntimeError):
    pass


def demand(value: bool, message: str) -> None:
    if not value:
        raise VerificationError(message)


def digest(path: Path) -> str:
    state = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            state.update(chunk)
    return state.hexdigest()


def stable_json(value: Any) -> bytes:
    return (json.dumps(value, indent=2, sort_keys=True, ensure_ascii=False) + "\n").encode()


def integer(value: Any) -> int | None:
    if value is None or isinstance(value, bool):
        return None
    try:
        converted = float(value)
    except (TypeError, ValueError):
        return None
    if not math.isfinite(converted) or converted != math.floor(converted):
        return None
    return int(converted)


def real(value: Any) -> float | None:
    if value is None or isinstance(value, bool):
        return None
    try:
        converted = float(value)
    except (TypeError, ValueError):
        return None
    return converted if math.isfinite(converted) else None


def text(value: Any) -> str | None:
    return value if isinstance(value, str) and len(value) > 0 else None


def safe_string(value: Any) -> None:
    if isinstance(value, str) and SECRET_SHAPE.search(value.encode("utf-8")):
        raise VerificationError("credential-shaped identity value")


def no_duplicate_json(path: Path) -> Any:
    def convert(items: list[tuple[str, Any]]) -> dict[str, Any]:
        result: dict[str, Any] = {}
        for name, value in items:
            demand(name not in result, f"duplicate JSON key in {path.name}")
            result[name] = value
        return result

    return json.loads(path.read_text(encoding="utf-8"), object_pairs_hook=convert)


def git(repo: Path, *args: str) -> str:
    return subprocess.run(
        ["git", "-C", str(repo), *args],
        check=True,
        capture_output=True,
        text=True,
    ).stdout.strip()


def verify_commit(repo: Path, commit: str) -> dict[str, str]:
    demand(git(repo, "rev-parse", "HEAD") == commit, "wrong checked-out commit")
    source_hashes: dict[str, str] = {}
    for relative in REGISTERED:
        demand(
            git(repo, "hash-object", relative) == git(repo, "rev-parse", f"{commit}:{relative}"),
            f"registered source is dirty: {relative}",
        )
        source_hashes[relative] = digest(repo / relative)
    return source_hashes


def parquet_rows(path: Path, names: tuple[str, ...]) -> list[dict[str, Any]]:
    try:
        import pyarrow.parquet as pq
    except ImportError as exc:  # pragma: no cover
        raise VerificationError("pyarrow unavailable") from exc
    schema = pq.read_schema(path)
    demand(set(names).issubset(schema.names), f"missing parquet columns: {path.name}")
    return pq.read_table(path, columns=list(names)).to_pylist()


def training_tasks(paths: tuple[Path, Path]) -> set[str]:
    observed: set[str] = set()
    for path in paths:
        count = 0
        with path.open(encoding="utf-8") as lines:
            for index, line in enumerate(lines, 1):
                if not line.strip():
                    continue
                row = json.loads(line)
                name = text(row.get("task"))
                demand(name is not None, f"task absent: {path.name}:{index}")
                safe_string(name)
                observed.add(name)
                count += 1
        demand(count > 0, f"empty pairs: {path.name}")
    return observed


def edge_multiplicity(path: Path, wanted: set[tuple[str, str, str]]) -> Counter[tuple[str, str, str]]:
    try:
        import pyarrow.parquet as pq
    except ImportError as exc:  # pragma: no cover
        raise VerificationError("pyarrow unavailable") from exc
    parquet = pq.ParquetFile(path)
    names = ("parent_id", "child_id", "edge_kind")
    demand(set(names).issubset(parquet.schema_arrow.names), "edge identity columns absent")
    found: Counter[tuple[str, str, str]] = Counter()
    for batch in parquet.iter_batches(columns=list(names), batch_size=32768):
        parents = batch.column(0).to_pylist()
        children = batch.column(1).to_pylist()
        kinds = batch.column(2).to_pylist()
        for parent, child, kind in zip(parents, children, kinds):
            safe_string(parent)
            safe_string(child)
            safe_string(kind)
            triple = (parent, child, kind)
            if all(isinstance(item, str) for item in triple) and triple in wanted:
                found[triple] += 1
    return found


def reconstruct(
    node_rows: list[dict[str, Any]],
    kernel_rows: list[dict[str, Any]],
    tree_rows: list[dict[str, Any]],
    manifest: Any,
    edge_file: Path,
    outcome_rows: list[dict[str, Any]] | None,
    public_rows: list[dict[str, Any]] | None,
    seen_tasks: set[str],
) -> dict[str, Any]:
    demand(isinstance(manifest, dict) and len(manifest) > 0, "bad manifest root")
    score_is_max: dict[str, bool] = {}
    bad_manifest = 0
    for name, metadata in manifest.items():
        direction = metadata.get("score_direction") if isinstance(metadata, dict) else None
        if not isinstance(name, str) or not name or direction not in ("higher", "lower"):
            bad_manifest += 1
        else:
            score_is_max[name] = direction == "higher"

    node_keys = [text(row.get("node_id")) for row in node_rows]
    kernel_keys = [integer(row.get("kernel_id")) for row in kernel_rows]
    tree_keys = [text(row.get("tree_id")) for row in tree_rows]
    nc = Counter(item for item in node_keys if item is not None)
    kc = Counter(item for item in kernel_keys if item is not None)
    tc = Counter(item for item in tree_keys if item is not None)
    nodes = {key: row for key, row in zip(node_keys, node_rows) if key is not None and nc[key] == 1}
    kernels = {
        key: row for key, row in zip(kernel_keys, kernel_rows) if key is not None and kc[key] == 1
    }
    trees = {key: row for key, row in zip(tree_keys, tree_rows) if key is not None and tc[key] == 1}
    graph_tasks = {
        name
        for collection in (node_rows, kernel_rows, tree_rows)
        for row in collection
        if (name := text(row.get("comp"))) is not None
    }
    unused_manifest = sorted(set(score_is_max) - graph_tasks)
    missing_manifest = graph_tasks - set(score_is_max)
    errors = Counter(
        {
            "missing_node_id": sum(key is None for key in node_keys),
            "duplicate_node_id": sum(value - 1 for value in nc.values() if value > 1),
            "missing_kernel_id": sum(key is None for key in kernel_keys),
            "duplicate_kernel_id": sum(value - 1 for value in kc.values() if value > 1),
            "missing_tree_id": sum(key is None for key in tree_keys),
            "duplicate_tree_id": sum(value - 1 for value in tc.values() if value > 1),
        }
    )

    for row in kernel_rows:
        safe_string(row.get("comp"))
        safe_string(row.get("raw_dir"))
        comp = text(row.get("comp"))
        if comp is None:
            errors["kernel_missing_comp"] += 1
        expected = score_is_max.get(comp or "")
        if not isinstance(row.get("score_is_max"), bool) or row.get("score_is_max") != expected:
            errors["kernel_direction_mismatch"] += 1
    for row in tree_rows:
        safe_string(row.get("tree_id"))
        safe_string(row.get("comp"))
        if text(row.get("comp")) is None:
            errors["tree_missing_comp"] += 1

    fork_children: list[dict[str, Any]] = []
    for row in node_rows:
        for field in ("node_id", "tree_id", "comp", "parent_id", "edge_kind", "raw_code_path"):
            safe_string(row.get(field))
        node_id = text(row.get("node_id"))
        tree_id = text(row.get("tree_id"))
        comp = text(row.get("comp"))
        kernel_id = integer(row.get("kernel_id"))
        if comp is None:
            errors["node_missing_comp"] += 1
        expected = score_is_max.get(comp or "")
        if not isinstance(row.get("score_is_max"), bool) or row.get("score_is_max") != expected:
            errors["node_direction_mismatch"] += 1
        kernel = kernels.get(kernel_id) if kernel_id is not None else None
        if kernel is None or kernel.get("comp") != comp:
            errors["node_kernel_join_mismatch"] += 1
        tree = trees.get(tree_id or "")
        if tree is None or tree.get("comp") != comp:
            errors["node_tree_join_mismatch"] += 1
        if row.get("edge_kind") != "fork":
            continue
        errors["canonical_fork_nodes"] += 1
        parent_id = text(row.get("parent_id"))
        parent = nodes.get(parent_id or "")
        valid = True
        if node_id is None or nc.get(node_id) != 1 or parent is None:
            errors["fork_parent_join_mismatch"] += 1
            valid = False
        if integer(row.get("version_in_kernel")) != 1:
            errors["fork_not_first_kernel_version"] += 1
            valid = False
        if parent is not None:
            if parent.get("tree_id") != tree_id or parent.get("comp") != comp:
                errors["fork_parent_tree_comp_mismatch"] += 1
                valid = False
            if integer(row.get("depth")) is None or integer(parent.get("depth")) is None or integer(row.get("depth")) != integer(parent.get("depth")) + 1:
                errors["fork_depth_delta_mismatch"] += 1
                valid = False
            if integer(parent.get("kernel_id")) == kernel_id:
                errors["fork_same_kernel_as_parent"] += 1
                valid = False
        if valid:
            fork_children.append(
                {
                    "node": node_id,
                    "parent": parent_id,
                    "comp": comp,
                    "kernel": kernel_id,
                    "raw": text(row.get("raw_code_path")),
                    "parent_raw": text(parent.get("raw_code_path")),
                }
            )

    wanted_edges = {(child["parent"], child["node"], "fork") for child in fork_children}
    observed_edges = edge_multiplicity(edge_file, wanted_edges)
    errors["fork_edge_table_multiplicity_mismatch"] = sum(
        observed_edges.get(edge, 0) != 1 for edge in wanted_edges
    )
    grouped: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for child in fork_children:
        grouped[child["parent"]].append(child)
    errors["fork_child_kernel_duplicate_within_parent"] = sum(
        count - 1
        for children in grouped.values()
        for count in Counter(child["kernel"] for child in children).values()
        if count > 1
    )
    errors["fork_child_kernel_duplicate_global"] = sum(
        count - 1 for count in Counter(child["kernel"] for child in fork_children).values() if count > 1
    )

    nonzero_errors = [
        name for name, count in errors.items() if name != "canonical_fork_nodes" and count != 0
    ]
    identity_pass = bad_manifest == 0 and len(missing_manifest) == 0 and not nonzero_errors
    identity = {
        "counts": dict(sorted(errors.items())),
        "graph_competitions": len(graph_tasks),
        "identity_pass": identity_pass,
        "malformed_manifest_entries": bad_manifest,
        "manifest_entries": len(score_is_max),
        "missing_manifest_entries": len(missing_manifest),
        "selected_canonical_fork_children": len(fork_children),
        "selected_edge_triples": len(wanted_edges),
        "unused_manifest_entries": unused_manifest,
    }
    if not identity_pass:
        return {
            "gates": {"identity_and_direction": False},
            "identity": identity,
            "status": "IDENTITY_OR_JOIN_AMBIGUOUS",
            "support": {},
        }

    if outcome_rows is None or public_rows is None:
        return {
            "gates": {"identity_and_direction": True},
            "identity": identity,
            "status": "IDENTITY_PASS_SCORE_ROWS_NOT_READ",
            "support": {},
        }
    outcomes = {integer(row.get("kernel_id")): row.get("best_private_score") for row in outcome_rows}
    immediate = {text(row.get("node_id")): row.get("score_public") for row in public_rows}
    pair_counts: Counter[str] = Counter()
    parents: set[str] = set()
    needed_nodes: set[str] = set()
    path_nodes: set[str] = set()
    totals = Counter()
    for parent, children in sorted(grouped.items()):
        children.sort(key=lambda item: item["node"])
        for a, b in itertools.combinations(children, 2):
            totals["all_structural_pairs"] += 1
            if a["comp"] in seen_tasks:
                totals["task_overlap_structural_pairs"] += 1
                continue
            totals["task_unseen_structural_pairs"] += 1
            a_outcome, b_outcome = real(outcomes.get(a["kernel"])), real(outcomes.get(b["kernel"]))
            if a_outcome is None or b_outcome is None:
                totals["eventual_nonfinite_pairs"] += 1
                continue
            if a_outcome == b_outcome:
                totals["eventual_tie_pairs"] += 1
                continue
            totals["eventual_finite_nontie_pairs"] += 1
            pair_counts[a["comp"]] += 1
            parents.add(parent)
            for node, raw_path in ((parent, a["parent_raw"]), (a["node"], a["raw"]), (b["node"], b["raw"])):
                needed_nodes.add(node)
                if raw_path is not None:
                    path_nodes.add(node)
            a_public, b_public = real(immediate.get(a["node"])), real(immediate.get(b["node"]))
            if a_public is None or b_public is None:
                totals["immediate_public_nonfinite_pairs"] += 1
            elif a_public == b_public:
                totals["immediate_public_tie_pairs"] += 1
            else:
                totals["immediate_public_finite_nontie_pairs"] += 1

    finite_pairs = totals["eventual_finite_nontie_pairs"]
    dominant = max(pair_counts.values()) / finite_pairs if finite_pairs else None
    coverage = len(path_nodes) / len(needed_nodes) if needed_nodes else None
    support = {
        "declared_raw_code_node_coverage": coverage,
        "declared_raw_code_nodes": len(path_nodes),
        "dominant_pair_task_share": dominant,
        "parent_groups": len(parents),
        "required_raw_code_nodes": len(needed_nodes),
        "task_unseen_competitions": len(pair_counts),
        "task_unseen_pair_counts": dict(sorted(pair_counts.items())),
        "totals": dict(sorted(totals.items())),
        "training_competitions": len(seen_tasks),
    }
    gates = {
        "declared_raw_code_paths_complete": coverage == 1.0,
        "dominant_pair_task_share_at_most_0_20": dominant is not None and dominant <= 0.20,
        "finite_nontie_eventual_pairs_at_least_500": finite_pairs >= 500,
        "identity_and_direction": True,
        "parent_groups_at_least_100": len(parents) >= 100,
        "task_unseen_competitions_at_least_20": len(pair_counts) >= 20,
    }
    status = (
        "TRACEML_HUMAN_FORK_S1_PASS_DOWNLOAD_ALLOWED"
        if all(gates.values())
        else "TRACEML_HUMAN_FORK_S1_SUPPORT_GATE_FAILED"
    )
    return {"gates": gates, "identity": identity, "status": status, "support": support}


def arguments() -> argparse.Namespace:
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
    parser.add_argument("--producer-summary", type=Path, required=True)
    parser.add_argument("--expect-producer-summary-sha256", required=True)
    parser.add_argument("--output", type=Path, required=True)
    return parser.parse_args()


def main() -> None:
    args = arguments()
    sources = verify_commit(args.repo_root, args.source_commit)
    demand(digest(args.protocol) == args.expect_protocol_sha256, "protocol hash mismatch")
    demand(digest(args.input_manifest) == args.expect_input_manifest_sha256, "manifest hash mismatch")
    demand(digest(args.train_pairs) == args.expect_train_sha256, "train hash mismatch")
    demand(digest(args.dev_pairs) == args.expect_dev_sha256, "dev hash mismatch")
    demand(digest(args.producer_summary) == args.expect_producer_summary_sha256, "producer hash mismatch")
    protocol = no_duplicate_json(args.protocol)
    demand(protocol.get("protocol") == "traceml-human-fork-future-transfer-v1", "wrong protocol")
    file_manifest = no_duplicate_json(args.input_manifest)
    demand(file_manifest.get("fixed_revision") == REVISION, "wrong revision")
    listed = file_manifest.get("files")
    demand(isinstance(listed, dict), "missing listed files")
    for relative, metadata in listed.items():
        target = args.dataset_root / relative
        demand(isinstance(metadata, dict) and target.is_file(), f"bad input: {relative}")
        demand(target.stat().st_size == metadata.get("bytes"), f"size mismatch: {relative}")
        demand(digest(target) == metadata.get("sha256"), f"hash mismatch: {relative}")

    nodes = parquet_rows(
        args.dataset_root / "extras/nodes.parquet",
        ("node_id", "tree_id", "comp", "kernel_id", "version_in_kernel", "depth", "parent_id", "edge_kind", "score_is_max", "raw_code_path"),
    )
    kernels = parquet_rows(
        args.dataset_root / "extras/kernels.parquet", ("kernel_id", "comp", "score_is_max", "raw_dir")
    )
    trees = parquet_rows(args.dataset_root / "extras/trees.parquet", ("tree_id", "comp"))
    competition_manifest = no_duplicate_json(args.dataset_root / "manifests/competitions.json")
    tasks = training_tasks((args.train_pairs, args.dev_pairs))

    # First reconstruct identity with absent score rows.  If it passes, open aggregate score columns once.
    provisional = reconstruct(
        nodes,
        kernels,
        trees,
        competition_manifest,
        args.dataset_root / "extras/edges.parquet",
        None,
        None,
        tasks,
    )
    if provisional["identity"]["identity_pass"]:
        outcomes = parquet_rows(
            args.dataset_root / "extras/kernels.parquet", ("kernel_id", "best_private_score")
        )
        immediate = parquet_rows(
            args.dataset_root / "extras/nodes.parquet", ("node_id", "score_public")
        )
        rebuilt = reconstruct(
            nodes,
            kernels,
            trees,
            competition_manifest,
            args.dataset_root / "extras/edges.parquet",
            outcomes,
            immediate,
            tasks,
        )
    else:
        rebuilt = provisional

    producer = no_duplicate_json(args.producer_summary)
    checks = {
        "gates_exact": producer.get("gates") == rebuilt["gates"],
        "identity_exact": producer.get("identity") == rebuilt["identity"],
        "input_hashes": producer.get("inputs")
        == {
            "dev_sha256": args.expect_dev_sha256,
            "file_sha256": {key: value["sha256"] for key, value in sorted(listed.items())},
            "input_manifest_sha256": args.expect_input_manifest_sha256,
            "protocol_sha256": args.expect_protocol_sha256,
            "train_sha256": args.expect_train_sha256,
        },
        "producer_protocol": producer.get("protocol") == PRODUCER_PROTOCOL,
        "producer_source_commit": producer.get("source_commit") == args.source_commit,
        "producer_source_hash": producer.get("reproducibility", {}).get("source_file_sha256", {}).get(
            "phase1/traceml_human_fork_s1_support.py"
        )
        == sources["phase1/traceml_human_fork_s1_support.py"],
        "revision": producer.get("revision") == REVISION,
        "scope": producer.get("scope")
        == {
            "api_calls": 0,
            "effect_metrics_computed": [],
            "gpu": 0,
            "notebook_content_read": False,
            "predictor_scores_computed": False,
            "row_level_scores_emitted": False,
            "score_columns_read_after_identity_pass": rebuilt["identity"]["identity_pass"],
        },
        "status_exact": producer.get("status") == rebuilt["status"],
        "support_exact": producer.get("support") == rebuilt["support"],
    }
    demand(all(checks.values()), "independent reconstruction differs from producer")
    verification = {
        "checks": checks,
        "inputs": {
            "producer_summary_sha256": args.expect_producer_summary_sha256,
            "verifier_source_sha256": sources["phase1/verify_traceml_human_fork_s1_support.py"],
        },
        "observed": {
            "identity_pass": rebuilt["identity"]["identity_pass"],
            "s1_status": rebuilt["status"],
            "support_gates_pass": all(rebuilt["gates"].values()),
        },
        "producer_imported": False,
        "protocol": VERIFIER_PROTOCOL,
        "scope": {
            "api_calls": 0,
            "effect_metrics_computed": [],
            "gpu": 0,
            "notebook_content_read": False,
            "predictor_scores_computed": False,
            "row_level_scores_emitted": False,
        },
        "source_commit": args.source_commit,
        "status": "INDEPENDENT_TRACEML_HUMAN_FORK_S1_VERIFIED",
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_bytes(stable_json(verification))
    print(verification["status"])


if __name__ == "__main__":
    main()
