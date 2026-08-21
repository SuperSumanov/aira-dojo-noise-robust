#!/usr/bin/env python3
"""Independently reconstruct and verify the explicit status-certified edge manifest."""

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
PRODUCER_STATUS = "VERIFIED_STATUS_CERTIFIED_EDGE_MANIFEST"
VERIFY_STATUS = "INDEPENDENT_STATUS_CERTIFIED_EDGE_MANIFEST_VERIFIED"
ROLES = ("train", "frozen", "extension")
CERTIFIABLE = {"EXECUTION_ERROR", "OFFICIAL_GRADE_ABSENT"}
SHA256 = re.compile(r"^[0-9a-f]{64}$")
HEX40 = re.compile(r"^[0-9a-f]{40}$")
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


class VerificationError(RuntimeError):
    pass


def file_digest(path: Path) -> str:
    value = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            value.update(chunk)
    return value.hexdigest()


def lf_bytes(path: Path) -> bytes:
    text = path.read_bytes().decode("utf-8")
    if text.startswith("\ufeff"):
        text = text[1:]
    return text.replace("\r\n", "\n").replace("\r", "\n").encode("utf-8")


def lf_digest(path: Path) -> str:
    return hashlib.sha256(lf_bytes(path)).hexdigest()


def protocol_value(path: Path, root: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if value.get("protocol") != PROTOCOL or set(value.get("pair_inputs", {})) != set(ROLES):
        raise VerificationError("protocol identity mismatch")
    for field in (
        "input_per_parent_sha256", "input_status_sha256",
        "formal_summary_sha256_normalized_lf",
    ):
        if not SHA256.fullmatch(str(value.get(field, ""))):
            raise VerificationError(f"malformed protocol hash: {field}")
    for role in ROLES:
        item = value["pair_inputs"][role]
        if not SHA256.fullmatch(str(item.get("sha256_normalized_lf", ""))):
            raise VerificationError(f"malformed pair hash: {role}")
        target = (root / item["path"]).resolve()
        try:
            target.relative_to(root)
        except ValueError as error:
            raise VerificationError("pair path escapes repository") from error
    return value


def parent_census(path: Path, protocol: dict[str, Any]) -> dict[tuple[str, str], dict[str, Any]]:
    if file_digest(path) != protocol["input_per_parent_sha256"]:
        raise VerificationError("parent census hash mismatch")
    values: dict[tuple[str, str], dict[str, Any]] = {}
    with path.open(encoding="utf-8", newline="") as handle:
        reader = csv.DictReader(handle)
        if tuple(reader.fieldnames or ()) != UPSTREAM_FIELDS:
            raise VerificationError("parent census fields mismatch")
        for line_number, raw in enumerate(reader, 2):
            role, parent = raw["role"], raw["parent"]
            key = (role, parent)
            if role not in ROLES or not raw["task"] or not raw["run_id"] or not parent or key in values:
                raise VerificationError(f"invalid parent identity at row {line_number}")
            try:
                finite = int(raw["finite_card_child_count"])
                source = int(raw["source_declared_size"])
                pair_rows = int(raw["pair_rows"])
                published = int(raw["unique_edges"])
            except ValueError as error:
                raise VerificationError(f"invalid parent count at row {line_number}") from error
            if finite < 2 or source < finite or pair_rows < published or published > finite * (finite - 1) // 2:
                raise VerificationError(f"invalid parent capacity at row {line_number}")
            values[key] = {
                "role": role,
                "task": raw["task"],
                "run_id": raw["run_id"],
                "parent": parent,
                "finite_children": finite,
                "source_children": source,
                "pair_rows": pair_rows,
                "published_edges": published,
            }
    if len(values) != protocol["expected_parent_rows"]:
        raise VerificationError("parent census row count mismatch")
    return values


def endpoint_census(
    root: Path,
    protocol: dict[str, Any],
    parents: dict[tuple[str, str], dict[str, Any]],
) -> dict[tuple[str, str], set[str]]:
    endpoint_ids: dict[tuple[str, str], set[str]] = defaultdict(set)
    row_counts: Counter[tuple[str, str]] = Counter()
    unordered_pairs: dict[tuple[str, str], set[tuple[str, str]]] = defaultdict(set)
    role_counts: Counter[str] = Counter()
    for role in ROLES:
        item = protocol["pair_inputs"][role]
        pair_path = (root / item["path"]).resolve()
        if lf_digest(pair_path) != item["sha256_normalized_lf"]:
            raise VerificationError(f"pair hash mismatch: {role}")
        for line_number, line in enumerate(lf_bytes(pair_path).decode("utf-8").splitlines(), 1):
            value = json.loads(line)
            parent = value.get("parent")
            key = (role, parent)
            left, right = value.get("better"), value.get("worse")
            if key not in parents or value.get("task") != parents[key]["task"]:
                raise VerificationError(f"pair context mismatch: {role}:{line_number}")
            if not all(isinstance(item, str) and item for item in (left, right)) or left == right:
                raise VerificationError(f"invalid pair endpoint: {role}:{line_number}")
            if value.get("budget") != 0:
                raise VerificationError(f"non-b0 pair row: {role}:{line_number}")
            endpoint_ids[key].add(left)
            endpoint_ids[key].add(right)
            row_counts[key] += 1
            role_counts[role] += 1
            unordered_pairs[key].add(tuple(sorted((left, right))))
    if {role: role_counts[role] for role in ROLES} != protocol["expected_role_pair_rows"]:
        raise VerificationError("role pair counts mismatch")
    for key, parent in parents.items():
        if row_counts[key] != parent["pair_rows"]:
            raise VerificationError(f"parent pair-row mismatch: {key}")
        if len(unordered_pairs[key]) != parent["published_edges"]:
            raise VerificationError(f"parent edge count mismatch: {key}")
        if len(endpoint_ids[key]) != parent["finite_children"]:
            raise VerificationError(f"parent endpoint count mismatch: {key}")
    return endpoint_ids


def invalid_census(
    path: Path,
    protocol: dict[str, Any],
    parents: dict[tuple[str, str], dict[str, Any]],
) -> list[dict[str, str]]:
    if file_digest(path) != protocol["input_status_sha256"]:
        raise VerificationError("status registry hash mismatch")
    selected: list[dict[str, str]] = []
    all_children: set[str] = set()
    with path.open(encoding="utf-8") as handle:
        for line_number, line in enumerate(handle, 1):
            value = json.loads(line)
            child = value.get("child_id")
            key = (value.get("role"), value.get("expected_parent_id"))
            if not isinstance(child, str) or not child or child in all_children or key not in parents:
                raise VerificationError(f"invalid status identity at line {line_number}")
            all_children.add(child)
            if value.get("status") == "UNIQUE_NODE_RECOVERED" and value.get("category") in CERTIFIABLE:
                if (
                    value.get("parent_match") is not True
                    or value.get("journal_parent_id") != key[1]
                    or not SHA256.fullmatch(str(value.get("source_journal_sha256", "")))
                ):
                    raise VerificationError(f"invalid certified status at line {line_number}")
                selected.append(
                    {
                        "role": key[0],
                        "parent": key[1],
                        "invalid_child_id": child,
                        "invalid_category": value["category"],
                        "status_journal_sha256": value["source_journal_sha256"],
                    }
                )
    if len(selected) != protocol["expected_certified_invalid_children"]:
        raise VerificationError("certified invalid child count mismatch")
    return selected


def reconstruct_edges(
    invalid_rows: list[dict[str, str]],
    endpoints: dict[tuple[str, str], set[str]],
    parents: dict[tuple[str, str], dict[str, Any]],
) -> list[dict[str, str]]:
    result: list[dict[str, str]] = []
    identities: set[tuple[str, str, str, str]] = set()
    for invalid in invalid_rows:
        key = (invalid["role"], invalid["parent"])
        if invalid["invalid_child_id"] in endpoints[key]:
            raise VerificationError("certified invalid child is a finite endpoint")
        context = parents[key]
        for valid_child in sorted(endpoints[key]):
            identity = (invalid["role"], invalid["parent"], valid_child, invalid["invalid_child_id"])
            if identity in identities:
                raise VerificationError("duplicate reconstructed edge")
            identities.add(identity)
            result.append(
                {
                    "role": invalid["role"],
                    "task": context["task"],
                    "run_id": context["run_id"],
                    "parent": invalid["parent"],
                    "valid_child_id": valid_child,
                    "invalid_child_id": invalid["invalid_child_id"],
                    "invalid_category": invalid["invalid_category"],
                    "relation": "VALIDITY_DOMINANCE",
                    "status_journal_sha256": invalid["status_journal_sha256"],
                }
            )
    order = {role: index for index, role in enumerate(ROLES)}
    result.sort(
        key=lambda row: (
            order[row["role"]], row["task"], row["run_id"], row["parent"],
            row["invalid_child_id"], row["valid_child_id"],
        )
    )
    return result


def expected_summary(
    edges: list[dict[str, str]],
    parents: dict[tuple[str, str], dict[str, Any]],
    protocol: dict[str, Any],
    source_commit: str,
) -> dict[str, Any]:
    by_category = dict(sorted(Counter(row["invalid_category"] for row in edges).items()))
    by_role = dict(sorted(Counter(row["role"] for row in edges).items()))
    by_task = dict(sorted(Counter(row["task"] for row in edges).items()))
    execution = [row for row in edges if row["invalid_category"] == "EXECUTION_ERROR"]
    parent_rows = list(parents.values())

    def base(rows: list[dict[str, Any]]) -> dict[str, int]:
        return {
            "source_pair_capacity": sum(row["source_children"] * (row["source_children"] - 1) // 2 for row in rows),
            "published_unique_edges": sum(row["published_edges"] for row in rows),
        }

    def add(value: dict[str, int], edge_count: int) -> dict[str, Any]:
        capacity = value["source_pair_capacity"]
        published = value["published_unique_edges"]
        return {
            **value,
            "validity_dominance_edges": edge_count,
            "certified_relations": published + edge_count,
            "certified_coverage": (published + edge_count) / capacity,
            "coverage_gain": edge_count / capacity,
            "lost_relation_recovery": edge_count / (capacity - published),
        }

    overall = add(base(parent_rows), len(execution))
    roles = {
        role: add(
            base([row for row in parent_rows if row["role"] == role]),
            sum(edge["role"] == role for edge in execution),
        )
        for role in ROLES
    }
    task_base = {
        task: base([row for row in parent_rows if row["task"] == task])
        for task in sorted({row["task"] for row in parent_rows})
    }
    task_edges = Counter(row["task"] for row in execution)
    supported = [
        task for task, value in task_base.items()
        if value["source_pair_capacity"] >= protocol["minimum_task_source_pair_capacity"]
    ]
    positive = [task for task in supported if task_edges[task] > 0]
    dominant = max(task_base, key=lambda task: task_edges[task])
    dominant_share = task_edges[dominant] / len(execution)
    criteria = {
        "added_relations_ge_material_minimum": len(execution) >= protocol["material_min_added_relations"],
        "overall_coverage_gain_ge_material_minimum": overall["coverage_gain"] >= protocol["material_min_overall_coverage_gain"],
        "gap_recovery_ge_material_minimum": overall["lost_relation_recovery"] >= protocol["material_min_gap_recovery_share"],
        "train_coverage_gain_ge_material_minimum": roles["train"]["coverage_gain"] >= protocol["material_min_train_coverage_gain"],
        "frozen_coverage_gain_ge_material_minimum": roles["frozen"]["coverage_gain"] >= protocol["material_min_frozen_coverage_gain"],
        "supported_tasks_ge_minimum": len(supported) >= protocol["minimum_supported_tasks"],
        "tasks_with_positive_gain_ge_minimum": len(positive) >= protocol["minimum_tasks_with_positive_gain"],
        "dominant_task_share_le_maximum": dominant_share <= protocol["maximum_dominant_added_relation_task_share"],
        "relation_accounting_exact": overall["certified_relations"] == protocol["expected_published_edges"] + len(execution),
        "unknown_status_not_promoted": True,
    }
    return {
        "protocol": PROTOCOL,
        "status": PRODUCER_STATUS,
        "source_commit": source_commit,
        "edge_count": len(edges),
        "unique_valid_children": len({row["valid_child_id"] for row in edges}),
        "unique_invalid_children": len({row["invalid_child_id"] for row in edges}),
        "parents": len({(row["role"], row["parent"]) for row in edges}),
        "tasks": len({row["task"] for row in edges}),
        "by_category": by_category,
        "by_role": by_role,
        "by_task": by_task,
        "execution_error_only_sensitivity": {
            "overall": overall,
            "roles": roles,
            "support": {
                "supported_tasks": len(supported),
                "supported_task_ids": supported,
                "tasks_with_positive_gain": len(positive),
                "task_ids_with_positive_gain": positive,
                "dominant_added_relation_task": dominant,
                "dominant_added_relation_task_share": dominant_share,
            },
            "criteria": criteria,
            "preserves_all_original_material_gates": all(criteria.values()),
        },
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


def verify(
    root: Path,
    protocol_path: Path,
    parent_path: Path,
    status_path: Path,
    source_commit: str,
    artifact: Path,
) -> dict[str, Any]:
    if not HEX40.fullmatch(source_commit):
        raise VerificationError("source commit must be full SHA")
    if not artifact.is_dir() or {path.name for path in artifact.iterdir()} != {
        "edges.jsonl", "summary.json", "sha256_manifest.json"
    }:
        raise VerificationError("artifact membership mismatch")
    protocol = protocol_value(protocol_path, root)
    formal_path = (root / protocol["formal_summary_path"]).resolve()
    if lf_digest(formal_path) != protocol["formal_summary_sha256_normalized_lf"]:
        raise VerificationError("formal summary hash mismatch")
    formal = json.loads(lf_bytes(formal_path).decode("utf-8"))
    if (
        formal.get("status") != "VERIFIED_MATERIAL_STATUS_CERTIFIED_RELATION_RECOVERY"
        or formal.get("overall", {}).get("validity_dominance_edges") != protocol["expected_validity_edges"]
    ):
        raise VerificationError("formal summary contract mismatch")
    parents = parent_census(parent_path, protocol)
    endpoints = endpoint_census(root, protocol, parents)
    invalid_rows = invalid_census(status_path, protocol, parents)
    expected_edges = reconstruct_edges(invalid_rows, endpoints, parents)
    if len(expected_edges) != protocol["expected_validity_edges"]:
        raise VerificationError("reconstructed edge count mismatch")
    observed_edges = [
        json.loads(line)
        for line in (artifact / "edges.jsonl").read_text(encoding="utf-8").splitlines()
    ]
    if observed_edges != expected_edges:
        raise VerificationError("edge manifest differs from independent reconstruction")
    expected = expected_summary(expected_edges, parents, protocol, source_commit)
    observed = json.loads((artifact / "summary.json").read_text(encoding="utf-8"))
    if observed != expected:
        raise VerificationError("summary differs from independent reconstruction")
    expected_manifest = {
        name: file_digest(artifact / name) for name in ("edges.jsonl", "summary.json")
    }
    manifest = json.loads((artifact / "sha256_manifest.json").read_text(encoding="utf-8"))
    if manifest != expected_manifest:
        raise VerificationError("artifact manifest mismatch")
    return {
        "status": VERIFY_STATUS,
        "producer_status": observed["status"],
        "imports_producer": False,
        "edge_count": len(expected_edges),
        "unique_invalid_children": observed["unique_invalid_children"],
        "execution_error_only_preserves_all_original_material_gates": observed[
            "execution_error_only_sensitivity"
        ]["preserves_all_original_material_gates"],
        "maximum_reconstruction_difference": 0,
        "artifact_summary_sha256": expected_manifest["summary.json"],
        "artifact_manifest_sha256": file_digest(artifact / "sha256_manifest.json"),
        "pair_orientation_direction_used": False,
        "prospective_outcome_read": False,
    }


def atomic_json(path: Path, payload: dict[str, Any]) -> None:
    if path.exists():
        raise VerificationError(f"output exists: {path}")
    temporary = path.with_suffix(path.suffix + f".tmp.{os.getpid()}")
    temporary.write_text(
        json.dumps(payload, indent=2, sort_keys=True, ensure_ascii=False, allow_nan=False) + "\n",
        encoding="utf-8",
        newline="\n",
    )
    os.replace(temporary, path)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--repo-root", required=True)
    parser.add_argument("--protocol", required=True)
    parser.add_argument("--per-parent", required=True)
    parser.add_argument("--status-jsonl", required=True)
    parser.add_argument("--source-commit", required=True)
    parser.add_argument("--artifact", required=True)
    parser.add_argument("--output", required=True)
    args = parser.parse_args()
    receipt = verify(
        Path(args.repo_root).resolve(),
        Path(args.protocol).resolve(),
        Path(args.per_parent).resolve(),
        Path(args.status_jsonl).resolve(),
        args.source_commit,
        Path(args.artifact).resolve(),
    )
    atomic_json(Path(args.output).resolve(), receipt)
    print(receipt["status"])


if __name__ == "__main__":
    main()
