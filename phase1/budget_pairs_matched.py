"""L2 data v2: COUNT-MATCHED budget labels.

The v1 label ("best graded score anywhere in the subtree within depth B") is confounded: a node
with a larger subtree has drawn more samples from the score distribution, so its max is higher
for mechanical reasons. Measured on the v1 flip set, subtree depth alone predicts the
unlimited-budget label at 0.879 -- the label was largely encoding which node MCTS chose to
expand more, not which node was more promising.

Here the budget is a COUNT of expansions, matched across the two nodes of a pair: value_K(c) =
best graded among c and the first K descendants of c in expansion order (lineage.step). Both
nodes of a pair must have at least K descendants, so neither gets more draws than the other.
That is also the question that is actually asked at decision time: given the SAME K more
steps, which node goes further.

Emits budget_pairs_matched.jsonl (training) and budget_flip_matched.jsonl (paired eval).
Usage: python phase1/budget_pairs_matched.py OUT_PAIRS OUT_FLIP cards.jsonl [--ks 1,2,3,5]
"""
import argparse, collections, itertools, json, random

ap = argparse.ArgumentParser()
ap.add_argument("out_pairs"); ap.add_argument("out_flip"); ap.add_argument("cards")
ap.add_argument("--ks", default="1,2,3,5")
ap.add_argument("--cap", type=int, default=6000, help="max pairs per (task,K) for training")
ap.add_argument("--flip-cap", type=int, default=1200, help="max flip pairs per task for eval")
ap.add_argument("--tau-filter", action="store_true",
                help="drop pairs whose value gap is below the task's measured noise floor")
ap.add_argument("--tau-quantile", type=float, default=0.9)
ap.add_argument("--flip-boost", type=int, default=1,
                help="repeat budget-flipping training records N times; only ~5%% of pairs carry "
                     "any budget signal at all, so at 1x the model sees almost none")
ap.add_argument("--seed", type=int, default=7)
a = ap.parse_args()
KS = [int(x) for x in a.ks.split(",")]
KLO, KHI = min(KS), max(KS)

# Measured noise floor per task: same container, K re-executions, external re-grading. A pair
# whose two values differ by less than this is not a preference, it is measurement noise -- 25%
# of birds pairs fall below it, and birds is where the model scores below chance.
TAU = {}
if a.tau_filter:
    import csv as _csv
    _t = collections.defaultdict(list)
    for _r in _csv.DictReader(open("phase1/regrade_tau_nodes.csv")):
        try:
            _t[_r["competition"]].append(float(_r["tau"]))
        except (ValueError, KeyError):
            pass
    for _k, _v in _t.items():
        _v.sort()
        TAU[_k] = _v[min(int(a.tau_quantile * len(_v)), len(_v) - 1)]
    print(f"[tau] loaded noise floors for {len(TAU)} tasks "
          f"(tasks without one are kept unfiltered)")

cards = {}
for l in open(a.cards):
    d = json.loads(l); cards[d["id"]] = d
ORI = json.load(open("phase1/task_orientation.json"))
kids = collections.defaultdict(list)
for cid, d in cards.items():
    p = d["lineage"].get("parent_id")
    if p: kids[p].append(cid)


def desc_in_order(cid):
    """All descendants, in the order the search actually expanded them."""
    out, stack, seen = [], list(kids.get(cid, [])), set()
    while stack:
        x = stack.pop()
        if x in seen or x not in cards: continue
        seen.add(x); out.append(x); stack.extend(kids.get(x, []))
    return sorted(out, key=lambda c: (cards[c]["lineage"].get("step") or 0, c))


root = {}
def tree_root(cid, g=0):
    if cid in root: return root[cid]
    p = cards.get(cid, {}).get("lineage", {}).get("parent_id")
    r = cid if (not p or p not in cards or g > 200) else tree_root(p, g + 1)
    root[cid] = r; return r


DESC = {cid: desc_in_order(cid) for cid in cards}
val = collections.defaultdict(dict)
for cid, d in cards.items():
    t = d["task"]["name"]
    if t not in ORI: continue
    pick = min if ORI[t] else max
    own = d["label"]["graded"]
    for K in KS:
        if len(DESC[cid]) < K: continue          # not enough realised expansions: undefined
        val[K][cid] = pick([own] + [cards[x]["label"]["graded"] for x in DESC[cid][:K]])

rng = random.Random(a.seed)
by_task = collections.defaultdict(list)
for cid in cards:
    if cid in val[KLO]: by_task[cards[cid]["task"]["name"]].append(cid)

npair = collections.Counter(); nflip = collections.Counter(); ndrop = collections.Counter()
fp = open(a.out_pairs, "w"); ff = open(a.out_flip, "w")
for t, cs in sorted(by_task.items()):
    lower = ORI[t]
    roots = sorted({tree_root(c) for c in cs}); rng.shuffle(roots)
    hold = set(roots[int(0.8 * len(roots)):])
    prs = list(itertools.combinations(cs, 2)); rng.shuffle(prs)

    def lab(x, y, K):
        if x not in val[K] or y not in val[K]: return None
        vx, vy = val[K][x], val[K][y]
        if vx == vy: return None
        return (x, y) if ((vx < vy) if lower else (vx > vy)) else (y, x)

    # Split BEFORE capping. Capping first then filtering to held-out trees leaves almost
    # nothing for the eval set: held-out trees are 20% of trees, so both-endpoints-held-out
    # is ~4% of pairs, and a 6k cap then yields a couple of hundred eval pairs.
    tr_prs = [p for p in prs if tree_root(p[0]) not in hold and tree_root(p[1]) not in hold]
    te_prs = [p for p in prs if tree_root(p[0]) in hold and tree_root(p[1]) in hold]
    flips, ctrl = [], []
    for x, y in tr_prs[:a.cap] + te_prs[:a.cap]:
        ref = lab(x, y, KLO)
        for K in KS:
            L = lab(x, y, K)
            if L is None: continue
            hi, lo = L
            both = tree_root(hi) in hold and tree_root(lo) in hold
            either = tree_root(hi) in hold or tree_root(lo) in hold
            if either and not both: continue                     # straddles the boundary: drop
            gap = abs(val[K][x] - val[K][y])
            clears = None if t not in TAU else gap >= TAU[t]
            if a.tau_filter and clears is False:
                ndrop[t] += 1
                continue
            is_flip = ref is not None and ref != L
            split = "test" if both else "train"
            rec = json.dumps({
                "task": t, "better": hi, "worse": lo, "budget": K,
                "flips_vs_b1": is_flip,
                "gap_raw": round(gap, 6),
                "intask_split": split,
                "loto_fold": t, "clears_tau": clears, "src": "budget_matched"})
            # Oversample the records that actually depend on the budget. Eval is untouched --
            # only the training side is reweighted, so the test distribution stays natural.
            reps = a.flip_boost if (is_flip and split == "train") else 1
            for _ in range(reps):
                fp.write(rec + "\n")
            npair[(K, split)] += reps
        # Paired eval, one set per budget gap. The gaps form a dose-response ladder: if budget
        # conditioning is real, the gain over the 0.500 blind baseline should grow with the gap.
        # Each gap is filtered independently -- requiring >= K_max everywhere would throw away
        # the pairs that only qualify for the smaller gaps.
        if tree_root(x) in hold and tree_root(y) in hold:
            for KHI_ in [k for k in KS if k > KLO]:
                L, H = lab(x, y, KLO), lab(x, y, KHI_)
                if L is None or H is None: continue
                rec = {"task": t, "x": x, "y": y, "budget_lo": KLO, "budget_hi": KHI_,
                       "better_lo": L[0], "better_hi": H[0],
                       "gap_lo": round(abs(val[KLO][x] - val[KLO][y]), 6),
                       "gap_hi": round(abs(val[KHI_][x] - val[KHI_][y]), 6),
                       "kind": "flip" if L != H else "control"}
                (flips if L != H else ctrl).append(rec)
    keep = collections.Counter()
    out = []
    for r in flips:                                   # cap flips per (task, gap)
        if keep[("f", r["budget_hi"])] < a.flip_cap:
            keep[("f", r["budget_hi"])] += 1; out.append(r)
    for r in ctrl:                                    # match control count per gap
        if keep[("c", r["budget_hi"])] < keep[("f", r["budget_hi"])]:
            keep[("c", r["budget_hi"])] += 1; out.append(r)
    for r in out: ff.write(json.dumps(r) + "\n")
    nflip[t] = sum(1 for r in out if r["kind"] == "flip")
fp.close(); ff.close()

for k in sorted(npair): print(f"  K={k[0]:>2} {k[1]:5s}: {npair[k]}")
if ndrop:
    print(f"[tau] dropped {sum(ndrop.values())} records below the noise floor: " + ", ".join(f"{k[:20]}={v}" for k, v in ndrop.most_common(6)))
print(f"[matched] {sum(npair.values())} training records -> {a.out_pairs}")
for t in sorted(nflip):
    if nflip[t]: print(f"  flip {t[:44]:44s} {nflip[t]}")
print(f"[matched] {sum(nflip.values())} flip + same controls -> {a.out_flip}")
