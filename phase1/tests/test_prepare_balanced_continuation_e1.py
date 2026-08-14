from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

import pytest

import phase1.prepare_balanced_continuation_e1 as prepare


def sha(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def write_json(path: Path, value: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, sort_keys=True) + "\n", encoding="utf-8")


@pytest.mark.parametrize("operator_profile", ["deepseek", "qwen"])
def test_prepare_freezes_eight_rollouts_and_two_score_blind_stages(
    tmp_path: Path, monkeypatch, operator_profile: str
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
    input_summary = {
        "contains_outcomes": False,
        "first960_or_prospective_read": False,
        "selected_frozen_endpoint_overlap": 0,
        "selected_frozen_run_overlap": 0,
        "tasks": list(prepare.TASKS),
    }
    input_receipt = {
        "status": "VERIFIED_E1_INPUTS_OUTCOME_BLIND_ZERO_FROZEN_OVERLAP"
    }
    if operator_profile == "qwen":
        input_summary.update({
            "prior_selection_identity_only_read": True,
            "prior_selection_sha256": prepare.QWEN_PRIOR_SELECTION_SHA256,
            "excluded_prior_run_count": 2,
            "excluded_prior_anchor_count": 2,
            "selected_prior_run_overlap": 0,
        })
        input_receipt.update({
            "prior_selection_sha256": prepare.QWEN_PRIOR_SELECTION_SHA256,
            "selected_prior_run_overlap": 0,
        })
        (data_gate / "operator_profile.txt").write_text("qwen\n", encoding="ascii")
    write_json(inputs / "summary.json", input_summary)
    write_json(split / "summary.json", {
        "tasks": list(prepare.TASKS),
        "dtest_rows_read": 0,
        "private_answers_read": False,
        "public_dataset_contract_sha256": "a" * 64,
        "split_manifest_sha256_opaque": "b" * 64,
    })
    write_json(data_gate / "e1_inputs.verify.json", input_receipt)
    write_json(data_gate / "e1_split.verify.json", {
        "status": "VERIFIED_E1_SPLIT_RECONSTRUCTION_NO_DTEST_READ"
    })
    (data_gate / "source_commit.txt").write_text("2" * 40 + "\n", encoding="ascii")
    (data_gate / "top_manifest.sha256").write_text("manifest\n", encoding="ascii")
    container = tmp_path / "image.sif"
    container.write_bytes(b"container")
    worker_python = tmp_path / "shared-python"
    worker_python.write_bytes(b"python-binary")
    monkeypatch.setattr(prepare, "EXPECTED_CONTAINER_SHA256", sha(container.read_bytes()))
    monkeypatch.setattr(prepare, "WORKER_PYTHON", worker_python)
    monkeypatch.setattr(prepare, "exact_source_commit", lambda: "1" * 40)
    monkeypatch.setattr(prepare, "validate_worker_contract", lambda value: value)

    output = tmp_path / "prepared"
    qwen_receipt = (
        Path(__file__).resolve().parents[1]
        / "results"
        / "balanced_continuation_qwen_execution_smoke_20260814_d89311a_a2"
        / "verification.task_type_repair.047420c.json"
    )
    plan = prepare.build(argparse.Namespace(
        data_gate=str(data_gate),
        container=str(container),
        output=str(output),
        created_utc="2026-08-14T00:00:00Z",
        operator_profile=operator_profile,
        qwen_execution_smoke_receipt=(
            str(qwen_receipt) if operator_profile == "qwen" else None
        ),
    ))
    assert plan["rollout_jobs"] == 8
    assert plan["candidate_executions"] == 16
    assert plan["operator_api_calls"] == 8
    assert plan["worker_python_path"] == worker_python.as_posix()
    assert plan["worker_python_sha256"] == sha(worker_python.read_bytes())
    assert len(plan["stage_one_engineering_gate_indices"]) == 4
    assert len(plan["stage_two_remaining_indices"]) == 4
    assert plan["operator_profile"] == operator_profile
    if operator_profile == "qwen":
        assert (
            plan["qwen_execution_smoke_receipt_sha256"]
            == prepare.QWEN_REPAIRED_EXECUTION_GATE_SHA256
        )
    rows = prepare.read_jsonl(output / "assignment" / "assignment_manifest.jsonl")
    first = [rows[index] for index in plan["stage_one_engineering_gate_indices"]]
    assert {row["task"] for row in first} == set(prepare.TASKS)
    for task in prepare.TASKS:
        task_rows = [row for row in first if row["task"] == task]
        assert len(task_rows) == 2
        assert len({row["block_id"] for row in task_rows}) == 1
    assert plan["stage_one_outcomes_must_remain_sealed"] is True
    assert plan["stage_two_gate_uses_scores"] is False


def test_qwen_profile_requires_a_passing_execution_smoke_receipt(tmp_path: Path) -> None:
    with pytest.raises(prepare.PrepareError, match="requires an explicit passing"):
        prepare.validate_qwen_execution_gate(None)
    receipt = tmp_path / "failed-smoke.json"
    write_json(receipt, {
        "schema_version": "balanced-continuation-qwen-execution-smoke-verification-v1",
        "status": "VERIFIED_QWEN_EXECUTION_SMOKE_FAIL",
        "producer_imported": False,
        "results": 2,
        "tasks": list(prepare.TASKS),
        "candidate_executions": 2,
        "api_calls": 0,
        "dsearch_rows_read": 0,
        "dval_rows_read": 0,
        "dtest_rows_read": 0,
        "external_score_or_gain_reported": False,
        "all_gate_pass": False,
        "summary_sha256": ["a" * 64, "b" * 64],
    })
    with pytest.raises(prepare.PrepareError, match="not a passing frozen gate"):
        prepare.validate_qwen_execution_gate(str(receipt))


def test_qwen_profile_accepts_only_exact_task_type_repair_receipt(tmp_path: Path) -> None:
    receipt = (
        Path(__file__).resolve().parents[1]
        / "results"
        / "balanced_continuation_qwen_execution_smoke_20260814_d89311a_a2"
        / "verification.task_type_repair.047420c.json"
    )
    resolved, digest = prepare.validate_qwen_execution_gate(str(receipt))
    assert resolved == receipt.resolve()
    assert digest == prepare.QWEN_REPAIRED_EXECUTION_GATE_SHA256

    value = json.loads(receipt.read_text(encoding="utf-8"))
    value["corrected_results"][0]["submission_shape"]["valid"] = False
    tampered = tmp_path / "tampered-repair.json"
    write_json(tampered, value)
    with pytest.raises(prepare.PrepareError, match="not a passing frozen gate"):
        prepare.validate_qwen_execution_gate(str(tampered))


def test_qwen_preparation_rejects_data_gate_without_fresh_anchor_proof(
    tmp_path: Path, monkeypatch
) -> None:
    data_gate = tmp_path / "data-gate"
    inputs = data_gate / "e1_inputs"
    split = data_gate / "e1_split"
    inputs.mkdir(parents=True)
    split.mkdir()
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
    })
    write_json(data_gate / "e1_inputs.verify.json", {
        "status": "VERIFIED_E1_INPUTS_OUTCOME_BLIND_ZERO_FROZEN_OVERLAP"
    })
    write_json(data_gate / "e1_split.verify.json", {
        "status": "VERIFIED_E1_SPLIT_RECONSTRUCTION_NO_DTEST_READ"
    })
    container = tmp_path / "image.sif"
    container.write_bytes(b"container")
    worker_python = tmp_path / "shared-python"
    worker_python.write_bytes(b"python-binary")
    monkeypatch.setattr(prepare, "EXPECTED_CONTAINER_SHA256", sha(container.read_bytes()))
    monkeypatch.setattr(prepare, "WORKER_PYTHON", worker_python)
    monkeypatch.setattr(prepare, "exact_source_commit", lambda: "1" * 40)
    receipt = (
        Path(__file__).resolve().parents[1]
        / "results"
        / "balanced_continuation_qwen_execution_smoke_20260814_d89311a_a2"
        / "verification.task_type_repair.047420c.json"
    )
    with pytest.raises(prepare.PrepareError, match="fresh-anchor data-gate"):
        prepare.build(argparse.Namespace(
            data_gate=str(data_gate),
            container=str(container),
            output=str(tmp_path / "prepared"),
            created_utc="2026-08-14T00:00:00Z",
            operator_profile="qwen",
            qwen_execution_smoke_receipt=str(receipt),
        ))
