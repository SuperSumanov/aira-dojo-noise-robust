"""Helpers for building tiny fake dojo runs on disk."""

import json

import pytest

DEFAULT_MEDIAN = 0.5
DEFAULT_GOLD = 0.8


def journal_node(step, *, calls, buggy, score=None, parents=(), is_lower_better=False):
    """One journal line.  ``calls`` is a list of ``(operator, prompt, completion)``."""
    metrics = [
        {
            "usage": {"completion_tokens": len(completion), "prompt_tokens": len(prompt)},
            "prompt_messages": [{"role": "system", "content": prompt}],
            "completion_text": completion,
        }
        for _, prompt, completion in calls
    ]
    metric_info = {}
    if score is not None:
        metric_info = {
            "score": score,
            "median_threshold": DEFAULT_MEDIAN,
            "gold_threshold": DEFAULT_GOLD,
            "is_lower_better": is_lower_better,
        }
    return {
        "step": step,
        "id": f"node-{step}",
        "parents": list(parents),
        "is_buggy": buggy,
        "metric": None if buggy else score,
        "metric_info": metric_info,
        "exit_code": 1 if buggy else 0,
        "operators_used": [operator for operator, _, _ in calls],
        "operators_metrics": metrics,
    }


def write_run(
    batch_dir,
    run_id,
    nodes,
    *,
    task="spaceship-titanic",
    hardware="A100",
    provider="openai",
    model="deepseek-v4-flash",
    base_url="https://api.example.com",
    time_limit_secs=7200,
    execution_timeout=1200,
    num_children=2,
    launch_time="2026-07-28 13:27:55",
):
    """Write ``<batch_dir>/<run_id>/{dojo_config.json,checkpoint/journal.jsonl}``."""
    run_dir = batch_dir / run_id
    (run_dir / "checkpoint").mkdir(parents=True, exist_ok=True)
    (run_dir / "dojo_config.json").write_text(
        json.dumps(
            {
                "id": run_id,
                "metadata": {"seed": 1, "launch_time": launch_time},
                "task": {"name": task},
                "solver": {
                    "time_limit_secs": time_limit_secs,
                    "execution_timeout": execution_timeout,
                    "num_children": num_children,
                    "operators": {
                        "draft": {
                            "llm": {"client": {"provider": provider, "model_id": model, "base_url": base_url}}
                        }
                    },
                },
            }
        ),
        encoding="utf-8",
    )
    (run_dir / "env_variables.json").write_text(json.dumps({"HARDWARE": hardware}), encoding="utf-8")
    with (run_dir / "checkpoint" / "journal.jsonl").open("w", encoding="utf-8") as handle:
        for node in nodes:
            handle.write(json.dumps(node) + "\n")
    return run_dir


@pytest.fixture
def run_writer():
    return write_run


@pytest.fixture
def node_builder():
    return journal_node
