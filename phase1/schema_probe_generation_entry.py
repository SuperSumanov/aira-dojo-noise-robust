#!/usr/bin/env python3
"""Run one frozen direct AIRA generation and atomically record its real return code."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import subprocess
import tempfile
import time
from pathlib import Path


TASKS = {
    "tabular-playground-series-may-2022",
    "spooky-author-identification",
}


def atomic_json(path: Path, payload: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp_name = tempfile.mkstemp(prefix=f".{path.name}.", dir=path.parent)
    try:
        with os.fdopen(fd, "w", encoding="utf-8", newline="") as handle:
            json.dump(payload, handle, ensure_ascii=False, sort_keys=True, indent=2)
            handle.write("\n")
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(tmp_name, path)
    finally:
        if os.path.exists(tmp_name):
            os.unlink(tmp_name)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--task", required=True)
    parser.add_argument("--index", type=int, required=True)
    parser.add_argument("--seed", type=int, required=True)
    parser.add_argument("--issue", required=True)
    parser.add_argument("--status-dir", type=Path, required=True)
    args = parser.parse_args()
    if args.task not in TASKS or args.seed != 861 or args.issue != "schema_probe_smoke_v1":
        raise RuntimeError("entry point differs from frozen smoke matrix")
    if args.index not in (0, 1):
        raise RuntimeError("index must be 0 or 1")
    status_path = args.status_dir / f"index_{args.index}.json"
    if status_path.exists():
        raise RuntimeError(f"refusing existing status: {status_path}")

    command = [
        os.environ.get("SCHEMA_PROBE_AIRA_PYTHON", "/research/d7/spc/yzyang4/venvs/aira/bin/python"),
        "-m",
        "dojo.main_run",
        f"task=mlebench/{args.task}",
        "interpreter=jupyter",
        "solver=mlebench/mcts_schema_probe",
        "solver/client@solver.operators.analyze.llm.client=litellm_deepseek_flash",
        "solver/client@solver.operators.debug.llm.client=litellm_deepseek_flash",
        "solver/client@solver.operators.draft.llm.client=litellm_deepseek_flash",
        "solver/client@solver.operators.improve.llm.client=litellm_deepseek_flash",
        "solver.step_limit=1",
        "solver.execution_timeout=600",
        "solver.time_limit_secs=1200",
        f"metadata.git_issue_id={args.issue}",
        f"metadata.seed={args.seed}",
        "logger.use_wandb=false",
    ]
    started_wall_ns = time.time_ns()
    started = time.monotonic()
    completed = subprocess.run(command, check=False)
    ended_wall_ns = time.time_ns()
    payload = {
        "schema_version": 1,
        "task": args.task,
        "index": args.index,
        "seed": args.seed,
        "issue": args.issue,
        "return_code": completed.returncode,
        "started_wall_ns": started_wall_ns,
        "ended_wall_ns": ended_wall_ns,
        "wall_s": round(time.monotonic() - started, 6),
        "command": command,
        "command_sha256": hashlib.sha256("\0".join(command).encode("utf-8")).hexdigest(),
        "slurm_job_id": os.environ.get("SLURM_JOB_ID", ""),
        "slurm_step_id": os.environ.get("SLURM_STEP_ID", ""),
        "hostname": os.uname().nodename,
    }
    atomic_json(status_path, payload)
    print(
        "SCHEMA_PROBE_GENERATION_ENTRY_DONE "
        f"index={args.index} task={args.task} rc={completed.returncode} wall_s={payload['wall_s']}",
        flush=True,
    )
    raise SystemExit(completed.returncode)


if __name__ == "__main__":
    main()
