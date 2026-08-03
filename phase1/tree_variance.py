"""Lineage lumpiness, done right.

First attempt grouped by tree_root, but build_cards drops ungraded nodes, so lineages shatter
into fragments and the median "tree" had ONE node -- singleton groups have zero within-variance
by definition and mechanically inflate the between-group share. Two fixes:

  A. variance split restricted to fragments with >= 3 graded nodes (real groups only);
  B. parent-child Spearman on directly-linked graded pairs -- no grouping at all, so no
     fragment artifact: if knowing the parent's score pins the child's, lineage determines level.
"""
import collections, json

cards = {}
for l in open("phase1/cards_current.jsonl"):
    d = json.loads(l)
    cards[d["id"]] = d

root = {}
def tree_root(cid, g=0):
    if cid in root:
        return root[cid]
    p = cards.get(cid, {}).get("lineage", {}).get("parent_id")
    r = cid if (not p or p not in cards or g > 200) else tree_root(p, g + 1)
    root[cid] = r
    return r


def spearman(xs, ys):
    def rk(v):
        order = sorted(range(len(v)), key=lambda i: v[i])
        r = [0.0] * len(v)
        for i, j in enumerate(order):
            r[j] = i
        return r
    rx, ry = rk(xs), rk(ys)
    mx, my = sum(rx) / len(rx), sum(ry) / len(ry)
    num = sum((a - mx) * (b - my) for a, b in zip(rx, ry))
    dx = sum((a - mx) ** 2 for a in rx) ** 0.5
    dy = sum((b - my) ** 2 for b in ry) ** 0.5
    return num / (dx * dy) if dx and dy else float("nan")


by_task = collections.defaultdict(lambda: collections.defaultdict(list))
pc = collections.defaultdict(lambda: ([], []))
for cid, d in cards.items():
    t = d["task"]["name"]
    by_task[t][tree_root(cid)].append(d["label"]["graded"])
    p = d["lineage"].get("parent_id")
    if p in cards:
        pc[t][0].append(cards[p]["label"]["graded"])
        pc[t][1].append(d["label"]["graded"])

print(f"{'task':42s} {'frags>=3':>8} {'nodes':>6} {'btw-share':>10} {'par-child rho':>14} {'n_pairs':>8}")
print("-" * 96)
for t, trees in sorted(by_task.items(), key=lambda kv: -sum(len(v) for v in kv[1].values())):
    big = {k: v for k, v in trees.items() if len(v) >= 3}
    vals = [(v, k) for k, vs in big.items() for v in vs]
    share = float("nan")
    if len(vals) >= 40 and len(big) >= 4:
        order = sorted(range(len(vals)), key=lambda i: vals[i][0])
        rank = [0.0] * len(vals)
        for r_, i in enumerate(order):
            rank[i] = r_
        grp = collections.defaultdict(list)
        for i, (_, k) in enumerate(vals):
            grp[k].append(rank[i])
        gm = sum(rank) / len(rank)
        sst = sum((r_ - gm) ** 2 for r_ in rank)
        ssb = sum(len(rs) * ((sum(rs) / len(rs)) - gm) ** 2 for rs in grp.values())
        share = ssb / sst if sst else float("nan")
    xs, ys = pc[t]
    rho = spearman(xs, ys) if len(xs) >= 30 else float("nan")
    tot = sum(len(v) for v in trees.values())
    if tot < 100:
        continue
    print(f"{t[:42]:42s} {len(big):>8} {len(vals):>6} {share:>10.2f} {rho:>14.2f} {len(xs):>8}")
