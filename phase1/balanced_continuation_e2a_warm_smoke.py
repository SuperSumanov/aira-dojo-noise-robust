"""Run one frozen E2-A warm-start candidate without an API call or score access."""

from __future__ import annotations

import argparse
import json
import os
import pathlib
import subprocess
import sys
import uuid
from typing import Any

from phase1.balanced_continuation_e2a_scoring import (
    CREDENTIAL,
    ScoreError,
    TASK_SPECS,
    atomic_json,
    checked_json,
    file_sha256,
    load_predictions,
    load_public_ids,
    sha256_bytes,
)
from phase1.balanced_continuation_real_contract import validate_worker_contract
from phase1.balanced_continuation_real_worker import execute_candidate
from phase1.e2a_hf_cache import CacheError, verify_contract_cache
from phase1.balanced_continuation_worker import load_assignment, load_code_vault


SCHEMA = "balanced-continuation-e2a-warm-smoke-v1"
GIT_NO_LFS = [
    "-c", "filter.lfs.smudge=", "-c", "filter.lfs.process=",
    "-c", "filter.lfs.required=false",
]


class SmokeError(RuntimeError):
    pass


def require_directory(path: pathlib.Path, label: str) -> pathlib.Path:
    if not path.is_dir() or path.is_symlink():
        raise SmokeError(f"{label} is missing or symlinked")
    return path


def validate_public_submission(
    artifact: pathlib.Path, sample: pathlib.Path, task: str
) -> dict[str, Any]:
    public_ids = load_public_ids(sample, task)
    predictions, failure = load_predictions(
        artifact, task, evaluation_ids=public_ids, public_ids=public_ids
    )
    return {
        "valid": predictions is not None,
        "failure_reason": failure,
        "row_count": len(public_ids),
        "columns": [
            TASK_SPECS[task]["id_column"], *TASK_SPECS[task]["submission_columns"]
        ],
    }


def run(args: argparse.Namespace) -> dict[str, Any]:
    source_root = require_directory(pathlib.Path(args.source_root).resolve(), "source root")
    preparation = require_directory(pathlib.Path(args.preparation).resolve(), "preparation")
    data_gate = require_directory(pathlib.Path(args.data_gate).resolve(), "data gate")
    output_root = require_directory(pathlib.Path(args.output_root).resolve(), "output parent")
    workspace_root = require_directory(
        pathlib.Path(args.workspace_root).resolve(), "workspace parent"
    )
    container = pathlib.Path(args.container).resolve()
    hf_cache = require_directory(pathlib.Path(args.hf_cache).resolve(), "HF cache")
    nvfix = require_directory(pathlib.Path(args.nvfix_dir).resolve(), "NVVM fix")
    if not container.is_file() or container.is_symlink():
        raise SmokeError("container is missing or symlinked")

    plan = checked_json(preparation / "run_plan.json")
    real_raw = (preparation / "real_contract.json").read_bytes()
    if CREDENTIAL.search(real_raw):
        raise SmokeError("credential-shaped bytes in real contract")
    real = validate_worker_contract(json.loads(real_raw))
    commit = subprocess.run(
        ["git", *GIT_NO_LFS, "rev-parse", "HEAD"], cwd=source_root, check=True,
        stdout=subprocess.PIPE, stderr=subprocess.PIPE,
    ).stdout.decode("ascii").strip()
    dirty = subprocess.run(
        ["git", *GIT_NO_LFS, "status", "--porcelain"], cwd=source_root, check=True,
        stdout=subprocess.PIPE, stderr=subprocess.PIPE,
    ).stdout
    if commit != real["source_commit"] or dirty:
        raise SmokeError("source checkout is not the exact clean contract commit")
    if file_sha256(container) != real["container_sha256"]:
        raise SmokeError("container hash differs")
    try:
        verify_contract_cache(hf_cache, real, full=False)
    except CacheError as exc:
        raise SmokeError(f"HF cache contract differs: {exc}") from exc
    indices = plan.get("warm_smoke_assignment_indices")
    slot = int(args.slot)
    if (
        plan.get("schema_version") != "balanced-continuation-e2a-run-plan-v1"
        or plan.get("formal_submission_requires_passing_warm_smoke") is not True
        or plan.get("warm_smoke_candidate_executions") != 6
        or plan.get("warm_smoke_operator_api_calls") != 0
        or not isinstance(indices, list) or len(indices) != 6 or len(set(indices)) != 6
        or slot < 0 or slot >= 6
    ):
        raise SmokeError("warm-smoke run plan differs")
    assignment_index = indices[slot]
    assignment, assignment_line_sha, _ = load_assignment(
        preparation / "assignment", assignment_index
    )
    vault_sha, code_raw = load_code_vault(
        data_gate / "e2a_inputs" / "code_vault.jsonl", assignment
    )
    code = code_raw.decode("utf-8")
    smoke_rollout_id = sha256_bytes(json.dumps({
        "schema_version": SCHEMA,
        "source_rollout_id": assignment["rollout_id"],
        "assignment_line_sha256": assignment_line_sha,
        "slot": slot,
    }, sort_keys=True, separators=(",", ":")).encode("utf-8"))
    smoke_assignment = {**assignment, "rollout_id": smoke_rollout_id}
    output = output_root / f"slot_{slot}"
    workspace = workspace_root / f"slot_{slot}" / "candidate"
    if output.exists() or output.is_symlink() or workspace.parent.exists() or workspace.parent.is_symlink():
        raise SmokeError("warm-smoke output/workspace must be fresh")
    output.mkdir(mode=0o700)
    step = output / "step"
    step.mkdir(mode=0o700)
    workspace.mkdir(parents=True, mode=0o700)
    public_task = data_gate / "e2a_split" / "public" / assignment["task"]
    require_directory(public_task, "public task")
    execution = execute_candidate(
        code=code,
        assignment=smoke_assignment,
        real_contract=real,
        ordinal=0,
        workspace=workspace,
        workspace_token=uuid.uuid4().hex,
        step_dir=step,
        public_task=public_task,
        container=container,
        hf_cache=hf_cache,
        nvfix_dir=nvfix,
    )
    shape = validate_public_submission(
        step / "submission.csv", public_task / "sample_submission.csv", assignment["task"]
    )
    gate_pass = execution["execution_status"] == "ok" and shape["valid"] is True
    summary = {
        "schema_version": SCHEMA,
        "status": "PASS_PUBLIC_WARM_ONLY" if gate_pass else "FAIL_PUBLIC_WARM_ONLY",
        "source_commit": real["source_commit"],
        "producer_sha256": file_sha256(pathlib.Path(__file__).resolve()),
        "slot": slot,
        "assignment_index": assignment_index,
        "task": assignment["task"],
        "source_rollout_id": assignment["rollout_id"],
        "smoke_rollout_id": smoke_rollout_id,
        "assignment_line_sha256": assignment_line_sha,
        "code_vault_sha256": vault_sha,
        "code_sha256": assignment["code_sha256"],
        "candidate_executions": 1,
        "candidate_processes_started": int(execution["process_started"]),
        "candidate_wall_time_seconds": execution["wall_time_seconds"],
        "execution_status": execution["execution_status"],
        "artifact_sha256": execution["artifact_sha256"],
        "submission_shape": shape,
        "api_calls": 0,
        "candidate_retries": 0,
        "dsearch_rows_read": 0,
        "dval_rows_read": 0,
        "dtest_rows_read": 0,
        "labels_opened": False,
        "outcomes_read": False,
        "external_score_or_gain_reported": False,
        "public_data_read_only": execution["public_data_read_only"],
        "private_paths_mounted": execution["private_paths_mounted"],
        "gate_pass": gate_pass,
    }
    atomic_json(output / "summary.json", summary, mode=0o600)
    return summary


def parser() -> argparse.ArgumentParser:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--source-root", required=True)
    ap.add_argument("--preparation", required=True)
    ap.add_argument("--data-gate", required=True)
    ap.add_argument("--container", required=True)
    ap.add_argument("--hf-cache", required=True)
    ap.add_argument("--nvfix-dir", required=True)
    ap.add_argument("--output-root", required=True)
    ap.add_argument("--workspace-root", required=True)
    ap.add_argument("--slot", required=True, type=int)
    return ap


def main() -> int:
    try:
        result = run(parser().parse_args())
    except (
        SmokeError, ScoreError, OSError, UnicodeError, ValueError, json.JSONDecodeError,
        subprocess.SubprocessError,
    ) as exc:
        print(f"E2A_WARM_SMOKE_ERROR: {exc}", file=sys.stderr)
        return 2
    print(
        f"E2A_WARM_SMOKE_DONE slot={result['slot']} task={result['task']} "
        f"gate_pass={int(result['gate_pass'])} api_calls=0",
        flush=True,
    )
    return 0 if result["gate_pass"] else 3


if __name__ == "__main__":
    raise SystemExit(main())
