from __future__ import annotations

import argparse
import csv
import json
import os
from pathlib import Path

import pytest

import phase1.balanced_continuation_dsearch_eval as dsearch
import phase1.balanced_continuation_dval_sealer as dval
from phase1.balanced_continuation_e1_scoring import (
    evaluator_bundle_sha256,
    score_submission,
)
from phase1.balanced_continuation_real_contract import WORKER_CONTRACT_SCHEMA


ROLLOUT = "a" * 64
TOKEN = "b" * 32


def write_csv(path: Path, header: list[str], rows: list[list[object]]) -> None:
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.writer(handle, lineterminator="\n")
        writer.writerow(header)
        writer.writerows(rows)
    os.chmod(path, 0o600)


def write_json(path: Path, value: object) -> None:
    path.write_text(json.dumps(value, sort_keys=True) + "\n", encoding="utf-8")


def contract() -> dict:
    return {
        "schema_version": WORKER_CONTRACT_SCHEMA,
        "backend": "aira-dojo-external-v1",
        "source_commit": "1" * 40,
        "container_sha256": "2" * 64,
        "operator_config_sha256": "3" * 64,
        "prompt_sha256": "4" * 64,
        "public_dataset_contract_sha256": "5" * 64,
        "split_manifest_sha256_opaque": "6" * 64,
        "search_evaluator_executable_sha256": evaluator_bundle_sha256(Path(dsearch.__file__)),
        "sealed_label_evaluator_executable_sha256": evaluator_bundle_sha256(Path(dval.__file__)),
        "public_data_root": "/frozen/public",
        "continuation_horizon": 1,
        "operator_timeout_seconds": 180,
        "execution_timeout_seconds": 900,
        "evaluator_timeout_seconds": 120,
        "operator_policy": "debug_if_buggy_else_improve",
        "operator_calls_per_transition": 1,
        "operator_retry_count": 0,
        "execution_retry_count": 0,
        "analyze_operator_calls": 0,
        "workspace_policy": "fresh_per_rollout",
        "candidate_mount_policy": "public_read_only_no_private",
        "score_visibility": "D_search_only",
        "sealed_label_policy": "D_val_external_mode_0600",
        "split_policy": "80/10/10_D_train_D_search_D_val",
        "dtest_policy": "never_read",
    }


def test_accuracy_and_auc_reference_values(tmp_path: Path) -> None:
    spaceship_labels = tmp_path / "spaceship.csv"
    spaceship_sub = tmp_path / "spaceship_sub.csv"
    write_csv(spaceship_labels, ["PassengerId", "Transported"], [
        ["a", "True"], ["b", "False"], ["c", "True"], ["d", "False"]
    ])
    write_csv(spaceship_sub, ["PassengerId", "Transported"], [
        ["d", "False"], ["b", "True"], ["a", "True"], ["c", "True"]
    ])
    assert score_submission(spaceship_sub, spaceship_labels, "spaceship-titanic")["score"] == 0.75

    auc_labels = tmp_path / "auc.csv"
    auc_sub = tmp_path / "auc_sub.csv"
    write_csv(auc_labels, ["id", "target"], [["a", 0], ["b", 0], ["c", 1], ["d", 1]])
    write_csv(auc_sub, ["id", "target"], [["a", 0.1], ["b", 0.4], ["c", 0.35], ["d", 0.8]])
    assert score_submission(
        auc_sub, auc_labels, "tabular-playground-series-may-2022"
    )["score"] == 0.75


def test_invalid_submission_is_observed_without_exception(tmp_path: Path) -> None:
    labels = tmp_path / "labels.csv"
    submission = tmp_path / "submission.csv"
    write_csv(labels, ["id", "target"], [["a", 0], ["b", 1]])
    write_csv(submission, ["id", "target"], [["a", 0.2], ["a", 0.8]])
    result = score_submission(submission, labels, "tabular-playground-series-may-2022")
    assert result["submission_valid"] is False
    assert result["score"] is None
    assert result["failure_reason"] == "submission_id_or_schema_invalid"


def test_sidecars_expose_search_but_only_commit_val(tmp_path: Path) -> None:
    task = "spaceship-titanic"
    labels = tmp_path / f"{task}.csv"
    artifact = tmp_path / "submission.csv"
    write_csv(labels, ["PassengerId", "Transported"], [["a", "True"], ["b", "False"]])
    write_csv(artifact, ["PassengerId", "Transported"], [["a", "True"], ["b", "True"]])
    contract_path = tmp_path / "contract.json"
    write_json(contract_path, contract())
    search_receipt = tmp_path / "search.json"
    search = dsearch.run(argparse.Namespace(
        contract=str(contract_path), task=task, rollout_id=ROLLOUT, workspace_token=TOKEN,
        ordinal=0, artifact=str(artifact), labels=str(labels), receipt=str(search_receipt),
    ))
    assert search["dsearch_score"] == 0.5
    sealed = tmp_path / "sealed.json"
    label_receipt, commitment = dval.run(argparse.Namespace(
        contract=str(contract_path), task=task, rollout_id=ROLLOUT, workspace_token=TOKEN,
        ordinal=0, artifact=str(artifact), labels=str(labels), sealed_receipt=str(sealed),
    ))
    assert label_receipt["dval_score"] == 0.5
    assert not any("dval" in key.lower() for key in commitment)
    assert set(commitment) == {
        "schema_version", "rollout_id", "workspace_token", "task", "execution_ordinal",
        "sealed_label_receipt_sha256",
    }
    if os.name == "posix":
        assert sealed.stat().st_mode & 0o777 == 0o600


def test_wrapper_bundle_mismatch_fails_closed(tmp_path: Path) -> None:
    task = "spaceship-titanic"
    labels = tmp_path / f"{task}.csv"
    artifact = tmp_path / "submission.csv"
    write_csv(labels, ["PassengerId", "Transported"], [["a", "True"], ["b", "False"]])
    write_csv(artifact, ["PassengerId", "Transported"], [["a", "True"], ["b", "False"]])
    value = contract()
    value["search_evaluator_executable_sha256"] = "f" * 64
    contract_path = tmp_path / "contract.json"
    write_json(contract_path, value)
    with pytest.raises(Exception, match="bundle differs"):
        dsearch.run(argparse.Namespace(
            contract=str(contract_path), task=task, rollout_id=ROLLOUT, workspace_token=TOKEN,
            ordinal=0, artifact=str(artifact), labels=str(labels), receipt=str(tmp_path / "out.json"),
        ))
