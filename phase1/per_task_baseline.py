"""Per-task baselines, so each LOTO run has a target to be judged against.

A leave-one-task-out run trains on every other task and is tested on the held-out one. Its
accuracy is only meaningful next to what a training-free predictor gets on that same task --
tasks differ a lot in how predictable they are, so a single global baseline would mislead.

Undecidable pairs count as 0.5, matching how the model is scored (it must answer every pair).

Usage: python phase1/per_task_baseline.py PAIRS cards.jsonl
"""
import collections, json, sys

pairs_path, cards_path = sys.argv[1], sys.argv[2]
cards = {}
for l in open(cards_path):
    d = json.loads(l); cards[d["id"]] = d
ORI = json.load(open("phase1/task_orientation.json"))

pairs = [json.loads(l) for l in open(pairs_path)]
pairs = [p for p in pairs if p["better"] in cards and p["worse"] in cards]
by = collections.defaultdict(list)
for p in pairs:
    by[p["task"]].append(p)


def feat(cid, name):
    d = cards[cid]
    if name == "own_graded": return d["label"]["graded"]
    if name == "self_report": return (d.get("obs") or {}).get("val_at_low")
    if name == "parent_val":
        q = d["lineage"].get("parent_id")
        return cards[q]["label"]["graded"] if q in cards else None
    return None


NAMES = ["own_graded", "self_report", "parent_val"]
print(f"{'task':42s} {'pairs':>7} {'own_graded':>11} {'self_report':>12} {'parent_val':>11}")
print("-" * 88)
for t, ps in sorted(by.items(), key=lambda kv: -len(kv[1])):
    if len(ps) < 200: continue
    cells = []
    for name in NAMES:
        ok = 0.0
        for p in ps:
            a, b = feat(p["better"], name), feat(p["worse"], name)
            if a is None or b is None or a == b:
                ok += 0.5
            else:
                ok += (a > b) == (not ORI[t])
        cells.append(f"{ok / len(ps):.4f}")
    print(f"{t[:42]:42s} {len(ps):>7} {cells[0]:>11} {cells[1]:>12} {cells[2]:>11}")
print()
print("LOTO candidates need enough held-out pairs to resolve a difference; the top few by pair")
print("count are the only ones worth spending a run on.")
