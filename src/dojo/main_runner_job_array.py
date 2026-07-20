# Copyright (c) Meta Platforms, Inc. and affiliates.
# All rights reserved.
#
# This source code is licensed under the license found in the
# LICENSE file in the root directory of this source tree.

import asyncio
import copy
import glob
import itertools
import logging
import os
from dataclasses import asdict
from datetime import datetime
from pathlib import Path

import hydra
import submitit
from dotenv import load_dotenv
from omegaconf import DictConfig, OmegaConf
from submitit.helpers import RsyncSnapshot, monitor_jobs

from dojo.config_dataclasses.omegaconf.resolvers import register_new_resolvers
from dojo.config_dataclasses.launcher.base import LauncherConfig
from dojo.config_dataclasses.launcher.slurm import SlurmConfig
from dojo.config_dataclasses.launcher.srun_pool import SrunPoolConfig
from dojo.config_dataclasses.run import RunConfig
from dojo.config_dataclasses.runner import RunnerConfig
from dojo.core.runners.slurm.srun_pool import SrunPoolLauncher
from dojo.utils.environment import get_log_dir
from dojo.utils.git import get_git_top_level

load_dotenv()
log = logging.getLogger(__name__)

register_new_resolvers()


def run_batch_config(run_cfg: RunConfig) -> None:
    from dojo.main_run import _main

    _main(run_cfg)


def create_snapshot() -> Path:
    """Create one shared snapshot containing tracked and untracked source files."""
    original_path = Path.cwd()
    git_root = Path(get_git_top_level())
    date_str = datetime.now().strftime("%Y-%m-%d-%H-%M-%S-%f")
    snapshot_path = Path(get_log_dir()) / "aira-dojo" / "snapshots" / f"{date_str}"
    snapshot_path.mkdir(parents=True, exist_ok=False)
    log.info("Snapshotting code to %s", snapshot_path)

    try:
        os.chdir(git_root)
        with RsyncSnapshot(
            snapshot_dir=snapshot_path,
            root_dir=git_root,
            with_submodules=True,
            exclude=["*.ipynb", "*__pycache__", "*.mypy_cache"],
            # RsyncSnapshot otherwise ignores untracked source files, which is
            # surprising and breaks freshly-added worker/launcher modules.
            include=glob.glob("./src/**", recursive=True),
        ):
            pass
    finally:
        os.chdir(original_path)
    return snapshot_path.resolve()


def _snapshot_pythonpath(snapshot_path: Path) -> str:
    return os.pathsep.join(
        [
            str(snapshot_path / "src"),
            str(snapshot_path / "src/dojo/tasks/mlebench/mle-bench"),
        ]
    )


def launch_batch_jobs(
    config_list: list[RunConfig], launcher_cfg: SlurmConfig, snapshot_path: Path
) -> list[submitit.Job]:
    slurm_folder = Path(get_log_dir()) / "slurm_logs" / "%j"
    executor = submitit.SlurmExecutor(folder=slurm_folder)
    executor_kwargs = {
        key: val
        for key, val in asdict(launcher_cfg).items()
        if val is not None
        and not launcher_cfg.__dataclass_fields__[key].metadata.get("exclude_from_executor", False)
    }
    executor.update_parameters(**executor_kwargs)

    previous_cwd = Path.cwd()
    previous_pythonpath = os.environ.get("PYTHONPATH")
    try:
        os.chdir(snapshot_path)
        os.environ["PYTHONPATH"] = _snapshot_pythonpath(snapshot_path)
        jobs = []
        with executor.batch():
            for run_cfg in config_list:
                jobs.append(executor.submit(run_batch_config, run_cfg))
        return jobs
    finally:
        os.chdir(previous_cwd)
        if previous_pythonpath is None:
            os.environ.pop("PYTHONPATH", None)
        else:
            os.environ["PYTHONPATH"] = previous_pythonpath


def launch_srun_pool(
    config_list: list[RunConfig], launcher_cfg: SrunPoolConfig, snapshot_path: Path
) -> dict:
    return SrunPoolLauncher(config_list, launcher_cfg, snapshot_path).run()


def launch_jobs(config_list: list[RunConfig], launcher_cfg: LauncherConfig):
    if isinstance(launcher_cfg, SrunPoolConfig):
        snapshot_path = SrunPoolLauncher.resume_snapshot_path(config_list, launcher_cfg)
        if snapshot_path is None:
            snapshot_path = create_snapshot()
        return launch_srun_pool(config_list, launcher_cfg, snapshot_path)
    if isinstance(launcher_cfg, SlurmConfig):
        return launch_batch_jobs(config_list, launcher_cfg, create_snapshot())
    raise ValueError(f"Unsupported launcher configuration type: {type(launcher_cfg).__name__}")


def override_config(config, key, value):
    if "." in key:
        # Handle nested keys like 'metadata.seed'
        parts = key.split(".")
        if hasattr(config, parts[0]):
            override_config(getattr(config, parts[0]), ".".join(parts[1:]), value)
        else:
            # Key doesn't exist
            raise ValueError(f"Key '{key}' not found in config.")
    elif hasattr(config, key):
        # Handle top-level keys
        setattr(config, key, value)
    else:
        # Key doesn't exist and isn't nested
        raise ValueError(f"Key '{key}' not found in config.")


def fetch_config(config, key):
    if "." in key:
        # Handle nested keys like 'metadata.seed'
        parts = key.split(".")
        if hasattr(config, parts[0]):
            return fetch_config(getattr(config, parts[0]), ".".join(parts[1:]))
        else:
            # Key doesn't exist
            raise ValueError(f"Key '{key}' not found in config.")
    elif hasattr(config, key):
        # Handle top-level keys
        return getattr(config, key)
    else:
        # Key doesn't exist and isn't nested
        raise ValueError(f"Key '{key}' not found in config.")


async def _main(runner_configs: list[RunnerConfig]):
    if not runner_configs:
        raise ValueError("At least one RunnerConfig is required")
    launcher_cfg = runner_configs[0].launcher
    if any(type(cfg.launcher) is not type(launcher_cfg) for cfg in runner_configs):
        raise ValueError("All swept RunnerConfigs must use the same launcher type")
    run_configs = []
    for runner_cfg in runner_configs:
        for task_cfg in runner_cfg.benchmark.to_cfg_list():
            run_cfg = RunConfig(
                meta_id=runner_cfg.id,
                logger=runner_cfg.logger,
                metadata=runner_cfg.metadata,
                task=task_cfg,
                solver=runner_cfg.solver,
                interpreter=runner_cfg.interpreter,
            )

            # Resolve interpolations (e.g. experiment ID, time, etc.)
            run_cfg = OmegaConf.structured(run_cfg)
            OmegaConf.resolve(run_cfg)
            run_cfg = OmegaConf.to_object(run_cfg)
            run_cfg.validate()  # Make sure everything is valid

            # Add the run config to the list
            run_configs.append(run_cfg)

    if launcher_cfg.debug:
        result = []

        swept_keys = list(runner_configs[0].vars.keys()) + ["task.name"]
        # Print a summary of the jobs that would be launched
        log.debug("Dry run mode: printing job summary")
        for cfg in run_configs:
            for key in swept_keys:
                print(f"{key}{' ' * (30 - len(key))}{fetch_config(cfg, key)}")
            print("============" * 5)
    else:
        log.debug("Launching jobs...")
        result = launch_jobs(run_configs, launcher_cfg)

    return result


@hydra.main(version_base="1.3.2", config_path="configs", config_name="default_runner")
def main(_cfg: DictConfig):
    ## Validate and setup config
    # 1) Check structure
    og_cfg: RunnerConfig = hydra.utils.instantiate(_cfg)

    ## Create a list of Runner configs, given the list of override variables
    runner_configs = []
    cmd_vars = dict(og_cfg.vars)
    keys = list(cmd_vars.keys())
    for idx, values in enumerate(itertools.product(*(cmd_vars[key] for key in keys))):
        single_vars_comb = dict(zip(keys, values))

        # 1) Apply override variables to the run config
        runner_cfg: RunnerConfig = copy.deepcopy(og_cfg)
        for k, v in single_vars_comb.items():
            override_config(runner_cfg, k, v)

        # runner_cfg.validate()

        runner_configs.append(runner_cfg)

    result = asyncio.run(_main(runner_configs))
    if isinstance(og_cfg.launcher, SrunPoolConfig):
        if result:
            log.info("Srun pool manifest: %s", result["manifest_path"])
            if not result["successful"]:
                raise RuntimeError(
                    f"Srun pool finished with incomplete tasks; inspect {result['manifest_path']}"
                )
        return

    jobs = [j for j in result if j is not None]
    if og_cfg.launcher.monitor_jobs:
        log.info("Monitoring jobs...")
        # Monitor the jobs
        monitor_jobs(jobs)
    else:
        log.info("Jobs launched successfully, but not monitored.")
        job_arrays = ", ".join(sorted(set(str(job.job_id).split("_", 1)[0] for job in jobs)))
        log.info(f"Monitoring {len(jobs)} jobs from job arrays {job_arrays} \n")


if __name__ == "__main__":
    main()
