#!/usr/bin/env python3
"""Independent verifier for operator-conditioned retention support artifacts."""

from __future__ import annotations

import argparse
import collections
import csv
import hashlib
import json
import math
import re
import sys
from pathlib import Path
from typing import Any


PROTOCOL = "operator-conditioned-retention-support-v1"
ROLES = ("train", "frozen", "extension")
EXPECTED_ARTIFACTS = {"summary.json", "support_cells.csv", "sha256_manifest.json"}


class VerificationError(RuntimeError):
    pass


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def load_json(path: Path) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise VerificationError(f"invalid JSON: {path.name}") from exc


def parse_protocol(path: Path) -> dict[str, Any]:
    protocol = load_json(path)
    if not isinstance(protocol, dict) or protocol.get("protocol") != PROTOCOL:
        raise VerificationError("protocol mismatch")
    return protocol


def reconstruct(
    parent_path: Path, cards_path: Path, protocol: dict[str, Any]
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    if sha256_file(parent_path) != protocol.get("input_per_parent_sha256"):
        raise VerificationError("per-parent digest mismatch")
    if sha256_file(cards_path) != protocol.get("input_cards_sha256"):
        raise VerificationError("cards digest mismatch")

    parents: list[tuple[str, str, str, str, bool]] = []
    with parent_path.open(encoding="utf-8", newline="") as handle:
        reader = csv.reader(handle)
        try:
            header = next(reader)
        except StopIteration as exc:
            raise VerificationError("empty parent input") from exc
        index = {name: position for position, name in enumerate(header)}
        required = {"role", "task", "run_id", "parent", "parent_card_present"}
        if not required <= set(index) or len(index) != len(header):
            raise VerificationError("parent identity schema mismatch")
        seen: set[tuple[str, str]] = set()
        for line_number, values in enumerate(reader, 2):
            if len(values) != len(header):
                raise VerificationError(f"parent width mismatch at row {line_number}")
            role, task, run_id, parent = (
                values[index[name]] for name in ("role", "task", "run_id", "parent")
            )
            if role not in ROLES or not task or not run_id or not parent:
                raise VerificationError(f"invalid parent identity at row {line_number}")
            present_raw = values[index["parent_card_present"]]
            if present_raw not in {"True", "False"}:
                raise VerificationError(f"invalid parent presence at row {line_number}")
            if (role, parent) in seen:
                raise VerificationError(f"duplicate role-parent at row {line_number}")
            seen.add((role, parent))
            parents.append((role, task, run_id, parent, present_raw == "True"))

    cards: dict[str, tuple[str, str, str]] = {}
    with cards_path.open(encoding="utf-8") as handle:
        for line_number, line in enumerate(handle, 1):
            if not line.strip():
                continue
            row = json.loads(line)
            if not isinstance(row, dict) or not isinstance(row.get("lineage"), dict):
                raise VerificationError(f"invalid card at line {line_number}")
            card_id = row.get("id")
            task = row.get("task")
            run_id = row.get("run_id")
            op = row["lineage"].get("op")
            if not all(isinstance(value, str) and value for value in (card_id, task, run_id, op)):
                raise VerificationError(f"invalid card identity at line {line_number}")
            if card_id in cards:
                raise VerificationError(f"duplicate card id at line {line_number}")
            cards[card_id] = (task, run_id, op)

    if len(parents) != protocol.get("expected_parent_rows"):
        raise VerificationError("parent count mismatch")
    if len(cards) != protocol.get("expected_card_rows"):
        raise VerificationError("card count mismatch")
    role_counts = collections.Counter(parent[0] for parent in parents)
    actual_roles = {role: role_counts[role] for role in ROLES}
    if actual_roles != protocol.get("expected_role_parent_counts"):
        raise VerificationError("role count mismatch")

    grouped: dict[tuple[str, str, str], tuple[int, set[str]]] = {}
    role_runs: dict[str, set[str]] = {role: set() for role in ROLES}
    role_parents: dict[str, set[str]] = {role: set() for role in ROLES}
    joined = missing = presence_mismatch = context_mismatch = 0
    op_counts: collections.Counter[str] = collections.Counter()
    for role, task, run_id, parent, declared_present in parents:
        role_runs[role].add(run_id)
        role_parents[role].add(parent)
        card = cards.get(parent)
        if (card is not None) != declared_present:
            presence_mismatch += 1
        if card is None:
            missing += 1
            continue
        joined += 1
        card_task, card_run, op = card
        if card_task != task or card_run != run_id:
            context_mismatch += 1
            continue
        op_counts[op] += 1
        key = (role, task, op)
        count, runs = grouped.get(key, (0, set()))
        grouped[key] = (count + 1, runs | {run_id})

    cells: list[dict[str, Any]] = []
    for task, op in sorted({(key[1], key[2]) for key in grouped}):
        values: dict[str, tuple[int, int]] = {}
        for role in ROLES:
            count, runs = grouped.get((role, task, op), (0, set()))
            values[role] = (count, len(runs))
        eligible = (
            op in protocol["target_ops"]
            and values["train"][0] >= protocol["minimum_train_parents_per_cell"]
            and values["frozen"][0] >= protocol["minimum_frozen_parents_per_cell"]
            and values["train"][1] >= protocol["minimum_train_runs_per_cell"]
            and values["frozen"][1] >= protocol["minimum_frozen_runs_per_cell"]
        )
        cells.append(
            {
                "task": task,
                "op": op,
                "train_parents": values["train"][0],
                "train_runs": values["train"][1],
                "frozen_parents": values["frozen"][0],
                "frozen_runs": values["frozen"][1],
                "extension_parents": values["extension"][0],
                "extension_runs": values["extension"][1],
                "eligible_primary": eligible,
            }
        )

    eligible_by_task: dict[str, set[str]] = collections.defaultdict(set)
    for row in cells:
        if row["eligible_primary"]:
            eligible_by_task[row["task"]].add(row["op"])
    target_ops = set(protocol["target_ops"])
    supported_tasks = sorted(task for task, ops in eligible_by_task.items() if target_ops <= ops)
    supported_set = set(supported_tasks)
    supported_cells = [
        row
        for row in cells
        if row["task"] in supported_set and row["op"] in target_ops and row["eligible_primary"]
    ]
    frozen_per_task = collections.Counter()
    for row in supported_cells:
        frozen_per_task[row["task"]] += row["frozen_parents"]
    frozen_total = sum(frozen_per_task.values())
    dominant_share = max(frozen_per_task.values(), default=0) / frozen_total if frozen_total else None
    join_coverage = joined / len(parents)
    train_frozen_run_overlap = len(role_runs["train"] & role_runs["frozen"])
    train_frozen_parent_overlap = len(role_parents["train"] & role_parents["frozen"])
    criteria = {
        "parent_join_coverage_ge_minimum": join_coverage >= protocol["minimum_parent_join_coverage"],
        "parent_presence_mismatches_eq_0": presence_mismatch == 0,
        "parent_context_mismatches_eq_0": context_mismatch == 0,
        "train_frozen_run_overlap_eq_0": train_frozen_run_overlap == 0,
        "train_frozen_parent_overlap_eq_0": train_frozen_parent_overlap == 0,
        "supported_tasks_ge_minimum": len(supported_tasks) >= protocol["minimum_supported_tasks"],
        "supported_task_op_cells_ge_minimum": len(supported_cells)
        >= protocol["minimum_supported_task_op_cells"],
        "dominant_frozen_parent_share_le_maximum": dominant_share is not None
        and dominant_share <= protocol["maximum_dominant_frozen_parent_share"],
    }
    inventory = {
        "parent_rows": len(parents),
        "card_rows": len(cards),
        "support_cells": len(cells),
        "joined_parent_cards": joined,
        "missing_parent_cards": missing,
        "parent_join_coverage": join_coverage,
        "parent_presence_mismatches": presence_mismatch,
        "parent_context_mismatches": context_mismatch,
        "observed_parent_op_counts": dict(sorted(op_counts.items())),
        "role_distinct_runs": {role: len(role_runs[role]) for role in ROLES},
        "train_frozen_run_overlap": train_frozen_run_overlap,
        "train_frozen_parent_overlap": train_frozen_parent_overlap,
        "eligible_task_op_cells_before_complete_contrast": sum(row["eligible_primary"] for row in cells),
        "supported_task_op_cells": len(supported_cells),
        "supported_tasks": supported_tasks,
        "supported_frozen_parents": frozen_total,
        "dominant_frozen_parent_share": dominant_share,
    }
    return cells, {"inventory": inventory, "criteria": criteria}


def load_artifact_cells(path: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    with path.open(encoding="utf-8", newline="") as handle:
        reader = csv.DictReader(handle)
        expected = (
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
        if tuple(reader.fieldnames or ()) != expected:
            raise VerificationError("support-cell fields mismatch")
        for line_number, raw in enumerate(reader, 2):
            if raw["eligible_primary"] not in {"True", "False"}:
                raise VerificationError(f"invalid eligibility at support row {line_number}")
            row: dict[str, Any] = {
                "task": raw["task"],
                "op": raw["op"],
                "eligible_primary": raw["eligible_primary"] == "True",
            }
            for field in expected[2:-1]:
                try:
                    value = int(raw[field])
                except ValueError as exc:
                    raise VerificationError(f"invalid count at support row {line_number}") from exc
                if value < 0:
                    raise VerificationError(f"negative count at support row {line_number}")
                row[field] = value
            rows.append(row)
    return rows


def verify(args: argparse.Namespace) -> dict[str, Any]:
    artifact = Path(args.artifact).resolve()
    protocol_path = Path(args.protocol).resolve()
    parent_path = Path(args.per_parent).resolve()
    cards_path = Path(args.cards).resolve()
    if not artifact.is_dir():
        raise VerificationError("artifact directory missing")
    if {path.name for path in artifact.iterdir() if path.is_file()} != EXPECTED_ARTIFACTS:
        raise VerificationError("artifact filenames mismatch")
    manifest = load_json(artifact / "sha256_manifest.json")
    for name in ("summary.json", "support_cells.csv"):
        if not isinstance(manifest, dict) or manifest.get(name) != sha256_file(artifact / name):
            raise VerificationError(f"manifest mismatch for {name}")
    protocol = parse_protocol(protocol_path)
    expected_cells, expected = reconstruct(parent_path, cards_path, protocol)
    actual_cells = load_artifact_cells(artifact / "support_cells.csv")
    if actual_cells != expected_cells:
        raise VerificationError("support-cell reconstruction mismatch")
    summary = load_json(artifact / "summary.json")
    if not isinstance(summary, dict) or summary.get("protocol") != PROTOCOL:
        raise VerificationError("summary protocol mismatch")
    if summary.get("inputs") != {
        "per_parent_sha256": protocol["input_per_parent_sha256"],
        "cards_sha256": protocol["input_cards_sha256"],
    }:
        raise VerificationError("summary inputs mismatch")
    if summary.get("inventory") != expected["inventory"]:
        raise VerificationError("summary inventory mismatch")
    if summary.get("criteria") != expected["criteria"]:
        raise VerificationError("summary criteria mismatch")
    passed = all(expected["criteria"].values())
    expected_status = (
        "OPERATOR_CONDITIONED_RETENTION_TRANSPORT_SUPPORT_FEASIBLE"
        if passed
        else "INSUFFICIENT_OPERATOR_CONDITIONED_RETENTION_SUPPORT"
    )
    if summary.get("status") != expected_status:
        raise VerificationError("summary status mismatch")
    scope = summary.get("scope")
    false_fields = (
        "retention_values_used",
        "pair_orientation_used",
        "numeric_grade_used",
        "code_fields_used_or_emitted",
        "prospective_outcomes_read",
        "causal_operator_effect_claim_allowed",
        "base_llm_updated",
    )
    if not isinstance(scope, dict) or any(scope.get(field) is not False for field in false_fields):
        raise VerificationError("scope permits forbidden analysis or claim")
    if scope.get("s1_effect_analysis_authorized") is not passed or scope.get("gpu") != 0 or scope.get("api_calls") != 0:
        raise VerificationError("scope support authorization mismatch")
    boundaries = summary.get("claim_boundaries")
    if not isinstance(boundaries, dict) or boundaries != {
        "operator_assignment_randomized": False,
        "within_parent_operator_contrast_available": False,
        "operator_effect_identified": False,
        "transport_support_only": True,
    }:
        raise VerificationError("claim boundary mismatch")
    source_commit = summary.get("source_commit")
    if source_commit != args.source_commit or not re.fullmatch(r"[0-9a-f]{40}", source_commit or ""):
        raise VerificationError("source commit mismatch")
    return {
        "protocol": "independent-operator-conditioned-retention-support-verifier-v1",
        "status": "INDEPENDENT_OPERATOR_CONDITIONED_SUPPORT_VERIFIED",
        "producer_status": expected_status,
        "supported_tasks": len(expected["inventory"]["supported_tasks"]),
        "supported_task_op_cells": expected["inventory"]["supported_task_op_cells"],
        "producer_imported": False,
        "summary_sha256": sha256_file(artifact / "summary.json"),
    }


def main() -> int:
    try:
        parser = argparse.ArgumentParser()
        parser.add_argument("--protocol", required=True)
        parser.add_argument("--per-parent", required=True)
        parser.add_argument("--cards", required=True)
        parser.add_argument("--artifact", required=True)
        parser.add_argument("--source-commit", required=True)
        parser.add_argument("--output", required=True)
        args = parser.parse_args()
        result = verify(args)
        output = Path(args.output).resolve()
        if output.exists():
            raise VerificationError("verification output already exists")
        output.write_text(
            json.dumps(result, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
            newline="\n",
        )
        print(json.dumps(result, sort_keys=True, separators=(",", ":")))
        return 0
    except (VerificationError, OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        print(f"OPERATOR_CONDITIONED_RETENTION_SUPPORT_VERIFY_ERROR: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
