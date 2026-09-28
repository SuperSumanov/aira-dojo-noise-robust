"""Stage 4c: group-relative data from the grouped dataset.

One row per prompt group that has at least two members whose debug process ended
in a runnable solution.  ``responses`` holds those completions with the reward
that group-relative advantage needs, sorted best first.

The reward is the **episode** reward: every step of a debug process is credited
with the score of the runnable solution the process ended in, which is the MDP
return of the action that started it.  Members whose process never ended in a
runnable solution are dropped (they cannot carry a return) -- they are still
available as ``rejected`` in ``to_dpo``.

The parquet output is shaped for inspection and for offline variants; stock
``verl`` GRPO rolls out its own responses and only needs the prompt.
"""

from __future__ import annotations

import argparse
from pathlib import Path
from typing import Any

import pyarrow as pa

from . import groupdata
from .parquetwriter import MESSAGE_TYPE, SplitParquetWriter
from .selection import default_operators, eligible_members, training_prompt

RESPONSE_TYPE = pa.list_(
    pa.struct([("sample_id", pa.string()), ("completion", pa.string()), ("reward", pa.float64())])
)
GRPO_SCHEMA = pa.schema(
    [
        ("prompt", MESSAGE_TYPE),
        ("responses", RESPONSE_TYPE),
        ("rewards", pa.list_(pa.float64())),
        ("task", pa.string()),
        ("split", pa.string()),
        ("group_id", pa.string()),
        ("batch", pa.string()),
    ]
)


def to_grpo(
    dataset_dir: Path,
    output_dir: Path,
    operators: set[str] | None = None,
    verbose: bool = True,
) -> dict[str, Any]:
    """Write ``grpo.jsonl`` plus ``grpo_{train,val}.parquet``."""
    dataset_dir = Path(dataset_dir).resolve()
    output_dir = Path(output_dir).resolve()
    output_dir.mkdir(parents=True, exist_ok=True)
    operators = default_operators() if operators is None else operators

    splits = groupdata.read_splits(dataset_dir)
    normalize_packages = bool(groupdata.read_manifest(dataset_dir).get("normalize_packages", True))
    members_needed: dict[str, set[str]] = {}
    for group in groupdata.read_groups(dataset_dir):
        resolved = [
            member
            for member in eligible_members(group, operators)
            if member["episode_resolved"] and member.get("episode_reward") is not None
        ]
        if len(resolved) >= 2:
            members_needed[group["group_id"]] = {member["sample_id"] for member in resolved}

    buffered: dict[str, dict[str, Any]] = {}
    writer = SplitParquetWriter(output_dir, "grpo", GRPO_SCHEMA)
    rows = 0
    responses_total = 0
    with (output_dir / "grpo.jsonl").open("w", encoding="utf-8") as handle:
        for sample in groupdata.iter_samples(dataset_dir):
            group_id = sample["group_id"]
            needed = members_needed.get(group_id)
            if needed is None or sample["sample_id"] not in needed:
                continue
            buffer = buffered.setdefault(group_id, {})
            buffer[sample["sample_id"]] = sample
            if len(buffer) < len(needed):
                continue

            # Every member of a group answers the same canonical prompt; all of
            # them are resolved here, so ranking is a plain reward sort.
            ordered = sorted(buffer.values(), key=lambda sample: (sample["episode_reward"], sample["sample_id"]))
            ordered.reverse()
            prompt = training_prompt(ordered[0], normalize_packages)
            responses = [
                {
                    "sample_id": sample["sample_id"],
                    "completion": sample["completion"],
                    "reward": sample["episode_reward"],
                }
                for sample in ordered
            ]
            split = splits.get(group_id, "train") if splits else "train"
            record = {
                "group_id": group_id,
                "task": ordered[0]["task"],
                "batch": ordered[0]["batch"],
                "split": split,
                "prompt": prompt,
                "responses": responses,
            }
            groupdata.write_jsonl(handle, record)
            writer.write(
                split,
                {
                    "prompt": prompt,
                    "responses": responses,
                    "rewards": [response["reward"] for response in responses],
                    "task": record["task"],
                    "split": split,
                    "group_id": group_id,
                    "batch": record["batch"],
                },
            )
            rows += 1
            responses_total += len(responses)
            del buffered[group_id]
            del members_needed[group_id]
    writer.close()

    summary = {
        "view": "grpo",
        "dataset": str(dataset_dir),
        "groups": rows,
        "responses": responses_total,
        "parquet": writer.counts,
    }
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
    to_grpo(Path(args.dataset), Path(args.output_dir), operators=operators)


if __name__ == "__main__":
    main()
