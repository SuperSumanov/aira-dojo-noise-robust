"""Verify complete coverage and exact-K accounting for synthetic worker artifacts.

This collection verifier does not import the assignment producer or worker.  It consumes
the independent per-rollout receipts, checks that every frozen assignment appears exactly
once, and audits block support, fresh-workspace uniqueness, retries, replacements, and total
execution accounting.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import os
import pathlib
import re
import sys
import tempfile
from collections import Counter, defaultdict
from typing import Any


HEX64 = re.compile(r"[0-9a-f]{64}\Z")
CREDENTIAL = re.compile(
    rb"(?:^|[^A-Za-z0-9])(?:sk-[A-Za-z0-9._-]{16,}|hf_[A-Za-z0-9]{16,}|"
    rb"gh[pousr]_[A-Za-z0-9]{16,}|AKIA[0-9A-Z]{16}|AIza[0-9A-Za-z_-]{30,}|"
    rb"Bearer[ \t]+[A-Za-z0-9._-]{20,}|-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----)"
)
ASSIGNMENT_KEYS = {
    "protocol",
    "rollout_id",
    "global_order",
    "block_id",
    "block_replicate",
    "position_within_block",
    "inclusion_probability",
    "order_probability",
    "anchor_id",
    "task",
    "source_run_id",
    "parent_id",
    "sibling_id",
    "code_sha256",
    "anchor_contract_sha256",
    "execution_contract_sha256",
    "rollout_seed",
    "continuation_horizon",
    "warm_start_executions",
    "planned_continuation_executions",
}
SUMMARY_KEYS = {
    "protocol",
    "status",
    "created_utc",
    "contains_outcomes",
    "anchors_input_sha256",
    "execution_contract_sha256",
    "source_commit",
    "seed",
    "task_count",
    "anchor_count",
    "siblings_per_anchor",
    "replicates_per_sibling",
    "continuation_horizon",
    "rollout_jobs",
    "planned_warm_start_executions",
    "planned_continuation_executions",
    "planned_total_candidate_executions",
    "every_sibling_exactly_k",
    "every_block_contains_all_siblings",
    "fresh_workspace_required",
    "adaptive_allocation_allowed",
}
VERIFY_RECEIPT_KEYS = {
    "status",
    "rollout_id",
    "global_order",
    "continuation_horizon",
    "candidate_execution_attempts",
    "operator_calls",
    "retry_count",
    "replacement_count",
    "fresh_workspace_verified",
    "workspace_token",
    "best_within_h_utility",
    "gain_over_warm_start",
    "worker_sha256_manifest",
}
ASSIGNMENT_RECEIPT_KEYS = {
    "status",
    "result_sha256_manifest",
    "rollout_jobs",
    "anchor_count",
    "task_count",
    "siblings_per_anchor",
    "replicates_per_sibling",
    "continuation_horizon",
    "contains_outcomes",
    "independent_reconstruction_exact",
}
WORKER_IDENTITY_KEYS = {
    "rollout_id",
    "global_order",
    "block_id",
    "block_replicate",
    "anchor_id",
    "task",
    "sibling_id",
    "rollout_seed",
}


class CollectionVerifyError(RuntimeError):
    pass


def sha256_bytes(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def canonical_json(value: Any) -> bytes:
    return json.dumps(
        value, sort_keys=True, separators=(",", ":"), ensure_ascii=False, allow_nan=False
    ).encode("utf-8")


def checked_bytes(path: pathlib.Path) -> bytes:
    raw = path.read_bytes()
    if CREDENTIAL.search(raw):
        raise CollectionVerifyError(f"credential-shaped bytes refused before parsing: {path.name}")
    return raw


def parse_json(raw: bytes, where: str) -> dict[str, Any]:
    try:
        value = json.loads(raw)
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise CollectionVerifyError(f"invalid JSON in {where}: {exc}") from exc
    if not isinstance(value, dict):
        raise CollectionVerifyError(f"expected JSON object in {where}")
    return value


def finite_number(value: Any, where: str) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value):
        raise CollectionVerifyError(f"{where} must be a finite number")
    return float(value)


def exact_keys(value: Any, keys: set[str], where: str) -> dict[str, Any]:
    if not isinstance(value, dict) or set(value) != keys:
        actual = set(value) if isinstance(value, dict) else set()
        raise CollectionVerifyError(
            f"{where} keys differ: missing={sorted(keys - actual)} unknown={sorted(actual - keys)}"
        )
    return value


def atomic_json(path: pathlib.Path, value: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, temp_name = tempfile.mkstemp(prefix=f".{path.name}.", suffix=".tmp", dir=path.parent)
    temp = pathlib.Path(temp_name)
    try:
        with os.fdopen(fd, "wb") as handle:
            handle.write(canonical_json(value) + b"\n")
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temp, path)
    finally:
        if temp.exists():
            temp.unlink()


def load_assignments(result_dir: pathlib.Path) -> tuple[list[dict[str, Any]], dict[str, Any], str]:
    hash_manifest = parse_json(
        checked_bytes(result_dir / "sha256_manifest.json"), "assignment hash manifest"
    )
    required = {
        "anchors.input.jsonl",
        "assignment_manifest.jsonl",
        "command.txt",
        "execution_contract.input.json",
        "summary.json",
    }
    if set(hash_manifest) != required:
        raise CollectionVerifyError("assignment hash-manifest membership differs")
    for name, expected in hash_manifest.items():
        if not isinstance(expected, str) or not HEX64.fullmatch(expected):
            raise CollectionVerifyError("assignment hash manifest contains invalid digest")
        if sha256_bytes((result_dir / name).read_bytes()) != expected:
            raise CollectionVerifyError(f"assignment artifact hash mismatch: {name}")
    summary = exact_keys(
        parse_json(checked_bytes(result_dir / "summary.json"), "assignment summary"),
        SUMMARY_KEYS,
        "assignment summary",
    )
    raw = checked_bytes(result_dir / "assignment_manifest.jsonl")
    assignments = []
    for line_number, line in enumerate(raw.splitlines(), 1):
        try:
            row = json.loads(line)
        except json.JSONDecodeError as exc:
            raise CollectionVerifyError(f"invalid assignment at line {line_number}") from exc
        exact_keys(row, ASSIGNMENT_KEYS, f"assignment line {line_number}")
        if row["global_order"] != line_number - 1:
            raise CollectionVerifyError("assignment global order is not contiguous")
        assignments.append(row)
    if len(assignments) != summary["rollout_jobs"]:
        raise CollectionVerifyError("assignment row count differs from summary")
    return assignments, summary, sha256_bytes(raw)


def verify(args: argparse.Namespace) -> dict[str, Any]:
    assignment_dir = pathlib.Path(args.assignment_result).resolve()
    assignment_receipt_path = pathlib.Path(args.assignment_receipt).resolve()
    worker_root = pathlib.Path(args.worker_output_root).resolve()
    receipt_root = pathlib.Path(args.receipt_root).resolve()
    workspace_root = pathlib.Path(args.workspace_root).resolve()
    output = pathlib.Path(args.output).resolve()
    if output.exists():
        raise CollectionVerifyError("collection verification output already exists")
    if not assignment_dir.is_dir() or assignment_dir.is_symlink():
        raise CollectionVerifyError("assignment_result must be a non-symlink directory")
    if not assignment_receipt_path.is_file() or assignment_receipt_path.is_symlink():
        raise CollectionVerifyError("assignment_receipt must be a non-symlink file")
    for path, name in (
        (worker_root, "worker_output_root"),
        (receipt_root, "receipt_root"),
        (workspace_root, "workspace_root"),
    ):
        if not path.is_dir() or path.is_symlink():
            raise CollectionVerifyError(f"{name} must be a non-symlink directory")
    if any(root in output.parents for root in (worker_root, receipt_root, workspace_root)):
        raise CollectionVerifyError("collection output must be outside worker, receipt, and workspace roots")
    assignments, summary, assignment_manifest_sha = load_assignments(assignment_dir)
    assignment_receipt = exact_keys(
        parse_json(checked_bytes(assignment_receipt_path), "assignment verification receipt"),
        ASSIGNMENT_RECEIPT_KEYS,
        "assignment verification receipt",
    )
    assignment_receipt_expected = {
        "status": "VERIFIED_OUTCOME_BLIND_BALANCED_ASSIGNMENT",
        "result_sha256_manifest": sha256_bytes(
            (assignment_dir / "sha256_manifest.json").read_bytes()
        ),
        "rollout_jobs": summary["rollout_jobs"],
        "anchor_count": summary["anchor_count"],
        "task_count": summary["task_count"],
        "siblings_per_anchor": summary["siblings_per_anchor"],
        "replicates_per_sibling": summary["replicates_per_sibling"],
        "continuation_horizon": summary["continuation_horizon"],
        "contains_outcomes": False,
        "independent_reconstruction_exact": True,
    }
    if assignment_receipt != assignment_receipt_expected:
        raise CollectionVerifyError("assignment independent-verification receipt differs")
    expected_ids = [row["rollout_id"] for row in assignments]
    if len(set(expected_ids)) != len(expected_ids):
        raise CollectionVerifyError("duplicate rollout ID in assignment")
    inflight = [path.name for path in worker_root.iterdir() if path.name.startswith(".inflight-")]
    if inflight:
        raise CollectionVerifyError(f"inflight rollout artifacts remain: {sorted(inflight)}")
    actual_worker_entries = {path.name for path in worker_root.iterdir()}
    if actual_worker_entries != set(expected_ids):
        raise CollectionVerifyError("worker output coverage differs from assignment IDs")
    if any(path.is_symlink() or not path.is_dir() for path in worker_root.iterdir()):
        raise CollectionVerifyError("worker outputs must be non-symlink directories")
    expected_receipts = {f"{rollout_id}.verify.json" for rollout_id in expected_ids}
    actual_receipts = {path.name for path in receipt_root.iterdir()}
    if actual_receipts != expected_receipts:
        raise CollectionVerifyError("verification receipt coverage differs from assignment IDs")
    if any(path.is_symlink() or not path.is_file() for path in receipt_root.iterdir()):
        raise CollectionVerifyError("verification receipts must be non-symlink files")
    actual_workspaces = {path.name for path in workspace_root.iterdir()}
    if actual_workspaces != set(expected_ids):
        raise CollectionVerifyError("workspace coverage differs from assignment IDs")
    if any(path.is_symlink() or not path.is_dir() for path in workspace_root.iterdir()):
        raise CollectionVerifyError("workspaces must be non-symlink directories")
    workspace_tokens = set()
    workspace_paths = set()
    per_anchor_sibling = Counter()
    per_block = defaultdict(list)
    task_counts = Counter()
    total_attempts = total_operator_calls = total_retries = total_replacements = 0
    gains = []
    best_values = []
    receipt_hashes = {}
    for assignment in assignments:
        rollout_id = assignment["rollout_id"]
        artifact = worker_root / rollout_id
        if artifact.is_symlink():
            raise CollectionVerifyError("worker artifact directory is symlinked")
        receipt_path = receipt_root / f"{rollout_id}.verify.json"
        receipt = exact_keys(
            parse_json(checked_bytes(receipt_path), "worker verification receipt"),
            VERIFY_RECEIPT_KEYS,
            "worker verification receipt",
        )
        if (
            receipt["status"] != "VERIFIED_SYNTHETIC_BALANCED_CONTINUATION_ROLLOUT"
            or receipt["rollout_id"] != rollout_id
            or receipt["global_order"] != assignment["global_order"]
            or receipt["continuation_horizon"] != assignment["continuation_horizon"]
            or receipt["candidate_execution_attempts"] != 1 + assignment["continuation_horizon"]
            or receipt["operator_calls"] != assignment["continuation_horizon"]
            or receipt["retry_count"] != 0
            or receipt["replacement_count"] != 0
            or receipt["fresh_workspace_verified"] is not True
        ):
            raise CollectionVerifyError(f"verification receipt contract differs: {rollout_id}")
        worker_manifest_sha = sha256_bytes((artifact / "sha256_manifest.json").read_bytes())
        if receipt["worker_sha256_manifest"] != worker_manifest_sha:
            raise CollectionVerifyError("worker manifest hash differs from independent receipt")
        result = parse_json(checked_bytes(artifact / "result.json"), "worker result")
        for key in WORKER_IDENTITY_KEYS:
            if result.get(key) != assignment[key]:
                raise CollectionVerifyError(f"worker/assignment identity differs: {key}")
        if result.get("workspace_token") != receipt["workspace_token"]:
            raise CollectionVerifyError("workspace token differs between worker and verifier")
        raw_workspace_path = result.get("workspace_path")
        if not isinstance(raw_workspace_path, str) or not pathlib.Path(raw_workspace_path).is_absolute():
            raise CollectionVerifyError("worker workspace path must be absolute")
        workspace_path = pathlib.Path(raw_workspace_path).resolve()
        if not workspace_path.is_dir() or workspace_path.is_symlink():
            raise CollectionVerifyError("worker workspace is absent or symlinked")
        if workspace_path.parent != workspace_root or workspace_path.name != rollout_id:
            raise CollectionVerifyError("worker workspace is outside the frozen per-rollout root")
        token = receipt["workspace_token"]
        if not isinstance(token, str) or not token or token in workspace_tokens:
            raise CollectionVerifyError("workspace token is missing or reused")
        if str(workspace_path) in workspace_paths:
            raise CollectionVerifyError("workspace path is reused")
        workspace_tokens.add(token)
        workspace_paths.add(str(workspace_path))
        per_anchor_sibling[(assignment["anchor_id"], assignment["sibling_id"])] += 1
        per_block[assignment["block_id"]].append(assignment)
        task_counts[assignment["task"]] += 1
        total_attempts += receipt["candidate_execution_attempts"]
        total_operator_calls += receipt["operator_calls"]
        total_retries += receipt["retry_count"]
        total_replacements += receipt["replacement_count"]
        best_values.append(finite_number(receipt["best_within_h_utility"], "best utility"))
        gains.append(finite_number(receipt["gain_over_warm_start"], "gain"))
        receipt_hashes[receipt_path.name] = sha256_bytes(receipt_path.read_bytes())
    expected_k = summary["replicates_per_sibling"]
    if set(per_anchor_sibling.values()) != {expected_k}:
        raise CollectionVerifyError("not every sibling has exactly K completed rollouts")
    expected_b = summary["siblings_per_anchor"]
    for block_id, rows in per_block.items():
        if len(rows) != expected_b:
            raise CollectionVerifyError(f"block {block_id} does not contain B siblings")
        if {row["position_within_block"] for row in rows} != set(range(expected_b)):
            raise CollectionVerifyError(f"block {block_id} positions are not exact")
        if len({row["sibling_id"] for row in rows}) != expected_b:
            raise CollectionVerifyError(f"block {block_id} repeats a sibling")
    if total_attempts != summary["planned_total_candidate_executions"]:
        raise CollectionVerifyError("total candidate attempts differ from frozen plan")
    if total_operator_calls != summary["planned_continuation_executions"]:
        raise CollectionVerifyError("total operator calls differ from frozen continuation plan")
    if total_retries or total_replacements:
        raise CollectionVerifyError("collection contains retries or replacement rollouts")
    collection = {
        "status": "VERIFIED_COMPLETE_SYNTHETIC_BALANCED_CONTINUATION_COLLECTION",
        "assignment_manifest_sha256": assignment_manifest_sha,
        "assignment_verification_receipt_sha256": sha256_bytes(
            assignment_receipt_path.read_bytes()
        ),
        "rollout_jobs": len(assignments),
        "task_count": len(task_counts),
        "anchor_count": summary["anchor_count"],
        "siblings_per_anchor": expected_b,
        "replicates_per_sibling": expected_k,
        "continuation_horizon": summary["continuation_horizon"],
        "candidate_execution_attempts": total_attempts,
        "operator_calls": total_operator_calls,
        "retry_count": total_retries,
        "replacement_count": total_replacements,
        "unique_workspace_paths": len(workspace_paths),
        "unique_workspace_tokens": len(workspace_tokens),
        "every_sibling_exactly_k": True,
        "every_block_contains_all_siblings": True,
        "all_workspaces_fresh_and_unique": True,
        "mean_best_within_h_utility": sum(best_values) / len(best_values),
        "mean_gain_over_warm_start": sum(gains) / len(gains),
        "task_rollout_counts": dict(sorted(task_counts.items())),
        "verification_receipt_sha256s": dict(sorted(receipt_hashes.items())),
    }
    atomic_json(output, collection)
    return collection


def parser() -> argparse.ArgumentParser:
    ap = argparse.ArgumentParser()
    ap.add_argument("--assignment-result", required=True)
    ap.add_argument("--assignment-receipt", required=True)
    ap.add_argument("--worker-output-root", required=True)
    ap.add_argument("--receipt-root", required=True)
    ap.add_argument("--workspace-root", required=True)
    ap.add_argument("--output", required=True)
    return ap


def main() -> int:
    try:
        result = verify(parser().parse_args())
    except (CollectionVerifyError, OSError) as exc:
        print(f"BALANCED_CONTINUATION_COLLECTION_REJECTED: {exc}", file=sys.stderr)
        return 2
    print(canonical_json(result).decode("utf-8"))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
