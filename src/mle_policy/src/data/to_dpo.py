"""Stage 4b: preference pairs from the grouped dataset.

One row per (chosen, rejected) pair inside a group.  ``chosen`` is the member
that started the best debug process; ``rejected`` is any member whose process
ended worse -- including members that never ended in a runnable solution, which
is how "prefer code that works" enters the data.

The ranking signal is the **episode** reward: the score of the runnable solution
the member's debug process ended in.  Members whose process never ended in a
runnable solution are ranked last.

``chosen`` is *not* required to have run on its own: at a ``draft`` decision
point every candidate is usually broken, and the interesting comparison is
which broken draft was recoverable.  Pass ``--require-node-result`` for the
conservative variant that only pairs solutions which ran by themselves.
"""

from __future__ import annotations

import argparse
from pathlib import Path
from typing import Any

from . import groupdata
from .journal import stable_id
from .selection import default_operators, eligible_members, ranked_members, training_prompt


def _reward(member: dict[str, Any]) -> float | None:
    return member.get("episode_reward")


def to_dpo(
    dataset_dir: Path,
    output_dir: Path,
    operators: set[str] | None = None,
    max_pairs_per_group: int = 8,
    require_node_result: bool = False,
    verbose: bool = True,
) -> dict[str, Any]:
    """Write ``dpo.jsonl``."""
    dataset_dir = Path(dataset_dir).resolve()
    output_dir = Path(output_dir).resolve()
    output_dir.mkdir(parents=True, exist_ok=True)
    operators = default_operators() if operators is None else operators

    splits = groupdata.read_splits(dataset_dir)
    normalize_packages = bool(groupdata.read_manifest(dataset_dir).get("normalize_packages", True))
    plans: dict[str, dict[str, Any]] = {}
    for group in groupdata.read_groups(dataset_dir):
        members = eligible_members(group, operators)
        resolvable = [
            member for member in members if member["episode_resolved"] and member.get("episode_reward") is not None
        ]
        if require_node_result:
            resolvable = [member for member in resolvable if member["node_has_result"]]
        if not resolvable:
            continue
        chosen = ranked_members(resolvable)[0]
        chosen_reward = _reward(chosen)
        rejected = [
            member
            for member in members
            if member["sample_id"] != chosen["sample_id"]
            and (_reward(member) is None or _reward(member) < chosen_reward)
        ]
        if not rejected:
            continue
        # Worst first: the largest reward gaps carry the clearest signal.
        rejected.sort(key=lambda member: (_reward(member) is not None, _reward(member) or 0.0))
        plans[group["group_id"]] = {
            "task": group["task"],
            "split": splits.get(group["group_id"], "train") if splits else "train",
            "chosen": chosen["sample_id"],
            "rejected": [member["sample_id"] for member in rejected[:max_pairs_per_group]],
        }

    members_needed = {
        group_id: {plan["chosen"], *plan["rejected"]} for group_id, plan in plans.items()
    }
    buffered: dict[str, dict[str, Any]] = {}
    pairs = 0
    failed_rejected = 0
    with (output_dir / "dpo.jsonl").open("w", encoding="utf-8") as handle:
        for sample in groupdata.iter_samples(dataset_dir):
            group_id = sample["group_id"]
            needed = members_needed.get(group_id)
            if needed is None or sample["sample_id"] not in needed:
                continue
            buffer = buffered.setdefault(group_id, {})
            buffer[sample["sample_id"]] = sample
            if len(buffer) < len(needed):
                continue

            plan = plans[group_id]
            chosen = buffer[plan["chosen"]]
            for rejected_id in plan["rejected"]:
                rejected = buffer[rejected_id]
                groupdata.write_jsonl(
                    handle,
                    {
                        "pair_id": stable_id(chosen["group_id"], chosen["sample_id"], rejected["sample_id"]),
                        "group_id": chosen["group_id"],
                        "task": chosen["task"],
                        "split": plan["split"],
                        "prompt": training_prompt(chosen, normalize_packages),
                        "chosen": {
                            "sample_id": chosen["sample_id"],
                            "completion": chosen["completion"],
                            "reward": chosen["episode_reward"],
                            "node_reward": chosen["node_reward"],
                            "failed": not chosen["node_has_result"],
                        },
                        "rejected": {
                            "sample_id": rejected["sample_id"],
                            "completion": rejected["completion"],
                            "reward": rejected["episode_reward"],
                            "node_reward": rejected["node_reward"],
                            "failed": not rejected["node_has_result"],
                        },
                    },
                )
                pairs += 1
                failed_rejected += not rejected["node_has_result"]
            del buffered[group_id]
            del members_needed[group_id]

    summary = {
        "view": "dpo",
        "dataset": str(dataset_dir),
        "pairs": pairs,
        "pairs_with_failed_rejected": failed_rejected,
    }
    if verbose:
        print(summary)
    return summary


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--dataset", required=True, help="Aggregated dataset directory.")
    parser.add_argument("--output-dir", required=True)
    parser.add_argument("--operators", default=None, help="Comma separated; default draft,debug,improve,crossover.")
    parser.add_argument("--max-pairs-per-group", type=int, default=8)
    parser.add_argument(
        "--require-node-result",
        action="store_true",
        help="Only pair solutions that ran by themselves; default pairs by episode return.",
    )
    args = parser.parse_args()
    operators = {name.strip() for name in args.operators.split(",") if name.strip()} if args.operators else None
    to_dpo(
        Path(args.dataset),
        Path(args.output_dir),
        operators=operators,
        max_pairs_per_group=args.max_pairs_per_group,
        require_node_result=args.require_node_result,
    )


if __name__ == "__main__":
    main()
