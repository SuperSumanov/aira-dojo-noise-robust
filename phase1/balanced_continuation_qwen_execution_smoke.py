"""Execute the two hash-bound Qwen conformance scripts without scoring them.

This is an engineering-only gate.  It performs no API call and never opens D_search,
D_val, D_test, first-960, or prospective outcomes.
"""

from __future__ import annotations

import argparse
import csv
import json
import math
import os
import pathlib
import stat
import subprocess
import sys
import uuid
from itertools import zip_longest
from typing import Any

from phase1.balanced_continuation_e1_scoring import (
    CREDENTIAL,
    TASK_SPECS,
    atomic_json,
    canonical_json,
    checked_json,
    file_sha256,
    parse_boolean,
    sha256_bytes,
)
from phase1.balanced_continuation_operator_entry import (
    assess_single_complete_code,
    render_prompt,
)
from phase1.balanced_continuation_real_contract import validate_worker_contract
from phase1.balanced_continuation_real_worker import execute_candidate


SCHEMA = "balanced-continuation-qwen-execution-smoke-v1"
PROBE_SCHEMA = "balanced-continuation-operator-conformance-probe-v1"
EXPECTED_PROBE_SUMMARY_SHA256 = (
    "a30aa463a75ead9fa48fcd53a37921749425ac4a8ee696b18c2d0be33413ed1d"
)
EXPECTED_MODEL_ID = "qwen3-coder-flash"
EXPECTED_SOURCE_COMMIT = "e59a759d99dd490b6f8a0011c66dd7c772307b28"
EXPECTED_CONTAINER_SHA256 = (
    "801f646bed3cae6e74e10d793e71b0086658d4303d54552333c58125ddf9beda"
)
EXPECTED_TASKS = ("spaceship-titanic", "tabular-playground-series-may-2022")


class SmokeError(RuntimeError):
    pass


def require_directory(path: pathlib.Path, label: str) -> pathlib.Path:
    if not path.is_dir() or path.is_symlink():
        raise SmokeError(f"{label} is missing or symlinked")
    return path


def require_file(path: pathlib.Path, label: str) -> pathlib.Path:
    if not path.is_file() or path.is_symlink():
        raise SmokeError(f"{label} is missing or symlinked")
    return path


def require_mode_0600(path: pathlib.Path) -> None:
    if os.name == "posix" and stat.S_IMODE(path.stat().st_mode) != 0o600:
        raise SmokeError(f"raw probe file is not mode 0600: {path.name}")


def read_probe(
    probe_root: pathlib.Path,
    source_run_root: pathlib.Path,
    index: int,
) -> tuple[dict[str, Any], dict[str, Any], str]:
    summary_path = require_file(probe_root / "summary.json", "probe summary")
    require_mode_0600(summary_path)
    if file_sha256(summary_path) != EXPECTED_PROBE_SUMMARY_SHA256:
        raise SmokeError("probe summary SHA-256 differs")
    summary = checked_json(summary_path)
    records = summary.get("records")
    if (
        summary.get("schema_version") != PROBE_SCHEMA
        or summary.get("status") != "PASS_OPERATOR_ONLY_GATE"
        or summary.get("model_id") != EXPECTED_MODEL_ID
        or summary.get("api_calls") != 2
        or summary.get("candidate_executions") != 0
        or summary.get("gpu_jobs_started") != 0
        or summary.get("sdk_retries") != 0
        or summary.get("semantic_retries") != 0
        or summary.get("raw_responses_mode_0600") is not True
        or pathlib.Path(str(summary.get("source_run_root"))).resolve() != source_run_root
        or not isinstance(records, list)
        or len(records) != 2
        or [record.get("call_index") for record in records] != [0, 1]
        or [record.get("task") for record in records] != list(EXPECTED_TASKS)
        or any(record.get("gate_pass") is not True for record in records)
    ):
        raise SmokeError("probe summary contract differs")
    if index not in (0, 1):
        raise SmokeError("smoke index must be 0 or 1")
    record = records[index]
    raw_path = require_file(probe_root / f"call_{index:02d}.raw.json", "raw probe")
    require_mode_0600(raw_path)
    raw = checked_json(raw_path)
    expected_raw_keys = {
        "schema_version", "call_index", "task", "rollout_id", "prompt_sha256",
        "raw_response_sha256", "raw_response",
    }
    response_text = raw.get("raw_response")
    if (
        set(raw) != expected_raw_keys
        or raw.get("schema_version") != PROBE_SCHEMA
        or raw.get("call_index") != index
        or raw.get("task") != record.get("task")
        or raw.get("rollout_id") != record.get("rollout_id")
        or raw.get("prompt_sha256") != record.get("prompt_sha256")
        or raw.get("raw_response_sha256") != record.get("raw_response_sha256")
        or not isinstance(response_text, str)
        or sha256_bytes(response_text.encode("utf-8")) != raw.get("raw_response_sha256")
        or CREDENTIAL.search(response_text.encode("utf-8"))
    ):
        raise SmokeError("raw probe binding differs")
    return summary, record, response_text


def reconstruct_code(
    source_run_root: pathlib.Path,
    record: dict[str, Any],
    response_text: str,
) -> tuple[str, dict[str, Any]]:
    rollout_id = record.get("rollout_id")
    if not isinstance(rollout_id, str) or len(rollout_id) != 64:
        raise SmokeError("probe rollout identity differs")
    source = require_directory(
        source_run_root / "worker_outputs" / rollout_id, "source rollout"
    )
    warm_execution = checked_json(
        require_file(source / "steps" / "step_000" / "execution.json", "warm execution")
    )
    if (
        warm_execution.get("execution_status") != "ok"
        or warm_execution.get("artifact_sha256") is None
    ):
        raise SmokeError("selected source warm artifact is not successful")
    archived_request = checked_json(
        require_file(
            source / "steps" / "step_001" / "operator_request.json",
            "archived operator request",
        )
    )
    previous_code = archived_request.get("previous_code")
    if (
        sha256_bytes(canonical_json(archived_request))
        != record.get("archived_request_sha256")
        or not isinstance(previous_code, str)
        or sha256_bytes(previous_code.encode("utf-8"))
        != record.get("previous_code_sha256")
    ):
        raise SmokeError("archived operator request binding differs")
    prompt_request = {
        **archived_request,
        "operator": "improve",
        "previous_is_buggy": False,
    }
    prompt = render_prompt(prompt_request)
    if sha256_bytes(prompt.encode("utf-8")) != record.get("prompt_sha256"):
        raise SmokeError("reconstructed Qwen prompt differs")
    code, conformance = assess_single_complete_code(response_text, previous_code)
    if (
        conformance != "ok"
        or not code
        or len(code) != record.get("extracted_code_chars")
        or len(code.splitlines()) != record.get("extracted_code_lines")
    ):
        raise SmokeError("Qwen code reconstruction differs")
    return code, archived_request


def validate_submission_shape(
    sample_path: pathlib.Path,
    candidate_path: pathlib.Path,
    task: str,
) -> dict[str, Any]:
    if task not in TASK_SPECS:
        raise SmokeError("unsupported task for submission-shape validation")
    metric = TASK_SPECS[task]["metric"]
    if not candidate_path.is_file() or candidate_path.is_symlink():
        return {"valid": False, "reason": "submission_missing", "rows": 0, "columns": []}
    try:
        with sample_path.open("r", encoding="utf-8-sig", newline="") as expected_handle:
            with candidate_path.open("r", encoding="utf-8-sig", newline="") as actual_handle:
                expected_reader = csv.reader(expected_handle)
                actual_reader = csv.reader(actual_handle)
                expected_header = next(expected_reader, None)
                actual_header = next(actual_reader, None)
                if (
                    not expected_header
                    or actual_header != expected_header
                    or len(expected_header) < 2
                ):
                    return {
                        "valid": False,
                        "reason": "header_mismatch",
                        "rows": 0,
                        "columns": actual_header or [],
                    }
                rows = 0
                for expected, actual in zip_longest(expected_reader, actual_reader):
                    if expected is None or actual is None:
                        return {
                            "valid": False,
                            "reason": "row_count_mismatch",
                            "rows": rows,
                            "columns": actual_header,
                        }
                    if (
                        len(actual) != len(expected_header)
                        or not expected
                        or actual[0] != expected[0]
                    ):
                        return {
                            "valid": False,
                            "reason": "id_or_width_mismatch",
                            "rows": rows,
                            "columns": actual_header,
                        }
                    for value in actual[1:]:
                        if metric == "accuracy":
                            parse_boolean(value)
                        else:
                            parsed = float(value)
                            if not math.isfinite(parsed) or not 0.0 <= parsed <= 1.0:
                                raise ValueError("invalid probability prediction")
                    rows += 1
    except (OSError, UnicodeError, csv.Error, ValueError):
        return {"valid": False, "reason": "unparseable_prediction", "rows": 0, "columns": []}
    return {
        "valid": True,
        "reason": "ok",
        "rows": rows,
        "columns": actual_header,
    }


def run(args: argparse.Namespace) -> dict[str, Any]:
    source_root = require_directory(pathlib.Path(args.source_root).resolve(), "source root")
    commit = subprocess.run(
        ["git", "-C", str(source_root), "rev-parse", "HEAD"],
        check=True,
        capture_output=True,
        text=True,
    ).stdout.strip()
    if commit != args.source_commit:
        raise SmokeError("source checkout commit differs")
    source_run_root = require_directory(
        pathlib.Path(args.source_run_root).resolve(), "source run root"
    )
    probe_root = require_directory(pathlib.Path(args.probe_root).resolve(), "probe root")
    container = require_file(pathlib.Path(args.container).resolve(), "container")
    hf_cache = require_directory(pathlib.Path(args.hf_cache).resolve(), "HF cache")
    nvfix_dir = require_directory(pathlib.Path(args.nvfix_dir).resolve(), "NVVM fix")
    output_root = require_directory(pathlib.Path(args.output_root).resolve(), "output parent")
    workspace_root = require_directory(
        pathlib.Path(args.workspace_root).resolve(), "workspace parent"
    )
    if file_sha256(container) != EXPECTED_CONTAINER_SHA256:
        raise SmokeError("container SHA-256 differs")

    index = int(args.index)
    _, record, response_text = read_probe(probe_root, source_run_root, index)
    code, _ = reconstruct_code(source_run_root, record, response_text)
    source_artifact = source_run_root / "worker_outputs" / record["rollout_id"]
    source_contract = validate_worker_contract(
        checked_json(source_artifact / "real_contract.json")
    )
    if (
        source_contract.get("source_commit") != EXPECTED_SOURCE_COMMIT
        or source_contract.get("execution_timeout_seconds") != 600
    ):
        raise SmokeError("source execution contract differs")
    task = record["task"]
    public_task = require_directory(
        pathlib.Path(source_contract["public_data_root"]) / task, "public task"
    )
    sample = require_file(public_task / "sample_submission.csv", "public sample submission")

    index_output = output_root / f"index_{index}"
    index_workspace = workspace_root / f"index_{index}"
    if any(path.exists() or path.is_symlink() for path in (index_output, index_workspace)):
        raise SmokeError("smoke index output must be fresh")
    index_output.mkdir(mode=0o700)
    index_workspace.mkdir(mode=0o700)
    candidate_workspace = index_workspace / "candidate"
    candidate_workspace.mkdir(mode=0o700)
    step_dir = index_output / "step"
    step_dir.mkdir(mode=0o700)
    smoke_rollout_id = sha256_bytes(
        canonical_json({
            "schema_version": SCHEMA,
            "source_rollout_id": record["rollout_id"],
            "raw_response_sha256": record["raw_response_sha256"],
            "index": index,
        })
    )
    workspace_token = uuid.uuid4().hex
    assignment = {"rollout_id": smoke_rollout_id, "task": task}
    execution = execute_candidate(
        code=code,
        assignment=assignment,
        real_contract=source_contract,
        ordinal=1,
        workspace=candidate_workspace,
        workspace_token=workspace_token,
        step_dir=step_dir,
        public_task=public_task,
        container=container,
        hf_cache=hf_cache,
        nvfix_dir=nvfix_dir,
    )
    shape = validate_submission_shape(sample, step_dir / "submission.csv", task)
    gate_pass = execution["execution_status"] == "ok" and shape["valid"] is True
    summary = {
        "schema_version": SCHEMA,
        "status": "PASS_EXECUTION_ONLY" if gate_pass else "FAIL_EXECUTION_ONLY",
        "source_commit": args.source_commit,
        "producer_sha256": file_sha256(pathlib.Path(__file__).resolve()),
        "index": index,
        "task": task,
        "model_id": EXPECTED_MODEL_ID,
        "source_rollout_id": record["rollout_id"],
        "smoke_rollout_id": smoke_rollout_id,
        "probe_summary_sha256": EXPECTED_PROBE_SUMMARY_SHA256,
        "prompt_sha256": record["prompt_sha256"],
        "raw_response_sha256": record["raw_response_sha256"],
        "code_sha256": sha256_bytes(code.encode("utf-8")),
        "candidate_executions": 1,
        "candidate_processes_started": int(execution["process_started"]),
        "candidate_wall_time_seconds": execution["wall_time_seconds"],
        "execution_status": execution["execution_status"],
        "artifact_sha256": execution["artifact_sha256"],
        "submission_shape": shape,
        "api_calls": 0,
        "operator_retries": 0,
        "candidate_retries": 0,
        "dsearch_rows_read": 0,
        "dval_rows_read": 0,
        "dtest_rows_read": 0,
        "first960_or_prospective_read": False,
        "external_score_or_gain_reported": False,
        "public_data_read_only": execution["public_data_read_only"],
        "private_paths_mounted": execution["private_paths_mounted"],
        "source_warm_status": "ok",
        "gate_pass": gate_pass,
    }
    atomic_json(index_output / "summary.json", summary, mode=0o600)
    return summary


def parser() -> argparse.ArgumentParser:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--source-root", required=True)
    ap.add_argument("--source-commit", required=True)
    ap.add_argument("--source-run-root", required=True)
    ap.add_argument("--probe-root", required=True)
    ap.add_argument("--container", required=True)
    ap.add_argument("--hf-cache", required=True)
    ap.add_argument("--nvfix-dir", required=True)
    ap.add_argument("--output-root", required=True)
    ap.add_argument("--workspace-root", required=True)
    ap.add_argument("--index", required=True, type=int)
    return ap


def main() -> int:
    try:
        summary = run(parser().parse_args())
    except (
        SmokeError,
        OSError,
        ValueError,
        json.JSONDecodeError,
        subprocess.SubprocessError,
    ) as exc:
        print(f"QWEN_EXECUTION_SMOKE_ERROR: {exc}", file=sys.stderr)
        return 2
    print(
        "QWEN_EXECUTION_SMOKE_DONE "
        f"index={summary['index']} status={summary['status']} "
        f"candidate_executions={summary['candidate_executions']} api_calls=0",
        flush=True,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
