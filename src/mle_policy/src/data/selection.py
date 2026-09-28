"""Turn groups into the choices SFT / DPO / GRPO need.

The reward is the *episode* reward (see ``journal``): all steps of one debug
process share the score of the runnable solution it ended in.  A member with
``episode_resolved == False`` never produced a runnable solution and counts as
failed, ranked below every resolved member.
"""

from __future__ import annotations

from typing import Any

from .journal import CODE_OPERATORS, canonical_prompt


def training_prompt(sample: dict[str, Any], normalize_packages: bool) -> list[dict[str, Any]]:
    """The prompt a training row should carry.

    Samples keep the prompt exactly as recorded, package order included; what a
    group's members all answer is the *canonical* prompt, so that is what the
    converters hand to the trainer.
    """
    return canonical_prompt(sample["prompt"], normalize_packages)


def eligible_members(group: dict[str, Any], operators: set[str]) -> list[dict[str, Any]]:
    """Members whose operator is part of the training target."""
    return [member for member in group["members"] if member["operator"] in operators]


def rank_key(member: dict[str, Any]) -> tuple[int, float, str]:
    """Sort key: resolved first, then by reward, then a tie-break for stability."""
    reward = member.get("episode_reward")
    return (
        1 if member["episode_resolved"] else 0,
        reward if reward is not None else float("-inf"),
        member["sample_id"],
    )


def ranked_members(members: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Best first."""
    return sorted(members, key=rank_key, reverse=True)


def default_operators() -> set[str]:
    return set(CODE_OPERATORS)
