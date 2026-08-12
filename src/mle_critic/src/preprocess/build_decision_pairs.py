"""Build decision-aligned sibling pairs from a card corpus.

A decision set is the graded children of one recorded parent.  For budget K,
``value_K(child)`` is the best external grade among the child and its first K
visible descendants in expansion order.  Every unequal sibling combination is
written as one oriented preference pair.

This command deliberately does not assign a data split.  The old implementation
split lineage fragments here, but one physical AIRA run can contain several such
fragments, causing train/test leakage and corpus-size-dependent pair loss.  Use
``build_runsplit`` downstream to assign the frozen physical-run split.

Usage:
  python -m src.mle_critic.src.preprocess.build_decision_pairs \
    OUT CARDS --orientation ORIENTATION [--ks 0,1,2]
"""
from __future__ import annotations

import argparse
import collections
import itertools
import json
from pathlib import Path


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("out", type=Path)
    parser.add_argument("cards", type=Path)
    parser.add_argument("--ks", default="0,1,2")
    parser.add_argument(
        "--seed",
        type=int,
        default=7,
        help="deprecated compatibility option; splitting now happens downstream",
    )
    parser.add_argument(
        "--orientation",
        type=Path,
        default=Path(__file__).resolve().parents[4]
        / "data"
        / "mle_critic"
        / "task_orientation.json",
    )
    args = parser.parse_args()
    del args.seed
    budgets = [int(value) for value in args.ks.split(",")]

    cards = {}
    with args.cards.open(encoding="utf-8") as stream:
        for line in stream:
            card = json.loads(line)
            cards[card["id"]] = card
    orientation = json.loads(args.orientation.read_text(encoding="utf-8"))

    children = collections.defaultdict(list)
    for card_id, card in cards.items():
        parent_id = card["lineage"].get("parent_id")
        if parent_id:
            children[parent_id].append(card_id)

    def descendants_in_order(card_id: str) -> list[str]:
        descendants = []
        stack = list(children.get(card_id, []))
        seen = set()
        while stack:
            descendant_id = stack.pop()
            if descendant_id in seen or descendant_id not in cards:
                continue
            seen.add(descendant_id)
            descendants.append(descendant_id)
            stack.extend(children.get(descendant_id, []))
        return sorted(
            descendants,
            key=lambda descendant_id: (
                cards[descendant_id]["lineage"].get("step") or 0,
                descendant_id,
            ),
        )

    descendants = {
        card_id: descendants_in_order(card_id) for card_id in cards
    }

    def lookahead_value(card_id: str, budget: int):
        if budget == 0:
            return cards[card_id]["label"]["graded"]
        if len(descendants[card_id]) < budget:
            return None
        task = cards[card_id]["task"]["name"]
        choose = min if orientation[task] else max
        return choose(
            [cards[card_id]["label"]["graded"]]
            + [
                cards[descendant_id]["label"]["graded"]
                for descendant_id in descendants[card_id][:budget]
            ]
        )

    args.out.parent.mkdir(parents=True, exist_ok=True)
    counts = collections.Counter()
    decision_sets = collections.Counter()
    with args.out.open("w", encoding="utf-8") as output:
        for parent_id, sibling_ids in children.items():
            sibling_ids = [card_id for card_id in sibling_ids if card_id in cards]
            if len(sibling_ids) < 2:
                continue
            task = cards[sibling_ids[0]]["task"]["name"]
            if task not in orientation:
                continue
            if any(cards[card_id]["task"]["name"] != task for card_id in sibling_ids):
                raise ValueError(f"siblings under {parent_id} span multiple tasks")
            lower_is_better = orientation[task]
            decision_sets[task] += 1
            for budget in budgets:
                for left, right in itertools.combinations(sibling_ids, 2):
                    left_value = lookahead_value(left, budget)
                    right_value = lookahead_value(right, budget)
                    if (
                        left_value is None
                        or right_value is None
                        or left_value == right_value
                    ):
                        continue
                    left_wins = (
                        left_value < right_value
                        if lower_is_better
                        else left_value > right_value
                    )
                    better, worse = (left, right) if left_wins else (right, left)
                    record = {
                        "task": task,
                        "better": better,
                        "worse": worse,
                        "budget": budget,
                        "parent": parent_id,
                        "set_size": len(sibling_ids),
                        "gap_raw": round(abs(left_value - right_value), 6),
                        "intask_split": "unassigned",
                        "loto_fold": task,
                        "clears_tau": None,
                        "src": "decision",
                    }
                    output.write(json.dumps(record, ensure_ascii=False) + "\n")
                    counts[(budget, task)] += 1

    print(f"[decision_pairs] {sum(counts.values())} pairs -> {args.out}")
    for budget in budgets:
        print(
            f"  K={budget}: "
            f"{sum(count for (key, _), count in counts.items() if key == budget)}"
        )
    print(
        f"  decision sets: {sum(decision_sets.values())}; "
        f"tasks with sets: {len(decision_sets)}"
    )


if __name__ == "__main__":
    main()
