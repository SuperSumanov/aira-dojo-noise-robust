"""Zero-GPU process-boundary smoke for the future real continuation adapter.

This is deliberately a mock backend.  It proves that the orchestration can keep candidate
execution, D_search scoring, sealed D_val scoring, and the one-shot operator in separate
processes while producing the frozen real-adapter receipts.  It does not prove OS-level
private-data isolation or any scientific effect.
"""

from __future__ import annotations

import argparse
import csv
import json
import os
import pathlib
import re
import stat
import subprocess
import sys
import tempfile
import time
from typing import Any

from phase1.balanced_continuation_real_contract import (
    EXECUTION_RECEIPT_SCHEMA,
    OPERATOR_RESPONSE_SCHEMA,
    SEARCH_RECEIPT_SCHEMA,
    SEALED_LABEL_SCHEMA,
    WORKER_CONTRACT_SCHEMA,
    bind_visible_step,
    build_operator_request,
    canonical_json,
    sha256_bytes,
    validate_execution_receipt,
    validate_operator_response,
    validate_search_receipt,
    validate_worker_contract,
)


MOCK_SCHEMA = "balanced-continuation-real-adapter-mock-v1"
COMMITMENT_SCHEMA = "balanced-continuation-sealed-commitment-v1"
HEX40 = re.compile(r"[0-9a-f]{40}\Z")
CREDENTIAL = re.compile(
    rb"(?:^|[^A-Za-z0-9])(?:sk-[A-Za-z0-9._-]{16,}|hf_[A-Za-z0-9]{16,}|"
    rb"gh[pousr]_[A-Za-z0-9]{16,}|AKIA[0-9A-Z]{16}|AIza[0-9A-Za-z_-]{30,}|"
    rb"Bearer[ \t]+[A-Za-z0-9._-]{20,}|-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----)"
)


class MockAdapterError(RuntimeError):
    pass


def atomic_bytes(path: pathlib.Path, raw: bytes, mode: int | None = None) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, temporary_name = tempfile.mkstemp(prefix=f".{path.name}.", suffix=".tmp", dir=path.parent)
    temporary = pathlib.Path(temporary_name)
    try:
        with os.fdopen(fd, "wb") as handle:
            handle.write(raw)
            handle.flush()
            os.fsync(handle.fileno())
        if mode is not None:
            os.chmod(temporary, mode)
        os.replace(temporary, path)
        if mode is not None:
            os.chmod(path, mode)
    finally:
        if temporary.exists():
            temporary.unlink()


def atomic_json(path: pathlib.Path, value: Any, mode: int | None = None) -> None:
    atomic_bytes(path, canonical_json(value) + b"\n", mode=mode)


def checked_json(path: pathlib.Path) -> dict[str, Any]:
    raw = path.read_bytes()
    if CREDENTIAL.search(raw):
        raise MockAdapterError(f"credential-shaped bytes refused: {path.name}")
    try:
        value = json.loads(raw)
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise MockAdapterError(f"invalid JSON: {path}") from exc
    if not isinstance(value, dict):
        raise MockAdapterError(f"expected JSON object: {path}")
    return value


def require_new_absolute_dir(path_text: str, label: str) -> pathlib.Path:
    path = pathlib.Path(path_text)
    if not path.is_absolute():
        raise MockAdapterError(f"{label} must be absolute")
    if path.exists() or path.is_symlink():
        raise MockAdapterError(f"{label} must not pre-exist")
    path.mkdir(parents=True)
    return path.resolve()


def clean_subprocess_env() -> dict[str, str]:
    allowed = {
        "PATH",
        "SYSTEMROOT",
        "WINDIR",
        "TEMP",
        "TMP",
        "TMPDIR",
        "LANG",
        "LC_ALL",
        "LD_LIBRARY_PATH",
    }
    env = {key: value for key, value in os.environ.items() if key in allowed}
    env["PYTHONPATH"] = str(pathlib.Path(__file__).resolve().parents[1])
    return env


def verify_exact_git_source(source_commit: str) -> None:
    repo = pathlib.Path(__file__).resolve().parents[1]
    head = subprocess.run(
        ["git", "rev-parse", "HEAD"],
        cwd=repo,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=True,
    ).stdout.decode("ascii").strip()
    if head != source_commit:
        raise MockAdapterError(f"source commit differs: expected {source_commit}, found {head}")
    status_output = subprocess.run(
        ["git", "status", "--porcelain"],
        cwd=repo,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=True,
    ).stdout
    if status_output:
        raise MockAdapterError("formal mock smoke requires an exact clean worktree")


def artifact_prediction(code_sha: str) -> float:
    return int(code_sha[:12], 16) / float(16**12 - 1)


def run_candidate(args: argparse.Namespace) -> None:
    started = time.monotonic()
    workspace = pathlib.Path(args.workspace).resolve()
    public_root = pathlib.Path(args.public_root).resolve()
    code_path = pathlib.Path(args.code).resolve()
    receipt_path = pathlib.Path(args.receipt).resolve()
    artifact_path = pathlib.Path(args.artifact).resolve()
    if not workspace.is_dir() or not public_root.is_dir() or not code_path.is_file():
        raise MockAdapterError("candidate input path is absent")
    if workspace not in artifact_path.parents or workspace not in code_path.parents:
        raise MockAdapterError("candidate code/artifact escaped its rollout workspace")
    if artifact_path.exists() or receipt_path.exists():
        raise MockAdapterError("candidate output already exists")
    public_entries = list(public_root.iterdir())
    if not public_entries or any(stat.S_IMODE(path.stat().st_mode) & 0o222 for path in public_entries):
        raise MockAdapterError("mock public dataset is not read-only")
    code = code_path.read_bytes()
    code_sha = sha256_bytes(code)
    prediction = artifact_prediction(code_sha)
    artifact = f"id,prediction\n0,{prediction:.17g}\n".encode("ascii")
    atomic_bytes(artifact_path, artifact)
    terminal = "MOCK_PUBLIC_CANDIDATE_OK\n"
    receipt = {
        "schema_version": EXECUTION_RECEIPT_SCHEMA,
        "rollout_id": args.rollout_id,
        "workspace_token": args.workspace_token,
        "task": args.task,
        "execution_ordinal": args.ordinal,
        "code_sha256": code_sha,
        "execution_status": "ok",
        "process_started": True,
        "candidate_execution_attempted": True,
        "exit_code": 0,
        "timed_out": False,
        "wall_time_seconds": max(time.monotonic() - started, 1e-6),
        "terminal_output": terminal,
        "terminal_output_sha256": sha256_bytes(terminal.encode("utf-8")),
        "artifact_sha256": sha256_bytes(artifact),
        "public_data_read_only": True,
        "private_paths_mounted": False,
        "retry_count": 0,
    }
    atomic_json(receipt_path, receipt)


def read_prediction(artifact_path: pathlib.Path) -> float:
    with artifact_path.open("r", encoding="ascii", newline="") as handle:
        rows = list(csv.DictReader(handle))
    if len(rows) != 1 or set(rows[0]) != {"id", "prediction"} or rows[0]["id"] != "0":
        raise MockAdapterError("mock submission schema differs")
    value = float(rows[0]["prediction"])
    if not 0 <= value <= 1:
        raise MockAdapterError("mock prediction is outside [0,1]")
    return value


def score_from_label(artifact_path: pathlib.Path, label_path: pathlib.Path) -> float:
    prediction = read_prediction(artifact_path)
    label = checked_json(label_path)
    if set(label) != {"target"} or isinstance(label["target"], bool):
        raise MockAdapterError("mock private label schema differs")
    return 1.0 - abs(prediction - float(label["target"]))


def run_search_scorer(args: argparse.Namespace) -> None:
    contract = validate_worker_contract(checked_json(pathlib.Path(args.contract)))
    artifact_path = pathlib.Path(args.artifact).resolve()
    artifact_sha = sha256_bytes(artifact_path.read_bytes())
    score = score_from_label(artifact_path, pathlib.Path(args.label).resolve())
    receipt = {
        "schema_version": SEARCH_RECEIPT_SCHEMA,
        "rollout_id": args.rollout_id,
        "workspace_token": args.workspace_token,
        "task": args.task,
        "execution_ordinal": args.ordinal,
        "artifact_sha256": artifact_sha,
        "submission_valid": True,
        "dsearch_score": score,
        "search_utility": score,
        "orientation": 1,
        "split_manifest_sha256": contract["split_manifest_sha256_opaque"],
        "evaluator_executable_sha256": contract["search_evaluator_executable_sha256"],
        "grade_return_code": 0,
        "private_bytes_exposed_to_candidate": 0,
        "dtest_rows_read": 0,
    }
    validate_search_receipt(receipt, contract)
    atomic_json(pathlib.Path(args.receipt), receipt)


def run_label_sealer(args: argparse.Namespace) -> None:
    contract = validate_worker_contract(checked_json(pathlib.Path(args.contract)))
    artifact_path = pathlib.Path(args.artifact).resolve()
    artifact_sha = sha256_bytes(artifact_path.read_bytes())
    score = score_from_label(artifact_path, pathlib.Path(args.label).resolve())
    receipt = {
        "schema_version": SEALED_LABEL_SCHEMA,
        "rollout_id": args.rollout_id,
        "workspace_token": args.workspace_token,
        "task": args.task,
        "execution_ordinal": args.ordinal,
        "artifact_sha256": artifact_sha,
        "submission_valid": True,
        "dval_score": score,
        "dval_utility": score,
        "orientation": 1,
        "split_manifest_sha256": contract["split_manifest_sha256_opaque"],
        "evaluator_executable_sha256": contract["sealed_label_evaluator_executable_sha256"],
        "grade_return_code": 0,
        "private_bytes_exposed_to_candidate": 0,
        "dtest_rows_read": 0,
        "file_mode": 0o600,
    }
    sealed_path = pathlib.Path(args.sealed_receipt).resolve()
    if sealed_path.exists():
        raise MockAdapterError("sealed D_val receipt already exists")
    atomic_json(sealed_path, receipt, mode=0o600)
    commitment = {
        "schema_version": COMMITMENT_SCHEMA,
        "rollout_id": args.rollout_id,
        "workspace_token": args.workspace_token,
        "task": args.task,
        "execution_ordinal": args.ordinal,
        "sealed_label_receipt_sha256": sha256_bytes(sealed_path.read_bytes()),
    }
    sys.stdout.buffer.write(canonical_json(commitment) + b"\n")


def run_operator(args: argparse.Namespace) -> None:
    contract = validate_worker_contract(checked_json(pathlib.Path(args.contract)))
    request = checked_json(pathlib.Path(args.request))
    operator = request["operator"]
    code = request["previous_code"] + (
        f"\n# deterministic mock {operator} transition {request['transition_index']}\n"
    )
    raw_response = f"```python\n{code}```"
    response = {
        "schema_version": OPERATOR_RESPONSE_SCHEMA,
        "rollout_id": request["rollout_id"],
        "transition_index": request["transition_index"],
        "operator": operator,
        "request_sha256": sha256_bytes(canonical_json(request)),
        "raw_response_sha256": sha256_bytes(raw_response.encode("utf-8")),
        "extraction_status": "ok",
        "code": code,
        "code_sha256": sha256_bytes(code.encode("utf-8")),
        "provider_request_id": f"mock-{request['rollout_id'][:12]}-{request['transition_index']}",
        "operator_calls": 1,
        "retry_count": 0,
    }
    validate_operator_response(response, request, contract)
    atomic_json(pathlib.Path(args.response), response)


def run_process(
    root: pathlib.Path,
    records: list[dict[str, Any]],
    label: str,
    command: list[str],
) -> subprocess.CompletedProcess[bytes]:
    ordinal = len(records)
    before = time.monotonic()
    completed = subprocess.run(
        command,
        cwd=pathlib.Path(__file__).resolve().parents[1],
        env=clean_subprocess_env(),
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        timeout=30,
        check=False,
    )
    atomic_bytes(root / "logs" / f"{ordinal:03d}_{label}.stdout", completed.stdout)
    atomic_bytes(root / "logs" / f"{ordinal:03d}_{label}.stderr", completed.stderr)
    record = {
        "ordinal": ordinal,
        "label": label,
        "command": command,
        "return_code": completed.returncode,
        "wall_time_seconds": max(time.monotonic() - before, 1e-6),
    }
    records.append(record)
    atomic_json(root / "process_records.json", records)
    if completed.returncode != 0:
        raise MockAdapterError(f"mock sidecar {label} failed with rc={completed.returncode}")
    return completed


def run_smoke(args: argparse.Namespace) -> None:
    if not isinstance(args.source_commit, str) or not HEX40.fullmatch(args.source_commit):
        raise MockAdapterError("source_commit must be a 40-character lowercase Git SHA")
    if not getattr(args, "test_fixture_mode", False):
        verify_exact_git_source(args.source_commit)
    root = require_new_absolute_dir(args.output, "mock output")
    for name in (
        "public",
        "private_fixture",
        "workspace",
        "receipts",
        "sealed",
        "commitments",
        "operator",
        "logs",
    ):
        (root / name).mkdir()
    public_feature = root / "public" / "features.csv"
    atomic_bytes(public_feature, b"id,feature\n0,1\n")
    os.chmod(public_feature, 0o444)
    atomic_json(root / "private_fixture" / "dsearch.json", {"target": 0.25}, mode=0o600)
    atomic_json(root / "private_fixture" / "dval.json", {"target": 0.75}, mode=0o600)
    split_manifest = {
        "schema_version": "mock-80-10-10-split-manifest-v1",
        "role": "process-boundary-fixture-only",
        "dtest_materialized": False,
    }
    atomic_json(root / "split_manifest.json", split_manifest)
    executable_sha = sha256_bytes(pathlib.Path(__file__).read_bytes())
    logical_public_root = str((root / "public").resolve()) if os.name != "nt" else "/mock/public"
    contract = {
        "schema_version": WORKER_CONTRACT_SCHEMA,
        "backend": "aira-dojo-external-v1",
        "source_commit": args.source_commit,
        "container_sha256": sha256_bytes(b"mock-no-container"),
        "operator_config_sha256": sha256_bytes(b"mock-one-shot-operator"),
        "prompt_sha256": sha256_bytes(b"mock-fixed-prompt"),
        "public_dataset_contract_sha256": sha256_bytes(public_feature.read_bytes()),
        "split_manifest_sha256_opaque": sha256_bytes(canonical_json(split_manifest) + b"\n"),
        "search_evaluator_executable_sha256": executable_sha,
        "sealed_label_evaluator_executable_sha256": executable_sha,
        "public_data_root": logical_public_root,
        "continuation_horizon": 1,
        "operator_timeout_seconds": 30,
        "execution_timeout_seconds": 30,
        "evaluator_timeout_seconds": 30,
        "operator_policy": "debug_if_buggy_else_improve",
        "operator_calls_per_transition": 1,
        "operator_retry_count": 0,
        "execution_retry_count": 0,
        "analyze_operator_calls": 0,
        "workspace_policy": "fresh_per_rollout",
        "candidate_mount_policy": "public_read_only_no_private",
        "score_visibility": "D_search_only",
        "sealed_label_policy": "D_val_external_mode_0600",
        "split_policy": "80/10/10_D_train_D_search_D_val",
        "dtest_policy": "never_read",
    }
    validate_worker_contract(contract)
    atomic_json(root / "contract.json", contract)
    rollout_id = sha256_bytes(f"mock|{args.source_commit}|rollout-0".encode("ascii"))
    workspace_token = sha256_bytes(f"workspace|{rollout_id}".encode("ascii"))[:32]
    workspace = root / "workspace" / f"rollout-{workspace_token}"
    workspace.mkdir()
    initial_code = "# mock warm-start candidate\nVALUE = 1\n"
    code = initial_code
    records: list[dict[str, Any]] = []
    script = str(pathlib.Path(__file__).resolve())
    python = sys.executable
    for ordinal in range(2):
        code_path = workspace / f"code_{ordinal:03d}.py"
        atomic_bytes(code_path, code.encode("utf-8"))
        artifact_path = workspace / f"submission_{ordinal:03d}.csv"
        execution_path = root / "receipts" / f"execution_{ordinal:03d}.json"
        search_path = root / "receipts" / f"dsearch_{ordinal:03d}.json"
        sealed_path = root / "sealed" / f"dval_{ordinal:03d}.json"
        base_identity = [
            "--rollout-id",
            rollout_id,
            "--workspace-token",
            workspace_token,
            "--task",
            "mock-task",
            "--ordinal",
            str(ordinal),
        ]
        run_process(
            root,
            records,
            f"candidate_{ordinal:03d}",
            [
                python,
                script,
                "candidate",
                *base_identity,
                "--workspace",
                str(workspace),
                "--public-root",
                str(root / "public"),
                "--code",
                str(code_path),
                "--artifact",
                str(artifact_path),
                "--receipt",
                str(execution_path),
            ],
        )
        execution = validate_execution_receipt(checked_json(execution_path), contract)
        run_process(
            root,
            records,
            f"dsearch_{ordinal:03d}",
            [
                python,
                script,
                "search",
                *base_identity,
                "--contract",
                str(root / "contract.json"),
                "--artifact",
                str(artifact_path),
                "--label",
                str(root / "private_fixture" / "dsearch.json"),
                "--receipt",
                str(search_path),
            ],
        )
        search = validate_search_receipt(checked_json(search_path), contract)
        completed = run_process(
            root,
            records,
            f"dval_sealer_{ordinal:03d}",
            [
                python,
                script,
                "seal",
                *base_identity,
                "--contract",
                str(root / "contract.json"),
                "--artifact",
                str(artifact_path),
                "--label",
                str(root / "private_fixture" / "dval.json"),
                "--sealed-receipt",
                str(sealed_path),
            ],
        )
        if CREDENTIAL.search(completed.stdout):
            raise MockAdapterError("credential-shaped bytes in sealer commitment")
        commitment = json.loads(completed.stdout)
        expected_commitment_keys = {
            "schema_version",
            "rollout_id",
            "workspace_token",
            "task",
            "execution_ordinal",
            "sealed_label_receipt_sha256",
        }
        if not isinstance(commitment, dict) or set(commitment) != expected_commitment_keys:
            raise MockAdapterError("sealed commitment schema differs")
        if commitment["schema_version"] != COMMITMENT_SCHEMA:
            raise MockAdapterError("sealed commitment version differs")
        atomic_json(root / "commitments" / f"sealed_{ordinal:03d}.json", commitment)
        visible = bind_visible_step(
            execution,
            search,
            contract,
            stage="warm_start" if ordinal == 0 else "continuation",
            operator="none" if ordinal == 0 else "improve",
            code=code,
            sealed_label_receipt_sha256=commitment["sealed_label_receipt_sha256"],
        )
        atomic_json(root / "receipts" / f"visible_{ordinal:03d}.json", visible)
        if ordinal == 0:
            request = build_operator_request(
                visible,
                contract,
                task_description="Synthetic public-only mock task.",
                transition_index=1,
                operator_seed=1729,
            )
            request_path = root / "operator" / "request_001.json"
            response_path = root / "operator" / "response_001.json"
            atomic_json(request_path, request)
            run_process(
                root,
                records,
                "operator_001",
                [
                    python,
                    script,
                    "operator",
                    "--contract",
                    str(root / "contract.json"),
                    "--request",
                    str(request_path),
                    "--response",
                    str(response_path),
                ],
            )
            response = validate_operator_response(checked_json(response_path), request, contract)
            code = response["code"]
    summary = {
        "schema_version": MOCK_SCHEMA,
        "source_commit": args.source_commit,
        "rollout_id": rollout_id,
        "workspace_token": workspace_token,
        "candidate_processes": 2,
        "dsearch_processes": 2,
        "dval_sealer_processes": 2,
        "operator_processes": 1,
        "operator_calls": 1,
        "retry_count": 0,
        "analyze_calls": 0,
        "sealed_files_opened_by_worker": 0,
        "gpu_jobs": 0,
        "api_calls": 0,
        "scientific_outcome_claimed": False,
        "process_record_count": len(records),
    }
    atomic_json(root / "summary.json", summary)


def parser() -> argparse.ArgumentParser:
    result = argparse.ArgumentParser()
    sub = result.add_subparsers(dest="command", required=True)
    run = sub.add_parser("run")
    run.add_argument("--output", required=True)
    run.add_argument("--source-commit", required=True)
    common = argparse.ArgumentParser(add_help=False)
    common.add_argument("--rollout-id", required=True)
    common.add_argument("--workspace-token", required=True)
    common.add_argument("--task", required=True)
    common.add_argument("--ordinal", required=True, type=int)
    candidate = sub.add_parser("candidate", parents=[common])
    candidate.add_argument("--workspace", required=True)
    candidate.add_argument("--public-root", required=True)
    candidate.add_argument("--code", required=True)
    candidate.add_argument("--artifact", required=True)
    candidate.add_argument("--receipt", required=True)
    search = sub.add_parser("search", parents=[common])
    search.add_argument("--contract", required=True)
    search.add_argument("--artifact", required=True)
    search.add_argument("--label", required=True)
    search.add_argument("--receipt", required=True)
    seal = sub.add_parser("seal", parents=[common])
    seal.add_argument("--contract", required=True)
    seal.add_argument("--artifact", required=True)
    seal.add_argument("--label", required=True)
    seal.add_argument("--sealed-receipt", required=True)
    operator = sub.add_parser("operator")
    operator.add_argument("--contract", required=True)
    operator.add_argument("--request", required=True)
    operator.add_argument("--response", required=True)
    return result


def main() -> None:
    args = parser().parse_args()
    if args.command == "run":
        run_smoke(args)
    elif args.command == "candidate":
        run_candidate(args)
    elif args.command == "search":
        run_search_scorer(args)
    elif args.command == "seal":
        run_label_sealer(args)
    elif args.command == "operator":
        run_operator(args)
    else:
        raise MockAdapterError("unsupported command")


if __name__ == "__main__":
    main()
