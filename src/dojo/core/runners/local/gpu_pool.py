# Copyright (c) Meta Platforms, Inc. and affiliates.
# All rights reserved.

from __future__ import annotations

import csv
import hashlib
import json
import logging
import os
import re
import shutil
import signal
import socket
import subprocess
import sys
import time
from collections import Counter, deque
from dataclasses import asdict, dataclass
from datetime import datetime
from pathlib import Path
from types import FrameType
from typing import Any, Callable, Mapping, Sequence, TextIO

from dojo.config_dataclasses.launcher.local_gpu_pool import LocalGpuPoolConfig
from dojo.config_dataclasses.run import RunConfig

log = logging.getLogger(__name__)


@dataclass(frozen=True)
class GpuDevice:
    index: int
    uuid: str
    name: str
    memory_mb: int
    compute_mode: str


@dataclass
class RunningWorker:
    run_id: str
    process: subprocess.Popen[Any]
    identity_path: Path
    result_path: Path
    devices: tuple[GpuDevice, ...]
    stdout_file: TextIO
    stderr_file: TextIO
    started_monotonic: float
    timed_out: bool = False


@dataclass
class ExternalWorker:
    run_id: str
    identity_path: Path
    result_path: Path
    devices: tuple[GpuDevice, ...]
    identity: dict[str, Any]


def _seconds_since(timestamp: str) -> float | None:
    try:
        started_at = datetime.fromisoformat(timestamp)
    except (TypeError, ValueError):
        return None
    now = datetime.now(tz=started_at.tzinfo) if started_at.tzinfo else datetime.now()
    return (now - started_at).total_seconds()


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
            value = json.load(file)
        return value if isinstance(value, dict) else None
    except (FileNotFoundError, json.JSONDecodeError, OSError):
        return None


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


def _pid_matches(pid: int, expected_ticks: int) -> bool:
    try:
        fields = (
            Path(f"/proc/{pid}/stat")
            .read_text(encoding="utf-8")
            .rsplit(")", 1)[1]
            .split()
        )
        state = fields[0]
        actual_ticks = int(fields[19])
    except (FileNotFoundError, IndexError, ValueError, OSError):
        return False
    return state != "Z" and actual_ticks == expected_ticks


def _process_matches(identity: Mapping[str, Any]) -> bool:
    if identity.get("host") and identity.get("host") != socket.gethostname():
        return False
    if identity.get("host_boot_id") and identity.get("host_boot_id") != _host_boot_id():
        return False
    try:
        pid = int(identity["pid"])
        expected_ticks = int(identity["process_start_ticks"])
    except (KeyError, TypeError, ValueError):
        return False
    return _pid_matches(pid, expected_ticks)


def discover_gpu_inventory(
    *, run: Callable[..., subprocess.CompletedProcess[str]] = subprocess.run
) -> tuple[GpuDevice, ...]:
    executable = shutil.which("nvidia-smi")
    if executable is None:
        raise RuntimeError(
            "local_gpu_pool requires `nvidia-smi`, but it was not found in PATH"
        )

    mig = run([executable, "-L"], check=False, capture_output=True, text=True)
    if mig.returncode == 0 and any(
        line.lstrip().startswith("MIG ") for line in mig.stdout.splitlines()
    ):
        raise RuntimeError(
            "MIG devices were detected. local_gpu_pool does not yet support MIG or mixed parent/MIG pools."
        )

    result = run(
        [
            executable,
            "--query-gpu=index,uuid,name,memory.total,compute_mode",
            "--format=csv,noheader,nounits",
        ],
        check=False,
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        raise RuntimeError(f"Unable to discover NVIDIA GPUs: {result.stderr.strip()}")

    devices: list[GpuDevice] = []
    for row in csv.reader(result.stdout.splitlines(), skipinitialspace=True):
        if not row:
            continue
        if len(row) != 5:
            raise RuntimeError(f"Unexpected nvidia-smi GPU inventory row: {row!r}")
        try:
            devices.append(
                GpuDevice(
                    index=int(row[0]),
                    uuid=row[1].strip(),
                    name=row[2].strip(),
                    memory_mb=int(row[3]),
                    compute_mode=row[4].strip(),
                )
            )
        except ValueError as error:
            raise RuntimeError(
                f"Invalid nvidia-smi GPU inventory row: {row!r}"
            ) from error
    if not devices:
        raise RuntimeError("nvidia-smi reported no GPUs")
    uuids = [device.uuid for device in devices]
    if len(uuids) != len(set(uuids)):
        raise RuntimeError("nvidia-smi reported duplicate GPU UUIDs")
    return tuple(devices)


def _resolve_device_token(
    token: int | str, inventory: Sequence[GpuDevice]
) -> GpuDevice:
    by_index = {device.index: device for device in inventory}
    value = str(token).strip()
    if isinstance(token, int) or re.fullmatch(r"\d+", value):
        index = int(value)
        if index not in by_index:
            raise ValueError(f"Configured GPU index {index} does not exist")
        return by_index[index]
    if value.startswith("MIG-"):
        raise ValueError("MIG UUIDs are not supported by local_gpu_pool yet")
    matches = [
        device
        for device in inventory
        if device.uuid == value or device.uuid.startswith(value)
    ]
    if len(matches) != 1:
        raise ValueError(
            f"Configured GPU UUID {value!r} does not uniquely identify an available GPU"
        )
    return matches[0]


def normalize_gpu_devices(
    configured_devices: Sequence[int | str] | None,
    inventory: Sequence[GpuDevice],
    host_env: Mapping[str, str],
) -> tuple[GpuDevice, ...]:
    parent_is_set = "CUDA_VISIBLE_DEVICES" in host_env
    parent_value = host_env.get("CUDA_VISIBLE_DEVICES", "")
    parent_tokens = [
        token.strip() for token in parent_value.split(",") if token.strip()
    ]
    if parent_is_set and (not parent_tokens or parent_tokens == ["-1"]):
        raise RuntimeError("The controller CUDA_VISIBLE_DEVICES mask exposes no GPUs")
    parent_devices = (
        tuple(_resolve_device_token(token, inventory) for token in parent_tokens)
        if parent_is_set
        else tuple(inventory)
    )
    if len({device.uuid for device in parent_devices}) != len(parent_devices):
        raise ValueError("CUDA_VISIBLE_DEVICES contains duplicate GPUs")

    selected = (
        tuple(_resolve_device_token(token, inventory) for token in configured_devices)
        if configured_devices is not None
        else parent_devices
    )
    selected_uuids = [device.uuid for device in selected]
    if len(selected_uuids) != len(set(selected_uuids)):
        raise ValueError("launcher.devices contains duplicate GPUs")
    if parent_is_set:
        allowed = {device.uuid for device in parent_devices}
        disallowed = [device.uuid for device in selected if device.uuid not in allowed]
        if disallowed:
            raise ValueError(
                "launcher.devices cannot escape the controller CUDA_VISIBLE_DEVICES mask; "
                f"disallowed UUIDs: {disallowed}"
            )
    if not selected:
        raise ValueError("local_gpu_pool has no GPUs to manage")
    return selected


def format_hardware_description(devices: Sequence[GpuDevice]) -> str:
    groups = Counter((device.name, device.memory_mb) for device in devices)

    def describe(count: int, name: str, memory_mb: int) -> str:
        memory_gib = memory_mb / 1024
        memory = f"{memory_gib:g}"
        if count == 1:
            return f"1 x {name} ({memory} GiB VRAM)"
        return f"{count} x {name} ({memory} GiB VRAM each)"

    parts = [describe(count, name, memory) for (name, memory), count in groups.items()]
    if len(parts) == 1:
        count = len(devices)
        if count == 1:
            return parts[0]
        name, memory_mb = next(iter(groups))
        return f"{count} GPUs: {name} ({memory_mb / 1024:g} GiB VRAM each)"
    return f"{len(devices)} GPUs: " + "; ".join(parts)


class LocalGpuPoolLauncher:
    """Run a fixed-width FIFO pool of local workers with UUID-based CUDA masks."""

    MANIFEST_VERSION = 1

    def __init__(
        self,
        run_configs: list[RunConfig],
        launcher_cfg: LocalGpuPoolConfig,
        snapshot_path: Path,
        *,
        python_executable: str | Path | None = None,
        inventory: Sequence[GpuDevice] | None = None,
    ) -> None:
        if not run_configs:
            raise ValueError("LocalGpuPoolLauncher requires at least one RunConfig")
        launcher_cfg.validate()
        self.run_configs = run_configs
        self.run_configs_by_id = {run_cfg.id: run_cfg for run_cfg in run_configs}
        self.cfg = launcher_cfg
        self.snapshot_path = Path(snapshot_path).resolve()
        self.python_executable = Path(python_executable or sys.executable).absolute()
        self.inventory = (
            tuple(inventory) if inventory is not None else discover_gpu_inventory()
        )
        self.devices = normalize_gpu_devices(
            launcher_cfg.devices, self.inventory, os.environ
        )
        capacity = len(self.devices) // self.cfg.gpus_per_task
        self.max_parallel = (
            self.cfg.max_parallel if self.cfg.max_parallel is not None else capacity
        )
        if capacity < 1:
            raise ValueError(
                f"gpus_per_task={self.cfg.gpus_per_task} exceeds the {len(self.devices)} selected GPUs"
            )
        if self.max_parallel * self.cfg.gpus_per_task > len(self.devices):
            raise ValueError(
                f"Pool requests {self.max_parallel * self.cfg.gpus_per_task} GPU slots "
                f"({self.max_parallel} x {self.cfg.gpus_per_task}), but only {len(self.devices)} are selected"
            )

        self.host = socket.gethostname()
        self.boot_id = _host_boot_id()
        self.meta_exp_dir = self._get_meta_experiment_dir(run_configs)
        batch_key = self._batch_key(run_configs)
        self.pool_dir = self.meta_exp_dir / "local_gpu_pool" / batch_key
        self.manifest_path = self.pool_dir / "manifest.json"
        self.config_dir = self.pool_dir / "configs"
        self.identity_dir = self.pool_dir / "identities"
        self.result_dir = self.pool_dir / "results"
        self.log_dir = self.pool_dir / "logs"
        self._stop_requested = False
        self._stop_reason = ""
        self._paths_validated = False
        self._busy_checked = False
        self._previous_signal_handlers: dict[int, Any] = {}
        self.manifest = self._load_or_create_manifest()
        self.available_devices: deque[GpuDevice] = deque(self.devices)

    @staticmethod
    def _batch_key(run_configs: Sequence[RunConfig]) -> str:
        return hashlib.sha256(
            "\n".join(sorted(cfg.id for cfg in run_configs)).encode()
        ).hexdigest()[:12]

    @classmethod
    def resume_snapshot_path(
        cls, run_configs: list[RunConfig], launcher_cfg: LocalGpuPoolConfig
    ) -> Path | None:
        launcher_cfg.validate()
        meta_exp_dir = cls._get_meta_experiment_dir(run_configs)
        manifest_path = (
            meta_exp_dir
            / "local_gpu_pool"
            / cls._batch_key(run_configs)
            / "manifest.json"
        )
        manifest = _read_json(manifest_path)
        if not manifest:
            return None
        snapshot = Path(manifest.get("snapshot_path", ""))
        if not snapshot.is_dir():
            raise RuntimeError(
                f"Cannot resume local GPU pool because its snapshot is missing: {snapshot}"
            )
        return snapshot.resolve()

    @staticmethod
    def _get_meta_experiment_dir(run_configs: Sequence[RunConfig]) -> Path:
        parents = {
            Path(cfg.logger.output_dir).expanduser().resolve().parent
            for cfg in run_configs
        }
        if len(parents) != 1:
            formatted = ", ".join(sorted(str(path) for path in parents))
            raise ValueError(
                f"All local GPU pool configs must share one meta-experiment directory; got: {formatted}"
            )
        meta_exp_dir = parents.pop()
        meta_exp_dir.mkdir(parents=True, exist_ok=True)
        return meta_exp_dir

    @staticmethod
    def _file_stem(run_id: str) -> str:
        readable = re.sub(r"[^A-Za-z0-9_.-]+", "-", run_id).strip("-.")[:64] or "run"
        digest = hashlib.sha256(run_id.encode()).hexdigest()[:10]
        return f"{readable}-{digest}"

    def _load_or_create_manifest(self) -> dict[str, Any]:
        existing = _read_json(self.manifest_path)
        if existing:
            if existing.get("launcher_type") != "local_gpu_pool":
                raise ValueError(
                    f"Unexpected launcher manifest at {self.manifest_path}"
                )
            if Path(existing.get("snapshot_path", "")).resolve() != self.snapshot_path:
                raise ValueError(
                    "Existing manifest belongs to a different code snapshot"
                )
            if set(existing.get("tasks", {})) != {cfg.id for cfg in self.run_configs}:
                raise ValueError("Existing manifest task IDs do not match this launch")
            current_inventory = [asdict(device) for device in self.inventory]
            existing.setdefault("inventory", current_inventory)
            existing["current_inventory"] = current_inventory
            inventory_history = existing.setdefault("inventory_history", [])
            current_record = {
                "host": self.host,
                "host_boot_id": self.boot_id,
                "inventory": current_inventory,
            }
            if not inventory_history or any(
                inventory_history[-1].get(name) != current_record[name]
                for name in current_record
            ):
                inventory_history.append({**current_record, "discovered_at": _now()})
            existing["selected_gpu_uuids"] = [device.uuid for device in self.devices]
            existing["host"] = self.host
            existing["host_boot_id"] = self.boot_id
            self._save_manifest_data(existing)
            return existing

        ids = [cfg.id for cfg in self.run_configs]
        if len(ids) != len(set(ids)):
            duplicates = sorted(
                run_id for run_id, count in Counter(ids).items() if count > 1
            )
            raise ValueError(
                f"RunConfig IDs must be unique within a pool: {duplicates}"
            )

        for directory in (
            self.config_dir,
            self.identity_dir,
            self.result_dir,
            self.log_dir,
        ):
            directory.mkdir(parents=True, exist_ok=True)
        tasks: dict[str, dict[str, Any]] = {}
        for run_cfg in self.run_configs:
            config_path = self.config_dir / f"{self._file_stem(run_cfg.id)}.json"
            _atomic_write_json(config_path, run_cfg.to_typed_dict())
            tasks[run_cfg.id] = {
                "config_path": str(config_path),
                "experiment_dir": str(
                    Path(run_cfg.logger.output_dir).expanduser().resolve()
                ),
                "task_name": run_cfg.task.name,
                "status": "pending",
                "attempt": 0,
                "execution_id": "",
                "gpu_uuids": [],
                "gpu_indices": [],
                "stdout": "",
                "stderr": "",
                "exit_code": None,
                "reason": "",
                "attempts": [],
                "updated_at": _now(),
            }
        created_at = _now()
        inventory = [asdict(device) for device in self.inventory]
        manifest = {
            "version": self.MANIFEST_VERSION,
            "launcher_type": "local_gpu_pool",
            "host": self.host,
            "host_boot_id": self.boot_id,
            "snapshot_path": str(self.snapshot_path),
            "python_executable": str(self.python_executable),
            "pool_dir": str(self.pool_dir),
            "inventory": inventory,
            "current_inventory": inventory,
            "inventory_history": [
                {
                    "host": self.host,
                    "host_boot_id": self.boot_id,
                    "inventory": inventory,
                    "discovered_at": created_at,
                }
            ],
            "selected_gpu_uuids": [device.uuid for device in self.devices],
            "gpus_per_task": self.cfg.gpus_per_task,
            "max_parallel": self.max_parallel,
            "created_at": created_at,
            "updated_at": created_at,
            "tasks": tasks,
        }
        self._save_manifest_data(manifest)
        return manifest

    def _save_manifest_data(self, manifest: dict[str, Any]) -> None:
        manifest["updated_at"] = _now()
        _atomic_write_json(self.manifest_path, manifest)

    def _save_manifest(self) -> None:
        self._save_manifest_data(self.manifest)

    def _attempt_paths(
        self, run_id: str, attempt: int
    ) -> tuple[Path, Path, Path, Path]:
        base = f"{self._file_stem(run_id)}.attempt-{attempt}"
        return (
            self.identity_dir / f"{base}.json",
            self.result_dir / f"{base}.json",
            self.log_dir / f"{base}.out",
            self.log_dir / f"{base}.err",
        )

    def _devices_from_uuids(self, uuids: Sequence[str]) -> tuple[GpuDevice, ...]:
        by_uuid = {device.uuid: device for device in self.inventory}
        try:
            devices = tuple(by_uuid[uuid] for uuid in uuids)
        except KeyError as error:
            raise RuntimeError(
                f"A recovered attempt refers to unavailable GPU {error.args[0]}"
            ) from error
        selected = {device.uuid for device in self.devices}
        disallowed = [device.uuid for device in devices if device.uuid not in selected]
        if disallowed:
            raise RuntimeError(
                f"Recovered workers use GPUs outside the current launcher.devices selection: {disallowed}"
            )
        if len(devices) != self.cfg.gpus_per_task or len(
            {device.uuid for device in devices}
        ) != len(devices):
            raise RuntimeError(
                "Recovered attempt GPU assignment does not match the current gpus_per_task setting"
            )
        return devices

    def _allocate_devices(self) -> tuple[GpuDevice, ...]:
        if len(self.available_devices) < self.cfg.gpus_per_task:
            raise RuntimeError("Not enough available GPUs for a local worker")
        return tuple(
            self.available_devices.popleft() for _ in range(self.cfg.gpus_per_task)
        )

    def _release_devices(self, devices: Sequence[GpuDevice]) -> None:
        in_queue = {device.uuid for device in self.available_devices}
        for device in devices:
            if device.uuid in in_queue:
                raise RuntimeError(f"GPU {device.uuid} was released twice")
            self.available_devices.append(device)
            in_queue.add(device.uuid)

    def _required_paths(self) -> set[Path]:
        paths = {self.snapshot_path, self.python_executable, self.meta_exp_dir}
        for run_cfg in self.run_configs:
            runtime = getattr(run_cfg.interpreter, "container_runtime", "")
            if runtime:
                if runtime != "singularity":
                    raise ValueError(
                        "local_gpu_pool currently requires the Singularity "
                        f"container runtime, got {runtime!r}"
                    )
                if shutil.which("singularity") is None:
                    raise RuntimeError(
                        "local_gpu_pool requires `singularity` for containerized "
                        "interpreters, but it was not found in PATH"
                    )
            configured_env = getattr(run_cfg.interpreter, "env", {}) or {}
            if (
                "CUDA_DEVICE_ORDER" in configured_env
                and str(configured_env["CUDA_DEVICE_ORDER"]) != "PCI_BUS_ID"
            ):
                raise ValueError(
                    "interpreter.env must not override launcher-assigned CUDA_DEVICE_ORDER"
                )
            data_dir = getattr(run_cfg.task, "data_dir", "")
            if data_dir:
                paths.add(Path(data_dir).expanduser().resolve())
            image_dir = getattr(run_cfg.interpreter, "superimage_directory", "")
            image_version = getattr(run_cfg.interpreter, "superimage_version", "")
            if image_dir and image_version:
                paths.add(
                    Path(image_dir).expanduser().resolve()
                    / f"superimage.root.{image_version}.sif"
                )
            for overlay in getattr(run_cfg.interpreter, "read_only_overlays", []) or []:
                paths.add(Path(overlay).expanduser().resolve())
            for source in getattr(run_cfg.interpreter, "read_only_binds", {}) or {}:
                paths.add(Path(source).expanduser().resolve())
        return paths

    def _validate_paths(self) -> None:
        missing = [
            str(path) for path in sorted(self._required_paths()) if not path.exists()
        ]
        if missing:
            raise FileNotFoundError(
                f"Required local GPU pool paths do not exist: {missing}"
            )

    def _warn_busy_devices(self) -> None:
        if self._busy_checked:
            return
        self._busy_checked = True
        executable = shutil.which("nvidia-smi")
        if executable is None:
            return
        try:
            result = subprocess.run(
                [
                    executable,
                    "--query-compute-apps=gpu_uuid,pid,process_name,used_gpu_memory",
                    "--format=csv,noheader,nounits",
                ],
                check=False,
                capture_output=True,
                text=True,
            )
        except OSError as error:
            log.warning("Could not inspect existing GPU compute processes: %s", error)
            return
        selected = {device.uuid for device in self.devices}
        busy = [
            line
            for line in result.stdout.splitlines()
            if line.split(",", 1)[0].strip() in selected
        ]
        if busy:
            log.warning(
                "Selected GPUs already have compute processes. local_gpu_pool assumes exclusive deployment; "
                "verify these processes belong to the pool before continuing: %s",
                busy,
            )

    def _launch(self, run_id: str, devices: tuple[GpuDevice, ...]) -> RunningWorker:
        configured_env = (
            getattr(self.run_configs_by_id[run_id].interpreter, "env", {}) or {}
        )
        assigned_mask = ",".join(device.uuid for device in devices)
        if (
            "CUDA_VISIBLE_DEVICES" in configured_env
            and str(configured_env["CUDA_VISIBLE_DEVICES"]) != assigned_mask
        ):
            raise ValueError(
                "interpreter.env cannot override launcher-assigned CUDA_VISIBLE_DEVICES: "
                f"configured {configured_env['CUDA_VISIBLE_DEVICES']!r}, assigned {assigned_mask!r}"
            )
        task = self.manifest["tasks"][run_id]
        attempt = int(task["attempt"]) + 1
        identity_path, result_path, stdout_path, stderr_path = self._attempt_paths(
            run_id, attempt
        )
        command = [
            str(self.python_executable),
            "-m",
            "dojo.main_local_worker",
            task["config_path"],
            str(identity_path),
            str(result_path),
            "--run-id",
            run_id,
            "--attempt",
            str(attempt),
        ]
        device_metadata = [asdict(device) for device in devices]
        attempt_data = {
            "attempt": attempt,
            "status": "launching",
            "execution_id": "",
            "pid": None,
            "process_start_ticks": None,
            "gpu_uuids": [device.uuid for device in devices],
            "gpu_indices": [device.index for device in devices],
            "devices": device_metadata,
            "hardware_description": format_hardware_description(devices),
            "stdout": str(stdout_path),
            "stderr": str(stderr_path),
            "identity_path": str(identity_path),
            "result_path": str(result_path),
            "exit_code": None,
            "started_at": _now(),
            "ended_at": "",
            "reason": "",
        }
        task.update(
            {
                "status": "launching",
                "attempt": attempt,
                "execution_id": "",
                "gpu_uuids": attempt_data["gpu_uuids"],
                "gpu_indices": attempt_data["gpu_indices"],
                "stdout": str(stdout_path),
                "stderr": str(stderr_path),
                "exit_code": None,
                "reason": "",
                "updated_at": _now(),
            }
        )
        task["attempts"].append(attempt_data)
        self._save_manifest()

        env = os.environ.copy()
        env.update(
            {
                "CUDA_DEVICE_ORDER": "PCI_BUS_ID",
                "CUDA_VISIBLE_DEVICES": assigned_mask,
                "DOJO_LAUNCHER_TYPE": "local_gpu_pool",
                "DOJO_GPU_UUIDS": ",".join(device.uuid for device in devices),
                "DOJO_HARDWARE_DESCRIPTION": format_hardware_description(devices),
                "DOJO_ATTEMPT": str(attempt),
                "DOJO_EXECUTION_HOST": self.host,
                "DOJO_WORKER_IDENTITY_PATH": str(identity_path),
                "PYTHONPATH": os.pathsep.join(
                    [
                        str(self.snapshot_path / "src"),
                        str(self.snapshot_path / "src/dojo/tasks/mlebench/mle-bench"),
                    ]
                ),
                "PYTHONUNBUFFERED": "1",
            }
        )
        stdout_file = stdout_path.open("w", encoding="utf-8")
        stderr_file = stderr_path.open("w", encoding="utf-8")
        try:
            process = subprocess.Popen(
                command,
                cwd=self.snapshot_path,
                env=env,
                stdout=stdout_file,
                stderr=stderr_file,
                start_new_session=True,
            )
        except BaseException:
            stdout_file.close()
            stderr_file.close()
            self._finish_task(
                run_id,
                status="failed",
                exit_code=None,
                reason="could not start local worker",
            )
            raise

        try:
            ticks = _process_start_ticks(process.pid)
            execution_id = (
                f"{self.host}:{process.pid}:"
                f"{ticks if ticks is not None else 'unknown'}:a{attempt}"
            )
            attempt_data.update(
                {
                    "status": "running",
                    "execution_id": execution_id,
                    "pid": process.pid,
                    "process_start_ticks": ticks,
                }
            )
            task.update(
                {
                    "status": "running",
                    "execution_id": execution_id,
                    "updated_at": _now(),
                }
            )
            self._save_manifest()
        except BaseException:
            try:
                os.killpg(process.pid, signal.SIGTERM)
                process.wait(timeout=self.cfg.shutdown_grace_seconds)
            except ProcessLookupError:
                pass
            except subprocess.TimeoutExpired:
                try:
                    os.killpg(process.pid, signal.SIGKILL)
                except ProcessLookupError:
                    pass
                process.wait()
            finally:
                stdout_file.close()
                stderr_file.close()
            raise
        log.info(
            "Launched run %s attempt %s as PID %s on GPUs %s",
            run_id,
            attempt,
            process.pid,
            attempt_data["gpu_uuids"],
        )
        return RunningWorker(
            run_id=run_id,
            process=process,
            identity_path=identity_path,
            result_path=result_path,
            devices=devices,
            stdout_file=stdout_file,
            stderr_file=stderr_file,
            started_monotonic=time.monotonic(),
        )

    def _publish_identity(
        self, run_id: str, identity_path: Path
    ) -> dict[str, Any] | None:
        identity = _read_json(identity_path)
        if not identity:
            return None
        task = self.manifest["tasks"][run_id]
        if int(identity.get("attempt", -1)) != int(task["attempt"]):
            return None
        attempt = task["attempts"][-1]
        changed = False
        for name in (
            "execution_id",
            "pid",
            "pgid",
            "process_start_ticks",
            "container_pid",
            "container_pgid",
            "container_process_start_ticks",
        ):
            if name in identity and attempt.get(name) != identity[name]:
                attempt[name] = identity[name]
                changed = True
        if (
            identity.get("execution_id")
            and task.get("execution_id") != identity["execution_id"]
        ):
            task["execution_id"] = identity["execution_id"]
            changed = True
        if changed:
            task["status"] = "running"
            task["updated_at"] = _now()
            self._save_manifest()
        return identity

    def _finish_task(
        self,
        run_id: str,
        *,
        status: str,
        exit_code: int | None,
        reason: str = "",
        result: Mapping[str, Any] | None = None,
    ) -> None:
        task = self.manifest["tasks"][run_id]
        task.update(
            {
                "status": status,
                "exit_code": exit_code,
                "reason": reason,
                "updated_at": _now(),
            }
        )
        attempt = task["attempts"][-1]
        attempt.update(
            {
                "status": status,
                "exit_code": exit_code,
                "ended_at": (result or {}).get("ended_at", _now()),
                "reason": reason,
            }
        )
        if result:
            attempt["result"] = dict(result)
        self._save_manifest()

    def _queue_retry(self, run_id: str) -> bool:
        task = self.manifest["tasks"][run_id]
        failed_attempts = sum(
            attempt["status"] == "failed" for attempt in task["attempts"]
        )
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

    def _settle_result(
        self,
        run_id: str,
        result_path: Path,
        return_code: int | None,
        *,
        reason: str = "",
    ) -> bool:
        result = _read_json(result_path)
        completed = bool(
            result and result.get("status") == "completed" and return_code in (None, 0)
        )
        if completed:
            self._finish_task(
                run_id,
                status="completed",
                exit_code=int(result.get("exit_code", 0)),
                result=result,
            )
            return False
        result_reason = str((result or {}).get("exception_summary", "")).strip()
        self._finish_task(
            run_id,
            status="failed",
            exit_code=(
                return_code
                if return_code is not None
                else (result or {}).get("exit_code")
            ),
            reason=reason
            or result_reason
            or "worker exited without a successful terminal result",
            result=result,
        )
        return self._queue_retry(run_id)

    def _recover(self) -> tuple[deque[str], dict[str, ExternalWorker]]:
        pending: deque[str] = deque()
        external: dict[str, ExternalWorker] = {}
        reserved: set[str] = set()
        for run_id, task in self.manifest["tasks"].items():
            status = task["status"]
            if status == "completed":
                continue
            if status == "pending":
                pending.append(run_id)
                continue
            if status == "failed":
                failed_attempts = sum(
                    attempt["status"] == "failed"
                    for attempt in task.get("attempts", [])
                )
                if failed_attempts <= self.cfg.max_retries:
                    task["status"] = "pending"
                    pending.append(run_id)
                continue
            if status == "cancelled":
                task["status"] = "pending"
                task["reason"] = "resuming a controller-cancelled task"
                pending.append(run_id)
                continue

            attempt = task["attempts"][-1]
            identity_path = Path(attempt.get("identity_path", ""))
            result_path = Path(attempt.get("result_path", ""))
            identity = self._publish_identity(run_id, identity_path) or {}
            if _process_matches(identity):
                devices = self._devices_from_uuids(attempt.get("gpu_uuids", []))
                overlap = reserved.intersection(device.uuid for device in devices)
                if overlap:
                    raise RuntimeError(
                        f"Recovered workers claim the same GPU UUIDs: {sorted(overlap)}"
                    )
                reserved.update(device.uuid for device in devices)
                external[run_id] = ExternalWorker(
                    run_id=run_id,
                    identity_path=identity_path,
                    result_path=result_path,
                    devices=devices,
                    identity=identity,
                )
                task["status"] = "running"
                continue

            self._cleanup_orphan_container(identity)
            result = _read_json(result_path)
            if result and result.get("status") == "completed":
                self._finish_task(
                    run_id, status="completed", exit_code=0, result=result
                )
                continue

            self._finish_task(
                run_id,
                status="failed",
                exit_code=(result or {}).get("exit_code"),
                reason="controller restarted after the prior local worker disappeared",
                result=result,
            )
            if self._queue_retry(run_id):
                pending.append(run_id)

        self.available_devices = deque(
            device for device in self.devices if device.uuid not in reserved
        )
        self._save_manifest()
        return pending, external

    @staticmethod
    def _close_worker_logs(worker: RunningWorker) -> None:
        worker.stdout_file.close()
        worker.stderr_file.close()

    def _signal_identity(self, identity: Mapping[str, Any], signum: int) -> None:
        if not _process_matches(identity):
            return
        try:
            pgid = int(identity.get("pgid") or identity["pid"])
            os.killpg(pgid, signum)
        except (KeyError, TypeError, ValueError, ProcessLookupError, PermissionError):
            pass

    @staticmethod
    def _container_matches(identity: Mapping[str, Any]) -> bool:
        try:
            pid = int(identity["container_pid"])
            expected_ticks = int(identity["container_process_start_ticks"])
        except (KeyError, TypeError, ValueError):
            return False
        return _pid_matches(pid, expected_ticks)

    @classmethod
    def _signal_container(cls, identity: Mapping[str, Any], signum: int) -> None:
        if not cls._container_matches(identity):
            return
        try:
            pgid = int(identity["container_pgid"])
            os.killpg(pgid, signum)
        except (KeyError, TypeError, ValueError, ProcessLookupError, PermissionError):
            pass

    def _cleanup_orphan_container(self, identity: Mapping[str, Any]) -> None:
        if not self._container_matches(identity):
            return
        log.warning(
            "Cleaning orphaned Singularity process group %s before reusing its GPU slot",
            identity.get("container_pgid"),
        )
        self._signal_container(identity, signal.SIGTERM)
        deadline = time.monotonic() + self.cfg.shutdown_grace_seconds
        while self._container_matches(identity) and time.monotonic() < deadline:
            time.sleep(min(0.1, max(0.0, deadline - time.monotonic())))
        if self._container_matches(identity):
            self._signal_container(identity, signal.SIGKILL)
            kill_deadline = time.monotonic() + 5
            while (
                self._container_matches(identity) and time.monotonic() < kill_deadline
            ):
                time.sleep(0.05)
        if self._container_matches(identity):
            raise RuntimeError(
                "Could not clean a recovered orphan Singularity process; refusing to reuse its GPU slot"
            )

    def _terminate_worker(self, worker: RunningWorker) -> int:
        identity = self._publish_identity(worker.run_id, worker.identity_path) or {
            "host": self.host,
            "host_boot_id": self.boot_id,
            "pid": worker.process.pid,
            "pgid": worker.process.pid,
            "process_start_ticks": _process_start_ticks(worker.process.pid),
        }
        try:
            os.killpg(worker.process.pid, signal.SIGTERM)
        except ProcessLookupError:
            pass
        try:
            return worker.process.wait(timeout=self.cfg.shutdown_grace_seconds)
        except subprocess.TimeoutExpired:
            self._signal_container(identity, signal.SIGKILL)
            try:
                os.killpg(worker.process.pid, signal.SIGKILL)
            except ProcessLookupError:
                pass
            return worker.process.wait()

    def _poll_external(
        self, external: dict[str, ExternalWorker], pending: deque[str]
    ) -> None:
        for run_id, worker in list(external.items()):
            identity = (
                self._publish_identity(run_id, worker.identity_path) or worker.identity
            )
            worker.identity = identity
            if _process_matches(identity):
                timeout = self.cfg.task_timeout_seconds
                age = _seconds_since(str(identity.get("started_at", "")))
                if timeout is None or age is None or age < timeout:
                    continue
                self._signal_identity(identity, signal.SIGTERM)
                deadline = time.monotonic() + self.cfg.shutdown_grace_seconds
                while _process_matches(identity) and time.monotonic() < deadline:
                    time.sleep(min(0.1, max(0.0, deadline - time.monotonic())))
                if _process_matches(identity):
                    self._signal_container(identity, signal.SIGKILL)
                    self._signal_identity(identity, signal.SIGKILL)
                reason = f"task exceeded timeout of {timeout:g} seconds during recovery"
            else:
                reason = ""
            if _process_matches(identity):
                continue
            del external[run_id]
            if self._settle_result(run_id, worker.result_path, None, reason=reason):
                pending.append(run_id)
            self._release_devices(worker.devices)

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

    def _cancel_all(
        self, running: dict[str, RunningWorker], external: dict[str, ExternalWorker]
    ) -> None:
        for run_id, worker in list(running.items()):
            return_code = self._terminate_worker(worker)
            self._close_worker_logs(worker)
            self._finish_task(
                run_id,
                status="cancelled",
                exit_code=return_code,
                reason=self._stop_reason or "pool controller stopped",
                result=_read_json(worker.result_path),
            )
            self._release_devices(worker.devices)
        for run_id, worker in list(external.items()):
            self._signal_identity(worker.identity, signal.SIGTERM)
        deadline = time.monotonic() + self.cfg.shutdown_grace_seconds
        while time.monotonic() < deadline:
            if not any(
                _process_matches(worker.identity) for worker in external.values()
            ):
                break
            if external:
                time.sleep(min(0.1, max(0.0, deadline - time.monotonic())))
        for run_id, worker in list(external.items()):
            if _process_matches(worker.identity):
                self._signal_container(worker.identity, signal.SIGKILL)
                self._signal_identity(worker.identity, signal.SIGKILL)
            self._finish_task(
                run_id,
                status="cancelled",
                exit_code=None,
                reason=self._stop_reason or "pool controller stopped",
                result=_read_json(worker.result_path),
            )
            self._release_devices(worker.devices)
            del external[run_id]

    def run(self) -> dict[str, Any]:
        pending, external = self._recover()
        running: dict[str, RunningWorker] = {}
        self._install_signal_handlers()
        try:
            while pending or running or external:
                while (
                    pending
                    and not self._stop_requested
                    and len(running) + len(external) < self.max_parallel
                    and len(self.available_devices) >= self.cfg.gpus_per_task
                ):
                    if not self._paths_validated:
                        self._validate_paths()
                        self._warn_busy_devices()
                        self._paths_validated = True
                    run_id = pending.popleft()
                    devices = self._allocate_devices()
                    try:
                        running[run_id] = self._launch(run_id, devices)
                    except BaseException:
                        self._release_devices(devices)
                        raise

                if self._stop_requested:
                    for run_id in pending:
                        task = self.manifest["tasks"][run_id]
                        task["status"] = "pending"
                        task["reason"] = self._stop_reason
                        task["updated_at"] = _now()
                    pending.clear()
                    self._save_manifest()
                    self._cancel_all(running, external)
                    running.clear()
                    external.clear()
                    break

                for run_id, worker in list(running.items()):
                    self._publish_identity(run_id, worker.identity_path)
                    return_code = worker.process.poll()
                    timeout = self.cfg.task_timeout_seconds
                    if (
                        return_code is None
                        and timeout is not None
                        and time.monotonic() - worker.started_monotonic >= timeout
                    ):
                        worker.timed_out = True
                        return_code = self._terminate_worker(worker)
                    if return_code is None:
                        continue
                    del running[run_id]
                    self._close_worker_logs(worker)
                    if self._settle_result(
                        run_id,
                        worker.result_path,
                        return_code,
                        reason=(
                            f"task exceeded timeout of {self.cfg.task_timeout_seconds:g} seconds"
                            if worker.timed_out
                            and self.cfg.task_timeout_seconds is not None
                            else ""
                        ),
                    ):
                        pending.append(run_id)
                    self._release_devices(worker.devices)

                self._poll_external(external, pending)
                if pending or running or external:
                    time.sleep(self.cfg.poll_interval_seconds)
        except BaseException:
            self._stop_requested = True
            self._stop_reason = self._stop_reason or "pool controller failed"
            self._cancel_all(running, external)
            raise
        finally:
            self._restore_signal_handlers()

        counts = Counter(task["status"] for task in self.manifest["tasks"].values())
        summary = {
            "manifest_path": str(self.manifest_path),
            "launcher_type": "local_gpu_pool",
            "counts": dict(counts),
            "successful": counts.get("completed", 0) == len(self.manifest["tasks"]),
        }
        log.info("Local GPU pool finished: %s", summary)
        return summary
