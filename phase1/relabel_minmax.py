"""Per-task min-max relabel of graded cards (reproduces cards_real_mm.jsonl).

build_cards.py keeps cards by medal-based y_norm, but medal thresholds squash some tasks (e.g.
tps_may: all below bronze -> constant y_norm -> a useless fold). This rescales EACH task's label to
[0,1] by min-max over that task's raw graded scores (oriented for lower-is-better), giving intra-task
discrimination. In:  cards_real.jsonl (has label.graded)  Out: cards_real_mm.jsonl.

Usage:  python -m phase1.relabel_minmax cards_real.jsonl cards_real_mm.jsonl
"""
import argparse
from collections import defaultdict

from .cards import load_cards, save_cards


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("in_path")
    ap.add_argument("out_path")
    a = ap.parse_args()

    cards = load_cards(a.in_path)
    by_task = defaultdict(list)
    for c in cards:
        if c.label is not None and c.label.graded is not None:
            by_task[c.task.name].append(c)

    for t, cs in by_task.items():
        hib = cs[0].task.higher_is_better
        vals = [(c.label.graded if hib else -c.label.graded) for c in cs]
        lo, hi = min(vals), max(vals)
        for c in cs:
            v = c.label.graded if hib else -c.label.graded
            c.label.y_norm = (v - lo) / (hi - lo) if hi > lo else 0.5

    kept = [c for cs in by_task.values() for c in cs]
    save_cards(kept, a.out_path)
    print(f"[relabel_minmax] {len(kept)} cards -> {a.out_path}")
    for t in sorted(by_task):
        n = len(by_task[t])
        ys = [c.label.y_norm for c in by_task[t]]
        print(f"  {n:>4} | {t:35s} y_norm range [{min(ys):.2f},{max(ys):.2f}]")


if __name__ == "__main__":
    main()
