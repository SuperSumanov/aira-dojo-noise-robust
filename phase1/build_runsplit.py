"""Reassign pair-file splits at PHYSICAL-RUN level (post-hoc; labels untouched).

Fragment-level "tree" splits leaked run identity: 99.7% of test pairs share a run with
training pairs (card_run_map.json, validated segmentation). Rule here: hold 20% of runs
per task (seed 7); a pair is test iff BOTH endpoints' runs are held, train iff NEITHER is,
dropped if it straddles. Within-run pairs (all decision pairs) never straddle.

Flip-eval records are filtered by the same rule so flip metrics stay leak-consistent.

Usage: python phase1/build_runsplit.py
Writes: value_pairs_runsplit.jsonl, budget_pairs_v3_runsplit.jsonl,
        decision_pairs_runsplit.jsonl, budget_flip_v3_runsplit.jsonl, runsplit_holdruns.json
"""
import collections, json, random

import os, sys
CARDS = sys.argv[1] if len(sys.argv) > 1 else "phase1/cards_current_v9.jsonl"
RUN = json.load(open("phase1/card_run_map.json"))
task_of_run = {}
for l in open(CARDS):
    d = json.loads(l)
    task_of_run[RUN[d["id"]]] = d["task"]["name"]

# FROZEN holdout. Prior assignments are immutable so models trained on the earlier train
# side stay valid on the earlier test side; only runs outside the old universe enter the
# new draw (20% per task, seed 7). The old universe is exactly the run set of the file the
# original draw iterated.
prior = json.load(open("phase1/runsplit_holdruns.json")) \
    if os.path.exists("phase1/runsplit_holdruns.json") else []
prior_hold = set(prior["hold"] if isinstance(prior, dict) else prior)
if isinstance(prior, dict):
    prior_all = set(prior["all"])
else:
    prior_all = set()
    if os.path.exists("phase1/cards_current.jsonl"):
        for l in open("phase1/cards_current.jsonl"):
            d = json.loads(l)
            r = RUN.get(d["id"])
            if r is not None:
                prior_all.add(r)
    assert prior_hold <= prior_all, "held runs missing from the reconstructed old universe"

rng = random.Random(7)
by_task = collections.defaultdict(list)
for r, t in task_of_run.items():
    if r not in prior_all:
        by_task[t].append(r)
hold = set(prior_hold)
for t in sorted(by_task):
    rs = sorted(by_task[t])
    rng.shuffle(rs)
    hold.update(rs[int(0.8 * len(rs)):])
json.dump({"hold": sorted(hold), "all": sorted(prior_all | set(task_of_run))},
          open("phase1/runsplit_holdruns.json", "w"))
print(f"runs={len(task_of_run)} held={len(hold)} "
      f"(frozen prior: {len(prior_hold)} held / {len(prior_all)} universe; "
      f"new runs drawn from: {sum(map(len, by_task.values()))})")

JOBS = [
    ("phase1/value_pairs_v3.jsonl", "phase1/value_pairs_runsplit.jsonl"),
    ("phase1/budget_pairs_v3.jsonl", "phase1/budget_pairs_v3_runsplit.jsonl"),
    ("phase1/decision_pairs_v9raw.jsonl", "phase1/decision_pairs_runsplit.jsonl"),
    ("phase1/budget_flip_v3.jsonl", "phase1/budget_flip_v3_runsplit.jsonl"),
]
for src, dst in JOBS:
    n = collections.Counter()
    with open(dst, "w") as out:
        for l in open(src):
            p = json.loads(l)
            ids = [p[k] for k in ("better", "worse") if k in p and isinstance(p.get(k), str)]
            if len(ids) < 2 or any(i not in RUN for i in ids):
                n["skip_unmapped"] += 1
                continue
            h = {RUN[i] in hold for i in ids}
            if len(h) > 1:
                n["drop_straddle"] += 1
                continue
            p["intask_split"] = "test" if h.pop() else "train"
            out.write(json.dumps(p) + "\n")
            n[p["intask_split"]] += 1
    print(f"{dst}: {dict(n)}")

# verification: no run contributes to both sides of any output file
for _, dst in JOBS:
    sides = collections.defaultdict(set)
    for l in open(dst):
        p = json.loads(l)
        for k in ("better", "worse"):
            sides[RUN[p[k]]].add(p["intask_split"])
    bad = sum(1 for v in sides.values() if len(v) > 1)
    print(f"verify {dst}: runs on both sides = {bad} {'OK' if bad == 0 else 'BROKEN'}")
