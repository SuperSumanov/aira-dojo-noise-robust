from __future__ import annotations

import argparse
import json
from pathlib import Path

import pytest

import phase1.balanced_continuation_operator_entry as entry
from phase1.balanced_continuation_real_contract import (
    EXECUTION_RECEIPT_SCHEMA,
    SEARCH_RECEIPT_SCHEMA,
    WORKER_CONTRACT_SCHEMA,
    bind_visible_step,
    build_operator_request,
    canonical_json,
    sha256_bytes,
)


ROLLOUT = "a" * 64
TOKEN = "b" * 32
ARTIFACT = "c" * 64


def contract() -> dict:
    return {
        "schema_version": WORKER_CONTRACT_SCHEMA,
        "backend": "aira-dojo-external-v1",
        "source_commit": "1" * 40,
        "container_sha256": "2" * 64,
        "operator_config_sha256": entry.operator_config_sha256(),
        "prompt_sha256": entry.prompt_bundle_sha256(),
        "public_dataset_contract_sha256": "5" * 64,
        "split_manifest_sha256_opaque": "6" * 64,
        "search_evaluator_executable_sha256": "7" * 64,
        "sealed_label_evaluator_executable_sha256": "8" * 64,
        "public_data_root": "/frozen/public",
        "continuation_horizon": 1,
        "operator_timeout_seconds": 180,
        "execution_timeout_seconds": 600,
        "evaluator_timeout_seconds": 120,
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


def request(value: dict) -> dict:
    code = "print('baseline')\n"
    terminal = "FINAL_VALIDATION_SCORE: 0.7\n"
    execution = {
        "schema_version": EXECUTION_RECEIPT_SCHEMA,
        "rollout_id": ROLLOUT,
        "workspace_token": TOKEN,
        "task": "spaceship-titanic",
        "execution_ordinal": 0,
        "code_sha256": sha256_bytes(code.encode()),
        "execution_status": "ok",
        "process_started": True,
        "candidate_execution_attempted": True,
        "exit_code": 0,
        "timed_out": False,
        "wall_time_seconds": 1.0,
        "terminal_output": terminal,
        "terminal_output_sha256": sha256_bytes(terminal.encode()),
        "artifact_sha256": ARTIFACT,
        "public_data_read_only": True,
        "private_paths_mounted": False,
        "retry_count": 0,
    }
    search = {
        "schema_version": SEARCH_RECEIPT_SCHEMA,
        "rollout_id": ROLLOUT,
        "workspace_token": TOKEN,
        "task": "spaceship-titanic",
        "execution_ordinal": 0,
        "artifact_sha256": ARTIFACT,
        "submission_valid": True,
        "dsearch_score": 0.75,
        "search_utility": 0.75,
        "orientation": 1,
        "split_manifest_sha256": "6" * 64,
        "evaluator_executable_sha256": "7" * 64,
        "grade_return_code": 0,
        "private_bytes_exposed_to_candidate": 0,
        "dtest_rows_read": 0,
    }
    visible = bind_visible_step(
        execution, search, value, stage="warm_start", operator="none", code=code,
        sealed_label_receipt_sha256="9" * 64,
    )
    return build_operator_request(
        visible, value, task_description="Public task description only.",
        transition_index=1, operator_seed=1729,
    )


def write_json(path: Path, value: object) -> None:
    path.write_bytes(canonical_json(value) + b"\n")


def args(tmp_path: Path, value: dict, req: dict) -> argparse.Namespace:
    contract_path, request_path = tmp_path / "contract.json", tmp_path / "request.json"
    write_json(contract_path, value)
    write_json(request_path, req)
    return argparse.Namespace(
        contract=str(contract_path), request=str(request_path),
        response=str(tmp_path / "response.json"),
        raw_response=str(tmp_path / "raw_response.json"),
        usage_receipt=str(tmp_path / "usage.json"),
    )


def complete_script() -> str:
    padding = "\n".join(f"feature_{index} = {index}" for index in range(24))
    return f"""```python
import pandas as pd
from sklearn.model_selection import KFold

train = pd.read_csv("./data/train.csv")
test = pd.read_csv("./data/test.csv")
{padding}
score = 0.75
submission = pd.DataFrame({{"PassengerId": test["PassengerId"], "Transported": False}})
submission.to_csv("submission.csv", index=False)
print(f"FINAL_VALIDATION_SCORE: {{score}}")
```"""


def test_one_mocked_call_and_exact_response(tmp_path: Path) -> None:
    value = contract()
    req = request(value)
    calls = []

    def caller(prompt: str):
        calls.append(prompt)
        return complete_script(), "provider-1", {
            "schema_version": "balanced-continuation-operator-usage-v1",
            "model_id": entry.MODEL_ID,
            "provider_request_id": "provider-1",
            "api_calls": 1,
            "retry_count": 0,
            "latency_seconds": 0.1,
            "prompt_tokens": 10,
            "completion_tokens": 5,
            "total_tokens": 15,
        }

    result = entry.run(args(tmp_path, value, req), caller=caller)
    assert len(calls) == 1
    assert result["extraction_status"] == "ok"
    assert result["code"].startswith("import pandas as pd\n")
    assert "Public task description only." in calls[0]
    assert "dval" not in calls[0].lower()
    usage = json.loads((tmp_path / "usage.json").read_text())
    assert usage["api_calls"] == 1 and usage["retry_count"] == 0
    raw = json.loads((tmp_path / "raw_response.json").read_text())
    assert raw["raw_response"] == complete_script()
    assert raw["raw_response_sha256"] == result["raw_response_sha256"]


def test_invalid_format_is_not_retried_or_filled(tmp_path: Path) -> None:
    value = contract()
    req = request(value)
    calls = 0

    def caller(_: str):
        nonlocal calls
        calls += 1
        return "No code block available.", None, {
            "schema_version": "balanced-continuation-operator-usage-v1",
            "model_id": entry.MODEL_ID,
            "provider_request_id": None,
            "api_calls": 1,
            "retry_count": 0,
            "latency_seconds": 0.1,
            "prompt_tokens": None,
            "completion_tokens": None,
            "total_tokens": None,
        }

    result = entry.run(args(tmp_path, value, req), caller=caller)
    assert calls == 1
    assert result["extraction_status"] == "invalid_format"
    assert result["code"] == ""


@pytest.mark.parametrize("raw,reason", [
    ("plan\n" + complete_script(), "not_exactly_one_python_block"),
    ("```python\nprint('tiny')\n```", "replacement_too_short"),
    (complete_script() + "\n```python\nprint('second')\n```", "not_exactly_one_python_block"),
    (complete_script()[:-3], "not_exactly_one_python_block"),
])
def test_complete_script_gate_rejects_fragments(raw: str, reason: str) -> None:
    code, observed = entry.assess_single_complete_code(raw, "x" * 2000)
    assert code == ""
    assert observed == reason


def test_operator_config_tamper_fails_before_call(tmp_path: Path) -> None:
    value = contract()
    req = request(value)
    value["operator_config_sha256"] = "f" * 64
    called = False

    def caller(_: str):
        nonlocal called
        called = True
        raise AssertionError

    with pytest.raises(entry.OperatorError, match="config differs"):
        entry.run(args(tmp_path, value, req), caller=caller)
    assert called is False


def test_prompt_render_is_deterministic() -> None:
    value = contract()
    req = request(value)
    assert entry.render_prompt(req) == entry.render_prompt(req)
    assert sha256_bytes(entry.render_prompt(req).encode()) == sha256_bytes(
        entry.render_prompt(req).encode()
    )
