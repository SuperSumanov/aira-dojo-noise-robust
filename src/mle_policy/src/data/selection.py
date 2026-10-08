"""Turn groups into the choices SFT / DPO / GRPO need.

The reward is the *episode* reward (see ``journal``): all steps of one debug
process share the score of the runnable solution it ended in.  A member with
``episode_resolved == False`` never produced a runnable solution and counts as
failed, ranked below every resolved member.
"""

from __future__ import annotations

from typing import Any

from .journal import CODE_OPERATORS, canonical_prompt, strip_search_memory
from .operator_prompts import system_message

# Operators whose prompt carries the "PREVIOUSLY EXPLORED ..." search memory.
# ``debug`` / ``analysis`` prompts carry the code and the error instead and are
# never rewritten.
MEMORY_OPERATORS = ("draft", "improve", "crossover")


def training_prompt(sample: dict[str, Any], normalize_packages: bool) -> list[dict[str, Any]]:
    """The prompt a training row should carry.

    Samples keep the prompt exactly as recorded, package order included; what a
    group's members all answer is the *canonical* prompt, so that is what the
    converters hand to the trainer.
    """
    return canonical_prompt(sample["prompt"], normalize_packages)


def training_messages(
    sample: dict[str, Any],
    normalize_packages: bool,
    strip_memory: bool = True,
) -> list[dict[str, Any]]:
    """The prompt of one training row, as the ``[system, user]`` chat prefix.

    Three normalisations happen here, and SFT and GRPO must agree on all of
    them or the two views would train different questions:

    * the shuffled package list is sorted (``training_prompt``);
    * proposal prompts drop their "PREVIOUSLY EXPLORED ..." search memory, so
      the model learns the choice itself instead of reading what the rest of the
      search already tried (``debug`` / ``analysis`` keep theirs);
    * a run that only recorded one ``system`` turn -- an OpenAI-protocol client
      stored the whole rendered prompt there -- gets the operator's own system
      message back from its dojo config, and the recorded turn becomes ``user``.
    """
    prompt = training_prompt(sample, normalize_packages)
    if strip_memory and sample["operator"] in MEMORY_OPERATORS:
        prompt = [{"role": message["role"], "content": strip_search_memory(message["content"])} for message in prompt]
    if len(prompt) == 1 and prompt[0]["role"] == "system":
        prompt = [
            {"role": "system", "content": system_message(sample["operator"])},
            {"role": "user", "content": prompt[0]["content"]},
        ]
    return prompt


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
