"""Two changes build_runsplit.py needs before it can see the v9 corpus.

CORPUS PATH. It hardcodes cards_current.jsonl (the original 9,433-card file). Any run that
only exists in a newer corpus never enters task_of_run, therefore never enters the holdout
draw, therefore every pair it touches lands in train. The senior's whole 1,940-card batch
would silently contribute zero test pairs. The path becomes an argument defaulting to the
newest corpus.

FROZEN HOLDOUT. It shuffles the full per-task run list with seed 7. Adding runs changes the
list length, which changes the permutation, which reassigns hold status for OLD runs too.
The fine-tuned RM was trained on the old train side; a reshuffle moves formerly-train runs
into test, and every number the RM produces on the new split is contaminated. Fix: freeze
every run of the OLD universe at its existing assignment -- held stays held (read from
runsplit_holdruns.json, which is a plain list), everything else in the old corpus stays
train -- and draw 20% only among runs absent from the old universe. The old universe is
reconstructed exactly: it is the run set of cards_current.jsonl, the very file the original
draw iterated. The writer is upgraded to record {"hold", "all"} so the NEXT extension can
freeze from the file alone.
"""
P = "phase1/build_runsplit.py"
s = open(P, encoding="utf-8").read()

if "FROZEN" in s:
    print("already patched")
    raise SystemExit(0)

a = '''RUN = json.load(open("phase1/card_run_map.json"))
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
'''
assert s.count(a) == 1, f"anchor not found ({s.count(a)})"
b = '''import os, sys
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
prior = json.load(open("phase1/runsplit_holdruns.json")) \\
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
'''
s = s.replace(a, b)
open(P, "w", encoding="utf-8").write(s)
print("patched", P)
