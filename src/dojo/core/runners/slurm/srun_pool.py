# Copyright (c) Meta Platforms, Inc. and affiliates.
# All rights reserved.

from __future__ import annotations

import getpass
import hashlib
import json
import logging
import os
import re
import signal
import subprocess
import sys
import time
from collections import Counter, deque
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from types import FrameType
from typing import Any

from dojo.config_dataclasses.launcher.srun_pool import SrunPoolConfig
from dojo.config_dataclasses.run import RunConfig
from dojo.core.runners.slurm.accounting import ACTIVE_STATES, TERMINAL_STATES, query_sacct

log = logging.getLogger(__name__)


@dataclass
class AllocationInfo:
    job_id: str
    node_list: str
    num_nodes: int
    num_cpus: int
    num_gpus: int
    end_time: datetime | None


@dataclass
class RunningStep:
    run_id: str
    process: subprocess.Popen[Any]
    identity_path: Path


def _now() -> str:
    return datetime.now().astimezone().isoformat()


def _atomic_write_json(path: Path, data: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary_path = path.with_name(f".{path.name}.{os.getpid()}.tmp")
    with temporary_path.open("w", encoding="utf-8") as file:
        json.dump(data, file, indent=2, sort_keys=True)
        file.flush()
        os.fsync(file.fileno())
    os.replace(temporary_path, path)


def _read_json(path: Path) -> dict[str, Any] | None:
    try:
        with path.open("r", encoding="utf-8") as file:
            return json.load(file)
    except (FileNotFoundError, json.JSONDecodeError):
        return None


def _parse_key_values(output: str) -> dict[str, str]:
    return dict(re.findall(r"(?:^|\s)([A-Za-z][A-Za-z0-9_/]*)=(\S+)", output))


def _parse_gpu_count(fields: dict[str, str]) -> int:
    tres_items = fields.get("TRES", "").split(",")
    aggregate = [item for item in tres_items if item.startswith("gres/gpu=")]
    if aggregate:
        return int(aggregate[0].split("=", 1)[1])
    typed = [item for item in tres_items if item.startswith("gres/gpu:")]
    if typed:
        return sum(int(item.rsplit("=", 1)[1]) for item in typed)

    per_node = fields.get("TresPerNode", "")
    matches = re.findall(r"(?:^|,)gpu(?::[^,:=]+)?[:=](\d+)", per_node)
    if matches:
        return sum(int(value) for value in matches)
    return 0


def _parse_end_time(value: str) -> datetime | None:
    if not value or value in {"Unknown", "N/A", "None"}:
        return None
    try:
        return datetime.fromisoformat(value)
    except ValueError:
        return None


class SrunPoolLauncher:
    """Maintain a fixed-width pool of exclusive Slurm steps in one allocation."""

    MANIFEST_VERSION = 1

    def __init__(
        self,
        run_configs: list[RunConfig],
        launcher_cfg: SrunPoolConfig,
        snapshot_path: Path,
        *,
        python_executable: str | Path | None = None,
    ) -> None:
        if not run_configs:
            raise ValueError("SrunPoolLauncher requires at least one RunConfig")
        launcher_cfg.validate()
        self.run_configs = run_configs
        self.cfg = launcher_cfg
        self.snapshot_path = Path(snapshot_path).resolve()
        self.python_executable = Path(python_executable or sys.executable).resolve()
        self.allocation = self._discover_allocation()
        self.meta_exp_dir = self._get_meta_experiment_dir(run_configs)
        batch_key = hashlib.sha256("\n".join(sorted(cfg.id for cfg in run_configs)).encode()).hexdigest()[:12]
        self.pool_dir = self.meta_exp_dir / "srun_pool" / batch_key
        self.manifest_path = self.pool_dir / "manifest.json"
        self.config_dir = self.pool_dir / "configs"
        self.identity_dir = self.pool_dir / "identities"
        self.log_dir = self.pool_dir / "logs"
        self._stop_requested = False
        self._stop_reason = ""
        self._paths_validated = False
        self._previous_signal_handlers: dict[int, Any] = {}
        self.manifest = self._load_or_create_manifest()

    @staticmethod
    def allocation_job_id(launcher_cfg: SrunPoolConfig) -> str:
        job_id = launcher_cfg.allocation_job_id or os.environ.get("SLURM_JOB_ID", "")
        if not job_id:
            raise RuntimeError(
                "srun_pool requires an active Slurm allocation: set SLURM_JOB_ID by running inside "
                "salloc, or provide launcher.allocation_job_id explicitly"
            )
        if not re.fullmatch(r"\d+", str(job_id)):
            raise ValueError(f"Invalid Slurm allocation job ID: {job_id!r}")
        return str(job_id)

    @classmethod
    def resume_snapshot_path(
        cls, run_configs: list[RunConfig], launcher_cfg: SrunPoolConfig
    ) -> Path | None:
        cls.allocation_job_id(launcher_cfg)
        meta_exp_dir = cls._get_meta_experiment_dir(run_configs)
        batch_key = hashlib.sha256("\n".join(sorted(cfg.id for cfg in run_configs)).encode()).hexdigest()[:12]
        manifest_path = meta_exp_dir / "srun_pool" / batch_key / "manifest.json"
        manifest = _read_json(manifest_path)
        if not manifest:
            return None
        snapshot = Path(manifest.get("snapshot_path", ""))
        if not snapshot.is_dir():
            raise RuntimeError(f"Cannot resume srun pool because its snapshot is missing: {snapshot}")
        return snapshot.resolve()

    @staticmethod
    def _get_meta_experiment_dir(run_configs: list[RunConfig]) -> Path:
        parents = {Path(cfg.logger.output_dir).expanduser().resolve().parent for cfg in run_configs}
        if len(parents) != 1:
            formatted = ", ".join(sorted(str(path) for path in parents))
            raise ValueError(f"All srun pool configs must share one meta-experiment directory; got: {formatted}")
        meta_exp_dir = parents.pop()
        meta_exp_dir.mkdir(parents=True, exist_ok=True)
        return meta_exp_dir

    def _discover_allocation(self) -> AllocationInfo:
        job_id = self.allocation_job_id(self.cfg)
        result = subprocess.run(
            ["scontrol", "show", "job", job_id, "-o"],
            check=False,
            capture_output=True,
            text=True,
        )
        if result.returncode != 0:
            raise RuntimeError(f"Unable to inspect Slurm allocation {job_id}: {result.stderr.strip()}")
        fields = _parse_key_values(result.stdout)
        if fields.get("JobState") != "RUNNING":
            raise RuntimeError(
                f"Slurm allocation {job_id} is not RUNNING (state={fields.get('JobState', 'unknown')})"
            )
        owner = fields.get("UserId", "").split("(", 1)[0]
        if owner and owner != getpass.getuser():
            raise PermissionError(f"Slurm allocation {job_id} belongs to {owner}, not {getpass.getuser()}")

        num_nodes = int(fields.get("NumNodes", "0"))
        num_cpus = int(fields.get("NumCPUs", "0"))
        num_gpus = _parse_gpu_count(fields)
        if num_nodes != 1:
            raise ValueError(f"srun_pool currently supports one node, but allocation {job_id} has {num_nodes}")
        requested_cpus = self.cfg.max_parallel * self.cfg.cpus_per_step
        requested_gpus = self.cfg.max_parallel * self.cfg.gpus_per_step
        if requested_cpus > num_cpus:
            raise ValueError(
                f"Pool requests {requested_cpus} CPUs ({self.cfg.max_parallel} x {self.cfg.cpus_per_step}), "
                f"but allocation {job_id} has {num_cpus}"
            )
        if requested_gpus > num_gpus:
            raise ValueError(
                f"Pool requests {requested_gpus} GPUs ({self.cfg.max_parallel} x {self.cfg.gpus_per_step}), "
                f"but allocation {job_id} has {num_gpus}"
            )
        return AllocationInfo(
            job_id=job_id,
            node_list=fields.get("NodeList", os.environ.get("SLURM_JOB_NODELIST", "")),
            num_nodes=num_nodes,
            num_cpus=num_cpus,
            num_gpus=num_gpus,
            end_time=_parse_end_time(fields.get("EndTime", "")),
        )

    def _load_or_create_manifest(self) -> dict[str, Any]:
        existing = _read_json(self.manifest_path)
        if existing:
            if Path(existing.get("snapshot_path", "")).resolve() != self.snapshot_path:
                raise ValueError("Existing manifest belongs to a different code snapshot")
            manifest_ids = set(existing.get("tasks", {}))
            requested_ids = {cfg.id for cfg in self.run_configs}
            if manifest_ids != requested_ids:
                raise ValueError("Existing manifest task IDs do not match this launch")
            allocations = existing.setdefault("allocations", [])
            if not any(item.get("allocation_id") == self.allocation.job_id for item in allocations):
                allocations.append(
                    {
                        "allocation_id": self.allocation.job_id,
                        "node_list": self.allocation.node_list,
                        "started_at": _now(),
                    }
                )
            existing["allocation_id"] = self.allocation.job_id
            existing["node_list"] = self.allocation.node_list
            _atomic_write_json(self.manifest_path, existing)
            return existing

        ids = [cfg.id for cfg in self.run_configs]
        if len(ids) != len(set(ids)):
            duplicates = sorted(run_id for run_id, count in Counter(ids).items() if count > 1)
            raise ValueError(f"RunConfig IDs must be unique within a pool: {duplicates}")

        self.config_dir.mkdir(parents=True, exist_ok=True)
        self.identity_dir.mkdir(parents=True, exist_ok=True)
        self.log_dir.mkdir(parents=True, exist_ok=True)
        pool_created_at = _now()
        tasks: dict[str, dict[str, Any]] = {}
        for run_cfg in self.run_configs:
            stem = self._file_stem(run_cfg.id)
            config_path = self.config_dir / f"{stem}.json"
            _atomic_write_json(config_path, run_cfg.to_typed_dict())
            tasks[run_cfg.id] = {
                "config_path": str(config_path),
                "experiment_dir": str(Path(run_cfg.logger.output_dir).expanduser().resolve()),
                "task_name": run_cfg.task.name,
                "status": "pending",
                "attempt": 0,
                "step_id": "",
                "stdout": "",
                "stderr": "",
                "exit_code": None,
                "slurm_state": "",
                "reason": "",
                "attempts": [],
                "updated_at": _now(),
            }
        manifest: dict[str, Any] = {
            "version": self.MANIFEST_VERSION,
            "launcher_type": "srun_pool",
            "allocation_id": self.allocation.job_id,
            "node_list": self.allocation.node_list,
            "allocations": [
                {
                    "allocation_id": self.allocation.job_id,
                    "node_list": self.allocation.node_list,
                    "started_at": pool_created_at,
                }
            ],
            "snapshot_path": str(self.snapshot_path),
            "python_executable": str(self.python_executable),
            "pool_dir": str(self.pool_dir),
            "created_at": pool_created_at,
            "updated_at": pool_created_at,
            "tasks": tasks,
        }
        _atomic_write_json(self.manifest_path, manifest)
        return manifest

    @staticmethod
    def _file_stem(run_id: str) -> str:
        readable = re.sub(r"[^A-Za-z0-9_.-]+", "-", run_id).strip("-.")[:64] or "run"
        digest = hashlib.sha256(run_id.encode()).hexdigest()[:10]
        return f"{readable}-{digest}"

    def _save_manifest(self) -> None:
        self.manifest["updated_at"] = _now()
        _atomic_write_json(self.manifest_path, self.manifest)

    def _identity_path(self, run_id: str, attempt: int) -> Path:
        return self.identity_dir / f"{self._file_stem(run_id)}.attempt-{attempt}.json"

    def _log_paths(self, run_id: str, attempt: int) -> tuple[Path, Path]:
        base = self.log_dir / f"{self._file_stem(run_id)}.attempt-{attempt}"
        return Path(f"{base}.out"), Path(f"{base}.err")

    def _required_paths(self) -> tuple[list[Path], list[str]]:
        paths = {self.snapshot_path, self.python_executable, self.meta_exp_dir}
        executables: set[str] = set()
        for run_cfg in self.run_configs:
            data_dir = getattr(run_cfg.task, "data_dir", "")
            if data_dir:
                paths.add(Path(data_dir).expanduser().resolve())
            runtime = getattr(run_cfg.interpreter, "container_runtime", "")
            if runtime:
                executables.add(str(runtime))
            superimage_directory = getattr(run_cfg.interpreter, "superimage_directory", "")
            superimage_version = getattr(run_cfg.interpreter, "superimage_version", "")
            if superimage_directory and superimage_version:
                paths.add(
                    Path(superimage_directory).expanduser().resolve()
                    / f"superimage.root.{superimage_version}.sif"
                )
            for overlay in getattr(run_cfg.interpreter, "read_only_overlays", []) or []:
                paths.add(Path(overlay).expanduser().resolve())
            for source in (getattr(run_cfg.interpreter, "read_only_binds", {}) or {}):
                paths.add(Path(source).expanduser().resolve())
        return sorted(paths), sorted(executables)

    def _validate_paths_on_node(self) -> None:
        paths, executables = self._required_paths()
        script = (
            "import json, pathlib, shutil, sys; "
            "spec=json.loads(sys.argv[1]); "
            "missing=[p for p in spec['paths'] if not pathlib.Path(p).exists()]; "
            "missing_exec=[p for p in spec['executables'] if shutil.which(p) is None]; "
            "assert not missing and not missing_exec, "
            "f'paths not visible: {missing}; executables not found: {missing_exec}'"
        )
        command = self._srun_prefix(job_name="dojo-path-check") + [
            str(self.python_executable),
            "-c",
            script,
            json.dumps({"paths": [str(path) for path in paths], "executables": executables}),
        ]
        result = subprocess.run(command, check=False, capture_output=True, text=True)
        if result.returncode != 0:
            raise RuntimeError(
                "Compute-node path validation failed before launching the pool: "
                f"{result.stderr.strip() or result.stdout.strip()}"
            )

    def _srun_prefix(self, *, job_name: str) -> list[str]:
        return [
            "srun",
            f"--jobid={self.allocation.job_id}",
            "--exclusive",
            "--nodes=1",
            f"--ntasks={self.cfg.ntasks_per_step}",
            f"--cpus-per-task={self.cfg.cpus_per_step}",
            f"--gres=gpu:{self.cfg.gpus_per_step}",
            f"--job-name={job_name}",
            f"--chdir={self.snapshot_path}",
        ]

    def _launch(self, run_id: str) -> RunningStep:
        task = self.manifest["tasks"][run_id]
        attempt = int(task["attempt"]) + 1
        stdout_path, stderr_path = self._log_paths(run_id, attempt)
        identity_path = self._identity_path(run_id, attempt)
        job_name = f"dojo-{hashlib.sha256(run_id.encode()).hexdigest()[:8]}-a{attempt}"
        command = self._srun_prefix(job_name=job_name) + [
            f"--output={stdout_path}",
            f"--error={stderr_path}",
            str(self.python_executable),
            "-m",
            "dojo.main_srun_worker",
            task["config_path"],
            str(identity_path),
            "--run-id",
            run_id,
            "--attempt",
            str(attempt),
        ]
        attempt_data = {
            "attempt": attempt,
            "job_name": job_name,
            "status": "launching",
            "step_id": "",
            "stdout": str(stdout_path),
            "stderr": str(stderr_path),
            "identity_path": str(identity_path),
            "exit_code": None,
            "slurm_state": "",
            "started_at": _now(),
            "ended_at": "",
        }
        task.update(
            {
                "status": "launching",
                "attempt": attempt,
                "step_id": "",
                "stdout": str(stdout_path),
                "stderr": str(stderr_path),
                "exit_code": None,
                "slurm_state": "",
                "reason": "",
                "updated_at": _now(),
            }
        )
        task["attempts"].append(attempt_data)
        self._save_manifest()

        env = os.environ.copy()
        snapshot_pythonpath = [
            str(self.snapshot_path / "src"),
            str(self.snapshot_path / "src/dojo/tasks/mlebench/mle-bench"),
        ]
        env["PYTHONPATH"] = os.pathsep.join(snapshot_pythonpath)
        env["PYTHONUNBUFFERED"] = "1"
        try:
            process = subprocess.Popen(command, cwd=self.snapshot_path, env=env)
        except BaseException as error:
            self._finish_task(
                run_id,
                status="failed",
                exit_code=None,
                reason=f"could not start srun: {error}",
            )
            raise
        log.info("Launched run %s attempt %s with local srun PID %s", run_id, attempt, process.pid)
        return RunningStep(run_id=run_id, process=process, identity_path=identity_path)

    def _publish_identity(self, run_id: str, identity_path: Path) -> None:
        identity = _read_json(identity_path)
        if not identity:
            return
        task = self.manifest["tasks"][run_id]
        if int(identity.get("attempt", -1)) != int(task["attempt"]):
            return
        full_step_id = str(identity.get("full_step_id", ""))
        if not full_step_id or task.get("step_id") == full_step_id:
            return
        task["status"] = "running"
        task["step_id"] = full_step_id
        task["updated_at"] = _now()
        attempt = task["attempts"][-1]
        attempt["status"] = "running"
        attempt["step_id"] = full_step_id
        self._save_manifest()

    def _find_active_step(self, task: dict[str, Any]) -> dict[str, str] | None:
        job_name = task["attempts"][-1].get("job_name", "")
        if not job_name:
            return None
        result = subprocess.run(
            ["scontrol", "show", "step", "-o"],
            check=False,
            capture_output=True,
            text=True,
        )
        if result.returncode != 0:
            return None
        for line in result.stdout.splitlines():
            fields = _parse_key_values(line)
            if fields.get("Name") != job_name:
                continue
            step_id = fields.get("StepId", "")
            known_allocations = {
                item.get("allocation_id", "") for item in self.manifest.get("allocations", [])
            }
            if step_id.partition(".")[0] in known_allocations:
                return {
                    "JobIDRaw": step_id,
                    "JobName": job_name,
                    "State": fields.get("State", "RUNNING"),
                    "ExitCode": "",
                }
        return None

    def _finish_task(
        self,
        run_id: str,
        *,
        status: str,
        exit_code: int | None,
        slurm_state: str = "",
        reason: str = "",
    ) -> None:
        task = self.manifest["tasks"][run_id]
        task.update(
            {
                "status": status,
                "exit_code": exit_code,
                "slurm_state": slurm_state,
                "reason": reason,
                "updated_at": _now(),
            }
        )
        attempt = task["attempts"][-1]
        attempt.update(
            {
                "status": status,
                "exit_code": exit_code,
                "slurm_state": slurm_state,
                "ended_at": _now(),
            }
        )
        self._save_manifest()

    @staticmethod
    def _exit_status(exit_code: str) -> int | None:
        try:
            return int(exit_code.split(":", 1)[0])
        except (AttributeError, ValueError):
            return None

    def _accounting_for_task(self, task: dict[str, Any]) -> dict[str, str] | None:
        step_id = task.get("step_id", "")
        if step_id:
            try:
                return query_sacct(step_id).get(step_id)
            except RuntimeError as error:
                log.warning("Could not query accounting for %s: %s", step_id, error)
        return None

    def _complete_local_step(self, running: RunningStep, return_code: int) -> bool:
        self._publish_identity(running.run_id, running.identity_path)
        task = self.manifest["tasks"][running.run_id]
        accounting = self._accounting_for_task(task)
        slurm_state = accounting["State"] if accounting else ""
        exit_code = self._exit_status(accounting["ExitCode"]) if accounting else return_code
        failed_terminal_states = TERMINAL_STATES - {"COMPLETED"}
        # srun is authoritative for process completion; SlurmDBD can briefly lag
        # behind and still report RUNNING/COMPLETING after srun returned zero.
        completed = return_code == 0 and slurm_state not in failed_terminal_states
        if completed:
            self._finish_task(
                running.run_id,
                status="completed",
                exit_code=exit_code,
                slurm_state="COMPLETED",
            )
            return False

        self._finish_task(
            running.run_id,
            status="failed",
            exit_code=exit_code,
            slurm_state=slurm_state or "FAILED",
            reason=f"srun exited with code {return_code}",
        )
        return self._queue_retry(running.run_id)

    def _queue_retry(self, run_id: str) -> bool:
        task = self.manifest["tasks"][run_id]
        failed_attempts = sum(attempt["status"] == "failed" for attempt in task["attempts"])
        if failed_attempts <= self.cfg.max_retries and not self._stop_requested:
            task["status"] = "pending"
            task["reason"] = "retrying after failed attempt"
            task["updated_at"] = _now()
            self._save_manifest()
            return True
        if self.cfg.fail_fast:
            self._stop_requested = True
            self._stop_reason = f"fail_fast after run {run_id} failed"
        return False

    def _recover(self) -> tuple[deque[str], set[str]]:
        pending: deque[str] = deque()
        external_running: set[str] = set()
        try:
            recovery_ids = [
                item.get("allocation_id", "") for item in self.manifest.get("allocations", [])
            ]
            recovery_ids.append(self.allocation.job_id)
            recovery_ids.extend(
                task.get("step_id", "")
                for task in self.manifest["tasks"].values()
                if task.get("step_id")
            )
            allocation_records = query_sacct(recovery_ids)
        except RuntimeError as error:
            log.warning("Could not query allocation accounting during recovery: %s", error)
            allocation_records = {}

        records_by_name = {record["JobName"]: record for record in allocation_records.values()}
        for run_id, task in self.manifest["tasks"].items():
            status = task["status"]
            if status == "completed":
                continue
            if status == "pending":
                task["status"] = "pending"
                pending.append(run_id)
                continue
            if status == "failed":
                failed_attempts = sum(
                    attempt["status"] == "failed" for attempt in task["attempts"]
                )
                if failed_attempts <= self.cfg.max_retries:
                    task["status"] = "pending"
                    pending.append(run_id)
                continue

            identity_path = Path(task["attempts"][-1].get("identity_path", ""))
            self._publish_identity(run_id, identity_path)
            record = None
            if task.get("step_id"):
                record = allocation_records.get(task["step_id"])
            if record is None:
                record = records_by_name.get(task["attempts"][-1].get("job_name", ""))
            if record is None:
                record = self._find_active_step(task)
            if record is not None and "." in record["JobIDRaw"]:
                task["step_id"] = record["JobIDRaw"]
                task["attempts"][-1]["step_id"] = record["JobIDRaw"]

            state = record["State"] if record else ""
            if status == "cancelled":
                if state == "COMPLETED":
                    self._finish_task(
                        run_id,
                        status="completed",
                        exit_code=self._exit_status(record["ExitCode"]),
                        slurm_state=state,
                    )
                elif state in ACTIVE_STATES:
                    task["status"] = "running"
                    task["slurm_state"] = state
                    external_running.add(run_id)
                else:
                    task["status"] = "pending"
                    task["reason"] = "resuming an interrupted attempt"
                    task["updated_at"] = _now()
                    pending.append(run_id)
                continue
            if state == "COMPLETED":
                self._finish_task(
                    run_id,
                    status="completed",
                    exit_code=self._exit_status(record["ExitCode"]),
                    slurm_state=state,
                )
            elif state in TERMINAL_STATES:
                self._finish_task(
                    run_id,
                    status="failed",
                    exit_code=self._exit_status(record["ExitCode"]),
                    slurm_state=state,
                    reason="Recovered a terminal Slurm step",
                )
                if self._queue_retry(run_id):
                    pending.append(run_id)
            elif state in ACTIVE_STATES:
                task["status"] = "running"
                task["slurm_state"] = state
                external_running.add(run_id)
            else:
                self._finish_task(
                    run_id,
                    status="failed",
                    exit_code=None,
                    reason="Controller restarted before the prior Slurm step could be recovered",
                )
                if self._queue_retry(run_id):
                    pending.append(run_id)
        self._save_manifest()
        return pending, external_running

    def _poll_external(self, external_running: set[str], pending: deque[str]) -> None:
        step_to_run = {
            self.manifest["tasks"][run_id].get("step_id", ""): run_id for run_id in external_running
        }
        step_to_run.pop("", None)
        if not step_to_run:
            return
        try:
            records = query_sacct(list(step_to_run))
        except RuntimeError as error:
            log.warning("Could not poll recovered Slurm steps: %s", error)
            return
        for step_id, run_id in step_to_run.items():
            record = records.get(step_id)
            if not record or record["State"] in ACTIVE_STATES:
                continue
            external_running.remove(run_id)
            if record["State"] == "COMPLETED":
                self._finish_task(
                    run_id,
                    status="completed",
                    exit_code=self._exit_status(record["ExitCode"]),
                    slurm_state=record["State"],
                )
            else:
                self._finish_task(
                    run_id,
                    status="failed",
                    exit_code=self._exit_status(record["ExitCode"]),
                    slurm_state=record["State"],
                    reason="Recovered Slurm step ended unsuccessfully",
                )
                if self._queue_retry(run_id):
                    pending.append(run_id)

    def _remaining_seconds(self) -> float | None:
        if self.allocation.end_time is None:
            return None
        end_time = self.allocation.end_time
        now = datetime.now(tz=end_time.tzinfo) if end_time.tzinfo else datetime.now()
        return (end_time - now).total_seconds()

    def _can_launch(self) -> bool:
        remaining = self._remaining_seconds()
        return remaining is None or remaining >= self.cfg.min_remaining_seconds_to_launch

    def _signal_handler(self, signum: int, frame: FrameType | None) -> None:
        del frame
        self._stop_requested = True
        self._stop_reason = f"received signal {signal.Signals(signum).name}"

    def _install_signal_handlers(self) -> None:
        for signum in (signal.SIGINT, signal.SIGTERM):
            self._previous_signal_handlers[signum] = signal.getsignal(signum)
            signal.signal(signum, self._signal_handler)

    def _restore_signal_handlers(self) -> None:
        for signum, handler in self._previous_signal_handlers.items():
            signal.signal(signum, handler)
        self._previous_signal_handlers.clear()

    def _cancel_running(self, running: dict[str, RunningStep], external_running: set[str]) -> None:
        step_ids = []
        for run_id in set(running) | external_running:
            step_id = self.manifest["tasks"][run_id].get("step_id", "")
            if step_id:
                step_ids.append(step_id)
        for step_id in step_ids:
            subprocess.run(["scancel", "--signal=TERM", step_id], check=False)
        for item in running.values():
            if item.process.poll() is None:
                item.process.terminate()

        deadline = time.monotonic() + self.cfg.shutdown_grace_seconds
        for item in running.values():
            remaining = max(0.0, deadline - time.monotonic())
            try:
                item.process.wait(timeout=remaining)
            except subprocess.TimeoutExpired:
                item.process.kill()
                item.process.wait()
        for run_id in set(running) | external_running:
            self._finish_task(
                run_id,
                status="cancelled",
                exit_code=None,
                slurm_state="CANCELLED",
                reason=self._stop_reason or "pool controller stopped",
            )

    def run(self) -> dict[str, Any]:
        if not any(task["status"] != "completed" for task in self.manifest["tasks"].values()):
            log.info("All tasks in %s are already completed", self.manifest_path)

        pending, external_running = self._recover()
        running: dict[str, RunningStep] = {}
        self._install_signal_handlers()
        try:
            while pending or running or external_running:
                if pending and not self._can_launch() and not running and not external_running:
                    self._stop_requested = True
                    self._stop_reason = "allocation has too little time remaining to launch another task"

                while (
                    pending
                    and not self._stop_requested
                    and self._can_launch()
                    and len(running) + len(external_running) < self.cfg.max_parallel
                ):
                    # On controller restart, recovered steps may occupy every
                    # resource slot. Defer this resource-bearing srun until a
                    # slot is available instead of blocking recovery itself.
                    if self.cfg.validate_paths_on_node and not self._paths_validated:
                        self._validate_paths_on_node()
                        self._paths_validated = True
                    run_id = pending.popleft()
                    running[run_id] = self._launch(run_id)

                if self._stop_requested:
                    for run_id in pending:
                        task = self.manifest["tasks"][run_id]
                        task["status"] = "pending"
                        task["reason"] = self._stop_reason
                        task["updated_at"] = _now()
                    pending.clear()
                    self._save_manifest()
                    self._cancel_running(running, external_running)
                    running.clear()
                    external_running.clear()
                    break

                for run_id, item in list(running.items()):
                    self._publish_identity(run_id, item.identity_path)
                    return_code = item.process.poll()
                    if return_code is None:
                        continue
                    del running[run_id]
                    if self._complete_local_step(item, return_code):
                        pending.append(run_id)

                self._poll_external(external_running, pending)

                if self._stop_requested:
                    for run_id in pending:
                        task = self.manifest["tasks"][run_id]
                        task["status"] = "pending"
                        task["reason"] = self._stop_reason
                        task["updated_at"] = _now()
                    pending.clear()
                    self._save_manifest()
                    self._cancel_running(running, external_running)
                    running.clear()
                    external_running.clear()
                    break

                if pending or running or external_running:
                    time.sleep(self.cfg.poll_interval_seconds)
        except BaseException:
            self._stop_requested = True
            self._stop_reason = self._stop_reason or "pool controller failed"
            self._cancel_running(running, external_running)
            raise
        finally:
            self._restore_signal_handlers()

        counts = Counter(task["status"] for task in self.manifest["tasks"].values())
        summary = {
            "manifest_path": str(self.manifest_path),
            "allocation_id": self.allocation.job_id,
            "counts": dict(counts),
            "successful": counts.get("completed", 0) == len(self.manifest["tasks"]),
        }
        log.info("Srun pool finished: %s", summary)
        return summary
