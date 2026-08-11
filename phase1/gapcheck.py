"""Is the stratification variable the label margin, or something else?

The pair files carry their own `gap_raw`. gap_strat.py ignored it and recomputed
|graded(better) - graded(worse)| from the cards. If those two disagree, the whole
stratification is indexed on the wrong quantity: for value (lookahead) pairs the label is
defined by what the subtree eventually reached, not by the two nodes' own scores, so a pair
whose endpoints score identically can still carry a perfectly well-defined label -- and it
would land in the smallest-gap bucket and look like an anomaly.

That is exactly the shape of the anomaly in the first pass: bucket [0,1e-4) is the ONLY
small-gap bucket where the RM does not collapse (0.6346 on n=52). Before reading anything
into the collapse, check whether these are the same number.
"""
import json, math

def fin(x):
    try:
        v = float(x)
    except (TypeError, ValueError):
        return None
    return v if math.isfinite(v) else None

cards = {}
for l in open("phase1/cards_current_v8.jsonl"):
    d = json.loads(l)
    cards[d["id"]] = d

for name in ("hits_l1_uncapped.jsonl", "value_pairs_runsplit.jsonl",
             "decision_pairs_runsplit.jsonl"):
    n = same = miss = 0
    worst = []
    zero_raw = 0
    for l in open("phase1/" + name):
        p = json.loads(l)
        gr = fin(p.get("gap_raw"))
        b, w = p["better"], p["worse"]
        if b not in cards or w not in cards:
            miss += 1
            continue
        gb = fin(cards[b]["label"].get("graded"))
        gw = fin(cards[w]["label"].get("graded"))
        if gb is None or gw is None or gr is None:
            miss += 1
            continue
        mine = abs(gb - gw)
        n += 1
        if gr < 1e-9:
            zero_raw += 1
        d = abs(mine - gr)
        if d < 1e-6:
            same += 1
        else:
            worst.append((d, round(gr, 5), round(mine, 5), p["task"][:24]))
    worst.sort(reverse=True)
    print(f"\n{name}: comparable {n}, unusable {miss}")
    print(f"  gap_raw == |graded_b - graded_w| on {same}/{n} = {same/max(n,1):.2%}")
    print(f"  gap_raw exactly 0: {zero_raw}")
    if worst:
        print(f"  largest disagreements (|diff|, gap_raw, recomputed, task):")
        for x in worst[:6]:
            print(f"    {x}")
        # does the SIGN of the label agree with the recomputed order?
        print(f"  median |diff| among disagreeing: "
              f"{sorted(x[0] for x in worst)[len(worst)//2]:.6f}")
