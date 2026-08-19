"""Independently verify one six-task E2-A public-only warm-start smoke result."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import pathlib
import re
import stat
import subprocess
import sys
import tempfile
from typing import Any

from phase1.balanced_continuation_e2a_scoring import (
    CREDENTIAL,
    ScoreError,
    TASK_SPECS,
    file_sha256,
    load_predictions,
    load_public_ids,
)
from phase1.balanced_continuation_real_contract import (
    canonical_json,
    validate_execution_receipt,
    validate_worker_contract,
)
from phase1.verify_e2a_hf_cache import (
    IndependentCacheError,
    verify_contract_cache_independent,
)
from phase1.balanced_continuation_worker import load_assignment, load_code_vault


SCHEMA = "balanced-continuation-e2a-warm-smoke-v1"
INTENT_SCHEMA = "balanced-continuation-real-process-intent-v1"
HEX32 = re.compile(r"^[0-9a-f]{32}$")
GIT_NO_LFS = [
    "-c", "filter.lfs.smudge=", "-c", "filter.lfs.process=",
    "-c", "filter.lfs.required=false",
]


class VerifyError(RuntimeError):
    pass


def digest(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def read_json(path: pathlib.Path) -> dict[str, Any]:
    raw = path.read_bytes()
    if CREDENTIAL.search(raw):
        raise VerifyError(f"credential-shaped bytes in {path.name}")
    value = json.loads(raw)
    if not isinstance(value, dict):
        raise VerifyError(f"expected JSON object: {path.name}")
    return value


def atomic_json(path: pathlib.Path, value: Any) -> None:
    if path.exists() or path.is_symlink():
        raise VerifyError("verification receipt must be new")
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, name = tempfile.mkstemp(prefix=f".{path.name}.", suffix=".tmp", dir=path.parent)
    temporary = pathlib.Path(name)
    try:
        with os.fdopen(fd, "wb") as handle:
            handle.write(canonical_json(value) + b"\n")
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary, path)
    finally:
        if temporary.exists():
            temporary.unlink()


def reconstruct_shape(
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


def verify(args: argparse.Namespace) -> dict[str, Any]:
    source_root = pathlib.Path(args.source_root).resolve()
    preparation = pathlib.Path(args.preparation).resolve()
    data_gate = pathlib.Path(args.data_gate).resolve()
    output_root = pathlib.Path(args.output_root).resolve()
    workspace_root = pathlib.Path(args.workspace_root).resolve()
    container = pathlib.Path(args.container).resolve()
    hf_cache = pathlib.Path(args.hf_cache).resolve()
    nvfix = pathlib.Path(args.nvfix_dir).resolve()
    receipt = pathlib.Path(args.receipt).resolve()
    for path, label in (
        (source_root, "source"), (preparation, "preparation"),
        (data_gate, "data gate"), (output_root, "output"),
        (workspace_root, "workspace"), (hf_cache, "HF cache"), (nvfix, "NVVM"),
    ):
        if not path.is_dir() or path.is_symlink():
            raise VerifyError(f"{label} root differs")
    if not container.is_file() or container.is_symlink():
        raise VerifyError("container differs")
    plan = read_json(preparation / "run_plan.json")
    real_raw = (preparation / "real_contract.json").read_bytes()
    if CREDENTIAL.search(real_raw):
        raise VerifyError("credential-shaped bytes in real contract")
    real = validate_worker_contract(json.loads(real_raw))
    source_head = subprocess.run(
        ["git", *GIT_NO_LFS, "rev-parse", "HEAD"], cwd=source_root, check=True,
        stdout=subprocess.PIPE, stderr=subprocess.PIPE,
    ).stdout.decode("ascii").strip()
    source_dirty = subprocess.run(
        ["git", *GIT_NO_LFS, "status", "--porcelain"], cwd=source_root, check=True,
        stdout=subprocess.PIPE, stderr=subprocess.PIPE,
    ).stdout
    if source_head != real["source_commit"] or source_dirty:
        raise VerifyError("source checkout is not the exact clean contract commit")
    if file_sha256(container) != real["container_sha256"]:
        raise VerifyError("container hash differs")
    try:
        verify_contract_cache_independent(hf_cache, real, full=False)
    except IndependentCacheError as exc:
        raise VerifyError(f"HF cache contract differs: {exc}") from exc
    indices = plan.get("warm_smoke_assignment_indices")
    slot = int(args.slot)
    if (
        not isinstance(indices, list) or len(indices) != 6 or len(set(indices)) != 6
        or not 0 <= slot < 6
    ):
        raise VerifyError("warm-smoke selection differs")
    assignment_index = indices[slot]
    assignment, assignment_line_sha, _ = load_assignment(
        preparation / "assignment", assignment_index
    )
    vault_sha, code_raw = load_code_vault(
        data_gate / "e2a_inputs" / "code_vault.jsonl", assignment
    )
    smoke_rollout_id = digest(json.dumps({
        "schema_version": SCHEMA,
        "source_rollout_id": assignment["rollout_id"],
        "assignment_line_sha256": assignment_line_sha,
        "slot": slot,
    }, sort_keys=True, separators=(",", ":")).encode("utf-8"))
    root = output_root / f"slot_{slot}"
    step = root / "step"
    workspace = workspace_root / f"slot_{slot}" / "candidate"
    if not root.is_dir() or root.is_symlink() or not workspace.is_dir() or workspace.is_symlink():
        raise VerifyError("smoke output/workspace differs")
    if {path.name for path in root.iterdir()} != {"step", "summary.json"}:
        raise VerifyError("warm-smoke top-level file set differs")
    summary = read_json(root / "summary.json")
    execution = validate_execution_receipt(read_json(step / "execution.json"), real)
    if (
        execution["rollout_id"] != smoke_rollout_id
        or execution["task"] != assignment["task"]
        or execution["execution_ordinal"] != 0
        or execution["code_sha256"] != assignment["code_sha256"]
        or execution["candidate_execution_attempted"] is not True
        or execution["public_data_read_only"] is not True
        or execution["private_paths_mounted"] is not False
        or execution["retry_count"] != 0
        or not isinstance(execution["workspace_token"], str)
        or not HEX32.fullmatch(execution["workspace_token"])
    ):
        raise VerifyError("execution receipt identity differs")
    if (step / "code.py").read_bytes() != code_raw or (workspace / "solution.py").read_bytes() != code_raw:
        raise VerifyError("executed code differs from frozen vault")
    intent = read_json(step / "candidate_intent.json")
    command = intent.get("command")
    if (
        intent.get("schema_version") != INTENT_SCHEMA
        or intent.get("rollout_id") != smoke_rollout_id
        or intent.get("execution_ordinal") != 0
        or intent.get("process_kind") != "candidate"
        or intent.get("process_will_start") is not True
        or intent.get("retry_count") != 0
        or not isinstance(command, list)
        or any(not isinstance(item, str) for item in command)
        or intent.get("command_sha256") != digest("\0".join(command).encode("utf-8"))
        or command[:2] != ["singularity", "exec"]
        or "--network" not in command
        or command[command.index("--network") + 1] != "none"
        or "--cleanenv" not in command
        or str(container) not in command
    ):
        raise VerifyError("candidate intent/network contract differs")
    bind_values = [
        command[index + 1]
        for index, item in enumerate(command[:-1]) if item == "--bind"
    ]
    combined = ",".join(bind_values)
    public_task = data_gate / "e2a_split" / "public" / assignment["task"]
    required_mounts = (
        f"{workspace}:/workspace", f"{public_task}:/workspace/data:ro",
        f"{hf_cache}:/hf:ro", f"{nvfix}:/mnt:ro",
    )
    if any(item not in combined for item in required_mounts):
        raise VerifyError("candidate mount contract differs")
    if any(item in combined.lower() for item in ("/private", "dsearch", "dval", "answer")):
        raise VerifyError("candidate command contains private-label mount")

    process = read_json(step / "candidate_process.json")
    stdout = step / "candidate.stdout"
    stderr = step / "candidate.stderr"
    if (
        process.get("return_code") != execution["exit_code"]
        or process.get("timed_out") != execution["timed_out"]
        or process.get("wall_time_seconds") != execution["wall_time_seconds"]
        or process.get("stdout_sha256") != file_sha256(stdout)
        or process.get("stderr_sha256") != file_sha256(stderr)
    ):
        raise VerifyError("candidate process receipt differs")
    artifact = step / "submission.csv"
    if execution["artifact_sha256"] is None:
        if artifact.exists() or artifact.is_symlink():
            raise VerifyError("null artifact unexpectedly materialized")
    elif not artifact.is_file() or artifact.is_symlink() or file_sha256(artifact) != execution[
        "artifact_sha256"
    ]:
        raise VerifyError("candidate artifact differs")
    shape = reconstruct_shape(
        artifact, public_task / "sample_submission.csv", assignment["task"]
    )
    expected_pass = execution["execution_status"] == "ok" and shape["valid"] is True
    producer_path = source_root / "phase1" / "balanced_continuation_e2a_warm_smoke.py"
    expected_summary = {
        "schema_version": SCHEMA,
        "status": "PASS_PUBLIC_WARM_ONLY" if expected_pass else "FAIL_PUBLIC_WARM_ONLY",
        "source_commit": real["source_commit"],
        "producer_sha256": file_sha256(producer_path),
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
        "public_data_read_only": True,
        "private_paths_mounted": False,
        "gate_pass": expected_pass,
    }
    if summary != expected_summary:
        raise VerifyError("warm-smoke summary differs from independent reconstruction")
    if any(
        re.search(r"(?i)(dsearch|dval|dtest|score|gain|utility)", path.name)
        for path in root.rglob("*") if path.is_file()
    ):
        raise VerifyError("score-bearing artifact found in warm-only smoke")
    if os.name == "posix" and stat.S_IMODE((root / "summary.json").stat().st_mode) != 0o600:
        raise VerifyError("warm-smoke summary mode differs")
    result = {
        "schema_version": "balanced-continuation-e2a-warm-smoke-verification-v1",
        "status": (
            "VERIFIED_E2A_PUBLIC_WARM_SMOKE_PASS"
            if expected_pass else "VERIFIED_E2A_PUBLIC_WARM_SMOKE_FAIL"
        ),
        "producer_imported": False,
        "slot": slot,
        "assignment_index": assignment_index,
        "task": assignment["task"],
        "candidate_executions": 1,
        "api_calls": 0,
        "dsearch_rows_read": 0,
        "dval_rows_read": 0,
        "dtest_rows_read": 0,
        "labels_opened": False,
        "outcomes_read": False,
        "gate_pass": expected_pass,
        "summary_sha256": file_sha256(root / "summary.json"),
    }
    atomic_json(receipt, result)
    print(json.dumps(result, sort_keys=True, separators=(",", ":")))
    return result


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source-root", required=True)
    parser.add_argument("--preparation", required=True)
    parser.add_argument("--data-gate", required=True)
    parser.add_argument("--container", required=True)
    parser.add_argument("--hf-cache", required=True)
    parser.add_argument("--nvfix-dir", required=True)
    parser.add_argument("--output-root", required=True)
    parser.add_argument("--workspace-root", required=True)
    parser.add_argument("--slot", required=True, type=int)
    parser.add_argument("--receipt", required=True)
    try:
        verify(parser.parse_args())
    except (
        VerifyError, ScoreError, OSError, UnicodeError, ValueError, json.JSONDecodeError,
        subprocess.SubprocessError,
    ) as exc:
        print(f"VERIFY_E2A_WARM_SMOKE_ERROR: {exc}", file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
