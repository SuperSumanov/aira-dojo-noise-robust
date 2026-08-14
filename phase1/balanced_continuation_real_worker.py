"""Execute one real, hash-locked balanced-continuation rollout.

Each rollout gets one fresh workspace, one warm-start execution, and exactly H one-shot
operator transitions.  Intent records are durable before every potentially paid action.
An interrupted PENDING action without a complete step manifest is ambiguous and therefore
never retried automatically.
"""

from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import json
import os
import pathlib
import re
import shutil
import signal
import subprocess
import sys
import tempfile
import threading
import time
import uuid
from typing import Any

from phase1.balanced_continuation_e1_scoring import (
    CREDENTIAL,
    ScoreError,
    checked_json,
    file_sha256,
)
from phase1.balanced_continuation_operator_entry import MODEL_ID
from phase1.balanced_continuation_real_contract import (
    EXECUTION_RECEIPT_SCHEMA,
    RealContractError,
    bind_visible_step,
    build_operator_request,
    canonical_json,
    sha256_bytes,
    validate_execution_receipt,
    validate_operator_response,
    validate_search_receipt,
    validate_visible_step,
    validate_worker_contract,
)
from phase1.balanced_continuation_worker import WorkerError, load_assignment, load_code_vault


STATE_SCHEMA = "balanced-continuation-real-worker-state-v1"
RESULT_SCHEMA = "balanced-continuation-real-worker-result-v1"
WORKSPACE_SCHEMA = "balanced-continuation-real-workspace-v1"
INTENT_SCHEMA = "balanced-continuation-real-process-intent-v1"
STEP_MANIFEST_SCHEMA = "balanced-continuation-real-step-manifest-v1"
COMMITMENT_SCHEMA = "balanced-continuation-sealed-commitment-v1"
OPERATOR_USAGE_SCHEMA = "balanced-continuation-operator-usage-v1"
LOG_HEAD_BYTES = 32768
LOG_TAIL_BYTES = 32768
HEX64 = re.compile(r"[0-9a-f]{64}\Z")
HEX32 = re.compile(r"[0-9a-f]{32}\Z")
RESULT_KEYS = {
    "schema_version", "status", "rollout_id", "global_order", "block_id",
    "block_replicate", "anchor_id", "task", "sibling_id", "source_run_id",
    "source_commit", "assignment_line_sha256", "real_contract_sha256",
    "workspace_path", "workspace_token", "started_utc", "ended_utc",
    "continuation_horizon", "execution_timeout_seconds", "candidate_network_policy",
    "candidate_execution_attempts", "candidate_processes_started", "operator_calls",
    "operator_retry_count", "candidate_retry_count", "analyze_operator_calls",
    "dtest_rows_read", "candidate_wall_time_seconds", "visible_dsearch_utilities",
    "sealed_dval_commitment_sha256s", "api_usage",
}


class RealWorkerError(RuntimeError):
    pass


def utc_now() -> str:
    return dt.datetime.now(dt.timezone.utc).isoformat(timespec="microseconds").replace(
        "+00:00", "Z"
    )


def atomic_bytes(path: pathlib.Path, raw: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, name = tempfile.mkstemp(prefix=f".{path.name}.", suffix=".tmp", dir=path.parent)
    temporary = pathlib.Path(name)
    try:
        with os.fdopen(fd, "wb") as handle:
            handle.write(raw)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary, path)
        if os.name == "posix":
            directory_fd = os.open(path.parent, os.O_RDONLY | getattr(os, "O_DIRECTORY", 0))
            try:
                os.fsync(directory_fd)
            finally:
                os.close(directory_fd)
    finally:
        if temporary.exists():
            temporary.unlink()


def atomic_json_new(path: pathlib.Path, value: Any) -> None:
    if path.exists() or path.is_symlink():
        raise RealWorkerError(f"refusing existing output: {path}")
    atomic_bytes(path, canonical_json(value) + b"\n")


def atomic_json_replace(path: pathlib.Path, value: Any) -> None:
    atomic_bytes(path, canonical_json(value) + b"\n")


def require_new_root(path_text: str, label: str) -> pathlib.Path:
    path = pathlib.Path(path_text)
    if not path.is_absolute():
        raise RealWorkerError(f"{label} must be absolute")
    path = path.resolve()
    if not path.is_dir() or path.is_symlink():
        raise RealWorkerError(f"{label} must be an existing non-symlink directory")
    return path


def require_disjoint_roots(roots: dict[str, pathlib.Path]) -> None:
    values = list(roots.items())
    for index, (left_name, left) in enumerate(values):
        for right_name, right in values[index + 1:]:
            if left == right or left in right.parents or right in left.parents:
                raise RealWorkerError(
                    f"{left_name} and {right_name} roots must be disjoint"
                )


def exact_git_source(expected_commit: str) -> pathlib.Path:
    repo = pathlib.Path(__file__).resolve().parents[1]
    head = subprocess.run(
        ["git", "rev-parse", "HEAD"], cwd=repo, check=True,
        stdout=subprocess.PIPE, stderr=subprocess.PIPE,
    ).stdout.decode("ascii").strip()
    if head != expected_commit:
        raise RealWorkerError(f"source commit differs: expected={expected_commit} actual={head}")
    if subprocess.run(
        ["git", "status", "--porcelain"], cwd=repo, check=True,
        stdout=subprocess.PIPE, stderr=subprocess.PIPE,
    ).stdout:
        raise RealWorkerError("real worker requires an exact clean worktree")
    return repo


def evaluator_contract_sha(real_contract: dict[str, Any]) -> str:
    return sha256_bytes(canonical_json({
        "split_manifest_sha256_opaque": real_contract["split_manifest_sha256_opaque"],
        "search_evaluator_executable_sha256": real_contract["search_evaluator_executable_sha256"],
        "sealed_label_evaluator_executable_sha256": real_contract[
            "sealed_label_evaluator_executable_sha256"
        ],
        "score_visibility": real_contract["score_visibility"],
        "sealed_label_policy": real_contract["sealed_label_policy"],
    }))


def validate_contract_pair(
    legacy: dict[str, Any], real: dict[str, Any], split_root: pathlib.Path
) -> None:
    expected = {
        "model_id": MODEL_ID,
        "provider": "deepseek",
        "operator_config_sha256": real["operator_config_sha256"],
        "prompt_sha256": real["prompt_sha256"],
        "source_commit": real["source_commit"],
        "dataset_contract_sha256": real["public_dataset_contract_sha256"],
        "evaluator_contract_sha256": evaluator_contract_sha(real),
        "hardware_class": "single-rtx3090-24gb",
        "execution_timeout_seconds": real["execution_timeout_seconds"],
        "continuation_horizon": real["continuation_horizon"],
        "debug_policy": "fixed_one_operator_per_step",
        "workspace_policy": "fresh_per_rollout",
        "temperature": 0.6,
    }
    if legacy != {"schema_version": "balanced-continuation-contract-v1", **expected}:
        raise RealWorkerError("assignment and real worker contracts are not identical in meaning")
    public_root = (split_root / "public").resolve()
    if real["public_data_root"] != public_root.as_posix():
        raise RealWorkerError("real contract public root differs from split root")
    summary = checked_json(split_root / "summary.json")
    if (
        summary.get("public_dataset_contract_sha256")
        != real["public_dataset_contract_sha256"]
        or summary.get("split_manifest_sha256_opaque")
        != real["split_manifest_sha256_opaque"]
        or summary.get("dtest_rows_read") != 0
    ):
        raise RealWorkerError("split summary differs from real worker contract")


def task_description(repo: pathlib.Path, split_root: pathlib.Path, task: str) -> str:
    instructions = repo / "src" / "dojo" / "tasks" / "mlebench" / "instructions.txt"
    description = split_root / "public" / task / "description.md"
    if not instructions.is_file() or not description.is_file():
        raise RealWorkerError("public task description source is missing")
    value = instructions.read_text(encoding="utf-8") + "\n" + description.read_text(encoding="utf-8")
    if CREDENTIAL.search(value.encode("utf-8")):
        raise RealWorkerError("credential-shaped bytes in public task description")
    return value


def clean_sidecar_env(include_operator_credential: bool) -> dict[str, str]:
    allowed = {
        "PATH", "LANG", "LC_ALL", "LD_LIBRARY_PATH", "SSL_CERT_FILE", "SSL_CERT_DIR",
        "HTTP_PROXY", "HTTPS_PROXY", "http_proxy", "https_proxy", "NO_PROXY", "no_proxy",
    }
    env = {key: value for key, value in os.environ.items() if key in allowed}
    if include_operator_credential:
        for key in ("PRIMARY_KEY_DEEPSEEK_V4_FLASH", "PRIMARY_KEY"):
            if key in os.environ:
                env[key] = os.environ[key]
    env["PYTHONPATH"] = str(pathlib.Path(__file__).resolve().parents[1])
    return env


def process_intent(
    path: pathlib.Path,
    *,
    rollout_id: str,
    ordinal: int,
    process_kind: str,
    command: list[str],
    process_will_start: bool,
) -> None:
    if path.exists() or path.is_symlink():
        raise RealWorkerError(f"process intent already exists: {path}")
    safe_command = [part for part in command if not CREDENTIAL.search(part.encode("utf-8"))]
    if len(safe_command) != len(command):
        raise RealWorkerError("credential-shaped command argument refused")
    atomic_json_new(path, {
        "schema_version": INTENT_SCHEMA,
        "rollout_id": rollout_id,
        "execution_ordinal": ordinal,
        "process_kind": process_kind,
        "process_will_start": process_will_start,
        "command": command,
        "command_sha256": sha256_bytes("\0".join(command).encode("utf-8")),
        "created_utc": utc_now(),
        "retry_count": 0,
    })


def kill_process_group(process: subprocess.Popen[bytes]) -> None:
    if process.poll() is not None:
        return
    try:
        os.killpg(process.pid, signal.SIGTERM)
    except ProcessLookupError:
        return
    try:
        process.wait(timeout=5)
    except subprocess.TimeoutExpired:
        try:
            os.killpg(process.pid, signal.SIGKILL)
        except ProcessLookupError:
            pass
        process.wait(timeout=10)


def capture_pipe(pipe: Any, destination: dict[str, Any]) -> None:
    digest = hashlib.sha256()
    total = 0
    complete = bytearray()
    head = bytearray()
    tail = bytearray()
    truncated = False
    while True:
        chunk = pipe.read(65536)
        if not chunk:
            break
        digest.update(chunk)
        total += len(chunk)
        if not truncated:
            complete.extend(chunk)
            if len(complete) > LOG_HEAD_BYTES + LOG_TAIL_BYTES:
                truncated = True
                head.extend(complete[:LOG_HEAD_BYTES])
                tail.extend(complete[-LOG_TAIL_BYTES:])
                complete.clear()
        else:
            tail.extend(chunk)
            if len(tail) > LOG_TAIL_BYTES:
                del tail[:-LOG_TAIL_BYTES]
    if truncated:
        marker = f"\n...[LOG TRUNCATED; full_bytes={total}]...\n".encode("ascii")
        stored = bytes(head) + marker + bytes(tail)
    else:
        stored = bytes(complete)
    destination.update({
        "stored": stored,
        "total_bytes": total,
        "truncated": truncated,
        "full_sha256": digest.hexdigest(),
    })


def run_process_once(
    command: list[str],
    *,
    cwd: pathlib.Path,
    env: dict[str, str] | None,
    timeout_seconds: int,
    stdout_path: pathlib.Path,
    stderr_path: pathlib.Path,
) -> dict[str, Any]:
    if stdout_path.exists() or stderr_path.exists():
        raise RealWorkerError("process log path already exists")
    started_utc = utc_now()
    started = time.monotonic()
    process = subprocess.Popen(
        command, cwd=cwd, env=env, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
        start_new_session=True,
    )
    if process.stdout is None or process.stderr is None:
        raise RealWorkerError("candidate process pipes were not created")
    stdout_capture: dict[str, Any] = {}
    stderr_capture: dict[str, Any] = {}
    stdout_thread = threading.Thread(
        target=capture_pipe, args=(process.stdout, stdout_capture), daemon=True
    )
    stderr_thread = threading.Thread(
        target=capture_pipe, args=(process.stderr, stderr_capture), daemon=True
    )
    stdout_thread.start()
    stderr_thread.start()
    timed_out = False
    try:
        process.wait(timeout=timeout_seconds)
    except subprocess.TimeoutExpired:
        timed_out = True
        kill_process_group(process)
    stdout_thread.join(timeout=15)
    stderr_thread.join(timeout=15)
    if stdout_thread.is_alive() or stderr_thread.is_alive():
        kill_process_group(process)
        raise RealWorkerError("candidate log drain did not terminate")
    if "stored" not in stdout_capture or "stored" not in stderr_capture:
        raise RealWorkerError("candidate log capture failed")
    atomic_bytes(stdout_path, stdout_capture.pop("stored"))
    atomic_bytes(stderr_path, stderr_capture.pop("stored"))
    return {
        "started_utc": started_utc,
        "ended_utc": utc_now(),
        "wall_time_seconds": max(time.monotonic() - started, 1e-6),
        "return_code": int(process.returncode),
        "timed_out": timed_out,
        "stdout_sha256": file_sha256(stdout_path),
        "stderr_sha256": file_sha256(stderr_path),
        "stdout_capture": stdout_capture,
        "stderr_capture": stderr_capture,
    }


def candidate_host_env() -> dict[str, str]:
    forbidden_prefixes = ("SINGULARITYENV_", "APPTAINERENV_")
    forbidden = sorted(
        key for key in os.environ if key.upper().startswith(forbidden_prefixes)
    )
    if forbidden:
        raise RealWorkerError(
            "candidate environment injection variables are forbidden: " + ",".join(forbidden)
        )
    allowed = {
        "PATH", "HOME", "USER", "LANG", "LC_ALL", "LD_LIBRARY_PATH", "TMPDIR",
        "CUDA_VISIBLE_DEVICES", "NVIDIA_VISIBLE_DEVICES", "SLURM_JOB_ID",
        "SLURM_ARRAY_JOB_ID", "SLURM_ARRAY_TASK_ID", "SLURM_JOB_GPUS",
    }
    env = {key: value for key, value in os.environ.items() if key in allowed}
    if any(CREDENTIAL.search(value.encode("utf-8")) for value in env.values()):
        raise RealWorkerError("credential-shaped bytes refused in candidate host environment")
    return env


def candidate_command(
    workspace: pathlib.Path,
    public_task: pathlib.Path,
    container: pathlib.Path,
    hf_cache: pathlib.Path,
    nvfix_dir: pathlib.Path,
) -> list[str]:
    binds = f"{workspace}:/workspace,{public_task}:/workspace/data:ro,{hf_cache}:/hf:ro"
    return [
        "singularity", "exec", "--containall", "--cleanenv", "--net", "--network", "none",
        "--no-home", "--no-mount", "bind-paths", "--no-eval", "--nv",
        "--pwd", "/workspace",
        "--bind", binds,
        "--bind", "/etc/OpenCL/vendors/nvidia.icd:/etc/OpenCL/vendors/nvidia.icd",
        "--bind", f"{nvfix_dir}:/mnt:ro",
        str(container), "env",
        "PYTHONUNBUFFERED=1", "WANDB_DISABLED=1", "TQDM_DISABLE=1", "TF_CPP_MIN_LOG_LEVEL=3",
        "HOME=/tmp", "HF_HOME=/hf", "TORCH_HOME=/hf/torch", "HF_HUB_OFFLINE=1",
        "TRANSFORMERS_OFFLINE=1", "LD_LIBRARY_PATH=/mnt:/.singularity.d/libs",
        "python", "solution.py",
    ]


def terminal_output(stdout_path: pathlib.Path, stderr_path: pathlib.Path) -> str:
    stdout = stdout_path.read_bytes()[-32768:].decode("utf-8", errors="replace")
    stderr = stderr_path.read_bytes()[-32768:].decode("utf-8", errors="replace")
    value = f"[stdout tail]\n{stdout}\n[stderr tail]\n{stderr}"
    if CREDENTIAL.search(value.encode("utf-8")):
        raise RealWorkerError("credential-shaped bytes in candidate terminal output")
    return value


def execute_candidate(
    *,
    code: str,
    assignment: dict[str, Any],
    real_contract: dict[str, Any],
    ordinal: int,
    workspace: pathlib.Path,
    workspace_token: str,
    step_dir: pathlib.Path,
    public_task: pathlib.Path,
    container: pathlib.Path,
    hf_cache: pathlib.Path,
    nvfix_dir: pathlib.Path,
) -> dict[str, Any]:
    code_path = step_dir / "code.py"
    atomic_bytes(code_path, code.encode("utf-8"))
    solution = workspace / "solution.py"
    atomic_bytes(solution, code.encode("utf-8"))
    submission = workspace / "submission.csv"
    if submission.exists() or submission.is_symlink():
        submission.unlink()
    command = candidate_command(workspace, public_task, container, hf_cache, nvfix_dir)
    intent = step_dir / "candidate_intent.json"
    process_intent(
        intent, rollout_id=assignment["rollout_id"], ordinal=ordinal,
        process_kind="candidate", command=command, process_will_start=True,
    )
    stdout_path, stderr_path = step_dir / "candidate.stdout", step_dir / "candidate.stderr"
    process = run_process_once(
        command, cwd=workspace, env=candidate_host_env(),
        timeout_seconds=real_contract["execution_timeout_seconds"],
        stdout_path=stdout_path, stderr_path=stderr_path,
    )
    status = "timeout" if process["timed_out"] else (
        "ok" if process["return_code"] == 0 else "execution_error"
    )
    artifact_path = step_dir / "submission.csv"
    artifact_sha: str | None = None
    if status == "ok" and submission.is_file() and not submission.is_symlink():
        shutil.copyfile(submission, artifact_path)
        artifact_sha = file_sha256(artifact_path)
    terminal = terminal_output(stdout_path, stderr_path)
    receipt = {
        "schema_version": EXECUTION_RECEIPT_SCHEMA,
        "rollout_id": assignment["rollout_id"],
        "workspace_token": workspace_token,
        "task": assignment["task"],
        "execution_ordinal": ordinal,
        "code_sha256": sha256_bytes(code.encode("utf-8")),
        "execution_status": status,
        "process_started": True,
        "candidate_execution_attempted": True,
        "exit_code": process["return_code"],
        "timed_out": process["timed_out"],
        "wall_time_seconds": process["wall_time_seconds"],
        "terminal_output": terminal,
        "terminal_output_sha256": sha256_bytes(terminal.encode("utf-8")),
        "artifact_sha256": artifact_sha,
        "public_data_read_only": True,
        "private_paths_mounted": False,
        "retry_count": 0,
    }
    validate_execution_receipt(receipt, real_contract)
    atomic_json_new(step_dir / "execution.json", receipt)
    atomic_json_new(step_dir / "candidate_process.json", process)
    return receipt


def invalid_format_execution(
    code: str,
    assignment: dict[str, Any],
    real_contract: dict[str, Any],
    ordinal: int,
    workspace_token: str,
    step_dir: pathlib.Path,
) -> dict[str, Any]:
    atomic_bytes(step_dir / "code.py", code.encode("utf-8"))
    process_intent(
        step_dir / "candidate_intent.json", rollout_id=assignment["rollout_id"],
        ordinal=ordinal, process_kind="candidate", command=[], process_will_start=False,
    )
    terminal = "operator response did not contain an executable code block\n"
    receipt = {
        "schema_version": EXECUTION_RECEIPT_SCHEMA,
        "rollout_id": assignment["rollout_id"],
        "workspace_token": workspace_token,
        "task": assignment["task"],
        "execution_ordinal": ordinal,
        "code_sha256": sha256_bytes(code.encode("utf-8")),
        "execution_status": "invalid_format",
        "process_started": False,
        "candidate_execution_attempted": True,
        "exit_code": None,
        "timed_out": False,
        "wall_time_seconds": 1e-6,
        "terminal_output": terminal,
        "terminal_output_sha256": sha256_bytes(terminal.encode()),
        "artifact_sha256": None,
        "public_data_read_only": True,
        "private_paths_mounted": False,
        "retry_count": 0,
    }
    validate_execution_receipt(receipt, real_contract)
    atomic_json_new(step_dir / "execution.json", receipt)
    return receipt


def run_sidecar(
    step_dir: pathlib.Path,
    label: str,
    command: list[str],
    *,
    rollout_id: str,
    ordinal: int,
    timeout_seconds: int,
    include_operator_credential: bool = False,
) -> subprocess.CompletedProcess[bytes]:
    process_intent(
        step_dir / f"{label}_intent.json", rollout_id=rollout_id, ordinal=ordinal,
        process_kind=label, command=command, process_will_start=True,
    )
    started = time.monotonic()
    try:
        completed = subprocess.run(
            command, cwd=pathlib.Path(__file__).resolve().parents[1],
            env=clean_sidecar_env(include_operator_credential),
            stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=timeout_seconds,
            check=False,
        )
    except subprocess.TimeoutExpired as exc:
        stdout = exc.stdout or b""
        stderr = exc.stderr or b""
        if CREDENTIAL.search(stdout + b"\n" + stderr):
            raise RealWorkerError(f"credential-shaped bytes in {label} timeout output") from exc
        atomic_bytes(step_dir / f"{label}.stdout", stdout)
        atomic_bytes(step_dir / f"{label}.stderr", stderr)
        atomic_json_new(step_dir / f"{label}_process.json", {
            "return_code": None, "timed_out": True,
            "wall_time_seconds": max(time.monotonic() - started, 1e-6),
        })
        raise RealWorkerError(f"{label} timed out; no automatic retry") from exc
    if CREDENTIAL.search(completed.stdout + b"\n" + completed.stderr):
        raise RealWorkerError(f"credential-shaped bytes in {label} process output")
    atomic_bytes(step_dir / f"{label}.stdout", completed.stdout)
    atomic_bytes(step_dir / f"{label}.stderr", completed.stderr)
    atomic_json_new(step_dir / f"{label}_process.json", {
        "return_code": completed.returncode, "timed_out": False,
        "wall_time_seconds": max(time.monotonic() - started, 1e-6),
        "stdout_sha256": sha256_bytes(completed.stdout),
        "stderr_sha256": sha256_bytes(completed.stderr),
    })
    if completed.returncode != 0:
        raise RealWorkerError(f"{label} failed rc={completed.returncode}; no automatic retry")
    return completed


def score_step(
    *,
    assignment: dict[str, Any],
    real_contract: dict[str, Any],
    ordinal: int,
    workspace_token: str,
    step_dir: pathlib.Path,
    split_root: pathlib.Path,
    sealed_rollout_root: pathlib.Path,
) -> tuple[dict[str, Any], dict[str, Any]]:
    artifact = step_dir / "submission.csv"
    dsearch_path = step_dir / "dsearch.json"
    base = [
        "--contract", str(step_dir.parent.parent / "real_contract.json"),
        "--task", assignment["task"], "--rollout-id", assignment["rollout_id"],
        "--workspace-token", workspace_token, "--ordinal", str(ordinal),
        "--artifact", str(artifact),
    ]
    run_sidecar(
        step_dir, "dsearch",
        [
            sys.executable, "-m", "phase1.balanced_continuation_dsearch_eval",
            *base,
            "--labels", str(split_root / "private" / "dsearch" / f"{assignment['task']}.csv"),
            "--receipt", str(dsearch_path),
        ],
        rollout_id=assignment["rollout_id"], ordinal=ordinal,
        timeout_seconds=real_contract["evaluator_timeout_seconds"],
    )
    search = validate_search_receipt(checked_json(dsearch_path), real_contract)
    sealed_path = sealed_rollout_root / f"dval_{ordinal:03d}.json"
    completed = run_sidecar(
        step_dir, "dval_sealer",
        [
            sys.executable, "-m", "phase1.balanced_continuation_dval_sealer",
            *base,
            "--labels", str(split_root / "private" / "dval" / f"{assignment['task']}.csv"),
            "--sealed-receipt", str(sealed_path),
        ],
        rollout_id=assignment["rollout_id"], ordinal=ordinal,
        timeout_seconds=real_contract["evaluator_timeout_seconds"],
    )
    if CREDENTIAL.search(completed.stdout):
        raise RealWorkerError("credential-shaped bytes in sealed commitment")
    try:
        commitment = json.loads(completed.stdout)
    except json.JSONDecodeError as exc:
        raise RealWorkerError("D_val sealer stdout is not one commitment") from exc
    expected_keys = {
        "schema_version", "rollout_id", "workspace_token", "task", "execution_ordinal",
        "sealed_label_receipt_sha256",
    }
    if not isinstance(commitment, dict) or set(commitment) != expected_keys:
        raise RealWorkerError("sealed commitment schema differs")
    if (
        commitment["schema_version"] != COMMITMENT_SCHEMA
        or commitment["rollout_id"] != assignment["rollout_id"]
        or commitment["workspace_token"] != workspace_token
        or commitment["task"] != assignment["task"]
        or commitment["execution_ordinal"] != ordinal
        or not isinstance(commitment["sealed_label_receipt_sha256"], str)
        or not HEX64.fullmatch(commitment["sealed_label_receipt_sha256"])
    ):
        raise RealWorkerError("sealed commitment identity differs")
    atomic_json_new(step_dir / "dval_commitment.json", commitment)
    return search, commitment


def recursive_hashes(root: pathlib.Path, exclude: set[str] | None = None) -> dict[str, str]:
    exclude = exclude or set()
    output = {}
    for path in sorted(root.rglob("*")):
        rel = path.relative_to(root).as_posix()
        if path.is_file() and rel not in exclude:
            output[rel] = file_sha256(path)
    return output


def finalize_step(step_dir: pathlib.Path, assignment: dict[str, Any], ordinal: int) -> str:
    manifest_path = step_dir / "step_manifest.json"
    if manifest_path.exists():
        raise RealWorkerError("step manifest already exists")
    value = {
        "schema_version": STEP_MANIFEST_SCHEMA,
        "rollout_id": assignment["rollout_id"],
        "execution_ordinal": ordinal,
        "files": recursive_hashes(step_dir),
    }
    atomic_json_new(manifest_path, value)
    return file_sha256(manifest_path)


def validate_complete_step(step_dir: pathlib.Path, rollout_id: str, ordinal: int) -> str:
    manifest_path = step_dir / "step_manifest.json"
    manifest = checked_json(manifest_path)
    if (
        set(manifest) != {"schema_version", "rollout_id", "execution_ordinal", "files"}
        or manifest["schema_version"] != STEP_MANIFEST_SCHEMA
        or manifest["rollout_id"] != rollout_id
        or manifest["execution_ordinal"] != ordinal
        or manifest["files"] != recursive_hashes(step_dir, {"step_manifest.json"})
    ):
        raise RealWorkerError(f"durable step manifest differs at ordinal {ordinal}")
    return file_sha256(manifest_path)


def initial_state(
    assignment: dict[str, Any], assignment_line_sha: str, real_contract_sha: str,
    code_vault_sha: str, workspace: pathlib.Path, workspace_token: str,
) -> dict[str, Any]:
    return {
        "schema_version": STATE_SCHEMA,
        "rollout_id": assignment["rollout_id"],
        "assignment_line_sha256": assignment_line_sha,
        "real_contract_sha256": real_contract_sha,
        "code_vault_sha256": code_vault_sha,
        "phase": "READY",
        "next_execution_ordinal": 0,
        "pending_execution_ordinal": None,
        "workspace_path": str(workspace),
        "workspace_token": workspace_token,
        "started_utc": utc_now(),
        "completed_step_manifest_sha256s": [],
        "operator_calls": 0,
        "candidate_execution_attempts": 0,
    }


def validate_state(
    state: dict[str, Any], assignment: dict[str, Any], assignment_line_sha: str,
    real_contract_sha: str, code_vault_sha: str, horizon: int,
) -> None:
    required = {
        "schema_version", "rollout_id", "assignment_line_sha256", "real_contract_sha256",
        "code_vault_sha256", "phase", "next_execution_ordinal", "pending_execution_ordinal",
        "workspace_path", "workspace_token", "completed_step_manifest_sha256s",
        "operator_calls", "candidate_execution_attempts", "started_utc",
    }
    if set(state) != required or state["schema_version"] != STATE_SCHEMA:
        raise RealWorkerError("worker state schema differs")
    expected = {
        "rollout_id": assignment["rollout_id"],
        "assignment_line_sha256": assignment_line_sha,
        "real_contract_sha256": real_contract_sha,
        "code_vault_sha256": code_vault_sha,
    }
    if any(state[key] != value for key, value in expected.items()):
        raise RealWorkerError("worker state identity differs")
    if state["phase"] not in {"READY", "PENDING", "FINALIZED"}:
        raise RealWorkerError("worker state phase differs")
    if not isinstance(state["workspace_path"], str) or not pathlib.Path(
        state["workspace_path"]
    ).is_absolute():
        raise RealWorkerError("worker state workspace path differs")
    if not isinstance(state["workspace_token"], str) or not HEX32.fullmatch(
        state["workspace_token"]
    ):
        raise RealWorkerError("worker state workspace token differs")
    try:
        dt.datetime.fromisoformat(state["started_utc"].replace("Z", "+00:00"))
    except (AttributeError, ValueError) as exc:
        raise RealWorkerError("worker state start timestamp differs") from exc
    next_ordinal = state["next_execution_ordinal"]
    if (
        isinstance(next_ordinal, bool)
        or not isinstance(next_ordinal, int)
        or not 0 <= next_ordinal <= horizon + 1
    ):
        raise RealWorkerError("worker state next ordinal differs")
    pending = state["pending_execution_ordinal"]
    if state["phase"] == "PENDING":
        if pending != next_ordinal or next_ordinal > horizon:
            raise RealWorkerError("worker state pending ordinal differs")
    elif pending is not None:
        raise RealWorkerError("non-pending worker state has a pending ordinal")
    if state["phase"] == "FINALIZED" and next_ordinal != horizon + 1:
        raise RealWorkerError("finalized worker state did not finish the horizon")
    manifests = state["completed_step_manifest_sha256s"]
    if not isinstance(manifests, list) or any(
        not isinstance(value, str) or not HEX64.fullmatch(value) for value in manifests
    ):
        raise RealWorkerError("worker state step manifests differ")
    for key in ("operator_calls", "candidate_execution_attempts"):
        value = state[key]
        if isinstance(value, bool) or not isinstance(value, int) or value < 0:
            raise RealWorkerError(f"worker state {key} differs")


def validate_operator_usage(
    value: dict[str, Any], request: dict[str, Any], response: dict[str, Any]
) -> None:
    expected_keys = {
        "schema_version", "model_id", "provider_request_id", "api_calls", "retry_count",
        "latency_seconds", "prompt_tokens", "completion_tokens", "total_tokens",
        "request_sha256", "rendered_prompt_sha256", "raw_response_sha256",
        "extraction_status",
    }
    if set(value) != expected_keys:
        raise RealWorkerError("operator usage schema differs")
    if (
        value["schema_version"] != OPERATOR_USAGE_SCHEMA
        or value["model_id"] != MODEL_ID
        or value["provider_request_id"] != response["provider_request_id"]
        or value["api_calls"] != 1
        or value["retry_count"] != 0
        or value["request_sha256"] != sha256_bytes(canonical_json(request))
        or value["raw_response_sha256"] != response["raw_response_sha256"]
        or value["extraction_status"] != response["extraction_status"]
        or not isinstance(value["latency_seconds"], (int, float))
        or isinstance(value["latency_seconds"], bool)
        or value["latency_seconds"] <= 0
    ):
        raise RealWorkerError("operator usage receipt differs")
    if not isinstance(value["rendered_prompt_sha256"], str) or not HEX64.fullmatch(
        value["rendered_prompt_sha256"]
    ):
        raise RealWorkerError("operator rendered-prompt hash differs")
    token_values = [
        value["prompt_tokens"], value["completion_tokens"], value["total_tokens"]
    ]
    if any(
        item is not None
        and (isinstance(item, bool) or not isinstance(item, int) or item < 0)
        for item in token_values
    ):
        raise RealWorkerError("operator token accounting differs")
    if all(isinstance(item, int) and not isinstance(item, bool) for item in token_values):
        if token_values[0] + token_values[1] != token_values[2]:
            raise RealWorkerError("operator total token accounting differs")


def completed_progress(
    inflight: pathlib.Path,
    assignment: dict[str, Any],
    real_contract: dict[str, Any],
    description: str,
    count: int,
) -> tuple[list[str], int, int]:
    manifests: list[str] = []
    operator_calls = 0
    previous: dict[str, Any] | None = None
    for ordinal in range(count):
        step_dir = inflight / "steps" / f"step_{ordinal:03d}"
        manifests.append(validate_complete_step(step_dir, assignment["rollout_id"], ordinal))
        execution = validate_execution_receipt(
            checked_json(step_dir / "execution.json"), real_contract
        )
        search = validate_search_receipt(checked_json(step_dir / "dsearch.json"), real_contract)
        commitment = checked_json(step_dir / "dval_commitment.json")
        expected_commitment = {
            "schema_version": COMMITMENT_SCHEMA,
            "rollout_id": assignment["rollout_id"],
            "workspace_token": execution["workspace_token"],
            "task": assignment["task"],
            "execution_ordinal": ordinal,
        }
        if any(commitment.get(key) != value for key, value in expected_commitment.items()):
            raise RealWorkerError("completed-step sealed commitment identity differs")
        sealed_sha = commitment.get("sealed_label_receipt_sha256")
        if not isinstance(sealed_sha, str) or not HEX64.fullmatch(sealed_sha):
            raise RealWorkerError("completed-step sealed commitment hash differs")
        if ordinal == 0:
            operator = "none"
            code = (step_dir / "code.py").read_text(encoding="utf-8")
            if any((step_dir / name).exists() for name in (
                "operator_request.json", "operator_response.json", "operator_usage.json"
            )):
                raise RealWorkerError("warm-start step unexpectedly contains an operator call")
        else:
            if previous is None:
                raise RealWorkerError("continuation step lacks previous visible state")
            request = checked_json(step_dir / "operator_request.json")
            expected_request = build_operator_request(
                previous,
                real_contract,
                task_description=description,
                transition_index=ordinal,
                operator_seed=assignment["rollout_seed"] + ordinal,
            )
            if request != expected_request:
                raise RealWorkerError("completed-step operator request chain differs")
            response = validate_operator_response(
                checked_json(step_dir / "operator_response.json"), request, real_contract
            )
            usage = checked_json(step_dir / "operator_usage.json")
            validate_operator_usage(usage, request, response)
            operator_calls += response["operator_calls"]
            operator = response["operator"]
            code = response["code"]
        visible = validate_visible_step(checked_json(step_dir / "visible.json"), real_contract)
        expected_visible = bind_visible_step(
            execution,
            search,
            real_contract,
            stage="warm_start" if ordinal == 0 else "continuation",
            operator=operator,
            code=code,
            sealed_label_receipt_sha256=sealed_sha,
        )
        if visible != expected_visible:
            raise RealWorkerError("completed-step visible binding differs")
        previous = visible
    return manifests, operator_calls, count


def create_workspace(
    workspace_root: pathlib.Path, assignment: dict[str, Any], assignment_line_sha: str
) -> tuple[pathlib.Path, str]:
    workspace = workspace_root / assignment["rollout_id"]
    if workspace.exists() or workspace.is_symlink():
        raise RealWorkerError("fresh rollout workspace already exists")
    workspace.mkdir()
    (workspace / "candidate").mkdir()
    token = uuid.uuid4().hex
    atomic_json_new(workspace / "workspace_marker.json", {
        "schema_version": WORKSPACE_SCHEMA,
        "rollout_id": assignment["rollout_id"],
        "assignment_line_sha256": assignment_line_sha,
        "workspace_token": token,
        "created_utc": utc_now(),
        "fresh_directory_created": True,
    })
    return workspace, token


def validate_workspace_marker(
    workspace: pathlib.Path,
    assignment: dict[str, Any],
    assignment_line_sha: str,
    workspace_token: str,
) -> None:
    marker = checked_json(workspace / "workspace_marker.json")
    expected_keys = {
        "schema_version", "rollout_id", "assignment_line_sha256", "workspace_token",
        "created_utc", "fresh_directory_created",
    }
    if (
        set(marker) != expected_keys
        or marker["schema_version"] != WORKSPACE_SCHEMA
        or marker["rollout_id"] != assignment["rollout_id"]
        or marker["assignment_line_sha256"] != assignment_line_sha
        or marker["workspace_token"] != workspace_token
        or marker["fresh_directory_created"] is not True
    ):
        raise RealWorkerError("fresh-workspace marker differs")
    try:
        dt.datetime.fromisoformat(marker["created_utc"].replace("Z", "+00:00"))
    except (AttributeError, ValueError) as exc:
        raise RealWorkerError("fresh-workspace timestamp differs") from exc
    candidate = workspace / "candidate"
    if not candidate.is_dir() or candidate.is_symlink():
        raise RealWorkerError("candidate workspace directory differs")


def validate_result_object(
    result: dict[str, Any],
    assignment: dict[str, Any],
    assignment_line_sha: str,
    real_contract: dict[str, Any],
    real_contract_sha: str,
    state: dict[str, Any],
    steps: list[dict[str, Any]],
    usage: list[dict[str, Any]],
    candidate_wall_times: list[float],
) -> dict[str, Any]:
    if set(result) != RESULT_KEYS:
        raise RealWorkerError("real rollout result schema differs")
    expected = {
        "schema_version": RESULT_SCHEMA,
        "status": "COMPLETE_REAL_BALANCED_CONTINUATION_ROLLOUT",
        "rollout_id": assignment["rollout_id"],
        "global_order": assignment["global_order"],
        "block_id": assignment["block_id"],
        "block_replicate": assignment["block_replicate"],
        "anchor_id": assignment["anchor_id"],
        "task": assignment["task"],
        "sibling_id": assignment["sibling_id"],
        "source_run_id": assignment["source_run_id"],
        "source_commit": real_contract["source_commit"],
        "assignment_line_sha256": assignment_line_sha,
        "real_contract_sha256": real_contract_sha,
        "workspace_path": state["workspace_path"],
        "workspace_token": state["workspace_token"],
        "started_utc": state["started_utc"],
        "continuation_horizon": real_contract["continuation_horizon"],
        "execution_timeout_seconds": real_contract["execution_timeout_seconds"],
        "candidate_network_policy": "singularity-network-none",
        "candidate_execution_attempts": len(steps),
        "candidate_processes_started": sum(step["process_started"] for step in steps),
        "operator_calls": real_contract["continuation_horizon"],
        "operator_retry_count": 0,
        "candidate_retry_count": 0,
        "analyze_operator_calls": 0,
        "dtest_rows_read": 0,
        "visible_dsearch_utilities": [step["search_utility"] for step in steps],
        "sealed_dval_commitment_sha256s": [
            step["sealed_label_receipt_sha256"] for step in steps
        ],
        "api_usage": usage,
    }
    if any(result.get(key) != value for key, value in expected.items()):
        raise RealWorkerError("real rollout result identity/counters differ")
    walls = result["candidate_wall_time_seconds"]
    if (
        walls != candidate_wall_times
        or len(walls) != len(steps)
        or any(
            isinstance(value, bool)
            or not isinstance(value, (int, float))
            or value <= 0
            for value in walls
        )
    ):
        raise RealWorkerError("real rollout candidate wall times differ")
    try:
        started = dt.datetime.fromisoformat(result["started_utc"].replace("Z", "+00:00"))
        ended = dt.datetime.fromisoformat(result["ended_utc"].replace("Z", "+00:00"))
    except (AttributeError, ValueError) as exc:
        raise RealWorkerError("real rollout result timestamp differs") from exc
    if ended < started:
        raise RealWorkerError("real rollout ended before it started")
    if b"dval_score" in canonical_json(result) or b"dval_utility" in canonical_json(result):
        raise RealWorkerError("sealed D_val value leaked into worker result")
    return result


def validate_final_directory(
    root: pathlib.Path,
    assignment: dict[str, Any],
    assignment_line_sha: str,
    real_contract: dict[str, Any],
    real_contract_sha: str,
    code_vault_sha: str,
    description: str,
) -> dict[str, Any]:
    if not root.is_dir() or root.is_symlink():
        raise RealWorkerError("final rollout root differs")
    manifest = checked_json(root / "sha256_manifest.json")
    expected_manifest = recursive_hashes(root, {"sha256_manifest.json"})
    if manifest != expected_manifest:
        raise RealWorkerError("final rollout hash manifest differs")
    state = checked_json(root / "state.json")
    validate_state(
        state,
        assignment,
        assignment_line_sha,
        real_contract_sha,
        code_vault_sha,
        real_contract["continuation_horizon"],
    )
    if state["phase"] != "FINALIZED":
        raise RealWorkerError("final rollout state is not finalized")
    manifests, operator_calls, attempts = completed_progress(
        root,
        assignment,
        real_contract,
        description,
        real_contract["continuation_horizon"] + 1,
    )
    if (
        state["completed_step_manifest_sha256s"] != manifests
        or state["operator_calls"] != operator_calls
        or state["candidate_execution_attempts"] != attempts
    ):
        raise RealWorkerError("final rollout state counters differ")
    steps = [
        validate_visible_step(
            checked_json(root / "steps" / f"step_{ordinal:03d}" / "visible.json"),
            real_contract,
        )
        for ordinal in range(real_contract["continuation_horizon"] + 1)
    ]
    usage = [
        checked_json(root / "steps" / f"step_{ordinal:03d}" / "operator_usage.json")
        for ordinal in range(1, real_contract["continuation_horizon"] + 1)
    ]
    candidate_wall_times = [
        checked_json(root / "steps" / f"step_{ordinal:03d}" / "execution.json")[
            "wall_time_seconds"
        ]
        for ordinal in range(real_contract["continuation_horizon"] + 1)
    ]
    return validate_result_object(
        checked_json(root / "result.json"),
        assignment,
        assignment_line_sha,
        real_contract,
        real_contract_sha,
        state,
        steps,
        usage,
        candidate_wall_times,
    )


def run(args: argparse.Namespace) -> dict[str, Any]:
    assignment_root = pathlib.Path(args.assignment_result).resolve()
    code_vault_path = pathlib.Path(args.code_vault).resolve()
    real_contract_path = pathlib.Path(args.real_contract).resolve()
    split_root = pathlib.Path(args.split_root).resolve()
    container = pathlib.Path(args.container).resolve()
    hf_cache = pathlib.Path(args.hf_cache).resolve()
    nvfix_dir = pathlib.Path(args.nvfix_dir).resolve()
    output_root = require_new_root(args.output_root, "output root")
    workspace_root = require_new_root(args.workspace_root, "workspace root")
    sealed_root = require_new_root(args.sealed_root, "sealed root")
    require_disjoint_roots({
        "output": output_root,
        "workspace": workspace_root,
        "sealed": sealed_root,
        "split": split_root,
    })
    assignment, assignment_line_sha, legacy_contract = load_assignment(assignment_root, args.index)
    code_vault_sha, initial_code_raw = load_code_vault(code_vault_path, assignment)
    initial_code = initial_code_raw.decode("utf-8")
    real_raw = real_contract_path.read_bytes()
    if CREDENTIAL.search(real_raw):
        raise RealWorkerError("credential-shaped bytes in real contract")
    real_contract = validate_worker_contract(json.loads(real_raw))
    real_contract_sha = sha256_bytes(real_raw)
    repo = exact_git_source(real_contract["source_commit"])
    validate_contract_pair(legacy_contract, real_contract, split_root)
    if file_sha256(container) != real_contract["container_sha256"]:
        raise RealWorkerError("container hash differs from real contract")
    if not hf_cache.is_dir() or not nvfix_dir.is_dir():
        raise RealWorkerError("HF cache or NVIDIA compatibility directory is missing")
    if not (nvfix_dir / "libnvidia-nvvm.so.4").is_file():
        raise RealWorkerError("NVIDIA compatibility library is missing")
    public_task = split_root / "public" / assignment["task"]
    if not public_task.is_dir() or public_task.is_symlink():
        raise RealWorkerError("candidate public task root is missing or symlinked")
    description = task_description(repo, split_root, assignment["task"])

    final = output_root / assignment["rollout_id"]
    inflight = output_root / f".inflight-{assignment['rollout_id']}"
    if final.exists() or final.is_symlink():
        if inflight.exists() or inflight.is_symlink():
            raise RealWorkerError("both final and inflight rollout roots exist")
        result = validate_final_directory(
            final,
            assignment,
            assignment_line_sha,
            real_contract,
            real_contract_sha,
            code_vault_sha,
            description,
        )
        workspace = pathlib.Path(result["workspace_path"]).resolve()
        if workspace.parent != workspace_root or workspace.name != assignment["rollout_id"]:
            raise RealWorkerError("existing final workspace escaped the rollout root")
        validate_workspace_marker(
            workspace, assignment, assignment_line_sha, result["workspace_token"]
        )
        return result
    if not inflight.exists() and not inflight.is_symlink():
        inflight.mkdir()
        (inflight / "steps").mkdir()
        atomic_bytes(inflight / "real_contract.json", real_raw)
        workspace, token = create_workspace(workspace_root, assignment, assignment_line_sha)
        sealed_rollout = sealed_root / assignment["rollout_id"]
        if sealed_rollout.exists() or sealed_rollout.is_symlink():
            raise RealWorkerError("sealed rollout root already exists")
        sealed_rollout.mkdir()
        os.chmod(sealed_rollout, 0o700)
        state = initial_state(
            assignment, assignment_line_sha, real_contract_sha, code_vault_sha, workspace, token
        )
        atomic_json_new(inflight / "state.json", state)
    elif not inflight.is_dir() or inflight.is_symlink():
        raise RealWorkerError("inflight rollout root differs")
    state = checked_json(inflight / "state.json")
    validate_state(
        state,
        assignment,
        assignment_line_sha,
        real_contract_sha,
        code_vault_sha,
        real_contract["continuation_horizon"],
    )
    workspace = pathlib.Path(state["workspace_path"]).resolve()
    if workspace.parent != workspace_root or workspace.name != assignment["rollout_id"]:
        raise RealWorkerError("checkpoint workspace escaped the rollout root")
    validate_workspace_marker(
        workspace, assignment, assignment_line_sha, state["workspace_token"]
    )
    candidate_workspace = workspace / "candidate"
    sealed_rollout = sealed_root / assignment["rollout_id"]
    if not workspace.is_dir() or not sealed_rollout.is_dir():
        raise RealWorkerError("checkpoint workspace/sealed root is missing")

    if state["phase"] == "PENDING":
        ordinal = state["pending_execution_ordinal"]
        step_dir = inflight / "steps" / f"step_{ordinal:03d}"
        if not (step_dir / "step_manifest.json").is_file():
            raise RealWorkerError(
                "ambiguous PENDING paid action has no complete manifest; automatic retry forbidden"
            )
        manifests, operator_calls, candidate_attempts = completed_progress(
            inflight, assignment, real_contract, description, ordinal + 1
        )
        state["completed_step_manifest_sha256s"] = manifests
        state["operator_calls"] = operator_calls
        state["candidate_execution_attempts"] = candidate_attempts
        state["next_execution_ordinal"] = ordinal + 1
        state["pending_execution_ordinal"] = None
        state["phase"] = "READY"
        atomic_json_replace(inflight / "state.json", state)

    manifests, operator_calls, candidate_attempts = completed_progress(
        inflight,
        assignment,
        real_contract,
        description,
        state["next_execution_ordinal"],
    )
    if (
        state["completed_step_manifest_sha256s"] != manifests
        or state["operator_calls"] != operator_calls
        or state["candidate_execution_attempts"] != candidate_attempts
    ):
        raise RealWorkerError("worker checkpoint counters differ from durable completed steps")

    horizon = real_contract["continuation_horizon"]
    while state["next_execution_ordinal"] <= horizon:
        ordinal = state["next_execution_ordinal"]
        step_dir = inflight / "steps" / f"step_{ordinal:03d}"
        if step_dir.exists() or step_dir.is_symlink():
            raise RealWorkerError("uncommitted step directory already exists")
        step_dir.mkdir()
        state["phase"] = "PENDING"
        state["pending_execution_ordinal"] = ordinal
        atomic_json_replace(inflight / "state.json", state)

        if ordinal == 0:
            code = initial_code
            operator = "none"
            execution = execute_candidate(
                code=code, assignment=assignment, real_contract=real_contract, ordinal=ordinal,
                workspace=candidate_workspace, workspace_token=state["workspace_token"],
                step_dir=step_dir,
                public_task=public_task, container=container, hf_cache=hf_cache, nvfix_dir=nvfix_dir,
            )
        else:
            previous = validate_visible_step(
                checked_json(inflight / "steps" / f"step_{ordinal - 1:03d}" / "visible.json"),
                real_contract,
            )
            request = build_operator_request(
                previous, real_contract, task_description=description,
                transition_index=ordinal, operator_seed=assignment["rollout_seed"] + ordinal,
            )
            request_path = step_dir / "operator_request.json"
            response_path = step_dir / "operator_response.json"
            usage_path = step_dir / "operator_usage.json"
            atomic_json_new(request_path, request)
            run_sidecar(
                step_dir, "operator",
                [
                    sys.executable, "-m", "phase1.balanced_continuation_operator_entry",
                    "--contract", str(inflight / "real_contract.json"),
                    "--request", str(request_path), "--response", str(response_path),
                    "--usage-receipt", str(usage_path),
                ],
                rollout_id=assignment["rollout_id"], ordinal=ordinal,
                timeout_seconds=real_contract["operator_timeout_seconds"],
                include_operator_credential=True,
            )
            response = validate_operator_response(
                checked_json(response_path), request, real_contract
            )
            operator = response["operator"]
            code = response["code"]
            if response["extraction_status"] == "invalid_format":
                execution = invalid_format_execution(
                    code, assignment, real_contract, ordinal, state["workspace_token"], step_dir
                )
            else:
                execution = execute_candidate(
                    code=code, assignment=assignment, real_contract=real_contract, ordinal=ordinal,
                    workspace=candidate_workspace, workspace_token=state["workspace_token"],
                    step_dir=step_dir,
                    public_task=public_task, container=container, hf_cache=hf_cache,
                    nvfix_dir=nvfix_dir,
                )
        search, commitment = score_step(
            assignment=assignment, real_contract=real_contract, ordinal=ordinal,
            workspace_token=state["workspace_token"], step_dir=step_dir,
            split_root=split_root, sealed_rollout_root=sealed_rollout,
        )
        visible = bind_visible_step(
            execution, search, real_contract,
            stage="warm_start" if ordinal == 0 else "continuation",
            operator=operator, code=code,
            sealed_label_receipt_sha256=commitment["sealed_label_receipt_sha256"],
        )
        atomic_json_new(step_dir / "visible.json", visible)
        finalize_step(step_dir, assignment, ordinal)
        manifests, operator_calls, candidate_attempts = completed_progress(
            inflight, assignment, real_contract, description, ordinal + 1
        )
        state["completed_step_manifest_sha256s"] = manifests
        state["operator_calls"] = operator_calls
        state["candidate_execution_attempts"] = candidate_attempts
        state["next_execution_ordinal"] = ordinal + 1
        state["pending_execution_ordinal"] = None
        state["phase"] = "READY"
        atomic_json_replace(inflight / "state.json", state)

    steps = [
        validate_visible_step(
            checked_json(inflight / "steps" / f"step_{ordinal:03d}" / "visible.json"),
            real_contract,
        )
        for ordinal in range(horizon + 1)
    ]
    usage = []
    for ordinal in range(1, horizon + 1):
        usage.append(checked_json(inflight / "steps" / f"step_{ordinal:03d}" / "operator_usage.json"))
    candidate_wall_times = [
        checked_json(inflight / "steps" / f"step_{ordinal:03d}" / "execution.json")[
            "wall_time_seconds"
        ]
        for ordinal in range(horizon + 1)
    ]
    result_path = inflight / "result.json"
    if result_path.exists() or result_path.is_symlink():
        result = checked_json(result_path)
    else:
        if state["phase"] == "FINALIZED":
            raise RealWorkerError("finalized checkpoint is missing its durable result")
        result = {
            "schema_version": RESULT_SCHEMA,
            "status": "COMPLETE_REAL_BALANCED_CONTINUATION_ROLLOUT",
            "rollout_id": assignment["rollout_id"],
            "global_order": assignment["global_order"],
            "block_id": assignment["block_id"],
            "block_replicate": assignment["block_replicate"],
            "anchor_id": assignment["anchor_id"],
            "task": assignment["task"],
            "sibling_id": assignment["sibling_id"],
            "source_run_id": assignment["source_run_id"],
            "source_commit": real_contract["source_commit"],
            "assignment_line_sha256": assignment_line_sha,
            "real_contract_sha256": real_contract_sha,
            "workspace_path": str(workspace),
            "workspace_token": state["workspace_token"],
            "started_utc": state["started_utc"],
            "ended_utc": utc_now(),
            "continuation_horizon": horizon,
            "execution_timeout_seconds": real_contract["execution_timeout_seconds"],
            "candidate_network_policy": "singularity-network-none",
            "candidate_execution_attempts": state["candidate_execution_attempts"],
            "candidate_processes_started": sum(step["process_started"] for step in steps),
            "operator_calls": state["operator_calls"],
            "operator_retry_count": 0,
            "candidate_retry_count": 0,
            "analyze_operator_calls": 0,
            "dtest_rows_read": 0,
            "candidate_wall_time_seconds": candidate_wall_times,
            "visible_dsearch_utilities": [step["search_utility"] for step in steps],
            "sealed_dval_commitment_sha256s": [
                step["sealed_label_receipt_sha256"] for step in steps
            ],
            "api_usage": usage,
        }
        atomic_json_new(result_path, result)
    validate_result_object(
        result,
        assignment,
        assignment_line_sha,
        real_contract,
        real_contract_sha,
        state,
        steps,
        usage,
        candidate_wall_times,
    )
    if state["phase"] != "FINALIZED":
        state["phase"] = "FINALIZED"
        atomic_json_replace(inflight / "state.json", state)
    validate_state(
        state,
        assignment,
        assignment_line_sha,
        real_contract_sha,
        code_vault_sha,
        horizon,
    )
    manifest_path = inflight / "sha256_manifest.json"
    expected_manifest = recursive_hashes(inflight, {"sha256_manifest.json"})
    if manifest_path.exists() or manifest_path.is_symlink():
        if checked_json(manifest_path) != expected_manifest:
            raise RealWorkerError("inflight final hash manifest differs")
    else:
        atomic_json_new(manifest_path, expected_manifest)
    os.replace(inflight, final)
    if os.name == "posix":
        directory_fd = os.open(output_root, os.O_RDONLY | getattr(os, "O_DIRECTORY", 0))
        try:
            os.fsync(directory_fd)
        finally:
            os.close(directory_fd)
    return validate_final_directory(
        final,
        assignment,
        assignment_line_sha,
        real_contract,
        real_contract_sha,
        code_vault_sha,
        description,
    )


def parser() -> argparse.ArgumentParser:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--assignment-result", required=True)
    ap.add_argument("--code-vault", required=True)
    ap.add_argument("--real-contract", required=True)
    ap.add_argument("--split-root", required=True)
    ap.add_argument("--index", required=True, type=int)
    ap.add_argument("--output-root", required=True)
    ap.add_argument("--workspace-root", required=True)
    ap.add_argument("--sealed-root", required=True)
    ap.add_argument("--container", required=True)
    ap.add_argument("--hf-cache", required=True)
    ap.add_argument("--nvfix-dir", required=True)
    return ap


def main() -> int:
    try:
        result = run(parser().parse_args())
    except (
        RealWorkerError,
        RealContractError,
        ScoreError,
        WorkerError,
        OSError,
        UnicodeError,
        json.JSONDecodeError,
        subprocess.SubprocessError,
    ) as exc:
        print(f"REAL_BALANCED_WORKER_ERROR: {exc}", file=sys.stderr)
        return 2
    print(canonical_json(result).decode("utf-8"))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
