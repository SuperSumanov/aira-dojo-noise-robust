from __future__ import annotations

import argparse
import builtins
import hashlib
import json
from collections import Counter
from pathlib import Path

import pytest

from phase1 import randomized_sibling_logging_manifest as producer
from phase1 import verify_randomized_sibling_logging_manifest as verifier


def write_json(path: Path, value: object) -> None:
    path.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def base_config() -> dict:
    return {
        "schema_version": producer.CONFIG_SCHEMA,
        "created_utc": "2026-08-14T12:00:00Z",
        "source_commit": "a" * 40,
        "seed": 20260814,
        "continuation_horizon": 1,
        "execution_timeout_seconds": 600,
        "policy_contract_sha256": "b" * 64,
        "operator_contract_sha256": "c" * 64,
        "evaluator_contract_sha256": "d" * 64,
        "calibration_parents_per_task": {"task-a": 1, "task-b": 1},
        "workspace_policy": "fresh_per_rollout",
        "retry_count": 0,
        "adaptive_allocation_allowed": False,
    }


def parent_row(task: str, index: int) -> dict:
    marker = f"{task}-{index}"
    return {
        "schema_version": producer.PARENT_SCHEMA,
        "task": task,
        "physical_run_id": f"run-{marker}",
        "parent_id": f"parent-{marker}",
        "generation_started_at_utc": f"2026-08-14T12:0{index}:00.123456Z",
        "source_sha256": hashlib.sha256(f"source-{marker}".encode()).hexdigest(),
        "operator_contract_sha256": "c" * 64,
        "evaluator_contract_sha256": "d" * 64,
        "sibling_ids": [f"sibling-{marker}-z", f"sibling-{marker}-a"],
        "sibling_code_sha256": [
            hashlib.sha256(f"code-{marker}-z".encode()).hexdigest(),
            hashlib.sha256(f"code-{marker}-a".encode()).hexdigest(),
        ],
        "source_sibling_receipt_sha256": [
            hashlib.sha256(f"receipt-{marker}-z".encode()).hexdigest(),
            hashlib.sha256(f"receipt-{marker}-a".encode()).hexdigest(),
        ],
        "upstream_selection_probability_attested": 0.25 + 0.25 * index,
        "upstream_selection_receipt_sha256": hashlib.sha256(
            f"selection-{marker}".encode()
        ).hexdigest(),
        "displaced_candidate_execution_slots": 2,
    }


def fixture_files(tmp_path: Path) -> tuple[Path, Path, list[dict], dict]:
    rows = [parent_row(task, index) for task in ("task-a", "task-b") for index in range(3)]
    config = base_config()
    for task in ("task-a", "task-b"):
        task_rows = [row for row in rows if row["task"] == task]
        selected = sorted(
            task_rows,
            key=lambda row: producer.hash_order(
                config["seed"],
                "calibration",
                task,
                row["physical_run_id"],
                row["parent_id"],
            ),
        )[: config["calibration_parents_per_task"][task]]
        selected_keys = {(row["physical_run_id"], row["parent_id"]) for row in selected}
        for row in task_rows:
            if (row["physical_run_id"], row["parent_id"]) in selected_keys:
                row["displaced_candidate_execution_slots"] = 4
    parents = tmp_path / "parents.jsonl"
    parents.write_text(
        "".join(json.dumps(row, sort_keys=True) + "\n" for row in rows), encoding="utf-8"
    )
    config_path = tmp_path / "config.json"
    write_json(config_path, config)
    return parents, config_path, rows, config


def build(tmp_path: Path, parents: Path, config: Path) -> Path:
    output = tmp_path / "result"
    args = argparse.Namespace(parents=str(parents), config=str(config), output=str(output))
    assert producer.build(args) == 0
    return output


def test_partial_calibration_is_exact_budgeted_and_independently_verified(tmp_path: Path) -> None:
    parents, config, _, _ = fixture_files(tmp_path)
    output = build(tmp_path, parents, config)
    summary = json.loads((output / "summary.json").read_text(encoding="utf-8"))
    assert summary["parent_count"] == 6
    assert summary["task_count"] == 2
    assert summary["calibration_parent_count"] == 2
    assert summary["rollout_jobs"] == 16
    assert summary["planned_candidate_execution_slots"] == 16
    assert summary["displaced_candidate_execution_slots"] == 16
    assert summary["declared_slot_ledger_matches_plan"] is True
    assert summary["actual_production_budget_decrement_verified"] is False
    assert summary["upstream_selection_probability_verified_by_assignment"] is False
    assert summary["contains_outcomes"] is False
    assert summary["outcomes_read"] is False

    rows = [json.loads(line) for line in (output / "assignment_manifest.jsonl").read_text().splitlines()]
    assert Counter(row["replicate"] for row in rows) == {0: 12, 1: 4}
    assert len({row["block_id"] for row in rows}) == 8
    for block_id in {row["block_id"] for row in rows}:
        block = [row for row in rows if row["block_id"] == block_id]
        assert len(block) == 2
        assert {row["position_within_block"] for row in block} == {0, 1}
        assert {row["order_probability"] for row in block} == {0.5}
    assert {row["conditional_calibration_probability"] for row in rows} == {1 / 3}

    receipt = tmp_path / "verification.json"
    assert verifier.verify(argparse.Namespace(result=str(output), receipt=str(receipt))) == 0
    verification = json.loads(receipt.read_text(encoding="utf-8"))
    assert verification["status"] == "VERIFIED_OUTCOME_BLIND_RANDOMIZED_SIBLING_ASSIGNMENT"
    assert verification["producer_imported"] is False
    assert verification["independent_reconstruction_exact"] is True


def test_outcome_bearing_key_is_rejected_before_assignment(tmp_path: Path) -> None:
    parents, config, rows, _ = fixture_files(tmp_path)
    rows[0]["score"] = 0.9
    parents.write_text("".join(json.dumps(row) + "\n" for row in rows), encoding="utf-8")
    with pytest.raises(producer.AssignmentError, match="forbidden outcome-bearing key"):
        producer.build(
            argparse.Namespace(parents=str(parents), config=str(config), output=str(tmp_path / "bad"))
        )


def test_credential_shape_is_rejected_before_json_parse(tmp_path: Path) -> None:
    parents, config, _, _ = fixture_files(tmp_path)
    parents.write_bytes(b"not-json " + b"sk-" + b"A" * 20 + b"\n")
    with pytest.raises(producer.AssignmentError, match="credential-shaped bytes refused before parsing"):
        producer.build(
            argparse.Namespace(parents=str(parents), config=str(config), output=str(tmp_path / "bad"))
        )


def test_displaced_slot_mismatch_fails_closed(tmp_path: Path) -> None:
    parents, config, rows, _ = fixture_files(tmp_path)
    rows[0]["displaced_candidate_execution_slots"] += 1
    parents.write_text("".join(json.dumps(row) + "\n" for row in rows), encoding="utf-8")
    with pytest.raises(producer.AssignmentError, match="displaced-slot ledger mismatch"):
        producer.build(
            argparse.Namespace(parents=str(parents), config=str(config), output=str(tmp_path / "bad"))
        )


def test_calibration_quota_cannot_exceed_task_support(tmp_path: Path) -> None:
    parents, config_path, _, config = fixture_files(tmp_path)
    config["calibration_parents_per_task"]["task-a"] = 4
    write_json(config_path, config)
    with pytest.raises(producer.AssignmentError, match="calibration quota exceeds support"):
        producer.build(
            argparse.Namespace(
                parents=str(parents), config=str(config_path), output=str(tmp_path / "bad")
            )
        )


def test_independent_verifier_rejects_rehashed_assignment_tampering(tmp_path: Path) -> None:
    parents, config, _, _ = fixture_files(tmp_path)
    output = build(tmp_path, parents, config)
    assignment_path = output / "assignment_manifest.jsonl"
    rows = [json.loads(line) for line in assignment_path.read_text(encoding="utf-8").splitlines()]
    rows[0]["order_probability"] = 0.75
    assignment_path.write_text(
        "".join(producer.canonical_json(row) + "\n" for row in rows), encoding="utf-8"
    )
    hashes_path = output / "sha256_manifest.json"
    hashes = json.loads(hashes_path.read_text(encoding="utf-8"))
    hashes["assignment_manifest.jsonl"] = hashlib.sha256(assignment_path.read_bytes()).hexdigest()
    write_json(hashes_path, hashes)
    with pytest.raises(verifier.VerificationError, match="independent reconstruction"):
        verifier.verify(
            argparse.Namespace(result=str(output), receipt=str(tmp_path / "verification.json"))
        )


def test_verifier_does_not_import_assignment_producer(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    parents, config, _, _ = fixture_files(tmp_path)
    output = build(tmp_path, parents, config)
    original_import = builtins.__import__

    def guarded_import(name: str, *args, **kwargs):
        if name.endswith("randomized_sibling_logging_manifest") and not name.endswith(
            "verify_randomized_sibling_logging_manifest"
        ):
            raise AssertionError("independent verifier imported producer")
        return original_import(name, *args, **kwargs)

    monkeypatch.setattr(builtins, "__import__", guarded_import)
    receipt = tmp_path / "verification.json"
    assert verifier.verify(argparse.Namespace(result=str(output), receipt=str(receipt))) == 0
