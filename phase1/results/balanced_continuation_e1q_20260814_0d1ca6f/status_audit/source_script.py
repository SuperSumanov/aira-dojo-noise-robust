#!/usr/bin/env python3
"""Post-hoc reporting repair for E1-Q execution-status fields.

The frozen compact collection omitted execution status and artifact-presence
fields required by the preregistration.  This script does not change any
scientific value.  It reads only already-verified execution receipts and the
compact collection, rejects credential-shaped receipt bytes before JSON parse,
and exports a narrow status-only table with source hashes.
"""

from __future__ import annotations

import argparse
import collections
import hashlib
import json
import math
import os
import pathlib
import re
from typing import Any


CREDENTIAL = re.compile(
    rb"sk-[A-Za-z0-9._-]{16,}|hf_[A-Za-z0-9]{20,}|"
    rb"gh[pousr]_[A-Za-z0-9]{20,}|AKIA[0-9A-Z]{16}|"
    rb"AIza[0-9A-Za-z_-]{30,}|Bearer\s+[A-Za-z0-9._-]{20,}|"
    rb"-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----"
)
ALLOWED_STATUS = {"ok", "timeout", "execution_error", "invalid_format"}


class AuditError(RuntimeError):
    pass


def sha256_bytes(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def sha256(path: pathlib.Path) -> str:
    return sha256_bytes(path.read_bytes())


def checked_json(path: pathlib.Path) -> tuple[dict[str, Any], str]:
    if path.is_symlink() or not path.is_file():
        raise AuditError(f"not a regular file: {path}")
    raw = path.read_bytes()
    if CREDENTIAL.search(raw):
        raise AuditError(f"credential-shaped bytes before JSON parse: {path}")
    value = json.loads(raw.decode("utf-8"))
    if not isinstance(value, dict):
        raise AuditError(f"non-object JSON: {path}")
    return value, sha256_bytes(raw)


def load_rollouts(path: pathlib.Path) -> dict[str, dict[str, Any]]:
    if path.is_symlink() or not path.is_file():
        raise AuditError("collection rollouts are absent or symlinked")
    raw = path.read_bytes()
    if CREDENTIAL.search(raw):
        raise AuditError("credential-shaped bytes in compact rollouts")
    rows: dict[str, dict[str, Any]] = {}
    for line_number, line in enumerate(raw.decode("utf-8").splitlines(), 1):
        if not line:
            continue
        value = json.loads(line)
        rollout_id = str(value.get("rollout_id") or "")
        if not rollout_id or rollout_id in rows:
            raise AuditError(f"duplicate/empty rollout at line {line_number}")
        rows[rollout_id] = value
    if len(rows) != 8:
        raise AuditError(f"expected eight compact rollouts, found {len(rows)}")
    return rows


def finite_nonnegative(value: Any, label: str) -> float:
    if isinstance(value, bool):
        raise AuditError(f"boolean {label}")
    try:
        number = float(value)
    except (TypeError, ValueError) as exc:
        raise AuditError(f"non-numeric {label}") from exc
    if not math.isfinite(number) or number < 0:
        raise AuditError(f"invalid {label}")
    return number


def validate_execution(value: dict[str, Any], path: pathlib.Path) -> dict[str, Any]:
    required = {
        "rollout_id", "task", "execution_ordinal", "execution_status",
        "process_started", "candidate_execution_attempted", "exit_code",
        "timed_out", "wall_time_seconds", "artifact_sha256", "retry_count",
        "public_data_read_only", "private_paths_mounted", "code_sha256",
    }
    if not required <= set(value):
        raise AuditError(f"execution receipt missing fields: {path}")
    status = str(value["execution_status"])
    if status not in ALLOWED_STATUS:
        raise AuditError(f"unknown execution status: {status}")
    process_started = value["process_started"]
    timed_out = value["timed_out"]
    attempted = value["candidate_execution_attempted"]
    if not all(isinstance(item, bool) for item in (process_started, timed_out, attempted)):
        raise AuditError("execution booleans differ")
    if not attempted or value["retry_count"] != 0:
        raise AuditError("attempt/retry contract differs")
    if value["public_data_read_only"] is not True or value["private_paths_mounted"] is not False:
        raise AuditError("execution isolation contract differs")
    exit_code = value["exit_code"]
    artifact = value["artifact_sha256"]
    if artifact is not None and (not isinstance(artifact, str) or len(artifact) != 64):
        raise AuditError("artifact SHA differs")
    if not isinstance(value["code_sha256"], str) or len(value["code_sha256"]) != 64:
        raise AuditError("code SHA differs")
    if status == "ok" and (not process_started or timed_out or exit_code != 0):
        raise AuditError("ok execution semantics differ")
    if status == "timeout" and (not process_started or not timed_out):
        raise AuditError("timeout execution semantics differ")
    if status == "execution_error" and (
        not process_started or timed_out or not isinstance(exit_code, int) or exit_code == 0
    ):
        raise AuditError("execution-error semantics differ")
    if status == "invalid_format" and (process_started or timed_out or exit_code is not None or artifact is not None):
        raise AuditError("invalid-format semantics differ")
    ordinal = int(value["execution_ordinal"])
    if ordinal not in (0, 1):
        raise AuditError("execution ordinal differs")
    return {
        "rollout_id": str(value["rollout_id"]),
        "task": str(value["task"]),
        "execution_ordinal": ordinal,
        "stage": "warm" if ordinal == 0 else "continuation",
        "execution_status": status,
        "process_started": process_started,
        "timed_out": timed_out,
        "exit_code": exit_code,
        "artifact_present": artifact is not None,
        "wall_time_seconds": finite_nonnegative(value["wall_time_seconds"], "wall time"),
    }


def audit(worker_root: pathlib.Path, collection: pathlib.Path) -> dict[str, Any]:
    rollouts_path = collection / "rollouts.jsonl"
    summary_path = collection / "summary.json"
    compact = load_rollouts(rollouts_path)
    summary, summary_sha = checked_json(summary_path)
    if summary.get("status") != "VERIFIED_COMPLETE_REAL_E1_COLLECTION_DESCRIPTIVE_ONLY":
        raise AuditError("compact collection status differs")
    execution_files = sorted(worker_root.rglob("execution.json"))
    if len(execution_files) != 16:
        raise AuditError(f"expected 16 execution receipts, found {len(execution_files)}")
    source_hashes: dict[tuple[str, int], str] = {}
    executions: dict[tuple[str, int], dict[str, Any]] = {}
    for path in execution_files:
        raw, source_sha = checked_json(path)
        row = validate_execution(raw, path)
        key = (row["rollout_id"], row["execution_ordinal"])
        if key in executions:
            raise AuditError(f"duplicate execution identity: {key}")
        executions[key] = row
        source_hashes[key] = source_sha
    expected = {(rollout_id, ordinal) for rollout_id in compact for ordinal in (0, 1)}
    if set(executions) != expected:
        raise AuditError("execution identities differ from compact collection")

    rows: list[dict[str, Any]] = []
    for rollout in sorted(compact.values(), key=lambda item: item["global_order"]):
        rollout_id = rollout["rollout_id"]
        for ordinal in (0, 1):
            execution = executions[(rollout_id, ordinal)]
            if execution["task"] != rollout["task"]:
                raise AuditError("execution task differs from compact rollout")
            dsearch = rollout[
                "warm_dsearch_utility_raw" if ordinal == 0 else "continuation_dsearch_utility_raw"
            ]
            dval = rollout[
                "warm_dval_utility_raw" if ordinal == 0 else "continuation_dval_utility_raw"
            ]
            rows.append(
                {
                    "global_order": rollout["global_order"],
                    "rollout_id": rollout_id,
                    "task": rollout["task"],
                    "sibling_id": rollout["sibling_id"],
                    "block_replicate": rollout["block_replicate"],
                    **execution,
                    "artifact_scored_on_dsearch": dsearch is not None,
                    "artifact_scored_on_dval": dval is not None,
                    "source_execution_receipt_sha256": source_hashes[(rollout_id, ordinal)],
                }
            )

    by_stage: dict[str, Any] = {}
    for stage in ("warm", "continuation"):
        selected = [row for row in rows if row["stage"] == stage]
        by_stage[stage] = {
            "executions": len(selected),
            "status_counts": dict(sorted(collections.Counter(row["execution_status"] for row in selected).items())),
            "artifacts_present": sum(row["artifact_present"] for row in selected),
            "artifacts_scored_on_dsearch": sum(row["artifact_scored_on_dsearch"] for row in selected),
            "artifacts_scored_on_dval": sum(row["artifact_scored_on_dval"] for row in selected),
            "timed_out": sum(row["timed_out"] for row in selected),
        }
    return {
        "protocol": "balanced_continuation_e1q_status_reporting_repair_v1",
        "status": "VERIFIED_POSTHOC_E1Q_STATUS_REPORTING_REPAIR",
        "changes_scientific_collection": False,
        "used_for_e1_stopping_or_selection": False,
        "scope": {
            "reads_execution_receipts": True,
            "exports_terminal_output": False,
            "exports_code": False,
            "reads_operator_raw_response": False,
            "reads_credentials": False,
        },
        "source": {
            "collection_summary_sha256": summary_sha,
            "collection_rollouts_sha256": sha256(rollouts_path),
            "execution_receipts": len(execution_files),
        },
        "summary": {
            "rows": len(rows),
            "rollouts": len(compact),
            "by_stage": by_stage,
        },
        "rows": rows,
    }


def atomic_json(path: pathlib.Path, value: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=False)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(
        json.dumps(value, indent=2, sort_keys=True, ensure_ascii=False, allow_nan=False) + "\n",
        encoding="utf-8",
        newline="\n",
    )
    os.replace(temporary, path)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--worker-root", required=True, type=pathlib.Path)
    parser.add_argument("--collection", required=True, type=pathlib.Path)
    parser.add_argument("--output", required=True, type=pathlib.Path)
    args = parser.parse_args()
    result = audit(args.worker_root.resolve(), args.collection.resolve())
    atomic_json(args.output.resolve(), result)
    print(json.dumps(result["summary"], sort_keys=True, separators=(",", ":")))
    print(result["status"])


if __name__ == "__main__":
    main()
