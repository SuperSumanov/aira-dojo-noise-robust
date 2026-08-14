import argparse
import hashlib
import json
from pathlib import Path

import pytest

from phase1.balanced_continuation_manifest import build as build_assignment
from phase1.balanced_continuation_worker import (
    InjectedCrash,
    WorkerError,
    run_worker,
)
from phase1.run_balanced_continuation_worker_e0 import fixture_rows, synthetic_outcomes
from phase1.verify_balanced_continuation_collection import (
    CollectionVerifyError,
    verify as verify_collection,
)
from phase1.verify_balanced_continuation_manifest import verify as verify_assignment
from phase1.verify_balanced_continuation_worker import VerifyError, verify


H64 = "a" * 64
H40 = "1" * 40


def sha(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def write_json(path: Path, value: dict) -> None:
    path.write_text(json.dumps(value, sort_keys=True) + "\n", encoding="utf-8")


def prepare(tmp_path: Path, horizon: int = 2) -> dict:
    source = tmp_path / "source"
    source.mkdir()
    codes = {
        "sibling-a": "print('candidate-a')\n",
        "sibling-b": "print('candidate-b')\n",
    }
    anchors = []
    for sibling_id, code in codes.items():
        anchors.append(
            {
                "anchor_id": "anchor-0",
                "task": "synthetic-task",
                "source_run_id": "synthetic-run-0",
                "parent_id": "parent-0",
                "sibling_id": sibling_id,
                "code_sha256": sha(code.encode()),
                "anchor_contract_sha256": H64,
            }
        )
    anchors_path = source / "anchors.jsonl"
    anchors_path.write_text(
        "".join(json.dumps(row, sort_keys=True) + "\n" for row in anchors), encoding="utf-8"
    )
    contract = {
        "schema_version": "balanced-continuation-contract-v1",
        "model_id": "synthetic-model",
        "provider": "synthetic-provider",
        "operator_config_sha256": "b" * 64,
        "prompt_sha256": "c" * 64,
        "source_commit": H40,
        "dataset_contract_sha256": "d" * 64,
        "evaluator_contract_sha256": "e" * 64,
        "hardware_class": "synthetic-no-gpu",
        "execution_timeout_seconds": 120,
        "continuation_horizon": horizon,
        "debug_policy": "fixed_one_operator_per_step",
        "workspace_policy": "fresh_per_rollout",
        "temperature": 0.7,
    }
    contract_path = source / "contract.json"
    write_json(contract_path, contract)
    assignment_result = tmp_path / "assignment"
    rc = build_assignment(
        argparse.Namespace(
            anchors=str(anchors_path),
            contract=str(contract_path),
            output=str(assignment_result),
            siblings_per_anchor=2,
            replicates=2,
            horizon=horizon,
            seed=20260814,
            created_utc="2026-08-14T00:00:00Z",
        )
    )
    assert rc == 0
    code_vault = source / "code_vault.jsonl"
    code_vault.write_text(
        "".join(
            json.dumps(
                {"sibling_id": sibling_id, "code": code, "code_sha256": sha(code.encode())},
                sort_keys=True,
            )
            + "\n"
            for sibling_id, code in codes.items()
        ),
        encoding="utf-8",
    )
    assignments = [
        json.loads(line)
        for line in (assignment_result / "assignment_manifest.jsonl").read_text().splitlines()
    ]
    rollout_outcomes = {}
    for row in assignments:
        if row["global_order"] % 2 == 0:
            outcomes = [
                {"status": "ok", "utility": 0.2, "is_buggy": False, "wall_time_ms": 10},
                {"status": "timeout", "utility": None, "is_buggy": True, "wall_time_ms": 120000},
                {"status": "ok", "utility": 0.6, "is_buggy": False, "wall_time_ms": 12},
            ]
        else:
            outcomes = [
                {"status": "invalid", "utility": None, "is_buggy": True, "wall_time_ms": 4},
                {"status": "ok", "utility": 0.4, "is_buggy": False, "wall_time_ms": 9},
                {"status": "invalid", "utility": None, "is_buggy": True, "wall_time_ms": 6},
            ]
        rollout_outcomes[row["rollout_id"]] = outcomes[: horizon + 1]
    backend_spec = source / "backend_spec.json"
    write_json(
        backend_spec,
        {
            "schema_version": "balanced-continuation-synthetic-backend-v1",
            "backend": "deterministic-synthetic-v1",
            "failure_utility": 0.0,
            "utility_min": 0.0,
            "utility_max": 1.0,
            "practical_delta": 0.1,
            "rollouts": rollout_outcomes,
        },
    )
    output_root = tmp_path / "outputs"
    workspace_root = tmp_path / "workspaces"
    output_root.mkdir()
    workspace_root.mkdir()
    return {
        "assignment_result": assignment_result,
        "code_vault": code_vault,
        "backend_spec": backend_spec,
        "assignments": assignments,
        "output_root": output_root,
        "workspace_root": workspace_root,
    }


def worker_args(fixture: dict, index: int, resume: bool = False) -> argparse.Namespace:
    return argparse.Namespace(
        assignment_result=str(fixture["assignment_result"]),
        code_vault=str(fixture["code_vault"]),
        backend_spec=str(fixture["backend_spec"]),
        index=index,
        output_root=str(fixture["output_root"].resolve()),
        workspace_root=str(fixture["workspace_root"].resolve()),
        resume=resume,
    )


def verify_args(fixture: dict, artifact: Path, receipt: Path) -> argparse.Namespace:
    return argparse.Namespace(
        artifact=str(artifact),
        assignment_result=str(fixture["assignment_result"]),
        code_vault=str(fixture["code_vault"]),
        backend_spec=str(fixture["backend_spec"]),
        receipt=str(receipt),
    )


def complete_collection(fixture: dict, tmp_path: Path) -> tuple[Path, Path]:
    assignment_receipt = tmp_path / "assignment.verify.json"
    assert (
        verify_assignment(
            argparse.Namespace(
                result=str(fixture["assignment_result"]),
                receipt=str(assignment_receipt),
            )
        )
        == 0
    )
    receipt_root = tmp_path / "worker-receipts"
    receipt_root.mkdir()
    for index, assignment in enumerate(fixture["assignments"]):
        result = run_worker(worker_args(fixture, index))
        assert result["rollout_id"] == assignment["rollout_id"]
        artifact = fixture["output_root"] / assignment["rollout_id"]
        verify(
            verify_args(
                fixture,
                artifact,
                receipt_root / f"{assignment['rollout_id']}.verify.json",
            )
        )
    return assignment_receipt, receipt_root


def collection_args(
    fixture: dict,
    assignment_receipt: Path,
    receipt_root: Path,
    output: Path,
) -> argparse.Namespace:
    return argparse.Namespace(
        assignment_result=str(fixture["assignment_result"]),
        assignment_receipt=str(assignment_receipt),
        worker_output_root=str(fixture["output_root"]),
        receipt_root=str(receipt_root),
        workspace_root=str(fixture["workspace_root"]),
        output=str(output),
    )


def test_worker_and_independent_verifier_cover_improve_debug_and_timeout(tmp_path: Path) -> None:
    fixture = prepare(tmp_path)
    result = run_worker(worker_args(fixture, 0))
    rollout_id = fixture["assignments"][0]["rollout_id"]
    artifact = fixture["output_root"] / rollout_id
    assert result["candidate_execution_attempts"] == 3
    assert result["operator_calls"] == 2
    assert result["retry_count"] == result["replacement_count"] == 0
    steps = [json.loads((artifact / f"step_{i:03d}.json").read_text()) for i in range(3)]
    assert [step["operator"] for step in steps] == ["none", "improve", "debug"]
    assert [step["execution_status"] for step in steps] == ["ok", "timeout", "ok"]
    receipt = verify(verify_args(fixture, artifact, tmp_path / "verify.json"))
    assert receipt["status"] == "VERIFIED_SYNTHETIC_BALANCED_CONTINUATION_ROLLOUT"
    assert receipt["fresh_workspace_verified"] is True
    workspace = fixture["workspace_root"] / rollout_id
    assert {path.name for path in workspace.iterdir()} == {
        "workspace_marker.json",
        "execution_000.json",
        "execution_001.json",
        "execution_002.json",
    }
    with pytest.raises(WorkerError, match="already finalized"):
        run_worker(worker_args(fixture, 0))


def test_full_e0_fixture_is_frozen_balanced_and_covers_failure_paths() -> None:
    anchors, vault = fixture_rows()
    assert len(anchors) == len(vault) == 12
    assert len({row["anchor_id"] for row in anchors}) == 4
    assert len({row["task"] for row in anchors}) == 2
    assert len({row["sibling_id"] for row in anchors}) == 12
    assert len({row["code_sha256"] for row in anchors}) == 12
    statuses = {
        outcome["status"]
        for global_order in range(4)
        for outcome in synthetic_outcomes(global_order)
    }
    assert statuses == {"ok", "timeout", "invalid"}


def test_resume_promotes_durable_receipt_without_reexecution(tmp_path: Path) -> None:
    fixture = prepare(tmp_path)
    rollout_id = fixture["assignments"][1]["rollout_id"]
    with pytest.raises(InjectedCrash, match="durable receipt 1"):
        run_worker(worker_args(fixture, 1), crash_after_receipt=1)
    execution = fixture["workspace_root"] / rollout_id / "execution_001.json"
    before = execution.read_bytes()
    state = json.loads(
        (fixture["output_root"] / f".inflight-{rollout_id}" / "state.json").read_text()
    )
    assert state["phase"] == "PENDING"
    result = run_worker(worker_args(fixture, 1, resume=True))
    assert execution.read_bytes() == before
    assert result["candidate_execution_attempts"] == 3
    artifact = fixture["output_root"] / rollout_id
    verify(verify_args(fixture, artifact, tmp_path / "resume_verify.json"))


def test_resume_refuses_ambiguous_pending_without_durable_receipt(tmp_path: Path) -> None:
    fixture = prepare(tmp_path)
    rollout_id = fixture["assignments"][0]["rollout_id"]
    with pytest.raises(InjectedCrash):
        run_worker(worker_args(fixture, 0), crash_after_receipt=1)
    inflight = fixture["output_root"] / f".inflight-{rollout_id}"
    (inflight / "step_001.json").unlink()
    (inflight / "code_001.py").unlink()
    with pytest.raises(WorkerError, match="AMBIGUOUS_PENDING_NO_DURABLE_RECEIPT"):
        run_worker(worker_args(fixture, 0, resume=True))
    assert (fixture["workspace_root"] / rollout_id / "execution_001.json").is_file()


def test_resume_revalidates_durable_receipt_before_further_execution(tmp_path: Path) -> None:
    fixture = prepare(tmp_path)
    rollout_id = fixture["assignments"][1]["rollout_id"]
    with pytest.raises(InjectedCrash):
        run_worker(worker_args(fixture, 1), crash_after_receipt=1)
    inflight = fixture["output_root"] / f".inflight-{rollout_id}"
    pending_receipt = inflight / "step_001.json"
    tampered = json.loads(pending_receipt.read_text(encoding="utf-8"))
    tampered["effective_utility"] = 0.9
    write_json(pending_receipt, tampered)
    with pytest.raises(WorkerError, match="durable step receipt differs at ordinal 1"):
        run_worker(worker_args(fixture, 1, resume=True))
    assert not (fixture["workspace_root"] / rollout_id / "execution_002.json").exists()


def test_fresh_workspace_collision_fails_before_candidate_execution(tmp_path: Path) -> None:
    fixture = prepare(tmp_path)
    rollout_id = fixture["assignments"][0]["rollout_id"]
    collision = fixture["workspace_root"] / rollout_id
    collision.mkdir()
    (collision / "foreign-cache.bin").write_bytes(b"carry-over")
    with pytest.raises(WorkerError, match="fresh workspace path already exists"):
        run_worker(worker_args(fixture, 0))
    assert not list(collision.glob("execution_*.json"))


def test_independent_verifier_rejects_semantic_tamper_even_after_rehash(
    tmp_path: Path,
) -> None:
    fixture = prepare(tmp_path)
    run_worker(worker_args(fixture, 0))
    rollout_id = fixture["assignments"][0]["rollout_id"]
    artifact = fixture["output_root"] / rollout_id
    code_path = artifact / "code_001.py"
    code_path.write_bytes(code_path.read_bytes() + b"# attacker edit\n")
    manifest_path = artifact / "sha256_manifest.json"
    manifest = json.loads(manifest_path.read_text())
    manifest["code_001.py"] = sha(code_path.read_bytes())
    write_json(manifest_path, manifest)
    with pytest.raises(VerifyError, match="generated code differs"):
        verify(verify_args(fixture, artifact, tmp_path / "tamper_verify.json"))


def test_code_vault_credential_is_rejected_before_json_parse(tmp_path: Path) -> None:
    fixture = prepare(tmp_path)
    fixture["code_vault"].write_bytes(b"not json sk-" + b"A" * 24)
    with pytest.raises(WorkerError, match="credential-shaped bytes refused before parsing"):
        run_worker(worker_args(fixture, 0))


def test_backend_outcome_count_must_equal_one_plus_horizon(tmp_path: Path) -> None:
    fixture = prepare(tmp_path)
    spec = json.loads(fixture["backend_spec"].read_text())
    rollout_id = fixture["assignments"][0]["rollout_id"]
    spec["rollouts"][rollout_id] = spec["rollouts"][rollout_id][:-1]
    write_json(fixture["backend_spec"], spec)
    with pytest.raises(WorkerError, match="outcome count differs"):
        run_worker(worker_args(fixture, 0))


def test_output_and_workspace_roots_must_be_disjoint(tmp_path: Path) -> None:
    fixture = prepare(tmp_path)
    args = worker_args(fixture, 0)
    nested = fixture["output_root"] / "workspace"
    nested.mkdir()
    args.workspace_root = str(nested.resolve())
    with pytest.raises(WorkerError, match="must be disjoint"):
        run_worker(args)


def test_collection_verifier_closes_exact_k_and_workspace_accounting(tmp_path: Path) -> None:
    fixture = prepare(tmp_path)
    assignment_receipt, receipt_root = complete_collection(fixture, tmp_path)
    collection = verify_collection(
        collection_args(
            fixture,
            assignment_receipt,
            receipt_root,
            tmp_path / "collection.verify.json",
        )
    )
    assert collection["status"] == "VERIFIED_COMPLETE_SYNTHETIC_BALANCED_CONTINUATION_COLLECTION"
    assert collection["rollout_jobs"] == 4
    assert collection["candidate_execution_attempts"] == 12
    assert collection["operator_calls"] == 8
    assert collection["unique_workspace_paths"] == 4
    assert collection["unique_workspace_tokens"] == 4
    assert collection["task_rollout_counts"] == {"synthetic-task": 4}


def test_collection_verifier_rejects_missing_receipt(tmp_path: Path) -> None:
    fixture = prepare(tmp_path)
    assignment_receipt, receipt_root = complete_collection(fixture, tmp_path)
    first_id = fixture["assignments"][0]["rollout_id"]
    (receipt_root / f"{first_id}.verify.json").unlink()
    with pytest.raises(CollectionVerifyError, match="receipt coverage"):
        verify_collection(
            collection_args(
                fixture,
                assignment_receipt,
                receipt_root,
                tmp_path / "collection.verify.json",
            )
        )


def test_collection_verifier_rejects_leftover_inflight(tmp_path: Path) -> None:
    fixture = prepare(tmp_path)
    assignment_receipt, receipt_root = complete_collection(fixture, tmp_path)
    (fixture["output_root"] / ".inflight-stray").mkdir()
    with pytest.raises(CollectionVerifyError, match="inflight rollout artifacts remain"):
        verify_collection(
            collection_args(
                fixture,
                assignment_receipt,
                receipt_root,
                tmp_path / "collection.verify.json",
            )
        )


def test_collection_verifier_rejects_reused_workspace_token_after_rehash(
    tmp_path: Path,
) -> None:
    fixture = prepare(tmp_path)
    assignment_receipt, receipt_root = complete_collection(fixture, tmp_path)
    first_id = fixture["assignments"][0]["rollout_id"]
    second_id = fixture["assignments"][1]["rollout_id"]
    first_result = json.loads(
        (fixture["output_root"] / first_id / "result.json").read_text(encoding="utf-8")
    )
    second_artifact = fixture["output_root"] / second_id
    second_result_path = second_artifact / "result.json"
    second_result = json.loads(second_result_path.read_text(encoding="utf-8"))
    second_result["workspace_token"] = first_result["workspace_token"]
    write_json(second_result_path, second_result)
    worker_manifest_path = second_artifact / "sha256_manifest.json"
    worker_manifest = json.loads(worker_manifest_path.read_text(encoding="utf-8"))
    worker_manifest["result.json"] = sha(second_result_path.read_bytes())
    write_json(worker_manifest_path, worker_manifest)
    second_receipt_path = receipt_root / f"{second_id}.verify.json"
    second_receipt = json.loads(second_receipt_path.read_text(encoding="utf-8"))
    second_receipt["workspace_token"] = first_result["workspace_token"]
    second_receipt["worker_sha256_manifest"] = sha(worker_manifest_path.read_bytes())
    write_json(second_receipt_path, second_receipt)
    with pytest.raises(CollectionVerifyError, match="workspace token is missing or reused"):
        verify_collection(
            collection_args(
                fixture,
                assignment_receipt,
                receipt_root,
                tmp_path / "collection.verify.json",
            )
        )
