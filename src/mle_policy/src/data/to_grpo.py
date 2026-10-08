"""Stage 4c: group-relative training rows, one per LLM call, advantage included.

The training data is the *same* material SFT uses -- every operation (LLM call)
of every episode, as a ``[prompt, completion]`` pair.  What GRPO adds is the
advantage, and the advantage is what makes this file different from ``sft.jsonl``:

* one **group** is the set of episodes that answered the same root prompt under
  one environment (the same ``group_id`` the pipeline already builds), so GRPO's
  "several attempts at one question" is exactly this group;
* every episode in the group has one number, its ``episode_reward`` (the
  normalised score of the runnable solution its debug chain ended in, see
  ``overview.md``);
* the group-relative advantage ``A = (reward - mean) / std`` is computed **here**,
  once, over that group.  ``--no-norm-adv-by-std`` drops the ``/ std`` (Dr.GRPO
  style, so the size of the reward gap keeps mattering);
* every operation of an episode gets one row carrying **its episode's advantage**.
  The whole debug chain is one decision chain, so all of its steps share the
  return; they just become independent training samples, exactly like the SFT
  view splits them into independent rows.

Computing the advantage here instead of inside the trainer also removes a
constraint: the advantage no longer depends on what else happens to land in the
same training batch, so rows can be shuffled and batched freely.

An episode that never produced a runnable solution has no score.  It still is a
member of its group (it answered the same prompt), so it gets
``min(runnable rewards of its group) - 1 gold span`` by default: that keeps it
last inside its group whatever the competition's reward scale is
(``--unresolved-reward`` pins a value instead).

Groups that carry no contrast at all are skipped: fewer than two members, no
runnable member (then every reward is the same floor), or identical rewards
(``std == 0``, advantage 0 for everyone).  They would contribute nothing.

Rows are the SFT prompt shape: ``selection.training_messages`` (sorted package
list, no search memory on proposals, operator system message restored), and the
episode's root operation uses the group's earliest root prompt, again like SFT.

Output is ``grpo.jsonl`` only.  The tokenised parquet is built later, by
``src/verl/my_recipes/mle_policy/src/data/build_grpo_parquet.py``.
"""

from __future__ import annotations

import argparse
import math
import statistics
from pathlib import Path
from typing import Any

from . import groupdata
from .selection import default_operators, eligible_members, training_messages

# Reward given to an episode that never produced a runnable solution, by default
# one gold span below the worst runnable response of the same group.
UNRESOLVED_REWARD_GAP = 1.0
# Below this the group has no contrast and every advantage would be 0.
MIN_REWARD_SPREAD = 1e-6


def group_advantages(rewards: list[float], norm_by_std: bool) -> list[float]:
    """GRPO's outcome advantage: ``(r - mean) / std`` over one group.

    The standard deviation uses ``n - 1``, the same thing ``torch.std`` computes
    in Verl's GRPO estimator.
    """
    mean = statistics.fmean(rewards)
    if not norm_by_std:
        return [reward - mean for reward in rewards]
    variance = sum((reward - mean) ** 2 for reward in rewards) / (len(rewards) - 1)
    std = math.sqrt(variance)
    return [(reward - mean) / std for reward in rewards]


def to_grpo(
    dataset_dir: Path,
    output_dir: Path,
    operators: set[str] | None = None,
unresolved_reward: float | None = None,
norm_by_std: bool = True,
strip_memory: bool = True,
reward_clip: tuple[float, float] | None = None,
verbose: bool = True,
) -> dict[str, Any]:
    """Write ``grpo.jsonl``: one advantage-carrying row per operation."""
    dataset_dir = Path(dataset_dir).resolve()
    output_dir = Path(output_dir).resolve()
    output_dir.mkdir(parents=True, exist_ok=True)
    operators = default_operators() if operators is None else operators
    if reward_clip is not None and reward_clip[0] >= reward_clip[1]:
        raise ValueError(f"reward_clip must be an increasing (low, high) pair, got {reward_clip}")

    splits = groupdata.read_splits(dataset_dir)
    normalize_packages = bool(groupdata.read_manifest(dataset_dir).get("normalize_packages", True))
    groups = groupdata.read_groups(dataset_dir)

    # Pass 1: decide which groups can carry an advantage at all, and compute it.
    plan: dict[str, dict[str, Any]] = {}
    skipped = {"too_few_members": 0, "nothing_runnable": 0, "no_contrast": 0}
    clipped_episodes = 0
    for group in groups:
        members = eligible_members(group, operators)
        if len(members) < 2:
            skipped["too_few_members"] += 1
            continue
        scored = {
            member["sample_id"]: member["episode_reward"]
            for member in members
            if member["episode_reward"] is not None
        }
        if not scored:
            skipped["nothing_runnable"] += 1
            continue
        if reward_clip is not None:
            low, high = reward_clip
            for sample_id, reward in scored.items():
                bounded = min(max(reward, low), high)
                if bounded != reward:
                    clipped_episodes += 1
                scored[sample_id] = bounded
        floor = unresolved_reward if unresolved_reward is not None else min(scored.values()) - UNRESOLVED_REWARD_GAP
        group_rewards = [scored.get(member["sample_id"], floor) for member in members]
        if max(group_rewards) - min(group_rewards) < MIN_REWARD_SPREAD:
            skipped["no_contrast"] += 1
            continue
        plan[group["group_id"]] = {
            "members": members,
            "rewards": group_rewards,
            "advantages": group_advantages(group_rewards, norm_by_std),
        }

    # Pass 2: read the calls of the surviving episodes.  The rows need every
    # operation of every member, so this keeps all of samples.jsonl for those
    # episodes (the SFT view materialises all of it too).
    wanted_episodes = {member["episode_id"] for entry in plan.values() for member in entry["members"]}
    samples_by_episode: dict[str, list[dict[str, Any]]] = {}
    for sample in groupdata.iter_samples(dataset_dir):
        if sample["episode_id"] in wanted_episodes:
            samples_by_episode.setdefault(sample["episode_id"], []).append(sample)

    # Pass 3: write one row per operation, each carrying its episode's advantage.
    rows = 0
    groups_written = 0
    advantages_seen: list[float] = []
    with (output_dir / "grpo.jsonl").open("w", encoding="utf-8") as handle:
        for group in groups:
            entry = plan.get(group["group_id"])
            if entry is None:
                continue
            members = entry["members"]
            earliest = min(members, key=lambda member: (member["node_step"], member["sample_id"]))
            init_sample = None
            for sample in samples_by_episode[earliest["episode_id"]]:
                if sample["sample_id"] == earliest["root_sample_id"]:
                    init_sample = sample
            if init_sample is None:
                raise ValueError(f"group {group['group_id']} has no sample for its earliest root")
            init_prompt = training_messages(init_sample, normalize_packages, strip_memory=strip_memory)

            split = splits.get(group["group_id"], "train") if splits else "train"
            for member, reward, advantage in zip(members, entry["rewards"], entry["advantages"], strict=True):
                for sample in samples_by_episode[member["episode_id"]]:
                    if sample["operator"] not in operators:
                        continue
                    if sample["sample_id"] == member["root_sample_id"]:
                        prompt = init_prompt
                    else:
                        prompt = training_messages(sample, normalize_packages, strip_memory=strip_memory)
                    groupdata.write_jsonl(
                        handle,
                        {
                            "sample_id": sample["sample_id"],
                            "group_id": group["group_id"],
                            "episode_id": member["episode_id"],
                            "task": group["task"],
                            "batch": group["batch"],
                            "split": split,
                            "operator": sample["operator"],
                            "prompt": prompt,
                            "completion": sample["completion"],
                            "reward": reward,
                            "advantage": advantage,
                            "episode_resolved": bool(member["episode_resolved"]),
                            "node_has_result": bool(sample["node_has_result"]),
                        },
                    )
                    rows += 1
                    advantages_seen.append(advantage)
            groups_written += 1

    summary = {
        "view": "grpo",
        "dataset": str(dataset_dir),
        "groups": groups_written,
        "rows": rows,
        "skipped_groups": skipped,
        "norm_by_std": norm_by_std,
        "reward_clip": list(reward_clip) if reward_clip else None,
        "clipped_episodes": clipped_episodes,
        "advantage": {
            "min": min(advantages_seen) if advantages_seen else None,
            "max": max(advantages_seen) if advantages_seen else None,
        },
    }
    if verbose:
        print(summary)
    return summary


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--dataset", required=True, help="Aggregated dataset directory.")
    parser.add_argument("--output-dir", required=True)
    parser.add_argument("--operators", default=None, help="Comma separated; default draft,debug,improve,crossover,analysis.")
    parser.add_argument(
        "--unresolved-reward",
        type=float,
        default=None,
        help=(
            "Fixed reward for an episode that never produced a runnable solution. "
            "Default: one gold span below the worst runnable response of its group."
        ),
    )
    parser.add_argument(
        "--no-norm-adv-by-std",
        dest="norm_by_std",
        action="store_false",
        help="Do not divide by the group std, so the size of the reward gap keeps mattering.",
    )
    parser.add_argument(
        "--reward-clip",
        type=float,
        nargs=2,
        default=None,
        metavar=("LOW", "HIGH"),
        help=(
            "Bound the score reward before the advantage is computed.  The normalised reward "
            "explodes on competitions whose gold threshold sits next to the median (see the doc); "
            "e.g. --reward-clip -3 3."
        ),
    )
    parser.add_argument(
        "--keep-search-memory",
        dest="strip_memory",
        action="store_false",
        help="Keep the 'PREVIOUSLY EXPLORED ...' section of proposal prompts (SFT strips it).",
    )
    args = parser.parse_args()
    operators = {name.strip() for name in args.operators.split(",") if name.strip()} if args.operators else None
    to_grpo(
        Path(args.dataset),
        Path(args.output_dir),
        operators=operators,
        unresolved_reward=args.unresolved_reward,
        norm_by_std=args.norm_by_std,
        strip_memory=args.strip_memory,
        reward_clip=tuple(args.reward_clip) if args.reward_clip else None,
    )


if __name__ == "__main__":
    main()
