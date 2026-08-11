"""Confirm what gap_raw measures on lookahead pairs, using a subset where the answer is forced.

Hypothesis: for a lookahead pair, better/worse is decided by what each node's SUBTREE
eventually reached, so gap_raw is a subtree-best margin -- a different quantity from the two
nodes' own scores, which is why it matches |graded diff| only 10% of the time.

The file carries `steps_to_best`: how far below each node its subtree's best sits. When both
entries are 0 the node IS its own subtree best, so under the hypothesis gap_raw must reduce
to |graded diff| on exactly that subset and on no other. If the match rate jumps to ~100%
there and stays low elsewhere, the hypothesis is confirmed and the correct stratifier for
lookahead pairs is gap_raw, not the own-score gap that gap_strat.py used.

Also recovers the ORDER: whether better/worse agrees with own graded, conditioned the same
way. Under the hypothesis, disagreement should be concentrated where steps_to_best > 0.
"""
import collections, json, math

ORI = json.load(open("phase1/task_orientation.json"))
G = {}
for l in open("phase1/cards_current_v8.jsonl"):
    d = json.loads(l)
    try:
        v = float(d.get("label", {}).get("graded"))
        G[d["id"]] = v if math.isfinite(v) else None
    except (TypeError, ValueError):
        G[d["id"]] = None

buckets = collections.defaultdict(lambda: [0, 0, 0])   # n, gap_match, order_ok
for l in open("phase1/value_pairs_runsplit.jsonl"):
    p = json.loads(l)
    b, w = p["better"], p["worse"]
    gb, gw = G.get(b), G.get(w)
    if gb is None or gw is None or gb == gw:
        continue
    try:
        gr = float(p["gap_raw"])
    except (TypeError, ValueError, KeyError):
        continue
    stb = p.get("steps_to_best")
    key = ("both 0" if stb == [0, 0] else
           "one 0" if isinstance(stb, list) and 0 in stb else
           "neither 0" if isinstance(stb, list) else "missing")
    v = buckets[key]
    v[0] += 1
    v[1] += int(abs(abs(gb - gw) - gr) < 1e-6)
    v[2] += int((gb < gw) if ORI.get(p["task"], False) else (gb > gw))

print(f"{'steps_to_best':14s} {'n':>7} {'gap_raw == |graded diff|':>26} "
      f"{'better has better own score':>29}")
for k in ("both 0", "one 0", "neither 0", "missing"):
    if k not in buckets:
        continue
    n, gm, ok = buckets[k]
    print(f"{k:14s} {n:7d} {gm/n:26.2%} {ok/n:29.2%}")
print("\nUnder the hypothesis: 'both 0' -> ~100% on both columns, everything else far below.")
print("If that is what prints, gap_raw is the subtree-best margin and IS the label margin,")
print("so it is the quantity to stratify on. The own-score gap is a different variable and")
print("stratifying on it mixes pairs whose labels are about entirely different comparisons.")
