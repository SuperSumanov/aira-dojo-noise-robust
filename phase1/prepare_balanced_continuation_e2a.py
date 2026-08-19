"""Freeze the six-task E2-A contracts, variable-K assignment, and score-blind waves."""

from __future__ import annotations

import argparse
import datetime as dt
import json
import os
import pathlib
import shutil
import subprocess
import sys
from typing import Any

from phase1 import balanced_continuation_qwen_operator_entry as qwen_operator
from phase1.balanced_continuation_e2a_manifest import (
    ManifestError,
    build as build_assignment,
)
from phase1.balanced_continuation_e2a_scoring import (
    CREDENTIAL,
    TASK_SPECS,
    canonical_json,
    checked_json,
    evaluator_bundle_sha256,
    file_sha256,
    sha256_bytes,
)
from phase1.balanced_continuation_real_contract import (
    REAL_BACKEND,
    WORKER_CONTRACT_SCHEMA,
    RealContractError,
    validate_worker_contract,
)
from phase1.prepare_balanced_continuation_e1 import (
    EXPECTED_CONTAINER_SHA256,
    QWEN_REPAIRED_EXECUTION_GATE_SHA256,
    WORKER_PYTHON,
    atomic_json,
    evaluator_contract_sha,
    validate_qwen_execution_gate,
)


SCHEMA = "balanced-continuation-e2a-preparation-v1"
RUN_PLAN_SCHEMA = "balanced-continuation-e2a-run-plan-v1"
TASKS = tuple(TASK_SPECS)
HORIZON = 1
SIBLINGS = 2
ASSIGNMENT_SEED = 20260819
EXECUTION_TIMEOUT_SECONDS = 600
OPERATOR_TIMEOUT_SECONDS = 240
EVALUATOR_TIMEOUT_SECONDS = 120
EXPECTED_GPU_HOURS = 10.247889130908273
HARD_GPU_HOURS = 20.0
WARM_SMOKE_CANDIDATE_EXECUTIONS = 6
WARM_SMOKE_HARD_GPU_HOURS = 1.0
GIT_NO_LFS = [
    "-c", "filter.lfs.smudge=", "-c", "filter.lfs.process=",
    "-c", "filter.lfs.required=false",
]


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
        ["git", *GIT_NO_LFS, "rev-parse", "HEAD"], cwd=root, check=True,
        stdout=subprocess.PIPE, stderr=subprocess.PIPE,
    ).stdout.decode("ascii").strip()
    dirty = subprocess.run(
        ["git", *GIT_NO_LFS, "status", "--porcelain"], cwd=root, check=True,
        stdout=subprocess.PIPE, stderr=subprocess.PIPE,
    ).stdout
    if dirty:
        raise PrepareError("E2-A preparation requires an exact clean Git worktree")
    return head


def read_jsonl(path: pathlib.Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for line in path.read_bytes().splitlines():
        value = json.loads(line)
        if not isinstance(value, dict):
            raise PrepareError(f"JSONL row is not an object: {path.name}")
        rows.append(value)
    return rows


def require_data_gate(data_gate: pathlib.Path) -> tuple[pathlib.Path, pathlib.Path, dict, dict]:
    if not data_gate.is_dir() or data_gate.is_symlink():
        raise PrepareError("verified E2-A data-gate root is missing or symlinked")
    input_root = data_gate / "e2a_inputs"
    split_root = data_gate / "e2a_split"
    if (
        not input_root.is_dir() or input_root.is_symlink()
        or not split_root.is_dir() or split_root.is_symlink()
    ):
        raise PrepareError("E2-A input/split root differs")
    input_receipt = checked_json(data_gate / "e2a_inputs.verify.json")
    split_receipt = checked_json(data_gate / "e2a_split.verify.json")
    if (
        input_receipt.get("status")
        != "VERIFIED_E2A_INPUTS_OUTCOME_BLIND_DISTINCT_RUNS"
        or input_receipt.get("producer_imported") is not False
        or input_receipt.get("tasks") != list(TASKS)
        or input_receipt.get("anchors") != 24
        or input_receipt.get("physical_runs") != 24
        or input_receipt.get("siblings") != 48
        or input_receipt.get("calibration_anchors") != 6
        or input_receipt.get("scientific_outcomes_read") is not False
        or input_receipt.get("official_test_read") is not False
        or input_receipt.get("first960_or_prospective_read") is not False
    ):
        raise PrepareError("E2-A input verification receipt differs")
    if (
        split_receipt.get("status")
        != "VERIFIED_E2A_SPLIT_RECONSTRUCTION_NO_DTEST_READ"
        or split_receipt.get("producer_imported") is not False
        or split_receipt.get("tasks") != list(TASKS)
        or split_receipt.get("dtest_rows_read") != 0
        or split_receipt.get("official_sample_submission_read") is not False
        or split_receipt.get("private_answers_read") is not False
    ):
        raise PrepareError("E2-A split verification receipt differs")
    input_summary = checked_json(input_root / "summary.json")
    split_summary = checked_json(split_root / "summary.json")
    if (
        input_summary.get("status") != "E2A_INPUTS_FROZEN_OUTCOME_BLIND"
        or input_summary.get("tasks") != list(TASKS)
        or input_summary.get("anchor_count") != 24
        or input_summary.get("physical_run_count") != 24
        or input_summary.get("sibling_count") != 48
        or input_summary.get("calibration_anchor_count") != 6
        or input_summary.get("contains_outcomes") is not False
        or input_summary.get("scientific_outcomes_read") is not False
        or input_summary.get("official_test_read") is not False
        or input_summary.get("first960_or_prospective_read") is not False
    ):
        raise PrepareError("E2-A input summary differs")
    if (
        split_summary.get("status") != "VERIFIED_E2A_80_10_10_SPLIT_BUILT"
        or split_summary.get("tasks") != list(TASKS)
        or split_summary.get("dtest_rows_read") != 0
        or split_summary.get("official_sample_submission_read") is not False
        or split_summary.get("private_answers_read") is not False
    ):
        raise PrepareError("E2-A split summary differs")
    if (
        input_receipt.get("result_manifest_sha256")
        != file_sha256(input_root / "sha256_manifest.json")
        or split_receipt.get("result_manifest_sha256")
        != file_sha256(split_root / "sha256_manifest.json")
        or input_summary.get("anchors_sha256") != file_sha256(input_root / "anchors.jsonl")
        or input_summary.get("code_vault_sha256")
        != file_sha256(input_root / "code_vault.jsonl")
        or input_summary.get("calibration_anchor_ids_sha256")
        != file_sha256(input_root / "calibration_anchor_ids.json")
    ):
        raise PrepareError("E2-A data-gate hash binding differs")
    return input_root, split_root, input_summary, split_summary


def build(args: argparse.Namespace) -> dict[str, Any]:
    source_commit = exact_source_commit()
    data_gate = pathlib.Path(args.data_gate).resolve()
    container = pathlib.Path(args.container).resolve()
    output = pathlib.Path(args.output).resolve()
    if output.exists() or output.is_symlink():
        raise PrepareError("E2-A preparation output must be new")
    if not container.is_file() or container.is_symlink():
        raise PrepareError("container image is missing or symlinked")
    if file_sha256(container) != EXPECTED_CONTAINER_SHA256:
        raise PrepareError("container SHA-256 differs")
    if not WORKER_PYTHON.is_file() or WORKER_PYTHON.is_symlink():
        raise PrepareError("shared worker Python is missing or symlinked")
    qwen_gate_path, qwen_gate_sha = validate_qwen_execution_gate(
        getattr(args, "qwen_execution_smoke_receipt", None)
    )
    if qwen_gate_sha != QWEN_REPAIRED_EXECUTION_GATE_SHA256:
        raise PrepareError("historical Qwen operator execution gate differs")
    input_root, split_root, input_summary, split_summary = require_data_gate(data_gate)

    staging = output.parent / f".{output.name}.staging"
    if staging.exists() or staging.is_symlink():
        raise PrepareError("E2-A preparation staging root already exists")
    staging.mkdir()
    try:
        from phase1 import balanced_continuation_e2a_dsearch_eval as dsearch_module
        from phase1 import balanced_continuation_e2a_dval_sealer as dval_module

        real_contract = {
            "schema_version": WORKER_CONTRACT_SCHEMA,
            "backend": REAL_BACKEND,
            "source_commit": source_commit,
            "container_sha256": EXPECTED_CONTAINER_SHA256,
            "operator_config_sha256": qwen_operator.operator_config_sha256(),
            "prompt_sha256": qwen_operator.prompt_bundle_sha256(),
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
            "model_id": qwen_operator.MODEL_ID,
            "provider": qwen_operator.PROVIDER,
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
            "temperature": qwen_operator.TEMPERATURE,
        }
        real_path = staging / "real_contract.json"
        legacy_path = staging / "execution_contract.json"
        atomic_json(real_path, real_contract)
        atomic_json(legacy_path, legacy_contract)
        assignment_root = staging / "assignment"
        build_assignment(argparse.Namespace(
            anchors=str((input_root / "anchors.jsonl").resolve()),
            calibration_anchors=str((input_root / "calibration_anchor_ids.json").resolve()),
            contract=str(legacy_path.resolve()),
            output=str(assignment_root.resolve()),
            siblings_per_anchor=SIBLINGS,
            horizon=HORIZON,
            seed=ASSIGNMENT_SEED,
            created_utc=args.created_utc,
        ))
        assignments = read_jsonl(assignment_root / "assignment_manifest.jsonl")
        calibration_value = json.loads(
            (input_root / "calibration_anchor_ids.json").read_bytes()
        )
        if not isinstance(calibration_value, list):
            raise PrepareError("E2-A calibration anchor list differs")
        calibration = set(calibration_value)
        if len(assignments) != 60 or len(calibration) != 6:
            raise PrepareError("E2-A assignment/calibration count differs")
        engineering = sorted(
            row["global_order"] for row in assignments
            if row["anchor_id"] in calibration and row["block_replicate"] == 0
        )
        remaining = sorted(set(range(60)) - set(engineering))
        if len(engineering) != 12 or len(remaining) != 48:
            raise PrepareError("E2-A score-blind wave sizes differ")
        engineering_rows = [assignments[index] for index in engineering]
        if {row["task"] for row in engineering_rows} != set(TASKS):
            raise PrepareError("E2-A engineering wave task coverage differs")
        for task in TASKS:
            rows = [row for row in engineering_rows if row["task"] == task]
            if len(rows) != 2 or len({row["block_id"] for row in rows}) != 1:
                raise PrepareError(f"E2-A engineering wave is not one full block: {task}")
        warm_smoke = []
        for task in TASKS:
            task_rows = [
                row for row in assignments
                if row["task"] == task and row["block_replicate"] == 0
            ]
            selected = min(
                task_rows,
                key=lambda row: sha256_bytes(canonical_json({
                    "protocol": "balanced-continuation-e2a-warm-smoke-selection-v1",
                    "task": task,
                    "sibling_id": row["sibling_id"],
                })),
            )
            warm_smoke.append(selected["global_order"])
        if len(warm_smoke) != 6 or len(set(warm_smoke)) != 6:
            raise PrepareError("E2-A warm-smoke selection differs")

        run_plan = {
            "schema_version": RUN_PLAN_SCHEMA,
            "status": "FROZEN_OUTCOME_BLIND_E2A_RUN_PLAN",
            "source_commit": source_commit,
            "data_gate_source_commit": (data_gate / "source_commit.txt").read_text(
                encoding="utf-8"
            ).strip(),
            "data_gate_top_manifest_sha256": file_sha256(data_gate / "top_manifest.sha256"),
            "tasks": list(TASKS),
            "anchors_per_task": 4,
            "siblings_per_anchor": 2,
            "broad_replicates": 1,
            "calibration_anchor_count": 6,
            "calibration_replicates": 2,
            "continuation_horizon": 1,
            "rollout_jobs": 60,
            "candidate_executions": 120,
            "operator_api_calls": 60,
            "operator_profile": "qwen",
            "operator_model_id": qwen_operator.MODEL_ID,
            "historical_qwen_execution_gate_sha256": qwen_gate_sha,
            "expected_gpu_hours": EXPECTED_GPU_HOURS,
            "candidate_timeout_upper_bound_gpu_hours": HARD_GPU_HOURS,
            "worker_python_path": WORKER_PYTHON.as_posix(),
            "worker_python_sha256": file_sha256(WORKER_PYTHON),
            "candidate_timeout_seconds": EXECUTION_TIMEOUT_SECONDS,
            "operator_timeout_seconds": OPERATOR_TIMEOUT_SECONDS,
            "slurm_array_concurrency": 4,
            "gpus_per_job": 1,
            "excluded_nodes": ["projgpu7", "projgpu8", "projgpu33", "gpu36", "gpu38"],
            "warm_smoke_tasks": list(TASKS),
            "warm_smoke_candidate_executions": WARM_SMOKE_CANDIDATE_EXECUTIONS,
            "warm_smoke_operator_api_calls": 0,
            "warm_smoke_hard_gpu_hours": WARM_SMOKE_HARD_GPU_HOURS,
            "warm_smoke_assignment_indices": warm_smoke,
            "formal_submission_requires_passing_warm_smoke": True,
            "engineering_wave_indices": engineering,
            "remaining_wave_indices": remaining,
            "engineering_wave_outcomes_must_remain_sealed": True,
            "remaining_wave_gate_uses_scores": False,
            "adaptive_allocation_allowed": False,
            "post_outcome_replacement_allowed": False,
        }
        atomic_json(staging / "run_plan.json", run_plan)
        source_inputs = {
            "schema_version": SCHEMA,
            "created_utc": args.created_utc,
            "source_commit": source_commit,
            "data_gate_root": data_gate.as_posix(),
            "data_gate_source_commit": run_plan["data_gate_source_commit"],
            "input_verification_receipt_sha256": file_sha256(
                data_gate / "e2a_inputs.verify.json"
            ),
            "split_verification_receipt_sha256": file_sha256(
                data_gate / "e2a_split.verify.json"
            ),
            "anchors_sha256": input_summary["anchors_sha256"],
            "code_vault_sha256": input_summary["code_vault_sha256"],
            "calibration_anchor_ids_sha256": input_summary[
                "calibration_anchor_ids_sha256"
            ],
            "real_contract_sha256": file_sha256(real_path),
            "execution_contract_sha256": file_sha256(legacy_path),
            "container_path": container.as_posix(),
            "container_sha256": EXPECTED_CONTAINER_SHA256,
            "worker_python_path": run_plan["worker_python_path"],
            "worker_python_sha256": run_plan["worker_python_sha256"],
            "operator_profile": "qwen",
            "operator_model_id": qwen_operator.MODEL_ID,
            "historical_qwen_execution_gate_path": qwen_gate_path.as_posix(),
            "historical_qwen_execution_gate_sha256": qwen_gate_sha,
            "contains_outcomes": False,
            "first960_or_prospective_read": False,
            "dtest_rows_read": 0,
        }
        atomic_json(staging / "source_inputs.json", source_inputs)
        manifest = {
            path.relative_to(staging).as_posix(): file_sha256(path)
            for path in sorted(staging.rglob("*"))
            if path.is_file() and path.name != "sha256_manifest.json"
        }
        atomic_json(staging / "sha256_manifest.json", manifest)
        if CREDENTIAL.search(b"".join(
            path.read_bytes() for path in staging.rglob("*") if path.is_file()
        )):
            raise PrepareError("credential-shaped bytes found in E2-A preparation")
        os.replace(staging, output)
    finally:
        if staging.exists():
            shutil.rmtree(staging)
    summary = checked_json(output / "run_plan.json")
    print(canonical_json(summary).decode("utf-8"))
    return summary


def parser() -> argparse.ArgumentParser:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--data-gate", required=True)
    ap.add_argument("--container", required=True)
    ap.add_argument("--output", required=True)
    ap.add_argument("--qwen-execution-smoke-receipt", required=True)
    ap.add_argument("--created-utc", default=utc_now())
    return ap


def main() -> int:
    try:
        build(parser().parse_args())
    except (
        PrepareError, ManifestError, RealContractError, OSError, UnicodeError,
        ValueError, json.JSONDecodeError, subprocess.SubprocessError,
    ) as exc:
        print(f"PREPARE_BALANCED_E2A_ERROR: {exc}", file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
