from __future__ import annotations

import json
import sys
from pathlib import Path

from phase1 import build_schema_probe_repair_manifest as builder
from phase1 import extract_schema_probe_repair_manifest as extractor


def write_json(path: Path, payload: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, sort_keys=True) + "\n", encoding="utf-8")


def contract_code(label: str) -> str:
    return f'''
import os
probe = "candidate_probe.csv"
os.replace("{label}.tmp", probe)
os.fsync(1)
print("CANDIDATE_PROBE_READY elapsed_s=1 sha256=" + "a" * 64)
print("FULL_CANDIDATE_READY elapsed_s=2 sha256=" + "b" * 64)
'''


def make_node(
    step: int,
    *,
    code: str,
    is_buggy: bool,
    parents: list[int],
    children: list[int],
    operators: list[str],
    label: str,
) -> dict:
    return {
        "id": label,
        "step": step,
        "code": code,
        "is_buggy": is_buggy,
        "exit_code": 1 if is_buggy else 0,
        "parents": parents,
        "children": children,
        "operators_used": operators,
    }


def test_v2_builder_and_extractor_end_to_end(tmp_path: Path, monkeypatch) -> None:
    run_root = tmp_path / "runs" / "aira-dojo"
    issue_root = run_root / "user_yzyang4_issue_schema_probe_repair_v2"
    status_dir = tmp_path / "status"
    tasks = ["spaceship-titanic", "tweet-sentiment-extraction"]

    for index, task in enumerate(tasks):
        task_id = f"user_yzyang4_issue_schema_probe_repair_v2_seed_862_id_{index}"
        experiment_dir = issue_root / task_id
        operators = {
            name: {"llm": {"client": {"model_id": "deepseek-v4-flash"}}}
            for name in ("analyze", "debug", "draft", "improve")
        }
        operators["draft"]["system_message_prompt_template"] = {
            "template": "CRITICAL ANYTIME ARTIFACT CONTRACT candidate_probe.csv"
        }
        config = {
            "id": task_id,
            "task": {
                "name": task,
                "data_dir": f"/research/d7/spc/yzyang4/mle-bench-data/{task}/prepared/public",
            },
            "metadata": {"seed": 862, "git_issue_id": "schema_probe_repair_v2"},
            "solver": {
                "step_limit": 3,
                "num_children": 1,
                "max_debug_depth": 1,
                "stop_after_first_valid": True,
                "execution_timeout": 600,
                "time_limit_secs": 1200,
                "operators": operators,
            },
            "logger": {"output_dir": str(experiment_dir)},
        }
        write_json(experiment_dir / "dojo_config.json", config)
        root = make_node(
            0,
            code="",
            is_buggy=True,
            parents=[],
            children=[1],
            operators=[],
            label=f"root-{index}",
        )
        if index == 0:
            nodes = [
                root,
                make_node(
                    1,
                    code=contract_code("draft"),
                    is_buggy=False,
                    parents=[0],
                    children=[],
                    operators=["draft", "analysis"],
                    label="valid-draft",
                ),
            ]
        else:
            nodes = [
                root,
                make_node(
                    1,
                    code="raise RuntimeError('draft')",
                    is_buggy=True,
                    parents=[0],
                    children=[2],
                    operators=["draft", "analysis"],
                    label="failed-draft",
                ),
                make_node(
                    2,
                    code=contract_code("debug"),
                    is_buggy=False,
                    parents=[1],
                    children=[],
                    operators=["debug", "analysis"],
                    label="valid-debug",
                ),
            ]
        write_json(experiment_dir / f"{task_id}_MCTS_search_data.json", {"nodes": nodes})
        journal = experiment_dir / "checkpoint" / "journal.jsonl"
        journal.parent.mkdir(parents=True, exist_ok=True)
        journal.write_text("{}\n" * len(nodes), encoding="utf-8")
        write_json(experiment_dir / "checkpoint" / "state.json", {"current_step": len(nodes)})
        write_json(
            status_dir / f"index_{index}.json",
            {
                "task": task,
                "seed": 862,
                "issue": "schema_probe_repair_v2",
                "return_code": 0,
                "command_sha256": f"command-{index}",
            },
        )

    generation_manifest = tmp_path / "generation_manifest.json"
    generation_audit = tmp_path / "generation_manifest.audit.json"
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "builder",
            "--run-root",
            str(run_root),
            "--status-dir",
            str(status_dir),
            "--issue",
            "schema_probe_repair_v2",
            "--seed",
            "862",
            "--tasks",
            *tasks,
            "--out",
            str(generation_manifest),
            "--audit",
            str(generation_audit),
        ],
    )
    builder.main()
    audit = json.loads(generation_audit.read_text(encoding="utf-8"))
    assert [row["topology_mode"] for row in audit["rows"]] == ["draft_valid", "debug_valid"]

    replay_manifest = tmp_path / "replay_manifest.jsonl"
    replay_audit = tmp_path / "replay_manifest.audit.json"
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "extractor",
            "--run-root",
            str(run_root),
            "--run-manifest",
            str(generation_manifest),
            "--issue",
            "schema_probe_repair_v2",
            "--seed",
            "862",
            "--tasks",
            *tasks,
            "--out",
            str(replay_manifest),
            "--audit",
            str(replay_audit),
        ],
    )
    extractor.main()
    rows = [json.loads(line) for line in replay_manifest.read_text(encoding="utf-8").splitlines()]
    assert len(rows) == 2
    assert {row["generation_topology_mode"] for row in rows} == {"draft_valid", "debug_valid"}
    assert all(row["code_sha256"] for row in rows)
