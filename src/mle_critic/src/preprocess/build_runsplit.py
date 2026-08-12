"""Apply and extend a frozen physical-run split to pair files.

The holdout file uses the current schema ``{"hold": [...], "all": [...]}``.
Runs in ``all`` keep their existing assignment forever.  New runs are drawn
task-wise into the held-out side with seed 7, then added to ``all``.  Legacy
list-only holdout files are still readable, but cannot be safely extended
without ``--prior-cards`` to identify their already-assigned run universe.

Both pair endpoints must be on the same side.  Straddling or unmapped pairs are
dropped.  This replaces the invalid lineage-fragment/tree split.

Usage:
  python -m src.mle_critic.src.preprocess.build_runsplit \
    CARDS RUN_MAP HOLD_RUNS OUT_DIR PAIR...
"""
from __future__ import annotations

import argparse
import collections
import json
import random
from pathlib import Path


def read_cards(path: Path) -> dict[str, dict]:
    cards = {}
    with path.open(encoding="utf-8") as stream:
        for line in stream:
            card = json.loads(line)
            cards[card["id"]] = card
    return cards


def runs_in_cards(cards: dict[str, dict], run_map: dict[str, str]) -> set[str]:
    return {run_map[card_id] for card_id in cards if card_id in run_map}


def draw_holdout(
    runs: set[str], task_of_run: dict[str, str], seed: int
) -> set[str]:
    by_task = collections.defaultdict(list)
    for run_id in runs:
        by_task[task_of_run[run_id]].append(run_id)
    rng = random.Random(seed)
    hold = set()
    for task in sorted(by_task):
        task_runs = sorted(by_task[task])
        rng.shuffle(task_runs)
        hold.update(task_runs[int(0.8 * len(task_runs)):])
    return hold


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("cards", type=Path)
    parser.add_argument("run_map", type=Path)
    parser.add_argument("hold_runs", type=Path)
    parser.add_argument("out_dir", type=Path)
    parser.add_argument("pairs", nargs="+", type=Path)
    parser.add_argument(
        "--out-name",
        default=None,
        help="output filename when exactly one pair file is supplied",
    )
    parser.add_argument(
        "--regenerate-hold",
        action="store_true",
        help="discard all frozen assignments and redraw from the current corpus",
    )
    parser.add_argument(
        "--prior-cards",
        type=Path,
        help="old corpus universe when upgrading a legacy list-only holdout file",
    )
    parser.add_argument("--seed", type=int, default=7)
    args = parser.parse_args()

    run_map = json.loads(args.run_map.read_text(encoding="utf-8"))
    cards = read_cards(args.cards)
    missing_run_ids = set(cards) - set(run_map)
    if missing_run_ids:
        sample = sorted(missing_run_ids)[:3]
        raise ValueError(
            f"run map is missing {len(missing_run_ids)} cards, e.g. {sample}"
        )

    current_runs = runs_in_cards(cards, run_map)
    task_of_run = {}
    for card_id, card in cards.items():
        run_id = run_map[card_id]
        task = card["task"]["name"]
        previous = task_of_run.setdefault(run_id, task)
        if previous != task:
            raise ValueError(f"physical run {run_id} spans {previous} and {task}")

    hold = set()
    assigned = set()
    if args.hold_runs.exists() and not args.regenerate_hold:
        payload = json.loads(args.hold_runs.read_text(encoding="utf-8"))
        if isinstance(payload, dict):
            hold = set(payload["hold"])
            assigned = set(payload["all"])
        elif isinstance(payload, list):
            hold = set(payload)
            if args.prior_cards is None:
                raise ValueError(
                    "legacy list-only holdout does not record its assigned run "
                    "universe; pass the matching old corpus with --prior-cards "
                    "or install the authoritative {'hold','all'} holdout file"
                )
            assigned = runs_in_cards(read_cards(args.prior_cards), run_map)
        else:
            raise ValueError("holdout JSON must be a list or an object")
        if not hold <= assigned:
            raise ValueError("held-out runs are not a subset of the assigned universe")

    if args.regenerate_hold or not args.hold_runs.exists():
        assigned = set(current_runs)
        hold = draw_holdout(current_runs, task_of_run, args.seed)
        new_runs = set(current_runs)
    else:
        new_runs = current_runs - assigned
        hold.update(draw_holdout(new_runs, task_of_run, args.seed))
        assigned.update(new_runs)

    args.hold_runs.parent.mkdir(parents=True, exist_ok=True)
    args.hold_runs.write_text(
        json.dumps(
            {"hold": sorted(hold), "all": sorted(assigned)},
            ensure_ascii=False,
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )
    print(
        f"runs={len(current_runs)} held={len(hold & current_runs)} "
        f"frozen_universe={len(assigned)} new_runs={len(new_runs)}"
    )

    args.out_dir.mkdir(parents=True, exist_ok=True)
    for source in args.pairs:
        if args.out_name is not None and len(args.pairs) != 1:
            raise SystemExit("--out-name requires exactly one input pair file")
        destination = args.out_dir / (
            args.out_name
            or source.name.replace("_v2", "_runsplit").replace("_v3", "_runsplit")
        )
        counts = collections.Counter()
        sides_by_run = collections.defaultdict(set)
        with source.open(encoding="utf-8") as input_stream, destination.open(
            "w", encoding="utf-8"
        ) as output:
            for line in input_stream:
                pair = json.loads(line)
                keys = ("better", "worse") if "better" in pair else ("x", "y")
                ids = [pair.get(key) for key in keys]
                if any(card_id not in run_map for card_id in ids):
                    counts["skip_unmapped"] += 1
                    continue
                endpoint_runs = [run_map[card_id] for card_id in ids]
                endpoint_sides = {run_id in hold for run_id in endpoint_runs}
                if len(endpoint_sides) != 1:
                    counts["drop_straddle"] += 1
                    continue
                split = "test" if endpoint_sides.pop() else "train"
                pair["intask_split"] = split
                output.write(json.dumps(pair, ensure_ascii=False) + "\n")
                counts[split] += 1
                for run_id in endpoint_runs:
                    sides_by_run[run_id].add(split)
        leaking_runs = [run_id for run_id, sides in sides_by_run.items() if len(sides) > 1]
        if leaking_runs:
            raise RuntimeError(
                f"{destination} has {len(leaking_runs)} runs on both split sides"
            )
        print(f"{source.name} -> {destination.name}: {dict(counts)}")


if __name__ == "__main__":
    main()
