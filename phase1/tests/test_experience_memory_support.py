from __future__ import annotations

import json
from pathlib import Path

from phase1.audit_experience_memory_support import audit


def _write_jsonl(path: Path, rows: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("".join(json.dumps(row) + "\n" for row in rows), encoding="utf-8")


def _card(card_id: str, run_id: str, task: str, y_norm: float, code: str = "x") -> dict:
    return {
        "id": card_id,
        "run_id": run_id,
        "task": {"name": task, "desc": task, "higher_is_better": True},
        "code": code,
        "label": {"y_norm": y_norm, "graded": y_norm},
    }


def test_audit_excludes_whole_frozen_run_and_normalizes_task_name(tmp_path: Path) -> None:
    cards = [
        _card("frozen-a", "run-frozen", "task-a", 0.8, "frozen-code"),
        _card("frozen-b", "run-frozen", "task-a", 0.7, "other-frozen-code"),
        _card("frozen-extra", "run-frozen", "task-a", 0.9, "must-also-be-excluded"),
        _card("memory-low", "run-memory", "task-a", 0.1, "low"),
        _card("memory-best", "run-memory", "task-a", 0.9, "df.to_csv('submission.csv')"),
    ]
    phase1 = tmp_path / "phase1"
    _write_jsonl(phase1 / "cards_current_v11.jsonl", cards)
    pair = {
        "better": "frozen-a",
        "worse": "frozen-b",
        "parent": "missing-parent",
        "intask_split": "test",
    }
    for index in range(3):
        _write_jsonl(phase1 / f"decision_clean_b{index}.jsonl", [pair])

    status_dir = (
        phase1
        / "results"
        / "source_opportunity_journal_status_v11_20260815_42cb6b1"
    )
    status_dir.mkdir(parents=True)
    (status_dir / "verification_summary.json").write_text(
        json.dumps(
            {
                "roles": {
                    "train": {
                        "target_missing_identities": 3,
                        "unique_nodes_recovered": 2,
                        "categories": {"EXECUTION_ERROR": 2},
                    }
                }
            }
        ),
        encoding="utf-8",
    )

    result = audit(tmp_path)

    assert result["frozen_exclusion"]["memory_physical_run_overlap"] == 0
    assert result["verified_success_memory"]["cards_after_run_exclusion"] == 2
    assert result["verified_success_memory"]["best_episode_per_physical_run"] == 1
    assert result["per_task_best_episodes"] == {"task-a": 1}
    assert result["train_failure_status_memory"]["unrecovered_status_nodes"] == 1
