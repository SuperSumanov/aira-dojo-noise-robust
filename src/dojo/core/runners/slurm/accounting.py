# Copyright (c) Meta Platforms, Inc. and affiliates.
# All rights reserved.

from __future__ import annotations

import subprocess
from collections.abc import Callable, Sequence

SACCT_FIELDS = (
    "JobIDRaw",
    "JobName",
    "State",
    "ExitCode",
    "Submit",
    "Start",
    "End",
    "ElapsedRaw",
    "NodeList",
)

TERMINAL_STATES = {
    "BOOT_FAIL",
    "CANCELLED",
    "COMPLETED",
    "DEADLINE",
    "FAILED",
    "NODE_FAIL",
    "OUT_OF_MEMORY",
    "PREEMPTED",
    "REVOKED",
    "TIMEOUT",
}
ACTIVE_STATES = {
    "CONFIGURING",
    "COMPLETING",
    "PENDING",
    "REQUEUED",
    "RESIZING",
    "RUNNING",
    "SUSPENDED",
}


def normalize_slurm_state(state: str) -> str:
    """Remove Slurm annotations such as `CANCELLED by 123` and `COMPLETED+`."""
    return state.strip().split(maxsplit=1)[0].rstrip("+")


def parse_sacct_parsable(output: str) -> dict[str, dict[str, str]]:
    records: dict[str, dict[str, str]] = {}
    for line in output.splitlines():
        if not line.strip():
            continue
        values = line.split("|")
        if values and values[-1] == "":
            values.pop()
        if len(values) != len(SACCT_FIELDS):
            raise ValueError(
                f"Expected {len(SACCT_FIELDS)} sacct fields, got {len(values)} in line: {line!r}"
            )
        record = dict(zip(SACCT_FIELDS, values))
        record["State"] = normalize_slurm_state(record["State"])
        records[record["JobIDRaw"]] = record
    return records


def query_sacct(
    job_ids: str | Sequence[str],
    *,
    run: Callable[..., subprocess.CompletedProcess[str]] = subprocess.run,
) -> dict[str, dict[str, str]]:
    if isinstance(job_ids, str):
        ids = [job_ids]
    else:
        ids = [str(job_id) for job_id in job_ids]
    ids = [job_id for job_id in ids if job_id]
    if not ids:
        return {}

    result = run(
        [
            "sacct",
            "-P",
            "-n",
            "-j",
            ",".join(ids),
            f"--format={','.join(SACCT_FIELDS)}",
        ],
        check=False,
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        raise RuntimeError(f"sacct failed with exit code {result.returncode}: {result.stderr.strip()}")
    return parse_sacct_parsable(result.stdout)
