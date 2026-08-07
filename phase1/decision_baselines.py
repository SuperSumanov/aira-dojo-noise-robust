"""Training-free baselines on the decision test pairs (sibling comparisons).

The decision table needs the L4-style comparison column: what does the search already
know at expansion time, with NO trained value model? Anything a trained RM adds must
clear these. Same 847 test pairs the trained arms scored (test side of
decision_pairs_v1.jsonl; the 900 cap never binds).

Baselines (per pair, better-vs-worse as labeled by the builder):
  self_report : agent's own validation claim (obs.val_at_low), task-orientation-aware
  code_len    : longer code wins (as-is; <0.5 just means shorter wins)
  runtime     : longer obs.runtime_s wins
  step_order  : later-generated sibling (lineage.step) wins
Ties/missing on either side -> pair skipped for that baseline; coverage reported.

Usage: python phase1/decision_baselines.py
"""
import collections, json, math

import sys
CARDS = "phase1/cards_current.jsonl"
PAIRS = sys.argv[1] if len(sys.argv) > 1 else "phase1/decision_pairs_v1.jsonl"
print("pairs file:", PAIRS)
ORI = json.load(open("phase1/task_orientation.json"))

cards = {}
for l in open(CARDS):
    d = json.loads(l)
    cards[d["id"]] = d

pairs = [json.loads(l) for l in open(PAIRS)]
test = [p for p in pairs if p["intask_split"] == "test"
        and p["better"] in cards and p["worse"] in cards]
print(f"decision test pairs: {len(test)}")


def sr(cid):
    v = cards[cid]["obs"].get("val_at_low")
    try:
        return float(v)
    except (TypeError, ValueError):
        return None


def feat(cid, name):
    d = cards[cid]
    if name == "self_report":
        return sr(cid)
    if name == "code_len":
        return float(len(d.get("code") or ""))
    if name == "runtime":
        v = d["obs"].get("runtime_s")
        try:
            return float(v)
        except (TypeError, ValueError):
            return None
    if name == "step_order":
        s = d["lineage"].get("step")
        return float(s) if s is not None else None


def acc_of(name, subset):
    """Fraction of pairs where 'higher feature' (orientation-aware for self_report)
    picks the labeled better sibling."""
    k = n = 0
    for p in subset:
        b, w = feat(p["better"], name), feat(p["worse"], name)
        if b is None or w is None or b == w:
            continue
        hi_wins = b > w
        if name == "self_report" and ORI.get(p["task"], False):  # lower-is-better task
            hi_wins = b < w
        k += int(hi_wins)
        n += 1
    return k, n


names = ["self_report", "code_len", "runtime", "step_order"]
print(f"\n{'baseline':12s} {'acc':>6} {'k/n':>10} {'cover':>6} {'se':>6}")
for name in names:
    k, n = acc_of(name, test)
    a = k / n if n else float("nan")
    se = math.sqrt(a * (1 - a) / n) if n else float("nan")
    print(f"{name:12s} {a:6.3f} {k:>4}/{n:<5} {n/len(test):6.1%} {se:6.3f}")

print("\nper-K (self_report):")
for K in (0, 1, 2):
    sub = [p for p in test if p["budget"] == K]
    k, n = acc_of("self_report", sub)
    print(f"  K={K}: {k}/{n} = {k/max(n,1):.3f}")

print("\nper-task self_report (n>=25 in test):")
byt = collections.defaultdict(list)
for p in test:
    byt[p["task"]].append(p)
for t in sorted(byt, key=lambda x: -len(byt[x])):
    if len(byt[t]) < 25:
        continue
    k, n = acc_of("self_report", byt[t])
    print(f"  {t[:42]:42s} {k:>3}/{n:<4} = {k/max(n,1):.3f}  (pairs={len(byt[t])})")
