# Copyright (c) Meta Platforms, Inc. and affiliates.
# All rights reserved.

from __future__ import annotations

import argparse
import json
import os
import signal
import socket
import traceback
from datetime import datetime
from pathlib import Path
from types import FrameType


def _now() -> str:
    return datetime.now().astimezone().isoformat()


def _atomic_write_json(path: Path, data: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary_path = path.with_name(f".{path.name}.{os.getpid()}.tmp")
    with temporary_path.open("w", encoding="utf-8") as file:
        json.dump(data, file, indent=2, sort_keys=True)
        file.flush()
        os.fsync(file.fileno())
    os.replace(temporary_path, path)


def _host_boot_id() -> str:
    try:
        return (
            Path("/proc/sys/kernel/random/boot_id").read_text(encoding="utf-8").strip()
        )
    except OSError:
        return ""


def _process_start_ticks(pid: int) -> int | None:
    try:
        stat = Path(f"/proc/{pid}/stat").read_text(encoding="utf-8")
        return int(stat.rsplit(")", 1)[1].split()[19])
    except (FileNotFoundError, IndexError, ValueError, OSError):
        return None


_termination_signal: int | None = None


def _handle_signal(signum: int, frame: FrameType | None) -> None:
    del frame
    global _termination_signal
    _termination_signal = signum
    raise SystemExit(128 + signum)


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Run one AIRA Dojo config on a local GPU slot."
    )
    parser.add_argument("config", type=Path)
    parser.add_argument("identity", type=Path)
    parser.add_argument("result", type=Path)
    parser.add_argument("--run-id", required=True)
    parser.add_argument("--attempt", required=True, type=int)
    args = parser.parse_args()

    for signum in (signal.SIGINT, signal.SIGTERM):
        signal.signal(signum, _handle_signal)

    pid = os.getpid()
    ticks = _process_start_ticks(pid)
    host = socket.gethostname()
    execution_id = (
        f"{host}:{pid}:{ticks if ticks is not None else 'unknown'}:a{args.attempt}"
    )
    os.environ.update(
        {
            "DOJO_LAUNCHER_TYPE": "local_gpu_pool",
            "DOJO_ATTEMPT": str(args.attempt),
            "DOJO_EXECUTION_ID": execution_id,
            "DOJO_EXECUTION_HOST": host,
            "DOJO_WORKER_IDENTITY_PATH": str(args.identity),
        }
    )
    _atomic_write_json(
        args.identity,
        {
            "run_id": args.run_id,
            "attempt": args.attempt,
            "execution_id": execution_id,
            "host": host,
            "host_boot_id": _host_boot_id(),
            "pid": pid,
            "pgid": os.getpgid(pid),
            "process_start_ticks": ticks,
            "gpu_uuids": [
                value
                for value in os.environ.get("DOJO_GPU_UUIDS", "").split(",")
                if value
            ],
            "started_at": _now(),
            "container_pid": None,
            "container_pgid": None,
            "container_process_start_ticks": None,
        },
    )

    started_at = _now()
    try:
        from dojo.config_dataclasses.run import RunConfig
        from dojo.main_run import _main

        run_cfg = RunConfig.load_from_json(args.config)
        _main(run_cfg)
    except BaseException as error:
        status = "cancelled" if _termination_signal is not None else "failed"
        exit_code = 128 + _termination_signal if _termination_signal is not None else 1
        if isinstance(error, SystemExit) and isinstance(error.code, int):
            exit_code = error.code
        _atomic_write_json(
            args.result,
            {
                "run_id": args.run_id,
                "attempt": args.attempt,
                "execution_id": execution_id,
                "status": status,
                "exit_code": exit_code,
                "started_at": started_at,
                "ended_at": _now(),
                "exception_summary": f"{type(error).__name__}: {error}",
                "termination_signal": _termination_signal,
            },
        )
        traceback.print_exc()
        raise
    else:
        _atomic_write_json(
            args.result,
            {
                "run_id": args.run_id,
                "attempt": args.attempt,
                "execution_id": execution_id,
                "status": "completed",
                "exit_code": 0,
                "started_at": started_at,
                "ended_at": _now(),
                "exception_summary": "",
                "termination_signal": None,
            },
        )


if __name__ == "__main__":
    main()
