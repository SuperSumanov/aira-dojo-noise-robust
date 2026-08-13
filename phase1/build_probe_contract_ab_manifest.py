#!/usr/bin/env python3
"""Fail-closed validation of the frozen probe-contract A/B generation grid."""

from __future__ import annotations

import argparse
import copy
import json
from pathlib import Path

from phase1.build_schema_probe_generation_manifest import nested
from phase1.build_schema_probe_repair_manifest import validate_topology
from phase1.probe_contract_ab_common import (
    atomic_json,
    row_for_index,
    sha256_file,
    sha256_text,
    spec_for_version,
)


CONTRACT_PREFIXES = (
    "- CRITICAL ANYTIME ARTIFACT CONTRACT:",
    "- Preserve the probe as immutable `candidate_probe.csv`.",
    "- Continue IN THE SAME PYTHON PROCESS from that probe into the full candidate method.",
    "- The host evaluates artifact creation time independently.",
)


def strip_contract(prompt: str) -> tuple[str, list[str]]:
    kept: list[str] = []
    removed: list[str] = []
    for line in prompt.splitlines():
        normalized = line.strip()
        if any(normalized.startswith(prefix) for prefix in CONTRACT_PREFIXES):
            removed.append(normalized)
        else:
            kept.append(line)
    return "\n".join(kept), removed


def aggregate_usage(code_nodes: list[dict]) -> dict:
    totals = {
        "records": 0,
        "successful_records": 0,
        "prompt_tokens": 0,
        "completion_tokens": 0,
        "reasoning_tokens": 0,
        "total_tokens": 0,
        "latency_s": 0.0,
    }
    for node in code_nodes:
        metrics = node.get("operators_metrics", [])
        if not isinstance(metrics, list):
            raise RuntimeError("operators_metrics is not a list")
        for metric in metrics:
            usage = metric.get("usage") if isinstance(metric, dict) else None
            if not isinstance(usage, dict):
                continue
            totals["records"] += 1
            totals["successful_records"] += int(usage.get("success") is True)
            for name in ("prompt_tokens", "completion_tokens", "total_tokens"):
                totals[name] += int(usage.get(name) or 0)
            details = usage.get("completion_tokens_details") or {}
            totals["reasoning_tokens"] += int(details.get("reasoning_tokens") or 0)
            totals["latency_s"] += float(usage.get("latency") or 0.0)
    totals["latency_s"] = round(totals["latency_s"], 6)
    return totals


def normalize_solver(solver: dict) -> dict:
    value = copy.deepcopy(solver)
    # Hydra resolves these two fields from the per-run experiment identity.
    # They must differ across independent A/B runs and do not change solver
    # behavior.  Keep every scientific knob fail-closed below this boundary.
    value.pop("checkpoint_path", None)
    value.pop("exp_name", None)
    value["operators"]["draft"]["system_message_prompt_template"]["template"] = "<ARM_PROMPT>"
    return value


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--version", choices=("v1", "v2"), default="v1")
    parser.add_argument("--run-root", type=Path, required=True)
    parser.add_argument("--status-dir", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    spec = spec_for_version(args.version)
    if args.out.exists():
        raise RuntimeError(f"refusing existing generation manifest: {args.out}")

    status_paths = sorted(args.status_dir.glob("index_*.json"))
    if len(status_paths) != len(spec.matrix):
        raise RuntimeError(f"expected {len(spec.matrix)} status records, got {len(status_paths)}")
    statuses: dict[int, tuple[dict, Path]] = {}
    for path in status_paths:
        row = json.loads(path.read_text(encoding="utf-8"))
        index = int(row.get("index", -1))
        expected = row_for_index(index, args.version)
        if any(row.get(key) != value for key, value in expected.items()):
            raise RuntimeError(f"status identity mismatch: {path}")
        if args.version == "v2" and (
            row.get("schema_version") != spec.schema_version
            or row.get("experiment") != spec.experiment
            or row.get("version") != spec.version
        ):
            raise RuntimeError(f"status experiment mismatch: {path}")
        if row.get("return_code") != 0 or not isinstance(row.get("command_sha256"), str):
            raise RuntimeError(f"generation infrastructure failed: {path}")
        if index in statuses:
            raise RuntimeError(f"duplicate status index: {index}")
        statuses[index] = (row, path)
    if set(statuses) != set(range(len(spec.matrix))):
        raise RuntimeError("status index grid mismatch")

    config_records: list[tuple[str, Path]] = []
    for arm, issue in spec.issue_by_arm.items():
        issue_root = args.run_root / f"user_yzyang4_issue_{issue}"
        paths = sorted(issue_root.glob("*/dojo_config.json"))
        if len(paths) != len(spec.tasks):
            raise RuntimeError(f"expected {len(spec.tasks)} configs for {arm}, got {len(paths)}")
        config_records.extend((arm, path) for path in paths)
    if len(config_records) != len(spec.matrix):
        raise RuntimeError("total config count mismatch")

    rows: list[dict] = []
    prompts: dict[tuple[str, str], str] = {}
    normalized_solvers: dict[tuple[str, str], dict] = {}
    seen: set[tuple[str, str]] = set()
    matrix_index = {(row["task"], row["arm"]): row["index"] for row in spec.matrix}
    for arm, config_path in config_records:
        config = json.loads(config_path.read_text(encoding="utf-8"))
        task = str(nested(config, "task", "name"))
        key = (task, arm)
        if key not in matrix_index or key in seen:
            raise RuntimeError(f"unexpected/duplicate generated block: {key}")
        seen.add(key)
        index = matrix_index[key]
        expected = row_for_index(index, args.version)
        if int(nested(config, "metadata", "seed")) != spec.seed:
            raise RuntimeError(f"seed mismatch: {key}")
        if str(nested(config, "metadata", "git_issue_id")) != expected["issue"]:
            raise RuntimeError(f"issue mismatch: {key}")
        expected_data = Path("/research/d7/spc/yzyang4/mle-bench-data") / task / "prepared" / "public"
        if Path(nested(config, "task", "data_dir")) != expected_data:
            raise RuntimeError(f"non-public data path: {key}")

        solver = nested(config, "solver")
        exact_budget = {
            "step_limit": 3,
            "num_children": 1,
            "max_debug_depth": 1,
            "execution_timeout": 600,
            "time_limit_secs": 1200,
        }
        if any(int(solver.get(name, -1)) != value for name, value in exact_budget.items()):
            raise RuntimeError(f"solver budget mismatch: {key}")
        if solver.get("stop_after_first_valid") is not True:
            raise RuntimeError(f"first-valid stop disabled: {key}")
        operators = solver.get("operators", {})
        for name in ("analyze", "debug", "draft", "improve"):
            if nested(operators, name, "llm", "client", "model_id") != "deepseek-v4-flash":
                raise RuntimeError(f"client mismatch: {key}/{name}")
        prompt = str(nested(operators, "draft", "system_message_prompt_template", "template"))
        has_contract = "CRITICAL ANYTIME ARTIFACT CONTRACT" in prompt and "candidate_probe.csv" in prompt
        if has_contract != (arm == "contract"):
            raise RuntimeError(f"arm prompt mismatch: {key}")
        prompts[key] = prompt
        normalized_solvers[key] = normalize_solver(solver)

        experiment_dir = config_path.parent
        if Path(nested(config, "logger", "output_dir")) != experiment_dir:
            raise RuntimeError(f"logger output mismatch: {key}")
        exports = sorted(experiment_dir.glob("*_MCTS_search_data.json"))
        journals = sorted(experiment_dir.glob("checkpoint/journal.jsonl"))
        states = sorted(experiment_dir.glob("checkpoint/state.json"))
        if len(exports) != 1 or len(journals) != 1 or len(states) != 1:
            raise RuntimeError(f"incomplete generation artifacts: {key}")
        export = json.loads(exports[0].read_text(encoding="utf-8"))
        state = json.loads(states[0].read_text(encoding="utf-8"))
        journal_lines = sum(bool(line.strip()) for line in journals[0].read_text(encoding="utf-8").splitlines())
        mode, code_nodes, selected = validate_topology(
            export.get("nodes") if isinstance(export, dict) else None,
            journal_lines=journal_lines,
            current_step=int(state.get("current_step", -1)),
        )
        task_id = str(config.get("id", ""))
        if not task_id or experiment_dir.name != task_id:
            raise RuntimeError(f"task id mismatch: {key}")
        if solver.get("exp_name") != task_id or Path(solver.get("checkpoint_path", "")) != (
            experiment_dir / "checkpoint"
        ):
            raise RuntimeError(f"solver run-identity path mismatch: {key}")
        status, status_path = statuses[index]
        rows.append(
            {
                **expected,
                "task_id": task_id,
                "experiment_dir": str(experiment_dir),
                "dojo_config_sha256": sha256_file(config_path),
                "source_export": str(exports[0]),
                "source_export_sha256": sha256_file(exports[0]),
                "journal_sha256": sha256_file(journals[0]),
                "state_sha256": sha256_file(states[0]),
                "status_sha256": sha256_file(status_path),
                "command_sha256": status["command_sha256"],
                "generation_wall_s": status["wall_s"],
                "topology_mode": mode,
                "code_nodes": len(code_nodes),
                "selected_node_id": str(selected.get("id", "")),
                "selected_node_step": selected.get("step"),
                "selected_node_is_buggy": selected.get("is_buggy"),
                "journal_lines": journal_lines,
                "current_step": state.get("current_step"),
                "draft_prompt_sha256": sha256_text(prompt),
                "llm_usage": aggregate_usage(code_nodes),
            }
        )

    if seen != set(matrix_index):
        raise RuntimeError("generated block grid incomplete")
    prompt_audits = []
    for task in spec.tasks:
        original = prompts[(task, "original")]
        contract = prompts[(task, "contract")]
        stripped, removed = strip_contract(contract)
        if stripped != original or len(removed) != len(CONTRACT_PREFIXES):
            raise RuntimeError(f"prompt difference is not exactly the frozen contract block: {task}")
        if normalized_solvers[(task, "original")] != normalized_solvers[(task, "contract")]:
            raise RuntimeError(f"non-prompt solver difference: {task}")
        prompt_audits.append(
            {
                "task": task,
                "original_prompt_sha256": sha256_text(original),
                "contract_prompt_sha256": sha256_text(contract),
                "removed_contract_lines": removed,
                "normalized_solver_equal": True,
            }
        )

    payload = {
        "schema_version": spec.schema_version,
        "experiment": spec.experiment,
        "version": spec.version,
        "seed": spec.seed,
        "tasks": list(spec.tasks),
        "arms": list(spec.issue_by_arm),
        "rows": sorted(rows, key=lambda row: row["index"]),
        "prompt_audits": prompt_audits,
    }
    atomic_json(args.out, payload)
    print(
        f"PROBE_CONTRACT_AB_GENERATION_PASS version={spec.version} "
        f"rows={len(rows)} pairs={len(spec.tasks)}",
        flush=True,
    )


if __name__ == "__main__":
    main()
