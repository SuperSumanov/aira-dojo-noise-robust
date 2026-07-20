import json
import hashlib
import os
import subprocess
import sys
import time
from collections import deque
from dataclasses import dataclass, field
from pathlib import Path
from types import SimpleNamespace

import pytest

from aira_core.config.base import BaseConfig
from dojo.config_dataclasses.utils import dataclass_from_dict, dataclass_to_dict
from dojo.config_dataclasses.run import RunConfig
from dojo.config_dataclasses.task.mlebench import MLEBenchTaskConfig
from dojo.config_dataclasses.solver.greedy import GreedySolverConfig
from dojo.core.runners.slurm.accounting import parse_sacct_parsable, query_sacct
from dojo.core.runners.slurm.manifest import get_srun_pool_tasks
from dojo.config_dataclasses.launcher.srun_pool import SrunPoolConfig
from dojo.core.runners.slurm.srun_pool import AllocationInfo
from dojo.core.runners.slurm.srun_pool import SrunPoolLauncher
from dojo.core.runners.slurm.srun_pool import _parse_gpu_count, _parse_key_values
from dojo.utils.slurm import get_slurm_identity


@dataclass
class _BaseChildConfig(BaseConfig):
    value: int = 1


@dataclass
class _ConcreteChildConfig(_BaseChildConfig):
    extra: str = "kept"


@dataclass
class _ParentConfig(BaseConfig):
    child: _BaseChildConfig = field(default_factory=_BaseChildConfig)
    mapping: dict[str, _BaseChildConfig] = field(default_factory=dict)


def test_typed_dataclass_json_round_trip_preserves_subclasses() -> None:
    config = _ParentConfig(
        child=_ConcreteChildConfig(value=4, extra="nested"),
        mapping={"operator": _ConcreteChildConfig(value=8, extra="mapping")},
    )

    restored = dataclass_from_dict(_ParentConfig, dataclass_to_dict(config))

    assert restored == config
    assert isinstance(restored.child, _ConcreteChildConfig)
    assert isinstance(restored.mapping["operator"], _ConcreteChildConfig)


def test_old_dataclass_json_keeps_new_defaults() -> None:
    restored = dataclass_from_dict(_ConcreteChildConfig, {"value": 3})
    assert restored == _ConcreteChildConfig(value=3, extra="kept")


def test_run_config_keeps_type_markers_out_of_experiment_json() -> None:
    config = RunConfig(
        id="run",
        task=MLEBenchTaskConfig(name="demo"),
        solver=GreedySolverConfig(operators={}),
    )

    assert "_dojo_dataclass_type" not in config.to_dict()
    assert config.to_typed_dict()["task"]["_dojo_dataclass_type"].endswith(
        ":MLEBenchTaskConfig"
    )


def test_slurm_identity_for_srun_pool(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("SLURM_JOB_ID", "7668")
    monkeypatch.setenv("SLURM_STEP_ID", "3")
    monkeypatch.setenv("DOJO_LAUNCHER_TYPE", "srun_pool")
    monkeypatch.delenv("SLURM_ARRAY_JOB_ID", raising=False)

    identity = get_slurm_identity()

    assert identity.full_id == "7668.3"
    assert identity.allocation_id == "7668"
    assert identity.step_id == "3"
    assert identity.launcher_type == "srun_pool"


def test_slurm_identity_for_submitit_array(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("SLURM_JOB_ID", "9001")
    monkeypatch.setenv("SLURM_ARRAY_JOB_ID", "9000")
    monkeypatch.setenv("SLURM_ARRAY_TASK_ID", "7")
    monkeypatch.delenv("SLURM_STEP_ID", raising=False)

    identity = get_slurm_identity()

    assert identity.full_id == "9000_7"
    assert identity.allocation_id == "9000"
    assert identity.step_id == ""


def test_parse_allocation_resources() -> None:
    fields = _parse_key_values(
        "JobId=7668 JobState=RUNNING NodeList=gpu7 NumNodes=1 NumCPUs=4 "
        "TRES=cpu=4,node=1,billing=4,gres/gpu=2 TresPerNode=gpu:2"
    )
    assert fields["JobState"] == "RUNNING"
    assert _parse_gpu_count(fields) == 2
    assert _parse_gpu_count({"TresPerNode": "gpu:8"}) == 8
    assert _parse_gpu_count({"TresPerNode": "gpu:titanx:8"}) == 8
    assert _parse_gpu_count({"TRES": "gres/gpu=8,gres/gpu:titanx=8"}) == 8


def test_parse_sacct_19_parsable_output() -> None:
    output = (
        "7668|allocation|COMPLETED|0:0|2026-07-20T13:35:34|2026-07-20T13:35:34|"
        "2026-07-20T13:35:47|13|gpu7\n"
        "7668.0|dojo-a|CANCELLED by 4586|0:15|2026-07-20T13:35:37|2026-07-20T13:35:37|"
        "2026-07-20T13:35:47|10|gpu7\n"
    )

    records = parse_sacct_parsable(output)

    assert records["7668"]["State"] == "COMPLETED"
    assert records["7668.0"]["State"] == "CANCELLED"
    assert records["7668.0"]["ExitCode"] == "0:15"


def test_query_sacct_uses_parsable_fields() -> None:
    calls = []

    def fake_run(command, **kwargs):
        calls.append((command, kwargs))
        return subprocess.CompletedProcess(
            command,
            0,
            stdout="7668.1|dojo|RUNNING|0:0|a|b|Unknown|5|gpu7\n",
            stderr="",
        )

    records = query_sacct(["7668.1"], run=fake_run)

    assert records["7668.1"]["State"] == "RUNNING"
    assert "-P" in calls[0][0]
    assert "--json" not in calls[0][0]


def test_manifest_reader_maps_tasks(tmp_path: Path) -> None:
    manifest_path = tmp_path / "srun_pool/demo/manifest.json"
    manifest_path.parent.mkdir(parents=True)
    manifest_path.write_text(
        json.dumps(
            {
                "launcher_type": "srun_pool",
                "allocation_id": "7668",
                "node_list": "gpu7",
                "allocations": [
                    {"allocation_id": "7667", "node_list": "gpu6"},
                    {"allocation_id": "7668", "node_list": "gpu7"},
                ],
                "tasks": {"run-a": {"status": "completed", "step_id": "7667.0"}},
            }
        ),
        encoding="utf-8",
    )

    tasks = get_srun_pool_tasks(tmp_path)

    assert tasks[0]["run_id"] == "run-a"
    assert tasks[0]["allocation_id"] == "7667"
    assert tasks[0]["node_list"] == "gpu6"
    assert tasks[0]["step_id"] == "7667.0"


def test_host_runner_import_does_not_load_training_frameworks() -> None:
    code = (
        "import sys; import dojo.main_runner_job_array; import dojo.main_srun_worker; "
        "import dojo.main_run; assert 'torch' not in sys.modules; "
        "assert 'tensorflow' not in sys.modules; assert 'wandb' not in sys.modules"
    )
    environment = os.environ.copy()
    environment["PYTHONPATH"] = str(Path(__file__).parents[1] / "src")

    result = subprocess.run(
        [sys.executable, "-c", code],
        env=environment,
        check=False,
        capture_output=True,
        text=True,
    )

    assert result.returncode == 0, result.stderr


def test_srun_pool_fixed_concurrency_and_manifest(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir()
    events_path = tmp_path / "events.jsonl"
    scontrol = bin_dir / "scontrol"
    scontrol.write_text(
        "#!/bin/sh\n"
        "if [ \"$2\" = \"job\" ]; then\n"
        "  echo 'JobId=999 UserId='\"$(id -un)\"'(1) JobState=RUNNING EndTime=2099-01-01T00:00:00 "
        "NodeList=gpu7 NumNodes=1 NumCPUs=4 TRES=cpu=4,node=1,gres/gpu=2 TresPerNode=gpu:2'\n"
        "fi\n",
        encoding="utf-8",
    )
    sacct = bin_dir / "sacct"
    sacct.write_text(
        "#!/bin/sh\n"
        "while [ $# -gt 0 ]; do\n"
        "  if [ \"$1\" = '-j' ]; then ids=$2; shift 2; else shift; fi\n"
        "done\n"
        "oldifs=$IFS; IFS=,\n"
        "for id in $ids; do\n"
        "  echo \"$id|dojo|COMPLETED|0:0|2026-01-01T00:00:00|2026-01-01T00:00:00|"
        "2026-01-01T00:00:01|1|gpu7\"\n"
        "done\n"
        "IFS=$oldifs\n",
        encoding="utf-8",
    )
    srun = bin_dir / "srun"
    srun.write_text(
        "#!/usr/bin/env python3\n"
        "import json, os, sys, time\n"
        "run_index = sys.argv.index('--run-id')\n"
        "run_id = sys.argv[run_index + 1]\n"
        "attempt = int(sys.argv[run_index + 3])\n"
        "identity = sys.argv[run_index - 1]\n"
        "step = str(os.getpid())\n"
        "with open(identity, 'w') as file:\n"
        "    json.dump({'run_id': run_id, 'attempt': attempt, 'allocation_id': '999', "
        "'step_id': step, 'full_step_id': f'999.{step}'}, file)\n"
        "with open(os.environ['POOL_TEST_EVENTS'], 'a') as file:\n"
        "    file.write(json.dumps({'event': 'start', 'run_id': run_id, 'time': time.time()}) + '\\n')\n"
        "time.sleep(0.75)\n"
        "with open(os.environ['POOL_TEST_EVENTS'], 'a') as file:\n"
        "    file.write(json.dumps({'event': 'end', 'run_id': run_id, 'time': time.time()}) + '\\n')\n",
        encoding="utf-8",
    )
    for executable in (scontrol, sacct, srun):
        executable.chmod(0o755)

    monkeypatch.setenv("PATH", f"{bin_dir}{os.pathsep}{os.environ['PATH']}")
    monkeypatch.setenv("SLURM_JOB_ID", "999")
    monkeypatch.setenv("POOL_TEST_EVENTS", str(events_path))
    snapshot = tmp_path / "snapshot"
    snapshot.mkdir()
    meta_dir = tmp_path / "experiments"

    class FakeRunConfig:
        def __init__(self, run_id: str) -> None:
            self.id = run_id
            self.logger = SimpleNamespace(output_dir=str(meta_dir / run_id))
            self.task = SimpleNamespace(name=f"task-{run_id}", data_dir="")
            self.interpreter = SimpleNamespace()

        def to_dict(self) -> dict:
            return {"id": self.id}

        def to_typed_dict(self) -> dict:
            return self.to_dict()

    config = SrunPoolConfig(
        debug=False,
        max_parallel=2,
        cpus_per_step=2,
        gpus_per_step=1,
        poll_interval_seconds=0.02,
        max_retries=0,
        min_remaining_seconds_to_launch=0,
        validate_paths_on_node=False,
    )
    run_configs = [FakeRunConfig(f"run-{index}") for index in range(3)]
    launcher = SrunPoolLauncher(run_configs, config, snapshot)  # type: ignore[arg-type]

    summary = launcher.run()

    assert summary["successful"] is True
    manifest = json.loads(Path(summary["manifest_path"]).read_text(encoding="utf-8"))
    assert {task["status"] for task in manifest["tasks"].values()} == {"completed"}
    assert all(task["step_id"].startswith("999.") for task in manifest["tasks"].values())

    events = [json.loads(line) for line in events_path.read_text(encoding="utf-8").splitlines()]
    active = peak = 0
    for event in sorted(events, key=lambda item: item["time"]):
        active += 1 if event["event"] == "start" else -1
        peak = max(peak, active)
    assert peak == 2

    monkeypatch.setenv("SLURM_JOB_ID", "1000")
    resumed_summary = SrunPoolLauncher(  # type: ignore[arg-type]
        run_configs, config, snapshot
    ).run()
    resumed_manifest = json.loads(
        Path(resumed_summary["manifest_path"]).read_text(encoding="utf-8")
    )

    assert resumed_summary["successful"] is True
    assert [item["allocation_id"] for item in resumed_manifest["allocations"]] == [
        "999",
        "1000",
    ]
    assert len(events_path.read_text(encoding="utf-8").splitlines()) == len(events)


def test_srun_pool_resumes_across_allocations(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    meta_dir = tmp_path / "experiments"

    class FakeRunConfig:
        id = "run-a"
        logger = SimpleNamespace(output_dir=str(meta_dir / "run-a"))

    config = SrunPoolConfig(max_parallel=1, cpus_per_step=1, gpus_per_step=1)
    monkeypatch.setenv("SLURM_JOB_ID", "1000")
    expected_key = hashlib.sha256(b"run-a").hexdigest()[:12]
    manifest_path = meta_dir / "srun_pool" / expected_key / "manifest.json"
    snapshot = tmp_path / "snapshot"
    snapshot.mkdir()
    manifest_path.parent.mkdir(parents=True)
    manifest_path.write_text(
        json.dumps({"snapshot_path": str(snapshot), "tasks": {"run-a": {"status": "pending"}}}),
        encoding="utf-8",
    )

    resumed = SrunPoolLauncher.resume_snapshot_path(
        [FakeRunConfig()],  # type: ignore[list-item]
        config,
    )

    assert resumed == snapshot.resolve()


def test_srun_pool_does_not_block_recovery_with_path_check(tmp_path: Path) -> None:
    launcher = object.__new__(SrunPoolLauncher)
    launcher.cfg = SimpleNamespace(
        validate_paths_on_node=True,
        max_parallel=1,
        poll_interval_seconds=0,
    )
    launcher.manifest_path = tmp_path / "manifest.json"
    launcher.manifest = {"tasks": {"run-a": {"status": "running"}}}
    launcher.allocation = AllocationInfo("999", "gpu7", 1, 2, 1, None)
    launcher._paths_validated = False
    launcher._stop_requested = False
    launcher._stop_reason = ""
    launcher._previous_signal_handlers = {}

    path_checks = []
    launcher._validate_paths_on_node = lambda: path_checks.append(True)
    launcher._recover = lambda: (deque(), {"run-a"})
    launcher._install_signal_handlers = lambda: None
    launcher._restore_signal_handlers = lambda: None

    def finish_recovered(external_running, pending):
        del pending
        launcher.manifest["tasks"]["run-a"]["status"] = "completed"
        external_running.clear()

    launcher._poll_external = finish_recovered

    summary = launcher.run()

    assert summary["successful"] is True
    assert path_checks == []
