from __future__ import annotations

import hashlib
import json
from collections import Counter
from pathlib import Path

import pytest

from phase1.audit_archive_rejection_support_census import (
    ARCHIVE_ONLY,
    NO_SUPPORT,
    PRIOR_SUPPORT,
    WINDOW_SUPPORT,
    RejectionSupportCensusError,
    build_result,
)
from phase1.verify_archive_rejection_support_census import (
    CensusVerificationError,
    verify,
)


REASON_ID = "JOURNAL_TASK_IDENTITY_NOT_EXACTLY_ONE_WITHIN_ARCHIVE"
REASON_ABSENT = "JOURNAL_TASK_IDENTITY_ABSENT_ALL_CHECKPOINTS"
REASON_JOURNAL = "ARCHIVE_HAS_NO_CHECKPOINT_JOURNALS"
ALIAS = "ARCHIVE_BYTES_DUPLICATE_COMMITTED_TRANSACTION"
ROOT = Path(__file__).resolve().parents[2]


def write_json(path: Path, value: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
        newline="\n",
    )


def file_sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def observation_row(relative: str, source_root: str) -> dict[str, object]:
    return {
        "baseline": False,
        "committed_archive_sha256": None,
        "committed_snapshot_sha256": None,
        "first_stable_at_epoch": 1.0,
        "last_observed_at_epoch": 2.0,
        "mtime_ns": 3,
        "path": source_root.rstrip("/") + "/" + relative,
        "present": True,
        "rejected_archive_sha256": None,
        "rejection_reason_code": None,
        "rejection_registry_sha256": None,
        "size": 4,
        "stable_observations": 3,
    }


def make_intake(
    state: Path,
    index: int,
    task: str,
    relative: str,
    archive_sha: str,
    *,
    eligible: bool,
) -> dict[str, object]:
    drop_id = f"drop-{index:03d}"
    intake = state / "intakes" / drop_id
    intake.mkdir(parents=True)
    provenance = intake / "source_provenance.json"
    write_json(
        provenance,
        [
            {
                "archive_name": Path(relative).name,
                "archive_sha256": archive_sha,
                "eligible": eligible,
                "empty_code_nodes_excluded": 0,
                "endpoints": 2 if eligible else 0,
                "flow_status": "scoreable" if eligible else "unscoreable",
                "generation_started_at_utc": "2026-09-01T00:00:00Z",
                "journal_member": "checkpoint/journal.json",
                "journal_mtime": 1,
                "journal_sha256": "e" * 64,
                "run_id": f"run-{index:03d}",
                "task": task,
            }
        ],
    )
    summary = intake / "summary.json"
    write_json(
        summary,
        {
            "status": "PROSPECTIVE_DROP_INTAKE_COMPLETE",
            "protocol": "prospective_drop_intake_v1",
            "outputs": {"source_provenance_sha256": file_sha(provenance)},
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
    return {
        "archive_relative_path": relative,
        "archive_sha256": archive_sha,
        "archive_size": 4,
        "committed_at_utc": "2026-09-01T00:00:00Z",
        "drop_id": drop_id,
        "intake_dir": str(intake.resolve()),
        "intake_summary_sha256": file_sha(summary),
        "score_dir": str((state / "scores" / drop_id).resolve()),
        "score_summary_sha256": "d" * 64,
    }


def transaction_blob(rows: list[dict[str, object]]) -> bytes:
    return "".join(
        json.dumps(row, sort_keys=True, separators=(",", ":")) + "\n" for row in rows
    ).encode()


def make_snapshot(
    state: Path,
    rows: list[dict[str, object]],
    inventory: dict[str, int],
) -> tuple[str, str]:
    transactions = transaction_blob(rows)
    transaction_sha = hashlib.sha256(transactions).hexdigest()
    summary = (json.dumps({"inventory": inventory}, indent=2, sort_keys=True) + "\n").encode()
    summary_sha = hashlib.sha256(summary).hexdigest()
    manifest = (
        f"{transaction_sha}  transactions.jsonl\n"
        f"{summary_sha}  accumulator/summary.json\n"
    ).encode()
    snapshot_sha = hashlib.sha256(manifest).hexdigest()
    snapshot = state / "snapshots" / snapshot_sha
    (snapshot / "accumulator").mkdir(parents=True)
    (snapshot / "transactions.jsonl").write_bytes(transactions)
    (snapshot / "accumulator" / "summary.json").write_bytes(summary)
    (snapshot / "SHA256SUMS").write_bytes(manifest)
    return snapshot_sha, transaction_sha


def fixture(
    tmp_path: Path,
    *,
    tamper_prefix: bool = False,
    payload_overlap: bool = False,
) -> dict[str, object]:
    root = tmp_path / "repo"
    state = tmp_path / "state"
    root.mkdir()
    (state / "intakes").mkdir(parents=True)
    source_root = "/safe/source"
    entries: dict[str, dict[str, object]] = {}

    baseline_relative = "legacy/baseline.tar.gz"
    baseline = observation_row(baseline_relative, source_root)
    baseline["baseline"] = True
    entries[baseline_relative] = baseline

    accepted_specs = [
        ("prior-a", True),
        ("window-a", True),
        ("archive-only", False),
    ]
    transactions: list[dict[str, object]] = []
    accepted_hashes: list[str] = []
    for index, (task, eligible) in enumerate(accepted_specs):
        relative = f"{1000 + index}/{task}-4seeds.tar.gz"
        archive_sha = f"{index + 1:064x}"
        accepted_hashes.append(archive_sha)
        row = observation_row(relative, source_root)
        row["committed_archive_sha256"] = archive_sha
        row["committed_snapshot_sha256"] = "f" * 64
        entries[relative] = row
        transactions.append(
            make_intake(state, index, task, relative, archive_sha, eligible=eligible)
        )

    target_specs = [
        (REASON_ID, "prior-a"),
        (REASON_ID, "prior-a"),
        (REASON_ID, "window-a"),
        (REASON_ID, "archive-only"),
        (REASON_ID, "no-support"),
        (REASON_ABSENT, "prior-a"),
        (REASON_ABSENT, "prior-a"),
        (REASON_ABSENT, "window-a"),
        (REASON_ABSENT, "archive-only"),
        (REASON_ABSENT, "no-support"),
        (REASON_JOURNAL, "window-a"),
        (REASON_JOURNAL, "archive-only"),
        (REASON_JOURNAL, "no-support"),
        (REASON_JOURNAL, "no-support"),
    ]
    registry_hashes = {
        reason: hashlib.sha256(reason.encode()).hexdigest()
        for reason in (REASON_ID, REASON_ABSENT, REASON_JOURNAL, ALIAS)
    }
    for index, (reason, task) in enumerate(target_specs):
        relative = f"{2000 + index}/{task}-{8 + index}seeds.tar.gz"
        row = observation_row(relative, source_root)
        row["rejected_archive_sha256"] = (
            accepted_hashes[0] if payload_overlap and index == 0 else f"{9000 + index:064x}"
        )
        row["rejection_reason_code"] = reason
        row["rejection_registry_sha256"] = registry_hashes[reason]
        entries[relative] = row

    alias_relative = "3000/prior-a-99seeds.tar.gz"
    alias = observation_row(alias_relative, source_root)
    alias["rejected_archive_sha256"] = "a" * 64
    alias["rejection_reason_code"] = ALIAS
    alias["rejection_registry_sha256"] = registry_hashes[ALIAS]
    entries[alias_relative] = alias

    prior_rows = transactions[:1]
    current_rows = transactions if not tamper_prefix else transactions[1:] + transactions[:1]
    prior_snapshot, prior_tx_sha = make_snapshot(
        state,
        prior_rows,
        {
            "all_physical_runs": 1,
            "eligible_runs": 1,
            "eligible_endpoints": 2,
            "eligible_structural_pairs": 1,
            "eligible_tasks": 1,
        },
    )
    current_snapshot, current_tx_sha = make_snapshot(
        state,
        current_rows,
        {
            "all_physical_runs": 3,
            "eligible_runs": 2,
            "eligible_endpoints": 4,
            "eligible_structural_pairs": 2,
            "eligible_tasks": 3,
        },
    )
    (state / "LATEST").write_text(current_snapshot + "\n", encoding="ascii")

    observations = root / "observations.json"
    write_json(
        observations,
        {
            "baseline_sealed_at_epoch": 1.0,
            "entries": entries,
            "protocol": "prospective_archive_observer_v1",
            "source_root": source_root,
        },
    )
    evidence = {}
    for name in ("ledger", "ledger_verification", "single_result", "single_verification"):
        path = root / f"{name}.json"
        path.write_text(f'{{"synthetic":"{name}"}}\n', encoding="utf-8")
        evidence[name] = path

    protocol = root / "protocol.json"
    reason_counts = Counter(reason for reason, _task in target_specs)
    reason_counts[ALIAS] = 1
    write_json(
        protocol,
        {
            "protocol": "archive_rejection_support_census_v1",
            "frozen_before_full_census_support_readout": True,
            "inputs": {
                "prior_snapshot_sha256": prior_snapshot,
                "current_snapshot_sha256": current_snapshot,
                "current_observations_sha256": file_sha(observations),
                "current_observations_bytes": observations.stat().st_size,
                "prior_transactions_sha256": prior_tx_sha,
                "prior_transaction_lines": 1,
                "current_transactions_sha256": current_tx_sha,
                "current_transaction_lines": 3,
                "current_window_transaction_lines": 2,
                "legacy_twelve_event_ledger_path": evidence["ledger"].relative_to(root).as_posix(),
                "legacy_twelve_event_ledger_sha256": file_sha(evidence["ledger"]),
                "legacy_twelve_event_verification_path": evidence["ledger_verification"].relative_to(root).as_posix(),
                "legacy_twelve_event_verification_sha256": file_sha(evidence["ledger_verification"]),
                "latest_single_event_result_path": evidence["single_result"].relative_to(root).as_posix(),
                "latest_single_event_result_sha256": file_sha(evidence["single_result"]),
                "latest_single_event_verification_path": evidence["single_verification"].relative_to(root).as_posix(),
                "latest_single_event_verification_sha256": file_sha(evidence["single_verification"]),
            },
            "known_before_readout": {
                "population": {
                    "observed_archives": len(entries),
                    "baseline_archives": 1,
                    "accepted_archives": 3,
                    "structural_rejected_archives": 14,
                    "alias_quarantined_archives": 1,
                    "pending_archives": 0,
                    "rejection_reason_counts": dict(sorted(reason_counts.items())),
                    "physical_runs": 3,
                    "eligible_runs": 2,
                    "eligible_endpoints": 4,
                    "eligible_structural_pairs": 2,
                    "eligible_tasks": 3,
                },
                "partial_support_disclosure": {
                    "legacy_structural_rejection_events": 2,
                    "latest_single_event_class": NO_SUPPORT,
                },
            },
            "unknown_at_freeze": {
                "thirteenth_event_support_class": False,
                "fourteen_event_support_class_counts": False,
            },
            "estimand": {
                "full_census_not_sampling_inference": True,
                "no_binary_success_threshold": True,
            },
            "support_classes_in_precedence_order": [
                {"class": PRIOR_SUPPORT},
                {"class": WINDOW_SUPPORT},
                {"class": ARCHIVE_ONLY},
                {"class": NO_SUPPORT},
            ],
            "access_contract": {
                "observation_and_hash_bound_intake_metadata_only": True,
                "rejection_registry_contents_opened": False,
                "archive_payloads_opened": False,
                "labels_grades_outcomes_predictions_accuracy_or_utility_read": False,
                "candidate_identities_or_profiles_read": False,
                "identity_values_emitted": False,
                "gpu_paid_api_model_fit_base_update": "0/0/0/0",
            },
        },
    )
    return {
        "root": root,
        "state": state,
        "protocol": protocol,
        "observations": observations,
        "identity_values": {
            "prior-a",
            "window-a",
            "archive-only",
            "no-support",
            "run-000",
            "run-001",
            "run-002",
        },
    }


def test_four_class_census_matches_independent_verifier(tmp_path: Path) -> None:
    case = fixture(tmp_path)
    result = build_result(case["protocol"], case["observations"], case["state"])
    assert result["event_support_class_counts"] == {
        PRIOR_SUPPORT: 4,
        WINDOW_SUPPORT: 3,
        ARCHIVE_ONLY: 3,
        NO_SUPPORT: 4,
    }
    assert result["competition_support_class_counts"] == {
        "distinct_rejected_competitions": 4,
        PRIOR_SUPPORT: 1,
        WINDOW_SUPPORT: 1,
        ARCHIVE_ONLY: 1,
        NO_SUPPORT: 1,
    }
    assert sum(
        sum(classes.values()) for classes in result["reason_by_event_support_class"].values()
    ) == 14
    result_path = case["root"] / "result.json"
    write_json(result_path, result)
    receipt = verify(case["protocol"], case["observations"], result_path, case["state"])
    assert receipt["status"] == "INDEPENDENT_ARCHIVE_REJECTION_SUPPORT_CENSUS_PASS"
    assert receipt["all_result_fields_equal"] is True


def test_frozen_protocol_contract_and_evidence_hashes() -> None:
    protocol_path = ROOT / "phase1/archive_rejection_support_census_v1.json"
    protocol = json.loads(protocol_path.read_text(encoding="utf-8"))
    inputs = protocol["inputs"]
    population = protocol["known_before_readout"]["population"]
    assert inputs["current_transaction_lines"] - inputs["prior_transaction_lines"] == inputs[
        "current_window_transaction_lines"
    ] == 7
    assert population["structural_rejected_archives"] == 14
    assert sum(population["rejection_reason_counts"].values()) == (
        population["structural_rejected_archives"]
        + population["alias_quarantined_archives"]
    )
    assert set(protocol["unknown_at_freeze"].values()) == {False}
    assert protocol["access_contract"]["identity_values_emitted"] is False
    for path_key, hash_key in (
        ("legacy_twelve_event_ledger_path", "legacy_twelve_event_ledger_sha256"),
        (
            "legacy_twelve_event_verification_path",
            "legacy_twelve_event_verification_sha256",
        ),
        ("latest_single_event_result_path", "latest_single_event_result_sha256"),
        (
            "latest_single_event_verification_path",
            "latest_single_event_verification_sha256",
        ),
    ):
        evidence = (protocol_path.parent / inputs[path_key]).resolve()
        evidence.relative_to(protocol_path.parent.resolve())
        assert evidence.is_file() and not evidence.is_symlink()
        assert file_sha(evidence) == inputs[hash_key]


def test_census_emits_no_identity_values(tmp_path: Path) -> None:
    case = fixture(tmp_path)
    result = build_result(case["protocol"], case["observations"], case["state"])
    rendered = json.dumps(result, sort_keys=True)
    assert all(value not in rendered for value in case["identity_values"])
    assert result["access_attestation"][
        "labels_grades_outcomes_predictions_accuracy_or_utility_read"
    ] is False
    assert result["access_attestation"][
        "event_competition_archive_task_run_or_candidate_identity_values_emitted"
    ] is False


def test_window_size_is_protocol_bound(tmp_path: Path) -> None:
    case = fixture(tmp_path)
    protocol = json.loads(case["protocol"].read_text(encoding="utf-8"))
    protocol["inputs"]["current_window_transaction_lines"] = 1
    write_json(case["protocol"], protocol)
    with pytest.raises(RejectionSupportCensusError, match="transaction count mismatch"):
        build_result(case["protocol"], case["observations"], case["state"])


@pytest.mark.parametrize(
    ("options", "message"),
    [
        ({"tamper_prefix": True}, "prior byte prefix"),
        ({"payload_overlap": True}, "overlaps accepted"),
    ],
)
def test_integrity_attacks_fail_closed(
    tmp_path: Path, options: dict[str, bool], message: str
) -> None:
    case = fixture(tmp_path, **options)
    with pytest.raises(RejectionSupportCensusError, match=message):
        build_result(case["protocol"], case["observations"], case["state"])


def test_independent_verifier_rejects_candidate_tamper(tmp_path: Path) -> None:
    case = fixture(tmp_path)
    result = build_result(case["protocol"], case["observations"], case["state"])
    result["event_support_class_counts"][PRIOR_SUPPORT] += 1
    result_path = case["root"] / "tampered.json"
    write_json(result_path, result)
    with pytest.raises(CensusVerificationError, match="differs"):
        verify(case["protocol"], case["observations"], result_path, case["state"])


def test_independent_verifier_does_not_import_census_producer() -> None:
    source = Path("phase1/verify_archive_rejection_support_census.py").read_text(
        encoding="utf-8"
    )
    assert "audit_archive_rejection_support_census" not in source
