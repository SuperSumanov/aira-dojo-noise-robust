# Copyright (c) Meta Platforms, Inc. and affiliates.
# All rights reserved.

from __future__ import annotations

import argparse
import json
import os
from datetime import datetime
from pathlib import Path


def _atomic_write_json(path: Path, data: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary_path = path.with_name(f".{path.name}.{os.getpid()}.tmp")
    with temporary_path.open("w", encoding="utf-8") as file:
        json.dump(data, file, indent=2, sort_keys=True)
        file.flush()
        os.fsync(file.fileno())
    os.replace(temporary_path, path)


def main() -> None:
    parser = argparse.ArgumentParser(description="Run one AIRA Dojo config inside a Slurm allocation step.")
    parser.add_argument("config", type=Path)
    parser.add_argument("identity", type=Path)
    parser.add_argument("--run-id", required=True)
    parser.add_argument("--attempt", required=True, type=int)
    args = parser.parse_args()

    allocation_id = os.environ.get("SLURM_JOB_ID", "")
    step_id = os.environ.get("SLURM_STEP_ID", "")
    if not allocation_id or not step_id:
        raise RuntimeError("main_srun_worker must run inside a Slurm job step")

    _atomic_write_json(
        args.identity,
        {
            "run_id": args.run_id,
            "attempt": args.attempt,
            "allocation_id": allocation_id,
            "step_id": step_id,
            "full_step_id": f"{allocation_id}.{step_id}",
            "pid": os.getpid(),
            "started_at": datetime.now().astimezone().isoformat(),
        },
    )

    os.environ["DOJO_LAUNCHER_TYPE"] = "srun_pool"

    # Import after publishing the identity so the controller can map import-time
    # failures to the Slurm step that produced them.
    from dojo.config_dataclasses.run import RunConfig
    from dojo.main_run import _main

    run_cfg = RunConfig.load_from_json(args.config)
    _main(run_cfg)


if __name__ == "__main__":
    main()
