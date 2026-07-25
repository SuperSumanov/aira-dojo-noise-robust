# Copyright (c) Meta Platforms, Inc. and affiliates.
# All rights reserved.

from dataclasses import dataclass, field

from dojo.config_dataclasses.launcher.base import LauncherConfig


@dataclass
class LocalGpuPoolConfig(LauncherConfig):
    devices: list[int | str] | None = field(
        default=None, metadata={"exclude_from_hash": True}
    )
    gpus_per_task: int = field(default=1, metadata={"exclude_from_hash": True})
    max_parallel: int | None = field(default=None, metadata={"exclude_from_hash": True})
    poll_interval_seconds: float = field(
        default=2.0, metadata={"exclude_from_hash": True}
    )
    max_retries: int = field(default=1, metadata={"exclude_from_hash": True})
    fail_fast: bool = field(default=False, metadata={"exclude_from_hash": True})
    task_timeout_seconds: float | None = field(
        default=None, metadata={"exclude_from_hash": True}
    )
    shutdown_grace_seconds: float = field(
        default=30.0, metadata={"exclude_from_hash": True}
    )

    def validate(self) -> None:
        super().validate()
        if self.gpus_per_task <= 0:
            raise ValueError("gpus_per_task must be positive")
        if self.max_parallel is not None and self.max_parallel <= 0:
            raise ValueError("max_parallel must be positive when set")
        if self.poll_interval_seconds <= 0:
            raise ValueError("poll_interval_seconds must be positive")
        if self.max_retries < 0:
            raise ValueError("max_retries cannot be negative")
        if self.task_timeout_seconds is not None and self.task_timeout_seconds <= 0:
            raise ValueError("task_timeout_seconds must be positive when set")
        if self.shutdown_grace_seconds < 0:
            raise ValueError("shutdown_grace_seconds cannot be negative")
        if self.devices is not None and not self.devices:
            raise ValueError(
                "devices cannot be empty; use CUDA_VISIBLE_DEVICES=-1 to expose no GPUs"
            )
        if not self.await_completion or not self.monitor_jobs:
            raise ValueError(
                "local_gpu_pool must await and monitor its workers; detached pool controllers are not supported"
            )
