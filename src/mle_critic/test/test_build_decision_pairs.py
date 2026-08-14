import json
import sys

from src.mle_critic.src.preprocess.build_bt_pairs.build_decision_pairs import (
    build_decision_pairs,
    main,
)
from src.mle_critic.src.preprocess.download_and_resolve.cards import (
    Card,
    Label,
    Lineage,
    TaskInfo,
    save_cards,
)


def make_card(
    card_id,
    grade,
    parent_id=None,
    *,
    step,
    higher_is_better=True,
):
    return Card(
        id=card_id,
        task=TaskInfo(name="task", higher_is_better=higher_is_better),
        lineage=Lineage(parent_id=parent_id, step=step),
        label=Label(graded=grade) if grade is not None else None,
    )


def decision_cards(higher_is_better=True):
    return {
        "run-a": [
            make_card("root", None, step=0, higher_is_better=higher_is_better),
            make_card(
                "a", 0.5, "root", step=1, higher_is_better=higher_is_better
            ),
            make_card(
                "b", 0.8, "root", step=2, higher_is_better=higher_is_better
            ),
            make_card(
                "a-ungraded", None, "a", step=3, higher_is_better=higher_is_better
            ),
            make_card(
                "a-best",
                0.9,
                "a-ungraded",
                step=4,
                higher_is_better=higher_is_better,
            ),
            make_card(
                "b-child-1", 0.8, "b", step=5, higher_is_better=higher_is_better
            ),
            make_card(
                "b-child-2", 0.8, "b", step=6, higher_is_better=higher_is_better
            ),
        ]
    }


def test_decision_pair_value_uses_first_k_expansions_including_ungraded_nodes():
    records, summary = build_decision_pairs(decision_cards(), budgets=[0, 1, 2])

    assert summary["pairs"] == 3
    assert [(record["budget"], record["better"], record["worse"]) for record in records] == [
        (0, "b", "a"),
        (1, "b", "a"),
        (2, "a", "b"),
    ]
    assert all(record["intask_split"] == "unassigned" for record in records)
    assert all(record["set_size"] == 2 for record in records)


def test_lower_is_better_direction_comes_from_cards():
    records, _ = build_decision_pairs(
        decision_cards(higher_is_better=False), budgets=[0]
    )

    assert len(records) == 1
    assert (records[0]["better"], records[0]["worse"]) == ("a", "b")


def test_non_finite_grades_do_not_enter_decision_values():
    cards = decision_cards()
    cards["run-a"][1].label = Label(graded=float("nan"))

    records, _ = build_decision_pairs(cards, budgets=[0])

    assert records == []


def test_main_reads_grouped_cards_and_writes_raw_pairs(tmp_path, monkeypatch):
    cards_path = tmp_path / "cards.json"
    pairs_path = tmp_path / "decision_raw.jsonl"
    save_cards(decision_cards(), str(cards_path))
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "build_decision_pairs",
            str(pairs_path),
            str(cards_path),
            "--budgets",
            "0,2",
        ],
    )

    main()

    records = [json.loads(line) for line in pairs_path.read_text().splitlines()]
    assert [record["budget"] for record in records] == [0, 2]
