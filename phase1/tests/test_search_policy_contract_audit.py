from __future__ import annotations

import argparse
import io
import json
import tarfile
from pathlib import Path

import pytest

from phase1.search_policy_contract_audit import (
    AuditError,
    build as producer_build,
    config_contract,
    contract_comparison,
    parse_journal,
    read_archive,
    safe_member_path,
    structure_metrics,
)
from phase1.verify_search_policy_contract_audit import verify as artifact_verify


def make_config(*, task: str = "task-a", model: str = "model-a", children: int = 2) -> bytes:
    prompt = {"template": "fixed", "input_variables": [], "partial_variables": {}}
    operator = {
        "llm": {
            "client": {"model_id": model, "provider": "openai"},
            "generation_kwargs": {"temperature": 0.5},
        },
        "init_user_message_prompt_template": prompt,
        "system_message_prompt_template": prompt,
        "user_message_prompt_template": prompt,
    }
    value = {
        "metadata": {"git_commit_id": "a" * 40, "seed": 7},
        "interpreter": {"timeout": 100},
        "solver": {
            "execution_timeout": 100,
            "max_debug_depth": 20,
            "max_debug_time": 1000.0,
            "num_children": children,
            "step_limit": 20,
            "time_limit_secs": 200,
            "uct_c": 0.25,
            "use_complexity": False,
            "use_test_score": False,
            "memory": {
                "memory_processor": "simple_memory",
                "memory_op_kwargs": {"include_buggy_nodes": False, "only_plans": False},
            },
            "operators": {name: operator for name in ("analyze", "draft", "debug", "improve")},
        },
        "task": {"benchmark": "mlebench", "name": task},
    }
    return json.dumps(value).encode()


def make_nodes(branch_sizes: tuple[int, int] = (2, 2), task: str = "task-a") -> list[dict]:
    nodes = [
        {
            "step": 0,
            "parents": [],
            "children": [1, 2],
            "creation_time": 1.0,
            "metric_info": {},
        }
    ]
    next_step = 3
    children_by_step = {1: [], 2: []}
    for branch, size in zip((1, 2), branch_sizes):
        nodes.append(
            {
                "step": branch,
                "parents": [0],
                "children": children_by_step[branch],
                "creation_time": 2.0,
                "metric_info": {"competition_id": task},
            }
        )
        parent = branch
        for _ in range(size - 1):
            step = next_step
            next_step += 1
            children_by_step[parent].append(step)
            children_by_step[step] = []
            nodes.append(
                {
                    "step": step,
                    "parents": [parent],
                    "children": children_by_step[step],
                    "creation_time": 3.0,
                    "metric_info": {"competition_id": task},
                }
            )
            parent = step
    return sorted(nodes, key=lambda row: row["step"])


def journal_bytes(nodes: list[dict]) -> bytes:
    return ("\n".join(json.dumps(node) for node in nodes) + "\n").encode()


def add_bytes(handle: tarfile.TarFile, name: str, blob: bytes) -> None:
    info = tarfile.TarInfo(name)
    info.size = len(blob)
    handle.addfile(info, io.BytesIO(blob))


def write_run_archive(path: Path, config: bytes, nodes: list[dict]) -> None:
    with tarfile.open(path, "w:gz") as handle:
        add_bytes(handle, "run/dojo_config.json", config)
        add_bytes(handle, "run/checkpoint/journal.jsonl", journal_bytes(nodes))
        dummy_secret = b'{"not_read":"' + b"sk-" + b"a" * 16 + b'"}'
        add_bytes(handle, "run/env_variables.json", dummy_secret)


def test_balanced_and_concentrated_structure_metrics() -> None:
    balanced = structure_metrics(make_nodes((2, 2)))
    assert balanced["normalized_hhi"] == pytest.approx(0.0)
    assert balanced["normalized_entropy"] == pytest.approx(1.0)
    assert balanced["effective_branch_ratio"] == pytest.approx(1.0)
    assert balanced["gini"] == pytest.approx(0.0)

    concentrated = structure_metrics(make_nodes((3, 1)))
    assert concentrated["hhi"] == pytest.approx(0.625)
    assert concentrated["normalized_hhi"] == pytest.approx(0.25)
    assert concentrated["gini"] == pytest.approx(0.25)


def test_config_contract_changes_with_model_and_children() -> None:
    left, task, seed = config_contract(make_config())
    right, _, _ = config_contract(make_config(model="model-b", children=5))
    assert task == "task-a"
    assert seed == 7
    assert left != right
    assert left["operators"]["draft"]["model_id"] == "model-a"
    assert left["selected"]["solver.num_children"] == 2


def test_parse_journal_validates_declared_children() -> None:
    nodes = make_nodes()
    parsed, journal_sha = parse_journal(journal_bytes(nodes), "task-a")
    assert len(parsed) == 5
    assert len(journal_sha) == 64
    nodes[0]["children"] = [1]
    with pytest.raises(AuditError, match="declared children"):
        parse_journal(journal_bytes(nodes), "task-a")


def test_archive_refuses_credential_before_json(tmp_path: Path) -> None:
    archive = tmp_path / "bad.tar.gz"
    with tarfile.open(archive, "w:gz") as handle:
        dummy_secret = b'{"token":"' + b"sk-" + b"a" * 16 + b'"}'
        add_bytes(handle, "run/dojo_config.json", dummy_secret)
        add_bytes(handle, "run/checkpoint/journal.jsonl", journal_bytes(make_nodes()))
    with pytest.raises(AuditError, match="credential-shaped"):
        read_archive(archive, 1_000_000, 100, 10_000_000)


def test_archive_tracks_incomplete_roots_without_reading_other_files(tmp_path: Path) -> None:
    archive = tmp_path / "partial.tar.gz"
    with tarfile.open(archive, "w:gz") as handle:
        add_bytes(handle, "run-a/dojo_config.json", make_config())
        add_bytes(handle, "run-a/checkpoint/journal.jsonl", journal_bytes(make_nodes()))
        add_bytes(handle, "run-b/dojo_config.json", make_config())
        dummy_secret = b'{"secret":"' + b"sk-" + b"a" * 16 + b'"}'
        add_bytes(handle, "run-a/env_variables.json", dummy_secret)
    roots, audit = read_archive(archive, 1_000_000, 100, 10_000_000)
    assert set(roots) == {"run-a", "run-b"}
    assert audit["complete_run_roots"] == 1
    assert audit["incomplete_run_roots"] == 1


def test_contract_comparison_requires_single_exact_signature_per_task() -> None:
    rows = [
        {"task": "a", "arm": "mcts", "contract_sha256": "x"},
        {"task": "a", "arm": "sequential", "contract_sha256": "x"},
    ]
    assert contract_comparison(rows, ("mcts", "sequential"))[
        "all_common_tasks_exact_contract_match"
    ]
    rows.append({"task": "a", "arm": "sequential", "contract_sha256": "y"})
    assert not contract_comparison(rows, ("mcts", "sequential"))[
        "all_common_tasks_exact_contract_match"
    ]


def test_unsafe_tar_member_rejected() -> None:
    info = tarfile.TarInfo("../escape/dojo_config.json")
    with pytest.raises(AuditError, match="unsafe tar member path"):
        safe_member_path(info)


def test_end_to_end_artifact_verifier(tmp_path: Path) -> None:
    mcts = tmp_path / "mcts"
    mcts_second = tmp_path / "mcts-second"
    sequential = tmp_path / "sequential"
    mcts.mkdir()
    mcts_second.mkdir()
    sequential.mkdir()
    left_nodes = make_nodes()
    right_nodes = make_nodes()
    for node in right_nodes:
        node["creation_time"] += 10.0
    write_run_archive(mcts / "left.tar.gz", make_config(model="left"), left_nodes)
    second_left_nodes = make_nodes()
    for node in second_left_nodes:
        node["creation_time"] += 20.0
    write_run_archive(
        mcts_second / "left.tar.gz", make_config(model="left-second"), second_left_nodes
    )
    write_run_archive(
        sequential / "right.tar.gz", make_config(model="right", children=5), right_nodes
    )
    result = tmp_path / "result"
    producer_args = argparse.Namespace(
        batch=[
            ("mcts", "mcts-a", mcts.resolve()),
            ("mcts", "mcts-b", mcts_second.resolve()),
            ("sequential", "seq-a", sequential.resolve()),
        ],
        out_dir=result,
        repo_root=Path.cwd(),
        max_archives_per_batch=10,
        max_archive_bytes=10_000_000,
        max_member_bytes=1_000_000,
        max_members_per_archive=100,
        max_declared_bytes_per_archive=10_000_000,
    )
    assert producer_build(producer_args) == 0
    verify_args = argparse.Namespace(
        result_dir=result,
        batch=[
            ("mcts", "mcts-a", mcts.resolve()),
            ("mcts", "mcts-b", mcts_second.resolve()),
            ("sequential", "seq-a", sequential.resolve()),
        ],
    )
    assert artifact_verify(verify_args) == 0
    summary = json.loads((result / "summary.json").read_text(encoding="utf-8"))
    assert summary["status"] == "CONTRACT_KILLED_DESCRIPTIVE_SUPPORT_INSUFFICIENT"
