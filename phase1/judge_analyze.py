"""Score the LLM judge and emit it as a suite member.

Pairwise LLM judging has a known position bias, so every pair was asked in both orders.
Three numbers matter and all three are reported: order-averaged accuracy (the headline),
the consistency rate between the two orders (a reliability diagnostic -- a judge that flips
when you swap A and B is not measuring the code), and the accuracy restricted to pairs
where the two orders agree (what you would get from a self-consistency filter, at double
the query cost).

Also dumps a per-node score file so predictor_suite.py can pick the judge up in the same
table as everything else: a node's score is the fraction of its comparisons it won.

Usage: python phase1/judge_analyze.py judge_code.jsonl [--dump phase1/judge_scores.json]
"""
import argparse, collections, json, math, random

ap = argparse.ArgumentParser()
ap.add_argument("hits")
ap.add_argument("--dump", default="")
a = ap.parse_args()

rows = [json.loads(l) for l in open(a.hits)]
print(f"calls: {len(rows)}")
parsed = [r for r in rows if r.get("correct") is not None]
trunc = sum(1 for r in rows if r.get("truncated"))
print(f"parsed: {len(parsed)} ({len(parsed)/len(rows):.1%}), "
      f"answer recovered from a cut-off trace: {trunc}")

by_pair = collections.defaultdict(dict)
for r in parsed:
    by_pair[(r["better"], r["worse"])][r["order"]] = r
both = {k: v for k, v in by_pair.items() if len(v) == 2}
print(f"pairs with both orders: {len(both)} / {len(by_pair)}")

# order-averaged: 1.0 both right, 0.5 split, 0.0 both wrong
per_run, cons, agree_only = collections.defaultdict(list), [], collections.defaultdict(list)
for k, v in both.items():
    c0, c1 = v[0]["correct"], v[1]["correct"]
    run = v[0]["run"]
    per_run[run].append((c0 + c1) / 2.0)
    consistent = (c0 == c1)
    cons.append(int(consistent))
    if consistent:
        agree_only[run].append(float(c0))


def boot(d, nb=4000, seed=7):
    runs = list(d)
    r = random.Random(seed)
    out = []
    for _ in range(nb):
        vals = [x for q in (r.choice(runs) for _ in runs) for x in d[q]]
        out.append(sum(vals) / len(vals))
    out.sort()
    return out[int(.025 * nb)], out[int(.975 * nb)]


vals = [x for vs in per_run.values() for x in vs]
acc = sum(vals) / len(vals)
lo, hi = boot(per_run)
print(f"\norder-averaged accuracy: {acc:.4f}  run-clustered 95% CI [{lo:.4f}, {hi:.4f}] "
      f"({len(per_run)} runs, {len(vals)} pairs)")
print(f"order consistency: {sum(cons)/len(cons):.3f}  "
      f"(a coin-flipping judge would sit at 0.50)")
av = [x for vs in agree_only.values() for x in vs]
if av:
    alo, ahi = boot(agree_only)
    print(f"accuracy on order-consistent pairs only: {sum(av)/len(av):.4f} "
          f"[{alo:.4f}, {ahi:.4f}]  n={len(av)}  (self-consistency filter, 2x query cost)")

# position bias: how often does it pick the FIRST option regardless of truth
firstpick = 0
for k, v in both.items():
    for o in (0, 1):
        r = v[o]
        chose_first = (r["correct"] == 1) == (o == 0)
        firstpick += int(chose_first)
print(f"picks the first-listed option: {firstpick/(2*len(both)):.3f} "
      f"(0.50 = unbiased)")

byt = collections.defaultdict(lambda: [0.0, 0])
for k, v in both.items():
    byt[v[0]["task"]][0] += (v[0]["correct"] + v[1]["correct"]) / 2.0
    byt[v[0]["task"]][1] += 1
print("\nper task:")
for t, (s, n) in sorted(byt.items(), key=lambda kv: -kv[1][1]):
    if n >= 10:
        print(f"  {t[:44]:44s} {s:6.1f}/{n:<4d} = {s/n:.3f}")

if a.dump:
    wins = collections.defaultdict(lambda: [0.0, 0])
    for k, v in both.items():
        b, w = k
        s = (v[0]["correct"] + v[1]["correct"]) / 2.0
        wins[b][0] += s
        wins[b][1] += 1
        wins[w][0] += (1 - s)
        wins[w][1] += 1
    json.dump({c: s / n for c, (s, n) in wins.items() if n}, open(a.dump, "w"))
    print(f"\ndumped {len(wins)} node scores -> {a.dump}")
