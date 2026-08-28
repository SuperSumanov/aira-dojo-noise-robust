from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

import pytest

from phase1 import build_openrouter_full_context_panel as builder
from phase1 import openrouter_full_context_judge as judge


REAL_PROTOCOL = Path(__file__).resolve().parents[1] / "openrouter_full_context_judge_v1.json"


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def write_json(path: Path, value: object) -> None:
    path.write_text(json.dumps(value, sort_keys=True), encoding="utf-8")


def write_jsonl(path: Path, rows: list[dict[str, object]]) -> None:
    path.write_text(
        "".join(json.dumps(row, sort_keys=True) + "\n" for row in rows),
        encoding="utf-8",
    )


def make_card(identity: str, task: str, parent: str | None) -> dict[str, object]:
    return {
        "id": identity,
        "task": {
            "name": task,
            "desc": f"Synthetic complete description for {task}",
            "metric": "accuracy",
            "higher_is_better": True,
        },
        "lineage": {"parent_id": parent},
        "client": "fixed-client",
        "hardware": "fixed-hardware",
        "time_limit": 3600,
        "execution_timeout": 300,
        "code": f"print('complete program for {identity[-4:]}')",
    }


def make_inputs(tmp_path: Path) -> tuple[Path, str, Path, Path]:
    protocol = json.loads(REAL_PROTOCOL.read_text(encoding="utf-8"))
    cards: dict[str, list[dict[str, object]]] = {}
    decision: list[dict[str, object]] = []
    value: list[dict[str, object]] = []
    runs: list[str] = []
    tasks = [f"task-{index:02d}" for index in range(16)]
    gaps = [1.25, 2.5, 5.0, 10.0]
    for index in range(64):
        run = f"synthetic-run-{index:03d}"
        task = tasks[index // 4]
        gap = gaps[index % 4]
        first = f"synthetic-card-{index:03d}-first"
        second = f"synthetic-card-{index:03d}-second"
        runs.append(run)
        if index < 32:
            cards[run] = [make_card(first, task, None), make_card(second, task, None)]
            value.append(
                {
                    "better": first,
                    "worse": second,
                    "task": task,
                    "loto_fold": task,
                    "intask_split": "test",
                    "gap_raw": gap,
                }
            )
        else:
            parent = f"synthetic-card-{index:03d}-parent"
            cards[run] = [
                make_card(parent, task, None),
                make_card(first, task, parent),
                make_card(second, task, parent),
            ]
            decision.append(
                {
                    "better": first,
                    "worse": second,
                    "parent": parent,
                    "task": task,
                    "loto_fold": task,
                    "intask_split": "test",
                    "gap_raw": gap,
                }
            )

    paths = {
        "cards": tmp_path / "cards.json",
        "run_split": tmp_path / "runs.json",
        "decision": tmp_path / "decision.jsonl",
        "value_hardware_time": tmp_path / "value.jsonl",
        "task_unit_gap": tmp_path / "gaps.json",
    }
    write_json(paths["cards"], cards)
    write_json(paths["run_split"], {"all": runs, "hold": runs})
    write_jsonl(paths["decision"], decision)
    write_jsonl(paths["value_hardware_time"], value)
    write_json(paths["task_unit_gap"], {task: 1.0 for task in tasks})

    protocol["immutable_inputs"]["run_split"]["all_runs"] = 64
    protocol["immutable_inputs"]["run_split"]["held_runs"] = 64
    for role in paths:
        protocol["immutable_inputs"][role]["bytes"] = paths[role].stat().st_size
        key = "lfs_oid_sha256" if role == "task_unit_gap" else "sha256"
        protocol["immutable_inputs"][role][key] = sha256(paths[role])
    protocol["immutable_inputs"]["decision"]["rows"] = len(decision)
    protocol["immutable_inputs"]["decision"]["test_rows"] = len(decision)
    protocol["immutable_inputs"]["value_hardware_time"]["rows"] = len(value)
    protocol["immutable_inputs"]["value_hardware_time"]["test_rows"] = len(value)
    protocol_path = tmp_path / "protocol.json"
    write_json(protocol_path, protocol)
    protocol_sha = sha256(protocol_path)
    panel_path = tmp_path / "private" / "panel.jsonl"
    receipt_path = tmp_path / "private" / "receipt.jsonl"
    args = argparse.Namespace(
        protocol=protocol_path,
        protocol_sha256=protocol_sha,
        cards=paths["cards"],
        run_split=paths["run_split"],
        decision=paths["decision"],
        value_hardware_time=paths["value_hardware_time"],
        task_unit_gap=paths["task_unit_gap"],
        panel_out=panel_path,
        receipt_out=receipt_path,
    )
    receipt = builder.build(args)
    assert receipt["selection"]["pairs"] == 64
    return protocol_path, protocol_sha, panel_path, receipt_path


def test_builder_materializes_exact_balanced_private_panel(tmp_path: Path) -> None:
    _, _, panel_path, receipt_path = make_inputs(tmp_path)
    rows = [json.loads(line) for line in panel_path.read_text(encoding="utf-8").splitlines()]
    receipt = json.loads(receipt_path.read_text(encoding="utf-8"))
    assert len(rows) == 64
    assert sum(row["smoke"] for row in rows) == 8
    assert receipt["selection"]["physical_runs"] == 64
    assert receipt["selection"]["endpoint_duplicate_excess"] == 0
    assert receipt["selection"]["maximum_pairs_per_task"] == 4
    assert receipt["security"]["api_calls"] == 0


def test_missing_metric_is_rejected_as_ineligible_not_global_parse_failure() -> None:
    value = make_card("synthetic-card-with-missing-metric", "task-a", None)
    assert isinstance(value["task"], dict)
    value["task"]["metric"] = None
    missing = builder.parse_card(
        "synthetic-card-with-missing-metric", "synthetic-run-a", value
    )
    valid_value = make_card("synthetic-card-with-valid-metric", "task-a", None)
    valid = builder.parse_card(
        "synthetic-card-with-valid-metric", "synthetic-run-a", valid_value
    )
    rows = [
        {
            "better": missing.identity,
            "worse": valid.identity,
            "task": "task-a",
            "loto_fold": "task-a",
            "gap_raw": 1.5,
        }
    ]
    candidates, rejected = builder.eligible_candidates(
        "value_hardware_time",
        rows,
        {missing.identity: missing, valid.identity: valid},
        {"synthetic-run-a"},
        {"task-a": 1.0},
        json.loads(REAL_PROTOCOL.read_text(encoding="utf-8"))["selection"]["gap_bins"],
    )
    assert candidates == []
    assert rejected == {"missing_prompt_metadata": 1}


def test_request_contract_keeps_full_code_and_excludes_labels(tmp_path: Path) -> None:
    protocol_path, protocol_sha, panel_path, _ = make_inputs(tmp_path)
    protocol, _ = judge.load_protocol(protocol_path, protocol_sha)
    row = judge.read_jsonl(panel_path)[0]
    model = protocol["model_catalog_snapshot"]["models"][0]["id"]
    request = judge.request_payload(row, "AB", model, protocol)
    serialized = judge.canonical_json(request)
    assert row["better"]["code"] in serialized
    assert row["worse"]["code"] in serialized
    assert row["better"]["id"] not in serialized
    assert row["worse"]["id"] not in serialized
    assert "max_tokens" not in request
    assert request["reasoning"] == {"enabled": True}
    assert request["provider"] == {"zdr": True, "data_collection": "deny"}


@pytest.mark.parametrize(
    ("content", "pick"),
    [("A", "A"), ("**B**", "B"), ("I considered A but choose B", None), ("", None)],
)
def test_final_choice_parser_does_not_salvage_reasoning(content: str, pick: str | None) -> None:
    response = {
        "choices": [{"message": {"content": content, "reasoning": "Answer A"}}]
    }
    observed, _ = judge.parse_final_pick(response)
    assert observed == pick


def test_mock_smoke_is_network_free_append_only_and_resumable(tmp_path: Path) -> None:
    protocol_path, protocol_sha, panel_path, _ = make_inputs(tmp_path)
    raw_path = tmp_path / "private" / "mock.jsonl"
    args = argparse.Namespace(
        protocol=protocol_path,
        protocol_sha256=protocol_sha,
        panel=panel_path,
        raw_out=raw_path,
        phase="smoke",
        transport="mock",
        models=None,
        launch_receipt=None,
        timeout_seconds=1.0,
    )
    first = judge.run(args)
    second = judge.run(args)
    assert first["status"] == "MOCK_COMPLETE_NO_NETWORK"
    assert first["attempted_calls"] == 64
    assert first["successful_calls"] == 64
    assert second["attempted_calls"] == 0
    assert second["skipped_existing_calls"] == 64
    assert len(raw_path.read_text(encoding="utf-8").splitlines()) == 64


def test_live_transport_requires_separate_launch_receipt_before_credential(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    protocol_path, protocol_sha, panel_path, _ = make_inputs(tmp_path)
    monkeypatch.setenv(judge.KEY_ENVIRONMENT_VARIABLE, "synthetic-not-a-real-credential")
    args = argparse.Namespace(
        protocol=protocol_path,
        protocol_sha256=protocol_sha,
        panel=panel_path,
        raw_out=tmp_path / "private" / "live.jsonl",
        phase="smoke",
        transport="live",
        models=None,
        launch_receipt=None,
        timeout_seconds=1.0,
    )
    with pytest.raises(judge.JudgeError, match="separate launch receipt"):
        judge.run(args)
