"""Close the complete E1 collection before opening any sealed D_val value."""

from __future__ import annotations

import argparse
import json
import math
import os
import pathlib
import shutil
import sys
import tempfile
from collections import defaultdict
from typing import Any

from phase1.balanced_continuation_e1_scoring import CREDENTIAL, file_sha256
from phase1.balanced_continuation_real_contract import (
    RealContractError,
    canonical_json,
    validate_sealed_label_receipt,
    validate_worker_contract,
)
from phase1.verify_balanced_continuation_real_worker import (
    checked,
    read_jsonl_bytes,
)


SCHEMA = "balanced-continuation-e1-collection-v1"
WORKER_RECEIPT_STATUS = "VERIFIED_REAL_E1_ROLLOUT_COMMITMENT_ONLY"
TASKS = ("spaceship-titanic", "tabular-playground-series-may-2022")
EXPECTED_ROLLOUTS = 8
EXPECTED_CANDIDATE_ATTEMPTS = 16
EXPECTED_OPERATOR_CALLS = 8
FAILURE_UTILITY = 0.0
PRACTICAL_DELTA = 0.01


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


def mean(values: list[float]) -> float:
    if not values:
        raise CollectionError("cannot average an empty value list")
    return sum(values) / len(values)


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
        assignment_receipt.get("status") != "VERIFIED_OUTCOME_BLIND_BALANCED_ASSIGNMENT"
        or assignment_receipt.get("independent_reconstruction_exact") is not True
        or assignment_receipt.get("rollout_jobs") != EXPECTED_ROLLOUTS
        or assignment_receipt.get("siblings_per_anchor") != 2
        or assignment_receipt.get("replicates_per_sibling") != 2
        or assignment_receipt.get("continuation_horizon") != 1
    ):
        raise CollectionError("independent assignment receipt differs from frozen E1")
    assignment_rows = [row for _, row in read_jsonl_bytes(
        assignment_root / "assignment_manifest.jsonl"
    )]
    if len(assignment_rows) != EXPECTED_ROLLOUTS:
        raise CollectionError("assignment does not contain eight E1 rollouts")
    rollout_ids = [row["rollout_id"] for row in assignment_rows]
    if len(set(rollout_ids)) != EXPECTED_ROLLOUTS:
        raise CollectionError("assignment rollout IDs are not unique")

    # Coverage closes completely before this function reads a single sealed JSON value.
    if not worker_root.is_dir() or worker_root.is_symlink():
        raise CollectionError("worker output root differs")
    worker_entries = {path.name for path in worker_root.iterdir()}
    if any(name.startswith(".inflight-") for name in worker_entries):
        raise CollectionError("inflight rollout artifacts remain")
    if worker_entries != set(rollout_ids):
        raise CollectionError("worker rollout coverage differs from assignment")
    if not receipt_root.is_dir() or receipt_root.is_symlink():
        raise CollectionError("worker receipt root differs")
    expected_receipt_names = {f"{rollout_id}.verify.json" for rollout_id in rollout_ids}
    if {path.name for path in receipt_root.iterdir()} != expected_receipt_names:
        raise CollectionError("worker verification receipt coverage differs")
    if not workspace_root.is_dir() or workspace_root.is_symlink():
        raise CollectionError("workspace root differs")
    if {path.name for path in workspace_root.iterdir()} != set(rollout_ids):
        raise CollectionError("workspace coverage differs from assignment")
    if not sealed_root.is_dir() or sealed_root.is_symlink():
        raise CollectionError("sealed root differs")
    if {path.name for path in sealed_root.iterdir()} != set(rollout_ids):
        raise CollectionError("sealed rollout coverage differs from assignment")

    receipts: list[dict[str, Any]] = []
    workspace_paths: set[str] = set()
    workspace_tokens: set[str] = set()
    candidate_attempts = 0
    operator_calls = 0
    candidate_processes = 0
    task_counts: dict[str, int] = defaultdict(int)
    sibling_counts: dict[str, int] = defaultdict(int)
    block_members: dict[str, set[str]] = defaultdict(set)
    for index, assignment in enumerate(assignment_rows):
        receipt = checked(receipt_root / f"{assignment['rollout_id']}.verify.json")
        required_identity = {
            "rollout_id": assignment["rollout_id"],
            "global_order": index,
            "block_id": assignment["block_id"],
            "block_replicate": assignment["block_replicate"],
            "task": assignment["task"],
            "sibling_id": assignment["sibling_id"],
            "source_run_id": assignment["source_run_id"],
            "source_commit": checked(contract_path)["source_commit"],
        }
        if (
            receipt.get("status") != WORKER_RECEIPT_STATUS
            or receipt.get("worker_imported") is not False
            or receipt.get("sealed_values_opened") is not False
            or any(receipt.get(key) != value for key, value in required_identity.items())
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
        task_counts[assignment["task"]] += 1
        sibling_counts[assignment["sibling_id"]] += 1
        block_members[assignment["block_id"]].add(assignment["sibling_id"])
        receipts.append(receipt)
    if (
        len(workspace_paths) != EXPECTED_ROLLOUTS
        or len(workspace_tokens) != EXPECTED_ROLLOUTS
        or candidate_attempts != EXPECTED_CANDIDATE_ATTEMPTS
        or operator_calls != EXPECTED_OPERATOR_CALLS
        or task_counts != {task: 4 for task in TASKS}
        or set(sibling_counts.values()) != {2}
        or len(sibling_counts) != 4
        or len(block_members) != 4
        or any(len(members) != 2 for members in block_members.values())
    ):
        raise CollectionError("complete E1 accounting/balance gate differs")

    coverage_gate = {
        "all_eight_assignment_rollouts_present": True,
        "all_eight_independent_worker_receipts_present": True,
        "no_inflight_rollouts": True,
        "unique_workspace_paths": 8,
        "unique_workspace_tokens": 8,
        "candidate_execution_attempts": candidate_attempts,
        "operator_calls": operator_calls,
        "retry_count": 0,
        "dtest_rows_read": 0,
        "sealed_values_opened_before_coverage_gate": False,
    }

    # Only the complete-coverage branch below parses D_val JSON.
    contract_raw = contract_path.read_bytes()
    if CREDENTIAL.search(contract_raw):
        raise CollectionError("credential-shaped bytes in real contract")
    contract = validate_worker_contract(json.loads(contract_raw))
    rollout_rows: list[dict[str, Any]] = []
    sealed_files_opened = 0
    for assignment, receipt in zip(assignment_rows, receipts):
        dval_raw: list[float | None] = []
        dval_effective: list[float] = []
        for ordinal in range(2):
            sealed_path = sealed_root / assignment["rollout_id"] / f"dval_{ordinal:03d}.json"
            sealed = validate_sealed_label_receipt(checked(sealed_path), contract)
            sealed_files_opened += 1
            if (
                sealed["rollout_id"] != assignment["rollout_id"]
                or sealed["workspace_token"] != receipt["workspace_token"]
                or sealed["task"] != assignment["task"]
                or sealed["execution_ordinal"] != ordinal
                or file_sha256(sealed_path)
                != receipt["sealed_dval_commitment_sha256s"][ordinal]
            ):
                raise CollectionError("opened sealed D_val receipt identity differs")
            utility = finite_or_none(sealed["dval_utility"], "D_val utility")
            dval_raw.append(utility)
            dval_effective.append(FAILURE_UTILITY if utility is None else utility)
        dsearch_raw = [
            finite_or_none(value, "D_search utility")
            for value in receipt["visible_dsearch_utilities"]
        ]
        dsearch_effective = [FAILURE_UTILITY if value is None else value for value in dsearch_raw]
        gain = dval_effective[1] - dval_effective[0]
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
            "warm_dsearch_utility_raw": dsearch_raw[0],
            "continuation_dsearch_utility_raw": dsearch_raw[1],
            "warm_dval_utility_raw": dval_raw[0],
            "continuation_dval_utility_raw": dval_raw[1],
            "warm_dval_utility_effective": dval_effective[0],
            "best_within_h_dval_utility_effective": dval_effective[1],
            "gain_over_warm_dval": gain,
            "gain_exceeds_practical_delta": gain >= PRACTICAL_DELTA,
            "failure_utility": FAILURE_UTILITY,
            "practical_delta": PRACTICAL_DELTA,
            "candidate_wall_time_seconds": receipt["candidate_wall_time_seconds"],
            "candidate_processes_started": receipt["candidate_processes_started"],
            "operator_api_calls": 1,
            "operator_usage": receipt["api_usage"],
        })
    if sealed_files_opened != 16:
        raise CollectionError("sealed D_val open count differs")

    sibling_groups: dict[tuple[str, str], list[dict[str, Any]]] = defaultdict(list)
    for row in rollout_rows:
        sibling_groups[(row["task"], row["sibling_id"])].append(row)
    sibling_rows: list[dict[str, Any]] = []
    for (task, sibling), rows in sorted(sibling_groups.items()):
        rows.sort(key=lambda row: row["block_replicate"])
        values = [row["best_within_h_dval_utility_effective"] for row in rows]
        gains = [row["gain_over_warm_dval"] for row in rows]
        sibling_rows.append({
            "schema_version": SCHEMA,
            "task": task,
            "sibling_id": sibling,
            "replicates": 2,
            "balanced_vh_mean": mean(values),
            "balanced_vh_sample_variance": (values[0] - values[1]) ** 2 / 2,
            "mean_gain_over_warm": mean(gains),
            "practical_success_probability": mean([
                float(row["gain_exceeds_practical_delta"]) for row in rows
            ]),
        })

    task_diagnostics: list[dict[str, Any]] = []
    for task in TASKS:
        task_rows = [row for row in rollout_rows if row["task"] == task]
        winners = []
        for replicate in range(2):
            block = [row for row in task_rows if row["block_replicate"] == replicate]
            if len(block) != 2:
                raise CollectionError("task replicate block is incomplete after open")
            first, second = block
            if first["best_within_h_dval_utility_effective"] == second[
                "best_within_h_dval_utility_effective"
            ]:
                winners.append("tie")
            else:
                winners.append(max(
                    block, key=lambda row: row["best_within_h_dval_utility_effective"]
                )["sibling_id"])
        task_diagnostics.append({
            "schema_version": SCHEMA,
            "task": task,
            "rollouts": 4,
            "replicate_winners": winners,
            "replicate_ranking_agreement": winners[0] == winners[1],
            "mean_gain_over_warm": mean([
                row["gain_over_warm_dval"] for row in task_rows
            ]),
            "positive_gain_rollouts": sum(
                row["gain_over_warm_dval"] > 0 for row in task_rows
            ),
            "practical_gain_rollouts": sum(
                row["gain_exceeds_practical_delta"] for row in task_rows
            ),
        })

    staging = output.parent / f".{output.name}.staging"
    if staging.exists() or staging.is_symlink():
        raise CollectionError("collection staging root already exists")
    staging.mkdir()
    try:
        write_jsonl(staging / "rollouts.jsonl", rollout_rows)
        write_jsonl(staging / "sibling_labels.jsonl", sibling_rows)
        write_jsonl(staging / "task_diagnostics.jsonl", task_diagnostics)
        total_candidate_wall = sum(
            sum(row["candidate_wall_time_seconds"]) for row in rollout_rows
        )
        summary = {
            "schema_version": SCHEMA,
            "status": "VERIFIED_COMPLETE_REAL_E1_COLLECTION_DESCRIPTIVE_ONLY",
            "coverage_gate": coverage_gate,
            "source_commit": contract["source_commit"],
            "tasks": list(TASKS),
            "rollout_jobs": 8,
            "candidate_execution_attempts": 16,
            "candidate_processes_started": candidate_processes,
            "operator_api_calls": 8,
            "operator_retry_count": 0,
            "candidate_retry_count": 0,
            "analyze_operator_calls": 0,
            "dtest_rows_read": 0,
            "sealed_values_opened": True,
            "sealed_files_opened_after_coverage_gate": sealed_files_opened,
            "failure_utility": FAILURE_UTILITY,
            "practical_delta": PRACTICAL_DELTA,
            "total_candidate_wall_seconds": total_candidate_wall,
            "realized_candidate_gpu_hours": total_candidate_wall / 3600,
            "rollouts_with_positive_dval_gain": sum(
                row["gain_over_warm_dval"] > 0 for row in rollout_rows
            ),
            "rollouts_with_practical_dval_gain": sum(
                row["gain_exceeds_practical_delta"] for row in rollout_rows
            ),
            "task_replicate_ranking_agreements": sum(
                row["replicate_ranking_agreement"] for row in task_diagnostics
            ),
            "primary_gate_claim_allowed": False,
            "e2_e3_unlocked": False,
            "interpretation": "E1 is an engineering smoke and descriptive effect-size probe only",
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
        CollectionError,
        RealContractError,
        OSError,
        ValueError,
        json.JSONDecodeError,
    ) as exc:
        print(f"VERIFY_BALANCED_E1_COLLECTION_ERROR: {exc}", file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
