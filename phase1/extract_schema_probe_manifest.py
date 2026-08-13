#!/usr/bin/env python3
"""Freeze one generated draft per task for the schema/probe contract smoke.

The extractor is deliberately fail-closed: it accepts exactly one completed run and one
non-empty code node for every preregistered task.  It performs only a static contract gate;
the replay worker and independent validator establish whether the emitted artifacts are real.
"""

from __future__ import annotations

import argparse
import ast
import hashlib
import json
import os
import tempfile
from pathlib import Path


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


def static_contract(code: str) -> dict[str, object]:
    checks: dict[str, object] = {}
    try:
        tree = ast.parse(code)
        checks["python_ast_parse"] = True
    except SyntaxError as exc:
        checks["python_ast_parse"] = False
        checks["syntax_error"] = f"{exc.msg}:{exc.lineno}"
        return checks

    constants = [
        node.value
        for node in ast.walk(tree)
        if isinstance(node, ast.Constant) and isinstance(node.value, str)
    ]
    joined = "\n".join(constants)
    calls = list(ast.walk(tree))
    checks["candidate_probe_path"] = "candidate_probe.csv" in joined
    checks["candidate_marker"] = "CANDIDATE_PROBE_READY" in joined
    checks["full_marker"] = "FULL_CANDIDATE_READY" in joined
    checks["common_fallback_marker_available"] = "COMMON_FALLBACK_READY" in joined
    checks["uses_os_replace"] = any(
        isinstance(node, ast.Call)
        and isinstance(node.func, ast.Attribute)
        and isinstance(node.func.value, ast.Name)
        and node.func.value.id == "os"
        and node.func.attr == "replace"
        for node in calls
    )
    checks["uses_fsync"] = any(
        isinstance(node, ast.Call)
        and isinstance(node.func, ast.Attribute)
        and isinstance(node.func.value, ast.Name)
        and node.func.value.id == "os"
        and node.func.attr == "fsync"
        for node in calls
    )
    required = (
        "python_ast_parse",
        "candidate_probe_path",
        "candidate_marker",
        "full_marker",
        "uses_os_replace",
        "uses_fsync",
    )
    checks["required_pass"] = all(checks.get(name) is True for name in required)
    return checks


def parse_seed(task_id: str) -> int:
    marker = "_seed_"
    if marker not in task_id:
        raise RuntimeError(f"task id has no seed: {task_id}")
    return int(task_id.split(marker, 1)[1].split("_", 1)[0])


def self_test() -> None:
    compliant = '''
import os
name = "candidate_probe.csv"
os.replace("a.tmp", name)
os.fsync(1)
print("CANDIDATE_PROBE_READY elapsed_s=1 sha256=" + "a" * 64)
print("FULL_CANDIDATE_READY elapsed_s=2 sha256=" + "b" * 64)
print("COMMON_FALLBACK_READY")
'''
    checks = static_contract(compliant)
    assert checks["required_pass"] is True
    assert static_contract("print('submission.csv')").get("required_pass") is False
    assert parse_seed("user_x_seed_861_id_y") == 861
    print("SCHEMA_PROBE_EXTRACTOR_SELF_TEST_PASS")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--run-root", type=Path)
    parser.add_argument("--run-manifest", type=Path)
    parser.add_argument("--issue")
    parser.add_argument("--tasks", nargs="+")
    parser.add_argument("--seed", type=int)
    parser.add_argument("--out", type=Path)
    parser.add_argument("--audit", type=Path)
    parser.add_argument("--self-test", action="store_true")
    args = parser.parse_args()
    if args.self_test:
        self_test()
        return
    if None in (args.run_root, args.issue, args.tasks, args.seed, args.out, args.audit):
        parser.error("--run-root --issue --tasks --seed --out --audit are required")

    expected_tasks = sorted(set(args.tasks))
    if len(expected_tasks) != len(args.tasks):
        raise RuntimeError("duplicate preregistered task")
    if args.out.exists() or args.audit.exists():
        raise RuntimeError("refusing to overwrite extraction outputs")

    issue_root = args.run_root / f"user_yzyang4_issue_{args.issue}"
    if args.run_manifest is not None:
        manifest_path = args.run_manifest
        if not manifest_path.is_file():
            raise RuntimeError(f"explicit run manifest missing: {manifest_path}")
    else:
        manifests = sorted(issue_root.glob("srun_pool/*/manifest.json"))
        if len(manifests) != 1:
            raise RuntimeError(f"expected one run manifest, got {len(manifests)}")
        manifest_path = manifests[0]
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    task_entries = manifest.get("tasks")
    if not isinstance(task_entries, dict) or len(task_entries) != len(expected_tasks):
        raise RuntimeError("run manifest task count differs from frozen matrix")

    rows: list[dict] = []
    audit_rows: list[dict] = []
    seen_tasks: set[str] = set()
    for task_id, meta in sorted(task_entries.items()):
        if not isinstance(meta, dict):
            raise RuntimeError(f"malformed task metadata: {task_id}")
        task = str(meta.get("task_name", ""))
        seed = parse_seed(task_id)
        status = str(meta.get("status", "")).lower()
        exit_code = meta.get("exit_code")
        if task not in expected_tasks or task in seen_tasks or seed != args.seed:
            raise RuntimeError(f"unexpected task/seed: {task_id} task={task} seed={seed}")
        if status != "completed" or int(exit_code) != 0:
            raise RuntimeError(f"incomplete generation: {task_id} status={status} rc={exit_code}")
        seen_tasks.add(task)

        experiment_dir = Path(meta["experiment_dir"])
        exports = sorted(experiment_dir.glob("*_MCTS_search_data.json"))
        if len(exports) != 1 or exports[0].stat().st_size == 0:
            raise RuntimeError(f"expected one nonempty search export: {task_id}")
        export_path = exports[0]
        export = json.loads(export_path.read_text(encoding="utf-8"))
        nodes = export.get("nodes") if isinstance(export, dict) else None
        if not isinstance(nodes, list):
            raise RuntimeError(f"search export has no node list: {task_id}")
        code_nodes = [node for node in nodes if isinstance(node, dict) and str(node.get("code", "")).strip()]
        if len(code_nodes) != 1:
            raise RuntimeError(f"expected exactly one generated code node, got {len(code_nodes)}: {task_id}")
        node = code_nodes[0]
        code = str(node["code"])
        checks = static_contract(code)
        code_sha = hashlib.sha256(code.encode("utf-8")).hexdigest()
        audit_rows.append(
            {
                "task": task,
                "seed": seed,
                "task_id": task_id,
                "experiment_dir": str(experiment_dir),
                "source_export": str(export_path),
                "source_export_sha256": sha256_file(export_path),
                "node_id": str(node.get("id", "")),
                "node_step": node.get("step"),
                "node_exit_code": node.get("exit_code"),
                "code_sha256": code_sha,
                "code_bytes": len(code.encode("utf-8")),
                "static_contract": checks,
            }
        )
        if checks.get("required_pass") is not True:
            continue
        rows.append(
            {
                "schema_version": 1,
                "card_id": f"schema_probe|{task}|seed={seed}|node={node.get('id', '')}",
                "competition": task,
                "seed": seed,
                "code": code,
                "code_sha256": code_sha,
                "source_task_id": task_id,
                "source_export": str(export_path),
                "source_export_sha256": sha256_file(export_path),
                "source_run_manifest": str(manifest_path),
                "source_run_manifest_sha256": sha256_file(manifest_path),
            }
        )

    audit_payload = {
        "schema_version": 1,
        "issue": args.issue,
        "seed": args.seed,
        "expected_tasks": expected_tasks,
        "run_manifest": str(manifest_path),
        "run_manifest_sha256": sha256_file(manifest_path),
        "generated_rows": len(audit_rows),
        "static_gate_pass_rows": len(rows),
        "rows": audit_rows,
    }
    atomic_json(args.audit, audit_payload)
    if seen_tasks != set(expected_tasks) or len(rows) != len(expected_tasks):
        raise RuntimeError(
            f"static contract gate failed: seen={sorted(seen_tasks)} pass={len(rows)}/{len(expected_tasks)}"
        )

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
    print(
        "SCHEMA_PROBE_EXTRACTION_PASS "
        f"tasks={len(rows)} seed={args.seed} manifest_sha256={audit_payload['replay_manifest_sha256']}"
    )


if __name__ == "__main__":
    main()
