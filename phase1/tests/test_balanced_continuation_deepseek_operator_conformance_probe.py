from __future__ import annotations

import argparse
import json
from pathlib import Path

from phase1.balanced_continuation_deepseek_operator_conformance_probe import run


def write_json(path: Path, value: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, sort_keys=True) + "\n", encoding="utf-8")


def complete_script() -> str:
    padding = "\n".join(f"feature_{index} = {index}" for index in range(30))
    return f"""```python
import pandas as pd
from sklearn.model_selection import KFold
train = pd.read_csv("./data/train.csv")
test = pd.read_csv("./data/test.csv")
{padding}
score = 0.5
submission = pd.DataFrame({{"id": test.iloc[:, 0], "target": 0.5}})
submission.to_csv("submission.csv", index=False)
print(f"FINAL_VALIDATION_SCORE: {{score}}")
```"""


def add_rollout(run: Path, task: str, rollout: str) -> None:
    root = run / "worker_outputs" / rollout
    write_json(root / "result.json", {"task": task, "rollout_id": rollout})
    write_json(root / "steps" / "step_000" / "execution.json", {"execution_status": "ok"})
    (root / "steps" / "step_000" / "submission.csv").write_text(
        "id,target\n1,0.5\n", encoding="utf-8"
    )
    previous = "import pandas as pd\n" + "\n".join(
        f"x_{index} = {index}" for index in range(50)
    )
    write_json(root / "steps" / "step_001" / "operator_request.json", {
        "operator": "debug",
        "previous_is_buggy": True,
        "task_description": f"Description for {task}",
        "previous_code": previous,
        "previous_code_sha256": "f" * 64,
        "previous_terminal_output": "FINAL_VALIDATION_SCORE: 0.5",
        "execution_timeout_seconds": 600,
    })


def test_production_profile_two_call_gate_is_execution_free(tmp_path: Path) -> None:
    run_root = tmp_path / "run"
    write_json(run_root / "final_status.json", {
        "status": "VERIFIED_COMPLETE_REAL_E1_COLLECTION",
        "collection_rc": 0,
    })
    add_rollout(run_root, "spaceship-titanic", "b" * 64)
    add_rollout(run_root, "tabular-playground-series-may-2022", "c" * 64)
    prompts: list[str] = []

    def caller(prompt: str) -> dict:
        prompts.append(prompt)
        return {
            "content": complete_script(),
            "response_channel": "content",
            "provider_request_id": f"request-{len(prompts)}",
            "finish_reason": "stop",
            "latency_seconds": 0.1,
            "prompt_tokens": 100,
            "completion_tokens": 200,
            "total_tokens": 300,
        }

    output = tmp_path / "output"
    summary = run(
        argparse.Namespace(run_root=str(run_root), output_root=str(output)), caller=caller
    )
    assert len(prompts) == 2
    assert summary["status"] == "PASS_PRODUCTION_MODEL_OPERATOR_GATE"
    assert summary["production_profile_exact_match"] is True
    assert summary["model_id"] == "deepseek-v4-flash"
    assert summary["temperature"] == 0.6 and summary["top_p"] == 0.95
    assert summary["client_timeout_seconds"] == 180
    assert summary["api_calls"] == 2
    assert summary["gpu_jobs_started"] == 0
    assert summary["candidate_executions"] == 0
    assert summary["method_claim_allowed"] is False
    assert summary["new_gpu_budget_still_required"] is True
    assert summary["e2_e3_unlocked"] is False
    assert all(row["gate_pass"] for row in summary["records"])


def test_one_nonconforming_response_fails_whole_gate(tmp_path: Path) -> None:
    run_root = tmp_path / "run"
    write_json(run_root / "final_status.json", {
        "status": "VERIFIED_COMPLETE_REAL_E1_COLLECTION",
        "collection_rc": 0,
    })
    add_rollout(run_root, "spaceship-titanic", "b" * 64)
    add_rollout(run_root, "tabular-playground-series-may-2022", "c" * 64)
    calls = 0

    def caller(_: str) -> dict:
        nonlocal calls
        calls += 1
        return {
            "content": complete_script() if calls == 1 else "truncated",
            "response_channel": "content",
            "provider_request_id": f"request-{calls}",
            "finish_reason": "stop" if calls == 1 else "length",
            "latency_seconds": 0.1,
            "prompt_tokens": 100,
            "completion_tokens": 200 if calls == 1 else 8192,
            "total_tokens": 300 if calls == 1 else 8292,
        }

    summary = run(
        argparse.Namespace(run_root=str(run_root), output_root=str(tmp_path / "output")),
        caller=caller,
    )
    assert calls == 2
    assert summary["status"] == "FAIL_PRODUCTION_MODEL_OPERATOR_GATE"
    assert summary["production_operator_engineering_gate_passed"] is False
    assert summary["records"][1]["at_output_token_cap"] is True


def test_launcher_is_clean_pinned_and_credential_free() -> None:
    launcher = (
        Path(__file__).resolve().parents[1]
        / "scripts"
        / "launch_balanced_continuation_deepseek_operator_probe_20260814.sh"
    ).read_text(encoding="utf-8")
    assert "rev-parse HEAD" in launcher
    assert "status --porcelain" in launcher
    assert "api_calls_cap=2" in launcher
    assert "gpu_jobs_cap=0" in launcher
    assert "candidate_executions_cap=0" in launcher
    assert "rc=$?" in launcher and 'exit "$rc"' in launcher
    assert "PRIMARY_KEY_DEEPSEEK_V4_FLASH=" not in launcher
    assert launcher.index('source "${HOME}/env_setup.sh"') < launcher.index("set -u")
