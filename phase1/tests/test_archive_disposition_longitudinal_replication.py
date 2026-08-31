from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pytest

from phase1.audit_archive_disposition_longitudinal_replication import (
    ReplicationError,
    build_result,
)
from phase1.verify_archive_disposition_longitudinal_replication import (
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
        json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
        newline="\n",
    )


def _sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _entry(relative: str) -> dict[str, object]:
    return {
        "baseline": False,
        "committed_archive_sha256": None,
        "committed_snapshot_sha256": None,
        "first_stable_at_epoch": 1.0,
        "last_observed_at_epoch": 2.0,
        "mtime_ns": 3,
        "path": f"/safe/source/{relative}",
        "present": True,
        "rejected_archive_sha256": None,
        "rejection_reason_code": None,
        "rejection_registry_sha256": None,
        "size": 4,
        "stable_observations": 3,
    }


def _historical() -> dict[str, object]:
    competitions = [f"competition-{index}" for index in range(6)]
    return {
        "protocol": "prospective_structural_rejection_ledger_v1",
        "status": "OUTCOME_BLIND_ARCHIVE_DISPOSITION_AUDIT_COMPLETE",
        "counts": {
            "accepted_archive_transactions": 78,
            "baseline_archives": 128,
            "identity_related_rejections": 11,
            "mixed_disposition_competitions": 6,
            "observed_archives": 218,
            "pending_archives": 0,
            "rejected_archives": 12,
            "rejected_competitions": 6,
            "settled_archive_decisions": 90,
        },
        "fractions": {
            "mixed_disposition_over_rejected_competitions": {
                "numerator": 6,
                "denominator": 6,
                "value": 1.0,
            }
        },
        "rejected_competition_timelines": [
            {
                "competition": competition,
                "accepted_archive_transactions": 1,
                "rejected_archives": 2,
            }
            for competition in competitions
        ],
    }


def _observations(
    *, rejected_only: bool = False
) -> tuple[dict[str, object], dict[str, str]]:
    entries: dict[str, object] = {}
    accepted_tasks: dict[str, str] = {}
    serial = 1
    for index in range(128):
        relative = f"legacy-{index % 3}/baseline-{index}.tar.gz"
        row = _entry(relative)
        row["baseline"] = True
        entries[relative] = row
    for index in range(126):
        task = f"competition-{index % 8}"
        basename = (
            f"legacy-bundle-{index}.tar.gz"
            if index < 2
            else f"{task}-4seeds.tar.gz"
        )
        relative = f"{2000 + index:04d}/{basename}"
        row = _entry(relative)
        row["committed_archive_sha256"] = f"{serial:064x}"
        row["committed_snapshot_sha256"] = "f" * 64
        entries[relative] = row
        accepted_tasks[relative] = task
        serial += 1
    structural_reasons = (
        [STRUCTURAL_REASONS[0]] * 2
        + [STRUCTURAL_REASONS[1]] * 2
        + [STRUCTURAL_REASONS[2]] * 9
    )
    for index, reason in enumerate(structural_reasons):
        task = "rejected-only" if rejected_only and index == 0 else f"competition-{index % 8}"
        relative = f"{3000 + index:04d}/{task}-4seeds.tar.gz"
        row = _entry(relative)
        row["rejected_archive_sha256"] = f"{serial:064x}"
        row["rejection_registry_sha256"] = f"{9000 + index:064x}"
        row["rejection_reason_code"] = reason
        entries[relative] = row
        serial += 1
    for index in range(8):
        task = f"competition-{index}"
        relative = f"{4000 + index:04d}/{task}-4seeds.tar.gz"
        row = _entry(relative)
        row["rejected_archive_sha256"] = f"{index + 1:064x}"
        row["rejection_registry_sha256"] = "a" * 64
        row["rejection_reason_code"] = ALIAS_REASON
        entries[relative] = row
    return (
        {
            "baseline_sealed_at_epoch": 1.0,
            "entries": entries,
            "protocol": "prospective_archive_observer_v1",
            "source_root": "/safe/source",
        },
        accepted_tasks,
    )


def _provenance_row(
    task: str,
    archive_name: str,
    archive_sha: str,
    *,
    include_competition_source: bool,
) -> dict[str, object]:
    row: dict[str, object] = {
        "archive_name": archive_name,
        "archive_sha256": archive_sha,
        "eligible": True,
        "empty_code_nodes_excluded": 0,
        "endpoints": 2,
        "flow_status": "scoreable",
        "generation_started_at_utc": "2026-08-31T00:00:00Z",
        "journal_member": "checkpoint/journal.json",
        "journal_mtime": 1,
        "journal_sha256": "e" * 64,
        "run_id": "synthetic-run",
        "task": task,
    }
    if include_competition_source:
        row["competition_id_source"] = "explicit_journal"
    return row


def _build_state(
    tmp_path: Path,
    observations: dict[str, object],
    accepted_tasks: dict[str, str],
) -> tuple[Path, str, int, int]:
    state = tmp_path / "state"
    intakes = state / "intakes"
    intakes.mkdir(parents=True)
    entries = observations["entries"]
    transactions: list[dict[str, object]] = []
    provenance_rows = 0
    competition_source_rows = 0
    for index, (relative, task) in enumerate(sorted(accepted_tasks.items())):
        row = entries[relative]
        archive_sha = row["committed_archive_sha256"]
        drop_id = f"drop-{index:03d}"
        intake = intakes / drop_id
        intake.mkdir()
        provenance = [
            _provenance_row(
                task,
                Path(relative).name,
                str(archive_sha),
                include_competition_source=index < 25,
            )
        ]
        provenance_path = intake / "source_provenance.json"
        _write(provenance_path, provenance)
        provenance_rows += len(provenance)
        competition_source_rows += "competition_id_source" in provenance[0]
        summary_path = intake / "summary.json"
        _write(
            summary_path,
            {
                "status": "PROSPECTIVE_DROP_INTAKE_COMPLETE",
                "protocol": "prospective_drop_intake_v1",
                "outputs": {"source_provenance_sha256": _sha(provenance_path)},
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
                "archive_sha256": archive_sha,
                "archive_size": 4,
                "committed_at_utc": "2026-08-31T00:00:00Z",
                "drop_id": drop_id,
                "intake_dir": str(intake.resolve()),
                "intake_summary_sha256": _sha(summary_path),
                "score_dir": str((state / "scores" / drop_id).resolve()),
                "score_summary_sha256": "d" * 64,
            }
        )
    transaction_blob = "".join(
        json.dumps(row, sort_keys=True, separators=(",", ":")) + "\n"
        for row in transactions
    ).encode("utf-8")
    transaction_sha = hashlib.sha256(transaction_blob).hexdigest()
    manifest_blob = f"{transaction_sha}  transactions.jsonl\n".encode("utf-8")
    latest = hashlib.sha256(manifest_blob).hexdigest()
    snapshot = state / "snapshots" / latest
    snapshot.mkdir(parents=True)
    (snapshot / "transactions.jsonl").write_bytes(transaction_blob)
    (snapshot / "SHA256SUMS").write_bytes(manifest_blob)
    for relative in accepted_tasks:
        entries[relative]["committed_snapshot_sha256"] = latest
    return state, latest, provenance_rows, competition_source_rows


def _protocol(
    observations: Path,
    historical: Path,
    latest: str,
    provenance_rows: int,
    competition_source_rows: int,
) -> dict[str, object]:
    evidence: dict[str, tuple[str, str]] = {}
    for name in (
        "v1_failure.json",
        "v1_protocol.json",
        "alias_summary.json",
        "alias_declaration.md",
    ):
        path = observations.parent / name
        path.write_text(f"synthetic evidence: {name}\n", encoding="utf-8")
        evidence[name] = (name, _sha(path))
    return {
        "protocol": "archive_disposition_longitudinal_replication_v2",
        "frozen_before_current_structural_mixed_disposition_readout": True,
        "inputs": {
            "current_latest_snapshot_sha256": latest,
            "current_observations_sha256": _sha(observations),
            "current_observations_bytes": observations.stat().st_size,
            "current_source_archive_count": 275,
            "historical_ledger_sha256": _sha(historical),
            "v1_failure_path": evidence["v1_failure.json"][0],
            "v1_failure_sha256": evidence["v1_failure.json"][1],
            "v1_protocol_path": evidence["v1_protocol.json"][0],
            "v1_protocol_sha256": evidence["v1_protocol.json"][1],
            "alias_formal_summary_path": evidence["alias_summary.json"][0],
            "alias_formal_summary_sha256": evidence["alias_summary.json"][1],
            "alias_declaration_report_path": evidence["alias_declaration.md"][0],
            "alias_declaration_report_sha256": evidence["alias_declaration.md"][1],
        },
        "known_metadata_before_readout": {
            "current_baseline_archives": 128,
            "current_accepted_archives": 126,
            "current_rejected_archives": 21,
            "current_structural_rejected_archives": 13,
            "current_alias_quarantined_archives": 8,
            "current_pending_archives": 0,
            "current_snapshot_transactions": 126,
            "current_accepted_single_task_archives": 126,
            "current_accepted_seeded_filename_archives": 124,
            "current_accepted_task_metadata_fallback_archives": 2,
            "current_rejected_seeded_filename_archives": 21,
            "current_hash_bound_source_provenance_rows": provenance_rows,
            "current_source_provenance_competition_source_rows": competition_source_rows,
            "current_accepted_unique_payload_hashes": 126,
            "current_structural_unique_payload_hashes": 13,
            "current_structural_payload_hashes_overlapping_accepted": 0,
            "current_alias_unique_payload_hashes": 8,
            "current_alias_payload_hashes_overlapping_accepted": 8,
            "current_distinct_alias_registry_hashes": 1,
            "current_rejection_reason_counts": {
                ALIAS_REASON: 8,
                STRUCTURAL_REASONS[0]: 2,
                STRUCTURAL_REASONS[1]: 2,
                STRUCTURAL_REASONS[2]: 9,
            },
            "historical_observed_archives": 218,
            "historical_settled_postbaseline_archives": 90,
            "historical_rejected_competitions": 6,
            "historical_mixed_disposition_competitions": 6,
        },
        "rejection_taxonomy": {
            "structural_target_reasons": STRUCTURAL_REASONS,
            "quarantine_only_reasons": [ALIAS_REASON],
            "quarantine_archives_contribute_to_structural_competition_estimand": False,
            "quarantine_archives_contribute_to_overall_settled_growth_gate": True,
        },
        "decision_rule": {
            "strong": {
                "minimum_current_structural_rejected_competitions": 6,
                "minimum_overall_extension_settled_archives": 50,
                "required_current_structural_mixed_disposition_fraction": 1.0,
                "status": "LONGITUDINAL_ARCHIVE_LEVEL_GATE_REPLICATED",
            },
            "partial": {
                "minimum_current_structural_mixed_disposition_fraction": 0.8,
                "status": "PARTIAL_ARCHIVE_LEVEL_GATE_REPLICATION",
            },
            "kill": {"status": "ARCHIVE_LEVEL_GATE_REPLICATION_FAILED"},
        },
        "access_contract": {
            "observation_metadata_only": True,
            "hash_bound_intake_task_metadata_only": True,
            "archive_payloads_opened": False,
            "labels_grades_outcomes_predictions_accuracy_or_utility_read": False,
            "candidate_identities_emitted": False,
            "run_or_card_identity_values_emitted": False,
            "gpu_paid_api_model_fit_base_update": "0/0/0/0",
        },
    }


def _fixture(
    tmp_path: Path, *, rejected_only: bool = False
) -> tuple[Path, Path, Path, Path]:
    observations = tmp_path / "observations.json"
    historical = tmp_path / "historical.json"
    protocol = tmp_path / "protocol.json"
    population, accepted_tasks = _observations(rejected_only=rejected_only)
    state, latest, provenance_rows, competition_source_rows = _build_state(
        tmp_path, population, accepted_tasks
    )
    _write(observations, population)
    _write(historical, _historical())
    _write(
        protocol,
        _protocol(
            observations,
            historical,
            latest,
            provenance_rows,
            competition_source_rows,
        ),
    )
    return protocol, observations, historical, state


def test_strong_replication_and_independent_verifier(tmp_path: Path) -> None:
    protocol, observations, historical, state = _fixture(tmp_path)
    result = build_result(protocol, observations, historical, state)
    assert result["status"] == "LONGITUDINAL_ARCHIVE_LEVEL_GATE_REPLICATED"
    assert result["current"]["structural_rejected_competitions"] == 8
    assert result["current"]["structural_mixed_disposition_competitions"] == 8
    assert result["current"]["alias_quarantined_archives"] == 8
    assert result["current"]["payload_hash_partition_audit"] == {
        "accepted_unique_payload_hashes": 126,
        "structural_unique_payload_hashes": 13,
        "structural_payload_hashes_overlapping_accepted": 0,
        "alias_unique_payload_hashes": 8,
        "alias_payload_hashes_overlapping_accepted": 8,
        "distinct_alias_registry_hashes": 1,
        "distinct_postbaseline_payload_hashes": 139,
    }
    assert result["extension_beyond_historical_anchor"]["overall_settled_archives"] == 57
    assert result["extension_beyond_historical_anchor"]["structural_target_settled_archives"] == 49
    assert result["current"]["competition_mapping_audit"] == {
        "snapshot_transactions": 126,
        "accepted_single_task_archives": 126,
        "accepted_seeded_filename_archives": 124,
        "accepted_task_metadata_fallback_archives": 2,
        "accepted_filename_task_mismatches": 0,
        "hash_bound_source_provenance_rows": 126,
        "source_provenance_competition_source_rows": 25,
        "rejected_seeded_filename_archives": 21,
    }
    result_path = tmp_path / "result.json"
    _write(result_path, result)
    receipt = verify(protocol, observations, historical, result_path, state)
    assert receipt["status"] == "INDEPENDENT_ARCHIVE_DISPOSITION_REPLICATION_PASS"
    assert receipt["all_aggregate_fields_equal"] is True


def test_nonmixed_rejected_competition_is_only_partial(tmp_path: Path) -> None:
    protocol, observations, historical, state = _fixture(
        tmp_path, rejected_only=True
    )
    result = build_result(protocol, observations, historical, state)
    assert result["status"] == "PARTIAL_ARCHIVE_LEVEL_GATE_REPLICATION"
    assert result["current"]["structural_rejected_competitions"] == 9
    assert result["current"]["structural_mixed_disposition_competitions"] == 8
    assert result["decision"]["strong_gate_passed"] is False


def test_duplicate_postbaseline_payload_hash_fails_closed(tmp_path: Path) -> None:
    protocol, observations, historical, state = _fixture(tmp_path)
    value = json.loads(observations.read_text(encoding="utf-8"))
    accepted = [
        row
        for row in value["entries"].values()
        if row["committed_archive_sha256"] is not None
    ]
    accepted[1]["committed_archive_sha256"] = accepted[0]["committed_archive_sha256"]
    _write(observations, value)
    original_protocol = json.loads(protocol.read_text(encoding="utf-8"))
    _write(
        protocol,
        _protocol(
            observations,
            historical,
            original_protocol["inputs"]["current_latest_snapshot_sha256"],
            original_protocol["known_metadata_before_readout"][
                "current_hash_bound_source_provenance_rows"
            ],
            original_protocol["known_metadata_before_readout"][
                "current_source_provenance_competition_source_rows"
            ],
        ),
    )
    with pytest.raises(ReplicationError, match="duplicate accepted"):
        build_result(protocol, observations, historical, state)


def test_unknown_reason_fails_closed(tmp_path: Path) -> None:
    protocol, observations, historical, state = _fixture(tmp_path)
    value = json.loads(observations.read_text(encoding="utf-8"))
    rejected = next(
        row
        for row in value["entries"].values()
        if row["rejected_archive_sha256"] is not None
    )
    rejected["rejection_reason_code"] = "UNREGISTERED_REASON"
    _write(observations, value)
    original_protocol = json.loads(protocol.read_text(encoding="utf-8"))
    _write(
        protocol,
        _protocol(
            observations,
            historical,
            original_protocol["inputs"]["current_latest_snapshot_sha256"],
            original_protocol["known_metadata_before_readout"][
                "current_hash_bound_source_provenance_rows"
            ],
            original_protocol["known_metadata_before_readout"][
                "current_source_provenance_competition_source_rows"
            ],
        ),
    )
    with pytest.raises(ReplicationError, match="unknown rejection reason"):
        build_result(protocol, observations, historical, state)


def test_alias_quarantine_cannot_enter_structural_estimand(tmp_path: Path) -> None:
    protocol, observations, historical, state = _fixture(tmp_path)
    value = json.loads(observations.read_text(encoding="utf-8"))
    old_relative, alias = next(
        (relative, row)
        for relative, row in value["entries"].items()
        if row["rejection_reason_code"] == ALIAS_REASON
    )
    new_relative = "4999/alias-only-4seeds.tar.gz"
    alias["path"] = f"/safe/source/{new_relative}"
    value["entries"][new_relative] = value["entries"].pop(old_relative)
    _write(observations, value)
    old_protocol = json.loads(protocol.read_text(encoding="utf-8"))
    _write(
        protocol,
        _protocol(
            observations,
            historical,
            old_protocol["inputs"]["current_latest_snapshot_sha256"],
            old_protocol["known_metadata_before_readout"][
                "current_hash_bound_source_provenance_rows"
            ],
            old_protocol["known_metadata_before_readout"][
                "current_source_provenance_competition_source_rows"
            ],
        ),
    )
    result = build_result(protocol, observations, historical, state)
    assert result["current"]["structural_rejected_competitions"] == 8
    assert result["current"]["structural_mixed_disposition_competitions"] == 8


def test_alias_payload_must_overlap_accepted(tmp_path: Path) -> None:
    protocol, observations, historical, state = _fixture(tmp_path)
    value = json.loads(observations.read_text(encoding="utf-8"))
    alias = next(
        row
        for row in value["entries"].values()
        if row["rejection_reason_code"] == ALIAS_REASON
    )
    alias["rejected_archive_sha256"] = "b" * 64
    _write(observations, value)
    old_protocol = json.loads(protocol.read_text(encoding="utf-8"))
    _write(
        protocol,
        _protocol(
            observations,
            historical,
            old_protocol["inputs"]["current_latest_snapshot_sha256"],
            old_protocol["known_metadata_before_readout"][
                "current_hash_bound_source_provenance_rows"
            ],
            old_protocol["known_metadata_before_readout"][
                "current_source_provenance_competition_source_rows"
            ],
        ),
    )
    with pytest.raises(ReplicationError, match="payload hash taxonomy"):
        build_result(protocol, observations, historical, state)


def test_structural_payload_must_be_disjoint_from_accepted(tmp_path: Path) -> None:
    protocol, observations, historical, state = _fixture(tmp_path)
    value = json.loads(observations.read_text(encoding="utf-8"))
    structural = next(
        row
        for row in value["entries"].values()
        if row["rejection_reason_code"] in STRUCTURAL_REASONS
    )
    structural["rejected_archive_sha256"] = f"{1:064x}"
    _write(observations, value)
    old_protocol = json.loads(protocol.read_text(encoding="utf-8"))
    _write(
        protocol,
        _protocol(
            observations,
            historical,
            old_protocol["inputs"]["current_latest_snapshot_sha256"],
            old_protocol["known_metadata_before_readout"][
                "current_hash_bound_source_provenance_rows"
            ],
            old_protocol["known_metadata_before_readout"][
                "current_source_provenance_competition_source_rows"
            ],
        ),
    )
    with pytest.raises(ReplicationError, match="payload hash taxonomy"):
        build_result(protocol, observations, historical, state)


def test_bound_v1_failure_evidence_drift_fails_closed(tmp_path: Path) -> None:
    protocol, observations, historical, state = _fixture(tmp_path)
    (tmp_path / "v1_failure.json").write_text("drift\n", encoding="utf-8")
    with pytest.raises(ReplicationError, match="v1 failure hash mismatch"):
        build_result(protocol, observations, historical, state)


def test_verifier_rejects_status_mutation(tmp_path: Path) -> None:
    protocol, observations, historical, state = _fixture(tmp_path)
    result = build_result(protocol, observations, historical, state)
    result["status"] = "PARTIAL_ARCHIVE_LEVEL_GATE_REPLICATION"
    result_path = tmp_path / "mutated.json"
    _write(result_path, result)
    with pytest.raises(VerificationError, match="result status mismatch"):
        verify(protocol, observations, historical, result_path, state)


def test_malformed_partial_threshold_fails_closed(tmp_path: Path) -> None:
    protocol, observations, historical, state = _fixture(tmp_path)
    value = json.loads(protocol.read_text(encoding="utf-8"))
    value["decision_rule"]["partial"][
        "minimum_current_structural_mixed_disposition_fraction"
    ] = "0.8"
    _write(protocol, value)
    with pytest.raises(ReplicationError, match="partial mixed-disposition fraction"):
        build_result(protocol, observations, historical, state)
