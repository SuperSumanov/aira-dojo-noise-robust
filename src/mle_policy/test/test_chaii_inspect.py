"""Shared reasoning/code analysis and offline comparison regression tests."""

import json
import sys

import pytest

from mle_policy.src.self_distillation.chaii_test.evaluation import (
    analyze_record,
    length_summary,
    proportion,
    response_mode,
    summarize,
)
from mle_policy.src.self_distillation.chaii_test.inspect import compare_reports, comparison_table, inspect_run, main


def record(content, reasoning=None, reasoning_key="reasoning_content", finish="stop", tokens=20):
    message = {"content": content}
    if reasoning is not None:
        message[reasoning_key] = reasoning
    return {"sample_index": 0, "finish_reason": finish, "response": {
        "choices": [{"message": message, "finish_reason": finish}], "usage": {"completion_tokens": tokens},
    }}


@pytest.mark.parametrize("thought,identifier,description", [
    ("use_fast=False", True, True),
    ("XLMRobertaTokenizerFast", True, True),
    ("BertTokenizerFast", True, True),
    ("Use fast tokenizers for offsets", False, True),
    ("fast-tokenizer", False, True),
    ("fast tokenization", False, True),
    ("training is fast; tokenizer is slow", False, False),
    ("abuse_fast", False, False),
])
def test_thinking_knowledge(thought, identifier, description):
    row = analyze_record(record(thought + "</think>\n```python\nprint(1)\n```"))
    assert row["thinking_explicit_identifier"] is identifier
    assert row["thinking_including_description"] is description
    assert not row["final_code_explicit_identifier"]
    assert row["thinking_closed"] is True


@pytest.mark.parametrize("key", ["reasoning", "reasoning_content"])
def test_separate_reasoning(key):
    row = analyze_record(record("```python\nuse_fast=True\n```", "fast tokenizer", key))
    assert row["thinking_including_description"]
    assert not row["thinking_explicit_identifier"]
    assert row["final_code_explicit_identifier"]
    assert row["thinking_closed"] is True
    assert row["thinking_format"] == "separate"


@pytest.mark.parametrize("mode,opening", [("thinking", ""), ("auto", "<think>")])
@pytest.mark.parametrize("finish", ["stop", "length"])
def test_unclosed_thought_code_is_not_final(mode, opening, finish):
    row = analyze_record(record(opening + "Thought\n```python\nXLMRobertaTokenizerFast()\n```", finish=finish), mode)
    assert row["thinking_explicit_identifier"]
    assert row["thinking_closed"] is False
    assert row["premature_stop"] is (finish == "stop")
    assert row["truncated"] is (finish == "length")
    assert not row["has_code"]
    assert not row["final_code_explicit_identifier"]


def test_empty_reasoning_field_does_not_hide_unclosed_thinking():
    row = analyze_record(record("Thinking use_fast", ""), "thinking")
    assert row["thinking_closed"] is False
    assert row["thinking_explicit_identifier"]


def test_code_only_output_and_no_think_denominator():
    row = analyze_record(record("```python\nuse_fast=True\n```"), "answer")
    assert row["thinking_closed"] is None
    assert not row["thinking_explicit_identifier"]
    assert row["final_code_explicit_identifier"]
    assert row["valid_final_code"]
    assert summarize([row])["metrics"]["thinking_closed"]["total"] == 0


def test_final_answer_prose_is_not_code_knowledge():
    row = analyze_record(record("Thought</think>Use XLMRobertaTokenizerFast.\n```python\nprint(1)\n```"))
    assert not row["final_code_explicit_identifier"]


def test_truncated_final_code_retains_knowledge_but_not_completeness():
    row = analyze_record(record("Thought</think>\n```python\nuse_fast=True", finish="length"))
    assert row["thinking_closed"] is True
    assert row["final_code_explicit_identifier"]
    assert not row["code_fences_closed"]
    assert not row["valid_final_code"]
    assert row["truncated"]


def test_identifier_is_lexical_constructor_is_structural():
    row = analyze_record(record("```python\n# use_fast=True\nprint('BertTokenizerFast')\n```"))
    assert row["final_code_explicit_identifier"]
    assert not row["explicit_fast_constructor"]
    slow = analyze_record(record("```python\nXLMRobertaTokenizer.from_pretrained('model', use_fast=True)\n```"))
    assert slow["slow_class_use_fast"]
    assert not slow["explicit_fast_constructor"]
    fast = analyze_record(record("```python\nAutoTokenizer.from_pretrained('model', use_fast=True)\n```"))
    assert fast["explicit_fast_constructor"]


def test_multiple_code_blocks_and_invalid_syntax():
    row = analyze_record(record("```python\nuse_fast=True\n```\n```python\nnot valid python syntax here!\n```"))
    assert row["final_code_explicit_identifier"]
    assert not row["valid_final_code"]
    assert row["syntax_error"]


def test_non_python_fences_do_not_leak_into_python_blocks():
    row = analyze_record(record("```json\n{\"use_fast\": true}\n```\n```python\nprint(1)\n```"))
    assert row["code_blocks"] == 1
    assert not row["final_code_explicit_identifier"]
    assert row["valid_final_code"]


def test_missing_usage_errors_and_stop_only_rates():
    missing_usage = record("use_fast", finish="length")
    del missing_usage["response"]["usage"]
    rows = [analyze_record(missing_usage, "thinking"), analyze_record(record("plain")),
            {"sample_index": 2, "error": "test failure"}]
    summary = summarize(rows)
    assert (summary["failed"], summary["truncated"], summary["completed"]) == (1, 1, 3)
    assert summary["metrics"]["thinking_explicit_identifier"]["rate"] == 0.5
    assert summary["stop_only_metrics"]["thinking_explicit_identifier"]["rate"] == 0
    assert summary["lengths"]["completion_tokens"]["count"] == 1
    assert summary["metrics"]["thinking_closed"]["total"] == 1


def test_wilson_and_length_statistics():
    assert proportion(0, 0)["rate"] is None
    assert proportion(5, 10)["wilson_95"] == pytest.approx([0.236593, 0.763407], abs=1e-6)
    assert length_summary([1, 2, 3, 4, 5, 6, 7, 8, 9, 10, None]) == {
        "count": 10, "mean": 5.5, "median": 5.5, "p90": 9, "min": 1, "max": 10,
    }
    assert length_summary([])["mean"] is None


def test_auto_mode_uses_request_not_generation_overrides():
    request = {"chat_template_kwargs": {"enable_thinking": True}}
    assert response_mode(request) == "thinking"
    assert response_mode(request, "answer") == "answer"
    assert response_mode({}) == "auto"
    assert response_mode({"reasoning_effort": "medium"}) == "thinking"
    assert response_mode({"reasoning_effort": "medium", "chat_template_kwargs": {"enable_thinking": False}}) == "answer"


def test_offline_recomputes_old_indicators_and_compares_lengths(tmp_path):
    reports = []
    for name, tokens, thought in [("base", 10, "plain"), ("adapter", 30, "fast tokenizer")]:
        directory = tmp_path / name
        directory.mkdir()
        raw = record(thought, tokens=tokens)
        raw["indicators"] = {"use_fast": False}
        (directory / "responses.jsonl").write_text(json.dumps(raw) + "\n")
        (directory / "request.json").write_text(json.dumps({"request": {
            "chat_template_kwargs": {"enable_thinking": True}, "model": name,
        }}))
        reports.append(inspect_run(directory / "responses.jsonl"))
    assert reports[1]["metrics"]["thinking_including_description"]["hits"] == 1
    assert not reports[1]["samples"][0]["has_code"]
    difference = compare_reports(reports)[1]
    assert difference["length_changes"]["completion_tokens"] == {"mean_delta": 20, "mean_ratio": 3}
    assert difference["rate_delta_percentage_points"]["thinking_including_description"] == 100
    assert "思考：明确标识符" in comparison_table(reports)
    assert "30/30" in comparison_table(reports)


def test_offline_cli_writes_json_and_markdown(tmp_path, monkeypatch, capsys):
    responses = tmp_path / "responses.jsonl"
    responses.write_text(json.dumps(record("use_fast=True")) + "\n")
    output = tmp_path / "report" / "comparison.json"
    monkeypatch.setattr(sys, "argv", ["inspect", "--responses", str(responses),
                                    "--response-mode", "thinking", "--output", str(output)])
    main()
    report = json.loads(output.read_text())
    assert report["schema_version"] == 2
    assert report["reports"][0]["metrics"]["thinking_explicit_identifier"]["hits"] == 1
    assert output.with_suffix(".md").read_text().strip() == capsys.readouterr().out.strip()


def test_all_failed_and_empty_runs_have_no_fake_rates(tmp_path):
    path = tmp_path / "responses.jsonl"
    for text in ("", json.dumps({"sample_index": 0, "error": "HTTP failure"}) + "\n"):
        path.write_text(text)
        report = inspect_run(path)
        assert report["metrics"]["thinking_explicit_identifier"]["rate"] is None
        assert report["lengths"]["completion_tokens"]["count"] == 0
        assert compare_reports([report])[0]["length_changes"]["completion_tokens"]["mean_ratio"] is None
