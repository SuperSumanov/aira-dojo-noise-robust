"""Build sibling preference pairs that match AIRA-Dojo branch decisions.

The input is the run-grouped Card JSON produced by ``build_cards``.  For every
parent with at least two visible children, the children form one decision set.
At budget ``K``, a child's value is the best external grade among the child and
its first ``K`` visible descendants in journal expansion order.

This command only constructs raw pairs.  It writes
``intask_split="unassigned"``; apply the frozen physical-run split afterwards
with ``build_bt_pairs.build_runsplit``.

Usage:
    python -m src.preprocess.build_bt_pairs.build_decision_pairs \
        OUT.jsonl CARDS.json --budgets 0,1,2
"""
from __future__ import annotations

import argparse
import itertools
import json
import math
from collections import Counter, defaultdict
from pathlib import Path
from typing import Mapping, Sequence

from ..download_and_resolve.cards import Card, load_cards


def index_cards(
    cards_by_run_id: Mapping[str, Sequence[Card]],
) -> tuple[dict[str, Card], dict[str, str]]:
    """Index Cards by ID and validate their physical run boundaries."""
    cards_by_id: dict[str, Card] = {}
    run_id_by_card_id: dict[str, str] = {}

    for run_id, run_cards in cards_by_run_id.items():
        task_names = {card.task.name for card in run_cards}
        if len(task_names) > 1:
            raise ValueError(
                f"Physical run {run_id!r} spans multiple tasks: {sorted(task_names)}"
            )
        for card in run_cards:
            if card.id in cards_by_id:
                previous_run = run_id_by_card_id[card.id]
                raise ValueError(
                    f"Duplicate Card ID {card.id!r} in runs "
                    f"{previous_run!r} and {run_id!r}"
                )
            cards_by_id[card.id] = card
            run_id_by_card_id[card.id] = run_id

    for card in cards_by_id.values():
        parent_id = card.lineage.parent_id
        if parent_id not in cards_by_id:
            continue
        if run_id_by_card_id[parent_id] != run_id_by_card_id[card.id]:
            raise ValueError(
                f"Card {card.id!r} and parent {parent_id!r} belong to different runs"
            )
        if cards_by_id[parent_id].task.name != card.task.name:
            raise ValueError(
                f"Card {card.id!r} and parent {parent_id!r} belong to different tasks"
            )

    return cards_by_id, run_id_by_card_id


def build_children_index(cards_by_id: Mapping[str, Card]) -> dict[str, list[str]]:
    """Return visible child Card IDs for every visible parent."""
    children_by_parent_id: dict[str, list[str]] = defaultdict(list)
    for card in cards_by_id.values():
        parent_id = card.lineage.parent_id
        if parent_id and parent_id in cards_by_id:
            children_by_parent_id[parent_id].append(card.id)
    return dict(children_by_parent_id)


def expansion_order(card: Card) -> tuple[float, str]:
    """Sort journal nodes by recorded expansion step, then by stable Card ID."""
    step = card.lineage.step
    return (float(step) if step is not None else float("inf"), card.id)


def descendants_in_expansion_order(
    card_id: str,
    cards_by_id: Mapping[str, Card],
    children_by_parent_id: Mapping[str, Sequence[str]],
) -> list[str]:
    """Return all visible descendants ordered by when the journal expanded them."""
    descendants: list[str] = []
    pending = list(children_by_parent_id.get(card_id, []))
    visited = {card_id}

    while pending:
        descendant_id = pending.pop()
        if descendant_id in visited:
            continue
        visited.add(descendant_id)
        descendants.append(descendant_id)
        pending.extend(children_by_parent_id.get(descendant_id, []))

    descendants.sort(
        key=lambda descendant_id: expansion_order(cards_by_id[descendant_id])
    )
    return descendants


def graded_score(card: Card) -> float | None:
    """Return a finite external grade, treating NaN/Inf as missing labels."""
    if card.label is None or card.label.graded is None:
        return None
    score = float(card.label.graded)
    return score if math.isfinite(score) else None


def resolve_task_directions(cards_by_id: Mapping[str, Card]) -> dict[str, bool]:
    """Resolve metric direction from graded Cards and reject contradictions."""
    higher_is_better_by_task: dict[str, bool] = {}
    for card in cards_by_id.values():
        if graded_score(card) is None:
            continue
        previous = higher_is_better_by_task.setdefault(
            card.task.name, card.task.higher_is_better
        )
        if previous != card.task.higher_is_better:
            raise ValueError(
                f"Inconsistent higher_is_better values for task {card.task.name!r}"
            )
    return higher_is_better_by_task


def lookahead_value(
    card_id: str,
    budget: int,
    cards_by_id: Mapping[str, Card],
    descendant_ids: Sequence[str],
    higher_is_better: bool,
) -> float | None:
    """Compute value after exactly ``budget`` recorded descendant expansions.

    An ungraded node still consumes one expansion from the budget.  It simply
    contributes no score to the best-grade aggregation.  The value is undefined
    when fewer than ``budget`` descendants exist or no grade is visible in the
    child-plus-budget window.
    """
    if len(descendant_ids) < budget:
        return None

    visible_card_ids = [card_id, *descendant_ids[:budget]]
    visible_grades = [
        score
        for visible_card_id in visible_card_ids
        if (score := graded_score(cards_by_id[visible_card_id])) is not None
    ]
    if not visible_grades:
        return None
    return (max if higher_is_better else min)(visible_grades)


def build_decision_pairs(
    cards_by_run_id: Mapping[str, Sequence[Card]],
    budgets: Sequence[int],
) -> tuple[list[dict], dict[str, int]]:
    """Build all unequal sibling pairs for each requested lookahead budget."""
    if not budgets:
        raise ValueError("At least one budget is required")
    if any(budget < 0 for budget in budgets):
        raise ValueError("Budgets must be non-negative")
    if len(set(budgets)) != len(budgets):
        raise ValueError("Budgets must not contain duplicates")

    cards_by_id, _ = index_cards(cards_by_run_id)
    children_by_parent_id = build_children_index(cards_by_id)
    higher_is_better_by_task = resolve_task_directions(cards_by_id)

    descendants_by_card_id: dict[str, list[str]] = {}

    def descendants_for(card_id: str) -> list[str]:
        if card_id not in descendants_by_card_id:
            descendants_by_card_id[card_id] = descendants_in_expansion_order(
                card_id, cards_by_id, children_by_parent_id
            )
        return descendants_by_card_id[card_id]

    records: list[dict] = []
    pair_counts: Counter[tuple[int, str]] = Counter()
    decision_set_counts: Counter[str] = Counter()

    for parent_id in sorted(children_by_parent_id):
        sibling_ids = sorted(
            children_by_parent_id[parent_id],
            key=lambda card_id: expansion_order(cards_by_id[card_id]),
        )
        if len(sibling_ids) < 2:
            continue

        task_name = cards_by_id[sibling_ids[0]].task.name
        if any(
            cards_by_id[card_id].task.name != task_name
            for card_id in sibling_ids
        ):
            raise ValueError(f"Siblings under {parent_id!r} span multiple tasks")
        if task_name not in higher_is_better_by_task:
            continue

        decision_set_counts[task_name] += 1
        higher_is_better = higher_is_better_by_task[task_name]
        for budget in budgets:
            value_by_card_id = {
                card_id: lookahead_value(
                    card_id,
                    budget,
                    cards_by_id,
                    descendants_for(card_id),
                    higher_is_better,
                )
                for card_id in sibling_ids
            }
            for left_id, right_id in itertools.combinations(sibling_ids, 2):
                left_value = value_by_card_id[left_id]
                right_value = value_by_card_id[right_id]
                if (
                    left_value is None
                    or right_value is None
                    or left_value == right_value
                ):
                    continue

                left_is_better = (
                    left_value > right_value
                    if higher_is_better
                    else left_value < right_value
                )
                better_id, worse_id = (
                    (left_id, right_id) if left_is_better else (right_id, left_id)
                )
                records.append(
                    {
                        "task": task_name,
                        "better": better_id,
                        "worse": worse_id,
                        "budget": budget,
                        "parent": parent_id,
                        "set_size": len(sibling_ids),
                        "gap_raw": round(abs(left_value - right_value), 6),
                        "intask_split": "unassigned",
                        "loto_fold": task_name,
                        "clears_tau": None,
                        "src": "decision",
                    }
                )
                pair_counts[(budget, task_name)] += 1

    summary = {
        "pairs": len(records),
        "decision_sets": sum(decision_set_counts.values()),
        "tasks_with_decision_sets": len(decision_set_counts),
    }
    for budget in budgets:
        summary[f"pairs_at_budget_{budget}"] = sum(
            count
            for (pair_budget, _), count in pair_counts.items()
            if pair_budget == budget
        )
    return records, summary


def parse_budgets(raw_budgets: str) -> list[int]:
    """Parse a comma-separated budget list with useful validation errors."""
    try:
        budgets = [int(value.strip()) for value in raw_budgets.split(",")]
    except ValueError as error:
        raise argparse.ArgumentTypeError(
            f"Budgets must be comma-separated integers: {raw_budgets!r}"
        ) from error
    if not budgets or any(budget < 0 for budget in budgets):
        raise argparse.ArgumentTypeError("Budgets must be non-negative integers")
    if len(set(budgets)) != len(budgets):
        raise argparse.ArgumentTypeError("Budgets must not contain duplicates")
    return budgets


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("out", type=Path, help="raw decision-pair JSONL")
    parser.add_argument("cards", type=Path, help="run-grouped Card JSON")
    parser.add_argument(
        "--budgets",
        type=parse_budgets,
        default=parse_budgets("0,1,2"),
        help="comma-separated descendant expansion budgets",
    )
    return parser.parse_args()


def main() -> None:
    arguments = parse_args()
    cards_by_run_id = load_cards(str(arguments.cards))
    records, summary = build_decision_pairs(cards_by_run_id, arguments.budgets)

    arguments.out.parent.mkdir(parents=True, exist_ok=True)
    with arguments.out.open("w", encoding="utf-8") as output_file:
        for record in records:
            output_file.write(json.dumps(record, ensure_ascii=False) + "\n")

    print(f"[decision_pairs] {summary['pairs']} pairs -> {arguments.out}")
    for budget in arguments.budgets:
        print(f"  K={budget}: {summary[f'pairs_at_budget_{budget}']}")
    print(
        f"  decision sets={summary['decision_sets']} "
        f"tasks={summary['tasks_with_decision_sets']}"
    )


if __name__ == "__main__":
    main()
