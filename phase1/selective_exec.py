"""The experiment the critic was always for: skipping executions, not out-ranking a score
that only exists after you have already paid for it.

Every comparison so far pitted the critic against the agent's self-reported validation
score. The senior's objection is correct and it invalidates that framing: the self-report
exists only AFTER a candidate has been executed, and executing an ML script costs minutes to
hours while a critic forward pass costs seconds. The two signals are not available at the
same decision point, so ranking them head-to-head answers a question nobody needs answered.

The decision that actually matters: k candidate programs have been generated; execute which?
At that moment there is no self-report for any of them. The only signals are the code itself
and cheap structural features -- which is exactly the comparison where the critic already
wins decisively (0.647 vs 0.503, p=3e-21). That number was filed as a consolation prize; it
is the main result for this use case.

This scores the counterfactual offline. Our corpus executed every generated sibling, so for
each sibling set we know what every unexplored branch WOULD have produced:

  execute-all   : run all k, keep the best by self-report      cost k   (current practice)
  critic-top-1  : run only the critic's pick                   cost 1
  critic-top-2  : run its top two, keep the better self-report cost 2
  random-1/2    : the honest cheap baselines at the same cost
  oracle-1      : run only the truly best                      cost 1   (ceiling)

Reported as achieved grade normalised within each set, so tasks with different metrics
combine: 0 = worst sibling, 1 = best sibling. That makes "fraction of the achievable gain
captured per execution" the headline, which is what a compute-poor searcher buys.

Held-out runs only (runsplit_holdruns.json); CIs clustered by run.

Usage: python phase1/selective_exec.py SCORES.json
"""
import collections, json, math, random, statistics, sys

SCORES = sys.argv[1] if len(sys.argv) > 1 else "phase1/rm_scores_sibling.json"
ORI = json.load(open("phase1/task_orientation.json"))
RUN = json.load(open("phase1/card_run_map.json"))
HOLD = set(json.load(open("phase1/runsplit_holdruns.json")))
rm = {k: float(v) for k, v in json.load(open(SCORES)).items()}

cards = {}
for l in open("phase1/cards_current_v7.jsonl"):
    d = json.loads(l)
    cards[d["id"]] = d
kids = collections.defaultdict(list)
for cid, d in cards.items():
    p = d["lineage"].get("parent_id")
    if p:
        kids[p].append(cid)


def fin(x):
    try:
        v = float(x)
    except (TypeError, ValueError):
        return None
    return v if math.isfinite(v) else None


sets = []
for parent, ch in kids.items():
    ch = [c for c in ch if c in cards and c in rm]
    if len(ch) < 2:
        continue
    if any(RUN.get(c) not in HOLD for c in ch):
        continue                      # held-out runs only: the model never saw these
    t = cards[ch[0]]["task"]["name"]
    if t not in ORI:
        continue
    g = {c: fin(cards[c]["label"].get("graded")) for c in ch}
    s = {c: fin(cards[c]["obs"].get("val_at_low")) for c in ch}
    if any(g[c] is None for c in ch):
        continue
    sgn = -1.0 if ORI[t] else 1.0     # make "higher is better" uniform
    sets.append({"task": t, "run": RUN[ch[0]], "ch": ch,
                 "g": {c: sgn * g[c] for c in ch},
                 "s": {c: (None if s[c] is None else sgn * s[c]) for c in ch}})
print(f"sibling sets in held-out runs: {len(sets)} "
      f"over {len({x['run'] for x in sets})} runs, "
      f"{len({x['task'] for x in sets})} tasks")
ksz = collections.Counter(len(x["ch"]) for x in sets)
print(f"set sizes: {dict(sorted(ksz.items()))}")


def norm(v, lo, hi):
    return 0.5 if hi - lo < 1e-12 else (v - lo) / (hi - lo)


rng = random.Random(7)
POL = ["execute_all_sr", "critic_top1", "critic_top2", "random1", "random2",
       "oracle1", "codelen_top1"]
per_run = {p: collections.defaultdict(list) for p in POL}
cost = collections.Counter()
for S in sets:
    ch, g, s = S["ch"], S["g"], S["s"]
    lo, hi = min(g.values()), max(g.values())
    order_rm = sorted(ch, key=lambda c: -rm[c])
    order_len = sorted(ch, key=lambda c: -len(cards[c].get("code") or ""))

    def by_sr(sub):
        """what you keep after executing `sub`: the best self-report among them,
        falling back to an arbitrary member when none reported a score."""
        have = [c for c in sub if s[c] is not None]
        return max(have, key=lambda c: s[c]) if have else sub[0]

    picks = {
        "execute_all_sr": (by_sr(ch), len(ch)),
        "critic_top1": (order_rm[0], 1),
        "critic_top2": (by_sr(order_rm[:2]), 2),
        "random1": (rng.choice(ch), 1),
        "random2": (by_sr(rng.sample(ch, 2)), 2),
        "oracle1": (max(ch, key=lambda c: g[c]), 1),
        "codelen_top1": (order_len[0], 1),
    }
    for p, (c, k) in picks.items():
        per_run[p][S["run"]].append(norm(g[c], lo, hi))
        cost[p] += k

nsets = len(sets)


def boot(d, nb=3000, seed=7):
    runs = list(d)
    r = random.Random(seed)
    out = []
    for _ in range(nb):
        vals = [v for x in (r.choice(runs) for _ in runs) for v in d[x]]
        out.append(sum(vals) / len(vals))
    out.sort()
    return out[int(.025 * nb)], out[int(.975 * nb)]


print(f"\n{'policy':16s} {'exec/set':>9} {'captured':>9} {'95% CI (run-clustered)':>24}")
print("-" * 64)
res = {}
for p in POL:
    vals = [v for vs in per_run[p].values() for v in vs]
    m = statistics.mean(vals)
    lo, hi = boot(per_run[p])
    res[p] = m
    print(f"{p:16s} {cost[p]/nsets:9.2f} {m:9.4f}   [{lo:.4f}, {hi:.4f}]")

print(f"\nthe question this answers: at ONE execution per set, does reading the code beat")
print(f"guessing?  critic_top1 {res['critic_top1']:.4f} vs random1 {res['random1']:.4f} "
      f"(delta {res['critic_top1']-res['random1']:+.4f})")
# paired by run, because the two policies act on the very same sets
d = {r: [a - b for a, b in zip(per_run["critic_top1"][r], per_run["random1"][r])]
     for r in per_run["critic_top1"]}
lo, hi = boot(d)
mean_d = statistics.mean([v for vs in d.values() for v in vs])
print(f"paired delta {mean_d:+.4f}, run-clustered 95% CI [{lo:+.4f}, {hi:+.4f}] "
      f"-> {'SIGNIFICANT' if lo > 0 else 'not resolved'}")
print(f"\ncost-quality: execute-all buys {res['execute_all_sr']:.4f} for "
      f"{cost['execute_all_sr']/nsets:.2f} executions; critic_top1 buys "
      f"{res['critic_top1']:.4f} for 1.00.")
if res["execute_all_sr"] > res["critic_top1"]:
    saved = (cost["execute_all_sr"] / nsets) - 1.0
    lost = res["execute_all_sr"] - res["critic_top1"]
    print(f"  trade: {saved:.2f} executions saved per set for {lost:.4f} of the "
          f"achievable gain given up.")
print("\nper task (captured at 1 execution):")
bt = collections.defaultdict(lambda: collections.defaultdict(list))
for S, in zip(sets):
    pass
for p in ("critic_top1", "random1", "oracle1"):
    pass
tt = collections.defaultdict(lambda: [[], []])
for S in sets:
    ch, g = S["ch"], S["g"]
    lo_, hi_ = min(g.values()), max(g.values())
    c_rm = max(ch, key=lambda c: rm[c])
    tt[S["task"]][0].append(norm(g[c_rm], lo_, hi_))
    tt[S["task"]][1].append(norm(g[rng.choice(ch)], lo_, hi_))
for t, (a, b) in sorted(tt.items(), key=lambda kv: -len(kv[1][0])):
    if len(a) >= 15:
        print(f"  {t[:42]:42s} n={len(a):4d}  critic {statistics.mean(a):.3f}  "
              f"random {statistics.mean(b):.3f}  delta {statistics.mean(a)-statistics.mean(b):+.3f}")
