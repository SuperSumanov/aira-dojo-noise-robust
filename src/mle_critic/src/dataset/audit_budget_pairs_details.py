"""Second audit pass: the checks that would invalidate results without leaving a trace.

  8   training task balance -- if one task dominates training, per-task failures elsewhere are
                               expected rather than informative
  9   step field integrity  -- count-matching orders descendants by lineage.step; duplicate or
                               missing steps silently make "the first K expansions" arbitrary
  10  length confound       -- can a model score this well by reading only code LENGTH?
  11  eval sampling bias    -- what eval_cap actually draws per task, vs the full test pool
  12  duplicate code within a split -- repeated solutions shrink the effective sample further

Usage: python -m src.mle_critic.src.dataset.audit_budget_pairs_details PAIRS cards.jsonl [EVAL_CAP]
"""
import collections, hashlib, json, random, statistics, sys
from pathlib import Path

DATA_DIR = Path(__file__).resolve().parents[4] / "data" / "mle_critic"

pairs_path, cards_path = sys.argv[1], sys.argv[2]
eval_cap = int(sys.argv[3]) if len(sys.argv) > 3 else 1500
cards = {}
for l in open(cards_path):
    d = json.loads(l); cards[d["id"]] = d
ORI = json.load(open(DATA_DIR / "task_orientation.json"))
recs = [json.loads(l) for l in open(pairs_path)]
recs = [r for r in recs if r["better"] in cards and r["worse"] in cards]
tr = [r for r in recs if r["intask_split"] == "train"]
te = [r for r in recs if r["intask_split"] == "test"]

print("[8] training task balance")
c = collections.Counter(r["task"] for r in tr)
tot = sum(c.values())
for t, n in c.most_common(6):
    print(f"    {t[:42]:42s} {n:7d}  {n * 100 / tot:5.1f}%")
print(f"    -> top task is {c.most_common(1)[0][1] * 100 // tot}% of training")

print()
print("[9] step field integrity (count-matching orders descendants by it)")
miss = sum(1 for d in cards.values() if d["lineage"].get("step") is None)
bytree = collections.defaultdict(list)
for cid, d in cards.items():
    p = d["lineage"].get("parent_id")
    bytree[p].append(d["lineage"].get("step"))
dupe_groups = sum(1 for v in bytree.values() if len(v) != len(set(v)))
print(f"    cards with no step: {miss}/{len(cards)}")
print(f"    sibling groups with duplicate step values: {dupe_groups}/{len(bytree)}")
kids = collections.defaultdict(list)
for cid, d in cards.items():
    p = d["lineage"].get("parent_id")
    if p: kids[p].append(cid)
inv = 0
for p, ks in kids.items():
    if p not in cards:
        continue
    ps = cards[p]["lineage"].get("step")
    for k in ks:
        ks_ = cards[k]["lineage"].get("step")
        if ps is not None and ks_ is not None and ks_ <= ps:
            inv += 1
print(f"    children whose step <= parent step (impossible if step is expansion order): {inv}")

print()
print("[10] length confound -- accuracy of 'prefer the longer/shorter program'")
for name, longer in (("longer wins", True), ("shorter wins", False)):
    ok = 0.0
    for r in te:
        a_, b_ = len(cards[r["better"]].get("code") or ""), len(cards[r["worse"]].get("code") or "")
        ok += 0.5 if a_ == b_ else float((a_ > b_) == longer)
    print(f"    {name:14s} {ok / max(len(te), 1):.4f}")
byt = collections.defaultdict(lambda: [0.0, 0])
for r in te:
    a_, b_ = len(cards[r["better"]].get("code") or ""), len(cards[r["worse"]].get("code") or "")
    e = byt[r["task"]]
    e[0] += 0.5 if a_ == b_ else float(a_ > b_); e[1] += 1
print("    per task (longer wins):")
for t, (o, n) in sorted(byt.items(), key=lambda kv: -kv[1][1])[:6]:
    print(f"      {t[:42]:42s} {o / n:.4f}  (n={n})")

print()
print(f"[11] what eval_cap={eval_cap} actually draws (reproducing the trainer's shuffle)")
rng = random.Random(7)
trp = list(tr); tep = list(te)
rng.shuffle(trp); rng.shuffle(tep)
drawn = tep[:eval_cap]
cd = collections.Counter(r["task"] for r in drawn)
cf = collections.Counter(r["task"] for r in te)
print(f"    {'task':42s} {'drawn':>6} {'full pool':>10} {'SE(drawn)':>10}")
for t, n in cd.most_common():
    print(f"    {t[:42]:42s} {n:>6} {cf[t]:>10} {0.5 / max(n, 1) ** 0.5:>10.3f}")

print()
print("[12] duplicate solutions WITHIN each split")
for name, rs in (("train", tr), ("test", te)):
    nodes = {r["better"] for r in rs} | {r["worse"] for r in rs}
    h = [hashlib.md5(" ".join((cards[n].get("code") or "").split()).encode()).hexdigest()
         for n in nodes]
    print(f"    {name}: {len(nodes)} nodes -> {len(set(h))} distinct programs "
          f"({(len(nodes) - len(set(h))) * 100 // max(len(nodes), 1)}% duplicated)")
