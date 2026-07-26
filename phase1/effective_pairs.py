"""Effective-pairs v0: same-task graded pairs whose raw-score gap clears the task noise floor.
Floor = 2 * max(p90_tau, 1e-9) from regrade_tau_nodes.csv (tau-measured tasks only; others 'pending').
Usage: python phase1/effective_pairs.py <cards.jsonl> [more.jsonl ...]"""
import csv, json, sys, collections, itertools

taus = collections.defaultdict(list)
for r in csv.DictReader(open("phase1/regrade_tau_nodes.csv")):
    if r["tau"]:
        taus[r["competition"]].append(float(r["tau"]))
floor = {}
for t, v in taus.items():
    v = sorted(v)
    floor[t] = 2 * max(v[int(0.9 * (len(v) - 1))], 1e-9)

cards = collections.defaultdict(list)
for path in sys.argv[1:]:
    for l in open(path):
        d = json.loads(l)
        task = (d.get("task") or {}).get("name")
        g = (d.get("label") or {}).get("graded")
        if task and g is not None:
            cards[task].append(g)

print(f"{'task':44s} {'n':>4} {'pairs':>7} {'effective':>9} {'eff%':>6} {'floor':>9}")
tot_p = tot_e = 0
for t, gs in sorted(cards.items(), key=lambda kv: -len(kv[1])):
    n = len(gs)
    pairs = n * (n - 1) // 2
    if t in floor:
        f = floor[t]
        eff = sum(1 for a, b in itertools.combinations(gs, 2) if abs(a - b) > f)
        print(f"{t[:44]:44s} {n:4d} {pairs:7d} {eff:9d} {100*eff/max(pairs,1):5.1f}% {f:9.4g}")
        tot_p += pairs; tot_e += eff
    else:
        print(f"{t[:44]:44s} {n:4d} {pairs:7d} {'pending':>9} {'':>6} {'no-tau':>9}")
print(f"TOTAL (tau-measured tasks): pairs={tot_p} effective={tot_e} ({100*tot_e/max(tot_p,1):.1f}%)")
