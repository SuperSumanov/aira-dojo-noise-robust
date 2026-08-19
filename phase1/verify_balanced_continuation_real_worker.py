"""Independent commitment-only verifier for one production E1 rollout.

This module deliberately does not import the production worker and never parses a sealed
D_val receipt.  It verifies the sealed file's mode and byte hash only; D_val values remain
unopened until the complete eight-rollout collection gate succeeds.
"""

from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import json
import os
import pathlib
import re
import stat
import subprocess
import sys
import tempfile
from typing import Any

from phase1.balanced_continuation_e1_scoring import (
    CREDENTIAL,
    evaluator_bundle_sha256 as e1_evaluator_bundle_sha256,
    file_sha256,
)
from phase1 import balanced_continuation_operator_entry as deepseek_operator
from phase1 import balanced_continuation_qwen_operator_entry as qwen_operator
from phase1.balanced_continuation_real_contract import (
    RealContractError,
    bind_visible_step,
    build_operator_request,
    canonical_json,
    sha256_bytes,
    validate_execution_receipt,
    validate_operator_response,
    validate_search_receipt,
    validate_visible_step,
    validate_worker_contract,
)


STATE_SCHEMA = "balanced-continuation-real-worker-state-v1"
RESULT_SCHEMA = "balanced-continuation-real-worker-result-v1"
WORKSPACE_SCHEMA = "balanced-continuation-real-workspace-v1"
INTENT_SCHEMA = "balanced-continuation-real-process-intent-v1"
STEP_MANIFEST_SCHEMA = "balanced-continuation-real-step-manifest-v1"
COMMITMENT_SCHEMA = "balanced-continuation-sealed-commitment-v1"
OPERATOR_USAGE_SCHEMA = "balanced-continuation-operator-usage-v1"
ASSIGNMENT_PROTOCOL = "balanced-continuation-v1"
HEX32 = re.compile(r"[0-9a-f]{32}\Z")
HEX40 = re.compile(r"[0-9a-f]{40}\Z")
HEX64 = re.compile(r"[0-9a-f]{64}\Z")
GIT_NO_LFS = [
    "-c", "filter.lfs.smudge=", "-c", "filter.lfs.process=",
    "-c", "filter.lfs.required=false",
]
ASSIGNMENT_KEYS = {
    "protocol", "rollout_id", "global_order", "block_id", "block_replicate",
    "position_within_block", "inclusion_probability", "order_probability", "anchor_id",
    "task", "source_run_id", "parent_id", "sibling_id", "code_sha256",
    "anchor_contract_sha256", "execution_contract_sha256", "rollout_seed",
    "continuation_horizon", "warm_start_executions", "planned_continuation_executions",
}
LEGACY_CONTRACT_KEYS = {
    "schema_version", "model_id", "provider", "operator_config_sha256", "prompt_sha256",
    "source_commit", "dataset_contract_sha256", "evaluator_contract_sha256",
    "hardware_class", "execution_timeout_seconds", "continuation_horizon", "debug_policy",
    "workspace_policy", "temperature",
}
STATE_KEYS = {
    "schema_version", "rollout_id", "assignment_line_sha256", "real_contract_sha256",
    "code_vault_sha256", "phase", "next_execution_ordinal", "pending_execution_ordinal",
    "workspace_path", "workspace_token", "started_utc",
    "completed_step_manifest_sha256s", "operator_calls", "candidate_execution_attempts",
}
RESULT_KEYS = {
    "schema_version", "status", "rollout_id", "global_order", "block_id",
    "block_replicate", "anchor_id", "task", "sibling_id", "source_run_id",
    "source_commit", "assignment_line_sha256", "real_contract_sha256",
    "workspace_path", "workspace_token", "started_utc", "ended_utc",
    "continuation_horizon", "execution_timeout_seconds", "candidate_network_policy",
    "candidate_execution_attempts", "candidate_processes_started", "operator_calls",
    "operator_retry_count", "candidate_retry_count", "analyze_operator_calls",
    "dtest_rows_read", "candidate_wall_time_seconds", "visible_dsearch_utilities",
    "sealed_dval_commitment_sha256s", "api_usage",
}
INTENT_KEYS = {
    "schema_version", "rollout_id", "execution_ordinal", "process_kind",
    "process_will_start", "command", "command_sha256", "created_utc", "retry_count",
}
USAGE_KEYS = {
    "schema_version", "model_id", "provider_request_id", "api_calls", "retry_count",
    "latency_seconds", "prompt_tokens", "completion_tokens", "total_tokens",
    "request_sha256", "rendered_prompt_sha256", "raw_response_sha256",
    "extraction_status",
}


class VerifyError(RuntimeError):
    pass


def operator_profile(real_contract: dict[str, Any]) -> dict[str, Any]:
    """Independently resolve an allow-listed operator from both frozen hashes."""
    candidates = (
        {
            "module": deepseek_operator,
            "model_id": deepseek_operator.MODEL_ID,
            "provider": "deepseek",
            "temperature": deepseek_operator.TEMPERATURE,
            "raw_response_schema": deepseek_operator.RAW_RESPONSE_SCHEMA,
        },
        {
            "module": qwen_operator,
            "model_id": qwen_operator.MODEL_ID,
            "provider": qwen_operator.PROVIDER,
            "temperature": qwen_operator.TEMPERATURE,
            "raw_response_schema": qwen_operator.RAW_RESPONSE_SCHEMA,
        },
    )
    matches = [
        profile for profile in candidates
        if real_contract["operator_config_sha256"]
        == profile["module"].operator_config_sha256()
        and real_contract["prompt_sha256"]
        == profile["module"].prompt_bundle_sha256()
    ]
    if len(matches) != 1:
        raise VerifyError("unsupported or mixed operator-profile hashes")
    return matches[0]


def evaluator_module_names(real_contract: dict[str, Any]) -> tuple[str, str]:
    """Independently allow-list one exact scorer/sealer bundle pair."""
    from phase1 import balanced_continuation_dsearch_eval as e1_search
    from phase1 import balanced_continuation_dval_sealer as e1_val
    from phase1 import balanced_continuation_e2a_dsearch_eval as e2a_search
    from phase1 import balanced_continuation_e2a_dval_sealer as e2a_val
    from phase1.balanced_continuation_e2a_scoring import (
        evaluator_bundle_sha256 as e2a_evaluator_bundle_sha256,
    )

    candidates = (
        (
            "phase1.balanced_continuation_dsearch_eval",
            "phase1.balanced_continuation_dval_sealer",
            e1_evaluator_bundle_sha256(pathlib.Path(e1_search.__file__)),
            e1_evaluator_bundle_sha256(pathlib.Path(e1_val.__file__)),
        ),
        (
            "phase1.balanced_continuation_e2a_dsearch_eval",
            "phase1.balanced_continuation_e2a_dval_sealer",
            e2a_evaluator_bundle_sha256(pathlib.Path(e2a_search.__file__)),
            e2a_evaluator_bundle_sha256(pathlib.Path(e2a_val.__file__)),
        ),
    )
    matches = [
        (search_name, val_name)
        for search_name, val_name, search_sha, val_sha in candidates
        if real_contract["search_evaluator_executable_sha256"] == search_sha
        and real_contract["sealed_label_evaluator_executable_sha256"] == val_sha
    ]
    if len(matches) != 1:
        raise VerifyError("unsupported or mixed evaluator-profile hashes")
    return matches[0]


def checked(path: pathlib.Path) -> dict[str, Any]:
    raw = path.read_bytes()
    if CREDENTIAL.search(raw):
        raise VerifyError(f"credential-shaped bytes refused: {path.name}")
    value = json.loads(raw)
    if not isinstance(value, dict):
        raise VerifyError(f"expected JSON object: {path}")
    return value


def read_jsonl_bytes(path: pathlib.Path) -> list[tuple[bytes, dict[str, Any]]]:
    raw = path.read_bytes()
    if CREDENTIAL.search(raw):
        raise VerifyError(f"credential-shaped bytes refused: {path.name}")
    output = []
    for line_number, line in enumerate(raw.splitlines(), 1):
        value = json.loads(line)
        if not isinstance(value, dict):
            raise VerifyError(f"JSONL row is not an object at line {line_number}")
        output.append((line, value))
    return output


def exact_keys(value: Any, keys: set[str], where: str) -> dict[str, Any]:
    if not isinstance(value, dict) or set(value) != keys:
        raise VerifyError(f"{where} keys differ")
    return value


def parse_time(value: Any, where: str) -> dt.datetime:
    try:
        parsed = dt.datetime.fromisoformat(value.replace("Z", "+00:00"))
    except (AttributeError, ValueError) as exc:
        raise VerifyError(f"{where} timestamp differs") from exc
    if parsed.tzinfo is None:
        raise VerifyError(f"{where} timestamp lacks timezone")
    return parsed


def recursive_hashes(root: pathlib.Path, exclude: set[str] | None = None) -> dict[str, str]:
    exclude = exclude or set()
    return {
        path.relative_to(root).as_posix(): file_sha256(path)
        for path in sorted(root.rglob("*"))
        if path.is_file() and path.relative_to(root).as_posix() not in exclude
    }


def evaluator_contract_sha(real: dict[str, Any]) -> str:
    return sha256_bytes(canonical_json({
        "split_manifest_sha256_opaque": real["split_manifest_sha256_opaque"],
        "search_evaluator_executable_sha256": real["search_evaluator_executable_sha256"],
        "sealed_label_evaluator_executable_sha256": real[
            "sealed_label_evaluator_executable_sha256"
        ],
        "score_visibility": real["score_visibility"],
        "sealed_label_policy": real["sealed_label_policy"],
    }))


def load_assignment(
    root: pathlib.Path, index: int
) -> tuple[dict[str, Any], str, dict[str, Any]]:
    expected_files = {
        "anchors.input.jsonl", "assignment_manifest.jsonl", "command.txt",
        "execution_contract.input.json", "summary.json", "sha256_manifest.json",
    }
    if not root.is_dir() or root.is_symlink() or {p.name for p in root.iterdir()} != expected_files:
        raise VerifyError("assignment result file set differs")
    manifest = checked(root / "sha256_manifest.json")
    if set(manifest) != expected_files - {"sha256_manifest.json"}:
        raise VerifyError("assignment hash manifest membership differs")
    for name, digest in manifest.items():
        if not isinstance(digest, str) or not HEX64.fullmatch(digest):
            raise VerifyError("assignment hash manifest value differs")
        if file_sha256(root / name) != digest:
            raise VerifyError(f"assignment hash differs: {name}")
    rows = read_jsonl_bytes(root / "assignment_manifest.jsonl")
    if index < 0 or index >= len(rows):
        raise VerifyError("assignment index is outside the manifest")
    line, assignment = rows[index]
    exact_keys(assignment, ASSIGNMENT_KEYS, "assignment")
    if (
        assignment["protocol"] != ASSIGNMENT_PROTOCOL
        or assignment["global_order"] != index
        or assignment["continuation_horizon"] != 1
        or assignment["warm_start_executions"] != 1
        or assignment["planned_continuation_executions"] != 1
    ):
        raise VerifyError("assignment frozen E1 counters differ")
    for key in ("rollout_id", "block_id", "code_sha256", "anchor_contract_sha256"):
        if not isinstance(assignment[key], str) or not HEX64.fullmatch(assignment[key]):
            raise VerifyError(f"assignment {key} differs")
    legacy_raw = (root / "execution_contract.input.json").read_bytes()
    if CREDENTIAL.search(legacy_raw):
        raise VerifyError("credential-shaped bytes in legacy contract")
    legacy = exact_keys(json.loads(legacy_raw), LEGACY_CONTRACT_KEYS, "legacy contract")
    if assignment["execution_contract_sha256"] != sha256_bytes(legacy_raw):
        raise VerifyError("assignment legacy-contract binding differs")
    return assignment, sha256_bytes(line), legacy


def load_initial_code(path: pathlib.Path, assignment: dict[str, Any]) -> tuple[str, str]:
    selected = None
    seen: set[str] = set()
    for _, row in read_jsonl_bytes(path):
        if set(row) != {"sibling_id", "code", "code_sha256"}:
            raise VerifyError("code-vault schema differs")
        sibling = row["sibling_id"]
        code = row["code"]
        digest = row["code_sha256"]
        if not isinstance(sibling, str) or sibling in seen or not isinstance(code, str):
            raise VerifyError("code-vault identity differs")
        seen.add(sibling)
        if sha256_bytes(code.encode("utf-8")) != digest:
            raise VerifyError("code-vault code hash differs")
        if sibling == assignment["sibling_id"]:
            selected = code
    if selected is None or sha256_bytes(selected.encode("utf-8")) != assignment["code_sha256"]:
        raise VerifyError("assignment code is absent from the code vault")
    return selected, file_sha256(path)


def validate_contract_pair(
    legacy: dict[str, Any], real: dict[str, Any], split_root: pathlib.Path
) -> None:
    profile = operator_profile(real)
    expected = {
        "schema_version": "balanced-continuation-contract-v1",
        "model_id": profile["model_id"],
        "provider": profile["provider"],
        "operator_config_sha256": real["operator_config_sha256"],
        "prompt_sha256": real["prompt_sha256"],
        "source_commit": real["source_commit"],
        "dataset_contract_sha256": real["public_dataset_contract_sha256"],
        "evaluator_contract_sha256": evaluator_contract_sha(real),
        "hardware_class": "single-rtx3090-24gb",
        "execution_timeout_seconds": real["execution_timeout_seconds"],
        "continuation_horizon": real["continuation_horizon"],
        "debug_policy": "fixed_one_operator_per_step",
        "workspace_policy": "fresh_per_rollout",
        "temperature": profile["temperature"],
    }
    if legacy != expected:
        raise VerifyError("legacy and real contracts differ in meaning")
    summary = checked(split_root / "summary.json")
    if (
        real["public_data_root"] != (split_root / "public").resolve().as_posix()
        or summary.get("public_dataset_contract_sha256")
        != real["public_dataset_contract_sha256"]
        or summary.get("split_manifest_sha256_opaque")
        != real["split_manifest_sha256_opaque"]
        or summary.get("dtest_rows_read") != 0
    ):
        raise VerifyError("split and real contract binding differs")


def validate_intent(
    path: pathlib.Path,
    assignment: dict[str, Any],
    ordinal: int,
    kind: str,
    will_start: bool,
) -> list[str]:
    value = exact_keys(checked(path), INTENT_KEYS, f"{kind} intent")
    command = value["command"]
    if (
        value["schema_version"] != INTENT_SCHEMA
        or value["rollout_id"] != assignment["rollout_id"]
        or value["execution_ordinal"] != ordinal
        or value["process_kind"] != kind
        or value["process_will_start"] is not will_start
        or value["retry_count"] != 0
        or not isinstance(command, list)
        or any(not isinstance(item, str) for item in command)
        or value["command_sha256"] != sha256_bytes("\0".join(command).encode("utf-8"))
    ):
        raise VerifyError(f"{kind} process intent differs")
    parse_time(value["created_utc"], f"{kind} intent")
    return command


def validate_process(path: pathlib.Path, stdout: pathlib.Path, stderr: pathlib.Path) -> dict[str, Any]:
    value = checked(path)
    required = {
        "started_utc", "ended_utc", "wall_time_seconds", "return_code", "timed_out",
        "stdout_sha256", "stderr_sha256", "stdout_capture", "stderr_capture",
    }
    exact_keys(value, required, "candidate process")
    if (
        value["stdout_sha256"] != file_sha256(stdout)
        or value["stderr_sha256"] != file_sha256(stderr)
        or not isinstance(value["return_code"], int)
        or isinstance(value["return_code"], bool)
        or not isinstance(value["timed_out"], bool)
        or not isinstance(value["wall_time_seconds"], (int, float))
        or isinstance(value["wall_time_seconds"], bool)
        or value["wall_time_seconds"] <= 0
    ):
        raise VerifyError("candidate process receipt differs")
    if parse_time(value["ended_utc"], "candidate end") < parse_time(
        value["started_utc"], "candidate start"
    ):
        raise VerifyError("candidate process ended before start")
    for label in ("stdout_capture", "stderr_capture"):
        capture = value[label]
        if (
            not isinstance(capture, dict)
            or set(capture) != {"total_bytes", "truncated", "full_sha256"}
            or not isinstance(capture["total_bytes"], int)
            or isinstance(capture["total_bytes"], bool)
            or capture["total_bytes"] < 0
            or not isinstance(capture["truncated"], bool)
            or not isinstance(capture["full_sha256"], str)
            or not HEX64.fullmatch(capture["full_sha256"])
        ):
            raise VerifyError("candidate bounded-log capture differs")
    return value


def validate_sidecar_process(path: pathlib.Path, stdout: pathlib.Path, stderr: pathlib.Path) -> None:
    value = checked(path)
    if set(value) != {
        "return_code", "timed_out", "wall_time_seconds", "stdout_sha256", "stderr_sha256"
    }:
        raise VerifyError("sidecar process receipt schema differs")
    if (
        value["return_code"] != 0
        or value["timed_out"] is not False
        or not isinstance(value["wall_time_seconds"], (int, float))
        or isinstance(value["wall_time_seconds"], bool)
        or value["wall_time_seconds"] <= 0
        or value["stdout_sha256"] != file_sha256(stdout)
        or value["stderr_sha256"] != file_sha256(stderr)
    ):
        raise VerifyError("sidecar process receipt differs")


def validate_usage(
    value: dict[str, Any], request: dict[str, Any], response: dict[str, Any],
    real_contract: dict[str, Any],
) -> None:
    profile = operator_profile(real_contract)
    exact_keys(value, USAGE_KEYS, "operator usage")
    if (
        value["schema_version"] != OPERATOR_USAGE_SCHEMA
        or value["model_id"] != profile["model_id"]
        or value["provider_request_id"] != response["provider_request_id"]
        or value["api_calls"] != 1
        or value["retry_count"] != 0
        or value["request_sha256"] != sha256_bytes(canonical_json(request))
        or value["raw_response_sha256"] != response["raw_response_sha256"]
        or value["extraction_status"] != response["extraction_status"]
        or not isinstance(value["rendered_prompt_sha256"], str)
        or not HEX64.fullmatch(value["rendered_prompt_sha256"])
    ):
        raise VerifyError("operator usage binding differs")
    tokens = [value["prompt_tokens"], value["completion_tokens"], value["total_tokens"]]
    if any(
        item is not None
        and (not isinstance(item, int) or isinstance(item, bool) or item < 0)
        for item in tokens
    ):
        raise VerifyError("operator token accounting differs")
    if all(isinstance(item, int) and not isinstance(item, bool) for item in tokens):
        if tokens[0] + tokens[1] != tokens[2]:
            raise VerifyError("operator total token accounting differs")


def atomic_json(path: pathlib.Path, value: Any) -> None:
    if path.exists() or path.is_symlink():
        raise VerifyError("verification receipt must be new")
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, name = tempfile.mkstemp(prefix=f".{path.name}.", suffix=".tmp", dir=path.parent)
    temporary = pathlib.Path(name)
    try:
        with os.fdopen(fd, "wb") as handle:
            handle.write(canonical_json(value) + b"\n")
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary, path)
    finally:
        if temporary.exists():
            temporary.unlink()


def verify(args: argparse.Namespace) -> dict[str, Any]:
    assignment_root = pathlib.Path(args.assignment_result).resolve()
    artifact = pathlib.Path(args.artifact).resolve()
    code_vault = pathlib.Path(args.code_vault).resolve()
    contract_path = pathlib.Path(args.real_contract).resolve()
    split_root = pathlib.Path(args.split_root).resolve()
    workspace_root = pathlib.Path(args.workspace_root).resolve()
    sealed_root = pathlib.Path(args.sealed_root).resolve()
    container = pathlib.Path(args.container).resolve()
    hf_cache = pathlib.Path(args.hf_cache).resolve()
    nvfix = pathlib.Path(args.nvfix_dir).resolve()
    source_root = pathlib.Path(args.source_root).resolve()
    assignment, line_sha, legacy = load_assignment(assignment_root, args.index)
    initial_code, code_vault_sha = load_initial_code(code_vault, assignment)
    real_raw = contract_path.read_bytes()
    if CREDENTIAL.search(real_raw):
        raise VerifyError("credential-shaped bytes in real contract")
    real = validate_worker_contract(json.loads(real_raw))
    real_sha = sha256_bytes(real_raw)
    if not source_root.is_dir() or source_root.is_symlink():
        raise VerifyError("exact source root differs")
    source_head = subprocess.run(
        ["git", *GIT_NO_LFS, "rev-parse", "HEAD"], cwd=source_root, check=True,
        stdout=subprocess.PIPE, stderr=subprocess.PIPE,
    ).stdout.decode("ascii").strip()
    source_dirty = subprocess.run(
        ["git", *GIT_NO_LFS, "status", "--porcelain"], cwd=source_root, check=True,
        stdout=subprocess.PIPE, stderr=subprocess.PIPE,
    ).stdout
    if source_head != real["source_commit"] or source_dirty:
        raise VerifyError("source root is not the exact clean contract commit")
    validate_contract_pair(legacy, real, split_root)
    profile = operator_profile(real)
    dsearch_module, dval_module = evaluator_module_names(real)
    if file_sha256(container) != real["container_sha256"]:
        raise VerifyError("container hash differs")
    if not hf_cache.is_dir() or not nvfix.is_dir():
        raise VerifyError("HF/NVIDIA helper root differs")
    if artifact.name != assignment["rollout_id"] or artifact.parent.name == "":
        raise VerifyError("rollout artifact identity differs")
    if not artifact.is_dir() or artifact.is_symlink():
        raise VerifyError("rollout artifact root differs")
    if {path.name for path in artifact.iterdir()} != {
        "real_contract.json", "result.json", "sha256_manifest.json", "state.json", "steps"
    }:
        raise VerifyError("rollout top-level file set differs")
    if (artifact / "real_contract.json").read_bytes() != real_raw:
        raise VerifyError("rollout copy of real contract differs")
    top_manifest = checked(artifact / "sha256_manifest.json")
    if top_manifest != recursive_hashes(artifact, {"sha256_manifest.json"}):
        raise VerifyError("rollout top hash manifest differs")
    state = exact_keys(checked(artifact / "state.json"), STATE_KEYS, "worker state")
    if (
        state["schema_version"] != STATE_SCHEMA
        or state["rollout_id"] != assignment["rollout_id"]
        or state["assignment_line_sha256"] != line_sha
        or state["real_contract_sha256"] != real_sha
        or state["code_vault_sha256"] != code_vault_sha
        or state["phase"] != "FINALIZED"
        or state["next_execution_ordinal"] != 2
        or state["pending_execution_ordinal"] is not None
        or state["operator_calls"] != 1
        or state["candidate_execution_attempts"] != 2
        or not isinstance(state["workspace_token"], str)
        or not HEX32.fullmatch(state["workspace_token"])
    ):
        raise VerifyError("final worker state differs")
    parse_time(state["started_utc"], "worker start")
    workspace = pathlib.Path(state["workspace_path"]).resolve()
    if workspace.parent != workspace_root or workspace.name != assignment["rollout_id"]:
        raise VerifyError("rollout workspace escaped its frozen root")
    marker = checked(workspace / "workspace_marker.json")
    if (
        set(marker) != {
            "schema_version", "rollout_id", "assignment_line_sha256", "workspace_token",
            "created_utc", "fresh_directory_created",
        }
        or marker["schema_version"] != WORKSPACE_SCHEMA
        or marker["rollout_id"] != assignment["rollout_id"]
        or marker["assignment_line_sha256"] != line_sha
        or marker["workspace_token"] != state["workspace_token"]
        or marker["fresh_directory_created"] is not True
        or not (workspace / "candidate").is_dir()
        or (workspace / "candidate").is_symlink()
    ):
        raise VerifyError("fresh workspace marker differs")
    parse_time(marker["created_utc"], "workspace creation")

    step_root = artifact / "steps"
    expected_steps = {f"step_{ordinal:03d}" for ordinal in range(2)}
    if not step_root.is_dir() or {path.name for path in step_root.iterdir()} != expected_steps:
        raise VerifyError("rollout step directory set differs")
    visible_steps: list[dict[str, Any]] = []
    candidate_walls: list[float] = []
    manifest_shas: list[str] = []
    usages: list[dict[str, Any]] = []
    commitments: list[str] = []
    sealed_rollout = sealed_root / assignment["rollout_id"]
    if not sealed_rollout.is_dir() or sealed_rollout.is_symlink():
        raise VerifyError("sealed rollout root differs")
    if os.name == "posix" and stat.S_IMODE(sealed_rollout.stat().st_mode) != 0o700:
        raise VerifyError("sealed rollout root is not mode 0700")
    expected_sealed = {f"dval_{ordinal:03d}.json" for ordinal in range(2)}
    if {path.name for path in sealed_rollout.iterdir()} != expected_sealed:
        raise VerifyError("sealed rollout file set differs")

    previous: dict[str, Any] | None = None
    for ordinal in range(2):
        step = step_root / f"step_{ordinal:03d}"
        step_manifest = checked(step / "step_manifest.json")
        if (
            set(step_manifest) != {"schema_version", "rollout_id", "execution_ordinal", "files"}
            or step_manifest["schema_version"] != STEP_MANIFEST_SCHEMA
            or step_manifest["rollout_id"] != assignment["rollout_id"]
            or step_manifest["execution_ordinal"] != ordinal
            or step_manifest["files"] != recursive_hashes(step, {"step_manifest.json"})
        ):
            raise VerifyError(f"step manifest differs at ordinal {ordinal}")
        manifest_shas.append(file_sha256(step / "step_manifest.json"))
        code = (step / "code.py").read_text(encoding="utf-8")
        execution = validate_execution_receipt(checked(step / "execution.json"), real)
        if (
            execution["rollout_id"] != assignment["rollout_id"]
            or execution["workspace_token"] != state["workspace_token"]
            or execution["task"] != assignment["task"]
            or execution["execution_ordinal"] != ordinal
            or execution["code_sha256"] != sha256_bytes(code.encode("utf-8"))
        ):
            raise VerifyError("execution receipt identity differs")
        candidate_command = validate_intent(
            step / "candidate_intent.json",
            assignment,
            ordinal,
            "candidate",
            execution["process_started"],
        )
        if execution["process_started"]:
            required_flags = (
                "--containall", "--cleanenv", "--net", "--network", "none", "--no-home",
                "--no-mount", "bind-paths", "--no-eval",
            )
            if (
                candidate_command[:2] != ["singularity", "exec"]
                or any(flag not in candidate_command for flag in required_flags)
                or candidate_command[candidate_command.index("--network") + 1] != "none"
                or candidate_command[candidate_command.index("--no-mount") + 1] != "bind-paths"
                or str(container) not in candidate_command
            ):
                raise VerifyError("candidate network/container command differs")
            bind_values = [
                candidate_command[index + 1]
                for index, item in enumerate(candidate_command[:-1])
                if item == "--bind"
            ]
            combined = ",".join(bind_values)
            required_mounts = (
                f"{workspace / 'candidate'}:/workspace",
                f"{split_root / 'public' / assignment['task']}:/workspace/data:ro",
                f"{hf_cache}:/hf:ro",
                f"{nvfix}:/mnt:ro",
            )
            if any(mount not in combined for mount in required_mounts):
                raise VerifyError("candidate public-only mount contract differs")
            lowered = combined.lower()
            if any(word in lowered for word in ("/private", "dsearch", "dval", "answer")):
                raise VerifyError("candidate command contains a private-label mount")
            process = validate_process(
                step / "candidate_process.json",
                step / "candidate.stdout",
                step / "candidate.stderr",
            )
            if (
                process["return_code"] != execution["exit_code"]
                or process["timed_out"] != execution["timed_out"]
                or process["wall_time_seconds"] != execution["wall_time_seconds"]
            ):
                raise VerifyError("candidate process/execution receipt differs")
            expected_terminal = (
                "[stdout tail]\n"
                + (step / "candidate.stdout").read_bytes()[-32768:].decode(
                    "utf-8", errors="replace"
                )
                + "\n[stderr tail]\n"
                + (step / "candidate.stderr").read_bytes()[-32768:].decode(
                    "utf-8", errors="replace"
                )
            )
            if execution["terminal_output"] != expected_terminal:
                raise VerifyError("candidate terminal evidence differs from bounded logs")
        elif candidate_command:
            raise VerifyError("invalid-format candidate unexpectedly has a command")
        elif execution["terminal_output"] != (
            "operator response did not contain an executable code block\n"
        ):
            raise VerifyError("invalid-format terminal evidence differs")
        candidate_walls.append(execution["wall_time_seconds"])
        submission = step / "submission.csv"
        if execution["artifact_sha256"] is None:
            if submission.exists() or submission.is_symlink():
                raise VerifyError("null-artifact execution retained a submission")
        elif not submission.is_file() or submission.is_symlink() or file_sha256(
            submission
        ) != execution["artifact_sha256"]:
            raise VerifyError("candidate submission artifact differs")

        for label, expected_module in (
            ("dsearch", dsearch_module), ("dval_sealer", dval_module)
        ):
            sidecar_command = validate_intent(
                step / f"{label}_intent.json", assignment, ordinal, label, True
            )
            if (
                len(sidecar_command) < 3
                or sidecar_command[0] != sys.executable
                or sidecar_command[1:3] != ["-m", expected_module]
            ):
                raise VerifyError(f"{label} evaluator module command differs")
            validate_sidecar_process(
                step / f"{label}_process.json",
                step / f"{label}.stdout",
                step / f"{label}.stderr",
            )
        search = validate_search_receipt(checked(step / "dsearch.json"), real)
        for key in ("rollout_id", "workspace_token", "task", "execution_ordinal", "artifact_sha256"):
            if search[key] != execution[key]:
                raise VerifyError("D_search and execution identities differ")
        commitment = checked(step / "dval_commitment.json")
        if (
            set(commitment) != {
                "schema_version", "rollout_id", "workspace_token", "task",
                "execution_ordinal", "sealed_label_receipt_sha256",
            }
            or commitment["schema_version"] != COMMITMENT_SCHEMA
            or commitment["rollout_id"] != assignment["rollout_id"]
            or commitment["workspace_token"] != state["workspace_token"]
            or commitment["task"] != assignment["task"]
            or commitment["execution_ordinal"] != ordinal
            or not isinstance(commitment["sealed_label_receipt_sha256"], str)
            or not HEX64.fullmatch(commitment["sealed_label_receipt_sha256"])
        ):
            raise VerifyError("sealed D_val commitment differs")
        if (step / "dval_sealer.stdout").read_bytes() != canonical_json(commitment) + b"\n":
            raise VerifyError("D_val sealer stdout is not the exact commitment")
        sealed_path = sealed_rollout / f"dval_{ordinal:03d}.json"
        if not sealed_path.is_file() or sealed_path.is_symlink():
            raise VerifyError("sealed D_val receipt path differs")
        if os.name == "posix" and stat.S_IMODE(sealed_path.stat().st_mode) != 0o600:
            raise VerifyError("sealed D_val receipt is not mode 0600")
        # Byte hashing is allowed here; the JSON value is deliberately never parsed.
        if file_sha256(sealed_path) != commitment["sealed_label_receipt_sha256"]:
            raise VerifyError("sealed D_val commitment hash differs")
        commitments.append(commitment["sealed_label_receipt_sha256"])

        if ordinal == 0:
            if code != initial_code:
                raise VerifyError("warm-start code differs from the frozen code vault")
            if any((step / name).exists() for name in (
                "operator_request.json", "operator_response.json", "operator_raw_response.json",
                "operator_usage.json",
            )):
                raise VerifyError("warm-start unexpectedly contains operator artifacts")
            operator = "none"
        else:
            if previous is None:
                raise VerifyError("continuation lacks a previous visible step")
            request = checked(step / "operator_request.json")
            description_path = split_root / "public" / assignment["task"] / "description.md"
            instructions_path = (
                source_root / "src" / "dojo" / "tasks" / "mlebench" / "instructions.txt"
            )
            description = instructions_path.read_text(encoding="utf-8") + "\n" + description_path.read_text(
                encoding="utf-8"
            )
            expected_request = build_operator_request(
                previous,
                real,
                task_description=description,
                transition_index=ordinal,
                operator_seed=assignment["rollout_seed"] + ordinal,
            )
            if request != expected_request:
                raise VerifyError("operator request chain differs")
            response = validate_operator_response(checked(step / "operator_response.json"), request, real)
            if response["code"] != code:
                raise VerifyError("operator response code differs from executed code")
            raw_document = checked(step / "operator_raw_response.json")
            if (
                set(raw_document) != {
                    "schema_version", "request_sha256", "raw_response_sha256", "raw_response"
                }
                or raw_document["schema_version"] != profile["raw_response_schema"]
                or raw_document["request_sha256"] != response["request_sha256"]
                or raw_document["raw_response_sha256"] != response["raw_response_sha256"]
                or not isinstance(raw_document["raw_response"], str)
                or sha256_bytes(raw_document["raw_response"].encode("utf-8"))
                != response["raw_response_sha256"]
            ):
                raise VerifyError("raw operator response binding differs")
            validate_intent(step / "operator_intent.json", assignment, ordinal, "operator", True)
            validate_sidecar_process(
                step / "operator_process.json",
                step / "operator.stdout",
                step / "operator.stderr",
            )
            usage = checked(step / "operator_usage.json")
            validate_usage(usage, request, response, real)
            usages.append(usage)
            operator = response["operator"]
        visible = validate_visible_step(checked(step / "visible.json"), real)
        expected_visible = bind_visible_step(
            execution,
            search,
            real,
            stage="warm_start" if ordinal == 0 else "continuation",
            operator=operator,
            code=code,
            sealed_label_receipt_sha256=commitment["sealed_label_receipt_sha256"],
        )
        if visible != expected_visible:
            raise VerifyError("visible step binding differs")
        visible_steps.append(visible)
        previous = visible

    if state["completed_step_manifest_sha256s"] != manifest_shas:
        raise VerifyError("worker state step-manifest chain differs")
    result = exact_keys(checked(artifact / "result.json"), RESULT_KEYS, "worker result")
    expected_result = {
        "schema_version": RESULT_SCHEMA,
        "status": "COMPLETE_REAL_BALANCED_CONTINUATION_ROLLOUT",
        "rollout_id": assignment["rollout_id"],
        "global_order": assignment["global_order"],
        "block_id": assignment["block_id"],
        "block_replicate": assignment["block_replicate"],
        "anchor_id": assignment["anchor_id"],
        "task": assignment["task"],
        "sibling_id": assignment["sibling_id"],
        "source_run_id": assignment["source_run_id"],
        "source_commit": real["source_commit"],
        "assignment_line_sha256": line_sha,
        "real_contract_sha256": real_sha,
        "workspace_path": str(workspace),
        "workspace_token": state["workspace_token"],
        "started_utc": state["started_utc"],
        "continuation_horizon": 1,
        "execution_timeout_seconds": 600,
        "candidate_network_policy": "singularity-network-none",
        "candidate_execution_attempts": 2,
        "candidate_processes_started": sum(step["process_started"] for step in visible_steps),
        "operator_calls": 1,
        "operator_retry_count": 0,
        "candidate_retry_count": 0,
        "analyze_operator_calls": 0,
        "dtest_rows_read": 0,
        "candidate_wall_time_seconds": candidate_walls,
        "visible_dsearch_utilities": [step["search_utility"] for step in visible_steps],
        "sealed_dval_commitment_sha256s": commitments,
        "api_usage": usages,
    }
    if any(result.get(key) != value for key, value in expected_result.items()):
        raise VerifyError("worker result identity/counters differ")
    if parse_time(result["ended_utc"], "rollout end") < parse_time(
        result["started_utc"], "rollout start"
    ):
        raise VerifyError("rollout result ended before start")
    raw_result = canonical_json(result)
    if b"dval_score" in raw_result or b"dval_utility" in raw_result:
        raise VerifyError("D_val value leaked into worker result")
    receipt = {
        "schema_version": "balanced-continuation-real-worker-verification-v1",
        "status": "VERIFIED_REAL_E1_ROLLOUT_COMMITMENT_ONLY",
        "worker_imported": False,
        "sealed_values_opened": False,
        "rollout_id": assignment["rollout_id"],
        "global_order": assignment["global_order"],
        "block_id": assignment["block_id"],
        "block_replicate": assignment["block_replicate"],
        "task": assignment["task"],
        "sibling_id": assignment["sibling_id"],
        "source_run_id": assignment["source_run_id"],
        "source_commit": real["source_commit"],
        "artifact_sha256_manifest": file_sha256(artifact / "sha256_manifest.json"),
        "workspace_path": str(workspace),
        "workspace_token": state["workspace_token"],
        "candidate_execution_attempts": 2,
        "candidate_processes_started": result["candidate_processes_started"],
        "operator_calls": 1,
        "operator_retry_count": 0,
        "candidate_retry_count": 0,
        "dtest_rows_read": 0,
        "network_disabled_verified": True,
        "public_mount_read_only_verified": True,
        "private_mounts_verified_zero": True,
        "sealed_receipts": 2,
        "sealed_modes_0600_verified": True,
        "visible_dsearch_utilities": result["visible_dsearch_utilities"],
        "sealed_dval_commitment_sha256s": commitments,
        "candidate_wall_time_seconds": candidate_walls,
        "api_usage": usages,
    }
    receipt_path = pathlib.Path(args.receipt).resolve()
    atomic_json(receipt_path, receipt)
    print(canonical_json(receipt).decode("utf-8"))
    return receipt


def parser() -> argparse.ArgumentParser:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--artifact", required=True)
    ap.add_argument("--assignment-result", required=True)
    ap.add_argument("--code-vault", required=True)
    ap.add_argument("--real-contract", required=True)
    ap.add_argument("--split-root", required=True)
    ap.add_argument("--workspace-root", required=True)
    ap.add_argument("--sealed-root", required=True)
    ap.add_argument("--container", required=True)
    ap.add_argument("--hf-cache", required=True)
    ap.add_argument("--nvfix-dir", required=True)
    ap.add_argument("--source-root", required=True)
    ap.add_argument("--index", required=True, type=int)
    ap.add_argument("--receipt", required=True)
    return ap


def main() -> int:
    try:
        verify(parser().parse_args())
    except (
        VerifyError,
        RealContractError,
        OSError,
        ValueError,
        json.JSONDecodeError,
        subprocess.SubprocessError,
    ) as exc:
        print(f"VERIFY_REAL_BALANCED_WORKER_ERROR: {exc}", file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
