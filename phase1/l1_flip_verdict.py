"""Direction A entry ticket: run-clean strict-flip accuracy of the L1 runsplit model.

The 08-06 critique doc's claim: on pairs where future value disagrees with current
quality (flips), every current-quality proxy fails by construction, so the trained RM is
the only usable signal -- IF its flip accuracy survives a leak-free split. This computes
that number from l1run's per-pair hits (value_pairs_runsplit is run-level clean by
construction, so every eval pair here is 'strict').

Cluster bootstrap is by RUN (card_run_map.json), one level stricter than the doc's
by-tree advice: 3000 pairs come from ~100 held runs, pair-level CIs would be fake-narrow.

Also reports the free competitors and the structural baselines on the same slices, and
the per-K decision-side context is NOT recomputed here (see sibling_flips.py).

Usage: python phase1/l1_flip_verdict.py
"""
import collections, json, math, random

cards = {}
for l in open("phase1/cards_current.jsonl"):
    d = json.loads(l)
    cards[d["id"]] = d
RUN = json.load(open("phase1/card_run_map.json"))
ORI = json.load(open("phase1/task_orientation.json"))

flip_flag = {}
subtree = {}
for l in open("phase1/value_pairs_runsplit.jsonl"):
    p = json.loads(l)
    if p["intask_split"] != "test":
        continue
    k = (p["better"], p["worse"])
    flip_flag[k] = (p.get("agrees_with_quality") is False)
    ss = p.get("subtree_sizes")
    subtree[k] = tuple(ss) if isinstance(ss, (list, tuple)) and len(ss) == 2 else None

rows = []
for l in open("phase1/hits_l1_runsplit.jsonl"):
    h = json.loads(l)
    k = (h["better"], h["worse"])
    if k not in flip_flag or h["better"] not in cards:
        continue
    rows.append({"k": k, "hit": h["hit"], "flip": flip_flag[k],
                 "task": h["task"], "run": RUN.get(h["better"])})
print(f"scored eval pairs joined: {len(rows)} "
      f"(flips {sum(r['flip'] for r in rows)}, "
      f"{sum(r['flip'] for r in rows)/max(len(rows),1):.1%})")


def sr_hit(b, w, task):
    try:
        sb = float(cards[b]["obs"].get("val_at_low"))
        sw = float(cards[w]["obs"].get("val_at_low"))
    except (TypeError, ValueError):
        return None
    if sb == sw:
        return None
    return int((sb < sw) if ORI.get(task, False) else (sb > sw))


def boot_ci(sub, n=2000, seed=7):
    """Cluster bootstrap over RUNS."""
    by = collections.defaultdict(list)
    for r in sub:
        by[r["run"]].append(r["hit"])
    runs = list(by)
    rng = random.Random(seed)
    draws = []
    for _ in range(n):
        vals = [v for x in (rng.choice(runs) for _ in runs) for v in by[x]]
        draws.append(sum(vals) / len(vals))
    draws.sort()
    return draws[int(0.025 * n)], draws[int(0.975 * n)], len(runs)


print(f"\n{'slice':10s} {'n':>6} {'RM':>7} {'95% CI (run-clustered)':>24} {'SR':>7} {'subtree':>8}")
print("-" * 72)
for name, sel in (("ALL", lambda r: True),
                  ("AGREE", lambda r: not r["flip"]),
                  ("FLIP", lambda r: r["flip"])):
    sub = [r for r in rows if sel(r)]
    if not sub:
        continue
    acc = sum(r["hit"] for r in sub) / len(sub)
    lo, hi, nruns = boot_ci(sub)
    srs = [sr_hit(*r["k"], r["task"]) for r in sub]
    srs = [s for s in srs if s is not None]
    sts = [(1 if subtree[r["k"]][0] > subtree[r["k"]][1] else 0)
           for r in sub if subtree.get(r["k"]) and subtree[r["k"]][0] != subtree[r["k"]][1]]
    print(f"{name:10s} {len(sub):>6} {acc:>7.4f} [{lo:.4f}, {hi:.4f}] ({nruns} runs)"
          f" {sum(srs)/max(len(srs),1):>7.3f} {sum(sts)/max(len(sts),1):>8.3f}")

flips = [r for r in rows if r["flip"]]
if flips:
    k = sum(r["hit"] for r in flips)
    n = len(flips)
    from math import comb
    p1 = sum(comb(n, i) for i in range(k, n + 1)) / 2 ** n
    print(f"\nFLIP one-sided binomial vs 0.5 (pair-level, anti-conservative): p={p1:.2e}")
    print("the quotable test is the run-clustered CI above: lower bound > 0.5 -> Direction A lives")

per = collections.defaultdict(lambda: [0, 0])
for r in flips:
    per[r["task"]][0] += r["hit"]
    per[r["task"]][1] += 1
print("\nFLIP per task:")
for t, (a, b) in sorted(per.items(), key=lambda kv: -kv[1][1]):
    print(f"  {t[:42]:42s} {a:>4}/{b:<4} = {a/b:.3f}")
