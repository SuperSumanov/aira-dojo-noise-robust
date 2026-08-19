from __future__ import annotations

import hashlib
import json
from pathlib import Path

from phase1.verify_prospective_structural_gate import verify


def _write_json(path: Path, value: object) -> str:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, sort_keys=True) + "\n", encoding="utf-8")
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _write_jsonl(path: Path, rows: list[dict[str, object]]) -> str:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        "".join(json.dumps(row, sort_keys=True) + "\n" for row in rows),
        encoding="utf-8",
    )
    return hashlib.sha256(path.read_bytes()).hexdigest()


def test_independent_structural_gate_rebuilds_pairs(tmp_path: Path) -> None:
    state = tmp_path / "state"
    snapshot = state / "snapshots" / ("a" * 64)
    intake = state / "intakes" / "drop-a"
    blind = [
        {
            "card_id": "a",
            "run_id": "run-a",
            "task": "task-a",
            "code_sha256": "1" * 64,
            "lineage": {"parent": "parent-a"},
        },
        {
            "card_id": "b",
            "run_id": "run-a",
            "task": "task-a",
            "code_sha256": "2" * 64,
            "lineage": {"parent": "parent-a"},
        },
        {
            "card_id": "c",
            "run_id": "run-a",
            "task": "task-a",
            "code_sha256": "2" * 64,
            "lineage": {"parent": "parent-a"},
        },
        {
            "card_id": "d",
            "run_id": "run-b",
            "task": "task-b",
            "code_sha256": "3" * 64,
            "lineage": {"parent": "parent-b"},
        },
    ]
    pairs = [
        {
            "task": "task-a",
            "run_id": "run-a",
            "parent": "parent-a",
            "left": left,
            "right": right,
        }
        for left, right in (("a", "b"), ("a", "c"), ("b", "c"))
    ]
    blind_sha = _write_jsonl(intake / "eligible_blind_manifest.jsonl", blind)
    pair_sha = _write_jsonl(intake / "eligible_structural_pairs.jsonl", pairs)
    intake_summary = {
        "outputs": {
            "eligible_blind_manifest_sha256": blind_sha,
            "eligible_structural_pairs_sha256": pair_sha,
        },
        "security": {
            "env_members_read": False,
            "live_event_journal_members_read": False,
            "journal_scanned_before_json": True,
        },
        "blindness": {
            "labels_used_for_run_selection": False,
            "labels_used_for_endpoint_selection": False,
        },
    }
    summary_sha = _write_json(intake / "summary.json", intake_summary)
    _write_jsonl(
        snapshot / "intake_registry.jsonl",
        [
            {
                "drop_id": "drop-a",
                "intake_dir": str(intake),
                "summary_sha256": summary_sha,
            }
        ],
    )
    _write_jsonl(
        snapshot / "accumulator" / "provisional_runs.jsonl",
        [
            {
                "run_id": "run-a",
                "task": "task-a",
                "drop_id": "drop-a",
                "flow_status": "scoreable",
                "endpoints": 3,
            },
            {
                "run_id": "run-b",
                "task": "task-b",
                "drop_id": "drop-a",
                "flow_status": "scoreable",
                "endpoints": 1,
            },
        ],
    )
    _write_json(
        snapshot / "accumulator" / "summary.json",
        {
            "inventory": {
                "drops": 1,
                "eligible_runs": 2,
                "eligible_tasks": 2,
                "eligible_endpoints": 4,
                "eligible_structural_pairs": 3,
                "unique_exact_code_sha256": 3,
                "exact_code_duplicate_endpoints": 1,
            },
            "task_support": {"all_eligible": {"structural_pair_counts": {"task-a": 3}}},
        },
    )

    receipt = verify(state, snapshot, 4, 1, 2, 1.0, "b" * 40)

    assert receipt["status"] == "STRUCTURAL_GATE_NOT_YET_MET"
    assert receipt["independent_inventory"] == {
        "transactions": 1,
        "eligible_runs": 2,
        "eligible_tasks": 2,
        "eligible_endpoints": 4,
        "eligible_structural_pairs": 3,
        "finite_decision_runs": 1,
        "pair_tasks": 1,
        "dominant_pair_task_count": 3,
        "dominant_pair_task_share": 1.0,
        "unique_exact_code_sha256": 3,
        "exact_code_duplicate_endpoints": 1,
    }
    assert receipt["gate"]["remaining_structural_pairs"] == 1
    assert receipt["gate"]["checks"] == {
        "structural_pairs": False,
        "finite_decision_runs": True,
        "tasks": True,
        "dominant_pair_task_share": True,
    }
    assert all(receipt["cross_checks_against_accumulator"].values())
    assert receipt["protocol"] == "prospective_structural_gate_independent_verifier_v3"
    assert receipt["reproducibility"]["source_commit"] == "b" * 40
    assert receipt["reproducibility"]["randomness_used"] is False
    assert receipt["reproducibility"]["thresholds"] == {
        "minimum_structural_pairs": 4,
        "minimum_finite_decision_runs": 1,
        "minimum_tasks": 2,
        "maximum_dominant_pair_task_share": 1.0,
    }
    assert receipt["asset_quality"]["decision_support"] == {
        "runs_with_finite_decision": 1,
        "run_pair_coverage": 0.5,
        "tasks_with_finite_decision": 1,
        "task_pair_coverage": 0.5,
        "decision_parent_groups": 1,
        "median_pairs_per_decision_run": 3,
        "minimum_pairs_per_supported_task": 3,
        "maximum_pairs_per_supported_task": 3,
    }
    assert receipt["asset_quality"]["code_redundancy"] == {
        "exact_code_unique_fraction": 0.75,
        "duplicate_code_groups": 1,
        "duplicate_endpoints_beyond_first": 1,
        "cross_run_duplicate_code_groups": 0,
        "cross_task_duplicate_code_groups": 0,
    }
