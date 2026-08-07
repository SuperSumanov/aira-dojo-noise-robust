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

RUN = json.load(open("phase1/card_run_map.json"))
task_of_run = {}
for l in open("phase1/cards_current.jsonl"):
    d = json.loads(l)
    task_of_run[RUN[d["id"]]] = d["task"]["name"]

rng = random.Random(7)
by_task = collections.defaultdict(list)
for r, t in task_of_run.items():
    by_task[t].append(r)
hold = set()
for t in sorted(by_task):
    rs = sorted(by_task[t])
    rng.shuffle(rs)
    hold.update(rs[int(0.8 * len(rs)):])
json.dump(sorted(hold), open("phase1/runsplit_holdruns.json", "w"))
print(f"runs={len(task_of_run)} held={len(hold)}")

JOBS = [
    ("phase1/value_pairs_v3.jsonl", "phase1/value_pairs_runsplit.jsonl"),
    ("phase1/budget_pairs_v3.jsonl", "phase1/budget_pairs_v3_runsplit.jsonl"),
    ("phase1/decision_pairs_v1b.jsonl", "phase1/decision_pairs_runsplit.jsonl"),
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
