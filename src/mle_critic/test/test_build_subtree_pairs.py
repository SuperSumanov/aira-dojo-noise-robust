import json
import sys

from src.mle_critic.src.preprocess.build_bt_pairs.build_subtree_pairs import (
    build_children_index,
    build_value_pairs,
    compute_node_values,
    flatten_runs,
    main,
)
from src.mle_critic.src.preprocess.download_and_resolve.cards import (
    Card,
    Label,
    Lineage,
    Obs,
    TaskInfo,
    save_cards,
)


def make_card(
    card_id,
    grade,
    parent_id=None,
    *,
    runtime_s=1.0,
    higher_is_better=True,
):
    return Card(
        id=card_id,
        task=TaskInfo(name="task", higher_is_better=higher_is_better),
        obs=Obs(runtime_s=runtime_s),
        lineage=Lineage(parent_id=parent_id),
        label=Label(graded=grade) if grade is not None else None,
    )


def test_node_value_traverses_unlabelled_cards_and_applies_budgets():
    cards_by_run = {
        "run-a": [
            make_card("root", 0.2),
            make_card("bridge", None, "root", runtime_s=3.0),
            make_card("best", 0.9, "bridge", runtime_s=4.0),
        ]
    }
    cards_by_id, _ = flatten_runs(cards_by_run)
    children = build_children_index(cards_by_id)

    unlimited = compute_node_values(cards_by_id, children)
    assert unlimited["root"].best_subtree_grade == 0.9
    assert unlimited["root"].reachable_descendant_count == 2
    assert unlimited["root"].steps_to_best == 2

    assert "root" not in compute_node_values(
        cards_by_id, children, budget_steps=1
    )
    assert "root" not in compute_node_values(
        cards_by_id, children, budget_seconds=6.0
    )


def test_non_finite_grades_are_treated_as_missing():
    cards_by_run = {
        "run-a": [
            make_card("root", 0.2),
            make_card("nan-child", float("nan"), "root"),
            make_card("best", 0.9, "nan-child"),
        ]
    }
    cards_by_id, _ = flatten_runs(cards_by_run)

    values = compute_node_values(cards_by_id, build_children_index(cards_by_id))

    assert values["root"].best_subtree_grade == 0.9


def test_pair_metadata_is_ordered_as_better_then_worse():
    cards_by_run = {
        "run-a": [
            make_card("a", 0.1),
            make_card("a-child", 0.9, "a"),
            make_card("b", 0.8),
            make_card("b-child", 0.8, "b"),
            make_card("b-child-2", 0.8, "b"),
        ]
    }

    records, _ = build_value_pairs(cards_by_run, seed=7)

    assert len(records) == 1
    record = records[0]
    assert (record["better"], record["worse"]) == ("a", "b")
    assert record["agrees_with_quality"] is False
    assert record["subtree_sizes"] == [1, 2]
    assert record["steps_to_best"] == [1, 0]


def test_raw_pair_keeps_endpoints_from_different_runs_unassigned():
    cards_by_run = {
        "run-a": [
            make_card("a", 0.1),
            make_card("a-child", 0.9, "a"),
        ],
        "run-b": [
            make_card("b", 0.8),
            make_card("b-child", 0.8, "b"),
        ],
    }

    records, _ = build_value_pairs(cards_by_run, seed=7)

    assert len(records) == 1
    assert records[0]["intask_split"] == "unassigned"


def test_lower_score_is_oriented_as_better_when_task_says_so():
    cards_by_run = {
        "run-a": [
            make_card("a", 0.8, higher_is_better=False),
            make_card("a-child", 0.2, "a", higher_is_better=False),
            make_card("b", 0.3, higher_is_better=False),
            make_card("b-child", 0.3, "b", higher_is_better=False),
        ]
    }

    records, _ = build_value_pairs(cards_by_run)

    assert len(records) == 1
    assert (records[0]["better"], records[0]["worse"]) == ("a", "b")


def test_pair_filters_apply_before_computing_subtree_values():
    cards = {
        "run-a__2026-01-01": [
            make_card("a", 0.1),
            make_card("a-child", 0.9, "a"),
            make_card("b", 0.8),
            make_card("b-child", 0.8, "b"),
        ]
    }
    for card in cards["run-a__2026-01-01"]:
        card.time_limit = 100
        card.execution_timeout = 10
        card.client = "openai/gpt-5"
        card.hardware = "slurm/a100"

    records, _ = build_value_pairs(
        cards,
        time_limit=(100, 100),
        execution_timeout=(10, 10),
        client="gpt-5",
        hardware="a100",
        date=("2026-01-01", "2026-01-01"),
    )
    assert len(records) == 1

    excluding_filters = [
        {"time_limit": (101, 200)},
        {"execution_timeout": (11, 20)},
        {"client": "claude"},
        {"hardware": "h100"},
        {"date": ("2026-01-02", "2026-01-31")},
    ]
    for filters in excluding_filters:
        filtered_records, _ = build_value_pairs(cards, **filters)
        assert filtered_records == []


def test_main_reads_run_grouped_cards_and_writes_jsonl(tmp_path, monkeypatch):
    cards_path = tmp_path / "cards.json"
    output_path = tmp_path / "pairs.jsonl"
    save_cards(
        {
            "run-a": [
                make_card("a", 0.1),
                make_card("a-child", 0.9, "a"),
                make_card("b", 0.8),
                make_card("b-child", 0.8, "b"),
            ]
        },
        str(cards_path),
    )
    monkeypatch.setattr(
        sys,
        "argv",
        ["build_subtree_pairs", str(output_path), str(cards_path)],
    )

    main()

    records = [json.loads(line) for line in output_path.read_text().splitlines()]
    assert len(records) == 1
    assert (records[0]["better"], records[0]["worse"]) == ("a", "b")
