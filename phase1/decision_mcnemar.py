"""Paired comparison on decision test pairs: self_report vs the lookahead RM (cell C hits).

McNemar on the 810 pairs where self_report is defined (both sides reported, distinct);
gap-quartile stratification of both scorers (is the RM only failing on hairline gaps?).

Usage: python phase1/decision_mcnemar.py
"""
import json, math

ORI = json.load(open("phase1/task_orientation.json"))
cards = {}
for l in open("phase1/cards_current.jsonl"):
    d = json.loads(l)
    cards[d["id"]] = d

hits = {}
gaps = {}
for l in open("phase1/hits_lookahead_on_decision.jsonl"):
    d = json.loads(l)
    k = (d["better"], d["worse"], d["budget"])
    hits[k] = d["hit"]
    gaps[k] = d.get("gap_raw") or 0.0
print(f"RM hits loaded: {len(hits)}")


def sr(cid):
    try:
        return float(cards[cid]["obs"].get("val_at_low"))
    except (TypeError, ValueError):
        return None


both = []          # (rm_hit, sr_hit, gap, budget)
rm_only = []       # pairs where SR undefined
for (b, w, K), h in hits.items():
    sb, sw = sr(b), sr(w)
    task = cards[b]["task"]["name"]
    if sb is None or sw is None or sb == sw:
        rm_only.append(h)
        continue
    s_hit = int((sb < sw) if ORI.get(task, False) else (sb > sw))
    both.append((h, s_hit, gaps[(b, w, K)], K))

n = len(both)
rm_acc = sum(x[0] for x in both) / n
sr_acc = sum(x[1] for x in both) / n
b01 = sum(1 for x in both if x[0] == 0 and x[1] == 1)   # SR right, RM wrong
b10 = sum(1 for x in both if x[0] == 1 and x[1] == 0)   # RM right, SR wrong
print(f"covered pairs n={n}: RM acc={rm_acc:.3f}  SR acc={sr_acc:.3f}")
print(f"discordant: SR-right/RM-wrong={b01}  RM-right/SR-wrong={b10}")
m = b01 + b10
if m:
    # two-sided exact binomial on the discordant pairs
    from math import comb
    k = min(b01, b10)
    p = sum(comb(m, i) for i in range(0, k + 1)) / 2 ** m * 2
    print(f"McNemar exact two-sided p = {min(p, 1.0):.2e}  (m={m})")
print(f"RM acc on the {len(rm_only)} SR-undefined pairs: "
      f"{sum(rm_only)/max(len(rm_only),1):.3f}")

qs = sorted(x[2] for x in both)
cuts = [qs[int(len(qs) * q)] for q in (0.25, 0.5, 0.75)]
print(f"\ngap_raw quartile cuts: {[round(c,4) for c in cuts]}")
print(f"{'quartile':10s} {'n':>5} {'RM':>7} {'SR':>7}")
for qi in range(4):
    lo = cuts[qi - 1] if qi > 0 else -1
    hi = cuts[qi] if qi < 3 else float('inf')
    sub = [x for x in both if lo < x[2] <= hi] if qi > 0 else [x for x in both if x[2] <= hi]
    if not sub:
        continue
    print(f"Q{qi+1:<9d} {len(sub):>5} {sum(x[0] for x in sub)/len(sub):>7.3f} "
          f"{sum(x[1] for x in sub)/len(sub):>7.3f}")

print(f"\nper-K on covered pairs:")
for K in (0, 1, 2):
    sub = [x for x in both if x[3] == K]
    if sub:
        print(f"  K={K}: n={len(sub)} RM={sum(x[0] for x in sub)/len(sub):.3f} "
              f"SR={sum(x[1] for x in sub)/len(sub):.3f}")
