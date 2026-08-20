"""Build sibling preference pairs that match AIRA-Dojo branch decisions.

The input is the run-grouped Card JSON produced by ``build_cards``.  For every
parent with at least two visible children, the children form one decision set.
At budget zero, a child's value is its current external grade.  At a positive
budget, its value is the best external grade among the child and up to that
many visible descendants in journal expansion order.

This command only constructs raw pairs.  It writes
``intask_split="unassigned"``; apply the frozen physical-run split afterwards
with ``build_bt_pairs.build_runsplit``.

Usage:
    python -m src.preprocess.build_bt_pairs.build_augmented_decision_pairs \
        OUT.jsonl CARDS.json [--cap N] [--seed N] [--budget N] [--draft_pairs]
"""
from __future__ import annotations

import argparse
import itertools
import json
import math
from collections import Counter, defaultdict
from pathlib import Path
from typing import Mapping, Sequence
import random

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

def build_children_index(cards_by_id: Mapping[str, Card], cards_by_run_id: Mapping[str, Sequence[Card]], draft_pairs: bool = False) -> dict[str, list[str]]:
    """Return visible child Card IDs for every visible parent."""
    children_by_parent_id: dict[str, list[str]] = defaultdict(list)
    for card in cards_by_id.values():
        if (card.label is None or 
            card.obs.error is not None or 
            card.lineage.parent_id is None):
            continue 
        parent_id = card.lineage.parent_id
        parent_card = cards_by_id.get(parent_id)
        # Skip the debug node between the parent and the child, because they are common
        # and decrease the amount of children that are visible to the decision pair builder.
        while parent_card.obs.error:
            parent_id = parent_card.lineage.parent_id
            parent_card = cards_by_id.get(parent_id)
        # If the parent is root node, it will be processed in draft pairs logic and skipped in improve pair.
        if not draft_pairs and parent_card.label is None:
            continue
        if parent_id and parent_id in cards_by_id:
            children_by_parent_id[parent_id].append(card.id)

    # Merge the root nodes from one experiment if draft pairs is true
    if draft_pairs and len(cards_by_run_id) > 1:
        # Assume you are applying this on one experiment
        root_nodes_id = []
        for run_id, run_cards in cards_by_run_id.items():
            root_nodes_id.append(run_cards[0].id)
        merged_root_node_id = root_nodes_id[0]
        for root_node_id in root_nodes_id[1:]:
            children_by_parent_id[merged_root_node_id].extend(children_by_parent_id[root_node_id])
            del children_by_parent_id[root_node_id]
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
    """Compute current value (0) or full future value (non-zero budget)."""
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
    budget: int,
    draft_pairs: bool = False,
    cap: int = 9999,
) -> tuple[list[dict], dict[str, int]]:
    """Build all unequal sibling pairs for each requested lookahead budget."""
    cards_by_id, _ = index_cards(cards_by_run_id)
    children_by_parent_id = build_children_index(cards_by_id, cards_by_run_id, draft_pairs=draft_pairs)
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
        if draft_pairs and cards_by_id[parent_id].lineage.parent_id is not None:
            continue
        sibling_ids = sorted(
            children_by_parent_id[parent_id],
            key=lambda card_id: expansion_order(cards_by_id[card_id]),
        )
        if len(sibling_ids) < 2:
            continue

        task_name = cards_by_id[sibling_ids[0]].task.name
        decision_set_counts[task_name] += 1
        higher_is_better = higher_is_better_by_task[task_name]
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

    if len(records) > cap:
        print(
            f"[decision_pairs] WARNING: {len(records)} pairs exceeds cap {cap}, "
            "randomly sampling pairs to reduce the size, but the following summary statistics is for the whole dataset."
        )
        records = random.sample(records, cap)

    summary = {
        "pairs": len(records),
        "decision_sets": sum(decision_set_counts.values()),
        "tasks_with_decision_sets": len(decision_set_counts),
    }
    summary[f"pairs_at_budget_{budget}"] = sum(
        count
        for (pair_budget, _), count in pair_counts.items()
        if pair_budget == budget
    )
    return records, summary

def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("out", type=Path, help="raw decision-pair JSONL")
    parser.add_argument("cards", type=Path, help="run-grouped Card JSON")
    parser.add_argument("--cap", type=int, default=9999, help="Maximum number of pairs to generate")
    parser.add_argument("--seed", type=int, default=7, help="Random seed for pair sampling")
    parser.add_argument(
        "--budget",
        type=int,
        default=0,
        help="Number of step to lookahead for best descendant value (0=disabled)",
    )
    parser.add_argument(
        "--draft_pairs",
        action="store_true",
        help="Build the decision pair using draft node",
    )
    return parser.parse_args()


def main() -> None:
    arguments = parse_args()
    cards_by_run_id = load_cards(str(arguments.cards))
    if arguments.draft_pairs:
        print(
            "[decision_pairs] Using draft node to build decision pairs,"
            "which will merge multiple draft nodes across one experiment into one parent node.\n"
            "[CRITICAL] This will assume you cards are prepared based on one experiment instead of global cards. "
        )
    else:
        print(
            "[decision_pairs] Using improve node to build decision pairs,"
            "which will ignore draft node and only use children belong to one parent to build pairs."
        )

    random.seed(arguments.seed)
    records, summary = build_decision_pairs(cards_by_run_id, arguments.budget, arguments.draft_pairs, arguments.cap)

    arguments.out.parent.mkdir(parents=True, exist_ok=True)
    with arguments.out.open("w", encoding="utf-8") as output_file:
        for record in records:
            output_file.write(json.dumps(record, ensure_ascii=False) + "\n")

    print(f"[decision_pairs] {summary['pairs']} pairs -> {arguments.out}")
    print(f"  K={arguments.budget}: {summary[f'pairs_at_budget_{arguments.budget}']}")
    print(
        f"  decision sets={summary['decision_sets']} "
        f"tasks={summary['tasks_with_decision_sets']}"
    )


if __name__ == "__main__":
    main()
