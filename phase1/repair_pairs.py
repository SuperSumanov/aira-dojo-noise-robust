"""Repair-worthiness pairs: which failed program is worth spending a debug step on?

The one decision in the search where the agent's self-report is not merely weak but
UNDEFINED: the node produced no score at all. Measured on the corpus, 1,067 nodes are
scoreless, the search retries 875 of them (always exactly once -- there is no retry-count
variation to exploit), and 53.3% of those repairs go on to produce a score. So the decision
is real, frequent, and its outcome is balanced.

Framed pairwise so the existing Bradley-Terry trainer applies unchanged, and -- more
importantly -- so the task-prior baseline is exactly 0.5: both endpoints come from the SAME
task, so "guess the task's majority class" earns nothing. (Pooled across tasks the majority
baseline is 0.603, which is why a pooled binary framing would have been misleading.)

  endpoint  = a scoreless node that the search retried
  label     = its repair produced a score / did not
  pair      = same task, one success and one failure
  split     = by RUN (card_run_map.json), the standing rule after the leakage audit
  text      = the FAILED parent's code -- the artifact available at decision time

Usage: python phase1/repair_pairs.py OUT.jsonl [cards.jsonl] [--cap-per-task N]
"""
import collections, itertools, json, math, random, sys

OUT = sys.argv[1]
CARDS = sys.argv[2] if len(sys.argv) > 2 else "phase1/cards_current_v7.jsonl"
CAP = 4000
if "--cap-per-task" in sys.argv:
    CAP = int(sys.argv[sys.argv.index("--cap-per-task") + 1])

cards = {}
for l in open(CARDS):
    d = json.loads(l)
    cards[d["id"]] = d
RUN = json.load(open("phase1/card_run_map.json"))


def fin(x):
    try:
        v = float(x)
    except (TypeError, ValueError):
        return None
    return v if math.isfinite(v) else None


def sr_of(d):
    return fin(d["obs"].get("val_at_low"))


scoreless = {c for c, d in cards.items() if sr_of(d) is None}
# outcome of the repair the search actually performed on this node
outcome = {}
for c, d in cards.items():
    p = d["lineage"].get("parent_id")
    if d["lineage"].get("op") == "Debug" and p in scoreless:
        # a parent retried more than once would need aggregating; the corpus has none
        outcome[p] = max(outcome.get(p, 0), int(sr_of(d) is not None))
print(f"scoreless nodes {len(scoreless)}; retried (labelled) {len(outcome)}; "
      f"success rate {sum(outcome.values())/max(len(outcome),1):.3f}")

by_task = collections.defaultdict(list)
for c, y in outcome.items():
    if c in RUN:
        by_task[cards[c]["task"]["name"]].append((c, y))

rng = random.Random(7)
hold = {}
for t, lst in by_task.items():
    runs = sorted({RUN[c] for c, _ in lst})
    rng.shuffle(runs)
    hold[t] = set(runs[int(0.8 * len(runs)):])

n = collections.Counter()
with open(OUT, "w") as f:
    for t, lst in sorted(by_task.items()):
        if len(lst) < 30:
            continue
        wins = [c for c, y in lst if y == 1]
        loss = [c for c, y in lst if y == 0]
        if not wins or not loss:
            continue
        prs = [(a, b) for a in wins for b in loss]
        rng.shuffle(prs)
        kept = 0
        for hi, lo in prs:
            hh, hl = RUN[hi] in hold[t], RUN[lo] in hold[t]
            if hh != hl:
                n[t, "straddle_dropped"] += 1
                continue          # never let a held run leak into training
            split = "test" if hh else "train"
            f.write(json.dumps({
                "task": t, "better": hi, "worse": lo, "budget": 0,
                "intask_split": split, "loto_fold": t,
                "clears_tau": None, "src": "repair"}) + "\n")
            n[t, split] += 1
            kept += 1
            if kept >= CAP:
                break
        print(f"  {t[:42]:42s} succ={len(wins):4d} fail={len(loss):4d} "
              f"pairs={kept}  (test {n[t,'test']})")

print(f"\n[repair_pairs] wrote {sum(v for (t, k), v in n.items() if k in ('train','test'))} "
      f"pairs -> {OUT}")
print(f"  train {sum(v for (t,k),v in n.items() if k=='train')}, "
      f"test {sum(v for (t,k),v in n.items() if k=='test')}, "
      f"straddle dropped {sum(v for (t,k),v in n.items() if k=='straddle_dropped')}")
sides = collections.defaultdict(set)
for l in open(OUT):
    p = json.loads(l)
    for e in (p["better"], p["worse"]):
        sides[RUN[e]].add(p["intask_split"])
bad = sum(1 for v in sides.values() if len(v) > 1)
print(f"  verify: runs appearing on both sides = {bad} {'OK' if bad == 0 else 'BROKEN'}")
