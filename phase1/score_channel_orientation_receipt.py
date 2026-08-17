#!/usr/bin/env python3
"""Freeze selected-task metric orientations without reading replay outcomes."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import platform
import subprocess
import tempfile
from pathlib import Path
from typing import Any


PROTOCOL = "score-channel-task-orientation-v1"
SELECTION_PROTOCOL = "score-channel-parent-selection-v1"
SELECTION_ROW_SCHEMA = "score-channel-parent-selection-row-v1"
SOURCE_PROTOCOL = "score-channel-metric-orientation-source-v1"
SELECTION_KEYS = {
    "schema_version", "task", "run_id", "parent_id", "source_intake",
    "selection_rank_in_run", "selection_key_sha256", "candidate_card_ids",
    "candidate_count", "candidate_identity_sha256",
}


class OrientationError(RuntimeError):
    """Fail-closed orientation-receipt error."""


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


def valid_sha(value: Any, label: str) -> str:
    if (
        not isinstance(value, str) or len(value) != 64
        or any(character not in "0123456789abcdef" for character in value.lower())
    ):
        raise OrientationError(f"invalid {label}")
    return value.lower()


def read_object(path: Path, label: str) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
        canonical(value)
    except (OSError, json.JSONDecodeError, TypeError, ValueError) as error:
        raise OrientationError(f"cannot read canonical {label}") from error
    if not isinstance(value, dict):
        raise OrientationError(f"{label} is not an object")
    return value


def read_rows(path: Path, label: str) -> list[dict[str, Any]]:
    try:
        lines = path.read_text(encoding="utf-8").splitlines()
    except OSError as error:
        raise OrientationError(f"cannot read {label}") from error
    if not lines or any(not line for line in lines):
        raise OrientationError(f"{label} is empty or contains a blank line")
    rows = []
    for number, line in enumerate(lines, 1):
        try:
            row = json.loads(line)
            canonical(row)
        except (json.JSONDecodeError, TypeError, ValueError) as error:
            raise OrientationError(f"invalid {label} line {number}") from error
        if not isinstance(row, dict):
            raise OrientationError(f"non-object {label} line {number}")
        rows.append(row)
    return rows


def selected_tasks(root: Path) -> tuple[list[str], dict[str, str]]:
    summary_path = root / "summary.json"
    rows_path = root / "selected_parents.jsonl"
    summary = read_object(summary_path, "selection summary")
    if (
        summary.get("protocol") != SELECTION_PROTOCOL
        or summary.get("status") != "PARENT_GATE_PASS_REPLAY_APPROVAL_PENDING"
        or (summary.get("gates") or {}).get("parent_gate_pass") is not True
    ):
        raise OrientationError("parent selection has not passed")
    expected = valid_sha(
        (summary.get("outputs") or {}).get("selected_parents_sha256"),
        "selected-parent SHA",
    )
    if digest(rows_path) != expected:
        raise OrientationError("selected-parent SHA mismatch")
    rows = read_rows(rows_path, "selected parents")
    parents: set[tuple[str, str]] = set()
    tasks: set[str] = set()
    for row in rows:
        key = (row.get("run_id"), row.get("parent_id"))
        task = row.get("task")
        if (
            set(row) != SELECTION_KEYS
            or row.get("schema_version") != SELECTION_ROW_SCHEMA
            or not isinstance(task, str) or not task
            or any(not isinstance(item, str) or not item for item in key)
            or key in parents
        ):
            raise OrientationError("invalid selected-parent identity")
        parents.add(key)
        tasks.add(task)
    if (summary.get("counts") or {}).get("selected_parents") != len(rows):
        raise OrientationError("selected-parent count mismatch")
    return sorted(tasks), {
        "selection_summary_sha256": digest(summary_path),
        "selected_parents_sha256": expected,
    }


def load_sources(legacy_path: Path, supplement_path: Path) -> tuple[dict[str, bool], dict[str, str]]:
    legacy = read_object(legacy_path, "legacy orientation source")
    if any(not isinstance(task, str) or not task or type(value) is not bool for task, value in legacy.items()):
        raise OrientationError("legacy orientation source must map task to bool")
    supplement = read_object(supplement_path, "orientation supplement")
    if (
        supplement.get("protocol") != SOURCE_PROTOCOL
        or supplement.get("created_before_replay_outcomes") is not True
        or supplement.get("outcomes_read") is not False
        or not isinstance(supplement.get("tasks"), dict)
    ):
        raise OrientationError("orientation supplement contract mismatch")
    merged = dict(legacy)
    source = {task: "legacy" for task in legacy}
    for task, row in supplement["tasks"].items():
        if (
            not isinstance(task, str) or not task or not isinstance(row, dict)
            or set(row) != {
                "lower_is_better", "orientation", "leaderboard_rows", "leaderboard_sha256"
            }
            or type(row.get("lower_is_better")) is not bool
            or row.get("orientation") != (-1 if row["lower_is_better"] else 1)
            or isinstance(row.get("leaderboard_rows"), bool)
            or not isinstance(row.get("leaderboard_rows"), int)
            or row["leaderboard_rows"] <= 0
        ):
            raise OrientationError("invalid supplemental orientation row")
        valid_sha(row.get("leaderboard_sha256"), "leaderboard SHA")
        lower = row["lower_is_better"]
        if task in merged and merged[task] is not lower:
            raise OrientationError("legacy/supplement orientation conflict")
        merged[task] = lower
        source[task] = "legacy+supplement" if task in legacy else "supplement"
    return merged, source


def repository_head(root: Path) -> str:
    result = subprocess.run(
        ["git", "-C", str(root), "rev-parse", "HEAD"],
        capture_output=True, text=True, check=False,
    )
    value = result.stdout.strip()
    if result.returncode or len(value) != 40:
        raise OrientationError("cannot resolve source commit")
    return value


def produce(
    selection_dir: Path, legacy_path: Path, supplement_path: Path,
    source_root: Path, out: Path,
) -> dict[str, Any]:
    if out.exists():
        raise FileExistsError(f"refusing to overwrite orientation receipt: {out}")
    tasks, inputs = selected_tasks(selection_dir)
    merged, source = load_sources(legacy_path, supplement_path)
    missing = sorted(set(tasks) - set(merged))
    if missing:
        raise OrientationError(f"selected task has no frozen metric orientation: {missing}")
    lower = {task: merged[task] for task in tasks}
    value = {
        "protocol": PROTOCOL,
        "created_before_replay_outcomes": True,
        "outcomes_read": False,
        "tasks": tasks,
        "lower_is_better": lower,
        "orientation": {task: -1 if lower[task] else 1 for task in tasks},
        "source_by_task": {task: source[task] for task in tasks},
        "inputs": {
            **inputs,
            "legacy_orientation_sha256": digest(legacy_path),
            "orientation_supplement_sha256": digest(supplement_path),
        },
        "implementation": {
            "source_commit": repository_head(source_root),
            "script_sha256": digest(Path(__file__)),
            "python": platform.python_version(),
        },
    }
    out.parent.mkdir(parents=True, exist_ok=True)
    descriptor, temporary_name = tempfile.mkstemp(prefix=f".{out.name}.", dir=out.parent)
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8", newline="\n") as handle:
            handle.write(json.dumps(value, ensure_ascii=False, sort_keys=True, indent=2) + "\n")
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary_name, out)
    except Exception:
        try:
            os.unlink(temporary_name)
        except FileNotFoundError:
            pass
        raise
    return value


def arguments() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--selection-dir", type=Path, required=True)
    parser.add_argument("--legacy", type=Path, required=True)
    parser.add_argument("--supplement", type=Path, required=True)
    parser.add_argument("--source-root", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    return parser.parse_args()


def main() -> int:
    args = arguments()
    try:
        value = produce(
            args.selection_dir, args.legacy, args.supplement, args.source_root, args.out
        )
    except (OrientationError, FileExistsError, OSError) as error:
        print(f"SCORE_CHANNEL_ORIENTATION_ERROR: {error}", file=os.sys.stderr)
        return 2
    print(canonical({
        "status": "SCORE_CHANNEL_ORIENTATION_FROZEN",
        "tasks": value["tasks"],
        "outcomes_read": value["outcomes_read"],
        "receipt_sha256": digest(args.out),
    }))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
