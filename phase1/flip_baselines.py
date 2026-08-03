"""Trivial baselines on the budget-flip eval set -- run BEFORE reading the L2 result.

Two questions:
  1. Is the analytic claim true? Any budget-BLIND rule must average exactly 0.500 across the
     two budgets, because the labels are opposite and the rule cannot see the budget.
  2. Is there a trivial BUDGET-AWARE rule that already solves it? A feature like subtree size
     or depth can legitimately change which node it prefers as the budget grows. If one of
     those hits the same accuracy a trained budget-conditioned model does, L2 is not a finding.

Usage: python phase1/flip_baselines.py phase1/budget_flip_eval_v1.jsonl phase1/cards_current.jsonl
"""
import collections, json, sys

fe_path, cards_path = sys.argv[1], sys.argv[2]
cards = {}
for l in open(cards_path):
    d = json.loads(l); cards[d["id"]] = d
ORI = json.load(open("phase1/task_orientation.json"))
kids = collections.defaultdict(list)
for cid, d in cards.items():
    p = d["lineage"].get("parent_id")
    if p: kids[p].append(cid)


def subtree_sizes(cid):
    """(descendants within 1 step, descendants total, max depth below)"""
    n1 = len(kids.get(cid, []))
    tot, deep, stack = 0, 0, [(k, 1) for k in kids.get(cid, [])]
    seen = set()
    while stack:
        x, dist = stack.pop()
        if x in seen: continue
        seen.add(x); tot += 1; deep = max(deep, dist)
        stack.extend((k, dist + 1) for k in kids.get(x, []))
    return n1, tot, deep


SZ = {cid: subtree_sizes(cid) for cid in cards}
recs = [json.loads(l) for l in open(fe_path)]
recs = [r for r in recs if r["x"] in cards and r["y"] in cards]


def feat(cid, name):
    d = cards[cid]
    if name == "own_graded":
        return d["label"]["graded"]
    if name == "self_report":
        v = d.get("label", {}).get("self_reported")
        return v if isinstance(v, (int, float)) else None
    if name == "n_children": return SZ[cid][0]
    if name == "subtree_size": return SZ[cid][1]
    if name == "subtree_depth": return SZ[cid][2]
    if name == "tree_depth": return d["lineage"].get("tree_depth") or 0
    return None


# budget-blind rules: one prediction, scored against both budgets' labels
BLIND = ["own_graded", "self_report", "n_children", "subtree_size", "subtree_depth", "tree_depth"]
# budget-aware rules: prefer own score when tight, prefer growth potential when loose
AWARE = [("own_graded@lo -> subtree_size@hi", "own_graded", "subtree_size"),
         ("own_graded@lo -> subtree_depth@hi", "own_graded", "subtree_depth"),
         ("own_graded@lo -> n_children@hi", "own_graded", "n_children")]

print(f"n_flip={sum(r['kind']=='flip' for r in recs)}  n_control={sum(r['kind']=='control' for r in recs)}")
print()


def pick(r, name, higher_better):
    fx, fy = feat(r["x"], name), feat(r["y"], name)
    if fx is None or fy is None or fx == fy:
        return None
    return r["x"] if ((fx > fy) == higher_better) else r["y"]


for kind in ("flip", "control"):
    rs = [r for r in recs if r["kind"] == kind]
    print(f"--- {kind} pairs (n={len(rs)}) ---")
    for name in BLIND:
        for hb in ([False, True] if name == "own_graded" else [True]):
            lo_ok = hi_ok = dec = 0
            for r in rs:
                # orientation for own_graded follows the task (lower-is-better tasks flip it)
                h = (not ORI[r["task"]]) if name == "own_graded" else hb
                p = pick(r, name, h)
                if p is None: continue
                dec += 1
                lo_ok += p == r["better_lo"]; hi_ok += p == r["better_hi"]
            if not dec: continue
            tag = name + ("" if name != "own_graded" else " (task-oriented)")
            print(f"  {tag:34s} decided={dec:5d} acc@lo={lo_ok/dec:.3f} "
                  f"acc@hi={hi_ok/dec:.3f} mean={(lo_ok+hi_ok)/(2*dec):.3f}")
            if name == "own_graded": break
    for label, flo, fhi in AWARE:
        lo_ok = hi_ok = dec = 0
        for r in rs:
            pl = pick(r, flo, not ORI[r["task"]])
            ph = pick(r, fhi, True)
            if pl is None or ph is None: continue
            dec += 1
            lo_ok += pl == r["better_lo"]; hi_ok += ph == r["better_hi"]
        if dec:
            print(f"  {label:34s} decided={dec:5d} acc@lo={lo_ok/dec:.3f} "
                  f"acc@hi={hi_ok/dec:.3f} mean={(lo_ok+hi_ok)/(2*dec):.3f}")
    print()
