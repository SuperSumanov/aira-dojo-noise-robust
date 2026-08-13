from __future__ import annotations

import json
import sys
from pathlib import Path

from phase1 import build_probe_contract_ab_manifest as builder
from phase1 import extract_probe_contract_ab_manifest as extractor
from phase1.probe_contract_ab_common import ISSUE_BY_ARM, MATRIX, SEED, TASKS, row_for_index
from phase1.validate_probe_contract_ab import classify


def write_json(path: Path, payload: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, sort_keys=True) + "\n", encoding="utf-8")


ORIGINAL_PROMPT = "BASE\nMANDATORY OUTPUT"
CONTRACT_PROMPT = "\n".join(
    [
        "BASE",
        "- CRITICAL ANYTIME ARTIFACT CONTRACT: test",
        "- Preserve the probe as immutable `candidate_probe.csv`. test",
        "- Continue IN THE SAME PYTHON PROCESS from that probe into the full candidate method. test",
        "- The host evaluates artifact creation time independently. test",
        "MANDATORY OUTPUT",
    ]
)


def contract_code(label: str) -> str:
    return f'''
import os
probe = "candidate_probe.csv"
os.replace("{label}.tmp", probe)
os.fsync(1)
print("CANDIDATE_PROBE_READY elapsed_s=1 sha256=" + "a" * 64)
print("FULL_CANDIDATE_READY elapsed_s=2 sha256=" + "b" * 64)
'''


def original_code() -> str:
    return "print('FINAL_VALIDATION_SCORE: 0.5')\n"


def test_ab_builder_extractor_and_gate_fixture(tmp_path: Path, monkeypatch) -> None:
    run_root = tmp_path / "runs" / "aira-dojo"
    status_dir = tmp_path / "status"
    for frozen in MATRIX:
        expected = row_for_index(frozen["index"])
        issue_root = run_root / f"user_yzyang4_issue_{expected['issue']}"
        task_id = f"user_yzyang4_issue_{expected['issue']}_seed_{SEED}_id_{expected['index']}"
        experiment_dir = issue_root / task_id
        operators = {
            name: {"llm": {"client": {"model_id": "deepseek-v4-flash"}}}
            for name in ("analyze", "debug", "draft", "improve")
        }
        operators["draft"]["system_message_prompt_template"] = {
            "template": CONTRACT_PROMPT if expected["arm"] == "contract" else ORIGINAL_PROMPT
        }
        config = {
            "id": task_id,
            "task": {
                "name": expected["task"],
                "data_dir": (
                    f"/research/d7/spc/yzyang4/mle-bench-data/{expected['task']}/prepared/public"
                ),
            },
            "metadata": {"seed": SEED, "git_issue_id": expected["issue"]},
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
        code = contract_code(str(expected["index"])) if expected["arm"] == "contract" else original_code()
        nodes = [
            {
                "id": f"root-{expected['index']}",
                "step": 0,
                "code": "",
                "is_buggy": True,
                "parents": [],
                "children": [1],
                "operators_used": [],
            },
            {
                "id": f"leaf-{expected['index']}",
                "step": 1,
                "code": code,
                "is_buggy": False,
                "exit_code": 0,
                "parents": [0],
                "children": [],
                "operators_used": ["draft", "analysis"],
                "operators_metrics": [],
            },
        ]
        write_json(experiment_dir / f"{task_id}_MCTS_search_data.json", {"nodes": nodes})
        journal = experiment_dir / "checkpoint" / "journal.jsonl"
        journal.parent.mkdir(parents=True, exist_ok=True)
        journal.write_text("{}\n{}\n", encoding="utf-8")
        write_json(experiment_dir / "checkpoint" / "state.json", {"current_step": 2})
        write_json(
            status_dir / f"index_{expected['index']:02d}.json",
            {
                "schema_version": 1,
                **expected,
                "return_code": 0,
                "command_sha256": f"command-{expected['index']}",
                "wall_s": 10.0,
            },
        )

    generation_manifest = tmp_path / "generation_manifest.json"
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "builder",
            "--run-root",
            str(run_root),
            "--status-dir",
            str(status_dir),
            "--out",
            str(generation_manifest),
        ],
    )
    builder.main()
    generation = json.loads(generation_manifest.read_text(encoding="utf-8"))
    assert len(generation["rows"]) == 12
    assert len(generation["prompt_audits"]) == 6
    assert all(row["normalized_solver_equal"] for row in generation["prompt_audits"])

    replay_manifest = tmp_path / "replay_manifest.jsonl"
    replay_audit = tmp_path / "replay_manifest.audit.json"
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "extractor",
            "--generation-manifest",
            str(generation_manifest),
            "--out",
            str(replay_manifest),
            "--audit",
            str(replay_audit),
        ],
    )
    extractor.main()
    rows = [json.loads(line) for line in replay_manifest.read_text(encoding="utf-8").splitlines()]
    audit = json.loads(replay_audit.read_text(encoding="utf-8"))
    assert len(rows) == 12
    assert audit["python_ast_parse_rows"] == 12
    assert audit["contract_static_pass_rows"] == 6
    assert {row["task"] for row in rows} == set(TASKS)
    assert {row["issue"] for row in rows} == set(ISSUE_BY_ARM.values())

    verdict, gates = classify(
        {
            "contract_probe_valid": 6,
            "contract_coverage_120": 6,
            "coverage_gain": 3,
            "contract_full_valid": 5,
            "original_full_valid": 6,
            "paired_full_scores": 5,
            "median_relative_oriented_full_delta": -0.01,
            "catastrophic_harm_count": 1,
        }
    )
    assert verdict == "PROMISING"
    assert all(gates.values())
