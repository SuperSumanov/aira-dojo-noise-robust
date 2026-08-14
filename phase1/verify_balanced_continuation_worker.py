"""Independently verify one synthetic balanced-continuation worker artifact.

This verifier intentionally does not import ``balanced_continuation_worker``.  It re-parses
the assignment, code vault, backend contract, state machine, workspace markers, generated
codes, per-step receipts, and final derivations from first principles.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import os
import pathlib
import re
import sys
import tempfile
from typing import Any


ASSIGNMENT_PROTOCOL = "balanced-continuation-v1"
WORKER_SCHEMA = "balanced-continuation-worker-result-v1"
STATE_SCHEMA = "balanced-continuation-worker-state-v1"
STEP_SCHEMA = "balanced-continuation-worker-step-v1"
WORKSPACE_SCHEMA = "balanced-continuation-workspace-v1"
SYNTHETIC_SCHEMA = "balanced-continuation-synthetic-backend-v1"
SYNTHETIC_BACKEND = "deterministic-synthetic-v1"
HEX64 = re.compile(r"[0-9a-f]{64}\Z")
CREDENTIAL = re.compile(
    rb"(?:^|[^A-Za-z0-9])(?:sk-[A-Za-z0-9._-]{16,}|hf_[A-Za-z0-9]{16,}|"
    rb"gh[pousr]_[A-Za-z0-9]{16,}|AKIA[0-9A-Z]{16}|AIza[0-9A-Za-z_-]{30,}|"
    rb"Bearer[ \t]+[A-Za-z0-9._-]{20,}|-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----)"
)

ASSIGNMENT_KEYS = {
    "protocol",
    "rollout_id",
    "global_order",
    "block_id",
    "block_replicate",
    "position_within_block",
    "inclusion_probability",
    "order_probability",
    "anchor_id",
    "task",
    "source_run_id",
    "parent_id",
    "sibling_id",
    "code_sha256",
    "anchor_contract_sha256",
    "execution_contract_sha256",
    "rollout_seed",
    "continuation_horizon",
    "warm_start_executions",
    "planned_continuation_executions",
}
CONTRACT_KEYS = {
    "schema_version",
    "model_id",
    "provider",
    "operator_config_sha256",
    "prompt_sha256",
    "source_commit",
    "dataset_contract_sha256",
    "evaluator_contract_sha256",
    "hardware_class",
    "execution_timeout_seconds",
    "continuation_horizon",
    "debug_policy",
    "workspace_policy",
    "temperature",
}
CODE_VAULT_ROW_KEYS = {"sibling_id", "code", "code_sha256"}
SYNTHETIC_KEYS = {
    "schema_version",
    "backend",
    "failure_utility",
    "utility_min",
    "utility_max",
    "practical_delta",
    "rollouts",
}
SYNTHETIC_OUTCOME_KEYS = {"status", "utility", "is_buggy", "wall_time_ms"}
STATE_KEYS = {
    "schema_version",
    "rollout_id",
    "assignment_line_sha256",
    "execution_contract_sha256",
    "code_vault_sha256",
    "backend_spec_sha256",
    "workspace_path",
    "workspace_token",
    "phase",
    "next_execution_ordinal",
    "pending_execution_ordinal",
    "step_receipt_sha256s",
    "source_commit",
}
STEP_KEYS = {
    "schema_version",
    "rollout_id",
    "execution_ordinal",
    "stage",
    "transition_index",
    "operator",
    "operator_calls",
    "candidate_execution_attempted",
    "input_code_sha256",
    "output_code_sha256",
    "execution_status",
    "raw_utility",
    "effective_utility",
    "is_buggy",
    "wall_time_ms",
    "retry_count",
    "replacement_count",
    "workspace_token",
    "backend_receipt_sha256",
}
WORKSPACE_KEYS = {
    "schema_version",
    "rollout_id",
    "assignment_line_sha256",
    "workspace_token",
    "created_utc",
    "fresh_directory_created",
}
RESULT_KEYS = {
    "schema_version",
    "status",
    "rollout_id",
    "global_order",
    "block_id",
    "block_replicate",
    "anchor_id",
    "task",
    "sibling_id",
    "rollout_seed",
    "assignment_line_sha256",
    "execution_contract_sha256",
    "code_vault_sha256",
    "backend_spec_sha256",
    "source_commit",
    "backend",
    "workspace_path",
    "workspace_token",
    "workspace_marker_sha256",
    "warm_start_executions",
    "continuation_executions",
    "candidate_execution_attempts",
    "operator_calls",
    "retry_count",
    "replacement_count",
    "step_receipt_sha256s",
    "derived",
    "software",
}
DERIVED_KEYS = {
    "warm_start_utility",
    "best_within_h_utility",
    "gain_over_warm_start",
    "exceeds_practical_delta",
    "failure_utility",
}
SOFTWARE_KEYS = {"python", "platform"}
WORKSPACE_EXECUTION_KEYS = {
    "backend",
    "rollout_id",
    "execution_ordinal",
    "workspace_token",
    "output_code_sha256",
    "status",
}


class VerifyError(RuntimeError):
    pass


def canonical_json(value: Any) -> bytes:
    return json.dumps(
        value, sort_keys=True, separators=(",", ":"), ensure_ascii=False, allow_nan=False
    ).encode("utf-8")


def sha256_bytes(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def checked_bytes(path: pathlib.Path) -> bytes:
    raw = path.read_bytes()
    if CREDENTIAL.search(raw):
        raise VerifyError(f"credential-shaped bytes refused before parsing: {path.name}")
    return raw


def parse_json(raw: bytes, where: str) -> dict[str, Any]:
    try:
        value = json.loads(raw)
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise VerifyError(f"invalid JSON in {where}: {exc}") from exc
    if not isinstance(value, dict):
        raise VerifyError(f"expected JSON object in {where}")
    return value


def exact_keys(value: Any, keys: set[str], where: str) -> dict[str, Any]:
    if not isinstance(value, dict) or set(value) != keys:
        actual = set(value) if isinstance(value, dict) else set()
        raise VerifyError(
            f"{where} keys differ: missing={sorted(keys - actual)} unknown={sorted(actual - keys)}"
        )
    return value


def validate_sha(value: Any, where: str) -> str:
    if not isinstance(value, str) or not HEX64.fullmatch(value):
        raise VerifyError(f"invalid SHA-256 in {where}")
    return value


def finite_number(value: Any, where: str) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(float(value)):
        raise VerifyError(f"{where} must be finite numeric")
    return float(value)


def atomic_json(path: pathlib.Path, value: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, temp_name = tempfile.mkstemp(prefix=f".{path.name}.", suffix=".tmp", dir=path.parent)
    temp = pathlib.Path(temp_name)
    try:
        with os.fdopen(fd, "wb") as handle:
            handle.write(canonical_json(value) + b"\n")
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temp, path)
    finally:
        if temp.exists():
            temp.unlink()


def validate_assignment_artifacts(result_dir: pathlib.Path) -> None:
    manifest = parse_json(
        checked_bytes(result_dir / "sha256_manifest.json"), "assignment sha256 manifest"
    )
    names = {
        "anchors.input.jsonl",
        "assignment_manifest.jsonl",
        "command.txt",
        "execution_contract.input.json",
        "summary.json",
    }
    if set(manifest) != names:
        raise VerifyError("assignment artifact membership differs")
    for name, digest in manifest.items():
        validate_sha(digest, f"assignment {name}")
        path = result_dir / name
        if not path.is_file() or sha256_bytes(path.read_bytes()) != digest:
            raise VerifyError(f"assignment artifact hash mismatch: {name}")


def load_assignment(
    result_dir: pathlib.Path, index: int
) -> tuple[dict[str, Any], str, dict[str, Any]]:
    validate_assignment_artifacts(result_dir)
    contract_raw = checked_bytes(result_dir / "execution_contract.input.json")
    contract = exact_keys(parse_json(contract_raw, "execution contract"), CONTRACT_KEYS, "execution contract")
    lines = checked_bytes(result_dir / "assignment_manifest.jsonl").splitlines()
    if index < 0 or index >= len(lines):
        raise VerifyError("result global_order is outside assignment manifest")
    try:
        assignment = json.loads(lines[index])
    except json.JSONDecodeError as exc:
        raise VerifyError("invalid assignment line") from exc
    exact_keys(assignment, ASSIGNMENT_KEYS, "assignment")
    if assignment["protocol"] != ASSIGNMENT_PROTOCOL or assignment["global_order"] != index:
        raise VerifyError("assignment protocol/order mismatch")
    contract_sha = sha256_bytes(contract_raw)
    if assignment["execution_contract_sha256"] != contract_sha:
        raise VerifyError("execution contract hash differs from assignment")
    return assignment, sha256_bytes(lines[index]), contract


def load_code(path: pathlib.Path, assignment: dict[str, Any]) -> tuple[str, bytes]:
    raw = checked_bytes(path)
    selected = None
    seen = set()
    for line_number, line in enumerate(raw.splitlines(), 1):
        if not line.strip():
            continue
        try:
            row = json.loads(line)
        except json.JSONDecodeError as exc:
            raise VerifyError(f"invalid code vault at line {line_number}") from exc
        exact_keys(row, CODE_VAULT_ROW_KEYS, f"code-vault line {line_number}")
        if row["sibling_id"] in seen:
            raise VerifyError("duplicate sibling in code vault")
        seen.add(row["sibling_id"])
        if not isinstance(row["code"], str):
            raise VerifyError("code-vault code is not string")
        code = row["code"].encode("utf-8")
        if sha256_bytes(code) != row["code_sha256"]:
            raise VerifyError("code-vault code hash mismatch")
        if row["sibling_id"] == assignment["sibling_id"]:
            selected = row
    if selected is None or selected["code_sha256"] != assignment["code_sha256"]:
        raise VerifyError("assigned code is absent or hash-mismatched")
    return sha256_bytes(raw), selected["code"].encode("utf-8")


def load_spec(
    path: pathlib.Path, assignment: dict[str, Any]
) -> tuple[dict[str, Any], list[dict[str, Any]], str]:
    raw = checked_bytes(path)
    spec = exact_keys(parse_json(raw, "backend spec"), SYNTHETIC_KEYS, "backend spec")
    if spec["schema_version"] != SYNTHETIC_SCHEMA or spec["backend"] != SYNTHETIC_BACKEND:
        raise VerifyError("unsupported backend spec")
    lower = finite_number(spec["utility_min"], "utility_min")
    upper = finite_number(spec["utility_max"], "utility_max")
    failure = finite_number(spec["failure_utility"], "failure_utility")
    delta = finite_number(spec["practical_delta"], "practical_delta")
    if not lower < upper or not lower <= failure <= upper or delta < 0:
        raise VerifyError("invalid backend utility contract")
    rollouts = spec["rollouts"]
    outcomes = rollouts.get(assignment["rollout_id"]) if isinstance(rollouts, dict) else None
    if not isinstance(outcomes, list) or len(outcomes) != 1 + assignment["continuation_horizon"]:
        raise VerifyError("backend outcome count differs from assignment")
    for ordinal, outcome in enumerate(outcomes):
        exact_keys(outcome, SYNTHETIC_OUTCOME_KEYS, f"backend outcome {ordinal}")
        if outcome["status"] == "ok":
            utility = finite_number(outcome["utility"], f"backend utility {ordinal}")
            if not lower <= utility <= upper or outcome["is_buggy"] is not False:
                raise VerifyError("inconsistent successful backend outcome")
        elif outcome["status"] in {"timeout", "invalid"}:
            if outcome["utility"] is not None or outcome["is_buggy"] is not True:
                raise VerifyError("inconsistent failed backend outcome")
        else:
            raise VerifyError("unknown backend outcome status")
        if isinstance(outcome["wall_time_ms"], bool) or not isinstance(outcome["wall_time_ms"], int) or outcome["wall_time_ms"] < 0:
            raise VerifyError("invalid backend wall time")
    parsed = {**spec, "failure_utility": failure, "practical_delta": delta}
    return parsed, outcomes, sha256_bytes(raw)


def generated_code(previous: bytes, rollout_id: str, transition: int, operator: str) -> bytes:
    return previous + (
        f"\n# balanced-continuation synthetic transition={transition} "
        f"operator={operator} rollout={rollout_id}\n"
    ).encode("utf-8")


def verify(args: argparse.Namespace) -> dict[str, Any]:
    artifact = pathlib.Path(args.artifact).resolve()
    if not artifact.is_dir() or artifact.is_symlink():
        raise VerifyError("artifact must be a non-symlink directory")
    result = exact_keys(
        parse_json(checked_bytes(artifact / "result.json"), "worker result"),
        RESULT_KEYS,
        "worker result",
    )
    if result["schema_version"] != WORKER_SCHEMA or result["status"] != "VERIFIED_SYNTHETIC_ROLLOUT_COMPLETE":
        raise VerifyError("worker result status/schema mismatch")
    if result["backend"] != SYNTHETIC_BACKEND or artifact.name != result["rollout_id"]:
        raise VerifyError("worker backend/artifact identity mismatch")
    assignment, assignment_sha, contract = load_assignment(
        pathlib.Path(args.assignment_result).resolve(), result["global_order"]
    )
    code_vault_sha, initial_code = load_code(pathlib.Path(args.code_vault).resolve(), assignment)
    spec, outcomes, backend_spec_sha = load_spec(pathlib.Path(args.backend_spec).resolve(), assignment)
    horizon = assignment["continuation_horizon"]
    expected_identity = {
        "rollout_id": assignment["rollout_id"],
        "global_order": assignment["global_order"],
        "block_id": assignment["block_id"],
        "block_replicate": assignment["block_replicate"],
        "anchor_id": assignment["anchor_id"],
        "task": assignment["task"],
        "sibling_id": assignment["sibling_id"],
        "rollout_seed": assignment["rollout_seed"],
        "assignment_line_sha256": assignment_sha,
        "execution_contract_sha256": assignment["execution_contract_sha256"],
        "code_vault_sha256": code_vault_sha,
        "backend_spec_sha256": backend_spec_sha,
        "source_commit": contract["source_commit"],
    }
    for key, expected in expected_identity.items():
        if result[key] != expected:
            raise VerifyError(f"worker result identity mismatch: {key}")
    state = exact_keys(
        parse_json(checked_bytes(artifact / "state.json"), "worker state"),
        STATE_KEYS,
        "worker state",
    )
    if (
        state["schema_version"] != STATE_SCHEMA
        or state["phase"] != "FINALIZED"
        or state["pending_execution_ordinal"] is not None
        or state["next_execution_ordinal"] != horizon + 1
    ):
        raise VerifyError("worker state is not exactly finalized")
    for key in (
        "rollout_id",
        "assignment_line_sha256",
        "execution_contract_sha256",
        "code_vault_sha256",
        "backend_spec_sha256",
        "source_commit",
        "workspace_path",
        "workspace_token",
    ):
        if state[key] != result[key]:
            raise VerifyError(f"state/result mismatch: {key}")
    manifest = parse_json(checked_bytes(artifact / "sha256_manifest.json"), "worker hash manifest")
    expected_files = {"state.json", "result.json"}
    expected_files.update(f"step_{i:03d}.json" for i in range(horizon + 1))
    expected_files.update(f"code_{i:03d}.py" for i in range(horizon + 1))
    if set(manifest) != expected_files:
        raise VerifyError("worker artifact hash-manifest membership differs")
    actual_files = {path.name for path in artifact.iterdir() if path.is_file()}
    if actual_files != expected_files | {"sha256_manifest.json"}:
        raise VerifyError("worker artifact contains missing or extra files")
    for name, digest in manifest.items():
        validate_sha(digest, f"worker artifact {name}")
        if sha256_bytes((artifact / name).read_bytes()) != digest:
            raise VerifyError(f"worker artifact hash mismatch: {name}")
    workspace = pathlib.Path(result["workspace_path"])
    if not workspace.is_dir() or workspace.is_symlink():
        raise VerifyError("recorded workspace is absent or symlinked")
    marker = exact_keys(
        parse_json(checked_bytes(workspace / "workspace_marker.json"), "workspace marker"),
        WORKSPACE_KEYS,
        "workspace marker",
    )
    if (
        marker["schema_version"] != WORKSPACE_SCHEMA
        or marker["rollout_id"] != result["rollout_id"]
        or marker["assignment_line_sha256"] != assignment_sha
        or marker["workspace_token"] != result["workspace_token"]
        or marker["fresh_directory_created"] is not True
        or sha256_bytes((workspace / "workspace_marker.json").read_bytes())
        != result["workspace_marker_sha256"]
    ):
        raise VerifyError("workspace marker differs from result")
    expected_workspace_files = {"workspace_marker.json"} | {
        f"execution_{i:03d}.json" for i in range(horizon + 1)
    }
    if {path.name for path in workspace.iterdir()} != expected_workspace_files:
        raise VerifyError("synthetic workspace contains carry-over or missing artifacts")
    previous_code = initial_code
    previous_step = None
    receipt_hashes = []
    steps = []
    for ordinal in range(horizon + 1):
        step_path = artifact / f"step_{ordinal:03d}.json"
        step = exact_keys(parse_json(checked_bytes(step_path), "step receipt"), STEP_KEYS, "step receipt")
        if step["schema_version"] != STEP_SCHEMA or step["rollout_id"] != result["rollout_id"]:
            raise VerifyError("step schema/rollout mismatch")
        if step["execution_ordinal"] != ordinal or step["transition_index"] != ordinal:
            raise VerifyError("step ordinal/transition mismatch")
        if ordinal == 0:
            expected_stage, expected_operator, expected_calls = "warm_start", "none", 0
            expected_code = previous_code
        else:
            expected_stage, expected_calls = "continuation", 1
            expected_operator = "debug" if previous_step["is_buggy"] else "improve"
            expected_code = generated_code(previous_code, result["rollout_id"], ordinal, expected_operator)
        if (
            step["stage"] != expected_stage
            or step["operator"] != expected_operator
            or step["operator_calls"] != expected_calls
            or step["candidate_execution_attempted"] is not True
            or step["input_code_sha256"] != sha256_bytes(previous_code)
            or step["output_code_sha256"] != sha256_bytes(expected_code)
            or step["retry_count"] != 0
            or step["replacement_count"] != 0
            or step["workspace_token"] != result["workspace_token"]
        ):
            raise VerifyError(f"step contract mismatch at ordinal {ordinal}")
        code_raw = checked_bytes(artifact / f"code_{ordinal:03d}.py")
        if code_raw != expected_code:
            raise VerifyError(f"generated code differs at ordinal {ordinal}")
        outcome = outcomes[ordinal]
        effective = float(outcome["utility"]) if outcome["utility"] is not None else spec["failure_utility"]
        if (
            step["execution_status"] != outcome["status"]
            or step["raw_utility"] != outcome["utility"]
            or not math.isclose(step["effective_utility"], effective, rel_tol=0, abs_tol=0)
            or step["is_buggy"] is not outcome["is_buggy"]
            or step["wall_time_ms"] != outcome["wall_time_ms"]
        ):
            raise VerifyError(f"step outcome differs at ordinal {ordinal}")
        execution_path = workspace / f"execution_{ordinal:03d}.json"
        execution = exact_keys(
            parse_json(checked_bytes(execution_path), "workspace execution"),
            WORKSPACE_EXECUTION_KEYS,
            "workspace execution",
        )
        if (
            execution["backend"] != SYNTHETIC_BACKEND
            or execution["rollout_id"] != result["rollout_id"]
            or execution["execution_ordinal"] != ordinal
            or execution["workspace_token"] != result["workspace_token"]
            or execution["output_code_sha256"] != sha256_bytes(expected_code)
            or execution["status"] != outcome["status"]
            or step["backend_receipt_sha256"] != sha256_bytes(execution_path.read_bytes())
        ):
            raise VerifyError(f"workspace execution differs at ordinal {ordinal}")
        receipt_hashes.append(sha256_bytes(step_path.read_bytes()))
        steps.append(step)
        previous_code = expected_code
        previous_step = step
    if state["step_receipt_sha256s"] != receipt_hashes or result["step_receipt_sha256s"] != receipt_hashes:
        raise VerifyError("step receipt hash chain differs")
    derived = exact_keys(result["derived"], DERIVED_KEYS, "derived result")
    exact_keys(result["software"], SOFTWARE_KEYS, "software result")
    warm = steps[0]["effective_utility"]
    best = max(step["effective_utility"] for step in steps[1:])
    gain = best - warm
    if (
        not math.isclose(derived["warm_start_utility"], warm, rel_tol=0, abs_tol=0)
        or not math.isclose(derived["best_within_h_utility"], best, rel_tol=0, abs_tol=0)
        or not math.isclose(derived["gain_over_warm_start"], gain, rel_tol=0, abs_tol=0)
        or derived["exceeds_practical_delta"] is not (gain >= spec["practical_delta"])
        or not math.isclose(derived["failure_utility"], spec["failure_utility"], rel_tol=0, abs_tol=0)
    ):
        raise VerifyError("derived rollout labels differ")
    if (
        result["warm_start_executions"] != 1
        or result["continuation_executions"] != horizon
        or result["candidate_execution_attempts"] != horizon + 1
        or result["operator_calls"] != horizon
        or result["retry_count"] != 0
        or result["replacement_count"] != 0
    ):
        raise VerifyError("final execution accounting differs")
    receipt = {
        "status": "VERIFIED_SYNTHETIC_BALANCED_CONTINUATION_ROLLOUT",
        "rollout_id": result["rollout_id"],
        "global_order": result["global_order"],
        "continuation_horizon": horizon,
        "candidate_execution_attempts": horizon + 1,
        "operator_calls": horizon,
        "retry_count": 0,
        "replacement_count": 0,
        "fresh_workspace_verified": True,
        "workspace_token": result["workspace_token"],
        "best_within_h_utility": best,
        "gain_over_warm_start": gain,
        "worker_sha256_manifest": sha256_bytes((artifact / "sha256_manifest.json").read_bytes()),
    }
    receipt_path = pathlib.Path(args.receipt).resolve()
    if receipt_path.exists():
        raise VerifyError("verification receipt already exists")
    atomic_json(receipt_path, receipt)
    return receipt


def parser() -> argparse.ArgumentParser:
    ap = argparse.ArgumentParser()
    ap.add_argument("--artifact", required=True)
    ap.add_argument("--assignment-result", required=True)
    ap.add_argument("--code-vault", required=True)
    ap.add_argument("--backend-spec", required=True)
    ap.add_argument("--receipt", required=True)
    return ap


def main() -> int:
    try:
        receipt = verify(parser().parse_args())
    except (VerifyError, OSError) as exc:
        print(f"BALANCED_CONTINUATION_VERIFY_REJECTED: {exc}", file=sys.stderr)
        return 2
    print(canonical_json(receipt).decode("utf-8"))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
