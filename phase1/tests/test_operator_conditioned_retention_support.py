import csv
import json
from argparse import Namespace
from pathlib import Path

import pytest

from phase1.operator_conditioned_retention_support import (
    STATUS_FAIL,
    STATUS_PASS,
    SupportError,
    UPSTREAM_FIELDS,
    load_card_identity,
    run,
    sha256_file,
)
from phase1.verify_operator_conditioned_retention_support import verify


def write_json(path: Path, value: object) -> None:
    path.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def make_inputs(tmp_path: Path) -> tuple[Path, Path, list[dict[str, object]]]:
    parent_path = tmp_path / "parents.csv"
    cards_path = tmp_path / "cards.jsonl"
    parent_rows: list[dict[str, str]] = []
    cards: list[dict[str, object]] = []
    for task in ("task-a", "task-b"):
        for op in ("Debug", "Improve"):
            for role, count in (("train", 2), ("frozen", 1)):
                for index in range(count):
                    parent = f"{task}-{op}-{role}-{index}"
                    run_id = f"run-{task}-{op}-{role}-{index}"
                    row = {field: "" for field in UPSTREAM_FIELDS}
                    row.update(
                        {
                            "role": role,
                            "task": task,
                            "run_id": run_id,
                            "parent": parent,
                            "parent_card_present": "True",
                        }
                    )
                    parent_rows.append(row)
                    cards.append(
                        {
                            "id": parent,
                            "task": {"name": task},
                            "run_id": run_id,
                            "lineage": {"op": op},
                            "code": "unused",
                            "obs": "unused",
                        }
                    )
    with parent_path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=UPSTREAM_FIELDS, lineterminator="\n")
        writer.writeheader()
        writer.writerows(parent_rows)
    cards_path.write_text(
        "".join(json.dumps(card, sort_keys=True) + "\n" for card in cards),
        encoding="utf-8",
    )
    return parent_path, cards_path, cards


def make_protocol(
    tmp_path: Path,
    parent_path: Path,
    cards_path: Path,
    *,
    minimum_supported_tasks: int = 2,
) -> Path:
    protocol = {
        "protocol": "operator-conditioned-retention-support-v1",
        "input_per_parent_sha256": sha256_file(parent_path),
        "input_cards_sha256": sha256_file(cards_path),
        "expected_parent_rows": 12,
        "expected_card_rows": 12,
        "expected_role_parent_counts": {"train": 8, "frozen": 4, "extension": 0},
        "target_ops": ["Debug", "Improve"],
        "minimum_parent_join_coverage": 0.9,
        "minimum_train_parents_per_cell": 2,
        "minimum_frozen_parents_per_cell": 1,
        "minimum_train_runs_per_cell": 2,
        "minimum_frozen_runs_per_cell": 1,
        "minimum_supported_tasks": minimum_supported_tasks,
        "minimum_supported_task_op_cells": minimum_supported_tasks * 2,
        "maximum_dominant_frozen_parent_share": 0.6,
    }
    path = tmp_path / f"protocol-{minimum_supported_tasks}.json"
    write_json(path, protocol)
    return path


def producer_args(
    protocol: Path, parent_path: Path, cards_path: Path, output: Path
) -> Namespace:
    return Namespace(
        protocol=str(protocol),
        per_parent=str(parent_path),
        cards=str(cards_path),
        source_commit="0" * 40,
        output=str(output),
    )


def test_support_pass_and_independent_reconstruction(tmp_path: Path) -> None:
    parent_path, cards_path, _ = make_inputs(tmp_path)
    protocol = make_protocol(tmp_path, parent_path, cards_path)
    artifact = tmp_path / "artifact"
    assert run(producer_args(protocol, parent_path, cards_path, artifact)) == 0
    summary = json.loads((artifact / "summary.json").read_text(encoding="utf-8"))
    assert summary["status"] == STATUS_PASS
    assert summary["inventory"]["supported_tasks"] == ["task-a", "task-b"]
    assert summary["inventory"]["supported_task_op_cells"] == 4
    assert summary["inventory"]["train_frozen_run_overlap"] == 0
    result = verify(
        Namespace(
            protocol=str(protocol),
            per_parent=str(parent_path),
            cards=str(cards_path),
            artifact=str(artifact),
            source_commit="0" * 40,
        )
    )
    assert result["status"] == "INDEPENDENT_OPERATOR_CONDITIONED_SUPPORT_VERIFIED"
    assert result["producer_status"] == STATUS_PASS
    assert result["producer_imported"] is False


def test_support_gate_fails_without_lowering_threshold(tmp_path: Path) -> None:
    parent_path, cards_path, _ = make_inputs(tmp_path)
    protocol = make_protocol(
        tmp_path, parent_path, cards_path, minimum_supported_tasks=3
    )
    artifact = tmp_path / "artifact"
    assert run(producer_args(protocol, parent_path, cards_path, artifact)) == 0
    summary = json.loads((artifact / "summary.json").read_text(encoding="utf-8"))
    assert summary["status"] == STATUS_FAIL
    assert summary["criteria"]["supported_tasks_ge_minimum"] is False
    assert summary["scope"]["s1_effect_analysis_authorized"] is False


def test_context_mismatch_fails_closed(tmp_path: Path) -> None:
    parent_path, cards_path, cards = make_inputs(tmp_path)
    cards[0]["run_id"] = "wrong-run"
    cards_path.write_text(
        "".join(json.dumps(card, sort_keys=True) + "\n" for card in cards),
        encoding="utf-8",
    )
    protocol = make_protocol(tmp_path, parent_path, cards_path)
    artifact = tmp_path / "artifact"
    assert run(producer_args(protocol, parent_path, cards_path, artifact)) == 0
    summary = json.loads((artifact / "summary.json").read_text(encoding="utf-8"))
    assert summary["status"] == STATUS_FAIL
    assert summary["inventory"]["parent_context_mismatches"] == 1
    assert summary["criteria"]["parent_context_mismatches_eq_0"] is False


def test_credential_shaped_card_is_refused_before_parse(tmp_path: Path) -> None:
    parent_path, cards_path, _ = make_inputs(tmp_path)
    credential_shape = "s" + "k-" + "a" * 16
    cards_path.write_text(
        cards_path.read_text(encoding="utf-8")
        + json.dumps({"code": credential_shape, "id": "extra"})
        + "\n",
        encoding="utf-8",
    )
    protocol = make_protocol(tmp_path, parent_path, cards_path)
    with pytest.raises(SupportError, match="credential-shaped"):
        load_card_identity(cards_path, json.loads(protocol.read_text(encoding="utf-8")))


def test_flat_task_string_is_rejected_as_schema_drift(tmp_path: Path) -> None:
    parent_path, cards_path, cards = make_inputs(tmp_path)
    cards[0]["task"] = "task-a"
    cards_path.write_text(
        "".join(json.dumps(card, sort_keys=True) + "\n" for card in cards),
        encoding="utf-8",
    )
    protocol = make_protocol(tmp_path, parent_path, cards_path)
    with pytest.raises(SupportError, match="task object"):
        load_card_identity(cards_path, json.loads(protocol.read_text(encoding="utf-8")))
