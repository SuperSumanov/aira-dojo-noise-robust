"""Execute one hash-locked balanced-continuation rollout in a fresh workspace.

Only the deterministic synthetic backend is enabled in this gate.  The state machine and
artifact contract are intentionally backend-agnostic so a real aira-dojo adapter can be
added later without weakening exactly-K, no-replacement, or resume semantics.

Resume is fail-closed: a PENDING operation with no durable step receipt is ambiguous and is
never repeated automatically.  A durable receipt can be promoted without re-execution.
"""

from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import json
import math
import os
import pathlib
import platform
import re
import sys
import tempfile
import uuid
from typing import Any


ASSIGNMENT_PROTOCOL = "balanced-continuation-v1"
WORKER_SCHEMA = "balanced-continuation-worker-result-v1"
STATE_SCHEMA = "balanced-continuation-worker-state-v1"
STEP_SCHEMA = "balanced-continuation-worker-step-v1"
WORKSPACE_SCHEMA = "balanced-continuation-workspace-v1"
CODE_VAULT_SCHEMA = "balanced-continuation-code-vault-v1"
SYNTHETIC_SCHEMA = "balanced-continuation-synthetic-backend-v1"
SYNTHETIC_BACKEND = "deterministic-synthetic-v1"
HEX32 = re.compile(r"[0-9a-f]{32}\Z")
HEX64 = re.compile(r"[0-9a-f]{64}\Z")
HEX40 = re.compile(r"[0-9a-f]{40}\Z")
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
WORKSPACE_EXECUTION_KEYS = {
    "backend",
    "rollout_id",
    "execution_ordinal",
    "workspace_token",
    "output_code_sha256",
    "status",
}


class WorkerError(RuntimeError):
    pass


class InjectedCrash(RuntimeError):
    """Test-only crash after a durable receipt and before state promotion."""


def utc_now() -> str:
    return dt.datetime.now(dt.timezone.utc).isoformat(timespec="microseconds").replace("+00:00", "Z")


def canonical_json(value: Any) -> bytes:
    return json.dumps(
        value, sort_keys=True, separators=(",", ":"), ensure_ascii=False, allow_nan=False
    ).encode("utf-8")


def sha256_bytes(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def checked_bytes(path: pathlib.Path) -> bytes:
    raw = path.read_bytes()
    if CREDENTIAL.search(raw):
        raise WorkerError(f"credential-shaped bytes refused before parsing: {path.name}")
    return raw


def exact_keys(value: Any, keys: set[str], where: str) -> dict[str, Any]:
    if not isinstance(value, dict) or set(value) != keys:
        actual = set(value) if isinstance(value, dict) else set()
        raise WorkerError(
            f"{where} keys differ: missing={sorted(keys - actual)} unknown={sorted(actual - keys)}"
        )
    return value


def parse_json(raw: bytes, where: str) -> dict[str, Any]:
    try:
        value = json.loads(raw)
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise WorkerError(f"invalid JSON in {where}: {exc}") from exc
    if not isinstance(value, dict):
        raise WorkerError(f"expected JSON object in {where}")
    return value


def atomic_bytes(path: pathlib.Path, raw: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, temp_name = tempfile.mkstemp(prefix=f".{path.name}.", suffix=".tmp", dir=path.parent)
    temp = pathlib.Path(temp_name)
    try:
        with os.fdopen(fd, "wb") as handle:
            handle.write(raw)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temp, path)
    finally:
        if temp.exists():
            temp.unlink()


def atomic_json(path: pathlib.Path, value: Any) -> None:
    atomic_bytes(path, canonical_json(value) + b"\n")


def validate_sha(value: Any, where: str) -> str:
    if not isinstance(value, str) or not HEX64.fullmatch(value):
        raise WorkerError(f"invalid SHA-256 in {where}")
    return value


def validate_nonnegative_int(value: Any, where: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value < 0:
        raise WorkerError(f"{where} must be a non-negative integer")
    return value


def validate_artifact_manifest(result_dir: pathlib.Path) -> None:
    manifest_path = result_dir / "sha256_manifest.json"
    manifest = parse_json(checked_bytes(manifest_path), "assignment sha256_manifest")
    expected_names = {
        "anchors.input.jsonl",
        "assignment_manifest.jsonl",
        "command.txt",
        "execution_contract.input.json",
        "summary.json",
    }
    if set(manifest) != expected_names:
        raise WorkerError("assignment sha256_manifest has unexpected membership")
    for name, expected in manifest.items():
        validate_sha(expected, f"assignment manifest {name}")
        path = result_dir / name
        if not path.is_file() or sha256_bytes(path.read_bytes()) != expected:
            raise WorkerError(f"assignment artifact hash mismatch: {name}")


def load_assignment(result_dir: pathlib.Path, index: int) -> tuple[dict[str, Any], str, dict[str, Any]]:
    validate_artifact_manifest(result_dir)
    contract_raw = checked_bytes(result_dir / "execution_contract.input.json")
    contract = exact_keys(parse_json(contract_raw, "execution contract"), CONTRACT_KEYS, "execution contract")
    if contract["schema_version"] != "balanced-continuation-contract-v1":
        raise WorkerError("unsupported execution contract schema")
    if contract["workspace_policy"] != "fresh_per_rollout":
        raise WorkerError("execution contract does not require a fresh workspace")
    if contract["debug_policy"] != "fixed_one_operator_per_step":
        raise WorkerError("execution contract does not freeze one operator call per step")
    if not isinstance(contract["source_commit"], str) or not HEX40.fullmatch(contract["source_commit"]):
        raise WorkerError("invalid source_commit in execution contract")
    lines = checked_bytes(result_dir / "assignment_manifest.jsonl").splitlines()
    if index < 0 or index >= len(lines):
        raise WorkerError(f"assignment index {index} is outside [0, {len(lines)})")
    try:
        assignment = json.loads(lines[index])
    except json.JSONDecodeError as exc:
        raise WorkerError(f"invalid assignment JSON at index {index}") from exc
    exact_keys(assignment, ASSIGNMENT_KEYS, "assignment")
    if assignment["global_order"] != index:
        raise WorkerError("assignment global_order does not match selected index")
    if assignment["protocol"] != ASSIGNMENT_PROTOCOL:
        raise WorkerError("unsupported assignment protocol")
    for key in (
        "rollout_id",
        "block_id",
        "code_sha256",
        "anchor_contract_sha256",
        "execution_contract_sha256",
    ):
        validate_sha(assignment[key], f"assignment {key}")
    contract_sha = sha256_bytes(contract_raw)
    if assignment["execution_contract_sha256"] != contract_sha:
        raise WorkerError("assignment execution-contract hash mismatch")
    if assignment["continuation_horizon"] != contract["continuation_horizon"]:
        raise WorkerError("assignment horizon differs from execution contract")
    if assignment["warm_start_executions"] != 1:
        raise WorkerError("worker requires exactly one warm-start execution")
    if assignment["planned_continuation_executions"] != assignment["continuation_horizon"]:
        raise WorkerError("planned continuation count differs from horizon")
    return assignment, sha256_bytes(lines[index]), contract


def load_code_vault(path: pathlib.Path, assignment: dict[str, Any]) -> tuple[str, bytes]:
    raw = checked_bytes(path)
    selected: dict[str, Any] | None = None
    seen: set[str] = set()
    for line_number, line in enumerate(raw.splitlines(), 1):
        if not line.strip():
            continue
        try:
            row = json.loads(line)
        except json.JSONDecodeError as exc:
            raise WorkerError(f"invalid code-vault JSON at line {line_number}") from exc
        exact_keys(row, CODE_VAULT_ROW_KEYS, f"code-vault line {line_number}")
        sibling_id = row["sibling_id"]
        if not isinstance(sibling_id, str) or not sibling_id or sibling_id in seen:
            raise WorkerError("invalid or duplicate sibling_id in code vault")
        seen.add(sibling_id)
        if not isinstance(row["code"], str):
            raise WorkerError("code-vault code must be a string")
        code_raw = row["code"].encode("utf-8")
        code_sha = validate_sha(row["code_sha256"], "code-vault row")
        if sha256_bytes(code_raw) != code_sha:
            raise WorkerError(f"code-vault payload hash mismatch for {sibling_id}")
        if sibling_id == assignment["sibling_id"]:
            selected = row
    if selected is None:
        raise WorkerError("assigned sibling is absent from code vault")
    if selected["code_sha256"] != assignment["code_sha256"]:
        raise WorkerError("assigned code hash differs from code vault")
    return sha256_bytes(raw), selected["code"].encode("utf-8")


def finite_number(value: Any, where: str) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(float(value)):
        raise WorkerError(f"{where} must be finite numeric")
    return float(value)


def load_synthetic_spec(
    path: pathlib.Path, assignment: dict[str, Any]
) -> tuple[dict[str, Any], list[dict[str, Any]], str]:
    raw = checked_bytes(path)
    spec = exact_keys(parse_json(raw, "synthetic backend spec"), SYNTHETIC_KEYS, "synthetic backend spec")
    if spec["schema_version"] != SYNTHETIC_SCHEMA or spec["backend"] != SYNTHETIC_BACKEND:
        raise WorkerError("unsupported synthetic backend spec")
    lower = finite_number(spec["utility_min"], "utility_min")
    upper = finite_number(spec["utility_max"], "utility_max")
    failure = finite_number(spec["failure_utility"], "failure_utility")
    delta = finite_number(spec["practical_delta"], "practical_delta")
    if not lower < upper or not lower <= failure <= upper or delta < 0:
        raise WorkerError("invalid synthetic utility bounds/floor/delta")
    rollouts = spec["rollouts"]
    if not isinstance(rollouts, dict):
        raise WorkerError("synthetic rollouts must be an object")
    rollout_id = assignment["rollout_id"]
    outcomes = rollouts.get(rollout_id)
    expected_count = 1 + assignment["continuation_horizon"]
    if not isinstance(outcomes, list) or len(outcomes) != expected_count:
        raise WorkerError("synthetic outcome count differs from one plus horizon")
    parsed: list[dict[str, Any]] = []
    for ordinal, outcome in enumerate(outcomes):
        exact_keys(outcome, SYNTHETIC_OUTCOME_KEYS, f"synthetic outcome {ordinal}")
        status = outcome["status"]
        if status not in {"ok", "timeout", "invalid"}:
            raise WorkerError(f"unsupported synthetic status at ordinal {ordinal}")
        validate_nonnegative_int(outcome["wall_time_ms"], f"wall_time_ms {ordinal}")
        if not isinstance(outcome["is_buggy"], bool):
            raise WorkerError(f"is_buggy {ordinal} must be boolean")
        if status == "ok":
            utility = finite_number(outcome["utility"], f"utility {ordinal}")
            if not lower <= utility <= upper or outcome["is_buggy"]:
                raise WorkerError(f"inconsistent successful synthetic outcome {ordinal}")
        elif outcome["utility"] is not None or not outcome["is_buggy"]:
            raise WorkerError(f"inconsistent failed synthetic outcome {ordinal}")
        parsed.append(outcome)
    spec = {**spec, "utility_min": lower, "utility_max": upper, "failure_utility": failure, "practical_delta": delta}
    return spec, parsed, sha256_bytes(raw)


def ensure_existing_root(path: pathlib.Path, label: str) -> pathlib.Path:
    if not path.is_absolute():
        raise WorkerError(f"{label} must be absolute")
    resolved = path.resolve()
    if not resolved.is_dir() or resolved.is_symlink():
        raise WorkerError(f"{label} must be an existing non-symlink directory")
    return resolved


def create_workspace(
    workspace_root: pathlib.Path, assignment: dict[str, Any], assignment_sha: str
) -> tuple[pathlib.Path, str, str]:
    workspace = workspace_root / assignment["rollout_id"]
    if workspace.exists() or workspace.is_symlink():
        raise WorkerError("fresh workspace path already exists")
    workspace.mkdir()
    token = uuid.uuid4().hex
    marker = {
        "schema_version": WORKSPACE_SCHEMA,
        "rollout_id": assignment["rollout_id"],
        "assignment_line_sha256": assignment_sha,
        "workspace_token": token,
        "created_utc": utc_now(),
        "fresh_directory_created": True,
    }
    marker_path = workspace / "workspace_marker.json"
    atomic_json(marker_path, marker)
    return workspace, token, sha256_bytes(marker_path.read_bytes())


def validate_workspace(
    workspace: pathlib.Path, state: dict[str, Any], assignment_sha: str
) -> str:
    if workspace.resolve() != pathlib.Path(state["workspace_path"]).resolve():
        raise WorkerError("workspace path differs from checkpoint")
    marker_path = workspace / "workspace_marker.json"
    marker = exact_keys(
        parse_json(checked_bytes(marker_path), "workspace marker"), WORKSPACE_KEYS, "workspace marker"
    )
    if (
        marker["schema_version"] != WORKSPACE_SCHEMA
        or marker["rollout_id"] != state["rollout_id"]
        or marker["assignment_line_sha256"] != assignment_sha
        or marker["workspace_token"] != state["workspace_token"]
        or marker["fresh_directory_created"] is not True
    ):
        raise WorkerError("workspace marker differs from checkpoint")
    return sha256_bytes(marker_path.read_bytes())


def generated_code(previous: bytes, rollout_id: str, transition: int, operator: str) -> bytes:
    suffix = (
        f"\n# balanced-continuation synthetic transition={transition} "
        f"operator={operator} rollout={rollout_id}\n"
    ).encode("utf-8")
    return previous + suffix


def step_filename(ordinal: int) -> str:
    return f"step_{ordinal:03d}.json"


def code_filename(ordinal: int) -> str:
    return f"code_{ordinal:03d}.py"


def validate_state(state: Any, expected: dict[str, str], horizon: int) -> dict[str, Any]:
    state = exact_keys(state, STATE_KEYS, "worker state")
    if state["schema_version"] != STATE_SCHEMA:
        raise WorkerError("unsupported worker-state schema")
    for key, value in expected.items():
        if state[key] != value:
            raise WorkerError(f"worker-state identity mismatch: {key}")
    if state["phase"] not in {"READY", "PENDING", "FINALIZED"}:
        raise WorkerError("invalid worker-state phase")
    if not isinstance(state["workspace_path"], str) or not pathlib.Path(
        state["workspace_path"]
    ).is_absolute():
        raise WorkerError("checkpoint workspace path must be absolute")
    if not isinstance(state["workspace_token"], str) or not HEX32.fullmatch(
        state["workspace_token"]
    ):
        raise WorkerError("checkpoint workspace token is invalid")
    next_ordinal = validate_nonnegative_int(state["next_execution_ordinal"], "next_execution_ordinal")
    if next_ordinal > horizon + 1:
        raise WorkerError("next execution ordinal exceeds horizon")
    pending = state["pending_execution_ordinal"]
    if state["phase"] == "PENDING":
        if pending != next_ordinal:
            raise WorkerError("pending ordinal differs from next ordinal")
        if next_ordinal > horizon:
            raise WorkerError("pending ordinal exceeds continuation horizon")
    elif pending is not None:
        raise WorkerError("non-pending state carries pending ordinal")
    hashes = state["step_receipt_sha256s"]
    if not isinstance(hashes, list) or len(hashes) != next_ordinal:
        raise WorkerError("checkpoint step-hash count differs from next ordinal")
    for value in hashes:
        validate_sha(value, "checkpoint step receipt")
    return state


def execute_synthetic_step(
    assignment: dict[str, Any],
    ordinal: int,
    previous_step: dict[str, Any] | None,
    input_code: bytes,
    outcome: dict[str, Any],
    failure_utility: float,
    workspace: pathlib.Path,
    workspace_token: str,
) -> tuple[dict[str, Any], bytes]:
    if ordinal == 0:
        stage = "warm_start"
        transition = 0
        operator = "none"
        operator_calls = 0
        output_code = input_code
    else:
        stage = "continuation"
        transition = ordinal
        if previous_step is None:
            raise WorkerError("continuation step lacks prior execution")
        operator = "debug" if previous_step["is_buggy"] else "improve"
        operator_calls = 1
        output_code = generated_code(input_code, assignment["rollout_id"], transition, operator)
    execution_record = {
        "backend": SYNTHETIC_BACKEND,
        "rollout_id": assignment["rollout_id"],
        "execution_ordinal": ordinal,
        "workspace_token": workspace_token,
        "output_code_sha256": sha256_bytes(output_code),
        "status": outcome["status"],
    }
    execution_path = workspace / f"execution_{ordinal:03d}.json"
    if execution_path.exists():
        raise WorkerError("synthetic execution marker already exists; refusing replacement")
    atomic_json(execution_path, execution_record)
    raw_utility = outcome["utility"]
    effective = float(raw_utility) if raw_utility is not None else failure_utility
    receipt = {
        "schema_version": STEP_SCHEMA,
        "rollout_id": assignment["rollout_id"],
        "execution_ordinal": ordinal,
        "stage": stage,
        "transition_index": transition,
        "operator": operator,
        "operator_calls": operator_calls,
        "candidate_execution_attempted": True,
        "input_code_sha256": sha256_bytes(input_code),
        "output_code_sha256": sha256_bytes(output_code),
        "execution_status": outcome["status"],
        "raw_utility": raw_utility,
        "effective_utility": effective,
        "is_buggy": outcome["is_buggy"],
        "wall_time_ms": outcome["wall_time_ms"],
        "retry_count": 0,
        "replacement_count": 0,
        "workspace_token": workspace_token,
        "backend_receipt_sha256": sha256_bytes(execution_path.read_bytes()),
    }
    return receipt, output_code


def load_step(path: pathlib.Path, ordinal: int, rollout_id: str) -> dict[str, Any]:
    step = exact_keys(parse_json(checked_bytes(path), f"step receipt {ordinal}"), STEP_KEYS, "step receipt")
    if step["schema_version"] != STEP_SCHEMA or step["rollout_id"] != rollout_id:
        raise WorkerError("step receipt identity mismatch")
    if step["execution_ordinal"] != ordinal:
        raise WorkerError("step receipt ordinal mismatch")
    return step


def validate_recorded_step(
    inflight: pathlib.Path,
    workspace: pathlib.Path,
    assignment: dict[str, Any],
    ordinal: int,
    previous_code: bytes,
    previous_step: dict[str, Any] | None,
    outcome: dict[str, Any],
    failure_utility: float,
    workspace_token: str,
) -> tuple[dict[str, Any], bytes]:
    """Validate one already-paid execution without invoking the backend again."""
    if ordinal == 0:
        stage, transition, operator, operator_calls = "warm_start", 0, "none", 0
        expected_code = previous_code
    else:
        if previous_step is None:
            raise WorkerError("recorded continuation lacks its previous step")
        stage, transition, operator_calls = "continuation", ordinal, 1
        operator = "debug" if previous_step["is_buggy"] else "improve"
        expected_code = generated_code(previous_code, assignment["rollout_id"], ordinal, operator)
    code_path = inflight / code_filename(ordinal)
    receipt_path = inflight / step_filename(ordinal)
    execution_path = workspace / f"execution_{ordinal:03d}.json"
    for path, label in (
        (code_path, "recorded code"),
        (receipt_path, "step receipt"),
        (execution_path, "backend receipt"),
    ):
        if not path.is_file() or path.is_symlink():
            raise WorkerError(f"durable {label} is absent or symlinked")
    if checked_bytes(code_path) != expected_code:
        raise WorkerError(f"durable generated code differs at ordinal {ordinal}")
    execution = exact_keys(
        parse_json(checked_bytes(execution_path), "workspace execution"),
        WORKSPACE_EXECUTION_KEYS,
        "workspace execution",
    )
    expected_execution = {
        "backend": SYNTHETIC_BACKEND,
        "rollout_id": assignment["rollout_id"],
        "execution_ordinal": ordinal,
        "workspace_token": workspace_token,
        "output_code_sha256": sha256_bytes(expected_code),
        "status": outcome["status"],
    }
    if execution != expected_execution:
        raise WorkerError(f"durable backend receipt differs at ordinal {ordinal}")
    raw_utility = outcome["utility"]
    effective = float(raw_utility) if raw_utility is not None else failure_utility
    expected_receipt = {
        "schema_version": STEP_SCHEMA,
        "rollout_id": assignment["rollout_id"],
        "execution_ordinal": ordinal,
        "stage": stage,
        "transition_index": transition,
        "operator": operator,
        "operator_calls": operator_calls,
        "candidate_execution_attempted": True,
        "input_code_sha256": sha256_bytes(previous_code),
        "output_code_sha256": sha256_bytes(expected_code),
        "execution_status": outcome["status"],
        "raw_utility": raw_utility,
        "effective_utility": effective,
        "is_buggy": outcome["is_buggy"],
        "wall_time_ms": outcome["wall_time_ms"],
        "retry_count": 0,
        "replacement_count": 0,
        "workspace_token": workspace_token,
        "backend_receipt_sha256": sha256_bytes(execution_path.read_bytes()),
    }
    receipt = load_step(receipt_path, ordinal, assignment["rollout_id"])
    if receipt != expected_receipt:
        raise WorkerError(f"durable step receipt differs at ordinal {ordinal}")
    return receipt, expected_code


def validate_resume_prefix(
    inflight: pathlib.Path,
    workspace: pathlib.Path,
    state: dict[str, Any],
    assignment: dict[str, Any],
    initial_code: bytes,
    outcomes: list[dict[str, Any]],
    failure_utility: float,
) -> tuple[dict[str, Any] | None, bytes]:
    """Revalidate every completed step and its hash chain before further spending."""
    previous_step = None
    previous_code = initial_code
    completed = state["next_execution_ordinal"]
    for ordinal in range(completed):
        step, output_code = validate_recorded_step(
            inflight,
            workspace,
            assignment,
            ordinal,
            previous_code,
            previous_step,
            outcomes[ordinal],
            failure_utility,
            state["workspace_token"],
        )
        receipt_hash = sha256_bytes((inflight / step_filename(ordinal)).read_bytes())
        if receipt_hash != state["step_receipt_sha256s"][ordinal]:
            raise WorkerError(f"checkpoint receipt hash differs at ordinal {ordinal}")
        previous_step, previous_code = step, output_code
    return previous_step, previous_code


def validate_inflight_membership(
    inflight: pathlib.Path,
    workspace: pathlib.Path,
    completed: int,
    pending_durable: bool,
) -> None:
    last_ordinal = completed if pending_durable else completed - 1
    expected_inflight = {"state.json", "code_000.py"}
    if last_ordinal >= 0:
        expected_inflight.update(code_filename(i) for i in range(last_ordinal + 1))
        expected_inflight.update(step_filename(i) for i in range(last_ordinal + 1))
    entries = {path.name for path in inflight.iterdir()}
    if entries != expected_inflight or any(path.is_symlink() for path in inflight.iterdir()):
        raise WorkerError("inflight checkpoint contains missing, extra, or symlinked artifacts")
    expected_workspace = {"workspace_marker.json"}
    if last_ordinal >= 0:
        expected_workspace.update(f"execution_{i:03d}.json" for i in range(last_ordinal + 1))
    workspace_entries = {path.name for path in workspace.iterdir()}
    if workspace_entries != expected_workspace or any(
        path.is_symlink() for path in workspace.iterdir()
    ):
        raise WorkerError("workspace contains missing, extra, or symlinked resume artifacts")


def promote_durable_pending(
    inflight: pathlib.Path, state: dict[str, Any], assignment: dict[str, Any]
) -> dict[str, Any]:
    ordinal = state["pending_execution_ordinal"]
    receipt_path = inflight / step_filename(ordinal)
    code_path = inflight / code_filename(ordinal)
    if (
        not receipt_path.is_file()
        or receipt_path.is_symlink()
        or not code_path.is_file()
        or code_path.is_symlink()
    ):
        raise WorkerError(
            "AMBIGUOUS_PENDING_NO_DURABLE_RECEIPT: automatic re-execution is forbidden"
        )
    receipt = load_step(receipt_path, ordinal, assignment["rollout_id"])
    if sha256_bytes(code_path.read_bytes()) != receipt["output_code_sha256"]:
        raise WorkerError("durable pending code hash differs from step receipt")
    hashes = list(state["step_receipt_sha256s"])
    hashes.append(sha256_bytes(receipt_path.read_bytes()))
    state = {
        **state,
        "phase": "READY",
        "next_execution_ordinal": ordinal + 1,
        "pending_execution_ordinal": None,
        "step_receipt_sha256s": hashes,
    }
    atomic_json(inflight / "state.json", state)
    return state


def finalize(
    inflight: pathlib.Path,
    final: pathlib.Path,
    state: dict[str, Any],
    assignment: dict[str, Any],
    assignment_sha: str,
    contract: dict[str, Any],
    code_vault_sha: str,
    backend_spec_sha: str,
    backend_spec: dict[str, Any],
    workspace_marker_sha: str,
) -> dict[str, Any]:
    horizon = assignment["continuation_horizon"]
    steps = [load_step(inflight / step_filename(i), i, assignment["rollout_id"]) for i in range(horizon + 1)]
    warm = steps[0]["effective_utility"]
    continuation_values = [step["effective_utility"] for step in steps[1:]]
    best = max(continuation_values)
    result = {
        "schema_version": WORKER_SCHEMA,
        "status": "VERIFIED_SYNTHETIC_ROLLOUT_COMPLETE",
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
        "backend": SYNTHETIC_BACKEND,
        "workspace_path": state["workspace_path"],
        "workspace_token": state["workspace_token"],
        "workspace_marker_sha256": workspace_marker_sha,
        "warm_start_executions": 1,
        "continuation_executions": horizon,
        "candidate_execution_attempts": horizon + 1,
        "operator_calls": horizon,
        "retry_count": 0,
        "replacement_count": 0,
        "step_receipt_sha256s": state["step_receipt_sha256s"],
        "derived": {
            "warm_start_utility": warm,
            "best_within_h_utility": best,
            "gain_over_warm_start": best - warm,
            "exceeds_practical_delta": best - warm >= backend_spec["practical_delta"],
            "failure_utility": backend_spec["failure_utility"],
        },
        "software": {"python": platform.python_version(), "platform": platform.platform()},
    }
    atomic_json(inflight / "result.json", result)
    final_state = {**state, "phase": "FINALIZED", "pending_execution_ordinal": None}
    atomic_json(inflight / "state.json", final_state)
    files = sorted(path for path in inflight.iterdir() if path.is_file() and path.name != "sha256_manifest.json")
    hash_manifest = {path.name: sha256_bytes(path.read_bytes()) for path in files}
    atomic_json(inflight / "sha256_manifest.json", hash_manifest)
    if final.exists() or final.is_symlink():
        raise WorkerError("final rollout output already exists")
    inflight.replace(final)
    return result


def run_worker(args: argparse.Namespace, crash_after_receipt: int | None = None) -> dict[str, Any]:
    assignment_result = pathlib.Path(args.assignment_result).resolve()
    code_vault = pathlib.Path(args.code_vault).resolve()
    backend_spec_path = pathlib.Path(args.backend_spec).resolve()
    output_root = ensure_existing_root(pathlib.Path(args.output_root), "output_root")
    workspace_root = ensure_existing_root(pathlib.Path(args.workspace_root), "workspace_root")
    if output_root == workspace_root or output_root in workspace_root.parents or workspace_root in output_root.parents:
        raise WorkerError("output_root and workspace_root must be disjoint")
    assignment, assignment_sha, contract = load_assignment(assignment_result, args.index)
    code_vault_sha, initial_code = load_code_vault(code_vault, assignment)
    backend_spec, outcomes, backend_spec_sha = load_synthetic_spec(backend_spec_path, assignment)
    rollout_id = assignment["rollout_id"]
    final = output_root / rollout_id
    inflight = output_root / f".inflight-{rollout_id}"
    if final.exists() or final.is_symlink():
        raise WorkerError("rollout is already finalized; duplicate execution refused")
    expected_state = {
        "rollout_id": rollout_id,
        "assignment_line_sha256": assignment_sha,
        "execution_contract_sha256": assignment["execution_contract_sha256"],
        "code_vault_sha256": code_vault_sha,
        "backend_spec_sha256": backend_spec_sha,
        "source_commit": contract["source_commit"],
    }
    horizon = assignment["continuation_horizon"]
    if inflight.exists() or inflight.is_symlink():
        if inflight.is_symlink() or not inflight.is_dir():
            raise WorkerError("inflight rollout must be a non-symlink directory")
        if not args.resume:
            raise WorkerError("inflight rollout exists; explicit --resume is required")
        state = validate_state(
            parse_json(checked_bytes(inflight / "state.json"), "worker state"),
            expected_state,
            horizon,
        )
        workspace = pathlib.Path(state["workspace_path"])
        if workspace.parent.resolve() != workspace_root or workspace.name != rollout_id:
            raise WorkerError("checkpoint workspace is outside the frozen rollout root")
        if not workspace.is_dir() or workspace.is_symlink():
            raise WorkerError("checkpoint workspace is absent or symlinked")
        workspace_marker_sha = validate_workspace(workspace, state, assignment_sha)
        previous_step, previous_code = validate_resume_prefix(
            inflight,
            workspace,
            state,
            assignment,
            initial_code,
            outcomes,
            backend_spec["failure_utility"],
        )
        if state["phase"] == "PENDING":
            ordinal = state["pending_execution_ordinal"]
            receipt_path = inflight / step_filename(ordinal)
            code_path = inflight / code_filename(ordinal)
            if (
                not receipt_path.is_file()
                or receipt_path.is_symlink()
                or not code_path.is_file()
                or code_path.is_symlink()
            ):
                raise WorkerError(
                    "AMBIGUOUS_PENDING_NO_DURABLE_RECEIPT: automatic re-execution is forbidden"
                )
            validate_recorded_step(
                inflight,
                workspace,
                assignment,
                ordinal,
                previous_code,
                previous_step,
                outcomes[ordinal],
                backend_spec["failure_utility"],
                state["workspace_token"],
            )
            validate_inflight_membership(inflight, workspace, ordinal, True)
            state = promote_durable_pending(inflight, state, assignment)
        else:
            validate_inflight_membership(
                inflight, workspace, state["next_execution_ordinal"], False
            )
        if state["phase"] == "FINALIZED":
            raise WorkerError("inflight state says FINALIZED but was not atomically promoted")
    else:
        if args.resume:
            raise WorkerError("--resume requested but no inflight rollout exists")
        inflight.mkdir()
        workspace, workspace_token, workspace_marker_sha = create_workspace(
            workspace_root, assignment, assignment_sha
        )
        atomic_bytes(inflight / code_filename(0), initial_code)
        state = {
            "schema_version": STATE_SCHEMA,
            **expected_state,
            "workspace_path": str(workspace),
            "workspace_token": workspace_token,
            "phase": "READY",
            "next_execution_ordinal": 0,
            "pending_execution_ordinal": None,
            "step_receipt_sha256s": [],
        }
        atomic_json(inflight / "state.json", state)
    while state["next_execution_ordinal"] <= horizon:
        ordinal = state["next_execution_ordinal"]
        state = {
            **state,
            "phase": "PENDING",
            "pending_execution_ordinal": ordinal,
        }
        atomic_json(inflight / "state.json", state)
        input_path = inflight / code_filename(0 if ordinal == 0 else ordinal - 1)
        input_code = input_path.read_bytes()
        previous = None if ordinal == 0 else load_step(
            inflight / step_filename(ordinal - 1), ordinal - 1, rollout_id
        )
        receipt, output_code = execute_synthetic_step(
            assignment,
            ordinal,
            previous,
            input_code,
            outcomes[ordinal],
            backend_spec["failure_utility"],
            workspace,
            state["workspace_token"],
        )
        atomic_bytes(inflight / code_filename(ordinal), output_code)
        receipt_path = inflight / step_filename(ordinal)
        atomic_json(receipt_path, receipt)
        if crash_after_receipt == ordinal:
            raise InjectedCrash(f"injected crash after durable receipt {ordinal}")
        hashes = list(state["step_receipt_sha256s"])
        hashes.append(sha256_bytes(receipt_path.read_bytes()))
        state = {
            **state,
            "phase": "READY",
            "next_execution_ordinal": ordinal + 1,
            "pending_execution_ordinal": None,
            "step_receipt_sha256s": hashes,
        }
        atomic_json(inflight / "state.json", state)
    return finalize(
        inflight,
        final,
        state,
        assignment,
        assignment_sha,
        contract,
        code_vault_sha,
        backend_spec_sha,
        backend_spec,
        workspace_marker_sha,
    )


def parser() -> argparse.ArgumentParser:
    ap = argparse.ArgumentParser()
    ap.add_argument("--assignment-result", required=True)
    ap.add_argument("--code-vault", required=True)
    ap.add_argument("--backend-spec", required=True)
    ap.add_argument("--index", type=int, required=True)
    ap.add_argument("--output-root", required=True)
    ap.add_argument("--workspace-root", required=True)
    ap.add_argument("--resume", action="store_true")
    return ap


def main() -> int:
    try:
        result = run_worker(parser().parse_args())
    except (WorkerError, OSError) as exc:
        print(f"BALANCED_CONTINUATION_WORKER_REJECTED: {exc}", file=sys.stderr)
        return 2
    print(canonical_json(result).decode("utf-8"))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
