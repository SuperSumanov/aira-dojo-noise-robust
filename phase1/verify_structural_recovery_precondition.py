#!/usr/bin/env python3
"""Prove that an exact malformed archive is the first ready unprocessed archive."""
from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

from phase1.prospective_production_runner import (
    ProductionError,
    load_observations,
    ready_archives,
    sha256,
)


class PreconditionError(RuntimeError):
    pass


def verify(
    source_root: Path,
    state_root: Path,
    relative: str,
    expected_sha256: str,
    expected_size: int,
    expected_mtime_ns: int,
    now_epoch: float,
) -> dict[str, object]:
    source_root = source_root.resolve()
    state_root = state_root.resolve()
    if (state_root / "BASELINE_INVALID").exists():
        raise PreconditionError("baseline invalid marker exists")
    observations = load_observations(state_root / "observations.json", source_root)
    ready = ready_archives(observations, now_epoch, 21600, 3, 600)
    if not ready or ready[0] != relative:
        raise PreconditionError("expected malformed archive is not first ready")
    entry = observations["entries"].get(relative)
    if not isinstance(entry, dict):
        raise PreconditionError("expected archive observation is absent")
    archive = (source_root / relative).resolve()
    if archive.parent.parent != source_root or not archive.is_file() or archive.is_symlink():
        raise PreconditionError("archive path binding mismatch")
    stat = archive.stat()
    if stat.st_size != expected_size or stat.st_mtime_ns != expected_mtime_ns:
        raise PreconditionError("archive filesystem metadata mismatch")
    if entry.get("size") != expected_size or entry.get("mtime_ns") != expected_mtime_ns:
        raise PreconditionError("archive observer metadata mismatch")
    if Path(str(entry.get("path"))).resolve() != archive:
        raise PreconditionError("archive observer path mismatch")
    if sha256(archive) != expected_sha256:
        raise PreconditionError("archive SHA mismatch")
    if any(
        entry.get(key) is not None
        for key in (
            "committed_archive_sha256",
            "committed_snapshot_sha256",
            "rejected_archive_sha256",
            "rejection_reason_code",
            "rejection_registry_sha256",
        )
    ):
        raise PreconditionError("archive already has a disposition")
    return {
        "protocol": "prospective_structural_recovery_precondition_v1",
        "status": "EXACT_ARCHIVE_IS_FIRST_READY",
        "archive_relative_path": relative,
        "archive_sha256": expected_sha256,
        "archive_size": expected_size,
        "archive_mtime_ns": expected_mtime_ns,
        "ready_archives": len(ready),
        "minimum_age_seconds": 21600,
        "minimum_observations": 3,
        "minimum_stable_span_seconds": 600,
        "outcomes_read": False,
    }


def write_new(path: Path, value: dict[str, object]) -> None:
    if path.exists():
        raise PreconditionError("output exists")
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(path.name + f".tmp-{os.getpid()}")
    temporary.write_text(
        json.dumps(value, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
        newline="\n",
    )
    temporary.replace(path)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--source-root", required=True, type=Path)
    parser.add_argument("--state-root", required=True, type=Path)
    parser.add_argument("--archive-relative-path", required=True)
    parser.add_argument("--expect-archive-sha256", required=True)
    parser.add_argument("--expect-archive-size", required=True, type=int)
    parser.add_argument("--expect-archive-mtime-ns", required=True, type=int)
    parser.add_argument("--now-epoch", required=True, type=float)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    try:
        receipt = verify(
            args.source_root,
            args.state_root,
            args.archive_relative_path,
            args.expect_archive_sha256,
            args.expect_archive_size,
            args.expect_archive_mtime_ns,
            args.now_epoch,
        )
        write_new(args.output.resolve(), receipt)
        print(json.dumps(receipt, sort_keys=True, separators=(",", ":")))
        return 0
    except (OSError, PreconditionError, ProductionError) as exc:
        print(f"STRUCTURAL_RECOVERY_PRECONDITION_ERROR: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    sys.exit(main())
