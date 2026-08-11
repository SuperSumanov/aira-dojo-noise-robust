"""Gap-stratified evaluation, corrected: stratify on the LABEL margin.

gap_strat.py stratified lookahead pairs on |graded(better) - graded(worse)|. That is not the
margin the label encodes. A lookahead pair's better/worse is decided by what each node's
SUBTREE reached, and the file records that margin as gap_raw. The two agree on 10.4% of rows
overall and, decisively, on 100.00% of the 3,804 rows where steps_to_best == [0,0] -- the
subset where the node IS its own subtree best and the two quantities must coincide. So
gap_raw is the label margin and the earlier stratification mixed pairs whose labels are
about different comparisons. That also explains the one anomaly in the first pass: bucket
[0,1e-4) was the only small-gap bucket that did not collapse, because those pairs have
near-identical own scores while their labels are about entirely different subtrees.

Everything below is re-derived on gap_raw. Bucket edges and the 1e-2 hard threshold are the
proposal's and are unchanged.

The ceiling needs a caveat that the first pass did not have. The regrade data measures how
reliably a NODE's own score reproduces, so the ceiling curve is indexed by an own-score
margin. Applying it to a subtree-best margin ignores a second noise source -- re-measurement
can change WHICH node is the subtree best -- so on lookahead pairs the curve is an UPPER
BOUND on the true ceiling, and is labelled as such. It is exact only on the steps_to_best
== [0,0] subset, which is therefore reported separately as the anchor where the "not label
noise" argument is airtight.

Usage: python phase1/gap_strat3.py
"""
import collections, glob, json, math, random, statistics

EDGES = [0.0, 1e-4, 3e-4, 1e-3, 3e-3, 1e-2, 3e-2, 1e-1, 3e-1, float("inf")]
HARD = 1e-2
ORI = json.load(open("phase1/task_orientation.json"))
RUN = json.load(open("phase1/card_run_map.json"))
PP = json.load(open("phase1/perpair_hits.json"))
cards = {}
for l in open("phase1/cards_current_v8.jsonl"):
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


# ---- ceiling curve from our own regrades, indexed by own-score margin -------------
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
            l1, l2 = lab(orig[ci], orig[cj], t), lab(mi, mj, t)
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
    ceil[k] = last if last is not None else 0.5
print("ceiling curve (own-score margin; an UPPER BOUND when applied to subtree margins)")
for k in range(len(EDGES) - 1):
    o, n = obs[k]
    print(f"  [{EDGES[k]:.0e},{EDGES[k+1]:.0e})  n={n:5d}  "
          f"agree={(o/n if n else float('nan')):.4f}  ceiling={ceil[k]:.4f}")

# ---- pairs, keyed on the LABEL margin --------------------------------------------
stb = {}
for l in open("phase1/value_pairs_runsplit.jsonl"):
    p = json.loads(l)
    stb[p["better"] + "|" + p["worse"]] = p.get("steps_to_best")

rows = []
for l in open("phase1/hits_l1_uncapped.jsonl"):
    h = json.loads(l)
    b, w = h["better"], h["worse"]
    g = fin(h.get("gap_raw"))
    if g is None or b not in cards or w not in cards:
        continue
    key = b + "|" + w
    s = stb.get(key)
    rows.append({"b": b, "w": w, "key": key, "task": h["task"], "gap": g,
                 "k": bucket(g), "rm": h["hit"], "run": RUN.get(b),
                 "own": s == [0, 0]})
print(f"\nlookahead pairs with a label margin: {len(rows)}; "
      f"of which steps_to_best==[0,0] (ceiling exact): {sum(r['own'] for r in rows)}")

PRED = {"rm_1.5b": lambda r: r["rm"]}
for name in PP:
    PRED[name] = (lambda nm: lambda r: PP[nm].get(r["key"]))(name)
ORDER = ["rm_1.5b"] + [p for p in ["self_report", "tfidf_lr", "static_gbm", "static_lr",
                                   "embed_frozen_05b", "judge_ds8k", "judge_qwenmax",
                                   "code_len", "n_lines", "random"] if p in PP]
ORDER += [p for p in sorted(PP) if p not in ORDER]


def boot(d, nb=3000, seed=7):
    ks = list(d)
    if not ks:
        return float("nan"), float("nan")
    rr = random.Random(seed)
    o = []
    for _ in range(nb):
        v = [x for k in (rr.choice(ks) for _ in ks) for x in d[k]]
        o.append(sum(v) / len(v))
    o.sort()
    return o[int(.025 * nb)], o[int(.975 * nb)]


def report(sub, title, preds=None):
    preds = preds or ORDER
    n = len(sub)
    if not n:
        print(f"\n{title}: EMPTY")
        return
    wc = sum(ceil[r["k"]] for r in sub) / n
    print(f"\n{title}\n   n={n}   ceiling(upper bound) = {wc:.4f}")
    print(f"   {'predictor':18s} {'acc':>7} {'task-clustered':>19} {'run-clustered':>19} "
          f"{'n':>6} {'cov':>5}")
    for name in preds:
        fn = PRED[name]
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
        star = "  *" if (lo > 0.5 and rlo > 0.5) else ""
        print(f"   {name:18s} {sum(v)/len(v):7.4f} [{lo:6.4f},{hi:6.4f}] "
              f"[{rlo:6.4f},{rhi:6.4f}] {len(v):6d} {len(v)/n:5.2f}{star}")
    print("   * = both clustered intervals exclude 0.5")


print("\n" + "=" * 92)
print("CORRECTED GAP-STRATIFIED TABLE  (x-axis = gap_raw, the label margin)")
print("=" * 92)
print(f"{'bucket':>16} {'n':>6} {'ceil':>6} " + " ".join(f"{p[:11]:>11}" for p in ORDER))
for k in range(len(EDGES) - 1):
    sub = [r for r in rows if r["k"] == k]
    if not sub:
        continue
    cells = []
    for name in ORDER:
        v = [PRED[name](r) for r in sub]
        v = [x for x in v if x is not None]
        cells.append(f"{sum(v)/len(v):11.4f}" if v else f"{'--':>11}")
    print(f"[{EDGES[k]:.0e},{EDGES[k+1]:.0e}) {len(sub):6d} {ceil[k]:6.3f} " +
          " ".join(cells))

hard = [r for r in rows if r["gap"] < HARD]
report(hard, "HARD  gap_raw < 1e-2")
report([r for r in rows if r["gap"] >= HARD], "EASY  gap_raw >= 1e-2")

print("\n" + "=" * 92)
print("ANCHOR: steps_to_best == [0,0] -- label margin IS an own-score margin, so the")
print("ceiling applies exactly here rather than as an upper bound")
print("=" * 92)
own = [r for r in rows if r["own"]]
report([r for r in own if r["gap"] < HARD], "HARD  anchor subset")
report([r for r in own if r["gap"] >= HARD], "EASY  anchor subset")

print("\n" + "=" * 92)
print("SAME-POOL: restricted to pairs every predictor answers")
print("=" * 92)
common = [r for r in rows if all(PRED[p](r) is not None for p in ORDER)]
print(f"pairs answered by all {len(ORDER)} predictors: {len(common)} "
      f"({len(common)/max(len(rows),1):.1%})")
ch = [r for r in common if r["gap"] < HARD]
report(ch, "HARD  same-pool")
report([r for r in common if r["gap"] >= HARD], "EASY  same-pool")

print("\n" + "=" * 92)
print("KILL CONDITIONS, recomputed on the label margin")
print("=" * 92)
byt = collections.Counter(r["task"] for r in hard)
top = byt.most_common(1)[0] if byt else ("-", 0)
share = top[1] / max(len(hard), 1)
print(f"K1  hard pairs = {len(hard)} (need >= 400) -> "
      f"{'PASS' if len(hard) >= 400 else 'FAIL'}")
print(f"    dominant task {top[0][:34]} = {share:.1%} (need <= 85%) -> "
      f"{'PASS' if share <= 0.85 else 'FAIL'}")
print(f"    {'task':44s} {'n':>5} {'rm':>8} {'self_rep':>9}")
for t, c in byt.most_common(10):
    sub = [r for r in hard if r["task"] == t]
    sr = [PRED["self_report"](r) for r in sub] if "self_report" in PRED else []
    sr = [x for x in sr if x is not None]
    print(f"    {t[:44]:44s} {c:5d} {sum(r['rm'] for r in sub)/len(sub):8.4f} "
          + (f"{sum(sr)/len(sr):9.4f}" if sr else f"{'--':>9}"))
big = [(t, c) for t, c in byt.items() if c >= 60]
if len(big) >= 3:
    accs = [(t, sum(r["rm"] for r in hard if r["task"] == t) /
             sum(1 for r in hard if r["task"] == t)) for t, _ in big]
    hi = [t for t, x in accs if x > 0.55]
    lo = [t for t, x in accs if x < 0.45]
    print(f"K2  tasks with n>=60: {len(big)}; above 0.55: {len(hi)}; below 0.45: {len(lo)}"
          f" -> {'FAIL (not one phenomenon)' if hi and lo else 'PASS (consistent)'}")
else:
    print(f"K2  only {len(big)} tasks with n>=60 -- cannot assess")
wc = sum(ceil[r["k"]] for r in hard) / max(len(hard), 1)
wo = (sum(ceil[r["k"]] for r in own if r["gap"] < HARD) /
      max(sum(1 for r in own if r["gap"] < HARD), 1))
print(f"K3  hard ceiling (upper bound, all pairs) = {wc:.4f} (need >= 0.65) -> "
      f"{'PASS' if wc >= 0.65 else 'FAIL'}")
print(f"    hard ceiling (exact, anchor subset)   = {wo:.4f} -> "
      f"{'PASS' if wo >= 0.65 else 'FAIL'}   <- the one that is airtight")
