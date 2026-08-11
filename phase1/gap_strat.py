"""VOIDED 2026-08-12 -- superseded by phase1/gap_strat3.py. Kept for audit, do not cite.

This script stratified lookahead pairs on |graded(better) - graded(worse)|. That is not the
margin the label encodes: a lookahead pair's better/worse is decided by what each node's
SUBTREE reached, and the file records that margin as gap_raw. The two coincide on 100.00% of
the 3,804 rows where steps_to_best == [0,0] and on 10.4% overall (phase1/confirm_gap.py), so
gap_raw is the label margin and every verdict printed below is indexed on the wrong axis.

Corrected results: phase1/gap_strat3.txt (lookahead) and phase1/gap_strat4.txt (the clean
budget-0 sibling set). Write-up: phase1/实验记录/2026-08-12/.
"""

"""Gap-stratified predictor evaluation -- and first, the three kill conditions.

The proposed main line: a predictor's headline pairwise accuracy is a weighted average over
a distribution of TRUE-SCORE GAPS, and that distribution is a property of how pairs were
constructed, not of the decisions a search actually faces. Stratify and the claim is that
everything collapses to chance below gap ~1e-2, while the label-noise ceiling there is far
above chance -- so the collapse is not measurement error.

Before adopting any of that, the proposal's own kill conditions are checked here, on our
full corpus and our own artefacts rather than a partial checkout:

  K1  hard region (gap < 1e-2) with common coverage < 400 pairs, or one task > 85% of it
  K2  >=3 tasks with n>=60 each in the hard region that do NOT agree (some clearly above
      0.5, some clearly below) -- then it is not one phenomenon
  K3  the recomputed noise ceiling inside the hard region < 0.65 -- then "not label noise"
      fails and half the argument goes with it

Bucket edges and the 1e-2 threshold come from the proposal and are fixed here before any
result is read; they are not tunable.

Ceiling curve comes from our own regrade recomputation, not from the proposal's numbers.

Usage: python phase1/gap_strat.py [--hits phase1/hits_l1_uncapped.jsonl]
"""
import argparse, collections, glob, json, math, random, statistics

ap = argparse.ArgumentParser()
ap.add_argument("--hits", default="phase1/hits_l1_uncapped.jsonl")
ap.add_argument("--cards", default="phase1/cards_current_v8.jsonl")
a = ap.parse_args()

EDGES = [0.0, 1e-4, 3e-4, 1e-3, 3e-3, 1e-2, 3e-2, 1e-1, 3e-1, float("inf")]
HARD = 1e-2
ORI = json.load(open("phase1/task_orientation.json"))
RUN = json.load(open("phase1/card_run_map.json"))
cards = {}
for l in open(a.cards):
    d = json.loads(l)
    cards[d["id"]] = d


def fin(x):
    try:
        v = float(x)
    except (TypeError, ValueError):
        return None
    return v if math.isfinite(v) else None


def bucket(g):
    for k in range(len(EDGES) - 1):
        if EDGES[k] <= g < EDGES[k + 1]:
            return k
    return len(EDGES) - 2


# ---- ceiling curve, recomputed from our regrade data ---------------------------
reps, orig, task_of = collections.defaultdict(list), {}, {}
for path in sorted(glob.glob("phase1/regrade_results*.jsonl")):
    for l in open(path):
        try:
            d = json.loads(l)
        except json.JSONDecodeError:
            continue
        cid = d.get("card_id")
        if not cid:
            continue
        task_of[cid] = d.get("competition")
        o = fin(d.get("orig_graded"))
        if o is not None:
            orig[cid] = o
        s = fin(d.get("score"))
        if s is not None:
            reps[cid].append(s)
usable = {c: v for c, v in reps.items() if len(v) >= 2 and c in orig}


def lab(x, y, t):
    return None if x == y else int((x < y) if ORI.get(t, False) else (x > y))


obs = collections.defaultdict(lambda: [0, 0])
bt = collections.defaultdict(list)
for c in usable:
    bt[task_of[c]].append(c)
for t, cs in bt.items():
    for i in range(len(cs)):
        for j in range(i + 1, len(cs)):
            ci, cj = cs[i], cs[j]
            mi, mj = statistics.mean(usable[ci]), statistics.mean(usable[cj])
            l1 = lab(orig[ci], orig[cj], t)
            l2 = lab(mi, mj, t)
            if l1 is None or l2 is None:
                continue
            k = bucket(abs(mi - mj))
            obs[k][0] += int(l1 == l2)
            obs[k][1] += 1


def invert(p):
    return 0.5 if p is None or p <= 0.5 else (1 + math.sqrt(max(0.0, 2 * p - 1))) / 2


ceil, last = {}, None
for k in range(len(EDGES) - 1):
    o, n = obs[k]
    if n >= 25:
        last = invert(o / n)
    ceil[k] = last if last is not None else 0.5   # inherit from smaller gap, never pool
print("ceiling curve recomputed from our own regrades "
      "(n>=25 per bucket, unestimable buckets inherit downward):")
for k in range(len(EDGES) - 1):
    o, n = obs[k]
    print(f"  [{EDGES[k]:.0e},{EDGES[k+1]:.0e})  regrade_n={n:5d}  "
          f"agree={o/n if n else float('nan'):.4f}  ceiling={ceil[k]:.4f}"
          if n else
          f"  [{EDGES[k]:.0e},{EDGES[k+1]:.0e})  regrade_n={n:5d}  "
          f"ceiling={ceil[k]:.4f} (inherited)")

# ---- predictors ---------------------------------------------------------------
rows = []
for l in open(a.hits):
    h = json.loads(l)
    b, w = h["better"], h["worse"]
    if b not in cards or w not in cards:
        continue
    gb, gw = fin(cards[b]["label"].get("graded")), fin(cards[w]["label"].get("graded"))
    if gb is None or gw is None:
        continue
    rows.append({"b": b, "w": w, "task": h["task"], "gap": abs(gb - gw),
                 "k": bucket(abs(gb - gw)), "rm": h["hit"], "run": RUN.get(b)})
print(f"\nscored pairs with a computable gap: {len(rows)}")


def sr_hit(r):
    sb, sw = (fin(cards[r["b"]]["obs"].get("val_at_low")),
              fin(cards[r["w"]]["obs"].get("val_at_low")))
    if sb is None or sw is None or sb == sw:
        return None
    return int((sb < sw) if ORI.get(r["task"], False) else (sb > sw))


EMB = {}
try:
    EMB = json.load(open("phase1/embed_scores.json"))
except FileNotFoundError:
    pass


def emb_hit(r):
    if r["b"] not in EMB or r["w"] not in EMB:
        return None
    return int(float(EMB[r["b"]]) > float(EMB[r["w"]]))


def len_hit(r):
    lb, lw = len(cards[r["b"]].get("code") or ""), len(cards[r["w"]].get("code") or "")
    return None if lb == lw else int(lb > lw)


PRED = {"rm_1.5b": lambda r: r["rm"], "self_report": sr_hit,
        "embed_frozen": emb_hit, "code_len": len_hit,
        "gap_oracle": lambda r: 1}          # positive control: must be 1.000 everywhere


def boot(d, nb=3000, seed=7):
    ks = list(d)
    if not ks:
        return float("nan"), float("nan")
    r = random.Random(seed)
    o = []
    for _ in range(nb):
        v = [x for k in (r.choice(ks) for _ in ks) for x in d[k]]
        o.append(sum(v) / len(v))
    o.sort()
    return o[int(.025 * nb)], o[int(.975 * nb)]


print(f"\n{'bucket':>16} {'n':>6} {'ceil':>6} " +
      " ".join(f"{p:>13}" for p in PRED))
for k in range(len(EDGES) - 1):
    sub = [r for r in rows if r["k"] == k]
    if not sub:
        continue
    cells = []
    for name, fn in PRED.items():
        v = [fn(r) for r in sub]
        v = [x for x in v if x is not None]
        cells.append(f"{sum(v)/len(v):.4f}({len(v):4d})" if v else "     --      ")
    print(f"[{EDGES[k]:.0e},{EDGES[k+1]:.0e}) {len(sub):6d} {ceil[k]:6.3f} " +
          " ".join(cells))

print("\n--- pre-registered hard/easy split at gap < 1e-2 ---")
for label, sel in (("HARD  gap<1e-2", lambda r: r["gap"] < HARD),
                   ("EASY  gap>=1e-2", lambda r: r["gap"] >= HARD)):
    sub = [r for r in rows if sel(r)]
    n = len(sub)
    wc = sum(ceil[r["k"]] for r in sub) / max(n, 1)
    print(f"\n{label}: n={n} ({n/len(rows):.1%})   recomputed ceiling = {wc:.4f}")
    for name, fn in PRED.items():
        if name == "gap_oracle":
            continue
        d_t, d_r = collections.defaultdict(list), collections.defaultdict(list)
        for r in sub:
            x = fn(r)
            if x is None:
                continue
            d_t[r["task"]].append(float(x))
            d_r[r["run"]].append(float(x))
        v = [x for vs in d_t.values() for x in vs]
        if not v:
            continue
        lo, hi = boot(d_t)
        rlo, rhi = boot(d_r)
        print(f"   {name:14s} {sum(v)/len(v):.4f}  task[{lo:.4f},{hi:.4f}]  "
              f"run[{rlo:.4f},{rhi:.4f}]  n={len(v)}")

print("\n--- KILL CONDITIONS ---")
hard = [r for r in rows if r["gap"] < HARD]
byt = collections.Counter(r["task"] for r in hard)
top = byt.most_common(1)[0] if byt else ("-", 0)
share = top[1] / max(len(hard), 1)
print(f"K1  hard-region pairs = {len(hard)} (need >= 400)  -> "
      f"{'PASS' if len(hard) >= 400 else 'FAIL'}")
print(f"    dominant task {top[0][:30]} = {share:.1%} (need <= 85%)  -> "
      f"{'PASS' if share <= 0.85 else 'FAIL'}")
print(f"    task decomposition of the hard region:")
for t, c in byt.most_common(8):
    sub = [r for r in hard if r["task"] == t]
    acc = sum(r["rm"] for r in sub) / len(sub)
    print(f"      {t[:40]:42s} n={c:5d}  RM={acc:.4f}")
big = [(t, c) for t, c in byt.items() if c >= 60]
if len(big) >= 3:
    accs = []
    for t, c in big:
        sub = [r for r in hard if r["task"] == t]
        accs.append((t, sum(r["rm"] for r in sub) / len(sub)))
    hi = [t for t, x in accs if x > 0.55]
    lo = [t for t, x in accs if x < 0.45]
    print(f"K2  tasks with n>=60: {len(big)}; clearly above 0.55: {len(hi)}; "
          f"clearly below 0.45: {len(lo)}  -> "
          f"{'FAIL (not one phenomenon)' if hi and lo else 'PASS (consistent)'}")
else:
    print(f"K2  only {len(big)} tasks with n>=60 in the hard region -- cannot assess")
wc = sum(ceil[r["k"]] for r in hard) / max(len(hard), 1)
print(f"K3  recomputed hard-region ceiling = {wc:.4f} (need >= 0.65)  -> "
      f"{'PASS' if wc >= 0.65 else 'FAIL'}")
