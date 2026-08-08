"""Split the L1 audit eval (3000 pairs, acc 0.82) into leakage strata.

Strata per test pair (empirical, no rng replay):
  frag-clean : neither endpoint's FRAGMENT appears in any train pair
  run-clean  : neither endpoint's RUN (card_run_map) appears in any train pair
  mixed      : at least one endpoint's fragment is train-touched
If mixed >> frag-clean the 0.828 rode on seen-fragment anchoring; run-clean is the
forecast for the run-split retrain (expect tiny n here).

Also: 3-seed decision McNemar vs self-report on v1b (hits_dec_s7/8/9).

Usage: python phase1/l1_cleanjoin.py
"""
import collections, json, math
from math import comb

cards = {}
for l in open("phase1/cards_current.jsonl"):
    d = json.loads(l)
    cards[d["id"]] = d
RUN = json.load(open("phase1/card_run_map.json"))
ORI = json.load(open("phase1/task_orientation.json"))

root = {}
def tr(c, g=0):
    if c in root:
        return root[c]
    p = cards.get(c, {}).get("lineage", {}).get("parent_id")
    r = c if (not p or p not in cards or g > 200) else tr(p, g + 1)
    root[c] = r
    return r

train_frags, train_runs = set(), set()
for l in open("phase1/value_pairs_v3.jsonl"):
    p = json.loads(l)
    if p["intask_split"] == "train":
        for e in (p["better"], p["worse"]):
            if e in cards:
                train_frags.add(tr(e))
                train_runs.add(RUN.get(e))

strata = collections.defaultdict(lambda: [0, 0])
for l in open("phase1/hits_l1_valuepairs.jsonl"):
    h = json.loads(l)
    b, w = h["better"], h["worse"]
    if b not in cards or w not in cards:
        continue
    fclean = tr(b) not in train_frags and tr(w) not in train_frags
    rclean = RUN.get(b) not in train_runs and RUN.get(w) not in train_runs
    for k, cond in (("all", True), ("frag_clean", fclean),
                    ("frag_mixed", not fclean), ("run_clean", rclean)):
        if cond:
            strata[k][0] += h["hit"]
            strata[k][1] += 1
print("L1 audit strata (lookahead ckpt, 3000-pair eval):")
for k in ("all", "frag_clean", "frag_mixed", "run_clean"):
    a, n = strata[k]
    se = math.sqrt(a/n*(1-a/n)/n) if n else 0
    print(f"  {k:11s} {a:>5}/{n:<5} = {a/max(n,1):.4f}  (se {se:.3f})")

print("\n3-seed decision (v1b) McNemar vs self-report, same covered pairs:")
def sr_hit(b, w, task):
    try:
        sb = float(cards[b]["obs"].get("val_at_low"))
        sw = float(cards[w]["obs"].get("val_at_low"))
    except (TypeError, ValueError):
        return None
    if sb == sw:
        return None
    return int((sb < sw) if ORI.get(task, False) else (sb > sw))

votes = collections.defaultdict(list)
srh = {}
for s in (7, 8, 9):
    for l in open(f"phase1/hits_dec_s{s}.jsonl"):
        h = json.loads(l)
        k = (h["better"], h["worse"], h["budget"])
        votes[k].append(h["hit"])
        if k not in srh:
            srh[k] = sr_hit(h["better"], h["worse"], h["task"])

per_seed = []
for i, s in enumerate((7, 8, 9)):
    b01 = b10 = rm = n = 0
    for k, v in votes.items():
        if srh[k] is None or len(v) != 3:
            continue
        n += 1
        rm += v[i]
        if v[i] == 0 and srh[k] == 1:
            b01 += 1
        if v[i] == 1 and srh[k] == 0:
            b10 += 1
    m = b01 + b10
    p = min(1.0, sum(comb(m, j) for j in range(0, min(b01, b10) + 1)) / 2**m * 2) if m else 1.0
    per_seed.append((s, rm / n, b01, b10, p, n))
    print(f"  seed {s}: RM {rm/n:.3f} vs SR, discordant {b01}:{b10}, McNemar p={p:.2e} (n={n})")
maj = b01 = b10 = n = 0
srac = 0
for k, v in votes.items():
    if srh[k] is None or len(v) != 3:
        continue
    n += 1
    mv = int(sum(v) >= 2)
    maj += mv
    srac += srh[k]
    if mv == 0 and srh[k] == 1:
        b01 += 1
    if mv == 1 and srh[k] == 0:
        b10 += 1
m = b01 + b10
p = min(1.0, sum(comb(m, j) for j in range(0, min(b01, b10) + 1)) / 2**m * 2) if m else 1.0
print(f"  3-seed majority: RM {maj/n:.3f} vs SR {srac/n:.3f}, "
      f"discordant {b01}:{b10}, McNemar p={p:.2e} (n={n})")
