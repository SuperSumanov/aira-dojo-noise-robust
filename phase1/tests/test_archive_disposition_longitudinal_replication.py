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


LATEST = "f" * 64
REASONS = [
    "ARCHIVE_HAS_NO_CHECKPOINT_JOURNALS",
    "JOURNAL_TASK_IDENTITY_ABSENT_ALL_CHECKPOINTS",
    "JOURNAL_TASK_IDENTITY_NOT_EXACTLY_ONE_WITHIN_ARCHIVE",
]


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


def _observations(*, rejected_only: bool = False) -> dict[str, object]:
    entries: dict[str, object] = {}
    serial = 1
    for index in range(128):
        relative = f"{1000 + index:04d}/baseline-{index}.tar.gz"
        row = _entry(relative)
        row["baseline"] = True
        entries[relative] = row
    for index in range(126):
        task = f"competition-{index % 8}"
        relative = f"{2000 + index:04d}/{task}-4seeds.tar.gz"
        row = _entry(relative)
        row["committed_archive_sha256"] = f"{serial:064x}"
        row["committed_snapshot_sha256"] = LATEST if index == 0 else f"{5000 + index:064x}"
        entries[relative] = row
        serial += 1
    for index in range(21):
        task = "rejected-only" if rejected_only and index == 0 else f"competition-{index % 8}"
        relative = f"{3000 + index:04d}/{task}-4seeds.tar.gz"
        row = _entry(relative)
        row["rejected_archive_sha256"] = f"{serial:064x}"
        row["rejection_registry_sha256"] = f"{9000 + index:064x}"
        row["rejection_reason_code"] = REASONS[index % len(REASONS)]
        entries[relative] = row
        serial += 1
    return {
        "baseline_sealed_at_epoch": 1.0,
        "entries": entries,
        "protocol": "prospective_archive_observer_v1",
        "source_root": "/safe/source",
    }


def _protocol(observations: Path, historical: Path) -> dict[str, object]:
    return {
        "protocol": "archive_disposition_longitudinal_replication_v1",
        "frozen_before_current_mixed_disposition_readout": True,
        "inputs": {
            "current_latest_snapshot_sha256": LATEST,
            "current_observations_sha256": _sha(observations),
            "current_observations_bytes": observations.stat().st_size,
            "current_source_archive_count": 275,
            "historical_ledger_sha256": _sha(historical),
        },
        "known_metadata_before_readout": {
            "current_baseline_archives": 128,
            "current_accepted_archives": 126,
            "current_rejected_archives": 21,
            "current_pending_archives": 0,
            "historical_observed_archives": 218,
            "historical_settled_postbaseline_archives": 90,
            "historical_rejected_competitions": 6,
            "historical_mixed_disposition_competitions": 6,
        },
        "recognized_rejection_reasons": REASONS,
        "decision_rule": {
            "strong": {
                "minimum_current_rejected_competitions": 6,
                "minimum_extension_settled_archives": 50,
                "required_current_mixed_disposition_fraction": 1.0,
                "status": "LONGITUDINAL_ARCHIVE_LEVEL_GATE_REPLICATED",
            },
            "partial": {
                "minimum_current_mixed_disposition_fraction": 0.8,
                "status": "PARTIAL_ARCHIVE_LEVEL_GATE_REPLICATION",
            },
            "kill": {"status": "ARCHIVE_LEVEL_GATE_REPLICATION_FAILED"},
        },
        "access_contract": {
            "observation_metadata_only": True,
            "archive_payloads_opened": False,
            "labels_grades_outcomes_predictions_accuracy_or_utility_read": False,
            "candidate_identities_emitted": False,
            "gpu_paid_api_model_fit_base_update": "0/0/0/0",
        },
    }


def _fixture(tmp_path: Path, *, rejected_only: bool = False) -> tuple[Path, Path, Path]:
    observations = tmp_path / "observations.json"
    historical = tmp_path / "historical.json"
    protocol = tmp_path / "protocol.json"
    _write(observations, _observations(rejected_only=rejected_only))
    _write(historical, _historical())
    _write(protocol, _protocol(observations, historical))
    return protocol, observations, historical


def test_strong_replication_and_independent_verifier(tmp_path: Path) -> None:
    protocol, observations, historical = _fixture(tmp_path)
    result = build_result(protocol, observations, historical)
    assert result["status"] == "LONGITUDINAL_ARCHIVE_LEVEL_GATE_REPLICATED"
    assert result["current"]["rejected_competitions"] == 8
    assert result["current"]["mixed_disposition_competitions"] == 8
    assert result["extension_beyond_historical_anchor"]["settled_archives"] == 57
    result_path = tmp_path / "result.json"
    _write(result_path, result)
    receipt = verify(protocol, observations, historical, result_path)
    assert receipt["status"] == "INDEPENDENT_ARCHIVE_DISPOSITION_REPLICATION_PASS"
    assert receipt["all_aggregate_fields_equal"] is True


def test_nonmixed_rejected_competition_is_only_partial(tmp_path: Path) -> None:
    protocol, observations, historical = _fixture(tmp_path, rejected_only=True)
    result = build_result(protocol, observations, historical)
    assert result["status"] == "PARTIAL_ARCHIVE_LEVEL_GATE_REPLICATION"
    assert result["current"]["rejected_competitions"] == 9
    assert result["current"]["mixed_disposition_competitions"] == 8
    assert result["decision"]["strong_gate_passed"] is False


def test_duplicate_postbaseline_payload_hash_fails_closed(tmp_path: Path) -> None:
    protocol, observations, historical = _fixture(tmp_path)
    value = json.loads(observations.read_text(encoding="utf-8"))
    accepted = [
        row
        for row in value["entries"].values()
        if row["committed_archive_sha256"] is not None
    ]
    accepted[1]["committed_archive_sha256"] = accepted[0]["committed_archive_sha256"]
    _write(observations, value)
    _write(protocol, _protocol(observations, historical))
    with pytest.raises(ReplicationError, match="duplicate postbaseline"):
        build_result(protocol, observations, historical)


def test_unknown_reason_fails_closed(tmp_path: Path) -> None:
    protocol, observations, historical = _fixture(tmp_path)
    value = json.loads(observations.read_text(encoding="utf-8"))
    rejected = next(
        row
        for row in value["entries"].values()
        if row["rejected_archive_sha256"] is not None
    )
    rejected["rejection_reason_code"] = "UNREGISTERED_REASON"
    _write(observations, value)
    _write(protocol, _protocol(observations, historical))
    with pytest.raises(ReplicationError, match="unknown rejection reason"):
        build_result(protocol, observations, historical)


def test_verifier_rejects_status_mutation(tmp_path: Path) -> None:
    protocol, observations, historical = _fixture(tmp_path)
    result = build_result(protocol, observations, historical)
    result["status"] = "PARTIAL_ARCHIVE_LEVEL_GATE_REPLICATION"
    result_path = tmp_path / "mutated.json"
    _write(result_path, result)
    with pytest.raises(VerificationError, match="result status mismatch"):
        verify(protocol, observations, historical, result_path)


def test_malformed_partial_threshold_fails_closed(tmp_path: Path) -> None:
    protocol, observations, historical = _fixture(tmp_path)
    value = json.loads(protocol.read_text(encoding="utf-8"))
    value["decision_rule"]["partial"][
        "minimum_current_mixed_disposition_fraction"
    ] = "0.8"
    _write(protocol, value)
    with pytest.raises(ReplicationError, match="partial mixed-disposition fraction"):
        build_result(protocol, observations, historical)
