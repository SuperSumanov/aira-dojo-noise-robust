#!/usr/bin/env python3
"""Validate direct generation artifacts and build the extractor's frozen run manifest."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import tempfile
from pathlib import Path


EXPECTED_STEP_LIMIT = 2  # blank root is step 1; one generated candidate is step 2


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()


def atomic_json(path: Path, payload: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp_name = tempfile.mkstemp(prefix=f".{path.name}.", dir=path.parent)
    try:
        with os.fdopen(fd, "w", encoding="utf-8", newline="") as handle:
            json.dump(payload, handle, ensure_ascii=False, sort_keys=True, indent=2)
            handle.write("\n")
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(tmp_name, path)
    finally:
        if os.path.exists(tmp_name):
            os.unlink(tmp_name)


def nested(root: dict, *keys: str):
    value = root
    for key in keys:
        if not isinstance(value, dict) or key not in value:
            raise RuntimeError(f"missing config path: {'.'.join(keys)}")
        value = value[key]
    return value


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--run-root", type=Path, required=True)
    parser.add_argument("--status-dir", type=Path, required=True)
    parser.add_argument("--issue", required=True)
    parser.add_argument("--seed", type=int, required=True)
    parser.add_argument("--tasks", nargs="+", required=True)
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--audit", type=Path, required=True)
    args = parser.parse_args()
    tasks = sorted(set(args.tasks))
    if len(tasks) != 2 or args.seed != 861 or args.issue != "schema_probe_smoke_v1":
        raise RuntimeError("generation manifest request differs from frozen matrix")
    if args.out.exists() or args.audit.exists():
        raise RuntimeError("refusing existing generation manifest outputs")

    status_paths = sorted(args.status_dir.glob("index_*.json"))
    if len(status_paths) != 2:
        raise RuntimeError(f"expected two status records, got {len(status_paths)}")
    statuses = [json.loads(path.read_text(encoding="utf-8")) for path in status_paths]
    status_by_task = {row.get("task"): row for row in statuses}
    status_path_by_task = {row.get("task"): path for row, path in zip(statuses, status_paths)}
    if sorted(status_by_task) != tasks:
        raise RuntimeError("status task set mismatch")
    for task, status in status_by_task.items():
        if (
            status.get("return_code") != 0
            or status.get("seed") != args.seed
            or status.get("issue") != args.issue
            or not isinstance(status.get("command_sha256"), str)
        ):
            raise RuntimeError(f"generation entry failed or malformed: {task}")

    issue_root = args.run_root / f"user_yzyang4_issue_{args.issue}"
    config_paths = sorted(issue_root.glob("*/dojo_config.json"))
    if len(config_paths) != 2:
        raise RuntimeError(f"expected exactly two experiment configs, got {len(config_paths)}")

    entries: dict[str, dict] = {}
    audit_rows: list[dict] = []
    for config_path in config_paths:
        config = json.loads(config_path.read_text(encoding="utf-8"))
        task = str(nested(config, "task", "name"))
        seed = int(nested(config, "metadata", "seed"))
        issue = str(nested(config, "metadata", "git_issue_id"))
        experiment_dir = config_path.parent
        if task not in tasks or task in entries or seed != args.seed or issue != args.issue:
            raise RuntimeError(f"unexpected/duplicate experiment config: {config_path}")
        # The deployment root is fixed; compare resolved config to the canonical public-only path.
        expected_data = Path("/research/d7/spc/yzyang4/mle-bench-data") / task / "prepared" / "public"
        if Path(nested(config, "task", "data_dir")) != expected_data:
            raise RuntimeError(f"non-public task data path: {task}")
        solver = nested(config, "solver")
        if (
            int(solver.get("step_limit", -1)) != EXPECTED_STEP_LIMIT
            or int(solver.get("execution_timeout", -1)) != 600
            or int(solver.get("time_limit_secs", -1)) != 1200
        ):
            raise RuntimeError(f"solver budget mismatch: {task}")
        operators = solver.get("operators", {})
        for name in ("analyze", "debug", "draft", "improve"):
            model_id = nested(operators, name, "llm", "client", "model_id")
            if model_id != "deepseek-v4-flash":
                raise RuntimeError(f"client mismatch {task}/{name}: {model_id}")
        prompt = nested(operators, "draft", "system_message_prompt_template", "template")
        if "CRITICAL ANYTIME ARTIFACT CONTRACT" not in prompt or "candidate_probe.csv" not in prompt:
            raise RuntimeError(f"schema/probe prompt missing from resolved config: {task}")
        if Path(nested(config, "logger", "output_dir")) != experiment_dir:
            raise RuntimeError(f"logger output provenance mismatch: {task}")

        exports = sorted(experiment_dir.glob("*_MCTS_search_data.json"))
        journals = sorted(experiment_dir.glob("checkpoint/journal.jsonl"))
        states = sorted(experiment_dir.glob("checkpoint/state.json"))
        if len(exports) != 1 or len(journals) != 1 or len(states) != 1:
            raise RuntimeError(f"incomplete generation artifacts: {task}")
        export = json.loads(exports[0].read_text(encoding="utf-8"))
        nodes = export.get("nodes") if isinstance(export, dict) else None
        code_nodes = [node for node in nodes or [] if isinstance(node, dict) and str(node.get("code", "")).strip()]
        journal_lines = sum(1 for line in journals[0].read_text(encoding="utf-8").splitlines() if line.strip())
        state = json.loads(states[0].read_text(encoding="utf-8"))
        if len(code_nodes) != 1 or journal_lines != 1 or int(state.get("current_step", -1)) != 1:
            raise RuntimeError(
                f"one-step topology mismatch {task}: code_nodes={len(code_nodes)} journal={journal_lines} "
                f"state={state.get('current_step')}"
            )
        task_id = str(config.get("id", ""))
        if not task_id or experiment_dir.name != task_id:
            raise RuntimeError(f"experiment identity mismatch: {task}")
        status = status_by_task[task]
        entries[task_id] = {
            "task_name": task,
            "status": "completed",
            "exit_code": 0,
            "experiment_dir": str(experiment_dir),
            "attempts": [
                {
                    "attempt": 1,
                    "status": "completed",
                    "exit_code": 0,
                    "slurm_state": "COMPLETED",
                    "command_sha256": status["command_sha256"],
                }
            ],
        }
        audit_rows.append(
            {
                "task": task,
                "seed": seed,
                "task_id": task_id,
                "experiment_dir": str(experiment_dir),
                "dojo_config_sha256": sha256_file(config_path),
                "search_export_sha256": sha256_file(exports[0]),
                "journal_sha256": sha256_file(journals[0]),
                "state_sha256": sha256_file(states[0]),
                "status_sha256": sha256_file(status_path_by_task[task]),
                "code_nodes": len(code_nodes),
                "journal_lines": journal_lines,
                "current_step": state.get("current_step"),
            }
        )

    if sorted(row["task_name"] for row in entries.values()) != tasks:
        raise RuntimeError("experiment task set mismatch")
    manifest = {
        "version": 1,
        "launcher_type": "direct_srun_frozen",
        "issue": args.issue,
        "seed": args.seed,
        "tasks": entries,
    }
    atomic_json(args.out, manifest)
    audit = {
        "schema_version": 1,
        "issue": args.issue,
        "seed": args.seed,
        "tasks": tasks,
        "manifest": str(args.out),
        "manifest_sha256": sha256_file(args.out),
        "rows": sorted(audit_rows, key=lambda row: row["task"]),
    }
    atomic_json(args.audit, audit)
    print(
        "SCHEMA_PROBE_GENERATION_MANIFEST_PASS "
        f"tasks={len(entries)} manifest_sha256={audit['manifest_sha256']}"
    )


if __name__ == "__main__":
    main()
