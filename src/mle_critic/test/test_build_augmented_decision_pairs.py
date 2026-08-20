import json
import sys

from src.mle_critic.src.preprocess.build_bt_pairs.build_augmented_decision_pairs import (
    build_decision_pairs,
    main,
)
from src.mle_critic.src.preprocess.download_and_resolve.cards import (
    Card,
    Obs,
    Label,
    Lineage,
    TaskInfo,
    save_cards,
)


def make_card(
    card_id,
    grade,
    parent_id=None,
    error=None,
    *,
    step,
    higher_is_better=True,
):
    return Card(
        id=card_id,
        obs=Obs(error=error),
        task=TaskInfo(name="task", higher_is_better=higher_is_better),
        lineage=Lineage(parent_id=parent_id, step=step),
        label=Label(graded=grade) if grade is not None else None,
    )


def decision_cards(higher_is_better=True):
    return {
        "run-a": [
            make_card("root-1", None, None, step=0, higher_is_better=higher_is_better),
            make_card(
                "a", 0.5, "root-1", None, step=1, higher_is_better=higher_is_better
            ),
            make_card(
                "b", 0.8, "root-1", None, step=2, higher_is_better=higher_is_better
            ),
            make_card(
                "a-ungraded", None, "a", "exec_error", step=3, higher_is_better=higher_is_better
            ),
            make_card(
                "a-best",
                0.9,
                "a-ungraded",
                None,
                step=4,
                higher_is_better=higher_is_better,
            ),
            make_card(
                "b-child-1", 0.8, "b", None, step=5, higher_is_better=higher_is_better
            ),
            make_card(
                "b-child-2", 0.8, "b", None, step=6, higher_is_better=higher_is_better
            ),
            make_card(
                "b-child-3", None, "b", "exec_error", step=7, higher_is_better=higher_is_better
            ),
            make_card(
                "b-child-4", 0.85, "b-child-3", None, step=8, higher_is_better=higher_is_better
            )
        ],
        "run-c": [
            make_card("root-2", None, None, step=0, higher_is_better=higher_is_better),
            make_card(
                "c", 0.6, "root-2", None, step=1, higher_is_better=higher_is_better
            ),
            make_card(
                "d", 0.9, "root-2", None, step=2, higher_is_better=higher_is_better
            ),
            make_card(
                "c-ungraded", None, "c", "exec_error", step=3, higher_is_better=higher_is_better
            ),
            make_card(
                "c-best",
                1.0,
                "c-ungraded",
                None,
                step=4,
                higher_is_better=higher_is_better,
            ),
            make_card(
                "d-child-1", 0.9, "d", None, step=5, higher_is_better=higher_is_better
            ),
            make_card(
                "d-child-2", 0.9, "d", None, step=6, higher_is_better=higher_is_better
            ),
            make_card(
                "d-child-3", None, "d", "exec_error", step=7, higher_is_better=higher_is_better
            ),
            make_card(
                "d-child-4", 0.95, "d-child-3", None, step=8, higher_is_better=higher_is_better
            )
        ]
    }


def test_improve_decision_pair_supports_current_and_full_lookahead_values():
    records, summary = build_decision_pairs(decision_cards(), budgets=[0, 1000])

    assert summary["pairs"] == 8
    assert [(record["budget"], record["better"], record["worse"]) for record in records] == [
        (0, "b-child-4", "b-child-1"),
        (0, "b-child-4", "b-child-2"),
        (1000, "b-child-4", "b-child-1"),
        (1000, "b-child-4", "b-child-2"),
        (0, "d-child-4", "d-child-1"),
        (0, "d-child-4", "d-child-2"),
        (1000, "d-child-4", "d-child-1"),
        (1000, "d-child-4", "d-child-2"),
    ]
    assert summary["pairs_at_budget_0"] == 4
    assert summary["pairs_at_budget_1000"] == 4
    assert all(record["intask_split"] == "unassigned" for record in records)


def test_lower_is_better_direction_comes_from_cards():
    records, _ = build_decision_pairs(
        decision_cards(higher_is_better=False), budgets=[1000], draft_pairs=True
    )

    assert len(records) == 6
    assert all(record["budget"] == 1000 for record in records)
    assert ("b", "d") in {(record["better"], record["worse"]) for record in records}


def test_error_nodes_do_not_enter_decision_values():
    cards = decision_cards()
    cards["run-a"][1].obs = Obs(error="exec_error")
    cards["run-c"][1].obs = Obs(error="exec_error")

    records, _ = build_decision_pairs(cards, budgets=[0], draft_pairs=True)

    assert len(records) == 5
    # It should be like (c-best, a-best), (c-best, d), (c-best, b), (a-best, b) and (d, b)
    assert all(record["better"] in ["c-best", "d", "a-best"] for record in records)
    assert all(record["worse"] in ["a-best", "b", "d"] for record in records)


def test_main_supports_lookahead_mode(tmp_path, monkeypatch):
    cards_path = tmp_path / "cards.json"
    pairs_path = tmp_path / "decision_raw.jsonl"
    save_cards(decision_cards(), str(cards_path))
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "build_augmented_decision_pairs",
            str(pairs_path),
            str(cards_path),
            "--lookahead",
        ],
    )

    main()

    records = [json.loads(line) for line in pairs_path.read_text().splitlines()]
    assert records
    assert {record["budget"] for record in records} == {1000}
