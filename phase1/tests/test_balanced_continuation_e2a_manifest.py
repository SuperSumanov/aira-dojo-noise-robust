from __future__ import annotations

import argparse
import hashlib
import json
from collections import Counter
from pathlib import Path

import pytest

from phase1.balanced_continuation_e2a_manifest import build
from phase1.balanced_continuation_worker import load_assignment
from phase1.verify_balanced_continuation_e2a_manifest import verify


def canon(value) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":")).encode()


def make_inputs(tmp_path: Path) -> tuple[Path, Path, Path]:
    anchors = []
    calibration = []
    for task_index in range(6):
        for parent_index in range(4):
            anchor_id = hashlib.sha256(f"a-{task_index}-{parent_index}".encode()).hexdigest()
            contract_sha = hashlib.sha256(f"c-{task_index}-{parent_index}".encode()).hexdigest()
            if parent_index == 0:
                calibration.append(anchor_id)
            for sibling_index in range(2):
                anchors.append({
                    "anchor_id": anchor_id, "task": f"task-{task_index}",
                    "source_run_id": f"run-{task_index}-{parent_index}",
                    "parent_id": f"parent-{task_index}-{parent_index}",
                    "sibling_id": f"sibling-{task_index}-{parent_index}-{sibling_index}",
                    "code_sha256": hashlib.sha256(
                        f"code-{task_index}-{parent_index}-{sibling_index}".encode()
                    ).hexdigest(),
                    "anchor_contract_sha256": contract_sha,
                })
    anchor_path = tmp_path / "anchors.jsonl"
    anchor_path.write_bytes(b"".join(canon(row) + b"\n" for row in anchors))
    calibration_path = tmp_path / "calibration.json"
    calibration_path.write_bytes(canon(calibration) + b"\n")
    contract = {
        "schema_version": "balanced-continuation-contract-v1", "model_id": "model",
        "provider": "provider", "operator_config_sha256": "1" * 64,
        "prompt_sha256": "2" * 64, "source_commit": "3" * 40,
        "dataset_contract_sha256": "4" * 64, "evaluator_contract_sha256": "5" * 64,
        "hardware_class": "single-rtx3090-24gb", "execution_timeout_seconds": 600,
        "continuation_horizon": 1, "debug_policy": "fixed_one_operator_per_step",
        "workspace_policy": "fresh_per_rollout", "temperature": 0.0,
    }
    contract_path = tmp_path / "contract.json"
    contract_path.write_bytes(canon(contract) + b"\n")
    return anchor_path, calibration_path, contract_path


def test_e2a_manifest_has_exact_variable_k_and_worker_reads_it(tmp_path: Path) -> None:
    anchors, calibration, contract = make_inputs(tmp_path)
    output = (tmp_path / "result").resolve()
    summary = build(argparse.Namespace(
        anchors=str(anchors), calibration_anchors=str(calibration), contract=str(contract),
        output=str(output), siblings_per_anchor=2, horizon=1, seed=20260819,
        created_utc="2026-08-19T00:00:00Z",
    ))
    rows = [json.loads(line) for line in (output / "assignment_manifest.jsonl").read_text().splitlines()]
    assert summary["rollout_jobs"] == len(rows) == 60
    assert summary["planned_total_candidate_executions"] == 120
    counts = Counter(row["sibling_id"] for row in rows)
    assert Counter(counts.values()) == Counter({1: 36, 2: 12})
    blocks = Counter(row["block_id"] for row in rows)
    assert len(blocks) == 30 and set(blocks.values()) == {2}
    assignment, _, _ = load_assignment(output, 59)
    assert assignment == rows[59]
    receipt = tmp_path / "verify.json"
    verification = verify(argparse.Namespace(result=str(output), receipt=str(receipt)))
    assert verification["status"] == "VERIFIED_E2A_OUTCOME_BLIND_VARIABLE_K_ASSIGNMENT"
    assert verification["producer_imported"] is False
    assert verification["siblings_once"] == 36
    assert verification["siblings_twice"] == 12


def test_independent_verifier_rejects_variable_k_tamper(tmp_path: Path) -> None:
    anchors, calibration, contract = make_inputs(tmp_path)
    output = (tmp_path / "result").resolve()
    build(argparse.Namespace(
        anchors=str(anchors), calibration_anchors=str(calibration), contract=str(contract),
        output=str(output), siblings_per_anchor=2, horizon=1, seed=20260819,
        created_utc="2026-08-19T00:00:00Z",
    ))
    rows = (output / "assignment_manifest.jsonl").read_text(encoding="utf-8").splitlines()
    rows[0], rows[1] = rows[1], rows[0]
    (output / "assignment_manifest.jsonl").write_text(
        "\n".join(rows) + "\n", encoding="utf-8", newline="\n"
    )
    with pytest.raises(Exception, match="artifact hash mismatch"):
        verify(argparse.Namespace(result=str(output), receipt=str(tmp_path / "verify.json")))


def test_calibration_task_duplication_fails(tmp_path: Path) -> None:
    anchors, calibration, contract = make_inputs(tmp_path)
    values = json.loads(calibration.read_bytes())
    values[-1] = values[0]
    calibration.write_bytes(canon(values) + b"\n")
    with pytest.raises(Exception, match="six unique"):
        build(argparse.Namespace(
            anchors=str(anchors), calibration_anchors=str(calibration), contract=str(contract),
            output=str((tmp_path / "result").resolve()), siblings_per_anchor=2,
            horizon=1, seed=20260819, created_utc="2026-08-19T00:00:00Z",
        ))
