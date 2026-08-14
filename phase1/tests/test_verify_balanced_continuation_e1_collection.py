from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

import pytest

import phase1.verify_balanced_continuation_e1_collection as collection
import phase1.verify_balanced_continuation_e1_archive as archive_verifier


def write_json(path: Path, value: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, sort_keys=True) + "\n", encoding="utf-8")


def contract() -> dict:
    return {
        "schema_version": "balanced-continuation-real-worker-contract-v1",
        "backend": "aira-dojo-external-v1",
        "source_commit": "1" * 40,
        "container_sha256": "2" * 64,
        "operator_config_sha256": "3" * 64,
        "prompt_sha256": "4" * 64,
        "public_dataset_contract_sha256": "5" * 64,
        "split_manifest_sha256_opaque": "6" * 64,
        "search_evaluator_executable_sha256": "7" * 64,
        "sealed_label_evaluator_executable_sha256": "8" * 64,
        "public_data_root": "/frozen/public",
        "continuation_horizon": 1,
        "operator_timeout_seconds": 240,
        "execution_timeout_seconds": 600,
        "evaluator_timeout_seconds": 120,
        "operator_policy": "debug_if_buggy_else_improve",
        "operator_calls_per_transition": 1,
        "operator_retry_count": 0,
        "execution_retry_count": 0,
        "analyze_operator_calls": 0,
        "workspace_policy": "fresh_per_rollout",
        "candidate_mount_policy": "public_read_only_no_private",
        "score_visibility": "D_search_only",
        "sealed_label_policy": "D_val_external_mode_0600",
        "split_policy": "80/10/10_D_train_D_search_D_val",
        "dtest_policy": "never_read",
    }


def fixture(tmp_path: Path) -> argparse.Namespace:
    assignment = tmp_path / "assignment"
    worker = tmp_path / "worker"
    receipts = tmp_path / "receipts"
    workspaces = tmp_path / "workspaces"
    sealed = tmp_path / "sealed"
    for path in (assignment, worker, receipts, workspaces, sealed):
        path.mkdir()
    rows = []
    contract_value = contract()
    contract_path = tmp_path / "contract.json"
    write_json(contract_path, contract_value)
    for task_index, task in enumerate(collection.TASKS):
        for replicate in range(2):
            block = f"{task_index * 2 + replicate + 1:064x}"
            for sibling_index in range(2):
                index = len(rows)
                rollout_id = f"{index + 20:064x}"
                token = f"{index + 40:032x}"
                sibling = f"sibling-{task_index}-{sibling_index}"
                row = {
                    "global_order": index,
                    "rollout_id": rollout_id,
                    "block_id": block,
                    "block_replicate": replicate,
                    "task": task,
                    "sibling_id": sibling,
                    "source_run_id": f"run-{task_index}",
                    "anchor_id": f"anchor-{task_index}",
                    "rollout_seed": 100 + index,
                }
                rows.append(row)
                (worker / rollout_id).mkdir()
                workspace_path = workspaces / rollout_id
                workspace_path.mkdir()
                sealed_rollout = sealed / rollout_id
                sealed_rollout.mkdir()
                commitments = []
                for ordinal, score in enumerate((0.5, 0.6)):
                    sealed_receipt = {
                        "schema_version": "balanced-continuation-sealed-dval-receipt-v1",
                        "rollout_id": rollout_id,
                        "workspace_token": token,
                        "task": task,
                        "execution_ordinal": ordinal,
                        "artifact_sha256": "a" * 64,
                        "submission_valid": True,
                        "dval_score": score,
                        "dval_utility": score,
                        "orientation": 1,
                        "split_manifest_sha256": contract_value[
                            "split_manifest_sha256_opaque"
                        ],
                        "evaluator_executable_sha256": contract_value[
                            "sealed_label_evaluator_executable_sha256"
                        ],
                        "grade_return_code": 0,
                        "private_bytes_exposed_to_candidate": 0,
                        "dtest_rows_read": 0,
                        "file_mode": 0o600,
                    }
                    path = sealed_rollout / f"dval_{ordinal:03d}.json"
                    write_json(path, sealed_receipt)
                    commitments.append(hashlib.sha256(path.read_bytes()).hexdigest())
                write_json(receipts / f"{rollout_id}.verify.json", {
                    "status": collection.WORKER_RECEIPT_STATUS,
                    "worker_imported": False,
                    "sealed_values_opened": False,
                    "rollout_id": rollout_id,
                    "global_order": index,
                    "block_id": block,
                    "block_replicate": replicate,
                    "task": task,
                    "sibling_id": sibling,
                    "source_run_id": f"run-{task_index}",
                    "source_commit": contract_value["source_commit"],
                    "candidate_execution_attempts": 2,
                    "candidate_processes_started": 2,
                    "operator_calls": 1,
                    "operator_retry_count": 0,
                    "candidate_retry_count": 0,
                    "dtest_rows_read": 0,
                    "network_disabled_verified": True,
                    "public_mount_read_only_verified": True,
                    "private_mounts_verified_zero": True,
                    "sealed_receipts": 2,
                    "sealed_modes_0600_verified": True,
                    "sealed_dval_commitment_sha256s": commitments,
                    "workspace_path": str(workspace_path.resolve()),
                    "workspace_token": token,
                    "visible_dsearch_utilities": [0.49, 0.59],
                    "candidate_wall_time_seconds": [2.0, 3.0],
                    "api_usage": [{"api_calls": 1, "retry_count": 0}],
                })
    (assignment / "assignment_manifest.jsonl").write_text(
        "".join(json.dumps(row) + "\n" for row in rows), encoding="utf-8"
    )
    assignment_receipt = tmp_path / "assignment.verify.json"
    write_json(assignment_receipt, {
        "status": "VERIFIED_OUTCOME_BLIND_BALANCED_ASSIGNMENT",
        "independent_reconstruction_exact": True,
        "rollout_jobs": 8,
        "siblings_per_anchor": 2,
        "replicates_per_sibling": 2,
        "continuation_horizon": 1,
    })
    return argparse.Namespace(
        assignment_result=str(assignment),
        assignment_receipt=str(assignment_receipt),
        worker_output_root=str(worker),
        worker_receipt_root=str(receipts),
        workspace_root=str(workspaces),
        sealed_root=str(sealed),
        real_contract=str(contract_path),
        output=str(tmp_path / "output"),
    )


def test_complete_coverage_opens_exactly_sixteen_sealed_receipts(tmp_path: Path) -> None:
    args = fixture(tmp_path)
    summary = collection.verify(args)
    assert summary["rollout_jobs"] == 8
    assert summary["sealed_files_opened_after_coverage_gate"] == 16
    assert summary["rollouts_with_positive_dval_gain"] == 8
    assert summary["task_replicate_ranking_agreements"] == 2
    assert summary["primary_gate_claim_allowed"] is False
    assert summary["e2_e3_unlocked"] is False
    receipt = archive_verifier.verify(
        Path(args.output), tmp_path / "archive.verify.json"
    )
    assert receipt["status"] == "VERIFIED_INDEPENDENT_E1_ARCHIVE_ANALYSIS"
    assert receipt["producer_imported"] is False


def test_independent_archive_verifier_rejects_aggregate_tampering(tmp_path: Path) -> None:
    args = fixture(tmp_path)
    collection.verify(args)
    sibling_path = Path(args.output) / "sibling_labels.jsonl"
    rows = [json.loads(line) for line in sibling_path.read_text(encoding="utf-8").splitlines()]
    rows[0]["balanced_vh_mean"] += 0.1
    sibling_path.write_text(
        "".join(json.dumps(row, sort_keys=True) + "\n" for row in rows),
        encoding="utf-8",
    )
    manifest_path = Path(args.output) / "sha256_manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    manifest["sibling_labels.jsonl"] = hashlib.sha256(sibling_path.read_bytes()).hexdigest()
    write_json(manifest_path, manifest)
    with pytest.raises(archive_verifier.ArchiveVerificationError, match="numeric mismatch"):
        archive_verifier.verify(Path(args.output), tmp_path / "archive.verify.json")


def test_missing_rollout_fails_before_any_sealed_json_is_parsed(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    args = fixture(tmp_path)
    worker_root = Path(args.worker_output_root)
    next(iter(worker_root.iterdir())).rmdir()
    original_checked = collection.checked
    sealed_reads = 0

    def guarded(path: Path):
        nonlocal sealed_reads
        if Path(args.sealed_root) in path.resolve().parents:
            sealed_reads += 1
        return original_checked(path)

    monkeypatch.setattr(collection, "checked", guarded)
    with pytest.raises(collection.CollectionError, match="worker rollout coverage"):
        collection.verify(args)
    assert sealed_reads == 0
