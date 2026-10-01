"""Stage 4a: complete-episode SFT data from the grouped dataset.

Each group contributes every operation from its highest-reward episode that
contains a runnable operation.  The root operation uses the earliest root
prompt in the group; later operations keep their recorded prompts.

Proposal prompts (draft / improve / crossover) carry a "PREVIOUSLY EXPLORED ..."
section listing what the other candidates in the search already tried.  That
search memory is removed here: the training target is the choice itself, and the
model should learn the selection in its weights instead of reading the log of
previous attempts.  ``debug`` and ``analysis`` prompts are left alone -- they
carry the code and the error that the fix is about.

Rows whose run only recorded one ``system`` message (the OpenAI-protocol clients)
get the operator's system message back from its dojo config, so every row is a
``[system, user, assistant]`` conversation -- Qwen expects one, and a bare user
turn makes the chat template unhappy.

``operator`` (draft / debug / improve / crossover / analysis) is carried into
``sft.jsonl`` so the Verl converter can report how many rows of each operator
survive the length filter.
"""

from __future__ import annotations

import argparse
from pathlib import Path
from typing import Any

import pyarrow as pa

from . import groupdata
from .journal import strip_search_memory
from .operator_prompts import system_message
from .parquetwriter import MESSAGE_TYPE, SplitParquetWriter
from .selection import default_operators, eligible_members, ranked_members, training_prompt

SFT_SCHEMA = pa.schema([("messages", MESSAGE_TYPE)])

# Operators whose prompt carries the search memory.  debug/analysis keep theirs.
MEMORY_OPERATORS = ("draft", "improve", "crossover")


def _prompt_for(sample: dict[str, Any], normalize_packages: bool) -> list[dict[str, Any]]:
    """The prompt a training row carries: canonical packages, no search memory.

    A recorded single ``system`` turn is the rendered user message of an
    OpenAI-protocol run: it becomes the user turn and the operator's own system
    message is put back in front of it.
    """
    prompt = training_prompt(sample, normalize_packages)
    if sample["operator"] in MEMORY_OPERATORS:
        prompt = [
            {"role": message["role"], "content": strip_search_memory(message["content"])}
            for message in prompt
        ]
    if len(prompt) == 1 and prompt[0]["role"] == "system":
        prompt = [
            {"role": "system", "content": system_message(sample["operator"])},
            {"role": "user", "content": prompt[0]["content"]},
        ]
    return prompt


def to_sft(
    dataset_dir: Path,
    output_dir: Path,
    operators: set[str] | None = None,
    verbose: bool = True,
) -> dict[str, Any]:
    """Write ``sft.jsonl`` plus ``sft_{train,val}.parquet``."""
    dataset_dir = Path(dataset_dir).resolve()
    output_dir = Path(output_dir).resolve()
    output_dir.mkdir(parents=True, exist_ok=True)
    operators = default_operators() if operators is None else operators

    splits = groupdata.read_splits(dataset_dir)
    normalize_packages = bool(groupdata.read_manifest(dataset_dir).get("normalize_packages", True))
    samples_by_id = {sample["sample_id"]: sample for sample in groupdata.iter_samples(dataset_dir)}

    rows = 0
    writer = SplitParquetWriter(output_dir, "sft", SFT_SCHEMA)
    with (output_dir / "sft.jsonl").open("w", encoding="utf-8") as handle:
        for group in groupdata.read_groups(dataset_dir):
            all_episodes = eligible_members(group, operators)
            if not all_episodes:
                continue
            init_episode = min(all_episodes, key=lambda e: (e["node_step"], e["sample_id"]))
            init_sample = samples_by_id[init_episode["root_sample_id"]]
            init_prompt = _prompt_for(init_sample, normalize_packages)

            episodes = all_episodes
            runnable_by_episode = {
                episode["episode_id"]: [
                    samples_by_id[sample_id]
                    for sample_id in episode["sample_ids"]
                    if sample_id in samples_by_id
                    and samples_by_id[sample_id]["operator"] in operators
                    and samples_by_id[sample_id]["node_has_result"]
                ]
                for episode in episodes
            }
            episodes = [episode for episode in episodes if runnable_by_episode[episode["episode_id"]]]
            if not episodes:
                continue
            best_episode = ranked_members(episodes)[0]
            for sample_id in best_episode["sample_ids"]:
                sample = samples_by_id.get(sample_id)
                split = splits.get(sample["group_id"], "train") if splits else "train"
                prompt = _prompt_for(sample, normalize_packages)
                if sample_id == best_episode["root_sample_id"]:
                    messages = init_prompt + [{"role": "assistant", "content": sample["completion"]}]
                else:
                    messages = prompt + [{"role": "assistant", "content": sample["completion"]}]
                groupdata.write_jsonl(
                    handle,
                    {
                        "sample_id": sample["sample_id"],
                        "group_id": sample["group_id"],
                        "task": sample["task"],
                        "operator": sample["operator"],
                        "split": split,
                        "batch": sample["batch"],
                        "reward": sample["node_reward"],
                        "episode_reward": sample["episode_reward"],
                        "messages": messages,
                    },
                )
                writer.write(split, {"messages": messages})
                rows += 1
    writer.close()

    summary = {"view": "sft", "dataset": str(dataset_dir), "rows": rows, "parquet": writer.counts}
    if verbose:
        print(summary)
    return summary


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--dataset", required=True, help="Aggregated dataset directory.")
    parser.add_argument("--output-dir", required=True)
    parser.add_argument("--operators", default=None, help="Comma separated; default draft,debug,improve,crossover,analysis.")
    args = parser.parse_args()
    operators = {name.strip() for name in args.operators.split(",") if name.strip()} if args.operators else None
    to_sft(Path(args.dataset), Path(args.output_dir), operators=operators)


if __name__ == "__main__":
    main()
