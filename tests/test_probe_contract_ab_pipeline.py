from __future__ import annotations

import json
import re
import sys
import zipfile
from pathlib import Path

import pytest

from phase1 import build_probe_contract_ab_manifest as builder
from phase1 import extract_probe_contract_ab_manifest as extractor
from phase1.audit_probe_contract_ab_hydra import audit_sample
from phase1.probe_contract_ab_common import row_for_index, spec_for_version
from phase1.validate_probe_contract_ab import classify, materialize_sample
from phase1.validate_schema_probe_contract import compare_to_sample


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


@pytest.mark.parametrize("version", ["v1", "v2"])
def test_ab_builder_extractor_and_gate_fixture(tmp_path: Path, monkeypatch, version: str) -> None:
    spec = spec_for_version(version)
    run_root = tmp_path / "runs" / "aira-dojo"
    status_dir = tmp_path / "status"
    for frozen in spec.matrix:
        expected = row_for_index(frozen["index"], version)
        issue_root = run_root / f"user_yzyang4_issue_{expected['issue']}"
        task_id = (
            f"user_yzyang4_issue_{expected['issue']}_seed_{spec.seed}_id_{expected['index']}"
        )
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
            "metadata": {"seed": spec.seed, "git_issue_id": expected["issue"]},
            "solver": {
                "exp_name": task_id,
                "checkpoint_path": str(experiment_dir / "checkpoint"),
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
                "schema_version": spec.schema_version,
                "experiment": spec.experiment,
                "version": spec.version,
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
            "--version",
            version,
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
    assert len(generation["rows"]) == len(spec.matrix)
    assert len(generation["prompt_audits"]) == len(spec.tasks)
    assert all(row["normalized_solver_equal"] for row in generation["prompt_audits"])

    replay_manifest = tmp_path / "replay_manifest.jsonl"
    replay_audit = tmp_path / "replay_manifest.audit.json"
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "extractor",
            "--version",
            version,
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
    assert len(rows) == len(spec.matrix)
    assert audit["python_ast_parse_rows"] == len(spec.matrix)
    assert audit["contract_static_pass_rows"] == len(spec.tasks)
    assert {row["task"] for row in rows} == set(spec.tasks)
    assert {row["issue"] for row in rows} == set(spec.issue_by_arm.values())

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


def test_solver_normalization_ignores_only_per_run_identity() -> None:
    base = {
        "exp_name": "run-a",
        "checkpoint_path": "/tmp/run-a/checkpoint",
        "step_limit": 3,
        "operators": {
            "draft": {
                "system_message_prompt_template": {"template": "original prompt"}
            }
        },
    }
    paired = {
        "exp_name": "run-b",
        "checkpoint_path": "/tmp/run-b/checkpoint",
        "step_limit": 3,
        "operators": {
            "draft": {
                "system_message_prompt_template": {"template": "contract prompt"}
            }
        },
    }
    assert builder.normalize_solver(base) == builder.normalize_solver(paired)

    paired["step_limit"] = 4
    assert builder.normalize_solver(base) != builder.normalize_solver(paired)


def test_v2_zip_sample_and_identifier_gate(tmp_path: Path) -> None:
    task = "text-normalization-challenge-english-language"
    public = tmp_path / task / "prepared" / "public"
    public.mkdir(parents=True)
    archive_path = public / "en_sample_submission_2.csv.zip"
    member = "en_sample_submission_2.csv"
    with zipfile.ZipFile(archive_path, "w") as archive:
        archive.writestr(member, "id,pred\n1,0.5\n2,0.5\n")
    audited = audit_sample(public, archive_path.name, member)
    assert audited["header"] == "id,pred"
    assert audited["member_bytes"] > 0

    cache = tmp_path / "cache"
    cache.mkdir()
    sample = materialize_sample(task, tmp_path, cache, "v2")
    valid = tmp_path / "valid.csv"
    wrong_ids = tmp_path / "wrong_ids.csv"
    valid.write_text("id,pred\n1,0.2\n2,0.8\n", encoding="utf-8")
    wrong_ids.write_text("id,pred\n9,0.2\n8,0.8\n", encoding="utf-8")
    assert compare_to_sample(valid, sample)["candidate_specific"] is True
    comparison = compare_to_sample(wrong_ids, sample)
    assert comparison["ids_match"] is False
    assert comparison["candidate_specific"] is False


def test_v2_operational_scripts_match_frozen_matrix() -> None:
    root = Path(__file__).parents[1]
    prereg = root / "phase1" / "probe_contract_ab_safety_v2" / "prereg"
    generation = (prereg / "probe_contract_ab_v2_generate_20260813.sbatch").read_text(
        encoding="utf-8"
    )
    hydra = (prereg / "hydra_preflight_probe_contract_ab_v2_20260813.sh").read_text(
        encoding="utf-8"
    )
    replay = (prereg / "probe_contract_ab_v2_replay_20260813.sbatch").read_text(
        encoding="utf-8"
    )
    expected = [row_for_index(index, "v2") for index in range(16)]
    launched = [
        {
            "index": int(index),
            "task": task,
            "arm": arm,
            "seed": 887,
            "issue": issue,
        }
        for index, task, arm, issue in re.findall(
            r"^launch_entry (\d+) (\S+) (original|contract) (\S+)$", generation, re.MULTILINE
        )
    ]
    composed = [
        {
            "index": int(index),
            "task": task,
            "arm": arm,
            "seed": 887,
            "issue": issue,
        }
        for index, task, arm, issue in re.findall(
            r"^  '(\d+)\|([^|]+)\|(original|contract)\|([^']+)'$", hydra, re.MULTILINE
        )
    ]
    assert launched == expected
    assert composed == expected
    assert "#SBATCH --array=0-15%4" in replay
    assert "#SBATCH --time=00:20:00" in replay
