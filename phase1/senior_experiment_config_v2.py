#!/usr/bin/env python3
"""Export one future-only, prompt-sensitive senior config sidecar row.

The exporter reads a producer-side ``dojo_config.json`` before archive release.
It emits only public metadata and SHA-256 fingerprints; the resolved solver
payload itself is never copied to the sidecar.
"""
from __future__ import annotations

import argparse
import copy
import datetime as dt
import hashlib
import json
import os
import re
from pathlib import Path
from typing import Any

import phase1.validate_senior_experiment_config_manifest as v1


PROTOCOL = "senior-experiment-config-manifest-v2"
SOLVER_PROJECTION_SCHEMA = "resolved-solver-minus-run-paths-v1"
VOLATILE_SOLVER_FIELDS = {"exp_name", "checkpoint_path"}
CONFIG_FIELDS = {
    "client",
    "execution_timeout",
    "experiment_stratum_sha256",
    "generator_release",
    "hardware",
    "resolved_solver_config_sha256",
    "run_id",
    "solver_projection_schema",
    "task",
    "time_limit",
}


class ExportError(RuntimeError):
    """Raised when future producer config export must fail closed."""


def sha256_bytes(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def solver_projection(config: dict[str, Any]) -> dict[str, Any]:
    solver = config.get("solver")
    if not isinstance(solver, dict) or not solver:
        raise ExportError("dojo config has no resolved solver object")
    projected = copy.deepcopy(solver)
    for field in VOLATILE_SOLVER_FIELDS:
        projected.pop(field, None)
    if not projected:
        raise ExportError("resolved solver projection is empty")
    return projected


def resolved_solver_config_sha256(config: dict[str, Any]) -> str:
    try:
        encoded = v1.canonical_json(solver_projection(config)).encode("utf-8")
    except (TypeError, ValueError) as exc:
        raise ExportError("resolved solver projection is not finite canonical JSON") from exc
    if v1.CREDENTIAL.search(encoded):
        raise ExportError("credential-shaped bytes in resolved solver projection")
    return sha256_bytes(encoded)


def experiment_stratum_sha256(row: dict[str, Any]) -> str:
    payload = (
        row["task"],
        row["client"],
        row["generator_release"],
        row["hardware"],
        row["time_limit"],
        row["execution_timeout"],
        row["solver_projection_schema"],
        row["resolved_solver_config_sha256"],
    )
    try:
        encoded = json.dumps(
            payload,
            ensure_ascii=False,
            separators=(",", ":"),
            allow_nan=False,
        ).encode("utf-8")
    except (TypeError, ValueError) as exc:
        raise ExportError("experiment stratum is not finite canonical JSON") from exc
    return sha256_bytes(encoded)


def run_id_from_config(config: dict[str, Any]) -> str:
    source_id = config.get("id")
    launch_time = (config.get("metadata") or {}).get("launch_time")
    if not isinstance(source_id, str) or not source_id:
        raise ExportError("dojo config id is absent")
    if not isinstance(launch_time, str):
        raise ExportError("dojo config launch_time is absent")
    match = re.match(r"^(\d{4}-\d{2}-\d{2})", launch_time)
    if match is None:
        raise ExportError("dojo config launch_time has no ISO date")
    try:
        dt.date.fromisoformat(match.group(1))
    except ValueError as exc:
        raise ExportError("dojo config launch date is invalid") from exc
    run_id = f"{source_id}__{match.group(1)}"
    if v1.RUN_RE.fullmatch(run_id) is None:
        raise ExportError("derived physical run ID violates the future contract")
    return run_id


def uniform_operator_client(config: dict[str, Any]) -> str:
    operators = (config.get("solver") or {}).get("operators")
    if not isinstance(operators, dict) or not operators:
        raise ExportError("resolved solver operators are absent")
    clients: dict[str, str] = {}
    for operator, value in operators.items():
        if not isinstance(value, dict) or "llm" not in value:
            continue
        try:
            model_id = value["llm"]["client"]["model_id"]
        except (KeyError, TypeError) as exc:
            raise ExportError(f"operator client is malformed: {operator}") from exc
        if not isinstance(model_id, str) or not model_id:
            raise ExportError(f"operator client is invalid: {operator}")
        clients[str(operator)] = model_id
    if "draft" not in clients:
        raise ExportError("draft operator client is absent")
    if len(set(clients.values())) != 1:
        raise ExportError("operator clients are mixed; scalar client would be ambiguous")
    return clients["draft"]


def make_row(
    config: dict[str, Any],
    *,
    task: str,
    generator_release: str,
    hardware: str,
) -> dict[str, Any]:
    solver = config.get("solver")
    if not isinstance(solver, dict):
        raise ExportError("resolved solver is absent")
    try:
        time_limit = solver["time_limit_secs"]
        execution_timeout = solver["execution_timeout"]
    except KeyError as exc:
        raise ExportError("solver time limits are absent") from exc
    row: dict[str, Any] = {
        "client": uniform_operator_client(config),
        "execution_timeout": execution_timeout,
        "experiment_stratum_sha256": "0" * 64,
        "generator_release": generator_release,
        "hardware": hardware,
        "resolved_solver_config_sha256": resolved_solver_config_sha256(config),
        "run_id": run_id_from_config(config),
        "solver_projection_schema": SOLVER_PROJECTION_SCHEMA,
        "task": task,
        "time_limit": time_limit,
    }
    for field in ("task", "client", "generator_release", "hardware"):
        try:
            v1.public_value(row[field], field)
        except v1.ContractError as exc:
            raise ExportError(str(exc)) from exc
    try:
        v1.positive_number(time_limit, "time_limit")
        v1.positive_number(execution_timeout, "execution_timeout")
    except v1.ContractError as exc:
        raise ExportError(str(exc)) from exc
    row["experiment_stratum_sha256"] = experiment_stratum_sha256(row)
    return row


def load_dojo_config(path_value: str | Path) -> dict[str, Any]:
    unresolved = Path(path_value)
    if unresolved.is_symlink() or not unresolved.is_file():
        raise ExportError("dojo config is absent, non-regular, or symlinked")
    raw = unresolved.resolve().read_bytes()
    if v1.CREDENTIAL.search(raw):
        raise ExportError("credential-shaped bytes refused before dojo config parse")
    try:
        value = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise ExportError("dojo config is invalid JSON") from exc
    if not isinstance(value, dict):
        raise ExportError("dojo config root is not an object")
    return value


def write_row(path_value: str | Path, row: dict[str, Any]) -> None:
    unresolved = Path(path_value)
    if unresolved.is_symlink() or unresolved.exists():
        raise ExportError("output already exists or is symlinked")
    path = unresolved.resolve()
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(path.name + f".tmp-{os.getpid()}")
    if temporary.exists():
        raise ExportError("temporary output already exists")
    try:
        temporary.write_text(
            v1.canonical_json(row) + "\n", encoding="utf-8", newline="\n"
        )
        os.replace(temporary, path)
    finally:
        if temporary.exists():
            temporary.unlink()


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dojo-config", required=True)
    parser.add_argument("--task", required=True)
    parser.add_argument("--generator-release", required=True)
    parser.add_argument("--hardware", required=True)
    parser.add_argument("--output", required=True)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    try:
        row = make_row(
            load_dojo_config(args.dojo_config),
            task=args.task,
            generator_release=args.generator_release,
            hardware=args.hardware,
        )
        write_row(args.output, row)
    except (ExportError, OSError) as exc:
        print(f"SENIOR_CONFIG_V2_EXPORT_FAIL type={type(exc).__name__}", file=os.sys.stderr)
        return 2
    print(
        "SENIOR_CONFIG_V2_EXPORT_PASS "
        f"run_id={row['run_id']} solver_sha256={row['resolved_solver_config_sha256']}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
