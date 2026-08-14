from __future__ import annotations

import hashlib
import json
import os
import sys
from pathlib import Path

import pytest

import phase1.balanced_continuation_real_worker as worker


def write_json(path: Path, value: object) -> None:
    path.write_text(json.dumps(value, sort_keys=True) + "\n", encoding="utf-8")


def test_atomic_state_replacement_and_new_output_guard(tmp_path: Path) -> None:
    state = tmp_path / "state.json"
    worker.atomic_json_new(state, {"phase": "READY", "value": 1})
    with pytest.raises(worker.RealWorkerError, match="refusing existing"):
        worker.atomic_json_new(state, {"phase": "PENDING", "value": 2})
    worker.atomic_json_replace(state, {"phase": "PENDING", "value": 2})
    assert json.loads(state.read_text(encoding="utf-8")) == {
        "phase": "PENDING",
        "value": 2,
    }


def test_candidate_command_is_networkless_and_mounts_only_public_inputs_read_only(
    tmp_path: Path,
) -> None:
    command = worker.candidate_command(
        tmp_path / "workspace",
        tmp_path / "public-task",
        tmp_path / "image.sif",
        tmp_path / "hf",
        tmp_path / "nvfix",
    )
    assert command[:8] == [
        "singularity",
        "exec",
        "--containall",
        "--cleanenv",
        "--net",
        "--network",
        "none",
        "--no-home",
    ]
    assert command[8:13] == ["--no-mount", "bind-paths", "--no-eval", "--nv", "--pwd"]
    bind_value = command[command.index("--bind") + 1]
    assert f"{tmp_path / 'public-task'}:/workspace/data:ro" in bind_value
    assert f"{tmp_path / 'hf'}:/hf:ro" in bind_value
    assert "private" not in bind_value


def test_candidate_environment_excludes_provider_credentials_and_refuses_injection(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("PRIMARY_KEY", "sk-" + "A" * 24)
    environment = worker.candidate_host_env()
    assert "PRIMARY_KEY" not in environment
    monkeypatch.setenv("SINGULARITYENV_PRIMARY_KEY", "not-even-a-secret")
    with pytest.raises(worker.RealWorkerError, match="injection variables are forbidden"):
        worker.candidate_host_env()


def test_mutable_and_private_roots_must_be_disjoint(tmp_path: Path) -> None:
    output = tmp_path / "output"
    nested = output / "workspace"
    split = tmp_path / "split"
    sealed = tmp_path / "sealed"
    for path in (output, nested, split, sealed):
        path.mkdir(exist_ok=True)
    with pytest.raises(worker.RealWorkerError, match="must be disjoint"):
        worker.require_disjoint_roots({
            "output": output.resolve(),
            "workspace": nested.resolve(),
            "split": split.resolve(),
            "sealed": sealed.resolve(),
        })


def test_candidate_logs_are_drained_with_bounded_head_tail_evidence(tmp_path: Path) -> None:
    stdout = tmp_path / "stdout.log"
    stderr = tmp_path / "stderr.log"
    raw = b"A" * 100_000
    receipt = worker.run_process_once(
        [sys.executable, "-c", "import sys;sys.stdout.buffer.write(b'A'*100000)"],
        cwd=tmp_path,
        env=os.environ.copy(),
        timeout_seconds=10,
        stdout_path=stdout,
        stderr_path=stderr,
    )
    assert receipt["return_code"] == 0
    assert receipt["stdout_capture"] == {
        "total_bytes": len(raw),
        "truncated": True,
        "full_sha256": hashlib.sha256(raw).hexdigest(),
    }
    stored = stdout.read_bytes()
    assert stored.startswith(b"A" * worker.LOG_HEAD_BYTES)
    assert stored.endswith(b"A" * worker.LOG_TAIL_BYTES)
    assert b"LOG TRUNCATED" in stored
    assert len(stored) < len(raw)


def test_completed_progress_reconstructs_counts_from_durable_manifests(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    rollout_id = "b" * 64
    token = "c" * 32
    assignment = {"rollout_id": rollout_id, "task": "task", "rollout_seed": 40}
    contract = {"continuation_horizon": 1}
    steps = tmp_path / "steps"
    steps.mkdir()

    monkeypatch.setattr(worker, "validate_execution_receipt", lambda value, _: value)
    monkeypatch.setattr(worker, "validate_search_receipt", lambda value, _: value)
    monkeypatch.setattr(worker, "validate_visible_step", lambda value, _: value)
    monkeypatch.setattr(
        worker,
        "build_operator_request",
        lambda *args, **kwargs: {"expected": kwargs["operator_seed"]},
    )
    monkeypatch.setattr(worker, "validate_operator_response", lambda value, *_: value)
    monkeypatch.setattr(worker, "validate_operator_usage", lambda *args: None)
    monkeypatch.setattr(worker, "operator_profile", lambda _: {
        "raw_response_schema": worker.deepseek_operator.RAW_RESPONSE_SCHEMA,
    })
    monkeypatch.setattr(
        worker, "bind_visible_step", lambda *args, **kwargs: {"code": kwargs["code"]}
    )

    first = steps / "step_000"
    first.mkdir()
    write_json(first / "execution.json", {"workspace_token": token})
    write_json(first / "dsearch.json", {})
    write_json(first / "dval_commitment.json", {
        "schema_version": worker.COMMITMENT_SCHEMA,
        "rollout_id": rollout_id,
        "workspace_token": token,
        "task": "task",
        "execution_ordinal": 0,
        "sealed_label_receipt_sha256": "d" * 64,
    })
    (first / "code.py").write_text("warm", encoding="utf-8")
    write_json(first / "visible.json", {"code": "warm"})
    worker.finalize_step(first, assignment, 0)

    second = steps / "step_001"
    second.mkdir()
    write_json(second / "execution.json", {"workspace_token": token})
    write_json(second / "dsearch.json", {})
    write_json(second / "dval_commitment.json", {
        "schema_version": worker.COMMITMENT_SCHEMA,
        "rollout_id": rollout_id,
        "workspace_token": token,
        "task": "task",
        "execution_ordinal": 1,
        "sealed_label_receipt_sha256": "e" * 64,
    })
    write_json(second / "operator_request.json", {"expected": 41})
    raw_response = "```python\ncontinued\n```"
    raw_sha = worker.sha256_bytes(raw_response.encode("utf-8"))
    write_json(second / "operator_response.json", {
        "operator_calls": 1,
        "operator": "improve",
        "code": "continued",
        "request_sha256": "f" * 64,
        "raw_response_sha256": raw_sha,
    })
    write_json(second / "operator_raw_response.json", {
        "schema_version": worker.deepseek_operator.RAW_RESPONSE_SCHEMA,
        "request_sha256": "f" * 64,
        "raw_response_sha256": raw_sha,
        "raw_response": raw_response,
    })
    write_json(second / "operator_usage.json", {})
    write_json(second / "visible.json", {"code": "continued"})
    worker.finalize_step(second, assignment, 1)

    manifests, calls, attempts = worker.completed_progress(
        tmp_path, assignment, contract, "description", 2
    )
    assert len(manifests) == 2
    assert calls == 1
    assert attempts == 2

    (second / "code-after-manifest.txt").write_text("tamper", encoding="utf-8")
    with pytest.raises(worker.RealWorkerError, match="durable step manifest differs"):
        worker.completed_progress(tmp_path, assignment, contract, "description", 2)


def test_operator_sidecar_receives_only_selected_provider_credential(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("PRIMARY_KEY_DEEPSEEK_V4_FLASH", "deepseek-placeholder")
    monkeypatch.setenv("PRIMARY_KEY_QWEN3_CODER_FLASH", "qwen-placeholder")
    qwen = worker.clean_sidecar_env(True, ("PRIMARY_KEY_QWEN3_CODER_FLASH",))
    deepseek = worker.clean_sidecar_env(True, ("PRIMARY_KEY_DEEPSEEK_V4_FLASH",))
    candidate = worker.clean_sidecar_env(False)
    assert qwen["PRIMARY_KEY_QWEN3_CODER_FLASH"] == "qwen-placeholder"
    assert "PRIMARY_KEY_DEEPSEEK_V4_FLASH" not in qwen
    assert deepseek["PRIMARY_KEY_DEEPSEEK_V4_FLASH"] == "deepseek-placeholder"
    assert "PRIMARY_KEY_QWEN3_CODER_FLASH" not in deepseek
    assert "PRIMARY_KEY_DEEPSEEK_V4_FLASH" not in candidate
    assert "PRIMARY_KEY_QWEN3_CODER_FLASH" not in candidate
