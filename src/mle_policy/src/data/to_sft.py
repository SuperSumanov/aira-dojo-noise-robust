"""Stage 4a: complete-episode SFT data from the grouped dataset.

Each group contributes every operation from its highest-reward episode that
contains a runnable operation.  The root operation uses the earliest root
prompt in the group; later operations keep their recorded prompts.

The prompt normalisation (sorted package list, no search memory on proposals,
operator system message restored) lives in ``selection.training_messages`` so
that SFT and GRPO ask the model the same question.

``operator`` (draft / debug / improve / crossover / analysis) is carried into
``sft.jsonl`` so the Verl converter can report how many rows of each operator
survive the length filter.

Only ``sft.jsonl`` is written here; the tokenised parquet is produced by the
Verl-side converter, which is the only place that knows the model's chat
template.
"""

from __future__ import annotations

import argparse
from pathlib import Path
from typing import Any

from . import groupdata
from .selection import default_operators, eligible_members, ranked_members, training_messages


def to_sft(
    dataset_dir: Path,
    output_dir: Path,
    operators: set[str] | None = None,
    verbose: bool = True,
) -> dict[str, Any]:
    """Write ``sft.jsonl``."""
    dataset_dir = Path(dataset_dir).resolve()
    output_dir = Path(output_dir).resolve()
    output_dir.mkdir(parents=True, exist_ok=True)
    operators = default_operators() if operators is None else operators

    splits = groupdata.read_splits(dataset_dir)
    normalize_packages = bool(groupdata.read_manifest(dataset_dir).get("normalize_packages", True))
    samples_by_id = {sample["sample_id"]: sample for sample in groupdata.iter_samples(dataset_dir)}

    rows = 0
    with (output_dir / "sft.jsonl").open("w", encoding="utf-8") as handle:
        for group in groupdata.read_groups(dataset_dir):
            all_episodes = eligible_members(group, operators)
            if not all_episodes:
                continue
            init_episode = min(all_episodes, key=lambda e: (e["node_step"], e["sample_id"]))
            init_sample = samples_by_id[init_episode["root_sample_id"]]
            init_prompt = training_messages(init_sample, normalize_packages)

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
                prompt = training_messages(sample, normalize_packages)
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
                rows += 1

    summary = {"view": "sft", "dataset": str(dataset_dir), "rows": rows}
    if verbose:
        print(summary)
    return summary


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--dataset", required=True, help="Aggregated dataset directory.")
    parser.add_argument("--output-dir", required=True)
    parser.add_argument(
        "--operators", default=None, help="Comma separated; default draft,debug,improve,crossover,analysis."
    )
    args = parser.parse_args()
    operators = {name.strip() for name in args.operators.split(",") if name.strip()} if args.operators else None
    to_sft(Path(args.dataset), Path(args.output_dir), operators=operators)


if __name__ == "__main__":
    main()
