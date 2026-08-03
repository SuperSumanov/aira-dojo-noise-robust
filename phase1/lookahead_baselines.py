"""L4: the comparison column the lookahead table needs, on the SAME held-out pairs the model uses.

Every baseline here is budget-blind and needs no training, so it answers "how much of the
lookahead label is already readable off the node itself?" before any model is credited with it:

  own_graded   the node's own external score -- the shortcut a "who looks better now" model takes
  self_report  obs.val_at_low, the score the agent claims for itself (available at decision time,
               unlike own_graded, which needs an external grading run)
  parent_val   the parent's own score -- how much is inherited rather than about this node
  runtime      longer-running solutions as a proxy for more capacity

Reported per budget K so the numbers line up with the trained model's per-budget breakdown.
Usage: python phase1/lookahead_baselines.py PAIRS cards.jsonl
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
print(f"held-out pairs: {len(pairs)}")


def feat(cid, name):
    d = cards[cid]
    if name == "own_graded": return d["label"]["graded"]
    if name == "self_report": return (d.get("obs") or {}).get("val_at_low")
    if name == "runtime": return (d.get("obs") or {}).get("runtime_s")
    if name == "parent_val":
        p = d["lineage"].get("parent_id")
        return cards[p]["label"]["graded"] if p in cards else None
    return None


NAMES = ["own_graded", "self_report", "parent_val", "runtime"]
by_budget = collections.defaultdict(list)
for p in pairs:
    by_budget[p.get("budget", "all")].append(p)

hdr = f"{'budget':>8}  {'n':>6}  " + "  ".join(f"{n:>22}" for n in NAMES)
print(hdr); print("-" * len(hdr))
for B in sorted(by_budget, key=str):
    ps = by_budget[B]
    cells = []
    for name in NAMES:
        ok = dec = 0
        for p in ps:
            fb, fw = feat(p["better"], name), feat(p["worse"], name)
            if fb is None or fw is None or fb == fw: continue
            dec += 1
            # score-like features follow the task orientation; runtime is just "bigger"
            higher_wins = True if name == "runtime" else (not ORI[p["task"]])
            ok += (fb > fw) == higher_wins
        cells.append(f"{ok / dec:.3f} (n={dec})" if dec else "     --     ")
    print(f"{str(B):>8}  {len(ps):>6}  " + "  ".join(f"{c:>22}" for c in cells))

def subset_report(title, ps):
    if not ps: return
    print()
    print(f"{title} (n={len(ps)}):")
    for name in NAMES:
        ok = dec = 0
        for p in ps:
            fb, fw = feat(p["better"], name), feat(p["worse"], name)
            if fb is None or fw is None or fb == fw: continue
            dec += 1
            higher_wins = True if name == "runtime" else (not ORI[p["task"]])
            ok += (fb > fw) == higher_wins
        if dec: print(f"  {name:14s} {ok / dec:.3f} (n={dec})")


# The two subsets a lookahead model is actually judged on. Both are defined so that a model
# which only reads "who looks better right now" scores 0 -- reporting the full test set instead
# lets a shortcut model hide behind the 80%+ of pairs where now and later happen to agree.
subset_report("flips_vs_b1 subset -- no budget-blind rule can be right at every budget",
              [p for p in pairs if p.get("flips_vs_b1")])
subset_report("disagree subset (agrees_with_quality=False) -- now and later point opposite ways",
              [p for p in pairs if p.get("agrees_with_quality") is False])
