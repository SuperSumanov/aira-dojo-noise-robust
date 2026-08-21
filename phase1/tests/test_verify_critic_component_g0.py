from __future__ import annotations

import json
from pathlib import Path

import pytest

from phase1 import verify_critic_component_g0 as g0


def write_json(path: Path, value: dict) -> None:
    path.write_text(json.dumps(value), encoding="utf-8")


def make_valid_artifacts(tmp_path: Path) -> tuple[dict, dict[str, Path]]:
    snapshot = tmp_path / g0.MODEL_REVISION
    snapshot.mkdir()
    output = tmp_path / "output"
    checkpoint = output / "checkpoint-10"
    checkpoint.mkdir(parents=True)
    source_commit = "a" * 40
    accuracy = 0.6
    write_json(
        checkpoint / "trainer_state.json",
        {
            "global_step": 10,
            "best_model_checkpoint": str(checkpoint),
            "best_metric": accuracy,
            "log_history": [
                {"loss": 0.7, "step": 1},
                {"eval_loss": 0.65, "eval_pair_accuracy": accuracy, "step": 10},
            ],
        },
    )
    write_json(
        checkpoint / "rm_meta.json",
        {
            "protocol": "rm-dev-selected-checkpoint-v1",
            "base_model": str(snapshot),
            "max_len": 16_384,
            "head_frac": 0.25,
            "task_cond": True,
            "budget_cond": False,
            "budget_pos": "head",
            "seed": 6,
            "train_pairs_sha256": g0.EXPECTED_INPUTS["train"]["sha256"],
            "dev_pairs_sha256": g0.EXPECTED_INPUTS["dev"]["sha256"],
            "cards_sha256": g0.EXPECTED_INPUTS["cards"]["sha256"],
            "train_pairs": 4_689,
            "dev_pairs": 551,
            "split_name": "in-task-train-run-dev",
            "separation": {
                "train_pairs": 4_689,
                "dev_pairs": 551,
                "train_endpoints": 4_095,
                "dev_endpoints": 626,
                "train_runs": 430,
                "dev_runs": 81,
            },
            "metric_for_best_model": "eval_pair_accuracy",
            "greater_is_better": True,
            "best_dev_pair_accuracy": accuracy,
            "training_code_git_commit": source_commit,
        },
    )
    launcher_log = tmp_path / "launcher.log"
    launcher_log.write_text(
        '[g0-worker-timing] {"event":"launcher_start","monotonic_ns":1000000000,"utc":"2026-08-21T00:00:00+00:00"}\n'
        "processes=2 effective_pair_batch=128 max_len=16384 epochs=1\n"
        "max_steps=10 scheduler=cosine warmup_ratio=0.03\n"
        '[rm-timing] {"event":"train_begin","global_step":0,"max_steps":10,"monotonic_ns":2000000000,"utc":"2026-08-21T00:00:01+00:00"}\n'
        '[rm-timing] {"event":"optimizer_step_1","global_step":1,"max_steps":10,"monotonic_ns":3000000000,"utc":"2026-08-21T00:00:02+00:00"}\n'
        '[rm-timing] {"event":"optimizer_step_final","global_step":10,"max_steps":10,"monotonic_ns":12000000000,"utc":"2026-08-21T00:00:11+00:00"}\n'
        '[rm-timing] {"event":"dev_evaluate_complete","global_step":10,"max_steps":10,"monotonic_ns":15000000000,"utc":"2026-08-21T00:00:14+00:00"}\n'
        '[rm-timing] {"event":"train_end","global_step":10,"max_steps":10,"monotonic_ns":16000000000,"utc":"2026-08-21T00:00:15+00:00"}\n'
        "[rm-hf] training complete\n",
        encoding="utf-8",
    )
    resource = tmp_path / "resource.txt"
    resource.write_text(
        "Elapsed (wall clock) time (h:mm:ss or m:ss): 0:20.00\nExit status: 0\n",
        encoding="utf-8",
    )
    telemetry = tmp_path / "telemetry.csv"
    telemetry.write_text(
        "timestamp_utc,visible_id,name,uuid,memory_total_mib,memory_used_mib,utilization_gpu_pct,power_draw_w\n"
        "2026-08-21T00:00:00Z,0,NVIDIA RTX PRO 6000,GPU-a,97887,1000,50,100\n"
        "2026-08-21T00:00:00Z,1,NVIDIA RTX PRO 6000,GPU-b,97887,2000,40,90\n",
        encoding="utf-8",
    )
    preflight = {
        "source": {"commit": source_commit},
        "model": {"snapshot": str(snapshot)},
    }
    return preflight, {
        "output": output,
        "checkpoint": checkpoint,
        "log": launcher_log,
        "resource": resource,
        "telemetry": telemetry,
    }


def test_valid_training_artifacts_require_one_step10_dev_eval(tmp_path: Path) -> None:
    preflight, paths = make_valid_artifacts(tmp_path)
    result = g0.validate_training_artifacts(
        paths["output"], paths["log"], paths["resource"], paths["telemetry"], preflight
    )
    assert result["global_step"] == 10
    assert result["dev_evaluations"] == 1
    assert result["dev_pair_accuracy"] == 0.6
    assert result["peak_gpu_memory_mib"] == 2000
    assert result["timing"]["seconds"]["dev_evaluation"] == 3.0
    assert result["gnu_elapsed_seconds"] == 20.0


def test_wrong_global_step_fails_closed(tmp_path: Path) -> None:
    preflight, paths = make_valid_artifacts(tmp_path)
    state_path = paths["checkpoint"] / "trainer_state.json"
    state = json.loads(state_path.read_text(encoding="utf-8"))
    state["global_step"] = 9
    write_json(state_path, state)
    with pytest.raises(g0.ContractError, match="global_step"):
        g0.validate_training_artifacts(
            paths["output"], paths["log"], paths["resource"], paths["telemetry"], preflight
        )


def test_second_dev_evaluation_fails_closed(tmp_path: Path) -> None:
    preflight, paths = make_valid_artifacts(tmp_path)
    state_path = paths["checkpoint"] / "trainer_state.json"
    state = json.loads(state_path.read_text(encoding="utf-8"))
    state["log_history"].append({"eval_pair_accuracy": 0.61, "step": 5})
    write_json(state_path, state)
    with pytest.raises(g0.ContractError, match="exactly one dev evaluation"):
        g0.validate_training_artifacts(
            paths["output"], paths["log"], paths["resource"], paths["telemetry"], preflight
        )


def test_forbidden_heldout_path_in_log_fails_closed(tmp_path: Path) -> None:
    preflight, paths = make_valid_artifacts(tmp_path)
    with paths["log"].open("a", encoding="utf-8") as handle:
        handle.write("opened heldout_test.jsonl\n")
    with pytest.raises(g0.ContractError, match="forbidden test path"):
        g0.validate_training_artifacts(
            paths["output"], paths["log"], paths["resource"], paths["telemetry"], preflight
        )


def test_missing_wall_clock_event_fails_closed(tmp_path: Path) -> None:
    preflight, paths = make_valid_artifacts(tmp_path)
    text = paths["log"].read_text(encoding="utf-8")
    text = "\n".join(line for line in text.splitlines() if '"event":"train_end"' not in line) + "\n"
    paths["log"].write_text(text, encoding="utf-8")
    with pytest.raises(g0.ContractError, match="timing event sequence"):
        g0.validate_training_artifacts(
            paths["output"], paths["log"], paths["resource"], paths["telemetry"], preflight
        )


def test_worker_and_scheduler_cannot_self_submit() -> None:
    root = Path(__file__).resolve().parents[1]
    worker = (root / "scripts/critic_component_g0_worker_20260821.sh").read_text(encoding="utf-8")
    scheduler = (root / "scripts/critic_component_g0_pro6000_20260821.sbatch").read_text(
        encoding="utf-8"
    )
    assert "heldout_test" not in worker.lower()
    assert "test_pairs" not in worker.lower()
    assert not any(line.lstrip().startswith("sbatch ") for line in worker.splitlines())
    assert not any(line.lstrip().startswith("sbatch ") for line in scheduler.splitlines())
    assert "#SBATCH --gres=gpu:pro6000:2" in scheduler
    assert "#SBATCH --time=02:00:00" in scheduler
    assert "#SBATCH --qos=zliang_gpu" in scheduler
