from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path

import pytest

from phase1.verify_structural_recovery_precondition import PreconditionError, verify


def _sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _entry(archive: Path, mtime_ns: int) -> dict[str, object]:
    return {
        "baseline": False,
        "committed_archive_sha256": None,
        "committed_snapshot_sha256": None,
        "first_stable_at_epoch": 10.0,
        "last_observed_at_epoch": 700.0,
        "mtime_ns": mtime_ns,
        "path": str(archive.resolve()),
        "present": True,
        "rejected_archive_sha256": None,
        "rejection_reason_code": None,
        "rejection_registry_sha256": None,
        "size": archive.stat().st_size,
        "stable_observations": 3,
    }


def test_exact_archive_must_be_first_ready(tmp_path: Path) -> None:
    source = tmp_path / "source"
    archive = source / "0819" / "target.tar.gz"
    archive.parent.mkdir(parents=True)
    archive.write_bytes(b"opaque")
    os.utime(archive, ns=(1_000_000_000, 1_000_000_000))
    state = tmp_path / "state"
    state.mkdir()
    observations = {
        "protocol": "prospective_archive_observer_v1",
        "source_root": str(source.resolve()),
        "baseline_sealed_at_epoch": 1.0,
        "entries": {"0819/target.tar.gz": _entry(archive, archive.stat().st_mtime_ns)},
    }
    (state / "observations.json").write_text(json.dumps(observations) + "\n", encoding="utf-8")

    receipt = verify(
        source,
        state,
        "0819/target.tar.gz",
        _sha(archive),
        archive.stat().st_size,
        archive.stat().st_mtime_ns,
        30_000.0,
    )
    assert receipt["status"] == "EXACT_ARCHIVE_IS_FIRST_READY"
    assert receipt["outcomes_read"] is False

    earlier = source / "0819" / "earlier.tar.gz"
    earlier.write_bytes(b"earlier")
    os.utime(earlier, ns=(500_000_000, 500_000_000))
    observations["entries"]["0819/earlier.tar.gz"] = _entry(
        earlier, earlier.stat().st_mtime_ns
    )
    (state / "observations.json").write_text(json.dumps(observations) + "\n", encoding="utf-8")
    with pytest.raises(PreconditionError, match="not first ready"):
        verify(
            source,
            state,
            "0819/target.tar.gz",
            _sha(archive),
            archive.stat().st_size,
            archive.stat().st_mtime_ns,
            30_000.0,
        )
