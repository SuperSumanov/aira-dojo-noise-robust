"""Apply a physical-run split to existing pair files.

Both endpoints must be in training runs or both in held-out runs; straddling
pairs are dropped.  This is the corrected replacement for fragment/tree splits.

Usage:
  python -m src.mle_critic.src.preprocess.build_runsplit CARDS RUN_MAP HOLD_RUNS OUT_DIR PAIR...
"""
from __future__ import annotations

import argparse
import collections
import json
import random
from pathlib import Path


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("cards", type=Path)
    ap.add_argument("run_map", type=Path)
    ap.add_argument("hold_runs", type=Path)
    ap.add_argument("out_dir", type=Path)
    ap.add_argument("pairs", nargs="+", type=Path)
    ap.add_argument("--out-name", default=None,
                    help="output filename when exactly one pair file is supplied")
    ap.add_argument("--regenerate-hold", action="store_true",
                    help="recompute holdout runs even if hold_runs already exists")
    ap.add_argument("--seed", type=int, default=7)
    args = ap.parse_args()
    run_map = json.loads(args.run_map.read_text())
    cards = {}
    with args.cards.open() as stream:
        for line in stream:
            card = json.loads(line)
            cards[card["id"]] = card
    by_task = collections.defaultdict(list)
    for cid, rid in run_map.items():
        if cid in cards:
            by_task[cards[cid]["task"]["name"]].append(rid)
    if args.hold_runs.exists() and not args.regenerate_hold:
        hold = set(json.loads(args.hold_runs.read_text()))
    else:
        rng = random.Random(args.seed)
        hold = set()
        for task in sorted(by_task):
            runs = sorted(set(by_task[task]))
            rng.shuffle(runs)
            hold.update(runs[int(0.8 * len(runs)):])
        args.hold_runs.parent.mkdir(parents=True, exist_ok=True)
        args.hold_runs.write_text(json.dumps(sorted(hold), indent=2) + "\n")
    args.out_dir.mkdir(parents=True, exist_ok=True)
    print(f"runs={len(set(run_map.values()))} held={len(hold)}")
    for src in args.pairs:
        if args.out_name is not None and len(args.pairs) != 1:
            raise SystemExit("--out-name requires exactly one input pair file")
        dst = args.out_dir / (args.out_name or
                              src.name.replace("_v2", "_runsplit").replace("_v3", "_runsplit"))
        counts = collections.Counter()
        with src.open() as inp, dst.open("w") as out:
            for line in inp:
                pair = json.loads(line)
                keys = ("better", "worse") if "better" in pair else ("x", "y")
                ids = [pair.get(k) for k in keys]
                if any(i not in run_map for i in ids):
                    counts["skip_unmapped"] += 1
                    continue
                sides = {run_map[i] in hold for i in ids}
                if len(sides) != 1:
                    counts["drop_straddle"] += 1
                    continue
                pair["intask_split"] = "test" if True in sides else "train"
                out.write(json.dumps(pair, separators=(",", ":")) + "\n")
                counts[pair["intask_split"]] += 1
        print(f"{src.name} -> {dst.name}: {dict(counts)}")


if __name__ == "__main__":
    main()
