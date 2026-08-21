#!/usr/bin/env python3
"""Export explicit child-ID edges for the verified status-certified order."""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import os
import re
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any


PROTOCOL = "status-certified-edge-export-v1"
STATUS = "VERIFIED_STATUS_CERTIFIED_EDGE_MANIFEST"
ROLES = ("train", "frozen", "extension")
SHA256 = re.compile(r"^[0-9a-f]{64}$")
HEX40 = re.compile(r"^[0-9a-f]{40}$")
CERTIFIABLE = {"EXECUTION_ERROR", "OFFICIAL_GRADE_ABSENT"}
UPSTREAM_FIELDS = (
    "role", "task", "run_id", "parent", "pair_rows", "unique_edges",
    "published_endpoint_count", "declared_set_size", "raw_card_child_count",
    "finite_card_child_count", "source_declared_size", "source_size_consistent",
    "source_size_not_smaller_than_raw", "raw_context_consistent",
    "endpoints_all_finite", "endpoint_fidelity", "declared_matches_finite",
    "finite_endpoint_coverage", "pair_graph_coverage_over_finite",
    "raw_source_retention", "finite_source_retention", "raw_equals_source",
    "finite_equals_source", "parent_card_present", "parent_context_consistent",
    "parent_children_declared_count", "parent_children_contains_raw",
    "source_size_gt_five",
)


class ExportError(RuntimeError):
    pass


def digest(path: Path) -> str:
    value = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            value.update(chunk)
    return value.hexdigest()


def normalized_bytes(path: Path) -> bytes:
    text = path.read_bytes().decode("utf-8")
    if text.startswith("\ufeff"):
        text = text[1:]
    return text.replace("\r\n", "\n").replace("\r", "\n").encode("utf-8")


def normalized_digest(path: Path) -> str:
    return hashlib.sha256(normalized_bytes(path)).hexdigest()


def load_protocol(path: Path, repo_root: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if value.get("protocol") != PROTOCOL:
        raise ExportError("invalid protocol")
    for field in (
        "input_per_parent_sha256", "input_status_sha256",
        "formal_summary_sha256_normalized_lf",
    ):
        if not SHA256.fullmatch(str(value.get(field, ""))):
            raise ExportError(f"invalid protocol hash: {field}")
    if set(value.get("pair_inputs", {})) != set(ROLES):
        raise ExportError("pair input roles mismatch")
    for role, item in value["pair_inputs"].items():
        if not isinstance(item, dict) or not SHA256.fullmatch(str(item.get("sha256_normalized_lf", ""))):
            raise ExportError(f"invalid pair input: {role}")
        candidate = (repo_root / item["path"]).resolve()
        try:
            candidate.relative_to(repo_root)
        except ValueError as error:
            raise ExportError("pair input escapes repository") from error
    return value


def load_parent_rows(path: Path, protocol: dict[str, Any]) -> dict[tuple[str, str], dict[str, Any]]:
    if digest(path) != protocol["input_per_parent_sha256"]:
        raise ExportError("per-parent SHA mismatch")
    result: dict[tuple[str, str], dict[str, Any]] = {}
    with path.open(encoding="utf-8", newline="") as handle:
        reader = csv.DictReader(handle)
        if tuple(reader.fieldnames or ()) != UPSTREAM_FIELDS:
            raise ExportError("per-parent fields mismatch")
        for line_number, raw in enumerate(reader, 2):
            role, parent = raw["role"], raw["parent"]
            key = (role, parent)
            if role not in ROLES or not parent or key in result:
                raise ExportError(f"invalid parent identity at row {line_number}")
            try:
                finite = int(raw["finite_card_child_count"])
                source = int(raw["source_declared_size"])
                pair_rows = int(raw["pair_rows"])
                edges = int(raw["unique_edges"])
            except ValueError as error:
                raise ExportError(f"invalid parent count at row {line_number}") from error
            if not 2 <= finite <= source or edges > finite * (finite - 1) // 2 or pair_rows < edges:
                raise ExportError(f"invalid parent capacity at row {line_number}")
            result[key] = {
                "role": role,
                "task": raw["task"],
                "run_id": raw["run_id"],
                "parent": parent,
                "finite_children": finite,
                "source_children": source,
                "pair_rows": pair_rows,
                "published_edges": edges,
            }
    if len(result) != protocol["expected_parent_rows"]:
        raise ExportError("parent count mismatch")
    return result


def load_endpoint_sets(
    protocol: dict[str, Any],
    repo_root: Path,
    parents: dict[tuple[str, str], dict[str, Any]],
) -> dict[tuple[str, str], set[str]]:
    endpoints: dict[tuple[str, str], set[str]] = defaultdict(set)
    pair_counts: Counter[tuple[str, str]] = Counter()
    unique_pairs: dict[tuple[str, str], set[tuple[str, str]]] = defaultdict(set)
    role_rows: Counter[str] = Counter()
    for role in ROLES:
        item = protocol["pair_inputs"][role]
        path = (repo_root / item["path"]).resolve()
        if normalized_digest(path) != item["sha256_normalized_lf"]:
            raise ExportError(f"pair input hash mismatch: {role}")
        for line_number, line in enumerate(normalized_bytes(path).decode("utf-8").splitlines(), 1):
            raw = json.loads(line)
            parent, task = raw.get("parent"), raw.get("task")
            left, right = raw.get("better"), raw.get("worse")
            key = (role, parent)
            if key not in parents or parents[key]["task"] != task:
                raise ExportError(f"pair parent/task mismatch: {role}:{line_number}")
            if not all(isinstance(value, str) and value for value in (left, right)) or left == right:
                raise ExportError(f"invalid endpoint identity: {role}:{line_number}")
            if raw.get("budget") != 0:
                raise ExportError(f"non-b0 row: {role}:{line_number}")
            endpoints[key].update((left, right))
            pair_counts[key] += 1
            unique_pairs[key].add(tuple(sorted((left, right))))
            role_rows[role] += 1
    if dict(role_rows) != protocol["expected_role_pair_rows"]:
        raise ExportError("role pair-row counts mismatch")
    for key, parent in parents.items():
        if pair_counts[key] != parent["pair_rows"]:
            raise ExportError(f"parent pair-row mismatch: {key}")
        if len(unique_pairs[key]) != parent["published_edges"]:
            raise ExportError(f"parent unique-edge mismatch: {key}")
        if len(endpoints[key]) != parent["finite_children"]:
            raise ExportError(f"parent endpoint-coverage mismatch: {key}")
    return endpoints


def load_certified_invalid(
    path: Path,
    protocol: dict[str, Any],
    parents: dict[tuple[str, str], dict[str, Any]],
) -> list[dict[str, str]]:
    if digest(path) != protocol["input_status_sha256"]:
        raise ExportError("status SHA mismatch")
    result = []
    seen: set[str] = set()
    with path.open(encoding="utf-8") as handle:
        for line_number, line in enumerate(handle, 1):
            raw = json.loads(line)
            child = raw.get("child_id")
            key = (raw.get("role"), raw.get("expected_parent_id"))
            if not isinstance(child, str) or not child or child in seen or key not in parents:
                raise ExportError(f"invalid status identity at line {line_number}")
            seen.add(child)
            if raw.get("status") == "UNIQUE_NODE_RECOVERED" and raw.get("category") in CERTIFIABLE:
                if (
                    raw.get("parent_match") is not True
                    or raw.get("journal_parent_id") != key[1]
                    or not SHA256.fullmatch(str(raw.get("source_journal_sha256", "")))
                ):
                    raise ExportError(f"invalid certified status at line {line_number}")
                result.append(
                    {
                        "role": key[0],
                        "parent": key[1],
                        "invalid_child_id": child,
                        "invalid_category": raw["category"],
                        "status_journal_sha256": raw["source_journal_sha256"],
                    }
                )
    if len(result) != protocol["expected_certified_invalid_children"]:
        raise ExportError("certified invalid count mismatch")
    return result


def build_edges(
    invalid_rows: list[dict[str, str]],
    endpoints: dict[tuple[str, str], set[str]],
    parents: dict[tuple[str, str], dict[str, Any]],
) -> list[dict[str, str]]:
    edges = []
    seen: set[tuple[str, str, str, str]] = set()
    for invalid in invalid_rows:
        key = (invalid["role"], invalid["parent"])
        parent = parents[key]
        if invalid["invalid_child_id"] in endpoints[key]:
            raise ExportError("invalid child appears among finite endpoints")
        for valid in sorted(endpoints[key]):
            edge_key = (invalid["role"], invalid["parent"], valid, invalid["invalid_child_id"])
            if edge_key in seen:
                raise ExportError("duplicate exported edge")
            seen.add(edge_key)
            edges.append(
                {
                    "role": invalid["role"],
                    "task": parent["task"],
                    "run_id": parent["run_id"],
                    "parent": invalid["parent"],
                    "valid_child_id": valid,
                    "invalid_child_id": invalid["invalid_child_id"],
                    "invalid_category": invalid["invalid_category"],
                    "relation": "VALIDITY_DOMINANCE",
                    "status_journal_sha256": invalid["status_journal_sha256"],
                }
            )
    role_rank = {role: index for index, role in enumerate(ROLES)}
    edges.sort(
        key=lambda row: (
            role_rank[row["role"]], row["task"], row["run_id"], row["parent"],
            row["invalid_child_id"], row["valid_child_id"],
        )
    )
    return edges


def summarize(
    edges: list[dict[str, str]],
    parents: dict[tuple[str, str], dict[str, Any]],
    protocol: dict[str, Any],
    source_commit: str,
) -> dict[str, Any]:
    by_category = dict(sorted(Counter(row["invalid_category"] for row in edges).items()))
    by_role = dict(sorted(Counter(row["role"] for row in edges).items()))
    by_task = dict(sorted(Counter(row["task"] for row in edges).items()))
    execution_edges = [row for row in edges if row["invalid_category"] == "EXECUTION_ERROR"]

    def base(rows: list[dict[str, Any]]) -> dict[str, int]:
        return {
            "source_pair_capacity": sum(row["source_children"] * (row["source_children"] - 1) // 2 for row in rows),
            "published_unique_edges": sum(row["published_edges"] for row in rows),
        }

    def augmented(base_value: dict[str, int], added: int) -> dict[str, Any]:
        capacity = base_value["source_pair_capacity"]
        published_count = base_value["published_unique_edges"]
        gap = capacity - published_count
        return {
            **base_value,
            "validity_dominance_edges": added,
            "certified_relations": published_count + added,
            "certified_coverage": (published_count + added) / capacity,
            "coverage_gain": added / capacity,
            "lost_relation_recovery": added / gap,
        }

    parent_values = list(parents.values())
    overall_sensitivity = augmented(base(parent_values), len(execution_edges))
    role_sensitivity = {
        role: augmented(
            base([row for row in parent_values if row["role"] == role]),
            sum(row["role"] == role for row in execution_edges),
        )
        for role in ROLES
    }
    task_bases = {
        task: base([row for row in parent_values if row["task"] == task])
        for task in sorted({row["task"] for row in parent_values})
    }
    task_added = Counter(row["task"] for row in execution_edges)
    supported_tasks = [
        task for task, value in task_bases.items()
        if value["source_pair_capacity"] >= protocol["minimum_task_source_pair_capacity"]
    ]
    positive_tasks = [task for task in supported_tasks if task_added[task] > 0]
    dominant_task = max(task_bases, key=lambda task: task_added[task])
    dominant_share = task_added[dominant_task] / len(execution_edges)
    criteria = {
        "added_relations_ge_material_minimum": len(execution_edges) >= protocol["material_min_added_relations"],
        "overall_coverage_gain_ge_material_minimum": overall_sensitivity["coverage_gain"] >= protocol["material_min_overall_coverage_gain"],
        "gap_recovery_ge_material_minimum": overall_sensitivity["lost_relation_recovery"] >= protocol["material_min_gap_recovery_share"],
        "train_coverage_gain_ge_material_minimum": role_sensitivity["train"]["coverage_gain"] >= protocol["material_min_train_coverage_gain"],
        "frozen_coverage_gain_ge_material_minimum": role_sensitivity["frozen"]["coverage_gain"] >= protocol["material_min_frozen_coverage_gain"],
        "supported_tasks_ge_minimum": len(supported_tasks) >= protocol["minimum_supported_tasks"],
        "tasks_with_positive_gain_ge_minimum": len(positive_tasks) >= protocol["minimum_tasks_with_positive_gain"],
        "dominant_task_share_le_maximum": dominant_share <= protocol["maximum_dominant_added_relation_task_share"],
        "relation_accounting_exact": overall_sensitivity["certified_relations"] == protocol["expected_published_edges"] + len(execution_edges),
        "unknown_status_not_promoted": True,
    }
    sensitivity = {
        "overall": overall_sensitivity,
        "roles": role_sensitivity,
        "support": {
            "supported_tasks": len(supported_tasks),
            "supported_task_ids": supported_tasks,
            "tasks_with_positive_gain": len(positive_tasks),
            "task_ids_with_positive_gain": positive_tasks,
            "dominant_added_relation_task": dominant_task,
            "dominant_added_relation_task_share": dominant_share,
        },
        "criteria": criteria,
        "preserves_all_original_material_gates": all(criteria.values()),
    }
    return {
        "protocol": PROTOCOL,
        "status": STATUS,
        "source_commit": source_commit,
        "edge_count": len(edges),
        "unique_valid_children": len({row["valid_child_id"] for row in edges}),
        "unique_invalid_children": len({row["invalid_child_id"] for row in edges}),
        "parents": len({(row["role"], row["parent"]) for row in edges}),
        "tasks": len({row["task"] for row in edges}),
        "by_category": by_category,
        "by_role": by_role,
        "by_task": by_task,
        "execution_error_only_sensitivity": sensitivity,
        "scope": {
            "post_result_release_export": True,
            "published_pair_files_read_for_endpoint_identity": True,
            "published_pair_orientation_direction_used": False,
            "gap_or_numeric_score_used": False,
            "candidate_code_read": False,
            "prospective_outcome_read": False,
            "complete_choice_set_claim": False,
            "numeric_quality_order_claim": False,
        },
    }


def write_outputs(output: Path, edges: list[dict[str, str]], summary: dict[str, Any]) -> None:
    if output.exists():
        raise ExportError(f"output exists: {output}")
    temporary = output.with_name(output.name + f".tmp.{os.getpid()}")
    temporary.mkdir(parents=True)
    with (temporary / "edges.jsonl").open("w", encoding="utf-8", newline="\n") as handle:
        for row in edges:
            handle.write(json.dumps(row, sort_keys=True, ensure_ascii=False) + "\n")
    (temporary / "summary.json").write_text(
        json.dumps(summary, indent=2, sort_keys=True, ensure_ascii=False, allow_nan=False) + "\n",
        encoding="utf-8",
        newline="\n",
    )
    manifest = {name: digest(temporary / name) for name in ("edges.jsonl", "summary.json")}
    (temporary / "sha256_manifest.json").write_text(
        json.dumps(manifest, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
        newline="\n",
    )
    os.replace(temporary, output)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--repo-root", required=True)
    parser.add_argument("--protocol", required=True)
    parser.add_argument("--per-parent", required=True)
    parser.add_argument("--status-jsonl", required=True)
    parser.add_argument("--source-commit", required=True)
    parser.add_argument("--output", required=True)
    args = parser.parse_args()
    if not HEX40.fullmatch(args.source_commit):
        raise ExportError("source commit must be full SHA")
    repo_root = Path(args.repo_root).resolve()
    protocol = load_protocol(Path(args.protocol).resolve(), repo_root)
    formal = (repo_root / protocol["formal_summary_path"]).resolve()
    if normalized_digest(formal) != protocol["formal_summary_sha256_normalized_lf"]:
        raise ExportError("formal summary hash mismatch")
    formal_payload = json.loads(normalized_bytes(formal).decode("utf-8"))
    if (
        formal_payload.get("status") != "VERIFIED_MATERIAL_STATUS_CERTIFIED_RELATION_RECOVERY"
        or formal_payload.get("overall", {}).get("validity_dominance_edges")
        != protocol["expected_validity_edges"]
    ):
        raise ExportError("formal summary contract mismatch")
    parents = load_parent_rows(Path(args.per_parent).resolve(), protocol)
    endpoints = load_endpoint_sets(protocol, repo_root, parents)
    invalid_rows = load_certified_invalid(Path(args.status_jsonl).resolve(), protocol, parents)
    edges = build_edges(invalid_rows, endpoints, parents)
    if len(edges) != protocol["expected_validity_edges"]:
        raise ExportError("edge count differs from formal audit")
    summary = summarize(edges, parents, protocol, args.source_commit)
    write_outputs(Path(args.output).resolve(), edges, summary)
    print(STATUS)


if __name__ == "__main__":
    main()
