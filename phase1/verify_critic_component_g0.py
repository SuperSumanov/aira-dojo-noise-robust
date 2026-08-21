"""Fail-closed pre/postflight checks for the component-split critic G0 run.

This module never accepts a test-pair path.  G0 is an engineering calibration:
ten optimizer steps followed by exactly one complete dev evaluation.
"""

from __future__ import annotations

import argparse
import csv
import datetime as dt
import hashlib
import importlib
import json
import math
import os
from pathlib import Path, PurePosixPath
import re
import subprocess
import sys
from typing import Any


PROTOCOL = "critic-component-g0-engineering-calibration-v1"
MODEL_REPO = "Qwen/Qwen3-1.7B-Base"
MODEL_REVISION = "ea980cb0a6c2ae4b936e82123acc929f1cec04c1"

SCHEDULER_CONTRACTS = {
    ("zliang_gpu", "zliang_gpu"): {
        "cpus_per_task": 16,
        "min_memory_node": "128G",
    },
    ("gpu_24h", "gpu"): {
        "cpus_per_task": 12,
        "min_memory_node": "0",
    },
}

EXPECTED_INPUTS = {
    "train": {
        "sha256": "0ec49d76a896accf8e85a2556ca7ed12b9379b1867247d99c6be5e4c83bea98e",
        "bytes": 3_208_089,
        "pairs": 4_689,
    },
    "dev": {
        "sha256": "3b3fb53f84277e935c66d3b3d1646d7a7d33624fb916e3f9bcc15f689904cfa4",
        "bytes": 376_635,
        "pairs": 551,
    },
    "cards": {
        "sha256": "5fd24c8e545a67e1048f8a67b23bcb64605b9ad584a4fbaa44aa1b1f1b6e1afb",
        "bytes": 604_190_866,
        "cards": 31_742,
    },
}

FIXED_CONFIG = {
    "model_repo": MODEL_REPO,
    "model_revision": MODEL_REVISION,
    "seed": 6,
    "num_processes": 2,
    "max_len": 16_384,
    "head_frac": 0.25,
    "task_cond": True,
    "budget_cond": False,
    "bf16": True,
    "zero_stage": 3,
    "learning_rate": 1e-5,
    "lr_scheduler_type": "cosine",
    "warmup_ratio": 0.03,
    "per_device_train_batch_size": 8,
    "per_device_eval_batch_size": 8,
    "gradient_accumulation_steps": 8,
    "effective_pair_batch_size": 128,
    "max_steps": 10,
    "eval_steps": 10,
    "eval_on_start": False,
    "expected_dev_evaluations": 1,
}

FORBIDDEN_RUNTIME_PATTERN = re.compile(
    r"(?:heldout[_-]?test|test[_-]?pairs|decision_clean_b\d+[^\s]*test)", re.IGNORECASE
)


class ContractError(RuntimeError):
    """Raised when a frozen G0 contract is violated."""


def require(condition: bool, message: str) -> None:
    if not condition:
        raise ContractError(message)


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def load_json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    require(isinstance(value, dict), f"expected a JSON object: {path}")
    return value


def write_json_exclusive(path: Path, value: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    rendered = json.dumps(value, indent=2, sort_keys=True, allow_nan=False) + "\n"
    with path.open("x", encoding="utf-8", newline="\n") as handle:
        handle.write(rendered)
        handle.flush()
        os.fsync(handle.fileno())
    path.chmod(0o600)


def git_state(root: Path, expected_commit: str | None = None) -> dict[str, Any]:
    root = root.resolve(strict=True)
    commit = subprocess.run(
        ["git", "-C", str(root), "rev-parse", "HEAD"],
        check=True,
        capture_output=True,
        text=True,
    ).stdout.strip()
    status = subprocess.run(
        ["git", "-C", str(root), "status", "--porcelain", "--untracked-files=all"],
        check=True,
        capture_output=True,
        text=True,
    ).stdout
    require(not status.strip(), f"Git worktree is not clean: {root}")
    if expected_commit is not None:
        require(commit == expected_commit, f"source commit mismatch: {commit}")
    return {"path": str(root), "commit": commit, "clean": True}


def validate_input(path: Path, label: str) -> dict[str, Any]:
    expected = EXPECTED_INPUTS[label]
    path = path.resolve(strict=True)
    require(path.is_file(), f"{label} is not a regular file: {path}")
    observed_bytes = path.stat().st_size
    observed_sha = sha256_file(path)
    require(observed_bytes == expected["bytes"], f"{label} byte-size mismatch")
    require(observed_sha == expected["sha256"], f"{label} SHA-256 mismatch")
    return {
        "path": str(path),
        "bytes": observed_bytes,
        "sha256": observed_sha,
        **{key: value for key, value in expected.items() if key not in {"bytes", "sha256"}},
    }


def parse_sha256_manifest(path: Path) -> dict[str, str]:
    entries: dict[str, str] = {}
    for line_number, raw in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
        if not raw:
            continue
        match = re.fullmatch(r"([0-9a-f]{64})  (.+)", raw)
        require(match is not None, f"malformed model manifest line {line_number}")
        digest, relative = match.groups()
        posix = PurePosixPath(relative)
        require(not posix.is_absolute(), f"absolute model manifest path: {relative}")
        require(".." not in posix.parts, f"escaping model manifest path: {relative}")
        require(relative not in entries, f"duplicate model manifest path: {relative}")
        entries[relative] = digest
    require(len(entries) == 10, f"expected 10 pinned model files, found {len(entries)}")
    return entries


def validate_model_snapshot(snapshot: Path, manifest: Path) -> dict[str, Any]:
    snapshot = snapshot.resolve(strict=True)
    manifest = manifest.resolve(strict=True)
    require(snapshot.is_dir(), f"model snapshot is not a directory: {snapshot}")
    require(snapshot.name == MODEL_REVISION, "model snapshot basename is not the pinned revision")
    entries = parse_sha256_manifest(manifest)
    observed_files = {
        path.relative_to(snapshot).as_posix()
        for path in snapshot.rglob("*")
        if path.is_file()
    }
    require(observed_files == set(entries), "model snapshot file inventory mismatch")
    total_bytes = 0
    for relative, expected_sha in entries.items():
        path = snapshot / relative
        require(path.is_file(), f"missing model file: {relative}")
        observed_sha = sha256_file(path)
        require(observed_sha == expected_sha, f"model file SHA-256 mismatch: {relative}")
        total_bytes += path.stat().st_size
    return {
        "repo_id": MODEL_REPO,
        "revision": MODEL_REVISION,
        "snapshot": str(snapshot),
        "manifest": str(manifest),
        "manifest_sha256": sha256_file(manifest),
        "files": len(entries),
        "bytes": total_bytes,
    }


def _scontrol_fields(job_line: str) -> dict[str, str]:
    fields: dict[str, str] = {}
    for token in job_line.split():
        if "=" not in token:
            continue
        key, value = token.split("=", 1)
        fields[key] = value
    return fields


def validate_scheduler_allocation(environment: dict[str, str], job_line: str) -> dict[str, Any]:
    job_id = environment.get("SLURM_JOB_ID", "")
    partition = environment.get("SLURM_JOB_PARTITION", "")
    fields = _scontrol_fields(job_line)
    require(job_id.isdigit(), "G0 must run inside a Slurm job")
    require(fields.get("JobId") == job_id, "scontrol job ID mismatch")
    require(fields.get("Partition") == partition, "scontrol partition mismatch")
    qos = fields.get("QOS", "")
    contract = SCHEDULER_CONTRACTS.get((partition, qos))
    require(contract is not None, f"unexpected partition/QoS pair: {(partition, qos)!r}")
    cpus_per_task = int(environment.get("SLURM_CPUS_PER_TASK", "0"))
    require(cpus_per_task == contract["cpus_per_task"], "unexpected CPUs per task")
    require(fields.get("NumCPUs") == str(cpus_per_task), "scontrol CPU count mismatch")
    require(fields.get("CPUs/Task") == str(cpus_per_task), "scontrol CPUs/task mismatch")
    require(fields.get("MinMemoryNode") == contract["min_memory_node"], "unexpected memory request")
    require(fields.get("TimeLimit") == "02:00:00", "unexpected Slurm time limit")
    require(environment.get("SLURM_JOB_NODELIST") == "projgpu39", "unexpected Slurm node")
    require(fields.get("NodeList") == "projgpu39", "scontrol node mismatch")
    require("gres/gpu=2" in fields.get("TRES", "").split(","), "unexpected GPU allocation")
    return {
        "job_id": job_id,
        "partition": partition,
        "qos": qos,
        "node_list": "projgpu39",
        "cpus_per_task": cpus_per_task,
        "min_memory_node": fields["MinMemoryNode"],
        "time_limit": fields["TimeLimit"],
    }


def collect_cluster_receipt() -> dict[str, Any]:
    job_id = os.environ.get("SLURM_JOB_ID", "")
    visible = [item.strip() for item in os.environ.get("CUDA_VISIBLE_DEVICES", "").split(",") if item.strip()]
    require(job_id.isdigit(), "G0 must run inside a Slurm job")
    require(len(visible) == 2 and len(set(visible)) == 2, "exactly two visible GPUs are required")

    job_line = subprocess.run(
        ["scontrol", "show", "job", "-o", job_id],
        check=True,
        capture_output=True,
        text=True,
    ).stdout.strip()
    scheduler = validate_scheduler_allocation(dict(os.environ), job_line)

    gpus = []
    for visible_id in visible:
        line = subprocess.run(
            [
                "nvidia-smi",
                "-i",
                visible_id,
                "--query-gpu=name,uuid,memory.total",
                "--format=csv,noheader,nounits",
            ],
            check=True,
            capture_output=True,
            text=True,
        ).stdout.strip()
        rows = list(csv.reader([line], skipinitialspace=True))
        require(len(rows) == 1 and len(rows[0]) == 3, "unexpected nvidia-smi output")
        name, uuid, memory = rows[0]
        memory_mib = int(memory)
        require("PRO 6000" in name.upper(), f"unexpected GPU model: {name}")
        require(memory_mib >= 90_000, f"GPU memory below 90,000 MiB: {memory_mib}")
        gpus.append(
            {"visible_id": visible_id, "name": name, "uuid": uuid, "memory_total_mib": memory_mib}
        )
    require(len({gpu["uuid"] for gpu in gpus}) == 2, "GPU UUIDs are not unique")
    return {
        **scheduler,
        "visible_devices": visible,
        "gpus": gpus,
        "scontrol_sha256": hashlib.sha256(job_line.encode()).hexdigest(),
    }


def collect_runtime_and_model(snapshot: Path) -> dict[str, Any]:
    versions = {"python": sys.version.split()[0]}
    for name in ("torch", "transformers", "accelerate", "deepspeed"):
        module = importlib.import_module(name)
        versions[name] = str(getattr(module, "__version__", "unknown"))

    from transformers import AutoConfig, AutoTokenizer

    config = AutoConfig.from_pretrained(snapshot, local_files_only=True, trust_remote_code=False)
    tokenizer = AutoTokenizer.from_pretrained(snapshot, local_files_only=True, trust_remote_code=False)
    require(getattr(config, "model_type", None) == "qwen3", "unexpected model_type")
    require(getattr(config, "hidden_size", None) == 2048, "unexpected hidden_size")
    require(len(tokenizer) == 151_669, "unexpected tokenizer size")
    return {
        "versions": versions,
        "model_config": {
            "model_type": config.model_type,
            "hidden_size": config.hidden_size,
            "tokenizer_size": len(tokenizer),
        },
    }


def validate_source(source_root: Path, expected_commit: str) -> dict[str, Any]:
    source = git_state(source_root, expected_commit)
    root = Path(source["path"])
    launcher = root / "src/mle_critic/scripts/train/pro6000/train_rm_confirmatory_one.sh"
    trainer = root / "src/mle_critic/src/train/bradley_terry.py"
    training_config = root / "src/mle_critic/src/train/config/bradley_terry_config.py"
    zero3 = root / "src/mle_critic/recipes/zero3.yaml"
    timing_test = root / "src/mle_critic/test/test_wall_clock_receipt_callback.py"
    for path in (launcher, trainer, training_config, zero3, timing_test):
        require(path.is_file(), f"missing source artifact: {path}")
    subprocess.run(["bash", "-n", str(launcher)], check=True)
    launcher_text = launcher.read_text(encoding="utf-8")
    require('--max_steps "$CONFIRM_MAX_STEPS"' in launcher_text, "source launcher lacks max_steps")
    require("test_pairs" not in launcher_text, "source launcher contains a test-pair argument")
    require('--task_cond true' in launcher_text, "source launcher does not pin task conditioning")
    require('--budget_cond false' in launcher_text, "source launcher does not disable budget conditioning")
    trainer_text = trainer.read_text(encoding="utf-8")
    for marker in (
        "train_begin",
        "optimizer_step_1",
        "optimizer_step_final",
        "dev_evaluate_complete",
        "train_end",
    ):
        require(marker in trainer_text, f"source trainer lacks timing marker: {marker}")
    source["artifacts"] = {
        path.relative_to(root).as_posix(): {"bytes": path.stat().st_size, "sha256": sha256_file(path)}
        for path in (launcher, trainer, training_config, zero3, timing_test)
    }
    return source


def parse_elapsed_seconds(value: str) -> float:
    parts = value.split(":")
    require(len(parts) in {2, 3}, f"unexpected elapsed-time format: {value}")
    numbers = [float(part) for part in parts]
    if len(numbers) == 2:
        minutes, seconds = numbers
        return minutes * 60 + seconds
    hours, minutes, seconds = numbers
    return hours * 3600 + minutes * 60 + seconds


def parse_timing_receipts(log_text: str) -> dict[str, Any]:
    worker_prefix = "[g0-worker-timing] "
    trainer_prefix = "[rm-timing] "
    worker_rows = []
    trainer_rows = []
    for line in log_text.splitlines():
        if worker_prefix in line:
            worker_rows.append(json.loads(line.split(worker_prefix, 1)[1]))
        if trainer_prefix in line:
            trainer_rows.append(json.loads(line.split(trainer_prefix, 1)[1]))
    require(
        [row.get("event") for row in worker_rows] == ["launcher_start"],
        "expected exactly one launcher_start timing receipt",
    )
    expected_events = [
        "train_begin",
        "optimizer_step_1",
        "optimizer_step_final",
        "dev_evaluate_complete",
        "train_end",
    ]
    require(
        [row.get("event") for row in trainer_rows] == expected_events,
        "trainer timing event sequence mismatch",
    )
    require(
        [row.get("global_step") for row in trainer_rows] == [0, 1, 10, 10, 10],
        "trainer timing global steps mismatch",
    )
    rows = worker_rows + trainer_rows
    monotonic = [int(row["monotonic_ns"]) for row in rows]
    require(
        all(later > earlier for earlier, later in zip(monotonic, monotonic[1:])),
        "timing is not monotonic",
    )
    by_event = {row["event"]: int(row["monotonic_ns"]) for row in rows}
    seconds = {
        "launcher_to_train_begin": (by_event["train_begin"] - by_event["launcher_start"]) / 1e9,
        "train_begin_to_step1": (by_event["optimizer_step_1"] - by_event["train_begin"]) / 1e9,
        "step1_to_step10": (by_event["optimizer_step_final"] - by_event["optimizer_step_1"]) / 1e9,
        "dev_evaluation": (
            by_event["dev_evaluate_complete"] - by_event["optimizer_step_final"]
        )
        / 1e9,
        "train_begin_to_train_end": (by_event["train_end"] - by_event["train_begin"]) / 1e9,
        "launcher_to_train_end": (by_event["train_end"] - by_event["launcher_start"]) / 1e9,
    }
    require(all(value >= 0 for value in seconds.values()), "negative timing interval")
    return {"events": rows, "seconds": seconds}


def validate_training_artifacts(
    output_dir: Path,
    launcher_log: Path,
    resource_usage: Path,
    telemetry_path: Path,
    preflight: dict[str, Any],
) -> dict[str, Any]:
    checkpoints = sorted(path for path in output_dir.glob("checkpoint-*") if path.is_dir())
    require([path.name for path in checkpoints] == ["checkpoint-10"], "expected only checkpoint-10")
    checkpoint = checkpoints[0]
    state = load_json(checkpoint / "trainer_state.json")
    metadata = load_json(checkpoint / "rm_meta.json")

    require(state.get("global_step") == 10, "trainer global_step is not 10")
    best_checkpoint = Path(str(state.get("best_model_checkpoint", ""))).name
    require(best_checkpoint == "checkpoint-10", "best checkpoint is not checkpoint-10")
    history = state.get("log_history")
    require(isinstance(history, list), "trainer log_history is missing")
    eval_rows = [row for row in history if isinstance(row, dict) and "eval_pair_accuracy" in row]
    require(len(eval_rows) == 1, f"expected exactly one dev evaluation, found {len(eval_rows)}")
    eval_row = eval_rows[0]
    require(eval_row.get("step") == 10, "dev evaluation did not occur at step 10")
    for key, value in eval_row.items():
        if key.startswith("eval_") and isinstance(value, (int, float)):
            require(math.isfinite(float(value)), f"non-finite dev metric: {key}")
    accuracy = float(eval_row["eval_pair_accuracy"])
    require(0.0 <= accuracy <= 1.0, "dev pair accuracy is outside [0, 1]")
    require(math.isclose(float(state.get("best_metric")), accuracy), "best metric disagrees with dev accuracy")

    expected_meta = {
        "protocol": "rm-dev-selected-checkpoint-v1",
        "max_len": 16_384,
        "head_frac": 0.25,
        "task_cond": True,
        "budget_cond": False,
        "budget_pos": "head",
        "seed": 6,
        "train_pairs_sha256": EXPECTED_INPUTS["train"]["sha256"],
        "dev_pairs_sha256": EXPECTED_INPUTS["dev"]["sha256"],
        "cards_sha256": EXPECTED_INPUTS["cards"]["sha256"],
        "train_pairs": 4_689,
        "dev_pairs": 551,
        "metric_for_best_model": "eval_pair_accuracy",
        "greater_is_better": True,
        "training_code_git_commit": preflight["source"]["commit"],
        "split_name": "in-task-train-run-dev",
        "separation": {
            "train_pairs": 4_689,
            "dev_pairs": 551,
            "train_endpoints": 4_095,
            "dev_endpoints": 626,
            "train_runs": 430,
            "dev_runs": 81,
        },
    }
    for key, value in expected_meta.items():
        require(metadata.get(key) == value, f"checkpoint metadata mismatch: {key}")
    require(
        Path(str(metadata.get("base_model", ""))).resolve()
        == Path(preflight["model"]["snapshot"]).resolve(),
        "checkpoint base model is not the pinned snapshot",
    )
    require(
        math.isclose(float(metadata.get("best_dev_pair_accuracy")), accuracy),
        "checkpoint dev accuracy disagrees with trainer state",
    )

    log_text = launcher_log.read_text(encoding="utf-8", errors="replace")
    require(not FORBIDDEN_RUNTIME_PATTERN.search(log_text), "launcher log mentions a forbidden test path")
    require(
        "processes=2 effective_pair_batch=128 max_len=16384" in log_text,
        "launcher log is missing the fixed batch/context receipt",
    )
    require(
        "max_steps=10 scheduler=cosine warmup_ratio=0.03" in log_text,
        "launcher log is missing the fixed step/scheduler receipt",
    )
    require("[rm-hf] training complete" in log_text, "training completion marker is missing")
    timing = parse_timing_receipts(log_text)

    usage_text = resource_usage.read_text(encoding="utf-8", errors="replace")
    require("Exit status: 0" in usage_text, "GNU time did not record exit status 0")
    elapsed_match = re.search(
        r"Elapsed \(wall clock\) time .*?:\s*([0-9:.]+)\s*$", usage_text, re.MULTILINE
    )
    require(elapsed_match is not None, "GNU time elapsed duration is missing")
    elapsed_seconds = parse_elapsed_seconds(elapsed_match.group(1))
    require(
        elapsed_seconds >= timing["seconds"]["train_begin_to_train_end"],
        "GNU elapsed time is shorter than callback training time",
    )

    with telemetry_path.open("r", encoding="utf-8", newline="") as handle:
        telemetry = list(csv.DictReader(handle))
    require(telemetry, "GPU telemetry is empty")
    uuids = {row["uuid"] for row in telemetry}
    require(len(uuids) == 2, "telemetry does not contain exactly two GPU UUIDs")
    require(all("PRO 6000" in row["name"].upper() for row in telemetry), "telemetry GPU mismatch")
    peak_memory = max(int(float(row["memory_used_mib"])) for row in telemetry)

    artifacts = {}
    for path in sorted(item for item in checkpoint.rglob("*") if item.is_file()):
        artifacts[path.relative_to(output_dir).as_posix()] = {
            "bytes": path.stat().st_size,
            "sha256": sha256_file(path),
        }
    return {
        "checkpoint": str(checkpoint.resolve()),
        "global_step": 10,
        "dev_evaluations": 1,
        "dev_pair_accuracy": accuracy,
        "peak_gpu_memory_mib": peak_memory,
        "gpu_uuids": sorted(uuids),
        "timing": timing,
        "gnu_elapsed_seconds": elapsed_seconds,
        "checkpoint_artifacts": artifacts,
    }


def command_assets(args: argparse.Namespace) -> None:
    verifier_path = Path(__file__).resolve(strict=True)
    source = validate_source(Path(args.source_root), args.expected_source_commit)
    inputs = {
        "train": validate_input(Path(args.train_pairs), "train"),
        "dev": validate_input(Path(args.dev_pairs), "dev"),
        "cards": validate_input(Path(args.cards), "cards"),
    }
    model = validate_model_snapshot(Path(args.model_snapshot), Path(args.model_manifest))
    runtime = collect_runtime_and_model(Path(args.model_snapshot))
    receipt = {
        "status": "G0_STATIC_ASSETS_PASS",
        "protocol": PROTOCOL,
        "created_at_utc": dt.datetime.now(dt.timezone.utc).isoformat(),
        "gpu_jobs": 0,
        "api_calls": 0,
        "test_pair_reads": 0,
        "verifier": {
            "path": str(verifier_path),
            "bytes": verifier_path.stat().st_size,
            "sha256": sha256_file(verifier_path),
        },
        "source": source,
        "inputs": inputs,
        "model": model,
        "runtime": runtime,
        "fixed_config": FIXED_CONFIG,
    }
    write_json_exclusive(Path(args.receipt), receipt)


def command_preflight(args: argparse.Namespace) -> None:
    for key, value in os.environ.items():
        require(not FORBIDDEN_RUNTIME_PATTERN.search(key), f"forbidden test-like environment key: {key}")
        require(
            not FORBIDDEN_RUNTIME_PATTERN.search(value),
            f"forbidden test-like value in environment key: {key}",
        )
    run_root = Path(args.run_root).resolve()
    require(run_root.is_dir(), "run root must already exist")
    output_dir = Path(args.output_dir).resolve()
    receipt_path = Path(args.receipt).resolve()
    require(output_dir.parent == run_root, "training output must be a direct child of run root")
    require(receipt_path.parent == run_root, "preflight receipt must be a direct child of run root")
    require(not output_dir.exists(), "training output directory already exists")

    source = validate_source(Path(args.source_root), args.expected_source_commit)
    control = git_state(Path(args.control_root))
    require(not run_root.is_relative_to(Path(source["path"])), "run root is inside source worktree")
    require(not run_root.is_relative_to(Path(control["path"])), "run root is inside control worktree")
    launcher = Path(source["path"]) / "src/mle_critic/scripts/train/pro6000/train_rm_confirmatory_one.sh"
    cluster = collect_cluster_receipt()

    inputs = {
        "train": validate_input(Path(args.train_pairs), "train"),
        "dev": validate_input(Path(args.dev_pairs), "dev"),
        "cards": validate_input(Path(args.cards), "cards"),
    }
    model = validate_model_snapshot(Path(args.model_snapshot), Path(args.model_manifest))
    runtime = collect_runtime_and_model(Path(args.model_snapshot))
    receipt = {
        "status": "G0_PREFLIGHT_PASS",
        "protocol": PROTOCOL,
        "created_at_utc": dt.datetime.now(dt.timezone.utc).isoformat(),
        "scope": "dev-only engineering calibration; no test input is accepted",
        "verifier": {
            "path": str(Path(__file__).resolve(strict=True)),
            "bytes": Path(__file__).stat().st_size,
            "sha256": sha256_file(Path(__file__)),
        },
        "source": source,
        "control": control,
        "launcher_sha256": sha256_file(launcher),
        "inputs": inputs,
        "model": model,
        "runtime": runtime,
        "cluster": cluster,
        "fixed_config": FIXED_CONFIG,
    }
    write_json_exclusive(Path(args.receipt), receipt)


def command_verify(args: argparse.Namespace) -> None:
    preflight_path = Path(args.preflight).resolve(strict=True)
    preflight = load_json(preflight_path)
    require(preflight.get("status") == "G0_PREFLIGHT_PASS", "preflight receipt is not valid")
    require(preflight.get("protocol") == PROTOCOL, "preflight protocol mismatch")
    require(preflight.get("fixed_config") == FIXED_CONFIG, "fixed configuration mismatch")

    git_state(Path(preflight["source"]["path"]), preflight["source"]["commit"])
    git_state(Path(preflight["control"]["path"]), preflight["control"]["commit"])
    for label in ("train", "dev", "cards"):
        current = validate_input(Path(preflight["inputs"][label]["path"]), label)
        require(current == preflight["inputs"][label], f"{label} changed after preflight")
    current_model = validate_model_snapshot(
        Path(preflight["model"]["snapshot"]), Path(preflight["model"]["manifest"])
    )
    require(current_model == preflight["model"], "model snapshot changed after preflight")

    result = validate_training_artifacts(
        Path(args.output_dir).resolve(strict=True),
        Path(args.launcher_log).resolve(strict=True),
        Path(args.resource_usage).resolve(strict=True),
        Path(args.telemetry).resolve(strict=True),
        preflight,
    )
    receipt = {
        "status": "G0_ENGINEERING_CALIBRATION_VALID",
        "protocol": PROTOCOL,
        "verified_at_utc": dt.datetime.now(dt.timezone.utc).isoformat(),
        "preflight": str(preflight_path),
        "preflight_sha256": sha256_file(preflight_path),
        "result": result,
        "scientific_claim": "none; dev-only budget calibration",
    }
    write_json_exclusive(Path(args.receipt), receipt)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser()
    subparsers = parser.add_subparsers(dest="command", required=True)

    assets = subparsers.add_parser("assets")
    for name in (
        "source_root",
        "expected_source_commit",
        "train_pairs",
        "dev_pairs",
        "cards",
        "model_snapshot",
        "model_manifest",
        "receipt",
    ):
        assets.add_argument("--" + name.replace("_", "-"), required=True)
    assets.set_defaults(func=command_assets)

    preflight = subparsers.add_parser("preflight")
    for name in (
        "run_root",
        "output_dir",
        "source_root",
        "expected_source_commit",
        "control_root",
        "train_pairs",
        "dev_pairs",
        "cards",
        "model_snapshot",
        "model_manifest",
        "receipt",
    ):
        preflight.add_argument("--" + name.replace("_", "-"), required=True)
    preflight.set_defaults(func=command_preflight)

    verify = subparsers.add_parser("verify")
    for name in (
        "preflight",
        "output_dir",
        "launcher_log",
        "resource_usage",
        "telemetry",
        "receipt",
    ):
        verify.add_argument("--" + name.replace("_", "-"), required=True)
    verify.set_defaults(func=command_verify)
    return parser


def main() -> None:
    args = build_parser().parse_args()
    try:
        args.func(args)
    except (ContractError, FileNotFoundError, KeyError, ValueError, subprocess.CalledProcessError) as error:
        raise SystemExit(f"G0 contract failure: {error}") from error


if __name__ == "__main__":
    main()
