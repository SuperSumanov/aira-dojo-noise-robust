"""Dissect the 10 trees whose decision pairs appear on BOTH sides of the split.

decision_pairs.py assigns in_hold = tree_root(ch[0]) in hold[task]; chains are <=15 deep so
tree_root is deterministic. Same root should imply same side. Find the offenders and print
everything about them: root, task(s) seen in the tree, hold membership reconstruction,
which sets emitted which split.

Usage: python phase1/dissect_dec_overlap.py
"""
import collections, json, random

cards = {}
for l in open("phase1/cards_current.jsonl"):
    d = json.loads(l)
    cards[d["id"]] = d
ORI = json.load(open("phase1/task_orientation.json"))

root = {}
def tree_root(cid, g=0):
    if cid in root:
        return root[cid]
    p = cards.get(cid, {}).get("lineage", {}).get("parent_id")
    r = cid if (not p or p not in cards or g > 200) else tree_root(p, g + 1)
    root[cid] = r
    return r

# reconstruct hold exactly as decision_pairs.py (seed 7, same iteration order)
rng = random.Random(7)
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

# read emitted pairs, group splits by root
sides = collections.defaultdict(lambda: collections.defaultdict(int))
tasks_of = collections.defaultdict(set)
parents_of = collections.defaultdict(lambda: collections.defaultdict(set))
for l in open("phase1/decision_pairs_v1.jsonl"):
    p = json.loads(l)
    r = tree_root(p["better"])
    sides[r][p["intask_split"]] += 1
    tasks_of[r].add(p["task"])
    parents_of[r][p["intask_split"]].add(p["parent"])

bad = [r for r, s in sides.items() if len(s) > 1]
print(f"roots with pairs on both sides: {len(bad)}")
aff_test = sum(sides[r]["test"] for r in bad)
print(f"affected TEST pairs total: {aff_test}")
for r in bad[:12]:
    ts = tasks_of[r]
    t0 = next(iter(ts))
    print(f"\nroot={r[:60]}")
    print(f"  tasks in emitted pairs: {sorted(ts)}")
    print(f"  root in hold[{t0[:20]}]: {r in hold.get(t0, set())}")
    print(f"  split counts: {dict(sides[r])}")
    # do the two sides' parents share nodes or are they disjoint subforests?
    tp, sp = parents_of[r]["train"], parents_of[r]["test"]
    print(f"  parents train={len(tp)} test={len(sp)} shared={len(tp & sp)}")
    # check: does tree_root(parent's children[0]) disagree with r for some sets?
    for side, ps in (("train", tp), ("test", sp)):
        for par in list(ps)[:2]:
            ch = [c for c in cards if cards[c]["lineage"].get("parent_id") == par]
            if ch:
                rr = tree_root(sorted(ch)[0])
                t_ch = cards[ch[0]]["task"]["name"]
                print(f"    sample {side} set parent={par[:40]} ch0_root==r: {rr == r} "
                      f"ch_task={t_ch[:20]} root_in_hold[that_task]={rr in hold.get(t_ch, set())}")
