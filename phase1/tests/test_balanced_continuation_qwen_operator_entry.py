from __future__ import annotations

import json
from pathlib import Path

import pytest

import phase1.balanced_continuation_qwen_operator_entry as entry
import phase1.balanced_continuation_real_worker as worker
import phase1.verify_balanced_continuation_real_worker as verifier
from phase1.tests.test_balanced_continuation_operator_entry import (
    args,
    complete_script,
    contract as deepseek_contract,
    request,
)


def contract() -> dict:
    value = deepseek_contract()
    value["operator_config_sha256"] = entry.operator_config_sha256()
    value["prompt_sha256"] = entry.prompt_bundle_sha256()
    return value


def usage(provider_id: str | None) -> dict:
    return {
        "schema_version": "balanced-continuation-operator-usage-v1",
        "model_id": entry.MODEL_ID,
        "provider_request_id": provider_id,
        "api_calls": 1,
        "retry_count": 0,
        "latency_seconds": 0.1,
        "prompt_tokens": 10,
        "completion_tokens": 5,
        "total_tokens": 15,
    }


def test_qwen_one_mocked_call_and_profile_resolution(tmp_path: Path) -> None:
    value = contract()
    req = request(value)
    calls: list[str] = []

    def caller(prompt: str):
        calls.append(prompt)
        return complete_script(), "qwen-provider-1", usage("qwen-provider-1")

    result = entry.run(args(tmp_path, value, req), caller=caller)
    assert len(calls) == 1
    assert result["extraction_status"] == "ok"
    assert worker.operator_profile(value)["module_name"].endswith("qwen_operator_entry")
    assert verifier.operator_profile(value)["provider"] == "qwen"
    raw = json.loads((tmp_path / "raw_response.json").read_text(encoding="utf-8"))
    assert raw["schema_version"] == entry.RAW_RESPONSE_SCHEMA
    assert raw["raw_response"] == complete_script()


def test_qwen_invalid_format_is_one_call_without_retry(tmp_path: Path) -> None:
    value = contract()
    req = request(value)
    calls = 0

    def caller(_: str):
        nonlocal calls
        calls += 1
        return "No code block available.", None, usage(None)

    result = entry.run(args(tmp_path, value, req), caller=caller)
    assert calls == 1
    assert result["extraction_status"] == "invalid_format"
    assert result["code"] == ""


def test_qwen_hash_tamper_fails_before_call(tmp_path: Path) -> None:
    value = contract()
    req = request(value)
    value["prompt_sha256"] = "f" * 64
    called = False

    def caller(_: str):
        nonlocal called
        called = True
        raise AssertionError

    with pytest.raises(entry.QwenOperatorError, match="prompt bundle differs"):
        entry.run(args(tmp_path, value, req), caller=caller)
    assert called is False
