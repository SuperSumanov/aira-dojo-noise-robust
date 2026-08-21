#!/usr/bin/env python3
"""Independently reconstruct and verify the status-certified partial order."""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import math
import os
import re
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any, Iterable


PROTOCOL = "status-certified-partial-order-v1"
STATUS_PASS = "VERIFIED_MATERIAL_STATUS_CERTIFIED_RELATION_RECOVERY"
STATUS_BELOW = "VERIFIED_STATUS_RELATIONS_BELOW_MATERIAL_GATE"
STATUS_SUPPORT = "INSUFFICIENT_TASK_SUPPORT_FOR_STATUS_CERTIFIED_ORDER"
ROLES = ("train", "frozen", "extension")
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
PARENT_FIELDS = (
    "role", "task", "run_id", "parent", "source_children", "finite_children",
    "published_unique_edges", "status_target_children",
    "status_certified_invalid_children", "unknown_status_children",
    "unregistered_missing_slots", "validity_dominance_edges",
    "certified_relations", "unresolved_relations", "source_pair_capacity",
    "published_coverage", "certified_coverage", "coverage_gain",
    "lost_relation_recovery",
)
AGGREGATE_FIELDS = (
    "stratum_type", "stratum", "parents", "runs", "source_children",
    "finite_children", "published_unique_edges", "status_target_children",
    "status_certified_invalid_children", "unknown_status_children",
    "unregistered_missing_slots", "validity_dominance_edges",
    "certified_relations", "unresolved_relations", "source_pair_capacity",
    "parents_with_status_targets", "parents_with_added_relations",
    "published_coverage", "certified_coverage", "coverage_gain",
    "lost_relation_recovery",
)


class VerificationError(RuntimeError):
    pass


def digest(path: Path) -> str:
    value = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            value.update(chunk)
    return value.hexdigest()


def comb2(value: int) -> int:
    return value * (value - 1) // 2


def ratio(numerator: int | float, denominator: int | float) -> float | None:
    return numerator / denominator if denominator else None


def parse_bool(value: str, where: str) -> bool:
    if value == "True":
        return True
    if value == "False":
        return False
    raise VerificationError(f"invalid bool at {where}")


def parse_int(value: str, where: str) -> int:
    try:
        result = int(value)
    except ValueError as error:
        raise VerificationError(f"invalid integer at {where}") from error
    if result < 0:
        raise VerificationError(f"negative integer at {where}")
    return result


def load_protocol(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if value.get("protocol") != PROTOCOL:
        raise VerificationError("invalid protocol")
    if value.get("certifiable_categories") != ["EXECUTION_ERROR", "OFFICIAL_GRADE_ABSENT"]:
        raise VerificationError("certifiable category drift")
    for field in ("input_per_parent_sha256", "input_status_sha256"):
        if not SHA256.fullmatch(str(value.get(field, ""))):
            raise VerificationError(f"invalid input hash: {field}")
    return value


def load_parents(path: Path, protocol: dict[str, Any]) -> list[dict[str, Any]]:
    if digest(path) != protocol["input_per_parent_sha256"]:
        raise VerificationError("per-parent SHA mismatch")
    rows: list[dict[str, Any]] = []
    seen: set[tuple[str, str]] = set()
    with path.open(encoding="utf-8", newline="") as handle:
        reader = csv.DictReader(handle)
        if tuple(reader.fieldnames or ()) != UPSTREAM_FIELDS:
            raise VerificationError("upstream parent fields mismatch")
        for line_number, raw in enumerate(reader, 2):
            role, task, run_id, parent = (
                raw[name] for name in ("role", "task", "run_id", "parent")
            )
            key = (role, parent)
            if role not in ROLES or not task or not run_id or not parent or key in seen:
                raise VerificationError(f"invalid parent identity at row {line_number}")
            seen.add(key)
            source = parse_int(raw["source_declared_size"], f"source:{line_number}")
            raw_count = parse_int(raw["raw_card_child_count"], f"raw:{line_number}")
            finite = parse_int(raw["finite_card_child_count"], f"finite:{line_number}")
            endpoints = parse_int(raw["published_endpoint_count"], f"endpoints:{line_number}")
            edges = parse_int(raw["unique_edges"], f"edges:{line_number}")
            pair_rows = parse_int(raw["pair_rows"], f"pair_rows:{line_number}")
            if source < 2 or not 2 <= finite == raw_count == endpoints <= source:
                raise VerificationError(f"incompatible parent funnel at row {line_number}")
            if edges > comb2(finite) or pair_rows < edges:
                raise VerificationError(f"edge capacity mismatch at row {line_number}")
            for field in (
                "source_size_consistent", "source_size_not_smaller_than_raw",
                "raw_context_consistent", "endpoints_all_finite", "endpoint_fidelity",
                "declared_matches_finite", "parent_context_consistent",
            ):
                if not parse_bool(raw[field], f"{field}:{line_number}"):
                    raise VerificationError(f"upstream gate failed at row {line_number}")
            rows.append(
                {
                    "role": role,
                    "task": task,
                    "run_id": run_id,
                    "parent": parent,
                    "source_children": source,
                    "finite_children": finite,
                    "published_unique_edges": edges,
                }
            )
    if len(rows) != protocol["expected_parent_rows"]:
        raise VerificationError("parent count mismatch")
    role_counter = Counter(row["role"] for row in rows)
    if {role: role_counter[role] for role in ROLES} != protocol["expected_role_parent_counts"]:
        raise VerificationError("parent role count mismatch")
    return rows


def load_statuses(
    path: Path,
    protocol: dict[str, Any],
    parent_keys: set[tuple[str, str]],
) -> dict[tuple[str, str], Counter[str]]:
    if digest(path) != protocol["input_status_sha256"]:
        raise VerificationError("status SHA mismatch")
    grouped: dict[tuple[str, str], Counter[str]] = defaultdict(Counter)
    children: set[str] = set()
    statuses: Counter[str] = Counter()
    categories: Counter[str] = Counter()
    with path.open(encoding="utf-8") as handle:
        for line_number, line in enumerate(handle, 1):
            raw = json.loads(line)
            child = raw.get("child_id")
            role = raw.get("role")
            parent = raw.get("expected_parent_id")
            status = raw.get("status")
            category = raw.get("category")
            key = (role, parent)
            if not isinstance(child, str) or not child or child in children or key not in parent_keys:
                raise VerificationError(f"invalid status identity at line {line_number}")
            children.add(child)
            if status == "UNIQUE_NODE_RECOVERED":
                if (
                    raw.get("parent_match") is not True
                    or raw.get("journal_parent_id") != parent
                    or not SHA256.fullmatch(str(raw.get("source_journal_sha256", "")))
                    or category == "UNKNOWN"
                ):
                    raise VerificationError(f"invalid recovered status at line {line_number}")
            elif status in {"SOURCE_JOURNAL_NOT_FOUND", "SOURCE_JOURNAL_COLLISION"}:
                if category != "UNKNOWN" or raw.get("parent_match") is not False:
                    raise VerificationError(f"unknown status promotion at line {line_number}")
            else:
                raise VerificationError(f"unknown status at line {line_number}")
            statuses[status] += 1
            categories[category] += 1
            grouped[key]["targets"] += 1
            if status == "UNIQUE_NODE_RECOVERED" and category in protocol["certifiable_categories"]:
                grouped[key]["certified"] += 1
            else:
                grouped[key]["unknown"] += 1
    if len(children) != protocol["expected_status_rows"]:
        raise VerificationError("status row count mismatch")
    if dict(sorted(statuses.items())) != protocol["expected_status_counts"]:
        raise VerificationError("status counts mismatch")
    if dict(sorted(categories.items())) != protocol["expected_status_category_counts"]:
        raise VerificationError("category counts mismatch")
    return grouped


def reconstruct_parents(
    parents: list[dict[str, Any]], statuses: dict[tuple[str, str], Counter[str]]
) -> list[dict[str, Any]]:
    result = []
    for row in parents:
        counts = statuses.get((row["role"], row["parent"]), Counter())
        targets = counts["targets"]
        certified = counts["certified"]
        unknown = counts["unknown"]
        missing = row["source_children"] - row["finite_children"]
        if targets > missing or targets != certified + unknown:
            raise VerificationError("status/missing accounting mismatch")
        capacity = comb2(row["source_children"])
        added = row["finite_children"] * certified
        total = row["published_unique_edges"] + added
        if total > capacity:
            raise VerificationError("certified relations exceed source capacity")
        gap = capacity - row["published_unique_edges"]
        result.append(
            {
                **row,
                "status_target_children": targets,
                "status_certified_invalid_children": certified,
                "unknown_status_children": unknown,
                "unregistered_missing_slots": missing - targets,
                "validity_dominance_edges": added,
                "certified_relations": total,
                "unresolved_relations": capacity - total,
                "source_pair_capacity": capacity,
                "published_coverage": ratio(row["published_unique_edges"], capacity),
                "certified_coverage": ratio(total, capacity),
                "coverage_gain": ratio(added, capacity),
                "lost_relation_recovery": ratio(added, gap),
            }
        )
    return result


def aggregate(rows: Iterable[dict[str, Any]], stratum_type: str, stratum: str) -> dict[str, Any]:
    values = list(rows)
    value: dict[str, Any] = {
        "stratum_type": stratum_type,
        "stratum": stratum,
        "parents": len(values),
        "runs": len({(row["role"], row["run_id"]) for row in values}),
    }
    for field in (
        "source_children", "finite_children", "published_unique_edges",
        "status_target_children", "status_certified_invalid_children",
        "unknown_status_children", "unregistered_missing_slots",
        "validity_dominance_edges", "certified_relations", "unresolved_relations",
        "source_pair_capacity",
    ):
        value[field] = sum(int(row[field]) for row in values)
    value["parents_with_status_targets"] = sum(row["status_target_children"] > 0 for row in values)
    value["parents_with_added_relations"] = sum(row["validity_dominance_edges"] > 0 for row in values)
    gap = value["source_pair_capacity"] - value["published_unique_edges"]
    value["published_coverage"] = ratio(value["published_unique_edges"], value["source_pair_capacity"])
    value["certified_coverage"] = ratio(value["certified_relations"], value["source_pair_capacity"])
    value["coverage_gain"] = ratio(value["validity_dominance_edges"], value["source_pair_capacity"])
    value["lost_relation_recovery"] = ratio(value["validity_dominance_edges"], gap)
    return value


def expected_summary(
    rows: list[dict[str, Any]], protocol: dict[str, Any], source_commit: str
) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    overall = aggregate(rows, "overall", "all")
    roles = {
        role: aggregate((row for row in rows if row["role"] == role), "role", role)
        for role in ROLES
    }
    tasks = [
        aggregate((row for row in rows if row["task"] == task), "task", task)
        for task in sorted({row["task"] for row in rows})
    ]
    supported = [
        row for row in tasks
        if row["source_pair_capacity"] >= protocol["minimum_task_source_pair_capacity"]
    ]
    positive = [row for row in supported if row["validity_dominance_edges"] > 0]
    dominant = max(tasks, key=lambda row: row["validity_dominance_edges"])
    dominant_share = ratio(dominant["validity_dominance_edges"], overall["validity_dominance_edges"])
    criteria = {
        "added_relations_ge_material_minimum": overall["validity_dominance_edges"] >= protocol["material_min_added_relations"],
        "overall_coverage_gain_ge_material_minimum": overall["coverage_gain"] >= protocol["material_min_overall_coverage_gain"],
        "gap_recovery_ge_material_minimum": overall["lost_relation_recovery"] >= protocol["material_min_gap_recovery_share"],
        "train_coverage_gain_ge_material_minimum": roles["train"]["coverage_gain"] >= protocol["material_min_train_coverage_gain"],
        "frozen_coverage_gain_ge_material_minimum": roles["frozen"]["coverage_gain"] >= protocol["material_min_frozen_coverage_gain"],
        "tasks_with_positive_gain_ge_minimum": len(positive) >= protocol["minimum_tasks_with_positive_gain"],
        "dominant_task_share_le_maximum": dominant_share is not None and dominant_share <= protocol["maximum_dominant_added_relation_task_share"],
        "relation_accounting_exact": (
            overall["certified_relations"] == overall["published_unique_edges"] + overall["validity_dominance_edges"]
            and overall["unresolved_relations"] == overall["source_pair_capacity"] - overall["certified_relations"]
        ),
        "unknown_status_not_promoted": True,
    }
    if len(supported) < protocol["minimum_supported_tasks"]:
        status = STATUS_SUPPORT
    elif all(criteria.values()):
        status = STATUS_PASS
    else:
        status = STATUS_BELOW
    summary = {
        "protocol": PROTOCOL,
        "status": status,
        "claim_allowed": status == STATUS_PASS,
        "source_commit": source_commit,
        "input_sha256": {
            "per_parent": protocol["input_per_parent_sha256"],
            "status": protocol["input_status_sha256"],
        },
        "overall": overall,
        "roles": roles,
        "support": {
            "all_tasks": len(tasks),
            "supported_tasks": len(supported),
            "supported_task_ids": [row["stratum"] for row in supported],
            "tasks_with_positive_gain": len(positive),
            "task_ids_with_positive_gain": [row["stratum"] for row in positive],
            "dominant_added_relation_task": dominant["stratum"],
            "dominant_added_relation_task_share": dominant_share,
        },
        "criteria": criteria,
        "prior_art_boundary": {
            "invalid_as_worst_is_novel": False,
            "feasibility_objective_decomposition_is_novel": False,
            "allowed_contribution": "provenance-bound partial-order coverage for natural MLE-agent siblings",
        },
        "scope": {
            "actual_agent_comparison_log_claim": False,
            "complete_choice_set_claim": False,
            "missing_at_random_claim": False,
            "unknown_status_imputed": False,
            "numeric_outcome_read": False,
            "candidate_code_read": False,
            "pair_orientation_read": False,
            "prospective_outcome_read": False,
            "predictor_or_search_utility_claim": False,
            "gpu_hours": 0,
            "api_calls": 0,
            "base_llm_updates": 0,
        },
    }
    return summary, [overall, *roles.values(), *tasks]


def fmt(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, bool):
        return "True" if value else "False"
    if isinstance(value, float):
        return format(value, ".17g")
    return str(value)


def csv_payload(fields: tuple[str, ...], rows: Iterable[dict[str, Any]]) -> list[dict[str, str]]:
    return [{field: fmt(row[field]) for field in fields} for row in rows]


def read_csv(path: Path, fields: tuple[str, ...]) -> list[dict[str, str]]:
    with path.open(encoding="utf-8", newline="") as handle:
        reader = csv.DictReader(handle)
        if tuple(reader.fieldnames or ()) != fields:
            raise VerificationError(f"artifact fields mismatch: {path.name}")
        return list(reader)


def verify(
    protocol_path: Path,
    parent_path: Path,
    status_path: Path,
    source_commit: str,
    artifact: Path,
) -> dict[str, Any]:
    if not HEX40.fullmatch(source_commit):
        raise VerificationError("source commit must be full SHA")
    required = {"aggregate.csv", "per_parent.csv", "sha256_manifest.json", "summary.json"}
    if not artifact.is_dir() or {path.name for path in artifact.iterdir()} != required:
        raise VerificationError("artifact membership mismatch")
    protocol = load_protocol(protocol_path)
    parents = load_parents(parent_path, protocol)
    keys = {(row["role"], row["parent"]) for row in parents}
    statuses = load_statuses(status_path, protocol, keys)
    parent_rows = reconstruct_parents(parents, statuses)
    summary, aggregate_rows = expected_summary(parent_rows, protocol, source_commit)
    if read_csv(artifact / "per_parent.csv", PARENT_FIELDS) != csv_payload(PARENT_FIELDS, parent_rows):
        raise VerificationError("per-parent artifact differs from independent reconstruction")
    if read_csv(artifact / "aggregate.csv", AGGREGATE_FIELDS) != csv_payload(AGGREGATE_FIELDS, aggregate_rows):
        raise VerificationError("aggregate artifact differs from independent reconstruction")
    observed_summary = json.loads((artifact / "summary.json").read_text(encoding="utf-8"))
    if observed_summary != summary:
        raise VerificationError("summary differs from independent reconstruction")
    manifest = json.loads((artifact / "sha256_manifest.json").read_text(encoding="utf-8"))
    expected_manifest = {
        name: digest(artifact / name)
        for name in ("aggregate.csv", "per_parent.csv", "summary.json")
    }
    if manifest != expected_manifest:
        raise VerificationError("artifact manifest mismatch")
    return {
        "status": "INDEPENDENT_STATUS_CERTIFIED_PARTIAL_ORDER_VERIFIED",
        "producer_status": summary["status"],
        "claim_allowed": summary["claim_allowed"],
        "imports_producer": False,
        "parent_rows": len(parent_rows),
        "validity_dominance_edges": summary["overall"]["validity_dominance_edges"],
        "certified_coverage": summary["overall"]["certified_coverage"],
        "coverage_gain": summary["overall"]["coverage_gain"],
        "lost_relation_recovery": summary["overall"]["lost_relation_recovery"],
        "maximum_reconstruction_difference": 0.0,
        "artifact_summary_sha256": expected_manifest["summary.json"],
        "artifact_manifest_sha256": digest(artifact / "sha256_manifest.json"),
        "prospective_outcome_read": False,
    }


def atomic_json(path: Path, payload: dict[str, Any]) -> None:
    if path.exists():
        raise VerificationError(f"output exists: {path}")
    temporary = path.with_suffix(path.suffix + f".tmp.{os.getpid()}")
    temporary.write_text(
        json.dumps(payload, indent=2, sort_keys=True, ensure_ascii=False, allow_nan=False)
        + "\n",
        encoding="utf-8",
        newline="\n",
    )
    os.replace(temporary, path)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--protocol", required=True)
    parser.add_argument("--per-parent", required=True)
    parser.add_argument("--status-jsonl", required=True)
    parser.add_argument("--source-commit", required=True)
    parser.add_argument("--artifact", required=True)
    parser.add_argument("--output", required=True)
    args = parser.parse_args()
    receipt = verify(
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
