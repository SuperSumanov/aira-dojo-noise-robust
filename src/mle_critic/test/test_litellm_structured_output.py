"""Offline regression tests for LiteLLM structured-output handling."""

from __future__ import annotations

import importlib.util
import json
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest

BACKEND_PATH = (
    Path(__file__).resolve().parents[2]
    / "dojo/core/solvers/llm_helpers/backends/lite_llm.py"
)
BACKEND_SPEC = importlib.util.spec_from_file_location("dojo_lite_llm_backend", BACKEND_PATH)
assert BACKEND_SPEC is not None and BACKEND_SPEC.loader is not None
backend = importlib.util.module_from_spec(BACKEND_SPEC)
BACKEND_SPEC.loader.exec_module(backend)


SCHEMA = {
    "type": "object",
    "properties": {
        "is_bug": {"type": "boolean"},
        "summary": {"type": "string"},
        "metric": {"type": "number"},
    },
    "required": ["is_bug", "summary", "metric"],
    "additionalProperties": False,
}


class FakeCompletion:
    def __init__(self, *, content: str | None = None, tool_calls: list[Any] | None = None):
        self.choices = [
            SimpleNamespace(
                message=SimpleNamespace(content=content, tool_calls=tool_calls, function_call=None)
            )
        ]

    def to_dict(self) -> dict[str, Any]:
        return {"usage": {"prompt_tokens": 10, "completion_tokens": 5}}


def _client() -> backend.LiteLLMClient:
    cfg = SimpleNamespace(
        model_id="deepseek-v4-flash",
        base_url="https://api.deepseek.com",
        use_azure_client=False,
        provider="openai",
    )
    return backend.LiteLLMClient(cfg)


def _query(client: backend.LiteLLMClient, **kwargs: Any) -> tuple[Any, dict[str, Any]]:
    return client._query_client(
        messages=[{"role": "system", "content": "Review this run."}],
        model_kwargs={"temperature": 0, **kwargs},
        json_schema=json.dumps(SCHEMA),
        function_name="submit_review",
        function_description="Submit the review.",
    )


def test_structured_output_defaults_to_json_mode(monkeypatch: pytest.MonkeyPatch) -> None:
    calls: list[dict[str, Any]] = []

    def fake_completion(*, messages: list[dict[str, str]], **kwargs: Any) -> FakeCompletion:
        calls.append({"messages": messages, **kwargs})
        return FakeCompletion(
            content='{"is_bug": false, "summary": "ok", "metric": 0.8123}'
        )

    monkeypatch.setattr(backend, "completion_fn", fake_completion)
    output, _usage = _query(_client())

    assert output == {"is_bug": False, "summary": "ok", "metric": 0.8123}
    assert calls[0]["response_format"] == {"type": "json_object"}
    assert "tools" not in calls[0]
    assert "JSON Schema" in calls[0]["messages"][0]["content"]


def test_invalid_json_is_retried_and_validated(monkeypatch: pytest.MonkeyPatch) -> None:
    responses = iter(
        [
            FakeCompletion(content='{"is_bug": false'),
            FakeCompletion(content='{"is_bug": false, "summary": "ok", "metric": 0.8123}'),
        ]
    )
    calls = 0

    def fake_completion(**_kwargs: Any) -> FakeCompletion:
        nonlocal calls
        calls += 1
        return next(responses)

    monkeypatch.setattr(backend, "completion_fn", fake_completion)
    output, usage = _query(_client(), structured_output_retries=1)

    assert output["metric"] == 0.8123
    assert calls == 2
    assert usage["structured_output_transport"] == "json"
    assert usage["structured_output_requests"] == 2
    assert usage["prompt_tokens"] == 20
    assert usage["completion_tokens"] == 10


def test_schema_violation_never_falls_back_to_plain_text(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        backend,
        "completion_fn",
        lambda **_kwargs: FakeCompletion(content='{"is_bug": false, "summary": "ok"}'),
    )

    with pytest.raises(ValueError, match="Invalid structured output after 1 attempt"):
        _query(_client(), structured_output_retries=0)


def test_tools_mode_uses_modern_shape_and_parses_tool_calls(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls: list[dict[str, Any]] = []
    function = SimpleNamespace(
        name="submit_review",
        arguments='{"is_bug": false, "summary": "ok", "metric": 0.8123}',
    )

    def fake_completion(*, messages: list[dict[str, str]], **kwargs: Any) -> FakeCompletion:
        calls.append({"messages": messages, **kwargs})
        return FakeCompletion(tool_calls=[SimpleNamespace(function=function)])

    monkeypatch.setattr(backend, "completion_fn", fake_completion)
    output, _usage = _query(_client(), structured_output_mode="tools")

    assert output["is_bug"] is False
    assert calls[0]["tools"][0] == {
        "type": "function",
        "function": {
            "name": "submit_review",
            "description": "Submit the review.",
            "parameters": SCHEMA,
        },
    }
    assert calls[0]["tool_choice"] == {
        "type": "function",
        "function": {"name": "submit_review"},
    }
    assert "functions" not in calls[0]
    assert "function_call" not in calls[0]


def test_unsupported_json_mode_falls_back_to_modern_tools(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    class FakeBadRequestError(Exception):
        pass

    calls: list[dict[str, Any]] = []
    function = SimpleNamespace(
        name="submit_review",
        arguments='{"is_bug": false, "summary": "ok", "metric": 0.8123}',
    )

    def fake_completion(*, messages: list[dict[str, str]], **kwargs: Any) -> FakeCompletion:
        calls.append({"messages": messages, **kwargs})
        if "response_format" in kwargs:
            raise FakeBadRequestError("response_format json_object is not supported")
        return FakeCompletion(tool_calls=[SimpleNamespace(function=function)])

    monkeypatch.setattr(backend.litellm, "BadRequestError", FakeBadRequestError)
    monkeypatch.setattr(backend, "completion_fn", fake_completion)
    output, _usage = _query(_client())

    assert output["metric"] == 0.8123
    assert len(calls) == 2
    assert calls[0]["response_format"] == {"type": "json_object"}
    assert calls[1]["tools"][0]["function"]["name"] == "submit_review"
    assert calls[1]["tool_choice"]["function"]["name"] == "submit_review"
