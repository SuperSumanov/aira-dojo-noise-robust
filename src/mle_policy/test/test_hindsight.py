import asyncio
import copy
import hashlib
import json
from pathlib import Path
import subprocess
from types import SimpleNamespace

import httpx
import pytest

from src.mle_policy.src.data.hindsight.__main__ import rewrite, run
from src.mle_policy.src.data.hindsight.helper import VERSION, atomic_json, parts
from src.mle_policy.src.data.hindsight.client import ModelClient, validate_hint
from src.mle_policy.src.data.helper.filter_positive import filter_positive
from src.mle_policy.src.data.helper.align_splits import align_splits
from src.mle_policy.src.data.helper.merge import merge
from src.mle_policy.src.data.hindsight.regenerate import extract_hint, generation_options, hint_messages, inject_hint
from src.mle_policy.src.data.hindsight.tree import better, episodes, validate
from src.mle_policy.test.verify_hindsight import verify_all
from src.mle_policy.src.data.build_batch_groups import build_batch
from src.mle_policy.src.data.to_grpo import to_grpo
from src.mle_policy.src.data.journal import has_training_outcome, iter_samples, read_run_meta


@pytest.mark.parametrize("metric, expected", [(0.4, True), (None, False), (True, False), (float("nan"), False)])
def test_metric_labels_do_not_require_source_metadata(metric, expected):
    assert has_training_outcome({"is_buggy": None, "metric": metric}) is expected
    assert not has_training_outcome({"is_buggy": True, "metric": metric})


def test_bigjournal_script_discovers_fixture_without_checkpoint(tmp_path):
    repo = Path(__file__).resolve().parents[3]
    fixture = repo / "src/mle_policy/test/fixtures/hindsight"
    result = subprocess.run(
        [
            "bash",
            "src/mle_policy/scripts/data/build_all_batches_bigjournal.sh",
            str(fixture),
            str(tmp_path),
            "--print",
        ],
        cwd=repo,
        capture_output=True,
        text=True,
        check=True,
    )
    assert result.stdout.strip() == str(fixture)


def test_experiment_fixture_compares_both_inputs_with_shared_hint(tmp_path, monkeypatch):
    import src.mle_policy.src.data.hindsight.experiment as experiment

    clients = []

    class ExperimentClient(FakeClient):
        def __init__(self, *args):
            super().__init__()
            clients.append(self)

        async def close(self):
            pass

    fixture = Path(__file__).parent / "fixtures/hindsight/run/json/JOURNAL.jsonl"
    monkeypatch.setattr(experiment, "ModelClient", ExperimentClient)
    args = SimpleNamespace(
        journal=fixture,
        output=tmp_path,
        case=["debug:1:1", "improve:1:3"],
        base_url="http://unused",
        api_key="",
        model="fake",
        concurrency=2,
    )
    asyncio.run(experiment.compare(args))
    summary = json.loads((tmp_path / "summary.json").read_text())
    assert len(summary) == 4
    client = clients[0]
    assert sum(stage.endswith("_hint") for stage, _ in client.requests) == 2
    assert sum(stage == "regenerate" for stage, _ in client.requests) == 4
    for case in args.case:
        directories = [tmp_path / (case.replace(":", "-") + suffix) for suffix in ("-hint-only", "-with-code")]
        assert (directories[0] / "hint.md").read_text() == (directories[1] / "hint.md").read_text()
        assert (directories[0] / "hint_trace.json").read_text() == (directories[1] / "hint_trace.json").read_text()
        for directory in directories:
            hint_trace = json.loads((directory / "hint_trace.json").read_text())
            assert hint_trace[-1]["stage"] == case.split(":")[0] + "_hint"
            assert hint_trace[-1]["result"]["hint"] + "\n" == (directory / "hint.md").read_text()
            assert hint_trace[-1]["messages"][0]["role"] == "system"
            assert json.loads(hint_trace[-1]["messages"][1]["content"])["target_trajectory"]
            rewrite_trace = json.loads((directory / "rewrite_trace.json").read_text())
            assert ("regenerate", rewrite_trace["messages"]) in client.requests
            assert "Preserve tensor dimensions" in str(rewrite_trace["messages"])
            assert rewrite_trace["result"]["completion"] + "\n" == (directory / "generated.md").read_text()
            assert (
                rewrite_trace["generation"] == json.loads((directory / "diagnostics.json").read_text())["generation"]
            )
            nodes = json.loads((directory / "nodes.json").read_text())
            validate(nodes)
            rewritten = rewrites(nodes)[0]
            assert (
                rewritten["operators_metrics"][0]["completion_text"] + "\n" == (directory / "generated.md").read_text()
            )
            assert rewritten["parents"] == [0]
            assert "Preserve tensor dimensions" not in str(rewritten["operators_metrics"][0]["prompt_messages"])
            assert (
                json.loads((directory / "original_prompt.json").read_text())
                == rewritten["operators_metrics"][0]["prompt_messages"]
            )
            assert rewritten["hindsight"]["metric_source"]["step"] == (2 if case.startswith("debug") else 3)


def make_node(step, operation, parent=None, *, buggy=False, metric=0.5, maximize=True):
    buggy = buggy or operation is None
    code = f"print({step})"
    return {
        "step": step,
        "id": f"node-{step}",
        "parents": [] if parent is None else [parent],
        "children": [],
        "operators_used": [operation] if operation else [],
        "operators_metrics": (
            [
                {
                    "prompt_messages": [{"role": "user", "content": f"task at {step}"}],
                    "completion_text": f"reasoning {step}\n</think>\n\nplan {step}\n```python\n{code}\n```",
                    "usage": {"completion_tokens": 123},
                }
            ]
            if operation
            else []
        ),
        "is_buggy": buggy,
        "metric": None if buggy else metric,
        "metric_maximize": None if buggy else maximize,
        "code": code,
        "plan": f"plan {step}",
        "exit_code": 1 if buggy else 0,
        "term_out": "traceback" if buggy else "finished",
        "current_best_node": 0,
        "metric_info/score": 0.9,
        "metric_info/median_threshold": 0.2,
        "metric_info/gold_threshold": 0.8,
        "metric_info/is_lower_better": not maximize,
    }


class FakeClient:
    def __init__(self):
        self.requests = []

    async def debug_hint(self, messages, *, part=False):
        return await self._result("debug_hint_part" if part else "debug_hint", messages)

    async def improve_hint(self, messages, *, part=False):
        return await self._result("improve_hint_part" if part else "improve_hint", messages)

    async def _result(self, stage, messages):
        payload = json.loads(messages[1]["content"])
        self.requests.append((stage, payload))
        return {"hint": "Preserve tensor dimensions and use the fast tokenizer."}

    async def generate(self, messages, generation):
        self.requests.append(("regenerate", copy.deepcopy(messages)))
        return {
            "completion": "Let me work through tokenization.\n</think>\n\nI will train and validate.\n```python\nprint('new')\n```",
            "usage": {"completion_tokens": 20},
            "cache_key": "test-cache",
            "model": "fake-policy",
        }


def rewrites(nodes):
    return [node for node in nodes if node["hindsight"]["kind"] == "rewrite"]


def test_long_hint_reads_all_steps_before_synthesis():
    nodes = [make_node(0, None), make_node(1, "draft", 0, buggy=True), make_node(2, "debug", 1)]
    nodes[1]["plan"] = "long plan " * 30000
    by_step = {node["step"]: node for node in nodes}
    episode = episodes(nodes)[0]
    client = FakeClient()
    trace = []
    hint = asyncio.run(extract_hint("debug", episode, episode, by_step, client, trace=trace))
    assert hint
    fragments = [payload for stage, payload in client.requests if stage == "debug_hint_part"]
    assert [payload["target_trajectory"][0]["step"] for payload in fragments] == [1, 2]
    assert fragments[0]["target_trajectory"][0]["plan"] == nodes[1]["plan"]
    assert all(
        "response" not in entry and "executed_code" not in entry
        for payload in fragments
        for entry in payload["target_trajectory"]
    )
    stage, combined = client.requests[-1]
    assert stage == "debug_hint"
    assert len(combined["trajectory_guidance"]) == 2
    assert not combined["target_trajectory"]
    assert combined["final_code"] == nodes[2]["code"]
    assert [entry["stage"] for entry in trace] == ["debug_hint_part", "debug_hint_part", "debug_hint"]
    assert [json.loads(entry["messages"][1]["content"]) for entry in trace] == [
        payload for _, payload in client.requests
    ]
    assert all(entry["result"]["hint"] == hint for entry in trace)


def test_align_splits_inherits_original_groups(tmp_path):
    original, hindsight = tmp_path / "original", tmp_path / "hindsight"
    original.mkdir()
    hindsight.mkdir()
    group = {"group_id": "a", "batch": "batch", "task": "task", "members": [{"run_dir": "run"}]}
    (original / "groups.jsonl").write_text(json.dumps(group) + "\n")
    (hindsight / "groups.jsonl").write_text(json.dumps(group) + "\n")
    (hindsight / "manifest.json").write_text("{}")
    (original / "splits.jsonl").write_text(json.dumps({"group_id": "a", "split": "val"}) + "\n")
    assert align_splits(original, hindsight)["group_counts"] == {"val": 1}
    assert json.loads((hindsight / "splits.jsonl").read_text())["split"] == "val"


def test_merge_keeps_full_rows_and_rejects_invalid_hindsight(tmp_path):
    original, synthetic, destination = (
        tmp_path / "original.jsonl",
        tmp_path / "positive.jsonl",
        tmp_path / "merged.jsonl",
    )
    baseline = {"sample_id": "original", "group_id": "group", "split": "train", "advantage": -1}
    regenerated = {
        **baseline,
        "sample_id": "synthetic",
        "advantage": 1,
    }
    original.write_text(json.dumps(baseline) + "\n")
    synthetic.write_text(json.dumps(regenerated) + "\n")
    assert merge(original, synthetic, destination)["rows"] == 2
    assert list(map(json.loads, destination.read_text().splitlines())) == [baseline, regenerated]
    for field, value, message in (
        ("advantage", 0, "positive-advantage"),
        ("sample_id", "original", "Duplicate"),
        ("split", "val", "Inconsistent group split"),
    ):
        synthetic.write_text(json.dumps({**regenerated, field: value}) + "\n")
        with pytest.raises(ValueError, match=message):
            merge(original, synthetic, destination)


def test_preserves_ancestor_tree_without_original_training_calls():
    nodes = [
        make_node(0, None),
        make_node(1, "draft", 0),
        make_node(2, "improve", 1, buggy=True),
        make_node(3, "debug", 2, metric=0.4),
    ]
    output, _ = asyncio.run(rewrite(nodes, FakeClient()))
    by_step = {node["step"]: node for node in output}
    assert by_step[1]["parents"] == [0]
    assert by_step[0]["children"] == [1]
    assert by_step[1]["children"] == [rewrites(output)[0]["step"]]
    assert not by_step[1]["operators_metrics"]
    assert rewrites(output)[0]["parents"] == [1]
    validate(output)


@pytest.mark.parametrize("include_code", [True, False])
def test_debug_hint_then_full_generation_with_clean_stored_prompt(include_code):
    nodes = [make_node(0, None), make_node(1, "draft", 0, buggy=True), make_node(2, "debug", 1)]
    original = copy.deepcopy(nodes)
    client = FakeClient()
    output, report = asyncio.run(
        rewrite(nodes, client, include_code=include_code, source_journal="run/json/JOURNAL.jsonl")
    )
    assert nodes == original
    assert len(output) == 2
    added = rewrites(output)[0]
    assert added["code"] == "print('new')"
    assert added["is_buggy"] is None and added["metric"] == 0.5
    assert added["parents"] == [0]
    assert added["plan"] == "I will train and validate."
    call = added["operators_metrics"][0]
    assert call["prompt_messages"] == nodes[1]["operators_metrics"][0]["prompt_messages"]
    assert call["usage"] == {}
    assert "Let me work through" in call["completion_text"]
    assert (
        call["completion_text"]
        == "Let me work through tokenization.\n</think>\n\nI will train and validate.\n```python\nprint('new')\n```"
    )
    assert "hindsight_notes" not in json.dumps(output)
    assert all(node["id"] not in {source["id"] for source in nodes} for node in output)
    assert output[0]["operators_metrics"] == [] and output[0]["code"] == ""
    provenance = added["hindsight"]
    assert provenance["target_trajectory"] == [{"step": 1, "id": "node-1"}, {"step": 2, "id": "node-2"}]
    assert provenance["metric_source"] == {"step": 2, "id": "node-2"}
    assert provenance["metric_origin"] == "inherited"
    assert provenance["execution_status"] == "not_run"
    assert provenance["response_origin"] == "regenerated"
    assert all(added[field] is None for field in ("analysis", "term_out", "_term_out", "exit_code", "exec_time"))
    assert "metric_info/score" not in added
    assert provenance["source_journal"] == "run/json/JOURNAL.jsonl"
    assert provenance["hint_includes_code"] == include_code
    augmented = next(payload for stage, payload in client.requests if stage == "regenerate")
    assert augmented[-1]["content"].startswith("\n\n<hindsight_notes>")
    assert augmented[-1]["content"].endswith(
        "</hindsight_notes>" + nodes[1]["operators_metrics"][0]["prompt_messages"][-1]["content"]
    )
    assert ("print(2)" in augmented[-1]["content"]) == include_code
    hint_payload = next(payload for stage, payload in client.requests if stage == "debug_hint")
    assert hint_payload["target_trajectory"][0]["execution_output"] == "traceback"
    assert report["debug_rewrites"][0]["added_steps"] == [3]
    assert len(episodes(output)) == 1


def test_improve_inherits_donor_metric_and_keeps_generated_code():
    nodes = [
        make_node(0, None),
        make_node(1, "draft", 0, metric=0.2),
        make_node(2, "improve", 1, buggy=True),
        make_node(3, "debug", 2, metric=0.8),
    ]
    result, report = asyncio.run(rewrite(nodes, FakeClient()))
    assert len(report["debug_rewrites"]) == len(report["improve_rewrites"]) == 1
    added = next(node for node in rewrites(result) if node["hindsight"]["stage"] == "improve")
    assert added["code"] == "print('new')"
    assert added["metric"] == 0.8 and added["operators_used"] == ["draft"]
    assert added["parents"] == [0]
    assert added["operators_metrics"][0]["prompt_messages"] == nodes[1]["operators_metrics"][0]["prompt_messages"]
    assert added["hindsight"]["donor_trajectory"] == [{"step": 2, "id": "node-2"}, {"step": 3, "id": "node-3"}]
    assert all(node["operators_used"] != ["debug"] for node in result)
    assert all(len(episode.steps) == 1 for episode in episodes(result))
    assert report["rewrites_by_target_operator"]["improve"] == {"draft": 1}


def test_improve_can_rewrite_an_implement_episode_that_needed_debugging():
    nodes = [
        make_node(0, None),
        make_node(1, "draft", 0, buggy=True),
        make_node(2, "debug", 1, metric=0.2),
        make_node(3, "improve", 2, metric=0.8),
    ]
    result, report = asyncio.run(rewrite(nodes, FakeClient()))
    added = next(node for node in rewrites(result) if node["hindsight"]["stage"] == "improve")
    assert added["operators_used"] == ["draft"]
    assert added["hindsight"]["prompt_source"]["step"] == 1
    assert added["hindsight"]["target_trajectory"] == [{"step": 1, "id": "node-1"}, {"step": 2, "id": "node-2"}]
    assert added["code"] == "print('new')" and added["parents"] == [0]
    assert report["rewrites_by_target_operator"]["improve"] == {"draft": 1}


@pytest.mark.parametrize("mode, improve_count", [("debug", 0), ("debug-improve", 1)])
def test_rewrite_modes_keep_all_resolved_debug_trajectories(mode, improve_count):
    nodes = [
        make_node(0, None),
        make_node(1, "draft", 0, buggy=True),
        make_node(2, "debug", 1),
        make_node(3, "improve", 2, metric=0.8),
        make_node(4, "draft", 0, buggy=True),
        make_node(5, "debug", 4),
    ]
    original = copy.deepcopy(nodes)
    client = FakeClient()
    result, report = asyncio.run(rewrite(nodes, client, mode=mode))
    assert nodes == original
    assert report["mode"] == mode
    assert {item["root"] for item in report["debug_rewrites"]} == {1, 4}
    assert len(report["improve_rewrites"]) == improve_count
    assert len(rewrites(result)) == 2 + improve_count
    assert sum(stage == "improve_hint" for stage, _ in client.requests) == improve_count
    assert {stage for stage, _ in client.requests} <= {"debug_hint", "improve_hint", "regenerate"}


def test_rewrite_rejects_unknown_mode():
    with pytest.raises(ValueError, match="Unknown hindsight mode"):
        asyncio.run(rewrite([], FakeClient(), mode="improve"))


def test_no_rewrite_produces_empty_journal():
    result, report = asyncio.run(rewrite([make_node(0, None), make_node(1, "draft", 0)], FakeClient()))
    assert result == [] and report["output_nodes"] == 0


@pytest.mark.parametrize("maximize", [True, False])
def test_improvement_uses_cv_direction_not_official_score(maximize):
    nodes = [
        make_node(0, None),
        make_node(1, "draft", 0, metric=0.5, maximize=maximize),
        make_node(2, "improve", 1, metric=0.8 if maximize else 0.2, maximize=maximize),
    ]
    nodes[2]["metric_info/score"] = 0
    result, report = asyncio.run(rewrite(nodes, FakeClient()))
    assert len(report["improve_rewrites"]) == 1
    assert "metric_info/score" not in rewrites(result)[0]


def test_unresolved_and_tied_episodes_have_no_improvement():
    nodes = [
        make_node(0, None),
        make_node(1, "draft", 0),
        make_node(2, "improve", 1),
        make_node(3, "improve", 2, buggy=True),
    ]
    result, report = asyncio.run(rewrite(nodes, FakeClient()))
    assert result == [] and not report["improve_rewrites"]
    assert not better(make_node(5, "draft", metric=float("nan")), nodes[1])


def test_generation_options_preserve_recorded_sampling():
    options = generation_options(
        {"temperature": 0.7, "top_p": 0.8, "reasoning_effort": "high", "allowed_openai_params": []}
    )
    assert options["temperature"] == 0.7 and options["top_p"] == 0.8
    assert options["chat_template_kwargs"] == {"enable_thinking": True, "reasoning_effort": "high"}
    assert "allowed_openai_params" not in options
    assert "max_tokens" not in options
    assert "max_tokens" not in generation_options()
    assert generation_options({"max_tokens": 12345})["max_tokens"] == 12345
    with pytest.raises(ValueError, match="reasoning-enabled"):
        generation_options({"chat_template_kwargs": {"enable_thinking": False}})


def test_response_parsing_preserves_native_thinking_code_blocks():
    text = (
        "<think>Need a tensor: ```python\nshape = (2, 3)\n```\n</think>\n\n# Plan\nTrain.\n```python\nprint(1)\n```\n"
    )
    thinking, answer, block = parts(text)
    assert thinking.startswith("<think>") and "shape = (2, 3)" in thinking
    assert block.group("code").strip() == "print(1)"
    assert answer[: block.start()].strip() == "# Plan\nTrain."


@pytest.mark.parametrize(
    "text",
    [
        "summary\n```python\nprint(1)\n```",
        "reason\n</think>\n```python\nprint(1)\n```",
        "reason\n</think>\nplan\n```python\nif\n```",
        "reason\n</think>\nplan\n```python\nprint(1)\n```\n```python\nprint(2)\n```",
    ],
)
def test_incomplete_responses_rejected(text):
    with pytest.raises((ValueError, SyntaxError)):
        parts(text)


def test_hint_injection_does_not_mutate_original_messages():
    messages = [{"role": "system", "content": "system"}, {"role": "user", "content": "task"}]
    augmented = inject_hint(messages, "use fast tokenizer")
    assert messages[-1]["content"] == "task" and augmented[0] == messages[0]
    with pytest.raises(ValueError, match="text user"):
        inject_hint([], "hint")


def test_hint_schema_and_trajectory_payload():
    validate_hint({"hint": "detailed advice\n```python\nx = 1\n```"})
    with pytest.raises(ValueError, match="nonempty hint"):
        validate_hint({"thinking": "summary"})
    nodes = [make_node(0, None), make_node(1, "draft", 0, buggy=True), make_node(2, "debug", 1)]
    episode = episodes(nodes)[0]
    payload = json.loads(
        hint_messages(episode, episode, {node["step"]: node for node in nodes}, "debug")[1]["content"]
    )
    assert len(payload["target_trajectory"]) == 2
    assert payload["final_code"] == "print(2)"


@pytest.mark.parametrize("separate_reasoning", [False, True])
def test_generation_native_reasoning_cache_and_unconstrained_request(tmp_path, separate_reasoning):
    calls = []

    def respond(request):
        calls.append(json.loads(request.content))
        message = {"content": "plan\n```python\nprint(1)\n```"}
        if separate_reasoning:
            message["reasoning_content"] = "Let me think."
        else:
            message["content"] = "Let me think.\n</think>\n\n" + message["content"]
        return httpx.Response(200, json={"choices": [{"finish_reason": "stop", "message": message}], "usage": {}})

    async def exercise():
        client = ModelClient("http://localhost/v1", "key", "model", tmp_path)
        client.backend._client = client.backend._client.with_options(
            http_client=httpx.Client(transport=httpx.MockTransport(respond))
        )
        first = await client.generate([{"role": "user", "content": "task"}], generation_options())
        assert "Let me think." in first["completion"]
        assert await client.generate([{"role": "user", "content": "task"}], generation_options()) == first
        await client.close()

    asyncio.run(exercise())
    assert len(calls) == 1
    assert "response_format" not in calls[0]
    assert calls[0]["chat_template_kwargs"]["enable_thinking"] is True
    assert calls[0]["temperature"] == 0.6


@pytest.mark.parametrize(
    "method, part, stage",
    [
        ("debug_hint", False, "debug_hint"),
        ("debug_hint", True, "debug_hint_part"),
        ("improve_hint", False, "improve_hint"),
        ("improve_hint", True, "improve_hint_part"),
    ],
)
def test_stage_entries_retry_validate_and_cache(tmp_path, monkeypatch, method, part, stage):
    calls = []
    expected = {"hint": "advice"}

    def respond(request):
        calls.append(json.loads(request.content))
        content = "invalid JSON" if len(calls) == 1 else json.dumps(expected)
        return httpx.Response(200, json={"choices": [{"finish_reason": "stop", "message": {"content": content}}]})

    async def no_sleep(delay):
        pass

    monkeypatch.setattr("src.mle_policy.src.data.hindsight.client.asyncio.sleep", no_sleep)

    async def exercise():
        client = ModelClient("http://localhost/v1", "", "model", tmp_path / "cache")
        client.backend._client = client.backend._client.with_options(
            http_client=httpx.Client(transport=httpx.MockTransport(respond))
        )
        messages = [{"role": "user", "content": "input"}]
        options = {} if part is None else {"part": part}
        try:
            assert await getattr(client, method)(messages, **options) == expected
            assert await getattr(client, method)(messages, **options) == expected
        finally:
            await client.close()
        assert messages == [{"role": "user", "content": "input"}]

    asyncio.run(exercise())
    assert len(calls) == 2
    assert calls[0]["max_tokens"] == 8192
    assert calls[0]["chat_template_kwargs"]["enable_thinking"] is False
    assert calls[0]["response_format"]["type"] == "json_object"
    schema = calls[1]["response_format"]["json_schema"]["schema"]
    assert set(schema["required"]) == set(expected)
    assert schema["properties"] == {"hint": {"type": "string", "minLength": 1}}
    cached = json.loads(next((tmp_path / "cache" / stage).glob("*.json")).read_text())
    assert cached["identity"] == {"stage": stage, "version": VERSION, "request": calls[0]}
    assert cached["attempt_request"] == calls[1]
    assert cached["result"] == expected


def test_generation_retries_truncation_without_changing_prompt(tmp_path, monkeypatch):
    requests = []

    def respond(request):
        requests.append(json.loads(request.content))
        return httpx.Response(
            200,
            json={
                "choices": [
                    {
                        "finish_reason": "length" if len(requests) == 1 else "stop",
                        "message": {"content": "thinking\n</think>\nplan\n```python\nprint(1)\n```"},
                    }
                ]
            },
        )

    async def no_sleep(delay):
        pass

    monkeypatch.setattr("src.mle_policy.src.data.hindsight.client.asyncio.sleep", no_sleep)

    async def exercise():
        client = ModelClient("http://localhost/v1", "", "model", tmp_path)
        client.backend._client = client.backend._client.with_options(
            http_client=httpx.Client(transport=httpx.MockTransport(respond))
        )
        result = await client.generate([{"role": "user", "content": "task"}], generation_options())
        assert result["model"] == "model"
        await client.close()

    asyncio.run(exercise())
    assert len(requests) == 2 and requests[0] == requests[1]
    assert "max_tokens" not in requests[0]
    assert len(list((tmp_path / "errors").glob("*.json"))) == 1


def test_atomic_json_keeps_existing_file_when_serialization_fails(tmp_path):
    destination = tmp_path / "result.json"
    atomic_json(destination, {"result": "complete"})
    with pytest.raises(TypeError):
        atomic_json(destination, {"result": object()})
    assert json.loads(destination.read_text()) == {"result": "complete"}
    atomic_json(destination, {"result": "updated"})
    assert json.loads(destination.read_text()) == {"result": "updated"}


@pytest.mark.parametrize("mode", ["debug", "debug-improve"])
def test_cli_hindsight_only_roundtrip_verifier_and_downstream(tmp_path, monkeypatch, run_writer, mode):
    import src.mle_policy.src.data.hindsight.__main__ as cli

    source, output = tmp_path / "source", tmp_path / "output"
    nodes = [
        make_node(0, None),
        make_node(1, "draft", 0, metric=0.2),
        make_node(2, "improve", 1, buggy=True),
        make_node(3, "debug", 2, metric=0.8),
        make_node(4, "improve", 1, metric=0.6),
    ]
    run_dir = run_writer(source, "run-a", nodes)
    journal = run_dir / "json/JOURNAL.jsonl"
    journal.parent.mkdir()
    journal.write_text(
        "".join(json.dumps({"timestamp": "today", "step": node["step"], "data": node}) + "\n" for node in nodes)
    )

    class CliClient(FakeClient):
        def __init__(self, *args):
            super().__init__()
            self.cache = args[3]

        async def generate(self, messages, generation):
            result = await super().generate(messages, generation)
            identity = {
                "version": VERSION,
                "stage": "regenerate",
                "request": {"model": "fake-policy", "messages": messages, **generation},
            }
            digest = hashlib.sha256(json.dumps(identity, sort_keys=True).encode()).hexdigest()
            result["cache_key"] = digest
            atomic_json(self.cache / "regenerate" / f"{digest}.json", {"identity": identity, "result": result})
            return result

        async def close(self):
            pass

    monkeypatch.setattr(cli, "ModelClient", CliClient)
    args = SimpleNamespace(
        input=source,
        output=output,
        base_url="unused",
        api_key="unused",
        model="fake",
        concurrency=2,
        journal_workers=2,
        hint_code="include",
        mode=mode,
    )
    asyncio.run(run(args))
    asyncio.run(run(args))
    summary = json.loads((output / "_hindsight/summary.json").read_text())
    assert summary["journals"][0]["status"] == "cached"
    verified = verify_all(source, output)
    assert verified["totals"]["improve_episodes_added"] == (0 if mode == "debug" else 2)
    assert verified["totals"]["downstream_samples"] == (1 if mode == "debug" else 3)
    samples = list(iter_samples(output / "run-a/checkpoint/journal.jsonl", read_run_meta(output / "run-a"), "batch"))
    assert len(samples) == (1 if mode == "debug" else 3)
    if samples:
        assert {sample["episode_metric"] for sample in samples} == ({0.8} if mode == "debug" else {0.6, 0.8})
        assert all(sample["node_step"] == sample["episode_terminal_step"] for sample in samples)
        assert all(not sample["node_has_result"] and sample["exit_code"] is None for sample in samples)
        build_batch(output, tmp_path / "batch", verbose=False)
        exported = to_grpo(tmp_path / "batch", tmp_path / "grpo", use_metric_reward=True, verbose=False)
        assert exported["rows"] == (0 if mode == "debug" else 2)
        filtered = filter_positive(tmp_path / "grpo/grpo.jsonl", tmp_path / "positive.jsonl")
        assert filtered["positive_rows"] == (0 if mode == "debug" else 1)
        positives = [json.loads(line) for line in (tmp_path / "positive.jsonl").read_text().splitlines()]
        if positives:
            assert positives[0]["advantage"] > 0
            assert "hindsight" not in positives[0]
    args.mode = "debug-improve" if mode == "debug" else "debug"
    asyncio.run(run(args))
    summary = json.loads((output / "_hindsight/summary.json").read_text())
    assert summary["journals"][0]["status"] == "written"
    assert summary["mode"] == args.mode
    verified = verify_all(source, output)
    assert verified["totals"]["improve_episodes_added"] == (0 if args.mode == "debug" else 2)
    asyncio.run(run(args))
    assert json.loads((output / "_hindsight/summary.json").read_text())["journals"][0]["status"] == "cached"
    rewritten = output / "run-a/json/JOURNAL.jsonl"
    rewritten.write_text(rewritten.read_text() + "\n")
    with pytest.raises(ValueError, match="Artifact changed"):
        verify_all(source, output)


def test_tree_validation_rejects_branching_debug_and_missing_parent():
    nodes = [
        make_node(0, None),
        make_node(1, "draft", 0, buggy=True),
        make_node(2, "debug", 1),
        make_node(3, "debug", 1),
    ]
    with pytest.raises(ValueError, match="Branching debug"):
        episodes(nodes)
    with pytest.raises(ValueError, match="Invalid parent"):
        validate([make_node(1, "draft", 0)])


@pytest.mark.parametrize("bad_advantage", [None, True, float("nan"), float("inf")])
def test_positive_filter_rejects_missing_or_invalid_advantage(tmp_path, bad_advantage):
    source = tmp_path / "input.jsonl"
    source.write_text(json.dumps({"advantage": bad_advantage}) + "\n")
    destination = tmp_path / "output.jsonl"
    destination.write_text("existing\n")
    with pytest.raises(ValueError, match="finite computed advantage"):
        filter_positive(source, destination)


def test_positive_filter_is_strict_without_tree_metadata(tmp_path):
    rows = [{"advantage": advantage} for advantage in (-1, 0, 1)]
    source = tmp_path / "input.jsonl"
    source.write_text("".join(json.dumps(row) + "\n" for row in rows))
    report = filter_positive(source, tmp_path / "output.jsonl")
    assert report["positive_rows"] == 1 and report["nonpositive_rows"] == 2
    assert json.loads((tmp_path / "output.jsonl").read_text()) == rows[2]
    source.write_text(json.dumps({"advantage": 1}) + "\n")
    assert filter_positive(source, tmp_path / "plain.jsonl")["positive_rows"] == 1
