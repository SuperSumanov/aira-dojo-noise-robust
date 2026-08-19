from __future__ import annotations

import copy
import hashlib
import math

import pytest

from phase1.balanced_continuation_real_contract import (
    EXECUTION_RECEIPT_SCHEMA,
    OPERATOR_RESPONSE_SCHEMA,
    SEARCH_RECEIPT_SCHEMA,
    SEALED_LABEL_SCHEMA,
    E2A_WORKER_CONTRACT_SCHEMA,
    WORKER_CONTRACT_SCHEMA,
    RealContractError,
    bind_visible_step,
    build_operator_request,
    canonical_json,
    sha256_bytes,
    validate_execution_receipt,
    validate_operator_response,
    validate_operator_request,
    validate_search_receipt,
    validate_sealed_label_receipt,
    validate_visible_step,
    validate_worker_contract,
)


H64 = "a" * 64
ROLLOUT = "b" * 64
TOKEN = "c" * 32


def sha(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def contract() -> dict:
    return {
        "schema_version": WORKER_CONTRACT_SCHEMA,
        "backend": "aira-dojo-external-v1",
        "source_commit": "1" * 40,
        "container_sha256": "2" * 64,
        "operator_config_sha256": "3" * 64,
        "prompt_sha256": "4" * 64,
        "public_dataset_contract_sha256": "5" * 64,
        "split_manifest_sha256_opaque": "6" * 64,
        "search_evaluator_executable_sha256": "7" * 64,
        "sealed_label_evaluator_executable_sha256": "8" * 64,
        "public_data_root": "/frozen/public",
        "continuation_horizon": 2,
        "operator_timeout_seconds": 180,
        "execution_timeout_seconds": 1500,
        "evaluator_timeout_seconds": 600,
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


def e2a_contract() -> dict:
    value = contract()
    value.update({
        "schema_version": E2A_WORKER_CONTRACT_SCHEMA,
        "hf_cache_path": "/frozen/e2a-hf-cache",
        "hf_cache_manifest_sha256": "9" * 64,
        "hf_cache_payload_sha256": "a" * 64,
    })
    return value


def execution(
    *,
    ordinal: int = 0,
    status: str = "ok",
    artifact: str | None = H64,
    terminal: str = "FINAL_VALIDATION_SCORE: 0.71\n",
) -> dict:
    return {
        "schema_version": EXECUTION_RECEIPT_SCHEMA,
        "rollout_id": ROLLOUT,
        "workspace_token": TOKEN,
        "task": "synthetic-real-task",
        "execution_ordinal": ordinal,
        "code_sha256": sha("print('candidate')\n"),
        "execution_status": status,
        "process_started": status != "invalid_format",
        "candidate_execution_attempted": True,
        "exit_code": 0 if status == "ok" else None,
        "timed_out": status == "timeout",
        "wall_time_seconds": 12.5,
        "terminal_output": terminal,
        "terminal_output_sha256": sha(terminal),
        "artifact_sha256": artifact,
        "public_data_read_only": True,
        "private_paths_mounted": False,
        "retry_count": 0,
    }


def search(
    *,
    ordinal: int = 0,
    artifact: str | None = H64,
    valid: bool = True,
    score: float | None = 0.8,
) -> dict:
    return {
        "schema_version": SEARCH_RECEIPT_SCHEMA,
        "rollout_id": ROLLOUT,
        "workspace_token": TOKEN,
        "task": "synthetic-real-task",
        "execution_ordinal": ordinal,
        "artifact_sha256": artifact,
        "submission_valid": valid,
        "dsearch_score": score,
        "search_utility": score,
        "orientation": 1,
        "split_manifest_sha256": "6" * 64,
        "evaluator_executable_sha256": "7" * 64,
        "grade_return_code": 0,
        "private_bytes_exposed_to_candidate": 0,
        "dtest_rows_read": 0,
    }


def sealed_label() -> dict:
    return {
        "schema_version": SEALED_LABEL_SCHEMA,
        "rollout_id": ROLLOUT,
        "workspace_token": TOKEN,
        "task": "synthetic-real-task",
        "execution_ordinal": 0,
        "artifact_sha256": H64,
        "submission_valid": True,
        "dval_score": 0.75,
        "dval_utility": 0.75,
        "orientation": 1,
        "split_manifest_sha256": "6" * 64,
        "evaluator_executable_sha256": "8" * 64,
        "grade_return_code": 0,
        "private_bytes_exposed_to_candidate": 0,
        "dtest_rows_read": 0,
        "file_mode": 0o600,
    }


def warm_visible() -> dict:
    label = sealed_label()
    return bind_visible_step(
        execution(),
        search(),
        contract(),
        stage="warm_start",
        operator="none",
        code="print('candidate')\n",
        sealed_label_receipt_sha256=sha256_bytes(canonical_json(label)),
    )


def test_happy_path_exposes_search_only_and_selects_improve() -> None:
    validate_worker_contract(contract())
    validate_sealed_label_receipt(sealed_label(), contract())
    visible = warm_visible()
    assert visible["dsearch_score"] == 0.8
    assert visible["is_buggy"] is False
    assert not any("dval" in key.lower() for key in visible)
    request = build_operator_request(
        visible,
        contract(),
        task_description="Only public task description.",
        transition_index=1,
        operator_seed=123,
    )
    assert request["operator"] == "improve"
    assert request["previous_dsearch_score"] == 0.8
    assert not any("dval" in key.lower() for key in request)


def test_e2a_v2_contract_requires_exact_cache_binding() -> None:
    validate_worker_contract(e2a_contract())
    missing = e2a_contract()
    del missing["hf_cache_manifest_sha256"]
    with pytest.raises(RealContractError, match="missing=.*hf_cache_manifest_sha256"):
        validate_worker_contract(missing)
    bad_path = e2a_contract()
    bad_path["hf_cache_path"] = "relative/cache"
    with pytest.raises(RealContractError, match="absolute POSIX"):
        validate_worker_contract(bad_path)


def test_failed_warm_start_selects_debug_without_private_label() -> None:
    failed_execution = execution(status="timeout", artifact=None, terminal="timed out")
    failed_search = search(artifact=None, valid=False, score=None)
    visible = bind_visible_step(
        failed_execution,
        failed_search,
        contract(),
        stage="warm_start",
        operator="none",
        code="print('candidate')\n",
        sealed_label_receipt_sha256="9" * 64,
    )
    assert visible["is_buggy"] is True
    request = build_operator_request(
        visible,
        contract(),
        task_description="Public task.",
        transition_index=1,
        operator_seed=7,
    )
    assert request["operator"] == "debug"


def test_old_hce_split_and_extra_dval_field_fail_closed() -> None:
    old = contract()
    old["split_policy"] = "50/25/25_D_search_D_val_D_test"
    with pytest.raises(RealContractError, match="split_policy"):
        validate_worker_contract(old)
    leaked = search()
    leaked["dval_score"] = 0.9
    with pytest.raises(RealContractError, match="unknown=.*dval_score"):
        validate_search_receipt(leaked, contract())


def test_private_mount_and_dtest_reads_fail_closed() -> None:
    mounted = execution()
    mounted["private_paths_mounted"] = True
    with pytest.raises(RealContractError, match="mount isolation"):
        validate_execution_receipt(mounted, contract())
    read_test = search()
    read_test["dtest_rows_read"] = 1
    with pytest.raises(RealContractError, match="read D_test"):
        validate_search_receipt(read_test, contract())


def test_sealed_label_requires_mode_0600_and_never_reads_dtest() -> None:
    wrong_mode = sealed_label()
    wrong_mode["file_mode"] = 0o644
    with pytest.raises(RealContractError, match="mode 0600"):
        validate_sealed_label_receipt(wrong_mode, contract())
    read_test = sealed_label()
    read_test["dtest_rows_read"] = 2
    with pytest.raises(RealContractError, match="read D_test"):
        validate_sealed_label_receipt(read_test, contract())


def test_nonfinite_score_and_identity_mismatch_fail_closed() -> None:
    nonfinite = search(score=math.nan)
    with pytest.raises(RealContractError, match="canonical finite JSON"):
        validate_search_receipt(nonfinite, contract())
    mismatched = search()
    mismatched["workspace_token"] = "d" * 32
    with pytest.raises(RealContractError, match="identities differ"):
        bind_visible_step(
            execution(),
            mismatched,
            contract(),
            stage="warm_start",
            operator="none",
            code="print('candidate')\n",
            sealed_label_receipt_sha256="9" * 64,
        )


def test_terminal_credential_shape_is_rejected_before_visibility() -> None:
    secret_terminal = "debug=" + "sk-" + "A" * 24
    leaked = execution(terminal=secret_terminal)
    with pytest.raises(RealContractError, match="credential-shaped bytes"):
        validate_execution_receipt(leaked, contract())


def test_operator_response_is_bound_one_call_no_retry() -> None:
    request = build_operator_request(
        warm_visible(),
        contract(),
        task_description="Public task.",
        transition_index=1,
        operator_seed=9,
    )
    code = "print('improved')\n"
    response = {
        "schema_version": OPERATOR_RESPONSE_SCHEMA,
        "rollout_id": ROLLOUT,
        "transition_index": 1,
        "operator": "improve",
        "request_sha256": sha256_bytes(canonical_json(request)),
        "raw_response_sha256": "a" * 64,
        "extraction_status": "ok",
        "code": code,
        "code_sha256": sha(code),
        "provider_request_id": "mock-request-1",
        "operator_calls": 1,
        "retry_count": 0,
    }
    validate_operator_response(response, request, contract())
    retried = copy.deepcopy(response)
    retried["retry_count"] = 1
    with pytest.raises(RealContractError, match="one-call/no-retry"):
        validate_operator_response(retried, request, contract())


def test_invalid_operator_format_is_counted_without_inventing_code() -> None:
    request = build_operator_request(
        warm_visible(),
        contract(),
        task_description="Public task.",
        transition_index=1,
        operator_seed=10,
    )
    response = {
        "schema_version": OPERATOR_RESPONSE_SCHEMA,
        "rollout_id": ROLLOUT,
        "transition_index": 1,
        "operator": "improve",
        "request_sha256": sha256_bytes(canonical_json(request)),
        "raw_response_sha256": "a" * 64,
        "extraction_status": "invalid_format",
        "code": "",
        "code_sha256": sha(""),
        "provider_request_id": None,
        "operator_calls": 1,
        "retry_count": 0,
    }
    validate_operator_response(response, request, contract())
    invented = copy.deepcopy(response)
    invented["code"] = "pass\n"
    invented["code_sha256"] = sha("pass\n")
    with pytest.raises(RealContractError, match="must not invent code"):
        validate_operator_response(invented, request, contract())


def test_remote_path_contract_is_posix_and_non_root() -> None:
    windows = contract()
    windows["public_data_root"] = r"C:\\private\\data"
    with pytest.raises(RealContractError, match="absolute POSIX"):
        validate_worker_contract(windows)
    root = contract()
    root["public_data_root"] = "/"
    with pytest.raises(RealContractError, match="canonical non-root"):
        validate_worker_contract(root)
    traversal = contract()
    traversal["public_data_root"] = "/frozen/../private"
    with pytest.raises(RealContractError, match="canonical non-root"):
        validate_worker_contract(traversal)


def test_execution_status_and_integer_counters_are_strict() -> None:
    contradictory = execution(status="timeout", artifact=None, terminal="timed out")
    contradictory["timed_out"] = False
    with pytest.raises(RealContractError, match="timeout status/flag"):
        validate_execution_receipt(contradictory, contract())
    boolean_counter = search()
    boolean_counter["dtest_rows_read"] = False
    with pytest.raises(RealContractError, match="non-negative integer"):
        validate_search_receipt(boolean_counter, contract())


def test_visible_and_operator_request_cannot_be_forged_after_binding() -> None:
    visible = warm_visible()
    visible["is_buggy"] = True
    with pytest.raises(RealContractError, match="buggy flag differs"):
        validate_visible_step(visible, contract())
    request = build_operator_request(
        warm_visible(),
        contract(),
        task_description="Public task.",
        transition_index=1,
        operator_seed=11,
    )
    request["operator"] = "debug"
    with pytest.raises(RealContractError, match="fixed debug/improve"):
        validate_operator_request(request, contract())
