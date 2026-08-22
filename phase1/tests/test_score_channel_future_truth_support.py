from __future__ import annotations

from collections import Counter
import hashlib
import json
from pathlib import Path

import pytest

from phase1 import score_channel_future_truth_support as producer
from phase1 import verify_score_channel_future_truth_support as verifier


REPO = Path(__file__).resolve().parents[2]
PROTOCOL = REPO / "phase1" / "score_channel_future_identifiability_protocol_v1.json"
PROTOCOL_SHA = producer.FROZEN_PROTOCOL_SHA256


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def text_digest(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def write_json(path: Path, value: object) -> None:
    path.write_text(
        json.dumps(value, indent=2, sort_keys=True, allow_nan=False) + "\n",
        encoding="utf-8",
        newline="\n",
    )


def write_rows(path: Path, rows: list[dict]) -> None:
    path.write_text(
        "".join(json.dumps(row, sort_keys=True, separators=(",", ":"), allow_nan=False) + "\n" for row in rows),
        encoding="utf-8",
        newline="\n",
    )


def selected_task(index: int) -> str:
    if index < 20:
        return "task-0"
    # Counts across task-1..task-7 are 9,9,9,9,8,8,8.
    return f"task-{1 + min(6, (index - 20) // 9)}"


def build_fixture(
    tmp_path: Path,
    *,
    selected_runs: int = 80,
    parents_per_selected_run: int = 1,
    tie_run: int | None = None,
    unavailable_run: int | None = None,
) -> tuple[Path, Path, str]:
    state = tmp_path / "state"
    intake = state / "intakes" / "drop-a"
    intake.mkdir(parents=True)
    archive_sha = "a" * 64
    pairs: list[dict] = []
    vault: list[dict] = []
    runs: list[dict] = []
    for run_index in range(300):
        journal = text_digest(f"journal-{run_index}")
        run_id = f"journal:{journal}"
        task = selected_task(run_index) if run_index < selected_runs else f"task-{run_index % 10}"
        runs.append({
            "archive_relative_path": "0821/drop-a.tar.gz",
            "archive_sha256": archive_sha,
            "drop_id": "drop-a",
            "endpoints": 2 if run_index < selected_runs else 0,
            "flow_status": "scoreable" if run_index < selected_runs else "no_scoreable_code",
            "generation_started_at_utc": f"2026-08-22T12:{run_index % 60:02d}:00Z",
            "journal_sha256": journal,
            "run_id": run_id,
            "task": task,
        })
        if run_index >= selected_runs:
            continue
        for parent_index in range(parents_per_selected_run):
            parent = f"parent-{run_index:03d}-{parent_index}"
            children = [f"card-{run_index:03d}-{parent_index}-{child}" for child in range(2)]
            pairs.append({
                "task": task,
                "run_id": run_id,
                "parent": parent,
                "left": children[0],
                "right": children[1],
            })
            for child_index, card in enumerate(children):
                high = 0.0 if tie_run == run_index else 0.1
                y_norm = 0.0 if child_index == 0 else high
                if unavailable_run == run_index and child_index == 1 and parent_index == 0:
                    y_norm = None
                vault.append({
                    "card_id": card,
                    "task": task,
                    "run_id": run_id,
                    "graded": 0.5 + child_index,
                    "y_norm": y_norm,
                    "eligible_by_start_time": True,
                })

    pair_path = intake / "eligible_structural_pairs.jsonl"
    vault_path = intake / "label_vault.jsonl"
    write_rows(pair_path, pairs)
    write_rows(vault_path, vault)
    intake_summary = {
        "protocol": "prospective_drop_intake_v1",
        "status": "PROSPECTIVE_DROP_INTAKE_COMPLETE",
        "blindness": {
            "labels_used_for_run_selection": False,
            "labels_used_for_endpoint_selection": False,
            "label_values_printed": False,
            "metrics_computed": [],
        },
        "security": {
            "credential_shaped_journals": 0,
            "env_members_extracted": False,
            "env_members_read": False,
            "journal_scanned_before_json": True,
            "live_event_journal_members_read": False,
            "precutoff_code_sha256_overlap": 0,
            "precutoff_endpoint_id_overlap": 0,
            "raw_journals_written": False,
        },
        "outputs": {
            "eligible_structural_pairs_sha256": digest(pair_path),
            "label_vault_sha256": digest(vault_path),
        },
    }
    intake_summary_path = intake / "summary.json"
    write_json(intake_summary_path, intake_summary)

    cohort = tmp_path / "cohort"
    cohort.mkdir()
    run_path = cohort / "cohort_runs.jsonl"
    write_rows(run_path, runs)
    archive_rows = [{
        "archive_relative_path": "0821/drop-a.tar.gz",
        "archive_sha256": archive_sha,
        "archive_size": 123,
        "cumulative_unique_physical_runs": 300,
        "drop_id": "drop-a",
        "intake_summary_sha256": digest(intake_summary_path),
        "mtime_ns": 1787407963000000000,
        "physical_runs": 300,
        "source_provenance_sha256": "b" * 64,
    }]
    archive_path = cohort / "cohort_archives.jsonl"
    write_rows(archive_path, archive_rows)
    task_counts = Counter(row["task"] for row in runs)
    cohort_summary = {
        "protocol": "score-channel-future-identity-cohort-v1",
        "status": "FUTURE_COHORT_IDENTITY_CLOSED_TRUTH_UNREAD",
        "inputs": {
            "protocol_sha256": PROTOCOL_SHA,
            "intake_summary_sha256": {"drop-a": digest(intake_summary_path)},
            "source_provenance_sha256": {"drop-a": "b" * 64},
        },
        "closure": {
            "accepted_unique_physical_run_target": 300,
            "boundary_archive": "0821/drop-a.tar.gz",
            "complete_boundary_archive_included": True,
            "remaining_runs_to_target": 0,
        },
        "inventory": {
            "selected_archives": 1,
            "selected_physical_runs": 300,
            "selected_tasks": len(task_counts),
            "per_task_selected_runs": dict(sorted(task_counts.items())),
        },
        "blindness": {
            "label_vault_opened": False,
            "score_or_outcome_opened": False,
            "truth_support_computed": False,
            "replay_submission_authorized": False,
        },
        "outputs": {
            "cohort_runs_sha256": digest(run_path),
            "cohort_archives_sha256": digest(archive_path),
        },
    }
    summary_path = cohort / "summary.json"
    write_json(summary_path, cohort_summary)
    return state, cohort, digest(summary_path)


def run_producer(tmp_path: Path, state: Path, cohort: Path, cohort_sha: str, name: str = "truth") -> tuple[Path, dict]:
    output = tmp_path / name
    summary = producer.produce(
        PROTOCOL,
        PROTOCOL_SHA,
        cohort,
        cohort_sha,
        state,
        REPO,
        output,
    )
    return output, summary


def test_exact_gate_boundary_passes_and_independent_verifier_agrees(tmp_path: Path) -> None:
    state, cohort, cohort_sha = build_fixture(tmp_path)
    output, summary = run_producer(tmp_path, state, cohort, cohort_sha)
    assert summary["status"] == "TRUTH_SUPPORT_ELIGIBLE_REPLAY_DESIGN_REQUEST_ONLY"
    assert summary["truth_support"]["counts"] == {
        "selected_parents": 80,
        "selected_candidates": 160,
        "selected_physical_runs": 80,
        "selected_tasks": 8,
        "truth_available_parents": 80,
        "truth_unavailable_parents": 0,
        "tied_parents": 0,
        "nontied_parents": 80,
        "tasks_with_nontied_parent": 8,
    }
    assert summary["truth_support"]["balance"]["dominant_nontied_task_share"] == 0.25
    assert summary["truth_support"]["gates"]["all_pass"] is True
    assert summary["decision"]["replay_submission_authorized"] is False
    receipt = verifier.verify(
        PROTOCOL,
        PROTOCOL_SHA,
        cohort,
        cohort_sha,
        state,
        output,
        tmp_path / "receipt.json",
    )
    assert receipt["status"] == "PASS_ELIGIBLE_REPLAY_DESIGN_REQUEST_ONLY"
    assert receipt["producer_module_imported"] is False


def test_one_tie_below_threshold_kills_without_changing_selection(tmp_path: Path) -> None:
    state, cohort, cohort_sha = build_fixture(tmp_path, tie_run=0)
    output, summary = run_producer(tmp_path, state, cohort, cohort_sha)
    assert summary["status"] == "TRUTH_SUPPORT_KILL_NO_REPLAY_REQUEST"
    assert summary["truth_support"]["counts"]["selected_parents"] == 80
    assert summary["truth_support"]["counts"]["nontied_parents"] == 79
    assert summary["truth_support"]["counts"]["tied_parents"] == 1
    assert summary["truth_support"]["gates"]["nontied_selected_parents"] is False
    receipt = verifier.verify(
        PROTOCOL, PROTOCOL_SHA, cohort, cohort_sha, state, output, tmp_path / "receipt.json"
    )
    assert receipt["status"] == "PASS_KILL_NO_REPLAY_REQUEST"


def test_missing_y_norm_is_unavailable_and_never_reselected(tmp_path: Path) -> None:
    state, cohort, cohort_sha = build_fixture(tmp_path, unavailable_run=0)
    output, summary = run_producer(tmp_path, state, cohort, cohort_sha)
    rows = [json.loads(line) for line in (output / "selected_parents.jsonl").read_text(encoding="utf-8").splitlines()]
    assert len(rows) == 80
    assert any(row["run_id"].endswith(text_digest("journal-0")) for row in rows)
    assert summary["truth_support"]["counts"]["truth_unavailable_parents"] == 1
    assert summary["truth_support"]["counts"]["nontied_parents"] == 79
    assert all(not ({"graded", "y_norm", "gap", "winner"} & set(row)) for row in rows)


def test_per_run_cap_uses_frozen_hash_lottery(tmp_path: Path) -> None:
    state, cohort, cohort_sha = build_fixture(tmp_path, parents_per_selected_run=3)
    output, summary = run_producer(tmp_path, state, cohort, cohort_sha)
    rows = [json.loads(line) for line in (output / "selected_parents.jsonl").read_text(encoding="utf-8").splitlines()]
    assert len(rows) == 160
    assert summary["identity"]["eligible_parents_before_per_run_cap"] == 240
    per_run = Counter(row["run_id"] for row in rows)
    assert set(per_run.values()) == {2}
    first = [row for row in rows if row["run_id"] == rows[0]["run_id"]]
    possible = []
    for parent_index in range(3):
        parent = f"parent-000-{parent_index}"
        possible.append((text_digest(f"20260813|{rows[0]['run_id']}|{parent}"), parent))
    assert [row["parent_id"] for row in first] == [parent for _, parent in sorted(possible)[:2]]


def test_collecting_cohort_fails_before_label_vault_open(tmp_path: Path) -> None:
    state, cohort, _ = build_fixture(tmp_path)
    summary_path = cohort / "summary.json"
    summary = json.loads(summary_path.read_text(encoding="utf-8"))
    summary["status"] = "FUTURE_COHORT_COLLECTING"
    summary["closure"]["remaining_runs_to_target"] = 1
    write_json(summary_path, summary)
    (state / "intakes" / "drop-a" / "label_vault.jsonl").unlink()
    with pytest.raises(producer.TruthSupportError, match="closed truth-unread"):
        run_producer(tmp_path, state, cohort, digest(summary_path))


def test_outputs_are_byte_deterministic_and_raw_labels_absent(tmp_path: Path) -> None:
    state, cohort, cohort_sha = build_fixture(tmp_path)
    first, summary_a = run_producer(tmp_path, state, cohort, cohort_sha, "first")
    second, summary_b = run_producer(tmp_path, state, cohort, cohort_sha, "second")
    assert (first / "selected_parents.jsonl").read_bytes() == (second / "selected_parents.jsonl").read_bytes()
    scientific_a = {key: value for key, value in summary_a.items() if key != "implementation"}
    scientific_b = {key: value for key, value in summary_b.items() if key != "implementation"}
    assert scientific_a == scientific_b
    blob = (first / "selected_parents.jsonl").read_text(encoding="utf-8")
    assert '"graded"' not in blob and '"y_norm"' not in blob and '"gap"' not in blob


def test_independent_verifier_rejects_tampered_selection(tmp_path: Path) -> None:
    state, cohort, cohort_sha = build_fixture(tmp_path)
    output, _ = run_producer(tmp_path, state, cohort, cohort_sha)
    rows_path = output / "selected_parents.jsonl"
    rows = [json.loads(line) for line in rows_path.read_text(encoding="utf-8").splitlines()]
    rows[0]["selection_rank_in_run"] = 2
    write_rows(rows_path, rows)
    with pytest.raises(verifier.VerificationError, match="reconstruction mismatch"):
        verifier.verify(
            PROTOCOL, PROTOCOL_SHA, cohort, cohort_sha, state, output, tmp_path / "receipt.json"
        )


def test_verifier_source_is_independent_of_producer_module() -> None:
    source = (REPO / "phase1" / "verify_score_channel_future_truth_support.py").read_text(encoding="utf-8")
    assert "from phase1 import score_channel_future_truth_support" not in source
    assert "import score_channel_future_truth_support" not in source
