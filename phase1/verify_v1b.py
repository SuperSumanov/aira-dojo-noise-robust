"""Verify decision_pairs_v1b: no set straddles fragments, pair-level sides consistent per root.

Usage: python phase1/verify_v1b.py phase1/decision_pairs_v1b.jsonl
"""
import collections, json, sys

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

sides = collections.defaultdict(set)
cnt = collections.Counter()
for l in open(sys.argv[1]):
    p = json.loads(l)
    cnt[p["intask_split"], p["budget"]] += 1
    for e in (p["better"], p["worse"]):
        sides[tree_root(e)].add(p["intask_split"])

bad = [r for r, s in sides.items() if len(s) > 1]
print(f"fragment roots touched: {len(sides)}; roots on both sides: {len(bad)}")
for k in sorted(cnt):
    print(f"  split={k[0]:5s} K={k[1]}: {cnt[k]}")
print("VERDICT:", "CLEAN" if not bad else f"STILL BROKEN ({len(bad)})")
