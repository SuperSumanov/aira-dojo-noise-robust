import hashlib
import json
import subprocess
from pathlib import Path

import pytest

from phase1.score_channel_cohort_support import SupportError, produce
from phase1.verify_score_channel_cohort_support import VerificationError, verify


REPO = Path(__file__).resolve().parents[2]


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def make_selection(tmp_path: Path, *, duplicate: bool = False) -> Path:
    selection = tmp_path / "selection"
    selection.mkdir()
    specs = [
        ("task-a", "run-a", "parent-a", ["a", "b"]),
        ("task-a", "run-a", "parent-b", ["c", "d", "e"]),
        ("task-b", "run-b", "parent-c", ["f", "g"]),
        ("task-b", "run-c", "parent-d", ["a" if duplicate else "h", "i"]),
    ]
    rows = []
    for index, (task, run, parent, cards) in enumerate(specs):
        rows.append({
            "schema_version": "score-channel-parent-selection-row-v1",
            "task": task,
            "run_id": run,
            "parent_id": parent,
            "source_intake": f"intake-{index}",
            "selection_rank_in_run": 1 if index != 1 else 2,
            "selection_key_sha256": f"{index + 1:064x}",
            "candidate_card_ids": cards,
            "candidate_count": len(cards),
            "candidate_identity_sha256": hashlib.sha256(
                json.dumps(cards, sort_keys=True, separators=(",", ":")).encode("utf-8")
            ).hexdigest(),
        })
    rows_path = selection / "selected_parents.jsonl"
    rows_path.write_text(
        "".join(json.dumps(row, sort_keys=True, separators=(",", ":")) + "\n" for row in rows),
        encoding="utf-8",
    )
    (selection / "summary.json").write_text(json.dumps({
        "protocol": "score-channel-parent-selection-v1",
        "status": "PARENT_GATE_PASS_REPLAY_APPROVAL_PENDING",
        "gates": {"parent_gate_pass": True},
        "counts": {"selected_parents": 4, "selected_candidates": 8 if duplicate else 9},
        "outputs": {"selected_parents_sha256": sha(rows_path)},
    }, sort_keys=True, indent=2) + "\n", encoding="utf-8")
    return selection


def test_support_roundtrip_is_outcome_blind_and_independent(tmp_path: Path):
    selection = make_selection(tmp_path)
    audit = tmp_path / "audit.json"
    value = produce(selection, REPO, audit)
    support = value["support"]
    assert support["counts"] == {
        "selected_tasks": 2,
        "physical_runs": 3,
        "selected_parents": 4,
        "selected_candidates": 9,
        "unique_candidate_ids": 9,
        "duplicate_candidate_memberships": 0,
    }
    assert support["dominant_task_by_candidates"] == {
        "task": "task-a", "count": 5, "denominator": 9, "share": 5 / 9,
    }
    assert support["parent_candidate_count_histogram"] == {"2": 3, "3": 1}
    receipt = verify(selection, audit, sha(audit))
    assert receipt["producer_imported"] is False
    assert receipt["support_exact"] is True

    verifier = (REPO / "phase1" / "verify_score_channel_cohort_support.py").read_text(encoding="utf-8")
    assert "score_channel_cohort_support import" not in verifier


def test_support_fails_closed_on_cross_parent_candidate_reuse(tmp_path: Path):
    selection = make_selection(tmp_path, duplicate=True)
    with pytest.raises(SupportError, match="more than one selected parent"):
        produce(selection, REPO, tmp_path / "audit.json")


def test_independent_verifier_rejects_tampered_receipt(tmp_path: Path):
    selection = make_selection(tmp_path)
    audit = tmp_path / "audit.json"
    produce(selection, REPO, audit)
    value = json.loads(audit.read_text(encoding="utf-8"))
    value["support"]["counts"]["selected_candidates"] = 999
    audit.write_text(json.dumps(value, sort_keys=True, indent=2) + "\n", encoding="utf-8")
    with pytest.raises(VerificationError, match="differs"):
        verify(selection, audit, sha(audit))
