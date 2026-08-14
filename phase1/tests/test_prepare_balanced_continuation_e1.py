from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

import phase1.prepare_balanced_continuation_e1 as prepare


def sha(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def write_json(path: Path, value: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, sort_keys=True) + "\n", encoding="utf-8")


def test_prepare_freezes_eight_rollouts_and_two_score_blind_stages(
    tmp_path: Path, monkeypatch
) -> None:
    data_gate = tmp_path / "data-gate"
    inputs = data_gate / "e1_inputs"
    split = data_gate / "e1_split"
    inputs.mkdir(parents=True)
    (split / "public").mkdir(parents=True)
    anchors = []
    vault = []
    for task_index, task in enumerate(prepare.TASKS):
        for sibling_index in range(2):
            sibling = f"sibling-{task_index}-{sibling_index}"
            code = f"print({task_index * 2 + sibling_index})\n"
            anchors.append({
                "anchor_id": f"anchor-{task_index}",
                "task": task,
                "source_run_id": f"run-{task_index}",
                "parent_id": f"parent-{task_index}",
                "sibling_id": sibling,
                "code_sha256": sha(code.encode()),
                "anchor_contract_sha256": f"{task_index + 1:064x}",
            })
            vault.append({
                "sibling_id": sibling,
                "code": code,
                "code_sha256": sha(code.encode()),
            })
    (inputs / "anchors.jsonl").write_text(
        "".join(json.dumps(row) + "\n" for row in anchors), encoding="utf-8"
    )
    (inputs / "code_vault.jsonl").write_text(
        "".join(json.dumps(row) + "\n" for row in vault), encoding="utf-8"
    )
    write_json(inputs / "summary.json", {
        "contains_outcomes": False,
        "first960_or_prospective_read": False,
        "selected_frozen_endpoint_overlap": 0,
        "selected_frozen_run_overlap": 0,
        "tasks": list(prepare.TASKS),
    })
    write_json(split / "summary.json", {
        "tasks": list(prepare.TASKS),
        "dtest_rows_read": 0,
        "private_answers_read": False,
        "public_dataset_contract_sha256": "a" * 64,
        "split_manifest_sha256_opaque": "b" * 64,
    })
    write_json(data_gate / "e1_inputs.verify.json", {
        "status": "VERIFIED_E1_INPUTS_OUTCOME_BLIND_ZERO_FROZEN_OVERLAP"
    })
    write_json(data_gate / "e1_split.verify.json", {
        "status": "VERIFIED_E1_SPLIT_RECONSTRUCTION_NO_DTEST_READ"
    })
    (data_gate / "source_commit.txt").write_text("2" * 40 + "\n", encoding="ascii")
    (data_gate / "top_manifest.sha256").write_text("manifest\n", encoding="ascii")
    container = tmp_path / "image.sif"
    container.write_bytes(b"container")
    monkeypatch.setattr(prepare, "EXPECTED_CONTAINER_SHA256", sha(container.read_bytes()))
    monkeypatch.setattr(prepare, "exact_source_commit", lambda: "1" * 40)
    monkeypatch.setattr(prepare, "validate_worker_contract", lambda value: value)

    output = tmp_path / "prepared"
    plan = prepare.build(argparse.Namespace(
        data_gate=str(data_gate),
        container=str(container),
        output=str(output),
        created_utc="2026-08-14T00:00:00Z",
    ))
    assert plan["rollout_jobs"] == 8
    assert plan["candidate_executions"] == 16
    assert plan["operator_api_calls"] == 8
    assert len(plan["stage_one_engineering_gate_indices"]) == 4
    assert len(plan["stage_two_remaining_indices"]) == 4
    rows = prepare.read_jsonl(output / "assignment" / "assignment_manifest.jsonl")
    first = [rows[index] for index in plan["stage_one_engineering_gate_indices"]]
    assert {row["task"] for row in first} == set(prepare.TASKS)
    for task in prepare.TASKS:
        task_rows = [row for row in first if row["task"] == task]
        assert len(task_rows) == 2
        assert len({row["block_id"] for row in task_rows}) == 1
    assert plan["stage_one_outcomes_must_remain_sealed"] is True
    assert plan["stage_two_gate_uses_scores"] is False
