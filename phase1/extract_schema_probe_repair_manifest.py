#!/usr/bin/env python3
"""Freeze the exact V2 draft-or-debug leaf for independent continuous replay."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import tempfile
from pathlib import Path

from phase1.build_schema_probe_generation_manifest import atomic_json, sha256_file
from phase1.build_schema_probe_repair_manifest import (
    EXPECTED_ISSUE,
    EXPECTED_SEED,
    EXPECTED_TASKS,
    validate_topology,
)
from phase1.extract_schema_probe_manifest import parse_seed, static_contract


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--run-root", type=Path, required=True)
    parser.add_argument("--run-manifest", type=Path, required=True)
    parser.add_argument("--issue", required=True)
    parser.add_argument("--tasks", nargs="+", required=True)
    parser.add_argument("--seed", type=int, required=True)
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--audit", type=Path, required=True)
    args = parser.parse_args()
    if (
        set(args.tasks) != EXPECTED_TASKS
        or len(set(args.tasks)) != len(args.tasks)
        or args.seed != EXPECTED_SEED
        or args.issue != EXPECTED_ISSUE
    ):
        raise RuntimeError("extraction request differs from preregistered V2 matrix")
    if args.out.exists() or args.audit.exists():
        raise RuntimeError("refusing to overwrite V2 extraction outputs")

    manifest = json.loads(args.run_manifest.read_text(encoding="utf-8"))
    if (
        manifest.get("version") != 2
        or manifest.get("issue") != args.issue
        or manifest.get("seed") != args.seed
    ):
        raise RuntimeError("run manifest identity mismatch")
    task_entries = manifest.get("tasks")
    if not isinstance(task_entries, dict) or len(task_entries) != 2:
        raise RuntimeError("run manifest task count mismatch")

    issue_root = (args.run_root / f"user_yzyang4_issue_{args.issue}").resolve()
    rows: list[dict] = []
    audit_rows: list[dict] = []
    seen_tasks: set[str] = set()
    for task_id, meta in sorted(task_entries.items()):
        if not isinstance(meta, dict):
            raise RuntimeError(f"malformed task metadata: {task_id}")
        task = str(meta.get("task_name", ""))
        if task not in EXPECTED_TASKS or task in seen_tasks or parse_seed(task_id) != args.seed:
            raise RuntimeError(f"unexpected task identity: {task_id}")
        if str(meta.get("status", "")).lower() != "completed" or int(meta.get("exit_code", -1)) != 0:
            raise RuntimeError(f"incomplete generation: {task_id}")
        seen_tasks.add(task)
        experiment_dir = Path(meta["experiment_dir"]).resolve()
        if not experiment_dir.is_relative_to(issue_root):
            raise RuntimeError(f"experiment path escapes frozen issue root: {task}")
        exports = sorted(experiment_dir.glob("*_MCTS_search_data.json"))
        journals = sorted(experiment_dir.glob("checkpoint/journal.jsonl"))
        states = sorted(experiment_dir.glob("checkpoint/state.json"))
        if len(exports) != 1 or len(journals) != 1 or len(states) != 1:
            raise RuntimeError(f"incomplete generation artifacts: {task}")
        export = json.loads(exports[0].read_text(encoding="utf-8"))
        state = json.loads(states[0].read_text(encoding="utf-8"))
        journal_lines = sum(bool(line.strip()) for line in journals[0].read_text(encoding="utf-8").splitlines())
        mode, code_nodes, selected = validate_topology(
            export.get("nodes") if isinstance(export, dict) else None,
            journal_lines=journal_lines,
            current_step=int(state.get("current_step", -1)),
        )
        code = str(selected["code"])
        checks = static_contract(code)
        code_sha = hashlib.sha256(code.encode("utf-8")).hexdigest()
        audit_rows.append({
            "task": task,
            "seed": args.seed,
            "task_id": task_id,
            "experiment_dir": str(experiment_dir),
            "source_export": str(exports[0]),
            "source_export_sha256": sha256_file(exports[0]),
            "topology_mode": mode,
            "code_nodes": len(code_nodes),
            "selected_node_id": str(selected.get("id", "")),
            "selected_node_step": selected.get("step"),
            "selected_node_exit_code": selected.get("exit_code"),
            "selected_node_is_buggy": selected.get("is_buggy"),
            "code_sha256": code_sha,
            "code_bytes": len(code.encode("utf-8")),
            "static_contract": checks,
        })
        if checks.get("required_pass") is not True:
            continue
        rows.append({
            "schema_version": 2,
            "card_id": f"schema_probe_v2|{task}|seed={args.seed}|node={selected.get('id', '')}",
            "competition": task,
            "seed": args.seed,
            "code": code,
            "code_sha256": code_sha,
            "generation_topology_mode": mode,
            "generation_node_is_buggy": selected.get("is_buggy"),
            "source_task_id": task_id,
            "source_export": str(exports[0]),
            "source_export_sha256": sha256_file(exports[0]),
            "source_run_manifest": str(args.run_manifest),
            "source_run_manifest_sha256": sha256_file(args.run_manifest),
        })

    audit_payload = {
        "schema_version": 2,
        "issue": args.issue,
        "seed": args.seed,
        "expected_tasks": sorted(EXPECTED_TASKS),
        "run_manifest": str(args.run_manifest),
        "run_manifest_sha256": sha256_file(args.run_manifest),
        "generated_rows": len(audit_rows),
        "static_gate_pass_rows": len(rows),
        "rows": sorted(audit_rows, key=lambda row: row["task"]),
    }
    atomic_json(args.audit, audit_payload)
    if seen_tasks != EXPECTED_TASKS or len(rows) != 2:
        raise RuntimeError(f"V2 static contract gate failed: seen={sorted(seen_tasks)} pass={len(rows)}/2")

    args.out.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp_name = tempfile.mkstemp(prefix=f".{args.out.name}.", dir=args.out.parent)
    try:
        with os.fdopen(fd, "w", encoding="utf-8", newline="") as handle:
            for row in sorted(rows, key=lambda item: item["competition"]):
                handle.write(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n")
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(tmp_name, args.out)
    finally:
        if os.path.exists(tmp_name):
            os.unlink(tmp_name)
    audit_payload["replay_manifest"] = str(args.out)
    audit_payload["replay_manifest_sha256"] = sha256_file(args.out)
    atomic_json(args.audit, audit_payload)
    print(f"SCHEMA_PROBE_REPAIR_EXTRACTION_PASS tasks=2 manifest_sha256={audit_payload['replay_manifest_sha256']}")


if __name__ == "__main__":
    main()
