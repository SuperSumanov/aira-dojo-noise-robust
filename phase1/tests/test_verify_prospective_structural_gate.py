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
        {
            "card_id": "e",
            "run_id": "run-c",
            "task": "task-c",
            "code_sha256": "6" * 64,
            "lineage": {"parent": "parent-c"},
        },
        {
            "card_id": "f",
            "run_id": "run-c",
            "task": "task-c",
            "code_sha256": "7" * 64,
            "lineage": {"parent": "parent-c"},
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
    ] + [
        {
            "task": "task-c",
            "run_id": "run-c",
            "parent": "parent-c",
            "left": "e",
            "right": "f",
        }
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
                "generation_started_at_utc": "2026-08-14T00:00:00Z",
                "source_sha256": "4" * 64,
            },
            {
                "run_id": "run-b",
                "task": "task-b",
                "drop_id": "drop-a",
                "flow_status": "scoreable",
                "endpoints": 1,
                "generation_started_at_utc": "2026-08-14T00:01:00Z",
                "source_sha256": "5" * 64,
            },
            {
                "run_id": "run-c",
                "task": "task-c",
                "drop_id": "drop-a",
                "flow_status": "scoreable",
                "endpoints": 2,
                "generation_started_at_utc": "2026-08-14T00:02:00Z",
                "source_sha256": "8" * 64,
            },
        ],
    )
    _write_json(
        snapshot / "accumulator" / "summary.json",
        {
            "inventory": {
                "drops": 1,
                "eligible_runs": 3,
                "eligible_tasks": 3,
                "eligible_endpoints": 6,
                "eligible_structural_pairs": 4,
                "provisional_first960_runs": 2,
                "provisional_first960_endpoints": 4,
                "provisional_first960_structural_pairs": 3,
                "unique_exact_code_sha256": 5,
                "exact_code_duplicate_endpoints": 1,
            },
            "task_support": {
                "all_eligible": {
                    "structural_pair_counts": {"task-a": 3, "task-c": 1}
                },
                "provisional_first960": {"structural_pair_counts": {"task-a": 3}},
            },
            "status": "PROSPECTIVE_COHORT_AWAITING_CLOSURE",
            "closure": {
                "provided": False,
                "all_scheduled_runs_uploaded": None,
                "outcomes_read": None,
            },
        },
    )

    receipt = verify(state, snapshot, 4, 1, 2, 1.0, 2, "b" * 40)

    assert receipt["status"] == "CONFIRMATORY_COHORT_AWAITING_CLOSURE"
    assert receipt["independent_inventory"] == {
        "transactions": 1,
        "all_eligible": {"runs": 3, "tasks": 3, "endpoints": 6, "structural_pairs": 4},
        "provisional_first960": {
            "target_runs": 2,
            "runs": 2,
            "tasks": 2,
            "endpoints": 4,
            "structural_pairs": 3,
            "finite_decision_runs": 1,
            "pair_tasks": 1,
            "dominant_pair_task_count": 3,
            "dominant_pair_task_share": 1.0,
            "unique_exact_code_sha256": 3,
            "exact_code_duplicate_endpoints": 1,
        },
    }
    assert receipt["gate"]["remaining_structural_pairs"] == 1
    assert receipt["gate"]["checks"] == {
        "confirmatory_cohort_runs": True,
        "accrual_closed_without_outcomes": False,
        "structural_pairs": False,
        "finite_decision_runs": True,
        "tasks": True,
        "dominant_pair_task_share": True,
    }
    assert all(receipt["cross_checks_against_accumulator"].values())
    assert receipt["protocol"] == "prospective_structural_gate_independent_verifier_v4"
    assert receipt["reproducibility"]["source_commit"] == "b" * 40
    assert receipt["reproducibility"]["randomness_used"] is False
    assert receipt["reproducibility"]["thresholds"] == {
        "minimum_structural_pairs": 4,
        "minimum_finite_decision_runs": 1,
        "minimum_tasks": 2,
        "maximum_dominant_pair_task_share": 1.0,
        "minimum_confirmatory_cohort_runs": 2,
        "accrual_closure_required": True,
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

    accumulator_summary_path = snapshot / "accumulator" / "summary.json"
    accumulator_summary = json.loads(accumulator_summary_path.read_text(encoding="utf-8"))
    accumulator_summary["status"] = "PROSPECTIVE_FIRST960_IDENTITY_FROZEN"
    accumulator_summary["closure"] = {
        "provided": True,
        "all_scheduled_runs_uploaded": True,
        "outcomes_read": False,
    }
    _write_json(accumulator_summary_path, accumulator_summary)
    closed_receipt = verify(state, snapshot, 3, 1, 2, 1.0, 2, "b" * 40)
    assert closed_receipt["status"] == "CONFIRMATORY_STRUCTURAL_GATE_MET"
    assert closed_receipt["gate"]["all_pass"] is True
    assert closed_receipt["independent_inventory"]["all_eligible"]["structural_pairs"] == 4
    assert closed_receipt["independent_inventory"]["provisional_first960"]["structural_pairs"] == 3
