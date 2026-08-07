"""Tree-level holdout consistency across pairs files.

Suspicion: each builder derives its own eligible-tree list before the seed-7 shuffle, so
"holdout trees" differ per file. Then evaluating model(trained on file A) on file B's test
side leaks A's TRAINING trees into the eval -> the symmetric +10pt cross-superiority in the
L2 2x2 would be memorization, not generalization.

For every ordered file pair (A trained-on, B evaluated-on): count B-test pairs whose tree
root was in A's train side. Also sanity: own test vs own train overlap must be 0.

Usage: python phase1/overlap_check.py
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

FILES = {
    "v2": "phase1/budget_pairs_v2.jsonl",
    "v3": "phase1/budget_pairs_v3.jsonl",
    "dec": "phase1/decision_pairs_v1.jsonl",
    "look": "phase1/value_pairs_v3.jsonl",
}

trees = {}   # name -> {"train": set, "test": set}
pairs_by = {}
for name, path in FILES.items():
    tr, te, plist = set(), set(), []
    try:
        for l in open(path):
            p = json.loads(l)
            if p["better"] not in cards:
                continue
            r = tree_root(p["better"])
            (tr if p.get("intask_split") == "train" else te).add(r)
            plist.append((p.get("intask_split"), r))
    except FileNotFoundError:
        print(f"[skip] {path} missing")
        continue
    trees[name] = {"train": tr, "test": te}
    pairs_by[name] = plist
    both = tr & te
    print(f"{name:5s} train_trees={len(tr):4d} test_trees={len(te):4d} "
          f"own-overlap={len(both)} {'OK' if not both else '<-- BROKEN SPLIT'}")

print()
print(f"{'model-on':>9} {'eval-side':>10} {'test trees in trainer.train':>28} {'affected test pairs':>20}")
for a in trees:            # trained on a
    for b in trees:        # evaluated on b's test side
        if a == b:
            continue
        bad_trees = trees[b]["test"] & trees[a]["train"]
        bad_pairs = sum(1 for s, r in pairs_by[b] if s != "train" and r in bad_trees)
        tot_pairs = sum(1 for s, r in pairs_by[b] if s != "train")
        print(f"{a:>9} {b:>10} {len(bad_trees):5d}/{len(trees[b]['test']):<5d}"
              f"{'':10s} {bad_pairs:6d}/{tot_pairs:<6d} = {bad_pairs/max(tot_pairs,1):.1%}")
