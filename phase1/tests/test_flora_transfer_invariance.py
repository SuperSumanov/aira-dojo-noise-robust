import hashlib
import json
from pathlib import Path

from phase1.flora_transfer_invariance import (
    endpoint_from_row,
    load_prospective,
    summarize_cohort,
)


def _row(identifier: str, op: str = "Improve", code: str | None = None) -> dict:
    return {
        "id": identifier,
        "task": "task-slug",
        "run_id": "run-1",
        "code": code or f"print('{identifier}')",
        "lineage": {
            "parent_id": "parent-1",
            "op": op,
            "depth": 2,
            "step": 3,
            "n_siblings": 2,
        },
    }


def test_monolithic_candidate_code_is_not_relabelled_as_workflow_graph() -> None:
    endpoint = endpoint_from_row(_row("a"), prospective=False)
    assert endpoint["candidate_code_available"] is True
    assert endpoint["task_identifier_available"] is True
    assert not any(endpoint["literal"].values())


def test_v11_nested_task_description_is_counted_but_task_slug_is_not() -> None:
    row = _row("a")
    row["task"] = {"name": "task-slug", "desc": "Predict the target from tabular data."}
    endpoint = endpoint_from_row(row, prospective=False)
    assert endpoint["task"] == "task-slug"
    assert endpoint["literal"]["natural_language_task_description"] is True


def test_lineage_pair_is_invariant_when_only_candidate_code_changes() -> None:
    cards = {name: endpoint_from_row(_row(name), prospective=False) for name in ("a", "b")}
    summary = summarize_cohort(cards, [("a", "b")])
    assert summary["pair_invariance"]["noncode_pair_invariant_fraction"] == 1.0
    assert summary["pair_invariance"]["noncode_discriminative_pairs"] == 0
    assert summary["pair_invariance"]["exact_code_distinct_fraction"] == 1.0


def test_operator_difference_makes_lineage_view_nondegenerate() -> None:
    cards = {
        "a": endpoint_from_row(_row("a", op="Debug"), prospective=False),
        "b": endpoint_from_row(_row("b", op="Improve"), prospective=False),
    }
    summary = summarize_cohort(cards, [("a", "b")])
    assert summary["pair_invariance"]["noncode_discriminative_pairs"] == 1
    assert summary["pair_invariance"]["differences_by_lineage_field"]["op"] == 1


def _write_json(path: Path, value: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, sort_keys=True) + "\n", encoding="utf-8")


def _write_jsonl(path: Path, values: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("".join(json.dumps(value, sort_keys=True) + "\n" for value in values), encoding="utf-8")


def _sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def test_prospective_loader_uses_blind_manifest_and_first960_order(tmp_path: Path) -> None:
    state = tmp_path / "state"
    snapshot = state / "snapshots" / ("a" * 64)
    intake = state / "intakes" / "drop-1"
    manifest = intake / "eligible_blind_manifest.jsonl"
    rows = []
    for identifier in ("a", "b"):
        code = f"print('{identifier}')"
        rows.append(
            {
                "card_id": identifier,
                "task": "task-slug",
                "run_id": "run-1",
                "code": code,
                "code_sha256": hashlib.sha256(code.encode()).hexdigest(),
                "lineage": {"depth": 2, "step": 3, "n_siblings": 2, "op": "Improve", "parent": "p"},
                "generation_started_at_utc": "2026-08-20T00:00:00Z",
                "source_sha256": "b" * 64,
            }
        )
    _write_jsonl(manifest, rows)
    summary_path = intake / "summary.json"
    _write_json(
        summary_path,
        {
            "outputs": {"eligible_blind_manifest_sha256": _sha(manifest)},
            "security": {"env_members_read": False, "live_event_journal_members_read": False},
            "blindness": {
                "labels_used_for_run_selection": False,
                "labels_used_for_endpoint_selection": False,
                "metrics_computed": [],
            },
        },
    )
    _write_jsonl(
        snapshot / "intake_registry.jsonl",
        [{"drop_id": "drop-1", "intake_dir": str(intake.resolve()), "summary_sha256": _sha(summary_path)}],
    )
    _write_jsonl(
        snapshot / "accumulator" / "provisional_runs.jsonl",
        [
            {
                "run_id": "run-1",
                "task": "task-slug",
                "drop_id": "drop-1",
                "flow_status": "scoreable",
                "endpoints": 2,
                "generation_started_at_utc": "2026-08-20T00:00:00Z",
                "source_sha256": "b" * 64,
            }
        ],
    )
    cards, pairs, metadata = load_prospective(state, snapshot, 960)
    assert set(cards) == {"a", "b"}
    assert pairs == [("a", "b")]
    assert metadata["observed_runs"] == 1


def test_summary_never_contains_identity_or_code_values() -> None:
    cards = {name: endpoint_from_row(_row(name), prospective=False) for name in ("a", "b")}
    blob = json.dumps(summarize_cohort(cards, [("a", "b")]), sort_keys=True)
    assert "task-slug" not in blob
    assert "run-1" not in blob
    assert "parent-1" not in blob
    assert "print(" not in blob
