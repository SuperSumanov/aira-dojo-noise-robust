"""Baselines on the EXACT pairs the model was scored on.

rm_train_hf.py draws its test set deterministically: Random(seed), shuffle(train_pool),
shuffle(test_pool), then take the first eval_cap. Both shuffles consume the same generator, so
the draw is reproducible only if they happen in that order. Reproducing it here makes the model
number and the baseline numbers refer to the same pairs -- otherwise "the model matches
self-report" is comparing two different test sets.

Usage: python phase1/exact_eval_baseline.py PAIRS cards.jsonl EVAL_CAP [SEED]
"""
import json, random, sys

pairs_path, cards_path = sys.argv[1], sys.argv[2]
eval_cap = int(sys.argv[3])
seed = int(sys.argv[4]) if len(sys.argv) > 4 else 7

cards = {}
for l in open(cards_path):
    d = json.loads(l); cards[d["id"]] = d
ORI = json.load(open("phase1/task_orientation.json"))

pairs = [json.loads(l) for l in open(pairs_path)]
pairs = [p for p in pairs if p["better"] in cards and p["worse"] in cards]
train_pool = [p for p in pairs if p["intask_split"] == "train"]
test_pool = [p for p in pairs if p["intask_split"] == "test"]
rng = random.Random(seed)
rng.shuffle(train_pool)          # must happen first: it consumes the same generator
rng.shuffle(test_pool)
test_pool = test_pool[:eval_cap]
print(f"reproduced eval set: n={len(test_pool)} (cap={eval_cap}, seed={seed})")


def feat(cid, name):
    d = cards[cid]
    if name == "own_graded": return d["label"]["graded"]
    if name == "self_report": return (d.get("obs") or {}).get("val_at_low")
    if name == "parent_val":
        p = d["lineage"].get("parent_id")
        return cards[p]["label"]["graded"] if p in cards else None
    return None


print()
print("A predictor that cannot decide a pair is scored as a coin flip on it, since the model is")
print("forced to answer every pair -- crediting a baseline only where it happens to be defined")
print("would flatter it.")
print()
for name in ("own_graded", "self_report", "parent_val"):
    ok = dec = 0.0
    for p in test_pool:
        a, b = feat(p["better"], name), feat(p["worse"], name)
        if a is None or b is None or a == b:
            ok += 0.5
            continue
        dec += 1
        ok += (a > b) == (not ORI[p["task"]])
    print(f"  {name:12s} {ok / len(test_pool):.4f}   (decided {int(dec)}/{len(test_pool)} "
          f"= {dec * 100 / len(test_pool):.0f}%, rest scored 0.5)")
