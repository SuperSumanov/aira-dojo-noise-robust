"""Expand a warmup benchmark into independently configured MLE-bench tasks."""

from dataclasses import dataclass
from pathlib import Path

from omegaconf import MISSING

from dojo.config_dataclasses.benchmark import BenchmarkConfig
from dojo.config_dataclasses.task.mlebench_warmup import MLEBenchTaskWarmupConfig


@dataclass
class WarmupBenchmarkConfig(BenchmarkConfig):
    warmup_root: str = MISSING
    warmup_version: str = "v1"

    def to_cfg_list(self):
        root = Path(self.warmup_root).resolve()
        return [
            MLEBenchTaskWarmupConfig(
                name=task_name,
                benchmark=self.name,
                **{
                    "warmup_dir": str(root / task_name / self.warmup_version),
                    **self.overrides,
                    **self.task_overrides.get(task_name, {}),
                },
            )
            for task_name in self.tasks
        ]
