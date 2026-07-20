# Copyright (c) Meta Platforms, Inc. and affiliates.
# All rights reserved.

from dataclasses import dataclass, field

from dojo.config_dataclasses.launcher.base import LauncherConfig


@dataclass
class SrunPoolConfig(LauncherConfig):
    max_parallel: int = field(default=8, metadata={"exclude_from_hash": True})
    cpus_per_step: int = field(default=2, metadata={"exclude_from_hash": True})
    gpus_per_step: int = field(default=1, metadata={"exclude_from_hash": True})
    ntasks_per_step: int = field(default=1, metadata={"exclude_from_hash": True})
    poll_interval_seconds: float = field(default=5.0, metadata={"exclude_from_hash": True})
    max_retries: int = field(default=1, metadata={"exclude_from_hash": True})
    fail_fast: bool = field(default=False, metadata={"exclude_from_hash": True})
    allocation_job_id: str | None = field(default=None, metadata={"exclude_from_hash": True})
    min_remaining_seconds_to_launch: int = field(default=1800, metadata={"exclude_from_hash": True})
    shutdown_grace_seconds: int = field(default=30, metadata={"exclude_from_hash": True})
    validate_paths_on_node: bool = field(default=True, metadata={"exclude_from_hash": True})

    def validate(self) -> None:
        super().validate()
        positive = {
            "max_parallel": self.max_parallel,
            "cpus_per_step": self.cpus_per_step,
            "gpus_per_step": self.gpus_per_step,
            "ntasks_per_step": self.ntasks_per_step,
            "poll_interval_seconds": self.poll_interval_seconds,
        }
        for name, value in positive.items():
            if value <= 0:
                raise ValueError(f"{name} must be positive, got {value}")
        if self.ntasks_per_step != 1:
            raise ValueError("The first SrunPoolLauncher implementation supports ntasks_per_step=1 only")
        if self.max_retries < 0:
            raise ValueError("max_retries cannot be negative")
        if self.min_remaining_seconds_to_launch < 0:
            raise ValueError("min_remaining_seconds_to_launch cannot be negative")
        if self.shutdown_grace_seconds < 0:
            raise ValueError("shutdown_grace_seconds cannot be negative")
        if not self.await_completion or not self.monitor_jobs:
            raise ValueError("srun_pool must await and monitor its steps; detached pool controllers are not supported")
