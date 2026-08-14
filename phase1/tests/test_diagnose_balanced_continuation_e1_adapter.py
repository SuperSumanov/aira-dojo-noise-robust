from __future__ import annotations

import argparse
import csv
import json
import os
from pathlib import Path

from phase1.diagnose_balanced_continuation_e1_adapter import diagnose


def write_json(path: Path, value: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, sort_keys=True) + "\n", encoding="utf-8")


def write_csv(path: Path, rows: list[list[object]], mode: int) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.writer(handle, lineterminator="\n")
        writer.writerow(["PassengerId", "Transported"])
        writer.writerows(rows)
    os.chmod(path, mode)


def test_post_gate_replay_proves_union_adapter_bug_without_method_claim(tmp_path: Path) -> None:
    task = "spaceship-titanic"
    rollout = "a" * 64
    run = tmp_path / "run"
    data = tmp_path / "data"
    split = data / "e1_split"
    public_sample = split / "public" / task / "sample_submission.csv"
    dsearch = split / "private" / "dsearch" / f"{task}.csv"
    dval = split / "private" / "dval" / f"{task}.csv"
    write_csv(public_sample, [["search", False], ["val", False]], 0o444)
    write_csv(dsearch, [["search", True]], 0o600)
    write_csv(dval, [["val", False]], 0o600)

    write_json(run / "preparation" / "source_inputs.json", {
        "data_gate_root": str(data.resolve()),
        "contains_outcomes": False,
        "source_commit": "1" * 40,
    })
    write_json(run / "final_status.json", {
        "status": "VERIFIED_COMPLETE_REAL_E1_COLLECTION",
        "collection_rc": 0,
    })
    write_json(run / "collection" / "summary.json", {
        "sealed_values_opened": True,
        "coverage_gate": {"sealed_values_opened_before_coverage_gate": False},
    })
    result_root = run / "worker_outputs" / rollout
    write_json(result_root / "result.json", {
        "rollout_id": rollout,
        "task": task,
        "continuation_horizon": 1,
    })
    for ordinal in (0, 1):
        step = result_root / "steps" / f"step_{ordinal:03d}"
        write_json(step / "execution.json", {
            "execution_status": "ok" if ordinal == 0 else "invalid_format",
            "process_started": ordinal == 0,
            "timed_out": False,
            "exit_code": 0 if ordinal == 0 else None,
        })
        write_json(step / "dsearch.json", {
            "submission_valid": False,
            "grade_return_code": 2,
        })
        write_json(run / "sealed" / rollout / f"dval_{ordinal:03d}.json", {
            "submission_valid": False,
            "grade_return_code": 2,
        })
        if ordinal == 1:
            write_json(step / "operator_usage.json", {"extraction_status": "invalid_format"})
    write_csv(
        result_root / "steps" / "step_000" / "submission.csv",
        [["val", False], ["search", True]],
        0o600,
    )

    value = diagnose(argparse.Namespace(run_root=str(run), data_gate_root=str(data)))
    assert value["status"] == "DIAGNOSTIC_ONLY_POST_HOC_ADAPTER_REPLAY_NO_METHOD_CLAIM"
    assert value["split_proofs"][0]["private_union_equals_public"] is True
    assert value["aggregate"] == {
        "rollouts": 1,
        "steps": 2,
        "candidate_processes_started": 1,
        "operator_invalid_format": 1,
        "operator_calls_at_output_token_cap": 0,
        "continuation_failure_classes": {"invalid_format": 1},
        "artifacts_present": 1,
        "legacy_dsearch_valid": 0,
        "legacy_dval_valid": 0,
        "replayed_dsearch_valid": 1,
        "replayed_dval_valid": 1,
        "replayed_paired_rollouts": 0,
        "replayed_positive_dval_gains": 0,
        "replayed_zero_dval_gains": 0,
        "replayed_negative_dval_gains": 0,
    }
    assert value["method_claim_allowed"] is False
    assert value["e2_e3_unlocked"] is False
