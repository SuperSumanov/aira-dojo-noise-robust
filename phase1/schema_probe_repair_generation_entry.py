#!/usr/bin/env python3
"""Run one preregistered V2 schema/probe generation entry."""

from __future__ import annotations

import argparse
import hashlib
import os
import subprocess
import time
from pathlib import Path

from phase1.schema_probe_generation_entry import atomic_json


TASK_BY_INDEX = {
    0: "spaceship-titanic",
    1: "tweet-sentiment-extraction",
}
EXPECTED_SEED = 862
EXPECTED_ISSUE = "schema_probe_repair_v2"


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--task", required=True)
    parser.add_argument("--index", type=int, required=True)
    parser.add_argument("--seed", type=int, required=True)
    parser.add_argument("--issue", required=True)
    parser.add_argument("--status-dir", type=Path, required=True)
    args = parser.parse_args()
    if (
        TASK_BY_INDEX.get(args.index) != args.task
        or args.seed != EXPECTED_SEED
        or args.issue != EXPECTED_ISSUE
    ):
        raise RuntimeError("entry point differs from preregistered V2 matrix")
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
        "solver.step_limit=3",
        "solver.num_children=1",
        "solver.max_debug_depth=1",
        "solver.stop_after_first_valid=true",
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
        "schema_version": 2,
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
        "SCHEMA_PROBE_REPAIR_ENTRY_DONE "
        f"index={args.index} task={args.task} rc={completed.returncode} wall_s={payload['wall_s']}",
        flush=True,
    )
    raise SystemExit(completed.returncode)


if __name__ == "__main__":
    main()
