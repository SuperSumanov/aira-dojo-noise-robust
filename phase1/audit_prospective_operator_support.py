#!/usr/bin/env python3
"""Outcome-blind support audit for future randomized operator logging."""
from __future__ import annotations

import argparse
import collections
import hashlib
import json
import os
import re
import sys
from pathlib import Path
from typing import Any


PROTOCOL = "prospective-operator-support-v1"
SHA256 = re.compile(r"[0-9a-f]{64}")
CREDENTIAL = re.compile(
    rb"(?:sk-[A-Za-z0-9._-]{16,}|api[_-]?key\s*[:=]\s*['\"]?[A-Za-z0-9._-]{16,})",
    re.I,
)
TARGET_OPS = ("Debug", "Improve")


class AuditError(RuntimeError):
    pass


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()


def load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def load_jsonl(path: Path) -> list[dict[str, Any]]:
    blob = path.read_bytes()
    if CREDENTIAL.search(blob):
        raise AuditError(f"credential-shaped content in {path.name}")
    rows: list[dict[str, Any]] = []
    for line_number, line in enumerate(blob.decode("utf-8").splitlines(), 1):
        if not line:
            raise AuditError(f"blank line in {path.name}:{line_number}")
        row = json.loads(line)
        if not isinstance(row, dict):
            raise AuditError(f"non-object row in {path.name}:{line_number}")
        rows.append(row)
    return rows


def intake_path(state_root: Path, transaction: dict[str, Any]) -> Path:
    drop_id = transaction.get("drop_id")
    if not isinstance(drop_id, str) or not drop_id:
        raise AuditError("transaction drop_id missing")
    expected = (state_root / "intakes" / drop_id).resolve()
    declared = Path(str(transaction.get("intake_dir", ""))).resolve()
    if declared != expected or not expected.is_dir():
        raise AuditError(f"intake path mismatch for {drop_id}")
    return expected


def collect(args: argparse.Namespace) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    transactions_path = Path(args.transactions).resolve()
    if sha256_file(transactions_path) != args.expect_transactions_sha256:
        raise AuditError("transactions SHA mismatch")
    state_root = Path(args.state_root).resolve()
    transactions = load_jsonl(transactions_path)
    if len(transactions) != args.expect_transactions:
        raise AuditError("transaction count mismatch")

    endpoints: dict[str, dict[str, str]] = {}
    parents: dict[tuple[str, str, str], list[dict[str, str]]] = collections.defaultdict(list)
    input_manifests: list[dict[str, str]] = []
    run_tasks: dict[str, str] = {}
    for transaction in transactions:
        intake = intake_path(state_root, transaction)
        summary_path = intake / "summary.json"
        if sha256_file(summary_path) != transaction.get("intake_summary_sha256"):
            raise AuditError("intake summary SHA mismatch")
        summary = load_json(summary_path)
        if summary.get("status") != "PROSPECTIVE_DROP_INTAKE_COMPLETE":
            raise AuditError("intake is not complete")
        blindness = summary.get("blindness", {})
        security = summary.get("security", {})
        if (
            blindness.get("labels_used_for_endpoint_selection") is not False
            or blindness.get("labels_used_for_run_selection") is not False
            or blindness.get("metrics_computed") != []
            or security.get("env_members_read") is not False
            or security.get("credential_shaped_journals") != 0
        ):
            raise AuditError("intake blindness/security contract mismatch")
        manifest_path = intake / "eligible_blind_manifest.jsonl"
        expected_manifest_sha = summary.get("outputs", {}).get("eligible_blind_manifest_sha256")
        if not isinstance(expected_manifest_sha, str) or sha256_file(manifest_path) != expected_manifest_sha:
            raise AuditError("eligible manifest SHA mismatch")
        input_manifests.append({"drop_id": transaction["drop_id"], "sha256": expected_manifest_sha})
        for row in load_jsonl(manifest_path):
            card_id = row.get("card_id")
            task = row.get("task")
            run_id = row.get("run_id")
            lineage = row.get("lineage")
            if not all(isinstance(value, str) and value for value in (card_id, task, run_id)) or not isinstance(lineage, dict):
                raise AuditError("invalid eligible manifest identity")
            op = lineage.get("op")
            parent = lineage.get("parent")
            if not isinstance(op, str) or not op:
                raise AuditError("lineage op missing")
            record = {"task": task, "run_id": run_id, "op": op}
            if card_id in endpoints:
                raise AuditError(f"duplicate endpoint {card_id}")
            endpoints[card_id] = record
            previous_task = run_tasks.setdefault(run_id, task)
            if previous_task != task:
                raise AuditError("run spans tasks")
            if parent is not None:
                if not isinstance(parent, str) or not parent:
                    raise AuditError("invalid parent identity")
                parents[(task, run_id, parent)].append({"card_id": card_id, "op": op})

    parent_rows: list[dict[str, Any]] = []
    for (task, run_id, parent), children in sorted(parents.items()):
        ops = sorted({child["op"] for child in children})
        parent_key = hashlib.sha256(f"{task}\0{run_id}\0{parent}".encode()).hexdigest()
        parent_rows.append(
            {
                "parent_key_sha256": parent_key,
                "task": task,
                "run_id": run_id,
                "children": len(children),
                "ops": ops,
                "mixed": len(ops) >= 2,
                "exact_two": len(children) == 2,
            }
        )
    return parent_rows, {
        "transactions": len(transactions),
        "transaction_sha256": args.expect_transactions_sha256,
        "input_manifests": input_manifests,
        "endpoints": endpoints,
        "runs": run_tasks,
    }


def summarize(parent_rows: list[dict[str, Any]], metadata: dict[str, Any], source_commit: str) -> dict[str, Any]:
    endpoints = metadata["endpoints"]
    endpoint_ops = collections.Counter(row["op"] for row in endpoints.values())
    op_tasks: dict[str, set[str]] = collections.defaultdict(set)
    op_runs: dict[str, set[str]] = collections.defaultdict(set)
    for row in endpoints.values():
        op_tasks[row["op"]].add(row["task"])
        op_runs[row["op"]].add(row["run_id"])
    mixed = [row for row in parent_rows if row["mixed"]]
    mixed_tasks = collections.Counter(row["task"] for row in mixed)
    exact_two_mixed = [row for row in mixed if row["exact_two"]]
    dominant_mixed_share = max(mixed_tasks.values(), default=0) / len(mixed) if mixed else None
    gates = {
        "transactions_eq_expected": metadata["transactions"] == len(metadata["input_manifests"]),
        "eligible_runs_ge_150": len(metadata["runs"]) >= 150,
        "eligible_tasks_ge_15": len(set(metadata["runs"].values())) >= 15,
        "eligible_endpoints_ge_3000": len(endpoints) >= 3000,
        "debug_and_improve_each_ge_1000_endpoints": all(endpoint_ops[op] >= 1000 for op in TARGET_OPS),
        "debug_and_improve_each_ge_15_tasks": all(len(op_tasks[op]) >= 15 for op in TARGET_OPS),
        "mixed_operator_parents_ge_100": len(mixed) >= 100,
        "mixed_operator_tasks_ge_10": len(mixed_tasks) >= 10,
        "exact_two_mixed_operator_parents_ge_60": len(exact_two_mixed) >= 60,
        "dominant_mixed_operator_task_share_le_0_25": dominant_mixed_share is not None and dominant_mixed_share <= 0.25,
    }
    passed = all(gates.values())
    return {
        "protocol": PROTOCOL,
        "status": "OPERATOR_RANDOMIZATION_SUPPORT_FEASIBLE" if passed else "INSUFFICIENT_OPERATOR_RANDOMIZATION_SUPPORT",
        "source_commit": source_commit,
        "scope": {
            "outcomes_read": False,
            "label_vault_opened": False,
            "numeric_grade_read": False,
            "raw_code_emitted": False,
            "gpu": 0,
            "api_calls": 0,
            "production_activation_authorized": False,
            "causal_claim_allowed": False,
        },
        "inventory": {
            "transactions": metadata["transactions"],
            "eligible_endpoints": len(endpoints),
            "eligible_runs": len(metadata["runs"]),
            "eligible_tasks": len(set(metadata["runs"].values())),
            "nonroot_parents": len(parent_rows),
            "mixed_operator_parents": len(mixed),
            "mixed_operator_tasks": len(mixed_tasks),
            "exact_two_mixed_operator_parents": len(exact_two_mixed),
            "dominant_mixed_operator_task_share": dominant_mixed_share,
        },
        "endpoint_op_counts": dict(sorted(endpoint_ops.items())),
        "op_task_support": {op: len(op_tasks[op]) for op in sorted(op_tasks)},
        "op_run_support": {op: len(op_runs[op]) for op in sorted(op_runs)},
        "mixed_parent_per_task": dict(sorted(mixed_tasks.items())),
        "criteria": gates,
        "inputs": {
            "transactions_sha256": metadata["transaction_sha256"],
            "eligible_manifest_shas": metadata["input_manifests"],
        },
    }


def write_json(path: Path, value: Any) -> None:
    path.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n", encoding="utf-8", newline="\n")


def run(args: argparse.Namespace) -> int:
    if not re.fullmatch(r"[0-9a-f]{40}", args.source_commit):
        raise AuditError("source commit must be full lowercase SHA-1")
    if not SHA256.fullmatch(args.expect_transactions_sha256):
        raise AuditError("transactions digest invalid")
    parent_rows, metadata = collect(args)
    summary = summarize(parent_rows, metadata, args.source_commit)
    output = Path(args.output).resolve()
    staging = output.with_name(output.name + f".tmp-{os.getpid()}")
    if output.exists() or staging.exists():
        raise AuditError("output already exists")
    staging.mkdir(parents=True)
    write_json(staging / "summary.json", summary)
    with (staging / "parent_support.jsonl").open("w", encoding="utf-8", newline="\n") as handle:
        for row in parent_rows:
            handle.write(json.dumps(row, sort_keys=True) + "\n")
    manifest = {name: sha256_file(staging / name) for name in ("summary.json", "parent_support.jsonl")}
    write_json(staging / "sha256_manifest.json", manifest)
    staging.replace(output)
    print(json.dumps(summary, sort_keys=True, separators=(",", ":")))
    return 0


def parser() -> argparse.ArgumentParser:
    value = argparse.ArgumentParser()
    value.add_argument("--transactions", required=True)
    value.add_argument("--expect-transactions-sha256", required=True)
    value.add_argument("--expect-transactions", type=int, required=True)
    value.add_argument("--state-root", required=True)
    value.add_argument("--source-commit", required=True)
    value.add_argument("--output", required=True)
    return value


def main() -> int:
    try:
        return run(parser().parse_args())
    except (AuditError, OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        print(f"PROSPECTIVE_OPERATOR_SUPPORT_ERROR: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
