"""Fail-closed schemas for the future real balanced-continuation adapter.

This module does not execute a candidate, call an LLM, or open private labels.  It freezes
the process boundary that a real adapter must satisfy: an operator receives only deployment-
visible state, a public-only candidate executor emits an execution receipt, an external scorer
returns D_search only, and D_val is written to a separately sealed receipt.  D_test is never
read.  Keeping this contract independent of aira-dojo's current MCTS and in-process HCE paths
prevents their retries, extra analyze calls, and label visibility from entering E1 unnoticed.
"""

from __future__ import annotations

import hashlib
import json
import math
import re
from typing import Any


WORKER_CONTRACT_SCHEMA = "balanced-continuation-real-worker-contract-v1"
E2A_WORKER_CONTRACT_SCHEMA = "balanced-continuation-real-worker-contract-v2"
OPERATOR_REQUEST_SCHEMA = "balanced-continuation-operator-request-v1"
OPERATOR_RESPONSE_SCHEMA = "balanced-continuation-operator-response-v1"
EXECUTION_RECEIPT_SCHEMA = "balanced-continuation-public-execution-receipt-v1"
SEARCH_RECEIPT_SCHEMA = "balanced-continuation-dsearch-receipt-v1"
SEALED_LABEL_SCHEMA = "balanced-continuation-sealed-dval-receipt-v1"
VISIBLE_STEP_SCHEMA = "balanced-continuation-visible-step-v1"
REAL_BACKEND = "aira-dojo-external-v1"
HEX32 = re.compile(r"[0-9a-f]{32}\Z")
HEX40 = re.compile(r"[0-9a-f]{40}\Z")
HEX64 = re.compile(r"[0-9a-f]{64}\Z")
CREDENTIAL = re.compile(
    rb"(?:^|[^A-Za-z0-9])(?:sk-[A-Za-z0-9._-]{16,}|hf_[A-Za-z0-9]{16,}|"
    rb"gh[pousr]_[A-Za-z0-9]{16,}|AKIA[0-9A-Z]{16}|AIza[0-9A-Za-z_-]{30,}|"
    rb"Bearer[ \t]+[A-Za-z0-9._-]{20,}|-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----)"
)

WORKER_CONTRACT_KEYS = {
    "schema_version",
    "backend",
    "source_commit",
    "container_sha256",
    "operator_config_sha256",
    "prompt_sha256",
    "public_dataset_contract_sha256",
    "split_manifest_sha256_opaque",
    "search_evaluator_executable_sha256",
    "sealed_label_evaluator_executable_sha256",
    "public_data_root",
    "continuation_horizon",
    "operator_timeout_seconds",
    "execution_timeout_seconds",
    "evaluator_timeout_seconds",
    "operator_policy",
    "operator_calls_per_transition",
    "operator_retry_count",
    "execution_retry_count",
    "analyze_operator_calls",
    "workspace_policy",
    "candidate_mount_policy",
    "score_visibility",
    "sealed_label_policy",
    "split_policy",
    "dtest_policy",
}
E2A_WORKER_CONTRACT_KEYS = WORKER_CONTRACT_KEYS | {
    "hf_cache_path",
    "hf_cache_manifest_sha256",
    "hf_cache_payload_sha256",
}
VISIBLE_STEP_KEYS = {
    "schema_version",
    "rollout_id",
    "workspace_token",
    "task",
    "execution_ordinal",
    "stage",
    "operator",
    "code",
    "code_sha256",
    "execution_status",
    "process_started",
    "candidate_execution_attempted",
    "terminal_output",
    "terminal_output_sha256",
    "artifact_sha256",
    "submission_valid",
    "dsearch_score",
    "search_utility",
    "orientation",
    "is_buggy",
    "execution_receipt_sha256",
    "search_receipt_sha256",
    "sealed_label_receipt_sha256",
}
OPERATOR_REQUEST_KEYS = {
    "schema_version",
    "rollout_id",
    "transition_index",
    "task",
    "task_description",
    "previous_visible_step_sha256",
    "previous_code",
    "previous_code_sha256",
    "previous_terminal_output",
    "previous_execution_status",
    "previous_is_buggy",
    "previous_dsearch_score",
    "previous_search_utility",
    "operator",
    "operator_seed",
    "remaining_steps",
    "execution_timeout_seconds",
    "public_dataset_contract_sha256",
}
OPERATOR_RESPONSE_KEYS = {
    "schema_version",
    "rollout_id",
    "transition_index",
    "operator",
    "request_sha256",
    "raw_response_sha256",
    "extraction_status",
    "code",
    "code_sha256",
    "provider_request_id",
    "operator_calls",
    "retry_count",
}
EXECUTION_RECEIPT_KEYS = {
    "schema_version",
    "rollout_id",
    "workspace_token",
    "task",
    "execution_ordinal",
    "code_sha256",
    "execution_status",
    "process_started",
    "candidate_execution_attempted",
    "exit_code",
    "timed_out",
    "wall_time_seconds",
    "terminal_output",
    "terminal_output_sha256",
    "artifact_sha256",
    "public_data_read_only",
    "private_paths_mounted",
    "retry_count",
}
SEARCH_RECEIPT_KEYS = {
    "schema_version",
    "rollout_id",
    "workspace_token",
    "task",
    "execution_ordinal",
    "artifact_sha256",
    "submission_valid",
    "dsearch_score",
    "search_utility",
    "orientation",
    "split_manifest_sha256",
    "evaluator_executable_sha256",
    "grade_return_code",
    "private_bytes_exposed_to_candidate",
    "dtest_rows_read",
}
SEALED_LABEL_KEYS = {
    "schema_version",
    "rollout_id",
    "workspace_token",
    "task",
    "execution_ordinal",
    "artifact_sha256",
    "submission_valid",
    "dval_score",
    "dval_utility",
    "orientation",
    "split_manifest_sha256",
    "evaluator_executable_sha256",
    "grade_return_code",
    "private_bytes_exposed_to_candidate",
    "dtest_rows_read",
    "file_mode",
}


class RealContractError(RuntimeError):
    pass


def canonical_json(value: Any) -> bytes:
    return json.dumps(
        value, sort_keys=True, separators=(",", ":"), ensure_ascii=False, allow_nan=False
    ).encode("utf-8")


def sha256_bytes(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def exact_keys(value: Any, keys: set[str], where: str) -> dict[str, Any]:
    if not isinstance(value, dict) or set(value) != keys:
        actual = set(value) if isinstance(value, dict) else set()
        raise RealContractError(
            f"{where} keys differ: missing={sorted(keys - actual)} unknown={sorted(actual - keys)}"
        )
    return value


def require_string(value: Any, where: str) -> str:
    if not isinstance(value, str) or not value:
        raise RealContractError(f"{where} must be a non-empty string")
    return value


def require_sha(value: Any, where: str) -> str:
    if not isinstance(value, str) or not HEX64.fullmatch(value):
        raise RealContractError(f"{where} must be a lowercase SHA-256")
    return value


def require_nonnegative_int(value: Any, where: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value < 0:
        raise RealContractError(f"{where} must be a non-negative integer")
    return value


def require_bool(value: Any, where: str) -> bool:
    if not isinstance(value, bool):
        raise RealContractError(f"{where} must be boolean")
    return value


def require_posix_absolute_path(value: Any, where: str) -> str:
    raw = require_string(value, where)
    if "\\" in raw or "\x00" in raw or not raw.startswith("/"):
        raise RealContractError(f"{where} must be an absolute POSIX path")
    parts = raw.split("/")
    if raw == "/" or any(part in {".", ".."} for part in parts) or "//" in raw:
        raise RealContractError(f"{where} must be a canonical non-root POSIX path")
    return raw


def require_positive_number(value: Any, where: str) -> float:
    if (
        isinstance(value, bool)
        or not isinstance(value, (int, float))
        or not math.isfinite(float(value))
        or float(value) <= 0
    ):
        raise RealContractError(f"{where} must be a positive finite number")
    return float(value)


def optional_finite(value: Any, where: str) -> float | None:
    if value is None:
        return None
    if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(float(value)):
        raise RealContractError(f"{where} must be null or finite numeric")
    return float(value)


def reject_credential_shape(value: Any, where: str) -> None:
    try:
        raw = canonical_json(value)
    except (TypeError, ValueError) as exc:
        raise RealContractError(f"{where} is not canonical finite JSON") from exc
    if CREDENTIAL.search(raw):
        raise RealContractError(f"credential-shaped bytes refused in {where}")


def validate_worker_contract(value: Any) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise RealContractError("real worker contract must be an object")
    schema = value.get("schema_version")
    keys = (
        E2A_WORKER_CONTRACT_KEYS
        if schema == E2A_WORKER_CONTRACT_SCHEMA
        else WORKER_CONTRACT_KEYS
    )
    contract = exact_keys(value, keys, "real worker contract")
    reject_credential_shape(contract, "real worker contract")
    if schema not in {WORKER_CONTRACT_SCHEMA, E2A_WORKER_CONTRACT_SCHEMA} or contract[
        "backend"
    ] != REAL_BACKEND:
        raise RealContractError("unsupported real worker contract schema/backend")
    if not isinstance(contract["source_commit"], str) or not HEX40.fullmatch(contract["source_commit"]):
        raise RealContractError("source_commit must be a 40-character lowercase Git SHA")
    for key in (
        "container_sha256",
        "operator_config_sha256",
        "prompt_sha256",
        "public_dataset_contract_sha256",
        "split_manifest_sha256_opaque",
        "search_evaluator_executable_sha256",
        "sealed_label_evaluator_executable_sha256",
    ):
        require_sha(contract[key], key)
    if schema == E2A_WORKER_CONTRACT_SCHEMA:
        require_posix_absolute_path(contract["hf_cache_path"], "hf_cache_path")
        require_sha(contract["hf_cache_manifest_sha256"], "hf_cache_manifest_sha256")
        require_sha(contract["hf_cache_payload_sha256"], "hf_cache_payload_sha256")
    require_posix_absolute_path(contract["public_data_root"], "public_data_root")
    horizon = require_nonnegative_int(contract["continuation_horizon"], "continuation_horizon")
    if horizon < 1:
        raise RealContractError("continuation_horizon must be positive")
    for key in ("operator_timeout_seconds", "execution_timeout_seconds", "evaluator_timeout_seconds"):
        require_positive_number(contract[key], key)
    frozen = {
        "operator_policy": "debug_if_buggy_else_improve",
        "operator_calls_per_transition": 1,
        "operator_retry_count": 0,
        "execution_retry_count": 0,
        "analyze_operator_calls": 0,
        "workspace_policy": "fresh_per_rollout",
        "candidate_mount_policy": "public_read_only_no_private",
        "score_visibility": "D_search_only",
        "sealed_label_policy": "D_val_external_mode_0600",
        "split_policy": "80/10/10_D_train_D_search_D_val",
        "dtest_policy": "never_read",
    }
    for key, expected in frozen.items():
        if contract[key] != expected:
            raise RealContractError(f"real worker contract violates frozen {key}")
    return contract


def validate_execution_receipt(value: Any, contract: dict[str, Any]) -> dict[str, Any]:
    validate_worker_contract(contract)
    receipt = exact_keys(value, EXECUTION_RECEIPT_KEYS, "public execution receipt")
    reject_credential_shape(receipt, "public execution receipt")
    if receipt["schema_version"] != EXECUTION_RECEIPT_SCHEMA:
        raise RealContractError("unsupported public execution receipt schema")
    for key in ("rollout_id", "code_sha256"):
        require_sha(receipt[key], f"execution {key}")
    if not isinstance(receipt["workspace_token"], str) or not HEX32.fullmatch(receipt["workspace_token"]):
        raise RealContractError("execution workspace token is invalid")
    require_string(receipt["task"], "execution task")
    require_nonnegative_int(receipt["execution_ordinal"], "execution ordinal")
    if receipt["execution_status"] not in {
        "ok",
        "timeout",
        "execution_error",
        "invalid_format",
    }:
        raise RealContractError("unsupported public execution status")
    process_started = require_bool(receipt["process_started"], "execution process_started")
    if receipt["candidate_execution_attempted"] is not True:
        raise RealContractError("execution process/attempt flags are invalid")
    if receipt["execution_status"] == "invalid_format" and process_started is not False:
        raise RealContractError("invalid-format candidate must not start a process")
    if receipt["execution_status"] != "invalid_format" and process_started is not True:
        raise RealContractError("non-format execution must start a process")
    exit_code = receipt["exit_code"]
    if exit_code is not None and (isinstance(exit_code, bool) or not isinstance(exit_code, int)):
        raise RealContractError("execution exit_code must be integer or null")
    timed_out = require_bool(receipt["timed_out"], "execution timed_out")
    if (receipt["execution_status"] == "timeout") != timed_out:
        raise RealContractError("execution timeout status/flag differ")
    if receipt["execution_status"] == "ok" and exit_code != 0:
        raise RealContractError("successful execution must have exit code zero")
    if receipt["execution_status"] == "invalid_format" and (
        exit_code is not None or timed_out or receipt["artifact_sha256"] is not None
    ):
        raise RealContractError("invalid-format execution has process-only fields")
    require_positive_number(receipt["wall_time_seconds"], "execution wall time")
    if not isinstance(receipt["terminal_output"], str):
        raise RealContractError("terminal output must be a string")
    if sha256_bytes(receipt["terminal_output"].encode("utf-8")) != require_sha(
        receipt["terminal_output_sha256"], "terminal output hash"
    ):
        raise RealContractError("terminal output hash differs")
    if receipt["artifact_sha256"] is not None:
        require_sha(receipt["artifact_sha256"], "execution artifact hash")
    if receipt["public_data_read_only"] is not True or receipt["private_paths_mounted"] is not False:
        raise RealContractError("candidate execution mount isolation is violated")
    if require_nonnegative_int(receipt["retry_count"], "execution retry count") != 0:
        raise RealContractError("candidate execution retry is forbidden")
    return receipt


def validate_search_receipt(value: Any, contract: dict[str, Any]) -> dict[str, Any]:
    validate_worker_contract(contract)
    receipt = exact_keys(value, SEARCH_RECEIPT_KEYS, "D_search receipt")
    reject_credential_shape(receipt, "D_search receipt")
    if receipt["schema_version"] != SEARCH_RECEIPT_SCHEMA:
        raise RealContractError("unsupported D_search receipt schema")
    require_sha(receipt["rollout_id"], "D_search rollout_id")
    if not isinstance(receipt["workspace_token"], str) or not HEX32.fullmatch(receipt["workspace_token"]):
        raise RealContractError("D_search workspace token is invalid")
    require_string(receipt["task"], "D_search task")
    require_nonnegative_int(receipt["execution_ordinal"], "D_search ordinal")
    if receipt["artifact_sha256"] is not None:
        require_sha(receipt["artifact_sha256"], "D_search artifact hash")
    submission_valid = require_bool(receipt["submission_valid"], "submission_valid")
    score = optional_finite(receipt["dsearch_score"], "D_search score")
    utility = optional_finite(receipt["search_utility"], "search utility")
    if receipt["orientation"] not in {-1, 1}:
        raise RealContractError("D_search orientation must be -1 or 1")
    if submission_valid != (score is not None and utility is not None):
        raise RealContractError("D_search validity/score fields are inconsistent")
    if score is not None and not math.isclose(utility, receipt["orientation"] * score, rel_tol=0, abs_tol=0):
        raise RealContractError("search utility does not equal oriented D_search score")
    if receipt["split_manifest_sha256"] != contract["split_manifest_sha256_opaque"]:
        raise RealContractError("D_search split manifest differs from worker contract")
    if receipt["evaluator_executable_sha256"] != contract["search_evaluator_executable_sha256"]:
        raise RealContractError("D_search evaluator executable differs from worker contract")
    if isinstance(receipt["grade_return_code"], bool) or not isinstance(receipt["grade_return_code"], int):
        raise RealContractError("D_search grade return code must be integer")
    private_bytes = require_nonnegative_int(
        receipt["private_bytes_exposed_to_candidate"],
        "D_search private bytes exposed to candidate",
    )
    dtest_rows = require_nonnegative_int(receipt["dtest_rows_read"], "D_search D_test rows")
    if private_bytes != 0 or dtest_rows != 0:
        raise RealContractError("D_search scorer exposed private bytes or read D_test")
    return receipt


def validate_sealed_label_receipt(
    value: Any, contract_value: Any | None = None
) -> dict[str, Any]:
    contract = validate_worker_contract(contract_value) if contract_value is not None else None
    receipt = exact_keys(value, SEALED_LABEL_KEYS, "sealed D_val receipt")
    reject_credential_shape(receipt, "sealed D_val receipt")
    if receipt["schema_version"] != SEALED_LABEL_SCHEMA:
        raise RealContractError("unsupported sealed D_val receipt schema")
    require_sha(receipt["rollout_id"], "sealed rollout_id")
    if not isinstance(receipt["workspace_token"], str) or not HEX32.fullmatch(receipt["workspace_token"]):
        raise RealContractError("sealed workspace token is invalid")
    require_string(receipt["task"], "sealed task")
    require_nonnegative_int(receipt["execution_ordinal"], "sealed ordinal")
    if receipt["artifact_sha256"] is not None:
        require_sha(receipt["artifact_sha256"], "sealed artifact hash")
    submission_valid = require_bool(receipt["submission_valid"], "sealed submission_valid")
    score = optional_finite(receipt["dval_score"], "D_val score")
    utility = optional_finite(receipt["dval_utility"], "D_val utility")
    if receipt["orientation"] not in {-1, 1}:
        raise RealContractError("D_val orientation must be -1 or 1")
    if submission_valid != (score is not None and utility is not None):
        raise RealContractError("D_val validity/score fields are inconsistent")
    if score is not None and not math.isclose(utility, receipt["orientation"] * score, rel_tol=0, abs_tol=0):
        raise RealContractError("D_val utility does not equal oriented score")
    split_sha = require_sha(receipt["split_manifest_sha256"], "sealed split manifest")
    evaluator_sha = require_sha(
        receipt["evaluator_executable_sha256"], "sealed evaluator executable"
    )
    if contract is not None and split_sha != contract["split_manifest_sha256_opaque"]:
        raise RealContractError("sealed split manifest differs from worker contract")
    if (
        contract is not None
        and evaluator_sha != contract["sealed_label_evaluator_executable_sha256"]
    ):
        raise RealContractError("sealed evaluator executable differs from worker contract")
    if isinstance(receipt["grade_return_code"], bool) or not isinstance(
        receipt["grade_return_code"], int
    ):
        raise RealContractError("sealed grade return code must be integer")
    private_bytes = require_nonnegative_int(
        receipt["private_bytes_exposed_to_candidate"],
        "sealed private bytes exposed to candidate",
    )
    dtest_rows = require_nonnegative_int(receipt["dtest_rows_read"], "sealed D_test rows")
    file_mode = require_nonnegative_int(receipt["file_mode"], "sealed file mode")
    if private_bytes != 0 or dtest_rows != 0 or file_mode != 0o600:
        raise RealContractError("sealed label receipt read D_test or is not mode 0600")
    return receipt


def bind_visible_step(
    execution_value: Any,
    search_value: Any,
    contract_value: Any,
    *,
    stage: str,
    operator: str,
    code: str,
    sealed_label_receipt_sha256: str,
) -> dict[str, Any]:
    contract = validate_worker_contract(contract_value)
    execution = validate_execution_receipt(execution_value, contract)
    search = validate_search_receipt(search_value, contract)
    identity_keys = ("rollout_id", "workspace_token", "task", "execution_ordinal", "artifact_sha256")
    if any(execution[key] != search[key] for key in identity_keys):
        raise RealContractError("execution and D_search receipt identities differ")
    if sha256_bytes(code.encode("utf-8")) != execution["code_sha256"]:
        raise RealContractError("visible code differs from execution receipt")
    ordinal = execution["execution_ordinal"]
    if ordinal == 0:
        if stage != "warm_start" or operator != "none":
            raise RealContractError("ordinal zero must be a no-operator warm start")
    elif stage != "continuation" or operator not in {"improve", "debug"}:
        raise RealContractError("continuation stage/operator is invalid")
    sealed_sha = require_sha(sealed_label_receipt_sha256, "sealed label receipt hash")
    is_buggy = not (
        execution["execution_status"] == "ok"
        and search["submission_valid"] is True
        and search["dsearch_score"] is not None
    )
    visible = {
        "schema_version": VISIBLE_STEP_SCHEMA,
        "rollout_id": execution["rollout_id"],
        "workspace_token": execution["workspace_token"],
        "task": execution["task"],
        "execution_ordinal": ordinal,
        "stage": stage,
        "operator": operator,
        "code": code,
        "code_sha256": execution["code_sha256"],
        "execution_status": execution["execution_status"],
        "process_started": execution["process_started"],
        "candidate_execution_attempted": execution["candidate_execution_attempted"],
        "terminal_output": execution["terminal_output"],
        "terminal_output_sha256": execution["terminal_output_sha256"],
        "artifact_sha256": execution["artifact_sha256"],
        "submission_valid": search["submission_valid"],
        "dsearch_score": search["dsearch_score"],
        "search_utility": search["search_utility"],
        "orientation": search["orientation"],
        "is_buggy": is_buggy,
        "execution_receipt_sha256": sha256_bytes(canonical_json(execution)),
        "search_receipt_sha256": sha256_bytes(canonical_json(search)),
        "sealed_label_receipt_sha256": sealed_sha,
    }
    return validate_visible_step(visible, contract)


def validate_visible_step(value: Any, contract_value: Any | None = None) -> dict[str, Any]:
    contract = validate_worker_contract(contract_value) if contract_value is not None else None
    visible = exact_keys(value, VISIBLE_STEP_KEYS, "visible step")
    reject_credential_shape(visible, "visible step")
    if visible["schema_version"] != VISIBLE_STEP_SCHEMA:
        raise RealContractError("unsupported visible-step schema")
    require_sha(visible["rollout_id"], "visible rollout_id")
    if not isinstance(visible["workspace_token"], str) or not HEX32.fullmatch(
        visible["workspace_token"]
    ):
        raise RealContractError("visible workspace token is invalid")
    require_string(visible["task"], "visible task")
    ordinal = require_nonnegative_int(visible["execution_ordinal"], "visible ordinal")
    if contract is not None and ordinal > contract["continuation_horizon"]:
        raise RealContractError("visible ordinal exceeds continuation horizon")
    if ordinal == 0:
        if visible["stage"] != "warm_start" or visible["operator"] != "none":
            raise RealContractError("visible ordinal zero is not a no-operator warm start")
    elif visible["stage"] != "continuation" or visible["operator"] not in {"debug", "improve"}:
        raise RealContractError("visible continuation stage/operator is invalid")
    if not isinstance(visible["code"], str) or sha256_bytes(
        visible["code"].encode("utf-8")
    ) != require_sha(visible["code_sha256"], "visible code hash"):
        raise RealContractError("visible code/hash differs")
    if visible["execution_status"] not in {"ok", "timeout", "execution_error", "invalid_format"}:
        raise RealContractError("unsupported visible execution status")
    process_started = require_bool(visible["process_started"], "visible process_started")
    if visible["candidate_execution_attempted"] is not True:
        raise RealContractError("visible candidate attempt flag must be true")
    if (visible["execution_status"] == "invalid_format") == process_started:
        raise RealContractError("visible execution status/process flag differ")
    if not isinstance(visible["terminal_output"], str) or sha256_bytes(
        visible["terminal_output"].encode("utf-8")
    ) != require_sha(visible["terminal_output_sha256"], "visible terminal hash"):
        raise RealContractError("visible terminal output/hash differs")
    if visible["artifact_sha256"] is not None:
        require_sha(visible["artifact_sha256"], "visible artifact hash")
    submission_valid = require_bool(visible["submission_valid"], "visible submission_valid")
    score = optional_finite(visible["dsearch_score"], "visible D_search score")
    utility = optional_finite(visible["search_utility"], "visible search utility")
    if visible["orientation"] not in {-1, 1}:
        raise RealContractError("visible orientation must be -1 or 1")
    if submission_valid != (score is not None and utility is not None):
        raise RealContractError("visible validity/score fields are inconsistent")
    if score is not None and not math.isclose(
        utility, visible["orientation"] * score, rel_tol=0, abs_tol=0
    ):
        raise RealContractError("visible search utility is not the oriented score")
    expected_buggy = not (visible["execution_status"] == "ok" and submission_valid)
    if require_bool(visible["is_buggy"], "visible is_buggy") != expected_buggy:
        raise RealContractError("visible buggy flag differs from execution/search state")
    for key in (
        "execution_receipt_sha256",
        "search_receipt_sha256",
        "sealed_label_receipt_sha256",
    ):
        require_sha(visible[key], f"visible {key}")
    return visible


def build_operator_request(
    previous_visible_step: Any,
    contract_value: Any,
    *,
    task_description: str,
    transition_index: int,
    operator_seed: int,
) -> dict[str, Any]:
    contract = validate_worker_contract(contract_value)
    previous = validate_visible_step(previous_visible_step, contract)
    transition = require_nonnegative_int(transition_index, "transition index")
    if transition < 1 or transition > contract["continuation_horizon"]:
        raise RealContractError("transition index is outside the continuation horizon")
    if previous["execution_ordinal"] != transition - 1:
        raise RealContractError("operator request does not follow the previous execution")
    seed = require_nonnegative_int(operator_seed, "operator seed")
    operator = "debug" if previous["is_buggy"] else "improve"
    request = {
        "schema_version": OPERATOR_REQUEST_SCHEMA,
        "rollout_id": previous["rollout_id"],
        "transition_index": transition,
        "task": previous["task"],
        "task_description": require_string(task_description, "task description"),
        "previous_visible_step_sha256": sha256_bytes(canonical_json(previous)),
        "previous_code": previous["code"],
        "previous_code_sha256": previous["code_sha256"],
        "previous_terminal_output": previous["terminal_output"],
        "previous_execution_status": previous["execution_status"],
        "previous_is_buggy": previous["is_buggy"],
        "previous_dsearch_score": previous["dsearch_score"],
        "previous_search_utility": previous["search_utility"],
        "operator": operator,
        "operator_seed": seed,
        "remaining_steps": contract["continuation_horizon"] - transition + 1,
        "execution_timeout_seconds": contract["execution_timeout_seconds"],
        "public_dataset_contract_sha256": contract["public_dataset_contract_sha256"],
    }
    return validate_operator_request(request, contract)


def validate_operator_request(value: Any, contract_value: Any) -> dict[str, Any]:
    contract = validate_worker_contract(contract_value)
    request = exact_keys(value, OPERATOR_REQUEST_KEYS, "operator request")
    reject_credential_shape(request, "operator request")
    if request["schema_version"] != OPERATOR_REQUEST_SCHEMA:
        raise RealContractError("unsupported operator request schema")
    require_sha(request["rollout_id"], "operator request rollout_id")
    transition = require_nonnegative_int(request["transition_index"], "transition index")
    if transition < 1 or transition > contract["continuation_horizon"]:
        raise RealContractError("operator request transition is outside continuation horizon")
    require_string(request["task"], "operator request task")
    require_string(request["task_description"], "operator request task description")
    require_sha(request["previous_visible_step_sha256"], "previous visible-step hash")
    if not isinstance(request["previous_code"], str) or sha256_bytes(
        request["previous_code"].encode("utf-8")
    ) != require_sha(request["previous_code_sha256"], "previous code hash"):
        raise RealContractError("operator request previous code/hash differs")
    if not isinstance(request["previous_terminal_output"], str):
        raise RealContractError("operator request terminal output must be a string")
    if request["previous_execution_status"] not in {
        "ok",
        "timeout",
        "execution_error",
        "invalid_format",
    }:
        raise RealContractError("unsupported previous execution status")
    previous_buggy = require_bool(request["previous_is_buggy"], "previous_is_buggy")
    score = optional_finite(request["previous_dsearch_score"], "previous D_search score")
    utility = optional_finite(request["previous_search_utility"], "previous search utility")
    if (score is None) != (utility is None):
        raise RealContractError("operator request previous score/utility nullness differs")
    expected_buggy = not (request["previous_execution_status"] == "ok" and score is not None)
    if previous_buggy != expected_buggy:
        raise RealContractError("operator request buggy flag differs from visible state")
    expected_operator = "debug" if previous_buggy else "improve"
    if request["operator"] != expected_operator:
        raise RealContractError("operator request violates fixed debug/improve policy")
    require_nonnegative_int(request["operator_seed"], "operator seed")
    if request["remaining_steps"] != contract["continuation_horizon"] - transition + 1:
        raise RealContractError("operator request remaining_steps differs")
    if request["execution_timeout_seconds"] != contract["execution_timeout_seconds"]:
        raise RealContractError("operator request execution timeout differs")
    if request["public_dataset_contract_sha256"] != contract["public_dataset_contract_sha256"]:
        raise RealContractError("operator request public dataset contract differs")
    return request


def validate_operator_response(
    value: Any, request_value: Any, contract_value: Any
) -> dict[str, Any]:
    request = validate_operator_request(request_value, contract_value)
    response = exact_keys(value, OPERATOR_RESPONSE_KEYS, "operator response")
    reject_credential_shape(response, "operator response")
    if response["schema_version"] != OPERATOR_RESPONSE_SCHEMA:
        raise RealContractError("unsupported operator response schema")
    if (
        response["rollout_id"] != request["rollout_id"]
        or response["transition_index"] != request["transition_index"]
        or response["operator"] != request["operator"]
        or response["request_sha256"] != sha256_bytes(canonical_json(request))
    ):
        raise RealContractError("operator response identity/request binding differs")
    require_sha(response["raw_response_sha256"], "raw operator response hash")
    if response["extraction_status"] not in {"ok", "invalid_format"}:
        raise RealContractError("unsupported operator extraction status")
    if not isinstance(response["code"], str):
        raise RealContractError("operator code must be a string")
    if sha256_bytes(response["code"].encode("utf-8")) != require_sha(
        response["code_sha256"], "operator code hash"
    ):
        raise RealContractError("operator code hash differs")
    if response["extraction_status"] == "ok" and not response["code"]:
        raise RealContractError("successful operator extraction returned empty code")
    if response["extraction_status"] == "invalid_format" and response["code"]:
        raise RealContractError("invalid-format operator response must not invent code")
    if response["provider_request_id"] is not None and not isinstance(
        response["provider_request_id"], str
    ):
        raise RealContractError("provider request id must be string or null")
    if response["operator_calls"] != 1 or response["retry_count"] != 0:
        raise RealContractError("operator response violates one-call/no-retry policy")
    return response
