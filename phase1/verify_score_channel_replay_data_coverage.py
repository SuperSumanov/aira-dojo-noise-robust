#!/usr/bin/env python3
"""Verify that every frozen replay task has nonempty public and private data."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import tempfile
from collections import Counter
from pathlib import Path
from typing import Any


PROTOCOL = "score-channel-replay-data-coverage-v1"
REPLAY_PROTOCOL = "score-channel-replay-manifest-v1"
ROW_PROTOCOL = "score-channel-replay-candidate-v1"


class CoverageError(RuntimeError):
    pass


def digest(path: Path) -> str:
    state = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            state.update(block)
    return state.hexdigest()


def object_file(path: Path, label: str) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        raise CoverageError(f"cannot read {label}") from error
    if not isinstance(value, dict):
        raise CoverageError(f"{label} is not an object")
    return value


def replay_task_counts(replay_dir: Path) -> tuple[Counter[str], str]:
    summary_path = replay_dir / "summary.json"
    manifest_path = replay_dir / "replay_manifest.jsonl"
    summary = object_file(summary_path, "replay summary")
    expected_sha = (summary.get("outputs") or {}).get("replay_manifest_sha256")
    actual_sha = digest(manifest_path)
    if (
        summary.get("protocol") != REPLAY_PROTOCOL
        or summary.get("status") != "REPLAY_MANIFEST_FROZEN_APPROVAL_PENDING"
        or not isinstance(expected_sha, str)
        or actual_sha != expected_sha
    ):
        raise CoverageError("replay summary or manifest binding mismatch")
    counts: Counter[str] = Counter()
    try:
        lines = manifest_path.read_text(encoding="utf-8").splitlines()
    except OSError as error:
        raise CoverageError("cannot read replay manifest") from error
    if not lines or any(not line for line in lines):
        raise CoverageError("replay manifest is empty or contains blank lines")
    for number, line in enumerate(lines, 1):
        try:
            row = json.loads(line)
        except json.JSONDecodeError as error:
            raise CoverageError(f"invalid replay row {number}") from error
        task = row.get("task") if isinstance(row, dict) else None
        if (
            not isinstance(row, dict)
            or row.get("schema_version") != ROW_PROTOCOL
            or not isinstance(task, str)
            or not task
        ):
            raise CoverageError(f"invalid replay identity at row {number}")
        counts[task] += 1
    expected_rows = (summary.get("counts") or {}).get("planned_candidate_replays")
    if isinstance(expected_rows, bool) or expected_rows != sum(counts.values()):
        raise CoverageError("replay count mismatch")
    return counts, actual_sha


def tree_stats(root: Path) -> tuple[int, int]:
    count = 0
    total = 0
    if not root.is_dir():
        return count, total
    for path in root.rglob("*"):
        if path.is_file():
            count += 1
            total += path.stat().st_size
    return count, total


def verify(replay_dir: Path, data_root: Path) -> dict[str, Any]:
    counts, manifest_sha = replay_task_counts(replay_dir)
    tasks = {}
    missing = []
    complete_candidates = 0
    missing_candidates = 0
    for task, candidate_count in sorted(counts.items()):
        prepared = data_root / task / "prepared"
        public_files, public_bytes = tree_stats(prepared / "public")
        private_files, private_bytes = tree_stats(prepared / "private")
        complete = public_files > 0 and private_files > 0
        if not complete:
            missing.append(task)
            missing_candidates += candidate_count
        else:
            complete_candidates += candidate_count
        tasks[task] = {
            "candidate_count": candidate_count,
            "public_files": public_files,
            "public_bytes": public_bytes,
            "private_files": private_files,
            "private_bytes": private_bytes,
            "complete": complete,
        }
    return {
        "protocol": PROTOCOL,
        "status": "PASS_REPLAY_DATA_COVERAGE" if not missing else "FAIL_REPLAY_DATA_COVERAGE",
        "outcomes_read": False,
        "labels_read": False,
        "candidate_code_used": False,
        "data_root": str(data_root.resolve()),
        "replay_manifest_sha256": manifest_sha,
        "counts": {
            "candidate_replays": sum(counts.values()),
            "tasks": len(counts),
            "complete_tasks": len(counts) - len(missing),
            "missing_tasks": len(missing),
            "complete_candidate_replays": complete_candidates,
            "missing_candidate_replays": missing_candidates,
        },
        "missing_tasks": missing,
        "tasks": tasks,
    }


def write_receipt(path: Path, value: dict[str, Any]) -> None:
    if path.exists():
        raise FileExistsError(f"refusing to overwrite receipt: {path}")
    path.parent.mkdir(parents=True, exist_ok=True)
    descriptor, temporary_name = tempfile.mkstemp(prefix=f".{path.name}.", dir=path.parent)
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8", newline="\n") as handle:
            json.dump(value, handle, ensure_ascii=False, sort_keys=True, indent=2, allow_nan=False)
            handle.write("\n")
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary_name, path)
    except Exception:
        try:
            os.unlink(temporary_name)
        except FileNotFoundError:
            pass
        raise


def arguments() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--replay-dir", type=Path, required=True)
    parser.add_argument("--data-root", type=Path, required=True)
    parser.add_argument("--receipt", type=Path, required=True)
    return parser.parse_args()


def main() -> int:
    args = arguments()
    try:
        value = verify(args.replay_dir, args.data_root)
        write_receipt(args.receipt, value)
    except (CoverageError, FileExistsError, OSError) as error:
        print(f"SCORE_CHANNEL_DATA_COVERAGE_ERROR: {error}", file=os.sys.stderr)
        return 2
    print(json.dumps({
        "status": value["status"],
        "counts": value["counts"],
        "missing_tasks": value["missing_tasks"],
        "receipt_sha256": digest(args.receipt),
    }, sort_keys=True, separators=(",", ":")))
    return 0 if value["status"].startswith("PASS_") else 3


if __name__ == "__main__":
    raise SystemExit(main())
