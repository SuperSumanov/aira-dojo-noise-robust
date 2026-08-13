#!/usr/bin/env python3
"""Validate the exact V2 conditional-debug topology and freeze a run manifest."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from phase1.build_schema_probe_generation_manifest import atomic_json, nested, sha256_file


EXPECTED_TASKS = {
    "spaceship-titanic",
    "tweet-sentiment-extraction",
}
EXPECTED_SEED = 862
EXPECTED_ISSUE = "schema_probe_repair_v2"
EXPECTED_STEP_LIMIT = 3


def _operator_set(node: dict) -> set[str]:
    value = node.get("operators_used")
    if not isinstance(value, list) or not all(isinstance(item, str) for item in value):
        raise RuntimeError("node operators_used is malformed")
    return set(value)


def validate_topology(
    nodes: object,
    *,
    journal_lines: int,
    current_step: int,
) -> tuple[str, list[dict], dict]:
    """Return (mode, code_nodes, selected_node), rejecting every extra branch."""
    if not isinstance(nodes, list) or current_step not in (2, 3):
        raise RuntimeError(f"invalid V2 node/state count: current_step={current_step}")
    if journal_lines != current_step or len(nodes) != current_step:
        raise RuntimeError(
            f"journal/export/state mismatch: nodes={len(nodes)} journal={journal_lines} state={current_step}"
        )
    if any(not isinstance(node, dict) for node in nodes):
        raise RuntimeError("non-dict node in search export")
    typed_nodes: list[dict] = list(nodes)
    if [node.get("step") for node in typed_nodes] != list(range(current_step)):
        raise RuntimeError("node steps are not the exact contiguous root-first sequence")

    root = typed_nodes[0]
    if str(root.get("code", "")).strip() or root.get("parents") != [] or root.get("children") != [1]:
        raise RuntimeError("malformed root topology")
    if _operator_set(root):
        raise RuntimeError("root unexpectedly records an operator")

    draft = typed_nodes[1]
    if not str(draft.get("code", "")).strip() or draft.get("parents") != [0]:
        raise RuntimeError("malformed draft topology")
    draft_ops = _operator_set(draft)
    if "draft" not in draft_ops or "debug" in draft_ops or "improve" in draft_ops:
        raise RuntimeError("step 1 is not a pure draft")

    if current_step == 2:
        if draft.get("is_buggy") is not False or draft.get("children") != []:
            raise RuntimeError("two-node run did not stop on a valid draft")
        return "draft_valid", [draft], draft

    debug = typed_nodes[2]
    if draft.get("is_buggy") is not True or draft.get("children") != [2]:
        raise RuntimeError("three-node run did not debug a failed draft")
    if (
        not str(debug.get("code", "")).strip()
        or debug.get("parents") != [1]
        or debug.get("children") != []
    ):
        raise RuntimeError("malformed debug topology")
    debug_ops = _operator_set(debug)
    if "debug" not in debug_ops or "improve" in debug_ops or "draft" in debug_ops:
        raise RuntimeError("step 2 is not a single debug")
    mode = "debug_valid" if debug.get("is_buggy") is False else "debug_exhausted"
    return mode, [draft, debug], debug


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
    if (
        set(tasks) != EXPECTED_TASKS
        or len(tasks) != len(args.tasks)
        or args.seed != EXPECTED_SEED
        or args.issue != EXPECTED_ISSUE
    ):
        raise RuntimeError("generation manifest request differs from preregistered V2 matrix")
    if args.out.exists() or args.audit.exists():
        raise RuntimeError("refusing existing generation manifest outputs")

    status_paths = sorted(args.status_dir.glob("index_*.json"))
    if len(status_paths) != 2:
        raise RuntimeError(f"expected two status records, got {len(status_paths)}")
    statuses = [json.loads(path.read_text(encoding="utf-8")) for path in status_paths]
    status_by_task = {row.get("task"): row for row in statuses}
    status_path_by_task = {row.get("task"): path for row, path in zip(statuses, status_paths)}
    if set(status_by_task) != EXPECTED_TASKS:
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
        if task not in EXPECTED_TASKS or task in {row["task"] for row in audit_rows}:
            raise RuntimeError(f"unexpected or duplicate task: {task}")
        if seed != args.seed or issue != args.issue:
            raise RuntimeError(f"task identity mismatch: {task}")
        expected_data = Path("/research/d7/spc/yzyang4/mle-bench-data") / task / "prepared" / "public"
        if Path(nested(config, "task", "data_dir")) != expected_data:
            raise RuntimeError(f"non-public task data path: {task}")

        solver = nested(config, "solver")
        expected_solver = {
            "step_limit": EXPECTED_STEP_LIMIT,
            "num_children": 1,
            "max_debug_depth": 1,
            "execution_timeout": 600,
            "time_limit_secs": 1200,
        }
        if any(int(solver.get(key, -1)) != value for key, value in expected_solver.items()):
            raise RuntimeError(f"solver budget mismatch: {task}")
        if solver.get("stop_after_first_valid") is not True:
            raise RuntimeError(f"first-valid stopping is not enabled: {task}")
        operators = solver.get("operators", {})
        for name in ("analyze", "debug", "draft", "improve"):
            if nested(operators, name, "llm", "client", "model_id") != "deepseek-v4-flash":
                raise RuntimeError(f"client mismatch: {task}/{name}")
        prompt = nested(operators, "draft", "system_message_prompt_template", "template")
        if "CRITICAL ANYTIME ARTIFACT CONTRACT" not in prompt or "candidate_probe.csv" not in prompt:
            raise RuntimeError(f"schema/probe prompt missing: {task}")
        if Path(nested(config, "logger", "output_dir")) != experiment_dir:
            raise RuntimeError(f"logger output provenance mismatch: {task}")

        exports = sorted(experiment_dir.glob("*_MCTS_search_data.json"))
        journals = sorted(experiment_dir.glob("checkpoint/journal.jsonl"))
        states = sorted(experiment_dir.glob("checkpoint/state.json"))
        if len(exports) != 1 or len(journals) != 1 or len(states) != 1:
            raise RuntimeError(f"incomplete generation artifacts: {task}")
        export = json.loads(exports[0].read_text(encoding="utf-8"))
        journal_lines = sum(bool(line.strip()) for line in journals[0].read_text(encoding="utf-8").splitlines())
        state = json.loads(states[0].read_text(encoding="utf-8"))
        mode, code_nodes, selected = validate_topology(
            export.get("nodes") if isinstance(export, dict) else None,
            journal_lines=journal_lines,
            current_step=int(state.get("current_step", -1)),
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
            "attempts": [{
                "attempt": 1,
                "status": "completed",
                "exit_code": 0,
                "slurm_state": "COMPLETED",
                "command_sha256": status["command_sha256"],
            }],
        }
        audit_rows.append({
            "task": task,
            "seed": seed,
            "task_id": task_id,
            "experiment_dir": str(experiment_dir),
            "dojo_config_sha256": sha256_file(config_path),
            "search_export_sha256": sha256_file(exports[0]),
            "journal_sha256": sha256_file(journals[0]),
            "state_sha256": sha256_file(states[0]),
            "status_sha256": sha256_file(status_path_by_task[task]),
            "topology_mode": mode,
            "code_nodes": len(code_nodes),
            "selected_node_step": selected.get("step"),
            "selected_node_is_buggy": selected.get("is_buggy"),
            "journal_lines": journal_lines,
            "current_step": state.get("current_step"),
        })

    manifest = {
        "version": 2,
        "launcher_type": "direct_srun_preregistered_conditional_debug",
        "issue": args.issue,
        "seed": args.seed,
        "tasks": entries,
    }
    atomic_json(args.out, manifest)
    audit = {
        "schema_version": 2,
        "issue": args.issue,
        "seed": args.seed,
        "tasks": tasks,
        "manifest": str(args.out),
        "manifest_sha256": sha256_file(args.out),
        "rows": sorted(audit_rows, key=lambda row: row["task"]),
    }
    atomic_json(args.audit, audit)
    print(f"SCHEMA_PROBE_REPAIR_GENERATION_PASS tasks={len(entries)} manifest_sha256={audit['manifest_sha256']}")


if __name__ == "__main__":
    main()
