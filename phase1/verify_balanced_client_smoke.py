"""Independent, score-blind verifier for the balanced three-client smoke."""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
from pathlib import Path
from typing import Any

import yaml


SCHEMA = "balanced-client-smoke-independent-verification-v1"
TASK = "spooky-author-identification"
SEED = 1401
OPERATORS = ("analyze", "debug", "draft", "improve")
CLIENTS = {
    0: ("deepseek-v4-flash", "https://api.deepseek.com"),
    1: ("qwen3-coder-flash", "https://dashscope.aliyuncs.com/compatible-mode/v1"),
    2: ("glm-5", "https://dashscope.aliyuncs.com/compatible-mode/v1"),
}
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


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def canonical(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False)


def verify_client_config(config: dict[str, Any], model: str, base_url: str) -> None:
    if nested(config, "metadata.seed") != SEED:
        raise VerificationError("final seed mismatch")
    if nested(config, "task.name") != TASK:
        raise VerificationError("final task mismatch")
    if nested(config, "solver.step_limit") != 2:
        raise VerificationError("final step limit mismatch")
    if nested(config, "solver.execution_timeout") != 300:
        raise VerificationError("final execution timeout mismatch")
    if nested(config, "solver.time_limit_secs") != 900:
        raise VerificationError("final run cap mismatch")
    if nested(config, "logger.write_env_vars") is not False:
        raise VerificationError("environment logging was not disabled")
    for operator in OPERATORS:
        client = nested(config, f"solver.operators.{operator}.llm.client")
        if client.get("model_id") != model or client.get("base_url") != base_url:
            raise VerificationError(f"final client mismatch: {operator}")


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
    if [row.get("step") for row in rows] != [0, 1]:
        raise VerificationError("journal must contain exactly steps 0 and 1")
    if rows[0].get("code") not in (None, ""):
        raise VerificationError("MCTS root must have blank code")
    if not isinstance(rows[1].get("code"), str) or not rows[1]["code"].strip():
        raise VerificationError("non-root candidate contains empty code")
    if rows[0].get("parents") not in (None, []):
        raise VerificationError("root has a parent")
    if rows[1].get("parents") != [0]:
        raise VerificationError("step 1 parent mismatch")
    if rows[0].get("children") != [1] or rows[1].get("children") not in (None, []):
        raise VerificationError("journal child graph mismatch")
    return rows


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
        if not 0 < elapsed <= 1800 or "gres/gpu=1" not in resources:
            raise VerificationError("Slurm resource contract mismatch")
    return {job: rows[job][2] for job in job_ids}


def verify(root: Path, expected_commit: str, output: Path) -> dict[str, Any]:
    root = root.resolve()
    if not re.fullmatch(r"[0-9a-f]{40}", expected_commit):
        raise VerificationError("expected commit must be a full SHA")
    if not root.is_dir():
        raise VerificationError("run root does not exist")
    if any(path.name == "env_variables.json" for path in root.rglob("*")):
        raise VerificationError("environment dump exists")
    if (root / "source_commit.txt").read_text(encoding="utf-8").strip() != expected_commit:
        raise VerificationError("source commit mismatch")
    if (root / "control_commit.txt").read_text(encoding="utf-8").strip() != expected_commit:
        raise VerificationError("control commit mismatch")
    job_ids = [line for line in (root / "submission.txt").read_text(encoding="utf-8").splitlines() if line]
    if len(job_ids) != 3 or len(set(job_ids)) != 3 or any(not job.isdigit() for job in job_ids):
        raise VerificationError("submission must contain three unique job IDs")
    elapsed = parse_accounting(root, job_ids)

    run_configs = list((root / "outputs").rglob("dojo_config.json"))
    if len(run_configs) != 3:
        raise VerificationError("expected exactly three output run roots")
    by_model: dict[str, Path] = {}
    rows: list[dict[str, Any]] = []
    for index, (model, base_url) in CLIENTS.items():
        rc = checked_json(root / f"rc_{index}.json")
        if rc != {"array_index": index, "model": model, "rc": 0, "source_commit": expected_commit}:
            raise VerificationError(f"worker receipt mismatch: {index}")
        resolved = checked_yaml(root / f"resolved_{index}.yaml")
        verify_client_config(resolved, model, base_url)
        matches = []
        for config_path in run_configs:
            config = checked_json(config_path)
            if nested(config, "solver.operators.analyze.llm.client.model_id") == model:
                matches.append((config_path, config))
        if len(matches) != 1:
            raise VerificationError(f"expected one final run for {model}")
        run_config_path, config = matches[0]
        by_model[model] = run_config_path
        verify_client_config(config, model, base_url)
        run_dir = run_config_path.parent
        journal_path = run_dir / "checkpoint" / "journal.jsonl"
        state_path = run_dir / "checkpoint" / "state.json"
        journal = parse_journal(journal_path)
        state = checked_json(state_path)
        if state.get("current_step") != 2 or state.get("num_starts") != 0:
            raise VerificationError(f"checkpoint state mismatch: {model}")
        search_paths = list(run_dir.glob("*_search_data.json"))
        if len(search_paths) != 1:
            raise VerificationError(f"expected one search export: {model}")
        search = checked_json(search_paths[0])
        if canonical(search.get("nodes")) != canonical(journal):
            raise VerificationError(f"search export/journal mismatch: {model}")
        rows.append(
            {
                "index": index,
                "model": model,
                "journal_rows": len(journal),
                "journal_sha256": sha256(journal_path),
                "state_sha256": sha256(state_path),
                "search_sha256": sha256(search_paths[0]),
                "config_sha256": sha256(run_config_path),
            }
        )
    if set(by_model) != {value[0] for value in CLIENTS.values()}:
        raise VerificationError("final model coverage mismatch")
    result = {
        "schema_version": SCHEMA,
        "status": "PASS_BALANCED_CLIENT_SMOKE",
        "source_commit": expected_commit,
        "control_commit": expected_commit,
        "task": TASK,
        "seed": SEED,
        "physical_runs": 3,
        "journal_rows_total": 6,
        "environment_dumps": 0,
        "job_ids": job_ids,
        "elapsed_seconds": elapsed,
        "rows": rows,
        "score_fields_read": False,
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
        f"BALANCED_CLIENT_SMOKE_VERIFIED status={result['status']} "
        f"runs={result['physical_runs']} journal_rows={result['journal_rows_total']}"
    )


if __name__ == "__main__":
    main()
