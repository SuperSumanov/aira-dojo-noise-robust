from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pytest

from phase1.audit_archive_granularity_retention import (
    RetentionAuditError,
    build_result,
)
from phase1.verify_archive_granularity_retention import (
    VerificationError,
    verify,
)


STRUCTURAL_REASONS = [
    "ARCHIVE_HAS_NO_CHECKPOINT_JOURNALS",
    "JOURNAL_TASK_IDENTITY_ABSENT_ALL_CHECKPOINTS",
    "JOURNAL_TASK_IDENTITY_NOT_EXACTLY_ONE_WITHIN_ARCHIVE",
]
ALIAS_REASON = "ARCHIVE_BYTES_DUPLICATE_COMMITTED_TRANSACTION"


def _write(path: Path, value: object) -> None:
    path.write_text(
        json.dumps(value, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
        newline="\n",
    )


def _hash(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _entry(relative: str) -> dict[str, object]:
    return {
        "baseline": False,
        "committed_archive_sha256": None,
        "committed_snapshot_sha256": None,
        "first_stable_at_epoch": 1.0,
        "last_observed_at_epoch": 2.0,
        "mtime_ns": 3,
        "path": f"/synthetic/source/{relative}",
        "present": True,
        "rejected_archive_sha256": None,
        "rejection_reason_code": None,
        "rejection_registry_sha256": None,
        "size": 4,
        "stable_observations": 3,
    }


def _provenance(
    task: str,
    archive_name: str,
    archive_hash: str,
    run_id: str,
    eligible: bool,
) -> dict[str, object]:
    return {
        "archive_name": archive_name,
        "archive_sha256": archive_hash,
        "eligible": eligible,
        "empty_code_nodes_excluded": 0,
        "endpoints": 10 if eligible else 0,
        "flow_status": "scoreable" if eligible else "unscoreable",
        "generation_started_at_utc": "2026-08-31T00:00:00Z",
        "journal_member": "checkpoint/journal.json",
        "journal_mtime": 1,
        "journal_sha256": "e" * 64,
        "run_id": run_id,
        "task": task,
        "competition_id_source": "explicit_journal",
    }


def _fixture(
    tmp_path: Path,
    *,
    affected_eligible_count: int = 6,
    duplicate_run_identity: bool = False,
) -> tuple[Path, Path, Path, list[str], list[str]]:
    task_names = [f"private-task-{index}" for index in range(8)]
    run_ids = [f"private-run-{index}" for index in range(8)]
    entries: dict[str, dict[str, object]] = {}
    for index in range(2):
        relative = f"legacy/baseline-{index}.tar.gz"
        row = _entry(relative)
        row["baseline"] = True
        entries[relative] = row
    accepted: list[tuple[str, str, str]] = []
    for index, task in enumerate(task_names):
        relative = f"{1000 + index}/{task}-2seeds.tar.gz"
        archive_hash = f"{index + 1:064x}"
        row = _entry(relative)
        row["committed_archive_sha256"] = archive_hash
        entries[relative] = row
        accepted.append((relative, archive_hash, task))
    for index, task in enumerate(task_names[:6]):
        relative = f"{2000 + index}/{task}-2seeds.tar.gz"
        row = _entry(relative)
        row["rejected_archive_sha256"] = f"{100 + index:064x}"
        row["rejection_reason_code"] = STRUCTURAL_REASONS[index % 3]
        row["rejection_registry_sha256"] = f"{200 + index:064x}"
        entries[relative] = row
    alias_relative = "3000/private-alias-only-2seeds.tar.gz"
    alias = _entry(alias_relative)
    alias["rejected_archive_sha256"] = f"{300:064x}"
    alias["rejection_reason_code"] = ALIAS_REASON
    alias["rejection_registry_sha256"] = f"{301:064x}"
    entries[alias_relative] = alias

    state = tmp_path / "state"
    intakes = state / "intakes"
    intakes.mkdir(parents=True)
    transactions: list[dict[str, object]] = []
    eligible_runs = 0
    eligible_endpoints = 0
    for index, (relative, archive_hash, task) in enumerate(accepted):
        drop_id = f"drop-{index}"
        intake = intakes / drop_id
        intake.mkdir()
        eligible = index < affected_eligible_count or index >= 6
        provenance_path = intake / "source_provenance.json"
        _write(
            provenance_path,
            [
                _provenance(
                    task,
                    Path(relative).name,
                    archive_hash,
                    run_ids[0] if duplicate_run_identity and index == 1 else run_ids[index],
                    eligible,
                )
            ],
        )
        eligible_runs += int(eligible)
        eligible_endpoints += 10 * int(eligible)
        summary_path = intake / "summary.json"
        _write(
            summary_path,
            {
                "protocol": "prospective_drop_intake_v1",
                "status": "PROSPECTIVE_DROP_INTAKE_COMPLETE",
                "outputs": {"source_provenance_sha256": _hash(provenance_path)},
                "security": {
                    "env_members_read": False,
                    "live_event_journal_members_read": False,
                    "journal_scanned_before_json": True,
                },
                "blindness": {
                    "labels_used_for_run_selection": False,
                    "labels_used_for_endpoint_selection": False,
                    "label_values_printed": False,
                },
            },
        )
        transactions.append(
            {
                "archive_relative_path": relative,
                "archive_sha256": archive_hash,
                "archive_size": 4,
                "committed_at_utc": "2026-08-31T00:00:00Z",
                "drop_id": drop_id,
                "intake_dir": str(intake.resolve()),
                "intake_summary_sha256": _hash(summary_path),
                "score_dir": str((state / "scores" / drop_id).resolve()),
                "score_summary_sha256": "d" * 64,
            }
        )
    tx_blob = "".join(
        json.dumps(row, sort_keys=True, separators=(",", ":")) + "\n"
        for row in transactions
    ).encode()
    tx_hash = hashlib.sha256(tx_blob).hexdigest()
    manifest_blob = f"{tx_hash}  transactions.jsonl\n".encode()
    latest = hashlib.sha256(manifest_blob).hexdigest()
    snapshot = state / "snapshots" / latest
    snapshot.mkdir(parents=True)
    (snapshot / "transactions.jsonl").write_bytes(tx_blob)
    (snapshot / "SHA256SUMS").write_bytes(manifest_blob)
    for relative, _archive_hash, _task in accepted:
        entries[relative]["committed_snapshot_sha256"] = latest

    observations_path = tmp_path / "observations.json"
    _write(
        observations_path,
        {
            "baseline_sealed_at_epoch": 1.0,
            "entries": entries,
            "protocol": "prospective_archive_observer_v1",
            "source_root": "/synthetic/source",
        },
    )
    prior_path = tmp_path / "prior.json"
    _write(
        prior_path,
        {
            "protocol": "archive_disposition_longitudinal_replication_v2",
            "status": "LONGITUDINAL_ARCHIVE_LEVEL_GATE_REPLICATED",
            "current": {
                "structural_rejected_competitions": 6,
                "structural_mixed_disposition_competitions": 6,
            },
            "access_attestation": {
                "labels_grades_outcomes_predictions_accuracy_or_utility_read": False,
                "candidate_identities_emitted": False,
            },
        },
    )
    prior_verification_path = tmp_path / "prior-verification.json"
    _write(
        prior_verification_path,
        {
            "status": "INDEPENDENT_ARCHIVE_DISPOSITION_REPLICATION_PASS",
            "all_aggregate_fields_equal": True,
            "result_sha256": _hash(prior_path),
        },
    )
    protocol_path = tmp_path / "protocol.json"
    protocol = {
        "protocol": "archive_granularity_retention_audit_v1",
        "frozen_before_retention_count_readout": True,
        "disclosure_at_freeze": {
            "structural_rejected_competition_count_known": 6,
            "structural_mixed_disposition_competition_count_known": 6,
            "affected_competition_identities_read_or_emitted": False,
            "retained_accepted_archive_count_read": False,
            "retained_physical_run_count_read": False,
            "retained_eligible_run_count_read": False,
            "retained_eligible_endpoint_count_read": False,
            "affected_task_dominance_read": False,
        },
        "inputs": {
            "current_latest_snapshot_sha256": latest,
            "current_observations_sha256": _hash(observations_path),
            "current_observations_bytes": observations_path.stat().st_size,
            "archive_disposition_v2_result_path": prior_path.name,
            "archive_disposition_v2_result_sha256": _hash(prior_path),
            "archive_disposition_v2_verification_path": prior_verification_path.name,
            "archive_disposition_v2_verification_sha256": _hash(prior_verification_path),
        },
        "known_structural_metadata_before_readout": {
            "observed_archives": len(entries),
            "baseline_archives": 2,
            "accepted_archives": 8,
            "structural_rejected_archives": 6,
            "alias_quarantined_archives": 1,
            "pending_archives": 0,
            "accepted_tasks": 8,
            "accepted_physical_runs": 8,
            "accepted_eligible_runs": eligible_runs,
            "accepted_eligible_endpoints": eligible_endpoints,
            "structural_rejected_competitions": 6,
            "structural_mixed_disposition_competitions": 6,
            "accepted_single_task_archives": 8,
            "hash_bound_source_provenance_rows": 8,
        },
        "rejection_taxonomy": {
            "structural_target_reasons": STRUCTURAL_REASONS,
            "quarantine_only_reasons": [ALIAS_REASON],
            "aliases_enter_retention_estimand": False,
        },
        "decision_rule": {
            "strong": {
                "minimum_affected_competitions_with_eligible_support": 6,
                "minimum_retained_eligible_run_share": 0.1,
                "minimum_retained_eligible_endpoint_share": 0.1,
                "maximum_dominant_affected_task_eligible_run_share": 0.7,
                "maximum_dominant_affected_task_eligible_endpoint_share": 0.7,
                "status": "ARCHIVE_GRANULARITY_RETENTION_STRONG",
            },
            "partial": {
                "minimum_affected_competitions_with_eligible_support": 4,
                "minimum_retained_eligible_run_share": 0.05,
                "minimum_retained_eligible_endpoint_share": 0.05,
                "maximum_dominant_affected_task_eligible_run_share": 0.85,
                "maximum_dominant_affected_task_eligible_endpoint_share": 0.85,
                "status": "ARCHIVE_GRANULARITY_RETENTION_PARTIAL",
            },
            "kill": {"status": "ARCHIVE_GRANULARITY_RETENTION_NOT_SUPPORTED"},
            "integrity_failure_status": "ARCHIVE_GRANULARITY_RETENTION_INTEGRITY_FAIL",
        },
        "access_contract": {
            "observation_and_hash_bound_intake_metadata_only": True,
            "archive_payloads_opened": False,
            "labels_grades_outcomes_predictions_accuracy_or_utility_read": False,
            "candidate_identities_or_profiles_read": False,
            "archive_task_run_or_candidate_identity_values_emitted": False,
            "gpu_paid_api_model_fit_base_update": "0/0/0/0",
        },
    }
    _write(protocol_path, protocol)
    return protocol_path, observations_path, state, task_names, run_ids


def test_strong_result_and_independent_verifier(tmp_path: Path) -> None:
    protocol, observations, state, task_names, run_ids = _fixture(tmp_path)
    result = build_result(protocol, observations, state)
    assert result["status"] == "ARCHIVE_GRANULARITY_RETENTION_STRONG"
    retained = result["retained_by_archive_granular_validation"]
    assert retained["affected_competitions"] == 6
    assert retained["eligible_runs"] == 6
    assert retained["eligible_endpoints"] == 60
    result_path = tmp_path / "result.json"
    _write(result_path, result)
    receipt = verify(protocol, observations, result_path, state)
    assert receipt["status"] == "INDEPENDENT_ARCHIVE_GRANULARITY_RETENTION_PASS"
    serialized = json.dumps(result, sort_keys=True)
    assert all(task not in serialized for task in task_names)
    assert all(run_id not in serialized for run_id in run_ids)


@pytest.mark.parametrize(
    ("eligible_count", "expected"),
    [
        (4, "ARCHIVE_GRANULARITY_RETENTION_PARTIAL"),
        (3, "ARCHIVE_GRANULARITY_RETENTION_NOT_SUPPORTED"),
    ],
)
def test_partial_and_kill_rules(
    tmp_path: Path, eligible_count: int, expected: str
) -> None:
    protocol, observations, state, _tasks, _runs = _fixture(
        tmp_path, affected_eligible_count=eligible_count
    )
    assert build_result(protocol, observations, state)["status"] == expected


def test_alias_only_task_does_not_enter_affected_set(tmp_path: Path) -> None:
    protocol, observations, state, _tasks, _runs = _fixture(tmp_path)
    result = build_result(protocol, observations, state)
    assert result["retained_by_archive_granular_validation"]["affected_competitions"] == 6


def test_duplicate_run_identity_fails_closed(tmp_path: Path) -> None:
    protocol, observations, state, _tasks, _runs = _fixture(
        tmp_path, duplicate_run_identity=True
    )
    with pytest.raises(RetentionAuditError, match="run identity duplicated"):
        build_result(protocol, observations, state)


def test_known_total_drift_fails_closed(tmp_path: Path) -> None:
    protocol, observations, state, _tasks, _runs = _fixture(tmp_path)
    value = json.loads(protocol.read_text(encoding="utf-8"))
    value["known_structural_metadata_before_readout"]["accepted_eligible_runs"] += 1
    _write(protocol, value)
    with pytest.raises(RetentionAuditError, match="accepted structural totals mismatch"):
        build_result(protocol, observations, state)


def test_prior_hash_drift_fails_closed(tmp_path: Path) -> None:
    protocol, observations, state, _tasks, _runs = _fixture(tmp_path)
    prior = tmp_path / "prior.json"
    prior.write_text(prior.read_text(encoding="utf-8") + " ", encoding="utf-8")
    with pytest.raises(RetentionAuditError, match="prior result hash binding mismatch"):
        build_result(protocol, observations, state)


def test_independent_verifier_rejects_result_mutation(tmp_path: Path) -> None:
    protocol, observations, state, _tasks, _runs = _fixture(tmp_path)
    result = build_result(protocol, observations, state)
    result["retained_by_archive_granular_validation"]["eligible_runs"] += 1
    result_path = tmp_path / "result.json"
    _write(result_path, result)
    with pytest.raises(VerificationError, match="independent reconstruction"):
        verify(protocol, observations, result_path, state)
