"""Close E2-A coverage, then open sealed values and apply the frozen support gates."""

from __future__ import annotations

import argparse
import json
import math
import os
import pathlib
import shutil
import sys
import tempfile
from collections import Counter, defaultdict
from typing import Any

from phase1.balanced_continuation_e2a_scoring import (
    CREDENTIAL,
    TASK_SPECS,
    analysis_utility,
    file_sha256,
)
from phase1.balanced_continuation_real_contract import (
    RealContractError,
    canonical_json,
    validate_execution_receipt,
    validate_search_receipt,
    validate_sealed_label_receipt,
    validate_worker_contract,
)
from phase1.verify_balanced_continuation_real_worker import checked, read_jsonl_bytes


SCHEMA = "balanced-continuation-e2a-collection-v1"
TASKS = tuple(TASK_SPECS)
WORKER_RECEIPT_STATUS = "VERIFIED_REAL_E2A_ROLLOUT_COMMITMENT_ONLY"
EXPECTED_ROLLOUTS = 60
EXPECTED_CANDIDATE_ATTEMPTS = 120
EXPECTED_OPERATOR_CALLS = 60
MAX_REALIZED_GPU_HOURS = 12.5
MIN_CONTINUATION_ARTIFACT_RATE = 0.50


class CollectionError(RuntimeError):
    pass


def atomic_bytes(path: pathlib.Path, raw: bytes) -> None:
    if path.exists() or path.is_symlink():
        raise CollectionError(f"refusing existing output: {path}")
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, name = tempfile.mkstemp(prefix=f".{path.name}.", suffix=".tmp", dir=path.parent)
    temporary = pathlib.Path(name)
    try:
        with os.fdopen(fd, "wb") as handle:
            handle.write(raw)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary, path)
    finally:
        if temporary.exists():
            temporary.unlink()


def atomic_json(path: pathlib.Path, value: Any) -> None:
    atomic_bytes(path, canonical_json(value) + b"\n")


def write_jsonl(path: pathlib.Path, rows: list[dict[str, Any]]) -> None:
    atomic_bytes(path, b"".join(canonical_json(row) + b"\n" for row in rows))


def finite_or_none(value: Any, where: str) -> float | None:
    if value is None:
        return None
    if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value):
        raise CollectionError(f"{where} must be null or finite numeric")
    return float(value)


def require_roots(
    worker_root: pathlib.Path,
    receipt_root: pathlib.Path,
    workspace_root: pathlib.Path,
    sealed_root: pathlib.Path,
    rollout_ids: list[str],
) -> None:
    expected = set(rollout_ids)
    if not worker_root.is_dir() or worker_root.is_symlink():
        raise CollectionError("worker output root differs")
    worker_entries = {path.name for path in worker_root.iterdir()}
    if any(name.startswith(".inflight-") for name in worker_entries):
        raise CollectionError("inflight rollout artifacts remain")
    if worker_entries != expected:
        raise CollectionError("worker rollout coverage differs")
    if not receipt_root.is_dir() or receipt_root.is_symlink():
        raise CollectionError("worker receipt root differs")
    if {path.name for path in receipt_root.iterdir()} != {
        f"{rollout_id}.verify.json" for rollout_id in rollout_ids
    }:
        raise CollectionError("worker verification receipt coverage differs")
    if not workspace_root.is_dir() or workspace_root.is_symlink():
        raise CollectionError("workspace root differs")
    if {path.name for path in workspace_root.iterdir()} != expected:
        raise CollectionError("workspace coverage differs")
    if not sealed_root.is_dir() or sealed_root.is_symlink():
        raise CollectionError("sealed root differs")
    if {path.name for path in sealed_root.iterdir()} != expected:
        raise CollectionError("sealed rollout coverage differs")


def failure_class(execution: dict[str, Any], submission_valid: bool) -> str:
    if execution["execution_status"] != "ok":
        return str(execution["execution_status"])
    if execution["artifact_sha256"] is None:
        return "no_artifact"
    if not submission_valid:
        return "invalid_submission"
    return "valid"


def unique_winner(rows: list[dict[str, Any]]) -> str | None:
    if len(rows) != 2 or len({row["sibling_id"] for row in rows}) != 2:
        raise CollectionError("sibling block is not exact-two")
    first, second = rows
    left = first["continuation_dval_analysis_utility"]
    right = second["continuation_dval_analysis_utility"]
    if left == right:
        return None
    return first["sibling_id"] if left > right else second["sibling_id"]


def verify(args: argparse.Namespace) -> dict[str, Any]:
    assignment_root = pathlib.Path(args.assignment_result).resolve()
    assignment_receipt_path = pathlib.Path(args.assignment_receipt).resolve()
    worker_root = pathlib.Path(args.worker_output_root).resolve()
    receipt_root = pathlib.Path(args.worker_receipt_root).resolve()
    workspace_root = pathlib.Path(args.workspace_root).resolve()
    sealed_root = pathlib.Path(args.sealed_root).resolve()
    contract_path = pathlib.Path(args.real_contract).resolve()
    output = pathlib.Path(args.output).resolve()
    if output.exists() or output.is_symlink():
        raise CollectionError("collection output must be new")
    assignment_receipt = checked(assignment_receipt_path)
    if (
        assignment_receipt.get("status")
        != "VERIFIED_E2A_OUTCOME_BLIND_VARIABLE_K_ASSIGNMENT"
        or assignment_receipt.get("independent_reconstruction_exact") is not True
        or assignment_receipt.get("rollout_jobs") != EXPECTED_ROLLOUTS
        or assignment_receipt.get("planned_total_candidate_executions")
        != EXPECTED_CANDIDATE_ATTEMPTS
        or assignment_receipt.get("planned_operator_api_calls") != EXPECTED_OPERATOR_CALLS
        or assignment_receipt.get("anchor_count") != 24
        or assignment_receipt.get("physical_run_count") != 24
        or assignment_receipt.get("task_count") != 6
        or assignment_receipt.get("block_count") != 30
        or assignment_receipt.get("siblings_once") != 36
        or assignment_receipt.get("siblings_twice") != 12
    ):
        raise CollectionError("independent assignment receipt differs from frozen E2-A")
    assignments = [
        row for _, row in read_jsonl_bytes(assignment_root / "assignment_manifest.jsonl")
    ]
    if len(assignments) != EXPECTED_ROLLOUTS:
        raise CollectionError("assignment does not contain 60 E2-A rollouts")
    rollout_ids = [row["rollout_id"] for row in assignments]
    if len(set(rollout_ids)) != EXPECTED_ROLLOUTS:
        raise CollectionError("assignment rollout IDs are not unique")
    if Counter(row["task"] for row in assignments) != Counter({task: 10 for task in TASKS}):
        raise CollectionError("assignment task balance differs")
    if Counter(Counter(row["sibling_id"] for row in assignments).values()) != Counter({1: 36, 2: 12}):
        raise CollectionError("assignment variable-K exposure differs")
    blocks: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in assignments:
        blocks[row["block_id"]].append(row)
    if len(blocks) != 30 or any(
        len(rows) != 2 or len({row["sibling_id"] for row in rows}) != 2
        for rows in blocks.values()
    ):
        raise CollectionError("assignment block completeness differs")

    # No sealed JSON is parsed before every assignment and independent worker receipt closes.
    require_roots(worker_root, receipt_root, workspace_root, sealed_root, rollout_ids)
    contract_identity = checked(contract_path)["source_commit"]
    receipts: list[dict[str, Any]] = []
    workspace_paths: set[str] = set()
    workspace_tokens: set[str] = set()
    candidate_attempts = 0
    operator_calls = 0
    candidate_processes = 0
    for index, assignment in enumerate(assignments):
        receipt = checked(receipt_root / f"{assignment['rollout_id']}.verify.json")
        identity = {
            "rollout_id": assignment["rollout_id"],
            "global_order": index,
            "block_id": assignment["block_id"],
            "block_replicate": assignment["block_replicate"],
            "task": assignment["task"],
            "sibling_id": assignment["sibling_id"],
            "source_run_id": assignment["source_run_id"],
            "source_commit": contract_identity,
        }
        if (
            receipt.get("status") != WORKER_RECEIPT_STATUS
            or receipt.get("worker_imported") is not False
            or receipt.get("sealed_values_opened") is not False
            or any(receipt.get(key) != value for key, value in identity.items())
            or receipt.get("candidate_execution_attempts") != 2
            or receipt.get("operator_calls") != 1
            or receipt.get("operator_retry_count") != 0
            or receipt.get("candidate_retry_count") != 0
            or receipt.get("dtest_rows_read") != 0
            or receipt.get("network_disabled_verified") is not True
            or receipt.get("public_mount_read_only_verified") is not True
            or receipt.get("private_mounts_verified_zero") is not True
            or receipt.get("sealed_receipts") != 2
            or receipt.get("sealed_modes_0600_verified") is not True
            or not isinstance(receipt.get("api_usage"), list)
            or len(receipt["api_usage"]) != 1
            or receipt["api_usage"][0].get("api_calls") != 1
            or receipt["api_usage"][0].get("retry_count") != 0
        ):
            raise CollectionError(f"worker receipt differs at assignment index {index}")
        commitments = receipt.get("sealed_dval_commitment_sha256s")
        if not isinstance(commitments, list) or len(commitments) != 2:
            raise CollectionError("worker sealed commitment list differs")
        workspace_path = receipt.get("workspace_path")
        workspace_token = receipt.get("workspace_token")
        if not isinstance(workspace_path, str) or not isinstance(workspace_token, str):
            raise CollectionError("worker workspace identity differs")
        workspace_paths.add(workspace_path)
        workspace_tokens.add(workspace_token)
        candidate_attempts += receipt["candidate_execution_attempts"]
        operator_calls += receipt["operator_calls"]
        candidate_processes += receipt["candidate_processes_started"]
        receipts.append(receipt)
    if (
        len(workspace_paths) != EXPECTED_ROLLOUTS
        or len(workspace_tokens) != EXPECTED_ROLLOUTS
        or candidate_attempts != EXPECTED_CANDIDATE_ATTEMPTS
        or operator_calls != EXPECTED_OPERATOR_CALLS
    ):
        raise CollectionError("complete E2-A accounting gate differs")
    coverage_gate = {
        "all_60_assignment_rollouts_present": True,
        "all_60_independent_worker_receipts_present": True,
        "no_inflight_rollouts": True,
        "unique_workspace_paths": 60,
        "unique_workspace_tokens": 60,
        "candidate_execution_attempts": 120,
        "operator_calls": 60,
        "retry_count": 0,
        "dtest_rows_read": 0,
        "sealed_values_opened_before_coverage_gate": False,
    }

    contract_raw = contract_path.read_bytes()
    if CREDENTIAL.search(contract_raw):
        raise CollectionError("credential-shaped bytes in real contract")
    contract = validate_worker_contract(json.loads(contract_raw))
    rollout_rows: list[dict[str, Any]] = []
    sealed_files_opened = 0
    continuation_artifacts = 0
    for assignment, receipt in zip(assignments, receipts):
        steps: list[dict[str, Any]] = []
        rollout_root = worker_root / assignment["rollout_id"] / "steps"
        for ordinal in range(2):
            step_root = rollout_root / f"step_{ordinal:03d}"
            execution = validate_execution_receipt(checked(step_root / "execution.json"), contract)
            search = validate_search_receipt(checked(step_root / "dsearch.json"), contract)
            sealed_path = sealed_root / assignment["rollout_id"] / f"dval_{ordinal:03d}.json"
            sealed = validate_sealed_label_receipt(checked(sealed_path), contract)
            sealed_files_opened += 1
            if (
                execution["rollout_id"] != assignment["rollout_id"]
                or search["rollout_id"] != assignment["rollout_id"]
                or sealed["rollout_id"] != assignment["rollout_id"]
                or execution["workspace_token"] != receipt["workspace_token"]
                or search["workspace_token"] != receipt["workspace_token"]
                or sealed["workspace_token"] != receipt["workspace_token"]
                or execution["task"] != assignment["task"]
                or search["task"] != assignment["task"]
                or sealed["task"] != assignment["task"]
                or execution["execution_ordinal"] != ordinal
                or search["execution_ordinal"] != ordinal
                or sealed["execution_ordinal"] != ordinal
                or search["artifact_sha256"] != execution["artifact_sha256"]
                or sealed["artifact_sha256"] != execution["artifact_sha256"]
                or file_sha256(sealed_path)
                != receipt["sealed_dval_commitment_sha256s"][ordinal]
            ):
                raise CollectionError("opened step/sealed identity differs")
            dsearch_score = finite_or_none(search["dsearch_score"], "D_search score")
            dval_score = finite_or_none(sealed["dval_score"], "D_val score")
            steps.append({
                "execution": execution,
                "dsearch_score": dsearch_score,
                "dsearch_valid": search["submission_valid"],
                "dsearch_analysis": analysis_utility(
                    assignment["task"], dsearch_score, search["submission_valid"]
                ),
                "dval_score": dval_score,
                "dval_valid": sealed["submission_valid"],
                "dval_analysis": analysis_utility(
                    assignment["task"], dval_score, sealed["submission_valid"]
                ),
                "raw_oriented_dval_utility": finite_or_none(
                    sealed["dval_utility"], "raw oriented D_val utility"
                ),
            })
        warm, continuation = steps
        continuation_artifacts += int(continuation["execution"]["artifact_sha256"] is not None)
        rollout_rows.append({
            "schema_version": SCHEMA,
            "global_order": assignment["global_order"],
            "rollout_id": assignment["rollout_id"],
            "block_id": assignment["block_id"],
            "block_replicate": assignment["block_replicate"],
            "rollout_seed": assignment["rollout_seed"],
            "task": assignment["task"],
            "anchor_id": assignment["anchor_id"],
            "sibling_id": assignment["sibling_id"],
            "source_run_id": assignment["source_run_id"],
            "warm_dsearch_score_raw": warm["dsearch_score"],
            "continuation_dsearch_score_raw": continuation["dsearch_score"],
            "warm_dval_score_raw": warm["dval_score"],
            "continuation_dval_score_raw": continuation["dval_score"],
            "warm_dval_raw_oriented_utility": warm["raw_oriented_dval_utility"],
            "continuation_dval_raw_oriented_utility": continuation[
                "raw_oriented_dval_utility"
            ],
            "warm_dval_valid": warm["dval_valid"],
            "continuation_dval_valid": continuation["dval_valid"],
            "warm_dval_analysis_utility": warm["dval_analysis"],
            "continuation_dval_analysis_utility": continuation["dval_analysis"],
            "continuation_minus_warm_analysis_gain": (
                continuation["dval_analysis"] - warm["dval_analysis"]
            ),
            "continuation_artifact_present": continuation["execution"]["artifact_sha256"]
            is not None,
            "warm_failure_class": failure_class(warm["execution"], warm["dval_valid"]),
            "continuation_failure_class": failure_class(
                continuation["execution"], continuation["dval_valid"]
            ),
            "candidate_wall_time_seconds": receipt["candidate_wall_time_seconds"],
            "candidate_processes_started": receipt["candidate_processes_started"],
            "operator_api_calls": 1,
            "operator_usage": receipt["api_usage"],
        })
    if sealed_files_opened != 120:
        raise CollectionError("sealed D_val open count differs")

    by_anchor_rep: dict[tuple[str, int], list[dict[str, Any]]] = defaultdict(list)
    for row in rollout_rows:
        by_anchor_rep[(row["anchor_id"], row["block_replicate"])].append(row)
    broad_groups = {
        anchor: rows for (anchor, replicate), rows in by_anchor_rep.items() if replicate == 0
    }
    if len(broad_groups) != 24:
        raise CollectionError("broad parent coverage differs")
    parent_rows: list[dict[str, Any]] = []
    for anchor_id, rows in sorted(broad_groups.items()):
        winner = unique_winner(rows)
        parent_rows.append({
            "schema_version": SCHEMA,
            "anchor_id": anchor_id,
            "task": rows[0]["task"],
            "source_run_id": rows[0]["source_run_id"],
            "sibling_ids": sorted(row["sibling_id"] for row in rows),
            "winner_sibling_id": winner,
            "non_tie": winner is not None,
            "both_continuations_invalid": not any(row["continuation_dval_valid"] for row in rows),
        })

    calibration_anchors = {
        anchor for (anchor, replicate) in by_anchor_rep if replicate == 1
    }
    if len(calibration_anchors) != 6:
        raise CollectionError("calibration parent coverage differs")
    calibration_rows: list[dict[str, Any]] = []
    for anchor in sorted(calibration_anchors):
        first = sorted(by_anchor_rep[(anchor, 0)], key=lambda row: row["sibling_id"])
        second = sorted(by_anchor_rep[(anchor, 1)], key=lambda row: row["sibling_id"])
        if [row["sibling_id"] for row in first] != [row["sibling_id"] for row in second]:
            raise CollectionError("calibration sibling identity differs across replicates")
        winners = [unique_winner(first), unique_winner(second)]
        informative = all(winner is not None for winner in winners)
        validity_agreement = [
            left["continuation_dval_valid"] == right["continuation_dval_valid"]
            for left, right in zip(first, second)
        ]
        raw_differences = [
            None
            if left["continuation_dval_score_raw"] is None
            or right["continuation_dval_score_raw"] is None
            else abs(
                left["continuation_dval_score_raw"]
                - right["continuation_dval_score_raw"]
            )
            for left, right in zip(first, second)
        ]
        calibration_rows.append({
            "schema_version": SCHEMA,
            "anchor_id": anchor,
            "task": first[0]["task"],
            "source_run_id": first[0]["source_run_id"],
            "sibling_ids": [row["sibling_id"] for row in first],
            "replicate_winners": winners,
            "informative": informative,
            "winner_consistent": informative and winners[0] == winners[1],
            "per_sibling_validity_agreement": validity_agreement,
            "per_sibling_raw_score_absolute_difference": raw_differences,
            "per_sibling_analysis_utility_absolute_difference": [
                abs(
                    left["continuation_dval_analysis_utility"]
                    - right["continuation_dval_analysis_utility"]
                )
                for left, right in zip(first, second)
            ],
        })

    task_rows: list[dict[str, Any]] = []
    for task in TASKS:
        broad_rollouts = [
            row for row in rollout_rows
            if row["task"] == task and row["block_replicate"] == 0
        ]
        task_parents = [row for row in parent_rows if row["task"] == task]
        valid_values = [
            row["continuation_dval_analysis_utility"]
            for row in broad_rollouts if row["continuation_dval_valid"]
        ]
        valid_count = len(valid_values)
        task_rows.append({
            "schema_version": SCHEMA,
            "task": task,
            "broad_rollouts": len(broad_rollouts),
            "broad_parents": len(task_parents),
            "non_tie_parent_count": sum(row["non_tie"] for row in task_parents),
            "valid_continuation_count": valid_count,
            "nonvalid_continuation_count": len(broad_rollouts) - valid_count,
            "has_valid_and_nonvalid_continuations": 0 < valid_count < len(broad_rollouts),
            "all_broad_continuations_valid": valid_count == len(broad_rollouts),
            "valid_conditional_utility_has_variation": (
                len(valid_values) >= 2 and max(valid_values) > min(valid_values)
            ),
            "continuation_failure_classes": dict(sorted(Counter(
                row["continuation_failure_class"] for row in broad_rollouts
            ).items())),
        })

    total_candidate_wall = sum(
        sum(row["candidate_wall_time_seconds"]) for row in rollout_rows
    )
    realized_gpu_hours = total_candidate_wall / 3600.0
    continuation_artifact_rate = continuation_artifacts / EXPECTED_ROLLOUTS
    informative_calibration = sum(row["informative"] for row in calibration_rows)
    consistent_calibration = sum(row["winner_consistent"] for row in calibration_rows)
    tasks_three_nontie = sum(row["non_tie_parent_count"] >= 3 for row in task_rows)
    mixed_tasks = sum(row["has_valid_and_nonvalid_continuations"] for row in task_rows)
    varying_tasks = sum(row["valid_conditional_utility_has_variation"] for row in task_rows)
    all_valid_tasks = sum(row["all_broad_continuations_valid"] for row in task_rows)
    label_gate_components = {
        "calibration_informative_at_least_5_of_6": informative_calibration >= 5,
        "calibration_winner_consistent_at_least_4_of_6": consistent_calibration >= 4,
        "tasks_with_at_least_3_non_tie_parents_at_least_4_of_6": tasks_three_nontie >= 4,
        "realized_candidate_gpu_hours_at_most_12_5": realized_gpu_hours <= MAX_REALIZED_GPU_HOURS,
        "continuation_terminal_artifact_rate_at_least_0_50": (
            continuation_artifact_rate >= MIN_CONTINUATION_ARTIFACT_RATE
        ),
    }
    label_support = all(label_gate_components.values())
    hurdle_support = label_support and mixed_tasks >= 4 and varying_tasks >= 4
    quality_only_support = (
        label_support and not hurdle_support and all_valid_tasks >= 4 and varying_tasks >= 4
    )
    if hurdle_support:
        verdict = "HURDLE_SUPPORT"
    elif quality_only_support:
        verdict = "QUALITY_ONLY_SUPPORT"
    elif label_support:
        verdict = "LABEL_RESOURCE_SUPPORT_WITHOUT_METHOD_ROUTE"
    else:
        verdict = "KILL"

    staging = output.parent / f".{output.name}.staging"
    if staging.exists() or staging.is_symlink():
        raise CollectionError("collection staging root already exists")
    staging.mkdir()
    try:
        write_jsonl(staging / "rollouts.jsonl", rollout_rows)
        write_jsonl(staging / "parents.jsonl", parent_rows)
        write_jsonl(staging / "calibration.jsonl", calibration_rows)
        write_jsonl(staging / "tasks.jsonl", task_rows)
        summary = {
            "schema_version": SCHEMA,
            "status": "VERIFIED_COMPLETE_REAL_E2A_COLLECTION",
            "verdict": verdict,
            "coverage_gate": coverage_gate,
            "source_commit": contract["source_commit"],
            "tasks": list(TASKS),
            "gate_population": "broad_replicate_0_parent_balanced",
            "rollout_jobs": EXPECTED_ROLLOUTS,
            "candidate_execution_attempts": candidate_attempts,
            "candidate_processes_started": candidate_processes,
            "operator_api_calls": operator_calls,
            "operator_retry_count": 0,
            "candidate_retry_count": 0,
            "analyze_operator_calls": 0,
            "dtest_rows_read": 0,
            "sealed_values_opened": True,
            "sealed_files_opened_after_coverage_gate": sealed_files_opened,
            "realized_candidate_gpu_hours": realized_gpu_hours,
            "continuation_terminal_artifact_rate": continuation_artifact_rate,
            "calibration_informative_parents": informative_calibration,
            "calibration_winner_consistent_parents": consistent_calibration,
            "tasks_with_at_least_3_non_tie_parents": tasks_three_nontie,
            "tasks_with_valid_and_nonvalid_continuations": mixed_tasks,
            "tasks_with_valid_conditional_utility_variation": varying_tasks,
            "tasks_with_all_broad_continuations_valid": all_valid_tasks,
            "label_resource_gate_components": label_gate_components,
            "label_resource_support": label_support,
            "hurdle_support": hurdle_support,
            "quality_only_support": quality_only_support,
            "quality_only_operationalization": (
                "label gate passes, hurdle fails, at least four tasks have all broad "
                "continuations valid, and at least four tasks retain conditional variation"
            ),
            "post_outcome_replacement_count": 0,
            "primary_method_claim_allowed": False,
            "e2b_requires_separate_preregistration": label_support,
        }
        atomic_json(staging / "summary.json", summary)
        manifest = {
            path.name: file_sha256(path)
            for path in sorted(staging.iterdir())
            if path.is_file() and path.name != "sha256_manifest.json"
        }
        atomic_json(staging / "sha256_manifest.json", manifest)
        if CREDENTIAL.search(b"".join(path.read_bytes() for path in staging.iterdir())):
            raise CollectionError("credential-shaped bytes in collection output")
        os.replace(staging, output)
    finally:
        if staging.exists():
            shutil.rmtree(staging)
    print(canonical_json(summary).decode("utf-8"))
    return summary


def parser() -> argparse.ArgumentParser:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--assignment-result", required=True)
    ap.add_argument("--assignment-receipt", required=True)
    ap.add_argument("--worker-output-root", required=True)
    ap.add_argument("--worker-receipt-root", required=True)
    ap.add_argument("--workspace-root", required=True)
    ap.add_argument("--sealed-root", required=True)
    ap.add_argument("--real-contract", required=True)
    ap.add_argument("--output", required=True)
    return ap


def main() -> int:
    try:
        verify(parser().parse_args())
    except (
        CollectionError, RealContractError, OSError, UnicodeError, ValueError,
        json.JSONDecodeError,
    ) as exc:
        print(f"VERIFY_BALANCED_E2A_COLLECTION_ERROR: {exc}", file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
