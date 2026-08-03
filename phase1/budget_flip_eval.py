"""L2 eval set: BUDGET-FLIP pairs (+ matched non-flip controls).

A flip pair is a node pair whose lookahead label under a 1-step budget is the OPPOSITE of its
label under the unlimited-subtree budget: "who looks better if we stop now" vs "who leads
somewhere better eventually" disagree. On such pairs a budget-BLIND model scores exactly 0.500
by construction -- it sees the same two inputs twice and the two labels are opposite -- so 0.5
here is an analytic baseline, not an empirical one. Only a model that reads the budget can beat it.

Control pairs keep the SAME label at both budgets. A model that flips its preference there is
just noisy rather than budget-aware, so the control flip-rate is the false-positive channel.

Holdout replicates budget_pairs.py exactly (same seed, same tree-level 80/20, both endpoints
in holdout), so this eval set never touches a tree the model trained on.

Usage: python phase1/budget_flip_eval.py out.jsonl cards.jsonl [--lo 1] [--hi 0] [--cap 800]
"""
import argparse, collections, itertools, json, random

ap = argparse.ArgumentParser()
ap.add_argument("out"); ap.add_argument("cards")
ap.add_argument("--lo", type=int, default=1, help="tight budget (steps)")
ap.add_argument("--hi", type=int, default=0, help="loose budget (0 = unlimited subtree)")
ap.add_argument("--cap", type=int, default=800, help="max flip pairs per task (controls matched)")
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

val = collections.defaultdict(dict)
sub = {cid: subtree(cid) for cid in cards}
for cid, d in cards.items():
    t = d["task"]["name"]
    if t not in ORI: continue
    pick = min if ORI[t] else max
    own = d["label"]["graded"]
    for B in (a.lo, a.hi):
        ds = [x for x, dist in sub[cid] if x in cards and (B == 0 or dist <= B)]
        if not ds: continue
        val[B][cid] = pick([own] + [cards[x]["label"]["graded"] for x in ds])

rng = random.Random(a.seed)
by_task = collections.defaultdict(list)
for cid in cards:
    t = cards[cid]["task"]["name"]
    if any(cid in val[B] for B in (a.lo, a.hi)): by_task[t].append(cid)

nf, nc = collections.Counter(), collections.Counter()
with open(a.out, "w") as f:
    for t, cs in sorted(by_task.items()):
        lower = ORI[t]
        # The holdout must be byte-identical to budget_pairs.py's, or "held-out" trees here
        # could be trees the model trained on. That means consuming the shared rng stream the
        # same way: shuffle the FULL pair list (not just holdout pairs) even though we then
        # keep only the holdout ones -- a shorter shuffle would desync every later task.
        roots = sorted({tree_root(c) for c in cs}); rng.shuffle(roots)
        hold = set(roots[int(0.8 * len(roots)):])
        prs = list(itertools.combinations(cs, 2)); rng.shuffle(prs)
        prs = [(x, y) for x, y in prs if tree_root(x) in hold and tree_root(y) in hold]

        def lab(x, y, B):
            if x not in val[B] or y not in val[B]: return None
            vx, vy = val[B][x], val[B][y]
            if vx == vy: return None
            return (x, y) if ((vx < vy) if lower else (vx > vy)) else (y, x)

        flips, ctrl = [], []
        for x, y in prs:
            L, H = lab(x, y, a.lo), lab(x, y, a.hi)
            if L is None or H is None: continue
            rec = {"task": t, "x": x, "y": y,
                   "budget_lo": a.lo, "budget_hi": a.hi,
                   "better_lo": L[0], "better_hi": H[0],
                   "gap_lo": round(abs(val[a.lo][x] - val[a.lo][y]), 6),
                   "gap_hi": round(abs(val[a.hi][x] - val[a.hi][y]), 6)}
            if L != H:
                rec["kind"] = "flip"; flips.append(rec)
            elif len(ctrl) < a.cap:
                rec["kind"] = "control"; ctrl.append(rec)
            if len(flips) >= a.cap and len(ctrl) >= a.cap: break
        ctrl = ctrl[:len(flips)] if flips else []
        for r in flips + ctrl:
            f.write(json.dumps(r) + "\n")
        nf[t] = len(flips); nc[t] = len(ctrl)

for t in sorted(nf):
    if nf[t]: print(f"  {t[:44]:44s} flip={nf[t]:5d} control={nc[t]:5d}")
print(f"[flip_eval] {sum(nf.values())} flip + {sum(nc.values())} control -> {a.out}")
