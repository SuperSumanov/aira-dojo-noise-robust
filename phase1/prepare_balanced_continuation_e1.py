"""Freeze the real balanced-continuation E1 contract, assignment, and phased run plan."""

from __future__ import annotations

import argparse
import datetime as dt
import json
import os
import pathlib
import shutil
import subprocess
import sys
import tempfile
from typing import Any

from phase1.balanced_continuation_e1_scoring import (
    CREDENTIAL,
    canonical_json,
    checked_json,
    evaluator_bundle_sha256,
    file_sha256,
    sha256_bytes,
)
from phase1.balanced_continuation_manifest import ManifestError, build as build_assignment
from phase1.balanced_continuation_operator_entry import (
    MODEL_ID,
    TEMPERATURE,
    operator_config_sha256,
    prompt_bundle_sha256,
)
from phase1.balanced_continuation_real_contract import (
    REAL_BACKEND,
    WORKER_CONTRACT_SCHEMA,
    RealContractError,
    validate_worker_contract,
)


SCHEMA = "balanced-continuation-e1-preparation-v1"
RUN_PLAN_SCHEMA = "balanced-continuation-e1-run-plan-v1"
EXPECTED_CONTAINER_SHA256 = "801f646bed3cae6e74e10d793e71b0086658d4303d54552333c58125ddf9beda"
TASKS = ("spaceship-titanic", "tabular-playground-series-may-2022")
HORIZON = 1
SIBLINGS = 2
REPLICATES = 2
ASSIGNMENT_SEED = 20260814
EXECUTION_TIMEOUT_SECONDS = 600
OPERATOR_TIMEOUT_SECONDS = 240
EVALUATOR_TIMEOUT_SECONDS = 120
EXPECTED_GPU_HOURS = 3.24


class PrepareError(RuntimeError):
    pass


def utc_now() -> str:
    return dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds").replace(
        "+00:00", "Z"
    )


def repo_root() -> pathlib.Path:
    return pathlib.Path(__file__).resolve().parents[1]


def exact_source_commit() -> str:
    root = repo_root()
    head = subprocess.run(
        ["git", "rev-parse", "HEAD"], cwd=root, check=True,
        stdout=subprocess.PIPE, stderr=subprocess.PIPE,
    ).stdout.decode("ascii").strip()
    dirty = subprocess.run(
        ["git", "status", "--porcelain"], cwd=root, check=True,
        stdout=subprocess.PIPE, stderr=subprocess.PIPE,
    ).stdout
    if dirty:
        raise PrepareError("E1 preparation requires an exact clean Git worktree")
    return head


def atomic_json(path: pathlib.Path, value: Any) -> None:
    if path.exists() or path.is_symlink():
        raise PrepareError(f"refusing existing output: {path}")
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, name = tempfile.mkstemp(prefix=f".{path.name}.", suffix=".tmp", dir=path.parent)
    temporary = pathlib.Path(name)
    try:
        with os.fdopen(fd, "wb") as handle:
            handle.write(canonical_json(value) + b"\n")
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary, path)
    finally:
        if temporary.exists():
            temporary.unlink()


def evaluator_contract_sha(real: dict[str, Any]) -> str:
    return sha256_bytes(canonical_json({
        "split_manifest_sha256_opaque": real["split_manifest_sha256_opaque"],
        "search_evaluator_executable_sha256": real["search_evaluator_executable_sha256"],
        "sealed_label_evaluator_executable_sha256": real[
            "sealed_label_evaluator_executable_sha256"
        ],
        "score_visibility": real["score_visibility"],
        "sealed_label_policy": real["sealed_label_policy"],
    }))


def read_jsonl(path: pathlib.Path) -> list[dict[str, Any]]:
    rows = []
    for line in path.read_bytes().splitlines():
        value = json.loads(line)
        if not isinstance(value, dict):
            raise PrepareError(f"JSONL row is not an object: {path.name}")
        rows.append(value)
    return rows


def build(args: argparse.Namespace) -> dict[str, Any]:
    source_commit = exact_source_commit()
    data_gate = pathlib.Path(args.data_gate).resolve()
    container = pathlib.Path(args.container).resolve()
    output = pathlib.Path(args.output).resolve()
    if output.exists() or output.is_symlink():
        raise PrepareError("E1 preparation output must be new")
    if not data_gate.is_dir() or data_gate.is_symlink():
        raise PrepareError("verified data-gate root is missing or symlinked")
    if not container.is_file() or container.is_symlink():
        raise PrepareError("container image is missing or symlinked")
    if file_sha256(container) != EXPECTED_CONTAINER_SHA256:
        raise PrepareError("container SHA-256 differs")
    input_root = data_gate / "e1_inputs"
    split_root = data_gate / "e1_split"
    input_receipt = checked_json(data_gate / "e1_inputs.verify.json")
    split_receipt = checked_json(data_gate / "e1_split.verify.json")
    if input_receipt.get("status") != "VERIFIED_E1_INPUTS_OUTCOME_BLIND_ZERO_FROZEN_OVERLAP":
        raise PrepareError("E1 input independent-verification receipt differs")
    if split_receipt.get("status") != "VERIFIED_E1_SPLIT_RECONSTRUCTION_NO_DTEST_READ":
        raise PrepareError("E1 split independent-verification receipt differs")
    input_summary = checked_json(input_root / "summary.json")
    split_summary = checked_json(split_root / "summary.json")
    if (
        input_summary.get("contains_outcomes") is not False
        or input_summary.get("first960_or_prospective_read") is not False
        or input_summary.get("selected_frozen_endpoint_overlap") != 0
        or input_summary.get("selected_frozen_run_overlap") != 0
        or input_summary.get("tasks") != list(TASKS)
    ):
        raise PrepareError("E1 outcome-blind input summary differs")
    if (
        split_summary.get("tasks") != list(TASKS)
        or split_summary.get("dtest_rows_read") != 0
        or split_summary.get("private_answers_read") is not False
    ):
        raise PrepareError("E1 split summary differs")

    root = output.parent / f".{output.name}.staging"
    if root.exists() or root.is_symlink():
        raise PrepareError("E1 preparation staging root already exists")
    root.mkdir()
    try:
        from phase1 import balanced_continuation_dsearch_eval as dsearch_module
        from phase1 import balanced_continuation_dval_sealer as dval_module

        real_contract = {
            "schema_version": WORKER_CONTRACT_SCHEMA,
            "backend": REAL_BACKEND,
            "source_commit": source_commit,
            "container_sha256": EXPECTED_CONTAINER_SHA256,
            "operator_config_sha256": operator_config_sha256(),
            "prompt_sha256": prompt_bundle_sha256(),
            "public_dataset_contract_sha256": split_summary[
                "public_dataset_contract_sha256"
            ],
            "split_manifest_sha256_opaque": split_summary[
                "split_manifest_sha256_opaque"
            ],
            "search_evaluator_executable_sha256": evaluator_bundle_sha256(
                pathlib.Path(dsearch_module.__file__).resolve()
            ),
            "sealed_label_evaluator_executable_sha256": evaluator_bundle_sha256(
                pathlib.Path(dval_module.__file__).resolve()
            ),
            "public_data_root": (split_root / "public").resolve().as_posix(),
            "continuation_horizon": HORIZON,
            "operator_timeout_seconds": OPERATOR_TIMEOUT_SECONDS,
            "execution_timeout_seconds": EXECUTION_TIMEOUT_SECONDS,
            "evaluator_timeout_seconds": EVALUATOR_TIMEOUT_SECONDS,
            "operator_policy": "debug_if_buggy_else_improve",
            "operator_calls_per_transition": 1,
            "operator_retry_count": 0,
            "execution_retry_count": 0,
            "analyze_operator_calls": 0,
            "workspace_policy": "fresh_per_rollout",
            "candidate_mount_policy": "public_read_only_no_private",
            "score_visibility": "D_search_only",
            "sealed_label_policy": "D_val_external_mode_0600",
            "split_policy": "80/10/10_D_train_D_search_D_val",
            "dtest_policy": "never_read",
        }
        validate_worker_contract(real_contract)
        legacy_contract = {
            "schema_version": "balanced-continuation-contract-v1",
            "model_id": MODEL_ID,
            "provider": "deepseek",
            "operator_config_sha256": real_contract["operator_config_sha256"],
            "prompt_sha256": real_contract["prompt_sha256"],
            "source_commit": source_commit,
            "dataset_contract_sha256": real_contract["public_dataset_contract_sha256"],
            "evaluator_contract_sha256": evaluator_contract_sha(real_contract),
            "hardware_class": "single-rtx3090-24gb",
            "execution_timeout_seconds": EXECUTION_TIMEOUT_SECONDS,
            "continuation_horizon": HORIZON,
            "debug_policy": "fixed_one_operator_per_step",
            "workspace_policy": "fresh_per_rollout",
            "temperature": TEMPERATURE,
        }
        real_path = root / "real_contract.json"
        legacy_path = root / "execution_contract.json"
        atomic_json(real_path, real_contract)
        atomic_json(legacy_path, legacy_contract)
        assignment_root = root / "assignment"
        rc = build_assignment(argparse.Namespace(
            anchors=str((input_root / "anchors.jsonl").resolve()),
            contract=str(legacy_path.resolve()),
            output=str(assignment_root.resolve()),
            siblings_per_anchor=SIBLINGS,
            replicates=REPLICATES,
            horizon=HORIZON,
            seed=ASSIGNMENT_SEED,
            created_utc=args.created_utc,
        ))
        if rc != 0:
            raise PrepareError(f"balanced assignment producer failed rc={rc}")
        assignments = read_jsonl(assignment_root / "assignment_manifest.jsonl")
        if len(assignments) != 8:
            raise PrepareError("E1 assignment does not contain exactly eight rollouts")
        stage_one = sorted(
            row["global_order"] for row in assignments if row["block_replicate"] == 0
        )
        stage_two = sorted(set(range(8)) - set(stage_one))
        if len(stage_one) != 4 or len(stage_two) != 4:
            raise PrepareError("E1 phased block allocation differs")
        stage_one_rows = [assignments[index] for index in stage_one]
        if {row["task"] for row in stage_one_rows} != set(TASKS):
            raise PrepareError("E1 first stage does not cover both tasks")
        for task in TASKS:
            task_rows = [row for row in stage_one_rows if row["task"] == task]
            if len(task_rows) != 2 or len({row["block_id"] for row in task_rows}) != 1:
                raise PrepareError(f"E1 first stage is not one complete block for {task}")
        run_plan = {
            "schema_version": RUN_PLAN_SCHEMA,
            "status": "FROZEN_OUTCOME_BLIND_E1_RUN_PLAN",
            "source_commit": source_commit,
            "data_gate_source_commit": (data_gate / "source_commit.txt").read_text(
                encoding="utf-8"
            ).strip(),
            "data_gate_top_manifest_sha256": file_sha256(data_gate / "top_manifest.sha256"),
            "tasks": list(TASKS),
            "anchors_per_task": 1,
            "siblings_per_anchor": SIBLINGS,
            "replicates": REPLICATES,
            "continuation_horizon": HORIZON,
            "rollout_jobs": 8,
            "candidate_executions": 16,
            "operator_api_calls": 8,
            "expected_gpu_hours": EXPECTED_GPU_HOURS,
            "candidate_timeout_seconds": EXECUTION_TIMEOUT_SECONDS,
            "candidate_timeout_upper_bound_gpu_hours": 16 * EXECUTION_TIMEOUT_SECONDS / 3600,
            "slurm_array_concurrency": 4,
            "gpus_per_job": 1,
            "excluded_nodes": ["projgpu7", "projgpu8", "projgpu33", "gpu36", "gpu38"],
            "stage_one_engineering_gate_indices": stage_one,
            "stage_two_remaining_indices": stage_two,
            "stage_one_outcomes_must_remain_sealed": True,
            "stage_two_gate_uses_scores": False,
            "e2_e3_authorized": False,
        }
        atomic_json(root / "run_plan.json", run_plan)
        source_inputs = {
            "schema_version": SCHEMA,
            "created_utc": args.created_utc,
            "source_commit": source_commit,
            "data_gate_root": data_gate.as_posix(),
            "data_gate_source_commit": run_plan["data_gate_source_commit"],
            "input_verification_receipt_sha256": file_sha256(
                data_gate / "e1_inputs.verify.json"
            ),
            "split_verification_receipt_sha256": file_sha256(
                data_gate / "e1_split.verify.json"
            ),
            "anchors_sha256": file_sha256(input_root / "anchors.jsonl"),
            "code_vault_sha256": file_sha256(input_root / "code_vault.jsonl"),
            "real_contract_sha256": file_sha256(real_path),
            "execution_contract_sha256": file_sha256(legacy_path),
            "container_path": container.as_posix(),
            "container_sha256": EXPECTED_CONTAINER_SHA256,
            "contains_outcomes": False,
            "first960_or_prospective_read": False,
            "dtest_rows_read": 0,
        }
        atomic_json(root / "source_inputs.json", source_inputs)
        manifest = {
            path.relative_to(root).as_posix(): file_sha256(path)
            for path in sorted(root.rglob("*"))
            if path.is_file() and path.name != "sha256_manifest.json"
        }
        atomic_json(root / "sha256_manifest.json", manifest)
        if CREDENTIAL.search(b"".join(path.read_bytes() for path in root.rglob("*") if path.is_file())):
            raise PrepareError("credential-shaped bytes found in E1 preparation artifact")
        os.replace(root, output)
    finally:
        if root.exists():
            shutil.rmtree(root)
    summary = checked_json(output / "run_plan.json")
    print(canonical_json(summary).decode("utf-8"))
    return summary


def parser() -> argparse.ArgumentParser:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--data-gate", required=True)
    ap.add_argument("--container", required=True)
    ap.add_argument("--output", required=True)
    ap.add_argument("--created-utc", default=utc_now())
    return ap


def main() -> int:
    try:
        build(parser().parse_args())
    except (
        PrepareError,
        ManifestError,
        RealContractError,
        OSError,
        ValueError,
        json.JSONDecodeError,
        subprocess.SubprocessError,
    ) as exc:
        print(f"PREPARE_BALANCED_E1_ERROR: {exc}", file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
