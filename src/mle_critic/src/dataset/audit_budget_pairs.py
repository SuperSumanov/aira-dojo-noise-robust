"""Full audit of the L2 pipeline, before more GPU goes into it.

Checks, in rough order of how badly each would invalidate the results:
  1  split integrity      -- any pair, or any node, on both sides of the train/test line
  2  budget consistency   -- the same pair must land in the same split under every budget
  3  effective data size  -- one pair emits up to 4 records; identical labels are duplicates
  4  label margin         -- pairs whose two values differ by less than execution noise
  5  near-duplicate code  -- train and test sharing essentially the same solution
  6  eval power           -- per-task counts too small to support a per-task claim
  7  degenerate labels    -- tasks where scores are near-constant or clipped

Usage: python -m src.mle_critic.src.dataset.audit_budget_pairs PAIRS cards.jsonl
"""
import collections, hashlib, json, statistics, sys
from pathlib import Path

DATA_DIR = Path(__file__).resolve().parents[4] / "data" / "mle_critic"

pairs_path, cards_path = sys.argv[1], sys.argv[2]
cards = {}
for l in open(cards_path):
    d = json.loads(l); cards[d["id"]] = d
recs = [json.loads(l) for l in open(pairs_path)]
recs = [r for r in recs if r["better"] in cards and r["worse"] in cards]
tr = [r for r in recs if r["intask_split"] == "train"]
te = [r for r in recs if r["intask_split"] == "test"]
print(f"records: {len(recs)}  train {len(tr)}  test {len(te)}")
print()

# 1 -------------------------------------------------------------------------
print("[1] split integrity")
kt = {frozenset((r["better"], r["worse"])) for r in tr}
ke = {frozenset((r["better"], r["worse"])) for r in te}
nt = {r["better"] for r in tr} | {r["worse"] for r in tr}
ne = {r["better"] for r in te} | {r["worse"] for r in te}
print(f"    pairs in both splits : {len(kt & ke)}   {'OK' if not (kt & ke) else 'LEAK'}")
print(f"    nodes in both splits : {len(nt & ne)}   {'OK' if not (nt & ne) else 'LEAK'}")

# 2 -------------------------------------------------------------------------
print()
print("[2] budget consistency (same pair, same split under every budget)")
side = collections.defaultdict(set)
for r in recs:
    side[frozenset((r["better"], r["worse"]))].add(r["intask_split"])
bad = sum(1 for v in side.values() if len(v) > 1)
print(f"    pairs appearing in >1 split: {bad}   {'OK' if not bad else 'INCONSISTENT'}")

# 3 -------------------------------------------------------------------------
print()
print("[3] effective data size -- a pair emits one record per budget; same label = duplicate")
for name, rs in (("train", tr), ("test", te)):
    uniq_pair = len({frozenset((r["better"], r["worse"])) for r in rs})
    # a distinct training signal is (ordered pair) -- same order under two budgets teaches twice
    uniq_signal = len({(r["better"], r["worse"]) for r in rs})
    print(f"    {name}: {len(rs)} records -> {uniq_pair} distinct pairs "
          f"({len(rs) / max(uniq_pair, 1):.2f}x duplication), {uniq_signal} distinct ordered pairs")
flipped = {k for k, v in collections.defaultdict(set).items()}
ordr = collections.defaultdict(set)
for r in recs:
    ordr[frozenset((r["better"], r["worse"]))].add((r["better"], r["worse"]))
both = sum(1 for v in ordr.values() if len(v) > 1)
print(f"    pairs whose ORDER flips across budgets (the real signal): {both} "
      f"of {len(ordr)} = {both * 100 / max(len(ordr), 1):.1f}%")

# 4 -------------------------------------------------------------------------
print()
print("[4] label margin vs measurement noise")
gaps = [r["gap_raw"] for r in recs if r.get("gap_raw") is not None]
if gaps:
    gaps_sorted = sorted(gaps)
    print(f"    gap_raw  p10={gaps_sorted[len(gaps)//10]:.6f}  median={statistics.median(gaps):.6f}  "
          f"p90={gaps_sorted[9*len(gaps)//10]:.6f}")
    print(f"    gaps exactly 0: {sum(1 for g in gaps if g == 0)}")
try:
    import csv as _csv
    tau = {}
    with open(DATA_DIR / "regrade_tau_nodes.csv") as f:
        for row in _csv.DictReader(f):
            t = row.get("task") or row.get("competition") or row.get("competition_id")
            v = row.get("tau") or row.get("std") or row.get("score_std")
            if t and v:
                try: tau.setdefault(t, []).append(float(v))
                except ValueError: pass
    if tau:
        print("    measured tau (p90 of per-node std) by task, vs median gap in that task:")
        gt = collections.defaultdict(list)
        for r in recs:
            if r.get("gap_raw") is not None: gt[r["task"]].append(r["gap_raw"])
        for t in sorted(tau):
            v = sorted(tau[t]); p90 = v[9 * len(v) // 10]
            if t in gt:
                med = statistics.median(gt[t])
                below = sum(1 for g in gt[t] if g < p90) * 100 // max(len(gt[t]), 1)
                print(f"      {t[:38]:38s} tau_p90={p90:.5f} median_gap={med:.5f} "
                      f"-> {below}% of pairs below tau")
except FileNotFoundError:
    print("    (no tau file)")

# 5 -------------------------------------------------------------------------
print()
print("[5] near-duplicate code across the split")


def norm(c):
    return hashlib.md5(" ".join((c or "").split()).encode()).hexdigest()


htr = {norm(cards[n].get("code")) for n in nt}
hte = {norm(cards[n].get("code")) for n in ne}
print(f"    byte-identical solutions shared train/test: {len(htr & hte)} "
      f"(train {len(htr)} distinct, test {len(hte)} distinct)")

# 6 -------------------------------------------------------------------------
print()
print("[6] eval power per task (test split)")
c = collections.Counter(r["task"] for r in te)
for t, n in c.most_common():
    se = 0.5 / (n ** 0.5)
    flag = "  <-- too small to quote alone" if n < 400 else ""
    print(f"    {t[:42]:42s} {n:6d}  SE~{se:.3f}{flag}")

# 7 -------------------------------------------------------------------------
print()
print("[7] degenerate labels")
sc = collections.defaultdict(list)
for cid, d in cards.items():
    sc[d["task"]["name"]].append(d["label"]["graded"])
tasks_in_pairs = {r["task"] for r in recs}
for t in sorted(tasks_in_pairs):
    v = sc.get(t, [])
    if len(v) < 5: continue
    uniq = len(set(v))
    print(f"    {t[:42]:42s} n={len(v):5d} distinct={uniq:5d} "
          f"({uniq * 100 // len(v)}%)" + ("   <-- heavily tied" if uniq * 100 // len(v) < 50 else ""))
