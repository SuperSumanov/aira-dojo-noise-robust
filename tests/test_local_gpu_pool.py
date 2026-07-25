from __future__ import annotations

import json
import os
import signal
import subprocess
import sys
import time
from pathlib import Path
from types import SimpleNamespace

import pytest

from dojo.config_dataclasses.launcher.local_gpu_pool import LocalGpuPoolConfig
from dojo.core.runners.local import gpu_pool
from dojo.core.runners.local.gpu_pool import (
    GpuDevice,
    LocalGpuPoolLauncher,
    discover_gpu_inventory,
    format_hardware_description,
    normalize_gpu_devices,
)
from dojo.core.runners.slurm.manifest import get_pool_tasks


@pytest.fixture
def inventory() -> tuple[GpuDevice, ...]:
    return (
        GpuDevice(0, "GPU-3090-a", "NVIDIA GeForce RTX 3090", 24576, "Default"),
        GpuDevice(1, "GPU-3090-b", "NVIDIA GeForce RTX 3090", 24576, "Default"),
        GpuDevice(2, "GPU-2080-a", "NVIDIA GeForce RTX 2080 Ti", 11264, "Default"),
    )


def test_normalize_gpu_devices_respects_parent_mask(
    inventory: tuple[GpuDevice, ...],
) -> None:
    selected = normalize_gpu_devices(None, inventory, {"CUDA_VISIBLE_DEVICES": "2,0"})
    assert [device.uuid for device in selected] == ["GPU-2080-a", "GPU-3090-a"]

    selected = normalize_gpu_devices(
        ["GPU-3090-a"], inventory, {"CUDA_VISIBLE_DEVICES": "2,0"}
    )
    assert [device.index for device in selected] == [0]

    with pytest.raises(ValueError, match="cannot escape"):
        normalize_gpu_devices([1], inventory, {"CUDA_VISIBLE_DEVICES": "2,0"})


def test_discover_gpu_inventory_parses_nvidia_smi(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(gpu_pool.shutil, "which", lambda name: "/usr/bin/nvidia-smi")
    calls: list[list[str]] = []

    def fake_run(
        command: list[str], **kwargs: object
    ) -> subprocess.CompletedProcess[str]:
        calls.append(command)
        if command[-1] == "-L":
            return subprocess.CompletedProcess(
                command, 0, stdout="GPU 0: RTX 3090 (UUID: GPU-a)\n"
            )
        return subprocess.CompletedProcess(
            command,
            0,
            stdout="0, GPU-a, NVIDIA GeForce RTX 3090, 24576, Default\n",
            stderr="",
        )

    discovered = discover_gpu_inventory(run=fake_run)

    assert discovered == (
        GpuDevice(0, "GPU-a", "NVIDIA GeForce RTX 3090", 24576, "Default"),
    )
    assert len(calls) == 2


def test_discover_gpu_inventory_rejects_mig(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(gpu_pool.shutil, "which", lambda name: "/usr/bin/nvidia-smi")

    def fake_run(
        command: list[str], **kwargs: object
    ) -> subprocess.CompletedProcess[str]:
        return subprocess.CompletedProcess(
            command,
            0,
            stdout="GPU 0: A100 (UUID: GPU-a)\n  MIG 1g.5gb Device 0: (UUID: MIG-a)\n",
            stderr="",
        )

    with pytest.raises(RuntimeError, match="MIG devices were detected"):
        discover_gpu_inventory(run=fake_run)


def test_normalize_gpu_devices_rejects_duplicates_and_empty_masks(
    inventory: tuple[GpuDevice, ...],
) -> None:
    with pytest.raises(ValueError, match="duplicate"):
        normalize_gpu_devices([0, "GPU-3090-a"], inventory, {})
    with pytest.raises(RuntimeError, match="exposes no GPUs"):
        normalize_gpu_devices(None, inventory, {"CUDA_VISIBLE_DEVICES": "-1"})


def test_hardware_description_reports_the_assigned_slot(
    inventory: tuple[GpuDevice, ...],
) -> None:
    assert format_hardware_description([inventory[0]]) == (
        "1 x NVIDIA GeForce RTX 3090 (24 GiB VRAM)"
    )
    assert format_hardware_description(inventory[:2]) == (
        "2 GPUs: NVIDIA GeForce RTX 3090 (24 GiB VRAM each)"
    )
    mixed = format_hardware_description([inventory[0], inventory[2]])
    assert mixed == (
        "2 GPUs: 1 x NVIDIA GeForce RTX 3090 (24 GiB VRAM); "
        "1 x NVIDIA GeForce RTX 2080 Ti (11 GiB VRAM)"
    )


def _make_fake_python(tmp_path: Path) -> Path:
    executable = tmp_path / "fake-python"
    executable.write_text(
        "#!/usr/bin/env python3\n"
        "import json, os, signal, socket, sys, time\n"
        "identity, result = sys.argv[4], sys.argv[5]\n"
        "run_id = sys.argv[sys.argv.index('--run-id') + 1]\n"
        "attempt = int(sys.argv[sys.argv.index('--attempt') + 1])\n"
        "pid = os.getpid()\n"
        "stat = open(f'/proc/{pid}/stat').read()\n"
        "ticks = int(stat.rsplit(')', 1)[1].split()[19])\n"
        "boot = open('/proc/sys/kernel/random/boot_id').read().strip()\n"
        "execution_id = f'{socket.gethostname()}:{pid}:{ticks}:a{attempt}'\n"
        "with open(identity, 'w') as file:\n"
        "    json.dump({'run_id': run_id, 'attempt': attempt, 'execution_id': execution_id, "
        "'host': socket.gethostname(), 'host_boot_id': boot, 'pid': pid, 'pgid': os.getpgid(pid), "
        "'process_start_ticks': ticks, 'gpu_uuids': os.environ['DOJO_GPU_UUIDS'].split(',')}, file)\n"
        "event = {'event': 'start', 'run_id': run_id, 'attempt': attempt, "
        "'time': time.time(), 'mask': os.environ['CUDA_VISIBLE_DEVICES'], "
        "'hardware': os.environ['DOJO_HARDWARE_DESCRIPTION']}\n"
        "with open(os.environ['POOL_TEST_EVENTS'], 'a') as file:\n"
        "    file.write(json.dumps(event) + '\\n')\n"
        "time.sleep(float(os.environ.get('POOL_TEST_SLEEP', '0.35')))\n"
        "failed = os.environ.get('POOL_TEST_FAIL_FIRST') == '1' and attempt == 1\n"
        "status, exit_code = ('failed', 1) if failed else ('completed', 0)\n"
        "with open(result, 'w') as file:\n"
        "    json.dump({'run_id': run_id, 'attempt': attempt, 'execution_id': execution_id, "
        "'status': status, 'exit_code': exit_code, 'ended_at': 'now', "
        "'exception_summary': 'planned failure' if failed else ''}, file)\n"
        "with open(os.environ['POOL_TEST_EVENTS'], 'a') as file:\n"
        "    file.write(json.dumps({'event': 'end', 'run_id': run_id, 'attempt': attempt, "
        "'time': time.time(), 'mask': os.environ['CUDA_VISIBLE_DEVICES']}) + '\\n')\n"
        "raise SystemExit(exit_code)\n",
        encoding="utf-8",
    )
    executable.chmod(0o755)
    return executable


class _FakeRunConfig:
    def __init__(self, run_id: str, meta_dir: Path) -> None:
        self.id = run_id
        self.logger = SimpleNamespace(output_dir=str(meta_dir / run_id))
        self.task = SimpleNamespace(name=f"task-{run_id}", data_dir="")
        self.interpreter = SimpleNamespace()

    def to_typed_dict(self) -> dict:
        return {"id": self.id}


def _make_launcher(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    inventory: tuple[GpuDevice, ...],
    *,
    run_count: int = 3,
    max_parallel: int = 2,
    max_retries: int = 0,
    timeout: float | None = None,
    gpus_per_task: int = 1,
    fail_fast: bool = False,
) -> tuple[LocalGpuPoolLauncher, Path, list[_FakeRunConfig]]:
    tmp_path.mkdir(parents=True, exist_ok=True)
    monkeypatch.delenv("CUDA_VISIBLE_DEVICES", raising=False)
    monkeypatch.setattr(gpu_pool.shutil, "which", lambda name: f"/fake/{name}")
    events = tmp_path / "events.jsonl"
    monkeypatch.setenv("POOL_TEST_EVENTS", str(events))
    snapshot = tmp_path / "snapshot"
    snapshot.mkdir(exist_ok=True)
    meta_dir = tmp_path / "experiments"
    configs = [_FakeRunConfig(f"run-{index}", meta_dir) for index in range(run_count)]
    cfg = LocalGpuPoolConfig(
        debug=False,
        devices=[0, 1],
        max_parallel=max_parallel,
        gpus_per_task=gpus_per_task,
        poll_interval_seconds=0.01,
        max_retries=max_retries,
        task_timeout_seconds=timeout,
        shutdown_grace_seconds=0.2,
        fail_fast=fail_fast,
    )
    launcher = LocalGpuPoolLauncher(
        configs,  # type: ignore[arg-type]
        cfg,
        snapshot,
        python_executable=_make_fake_python(tmp_path),
        inventory=inventory,
    )
    return launcher, events, configs


def test_local_pool_fixed_concurrency_gpu_masks_and_manifest(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    inventory: tuple[GpuDevice, ...],
) -> None:
    launcher, events_path, configs = _make_launcher(tmp_path, monkeypatch, inventory)

    summary = launcher.run()

    assert summary["successful"] is True
    manifest = json.loads(Path(summary["manifest_path"]).read_text(encoding="utf-8"))
    assert manifest["launcher_type"] == "local_gpu_pool"
    assert {task["status"] for task in manifest["tasks"].values()} == {"completed"}
    assert all(len(task["gpu_uuids"]) == 1 for task in manifest["tasks"].values())
    assert all(task["execution_id"] for task in manifest["tasks"].values())

    events = [
        json.loads(line)
        for line in events_path.read_text(encoding="utf-8").splitlines()
    ]
    active: set[str] = set()
    peak = 0
    for event in sorted(events, key=lambda item: item["time"]):
        if event["event"] == "start":
            assert event["mask"] not in active
            active.add(event["mask"])
            peak = max(peak, len(active))
        else:
            active.remove(event["mask"])
    assert peak == 2
    assert not active

    tasks = get_pool_tasks(tmp_path / "experiments")
    assert {task["launcher_type"] for task in tasks} == {"local_gpu_pool"}
    assert {task["run_id"] for task in tasks} == {config.id for config in configs}


def test_local_pool_retries_and_recovers_terminal_results(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    inventory: tuple[GpuDevice, ...],
) -> None:
    launcher, events_path, configs = _make_launcher(
        tmp_path, monkeypatch, inventory, run_count=1, max_parallel=1, max_retries=1
    )
    monkeypatch.setenv("POOL_TEST_FAIL_FIRST", "1")

    summary = launcher.run()
    assert summary["successful"] is True
    manifest_path = Path(summary["manifest_path"])
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    attempts = manifest["tasks"]["run-0"]["attempts"]
    assert [attempt["status"] for attempt in attempts] == ["failed", "completed"]

    event_count = len(events_path.read_text(encoding="utf-8").splitlines())
    manifest["tasks"]["run-0"]["status"] = "running"
    manifest["tasks"]["run-0"]["attempts"][-1]["status"] = "running"
    manifest_path.write_text(json.dumps(manifest), encoding="utf-8")

    resumed = LocalGpuPoolLauncher(
        configs,  # type: ignore[arg-type]
        launcher.cfg,
        launcher.snapshot_path,
        python_executable=launcher.python_executable,
        inventory=inventory,
    ).run()
    assert resumed["successful"] is True
    assert len(events_path.read_text(encoding="utf-8").splitlines()) == event_count


def test_local_pool_recovers_a_live_worker_without_duplicate_launch(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    inventory: tuple[GpuDevice, ...],
) -> None:
    launcher, events_path, configs = _make_launcher(
        tmp_path, monkeypatch, inventory, run_count=1, max_parallel=1
    )
    identity_path, result_path, stdout_path, stderr_path = launcher._attempt_paths(
        "run-0", 1
    )
    external_script = tmp_path / "external-worker"
    external_script.write_text(
        "#!/usr/bin/env python3\n"
        "import json, os, socket, sys, time\n"
        "identity, result = sys.argv[1:3]\n"
        "pid = os.getpid()\n"
        "fields = open(f'/proc/{pid}/stat').read().rsplit(')', 1)[1].split()\n"
        "ticks = int(fields[19])\n"
        "boot = open('/proc/sys/kernel/random/boot_id').read().strip()\n"
        "execution_id = f'{socket.gethostname()}:{pid}:{ticks}:a1'\n"
        "with open(identity, 'w') as file:\n"
        "    json.dump({'run_id': 'run-0', 'attempt': 1, 'execution_id': execution_id, "
        "'host': socket.gethostname(), 'host_boot_id': boot, 'pid': pid, 'pgid': os.getpgid(pid), "
        "'process_start_ticks': ticks, 'gpu_uuids': ['GPU-3090-a'], 'started_at': "
        "'2026-07-24T00:00:00+00:00'}, file)\n"
        "time.sleep(0.4)\n"
        "with open(result, 'w') as file:\n"
        "    json.dump({'run_id': 'run-0', 'attempt': 1, 'execution_id': execution_id, "
        "'status': 'completed', 'exit_code': 0, 'ended_at': 'now'}, file)\n",
        encoding="utf-8",
    )
    external_script.chmod(0o755)
    external = subprocess.Popen(
        [str(external_script), str(identity_path), str(result_path)],
        start_new_session=True,
    )
    deadline = time.monotonic() + 2
    while not identity_path.exists() and time.monotonic() < deadline:
        time.sleep(0.01)
    assert identity_path.exists()
    identity = json.loads(identity_path.read_text(encoding="utf-8"))

    manifest = launcher.manifest
    task = manifest["tasks"]["run-0"]
    task.update(
        {
            "status": "running",
            "attempt": 1,
            "execution_id": identity["execution_id"],
            "gpu_uuids": ["GPU-3090-a"],
            "gpu_indices": [0],
            "stdout": str(stdout_path),
            "stderr": str(stderr_path),
            "attempts": [
                {
                    "attempt": 1,
                    "status": "running",
                    "execution_id": identity["execution_id"],
                    "gpu_uuids": ["GPU-3090-a"],
                    "gpu_indices": [0],
                    "identity_path": str(identity_path),
                    "result_path": str(result_path),
                    "stdout": str(stdout_path),
                    "stderr": str(stderr_path),
                    "started_at": identity["started_at"],
                    "ended_at": "",
                }
            ],
        }
    )
    launcher.manifest_path.write_text(json.dumps(manifest), encoding="utf-8")

    resumed = LocalGpuPoolLauncher(
        configs,  # type: ignore[arg-type]
        launcher.cfg,
        launcher.snapshot_path,
        python_executable=launcher.python_executable,
        inventory=inventory,
    ).run()
    external.wait(timeout=2)

    assert resumed["successful"] is True
    assert not events_path.exists()
    recovered_manifest = json.loads(
        Path(resumed["manifest_path"]).read_text(encoding="utf-8")
    )
    assert len(recovered_manifest["tasks"]["run-0"]["attempts"]) == 1


def test_local_pool_cleans_orphan_container_before_reusing_slot(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    inventory: tuple[GpuDevice, ...],
) -> None:
    launcher, _, configs = _make_launcher(
        tmp_path, monkeypatch, inventory, run_count=1, max_parallel=1
    )
    identity_path, result_path, stdout_path, stderr_path = launcher._attempt_paths(
        "run-0", 1
    )
    container = subprocess.Popen(
        [
            sys.executable,
            "-c",
            "import time; time.sleep(30)",
        ],
        start_new_session=True,
    )
    fields = (
        Path(f"/proc/{container.pid}/stat")
        .read_text(encoding="utf-8")
        .rsplit(")", 1)[1]
        .split()
    )
    container_ticks = int(fields[19])
    identity = {
        "run_id": "run-0",
        "attempt": 1,
        "execution_id": "missing-worker:a1",
        "host": launcher.host,
        "host_boot_id": launcher.boot_id,
        "pid": 99999999,
        "pgid": 99999999,
        "process_start_ticks": 1,
        "gpu_uuids": ["GPU-3090-a"],
        "started_at": "2026-07-24T00:00:00+00:00",
        "container_pid": container.pid,
        "container_pgid": os.getpgid(container.pid),
        "container_process_start_ticks": container_ticks,
    }
    identity_path.write_text(json.dumps(identity), encoding="utf-8")
    task = launcher.manifest["tasks"]["run-0"]
    task.update(
        {
            "status": "running",
            "attempt": 1,
            "gpu_uuids": ["GPU-3090-a"],
            "gpu_indices": [0],
            "attempts": [
                {
                    "attempt": 1,
                    "status": "running",
                    "gpu_uuids": ["GPU-3090-a"],
                    "gpu_indices": [0],
                    "identity_path": str(identity_path),
                    "result_path": str(result_path),
                    "stdout": str(stdout_path),
                    "stderr": str(stderr_path),
                    "started_at": identity["started_at"],
                    "ended_at": "",
                }
            ],
        }
    )
    launcher.manifest_path.write_text(json.dumps(launcher.manifest), encoding="utf-8")

    summary = LocalGpuPoolLauncher(
        configs,  # type: ignore[arg-type]
        launcher.cfg,
        launcher.snapshot_path,
        python_executable=launcher.python_executable,
        inventory=inventory,
    ).run()
    container.wait(timeout=2)

    assert summary["successful"] is False
    assert container.returncode == -signal.SIGTERM


def test_local_pool_supports_multi_gpu_slots_and_fail_fast(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    inventory: tuple[GpuDevice, ...],
) -> None:
    multi_launcher, events_path, _ = _make_launcher(
        tmp_path / "multi",
        monkeypatch,
        inventory,
        run_count=1,
        max_parallel=1,
        gpus_per_task=2,
    )
    summary = multi_launcher.run()
    assert summary["successful"] is True
    event = json.loads(events_path.read_text(encoding="utf-8").splitlines()[0])
    assert event["mask"] == "GPU-3090-a,GPU-3090-b"
    assert event["hardware"] == "2 GPUs: NVIDIA GeForce RTX 3090 (24 GiB VRAM each)"

    monkeypatch.setenv("POOL_TEST_FAIL_FIRST", "1")
    fail_launcher, fail_events, _ = _make_launcher(
        tmp_path / "fail-fast",
        monkeypatch,
        inventory,
        run_count=2,
        max_parallel=1,
        fail_fast=True,
    )
    failed = fail_launcher.run()
    assert failed["successful"] is False
    events = [
        json.loads(line)
        for line in fail_events.read_text(encoding="utf-8").splitlines()
    ]
    assert {event["run_id"] for event in events} == {"run-0"}
    manifest = json.loads(Path(failed["manifest_path"]).read_text(encoding="utf-8"))
    assert manifest["tasks"]["run-0"]["status"] == "failed"
    assert manifest["tasks"]["run-1"]["status"] == "pending"


def test_local_pool_timeout_releases_worker_and_records_failure(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    inventory: tuple[GpuDevice, ...],
) -> None:
    launcher, _, _ = _make_launcher(
        tmp_path,
        monkeypatch,
        inventory,
        run_count=1,
        max_parallel=1,
        timeout=0.05,
    )
    monkeypatch.setenv("POOL_TEST_SLEEP", "30")

    started = time.monotonic()
    summary = launcher.run()

    assert time.monotonic() - started < 5
    assert summary["successful"] is False
    manifest = json.loads(Path(summary["manifest_path"]).read_text(encoding="utf-8"))
    task = manifest["tasks"]["run-0"]
    assert task["status"] == "failed"
    assert "exceeded timeout" in task["reason"]
    pid = task["attempts"][-1]["pid"]
    with pytest.raises(ProcessLookupError):
        os.kill(pid, 0)


def test_local_pool_controller_shutdown_terminates_worker(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    inventory: tuple[GpuDevice, ...],
) -> None:
    launcher, _, _ = _make_launcher(
        tmp_path, monkeypatch, inventory, run_count=1, max_parallel=1
    )
    monkeypatch.setenv("POOL_TEST_SLEEP", "30")
    devices = launcher._allocate_devices()
    worker = launcher._launch("run-0", devices)
    deadline = time.monotonic() + 2
    while not worker.identity_path.exists() and time.monotonic() < deadline:
        time.sleep(0.01)
    launcher._stop_reason = "test shutdown"

    launcher._cancel_all({"run-0": worker}, {})

    assert worker.process.poll() is not None
    manifest = json.loads(launcher.manifest_path.read_text(encoding="utf-8"))
    assert manifest["tasks"]["run-0"]["status"] == "cancelled"
    assert manifest["tasks"]["run-0"]["reason"] == "test shutdown"
    with pytest.raises(ProcessLookupError):
        os.kill(worker.process.pid, 0)


def test_local_pool_analysis_does_not_query_slurm(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from dojo.analysis_utils import meta_data_wrangling

    task = {
        "run_id": "run-a",
        "launcher_type": "local_gpu_pool",
        "execution_id": "host:12:34:a1",
        "step_id": "",
        "allocation_id": "",
        "status": "completed",
        "exit_code": 0,
        "stdout": "",
        "stderr": "",
        "node_list": "host",
        "experiment_dir": "/tmp/run-a",
        "config_path": "/tmp/config.json",
        "manifest_path": "/tmp/manifest.json",
        "gpu_uuids": ["GPU-a"],
    }
    monkeypatch.setattr(
        meta_data_wrangling,
        "get_slurm_data",
        lambda ids: pytest.fail(f"local pool unexpectedly queried Slurm for {ids}"),
    )
    monkeypatch.setattr(
        meta_data_wrangling.RunConfig,
        "load_from_json",
        lambda path: SimpleNamespace(task=SimpleNamespace(name="spaceship-titanic")),
    )

    dataframe = meta_data_wrangling.prepare_pool_dataframe("/tmp", [task])

    assert dataframe.loc["run-a", "JobID"] == "host:12:34:a1"
    assert dataframe.loc["run-a", "LauncherType"] == "local_gpu_pool"
    assert dataframe.loc["run-a", "GPUUUIDs"] == ["GPU-a"]


def test_local_pool_config_requires_a_managed_controller() -> None:
    with pytest.raises(ValueError, match="must await and monitor"):
        LocalGpuPoolConfig(await_completion=False).validate()
    with pytest.raises(ValueError, match="gpus_per_task"):
        LocalGpuPoolConfig(gpus_per_task=0).validate()
