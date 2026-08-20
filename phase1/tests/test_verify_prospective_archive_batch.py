from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path

import pytest

from phase1.verify_prospective_archive_batch import BatchVerificationError, verify


def _sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _fixture(tmp_path: Path) -> tuple[Path, Path, Path, str, dict[str, object]]:
    source = tmp_path / "source"
    archive = source / "0819" / "task.tar.gz"
    archive.parent.mkdir(parents=True)
    archive.write_bytes(b"opaque")
    os.utime(archive, ns=(1_000_000_000, 1_000_000_000))
    row = {
        "archive_mtime_ns": archive.stat().st_mtime_ns,
        "archive_relative_path": "0819/task.tar.gz",
        "archive_sha256": _sha(archive),
        "archive_size": archive.stat().st_size,
    }
    manifest = tmp_path / "manifest.json"
    manifest.write_text(
        json.dumps(
            {
                "entries": [row],
                "outcomes_read": False,
                "protocol": "prospective_archive_batch_manifest_v1",
            },
            sort_keys=True,
        )
        + "\n",
        encoding="utf-8",
    )
    state = tmp_path / "state"
    state.mkdir()
    entry = {
        "baseline": False,
        "committed_archive_sha256": None,
        "committed_snapshot_sha256": None,
        "first_stable_at_epoch": 10.0,
        "last_observed_at_epoch": 700.0,
        "mtime_ns": archive.stat().st_mtime_ns,
        "path": str(archive.resolve()),
        "present": True,
        "rejected_archive_sha256": None,
        "rejection_reason_code": None,
        "rejection_registry_sha256": None,
        "size": archive.stat().st_size,
        "stable_observations": 3,
    }
    (state / "observations.json").write_text(
        json.dumps(
            {
                "protocol": "prospective_archive_observer_v1",
                "source_root": str(source.resolve()),
                "baseline_sealed_at_epoch": 1.0,
                "entries": {"0819/task.tar.gz": entry},
            }
        )
        + "\n",
        encoding="utf-8",
    )
    return source, state, manifest, _sha(manifest), entry


def test_pending_then_committed_batch(tmp_path: Path) -> None:
    source, state, manifest, manifest_sha, entry = _fixture(tmp_path)
    pending = verify(source, state, manifest, manifest_sha, True)
    assert pending["status"] == "BATCH_PENDING"
    assert pending["states"] == {"committed": 0, "rejected": 0, "pending": 1}

    observations = json.loads((state / "observations.json").read_text(encoding="utf-8"))
    observed_entry = observations["entries"]["0819/task.tar.gz"]
    observed_entry["committed_archive_sha256"] = _sha(source / "0819" / "task.tar.gz")
    observed_entry["committed_snapshot_sha256"] = "d" * 64
    (state / "observations.json").write_text(json.dumps(observations) + "\n", encoding="utf-8")
    resolved = verify(source, state, manifest, manifest_sha, False)
    assert resolved["status"] == "BATCH_RESOLVED"
    assert resolved["states"] == {"committed": 1, "rejected": 0, "pending": 0}


def test_rejects_conflicting_disposition(tmp_path: Path) -> None:
    source, state, manifest, manifest_sha, _entry = _fixture(tmp_path)
    observations = json.loads((state / "observations.json").read_text(encoding="utf-8"))
    observed_entry = observations["entries"]["0819/task.tar.gz"]
    observed_entry["committed_archive_sha256"] = _sha(source / "0819" / "task.tar.gz")
    observed_entry["rejected_archive_sha256"] = _sha(source / "0819" / "task.tar.gz")
    (state / "observations.json").write_text(json.dumps(observations) + "\n", encoding="utf-8")
    with pytest.raises(BatchVerificationError, match="both committed and rejected"):
        verify(source, state, manifest, manifest_sha, False)
