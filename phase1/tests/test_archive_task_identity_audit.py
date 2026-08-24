from __future__ import annotations

import json
import io
import tarfile
from pathlib import Path

from phase1.audit_archive_task_identity import audit, identity_cardinality
from phase1.prospective_drop_intake import sha256


def blob(identities: list[str | None]) -> bytes:
    rows = []
    for step, identity in enumerate(identities):
        metric = {} if identity is None else {"competition_id": identity}
        rows.append(json.dumps({"step": step, "metric_info": metric}))
    return ("\n".join(rows) + "\n").encode("utf-8")


def test_identity_cardinality_does_not_emit_values() -> None:
    assert identity_cardinality(blob([None, None])) == (2, 0)
    assert identity_cardinality(blob(["task-a", "task-a"])) == (2, 1)
    assert identity_cardinality(blob(["task-a", "task-b"])) == (2, 2)


def test_live_only_archive_is_a_distinct_structural_rejection(tmp_path: Path) -> None:
    archive = tmp_path / "live-only.tar.gz"
    payload = b"\xff\xfelive-member-must-not-be-read-or-decoded\n"
    with tarfile.open(archive, "w:gz") as handle:
        info = tarfile.TarInfo("batch/run/json/JOURNAL.jsonl")
        info.size = len(payload)
        info.mtime = 1
        handle.addfile(info, io.BytesIO(payload))

    value = audit(archive, sha256(archive), "a" * 40)

    assert value["status"] == "STRUCTURAL_NO_CHECKPOINT_REJECTION_SUPPORTED"
    assert value["recommended_reason_code"] == "ARCHIVE_HAS_NO_CHECKPOINT_JOURNALS"
    assert value["journals"] == 0
    assert value["invalid_journals"] == 0
    assert value["per_journal"] == []
    assert value["archive_audit"]["checkpoint_runs"] == 0
    assert value["archive_audit"]["live_only_runs_excluded"] == 1
    assert value["security"]["live_event_journal_members_read"] is False
    assert value["outcomes_read"] is False
