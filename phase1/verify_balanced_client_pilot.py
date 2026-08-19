"""Independent support-only verifier for the balanced three-client pilot."""
from __future__ import annotations

import argparse
import collections
import hashlib
import json
import math
import os
import re
from pathlib import Path
from typing import Any

import yaml


SCHEMA = "balanced-client-pilot-independent-verification-v1"
OPERATORS = ("analyze", "debug", "draft", "improve")
CREDENTIAL = re.compile(
    rb"(?:^|[^A-Za-z0-9])(?:sk-[A-Za-z0-9._-]{16,}|hf_[A-Za-z0-9]{16,}|"
    rb"gh[pousr]_[A-Za-z0-9]{16,}|AKIA[0-9A-Z]{16}|AIza[0-9A-Za-z_-]{30,}|"
    rb"Bearer\s+[A-Za-z0-9._-]{20,}|BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY)"
)


class VerificationError(RuntimeError):
    pass


def checked_bytes(path: Path, cap: int = 64 * 1024 * 1024) -> bytes:
    if not path.is_file():
        raise VerificationError(f"missing required file: {path}")
    size = path.stat().st_size
    if size <= 0 or size > cap:
        raise VerificationError(f"file outside byte cap: {path}")
    blob = path.read_bytes()
    if len(blob) != size:
        raise VerificationError(f"short read: {path}")
    if CREDENTIAL.search(blob):
        raise VerificationError(f"credential-shaped content refused before parse: {path}")
    return blob


def checked_json(path: Path) -> Any:
    try:
        return json.loads(checked_bytes(path).decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as error:
        raise VerificationError(f"invalid JSON: {path}") from error


def checked_yaml(path: Path) -> Any:
    try:
        return yaml.safe_load(checked_bytes(path).decode("utf-8"))
    except (UnicodeDecodeError, yaml.YAMLError) as error:
        raise VerificationError(f"invalid YAML: {path}") from error


def nested(value: Any, dotted: str) -> Any:
    current = value
    for part in dotted.split("."):
        if not isinstance(current, dict) or part not in current:
            raise VerificationError(f"missing field: {dotted}")
        current = current[part]
    return current


def canonical(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False)


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def issue_id(row: dict[str, Any]) -> str:
    return f"balanced_client_pilot_20260819_{row['model_id']}_{row['task']}_{row['seed']}"


def verify_config(config: dict[str, Any], row: dict[str, Any]) -> None:
    if nested(config, "metadata.seed") != row["seed"] or nested(config, "task.name") != row["task"]:
        raise VerificationError("task/seed mismatch")
    if nested(config, "metadata.git_issue_id") != issue_id(row):
        raise VerificationError("issue ID mismatch")
    if nested(config, "solver.step_limit") != 4:
        raise VerificationError("step limit mismatch")
    if nested(config, "solver.execution_timeout") != 300:
        raise VerificationError("execution timeout mismatch")
    if nested(config, "solver.time_limit_secs") != 1800:
        raise VerificationError("run cap mismatch")
    if nested(config, "logger.write_env_vars") is not False:
        raise VerificationError("environment logging was not disabled")
    for operator in OPERATORS:
        client = nested(config, f"solver.operators.{operator}.llm.client")
        if client.get("model_id") != row["model_id"] or client.get("base_url") != row["base_url"]:
            raise VerificationError(f"client mismatch: {operator}")


def parse_journal(path: Path) -> list[dict[str, Any]]:
    try:
        lines = checked_bytes(path).decode("utf-8").splitlines()
    except UnicodeDecodeError as error:
        raise VerificationError("journal is not UTF-8") from error
    rows: list[dict[str, Any]] = []
    for line_number, line in enumerate(lines, 1):
        if not line:
            continue
        try:
            row = json.loads(line)
        except json.JSONDecodeError as error:
            raise VerificationError(f"invalid journal row {line_number}") from error
        if not isinstance(row, dict):
            raise VerificationError("journal row is not an object")
        rows.append(row)
    if [row.get("step") for row in rows] != [0, 1, 2, 3]:
        raise VerificationError("journal must contain exactly steps 0 through 3")
    if rows[0].get("code") not in (None, ""):
        raise VerificationError("MCTS root must have blank code")
    if any(not isinstance(row.get("code"), str) or not row["code"].strip() for row in rows[1:]):
        raise VerificationError("non-root candidate contains empty code")
    by_step = {row["step"]: row for row in rows}
    expected_children: dict[int, list[int]] = collections.defaultdict(list)
    for row in rows:
        parents = row.get("parents") or []
        step = row["step"]
        if step == 0:
            if parents:
                raise VerificationError("root has a parent")
        elif len(parents) != 1 or parents[0] not in by_step or parents[0] >= step:
            raise VerificationError("non-root parent graph mismatch")
        for parent in parents:
            expected_children[parent].append(step)
    for row in rows:
        if sorted(row.get("children") or []) != sorted(expected_children[row["step"]]):
            raise VerificationError("declared child graph mismatch")
    return rows


def valid_candidate(node: dict[str, Any]) -> bool:
    metric = node.get("metric")
    info = node.get("metric_info")
    return (
        not node.get("is_buggy", False)
        and not isinstance(metric, bool)
        and isinstance(metric, (int, float))
        and math.isfinite(float(metric))
        and isinstance(info, dict)
        and info.get("valid_submission") in (1, 1.0, True)
    )


def support_counts(journal: list[dict[str, Any]]) -> tuple[int, int]:
    valid = [node for node in journal[1:] if valid_candidate(node)]
    by_parent: collections.Counter[int] = collections.Counter(int(node["parents"][0]) for node in valid)
    pairs = sum(count * (count - 1) // 2 for count in by_parent.values())
    return len(valid), pairs


def parse_accounting(root: Path, job_ids: list[str]) -> dict[str, int]:
    lines = checked_bytes(root / "slurm_accounting.txt").decode("utf-8").splitlines()
    rows: dict[str, tuple[str, str, int, str]] = {}
    for line in lines:
        fields = line.split("|")
        if len(fields) != 5 or fields[0] not in job_ids:
            continue
        job, state, exit_code, elapsed_raw, resources = fields
        if job in rows:
            raise VerificationError("duplicate top-level accounting row")
        try:
            elapsed = int(elapsed_raw)
        except ValueError as error:
            raise VerificationError("non-integer accounting duration") from error
        rows[job] = (state, exit_code, elapsed, resources)
    if set(rows) != set(job_ids):
        raise VerificationError("incomplete top-level accounting")
    for state, exit_code, elapsed, resources in rows.values():
        if state != "COMPLETED" or exit_code != "0:0":
            raise VerificationError("Slurm job did not complete cleanly")
        if not 0 < elapsed <= 8100 or "gres/gpu=1" not in resources:
            raise VerificationError("Slurm resource contract mismatch")
    return {job: rows[job][2] for job in job_ids}


def validate_manifest(manifest: dict[str, Any]) -> list[dict[str, Any]]:
    if manifest.get("schema_version") != "balanced-client-pilot-manifest-v1":
        raise VerificationError("manifest schema mismatch")
    if manifest.get("tasks") != ["spooky-author-identification", "spaceship-titanic"]:
        raise VerificationError("manifest task list mismatch")
    if manifest.get("seeds") != [1402, 1403]:
        raise VerificationError("manifest seed list mismatch")
    if manifest.get("slurm_time_limit") != "02:15:00":
        raise VerificationError("manifest Slurm cap mismatch")
    if manifest.get("shards") != [[0, 4, 8], [5, 9, 1], [10, 2, 6], [3, 7, 11]]:
        raise VerificationError("manifest shard schedule mismatch")
    rows = manifest.get("rows")
    if not isinstance(rows, list) or len(rows) != 12:
        raise VerificationError("manifest must contain 12 rows")
    expected = {
        (model, task, seed)
        for model in ("deepseek-v4-flash", "qwen3-coder-flash", "glm-5")
        for task in ("spooky-author-identification", "spaceship-titanic")
        for seed in (1402, 1403)
    }
    actual = {(row.get("model_id"), row.get("task"), row.get("seed")) for row in rows}
    if actual != expected or [row.get("index") for row in rows] != list(range(12)):
        raise VerificationError("manifest factorial grid mismatch")
    if manifest.get("step_limit") != 4 or manifest.get("execution_timeout") != 300:
        raise VerificationError("manifest execution contract mismatch")
    if manifest.get("run_time_limit_secs") != 1800:
        raise VerificationError("manifest run cap mismatch")
    return rows


def verify(root: Path, expected_commit: str, output: Path) -> dict[str, Any]:
    root = root.resolve()
    if not re.fullmatch(r"[0-9a-f]{40}", expected_commit):
        raise VerificationError("expected commit must be a full SHA")
    if any(path.name == "env_variables.json" for path in root.rglob("*")):
        raise VerificationError("environment dump exists")
    if (root / "source_commit.txt").read_text(encoding="utf-8").strip() != expected_commit:
        raise VerificationError("source commit mismatch")
    if (root / "control_commit.txt").read_text(encoding="utf-8").strip() != expected_commit:
        raise VerificationError("control commit mismatch")
    manifest = checked_json(root / "manifest.json")
    rows = validate_manifest(manifest)
    job_ids = [line for line in (root / "submission.txt").read_text(encoding="utf-8").splitlines() if line]
    if len(job_ids) != 4 or len(set(job_ids)) != 4 or any(not job.isdigit() for job in job_ids):
        raise VerificationError("submission must contain four unique shard job IDs")
    elapsed = parse_accounting(root, job_ids)
    run_configs = list((root / "outputs").rglob("dojo_config.json"))
    if len(run_configs) != 12:
        raise VerificationError("expected exactly 12 output run roots")

    valid_runs = collections.Counter()
    valid_nodes = collections.Counter()
    sibling_pairs = collections.Counter()
    per_task_valid_runs = collections.Counter()
    receipts: list[dict[str, Any]] = []
    for row in rows:
        index = row["index"]
        expected_rc = {
            "index": index, "model": row["model_id"], "task": row["task"], "seed": row["seed"],
            "rc": 0, "source_commit": expected_commit,
        }
        if checked_json(root / f"rc_{index}.json") != expected_rc:
            raise VerificationError(f"worker receipt mismatch: {index}")
        resolved = checked_yaml(root / f"resolved_{index}.yaml")
        verify_config(resolved, row)
        matches = []
        for config_path in run_configs:
            config = checked_json(config_path)
            if nested(config, "metadata.git_issue_id") == issue_id(row):
                matches.append((config_path, config))
        if len(matches) != 1:
            raise VerificationError(f"expected one final run for manifest row {index}")
        config_path, config = matches[0]
        verify_config(config, row)
        run_dir = config_path.parent
        journal_path = run_dir / "checkpoint" / "journal.jsonl"
        state_path = run_dir / "checkpoint" / "state.json"
        journal = parse_journal(journal_path)
        state = checked_json(state_path)
        if state.get("current_step") != 4 or state.get("num_starts") != 0:
            raise VerificationError(f"checkpoint state mismatch: {index}")
        search_paths = list(run_dir.glob("*_search_data.json"))
        if len(search_paths) != 1:
            raise VerificationError(f"expected one search export: {index}")
        search = checked_json(search_paths[0])
        if canonical(search.get("nodes")) != canonical(journal):
            raise VerificationError(f"search export/journal mismatch: {index}")
        node_count, pair_count = support_counts(journal)
        model = row["model_id"]
        valid_nodes[model] += node_count
        sibling_pairs[model] += pair_count
        if node_count > 0:
            valid_runs[model] += 1
            per_task_valid_runs[row["task"]] += 1
        receipts.append({
            "index": index, "model": model, "task": row["task"], "seed": row["seed"],
            "valid_nonroot_nodes": node_count, "finite_sibling_pairs": pair_count,
            "journal_sha256": sha256(journal_path), "config_sha256": sha256(config_path),
            "state_sha256": sha256(state_path), "search_sha256": sha256(search_paths[0]),
        })

    models = ("deepseek-v4-flash", "qwen3-coder-flash", "glm-5")
    total_nodes = sum(valid_nodes.values())
    total_pairs = sum(sibling_pairs.values())
    max_pair_share = max(sibling_pairs.values(), default=0) / total_pairs if total_pairs else 1.0
    gates = {
        "each_client_valid_runs_at_least_2": all(valid_runs[model] >= 2 for model in models),
        "valid_nonroot_nodes_at_least_18": total_nodes >= 18,
        "finite_sibling_pairs_at_least_6": total_pairs >= 6,
        "each_client_has_pair": all(sibling_pairs[model] >= 1 for model in models),
        "max_client_pair_share_at_most_0_60": max_pair_share <= 0.60,
    }
    status = "GO_BALANCED_ACQUISITION" if all(gates.values()) else "INSUFFICIENT_BALANCED_PILOT_SUPPORT"
    result = {
        "schema_version": SCHEMA,
        "status": status,
        "source_commit": expected_commit,
        "control_commit": expected_commit,
        "physical_runs": 12,
        "journal_rows_total": 48,
        "environment_dumps": 0,
        "job_ids": job_ids,
        "elapsed_seconds": elapsed,
        "valid_runs_by_client": dict(valid_runs),
        "valid_runs_by_task": dict(per_task_valid_runs),
        "valid_nonroot_nodes_by_client": dict(valid_nodes),
        "finite_sibling_pairs_by_client": dict(sibling_pairs),
        "valid_nonroot_nodes_total": total_nodes,
        "finite_sibling_pairs_total": total_pairs,
        "max_client_pair_share": max_pair_share,
        "gates": gates,
        "rows": receipts,
        "score_values_reported": False,
        "winner_labels_computed": False,
    }
    temporary = output.with_suffix(output.suffix + ".tmp")
    temporary.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    os.replace(temporary, output)
    return result


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", type=Path, required=True)
    parser.add_argument("--expected-commit", required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    result = verify(args.root, args.expected_commit, args.output)
    print(
        f"BALANCED_CLIENT_PILOT_VERIFIED status={result['status']} runs={result['physical_runs']} "
        f"valid_nodes={result['valid_nonroot_nodes_total']} pairs={result['finite_sibling_pairs_total']}"
    )


if __name__ == "__main__":
    main()
