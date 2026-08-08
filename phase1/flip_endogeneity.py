"""Endogeneity controls for the value-pairs FLIP subset (the 08-06 doc's fatal-rebuttal check).

The doc's Direction A rests on 'the trained model scores 0.6094 on flip pairs where every
free proxy is 0.000 by construction'. Its own section 2.5 warns: subtree-best labels are a
product of MCTS search allocation, so 'predicts subtree-best' may collapse into 'predicts
which node got searched more'. Before ANY flip number is quoted, the cheap structural
predictors must fail on the flip subset:

  subtree_size  : larger recorded subtree wins   (search-allocation artefact channel)
  n_children    : more children wins
  step_order    : later-generated wins
  self_report   : the free competitor (expected LOW on flips: they oppose current quality)
  own_graded    : exact 0.000 by construction -- sanity check that the flag means what
                  it says (any deviation = my join or orientation is wrong, abort)

Slices: ALL test / AGREE / FLIP, on value_pairs_v3 test side.

Usage: python phase1/flip_endogeneity.py
"""
import collections, json, math

cards = {}
for l in open("phase1/cards_current.jsonl"):
    d = json.loads(l)
    cards[d["id"]] = d
ORI = json.load(open("phase1/task_orientation.json"))

rows = []
for l in open("phase1/value_pairs_v3.jsonl"):
    p = json.loads(l)
    if p.get("intask_split") == "test" and p["better"] in cards and p["worse"] in cards:
        rows.append(p)
n_flip = sum(1 for p in rows if p.get("agrees_with_quality") is False)
print(f"value_pairs_v3 test rows: {len(rows)}; flips {n_flip} "
      f"({n_flip/max(len(rows),1):.1%})")
per_task = collections.Counter(p["task"] for p in rows if p.get("agrees_with_quality") is False)
tot_task = collections.Counter(p["task"] for p in rows)
for t in sorted(tot_task, key=lambda x: -tot_task[x])[:8]:
    print(f"   {t[:40]:40s} flips {per_task[t]}/{tot_task[t]} = {per_task[t]/tot_task[t]:.1%}")


def feat(cid, name):
    d = cards[cid]
    if name == "self_report":
        try:
            return float(d["obs"].get("val_at_low"))
        except (TypeError, ValueError):
            return None
    if name == "own_graded":
        g = d["label"].get("graded")
        return float(g) if g is not None else None
    if name == "n_children":
        return float(len(d["lineage"].get("children_ids") or []))
    if name == "step_order":
        s = d["lineage"].get("step")
        return float(s) if s is not None else None


def pair_subtree(p):
    ss = p.get("subtree_sizes")
    if isinstance(ss, (list, tuple)) and len(ss) == 2:
        try:
            return float(ss[0]), float(ss[1])
        except (TypeError, ValueError):
            return None
    return None


def acc(name, subset):
    k = n = 0
    for p in subset:
        if name == "subtree_size":
            st = pair_subtree(p)
            if st is None or st[0] == st[1]:
                continue
            hi = st[0] > st[1]
        else:
            b, w = feat(p["better"], name), feat(p["worse"], name)
            if b is None or w is None or b == w:
                continue
            hi = b > w
            if name in ("self_report", "own_graded") and ORI.get(p["task"], False):
                hi = b < w
        k += int(hi)
        n += 1
    return k, n


SLICES = [("ALL", rows),
          ("AGREE", [p for p in rows if p.get("agrees_with_quality") is not False]),
          ("FLIP", [p for p in rows if p.get("agrees_with_quality") is False])]
BASES = ["own_graded", "self_report", "subtree_size", "n_children", "step_order"]
print(f"\n{'baseline':13s}" + "".join(f" {s[0]:>16s}" for s in SLICES))
print("-" * 66)
for bn in BASES:
    cells = []
    for _, sub in SLICES:
        k, n = acc(bn, sub)
        se = math.sqrt(max(k/n*(1-k/n), 1e-12)/n) if n else float("nan")
        cells.append(f"{k/max(n,1):.3f}±{se:.3f}" if n else "   --  ")
    print(f"{bn:13s}" + "".join(f" {c:>16s}" for c in cells))
print("\nread: own_graded on FLIP must print 0.000 exactly (flag sanity).")
print("      subtree_size on FLIP >~0.55 would confirm the endogeneity fear --")
print("      then no flip number is quotable until size-matched/limited-K rebuilds.")
