from __future__ import annotations

import argparse
import hashlib
import json
import shutil
from pathlib import Path

import pytest

import phase1.verify_balanced_continuation_e2a_collection as collection
import phase1.verify_balanced_continuation_e2a_archive as archive


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


def task_score(task: str, parent: int, sibling: int, ordinal: int) -> float:
    metric = collection.TASK_SPECS[task]["metric"]
    if metric in {"multiclass_log_loss", "mean_columnwise_rmsle"}:
        return 0.8 + parent * 0.01 - sibling * 0.1 - ordinal * 0.02
    if metric in {"accuracy", "roc_auc"}:
        return 0.45 + parent * 0.01 + sibling * 0.1 + ordinal * 0.02
    return -0.2 + parent * 0.05 + sibling * 0.2 + ordinal * 0.03


def fixture(tmp_path: Path) -> argparse.Namespace:
    assignment_root = tmp_path / "assignment"
    worker_root = tmp_path / "worker"
    receipt_root = tmp_path / "receipts"
    workspace_root = tmp_path / "workspaces"
    sealed_root = tmp_path / "sealed"
    for path in (assignment_root, worker_root, receipt_root, workspace_root, sealed_root):
        path.mkdir()
    contract_value = contract()
    contract_path = tmp_path / "contract.json"
    write_json(contract_path, contract_value)
    rows = []
    for task_index, task in enumerate(collection.TASKS):
        for parent in range(4):
            replicates = (0, 1) if parent == 0 else (0,)
            anchor = f"anchor-{task_index}-{parent}"
            for replicate in replicates:
                block = hashlib.sha256(f"block-{anchor}-{replicate}".encode()).hexdigest()
                for sibling in range(2):
                    index = len(rows)
                    rollout_id = f"{index + 100:064x}"
                    sibling_id = f"sibling-{task_index}-{parent}-{sibling}"
                    row = {
                        "global_order": index,
                        "rollout_id": rollout_id,
                        "block_id": block,
                        "block_replicate": replicate,
                        "task": task,
                        "sibling_id": sibling_id,
                        "source_run_id": f"run-{task_index}-{parent}",
                        "anchor_id": anchor,
                        "rollout_seed": 1000 + index,
                    }
                    rows.append(row)
                    (worker_root / rollout_id / "steps").mkdir(parents=True)
                    workspace = workspace_root / rollout_id
                    workspace.mkdir()
                    sealed_rollout = sealed_root / rollout_id
                    sealed_rollout.mkdir()
                    token = f"{index + 200:032x}"
                    commitments = []
                    visible = []
                    for ordinal in range(2):
                        score = task_score(task, parent, sibling, ordinal)
                        orientation = int(collection.TASK_SPECS[task]["orientation"])
                        artifact_sha = hashlib.sha256(
                            f"artifact-{index}-{ordinal}".encode()
                        ).hexdigest()
                        execution = {
                            "schema_version": "balanced-continuation-public-execution-receipt-v1",
                            "rollout_id": rollout_id,
                            "workspace_token": token,
                            "task": task,
                            "execution_ordinal": ordinal,
                            "code_sha256": "a" * 64,
                            "execution_status": "ok",
                            "process_started": True,
                            "candidate_execution_attempted": True,
                            "exit_code": 0,
                            "timed_out": False,
                            "wall_time_seconds": 2.0 + ordinal,
                            "terminal_output": "ok",
                            "terminal_output_sha256": hashlib.sha256(b"ok").hexdigest(),
                            "artifact_sha256": artifact_sha,
                            "public_data_read_only": True,
                            "private_paths_mounted": False,
                            "retry_count": 0,
                        }
                        search = {
                            "schema_version": "balanced-continuation-dsearch-receipt-v1",
                            "rollout_id": rollout_id,
                            "workspace_token": token,
                            "task": task,
                            "execution_ordinal": ordinal,
                            "artifact_sha256": artifact_sha,
                            "submission_valid": True,
                            "dsearch_score": score,
                            "search_utility": orientation * score,
                            "orientation": orientation,
                            "split_manifest_sha256": contract_value[
                                "split_manifest_sha256_opaque"
                            ],
                            "evaluator_executable_sha256": contract_value[
                                "search_evaluator_executable_sha256"
                            ],
                            "grade_return_code": 0,
                            "private_bytes_exposed_to_candidate": 0,
                            "dtest_rows_read": 0,
                        }
                        sealed = {
                            "schema_version": "balanced-continuation-sealed-dval-receipt-v1",
                            "rollout_id": rollout_id,
                            "workspace_token": token,
                            "task": task,
                            "execution_ordinal": ordinal,
                            "artifact_sha256": artifact_sha,
                            "submission_valid": True,
                            "dval_score": score,
                            "dval_utility": orientation * score,
                            "orientation": orientation,
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
                        step = worker_root / rollout_id / "steps" / f"step_{ordinal:03d}"
                        write_json(step / "execution.json", execution)
                        write_json(step / "dsearch.json", search)
                        sealed_path = sealed_rollout / f"dval_{ordinal:03d}.json"
                        write_json(sealed_path, sealed)
                        commitments.append(hashlib.sha256(sealed_path.read_bytes()).hexdigest())
                        visible.append(search["search_utility"])
                    write_json(receipt_root / f"{rollout_id}.verify.json", {
                        "status": collection.WORKER_RECEIPT_STATUS,
                        "worker_imported": False,
                        "sealed_values_opened": False,
                        "rollout_id": rollout_id,
                        "global_order": index,
                        "block_id": block,
                        "block_replicate": replicate,
                        "task": task,
                        "sibling_id": sibling_id,
                        "source_run_id": f"run-{task_index}-{parent}",
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
                        "workspace_path": str(workspace.resolve()),
                        "workspace_token": token,
                        "visible_dsearch_utilities": visible,
                        "candidate_wall_time_seconds": [2.0, 3.0],
                        "api_usage": [{"api_calls": 1, "retry_count": 0}],
                    })
    assert len(rows) == 60
    (assignment_root / "assignment_manifest.jsonl").write_text(
        "".join(json.dumps(row) + "\n" for row in rows), encoding="utf-8"
    )
    assignment_receipt = tmp_path / "assignment.verify.json"
    write_json(assignment_receipt, {
        "status": "VERIFIED_E2A_OUTCOME_BLIND_VARIABLE_K_ASSIGNMENT",
        "independent_reconstruction_exact": True,
        "rollout_jobs": 60,
        "planned_total_candidate_executions": 120,
        "planned_operator_api_calls": 60,
        "anchor_count": 24,
        "physical_run_count": 24,
        "task_count": 6,
        "block_count": 30,
        "siblings_once": 36,
        "siblings_twice": 12,
    })
    return argparse.Namespace(
        assignment_result=str(assignment_root),
        assignment_receipt=str(assignment_receipt),
        worker_output_root=str(worker_root),
        worker_receipt_root=str(receipt_root),
        workspace_root=str(workspace_root),
        sealed_root=str(sealed_root),
        real_contract=str(contract_path),
        output=str(tmp_path / "output"),
    )


def test_complete_e2a_collection_yields_quality_only_support(tmp_path: Path) -> None:
    args = fixture(tmp_path)
    summary = collection.verify(args)
    assert summary["rollout_jobs"] == 60
    assert summary["candidate_execution_attempts"] == 120
    assert summary["sealed_files_opened_after_coverage_gate"] == 120
    assert summary["calibration_informative_parents"] == 6
    assert summary["calibration_winner_consistent_parents"] == 6
    assert summary["tasks_with_at_least_3_non_tie_parents"] == 6
    assert summary["tasks_with_all_broad_continuations_valid"] == 6
    assert summary["label_resource_support"] is True
    assert summary["hurdle_support"] is False
    assert summary["quality_only_support"] is True
    assert summary["verdict"] == "QUALITY_ONLY_SUPPORT"
    receipt = archive.verify(Path(args.output), tmp_path / "archive.verify.json")
    assert receipt["status"] == "VERIFIED_INDEPENDENT_E2A_ARCHIVE_AND_GATES"
    assert receipt["producer_imported"] is False
    assert receipt["verdict"] == "QUALITY_ONLY_SUPPORT"


def test_e2a_archive_rejects_gate_tampering(tmp_path: Path) -> None:
    args = fixture(tmp_path)
    collection.verify(args)
    summary_path = Path(args.output) / "summary.json"
    summary = json.loads(summary_path.read_text(encoding="utf-8"))
    summary["verdict"] = "HURDLE_SUPPORT"
    write_json(summary_path, summary)
    manifest_path = Path(args.output) / "sha256_manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    manifest["summary.json"] = hashlib.sha256(summary_path.read_bytes()).hexdigest()
    write_json(manifest_path, manifest)
    with pytest.raises(archive.ArchiveError, match="value mismatch"):
        archive.verify(Path(args.output), tmp_path / "archive.verify.json")


def test_e2a_coverage_failure_precedes_sealed_value_open(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    args = fixture(tmp_path)
    shutil.rmtree(next(iter(Path(args.worker_output_root).iterdir())))
    original = collection.checked
    sealed_reads = 0

    def guarded(path: Path):
        nonlocal sealed_reads
        if Path(args.sealed_root) in path.resolve().parents:
            sealed_reads += 1
        return original(path)

    monkeypatch.setattr(collection, "checked", guarded)
    with pytest.raises(collection.CollectionError, match="worker rollout coverage"):
        collection.verify(args)
    assert sealed_reads == 0
