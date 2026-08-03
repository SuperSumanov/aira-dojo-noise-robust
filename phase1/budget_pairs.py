"""L2 data: BUDGET-CONDITIONED lookahead pairs.

Same node pair, evaluated under several budgets B. The label (who leads to the better solution)
is recomputed per budget from the tree, so the SAME pair can flip as B grows. The budget is
emitted as an explicit field so the model can be conditioned on it.

Emits one record per (pair, budget). Tree-level split. Also marks `flips_vs_b1`: whether this
pair's label at this budget differs from its label at B=1 -- the subset that a budget-blind
model cannot get right for all budgets simultaneously.

Usage: python phase1/budget_pairs.py out.jsonl cards.jsonl [--budgets 1,2,3,5,0] [--cap 6000]
"""
import argparse, collections, itertools, json, random

ap = argparse.ArgumentParser()
ap.add_argument("out"); ap.add_argument("cards")
ap.add_argument("--budgets", default="1,2,3,5,0", help="0 = unlimited subtree")
ap.add_argument("--cap", type=int, default=6000, help="max pairs per (task,budget)")
ap.add_argument("--seed", type=int, default=7)
a = ap.parse_args()

cards = {}
for l in open(a.cards):
    d = json.loads(l); cards[d["id"]] = d
ORI = json.load(open("phase1/task_orientation.json"))
kids = collections.defaultdict(list)
for cid, d in cards.items():
    p = d["lineage"].get("parent_id")
    if p: kids[p].append(cid)

def subtree(cid):
    out, stack, seen = [], [(k, 1) for k in kids.get(cid, [])], set()
    while stack:
        x, dist = stack.pop()
        if x in seen: continue
        seen.add(x); out.append((x, dist))
        stack.extend((k, dist + 1) for k in kids.get(x, []))
    return out

root = {}
def tree_root(cid, g=0):
    if cid in root: return root[cid]
    p = cards.get(cid, {}).get("lineage", {}).get("parent_id")
    r = cid if (not p or p not in cards or g > 200) else tree_root(p, g + 1)
    root[cid] = r; return r

BUDGETS = [int(x) for x in a.budgets.split(",")]
# value(node, budget) for every budget
val = collections.defaultdict(dict)
sub = {cid: subtree(cid) for cid in cards}
for cid, d in cards.items():
    t = d["task"]["name"]
    if t not in ORI: continue
    lower = ORI[t]; pick = min if lower else max
    own = d["label"]["graded"]
    for B in BUDGETS:
        ds = [x for x, dist in sub[cid] if x in cards and (B == 0 or dist <= B)]
        if not ds: continue
        val[B][cid] = pick([own] + [cards[x]["label"]["graded"] for x in ds])

rng = random.Random(a.seed)
by_task = collections.defaultdict(list)
for cid in cards:
    t = cards[cid]["task"]["name"]
    if any(cid in val[B] for B in BUDGETS): by_task[t].append(cid)

n = collections.Counter()
with open(a.out, "w") as f:
    for t, cs in sorted(by_task.items()):
        lower = ORI[t]
        roots = sorted({tree_root(c) for c in cs}); rng.shuffle(roots)
        hold = set(roots[int(0.8 * len(roots)):])
        prs = list(itertools.combinations(cs, 2)); rng.shuffle(prs); prs = prs[:a.cap]
        for x, y in prs:
            # label at B=1 (reference for flip detection)
            def lab(B):
                if x not in val[B] or y not in val[B]: return None
                vx, vy = val[B][x], val[B][y]
                if vx == vy: return None
                return (x, y) if ((vx < vy) if lower else (vx > vy)) else (y, x)
            ref = lab(1)
            for B in BUDGETS:
                L = lab(B)
                if L is None: continue
                hi, lo = L
                split = "test" if (tree_root(hi) in hold and tree_root(lo) in hold) else \
                        ("drop" if (tree_root(hi) in hold or tree_root(lo) in hold) else "train")
                if split == "drop": continue
                f.write(json.dumps({
                    "task": t, "better": hi, "worse": lo, "budget": B,
                    "flips_vs_b1": (ref is not None and ref != L),
                    "gap_raw": round(abs(val[B][x] - val[B][y]), 6),
                    "intask_split": split, "loto_fold": t,
                    "clears_tau": None, "src": "budget"}) + "\n")
                n[(B, split)] += 1
for k in sorted(n): print(f"  budget={k[0]:>2} {k[1]:5s}: {n[k]}")
print(f"[budget_pairs] {sum(n.values())} records -> {a.out}")
