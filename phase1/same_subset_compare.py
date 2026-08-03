"""Compare the model against the baselines on EXACTLY the pairs both can decide.

The model scores every pair; self_report is undefined wherever a card has no val_at_low, and
own_graded ties are undecidable. Comparing 0.764 over all pairs against 0.760 over a smaller
subset is not a comparison. This restricts every predictor to the intersection.

Usage: python phase1/same_subset_compare.py PAIRS cards.jsonl
"""
import collections, json, sys

pairs_path, cards_path = sys.argv[1], sys.argv[2]
cards = {}
for l in open(cards_path):
    d = json.loads(l); cards[d["id"]] = d
ORI = json.load(open("phase1/task_orientation.json"))

pairs = [json.loads(l) for l in open(pairs_path)]
pairs = [p for p in pairs if p.get("intask_split") == "test"
         and p["better"] in cards and p["worse"] in cards]


def feat(cid, name):
    d = cards[cid]
    if name == "own_graded": return d["label"]["graded"]
    if name == "self_report": return (d.get("obs") or {}).get("val_at_low")
    if name == "parent_val":
        p = d["lineage"].get("parent_id")
        return cards[p]["label"]["graded"] if p in cards else None
    return None


NAMES = ["own_graded", "self_report", "parent_val"]
# a pair is comparable only if EVERY baseline can decide it
def decidable(p, name):
    a, b = feat(p["better"], name), feat(p["worse"], name)
    return a is not None and b is not None and a != b


common = [p for p in pairs if all(decidable(p, n) for n in NAMES)]
print(f"held-out test pairs: {len(pairs)}")
print(f"decidable by ALL baselines (the only fair comparison set): {len(common)} "
      f"({len(common) * 100 // max(len(pairs), 1)}%)")
print()

for label, ps in (("all test pairs", pairs), ("common subset", common)):
    print(f"--- {label} (n={len(ps)}) ---")
    for name in NAMES:
        ok = dec = 0
        for p in ps:
            a, b = feat(p["better"], name), feat(p["worse"], name)
            if a is None or b is None or a == b: continue
            dec += 1
            ok += (a > b) == (not ORI[p["task"]])
        if dec: print(f"  {name:12s} {ok / dec:.4f}  (decided {dec}/{len(ps)})")
    print()

by = collections.Counter(p["budget"] for p in common if "budget" in p)
if by:
    print("common subset by budget:", dict(sorted(by.items())))
print()
print("To finish the comparison, re-run the model's eval restricted to these pair ids;")
print("the model number quoted against these must come from the same set, not the full test pool.")
ids = [[p["better"], p["worse"], p.get("budget")] for p in common]
json.dump(ids, open("phase1/common_eval_ids.json", "w"))
print(f"wrote {len(ids)} pair ids -> phase1/common_eval_ids.json")
