from __future__ import annotations

import argparse
import json
import pathlib
from types import SimpleNamespace

import pytest

from phase1 import balanced_continuation_qwen_execution_smoke as smoke
from phase1 import verify_balanced_continuation_qwen_execution_smoke as verifier


def write_json(path: pathlib.Path, value: object, mode: int | None = None) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(value, sort_keys=True, separators=(",", ":")) + "\n",
        encoding="utf-8",
    )
    if mode is not None:
        path.chmod(mode)


def complete_code() -> str:
    lines = [
        "import pandas as pd",
        "import numpy as np",
        "train = pd.read_csv('./data/train.csv')",
        "sample = pd.read_csv('./data/sample_submission.csv')",
        "submission = sample.copy()",
        "target = submission.columns[1]",
        "values = np.full(len(submission), 0.5)",
        "submission[target] = values",
        "submission.to_csv('submission.csv', index=False)",
        "metric = 0.5",
    ]
    lines.extend(f"# deterministic filler line {index:02d} for complete replacement script" for index in range(20))
    lines.append("print(f'FINAL_VALIDATION_SCORE: {metric}')")
    return "\n".join(lines) + "\n"


def build_fixture(tmp_path: pathlib.Path) -> dict[str, pathlib.Path]:
    source_root = tmp_path / "source"
    source_run = tmp_path / "source-run"
    probe = tmp_path / "probe"
    public = tmp_path / "public"
    output = tmp_path / "output"
    workspace = tmp_path / "workspace"
    hf_cache = tmp_path / "hf"
    nvfix = tmp_path / "nvfix"
    job_rc = tmp_path / "job-rc"
    for path in (
        source_root, source_run, probe, public, output, workspace, hf_cache, nvfix, job_rc
    ):
        path.mkdir(parents=True)
    container = tmp_path / "container.sif"
    container.write_bytes(b"container")
    previous = complete_code()
    response = f"```python\n{complete_code().rstrip()}\n```"
    records = []
    for index, task in enumerate(smoke.EXPECTED_TASKS):
        rollout_id = str(index + 1) * 64
        archived = {
            "rollout_id": rollout_id,
            "transition_index": 1,
            "operator": "debug",
            "previous_is_buggy": True,
            "task_description": "Synthetic task",
            "previous_code": previous,
            "previous_code_sha256": smoke.sha256_bytes(previous.encode()),
            "previous_terminal_output": "clean",
            "execution_timeout_seconds": 600,
        }
        prompt_request = {**archived, "operator": "improve", "previous_is_buggy": False}
        prompt_sha = smoke.sha256_bytes(smoke.render_prompt(prompt_request).encode())
        raw_sha = smoke.sha256_bytes(response.encode())
        record = {
            "call_index": index,
            "task": task,
            "rollout_id": rollout_id,
            "gate_pass": True,
            "archived_request_sha256": smoke.sha256_bytes(smoke.canonical_json(archived)),
            "previous_code_sha256": archived["previous_code_sha256"],
            "prompt_sha256": prompt_sha,
            "raw_response_sha256": raw_sha,
            "extracted_code_chars": len(complete_code()),
            "extracted_code_lines": len(complete_code().splitlines()),
        }
        records.append(record)
        source = source_run / "worker_outputs" / rollout_id
        write_json(
            source / "steps" / "step_000" / "execution.json",
            {"execution_status": "ok", "artifact_sha256": "a" * 64},
        )
        write_json(source / "steps" / "step_001" / "operator_request.json", archived)
        write_json(
            source / "real_contract.json",
            {
                "source_commit": smoke.EXPECTED_SOURCE_COMMIT,
                "execution_timeout_seconds": 600,
                "public_data_root": str(public),
            },
        )
        task_root = public / task
        task_root.mkdir()
        (task_root / "sample_submission.csv").write_text(
            "id,prediction\na,0\nb,0\n", encoding="utf-8"
        )
        write_json(
            probe / f"call_{index:02d}.raw.json",
            {
                "schema_version": smoke.PROBE_SCHEMA,
                "call_index": index,
                "task": task,
                "rollout_id": rollout_id,
                "prompt_sha256": prompt_sha,
                "raw_response_sha256": raw_sha,
                "raw_response": response,
            },
            mode=0o600,
        )
    write_json(
        probe / "summary.json",
        {
            "schema_version": smoke.PROBE_SCHEMA,
            "status": "PASS_OPERATOR_ONLY_GATE",
            "model_id": smoke.EXPECTED_MODEL_ID,
            "source_run_root": str(source_run.resolve()),
            "api_calls": 2,
            "candidate_executions": 0,
            "gpu_jobs_started": 0,
            "sdk_retries": 0,
            "semantic_retries": 0,
            "raw_responses_mode_0600": True,
            "records": records,
        },
        mode=0o600,
    )
    return {
        "source_root": source_root,
        "source_run": source_run,
        "probe": probe,
        "public": public,
        "output": output,
        "workspace": workspace,
        "hf_cache": hf_cache,
        "nvfix": nvfix,
        "container": container,
        "job_rc": job_rc,
    }


@pytest.mark.parametrize("bad_index", [None, 0])
def test_two_index_smoke_and_independent_verifier(
    tmp_path: pathlib.Path, monkeypatch, bad_index: int | None
) -> None:
    paths = build_fixture(tmp_path)
    probe_sha = smoke.file_sha256(paths["probe"] / "summary.json")
    monkeypatch.setattr(smoke, "EXPECTED_PROBE_SUMMARY_SHA256", probe_sha)
    monkeypatch.setattr(verifier, "PROBE_SHA256", probe_sha)
    monkeypatch.setattr(smoke, "EXPECTED_CONTAINER_SHA256", smoke.file_sha256(paths["container"]))
    monkeypatch.setattr(smoke, "validate_worker_contract", lambda value: value)
    monkeypatch.setattr(
        smoke.subprocess,
        "run",
        lambda *args, **kwargs: SimpleNamespace(stdout="f" * 40 + "\n"),
    )

    def fake_execute_candidate(**kwargs):
        step = kwargs["step_dir"]
        code = kwargs["code"]
        task = kwargs["assignment"]["task"]
        code_sha = smoke.sha256_bytes(code.encode())
        (step / "code.py").write_bytes(code.encode("utf-8"))
        submission = step / "submission.csv"
        if bad_index is not None and task == smoke.EXPECTED_TASKS[bad_index]:
            submission.write_text("id,prediction\na,False\nb,True\n", encoding="utf-8")
        else:
            submission.write_text("id,prediction\na,0.4\nb,0.6\n", encoding="utf-8")
        execution = {
            "rollout_id": kwargs["assignment"]["rollout_id"],
            "task": task,
            "execution_ordinal": 1,
            "code_sha256": code_sha,
            "execution_status": "ok",
            "process_started": True,
            "candidate_execution_attempted": True,
            "exit_code": 0,
            "timed_out": False,
            "retry_count": 0,
            "public_data_read_only": True,
            "private_paths_mounted": False,
            "wall_time_seconds": 1.25,
            "artifact_sha256": smoke.file_sha256(submission),
        }
        write_json(step / "execution.json", execution)
        command = [
            "singularity", "exec", "--containall", "--cleanenv",
            "--network", "none", "container", "python", "solution.py",
        ]
        write_json(
            step / "candidate_intent.json",
            {
                "schema_version": "balanced-continuation-real-process-intent-v1",
                "rollout_id": kwargs["assignment"]["rollout_id"],
                "execution_ordinal": 1,
                "process_kind": "candidate",
                "process_will_start": True,
                "command": command,
                "command_sha256": smoke.sha256_bytes(smoke.canonical_json(command)),
                "created_utc": "2026-08-14T00:00:00Z",
                "retry_count": 0,
            },
        )
        (step / "candidate.stdout").write_bytes(b"")
        (step / "candidate.stderr").write_bytes(b"")
        write_json(
            step / "candidate_process.json",
            {
                "return_code": 0,
                "timed_out": False,
                "wall_time_seconds": 1.25,
                "stdout_sha256": smoke.sha256_bytes(b""),
                "stderr_sha256": smoke.sha256_bytes(b""),
            },
        )
        return execution

    monkeypatch.setattr(smoke, "execute_candidate", fake_execute_candidate)
    for index in range(2):
        result = smoke.run(
            argparse.Namespace(
                source_root=str(paths["source_root"]),
                source_commit="f" * 40,
                source_run_root=str(paths["source_run"]),
                probe_root=str(paths["probe"]),
                container=str(paths["container"]),
                hf_cache=str(paths["hf_cache"]),
                nvfix_dir=str(paths["nvfix"]),
                output_root=str(paths["output"]),
                workspace_root=str(paths["workspace"]),
                index=index,
            )
        )
        expected_status = (
            "FAIL_EXECUTION_ONLY" if index == bad_index else "PASS_EXECUTION_ONLY"
        )
        assert result["status"] == expected_status
        assert result["external_score_or_gain_reported"] is False
        write_json(
            paths["job_rc"] / f"{index}.json",
            {
                "index": index,
                "slurm_job_id": f"123_{index}",
                "producer_rc": 0,
                "safety_rc": 0,
            },
        )

    receipt = tmp_path / "verify.json"
    result = verifier.verify(
        argparse.Namespace(
            source_root=str(paths["source_root"]),
            source_run_root=str(paths["source_run"]),
            probe_root=str(paths["probe"]),
            output_root=str(paths["output"]),
            workspace_root=str(paths["workspace"]),
            job_rc_root=str(paths["job_rc"]),
            receipt=str(receipt),
        )
    )
    assert result["status"] == (
        "VERIFIED_QWEN_EXECUTION_SMOKE_FAIL"
        if bad_index is not None
        else "VERIFIED_QWEN_EXECUTION_SMOKE_PASS"
    )
    assert result["candidate_executions"] == 2
    assert result["api_calls"] == 0


def test_submission_shape_rejects_reordered_ids(tmp_path: pathlib.Path) -> None:
    sample = tmp_path / "sample.csv"
    candidate = tmp_path / "candidate.csv"
    sample.write_text("id,pred\na,0\nb,0\n", encoding="utf-8")
    candidate.write_text("id,pred\nb,0.4\na,0.6\n", encoding="utf-8")
    result = smoke.validate_submission_shape(sample, candidate)
    assert result["valid"] is False
    assert result["reason"] == "id_or_width_mismatch"
