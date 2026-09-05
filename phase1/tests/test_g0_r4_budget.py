import pytest
from pathlib import Path

from phase1.verify_critic_component_g0 import ContractError, validate_scheduler_allocation


def allocation(time="01:55:09", revision="20260905-r4", recovery="1"):
    env = {"SLURM_JOB_ID": "90000", "SLURM_JOB_PARTITION": "gpu_24h",
           "SLURM_CPUS_PER_TASK": "12", "SLURM_JOB_NODELIST": "projgpu39",
           "G0_RECOVERY_FINAL_ONLY": recovery, "G0_BUDGET_REVISION": revision}
    line = ("JobId=90000 Partition=gpu_24h QOS=gpu NumCPUs=12 CPUs/Task=12 "
            "MinMemoryNode=0 Requeue=0 Restarts=0 NodeList=projgpu39 TRES=cpu=12,gres/gpu=2 "
            f"TimeLimit={time}")
    return env, line


def test_r4_exact_budget():
    result = validate_scheduler_allocation(*allocation())
    assert result["time_limit"] == "01:55:09"
    assert 582 + 2 * (3600 + 55 * 60 + 9) == 14400


@pytest.mark.parametrize("time", ["01:57:00", "02:00:00", "01:55:10", "01:55:08"])
def test_r4_rejects_other_walltimes(time):
    with pytest.raises(ContractError, match="time limit"):
        validate_scheduler_allocation(*allocation(time=time))


def test_r4_requires_recovery():
    with pytest.raises(ContractError, match="requires final-only"):
        validate_scheduler_allocation(*allocation(recovery="0"))


def test_unknown_revision_rejected():
    with pytest.raises(ContractError, match="unknown G0 budget"):
        validate_scheduler_allocation(*allocation(revision="future"))


def test_legacy_budget_unchanged():
    assert validate_scheduler_allocation(*allocation(time="01:57:00", revision="legacy"))["time_limit"] == "01:57:00"


def test_trace_keeps_output_isolation_and_launcher():
    worker = Path('phase1/scripts/critic_component_g0_worker_20260821.sh').read_text()
    assert worker.index('export MLE_CRITIC_OUTPUT_DIR=') < worker.index('/usr/bin/strace')
    assert '-e trace=%file -o "$G0_RUN_ROOT/file_access.strace" bash "$launcher"' in worker
