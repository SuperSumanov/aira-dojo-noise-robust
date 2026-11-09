from dataclasses import dataclass

from omegaconf import MISSING, SI

from dojo.config_dataclasses.task.mlebench import MLEBenchTaskConfig


@dataclass
class MLEBenchTaskWarmupConfig(MLEBenchTaskConfig):
    warmup_dir: str = MISSING
    public_dir: str = SI("${task.warmup_dir}/public")
    data_dir: str = SI("${task.public_dir}")
