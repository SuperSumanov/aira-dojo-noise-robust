"""Final L1 chapter numbers: paired RM-vs-SR on the run-clean eval, per slice.

The slice table printed RM on all pairs but SR on covered pairs only; the quotable
comparison is paired-on-covered with McNemar, plus RM-vs-subtree the same way.
"""
import json
from math import comb

cards = {}
for l in open("phase1/cards_current.jsonl"):
    d = json.loads(l)
    cards[d["id"]] = d
ORI = json.load(open("phase1/task_orientation.json"))

flip_flag, subtree = {}, {}
for l in open("phase1/value_pairs_runsplit.jsonl"):
    p = json.loads(l)
    if p["intask_split"] == "test":
        k = (p["better"], p["worse"])
        flip_flag[k] = (p.get("agrees_with_quality") is False)
        ss = p.get("subtree_sizes")
        subtree[k] = tuple(ss) if isinstance(ss, (list, tuple)) and len(ss) == 2 else None


def sr_hit(b, w, task):
    try:
        sb = float(cards[b]["obs"].get("val_at_low"))
        sw = float(cards[w]["obs"].get("val_at_low"))
    except (TypeError, ValueError):
        return None
    if sb == sw:
        return None
    return int((sb < sw) if ORI.get(task, False) else (sb > sw))


rows = []
for l in open("phase1/hits_l1_runsplit.jsonl"):
    h = json.loads(l)
    k = (h["better"], h["worse"])
    if k in flip_flag:
        rows.append((h["hit"], sr_hit(*k, h["task"]), flip_flag[k], k))


def mcnemar(pairs):
    b01 = sum(1 for a, b in pairs if a == 0 and b == 1)
    b10 = sum(1 for a, b in pairs if a == 1 and b == 0)
    m = b01 + b10
    p = (min(1.0, sum(comb(m, i) for i in range(0, min(b01, b10) + 1)) / 2 ** m * 2)
         if m else 1.0)
    return b01, b10, p


for name, sel in (("ALL", lambda f: True), ("AGREE", lambda f: not f),
                  ("FLIP", lambda f: f)):
    cov = [(rm, s) for rm, s, f, _ in rows if sel(f) and s is not None]
    if not cov:
        continue
    n = len(cov)
    rm_a = sum(a for a, _ in cov) / n
    sr_a = sum(b for _, b in cov) / n
    b01, b10, p = mcnemar(cov)
    print(f"[{name:5s}] covered n={n:5d}  RM={rm_a:.4f}  SR={sr_a:.4f}  "
          f"discordant SRwin:RMwin={b01}:{b10}  McNemar p={p:.2e}")

covs = [(rm, (1 if subtree[k][0] > subtree[k][1] else 0)) for rm, _, f, k in rows
        if subtree.get(k) and subtree[k][0] != subtree[k][1]]
n = len(covs)
b01, b10, p = mcnemar(covs)
print(f"[vs subtree_size] n={n} RM={sum(a for a,_ in covs)/n:.4f} "
      f"sub={sum(b for _,b in covs)/n:.4f} {b01}:{b10} p={p:.2e}")
