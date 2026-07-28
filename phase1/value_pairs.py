"""Node-VALUE pairs: "which node leads to a better solution" (vs "which node is better now").

Label for a node = best graded score in its subtree (its own score included), optionally limited to
descendants reachable within a budget (extra steps / extra exec seconds). Pairs are same-task; each
record carries the now-labels too, so the "does it disagree with quality ranking" split is free.
Usage: python phase1/value_pairs.py out.jsonl cards.jsonl [--budget-steps 0] [--cap 20000]
"""
import argparse, collections, itertools, json, random

ap = argparse.ArgumentParser()
ap.add_argument("out"); ap.add_argument("cards")
ap.add_argument("--budget-steps", type=int, default=0, help="0 = whole subtree; else max step distance")
ap.add_argument("--cap", type=int, default=20000)
ap.add_argument("--seed", type=int, default=7)
ap.add_argument("--split-by", choices=["card", "tree"], default="tree")
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
    """(descendant_id, step_distance) reachable from cid."""
    out, stack, seen = [], [(k, 1) for k in kids.get(cid, [])], set()
    while stack:
        x, dist = stack.pop()
        if x in seen: continue
        seen.add(x); out.append((x, dist))
        stack.extend((k, dist + 1) for k in kids.get(x, []))
    return out

val = {}
for cid, d in cards.items():
    t = d["task"]["name"]
    if t not in ORI: continue
    lower = ORI[t]; better = min if lower else max
    ds = [(x, dist) for x, dist in subtree(cid) if x in cards
          and (a.budget_steps == 0 or dist <= a.budget_steps)]
    own = d["label"]["graded"]
    if not ds: continue
    bd = better([own] + [cards[x]["label"]["graded"] for x, _ in ds])
    dist_to_best = min([dist for x, dist in ds if cards[x]["label"]["graded"] == bd] or [0])
    val[cid] = (t, own, bd, len(ds), dist_to_best)

by = collections.defaultdict(list)
for cid, v in val.items(): by[v[0]].append((cid,) + v[1:])
rng = random.Random(a.seed)
n = 0
with open(a.out, "w") as f:
    for t, v in sorted(by.items()):
        lower = ORI[t]
        prs = [(x, y) for x, y in itertools.combinations(v, 2) if x[2] != y[2]]
        rng.shuffle(prs); prs = prs[:a.cap]
        if a.split_by == "tree":
            root = {}
            def tree_root(cid, guard=0):
                if cid in root: return root[cid]
                p = cards.get(cid, {}).get("lineage", {}).get("parent_id")
                r = cid if (not p or p not in cards or guard > 200) else tree_root(p, guard + 1)
                root[cid] = r
                return r
            roots = sorted({tree_root(c[0]) for c in v}); rng.shuffle(roots)
            hold_roots = set(roots[int(0.8 * len(roots)):])
            hold = {c[0] for c in v if tree_root(c[0]) in hold_roots}
            print(f"   [{t[:24]}] trees={len(roots)} held_trees={len(hold_roots)} held_nodes={len(hold)}")
        else:
            ids = [c[0] for c in v]; rng.shuffle(ids)
            hold = set(ids[int(0.8 * len(ids)):])
        for (ca, oa, ba, na, da), (cb, ob, bb, nb, db) in prs:
            hi, lo = ((ca, cb) if (ba < bb if lower else ba > bb) else (cb, ca))
            now_hi = (ca if (oa < ob if lower else oa > ob) else cb)
            f.write(json.dumps({
                "task": t, "better": hi, "worse": lo,
                "agrees_with_quality": now_hi == hi,      # False = the 26% that flip
                "gap_raw": round(abs(ba - bb), 6),
                "subtree_sizes": [na, nb], "steps_to_best": [da, db],
                "budget_steps": a.budget_steps,
                "intask_split": "test" if (hi in hold or lo in hold) else "train",
                "loto_fold": t, "clears_tau": None, "src": "value"}) + "\n")
            n += 1
        print(f"{t[:38]:38s} nodes={len(v):5d} pairs={len(prs)}")
print(f"[value_pairs] {n} pairs -> {a.out}")
