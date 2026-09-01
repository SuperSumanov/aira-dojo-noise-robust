from __future__ import annotations

import copy
import hashlib
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
PARENT = ROOT / "phase1/incremental_archive_rejection_support_audit_v1.json"
EXECUTION = ROOT / "phase1/incremental_archive_rejection_support_audit_execution_v2.json"
ADDENDUM = ROOT / "phase1/incremental_archive_rejection_support_execution_addendum_v2.json"
RUNNER = ROOT / "phase1/scripts/run_incremental_archive_rejection_support_formal_20260901.sh"


def load(path: Path) -> dict[str, object]:
    value = json.loads(path.read_text(encoding="utf-8"))
    assert isinstance(value, dict)
    return value


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def test_execution_v2_changes_only_the_frozen_observations_hash() -> None:
    parent = load(PARENT)
    execution = load(EXECUTION)
    expected = copy.deepcopy(parent)
    expected["inputs"]["current_observations_sha256"] = (
        "d2ed361a557bf52dadfe9f0547e49c16ea5dc1eea42a1c78f7b354542a2a704a"
    )
    assert execution == expected


def test_addendum_binds_the_result_free_failure_and_immutable_copy() -> None:
    addendum = load(ADDENDUM)
    assert addendum["parent_protocol_sha256"] == sha(PARENT)
    assert addendum["execution_protocol_sha256"] == sha(EXECUTION)
    assert addendum["failed_attempt"]["producer_started"] is False
    assert addendum["failed_attempt"]["result_files_created"] == 0
    assert addendum["failed_attempt"]["verification_files_created"] == 0
    assert addendum["immutable_observations_copy"]["copy_completed_before_support_readout"] is True
    assert addendum["not_claimed"]["old_and_new_observer_files_differ_only_in_updated_at_utc_claimed"] is False
    assert addendum["scientific_changes"] == []
    assert addendum["resource_changes"] == []
    assert addendum["access_changes"] == []


def test_runner_uses_only_the_immutable_observer_copy() -> None:
    text = RUNNER.read_text(encoding="utf-8")
    expected = (
        'OBSERVATIONS="$STATE_ROOT/frozen_inputs/'
        'incremental_archive_support_20260901_d2ed361a/observations.json"'
    )
    assert text.count(expected) == 1
    assert 'OBSERVATIONS="$STATE_ROOT/observations.json"' not in text
    assert "EXPECTED_OBSERVATIONS_RECEIPT_SHA=" in text
    assert "EXPECTED_SOURCE_ARCHIVES" not in text
