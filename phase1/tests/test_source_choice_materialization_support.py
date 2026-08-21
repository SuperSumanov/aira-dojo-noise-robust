import argparse
import csv
import json
import sys
from pathlib import Path

import pytest

from phase1 import source_choice_materialization_support as producer
from phase1 import verify_source_choice_materialization_support as verifier


def answer_row(role: str, task: str, parent_raw: str, run_raw: str, incomplete: bool) -> dict[str, str]:
    source = 3
    finite = 2 if incomplete else 3
    row = {field: "0" for field in producer.ANSWER_FIELDS}
    row.update(
        {
            "role": role,
            "task": task,
            "run_id_sha256": producer.hash_text(run_raw),
            "parent_sha256": producer.hash_text(parent_raw),
            "source_children": str(source),
            "finite_children": str(finite),
            "source_identity_available": "True",
            "missing_identity_children": "1" if incomplete else "0",
            "published_winner_identified": "True",
            "status_winner_identified": "True",
            "execution_only_winner_identified": "True",
            "newly_identified_by_status": "False",
            "newly_identified_execution_only": "False",
        }
    )
    return row


def write_csv(path: Path, fields: tuple[str, ...], rows: list[dict[str, str]]) -> None:
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields, lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)


def fixture(tmp_path: Path) -> tuple[Path, Path, Path, Path]:
    answers: list[dict[str, str]] = []
    construction: list[dict[str, str]] = []
    for role, task in (("train", "task-a"), ("frozen", "task-b")):
        for index in range(20):
            parent = f"{role}-parent-{index}"
            run = f"{role}-run-{index // 2}"
            incomplete = index == 0
            answers.append(answer_row(role, task, parent, run, incomplete))
            if incomplete:
                construction.append(
                    {
                        "role": role,
                        "parent": parent,
                        "task": task,
                        "run_id": run,
                        "source_size": "3",
                        "eligible": "True",
                        "exclusion_reasons": "",
                    }
                )
    answer_path = tmp_path / "answer.csv"
    construction_path = tmp_path / "construction.csv"
    protocol_path = tmp_path / "protocol.json"
    output = tmp_path / "artifact"
    write_csv(answer_path, producer.ANSWER_FIELDS, answers)
    write_csv(construction_path, producer.CONSTRUCTION_FIELDS, construction)
    protocol = {
        "protocol": producer.PROTOCOL,
        "input_answerability_per_parent_sha256": producer.sha256_file(answer_path),
        "input_hurdle_construction_sha256": producer.sha256_file(construction_path),
        "expected_answerability_rows": 40,
        "expected_status_winners": 40,
        "expected_identity_available_incomplete_rows": 2,
        "expected_construction_rows_by_role": {"train": 1, "frozen": 1, "extension": 0},
        "expected_eligible_construction_rows_by_role": {
            "train": 1,
            "frozen": 1,
            "extension": 0,
        },
        "minimum_materializable_status_winners": 40,
        "minimum_materializable_status_winner_rate_all_parents": 1.0,
        "minimum_code_complete_share_of_status_winners": 1.0,
        "minimum_train_materializable_status_winners": 20,
        "minimum_frozen_materializable_status_winners": 20,
        "minimum_train_code_complete_share_of_status_winners": 1.0,
        "minimum_frozen_code_complete_share_of_status_winners": 1.0,
        "minimum_tasks_with_materializable_status_winner": 2,
        "minimum_tasks_with_at_least_20_materializable_status_winners": 2,
        "minimum_variable_arity_share": 1.0,
        "maximum_dominant_task_share": 0.5,
        "require_train_frozen_parent_overlap": 0,
        "require_train_frozen_run_overlap": 0,
        "allow_result_rescue": False,
        "scope": {
            "code_bytes_read": False,
            "numeric_grade_read": False,
            "gap_read": False,
            "prospective_outcome_read": False,
            "hurdle_model_result_read": False,
            "raw_archive_or_journal_read": False,
            "candidate_identity_emitted": False,
            "gpu": 0,
            "api_calls": 0,
            "base_llm_updated": False,
        },
    }
    protocol_path.write_text(json.dumps(protocol, indent=2) + "\n", encoding="utf-8")
    return protocol_path, answer_path, construction_path, output


def producer_args(paths: tuple[Path, Path, Path, Path]) -> argparse.Namespace:
    protocol, answer, construction, output = paths
    return argparse.Namespace(
        protocol=str(protocol),
        answerability_per_parent=str(answer),
        hurdle_construction=str(construction),
        source_commit="a" * 40,
        output=str(output),
    )


def verifier_args(paths: tuple[Path, Path, Path, Path], receipt: Path) -> argparse.Namespace:
    protocol, answer, construction, output = paths
    return argparse.Namespace(
        protocol=str(protocol),
        answerability_per_parent=str(answer),
        hurdle_construction=str(construction),
        source_commit="a" * 40,
        artifact=str(output),
        output=str(receipt),
    )


def test_materialization_support_passes_and_independent_verifier_agrees(tmp_path: Path, monkeypatch):
    paths = fixture(tmp_path)
    assert producer.run(producer_args(paths)) == 0
    summary = json.loads((paths[3] / "summary.json").read_text(encoding="utf-8"))
    assert summary["status"] == producer.STATUS_PASS
    assert summary["overall"]["materializable_status_winners"] == 40
    assert summary["overall"]["variable_arity_share"] == 1.0
    monkeypatch.delitem(sys.modules, "phase1.source_choice_materialization_support", raising=False)
    receipt = verifier.verify(verifier_args(paths, tmp_path / "receipt.json"))
    assert receipt["producer_imported"] is False
    assert receipt["criteria_all_pass"] is True


def test_independent_verifier_rejects_summary_drift(tmp_path: Path, monkeypatch):
    paths = fixture(tmp_path)
    producer.run(producer_args(paths))
    summary_path = paths[3] / "summary.json"
    summary = json.loads(summary_path.read_text(encoding="utf-8"))
    summary["overall"]["materializable_status_winners"] -= 1
    summary_path.write_text(json.dumps(summary) + "\n", encoding="utf-8")
    monkeypatch.delitem(sys.modules, "phase1.source_choice_materialization_support", raising=False)
    with pytest.raises(verifier.VerificationError, match="differs"):
        verifier.verify(verifier_args(paths, tmp_path / "receipt.json"))


def test_producer_rejects_answerability_hash_drift(tmp_path: Path):
    paths = fixture(tmp_path)
    with paths[1].open("a", encoding="utf-8") as handle:
        handle.write("\n")
    with pytest.raises(producer.SupportError, match="SHA mismatch"):
        producer.run(producer_args(paths))


def test_join_context_mismatch_is_fail_closed(tmp_path: Path):
    paths = fixture(tmp_path)
    construction_rows = list(csv.DictReader(paths[2].open(encoding="utf-8", newline="")))
    construction_rows[0]["task"] = "wrong-task"
    write_csv(paths[2], producer.CONSTRUCTION_FIELDS, construction_rows)
    protocol = json.loads(paths[0].read_text(encoding="utf-8"))
    protocol["input_hurdle_construction_sha256"] = producer.sha256_file(paths[2])
    paths[0].write_text(json.dumps(protocol) + "\n", encoding="utf-8")
    with pytest.raises(producer.SupportError, match="context mismatch"):
        producer.run(producer_args(paths))


def test_output_never_contains_raw_parent_or_run_identity(tmp_path: Path):
    paths = fixture(tmp_path)
    producer.run(producer_args(paths))
    output = b"".join(path.read_bytes() for path in paths[3].iterdir())
    assert b"train-parent-0" not in output
    assert b"frozen-run-0" not in output


def test_scope_drift_is_fail_closed(tmp_path: Path):
    paths = fixture(tmp_path)
    protocol = json.loads(paths[0].read_text(encoding="utf-8"))
    protocol["scope"]["code_bytes_read"] = True
    paths[0].write_text(json.dumps(protocol) + "\n", encoding="utf-8")
    with pytest.raises(producer.SupportError, match="scope declaration drifted"):
        producer.run(producer_args(paths))


def test_failed_material_gate_does_not_authorize_s1(tmp_path: Path):
    paths = fixture(tmp_path)
    protocol = json.loads(paths[0].read_text(encoding="utf-8"))
    protocol["minimum_tasks_with_materializable_status_winner"] = 3
    paths[0].write_text(json.dumps(protocol) + "\n", encoding="utf-8")
    assert producer.run(producer_args(paths)) == 0
    summary = json.loads((paths[3] / "summary.json").read_text(encoding="utf-8"))
    assert summary["status"] == producer.STATUS_FAIL
    assert summary["criteria"]["tasks_with_materializable_status_winner_ge_minimum"] is False
    assert summary["materialization_s1_authorized"] is False
