"""Decision-aligned pairs: train on the comparisons the search actually faces.

The senior's critique, verbatim in spirit: training enumerates random pairs from the whole
pool, but deployment ranks nodes DURING tree growth -- the two must align before "does training
help" means anything. The decision a value model faces at consultation time is: children of one
parent, at the moment of expansion. Those pairs are the training and eval distribution here.

Construction:
  decision set  = graded children of a common parent (>= 2 of them)
  label         = count-matched lookahead within the set: value_K(child) = best graded among
                  the child and its first K descendants in expansion order; both children must
                  have >= K descendants (K=0 means own score only, always defined)
  pair          = every within-set pair whose values differ
  split         = by tree, both endpoints in the same side (the standing rule)

K=0 sets double as the "rank siblings by their own eventual score" task; K>=1 sets ask the
deployment question proper ("which child leads somewhere better").

Usage: python phase1/decision_pairs.py OUT cards.jsonl [--ks 0,1,2] [--seed 7]
"""
import argparse, collections, itertools, json, random
from pathlib import Path

ap = argparse.ArgumentParser()
ap.add_argument("out"); ap.add_argument("cards")
ap.add_argument("--ks", default="0,1,2")
ap.add_argument("--seed", type=int, default=7)
ap.add_argument("--orientation", default=str(Path(__file__).resolve().parents[4] / "data" / "mle_critic" / "task_orientation.json"))
a = ap.parse_args()
KS = [int(x) for x in a.ks.split(",")]

cards = {}
for l in open(a.cards):
    d = json.loads(l)
    cards[d["id"]] = d
ORI = json.load(open(a.orientation))
kids = collections.defaultdict(list)
for cid, d in cards.items():
    p = d["lineage"].get("parent_id")
    if p:
        kids[p].append(cid)


def desc_in_order(cid):
    out, st, seen = [], list(kids.get(cid, [])), set()
    while st:
        x = st.pop()
        if x in seen or x not in cards:
            continue
        seen.add(x)
        out.append(x)
        st.extend(kids.get(x, []))
    return sorted(out, key=lambda c: (cards[c]["lineage"].get("step") or 0, c))


root = {}
def tree_root(cid, g=0):
    if cid in root:
        return root[cid]
    p = cards.get(cid, {}).get("lineage", {}).get("parent_id")
    r = cid if (not p or p not in cards or g > 200) else tree_root(p, g + 1)
    root[cid] = r
    return r


DESC = {c: desc_in_order(c) for c in cards}


def val(cid, K):
    if K == 0:
        return cards[cid]["label"]["graded"]
    if len(DESC[cid]) < K:
        return None
    t = cards[cid]["task"]["name"]
    pick = min if ORI.get(t, False) else max
    return pick([cards[cid]["label"]["graded"]] +
                [cards[x]["label"]["graded"] for x in DESC[cid][:K]])


rng = random.Random(a.seed)
by_task_roots = collections.defaultdict(set)
for cid in cards:
    t = cards[cid]["task"]["name"]
    if t in ORI:
        by_task_roots[t].add(tree_root(cid))
hold = {}
for t, roots in by_task_roots.items():
    rs = sorted(roots)
    rng.shuffle(rs)
    hold[t] = set(rs[int(0.8 * len(rs)):])

n = collections.Counter()
sets_seen = collections.Counter()
with open(a.out, "w") as f:
    for parent, ch in kids.items():
        ch = [c for c in ch if c in cards]
        if len(ch) < 2:
            continue
        t = cards[ch[0]]["task"]["name"]
        if t not in ORI:
            continue
        lower = ORI[t]
        sides_ = {tree_root(c) in hold[t] for c in ch}
        if len(sides_) > 1:
            n["__dropped_cross_fragment_sets__", -1, "drop"] += 1
            continue
        in_hold = sides_.pop()
        split = "test" if in_hold else "train"
        sets_seen[(t, split)] += 1
        for K in KS:
            for x, y in itertools.combinations(ch, 2):
                vx, vy = val(x, K), val(y, K)
                if vx is None or vy is None or vx == vy:
                    continue
                hi, lo = (x, y) if ((vx < vy) if lower else (vx > vy)) else (y, x)
                f.write(json.dumps({
                    "task": t, "better": hi, "worse": lo, "budget": K,
                    "parent": parent, "set_size": len(ch),
                    "gap_raw": round(abs(vx - vy), 6),
                    "intask_split": split, "loto_fold": t,
                    "clears_tau": None, "src": "decision"}) + "\n")
                n[(t[:20], K, split)] += 1

tot = sum(n.values())
print(f"[decision_pairs] {tot} pairs -> {a.out}")
per_split = collections.Counter()
for (t, K, s), v in n.items():
    per_split[(K, s)] += v
for k in sorted(per_split):
    print(f"  K={k[0]} {k[1]:5s}: {per_split[k]}")
top = collections.Counter()
for (t, K, s), v in n.items():
    top[t] += v
print("  by task:", dict(top.most_common(8)))
print("  decision sets:", dict(collections.Counter(s for (_, s) in sets_seen)),
      "total", sum(sets_seen.values()))
