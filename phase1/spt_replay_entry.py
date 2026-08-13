#!/usr/bin/env python3
"""Run one SPT worker and persist infrastructure RC independently of science output."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import subprocess
import sys
import time
from pathlib import Path


def command_sha256(command: list[str]) -> str:
    return hashlib.sha256("\0".join(command).encode("utf-8")).hexdigest()


def atomic_json(path: Path, payload: dict) -> None:
    with path.open("x", encoding="utf-8", newline="") as handle:
        json.dump(payload, handle, ensure_ascii=False, sort_keys=True, indent=2)
        handle.write("\n")
        handle.flush()
        os.fsync(handle.fileno())


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--index", type=int, required=True)
    parser.add_argument("--repo", type=Path, required=True)
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument("--runtime-source", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--workbase", type=Path, required=True)
    parser.add_argument("--status-dir", type=Path, required=True)
    parser.add_argument("--container-sha256", required=True)
    args = parser.parse_args()
    args.status_dir.mkdir(parents=True, exist_ok=True)
    status_path = args.status_dir / f"index_{args.index:02d}.json"
    if status_path.exists():
        raise RuntimeError(f"refusing existing status: {status_path}")
    command = [
        sys.executable,
        "-m",
        "phase1.spt_replay_worker",
        "--manifest",
        str(args.manifest),
        "--index",
        str(args.index),
        "--out",
        str(args.out),
        "--checkpoints",
        "30,60,120,240,360,600",
        "--poll-s",
        "0.10",
        "--workbase",
        str(args.workbase),
        "--runtime-source",
        str(args.runtime_source),
        "--container-sha256",
        args.container_sha256,
        "--online",
    ]
    started_wall_ns = time.time_ns()
    started = time.monotonic()
    completed = subprocess.run(command, cwd=args.repo, check=False)
    wall_s = time.monotonic() - started
    payload = {
        "schema_version": 1,
        "index": args.index,
        "return_code": completed.returncode,
        "wall_s": round(wall_s, 6),
        "started_wall_ns": started_wall_ns,
        "ended_wall_ns": time.time_ns(),
        "command_sha256": command_sha256(command),
        "slurm_job_id": os.environ.get("SLURM_JOB_ID"),
        "slurm_step_id": os.environ.get("SLURM_STEP_ID"),
        "hostname": os.uname().nodename,
        "cuda_visible_devices": os.environ.get("CUDA_VISIBLE_DEVICES"),
    }
    atomic_json(status_path, payload)
    print(
        f"SPT_REPLAY_ENTRY_DONE index={args.index} rc={completed.returncode} wall_s={wall_s:.6f}",
        flush=True,
    )
    raise SystemExit(completed.returncode)


if __name__ == "__main__":
    main()
