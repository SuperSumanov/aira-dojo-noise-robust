"""Step 1 replay, tokenizer indicators and partial output tests."""

import asyncio
import json
from argparse import Namespace

import httpx
import pytest

from mle_policy.src.self_distillation.chaii_test.__main__ import (
    read_step_one,
    sample,
)

from mle_policy.src.self_distillation.chaii_test.inspect import inspect_run


@pytest.fixture(params=[False, True])
def journal(tmp_path, request):
    directory = tmp_path / ("json" if request.param else "checkpoint")
    directory.mkdir()
    path = directory / ("JOURNAL.jsonl" if request.param else "journal.jsonl")
    messages = [{"role": "system", "content": "system"}, {"role": "user", "content": "original prompt"}]
    nodes = [
        {"step": 0},
        {"step": 3, "operators_used": ["draft"], "operators_metrics": [{}]},
        {
            "step": 1, "id": "draft", "operators_used": ["draft", "analysis"],
            "operators_metrics": [{"prompt_messages": messages}, {"prompt_messages": []}],
        },
    ]
    path.write_text("\n".join(json.dumps({"data": node} if request.param else node) for node in nodes))
    config = {
        "metadata": {"seed": 1},
        "solver": {"operators": {"draft": {"llm": {"generation_kwargs": {
            "allowed_openai_params": ["reasoning_effort"], "reasoning_effort": "medium",
            "temperature": 0.6, "top_p": 0.95,
        }}}}},
    }
    (tmp_path / "dojo_config.json").write_text(json.dumps(config))
    return path, messages, config


def test_reads_exact_step_one_and_run_config(journal):
    path, messages, config = journal
    node, call, recorded_config = read_step_one(path)
    assert node["step"] == 1
    assert call["prompt_messages"] == messages
    assert recorded_config == config


def test_missing_step_one_fails(journal):
    path, _, _ = journal
    path.write_text('{"step": 3, "operators_used": ["draft"]}\n')
    with pytest.raises(ValueError, match="No step 1"):
        read_step_one(path)


@pytest.mark.parametrize("extra_settings", [{}, {
    "seed": 42, "chat_template_kwargs": {"enable_thinking": False}, "max_tokens": 1234,
}])
def test_sampling_uses_recorded_settings(journal, tmp_path, extra_settings):
    path, messages, config = journal
    settings = config["solver"]["operators"]["draft"]["llm"]["generation_kwargs"]
    settings.update(extra_settings)
    (path.parent.parent / "dojo_config.json").write_text(json.dumps(config))
    requests = []

    async def handler(request):
        body = json.loads(request.content)
        requests.append(body)
        assert request.url.path == "/v1/chat/completions"
        if len(requests) == 2:
            return httpx.Response(500, text="test failure")
        return httpx.Response(200, json={
            "choices": [{"finish_reason": "stop", "message": {
                "content": "```python\nuse_fast=True\n```", "reasoning_content": "engineering notes",
            }}], "usage": {"completion_tokens": 10},
        })

    args = Namespace(
        journal=path, model_id="qwen3.8-27b-mle-lora", base_url="http://test/v1/",
        output_dir=tmp_path / "samples", n=3, concurrency=2, response_mode="auto",
    )

    async def run():
        async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
            return await sample(args, client)

    result = asyncio.run(run())
    expected = {key: value for key, value in settings.items() if key != "allowed_openai_params"}
    expected.update(model=args.model_id, messages=messages, n=1)
    assert requests == [expected] * 3
    assert result["failed"] == 1
    assert result["completed"] == 3
    assert result["unfinished"] == 0
    assert result["metrics"]["final_code_explicit_identifier"]["rate"] == 1
    records = [json.loads(line) for line in (args.output_dir / "responses.jsonl").read_text().splitlines()]
    assert len(records) == 3
    inspected = inspect_run(args.output_dir / "responses.jsonl")
    assert result["metrics"] == inspected["metrics"]
    assert result["lengths"] == inspected["lengths"]
    assert result["schema_version"] == 2
    assert (args.output_dir / "summary.json").exists()
    assert (args.output_dir / "request.json").exists()
    with pytest.raises(FileExistsError):
        asyncio.run(run())


def test_cancellation_keeps_partial_summary(journal, tmp_path):
    path, _, _ = journal
    requests = []

    async def handler(request):
        requests.append(request)
        if len(requests) > 1:
            await asyncio.Event().wait()
        return httpx.Response(200, json={
            "choices": [{"finish_reason": "stop", "message": {"content": "use_fast=True"}}],
        })

    args = Namespace(
        journal=path, model_id="qwen3.8-27b", base_url="http://test/v1",
        output_dir=tmp_path / "partial", n=3, concurrency=2, response_mode="auto",
    )

    async def run():
        async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
            task = asyncio.create_task(sample(args, client))
            while not (args.output_dir / "summary.json").exists():
                await asyncio.sleep(0.01)
            task.cancel()
            with pytest.raises(asyncio.CancelledError):
                await task

    asyncio.run(run())
    result = json.loads((args.output_dir / "summary.json").read_text())
    assert (result["requested"], result["completed"], result["unfinished"]) == (3, 1, 2)
    assert result["metrics"]["has_final_answer"]["rate"] == 0
    assert result["metrics"]["thinking_explicit_identifier"]["rate"] == 1
    assert result["lengths"]["completion_tokens"]["count"] == 0
    assert len((args.output_dir / "responses.jsonl").read_text().splitlines()) == 1
