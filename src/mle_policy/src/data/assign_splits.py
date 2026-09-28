"""Stage 3: decide the train/val split of an aggregated dataset.

This runs *after* aggregation, on purpose: which runs are held out is a choice
about the final dataset, not something a single batch should decide.

The unit that moves between train and val is the **split key**, chosen with
``--split-by``:

``task``
    whole competitions go to one side.  Val asks "can the policy handle a
    competition it has never seen" and never shares a task with train.
``group``
    individual prompt groups move, so val prompts are unseen but the tasks are
    not.
``run``
    whole runs move.  A group that spans runs is filed under its first run, so
    for cross-run groups this one leaks; prefer ``task``.

Keys are ranked by a seeded hash and the lowest ``--val-fraction`` become val,
which -- unlike a plain hash threshold -- always yields a non-empty val set.
"""

from __future__ import annotations

import argparse
import hashlib
import json
from collections import Counter
from pathlib import Path
from typing import Any

from . import groupdata


def assign_splits(
    groups: list[dict[str, Any]],
    split_by: str,
    val_fraction: float,
    seed: int,
) -> dict[str, str]:
    """Return ``group_id -> 'train' | 'val'``."""
    if split_by not in ("task", "group", "run"):
        raise ValueError(f"Unsupported split_by: {split_by}")

    def split_key(group: dict[str, Any]) -> str:
        if split_by == "group":
            return group["group_id"]
        if split_by == "run":
            return sorted(member["run_dir"] for member in group["members"])[0]
        return group["task"]

    keys = sorted(
        {split_key(group) for group in groups},
        key=lambda key: hashlib.blake2b(f"{seed}\x1f{key}".encode("utf-8"), digest_size=8).digest(),
    )
    n_val = int(round(val_fraction * len(keys)))
    if val_fraction > 0 and len(keys) > 1:
        n_val = min(max(n_val, 1), len(keys) - 1)
    val_keys = set(keys[:n_val])
    return {group["group_id"]: ("val" if split_key(group) in val_keys else "train") for group in groups}


def assign_dataset_splits(
    dataset_dir: Path,
    split_by: str = "task",
    val_fraction: float = 0.1,
    seed: int = 0,
    output_path: Path | None = None,
    verbose: bool = True,
) -> dict[str, Any]:
    """Write ``splits.jsonl`` for *dataset_dir*."""
    dataset_dir = Path(dataset_dir).resolve()
    groups = groupdata.read_groups(dataset_dir)
    splits = assign_splits(groups, split_by, val_fraction, seed)
    output_path = output_path or (dataset_dir / groupdata.SPLITS_FILE)

    counts = Counter(splits.values())
    val_tasks = sorted({group["task"] for group in groups if splits[group["group_id"]] == "val"})
    with output_path.open("w", encoding="utf-8") as handle:
        for group in groups:
            groupdata.write_jsonl(
                handle,
                {"group_id": group["group_id"], "task": group["task"], "split": splits[group["group_id"]]},
            )

    manifest_path = dataset_dir / groupdata.MANIFEST_FILE
    if manifest_path.is_file():
        manifest = groupdata.read_manifest(dataset_dir)
        manifest["split"] = {
            "split_by": split_by,
            "val_fraction": val_fraction,
            "seed": seed,
            "group_counts": dict(counts),
            "val_tasks": val_tasks,
        }
        groupdata.write_manifest(dataset_dir, manifest)

    summary = {
        "dataset": str(dataset_dir),
        "splits_file": str(output_path),
        "split_by": split_by,
        "val_fraction": val_fraction,
        "group_counts": dict(counts),
        "val_tasks": val_tasks,
    }
    if verbose:
        print(json.dumps(summary, ensure_ascii=False, indent=2))
    return summary


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--dataset", required=True, help="Aggregated dataset directory.")
    parser.add_argument("--split-by", choices=("task", "group", "run"), default="task")
    parser.add_argument("--val-fraction", type=float, default=0.1)
    parser.add_argument("--seed", type=int, default=0)
    parser.add_argument("--output", default=None, help="Defaults to <dataset>/splits.jsonl.")
    args = parser.parse_args()

    assign_dataset_splits(
        dataset_dir=Path(args.dataset),
        split_by=args.split_by,
        val_fraction=args.val_fraction,
        seed=args.seed,
        output_path=Path(args.output) if args.output else None,
    )


if __name__ == "__main__":
    main()
