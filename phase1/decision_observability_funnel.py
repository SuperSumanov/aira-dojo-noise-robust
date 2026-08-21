#!/usr/bin/env python3
"""Build an outcome-free source-to-published decision observability funnel."""

from __future__ import annotations

import argparse
import csv
import hashlib
import io
import json
import math
import os
import re
import shutil
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any, Iterable


PROTOCOL = "decision-observability-funnel-v1"
STATUS_PASS = "VERIFIED_MATERIAL_COMBINATORIAL_DECISION_ATTRITION"
STATUS_NO_MATERIAL = "VERIFIED_FUNNEL_NO_MATERIAL_COMBINATORIAL_ATTRITION"
STATUS_SUPPORT = "INSUFFICIENT_TASK_SUPPORT_FOR_FUNNEL"
HEX40 = re.compile(r"^[0-9a-f]{40}$")
SHA256 = re.compile(r"^[0-9a-f]{64}$")
ROLES = ("train", "frozen", "extension")
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
FUNNEL_FIELDS = (
    "stratum_type", "stratum", "parents", "runs", "source_children",
    "raw_children", "finite_children", "published_endpoints", "pair_rows",
    "published_unique_edges", "source_pair_capacity", "raw_pair_capacity",
    "finite_pair_capacity", "source_to_raw_pair_loss", "raw_to_finite_pair_loss",
    "finite_to_published_pair_loss", "source_to_finite_child_loss_share",
    "source_to_finite_pair_loss_share", "pair_minus_child_loss_share",
    "pair_attrition_amplification", "finite_pair_retention",
    "published_edge_retention_over_source", "published_edge_coverage_over_finite",
    "source_decision_parents", "finite_decision_parents",
    "published_decision_parents", "decision_parent_survival",
)


class FunnelError(RuntimeError):
    pass


def digest(path: Path) -> str:
    value = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            value.update(chunk)
    return value.hexdigest()


def comb2(value: int) -> int:
    return value * (value - 1) // 2


def load_protocol(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict) or value.get("protocol") != PROTOCOL:
        raise FunnelError("invalid protocol")
    if not SHA256.fullmatch(str(value.get("input_per_parent_sha256", ""))):
        raise FunnelError("invalid input SHA")
    integer_fields = (
        "expected_parent_rows", "minimum_supported_tasks",
        "minimum_task_source_pair_capacity",
        "minimum_tasks_with_pair_loss_gt_child_loss",
    )
    for field in integer_fields:
        item = value.get(field)
        if isinstance(item, bool) or not isinstance(item, int) or item <= 0:
            raise FunnelError(f"invalid protocol integer: {field}")
    for field in (
        "material_min_finite_pair_loss_share",
        "material_min_pair_minus_child_loss_share",
    ):
        item = value.get(field)
        if (
            isinstance(item, bool)
            or not isinstance(item, (int, float))
            or not math.isfinite(float(item))
            or not 0 <= float(item) <= 1
        ):
            raise FunnelError(f"invalid protocol float: {field}")
    counts = value.get("expected_role_parent_counts")
    if (
        not isinstance(counts, dict)
        or set(counts) != set(ROLES)
        or any(isinstance(item, bool) or not isinstance(item, int) or item < 0 for item in counts.values())
        or sum(counts.values()) != value["expected_parent_rows"]
    ):
        raise FunnelError("invalid expected role counts")
    if value.get("require_train_and_frozen_pair_loss_gt_child_loss") is not True:
        raise FunnelError("role gate must remain enabled")
    return value


def parse_bool(value: str, where: str) -> bool:
    if value == "True":
        return True
    if value == "False":
        return False
    raise FunnelError(f"invalid bool at {where}")


def parse_int(value: str, where: str) -> int:
    try:
        result = int(value)
    except ValueError as exc:
        raise FunnelError(f"invalid integer at {where}") from exc
    if result < 0:
        raise FunnelError(f"negative integer at {where}")
    return result


def parse_float(value: str, where: str) -> float:
    try:
        result = float(value)
    except ValueError as exc:
        raise FunnelError(f"invalid float at {where}") from exc
    if not math.isfinite(result):
        raise FunnelError(f"nonfinite float at {where}")
    return result


def load_rows(path: Path, protocol: dict[str, Any]) -> list[dict[str, Any]]:
    if digest(path) != protocol["input_per_parent_sha256"]:
        raise FunnelError("input SHA mismatch")
    rows: list[dict[str, Any]] = []
    seen: set[tuple[str, str]] = set()
    with path.open(encoding="utf-8", newline="") as handle:
        reader = csv.DictReader(handle)
        if tuple(reader.fieldnames or ()) != UPSTREAM_FIELDS:
            raise FunnelError("upstream fields mismatch")
        for line_number, raw in enumerate(reader, 2):
            role, task, run_id, parent = (raw[name] for name in ("role", "task", "run_id", "parent"))
            if role not in ROLES or not task or not run_id or not parent:
                raise FunnelError(f"invalid identity at row {line_number}")
            key = (role, parent)
            if key in seen:
                raise FunnelError("duplicate role-parent")
            seen.add(key)
            values = {
                name: parse_int(raw[name], f"{name}:{line_number}")
                for name in (
                    "pair_rows", "unique_edges", "published_endpoint_count",
                    "raw_card_child_count", "finite_card_child_count",
                    "source_declared_size",
                )
            }
            source = values["source_declared_size"]
            raw_count = values["raw_card_child_count"]
            finite = values["finite_card_child_count"]
            endpoints = values["published_endpoint_count"]
            edges = values["unique_edges"]
            if source <= 0 or not 0 <= finite <= raw_count <= source:
                raise FunnelError(f"invalid child funnel at row {line_number}")
            if endpoints > finite:
                raise FunnelError(f"published endpoints exceed finite candidates at row {line_number}")
            if edges > comb2(endpoints) or values["pair_rows"] < edges:
                raise FunnelError(f"published edges exceed capacity at row {line_number}")
            required_flags = (
                "source_size_consistent", "source_size_not_smaller_than_raw",
                "raw_context_consistent", "endpoints_all_finite", "endpoint_fidelity",
                "declared_matches_finite", "parent_context_consistent",
            )
            if not all(parse_bool(raw[name], f"{name}:{line_number}") for name in required_flags):
                raise FunnelError(f"upstream structural gate failed at row {line_number}")
            raw_retention = parse_float(raw["raw_source_retention"], f"raw retention:{line_number}")
            finite_retention = parse_float(raw["finite_source_retention"], f"finite retention:{line_number}")
            if not math.isclose(raw_retention, raw_count / source, abs_tol=1e-12):
                raise FunnelError(f"raw retention mismatch at row {line_number}")
            if not math.isclose(finite_retention, finite / source, abs_tol=1e-12):
                raise FunnelError(f"finite retention mismatch at row {line_number}")
            rows.append({
                "role": role,
                "task": task,
                "run_id": run_id,
                "parent": parent,
                **values,
            })
    if len(rows) != protocol["expected_parent_rows"]:
        raise FunnelError("parent row count mismatch")
    actual_counts = dict(sorted(Counter(row["role"] for row in rows).items()))
    if actual_counts != protocol["expected_role_parent_counts"]:
        raise FunnelError("role parent counts mismatch")
    return rows


def ratio(numerator: int | float, denominator: int | float) -> float | None:
    return numerator / denominator if denominator else None


def aggregate(rows: Iterable[dict[str, Any]], stratum_type: str, stratum: str) -> dict[str, Any]:
    values = list(rows)
    totals = {
        "parents": len(values),
        "runs": len({(row["role"], row["run_id"]) for row in values}),
        "source_children": sum(row["source_declared_size"] for row in values),
        "raw_children": sum(row["raw_card_child_count"] for row in values),
        "finite_children": sum(row["finite_card_child_count"] for row in values),
        "published_endpoints": sum(row["published_endpoint_count"] for row in values),
        "pair_rows": sum(row["pair_rows"] for row in values),
        "published_unique_edges": sum(row["unique_edges"] for row in values),
        "source_pair_capacity": sum(comb2(row["source_declared_size"]) for row in values),
        "raw_pair_capacity": sum(comb2(row["raw_card_child_count"]) for row in values),
        "finite_pair_capacity": sum(comb2(row["finite_card_child_count"]) for row in values),
        "source_decision_parents": sum(row["source_declared_size"] >= 2 for row in values),
        "finite_decision_parents": sum(row["finite_card_child_count"] >= 2 for row in values),
        "published_decision_parents": sum(row["unique_edges"] >= 1 for row in values),
    }
    if not (
        totals["source_pair_capacity"] >= totals["raw_pair_capacity"]
        >= totals["finite_pair_capacity"] >= totals["published_unique_edges"]
    ):
        raise FunnelError(f"aggregate pair funnel is not monotone for {stratum_type}:{stratum}")
    source_raw_loss = totals["source_pair_capacity"] - totals["raw_pair_capacity"]
    raw_finite_loss = totals["raw_pair_capacity"] - totals["finite_pair_capacity"]
    finite_published_loss = totals["finite_pair_capacity"] - totals["published_unique_edges"]
    child_loss = 1.0 - totals["finite_children"] / totals["source_children"]
    pair_loss = (
        1.0 - totals["finite_pair_capacity"] / totals["source_pair_capacity"]
        if totals["source_pair_capacity"] else 0.0
    )
    output: dict[str, Any] = {
        "stratum_type": stratum_type,
        "stratum": stratum,
        **totals,
        "source_to_raw_pair_loss": source_raw_loss,
        "raw_to_finite_pair_loss": raw_finite_loss,
        "finite_to_published_pair_loss": finite_published_loss,
        "source_to_finite_child_loss_share": child_loss,
        "source_to_finite_pair_loss_share": pair_loss,
        "pair_minus_child_loss_share": pair_loss - child_loss,
        "pair_attrition_amplification": ratio(pair_loss, child_loss),
        "finite_pair_retention": ratio(totals["finite_pair_capacity"], totals["source_pair_capacity"]),
        "published_edge_retention_over_source": ratio(
            totals["published_unique_edges"], totals["source_pair_capacity"]
        ),
        "published_edge_coverage_over_finite": ratio(
            totals["published_unique_edges"], totals["finite_pair_capacity"]
        ),
        "decision_parent_survival": ratio(
            totals["finite_decision_parents"], totals["source_decision_parents"]
        ),
    }
    if source_raw_loss + raw_finite_loss + finite_published_loss != (
        totals["source_pair_capacity"] - totals["published_unique_edges"]
    ):
        raise FunnelError("pair-loss additivity failed")
    return output


def analyze(rows: list[dict[str, Any]], protocol: dict[str, Any], source_commit: str) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    overall = aggregate(rows, "overall", "all")
    by_role = [aggregate((row for row in rows if row["role"] == role), "role", role) for role in ROLES]
    tasks = sorted({row["task"] for row in rows})
    by_task = [aggregate((row for row in rows if row["task"] == task), "task", task) for task in tasks]
    supported = [
        row for row in by_task
        if row["source_pair_capacity"] >= protocol["minimum_task_source_pair_capacity"]
    ]
    task_amplified = [
        row for row in supported
        if row["source_to_finite_pair_loss_share"] > row["source_to_finite_child_loss_share"]
    ]
    role_map = {row["stratum"]: row for row in by_role}
    role_gate = all(
        role_map[role]["source_to_finite_pair_loss_share"]
        > role_map[role]["source_to_finite_child_loss_share"]
        for role in ("train", "frozen")
    )
    support = len(supported) >= protocol["minimum_supported_tasks"]
    criteria = {
        "supported_tasks_ge_minimum": support,
        "finite_pair_loss_share_ge_material_minimum": (
            overall["source_to_finite_pair_loss_share"]
            >= protocol["material_min_finite_pair_loss_share"]
        ),
        "pair_minus_child_loss_share_ge_material_minimum": (
            overall["pair_minus_child_loss_share"]
            >= protocol["material_min_pair_minus_child_loss_share"]
        ),
        "tasks_with_pair_loss_gt_child_loss_ge_minimum": (
            len(task_amplified) >= protocol["minimum_tasks_with_pair_loss_gt_child_loss"]
        ),
        "train_and_frozen_pair_loss_gt_child_loss": role_gate,
        "loss_stages_add_exactly": True,
    }
    status = STATUS_SUPPORT if not support else STATUS_PASS if all(criteria.values()) else STATUS_NO_MATERIAL
    source_pairs_by_task = Counter({row["stratum"]: row["source_pair_capacity"] for row in by_task})
    published_edges_by_task = Counter({row["stratum"]: row["published_unique_edges"] for row in by_task})
    summary = {
        "protocol": PROTOCOL,
        "source_commit": source_commit,
        "status": status,
        "claim_allowed": status == STATUS_PASS,
        "inputs": {
            "per_parent_sha256": protocol["input_per_parent_sha256"],
            "parent_rows": len(rows),
            "role_parent_counts": dict(sorted(Counter(row["role"] for row in rows).items())),
        },
        "overall": overall,
        "roles": {row["stratum"]: row for row in by_role},
        "support": {
            "all_tasks": len(by_task),
            "supported_tasks": len(supported),
            "supported_task_ids": [row["stratum"] for row in supported],
            "tasks_with_pair_loss_gt_child_loss": len(task_amplified),
            "task_ids_with_pair_loss_gt_child_loss": [row["stratum"] for row in task_amplified],
            "minimum_task_source_pair_capacity": protocol["minimum_task_source_pair_capacity"],
            "dominant_source_pair_task": source_pairs_by_task.most_common(1)[0][0],
            "dominant_source_pair_share": ratio(source_pairs_by_task.most_common(1)[0][1], overall["source_pair_capacity"]),
            "dominant_published_edge_task": published_edges_by_task.most_common(1)[0][0],
            "dominant_published_edge_share": ratio(
                published_edges_by_task.most_common(1)[0][1], overall["published_unique_edges"]
            ),
        },
        "criteria": criteria,
        "scope": {
            "candidate_code_read": False,
            "numeric_outcome_read": False,
            "pair_orientation_read": False,
            "prospective_outcome_read": False,
            "complete_choice_set_claim": False,
            "missing_at_random_claim": False,
            "missing_candidate_quality_claim": False,
            "gpu_hours": 0,
            "api_calls": 0,
            "base_llm_updates": 0,
        },
    }
    return summary, [overall, *by_role, *by_task]


def json_bytes(value: Any) -> bytes:
    return (json.dumps(value, indent=2, sort_keys=True, allow_nan=False) + "\n").encode()


def csv_bytes(rows: list[dict[str, Any]]) -> bytes:
    handle = io.StringIO(newline="")
    writer = csv.DictWriter(handle, fieldnames=FUNNEL_FIELDS, extrasaction="ignore", lineterminator="\n")
    writer.writeheader()
    writer.writerows(rows)
    return handle.getvalue().encode()


def write_output(
    output: Path,
    protocol_path: Path,
    input_path: Path,
    source_commit: str,
    summary: dict[str, Any],
    funnel_rows: list[dict[str, Any]],
) -> None:
    if output.exists():
        raise FunnelError("output exists")
    staging = output.with_name(f".{output.name}.tmp-{os.getpid()}")
    if staging.exists():
        shutil.rmtree(staging)
    staging.mkdir(parents=True)
    try:
        files = {
            "funnel.csv": csv_bytes(funnel_rows),
            "input_sha256.txt": (digest(input_path) + "\n").encode(),
            "protocol.json": protocol_path.read_bytes(),
            "source_commit.txt": (source_commit + "\n").encode(),
            "summary.json": json_bytes(summary),
        }
        for name, blob in files.items():
            (staging / name).write_bytes(blob)
        manifest = {name: hashlib.sha256(blob).hexdigest() for name, blob in sorted(files.items())}
        (staging / "sha256_manifest.json").write_bytes(json_bytes(manifest))
        staging.replace(output)
    except Exception:
        shutil.rmtree(staging, ignore_errors=True)
        raise


def run(args: argparse.Namespace) -> int:
    protocol_path = Path(args.protocol).resolve()
    input_path = Path(args.per_parent).resolve()
    output = Path(args.output).resolve()
    if not HEX40.fullmatch(args.source_commit):
        raise FunnelError("source commit must be a full lowercase Git SHA")
    protocol = load_protocol(protocol_path)
    rows = load_rows(input_path, protocol)
    summary, funnel_rows = analyze(rows, protocol, args.source_commit)
    write_output(output, protocol_path, input_path, args.source_commit, summary, funnel_rows)
    print(
        "DECISION_OBSERVABILITY_FUNNEL_COMPLETE "
        f"status={summary['status']} parents={len(rows)} "
        f"source_pairs={summary['overall']['source_pair_capacity']} "
        f"finite_pairs={summary['overall']['finite_pair_capacity']}"
    )
    return 0


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--protocol", required=True)
    parser.add_argument("--per-parent", required=True)
    parser.add_argument("--source-commit", required=True)
    parser.add_argument("--output", required=True)
    return run(parser.parse_args())


if __name__ == "__main__":
    raise SystemExit(main())
