# Copyright (c) Meta Platforms, Inc. and affiliates.
# All rights reserved.
#
# This source code is licensed under the license found in the
# LICENSE file in the root directory of this source tree.

import os
from dataclasses import dataclass


@dataclass(frozen=True)
class SlurmIdentity:
    full_id: str = ""
    allocation_id: str = ""
    step_id: str = ""
    launcher_type: str = "local"


def get_slurm_identity() -> SlurmIdentity:
    launcher_type = os.environ.get("DOJO_LAUNCHER_TYPE", "")
    array_id = os.environ.get("SLURM_ARRAY_JOB_ID", "")
    array_task_id = os.environ.get("SLURM_ARRAY_TASK_ID", "")
    job_id = os.environ.get("SLURM_JOB_ID", "")
    step_id = os.environ.get("SLURM_STEP_ID", "")

    if array_id and array_task_id:
        return SlurmIdentity(
            full_id=f"{array_id}_{array_task_id}",
            allocation_id=array_id,
            launcher_type=launcher_type or "slurm_batch",
        )

    if job_id and step_id and step_id not in {"batch", "extern"}:
        return SlurmIdentity(
            full_id=f"{job_id}.{step_id}",
            allocation_id=job_id,
            step_id=step_id,
            launcher_type=launcher_type or "srun",
        )

    if job_id:
        return SlurmIdentity(
            full_id=job_id,
            allocation_id=job_id,
            launcher_type=launcher_type or "slurm_batch",
        )

    return SlurmIdentity(launcher_type=launcher_type or "local")


def get_slurm_id() -> str:
    return get_slurm_identity().full_id
