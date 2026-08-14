"""Build preference pairs from the best grade reachable below each Card.

For a Card ``c``, its value is the best external grade among ``c`` and its
graded descendants.  A pair therefore asks "which node eventually leads to a
better result?", rather than "which node has the better grade right now?".

The input is the run-grouped JSON file produced by ``build_cards``.  Unlabelled
Cards remain part of the tree and can connect a Card to a labelled descendant,
but they cannot contribute a grade themselves.

This command writes raw pairs with ``intask_split="unassigned"``.  Apply the
shared frozen physical-run split afterwards with ``build_bt_pairs.build_runsplit``.

Usage:
    python -m src.preprocess.build_bt_pairs.build_subtree_pairs \
        OUT.jsonl CARDS.json
"""
from __future__ import annotations

import argparse
import itertools
import json
import math
import random
from collections import defaultdict
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, Mapping, Sequence

from ..download_and_resolve.cards import Card, load_cards


@dataclass(frozen=True)
class Descendant:
    """A descendant and the cost of reaching it from an ancestor."""

    card_id: str
    step_distance: int
    cumulative_runtime_s: float


@dataclass(frozen=True)
class NodeValue:
    """The quantities needed to compare one Card with another."""

    card_id: str
    task_name: str
    current_grade: float
    best_subtree_grade: float
    reachable_descendant_count: int
    steps_to_best: int


def flatten_runs(
    cards_by_run_id: Mapping[str, Sequence[Card]],
) -> tuple[dict[str, Card], dict[str, str]]:
    """Index Cards by ID while retaining their physical run membership."""
    cards_by_id: dict[str, Card] = {}
    run_id_by_card_id: dict[str, str] = {}

    for run_id, run_cards in cards_by_run_id.items():
        for card in run_cards:
            if card.id in cards_by_id:
                previous_run = run_id_by_card_id[card.id]
                raise ValueError(
                    f"Duplicate Card ID {card.id!r} in runs "
                    f"{previous_run!r} and {run_id!r}"
                )
            cards_by_id[card.id] = card
            run_id_by_card_id[card.id] = run_id

    # A parent missing from the corpus simply starts a new visible tree.  A
    # parent in another run, however, means the physical run boundary is wrong.
    for card in cards_by_id.values():
        parent_id = card.lineage.parent_id
        if parent_id in run_id_by_card_id:
            if run_id_by_card_id[parent_id] != run_id_by_card_id[card.id]:
                raise ValueError(
                    f"Card {card.id!r} and parent {parent_id!r} "
                    "belong to different runs"
                )
            if cards_by_id[parent_id].task.name != card.task.name:
                raise ValueError(
                    f"Card {card.id!r} and parent {parent_id!r} "
                    "belong to different tasks"
                )

    return cards_by_id, run_id_by_card_id


def build_children_index(cards_by_id: Mapping[str, Card]) -> dict[str, list[str]]:
    """Return ``parent Card ID -> child Card IDs`` for visible Cards."""
    children_by_parent_id: dict[str, list[str]] = defaultdict(list)
    for card in cards_by_id.values():
        parent_id = card.lineage.parent_id
        if parent_id and parent_id in cards_by_id:
            children_by_parent_id[parent_id].append(card.id)
    return dict(children_by_parent_id)


def runtime_seconds(card: Card) -> float:
    """Treat a missing runtime as zero, matching the old data pipeline."""
    return float(card.obs.runtime_s) if card.obs.runtime_s is not None else 0.0


def find_descendants(
    ancestor_id: str,
    cards_by_id: Mapping[str, Card],
    children_by_parent_id: Mapping[str, Sequence[str]],
) -> list[Descendant]:
    """Traverse all visible descendants of ``ancestor_id`` without recursion."""
    descendants: list[Descendant] = []
    pending = [
        Descendant(child_id, 1, runtime_seconds(cards_by_id[child_id]))
        for child_id in children_by_parent_id.get(ancestor_id, [])
    ]
    # Mark the ancestor up front so malformed cyclic lineage cannot make it its
    # own descendant.
    visited = {ancestor_id}

    while pending:
        descendant = pending.pop()
        if descendant.card_id in visited:
            continue
        visited.add(descendant.card_id)
        descendants.append(descendant)

        for child_id in children_by_parent_id.get(descendant.card_id, []):
            pending.append(
                Descendant(
                    card_id=child_id,
                    step_distance=descendant.step_distance + 1,
                    cumulative_runtime_s=(
                        descendant.cumulative_runtime_s
                        + runtime_seconds(cards_by_id[child_id])
                    ),
                )
            )

    return descendants


def is_within_budget(
    descendant: Descendant,
    budget_steps: int,
    budget_seconds: float,
) -> bool:
    """Return whether a descendant is reachable under both optional budgets."""
    within_step_budget = budget_steps == 0 or descendant.step_distance <= budget_steps
    within_time_budget = (
        budget_seconds == 0
        or descendant.cumulative_runtime_s <= budget_seconds
    )
    return within_step_budget and within_time_budget


def graded_score(card: Card) -> float | None:
    """Return a finite external grade, treating NaN/Inf as missing labels."""
    if card.label is None or card.label.graded is None:
        return None
    score = float(card.label.graded)
    return score if math.isfinite(score) else None


def compute_node_values(
    cards_by_id: Mapping[str, Card],
    children_by_parent_id: Mapping[str, Sequence[str]],
    budget_steps: int = 0,
    budget_seconds: float = 0.0,
) -> dict[str, NodeValue]:
    """Compute the best reachable grade for every eligible Card.

    An eligible Card needs its own grade and at least one graded descendant
    within budget.  Requiring a descendant excludes leaves, whose "future
    value" would otherwise be identical to their current grade by definition.
    """
    values_by_card_id: dict[str, NodeValue] = {}

    for card_id, card in cards_by_id.items():
        current_grade = graded_score(card)
        if current_grade is None:
            continue

        reachable_descendants = [
            descendant
            for descendant in find_descendants(
                card_id, cards_by_id, children_by_parent_id
            )
            if is_within_budget(descendant, budget_steps, budget_seconds)
        ]
        reachable_graded_descendants = []
        for descendant in reachable_descendants:
            descendant_grade = graded_score(cards_by_id[descendant.card_id])
            if descendant_grade is not None:
                reachable_graded_descendants.append((descendant, descendant_grade))

        if not reachable_graded_descendants:
            continue

        choose_best = min if not card.task.higher_is_better else max
        best_subtree_grade = choose_best(
            [current_grade]
            + [grade for _, grade in reachable_graded_descendants]
        )

        # The node itself is zero steps away.  Only search descendants when a
        # strict improvement over the node's own grade supplies the best value.
        if current_grade == best_subtree_grade:
            steps_to_best = 0
        else:
            steps_to_best = min(
                descendant.step_distance
                for descendant, grade in reachable_graded_descendants
                if grade == best_subtree_grade
            )

        values_by_card_id[card_id] = NodeValue(
            card_id=card_id,
            task_name=card.task.name,
            current_grade=current_grade,
            best_subtree_grade=best_subtree_grade,
            reachable_descendant_count=len(reachable_descendants),
            steps_to_best=steps_to_best,
        )

    return values_by_card_id


def validate_task_directions(
    node_values: Iterable[NodeValue], cards_by_id: Mapping[str, Card]
) -> dict[str, bool]:
    """Return one metric direction per task, rejecting inconsistent metadata."""
    higher_is_better_by_task: dict[str, bool] = {}
    for node_value in node_values:
        direction = cards_by_id[node_value.card_id].task.higher_is_better
        previous = higher_is_better_by_task.setdefault(node_value.task_name, direction)
        if previous != direction:
            raise ValueError(
                f"Inconsistent higher_is_better values for task {node_value.task_name!r}"
            )
    return higher_is_better_by_task


def current_quality_agreement(
    better: NodeValue,
    worse: NodeValue,
    higher_is_better: bool,
) -> bool | None:
    """Compare the current-grade ordering with the future-value ordering."""
    if better.current_grade == worse.current_grade:
        return None
    if higher_is_better:
        return better.current_grade > worse.current_grade
    return better.current_grade < worse.current_grade


def make_pair_record(
    left: NodeValue,
    right: NodeValue,
    higher_is_better: bool,
    budget_steps: int,
    budget_seconds: float,
) -> dict:
    """Orient two unequal node values and serialize their training metadata."""
    left_is_better = (
        left.best_subtree_grade > right.best_subtree_grade
        if higher_is_better
        else left.best_subtree_grade < right.best_subtree_grade
    )
    better, worse = (left, right) if left_is_better else (right, left)

    return {
        "task": better.task_name,
        "better": better.card_id,
        "worse": worse.card_id,
        "agrees_with_quality": current_quality_agreement(
            better, worse, higher_is_better
        ),
        "gap_raw": round(
            abs(better.best_subtree_grade - worse.best_subtree_grade), 6
        ),
        # Both two-item fields follow [better, worse] order.
        "subtree_sizes": [
            better.reachable_descendant_count,
            worse.reachable_descendant_count,
        ],
        "steps_to_best": [better.steps_to_best, worse.steps_to_best],
        "budget_steps": budget_steps,
        "budget_secs": budget_seconds,
        "intask_split": "unassigned",
        "loto_fold": better.task_name,
        "clears_tau": None,
        "src": "value",
    }


def build_value_pairs(
    cards_by_run_id: Mapping[str, Sequence[Card]],
    cap_per_task: int = 20_000,
    seed: int = 7,
    budget_steps: int = 0,
    budget_seconds: float = 0.0,
) -> tuple[list[dict], dict[str, dict[str, int]]]:
    """Build capped, same-task raw value pairs and summary counts."""
    cards_by_id, _ = flatten_runs(cards_by_run_id)
    children_by_parent_id = build_children_index(cards_by_id)
    node_values_by_id = compute_node_values(
        cards_by_id,
        children_by_parent_id,
        budget_steps=budget_steps,
        budget_seconds=budget_seconds,
    )
    directions = validate_task_directions(node_values_by_id.values(), cards_by_id)

    node_values_by_task: dict[str, list[NodeValue]] = defaultdict(list)
    for node_value in node_values_by_id.values():
        node_values_by_task[node_value.task_name].append(node_value)

    random_generator = random.Random(seed)
    records: list[dict] = []
    summaries: dict[str, dict[str, int]] = {}

    for task_name in sorted(node_values_by_task):
        task_node_values = node_values_by_task[task_name]
        candidate_pairs = [
            pair
            for pair in itertools.combinations(task_node_values, 2)
            if pair[0].best_subtree_grade != pair[1].best_subtree_grade
        ]
        random_generator.shuffle(candidate_pairs)
        candidate_pairs = candidate_pairs[:cap_per_task]

        for left, right in candidate_pairs:
            records.append(
                make_pair_record(
                    left,
                    right,
                    directions[task_name],
                    budget_steps,
                    budget_seconds,
                )
            )

        summaries[task_name] = {
            "eligible_nodes": len(task_node_values),
            "candidate_pairs": len(candidate_pairs),
            "written_pairs": len(candidate_pairs),
        }

    return records, summaries


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("out", type=Path, help="output preference-pair JSONL")
    parser.add_argument("cards", type=Path, help="run-grouped Card JSON")
    parser.add_argument(
        "--budget-steps",
        type=int,
        default=0,
        help="maximum parent-child edges to a descendant; 0 means unlimited",
    )
    parser.add_argument(
        "--budget-secs",
        type=float,
        default=0.0,
        help="maximum cumulative descendant runtime; 0 means unlimited",
    )
    parser.add_argument(
        "--cap",
        type=int,
        default=20_000,
        help="maximum sampled candidate pairs per task before split filtering",
    )
    parser.add_argument("--seed", type=int, default=7)
    arguments = parser.parse_args()
    if arguments.budget_steps < 0:
        parser.error("--budget-steps must be non-negative")
    if arguments.budget_secs < 0:
        parser.error("--budget-secs must be non-negative")
    if arguments.cap < 1:
        parser.error("--cap must be positive")
    return arguments


def main() -> None:
    arguments = parse_args()
    cards_by_run_id = load_cards(str(arguments.cards))
    records, summaries = build_value_pairs(
        cards_by_run_id,
        cap_per_task=arguments.cap,
        seed=arguments.seed,
        budget_steps=arguments.budget_steps,
        budget_seconds=arguments.budget_secs,
    )

    arguments.out.parent.mkdir(parents=True, exist_ok=True)
    with arguments.out.open("w", encoding="utf-8") as output_file:
        for record in records:
            output_file.write(json.dumps(record, ensure_ascii=False) + "\n")

    for task_name, summary in summaries.items():
        print(
            f"{task_name[:38]:38s} "
            f"nodes={summary['eligible_nodes']:5d} "
            f"candidates={summary['candidate_pairs']:5d} "
            f"written={summary['written_pairs']:5d}"
        )
    print(f"[value_pairs] {len(records)} pairs -> {arguments.out}")


if __name__ == "__main__":
    main()
