from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

import phase1.prepare_balanced_continuation_e2a as prepare


def sha(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def write_json(path: Path, value: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, sort_keys=True) + "\n", encoding="utf-8")


def make_data_gate(root: Path) -> Path:
    inputs = root / "e2a_inputs"
    split = root / "e2a_split"
    inputs.mkdir(parents=True)
    (split / "public").mkdir(parents=True)
    anchors = []
    vault = []
    calibration = []
    for task_index, task in enumerate(prepare.TASKS):
        for parent_index in range(4):
            anchor_id = sha(f"anchor-{task_index}-{parent_index}".encode())
            if parent_index == 0:
                calibration.append(anchor_id)
            for sibling_index in range(2):
                sibling_id = f"sibling-{task_index}-{parent_index}-{sibling_index}"
                code = f"print({task_index}, {parent_index}, {sibling_index})\n"
                code_sha = sha(code.encode())
                anchors.append({
                    "anchor_id": anchor_id,
                    "task": task,
                    "source_run_id": f"run-{task_index}-{parent_index}",
                    "parent_id": f"parent-{task_index}-{parent_index}",
                    "sibling_id": sibling_id,
                    "code_sha256": code_sha,
                    "anchor_contract_sha256": sha(
                        f"contract-{task_index}-{parent_index}".encode()
                    ),
                })
                vault.append({
                    "sibling_id": sibling_id, "code": code, "code_sha256": code_sha,
                })
    (inputs / "anchors.jsonl").write_text(
        "".join(json.dumps(row) + "\n" for row in anchors), encoding="utf-8"
    )
    (inputs / "code_vault.jsonl").write_text(
        "".join(json.dumps(row) + "\n" for row in vault), encoding="utf-8"
    )
    write_json(inputs / "calibration_anchor_ids.json", calibration)
    write_json(inputs / "selected_public.json", [])
    input_manifest = inputs / "sha256_manifest.json"
    write_json(input_manifest, {})
    input_summary = {
        "status": "E2A_INPUTS_FROZEN_OUTCOME_BLIND",
        "tasks": list(prepare.TASKS),
        "anchor_count": 24,
        "physical_run_count": 24,
        "sibling_count": 48,
        "calibration_anchor_count": 6,
        "contains_outcomes": False,
        "scientific_outcomes_read": False,
        "official_test_read": False,
        "first960_or_prospective_read": False,
        "anchors_sha256": sha((inputs / "anchors.jsonl").read_bytes()),
        "code_vault_sha256": sha((inputs / "code_vault.jsonl").read_bytes()),
        "calibration_anchor_ids_sha256": sha(
            (inputs / "calibration_anchor_ids.json").read_bytes()
        ),
    }
    write_json(inputs / "summary.json", input_summary)

    split_manifest = split / "sha256_manifest.json"
    write_json(split_manifest, {})
    split_summary = {
        "status": "VERIFIED_E2A_80_10_10_SPLIT_BUILT",
        "tasks": list(prepare.TASKS),
        "dtest_rows_read": 0,
        "official_sample_submission_read": False,
        "private_answers_read": False,
        "public_dataset_contract_sha256": "a" * 64,
        "split_manifest_sha256_opaque": "b" * 64,
    }
    write_json(split / "summary.json", split_summary)
    write_json(root / "e2a_inputs.verify.json", {
        "status": "VERIFIED_E2A_INPUTS_OUTCOME_BLIND_DISTINCT_RUNS",
        "producer_imported": False,
        "tasks": list(prepare.TASKS),
        "anchors": 24,
        "physical_runs": 24,
        "siblings": 48,
        "calibration_anchors": 6,
        "scientific_outcomes_read": False,
        "official_test_read": False,
        "first960_or_prospective_read": False,
        "result_manifest_sha256": sha(input_manifest.read_bytes()),
    })
    write_json(root / "e2a_split.verify.json", {
        "status": "VERIFIED_E2A_SPLIT_RECONSTRUCTION_NO_DTEST_READ",
        "producer_imported": False,
        "tasks": list(prepare.TASKS),
        "dtest_rows_read": 0,
        "official_sample_submission_read": False,
        "private_answers_read": False,
        "result_manifest_sha256": sha(split_manifest.read_bytes()),
    })
    (root / "source_commit.txt").write_text("2" * 40 + "\n", encoding="ascii")
    (root / "top_manifest.sha256").write_text("manifest\n", encoding="ascii")
    return root


def test_prepare_freezes_sixty_variable_k_rollouts(tmp_path: Path, monkeypatch) -> None:
    data_gate = make_data_gate(tmp_path / "data-gate")
    container = tmp_path / "image.sif"
    container.write_bytes(b"container")
    worker_python = tmp_path / "python"
    worker_python.write_bytes(b"python")
    qwen_receipt = tmp_path / "qwen-gate.json"
    write_json(qwen_receipt, {"status": "test"})
    monkeypatch.setattr(prepare, "EXPECTED_CONTAINER_SHA256", sha(container.read_bytes()))
    monkeypatch.setattr(prepare, "WORKER_PYTHON", worker_python)
    monkeypatch.setattr(prepare, "exact_source_commit", lambda: "1" * 40)
    monkeypatch.setattr(prepare, "validate_worker_contract", lambda value: value)
    monkeypatch.setattr(
        prepare,
        "validate_qwen_execution_gate",
        lambda _: (qwen_receipt.resolve(), prepare.QWEN_REPAIRED_EXECUTION_GATE_SHA256),
    )
    output = tmp_path / "prepared"
    plan = prepare.build(argparse.Namespace(
        data_gate=str(data_gate), container=str(container), output=str(output),
        qwen_execution_smoke_receipt=str(qwen_receipt),
        created_utc="2026-08-19T00:00:00Z",
    ))
    assert plan["rollout_jobs"] == 60
    assert plan["candidate_executions"] == 120
    assert plan["operator_api_calls"] == 60
    assert plan["expected_gpu_hours"] == prepare.EXPECTED_GPU_HOURS
    assert plan["candidate_timeout_upper_bound_gpu_hours"] == 20.0
    assert len(plan["engineering_wave_indices"]) == 12
    assert len(plan["remaining_wave_indices"]) == 48
    assert len(plan["warm_smoke_assignment_indices"]) == 6
    assert plan["formal_submission_requires_passing_warm_smoke"] is True
    rows = prepare.read_jsonl(output / "assignment" / "assignment_manifest.jsonl")
    first = [rows[index] for index in plan["engineering_wave_indices"]]
    assert {row["task"] for row in first} == set(prepare.TASKS)
    for task in prepare.TASKS:
        task_rows = [row for row in first if row["task"] == task]
        assert len(task_rows) == 2
        assert len({row["block_id"] for row in task_rows}) == 1
    smoke = [rows[index] for index in plan["warm_smoke_assignment_indices"]]
    assert {row["task"] for row in smoke} == set(prepare.TASKS)
