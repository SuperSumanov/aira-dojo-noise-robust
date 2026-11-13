import asyncio
import copy
import json
from pathlib import Path
import subprocess
from types import SimpleNamespace

import pytest

from src.mle_policy.src.data.hindsight.__main__ import rewrite, run
from src.mle_policy.src.data.hindsight.helper import write_json, parts
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


@pytest.fixture(autouse=True)
def model_credentials(monkeypatch):
    monkeypatch.setenv("PRIMARY_KEY", "test-key")


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
        def __init__(self, config, semaphore):
            super().__init__()
            self.config = config
            self.semaphore = semaphore
            clients.append(self)

        async def close(self):
            pass

    fixture = Path(__file__).parent / "fixtures/hindsight/run/json/JOURNAL.jsonl"
    monkeypatch.setattr(experiment, "ModelClient", ExperimentClient)
    args = SimpleNamespace(
        journal=fixture,
        output=tmp_path,
        case=["debug:1:1", "improve:1:3"],
        concurrency=2,
    )
    asyncio.run(experiment.compare(args))
    assert {path.name for path in tmp_path.iterdir()} == {
        case.replace(":", "-") + suffix for case in args.case for suffix in ("-hint-only", "-with-code")
    }
    source_operators = json.loads((fixture.parent.parent / "dojo_config.json").read_text())["solver"]["operators"]
    assert [client.config for client in clients] == [
        settings["llm"]["client"] for settings in source_operators.values()
    ]
    assert all(client.semaphore is clients[0].semaphore for client in clients)
    client = clients[0]
    assert sum(stage.endswith("_hint") for stage, _ in client.requests) == 2
    assert sum(stage == "regenerate" for stage, _ in client.requests) == 4
    for case in args.case:
        traces = []
        for suffix in ("-hint-only", "-with-code"):
            directory = tmp_path / (case.replace(":", "-") + suffix)
            assert {path.name for path in directory.iterdir()} == {"trace.json", "nodes.json", "metadata.json"}
            trace = json.loads((directory / "trace.json").read_text())
            traces.append(trace)
            assert trace["hint"][-1]["stage"] == case.split(":")[0] + "_hint"
            assert ("regenerate", trace["rewrite"]["messages"]) in client.requests
            nodes = json.loads((directory / "nodes.json").read_text())
            validate(nodes)
            rewritten = rewrites(nodes)[0]
            assert rewritten["operators_metrics"][0]["completion_text"] == trace["rewrite"]["result"]["completion"]
            assert rewritten["parents"] == [0]
            assert "Preserve tensor dimensions" not in str(rewritten["operators_metrics"][0]["prompt_messages"])
            assert rewritten["hindsight"]["metric_source"]["step"] == (2 if case.startswith("debug") else 3)
        assert traces[0]["hint"] == traces[1]["hint"]


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
    output = asyncio.run(rewrite(nodes, dict.fromkeys(("draft", "improve"), FakeClient())))
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
    output = asyncio.run(
        rewrite(
            nodes,
            dict.fromkeys(("draft", "improve"), client),
            include_code=include_code,
            source_journal="run/json/JOURNAL.jsonl",
        )
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
    assert "experience" not in json.dumps(output)
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
    assert augmented[-1]["content"].startswith("\n\n<experience>")
    assert augmented[-1]["content"].endswith(
        "</experience>" + nodes[1]["operators_metrics"][0]["prompt_messages"][-1]["content"]
    )
    assert ("print(2)" in augmented[-1]["content"]) == include_code
    hint_payload = next(payload for stage, payload in client.requests if stage == "debug_hint")
    assert hint_payload["target_trajectory"][0]["execution_output"] == "traceback"
    assert added["step"] == 3
    assert len(episodes(output)) == 1


def test_improve_inherits_donor_metric_and_keeps_generated_code():
    nodes = [
        make_node(0, None),
        make_node(1, "draft", 0, metric=0.2),
        make_node(2, "improve", 1, buggy=True),
        make_node(3, "debug", 2, metric=0.8),
    ]
    result = asyncio.run(rewrite(nodes, dict.fromkeys(("draft", "improve"), FakeClient())))
    assert sorted(node["hindsight"]["stage"] for node in rewrites(result)) == ["debug", "improve"]
    added = next(node for node in rewrites(result) if node["hindsight"]["stage"] == "improve")
    assert added["code"] == "print('new')"
    assert added["metric"] == 0.8 and added["operators_used"] == ["draft"]
    assert added["parents"] == [0]
    assert added["operators_metrics"][0]["prompt_messages"] == nodes[1]["operators_metrics"][0]["prompt_messages"]
    assert added["hindsight"]["donor_trajectory"] == [{"step": 2, "id": "node-2"}, {"step": 3, "id": "node-3"}]
    assert all(node["operators_used"] != ["debug"] for node in result)
    assert all(len(episode.steps) == 1 for episode in episodes(result))
    assert [node["operators_used"] for node in rewrites(result) if node["hindsight"]["stage"] == "improve"] == [
        ["draft"]
    ]


def test_improve_can_rewrite_an_implement_episode_that_needed_debugging():
    nodes = [
        make_node(0, None),
        make_node(1, "draft", 0, buggy=True),
        make_node(2, "debug", 1, metric=0.2),
        make_node(3, "improve", 2, metric=0.8),
    ]
    result = asyncio.run(rewrite(nodes, dict.fromkeys(("draft", "improve"), FakeClient())))
    added = next(node for node in rewrites(result) if node["hindsight"]["stage"] == "improve")
    assert added["operators_used"] == ["draft"]
    assert added["hindsight"]["prompt_source"]["step"] == 1
    assert added["hindsight"]["target_trajectory"] == [{"step": 1, "id": "node-1"}, {"step": 2, "id": "node-2"}]
    assert added["code"] == "print('new')" and added["parents"] == [0]
    assert [node["operators_used"] for node in rewrites(result) if node["hindsight"]["stage"] == "improve"] == [
        ["draft"]
    ]


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
    result = asyncio.run(rewrite(nodes, dict.fromkeys(("draft", "improve"), client), mode=mode))
    assert nodes == original
    assert {
        node["hindsight"]["prompt_source"]["step"]
        for node in rewrites(result)
        if node["hindsight"]["stage"] == "debug"
    } == {1, 4}
    assert sum(node["hindsight"]["stage"] == "improve" for node in rewrites(result)) == improve_count
    assert len(rewrites(result)) == 2 + improve_count
    assert sum(stage == "improve_hint" for stage, _ in client.requests) == improve_count
    assert {stage for stage, _ in client.requests} <= {"debug_hint", "improve_hint", "regenerate"}


def test_rewrite_rejects_unknown_mode():
    with pytest.raises(ValueError, match="Unknown hindsight mode"):
        asyncio.run(rewrite([], dict.fromkeys(("draft", "improve"), FakeClient()), mode="improve"))


def test_no_rewrite_produces_empty_journal():
    result = asyncio.run(
        rewrite([make_node(0, None), make_node(1, "draft", 0)], dict.fromkeys(("draft", "improve"), FakeClient()))
    )
    assert result == []


@pytest.mark.parametrize("maximize", [True, False])
def test_improvement_uses_cv_direction_not_official_score(maximize):
    nodes = [
        make_node(0, None),
        make_node(1, "draft", 0, metric=0.5, maximize=maximize),
        make_node(2, "improve", 1, metric=0.8 if maximize else 0.2, maximize=maximize),
    ]
    nodes[2]["metric_info/score"] = 0
    result = asyncio.run(rewrite(nodes, dict.fromkeys(("draft", "improve"), FakeClient())))
    assert sum(node["hindsight"]["stage"] == "improve" for node in rewrites(result)) == 1
    assert "metric_info/score" not in rewrites(result)[0]


def test_unresolved_and_tied_episodes_have_no_improvement():
    nodes = [
        make_node(0, None),
        make_node(1, "draft", 0),
        make_node(2, "improve", 1),
        make_node(3, "improve", 2, buggy=True),
    ]
    result = asyncio.run(rewrite(nodes, dict.fromkeys(("draft", "improve"), FakeClient())))
    assert result == []
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


class Completion:
    def __init__(self, content, *, reasoning=None, finish_reason="stop"):
        self.choices = [
            SimpleNamespace(
                message=SimpleNamespace(content=content, reasoning_content=reasoning),
                finish_reason=finish_reason,
            )
        ]

    def to_dict(self):
        return {"usage": {"prompt_tokens": 10, "completion_tokens": 5}}


@pytest.fixture
def client_config():
    return {
        "base_url": "http://source/v1",
        "model_id": "fixture-model",
        "provider": "selfhosted",
        "use_azure_client": False,
    }


@pytest.mark.parametrize("separate_reasoning", [False, True])
def test_generation_native_reasoning_through_litellm(tmp_path, monkeypatch, client_config, separate_reasoning):
    import dojo.core.solvers.llm_helpers.backends.lite_llm as backend

    calls = []

    async def respond(**request):
        calls.append(request)
        answer = "plan\n```python\nprint(1)\n```"
        return Completion(
            answer if separate_reasoning else "Let me think.\n</think>\n\n" + answer,
            reasoning="Let me think." if separate_reasoning else None,
        )

    monkeypatch.setattr(backend, "completion_fn", respond)
    client = ModelClient(client_config, asyncio.Semaphore(2))
    result = asyncio.run(client.generate([{"role": "user", "content": "task"}], generation_options()))
    assert result["completion"].startswith("Let me think.\n</think>")
    assert result["model"] == "fixture-model"
    assert result["usage"]["total_tokens"] == 15
    assert len(calls) == 1
    assert calls[0]["model"] == "openai/fixture-model"
    assert calls[0]["base_url"] == "http://source/v1"
    assert calls[0]["api_key"] == "test-key"
    assert "include_reasoning" not in calls[0]
    assert "response_format" not in calls[0]
    assert calls[0]["chat_template_kwargs"]["enable_thinking"] is True
    assert calls[0]["max_retries"] == backend.NUM_RETRIES
    assert not list(tmp_path.iterdir())


@pytest.mark.parametrize(
    "method,part", [("debug_hint", False), ("debug_hint", True), ("improve_hint", False), ("improve_hint", True)]
)
def test_hint_reuses_litellm_schema_retries_and_thinking_parser(tmp_path, monkeypatch, client_config, method, part):
    import dojo.core.solvers.llm_helpers.backends.lite_llm as backend

    calls = []
    messages = [{"role": "user", "content": "input"}]

    async def respond(**request):
        calls.append(request)
        content = '{"hint": 3}' if len(calls) == 1 else '<think>reasoning</think>\n```json\n{"hint": "advice"}\n```'
        return Completion(content)

    monkeypatch.setattr(backend, "completion_fn", respond)
    client = ModelClient(client_config, asyncio.Semaphore(2))
    result = asyncio.run(getattr(client, method)(messages, part=part))
    assert result == {"hint": "advice"}
    assert len(calls) == 2
    assert messages == [{"role": "user", "content": "input"}]
    assert calls[0]["response_format"] == {"type": "json_object"}
    assert "JSON Schema" in calls[0]["messages"][0]["content"]
    assert "chat_template_kwargs" not in calls[0]
    assert calls[0]["max_tokens"] == 8192
    assert not list(tmp_path.iterdir())


@pytest.mark.parametrize("finish_reason", ["length", "content_filter"])
def test_generation_rejects_incomplete_response(monkeypatch, client_config, finish_reason):
    import dojo.core.solvers.llm_helpers.backends.lite_llm as backend

    async def respond(**request):
        return Completion("thinking\n</think>\nplan\n```python\nprint(1)\n```", finish_reason=finish_reason)

    monkeypatch.setattr(backend, "completion_fn", respond)
    client = ModelClient(client_config, asyncio.Semaphore(2))
    with pytest.raises(ValueError, match="Incomplete generation"):
        asyncio.run(client.generate([{"role": "user", "content": "task"}], generation_options()))


def test_shared_litellm_plain_response_still_omits_separate_reasoning(monkeypatch, client_config):
    import dojo.core.solvers.llm_helpers.backends.lite_llm as backend

    async def respond(**request):
        return Completion("answer", reasoning="thinking")

    monkeypatch.setattr(backend, "completion_fn", respond)
    client = backend.LiteLLMClient(SimpleNamespace(**client_config))
    output, _ = asyncio.run(client.query([{"role": "user", "content": "task"}]))
    assert output == "answer"


def test_write_json_creates_readable_artifact(tmp_path):
    path = tmp_path / "nested/result.json"
    write_json(path, {"hint": "advice"})
    assert json.loads(path.read_text()) == {"hint": "advice"}
    assert list(path.parent.iterdir()) == [path]


@pytest.mark.parametrize("mode", ["debug", "debug-improve"])
@pytest.mark.parametrize(
    "overrides",
    [{}, {"base_url": "http://local/v1"}, {"model_id": "local-model"},
     {"base_url": "http://local/v1", "model_id": "local-model"}],
)
def test_cli_hindsight_only_roundtrip_verifier_and_downstream(tmp_path, monkeypatch, run_writer, mode, overrides):
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
    config_path = run_dir / "dojo_config.json"
    config = json.loads(config_path.read_text())
    config["solver"]["operators"]["improve"] = copy.deepcopy(config["solver"]["operators"]["draft"])
    config_path.write_text(json.dumps(config))
    journal = run_dir / "json/JOURNAL.jsonl"
    journal.parent.mkdir()
    journal.write_text(
        "".join(json.dumps({"timestamp": "today", "step": node["step"], "data": node}) + "\n" for node in nodes)
    )

    class CliClient(FakeClient):
        def __init__(self, client_config, semaphore):
            super().__init__()
            expected = {**config["solver"]["operators"]["draft"]["llm"]["client"], **overrides}
            assert client_config == expected

        async def close(self):
            pass

    monkeypatch.setattr(cli, "ModelClient", CliClient)
    args = SimpleNamespace(
        input=source,
        output=output,
        concurrency=2,
        journal_workers=2,
        hint_code="include",
        mode=mode,
        base_url=overrides.get("base_url"),
        model_id=overrides.get("model_id"),
    )
    asyncio.run(run(args))
    asyncio.run(run(args))
    assert not (output / "_hindsight").exists()
    verified = verify_all(source, output, mode)
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
    verified = verify_all(source, output, args.mode)
    assert verified["totals"]["improve_episodes_added"] == (0 if args.mode == "debug" else 2)
    assert not (output / "_hindsight").exists()
    rewritten = output / "run-a/json/JOURNAL.jsonl"
    rows = [json.loads(line) for line in rewritten.read_text().splitlines()]
    rows[-1]["data"]["code"] = "changed"
    rewritten.write_text("\n".join(json.dumps(row) for row in rows))
    with pytest.raises(ValueError, match="Generated code mismatch"):
        verify_all(source, output, args.mode)


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


def test_model_concurrency_is_shared_by_hints_and_full_generation(monkeypatch, client_config):
    import dojo.core.solvers.llm_helpers.backends.lite_llm as backend

    async def exercise():
        client = ModelClient(client_config, asyncio.Semaphore(2))
        active = 0
        maximum = 0

        async def respond(**request):
            nonlocal active, maximum
            active += 1
            maximum = max(maximum, active)
            await asyncio.sleep(0)
            active -= 1
            return Completion(
                '{"hint": "advice"}'
                if "response_format" in request
                else "thinking\n</think>\nplan\n```python\nprint(1)\n```"
            )

        monkeypatch.setattr(backend, "completion_fn", respond)
        messages = [{"role": "user", "content": "task"}]
        await asyncio.gather(
            *(
                client.debug_hint(messages) if index % 2 else client.generate(messages, generation_options())
                for index in range(8)
            )
        )
        assert maximum == 2

    asyncio.run(exercise())


def test_hint_exhausts_shared_structured_output_attempts(tmp_path, monkeypatch, client_config):
    import dojo.core.solvers.llm_helpers.backends.lite_llm as backend

    calls = []

    async def respond(**request):
        calls.append(request)
        return Completion('{"hint": 3}')

    monkeypatch.setattr(backend, "completion_fn", respond)
    client = ModelClient(client_config, asyncio.Semaphore(2))
    with pytest.raises(ValueError, match="Invalid structured output after 3 attempt"):
        asyncio.run(client.debug_hint([{"role": "user", "content": "task"}]))
    assert len(calls) == backend.STRUCTURED_OUTPUT_RETRIES + 1
    assert not list(tmp_path.iterdir())


@pytest.mark.parametrize("model_key", [False, True])
def test_model_client_reads_existing_dotenv_credentials(tmp_path, monkeypatch, model_key, client_config):
    import src.mle_policy.src.data.hindsight.client as client_module
    from dotenv import load_dotenv

    path = tmp_path / ".env"
    path.write_text("PRIMARY_KEY=dotenv-key\n" + ("PRIMARY_KEY_FIXTURE_MODEL=dotenv-model-key\n" if model_key else ""))
    monkeypatch.delenv("PRIMARY_KEY")
    monkeypatch.delenv("PRIMARY_KEY_FIXTURE_MODEL", raising=False)
    monkeypatch.setattr(client_module, "load_dotenv", lambda: load_dotenv(path))

    client = ModelClient(client_config, asyncio.Semaphore(2))
    assert client.model == "fixture-model"
    assert client.backend.base_url == "http://source/v1"
    assert client.backend.api_key == ("dotenv-model-key" if model_key else "dotenv-key")


def test_rewrite_selects_target_operator_client():
    nodes = [
        make_node(0, None),
        make_node(1, "draft", 0, buggy=True),
        make_node(2, "debug", 1, metric=0.2),
        make_node(3, "improve", 2, buggy=True),
        make_node(4, "debug", 3, metric=0.8),
    ]
    draft, improve = FakeClient(), FakeClient()
    asyncio.run(rewrite(nodes, {"draft": draft, "improve": improve}))
    assert [stage for stage, _ in draft.requests] == ["debug_hint", "regenerate", "improve_hint", "regenerate"]
    assert [stage for stage, _ in improve.requests] == ["debug_hint", "regenerate"]


@pytest.mark.parametrize(
    "module",
    [
        "mle_policy.src.data.hindsight",
        "mle_policy.src.data.hindsight.experiment",
        "mle_policy.src.data.hindsight.exp.evaluate",
    ],
)
def test_cli_model_overrides_and_no_credential_override(module):
    import sys

    result = subprocess.run([sys.executable, "-m", module, "--help"], capture_output=True, text=True, check=True)
    assert "--api-key" not in result.stdout
    if module.endswith("experiment"):
        assert "--base-url" not in result.stdout
        assert "--model-id" not in result.stdout
    else:
        assert "--base-url" in result.stdout
        assert "--model-id" in result.stdout


@pytest.mark.parametrize(
    "content",
    [
        "<think>reasoning</think>\nplan\n```python\nprint(1)\n```",
        "plan\n```python\nprint(1)\n```",
    ],
)
def test_full_response_keeps_inline_thinking_without_duplication(monkeypatch, client_config, content):
    import dojo.core.solvers.llm_helpers.backends.lite_llm as backend

    async def respond(**request):
        return Completion(content, reasoning="separate reasoning")

    monkeypatch.setattr(backend, "completion_fn", respond)
    client = ModelClient(client_config, asyncio.Semaphore(2))
    result = asyncio.run(client.generate([{"role": "user", "content": "task"}], generation_options()))
    assert result["completion"].count("</think>") == 1
    if "</think>" in content:
        assert result["completion"] == content


def test_hint_reuses_shared_tools_transport_when_json_mode_is_unsupported(monkeypatch, client_config):
    import dojo.core.solvers.llm_helpers.backends.lite_llm as backend

    calls = []

    async def respond(**request):
        calls.append(request)
        if "response_format" in request:
            raise backend.litellm.BadRequestError(
                message="response_format json_object unsupported",
                model="fixture-model",
                llm_provider="openai",
            )
        completion = Completion(None)
        completion.choices[0].message.tool_calls = [
            SimpleNamespace(
                function=SimpleNamespace(name="debug_hint", arguments='{"hint": "advice"}'),
            )
        ]
        return completion

    monkeypatch.setattr(backend, "completion_fn", respond)
    client = ModelClient(client_config, asyncio.Semaphore(2))
    assert asyncio.run(client.debug_hint([{"role": "user", "content": "task"}])) == {"hint": "advice"}
    assert len(calls) == 2
    assert calls[1]["tool_choice"]["function"]["name"] == "debug_hint"
