import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path

import pytest

from phase1.score_channel_eligibility_registry import (
    RegistryError,
    load_registry_rows,
    parse_utc,
    repository_head,
    summarize,
)


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def write_intake(
    root: Path,
    name: str,
    rows: list[dict],
    *,
    security_patch: dict | None = None,
    wrong_sha: bool = False,
) -> None:
    directory = root / name
    directory.mkdir(parents=True)
    provenance = directory / "source_provenance.json"
    provenance.write_text(json.dumps(rows, indent=2) + "\n", encoding="utf-8")
    security = {
        "credential_shaped_journals": 0,
        "env_members_extracted": False,
        "env_members_read": False,
        "journal_scanned_before_json": True,
        "live_event_journal_members_read": False,
        "precutoff_code_sha256_overlap": 0,
        "precutoff_endpoint_id_overlap": 0,
        "raw_journals_written": False,
    }
    security.update(security_patch or {})
    summary = {
        "protocol": "prospective_drop_intake_v1",
        "security": security,
        "blindness": {
            "label_values_printed": False,
            "labels_used_for_endpoint_selection": False,
            "labels_used_for_run_selection": False,
            "metrics_computed": [],
        },
        "outputs": {
            "source_provenance_sha256": "0" * 64 if wrong_sha else sha256(provenance)
        },
    }
    (directory / "summary.json").write_text(
        json.dumps(summary, indent=2) + "\n", encoding="utf-8"
    )


def row(index: int, task: str, started: str) -> dict:
    digest = f"{index:064x}"
    return {
        "archive_name": f"archive-{task}.tar.gz",
        "archive_sha256": f"{index + 100:064x}",
        "run_id": f"journal:{digest}",
        "journal_sha256": digest,
        "task": task,
        "generation_started_at_utc": started,
        "flow_status": "must-not-leak",
        "endpoints": 99,
    }


def test_registry_filters_strictly_after_cutoff_and_whitelists_fields(tmp_path: Path) -> None:
    cutoff = parse_utc("2026-08-12T21:31:21Z")
    write_intake(
        tmp_path,
        "intake-a",
        [
            row(1, "task-a", "2026-08-12T21:31:21Z"),
            row(2, "task-a", "2026-08-12T21:31:22Z"),
            row(3, "task-b", "2026-08-13T00:00:00+00:00"),
        ],
    )
    all_rows, eligible, manifests = load_registry_rows(tmp_path, cutoff)
    assert len(all_rows) == 3
    assert len(eligible) == 2
    assert len(manifests) == 1
    assert "flow_status" not in eligible[0]
    assert "endpoints" not in eligible[0]
    assert eligible[0]["generation_started_at_utc"].endswith("Z")


@pytest.mark.parametrize(
    ("security_patch", "message"),
    [
        ({"env_members_read": True}, "unsafe intake flag"),
        ({"credential_shaped_journals": 1}, "unsafe intake flag"),
        ({"journal_scanned_before_json": False}, "unsafe intake flag"),
    ],
)
def test_registry_rejects_unsafe_intake_receipts(
    tmp_path: Path, security_patch: dict, message: str
) -> None:
    write_intake(
        tmp_path,
        "unsafe",
        [row(1, "task", "2026-08-13T00:00:00Z")],
        security_patch=security_patch,
    )
    with pytest.raises(RegistryError, match=message):
        load_registry_rows(tmp_path, parse_utc("2026-08-12T00:00:00Z"))


def test_registry_rejects_provenance_sha_mismatch(tmp_path: Path) -> None:
    write_intake(
        tmp_path,
        "bad-sha",
        [row(1, "task", "2026-08-13T00:00:00Z")],
        wrong_sha=True,
    )
    with pytest.raises(RegistryError, match="SHA mismatch"):
        load_registry_rows(tmp_path, parse_utc("2026-08-12T00:00:00Z"))


def test_registry_rejects_duplicate_physical_journal(tmp_path: Path) -> None:
    duplicate = row(1, "task", "2026-08-13T00:00:00Z")
    write_intake(tmp_path, "one", [duplicate])
    write_intake(tmp_path, "two", [duplicate])
    with pytest.raises(RegistryError, match="duplicate physical journal"):
        load_registry_rows(tmp_path, parse_utc("2026-08-12T00:00:00Z"))


def test_summary_fails_closed_until_both_run_and_balance_gates_pass() -> None:
    rows = [
        {
            "task": task,
            "generation_started_at_utc": "2026-08-13T00:00:00Z",
            "journal_sha256": f"{index:064x}",
        }
        for index, task in enumerate(("a", "a", "b"), start=1)
    ]
    waiting = summarize(rows, rows, [], "c" * 40, "2026-08-12T00:00:00Z", 4, 0.7)
    assert waiting["status"] == "RUN_GATE_WAIT"
    assert waiting["counts"]["remaining_to_min_runs"] == 1
    passed = summarize(rows, rows, [], "c" * 40, "2026-08-12T00:00:00Z", 3, 0.7)
    assert passed["status"] == "RUN_GATE_PASS_PARENT_GATE_PENDING"
    assert passed["gates"]["parent_gate_pending"] is True
    assert passed["gates"]["replay_submission_authorized"] is False


def test_parse_utc_requires_timezone() -> None:
    assert parse_utc("2026-08-13T00:00:00Z") == datetime(
        2026, 8, 13, tzinfo=timezone.utc
    )
    with pytest.raises(RegistryError, match="no timezone"):
        parse_utc("2026-08-13T00:00:00")


def test_repository_head_fails_closed_outside_git(tmp_path: Path) -> None:
    with pytest.raises(RegistryError, match="source commit"):
        repository_head(tmp_path)
