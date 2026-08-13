import json
import hashlib
from pathlib import Path

from phase1 import source_journal_run_ids as module


def journal(path: Path, task: str, nodes: list[tuple[str, int]]) -> None:
    path.parent.mkdir(parents=True)
    rows = []
    for node_id, step in nodes:
        rows.append(
            {
                "id": node_id,
                "step": step,
                "code": "print(1)",
                "metric_info": {"competition_id": task},
            }
        )
    path.write_text("".join(json.dumps(row) + "\n" for row in rows), encoding="utf-8")


def test_source_journals_separate_runs_when_labeled_steps_do_not_reset(tmp_path: Path) -> None:
    root = tmp_path / "journals"
    journal(root / "run_a" / "checkpoint" / "journal.jsonl", "task", [("a1", 1), ("a2", 2)])
    journal(root / "run_b" / "checkpoint" / "journal.jsonl", "task", [("b6", 6), ("b7", 7)])
    rows = [
        {"id": "task__a1", "task": {"name": "task"}, "lineage": {"parent_id": None}},
        {"id": "task__a2", "task": {"name": "task"}, "lineage": {"parent_id": "task__a1"}},
        {"id": "task__b6", "task": {"name": "task"}, "lineage": {"parent_id": None}},
        {"id": "task__b7", "task": {"name": "task"}, "lineage": {"parent_id": "task__b6"}},
    ]
    card_source, journal_meta, audit = module.source_index(rows, root)
    run_map, provenance, run_audit = module.assign_runs(rows, card_source, "batch.jsonl")
    assert audit["matched_journals"] == 2
    assert run_audit == {
        "runs": 2,
        "parent_cross_run_violations": 0,
        "mixed_task_runs": 0,
    }
    assert run_map["task__a2"] != run_map["task__b6"]
    assert set(run_map.values()) == {"batch.jsonl:0", "batch.jsonl:1"}
    assert len(provenance) == 2


def test_source_mapping_rejects_unmapped_card(tmp_path: Path) -> None:
    root = tmp_path / "journals"
    journal(root / "run_a" / "checkpoint" / "journal.jsonl", "task", [("a1", 1)])
    rows = [
        {"id": "task__a1", "task": {"name": "task"}, "lineage": {"parent_id": None}},
        {"id": "task__missing", "task": {"name": "task"}, "lineage": {"parent_id": None}},
    ]
    try:
        module.source_index(rows, root)
    except module.IntegrityError as error:
        assert "mapping not exact" in str(error)
    else:
        raise AssertionError("unmapped card did not fail closed")


def test_source_mapping_rejects_credential_before_parsing_json(tmp_path: Path) -> None:
    root = tmp_path / "journals"
    path = root / "run_a" / "checkpoint" / "journal.jsonl"
    path.parent.mkdir(parents=True)
    path.write_bytes(b"not-json sk-" + b"x" * 24 + b"\n")
    rows = [
        {"id": "task__a1", "task": {"name": "task"}, "lineage": {"parent_id": None}}
    ]
    try:
        module.source_index(rows, root)
    except module.IntegrityError as error:
        assert "credential shapes" in str(error)
    else:
        raise AssertionError("credential-bearing journal did not fail closed")


def test_source_mapping_rejects_cross_journal_parent(tmp_path: Path) -> None:
    root = tmp_path / "journals"
    journal(root / "run_a" / "checkpoint" / "journal.jsonl", "task", [("a1", 1)])
    journal(root / "run_b" / "checkpoint" / "journal.jsonl", "task", [("b1", 2)])
    rows = [
        {"id": "task__a1", "task": {"name": "task"}, "lineage": {"parent_id": None}},
        {"id": "task__b1", "task": {"name": "task"}, "lineage": {"parent_id": "task__a1"}},
    ]
    card_source, _, _ = module.source_index(rows, root)
    try:
        module.assign_runs(rows, card_source, "batch.jsonl")
    except module.IntegrityError as error:
        assert "parent/task validation" in str(error)
    else:
        raise AssertionError("cross-journal parent did not fail closed")


def test_write_cards_preserves_exact_order_and_refuses_overwrite(tmp_path: Path) -> None:
    rows = [
        {
            "id": "task__a1",
            "task": {"name": "task"},
            "lineage": {"parent_id": None},
            "provenance": {"existing": "kept"},
        }
    ]
    run_map = {"task__a1": "batch.jsonl:0"}
    provenance = {"batch.jsonl:0": {"source_journal": "run_a/checkpoint/journal.jsonl"}}
    journal_meta = {
        "run_a/checkpoint/journal.jsonl": {"source_journal_sha256": "a" * 64}
    }
    output = tmp_path / "cards.jsonl"
    digest = module.write_cards(output, rows, run_map, provenance, journal_meta)
    assert digest == hashlib.sha256(output.read_bytes()).hexdigest()
    emitted = json.loads(output.read_text(encoding="utf-8"))
    assert emitted["run_id"] == "batch.jsonl:0"
    assert emitted["provenance"]["existing"] == "kept"
    assert emitted["provenance"]["run_id_source"] == "source-journal-path:pre-flattening"
    try:
        module.write_cards(output, rows, run_map, provenance, journal_meta)
    except FileExistsError:
        pass
    else:
        raise AssertionError("existing output was overwritten")
