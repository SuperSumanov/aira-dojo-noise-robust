import json

import pytest

from src.mle_critic.src.preprocess.build_bt_pairs.apply_runsplit import (
    apply_runsplit,
    assign_pair_split,
    index_run_by_card_id,
)
from src.mle_critic.src.preprocess.download_and_resolve.cards import Card, TaskInfo


def make_card(card_id):
    return Card(id=card_id, task=TaskInfo(name="task"))


def test_apply_runsplit_marks_train_and_test_and_drops_crossing_pairs(tmp_path):
    cards_by_run = {
        "train-a": [make_card("ta")],
        "train-b": [make_card("tb")],
        "test-a": [make_card("ea")],
        "test-b": [make_card("eb")],
    }
    run_by_card = index_run_by_card_id(cards_by_run)
    raw_path = tmp_path / "raw.jsonl"
    output_path = tmp_path / "split.jsonl"
    raw_records = [
        {"better": "ta", "worse": "tb", "intask_split": "unassigned"},
        {"better": "ea", "worse": "eb", "intask_split": "unassigned"},
        {"better": "ta", "worse": "ea", "intask_split": "unassigned"},
    ]
    raw_path.write_text("".join(json.dumps(record) + "\n" for record in raw_records))

    counts = apply_runsplit(
        raw_path,
        output_path,
        run_by_card,
        held_out_runs={"test-a", "test-b"},
        assigned_runs=set(cards_by_run),
    )

    output_records = [
        json.loads(line) for line in output_path.read_text().splitlines()
    ]
    assert [record["intask_split"] for record in output_records] == [
        "train",
        "test",
    ]
    assert counts == {"train": 1, "test": 1, "dropped_straddling": 1}


def test_pair_on_unassigned_run_fails_with_update_instruction():
    with pytest.raises(ValueError, match="Update the runsplit"):
        assign_pair_split(
            {"better": "a", "worse": "b"},
            {"a": "assigned", "b": "new-run"},
            held_out_runs=set(),
            assigned_runs={"assigned"},
        )
