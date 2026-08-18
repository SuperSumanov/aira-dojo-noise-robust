#!/usr/bin/env python3
"""Outcome-blind structural support audit for a frozen score-channel cohort."""

from __future__ import annotations

import argparse
import collections
import hashlib
import json
import os
import platform
import subprocess
import tempfile
from pathlib import Path
from typing import Any


PROTOCOL = "score-channel-cohort-support-v1"
SELECTION_PROTOCOL = "score-channel-parent-selection-v1"
SELECTION_STATUS = "PARENT_GATE_PASS_REPLAY_APPROVAL_PENDING"
ROW_SCHEMA = "score-channel-parent-selection-row-v1"
ROW_KEYS = {
    "schema_version", "task", "run_id", "parent_id", "source_intake",
    "selection_rank_in_run", "selection_key_sha256", "candidate_card_ids",
    "candidate_count", "candidate_identity_sha256",
}


class SupportError(RuntimeError):
    """Fail-closed cohort-support error."""


def canonical(value: Any) -> str:
    return json.dumps(
        value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False
    )


def digest(path: Path) -> str:
    state = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            state.update(block)
    return state.hexdigest()


def text_digest(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def valid_sha(value: Any, label: str) -> str:
    if (
        not isinstance(value, str)
        or len(value) != 64
        or any(character not in "0123456789abcdef" for character in value.lower())
    ):
        raise SupportError(f"invalid {label}")
    return value.lower()


def read_object(path: Path, label: str) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
        canonical(value)
    except (OSError, json.JSONDecodeError, TypeError, ValueError) as error:
        raise SupportError(f"cannot read canonical {label}") from error
    if not isinstance(value, dict):
        raise SupportError(f"{label} is not an object")
    return value


def read_rows(path: Path) -> list[dict[str, Any]]:
    try:
        lines = path.read_text(encoding="utf-8").splitlines()
    except OSError as error:
        raise SupportError("cannot read selected parents") from error
    if not lines or any(not line for line in lines):
        raise SupportError("selected parents are empty or contain a blank line")
    rows: list[dict[str, Any]] = []
    for number, line in enumerate(lines, 1):
        try:
            row = json.loads(line)
            canonical(row)
        except (json.JSONDecodeError, TypeError, ValueError) as error:
            raise SupportError(f"invalid selected-parent line {number}") from error
        if not isinstance(row, dict):
            raise SupportError(f"non-object selected-parent line {number}")
        rows.append(row)
    return rows


def repository_head(root: Path) -> str:
    result = subprocess.run(
        ["git", "-C", str(root), "rev-parse", "HEAD"],
        capture_output=True,
        text=True,
        check=False,
    )
    value = result.stdout.strip()
    if result.returncode or len(value) != 40:
        raise SupportError("cannot resolve source commit")
    return value


def histogram(values: list[int]) -> dict[str, int]:
    return {str(key): count for key, count in sorted(collections.Counter(values).items())}


def dominant(counter: collections.Counter[str], denominator: int) -> dict[str, Any]:
    if not counter or denominator <= 0:
        raise SupportError("cannot compute dominant support on an empty cohort")
    task, count = sorted(counter.items(), key=lambda item: (-item[1], item[0]))[0]
    return {
        "task": task,
        "count": count,
        "denominator": denominator,
        "share": count / denominator,
    }


def compute(selection_dir: Path) -> tuple[dict[str, Any], dict[str, str]]:
    summary_path = selection_dir / "summary.json"
    rows_path = selection_dir / "selected_parents.jsonl"
    summary = read_object(summary_path, "selection summary")
    if (
        summary.get("protocol") != SELECTION_PROTOCOL
        or summary.get("status") != SELECTION_STATUS
        or (summary.get("gates") or {}).get("parent_gate_pass") is not True
    ):
        raise SupportError("parent selection is not frozen and passed")
    expected_rows_sha = valid_sha(
        (summary.get("outputs") or {}).get("selected_parents_sha256"),
        "selected-parent SHA",
    )
    if digest(rows_path) != expected_rows_sha:
        raise SupportError("selected-parent SHA mismatch")

    rows = read_rows(rows_path)
    parents: set[tuple[str, str]] = set()
    candidate_ids: set[str] = set()
    run_tasks: dict[str, str] = {}
    task_candidates: collections.Counter[str] = collections.Counter()
    task_parents: collections.Counter[str] = collections.Counter()
    task_runs: dict[str, set[str]] = collections.defaultdict(set)
    run_candidates: collections.Counter[str] = collections.Counter()
    run_parents: collections.Counter[str] = collections.Counter()
    parent_candidate_counts: list[int] = []

    for row in rows:
        if set(row) != ROW_KEYS or row.get("schema_version") != ROW_SCHEMA:
            raise SupportError("selected-parent row schema mismatch")
        task, run_id, parent_id = row.get("task"), row.get("run_id"), row.get("parent_id")
        candidates = row.get("candidate_card_ids")
        if (
            any(not isinstance(value, str) or not value for value in (task, run_id, parent_id))
            or not isinstance(candidates, list)
            or len(candidates) < 2
            or any(not isinstance(card_id, str) or not card_id for card_id in candidates)
            or candidates != sorted(candidates)
            or len(candidates) != len(set(candidates))
            or row.get("candidate_count") != len(candidates)
            or text_digest(canonical(candidates))
            != valid_sha(row.get("candidate_identity_sha256"), "candidate identity SHA")
        ):
            raise SupportError("invalid selected-parent identity or candidates")
        parent_key = (run_id, parent_id)
        if parent_key in parents:
            raise SupportError("duplicate selected parent")
        if any(card_id in candidate_ids for card_id in candidates):
            raise SupportError("candidate appears in more than one selected parent")
        if run_id in run_tasks and run_tasks[run_id] != task:
            raise SupportError("one physical run maps to multiple tasks")
        rank = row.get("selection_rank_in_run")
        if isinstance(rank, bool) or not isinstance(rank, int) or rank < 1:
            raise SupportError("invalid within-run selection rank")
        valid_sha(row.get("selection_key_sha256"), "selection-key SHA")
        if not isinstance(row.get("source_intake"), str) or not row["source_intake"]:
            raise SupportError("invalid source intake")

        parents.add(parent_key)
        candidate_ids.update(candidates)
        run_tasks[run_id] = task
        task_candidates[task] += len(candidates)
        task_parents[task] += 1
        task_runs[task].add(run_id)
        run_candidates[run_id] += len(candidates)
        run_parents[run_id] += 1
        parent_candidate_counts.append(len(candidates))

    counts = summary.get("counts") or {}
    if (
        counts.get("selected_parents") != len(rows)
        or counts.get("selected_candidates") != len(candidate_ids)
    ):
        raise SupportError("selection summary count mismatch")

    task_run_counts = {task: len(task_runs[task]) for task in sorted(task_runs)}
    task_count = len(task_candidates)
    candidate_count = len(candidate_ids)
    squared_mass = sum(count * count for count in task_candidates.values())
    support = {
        "counts": {
            "selected_tasks": task_count,
            "physical_runs": len(run_tasks),
            "selected_parents": len(parents),
            "selected_candidates": candidate_count,
            "unique_candidate_ids": len(candidate_ids),
            "duplicate_candidate_memberships": 0,
        },
        "dominant_task_by_candidates": dominant(task_candidates, candidate_count),
        "dominant_task_by_parents": dominant(task_parents, len(parents)),
        "dominant_task_by_runs": dominant(collections.Counter(task_run_counts), len(run_tasks)),
        "candidate_task_effective_number_hhi": {
            "numerator": candidate_count * candidate_count,
            "denominator": squared_mass,
            "value": candidate_count * candidate_count / squared_mass,
        },
        "task_candidate_counts": dict(sorted(task_candidates.items())),
        "task_parent_counts": dict(sorted(task_parents.items())),
        "task_run_counts": task_run_counts,
        "parent_candidate_count_histogram": histogram(parent_candidate_counts),
        "run_selected_parent_count_histogram": histogram(list(run_parents.values())),
        "run_candidate_count_histogram": histogram(list(run_candidates.values())),
    }
    return support, {
        "selection_summary_sha256": digest(summary_path),
        "selected_parents_sha256": expected_rows_sha,
    }


def produce(selection_dir: Path, repo: Path, out: Path) -> dict[str, Any]:
    if out.exists():
        raise FileExistsError(f"refusing to overwrite cohort-support receipt: {out}")
    support, inputs = compute(selection_dir)
    receipt = {
        "protocol": PROTOCOL,
        "status": "SCORE_CHANNEL_COHORT_SUPPORT_COMPLETE",
        "scope": "outcome_blind_structure_only",
        "inputs": inputs,
        "support": support,
        "blindness": {
            "label_vault_opened": False,
            "label_values_read": False,
            "candidate_code_opened": False,
            "replay_manifest_opened": False,
            "replay_outcomes_opened": False,
            "scientific_metrics_computed": [],
        },
        "implementation": {
            "source_commit": repository_head(repo),
            "script_sha256": digest(Path(__file__)),
            "python": platform.python_version(),
        },
    }
    out.parent.mkdir(parents=True, exist_ok=True)
    descriptor, temporary_name = tempfile.mkstemp(prefix=f".{out.name}.", dir=out.parent)
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8", newline="\n") as handle:
            handle.write(json.dumps(receipt, ensure_ascii=False, indent=2, sort_keys=True) + "\n")
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary_name, out)
    except Exception:
        if os.path.exists(temporary_name):
            os.unlink(temporary_name)
        raise
    return receipt


def arguments() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--selection-dir", required=True, type=Path)
    parser.add_argument("--repo", required=True, type=Path)
    parser.add_argument("--out", required=True, type=Path)
    return parser.parse_args()


def main() -> int:
    args = arguments()
    try:
        receipt = produce(args.selection_dir, args.repo, args.out)
    except (SupportError, FileExistsError, OSError) as error:
        print(f"SCORE_CHANNEL_COHORT_SUPPORT_ERROR: {error}", file=os.sys.stderr)
        return 2
    compact = {
        "status": receipt["status"],
        **receipt["support"]["counts"],
        "dominant_candidate_task": receipt["support"]["dominant_task_by_candidates"],
    }
    print(canonical(compact))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
