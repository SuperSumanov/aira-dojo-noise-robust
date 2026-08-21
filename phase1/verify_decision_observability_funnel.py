#!/usr/bin/env python3
"""Independent verifier for the decision observability funnel."""

from __future__ import annotations

import argparse
import csv
import hashlib
import io
import json
import math
import re
from collections import Counter
from pathlib import Path
from typing import Any, Iterable


PROTOCOL = "decision-observability-funnel-v1"
STATUS_PASS = "VERIFIED_MATERIAL_COMBINATORIAL_DECISION_ATTRITION"
STATUS_NO_MATERIAL = "VERIFIED_FUNNEL_NO_MATERIAL_COMBINATORIAL_ATTRITION"
STATUS_SUPPORT = "INSUFFICIENT_TASK_SUPPORT_FOR_FUNNEL"
HEX40 = re.compile(r"^[0-9a-f]{40}$")
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
ARTIFACT_FILES = {
    "funnel.csv", "input_sha256.txt", "protocol.json", "sha256_manifest.json",
    "source_commit.txt", "summary.json",
}


class VerificationError(RuntimeError):
    pass


def file_sha(path: Path) -> str:
    value = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            value.update(chunk)
    return value.hexdigest()


def comb2(value: int) -> int:
    return value * (value - 1) // 2


def parse_int(value: str, where: str) -> int:
    try:
        result = int(value)
    except ValueError as exc:
        raise VerificationError(f"invalid integer at {where}") from exc
    if result < 0:
        raise VerificationError(f"negative integer at {where}")
    return result


def parse_float(value: str, where: str) -> float:
    try:
        result = float(value)
    except ValueError as exc:
        raise VerificationError(f"invalid float at {where}") from exc
    if not math.isfinite(result):
        raise VerificationError(f"nonfinite float at {where}")
    return result


def parse_bool(value: str, where: str) -> bool:
    if value == "True":
        return True
    if value == "False":
        return False
    raise VerificationError(f"invalid bool at {where}")


def load_protocol(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    required = {
        "expected_parent_rows", "expected_role_parent_counts",
        "input_per_parent_sha256", "material_min_finite_pair_loss_share",
        "material_min_pair_minus_child_loss_share", "minimum_supported_tasks",
        "minimum_task_source_pair_capacity",
        "minimum_tasks_with_pair_loss_gt_child_loss", "protocol",
        "require_train_and_frozen_pair_loss_gt_child_loss",
    }
    if not isinstance(value, dict) or set(value) != required or value["protocol"] != PROTOCOL:
        raise VerificationError("protocol schema mismatch")
    if value["require_train_and_frozen_pair_loss_gt_child_loss"] is not True:
        raise VerificationError("role gate disabled")
    return value


def load_input(path: Path, protocol: dict[str, Any]) -> list[dict[str, Any]]:
    if file_sha(path) != protocol["input_per_parent_sha256"]:
        raise VerificationError("input SHA mismatch")
    rows: list[dict[str, Any]] = []
    identities: set[tuple[str, str]] = set()
    with path.open(encoding="utf-8", newline="") as handle:
        reader = csv.DictReader(handle)
        if tuple(reader.fieldnames or ()) != UPSTREAM_FIELDS:
            raise VerificationError("input fields mismatch")
        for line_number, raw in enumerate(reader, 2):
            role = raw["role"]
            task = raw["task"]
            run_id = raw["run_id"]
            parent = raw["parent"]
            if role not in ROLES or not task or not run_id or not parent:
                raise VerificationError("bad input identity")
            identity = (role, parent)
            if identity in identities:
                raise VerificationError("duplicate role-parent")
            identities.add(identity)
            numeric = {
                name: parse_int(raw[name], f"{name}:{line_number}")
                for name in (
                    "pair_rows", "unique_edges", "published_endpoint_count",
                    "raw_card_child_count", "finite_card_child_count",
                    "source_declared_size",
                )
            }
            source = numeric["source_declared_size"]
            raw_count = numeric["raw_card_child_count"]
            finite = numeric["finite_card_child_count"]
            endpoints = numeric["published_endpoint_count"]
            edges = numeric["unique_edges"]
            if source <= 0 or not 0 <= finite <= raw_count <= source:
                raise VerificationError("bad child funnel")
            if endpoints > finite or edges > comb2(endpoints) or numeric["pair_rows"] < edges:
                raise VerificationError("bad published graph capacity")
            flags = (
                "source_size_consistent", "source_size_not_smaller_than_raw",
                "raw_context_consistent", "endpoints_all_finite", "endpoint_fidelity",
                "declared_matches_finite", "parent_context_consistent",
            )
            if not all(parse_bool(raw[name], f"{name}:{line_number}") for name in flags):
                raise VerificationError("upstream structural flag false")
            if not math.isclose(
                parse_float(raw["raw_source_retention"], "raw retention"),
                raw_count / source,
                abs_tol=1e-12,
            ):
                raise VerificationError("raw retention mismatch")
            if not math.isclose(
                parse_float(raw["finite_source_retention"], "finite retention"),
                finite / source,
                abs_tol=1e-12,
            ):
                raise VerificationError("finite retention mismatch")
            rows.append({"role": role, "task": task, "run_id": run_id, "parent": parent, **numeric})
    if len(rows) != protocol["expected_parent_rows"]:
        raise VerificationError("parent row count mismatch")
    counts = dict(sorted(Counter(row["role"] for row in rows).items()))
    if counts != protocol["expected_role_parent_counts"]:
        raise VerificationError("role parent count mismatch")
    return rows


def ratio(numerator: int | float, denominator: int | float) -> float | None:
    return numerator / denominator if denominator else None


def summarize_group(rows: Iterable[dict[str, Any]], kind: str, name: str) -> dict[str, Any]:
    selected = list(rows)
    result: dict[str, Any] = {
        "stratum_type": kind,
        "stratum": name,
        "parents": len(selected),
        "runs": len({(row["role"], row["run_id"]) for row in selected}),
        "source_children": sum(row["source_declared_size"] for row in selected),
        "raw_children": sum(row["raw_card_child_count"] for row in selected),
        "finite_children": sum(row["finite_card_child_count"] for row in selected),
        "published_endpoints": sum(row["published_endpoint_count"] for row in selected),
        "pair_rows": sum(row["pair_rows"] for row in selected),
        "published_unique_edges": sum(row["unique_edges"] for row in selected),
        "source_pair_capacity": sum(comb2(row["source_declared_size"]) for row in selected),
        "raw_pair_capacity": sum(comb2(row["raw_card_child_count"]) for row in selected),
        "finite_pair_capacity": sum(comb2(row["finite_card_child_count"]) for row in selected),
        "source_decision_parents": sum(row["source_declared_size"] >= 2 for row in selected),
        "finite_decision_parents": sum(row["finite_card_child_count"] >= 2 for row in selected),
        "published_decision_parents": sum(row["unique_edges"] >= 1 for row in selected),
    }
    if not (
        result["source_pair_capacity"] >= result["raw_pair_capacity"]
        >= result["finite_pair_capacity"] >= result["published_unique_edges"]
    ):
        raise VerificationError("nonmonotone aggregate")
    a = result["source_pair_capacity"] - result["raw_pair_capacity"]
    b = result["raw_pair_capacity"] - result["finite_pair_capacity"]
    c = result["finite_pair_capacity"] - result["published_unique_edges"]
    if a + b + c != result["source_pair_capacity"] - result["published_unique_edges"]:
        raise VerificationError("loss additivity mismatch")
    child_loss = 1.0 - result["finite_children"] / result["source_children"]
    pair_loss = (
        1.0 - result["finite_pair_capacity"] / result["source_pair_capacity"]
        if result["source_pair_capacity"] else 0.0
    )
    result.update({
        "source_to_raw_pair_loss": a,
        "raw_to_finite_pair_loss": b,
        "finite_to_published_pair_loss": c,
        "source_to_finite_child_loss_share": child_loss,
        "source_to_finite_pair_loss_share": pair_loss,
        "pair_minus_child_loss_share": pair_loss - child_loss,
        "pair_attrition_amplification": ratio(pair_loss, child_loss),
        "finite_pair_retention": ratio(result["finite_pair_capacity"], result["source_pair_capacity"]),
        "published_edge_retention_over_source": ratio(
            result["published_unique_edges"], result["source_pair_capacity"]
        ),
        "published_edge_coverage_over_finite": ratio(
            result["published_unique_edges"], result["finite_pair_capacity"]
        ),
        "decision_parent_survival": ratio(
            result["finite_decision_parents"], result["source_decision_parents"]
        ),
    })
    return result


def reconstruct(
    rows: list[dict[str, Any]], protocol: dict[str, Any], source_commit: str
) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    overall = summarize_group(rows, "overall", "all")
    role_rows = [
        summarize_group((row for row in rows if row["role"] == role), "role", role)
        for role in ROLES
    ]
    tasks = sorted({row["task"] for row in rows})
    task_rows = [
        summarize_group((row for row in rows if row["task"] == task), "task", task)
        for task in tasks
    ]
    supported = [
        row for row in task_rows
        if row["source_pair_capacity"] >= protocol["minimum_task_source_pair_capacity"]
    ]
    amplified = [
        row for row in supported
        if row["source_to_finite_pair_loss_share"] > row["source_to_finite_child_loss_share"]
    ]
    roles = {row["stratum"]: row for row in role_rows}
    role_gate = all(
        roles[role]["source_to_finite_pair_loss_share"]
        > roles[role]["source_to_finite_child_loss_share"]
        for role in ("train", "frozen")
    )
    support_ok = len(supported) >= protocol["minimum_supported_tasks"]
    criteria = {
        "supported_tasks_ge_minimum": support_ok,
        "finite_pair_loss_share_ge_material_minimum": (
            overall["source_to_finite_pair_loss_share"]
            >= protocol["material_min_finite_pair_loss_share"]
        ),
        "pair_minus_child_loss_share_ge_material_minimum": (
            overall["pair_minus_child_loss_share"]
            >= protocol["material_min_pair_minus_child_loss_share"]
        ),
        "tasks_with_pair_loss_gt_child_loss_ge_minimum": (
            len(amplified) >= protocol["minimum_tasks_with_pair_loss_gt_child_loss"]
        ),
        "train_and_frozen_pair_loss_gt_child_loss": role_gate,
        "loss_stages_add_exactly": True,
    }
    status = STATUS_SUPPORT if not support_ok else STATUS_PASS if all(criteria.values()) else STATUS_NO_MATERIAL
    source_rank = sorted(
        ((row["source_pair_capacity"], row["stratum"]) for row in task_rows),
        key=lambda item: (-item[0], item[1]),
    )
    edge_rank = sorted(
        ((row["published_unique_edges"], row["stratum"]) for row in task_rows),
        key=lambda item: (-item[0], item[1]),
    )
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
        "roles": roles,
        "support": {
            "all_tasks": len(task_rows),
            "supported_tasks": len(supported),
            "supported_task_ids": [row["stratum"] for row in supported],
            "tasks_with_pair_loss_gt_child_loss": len(amplified),
            "task_ids_with_pair_loss_gt_child_loss": [row["stratum"] for row in amplified],
            "minimum_task_source_pair_capacity": protocol["minimum_task_source_pair_capacity"],
            "dominant_source_pair_task": source_rank[0][1],
            "dominant_source_pair_share": ratio(source_rank[0][0], overall["source_pair_capacity"]),
            "dominant_published_edge_task": edge_rank[0][1],
            "dominant_published_edge_share": ratio(edge_rank[0][0], overall["published_unique_edges"]),
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
    return summary, [overall, *role_rows, *task_rows]


def csv_blob(rows: list[dict[str, Any]]) -> bytes:
    handle = io.StringIO(newline="")
    writer = csv.DictWriter(handle, fieldnames=FUNNEL_FIELDS, extrasaction="ignore", lineterminator="\n")
    writer.writeheader()
    writer.writerows(rows)
    return handle.getvalue().encode()


def verify(args: argparse.Namespace) -> int:
    artifact = Path(args.artifact).resolve()
    protocol_path = Path(args.protocol).resolve()
    input_path = Path(args.per_parent).resolve()
    output_path = Path(args.output).resolve()
    if not HEX40.fullmatch(args.source_commit):
        raise VerificationError("bad source commit")
    if not artifact.is_dir() or output_path.exists():
        raise VerificationError("artifact missing or verifier output exists")
    actual_files = {path.name for path in artifact.iterdir() if path.is_file()}
    if actual_files != ARTIFACT_FILES:
        raise VerificationError("artifact file set mismatch")
    manifest = json.loads((artifact / "sha256_manifest.json").read_text(encoding="utf-8"))
    if set(manifest) != ARTIFACT_FILES - {"sha256_manifest.json"}:
        raise VerificationError("artifact manifest file set mismatch")
    for name, expected_sha in manifest.items():
        if file_sha(artifact / name) != expected_sha:
            raise VerificationError(f"artifact hash mismatch: {name}")
    protocol = load_protocol(protocol_path)
    if (artifact / "protocol.json").read_bytes() != protocol_path.read_bytes():
        raise VerificationError("protocol bytes mismatch")
    if (artifact / "source_commit.txt").read_text(encoding="utf-8") != args.source_commit + "\n":
        raise VerificationError("source commit receipt mismatch")
    if (artifact / "input_sha256.txt").read_text(encoding="utf-8") != file_sha(input_path) + "\n":
        raise VerificationError("input receipt mismatch")
    rows = load_input(input_path, protocol)
    expected_summary, expected_rows = reconstruct(rows, protocol, args.source_commit)
    actual_summary = json.loads((artifact / "summary.json").read_text(encoding="utf-8"))
    if actual_summary != expected_summary:
        raise VerificationError("scientific reconstruction mismatch")
    if (artifact / "funnel.csv").read_bytes() != csv_blob(expected_rows):
        raise VerificationError("funnel table reconstruction mismatch")
    receipt = {
        "status": "INDEPENDENT_DECISION_OBSERVABILITY_FUNNEL_VERIFIED",
        "producer_status": actual_summary["status"],
        "claim_allowed": actual_summary["claim_allowed"],
        "parent_rows": len(rows),
        "source_pair_capacity": actual_summary["overall"]["source_pair_capacity"],
        "finite_pair_capacity": actual_summary["overall"]["finite_pair_capacity"],
        "maximum_reconstruction_difference": 0.0,
        "imports_producer": False,
        "prospective_outcome_read": False,
        "artifact_summary_sha256": file_sha(artifact / "summary.json"),
        "artifact_manifest_sha256": file_sha(artifact / "sha256_manifest.json"),
    }
    output_path.write_text(
        json.dumps(receipt, indent=2, sort_keys=True, allow_nan=False) + "\n",
        encoding="utf-8",
        newline="\n",
    )
    print(
        "INDEPENDENT_DECISION_OBSERVABILITY_FUNNEL_VERIFIED "
        f"producer_status={receipt['producer_status']} parents={len(rows)}"
    )
    return 0


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--artifact", required=True)
    parser.add_argument("--protocol", required=True)
    parser.add_argument("--per-parent", required=True)
    parser.add_argument("--source-commit", required=True)
    parser.add_argument("--output", required=True)
    return verify(parser.parse_args())


if __name__ == "__main__":
    raise SystemExit(main())
