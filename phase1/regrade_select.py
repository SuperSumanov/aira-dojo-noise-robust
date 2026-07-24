"""Re-grade arm — node selection. Per task: up to N_SEL graded, non-trivial-code nodes,
stratified across the y range (quantile bins) and operator mix. Emits a manifest JSONL:
{card_id, competition, y_norm, graded, op, code}. Idempotent (overwrite).
Usage: python phase1/regrade_select.py [--per-task 24] [--out phase1/regrade_manifest.jsonl]
"""
import argparse
import json
import sys

import numpy as np

sys.path.insert(0, "/research/d7/spc/yzyang4/aira-dojo")
from phase1.cards import load_cards
from phase1.dataset import labeled

ap = argparse.ArgumentParser()
ap.add_argument("--cards", default="phase1/cards_t1_labeled.jsonl")
ap.add_argument("--per-task", type=int, default=24)
ap.add_argument("--out", default="phase1/regrade_manifest.jsonl")
a = ap.parse_args()

cards = labeled(load_cards(a.cards))
by_task = {}
for c in cards:
    if c.code and len(c.code.strip()) > 100 and c.label and c.label.graded is not None:
        by_task.setdefault(c.task.name, []).append(c)

rows = []
for t, cs in sorted(by_task.items()):
    if len(cs) < 8:
        print(f"skip {t}: only {len(cs)} candidates")
        continue
    ys = np.array([c.y for c in cs])
    order = np.argsort(ys)
    n = min(a.per_task, len(cs))
    picks_idx = sorted(set(int(round(i)) for i in np.linspace(0, len(cs) - 1, n)))  # quantile-stratified
    for i in picks_idx:
        c = cs[order[i]]
        rows.append({"card_id": c.id, "competition": c.task.name, "y_norm": c.y,
                     "graded": c.label.graded, "op": (c.lineage.op or "?"), "code": c.code})
    print(f"{t}: selected {len(picks_idx)}/{len(cs)} (y-range {ys.min():.2f}-{ys.max():.2f})")

with open(a.out, "w") as f:
    for r in rows:
        f.write(json.dumps(r) + "\n")
print(f"[regrade_select] {len(rows)} nodes -> {a.out}")
