from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pytest

from phase1 import verify_score_channel_replay_data_coverage as coverage


def write_rows(path: Path, rows: list[dict]) -> str:
    path.write_text(
        "".join(json.dumps(row, sort_keys=True, separators=(",", ":")) + "\n" for row in rows),
        encoding="utf-8", newline="\n",
    )
    return hashlib.sha256(path.read_bytes()).hexdigest()


def fixture(tmp_path: Path) -> tuple[Path, Path]:
    replay = tmp_path / "replay"
    replay.mkdir()
    rows = [
        {"schema_version": coverage.ROW_PROTOCOL, "task": "task-a", "code": "print(1)"},
        {"schema_version": coverage.ROW_PROTOCOL, "task": "task-a", "code": "print(2)"},
        {"schema_version": coverage.ROW_PROTOCOL, "task": "task-b", "code": "print(3)"},
    ]
    manifest_sha = write_rows(replay / "replay_manifest.jsonl", rows)
    (replay / "summary.json").write_text(json.dumps({
        "protocol": coverage.REPLAY_PROTOCOL,
        "status": "REPLAY_MANIFEST_FROZEN_APPROVAL_PENDING",
        "counts": {"planned_candidate_replays": 3},
        "outputs": {"replay_manifest_sha256": manifest_sha},
    }), encoding="utf-8")
    data = tmp_path / "data"
    for task in ("task-a", "task-b"):
        for split in ("public", "private"):
            root = data / task / "prepared" / split
            root.mkdir(parents=True)
            (root / "sample.bin").write_bytes(b"x")
    return replay, data


def test_complete_public_and_private_data_passes(tmp_path: Path) -> None:
    replay, data = fixture(tmp_path)
    value = coverage.verify(replay, data)
    assert value["status"] == "PASS_REPLAY_DATA_COVERAGE"
    assert value["counts"] == {
        "candidate_replays": 3,
        "tasks": 2,
        "complete_tasks": 2,
        "missing_tasks": 0,
        "complete_candidate_replays": 3,
        "missing_candidate_replays": 0,
    }
    assert value["outcomes_read"] is False
    assert value["candidate_code_used"] is False


def test_empty_private_split_fails_closed(tmp_path: Path) -> None:
    replay, data = fixture(tmp_path)
    (data / "task-b" / "prepared" / "private" / "sample.bin").unlink()
    value = coverage.verify(replay, data)
    assert value["status"] == "FAIL_REPLAY_DATA_COVERAGE"
    assert value["missing_tasks"] == ["task-b"]
    assert value["counts"]["complete_candidate_replays"] == 2
    assert value["counts"]["missing_candidate_replays"] == 1


def test_manifest_tamper_is_rejected(tmp_path: Path) -> None:
    replay, data = fixture(tmp_path)
    with (replay / "replay_manifest.jsonl").open("a", encoding="utf-8") as handle:
        handle.write("{}\n")
    with pytest.raises(coverage.CoverageError, match="binding mismatch"):
        coverage.verify(replay, data)
