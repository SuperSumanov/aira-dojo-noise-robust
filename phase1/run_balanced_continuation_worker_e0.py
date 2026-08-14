"""Run the full 24-rollout synthetic balanced-continuation worker gate.

This is an engineering gate only: it uses a deterministic synthetic backend, no GPU,
no network API, and no scientific outcomes.  Every production-facing component is invoked
through its CLI so exit codes and stdout/stderr are archived before the collection closes.
"""

from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import json
import os
import pathlib
import re
import subprocess
import sys
import tempfile
import time
import traceback
from typing import Any


HEX40 = re.compile(r"[0-9a-f]{40}\Z")
CREDENTIAL = re.compile(
    rb"(?:^|[^A-Za-z0-9])(?:sk-[A-Za-z0-9._-]{16,}|hf_[A-Za-z0-9]{16,}|"
    rb"gh[pousr]_[A-Za-z0-9]{16,}|AKIA[0-9A-Z]{16}|AIza[0-9A-Za-z_-]{30,}|"
    rb"Bearer[ \t]+[A-Za-z0-9._-]{20,}|-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----)"
)


class E0Error(RuntimeError):
    pass


def utc_now() -> str:
    return dt.datetime.now(dt.timezone.utc).isoformat(timespec="microseconds").replace(
        "+00:00", "Z"
    )


def canonical_json(value: Any) -> bytes:
    return json.dumps(
        value, sort_keys=True, separators=(",", ":"), ensure_ascii=False, allow_nan=False
    ).encode("utf-8")


def sha256_bytes(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def atomic_bytes(path: pathlib.Path, raw: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, temporary_name = tempfile.mkstemp(
        prefix=f".{path.name}.", suffix=".tmp", dir=path.parent
    )
    temporary = pathlib.Path(temporary_name)
    try:
        with os.fdopen(fd, "wb") as handle:
            handle.write(raw)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary, path)
    finally:
        if temporary.exists():
            temporary.unlink()


def atomic_json(path: pathlib.Path, value: Any) -> None:
    atomic_bytes(path, canonical_json(value) + b"\n")


def write_jsonl(path: pathlib.Path, rows: list[dict[str, Any]]) -> None:
    atomic_bytes(path, b"".join(canonical_json(row) + b"\n" for row in rows))


def git_check(repo: pathlib.Path, expected_commit: str) -> None:
    head = subprocess.run(
        ["git", "rev-parse", "HEAD"],
        cwd=repo,
        check=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    ).stdout.decode("ascii").strip()
    if head != expected_commit:
        raise E0Error(f"source commit differs: expected {expected_commit}, found {head}")
    status = subprocess.run(
        ["git", "status", "--porcelain"],
        cwd=repo,
        check=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    ).stdout
    if status:
        raise E0Error("formal E0 requires an exact clean worktree")


def fixture_rows() -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    anchors: list[dict[str, Any]] = []
    vault: list[dict[str, Any]] = []
    for task_index in range(2):
        task = f"synthetic-task-{task_index}"
        for anchor_index in range(2):
            anchor_id = f"synthetic-anchor-{task_index}-{anchor_index}"
            anchor_contract = sha256_bytes(
                f"E0|anchor|{task}|{anchor_id}|fixed-parent-context".encode("utf-8")
            )
            for sibling_index in range(3):
                sibling_id = f"synthetic-sibling-{task_index}-{anchor_index}-{sibling_index}"
                code = (
                    f"# deterministic balanced-continuation E0 candidate\n"
                    f"TASK = {task!r}\nANCHOR = {anchor_id!r}\n"
                    f"SIBLING = {sibling_id!r}\nprint(TASK, ANCHOR, SIBLING)\n"
                )
                code_sha = sha256_bytes(code.encode("utf-8"))
                anchors.append(
                    {
                        "anchor_id": anchor_id,
                        "task": task,
                        "source_run_id": f"synthetic-source-run-{task_index}-{anchor_index}",
                        "parent_id": f"synthetic-parent-{task_index}-{anchor_index}",
                        "sibling_id": sibling_id,
                        "code_sha256": code_sha,
                        "anchor_contract_sha256": anchor_contract,
                    }
                )
                vault.append(
                    {"sibling_id": sibling_id, "code": code, "code_sha256": code_sha}
                )
    return anchors, vault


def synthetic_outcomes(global_order: int) -> list[dict[str, Any]]:
    patterns = [
        [
            {"status": "ok", "utility": 0.2, "is_buggy": False, "wall_time_ms": 10},
            {"status": "timeout", "utility": None, "is_buggy": True, "wall_time_ms": 120000},
            {"status": "ok", "utility": 0.6, "is_buggy": False, "wall_time_ms": 12},
        ],
        [
            {"status": "invalid", "utility": None, "is_buggy": True, "wall_time_ms": 4},
            {"status": "ok", "utility": 0.4, "is_buggy": False, "wall_time_ms": 9},
            {"status": "ok", "utility": 0.3, "is_buggy": False, "wall_time_ms": 8},
        ],
        [
            {"status": "ok", "utility": 0.7, "is_buggy": False, "wall_time_ms": 11},
            {"status": "ok", "utility": 0.65, "is_buggy": False, "wall_time_ms": 13},
            {"status": "ok", "utility": 0.8, "is_buggy": False, "wall_time_ms": 15},
        ],
        [
            {"status": "ok", "utility": 0.4, "is_buggy": False, "wall_time_ms": 7},
            {"status": "invalid", "utility": None, "is_buggy": True, "wall_time_ms": 5},
            {"status": "timeout", "utility": None, "is_buggy": True, "wall_time_ms": 120000},
        ],
    ]
    return patterns[global_order % len(patterns)]


def run(args: argparse.Namespace) -> dict[str, Any]:
    repo = pathlib.Path(__file__).resolve().parents[1]
    output = pathlib.Path(args.output)
    if not output.is_absolute():
        raise E0Error("output must be an absolute path")
    output = output.resolve()
    if output.exists() or output.is_symlink():
        raise E0Error("output must not pre-exist")
    if not isinstance(args.source_commit, str) or not HEX40.fullmatch(args.source_commit):
        raise E0Error("source_commit must be a 40-character lowercase Git SHA")
    git_check(repo, args.source_commit)

    output.mkdir(parents=True)
    source = output / "source"
    assignment = output / "assignment"
    workers = output / "workers"
    workspaces = output / "workspaces"
    receipts = output / "worker_receipts"
    logs = output / "logs"
    for path in (source, workers, workspaces, receipts, logs):
        path.mkdir()
    command_records: list[dict[str, Any]] = []

    def run_command(label: str, command: list[str]) -> None:
        ordinal = len(command_records)
        started = utc_now()
        before = time.monotonic()
        completed = subprocess.run(
            command,
            cwd=repo,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            timeout=120,
            check=False,
        )
        wall_time_ms = round((time.monotonic() - before) * 1000)
        atomic_bytes(logs / f"{ordinal:03d}_{label}.stdout", completed.stdout)
        atomic_bytes(logs / f"{ordinal:03d}_{label}.stderr", completed.stderr)
        record = {
            "ordinal": ordinal,
            "label": label,
            "command": command,
            "started_utc": started,
            "ended_utc": utc_now(),
            "wall_time_ms": wall_time_ms,
            "return_code": completed.returncode,
        }
        command_records.append(record)
        atomic_json(output / "command_results.json", command_records)
        if completed.returncode != 0:
            raise E0Error(f"command {label} failed with rc={completed.returncode}")

    anchors, vault = fixture_rows()
    anchors_path = source / "anchors.jsonl"
    vault_path = source / "code_vault.jsonl"
    contract_path = source / "execution_contract.json"
    backend_path = source / "synthetic_backend.json"
    write_jsonl(anchors_path, anchors)
    write_jsonl(vault_path, vault)
    contract = {
        "schema_version": "balanced-continuation-contract-v1",
        "model_id": "deterministic-synthetic-v1",
        "provider": "offline-synthetic",
        "operator_config_sha256": sha256_bytes(b"E0|fixed-improve-debug-operator-v1"),
        "prompt_sha256": sha256_bytes(b"E0|deterministic-generated-code-v1"),
        "source_commit": args.source_commit,
        "dataset_contract_sha256": sha256_bytes(b"E0|two-tasks-four-anchors-three-siblings-v1"),
        "evaluator_contract_sha256": sha256_bytes(b"E0|bounded-synthetic-utility-v1"),
        "hardware_class": "cpu-offline-synthetic",
        "execution_timeout_seconds": 120,
        "continuation_horizon": 2,
        "debug_policy": "fixed_one_operator_per_step",
        "workspace_policy": "fresh_per_rollout",
        "temperature": 0.0,
    }
    atomic_json(contract_path, contract)
    python = sys.executable
    run_command(
        "assignment_producer",
        [
            python,
            "-m",
            "phase1.balanced_continuation_manifest",
            "--anchors",
            str(anchors_path),
            "--contract",
            str(contract_path),
            "--output",
            str(assignment),
            "--siblings-per-anchor",
            "3",
            "--replicates",
            "2",
            "--horizon",
            "2",
            "--seed",
            "20260814",
            "--created-utc",
            args.created_utc,
        ],
    )
    assignment_receipt = output / "assignment.verify.json"
    run_command(
        "assignment_independent_verify",
        [
            python,
            "-m",
            "phase1.verify_balanced_continuation_manifest",
            "--result",
            str(assignment),
            "--receipt",
            str(assignment_receipt),
        ],
    )
    assignment_rows = [
        json.loads(line)
        for line in (assignment / "assignment_manifest.jsonl").read_text(
            encoding="utf-8"
        ).splitlines()
    ]
    if len(assignment_rows) != 24:
        raise E0Error("E0 assignment must contain exactly 24 rollout jobs")
    backend = {
        "schema_version": "balanced-continuation-synthetic-backend-v1",
        "backend": "deterministic-synthetic-v1",
        "failure_utility": 0.0,
        "utility_min": 0.0,
        "utility_max": 1.0,
        "practical_delta": 0.1,
        "rollouts": {
            row["rollout_id"]: synthetic_outcomes(row["global_order"])
            for row in assignment_rows
        },
    }
    atomic_json(backend_path, backend)

    for index, row in enumerate(assignment_rows):
        rollout_id = row["rollout_id"]
        run_command(
            f"worker_{index:03d}",
            [
                python,
                "-m",
                "phase1.balanced_continuation_worker",
                "--assignment-result",
                str(assignment),
                "--code-vault",
                str(vault_path),
                "--backend-spec",
                str(backend_path),
                "--index",
                str(index),
                "--output-root",
                str(workers),
                "--workspace-root",
                str(workspaces),
            ],
        )
        run_command(
            f"verify_worker_{index:03d}",
            [
                python,
                "-m",
                "phase1.verify_balanced_continuation_worker",
                "--artifact",
                str(workers / rollout_id),
                "--assignment-result",
                str(assignment),
                "--code-vault",
                str(vault_path),
                "--backend-spec",
                str(backend_path),
                "--receipt",
                str(receipts / f"{rollout_id}.verify.json"),
            ],
        )

    collection_path = output / "collection.verify.json"
    run_command(
        "collection_independent_verify",
        [
            python,
            "-m",
            "phase1.verify_balanced_continuation_collection",
            "--assignment-result",
            str(assignment),
            "--assignment-receipt",
            str(assignment_receipt),
            "--worker-output-root",
            str(workers),
            "--receipt-root",
            str(receipts),
            "--workspace-root",
            str(workspaces),
            "--output",
            str(collection_path),
        ],
    )
    collection = json.loads(collection_path.read_text(encoding="utf-8"))
    expected = {
        "rollout_jobs": 24,
        "task_count": 2,
        "anchor_count": 4,
        "siblings_per_anchor": 3,
        "replicates_per_sibling": 2,
        "continuation_horizon": 2,
        "candidate_execution_attempts": 72,
        "operator_calls": 48,
        "retry_count": 0,
        "replacement_count": 0,
        "unique_workspace_paths": 24,
        "unique_workspace_tokens": 24,
    }
    for key, value in expected.items():
        if collection.get(key) != value:
            raise E0Error(f"collection accounting differs for {key}")
    if collection.get("task_rollout_counts") != {
        "synthetic-task-0": 12,
        "synthetic-task-1": 12,
    }:
        raise E0Error("task rollout counts differ from frozen E0 design")
    if len(command_records) != 51 or any(row["return_code"] != 0 for row in command_records):
        raise E0Error("command accounting differs from 51 successful process boundaries")

    pre_summary_files = [path for path in output.rglob("*") if path.is_file()]
    if any(CREDENTIAL.search(path.read_bytes()) for path in pre_summary_files):
        raise E0Error("credential-shaped bytes found in E0 output")
    summary = {
        "status": "VERIFIED_FULL_SYNTHETIC_BALANCED_CONTINUATION_E0",
        "scientific_outcome_claimed": False,
        "gpu_used": False,
        "api_used": False,
        "source_commit": args.source_commit,
        "created_utc": args.created_utc,
        "completed_utc": utc_now(),
        "command_processes": len(command_records),
        **expected,
        "task_rollout_counts": collection["task_rollout_counts"],
        "every_sibling_exactly_k": collection["every_sibling_exactly_k"],
        "every_block_contains_all_siblings": collection["every_block_contains_all_siblings"],
        "all_workspaces_fresh_and_unique": collection["all_workspaces_fresh_and_unique"],
        "assignment_manifest_sha256": sha256_bytes(
            (assignment / "assignment_manifest.jsonl").read_bytes()
        ),
        "assignment_verification_receipt_sha256": sha256_bytes(
            assignment_receipt.read_bytes()
        ),
        "collection_verification_sha256": sha256_bytes(collection_path.read_bytes()),
        "credential_shape_hits": 0,
    }
    atomic_json(output / "summary.json", summary)
    final_files = [path for path in output.rglob("*") if path.is_file()]
    if any(CREDENTIAL.search(path.read_bytes()) for path in final_files):
        raise E0Error("credential-shaped bytes found after writing E0 summary")
    relative_hashes = {
        path.relative_to(output).as_posix(): sha256_bytes(path.read_bytes())
        for path in sorted(final_files)
    }
    atomic_json(output / "sha256_manifest.json", relative_hashes)
    return summary


def parser() -> argparse.ArgumentParser:
    ap = argparse.ArgumentParser()
    ap.add_argument("--output", required=True)
    ap.add_argument("--source-commit", required=True)
    ap.add_argument("--created-utc", required=True)
    return ap


def main() -> int:
    args = parser().parse_args()
    output = pathlib.Path(args.output)
    try:
        result = run(args)
    except (E0Error, OSError, ValueError, subprocess.SubprocessError) as exc:
        if output.is_absolute() and output.exists() and output.is_dir():
            try:
                atomic_json(
                    output / "failure.json",
                    {
                        "status": "BALANCED_CONTINUATION_E0_FAILED",
                        "error_type": type(exc).__name__,
                        "error": str(exc),
                        "failed_utc": utc_now(),
                        "traceback": traceback.format_exc(),
                    },
                )
            except OSError:
                pass
        print(f"BALANCED_CONTINUATION_E0_FAILED: {exc}", file=sys.stderr)
        return 2
    print(canonical_json(result).decode("utf-8"))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
