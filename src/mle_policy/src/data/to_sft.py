"""Stage 4a: rejection-sampling SFT data from the grouped dataset.

One row per prompt group: the best runnable action from the best resolved
episode, formatted as ``[system, user, assistant]``.

The selected episode may start with a broken root, but SFT only emits an
individual action that actually ran.  This avoids imitating a broken draft while
still retaining a useful repaired action from the same episode.
"""

from __future__ import annotations

import argparse
from pathlib import Path
from typing import Any

import pyarrow as pa

from . import groupdata
from .parquetwriter import MESSAGE_TYPE, SplitParquetWriter
from .selection import default_operators, eligible_members, ranked_members, training_prompt

SFT_SCHEMA = pa.schema([("messages", MESSAGE_TYPE)])


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
    best_of_group: dict[str, str] = {}
    for group in groupdata.read_groups(dataset_dir):
        episodes = eligible_members(group, operators)
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
        runnable_samples = runnable_by_episode[best_episode["episode_id"]]
        best_sample = max(
            runnable_samples,
            key=lambda sample: (
                sample["node_reward"] is not None,
                sample["node_reward"] if sample["node_reward"] is not None else float("-inf"),
                sample["sample_id"],
            ),
        )
        best_of_group[group["group_id"]] = best_sample["sample_id"]

    rows = 0
    writer = SplitParquetWriter(output_dir, "sft", SFT_SCHEMA)
    with (output_dir / "sft.jsonl").open("w", encoding="utf-8") as handle:
        for sample in samples_by_id.values():
            if best_of_group.get(sample["group_id"]) != sample["sample_id"]:
                continue
            split = splits.get(sample["group_id"], "train") if splits else "train"
            prompt = training_prompt(sample, normalize_packages)
            messages = prompt + [{"role": "assistant", "content": sample["completion"]}]
            groupdata.write_jsonl(
                handle,
                {
                    "sample_id": sample["sample_id"],
                    "group_id": sample["group_id"],
                    "task": sample["task"],
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
    parser.add_argument("--operators", default=None, help="Comma separated; default draft,debug,improve,crossover.")
    args = parser.parse_args()
    operators = {name.strip() for name in args.operators.split(",") if name.strip()} if args.operators else None
    to_sft(Path(args.dataset), Path(args.output_dir), operators=operators)


if __name__ == "__main__":
    main()
