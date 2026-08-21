#!/usr/bin/env python3
"""Build a conservative status-certified partial order over source siblings."""

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


class PartialOrderError(RuntimeError):
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


def parse_int(value: str, where: str) -> int:
    try:
        result = int(value)
    except ValueError as error:
        raise PartialOrderError(f"invalid integer at {where}") from error
    if result < 0:
        raise PartialOrderError(f"negative integer at {where}")
    return result


def parse_bool(value: str, where: str) -> bool:
    if value == "True":
        return True
    if value == "False":
        return False
    raise PartialOrderError(f"invalid bool at {where}")


def load_protocol(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict) or value.get("protocol") != PROTOCOL:
        raise PartialOrderError("invalid protocol")
    for field in ("input_per_parent_sha256", "input_status_sha256"):
        if not SHA256.fullmatch(str(value.get(field, ""))):
            raise PartialOrderError(f"invalid protocol hash: {field}")
    integer_fields = (
        "expected_parent_rows", "expected_status_rows",
        "material_min_added_relations", "minimum_supported_tasks",
        "minimum_task_source_pair_capacity", "minimum_tasks_with_positive_gain",
    )
    for field in integer_fields:
        item = value.get(field)
        if isinstance(item, bool) or not isinstance(item, int) or item <= 0:
            raise PartialOrderError(f"invalid protocol integer: {field}")
    for field in (
        "material_min_frozen_coverage_gain", "material_min_gap_recovery_share",
        "material_min_overall_coverage_gain", "material_min_train_coverage_gain",
        "maximum_dominant_added_relation_task_share",
    ):
        item = value.get(field)
        if (
            isinstance(item, bool)
            or not isinstance(item, (int, float))
            or not math.isfinite(float(item))
            or not 0 <= float(item) <= 1
        ):
            raise PartialOrderError(f"invalid protocol fraction: {field}")
    roles = value.get("expected_role_parent_counts")
    if (
        not isinstance(roles, dict)
        or set(roles) != set(ROLES)
        or any(isinstance(item, bool) or not isinstance(item, int) or item < 0 for item in roles.values())
        or sum(roles.values()) != value["expected_parent_rows"]
    ):
        raise PartialOrderError("invalid expected role counts")
    statuses = value.get("expected_status_counts")
    categories = value.get("expected_status_category_counts")
    if (
        not isinstance(statuses, dict)
        or not isinstance(categories, dict)
        or sum(statuses.values()) != value["expected_status_rows"]
        or sum(categories.values()) != value["expected_status_rows"]
    ):
        raise PartialOrderError("invalid expected status accounting")
    certifiable = value.get("certifiable_categories")
    if certifiable != ["EXECUTION_ERROR", "OFFICIAL_GRADE_ABSENT"]:
        raise PartialOrderError("certifiable category contract changed")
    return value


def load_parents(path: Path, protocol: dict[str, Any]) -> list[dict[str, Any]]:
    if digest(path) != protocol["input_per_parent_sha256"]:
        raise PartialOrderError("per-parent input SHA mismatch")
    rows: list[dict[str, Any]] = []
    seen: set[tuple[str, str]] = set()
    with path.open(encoding="utf-8", newline="") as handle:
        reader = csv.DictReader(handle)
        if tuple(reader.fieldnames or ()) != UPSTREAM_FIELDS:
            raise PartialOrderError("upstream parent fields mismatch")
        for line_number, raw in enumerate(reader, 2):
            role, task, run_id, parent = (
                raw[name] for name in ("role", "task", "run_id", "parent")
            )
            if role not in ROLES or not task or not run_id or not parent:
                raise PartialOrderError(f"invalid parent identity at row {line_number}")
            key = (role, parent)
            if key in seen:
                raise PartialOrderError("duplicate role-parent")
            seen.add(key)
            source = parse_int(raw["source_declared_size"], f"source:{line_number}")
            raw_children = parse_int(raw["raw_card_child_count"], f"raw:{line_number}")
            finite = parse_int(raw["finite_card_child_count"], f"finite:{line_number}")
            endpoints = parse_int(raw["published_endpoint_count"], f"endpoints:{line_number}")
            pair_rows = parse_int(raw["pair_rows"], f"pair rows:{line_number}")
            edges = parse_int(raw["unique_edges"], f"edges:{line_number}")
            if source < 2 or not 2 <= finite == raw_children == endpoints <= source:
                raise PartialOrderError(f"parent child funnel incompatible at row {line_number}")
            if edges > comb2(finite) or pair_rows < edges:
                raise PartialOrderError(f"published edge capacity mismatch at row {line_number}")
            flags = (
                "source_size_consistent", "source_size_not_smaller_than_raw",
                "raw_context_consistent", "endpoints_all_finite", "endpoint_fidelity",
                "declared_matches_finite", "parent_context_consistent",
            )
            if not all(parse_bool(raw[name], f"{name}:{line_number}") for name in flags):
                raise PartialOrderError(f"upstream structural gate failed at row {line_number}")
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
        raise PartialOrderError("parent row count mismatch")
    role_counter = Counter(row["role"] for row in rows)
    actual_roles = {role: role_counter[role] for role in ROLES}
    if actual_roles != protocol["expected_role_parent_counts"]:
        raise PartialOrderError("parent role count mismatch")
    return rows


def load_statuses(
    path: Path,
    protocol: dict[str, Any],
    parents: dict[tuple[str, str], dict[str, Any]],
) -> dict[tuple[str, str], dict[str, int]]:
    if digest(path) != protocol["input_status_sha256"]:
        raise PartialOrderError("status input SHA mismatch")
    grouped: dict[tuple[str, str], Counter[str]] = defaultdict(Counter)
    seen_children: set[str] = set()
    status_counts: Counter[str] = Counter()
    category_counts: Counter[str] = Counter()
    with path.open(encoding="utf-8") as handle:
        for line_number, line in enumerate(handle, 1):
            raw = json.loads(line)
            child = raw.get("child_id")
            parent = raw.get("expected_parent_id")
            role = raw.get("role")
            status = raw.get("status")
            category = raw.get("category")
            if not isinstance(child, str) or not child or child in seen_children:
                raise PartialOrderError(f"duplicate or invalid status child at line {line_number}")
            seen_children.add(child)
            key = (role, parent)
            if key not in parents:
                raise PartialOrderError(f"status parent/role absent at line {line_number}")
            if status == "UNIQUE_NODE_RECOVERED":
                if (
                    raw.get("parent_match") is not True
                    or raw.get("journal_parent_id") != parent
                    or not SHA256.fullmatch(str(raw.get("source_journal_sha256", "")))
                    or category == "UNKNOWN"
                ):
                    raise PartialOrderError(f"invalid recovered status at line {line_number}")
            else:
                if status not in {"SOURCE_JOURNAL_NOT_FOUND", "SOURCE_JOURNAL_COLLISION"}:
                    raise PartialOrderError(f"unknown status at line {line_number}")
                if category != "UNKNOWN" or raw.get("parent_match") is not False:
                    raise PartialOrderError(f"unknown status promoted at line {line_number}")
            status_counts[status] += 1
            category_counts[category] += 1
            grouped[key]["targets"] += 1
            if status == "UNIQUE_NODE_RECOVERED" and category in protocol["certifiable_categories"]:
                grouped[key]["certified"] += 1
            else:
                grouped[key]["unknown"] += 1
    if len(seen_children) != protocol["expected_status_rows"]:
        raise PartialOrderError("status row count mismatch")
    if dict(sorted(status_counts.items())) != protocol["expected_status_counts"]:
        raise PartialOrderError("status count mismatch")
    if dict(sorted(category_counts.items())) != protocol["expected_status_category_counts"]:
        raise PartialOrderError("status category count mismatch")
    return {key: dict(value) for key, value in grouped.items()}


def build_parent_rows(
    parents: list[dict[str, Any]],
    statuses: dict[tuple[str, str], dict[str, int]],
) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for parent in parents:
        key = (parent["role"], parent["parent"])
        counts = statuses.get(key, {})
        targets = counts.get("targets", 0)
        certified = counts.get("certified", 0)
        unknown = counts.get("unknown", 0)
        missing_slots = parent["source_children"] - parent["finite_children"]
        if targets > missing_slots or certified + unknown != targets:
            raise PartialOrderError(f"status/missing-slot mismatch: {key}")
        unregistered = missing_slots - targets
        source_capacity = comb2(parent["source_children"])
        published = parent["published_unique_edges"]
        validity_edges = parent["finite_children"] * certified
        certified_relations = published + validity_edges
        if certified_relations > source_capacity:
            raise PartialOrderError(f"certified relations exceed source capacity: {key}")
        lost_gap = source_capacity - published
        rows.append(
            {
                **parent,
                "status_target_children": targets,
                "status_certified_invalid_children": certified,
                "unknown_status_children": unknown,
                "unregistered_missing_slots": unregistered,
                "validity_dominance_edges": validity_edges,
                "certified_relations": certified_relations,
                "unresolved_relations": source_capacity - certified_relations,
                "source_pair_capacity": source_capacity,
                "published_coverage": ratio(published, source_capacity),
                "certified_coverage": ratio(certified_relations, source_capacity),
                "coverage_gain": ratio(validity_edges, source_capacity),
                "lost_relation_recovery": ratio(validity_edges, lost_gap),
            }
        )
    return rows


def aggregate(rows: Iterable[dict[str, Any]], stratum_type: str, stratum: str) -> dict[str, Any]:
    values = list(rows)
    totals = {
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
        totals[field] = sum(int(row[field]) for row in values)
    totals["parents_with_status_targets"] = sum(row["status_target_children"] > 0 for row in values)
    totals["parents_with_added_relations"] = sum(row["validity_dominance_edges"] > 0 for row in values)
    gap = totals["source_pair_capacity"] - totals["published_unique_edges"]
    totals["published_coverage"] = ratio(
        totals["published_unique_edges"], totals["source_pair_capacity"]
    )
    totals["certified_coverage"] = ratio(
        totals["certified_relations"], totals["source_pair_capacity"]
    )
    totals["coverage_gain"] = ratio(
        totals["validity_dominance_edges"], totals["source_pair_capacity"]
    )
    totals["lost_relation_recovery"] = ratio(totals["validity_dominance_edges"], gap)
    return {"stratum_type": stratum_type, "stratum": stratum, **totals}


def summarize(
    rows: list[dict[str, Any]], protocol: dict[str, Any], source_commit: str
) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    overall = aggregate(rows, "overall", "all")
    roles = {
        role: aggregate((row for row in rows if row["role"] == role), "role", role)
        for role in ROLES
    }
    task_ids = sorted({row["task"] for row in rows})
    task_rows = [
        aggregate((row for row in rows if row["task"] == task), "task", task)
        for task in task_ids
    ]
    supported = [
        row
        for row in task_rows
        if row["source_pair_capacity"] >= protocol["minimum_task_source_pair_capacity"]
    ]
    positive = [row for row in supported if row["validity_dominance_edges"] > 0]
    dominant = max(task_rows, key=lambda row: row["validity_dominance_edges"])
    dominant_share = ratio(
        dominant["validity_dominance_edges"], overall["validity_dominance_edges"]
    )
    accounting_exact = (
        overall["certified_relations"]
        == overall["published_unique_edges"] + overall["validity_dominance_edges"]
        and overall["unresolved_relations"]
        == overall["source_pair_capacity"] - overall["certified_relations"]
    )
    criteria = {
        "added_relations_ge_material_minimum": (
            overall["validity_dominance_edges"] >= protocol["material_min_added_relations"]
        ),
        "overall_coverage_gain_ge_material_minimum": (
            overall["coverage_gain"] >= protocol["material_min_overall_coverage_gain"]
        ),
        "gap_recovery_ge_material_minimum": (
            overall["lost_relation_recovery"] >= protocol["material_min_gap_recovery_share"]
        ),
        "train_coverage_gain_ge_material_minimum": (
            roles["train"]["coverage_gain"] >= protocol["material_min_train_coverage_gain"]
        ),
        "frozen_coverage_gain_ge_material_minimum": (
            roles["frozen"]["coverage_gain"] >= protocol["material_min_frozen_coverage_gain"]
        ),
        "tasks_with_positive_gain_ge_minimum": (
            len(positive) >= protocol["minimum_tasks_with_positive_gain"]
        ),
        "dominant_task_share_le_maximum": (
            dominant_share is not None
            and dominant_share <= protocol["maximum_dominant_added_relation_task_share"]
        ),
        "relation_accounting_exact": accounting_exact,
        "unknown_status_not_promoted": True,
    }
    support_ok = len(supported) >= protocol["minimum_supported_tasks"]
    if not support_ok:
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
            "all_tasks": len(task_rows),
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
            "allowed_contribution": (
                "provenance-bound partial-order coverage for natural MLE-agent siblings"
            ),
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
    return summary, [overall, *roles.values(), *task_rows]


def fmt(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, bool):
        return "True" if value else "False"
    if isinstance(value, float):
        return format(value, ".17g")
    return str(value)


def write_csv(path: Path, fields: tuple[str, ...], rows: Iterable[dict[str, Any]]) -> None:
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields, lineterminator="\n")
        writer.writeheader()
        for row in rows:
            writer.writerow({field: fmt(row[field]) for field in fields})


def write_outputs(
    output: Path,
    parent_rows: list[dict[str, Any]],
    aggregate_rows: list[dict[str, Any]],
    summary: dict[str, Any],
) -> None:
    if output.exists():
        raise PartialOrderError(f"output exists: {output}")
    temporary = output.with_name(output.name + f".tmp.{os.getpid()}")
    temporary.mkdir(parents=True)
    write_csv(temporary / "per_parent.csv", PARENT_FIELDS, parent_rows)
    write_csv(temporary / "aggregate.csv", AGGREGATE_FIELDS, aggregate_rows)
    (temporary / "summary.json").write_text(
        json.dumps(summary, indent=2, sort_keys=True, ensure_ascii=False, allow_nan=False)
        + "\n",
        encoding="utf-8",
        newline="\n",
    )
    manifest = {
        name: digest(temporary / name)
        for name in ("aggregate.csv", "per_parent.csv", "summary.json")
    }
    (temporary / "sha256_manifest.json").write_text(
        json.dumps(manifest, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
        newline="\n",
    )
    os.replace(temporary, output)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--protocol", required=True)
    parser.add_argument("--per-parent", required=True)
    parser.add_argument("--status-jsonl", required=True)
    parser.add_argument("--source-commit", required=True)
    parser.add_argument("--output", required=True)
    args = parser.parse_args()
    if not HEX40.fullmatch(args.source_commit):
        raise PartialOrderError("source commit must be full SHA")
    protocol = load_protocol(Path(args.protocol).resolve())
    parents = load_parents(Path(args.per_parent).resolve(), protocol)
    parent_lookup = {(row["role"], row["parent"]): row for row in parents}
    statuses = load_statuses(Path(args.status_jsonl).resolve(), protocol, parent_lookup)
    parent_rows = build_parent_rows(parents, statuses)
    summary, aggregate_rows = summarize(parent_rows, protocol, args.source_commit)
    write_outputs(Path(args.output).resolve(), parent_rows, aggregate_rows, summary)
    print(summary["status"])


if __name__ == "__main__":
    main()
