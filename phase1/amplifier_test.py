"""The amplifier natural experiment: does removing MCTS selection reduce lineage lumpiness?

Mechanism under test (the pseudo-replication chapter): MCTS is a positive-feedback amplifier --
it commits budget to early winners, so runs collapse into few lineages whose identity carries
the score. The senior's sequential-expansion protocol removes selection from the generator.
Same model, same tasks, same grading; only the search policy differs.

Prediction fixed before looking: between-lineage share of within-task score-rank variance is
LOWER in sequential trees. Computed identically to phase1/tree_variance.py (fragments >= 3
graded nodes, rank-transformed within task x policy cell).

MCTS side uses the senior's deep-MCTS batches (0802-0804) so the regime (deep, conda, senior
accounts) matches everything except the policy. Tasks: the overlap with >= 40 graded cards on
both sides.
"""
import collections, json

SEQ = ["phase1/cards_senior_0805seq.jsonl"]
MCTS = ["phase1/cards_senior_0802.jsonl", "phase1/cards_senior_0803.jsonl",
        "phase1/cards_senior_0804.jsonl", "phase1/cards_deepA.jsonl",
        "phase1/cards_deepB2.jsonl"]


def load(files):
    cards = {}
    for f in files:
        try:
            for l in open(f):
                d = json.loads(l)
                cards[d["id"]] = d
        except FileNotFoundError:
            pass
    return cards


def between_share(cards):
    root = {}

    def tr(c, g=0):
        if c in root:
            return root[c]
        p = cards.get(c, {}).get("lineage", {}).get("parent_id")
        r = c if (not p or p not in cards or g > 200) else tr(p, g + 1)
        root[c] = r
        return r

    by = collections.defaultdict(lambda: collections.defaultdict(list))
    for cid, d in cards.items():
        by[d["task"]["name"]][tr(cid)].append(d["label"]["graded"])
    out = {}
    for t, trees in by.items():
        big = {k: v for k, v in trees.items() if len(v) >= 3}
        vals = [(v, k) for k, vs in big.items() for v in vs]
        if len(vals) < 40 or len(big) < 4:
            continue
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
        out[t] = (ssb / sst if sst else float("nan"), len(big), len(vals))
    return out


seq = between_share(load(SEQ))
mc = between_share(load(MCTS))
common = sorted(set(seq) & set(mc))
print(f"{'task':42s} {'MCTS share':>11} {'(frags,n)':>10} {'SEQ share':>10} {'(frags,n)':>10}")
print("-" * 92)
for t in common:
    m, s = mc[t], seq[t]
    print(f"{t[:42]:42s} {m[0]:>11.2f} {'(' + str(m[1]) + ',' + str(m[2]) + ')':>10} "
          f"{s[0]:>10.2f} {'(' + str(s[1]) + ',' + str(s[2]) + ')':>10}")
if common:
    dm = sum(mc[t][0] for t in common) / len(common)
    ds = sum(seq[t][0] for t in common) / len(common)
    print(f"\nmean between-lineage share on {len(common)} common tasks: "
          f"MCTS {dm:.2f} vs SEQUENTIAL {ds:.2f}")
    print("prediction (fixed in advance): SEQ < MCTS confirms the amplifier mechanism")
else:
    print("no common tasks with enough fragments yet -- needs more sequential data")
