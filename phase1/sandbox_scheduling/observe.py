"""Bounded, read-only Linux telemetry; NOT a scheduler or candidate profiler.

Only explicitly supplied, same-owner PID identities and GPU UUIDs are sampled.
Never discovers processes, reads candidate contents, or changes resources.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import io
import json
import math
import os
from pathlib import Path
import platform
import re
import subprocess
import time
import uuid


GPU_UUID = re.compile(r"GPU-[0-9a-fA-F]{8}(?:-[0-9a-fA-F]{4}){3}-[0-9a-fA-F]{12}\Z")
IO_FIELDS = ("read_bytes", "write_bytes", "cancelled_write_bytes")
GPU_FIELDS = ("utilization_percent", "memory_used_mib", "memory_total_mib")


def target(value: str) -> tuple[int, int]:
    """PID and Linux start ticks must come from a trusted launcher receipt."""
    if not re.fullmatch(r"[1-9][0-9]*:[0-9]+", value):
        raise ValueError("expected positive PID:nonnegative-start-ticks")
    return tuple(map(int, value.split(":")))


def parse_stat(text: str) -> dict:
    # comm may contain spaces and ')' characters; the final ')' closes field 2.
    left, right = text.find("("), text.rfind(")")
    if left < 1 or right <= left:
        raise ValueError("invalid stat layout")
    pid = int(text[:left].strip())
    fields = text[right + 1:].split()  # starts at documented field 3
    if len(fields) < 22 or pid <= 0 or len(fields[0]) != 1:
        raise ValueError("incomplete stat")
    result = {
        "pid": pid, "state": fields[0], "ppid": int(fields[1]),
        "pgid": int(fields[2]), "session_id": int(fields[3]),
        "cpu_ticks": int(fields[11]) + int(fields[12]),
        "threads": int(fields[17]), "start_ticks": int(fields[19]),
        "rss_pages": int(fields[21]),
    }
    if any(result[k] < 0 for k in result if k != "state"):
        raise ValueError("negative stat counter")
    return result


def parse_io(text: str) -> dict:
    pairs = dict(line.split(":", 1) for line in text.splitlines() if ":" in line)
    result = {field: int(pairs[field].strip()) for field in IO_FIELDS}
    if min(result.values()) < 0:
        raise ValueError("negative io counter")
    return result


def error_status(error: Exception) -> str:
    if isinstance(error, FileNotFoundError):
        return "missing"
    if isinstance(error, PermissionError):
        return "denied"
    if isinstance(error, OSError):
        return "os_error"
    return "malformed"


def sample_process(pid: int, start_ticks: int, *, proc: Path, uid: int, page_size: int) -> dict:
    """Own-process counters, not a process tree; reject identity races."""
    row = {"pid": pid, "expected_start_ticks": start_ticks, "scope": "explicit_pid_only",
           "status": "unknown", "stat": None, "storage_io": None, "io_status": "not_sampled"}
    directory = proc / str(pid)
    try:
        if directory.stat().st_uid != uid:
            row["status"] = "owner_mismatch"
            return row
        first = parse_stat((directory / "stat").read_text())
        if (first["pid"], first["start_ticks"]) != (pid, start_ticks):
            row["status"] = "identity_mismatch"
            return row
        storage_io, io_status = None, "ok"
        try:
            storage_io = parse_io((directory / "io").read_text())
        except (OSError, ValueError, KeyError) as error:
            io_status = error_status(error)
        last = parse_stat((directory / "stat").read_text())
        if (last["pid"], last["start_ticks"]) != (pid, start_ticks):
            row["status"] = "identity_changed_during_sample"
            return row
        if directory.stat().st_uid != uid:
            row["status"] = "owner_changed_during_sample"
            return row
        if last["state"] in {"Z", "X", "x"}:
            row["status"] = "exited"
            return row
        if last["cpu_ticks"] < first["cpu_ticks"]:
            row["status"] = "counter_regressed_during_sample"
            return row
        last["rss_bytes_approx"] = last.pop("rss_pages") * page_size
        row.update(status="ok", stat=last, storage_io=storage_io, io_status=io_status)
        return row
    except (OSError, ValueError, KeyError) as error:
        row["status"] = error_status(error)
        return row


def parse_gpu(text: str, expected_uuid: str) -> dict:
    rows = list(csv.reader(io.StringIO(text)))
    if len(rows) != 1 or len(rows[0]) != 5 or rows[0][0].strip() != expected_uuid:
        raise ValueError("GPU identity/shape mismatch")
    values = [v.strip() for v in rows[0]]
    if not re.fullmatch(r"[0-9]+(?:\.[0-9]+)+", values[1]):
        raise ValueError("invalid driver version")
    result = {"uuid": expected_uuid, "driver_version": values[1], "metrics": {}, "field_status": {}}
    for field, raw in zip(GPU_FIELDS, values[2:]):
        if raw in {"N/A", "[N/A]", "[Not Supported]", "Not Supported"}:
            result["metrics"][field] = None
            result["field_status"][field] = "unsupported"
        else:
            value = float(raw)
            if not math.isfinite(value) or value < 0 or (field == GPU_FIELDS[0] and value > 100):
                raise ValueError("invalid GPU metric")
            result["metrics"][field] = value
            result["field_status"][field] = "ok"
    used, total = (result["metrics"][k] for k in GPU_FIELDS[1:])
    if used is not None and total is not None and used > total:
        raise ValueError("GPU memory exceeds total")
    return result


def sample_gpu(gpu_uuid: str) -> dict:
    if not GPU_UUID.fullmatch(gpu_uuid):
        raise ValueError("full physical GPU UUID required")
    row = {"uuid": gpu_uuid, "scope": "whole_device_not_candidate", "status": "unknown", "data": None}
    try:
        completed = subprocess.run(
            ["nvidia-smi", "-i", gpu_uuid,
             "--query-gpu=uuid,driver_version,utilization.gpu,memory.used,memory.total",
             "--format=csv,noheader,nounits"], capture_output=True, text=True, timeout=2, check=False,
        )
        if completed.returncode:
            row["status"] = "query_failed"
        else:
            row.update(status="ok", data=parse_gpu(completed.stdout, gpu_uuid))
    except subprocess.TimeoutExpired:
        row["status"] = "timeout"
    except (OSError, ValueError) as error:
        row["status"] = error_status(error)
    # Neither command stderr nor unexpected output is copied into the receipt.
    return row


def cpu_delta(previous: dict, current: dict, clock_ticks: int) -> dict:
    """No imputation across missing samples, recycled PIDs, or counter resets."""
    result = {"status": "unavailable", "cpu_seconds": None}
    if previous["status"] != "ok" or current["status"] != "ok":
        return result
    a, b = previous["stat"], current["stat"]
    if (a["pid"], a["start_ticks"]) != (b["pid"], b["start_ticks"]):
        return result
    delta = b["cpu_ticks"] - a["cpu_ticks"]
    if delta < 0:
        return dict(result, status="counter_regression")
    if clock_ticks <= 0:
        raise ValueError("clock ticks must be positive")
    return {"status": "ok", "cpu_seconds": delta / clock_ticks}


def validate(args: argparse.Namespace) -> None:
    args.targets = [target(value) for value in args.pid]
    if len({pid for pid, _ in args.targets}) != len(args.targets):
        raise ValueError("duplicate PID")
    if not 1 <= len(args.targets) <= 32:
        raise ValueError("require 1 to 32 explicit PIDs")
    if (not math.isfinite(args.interval) or not 1 <= args.interval <= 30
            or not 1 <= args.samples <= 600 or args.interval * args.samples > 3600):
        raise ValueError("bounded sampling required: 1..30 seconds, 1..600 samples, <=1h planned")
    if not re.fullmatch(r"[0-9a-f]{40}", args.source_commit):
        raise ValueError("source commit must be full lower-case SHA1")
    if str(uuid.UUID(args.boot_id)) != args.boot_id:
        raise ValueError("boot identity must be canonical UUID")
    if len(args.gpu_uuid) > 8 or len(set(args.gpu_uuid)) != len(args.gpu_uuid):
        raise ValueError("at most eight distinct allocated GPUs")
    if any(not GPU_UUID.fullmatch(value) for value in args.gpu_uuid):
        raise ValueError("invalid physical GPU UUID")


def record(args: argparse.Namespace, *, proc: Path = Path("/proc")) -> int:
    validate(args)
    if platform.system() != "Linux":
        raise ValueError("Linux procfs required")
    if (proc / "sys/kernel/random/boot_id").read_text().strip() != args.boot_id:
        raise ValueError("host boot identity mismatch")
    uid = os.getuid()
    ticks, page_size = os.sysconf("SC_CLK_TCK"), os.sysconf("SC_PAGE_SIZE")
    source_sha = hashlib.sha256(Path(__file__).read_bytes()).hexdigest()
    previous = {}
    start = time.monotonic_ns()
    # Exclusive creation prevents overwriting another run/failed attempt.
    with Path(args.output).open("x", encoding="utf-8") as output:
        def emit(row: dict) -> None:
            output.write(json.dumps(row, sort_keys=True, allow_nan=False) + "\n")
            output.flush()

        emit({"kind": "header", "schema": "sandbox-observer-v0", "source_commit": args.source_commit,
              "recorder_sha256": source_sha, "host_boot_id": args.boot_id,
              "python_version": platform.python_version(), "kernel_release": platform.release(),
              "clock_ticks_per_second": ticks, "page_size_bytes": page_size,
              "targets": args.targets, "gpu_uuids": args.gpu_uuid, "interval_seconds": args.interval,
              "requested_samples": args.samples, "candidate_scope_complete": False,
              "gpu_scope": "whole_device", "randomness": "none",
              "started_utc_unix_ns": time.time_ns()})
        complete = False
        for index in range(args.samples):
            before = time.monotonic_ns()
            processes = []
            for pid, identity in args.targets:
                row = sample_process(pid, identity, proc=proc, uid=uid, page_size=page_size)
                row["cpu_delta"] = (cpu_delta(previous[pid], row, ticks) if pid in previous
                                    else {"status": "first_sample", "cpu_seconds": None})
                previous[pid] = row
                processes.append(row)
            devices = [sample_gpu(value) for value in args.gpu_uuid]
            after = time.monotonic_ns()
            healthy = all(p["status"] == "ok" and p["cpu_delta"]["status"] != "counter_regression"
                          for p in processes) and all(g["status"] == "ok" for g in devices)
            emit({"kind": "sample", "index": index, "started_monotonic_ns": before,
                  "ended_monotonic_ns": after, "utc_unix_ns": time.time_ns(),
                  "sampling_wall_seconds": (after - before) / 1e9,
                  "processes": processes, "devices": devices, "identity_query_ok": healthy})
            if not healthy:
                break  # Stop observation, never manipulate the target process.
            if index == args.samples - 1:
                complete = True
            else:
                time.sleep(args.interval)  # Interval is AFTER sampling, not an exact fixed-rate trace.
        emit({"kind": "footer", "status": "complete" if complete else "incomplete_observation",
              "written_samples": index + 1, "elapsed_seconds": (time.monotonic_ns() - start) / 1e9})
    return 0 if complete else 2


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--pid", action="append", required=True, help="launcher PID:start_ticks; repeat as needed")
    parser.add_argument("--boot-id", required=True, help="launcher host boot UUID")
    parser.add_argument("--gpu-uuid", action="append", default=[], help="explicit allocated physical GPU only")
    parser.add_argument("--source-commit", required=True)
    parser.add_argument("--output", required=True, help="new JSONL path; never append/overwrite")
    parser.add_argument("--samples", type=int, default=30)
    parser.add_argument("--interval", type=float, default=2)
    args = parser.parse_args()
    try:
        return record(args)
    except (ValueError, OSError):
        # Raw OS error paths can contain private names; no traceback/contents in the public receipt.
        parser.exit(2, "observation refused or interrupted by an I/O error; no target was modified\n")


if __name__ == "__main__":
    raise SystemExit(main())
