#!/usr/bin/env python3
"""Independent verifier for the outcome-blind score-channel support receipt."""

from __future__ import annotations

import argparse
import collections
import hashlib
import json
import math
import os
from pathlib import Path
from typing import Any


EXPECTED_KEYS = {
    "schema_version", "task", "run_id", "parent_id", "source_intake",
    "selection_rank_in_run", "selection_key_sha256", "candidate_card_ids",
    "candidate_count", "candidate_identity_sha256",
}


class VerificationError(RuntimeError):
    """Independent fail-closed verification error."""


def canonical(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False)


def digest(path: Path) -> str:
    state = hashlib.sha256()
    with path.open("rb") as handle:
        while True:
            block = handle.read(1048576)
            if not block:
                return state.hexdigest()
            state.update(block)


def sha_value(value: Any, label: str) -> str:
    if not isinstance(value, str) or len(value) != 64:
        raise VerificationError(f"invalid {label}")
    lowered = value.lower()
    if any(character not in "0123456789abcdef" for character in lowered):
        raise VerificationError(f"invalid {label}")
    return lowered


def object_file(path: Path, label: str) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
        canonical(value)
    except (OSError, json.JSONDecodeError, TypeError, ValueError) as error:
        raise VerificationError(f"cannot read canonical {label}") from error
    if type(value) is not dict:
        raise VerificationError(f"{label} is not an object")
    return value


def row_file(path: Path) -> list[dict[str, Any]]:
    try:
        lines = path.read_text(encoding="utf-8").splitlines()
    except OSError as error:
        raise VerificationError("cannot read selected rows") from error
    if not lines or any(line == "" for line in lines):
        raise VerificationError("selected rows empty or contain blanks")
    output: list[dict[str, Any]] = []
    for line in lines:
        try:
            value = json.loads(line)
            canonical(value)
        except (json.JSONDecodeError, TypeError, ValueError) as error:
            raise VerificationError("invalid selected row") from error
        if type(value) is not dict:
            raise VerificationError("selected row is not an object")
        output.append(value)
    return output


def hist(values: list[int]) -> dict[str, int]:
    counts: dict[int, int] = {}
    for value in values:
        counts[value] = counts.get(value, 0) + 1
    return {str(key): counts[key] for key in sorted(counts)}


def top(counts: dict[str, int], total: int) -> dict[str, Any]:
    name = min(counts, key=lambda key: (-counts[key], key))
    return {"task": name, "count": counts[name], "denominator": total, "share": counts[name] / total}


def rebuild(selection_dir: Path) -> tuple[dict[str, Any], dict[str, str]]:
    summary_path = selection_dir / "summary.json"
    rows_path = selection_dir / "selected_parents.jsonl"
    summary = object_file(summary_path, "selection summary")
    if (
        summary.get("protocol") != "score-channel-parent-selection-v1"
        or summary.get("status") != "PARENT_GATE_PASS_REPLAY_APPROVAL_PENDING"
        or (summary.get("gates") or {}).get("parent_gate_pass") is not True
    ):
        raise VerificationError("selection gate not passed")
    bound_rows_sha = sha_value((summary.get("outputs") or {}).get("selected_parents_sha256"), "row SHA")
    if digest(rows_path) != bound_rows_sha:
        raise VerificationError("selected row hash mismatch")

    rows = row_file(rows_path)
    parent_keys: set[tuple[str, str]] = set()
    cards: set[str] = set()
    run_to_task: dict[str, str] = {}
    candidates_by_task: dict[str, int] = {}
    parents_by_task: dict[str, int] = {}
    runs_by_task: dict[str, set[str]] = collections.defaultdict(set)
    candidates_by_run: dict[str, int] = {}
    parents_by_run: dict[str, int] = {}
    candidate_sizes: list[int] = []

    for row in rows:
        if set(row) != EXPECTED_KEYS or row.get("schema_version") != "score-channel-parent-selection-row-v1":
            raise VerificationError("row schema mismatch")
        task = row.get("task")
        run = row.get("run_id")
        parent = row.get("parent_id")
        intake = row.get("source_intake")
        if any(type(value) is not str or not value for value in (task, run, parent, intake)):
            raise VerificationError("invalid row identity")
        rank = row.get("selection_rank_in_run")
        if type(rank) is not int or rank < 1:
            raise VerificationError("invalid rank")
        sha_value(row.get("selection_key_sha256"), "selection key")
        members = row.get("candidate_card_ids")
        if type(members) is not list or len(members) < 2 or members != sorted(members):
            raise VerificationError("invalid candidate list")
        if any(type(member) is not str or not member for member in members) or len(set(members)) != len(members):
            raise VerificationError("invalid candidate member")
        if row.get("candidate_count") != len(members):
            raise VerificationError("candidate count mismatch")
        identity = hashlib.sha256(canonical(members).encode("utf-8")).hexdigest()
        if identity != sha_value(row.get("candidate_identity_sha256"), "candidate identity"):
            raise VerificationError("candidate identity mismatch")
        key = (run, parent)
        if key in parent_keys or any(member in cards for member in members):
            raise VerificationError("duplicate parent or candidate membership")
        if run in run_to_task and run_to_task[run] != task:
            raise VerificationError("run maps to multiple tasks")

        parent_keys.add(key)
        cards.update(members)
        run_to_task[run] = task
        candidates_by_task[task] = candidates_by_task.get(task, 0) + len(members)
        parents_by_task[task] = parents_by_task.get(task, 0) + 1
        runs_by_task[task].add(run)
        candidates_by_run[run] = candidates_by_run.get(run, 0) + len(members)
        parents_by_run[run] = parents_by_run.get(run, 0) + 1
        candidate_sizes.append(len(members))

    if (
        (summary.get("counts") or {}).get("selected_parents") != len(parent_keys)
        or (summary.get("counts") or {}).get("selected_candidates") != len(cards)
    ):
        raise VerificationError("selection count binding mismatch")

    task_run_counts = {task: len(runs_by_task[task]) for task in sorted(runs_by_task)}
    total_cards = len(cards)
    hhi_denominator = sum(value * value for value in candidates_by_task.values())
    reconstructed = {
        "counts": {
            "selected_tasks": len(candidates_by_task),
            "physical_runs": len(run_to_task),
            "selected_parents": len(parent_keys),
            "selected_candidates": total_cards,
            "unique_candidate_ids": len(cards),
            "duplicate_candidate_memberships": 0,
        },
        "dominant_task_by_candidates": top(candidates_by_task, total_cards),
        "dominant_task_by_parents": top(parents_by_task, len(parent_keys)),
        "dominant_task_by_runs": top(task_run_counts, len(run_to_task)),
        "candidate_task_effective_number_hhi": {
            "numerator": total_cards * total_cards,
            "denominator": hhi_denominator,
            "value": total_cards * total_cards / hhi_denominator,
        },
        "task_candidate_counts": {key: candidates_by_task[key] for key in sorted(candidates_by_task)},
        "task_parent_counts": {key: parents_by_task[key] for key in sorted(parents_by_task)},
        "task_run_counts": task_run_counts,
        "parent_candidate_count_histogram": hist(candidate_sizes),
        "run_selected_parent_count_histogram": hist(list(parents_by_run.values())),
        "run_candidate_count_histogram": hist(list(candidates_by_run.values())),
    }
    return reconstructed, {
        "selection_summary_sha256": digest(summary_path),
        "selected_parents_sha256": bound_rows_sha,
    }


def verify(selection_dir: Path, audit_path: Path, expected_sha: str) -> dict[str, Any]:
    expected_sha = sha_value(expected_sha, "expected audit SHA")
    if digest(audit_path) != expected_sha:
        raise VerificationError("audit receipt SHA mismatch")
    audit = object_file(audit_path, "support audit")
    support, inputs = rebuild(selection_dir)
    if (
        audit.get("protocol") != "score-channel-cohort-support-v1"
        or audit.get("status") != "SCORE_CHANNEL_COHORT_SUPPORT_COMPLETE"
        or audit.get("scope") != "outcome_blind_structure_only"
        or audit.get("inputs") != inputs
        or audit.get("support") != support
        or audit.get("blindness") != {
            "label_vault_opened": False,
            "label_values_read": False,
            "candidate_code_opened": False,
            "replay_manifest_opened": False,
            "replay_outcomes_opened": False,
            "scientific_metrics_computed": [],
        }
    ):
        raise VerificationError("support receipt differs from independent reconstruction")
    if not isinstance(audit.get("implementation"), dict):
        raise VerificationError("implementation receipt missing")
    return {
        "protocol": "score-channel-cohort-support-independent-verifier-v1",
        "status": "VERIFIED_SCORE_CHANNEL_COHORT_SUPPORT",
        "producer_imported": False,
        "outcomes_read": False,
        "support_exact": True,
        "audit_sha256": expected_sha,
        "counts": support["counts"],
        "dominant_task_by_candidates": support["dominant_task_by_candidates"],
    }


def arguments() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--selection-dir", required=True, type=Path)
    parser.add_argument("--audit", required=True, type=Path)
    parser.add_argument("--expect-audit-sha256", required=True)
    parser.add_argument("--receipt", required=True, type=Path)
    return parser.parse_args()


def main() -> int:
    args = arguments()
    try:
        receipt = verify(args.selection_dir, args.audit, args.expect_audit_sha256)
        if args.receipt.exists():
            raise FileExistsError(f"refusing to overwrite verifier receipt: {args.receipt}")
        args.receipt.parent.mkdir(parents=True, exist_ok=True)
        temporary = args.receipt.with_name(args.receipt.name + f".tmp-{os.getpid()}")
        temporary.write_text(json.dumps(receipt, indent=2, sort_keys=True) + "\n", encoding="utf-8", newline="\n")
        os.replace(temporary, args.receipt)
    except (VerificationError, FileExistsError, OSError) as error:
        print(f"SCORE_CHANNEL_COHORT_SUPPORT_VERIFY_ERROR: {error}", file=os.sys.stderr)
        return 2
    print(canonical(receipt))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
