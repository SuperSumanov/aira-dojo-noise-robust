#!/usr/bin/env python3
"""Execute exactly one frozen original-vs-contract generation entry."""

from __future__ import annotations

import argparse
import hashlib
import os
import subprocess
import time
from pathlib import Path

from phase1.probe_contract_ab_common import atomic_json, row_for_index


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--index", type=int, required=True)
    parser.add_argument("--task", required=True)
    parser.add_argument("--arm", required=True)
    parser.add_argument("--seed", type=int, required=True)
    parser.add_argument("--issue", required=True)
    parser.add_argument("--status-dir", type=Path, required=True)
    args = parser.parse_args()
    expected = row_for_index(args.index)
    supplied = {
        "index": args.index,
        "task": args.task,
        "arm": args.arm,
        "seed": args.seed,
        "issue": args.issue,
    }
    if supplied != expected:
        raise RuntimeError(f"entry differs from frozen A/B matrix: {supplied} != {expected}")

    status_path = args.status_dir / f"index_{args.index:02d}.json"
    if status_path.exists():
        raise RuntimeError(f"refusing existing status: {status_path}")
    solver = "mlebench/mcts_schema_probe" if args.arm == "contract" else "mlebench/mcts"
    first_valid_override = (
        "solver.stop_after_first_valid=true"
        if args.arm == "contract"
        else "+solver.stop_after_first_valid=true"
    )
    command = [
        os.environ.get("PROBE_AB_AIRA_PYTHON", "/research/d7/spc/yzyang4/venvs/aira/bin/python"),
        "-m",
        "dojo.main_run",
        "task=mlebench/_default",
        f"task.name={args.task}",
        "interpreter=jupyter",
        f"solver={solver}",
        "solver/client@solver.operators.analyze.llm.client=litellm_deepseek_flash",
        "solver/client@solver.operators.debug.llm.client=litellm_deepseek_flash",
        "solver/client@solver.operators.draft.llm.client=litellm_deepseek_flash",
        "solver/client@solver.operators.improve.llm.client=litellm_deepseek_flash",
        "solver.step_limit=3",
        "solver.num_children=1",
        "solver.max_debug_depth=1",
        first_valid_override,
        "solver.execution_timeout=600",
        "solver.time_limit_secs=1200",
        f"metadata.git_issue_id={args.issue}",
        f"metadata.seed={args.seed}",
        "logger.use_wandb=false",
    ]
    started_wall_ns = time.time_ns()
    started = time.monotonic()
    completed = subprocess.run(command, check=False)
    payload = {
        "schema_version": 1,
        **expected,
        "return_code": completed.returncode,
        "started_wall_ns": started_wall_ns,
        "ended_wall_ns": time.time_ns(),
        "wall_s": round(time.monotonic() - started, 6),
        "command": command,
        "command_sha256": hashlib.sha256("\0".join(command).encode("utf-8")).hexdigest(),
        "slurm_job_id": os.environ.get("SLURM_JOB_ID", ""),
        "slurm_step_id": os.environ.get("SLURM_STEP_ID", ""),
        "hostname": os.uname().nodename,
    }
    atomic_json(status_path, payload)
    print(
        "PROBE_CONTRACT_AB_ENTRY_DONE "
        f"index={args.index} task={args.task} arm={args.arm} "
        f"rc={completed.returncode} wall_s={payload['wall_s']}",
        flush=True,
    )
    raise SystemExit(completed.returncode)


if __name__ == "__main__":
    main()
