from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pytest

from phase1.audit_incremental_archive_rejection_support import (
    IncrementalArchiveAuditError,
    build_result,
)
from phase1.verify_incremental_archive_rejection_support import (
    IndependentVerificationError,
    verify,
)


TARGET_REASON = "ARCHIVE_HAS_NO_CHECKPOINT_JOURNALS"
ALIAS_REASON = "ARCHIVE_BYTES_DUPLICATE_COMMITTED_TRANSACTION"
TARGET_REGISTRY_CONTENT = b'{"synthetic_registry":"hash-binding-only"}\n'


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


def provenance_row(
    task: str,
    archive_name: str,
    archive_sha: str,
    run_id: str,
    *,
    eligible: bool = True,
) -> dict[str, object]:
    return {
        "archive_name": archive_name,
        "archive_sha256": archive_sha,
        "eligible": eligible,
        "empty_code_nodes_excluded": 0,
        "endpoints": 2 if eligible else 0,
        "flow_status": "scoreable" if eligible else "unscoreable",
        "generation_started_at_utc": "2026-09-01T00:00:00Z",
        "journal_member": "checkpoint/journal.json",
        "journal_mtime": 1,
        "journal_sha256": "e" * 64,
        "run_id": run_id,
        "task": task,
    }


def make_intake(
    state: Path,
    index: int,
    task: str,
    archive_relative: str,
    archive_sha: str,
) -> dict[str, object]:
    drop_id = f"drop-{index:03d}"
    intake = state / "intakes" / drop_id
    intake.mkdir(parents=True)
    provenance_path = intake / "source_provenance.json"
    write_json(
        provenance_path,
        [provenance_row(task, Path(archive_relative).name, archive_sha, f"run-{index:03d}")],
    )
    summary_path = intake / "summary.json"
    write_json(
        summary_path,
        {
            "status": "PROSPECTIVE_DROP_INTAKE_COMPLETE",
            "protocol": "prospective_drop_intake_v1",
            "outputs": {"source_provenance_sha256": file_sha(provenance_path)},
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
        "archive_relative_path": archive_relative,
        "archive_sha256": archive_sha,
        "archive_size": 4,
        "committed_at_utc": "2026-09-01T00:00:00Z",
        "drop_id": drop_id,
        "intake_dir": str(intake.resolve()),
        "intake_summary_sha256": file_sha(summary_path),
        "score_dir": str((state / "scores" / drop_id).resolve()),
        "score_summary_sha256": "d" * 64,
    }


def transaction_blob(rows: list[dict[str, object]]) -> bytes:
    return "".join(
        json.dumps(row, sort_keys=True, separators=(",", ":")) + "\n" for row in rows
    ).encode("utf-8")


def make_snapshot(
    state: Path,
    rows: list[dict[str, object]],
    inventory: dict[str, int],
) -> tuple[str, str]:
    blob = transaction_blob(rows)
    transaction_sha = hashlib.sha256(blob).hexdigest()
    summary_blob = (
        json.dumps({"inventory": inventory}, indent=2, sort_keys=True) + "\n"
    ).encode("utf-8")
    summary_sha = hashlib.sha256(summary_blob).hexdigest()
    manifest_blob = (
        f"{transaction_sha}  transactions.jsonl\n"
        f"{summary_sha}  accumulator/summary.json\n"
    ).encode("utf-8")
    snapshot_sha = hashlib.sha256(manifest_blob).hexdigest()
    snapshot = state / "snapshots" / snapshot_sha
    (snapshot / "accumulator").mkdir(parents=True)
    (snapshot / "transactions.jsonl").write_bytes(blob)
    (snapshot / "accumulator" / "summary.json").write_bytes(summary_blob)
    (snapshot / "SHA256SUMS").write_bytes(manifest_blob)
    return snapshot_sha, transaction_sha


def prior_evidence(
    root: Path,
    prior_snapshot: str,
    prior_counts: dict[str, int],
) -> tuple[Path, Path]:
    result = root / "prior_result.json"
    write_json(
        result,
        {
            "status": "LONGITUDINAL_ARCHIVE_LEVEL_GATE_REPLICATED",
            "input_bindings": {"current_latest_snapshot_sha256": prior_snapshot},
            "current": {
                "observed_archives": prior_counts["observed_archives"],
                "accepted_archives": prior_counts["accepted_archives"],
                "structural_rejected_archives": prior_counts["structural_rejected_archives"],
                "alias_quarantined_archives": prior_counts["alias_quarantined_archives"],
                "pending_archives": prior_counts["pending_archives"],
            },
        },
    )
    verification = root / "prior_verification.json"
    write_json(
        verification,
        {
            "status": "INDEPENDENT_ARCHIVE_DISPOSITION_REPLICATION_PASS",
            "result_sha256": file_sha(result),
            "identities_emitted": False,
            "outcomes_predictions_labels_read": False,
        },
    )
    return result, verification


def protocol_value(
    root: Path,
    observations: Path,
    registry: Path,
    prior_result: Path,
    prior_verification: Path,
    prior_snapshot: str,
    current_snapshot: str,
    prior_transaction_sha: str,
    current_transaction_sha: str,
    prior_count: int,
    current_count: int,
    prior_known: dict[str, int],
    current_known: dict[str, object],
    increment_observed: int,
    increment_accepted: int,
    target_count: int,
) -> dict[str, object]:
    return {
        "protocol": "incremental_archive_rejection_support_audit_v1",
        "frozen_before_target_competition_or_support_readout": True,
        "inputs": {
            "prior_snapshot_sha256": prior_snapshot,
            "current_snapshot_sha256": current_snapshot,
            "current_observations_sha256": file_sha(observations),
            "current_observations_bytes": observations.stat().st_size,
            "prior_transactions_sha256": prior_transaction_sha,
            "prior_transaction_lines": prior_count,
            "current_transactions_sha256": current_transaction_sha,
            "current_transaction_lines": current_count,
            "target_rejection_registry_path": registry.relative_to(root).as_posix(),
            "target_rejection_registry_sha256": file_sha(registry),
            "prior_archive_disposition_result_path": prior_result.relative_to(root).as_posix(),
            "prior_archive_disposition_result_sha256": file_sha(prior_result),
            "prior_archive_disposition_verification_path": prior_verification.relative_to(root).as_posix(),
            "prior_archive_disposition_verification_sha256": file_sha(prior_verification),
        },
        "known_before_readout": {
            "prior": prior_known,
            "current": current_known,
            "increment": {
                "observed_archives": increment_observed,
                "accepted_archives": increment_accepted,
                "structural_rejected_archives": target_count,
                "alias_quarantined_archives": 0,
                "pending_archives": 0,
                "target_rejection_reason": TARGET_REASON,
            },
        },
        "unknown_at_freeze": {
            "target_competition_identity_read_or_emitted": False,
            "target_competition_has_any_accepted_archive": False,
            "target_competition_has_prior_accepted_archive": False,
            "prior_accepted_archives_for_target": False,
            "prior_physical_runs_for_target": False,
            "prior_eligible_runs_for_target": False,
            "prior_eligible_endpoints_for_target": False,
            "new_window_support_for_target": False,
            "current_total_support_for_target": False,
            "decision_status": False,
        },
        "target_selection": {
            "required_count": 1,
            "required_rejection_reason": TARGET_REASON,
            "caller_may_choose_archive_or_competition": False,
            "registry_contents_required_for_selection": False,
            "registry_file_hash_only": True,
        },
        "decision_rule": {
            "strong": {
                "minimum_prior_accepted_archives": 1,
                "minimum_prior_eligible_runs": 1,
                "minimum_prior_eligible_endpoints": 1,
                "status": "INCREMENTAL_ARCHIVE_SUPPORT_PREEXISTING_STRONG",
            },
            "partial": {
                "prior_eligible_support_required": False,
                "minimum_current_accepted_archives": 1,
                "minimum_current_eligible_runs": 1,
                "minimum_current_eligible_endpoints": 1,
                "status": "INCREMENTAL_ARCHIVE_SUPPORT_CONTEMPORANEOUS_ONLY",
            },
            "absent": {"status": "INCREMENTAL_ARCHIVE_SUPPORT_ABSENT"},
            "integrity_failure": {"status": "INCREMENTAL_ARCHIVE_SUPPORT_INTEGRITY_FAIL"},
        },
        "access_contract": {
            "observation_and_hash_bound_intake_metadata_only": True,
            "target_registry_contents_opened": False,
            "archive_payloads_opened": False,
            "labels_grades_outcomes_predictions_accuracy_or_utility_read": False,
            "candidate_identities_or_profiles_read": False,
            "archive_task_run_or_candidate_identity_values_emitted": False,
            "gpu_paid_api_model_fit_base_update": "0/0/0/0",
        },
    }


def fixture(
    tmp_path: Path,
    support: str,
    *,
    prefix_tamper: bool = False,
    target_count: int = 1,
    target_payload_overlap: bool = False,
    bad_observation_path: bool = False,
) -> dict[str, object]:
    root = tmp_path / "repo"
    state = tmp_path / "state"
    root.mkdir()
    (state / "intakes").mkdir(parents=True)
    source_root = "/safe/source"
    target = "target-competition"
    prior_tasks = [target, "prior-other"] if support == "strong" else ["prior-other"]
    new_tasks = [target] if support == "contemporaneous" else ["new-other"]
    accepted_tasks = prior_tasks + new_tasks
    entries: dict[str, dict[str, object]] = {}
    baseline_relative = "legacy/baseline.tar.gz"
    baseline = observation_row(baseline_relative, source_root)
    baseline["baseline"] = True
    entries[baseline_relative] = baseline
    transactions: list[dict[str, object]] = []
    accepted_hashes: list[str] = []
    for index, task in enumerate(accepted_tasks):
        relative = f"{1000 + index}/{task}-4seeds.tar.gz"
        archive_sha = f"{index + 1:064x}"
        accepted_hashes.append(archive_sha)
        row = observation_row(relative, source_root)
        row["committed_archive_sha256"] = archive_sha
        row["committed_snapshot_sha256"] = "f" * 64
        entries[relative] = row
        transactions.append(make_intake(state, index, task, relative, archive_sha))
    registry = root / "target_registry.json"
    registry.write_bytes(TARGET_REGISTRY_CONTENT)
    for index in range(target_count):
        relative = f"{2000 + index}/{target}-{4 + index}seeds.tar.gz"
        row = observation_row(relative, source_root)
        row["rejected_archive_sha256"] = (
            accepted_hashes[0] if target_payload_overlap and index == 0 else f"{9000 + index:064x}"
        )
        row["rejection_reason_code"] = TARGET_REASON
        row["rejection_registry_sha256"] = file_sha(registry)
        entries[relative] = row
    if bad_observation_path:
        next(iter(entries.values()))["path"] = "wrong/path"

    prior_count = len(prior_tasks)
    prior_rows = transactions[:prior_count]
    current_rows = transactions[:]
    if prefix_tamper:
        current_rows = transactions[prior_count:] + transactions[:prior_count]
    total_tasks = len(set(accepted_tasks))
    inventory = {
        "all_physical_runs": len(accepted_tasks),
        "eligible_runs": len(accepted_tasks),
        "eligible_endpoints": 2 * len(accepted_tasks),
        "eligible_structural_pairs": len(accepted_tasks),
        "eligible_tasks": total_tasks,
    }
    prior_inventory = {
        "all_physical_runs": prior_count,
        "eligible_runs": prior_count,
        "eligible_endpoints": 2 * prior_count,
        "eligible_structural_pairs": prior_count,
        "eligible_tasks": len(set(prior_tasks)),
    }
    prior_snapshot, prior_tx_sha = make_snapshot(state, prior_rows, prior_inventory)
    current_snapshot, current_tx_sha = make_snapshot(state, current_rows, inventory)
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
    prior_known = {
        "observed_archives": 1 + prior_count,
        "baseline_archives": 1,
        "accepted_archives": prior_count,
        "structural_rejected_archives": 0,
        "alias_quarantined_archives": 0,
        "pending_archives": 0,
        "physical_runs": prior_count,
        "eligible_runs": prior_count,
        "eligible_endpoints": 2 * prior_count,
        "eligible_structural_pairs": prior_count,
        "eligible_tasks": len(set(prior_tasks)),
    }
    prior_result, prior_verification = prior_evidence(root, prior_snapshot, prior_known)
    current_known: dict[str, object] = {
        "observed_archives": len(entries),
        "baseline_archives": 1,
        "accepted_archives": len(accepted_tasks),
        "structural_rejected_archives": target_count,
        "alias_quarantined_archives": 0,
        "pending_archives": 0,
        "rejection_reason_counts": {TARGET_REASON: target_count},
        "physical_runs": len(accepted_tasks),
        "eligible_runs": len(accepted_tasks),
        "eligible_endpoints": 2 * len(accepted_tasks),
        "eligible_structural_pairs": len(accepted_tasks),
        "eligible_tasks": total_tasks,
    }
    protocol = root / "protocol.json"
    write_json(
        protocol,
        protocol_value(
            root,
            observations,
            registry,
            prior_result,
            prior_verification,
            prior_snapshot,
            current_snapshot,
            prior_tx_sha,
            current_tx_sha,
            prior_count,
            len(accepted_tasks),
            prior_known,
            current_known,
            len(entries) - prior_known["observed_archives"],
            len(accepted_tasks) - prior_count,
            target_count,
        ),
    )
    return {
        "root": root,
        "state": state,
        "protocol": protocol,
        "observations": observations,
        "target_task": target,
        "target_relative": f"2000/{target}-4seeds.tar.gz",
        "run_ids": [f"run-{index:03d}" for index in range(len(accepted_tasks))],
    }


@pytest.mark.parametrize(
    ("support", "expected_status", "prior_archives", "new_archives"),
    [
        ("strong", "INCREMENTAL_ARCHIVE_SUPPORT_PREEXISTING_STRONG", 1, 0),
        ("contemporaneous", "INCREMENTAL_ARCHIVE_SUPPORT_CONTEMPORANEOUS_ONLY", 0, 1),
        ("absent", "INCREMENTAL_ARCHIVE_SUPPORT_ABSENT", 0, 0),
    ],
)
def test_three_frozen_decision_paths_match_independent_verifier(
    tmp_path: Path,
    support: str,
    expected_status: str,
    prior_archives: int,
    new_archives: int,
) -> None:
    case = fixture(tmp_path, support)
    result = build_result(case["protocol"], case["observations"], case["state"])
    assert result["status"] == expected_status
    assert result["anonymized_target_support"]["prior_prefix"]["accepted_archives"] == prior_archives
    assert result["anonymized_target_support"]["new_window"]["accepted_archives"] == new_archives
    result_path = case["root"] / "result.json"
    write_json(result_path, result)
    receipt = verify(case["protocol"], case["observations"], result_path, case["state"])
    assert receipt["status"] == "INDEPENDENT_INCREMENTAL_ARCHIVE_SUPPORT_PASS"
    assert receipt["result_status"] == expected_status
    assert receipt["all_result_fields_equal"] is True


@pytest.mark.parametrize(
    ("options", "message"),
    [
        ({"prefix_tamper": True}, "prior byte prefix"),
        ({"target_count": 2}, "exactly one"),
        ({"target_payload_overlap": True}, "overlaps accepted"),
        ({"bad_observation_path": True}, "path/presence"),
    ],
)
def test_integrity_attacks_fail_closed(
    tmp_path: Path, options: dict[str, object], message: str
) -> None:
    case = fixture(tmp_path, "strong", **options)
    with pytest.raises(IncrementalArchiveAuditError, match=message):
        build_result(case["protocol"], case["observations"], case["state"])


def test_result_and_receipt_emit_no_identity_values(tmp_path: Path) -> None:
    case = fixture(tmp_path, "strong")
    result = build_result(case["protocol"], case["observations"], case["state"])
    result_path = case["root"] / "result.json"
    write_json(result_path, result)
    receipt = verify(case["protocol"], case["observations"], result_path, case["state"])
    rendered = json.dumps({"result": result, "receipt": receipt}, sort_keys=True)
    assert case["target_task"] not in rendered
    assert case["target_relative"] not in rendered
    assert all(run_id not in rendered for run_id in case["run_ids"])
    assert result["access_attestation"]["labels_grades_outcomes_predictions_accuracy_or_utility_read"] is False
    assert receipt["outcomes_predictions_labels_read"] is False


def test_independent_verifier_rejects_candidate_tamper(tmp_path: Path) -> None:
    case = fixture(tmp_path, "strong")
    result = build_result(case["protocol"], case["observations"], case["state"])
    result["anonymized_target_support"]["prior_prefix"]["eligible_endpoints"] += 1
    result_path = case["root"] / "tampered_result.json"
    write_json(result_path, result)
    with pytest.raises(IndependentVerificationError, match="differs"):
        verify(case["protocol"], case["observations"], result_path, case["state"])


def test_independent_verifier_does_not_import_producer() -> None:
    verifier_source = Path("phase1/verify_incremental_archive_rejection_support.py").read_text(
        encoding="utf-8"
    )
    assert "audit_incremental_archive_rejection_support" not in verifier_source


def test_adjacent_watcher_container_schema_fails_closed(tmp_path: Path) -> None:
    case = fixture(tmp_path, "strong")
    observations = json.loads(case["observations"].read_text(encoding="utf-8"))
    observations.pop("baseline_sealed_at_epoch")
    observations["minimum_age_seconds"] = 60
    observations["updated_at_utc"] = "2026-09-01T00:00:00Z"
    write_json(case["observations"], observations)
    protocol = json.loads(case["protocol"].read_text(encoding="utf-8"))
    protocol["inputs"]["current_observations_sha256"] = file_sha(case["observations"])
    protocol["inputs"]["current_observations_bytes"] = case["observations"].stat().st_size
    write_json(case["protocol"], protocol)
    with pytest.raises(IncrementalArchiveAuditError, match="schema mismatch"):
        build_result(case["protocol"], case["observations"], case["state"])
