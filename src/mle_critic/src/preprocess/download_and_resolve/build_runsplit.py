"""Create or extend the frozen train/test assignment of physical runs.

The Card input uses the run-grouped JSON format produced by ``build_cards``:

    {"physical_run_id": [{Card}, ...], ...}

The split file uses this repository's run-split format:

    {"hold": [test run IDs], "all": [all assigned run IDs]}

When the split file already exists, every old assignment is preserved.  Only
run IDs absent from ``all`` are assigned, task by task, using an 80/20 split.
When the split file does not exist, all runs in the Card file are assigned from
scratch.  Historical runs absent from the current Card corpus remain in the
output so that their frozen identities are not forgotten.

Usage:
    python -m src.preprocess.download_and_resolve.build_runsplit \
        CARDS.json RUNSPLIT.json [--out OUTPUT.json] [--seed 7]
"""
from __future__ import annotations

import argparse
import json
import os
import random
import tempfile
from collections import defaultdict
from pathlib import Path
from typing import Mapping, Sequence


def read_task_by_run(cards_path: Path) -> dict[str, str]:
    """Read one task name for every physical run in a grouped Card file."""
    with cards_path.open(encoding="utf-8") as input_file:
        cards_by_run_id = json.load(input_file)
    if not isinstance(cards_by_run_id, dict):
        raise ValueError(
            f"Expected a JSON object mapping run IDs to Card lists: {cards_path}"
        )

    task_by_run_id: dict[str, str] = {}
    for run_id, run_cards in cards_by_run_id.items():
        if not isinstance(run_id, str) or not run_id:
            raise ValueError(f"Invalid run ID in {cards_path}: {run_id!r}")
        if not isinstance(run_cards, list) or not run_cards:
            raise ValueError(f"Run {run_id!r} has no Cards")

        task_names = set()
        for card in run_cards:
            try:
                task_name = card["task"]["name"]
            except (KeyError, TypeError) as error:
                raise ValueError(
                    f"Run {run_id!r} contains a Card without task.name"
                ) from error
            if not isinstance(task_name, str) or not task_name:
                raise ValueError(
                    f"Run {run_id!r} contains an invalid task name: {task_name!r}"
                )
            task_names.add(task_name)

        if len(task_names) != 1:
            raise ValueError(
                f"Physical run {run_id!r} spans multiple tasks: {sorted(task_names)}"
            )
        task_by_run_id[run_id] = task_names.pop()

    return task_by_run_id


def read_existing_split(split_path: Path) -> tuple[set[str], set[str]]:
    """Return ``(held_out_runs, assigned_runs)`` or two empty sets if absent."""
    if not split_path.exists():
        return set(), set()

    with split_path.open(encoding="utf-8") as input_file:
        payload = json.load(input_file)
    if not isinstance(payload, dict):
        raise ValueError(
            f"Expected {split_path} to contain {{'hold': [...], 'all': [...]}}"
        )
    if not isinstance(payload.get("hold"), list) or not isinstance(
        payload.get("all"), list
    ):
        raise ValueError(f"Split file {split_path} must contain list fields hold/all")

    held_out_runs = set(payload["hold"])
    assigned_runs = set(payload["all"])
    if not all(isinstance(run_id, str) for run_id in assigned_runs | held_out_runs):
        raise ValueError(f"Split file {split_path} contains a non-string run ID")
    if not held_out_runs <= assigned_runs:
        unknown_held_out = sorted(held_out_runs - assigned_runs)[:3]
        raise ValueError(
            "Held-out runs must be included in the assigned universe; "
            f"examples missing from all: {unknown_held_out}"
        )
    return held_out_runs, assigned_runs


def draw_taskwise_holdout(
    run_ids: Sequence[str],
    task_by_run_id: Mapping[str, str],
    seed: int,
) -> tuple[set[str], dict[str, tuple[int, int]]]:
    """Select the final 20% of deterministically shuffled runs for each task."""
    runs_by_task: dict[str, list[str]] = defaultdict(list)
    for run_id in run_ids:
        runs_by_task[task_by_run_id[run_id]].append(run_id)

    random_generator = random.Random(seed)
    held_out_runs: set[str] = set()
    counts_by_task: dict[str, tuple[int, int]] = {}
    for task_name in sorted(runs_by_task):
        task_runs = sorted(runs_by_task[task_name])
        random_generator.shuffle(task_runs)
        task_holdout = task_runs[int(0.8 * len(task_runs)) :]
        held_out_runs.update(task_holdout)
        counts_by_task[task_name] = (len(task_runs), len(task_holdout))
    return held_out_runs, counts_by_task


def extend_runsplit(
    task_by_run_id: Mapping[str, str],
    old_held_out_runs: set[str],
    old_assigned_runs: set[str],
    seed: int = 7,
) -> tuple[set[str], set[str], set[str], dict[str, tuple[int, int]]]:
    """Preserve old assignments and assign every previously unseen run."""
    if not old_held_out_runs <= old_assigned_runs:
        raise ValueError("Old held-out runs are not a subset of old assigned runs")

    current_runs = set(task_by_run_id)
    new_runs = current_runs - old_assigned_runs
    new_held_out_runs, counts_by_task = draw_taskwise_holdout(
        sorted(new_runs), task_by_run_id, seed
    )

    assigned_runs = old_assigned_runs | new_runs
    held_out_runs = old_held_out_runs | new_held_out_runs
    return held_out_runs, assigned_runs, new_runs, counts_by_task


def write_split_atomic(
    output_path: Path, held_out_runs: set[str], assigned_runs: set[str]
) -> None:
    """Write a complete split file, replacing the destination atomically."""
    output_path.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "hold": sorted(held_out_runs),
        "all": sorted(assigned_runs),
    }
    temporary_path = None
    try:
        with tempfile.NamedTemporaryFile(
            mode="w",
            encoding="utf-8",
            dir=output_path.parent,
            prefix=f".{output_path.name}.",
            suffix=".tmp",
            delete=False,
        ) as temporary_file:
            temporary_path = Path(temporary_file.name)
            json.dump(payload, temporary_file, ensure_ascii=False, indent=2)
            temporary_file.write("\n")
        os.replace(temporary_path, output_path)
    finally:
        if temporary_path is not None and temporary_path.exists():
            temporary_path.unlink()


def update_runsplit(
    cards_path: Path,
    existing_split_path: Path,
    output_path: Path | None = None,
    seed: int = 7,
) -> dict[str, int]:
    """Load, extend, and write a frozen run split."""
    task_by_run_id = read_task_by_run(cards_path)
    old_held_out_runs, old_assigned_runs = read_existing_split(existing_split_path)

    current_runs = set(task_by_run_id)
    overlap_count = len(current_runs & old_assigned_runs)

    held_out_runs, assigned_runs, new_runs, counts_by_task = extend_runsplit(
        task_by_run_id,
        old_held_out_runs,
        old_assigned_runs,
        seed=seed,
    )
    destination = output_path or existing_split_path
    write_split_atomic(destination, held_out_runs, assigned_runs)

    print(
        f"current_runs={len(current_runs)} overlap_old={overlap_count} "
        f"new_runs={len(new_runs)} current_held={len(held_out_runs & current_runs)} "
        f"frozen_universe={len(assigned_runs)} -> {destination}"
    )
    for task_name, (new_count, held_count) in counts_by_task.items():
        print(
            f"  {task_name[:44]:44s} new={new_count:4d} "
            f"new_held={held_count:4d}"
        )

    return {
        "current_runs": len(current_runs),
        "overlap_old": overlap_count,
        "new_runs": len(new_runs),
        "current_held": len(held_out_runs & current_runs),
        "assigned_runs": len(assigned_runs),
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("cards", type=Path, help="run-grouped Card JSON")
    parser.add_argument(
        "runsplit",
        type=Path,
        help="existing split to extend, or path to create if it does not exist",
    )
    parser.add_argument(
        "--out",
        type=Path,
        default=None,
        help="write elsewhere instead of replacing/creating RUNSPLIT",
    )
    parser.add_argument("--seed", type=int, default=7)
    return parser.parse_args()


def main() -> None:
    arguments = parse_args()
    update_runsplit(
        cards_path=arguments.cards,
        existing_split_path=arguments.runsplit,
        output_path=arguments.out,
        seed=arguments.seed,
    )


if __name__ == "__main__":
    main()
