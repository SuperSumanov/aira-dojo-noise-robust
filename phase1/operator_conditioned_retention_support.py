#!/usr/bin/env python3
"""Outcome-blind support gate for operator-conditioned retention transport."""

from __future__ import annotations

import argparse
import collections
import csv
import hashlib
import json
import math
import os
import re
import sys
from pathlib import Path
from typing import Any, Sequence


PROTOCOL = "operator-conditioned-retention-support-v1"
STATUS_PASS = "OPERATOR_CONDITIONED_RETENTION_TRANSPORT_SUPPORT_FEASIBLE"
STATUS_FAIL = "INSUFFICIENT_OPERATOR_CONDITIONED_RETENTION_SUPPORT"
ROLES = ("train", "frozen", "extension")
SHA256 = re.compile(r"^[0-9a-f]{64}$")
HEX40 = re.compile(r"^[0-9a-f]{40}$")
CREDENTIAL = re.compile(
    rb"(?:^|[^A-Za-z0-9])(?:sk-(?:ws-)?[A-Za-z0-9._-]{16,}|"
    rb"hf_[A-Za-z0-9]{16,}|gh[pousr]_[A-Za-z0-9]{20,}|"
    rb"AKIA[0-9A-Z]{16}|AIza[0-9A-Za-z_-]{20,}|"
    rb"Bearer\s+[A-Za-z0-9._~-]{20,}|"
    rb"-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----)"
)
UPSTREAM_FIELDS = (
    "role",
    "task",
    "run_id",
    "parent",
    "pair_rows",
    "unique_edges",
    "published_endpoint_count",
    "declared_set_size",
    "raw_card_child_count",
    "finite_card_child_count",
    "source_declared_size",
    "source_size_consistent",
    "source_size_not_smaller_than_raw",
    "raw_context_consistent",
    "endpoints_all_finite",
    "endpoint_fidelity",
    "declared_matches_finite",
    "finite_endpoint_coverage",
    "pair_graph_coverage_over_finite",
    "raw_source_retention",
    "finite_source_retention",
    "raw_equals_source",
    "finite_equals_source",
    "parent_card_present",
    "parent_context_consistent",
    "parent_children_declared_count",
    "parent_children_contains_raw",
    "source_size_gt_five",
)
CELL_FIELDS = (
    "task",
    "op",
    "train_parents",
    "train_runs",
    "frozen_parents",
    "frozen_runs",
    "extension_parents",
    "extension_runs",
    "eligible_primary",
)


class SupportError(RuntimeError):
    pass


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def scan_file(path: Path) -> None:
    overlap = b""
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            payload = overlap + chunk
            if CREDENTIAL.search(payload):
                raise SupportError(f"credential-shaped bytes refused in {path.name}")
            overlap = payload[-256:]


def required_text(value: Any, where: str) -> str:
    if not isinstance(value, str) or not value:
        raise SupportError(f"invalid text at {where}")
    return value


def parse_bool(value: str, where: str) -> bool:
    if value == "True":
        return True
    if value == "False":
        return False
    raise SupportError(f"invalid boolean at {where}")


def positive_int(value: Any, where: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value <= 0:
        raise SupportError(f"invalid positive integer: {where}")
    return value


def load_protocol(path: Path) -> dict[str, Any]:
    scan_file(path)
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise SupportError("invalid protocol JSON") from exc
    if not isinstance(value, dict) or value.get("protocol") != PROTOCOL:
        raise SupportError("invalid protocol identity")
    for name in ("input_per_parent_sha256", "input_cards_sha256"):
        if not isinstance(value.get(name), str) or not SHA256.fullmatch(value[name]):
            raise SupportError(f"invalid protocol digest: {name}")
    for name in (
        "expected_parent_rows",
        "expected_card_rows",
        "minimum_train_parents_per_cell",
        "minimum_frozen_parents_per_cell",
        "minimum_train_runs_per_cell",
        "minimum_frozen_runs_per_cell",
        "minimum_supported_tasks",
        "minimum_supported_task_op_cells",
    ):
        positive_int(value.get(name), name)
    expected_roles = value.get("expected_role_parent_counts")
    if (
        not isinstance(expected_roles, dict)
        or set(expected_roles) != set(ROLES)
        or any(isinstance(count, bool) or not isinstance(count, int) or count < 0 for count in expected_roles.values())
        or sum(expected_roles.values()) != value["expected_parent_rows"]
    ):
        raise SupportError("invalid expected role counts")
    target_ops = value.get("target_ops")
    if (
        not isinstance(target_ops, list)
        or len(target_ops) < 2
        or any(not isinstance(op, str) or not op for op in target_ops)
        or target_ops != sorted(set(target_ops))
    ):
        raise SupportError("invalid target operator set")
    for name in ("minimum_parent_join_coverage", "maximum_dominant_frozen_parent_share"):
        number = value.get(name)
        if isinstance(number, bool) or not isinstance(number, (int, float)) or not math.isfinite(float(number)):
            raise SupportError(f"invalid protocol fraction: {name}")
        if not 0 < float(number) <= 1:
            raise SupportError(f"protocol fraction outside (0,1]: {name}")
    return value


def load_parent_identity(path: Path, protocol: dict[str, Any]) -> list[dict[str, Any]]:
    if sha256_file(path) != protocol["input_per_parent_sha256"]:
        raise SupportError("per-parent input SHA mismatch")
    scan_file(path)
    rows: list[dict[str, Any]] = []
    seen: set[tuple[str, str]] = set()
    with path.open(encoding="utf-8", newline="") as handle:
        reader = csv.DictReader(handle)
        if tuple(reader.fieldnames or ()) != UPSTREAM_FIELDS:
            raise SupportError("per-parent input fields mismatch")
        for line_number, raw in enumerate(reader, 2):
            role = required_text(raw.get("role"), f"parent row {line_number}:role")
            task = required_text(raw.get("task"), f"parent row {line_number}:task")
            run_id = required_text(raw.get("run_id"), f"parent row {line_number}:run")
            parent = required_text(raw.get("parent"), f"parent row {line_number}:parent")
            if role not in ROLES:
                raise SupportError(f"unknown role at parent row {line_number}")
            key = (role, parent)
            if key in seen:
                raise SupportError(f"duplicate role-parent at row {line_number}")
            seen.add(key)
            rows.append(
                {
                    "role": role,
                    "task": task,
                    "run_id": run_id,
                    "parent": parent,
                    "parent_card_present": parse_bool(
                        required_text(raw.get("parent_card_present"), f"parent row {line_number}:present"),
                        f"parent row {line_number}:present",
                    ),
                }
            )
    if len(rows) != protocol["expected_parent_rows"]:
        raise SupportError("unexpected parent row count")
    role_counts = collections.Counter(row["role"] for row in rows)
    actual_roles = {role: role_counts[role] for role in ROLES}
    if actual_roles != protocol["expected_role_parent_counts"]:
        raise SupportError("unexpected role parent counts")
    return rows


def load_card_identity(path: Path, protocol: dict[str, Any]) -> dict[str, dict[str, str]]:
    if sha256_file(path) != protocol["input_cards_sha256"]:
        raise SupportError("cards input SHA mismatch")
    scan_file(path)
    cards: dict[str, dict[str, str]] = {}
    with path.open(encoding="utf-8") as handle:
        for line_number, line in enumerate(handle, 1):
            if not line.strip():
                continue
            try:
                row = json.loads(line)
            except json.JSONDecodeError as exc:
                raise SupportError(f"invalid card JSON at line {line_number}") from exc
            if not isinstance(row, dict):
                raise SupportError(f"card row is not an object at line {line_number}")
            card_id = required_text(row.get("id"), f"card line {line_number}:id")
            if card_id in cards:
                raise SupportError(f"duplicate card id at line {line_number}")
            task = row.get("task")
            if not isinstance(task, dict):
                raise SupportError(f"invalid task object at card line {line_number}")
            lineage = row.get("lineage")
            if not isinstance(lineage, dict):
                raise SupportError(f"invalid lineage at card line {line_number}")
            cards[card_id] = {
                "task": required_text(task.get("name"), f"card line {line_number}:task.name"),
                "run_id": required_text(row.get("run_id"), f"card line {line_number}:run"),
                "op": required_text(lineage.get("op"), f"card line {line_number}:op"),
            }
    if len(cards) != protocol["expected_card_rows"]:
        raise SupportError("unexpected card row count")
    return cards


def build_cells(
    parents: Sequence[dict[str, Any]], cards: dict[str, dict[str, str]], protocol: dict[str, Any]
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    grouped: dict[tuple[str, str, str], dict[str, Any]] = collections.defaultdict(
        lambda: {"parents": 0, "runs": set()}
    )
    joined = 0
    missing = 0
    presence_mismatches = 0
    context_mismatches = 0
    observed_ops: collections.Counter[str] = collections.Counter()
    role_runs: dict[str, set[str]] = {role: set() for role in ROLES}
    role_parents: dict[str, set[str]] = {role: set() for role in ROLES}
    for row in parents:
        role_runs[row["role"]].add(row["run_id"])
        role_parents[row["role"]].add(row["parent"])
        card = cards.get(row["parent"])
        if (card is not None) != row["parent_card_present"]:
            presence_mismatches += 1
        if card is None:
            missing += 1
            continue
        joined += 1
        if card["task"] != row["task"] or card["run_id"] != row["run_id"]:
            context_mismatches += 1
            continue
        op = card["op"]
        observed_ops[op] += 1
        cell = grouped[(row["role"], row["task"], op)]
        cell["parents"] += 1
        cell["runs"].add(row["run_id"])

    task_ops = sorted({(task, op) for _, task, op in grouped})
    cells: list[dict[str, Any]] = []
    for task, op in task_ops:
        counts: dict[str, tuple[int, int]] = {}
        for role in ROLES:
            cell = grouped.get((role, task, op), {"parents": 0, "runs": set()})
            counts[role] = (int(cell["parents"]), len(cell["runs"]))
        eligible = (
            op in protocol["target_ops"]
            and counts["train"][0] >= protocol["minimum_train_parents_per_cell"]
            and counts["frozen"][0] >= protocol["minimum_frozen_parents_per_cell"]
            and counts["train"][1] >= protocol["minimum_train_runs_per_cell"]
            and counts["frozen"][1] >= protocol["minimum_frozen_runs_per_cell"]
        )
        cells.append(
            {
                "task": task,
                "op": op,
                "train_parents": counts["train"][0],
                "train_runs": counts["train"][1],
                "frozen_parents": counts["frozen"][0],
                "frozen_runs": counts["frozen"][1],
                "extension_parents": counts["extension"][0],
                "extension_runs": counts["extension"][1],
                "eligible_primary": eligible,
            }
        )

    eligible_by_task: dict[str, set[str]] = collections.defaultdict(set)
    for row in cells:
        if row["eligible_primary"]:
            eligible_by_task[row["task"]].add(row["op"])
    target_set = set(protocol["target_ops"])
    supported_tasks = sorted(task for task, ops in eligible_by_task.items() if target_set <= ops)
    supported_set = set(supported_tasks)
    supported_cells = [
        row for row in cells if row["task"] in supported_set and row["op"] in target_set and row["eligible_primary"]
    ]
    frozen_per_task = collections.Counter()
    for row in supported_cells:
        frozen_per_task[row["task"]] += row["frozen_parents"]
    supported_frozen = sum(frozen_per_task.values())
    dominant_share = max(frozen_per_task.values(), default=0) / supported_frozen if supported_frozen else None
    train_frozen_run_overlap = len(role_runs["train"] & role_runs["frozen"])
    train_frozen_parent_overlap = len(role_parents["train"] & role_parents["frozen"])
    join_coverage = joined / len(parents)
    criteria = {
        "parent_join_coverage_ge_minimum": join_coverage >= protocol["minimum_parent_join_coverage"],
        "parent_presence_mismatches_eq_0": presence_mismatches == 0,
        "parent_context_mismatches_eq_0": context_mismatches == 0,
        "train_frozen_run_overlap_eq_0": train_frozen_run_overlap == 0,
        "train_frozen_parent_overlap_eq_0": train_frozen_parent_overlap == 0,
        "supported_tasks_ge_minimum": len(supported_tasks) >= protocol["minimum_supported_tasks"],
        "supported_task_op_cells_ge_minimum": len(supported_cells)
        >= protocol["minimum_supported_task_op_cells"],
        "dominant_frozen_parent_share_le_maximum": dominant_share is not None
        and dominant_share <= protocol["maximum_dominant_frozen_parent_share"],
    }
    metadata = {
        "joined_parent_cards": joined,
        "missing_parent_cards": missing,
        "parent_join_coverage": join_coverage,
        "parent_presence_mismatches": presence_mismatches,
        "parent_context_mismatches": context_mismatches,
        "observed_parent_op_counts": dict(sorted(observed_ops.items())),
        "role_distinct_runs": {role: len(role_runs[role]) for role in ROLES},
        "train_frozen_run_overlap": train_frozen_run_overlap,
        "train_frozen_parent_overlap": train_frozen_parent_overlap,
        "eligible_task_op_cells_before_complete_contrast": sum(row["eligible_primary"] for row in cells),
        "supported_task_op_cells": len(supported_cells),
        "supported_tasks": supported_tasks,
        "supported_frozen_parents": supported_frozen,
        "dominant_frozen_parent_share": dominant_share,
        "criteria": criteria,
    }
    return cells, metadata


def summarize(
    parents: Sequence[dict[str, Any]],
    cards: dict[str, dict[str, str]],
    cells: Sequence[dict[str, Any]],
    metadata: dict[str, Any],
    protocol: dict[str, Any],
    source_commit: str,
) -> dict[str, Any]:
    passed = all(metadata["criteria"].values())
    return {
        "protocol": PROTOCOL,
        "status": STATUS_PASS if passed else STATUS_FAIL,
        "source_commit": source_commit,
        "scope": {
            "retention_values_used": False,
            "pair_orientation_used": False,
            "numeric_grade_used": False,
            "code_fields_used_or_emitted": False,
            "prospective_outcomes_read": False,
            "causal_operator_effect_claim_allowed": False,
            "s1_effect_analysis_authorized": passed,
            "gpu": 0,
            "api_calls": 0,
            "base_llm_updated": False,
        },
        "inputs": {
            "per_parent_sha256": protocol["input_per_parent_sha256"],
            "cards_sha256": protocol["input_cards_sha256"],
        },
        "inventory": {
            "parent_rows": len(parents),
            "card_rows": len(cards),
            "support_cells": len(cells),
            **{key: value for key, value in metadata.items() if key != "criteria"},
        },
        "criteria": metadata["criteria"],
        "claim_boundaries": {
            "operator_assignment_randomized": False,
            "within_parent_operator_contrast_available": False,
            "operator_effect_identified": False,
            "transport_support_only": True,
        },
    }


def write_json(path: Path, value: Any) -> None:
    path.write_text(
        json.dumps(value, indent=2, sort_keys=True, ensure_ascii=False) + "\n",
        encoding="utf-8",
        newline="\n",
    )


def run(args: argparse.Namespace) -> int:
    if not isinstance(args.source_commit, str) or not HEX40.fullmatch(args.source_commit):
        raise SupportError("source commit must be a full lowercase SHA-1")
    protocol_path = Path(args.protocol).resolve()
    parent_path = Path(args.per_parent).resolve()
    cards_path = Path(args.cards).resolve()
    for path in (protocol_path, parent_path, cards_path):
        if not path.is_file():
            raise SupportError(f"missing input: {path}")
    protocol = load_protocol(protocol_path)
    parents = load_parent_identity(parent_path, protocol)
    cards = load_card_identity(cards_path, protocol)
    cells, metadata = build_cells(parents, cards, protocol)
    summary = summarize(parents, cards, cells, metadata, protocol, args.source_commit)
    output = Path(args.output).resolve()
    staging = output.with_name(output.name + f".tmp-{os.getpid()}")
    if output.exists() or staging.exists():
        raise SupportError("output path already exists")
    staging.mkdir(parents=True)
    try:
        write_json(staging / "summary.json", summary)
        with (staging / "support_cells.csv").open("w", encoding="utf-8", newline="") as handle:
            writer = csv.DictWriter(handle, fieldnames=CELL_FIELDS, lineterminator="\n")
            writer.writeheader()
            writer.writerows(cells)
        manifest = {
            name: sha256_file(staging / name)
            for name in ("summary.json", "support_cells.csv")
        }
        write_json(staging / "sha256_manifest.json", manifest)
        for path in staging.iterdir():
            scan_file(path)
        staging.replace(output)
    except Exception:
        if staging.exists():
            for child in staging.iterdir():
                child.unlink()
            staging.rmdir()
        raise
    print(json.dumps(summary, sort_keys=True, separators=(",", ":")))
    return 0


def parser() -> argparse.ArgumentParser:
    value = argparse.ArgumentParser()
    value.add_argument("--protocol", required=True)
    value.add_argument("--per-parent", required=True)
    value.add_argument("--cards", required=True)
    value.add_argument("--source-commit", required=True)
    value.add_argument("--output", required=True)
    return value


def main() -> int:
    try:
        return run(parser().parse_args())
    except (SupportError, OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        print(f"OPERATOR_CONDITIONED_RETENTION_SUPPORT_ERROR: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
